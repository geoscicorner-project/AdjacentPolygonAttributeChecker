from collections import defaultdict
from dataclasses import dataclass, field
from qgis.core import QgsSpatialIndex, QgsWkbTypes, QgsGeometry
from .attribute_comparator import attribute_key, normalize_value
from .connected_components import DisjointSet


@dataclass
class AdjacencyOptions:
    field_names: list
    ignore_case: bool = True
    trim_whitespace: bool = True
    minimum_shared_boundary_length: float = 0.0
    allowed_values: dict = field(default_factory=dict)
    include_isolated_polygons: bool = False


@dataclass
class AdjacentGroup:
    group_id: str
    feature_ids: list
    neighbor_counts: dict
    @property
    def member_count(self):
        return len(self.feature_ids)


@dataclass
class AdjacencyResult:
    groups: list = field(default_factory=list)
    qualifying_pairs: list = field(default_factory=list)
    invalid_geometry_ids: list = field(default_factory=list)
    checked_feature_count: int = 0
    candidate_pair_count: int = 0
    geometry_error_count: int = 0
    filtered_feature_count: int = 0


def _boundary_geometry(geom):
    """Build polygon boundary lines using QGIS 3.44-compatible geometry accessors."""
    polygons = []
    if geom.isMultipart():
        polygons = geom.asMultiPolygon()
    else:
        polygon = geom.asPolygon()
        polygons = [polygon] if polygon else []
    lines = []
    for polygon in polygons:
        for ring in polygon:
            if len(ring) >= 2:
                lines.append(ring)
    if not lines:
        return QgsGeometry()
    return QgsGeometry.fromMultiPolylineXY(lines)


def _shared_boundary_length(a, b):
    ba = _boundary_geometry(a)
    bb = _boundary_geometry(b)
    if ba.isNull() or bb.isNull() or ba.isEmpty() or bb.isEmpty():
        return 0.0
    shared = ba.intersection(bb)
    if shared.isNull() or shared.isEmpty():
        return 0.0
    return float(shared.length())


def detect_adjacent_groups(layer, options, feedback=None):
    if layer is None or not layer.isValid():
        raise ValueError("Input layer is invalid.")
    if QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
        raise ValueError("Input layer must be polygon geometry.")
    available = {f.name() for f in layer.fields()}
    missing = [n for n in options.field_names if n not in available]
    if missing:
        raise ValueError("Unknown field(s): " + ", ".join(missing))
    if options.minimum_shared_boundary_length < 0:
        raise ValueError("Minimum shared boundary length cannot be negative.")

    result = AdjacencyResult()
    geoms, keys, invalid = {}, {}, set()
    index = QgsSpatialIndex()
    total = max(layer.featureCount(), 1)
    allowed = options.allowed_values or {}
    allowed_normalized = {
        name: set(normalize_value(value, options.ignore_case, options.trim_whitespace) for value in values)
        for name, values in allowed.items()
    }

    for i, feature in enumerate(layer.getFeatures()):
        if feedback and feedback.isCanceled():
            return result
        fid, geom = feature.id(), feature.geometry()
        try:
            # Filter attribute values before geometry processing.
            excluded = False
            for field_name in options.field_names:
                if field_name in allowed_normalized:
                    value_key = normalize_value(feature[field_name], options.ignore_case, options.trim_whitespace)
                    if value_key not in allowed_normalized[field_name]:
                        excluded = True
                        break
            if excluded:
                result.filtered_feature_count += 1
                continue
            if geom.isNull() or geom.isEmpty() or not geom.isGeosValid():
                invalid.add(fid)
                continue
            geoms[fid] = geom
            keys[fid] = attribute_key(feature, options.field_names,
                                      options.ignore_case, options.trim_whitespace) if options.field_names else ()
            index.addFeature(feature)
        except Exception:
            invalid.add(fid)
        if feedback and hasattr(feedback, "setProgress"):
            feedback.setProgress(20.0 * (i + 1) / total)

    result.checked_feature_count = len(geoms) + len(invalid)
    dsu = DisjointSet(geoms.keys())
    neighbors, pairs = defaultdict(int), []
    valid_ids = sorted(geoms)

    for i, a in enumerate(valid_ids):
        if feedback and feedback.isCanceled():
            return result
        for b in index.intersects(geoms[a].boundingBox()):
            if b <= a or b not in geoms or keys[a] != keys[b]:
                continue
            result.candidate_pair_count += 1
            try:
                length = _shared_boundary_length(geoms[a], geoms[b])
            except Exception:
                result.geometry_error_count += 1
                continue
            if length > options.minimum_shared_boundary_length:
                pairs.append((a, b, length))
                dsu.union(a, b)
                neighbors[a] += 1
                neighbors[b] += 1
        if feedback and hasattr(feedback, "setProgress"):
            feedback.setProgress(20.0 + 75.0 * (i + 1) / max(len(valid_ids), 1))

    # By default, export only polygons that have at least one qualifying
    # same-attribute neighbor. Optionally retain isolated eligible polygons
    # as one-feature groups when the user enables the corresponding checkbox.
    comps = [c for c in dsu.components() if len(c) > 1 and any(x in neighbors for x in c)]
    if options.include_isolated_polygons:
        comps.extend([[fid] for fid in valid_ids if neighbors.get(fid, 0) == 0])
    comps.sort(key=lambda c: min(c))
    for n, comp in enumerate(comps, 1):
        members = sorted(comp)
        result.groups.append(AdjacentGroup("G{:06d}".format(n), members,
                                  {x: neighbors[x] for x in members}))
    result.qualifying_pairs = pairs
    result.invalid_geometry_ids = sorted(invalid)
    if feedback and hasattr(feedback, "setProgress"):
        feedback.setProgress(100)
    return result
