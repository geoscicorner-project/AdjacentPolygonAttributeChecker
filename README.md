# Adjacent Polygon Attribute Checker

QGIS plugin for finding connected groups of adjacent polygons that share a positive-length boundary.

## Version 0.3.1

This development build introduces optional attribute matching, multi-field canonical matching, per-field value filters, a QGIS 3.44-compatible shared-boundary calculation, and an option to include isolated polygons.

## Installation for testing

1. Extract the ZIP file.
2. Copy the folder `AdjacentPolygonAttributeChecker` into the active QGIS profile's `python/plugins` directory.
3. Restart QGIS, or enable the plugin under **Plugins → Manage and Install Plugins → Installed**.
4. Open **Plugins → Adjacent Polygon Attribute Checker**.

## Workflow

1. Choose a polygon layer from the QGIS project, or choose an external SHP/GDB dataset.
2. Optionally select one or more attribute fields. If no fields are selected, the analysis is spatial-only.
3. For any selected field, use **Configure values for selected field...** to choose which unique values are included. Values not checked are excluded from analysis.
4. If multiple fields are selected, all selected field values are combined into one canonical matching key. Every selected field must match.
5. Set case and whitespace normalization.
6. Set minimum shared boundary length in input CRS map units. Zero accepts any positive shared boundary.
7. Optionally enable **Include polygons with no matching adjacent polygon** to retain isolated eligible polygons as single-feature groups.
8. Choose an output folder and filename prefix.
9. Select individual and/or dissolved output and run the analysis.

## Spatial analysis

- Candidate polygon pairs are found with a spatial index.
- Polygon ring boundaries are extracted and intersected to calculate shared-boundary length.
- Point-only contacts are ignored because they have zero shared-boundary length.
- Connected components are built using Union-Find.
- By default, polygons without a qualifying same-attribute neighbor are excluded. The optional checkbox can include them as single-feature groups.
- Invalid geometries are skipped and reported. Geometry operation errors are counted separately.
- The input layer is not modified.

## Outputs

- `<prefix>_individual.shp`: original polygons remain separate; adds `GROUP_ID`, `SRC_FID`, `NEIGH_CNT`, `STATUS`.
- `<prefix>_dissolved.shp`: one dissolved geometry per connected group; adds `GROUP_ID`, `MEMBER_CNT`.

## Notes

- The shared-boundary threshold uses the input CRS map units. Use a projected CRS when setting a threshold in metres.
- If a field has an explicitly configured empty value selection, no features pass that field's value filter.
- GDB sublayer enumeration depends on the installed GDAL/OGR provider. If enumeration fails, add the GDB layer in QGIS Browser and choose the project-layer option.
- Processing runs synchronously in this development build. Large datasets may temporarily make QGIS unresponsive. Test with representative subsets before production use.
- Shapefile field-name and data-type limitations apply.

## License

GPL-2.0-or-later.
