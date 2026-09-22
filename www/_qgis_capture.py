"""Run inside QGIS by www/figures.py: grab the toolbox and the dialogs, run
two algorithms through Processing, render their results like QGIS would.

    qgis.bat --nologo --noversioncheck --code www/_qgis_capture.py

with GAP_ROOT set to this repository's root (``--code`` scripts have no
``__file__``) and QT_QPA_PLATFORM=offscreen, so nothing is shown on a screen.
Writes into www/_capture/: toolbox.png, dialog_<algorithm>.png, the outputs
of grow_seeds and adaptels, and map_grow_seeds.png / map_adaptels.png.
Everything is logged to www/_capture/capture.log; QGIS quits when done.
"""
import os
import time
import traceback

ROOT = os.environ["GAP_ROOT"]
OUT = os.path.join(ROOT, "www", "_capture")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "capture.log"), "a", buffering=1, encoding="utf-8")


def log(m):
    LOG.write(f"[{time.strftime('%H:%M:%S')}] {m}\n")


from qgis.PyQt.QtCore import QSize, QTimer  # noqa: E402
from qgis.PyQt.QtGui import QColor, QImage, QPainter  # noqa: E402
from qgis.PyQt.QtWidgets import QApplication, QDockWidget, QLineEdit  # noqa: E402
from qgis.core import (QgsFillSymbol, QgsMapRendererCustomPainterJob, QgsMapSettings,  # noqa: E402
                       QgsMarkerSymbol, QgsProcessingContext, QgsProject, QgsRasterLayer, QgsVectorLayer)
from qgis.utils import iface  # noqa: E402

RGB = os.path.join(ROOT, "test_data", "SNP_21_2020_1.tif")
LAB = os.path.join(ROOT, "test_data", "SNP_21_2020_1_lab.tif")
PTS = os.path.join(ROOT, "test_data", "dead_trees_test.shp")
ORANGE, INK = "235,104,52", "31,31,31"


def settle(seconds=1.0):
    t0 = time.time()
    while time.time() - t0 < seconds:
        QApplication.processEvents()
        time.sleep(0.02)


def grab_toolbox():
    dock = iface.mainWindow().findChild(QDockWidget, "ProcessingToolbox")
    if dock is None:
        log("toolbox dock not found")
        return
    dock.show()
    dock.raise_()
    box = dock.findChild(QLineEdit)
    if box is not None:
        box.setText("GeoAdaptels")
    settle(1.5)
    dock.widget().resize(360, 420)
    settle(0.5)
    dock.widget().grab().save(os.path.join(OUT, "toolbox.png"))
    log("toolbox grabbed")


def grab_dialog(alg_id, params, name):
    from processing.tools.general import createAlgorithmDialog
    dlg = createAlgorithmDialog(alg_id, params)
    dlg.show()
    settle(0.5)
    dlg.setMinimumSize(820, 720)          # after show(): the dialog restores its remembered geometry on showing,
    dlg.resize(820, 720)                  # and a plain resize is discarded; the minimum size cannot be
    settle(2.5)
    dlg.grab().save(os.path.join(OUT, f"dialog_{name}.png"))
    dlg.close()
    settle(0.3)
    log(f"dialog {name} grabbed")


