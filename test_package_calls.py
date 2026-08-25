"""Exercise geoadaptels_palette/core.py against the real test data, WITHOUT
QGIS. This is what can be verified here; the QGIS parameter glue and the
in-QGIS runtime are the user's to test in a live QGIS.

Run with a Python that has pygeoadaptels + pygeopalette + numba + rasterio:

    PYTHONPATH="D:/Apps/pygeoadaptels;D:/Apps/pygeopalette;D:/Apps/qgis-geoadaptels-geopalette" \
        D:/miniforge3/envs/ml/python.exe qgis-geoadaptels-geopalette/test_package_calls.py
"""
import os
import sys
import tempfile

from geoadaptels_palette import core

DATA = "D:/Apps/pygeoadaptels/test_data"
RGB = os.path.join(DATA, "SNP_21_2020_1.tif")
LAB = os.path.join(DATA, "SNP_21_2020_1_lab.tif")
SHP = os.path.join(DATA, "dead_trees_test.shp")


def _exists(p):
    return os.path.exists(p) and os.path.getsize(p) > 0


def main():
    for p in (RGB, LAB, SHP):
        if not _exists(p):
            print(f"SKIP: missing {p}")
            return 0
    fails = []
    with tempfile.TemporaryDirectory() as td:
        j = lambda n: os.path.join(td, n)

        spaces = core.list_spaces()
        ok = len(spaces) == 15 and "lab" in spaces and "cam02" in spaces
        print(f"list_spaces        : {len(spaces)} spaces  {'OK' if ok else 'FAIL'}")
        if not ok:
            fails.append("list_spaces")

        core.run_convert_colourspace(RGB, "lab", j("lab.tif"))
        ok = _exists(j("lab.tif"))
        print(f"convert (RGB->lab) : {'OK' if ok else 'FAIL'}  temp-dir adapter")
        if not ok:
            fails.append("convert")

        n_ad = core.run_adaptels(RGB, j("ad.tif"), threshold=60)
        ok = _exists(j("ad.tif")) and n_ad > 0
        print(f"adaptels           : {n_ad} adaptels  {'OK' if ok else 'FAIL'}")
        if not ok:
            fails.append("adaptels")

        # The spec-bug fix: read_raster 5-tuple + reshape flat band to 2-D.
        n_ec = core.run_enforce_connectivity(j("ad.tif"), j("ec.tif"), min_size=0)
        ok = _exists(j("ec.tif")) and n_ec >= n_ad
        print(f"enforce_connect.   : {n_ad} -> {n_ec}  {'OK' if ok else 'FAIL'}  "
              f"(5-tuple + reshape)")
        if not ok:
            fails.append("enforce_connectivity")

        n_poly = core.run_vectorize(j("ad.tif"), j("ad.gpkg"), connectivity=8)
        ok = _exists(j("ad.gpkg")) and n_poly > 0
        print(f"vectorize (conn=8) : {n_poly} polygons  {'OK' if ok else 'FAIL'}")
        if not ok:
            fails.append("vectorize")

        n_si = core.run_sicle(RGB, j("si.tif"), n_segments=100)
        ok = _exists(j("si.tif")) and n_si > 0
        print(f"sicle              : {n_si} superpixels  {'OK' if ok else 'FAIL'}")
        if not ok:
            fails.append("sicle")

        # End-to-end correctness anchor: the dead-tree recipe from
        # grow_seeds_parametry.md -- ~6174 px assigned.
        import numpy as np
        import rasterio
        core.run_grow_seeds(
            LAB, SHP, out_labels=j("g.tif"), out_polys=j("g.gpkg"),
            max_cost=15, band_weights=[0.5, 2.5, 1.0], max_radius=20,
            fill_holes=True)
        with rasterio.open(j("g.tif")) as s:
            lab = s.read(1)
        assigned = int((lab != s.nodata).sum())
        ok = _exists(j("g.gpkg")) and 5500 < assigned < 6800
        print(f"grow_seeds (recipe): {assigned} px assigned  "
              f"{'OK' if ok else 'FAIL'}  (anchor ~6174)")
        if not ok:
            fails.append("grow_seeds")

    print()
    if fails:
        print(f"FAILED: {fails}")
        return 1
    print("ALL CORE CALLS OK -- package-side logic verified outside QGIS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
