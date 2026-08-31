"""Style the layers Processing loads back into the project.

Without this every result arrives as a grey ramp -- which is close to useless
for a *label* raster, where the values are region ids and neighbouring ids
carry no ordering. The operator would restyle by hand after every single run.
Here segmentation output gets a random palette (so adjacent regions contrast),
crown polygons get an outline-only style (so the orthophoto stays visible
underneath), and colour-space output gets a contrast stretch.

**Every entry point is wrapped so a styling failure can never fail the run.**
Styling is cosmetic; the algorithm already produced a correct file by the time
these are called, and losing a colour ramp is not a reason to lose the result.
Failures are reported to the log and the layer keeps QGIS's default style.

QGIS also needs the post-processor object to stay alive after
``postProcessAlgorithm`` returns, so instances are parked in ``_KEEP_ALIVE``;
letting them be garbage-collected is a known way to get a silent no-op.

Copyright (C) 2026 Igor Pawelec. Licence: GPLv3.
"""
from qgis.core import (
    QgsFillSymbol,
    QgsPalettedRasterRenderer,
    QgsProcessingLayerPostProcessorInterface,
)

# Above this many distinct labels a paletted renderer means an unusable legend
# and a slow unique-value scan, so those fall back to QGIS's default.
MAX_PALETTE_CLASSES = 20000

# Above this many pixels, do not even ask for the label count.
#
# `bandStatistics` with the default arguments is a full unsampled pass over
# every band statistic, and post-processors run on the GUI thread inside the
# task-completion handler. On a full orthophoto -- 130 M pixels, ~2.4 M adaptels
# at threshold 60 -- that pass blocks the main thread long enough for Qt to
# re-enter the event loop while the finished task is being torn down, which is
# a use-after-free, i.e. an access violation rather than a catchable error.
#
# The scan was only ever there to discover that the raster has far too many
# labels to paint a palette from. A raster this size always does, so the size
# alone answers the question in O(1) and the expensive call never happens.
MAX_PALETTE_PIXELS = 25_000_000

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


class LabelRasterPostProcessor(QgsProcessingLayerPostProcessorInterface):
    """Random palette for a label raster; nodata stays transparent.

    The packages declare nodata in the GeoTIFF (-1 for grow_seeds, -9999
    elsewhere), so QGIS already renders it transparent -- nothing to do here
    beyond the colours.
    """

    def postProcessLayer(self, layer, context, feedback=None):
        if not _usable(layer):
            return
        try:
            provider = layer.dataProvider()
            # Cheap gate first -- see MAX_PALETTE_PIXELS. Nothing below this
            # line may touch the pixels of a large raster.
            px = int(provider.xSize()) * int(provider.ySize())
            if px > MAX_PALETTE_PIXELS:
                if feedback is not None:
                    feedback.pushInfo(
                        f"{px} pixels is past {MAX_PALETTE_PIXELS}; leaving "
                        f"the default renderer rather than scanning the band.")
                return
            stats = provider.bandStatistics(1)
            n = int(stats.maximumValue) - int(stats.minimumValue) + 1
            if n > MAX_PALETTE_CLASSES:
                if feedback is not None:
                    feedback.pushInfo(
                        f"{n} distinct labels is past {MAX_PALETTE_CLASSES}; "
                        f"leaving the default renderer.")
                return
            classes = QgsPalettedRasterRenderer.classDataFromRaster(
                provider, 1)
            if not classes:
                return
            _assign_colours(classes)
            layer.setRenderer(
                QgsPalettedRasterRenderer(provider, 1, classes))
            layer.triggerRepaint()
        except Exception as e:  # cosmetic only -- never fail the run
            if feedback is not None:
                feedback.pushInfo(f"Could not style the label raster: {e}")


def _assign_colours(classes):
    """Give every class its own colour, here in Python rather than via a ramp.

    ``classDataFromRaster`` called without a colour ramp does *not* colour the
    classes -- it leaves each one the default-constructed QColor, which is
    black. 0.2.1 did exactly that and produced a legend of ~600 entries that
    were all black: the renderer was applied correctly and the raster still
    drew as a black rectangle. Assigning here rather than passing a ramp keeps
    the result independent of how any given QGIS treats a null ramp.

    Hues step by the golden angle, so **consecutively numbered labels land far
    apart on the colour wheel**. That matters for a segmentation specifically:
    neighbouring regions tend to carry neighbouring ids, and a plain sequential
    ramp would give them near-identical colours -- exactly where contrast is
    needed. Saturation and value wobble on separate cycles so that labels a
    full turn apart still differ.
    """
    from qgis.PyQt.QtGui import QColor
    for i, klass in enumerate(classes):
        hue = (i * 137.507764) % 360.0
        sat = 155 + (i * 37) % 85
        val = 175 + (i * 53) % 75
        klass.color = QColor.fromHsv(int(hue), int(sat), int(val))


