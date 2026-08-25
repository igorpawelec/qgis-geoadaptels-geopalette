"""pygeopalette + Adaptels -- a QGIS Processing provider.

Wraps the pygeoadaptels and pygeopalette Python packages; the algorithms live in
those packages, this plugin is glue. Copyright (C) 2026 Igor Pawelec. GPLv3.
"""


def classFactory(iface):
    from .plugin import Plugin
    return Plugin(iface)
