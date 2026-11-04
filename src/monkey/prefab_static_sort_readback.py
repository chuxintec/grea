"""Independent verifier for saved Unity static sort-queue evidence."""

from __future__ import annotations

import math
import hashlib
import json
import re

from .io import diagnostic


_SHA = re.compile(r"^[0-9a-f]{64}$")
_GUID = re.compile(r"^[0-9a-f]{32}$")
_TMP_STABLE_SLOT_FIELDS = (
    "slot", "disposition", "characterReferences", "visibleCharacterReferences",
    "textInfoVertexCount", "textInfoTriangleIndexCount", "textInfoNondegenerateTriangleCount",
    "canvasVertexCount", "canvasTriangleIndexCount", "canvasNondegenerateTriangleCount",
    "sourceAssetKind", "sourceAssetGuid", "sourceAssetLocalFileId", "atlasGuid", "atlasLocalFileId",
    "characterAssetEvidenceSha256", "sourceGraphicMaterialFingerprint", "sourceMeshSha256",
)


def _spine_field_bindings(component):
    """Return target member values from a pinned native Spine binding row."""
    rows = component.get("targetFieldBindings") if isinstance(component, dict) else None
    if not isinstance(rows, list):
        return None
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("member"), str):
            return None
        member = row["member"]
        if member in result:
            return None
        if "stringValue" in row:
            value = row["stringValue"]
        elif "boolValue" in row:
            value = row["boolValue"]
        elif "numberValue" in row:
            value = row["numberValue"]
        elif row.get("valueType") == "string":
            value = ""
        else:
            return None
        result[member] = value
    return result


def _spine_source_binding_fields_match(source_fields, component):
    """Compare serialized source fields with the independent stage binding row."""
    bound = _spine_field_bindings(component)
    if not isinstance(source_fields, dict) or not isinstance(bound, dict):
        return False
    source_to_native = {
        "animation": "startingAnimation", "loop": "startingLoop",
        "premultipliedAlpha": "pmaVertexColors", "skin": "initialSkinName",
        "timeScale": "timeScale",
    }
    expected = {target: bound[target] for target in source_to_native.values() if target in bound}
    if len(expected) != len(source_to_native):
        return False
    for source_name, target_name in source_to_native.items():
        actual = source_fields.get(target_name)
        expected_value = expected[target_name]
        if isinstance(expected_value, bool):
            if actual not in ("True", "False") or (actual == "True") is not expected_value:
                return False
        elif isinstance(expected_value, (int, float)) and not isinstance(expected_value, bool):
            try:
                if float(actual) != float(expected_value):
                    return False
            except (TypeError, ValueError):
                return False
        elif actual != expected_value:
            return False
    return set(source_fields) == set(expected)


def _load_spine_binding_contract(plan, raw_bytes):
    """Validate the candidate-local, SHA-pinned native binding-plan bytes."""
    stage = plan.get("spineNativeStage") if isinstance(plan, dict) else None
    if not isinstance(stage, dict):
        return None, ["Spine native stage is absent"]
    expected_hash = stage.get("nativeBindingPlanSha256")
    if not isinstance(raw_bytes, bytes) or not _SHA.fullmatch(expected_hash or ""):
        return None, ["frozen Spine native binding-plan bytes/hash are absent"]
    if hashlib.sha256(raw_bytes).hexdigest() != expected_hash:
        return None, ["frozen Spine native binding-plan bytes do not match the plan SHA"]
    try:
        binding = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, ["frozen Spine native binding-plan is not UTF-8 JSON"]
    if not isinstance(binding, dict):
        return None, ["frozen Spine native binding-plan root is malformed"]
    components = binding.get("components")
    data_assets = binding.get("dataAssets")
    errors = []
    if (binding.get("contract") != "monkey-spine-native-binding/1" or
            stage.get("nativeBindingPlanPath") != "Assets/Game/Editor/Conversion/spine-native-binding-plan.json" or
            binding.get("sourceManifestSha256") != stage.get("sourceManifestSha256") or
            binding.get("sourceNativeBindingPlanSha256") != stage.get("sourceNativeBindingPlanSha256") or
            binding.get("sourceManifestSha256") != plan.get("sourceManifestSha256") or
            not isinstance(components, list) or not isinstance(data_assets, list) or
            binding.get("componentCount") != len(components) or
            binding.get("dataAssetCount") != len(data_assets) or
            stage.get("componentCount") != len(components)):
        errors.append("frozen Spine native binding-plan contract, pins, or counts differ")
    component_map = {}
    for component in components if isinstance(components, list) else []:
        if (not isinstance(component, dict) or not isinstance(component.get("sourceComponentId"), str) or
                not isinstance(component.get("sourcePrefabId"), str) or
                not isinstance(component.get("sourceNodeId"), str) or
                type(component.get("sourceHasStaticDataReference")) is not bool):
            errors.append("frozen Spine native binding-plan component row is malformed")
            continue
        source_id = component["sourceComponentId"]
        if source_id in component_map:
            errors.append(f"frozen Spine native binding-plan repeats component {source_id}")
        component_map[source_id] = component
    data_map = {}
    for data in data_assets if isinstance(data_assets, list) else []:
        if (not isinstance(data, dict) or not isinstance(data.get("sourceAssetId"), str) or
                not isinstance(data.get("skeletonDataAssetPath"), str) or
                not data["skeletonDataAssetPath"].startswith("Assets/")):
            errors.append("frozen Spine native binding-plan data asset row is malformed")
            continue
        asset_id = data["sourceAssetId"]
        if asset_id in data_map:
            errors.append(f"frozen Spine native binding-plan repeats data asset {asset_id}")
        data_map[asset_id] = data
    for source_id, component in component_map.items():
        source_component = next((row for row in plan.get("components", [])
                                 if isinstance(row, dict) and row.get("sourceId") == source_id), None)
        if (source_component is None or source_component.get("type") != "sp.Skeleton" or
                component.get("sourceNodeId") != source_component.get("node")):
            errors.append(f"frozen Spine component does not map to the import-plan source row: {source_id}")
        asset_id = component.get("sourceDataAssetId")
        if component.get("sourceHasStaticDataReference"):
            if (not isinstance(asset_id, str) or not asset_id or asset_id not in data_map):
                errors.append(f"frozen Spine component data mapping is absent: {source_id}")
        elif asset_id is not None:
            errors.append(f"frozen source-null Spine component has a data asset mapping: {source_id}")
    expected_source_ids = {row.get("sourceId") for row in plan.get("components", [])
                           if isinstance(row, dict) and row.get("type") == "sp.Skeleton"}
    if expected_source_ids != set(component_map):
        errors.append("frozen Spine native binding component IDs do not exactly cover the import-plan Spine scope")
    if errors:
        return None, errors
    return {"components": component_map, "dataAssets": data_map}, []


def _valid_tmp_slot_enumeration(value, source_id):
    if not isinstance(value, dict):
        return False
    rows = value.get("rows")
    return (value.get("verified") is True and value.get("sourceComponentId") == source_id and
            type(value.get("slotCount")) is int and isinstance(rows, list) and
            value["slotCount"] == len(rows) and
            [row.get("slot") for row in rows if isinstance(row, dict)] == list(range(len(rows))) and
            all(isinstance(row, dict) for row in rows) and
            _SHA.fullmatch(value.get("sourceTextSha256") or "") is not None and
            _SHA.fullmatch(value.get("evidenceSha256") or "") is not None)


def _tmp_stable_slot_rows_match(saved, current, source_id):
    if (not _valid_tmp_slot_enumeration(saved, source_id) or
            not _valid_tmp_slot_enumeration(current, source_id) or
            saved.get("sourceTextSha256") != current.get("sourceTextSha256") or
            saved.get("slotCount") != current.get("slotCount")):
        return False
    for saved_row, current_row in zip(saved["rows"], current["rows"]):
        for key in _TMP_STABLE_SLOT_FIELDS:
            if saved_row.get(key) != current_row.get(key):
                return False
        if not _SHA.fullmatch(saved_row.get("characterAssetEvidenceSha256") or ""):
            return False
        if saved_row.get("disposition") == "drawable" and (
                not _SHA.fullmatch(saved_row.get("sourceMeshSha256") or "") or
                not _SHA.fullmatch(saved_row.get("sourceGraphicMaterialFingerprint") or "")):
            return False
    return True


def _diag(owner, message):
    return diagnostic("STATIC_SORT_QUEUE_NATIVE_MISMATCH", owner, message, owner)


def _same(actual, expected, keys):
    return all(actual.get(key) == expected.get(key) for key in keys)


def _field_rows(specs, rows, owner, *, sort_root=False):
    key = "sourceSortRoots" if sort_root else "sourceFields"
    if not isinstance(rows, list) or len(rows) != len(specs):
        return [f"{key} actual row count differs"]
    failures = []
    fields = ("sourceId", "nativeId", "node")
    actual_ids = []
    for index, (expected, actual) in enumerate(zip(specs, rows)):
        if not isinstance(actual, dict):
            failures.append(f"{key}[{index}] is malformed")
            continue
        actual_ids.append(actual.get("sourceId"))
        source_values_match = _same(actual, expected, fields)
        if sort_root:
            source_values_match = source_values_match and actual.get("enabledInSource") == expected.get("enabled")
        else:
            source_values_match = (source_values_match and actual.get("enabledInSource") == expected.get("enabled") and
                                   actual.get("sourceSortOrder") == expected.get("sortOrder"))
        if not source_values_match:
            failures.append(f"{key}[{index}] source value differs")
        if (actual.get("identityPresent") is not True or actual.get("verified") is not True or
                actual.get("identityComponentEnabled") is not False or
                actual.get("actualSourceId") != expected.get("sourceId") or
                actual.get("actualNativeId") != expected.get("nativeId") or
                actual.get("actualEnabledInSource") is not expected.get("enabled")):
            failures.append(f"{key}[{index}] persistent typed identity readback differs")
        if not sort_root and actual.get("actualSortOrder") != expected.get("sortOrder"):
            failures.append(f"sourceFields[{index}] actual sort order differs")
    if len(actual_ids) != len(set(actual_ids)):
        failures.append(f"{key} contains duplicate source identities")
    return failures


def _check_graphics(spec, queue_readback, owner, mode):
    failures = []
    expected = spec.get("renderers")
    rows = queue_readback.get("graphics")
    empty_rows = queue_readback.get("emptyRenderers")
    if not isinstance(expected, list) or not isinstance(rows, list) or not isinstance(empty_rows, list):
        return [f"{mode} graphics evidence is absent"]
    expected_by_id = {row.get("sourceComponentId"): row for row in expected if isinstance(row, dict)}
    empty_by_id = {row.get("sourceComponentId"): row for row in empty_rows
                   if isinstance(row, dict) and row.get("actualQueueIndex", -1) >= 0}
    non_draw = spec.get("nonDrawRenderers") or []
    retained_by_id = {row.get("sourceComponentId"): row for row in empty_rows
                      if isinstance(row, dict) and row.get("actualQueueIndex") == -1}
    expected_non_draw = {row.get("sourceComponentId"): row for row in non_draw if isinstance(row, dict)}
    if set(retained_by_id) != set(expected_non_draw):
        failures.append(f"{mode} disabled source renderer denominator differs")
    for sid, row in retained_by_id.items():
        source = expected_non_draw.get(sid)
        if source is None or not _empty_renderer_matches(source, row, mode):
            failures.append(f"{mode} disabled renderer typed evidence differs: {sid}")
    for sid, row in empty_by_id.items():
        source = expected_by_id.get(sid)
        if source is None or not _empty_renderer_matches(source, row, mode):
            failures.append(f"{mode} empty renderer typed evidence differs: {sid}")
    drawable_expected = {sid: row for sid, row in expected_by_id.items() if sid not in empty_by_id}
    seen = set()
    actual_order = []
    for row in rows:
        if not isinstance(row, dict):
            failures.append(f"{mode} graphic row is malformed")
            continue
        sid = row.get("sourceComponentId")
        source = drawable_expected.get(sid)
        if source is None:
            failures.append(f"{mode} graphic source identity is unexpected")
            continue
        seen.add(sid)
        actual_order.append((row.get("sourceQueueIndex"), sid))
        if row.get("sourceNode") != source.get("node"):
            failures.append(f"{mode} graphic source node differs: {sid}")
        if not isinstance(row.get("sourceQueueIndex"), int) or row.get("sourceQueueIndex") < 0:
            failures.append(f"{mode} graphic actual generated queue index is invalid: {sid}")
        if row.get("staticSnapshotVerified") is not True or row.get("verified") is not True:
            failures.append(f"{mode} graphic snapshot is not verified: {sid}")
        if row.get("sourceGraphicEnabled") is not True or row.get("vertexCount", 0) <= 0:
            failures.append(f"{mode} graphic has no enabled source geometry: {sid}")
        if not _GUID.fullmatch(row.get("meshAssetGuid") or ""):
            failures.append(f"{mode} graphic mesh asset identity is missing: {sid}")
        for key in ("capturedSourceMeshSha256", "meshContentSha256", "proxyMeshSha256"):
            if not _SHA.fullmatch(row.get(key) or ""):
                failures.append(f"{mode} graphic {key} evidence is missing: {sid}")
        if row.get("meshContentSha256") != row.get("proxyMeshSha256"):
            failures.append(f"{mode} persisted mesh content hash differs: {sid}")
        alpha_pairs = (("sourceRendererAlpha", "proxyRendererAlpha"),
                       ("sourceInheritedAlpha", "proxyInheritedAlpha"),
                       ("sourceEffectiveAlpha", "proxyEffectiveAlpha"))
        alpha_values_valid = True
        for source_key, proxy_key in alpha_pairs:
            source_alpha, proxy_alpha = row.get(source_key), row.get(proxy_key)
            if (type(source_alpha) not in (int, float) or type(proxy_alpha) not in (int, float) or
                    not math.isfinite(source_alpha) or not math.isfinite(proxy_alpha) or
                    abs(source_alpha - proxy_alpha) > 1e-4):
                alpha_values_valid = False
        if row.get("opacityVerified") is not True or not alpha_values_valid:
            failures.append(f"{mode} CanvasGroup/CanvasRenderer alpha evidence differs: {sid}")
        counts = row.get("sourceUvChannelVertexCounts")
        proxy_counts = row.get("proxyUvChannelVertexCounts")
        dimensions = row.get("sourceUvChannelDimensions")
        proxy_dimensions = row.get("proxyUvChannelDimensions")
        if (not isinstance(counts, list) or len(counts) != 8 or
                not isinstance(proxy_counts, list) or len(proxy_counts) != 8 or
                counts != proxy_counts or not isinstance(dimensions, list) or len(dimensions) != 8 or
                not isinstance(proxy_dimensions, list) or len(proxy_dimensions) != 8 or
                dimensions != proxy_dimensions):
            failures.append(f"{mode} UV channels 0–7 do not match source evidence: {sid}")
        if mode == "loaded":
            expected_measurement = "CanvasRenderer.SetMesh-local+Transform.localToWorldMatrix.MultiplyPoint3x4"
            def matrix_values(value):
                if not isinstance(value, str):
                    return None
                try:
                    parsed = [float(item) for item in value.split(",")]
                except (TypeError, ValueError):
                    return None
                return parsed if len(parsed) == 16 and all(math.isfinite(item) for item in parsed) else None

            source_matrix = matrix_values(row.get("transformedSourceMatrixExact"))
            proxy_matrix = matrix_values(row.get("transformedProxyMatrixExact"))
            try:
                capture_diagnostic = json.loads(row.get("transformCaptureDiagnosticJson"))
            except (TypeError, ValueError):
                capture_diagnostic = None
            capture_source_matrix = capture_diagnostic.get("sourceLocalToWorldMatrix") if isinstance(capture_diagnostic, dict) else None
            capture_proxy_matrix = capture_diagnostic.get("finalProxyLocalToWorldMatrix") if isinstance(capture_diagnostic, dict) else None
            capture_matrices_valid = all(isinstance(matrix, list) and len(matrix) == 16 and
                all(type(value) in (int, float) and math.isfinite(value) for value in matrix)
                for matrix in (capture_source_matrix, capture_proxy_matrix))
            if (row.get("worldMeasurementMethod") != expected_measurement or
                    source_matrix is None or proxy_matrix is None or
                    not isinstance(capture_diagnostic, dict) or
                    capture_diagnostic.get("sourceComponentId") != sid or
                    capture_diagnostic.get("selectedPath") in (None, "") or
                    not capture_matrices_valid or
                    not isinstance(row.get("transformedMatrixDifference"), str) or
                    not all(token in row["transformedMatrixDifference"] for token in ("firstIndex=", "maxAbsDifference="))):
                failures.append(f"loaded CanvasRenderer local-mesh/world-matrix measurement proof is incomplete: {sid}")
            vertex_error = row.get("maxWorldVertexError")
            vertex_diagnostic = row.get("transformedVertexDiagnostic")
            if (type(vertex_error) not in (int, float) or not math.isfinite(vertex_error) or vertex_error < 0 or
                    (vertex_error == 0 and vertex_diagnostic not in (None, "")) or
                    (vertex_error > 0 and (not isinstance(vertex_diagnostic, str) or
                     not all(token in vertex_diagnostic for token in
                             ("sourceLocal=", "sourceWorld=", "proxyLocal=", "proxyWorld=", "distance="))))):
                failures.append(f"loaded world-vertex diagnostics omit the measured source/proxy points: {sid}")
            if (row.get("runtimeMeshVerified") is not True or
                    row.get("transformedGeometryVerified") is not True or
                    row.get("worldRectVerified") is not True or
                    row.get("transformedMeshMetricsVerified") is not True or
                    row.get("sourceCulled") is not True or row.get("proxyVisible") is not True):
                failures.append(f"loaded graphic presentation evidence is incomplete: {sid}")
            if row.get("sourceMeshSha256") != row.get("capturedSourceMeshSha256"):
                failures.append(f"loaded source mesh differs from its persisted capture: {sid}")
            if row.get("renderedMeshSha256") != row.get("proxyMeshSha256"):
                failures.append(f"loaded CanvasRenderer mesh differs from persisted proxy: {sid}")
            if (row.get("renderedUvChannelVertexCounts") != proxy_counts or
                    row.get("renderedUvChannelDimensions") != proxy_dimensions):
                failures.append(f"loaded CanvasRenderer UV channels differ from proxy: {sid}")
            expected_transformed_hash = row.get("expectedTransformedMeshSha256")
            actual_transformed_hash = row.get("actualTransformedMeshSha256")
            if (not _SHA.fullmatch(expected_transformed_hash or "") or
                    not _SHA.fullmatch(actual_transformed_hash or "") or
                    (row.get("transformedMeshFingerprintVerified") is True) !=
                    (expected_transformed_hash == actual_transformed_hash)):
                failures.append(f"loaded transformed mesh fingerprint evidence is incomplete: {sid}")
            metrics = ("transformedTopologyMatches", "transformedUvMatches", "transformedColorsMatch",
                       "transformedNormalsMatch", "transformedTangentsMatch")
            max_error = row.get("maxWorldVertexError")
            if (type(max_error) not in (int, float) or not math.isfinite(max_error) or
                    max_error < 0 or max_error > 0.001 or
                    row.get("sourceVertexCount") != row.get("persistedProxyVertexCount") or
                    any(row.get(key) is not True for key in metrics)):
                failures.append(
                    f"loaded transformed mesh diagnostics differ: {sid} "
                    f"worldVertexError={max_error} topology={row.get('transformedTopologyMatches')} "
                    f"uv={row.get('transformedUvMatches')} colors={row.get('transformedColorsMatch')} "
                    f"normals={row.get('transformedNormalsMatch')} tangents={row.get('transformedTangentsMatch')}"
                )
        else:
            if row.get("renderedUvChannelVertexCounts") not in ([], None):
                failures.append(f"persistent readback claims initialized renderer channels: {sid}")
    if set(drawable_expected) != seen:
        failures.append(f"{mode} graphic source denominator differs")
    events = spec.get("drawEvents") or []
    expected_order = [event.get("sourceComponentId") for event in events
                      if isinstance(event, dict) and event.get("kind") == "renderer"]
    if not events:
        expected_order = [row.get("sourceComponentId") for row in expected if isinstance(row, dict)]
    observed_order = []
    queue_events = actual_order + [(row.get("actualQueueIndex"), sid) for sid, row in empty_by_id.items()]
    for _, sid in sorted(queue_events, key=lambda item: item[0] if isinstance(item[0], int) else -1):
        if not observed_order or observed_order[-1] != sid:
            observed_order.append(sid)
    if observed_order != expected_order:
        failures.append(f"{mode} renderer ordering differs from source queue")
    return failures


