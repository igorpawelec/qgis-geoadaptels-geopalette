"""Make the two pure-Python packages importable without installing anything.

``pygeoadaptels`` and ``pygeopalette`` are pure Python -- no compiled extensions
-- so a copy of them can simply ride along inside the plugin and be imported
from there. No pip, no network, no git, no admin rights. That removes the
single most common reason the plugin fails on someone else's machine: ``git``
is not on the PATH of QGIS's Python, so ``pip install git+https://...`` dies
before it starts.

Because they are pure Python and the sources are checked to stay 3.9-clean
(both packages carry a ``test_python39_compat.py`` for exactly this), the same
vendored copy works on **every** Python from 3.9 to 3.13 and on Windows, Linux
and macOS alike. There is nothing platform-specific to get wrong.

**An installed copy always wins.** The vendored one is a fallback, never an
override: someone who has pip-installed a newer pygeoadaptels keeps using it,
and the plugin does not silently shadow it with whatever it shipped with. The
log line says which one was loaded, so there is no guessing.

What this does *not* solve: the packages still need ``numba`` (pygeoadaptels)
and ``rasterio``/``fiona`` (file I/O). Those carry binaries, cannot be
vendored, and remain deps.py's job.

Copyright (C) 2026 Igor Pawelec. Licence: GPLv3.
"""
import importlib
import importlib.util
import os
import sys

VENDOR_DIR = os.path.join(os.path.dirname(__file__), "vendor")

# Pure-Python packages that can ride along. Anything with a compiled extension
# must NOT be listed here -- it would have to match the interpreter's version
# and platform, which is the whole reason those go through pip instead.
VENDORED = ("pygeoadaptels", "pygeopalette")


def _spec(name):
    try:
        return importlib.util.find_spec(name)
    except (ImportError, ValueError):
        return None


def activate(feedback=None):
    """Put the vendored copies on sys.path if the packages are not installed.

    Returns a dict of ``name -> "installed" | "vendored" | "missing"``. Safe to
    call repeatedly; never raises.
    """
    status = {}
    need_vendor = False
    for name in VENDORED:
        if _spec(name) is not None:
            status[name] = "installed"
        else:
            need_vendor = True

    if need_vendor and os.path.isdir(VENDOR_DIR):
        # Appended, not prepended: an installed package still wins if one
        # appears later in the session.
        if VENDOR_DIR not in sys.path:
            sys.path.append(VENDOR_DIR)
        importlib.invalidate_caches()

    for name in VENDORED:
        if name in status:
            continue
        spec = _spec(name)
        if spec is None:
            status[name] = "missing"
        else:
            origin = getattr(spec, "origin", "") or ""
            status[name] = ("vendored"
                            if os.path.abspath(VENDOR_DIR) in
                            os.path.abspath(origin) else "installed")

    if feedback is not None:
        parts = [f"{k} ({v})" for k, v in sorted(status.items())]
        feedback.pushInfo("Packages: " + ", ".join(parts))
    return status


def vendored_versions():
    """Versions of the bundled copies, read from the file the build wrote."""
    path = os.path.join(VENDOR_DIR, "VERSIONS.txt")
    out = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    out[k] = v
    except OSError:
        pass
    return out
