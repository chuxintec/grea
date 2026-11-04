"""Source-profiled 2D Sprite outline material bridge.

The source Effect is selected by all four canonical GLSL stage hashes and its
uniform/property contract, never by an Effect or Material UUID. The emitted
Unity/Creator shaders are native implementations of that bounded alpha-ring
algorithm; source GLSL is retained only as pinned evidence.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import uuid
from pathlib import Path
from typing import Any

from . import prefab_materials as common


PROFILE = "cocos24-sprite-alpha-outline-v1"
PROGRAM_NAME = "shader-2d-outline|vs|fs"
STAGE_HASHES = {
    "glsl1.vert": "8a3069c7a58d18842b3d76e3d1dd0111513f20ed6f4f922df67833c8a3ac6964",
    "glsl1.frag": "1c525aef1d89dd6fed42e7eaddb61af0bdf43474cbeae10b010057731312828e",
    "glsl3.vert": "12ab2e922ad1bb81a61bf1f1aff9ddc57fe8878e52da9acaa39eba8d487afd25",
    "glsl3.frag": "74f99c51a0551f37fb424a0992e4aaca2df453f8ad8352983aeb6d6dffbdcc22",
}
PROGRAM_HASH = "53fbec41d8b524d31908b3b27f1b6cccbd2fcd1eb0be9ace5917be386dad4784"
_EFFECT_PROPERTIES = {"outlineColor", "outlineTextureSize", "outlineWidth", "fillAlpha", "alphaThreshold", "texture"}
_MATERIAL_PROPERTIES = {"outlineColor", "outlineTextureSize", "outlineWidth"}
_TARGET = Path(__file__).parent / "targets" / "materials" / "sprite_outline"
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


class SpriteOutlineProfileError(ValueError):
    """Source material, shader profile or target binding is outside this module."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_sha(value: Any) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8"))


def _stage_hashes(effect: dict) -> dict[str, str]:
    shaders = effect.get("shaders")
    if (not isinstance(shaders, list) or len(shaders) != 1 or not isinstance(shaders[0], dict)
            or shaders[0].get("name") != PROGRAM_NAME):
        raise SpriteOutlineProfileError("Effect program set differs from the 2D Sprite outline profile")
    row = shaders[0]
    result = {}
    for language in ("glsl1", "glsl3"):
        stages = row.get(language)
        if not isinstance(stages, dict):
            raise SpriteOutlineProfileError("Effect lacks a complete GLSL language stage set")
        for stage in ("vert", "frag"):
            text = stages.get(stage)
            if not isinstance(text, str) or not text.strip():
                raise SpriteOutlineProfileError("Effect lacks a non-empty vertex/fragment stage")
            result[f"{language}.{stage}"] = common._canonical_stage_sha(text)
    return result


def _exact_effect_profile(effect: dict) -> bool:
    if not isinstance(effect, dict) or effect.get("__type__") != "cc.EffectAsset":
        return False
    try:
        stages = _stage_hashes(effect)
    except SpriteOutlineProfileError:
        return False
    if stages != STAGE_HASHES or _canonical_sha(stages) != PROGRAM_HASH:
        return False
    techniques = effect.get("techniques")
    if not isinstance(techniques, list) or len(techniques) != 1 or not isinstance(techniques[0], dict):
        return False
    passes = techniques[0].get("passes")
    if not isinstance(passes, list) or len(passes) != 1 or not isinstance(passes[0], dict):
        return False
    shader_pass = passes[0]
    if shader_pass.get("program") != PROGRAM_NAME:
        return False
    properties = shader_pass.get("properties")
    if not isinstance(properties, dict) or set(properties) != _EFFECT_PROPERTIES:
        return False
    required = {
        "outlineColor": (16, [1, 1, 1, 1]),
        "outlineTextureSize": (14, [256, 256]),
        "outlineWidth": (13, [3]),
        "fillAlpha": (13, [0]),
        "alphaThreshold": (13, [0.01]),
        "texture": (29, "white"),
    }
    for key, (kind, default) in required.items():
        value = properties.get(key)
        if not isinstance(value, dict) or value.get("type") != kind or value.get("value") != default:
            return False
    return True


def _effect_assets(assets: dict[str, dict]) -> list[dict]:
    return [asset for asset in assets.values() if asset.get("kind") == "cc.EffectAsset"
            and _exact_effect_profile(common._root_object(asset))]


