"""Pure package-call layer for the QGIS plugin.

Every function here takes plain paths and values and calls exactly one
pygeoadaptels / pygeopalette entry point. **Nothing in this module imports
qgis**, on purpose: it is the part that actually touches the packages, so it
can be unit-tested outside QGIS (see ../test_package_calls.py). The QGIS
algorithm classes in algorithms/ are thin wrappers that map dialog parameters
onto these functions.

Wrap, do not reimplement: no segmentation or colour logic lives here, only the
glue that turns "a raster path + parameters" into "the package's file-level
call". That keeps the plugin in step with the R/Python packages and their
bit-identical parity.

Copyright (C) 2026 Igor Pawelec. Licence: GPLv3.
"""

import glob
import os
import shutil
import tempfile


# ── colour spaces ──────────────────────────────────────────────────────

_SPACE_FALLBACK = ["cam02", "dlab", "hsi", "hsl", "hsv", "jch", "jzazbz",
                   "jzczhz", "lab", "lchab", "lchuv", "luv", "oklab", "xyY",
                   "ycbcr"]


def list_spaces():
    """Colour spaces pygeopalette offers, or a hardcoded fallback if the import
    is not ready when the dialog is built."""
    try:
        from pygeopalette import available_spaces
        spaces = list(available_spaces())
        return spaces or list(_SPACE_FALLBACK)
    except Exception:
        return list(_SPACE_FALLBACK)


# ── segmentation ───────────────────────────────────────────────────────

def run_adaptels(raster_path, out_path, threshold=60.0, distance="minkowski",
                 minkowski_p=2.0, queen_topology=False, normalize=False):
    from pygeoadaptels import create_adaptels
    _, n = create_adaptels(
        raster_path, output_file=out_path, threshold=threshold,
        distance=distance, minkowski_p=minkowski_p,
        queen_topology=queen_topology, normalize=normalize, quiet=True)
    return n


def run_sicle(raster_path, out_path, n_segments=200, n_oversampling=3000,
              n_iterations=2, saliency_file=None, random_state=42):
    from pygeoadaptels.sicle import create_sicle
    _, n = create_sicle(
        raster_path, output_file=out_path, n_segments=n_segments,
        n_oversampling=n_oversampling, n_iterations=n_iterations,
        saliency_file=saliency_file, random_state=random_state, quiet=True)
    return n


def run_grow_seeds(raster_path, points_path, out_labels=None, out_polys=None,
                   **kwargs):
    """kwargs -> grow_seeds: max_cost, band_weights, compactness, seed_window,
    max_radius, fill_holes. The package reprojects the point layer to the
    raster CRS and does the point->pixel conversion itself."""
    from pygeoadaptels.grow import grow_seeds_from_files
    grow_seeds_from_files(
        raster_path, points_path, output_file=out_labels, polygons=out_polys,
        quiet=True, **kwargs)


def run_enforce_connectivity(raster_path, out_path, min_size=0):
    """Read a single-band label raster, split any label that arrives in more
    than one connected piece, write it back.

    read_raster returns FIVE values -- (layers, mask, meta, cols, rows) -- and
    `layers` is flattened to (n_layers, size), so the band has to be reshaped
    to 2-D before enforce_connectivity sees it. (The spec's stub unpacked
    three values and skipped the reshape; both would raise.)
    """
    import numpy as np
    from pygeoadaptels import enforce_connectivity, read_raster, write_raster
    layers, _mask, meta, cols, rows = read_raster(raster_path)
    labels = np.asarray(layers[0], dtype=np.int32).reshape(rows, cols)
    new_labels, n = enforce_connectivity(labels, min_size=min_size)
    write_raster(out_path, new_labels, meta, cols, rows)
    return n


# ── vectorize ──────────────────────────────────────────────────────────

def run_vectorize(raster_path, out_path, connectivity=8, compute_area=True,
                  driver=None):
    """Polygonise a label raster. Driver is inferred from the output extension
    when not given; grow/adaptels labels are 8-connected, so default to 8."""
    from pygeoadaptels.vectorize import vectorize_from_file
    if driver is None:
        ext = os.path.splitext(out_path)[1].lower()
        driver = {".gpkg": "GPKG", ".geojson": "GeoJSON",
                  ".shp": "ESRI Shapefile"}.get(ext, "GPKG")
    return vectorize_from_file(
        raster_path, out_path, driver=driver, connectivity=connectivity,
        compute_area=compute_area, quiet=True)


# ── colour ─────────────────────────────────────────────────────────────

def run_convert_colourspace(raster_path, space, out_path):
    """convert_raster writes ``<base>_<space>.tif`` into a *directory* and
    takes no single-file argument, so it runs into a temp dir and the one
    multiband tif is moved to the user's chosen path.

    CAM02 uses its default viewing parameters (L_A, Y_b, surround); exposing
    them would need a convert_raster signature change in pygeopalette, out of
    scope for the plugin.
    """
    from pygeopalette.io_utils import convert_raster
    with tempfile.TemporaryDirectory() as td:
        convert_raster(raster_path, td, space, quiet=True)
        tifs = sorted(glob.glob(os.path.join(td, "*.tif")))
        if not tifs:
            raise RuntimeError(
                f"convert_raster produced no GeoTIFF for space '{space}'")
        # save_multiband defaults to True and save_singlebands to False, so
        # there is exactly one file; guard anyway.
        parent = os.path.dirname(os.path.abspath(out_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        if os.path.exists(out_path):
            os.remove(out_path)
        shutil.move(tifs[0], out_path)
    return out_path
