"""Evidence-bound Cocos 2.4 UI color material bridge for v0.7 Prefabs.

Only the selected ``shader-2d-uiColor`` Sprite material is ported. The shader
programs in target files are independently authored from the observed source
semantics; original GLSL is never copied or executed.
"""

from __future__ import annotations

import hashlib
import base64
import json
import math
import re
import uuid
from pathlib import Path
from typing import Any

from .io import inside, read


PROGRAM_NAME = "shader-2d-uiColor|vs|fs"
PROFILE = "cocos24-ui-color-sprite-v1"
UI_COLOR_STAGE_HASHES = {
    "glsl1.frag": "ddb8ad32ce7d03240f93622f5301b5ff995992e2c732024f98a76ed0281aeeb7",
    "glsl1.vert": "34b99181241a8d660dabd2b1ac01865c9bb3391c1cf1da6cea5cd10331f55191",
    "glsl3.frag": "3df64f235f8264f2ad159005218ddce484efcacc3c0a22418e01c301b577ffbc",
    "glsl3.vert": "c8a3453cf601c44cd95b8265c1ed916f8c71eb40a092ff45f32f89de422ade24",
}
_SUPPORTED_PROPERTIES = ("brightness", "saturation", "constrast", "gray", "silhouette")
_TARGET_DIR = Path(__file__).parent / "targets" / "materials" / "ui_color"


