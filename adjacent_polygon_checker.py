
# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .adjacent_polygon_checker_dialog import AdjacentPolygonCheckerDialog


class AdjacentPolygonAttributeChecker:

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        # Load plugin icon from the main plugin directory
        icon_path = os.path.join(
            os.path.dirname(__file__),
            "icon.png"
        )

        plugin_icon = QIcon(icon_path)

        # Create plugin action with icon
        self.action = QAction(
            plugin_icon,
            "Adjacent Polygon Attribute Checker",
            self.iface.mainWindow()
        )

        self.action.setToolTip(
            "Adjacent Polygon Attribute Checker"
        )

        self.action.triggered.connect(self.run)

        # Add action to QGIS menu and toolbar
        self.iface.addPluginToMenu(
            "&Adjacent Polygon Attribute Checker",
            self.action
        )

        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu(
                "&Adjacent Polygon Attribute Checker",
                self.action
            )

            self.iface.removeToolBarIcon(self.action)

            self.action = None

    def run(self):
        if self.dialog is None:
            self.dialog = AdjacentPolygonCheckerDialog(self.iface)

        self.dialog.refresh_project_layers()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
