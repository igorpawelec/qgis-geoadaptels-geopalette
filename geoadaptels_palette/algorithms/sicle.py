"""SICLE superpixels -- you set the count. Wraps create_sicle."""
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterBand,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)

from .. import core, styling
from ._base import advanced, require_packages, warm_jit


class SicleAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    BANDS = "BANDS"
    N_SEGMENTS = "N_SEGMENTS"
    N_OVERSAMPLING = "N_OVERSAMPLING"
    N_ITERATIONS = "N_ITERATIONS"
    SALIENCY = "SALIENCY"
    RANDOM_STATE = "RANDOM_STATE"
    OUTPUT = "OUTPUT"

    def name(self):
        return "sicle"

    def displayName(self):
        return "SICLE superpixels"

    def group(self):
        return "Segmentation"

    def groupId(self):
        return "segmentation"

    def createInstance(self):
        return SicleAlgorithm()

    def shortHelpString(self):
        return (
            "<p>Superpixels through Iterative CLEarcutting: start from far "
            "more seeds than you want, grow an optimum-path forest, score "
            "every seed, discard the least relevant, repeat. Unlike "
            "<i>Adaptels</i> the count is a target you set.</p>"
            "<p><code>n_iterations</code> does less than it looks. The "
            "paper's preservation curve makes 3 bit-identical to 2, and 5 "
            "performs two removal steps rather than five. Belem et al. use 2 "
            "as a <i>speed</i> setting whose rationale is specific to the "
            "differential IFT this does not use &mdash; raising it can "
            "improve delineation.</p>"
            "<p>A <b>saliency</b> raster (e.g. a normalised CHM) makes seeds "
            "near object borders survive removal. It must not be nodata "
            "where the raster is valid.</p>"
            "<p>Every label is a single 8-connected region, so do not follow "
            "this with <i>Enforce connectivity</i>: that tests "
            "4-connectivity and would split each superpixel into pieces that "
            "were never disconnected.</p>")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, "Input raster"))
        # Empty means every band -- the old behaviour and the right default.
        self.addParameter(QgsProcessingParameterBand(
            self.BANDS, "Bands to use (leave empty for all)", None,
            self.INPUT, optional=True, allowMultiple=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.N_SEGMENTS, "n_segments (desired count)",
            QgsProcessingParameterNumber.Integer, defaultValue=200,
            minValue=1))
        self.addParameter(advanced(QgsProcessingParameterNumber(
            self.N_OVERSAMPLING, "n_oversampling (initial seeds)",
            QgsProcessingParameterNumber.Integer, defaultValue=3000,
            minValue=1)))
        self.addParameter(advanced(QgsProcessingParameterNumber(
            self.N_ITERATIONS, "n_iterations",
            QgsProcessingParameterNumber.Integer, defaultValue=2,
            minValue=1)))
        self.addParameter(advanced(QgsProcessingParameterRasterLayer(
            self.SALIENCY, "Saliency raster (optional)", optional=True)))
        self.addParameter(advanced(QgsProcessingParameterNumber(
            self.RANDOM_STATE, "random_state (seed sampling)",
            QgsProcessingParameterNumber.Integer, defaultValue=42)))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT, "SICLE labels"))

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
        sal_layer = self.parameterAsRasterLayer(
            parameters, self.SALIENCY, context)
        saliency_file = sal_layer.source() if sal_layer is not None else None
        feedback.pushInfo(
            f"Segmenting on bands {bands or list(range(1, n_bands + 1))}")
        with core.band_subset(raster_path, bands, n_bands) as src:
            n = core.run_sicle(
                src, out,
                n_segments=self.parameterAsInt(parameters, self.N_SEGMENTS, context),
                n_oversampling=self.parameterAsInt(parameters, self.N_OVERSAMPLING, context),
                n_iterations=self.parameterAsInt(parameters, self.N_ITERATIONS, context),
                saliency_file=saliency_file,
                random_state=self.parameterAsInt(parameters, self.RANDOM_STATE, context))
        feedback.pushInfo(f"{n} superpixels")
        styling.style_label_raster(context, out)
        return {self.OUTPUT: out}
