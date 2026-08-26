"""QGIS plugin entry point."""


def classFactory(iface):
    from .plugin import OcrCoordinatesPlugin

    return OcrCoordinatesPlugin(iface)
