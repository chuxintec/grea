"""Evidence-bound Cocos Spine material profiles for recovered Prefabs.

Creator 3.8.8 uses its exact builtin Spine material when the pinned source
runtime variant is equivalent. Unity receives an independently authored
one-color material shader and per-page blend contract. Neither path claims
native import, compilation, runtime rendering or visual acceptance.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any

from .io import inside, read


PROFILE = "cocos24-builtin-spine-material-v1"
PROGRAM = "builtin-2d-spine|vs|fs"
SPINE_EFFECT_STAGE_HASHES = {
    "glsl1.frag": "3bb2a55e9e5fa8bb9d1f97b31fd75e6292bb87c4cab39efe5afeed1d4a182714",
    "glsl1.vert": "1dbd3ebfe7a0e34ef270254c1506dca27d6ccb6aad7d1fb2847fe7a7ce04b09a",
    "glsl3.frag": "1a187bf082dff2843d08d5b2f4d069110cdefbfaf1fa16ac36061e0007ad2e46",
    "glsl3.vert": "043cc31b8476583058a368c6edf9e9186164886402094ffa1d035505d1e82f89",
}
CREATOR_388_NATIVE_SPINE_SHADER_HASH = 3890043391
CREATOR_388_EFFECT_SHA256 = "1ffe08e459a6402f47b76a44a99189f0d55283b6ad5bea041f5cc925ed73b1d2"
SOURCE_ENGINE_FILE_PINS = {
    "extensions/spine/Skeleton.js": "7cdc119e26aa6dceec4bd78ae30dd08f39daa2f0da5d914d2197a730b558a5e8",
    "extensions/spine/spine-assembler.js": "a733c6b6b101cc43420b7bd60c133631a4f6a77cc942c5180a547ddac6523e53",
    "cocos2d/core/assets/material/CCMaterial.js": "7f40846a2999a4ea0cc01dc38d77bbed9ccb8c9e2b42168f03c49793bcf0dcd8",
    "cocos2d/core/assets/CCTexture2D.js": "ba795a58c0983ccd57c043e4355a192ff799d62fee4392dd77e7a5a43bdec8eb",
    "cocos2d/core/assets/material/effect-parser.ts": "08ace75665e7cde2cafd98e82b0692bdba67770fe407370980f271a5326bb4b4",
    "cocos2d/renderer/types.js": "17838b1cc430b585de605be2739fe12caac4f1d0d8933a200e598e379e0fac18",
    "cocos2d/renderer/core/pass.js": "499355b0cfe5982eba6c2d36e77ce3577b5d58251f2f9a9d6a669f614e769205",
    "cocos2d/renderer/gfx/enums.js": "97aa793e472c8228f671efa66b55b7adadc0f784440adac5bcd2d5c16f31f1df",
    "extensions/spine/lib/spine.js": "26570ea86a49c6174b53ddceb38302c642b33e096e3d822c6739ccd01d030a2f",
}
TARGET_ENGINE_FILE_PINS = {
    "cocos/spine/skeleton.ts": "2e86383e7e7dfb93bc40ec1d7e44c6bb2bebc8a3e95c100ad16620bd24114329",
    "cocos/spine/assembler/simple.ts": "dddc0f8d8e7e875d2d7835c389e534379a7d76c9a9d0a1a07d1e9973969a8277",
    "editor/assets/effects/for2d/builtin-spine.effect": CREATOR_388_EFFECT_SHA256,
    "cocos/asset/assets/material.ts": "e0de9543c7f442cdee052cb6382519aa68d2b89009a77d3e74ecfcd044a0f4a4",
    "cocos/render-scene/core/pass.ts": "a782fafde1d32fc7dacd30744ab5a6bc78e373f73934ab8eabceeaa1b06c9044",
    "cocos/render-scene/core/material-instance.ts": "2baf215c4f5161bb8b68a39d7389ca932198af304aca8e64ef9ac5d4fa683ea3",
    "cocos/render-scene/core/pass-instance.ts": "87674d92ad54e4f3d9cc31c6dc2fa1343c391369c3f370f37d501d0666f1c754",
    "cocos/misc/renderer.ts": "9553f966d2e93ee434edce063f5fb6829caef841bd8c483b87afc3234af3f0f8",
    "cocos/asset/asset-manager/builtin-res-mgr.ts": "aa90e49569399d6fffa3261ea3177b5970edfd27f57524fdc15275adad35fa14",
    "cocos/gfx/base/shader.ts": "5a6fe178d087166bab951fa3f131c38ef16ac113be66702943878d9cecc34880",
}
UNITY_SPINE38_REFERENCE = {
    "repository": "EsotericSoftware/spine-runtimes",
    "branch": "3.8",
    "commit": "8b4844bd4b193ba9e54487ed397a777993cbad56",
    "shaderPath": "spine-unity/Assets/Spine/Runtime/spine-unity/Shaders/Spine-Skeleton.shader",
    "shaderSha256": "5710d3dea3de57a81b2d5f65c73b0b0c0288e736c2990f7a6c006da040abda4f",
    "rendererSourcePath": "spine-unity/Assets/Spine/Runtime/spine-unity/Components/SkeletonRenderer.cs",
    "rendererSourceSha256": "a56bc75ccd170f3cbb6523e318e02a99fb0af41713836cbd12df3b10e0971525",
    "blendMaterialsSourcePath": "spine-unity/Assets/Spine/Runtime/spine-unity/Asset Types/BlendModeMaterials.cs",
    "blendMaterialsSourceSha256": "57b62c617f60f91c7bab7da6449850d72830c7b6baa740957eed134629ab51fd",
    "customMaterialsSourcePath": "spine-unity/Assets/Spine/Runtime/spine-unity/Components/SkeletonRendererCustomMaterials/SkeletonRendererCustomMaterials.cs",
    "customMaterialsSourceSha256": "f4db3d21798fb1a19344092971f063c4cd90d5c03c03bf1fbdcc82edca49379d",
    "shaderSemantics": {"blend": "One OneMinusSrcAlpha", "pmaVertexColorsDefault": True,
                        "straightAlphaInputToggle": True},
    "targetUse": "official 3.8 runtime source reference; local Unity runtime package/native material readback is still required",
}
UNITY_PROFILE_SHADER_SHA256 = "0fe1ea3481787d0de2bd7545c8e77d769c681a7d30ca48d6ad56482bdeec549b"
CREATOR_BINDING_HELPER_SHA256 = "cb2bc9f1470efd6a8ea0093a3607b85f317eaa7c0079df6ac1163532c770f32a"
UNITY_BINDING_HELPER_SHA256 = "464fb0e61a938257837f993640a0ba8944708aac2cad786aee8c6a39ef241f00"
TARGET_DIR = Path(__file__).parent / "targets" / "materials" / "spine"


class SpineMaterialError(ValueError):
    """Source evidence or normalized pins do not satisfy the Spine contract."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _stage_sha(text: str) -> str:
    return _sha(text.replace("\r\n", "\n").replace("\r", "\n").strip().encode("utf-8"))


