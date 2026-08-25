"""Enforce connectivity -- split any label that arrives in more than one piece.

There is no file wrapper in the package for this one, so core.run_enforce_
connectivity does the I/O: read the label raster (read_raster returns FIVE
values and a flat band), reshape, run enforce_connectivity, write back.
"""
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)

from .. import core, styling
from ._base import require_packages


class EnforceConnectivityAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    MIN_SIZE = "MIN_SIZE"
    OUTPUT = "OUTPUT"

    def name(self):
        return "enforce_connectivity"

    def displayName(self):
        return "Enforce connectivity"

    def group(self):
        return "Segmentation"

    def groupId(self):
        return "segmentation"

    def createInstance(self):
        return EnforceConnectivityAlgorithm()

    def shortHelpString(self):
        return (
            "<p>Split any label that arrives in more than one connected "
            "piece, so every region is contiguous.</p>"
            "<p>Adaptels compete for pixels: a later one takes a pixel from "
            "an earlier one whenever it arrives with a smaller accumulated "
            "distance. That competition is what gives the method its "
            "boundary adherence, and it can also cut an earlier adaptel in "
            "two &mdash; about 10% of them on a typical scene.</p>"
            "<p>Harmless if the labels are only a lookup. <b>Not</b> "
            "harmless for zonal statistics, which would average two "
            "spatially separate patches into one 'object'. The adaptel count "
            "rises by roughly 10%; nothing is merged and no pixel changes "
            "hands. <code>min_size</code> absorbs fragments below a size "
            "into a neighbour instead of keeping them.</p>"
            "<p>This tests <b>4</b>-connectivity, the adaptels grower's "
            "neighbourhood. Do not run it on SICLE or Grow Seeds output, "
            "which is 8-connected by construction.</p>")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, "Label raster"))
        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_SIZE, "min_size (0 = keep every component)",
            QgsProcessingParameterNumber.Integer, defaultValue=0, minValue=0))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT, "Connectivity-enforced labels"))

    def processAlgorithm(self, parameters, context, feedback):
        require_packages(feedback)
        raster_path = self.parameterAsRasterLayer(
            parameters, self.INPUT, context).source()
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        n = core.run_enforce_connectivity(
            raster_path, out,
            min_size=self.parameterAsInt(parameters, self.MIN_SIZE, context))
        feedback.pushInfo(f"{n} labels after enforcing connectivity")
        styling.style_label_raster(context, out)
        return {self.OUTPUT: out}
