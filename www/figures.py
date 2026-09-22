"""The README figures: real QGIS screenshots and renders, remade in one go.

    python www/figures.py                 # capture in QGIS, then compose
    python www/figures.py --compose-only  # reuse www/_capture/ from the last capture

Step 1 starts QGIS offscreen (nothing appears on the screen) with
www/_qgis_capture.py, which grabs the Processing toolbox and three algorithm
dialogs, runs Grow seeds and Adaptels through Processing on test_data/, and
renders their results the way QGIS draws them. QGIS is found through the
QGIS_BAT environment variable, or the default install below. Step 2 composes:
  www/toolbox.png      the provider in the Processing toolbox;
  www/grow_seeds.png   the Grow seeds dialog and its result on a 30 m window;
  www/adaptels.png     the Adaptels dialog and the label raster as the plugin
                       styles it on load, on the same window.
Needs matplotlib and Pillow; the QGIS side needs the plugin installed in the
QGIS profile with its dependencies (the first run installs them).
"""
import os
import subprocess
import sys
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CAP = os.path.join(HERE, "_capture")
QGIS_BAT = os.environ.get("QGIS_BAT", r"C:\Program Files\QGIS 4.2.2\bin\qgis.bat")
INK = "#1f1f1f"


def capture(timeout=420):
    """Run the in-QGIS capture and wait for its DONE line."""
    os.makedirs(CAP, exist_ok=True)
    for name in os.listdir(CAP):
        if name.endswith((".png", ".tif", ".gpkg", ".log")):
            os.remove(os.path.join(CAP, name))
    script = os.path.join(HERE, "_qgis_capture.py")
    run_cmd = os.path.join(CAP, "run.cmd")
    with open(run_cmd, "w", encoding="ascii") as fh:
        fh.write("@echo off\n"
                 f"set GAP_ROOT={ROOT}\n"
                 "set QT_QPA_PLATFORM=offscreen\n"
                 "set PYTHONIOENCODING=utf-8\n"
                 f"cd /d {ROOT}\n"
                 f'call "{QGIS_BAT}" --nologo --noversioncheck --code "{script}"\n')
    log = os.path.join(CAP, "capture.log")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with open(os.path.join(CAP, "stdout.log"), "w") as out:
        subprocess.Popen(["cmd", "/c", run_cmd], stdout=out, stderr=subprocess.STDOUT, creationflags=flags)
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(5)
        if os.path.exists(log):
            text = open(log, encoding="utf-8", errors="replace").read()
            if "DONE" in text or "Traceback" in text:
                break
    else:
        raise SystemExit(f"capture did not finish within {timeout} s; see {log}")
    text = open(log, encoding="utf-8", errors="replace").read()
    if "Traceback" in text:
        raise SystemExit("the capture failed inside QGIS:\n" + text)
    time.sleep(4)                                            # QGIS exits on its own right after DONE
    print(text.strip())


def trim(img, bg=None, pad=8):
    """Cut uniform margins (the toolbox grab has empty space below the tree)."""
    a = np.asarray(img.convert("RGB")).astype(int)
    if bg is None:
        bg = np.median(a[-24:-4].reshape(-1, 3), axis=0)     # the panel background, sampled above the frame line
    diff = np.abs(a - bg).sum(axis=2) > 60                   # text and icons, not the panel's own shading
    diff[-4:] = False                                        # the frame: its bottom line and its side lines
    diff[:, :4] = False
    diff[:, -4:] = False
    rows = np.where(diff.any(axis=1))[0]
    cols = np.where(diff.any(axis=0))[0]
    r1, c1 = min(rows.max() + pad, a.shape[0]), min(cols.max() + pad, a.shape[1])
    return img.crop((0, 0, c1, r1))


def panel(ax, img, label):
    ax.imshow(img)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor("#d9d9d9")
    ax.set_xlabel(label, fontsize=9.5, color=INK, labelpad=7)


def compose():
    tb = trim(Image.open(os.path.join(CAP, "toolbox.png")))
    fig, ax = plt.subplots(figsize=(4.6, 4.6 * tb.height / tb.width + 0.4))
    panel(ax, tb, "the provider in the Processing toolbox, six algorithms")
    fig.savefig(os.path.join(HERE, "toolbox.png"), dpi=160, bbox_inches="tight", facecolor="white")

    for name, dialog, result, labels in (
        ("grow_seeds", "dialog_grow_seeds.png", "map_grow_seeds_window.png",
         ("Grow seeds (inverse OBIA): a CIELAB raster, the point layer\nand the dead-tree recipe",
          "the crowns it grows\non a 30 m window of the plot")),
        ("adaptels", "dialog_adaptels.png", "map_adaptels_window.png",
         ("Adaptels: one raster, one threshold",
          "the label raster as the plugin styles it on load,\nthe same window")),
    ):
        d = Image.open(os.path.join(CAP, dialog))
        m = Image.open(os.path.join(CAP, result))
        h = 5.8
        fig, axes = plt.subplots(1, 2, figsize=(h * d.width / d.height + h + 0.3, h + 0.5),
                                 gridspec_kw={"width_ratios": [d.width / d.height, 1]})
        panel(axes[0], d, labels[0])
        panel(axes[1], m, labels[1])
        fig.subplots_adjust(wspace=0.04)
        fig.savefig(os.path.join(HERE, f"{name}.png"), dpi=160, bbox_inches="tight", facecolor="white")
    print("written: www/toolbox.png, www/grow_seeds.png, www/adaptels.png")


if __name__ == "__main__":
    if "--compose-only" not in sys.argv:
        capture()
    compose()
