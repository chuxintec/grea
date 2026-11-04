"""Validate the separately pinned source and controlled-host Spine Canvas proof.

This is intentionally a narrow consumer for the Unity producer's Canvas context
DTO. It does not perform general Unity readback or reinterpret Spine data.
"""
from __future__ import annotations

import math
from pathlib import Path
import re

from .io import load, read, sha

CONTRACT = "monkey-static-spine-source-canvas-context/1"
EVIDENCE_PATH = "Analysis/Readback/SpineRendering/source-canvas-context.json"
RENDERING_PATH = "Assets/Game/Editor/Conversion/spine-static-rendering.json"
IMPORT_PLAN_PATH = "Assets/Game/Editor/Conversion/import-plan.json"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_JSON_BYTES = 64 * 1024 * 1024
_PPU_TOLERANCE = 0.001
_SCALE_TOLERANCE = 0.000001


def _gap(code: str, *, source_id: str | None = None, **details) -> dict:
    row = {"code": code}
    if source_id is not None:
        row["sourceId"] = source_id
    row.update(details)
    return row


def _number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _close(actual, expected, tolerance=_PPU_TOLERANCE) -> bool:
    return _number(actual) and _number(expected) and abs(actual - expected) <= tolerance


def _relative_file(root: Path, relative: str) -> Path:
    path = root / relative
    if path.is_symlink():
        raise ValueError("symlink is not accepted")
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("path escapes candidate root")
    cursor = path.parent
    while cursor != root and cursor != cursor.parent:
        if cursor.is_symlink():
            raise ValueError("symlink parent is not accepted")
        cursor = cursor.parent
    return resolved


def _read_json(path: Path):
    raw = read(path, max_bytes=_MAX_JSON_BYTES)
    return raw, load(raw, max_nodes=2_000_000, max_depth=96)


def _readback_documents(documents, candidate_root: Path) -> list[dict]:
    if documents is None:
        directory = candidate_root / "Analysis/Readback/SpineRendering"
        if not directory.is_dir():
            return []
        result = []
        for path in sorted(directory.glob("*.json")):
            if path.name == "source-canvas-context.json":
                continue
            _, item = _read_json(path)
            if isinstance(item, dict):
                result.append(item)
        return result
    if isinstance(documents, dict):
        if documents.get("contract") == "monkey-static-spine-rendering-readback/1":
            return [documents]
        values = documents.values()
    elif isinstance(documents, (list, tuple)):
        values = documents
    else:
        return []
    return [item for item in values if isinstance(item, dict) and
            item.get("contract") == "monkey-static-spine-rendering-readback/1"]


def _expected_components(rendering: dict, gaps: list[dict]) -> dict[str, dict]:
    rows = rendering.get("components")
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        gaps.append(_gap("SPINE_CANVAS_RENDERING_COMPONENTS_INVALID"))
        return {}
    expected = {}
    for row in rows:
        sid = row.get("sourceComponentId")
        if not isinstance(sid, str) or not sid or sid in expected:
            gaps.append(_gap("SPINE_CANVAS_RENDERING_COMPONENT_ID_INVALID", source_id=sid if isinstance(sid, str) else None))
            continue
        expected[sid] = row
    return expected


def _load_candidate_inputs(root: Path, rendering: dict, gaps: list[dict]):
    try:
        rendering_path = _relative_file(root, RENDERING_PATH)
        raw, saved_rendering = _read_json(rendering_path)
        rendering_sha = sha(raw)
        if saved_rendering != rendering:
            gaps.append(_gap("SPINE_CANVAS_RENDERING_PLAN_DIFFERS_FROM_CANDIDATE"))
    except Exception as error:
        rendering_sha = None
        gaps.append(_gap("SPINE_CANVAS_RENDERING_PLAN_UNREADABLE", message=str(error)))
    try:
        import_path = _relative_file(root, IMPORT_PLAN_PATH)
        _, import_plan = _read_json(import_path)
        if not isinstance(import_plan, dict):
            raise ValueError("import plan is not a JSON object")
    except Exception as error:
        import_plan = None
        gaps.append(_gap("SPINE_CANVAS_IMPORT_PLAN_UNREADABLE", message=str(error)))
    return rendering_sha, import_plan


