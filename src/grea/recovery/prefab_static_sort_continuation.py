"""Prepare a pinned Unity static-sort contract from Cocos 2.4.15 source data.

This module reuses the existing source-backed sort queue planner and Unity
proxy DTO builder. Source SortRoot/SortOrder components remain source evidence;
coverage consumers may merge them only after the persistent identity markers and
the saved queue/render order have passed their independent readback checks.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from . import io
from .prefab_static_mask_sort import _raw_component
from .prefab_static_sort_queue import (
    StaticSortQueueError,
    prepare as prepare_sort_queue,
    to_unity_proxy_spec,
)


SCHEMA = "monkey-prefab-static-sort-continuation/1"
_MODULE_DIR = "static_sort_continuation"
_CONTRACT_FILE = "sort-queue-contract.json"
_SORT_TYPES = {"cc.SortRoot", "cc.SortOrder"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED_RAW_FIELDS = {
    "cc.SortRoot": {"__type__", "node"},
    "cc.SortOrder": {"__type__", "node", "_sortOrder"},
}
_IDENTITY_TYPES = {
    "cc.SortRoot": "Monkey.StaticSortQueueProxy.NativeStaticSortRootIdentity",
    "cc.SortOrder": "Monkey.StaticSortQueueProxy.NativeStaticSortOrderIdentity",
}


class StaticSortContinuationError(ValueError):
    """Pinned source sort semantics cannot be represented without inference."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _sort_rows(document: Mapping, label: str) -> dict[str, dict]:
    rows = document.get("components")
    if not isinstance(rows, list):
        raise StaticSortContinuationError(f"{label} component inventory is missing")
    result = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or row.get("type") not in _SORT_TYPES:
            continue
        source_id = row.get("sourceId")
        if not isinstance(source_id, str) or not source_id:
            raise StaticSortContinuationError(f"{label} sort component has no sourceId at index {index}")
        if source_id in result:
            raise StaticSortContinuationError(f"{label} has duplicate sort source identity: {source_id}")
        if type(row.get("enabled")) is not bool:
            raise StaticSortContinuationError(f"{label} sort component enabled state is unknown: {source_id}")
        result[source_id] = dict(row)
    return result


def _component_origins(plan: Mapping) -> dict[str, str]:
    origins = {}
    rows = list(plan.get("staticAnimationComponentOrigins", []) or [])
    for binding in plan.get("syncPrefabBindings", []) or []:
        if not isinstance(binding, Mapping):
            raise StaticSortContinuationError("sync prefab binding is malformed")
        component_rows = binding.get("componentOrigins", []) or []
        if not isinstance(component_rows, list):
            raise StaticSortContinuationError("sync component origin inventory is malformed")
        rows.extend(component_rows)
    for row in rows:
        if not isinstance(row, Mapping):
            raise StaticSortContinuationError("component source origin is malformed")
        instance, template = row.get("instanceSourceId"), row.get("templateSourceId")
        if not isinstance(instance, str) or not instance or not isinstance(template, str) or not template:
            raise StaticSortContinuationError("component source origin lacks exact IDs")
        previous = origins.get(instance)
        if previous is not None and previous != template:
            raise StaticSortContinuationError(f"conflicting component source origins: {instance}")
        origins[instance] = template
    return origins


def _resolve_origin(source_id: str, origins: Mapping[str, str]) -> str:
    cursor = source_id
    seen = set()
    while cursor in origins:
        if cursor in seen:
            raise StaticSortContinuationError(f"component source-origin cycle: {source_id}")
        seen.add(cursor)
        cursor = origins[cursor]
    return cursor


def _asset_id(source_id: str) -> str:
    asset_id, marker, _ = source_id.partition("#")
    if not marker:
        raise StaticSortContinuationError(f"sort source ID is not component-addressable: {source_id}")
    return asset_id


