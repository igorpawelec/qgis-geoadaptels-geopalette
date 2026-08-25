"""Shared helpers for the algorithm classes: the dependency gate, and the
parameter-flag helper that keeps the dialogs from overwhelming an operator."""
from qgis.core import QgsProcessingException

from ..deps import ensure_dependencies, manual_hint


def require_packages(feedback):
    ok, missing = ensure_dependencies(feedback)
    if not ok:
        raise QgsProcessingException(
            "This algorithm needs the Python packages: "
            + ", ".join(missing)
            + ".\nInstall them into QGIS's own Python and restart QGIS:\n  "
            + manual_hint())


def advanced(param):
    """Collapse a parameter under the dialog's 'Advanced' section.

    Grow Seeds alone has ten parameters; showing all of them at once buries
    the three that are actually tuned per scene. Nothing is hidden -- the
    section is one click away -- and the defaults are the values the guide
    recommends.

    Wrapped: if a future QGIS moves the flag enum, the parameter simply stays
    visible rather than the whole dialog failing to build.
    """
    try:
        from qgis.core import QgsProcessingParameterDefinition
        param.setFlags(
            param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
    except Exception:
        pass
    return param