def _validate_import_plan(rendering: dict, import_plan, expected: dict[str, dict],
                          context: dict, gaps: list[dict]) -> dict[str, dict]:
    if not isinstance(import_plan, dict):
        return {}
    if import_plan.get("sourceManifestSha256") != rendering.get("sourceManifestSha256"):
        gaps.append(_gap("SPINE_CANVAS_IMPORT_PLAN_MANIFEST_MISMATCH"))
    nodes = import_plan.get("nodes")
    if not isinstance(nodes, list) or any(not isinstance(row, dict) for row in nodes):
        gaps.append(_gap("SPINE_CANVAS_IMPORT_PLAN_NODES_INVALID"))
        nodes = []
    node_map = {}
    for row in nodes:
        sid = row.get("sourceId")
        if not isinstance(sid, str) or not sid or sid in node_map or type(row.get("active")) is not bool:
            gaps.append(_gap("SPINE_CANVAS_IMPORT_PLAN_NODE_ID_OR_ACTIVITY_INVALID",
                             source_id=sid if isinstance(sid, str) else None))
            continue
        node_map[sid] = row

    source_components = import_plan.get("components")
    if not isinstance(source_components, list) or any(not isinstance(row, dict) for row in source_components):
        gaps.append(_gap("SPINE_CANVAS_IMPORT_PLAN_COMPONENTS_INVALID"))
        source_components = []
    component_map = {}
    for row in source_components:
        sid = row.get("sourceId")
        if isinstance(sid, str) and sid:
            if sid in component_map:
                gaps.append(_gap("SPINE_CANVAS_IMPORT_PLAN_COMPONENT_ID_DUPLICATE", source_id=sid))
            component_map[sid] = row

    context_node_ids = set()
    contexts = context.get("contexts") if isinstance(context, dict) else None
    if isinstance(contexts, list):
        for row in contexts:
            if isinstance(row, dict) and isinstance(row.get("sourceNodeIds"), list):
                context_node_ids.update(node_id for node_id in row["sourceNodeIds"] if isinstance(node_id, str))
    if context_node_ids != set(node_map):
        gaps.append(_gap("SPINE_CANVAS_SOURCE_NODE_DENOMINATOR_MISMATCH",
                         missing=sorted(set(node_map) - context_node_ids),
                         extra=sorted(context_node_ids - set(node_map))))
    for sid, component in expected.items():
        source = component_map.get(sid)
        if source is None:
            gaps.append(_gap("SPINE_CANVAS_SOURCE_COMPONENT_MISSING_FROM_IMPORT_PLAN", source_id=sid))
            continue
        if source.get("node") != component.get("sourceNodeId"):
            gaps.append(_gap("SPINE_CANVAS_SOURCE_COMPONENT_NODE_MISMATCH", source_id=sid))
        if (type(component.get("sourceComponentEnabled")) is not bool or
                type(source.get("enabled")) is not bool or source.get("enabled") != component.get("sourceComponentEnabled")):
            gaps.append(_gap("SPINE_CANVAS_SOURCE_COMPONENT_ENABLED_MISMATCH", source_id=sid))
    return node_map