class _SpineReader:
    """Bounded reader for the 3.8 binary header/bones/slots needed here."""
    def __init__(self, data: bytes):
        if len(data) > 64 * 1024 * 1024:
            raise SpineMaterialError("Spine binary exceeds the inspection limit")
        self.data = data
        self.pos = 0

    def _take(self, size: int) -> bytes:
        if size < 0 or self.pos + size > len(self.data):
            raise SpineMaterialError("truncated Spine binary before slot blend modes")
        value = self.data[self.pos:self.pos + size]
        self.pos += size
        return value

    def byte(self) -> int:
        return struct.unpack(">b", self._take(1))[0]

    def int32(self) -> int:
        return struct.unpack(">i", self._take(4))[0]

    def float32(self) -> float:
        return struct.unpack(">f", self._take(4))[0]

    def boolean(self) -> bool:
        return self.byte() != 0

    def varint(self) -> int:
        result = 0
        shift = 0
        for _ in range(5):
            value = self.byte() & 0xFF
            result |= (value & 0x7F) << shift
            if not value & 0x80:
                return result
            shift += 7
        raise SpineMaterialError("invalid Spine varint")

    def count(self, label: str) -> int:
        value = self.varint()
        if value > 100_000:
            raise SpineMaterialError(f"unbounded Spine {label} count")
        return value

    def string(self) -> str | None:
        byte_count = self.varint()
        if byte_count == 0:
            return None
        if byte_count == 1:
            return ""
        return self._take(byte_count - 1).decode("utf-8")

    def string_ref(self, strings: list[str | None]) -> str | None:
        index = self.varint()
        if index == 0:
            return None
        if index > len(strings):
            raise SpineMaterialError("Spine string reference is out of range")
        return strings[index - 1]


def _binary_slot_blend_modes(raw: bytes) -> dict:
    """Read only the Spine 3.8 header/bone/slot prefix; never execute the asset."""
    reader = _SpineReader(raw)
    reader.string()  # hash
    version = reader.string()
    if not isinstance(version, str) or not re.fullmatch(r"3\.8\.\d+", version):
        raise SpineMaterialError("selected binary is not a recognized Spine 3.8 data version")
    for _ in range(4):
        reader.float32()
    nonessential = reader.boolean()
    if nonessential:
        reader.float32()
        reader.string()
        reader.string()
    strings = [reader.string() for _ in range(reader.count("string-table"))]
    bone_count = reader.count("bone")
    for index in range(bone_count):
        reader.string()
        if index:
            reader.varint()
        for _ in range(8):
            reader.float32()
        reader.varint()  # transform mode
        reader.boolean()  # skin required
        if nonessential:
            reader.int32()
    slots = []
    blend_names = ("normal", "additive", "multiply", "screen")
    for index in range(reader.count("slot")):
        name = reader.string()
        reader.varint()  # bone index
        reader.int32()   # light color
        reader.int32()   # dark color or -1
        reader.string_ref(strings)
        blend_index = reader.varint()
        if blend_index >= len(blend_names):
            raise SpineMaterialError("Spine slot has an unknown blend mode")
        slots.append({"slotIndex": index, "slotName": name, "blendMode": blend_names[blend_index]})
    return {"spineVersion": version, "boneCount": bone_count, "slotCount": len(slots),
            "blendModeCounts": {name: sum(1 for slot in slots if slot["blendMode"] == name)
                                for name in blend_names},
            "binaryPrefixBytesRead": reader.pos}


def _asset_rows(manifest: dict) -> dict[str, list[dict]]:
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        raise SpineMaterialError("source manifest has no asset list")
    result: dict[str, list[dict]] = {}
    for row in assets:
        if isinstance(row, dict) and isinstance(row.get("sourceId"), str):
            result.setdefault(row["sourceId"], []).append(row)
    return result


def _root(asset: dict) -> dict:
    doc = asset.get("document")
    instances = doc.get("instances") if isinstance(doc, dict) else None
    idx = doc.get("root") if isinstance(doc, dict) else None
    if not isinstance(instances, list):
        raise SpineMaterialError(f"{asset.get('sourceId')} has no decoded source document")
    if not isinstance(idx, int) or idx < 0 or idx >= len(instances) or not isinstance(instances[idx], dict):
        raise SpineMaterialError(f"{asset.get('sourceId')} has an invalid document root")
    return instances[idx]


def _resolve_uuid(rows: dict[str, list[dict]], bundle: str, uuid: str, kind: str) -> tuple[dict, list[str]]:
    source_id = f"{bundle}:{uuid}"
    chain: list[str] = []
    seen: set[str] = set()
    while True:
        if source_id in seen:
            raise SpineMaterialError(f"redirect cycle while resolving {kind} {uuid}")
        seen.add(source_id)
        matches = rows.get(source_id, [])
        if len(matches) != 1:
            raise SpineMaterialError(f"missing or ambiguous {kind} {source_id}")
        asset = matches[0]
        if asset.get("kind") != "redirect":
            if asset.get("kind") != kind:
                raise SpineMaterialError(f"{source_id} resolves to {asset.get('kind')}, expected {kind}")
            return asset, chain
        target = asset.get("redirectTarget")
        if not isinstance(target, str) or not target:
            raise SpineMaterialError(f"{source_id} redirect has no explicit target")
        declared_bundle = asset.get("redirectBundle")
        if declared_bundle and target.split(":", 1)[0] != declared_bundle:
            raise SpineMaterialError(f"{source_id} redirect bundle does not match its target")
        chain.append(source_id + " -> " + target)
        source_id = target


def _program(effect: dict) -> tuple[dict, dict[str, str]]:
    if effect.get("__type__") != "cc.EffectAsset":
        raise SpineMaterialError("referenced asset is not a cc.EffectAsset")
    shaders = effect.get("shaders")
    if not isinstance(shaders, list) or len(shaders) != 1 or not isinstance(shaders[0], dict):
        raise SpineMaterialError("Effect program set differs from the pinned builtin Spine profile")
    shader = shaders[0]
    if shader.get("name") != PROGRAM:
        raise SpineMaterialError("Effect program name differs from the pinned builtin Spine profile")
    hashes: dict[str, str] = {}
    for lang in ("glsl1", "glsl3"):
        code = shader.get(lang)
        if not isinstance(code, dict):
            raise SpineMaterialError("Effect lacks a complete recorded shader language")
        for stage in ("vert", "frag"):
            text = code.get(stage)
            if not isinstance(text, str) or not text.strip():
                raise SpineMaterialError("Effect lacks nonempty vertex/fragment source")
            hashes[f"{lang}.{stage}"] = _stage_sha(text)
    if hashes != SPINE_EFFECT_STAGE_HASHES:
        raise SpineMaterialError("Effect program formula/stages differ from the exact pinned source profile")
    return shader, hashes


