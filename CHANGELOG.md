# Changelog

## 0.3.1
- Added an option to include or exclude polygons with no qualifying same-attribute adjacent polygon.
- Isolated polygons are exported as single-feature groups when the option is enabled and marked `ISOLATED` in individual output.

## 0.3.0
- Made attribute matching optional; no selected fields means spatial-only analysis.
- Added per-field unique-value inclusion filters.
- Added canonical multi-field matching using the combination of selected field values.
- Replaced unsupported `QgsGeometry.boundary()` calls with polygon-ring extraction and boundary intersection.
- Separated filtered feature counts from invalid geometry counts and geometry operation errors.
- Preserved project/external SHP/GDB input and individual/dissolved Shapefile outputs.

## 0.2.0
- Added plugin menu and toolbar entry.
- Added QGIS project polygon layer selection.
- Added external Shapefile and File Geodatabase browsing.
- Added multi-field attribute selection and normalization options.
- Added shared-boundary threshold and connected grouping.
- Added individual and dissolved Shapefile exports.
- Added processing log and completion/error messages.