def _check_text_sources(spec, queue_readback, mode):
    failures = []
    non_draw_ids = {row.get("sourceComponentId") for row in spec.get("nonDrawRenderers", []) if isinstance(row, dict)}
    graphic_rows = queue_readback.get("graphics") or []
    drawable_ids = {row.get("sourceComponentId") for row in graphic_rows if isinstance(row, dict)}
    text_specs = {row.get("sourceComponentId"): row for row in spec.get("renderers", [])
                    if isinstance(row, dict) and row.get("sourceType") in ("cc.Label", "cc.RichText") and
                    row.get("sourceComponentId") not in non_draw_ids and row.get("sourceComponentId") in drawable_ids}
    expected_ids = set(text_specs)
    actual = queue_readback.get("textSources")
    if not isinstance(actual, list):
        return [f"{mode} TMP typed source readback is absent"]
    actual_ids = set()
    actual_slots = set()
    slot_enumerations = {}
    graphics = graphic_rows
    by_graphic_identity = {}
    for graphic in graphics:
        if isinstance(graphic, dict):
            by_graphic_identity.setdefault((graphic.get("sourceComponentId"), graphic.get("textMaterialSlot")), []).append(graphic)
    for row in actual:
        if (not isinstance(row, dict) or not isinstance(row.get("sourceComponentId"), str) or
                not isinstance(row.get("evidence"), dict)):
            failures.append(f"{mode} TMP source row is malformed")
            continue
        source_id = row["sourceComponentId"]
        slot = row.get("materialSlot")
        evidence = row["evidence"]
        actual_ids.add(source_id)
        key = (source_id, slot)
        regenerated_mesh = evidence.get("sourceMeshRegeneratedFromCurrentTmpVerified")
        if regenerated_mesh is True:
            if mode != "loaded":
                failures.append(f"{mode} TMP claims a live regenerated source mesh: {source_id}")
            if (not _SHA.fullmatch(evidence.get("sourceMeshPositionPairEvidenceSha256") or "") or
                    not _SHA.fullmatch(evidence.get("sourceMeshRegenerationEvidenceSha256") or "")):
                failures.append(f"{mode} TMP regenerated source mesh evidence hash is missing: {source_id}")
            linked_geometry = by_graphic_identity.get(key, [])
            geometry_flags = ("transformedTopologyMatches", "transformedUvMatches", "transformedColorsMatch",
                              "transformedNormalsMatch", "transformedTangentsMatch")
            max_world_error = linked_geometry[0].get("maxWorldVertexError") if len(linked_geometry) == 1 else None
            captured_source_hash = evidence.get("sourceMeshSha256")
            current_source_hash = evidence.get("currentSourceMeshSha256")
            proxy_mesh_hash = evidence.get("proxyMeshSha256")
            if (len(linked_geometry) != 1 or
                    linked_geometry[0].get("sourceComponentId") != source_id or
                    linked_geometry[0].get("textMaterialSlot") != slot or
                    not _SHA.fullmatch(captured_source_hash or "") or
                    linked_geometry[0].get("sourceMeshSha256") != captured_source_hash or
                    not _SHA.fullmatch(current_source_hash or "") or
                    linked_geometry[0].get("currentTextSourceMeshSha256") != current_source_hash or
                    not _SHA.fullmatch(proxy_mesh_hash or "") or
                    linked_geometry[0].get("proxyMeshSha256") != proxy_mesh_hash or
                    linked_geometry[0].get("transformedGeometryVerified") is not True or
                    any(linked_geometry[0].get(flag) is not True for flag in geometry_flags) or
                    type(max_world_error) not in (int, float) or not math.isfinite(max_world_error) or
                    max_world_error < 0 or max_world_error > 0.001):
                failures.append(f"{mode} TMP regenerated source mesh lacks matching strict proxy geometry proof: "
                                f"{source_id} slot={slot} maxWorldVertexError={max_world_error}")
        elif regenerated_mesh not in (None, False):
            failures.append(f"{mode} TMP regenerated source mesh flag is malformed: {source_id}")
        if type(slot) is not int or slot < 0 or key in actual_slots:
            failures.append(f"{mode} TMP material slot is invalid or duplicated: {source_id}")
        actual_slots.add(key)
        enumeration = evidence.get("textSlotEnumeration")
        if not isinstance(enumeration, dict):
            failures.append(f"{mode} TMP slot enumeration evidence is absent: {source_id}")
        else:
            rows = enumeration.get("rows")
            rows = rows if isinstance(rows, list) else []
            row_slots = [entry.get("slot") for entry in rows if isinstance(entry, dict)]
            if (enumeration.get("verified") is not True or enumeration.get("sourceComponentId") != source_id or
                    type(enumeration.get("slotCount")) is not int or enumeration.get("slotCount") != len(rows) or
                    len(row_slots) != len(rows) or any(type(value) is not int for value in row_slots) or
                    sorted(row_slots) != list(range(len(rows))) or
                    not _SHA.fullmatch(enumeration.get("sourceTextSha256") or "") or
                    not _SHA.fullmatch(enumeration.get("evidenceSha256") or "") or
                    any(not _SHA.fullmatch(entry.get("evidenceSha256") or "") for entry in rows if isinstance(entry, dict))):
                failures.append(f"{mode} TMP slot enumeration identity or denominator differs: {source_id}")
            else:
                if any(type(entry.get("sourceAssetLocalFileId")) is not int or entry["sourceAssetLocalFileId"] == 0 or
                       not _GUID.fullmatch(entry.get("sourceAssetGuid") or "") or
                       type(entry.get("atlasLocalFileId")) is not int or entry["atlasLocalFileId"] == 0 or
                       not _GUID.fullmatch(entry.get("atlasGuid") or "") or
                       not _SHA.fullmatch(entry.get("characterAssetEvidenceSha256") or "")
                       for entry in rows):
                    failures.append(f"{mode} TMP stable slot asset/glyph evidence is incomplete: {source_id}")
                for entry in rows:
                    if entry.get("disposition") == "drawable" and (
                            not _SHA.fullmatch(entry.get("sourceMeshSha256") or "") or
                            not _SHA.fullmatch(entry.get("sourceGraphicMaterialFingerprint") or "")):
                        failures.append(f"{mode} TMP drawable slot mesh/material proof is incomplete: {source_id}")
                previous = slot_enumerations.get(source_id)
                if previous is not None and previous.get("evidenceSha256") != enumeration.get("evidenceSha256"):
                    failures.append(f"{mode} TMP slot enumeration differs across proxy identities: {source_id}")
                slot_enumerations[source_id] = enumeration
                placeholders = [entry for entry in rows if entry.get("disposition") == "empty-placeholder"]
                unknown = [entry for entry in rows if entry.get("disposition") not in ("drawable", "empty-placeholder")]
                for entry in placeholders:
                    if (entry.get("slot") != 0 or type(entry.get("characterReferences")) is not int or
                            entry.get("characterReferences") < 0 or
                            type(entry.get("visibleCharacterReferences")) is not int or
                            entry.get("visibleCharacterReferences") != 0 or
                            type(entry.get("textInfoNondegenerateTriangleCount")) is not int or
                            entry.get("textInfoNondegenerateTriangleCount") != 0 or
                            type(entry.get("canvasNondegenerateTriangleCount")) is not int or
                            entry.get("canvasNondegenerateTriangleCount") != 0 or
                            not _SHA.fullmatch(entry.get("evidenceSha256") or "")):
                        failures.append(f"{mode} TMP placeholder lacks exact slot-0 zero-draw proof: {source_id}")
                if unknown or len(placeholders) > 1:
                    failures.append(f"{mode} TMP slot disposition is invalid: {source_id}")
        if source_id not in expected_ids:
            failures.append(f"{mode} TMP row has an extra source component: {source_id}")
        expected_node = text_specs.get(source_id, {}).get("node")
        if (row.get("sourceNode") != expected_node or row.get("readbackMode") != mode or
                evidence.get("sourceComponentId") != source_id or evidence.get("materialSlot") != slot):
            failures.append(f"{mode} TMP owner source-node/material-slot mapping differs: {source_id}")
        for key_name in ("proxyMaterialGuid", "shaderGuid", "textureGuid", "proxyMeshGuid", "ownerFontMaterialGuid"):
            if not _GUID.fullmatch(evidence.get(key_name) or ""):
                failures.append(f"{mode} TMP {key_name} identity is missing: {source_id}")
        source_material_guid = evidence.get("materialGuid")
        if source_material_guid and not _GUID.fullmatch(source_material_guid):
            failures.append(f"{mode} TMP source material GUID is malformed: {source_id}")
        if mode == "persistent":
            if (not _GUID.fullmatch(evidence.get("ownerGuid") or "") or
                    type(evidence.get("ownerLocalFileId")) is not int or evidence["ownerLocalFileId"] == 0 or
                    evidence.get("ownerScopeVerified") is not True or
                    evidence.get("persistentTextSlotContractVerified") is not True):
                failures.append(f"persistent TMP mapped owner GUID/local ID differs: {source_id}")
        elif (evidence.get("ownerGuid") not in (None, "") or evidence.get("ownerLocalFileId") not in (None, 0) or
              evidence.get("ownerScopeVerified") is not True):
            failures.append(f"loaded TMP owner does not match the transient loaded source map: {source_id}")
        for optional_guid in ("fontAssetGuid", "spriteAssetGuid"):
            value = evidence.get(optional_guid)
            if value and not _GUID.fullmatch(value):
                failures.append(f"{mode} TMP {optional_guid} is malformed: {source_id}")
        local_keys = ("proxyMaterialLocalFileId", "ownerFontMaterialLocalFileId", "shaderLocalFileId",
                      "textureLocalFileId", "proxyMeshLocalFileId")
        for local_key in local_keys:
            if type(evidence.get(local_key)) is not int or evidence[local_key] == 0:
                failures.append(f"{mode} TMP {local_key} is missing: {source_id}")
        if source_material_guid and (type(evidence.get("materialLocalFileId")) is not int or evidence["materialLocalFileId"] == 0):
            failures.append(f"{mode} TMP source material local ID is missing: {source_id}")
        if evidence.get("fontAssetGuid") and (type(evidence.get("fontAssetLocalFileId")) is not int or evidence["fontAssetLocalFileId"] == 0):
            failures.append(f"{mode} TMP font asset local ID is missing: {source_id}")
        if evidence.get("spriteAssetGuid") and (type(evidence.get("spriteAssetLocalFileId")) is not int or evidence["spriteAssetLocalFileId"] == 0):
            failures.append(f"{mode} TMP sprite asset local ID is missing: {source_id}")
        fallback_algorithm = evidence.get("tmpFallbackAlgorithm")
        if fallback_algorithm:
            outline_suffix = "+native-static-text-outline-v1"
            has_outline_profile = fallback_algorithm.endswith(outline_suffix)
            base_fallback_algorithm = (fallback_algorithm[:-len(outline_suffix)]
                                       if has_outline_profile else fallback_algorithm)
            outline_color = evidence.get("ownerStyleOutlineColor")
            outline_width = evidence.get("ownerStyleOutlineWidth")
            outline_color_valid = (isinstance(outline_color, dict) and
                                   all(type(outline_color.get(channel)) in (int, float) and
                                       math.isfinite(outline_color[channel]) and 0 <= outline_color[channel] <= 1
                                       for channel in ("r", "g", "b", "a")))
            outline_style_valid = (
                evidence.get("ownerStyleVerified") is True and
                evidence.get("ownerStyleProfile") == "native-static-text-outline-font-material-v1" and
                evidence.get("ownerStyleSourceComponentId") == source_id and
                type(outline_width) in (int, float) and math.isfinite(outline_width) and outline_width >= 0 and
                outline_color_valid and
                _GUID.fullmatch(evidence.get("ownerStyleSourceFontAssetGuid") or "") is not None and
                type(evidence.get("ownerStyleSourceFontAssetLocalFileId")) is int and
                evidence["ownerStyleSourceFontAssetLocalFileId"] != 0 and
                _GUID.fullmatch(evidence.get("ownerStyleSourceFontMaterialGuid") or "") is not None and
                type(evidence.get("ownerStyleSourceFontMaterialLocalFileId")) is int and
                evidence["ownerStyleSourceFontMaterialLocalFileId"] != 0 and
                _SHA.fullmatch(evidence.get("ownerStyleSourceFontMaterialFingerprint") or "") is not None and
                type(evidence.get("persistentFallbackVariantRegistered")) is bool and
                evidence.get("persistentFallbackVariantRegistered") is True
            )
            no_outline_style_valid = (
                evidence.get("ownerStyleVerified") is True and
                evidence.get("ownerStyleProfile") in (None, "") and
                evidence.get("ownerStyleSourceComponentId") in (None, "") and
                evidence.get("persistentFallbackVariantRegistered") is False
            )
            if (base_fallback_algorithm not in ("tmpro-fallback-font-material-v1",
                                                "tmpro-fallback-font-material-v1+tmpro-multi-atlas-v1",
                                                "tmpro-multi-atlas-v1") or
                    (has_outline_profile and not outline_style_valid) or
                    (not has_outline_profile and not no_outline_style_valid) or
                    not _GUID.fullmatch(evidence.get("fallbackFontAssetGuid") or "") or
                    not _GUID.fullmatch(evidence.get("fallbackFontMaterialGuid") or "") or
                    not _GUID.fullmatch(evidence.get("fallbackAtlasGuid") or "") or
                    any(type(evidence.get(key)) is not int or evidence[key] == 0 for key in
                        ("fallbackFontAssetLocalFileId", "fallbackFontMaterialLocalFileId", "fallbackAtlasLocalFileId")) or
                    not _SHA.fullmatch(evidence.get("transientFallbackFingerprint") or "") or
                    not _SHA.fullmatch(evidence.get("bakedProxyMaterialFingerprint") or "") or
                    evidence.get("transientFallbackFingerprint") != evidence.get("bakedProxyMaterialFingerprint")):
                failures.append(f"{mode} TMP SDK fallback descriptor or baked material proof differs: {source_id}")
        else:
            if source_material_guid is None or not _SHA.fullmatch(evidence.get("sourceMaterialFingerprint") or "") or \
                    evidence.get("bakedProxyMaterialFingerprint") != evidence.get("sourceMaterialFingerprint"):
                failures.append(f"{mode} TMP direct source material proof is incomplete: {source_id}")
        for fingerprint_key in ("sourceMaterialFingerprint", "ownerFontMaterialFingerprint",
                                "fallbackFontMaterialFingerprint", "bakedProxyMaterialFingerprint"):
            value = evidence.get(fingerprint_key)
            if value and not _SHA.fullmatch(value):
                failures.append(f"{mode} TMP {fingerprint_key} is malformed: {source_id}")
        if (bool(evidence.get("fontAssetGuid")) == bool(evidence.get("spriteAssetGuid")) or
                evidence.get("persistentReferencesVerified") is not True or
                evidence.get("fontAssetVerified") is not True or evidence.get("spriteAssetVerified") is not True or
                evidence.get("materialVerified") is not True or evidence.get("shaderVerified") is not True or
                evidence.get("textureVerified") is not True or evidence.get("proxyMaterialVerified") is not True or
                evidence.get("tmpFallbackDescriptorVerified") is not True or
                evidence.get("transientFallbackVerified") is not True or
                evidence.get("ownerFontMaterialVerified") is not True or
                evidence.get("fallbackFontAssetVerified") is not True or
                evidence.get("fallbackFontMaterialVerified") is not True or
                evidence.get("fallbackAtlasVerified") is not True or
                evidence.get("bakedProxyMeshVerified") is not True or
                evidence.get("verified") is not True):
            failures.append(f"{mode} TMP persistent owner/font/material/atlas proof differs: {source_id}")
        if not _SHA.fullmatch(evidence.get("sourceMeshSha256") or "") or not _SHA.fullmatch(evidence.get("proxyMeshSha256") or ""):
            failures.append(f"{mode} TMP source/proxy mesh hashes are missing: {source_id}")
        saved_slot = next((entry for entry in (enumeration or {}).get("rows", [])
                           if isinstance(entry, dict) and entry.get("slot") == slot), None)
        expected_slot_asset_guid = evidence.get("spriteAssetGuid") if saved_slot and saved_slot.get("sourceAssetKind") == "sprite" \
            else evidence.get("fontAssetGuid")
        expected_slot_asset_local = evidence.get("spriteAssetLocalFileId") if saved_slot and saved_slot.get("sourceAssetKind") == "sprite" \
            else evidence.get("fontAssetLocalFileId")
        if (saved_slot is None or saved_slot.get("disposition") != "drawable" or
                saved_slot.get("sourceAssetGuid") != expected_slot_asset_guid or
                saved_slot.get("sourceAssetLocalFileId") != expected_slot_asset_local or
                saved_slot.get("atlasGuid") != evidence.get("textureGuid") or
                saved_slot.get("atlasLocalFileId") != evidence.get("textureLocalFileId") or
                saved_slot.get("sourceMeshSha256") != evidence.get("sourceMeshSha256") or
                saved_slot.get("sourceGraphicMaterialFingerprint") != evidence.get("sourceMaterialFingerprint") or
                saved_slot.get("characterAssetEvidenceSha256") != evidence.get("textInfoCharacterAssetEvidenceSha256")):
            failures.append(f"{mode} TMP saved slot source/mesh/material/glyph proof differs: {source_id}")
        if mode == "loaded":
            current_enumeration = evidence.get("currentTextSlotEnumeration")
            if not _tmp_stable_slot_rows_match(enumeration, current_enumeration, source_id):
                failures.append(f"loaded TMP current slot differs in stable text/asset/mesh evidence: {source_id}")
            elif current_enumeration["rows"][slot].get("disposition") != "drawable":
                failures.append(f"loaded TMP current slot is not drawable: {source_id}")
        linked = by_graphic_identity.get((source_id, slot), [])
        if len(linked) != 1 or linked[0].get("meshAssetGuid") != evidence.get("proxyMeshGuid") or \
                linked[0].get("proxyMeshSha256") != evidence.get("proxyMeshSha256") or \
                linked[0].get("materialGuid") != evidence.get("proxyMaterialGuid") or linked[0].get("textureGuid") != evidence.get("textureGuid"):
            failures.append(f"{mode} TMP typed assets do not match exactly one proxy graphic: {source_id}")
        if mode == "loaded" and (evidence.get("generatedSlotResolved") is not True or
                                  evidence.get("sourceStateVerified") is not True or evidence.get("sourceMeshVerified") is not True):
            failures.append(f"loaded TMP source slot state or mesh differs: {source_id}")
        if mode == "persistent" and evidence.get("generatedSlotResolved") is True:
            failures.append(f"persistent TMP readback claims a loaded generated slot: {source_id}")
    for source_id, enumeration in slot_enumerations.items():
        expected_drawable_slots = {entry.get("slot") for entry in enumeration.get("rows", [])
                                   if entry.get("disposition") == "drawable"}
        observed_slots = {slot for sid, slot in actual_slots if sid == source_id}
        if expected_drawable_slots != observed_slots:
            failures.append(f"{mode} TMP drawable slots differ from native proxy identities: {source_id}")
        if not expected_drawable_slots:
            failures.append(f"{mode} TMP owner has no drawable slot identity: {source_id}")
    if actual_ids != expected_ids:
        failures.append(f"{mode} TMP source component denominator differs")
    if queue_readback.get("textSourcesVerified") is not True:
        failures.append(f"{mode} TMP aggregate typed source verification is false")
    return failures