def _material(effect_uuid: str, material: dict) -> dict:
    if material.get("__type__") != "cc.Material":
        raise SpineMaterialError("bound asset is not a cc.Material")
    ref = material.get("_effectAsset")
    if not isinstance(ref, dict) or not isinstance(ref.get("__uuid__"), str):
        raise SpineMaterialError("Material has no explicit Effect reference")
    if ref["__uuid__"] != effect_uuid:
        raise SpineMaterialError("Material Effect reference differs from resolved source Effect")
    if material.get("_techniqueData") not in ({}, None):
        raise SpineMaterialError("Material contains serialized overrides outside the builtin profile")
    allowed = {"__type__", "_effectAsset", "_name", "_techniqueData", "_uuid"}
    if set(material) - allowed:
        raise SpineMaterialError("Material has unrecognized serialized fields")
    return {"name": material.get("_name"), "techniqueData": material.get("_techniqueData", {})}


def _source_semantics(effect: dict, shader: dict) -> dict:
    techniques = effect.get("techniques")
    if not isinstance(techniques, list) or len(techniques) != 1:
        raise SpineMaterialError("Effect technique set differs from builtin Spine profile")
    passes = techniques[0].get("passes") if isinstance(techniques[0], dict) else None
    if not isinstance(passes, list) or len(passes) != 1 or not isinstance(passes[0], dict):
        raise SpineMaterialError("Effect pass set differs from builtin Spine profile")
    source_pass = passes[0]
    if source_pass.get("program") != PROGRAM:
        raise SpineMaterialError("Effect pass does not bind the pinned program")
    frag = shader["glsl3"]["frag"]
    # These checks are semantic anchors in addition to the canonical stage hash.
    formula = "((texColor.a - 1.0) * v_dark.a + 1.0 - texColor.rgb) * v_dark.rgb + texColor.rgb * v_light.rgb"
    if formula not in " ".join(frag.split()):
        raise SpineMaterialError("source two-color formula no longer matches the reviewed semantic anchor")
    has_gamma = "#if INPUT_IS_GAMMA" in frag
    has_alpha_atlas = "#if CC_USE_ALPHA_ATLAS_texture" in frag
    defines = shader.get("defines")
    define_names = {d.get("name") for d in defines if isinstance(d, dict)} if isinstance(defines, list) else set()
    required = {"USE_TINT", "CC_USE_MODEL", "USE_ALPHA_TEST", "CC_USE_ALPHA_ATLAS_texture", "INPUT_IS_GAMMA"}
    if define_names != required:
        raise SpineMaterialError("Effect define set differs from pinned source program")
    props = source_pass.get("properties")
    threshold = props.get("alphaThreshold", {}).get("value") if isinstance(props, dict) else None
    if threshold != [0.5]:
        raise SpineMaterialError("source alpha threshold differs from the recognized 0.5 default")
    blend = source_pass.get("blendState")
    blend_targets = blend.get("targets") if isinstance(blend, dict) else None
    if blend_targets != [{"blend": True}]:
        raise SpineMaterialError("source blend declaration differs from the recognized implicit state")
    return {
        "formula": "spine-two-color-v1",
        "sourceDefines": sorted(required),
        "conditionalGammaDecode": has_gamma,
        "conditionalAlphaAtlas": has_alpha_atlas,
        "sourceBlend": "enabled-factors-implicit",
        "sourceAlphaThreshold": 0.5,
        "sourceCullMode": source_pass.get("rasterizerState", {}).get("cullMode"),
        "creator388BuiltinMapping": {
            "USE_TINT": "TWO_COLORED",
            "CC_USE_MODEL": "USE_LOCAL",
            "USE_ALPHA_TEST": "USE_ALPHA_TEST",
            "dualColorEquation": "formula-matches-after-varying-renaming",
            "nativeShaderHash": CREATOR_388_NATIVE_SPINE_SHADER_HASH,
        },
    }


SOURCE_DEFAULT_SPINE_MATERIAL = {
    "status": "resolved_source_engine_default",
    "sourceEngineVersion": "2.4.15",
    "sourcePath": "extensions/spine/Skeleton.js",
    "sourceUrl": "https://raw.githubusercontent.com/cocos/cocos-engine/v2.4.15/extensions/spine/Skeleton.js",
    "sourceSha256": SOURCE_ENGINE_FILE_PINS["extensions/spine/Skeleton.js"],
    "method": "Skeleton._getDefaultMaterial -> cc.Material.getBuiltinMaterial('2d-spine')",
    "targetProfile": "Creator 3.8.8 builtinResMgr.get('default-spine-material')",
}


