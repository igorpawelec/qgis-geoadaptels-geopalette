"""Style the layers Processing loads back into the project.

Without this every result arrives as a grey ramp -- which is close to useless
for a *label* raster, where the values are region ids and neighbouring ids
carry no ordering. The operator would restyle by hand after every single run.
Here segmentation output gets a palette whose hues step by the golden angle
(so adjacent regions contrast), crown polygons get an outline-only style (so
the orthophoto stays visible underneath), and colour-space output gets a
contrast stretch.

**Every entry point is wrapped so a styling failure can never fail the run.**
Styling is cosmetic; the algorithm already produced a correct file by the time
these are called, and losing a colour ramp is not a reason to lose the result.
Failures are reported to the log and the layer keeps QGIS's default style.

**Nothing here reads a raster.** Post-processors run on the GUI thread inside
the task-completion handler, and 0.2.1 to 0.5.4 read the result there -- a
cumulative-cut stretch for the colour-space output, a statistics pass and a
unique-value scan for the label rasters. On a large raster that pass blocked
the main thread long enough for Qt to re-enter the event loop while the
finished task was being torn down: an access violation in ``on_complete``,
not a catchable error. Everything a renderer needs is now computed in the
worker, where the algorithm already knows it -- the label count, the band
ranges -- and handed to the post-processor as plain numbers. Found and fixed
the same way in the GeoSnag plugin.

Two QGIS traps besides that one: ``LayerDetails.setPostProcessor`` takes
ownership of the processor (``sip.ispyowned`` goes False), so it is kept alive
here only on bindings that do not; and ``layerToLoadOnCompletionDetails``
inserts a default entry for an unknown id, so ``willLoadLayerOnCompletion`` is
asked first. Copyright (C) 2026 Igor Pawelec. Licence: GPLv3.
"""
from qgis.core import (
    QgsFillSymbol,
    QgsPalettedRasterRenderer,
    QgsProcessingLayerPostProcessorInterface,
)

# Above this many labels a paletted renderer means an unusable legend and a
# very long class list, so those keep QGIS's default renderer.
MAX_PALETTE_CLASSES = 20000

# Only for a QGIS whose bindings do not take ownership; emptied on each run.
_KEEP_ALIVE = []


def _usable(layer):
    """Whether this layer is safe to touch.

    A post-processor can be handed a layer that never materialised. SIP raises
    RuntimeError for an object it knows has been deleted, so that case is
    catchable; the bare ``None`` case is not caught by anything downstream and
    has to be tested before the first attribute access.
    """
    try:
        return layer is not None and layer.isValid()
    except Exception:
        return False


def _label_colour(i):
    """Hues step by the golden angle, so **consecutively numbered labels land
    far apart on the colour wheel**. That matters for a segmentation
    specifically: neighbouring regions tend to carry neighbouring ids, and a
    plain sequential ramp would give them near-identical colours -- exactly
    where contrast is needed. Saturation and value wobble on separate cycles
    so that labels a full turn apart still differ."""
    from qgis.PyQt.QtGui import QColor
    hue = (i * 137.507764) % 360.0
    sat = 155 + (i * 37) % 85
    val = 175 + (i * 53) % 75
    return QColor.fromHsv(int(hue), int(sat), int(val))


class LabelRasterPostProcessor(QgsProcessingLayerPostProcessorInterface):
    """Golden-angle palette for a label raster whose ids run 0..n-1.

    The count comes from the algorithm -- every package function returns it,
    and for grow_seeds it is the number of points -- so the classes are built
    from an integer and the raster is never read here. Nodata (-1 for
    grow_seeds, -9999 elsewhere) is declared in the GeoTIFF, so QGIS already
    renders it transparent.
    """

    def __init__(self, n_labels):
        super().__init__()
        self.n_labels = n_labels

    def postProcessLayer(self, layer, context, feedback=None):
        if not _usable(layer) or not self.n_labels:
            return
        try:
            n = int(self.n_labels)
            if n > MAX_PALETTE_CLASSES:
                if feedback is not None:
                    feedback.pushInfo(f"{n} labels is past {MAX_PALETTE_CLASSES}; leaving the default renderer.")
                return
            classes = [QgsPalettedRasterRenderer.Class(i, _label_colour(i), str(i)) for i in range(n)]
            layer.setRenderer(QgsPalettedRasterRenderer(layer.dataProvider(), 1, classes))
            layer.triggerRepaint()
        except Exception as e:  # cosmetic only -- never fail the run
            if feedback is not None:
                feedback.pushInfo(f"Could not style the label raster: {e}")


class PolygonPostProcessor(QgsProcessingLayerPostProcessorInterface):
    """Outline-only polygons, so the imagery underneath stays visible."""

    def __init__(self, outline="255,0,0,255", width="0.5"):
        super().__init__()
        self._outline = outline
        self._width = width

    def postProcessLayer(self, layer, context, feedback=None):
        if not _usable(layer):
            return
        try:
            symbol = QgsFillSymbol.createSimple({
                "color": "0,0,0,0", "outline_color": self._outline,
                "outline_width": self._width, "outline_style": "solid"})
            layer.renderer().setSymbol(symbol)
            layer.triggerRepaint()
        except Exception as e:
            if feedback is not None:
                feedback.pushInfo(f"Could not style the polygons: {e}")