def _source_component_fields(source_id: str, source_type: str, manifest: Mapping) -> dict:
    raw = _raw_component(manifest, source_id)
    if raw.get("__type__") != source_type:
        raise StaticSortContinuationError(
            f"source component type differs at {source_id}: expected {source_type}, got {raw.get('__type__')!r}")
    expected_fields = _EXPECTED_RAW_FIELDS[source_type]
    if set(raw) != expected_fields:
        unknown = sorted(set(raw) - expected_fields)
        missing = sorted(expected_fields - set(raw))
        raise StaticSortContinuationError(
            f"source component fields are not the pinned built-in profile at {source_id}: "
            f"unknown={unknown}, missing={missing}")
    selector = source_id.split("#", 1)[1].split("/components/", 1)[0]
    try:
        expected_node_index = int(selector)
        source_node_index = raw["node"].get("__id__")
    except (AttributeError, TypeError, ValueError):
        raise StaticSortContinuationError(f"source component node reference is malformed: {source_id}")
    if type(source_node_index) is not int or source_node_index != expected_node_index:
        raise StaticSortContinuationError(f"source component node identity differs: {source_id}")
    if source_type == "cc.SortOrder":
        value = raw["_sortOrder"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise StaticSortContinuationError(f"source SortOrder has no finite numeric value: {source_id}")
    return dict(raw)


def _validate_source_binding(plan: Mapping, ir: Mapping, manifest: Mapping):
    expected_hash = plan.get("sourceManifestSha256")
    if not isinstance(expected_hash, str) or not _SHA256.fullmatch(expected_hash):
        raise StaticSortContinuationError("plan source manifest SHA-256 is missing")
    if manifest.get("sourceVersion") != "2.4.15" or manifest.get("sourceProfile") != "cocos-2.4.15-bundle":
        raise StaticSortContinuationError("source profile/version is outside the pinned Cocos 2.4.15 sort contract")
    if plan.get("sourceProfile") not in (None, manifest.get("sourceProfile")):
        raise StaticSortContinuationError("plan and source manifest profiles differ")
    if manifest.get("sourceManifestSha256", expected_hash) != expected_hash:
        raise StaticSortContinuationError("manifest source identity differs from plan")
    if ir.get("sourceManifestSha256") != expected_hash:
        raise StaticSortContinuationError("IR source manifest identity differs from plan")
    target = plan.get("targetProfile")
    if not isinstance(target, str) or not target.startswith("unity-"):
        raise StaticSortContinuationError("static sort continuation requires a Unity plan")
    manifest_path = plan.get("sourceManifestPath")
    if not isinstance(manifest_path, str) or not Path(manifest_path).is_absolute():
        raise StaticSortContinuationError("plan source manifest path is not absolute")
    raw_manifest = io.read(Path(manifest_path), max_bytes=128 * 1024 * 1024)
    if io.sha(raw_manifest) != expected_hash:
        raise StaticSortContinuationError("source manifest bytes differ from plan SHA-256")
    if _canonical(io.load(raw_manifest, max_nodes=8_000_000)) != _canonical(manifest):
        raise StaticSortContinuationError("in-memory source manifest differs from the pinned bytes")

    plan_rows = _sort_rows(plan, "plan")
    ir_rows = _sort_rows(ir, "IR")
    origins = _component_origins(plan)
    canonical_plan_ids = {_resolve_origin(source_id, origins) for source_id in plan_rows}
    prefab_assets = set()
    for prefab in plan.get("sourcePrefabs", []) or []:
        if not isinstance(prefab, Mapping) or not isinstance(prefab.get("sourceId"), str):
            raise StaticSortContinuationError("source Prefab inventory has an invalid identity")
        prefab_assets.add(prefab["sourceId"].split("#", 1)[0])
    selected_ir = {source_id: row for source_id, row in ir_rows.items()
                   if _asset_id(source_id) in prefab_assets}
    if set(selected_ir) != canonical_plan_ids:
        missing = sorted(set(selected_ir) - canonical_plan_ids)
        extra = sorted(canonical_plan_ids - set(selected_ir))
        raise StaticSortContinuationError(
            f"plan/IR source sort denominator differs: missingPlan={missing}, missingIR={extra}")

    source_rows = []
    for source_id, row in sorted(plan_rows.items()):
        source_origin = _resolve_origin(source_id, origins)
        source_type = row["type"]
        ir_row = selected_ir.get(source_origin)
        if not isinstance(ir_row, Mapping) or ir_row.get("type") != source_type:
            raise StaticSortContinuationError(f"plan/IR sort identity or type differs: {source_id}")
        fields = _source_component_fields(source_origin, source_type, manifest)
        if source_type == "cc.SortOrder":
            source_value = fields["_sortOrder"]
            for candidate, label in ((ir_row, "IR"), (row, "plan")):
                explicit = candidate.get("sortOrder", candidate.get("_sortOrder"))
                if explicit is not None and explicit != source_value:
                    raise StaticSortContinuationError(f"{label} SortOrder value differs from source: {source_id}")
        else:
            source_value = None
        source_node = row.get("node")
        if not isinstance(source_node, str) or not source_node:
            raise StaticSortContinuationError(f"sort component has no source node: {source_id}")
        source_rows.append({
            "sourceId": source_id,
            "sourceOriginId": source_origin,
            "sourceType": source_type,
            "sourceNodeId": source_node,
            "sourceEnabled": row["enabled"],
            "sourceFields": fields,
            "sourceFieldsSha256": io.sha(_canonical(fields)),
            "sourceSortOrder": source_value,
            "expectedMarkerType": _IDENTITY_TYPES[source_type],
            "nativeIdentityType": _IDENTITY_TYPES[source_type],
            "identityMarkerEnabled": False,
            "identityMarkerFieldsVerifiedRequired": True,
            "savedQueueReadbackRequired": True,
            "sourceBehaviorStatus": "dynamic_not_run",
            "dynamicSortBehavior": "not_restored",
            "presentationBoundary": "source-static-sort-queue-only",
        })
    return plan_rows, source_rows


def _validate_source_evidence(source_evidence, source_hash: str) -> list[dict]:
    if source_evidence is None:
        return []
    if not isinstance(source_evidence, Mapping) or source_evidence.get("sourceVersion") != "2.4.15":
        raise StaticSortContinuationError("optional source evidence version differs from pinned Cocos 2.4.15")
    if source_evidence.get("sourceManifestSha256") not in (None, source_hash):
        raise StaticSortContinuationError("optional source evidence is bound to another source manifest")
    files = source_evidence.get("files")
    if not isinstance(files, list) or not files:
        raise StaticSortContinuationError("optional source evidence has no pinned source files")
    seen = set()
    pinned = []
    for row in files:
        if not isinstance(row, Mapping):
            raise StaticSortContinuationError("optional source evidence file row is malformed")
        logical, path_value = row.get("logicalPath"), row.get("path")
        digest, size, origin_url = row.get("sha256"), row.get("bytes"), row.get("originUrl")
        if (not isinstance(logical, str) or not logical or "\\" in logical or
                PurePosixPath(logical).is_absolute() or any(part in ("", ".", "..") for part in PurePosixPath(logical).parts) or
                PurePosixPath(logical).as_posix() != logical or logical in seen):
            raise StaticSortContinuationError("optional source evidence logical path is unsafe or duplicated")
        if (not isinstance(path_value, str) or not Path(path_value).is_absolute() or
                not isinstance(digest, str) or not _SHA256.fullmatch(digest) or
                type(size) is not int or size < 0 or not isinstance(origin_url, str) or not origin_url):
            raise StaticSortContinuationError(f"optional source evidence pin is malformed: {logical}")
        try:
            source_path = io.safe(Path(path_value)).resolve(strict=True)
            raw = io.read(source_path, max_bytes=128 * 1024 * 1024)
        except Exception as error:
            raise StaticSortContinuationError(f"optional source evidence file is unavailable: {logical}") from error
        if source_path.is_symlink() or not source_path.is_file() or len(raw) != size or io.sha(raw) != digest:
            raise StaticSortContinuationError(f"optional source evidence file differs from its pin: {logical}")
        seen.add(logical)
        pinned.append({"logicalPath": logical, "path": str(source_path), "sha256": digest,
                       "bytes": size, "originUrl": origin_url})
    return pinned


def _public_summary(contract: Mapping, source_rows: list[dict], prefab_specs: list[dict], stage_manifest: dict) -> dict:
    return {
        "schema": SCHEMA,
        "status": "prepared_static_sort_queue_contract",
        "sourceProfile": "cocos-2.4.15-bundle",
        "sourceVersion": "2.4.15",
        "sourceManifestSha256": contract["sourceManifestSha256"],
        "sortComponentCount": len(source_rows),
        "sortOrderCount": sum(row["sourceType"] == "cc.SortOrder" for row in source_rows),
        "sortRootCount": sum(row["sourceType"] == "cc.SortRoot" for row in source_rows),
        "sourceComponentIds": [row["sourceId"] for row in source_rows],
        "prefabQueueCount": len(prefab_specs),
        "unityQueueMappedCount": sum(row.get("unityQueueMapped") is True for row in prefab_specs),
        "creatorQueueMappedCount": sum(row.get("creatorQueueMapped") is True for row in prefab_specs),
        "unsupportedCount": len(contract.get("unsupported", [])),
        "maskCount": sum(len(row.get("masks", [])) for row in prefab_specs),
        "moduleManifest": stage_manifest,
        "sourceBehaviorBoundary": "static import-state ordering only; dynamic runtime sort mutation not restored",
        "nativeCounterpartBoundary": "source SortRoot/SortOrder remain unconverted until verified marker and persistent queue readback are joined",
        "editor": "not_run",
        "player": "not_run",
    }


def prepare(plan: dict, ir: dict, manifest: dict, stage_root: str | Path, *, source_evidence=None) -> dict:
    """Attach verified native static-sort specs in a create-only module stage.

    No source files are modified. ``stage_root`` may contain sibling module
    products, but this module owns only the fresh ``static_sort_continuation``
    subtree and fails if that subtree already exists.
    """
    if not isinstance(plan, dict) or not isinstance(ir, dict) or not isinstance(manifest, dict):
        raise StaticSortContinuationError("static sort input documents must be objects")
    if plan.get("staticSortQueue") not in (None, []):
        raise StaticSortContinuationError("plan already has a staticSortQueue contract")
    plan_rows, source_rows = _validate_source_binding(plan, ir, manifest)
    pinned_source_files = _validate_source_evidence(source_evidence, plan["sourceManifestSha256"])

    try:
        queue_contract = prepare_sort_queue(plan, manifest)
    except (StaticSortQueueError, ValueError) as error:
        raise StaticSortContinuationError(f"source static sort queue preparation failed: {error}") from error
    occurrences = queue_contract.get("sortOrderOccurrences", []) + queue_contract.get("sortRootOccurrences", [])
    expected_source_ids = set(plan_rows)
    actual_source_ids = {row.get("sourceId") for row in occurrences if isinstance(row, Mapping)}
    if actual_source_ids != expected_source_ids or len(occurrences) != len(expected_source_ids):
        raise StaticSortContinuationError("source sort queue occurrence denominator differs from plan")
    if queue_contract.get("unsupported"):
        raise StaticSortContinuationError("source sort queue contains unsupported structures")
    if queue_contract.get("unityQueueMapped") is not True:
        raise StaticSortContinuationError("source sort queue cannot be mapped to Unity")

    prefab_specs = []
    prefab_rows = plan.get("sourcePrefabs")
    if not isinstance(prefab_rows, list) or not prefab_rows:
        raise StaticSortContinuationError("Unity source Prefab inventory is missing")
    prefab_roots = []
    for row in prefab_rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("root"), str) or not row.get("root"):
            raise StaticSortContinuationError("source Prefab root identity is missing")
        prefab_roots.append(row["root"])
    if len(prefab_roots) != len(set(prefab_roots)):
        raise StaticSortContinuationError("source Prefab root identities are duplicated")
    for root_scope in prefab_roots:
        try:
            spec = to_unity_proxy_spec(plan, manifest, root_scope)
        except (StaticSortQueueError, ValueError) as error:
            raise StaticSortContinuationError(f"Unity sort proxy contract failed at {root_scope}: {error}") from error
        if spec.get("unityQueueMapped") is not True or not isinstance(spec.get("drawEvents"), list):
            raise StaticSortContinuationError(f"Unity sort proxy has no verified draw queue at {root_scope}")
        prefab_specs.append(spec)

    stage = io.safe(Path(stage_root).absolute())
    if not stage.is_dir():
        raise StaticSortContinuationError("module stage root must already exist")
    input_paths = [io.safe(Path(plan["sourceManifestPath"]).absolute())]
    input_paths.extend(io.safe(Path(row["path"]).absolute()) for row in pinned_source_files)
    if any(stage == source or stage.is_relative_to(source) or source.is_relative_to(stage)
           for source in input_paths):
        raise StaticSortContinuationError("module output overlaps pinned source inputs")
    module_root = io.inside(stage, _MODULE_DIR)
    if module_root.exists() or module_root.is_symlink():
        raise StaticSortContinuationError("static sort module requires a fresh stage subtree")
    module_root.mkdir()
    try:
        contract = {
            "schema": SCHEMA,
            "sourceManifestSha256": queue_contract["sourceManifestSha256"],
            "sourceIrSha256": plan.get("sourceIrSha256"),
            "sourceProfile": manifest["sourceProfile"],
            "sourceVersion": manifest["sourceVersion"],
            "sourceEvidenceFiles": pinned_source_files,
            "sourceSortComponents": source_rows,
            "sortSemantics": queue_contract["sortSemantics"],
            "sortLimitations": queue_contract["sortLimitations"],
            "unsupported": queue_contract["unsupported"],
            "prefabSpecs": prefab_specs,
        }
        contract_path = module_root / _CONTRACT_FILE
        io.write_json(contract_path, contract)
        stage_manifest = io.finish(module_root, {
            "schemaVersion": 1,
            "schema": SCHEMA,
            "sourceManifestSha256": queue_contract["sourceManifestSha256"],
            "sourceIrSha256": plan.get("sourceIrSha256"),
            "sortComponentCount": len(source_rows),
            "sortOrderCount": sum(row["sourceType"] == "cc.SortOrder" for row in source_rows),
            "sortRootCount": sum(row["sourceType"] == "cc.SortRoot" for row in source_rows),
        })
        patched = copy.deepcopy(plan)
        bindings={row['sourceId']:row for row in source_rows}
        for component in patched['components']:
            source=bindings.get(component['sourceId'])
            if source is not None:
                component['nativeType']=source['expectedMarkerType']
                component['staticSortContinuationBinding']={
                    'sourceComponentId':source['sourceId'],'sourceNodeId':source['sourceNodeId'],
                    'expectedMarkerType':source['expectedMarkerType'],'savedQueueReadbackRequired':True}
        patched["staticSortQueue"] = prefab_specs
        patched["staticSortSourceComponents"] = source_rows
        patched["staticSortContinuation"] = {
            "schema": SCHEMA,
            "sourceManifestSha256": queue_contract["sourceManifestSha256"],
            "sourceIrSha256": plan.get("sourceIrSha256"),
            "sourceVersion": manifest["sourceVersion"],
            "sourceProfile": manifest["sourceProfile"],
            "moduleStage": _MODULE_DIR,
            "contractPath": _MODULE_DIR + "/" + _CONTRACT_FILE,
            "contractSha256": stage_manifest["files"][0]["sha256"],
            "sortComponentCount": len(source_rows),
            "sourceComponents": source_rows,
            "queueReadbackRequired": True,
            "dynamicSortBehavior": "not_restored",
        }
        summary = _public_summary(contract, source_rows, prefab_specs, stage_manifest)
        summary["moduleStage"] = str(module_root)
        summary["contractPath"] = str(contract_path)
        summary["contractSha256"] = stage_manifest["files"][0]["sha256"]
        return {"plan": patched, "summary": summary}
    except Exception:
        import shutil
        if module_root.is_dir() and not module_root.is_symlink():
            shutil.rmtree(module_root)
        raise