def _component_occurrences(manifest: dict, material_uuid: str, selected_indices: list[int] | None = None) -> list[dict]:
    rows = _asset_rows(manifest)
    selected = manifest.get("selection") if selected_indices is None else selected_indices
    if not isinstance(selected, list):
        raise SpineMaterialError("source manifest selection is missing")
    result = []
    for locator in selected:
        prefabs = [a for candidates in rows.values() for a in candidates
                   if a.get("kind") == "cc.Prefab" and a.get("index") == locator]
        if len(prefabs) != 1:
            raise SpineMaterialError(f"selected Prefab locator {locator!r} is missing or ambiguous")
        asset = prefabs[0]
        instances = asset.get("document", {}).get("instances", [])
        if not isinstance(instances, list):
            raise SpineMaterialError(f"{asset.get('sourceId')} has no source instances")
        for object_index, obj in enumerate(instances):
            if not isinstance(obj, dict):
                continue
            components: list[tuple[int | None, dict]] = []
            if obj.get("__type__") == "cc.Node":
                components = [(ci, c) for ci, c in enumerate(obj.get("_components", []) or [])
                              if isinstance(c, dict) and c.get("__type__") == "sp.Skeleton"]
            elif obj.get("__type__") == "sp.Skeleton":
                components = [(None, obj)]
            for component_index, component in components:
                refs = component.get("_materials", [])
                if not isinstance(refs, list) or not any(isinstance(ref, dict) and ref.get("__uuid__") == material_uuid for ref in refs):
                    continue
                component_id = (f"{asset['sourceId']}#{object_index}" if component_index is None else
                                f"{asset['sourceId']}#{object_index}/components/{component_index}")
                pma = component.get("premultipliedAlpha")
                tint = component.get("useTint")
                data_ref = component.get("_N$skeletonData")
                skeleton_data_uuid = data_ref.get("__uuid__") if isinstance(data_ref, dict) else None
                result.append({
                    "prefabSourceId": asset["sourceId"], "prefabPath": asset.get("logicalPath"),
                    "prefabLocator": locator, "sourceComponentId": component_id,
                    "inlineComponentIndex": component_index, "materialUuid": material_uuid,
                    "skeletonDataUuid": skeleton_data_uuid,
                    "premultipliedAlpha": {"status": "explicit", "value": pma} if isinstance(pma, bool)
                        else {"status": "not-serialized-default-unresolved"},
                    "useTint": {"status": "explicit", "value": tint} if isinstance(tint, bool)
                        else {"status": "not-serialized-default-unresolved"},
                    "preCacheMode": component.get("_preCacheMode"),
                    "defaultCacheMode": component.get("_defaultCacheMode", component.get("defaultCacheMode")),
                    "enableBatch": component.get("enableBatch"),
                    "sourceMaterialBinding": {"status": "explicit", "sourceMaterialReferenceSourceId": f"gameAsset:{material_uuid}"},
                })
            # Only a missing serialized field uses the source engine default.
            # Explicit null, an empty array, and unknown refs remain distinct and
            # are not silently rewritten to the built-in material.
            if obj.get("__type__") == "cc.Node":
                components = [(ci, c) for ci, c in enumerate(obj.get("_components", []) or [])
                              if isinstance(c, dict) and c.get("__type__") == "sp.Skeleton" and "_materials" not in c]
            elif obj.get("__type__") == "sp.Skeleton" and "_materials" not in obj:
                components = [(None, obj)]
            else:
                components = []
            for component_index, component in components:
                component_id = (f"{asset['sourceId']}#{object_index}" if component_index is None else
                                f"{asset['sourceId']}#{object_index}/components/{component_index}")
                data_ref = component.get("_N$skeletonData")
                skeleton_data_uuid = data_ref.get("__uuid__") if isinstance(data_ref, dict) else None
                result.append({
                    "prefabSourceId": asset["sourceId"], "prefabPath": asset.get("logicalPath"),
                    "prefabLocator": locator, "sourceComponentId": component_id,
                    "inlineComponentIndex": component_index, "materialUuid": None,
                    "skeletonDataUuid": skeleton_data_uuid,
                    "premultipliedAlpha": {"status": "explicit", "value": component["premultipliedAlpha"]}
                        if isinstance(component.get("premultipliedAlpha"), bool)
                        else {"status": "not-serialized-default-unresolved"},
                    "useTint": {"status": "explicit", "value": component["useTint"]}
                        if isinstance(component.get("useTint"), bool)
                        else {"status": "not-serialized-default-unresolved"},
                    "preCacheMode": component.get("_preCacheMode"),
                    "defaultCacheMode": component.get("_defaultCacheMode", component.get("defaultCacheMode")),
                    "enableBatch": component.get("enableBatch"),
                    "sourceMaterialBinding": dict(SOURCE_DEFAULT_SPINE_MATERIAL),
                })
            # Preserve invalid serialized states as explicit blockers. In
            # particular, `null` and `[]` are not the same as an omitted key.
            invalid_components = []
            candidates = ([(ci, c) for ci, c in enumerate(obj.get("_components", []) or [])
                           if isinstance(c, dict) and c.get("__type__") == "sp.Skeleton"]
                          if obj.get("__type__") == "cc.Node" else
                          [(None, obj)] if obj.get("__type__") == "sp.Skeleton" else [])
            for component_index, component in candidates:
                if "_materials" not in component:
                    continue
                refs = component.get("_materials")
                if isinstance(refs, list) and any(isinstance(ref, dict) and ref.get("__uuid__") == material_uuid for ref in refs):
                    continue
                component_id = (f"{asset['sourceId']}#{object_index}" if component_index is None else
                                f"{asset['sourceId']}#{object_index}/components/{component_index}")
                status = "explicit_null" if refs is None else "explicit_empty" if refs == [] else "explicit_unknown_or_unmatched"
                invalid_components.append((component_id, status))
            for component_id, status in invalid_components:
                result.append({"prefabSourceId": asset["sourceId"], "prefabPath": asset.get("logicalPath"),
                               "prefabLocator": locator, "sourceComponentId": component_id,
                               "inlineComponentIndex": None, "materialUuid": None, "skeletonDataUuid": None,
                               "premultipliedAlpha": {"status": "not-serialized-default-unresolved"},
                               "useTint": {"status": "not-serialized-default-unresolved"},
                               "preCacheMode": None, "defaultCacheMode": None, "enableBatch": None,
                               "sourceMaterialBinding": {"status": status}})
    return result


def _selected_spine_material_candidates(manifest: dict, selected_indices: list[int] | None = None) -> dict[str, int]:
    """Count exact material UUID references on selected source Spine components."""
    rows = _asset_rows(manifest)
    selected = manifest.get("selection") if selected_indices is None else selected_indices
    if not isinstance(selected, list):
        raise SpineMaterialError("source manifest selection is missing")
    counts: dict[str, int] = {}
    for locator in selected:
        prefabs = [a for candidates in rows.values() for a in candidates
                   if a.get("kind") == "cc.Prefab" and a.get("index") == locator]
        if len(prefabs) != 1:
            raise SpineMaterialError(f"selected Prefab locator {locator!r} is missing or ambiguous")
        for obj in prefabs[0].get("document", {}).get("instances", []):
            if not isinstance(obj, dict):
                continue
            components = ([c for c in obj.get("_components", []) or []
                           if isinstance(c, dict) and c.get("__type__") == "sp.Skeleton"]
                          if obj.get("__type__") == "cc.Node" else
                          [obj] if obj.get("__type__") == "sp.Skeleton" else [])
            for component in components:
                for ref in component.get("_materials", []) or []:
                    uid = ref.get("__uuid__") if isinstance(ref, dict) else None
                    if isinstance(uid, str) and uid:
                        counts[uid] = counts.get(uid, 0) + 1
    return counts


def _input_receipts(manifest: dict) -> dict[tuple[str, str], dict]:
    return {(row.get("bundle", manifest.get("bundle")), row.get("path")): row
            for row in manifest.get("inputs", []) if isinstance(row, dict)}