class StretchedRasterPostProcessor(QgsProcessingLayerPostProcessorInterface):
    """Contrast-stretch a continuous raster (the colour-space output) to
    per-band ranges the algorithm measured in the worker.

    Colour-space bands sit on wildly different scales -- L* is 0-100, a*/b*
    are unbounded and signed -- so the default 0-255 assumption renders them
    nearly black. Three or more bands become an RGB composite of the first
    three, one band a grey ramp; each band stretched to its own range.
    """

    def __init__(self, ranges):
        super().__init__()
        self.ranges = [(float(lo), float(hi)) for lo, hi in ranges]

    def postProcessLayer(self, layer, context, feedback=None):
        if not _usable(layer) or not self.ranges:
            return
        try:
            from qgis.core import QgsContrastEnhancement, QgsMultiBandColorRenderer, QgsSingleBandGrayRenderer
            provider = layer.dataProvider()
            enum = getattr(QgsContrastEnhancement, "ContrastEnhancementAlgorithm", QgsContrastEnhancement)
            algorithm = enum.StretchToMinimumMaximum

            def enhancement(band):
                lo, hi = self.ranges[band - 1]
                ce = QgsContrastEnhancement(provider.dataType(band))
                ce.setMinimumValue(lo, False)
                ce.setMaximumValue(hi, False)
                ce.setContrastEnhancementAlgorithm(algorithm, True)
                return ce

            if len(self.ranges) >= 3 and provider.bandCount() >= 3:
                renderer = QgsMultiBandColorRenderer(provider, 1, 2, 3)
                renderer.setRedContrastEnhancement(enhancement(1))
                renderer.setGreenContrastEnhancement(enhancement(2))
                renderer.setBlueContrastEnhancement(enhancement(3))
            else:
                renderer = QgsSingleBandGrayRenderer(provider, 1)
                renderer.setContrastEnhancement(enhancement(1))
            layer.setRenderer(renderer)
            layer.triggerRepaint()
        except Exception as e:
            if feedback is not None:
                feedback.pushInfo(f"Could not stretch the raster: {e}")


def band_ranges(path, lo=2.0, hi=98.0, max_px=4_000_000):
    """The 2-98 % range of every band of a raster, for StretchedRasterPostProcessor.

    Runs in the worker, right after the algorithm wrote the file. Reads at most
    ``max_px`` pixels per band (rasterio decimates on read), ignores nodata and
    NaN, and returns ``[(lo, hi), ...]``; an unreadable band gets (0, 1).
    """
    import math
    import numpy as np
    import rasterio
    out = []
    with rasterio.open(path) as src:
        f = max(1.0, math.sqrt(src.width * src.height / max_px))
        shape = (max(1, int(src.height / f)), max(1, int(src.width / f)))
        for b in range(1, src.count + 1):
            try:
                a = src.read(b, out_shape=shape).astype("float64")
                nd = src.nodatavals[b - 1] if src.nodatavals else None
                if nd is not None and not (isinstance(nd, float) and math.isnan(nd)):
                    a[a == nd] = np.nan
                a = a[np.isfinite(a)]
                if a.size == 0:
                    raise ValueError("no valid pixels")
                p, q = np.percentile(a, [lo, hi])
                out.append((float(p), float(q) if q > p else float(p) + 1.0))
            except Exception:
                out.append((0.0, 1.0))
    return out


def _still_ours(processor):
    """True when Python, not C++, owns the processor after the hand-over."""
    try:
        from qgis.PyQt import sip
        return bool(sip.ispyowned(processor))
    except Exception:
        return True                              # cannot tell: keep it, as before


def _register(context, dest_id, processor):
    """Attach `processor` to the layer already resolved as `dest_id`.

    **`dest_id` must be the destination the algorithm already computed** --
    never re-resolve it here. ``parameterAsOutputLayer`` is not idempotent for
    ``TEMPORARY_OUTPUT``: every call mints a fresh temp path *and* registers it
    to be loaded on completion, so a second call created a phantom output that
    nothing ever wrote (fixed in 0.2.1).

    Returns True when a post-processor was attached. Does nothing when the
    output was not requested, or is not being loaded into the project.
    """
    try:
        if not dest_id:
            return False
        # `layerToLoadOnCompletionDetails` is `mLayersToLoadOnCompletion[id]`
        # on the C++ side, and QMap::operator[] *inserts* a default entry when
        # the key is absent -- a layer-to-load that points at nothing, whose
        # post-processor is later handed a dangling layer. So ask first.
        if hasattr(context, "willLoadLayerOnCompletion"):
            if not context.willLoadLayerOnCompletion(dest_id):
                return False
        details = context.layerToLoadOnCompletionDetails(dest_id)
        if details is None:
            return False
        del _KEEP_ALIVE[:]                       # last run's, if any
        details.setPostProcessor(processor)
        if _still_ours(processor):               # bindings without /Transfer/
            _KEEP_ALIVE.append(processor)
        return True
    except Exception:
        # Not loading on completion, or an API shape this QGIS does not have.
        return False


def style_label_raster(context, dest_id, n_labels):
    return _register(context, dest_id, LabelRasterPostProcessor(n_labels))


def style_polygons(context, dest_id, outline="255,0,0,255"):
    return _register(context, dest_id, PolygonPostProcessor(outline=outline))


def style_stretched_raster(context, dest_id, ranges):
    return _register(context, dest_id, StretchedRasterPostProcessor(ranges))
