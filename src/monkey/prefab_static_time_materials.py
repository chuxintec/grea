"""Strict static-at-t0 profiles for two proven animated Cocos Sprite effects.

This is a finite projection, not a general Cocos effect importer. It accepts
only the exact normalized GLSL-stage fingerprints below, validates the source
Effect/Material/Sprite edges and hashes, and emits a clock-independent ordinary
Sprite shader with a pinned source-time contract of exactly zero seconds.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from pathlib import Path
from typing import Any

from . import io
from .prefab_materials import _asset_map, _canonical_sha, _find_asset_by_uuid, _root_object


SCHEMA = "monkey-prefab-static-time-materials/1"
PROFILE = "cocos24-static-t0-sprite-effects-v1"
STATIC_TIME_SECONDS = 0.0
PROGRAMS = {
    "textured-uv-flow-t0-v1": {
        "stageHashes": {
            "glsl1.vert": "e1b0eb9fba7a2161aabd3a5d226d2f31ff907601f36108bcd18f887d3e1aea8c",
            "glsl1.frag": "0ca0db6b67154371efd77cee67b3a53c811eccac6ec7629bdad68535adbcf283",
            "glsl3.vert": "feaee06573ef02d730b7a7715a7b617bbf52fcccb2a856b7164dea01006125d8",
            "glsl3.frag": "4d5131aa2cd3ed5b8d578c98a1a5db62e657349e43b5ade69536bfdc5eb17fb3",
        },
        "sourceProperties": ("speed",),
        "staticProof": "uvOffset=( -cc_time.x*speed, +cc_time.x*speed ); at sourceTimeSeconds=0 the offset is exactly (0,0)",
    },
    "textured-flash-sweep-t0-v1": {
        "stageHashes": {
            "glsl1.vert": "8a3069c7a58d18842b3d76e3d1dd0111513f20ed6f4f922df67833c8a3ac6964",
            "glsl1.frag": "b3f908711485214177e1206dc36aaa7725db8ca2d3ffdd2148ec1ea2254f70fe",
            "glsl3.vert": "12ab2e922ad1bb81a61bf1f1aff9ddc57fe8878e52da9acaa39eba8d487afd25",
            "glsl3.frag": "fe33d5fd5bc9d8e281b1f2bdee4173c900cf7235eb2d53f7e78fe622b125be91",
        },
        "sourceProperties": ("angle", "direction", "width", "flashTime", "delayTime", "loopInterval", "alphaThreshold", "flashColor"),
        "staticProof": "passtime=0 at sourceTimeSeconds=0; for delayTime>=0, passtime>delayTime is false, bright=0 and shader output equals its textured Sprite base output",
    },
}
_DEFINE_SCHEMA = [
    {"name": "USE_TEXTURE", "type": "boolean", "defines": []},
    {"name": "CC_USE_MODEL", "type": "boolean", "defines": []},
    {"name": "USE_ALPHA_TEST", "type": "boolean", "defines": []},
    {"name": "CC_USE_ALPHA_ATLAS_texture", "type": "boolean", "defines": ["USE_TEXTURE"]},
    {"name": "INPUT_IS_GAMMA", "type": "boolean", "defines": ["USE_TEXTURE"]},
    {"name": "USE_BGRA", "type": "boolean", "defines": []},
]
_EFFECT_PROPERTY_NAMES = {
    "textured-uv-flow-t0-v1": {"alphaThreshold", "speed", "texture"},
    "textured-flash-sweep-t0-v1": {"alphaThreshold", "angle", "delayTime", "direction", "flashColor",
                                    "flashTime", "loopInterval", "texture", "width"},
}
_MATERIAL_PROPERTY_NAMES = {
    "textured-uv-flow-t0-v1": {"speed"},
    "textured-flash-sweep-t0-v1": {"angle", "direction", "width", "flashTime", "delayTime", "loopInterval", "flashColor", "alphaThreshold"},
}
_TARGET_FILES = Path(__file__).parent / "targets" / "materials" / "static_time"
_SAFE_UUID = re.compile(r"^[0-9a-f-]{36}$")


class StaticTimeMaterialError(ValueError):
    """Source effect/material, target frame or static-time contract is outside the finite profile."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_stage_sha(text: str) -> str:
    return _sha(text.replace("\r\n", "\n").replace("\r", "\n").strip().encode("utf-8"))


def _canonical_json_sha(value: Any) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def _source_doc(asset: dict, label: str) -> tuple[dict, dict]:
    root = _root_object(asset)
    return asset, root


def _asset_uuid(asset: dict) -> str | None:
    source_id = asset.get("sourceId")
    if isinstance(source_id, str) and ":" in source_id:
        return source_id.split(":", 1)[1]
    key = asset.get("key")
    return key if isinstance(key, str) else None


