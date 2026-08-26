"""QGIS plugin lifecycle."""

from pathlib import Path

from qgis.PyQt.QtGui import QAction, QIcon
from qgis.core import QgsApplication

from .dialog import OcrCoordinatesDialog
from .i18n import translate


class OcrCoordinatesPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None
        self.locale = QgsApplication.locale()

    def tr(self, key, **values):
        return translate(key, self.locale, **values)

    def initGui(self):
        icon = QIcon(str(Path(__file__).with_name("icon.svg")))
        self.action = QAction(icon, self.tr("plugin_name"), self.iface.mainWindow())
        self.action.setToolTip(self.tr("tooltip"))
        self.action.triggered.connect(self.run)
        self.iface.addPluginToVectorMenu(self.tr("menu_name"), self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginVectorMenu(self.tr("menu_name"), self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None

    def run(self):
        if self.dialog is None:
            self.dialog = OcrCoordinatesDialog(self.iface, self.locale, self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
