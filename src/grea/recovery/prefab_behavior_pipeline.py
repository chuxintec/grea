"""Source-pinned local behavior lowering into a copy-on-write Prefab IR stage.

This is a pipeline adapter, not a game runtime. JavaScript is parsed only by the
existing vendored AST module extractor; generated C#/TypeScript is emitted only
from the explicit source-bound lowering table.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
from typing import Any

from . import io
from .output_limits import copy_verified
from .sources.code import modules as static_code_modules
from .prefab_local_behaviors import (
    RULE_VERSION,
    SOURCES,
    SUPPORTED_FIELDS,
    Lowering,
    lower_behavior,
)
from .sources.compiled import ParseError, fail

PIPELINE_SCHEMA = "monkey-prefab-behavior-ir/1"
EXPECTED_SOURCE_BUNDLE_SHA256 = "21af08e48846f6ad1a2e0673b0c945358136723b1664f0cd1f6ec9b3df6c5cb5"
SOURCE_BUNDLE_BUDGET = 128 * 1024 * 1024
STAGE_MANIFEST_BUDGET = 128 * 1024 * 1024
STAGE_DOCUMENT_BUDGET = 128 * 1024 * 1024
_SOURCE_RESERVED_FIELDS = {
    "__type__", "__editorExtras__", "_enabled", "_id", "_objFlags", "_prefab",
    "_scene", "_name", "_parent", "_children", "node", "_componentId", "_sourceId",
}
_COMPONENT_ID_RE = re.compile(r"^(?P<asset>[^#]+)#(?P<object>[0-9]+)(?:/components/(?P<ordinal>[0-9]+))?$")
_RF_CANDIDATE_RE = re.compile(r"^rf@(.+)@([0-9]+)$")
_TARGET_CLASS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _source_type_from_candidate(module: dict[str, Any]) -> str | None:
    candidate = module.get("candidate_id")
    if not isinstance(candidate, str):
        return None
    match = _RF_CANDIDATE_RE.fullmatch(candidate)
    if not match:
        return None
    return match.group(1)


def _index_source_modules(bundle: bytes) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    parsed, diagnostic = static_code_modules(bundle)
    index: dict[str, list[dict[str, Any]]] = {}
    invalid = []
    for row in parsed:
        source_type = _source_type_from_candidate(row)
        span = row.get("source_bytes") or {}
        start, end = span.get("start"), span.get("end")
        if source_type is None:
            continue
        if type(start) is not int or type(end) is not int or not (0 <= start < end <= len(bundle)):
            invalid.append({"candidateId": row.get("candidate_id"), "reason": "source byte span is invalid"})
            continue
        source = bundle[start:end]
        actual = _digest(source)
        if actual != row.get("sha256"):
            invalid.append({"candidateId": row.get("candidate_id"), "reason": "source byte span hash mismatch", "expected": row.get("sha256"), "actual": actual})
            continue
        # Also bind the RF-registration offset encoded by the existing module reader.
        match = _RF_CANDIDATE_RE.fullmatch(row["candidate_id"])
        if int(match.group(2)) != start:
            invalid.append({"candidateId": row.get("candidate_id"), "reason": "candidate RF offset differs from source span"})
            continue
        index.setdefault(source_type, []).append({
            "sourceType": source_type,
            "name": row.get("name"),
            "candidateId": row["candidate_id"],
            "sourceBytes": {"start": start, "end": end},
            "sha256": actual,
            "sourceFormat": row.get("confidence"),
            "_bytes": source,
        })
    for source_type, rows in index.items():
        # Duplicate identical identities are harmless only when the proof is identical.
        unique = {(r["sourceBytes"]["start"], r["sourceBytes"]["end"], r["sha256"]) for r in rows}
        if len(unique) > 1:
            for row in rows:
                row["ambiguousSourceType"] = True
    return index, {"moduleCount": len(parsed), "rfTypeCount": len(index), "diagnostic": diagnostic, "invalidModules": invalid}


def _source_asset_index(source_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    assets = source_manifest.get("assets")
    if not isinstance(assets, list):
        fail("SOURCE_ASSETS_MISSING", "sourceManifest.assets", "Expected the frozen asset records needed for serialized component readback")
    input_index = {}
    for row in source_manifest.get("inputs", []):
        if isinstance(row, dict) and isinstance(row.get("path"), str) and isinstance(row.get("bundle"), str):
            input_index[(row["bundle"], row["path"])] = row
    indexed: dict[str, dict[str, Any]] = {}
    for row in assets:
        if not isinstance(row, dict):
            continue
        source_id = row.get("sourceId")
        if not isinstance(source_id, str):
            continue
        if source_id in indexed:
            fail("DUPLICATE_SOURCE_ASSET_ID", source_id, "Source asset identity is ambiguous")
        # The manifest's embedded parsed object is itself sourceManifest-pinned;
        # when the original import input is listed, bind that additional exact pin too.
        candidate = dict(row)
        input_row = input_index.get((row.get("bundle"), row.get("importPath")))
        if input_row:
            candidate["_sourceInputPin"] = {"bundle": input_row.get("bundle"), "path": input_row.get("path"),
                                           "sha256": input_row.get("sha256"), "bytes": input_row.get("bytes")}
        indexed[source_id] = candidate
    return indexed


def _serialized_component(
    component: dict[str, Any], assets: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_id = component.get("sourceId")
    if not isinstance(source_id, str):
        fail("COMPONENT_SOURCE_ID_MISSING", "component", "Custom component has no sourceId")
    match = _COMPONENT_ID_RE.fullmatch(source_id)
    if not match:
        fail("COMPONENT_SOURCE_ID_INVALID", source_id, "Expected an exact asset object or inline component source identity")
    asset_id = match.group("asset")
    asset = assets.get(asset_id)
    if asset is None:
        fail("COMPONENT_SOURCE_ASSET_MISSING", source_id, "Source component asset is not in the pinned source manifest")
    document = asset.get("document")
    if not isinstance(document, dict) or not isinstance(document.get("instances"), list):
        fail("COMPONENT_SOURCE_DOCUMENT_MISSING", source_id, "Asset has no embedded serialized object document")
    objects = document["instances"]
    object_index = int(match.group("object"))
    if object_index >= len(objects) or not isinstance(objects[object_index], dict):
        fail("COMPONENT_SOURCE_OBJECT_MISSING", source_id, "Source object index is outside the document")
    ordinal_text = match.group("ordinal")
    if ordinal_text is None:
        payload = objects[object_index]
        raw_index = object_index
        node_source_id = None
    else:
        node = objects[object_index]
        if node.get("__type__") != "cc.Node":
            fail("COMPONENT_SOURCE_NODE_TYPE_MISMATCH", source_id, "Inline component owner is not a serialized Cocos Node")
        ordinal = int(ordinal_text)
        refs = node.get("_components")
        if not isinstance(refs, list) or ordinal >= len(refs):
            fail("COMPONENT_SOURCE_SLOT_MISSING", source_id, "Inline component ordinal is absent from the original node")
        reference = refs[ordinal]
        if isinstance(reference, dict) and set(reference) == {"__id__"} and type(reference["__id__"]) is int:
            raw_index = reference["__id__"]
            if raw_index < 0 or raw_index >= len(objects) or not isinstance(objects[raw_index], dict):
                fail("COMPONENT_SOURCE_REFERENCE_INVALID", source_id, "Original component object reference is outside the document")
            payload = objects[raw_index]
        elif isinstance(reference, dict):
            raw_index = None
            payload = reference
        else:
            fail("COMPONENT_SOURCE_REFERENCE_INVALID", source_id, "Component slot is neither an object reference nor an inline record")
        node_source_id = asset_id + "#" + str(object_index)
    expected_type = component.get("type")
    if not isinstance(expected_type, str) or payload.get("__type__") != expected_type:
        fail("COMPONENT_SOURCE_TYPE_MISMATCH", source_id, "IR component type differs from the exact serialized source record")
    fields = {k: deepcopy(v) for k, v in payload.items() if k not in _SOURCE_RESERVED_FIELDS}
    evidence = {
        "sourceAssetId": asset_id,
        "sourceAssetPath": asset.get("logicalPath"),
        "sourceImportPath": asset.get("importPath"),
        "sourceInputPin": asset.get("_sourceInputPin"),
        "sourceObjectIndex": object_index,
        "sourceComponentOrdinal": int(ordinal_text) if ordinal_text is not None else None,
        "sourceSerializedObjectIndex": raw_index,
        "sourceNodeId": node_source_id,
        "sourceComponentType": expected_type,
        "serializedFieldNames": sorted(fields),
        "serializedFieldsSha256": _digest(io.encoded(fields)),
    }
    return fields, evidence


def _component_inventory(components: list[dict[str, Any]]) -> dict[str, list[str]]:
    inventory: dict[str, list[str]] = {}
    for row in components:
        node = row.get("node")
        kind = row.get("type")
        if isinstance(node, str) and isinstance(kind, str):
            inventory.setdefault(node, []).append(kind)
    return {node: sorted(types) for node, types in inventory.items()}


def _target_name(key: str) -> str:
    return "creator3.8" if key == "creator" else "unity"


def _target_path_for_artifact(target: str, target_path: str) -> str:
    if not isinstance(target_path, str) or Path(target_path).is_absolute() or ".." in Path(target_path).parts:
        fail("BEHAVIOR_SCRIPT_PATH_INVALID", str(target_path), "Lowered script path is not a safe project-relative path")
    if target == "unity" and not target_path.startswith("Assets/Game/Scripts/Presentation/Recovered/"):
        fail("BEHAVIOR_SCRIPT_PATH_INVALID", target_path, "Unity behavior script escaped the recovered Presentation folder")
    if target == "creator" and not target_path.startswith("assets/Game/Scripts/Presentation/Recovered/"):
        fail("BEHAVIOR_SCRIPT_PATH_INVALID", target_path, "Creator behavior script escaped the recovered Presentation folder")
    return ("Targets/Unity/" if target == "unity" else "Targets/Creator/") + target_path


def _canonical_script_path(target: str, class_name: str) -> str:
    if not isinstance(class_name, str) or not _TARGET_CLASS_RE.fullmatch(class_name):
        fail("BEHAVIOR_CLASS_NAME_INVALID", str(class_name), "Recovered behavior class name must be a simple identifier")
    root = "Assets/Game/Scripts/Presentation/Recovered/" if target == "unity" else "assets/Game/Scripts/Presentation/Recovered/"
    suffix = ".cs" if target == "unity" else ".ts"
    return root + class_name + suffix


def _target_field_records(component_name: str, serialized_fields: dict[str, Any], lowering: Lowering) -> list[dict[str, Any]]:
    definitions = SUPPORTED_FIELDS.get(component_name, {})
    lowered_values = lowering.plan().get("serializedValues", {})
    result = []
    for name, (type_name, source_default) in sorted(definitions.items()):
        if name in serialized_fields:
            value = serialized_fields[name]
            origin = "serialized-source-field"
        else:
            value = lowered_values.get(name, source_default)
            origin = "source-module-default"
        if type_name == "bool":
            valid = isinstance(value, bool)
        else:
            valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        result.append({"name": name, "type": type_name, "value": value, "origin": origin,
                       "valueValidated": bool(valid), "valueValidation": "valid" if valid else "invalid source value; lowering must remain unsupported"})
    return result


def _module_public(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row.get(k) for k in ("sourceType", "name", "candidateId", "sourceBytes", "sha256", "sourceFormat")}


def _lower_target(
    component_name: str,
    source_type: str,
    module: dict[str, Any] | None,
    serialized_fields: dict[str, Any],
    source_bundle: bytes,
    base_module: dict[str, Any] | None,
    native_context: dict[str, Any],
    target_key: str,
) -> tuple[dict[str, Any], bytes | None]:
    target_name = _target_name(target_key)
    if module is None:
        reason = "No unique source RF module with this exact serialized component type was recovered."
        return ({"status": "unsupported", "component": component_name or None, "target": target_name,
                 "sourceSha256": None, "nativeType": None, "scriptPath": None, "scriptSha256": None,
                 "fields": [], "unsupportedBehaviors": [reason], "requiredProviders": [], "reason": reason}, None)
    if module.get("ambiguousSourceType"):
        reason = "Multiple distinct RF module byte regions claim this component type; no class was guessed."
        return ({"status": "unsupported", "component": module.get("name"), "target": target_name,
                 "sourceSha256": module.get("sha256"), "nativeType": None, "scriptPath": None, "scriptSha256": None,
                 "fields": [], "unsupportedBehaviors": [reason], "requiredProviders": [], "reason": reason,
                 "sourceModule": _module_public(module)}, None)
    if module.get("_bytes") is None:
        fail("SOURCE_MODULE_BYTES_MISSING", module.get("candidateId", "module"), "Verified module source bytes are absent")
    if component_name == "BaseEffect":
        reason = "BaseEffect is a helper inherited by ScaleBackEffect; direct component lowering has no independent source contract."
        return ({"status": "unsupported", "component": component_name, "target": target_name,
                 "sourceSha256": module.get("sha256"), "nativeType": None, "scriptPath": None,
                 "artifactPath": None, "scriptSha256": None, "fields": [],
                 "unsupportedBehaviors": [reason], "requiredProviders": [], "reason": reason,
                 "sourceModule": _module_public(module)}, None)
    base_bytes = base_module.get("_bytes") if base_module else None
    lowering = lower_behavior(
        component_name,
        source_type,
        module["_bytes"],
        target_name,
        serialized_fields,
        base_source_bytes=base_bytes,
        source_bundle_bytes=source_bundle,
        native_context=native_context,
    )
    plan = lowering.plan()
    script_bytes = None
    path = plan.get("scriptPath")
    script = lowering.script
    digest = None
    artifact_path = None
    if script is not None:
        if not isinstance(path, str):
            fail("BEHAVIOR_SCRIPT_PATH_MISSING", module.get("candidateId", "module"), "Lowerer returned a script without its planned path")
        # Lowering templates describe behavior, while this stage owns the target
        # layout contract. Canonical paths deliberately do not inherit template
        # folder choices from the previous delivery.
        path = _canonical_script_path(target_key, component_name)
        artifact_path = _target_path_for_artifact(target_key, path)
        script_bytes = script.encode("utf-8")
        digest = _digest(script_bytes)
    fields = _target_field_records(component_name, serialized_fields, lowering)
    return ({
        "status": plan["status"],
        "component": plan.get("component"),
        "target": target_name,
        "sourceSha256": plan.get("originalSourceSha256"),
        "nativeType": plan.get("nativeType"),
        "scriptPath": path,
        "artifactPath": artifact_path,
        "scriptSha256": digest,
        "fields": fields,
        "unsupportedBehaviors": plan.get("unsupportedBehaviors", []),
        "requiredProviders": plan.get("requiredProviders", []),
        "reason": plan.get("reason"),
        "sourceEvidence": plan.get("sourceEvidence", {}),
        "sourceModule": _module_public(module),
    }, script_bytes)


def _copy_source_stage(stage_root: Path, out: Path, stage_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = stage_manifest.get("files")
    if not isinstance(rows, list):
        fail("SOURCE_STAGE_FILES_MISSING", str(stage_root), "Owning normalize manifest has no files array")
    seen = set()
    copied = []
    for row in sorted(rows, key=lambda x: x.get("path", "")):
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            fail("SOURCE_STAGE_FILE_INVALID", str(stage_root), "Invalid source file row")
        relative = row["path"]
        if relative in seen:
            fail("SOURCE_STAGE_FILE_DUPLICATE", relative, "Duplicate source stage path")
        seen.add(relative)
        source_path = io.inside(stage_root, relative)
        if relative == "ir.json":
            # The parent IR bytes were verified with stage_bytes(); the derived IR is written below.
            continue
        destination = io.inside(out, relative)
        copy_verified(source_path, destination, row.get("sha256"), row.get("bytes"))
        copied.append({"path": relative, "sha256": row["sha256"], "bytes": row["bytes"], "owner": row.get("owner", "generated")})
    return copied


def project_ir(
    source_manifest_path: str | Path,
    ir_path: str | Path,
    source_bundle_path: str | Path,
    expected_bundle_sha256: str,
    output: str | Path,
) -> dict[str, Any]:
    """Create a fresh Prefab IR stage with source-bound local behavior candidates.

    Args are exact, manifest-owned stage paths. Source JS is parsed as data by the
    vendored static module reader and is never evaluated. Existing normalized
    resources are verified and copied byte-for-byte into the new stage.
    """
    source_manifest_path = io.safe(source_manifest_path)
    ir_path = io.safe(ir_path)
    source_bundle_path = io.safe(source_bundle_path)
    output = io.safe(output)
    if not isinstance(expected_bundle_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_bundle_sha256):
        fail("SOURCE_BUNDLE_PIN_INVALID", str(source_bundle_path), "Expected a lowercase SHA-256")
    if expected_bundle_sha256 != EXPECTED_SOURCE_BUNDLE_SHA256:
        fail("SOURCE_BUNDLE_PIN_UNSUPPORTED", str(source_bundle_path), "This behavior stage is pinned to the reviewed 21af08 source bundle")
    if source_manifest_path.name != "source-manifest.json":
        fail("SOURCE_MANIFEST_PATH_INVALID", str(source_manifest_path), "Expected the inspect stage source-manifest.json")
    if ir_path.name != "ir.json":
        fail("SOURCE_IR_PATH_INVALID", str(ir_path), "Expected a normalized stage ir.json")

    source_manifest_raw = io.stage_bytes(source_manifest_path)
    source_manifest = io.load(source_manifest_raw, max_nodes=8_000_000)
    source_manifest_sha = _digest(source_manifest_raw)
    source_manifest_stage = io.stage_manifest(source_manifest_path.parent)
    if not any(f.get("path") == source_manifest_path.name and f.get("sha256") == source_manifest_sha and f.get("bytes") == len(source_manifest_raw) for f in source_manifest_stage.get("files", [])):
        fail("SOURCE_MANIFEST_OWNERSHIP_INVALID", str(source_manifest_path), "Source manifest is not owned by its inspect stage")

    normalize_manifest = io.stage_manifest(ir_path.parent)
    ir_raw = io.stage_bytes(ir_path)
    if normalize_manifest.get("sourceManifestSha256") != source_manifest_sha:
        fail("SOURCE_MANIFEST_SHA_MISMATCH", str(ir_path), "IR stage was generated from a different inspect source manifest")
    if normalize_manifest.get("sourceProfile") != source_manifest.get("sourceProfile"):
        fail("SOURCE_PROFILE_MISMATCH", str(ir_path), "Normalize and inspect stages do not share a source profile")
    ir = io.load(ir_raw, max_nodes=8_000_000)
    if ir.get("sourceManifestSha256") != source_manifest_sha:
        fail("IR_SOURCE_MANIFEST_SHA_MISMATCH", str(ir_path), "IR provenance differs from its normalize manifest")
    components = ir.get("components")
    if not isinstance(components, list):
        fail("IR_COMPONENTS_MISSING", str(ir_path), "IR components must be an array")
    component_ids = [c.get("sourceId") for c in components if isinstance(c, dict) and c.get("sourceId") is not None]
    if len(component_ids) != len(set(component_ids)):
        fail("IR_COMPONENT_SOURCE_ID_DUPLICATE", str(ir_path), "Duplicate component sourceId prevents exact serialized binding")

    roots = source_manifest.get("sourceRoots")
    if not isinstance(roots, dict) or not isinstance(roots.get("main"), str):
        fail("SOURCE_MAIN_ROOT_MISSING", str(source_manifest_path), "Frozen source manifest has no main source root")
    expected_bundle_path = io.safe(Path(roots["main"]) / "game.js")
    if source_bundle_path != expected_bundle_path:
        fail("SOURCE_BUNDLE_PATH_MISMATCH", str(source_bundle_path), "Source bundle is not game.js under the manifest-pinned main source root")
    bundle = io.read(source_bundle_path, max_bytes=SOURCE_BUNDLE_BUDGET)
    bundle_sha = _digest(bundle)
    if bundle_sha != expected_bundle_sha256:
        fail("SOURCE_BUNDLE_SHA_MISMATCH", str(source_bundle_path), "Frozen source bundle hash differs from the required pin")

    output = io.new_output(output, (source_manifest_path, ir_path, source_bundle_path, source_manifest_path.parent, ir_path.parent))
    committed = False
    try:
        copied_source_files = _copy_source_stage(ir_path.parent, output, normalize_manifest)
        source_modules, source_module_parse = _index_source_modules(bundle)
        assets = _source_asset_index(source_manifest)
        inventory = _component_inventory(components)
        module_index = source_modules
        base_module = None
        base_rows = module_index.get(SOURCES["BaseEffect"]["source_type"], [])
        if len(base_rows) == 1:
            base_module = base_rows[0]
        diagnostics = []
        if source_module_parse.get("diagnostic"):
            diagnostic = source_module_parse["diagnostic"]
            diagnostics.append(io.diagnostic("SOURCE_MODULE_PARSE_PARTIAL", "sourceBundle", diagnostic.get("message", "Source module extraction is partial")))

        scripts: dict[tuple[str, str], dict[str, Any]] = {}
        class_identities: dict[tuple[str, str], tuple[str, str]] = {}
        def register_script(target_key: str, target_path: str, script_bytes: bytes, component_name: str,
                            source_module: dict[str, Any], role: str = "component") -> dict[str, Any]:
            artifact_path = _target_path_for_artifact(target_key, target_path)
            source_identity = (source_module.get("sourceType"), source_module.get("sha256"))
            class_key = (target_key, component_name)
            previous_identity = class_identities.get(class_key)
            if previous_identity is not None and previous_identity != source_identity:
                fail("BEHAVIOR_CLASS_NAME_COLLISION", artifact_path,
                     "Different source module identities claim one fixed target class name")
            class_identities[class_key] = source_identity
            key = (target_key, target_path)
            digest = _digest(script_bytes)
            previous = scripts.get(key)
            if previous and previous["sha256"] != digest:
                fail("BEHAVIOR_SCRIPT_COLLISION", artifact_path, "Two source identities generated different bytes for one target script path")
            if not previous:
                destination = io.inside(output, artifact_path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    fail("BEHAVIOR_SCRIPT_PATH_COLLISION", str(destination), "Behavior script overlaps a copied resource")
                destination.write_bytes(script_bytes)
                scripts[key] = {"target": target_key, "targetPath": target_path, "artifactPath": artifact_path,
                                "sha256": digest, "bytes": len(script_bytes), "className": component_name,
                                "role": role, "sourceModule": _module_public(source_module)}
            return scripts[key]

        behavior_records = []
        touched = 0
        source_type_occurrences: dict[str, int] = {}
        source_class_occurrences: dict[str, int] = {}
        source_module_matched_component_count = 0
        source_module_unmatched_component_count = 0
        by_source_type_name: dict[str, str] = {}
        for component in components:
            if not isinstance(component, dict):
                continue
            source_type = component.get("type")
            source_id = component.get("sourceId")
            module_rows = module_index.get(source_type, []) if isinstance(source_type, str) else []
            source_custom_type = (isinstance(source_type, str)
                                  and not source_type.startswith(("cc.", "sp.", "dragonBones.", "ccsg."))
                                  and component.get("supported") is False)
            is_custom = bool(module_rows) or source_custom_type
            if not is_custom:
                continue
            touched += 1
            source_type_occurrences[source_type] = source_type_occurrences.get(source_type, 0) + 1
            module = module_rows[0] if len(module_rows) == 1 else None
            if module is not None:
                source_module_matched_component_count += 1
            else:
                source_module_unmatched_component_count += 1
            component_name = module.get("name") if module else None
            if component_name:
                by_source_type_name[source_type] = component_name
                source_class_occurrences[component_name] = source_class_occurrences.get(component_name, 0) + 1
            serialized_fields: dict[str, Any] = {}
            serialized_evidence: dict[str, Any] = {"status": "unavailable", "reason": "exact source component identity was not recovered"}
            try:
                serialized_fields, serialized_evidence = _serialized_component(component, assets)
            except ParseError as error:
                serialized_evidence = {"status": "unavailable", "reason": error.message, "code": error.code}
                diagnostics.append(io.diagnostic(error.code, str(source_id), error.message, source_id))
            native_context = {"sameNodeComponentTypes": inventory.get(component.get("node"), [])}
            unity, unity_bytes = _lower_target(component_name or "", source_type, module, serialized_fields, bundle, base_module, native_context, "unity")
            creator, creator_bytes = _lower_target(component_name or "", source_type, module, serialized_fields, bundle, base_module, native_context, "creator")
            if serialized_evidence.get("status") == "unavailable":
                # A source identity gap must never accidentally enable a name-only lowering.
                for target_record in (unity, creator):
                    target_record["status"] = "unsupported"
                    target_record["scriptPath"] = None
                    target_record["artifactPath"] = None
                    target_record["scriptSha256"] = None
                    target_record["reason"] = serialized_evidence["reason"]
                    target_record["unsupportedBehaviors"] = [serialized_evidence["reason"]]
                unity_bytes = creator_bytes = None
            targets = {"unity": unity, "creator": creator}
            for target_key, target_bytes in (("unity", unity_bytes), ("creator", creator_bytes)):
                target_record = targets[target_key]
                if target_bytes is not None:
                    register_script(target_key, target_record["scriptPath"], target_bytes,
                                   target_record.get("component") or component_name or "unknown", module or {}, "component")
                    target_record["requiredScripts"] = []
                    if component_name == "ScaleBackEffect":
                        # The ScaleBack template derives from the separately source-pinned BaseEffect helper.
                        proof = target_record.get("sourceEvidence", {})
                        if proof.get("baseSourceSha256") != SOURCES["BaseEffect"]["sha256"]:
                            fail("BASE_EFFECT_SOURCE_PIN_MISMATCH", str(source_id), "ScaleBack lowering did not return the pinned inherited BaseEffect source")
                        if base_module is None or base_module.get("sha256") != SOURCES["BaseEffect"]["sha256"]:
                            fail("BASE_EFFECT_SOURCE_MISSING", str(source_id), "ScaleBack helper template lacks its exact BaseEffect source module")
                        suffix = ".cs" if target_key == "unity" else ".ts"
                        helper_path = _canonical_script_path(target_key, "BaseEffect")
                        helper_template = Path(__file__).with_name("targets") / "behaviors" / ("BaseEffect" + suffix)
                        helper_bytes = io.read(helper_template, max_bytes=2 * 1024 * 1024)
                        helper_record = register_script(target_key, helper_path, helper_bytes, "BaseEffect", base_module, "shared-helper")
                        helper_record.setdefault("helperFor", [])
                        if component_name not in helper_record["helperFor"]:
                            helper_record["helperFor"].append(component_name)
                        target_record["requiredScripts"].append({"targetPath": helper_path, "artifactPath": helper_record["artifactPath"],
                                                                 "sha256": helper_record["sha256"], "className": "BaseEffect"})
                if target_record["status"] not in ("lowered", "lowered_with_gaps"):
                    diagnostics.append(io.diagnostic("BEHAVIOR_UNSUPPORTED", str(source_id), target_record.get("reason") or "; ".join(target_record.get("unsupportedBehaviors", [])) or "No source-bound lowering", source_id))
                elif target_record["status"] == "lowered_with_gaps":
                    diagnostics.append(io.diagnostic("BEHAVIOR_LOWERED_WITH_GAPS", str(source_id), "; ".join(target_record.get("unsupportedBehaviors", [])), source_id))
            behavior = {
                "schema": "monkey-prefab-native-behavior/1",
                "className": component_name,
                "sourceType": source_type,
                "sourceId": source_id,
                "node": component.get("node"),
                "sourceModule": _module_public(module) if module else None,
                "sourceSerialized": serialized_evidence,
                "serializedFields": serialized_fields,
                "targets": targets,
                "runtimeComplete": False,
            }
            component["nativeBehavior"] = behavior
            behavior_records.append({"sourceId": source_id, "sourceType": source_type, "className": component_name,
                                     "unityStatus": unity["status"], "creatorStatus": creator["status"],
                                     "runtimeComplete": False})

        emitted_scripts = sorted(scripts.values(), key=lambda x: (x["target"], x["targetPath"]))
        # The derived root IR is the planner-facing index. Keep its script
        # references identical to the owning manifest rows and their stage hashes.
        ir["emittedBehaviorScripts"] = deepcopy(emitted_scripts)
        output_ir_path = output / "ir.json"
        output_ir_path.write_bytes(io.encoded(ir))
        target_counts: dict[str, dict[str, int]] = {"unity": {}, "creator": {}}
        for record in behavior_records:
            for target_key, field in (("unity", "unityStatus"), ("creator", "creatorStatus")):
                status = record[field]
                target_counts[target_key][status] = target_counts[target_key].get(status, 0) + 1
        report = {
            "schemaVersion": "monkey-prefab-behavior-stage/1",
            "stage": "source-bound-prefab-behavior-lowering",
            "sourceManifestPath": str(source_manifest_path),
            "sourceManifestSha256": source_manifest_sha,
            "sourceIRPath": str(ir_path),
            "sourceIRSha256": _digest(ir_raw),
            "sourceBundlePath": str(source_bundle_path),
            "sourceBundleSha256": bundle_sha,
            "sourceBundleBytes": len(bundle),
            "sourceBundleExecuted": False,
            "sourceProfile": normalize_manifest.get("sourceProfile"),
            "sourceCodeModuleIndex": source_module_parse,
            "behaviorRuleVersion": RULE_VERSION,
            "parentNormalizeManifestSha256": _digest(io.read(ir_path.parent / "manifest.json", max_bytes=STAGE_MANIFEST_BUDGET)),
            "copiedSourceFileCount": len(copied_source_files),
            "originalIRComponentCount": len(components),
            "nativeBehaviorComponentCount": touched,
            "sourceModuleMatchedComponentCount": source_module_matched_component_count,
            "sourceModuleUnmatchedComponentCount": source_module_unmatched_component_count,
            "sourceComponentTypeCount": len(source_type_occurrences),
            "sourceComponentOccurrencesByType": dict(sorted(source_type_occurrences.items())),
            "sourceClassOccurrencesByName": dict(sorted(source_class_occurrences.items())),
            "loweredComponentCount": sum(1 for r in behavior_records if r["unityStatus"].startswith("lowered") or r["creatorStatus"].startswith("lowered")),
            "runtimeComplete": False,
            "targetStatusCounts": target_counts,
            "emittedBehaviorScripts": emitted_scripts,
            "componentBehaviors": behavior_records,
            "diagnostics": diagnostics,
            "limitations": [
                "All behavior records remain runtimeComplete=false; no target prefab/scene script binding is performed here.",
                "AutoScaleComp stays unsupported without a real monkey.viewport-notch/1 provider binding and same-node layout clearance.",
                "The source stopAllActions behavior remains a gap for BreathEffect and ScaleBackEffect; generated adapters stop only their own tracked behavior.",
                "ScaleBackEffect Unity lowering stays unsupported on nodes with cc.Widget until monkey.widget-alignment/1 is explicitly provided.",
            ],
            "scopeMode": normalize_manifest.get("scopeMode", "selected-prefabs"),
            "status": "partial",
        }
        io.finish(output, report)
        committed = True
        return {"output": str(output), "irPath": str(output_ir_path), "manifestPath": str(output / "manifest.json"),
                "ir": ir, "emittedBehaviorScripts": emitted_scripts, "manifest": report}
    except Exception:
        if not committed and output.exists() and output.is_dir():
            shutil.rmtree(output)
        raise