def _validate_source_context(rendering: dict, expected: dict[str, dict], context: dict,
                             import_nodes: dict[str, dict], rendering_sha: str | None,
                             gaps: list[dict]) -> tuple[float | None, dict[str, dict]]:
    if not isinstance(context, dict):
        gaps.append(_gap("SPINE_CANVAS_CONTEXT_DOCUMENT_INVALID"))
        return None, {}
    manifest_sha = rendering.get("sourceManifestSha256")
    if (context.get("schemaVersion") != 1 or context.get("contract") != CONTRACT or
            context.get("capturePhase") != "source-construction-before-prefab-save"):
        gaps.append(_gap("SPINE_CANVAS_CONTEXT_SCHEMA_OR_PHASE_INVALID"))
    if not isinstance(manifest_sha, str) or not _SHA256.fullmatch(manifest_sha) or context.get("sourceManifestSha256") != manifest_sha:
        gaps.append(_gap("SPINE_CANVAS_CONTEXT_MANIFEST_MISMATCH"))
    if (not isinstance(rendering_sha, str) or context.get("renderingPlanSha256") != rendering_sha or
            not isinstance(context.get("renderingPlanSha256"), str) or not _SHA256.fullmatch(context["renderingPlanSha256"])):
        gaps.append(_gap("SPINE_CANVAS_CONTEXT_RENDERING_PIN_MISMATCH"))
    if not isinstance(context.get("evidenceSha256"), str) or not _SHA256.fullmatch(context["evidenceSha256"]):
        gaps.append(_gap("SPINE_CANVAS_CONTEXT_INNER_HASH_INVALID"))
    if context.get("sourceNodeGeometryVerified") is not True or context.get("sourceCanvasContextVerified") is not True:
        gaps.append(_gap("SPINE_CANVAS_SOURCE_CONTEXT_NOT_VERIFIED"))
    ppu = context.get("sourceReferencePixelsPerUnit")
    if not _number(ppu) or ppu <= 0:
        gaps.append(_gap("SPINE_CANVAS_SOURCE_PPU_INVALID"))
        ppu = None
    contexts = context.get("contexts")
    if not isinstance(contexts, list) or not contexts:
        gaps.append(_gap("SPINE_CANVAS_CONTEXT_ROWS_MISSING"))
        contexts = []
    context_map = {}
    all_nodes = []
    for row in contexts:
        if not isinstance(row, dict) or type(row.get("contextIndex")) is not int or row["contextIndex"] in context_map:
            gaps.append(_gap("SPINE_CANVAS_CONTEXT_INDEX_INVALID"))
            continue
        context_map[row["contextIndex"]] = row
        node_ids = row.get("sourceNodeIds")
        if (not isinstance(node_ids, list) or any(not isinstance(value, str) or not value for value in node_ids) or
                len(node_ids) != len(set(node_ids))):
            gaps.append(_gap("SPINE_CANVAS_CONTEXT_NODE_MEMBERSHIP_INVALID", contextIndex=row["contextIndex"]))
            continue
        all_nodes.extend(node_ids)
        if (row.get("sourceCanvasRenderMode") != "ScreenSpaceOverlay" or
                row.get("sourceCanvasScalerPresent") is not True or row.get("sourceCanvasPpuMatchesScaler") is not True or
                not _close(row.get("sourceCanvasReferencePixelsPerUnit"), ppu) or
                not _close(row.get("sourceScalerReferencePixelsPerUnit"), ppu)):
            gaps.append(_gap("SPINE_CANVAS_SOURCE_CONTEXT_VALUES_MISMATCH", contextIndex=row["contextIndex"]))
        resolution = row.get("sourceScalerReferenceResolution")
        if not isinstance(resolution, list) or len(resolution) != 2 or any(not _number(v) or v <= 0 for v in resolution):
            gaps.append(_gap("SPINE_CANVAS_SOURCE_SCALER_RESOLUTION_INVALID", contextIndex=row["contextIndex"]))
        if not _number(row.get("sourceScalerMatchWidthOrHeight")):
            gaps.append(_gap("SPINE_CANVAS_SOURCE_SCALER_MATCH_INVALID", contextIndex=row["contextIndex"]))
    if set(context_map) != set(range(len(context_map))) or len(all_nodes) != len(set(all_nodes)):
        gaps.append(_gap("SPINE_CANVAS_CONTEXT_INDEX_OR_NODE_DUPLICATE"))
    source_node_count = context.get("sourceNodeCount")
    if type(source_node_count) is not int or source_node_count <= 0 or len(set(all_nodes)) != source_node_count:
        gaps.append(_gap("SPINE_CANVAS_SOURCE_NODE_COUNT_MISMATCH"))
    if import_nodes and set(all_nodes) != set(import_nodes):
        gaps.append(_gap("SPINE_CANVAS_CONTEXT_IMPORT_NODE_SET_MISMATCH",
                         missing=sorted(set(import_nodes) - set(all_nodes)), extra=sorted(set(all_nodes) - set(import_nodes))))

    component_rows = context.get("components")
    if not isinstance(component_rows, list) or any(not isinstance(row, dict) for row in component_rows):
        gaps.append(_gap("SPINE_CANVAS_CONTEXT_COMPONENTS_INVALID"))
        component_rows = []
    component_map = {}
    for row in component_rows:
        sid = row.get("sourceComponentId")
        if not isinstance(sid, str) or not sid or sid in component_map:
            gaps.append(_gap("SPINE_CANVAS_CONTEXT_COMPONENT_ID_INVALID", source_id=sid if isinstance(sid, str) else None))
            continue
        component_map[sid] = row
    if set(component_map) != set(expected):
        gaps.append(_gap("SPINE_CANVAS_CONTEXT_COMPONENT_DENOMINATOR_MISMATCH",
                         missing=sorted(set(expected) - set(component_map)), extra=sorted(set(component_map) - set(expected))))
    for sid, source in expected.items():
        row = component_map.get(sid)
        if row is None:
            continue
        context_index = row.get("sourceCanvasContextIndex")
        expected_prefab = source.get("sourcePrefabId")
        expected_node = source.get("sourceNodeId")
        expected_data = source.get("sourceDataAssetId")
        if (row.get("sourcePrefabId") != expected_prefab or row.get("sourceNodeId") != expected_node or
                row.get("sourceDataAssetId") != expected_data or row.get("sourceCanvasContextVerified") is not True or
                row.get("sourceNodeActivityVerified") is not True or type(row.get("sourceNodeActive")) is not bool or
                type(source.get("sourceComponentEnabled")) is not bool or
                row.get("sourceComponentEnabled") is not source.get("sourceComponentEnabled")):
            gaps.append(_gap("SPINE_CANVAS_CONTEXT_SOURCE_IDENTITY_OR_ACTIVITY_MISMATCH", source_id=sid))
        if import_nodes and expected_node in import_nodes and row.get("sourceNodeActive") != import_nodes[expected_node].get("active"):
            gaps.append(_gap("SPINE_CANVAS_CONTEXT_NODE_ACTIVE_MISMATCH", source_id=sid))
        if (type(context_index) is not int or context_index not in context_map or
                expected_node not in context_map.get(context_index, {}).get("sourceNodeIds", [])):
            gaps.append(_gap("SPINE_CANVAS_CONTEXT_COMPONENT_MEMBERSHIP_MISMATCH", source_id=sid))
    return ppu, component_map


