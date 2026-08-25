"""Convert colour space -- RGB raster to a perceptual space. Wraps
convert_raster through a temp-dir adapter (the package writes into a directory,
not a single file)."""
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)

from .. import core, styling
from ._base import require_packages


class ConvertColourSpaceAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    SPACE = "SPACE"
    OUTPUT = "OUTPUT"

    def __init__(self):
        super().__init__()
        # Populated from the package when available, hardcoded fallback if the
        # import is not ready when the dialog is built.
        self.spaces = core.list_spaces()

    def name(self):
        return "convert_colourspace"

    def displayName(self):
        return "Convert colour space"

    def group(self):
        return "Colour"

    def groupId(self):
        return "colour"

    def createInstance(self):
        return ConvertColourSpaceAlgorithm()

    def shortHelpString(self):
        return (
            "<p>Convert an RGB raster into a perceptual or alternative colour "
            "space &mdash; 15 of them, from CIELAB and CIECAM02 to Oklab and "
            "Jzazbz.</p>"
            "<p>This is the step that makes <i>Grow Seeds</i>' "
            "<code>max_cost</code> meaningful: in CIELAB a distance of 1 is "
            "roughly one just-noticeable difference, so the tolerance reads "
            "as &Delta;E. A Euclidean step in raw RGB has no such "
            "meaning.</p>"
            "<p><b>Scales differ between spaces</b> and it bites when bands "
            "are stacked: L* is 0-100 with a*/b* unbounded, HSV hue is "
            "0-360, YCbCr is studio swing (Y 16-235).</p>"
            "<p><code>cam02</code> is real CIECAM02 and runs here with its "
            "<i>default</i> viewing parameters (L_A=64, Y_b=20, surround "
            "average); exposing those needs a change in pygeopalette itself. "
            "<code>jch</code> is a fast stand-in, not CIECAM02.</p>"
            "<p>Nodata is honoured: source nodata comes out as nodata rather "
            "than being converted as if it were black.</p>")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, "Input RGB raster"))
        default = self.spaces.index("lab") if "lab" in self.spaces else 0
        self.addParameter(QgsProcessingParameterEnum(
            self.SPACE, "Target colour space", options=self.spaces,
            defaultValue=default))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT, "Converted raster"))

    def processAlgorithm(self, parameters, context, feedback):
        require_packages(feedback)
        raster_path = self.parameterAsRasterLayer(
            parameters, self.INPUT, context).source()
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        space = self.spaces[self.parameterAsEnum(
            parameters, self.SPACE, context)]
        feedback.pushInfo(f"Converting to {space}")
        core.run_convert_colourspace(raster_path, space, out)
        styling.style_stretched_raster(context, out)
        return {self.OUTPUT: out}
