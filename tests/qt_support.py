"""Real Qt widgets with import-only QGIS stand-ins, not a QGIS integration test."""
import os
import sys
import types
from enum import IntEnum

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    import PyQt6.QtCore
    import PyQt6.QtGui
    import PyQt6.QtWidgets
except ImportError:
    AVAILABLE = False
else:
    AVAILABLE = True
    qgis = types.ModuleType('qgis')
    qgis.__path__ = []
    core = types.ModuleType('qgis.core')
    gui = types.ModuleType('qgis.gui')
    for name in ('QgsFeature', 'QgsField', 'QgsGeometry', 'QgsPointXY', 'QgsProject',
                 'QgsApplication', 'QgsSettings', 'QgsVectorLayer',
                 'QgsCoordinateReferenceSystem', 'QgsDistanceArea'):
        setattr(core, name, type(name, (), {}))
    core.QgsProject.instance = staticmethod(lambda: object())
    class DistanceUnit(IntEnum):
        Meters = 0
        Degrees = 1
    core.Qgis = types.SimpleNamespace(DistanceUnit=DistanceUnit)
    gui.QgsProjectionSelectionWidget = type('QgsProjectionSelectionWidget', (), {})
    sys.modules.update({'qgis': qgis, 'qgis.core': core, 'qgis.gui': gui,
                        'qgis.PyQt': PyQt6,
                        'qgis.PyQt.QtCore': PyQt6.QtCore,
                        'qgis.PyQt.QtGui': PyQt6.QtGui,
                        'qgis.PyQt.QtWidgets': PyQt6.QtWidgets})
    APP = PyQt6.QtWidgets.QApplication.instance() or PyQt6.QtWidgets.QApplication([])