def _validate_host_and_rows(rendering: dict, expected: dict[str, dict], source_context: dict,
                            context_components: dict[str, dict], source_ppu: float | None,
                            documents: list[dict], rendering_sha: str | None, gaps: list[dict]) -> None:
    groups: dict[str, list[dict]] = {}
    for sid, row in expected.items():
        prefab = row.get("sourcePrefabId")
        if not isinstance(prefab, str) or not prefab:
            gaps.append(_gap("SPINE_CANVAS_RENDERING_PREFAB_ID_MISSING", source_id=sid))
            continue
        groups.setdefault(prefab, []).append(row)
    saved_docs = [doc for doc in documents if doc.get("phase") == "saved-prefab-reopen"]
    by_prefab = {}
    for doc in saved_docs:
        prefab = doc.get("sourcePrefabId")
        if not isinstance(prefab, str) or not prefab or prefab in by_prefab:
            gaps.append(_gap("SPINE_CANVAS_SAVED_DOCUMENT_PREFAB_DUPLICATE_OR_MISSING", source_id=prefab if isinstance(prefab, str) else None))
            continue
        by_prefab[prefab] = doc
    if set(by_prefab) != set(groups):
        gaps.append(_gap("SPINE_CANVAS_SAVED_DOCUMENT_PREFAB_DENOMINATOR_MISMATCH",
                         missing=sorted(set(groups) - set(by_prefab)), extra=sorted(set(by_prefab) - set(groups))))

    manifest_sha = rendering.get("sourceManifestSha256")
    inner_sha = source_context.get("evidenceSha256")
    data_assets = rendering.get("dataAssets")
    data_map = {}
    if not isinstance(data_assets, list):
        gaps.append(_gap("SPINE_CANVAS_RENDERING_DATA_ASSETS_INVALID"))
        data_assets = []
    for data in data_assets:
        if not isinstance(data, dict):
            gaps.append(_gap("SPINE_CANVAS_RENDERING_DATA_ASSET_ROW_INVALID"))
            continue
        data_id = data.get("sourceDataAssetId")
        if not isinstance(data_id, str) or not data_id or data_id in data_map:
            gaps.append(_gap("SPINE_CANVAS_RENDERING_DATA_ASSET_ID_INVALID"))
            continue
        data_map[data_id] = data
    target_units = rendering.get("unitMapping", {}).get("targetUnitsPerSourcePixel") if isinstance(rendering.get("unitMapping"), dict) else None

    for prefab, sources in groups.items():
        doc = by_prefab.get(prefab)
        if doc is None:
            continue
        if doc.get("contract") != "monkey-static-spine-rendering-readback/1" or doc.get("schemaVersion") != 1:
            gaps.append(_gap("SPINE_CANVAS_SAVED_DOCUMENT_CONTRACT_INVALID", source_id=prefab))
        if (doc.get("sourceManifestSha256") != manifest_sha or doc.get("renderingPlanSha256") != rendering_sha or
                doc.get("sourcePrefabId") != prefab):
            gaps.append(_gap("SPINE_CANVAS_SAVED_DOCUMENT_PIN_MISMATCH", source_id=prefab))
        if doc.get("sourceCanvasContextEvidencePath") != EVIDENCE_PATH:
            gaps.append(_gap("SPINE_CANVAS_EVIDENCE_PATH_INVALID", source_id=prefab))
        file_sha = doc.get("sourceCanvasContextEvidenceFileSha256")
        if not isinstance(file_sha, str) or not _SHA256.fullmatch(file_sha):
            gaps.append(_gap("SPINE_CANVAS_EVIDENCE_FILE_HASH_INVALID", source_id=prefab))
        if doc.get("sourceCanvasContext") != source_context:
            gaps.append(_gap("SPINE_CANVAS_EMBEDDED_CONTEXT_DIFFERS_FROM_FILE", source_id=prefab))
        doc_rows = doc.get("components")
        if not isinstance(doc_rows, list) or any(not isinstance(row, dict) for row in doc_rows):
            gaps.append(_gap("SPINE_CANVAS_SAVED_COMPONENT_ROWS_INVALID", source_id=prefab))
            continue
        expected_by_id = {row.get("sourceComponentId"): row for row in sources}
        actual_by_id = {}
        for row in doc_rows:
            sid = row.get("sourceComponentId")
            if not isinstance(sid, str) or not sid or sid in actual_by_id:
                gaps.append(_gap("SPINE_CANVAS_SAVED_COMPONENT_ID_INVALID", source_id=sid if isinstance(sid, str) else prefab))
                continue
            actual_by_id[sid] = row
        if set(actual_by_id) != set(expected_by_id):
            gaps.append(_gap("SPINE_CANVAS_SAVED_COMPONENT_DENOMINATOR_MISMATCH", source_id=prefab,
                             missing=sorted(set(expected_by_id) - set(actual_by_id)),
                             extra=sorted(set(actual_by_id) - set(expected_by_id))))
        host_by_hash = {}
        for sid, source in expected_by_id.items():
            saved = actual_by_id.get(sid)
            if saved is None:
                continue
            source_context_row = context_components.get(sid)
            if (saved.get("sourceDataAssetId") != source.get("sourceDataAssetId") or
                    saved.get("sourceComponentEnabled") is not source.get("sourceComponentEnabled") or
                    saved.get("sourceVisible") is not source.get("sourceVisible")):
                gaps.append(_gap("SPINE_CANVAS_SAVED_ROW_SOURCE_FIELDS_MISMATCH", source_id=sid))
            if source_context_row is not None and source.get("eligible") is True and (
                    saved.get("sourceNodeActive") is not source_context_row.get("sourceNodeActive") or
                    saved.get("sourceNodeActivityVerified") is not True):
                gaps.append(_gap("SPINE_CANVAS_SAVED_ROW_NODE_ACTIVITY_MISMATCH", source_id=sid))
            source_component = context_components.get(sid)
            if source_component is None:
                continue
            if source.get("eligible") is not True:
                if saved.get("controlledHostContextEvidence") is not None:
                    gaps.append(_gap("SPINE_CANVAS_INELIGIBLE_ROW_HAS_HOST_PROOF", source_id=sid))
                continue
            host = saved.get("controlledHostContextEvidence")
            host_sha = saved.get("controlledHostContextEvidenceSha256")
            expected_context_index = source_component.get("sourceCanvasContextIndex")
            source_canvas = next((row for row in source_context.get("contexts", []) if isinstance(row, dict) and
                                  row.get("contextIndex") == expected_context_index), None)
            if not isinstance(host, dict):
                gaps.append(_gap("SPINE_CANVAS_CONTROLLED_HOST_EVIDENCE_MISSING", source_id=sid))
                continue
            if (not isinstance(host_sha, str) or not _SHA256.fullmatch(host_sha) or
                    host.get("evidenceSha256") != host_sha):
                gaps.append(_gap("SPINE_CANVAS_CONTROLLED_HOST_HASH_BINDING_INVALID", source_id=sid))
            if (host.get("schemaVersion") != 1 or host.get("contract") != "monkey-static-spine-controlled-prefab-host/1" or
                    host.get("contextKind") != "created-by-monkey-owned-prefab-ui-context" or host.get("verified") is not True or
                    host.get("sourceContextVerified") is not True or host.get("sourceCanvasScalerPresent") is not True or
                    host.get("controlledHostCanvasScalerAbsent") is not True or host.get("controlledHostGeometryMatchesPlan") is not True or
                    host.get("controlledHostCanvasRenderMode") != "WorldSpace" or host.get("controlledHostScaleMode") != "none" or
                    host.get("sourceCanvasEvidenceSha256") != inner_sha or host.get("sourceManifestSha256") != manifest_sha or
                    host.get("renderingPlanSha256") != rendering_sha):
                gaps.append(_gap("SPINE_CANVAS_CONTROLLED_HOST_CONTRACT_MISMATCH", source_id=sid))
            if source_canvas is None or host.get("sourceCanvasRenderMode") != source_canvas.get("sourceCanvasRenderMode"):
                gaps.append(_gap("SPINE_CANVAS_CONTROLLED_HOST_SOURCE_MODE_MISMATCH", source_id=sid))
            host_ppu = host.get("controlledHostReferencePixelsPerUnit")
            source_host_ppu = host.get("sourceCanvasReferencePixelsPerUnit")
            scaler_host_ppu = host.get("sourceScalerReferencePixelsPerUnit")
            if (source_ppu is None or not _close(host_ppu, source_ppu) or not _close(source_host_ppu, source_ppu) or
                    not _close(scaler_host_ppu, source_ppu) or not _close(saved.get("controlledHostCanvasReferencePixelsPerUnit"), source_ppu)):
                gaps.append(_gap("SPINE_CANVAS_CONTROLLED_HOST_PPU_MISMATCH", source_id=sid))
            if (saved.get("sourceCanvasContextEvidenceSha256") != inner_sha or
                    saved.get("sourceCanvasContextVerified") is not True or saved.get("controlledHostContextVerified") is not True or
                    saved.get("sourceCanvasContextKind") not in ("saved-persistent-owner-with-controlled-reopen-peer", "controlled-prefab-reopened-owner") or
                    saved.get("controlledHostContextKind") != host.get("contextKind") or
                    saved.get("controlledHostCanvasRenderMode") != "WorldSpace" or
                    not _close(saved.get("canvasReferencePixelsPerUnit"), source_ppu) or
                    not _close(saved.get("sourceCanvasReferencePixelsPerUnit"), source_ppu) or
                    not _close(saved.get("sourceScalerReferencePixelsPerUnit"), source_ppu)):
                gaps.append(_gap("SPINE_CANVAS_SAVED_ROW_CONTEXT_BINDING_MISMATCH", source_id=sid))
            if host_sha:
                prior = host_by_hash.get(host_sha)
                if prior is not None and prior != host:
                    gaps.append(_gap("SPINE_CANVAS_CONTROLLED_HOST_HASH_COLLISION", source_id=sid))
                host_by_hash[host_sha] = host

            data = data_map.get(source.get("sourceDataAssetId"))
            spec = data.get("factorySpec") if isinstance(data, dict) else None
            source_scale = spec.get("sourceDefaultScale") if isinstance(spec, dict) else None
            spec_units = spec.get("targetUnitsPerSourcePixel") if isinstance(spec, dict) else None
            if (not _number(source_scale) or source_scale <= 0 or not _number(target_units) or target_units <= 0 or
                    not _number(spec_units) or not _close(spec_units, target_units, _SCALE_TOLERANCE) or
                    saved.get("sourceDefaultScale") != source_scale or
                    not _close(saved.get("targetUnitsPerSourcePixel"), target_units, _SCALE_TOLERANCE) or source_ppu is None):
                gaps.append(_gap("SPINE_CANVAS_SCALE_INPUTS_INVALID", source_id=sid))
            else:
                expected_scale = source_scale * target_units / source_ppu
                actual_scale = saved.get("dataScale")
                if not _number(actual_scale) or abs(actual_scale - expected_scale) > _SCALE_TOLERANCE:
                    gaps.append(_gap("SPINE_CANVAS_DATA_SCALE_EQUATION_MISMATCH", source_id=sid,
                                     expected=expected_scale, actual=actual_scale))
        if len(host_by_hash) > 1:
            gaps.append(_gap("SPINE_CANVAS_PREFAB_HAS_MULTIPLE_CONTROLLED_HOSTS", source_id=prefab,
                             hostEvidenceSha256s=sorted(host_by_hash)))


