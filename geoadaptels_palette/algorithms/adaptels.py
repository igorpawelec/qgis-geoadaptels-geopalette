"""Adaptels -- scale-adaptive superpixels. Wraps create_adaptels."""
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterBand,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)

from .. import core, styling
from ._base import advanced, require_packages, warm_jit

DISTANCES = ["minkowski", "cosine", "angular"]


class AdaptelsAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    BANDS = "BANDS"
    THRESHOLD = "THRESHOLD"
    DISTANCE = "DISTANCE"
    MINKOWSKI_P = "MINKOWSKI_P"
    QUEEN = "QUEEN"
    NORMALIZE = "NORMALIZE"
    OUTPUT = "OUTPUT"

    def name(self):
        return "adaptels"

    def displayName(self):
        return "Adaptels (scale-adaptive superpixels)"

    def group(self):
        return "Segmentation"

    def groupId(self):
        return "segmentation"

    def createInstance(self):
        return AdaptelsAlgorithm()

    def shortHelpString(self):
        return (
            "<p>Scale-adaptive superpixels: regions grow until their internal "
            "distance passes <code>threshold</code>, so their size follows "
            "the scene &mdash; small where it is textured, large where it is "
            "flat. There is no target count.</p>"
            "<p><b>The threshold is per metric, not universal.</b> The "
            "default 60 is scaled for <code>minkowski</code> on 0-255 "
            "imagery; <code>cosine</code> and <code>angular</code> live in "
            "[0, 1] and want about 0.03. Passing 60 to those would merge the "
            "whole raster, so the package rejects it rather than returning "
            "nonsense.</p>"
            "<p><code>cosine</code> and <code>angular</code> compare the "
            "<i>direction</i> of the spectral vector, so the same material "
            "lit differently &mdash; a crown in sun and in shade &mdash; "
            "stays one region. <code>minkowski</code> will split it.</p>"
            "<p><b>Bands:</b> empty means all of them, which is usually what "
            "you want &mdash; adaptels compare whole spectral vectors, and on "
            "a 4-band ortho the infrared is the band that separates dead "
            "crowns best. Pick a subset to segment on fewer bands, or a single "
            "band to segment on that one alone. Band order does not matter "
            "here; only which bands are included.</p>"
            "<p>Adaptels compete for pixels, which can leave one label in "
            "two separate patches (about 10% of them). Harmless for a "
            "lookup, not harmless for zonal statistics &mdash; run "
            "<i>Enforce connectivity</i> if that matters.</p>")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, "Input raster"))
        # Empty means every band, which is both the old behaviour and the right
        # default: adaptels compare whole spectral vectors, and dropping the
        # infrared throws away the band that separates dead crowns best.
        # Selecting one band segments on that band alone.
        self.addParameter(QgsProcessingParameterBand(
            self.BANDS, "Bands to use (leave empty for all)", None,
            self.INPUT, optional=True, allowMultiple=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.THRESHOLD, "threshold (metric-dependent)",
            QgsProcessingParameterNumber.Double, defaultValue=60.0,
            minValue=0.0))
        self.addParameter(QgsProcessingParameterEnum(
            self.DISTANCE, "distance", options=DISTANCES, defaultValue=0))
        self.addParameter(advanced(QgsProcessingParameterNumber(
            self.MINKOWSKI_P, "minkowski_p (2 = Euclidean)",
            QgsProcessingParameterNumber.Double, defaultValue=2.0,
            minValue=0.1)))
        self.addParameter(advanced(QgsProcessingParameterBoolean(
            self.QUEEN, "queen_topology (8-connectivity)",
            defaultValue=False)))
        self.addParameter(advanced(QgsProcessingParameterBoolean(
            self.NORMALIZE, "normalize inputs to [0, 1]",
            defaultValue=False)))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT, "Adaptel labels"))

    def prepareAlgorithm(self, parameters, context, feedback):
        # Main thread. The numba kernels must be compiled here -- see warm_jit.
        warm_jit(feedback)
        return True

    def processAlgorithm(self, parameters, context, feedback):
        require_packages(feedback)
        layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        raster_path = layer.source()
        n_bands = layer.bandCount()
        bands = self.parameterAsInts(parameters, self.BANDS, context) or []
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        distance = DISTANCES[self.parameterAsEnum(
            parameters, self.DISTANCE, context)]
        feedback.pushInfo(
            f"Segmenting on bands {bands or list(range(1, n_bands + 1))}")
        with core.band_subset(raster_path, bands, n_bands) as src:
            n = core.run_adaptels(
                src, out,
                threshold=self.parameterAsDouble(parameters, self.THRESHOLD, context),
                distance=distance,
                minkowski_p=self.parameterAsDouble(parameters, self.MINKOWSKI_P, context),
                queen_topology=self.parameterAsBool(parameters, self.QUEEN, context),
                normalize=self.parameterAsBool(parameters, self.NORMALIZE, context))
        feedback.pushInfo(f"{n} adaptels")
        styling.style_label_raster(context, out)
        return {self.OUTPUT: out}
