"""Attach and export bridge for the bounded Sprite outline material profile.

``attach`` creates an immutable plan stage with every target payload, helper
and deterministic meta copied under stage ownership. ``emit_attached`` writes
those pinned files into a target.export-owned output directory without creating
or finishing a second candidate manifest. ``emit`` remains a standalone fresh
overlay API. None of these functions edits shared target importers or launches
an Editor.
"""
from __future__ import annotations

import base64
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from . import io
from .prefab_sprite_outline_materials import (
    PROFILE,
    SpriteOutlineProfileError,
    _validate_binding_spec,
)


class SpriteOutlinePipelineError(ValueError):
    """Source plan, outline profile or create-only stage is inconsistent."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _binding_plan(path: Path, expected: str) -> tuple[dict[str, Any], bytes]:
    raw = io.read(path)
    if _sha(raw) != expected:
        raise SpriteOutlinePipelineError("outline binding-plan SHA-256 differs")
    plan = io.load(raw, max_nodes=1_000_000, max_depth=96)
    if not isinstance(plan, dict) or plan.get("schema") != "monkey-prefab-sprite-outline-plan/1":
        raise SpriteOutlinePipelineError("unsupported outline binding-plan schema")
    spec = plan.get("spec")
    try:
        _validate_binding_spec(spec)
    except SpriteOutlineProfileError as error:
        raise SpriteOutlinePipelineError(str(error)) from error
    return plan, raw


def _resource_ids(plan: dict) -> set[str]:
    ids = set()
    for collection, keys in ((plan.get("textures", []), ("id", "sourceId")),
                             (plan.get("assets", []), ("id", "sourceId")),
                             (plan.get("spriteFrames", []), ("sourceId", "id"))):
        if not isinstance(collection, list):
            continue
        for row in collection:
            if isinstance(row, dict):
                ids.update(row[key] for key in keys if isinstance(row.get(key), str) and row[key])
    return ids


def _resource_row(plan: dict, source_id: str) -> dict | None:
    matches = []
    for collection in (plan.get("textures", []), plan.get("assets", []), plan.get("spriteFrames", [])):
        if not isinstance(collection, list):
            continue
        for row in collection:
            if isinstance(row, dict) and source_id in (row.get("id"), row.get("sourceId")):
                matches.append(row)
    if len(matches) > 1:
        # A texture may be represented in more than one plan collection only
        # when both records agree on its dimensions.
        vectors = [row.get("size", row.get("originalSize")) for row in matches]
        if any(vector != vectors[0] for vector in vectors[1:]):
            raise SpriteOutlinePipelineError("SpriteFrame target resource geometry is ambiguous: " + source_id)
    return matches[0] if matches else None


def _target_name(target_profile: str) -> str:
    if target_profile == "unity-6000.6.2f1-ugui":
        return "unity"
    if target_profile == "cocos-3.8.8":
        return "creator"
    raise SpriteOutlinePipelineError("target plan profile has no Sprite outline stage adapter")


def _unity_meta(source_name: str) -> bytes:
    guid = uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{PROFILE}:{source_name}").hex
    return (f"fileFormatVersion: 2\nguid: {guid}\nMonoImporter:\n  externalObjects: {{}}\n"
            "  serializedVersion: 2\n  defaultReferences: []\n  executionOrder: 0\n  icon: {instanceID: 0}\n"
            "  userData: \n  assetBundleName: \n  assetBundleVariant: \n").encode("utf-8")


def _stage_owned_payloads(binding_plan: dict, target: str, plan_root: str | Path | None) -> list[dict]:
    """Resolve and pin all data needed by one target before the attach stage is created."""
    if target not in ("unity", "creator"):
        raise SpriteOutlinePipelineError("unsupported outline target")
    repo_root = io.safe(plan_root) if plan_root is not None else Path(__file__).resolve().parents[2]
    prefix = "Assets/" if target == "unity" else "assets/"
    records: list[dict] = []
    seen_target: set[str] = set()

    def add(target_path: str, data: bytes, role: str, origin: str) -> None:
        if (not isinstance(target_path, str) or not target_path.startswith(prefix if role == "shader-effect-payload" else
                ("Assets/" if target == "unity" else "extensions/monkey-import/")) or
                ".." in Path(target_path).parts or Path(target_path).is_absolute()):
            raise SpriteOutlinePipelineError("unsafe outline target path: " + str(target_path))
        if target_path in seen_target:
            raise SpriteOutlinePipelineError("duplicate outline target path: " + target_path)
        seen_target.add(target_path)
        records.append({"targetPath": target_path,
                        "stagePath": "sprite-outline-owned/" + target_path,
                        "sha256": _sha(data), "bytes": len(data), "role": role,
                        "origin": origin, "data": data})

    owned_files = binding_plan.get("ownedFiles")
    if not isinstance(owned_files, list):
        raise SpriteOutlinePipelineError("outline binding plan has no ownedFiles array")
    for row in owned_files:
        if not isinstance(row, dict):
            raise SpriteOutlinePipelineError("outline owned-file record is malformed")
        target_path = row.get("path")
        if not isinstance(target_path, str) or not target_path.startswith(prefix):
            continue
        source_path = row.get("sourcePath")
        if source_path:
            try:
                data = io.read(io.inside(repo_root, source_path))
            except Exception as error:
                raise SpriteOutlinePipelineError("owned outline source file is unavailable: " + source_path) from error
        else:
            try:
                data = base64.b64decode(row.get("contentBase64", ""), validate=True)
            except (ValueError, TypeError) as error:
                raise SpriteOutlinePipelineError("owned inline outline payload is invalid: " + target_path) from error
        if len(data) != row.get("byteLength") or _sha(data) != row.get("sha256"):
            raise SpriteOutlinePipelineError("owned outline payload differs from its SHA/length pin: " + target_path)
        add(target_path, data, "shader-effect-payload", source_path or "inline-pinned-payload")

    helper_root = Path(__file__).parents[2] / "src/monkey/targets/materials/sprite_outline"
    if target == "unity":
        helpers = [
            ("UnitySpriteOutlineMaterialBindings.cs", "Assets/Game/Editor/Conversion/SpriteOutline/UnitySpriteOutlineMaterialBindings.cs"),
            ("UnitySpriteOutlineImporter.cs", "Assets/Game/Editor/Conversion/SpriteOutline/UnitySpriteOutlineImporter.cs"),
        ]
        for source_name, target_path in helpers:
            try:
                data = io.read(helper_root / source_name)
            except Exception as error:
                raise SpriteOutlinePipelineError("owned Unity outline helper is unavailable: " + source_name) from error
            add(target_path, data, "editor-helper", "monkey-package:" + source_name)
            add(target_path + ".meta", _unity_meta(source_name), "editor-helper-meta", "deterministic-profile-meta")
    else:
        helpers = [
            ("CreatorSpriteOutlineMaterialBindings.js", "extensions/monkey-import/sprite-outline-material-bindings.js"),
            ("CreatorSpriteOutlineImporter.js", "extensions/monkey-import/sprite-outline-importer.js"),
        ]
        for source_name, target_path in helpers:
            try:
                data = io.read(helper_root / source_name)
            except Exception as error:
                raise SpriteOutlinePipelineError("owned Creator outline helper is unavailable: " + source_name) from error
            add(target_path, data, "editor-helper", "monkey-package:" + source_name)
    if not any(row["role"] == "shader-effect-payload" for row in records):
        raise SpriteOutlinePipelineError("outline binding plan has no payload for target " + target)
    return records


def attach(plan_path: str | Path, expected_plan_sha256: str,
           outline_plan_path: str | Path, expected_outline_plan_sha256: str,
           out: str | Path, plan_root: str | Path | None = None) -> dict:
    """Attach one verified source material profile to a fresh target plan stage.

    Only the exact mapped Sprite components lose the two handoff diagnostics
    produced for the unsupported Material. Serialized fields, materials,
    frame references, and all unrelated components/diagnostics are retained.
    """
    source_path = io.safe(plan_path)
    binding_path = io.safe(outline_plan_path)
    try:
        source_raw = io.stage_bytes(source_path)
        source = io.load(source_raw, max_nodes=8_000_000, max_depth=128)
    except Exception as error:
        raise SpriteOutlinePipelineError("target plan must be an intact owned stage plan.json") from error
    if _sha(source_raw) != expected_plan_sha256:
        raise SpriteOutlinePipelineError("target plan SHA-256 differs from expected_plan_sha256")
    binding_plan, binding_raw = _binding_plan(binding_path, expected_outline_plan_sha256)
    spec = binding_plan["spec"]
    if source.get("sourceManifestSha256") != spec.get("sourceManifestSha256"):
        raise SpriteOutlinePipelineError("target plan and outline profile have different source manifests")
    target = _target_name(source.get("targetProfile"))
    owned_payloads = _stage_owned_payloads(binding_plan, target, plan_root)
    if source.get("spriteOutlineBinding"):
        raise SpriteOutlinePipelineError("target plan already contains a Sprite outline binding")
    components = source.get("components")
    nodes = source.get("nodes")
    if not isinstance(components, list) or not isinstance(nodes, list):
        raise SpriteOutlinePipelineError("target plan lacks node/component records")
    component_by_id = {row.get("sourceId"): row for row in components if isinstance(row, dict)}
    node_ids = {row.get("sourceId") for row in nodes if isinstance(row, dict)}
    diagnostics = source.get("diagnostics", [])
    if not isinstance(diagnostics, list):
        raise SpriteOutlinePipelineError("target plan diagnostics must be an array")
    allowed_codes = {"CUSTOM_MATERIAL_HANDOFF", "COMPONENT_HANDOFF"}
    bound_ids = [row["sourceId"] for row in spec["spriteBindings"]]
    if not bound_ids or len(bound_ids) != len(set(bound_ids)):
        raise SpriteOutlinePipelineError("outline binding source component IDs are empty or duplicated")
    resource_ids = _resource_ids(source)
    missing = []
    for binding in spec["spriteBindings"]:
        sid = binding["sourceId"]
        component = component_by_id.get(sid)
        if (not component or component.get("type") != "cc.Sprite" or
                component.get("spriteFrame") != binding["spriteFrameSourceId"] or
                not isinstance(component.get("node"), str) or component["node"] not in node_ids or
                spec["materialSourceId"] not in component.get("materials", [])):
            raise SpriteOutlinePipelineError("outline source Sprite edge differs from target plan: " + sid)
        if binding["spriteFrameSourceId"] not in resource_ids:
            raise SpriteOutlinePipelineError("outline SpriteFrame resource is absent from target plan: " + binding["spriteFrameSourceId"])
        resource = _resource_row(source, binding["spriteFrameSourceId"])
        if resource is None:
            raise SpriteOutlinePipelineError("outline SpriteFrame geometry is absent from target plan: " + binding["spriteFrameSourceId"])
        frame_size = resource.get("size", resource.get("originalSize"))
        expected_size = spec["properties"]["outlineTextureSize"]
        if not isinstance(frame_size, list) or len(frame_size) < 2 or frame_size[:2] != expected_size:
            raise SpriteOutlinePipelineError("outlineTextureSize differs from the planned SpriteFrame dimensions: " + binding["spriteFrameSourceId"])
        rows = [row for row in diagnostics if isinstance(row, dict) and row.get("sourceId") == sid]
        codes = {row.get("code") for row in rows}
        if codes - allowed_codes:
            raise SpriteOutlinePipelineError("source Sprite has unsupported gaps beyond its Material profile: " + sid)
        if component.get("convertible") is True:
            raise SpriteOutlinePipelineError("source Sprite is already convertible; refusing to overwrite its native mapping: " + sid)
        if codes != allowed_codes:
            raise SpriteOutlinePipelineError("Sprite is not blocked only by the recognized custom-material gap: " + sid)
        missing.append(component)
    if len(missing) != len(spec["spriteBindings"]):
        raise SpriteOutlinePipelineError("outline Sprite occurrence set differs")

    from copy import deepcopy
    updated = deepcopy(source)
    updated_components = {row["sourceId"]: row for row in updated["components"]}
    for binding in spec["spriteBindings"]:
        component = updated_components[binding["sourceId"]]
        component["convertible"] = True
        component["nativeSpriteOutlineMaterialSourceId"] = spec["materialSourceId"]
    updated["diagnostics"] = [row for row in updated["diagnostics"]
                              if not (isinstance(row, dict) and row.get("sourceId") in bound_ids and
                                      row.get("code") in allowed_codes)]
    updated["spriteOutlineBinding"] = spec
    updated["spriteOutlineBindingSource"] = {"bindingPlanSha256": expected_outline_plan_sha256,
                                              "sourceProfile": PROFILE,
                                              "sourceComponentIds": bound_ids,
                                              "target": target,
                                              "sourcePlanSha256": expected_plan_sha256,
                                              "ownedFiles": [{key: row[key] for key in ("targetPath", "stagePath", "sha256", "bytes", "role", "origin")}
                                                             for row in owned_payloads]}

    output = io.new_output(out, [source_path.parent, binding_path])
    from .output_limits import copy_verified
    for entry in io.stage_manifest(source_path.parent).get("files", []):
        relative = entry.get("path")
        if relative == source_path.name:
            continue
        source_file = io.inside(source_path.parent, relative)
        dest = io.inside(output, relative)
        copy_verified(source_file, dest, entry.get("sha256"), entry.get("bytes"))
    for row in owned_payloads:
        dest = io.inside(output, row["stagePath"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(row["data"])
    io.write_json(output / "plan.json", updated)
    io.write_json(output / "sprite-outline-binding-plan.json", binding_plan)
    report = {"schema": "monkey-prefab-sprite-outline-attach/1", "status": "attached-source-profile-pending-native-import",
              "sourcePlanSha256": expected_plan_sha256, "outlineBindingPlanSha256": expected_outline_plan_sha256,
              "sourceManifestSha256": spec["sourceManifestSha256"], "materialSourceId": spec["materialSourceId"],
              "spriteComponentIds": bound_ids, "spriteFrames": [row["spriteFrameSourceId"] for row in spec["spriteBindings"]],
              "convertedSpriteCount": len(bound_ids), "businessBehaviorsExecuted": False,
              "nativeCompilation": "not_run", "nativeRender": "not_run"}
    return io.finish(output, report)


def _stage_plan_path(value: str | Path) -> Path:
    path = io.safe(value)
    return path / "plan.json" if path.is_dir() else path


def emit_attached(binding_stage: str | Path, plan_root: str | Path,
                  existing_owned_output: str | Path) -> dict:
    """Copy a self-contained attached outline stage into an existing export output.

    ``plan_root`` is the exact attached target-plan stage being exported (or
    its ``plan.json`` path). Its verified plan bytes must match the plan in
    ``binding_stage``. ``existing_owned_output`` must already be the output
    directory created by target.export. This function writes only new files;
    the caller owns the final candidate manifest and report.
    """
    stage = io.safe(binding_stage)
    if not stage.is_dir():
        raise SpriteOutlinePipelineError("bindingStage must be an attached stage directory")
    attached_plan_path = stage / "plan.json"
    attached_raw = io.stage_bytes(attached_plan_path)
    attached = io.load(attached_raw, max_nodes=8_000_000, max_depth=128)
    info = attached.get("spriteOutlineBindingSource")
    spec = attached.get("spriteOutlineBinding")
    if not isinstance(info, dict) or not isinstance(spec, dict):
        raise SpriteOutlinePipelineError("attached plan has no Sprite outline profile")
    try:
        _validate_binding_spec(spec)
    except SpriteOutlineProfileError as error:
        raise SpriteOutlinePipelineError(str(error)) from error
    if info.get("sourceProfile") != PROFILE or info.get("target") != _target_name(attached.get("targetProfile")):
        raise SpriteOutlinePipelineError("attached outline target/profile identity differs")

    exported_plan = _stage_plan_path(plan_root)
    exported_raw = io.stage_bytes(exported_plan)
    if _sha(exported_raw) != _sha(attached_raw):
        raise SpriteOutlinePipelineError("plan_root does not identify the attached plan being exported")

    manifest = io.stage_manifest(stage)
    entries = {row.get("path"): row for row in manifest.get("files", []) if isinstance(row, dict)}
    owned = info.get("ownedFiles")
    if not isinstance(owned, list) or not owned:
        raise SpriteOutlinePipelineError("attached plan has no stage-owned outline copies")
    output = io.safe(existing_owned_output)
    if not output.is_dir():
        raise SpriteOutlinePipelineError("existing_owned_output must already be a directory")

    copies = []
    target_paths = set()
    for row in owned:
        if not isinstance(row, dict):
            raise SpriteOutlinePipelineError("attached owned-file record is malformed")
        target_path, stage_path = row.get("targetPath"), row.get("stagePath")
        expected_sha, expected_bytes = row.get("sha256"), row.get("bytes")
        if (not isinstance(target_path, str) or not isinstance(stage_path, str) or
                ".." in Path(target_path).parts or ".." in Path(stage_path).parts or
                Path(target_path).is_absolute() or Path(stage_path).is_absolute() or
                not isinstance(expected_sha, str) or len(expected_sha) != 64 or
                type(expected_bytes) is not int or expected_bytes < 0):
            raise SpriteOutlinePipelineError("attached owned-file pin is malformed")
        if target_path in target_paths:
            raise SpriteOutlinePipelineError("duplicate attached target path: " + target_path)
        target_paths.add(target_path)
        entry = entries.get(stage_path)
        if not entry or entry.get("sha256") != expected_sha or entry.get("bytes") != expected_bytes:
            raise SpriteOutlinePipelineError("attached stage manifest does not pin owned file: " + stage_path)
        source = io.inside(stage, stage_path)
        raw = io.read(source)
        if len(raw) != expected_bytes or _sha(raw) != expected_sha:
            raise SpriteOutlinePipelineError("attached outline payload changed: " + stage_path)
        destination = io.inside(output, target_path)
        if destination.exists():
            raise SpriteOutlinePipelineError("refusing to overwrite existing candidate file: " + target_path)
        copies.append((source, destination, target_path, expected_sha, expected_bytes))

    # All identities and collisions are checked before the first candidate write.
    from .output_limits import copy_verified
    written = []
    for source, destination, target_path, expected_sha, expected_bytes in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy_verified(source, destination, expected_sha, expected_bytes, atomic=False)
        written.append({"path": target_path, "sha256": expected_sha, "bytes": expected_bytes})
    return {"schema": "monkey-prefab-sprite-outline-export-emission/1",
            "status": "emitted-to-owned-candidate-pending-finish", "target": info["target"],
            "bindingPlanSha256": info.get("bindingPlanSha256"),
            "attachedPlanSha256": _sha(attached_raw), "files": written,
            "candidateManifestUpdated": False, "candidateReportUpdated": False,
            "nativeCompilation": "not_run", "nativeMaterialReadback": "not_run", "renderValidation": "not_run"}


def emit(outline_plan_path: str | Path, expected_outline_plan_sha256: str,
         plan_root: str | Path, target: str, out: str | Path) -> dict:
    """Emit shader/effect payload, helper source and deterministic helper metas.

    This is a candidate overlay, not a project import. Merge it into a fresh
    Unity or Creator candidate stage before its native Editor pass.
    """
    if target not in ("unity", "creator"):
        raise SpriteOutlinePipelineError("target must be 'unity' or 'creator'")
    binding_path = io.safe(outline_plan_path)
    plan, raw = _binding_plan(binding_path, expected_outline_plan_sha256)
    spec = plan["spec"]
    repo_root = io.safe(plan_root)
    output = io.new_output(out, [binding_path])
    emitted = []
    claimed = set()

    def stage_bytes_for(row):
        path, source_path = row.get("path"), row.get("sourcePath")
        if source_path:
            data = io.read(io.inside(repo_root, source_path))
        else:
            try:
                data = base64.b64decode(row.get("contentBase64", ""), validate=True)
            except (ValueError, TypeError) as error:
                raise SpriteOutlinePipelineError("owned inline payload is invalid") from error
        if len(data) != row.get("byteLength") or _sha(data) != row.get("sha256"):
            raise SpriteOutlinePipelineError("owned target payload changed: " + str(path))
        return path, data

    # Shader/effect/asset metadata from the profile plan are source-hash-pinned.
    prefixes = ("Assets/",) if target == "unity" else ("assets/",)
    for row in plan.get("ownedFiles", []):
        relative, data = stage_bytes_for(row)
        if not isinstance(relative, str) or not relative.startswith(prefixes) or ".." in Path(relative).parts:
            continue
        if relative in claimed:
            raise SpriteOutlinePipelineError("duplicate emitted target path: " + relative)
        claimed.add(relative)
        dest = io.inside(output, relative)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        emitted.append({"path": relative, "sha256": _sha(data), "bytes": len(data), "role": "shader-effect-payload"})

    helper_root = Path(__file__).parents[2] / "src/monkey/targets/materials/sprite_outline"
    if target == "unity":
        helpers = [
            ("UnitySpriteOutlineMaterialBindings.cs", "Assets/Game/Editor/Conversion/SpriteOutline/UnitySpriteOutlineMaterialBindings.cs"),
            ("UnitySpriteOutlineImporter.cs", "Assets/Game/Editor/Conversion/SpriteOutline/UnitySpriteOutlineImporter.cs"),
        ]
        for source_name, relative in helpers:
            data = io.read(helper_root / source_name)
            if relative in claimed: raise SpriteOutlinePipelineError("duplicate Unity helper target path")
            claimed.add(relative)
            guid = uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{PROFILE}:{source_name}").hex
            meta = (f"fileFormatVersion: 2\nguid: {guid}\nMonoImporter:\n  externalObjects: {{}}\n"
                    "  serializedVersion: 2\n  defaultReferences: []\n  executionOrder: 0\n  icon: {instanceID: 0}\n"
                    "  userData: \n  assetBundleName: \n  assetBundleVariant: \n").encode("utf-8")
            for suffix, payload, role in (("", data, "editor-helper"), (".meta", meta, "editor-helper-meta")):
                dest_path = relative + suffix
                dest = io.inside(output, dest_path); dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(payload)
                emitted.append({"path": dest_path, "sha256": _sha(payload), "bytes": len(payload), "role": role})
    else:
        helpers = [
            ("CreatorSpriteOutlineMaterialBindings.js", "extensions/monkey-import/sprite-outline-material-bindings.js"),
            ("CreatorSpriteOutlineImporter.js", "extensions/monkey-import/sprite-outline-importer.js"),
        ]
        for source_name, relative in helpers:
            data = io.read(helper_root / source_name)
            if relative in claimed: raise SpriteOutlinePipelineError("duplicate Creator helper target path")
            claimed.add(relative)
            dest = io.inside(output, relative); dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
            emitted.append({"path": relative, "sha256": _sha(data), "bytes": len(data), "role": "editor-helper"})

    hook = {"target": target, "planField": "spriteOutlineBinding", "profile": PROFILE,
            "sourceComponentIds": spec["sourceComponentIds"],
            "resolveReference": "MonkeyImporter.ResolveSpriteOutlineReference" if target == "unity" else "CreatorSpriteOutlineImporter.resolveReference",
            "prepare": "MonkeyImporter.PrepareSpriteOutline(spec, components, nodes, spriteFrames)" if target == "unity" else "CreatorSpriteOutlineImporter.createMaterial + bind",
            "readSaved": "MonkeyImporter.ReadSavedSpriteOutline(nodes, prefabId)" if target == "unity" else "CreatorSpriteOutlineImporter.readSaved(spec, components, nodes, material, effectAsset, spriteFrames, prefabId)"}
    io.write_json(output / "sprite-outline-hook.json", hook)
    report = {"schema": "monkey-prefab-sprite-outline-emit/1", "status": "overlay-emitted-native-editor-pending",
              "target": target, "bindingPlanSha256": expected_outline_plan_sha256,
              "materialSourceId": spec["materialSourceId"], "profile": PROFILE,
              "files": emitted, "hook": hook, "nativeAssetCreation": "pending-editor",
              "shaderCompilation": "not_run", "renderValidation": "not_run"}
    return io.finish(output, report)