def _find_effect_asset(assets: dict[str, dict], effect_uuid: str) -> tuple[dict, list[str]]:
    rows = [row for sid, row in assets.items() if _asset_uuid(row) == effect_uuid]
    redirects = [row for row in rows if row.get("kind") == "redirect"]
    concrete = [row for row in rows if row.get("kind") == "cc.EffectAsset"
                and isinstance(row.get("document"), dict)]
    if len(concrete) != 1:
        raise StaticTimeMaterialError(f"effect UUID must resolve to one decoded cc.EffectAsset: {effect_uuid}")
    return concrete[0], [row["sourceId"] for row in redirects]


def _stage_hashes(effect: dict) -> tuple[str, dict[str, str]]:
    shaders = effect.get("shaders")
    if not isinstance(shaders, list) or len(shaders) != 1 or not isinstance(shaders[0], dict):
        raise StaticTimeMaterialError("effect must contain exactly one source shader program")
    shader = shaders[0]
    stages = {}
    for lang in ("glsl1", "glsl3"):
        body = shader.get(lang)
        if not isinstance(body, dict):
            raise StaticTimeMaterialError("source effect lacks a complete GLSL version")
        for stage in ("vert", "frag"):
            code = body.get(stage)
            if not isinstance(code, str) or not code.strip():
                raise StaticTimeMaterialError("source effect lacks a complete vertex/fragment stage")
            stages[f"{lang}.{stage}"] = _canonical_stage_sha(code)
    for profile, row in PROGRAMS.items():
        if stages == row["stageHashes"]:
            return profile, stages
    raise StaticTimeMaterialError("source effect stage fingerprints are outside the static t0 profiles")


def _validate_effect(effect: dict) -> tuple[str, dict[str, str], dict[str, Any]]:
    if effect.get("__type__") != "cc.EffectAsset":
        raise StaticTimeMaterialError("source effect document is not a cc.EffectAsset")
    profile, stages = _stage_hashes(effect)
    shader = effect["shaders"][0]
    if shader.get("defines") != _DEFINE_SCHEMA:
        raise StaticTimeMaterialError("source effect define schema differs from the pinned program")
    techniques = effect.get("techniques")
    if not isinstance(techniques, list) or len(techniques) != 1:
        raise StaticTimeMaterialError("source effect must have exactly one technique")
    passes = techniques[0].get("passes") if isinstance(techniques[0], dict) else None
    if not isinstance(passes, list) or len(passes) != 1 or not isinstance(passes[0], dict):
        raise StaticTimeMaterialError("source effect must have exactly one pass")
    render_pass = passes[0]
    if render_pass.get("program") != shader.get("name"):
        raise StaticTimeMaterialError("source effect pass/program binding differs")
    blend = render_pass.get("blendState", {})
    targets = blend.get("targets", []) if isinstance(blend, dict) else []
    if targets != [{"blend": True}]:
        raise StaticTimeMaterialError("source effect blend contract is not the verified textured-sprite blend")
    if render_pass.get("rasterizerState") != {"cullMode": 0}:
        raise StaticTimeMaterialError("source effect rasterizer contract differs")
    props = render_pass.get("properties")
    expected_names = _EFFECT_PROPERTY_NAMES[profile]
    if not isinstance(props, dict) or set(props) != expected_names:
        raise StaticTimeMaterialError("source effect property set differs from its exact fingerprint profile")
    return profile, stages, props


def _decode_number(value: Any, name: str) -> float:
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise StaticTimeMaterialError(f"{name} must be a finite source scalar")
    return float(value)


def _decode_color(value: Any, name: str) -> list[float]:
    if isinstance(value, dict) and value.get("__value_type__") == 4:
        vals = value.get("values")
        if not isinstance(vals, list) or len(vals) != 1 or type(vals[0]) is not int or not 0 <= vals[0] <= 0xFFFFFFFF:
            raise StaticTimeMaterialError(f"{name} must be one packed Cocos Color")
        packed = vals[0]
        return [((packed >> shift) & 255) / 255.0 for shift in (0, 8, 16, 24)]
    if isinstance(value, list) and len(value) == 4 and all(type(x) in (int, float) and math.isfinite(x) for x in value):
        return [float(x) for x in value]
    raise StaticTimeMaterialError(f"{name} must be a Cocos Color or four finite channels")


