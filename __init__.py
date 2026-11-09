# -*- coding: utf-8 -*-
def classFactory(iface):
    from .adjacent_polygon_checker import AdjacentPolygonAttributeChecker
    return AdjacentPolygonAttributeChecker(iface)