def _check_spine_owner_delegations(spec, queue_readback, mode, plan=None, spine_native_bindings=None):
    failures = []
    renderers = spec.get("renderers")
    proof_rows = queue_readback.get("spineOwnerDelegations")
    source_spines = {row.get("sourceComponentId"): row for row in renderers or []
                     if isinstance(row, dict) and row.get("sourceType") == "sp.Skeleton"}
    if proof_rows is None and not source_spines:
        return failures
    if not isinstance(proof_rows, list):
        return [f"{mode} Spine owner delegation evidence is absent"]
    proof_by_id = {}
    for proof in proof_rows:
        if not isinstance(proof, dict) or not isinstance(proof.get("sourceComponentId"), str):
            failures.append(f"{mode} Spine owner delegation row is malformed")
            continue
        source_id = proof["sourceComponentId"]
        if source_id in proof_by_id:
            failures.append(f"{mode} Spine owner delegation source ID repeats: {source_id}")
        if source_id not in source_spines:
            failures.append(f"{mode} Spine owner delegation has an extra source ID: {source_id}")
        proof_by_id[source_id] = proof
    graphics = queue_readback.get("graphics") or []
    graphics_by_id = {}
    for graphic in graphics:
        if isinstance(graphic, dict) and isinstance(graphic.get("sourceComponentId"), str):
            graphics_by_id.setdefault(graphic["sourceComponentId"], []).append(graphic)
    for source_id, source in source_spines.items():
        rows = graphics_by_id.get(source_id, [])
        proof = proof_by_id.get(source_id)
        generated_children = [row for row in rows if row.get("generatedSourceChild") is True]
        if proof is None:
            if generated_children and len(generated_children) == len(rows):
                failures.append(f"{mode} Spine generated-child-only draw lacks owner delegation proof: {source_id}")
            continue
        child_paths = proof.get("delegatedChildPaths")
        child_types = proof.get("delegatedChildGraphicTypes")
        child_vertices = proof.get("childMeshVertexCounts")
        child_submeshes = proof.get("childMeshSubmeshCounts")
        child_materials = proof.get("childCanvasMaterialCounts")
        child_texture_guids = proof.get("delegatedChildTextureGuids")
        child_material_guids = proof.get("delegatedChildMaterialGuids")
        count = len(child_paths) if isinstance(child_paths, list) else -1
        spine_stage = (plan or {}).get("spineNativeStage") or {}
        binding_plan = spine_native_bindings
        if binding_plan is None and isinstance(spine_stage.get("components"), list) and isinstance(spine_stage.get("dataAssets"), list):
            # Direct helper callers may provide a fully materialized stage in
            # their fixture. Production plans carry only summary pins and must
            # pass the SHA-verified candidate binding plan explicitly.
            binding_plan = spine_stage
        component_rows = (binding_plan or {}).get("components", {})
        data_rows = (binding_plan or {}).get("dataAssets", {})
        if isinstance(component_rows, dict):
            expected_component = component_rows.get(source_id)
        else:
            expected_components = [entry for entry in component_rows
                                   if isinstance(entry, dict) and entry.get("sourceComponentId") == source_id]
            expected_component = expected_components[0] if len(expected_components) == 1 else None
        expected_data = []
        if expected_component and expected_component.get("sourceDataAssetId"):
            if isinstance(data_rows, dict):
                data = data_rows.get(expected_component.get("sourceDataAssetId"))
                expected_data = [data] if data else []
            else:
                expected_data = [entry for entry in data_rows
                                 if isinstance(entry, dict) and entry.get("sourceAssetId") == expected_component.get("sourceDataAssetId")]
        stage_mapping_matches = (binding_plan is not None and expected_component is not None and len(expected_data) == 1 and
            (spec.get("sourcePrefabId") is None or expected_component.get("sourcePrefabId") == spec.get("sourcePrefabId")) and
            expected_component.get("sourceHasStaticDataReference") is True and
            proof.get("sourceDataAssetId") == expected_component.get("sourceDataAssetId") and
            proof.get("sourceDataAssetPath") == expected_data[0].get("skeletonDataAssetPath") and
            proof.get("sourceManifestSha256") == spine_stage.get("sourceManifestSha256"))
        if (proof.get("sourceNode") != source.get("node") or
                proof.get("sourceGraphicType") != "Spine.Unity.SkeletonGraphic" or
                proof.get("sourceIdentityComponentId") != source_id or
                not isinstance(proof.get("sourceDataAssetId"), str) or not proof["sourceDataAssetId"] or
                not isinstance(proof.get("sourceDataAssetPath"), str) or
                not proof["sourceDataAssetPath"].startswith("Assets/") or
                not _GUID.fullmatch(proof.get("sourceDataAssetGuid") or "") or
                proof.get("sourceBindingPlanPath") != "Assets/Game/Editor/Conversion/spine-native-binding-plan.json" or
                proof.get("sourceBindingPlanPath") != spine_stage.get("nativeBindingPlanPath") or
                proof.get("sourceBindingPlanSha256") != spine_stage.get("nativeBindingPlanSha256") or
                not _SHA.fullmatch(proof.get("sourceManifestSha256") or "") or
                (spine_stage and not stage_mapping_matches) or
                proof.get("rootMeshVertexCount") != 0 or proof.get("rootMeshDelegated") is not True or
                proof.get("sourceIdentityVerified") is not True or
                proof.get("sourceDataReferenceVerified") is not True or
                proof.get("childRendererListVerified") is not True or
                proof.get("childReferencesPersistent") is not True or
                proof.get("verified") is not True or count <= 0 or
                not all(isinstance(values, list) and len(values) == count for values in
                        (child_types, child_vertices, child_submeshes, child_materials,
                         child_texture_guids, child_material_guids))):
            failures.append(f"{mode} Spine owner/registered-renderer typed proof differs: {source_id}")
            continue
        if (any(value != "UnityEngine.UI.RawImage" for value in child_types) or
                any(type(value) is not int or value <= 0 for value in child_vertices) or
                any(value != 1 for value in child_submeshes) or any(value != 1 for value in child_materials) or
                any(not _GUID.fullmatch(value or "") for value in child_material_guids) or
                any(not _GUID.fullmatch(value or "") for value in child_texture_guids)):
            failures.append(f"{mode} Spine delegated child mesh/resource proof differs: {source_id}")
        if (len(rows) != count or len(generated_children) != count or
                any(row.get("generatedSourceChild") is not True or
                    row.get("nativeGraphicType") != "UnityEngine.UI.RawImage" or
                    row.get("sourceNode") != source.get("node") for row in rows) or
                [row.get("vertexCount") for row in rows] != child_vertices):
            failures.append(f"{mode} Spine child proxy rows do not cover delegated native renderers: {source_id}")
        if (type(proof.get("rootCanvasMaterialCount")) is not int or proof["rootCanvasMaterialCount"] < 0 or
                (proof.get("rootMeshWasMissing") is True and proof.get("rootMeshSubmeshCount") != -1) or
                (proof.get("rootMeshWasMissing") is False and type(proof.get("rootMeshSubmeshCount")) is not int)):
            failures.append(f"{mode} Spine owner root mesh/material diagnostics are malformed: {source_id}")
    return failures


def _check_spine_null_data_owners(spec, queue_readback, mode, plan=None, spine_native_bindings=None):
    expected_spine_rows = [row for key in ("renderers", "nonDrawRenderers") for row in spec.get(key, [])
                           if isinstance(row, dict) and row.get("sourceType") == "sp.Skeleton"]
    expected_spines = {row.get("sourceComponentId"): row for row in expected_spine_rows}
    if len(expected_spines) != len(expected_spine_rows):
        return [f"{mode} Spine source scope contains repeated component IDs"]
    if not expected_spines:
        rows = queue_readback.get("spineNullDataOwners")
        return [] if rows in (None, []) else [f"{mode} Spine source-null rows are outside the queue scope"]
    failures = []
    stage = (plan or {}).get("spineNativeStage") or {}
    rows = queue_readback.get("spineNullDataOwners")
    if not isinstance(rows, list):
        return [f"{mode} Spine source-null data owner evidence is absent"]
    if queue_readback.get("spineNullDataOwnersVerified") is not True:
        failures.append(f"{mode} Spine source-null data owner aggregate verification is false")
    plan_components = {row.get("sourceId"): row for row in (plan or {}).get("components", [])
                       if isinstance(row, dict) and row.get("type") == "sp.Skeleton"}
    native_component_map = (spine_native_bindings or {}).get("components", {})
    actual_by_id = {}

    def named_fields(value):
        if not isinstance(value, str):
            return None
        try:
            entries = json.loads(value)
        except (TypeError, ValueError):
            return None
        if not isinstance(entries, list) or any(not isinstance(entry, str) or "=" not in entry for entry in entries):
            return None
        result = {}
        for entry in entries:
            key, item = entry.split("=", 1)
            if not key or key in result:
                return None
            result[key] = item
        return result

    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("sourceComponentId"), str):
            failures.append(f"{mode} Spine source-null data owner row is malformed")
            continue
        source_id = row["sourceComponentId"]
        if source_id in actual_by_id:
            failures.append(f"{mode} Spine source-null data owner repeats: {source_id}")
        actual_by_id[source_id] = row
        expected = expected_spines.get(source_id)
        component = plan_components.get(source_id)
        native_component = native_component_map.get(source_id) if isinstance(native_component_map, dict) else None
        if expected is None or component is None:
            failures.append(f"{mode} Spine source-null data owner is outside the frozen source scope: {source_id}")
            continue
        source_fields = named_fields(row.get("sourceTargetFieldsJson"))
        native_expected_fields = named_fields(row.get("expectedFieldsJson"))
        native_actual_fields = named_fields(row.get("actualFieldsJson"))
        source_time_scale = row.get("sourceTimeScale")
        native_time_scale = row.get("nativeTimeScale")
        try:
            source_field_time_scale = float(source_fields["timeScale"]) if isinstance(source_fields, dict) else math.nan
            native_field_time_scale = float(native_expected_fields["timeScale"]) if isinstance(native_expected_fields, dict) else math.nan
        except (TypeError, ValueError):
            source_field_time_scale = native_field_time_scale = math.nan
        material_count = row.get("rootCanvasMaterialCount")
        material_modifiers = row.get("rootExtraMaterialModifierCount")
        material_base_default = row.get("rootSourceBaseDefaultMaterial")
        material_slot_matches = row.get("rootMaterialSlotMatchesGraphicRendering")
        material_default_only_expected = (material_count == 0 or
            material_count == 1 and material_base_default is True and material_slot_matches is True and
            material_modifiers == 0)
        root_mesh_empty = row.get("nativeRootMeshEmpty") is True
        root_default_quad = row.get("nativeRootMeshDefaultGraphicQuad") is True
        root_mesh_state_valid = root_mesh_empty != root_default_quad
        if root_mesh_empty:
            root_mesh_state_valid &= row.get("rootMeshVertexCount") == 0 and row.get("rootMeshIndexCount") == 0
        elif root_default_quad:
            geometry_evidence = row.get("rootMeshGeometryEvidence")
            root_mesh_state_valid &= (row.get("rootMeshVertexCount") == 4 and
                row.get("rootMeshSubmeshCount") == 1 and row.get("rootMeshIndexCount") == 6 and
                _SHA.fullmatch(row.get("rootMeshSha256") or "") is not None and
                isinstance(geometry_evidence, str) and all(token in geometry_evidence for token in
                    ("vertexCount=4", "submeshes=1", "indices=6", "triangleOrderExact=True", "rectCornersExact=True")) and
                material_count == 1)
        source_graphics = [graphic for graphic in queue_readback.get("graphics", [])
                           if isinstance(graphic, dict) and graphic.get("sourceComponentId") == source_id]
        source_null_carriers = [carrier for carrier in queue_readback.get("emptyRenderers", [])
                                if isinstance(carrier, dict) and carrier.get("sourceComponentId") == source_id]
        if root_mesh_state_valid:
            root_mesh_state_valid &= len(source_graphics) == 0 and len(source_null_carriers) == 1
            if len(source_null_carriers) == 1:
                carrier = source_null_carriers[0]
                if expected.get("sourceActive") is False:
                    # An inactive owner already has an exact serialized/hierarchy
                    # no-draw cause. Keep that cause distinct from the absent
                    # data proof above; do not require the carrier to relabel it
                    # as a source-data no-draw.
                    root_mesh_state_valid &= (
                        carrier.get("noDrawReason") == "source-node-inactive" and
                        carrier.get("sourceActive") is False and carrier.get("sourceEnabled") is expected.get("sourceEnabled") and
                        carrier.get("sourceActivityMatchesExpected") is True and
                        carrier.get("sourceNoDrawEvidenceVerified") is False and
                        carrier.get("sourceSpineNullDataProofVerified") is False and
                        carrier.get("sourceGraphicSuppressedByPresenter") is False and
                        carrier.get("sourceMeshPresent") is False and carrier.get("sourceMeshVertexCount") == 0 and
                        carrier.get("sourceCanvasMaterialCount") == 0)
                elif expected.get("sourceEnabled") is False:
                    root_mesh_state_valid &= (
                        carrier.get("noDrawReason") == "source-renderer-disabled" and
                        carrier.get("sourceActive") is True and carrier.get("sourceEnabled") is False and
                        carrier.get("sourceActivityMatchesExpected") is True and
                        carrier.get("nativeComponentEnabled") is False and
                        carrier.get("sourceGraphicSuppressedByPresenter") is False and
                        carrier.get("sourceMeshPresent") is False and carrier.get("sourceMeshVertexCount") == 0 and
                        carrier.get("sourceCanvasMaterialCount") == 0)
                else:
                    root_mesh_state_valid &= (
                        carrier.get("noDrawReason") == "source-spine-data-reference-absent-no-source-renderable-output" and
                        carrier.get("sourceNoDrawEvidenceVerified") is True and
                        carrier.get("sourceSpineNullDataProofVerified") is True and
                        carrier.get("sourceSpineNullDataRootFallbackQuad") is root_default_quad)
                    root_mesh_state_valid &= (
                        carrier.get("spineNullDataRootMeshSha256") == (row.get("rootMeshSha256") or "") and
                        carrier.get("sourceGraphicSuppressedByPresenter") is (mode == "loaded") and
                        (root_mesh_empty or carrier.get("sourceSpineNullDataRootFallbackQuad") is True))
        time_scale_contract_matches = (isinstance(source_fields, dict) and isinstance(native_expected_fields, dict) and
            isinstance(native_actual_fields, dict) and type(source_time_scale) in (int, float) and
            type(native_time_scale) in (int, float) and math.isfinite(source_time_scale) and math.isfinite(native_time_scale) and
            row.get("sourceTimeScaleVerified") is True and row.get("sourceIdentityTimeScaleVerified") is True and
            row.get("persistentVisiblePose") is True and math.isfinite(source_field_time_scale) and
            math.isfinite(native_field_time_scale) and source_field_time_scale == float(source_time_scale) and
            native_field_time_scale == float(native_time_scale) == 0.0 and
            native_expected_fields == native_actual_fields and
            all(source_fields[key] == native_actual_fields[key] for key in source_fields if key != "timeScale") and
            set(source_fields) == set(native_actual_fields))
        if ((spine_native_bindings is not None and
             (native_component is None or native_component.get("sourcePrefabId") != spec.get("sourcePrefabId") or
              native_component.get("sourceNodeId") != component.get("node") or
              native_component.get("sourceHasStaticDataReference") is not False or
              native_component.get("sourceDataAssetId") is not None or
              native_component.get("staticDataState") != "source_uuid_absent_component_preserved_unbound" or
              not _spine_source_binding_fields_match(source_fields, native_component))) or
                row.get("sourceNode") != expected.get("node") or component.get("node") != expected.get("node") or
                component.get("enabled") is not expected.get("sourceEnabled") or
                row.get("sourceStaticDataState") != "source_uuid_absent_component_preserved_unbound" or
                row.get("sourceBindingPlanPath") != "Assets/Game/Editor/Conversion/spine-native-source-binding-plan.json" or
                row.get("sourceBindingPlanSha256") != stage.get("sourceNativeBindingPlanSha256") or
                row.get("sourceManifestSha256") != stage.get("sourceManifestSha256") or
                row.get("sourceMaterialClosureStatus") != "no-serialized-skeleton-data-no-render-material-closure" or
                stage.get("sourceManifestSha256") != (plan or {}).get("sourceManifestSha256") or
                not isinstance(row.get("rootMaterialEvidence"), str) or not row["rootMaterialEvidence"] or
                row.get("sourceIdentityComponentId") != source_id or
                # JsonUtility materializes an absent source-plan string as its
                # default empty string, so this diagnostic may be false even
                # when the SHA-pinned plan maps sourceDataAssetId to null.
                # Preserve its typed value; the independent plan map plus the
                # native data-reference check establish the null semantics.
                row.get("sourceHasStaticDataReference") is not False or type(row.get("sourceDataAssetIdNull")) is not bool or
                row.get("sourcePlanVerified") is not True or row.get("sourceIdentityVerified") is not True or
                type(row.get("sourceNodeActive")) is not bool or
                row.get("sourceNodeInactive") is not (row.get("sourceNodeActive") is False) or
                row.get("sourceOwnerEnabled") is not expected.get("sourceEnabled") or
                row.get("sourceSerializedActive") is not expected.get("sourceActive") or
                row.get("sourceSerializedActiveVerified") is not True or
                row.get("sourceActivityStage") != ("loaded-hierarchy-plus-serialized-scope" if mode == "loaded" else "persistent-serialized-scope") or
                mode == "loaded" and row.get("sourceNodeActive") is not expected.get("sourceActive") or
                row.get("nativeDataReferenceNull") is not True or
                not root_mesh_state_valid or row.get("registeredRendererListEmpty") is not True or
                row.get("rootCanvasDefaultMaterialOnly") is not material_default_only_expected or
                row.get("mappedStaticFieldsVerified") is not True or row.get("sourceBehaviorBoundaryVerified") is not True or
                row.get("dynamicAssignmentUnverified") is not True or row.get("verified") is not True or
                type(row.get("rootMeshVertexCount")) is not int or row["rootMeshVertexCount"] < 0 or
                type(row.get("rootMeshSubmeshCount")) is not int or row["rootMeshSubmeshCount"] < -1 or
                type(row.get("rootMeshIndexCount")) is not int or row["rootMeshIndexCount"] < 0 or
                type(row.get("rootCanvasMaterialCount")) is not int or row["rootCanvasMaterialCount"] not in (0, 1) or
                type(row.get("rootExtraMaterialModifierCount")) is not int or row["rootExtraMaterialModifierCount"] < 0 or
                type(material_base_default) is not bool or type(material_slot_matches) is not bool or
                row.get("registeredRendererCount") != 0 or
                not time_scale_contract_matches):
            failures.append(f"{mode} Spine source-null component, field, plan-hash, or native empty-render proof differs: {source_id}")
    return failures