def _decode_float(value: Any, label: str) -> float:
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SpriteOutlineProfileError(f"{label} must be a finite source scalar")
    return float(value)


def _decode_source_color(value: Any) -> list[float]:
    """Decode Cocos 2.4 Color._val (AABBGGRR), not a CSS/RGBA hex literal."""
    if not isinstance(value, dict) or value.get("__value_type__") != 4:
        raise SpriteOutlineProfileError("outlineColor is not a serialized Cocos Color")
    values = value.get("values")
    if not isinstance(values, list) or len(values) != 1 or type(values[0]) is not int or not 0 <= values[0] <= 0xFFFFFFFF:
        raise SpriteOutlineProfileError("outlineColor packed uint is malformed")
    packed = values[0]
    # Cocos Creator 2.4.15 Color constructor/getters use r in bits 0..7,
    # g in 8..15, b in 16..23 and a in 24..31.
    channels = [(packed >> shift) & 255 for shift in (0, 8, 16, 24)]
    return [channel / 255.0 for channel in channels]


def _source_properties(effect: dict, material: dict) -> tuple[dict, dict]:
    if not _exact_effect_profile(effect):
        raise SpriteOutlineProfileError("Effect is outside the exact alpha-ring source profile")
    if material.get("__type__") != "cc.Material":
        raise SpriteOutlineProfileError("selected source asset is not a Cocos Material")
    effect_ref = (material.get("_effectAsset") or {}).get("__uuid__")
    if not isinstance(effect_ref, str) or not effect_ref:
        raise SpriteOutlineProfileError("Material has no explicit Effect edge")
    technique_data = material.get("_techniqueData")
    zero = technique_data.get("0") if isinstance(technique_data, dict) else None
    if not isinstance(zero, dict):
        raise SpriteOutlineProfileError("Material has no technique 0 payload")
    defines, source_props = zero.get("defines"), zero.get("props")
    if defines != {"USE_TEXTURE": True}:
        raise SpriteOutlineProfileError("Material does not prove the exact textured Sprite variant")
    if not isinstance(source_props, dict) or not set(source_props).issubset(_MATERIAL_PROPERTIES):
        raise SpriteOutlineProfileError("Material has properties outside the source outline contract")
    if not _MATERIAL_PROPERTIES.issubset(source_props):
        raise SpriteOutlineProfileError("Material is missing a required source outline property")
    color = _decode_source_color(source_props["outlineColor"])
    texture_size = source_props["outlineTextureSize"]
    if not isinstance(texture_size, dict) or texture_size.get("__value_type__") != 0:
        raise SpriteOutlineProfileError("outlineTextureSize is not a serialized Cocos vec2")
    vector = texture_size.get("values")
    if (not isinstance(vector, list) or len(vector) != 2 or
            any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in vector)):
        raise SpriteOutlineProfileError("outlineTextureSize must contain two positive finite values")
    width = _decode_float(source_props["outlineWidth"], "outlineWidth")
    if not 0.0 <= width <= 8.0:
        raise SpriteOutlineProfileError("outlineWidth is outside the shader's proven 0..8 ring limit")
    effect_props = effect["techniques"][0]["passes"][0]["properties"]
    fill_alpha = _decode_float(source_props.get("fillAlpha", effect_props["fillAlpha"]["value"]), "fillAlpha")
    alpha_threshold = _decode_float(source_props.get("alphaThreshold", effect_props["alphaThreshold"]["value"]), "alphaThreshold")
    if not 0.0 <= fill_alpha <= 1.0 or not 0.0 <= alpha_threshold < 1.0:
        raise SpriteOutlineProfileError("fillAlpha/alphaThreshold are outside the source shader's supported range")
    if any(not 0.0 <= channel <= 1.0 for channel in color):
        raise SpriteOutlineProfileError("outlineColor channels must be normalized to 0..1")
    properties = {"outlineColor": color, "outlineTextureSize": [float(v) for v in vector],
                  "outlineWidth": width, "fillAlpha": fill_alpha, "alphaThreshold": alpha_threshold}
    return properties, {"defines": defines, "props": source_props}


