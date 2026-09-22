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
vendored, and are deps.py's job -- installed into ``libs/`` next to
``vendor/``, private to this plugin (see deps.py for why not the user site).

Copyright (C) 2026 Igor Pawelec. Licence: GPLv3.
"""
import importlib
import importlib.util
import os
import sys

VENDOR_DIR = os.path.join(os.path.dirname(__file__), "vendor")
# The binary dependencies deps.py installs, private to this plugin (never the
# user site, which every Python of the same minor version on the machine reads).
LIBS_DIR = os.path.join(os.path.dirname(__file__), "libs")

# Pure-Python packages that can ride along. Anything with a compiled extension
# must NOT be listed here -- it would have to match the interpreter's version
# and platform, which is the whole reason those go through pip instead.
VENDORED = ("pygeoadaptels", "pygeopalette")


def _spec(name):
    try:
        return importlib.util.find_spec(name)
    except (ImportError, ValueError):
        return None


def purge_stale():
    """Forget vendored modules already imported from a previous plugin zip.

    Installing a new zip replaces the files under vendor/, but the modules
    imported from the old files stay in sys.modules for the rest of the QGIS
    session, so the operator keeps running last week's package code with
    this week's plugin. Called once on plugin load; only modules whose file
    lies under the vendor directory are dropped, an installed copy is left
    alone. Returns the number of modules dropped.
    """
    root = os.path.abspath(VENDOR_DIR)
    dropped = 0
    for name in list(sys.modules):
        top = name.split(".")[0]
        if top not in VENDORED:
            continue
        mod = sys.modules.get(name)
        origin = getattr(mod, "__file__", None) or ""
        if origin and os.path.abspath(origin).startswith(root):
            del sys.modules[name]
            dropped += 1
    if dropped:
        importlib.invalidate_caches()
    return dropped


def activate(feedback=None):
    """Put libs/ and, if the packages are not installed, the vendored copies on sys.path.

    Returns a dict of ``name -> "installed" | "vendored" | "missing"``. Safe to
    call repeatedly; never raises.
    """
    # The plugin-private binary dependencies. Appended, so anything QGIS's own
    # Python already provides keeps winning.
    if os.path.isdir(LIBS_DIR) and LIBS_DIR not in sys.path:
        sys.path.append(LIBS_DIR)
        importlib.invalidate_caches()

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
