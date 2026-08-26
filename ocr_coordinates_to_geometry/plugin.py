"""QGIS plugin lifecycle."""

from qgis.PyQt.QtGui import QAction
from qgis.PyQt.QtWidgets import QStyle

from .dialog import OcrCoordinatesDialog


class OcrCoordinatesPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        icon = self.iface.mainWindow().style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        self.action = QAction(icon, "OCR координат → геометрия", self.iface.mainWindow())
        self.action.setToolTip("Построить точки, линию и полигон из скриншота таблицы координат")
        self.action.triggered.connect(self.run)
        self.iface.addPluginToVectorMenu("OCR координат", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginVectorMenu("OCR координат", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None

    def run(self):
        if self.dialog is None:
            self.dialog = OcrCoordinatesDialog(self.iface, self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
