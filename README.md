# GeoAdaptels + GeoPalette for QGIS

[![tests](https://github.com/igorpawelec/qgis-geoadaptels-geopalette/actions/workflows/tests.yml/badge.svg)](https://github.com/igorpawelec/qgis-geoadaptels-geopalette/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/igorpawelec/qgis-geoadaptels-geopalette)](https://github.com/igorpawelec/qgis-geoadaptels-geopalette/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

**Adaptive superpixels, seeded region growing and colour-space conversion for orthophotos, as Processing algorithms in QGIS.**

<img src="https://raw.githubusercontent.com/igorpawelec/qgis-geoadaptels-geopalette/main/www/toolbox.png" alt="The Processing toolbox with the GeoAdaptels + GeoPalette provider expanded: Convert colour space under Colour; Adaptels, Enforce connectivity, Grow seeds and SICLE superpixels under Segmentation; Vectorize labels under Vector" align="right" width="330"/>

A QGIS **Processing provider** that exposes the user-facing functions of [pygeoadaptels](https://github.com/igorpawelec/pygeoadaptels) and [pygeopalette](https://github.com/igorpawelec/pygeopalette) as six algorithms: pick one in the toolbox, drop in layers, fill the parameters, run. The results come back as layers, styled so they can be read at once. No Python is written, and the same algorithms are available in batch mode and in the graphical modeller.

**The plugin is glue.** The algorithms stay in the Python packages; this plugin turns a QGIS layer into a file path, calls the package's file-level function, and hands the output back to Processing. No segmentation or colour logic lives here, so it stays in step with the packages and with their R twins — [rgeoadaptels](https://github.com/igorpawelec/rgeoadaptels) is checked bit-identical to pygeoadaptels, so what QGIS draws is what R computes.

## The worked example: standing dead trees

An operator has digitised the standing dead trees of a plot as points and wants their crowns. Two algorithms do it. **Convert colour space** turns the RGB orthophoto into CIELAB, which is what makes the next step's tolerance meaningful — in CIELAB a distance of 1 is roughly one just-noticeable difference, so a `max_cost` reads as a ΔE. **Grow seeds** then grows every point into the region that looks like the pixel it sits on, within that tolerance, and everything unseeded stays unassigned: the operator supplies the objects, the algorithm supplies their boundaries.

<img src="https://raw.githubusercontent.com/igorpawelec/qgis-geoadaptels-geopalette/main/www/grow_seeds.png" alt="The Grow seeds dialog filled with the CIELAB raster, the dead-tree point layer, max_cost 15, band_weights 0.5,2.5,1 and max_radius 20, beside the crowns it grows on a 30 by 30 m window of the plot, drawn as orange outlines over the orthophoto" width="100%"/>

*The Grow seeds dialog with the dead-tree recipe — `max_cost` 15, `band_weights` 0.5,2.5,1, `max_radius` 20, `fill_holes` on — and its result on a 30 × 30 m window of the test plot (`test_data/`, a spruce stand at 0.25 m with 36 digitised dead trees). This is the same run as in the pygeoadaptels README: all 36 points grow, the crowns cover 4.9 % of the plot, and they stop at the living neighbours. Made by `www/figures.py` inside QGIS 4.2.*

The weights are the part that matters, and the reason is measurable: dead crowns sit at `a* ≈ +4`, healthy canopy at `a* ≈ -1`, and the gap is no larger than the brightness variation *inside* a single crown. Weighting `a*` up and `L*` down separates them — on this orthophoto it filled more (3544 → 6174 px) *and* spilled onto healthy trees less (19 % → 5 %) at the same time. `max_radius` is not optional: without it, past ΔE ≈ 25 one seed floods the scene. Full guidance is in [`docs/grow_seeds_guide.md`](https://github.com/igorpawelec/pygeoadaptels/blob/main/docs/grow_seeds_guide.md) in the package repository.

## Adaptels, and the rest

When no points exist and the whole scene has to be cut into segments, **Adaptels** does it with one parameter, a threshold in the units of the bands: regions grow until their internal distance passes it, so they come out small on textured crowns and large in homogeneous shadow, and the count follows the scene rather than a setting.

<img src="https://raw.githubusercontent.com/igorpawelec/qgis-geoadaptels-geopalette/main/www/adaptels.png" alt="The Adaptels dialog with the orthophoto and threshold 60, beside the resulting label raster on the same 30 m window, every adaptel in a distinct colour" width="100%"/>

*The Adaptels dialog at the default threshold of 60 and its label raster on the same window, drawn the way the plugin styles it on load: a palette whose hues step by the golden angle, so consecutively numbered neighbours contrast instead of blending. 2,792 adaptels on the plot, 403 in this window — the same numbers as in the pygeoadaptels README, because it is the same function.*

| Algorithm | Group | Wraps |
|---|---|---|
| Grow seeds (inverse OBIA) | Segmentation | `grow_seeds_from_files` |
| Adaptels | Segmentation | `create_adaptels` |
| SICLE superpixels | Segmentation | `create_sicle` |
| Enforce connectivity | Segmentation | `enforce_connectivity` (+ raster I/O) |
| Vectorize labels | Vector | `vectorize_from_file` |
| Convert colour space | Colour | `convert_raster` (15 spaces) |

**SICLE** is the fixed-count alternative to adaptels, with an optional saliency map; **Enforce connectivity** splits the adaptels that competition left in more than one piece, for zonal statistics; **Vectorize labels** turns any label raster into polygons. Results are styled on load: label rasters get the golden-angle palette, crown polygons are drawn outline-only so the imagery stays visible underneath.

## Install

1. Download `geoadaptels_palette-<version>.zip` from [Releases](https://github.com/igorpawelec/qgis-geoadaptels-geopalette/releases).
2. QGIS → **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Restart QGIS. The provider appears in the Processing toolbox as **GeoAdaptels + GeoPalette**.

`pygeoadaptels` and `pygeopalette` are **bundled inside the zip** — they are pure Python, so no download and no `git` is needed for them. Three compiled dependencies are not bundled and cannot be: `numba`, `rasterio` and `fiona`. The first algorithm run installs them into QGIS's own Python; if that fails on a locked-down machine, the Processing log prints the exact command to run by hand.

The plugin runs on QGIS 3.40 and 3.44 (Qt 5) and on QGIS 4 (Qt 6); the figures above were made in 4.2.2. Upgrading from a version before 0.4.0? **Uninstall the old plugin first** — it had a different internal id (`geopalette_adaptels`), so QGIS treats this as a separate plugin and you would end up with two sets of algorithms in the toolbox.

## When to use it, and when not

Use the plugin when the work happens in QGIS: an operator digitising and growing dead trees, a segmentation feeding a manual interpretation or zonal statistics, a colour conversion before either. The packages themselves are the better choice for anything scripted or batch-scale — the same functions, without the layer round-trip — and for the R side of the family.

It does not delineate crowns from a canopy height model; that is [pycacumen](https://github.com/igorpawelec/pycacumen) / [rcacumen](https://github.com/igorpawelec/rcacumen), which work on height rather than colour. Standing dead trees *without* digitised points — detection rather than delineation — is [pygeosnag](https://github.com/igorpawelec/pygeosnag) and its plugin [qgis-geosnag](https://github.com/igorpawelec/qgis-geosnag), which run on adaptels underneath.

### The package family

| Step | Python | R |
|---|---|---|
| Colour-space conversion of orthophotos | [pygeopalette](https://github.com/igorpawelec/pygeopalette) | [rgeopalette](https://github.com/igorpawelec/rgeopalette) |
| Adaptive superpixels and seeded growing on orthophotos | [pygeoadaptels](https://github.com/igorpawelec/pygeoadaptels) | [rgeoadaptels](https://github.com/igorpawelec/rgeoadaptels) |
| Crowns from a canopy height model | [pycacumen](https://github.com/igorpawelec/pycacumen) | [rcacumen](https://github.com/igorpawelec/rcacumen) |
| Standing dead trees on orthophotos | [pygeosnag](https://github.com/igorpawelec/pygeosnag) | — |
| The same, inside QGIS | **qgis-geoadaptels-geopalette**, [qgis-geosnag](https://github.com/igorpawelec/qgis-geosnag) | |
| Polish national geodata (GUGiK, BDL) | — | [rgeopl](https://github.com/igorpawelec/rgeopl) |

## Reference

<details>
<summary><b>Build from source</b></summary>

The build copies the two pure-Python packages into `geoadaptels_palette/vendor/` at build time, so it expects their checkouts **beside this repository**:

```
parent/
├── qgis-geoadaptels-geopalette/   <- this repo
├── pygeoadaptels/
└── pygeopalette/
```

```bash
python build_zip.py        # -> dist/geoadaptels_palette-<version>.zip
```

`vendor/` and `dist/` are build artefacts and are not committed — the vendored copy is regenerated on every build so it can never quietly drift from the packages it was cut from. A tag `v*` builds the zip on GitHub and attaches it to the release.

</details>

<details>
<summary><b>What is tested, and what is not</b></summary>

- **`geoadaptels_palette/core.py`** — the layer that actually calls the packages — is verified against the real test data by `test_package_calls.py`, which runs outside QGIS and also under QGIS's own Python:

  ```bash
  PYTHONPATH="../pygeoadaptels;../pygeopalette;." python test_package_calls.py
  ```

  It confirms every wrapped call, including two corrections to the original spec (`read_raster` returns five values and a flat band; the colour conversion writes into a directory), and reproduces the dead-tree grow_seeds anchor: ~6195 px assigned.

- **The QGIS layer without a QGIS** — every module imports and every algorithm builds its dialog against a stub `qgis` module in CI (`tests/test_stub_import.py`), the code is linted, and the zip is built and checked for the two vendored packages.

- **The QGIS layer in QGIS** — imports, the dependency bootstrap and the dialogs have been run in QGIS 3.40, 3.44 and 4.2 on Windows. All six algorithms execute and load their results; the figures above are that run, scripted.

- **Not verified:** a first-run dependency bootstrap on a genuinely clean machine (the development machine already had the packages), and anything on Linux or macOS.

**In-QGIS checklist.** The provider appears with six algorithms; Grow seeds with the recipe above assigns ≈6195 px, the end-to-end correctness anchor; a point layer with a selection or a different CRS still lands on the right pixels (the package reprojects; watch the log); each other algorithm runs and writes a layer QGIS can load; Convert colour space lists the 15 spaces from `available_spaces()`; batch mode and the graphical modeller both see the algorithms.

</details>

<details>
<summary><b>The figures</b></summary>

`python www/figures.py` remakes them: it starts QGIS offscreen with `www/_qgis_capture.py`, which grabs the toolbox and the dialogs, runs Grow seeds and Adaptels through Processing on `test_data/`, renders the results the way QGIS draws them, and exits; the composition is then done with matplotlib. QGIS is found through the `QGIS_BAT` environment variable (default: the 4.2.2 install path); the plugin has to be installed in the QGIS profile.

</details>

## Citing

If the segmentation contributes to a publication, please cite the method paper and the software:

> Pawelec, I., Hawryło, P., Netzel, P., & Socha, J. (2026). Evaluating superpixel algorithms for standing dead tree delineation using aerial orthoimagery. *International Journal of Applied Earth Observation and Geoinformation*, 147, 105180. [doi:10.1016/j.jag.2026.105180](https://doi.org/10.1016/j.jag.2026.105180)

This plugin and each package carry a `CITATION.cff` with machine-readable metadata, including the algorithm papers behind them — Achanta et al. 2018 for adaptels, Belém et al. 2023 for SICLE. The adaptels algorithm originates in a C implementation by **Paweł Netzel** at the University of Agriculture in Kraków; `pygeoadaptels` is a reimplementation of that work.

## Licence

GPLv3, matching the wrapped packages — which in turn inherit it from the projects they derive from.
