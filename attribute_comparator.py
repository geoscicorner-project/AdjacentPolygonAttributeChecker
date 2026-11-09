from qgis.core import NULL

def _is_null(value):
    try:
        return value is None or value == NULL
    except Exception:
        return value is None

def normalize_value(value, ignore_case=True, trim_whitespace=True):
    if _is_null(value):
        return ("__QGIS_NULL__",)
    type_name = type(value).__name__
    if isinstance(value, str):
        if trim_whitespace:
            value = value.strip()
        if ignore_case:
            value = value.casefold()
    try:
        hash(value)
        normalized = value
    except TypeError:
        normalized = repr(value)
    return (type_name, normalized)

def attribute_key(feature, fields, ignore_case=True, trim_whitespace=True):
    return tuple(normalize_value(feature[name], ignore_case, trim_whitespace) for name in fields)