def inspect_sprite_outline(source_manifest: str | Path, normalized_ir: str | Path | None = None) -> dict:
    """Resolve the exact source Sprite → Material → Effect shader structure."""
    manifest_path = Path(source_manifest).resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SpriteOutlineProfileError(f"unable to read source manifest: {error}") from error
    assets = common._asset_map(manifest)
    effects = _effect_assets(assets)
    if len(effects) != 1:
        raise SpriteOutlineProfileError(f"expected exactly one source Effect matching all shader-stage/property hashes; found {len(effects)}")
    effect_asset = effects[0]
    effect = common._root_object(effect_asset)
    effect_uuid = effect_asset["sourceId"].split(":", 1)[1]

    linked_materials = []
    for asset in common._selected_material_assets(manifest, assets):
        material = common._root_object(asset)
        if (material.get("_effectAsset") or {}).get("__uuid__") != effect_uuid:
            continue
        properties, source_values = _source_properties(effect, material)
        occurrences = common._prefab_material_occurrences(manifest, asset["sourceId"].split(":", 1)[1])
        linked_materials.append((asset, material, properties, source_values, occurrences))
    if len(linked_materials) != 1:
        raise SpriteOutlineProfileError(f"expected exactly one selected Material on the exact outline Effect; found {len(linked_materials)}")
    material_asset, material, properties, source_values, occurrences = linked_materials[0]
    frame_assets = []
    texture_assets = []
    seen_frames, seen_textures = set(), set()
    for occurrence in occurrences:
        frame_uuid = occurrence.get("spriteFrameUuid")
        if not frame_uuid:
            raise SpriteOutlineProfileError("material-bound Sprite has no SpriteFrame identity")
        frame_asset = common._find_asset_by_uuid(assets, frame_uuid, "cc.SpriteFrame")
        if frame_asset["sourceId"] not in seen_frames:
            seen_frames.add(frame_asset["sourceId"]); frame_assets.append(frame_asset)
        for instance in frame_asset.get("document", {}).get("instances", []):
            texture_uuid = (instance.get("_textureSetter") or {}).get("__uuid__")
            if not texture_uuid:
                raise SpriteOutlineProfileError("bound SpriteFrame has no Texture2D edge")
            texture_asset = common._find_asset_by_uuid(assets, texture_uuid, "cc.Texture2D")
            if texture_asset["sourceId"] not in seen_textures:
                seen_textures.add(texture_asset["sourceId"]); texture_assets.append(texture_asset)
    evidence = common._raw_source_evidence(manifest, effect_asset, material_asset, *frame_assets, *texture_assets)

    ir_path = Path(normalized_ir).resolve() if normalized_ir else manifest_path.parent.parent / "normalize" / "ir.json"
    ir_result = None
    if ir_path.is_file():
        try:
            ir_raw = ir_path.read_bytes(); ir = json.loads(ir_raw)
        except (OSError, json.JSONDecodeError) as error:
            raise SpriteOutlineProfileError(f"unable to read normalized IR: {error}") from error
        if ir.get("sourceManifestSha256") != _sha(manifest_path.read_bytes()):
            raise SpriteOutlineProfileError("normalized IR is not pinned to the supplied source manifest")
        source_ids = sorted(row["componentSourceId"] for row in occurrences)
        ir_rows = sorted(component.get("sourceId") for component in ir.get("components", [])
                         if isinstance(component, dict) and component.get("type") == "cc.Sprite"
                         and material_asset["sourceId"] in component.get("materials", []))
        ir_result = {"path": str(ir_path), "sha256": _sha(ir_raw), "sourceComponentIds": source_ids,
                     "irComponentIds": ir_rows, "exactMatch": source_ids == ir_rows,
                     "missingInIR": sorted(set(source_ids) - set(ir_rows)),
                     "extraInIR": sorted(set(ir_rows) - set(source_ids))}
    return {"profile": PROFILE, "programCanonicalSha256": PROGRAM_HASH, "programStageCanonicalSha256": STAGE_HASHES,
            "source": {"sourceManifestSha256": _sha(manifest_path.read_bytes()),
                       "sourceManifestPath": str(manifest_path), "sourceEvidence": evidence,
                       "colorPackingEvidence": {"engine": "Cocos Creator 2.4.15",
                                                "sourceUrl": "https://raw.githubusercontent.com/cocos-creator/engine/v2.4.15/cocos2d/core/value-types/color.ts",
                                                "sourceRanges": {"constructorPack": [369, 378], "getRed": [494, 502],
                                                                 "getGreen": [519, 526], "getBlue": [543, 550],
                                                                 "getAlpha": [567, 574]},
                                                "packedLayout": "AABBGGRR; red is low byte; green >>8; blue >>16; alpha >>24",
                                                "sourcePackedValue": source_values["props"]["outlineColor"]["values"][0]},
                       "effectSourceId": effect_asset["sourceId"], "materialSourceId": material_asset["sourceId"],
                       "effectDocumentSha256": common._canonical_sha(effect_asset.get("document")),
                       "materialDocumentSha256": common._canonical_sha(material_asset.get("document")),
                       "prefabOccurrences": occurrences, "normalizedIR": ir_result,
                       "spriteFrames": [{"sourceId": asset["sourceId"],
                                         "sourceUuid": asset["sourceId"].split(":", 1)[1],
                                         "logicalPath": asset.get("logicalPath")}
                                        for asset in frame_assets],
                       "textures": [{"sourceId": asset["sourceId"], "logicalPath": asset.get("logicalPath")}
                                    for asset in texture_assets]},
            "sourceProperties": source_values, "properties": properties}