def _check_spine_empty_pose_owners(spec, queue_readback, mode, plan=None, spine_native_bindings=None):
    """Verify active Spine renderer events retained as evidence-backed fixed-pose no-draw rows."""
    failures = []
    renderer_specs = {row.get("sourceComponentId"): row for row in spec.get("renderers", [])
                      if isinstance(row, dict) and row.get("sourceType") == "sp.Skeleton"}
    empty_rows = queue_readback.get("emptyRenderers") or []
    expected = {}
    for row in empty_rows:
        if not isinstance(row, dict) or row.get("noDrawReason") != "source-spine-fixed-pose-no-renderable-attachments":
            continue
        sid = row.get("sourceComponentId")
        if not isinstance(sid, str) or sid in expected:
            failures.append(f"{mode} Spine empty-pose renderer marker is malformed or duplicated")
            continue
        expected[sid] = row
    rows = queue_readback.get("spineEmptyPoseOwners")
    if not isinstance(rows, list):
        return failures + ([f"{mode} Spine fixed-pose empty-render evidence is absent"] if expected else [])
    if queue_readback.get("spineEmptyPoseOwnersVerified") is not True:
        failures.append(f"{mode} Spine fixed-pose empty-render aggregate is not verified")
    stage = (plan or {}).get("spineNativeStage") or {}
    native_component_map = (spine_native_bindings or {}).get("components", {})
    native_data_map = (spine_native_bindings or {}).get("dataAssets", {})
    actual_by_id = {}

    def named_fields(value):
        if not isinstance(value, str):
            return None
        try:
            entries = json.loads(value)
        except (TypeError, ValueError):
            return None
        if not isinstance(entries, list) or any(not isinstance(entry, str) or "=" not in entry for entry in entries):
            return None
        result = {}
        for entry in entries:
            key, item = entry.split("=", 1)
            if not key or key in result:
                return None
            result[key] = item
        return result

    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("sourceComponentId"), str):
            failures.append(f"{mode} Spine fixed-pose owner row is malformed")
            continue
        sid = row["sourceComponentId"]
        if sid in actual_by_id:
            failures.append(f"{mode} Spine fixed-pose owner identity repeats: {sid}")
        actual_by_id[sid] = row
        renderer = renderer_specs.get(sid)
        marker = expected.get(sid)
        native_component = native_component_map.get(sid) if isinstance(native_component_map, dict) else None
        native_data = (native_data_map.get(native_component.get("sourceDataAssetId"))
                       if isinstance(native_data_map, dict) and native_component else None)
        source_fields = named_fields(row.get("sourceTargetFieldsJson"))
        expected_fields = named_fields(row.get("expectedFieldsJson"))
        actual_fields = named_fields(row.get("actualFieldsJson"))
        try:
            source_scale = float(row.get("sourceTimeScale"))
            native_scale = float(row.get("nativeTimeScale"))
            source_field_scale = float(source_fields["timeScale"]) if source_fields else math.nan
            native_field_scale = float(expected_fields["timeScale"]) if expected_fields else math.nan
        except (TypeError, ValueError, KeyError):
            source_scale = native_scale = source_field_scale = native_field_scale = math.nan
        fields_match = (isinstance(source_fields, dict) and isinstance(expected_fields, dict) and
            isinstance(actual_fields, dict) and source_fields.keys() == expected_fields.keys() == actual_fields.keys() and
            math.isfinite(source_scale) and math.isfinite(native_scale) and math.isfinite(source_field_scale) and
            math.isfinite(native_field_scale) and source_field_scale == source_scale and
            native_field_scale == native_scale == 0.0 and expected_fields == actual_fields and
            all(source_fields[key] == actual_fields[key] for key in source_fields if key != "timeScale"))
        skin_match = (row.get("actualSkin") == row.get("sourceSkin") or
            row.get("actualSkin") in (None, "") and row.get("defaultSkinRuntimeNull") is True and
            row.get("runtimeDefaultSkinName") == row.get("sourceSkin"))
        source_component = next((component for component in (plan or {}).get("components", [])
                                 if component.get("sourceId") == sid), None)
        if ((spine_native_bindings is not None and
             (native_component is None or native_data is None or source_component is None or
              native_component.get("sourcePrefabId") != spec.get("sourcePrefabId") or
              native_component.get("sourceHasStaticDataReference") is not True or
              native_component.get("sourceDataAssetId") != row.get("sourceDataAssetId") or
              native_component.get("sourceNodeId") != source_component.get("node") or
              native_data.get("skeletonDataAssetPath") != row.get("sourceDataAssetPath") or
              not _spine_source_binding_fields_match(source_fields, native_component))) or
                renderer is None or marker is None or row.get("sourceNode") != renderer.get("node") or
                marker.get("sourceNode") != renderer.get("node") or marker.get("sourceEnabled") is not True or
                marker.get("sourceActive") is not True or marker.get("actualQueueIndex", -1) < 0 or
                row.get("sourceHasStaticDataReference") is not True or
                not isinstance(row.get("sourceDataAssetId"), str) or not row["sourceDataAssetId"].startswith("spineAsset:") or
                not isinstance(row.get("sourceDataAssetPath"), str) or
                not row["sourceDataAssetPath"].startswith("Assets/Game/Content/Spine/") or
                not _GUID.fullmatch(row.get("sourceDataAssetGuid") or "") or
                row.get("sourceBindingPlanPath") != "Assets/Game/Editor/Conversion/spine-native-binding-plan.json" or
                row.get("sourceBindingPlanSha256") != stage.get("nativeBindingPlanSha256") or
                row.get("sourceManifestSha256") != stage.get("sourceManifestSha256") or
                row.get("sourceManifestSha256") != (plan or {}).get("sourceManifestSha256") or
                not skin_match or row.get("sourceSkinRuntimeVerified") is not True or
                type(row.get("defaultSkinRuntimeNull")) is not bool or
                row.get("sourceAnimation") != row.get("actualAnimation") or
                not isinstance(row.get("sourceSkin"), str) or not isinstance(row.get("sourceAnimation"), str) or
                row.get("actualTrackTime") != 0 or not fields_match or
                any(row.get(key) is not True for key in (
                    "sourcePlanVerified", "sourceIdentityVerified", "sourceDataReferenceVerified",
                    "sourceTimeScaleVerified", "sourceIdentityTimeScaleVerified", "persistentVisiblePose",
                    "sourceBusinessBehaviorDisabled", "mappedStaticFieldsVerified", "sdkPoseInitialized",
                    "sdkDataIdentityVerified", "fixedPoseVerified", "noDrawableAttachmentPoseVerified",
                    "rootMeshEmpty", "registeredRendererListEmpty", "helperReadbackVerified",
                    "presenterProofCardinalityVerified", "presenterOwnerReferenceVerified",
                    "presenterDataAssetReferenceVerified", "presenterSourceIdentityVerified",
                    "presenterSkinEvidenceVerified", "presenterFieldEvidenceVerified",
                    "storedCaptureProofVerified", "storedSkinRepresentationVerified", "loadedPoseVerified", "verified")) or
                row.get("sourceCallbacksExecuted") is not False or
                row.get("fixedPoseDrawableAttachmentCount") != 0 or
                type(row.get("fixedPoseSlotCount")) is not int or row["fixedPoseSlotCount"] <= 0 or
                type(row.get("fixedPoseAttachmentCount")) is not int or row["fixedPoseAttachmentCount"] < 0 or
                row.get("presentationInstructionCount") != 0 or row.get("presentationCanvasRendererCount") != 0 or
                row.get("rootMeshVertexCount") != 0 or
                type(row.get("rootMeshSubmeshCount")) is not int or row["rootMeshSubmeshCount"] > 0 or
                type(row.get("rootCanvasMaterialCount")) is not int or row["rootCanvasMaterialCount"] < 0 or
                row.get("registeredRendererCount") != 0 or
                marker.get("spineEmptyPoseProof", {}).get("sourceComponentId") != sid):
            failures.append(f"{mode} Spine fixed-pose source/data/fields/SDK no-draw evidence differs: {sid}")
    if set(actual_by_id) != set(expected):
        failures.append(f"{mode} Spine fixed-pose owner IDs differ: expected={sorted(expected)} actual={sorted(actual_by_id)}")
    return failures


def _check_spine_non_draw_children(spec, queue_readback, mode, plan=None):
    failures = []
    all_expected_rows = [row for row in spec.get("nonDrawRenderers", [])
                         if isinstance(row, dict) and row.get("sourceType") == "sp.Skeleton"]
    null_rows = queue_readback.get("spineNullDataOwners") or []
    null_ids = {row.get("sourceComponentId") for row in null_rows if isinstance(row, dict)}
    expected_rows = [row for row in all_expected_rows if row.get("sourceComponentId") not in null_ids]
    actual_rows = queue_readback.get("spineNonDrawChildren")
    if not expected_rows and actual_rows is None:
        return failures
    if not isinstance(actual_rows, list):
        return [f"{mode} Spine non-draw child evidence is absent"]
    expected_by_id = {row.get("sourceComponentId"): row for row in expected_rows}
    if len(expected_by_id) != len(expected_rows):
        failures.append(f"{mode} Spine non-draw spec identities repeat")
    all_expected_ids = {row.get("sourceComponentId") for row in all_expected_rows}
    source_renderer_ids = {row.get("sourceComponentId") for row in spec.get("renderers", [])
                           if isinstance(row, dict) and row.get("sourceType") == "sp.Skeleton"}
    if null_ids - all_expected_ids - source_renderer_ids:
        failures.append(f"{mode} Spine source-null owner set has extra identities")
    if null_ids & set(expected_by_id) and not all(
            (row.get("sourceStaticDataState") == "source_uuid_absent_component_preserved_unbound" and
             row.get("sourceDataAssetIdNull") is True) for row in null_rows
            if isinstance(row, dict) and row.get("sourceComponentId") in null_ids):
        failures.append(f"{mode} Spine source-null owner has no exact absent-data proof")
    actual_by_id = {}
    child_keys = set()
    for row in actual_rows:
        if not isinstance(row, dict) or not isinstance(row.get("sourceComponentId"), str):
            failures.append(f"{mode} Spine non-draw child row is malformed")
            continue
        sid = row["sourceComponentId"]
        actual_by_id.setdefault(sid, []).append(row)
        key = (sid, row.get("childPath"))
        if key in child_keys:
            failures.append(f"{mode} Spine non-draw child identity repeats: {sid}")
        child_keys.add(key)
        expected = expected_by_id.get(sid)
        if expected is None:
            failures.append(f"{mode} Spine non-draw child has an extra source ID: {sid}")
            continue
        if row.get("ownerOnlyNoRegisteredChildren") is True:
            reason = ("inactive-owner-no-registered-renderers" if expected.get("sourceActive") is False else
                      "disabled-owner-no-registered-renderers")
            owner_identity_ok = (
                row.get("sourceNode") == expected.get("node") and row.get("noDrawReason") == reason and
                row.get("sourceOwnerEnabled") is expected.get("sourceEnabled") and
                row.get("sourceNodeActive") is expected.get("sourceActive") and
                row.get("sourceIdentityComponentId") == sid and
                isinstance(row.get("sourceDataAssetId"), str) and row["sourceDataAssetId"].startswith("spineAsset:") and
                isinstance(row.get("sourceDataAssetPath"), str) and row["sourceDataAssetPath"].startswith("Assets/") and
                bool(_GUID.fullmatch(row.get("sourceDataAssetGuid") or "")) and
                row.get("sourceIdentityVerified") is True and row.get("sourceDataReferenceVerified") is True and
                row.get("registeredChildVerified") is True and row.get("childReferencePersistent") is True and
                row.get("verified") is True and row.get("ownerRendererListReadable") is True and
                row.get("ownerRendererListEmpty") is True and row.get("ownerRootMeshEmpty") is True and
                row.get("childNoDrawVerified") is True and row.get("currentOwnerRendererListReadable") is True and
                row.get("currentOwnerRendererListEmpty") is True and row.get("currentOwnerRootMeshEmpty") is True and
                row.get("ownerRootMeshCaptureAndCurrentFingerprintAbsent") is True and
                (expected.get("sourceActive") is False or expected.get("sourceEnabled") is False)
            )
            if not owner_identity_ok:
                failures.append(f"{mode} Spine empty registered-list owner identity/data/no-draw proof differs: {sid}")
            if (row.get("childPath") not in (None, "") or row.get("childGraphicType") not in (None, "") or
                    row.get("childMaterialGuid") not in (None, "") or row.get("childTextureGuid") not in (None, "") or
                    any(row.get(key) != -1 for key in
                        ("sourceChildMeshVertexCount", "sourceChildMeshSubmeshCount", "sourceChildMaterialCount"))):
                failures.append(f"{mode} Spine empty registered-list owner invents a child row: {sid}")
            for prefix in ("ownerRootMesh", "currentOwnerRootMesh"):
                root_vertices = row.get(prefix + "VertexCount")
                root_submeshes = row.get(prefix + "SubmeshCount")
                if (row.get(prefix + "IndexCount") != 0 or root_vertices not in (-1, 0) or
                        root_submeshes not in (-1, 0) or root_vertices == 0 and root_submeshes != 0 or
                        root_vertices == -1 and root_submeshes != -1):
                    failures.append(f"{mode} Spine {prefix} capture/current geometry is not empty: {sid}")
            if row.get("ownerRootCanvasMaterialCount") != 0 or row.get("currentOwnerRootCanvasMaterialCount") != 0:
                failures.append(f"{mode} Spine owner root renderer has a material: {sid}")
            if row.get("ownerRootMeshSha256") not in (None, "") or row.get("currentOwnerRootMeshSha256") not in (None, ""):
                failures.append(f"{mode} Spine empty owner root unexpectedly reports a mesh fingerprint: {sid}")
            continue
        reason = "inactive-source" if expected.get("sourceActive") is False else "disabled-source"
        identity_ok = (row.get("sourceNode") == expected.get("node") and row.get("noDrawReason") == reason and
            row.get("sourceOwnerEnabled") is expected.get("sourceEnabled") and
            row.get("sourceNodeActive") is expected.get("sourceActive") and
            row.get("sourceIdentityComponentId") == sid and
            isinstance(row.get("sourceDataAssetId"), str) and row["sourceDataAssetId"].startswith("spineAsset:") and
            isinstance(row.get("sourceDataAssetPath"), str) and row["sourceDataAssetPath"].startswith("Assets/") and
            bool(_GUID.fullmatch(row.get("sourceDataAssetGuid") or "")) and
            isinstance(row.get("childPath"), str) and bool(row["childPath"]) and
            row.get("childGraphicType") == "UnityEngine.UI.RawImage" and
            bool(_GUID.fullmatch(row.get("childMaterialGuid") or "")) and
            bool(_GUID.fullmatch(row.get("childTextureGuid") or "")) and
            row.get("sourceIdentityVerified") is True and row.get("sourceDataReferenceVerified") is True and
            row.get("registeredChildVerified") is True and row.get("childReferencePersistent") is True and
            row.get("verified") is True)
        if not identity_ok:
            failures.append(f"{mode} Spine non-draw owner/child source identity or resource proof differs: {sid}")
        source_enabled, source_active, source_active_self = (row.get("sourceChildEnabled"),
            row.get("sourceChildActiveInHierarchy"), row.get("sourceChildActiveSelf"))
        if (type(source_enabled) is not bool or type(source_active) is not bool or
                type(source_active_self) is not bool or row.get("targetChildEnabled") is not source_enabled or
                row.get("targetChildActiveInHierarchy") is not source_active):
            failures.append(f"{mode} Spine child target state differs from its typed source state: {sid}")
        safe_state = source_active is False if expected.get("sourceActive") is False else source_active is False or source_enabled is False
        if row.get("childNoDrawVerified") is not True or not safe_state:
            failures.append(f"{mode} Spine registered child can still draw under a no-draw owner: {sid}")
        if any(type(row.get(key)) is not int or row.get(key) < -1 for key in
               ("sourceChildMeshVertexCount", "sourceChildMeshSubmeshCount", "sourceChildMaterialCount")):
            failures.append(f"{mode} Spine non-draw child mesh/material diagnostics are malformed: {sid}")
    if set(actual_by_id) != set(expected_by_id):
        failures.append(f"{mode} Spine non-draw child owner denominator differs")
    if (set(actual_by_id) | null_ids) & all_expected_ids != all_expected_ids:
        failures.append(f"{mode} Spine non-draw child/source-null owner denominator differs")
    if set(actual_by_id) & null_ids:
        failures.append(f"{mode} Spine owner is incorrectly reported as both data-null and registered-child")
    if any(not rows for rows in actual_by_id.values()):
        failures.append(f"{mode} Spine non-draw child mapping is empty")
    return failures