class PolygonPostProcessor(QgsProcessingLayerPostProcessorInterface):
    """Outline-only polygons, so the imagery underneath stays readable.

    A filled polygon layer hides exactly the thing the operator is checking the
    result against.
    """

    def __init__(self, outline="255,0,0,255", width="0.4"):
        super().__init__()
        self._outline = outline
        self._width = width

    def postProcessLayer(self, layer, context, feedback=None):
        if not _usable(layer):
            return
        try:
            symbol = QgsFillSymbol.createSimple({
                "color": "0,0,0,0",
                "outline_color": self._outline,
                "outline_width": self._width,
                "outline_style": "solid",
            })
            layer.renderer().setSymbol(symbol)
            layer.triggerRepaint()
        except Exception as e:
            if feedback is not None:
                feedback.pushInfo(f"Could not style the polygons: {e}")


class StretchedRasterPostProcessor(QgsProcessingLayerPostProcessorInterface):
    """Contrast-stretch a continuous raster (the colour-space output).

    Colour-space bands sit on wildly different scales -- L* is 0-100, a*/b*
    are unbounded and signed -- so the default 0-255 assumption renders them
    nearly black. Stretching to the actual min/max makes the result legible.
    """

    def postProcessLayer(self, layer, context, feedback=None):
        if not _usable(layer):
            return
        try:
            layer.setContrastEnhancement(
                _stretch_enum(), _cumulative_cut_enum())
            layer.triggerRepaint()
        except Exception as e:
            if feedback is not None:
                feedback.pushInfo(f"Could not stretch the raster: {e}")


def _stretch_enum():
    """StretchToMinimumMaximum, wherever this QGIS keeps it."""
    from qgis.core import QgsContrastEnhancement
    return QgsContrastEnhancement.StretchToMinimumMaximum


def _cumulative_cut_enum():
    """CumulativeCut limits -- 2-98 %, which ignores outliers."""
    from qgis.core import QgsRasterMinMaxOrigin
    return QgsRasterMinMaxOrigin.CumulativeCut


def _register(context, dest_id, processor):
    """Attach `processor` to the layer already resolved as `dest_id`.

    **`dest_id` must be the destination the algorithm already computed** --
    never re-resolve it here. ``parameterAsOutputLayer`` is not idempotent for
    ``TEMPORARY_OUTPUT``: every call mints a fresh temp path *and* registers it
    to be loaded on completion. Calling it a second time to attach styling
    therefore created a phantom output that nothing ever wrote, so QGIS
    reported "layers were not correctly generated" while the real result sat
    beside it unstyled. Fixed in 0.2.1; the file destination case hid it,
    because there the second call returns the same path.

    Returns True when a post-processor was attached. Does nothing when the
    output was not requested, or is not being loaded into the project.
    """
    try:
        if not dest_id:
            return False
        # `layerToLoadOnCompletionDetails` is `mLayersToLoadOnCompletion[id]`
        # on the C++ side, and QMap::operator[] *inserts* a default entry when
        # the key is absent. Calling it for an id QGIS was never going to load
        # therefore invents a layer-to-load that points at nothing, and the
        # post-processor attached to it is later handed a dangling layer --
        # an access violation inside on_complete, not a catchable exception.
        # So ask first, and only then reach for the details.
        if hasattr(context, "willLoadLayerOnCompletion"):
            if not context.willLoadLayerOnCompletion(dest_id):
                return False
        details = context.layerToLoadOnCompletionDetails(dest_id)
        if details is None:
            return False
        _KEEP_ALIVE.append(processor)
        details.setPostProcessor(processor)
        return True
    except Exception:
        # Not loading on completion, or an API shape this QGIS does not have.
        return False


def style_label_raster(context, dest_id):
    return _register(context, dest_id, LabelRasterPostProcessor())


def style_polygons(context, dest_id, outline="255,0,0,255"):
    return _register(context, dest_id, PolygonPostProcessor(outline=outline))


def style_stretched_raster(context, dest_id):
    return _register(context, dest_id, StretchedRasterPostProcessor())
