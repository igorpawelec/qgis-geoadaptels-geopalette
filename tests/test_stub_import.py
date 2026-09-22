"""Import the plugin and build its dialogs against a stub `qgis` module.

What can be checked without a QGIS: every module imports, the provider
lists its six algorithms, every algorithm builds its parameters, the
styling entry points exist, and the dependency bootstrap computes its pip
specs. The stub (tests/qgis_stub) makes every qgis.core name a permissive
dummy, so a wrong parameter class name or a missing import is caught here
and not in the operator's QGIS. The Processing runtime itself is tested in
a live QGIS.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

ALGORITHMS = {
    "adaptels": ("adaptels", "AdaptelsAlgorithm"),
    "convert_colourspace": ("convert_colourspace", "ConvertColourSpaceAlgorithm"),
    "enforce_connectivity": ("enforce_connectivity", "EnforceConnectivityAlgorithm"),
    "grow_seeds": ("grow_seeds", "GrowSeedsAlgorithm"),
    "sicle": ("sicle", "SicleAlgorithm"),
    "vectorize": ("vectorize", "VectorizeAlgorithm"),
}


def _setup():
    for p in (os.path.join(HERE, "qgis_stub"), ROOT):
        if p not in sys.path:
            sys.path.insert(0, p)


def test_provider_lists_six_algorithms():
    _setup()
    from geoadaptels_palette.provider import GeoAdaptelsProvider
    prov = GeoAdaptelsProvider()
    prov.loadAlgorithms()
    assert prov.id() == "geoadaptels" and prov.name() == "GeoAdaptels + GeoPalette"


def test_algorithms_build_their_parameters():
    _setup()
    import importlib
    for module, cls_name in ALGORITHMS.values():
        mod = importlib.import_module(f"geoadaptels_palette.algorithms.{module}")
        a = getattr(mod, cls_name)()
        a.initAlgorithm()
        assert a.name(), cls_name
        assert a.group(), cls_name
        assert len(a.shortHelpString()) > 100, cls_name
        assert a.createInstance().name() == a.name(), cls_name


def test_styling_and_deps_helpers():
    _setup()
    from geoadaptels_palette import deps, styling, vendor_loader
    assert callable(styling.style_polygons) and callable(styling.style_label_raster)
    assert callable(styling.style_stretched_raster)
    specs = deps._install_specs()
    assert any(s.startswith("numba") for s in specs) and any(s.startswith("rasterio") for s in specs)
    assert set(vendor_loader.VENDORED) == {"pygeoadaptels", "pygeopalette"}
    assert callable(deps.manual_hint) and "--target" in deps.manual_hint()
    assert vendor_loader.LIBS_DIR.endswith("libs")
    assert vendor_loader.purge_stale() == 0
    assert callable(styling.band_ranges)
