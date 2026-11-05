"""Build an exact static Mask contract for a frozen Cocos 2.4.15 plan.

The source plan is not rewritten or normalized. Every source ``cc.Mask`` row,
including prefab-sync occurrences and masks outside an active draw queue, gets
an identity row from its hash-bound component and source manifest evidence.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path

from .prefab_static_mask_sort import (
    StaticMaskSortError,
    _bound_manifest,
    _origin_rows,
    _raw_component,
)


CONTRACT = "monkey-static-mask-continuation/1"
SOURCE_PROFILE = "cocos-2.4.15-bundle"
SOURCE_VERSION = "2.4.15"
SOURCE_ENGINE_PATH = "cocos2d/core/components/CCMask.js"
SOURCE_ENGINE_URL = "https://raw.githubusercontent.com/cocos/cocos-engine/v2.4.15/cocos2d/core/components/CCMask.js"
SOURCE_ENGINE_SHA256 = "33484e873f07be39fa6433c22819609bc52e51419992ffe8d230d68c453017a6"

_DEFAULTS = {
    "maskType": {"sourceProperty": "_type", "serializedKeys": ["_type", "_N$type"], "value": 0, "jsonValue": "0"},
    "inverted": {"sourceProperty": "inverted", "serializedKeys": ["_inverted", "_N$inverted"], "value": False, "jsonValue": "false"},
    "alphaThreshold": {"sourceProperty": "alphaThreshold", "serializedKeys": ["_alphaThreshold", "_N$alphaThreshold"], "value": 0.1, "jsonValue": "0.1"},
}


class StaticMaskContinuationError(ValueError):
    """Raised when source Mask identity or contract coverage is incomplete."""


def _source_profile(plan: Mapping, manifest: Mapping) -> None:
    if manifest.get("sourceProfile") != SOURCE_PROFILE or manifest.get("sourceVersion") != SOURCE_VERSION:
        raise StaticMaskContinuationError("source Mask defaults require the pinned Cocos Creator 2.4.15 profile")
    try:
        _bound_manifest(plan, manifest)
    except StaticMaskSortError as exc:
        raise StaticMaskContinuationError(str(exc)) from exc


def _component_origins(plan: Mapping) -> dict[str, str]:
    origins: dict[str, str] = {}
    rows = list(plan.get("staticAnimationComponentOrigins", []))
    for relation in plan.get("syncPrefabBindings", []):
        if not isinstance(relation, Mapping):
            raise StaticMaskContinuationError("source component origin relation is malformed")
        rows.extend(relation.get("componentOrigins", []))
    for row in rows:
        if not isinstance(row, Mapping):
            raise StaticMaskContinuationError("source component origin row is malformed")
        instance, template = row.get("instanceSourceId"), row.get("templateSourceId")
        if not isinstance(instance, str) or not instance or not isinstance(template, str) or not template:
            raise StaticMaskContinuationError("source component origin identity is absent")
        prior = origins.get(instance)
        if prior is not None and prior != template:
            raise StaticMaskContinuationError(f"source component origin is ambiguous: {instance}")
        origins[instance] = template
    for instance in origins:
        cursor, seen = instance, set()
        while cursor in origins:
            if cursor in seen:
                raise StaticMaskContinuationError("source component origin cycle")
            seen.add(cursor)
            cursor = origins[cursor]
    return origins


def _with_origins(plan: Mapping, origins: Mapping[str, str]) -> dict:
    clone = dict(plan)
    clone["staticAnimationComponentOrigins"] = [
        {"instanceSourceId": source_id, "templateSourceId": template_id}
        for source_id, template_id in sorted(origins.items())
    ]
    return clone


def _effective_activity(plan: Mapping, node_id: str) -> tuple[bool, bool]:
    nodes = plan.get("nodes")
    if not isinstance(nodes, list):
        raise StaticMaskContinuationError("source node activity denominator is absent")
    node_map = {}
    for node in nodes:
        if not isinstance(node, Mapping) or not isinstance(node.get("sourceId"), str):
            raise StaticMaskContinuationError("source node activity row is malformed")
        if node["sourceId"] in node_map:
            raise StaticMaskContinuationError(f"source node identity repeats: {node['sourceId']}")
        node_map[node["sourceId"]] = node
    self_node = node_map.get(node_id)
    if self_node is None or type(self_node.get("active")) is not bool:
        raise StaticMaskContinuationError(f"source Mask node activity is not typed: {node_id}")
    self_active = self_node["active"]
    cursor, seen = node_id, set()
    while cursor is not None:
        if cursor in seen:
            raise StaticMaskContinuationError("source node hierarchy contains a cycle")
        seen.add(cursor)
        node = node_map.get(cursor)
        if node is None or type(node.get("active")) is not bool:
            raise StaticMaskContinuationError(f"source ancestor activity is absent: {cursor}")
        if not node["active"]:
            return self_active, False
        cursor = node.get("parent")
    return self_active, True


def _queue_denominator(plan: Mapping) -> tuple[set[str], set[str]]:
    queues = plan.get("staticSortQueue")
    if not isinstance(queues, list):
        raise StaticMaskContinuationError("source static-sort queue denominator is malformed")
    scoped_nodes, event_ids, seen_event_ids = set(), set(), set()
    for queue in queues:
        if not isinstance(queue, Mapping) or not isinstance(queue.get("rootScope"), str):
            raise StaticMaskContinuationError("source static-sort queue row is malformed")
        scoped_nodes.add(queue["rootScope"])
        child_order = queue.get("sourceChildOrder")
        if not isinstance(child_order, list):
            raise StaticMaskContinuationError("source static-sort child-order denominator is absent")
        for item in child_order:
            if not isinstance(item, Mapping) or not isinstance(item.get("node"), str):
                raise StaticMaskContinuationError("source static-sort child-order row is malformed")
            scoped_nodes.add(item["node"])
            children = item.get("children")
            if not isinstance(children, list) or any(not isinstance(child, str) for child in children):
                raise StaticMaskContinuationError("source static-sort child-order children are malformed")
            scoped_nodes.update(children)
        masks = queue.get("masks")
        if not isinstance(masks, list):
            raise StaticMaskContinuationError("source static-sort mask-event denominator is malformed")
        for mask in masks:
            if not isinstance(mask, Mapping) or not isinstance(mask.get("sourceId"), str):
                raise StaticMaskContinuationError("source static-sort mask event is malformed")
            source_id = mask["sourceId"]
            if source_id in seen_event_ids:
                raise StaticMaskContinuationError(f"source Mask has duplicate active queue events: {source_id}")
            seen_event_ids.add(source_id)
            event_ids.add(source_id)
    return scoped_nodes, event_ids


def _validate_queue_match(row: Mapping, event: Mapping) -> None:
    for key in ("sourceId", "nativeId", "node", "maskType", "enabled", "inverted", "alphaThreshold"):
        if key in event and event.get(key) != row.get(key):
            raise StaticMaskContinuationError(f"source queue Mask field differs from pinned source: {row.get('sourceId')} ({key})")
    if "sourceFields" in event and event["sourceFields"] != row.get("sourceFields"):
        raise StaticMaskContinuationError(f"source queue Mask fields differ from pinned component: {row.get('sourceId')}")
    if "sourceFieldsJson" in event and event["sourceFieldsJson"] != row.get("sourceFieldsJson"):
        raise StaticMaskContinuationError(f"source queue Mask JSON differs from pinned component: {row.get('sourceId')}")


def build_contract(plan: Mapping, manifest: Mapping, *, source_engine_evidence: Mapping | None = None) -> dict:
    """Build the exact static mask contract from a hash-bound frozen source plan.

    All source ``cc.Mask`` components are included. Queue event presence is a
    separate fact: an inactive ancestor can remove a mask from RenderFlow while
    the saved source component still requires identity and field evidence.
    """
    if not isinstance(plan, Mapping) or not isinstance(manifest, Mapping):
        raise StaticMaskContinuationError("source plan and manifest must be mappings")
    _source_profile(plan, manifest)
    components = plan.get("components")
    if not isinstance(components, list):
        raise StaticMaskContinuationError("frozen source component denominator is absent")
    if any(not isinstance(component, Mapping) for component in components):
        raise StaticMaskContinuationError("frozen source component row is malformed")
    mask_components = [component for component in components
                       if isinstance(component, Mapping) and component.get("type") == "cc.Mask"]
    component_ids = [component.get("sourceId") for component in mask_components]
    if any(not isinstance(source_id, str) or not source_id for source_id in component_ids):
        raise StaticMaskContinuationError("source Mask component has no stable source ID")
    if len(component_ids) != len(set(component_ids)):
        raise StaticMaskContinuationError("frozen source Mask component IDs repeat")

    origins = _component_origins(plan)
    source_plan = _with_origins(plan, origins)
    engine_defaults = _verify_source_engine_evidence(source_engine_evidence) if source_engine_evidence is not None else None
    prepared = _origin_rows(source_plan, manifest, "cc.Mask", include_convertible_masks=True,
                            mask_engine_defaults=engine_defaults)
    by_id = {row.get("sourceId"): row for row in prepared}
    if len(by_id) != len(prepared) or set(by_id) != set(component_ids):
        raise StaticMaskContinuationError("source Mask material identity denominator differs from frozen components")

    # The source queue manifest is used only to validate event correspondence;
    # it never defines which saved Mask components receive identity rows.
    if "staticSortQueue" in plan:
        scoped_nodes, event_ids = _queue_denominator(plan)
    else:
        scoped_nodes, event_ids = set(), set()
    queue_events: dict[str, list[Mapping]] = {}
    for queue in plan.get("staticSortQueue", []) or []:
        for event in queue.get("masks", []) or []:
            queue_events.setdefault(event.get("sourceId"), []).append(event)
    if set(queue_events) != event_ids:
        raise StaticMaskContinuationError("source queue event identity map differs")
    if event_ids - set(component_ids):
        raise StaticMaskContinuationError("source queue contains Mask IDs outside the component denominator")

    defaults_applied = {key: [] for key in _DEFAULTS}
    rows = []
    for source_id in sorted(component_ids):
        row = by_id[source_id]
        component = next(item for item in mask_components if item.get("sourceId") == source_id)
        origin_id = row.get("sourceOriginId")
        raw = _raw_component(manifest, origin_id)
        row["sourceFieldsJson"] = json.dumps(row["sourceFields"], ensure_ascii=False,
                                             sort_keys=True, separators=(",", ":"))
        default_fields = []
        for field, default in _DEFAULTS.items():
            if not any(key in raw for key in default["serializedKeys"]):
                default_fields.append(field)
                defaults_applied[field].append(source_id)
        self_active, effective_active = _effective_activity(plan, row["node"])
        events = queue_events.get(source_id, [])
        if len(events) > 1:
            raise StaticMaskContinuationError(f"source Mask has duplicate active queue events: {source_id}")
        for event in events:
            _validate_queue_match(row, event)
        in_queue_scope = row["node"] in scoped_nodes
        expected_event = in_queue_scope and effective_active and row["enabled"]
        if expected_event and not events:
            raise StaticMaskContinuationError(f"active source Mask has no matching queue event: {source_id}")
        if events and not expected_event:
            raise StaticMaskContinuationError(f"source queue includes a non-rendering Mask event: {source_id}")
        if events:
            queue_disposition = "active-mask-barrier-event"
        elif in_queue_scope and not effective_active:
            queue_disposition = "outside-active-render-flow-inactive-ancestor"
        elif in_queue_scope and not row["enabled"]:
            queue_disposition = "outside-active-render-flow-disabled-mask"
        else:
            queue_disposition = "outside-static-sort-queue-scope"
        rows.append({
            **row,
            "sourceOriginId": origin_id,
            "sourceDefaultFields": default_fields,
            "sourceActiveSelf": self_active,
            "sourceActive": effective_active,
            "sourceQueueDisposition": queue_disposition,
        })

    defaults = []
    for field, value in _DEFAULTS.items():
        ids = sorted(defaults_applied[field])
        if ids:
            defaults.append({"field": field, "sourceProperty": value["sourceProperty"],
                             "value": value["jsonValue"], "sourceIds": ids})
    return {
        "schemaVersion": 1,
        "contract": CONTRACT,
        "sourceManifestSha256": plan["sourceManifestSha256"],
        "sourceProfile": SOURCE_PROFILE,
        "sourceVersion": SOURCE_VERSION,
        "sourceEngine": {"path": SOURCE_ENGINE_PATH, "sha256": SOURCE_ENGINE_SHA256,
                         "url": SOURCE_ENGINE_URL},
        "sourceDefaults": defaults,
        "masks": rows,
    }


def _mask_component_denominator(plan: Mapping) -> dict[str, Mapping]:
    components = plan.get("components")
    if not isinstance(components, list):
        raise StaticMaskContinuationError("frozen import component denominator is absent")
    rows = [row for row in components if isinstance(row, Mapping) and row.get("type") == "cc.Mask"]
    result = {}
    for row in rows:
        source_id = row.get("sourceId")
        if not isinstance(source_id, str) or not source_id or source_id in result:
            raise StaticMaskContinuationError("frozen import Mask component IDs are absent or duplicated")
        result[source_id] = row
    return result


def _assert_same_components(source_plan: Mapping, import_plan: Mapping) -> None:
    source_rows = _mask_component_denominator(source_plan)
    import_rows = _mask_component_denominator(import_plan)
    if set(source_rows) != set(import_rows):
        raise StaticMaskContinuationError("frozen import Mask component identity set differs from source plan")
    for source_id, source in source_rows.items():
        target = import_rows[source_id]
        for key in ("node", "nativeId", "enabled", "maskType", "inverted"):
            if target.get(key) != source.get(key):
                raise StaticMaskContinuationError(f"frozen import Mask component field differs: {source_id} ({key})")


def attach_contract(import_plan: Mapping, source_plan: Mapping, manifest: Mapping) -> dict:
    """Return a copy of an import plan with the validated Mask contract attached.

    Only ``staticMasks`` is changed. Existing component data, resource files,
    plan hashes, and serialization choices are preserved byte-for-byte at the
    value level; conflicting preexisting Mask contracts fail closed.
    """
    if not isinstance(import_plan, Mapping):
        raise StaticMaskContinuationError("frozen import plan must be a mapping")
    contract = build_contract(source_plan, manifest)
    if import_plan.get("sourceManifestSha256") != contract["sourceManifestSha256"]:
        raise StaticMaskContinuationError("frozen import plan source manifest pin differs")
    _assert_same_components(source_plan, import_plan)
    prior = import_plan.get("staticMasks")
    if prior not in (None, contract):
        raise StaticMaskContinuationError("frozen import plan has a conflicting static Mask contract")
    attached = copy.deepcopy(dict(import_plan))
    attached["staticMasks"] = copy.deepcopy(contract)
    return attached


def _verify_ir_mask_origins(plan: Mapping, ir: Mapping) -> None:
    components = ir.get("components") if isinstance(ir, Mapping) else None
    if not isinstance(components, list):
        raise StaticMaskContinuationError("frozen IR component denominator is absent")
    by_id: dict[str, list[Mapping]] = {}
    for row in components:
        if not isinstance(row, Mapping) or not isinstance(row.get("sourceId"), str):
            raise StaticMaskContinuationError("frozen IR component row is malformed")
        by_id.setdefault(row["sourceId"], []).append(row)
    origins = _component_origins(plan)
    source_masks = [row for row in plan.get("components", [])
                    if isinstance(row, Mapping) and row.get("type") == "cc.Mask"]
    for component in source_masks:
        source_id = component["sourceId"]
        origin_id, seen = source_id, set()
        while origin_id in origins:
            if origin_id in seen:
                raise StaticMaskContinuationError("source component origin cycle")
            seen.add(origin_id)
            origin_id = origins[origin_id]
        matches = by_id.get(origin_id, [])
        if len(matches) != 1 or matches[0].get("type") != "cc.Mask":
            raise StaticMaskContinuationError(f"source Mask plan/IR identity differs: {source_id}")


def _verify_source_engine_evidence(evidence: Mapping) -> dict:
    if (not isinstance(evidence, Mapping) or
            evidence.get("sourceVersion", SOURCE_VERSION) != SOURCE_VERSION):
        raise StaticMaskContinuationError("Cocos Mask engine source version evidence is absent")
    candidates = evidence.get("files")
    if candidates is None:
        candidates = [evidence.get("sourceEngine", evidence)]
    if not isinstance(candidates, list):
        raise StaticMaskContinuationError("Cocos Mask engine source evidence files are malformed")
    rows = [row for row in candidates if isinstance(row, Mapping) and
            row.get("logicalPath", row.get("path")) == SOURCE_ENGINE_PATH]
    if len(rows) != 1:
        raise StaticMaskContinuationError("Cocos Mask engine source pin is absent or ambiguous")
    row = rows[0]
    path = row.get("path")
    expected_sha = row.get("sha256")
    origin_url = row.get("originUrl", row.get("url"))
    if (not isinstance(path, str) or not Path(path).is_absolute() or
            expected_sha != SOURCE_ENGINE_SHA256 or origin_url != SOURCE_ENGINE_URL):
        raise StaticMaskContinuationError("Cocos Mask engine source pin metadata differs")
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise StaticMaskContinuationError("Cocos Mask engine source bytes are unavailable") from exc
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != SOURCE_ENGINE_SHA256 or ("bytes" in row and row["bytes"] != len(raw)):
        raise StaticMaskContinuationError("Cocos Mask engine source bytes differ from pinned v2.4.15 file")
    return {"path": SOURCE_ENGINE_PATH, "sha256": SOURCE_ENGINE_SHA256,
            "url": SOURCE_ENGINE_URL, "bytes": len(raw)}


def prepare(plan, ir, manifest, stage, source_evidence=None) -> dict:
    """Prepare a fresh stage with a source-bound Mask contract and evidence.

    ``stage`` must be a new module stage root. Source IR, manifest, engine
    evidence, and the parent plan are read-only. The output plan is a deep copy
    with only its static Mask contract attached.
    """
    if not isinstance(plan, Mapping) or not isinstance(ir, Mapping):
        raise StaticMaskContinuationError("source plan and frozen IR are required")
    _verify_ir_mask_origins(plan, ir)
    engine_evidence = _verify_source_engine_evidence(source_evidence)
    contract = build_contract(plan, manifest, source_engine_evidence=source_evidence)
    contract["sourceEngine"] = engine_evidence
    patched = copy.deepcopy(dict(plan))
    prior = patched.get("staticMasks")
    if prior not in (None, contract):
        raise StaticMaskContinuationError("source plan has a conflicting static Mask contract")
    patched["staticMasks"] = copy.deepcopy(contract)
    metadata = {
        "contract": CONTRACT,
        "schemaVersion": 1,
        "sourceManifestSha256": contract["sourceManifestSha256"],
        "sourceEngine": engine_evidence,
        "sourceMaskCount": len(contract["masks"]),
        "sourceMaskIds": [row["sourceId"] for row in contract["masks"]],
        "queueMaskEventCount": sum(row["sourceQueueDisposition"] == "active-mask-barrier-event"
                                    for row in contract["masks"]),
        "sourceDefaultFieldCounts": {field["field"]: len(field["sourceIds"])
                                      for field in contract["sourceDefaults"]},
        "sourceBusinessExecuted": False,
        "native": "not_run",
        "visual": "not_run",
    }
    stage_root = Path(stage)
    if not stage_root.is_dir():
        raise StaticMaskContinuationError("Mask continuation stage root is not an existing directory")
    module_root = stage_root / "mask_static_continuation"
    try:
        module_root.mkdir()
    except FileExistsError as exc:
        raise StaticMaskContinuationError("Mask continuation stage already exists") from exc
    from . import io
    io.write_json(module_root / "contract.json", contract)
    io.write_json(module_root / "metadata.json", metadata)
    return {"plan": patched, "summary": {
        "sourceMaskCount": len(contract["masks"]),
        "queueMaskEventCount": metadata["queueMaskEventCount"],
        "sourceDefaultFieldCounts": metadata["sourceDefaultFieldCounts"],
        "inactiveAncestorMaskIds": [row["sourceId"] for row in contract["masks"]
                                     if row["sourceQueueDisposition"] == "outside-active-render-flow-inactive-ancestor"],
        "native": "not_run",
        "visual": "not_run",
    }}


def validate_export_contract(plan: Mapping) -> dict:
    """Fail before native export when a source Mask lacks its consumer contract.

    Unity's importer requires an identity row for every source ``cc.Mask``,
    including inactive and non-queue Masks. This preflight mirrors that
    denominator and the Unity consumer's schema-1 compatibility rule so the
    error is reported during export, before starting an Editor.
    """
    if not isinstance(plan, Mapping):
        raise StaticMaskContinuationError("STATIC_MASK_PLAN_INVALID")
    components = plan.get("components")
    if not isinstance(components, list) or any(not isinstance(row, Mapping) for row in components):
        raise StaticMaskContinuationError("STATIC_MASK_COMPONENT_DENOMINATOR_INVALID")
    masks = [row for row in components if row.get("type") == "cc.Mask"]
    ids = [row.get("sourceId") for row in masks]
    if any(not isinstance(sid, str) or not sid for sid in ids) or len(ids) != len(set(ids)):
        raise StaticMaskContinuationError("STATIC_MASK_SOURCE_COMPONENT_IDENTITY_INVALID")
    contract = plan.get("staticMasks")
    if not masks and contract is None:
        return {"status": "not-required", "sourceMaskCount": 0, "sourceMaskIds": []}
    if not masks:
        raise StaticMaskContinuationError("STATIC_MASK_CONTRACT_PRESENCE_MARKER_MISMATCH: no source cc.Mask components")
    if not isinstance(contract, Mapping):
        raise StaticMaskContinuationError(
            "STATIC_MASK_CONTRACT_REQUIRED: sourceMaskCount=" + str(len(ids)) +
            "; sourceMaskIds=" + ",".join(sorted(ids)))
    rows = contract.get("masks")
    if not isinstance(rows, list):
        raise StaticMaskContinuationError("STATIC_MASK_CONTRACT_ROWS_MISSING: sourceMaskCount=" + str(len(ids)))
    row_ids = [row.get("sourceId") if isinstance(row, Mapping) else None for row in rows]
    if (any(not isinstance(sid, str) or not sid for sid in row_ids) or
            len(row_ids) != len(set(row_ids)) or set(row_ids) != set(ids)):
        raise StaticMaskContinuationError("STATIC_MASK_COMPONENT_IDENTITY_DENOMINATOR_MISMATCH")
    if not isinstance(plan.get("sourceManifestSha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", plan["sourceManifestSha256"]) or \
            contract.get("sourceManifestSha256") != plan["sourceManifestSha256"]:
        raise StaticMaskContinuationError("STATIC_MASK_SOURCE_MANIFEST_PIN_MISMATCH")

    legacy = (contract.get("schemaVersion") == 1 and contract.get("contract") in (None, ""))
    if legacy:
        node_ids = {row.get("sourceId") for row in plan.get("nodes", []) if isinstance(row, Mapping)}
        components_by_id = {row.get("sourceId"): row for row in masks}
        origins = _component_origins(plan)
        for sid, component in zip(row_ids, rows):
            if not isinstance(component, Mapping):
                raise StaticMaskContinuationError("STATIC_MASK_LEGACY_FIELDS_MISSING")
            threshold = component.get("alphaThreshold")
            source_fields_json = component.get("sourceFieldsJson")
            try:
                parsed_fields = json.loads(source_fields_json) if isinstance(source_fields_json, str) else None
            except (TypeError, ValueError):
                parsed_fields = None
            if component.get("sourceMaterialResolution") is not None:
                raise StaticMaskContinuationError("STATIC_MASK_LEGACY_DEFAULT_MATERIAL_UNPROVEN")
            required_material_fields = ("sourceMaterialId", "resolvedSourceMaterialId", "sourceEffectId",
                                        "sourceEffectName", "sourceEffectDocumentSha256")
            expected_origin = sid
            origin_seen = set()
            while expected_origin in origins:
                if expected_origin in origin_seen:
                    raise StaticMaskContinuationError("STATIC_MASK_LEGACY_FIELDS_MISSING: source origin cycle")
                origin_seen.add(expected_origin)
                expected_origin = origins[expected_origin]
            source_component = components_by_id[sid]
            fields_valid = (
                isinstance(sid, str) and sid in set(ids) and
                component.get("sourceId") == sid and component.get("sourceOriginId") == expected_origin and
                isinstance(component.get("nativeId"), str) and bool(component["nativeId"]) and
                component.get("nativeId") == source_component.get("nativeId") and
                isinstance(component.get("node"), str) and component["node"] in node_ids and
                component.get("node") == source_component.get("node") and
                type(component.get("maskType")) is int and component["maskType"] in (0, 1, 2) and
                component.get("maskType") == source_component.get("maskType") and
                type(component.get("enabled")) is bool and component.get("enabled") is source_component.get("enabled") and
                type(component.get("inverted")) is bool and component.get("inverted") is source_component.get("inverted") and
                type(threshold) in (int, float) and math.isfinite(threshold) and 0 <= threshold <= 1 and
                isinstance(parsed_fields, Mapping) and bool(source_fields_json) and
                all(isinstance(component.get(key), str) and component[key]
                    for key in required_material_fields))
            if "alphaThreshold" in source_component:
                fields_valid = fields_valid and component.get("alphaThreshold") == source_component["alphaThreshold"]
            if component.get("maskType") == 2:
                fields_valid = fields_valid and all(isinstance(component.get(key), str) and component[key]
                    for key in ("spriteFrameUuid", "unityMaskShaderPath", "unityMaskShaderSha256",
                                "unityMaskMaterialGuid", "unityMaskMaterialPath"))
            if not fields_valid:
                raise StaticMaskContinuationError("STATIC_MASK_LEGACY_FIELDS_MISSING: " + str(sid))
        return {"status": "legacy-complete", "sourceMaskCount": len(ids), "sourceMaskIds": sorted(ids)}
    if (contract.get("schemaVersion") != 1 or contract.get("contract") != CONTRACT or
            contract.get("sourceProfile") != SOURCE_PROFILE or contract.get("sourceVersion") != SOURCE_VERSION or
            contract.get("sourceEngine") != {"path": SOURCE_ENGINE_PATH, "sha256": SOURCE_ENGINE_SHA256,
                                               "url": SOURCE_ENGINE_URL} and
            not _source_engine_metadata_matches(contract.get("sourceEngine"))):
        raise StaticMaskContinuationError("STATIC_MASK_SOURCE_DEFAULTS_PIN_MISMATCH")

    expected_by_id = {row["sourceId"]: row for row in masks}
    contract_by_id = {row["sourceId"]: row for row in rows}
    node_map = plan.get("nodes")
    if not isinstance(node_map, list):
        raise StaticMaskContinuationError("STATIC_MASK_SOURCE_NODE_ACTIVITY_UNPROVEN")
    scoped_nodes, event_ids = _queue_denominator(plan) if "staticSortQueue" in plan else (set(), set())
    queue_rows: dict[str, list[Mapping]] = {}
    for queue in plan.get("staticSortQueue", []) or []:
        for event in queue.get("masks", []) or []:
            if not isinstance(event, Mapping) or not isinstance(event.get("sourceId"), str):
                raise StaticMaskContinuationError("STATIC_MASK_QUEUE_EVENT_INVALID")
            queue_rows.setdefault(event["sourceId"], []).append(event)
    if set(queue_rows) != event_ids or event_ids - set(ids):
        raise StaticMaskContinuationError("STATIC_MASK_QUEUE_EVENT_DENOMINATOR_MISMATCH")

    defaults_by_field = {key: set() for key in _DEFAULTS}
    for sid, component in expected_by_id.items():
        row = contract_by_id[sid]
        threshold = row.get("alphaThreshold")
        source_fields = row.get("sourceFields")
        fields_json = row.get("sourceFieldsJson")
        if (not isinstance(row.get("sourceOriginId"), str) or not row["sourceOriginId"] or
                row.get("node") != component.get("node") or row.get("nativeId") != component.get("nativeId") or
                row.get("enabled") is not component.get("enabled") or
                row.get("maskType") != component.get("maskType") or
                row.get("inverted") is not component.get("inverted") or
                not isinstance(source_fields, Mapping) or not isinstance(fields_json, str) or
                fields_json != json.dumps(source_fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")) or
                type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 1):
            raise StaticMaskContinuationError("STATIC_MASK_COMPONENT_FIELDS_MISMATCH: " + sid)
        resolution = row.get("sourceMaterialResolution")
        if resolution is not None:
            if (resolution != "engine-default-builtin" or
                    row.get("sourceMaterialResolverPath") != SOURCE_ENGINE_PATH or
                    row.get("sourceMaterialResolverSha256") != SOURCE_ENGINE_SHA256):
                raise StaticMaskContinuationError("STATIC_MASK_DEFAULT_MATERIAL_PROOF_INVALID: " + sid)
            # Re-resolve against the original manifest, not a provider receipt
            # or a claimed builtin name in this contract row.
            from .prefab_static_mask_sort import _mask_material_proof
            try:
                manifest = json.loads(Path(plan["sourceManifestPath"]).read_bytes())
                _bound_manifest(plan, manifest)
                original = _raw_component(manifest, row["sourceOriginId"])
                if dict(original) != dict(source_fields):
                    raise StaticMaskSortError("Mask default material source fields differ")
                material_proof = _mask_material_proof(manifest, sid.partition(":")[0], original,
                                                     engine_defaults=contract["sourceEngine"])
                if any(row.get(key) != value for key, value in material_proof.items()):
                    raise StaticMaskSortError("Mask default material identity differs")
            except (KeyError, OSError, ValueError, TypeError) as exc:
                raise StaticMaskContinuationError("STATIC_MASK_DEFAULT_MATERIAL_PROOF_INVALID: " + sid) from exc
        try:
            active_self, effective_active = _effective_activity(plan, row["node"])
        except (KeyError, StaticMaskContinuationError) as exc:
            raise StaticMaskContinuationError("STATIC_MASK_SOURCE_NODE_ACTIVITY_UNPROVEN: " + sid) from exc
        if row.get("sourceActiveSelf") is not active_self or row.get("sourceActive") is not effective_active:
            raise StaticMaskContinuationError("STATIC_MASK_COMPONENT_FIELDS_MISMATCH: " + sid)
        in_scope = row["node"] in scoped_nodes
        events = queue_rows.get(sid, [])
        should_have_event = in_scope and effective_active and component.get("enabled") is True
        expected_disposition = ("active-mask-barrier-event" if should_have_event else
            "outside-active-render-flow-inactive-ancestor" if in_scope and not effective_active else
            "outside-active-render-flow-disabled-mask" if in_scope and component.get("enabled") is False else
            "outside-static-sort-queue-scope")
        if (row.get("sourceQueueDisposition") != expected_disposition or len(events) != int(should_have_event) or
                len(events) > 1):
            raise StaticMaskContinuationError("STATIC_MASK_QUEUE_EVENT_DENOMINATOR_MISMATCH: " + sid)
        for event in events:
            _validate_queue_match(row, event)
        fields = row.get("sourceDefaultFields")
        if (not isinstance(fields, list) or any(field not in defaults_by_field for field in fields) or
                len(fields) != len(set(fields))):
            raise StaticMaskContinuationError("STATIC_MASK_SOURCE_DEFAULT_FIELD_INVALID: " + sid)
        for field in fields:
            defaults_by_field[field].add(sid)

    defaults = contract.get("sourceDefaults")
    if not isinstance(defaults, list):
        raise StaticMaskContinuationError("STATIC_MASK_SOURCE_DEFAULT_EVIDENCE_INVALID")
    observed = {}
    for row in defaults:
        if not isinstance(row, Mapping) or row.get("field") not in defaults_by_field or row["field"] in observed:
            raise StaticMaskContinuationError("STATIC_MASK_SOURCE_DEFAULT_EVIDENCE_INVALID")
        field = row["field"]
        source_property = "_type" if field == "maskType" else field
        expected_value = "0" if field == "maskType" else "false" if field == "inverted" else "0.1"
        source_ids = row.get("sourceIds")
        if (row.get("sourceProperty") != source_property or row.get("value") != expected_value or
                not isinstance(source_ids, list) or any(not isinstance(sid, str) for sid in source_ids) or
                len(source_ids) != len(set(source_ids)) or set(source_ids) != defaults_by_field[field]):
            raise StaticMaskContinuationError("STATIC_MASK_SOURCE_DEFAULT_SCOPE_MISMATCH: " + field)
        observed[field] = set(source_ids)
    if set(observed) != {field for field, values in defaults_by_field.items() if values}:
        raise StaticMaskContinuationError("STATIC_MASK_SOURCE_DEFAULT_SCOPE_MISMATCH")
    return {"status": "verified", "sourceMaskCount": len(ids), "sourceMaskIds": sorted(ids)}


def _source_engine_metadata_matches(value: object) -> bool:
    return (isinstance(value, Mapping) and value.get("path") == SOURCE_ENGINE_PATH and
            value.get("sha256") == SOURCE_ENGINE_SHA256 and value.get("url") == SOURCE_ENGINE_URL)