def _empty_renderer_matches(expected, actual, mode):
    if not isinstance(actual, dict):
        return False
    source_type = expected.get("sourceType")
    expected_source_text = expected.get("sourceText", "")
    expected_native_text = expected.get("nativeTextExpectation", "")
    empty_label_text_proof = False
    if source_type in ("cc.Label", "cc.RichText") and expected.get("sourceTextEmpty") is True:
        empty_label_text_proof = (
            expected.get("sourceText") in (None, "") and expected.get("nativeTextExpectation") in (None, "") and
            actual.get("sourceText") in (None, "") and actual.get("nativeTextExpectation") in (None, "") and
            actual.get("sourceTextEmpty") is True and actual.get("nativeTextEmpty") is True and
            _empty_text_slot_enumeration_matches(expected, actual, mode)
        )
        if empty_label_text_proof:
            expected_source_text = expected_source_text or ""
            expected_native_text = expected_native_text or ""
    source_text_matches = actual.get("sourceText", "") == expected_source_text
    native_text_matches = actual.get("nativeTextExpectation", "") == expected_native_text
    if (actual.get("sourceNode") != expected.get("node") or
            actual.get("sourceType") != expected.get("sourceType") or
            actual.get("sourceComponentType") != expected.get("expectedGraphicType") or
            actual.get("sourceEnabled") is not expected.get("sourceEnabled") or
            actual.get("sourceActive") is not expected.get("sourceActive") or
            type(actual.get("sourceActiveSelf")) is not bool or
            type(actual.get("sourceSerializedActive")) is not bool or
            actual.get("sourceSerializedActiveVerified") is not True or
            actual.get("sourceSerializedActive") is not expected.get("sourceActive") or
            actual.get("sourceActivityMatchesExpected") is not True or
            type(actual.get("sourceActiveInHierarchy")) is not bool or
            type(actual.get("sourceHierarchyActiveMatchesExpected")) is not bool or
            actual.get("sourceHierarchyActiveMatchesExpected") is not
                (actual.get("sourceActiveInHierarchy") is expected.get("sourceActive")) or
            actual.get("sourceTextureBound") is not expected.get("sourceTextureBound", False) or
            not source_text_matches or not native_text_matches or
            actual.get("sourceTextEmpty") is not expected.get("sourceTextEmpty", False) or
            actual.get("sourceFontMissing") is not expected.get("sourceFontMissing", False) or
            actual.get("sourceReferenceVerified") is not True or actual.get("typedFieldsVerified") is not True or
            actual.get("carrierPresent") is not True or actual.get("verified") is not True):
        return False
    expected_activity_stage = "persistent-serialized-scope" if mode == "persistent" else "loaded-hierarchy-plus-serialized-scope"
    if actual.get("sourceActivityStage") != expected_activity_stage:
        return False
    if mode == "loaded" and (actual.get("sourceActiveInHierarchy") is not expected.get("sourceActive") or
                              actual.get("sourceHierarchyActiveMatchesExpected") is not True):
        return False
    if mode == "persistent":
        if (actual.get("carrierAssetIdentityVerified") is not True or
                not _GUID.fullmatch(actual.get("carrierGuid") or "") or
                type(actual.get("carrierLocalFileId")) is not int or actual.get("carrierLocalFileId") == 0):
            return False
    elif mode == "loaded":
        if (actual.get("carrierOwnerScopeVerified") is not True or actual.get("carrierGuid", "") not in (None, "") or
                type(actual.get("carrierLocalFileId")) is not int or actual.get("carrierLocalFileId") != 0):
            return False
    else:
        return False
    source_type = expected.get("sourceType")
    empty_pose_proof = actual.get("spineEmptyPoseProof")
    if actual.get("noDrawReason") != "source-spine-fixed-pose-no-renderable-attachments" and not _empty_spine_pose_placeholder(empty_pose_proof):
        return False
    if expected.get("sourceActive") is False:
        if actual.get("noDrawReason") != "source-node-inactive":
            return False

        if source_type == "cc.Sprite":
            return (actual.get("nativeTextureBound") is expected.get("sourceTextureBound") and
                    actual.get("nativeGraphicEnabled") is (expected.get("sourceEnabled") is True and
                                                            expected.get("sourceTextureBound") is True))
        if source_type in ("cc.Label", "cc.RichText"):
            return (actual.get("nativeGraphicEnabled") is expected.get("sourceEnabled") and
                    actual.get("nativeText") == expected_native_text and
                    actual.get("nativeFontMissing") is expected.get("sourceFontMissing"))
        if source_type == "cc.Graphics":
            return (actual.get("sourceCommandsEmpty") is True and actual.get("nativeCommandsEmpty") is True and
                    actual.get("sourceFieldsSha256") == expected.get("sourceFieldsSha256") and
                    actual.get("sourceDrawingCommands") == expected.get("sourceDrawingCommands") and
                    actual.get("sourceMaterialGuids") == expected.get("sourceMaterialGuids") and
                    actual.get("actualSourceMaterialGuids") == expected.get("sourceMaterialGuids"))
        return actual.get("nativeComponentEnabled") is expected.get("sourceEnabled")
    if expected.get("sourceEnabled") is False:
        if source_type in ("cc.Label", "cc.RichText"):
            return (actual.get("nativeComponentEnabled") is False and
                    actual.get("nativeText") == expected_native_text and
                    actual.get("nativeFontMissing") is expected.get("sourceFontMissing") and
                    actual.get("noDrawReason") == "source-renderer-disabled")
        return actual.get("nativeComponentEnabled") is False and actual.get("noDrawReason") == "source-renderer-disabled"
    if source_type == "cc.Sprite":
        common_null_sprite = (expected.get("sourceEnabled") is True and expected.get("sourceTextureBound") is False and
                              actual.get("nativeGraphicEnabled") is False and actual.get("nativeTextureBound") is False)
        zero_mesh = (actual.get("sourceMeshPresent") is False and actual.get("sourceMeshVertexCount") == 0 and
                     actual.get("noDrawReason") == "source-sprite-frame-null-native-image-disabled-zero-mesh")
        no_material = (actual.get("sourceCanvasMaterialCount") == 0 and
                       actual.get("noDrawReason") == "source-sprite-frame-null-native-image-disabled-no-material")
        return common_null_sprite and (zero_mesh or no_material)
    if source_type == "sp.Skeleton" and expected.get("sourceActive") is True and expected.get("sourceEnabled") is True:
        if actual.get("noDrawReason") == "source-spine-fixed-pose-no-renderable-attachments":
            proof = actual.get("spineEmptyPoseProof")
            return (isinstance(proof, dict) and proof.get("verified") is True and
                    proof.get("sourceComponentId") == actual.get("sourceComponentId") and
                    actual.get("nativeGraphicEnabled") is True and actual.get("nativeComponentEnabled") is True and
                    actual.get("sourceMeshPresent") is False and actual.get("sourceMeshVertexCount") == 0 and
                    type(actual.get("sourceCanvasMaterialCount")) is int and actual["sourceCanvasMaterialCount"] >= 0)
        if actual.get("noDrawReason") == "source-spine-data-reference-absent-no-source-renderable-output":
            fallback_quad = actual.get("sourceSpineNullDataRootFallbackQuad") is True
            fallback_hash_valid = isinstance(actual.get("spineNullDataRootMeshSha256"), str) and \
                re.fullmatch(r"[a-f0-9]{64}", actual["spineNullDataRootMeshSha256"]) is not None
            mesh_state_valid = (
                fallback_hash_valid and (
                    actual.get("sourceMeshPresent") is True and actual.get("sourceMeshVertexCount") == 4 and
                    actual.get("sourceCanvasMaterialCount") == 1 or
                    actual.get("sourceSpineNullDataRootMeshCacheAbsent") is True and
                    actual.get("sourceMeshPresent") is False and actual.get("sourceMeshVertexCount") == 0 and
                    actual.get("sourceCanvasMaterialCount") in (0, 1) and
                    (actual.get("sourceCanvasMaterialCount") == 0 or
                     actual.get("sourceSpineNullDataCurrentDefaultMaterialOnly") is True)
                )
            ) if fallback_quad else (
                actual.get("sourceMeshPresent") is False and actual.get("sourceMeshVertexCount") == 0 and
                actual.get("sourceCanvasMaterialCount") in (0, 1) and
                (actual.get("sourceCanvasMaterialCount") == 0 or
                 actual.get("sourceSpineNullDataCurrentDefaultMaterialOnly") is True) and
                actual.get("spineNullDataRootMeshSha256") in (None, "")
            )
            return (actual.get("nativeGraphicEnabled") is True and actual.get("nativeComponentEnabled") is True and
                    actual.get("sourceSpineNullDataProofVerified") is True and mesh_state_valid and
                    (mode == "persistent" and actual.get("sourceGraphicSuppressedByPresenter") is False or
                     mode == "loaded" and actual.get("sourceGraphicSuppressedByPresenter") is True))
        return False
    if source_type in ("cc.Label", "cc.RichText") and expected.get("sourceEnabled") is True:
        return (expected.get("sourceTextEmpty") is True and
                _empty_text_slot_enumeration_matches(expected, actual, mode) and
                actual.get("nativeTextEmpty") is True and
                actual.get("nativeText") == expected_native_text and
                actual.get("nativeGraphicEnabled") is True and actual.get("sourceMeshPresent") is False and
                actual.get("sourceMeshVertexCount") == 0 and actual.get("nativeFontMissing") is expected.get("sourceFontMissing") and
                actual.get("noDrawReason") == "source-text-empty-zero-mesh")
    if source_type == "cc.Graphics":
        expected_materials = expected.get("sourceMaterialGuids") or []
        return (expected.get("sourceCommandsEmpty") is True and actual.get("sourceCommandsEmpty") is True and
                actual.get("nativeCommandsEmpty") is True and actual.get("nativeComponentEnabled") is False and
                actual.get("sourceFieldsSha256") == expected.get("sourceFieldsSha256") and
                actual.get("sourceDrawingCommands") == expected.get("sourceDrawingCommands") and
                actual.get("sourceMaterialGuids") == expected_materials and
                actual.get("actualSourceMaterialGuids") == expected_materials and
                actual.get("noDrawReason") == "source-graphics-command-stream-proven-empty")
    return expected.get("sourceEnabled") is False and actual.get("nativeComponentEnabled") is False and actual.get("noDrawReason") == "source-renderer-disabled"


def _empty_text_slot_row_hash(row):
    def boolean(value):
        return "True" if value is True else "False" if value is False else str(value)

    fields = (
        row.get("slot"), row.get("characterReferences"), row.get("visibleCharacterReferences"),
        boolean(row.get("textInfoMaterialMissing")), row.get("textInfoVertexCount"),
        row.get("textInfoTriangleIndexCount"), row.get("textInfoNondegenerateTriangleCount"),
        row.get("canvasVertexCount"), row.get("canvasTriangleIndexCount"),
        row.get("canvasNondegenerateTriangleCount"), row.get("disposition"), row.get("sourceAssetKind"),
        f'{row.get("sourceAssetGuid") or ""}:{row.get("sourceAssetLocalFileId")}',
        f'{row.get("atlasGuid") or ""}:{row.get("atlasLocalFileId")}',
        row.get("textInfoMaterialFingerprint") or "", row.get("sourceGraphicMaterialFingerprint") or "",
        row.get("characterEvidenceSha256") or "", row.get("characterAssetEvidenceSha256") or "",
        row.get("sourceMeshSha256") or "",
    )
    return hashlib.sha256("|".join(str(value) for value in fields).encode("utf-8")).hexdigest()


def _valid_empty_text_slot_enumeration(value, source_id, text_hash):
    if (not isinstance(value, dict) or value.get("verified") is not True or
            value.get("sourceComponentId") != source_id or value.get("sourceTextSha256") != text_hash or
            type(value.get("slotCount")) is not int or value["slotCount"] <= 0 or
            not isinstance(value.get("rows"), list) or len(value["rows"]) != value["slotCount"] or
            not _SHA.fullmatch(value.get("evidenceSha256") or "")):
        return False
    row_hashes = []
    for index, row in enumerate(value["rows"]):
        if (not isinstance(row, dict) or row.get("slot") != index or row.get("disposition") != "empty-placeholder" or
                type(row.get("characterReferences")) is not int or row["characterReferences"] != 0 or
                type(row.get("visibleCharacterReferences")) is not int or row["visibleCharacterReferences"] != 0 or
                type(row.get("textInfoNondegenerateTriangleCount")) is not int or row["textInfoNondegenerateTriangleCount"] != 0 or
                type(row.get("canvasNondegenerateTriangleCount")) is not int or row["canvasNondegenerateTriangleCount"] != 0 or
                row.get("sourceAssetKind") not in ("font", "sprite") or
                not _GUID.fullmatch(row.get("sourceAssetGuid") or "") or
                type(row.get("sourceAssetLocalFileId")) is not int or row["sourceAssetLocalFileId"] == 0 or
                not _GUID.fullmatch(row.get("atlasGuid") or "") or
                type(row.get("atlasLocalFileId")) is not int or row["atlasLocalFileId"] == 0 or
                any(not _SHA.fullmatch(row.get(key) or "") for key in
                    ("characterEvidenceSha256", "characterAssetEvidenceSha256", "evidenceSha256")) or
                row.get("evidenceSha256") != _empty_text_slot_row_hash(row)):
            return False
        row_hashes.append(row["evidenceSha256"])
    expected_hash = hashlib.sha256((value["sourceComponentId"] + "|" + value["sourceTextSha256"] + "|" +
                                    str(value["slotCount"]) + "|" + "|".join(row_hashes)).encode("utf-8")).hexdigest()
    return value["evidenceSha256"] == expected_hash


def _empty_text_slot_enumeration_matches(expected, actual, mode):
    source_id = expected.get("sourceComponentId")
    raw_source_text = expected.get("sourceText")
    native_expectation = expected.get("nativeTextExpectation")
    source_text = actual.get("sourceText")
    if (raw_source_text not in (None, "") or native_expectation not in (None, "") or
            source_text not in (None, "") or actual.get("sourceTextEmpty") is not True):
        return False
    proof = actual.get("emptyTextSlotEnumerationProof")
    if (actual.get("emptyTextSlotEnumerationVerified") is not True or not isinstance(proof, dict) or
            proof.get("verified") is not True or proof.get("ownerScopeVerified") is not True or
            proof.get("persistentReferencesVerified") is not True or proof.get("sourceComponentId") != source_id):
        return False
    text_hash = hashlib.sha256((source_text or "").encode("utf-8")).hexdigest()
    saved = proof.get("slotEnumeration")
    if not _valid_empty_text_slot_enumeration(saved, source_id, text_hash):
        return False
    current = proof.get("currentSlotEnumeration")
    if mode == "persistent":
        if current in (None, {}):
            return True
        default_fields = {"sourceComponentId", "sourceTextSha256", "slotCount", "verified", "evidenceSha256", "rows"}
        return (isinstance(current, dict) and set(current) == default_fields and
                current.get("sourceComponentId") == "" and current.get("sourceTextSha256") == "" and
                type(current.get("slotCount")) is int and current.get("slotCount") == 0 and
                current.get("verified") is False and current.get("evidenceSha256") == "" and
                current.get("rows") == [])
    if mode == "loaded":
        return (_valid_empty_text_slot_enumeration(current, source_id, text_hash) and
                current.get("evidenceSha256") == saved.get("evidenceSha256"))
    return False


