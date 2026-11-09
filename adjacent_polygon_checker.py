from qgis.PyQt.QtWidgets import QAction
from .adjacent_polygon_checker_dialog import AdjacentPolygonCheckerDialog

class AdjacentPolygonAttributeChecker:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QAction("Adjacent Polygon Attribute Checker", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&Adjacent Polygon Attribute Checker", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu("&Adjacent Polygon Attribute Checker", self.action)
            self.iface.removeToolBarIcon(self.action)

    def run(self):
        if self.dialog is None:
            self.dialog = AdjacentPolygonCheckerDialog(self.iface)
        self.dialog.refresh_project_layers()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
