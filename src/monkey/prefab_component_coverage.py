"""Whole-source component disposition and static-evidence coverage.

The denominator is always the complete frozen ``plan.components`` list. This
module never uses ``convertible`` to remove source components from coverage.
Native, retained, disabled and unsupported representations remain distinct;
retention or a disabled carrier cannot prove static presentation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from .io import diagnostic


SCHEMA = "monkey-prefab-component-coverage/1"
_VISUAL_TYPES = {
    "cc.Sprite", "cc.Label", "cc.RichText", "cc.LabelOutline", "sp.Skeleton",
    "cc.Graphics", "cc.ParticleSystem", "cc.TiledMap",
}
_UNSUPPORTED_CODES = (
    "UNSUPPORTED", "HANDOFF", "NOT_SUPPORTED", "SOURCE_COMPONENT_PROFILE",
)
_UNITY_NATIVE_TYPES={
    'cc.Sprite':'UnityEngine.UI.Image','cc.Label':'TMPro.TextMeshProUGUI',
    'cc.RichText':'TMPro.TextMeshProUGUI','cc.LabelOutline':'TMPro.TextMeshProUGUI',
    'cc.Button':'UnityEngine.UI.Button','cc.Toggle':'UnityEngine.UI.Toggle',
    'cc.ToggleContainer':'UnityEngine.UI.ToggleGroup','cc.Widget':'NativeRectConstraints',
    'cc.Layout':'UnityEngine.UI.LayoutGroup','cc.ScrollView':'UnityEngine.UI.ScrollRect',
    'cc.Mask':'UnityEngine.UI.RectMask2D','cc.ProgressBar':'UnityEngine.UI.Slider',
    'cc.BlockInputEvents':'NativeInputBlocker','sp.Skeleton':'Spine.Unity.SkeletonGraphic',
}


def _rows(readback: dict, key: str) -> list[dict]:
    value = readback.get(key)
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _nested_rows(readback: dict, key: str) -> list[dict]:
    rows = list(_rows(readback, key))
    for prefab in _rows(readback, "sourcePrefabs"):
        rows.extend(_rows(prefab, key))
    return rows


def _identity(row: dict) -> str | None:
    value = row.get("sourceId") or row.get("sourceComponentId")
    return value if isinstance(value, str) and value else None


def _native_id(row: dict) -> str | None:
    for key in ("componentUuid", "nativeComponentId", "nativeId", "persistedGuid", "localFileId"):
        value = row.get(key)
        if (isinstance(value,str)and value.strip()and value.strip()!='0'
                or type(value)is int and value!=0):
            return str(value)
    return None


def _native_type(row: dict) -> str | None:
    for key in ("nativeType", "type", "componentType"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _native_identity_verified(row: dict) -> bool:
    return (_native_id(row) is not None
            and row.get("sourceIdentityVerified", True) is True
            and row.get("persistent", True) is True)


def _source_diagnostics(plan: dict, readback: dict) -> tuple[list[dict], dict[str, list[dict]]]:
    all_rows = []
    by_source: dict[str, list[dict]] = defaultdict(list)
    for origin, key in (("source", "diagnostics"), ("source", "sourceDiagnostics"), ("native", "diagnostics"),
                        ("source-readback", "sourceDiagnostics")):
        owner = plan if origin == "source" else readback
        rows = owner.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            # Preserve original diagnostic payload, adding only its provenance.
            if isinstance(row, dict):
                value = dict(row)
                value.setdefault("coverageOrigin", origin)
            else:
                value = diagnostic("SOURCE_OR_NATIVE_DIAGNOSTIC_PASSTHROUGH", f"{origin}/diagnostics/{len(all_rows)}",
                                   str(row))
                value["rawDiagnostic"] = row
                value["coverageOrigin"] = origin
            all_rows.append(value)
            source_id = row.get("sourceId") if isinstance(row, dict) else None
            if isinstance(source_id, str) and source_id:
                by_source[source_id].append(value)
    return all_rows, by_source


def _static_field_rows(readback: dict) -> list[dict]:
    rows = _nested_rows(readback, "staticFieldBindings")
    flattened = []
    for row in rows:
        if isinstance(row.get("binding"), dict):
            binding = dict(row["binding"])
            binding.setdefault("sourceId", row.get("sourceComponentId"))
            flattened.append(binding)
        else:
            flattened.append(row)
    return flattened


def _valid_static_fields(component: dict, fields_by_id: dict[str, list[dict]]) -> tuple[bool, str]:
    spec = component.get("staticFieldBinding")
    if not isinstance(spec, dict):
        return True, "not_required"
    sid = component.get("sourceId")
    rows = fields_by_id.get(sid, [])
    if len(rows) != 1:
        return False, "missing_or_ambiguous_static_field_readback"
    row = rows[0]
    # Creator's real readback contract has both nativeIdentityVerified and
    # fieldsVerified. Unity callers normalize its independently read carrier
    # and field reference proof to these same explicit booleans.
    if row.get("nativeIdentityVerified") is not True or row.get("fieldsVerified") is not True:
        return False, "static_field_identity_or_fields_unverified"
    expected_fields = spec.get("fields")
    actual_fields = row.get("fields")
    if not isinstance(expected_fields, list) or not isinstance(actual_fields, list):
        return False, "static_field_rows_missing"
    expected_names = [field.get("sourceFieldName") or field.get("name") for field in expected_fields if isinstance(field, dict)]
    actual_names = [field.get("sourceFieldName") or field.get("name") for field in actual_fields if isinstance(field, dict)]
    if len(expected_names) != len(expected_fields) or len(actual_names) != len(actual_fields) or sorted(expected_names) != sorted(actual_names):
        return False, "static_field_denominator_differs"
    for field in actual_fields:
        is_array=field.get('storageType')=='UnityEngine.Object[]'or field.get('elementKind')in ('node_ref','component_ref','asset_ref')
        is_ref=field.get('storageType')=='UnityEngine.Object'or field.get('kind')in ('node_ref','component_ref','asset_ref')
        if (field.get('verified')is False or is_array and field.get('referencesVerified')is False
                or is_ref and not is_array and field.get('referenceVerified')is False):
            return False, "static_field_value_or_reference_unverified"
    return True, "verified"


def _valid_retention(row: dict) -> bool:
    return (row.get("sourceIdentityVerified") is True
            and (row.get("verified") is True or row.get("fieldsVerified") is True)
            and isinstance(row.get("representation"), str) and bool(row["representation"])
            and row.get("status") in ("verified", "retained", "disabled", "native", "retained_source_identity_verified", "saved_static_references_verified"))


def _is_source_visible(component: dict, node_map: dict[str, dict]) -> bool | None:
    if component.get("type") not in _VISUAL_TYPES:
        return False
    if component.get("enabled") is False:
        return False
    node_id = component.get("node")
    if not isinstance(node_id, str) or node_id not in node_map:
        return None
    current = node_id
    seen = set()
    while current is not None:
        if current in seen:
            return None
        seen.add(current)
        node = node_map.get(current)
        if not isinstance(node, dict):
            return None
        if node.get("active") is False:
            return False
        current = node.get("parent")
    return True


def assess(plan: dict, readback: dict, engine: str) -> dict:
    """Assess every planned source component against explicit native evidence.

    ``readback.components`` uses actual editor rows (Creator's existing
    ``sourceId/type/componentUuid`` shape is accepted). Unity can pass a
    normalized row using the same keys. Optional explicit rows are
    ``retainedComponents``, ``disabledComponents``, ``staticFieldBindings``
    and ``staticPresentationValidation.components``. No field is inferred from
    ``convertible`` alone.
    """
    if not isinstance(plan, dict) or not isinstance(readback, dict) or engine not in ("unity", "creator"):
        raise ValueError("PREFAB_COMPONENT_COVERAGE_INPUT_INVALID")
    source_rows = plan.get("components")
    if not isinstance(source_rows, list):
        source_rows = []
    source_diagnostics, diagnostics_by_source = _source_diagnostics(plan, readback)
    diagnostics = list(source_diagnostics)
    readback_available = any(key in readback for key in (
        "components", "sourceComponentCoverage", "sourcePrefabs", "retainedComponents",
        "disabledComponents", "staticFieldBindings", "staticPresentationValidation"))

    source_by_id: dict[str, list[dict]] = defaultdict(list)
    components = []
    for index, component in enumerate(source_rows):
        if not isinstance(component, dict):
            diagnostics.append(diagnostic("SOURCE_COMPONENT_ROW_INVALID", f"components/{index}", "Source component row is not an object"))
            components.append({"sourceIndex": index, "sourceId": None, "disposition": "missing",
                               "nativeStatus": "missing", "retentionStatus": "not_applicable",
                               "staticPresentationStatus": "not_applicable", "playerStatus": "not_run"})
            continue
        source_id = component.get("sourceId")
        if not isinstance(source_id, str) or not source_id:
            diagnostics.append(diagnostic("SOURCE_COMPONENT_ID_MISSING", f"components/{index}", "Source component has no stable sourceId"))
            components.append({"sourceIndex": index, "sourceId": source_id, "sourceType": component.get("type"),
                               "disposition": "missing", "nativeStatus": "missing", "retentionStatus": "not_applicable",
                               "staticPresentationStatus": "not_applicable", "playerStatus": "not_run"})
            continue
        source_by_id[source_id].append(component)

    native_rows = _rows(readback, "components")
    native_source_ids = {_identity(row) for row in native_rows if _identity(row)}
    for prefab in _rows(readback, "sourcePrefabs"):
        for row in _rows(prefab, "components"):
            sid = _identity(row)
            if sid and sid in native_source_ids:
                continue
            native_rows.append(row)
            if sid:
                native_source_ids.add(sid)
    for observation in _rows(readback, "sourceComponentCoverage"):
        sid = _identity(observation)
        if sid in native_source_ids:
            continue
        actual = observation.get("nativeComponentReadback")
        if isinstance(actual, dict):
            native_rows.append(actual)
            if _identity(actual): native_source_ids.add(_identity(actual))
        elif isinstance(actual, list):
            for row in actual:
                if not isinstance(row, dict):
                    continue
                row_id = _identity(row)
                if row_id and row_id in native_source_ids:
                    continue
                native_rows.append(row)
                if row_id: native_source_ids.add(row_id)
    native_by_id: dict[str, list[dict]] = defaultdict(list)
    for row in native_rows:
        sid = _identity(row)
        if sid:
            native_by_id[sid].append(row)
    retained_by_id: dict[str, list[dict]] = defaultdict(list)
    for row in _rows(readback, "retainedComponents"):
        sid = _identity(row)
        if sid:
            retained_by_id[sid].append(row)
    disabled_by_id: dict[str, list[dict]] = defaultdict(list)
    for row in _rows(readback, "disabledComponents"):
        sid = _identity(row)
        if sid:
            disabled_by_id[sid].append(row)
    for row in native_rows:
        sid = _identity(row)
        if not sid:
            continue
        if row.get("status") == "retained":
            retained_by_id[sid].append(row)
        elif row.get("status") == "disabled":
            disabled_by_id[sid].append(row)
    static_fields_by_id: dict[str, list[dict]] = defaultdict(list)
    seen_field_readbacks = set()
    for row in _static_field_rows(readback):
        sid = _identity(row)
        if sid:
            signature = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
            if (sid, signature) in seen_field_readbacks:
                continue
            seen_field_readbacks.add((sid, signature))
            static_fields_by_id[sid].append(row)

    duplicate_source_ids = {sid for sid, rows in source_by_id.items() if len(rows) != 1}
    for sid in sorted(duplicate_source_ids):
        diagnostics.append(diagnostic("SOURCE_COMPONENT_ID_DUPLICATE", sid,
                                      "Source component ID occurs more than once in the full plan denominator", sid))

    visible_rows = {}
    presentation = readback.get("staticPresentationValidation")
    presentation_incomplete = isinstance(presentation, dict) and presentation.get("status") in ("partial", "fail")
    if presentation_incomplete:
        diagnostics.append(diagnostic("STATIC_PRESENTATION_NATIVE_INCOMPLETE", "readback/staticPresentationValidation",
                                      "Native presentation inventory reports incomplete source static semantics"))
    if isinstance(presentation, dict) and isinstance(presentation.get("components"), list):
        for row in presentation["components"]:
            if isinstance(row, dict) and isinstance(row.get("sourceId"), str):
                visible_rows.setdefault(row["sourceId"], []).append(row)
    # A pinned static Spine continuation proves only disabled retained source
    # data. Its contract explicitly states non_rendering and cannot satisfy
    # visual/static presentation coverage.
    spine_fragment = plan.get("staticSpineContinuation")
    spine_ids = set()
    if isinstance(spine_fragment, dict):
        spine_ids = {row.get("sourceComponentId") for row in spine_fragment.get("components", [])
                     if isinstance(row, dict) and isinstance(row.get("sourceComponentId"), str)}

    retention_expected = set()
    retention_verified = set()
    presentation_expected = set()
    presentation_verified = set()
    node_map = {row.get("sourceId"): row for row in plan.get("nodes", [])
                if isinstance(row, dict) and isinstance(row.get("sourceId"), str)}
    spine_fragment = plan.get("staticSpineContinuation")
    if isinstance(spine_fragment, dict):
        retention_expected.update(row.get("sourceComponentId") for row in spine_fragment.get("components", [])
                                  if isinstance(row, dict) and isinstance(row.get("sourceComponentId"), str))
    for row in plan.get("staticComponentRetentions", []):
        if isinstance(row, dict):
            sid = row.get("sourceComponentId") or row.get("sourceId")
            if isinstance(sid, str) and sid:
                retention_expected.add(sid)
    for source_id, rows in source_by_id.items():
        if len(rows) != 1:
            components.append({"sourceId": source_id, "sourceType": None,
                               "disposition": "missing", "nativeStatus": "missing",
                               "retentionStatus": "not_applicable", "staticPresentationStatus": "not_run",
                               "sourceVisible": None, "sourceDiagnostics": diagnostics_by_source.get(source_id, []),
                               "playerStatus": "not_run"})
            continue
        component = rows[0]
        if not readback_available:
            components.append({"sourceId": source_id, "sourceType": component.get("type"),
                               "expectedNativeType": component.get("nativeType") or component.get("type"),
                               "disposition": "missing", "nativeStatus": "not_run",
                               "staticFieldStatus": "not_run", "retentionStatus": "not_run",
                               "staticPresentationStatus": "not_run", "sourceVisible": None,
                               "sourceDiagnostics": diagnostics_by_source.get(source_id, []),
                               "playerStatus": "not_run"})
            continue
        expected_type = component.get("nativeType") or component.get("type")
        if engine=='unity':expected_type=_UNITY_NATIVE_TYPES.get(expected_type,expected_type)
        candidates = native_by_id.get(source_id, [])
        valid_native = [row for row in candidates if _native_identity_verified(row) and
                        (_native_type(row) == expected_type or engine=='unity'and isinstance(row.get('nativeBaseTypes'),list)and expected_type in row['nativeBaseTypes'])
                        and row.get("status") not in ("retained", "disabled", "unsupported", "missing")]
        if len(candidates) == 1 and len(valid_native) == 1:
            disposition = "native"
            field_ok, field_status = _valid_static_fields(component, static_fields_by_id)
            native_status = "pass" if field_ok else "partial"
            if not field_ok:
                diagnostics.append(diagnostic("NATIVE_STATIC_FIELD_READBACK_INCOMPLETE", source_id,
                                              "Native component exists but its planned static fields lack exact verified readback: " + field_status,
                                              source_id))
        else:
            field_status = "not_applicable"
            native_status = "missing"
            if len(candidates) > 1:
                diagnostics.append(diagnostic("NATIVE_COMPONENT_READBACK_AMBIGUOUS", source_id,
                                              "Multiple native component rows share one sourceId", source_id))
            elif candidates:
                diagnostics.append(diagnostic("NATIVE_COMPONENT_IDENTITY_MISMATCH", source_id,
                                              "Native component type or persistent identity differs", source_id))
            disposition = "missing"
            explicit = candidates[0] if len(candidates) == 1 else None
            if isinstance(explicit, dict) and explicit.get("status") == "unsupported":
                disposition = "unsupported"
            elif isinstance(explicit, dict) and explicit.get("status") == "missing":
                disposition = "missing"
            retained = retained_by_id.get(source_id, [])
            retained_fields_ok,retained_fields_status=_valid_static_fields(component,static_fields_by_id)
            if len(retained) == 1 and _valid_retention(retained[0]) and retained_fields_ok:
                disposition = "retained"
                field_status=retained_fields_status
                native_status = "partial"
                retention_expected.add(source_id)
                retention_verified.add(source_id)
            elif len(retained) > 1:
                diagnostics.append(diagnostic("STATIC_RETENTION_READBACK_AMBIGUOUS", source_id,
                                              "Multiple retained representations share one source component ID", source_id))
            elif source_id in spine_ids and isinstance(readback.get("staticSpineContinuation"), dict):
                spine_result = readback["staticSpineContinuation"]
                if spine_result.get("status") == "verified" and spine_result.get("sourceComponentIds") and source_id in spine_result["sourceComponentIds"]:
                    disposition = "retained"
                    native_status = "partial"
                    retention_expected.add(source_id)
                    retention_verified.add(source_id)
            if disposition == "missing":
                static_field_ok, static_field_status = _valid_static_fields(component, static_fields_by_id)
                if isinstance(component.get("staticFieldBinding"), dict) and static_field_ok:
                    disposition = "disabled"
                    native_status = "partial"
                    field_status = "verified"
                else:
                    field_status = static_field_status
                    disabled = disabled_by_id.get(source_id, [])
                if disposition == "missing" and len(disabled) == 1 and _valid_retention(disabled[0]):
                    disposition = "disabled"
                    native_status = "partial"
                elif disposition == "missing" and isinstance(explicit, dict) and explicit.get("status") == "disabled" and _valid_retention(explicit):
                    disposition = "disabled"
                    native_status = "partial"
                elif disposition == "missing":
                    codes = [str(row.get("code", "")) for row in diagnostics_by_source.get(source_id, [])]
                    if component.get("convertible") is False and any(token in code for code in codes for token in _UNSUPPORTED_CODES):
                        disposition = "unsupported"
                    elif component.get("convertible") is False and not component.get("nativeType"):
                        disposition = "unsupported"
                    else:
                        disposition = "missing"
                    diagnostics.append(diagnostic("SOURCE_COMPONENT_WITHOUT_NATIVE_DISPOSITION", source_id,
                                                  "No exact native component or verified explicit retention/disabled representation exists; disposition=" + disposition,
                                                  source_id))
        if disposition == "retained":
            retention_expected.add(source_id)
        elif component.get("retainedOnly") is True or component.get("retentionPolicy"):
            retention_expected.add(source_id)

        visible = _is_source_visible(component, node_map)
        if source_id in spine_ids and visible is True:
            presentation_expected.add(source_id)
            diagnostics.append(diagnostic("SOURCE_VISIBLE_SPINE_NOT_RENDERED", source_id,
                                          "Static Spine continuation is a retained non-rendering carrier", source_id))
            presentation_status = "partial"
        elif visible is not True:
            presentation_status = "not_applicable" if visible is False else "not_run"
        else:
            presentation_expected.add(source_id)
            evidence_rows = visible_rows.get(source_id, [])
            if (len(evidence_rows) == 1 and evidence_rows[0].get("sourceVisible") is True
                    and evidence_rows[0].get("verified") is True and evidence_rows[0].get("rendered") is True
                    and disposition == "native"):
                presentation_verified.add(source_id)
                presentation_status = "pass"
            elif len(evidence_rows) == 1 and evidence_rows[0].get("sourceVisible") is False and evidence_rows[0].get("verified") is True:
                presentation_status = "not_applicable"
            else:
                presentation_status = "partial"
                diagnostics.append(diagnostic("STATIC_PRESENTATION_READBACK_INCOMPLETE", source_id,
                                              "Visible source component lacks exact native rendered presentation proof", source_id))
        components.append({
            "sourceId": source_id,
            "sourceType": component.get("type"),
            "expectedNativeType": expected_type,
            "disposition": disposition,
            "nativeStatus": native_status,
            "nativeComponentReadback": valid_native[0] if len(valid_native) == 1 else None,
            "staticFieldStatus": field_status,
            "retentionStatus": "verified" if source_id in retention_verified else "retained_only" if disposition == "retained" else "not_applicable",
            "staticPresentationStatus": presentation_status,
            "sourceVisible": visible,
            "sourceDiagnostics": diagnostics_by_source.get(source_id, []),
            "playerStatus": "not_run",
        })

    # Keep malformed/duplicate source entries in original order as well as in
    # diagnostics; the report count always reflects the complete source list.
    ordered = []
    seen: Counter = Counter()
    for index, raw in enumerate(source_rows):
        sid = raw.get("sourceId") if isinstance(raw, dict) else None
        if isinstance(sid, str) and source_by_id.get(sid):
            if seen[sid] == 0:
                ordered.append(next(row for row in components if row.get("sourceId") == sid))
            seen[sid] += 1
            if seen[sid] > 1:
                ordered.append({"sourceIndex": index, "sourceId": sid, "sourceType": raw.get("type"),
                                "disposition": "missing", "nativeStatus": "missing", "retentionStatus": "not_applicable",
                                "staticPresentationStatus": "not_run", "playerStatus": "not_run"})
        else:
            ordered.append(next((row for row in components if row.get("sourceIndex") == index),
                                {"sourceIndex": index, "sourceId": sid, "sourceType": raw.get("type") if isinstance(raw, dict) else None,
                                 "disposition": "missing", "nativeStatus": "missing", "retentionStatus": "not_applicable",
                                 "staticPresentationStatus": "not_run", "playerStatus": "not_run"}))

    if not readback_available:
        for row in ordered:
            row["nativeStatus"] = "not_run"
            row["staticPresentationStatus"] = "not_run"

    expected_retained = set(retention_expected)
    retention_status = ("not_run" if not readback_available else "not_applicable" if not expected_retained
                        else "pass" if expected_retained <= retention_verified else "partial")
    for source_id in sorted(expected_retained - retention_verified) if readback_available else []:
        diagnostics.append(diagnostic("STATIC_RETENTION_READBACK_INCOMPLETE", source_id,
                                      "Declared retained representation lacks exact verified identity and fields/payload evidence", source_id))
    has_spine_unrendered = any(row.get("code") == "SOURCE_VISIBLE_SPINE_NOT_RENDERED" for row in diagnostics)
    if not readback_available:
        presentation_status = "not_run"
    elif not presentation_expected:
        presentation_status = "not_run"
    elif presentation_expected <= presentation_verified and not has_spine_unrendered and not presentation_incomplete:
        presentation_status = "pass"
    else:
        presentation_status = "partial"
    if not source_rows:
        native_status = "not_applicable"
    elif not readback_available:
        native_status = "not_run"
    elif any(row.get("disposition") in ("missing", "unsupported") for row in ordered):
        native_status = "fail"
    elif any(row.get("disposition") in ("retained", "disabled") or row.get("nativeStatus") != "pass" for row in ordered):
        native_status = "partial"
    else:
        native_status = "pass"
    return {
        "schema": SCHEMA,
        "engine": engine,
        "status": "not_run" if native_status == "not_run" else
                  "pass" if native_status == "pass" and presentation_status == "pass" else
                  "partial" if native_status in ("pass", "partial") else "fail",
        "sourceComponentCount": len(source_rows),
        "uniqueSourceComponentCount": len(source_by_id),
        "dispositionCounts": dict(Counter(row.get("disposition", "missing") for row in ordered)),
        "components": ordered,
        "sourceDiagnostics": source_diagnostics,
        "diagnostics": diagnostics,
        "nativeStaticValidation": native_status,
        "retentionValidation": retention_status,
        "staticPresentationValidation": {"status": presentation_status,
                                         "expectedSourceVisibleCount": len(presentation_expected),
                                         "verifiedSourceVisibleCount": len(presentation_verified),
                                         "diagnostics": [row for row in diagnostics if row.get("code", "").startswith("STATIC_PRESENTATION_") or row.get("code") == "SOURCE_VISIBLE_SPINE_NOT_RENDERED"]},
        "runtimeCheck": "not_run",
        "playerValidation": "not_run",
    }