def _owned_file(target: str, source: str | None = None, content: bytes | None = None) -> dict:
    if (source is None) == (content is None):
        raise SpriteOutlineProfileError("owned file must have exactly one immutable source")
    raw = content if content is not None else common.read(Path(__file__).parents[2] / source)
    return {"path": target, "sourcePath": source, "sha256": _sha(raw), "byteLength": len(raw),
            **({"contentBase64": base64.b64encode(raw).decode("ascii")} if content is not None else {})}


def _validate_binding_spec(spec: dict) -> None:
    if not isinstance(spec, dict) or spec.get("schema") != "monkey-prefab-sprite-outline-binding/1" or spec.get("profile") != PROFILE:
        raise SpriteOutlineProfileError("unsupported outline binding profile")
    if spec.get("programCanonicalSha256") != PROGRAM_HASH or spec.get("programStageCanonicalSha256") != STAGE_HASHES:
        raise SpriteOutlineProfileError("outline binding shader profile hashes differ")
    if not isinstance(spec.get("materialSourceId"), str) or not spec["materialSourceId"]:
        raise SpriteOutlineProfileError("source material identity is missing")
    if not _NAME.fullmatch(spec.get("module", "")):
        raise SpriteOutlineProfileError("module must be one safe path segment")
    properties = spec.get("properties")
    if not isinstance(properties, dict) or set(properties) != {"outlineColor", "outlineTextureSize", "outlineWidth", "fillAlpha", "alphaThreshold"}:
        raise SpriteOutlineProfileError("outline property structure differs")
    color = properties["outlineColor"]
    size = properties["outlineTextureSize"]
    if not isinstance(color, list) or len(color) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in color):
        raise SpriteOutlineProfileError("outlineColor is not a normalized RGBA vector")
    if not isinstance(size, list) or len(size) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in size):
        raise SpriteOutlineProfileError("outlineTextureSize is not a positive vec2")
    width, fill, threshold = properties["outlineWidth"], properties["fillAlpha"], properties["alphaThreshold"]
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (width, fill, threshold)) or not 0 <= width <= 8 or not 0 <= fill <= 1 or not 0 <= threshold < 1:
        raise SpriteOutlineProfileError("outline scalar is outside the supported source profile")
    rows = spec.get("spriteBindings")
    ids = spec.get("sourceComponentIds")
    if not isinstance(rows, list) or not rows or not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
        raise SpriteOutlineProfileError("outline Sprite source bindings are empty or malformed")
    if [row.get("sourceId") for row in rows if isinstance(row, dict)] != ids or any(not row.get("spriteFrameSourceId") for row in rows):
        raise SpriteOutlineProfileError("outline Sprite/source frame identity lists differ")
    targets = spec.get("unity"), spec.get("creator")
    for target in targets:
        if not isinstance(target, dict):
            raise SpriteOutlineProfileError("native target binding identities are missing")
    if not re.fullmatch(r"[0-9a-f]{32}", spec["unity"].get("shaderGuid", "")) or not re.fullmatch(r"[0-9a-f]{32}", spec["unity"].get("materialGuid", "")):
        raise SpriteOutlineProfileError("Unity native GUID is invalid")
    if not re.fullmatch(r"[0-9a-f-]{36}", spec["creator"].get("effectUuid", "")) or not re.fullmatch(r"[0-9a-f-]{36}", spec["creator"].get("materialUuid", "")):
        raise SpriteOutlineProfileError("Creator native UUID is invalid")