def _raw_sprite_records(manifest: dict, material_uuid: str) -> list[dict]:
    rows = []
    # Scan the whole frozen manifest: a selected Prefab can contain a sync
    # placeholder whose template is in the manifest's dependency closure but
    # not in the explicit selection list.
    prefabs = [asset for asset in manifest.get("assets", [])
               if isinstance(asset, dict) and asset.get("kind") == "cc.Prefab"]
    for asset in prefabs:
        instances = (asset.get("document") or {}).get("instances")
        if not isinstance(instances, list):
            continue
        sprite_rows = []
        for object_index, obj in enumerate(instances):
            if isinstance(obj, dict) and obj.get("__type__") == "cc.Sprite":
                sprite_rows.append((obj, f"{asset['sourceId']}#{object_index}"))
            if not isinstance(obj, dict) or obj.get("__type__") != "cc.Node":
                continue
            components = obj.get("_components", [])
            if not isinstance(components, list):
                raise StaticTimeMaterialError(f"node _components is malformed: {asset['sourceId']}#{object_index}")
            for ordinal, ref in enumerate(components):
                if isinstance(ref, dict) and set(ref) == {"__id__"} and type(ref.get("__id__")) is int:
                    idx = ref["__id__"]
                    component = instances[idx] if 0 <= idx < len(instances) else None
                    component_id = f"{asset['sourceId']}#{idx}"
                elif isinstance(ref, dict):
                    component = ref
                    component_id = f"{asset['sourceId']}#{object_index}/components/{ordinal}"
                else:
                    raise StaticTimeMaterialError(f"node component reference is malformed: {asset['sourceId']}#{object_index}")
                if isinstance(component, dict) and component.get("__type__") == "cc.Sprite":
                    sprite_rows.append((component, component_id))
        seen = set()
        for sprite, source_id in sprite_rows:
            if source_id in seen:
                continue
            seen.add(source_id)
            refs = sprite.get("_materials", [])
            if not isinstance(refs, list):
                raise StaticTimeMaterialError(f"Sprite materials are malformed: {source_id}")
            if not any(isinstance(ref, dict) and ref.get("__uuid__") == material_uuid for ref in refs):
                continue
            frame_ref = sprite.get("_spriteFrame")
            frame_uuid = frame_ref.get("__uuid__") if isinstance(frame_ref, dict) else None
            node_ref = sprite.get("node")
            node_index = node_ref.get("__id__") if isinstance(node_ref, dict) else None
            if type(node_index) is not int or not (0 <= node_index < len(instances)):
                raise StaticTimeMaterialError(f"Sprite node reference is invalid: {source_id}")
            rows.append({"sourceComponentId": source_id, "sourcePrefabId": asset["sourceId"],
                         "sourcePrefabPath": asset.get("logicalPath"), "sourceNodeId": f"{asset['sourceId']}#{node_index}",
                         "spriteFrameSourceId": f"gameAsset:{frame_uuid}" if frame_uuid else None,
                         "spriteFrameUuid": frame_uuid})
    if len({row["sourceComponentId"] for row in rows}) != len(rows):
        raise StaticTimeMaterialError("duplicate source Sprite material occurrence")
    return rows


def _source_property_snapshot(profile: str, material: dict, effect_props: dict) -> tuple[list[dict], dict]:
    tech_data = material.get("_techniqueData")
    zero = tech_data.get("0") if isinstance(tech_data, dict) else None
    if not isinstance(zero, dict) or set(tech_data) != {"0"}:
        raise StaticTimeMaterialError("source Material must contain exactly technique 0 data")
    defines, props = zero.get("defines"), zero.get("props")
    if defines != {"USE_TEXTURE": True}:
        raise StaticTimeMaterialError("source Material must enable only the textured Sprite define")
    if not isinstance(props, dict) or not set(props).issubset(_MATERIAL_PROPERTY_NAMES[profile]):
        raise StaticTimeMaterialError("source Material has properties outside its exact static t0 contract")
    names = PROGRAMS[profile]["sourceProperties"]
    snapshot = []
    for name in names:
        overridden = name in props
        raw_value = props[name] if overridden else effect_props[name].get("value")
        if name == "flashColor":
            value = _decode_color(raw_value, name)
            kind = "color"
        else:
            value = _decode_number(raw_value, name)
            kind = "scalar"
        snapshot.append({"name": name, "kind": kind, "value": value,
                         "source": "material-override" if overridden else "effect-default",
                         "rawValue": raw_value})
    values = {row["name"]: row["value"] for row in snapshot}
    if profile == "textured-uv-flow-t0-v1":
        if not math.isfinite(values["speed"]):
            raise StaticTimeMaterialError("UV flow speed must be finite")
    else:
        if values["delayTime"] < 0 or values["loopInterval"] <= 0 or values["flashTime"] < 0:
            raise StaticTimeMaterialError("flash sweep t0 proof requires delayTime>=0, loopInterval>0 and flashTime>=0")
    return snapshot, defines