def _read_manifest_native(manifest: dict, asset: dict, receipts: dict) -> tuple[bytes, dict]:
    bundle = asset.get("bundle", manifest.get("bundle"))
    relative = asset.get("native")
    roots = manifest.get("sourceRoots")
    if not isinstance(relative, str) or not isinstance(roots, dict) or not isinstance(roots.get(bundle), str):
        raise SpineMaterialError("Spine native binary path or source root is missing")
    try:
        raw = read(inside(Path(roots[bundle]), relative), max_bytes=64 * 1024 * 1024)
    except Exception as exc:
        raise SpineMaterialError(f"cannot read source Spine binary: {exc}") from exc
    receipt = receipts.get((bundle, relative))
    if not isinstance(receipt, dict) or receipt.get("sha256") != _sha(raw) or receipt.get("bytes") != len(raw):
        raise SpineMaterialError("source Spine binary does not match its frozen input receipt")
    return raw, {"status": "verified", "bundle": bundle, "nativePath": relative,
                 "sha256": _sha(raw), "bytes": len(raw)}


def _texture_alpha_atlas(manifest: dict, skeleton_asset: dict, rows: dict[str, list[dict]]) -> dict:
    skeleton = _root(skeleton_asset)
    refs = skeleton.get("textures")
    names = skeleton.get("textureNames")
    if not isinstance(refs, list) or not refs or not isinstance(names, list) or len(refs) != len(names):
        raise SpineMaterialError("selected Spine data has no explicit page texture references")
    result = []
    special = {1024: "RGB_A_PVRTC_2BPPV1", 1025: "RGB_A_PVRTC_4BPPV1", 1026: "RGBA_ETC1"}
    for page_index, (ref, page_name) in enumerate(zip(refs, names)):
        uuid = ref.get("__uuid__") if isinstance(ref, dict) else None
        if not isinstance(uuid, str):
            raise SpineMaterialError("Spine texture reference is not a serialized UUID")
        texture_asset, redirects = _resolve_uuid(rows, skeleton_asset.get("bundle", "gameAsset"), uuid, "cc.Texture2D")
        texture = _root(texture_asset)
        encoded = texture.get("data")
        match = re.match(r"^(\d+)@(\d+),", encoded) if isinstance(encoded, str) else None
        if not match:
            raise SpineMaterialError("source Texture2D format is not explicitly encoded")
        format_id = int(match.group(2))
        format_names = {34: "RGBA_ASTC_6x6"}
        is_alpha_atlas = True if format_id in special else False if 0 <= format_id <= 43 else None
        if is_alpha_atlas is None:
            raise SpineMaterialError(f"source Texture2D format {format_id} is outside the pinned Cocos pixel-format table")
        result.append({"pageIndex": page_index, "atlasPage": page_name,
                       "sourceId": texture_asset["sourceId"], "native": texture_asset.get("native"),
                       "serializedFormatId": format_id, "serializedFormatName": format_names.get(format_id),
                       "alphaAtlas": is_alpha_atlas,
                       "alphaAtlasFormat": special.get(format_id), "redirectChain": redirects})
    flags = {row["alphaAtlas"] for row in result}
    if len(flags) != 1:
        raise SpineMaterialError("Spine data pages mix alpha-atlas and ordinary texture formats")
    return {"status": "source-format-proven", "alphaAtlas": flags.pop(), "textures": result}


def _runtime_variants(manifest: dict, occurrences: list[dict]) -> dict:
    rows = _asset_rows(manifest)
    receipts = _input_receipts(manifest)
    result = []
    for occurrence in occurrences:
        row = {"sourceComponentId": occurrence["sourceComponentId"],
               "materialUuid": occurrence.get("materialUuid"),
               "sourceMaterialBinding": occurrence.get("sourceMaterialBinding", {"status": "explicit"}),
               "premultipliedAlpha": occurrence["premultipliedAlpha"],
               "useTint": occurrence["useTint"], "enableBatch": occurrence["enableBatch"]}
        pma = occurrence["premultipliedAlpha"]
        row["sourcePmaEffective"] = pma["value"] if pma.get("status") == "explicit" else True
        tint = occurrence["useTint"]
        row["sourceUseTintPropertyEffective"] = tint["value"] if tint.get("status") == "explicit" else False
        batch = occurrence["enableBatch"]
        row["sourceEnableBatchEffective"] = batch if isinstance(batch, bool) else False
        pre_cache = occurrence.get("preCacheMode")
        cache_mode = occurrence.get("defaultCacheMode")
        if cache_mode is None:
            cache_mode = 0
        row["sourceCacheMode"] = {"serializedPreCacheMode": pre_cache,
                                   "serializedDefaultCacheMode": occurrence.get("defaultCacheMode"),
                                   "effectiveDefaultCacheMode": cache_mode,
                                   "status": "realtime" if cache_mode == 0 else "cached" if cache_mode in (1, 2) else "unrecognized"}
        row["sourceUseTintDefine"] = row["sourceUseTintPropertyEffective"] or (
            row["sourceCacheMode"]["status"] == "cached")
        row["sourceUseModelDefine"] = not row["sourceEnableBatchEffective"]
        sid = occurrence.get("skeletonDataUuid")
        if sid is None:
            row.update(skeletonData={"status": "not-serialized"},
                       textures={"status": "no-serialized-skeleton-data", "alphaAtlas": None},
                       blendModes={"status": "no-serialized-skeleton-data", "counts": {}})
            result.append(row)
            continue
        prefab_bundle = occurrence["prefabSourceId"].split(":", 1)[0]
        try:
            skeleton_asset, redirects = _resolve_uuid(rows, prefab_bundle, sid, "sp.SkeletonData")
            raw, receipt = _read_manifest_native(manifest, skeleton_asset, receipts)
            blend = _binary_slot_blend_modes(raw)
            textures = _texture_alpha_atlas(manifest, skeleton_asset, rows)
            row.update(skeletonData={"status": "verified", "sourceId": skeleton_asset["sourceId"],
                                     "redirectChain": redirects, "receipt": receipt,
                                     "spineVersion": blend["spineVersion"]},
                       textures=textures,
                       blendModes={"status": "binary-prefix-parsed", **blend})
        except SpineMaterialError as exc:
            row.update(skeletonData={"status": "unresolved", "message": str(exc)},
                       textures={"status": "unresolved", "alphaAtlas": None},
                       blendModes={"status": "unresolved", "counts": {}})
        result.append(row)
    gamma = {"status": "source-engine-default", "value": False,
             "evidence": ["Cocos 2.4.15 effect-parser initializes boolean defines from enums2default.boolean=false",
                          "Skeleton.js and spine-assembler.js set USE_TINT and CC_USE_MODEL but never INPUT_IS_GAMMA"]}
    return {"sourceEngine": "cocos-engine-v2.4.15",
            "engineFileSha256": SOURCE_ENGINE_FILE_PINS,
            "defaults": {"premultipliedAlpha": True, "useTint": False, "enableBatch": False,
                         "defaultCacheMode": 0, "booleanEffectDefine": False,
                         "creator38NativeEffectSha256": CREATOR_388_EFFECT_SHA256,
                         "creator38NativeShaderHash": CREATOR_388_NATIVE_SPINE_SHADER_HASH},
            "inputGamma": gamma, "components": result}


