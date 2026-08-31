"""Vectorize -- polygonise a label raster. Wraps vectorize_from_file."""
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterVectorDestination,
)

from .. import core, styling
from ._base import advanced, require_packages, warm_jit

CONNECTIVITY = ["4", "8"]


class VectorizeAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    CONNECTIVITY = "CONNECTIVITY"
    COMPUTE_AREA = "COMPUTE_AREA"
    OUTPUT = "OUTPUT"

    def name(self):
        return "vectorize"

    def displayName(self):
        return "Vectorize labels"

    def group(self):
        return "Vector"

    def groupId(self):
        return "vector"

    def createInstance(self):
        return VectorizeAlgorithm()

    def shortHelpString(self):
        return (
            "<p>Polygonise a label raster, one polygon per region, with area "
            "and perimeter as attributes.</p>"
            "<p><b>Connectivity has to match how the labels were grown.</b> "
            "SICLE and Grow Seeds grow over 8 neighbours, so a crown that "
            "pinches on a diagonal is <i>one</i> region &mdash; polygonising "
            "it 4-connected splits it into separate rings that look like a "
            "defect and are only an artefact. Default 8 is right for those. "
            "Use 4 only for a raster produced 4-connected (Adaptels with "
            "<code>queen_topology</code> off).</p>"
            "<p>The output format follows the file extension: .gpkg is "
            "recommended &mdash; one file, no field-name limits, so joining "
            "back to point attributes stays clean.</p>")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, "Label raster"))
        self.addParameter(QgsProcessingParameterEnum(
            self.CONNECTIVITY, "connectivity", options=CONNECTIVITY,
            defaultValue=1))          # default index 1 -> "8"
        self.addParameter(advanced(QgsProcessingParameterBoolean(
            self.COMPUTE_AREA, "compute area / perimeter",
            defaultValue=True)))
        self.addParameter(QgsProcessingParameterVectorDestination(
            self.OUTPUT, "Polygons"))

    def prepareAlgorithm(self, parameters, context, feedback):
        # Main thread. The numba kernels must be compiled here -- see warm_jit.
        warm_jit(feedback)
        return True

    def processAlgorithm(self, parameters, context, feedback):
        require_packages(feedback)
        raster_path = self.parameterAsRasterLayer(
            parameters, self.INPUT, context).source()
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        conn = int(CONNECTIVITY[self.parameterAsEnum(
            parameters, self.CONNECTIVITY, context)])
        n = core.run_vectorize(
            raster_path, out, connectivity=conn,
            compute_area=self.parameterAsBool(
                parameters, self.COMPUTE_AREA, context))
        feedback.pushInfo(f"{n} polygons")
        styling.style_polygons(context, out)
        return {self.OUTPUT: out}
