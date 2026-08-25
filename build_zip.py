"""Build the installable QGIS plugin zip.

A QGIS plugin zip has the plugin folder at its top level, so this zips
``geoadaptels_palette/`` (excluding bytecode). Install the result via QGIS ->
Plugins -> Manage and Install Plugins -> Install from ZIP.

    python build_zip.py            # -> dist/geoadaptels_palette-<version>.zip
"""
import os
import re
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = "geoadaptels_palette"
SKIP_DIRS = {"__pycache__"}
SKIP_EXT = {".pyc", ".pyo"}

# Pure-Python packages copied into vendor/ at build time, so the plugin needs
# neither git nor a download for them. Only .py is copied -- no bytecode, which
# would be tied to one Python version and defeat the point.
VENDOR_SRC = {
    "pygeoadaptels": os.path.join(HERE, "..", "pygeoadaptels", "pygeoadaptels"),
    "pygeopalette": os.path.join(HERE, "..", "pygeopalette", "pygeopalette"),
}


def _version():
    meta = os.path.join(HERE, PLUGIN, "metadata.txt")
    with open(meta, encoding="utf-8") as fh:
        m = re.search(r"(?m)^version=(.+)$", fh.read())
    return m.group(1).strip() if m else "0.0.0"


def _pkg_version(pkg_dir):
    """Read __version__ out of the package's __init__.py without importing it."""
    init = os.path.join(pkg_dir, "__init__.py")
    try:
        with open(init, encoding="utf-8") as fh:
            m = re.findall(r'__version__\s*=\s*"([^"]+)"', fh.read())
        return m[-1] if m else "unknown"
    except OSError:
        return "unknown"


def vendor():
    """Refresh vendor/ from the sibling package checkouts.

    Done at build time rather than kept in the tree, so the bundled copy can
    never quietly drift from the packages it was cut from. The versions are
    written alongside, and the plugin logs which copy it loaded.
    """
    dest_root = os.path.join(HERE, PLUGIN, "vendor")
    if os.path.isdir(dest_root):
        shutil.rmtree(dest_root)
    os.makedirs(dest_root)

    versions = {}
    for name, src in VENDOR_SRC.items():
        src = os.path.abspath(src)
        if not os.path.isdir(src):
            raise SystemExit(
                f"Cannot vendor {name}: {src} not found. The build expects the "
                f"package checkouts beside this repository.")
        dest = os.path.join(dest_root, name)
        shutil.copytree(
            src, dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
        versions[name] = _pkg_version(src)

    with open(os.path.join(dest_root, "VERSIONS.txt"), "w",
              encoding="utf-8") as fh:
        for k, v in sorted(versions.items()):
            fh.write(f"{k}={v}\n")
    print("  vendored: " + ", ".join(f"{k} {v}" for k, v in sorted(versions.items())))
    return versions


def main():
    version = _version()
    vendor()
    dist = os.path.join(HERE, "dist")
    os.makedirs(dist, exist_ok=True)
    out = os.path.join(dist, f"{PLUGIN}-{version}.zip")
    root = os.path.join(HERE, PLUGIN)

    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if os.path.splitext(name)[1] in SKIP_EXT:
                    continue
                full = os.path.join(dirpath, name)
                arc = os.path.relpath(full, HERE)      # keep PLUGIN/ prefix
                zf.write(full, arc)
                n += 1

    size = os.path.getsize(out)
    print(f"Wrote {out}")
    print(f"  {n} files, {size / 1024:.1f} KiB, plugin version {version}")
    print("Install: QGIS -> Plugins -> Manage and Install -> Install from ZIP")


if __name__ == "__main__":
    main()
