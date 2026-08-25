"""The Processing provider: registers the six algorithms."""
import os

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .algorithms.adaptels import AdaptelsAlgorithm
from .algorithms.convert_colourspace import ConvertColourSpaceAlgorithm
from .algorithms.enforce_connectivity import EnforceConnectivityAlgorithm
from .algorithms.grow_seeds import GrowSeedsAlgorithm
from .algorithms.sicle import SicleAlgorithm
from .algorithms.vectorize import VectorizeAlgorithm


class GeoAdaptelsProvider(QgsProcessingProvider):
    def loadAlgorithms(self):
        for alg in (
            GrowSeedsAlgorithm(),
            AdaptelsAlgorithm(),
            SicleAlgorithm(),
            EnforceConnectivityAlgorithm(),
            VectorizeAlgorithm(),
            ConvertColourSpaceAlgorithm(),
        ):
            self.addAlgorithm(alg)

    def id(self):
        return "geoadaptels"

    def name(self):
        # Kept identical to `name=` in metadata.txt on purpose: the Plugin
        # Manager reads that one and the Processing toolbox reads this one, and
        # two spellings of the same plugin read as two different things.
        return "GeoAdaptels + GeoPalette"

    def longName(self):
        return ("GeoAdaptels + GeoPalette (superpixels, seeded growing, "
                "colour spaces)")

    def icon(self):
        p = os.path.join(os.path.dirname(__file__), "icon.png")
        return QIcon(p) if os.path.exists(p) else QgsProcessingProvider.icon(self)