def _ir_check(ir: dict, occurrences: list[dict], material_source_id: str,
              normalized_selection: set[int] | None = None) -> dict:
    components = ir.get("components")
    if not isinstance(components, list):
        raise SpineMaterialError("normalized IR has no component list")
    actual = {c.get("sourceId"): c for c in components if isinstance(c, dict)}
    ids = [row["sourceComponentId"] for row in occurrences]
    missing, source_manifest_only, mismatched = [], [], []
    occurrence_by_id = {row["sourceComponentId"]: row for row in occurrences}
    for sid in ids:
        component = actual.get(sid)
        if not component:
            locator = occurrence_by_id[sid].get("prefabLocator")
            if normalized_selection is not None and locator not in normalized_selection:
                source_manifest_only.append(sid)
            else:
                missing.append(sid)
            continue
        binding = next(row.get("sourceMaterialBinding", {}) for row in occurrences if row["sourceComponentId"] == sid)
        if component.get("type") != "sp.Skeleton":
            mismatched.append(sid)
        elif binding.get("status") == "explicit" and material_source_id not in component.get("materials", []):
            mismatched.append(sid)
        elif binding.get("status") == "resolved_source_engine_default" and component.get("materials", []):
            mismatched.append(sid)
        elif binding.get("status") not in {"explicit", "resolved_source_engine_default"}:
            mismatched.append(sid)
    return {"sourceComponentCount": len(ids), "matchedComponentCount": len(ids) - len(missing) - len(mismatched) - len(source_manifest_only),
            "sourceManifestOnlyComponentCount": len(source_manifest_only),
            "sourceManifestOnlySourceIds": source_manifest_only,
            "missingSourceIds": missing, "mismatchedSourceIds": mismatched,
            "exactMatch": not missing and not mismatched}