def plan_sprite_outline(source_manifest: str | Path, normalized_ir: str | Path, module: str,
                        source_manifest_sha256: str, normalized_ir_sha256: str) -> dict:
    """Produce source-pinned two-target shader/material intent and owned shader files."""
    if not _NAME.fullmatch(module or "") or ".." in Path(module).parts:
        raise SpriteOutlineProfileError("module must be one safe path segment")
    manifest_path, ir_path = Path(source_manifest).resolve(), Path(normalized_ir).resolve()
    manifest_raw, ir_raw = manifest_path.read_bytes(), ir_path.read_bytes()
    if _sha(manifest_raw) != source_manifest_sha256 or _sha(ir_raw) != normalized_ir_sha256:
        raise SpriteOutlineProfileError("explicit source manifest/IR SHA pin mismatch")
    ir = json.loads(ir_raw)
    if ir.get("sourceManifestSha256") != source_manifest_sha256:
        raise SpriteOutlineProfileError("normalized IR source manifest pin differs")
    source = inspect_sprite_outline(manifest_path, ir_path)
    if not source["source"]["normalizedIR"] or source["source"]["normalizedIR"]["sha256"] != normalized_ir_sha256 or not source["source"]["normalizedIR"]["exactMatch"]:
        raise SpriteOutlineProfileError("source material Sprite references do not match the pinned normalized IR exactly")
    props = source["properties"]
    props_hash = _canonical_sha(props)
    identity_seed = f"{PROFILE}:{PROGRAM_HASH}:{props_hash}:{module}"
    unity_shader_guid = uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{identity_seed}:unity-shader").hex
    unity_material_guid = uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{identity_seed}:unity-material").hex
    creator_effect_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{identity_seed}:creator-effect"))
    creator_material_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{identity_seed}:creator-material"))
    unity_shader_path = f"Assets/Game/Content/Shaders/{module}/Shader2DOutline.shader"
    unity_material_path = f"Assets/Game/Content/Materials/{module}/Shader2DOutline.mat"
    creator_effect_path = f"assets/resources/Shaders/{module}/Shader2DOutline.effect"
    creator_material_path = f"assets/resources/Materials/{module}/Shader2DOutline.mtl"
    unity_shader_meta = (f"fileFormatVersion: 2\nguid: {unity_shader_guid}\nShaderImporter:\n"
                         "  externalObjects: {}\n  defaultTextures: []\n  nonModifiableTextures: []\n"
                         "  preprocessorOverride: 0\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n").encode()
    unity_material_meta = (f"fileFormatVersion: 2\nguid: {unity_material_guid}\nNativeFormatImporter:\n"
                           "  externalObjects: {}\n  mainObjectFileID: 2100000\n  userData: \n"
                           "  assetBundleName: \n  assetBundleVariant: \n").encode()
    creator_effect_meta = json.dumps({"ver": "1.0.5", "uuid": creator_effect_uuid, "importer": "effect",
                                      "imported": False, "files": [], "subMetas": {}, "userData": {}},
                                     indent=2, sort_keys=True).encode() + b"\n"
    creator_material_meta = json.dumps({"ver": "1.0.5", "uuid": creator_material_uuid, "importer": "material",
                                        "imported": False, "files": [], "subMetas": {}, "userData": {}},
                                       indent=2, sort_keys=True).encode() + b"\n"
    helper_root = Path(__file__).parents[2] / "src/monkey/targets/materials/sprite_outline"
    spec = {"schema": "monkey-prefab-sprite-outline-binding/1", "profile": PROFILE,
            "programCanonicalSha256": PROGRAM_HASH, "programStageCanonicalSha256": STAGE_HASHES,
            "module": module, "materialSourceId": source["source"]["materialSourceId"],
            "effectSourceId": source["source"]["effectSourceId"],
            "sourceManifestSha256": source_manifest_sha256, "normalizedIrSha256": normalized_ir_sha256,
            "properties": props, "sourceComponentIds": [row["componentSourceId"] for row in source["source"]["prefabOccurrences"]],
            "spriteBindings": [{"sourceId": row["componentSourceId"],
                                "spriteFrameSourceId": next(frame["sourceId"] for frame in source["source"]["spriteFrames"]
                                                              if frame["sourceUuid"] == row["spriteFrameUuid"])}
                               for row in source["source"]["prefabOccurrences"]],
            "sourceBindings": source["source"]["prefabOccurrences"],
            "unity": {"shaderPath": unity_shader_path, "shaderGuid": unity_shader_guid,
                      "materialPath": unity_material_path, "materialGuid": unity_material_guid},
            "creator": {"effectPath": creator_effect_path, "effectUuid": creator_effect_uuid,
                        "materialPath": creator_material_path, "materialUuid": creator_material_uuid,
                        "materialMetaPath": creator_material_path + ".meta"},
            "nativeBindingHelpers": {
                "unity": {"sourcePath": "src/monkey/targets/materials/sprite_outline/UnitySpriteOutlineMaterialBindings.cs",
                          "sha256": _sha((helper_root / "UnitySpriteOutlineMaterialBindings.cs").read_bytes())},
                "creator38": {"sourcePath": "src/monkey/targets/materials/sprite_outline/CreatorSpriteOutlineMaterialBindings.js",
                              "sha256": _sha((helper_root / "CreatorSpriteOutlineMaterialBindings.js").read_bytes())}},
            "readbackContract": {"unity": "AssetDatabase shader/material GUID + exact properties + Image/SpriteRenderer sprite identity and material binding",
                                 "creator38": "EffectAsset/Material UUID + exact properties + cc.Sprite SpriteFrame identity and customMaterial binding"},
            "nativeCompilation": "not_run", "creatorEditorImport": "not_run", "renderValidation": "not_run"}
    _validate_binding_spec(spec)
    owned = [
        _owned_file(unity_shader_path, "src/monkey/targets/materials/sprite_outline/Shader2DOutline.shader"),
        _owned_file(unity_shader_path + ".meta", content=unity_shader_meta),
        _owned_file(unity_material_path + ".meta", content=unity_material_meta),
        _owned_file(creator_effect_path, "src/monkey/targets/materials/sprite_outline/Shader2DOutline.effect"),
        _owned_file(creator_effect_path + ".meta", content=creator_effect_meta),
        _owned_file(creator_material_path + ".meta", content=creator_material_meta),
    ]
    return {"schema": "monkey-prefab-sprite-outline-plan/1", "spec": spec, "ownedFiles": owned,
            "source": source["source"]}