def _empty_spine_pose_placeholder(value):
    """Only JsonUtility's all-default inline-class null placeholder is valid off Spine empty-pose rows."""
    if value is None or value == {}:
        return True
    if not isinstance(value, dict):
        return False
    string_fields = (
        "sourceComponentId", "sourceNode", "sourceDataAssetId", "sourceDataAssetPath", "sourceDataAssetGuid",
        "sourceBindingPlanPath", "sourceBindingPlanSha256", "sourceManifestSha256", "sourceSkin", "sourceAnimation",
        "actualSkin", "runtimeDefaultSkinName", "actualAnimation", "sourceTargetFieldsJson", "expectedFieldsJson",
        "actualFieldsJson",
    )
    boolean_fields = (
        "sourceHasStaticDataReference", "sourcePlanVerified", "sourceIdentityVerified", "sourceDataReferenceVerified",
        "sourceTimeScaleVerified", "sourceIdentityTimeScaleVerified", "persistentVisiblePose",
        "sourceBusinessBehaviorDisabled", "sourceCallbacksExecuted", "mappedStaticFieldsVerified", "sdkPoseInitialized",
        "sdkDataIdentityVerified", "sourceSkinRuntimeVerified", "defaultSkinRuntimeNull", "fixedPoseVerified",
        "noDrawableAttachmentPoseVerified", "rootMeshEmpty", "registeredRendererListEmpty", "helperReadbackVerified", "verified",
        "presenterFound", "presenterProofCardinalityVerified", "presenterOwnerReferenceVerified",
        "presenterDataAssetReferenceVerified", "presenterSourceIdentityVerified", "presenterSkinEvidenceVerified",
        "presenterFieldEvidenceVerified", "storedCaptureProofVerified", "storedSkinRepresentationVerified", "loadedPoseVerified",
        "currentOwnerPresent", "currentOwnerTypeMatches", "currentOwnerEnabledMatches",
        "currentOwnerReferenceMatchesStored", "currentOwnerNodeMappingMatches", "currentSourceIdentityMatches",
        "currentSourceSerializedActivityVerified", "currentSourceSerializedActivityMatchesExpected",
        "currentSourceHierarchyActivityMatchesExpected", "currentDataAssetPresent",
        "currentDataAssetReferenceMatchesStored", "currentDataAssetIdentityVerified",
        "currentDataAssetIdMatchesStored", "currentDataAssetPathMatchesStored", "currentDataAssetGuidMatchesStored",
        "currentBindingPlanPathMatchesStored", "currentBindingPlanHashMatchesStored", "currentManifestMatchesStored",
        "currentOwnerEnabled", "expectedOwnerEnabled", "sourceSerializedEffectiveActive",
        "expectedSerializedEffectiveActive", "sourceHierarchyActive", "expectedHierarchyActive",
    )
    count_fields = (
        "fixedPoseSlotCount", "fixedPoseAttachmentCount", "fixedPoseDrawableAttachmentCount",
        "presentationInstructionCount", "presentationCanvasRendererCount", "rootMeshVertexCount",
        "rootMeshSubmeshCount", "rootCanvasMaterialCount", "registeredRendererCount",
        "presenterProofArrayLength", "presenterMatchingProofCount",
    )
    string_fields = string_fields + (
        "diagnostic", "currentOwnerType", "currentOwnerIdentityComponentId", "currentSourceIdentityComponentType",
        "currentDataAssetType", "currentDataAssetPath", "currentDataAssetGuid", "currentDataAssetId",
        "currentBindingPlanPath", "currentBindingPlanSha256", "currentSourceManifestSha256",
    )
    float_fields = ("sourceTimeScale", "nativeTimeScale", "actualTrackTime")
    expected_keys = set(string_fields + boolean_fields + count_fields + float_fields)
    return (set(value) == expected_keys and all(value.get(key) == "" for key in string_fields) and
            all(value.get(key) is False for key in boolean_fields) and
            all(type(value.get(key)) is int and value.get(key) == 0 for key in count_fields) and
            all(type(value.get(key)) in (int, float) and value.get(key) == 0 for key in float_fields))


_BLOCK_INPUT_GRAPHIC_TYPES = {
    "cc.Sprite": "UnityEngine.UI.Image",
    "cc.Label": "TMPro.TextMeshProUGUI",
    "cc.RichText": "TMPro.TextMeshProUGUI",
    "sp.Skeleton": "Spine.Unity.SkeletonGraphic",
}


def _check_block_input_events(spec, row, mode, plan):
    failures = []
    declared = spec.get("sourceBlockInputEvents")
    actual = row.get("blockInputEvents")
    components = plan.get("components") if isinstance(plan, dict) else None
    if (declared is not None and not isinstance(declared, list)) or not isinstance(actual, list) or not isinstance(components, list):
        return [f"{mode} BlockInputEvents typed rows or source component plan are absent"]
    scope_nodes = {spec.get("rootScope")}
    for child_row in spec.get("sourceChildOrder") or []:
        if not isinstance(child_row, dict):
            failures.append(f"{mode} BlockInputEvents source child scope is malformed")
            continue
        scope_nodes.add(child_row.get("node"))
        scope_nodes.update(child_row.get("children") or [])
    source_blocks = [component for component in components if isinstance(component, dict) and
                     component.get("type") == "cc.BlockInputEvents" and component.get("node") in scope_nodes]
    source_ids = [component.get("sourceId") for component in source_blocks]
    if (len(source_ids) != len(set(source_ids)) or
            any(not isinstance(source_id, str) or not source_id for source_id in source_ids)):
        failures.append(f"{mode} source BlockInputEvents IDs are missing or duplicated")
    actual_by_id = {item.get("sourceComponentId"): item for item in actual if isinstance(item, dict)}
    if (len(actual_by_id) != len(actual) or
            len(source_ids) != len(source_blocks) or
            set(actual_by_id) != set(source_ids)):
        failures.append(f"{mode} BlockInputEvents source/native denominator differs")
    parent_by_node = {}
    for item in spec.get("sourceChildOrder") or []:
        if not isinstance(item, dict):
            continue
        for child in item.get("children") or []:
            if child in parent_by_node:
                failures.append(f"{mode} BlockInputEvents source node has duplicate parent: {child}")
            parent_by_node[child] = item.get("node")
    active_self = {item.get("node"): item.get("active") for item in spec.get("sourceNodeActive") or []
                   if isinstance(item, dict)}

    def effective_active(node):
        seen = set()
        cursor = node
        while cursor:
            if cursor in seen or active_self.get(cursor) is not True:
                return False
            seen.add(cursor)
            if cursor == spec.get("rootScope"):
                return True
            cursor = parent_by_node.get(cursor)
        return False

    for component in source_blocks:
        source_id, node = component.get("sourceId"), component.get("node")
        actual_row = actual_by_id.get(source_id)
        graphic_components = [item for item in components if isinstance(item, dict) and
                              item.get("node") == node and item.get("convertible") is True and
                              item.get("type") in _BLOCK_INPUT_GRAPHIC_TYPES]
        if len(graphic_components) > 1:
            failures.append(f"{mode} BlockInputEvents source Graphic mapping is ambiguous: {source_id}")
            continue
        graphic = graphic_components[0] if graphic_components else None
        expected_graphic_id = graphic.get("sourceId") if graphic else None
        expected_graphic_type = _BLOCK_INPUT_GRAPHIC_TYPES.get(graphic.get("type")) if graphic else None
        source_active = effective_active(node)
        expected_fields = {
            "sourceComponentId": source_id, "sourceType": "cc.BlockInputEvents",
            "sourceEnabled": component.get("enabled"), "sourceActive": source_active,
            "expectedSourceGraphicComponentId": expected_graphic_id,
            "expectedSourceGraphicType": expected_graphic_type,
        }
        expected_fields["node"] = node
        if isinstance(declared, list):
            declared_rows = [item for item in declared if isinstance(item, dict) and item.get("sourceComponentId") == source_id]
            if len(declared_rows) != 1 or any(declared_rows[0].get(key) != value for key, value in expected_fields.items()):
                failures.append(f"{mode} BlockInputEvents plan projection differs from source components: {source_id}")
        if not isinstance(actual_row, dict):
            failures.append(f"{mode} BlockInputEvents native row identity differs: {source_id}")
            continue
        actual_fields = {key: value for key, value in expected_fields.items() if key not in (
            "sourceType", "node", "expectedSourceGraphicComponentId", "expectedSourceGraphicType")}
        expected_graphic_identity_matches = (
            actual_row.get("expectedSourceGraphicComponentId") in (None, "") if expected_graphic_id is None
            else actual_row.get("expectedSourceGraphicComponentId") == expected_graphic_id)
        expected_graphic_type_matches = (
            actual_row.get("expectedSourceGraphicType") in (None, "") if expected_graphic_type is None
            else actual_row.get("expectedSourceGraphicType") == expected_graphic_type)
        if (actual_row.get("sourceNode") != node or
                any(actual_row.get(key) != value for key, value in actual_fields.items()) or
                not expected_graphic_identity_matches or not expected_graphic_type_matches):
            failures.append(f"{mode} BlockInputEvents native row identity differs: {source_id}")
            continue
        owns_surface = graphic is None
        expected_active_self = active_self.get(node)
        inactive_source = source_active is False or component.get("enabled") is False
        actual_activity_matches = (actual_row.get("sourceActiveSelf") is expected_active_self and
            type(actual_row.get("sourceActiveInHierarchy")) is bool and
            (mode != "loaded" or actual_row.get("sourceActiveInHierarchy") is source_active))
        if (actual_row.get("sourceReferenceVerified") is not True or
                not actual_activity_matches or
                actual_row.get("sourceSerializedActiveVerified") is not True or
                actual_row.get("sourceSerializedActive") is not source_active or
                actual_row.get("sourceHierarchyActiveMatchesExpected") is not True or
                actual_row.get("blockerPresent") is not True or actual_row.get("blockerUnique") is not True or
                actual_row.get("blockerEnabledMatches") is not True or
                actual_row.get("surfaceReferenceVerified") is not True or
                actual_row.get("surfaceOwnerMatches") is not True or
                actual_row.get("surfaceOwnedMatches") is not True or
                actual_row.get("surfaceEnabledMatches") is not True or
                actual_row.get("surfaceRaycastMatches") is not True or
                actual_row.get("surfaceImplementationVerified") is not True or
                actual_row.get("verified") is not True):
            failures.append(f"{mode} BlockInputEvents actual typed reference/state proof differs: {source_id}")
        if owns_surface:
            if actual_row.get("surfaceType") != "NativeInputBlockerSurface":
                failures.append(f"{mode} owned BlockInputEvents surface is not the exact clear-alpha typed surface: {source_id}")
            if inactive_source:
                if (actual_row.get("sourceNoDrawStateVerified") is not True or
                        actual_row.get("surfaceEnabledActual") is not False or
                        actual_row.get("surfaceRaycastActual") is not False):
                    failures.append(f"{mode} inactive/disabled BlockInputEvents surface is not actually disabled and non-raycast: {source_id}")
            elif mode == "loaded" and (actual_row.get("sourceNoDrawStateVerified") is not False or
                                      actual_row.get("surfaceMeshDeferred") is not False or
                                      actual_row.get("clearAlphaMeshVerified") is not True or
                                      actual_row.get("surfaceMeshVertexCount") != 4 or
                                      actual_row.get("surfaceMeshIndexCount") != 6):
                failures.append(f"loaded BlockInputEvents surface mesh is not a clear-alpha quad: {source_id}")
            if not inactive_source and mode == "persistent" and actual_row.get("surfaceMeshDeferred") is True and (
                    actual_row.get("clearAlphaMeshVerified") is True or
                    actual_row.get("surfaceMeshVertexCount") != -1 or actual_row.get("surfaceMeshIndexCount") != 0):
                failures.append(f"persistent BlockInputEvents incorrectly claims a deferred mesh was measured: {source_id}")
            if not inactive_source and mode == "persistent" and actual_row.get("surfaceMeshDeferred") is False and (
                    actual_row.get("clearAlphaMeshVerified") is not True or
                    actual_row.get("surfaceMeshVertexCount") != 4 or actual_row.get("surfaceMeshIndexCount") != 6):
                failures.append(f"persistent BlockInputEvents surface mesh evidence is malformed: {source_id}")
        elif actual_row.get("surfaceType") != expected_graphic_type or actual_row.get("surfaceOwnedMatches") is not True:
            failures.append(f"{mode} reused BlockInputEvents Graphic was incorrectly treated as input-only: {source_id}")
    if row.get("sourceBlockInputEventsVerified") is not True:
        failures.append(f"{mode} BlockInputEvents native aggregate proof is false")
    if isinstance(declared, list):
        declared_ids = [item.get("sourceComponentId") for item in declared if isinstance(item, dict)]
        if len(declared_ids) != len(declared) or len(set(declared_ids)) != len(declared_ids) or set(declared_ids) != set(source_ids):
            failures.append(f"{mode} BlockInputEvents native DTO denominator differs from plan components")
    return failures


def _check_source_mask_identities(spec, row, mode, plan):
    failures = []
    all_masks = plan.get("staticMasks", {}).get("masks") if isinstance(plan, dict) else None
    actual = row.get("sourceMaskIdentities")
    if not isinstance(all_masks, list) or not isinstance(actual, list):
        return [f"{mode} source Mask identity evidence is absent"]
    scope_nodes = {spec.get("rootScope")}
    for item in spec.get("sourceChildOrder") or []:
        if isinstance(item, dict):
            scope_nodes.add(item.get("node"))
            scope_nodes.update(item.get("children") or [])
    expected_rows = [item for item in all_masks if isinstance(item, dict) and item.get("node") in scope_nodes]
    expected_ids = [item.get("sourceId") for item in expected_rows]
    actual_by_id = {item.get("sourceId"): item for item in actual if isinstance(item, dict)}
    actual_ids = [item.get("sourceId") for item in actual if isinstance(item, dict)]
    if (len(expected_ids) != len(set(expected_ids)) or len(actual_ids) != len(actual) or
            len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != set(expected_ids)):
        failures.append(f"{mode} source Mask identity denominator is missing, duplicated, or extra")
    parent_by_node = {}
    for item in spec.get("sourceChildOrder") or []:
        if not isinstance(item, dict):
            continue
        for child in item.get("children") or []:
            if child in parent_by_node:
                failures.append(f"{mode} source Mask node has duplicate source parent: {child}")
            parent_by_node[child] = item.get("node")
    active_self = {item.get("node"): item.get("active") for item in spec.get("sourceNodeActive") or []
                   if isinstance(item, dict)}

    def effective_active(node):
        cursor, seen = node, set()
        while cursor:
            if cursor in seen or active_self.get(cursor) is not True:
                return False
            seen.add(cursor)
            if cursor == spec.get("rootScope"):
                return True
            cursor = parent_by_node.get(cursor)
        return False

    source_fields = ("sourceFieldsJson", "spriteFrameUuid", "sourceMaterialId", "resolvedSourceMaterialId", "sourceEffectId",
                     "sourceEffectName", "sourceEffectDocumentSha256", "unityMaskMaterialGuid",
                     "unityMaskShaderPath", "unityMaskShaderSha256")
    optional_source_fields = {"spriteFrameUuid", "unityMaskMaterialGuid", "unityMaskShaderPath", "unityMaskShaderSha256"}
    for expected in expected_rows:
        source_id, node = expected.get("sourceId"), expected.get("node")
        actual_row = actual_by_id.get(source_id)
        if not isinstance(actual_row, dict):
            continue
        active = effective_active(node)
        self_active = active_self.get(node)
        source_fields_match = all(
            (actual_row.get(key) in (None, "") if key in optional_source_fields and expected.get(key) in (None, "")
             else actual_row.get(key) == expected.get(key))
            for key in source_fields)
        expected_graphic_type = ("Monkey.StaticMaskSort.NativeStaticInvertedMaskGraphic" if expected.get("inverted") else
                                 "UnityEngine.UI.Image") if expected.get("maskType") == 0 else (
                                 "Monkey.StaticMaskSort.NativeStaticEllipseMaskGraphic" if expected.get("maskType") == 1 else
                                 "UnityEngine.UI.Image")
        if (actual_row.get("node") != node or
                not source_fields_match or
                actual_row.get("nativeId") != expected.get("nativeId") or
                actual_row.get("sourceMaskType") != expected.get("maskType") or
                actual_row.get("sourceEnabled") is not expected.get("enabled") or
                actual_row.get("sourceInverted") is not expected.get("inverted") or
                actual_row.get("sourceActiveSelfExpected") is not self_active or
                actual_row.get("sourceActiveExpected") is not active):
            failures.append(f"{mode} source Mask component/node/fields differ: {source_id}")
        if (actual_row.get("nativeMaskType") != "UnityEngine.UI.Mask" or
                actual_row.get("graphicType") != expected_graphic_type or
                actual_row.get("sourceMaskType") != expected.get("maskType") or
                actual_row.get("sourceIdentityVerified") is not True or
                actual_row.get("sourceMaskFieldsVerified") is not True or
                actual_row.get("sourceGraphicTypeVerified") is not True or
                actual_row.get("sourceReferenceVerified") is not True or
                actual_row.get("actualMaskEnabled") is not expected.get("enabled") or
                actual_row.get("actualGraphicEnabled") is not expected.get("enabled") or
                actual_row.get("actualRaycastTarget") is not False or
                actual_row.get("sourceSerializedActiveVerified") is not True or
                actual_row.get("sourceSerializedActive") is not active or
                actual_row.get("sourceActiveSelf") is not self_active or
                actual_row.get("sourceHierarchyActiveMatchesExpected") is not True or
                actual_row.get("sourceActivityStage") != ("loaded-hierarchy" if mode == "loaded" else "persistent-serialized-scope") or
                (mode == "loaded" and (actual_row.get("helperMaskReadbackVerified") is not True or
                                        actual_row.get("sourceRenderContextDeferred") is not False)) or
                (mode == "persistent" and actual_row.get("helperMaskReadbackVerified") is not True and
                 not (expected.get("maskType") == 0 and expected.get("inverted") is True and
                      actual_row.get("sourceRenderContextDeferred") is True)) or
                actual_row.get("sourceAlphaThreshold") != expected.get("alphaThreshold") or
                actual_row.get("actualAlphaThreshold") != expected.get("alphaThreshold") or
                actual_row.get("verified") is not True):
            failures.append(f"{mode} source Mask typed identity/activity proof differs: {source_id}")
        if mode == "loaded" and actual_row.get("sourceActiveInHierarchy") is not active:
            failures.append(f"loaded source Mask hierarchy activity differs: {source_id}")
    if row.get("sourceMaskIdentitiesVerified") is not True:
        failures.append(f"{mode} source Mask identity aggregate verification is false")
    return failures