def inspect_spine_materials(manifest_path: str | Path, ir_path: str | Path,
                            app_config_path: str | Path | None = None,
                            runtime_entry_path: str | Path | None = None,
                            selected_prefab_indices: list[int] | None = None) -> dict:
    """Inspect the exact source material/effect closure and component references."""
    manifest_path, ir_path = Path(manifest_path), Path(ir_path)
    manifest_raw, ir_raw = manifest_path.read_bytes(), ir_path.read_bytes()
    manifest, ir = json.loads(manifest_raw), json.loads(ir_raw)
    if manifest.get("sourceVersion") != "2.4.15":
        raise SpineMaterialError("source engine version is not the pinned Cocos 2.4.15 profile")
    rows = _asset_rows(manifest)
    # Discover the candidate from selected component references.  No private
    # source UUID or asset name is itself a capability predicate.
    selected_indices = manifest.get("selection") if selected_prefab_indices is None else selected_prefab_indices
    if (not isinstance(selected_indices, list) or not selected_indices
            or any(type(index) is not int for index in selected_indices)
            or len(set(selected_indices)) != len(selected_indices)):
        raise SpineMaterialError("selected Prefab locators must be a nonempty, duplicate-free integer list")
    known_prefab_indices = {row.get("index") for candidates in rows.values() for row in candidates
                            if row.get("kind") == "cc.Prefab"}
    if not set(selected_indices) <= known_prefab_indices:
        raise SpineMaterialError("selected Prefab locator is not present in the pinned source manifest")
    normalized_selection = set(manifest.get("selection", []))
    candidate_counts = _selected_spine_material_candidates(manifest, selected_indices)
    eligible = []
    candidate_errors: list[SpineMaterialError] = []
    for candidate_uuid, count in candidate_counts.items():
        try:
            asset, redirects = _resolve_uuid(rows, "gameAsset", candidate_uuid, "cc.Material")
            root = _root(asset)
            effect_ref = root.get("_effectAsset")
            effect_uuid = effect_ref.get("__uuid__") if isinstance(effect_ref, dict) else None
            if not isinstance(effect_uuid, str):
                continue
            effect_asset, effect_redirects = _resolve_uuid(rows, asset.get("bundle", "gameAsset"), effect_uuid, "cc.EffectAsset")
            effect_root = _root(effect_asset)
            shader, stage_hashes = _program(effect_root)
            eligible.append((count, candidate_uuid, asset, redirects, effect_uuid,
                             effect_asset, effect_redirects, effect_root, shader, stage_hashes))
        except SpineMaterialError as exc:
            candidate_errors.append(exc)
            continue
    if not eligible:
        for exc in candidate_errors:
            if "exact pinned source profile" in str(exc):
                raise exc
        raise SpineMaterialError("selected Spine components reference no Material with the exact pinned builtin Spine Effect")
    top_count = max(row[0] for row in eligible)
    top = [row for row in eligible if row[0] == top_count]
    if len(top) != 1:
        raise SpineMaterialError("selected Spine material candidate is ambiguous by source reference count")
    _, material_uuid, material_asset, redirect_chain, effect_uuid, effect_asset, effect_redirects, effect, shader, hashes = top[0]
    material = _root(material_asset)
    material_info = _material(effect_uuid, material)
    semantics = _source_semantics(effect, shader)
    occurrences = _component_occurrences(manifest, material_uuid, selected_indices)
    if not occurrences:
        raise SpineMaterialError("selected Prefabs have no Spine component referencing the resolved Material")
    reference_material_source_id = f"gameAsset:{material_uuid}"
    ir_result = _ir_check(ir, occurrences, reference_material_source_id, normalized_selection)
    variants = _runtime_variants(manifest, occurrences)
    creator_issues = []
    unity_issues = []
    for variant in variants["components"]:
        material_state = next(row.get("sourceMaterialBinding", {}) for row in occurrences
                              if row["sourceComponentId"] == variant["sourceComponentId"])
        if material_state.get("status") not in {"explicit", "resolved_source_engine_default"}:
            creator_issues.append({"code": "CREATOR_SPINE_MATERIAL_SOURCE_STATE_UNSUPPORTED",
                                   "componentSourceId": variant["sourceComponentId"],
                                   "message": "Serialized _materials is null, empty, or does not resolve to the pinned Spine material."})
        if variant["sourceCacheMode"]["status"] == "unrecognized":
            creator_issues.append({"code": "CREATOR_SPINE_CACHE_MODE_UNKNOWN",
                                   "componentSourceId": variant["sourceComponentId"],
                                   "message": "Source cache mode is outside the pinned Spine 2.4 runtime enum."})
        texture_info = variant["textures"]
        if texture_info.get("alphaAtlas") is True:
            creator_issues.append({"code": "CREATOR_ALPHA_ATLAS_VARIANT_UNMATCHED",
                                   "componentSourceId": variant["sourceComponentId"],
                                   "message": "Source texture is a split-alpha atlas; Creator 3.8.8 builtin-spine samples ordinary RGBA."})
        elif texture_info.get("alphaAtlas") is None and texture_info.get("status") not in (
                "no-serialized-skeleton-data", "unresolved"):
            creator_issues.append({"code": "CREATOR_TEXTURE_FORMAT_UNKNOWN",
                                   "componentSourceId": variant["sourceComponentId"],
                                   "message": "Source Texture2D format did not establish the alpha-atlas define."})
        modes = variant["blendModes"].get("blendModeCounts", {})
        if modes.get("screen", 0) and not variant["sourcePmaEffective"]:
            creator_issues.append({"code": "CREATOR_SCREEN_BLEND_FACTOR_MISMATCH",
                                   "componentSourceId": variant["sourceComponentId"],
                                   "message": "Cocos 2.4.15 always uses ONE for Screen source blend; Creator 3.8.8 uses SRC_ALPHA when PMA is false."})
        if variant["blendModes"].get("status") == "unresolved":
            creator_issues.append({"code": "CREATOR_SOURCE_BLEND_MODES_UNREADABLE",
                                   "componentSourceId": variant["sourceComponentId"],
                                   "message": variant["blendModes"].get("message", "Spine slot blend modes could not be read.")})
        if variant["sourceUseTintDefine"]:
            unity_issues.append({"code": "UNITY_TWO_COLOR_SHADER_VARIANT_UNSUPPORTED",
                                 "componentSourceId": variant["sourceComponentId"],
                                 "message": "The source-authored Unity one-color profile does not cover a TWO_COLORED vertex stream."})
        if variant["textures"].get("alphaAtlas") is True:
            unity_issues.append({"code": "UNITY_ALPHA_ATLAS_SHADER_VARIANT_UNSUPPORTED",
                                 "componentSourceId": variant["sourceComponentId"],
                                 "message": "The source-authored Unity profile requires ordinary RGBA atlas pages."})

    app_config = None
    if app_config_path is not None:
        config_raw = Path(app_config_path).read_bytes()
        config_value = json.loads(config_raw)
        app_config = {"path": str(app_config_path), "sha256": _sha(config_raw),
                      "bytes": len(config_raw), "renderSettings": {key: config_value[key] for key in
                          ("renderMode", "renderType", "colorSpace", "gamma", "colorSpaceMode") if key in config_value},
                      "status": "no-shader-render-settings" if not any(key in config_value for key in
                          ("renderMode", "renderType", "colorSpace", "gamma", "colorSpaceMode")) else "settings-present"}
    runtime_entry = None
    if runtime_entry_path is not None:
        entry_raw = Path(runtime_entry_path).read_bytes()
        text = entry_raw.decode("utf-8", errors="ignore")
        flags = {}
        for name in ("CC_NATIVERENDERER", "CC_JSB", "CC_BUILD"):
            match = re.search(rf"\b{name}\s*=\s*(!?)([01])", text)
            flags[name] = (not bool(int(match.group(2))) if match and match.group(1) else
                           bool(int(match.group(2))) if match else None)
        runtime_entry = {"path": str(runtime_entry_path), "sha256": _sha(entry_raw),
                         "bytes": len(entry_raw), "compiledRuntimeFlags": flags}

    blockers = list(creator_issues)
    if not ir_result["exactMatch"]:
        blockers.append({"code": "CREATOR_IR_COMPONENT_IDENTITY_MISMATCH",
                         "message": "Selected source Spine material occurrences do not match the normalized IR."})
    creator_status = ("source-semantics-exact-builtin-spine" if not creator_issues and ir_result["exactMatch"]
                      else "blocked-by-source-variant-mismatch")
    unity_per_component = []
    for row in variants["components"]:
        counts = row["blendModes"].get("blendModeCounts", {})
        if row["skeletonData"]["status"] != "verified":
            unity_per_component.append({"sourceComponentId": row["sourceComponentId"],
                                        "status": "no-serialized-skeleton-data-no-render-material-closure"})
            continue
        pma_src = 1 if row["sourcePmaEffective"] else 5
        source_blends = {"normal": (pma_src, 10), "additive": (pma_src, 1),
                         "multiply": (2, 10), "screen": (1, 6)}
        material_variants = []
        for mode, (src, dst) in source_blends.items():
            if counts.get(mode, 0):
                material_variants.append({"blendMode": mode, "sourceBlendFactor": src,
                                          "destinationBlendFactor": dst, "sourceSlotCount": counts[mode]})
        unity_per_component.append({"sourceComponentId": row["sourceComponentId"], "status": "profile-materials-defined",
                                    "shader": "Monkey/SpineSourceProfile/Colored",
                                    "shaderSourceSha256": UNITY_PROFILE_SHADER_SHA256,
                                    "pmaVertexColors": row["sourcePmaEffective"],
                                    "sourceAtlasPages": [{"pageIndex": tex["pageIndex"], "pageName": tex["atlasPage"],
                                                          "sourceTextureSourceId": tex["sourceId"],
                                                          "sourceNative": tex.get("native"),
                                                          "materialIdentitySeeds": {
                                                              mode["blendMode"]: tex["sourceId"] + "/spine-source-material/" + mode["blendMode"]
                                                              for mode in material_variants}}
                                                         for tex in row["textures"].get("textures", [])],
                                    "textureSourceFormats": [x.get("serializedFormatName") for x in row["textures"].get("textures", [])],
                                    "variants": material_variants,
                                    "blendModeMaterials": {"applyAdditiveMaterial": bool(counts.get("additive", 0)),
                                                           "mapping": "normal/additive material per source Atlas page"}})
    unity_blockers = []
    if unity_issues:
        unity_blockers.extend(unity_issues)
    unity_blockers.extend([
        {"code": "UNITY_PACKAGE_NATIVE_BINDING_NOT_READ_BACK",
         "message": "The official Spine 3.8 source is pinned, but the project-local package revision, generated atlas materials and native page/slot references have not been imported or read back."},
        {"code": "UNITY_SPINE_PAGE_MATERIAL_MAP_REQUIRED",
         "message": "Bind each source Atlas page to its normal material and, where present, the source additive/multiply/screen material through the Spine 3.8 blend-mode material API."},
    ])
    binding = {
        "status": creator_status,
        "creator38": {
            "strategy": "explicit-native-builtin-spine-material-reference",
            "targetMaterialUuid": "default-spine-material",
            "effect": "builtin-spine",
            "effectSourceSha256": CREATOR_388_EFFECT_SHA256,
            "nativeShaderHash": variants["defaults"]["creator38NativeShaderHash"],
            "sourceVariantConditions": {"INPUT_IS_GAMMA": False,
                                        "CC_USE_ALPHA_ATLAS_texture": False,
                                        "USE_ALPHA_TEST": False,
                                        "useTintPerComponent": "runtimeVariantEvidence.components[].sourceUseTintDefine",
                                        "useModelPerComponent": "runtimeVariantEvidence.components[].sourceUseModelDefine"},
            "macroMapping": semantics["creator388BuiltinMapping"],
            "perComponent": [{"sourceComponentId": row["sourceComponentId"],
                              "sourceMaterialReferenceSourceId": row.get("sourceMaterialBinding", {}).get("sourceMaterialReferenceSourceId"),
                              "sourceMaterialSourceId": material_asset["sourceId"] if row.get("sourceMaterialBinding", {}).get("status") == "explicit" else None,
                              "targetMaterialUuid": "default-spine-material",
                              "sourceMaterialBinding": next(occurrence["sourceMaterialBinding"] for occurrence in occurrences
                                                             if occurrence["sourceComponentId"] == row["sourceComponentId"]),
                              "premultipliedAlpha": row["sourcePmaEffective"],
                              "useTint": row["sourceUseTintDefine"],
                              "enableBatch": row["sourceEnableBatchEffective"],
                              "sourceCacheMode": row["sourceCacheMode"],
                              "sourceSkeletonDataStatus": row["skeletonData"]["status"],
                              "sourceBlendModeCounts": row["blendModes"].get("blendModeCounts", {}),
                              "runtimeMaterialStrategy": "Creator Spine runtime creates per-slot MaterialInstance over builtin-spine and selects blend factors from component PMA"}
                             for row in variants["components"]],
            "requiredReadback": ["customMaterial.effectAsset=builtin-spine", "material UUID=default-spine-material",
                                 "nativeShaderHash=3890043391", "per-component PMA/tint/cache settings",
                                 "per-slot blend state where source contains Screen"],
            "nativeReadbackStatus": "not_run",
            "helperFile": {"path": str(TARGET_DIR / "CreatorSpineMaterialBindings.js"),
                           "sha256": CREATOR_BINDING_HELPER_SHA256},
        },
        "unity": {
            "strategy": "source-authored-one-color-shader-and-per-page-spine-material-variants",
            "referenceProfile": UNITY_SPINE38_REFERENCE,
            "shaderSourceSha256": UNITY_PROFILE_SHADER_SHA256,
            "helperFile": {"path": str(TARGET_DIR / "UnitySpineMaterialBindings.cs"),
                           "sha256": UNITY_BINDING_HELPER_SHA256},
            "perComponent": unity_per_component,
            "status": "shader-candidate-ready-native-runtime-binding-pending" if not unity_issues
                else "blocked-by-source-variant-mismatch",
            "sourceBlendModes": "see per-component pinned Spine 3.8 binary prefix",
            "requiredEvidence": ["installed Unity Spine package exact commit/version", "source-compatible straight-alpha shader or exact per-slot material map",
                                 "blend/PMA readback", "native Material shader readback"],
        },
    }
    return {
        "profile": PROFILE,
        "source": {
            "manifestSha256": _sha(manifest_raw), "normalizedIrSha256": _sha(ir_raw),
            "materialReferenceSourceId": reference_material_source_id,
            "materialSourceId": material_asset["sourceId"], "materialName": material_info["name"],
            "materialOverrides": material_info["techniqueData"], "materialRedirectChain": redirect_chain,
            "effectSourceId": effect_asset["sourceId"], "effectName": effect.get("_name"),
            "effectRedirectChain": effect_redirects, "program": PROGRAM,
            "stageCanonicalSha256": hashes, "programCanonicalSha256": _sha(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()),
            "semantics": semantics, "runtimeVariantEvidence": variants,
            "unitySpine38Reference": UNITY_SPINE38_REFERENCE,
            "unityProfileShaderSha256": UNITY_PROFILE_SHADER_SHA256,
            "projectRenderConfig": app_config, "compiledRuntimeEntry": runtime_entry,
            "prefabOccurrences": occurrences,
            "irComponentCheck": ir_result,
        },
        "binding": binding,
        "blockers": blockers,
        "unityBlockers": unity_blockers,
        "nativeCompilation": "not_run",
        "nativeEditorImport": "not_run",
        "runtimeRendering": "not_run",
    }


