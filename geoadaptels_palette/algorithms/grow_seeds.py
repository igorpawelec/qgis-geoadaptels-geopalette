"""Grow Seeds -- seeded spectral region growing (inverse OBIA).

The reference algorithm; the others copy its shape. QGIS parameters are mapped
onto core.run_grow_seeds, which calls pygeoadaptels.grow.grow_seeds_from_files.
"""
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
    QgsProcessingParameterVectorDestination,
)

from .. import core, styling
from ._base import advanced, require_packages


class GrowSeedsAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    POINTS = "POINTS"
    MAX_COST = "MAX_COST"
    BAND_WEIGHTS = "BAND_WEIGHTS"
    COMPACTNESS = "COMPACTNESS"
    SEED_WINDOW = "SEED_WINDOW"
    MAX_RADIUS = "MAX_RADIUS"
    FILL_HOLES = "FILL_HOLES"
    OUTPUT = "OUTPUT"
    POLYGONS = "POLYGONS"

    def name(self):
        return "grow_seeds"

    def displayName(self):
        return "Grow seeds (inverse OBIA)"

    def group(self):
        return "Segmentation"

    def groupId(self):
        return "segmentation"

    def createInstance(self):
        return GrowSeedsAlgorithm()

    def shortHelpString(self):
        return (
            "<p>Grow each operator-placed point into the region that looks "
            "like the pixel it sits on. Everything unseeded stays nodata "
            "(-1). This is the inverse of Adaptels/SICLE: <b>you</b> supply "
            "the objects, the algorithm supplies their boundaries.</p>"
            "<p><b>Feed a CIELAB raster</b> (use <i>Convert colour space</i> "
            "first). <code>max_cost</code> is then a &Delta;E tolerance: 10 "
            "means the region will not cross anything more than &Delta;E 10 "
            "from the pixel you clicked. On raw RGB the number carries no "
            "perceptual meaning.</p>"
            "<p><b>Working recipe for standing dead trees</b>, measured on a "
            "0.25 m orthophoto:</p>"
            "<ul>"
            "<li><code>band_weights = 0.5,2.5,1</code> &mdash; down-weight "
            "L*, up-weight a*. Dead crowns sit at a*&asymp;+4, healthy canopy "
            "at a*&asymp;-1, and the gap is small, so this is what separates "
            "them. Measured: fills <i>more</i> (3544&rarr;6174 px) and spills "
            "onto healthy trees <i>less</i> (19%&rarr;5%) at the same "
            "time.</li>"
            "<li><code>max_cost = 15</code></li>"
            "<li><code>max_radius = 20</code> px &mdash; <b>not optional</b>. "
            "There is no plateau on this kind of scene: past &Delta;E&asymp;"
            "25 one seed floods the whole image.</li>"
            "<li><code>fill_holes</code> on &mdash; closes the pockets a cost "
            "cut leaves inside a crown.</li>"
            "</ul>"
            "<p>Label <i>i</i> is the region grown from the <i>i</i>-th "
            "point, so the result joins back to that point's attributes. Two "
            "points in one pixel is an error, not a silent merge.</p>")

    def helpUrl(self):
        return "https://github.com/igorpawelec/pygeoadaptels/blob/main/docs/grow_seeds_guide.md"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, "Input raster (CIELAB recommended)"))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.POINTS, "Seed points", [QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterNumber(
            self.MAX_COST, "max_cost (delta-E tolerance; empty = no cap)",
            QgsProcessingParameterNumber.Double, optional=True, minValue=0.0))
        self.addParameter(QgsProcessingParameterString(
            self.BAND_WEIGHTS, "band_weights (comma-separated, e.g. 0.5,2.5,1)",
            optional=True))
        self.addParameter(advanced(QgsProcessingParameterNumber(
            self.COMPACTNESS, "compactness (0 = pure spectral)",
            QgsProcessingParameterNumber.Double, defaultValue=0.0,
            minValue=0.0)))
        self.addParameter(advanced(QgsProcessingParameterNumber(
            self.SEED_WINDOW, "seed_window (k x k median; 1 = raw pixel, odd)",
            QgsProcessingParameterNumber.Integer, defaultValue=1,
            minValue=1)))
        self.addParameter(QgsProcessingParameterNumber(
            self.MAX_RADIUS, "max_radius (pixels; empty = unlimited)",
            QgsProcessingParameterNumber.Integer, optional=True, minValue=1))
        self.addParameter(advanced(QgsProcessingParameterBoolean(
            self.FILL_HOLES, "fill_holes", defaultValue=True)))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT, "Label raster", optional=True, createByDefault=True))
        self.addParameter(QgsProcessingParameterVectorDestination(
            self.POLYGONS, "Crown polygons", optional=True,
            createByDefault=False))

    def _optional_set(self, parameters, key):
        return parameters.get(key) is not None and parameters.get(key) != ""

    def processAlgorithm(self, parameters, context, feedback):
        require_packages(feedback)

        raster = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        raster_path = raster.source()

        # Export the point layer to a real file so the package's reader gets a
        # path, honouring any selection/filter on the layer.
        points_path = self.parameterAsCompatibleSourceLayerPath(
            parameters, self.POINTS, context, ["gpkg", "shp"], "gpkg",
            feedback)

        out_labels = self.parameterAsOutputLayer(
            parameters, self.OUTPUT, context) or None
        out_polys = self.parameterAsOutputLayer(
            parameters, self.POLYGONS, context) or None

        kwargs = {}
        if self._optional_set(parameters, self.MAX_COST):
            kwargs["max_cost"] = self.parameterAsDouble(
                parameters, self.MAX_COST, context)
        bw = self.parameterAsString(parameters, self.BAND_WEIGHTS, context)
        if bw:
            try:
                kwargs["band_weights"] = [
                    float(x) for x in bw.replace(";", ",").split(",")
                    if x.strip()]
            except ValueError:
                from qgis.core import QgsProcessingException
                raise QgsProcessingException(
                    f"band_weights must be numbers separated by commas, got "
                    f"{bw!r}")
        comp = self.parameterAsDouble(parameters, self.COMPACTNESS, context)
        if comp > 0:
            kwargs["compactness"] = comp
        sw = self.parameterAsInt(parameters, self.SEED_WINDOW, context)
        if sw > 1:
            kwargs["seed_window"] = sw
        if self._optional_set(parameters, self.MAX_RADIUS):
            kwargs["max_radius"] = self.parameterAsInt(
                parameters, self.MAX_RADIUS, context)
        kwargs["fill_holes"] = self.parameterAsBool(
            parameters, self.FILL_HOLES, context)

        feedback.pushInfo(f"grow_seeds parameters: {kwargs}")
        core.run_grow_seeds(raster_path, points_path,
                            out_labels=out_labels, out_polys=out_polys,
                            **kwargs)

        # Cosmetic, and deliberately after the work: a styling failure must
        # never cost the operator a finished segmentation.
        if out_labels:
            styling.style_label_raster(context, out_labels)
        if out_polys:
            styling.style_polygons(context, out_polys)

        result = {}
        if out_labels:
            result[self.OUTPUT] = out_labels
        if out_polys:
            result[self.POLYGONS] = out_polys
        return result
