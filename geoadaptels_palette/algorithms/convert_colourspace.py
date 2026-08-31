"""Convert colour space -- RGB raster to a perceptual space. Wraps
convert_raster through a temp-dir adapter (the package writes into a directory,
not a single file)."""
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterBand,
    QgsProcessingParameterEnum,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)

from .. import core, styling
from ._base import band_hint, require_packages, warm_jit


class ConvertColourSpaceAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    SPACE = "SPACE"
    RED = "RED"
    GREEN = "GREEN"
    BLUE = "BLUE"
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
            "than being converted as if it were black.</p>"
            "<p><b>Set the band numbers to match your raster.</b> The "
            "conversions are defined on red, green and blue, and the defaults "
            "1/2/3 are right only for a true-colour image. A CIR raster is "
            "(NIR, R, G) and an NRGB one puts the infrared first, so leaving "
            "the defaults there converts the wrong three bands and calls the "
            "result CIELAB. Running a space over a false-colour triple on "
            "purpose is a legitimate technique &mdash; just do it knowingly. "
            "The log warns when the band picked as red looks like "
            "infrared.</p>")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, "Input RGB raster"))
        default = self.spaces.index("lab") if "lab" in self.spaces else 0
        self.addParameter(QgsProcessingParameterEnum(
            self.SPACE, "Target colour space", options=self.spaces,
            defaultValue=default))
        # Which band is which. The conversions are defined on R, G, B; on a CIR
        # or NRGB raster the first three bands are not that, and the result
        # would be a false-colour transform wearing a colour-space name.
        for key, label, dflt in ((self.RED, "Red band", 1),
                                 (self.GREEN, "Green band", 2),
                                 (self.BLUE, "Blue band", 3)):
            self.addParameter(QgsProcessingParameterBand(
                key, label, dflt, self.INPUT))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT, "Converted raster"))

    def prepareAlgorithm(self, parameters, context, feedback):
        # Main thread. The numba kernels must be compiled here -- see warm_jit.
        warm_jit(feedback)
        return True

    def processAlgorithm(self, parameters, context, feedback):
        require_packages(feedback)
        layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        raster_path = layer.source()
        n_bands = layer.bandCount()
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        space = self.spaces[self.parameterAsEnum(
            parameters, self.SPACE, context)]
        rgb = [self.parameterAsInt(parameters, k, context)
               for k in (self.RED, self.GREEN, self.BLUE)]
        feedback.pushInfo(f"Converting to {space} from bands "
                          f"R={rgb[0]}, G={rgb[1]}, B={rgb[2]}")
        band_hint(raster_path, rgb, feedback)
        with core.band_subset(raster_path, rgb, n_bands) as src:
            core.run_convert_colourspace(src, space, out)
        styling.style_stretched_raster(context, out)
        return {self.OUTPUT: out}