def plan_spine_materials(manifest_path: str | Path, ir_path: str | Path,
                         expected_manifest_sha256: str, expected_ir_sha256: str,
                         app_config_path: str | Path | None = None,
                         runtime_entry_path: str | Path | None = None,
                         selected_prefab_indices: list[int] | None = None) -> dict:
    """Create an explicit, non-emitting contract for parent plan integration."""
    result = inspect_spine_materials(manifest_path, ir_path, app_config_path, runtime_entry_path, selected_prefab_indices)
    if result["source"]["manifestSha256"] != expected_manifest_sha256 or result["source"]["normalizedIrSha256"] != expected_ir_sha256:
        raise SpineMaterialError("explicit source manifest/IR pin mismatch")
    return {
        "schema": "monkey-spine-material-contract/1",
        "profile": result["profile"], "spec": result["binding"],
        "pins": {"sourceManifestSha256": expected_manifest_sha256, "normalizedIrSha256": expected_ir_sha256,
                 "materialReferenceSourceId": result["source"]["materialReferenceSourceId"],
                 "materialSourceId": result["source"]["materialSourceId"],
                 "effectSourceId": result["source"]["effectSourceId"],
                 "effectProgramCanonicalSha256": result["source"]["programCanonicalSha256"]},
        "sourceComponentCount": result["source"]["irComponentCheck"]["sourceComponentCount"],
        "creatorBindingStatus": result["binding"]["status"],
        "irComponentCheck": result["source"]["irComponentCheck"],
        "blockers": result["blockers"],
        "unityBlockers": result["unityBlockers"],
        "ownedFiles": [],
        "status": "creator-builtin-and-unity-shader-candidates-ready-native-bindings-pending",
        "nativeCompilation": "not_run", "nativeEditorImport": "not_run",
    }
