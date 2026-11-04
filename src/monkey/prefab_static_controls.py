"""Frozen, source-backed static bindings for Creator EditBox and Graphics."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from pathlib import Path


_SUPPORTED_GRAPHICS_PROFILE_SHA256 = "a4db92cdb68f3fb8366c189daa5f9a2e318c28f6674e80ed01f97868633a9b76"
_UNITY_GRAPHICS_SHADER = "Assets/Game/Content/Materials/StaticControls/NativeStaticGraphics.shader"


class StaticControlError(ValueError):
    pass


_CONTROL_TYPES = {"cc.EditBox", "cc.Graphics"}
_EDITBOX_FIELDS = {
    "_N$background": ("background", "cc.Sprite"),
    "_N$placeholderLabel": ("placeholderLabel", "cc.Label"),
    "_N$textLabel": ("textLabel", "cc.Label"),
}
_GRAPHICS_METADATA = {"__type__", "node", "_materials"}


def _component_identity(row):
    source_id = row.get("sourceId")
    if not isinstance(source_id, str) or "#" not in source_id:
        raise StaticControlError(f"invalid source component identity: {source_id!r}")
    return source_id


def _manifest_binding(plan, manifest):
    source_path = plan.get("sourceManifestPath")
    expected = plan.get("sourceManifestSha256")
    if not isinstance(source_path, str) or not isinstance(expected, str) or len(expected) != 64:
        raise StaticControlError("plan is not bound to a source manifest path and SHA-256")
    path = Path(source_path)
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise StaticControlError(f"bound source manifest is unavailable: {source_path}") from error
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise StaticControlError(f"bound source manifest SHA-256 differs: expected {expected}, got {actual}")
    try:
        frozen = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise StaticControlError("bound source manifest is not valid UTF-8 JSON") from error
    if not isinstance(manifest, Mapping) or not isinstance(frozen, Mapping):
        raise StaticControlError("manifest must be a JSON object")
    # Bind relevant documents to the hash-checked bytes instead of trusting a
    # caller's in-memory edits to the manifest.
    supplied = {a.get("sourceId"): a for a in manifest.get("assets", []) if isinstance(a, Mapping)}
    hashed = {a.get("sourceId"): a for a in frozen.get("assets", []) if isinstance(a, Mapping)}
    if not isinstance(manifest.get("assets"), list) or not isinstance(frozen.get("assets"), list):
        raise StaticControlError("manifest.assets must be an array")
    if set(supplied) != set(hashed):
        raise StaticControlError("in-memory source manifest asset identities differ from hash-bound bytes")
    for source_id, asset in supplied.items():
        source = hashed[source_id]
        if any(asset.get(key) != source.get(key) for key in ("kind", "bundle", "logicalPath", "redirectTarget", "document")):
            raise StaticControlError(f"in-memory source manifest entry differs from bound bytes: {source_id}")
    return actual


def _uuid_targets(manifest):
    targets = {}
    for asset in manifest["assets"]:
        if not isinstance(asset, Mapping) or not isinstance(asset.get("sourceId"), str):
            continue
        bundle, sep, uuid = asset["sourceId"].partition(":")
        if not sep or not uuid:
            continue
        targets.setdefault((bundle, uuid), []).append(asset)
    return targets


def _asset_for_uuid(manifest, bundle, uuid):
    index = _uuid_targets(manifest)
    candidates = index.get((bundle, uuid), [])
    if not candidates:
        candidates = [asset for (candidate_bundle, candidate_uuid), rows in index.items()
                      if candidate_uuid == uuid for asset in rows]
    if len(candidates) != 1:
        raise StaticControlError(f"material UUID is absent or ambiguous in source manifest: {uuid}")
    asset = candidates[0]
    original = asset["sourceId"]
    seen = set()
    while asset.get("kind") == "redirect":
        if original in seen:
            raise StaticControlError(f"material redirect cycle at {original}")
        seen.add(original)
        target = asset.get("redirectTarget")
        asset = next((row for row in manifest["assets"] if row.get("sourceId") == target), None)
        if asset is None:
            raise StaticControlError(f"material redirect target missing: {target}")
    return original, asset


def _raw_component(manifest, source_id):
    asset_id, _, tail = source_id.partition("#")
    asset = next((a for a in manifest["assets"] if a.get("sourceId") == asset_id), None)
    if asset is None or asset.get("kind") not in ("cc.Prefab", "cc.SceneAsset"):
        raise StaticControlError(f"source component asset is absent or not a Prefab/Scene: {asset_id}")
    document = asset.get("document")
    objects = document.get("instances") if isinstance(document, Mapping) else None
    if not isinstance(objects, list):
        raise StaticControlError(f"source component has no frozen document.instances: {asset_id}")
    parts = tail.split("/components/")
    try:
        obj_index = int(parts[0])
        if len(parts) == 2:
            node_index = int(parts[0])
            ordinal = int(parts[1])
            node = objects[node_index]
            components = node.get("_components", [])
            ref = components[ordinal]
            if isinstance(ref, Mapping) and type(ref.get("__id__")) is int:
                obj_index = ref["__id__"]
            elif isinstance(ref, Mapping) and ref.get("__type__"):
                if ref.get("__type__") != "cc.EditBox" and ref.get("__type__") != "cc.Graphics":
                    raise StaticControlError(f"unexpected inline static control type at {source_id}")
                return asset, objects, node_index, ref
            else:
                raise StaticControlError(f"source component row cannot be resolved: {source_id}")
        if len(parts) not in (1, 2):
            raise ValueError
        raw = objects[obj_index]
    except (IndexError, TypeError, ValueError) as error:
        raise StaticControlError(f"source component identity is outside its frozen document: {source_id}") from error
    if not isinstance(raw, Mapping):
        raise StaticControlError(f"source component object is malformed: {source_id}")
    return asset, objects, obj_index, raw


def _node_reference(asset, objects, raw_ref, expected_type, label):
    if not isinstance(raw_ref, Mapping) or type(raw_ref.get("__id__")) is not int:
        raise StaticControlError(f"{label} must be an exact serialized object reference")
    index = raw_ref["__id__"]
    if index < 0 or index >= len(objects):
        raise StaticControlError(f"{label} object index is outside document.instances")
    target = objects[index]
    if not isinstance(target, Mapping) or target.get("__type__") != expected_type:
        actual = target.get("__type__") if isinstance(target, Mapping) else None
        raise StaticControlError(f"{label} expected {expected_type}, observed {actual}")
    return f"{asset['sourceId']}#{index}"


def _material_binding(manifest, bundle, raw_material):
    if not isinstance(raw_material, Mapping) or not isinstance(raw_material.get("__uuid__"), str):
        raise StaticControlError("Graphics material is not a serialized source UUID reference")
    source_id, asset = _asset_for_uuid(manifest, bundle, raw_material["__uuid__"])
    document = asset.get("document")
    rows = document.get("instances") if isinstance(document, Mapping) else None
    root = rows[document.get("root", 0)] if isinstance(rows, list) and rows else None
    if asset.get("kind") != "cc.Material" or not isinstance(root, Mapping) or root.get("__type__") != "cc.Material":
        raise StaticControlError(f"Graphics material is not a serialized cc.Material: {asset.get('sourceId')}")
    technique_data = root.get("_techniqueData")
    first_technique = technique_data.get("0") if isinstance(technique_data, Mapping) else None
    defines = first_technique.get("defines") if isinstance(first_technique, Mapping) else None
    if not isinstance(defines, Mapping) or dict(defines):
        raise StaticControlError("Graphics source material technique 0 has unreviewed defines")
    effect_ref = root.get("_effectAsset")
    if not isinstance(effect_ref, Mapping) or not isinstance(effect_ref.get("__uuid__"), str):
        raise StaticControlError("Graphics material has no exact source effect reference")
    effect_id, effect = _asset_for_uuid(manifest, asset.get("bundle", bundle), effect_ref["__uuid__"])
    effect_rows = effect.get("document", {}).get("instances", [])
    effect_doc = effect_rows[0] if effect_rows else None
    effect_name = effect_doc.get("_name") if isinstance(effect_doc, Mapping) else None
    if effect.get("kind") != "cc.EffectAsset" or effect_name != "builtin-2d-graphics":
        raise StaticControlError(f"Graphics source effect is outside the proven native profile: {effect_name!r}")
    shader_rows = effect_doc.get("shaders") if isinstance(effect_doc, Mapping) else None
    if not isinstance(shader_rows, list) or len(shader_rows) != 1 or not isinstance(shader_rows[0], Mapping):
        raise StaticControlError("Graphics effect does not contain one unambiguous frozen shader definition")
    glsl = shader_rows[0].get("glsl1")
    if not isinstance(glsl, Mapping) or not isinstance(glsl.get("vert"), str) or not isinstance(glsl.get("frag"), str):
        raise StaticControlError("Graphics effect GLSL1 vertex/fragment source is absent")
    def normalize_glsl(source):
        return "\n".join(line.rstrip() for line in source.replace("\r\n", "\n").replace("\r", "\n").strip().splitlines()).strip()
    normalized_vertex = normalize_glsl(glsl["vert"])
    normalized_fragment = normalize_glsl(glsl["frag"])
    effect_profile_sha = hashlib.sha256((normalized_vertex + "\0" + normalized_fragment).encode("utf-8")).hexdigest()
    if effect_profile_sha != _SUPPORTED_GRAPHICS_PROFILE_SHA256:
        raise StaticControlError(f"Graphics GLSL profile is unreviewed: {effect_profile_sha}")
    shader_source_path = Path(__file__).parent / "targets/materials/static_controls/NativeStaticGraphics.shader"
    try:
        shader_sha = hashlib.sha256(shader_source_path.read_bytes()).hexdigest()
    except OSError as error:
        raise StaticControlError("Unity static Graphics shader payload is unavailable") from error
    source_effect_sha = hashlib.sha256(json.dumps(effect_doc, ensure_ascii=False, sort_keys=True,
                                                  separators=(",", ":")).encode("utf-8")).hexdigest()
    unity_profile = "cocos24-builtin-2d-graphics-glsl1-vertex-color-distance-v1"
    return {
        "sourceId": source_id,
        "resolvedSourceId": asset["sourceId"],
        "sourceMaterialName": root.get("_name"),
        "sourceTechniqueIndex": 0,
        "sourceTechniqueDefinesJson": "{}",
        "effectSourceId": effect_id,
        "effectName": effect_name,
        "sourceEffectUuid": effect_ref["__uuid__"],
        "nativeCreatorMaterialLookup": "builtin-graphics",
        "unityProfile": unity_profile,
        "sourceEffectDocumentSha256": source_effect_sha,
        "sourceEffectNormalizedGlslSha256": effect_profile_sha,
        "unityShaderPath": _UNITY_GRAPHICS_SHADER,
        "unityShaderSha256": shader_sha,
        "unityMaterialGuid": uuid.uuid5(uuid.NAMESPACE_URL,
            "monkey/static-controls/native-static-graphics/material/" + effect_profile_sha).hex,
        "unityMaterialPath": "Assets/Game/Content/Materials/StaticControls/NativeStaticGraphics_" + effect_profile_sha[:16] + ".mat",
    }


def _commands_empty(raw):
    # Creator 2.4 Graphics does not serialize its draw-method calls as commands.
    # Only explicit command payloads can prove a non-empty frozen initial state.
    for key in ("commands", "_commands", "path", "_path", "points", "_points"):
        value = raw.get(key)
        if value not in (None, [], {}):
            return False
    return True


def prepare(plan, manifest):
    """Attach verified source-backed static-control bindings to matching components."""
    if not isinstance(plan, Mapping) or not isinstance(manifest, Mapping):
        raise StaticControlError("plan and manifest must be mappings")
    manifest_sha = _manifest_binding(plan, manifest)
    components = plan.get("components")
    if not isinstance(components, list):
        raise StaticControlError("plan.components must be an array")
    component_by_id = {}
    for row in components:
        if not isinstance(row, dict):
            raise StaticControlError("plan.components contains a non-object row")
        source_id = _component_identity(row)
        if source_id in component_by_id:
            raise StaticControlError(f"duplicate plan component identity: {source_id}")
        component_by_id[source_id] = row
    bindings = []
    for component in components:
        source_type = component.get("type")
        if source_type not in _CONTROL_TYPES:
            continue
        source_id = component["sourceId"]
        asset, objects, object_index, raw = _raw_component(manifest, source_id)
        if raw.get("__type__") != source_type:
            raise StaticControlError(f"source component type differs from plan: {source_id}")
        raw_node = _node_reference(asset, objects, raw.get("node"), "cc.Node", "component.node")
        if raw_node != component.get("node"):
            raise StaticControlError(f"source component node identity differs from plan: {source_id}")
        binding = {
            "schemaVersion": 1,
            "sourceId": source_id,
            "node": component.get("node"),
            "sourceType": source_type,
            "sourceManifestSha256": manifest_sha,
            "sourceEnabled": component.get("enabled"),
            "enabled": False,
            "sourceObjectIndex": object_index,
        }
        if source_type == "cc.EditBox":
            if type(raw.get("maxLength")) is not int or raw["maxLength"] < 0:
                raise StaticControlError(f"EditBox maxLength is not a serialized integer: {source_id}")
            refs = []
            for source_field, (target_field, target_type) in _EDITBOX_FIELDS.items():
                target_id = _node_reference(asset, objects, raw.get(source_field), target_type, source_field)
                target_component = component_by_id.get(target_id)
                if (target_component is None or target_component.get("type") != target_type or
                        target_component.get("node") is None):
                    raise StaticControlError(f"EditBox reference has no exact planned native component: {target_id}")
                refs.append({"sourceField": source_field, "field": target_field,
                             "sourceId": target_id, "sourceType": target_type,
                             "nativeNodeSourceId": target_component["node"]})
            if set(raw) - {"__type__", "node", "_enabled", "maxLength", *_EDITBOX_FIELDS}:
                raise StaticControlError(f"EditBox has unhandled serialized fields: {source_id}")
            binding.update({"maxLength": raw["maxLength"], "references": refs,
                            "nativeCreatorType": "cc.EditBox", "inputBehavior": "disabled-static-only"})
        else:
            if not _commands_empty(raw):
                raise StaticControlError(f"Graphics has a serialized non-empty command payload: {source_id}")
            unhandled = set(raw) - _GRAPHICS_METADATA
            if unhandled:
                raise StaticControlError(f"Graphics has unhandled serialized fields {sorted(unhandled)}: {source_id}")
            materials = raw.get("_materials")
            if not isinstance(materials, list) or not materials:
                raise StaticControlError(f"Graphics source material reference is absent: {source_id}")
            bundle = asset.get("bundle", source_id.split(":", 1)[0])
            binding.update({"materials": [_material_binding(manifest, bundle, ref) for ref in materials],
                            "sourceDrawingCommands": "not-serialized-empty-in-fixed-state",
                            "nativeCreatorType": "cc.Graphics", "drawingBehavior": "disabled-static-only"})
        component["staticControlBinding"] = binding
        bindings.append(binding)
    return {"schemaVersion": 1, "namespace": plan.get("namespace"),
            "sourceManifestSha256": manifest_sha, "bindings": bindings, "diagnostics": []}


def emit_unity(report, output):
    """Copy the reviewed UI-compatible Unity shader payload into a candidate."""
    if not isinstance(report, Mapping) or not isinstance(report.get("bindings"), list):
        raise StaticControlError("static control report is malformed")
    materials = [m for b in report["bindings"] if isinstance(b, Mapping)
                 for m in b.get("materials", []) if isinstance(m, Mapping) and m.get("unityProfile")]
    if not materials:
        return []
    profiles = {(m.get("unityProfile"), m.get("unityShaderPath"), m.get("unityShaderSha256"),
                 m.get("sourceEffectNormalizedGlslSha256")) for m in materials}
    if len(profiles) != 1:
        raise StaticControlError("multiple or inconsistent Unity Graphics effect profiles in one plan")
    profile, relative, expected_sha, source_effect_sha = next(iter(profiles))
    if profile != "cocos24-builtin-2d-graphics-glsl1-vertex-color-distance-v1" or source_effect_sha != _SUPPORTED_GRAPHICS_PROFILE_SHA256:
        raise StaticControlError("Unity Graphics shader profile is not the reviewed source effect")
    source = Path(__file__).parent / "targets/materials/static_controls/NativeStaticGraphics.shader"
    payload = source.read_bytes()
    actual_sha = hashlib.sha256(payload).hexdigest()
    if actual_sha != expected_sha:
        raise StaticControlError("Unity Graphics shader payload hash differs from the bound plan")
    root = Path(output).resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise StaticControlError("Unity Graphics shader output escapes its candidate") from error
    if not target.as_posix().startswith((root / "Assets").as_posix() + "/"):
        raise StaticControlError("Unity Graphics shader must be stored under candidate Assets")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != expected_sha:
        raise StaticControlError(f"refusing to overwrite changed Unity Graphics shader: {relative}")
    if not target.exists():
        target.write_bytes(payload)
    namespace = report.get("namespace")
    if not isinstance(namespace, str) or not namespace:
        raise StaticControlError("Unity Graphics shader asset requires the frozen plan namespace")
    guid = uuid.uuid5(uuid.NAMESPACE_URL,
                      f"monkey/{namespace}/static-controls/native-static-graphics/{source_effect_sha}").hex
    meta = Path(str(target) + ".meta")
    expected_meta = f"fileFormatVersion: 2\nguid: {guid}\n"
    if meta.exists() and meta.read_text(encoding="utf-8") != expected_meta:
        raise StaticControlError(f"Unity Graphics shader meta differs from the bound GUID: {relative}.meta")
    if not meta.exists():
        meta.write_text(expected_meta, encoding="utf-8")
    return [{"path": relative, "sha256": expected_sha, "guid": guid,
             "sourceEffectNormalizedGlslSha256": source_effect_sha}]


def verify(bindings, readback, target="creator"):
    """Strictly compare static-control readback rows with their frozen bindings."""
    if not isinstance(bindings, list) or not isinstance(readback, list):
        return ["static control bindings/readback must both be arrays"]
    expected = {row.get("sourceId"): row for row in bindings if isinstance(row, Mapping)}
    actual = {}
    errors = []
    for row in readback:
        if not isinstance(row, Mapping) or not isinstance(row.get("sourceId"), str):
            errors.append("malformed native static-control readback row")
            continue
        sid = row["sourceId"]
        if sid in actual:
            errors.append(f"duplicate native static-control identity: {sid}")
        actual[sid] = row
    if set(actual) != set(expected):
        errors.append("native static-control source identities differ")
    for sid, spec in expected.items():
        row = actual.get(sid)
        if row is None:
            continue
        expected_type=("MonkeyStaticEditBox" if spec["sourceType"]=="cc.EditBox" else spec.get("nativeCreatorType")) if target=="creator" else ("NativeStaticEditBox" if spec['sourceType']=='cc.EditBox' else "NativeStaticGraphics")
        if row.get("nativeType") != expected_type or row.get("enabled") is not False:
            errors.append(f"native static-control type/disabled state differs: {sid}")
        if spec.get("sourceType") == "cc.EditBox":
            if row.get("maxLength") != spec.get("maxLength"):
                errors.append(f"EditBox maxLength differs: {sid}")
            actual_refs = row.get("references")
            want_refs = spec.get("references")
            if not isinstance(actual_refs, list) or len(actual_refs) != len(want_refs):
                errors.append(f"EditBox reference count differs: {sid}")
                continue
            for expected_ref in want_refs:
                matches = [ref for ref in actual_refs if isinstance(ref, Mapping) and
                           ref.get("field") == expected_ref["field"]]
                if len(matches) != 1 or matches[0].get("sourceId") != expected_ref["sourceId"] or matches[0].get("verified") is not True:
                    errors.append(f"EditBox native reference differs: {sid}/{expected_ref['field']}")
        else:
            if row.get("sourceDrawingCommands") != "not-serialized-empty-in-fixed-state":
                errors.append(f"Graphics source fixed-state evidence differs: {sid}")
            got = row.get("materials")
            want = spec.get("materials")
            if not isinstance(got, list) or len(got) != len(want):
                errors.append(f"Graphics material count differs: {sid}")
                continue
            for index, expected_material in enumerate(want):
                observed = got[index]
                native_identity=(observed.get("assetGuid")==expected_material.get("unityMaterialGuid") and bool(observed.get("localFileId")) and observed.get("persistent")is True) if target=="unity" else (observed.get("nativeUuid")=="f0416e68-0200-4b77-a926-4f9d16e494da" and observed.get("nativeEffectUuid")=="1c02ae6f-4492-4915-b8f8-7492a3b1e4cd")
                if (not isinstance(observed, Mapping) or observed.get("sourceId") != expected_material.get("sourceId") or
                        not native_identity or observed.get("verified") is not True):
                    errors.append(f"Graphics native material identity differs: {sid}/{index}")
    return errors
