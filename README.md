# GeoAdaptels + GeoPalette for QGIS

A QGIS **Processing provider** that exposes the user-facing functions of
[pygeoadaptels](https://github.com/igorpawelec/pygeoadaptels) and
[pygeopalette](https://github.com/igorpawelec/pygeopalette) as Processing
algorithms: pick the algorithm, drop in files, fill parameters, run.

**The plugin is glue.** The algorithms stay in the Python packages; this plugin
turns a QGIS layer into a file path, calls the package's file-level function,
and hands the output back to Processing. No segmentation or colour logic lives
here, so it stays in step with the packages and their R↔Python parity.

## Install

1. Download `geoadaptels_palette-<version>.zip` from
   [Releases](https://github.com/igorpawelec/qgis-geoadaptels-geopalette/releases).
2. QGIS → **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Restart QGIS. The provider appears in the Processing toolbox as
   **GeoAdaptels + GeoPalette**.

`pygeoadaptels` and `pygeopalette` are **bundled inside the zip** — they are
pure Python, so no download and no `git` is needed for them. Three compiled
dependencies are not bundled and cannot be: `numba`, `rasterio` and `fiona`.
The first algorithm run installs them into QGIS's own Python; if that fails on
a locked-down machine, the Processing log prints the exact command to run by
hand.

Upgrading from a version before 0.4.0? **Uninstall the old plugin first** — it
had a different internal id (`geopalette_adaptels`), so QGIS treats this as a
separate plugin and you would end up with two sets of algorithms in the
toolbox.

## Algorithms

| Algorithm | Group | Wraps |
|---|---|---|
| Grow seeds (inverse OBIA) | Segmentation | `grow_seeds_from_files` |
| Adaptels | Segmentation | `create_adaptels` |
| SICLE superpixels | Segmentation | `create_sicle` |
| Enforce connectivity | Segmentation | `enforce_connectivity` (+ raster I/O) |
| Vectorize labels | Vector | `vectorize_from_file` |
| Convert colour space | Colour | `convert_raster` (15 spaces) |

Results are styled on load: label rasters get a palette whose hues step by the
golden angle, so neighbouring regions contrast instead of blending; crown
polygons are drawn outline-only so the imagery stays visible underneath.

## A worked example: standing dead trees

1. **Convert colour space** — RGB ortho → `lab`. This is what makes the next
   step's tolerance meaningful: in CIELAB a distance of 1 is roughly one
   just-noticeable difference, so `max_cost` reads as a ΔE.
2. **Grow seeds** on the Lab raster plus your point layer, with
   `max_cost = 15`, `band_weights = 0.5,2.5,1`, `max_radius = 20`,
   `fill_holes` on.

The weights are the part that matters and the reason is measurable: dead crowns
sit at `a* ≈ +4`, healthy canopy at `a* ≈ -1`, and the gap is no larger than the
brightness variation *inside* a single crown. Weighting `a*` up and `L*` down
separates them — measured on a 0.25 m ortho, it filled more (3544 → 6174 px)
*and* spilled onto healthy trees less (19 % → 5 %) at the same time.
`max_radius` is not optional: without it, past ΔE ≈ 25 one seed floods the whole
scene.

Full guidance is in
[`docs/grow_seeds_guide.md`](https://github.com/igorpawelec/pygeoadaptels/blob/main/docs/grow_seeds_guide.md)
in the package repository.

## Build from source

The build copies the two pure-Python packages into `geoadaptels_palette/vendor/`
at build time, so it expects their checkouts **beside this repository**:

```
parent/
├── qgis-geoadaptels-geopalette/   <- this repo
├── pygeoadaptels/
└── pygeopalette/
```

```bash
python build_zip.py        # -> dist/geoadaptels_palette-0.4.0.zip
```

`vendor/` and `dist/` are build artefacts and are not committed — the vendored
copy is regenerated on every build so it can never quietly drift from the
packages it was cut from.

## What is tested, and what is not

- **`geoadaptels_palette/core.py`** — the layer that actually calls the
  packages — is verified against the real test data by `test_package_calls.py`,
  which runs outside QGIS and also under QGIS's own Python:

  ```bash
  PYTHONPATH="../pygeoadaptels;../pygeopalette;." python test_package_calls.py
  ```

  It confirms every wrapped call, including two corrections to the original
  spec (`read_raster` returns five values and a flat band; the colour
  conversion writes into a directory), and reproduces the dead-tree grow_seeds
  anchor: ~6195 px assigned.

- **The QGIS layer** — imports inside QGIS, the dependency bootstrap, the
  dialogs — has been run in QGIS 3.40 and 3.44 on Windows. All six algorithms
  execute and load their results.

- **Not verified:** a first-run dependency bootstrap on a genuinely clean
  machine (the development machine already had the packages), and anything on
  Linux or macOS. The vendored import path was checked in isolation with
  `PYTHONNOUSERSITE=1`, which is a simulation, not a fresh install.

## In-QGIS checklist

1. The provider **GeoAdaptels + GeoPalette** appears with six algorithms.
2. **Grow seeds** with the parameters above assigns ≈6195 px — the end-to-end
   correctness anchor.
3. A point layer with a **selection** or a **different CRS** still lands on the
   right pixels (the package reprojects; watch the log).
4. Each other algorithm runs and writes a layer QGIS can load.
5. **Convert colour space**: the space list is populated from
   `available_spaces()`, and the temp-dir adapter finds and moves the file.
6. Batch mode and the graphical modeller both see the algorithms.

## The package family

The plugin is the QGIS front-end to a pair of Python packages, each of which
has an R twin. The twins are not ports in name only: `rgeoadaptels` and
`pygeoadaptels` are checked **bit-identical** on 30 cases in CI, and the other
two pairs agree to a documented tolerance.

| | Python | R | What it does |
|---|---|---|---|
| Superpixels | [pygeoadaptels](https://github.com/igorpawelec/pygeoadaptels) | [rgeoadaptels](https://github.com/igorpawelec/rgeoadaptels) | adaptels, SICLE, `grow_seeds` |
| Colour | [pygeopalette](https://github.com/igorpawelec/pygeopalette) | [rgeopalette](https://github.com/igorpawelec/rgeopalette) | 15 colour spaces |
| Tree crowns | [pycacumen](https://github.com/igorpawelec/pycacumen) | [rcacumen](https://github.com/igorpawelec/rcacumen) | crown delineation from a CHM |

`pycacumen` / `rcacumen` are not wrapped by this plugin — they work on canopy
height models rather than orthophotos.

All of them, and this plugin, are at
[github.com/igorpawelec](https://github.com/igorpawelec).

## Citing

If the segmentation contributes to a publication, please cite the method paper
and the software:

> Pawelec, I., Hawryło, P., Netzel, P., & Socha, J. (2026). Evaluating
> superpixel algorithms for standing dead tree delineation using aerial
> orthoimagery. *International Journal of Applied Earth Observation and
> Geoinformation*, 147, 105180.
> [doi:10.1016/j.jag.2026.105180](https://doi.org/10.1016/j.jag.2026.105180)

Each package carries a `CITATION.cff` with machine-readable metadata, including
the algorithm papers behind it — Achanta et al. 2018 for adaptels, Belém et al.
2023 for SICLE.

The adaptels algorithm originates in a C implementation by **Paweł Netzel** at
the University of Agriculture in Kraków; `pygeoadaptels` is a reimplementation
of that work.

## Licence

GPLv3, matching the wrapped packages — which in turn inherit it from the
projects they derive from.
