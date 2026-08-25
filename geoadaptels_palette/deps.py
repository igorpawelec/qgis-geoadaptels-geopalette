"""Dependency bootstrap -- the single highest-risk piece of this plugin.

QGIS ships its own Python, and things have to be importable *from that
interpreter*. Since 0.3.0 the two pure-Python packages ride along inside the
plugin (see ``vendor_loader``), so this module only ever has to fetch the
three that carry compiled binaries: ``numba``, ``rasterio`` and ``fiona``.
That removes the dependency on ``git`` being present, which was the most
common way a clean machine failed.

Four things bite, all learned the hard way against QGIS 3.40/3.44 (Python
3.12) on Windows:

1. **``sys.executable`` is a launcher, not the interpreter.** On Windows QGIS
   it is ``bin/python3.exe``, which does not initialise as a subprocess ("No
   module named 'encodings'") and makes pip exit 1 with no useful output. The
   real interpreter sits at ``sys.prefix`` (``apps/PythonXY`` on Windows,
   ``prefix/bin`` on Linux). ``_qgis_python()`` resolves that.

2. **rasterio/fiona >= the numpy-2 line drag in numpy 2.5, which breaks numba
   and scipy** (they need numpy < 2.3). QGIS ships numpy 1.26, so the installs
   are pinned below the numpy-2 boundary (``rasterio<1.4``, ``fiona<1.10``) to
   keep the existing numpy.

3. **pip's real error was swallowed.** Output is captured and reported now, so
   a failure shows why rather than "returned non-zero exit status 1".

4. **PEP 668.** Debian, Ubuntu and Fedora mark the system interpreter
   "externally managed" and refuse ``--user`` outright. A failure carrying
   that phrase is retried with ``--break-system-packages``, which is what
   those distributions document for the case.

Policy: auto-install on first use, with the exact manual command in the log if
it fails (locked-down machines). Prototype the bare ``import pygeoadaptels``
bootstrap in a live QGIS before trusting the algorithms (spec section 2).

Copyright (C) 2026 Igor Pawelec. Licence: GPLv3.
"""
import importlib
import importlib.util
import os
import subprocess
import sys

# Everything an algorithm needs to be importable. pygeoadaptels and pygeopalette
# are pure Python and ride along in vendor/ (see vendor_loader), so they are
# checked here but never handed to pip.
REQUIRED = ["pygeoadaptels", "pygeopalette", "numba", "rasterio", "fiona"]

# Only the packages that carry compiled binaries, which cannot be vendored.
#
# **numba is listed explicitly.** It used to arrive as a dependency of
# pygeoadaptels when that was pip-installed; now that pygeoadaptels is
# vendored, pip is never told about it and would not install it otherwise.
BINARY_DEPS = ["numba", "rasterio", "fiona"]


def _install_specs():
    """Pin rasterio/fiona to match the numpy the interpreter already has.

    Current rasterio/fiona pull in numpy 2.5, which breaks numba (needs < 2.5)
    and scipy (< 2.3). QGIS ships numpy 1.26 through 3.44, so on those the
    pins are required -- installing without them uninstalls the working numpy
    and leaves numba dead. On an interpreter that is already on numpy 2 (some
    Linux distributions) the pins would be wrong, hence the check rather than
    a hardcoded list.
    """
    try:
        import numpy
        numpy_major = int(numpy.__version__.split(".")[0])
    except Exception:
        numpy_major = 1
    if numpy_major < 2:
        return ["numba", "rasterio<1.4", "fiona<1.10"]
    return ["numba", "rasterio", "fiona"]


INSTALL_SPECS = _install_specs()


def _qgis_python():
    """The real QGIS interpreter, not the ``bin/`` launcher.

    Inside QGIS ``sys.prefix`` is the interpreter home. The launcher at
    ``sys.executable`` fails to run as a subprocess on Windows, so it is only
    the last resort.
    """
    names = ("python.exe", "python3.exe", "python3", "python")
    for base in (sys.prefix, os.path.join(sys.prefix, "bin")):
        for name in names:
            p = os.path.join(base, name)
            if os.path.exists(p):
                return p
    return sys.executable


def missing_packages():
    return [m for m in REQUIRED if importlib.util.find_spec(m) is None]


def _pip(py, specs, extra=()):
    cmd = [py, "-m", "pip", "install", "--user", *extra, *specs]
    return subprocess.run(cmd, capture_output=True, text=True)


def ensure_dependencies(feedback=None, auto_install=True):
    """Return ``(ok, missing)``. Never raises; never hard-crashes the plugin.

    Order matters: the vendored pure-Python packages are put on the path
    *first*, so pip is only ever asked for the binary dependencies. On a clean
    machine that is the difference between "needs git and a working toolchain"
    and "needs three wheels from PyPI".
    """
    from . import vendor_loader
    vendor_loader.activate(feedback)

    missing = missing_packages()
    if not missing:
        return True, []
    if not auto_install:
        return False, missing

    # Only the binary ones are pip's business; if a vendored package is
    # missing the vendor directory is broken and pip cannot help.
    to_install = [m for m in missing if m in BINARY_DEPS]
    if not to_install:
        if feedback is not None:
            feedback.reportError(
                "These are bundled with the plugin but did not import: "
                + ", ".join(missing)
                + ". The plugin's vendor/ folder looks incomplete -- "
                  "reinstall the plugin zip.")
        return False, missing

    py = _qgis_python()
    specs = _install_specs()
    if feedback is not None:
        feedback.pushInfo(f"Installing {', '.join(to_install)} using {py}")
    try:
        r = _pip(py, specs)
        # PEP 668: Debian/Ubuntu/Fedora mark the system interpreter
        # "externally managed" and refuse --user outright. The override is
        # exactly what those distributions document for this case.
        if r.returncode != 0 and "externally-managed-environment" in (
                (r.stderr or "") + (r.stdout or "")):
            if feedback is not None:
                feedback.pushInfo(
                    "Interpreter is externally managed; retrying with "
                    "--break-system-packages.")
            r = _pip(py, specs, extra=("--break-system-packages",))
    except Exception as e:  # pragma: no cover - environment dependent
        if feedback is not None:
            feedback.reportError(f"Could not launch pip: {e}\n{manual_hint()}")
        return False, missing

    if r.returncode != 0:
        if feedback is not None:
            tail = (r.stdout or "")[-2000:] + "\n" + (r.stderr or "")[-2000:]
            feedback.reportError(
                "pip failed:\n" + tail.strip()
                + "\n\nInstall by hand into QGIS's Python and restart QGIS:\n  "
                + manual_hint())
        return False, missing

    importlib.invalidate_caches()
    still = missing_packages()
    if still and feedback is not None:
        feedback.reportError(
            "pip reported success but these are still not importable: "
            + ", ".join(still) + ".\nRestart QGIS, then try again.")
    return (not still), still


def manual_hint():
    """The exact one-line install command, for the log.

    Only the binary dependencies -- the two pure-Python packages ship inside
    the plugin, so an operator never has to fetch them.
    """
    py = _qgis_python()
    return f'"{py}" -m pip install --user ' + " ".join(_install_specs())
