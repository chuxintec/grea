"""Freeze exact Cocos Spine component data and references into non-rendering Unity carriers.

This module copies only pinned source bytes. It does not decode ASTC pages, parse
Spine animation data, create a renderer, or infer source defaults.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from .assets.spine import atlas_pages, binary_version
from .io import inside, safe, write_json, read
from .targets.unity import guid


CONTRACT = "monkey-prefab-static-spine-continuation/1"
READBACK_CONTRACT = "monkey-unity-static-spine-readback/1"
RUNTIME_REFERENCE_BACKUP = "cb453b884391dced615ab6c7d2d1407ca70bd7b49e5196020be4bb0fab8682a5"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_UUID = re.compile(r"^[0-9a-fA-F-]{32,36}$")
_UNITY_CONTENT_ROOT = "Assets/Game/Content/Spine/SourceData"
_EDITOR_HELPER = "Assets/Game/Editor/Conversion/UnityStaticSpineContinuation.cs"
_RUNTIME_REFERENCE = "Assets/Game/Presentation/Common/Layout/NativeStaticSpineReference.cs"
_RUNTIME_DATA = "Assets/Game/Presentation/Common/Layout/NativeStaticSpineData.cs"
_RUNTIME_REFERENCE_ROOT = "Assets/Plugins/Spine38"


class StaticSpineContinuationError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha_field(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise StaticSpineContinuationError(f"{label} must be lowercase SHA-256")
    return value


def _rel(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise StaticSpineContinuationError(f"{label} must be a canonical relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts) or path.as_posix() != value:
        raise StaticSpineContinuationError(f"{label} escapes its declared root")
    return value


def _source_file(manifest: dict, asset: dict, relative: str, inputs: dict[tuple[str, str], dict]) -> tuple[bytes, str, str]:
    bundle = asset.get("bundle", manifest.get("bundle"))
    if not isinstance(bundle, str) or bundle not in manifest.get("sourceRoots", {}):
        raise StaticSpineContinuationError(f"source root is absent for bundle {bundle!r}")
    relative = _rel(relative, "source native path")
    receipt = inputs.get((bundle, relative))
    if not isinstance(receipt, dict):
        raise StaticSpineContinuationError(f"source input receipt is absent: {bundle}:{relative}")
    source_root = safe(manifest["sourceRoots"][bundle])
    path = inside(source_root, relative).resolve(strict=True)
    try:
        path.relative_to(source_root)
    except ValueError as error:
        raise StaticSpineContinuationError(f"source input escapes bundle root: {relative}") from error
    if path.is_symlink() or not path.is_file():
        raise StaticSpineContinuationError(f"source input is not a regular file: {relative}")
    raw = read(path, max_bytes=128 * 1024 * 1024)
    expected = receipt.get("sha256")
    if not isinstance(expected, str) or not _SHA.fullmatch(expected) or _sha(raw) != expected:
        raise StaticSpineContinuationError(f"source input hash differs from frozen manifest: {relative}")
    expected_bytes = receipt.get("bytes", receipt.get("sizeBytes"))
    if expected_bytes is not None and expected_bytes != len(raw):
        raise StaticSpineContinuationError(f"source input length differs from frozen manifest: {relative}")
    return raw, expected, str(path)


def _component_origins(plan: dict) -> dict[str, str]:
    origins: dict[str, str] = {}
    for sync in plan.get("syncPrefabBindings", []) or []:
        if not isinstance(sync, dict):
            raise StaticSpineContinuationError("syncPrefabBindings contains a non-object row")
        for row in sync.get("componentOrigins", []) or []:
            if not isinstance(row, dict):
                raise StaticSpineContinuationError("sync component origin is not an object")
            instance_id, template_id = row.get("instanceSourceId"), row.get("templateSourceId")
            if not isinstance(instance_id, str) or not isinstance(template_id, str):
                raise StaticSpineContinuationError("sync component origin is missing exact source IDs")
            if instance_id in origins and origins[instance_id] != template_id:
                raise StaticSpineContinuationError(f"conflicting sync component origin: {instance_id}")
            origins[instance_id] = template_id
    return origins


def _raw_component(source_id: str, assets: dict[str, dict], origins: dict[str, str]) -> tuple[str, dict, dict]:
    template_id = origins.get(source_id, source_id)
    if "#" not in template_id:
        raise StaticSpineContinuationError(f"component ID has no source object ordinal: {template_id}")
    asset_id, selector = template_id.split("#", 1)
    asset = assets.get(asset_id)
    if not isinstance(asset, dict) or asset.get("kind") != "cc.Prefab":
        raise StaticSpineContinuationError(f"component source Prefab is absent: {asset_id}")
    instances = (asset.get("document") or {}).get("instances")
    if not isinstance(instances, list):
        raise StaticSpineContinuationError(f"source Prefab has no frozen instances: {asset_id}")
    if "/components/" in selector:
        node_text, component_text = selector.split("/components/", 1)
        try:
            node_index, component_index = int(node_text), int(component_text)
        except ValueError as error:
            raise StaticSpineContinuationError(f"invalid component selector: {template_id}") from error
        if not 0 <= node_index < len(instances):
            raise StaticSpineContinuationError(f"component node selector is out of bounds: {template_id}")
        node = instances[node_index]
        components = node.get("_components") if isinstance(node, dict) else None
        if not isinstance(components, list) or not 0 <= component_index < len(components):
            raise StaticSpineContinuationError(f"component ordinal is absent: {template_id}")
        component = components[component_index]
        if isinstance(component, dict) and set(component) == {"__id__"}:
            object_index = component["__id__"]
            if type(object_index) is not int or not 0 <= object_index < len(instances):
                raise StaticSpineContinuationError(f"component object reference is out of bounds: {template_id}")
            component = instances[object_index]
        node_index_for_component = node_index
    else:
        try:
            object_index = int(selector)
        except ValueError as error:
            raise StaticSpineContinuationError(f"invalid source object selector: {template_id}") from error
        if not 0 <= object_index < len(instances):
            raise StaticSpineContinuationError(f"source object selector is out of bounds: {template_id}")
        component = instances[object_index]
        node_ref = component.get("node") if isinstance(component, dict) else None
        node_index_for_component = node_ref.get("__id__") if isinstance(node_ref, dict) else None
    if not isinstance(component, dict) or component.get("__type__") != "sp.Skeleton":
        actual = component.get("__type__") if isinstance(component, dict) else type(component).__name__
        raise StaticSpineContinuationError(f"source component type differs at {template_id}: {actual}")
    if type(node_index_for_component) is not int or not 0 <= node_index_for_component < len(instances):
        raise StaticSpineContinuationError(f"source component node reference is missing: {template_id}")
    return template_id, asset, {"component": component, "node": instances[node_index_for_component],
                                "nodeIndex": node_index_for_component}


def _asset_uuid_map(assets: dict[str, dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for source_id, asset in assets.items():
        if ":" not in source_id:
            continue
        uuid = source_id.split(":", 1)[1]
        result.setdefault(uuid, []).append(asset)
    return result


def _resolve_source_uuid(uuid: str, uuid_assets: dict[str, list[dict]], assets: dict[str, dict]) -> tuple[dict | None, dict]:
    candidates = uuid_assets.get(uuid, [])
    if not candidates:
        return None, {"status": "source_uuid_not_found_in_pinned_manifest", "sourceUuid": uuid, "redirectChains": []}
    terminals: dict[str, dict] = {}
    chains = []
    for candidate in candidates:
        current = candidate
        chain = [current.get("sourceId")]
        seen = set()
        while current.get("kind") == "redirect":
            source_id = current.get("sourceId")
            if source_id in seen:
                raise StaticSpineContinuationError(f"source UUID redirect cycle: {uuid} via {chain}")
            seen.add(source_id)
            target_id = current.get("redirectTarget")
            if not isinstance(target_id, str) or not target_id:
                raise StaticSpineContinuationError(f"source UUID redirect has no exact redirectTarget: {source_id}")
            target = assets.get(target_id)
            if not isinstance(target, dict):
                raise StaticSpineContinuationError(f"source UUID redirect target is missing: {source_id} -> {target_id}")
            current = target
            chain.append(current.get("sourceId"))
        chains.append(chain)
        terminals[current["sourceId"]] = current
    if len(terminals) != 1:
        raise StaticSpineContinuationError(f"source UUID resolves ambiguously to multiple terminal manifest assets: {uuid}: {sorted(terminals)}")
    terminal = next(iter(terminals.values()))
    return terminal, {"status": "exact_redirect_chain_resolved", "sourceUuid": uuid,
                      "canonicalSourceAssetId": terminal["sourceId"], "redirectChains": chains}


def _collect_uuid_refs(value: Any, path: str = "") -> list[dict]:
    rows: list[dict] = []
    if isinstance(value, dict):
        uuid = value.get("__uuid__")
        if isinstance(uuid, str):
            rows.append({"fieldPath": path or "/", "sourceUuid": uuid})
        for key, child in value.items():
            if key == "__uuid__":
                continue
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            rows.extend(_collect_uuid_refs(child, path + "/" + escaped))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_collect_uuid_refs(child, path + "/" + str(index)))
    return rows


def _component_references(component: dict, uuid_assets: dict[str, list[dict]], assets: dict[str, dict]) -> list[dict]:
    refs = _collect_uuid_refs(component)
    for row in refs:
        asset, resolution = _resolve_source_uuid(row["sourceUuid"], uuid_assets, assets)
        row["sourceUuidResolution"] = resolution
        if asset is not None:
            row.update(sourceAssetId=asset["sourceId"], sourceAssetType=asset.get("kind"),
                       targetReferenceKind=("source-spine-data" if asset.get("kind") == "sp.SkeletonData"
                                            else "retained-source-material" if asset.get("kind") == "cc.Material"
                                            else "unsupported-source-object"))
        else:
            row.update(sourceAssetId=None, sourceAssetType=None, targetReferenceKind="source-asset-id-not-in-manifest",
                       resolutionStatus=resolution["status"])
    return refs


def _data_reference(component: dict, uuid_assets: dict[str, list[dict]], assets: dict[str, dict]) -> dict:
    keys = ("_N$skeletonData", "_skeletonData", "skeletonData")
    found = [(key, component[key]) for key in keys if key in component]
    if not found:
        return {"status": "source_reference_field_absent", "sourceDataAssetId": None, "sourceUuid": None,
                "fieldNames": []}
    refs = []
    for key, value in found:
        uuid = value.get("__uuid__") if isinstance(value, dict) else None
        if not isinstance(uuid, str):
            raise StaticSpineContinuationError(f"skeleton data reference {key} is not a source UUID object")
        asset, resolution = _resolve_source_uuid(uuid, uuid_assets, assets)
        if asset is None or asset.get("kind") != "sp.SkeletonData":
            raise StaticSpineContinuationError(f"skeleton data UUID is missing, ambiguous, or not SkeletonData after redirect resolution: {uuid}")
        refs.append((key, uuid, asset["sourceId"], resolution))
    unique = {item[2] for item in refs}
    if len(unique) != 1:
        raise StaticSpineContinuationError("conflicting serialized SkeletonData references are preserved but cannot be bound")
    return {"status": "source_reference_joined_exactly", "sourceDataAssetId": refs[0][2],
            "sourceUuid": refs[0][1], "fieldNames": [item[0] for item in refs],
            "uuidResolution": refs[0][3],
            "fieldUuidResolutions": [{"fieldName": item[0], "sourceUuid": item[1], "resolution": item[3]}
                                      for item in refs]}


def _field_state(fields: dict, key: str) -> dict:
    present = key in fields
    value = fields.get(key)
    if present:
        if isinstance(value, float) and not (value == value and abs(value) != float("inf")):
            raise StaticSpineContinuationError(f"non-finite serialized Spine field: {key}")
        return {"present": True, "value": value, "status": "serialized"}
    return {"present": False, "value": None, "status": "not_serialized_unknown"}


def _typed_field(name: str, state: dict) -> dict:
    value = state.get("value")
    result = {"name": name, "status": state.get("status"), "present": bool(state.get("present")),
              "boolValue": False, "numberValue": 0.0, "stringValue": ""}
    if type(value) is bool:
        result["boolValue"] = value
    elif type(value) in (int, float):
        result["numberValue"] = float(value)
    elif isinstance(value, str):
        result["stringValue"] = value
    return result


def _rebase_retained_sources(contract: dict, prefix: str) -> None:
    for key in ("payloads", "copies", "sourceEvidenceCopies"):
        rows = contract.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            source = row.get("source") if isinstance(row, dict) else None
            if isinstance(source, str):
                row["source"] = prefix + "/" + _rel(source, "retained source payload")
    rebased_evidence_objects = set()
    for row in contract.get("sourceEvidenceCopies", []) or []:
        if isinstance(row, dict) and isinstance(row.get("path"), str):
            row["path"] = prefix + "/" + _rel(row["path"], "retained source evidence path")
            rebased_evidence_objects.add(id(row))
    for asset in contract.get("assets", []) or []:
        if not isinstance(asset, dict):
            continue
        for key, evidence in asset.items():
            if key.endswith("EvidenceCopy") and isinstance(evidence, dict) and isinstance(evidence.get("path"), str) and id(evidence) not in rebased_evidence_objects:
                evidence["path"] = prefix + "/" + _rel(evidence["path"], "retained asset evidence path")
                rebased_evidence_objects.add(id(evidence))


def _merge_retained_contracts(existing: dict | None, added: dict) -> dict:
    if existing is None:
        return added
    if not isinstance(existing, dict) or existing.get("schema") != added.get("schema") or \
            existing.get("sourceManifestSha256") != added.get("sourceManifestSha256") or \
            existing.get("targetNamespace") != added.get("targetNamespace"):
        raise StaticSpineContinuationError("Spine retained material contract cannot merge with the plan's retained-assets identity")
    merged = dict(existing)
    for collection in ("assets", "payloads", "copies", "sourceEvidenceCopies"):
        old_rows = list(existing.get(collection) or [])
        new_rows = list(added.get(collection) or [])
        identity = "sourceId" if collection == "assets" else "path" if collection == "sourceEvidenceCopies" else "target"
        by_key = {row.get(identity): row for row in old_rows if isinstance(row, dict)}
        for row in new_rows:
            key = row.get(identity) if isinstance(row, dict) else None
            if key in by_key:
                old = by_key[key]
                if collection == "assets":
                    if _canonical(_retained_asset_semantics(old)) != _canonical(_retained_asset_semantics(row)):
                        raise StaticSpineContinuationError(f"retained asset identity collision with changed semantics: {key}")
                elif (old.get("sha256"), old.get("bytes")) != (row.get("sha256"), row.get("bytes")):
                    raise StaticSpineContinuationError(f"retained payload target collision with changed bytes: {key}")
                continue
            by_key[key] = row
        merged[collection] = list(by_key.values())
    references = list(existing.get("references") or [])
    reference_by_identity = {(row.get("sourceComponentId"), row.get("field"), row.get("index")): row
                             for row in references if isinstance(row, dict)}
    for row in added.get("references") or []:
        identity = (row.get("sourceComponentId"), row.get("field"), row.get("index"))
        previous = reference_by_identity.get(identity)
        if previous is not None:
            if _canonical(previous) != _canonical(row):
                raise StaticSpineContinuationError(f"retained source reference identity collision with changed target: {identity}")
            continue
        references.append(row)
        reference_by_identity[identity] = row
    merged["references"] = references
    gaps = list(existing.get("gaps") or []) + list(added.get("gaps") or [])
    merged["gaps"] = gaps
    if gaps:
        raise StaticSpineContinuationError("merged retained material contract contains source-reference gaps")
    return merged


def _retained_asset_semantics(row: dict) -> dict:
    value = json.loads(_canonical(row))
    for key, entry in value.items():
        if key.endswith("EvidenceCopy") and isinstance(entry, dict):
            entry.pop("path", None)
    return value


def _pinned_runtime_record(runtime_manifest: dict | None, runtime_manifest_path: str | Path | None,
                           runtime_manifest_sha256: str | None, runtime_assets_root: str | Path | None) -> dict:
    if runtime_manifest is None:
        return {"status": "not_required_for_nonrendering_source_byte_continuation",
                "assetDatabaseOrRendererUsed": False, "copied": False}
    if not all((runtime_manifest_path, runtime_manifest_sha256, runtime_assets_root)):
        raise StaticSpineContinuationError("optional Spine runtime pin requires manifest path/hash and backup root together")
    manifest_path = Path(runtime_manifest_path).resolve(strict=True)
    actual_manifest_sha = _sha(manifest_path.read_bytes())
    if _sha_field(runtime_manifest_sha256, "unity_runtime_manifest_sha256") != actual_manifest_sha:
        raise StaticSpineContinuationError("Spine runtime backup manifest bytes differ from the supplied pin")
    if runtime_manifest.get("producerManifestSHA256") != RUNTIME_REFERENCE_BACKUP:
        raise StaticSpineContinuationError("Spine runtime backup producer manifest SHA differs from the approved local backup")
    upstream = runtime_manifest.get("upstream", {})
    if (upstream.get("upstreamCommit") != "8b4844bd4b193ba9e54487ed397a777993cbad56" or
            upstream.get("sourceVersion") != "3.8.99 skeleton compatible branch3.8" or
            upstream.get("compiledAgainst") != "Unity6000.6.2f1"):
        raise StaticSpineContinuationError("Spine runtime backup identity/ABI differs from the pinned 3.8.99 Unity 6000.6.2f1 backup")
    root = Path(runtime_assets_root).resolve(strict=True)
    verified_files = []
    for row in runtime_manifest.get("files", []):
        relative = _rel(row.get("path"), "Spine runtime path")
        if not relative.startswith(_RUNTIME_REFERENCE_ROOT + "/"):
            raise StaticSpineContinuationError(f"Spine runtime file is outside the approved candidate plugin root: {relative}")
        path = inside(root, relative).resolve(strict=True)
        if path.is_symlink() or not path.is_file():
            raise StaticSpineContinuationError(f"Spine runtime backup entry is not a regular file: {relative}")
        raw = path.read_bytes()
        if _sha(raw) != row.get("sha256") or len(raw) != row.get("bytes"):
            raise StaticSpineContinuationError(f"Spine runtime backup file differs from its manifest: {relative}")
        verified_files.append({"path": relative, "sha256": row["sha256"], "bytes": len(raw)})
    return {"status": "optional_backup_read_only_verified_not_used", "manifestPath": str(manifest_path),
            "manifestSha256": actual_manifest_sha, "producerManifestSha256": RUNTIME_REFERENCE_BACKUP,
            "assetsRoot": str(root), "verifiedFiles": verified_files,
            "assetDatabaseOrRendererUsed": False, "copied": False}


def _prepare_impl(plan: dict, ir: dict, source_manifest: dict, output: str | Path, **pinned_runtime_inputs) -> dict:
    """Build a source-exact, non-rendering Spine reference plan and raw-byte payloads.

    Required pins are passed by the GREA bridge after it validates the request:
    ``source_manifest_path``, ``source_manifest_sha256`` and ``source_ir_sha256``.
    Optional SDK arguments are evidence only; this module does not need or copy
    the SDK because it does not instantiate a Spine runtime object or renderer.
    """
    if not isinstance(plan, dict) or not isinstance(ir, dict) or not isinstance(source_manifest, dict):
        raise StaticSpineContinuationError("plan, normalized IR, and source manifest must be parsed JSON objects")
    manifest_path = Path(pinned_runtime_inputs.get("source_manifest_path") or plan.get("sourceManifestPath", "")).resolve(strict=True)
    manifest_sha = _sha(manifest_path.read_bytes())
    expected_manifest_sha = _sha_field(pinned_runtime_inputs.get("source_manifest_sha256") or plan.get("sourceManifestSha256"),
                                       "source_manifest_sha256")
    expected_ir_sha = _sha_field(pinned_runtime_inputs.get("source_ir_sha256") or plan.get("sourceIrSha256"), "source_ir_sha256")
    if manifest_sha != expected_manifest_sha or plan.get("sourceManifestSha256") != manifest_sha:
        raise StaticSpineContinuationError("source manifest does not match the exact plan/request SHA")
    if ir.get("sourceManifestSha256") != manifest_sha or ir.get("sourceManifestPath") != str(manifest_path):
        raise StaticSpineContinuationError("normalized IR source manifest pin/path differs from the plan")
    if plan.get("sourceIrSha256") != expected_ir_sha:
        raise StaticSpineContinuationError("normalized IR hash differs from the exact plan/request SHA")
    try:
        disk_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StaticSpineContinuationError("pinned source manifest cannot be parsed as UTF-8 JSON") from error
    if disk_manifest != source_manifest:
        raise StaticSpineContinuationError("parsed source manifest differs from the pinned file bytes")
    if plan.get("projectLayout") != "monkey-project/2.0.0":
        raise StaticSpineContinuationError("unsupported target project layout for static Spine continuation")
    if plan.get("spineNativeStage") or plan.get("spineNativeBindingPlan"):
        raise StaticSpineContinuationError("static source continuation cannot be mixed with the legacy rendering Spine stage")
    if source_manifest.get("sourceVersion") != "2.4.15":
        raise StaticSpineContinuationError("source scale evidence in this continuation is pinned only to Cocos 2.4.15")

    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    module_root = destination / "spine_static_continuation"
    if module_root.exists() or module_root.is_symlink():
        raise StaticSpineContinuationError("Spine continuation module output already exists; choose a fresh plan identity")
    module_root.mkdir(parents=True)

    source_assets = source_manifest.get("assets")
    source_inputs = source_manifest.get("inputs")
    if not isinstance(source_assets, list) or not isinstance(source_inputs, list):
        raise StaticSpineContinuationError("source manifest requires assets and input receipts")
    assets = {row.get("sourceId"): row for row in source_assets if isinstance(row, dict) and row.get("sourceId")}
    if len(assets) != sum(isinstance(row, dict) and bool(row.get("sourceId")) for row in source_assets):
        raise StaticSpineContinuationError("source manifest asset sourceIds are missing or duplicated")
    inputs: dict[tuple[str, str], dict] = {}
    for row in source_inputs:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise StaticSpineContinuationError("source input receipt is malformed")
        key = (row.get("bundle", source_manifest.get("bundle")), row["path"])
        if key in inputs:
            raise StaticSpineContinuationError(f"duplicate source input receipt: {key}")
        inputs[key] = row
    uuid_assets = _asset_uuid_map(assets)
    source_skeleton_assets = [row for row in source_assets if isinstance(row, dict) and row.get("kind") == "sp.SkeletonData"]
    skeleton_by_id = {row["sourceId"]: row for row in source_skeleton_assets}
    if len(skeleton_by_id) != len(source_skeleton_assets):
        raise StaticSpineContinuationError("source SkeletonData identities are duplicated")

    component_rows = [row for row in plan.get("components", []) if isinstance(row, dict) and row.get("type") == "sp.Skeleton"]
    if not component_rows:
        fragment = {"schemaVersion": 1, "contract": CONTRACT, "sourceManifestSha256": manifest_sha,
                "sourceIrSha256": expected_ir_sha, "sourcePlanSha256": _sha(_canonical(plan)),
                "sourceManifestPath": str(manifest_path), "status": "no_spine_components",
                "components": [], "dataAssets": [], "payloadCopies": [], "supportFiles": [],
                "summary": {"componentCount": 0, "nonRendering": True, "dynamicBehavior": "not_restored"}}
        patched_plan = dict(plan)
        patched_plan["staticSpineContinuation"] = fragment
        return {"plan": patched_plan, "continuation": fragment, "status": fragment["status"]}
    component_ids = [row.get("sourceId") for row in component_rows]
    if any(not isinstance(value, str) or not value for value in component_ids) or len(set(component_ids)) != len(component_ids):
        raise StaticSpineContinuationError("Spine component sourceIds are missing or duplicated")
    origins = _component_origins(plan)
    refs_by_uuid = _asset_uuid_map(assets)
    raw_by_template: dict[str, tuple[str, dict, dict]] = {}
    components = []
    data_component_fields: dict[str, list[dict]] = {}
    for plan_row in component_rows:
        source_id = plan_row["sourceId"]
        template_id, prefab_asset, raw = _raw_component(source_id, assets, origins)
        raw_component = raw["component"]
        references = _component_references(raw_component, refs_by_uuid, assets)
        data_ref = _data_reference(raw_component, refs_by_uuid, assets)
        fields = {key: value for key, value in raw_component.items() if key not in ("__type__", "node")}
        fields_json = _canonical(fields).decode("utf-8")
        envelope_json = _canonical(raw_component).decode("utf-8")
        data_id = data_ref.get("sourceDataAssetId")
        if data_id:
            if data_id not in skeleton_by_id:
                raise StaticSpineContinuationError(f"component source data asset is not a SkeletonData manifest entry: {data_id}")
            data_component_fields.setdefault(data_id, []).append(fields)
        node_id = plan_row.get("node")
        if not isinstance(node_id, str) or not node_id:
            raise StaticSpineContinuationError(f"Spine component lacks a target source node ID: {source_id}")
        source_prefab_id = plan_row.get("sourcePrefabId") or source_id.split("#", 1)[0]
        known = {name: _field_state(fields, name) for name in (
            "defaultSkin", "_skinName", "defaultAnimation", "_animationName", "loop", "_playTimes",
            "timeScale", "premultipliedAlpha", "useTint", "debugSlots", "debugBones", "debugMesh",
            "enableBatch", "_preCacheMode")}
        component = {
            "sourceComponentId": source_id,
            "sourceTemplateComponentId": template_id,
            "sourcePrefabId": source_prefab_id,
            "sourceNodeId": node_id,
            "sourceTemplateNodeId": f"{template_id.split('#', 1)[0]}#{raw['nodeIndex']}",
            "sourceComponentType": raw_component.get("__type__"),
            "sourceComponentEnabled": plan_row.get("enabled"),
            "sourceComponentEnabledStatus": "plan-source-value" if isinstance(plan_row.get("enabled"), bool) else "unknown",
            "sourceDataReference": data_ref,
            "sourceFieldStates": known,
            "sourceFields": [_typed_field(name, state) for name, state in known.items()],
            "sourceFieldsJson": fields_json,
            "sourceFieldsSha256": _sha(fields_json.encode("utf-8")),
            "sourceComponentEnvelopeJson": envelope_json,
            "sourceComponentEnvelopeSha256": _sha(envelope_json.encode("utf-8")),
            "sourceNodeEnvelopeJson": _canonical(raw["node"]).decode("utf-8"),
            "sourceNodeEnvelopeSha256": _sha(_canonical(raw["node"])),
            "sourceObjectReferences": references,
            "sourceObjectReferencesJson": _canonical(references).decode("utf-8"),
            "sourceObjectReferencesSha256": _sha(_canonical(references)),
            "sourceOrigin": "sync-template" if source_id != template_id else "source-component",
            "nativeCarrierType": "NativeStaticSpineReference",
            "nativeCarrierStatus": "source-plan-pending-editor-create-readback",
            "renderingStatus": "not_rendered",
            "dynamicBehaviorStatus": "not_restored",
            "sourceCodeExecuted": False,
        }
        if data_id:
            data_component_fields[data_id][-1]["__sourceComponentId"] = source_id
        raw_by_template.setdefault(template_id, (source_id, prefab_asset, raw))
        components.append(component)

    unresolved_refs = [ref for component in components for ref in component["sourceObjectReferences"]
                       if ref.get("resolutionStatus") or ref.get("targetReferenceKind") not in ("source-spine-data", "retained-source-material")]
    if unresolved_refs:
        sample = [{"component": component["sourceComponentId"], "ref": ref} for component in components
                  for ref in component["sourceObjectReferences"]
                  if ref.get("resolutionStatus") or ref.get("targetReferenceKind") not in ("source-spine-data", "retained-source-material")][:8]
        raise StaticSpineContinuationError("Spine source object references are missing from the manifest or outside the supported exact data/material carrier: " +
                                           json.dumps(sample, ensure_ascii=False))
    missing_component_sources = [row["sourceComponentId"] for row in components
                                 if row["sourceDataReference"].get("sourceDataAssetId") is None]
    if missing_component_sources:
        raise StaticSpineContinuationError("Spine source components lack an exact serialized SkeletonData reference: " +
                                           ", ".join(missing_component_sources[:12]))

    # Read every original input byte verbatim; .astc.bytes payloads stay opaque TextAssets.
    payload_root = module_root / "payloads"
    copies: list[dict] = []
    data_assets: list[dict] = []
    data_asset_paths: dict[str, dict] = {}
    page_payloads: dict[str, dict] = {}
    namespace = plan.get("namespace") or "monkey-project"
    for source_id, asset in sorted(skeleton_by_id.items()):
        document = asset.get("document") if isinstance(asset.get("document"), dict) else {}
        skeleton_object = next((row for row in document.get("instances", [])
                                if isinstance(row, dict) and row.get("__type__") == "sp.SkeletonData"), None)
        if skeleton_object is None:
            raise StaticSpineContinuationError(f"SkeletonData source document is absent: {source_id}")
        atlas_text = skeleton_object.get("_atlasText")
        texture_names, texture_refs = skeleton_object.get("textureNames"), skeleton_object.get("textures")
        if not isinstance(atlas_text, str) or not isinstance(texture_names, list) or not isinstance(texture_refs, list):
            raise StaticSpineContinuationError(f"SkeletonData has no explicit atlas page/texture mapping: {source_id}")
        if atlas_pages(atlas_text) != texture_names or len(texture_names) != len(texture_refs):
            raise StaticSpineContinuationError(f"SkeletonData atlas and texture page identities differ: {source_id}")
        if any(not isinstance(page, str) or not page.lower().endswith(".png") for page in texture_names):
            raise StaticSpineContinuationError(f"Spine atlas page declaration is not an explicit PNG source page: {source_id}")
        native_path = asset.get("native")
        if not isinstance(native_path, str) or not native_path:
            raise StaticSpineContinuationError(f"SkeletonData source binary path is absent: {source_id}")
        skeleton_raw, skeleton_sha, skeleton_source_path = _source_file(source_manifest, asset, native_path, inputs)
        spine_version = binary_version(skeleton_raw)
        if spine_version is None:
            raise StaticSpineContinuationError(f"source SkeletonData binary version is not recognized without decoding: {source_id}")
        atlas_raw = atlas_text.encode("utf-8")
        token = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:20]
        data_rel = f"spine_static_continuation/payloads/{token}"
        asset_target_root = f"{_UNITY_CONTENT_ROOT}/{token}"
        skeleton_suffix = ".skel.bytes" if native_path.lower().endswith((".bin", ".skel.bytes")) else ".json.bytes"
        skeleton_name = "source" + skeleton_suffix
        skeleton_copy = _write_payload_copy(module_root, payload_root, data_rel, skeleton_name,
                                             asset_target_root + "/" + skeleton_name, skeleton_raw,
                                             "source-spine-skeleton-textasset", source_id, skeleton_source_path)
        copies.append(skeleton_copy)
        atlas_copy = _write_payload_copy(module_root, payload_root, data_rel, "source.atlas.txt",
                                          asset_target_root + "/source.atlas.txt", atlas_raw,
                                          "source-spine-atlas-textasset", source_id, "normalized-source-manifest-document")
        copies.append(atlas_copy)
        page_rows = []
        bundle = asset.get("bundle", source_manifest.get("bundle"))
        for ordinal, (source_page, texture_ref) in enumerate(zip(texture_names, texture_refs)):
            uuid = texture_ref.get("__uuid__") if isinstance(texture_ref, dict) else None
            if not isinstance(uuid, str):
                raise StaticSpineContinuationError(f"Spine page {source_page} has no source texture UUID: {source_id}")
            texture, resolution = _resolve_source_uuid(uuid, refs_by_uuid, assets)
            if texture is None or texture.get("kind") != "cc.Texture2D":
                raise StaticSpineContinuationError(f"Spine page texture UUID is missing, ambiguous, or not Texture2D after redirect resolution: {uuid}")
            texture_id = texture["sourceId"]
            raw_texture_path = texture.get("native")
            if not isinstance(raw_texture_path, str) or not raw_texture_path.lower().endswith(".astc"):
                raise StaticSpineContinuationError(f"Spine page is not a pinned ASTC source input: {texture_id}")
            if texture_id not in page_payloads:
                texture_raw, texture_sha, texture_source_path = _source_file(source_manifest, texture, raw_texture_path, inputs)
                page_token = hashlib.sha256(texture_id.encode("utf-8")).hexdigest()[:20]
                page_filename = f"page-{ordinal:02d}-{page_token}.astc.bytes"
                page_copy = _write_payload_copy(module_root, payload_root, f"payloads/pages/{page_token}",
                                                page_filename,
                                                f"{_UNITY_CONTENT_ROOT}/Pages/{page_filename}", texture_raw,
                                                "opaque-source-astc-page-textasset-not-decoded", texture_id,
                                                texture_source_path)
                page_payloads[texture_id] = page_copy
                copies.append(page_copy)
            page_rows.append({"sourcePageName": source_page, "sourceTextureSourceId": texture_id,
                              "sourceTextureUuid": uuid, "sourceTextureUuidResolution": resolution,
                              "sourceTextureSha256": page_payloads[texture_id]["sha256"],
                              "sourceTextureBytes": page_payloads[texture_id]["bytes"],
                              "sourceTexturePath": page_payloads[texture_id]["target"],
                              "textureAssetType": "TextAsset", "decodedTexture2D": False,
                              "atlasPageOrdinal": ordinal})
        pma_values = []
        for component in components:
            if component["sourceDataReference"].get("sourceDataAssetId") != source_id:
                continue
            state = component["sourceFieldStates"].get("premultipliedAlpha", {})
            if state.get("present"):
                if type(state.get("value")) is not bool:
                    raise StaticSpineContinuationError(f"source PMA field is not a bool: {component['sourceComponentId']}")
                pma_values.append(state["value"])
        pma_unknown_count = sum(1 for component in components
                                if component["sourceDataReference"].get("sourceDataAssetId") == source_id and
                                not component["sourceFieldStates"]["premultipliedAlpha"]["present"])
        distinct_pma = sorted(set(pma_values))
        pma_status = "source-field-unserialized-unknown" if pma_unknown_count else (
            "source-fields-conflict" if len(distinct_pma) > 1 else "source-fields-explicit" if len(distinct_pma) == 1 else "unreferenced-data-asset")
        data_asset_path = asset_target_root + "/NativeStaticSpineData.asset"
        data_record = {
            "sourceDataAssetId": source_id,
            "sourceDataUuid": source_id.split(":", 1)[1] if ":" in source_id else None,
            "sourceAssetType": "sp.SkeletonData",
            "sourceLogicalPath": asset.get("logicalPath"),
            "sourceSpineVersion": spine_version,
            "sourceNativePath": native_path,
            "sourceNativeSha256": skeleton_sha,
            "sourceNativeBytes": len(skeleton_raw),
            "sourceNativeAssetType": "TextAsset",
            "sourceSkeletonTextAssetPath": skeleton_copy["target"],
            "sourceAtlasTextAssetPath": atlas_copy["target"],
            "sourceAtlasSha256": _sha(atlas_raw),
            "sourceAtlasBytes": len(atlas_raw),
            "sourceAtlasPageCount": len(page_rows),
            "sourceAtlasPages": page_rows,
            "sourcePma": {"status": pma_status, "knownValues": distinct_pma,
                          "valueKnown": len(distinct_pma) == 1 and not pma_unknown_count,
                          "boolValue": distinct_pma[0] if len(distinct_pma) == 1 and not pma_unknown_count else False,
                          "unknownComponentCount": pma_unknown_count,
                          "value": distinct_pma[0] if len(distinct_pma) == 1 and not pma_unknown_count else None},
            "nativeStaticSpineDataAssetPath": data_asset_path,
            "nativeStaticSpineDataGuidPolicy": "Unity AssetDatabase assigns and readback pins persistent identity",
            "assetType": "NativeStaticSpineData",
            "status": "nonrendering-source-bytes-prepared",
            "skeletonParsed": False,
            "atlasDecoded": False,
            "pageDecoded": False,
            "rendererCreated": False,
            "sourceAnimationBehaviorRestored": False,
        }
        data_assets.append(data_record)
        data_asset_paths[source_id] = data_record

    for row in components:
        data_id = row["sourceDataReference"].get("sourceDataAssetId")
        row["nativeStaticDataAssetPath"] = data_asset_paths.get(data_id, {}).get("nativeStaticSpineDataAssetPath")
        row["dataReferenceStatus"] = "source-ID-and-bytes-pinned-native-record-pending-editor-create" if data_id in data_asset_paths else row["sourceDataReference"].get("status")
        row["componentReadbackStatus"] = "not_run"

    # The root owns the JsonUtility Plan field; this fragment contains no
    # target renderer or executable source behavior.
    fragment = {
        "schemaVersion": 1, "contract": CONTRACT,
        "sourceManifestPath": str(manifest_path), "sourceManifestSha256": manifest_sha,
        "sourceIrSha256": expected_ir_sha, "sourcePlanSha256": _sha(_canonical(plan)),
        "moduleStage": "spine_static_continuation",
        "sourceProfile": source_manifest.get("sourceProfile"), "sourceVersion": source_manifest.get("sourceVersion"),
        "projectLayout": plan.get("projectLayout"), "namespace": namespace,
        "status": "prepared_nonrendering_static_source_reference_plan",
        "nonRendering": True, "dynamicBehavior": "not_restored", "runtimeOrRendererLoaded": False,
        "dataAssets": data_assets, "components": components,
        "payloadCopies": copies,
        "supportFiles": _support_files(),
        "runtimeDependency": _pinned_runtime_record(
            pinned_runtime_inputs.get("unity_runtime_manifest"),
            pinned_runtime_inputs.get("unity_runtime_manifest_path"),
            pinned_runtime_inputs.get("unity_runtime_manifest_sha256"),
            pinned_runtime_inputs.get("unity_runtime_assets_root")),
        "unresolvedSourceComponentReferences": [r["sourceComponentId"] for r in components
            if any(ref.get("resolutionStatus") for ref in r["sourceObjectReferences"])],
        "summary": {
            "sourceSpineComponentCount": len(components),
            "sourceTemplateComponentCount": len({r["sourceTemplateComponentId"] for r in components}),
            "syncInstanceComponentCount": sum(r["sourceComponentId"] != r["sourceTemplateComponentId"] for r in components),
            "sourceSkeletonDataAssetCount": len(data_assets),
            "sourceSkeletonDataReferenceCount": sum(r["sourceDataReference"].get("sourceDataAssetId") is not None for r in components),
            "missingSourceSkeletonDataReferenceCount": sum(r["sourceDataReference"].get("sourceDataAssetId") is None for r in components),
            "sourceObjectReferenceCount": sum(len(r["sourceObjectReferences"]) for r in components),
            "missingSourceObjectReferenceCount": sum(bool(r.get("resolutionStatus")) for c in components for r in c["sourceObjectReferences"]),
            "pmaUnknownDataAssetCount": sum(r["sourcePma"]["status"] == "source-field-unserialized-unknown" for r in data_assets),
            "pmaConflictDataAssetCount": sum(r["sourcePma"]["status"] == "source-fields-conflict" for r in data_assets),
            "sourcePayloadFiles": len(copies), "sourceAstcPagesCopiedOpaque": len(page_payloads),
            "sourceAstcPagesDecoded": 0, "rendered": False, "animated": False,
        },
    }
    _validate_fragment(fragment)
    # Reuse the existing non-rendering retained-material carrier for the exact
    # source cc.Material references in sp.Skeleton._materials. It receives only
    # this family’s material refs, so it cannot trigger other texture decodes.
    retained_components = []
    for row in components:
        material_ids = [ref["sourceAssetId"] for ref in row["sourceObjectReferences"]
                        if ref.get("targetReferenceKind") == "retained-source-material"]
        if material_ids:
            retained_components.append({
                "sourceId": row["sourceComponentId"], "node": row["sourceNodeId"],
                "staticFieldBinding": {"fields": [{"sourceFieldName": "_materials", "kind": "asset_ref",
                    "storageType": "UnityEngine.Object[]", "elementKind": "asset_ref", "refValues": material_ids}]},
            })
    if retained_components:
        from .prefab_static_retained_assets import prepare as prepare_retained_assets
        retained_plan = {"namespace": namespace, "sourceManifestSha256": manifest_sha,
                         "components": retained_components}
        retained_stage = module_root / "retained-assets"
        retained = prepare_retained_assets(retained_plan, source_manifest, retained_stage)
        retained_contract = retained["contract"]
        _rebase_retained_sources(retained_contract, "spine_static_continuation/retained-assets")
        fragment["retainedAssetsContract"] = retained_contract
        fragment["retainedAssetsStage"] = "spine_static_continuation/retained-assets"
        retained_manifest = retained.get("manifest", {})
        fragment["summary"]["retainedSourceMaterialReferenceCount"] = retained_manifest.get("referenceCount", len(retained_contract.get("references", [])))
        fragment["summary"]["retainedSourceMaterialAssetCount"] = retained_manifest.get("assetCount", len(retained_contract.get("assets", [])))
        fragment["retainedAssetsPreparation"] = {"status": "prepared_nonrendering_retained_records",
            "gapCount": retained_manifest.get("gapCount", len(retained_contract.get("gaps", []))),
            "referenceCount": retained_manifest.get("referenceCount", len(retained_contract.get("references", []))),
            "assetCount": retained_manifest.get("assetCount", len(retained_contract.get("assets", [])))}
        if fragment["retainedAssetsPreparation"]["gapCount"]:
            raise StaticSpineContinuationError("source Spine material references could not all be retained; see retained contract gaps")
    else:
        fragment["retainedAssetsPreparation"] = {"status": "no_source_material_references"}
    _validate_fragment(fragment)
    write_json(module_root / "static-spine-continuation.json", fragment)
    patched_plan = dict(plan)
    if fragment.get("retainedAssetsContract") is not None:
        patched_plan["staticRetainedAssets"] = _merge_retained_contracts(
            plan.get("staticRetainedAssets"), fragment["retainedAssetsContract"])
    patched_plan["staticSpineContinuation"] = fragment
    return {"plan": patched_plan, "continuation": fragment,
            "status": "prepared_nonrendering_static_source_reference_plan"}


def prepare(plan: dict, ir: dict, source_manifest: dict, output: str | Path, **pinned_runtime_inputs) -> dict:
    """Build the module-owned subtree without disturbing sibling stage products."""
    destination = Path(output)
    module_root = destination / "spine_static_continuation"
    existed = module_root.exists() or module_root.is_symlink()
    try:
        return _prepare_impl(plan, ir, source_manifest, output, **pinned_runtime_inputs)
    except Exception:
        if not existed and module_root.is_dir() and not module_root.is_symlink():
            import shutil
            shutil.rmtree(module_root)
        raise


def _write_payload_copy(output: Path, payload_root: Path, source_relative: str, file_name: str,
                        target: str, raw: bytes, role: str, source_id: str, source_file: str) -> dict:
    source_relative = _rel(source_relative.rstrip("/") + "/" + file_name, "payload source path")
    target = _rel(target, "payload target path")
    if not target.startswith(_UNITY_CONTENT_ROOT + "/"):
        raise StaticSpineContinuationError(f"Spine source payload target escapes Content: {target}")
    dest = inside(output, source_relative)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        raise StaticSpineContinuationError(f"source payload path collision: {source_relative}")
    dest.write_bytes(raw)
    return {"source": source_relative, "target": target, "sha256": _sha(raw), "bytes": len(raw),
            "role": role, "sourceId": source_id, "sourceInputPath": source_file,
            "targetAssetType": "TextAsset", "targetDecoded": False}


def _support_files() -> list[dict]:
    root = Path(__file__).resolve().parent
    specifications = (
        ("targets/NativeStaticSpineReference.cs", _RUNTIME_REFERENCE, "nonrendering-static-component-carrier"),
        ("targets/NativeStaticSpineData.cs", _RUNTIME_DATA,
         "nonrendering-source-data-asset"),
        ("targets/UnityStaticSpineContinuation.cs", _EDITOR_HELPER, "editor-create-resolve-saved-readback-helper"),
    )
    rows = []
    for source, target, role in specifications:
        path = inside(root, source)
        raw = path.read_bytes()
        rows.append({"source": source, "target": target, "sha256": _sha(raw), "bytes": len(raw), "role": role})
    return rows


def _validate_fragment(fragment: dict) -> None:
    if fragment.get("contract") != CONTRACT or fragment.get("schemaVersion") != 1:
        raise StaticSpineContinuationError("unsupported static Spine continuation contract")
    component_ids = [row.get("sourceComponentId") for row in fragment.get("components", [])]
    if any(not isinstance(value, str) or not value for value in component_ids) or len(component_ids) != len(set(component_ids)):
        raise StaticSpineContinuationError("continuation component source IDs are missing or duplicated")
    data_ids = [row.get("sourceDataAssetId") for row in fragment.get("dataAssets", [])]
    if len(data_ids) != len(set(data_ids)) or any(not isinstance(value, str) for value in data_ids):
        raise StaticSpineContinuationError("continuation source data asset IDs are missing or duplicated")
    by_data = set(data_ids)
    for row in fragment.get("components", []):
        ref = row.get("sourceDataReference", {})
        data_id = ref.get("sourceDataAssetId")
        if data_id and data_id not in by_data:
            raise StaticSpineContinuationError(f"component source data ID has no preserved source record: {data_id}")
        if row.get("renderingStatus") != "not_rendered" or row.get("dynamicBehaviorStatus") != "not_restored":
            raise StaticSpineContinuationError("static continuation cannot advertise rendering or recovered behavior")
    for row in fragment.get("payloadCopies", []):
        if not _SHA.fullmatch(row.get("sha256", "")) or type(row.get("bytes")) is not int:
            raise StaticSpineContinuationError("payload manifest row lacks a file SHA/byte count")
        if not row.get("target", "").startswith(_UNITY_CONTENT_ROOT + "/"):
            raise StaticSpineContinuationError("source payload is outside the permitted Unity Content root")


def emit(plan: dict, plan_root: str | Path, output: str | Path) -> dict:
    """Copy pinned raw TextAsset payloads and this module's exact carrier helpers.

    SDK DLLs are not required or copied: these carriers preserve opaque source
    bytes and refs, and they do not invoke the Spine runtime.
    """
    fragment = plan.get("staticSpineContinuation")
    if isinstance(fragment, str):
        try:
            fragment = json.loads(fragment)
        except json.JSONDecodeError as error:
            raise StaticSpineContinuationError("staticSpineContinuation is not strict JSON") from error
    if not isinstance(fragment, dict):
        raise StaticSpineContinuationError("plan has no staticSpineContinuation fragment")
    _validate_fragment(fragment)
    if plan.get("spineNativeStage") or plan.get("spineNativeBindingPlan"):
        raise StaticSpineContinuationError("static source continuation cannot be mixed with the legacy rendering Spine stage")
    root, destination = Path(plan_root).resolve(strict=True), Path(output).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    for row in fragment.get("payloadCopies", []):
        source = _rel(row.get("source"), "payload source")
        target = _rel(row.get("target"), "payload target")
        if not target.startswith(_UNITY_CONTENT_ROOT + "/"):
            raise StaticSpineContinuationError(f"payload target is not under Unity Content: {target}")
        stage_root = inside(root, _rel(fragment.get("moduleStage", "spine_static_continuation"), "module stage")).resolve(strict=True)
        source_path = inside(stage_root, source).resolve(strict=True)
        try:
            source_path.relative_to(root)
        except ValueError as error:
            raise StaticSpineContinuationError(f"payload source escapes the plan root: {source}") from error
        if source_path.is_symlink() or not source_path.is_file():
            raise StaticSpineContinuationError(f"payload source is not a regular file: {source}")
        raw = source_path.read_bytes()
        if len(raw) != row.get("bytes") or _sha(raw) != row.get("sha256"):
            raise StaticSpineContinuationError(f"source payload differs from its pinned plan row: {source}")
        target_path = inside(destination, target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists() or target_path.is_symlink():
            raise StaticSpineContinuationError(f"refusing to overwrite candidate content: {target}")
        target_path.write_bytes(raw)
        meta_path = Path(str(target_path) + ".meta")
        if meta_path.exists() or meta_path.is_symlink():
            raise StaticSpineContinuationError(f"refusing to overwrite candidate asset metadata: {target}.meta")
        guid_value = guid(fragment["namespace"], "static-spine-source-text-asset/" + row["sourceId"] + "/" + target)
        meta_raw = _text_asset_meta(guid_value)
        meta_path.write_bytes(meta_raw)
        copied.append({"path": target, "sha256": _sha(raw), "bytes": len(raw), "role": row["role"],
                       "metaPath": target + ".meta", "metaSha256": _sha(meta_raw), "metaBytes": len(meta_raw),
                       "guid": guid_value})
    support = []
    source_root = Path(__file__).resolve().parent
    for row in fragment.get("supportFiles", []):
        source = _rel(row["source"], "support source")
        target = _rel(row["target"], "support target")
        allowed = target in (_EDITOR_HELPER, _RUNTIME_REFERENCE, _RUNTIME_DATA)
        if not allowed:
            raise StaticSpineContinuationError(f"unapproved static Spine helper target: {target}")
        source_path = inside(source_root, source).resolve(strict=True)
        raw = source_path.read_bytes()
        if len(raw) != row.get("bytes") or _sha(raw) != row.get("sha256"):
            raise StaticSpineContinuationError(f"Spine helper source changed after plan preparation: {source}")
        dest = inside(destination, target)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() or dest.is_symlink():
            raise StaticSpineContinuationError(f"refusing to overwrite candidate helper: {target}")
        dest.write_bytes(raw)
        guid_value = guid(fragment["namespace"], "static-spine-helper/" + source)
        meta_raw = _mono_script_meta(guid_value)
        if Path(str(dest) + ".meta").exists() or Path(str(dest) + ".meta").is_symlink():
            raise StaticSpineContinuationError(f"refusing to overwrite candidate helper metadata: {target}.meta")
        Path(str(dest) + ".meta").write_bytes(meta_raw)
        support.append({"path": target, "sha256": _sha(raw), "bytes": len(raw),
                        "metaPath": target + ".meta", "metaSha256": _sha(meta_raw), "metaBytes": len(meta_raw),
                        "guid": guid_value, "role": row["role"]})
    return {"schemaVersion": 1, "contract": CONTRACT, "status": "raw_source_payloads_and_carriers_emitted",
            "sourceManifestSha256": fragment["sourceManifestSha256"], "sourceIrSha256": fragment["sourceIrSha256"],
            "copiedPayloads": copied, "copiedSupportFiles": support,
            "dataAssetsCreatedByEditor": len(fragment.get("dataAssets", [])),
            "retainedAssetsEmission": "owned by shared staticRetainedAssets exporter",
            "sourceAstcPagesDecoded": 0, "runtimeDllsCopied": 0, "rendererCreated": False}


def _text_asset_meta(guid_value: str) -> bytes:
    return ("fileFormatVersion: 2\nguid: " + guid_value +
            "\nTextScriptImporter:\n  externalObjects: {}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n").encode("utf-8")


def _mono_script_meta(guid_value: str) -> bytes:
    return ("fileFormatVersion: 2\nguid: " + guid_value + "\nMonoImporter:\n  externalObjects: {}\n  serializedVersion: 2\n  defaultReferences: []\n  executionOrder: 0\n  icon: {instanceID: 0}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n").encode("utf-8")


def _persistent_identity(guid_value, local_id) -> bool:
    return (isinstance(guid_value, str) and re.fullmatch(r"[0-9a-f]{32}", guid_value) is not None
            and type(local_id) is int and -(1 << 63) <= local_id < (1 << 63) and local_id != 0)


def _saved_retained_meta(row, contract, saved_raw, native_readback):
    """Recover exact generator bytes, then verify the pinned saved equivalent."""
    recipes = {'unity-retained-material-meta': 'native-asset',
               'unity-default-material-meta': 'native-material',
               'unity-text-asset-meta': 'text', 'unity-texture2d-meta': 'texture'}
    recipe = recipes.get(row.get('kind'))
    if recipe is None or not row['target'].endswith('.meta'):
        raise StaticSpineContinuationError('No source-pinned generated meta recipe for this payload')
    matches = [asset.get('unity', {}) for asset in contract.get('assets', [])
               if asset.get('unity', {}).get('path', '') + '.meta' == row['target']]
    if len(matches) != 1:
        raise StaticSpineContinuationError('Generated meta asset identity is missing or ambiguous')
    from .prefab_static_retained_assets import _unity_meta
    original = _unity_meta(matches[0]['guid'], recipe)
    if len(original) != row['bytes'] or _sha(original) != row['sha256']:
        raise StaticSpineContinuationError('Generated meta recipe differs from the frozen original SHA/bytes')
    records = native_readback.get('nativeFiles') if isinstance(native_readback, dict) else None
    pins = [record for record in records or [] if isinstance(record, dict) and record.get('path') == row['target']]
    if len(pins) != 1:
        raise StaticSpineContinuationError('Saved meta requires one exact nativeFiles hash binding')
    from .unity_saved_meta import verify_saved_meta
    evidence = verify_saved_meta(original, saved_raw, pins[0].get('sha256'))
    return dict(evidence, path=row['target'], sourceKind=row['kind'])


def _verify_impl(plan_fragment: dict, candidate_root: str | Path, editor_readback: dict | str | Path,
                 native_readback=None, meta_observations=None) -> list[dict]:
    """Verify emitted bytes and an explicit Unity saved-prefab readback receipt."""
    fragment = plan_fragment
    from .io import diagnostic
    try:
        if isinstance(fragment, str):
            fragment = json.loads(fragment)
        _validate_fragment(fragment)
        candidate = Path(candidate_root).resolve(strict=True)
        if isinstance(editor_readback, (str, Path)):
            readback_path = Path(editor_readback).resolve(strict=True)
            receipt = json.loads(readback_path.read_text(encoding="utf-8"))
        elif isinstance(editor_readback, dict):
            receipt = editor_readback
            readback_path = None
        else:
            raise StaticSpineContinuationError("editor_readback must be a JSON object or readback path")
    except (OSError, UnicodeError, json.JSONDecodeError, StaticSpineContinuationError) as error:
        return [diagnostic("STATIC_SPINE_READBACK_INVALID", str(candidate_root), str(error))]

    file_rows = []
    for row in fragment.get("payloadCopies", []):
        target = _rel(row.get("target"), "payload target")
        path = inside(candidate, target).resolve(strict=True)
        if path.is_symlink() or not path.is_file():
            raise StaticSpineContinuationError(f"candidate source payload is absent: {target}")
        raw = path.read_bytes()
        if len(raw) != row.get("bytes") or _sha(raw) != row.get("sha256"):
            raise StaticSpineContinuationError(f"candidate source payload differs from pinned bytes: {target}")
        meta = inside(candidate, target + ".meta").resolve(strict=True)
        expected_guid = guid(fragment["namespace"], "static-spine-source-text-asset/" + row["sourceId"] + "/" + target)
        if meta.is_symlink() or not meta.is_file() or meta.read_bytes() != _text_asset_meta(expected_guid):
            raise StaticSpineContinuationError(f"candidate source TextAsset meta differs from its deterministic identity: {target}.meta")
        file_rows.append({"path": target, "sha256": _sha(raw), "bytes": len(raw), "role": row["role"]})
    for row in fragment.get("supportFiles", []):
        target = _rel(row.get("target"), "support target")
        path = inside(candidate, target).resolve(strict=True)
        if path.is_symlink() or not path.is_file():
            raise StaticSpineContinuationError(f"candidate static Spine helper is absent: {target}")
        raw = path.read_bytes()
        if len(raw) != row.get("bytes") or _sha(raw) != row.get("sha256"):
            raise StaticSpineContinuationError(f"candidate static Spine helper differs from the prepared source: {target}")
        meta = inside(candidate, target + ".meta").resolve(strict=True)
        expected_guid = guid(fragment["namespace"], "static-spine-helper/" + row["source"])
        if meta.is_symlink() or not meta.is_file() or meta.read_bytes() != _mono_script_meta(expected_guid):
            raise StaticSpineContinuationError(f"candidate static Spine helper metadata is absent: {target}.meta")
    for row in fragment.get("dataAssets", []):
        target = _rel(row.get("nativeStaticSpineDataAssetPath"), "native Spine data target")
        asset_path = inside(candidate, target).resolve(strict=True)
        meta_path = inside(candidate, target + ".meta").resolve(strict=True)
        if asset_path.is_symlink() or not asset_path.is_file():
            raise StaticSpineContinuationError(f"Editor-created NativeStaticSpineData asset is absent: {target}")
        if meta_path.is_symlink() or not meta_path.is_file():
            raise StaticSpineContinuationError(f"Editor-created NativeStaticSpineData metadata is absent: {target}.meta")

    if receipt.get("schemaVersion") != 1 or receipt.get("contract") != READBACK_CONTRACT:
        raise StaticSpineContinuationError("saved static Spine readback contract is absent or unsupported")
    if receipt.get("sourceManifestSha256") != fragment["sourceManifestSha256"] or receipt.get("sourceIrSha256") != fragment["sourceIrSha256"]:
        raise StaticSpineContinuationError("saved static Spine readback source pins differ")
    expected = {row["sourceComponentId"]: row for row in fragment.get("components", [])}
    rows = receipt.get("components")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise StaticSpineContinuationError("saved static Spine component readback rows are absent")
    actual = {row.get("sourceComponentId"): row for row in rows}
    if len(actual) != len(rows) or set(actual) != set(expected):
        raise StaticSpineContinuationError("saved static Spine component denominator/identities differ")
    failures = []
    for source_id, expected_row in expected.items():
        row = actual[source_id]
        for key, want in (("sourceTemplateComponentId", expected_row["sourceTemplateComponentId"]),
                          ("sourceNodeId", expected_row["sourceNodeId"]),
                          ("sourceFieldsSha256", expected_row["sourceFieldsSha256"]),
                          ("sourceComponentEnvelopeSha256", expected_row["sourceComponentEnvelopeSha256"])):
            if row.get(key) != want:
                failures.append({"sourceComponentId": source_id, "field": key, "expected": want, "actual": row.get(key)})
        if row.get("savedComponent") is not True or row.get("persistedGuidStatus") != "verified" or \
                not _persistent_identity(row.get("persistedGuid"), row.get("persistedLocalFileId")):
            failures.append({"sourceComponentId": source_id, "field": "persistedComponentIdentity", "actual": row.get("persistedGuidStatus")})
        expected_data_id = expected_row.get("sourceDataReference", {}).get("sourceDataAssetId")
        if expected_data_id is not None and (row.get("sourceDataAssetId") != expected_data_id or
                row.get("dataAssetGuidStatus") != "verified" or
                not _persistent_identity(row.get("dataAssetGuid"), row.get("dataAssetLocalFileId"))):
            failures.append({"sourceComponentId": source_id, "field": "persistedSkeletonDataIdentity",
                             "expectedSourceDataAssetId": expected_data_id, "actualSourceDataAssetId": row.get("sourceDataAssetId"),
                             "guidStatus": row.get("dataAssetGuidStatus")})
        if expected_data_id is not None:
            expected_data = next((asset for asset in fragment.get("dataAssets", [])
                                  if asset.get("sourceDataAssetId") == expected_data_id), None)
            asset_meta_path = inside(candidate, expected_data["nativeStaticSpineDataAssetPath"] + ".meta").resolve(strict=True) if expected_data else None
            match = re.search(r"^guid:\s*([0-9a-f]{32})\s*$", asset_meta_path.read_text(encoding="utf-8"), re.MULTILINE) if asset_meta_path else None
            if expected_data is None or not match or row.get("dataAssetGuid") != match.group(1):
                failures.append({"sourceComponentId": source_id, "field": "persistedSkeletonDataGuid",
                                 "expected": match.group(1) if match else None,
                                 "actual": row.get("dataAssetGuid")})
        if row.get("renderingStatus") != "not_rendered" or row.get("dynamicBehaviorStatus") != "not_restored":
            failures.append({"sourceComponentId": source_id, "field": "staticScopeStatus", "actual": row.get("renderingStatus")})
        expected_refs = {r["fieldPath"]: r for r in expected_row.get("sourceObjectReferences", [])}
        saved_refs = row.get("sourceObjectReferences")
        actual_refs = {r.get("fieldPath"): r for r in saved_refs if isinstance(r, dict)} if isinstance(saved_refs, list) else {}
        if set(actual_refs) != set(expected_refs):
            failures.append({"sourceComponentId": source_id, "field": "sourceObjectReferencePaths"})
            continue
        for field_path, ref in expected_refs.items():
            saved = actual_refs[field_path]
            if saved.get("sourceAssetId") != ref.get("sourceAssetId") or saved.get("sourceUuid") != ref.get("sourceUuid"):
                failures.append({"sourceComponentId": source_id, "field": "sourceObjectReferenceIdentity", "path": field_path})
            if saved.get("resolved") is not True or not _persistent_identity(saved.get("persistedGuid"), saved.get("persistedLocalFileId")):
                failures.append({"sourceComponentId": source_id, "field": "sourceObjectReferencePersistence", "path": field_path})
    if failures or receipt.get("status") != "saved_static_references_verified":
        if not failures:
            failures.append({"field": "readback.status", "actual": receipt.get("status")})
        return [diagnostic("STATIC_SPINE_SAVED_REFERENCE_MISMATCH", str(readback_path or candidate_root),
                           json.dumps(failures[:20], ensure_ascii=False))]
    retained_contract = fragment.get("retainedAssetsContract")
    retained_emit_rows = (retained_contract or {}).get("payloads", [])
    for row in retained_emit_rows:
        target = _rel(row.get("target"), "retained asset target")
        if not target.startswith("Assets/Game/Content/"):
            continue
        path = inside(candidate, target).resolve(strict=True)
        if path.is_symlink() or not path.is_file():
            return [diagnostic("STATIC_SPINE_RETAINED_ASSET_MISSING", target, "pinned non-rendering retained source payload is absent")]
        raw = path.read_bytes()
        if len(raw) != row.get("bytes") or _sha(raw) != row.get("sha256"):
            try:
                evidence = _saved_retained_meta(row, retained_contract, raw, native_readback)
                if meta_observations is not None:
                    meta_observations.append(evidence)
            except (ValueError, KeyError, TypeError) as error:
                return [diagnostic("STATIC_SPINE_RETAINED_ASSET_CHANGED", target,
                    "Retained payload differs from its original pin and no strict saved-meta equivalence is proven: " + str(error))]
    return []


def verify(plan_fragment: dict, candidate_root: str | Path, editor_readback: dict | str | Path | None = None,
           *, meta_observations=None) -> list[dict]:
    """Return strict diagnostics and read saved identity from the canonical sidecar."""
    from .io import diagnostic
    root = Path(candidate_root)
    sidecar = root / "Analysis" / "Readback" / "spine-static-continuation.json"
    try:
        if not sidecar.is_file() or sidecar.is_symlink():
            return [diagnostic("STATIC_SPINE_READBACK_MISSING", str(sidecar), "Editor saved-prefab identity sidecar is absent")]
        diagnostics = _verify_impl(plan_fragment, root, sidecar, editor_readback, meta_observations)
        if diagnostics or not isinstance(editor_readback, dict) or 'components' not in editor_readback:
            return diagnostics
        # Both records must refer to the same saved source instance. Template
        # identities and synthetic nonzero file IDs cannot stand in for it.
        receipt = json.loads(sidecar.read_text(encoding='utf-8'))
        actual = {}
        for row in editor_readback['components']:
            actual.setdefault(row.get('sourceId'), []).append(row)
        failures = []
        for row in receipt['components']:
            candidates = [item for item in actual.get(row['sourceComponentId'], [])
                          if item.get('nativeType') == 'NativeStaticSpineReference'
                          and item.get('representation') == 'disabled-source-data-carrier'
                          and item.get('status') == 'retained']
            if (len(candidates) != 1 or candidates[0].get('persistent') is not True
                    or candidates[0].get('sourceIdentityVerified') is not True
                    or candidates[0].get('guid') != row['persistedGuid']
                    or candidates[0].get('localFileId') != row['persistedLocalFileId']
                    or not _persistent_identity(candidates[0].get('guid'), candidates[0].get('localFileId'))):
                failures.append(row['sourceComponentId'])
        if failures:
            return [diagnostic('STATIC_SPINE_PERSISTENT_IDENTITY_MISMATCH', str(sidecar),
                               json.dumps({'sourceComponentIds': failures}, ensure_ascii=False))]
        return []
    except Exception as error:
        return [diagnostic("STATIC_SPINE_READBACK_INVALID", str(sidecar), f"{type(error).__name__}: {error}")]