def emit_sprite_outline(plan: dict, plan_root: str | Path, output_root: str | Path) -> dict:
    """Emit only pinned shader/effect/metadata files to an empty target candidate."""
    if not isinstance(plan, dict) or plan.get("schema") != "monkey-prefab-sprite-outline-plan/1":
        raise SpriteOutlineProfileError("unsupported Sprite outline plan schema")
    spec = plan.get("spec")
    _validate_binding_spec(spec)
    root = Path(output_root).resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty material candidate: {root}")
    root.mkdir(parents=True, exist_ok=True)
    files = []
    for row in plan.get("ownedFiles", []):
        target, source = row.get("path"), row.get("sourcePath")
        if not isinstance(target, str) or not target.startswith(("Assets/", "assets/")) or ".." in Path(target).parts:
            raise SpriteOutlineProfileError("unsafe owned target path")
        if source:
            raw = common.read(common.inside(Path(plan_root).resolve(), source))
        else:
            try:
                raw = base64.b64decode(row["contentBase64"], validate=True)
            except (KeyError, ValueError) as error:
                raise SpriteOutlineProfileError("owned metadata content is invalid") from error
        if len(raw) != row.get("byteLength") or _sha(raw) != row.get("sha256"):
            raise SpriteOutlineProfileError("owned material file differs from the pinned plan: " + target)
        dest = common.inside(root, target)
        if dest.exists():
            raise FileExistsError(f"refusing to replace target asset: {target}")
        files.append((target, dest, raw))
    emitted = []
    for target, dest, raw in files:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        emitted.append({"path": target, "sha256": _sha(raw), "byteLength": len(raw)})
    return {"schema": "monkey-prefab-sprite-outline-emission/1", "status": "shader-files-emitted-native-material-pending",
            "profile": PROFILE, "materialSourceId": spec["materialSourceId"], "files": emitted,
            "nativeCompilation": "not_run", "creatorEditorImport": "not_run", "renderValidation": "not_run"}