def verify_context_evidence(rendering: dict, candidate_root: str | Path,
                            documents=None) -> list[dict]:
    """Validate source Canvas and controlled-host evidence for saved Spine rows.

    Old plans without the context contract remain accepted only when the fixed
    evidence file is absent. Presence of that file opts into strict validation.
    ``documents`` may be parsed readback envelopes, a path-to-envelope mapping,
    or ``None`` to load saved Spine envelopes from the candidate readback folder.
    """
    if not isinstance(rendering, dict):
        return [_gap("SPINE_CANVAS_RENDERING_PLAN_INVALID")]
    try:
        root = Path(candidate_root).resolve(strict=True)
    except OSError as error:
        return [_gap("SPINE_CANVAS_CANDIDATE_ROOT_UNREADABLE", message=str(error))]
    context_lexical = root / EVIDENCE_PATH
    context_exists = context_lexical.exists() or context_lexical.is_symlink()
    required = rendering.get("sourceCanvasContextEvidenceContract") == CONTRACT
    if rendering.get("sourceCanvasContextEvidenceContract") not in (None, CONTRACT):
        return [_gap("SPINE_CANVAS_CONTEXT_CONTRACT_UNSUPPORTED")]
    if not context_exists and not required:
        return []
    gaps: list[dict] = []
    if not context_exists:
        return [_gap("SPINE_CANVAS_CONTEXT_EVIDENCE_REQUIRED_FILE_MISSING", path=EVIDENCE_PATH)]
    try:
        context_path = _relative_file(root, EVIDENCE_PATH)
        context_raw, context = _read_json(context_path)
        context_file_sha = sha(context_raw)
    except Exception as error:
        return [_gap("SPINE_CANVAS_CONTEXT_EVIDENCE_FILE_UNREADABLE", path=EVIDENCE_PATH, message=str(error))]

    expected = _expected_components(rendering, gaps)
    rendering_sha, import_plan = _load_candidate_inputs(root, rendering, gaps)
    if rendering.get("sourceCanvasContextEvidenceContract") == CONTRACT and context.get("contract") != CONTRACT:
        gaps.append(_gap("SPINE_CANVAS_CONTEXT_REQUIRED_CONTRACT_MISMATCH"))
    import_nodes = _validate_import_plan(rendering, import_plan, expected, context, gaps)
    source_ppu, context_components = _validate_source_context(rendering, expected, context,
        import_nodes, rendering_sha, gaps)
    try:
        readbacks = _readback_documents(documents, root)
    except Exception as error:
        gaps.append(_gap("SPINE_CANVAS_READBACK_DOCUMENTS_UNREADABLE", message=str(error)))
        readbacks = []
    saved = [row for row in readbacks if row.get("phase") == "saved-prefab-reopen"]
    if not saved:
        gaps.append(_gap("SPINE_CANVAS_SAVED_READBACKS_MISSING"))
    for doc in saved:
        if doc.get("sourceCanvasContextEvidencePath") != EVIDENCE_PATH:
            gaps.append(_gap("SPINE_CANVAS_EVIDENCE_PATH_INVALID", source_id=doc.get("sourcePrefabId")))
        if doc.get("sourceCanvasContextEvidenceFileSha256") != context_file_sha:
            gaps.append(_gap("SPINE_CANVAS_EVIDENCE_FILE_HASH_MISMATCH", source_id=doc.get("sourcePrefabId")))
        if doc.get("sourceCanvasContext") != context:
            gaps.append(_gap("SPINE_CANVAS_EMBEDDED_CONTEXT_DIFFERS_FROM_FILE", source_id=doc.get("sourcePrefabId")))
    _validate_host_and_rows(rendering, expected, context, context_components, source_ppu,
                            readbacks, rendering_sha, gaps)
    return gaps