def _check_queue(spec, row, owner, mode, plan=None, spine_native_bindings=None):
    failures = []
    if not isinstance(row, dict):
        return [f"{mode} queue readback is absent"]
    if row.get("rootScope") != spec.get("rootScope"):
        failures.append(f"{mode} queue root identity differs")
    if mode == "persistent":
        if (row.get("readbackMode") != "persistent" or row.get("provisional") is not False or
                row.get("verified") is not True or row.get("persistentSnapshotVerified") is not True or
                row.get("runtimeGeometryDeferred") is not True or
                row.get("initializedPresentationVerified") is not False):
            failures.append("saved Prefab queue lacks a persistent, runtime-deferred readback")
    else:
        if (row.get("readbackMode") != "initialized" or row.get("provisional") is not False or
                row.get("verified") is not True or row.get("persistentSnapshotVerified") is not True or
                row.get("initializedPresentationVerified") is not True or
                row.get("runtimeGeometryDeferred") is not False):
            failures.append("loaded Prefab queue lacks initialized presentation evidence")
    if row.get("sourceTreePreserved") is not True or row.get("drawSequenceVerified") is not True:
        failures.append(f"{mode} source tree or draw sequence is not verified")
    structural = row.get("structuralDiagnostics")
    if not isinstance(structural, list) or structural:
        failures.append(f"{mode} native readback reports structural failures: {structural}")
    if row.get("sourceGraphicsCovered") is not True:
        failures.append(f"{mode} source Graphic suppression coverage is incomplete")
    if row.get("layoutIgnored") is not True:
        failures.append(f"{mode} generated proxy root participates in source layout")
    if row.get("sourceFieldsPreserved") is not True:
        failures.append(f"{mode} source SortOrder fields are not preserved")
    if row.get("sourceSortRootsPreserved") is not True:
        failures.append(f"{mode} source SortRoot fields are not preserved")
    if row.get("sourceMaskReferencesVerified") is not True:
        failures.append(f"{mode} source mask component references are not verified")
    failures.extend(_check_source_mask_identities(spec, row, "loaded" if mode == "loaded" else "persistent", plan or {}))
    failures.extend(_field_rows(spec.get("sourceFields", []), row.get("sourceFields"), owner))
    failures.extend(_field_rows(spec.get("sourceSortRoots", []), row.get("sourceSortRoots"), owner, sort_root=True))
    failures.extend(_check_graphics(spec, row, owner, "loaded" if mode == "loaded" else "persistent"))
    failures.extend(_check_text_sources(spec, row, "loaded" if mode == "loaded" else "persistent"))
    failures.extend(_check_spine_owner_delegations(spec, row, "loaded" if mode == "loaded" else "persistent", plan,
                                                    spine_native_bindings))
    failures.extend(_check_spine_null_data_owners(spec, row, "loaded" if mode == "loaded" else "persistent", plan,
                                                   spine_native_bindings))
    failures.extend(_check_spine_empty_pose_owners(spec, row, "loaded" if mode == "loaded" else "persistent", plan,
                                                    spine_native_bindings))
    failures.extend(_check_spine_non_draw_children(spec, row, "loaded" if mode == "loaded" else "persistent", plan))
    failures.extend(_check_block_input_events(spec, row, "loaded" if mode == "loaded" else "persistent", plan))
    expected_masks = [mask.get("sourceId") for mask in spec.get("masks", []) if isinstance(mask, dict)]
    masks = row.get("masks")
    if (not isinstance(masks, list) or
            [mask.get("sourceId") for mask in masks if isinstance(mask, dict)] != expected_masks or
            row.get("maskSourceIds") != expected_masks or
            any(not isinstance(mask, dict) or mask.get("verified") is not True for mask in masks or [])):
        failures.append(f"{mode} mask event identities or native fields differ: " +
                        repr([mask.get("failedChecks") for mask in masks if isinstance(mask, dict)] if isinstance(masks, list) else masks))
    return failures


def _creator_non_draw_errors(spec, actual, creator_assets=None):
    expected_rows = spec.get("nonDrawRenderers")
    actual_rows = actual.get("sourceNonDrawRenderers")
    if not isinstance(expected_rows, list) or not isinstance(actual_rows, list):
        return ["Creator typed non-draw renderer readback is absent"]
    errors = []
    expected_by_id = {}
    for row in expected_rows:
        if not isinstance(row, dict) or not isinstance(row.get("sourceId"), str) or row["sourceId"] in expected_by_id:
            errors.append("Creator non-draw renderer spec identities are malformed or duplicated")
            continue
        expected_by_id[row["sourceId"]] = row
    actual_by_id = {}
    for row in actual_rows:
        if not isinstance(row, dict) or not isinstance(row.get("sourceId"), str) or row["sourceId"] in actual_by_id:
            errors.append("Creator native non-draw renderer rows are malformed or duplicated")
            continue
        actual_by_id[row["sourceId"]] = row
    if set(actual_by_id) != set(expected_by_id):
        errors.append("Creator native non-draw renderer source IDs differ")

    component_ids = set()
    source_nodes = spec.get("sourceNodeActive") or {}
    for sid, expected in expected_by_id.items():
        row = actual_by_id.get(sid)
        if row is None:
            continue
        expected_enabled = expected.get("nativeEnabledExpected")
        expected_needs_binding = expected.get("sourceNeedsSpriteBinding")
        source_frame_asset_id = expected.get("sourceSpriteFrameAssetId")
        native_image_uuid = expected.get("nativeSpriteImageUuidExpected")
        expected_native_frame = None
        source_type = expected.get("sourceType")
        if source_type == "cc.Sprite":
            if type(expected_needs_binding) is not bool:
                errors.append(f"Creator Sprite no-draw binding policy is missing: {sid}")
            elif expected_enabled is not (expected.get("sourceEnabled") is True and not expected_needs_binding):
                errors.append(f"Creator Sprite native enabled expectation conflicts with binding policy: {sid}")
            elif expected.get("sourceSpriteFrameUuid") is None and not expected_needs_binding:
                errors.append(f"Creator Sprite has null source frame without binding-needed proof: {sid}")
            elif expected_needs_binding and expected.get("sourceSpriteFrameUuid") is not None:
                errors.append(f"Creator Sprite has unresolved nonempty source SpriteFrame reference: {sid}")
            if expected.get("sourceTextureBound") is not (expected.get("sourceSpriteFrameUuid") is not None):
                errors.append(f"Creator Sprite source texture identity/bound flag differs: {sid}")
            if expected.get("sourceActive") is True and expected.get("sourceEnabled") is True:
                expected_reason = "null-sprite-frame" if expected_needs_binding else None
                if expected_reason is None or expected.get("noDrawReason") != expected_reason:
                    errors.append(f"Creator active no-draw Sprite reason conflicts with binding policy: {sid}")
            elif expected.get("sourceActive") is False and expected.get("noDrawReason") != "inactive-source":
                errors.append(f"Creator inactive Sprite no-draw reason differs: {sid}")
            elif expected.get("sourceActive") is True and expected.get("sourceEnabled") is False and expected.get("noDrawReason") != "disabled-source":
                errors.append(f"Creator disabled Sprite no-draw reason differs: {sid}")
            if expected_needs_binding:
                if source_frame_asset_id is not None or native_image_uuid is not None:
                    errors.append(f"Creator null-frame Sprite carries a nonnull target asset identity: {sid}")
            else:
                if not isinstance(source_frame_asset_id, str) or not source_frame_asset_id or not isinstance(native_image_uuid, str) or not native_image_uuid:
                    errors.append(f"Creator bound Sprite image asset identity is missing: {sid}")
                else:
                    matches = [asset for asset in creator_assets or [] if isinstance(asset, dict) and asset.get("sourceId") == source_frame_asset_id]
                    if (len(matches) != 1 or matches[0].get("kind") != "sprite" or
                            matches[0].get("uuid") != native_image_uuid or
                            not isinstance(matches[0].get("spriteFrameUuid"), str) or
                            re.fullmatch(r"[a-f0-9-]{36}@[a-f0-9]+", matches[0].get("spriteFrameUuid", "")) is None):
                        errors.append(f"Creator saved ImageAsset/SpriteFrame identity mapping differs: {sid}")
                    else:
                        expected_native_frame = matches[0]["spriteFrameUuid"]
        elif expected_needs_binding is not False:
            errors.append(f"Creator non-Sprite carries a Sprite binding policy: {sid}")
        elif source_frame_asset_id is not None or native_image_uuid is not None:
            errors.append(f"Creator non-Sprite carries a native SpriteFrame expectation: {sid}")
        if (row.get("sourceId") != sid or row.get("nativeId") != expected.get("nativeId") or
                row.get("node") != expected.get("node") or row.get("sourceType") != expected.get("sourceType") or
                row.get("expectedNativeType") != expected.get("expectedNativeType") or
                row.get("actualNativeType") != expected.get("expectedNativeType") or
                row.get("sourceEnabled") is not expected.get("sourceEnabled") or
                row.get("sourceActive") is not expected.get("sourceActive") or
                row.get("sourceNeedsSpriteBinding") is not expected_needs_binding or
                row.get("sourceSpriteFrameAssetId") != source_frame_asset_id or
                row.get("nativeSpriteImageUuidExpected") != native_image_uuid or
                row.get("nativeSpriteFrameUuidExpected") != expected_native_frame or
                row.get("nativeEnabledExpected") is not expected_enabled or
                row.get("componentEnabled") is not expected_enabled or
                row.get("nodeActive") is not source_nodes.get(expected.get("node")) or
                row.get("effectiveActive") is not expected.get("sourceActive") or
                row.get("noDrawReason") != expected.get("noDrawReason") or row.get("verified") is not True):
            errors.append(f"Creator non-draw source identity/activity/reason differs: {sid}")
        component_uuid = row.get("componentUuid")
        if not isinstance(component_uuid, str) or not component_uuid or component_uuid in component_ids:
            errors.append(f"Creator non-draw native component UUID missing or duplicated: {sid}")
        else:
            component_ids.add(component_uuid)
        fields_json = expected.get("sourceFieldsJson")
        fields_hash = expected.get("sourceFieldsSha256")
        try:
            parsed_fields = json.loads(fields_json) if isinstance(fields_json, str) else None
            canonical = json.dumps(parsed_fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except (ValueError, TypeError):
            parsed_fields, canonical = None, None
        if (not isinstance(parsed_fields, dict) or parsed_fields != expected.get("sourceFields") or
                canonical != fields_json or not isinstance(fields_hash, str) or
                hashlib.sha256(fields_json.encode("utf-8")).hexdigest() != fields_hash or
                row.get("sourceFieldsJson") != fields_json or row.get("sourceFieldsSha256") != fields_hash):
            errors.append(f"Creator non-draw serialized source fields/hash differ: {sid}")
        if (row.get("sourceSpriteFrameUuid") != expected.get("sourceSpriteFrameUuid") or
                row.get("sourceNeedsSpriteBinding") is not expected_needs_binding or
                row.get("sourceText") != expected.get("sourceText") or
                row.get("nativeTextExpectation") != expected.get("nativeTextExpectation") or
                row.get("sourceTextEmpty") != expected.get("sourceTextEmpty") or
                row.get("sourceFontId") != expected.get("sourceFontId") or
                row.get("nativeFontAssetId") != expected.get("nativeFontAssetId") or
                row.get("nativeFallbackAssetIds") != expected.get("nativeFallbackAssetIds") or
                row.get("targetSystemFontFamily") != expected.get("targetSystemFontFamily") or
                row.get("creatorMarkup") != expected.get("creatorMarkup")):
            errors.append(f"Creator non-draw source/target text or font contract differs: {sid}")
        if source_type == "cc.Sprite":
            frame = row.get("nativeSpriteFrameUuid")
            if expected_needs_binding and frame is not None:
                errors.append(f"Creator Sprite needing source binding gained a native SpriteFrame: {sid}")
            if not expected_needs_binding and frame != expected_native_frame:
                errors.append(f"Creator native SpriteFrame does not match exact resolved source asset: {sid}")
        if expected.get("sourceType") in ("cc.Label", "cc.RichText"):
            if row.get("actualText") != expected.get("nativeTextExpectation", expected.get("sourceText")):
                errors.append(f"Creator non-draw actual text differs from native projection: {sid}")
            if expected.get("noDrawReason") == "empty-text" and expected.get("sourceTextEmpty") is not True:
                errors.append(f"Creator empty-text reason has nonempty source proof: {sid}")
        if expected.get("sourceType") == "cc.Graphics":
            if (expected.get("initialCommandStreamEmpty") is not True or row.get("initialCommandStreamEmpty") is not True or
                    expected.get("sourceDrawingCommands") != "not-serialized-empty-in-fixed-state" or
                    row.get("sourceDrawingCommands") != expected.get("sourceDrawingCommands") or
                    row.get("sourceMaterialIds") != expected.get("sourceMaterialIds") or
                    row.get("graphicsPathCount") != 0 or row.get("nativeMaterialVerified") is not True or
                    row.get("nativeMaterialUuid") != "f0416e68-0200-4b77-a926-4f9d16e494da" or
                    row.get("nativeEffectUuid") != "1c02ae6f-4492-4915-b8f8-7492a3b1e4cd"):
                errors.append(f"Creator empty Graphics material/command proof differs: {sid}")
    return errors


def _creator_projection_errors(spec, actual, creator_assets=None):
    errors = []
    original = spec.get("sourceOriginalDrawEvents")
    proxy_events = spec.get("sourceDrawEvents")
    renderer_rows = spec.get("renderers")
    non_draw_rows = spec.get("nonDrawRenderers")
    mapping_rows = spec.get("sourceNonDrawRenderers")
    if not all(isinstance(value, list) for value in (original, proxy_events, renderer_rows, non_draw_rows, mapping_rows)):
        return ["Creator source queue projection contract is incomplete"]
    if actual.get("sourceOriginalDrawEvents") != original:
        errors.append("Creator actual original source event sequence differs")
    if actual.get("sourceQueueProjectionVerified") is not True:
        errors.append("Creator source queue projection flag is false")

    drawable = {}
    for row in renderer_rows:
        if not isinstance(row, dict) or not isinstance(row.get("sourceComponentId"), str):
            errors.append("Creator drawable renderer spec is malformed")
            continue
        sid = row["sourceComponentId"]
        if sid in drawable:
            errors.append(f"Creator drawable renderer source ID repeats: {sid}")
        drawable[sid] = row
    non_draw = {}
    for row in non_draw_rows:
        if not isinstance(row, dict) or not isinstance(row.get("sourceId"), str):
            errors.append("Creator non-draw renderer spec is malformed")
            continue
        sid = row["sourceId"]
        if sid in non_draw or sid in drawable:
            errors.append(f"Creator draw/non-draw source ID repeats: {sid}")
        non_draw[sid] = row

    event_indices = {}
    for index, event in enumerate(original):
        if (not isinstance(event, dict) or event.get("kind") not in ("renderer", "maskEnter", "maskExit") or
                not isinstance(event.get("node"), str)):
            errors.append(f"Creator original source event is malformed at {index}")
            continue
        if event["kind"] != "renderer":
            continue
        sid = event.get("sourceComponentId")
        if not isinstance(sid, str) or sid in event_indices:
            errors.append(f"Creator original renderer event source ID is missing/duplicated at {index}")
            continue
        event_indices[sid] = (index, event["node"])
        drawable_row, non_draw_row = drawable.get(sid), non_draw.get(sid)
        if (drawable_row is None) == (non_draw_row is None):
            errors.append(f"Creator original renderer event is not mapped exactly once: {sid}")
        elif drawable_row is not None and drawable_row.get("node") != event["node"]:
            errors.append(f"Creator drawable renderer event node differs: {sid}")
        elif non_draw_row is not None and non_draw_row.get("node") != event["node"]:
            errors.append(f"Creator non-draw renderer event node differs: {sid}")
    for sid, row in drawable.items():
        if sid not in event_indices:
            errors.append(f"Creator drawable renderer is absent from original queue: {sid}")

    expected_proxy_events = [event for event in original if not (
        isinstance(event, dict) and event.get("kind") == "renderer" and event.get("sourceComponentId") in non_draw)]
    if proxy_events != expected_proxy_events:
        errors.append("Creator proxy event stream is not the exact original drawable projection")

    expected_mappings = {}
    for sid, row in non_draw.items():
        source_event = event_indices.get(sid)
        expected_mappings[sid] = {"sourceComponentId": sid, "node": row.get("node"),
            "disposition": "source-render-event" if source_event else "source-component-only",
            "sourceEventIndex": source_event[0] if source_event else None,
            "noDrawReason": row.get("noDrawReason")}
    planned_mappings = {}
    for mapping in mapping_rows:
        if not isinstance(mapping, dict) or not isinstance(mapping.get("sourceComponentId"), str):
            errors.append("Creator source non-draw mapping is malformed")
            continue
        sid = mapping["sourceComponentId"]
        if sid in planned_mappings:
            errors.append(f"Creator source non-draw mapping repeats source ID: {sid}")
        planned_mappings[sid] = mapping
    if set(planned_mappings) != set(non_draw):
        errors.append("Creator planned non-draw mapping denominator differs")
    for sid, expected in expected_mappings.items():
        row = planned_mappings.get(sid)
        if (not isinstance(row, dict) or any(row.get(key) != value for key, value in expected.items())):
            errors.append(f"Creator planned non-draw index/node/reason differs: {sid}")

    actual_mappings = actual.get("sourceNonDrawSourceMappings")
    if not isinstance(actual_mappings, list) or len(actual_mappings) != len(expected_mappings):
        errors.append("Creator actual non-draw mapping count differs")
    else:
        observed = {}
        for row in actual_mappings:
            if not isinstance(row, dict) or not isinstance(row.get("sourceComponentId"), str):
                errors.append("Creator actual non-draw mapping row is malformed")
                continue
            sid = row["sourceComponentId"]
            if sid in observed:
                errors.append(f"Creator actual non-draw mapping repeats source ID: {sid}")
            observed[sid] = row
        if set(observed) != set(expected_mappings):
            errors.append("Creator actual non-draw mapping denominator differs")
        for sid, expected in expected_mappings.items():
            row = observed.get(sid)
            if (not isinstance(row, dict) or any(row.get(key) != value for key, value in expected.items()) or
                    row.get("verified") is not True):
                errors.append(f"Creator actual non-draw index/node/reason differs: {sid}")
    errors.extend(_creator_non_draw_errors(spec, actual, creator_assets))
    return errors


_CREATOR_MASK_CHECKS = frozenset({
    "maskPresent", "expectedSourceMaskPresent", "sourceAndProxyMaskRefs", "markerSourceComponentId",
    "markerMaskType", "maskType", "enabled", "inverted", "alphaThreshold", "backingType",
    "spriteFrame", "sourceAndNativeSpriteFields", "identityPresent", "identityDisabled", "identitySourceId",
    "identityNativeId", "identitySourceMaskType", "identityInverted", "identityAlphaThreshold",
    "identityFieldsJson", "identitySpriteFrameUuid", "identityNativeMaskReference",
    "identitySpriteFrameReference", "transform", "worldMatrix", "uiContentSize", "uiAnchor", "opacity", "layer",
})


def _creator_mask_readback_matches(expected, actual):
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return False
    source_id = expected.get("sourceId")
    native_id = expected.get("nativeId")
    node = expected.get("node")
    mask_type = expected.get("maskType")
    enabled = expected.get("enabled")
    inverted = expected.get("inverted")
    threshold = expected.get("alphaThreshold")
    sprite_frame = expected.get("spriteFrameUuid") or None
    checks = actual.get("checks")
    if (not isinstance(source_id, str) or not source_id or
            not (native_id is None or isinstance(native_id, str)) or
            not isinstance(node, str) or type(mask_type) is not int or type(enabled) is not bool or
            type(inverted) is not bool or isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or
            not isinstance(checks, dict) or set(checks) != _CREATOR_MASK_CHECKS or
            any(value is not True for value in checks.values())):
        return False
    if (actual.get("sourceId") != source_id or actual.get("sourceNode") != node or
            actual.get("sourceMaskType") != mask_type or type(actual.get("nativeMaskType")) is not int or
            actual.get("enabled") is not enabled or actual.get("inverted") is not inverted or
            actual.get("alphaThreshold") != threshold or actual.get("transformVerified") is not True or
            actual.get("opacityVerified") is not True or actual.get("verified") is not True or
            actual.get("expectedMaskEnabled") is not enabled or actual.get("expectedMaskType") != mask_type or
            actual.get("expectedInverted") is not inverted or actual.get("expectedAlphaThreshold") != threshold or
            actual.get("expectedSpriteFrameUuid") != sprite_frame or
            actual.get("identitySourceId") != source_id or
            actual.get("identityNativeId") != native_id or actual.get("identityNativeMaskRefMatches") is not True or
            type(actual.get("sourceLayer")) is not int or type(actual.get("nativeLayer")) is not int):
        return False
    for key in ("sourceLocalTransform", "nativeLocalTransform"):
        values = actual.get(key)
        if (not isinstance(values, list) or len(values) != 10 or
                any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                    for value in values)):
            return False
    for key in ("sourceWorldMatrix", "nativeWorldMatrix"):
        values = actual.get(key)
        if (not isinstance(values, list) or len(values) != 16 or
                any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                    for value in values)):
            return False
    for key in ("sourceSizeAnchor", "nativeSizeAnchor"):
        values = actual.get(key)
        if (not isinstance(values, list) or len(values) != 4 or
                any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                    for value in values)):
            return False
    if actual["sourceSizeAnchor"] != actual["nativeSizeAnchor"]:
        return False
    for key in ("sourceOpacityFactor", "nativeOpacityFactor"):
        value = actual.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return False
    if abs(actual["sourceOpacityFactor"] - actual["nativeOpacityFactor"]) > (1 / 255 + 1e-6):
        return False
    if mask_type == 2:
        expected_native_frame = actual.get("nativeSpriteFrameExpectedUuid")
        return (isinstance(expected_native_frame, str) and bool(expected_native_frame) and
                actual.get("expectedSpriteFrameUuid") == sprite_frame and
                actual.get("sourceSpriteFrameUuid") == expected_native_frame and
                actual.get("spriteFrameUuid") == expected_native_frame and
                actual.get("sourceSpriteType") == "Sprite" and actual.get("nativeSpriteType") == "Sprite" and
                actual.get("sourceSpriteEnabled") is True and actual.get("nativeSpriteEnabled") is True and
                isinstance(actual.get("sourceSpriteFingerprint"), str) and bool(actual.get("sourceSpriteFingerprint")) and
                actual.get("sourceSpriteFingerprint") == actual.get("nativeSpriteFingerprint"))
    return (actual.get("spriteFrameUuid") is None and actual.get("sourceSpriteFrameUuid") is None and
            actual.get("nativeSpriteFrameExpectedUuid") is None and actual.get("sourceSpriteType") is None and
            actual.get("nativeSpriteType") is None and actual.get("sourceSpriteFingerprint") is None and
            actual.get("nativeSpriteFingerprint") is None)