def render(layers, extent, path, size=900):
    ms = QgsMapSettings()
    ms.setLayers(layers)
    ms.setBackgroundColor(QColor(255, 255, 255))
    ms.setOutputSize(QSize(size, size))
    ms.setExtent(extent)
    ms.setDestinationCrs(layers[-1].crs())
    fmt = getattr(QImage, 'Format', QImage)                      # Qt6 scopes the enum, Qt5 does not
    img = QImage(QSize(size, size), fmt.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    job = QgsMapRendererCustomPainterJob(ms, p)
    job.start()
    job.waitForFinished()
    p.end()
    img.save(path)
    log(f"rendered {os.path.basename(path)}")


def stretch(layer, lo=2.0, hi=98.0):
    """Cumulative-cut contrast stretch on every band, what an operator does to a dark orthophoto."""
    from qgis.core import QgsContrastEnhancement, QgsRasterMinMaxOrigin
    ce = getattr(QgsContrastEnhancement, 'ContrastEnhancementAlgorithm', QgsContrastEnhancement)
    lim = getattr(QgsRasterMinMaxOrigin, 'Limits', QgsRasterMinMaxOrigin)
    r = layer.renderer()
    mmo = r.minMaxOrigin()
    mmo.setLimits(lim.CumulativeCut)
    mmo.setCumulativeCutLower(lo / 100)
    mmo.setCumulativeCutUpper(hi / 100)
    r.setMinMaxOrigin(mmo)
    layer.setContrastEnhancement(ce.StretchToMinimumMaximum, lim.CumulativeCut)
    layer.triggerRepaint()


def outline_layer(path, name, width="0.45"):
    v = QgsVectorLayer(path, name, "ogr")
    v.renderer().setSymbol(QgsFillSymbol.createSimple({"color": "0,0,0,0", "outline_color": ORANGE,
                                                       "outline_width": width, "outline_style": "solid"}))
    return v


def main():
    try:
        import processing
        rgb = QgsRasterLayer(RGB, "SNP_21_2020_1")
        pts = QgsVectorLayer(PTS, "dead trees", "ogr")
        pts.renderer().setSymbol(QgsMarkerSymbol.createSimple({"name": "circle", "color": INK, "outline_color": "255,255,255",
                                                               "outline_width": "0.35", "size": "2.2"}))
        stretch(rgb)
        QgsProject.instance().addMapLayers([rgb, pts])
        iface.mapCanvas().setExtent(rgb.extent())
        log(f"layers loaded, rgb valid={rgb.isValid()} pts={pts.featureCount()}")

        grab_toolbox()
        grab_dialog("geoadaptels:grow_seeds", {"INPUT": LAB, "POINTS": pts.id(), "MAX_COST": 15.0,
                                               "BAND_WEIGHTS": "0.5,2.5,1", "MAX_RADIUS": 20}, "grow_seeds")
        grab_dialog("geoadaptels:adaptels", {"INPUT": rgb.id(), "THRESHOLD": 60.0}, "adaptels")
        grab_dialog("geoadaptels:convert_colourspace", {"INPUT": rgb.id()}, "convert_colourspace")

        ctx = QgsProcessingContext()
        ctx.setProject(QgsProject.instance())
        g = processing.run("geoadaptels:grow_seeds",
                           {"INPUT": LAB, "POINTS": PTS, "MAX_COST": 15.0, "BAND_WEIGHTS": "0.5,2.5,1",
                            "COMPACTNESS": 0.0, "SEED_WINDOW": 1, "MAX_RADIUS": 20, "FILL_HOLES": True,
                            "OUTPUT": os.path.join(OUT, "grow_labels.tif"),
                            "POLYGONS": os.path.join(OUT, "grow_crowns.gpkg")}, context=ctx)
        log(f"grow_seeds -> {g}")
        a = processing.run("geoadaptels:adaptels",
                           {"INPUT": RGB, "THRESHOLD": 60.0, "DISTANCE": 0, "MINKOWSKI_P": 2.0, "QUEEN": False,
                            "NORMALIZE": False, "OUTPUT": os.path.join(OUT, "adaptels.tif")}, context=ctx)
        log(f"adaptels -> {a}")
        c = processing.run("geoadaptels:convert_colourspace",
                           {"INPUT": RGB, "SPACE": 8, "RED": 1, "GREEN": 2, "BLUE": 3,
                            "OUTPUT": os.path.join(OUT, "lab_from_plugin.tif")}, context=ctx)   # exercises band_ranges in the worker
        log(f"convert_colourspace -> {c}")

        crowns = outline_layer(g["POLYGONS"], "crowns", width="0.6")
        render([pts, crowns, rgb], rgb.extent(), os.path.join(OUT, "map_grow_seeds.png"))

        labels = QgsRasterLayer(a["OUTPUT"], "adaptels")
        from geoadaptels_palette.styling import LabelRasterPostProcessor
        n_labels = int(labels.dataProvider().bandStatistics(1).maximumValue) + 1
        LabelRasterPostProcessor(n_labels).postProcessLayer(labels, ctx)  # the palette the plugin applies on load
        render([labels], rgb.extent(), os.path.join(OUT, "map_adaptels.png"))
        from qgis.core import QgsRectangle
        res = rgb.rasterUnitsPerPixelX(); e = rgb.extent()
        r0, c0, n = 120, 90, 120                                 # the same 30 m window as the package READMEs
        win = QgsRectangle(e.xMinimum() + c0 * res, e.yMaximum() - (r0 + n) * res, e.xMinimum() + (c0 + n) * res, e.yMaximum() - r0 * res)
        render([labels], win, os.path.join(OUT, "map_adaptels_window.png"))
        render([pts, crowns, rgb], win, os.path.join(OUT, "map_grow_seeds_window.png"))
        log("DONE")
    except Exception:  # noqa: BLE001
        log(traceback.format_exc())
    QTimer.singleShot(500, quit_qgis)


def quit_qgis():
    """Neither QgsApplication.quit() nor the exit action ends an offscreen QGIS 4 (the exit action
    asks about the unsaved project and blocks); everything is on disk, so leave hard."""
    try:
        QgsProject.instance().setDirty(False)
        LOG.close()
    finally:
        os._exit(0)


QTimer.singleShot(6000, main)                     # let the profile's plugins finish loading first
