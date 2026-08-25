"""Plugin entry: register the Processing provider, try the dependency bootstrap.

The provider is always registered so the toolbox entry appears; whether the
wrapped packages are importable is a per-run concern handled in each algorithm
(they call deps.ensure_dependencies and report to the Processing log rather
than crashing the plugin at load).
"""
from qgis.core import QgsApplication

from .provider import GeoAdaptelsProvider


class Plugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initGui(self):
        # Put the bundled packages on sys.path as early as possible, so they
        # are importable from the Python console too, not just inside an
        # algorithm run. Never fatal: the algorithms check again and report
        # properly if something is genuinely missing.
        try:
            from . import vendor_loader
            vendor_loader.activate()
        except Exception:
            pass

        self.provider = GeoAdaptelsProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
