"""Adaptels -- scale-adaptive superpixels. Wraps create_adaptels."""
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)

from .. import core, styling
from ._base import advanced, require_packages

DISTANCES = ["minkowski", "cosine", "angular"]


class AdaptelsAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
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
            "<p>Adaptels compete for pixels, which can leave one label in "
            "two separate patches (about 10% of them). Harmless for a "
            "lookup, not harmless for zonal statistics &mdash; run "
            "<i>Enforce connectivity</i> if that matters.</p>")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, "Input raster"))
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

    def processAlgorithm(self, parameters, context, feedback):
        require_packages(feedback)
        raster_path = self.parameterAsRasterLayer(
            parameters, self.INPUT, context).source()
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        distance = DISTANCES[self.parameterAsEnum(
            parameters, self.DISTANCE, context)]
        n = core.run_adaptels(
            raster_path, out,
            threshold=self.parameterAsDouble(parameters, self.THRESHOLD, context),
            distance=distance,
            minkowski_p=self.parameterAsDouble(parameters, self.MINKOWSKI_P, context),
            queen_topology=self.parameterAsBool(parameters, self.QUEEN, context),
            normalize=self.parameterAsBool(parameters, self.NORMALIZE, context))
        feedback.pushInfo(f"{n} adaptels")
        styling.style_label_raster(context, out)
        return {self.OUTPUT: out}