def _file_meta(path: str, guid: str, kind: str) -> bytes:
    if kind == "shader":
        importer = "ShaderImporter:\n  externalObjects: {}\n  defaultTextures: []\n  nonModifiableTextures: []\n  preprocessorOverride: 0\n  userData:\n  assetBundleName:\n  assetBundleVariant:\n"
    elif kind == "effect":
        importer = "importer: effect\nver: 1.0.5\nimported: true\nfiles: []\nsubMetas: {}\nuserData: {}\nbundleName: ''\nbundleVariant: ''\n"
    else:
        importer = "importer: material\nver: 1.0.5\nimported: true\nfiles: []\nsubMetas: {}\nuserData: {}\nbundleName: ''\nbundleVariant: ''\n"
    return f"fileFormatVersion: 2\nguid: {guid}\n{importer}".encode("utf-8") if kind == "shader" else json.dumps({"ver": "1.0.5", "uuid": guid, "importer": kind, "imported": True, "files": [], "subMetas": {}, "userData": {}, "bundleName": "", "bundleVariant": ""}, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"


def _unity_meta(guid: str) -> bytes:
    return (f"fileFormatVersion: 2\nguid: {guid}\nShaderImporter:\n  externalObjects: {{}}\n  defaultTextures: []\n  nonModifiableTextures: []\n  preprocessorOverride: 0\n  userData:\n  assetBundleName:\n  assetBundleVariant:\n").encode("utf-8")


def _unity_material_meta(guid: str) -> bytes:
    return (f"fileFormatVersion: 2\nguid: {guid}\nNativeFormatImporter:\n  externalObjects: {{}}\n  mainObjectFileID: 2100000\n  userData:\n  assetBundleName:\n  assetBundleVariant:\n").encode("utf-8")


def _generic_properties(snapshot: list[dict]) -> dict:
    scalar = [row["value"] for row in snapshot if row["kind"] == "scalar"]
    color = next((row["value"] for row in snapshot if row["kind"] == "color"), [1.0, 1.0, 1.0, 1.0])
    if len(scalar) > 7:
        raise StaticTimeMaterialError("source property count exceeds target material contract")
    return {"sourceTimeSeconds": STATIC_TIME_SECONDS,
            **{f"sourceScalar{i}": value for i, value in enumerate(scalar)},
            "sourceColor": color}


def _target_identities(profile: str, snapshot: list[dict], source_material_id: str) -> dict:
    property_hash = _canonical_json_sha(snapshot)
    seed = f"{PROFILE}:{profile}:{source_material_id}:{property_hash}:sourceTimeSeconds=0"
    shader_guid = uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{PROFILE}:unity-shader").hex
    effect_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{PROFILE}:creator-effect"))
    material_guid = uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{seed}:unity-material").hex
    material_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{seed}:creator-material"))
    suffix = _sha(seed.encode("utf-8"))[:16]
    return {"propertySnapshotSha256": property_hash,
            "unity": {"shaderPath": "Assets/Game/Content/Shaders/StaticTime/StaticT0Sprite.shader",
                      "shaderGuid": shader_guid,
                      "materialPath": f"Assets/Game/Content/Materials/StaticTime/StaticT0Sprite-{suffix}.mat",
                      "materialGuid": material_guid},
            "creator": {"effectPath": "assets/resources/Shaders/StaticTime/StaticT0Sprite.effect",
                        "effectUuid": effect_uuid,
                        "effectMetaPath": "assets/resources/Shaders/StaticTime/StaticT0Sprite.effect.meta",
                        "materialPath": f"assets/resources/Materials/StaticTime/StaticT0Sprite-{suffix}.mtl",
                        "materialUuid": material_uuid,
                        "materialMetaPath": f"assets/resources/Materials/StaticTime/StaticT0Sprite-{suffix}.mtl.meta"}}


def inspect(source_manifest_path: str | Path, normalized_ir_path: str | Path) -> dict:
    """Inspect selected source material closures; no target files are emitted."""
    manifest_path, ir_path = io.safe(source_manifest_path), io.safe(normalized_ir_path)
    manifest_raw, ir_raw = io.read(manifest_path), io.read(ir_path)
    manifest, ir = io.load(manifest_raw, max_nodes=8_000_000), io.load(ir_raw, max_nodes=8_000_000)
    manifest_sha, ir_sha = io.sha(manifest_raw), io.sha(ir_raw)
    if ir.get("sourceManifestSha256") != manifest_sha:
        raise StaticTimeMaterialError("normalized IR source manifest SHA differs")
    assets = _asset_map(manifest)
    ir_components = {row.get("sourceId"): row for row in ir.get("components", []) if isinstance(row, dict)}
    profiles = []
    diagnostics = []
    for material_asset in (row for row in assets.values() if row.get("kind") == "cc.Material" and isinstance(row.get("document"), dict)):
        material = _root_object(material_asset)
        effect_ref = material.get("_effectAsset")
        effect_uuid = effect_ref.get("__uuid__") if isinstance(effect_ref, dict) else None
        if not isinstance(effect_uuid, str):
            continue
        try:
            effect_asset, redirect_chain = _find_effect_asset(assets, effect_uuid)
            effect = _root_object(effect_asset)
            profile, stage_hashes = _stage_hashes(effect)
        except StaticTimeMaterialError:
            continue
        # Once a source Effect matches an allowed program fingerprint, a broken
        # declaration/pass/material contract is an error, not a silent fallback.
        profile, stage_hashes, effect_props = _validate_effect(effect)
        source_material_id = material_asset["sourceId"]
        def resolves_material(identity):
            seen=set()
            while identity in assets and assets[identity].get('kind')=='redirect':
                if identity in seen:raise StaticTimeMaterialError('material redirect cycle')
                seen.add(identity);identity=assets[identity].get('redirectTarget')
            return identity==source_material_id
        source_material_references=sorted(sid for sid in assets if resolves_material(sid))
        material_uuid = _asset_uuid(material_asset)
        if not material_uuid:
            continue
        source_sprites = _raw_sprite_records(manifest, material_uuid)
        # The IR is the source-plan closure actually handed to this target
        # plan. Other prefabs can be present in a frozen manifest as unrelated
        # lookup records; they are not profile bindings for this conversion.
        selected_sprites = [row for row in source_sprites
                             if row["sourceComponentId"] in ir_components
                             and ir_components[row["sourceComponentId"]].get("materials") in [[sid]for sid in source_material_references]]
        if not selected_sprites:
            continue
        props, defines = _source_property_snapshot(profile, material, effect_props)
        if not all(row.get("spriteFrameSourceId") for row in selected_sprites):
            raise StaticTimeMaterialError(f"profile material Sprite lacks a source frame: {source_material_id}")
        for row in selected_sprites:
            frame_asset = _find_asset_by_uuid(assets, row["spriteFrameUuid"], "cc.SpriteFrame")
            # A raw Sprite stores only the UUID while the frozen manifest may
            # identify the exact dependency as remoteAsset rather than
            # gameAsset. Pin the manifest-resolved identity here.
            row["spriteFrameSourceId"] = frame_asset["sourceId"]
            component = ir_components.get(row["sourceComponentId"])
            frame_identity=component.get('spriteFrame') if isinstance(component,dict) else None
            frame_seen=set()
            while frame_identity in assets and assets[frame_identity].get('kind')=='redirect':
                if frame_identity in frame_seen:raise StaticTimeMaterialError('SpriteFrame redirect cycle')
                frame_seen.add(frame_identity);frame_identity=assets[frame_identity].get('redirectTarget')
            if not isinstance(component, dict) or component.get("type") != "cc.Sprite" or frame_identity != frame_asset["sourceId"]:
                raise StaticTimeMaterialError(f"source IR lacks an exact Sprite/frame binding: {row['sourceComponentId']}")
            if component.get("materials") not in [[sid]for sid in source_material_references]:
                raise StaticTimeMaterialError(f"source IR Sprite material binding differs: {row['sourceComponentId']}")
            row["sourceFrameDocumentSha256"] = _canonical_json_sha(frame_asset.get("document"))
        identity = _target_identities(profile, props, source_material_id)
        profiles.append({
            "profile": profile,
            "effectSourceId": effect_asset["sourceId"],
            "effectRedirectChain": redirect_chain,
            "effectStageHashes": stage_hashes,
            "effectDocumentSha256": _canonical_json_sha(effect_asset.get("document")),
            "sourceEffectDocumentSha256": _canonical_json_sha(effect_asset.get("document")),
            "sourceMaterialId": source_material_id,
            "sourceMaterialReferenceIds": source_material_references,
            "sourceMaterialUuid": material_uuid,
            "sourceMaterialDocumentSha256": _canonical_json_sha(material_asset.get("document")),
            "sourceMaterialProperties": props,
            "sourceMaterialDefines": defines,
            "sourcePropertySnapshot": props,
            "sourceSpriteBindings": selected_sprites,
            "staticTimeSeconds": STATIC_TIME_SECONDS,
            "staticTimeProof": PROGRAMS[profile]["staticProof"],
            "outputEquivalence": "ordinary-textured-sprite-at-source-time-zero-v1",
            "targetProperties": _generic_properties(props),
            **identity,
        })
    if len({row["sourceMaterialId"] for row in profiles}) != len(profiles):
        raise StaticTimeMaterialError("duplicate source Material profile")
    profiles.sort(key=lambda row: row["sourceMaterialId"])
    return {"schema": SCHEMA, "profile": PROFILE, "sourceManifestSha256": manifest_sha,
            "normalizedIrSha256": ir_sha, "sourceProfile": ir.get("sourceProfile"),
            "staticTimeSeconds": STATIC_TIME_SECONDS, "materials": profiles, "diagnostics": diagnostics}


def _validate_frame_available(plan: dict, target: str, frame_source_id: str) -> dict:
    if target == "creator":
        rows = [row for row in plan.get("assets", []) if isinstance(row, dict) and row.get("sourceId") == frame_source_id
                and row.get("kind") == "sprite"]
        if len(rows) != 1 or not rows[0].get("path") or not rows[0].get("uuid"):
            raise StaticTimeMaterialError(f"Creator SpriteFrame must be present as an exportable target sprite: {frame_source_id}")
        return rows[0]
    textures = [row for row in plan.get("textures", []) if isinstance(row, dict) and row.get("id") == frame_source_id]
    if len(textures) != 1 or not textures[0].get("path"):
        raise StaticTimeMaterialError(f"Unity SpriteFrame must be present in plan.textures: {frame_source_id}")
    guid = textures[0].get("guid")
    if guid is not None and (not isinstance(guid, str) or not re.fullmatch(r"[0-9a-f]{32}", guid)):
        raise StaticTimeMaterialError(f"Unity SpriteFrame GUID is malformed: {frame_source_id}")
    return textures[0]


def attach(plan: dict, spec: dict, target: str) -> dict:
    """Attach exact source t0 profiles and expand bindings through sync component origins."""
    if target not in ("unity", "creator"):
        raise StaticTimeMaterialError("target must be unity or creator")
    if not isinstance(plan, dict) or not isinstance(spec, dict) or spec.get("schema") != SCHEMA:
        raise StaticTimeMaterialError("invalid plan or static-time material spec")
    if plan.get("sourceManifestSha256") != spec.get("sourceManifestSha256"):
        raise StaticTimeMaterialError("target plan/source-manifest pin mismatch")
    if plan.get("sourceIrSha256") and plan.get("sourceIrSha256") != spec.get("normalizedIrSha256"):
        raise StaticTimeMaterialError("target plan/normalized-IR pin mismatch")
    components = plan.get("components")
    if not isinstance(components, list):
        raise StaticTimeMaterialError("target plan has no components")
    components_by_id = {row.get("sourceId"): row for row in components if isinstance(row, dict)}
    if len(components_by_id) != len(components):
        raise StaticTimeMaterialError("target plan has duplicate component source IDs")
    sync_origins = []
    for binding in plan.get("syncPrefabBindings", []) or []:
        for origin in (binding.get("componentOrigins", []) if isinstance(binding, dict) else []):
            if isinstance(origin, dict) and isinstance(origin.get("templateSourceId"), str) and isinstance(origin.get("instanceSourceId"), str):
                sync_origins.append(origin)
    material_rows = []
    source_to_material = {}
    for material in spec.get("materials", []):
        source_id = material.get("sourceMaterialId")
        source_bindings = material.get("sourceSpriteBindings", [])
        if not source_id or not source_bindings:
            raise StaticTimeMaterialError("profile material lacks source Sprite bindings")
        origin_to_frame = {row["sourceComponentId"]: row["spriteFrameSourceId"] for row in source_bindings}
        component_ids = set(origin_to_frame)
        origin_by_component_id = {component_id: component_id for component_id in origin_to_frame}
        for origin in sync_origins:
            if origin["templateSourceId"] in origin_to_frame:
                component_ids.add(origin["instanceSourceId"])
                origin_to_frame[origin["instanceSourceId"]] = origin_to_frame[origin["templateSourceId"]]
                origin_by_component_id[origin["instanceSourceId"]] = origin["templateSourceId"]
        rows = []
        for component_id in sorted(component_ids):
            component = components_by_id.get(component_id)
            if not isinstance(component, dict) or component.get("type") != "cc.Sprite":
                raise StaticTimeMaterialError(f"profile Sprite component is missing from the target plan: {component_id}")
            if component.get("materials") not in [[sid]for sid in material.get('sourceMaterialReferenceIds',[source_id])] or component.get("spriteFrame") != origin_to_frame[component_id]:
                raise StaticTimeMaterialError(f"plan Sprite material/frame no longer matches profile evidence: {component_id}")
            frame = _validate_frame_available(plan, target, origin_to_frame[component_id])
            if not component.get("node") or component["node"] not in {n.get("sourceId") for n in plan.get("nodes", []) if isinstance(n, dict)}:
                raise StaticTimeMaterialError(f"profile Sprite node is missing from target plan: {component_id}")
            # Reuse existing lowering values only after validating each required
            # field. This repairs nativeType/convertible without inventing a
            # frame, Sprite type, size mode, trim flag, material or source node.
            if type(component.get("mode")) is not int or component["mode"] not in (0, 1, 2):
                raise StaticTimeMaterialError(f"profile Sprite lowering mode is incomplete: {component_id}")
            if type(component.get("trim")) is not bool or type(component.get("enabled")) is not bool:
                raise StaticTimeMaterialError(f"profile Sprite trim/enabled lowering is incomplete: {component_id}")
            if target == "creator" and type(component.get("sizeMode")) is not int:
                raise StaticTimeMaterialError(f"Creator profile Sprite sizeMode is missing: {component_id}")
            component["nativeType"] = "cc.Sprite"
            component["nativeStaticTimeMaterialSourceId"] = source_id
            component["nativeStaticTimeMaterialProfile"] = material["profile"]
            component["nativeStaticTimeSourceComponentId"] = origin_by_component_id[component_id]
            component["convertible"] = True
            rows.append({"sourceId": component_id, "sourceComponentId": component["nativeStaticTimeSourceComponentId"],
                         "sourcePrefabId": next((row.get("sourcePrefabId") for row in source_bindings
                                                  if row.get("sourceComponentId") == component["nativeStaticTimeSourceComponentId"]), None),
                         "spriteFrameSourceId": origin_to_frame[component_id],
                         "spriteFrameTargetPath": frame.get("path"),
                         "ownerPrefabId": component_id.split("#", 1)[0]})
            source_to_material[component_id] = source_id
        rows.sort(key=lambda row: row["sourceId"])
        material_rows.append({**material, "target": target, "spriteBindings": rows})
    # Refuse an incomplete clone expansion: every target-plan Sprite that uses a
    # selected exact-profile Material must have one source or sync-origin proof.
    for component in components:
        if component.get("type") != "cc.Sprite":
            continue
        for source_material_id in component.get("materials", []) or []:
            if source_material_id in {row["sourceMaterialId"] for row in spec["materials"]} and component.get("sourceId") not in source_to_material:
                raise StaticTimeMaterialError(f"custom-material Sprite lacks a source or sync-component-origin proof: {component['sourceId']}")
    plan["staticTimeMaterials"] = {**spec, "target": target, "materials": material_rows}
    return plan


def prepare(source_manifest_path: str | Path, normalized_ir_path: str | Path, target: str,
            output: str | Path) -> dict:
    """Create a source-pinned t0 plan/payload bundle for Unity or Creator 3.8.8."""
    if target not in ("unity", "creator"):
        raise StaticTimeMaterialError("target must be unity or creator")
    manifest_path, ir_path = io.safe(source_manifest_path), io.safe(normalized_ir_path)
    inspected = inspect(manifest_path, ir_path)
    if not inspected["materials"]:
        return {"spec": None, "payloads": [], "diagnostics": inspected.get("diagnostics", [])}
    out = io.new_output(output, [manifest_path, ir_path])
    shader_name = "StaticT0Sprite.shader" if target == "unity" else "StaticT0Sprite.effect"
    shader_raw = io.read(_TARGET_FILES / shader_name)
    if b"cc_time" in shader_raw or b"_Time" in shader_raw:
        raise StaticTimeMaterialError("generated static t0 shader must not read an engine/global clock")
    shader_sha = io.sha(shader_raw)
    shader_guid = uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{PROFILE}:unity-shader").hex
    effect_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{PROFILE}:creator-effect"))
    spec = {key: value for key, value in inspected.items() if key != "diagnostics"}
    spec.update({"target": target,
                 "targetShaderSha256": shader_sha,
                 "targetShaderSourceTimeConstant": STATIC_TIME_SECONDS,
                 "targetShader": {"unity": {"path": "Assets/Game/Content/Shaders/StaticTime/StaticT0Sprite.shader",
                                               "guid": shader_guid},
                                  "creator": {"path": "assets/resources/Shaders/StaticTime/StaticT0Sprite.effect",
                                                "uuid": effect_uuid,
                                                "metaPath": "assets/resources/Shaders/StaticTime/StaticT0Sprite.effect.meta"}}})
    for material in spec["materials"]:
        material["targetShaderSha256"] = shader_sha
        material["targetShaderSourceTimeConstant"] = STATIC_TIME_SECONDS
        if target == "unity":
            material["targetMaterialGuid"] = material["unity"]["materialGuid"]
            material["targetShaderGuid"] = shader_guid
        else:
            material["targetMaterialUuid"] = material["creator"]["materialUuid"]
            material["targetEffectUuid"] = effect_uuid
    rel = shader_name
    staged = out / "payloads" / rel
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(shader_raw)
    payloads = [{"source": f"payloads/{rel}",
                 "target": spec["targetShader"][target]["path"], "sha256": shader_sha}]
    if target == "unity":
        meta_rel = rel + ".meta"
        meta_raw = _unity_meta(shader_guid)
        (out / "payloads" / meta_rel).write_bytes(meta_raw)
        payloads.append({"source": f"payloads/{meta_rel}", "target": spec["targetShader"][target]["path"] + ".meta",
                         "sha256": io.sha(meta_raw)})
        for index, material in enumerate(spec["materials"]):
            material_meta_rel = f"StaticT0Sprite-{index:02d}.mat.meta"
            material_meta_raw = _unity_material_meta(material["unity"]["materialGuid"])
            (out / "payloads" / material_meta_rel).write_bytes(material_meta_raw)
            payloads.append({"source": f"payloads/{material_meta_rel}",
                             "target": material["unity"]["materialPath"] + ".meta",
                             "sha256": io.sha(material_meta_raw)})
    else:
        meta_rel = rel + ".meta"
        meta_raw = _file_meta(spec["targetShader"][target]["path"], effect_uuid, "effect")
        (out / "payloads" / meta_rel).write_bytes(meta_raw)
        payloads.append({"source": f"payloads/{meta_rel}", "target": spec["targetShader"][target]["metaPath"],
                         "sha256": io.sha(meta_raw)})
    spec["payloads"] = payloads
    io.write_json(out / "static-time-materials.json", spec)
    report = io.finish(out, {"schemaVersion": 1, "profile": PROFILE, "sourceManifestSha256": spec["sourceManifestSha256"],
                             "normalizedIrSha256": spec["normalizedIrSha256"], "diagnostics": []})
    return {"spec": spec, "payloads": payloads, "output": str(out), "manifest": report}


def emit(binding: dict | None, plan_root: str | Path, output_root: str | Path) -> list[dict]:
    """Copy only hash-pinned shader/effect payloads into a target project."""
    if not binding:
        return []
    spec = binding.get("spec") if "spec" in binding else binding
    if not isinstance(spec, dict) or spec.get("schema") != SCHEMA:
        raise StaticTimeMaterialError("static time material plan is invalid")
    plan_root, output_root = io.safe(plan_root), io.safe(output_root)
    emitted = []
    for row in spec.get("payloads", []):
        raw = io.read(io.inside(plan_root, row["source"]))
        if io.sha(raw) != row.get("sha256"):
            raise StaticTimeMaterialError("plan-owned static t0 shader/effect payload hash differs")
        destination = io.inside(output_root, row["target"])
        if destination.exists():
            raise StaticTimeMaterialError(f"refusing to overwrite existing target shader/effect: {row['target']}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        emitted.append({"path": row["target"], "sha256": row["sha256"], "byteLength": len(raw), "role": "static-time-shader"})
    return emitted


def verify(spec: dict, actual: dict | None, target: str) -> list[dict]:
    """Verify native shader/material identities, frozen properties and per-Sprite bindings."""
    gaps = []
    if not spec or not isinstance(spec, dict) or spec.get("schema") != SCHEMA:
        return [io.diagnostic("STATIC_TIME_MATERIAL_READBACK_MISMATCH", "staticTimeMaterials", "Missing or invalid static-time material spec")]
    if (not isinstance(actual, dict) or actual.get("schema") != SCHEMA or actual.get("profile") != PROFILE
            or actual.get("sourceManifestSha256") != spec.get("sourceManifestSha256")
            or actual.get("normalizedIrSha256") != spec.get("normalizedIrSha256")):
        return [io.diagnostic("STATIC_TIME_MATERIAL_READBACK_MISMATCH", "staticTimeMaterials", "Saved source pins differ")]
    actual_rows = actual.get("materials")
    expected_ids = {row["sourceMaterialId"] for row in spec.get("materials", [])}
    if (not isinstance(actual_rows, list) or any(not isinstance(row, dict) for row in actual_rows) or
            len({row.get("sourceMaterialId") for row in actual_rows}) != len(actual_rows) or
            {row.get("sourceMaterialId") for row in actual_rows} != expected_ids):
        return [io.diagnostic("STATIC_TIME_MATERIAL_READBACK_MISMATCH", "staticTimeMaterials", "Saved material identity set differs")]
    rows = {row["sourceMaterialId"]: row for row in actual_rows}
    for expected in spec.get("materials", []):
        row = rows.get(expected.get("sourceMaterialId"))
        if row is None:
            gaps.append(io.diagnostic("STATIC_TIME_MATERIAL_READBACK_MISMATCH", expected.get("sourceMaterialId", "materials"), "Saved material binding is missing"))
            continue
        target_row = expected.get(target) or {}
        valid = (row.get("profile") == expected.get("profile")
                 and row.get("staticTimeSeconds") == STATIC_TIME_SECONDS
                 and row.get("sourceMaterialDocumentSha256") == expected.get("sourceMaterialDocumentSha256")
                 and row.get("sourceEffectDocumentSha256") == expected.get("sourceEffectDocumentSha256")
                 and row.get("sourcePropertiesVerified") is True
                 and row.get("shaderPayloadSha256") == expected.get("targetShaderSha256")
                 and row.get("targetPropertiesVerified") is True
                 and _native_properties_close(row.get("targetProperties"), expected.get("targetProperties"), target, expected.get("profile"))
                 and row.get("boundSpriteComponentIds") == [binding["sourceId"] for binding in expected.get("spriteBindings", [])])
        if target == "unity":
            valid = (valid and row.get("materialGuid") == target_row.get("materialGuid")
                     and row.get("shaderGuid") == target_row.get("shaderGuid")
                     and type(row.get("materialLocalFileId")) is int and row["materialLocalFileId"] != 0
                     and type(row.get("shaderLocalFileId")) is int and row["shaderLocalFileId"] != 0)
        elif target == "creator":
            valid = valid and row.get("materialUuid") == target_row.get("materialUuid") and row.get("effectUuid") == target_row.get("effectUuid")
        else:
            valid = False
        if not valid:
            gaps.append(io.diagnostic("STATIC_TIME_MATERIAL_READBACK_MISMATCH", expected.get("sourceMaterialId", "materials"), "Saved shader/material properties, t0 proof or Sprite bindings differ"))
    return gaps


def _native_properties_close(actual: Any, expected: Any, target: str, profile: str) -> bool:
    # Unity serializes all fields of its fixed MaterialProperties DTO. UV-flow
    # uses only scalar0; the six unused scalar slots must remain exactly zero.
    if target == "unity" and profile == "textured-uv-flow-t0-v1" and isinstance(actual, dict) and isinstance(expected, dict):
        extras = set(actual) - set(expected)
        padding = {f"sourceScalar{i}" for i in range(1, 7)}
        if not extras <= padding or any(type(actual[key]) not in (int, float) or actual[key] != 0 for key in extras):
            return False
        actual = {key: value for key, value in actual.items() if key not in extras}
    return _properties_close(actual, expected)


def _properties_close(actual: Any, expected: Any, tolerance: float = 1e-5) -> bool:
    """Compare saved Unity floats with a small serialization tolerance and exact shape."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(
            _properties_close(actual[key], value, tolerance) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _properties_close(left, right, tolerance) for left, right in zip(actual, expected))
    if isinstance(expected, bool):
        return actual is expected
    if isinstance(expected, (int, float)):
        return (not isinstance(actual, bool) and isinstance(actual, (int, float))
                and math.isfinite(actual) and abs(float(actual) - float(expected)) <= tolerance)
    return actual == expected