class MaterialProfileError(ValueError):
    """The source material or its evidence does not match this bounded port."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_sha(value: Any) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8"))


def _canonical_stage_sha(text: str) -> str:
    canonical = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return _sha(canonical.encode("utf-8"))


def _stage_hashes(effect: dict) -> dict[str, str]:
    shaders = effect.get("shaders")
    if (not isinstance(shaders, list) or len(shaders) != 1 or not isinstance(shaders[0], dict)
            or shaders[0].get("name") != PROGRAM_NAME):
        raise MaterialProfileError("Effect program set differs from the supported uiColor profile")
    stages = shaders[0]
    result = {}
    for lang in ("glsl1", "glsl3"):
        code = stages.get(lang)
        if not isinstance(code, dict):
            raise MaterialProfileError("source Effect lacks a complete recorded language stage set")
        for stage in ("vert", "frag"):
            text = code.get(stage)
            if not isinstance(text, str) or not text.strip():
                raise MaterialProfileError("source Effect lacks complete recorded vertex/fragment text")
            result[f"{lang}.{stage}"] = _canonical_stage_sha(text)
    return result


def _program_profile_hash(stage_hashes: dict[str, str]) -> str:
    return _canonical_sha(stage_hashes)


def _exact_ui_color_profile(effect: dict) -> bool:
    if effect.get("__type__") != "cc.EffectAsset" or effect.get("_name") != "shader-2d-uiColor":
        return False
    try:
        return _stage_hashes(effect) == UI_COLOR_STAGE_HASHES
    except MaterialProfileError:
        return False


def _asset_map(manifest: dict) -> dict[str, dict]:
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        raise MaterialProfileError("source manifest has no asset list")
    rows = [asset for asset in assets if isinstance(asset, dict) and isinstance(asset.get("sourceId"), str)]
    return {asset["sourceId"]: asset for asset in rows}


def _root_object(asset: dict) -> dict:
    document = asset.get("document")
    if not isinstance(document, dict) or not isinstance(document.get("instances"), list):
        raise MaterialProfileError(f"{asset.get('sourceId')} has no decoded source document")
    instances = document["instances"]
    root = document.get("root")
    if not isinstance(root, int) or not (0 <= root < len(instances)) or not isinstance(instances[root], dict):
        raise MaterialProfileError(f"{asset.get('sourceId')} has an invalid document root")
    return instances[root]


def _find_asset_by_uuid(assets: dict[str, dict], source_uuid: str, kind: str) -> dict:
    source_id = f"gameAsset:{source_uuid}"
    asset = assets.get(source_id)
    if not asset or asset.get("kind") != kind:
        matches = [row for key, row in assets.items()
                   if key.endswith(f":{source_uuid}") and row.get("kind") == kind]
        if len(matches) == 1:
            asset = matches[0]
        else:
            raise MaterialProfileError(f"missing or ambiguous {kind} dependency with source UUID {source_uuid}")
    return asset


def _decode_color(value: Any) -> list[float]:
    if isinstance(value, dict) and value.get("__value_type__") == 4:
        values = value.get("values")
        if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], int):
            raise MaterialProfileError("unsupported serialized color representation")
        packed = values[0] & 0xFFFFFFFF
        return [((packed >> shift) & 255) / 255.0 for shift in (24, 16, 8, 0)]
    if isinstance(value, (list, tuple)) and len(value) == 4:
        result = [float(x) for x in value]
        if all(math.isfinite(x) for x in result):
            return result
    raise MaterialProfileError("silhouette must be a four-channel source color")


def _scalar(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise MaterialProfileError(f"{name} must be a finite source number")
    return float(value)


def _source_properties(effect: dict, material: dict) -> tuple[dict[str, Any], dict[str, Any]]:
    if not _exact_ui_color_profile(effect):
        raise MaterialProfileError("Effect identity is outside the supported uiColor profile")
    techniques = effect.get("techniques")
    if not isinstance(techniques, list) or len(techniques) != 1 or not isinstance(techniques[0], dict):
        raise MaterialProfileError("Effect technique set differs from the supported uiColor profile")
    passes = techniques[0].get("passes", [])
    if not isinstance(passes, list) or len(passes) != 1 or not isinstance(passes[0], dict) or passes[0].get("program") != PROGRAM_NAME:
        raise MaterialProfileError("Effect pass does not bind the identified uiColor program")
    if material.get("__type__") != "cc.Material":
        raise MaterialProfileError("bound source asset is not a Cocos Material")
    source_effect_ref = material.get("_effectAsset")
    effect_ref = source_effect_ref.get("__uuid__") if isinstance(source_effect_ref, dict) else None
    if not isinstance(effect_ref, str) or not effect_ref:
        raise MaterialProfileError("source Material does not identify an Effect UUID")
    technique_data = material.get("_techniqueData", {})
    zero = technique_data.get("0", {}) if isinstance(technique_data, dict) else {}
    defines = zero.get("defines", {}) if isinstance(zero, dict) else {}
    props = zero.get("props", {}) if isinstance(zero, dict) else {}
    if not isinstance(defines, dict) or defines.get("USE_TEXTURE") is not True:
        raise MaterialProfileError("selected Material does not prove the expected textured Sprite variant")
    if any(name != "USE_TEXTURE" and value not in (False, 0, None) for name, value in defines.items()):
        raise MaterialProfileError("selected Material enables a macro outside the supported variant")
    if not isinstance(props, dict) or not set(props).issubset(_SUPPORTED_PROPERTIES):
        raise MaterialProfileError("selected Material has parameters outside the supported property contract")

    effect_props = passes[0].get("properties")
    if not isinstance(effect_props, dict) or not set(_SUPPORTED_PROPERTIES).issubset(effect_props):
        raise MaterialProfileError("Effect property declaration is incomplete")
    result: dict[str, Any] = {}
    source_values: dict[str, Any] = {}
    for name in _SUPPORTED_PROPERTIES:
        declared = effect_props[name].get("value")
        source_values[name] = props.get(name, declared)
        raw = source_values[name]
        if name == "silhouette":
            result[name] = _decode_color(raw)
        else:
            if isinstance(raw, list) and len(raw) == 1:
                raw = raw[0]
            result[name] = _scalar(raw, name)
    return result, {"defines": defines, "props": source_values}


def _prefab_material_occurrences(manifest: dict, material_uuid: str) -> list[dict]:
    selected = manifest.get("selection", [])
    assets = _asset_map(manifest)
    hits: list[dict] = []
    for locator in selected:
        asset = next((a for a in assets.values() if a.get("index") == locator and a.get("kind") == "cc.Prefab"), None)
        if not asset:
            continue
        objects = asset.get("document", {}).get("instances", [])
        for object_index, item in enumerate(objects):
            if not isinstance(item, dict):
                continue
            if item.get("__type__") == "cc.Sprite":
                components = [(None, item, f"{asset['sourceId']}#{object_index}")]
            elif item.get("__type__") == "cc.Node":
                components = [(component_index, component, f"{asset['sourceId']}#{object_index}/components/{component_index}")
                              for component_index, component in enumerate(item.get("_components", []))
                              if isinstance(component, dict) and component.get("__type__") == "cc.Sprite"]
            else:
                components = []
            for component_index, sprite, component_source_id in components:
                if not any(isinstance(ref, dict) and ref.get("__uuid__") == material_uuid
                           for ref in sprite.get("_materials", [])):
                    continue
                frame = sprite.get("_spriteFrame")
                hits.append({"prefabSourceId": asset["sourceId"], "prefabPath": asset.get("logicalPath"),
                             "locator": locator, "spriteObjectIndex": object_index,
                             "inlineComponentIndex": component_index, "componentSourceId": component_source_id,
                             "spriteFrameUuid": frame.get("__uuid__") if isinstance(frame, dict) else None})
    if not hits:
        raise MaterialProfileError("selected Material is not referenced by a selected Prefab Sprite")
    return hits


def _selected_prefab_assets(manifest: dict, assets: dict[str, dict]) -> list[dict]:
    rows = []
    for locator in manifest.get("selection", []):
        matches = [asset for asset in assets.values()
                   if asset.get("index") == locator and asset.get("kind") == "cc.Prefab"]
        if len(matches) == 1:
            rows.append(matches[0])
    return rows


def _selected_material_assets(manifest: dict, assets: dict[str, dict]) -> list[dict]:
    by_uuid: dict[str, list[dict]] = {}
    for source_id, asset in assets.items():
        if ":" in source_id:
            by_uuid.setdefault(source_id.split(":", 1)[1], []).append(asset)
    selected: dict[str, dict] = {}
    for prefab in _selected_prefab_assets(manifest, assets):
        for uid in prefab.get("references", []):
            matches = [asset for asset in by_uuid.get(uid, []) if asset.get("kind") == "cc.Material"]
            if len(matches) == 1:
                selected[matches[0]["sourceId"]] = matches[0]
    return list(selected.values())


def _find_supported_effect(assets: dict[str, dict]) -> dict:
    matches = []
    for asset in assets.values():
        if asset.get("kind") == "cc.EffectAsset" and _exact_ui_color_profile(_root_object(asset)):
            matches.append(asset)
    if len(matches) != 1:
        raise MaterialProfileError(f"expected one exact uiColor source program profile; found {len(matches)}")
    return matches[0]


def _find_supported_material(manifest: dict, assets: dict[str, dict], effect_asset: dict) -> dict:
    effect_uuid = effect_asset["sourceId"].split(":", 1)[1]
    linked = []
    for asset in _selected_material_assets(manifest, assets):
        material = _root_object(asset)
        if material.get("_effectAsset", {}).get("__uuid__") != effect_uuid:
            continue
        _source_properties(_root_object(effect_asset), material)
        linked.append(asset)
    if len(linked) != 1:
        raise MaterialProfileError(f"expected one selected material using the exact uiColor Effect; found {len(linked)}")
    return linked[0]


def _selected_material_inventory(manifest: dict, supported_material_ids: set[str] | None = None) -> dict:
    assets = _asset_map(manifest)
    by_uuid: dict[str, list[dict]] = {}
    for source_id, asset in assets.items():
        if ":" in source_id:
            by_uuid.setdefault(source_id.split(":", 1)[1], []).append(asset)
    materials = {asset["sourceId"]: asset for asset in _selected_material_assets(manifest, assets)}
    rows = []
    effect_ids: set[str] = set()
    for source_id, material_asset in sorted(materials.items()):
        material = _root_object(material_asset)
        effect_uuid = material.get("_effectAsset", {}).get("__uuid__")
        effects = [a for a in by_uuid.get(effect_uuid, []) if a.get("kind") == "cc.EffectAsset"] if effect_uuid else []
        effect_asset = effects[0] if len(effects) == 1 else None
        effect_name = _root_object(effect_asset).get("_name") if effect_asset else None
        effect_source_id = effect_asset.get("sourceId") if effect_asset else None
        if effect_source_id:
            effect_ids.add(effect_source_id)
        rows.append({"materialSourceId": source_id, "materialName": material.get("_name"),
                     "materialPath": material_asset.get("logicalPath"), "effectSourceId": effect_source_id,
                     "effectName": effect_name,
                     "status": "supported-profile" if source_id in (supported_material_ids or set()) else "retained-outside-profile",
                     "reason": None if source_id in (supported_material_ids or set()) else "No approved exact source profile in this module; keep source fields/references intact."})
    held = [row for row in rows if row["status"] != "supported-profile"]
    return {"selectedMaterialCount": len(rows), "supportedMaterialCount": len(rows) - len(held),
            "retainedOutsideProfileCount": len(held), "referencedEffectCount": len(effect_ids),
            "materials": rows,
            "effects": [{"sourceId": row["effectSourceId"], "name": row["effectName"]}
                        for row in rows if row["effectSourceId"]]}


def _raw_source_evidence(manifest: dict, *assets: dict) -> dict:
    files: dict[tuple[str, str], dict] = {}
    roots = manifest.get("sourceRoots", {})
    for asset in assets:
        bundle, rel = asset.get("bundle"), asset.get("importPath")
        if not isinstance(bundle, str) or not isinstance(rel, str) or bundle not in roots:
            raise MaterialProfileError("source asset has no exact source root/import path")
        path = (Path(roots[bundle]) / rel).resolve()
        root = Path(roots[bundle]).resolve()
        if root not in path.parents or not path.is_file():
            raise MaterialProfileError("source pack path is absent or escapes its declared root")
        raw = path.read_bytes()
        key = (bundle, rel)
        files[key] = {"bundle": bundle, "importPath": rel, "sha256": _sha(raw), "byteLength": len(raw)}
    return {"sourcePacks": list(files.values()),
            "assets": [{"sourceId": asset["sourceId"], "kind": asset.get("kind"),
                        "logicalPath": asset.get("logicalPath"), "pack": asset.get("pack"),
                        "packOrdinal": asset.get("packOrdinal"), "index": asset.get("index"),
                        "documentSha256": _canonical_sha(asset.get("document"))}
                       for asset in assets]}


def inspect_ui_color(source_manifest: str | Path, normalized_ir: str | Path | None = None) -> dict:
    """Resolve the selected Sprite→Material→Effect closure and source identity."""
    path = Path(source_manifest).resolve()
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MaterialProfileError(f"unable to read source manifest: {exc}") from exc
    assets = _asset_map(manifest)
    effect_asset = _find_supported_effect(assets)
    material_asset = _find_supported_material(manifest, assets, effect_asset)
    effect = _root_object(effect_asset)
    material = _root_object(material_asset)
    props, source_props = _source_properties(effect, material)
    material_uuid = material_asset["sourceId"].split(":", 1)[1]
    effect_uuid = effect_asset["sourceId"].split(":", 1)[1]
    prefabs = _prefab_material_occurrences(manifest, material_uuid)
    # Track the direct texture closure through the exact SpriteFrame UUIDs. The
    # texture itself is supplied by the Sprite renderer at runtime, not baked
    # into the generated Material.
    frame_ids = sorted({row["spriteFrameUuid"] for row in prefabs if row.get("spriteFrameUuid")})
    frame_assets = [_find_asset_by_uuid(assets, uid, "cc.SpriteFrame") for uid in frame_ids]
    texture_ids: set[str] = set()
    for frame_asset in frame_assets:
        for obj in frame_asset.get("document", {}).get("instances", []):
            if isinstance(obj, dict) and isinstance(obj.get("_textureSetter"), dict):
                uid = obj["_textureSetter"].get("__uuid__")
                if uid:
                    texture_ids.add(uid)
    texture_assets = [_find_asset_by_uuid(assets, uid, "cc.Texture2D") for uid in sorted(texture_ids)]
    source_material_ref = material.get("_effectAsset", {}).get("__uuid__")
    if source_material_ref != effect_uuid:
        raise MaterialProfileError("selected Material→Effect UUID edge differs from the exact shader-profile source")
    evidence = _raw_source_evidence(manifest, effect_asset, material_asset,
                                    *frame_assets, *texture_assets)
    material_scope = _selected_material_inventory(manifest, {material_asset["sourceId"]})
    ir_path = Path(normalized_ir).resolve() if normalized_ir is not None else path.parent.parent / "normalize" / "ir.json"
    ir_evidence = None
    if ir_path.is_file():
        try:
            ir_raw = ir_path.read_bytes()
            ir = json.loads(ir_raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise MaterialProfileError(f"unable to read normalized IR evidence: {exc}") from exc
        ir_components = ir.get("components", [])
        selected_prefab_ids = {row["prefabSourceId"] for row in prefabs}
        mapped = [component for component in ir_components if isinstance(component, dict)
                  and component.get("type") == "cc.Sprite"
                  and component.get("materials") and material_asset["sourceId"] in component["materials"]
                  and any(component.get("sourceId", "").startswith(prefab_id + "#") for prefab_id in selected_prefab_ids)]
        source_component_ids = sorted(row["componentSourceId"] for row in prefabs)
        ir_component_ids = sorted(component.get("sourceId") for component in mapped)
        ir_evidence = {"path": str(ir_path), "sha256": _sha(ir_raw),
                       "selectedSpriteMaterialReferenceCount": len(mapped),
                       "sourceOccurrences": len(prefabs),
                       "sourceToIRComponentIds": {"source": source_component_ids,
                                                   "ir": ir_component_ids,
                                                   "missingInIR": sorted(set(source_component_ids) - set(ir_component_ids)),
                                                   "extraInIR": sorted(set(ir_component_ids) - set(source_component_ids)),
                                                   "exactMatch": source_component_ids == ir_component_ids},
                       "components": [{"sourceId": c.get("sourceId"), "materialSourceId": material_asset["sourceId"]}
                                      for c in mapped]}
    return {"profile": PROFILE, "status": "supported-source-subset",
            "source": {"effectSourceId": effect_asset["sourceId"], "materialSourceId": material_asset["sourceId"],
                       "effectProgram": PROGRAM_NAME, "prefabOccurrences": prefabs,
                       "programStageCanonicalSha256": _stage_hashes(effect),
                       "programCanonicalSha256": _program_profile_hash(_stage_hashes(effect)),
                       "spriteFrames": [{"sourceId": a["sourceId"], "logicalPath": a.get("logicalPath")}
                                        for a in frame_assets],
                       "textures": [{"sourceId": a["sourceId"], "logicalPath": a.get("logicalPath")}
                                    for a in texture_assets],
                       "sourceEvidence": evidence,
                       "normalizedIR": ir_evidence,
                       "selectedMaterialScope": material_scope,
                       "effectDocumentSha256": _canonical_sha(effect_asset["document"]),
                       "materialDocumentSha256": _canonical_sha(material_asset["document"])},
            "material": {"sourceName": material.get("_name"), "defines": source_props["defines"],
                         "sourceProps": source_props["props"], "properties": props,
                         "propertyBindings": {"brightness": {"creator": "brightness", "unity": "_Brightness"},
                                             "saturation": {"creator": "saturation", "unity": "_Saturation"},
                                             "constrast": {"creator": "constrast", "unity": "_Constrast"},
                                             "gray": {"creator": "gray", "unity": "_Gray"},
                                             "silhouette": {"creator": "silhouette", "unity": "_Silhouette"}},
                         "textureBinding": "SpriteFrame/Texture2D remains supplied by target Sprite renderer"}}


def _unity_mat(name: str, shader_guid: str, props: dict) -> str:
    c = props["silhouette"]
    return ("%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!21 &2100000\nMaterial:\n"
            "  serializedVersion: 8\n  m_ObjectHideFlags: 0\n  m_CorrespondingSourceObject: {fileID: 0}\n"
            "  m_PrefabInstance: {fileID: 0}\n  m_PrefabAsset: {fileID: 0}\n"
            f"  m_Name: {name}\n  m_Shader: {{fileID: 4800000, guid: {shader_guid}, type: 3}}\n"
            "  m_Parent: {fileID: 0}\n  m_ModifiedSerializedProperties: 0\n  m_ValidKeywords: []\n"
            "  m_InvalidKeywords: []\n  m_LightmapFlags: 4\n  m_EnableInstancingVariants: 0\n"
            "  m_DoubleSidedGI: 0\n  m_CustomRenderQueue: -1\n  stringTagMap: {}\n"
            "  disabledShaderPasses: []\n  m_SavedProperties:\n    serializedVersion: 3\n"
            "    m_TexEnvs:\n    - _MainTex:\n        m_Texture: {fileID: 0}\n"
            "        m_Scale: {x: 1, y: 1}\n        m_Offset: {x: 0, y: 0}\n"
            "    m_Ints: []\n    m_Floats:\n"
            f"    - _Brightness: {props['brightness']!r}\n"
            f"    - _Saturation: {props['saturation']!r}\n"
            f"    - _Constrast: {props['constrast']!r}\n"
            f"    - _Gray: {props['gray']!r}\n"
            "    m_Colors:\n"
            f"    - _Silhouette: {{r: {c[0]!r}, g: {c[1]!r}, b: {c[2]!r}, a: {c[3]!r}}}\n"
            "    - _Color: {r: 1, g: 1, b: 1, a: 1}\n")


def _creator_material_contract(effect_guid: str, name: str, props: dict, source: dict) -> dict:
    return {"schema": "monkey-creator38-material-contract/1", "status": "material-intent-not-editor-imported",
            "name": name, "effectAsset": {"path": "Shader2DUIColor.effect", "uuid": effect_guid},
            "technique": 0, "defines": {"USE_TEXTURE": True}, "properties": props,
            "sourceSpriteTextureBinding": source["material"]["textureBinding"],
            "assignment": "Set as the Sprite custom material; retain SpriteFrame on Sprite.",
            "materialSourceId": source["source"]["materialSourceId"],
            "propertyBindings": source["material"]["propertyBindings"]}


def generate_ui_color(source_manifest: str | Path, output_dir: str | Path,
                      normalized_ir: str | Path | None = None) -> dict:
    """Generate the bounded dual-target UI-color candidate from exact source closure.

    Creator's material is emitted as a runtime/editor handoff contract because
    Creator serializes native material identity in its asset database; this
    function does not fabricate an imported UUID or an editor receipt.
    """
    source = inspect_ui_color(source_manifest, normalized_ir)
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty material candidate: {output}")
    output.mkdir(parents=True, exist_ok=True)
    material_source_id = source["source"]["materialSourceId"]
    unity_guid = uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{material_source_id}:unity-ui-color").hex
    unity_mat_guid = uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{material_source_id}:unity-material").hex
    creator_guid = uuid.uuid5(uuid.NAMESPACE_URL, f"monkey:{material_source_id}:creator38-ui-color-effect").hex
    unity_dir = output / "Unity"
    creator_dir = output / "Creator38"
    unity_dir.mkdir()
    creator_dir.mkdir()
    shader = (_TARGET_DIR / "Shader2DUIColor.shader").read_bytes()
    effect = (_TARGET_DIR / "Shader2DUIColor.effect").read_bytes()
    props = source["material"]["properties"]
    unity_shader_meta = (f"fileFormatVersion: 2\nguid: {unity_guid}\nShaderImporter:\n"
                         "  externalObjects: {}\n  defaultTextures: []\n  nonModifiableTextures: []\n"
                         "  preprocessorOverride: 0\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n")
    creator_effect_meta = (f"ver: 1.0.5\nimporter: effect\nimported: true\nuuid: {creator_guid}\n"
                           "files: {}\nsubMetas: {}\nuserData: {}\n")
    files = {
        unity_dir / "Shader2DUIColor.shader": shader,
        unity_dir / "Shader2DUIColor.shader.meta": unity_shader_meta.encode(),
        unity_dir / "Shader2DUIColor.mat": _unity_mat("Shader2DUIColor", unity_guid, props).encode(),
        unity_dir / "Shader2DUIColor.mat.meta": (
            f"fileFormatVersion: 2\nguid: {unity_mat_guid}\nNativeFormatImporter:\n  externalObjects: {{}}\n"
            "  mainObjectFileID: 2100000\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n").encode(),
        creator_dir / "Shader2DUIColor.effect": effect,
        creator_dir / "Shader2DUIColor.effect.meta": creator_effect_meta.encode(),
        creator_dir / "Shader2DUIColor.material-contract.json": json.dumps(
            _creator_material_contract(creator_guid, "Shader2DUIColor", props, source),
            ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    }
    outputs = []
    for path, raw in files.items():
        path.write_bytes(raw)
        outputs.append({"path": path.relative_to(output).as_posix(), "sha256": _sha(raw), "byteLength": len(raw)})
    report = {"schema": "monkey-prefab-material-handoff/1", "status": "source-bound-candidate-generated",
              "nativeCompilation": "not_run", "creatorEditorImport": "not_run", "renderValidation": "not_run",
              "profile": source["profile"], "source": source["source"],
              "unity": {"shaderGuid": unity_guid, "materialGuid": unity_mat_guid,
                        "materialSourceId": source["source"]["materialSourceId"],
                        "properties": props, "textureBinding": source["material"]["textureBinding"]},
              "creator38": {"effectGuid": creator_guid,
                            "materialStatus": "runtime-editor-contract-only-native-material-identity-pending",
                            "properties": props},
              "outputs": outputs,
              "selectedMaterialScope": source["source"]["selectedMaterialScope"],
              "limitations": ["No native compiler or Editor was run.",
                              "Creator material contract is not an imported .mtl asset.",
                              "Prefab Sprite assignment and texture identity readback remain integration work."]}
    report_raw = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    (output / "handoff.json").write_bytes(report_raw)
    return report


def _owned_file(target_path: str, source_path: str | None = None, content: bytes | None = None) -> dict:
    if (source_path is None) == (content is None):
        raise MaterialProfileError("owned file must have exactly one immutable source")
    raw = content if content is not None else read(Path(__file__).parents[2] / source_path)
    return {"path": target_path, "sourcePath": source_path, "sha256": _sha(raw), "byteLength": len(raw),
            **({"contentBase64": base64.b64encode(raw).decode("ascii")} if source_path is None else {})}


def _validate_binding_spec(spec: dict) -> None:
    """Validate the concrete cross-language payload shape consumed by both helpers."""
    if not isinstance(spec, dict) or spec.get("profile") != PROFILE:
        raise MaterialProfileError("native material spec profile is unsupported")
    if "sourceMaterialId" in spec or not isinstance(spec.get("materialSourceId"), str) or not spec["materialSourceId"]:
        raise MaterialProfileError("native material spec requires the canonical materialSourceId field")
    if spec.get("programCanonicalSha256") != _program_profile_hash(UI_COLOR_STAGE_HASHES):
        raise MaterialProfileError("native material spec program hash differs from exact profile")
    unity, creator = spec.get("unity"), spec.get("creator")
    if not isinstance(unity, dict) or not isinstance(creator, dict):
        raise MaterialProfileError("native target paths are missing")
    for key in ("shaderPath", "shaderGuid", "materialPath", "materialGuid"):
        if not isinstance(spec.get(key), str) or spec[key] != unity.get(key):
            raise MaterialProfileError(f"Unity helper field mismatch: {key}")
    if not all(isinstance(creator.get(key), str) and creator[key] for key in ("effectPath", "effectUuid", "materialPath", "materialUuid", "materialMetaPath")):
        raise MaterialProfileError("Creator native Effect/Material identities are incomplete")
    if creator["materialMetaPath"] != creator["materialPath"] + ".meta":
        raise MaterialProfileError("Creator native Material metadata path differs")
    source_ids = spec.get("sourceComponentIds")
    sprite_bindings = spec.get("spriteBindings")
    if (not isinstance(source_ids, list) or not source_ids or len(source_ids) != len(set(source_ids))
            or not isinstance(sprite_bindings, list)
            or [row.get("sourceId") for row in sprite_bindings if isinstance(row, dict)] != source_ids):
        raise MaterialProfileError("native target sourceId binding lists differ")
    properties = spec.get("properties")
    if not isinstance(properties, dict) or set(properties) != set(_SUPPORTED_PROPERTIES):
        raise MaterialProfileError("native target property structure differs")
    if spec.get("silhouette") != dict(zip(("r", "g", "b", "a"), properties["silhouette"])):
        raise MaterialProfileError("native target color structure differs")


def plan_ui_color(source_manifest: str | Path, normalized_ir: str | Path, module: str,
                  source_manifest_sha256: str, normalized_ir_sha256: str) -> dict:
    """Build a pinned target-plan fragment plus exact owned-file declarations.

    Native Unity .mat and Creator .mtl assets are deliberately omitted from
    ownedFiles; the target helpers create, save and read those assets through
    each engine's native asset APIs.
    """
    if not isinstance(module, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", module) or ".." in module:
        raise MaterialProfileError("module must be one safe path segment")
    if not re.fullmatch(r"[0-9a-f]{64}", source_manifest_sha256 or "") or not re.fullmatch(r"[0-9a-f]{64}", normalized_ir_sha256 or ""):
        raise MaterialProfileError("source manifest and IR SHA-256 pins are required")
    manifest_path, ir_path = Path(source_manifest).resolve(), Path(normalized_ir).resolve()
    manifest_raw, ir_raw = manifest_path.read_bytes(), ir_path.read_bytes()
    if _sha(manifest_raw) != source_manifest_sha256 or _sha(ir_raw) != normalized_ir_sha256:
        raise MaterialProfileError("explicit source manifest/IR pin mismatch")
    ir = json.loads(ir_raw)
    if ir.get("sourceManifestSha256") != source_manifest_sha256:
        raise MaterialProfileError("normalized IR is not pinned to the supplied source manifest")
    source = inspect_ui_color(manifest_path, ir_path)
    comparison = source["source"]["normalizedIR"].get("sourceToIRComponentIds")
    if not comparison or comparison.get("exactMatch") is not True:
        raise MaterialProfileError("source material component IDs do not exactly match the pinned normalized IR")

    material_source_id = source["source"]["materialSourceId"]
    unity_shader_guid = uuid.uuid5(uuid.NAMESPACE_URL, f"monkey/{material_source_id}/unity-material/{module}/shader").hex
    unity_material_guid = uuid.uuid5(uuid.NAMESPACE_URL, f"monkey/{material_source_id}/unity-material/{module}/material").hex
    creator_effect_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"monkey/{material_source_id}/creator-3.8.8/{module}/effect"))
    creator_material_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"monkey/{material_source_id}/creator-3.8.8/{module}/material"))
    unity_shader_path = f"Assets/Game/Content/Shaders/{module}/Shader2DUIColor.shader"
    unity_material_path = f"Assets/Game/Content/Materials/{module}/Shader2DUIColor.mat"
    creator_effect_path = f"assets/resources/Shaders/{module}/Shader2DUIColor.effect"
    creator_material_path = f"assets/resources/Materials/{module}/Shader2DUIColor.mtl"
    props = source["material"]["properties"]
    shader_meta = (f"fileFormatVersion: 2\nguid: {unity_shader_guid}\nShaderImporter:\n"
                   "  externalObjects: {}\n  defaultTextures: []\n  nonModifiableTextures: []\n"
                   "  preprocessorOverride: 0\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n").encode()
    material_meta = (f"fileFormatVersion: 2\nguid: {unity_material_guid}\nNativeFormatImporter:\n"
                     "  externalObjects: {}\n  mainObjectFileID: 2100000\n  userData: \n"
                     "  assetBundleName: \n  assetBundleVariant: \n").encode()
    creator_effect_meta = json.dumps({"ver": "1.0.5", "uuid": creator_effect_uuid, "importer": "effect",
                                      "imported": False, "files": [], "subMetas": {}, "userData": {}},
                                     ensure_ascii=False, indent=2, sort_keys=True).encode() + b"\n"
    creator_material_meta = json.dumps({"ver": "1.0.5", "uuid": creator_material_uuid, "importer": "material",
                                        "imported": False, "files": [], "subMetas": {}, "userData": {}},
                                       ensure_ascii=False, indent=2, sort_keys=True).encode() + b"\n"
    files = [
        _owned_file(unity_shader_path, f"src/monkey/targets/materials/ui_color/Shader2DUIColor.shader"),
        _owned_file(unity_shader_path + ".meta", content=shader_meta),
        _owned_file(unity_material_path + ".meta", content=material_meta),
        _owned_file(creator_effect_path, "src/monkey/targets/materials/ui_color/Shader2DUIColor.effect"),
        _owned_file(creator_effect_path + ".meta", content=creator_effect_meta),
        _owned_file(creator_material_path + ".meta", content=creator_material_meta),
    ]
    spec = {"schema": "monkey-prefab-material-binding-spec/1", "profile": source["profile"],
            "programCanonicalSha256": source["source"]["programCanonicalSha256"],
            "programStageCanonicalSha256": source["source"]["programStageCanonicalSha256"],
            "module": module, "materialSourceId": material_source_id,
            "sourceEffectId": source["source"]["effectSourceId"],
            "sourceManifestSha256": source_manifest_sha256, "normalizedIrSha256": normalized_ir_sha256,
            "sourceComponentIds": comparison["source"], "sourceIrComponentIds": comparison,
            "properties": props, "propertyBindings": source["material"]["propertyBindings"],
            "brightness": props["brightness"], "saturation": props["saturation"],
            "constrast": props["constrast"], "gray": props["gray"],
            "silhouette": {"r": props["silhouette"][0], "g": props["silhouette"][1],
                           "b": props["silhouette"][2], "a": props["silhouette"][3]},
            "textureBinding": source["material"]["textureBinding"],
            "unity": {"shaderPath": unity_shader_path, "shaderGuid": unity_shader_guid,
                      "materialPath": unity_material_path, "materialGuid": unity_material_guid},
            "shaderPath": unity_shader_path, "shaderGuid": unity_shader_guid,
            "materialPath": unity_material_path, "materialGuid": unity_material_guid,
            "creator": {"effectPath": creator_effect_path, "effectUuid": creator_effect_uuid,
                        "materialPath": creator_material_path, "materialUuid": creator_material_uuid,
                        "materialMetaPath": creator_material_path + ".meta"},
            "spriteBindings": [{"sourceId": component_id} for component_id in comparison["source"]],
            "sourceBindings": [{"sourceId": row["componentSourceId"],
                                "sourcePrefabId": row["prefabSourceId"],
                                "spriteFrameUuid": row.get("spriteFrameUuid")}
                               for row in source["source"]["prefabOccurrences"]],
            "nativeMaterialCreation": {"unity": "Create AssetDatabase metadata with planned GUID, then AssetDatabase.CreateAsset(new Material(importedShader), materialPath)",
                                       "creator38": "cc.Material.initialize + EditorExtends.serialize + host assetdb save/reimport callback returning exact path, asset UUID and metadata UUID"},
            "nativeBindingHelpers": {
                "unity": {"sourcePath": "src/monkey/targets/materials/ui_color/UnityMaterialBindings.cs",
                          "sha256": _sha(read(Path(__file__).parents[2] / "src/monkey/targets/materials/ui_color/UnityMaterialBindings.cs"))},
                "creator38": {"sourcePath": "src/monkey/targets/materials/ui_color/CreatorMaterialBindings.js",
                              "sha256": _sha(read(Path(__file__).parents[2] / "src/monkey/targets/materials/ui_color/CreatorMaterialBindings.js"))}},
            "readback": {"unity": "AssetDatabase GUID/localFileId, Shader GUID and all source properties",
                         "creator38": "reloaded cc.Material UUID, EffectAsset UUID, technique and source properties"}}
    _validate_binding_spec(spec)
    return {"schema": "monkey-prefab-material-plan-fragment/1", "spec": spec, "ownedFiles": files}


def emit_ui_color(plan: dict, plan_root: str | Path, output_root: str | Path) -> dict:
    """Copy only pinned helper/shader/effect files into a fresh target candidate."""
    if not isinstance(plan, dict) or plan.get("schema") != "monkey-prefab-material-plan-fragment/1":
        raise MaterialProfileError("unsupported material plan fragment")
    spec = plan.get("spec", {})
    _validate_binding_spec(spec)
    if spec.get("profile") != PROFILE or spec.get("programCanonicalSha256") != _program_profile_hash(UI_COLOR_STAGE_HASHES):
        raise MaterialProfileError("material plan is outside the exact source shader profile")
    if spec.get("sourceIrComponentIds", {}).get("exactMatch") is not True:
        raise MaterialProfileError("material plan source/IR component pins are not exact")
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    staged = []
    seen = set()
    for row in plan.get("ownedFiles", []):
        target = row.get("path")
        source_path = row.get("sourcePath")
        if (not isinstance(target, str) or not target.startswith(("Assets/", "assets/"))
                or ".." in Path(target).parts or target in seen):
            raise MaterialProfileError("unsafe material target owned-file path")
        seen.add(target)
        if source_path:
            raw = read(inside(Path(plan_root).resolve(), source_path))
        else:
            encoded = row.get("contentBase64")
            if not isinstance(encoded, str):
                raise MaterialProfileError("owned metadata content is absent")
            raw = base64.b64decode(encoded, validate=True)
        if len(raw) != row.get("byteLength") or _sha(raw) != row.get("sha256"):
            raise MaterialProfileError("material owned file differs from its plan pin: " + target)
        dest = inside(root, target)
        if dest.exists():
            raise FileExistsError(f"refusing to replace target asset: {target}")
        staged.append((target, dest, raw))
    emitted = []
    for target, dest, raw in staged:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        emitted.append({"path": target, "sha256": _sha(raw), "byteLength": len(raw)})
    return {"schema": "monkey-prefab-material-emission/1", "status": "owned-files-emitted-native-assets-pending",
            "spec": spec, "ownedFiles": emitted,
            "nativeAssets": {"unity": "created by UnityMaterialBindings.cs through AssetDatabase",
                             "creator38": "created by CreatorMaterialBindings.js through native serializer/assetdb callback"},
            "nativeCompilation": "not_run", "renderValidation": "not_run"}