def verify(plan: dict, result: dict, spine_native_bindings=None):
    """Return diagnostics from actual persistent and initialized queue rows.

    ``plan`` is the frozen Unity import plan. ``result`` is the Editor
    readback object (or its decoded JSON mapping); truthy aggregate flags are
    never sufficient without typed per-source rows.
    """
    queues = plan.get("staticSortQueue") or []
    if not queues:
        return []
    needs_spine_binding = any(isinstance(spec, dict) and any(
        isinstance(renderer, dict) and renderer.get("sourceType") == "sp.Skeleton"
        for key in ("renderers", "nonDrawRenderers") for renderer in spec.get(key, [])) for spec in queues)
    verified_spine_bindings = None
    spine_binding_errors = []
    if needs_spine_binding:
        verified_spine_bindings, spine_binding_errors = _load_spine_binding_contract(plan, spine_native_bindings)
    owner_by_id = {prefab.get("sourceId"): prefab for prefab in plan.get("sourcePrefabs", [])
                   if isinstance(prefab, dict)}
    rows = result.get("sourcePrefabs") if isinstance(result, dict) else None
    actual_by_id = {row.get("sourceId"): row for row in rows or [] if isinstance(row, dict)}
    diagnostics = []
    diagnostics.extend(_diag("staticSortQueue", message) for message in spine_binding_errors)
    if len(actual_by_id) != len(rows or []):
        return [_diag("staticSortQueue", "Source Prefab rows are malformed or duplicated")]
    queue_by_prefab = {}
    for spec in queues:
        if not isinstance(spec, dict):
            diagnostics.append(_diag("staticSortQueue", "Queue specification is malformed"))
            continue
        owner = spec.get("sourcePrefabId")
        queue_by_prefab.setdefault(owner, []).append(spec)
    for source_id, specs in queue_by_prefab.items():
        prefab = owner_by_id.get(source_id)
        if prefab is None:
            diagnostics.append(_diag(str(source_id), "Queue references unknown source Prefab"))
            continue
        observed = actual_by_id.get(source_id)
        if observed is None:
            diagnostics.append(_diag(source_id, "Source Prefab queue readback is absent"))
            continue
        binding = observed.get("staticSortFields")
        if not isinstance(binding, dict) or binding.get("sourcePrefabId") != source_id or binding.get("prefabPath") != prefab.get("path"):
            diagnostics.append(_diag(source_id, "Static sort Prefab binding identity differs"))
            continue
        if binding.get("verified") is not True:
            diagnostics.append(_diag(source_id, "Static sort aggregate verification failed"))
        for mode, key in (("persistent", "persistentAsset"), ("loaded", "loadedInstance")):
            actual = binding.get(key)
            if not isinstance(actual, list) or len(actual) != len(specs):
                diagnostics.append(_diag(source_id, f"{mode} queue scope count differs"))
                continue
            by_root = {row.get("rootScope"): row for row in actual if isinstance(row, dict)}
            expected_roots = {spec.get("rootScope") for spec in specs}
            if len(by_root) != len(actual) or set(by_root) != expected_roots:
                diagnostics.append(_diag(source_id, f"{mode} queue scopes are missing, extra, or duplicated"))
                continue
            for spec in specs:
                root = spec.get("rootScope")
                errors = _check_queue(spec, by_root[root], source_id, mode, plan, verified_spine_bindings)
                diagnostics.extend(_diag(source_id, f"{root}: {message}") for message in errors)
    return diagnostics


def verify_creator(plan: dict, saved: dict):
    """Verify Creator persistent/initialized static sort rows when wired by the Editor bridge."""
    queues = plan.get("staticSortQueue") or []
    if not queues:
        return []
    prefabs = {row.get("sourceId"): row for row in plan.get("sourcePrefabs", []) if isinstance(row, dict)}
    actual_rows = saved.get("sourcePrefabs") if isinstance(saved, dict) else None
    actual_prefabs = {row.get("sourceId"): row for row in actual_rows or [] if isinstance(row, dict)}
    diagnostics = []
    creator_assets = saved.get("assets") if isinstance(saved, dict) else None
    if creator_assets is not None:
        if not isinstance(creator_assets, list) or any(not isinstance(asset, dict) for asset in creator_assets):
            diagnostics.append(_diag("staticSortQueue", "Creator saved asset identity rows are malformed"))
            creator_assets = []
        elif len({asset.get("sourceId") for asset in creator_assets}) != len(creator_assets):
            diagnostics.append(_diag("staticSortQueue", "Creator saved asset source IDs are duplicated"))
    if len(actual_prefabs) != len(actual_rows or []):
        return [_diag("staticSortQueue", "Creator source Prefab rows are malformed or duplicated")]
    for spec in queues:
        owner = spec.get("sourcePrefabId") if isinstance(spec, dict) else None
        source_prefab = prefabs.get(owner)
        observed = actual_prefabs.get(owner)
        if source_prefab is None or observed is None:
            diagnostics.append(_diag(str(owner), "Creator sort queue source Prefab is missing"))
            continue
        binding = observed.get("staticSortQueue") or observed.get("staticSortFields")
        if not isinstance(binding, dict):
            diagnostics.append(_diag(owner, "Creator static sort Prefab binding identity differs"))
            continue
        if observed.get("path") != source_prefab.get("path") and binding.get("prefabPath") != source_prefab.get("path"):
            diagnostics.append(_diag(owner, "Creator static sort Prefab path differs"))
            continue
        if "persistent" in binding or "initialized" in binding:
            mode_rows = (("persistent", [binding.get("persistent")]),
                         ("loaded", [binding.get("initialized")]))
        else:
            mode_rows = (("persistent", binding.get("persistentAsset")),
                         ("loaded", binding.get("loadedInstance")))
        expected_root_scope = spec.get("rootScope")
        for mode, rows in mode_rows:
            presentation = "persistent" if mode == "persistent" else "initialized"
            if not isinstance(rows, list) or len(rows) != 1:
                diagnostics.append(_diag(owner, f"Creator {mode} queue scope count differs"))
                continue
            row = rows[0]
            if (not isinstance(row, dict) or row.get("rootScope") != expected_root_scope or
                    row.get("presentationMode") != presentation or row.get("verified") is not True):
                diagnostics.append(_diag(owner, f"Creator {mode} queue readback identity or mode differs"))
                continue
            if row.get("sourceTreePreserved") is not True or row.get("sourceFieldsPreserved") is not True or row.get("sourceSortRootsPreserved") is not True:
                diagnostics.append(_diag(owner, f"Creator {mode} source tree/fields are not verified"))
            if row.get("rootScope") != spec.get("rootScope"):
                diagnostics.append(_diag(owner, f"Creator {mode} queue identity differs"))
            diagnostics.extend(_diag(owner, f"Creator {mode}: {error}")
                               for error in _creator_projection_errors(spec, row, creator_assets))
            expected_orders = spec.get("sourceSortOrderFields", [])
            actual_orders = row.get("sourceSortOrderFields")
            if not isinstance(actual_orders, list) or len(actual_orders) != len(expected_orders):
                diagnostics.append(_diag(owner, f"Creator {mode} SortOrder row count differs"))
            else:
                for expected, actual in zip(expected_orders, actual_orders):
                    if (not isinstance(actual, dict) or actual.get("expectedSourceId") != expected.get("sourceId") or
                            actual.get("sourceId") != expected.get("sourceId") or
                            actual.get("expectedNativeId") != expected.get("nativeId") or
                            actual.get("nativeId") != expected.get("nativeId") or actual.get("node") != expected.get("node") or
                            actual.get("sourceSortOrder") != expected.get("sortOrder") or
                            actual.get("effectiveSourceSortOrder") != (expected.get("sortOrder") if expected.get("enabled") else 0) or
                            actual.get("enabledInSource") is not expected.get("enabled") or
                            actual.get("renderedOnNode") is not False or actual.get("verified") is not True or
                            actual.get("nativeClass") != "MonkeyStaticSortOrderField" or
                            not isinstance(actual.get("componentUuid"), str) or not actual.get("componentUuid")):
                        diagnostics.append(_diag(owner, f"Creator {mode} SortOrder typed field differs"))
            expected_sort_roots = spec.get("sourceSortRoots", [])
            actual_roots = row.get("sourceSortRoots")
            if not isinstance(actual_roots, list) or len(actual_roots) != len(expected_sort_roots):
                diagnostics.append(_diag(owner, f"Creator {mode} SortRoot row count differs"))
            else:
                for expected, actual in zip(expected_sort_roots, actual_roots):
                    if (not isinstance(actual, dict) or actual.get("expectedSourceId") != expected.get("sourceId") or
                            actual.get("sourceId") != expected.get("sourceId") or
                            actual.get("expectedNativeId") != expected.get("nativeId") or
                            actual.get("nativeId") != expected.get("nativeId") or actual.get("node") != expected.get("node") or
                            actual.get("enabledInSource") is not expected.get("enabled") or
                            actual.get("verified") is not True or actual.get("nativeClass") != "CreatorStaticSortRootField" or
                            not isinstance(actual.get("componentUuid"), str) or not actual.get("componentUuid")):
                        diagnostics.append(_diag(owner, f"Creator {mode} SortRoot typed field differs"))
            expected_graphics = spec.get("renderers", [])
            actual_graphics = row.get("graphics")
            if not isinstance(actual_graphics, list) or len(actual_graphics) != len(expected_graphics):
                diagnostics.append(_diag(owner, f"Creator {mode} renderer evidence count differs"))
            else:
                for expected, actual in zip(expected_graphics, actual_graphics):
                    if (not isinstance(actual, dict) or actual.get("sourceComponentId") != expected.get("sourceComponentId") or
                            actual.get("sourceNode") != expected.get("node") or actual.get("verified") is not True or
                            not actual.get("sourceFingerprint") or actual.get("sourceFingerprint") != actual.get("proxyFingerprint") or
                            actual.get("opacityVerified") is not True or actual.get("originalLayer") != actual.get("proxyLayer")):
                        diagnostics.append(_diag(owner, f"Creator {mode} renderer evidence differs"))
            expected_masks = spec.get("masks", [])
            actual_masks = row.get("masks")
            if not isinstance(actual_masks, list) or len(actual_masks) != len(expected_masks):
                diagnostics.append(_diag(owner, f"Creator {mode} mask evidence count differs"))
            else:
                expected_by_id = {}
                actual_by_id = {}
                for expected in expected_masks:
                    sid = expected.get("sourceId") if isinstance(expected, dict) else None
                    if not isinstance(sid, str) or not sid or sid in expected_by_id:
                        diagnostics.append(_diag(owner, f"Creator {mode} mask specification IDs are malformed or duplicated"))
                    else:
                        expected_by_id[sid] = expected
                for actual_mask in actual_masks:
                    sid = actual_mask.get("sourceId") if isinstance(actual_mask, dict) else None
                    if not isinstance(sid, str) or not sid or sid in actual_by_id:
                        diagnostics.append(_diag(owner, f"Creator {mode} mask readback IDs are malformed or duplicated"))
                    else:
                        actual_by_id[sid] = actual_mask
                if set(expected_by_id) != set(actual_by_id):
                    diagnostics.append(_diag(owner, f"Creator {mode} mask source ID mapping has missing or extra rows"))
                for sid, expected in expected_by_id.items():
                    actual_mask = actual_by_id.get(sid)
                    if actual_mask is None or not _creator_mask_readback_matches(expected, actual_mask):
                        diagnostics.append(_diag(owner, f"Creator {mode} mask typed evidence differs: {sid}"))
            if presentation == "persistent" and row.get("sourceLayersPreserved") is not True:
                diagnostics.append(_diag(owner, "Creator persistent source layer snapshot differs"))
            if presentation == "initialized" and (row.get("sourceSuppressed") is not True or row.get("nestedProxyRootsDisabled") is not True):
                diagnostics.append(_diag(owner, "Creator initialized source suppression evidence differs"))
            if row.get("drawSequenceVerified") is not True:
                diagnostics.append(_diag(owner, f"Creator {mode} draw sequence is not verified"))
    return diagnostics
