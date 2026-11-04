import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monkey import prefab_spine_materials as spine_materials
from monkey.prefab_spine_materials import SpineMaterialError, inspect_spine_materials, plan_spine_materials


FORMULA = "((texColor.a - 1.0) * v_dark.a + 1.0 - texColor.rgb) * v_dark.rgb + texColor.rgb * v_light.rgb"


def _asset(source_id, kind, index, document, *, bundle="gameAsset", refs=None, redirect=None):
    row = {"sourceId": source_id, "kind": kind, "index": index, "bundle": bundle,
           "logicalPath": kind, "references": refs or [], "document": document}
    if redirect:
        row.update(redirectTarget=redirect, redirectBundle=redirect.split(":", 1)[0])
    return row


def _varint(value):
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _string(value):
    if value is None:
        return b"\x00"
    raw = value.encode("utf-8")
    return _varint(len(raw) + 1) + raw


def _spine38_binary(blend_mode=0):
    out = bytearray(_string("synthetic-hash") + _string("3.8.99"))
    out += b"".join(__import__("struct").pack(">f", 0.0) for _ in range(4))
    out += b"\x00"  # nonessential
    out += _varint(0)  # string table
    out += _varint(1) + _string("root")  # bones
    out += b"".join(__import__("struct").pack(">f", value) for value in (0, 0, 0, 1, 1, 0, 0, 0))
    out += _varint(0) + b"\x00"  # transform mode, skinRequired
    out += _varint(1) + _string("slot") + _varint(0)
    out += __import__("struct").pack(">ii", -1, -1)
    out += _varint(0) + _varint(blend_mode)
    return bytes(out)


def _fixture(root: Path, *, changed_formula=False, extra_override=False, blend_mode=0):
    root.mkdir(parents=True, exist_ok=True)
    vert = "void main () { gl_Position = vec4(1.0); }"
    frag = f"void main () {{ vec4 texColor = vec4(1.0); vec4 v_dark = vec4(0.0); vec4 v_light = vec4(1.0); vec4 outColor; outColor.rgb = {FORMULA}; }}"
    if changed_formula:
        frag = frag.replace("texColor.rgb * v_light.rgb", "texColor.rgb * v_dark.rgb")
    effect = {
        "__type__": "cc.EffectAsset", "_name": "arbitrary-effect-name",
        "shaders": [{"name": spine_materials.PROGRAM,
                     "glsl1": {"vert": vert, "frag": frag},
                     "glsl3": {"vert": vert, "frag": frag},
                     "defines": [{"name": name, "type": "boolean"} for name in
                                 ("USE_TINT", "CC_USE_MODEL", "USE_ALPHA_TEST", "CC_USE_ALPHA_ATLAS_texture", "INPUT_IS_GAMMA")]}],
        "techniques": [{"passes": [{"program": spine_materials.PROGRAM,
                                      "properties": {"alphaThreshold": {"value": [0.5]}},
                                      "blendState": {"targets": [{"blend": True}]},
                                      "rasterizerState": {"cullMode": 0}}]}],
    }
    material = {"__type__": "cc.Material", "_name": "unrelated-name",
                "_effectAsset": {"__uuid__": "effect-uuid"}, "_techniqueData": {}}
    if extra_override:
        material["_techniqueData"] = {"0": {"defines": {"USE_TINT": True}}}
    skeleton_raw = _spine38_binary(blend_mode)
    native_rel = "native/skeleton.bin"
    skeleton_root = root / "source-spine"
    (skeleton_root / "native").mkdir(parents=True, exist_ok=True)
    (skeleton_root / native_rel).write_bytes(skeleton_raw)
    component = {"__type__": "sp.Skeleton", "_materials": [{"__uuid__": "material-uuid"}],
                 "_N$skeletonData": {"__uuid__": "skeleton-uuid"}, "_preCacheMode": 0,
                 "premultipliedAlpha": False}
    prefab = {"__type__": "cc.Prefab", "_name": "synthetic"}
    assets = [
        _asset("gameAsset:material-uuid", "redirect", 2, {}, redirect="internal:material-uuid"),
        _asset("internal:material-uuid", "cc.Material", 2,
               {"root": 0, "instances": [material]}, bundle="internal", refs=["effect-uuid"]),
        _asset("internal:effect-uuid", "cc.EffectAsset", 3,
               {"root": 0, "instances": [effect]}, bundle="internal"),
        _asset("gameAsset:skeleton-uuid", "redirect", 4, {}, redirect="spineAsset:skeleton-uuid"),
        _asset("spineAsset:skeleton-uuid", "sp.SkeletonData", 4,
               {"root": 0, "instances": [{"__type__": "sp.SkeletonData", "textureNames": ["atlas.png"],
                                            "textures": [{"__uuid__": "texture-uuid"}]}]},
               bundle="spineAsset"),
        _asset("spineAsset:texture-uuid", "cc.Texture2D", 5,
               {"root": 0, "instances": [{"__type__": "cc.Texture2D", "data": "7@34,9729,9729,33071,33071,0,0,0"}]},
               bundle="spineAsset"),
        _asset("gameAsset:prefab-uuid", "cc.Prefab", 1,
               {"root": 0, "instances": [prefab, {"__type__": "cc.Node", "_components": [component]}]},
               refs=["material-uuid"]),
    ]
    assets[4]["native"] = native_rel
    manifest = {"selection": [1], "assets": assets,
                "sourceRoots": {"spineAsset": str(skeleton_root)},
                "inputs": [{"bundle": "spineAsset", "path": native_rel,
                            "bytes": len(skeleton_raw), "sha256": hashlib.sha256(skeleton_raw).hexdigest()}],
                "sourceVersion": "2.4.15"}
    ir = {"components": [{"type": "sp.Skeleton", "sourceId": "gameAsset:prefab-uuid#1/components/0",
                          "materials": ["gameAsset:material-uuid"]}]}
    manifest_path = root / "source-manifest.json"
    ir_path = root / "ir.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    ir_path.write_text(json.dumps(ir), encoding="utf-8")
    hashes = {}
    for lang in ("glsl1", "glsl3"):
        for stage in ("vert", "frag"):
            hashes[f"{lang}.{stage}"] = spine_materials._stage_sha(effect["shaders"][0][lang][stage])
    return manifest_path, ir_path, hashes


class PrefabSpineMaterialTests(unittest.TestCase):
    def setUp(self):
        self._inside = patch.object(spine_materials, "inside",
                                    side_effect=lambda root, relative: Path(root) / relative)
        self._read = patch.object(spine_materials, "read",
                                  side_effect=lambda path, **kwargs: Path(path).read_bytes())
        self._inside.start()
        self._read.start()

    def tearDown(self):
        self._inside.stop()
        self._read.stop()

    def test_exact_source_profile_resolves_creator_builtin_variants_explicitly(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, ir, hashes = _fixture(Path(temp))
            with patch.object(spine_materials, "SPINE_EFFECT_STAGE_HASHES", hashes):
                result = inspect_spine_materials(manifest, ir)
            self.assertEqual(result["source"]["materialSourceId"], "internal:material-uuid")
            self.assertEqual(result["source"]["materialReferenceSourceId"], "gameAsset:material-uuid")
            self.assertEqual(result["source"]["irComponentCheck"]["exactMatch"], True)
            self.assertEqual(result["source"]["semantics"]["creator388BuiltinMapping"]["USE_TINT"], "TWO_COLORED")
            self.assertEqual(result["binding"]["status"], "source-semantics-exact-builtin-spine")
            self.assertEqual(result["nativeCompilation"], "not_run")
            self.assertEqual(result["blockers"], [])
            self.assertEqual(result["source"]["runtimeVariantEvidence"]["components"][0]["textures"]["alphaAtlas"], False)
            self.assertEqual(result["source"]["runtimeVariantEvidence"]["components"][0]["sourcePmaEffective"], False)
            self.assertFalse(result["source"]["runtimeVariantEvidence"]["components"][0]["sourceUseTintDefine"])
            self.assertTrue(result["source"]["runtimeVariantEvidence"]["components"][0]["sourceUseModelDefine"])
            self.assertEqual(result["binding"]["creator38"]["targetMaterialUuid"], "default-spine-material")
            self.assertEqual(result["binding"]["creator38"]["nativeShaderHash"], 3890043391)
            component_binding = result["binding"]["creator38"]["perComponent"][0]
            self.assertEqual(component_binding["sourceMaterialReferenceSourceId"], "gameAsset:material-uuid")
            self.assertEqual(component_binding["sourceMaterialSourceId"], "internal:material-uuid")

    def test_omitted_materials_uses_pinned_source_engine_default(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, ir, hashes = _fixture(Path(temp))
            manifest_data = json.loads(manifest.read_text())
            ir_data = json.loads(ir.read_text())
            component = manifest_data["assets"][-1]["document"]["instances"][1]["_components"][0]
            clone = json.loads(json.dumps(component))
            manifest_data["assets"][-1]["document"]["instances"][1]["_components"].append(clone)
            ir_data["components"].append({"type": "sp.Skeleton", "sourceId": "gameAsset:prefab-uuid#1/components/1",
                                          "materials": ["gameAsset:material-uuid"]})
            component.pop("_materials")
            ir_data["components"][0]["materials"] = []
            manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
            ir.write_text(json.dumps(ir_data), encoding="utf-8")
            with patch.object(spine_materials, "SPINE_EFFECT_STAGE_HASHES", hashes):
                result = inspect_spine_materials(manifest, ir)
            binding = next(row for row in result["binding"]["creator38"]["perComponent"]
                           if row["sourceComponentId"].endswith("/components/0"))
            self.assertEqual(binding["sourceMaterialBinding"]["status"], "resolved_source_engine_default")
            self.assertIsNone(binding["sourceMaterialReferenceSourceId"])
            self.assertIsNone(binding["sourceMaterialSourceId"])
            self.assertEqual(binding["sourceMaterialBinding"]["sourcePath"], "extensions/spine/Skeleton.js")
            self.assertTrue(result["source"]["irComponentCheck"]["exactMatch"])

    def test_dependency_prefab_rows_are_source_pinned_without_claiming_ir_presence(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, ir, hashes = _fixture(Path(temp))
            manifest_data = json.loads(manifest.read_text())
            prefab = json.loads(json.dumps(manifest_data["assets"][-1]))
            prefab.update(sourceId="gameAsset:dependency-prefab", index=2, key="dependency-prefab")
            prefab["document"]["instances"][1]["_components"][0]["_materials"] = [{"__uuid__": "material-uuid"}]
            manifest_data["assets"].append(prefab)
            manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
            with patch.object(spine_materials, "SPINE_EFFECT_STAGE_HASHES", hashes):
                result = inspect_spine_materials(manifest, ir, selected_prefab_indices=[1, 2])
            check = result["source"]["irComponentCheck"]
            self.assertEqual(check["sourceComponentCount"], 2)
            self.assertEqual(check["matchedComponentCount"], 1)
            self.assertEqual(check["sourceManifestOnlyComponentCount"], 1)
            self.assertTrue(check["exactMatch"])

    def test_explicit_null_or_empty_materials_are_not_rewritten_to_default(self):
        for invalid in (None, [], [{"__uuid__": "unknown-material-uuid"}]):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as temp:
                manifest, ir, hashes = _fixture(Path(temp))
                manifest_data = json.loads(manifest.read_text())
                ir_data = json.loads(ir.read_text())
                component = manifest_data["assets"][-1]["document"]["instances"][1]["_components"][0]
                clone = json.loads(json.dumps(component))
                manifest_data["assets"][-1]["document"]["instances"][1]["_components"].append(clone)
                ir_data["components"].append({"type": "sp.Skeleton", "sourceId": "gameAsset:prefab-uuid#1/components/1",
                                              "materials": ["gameAsset:material-uuid"]})
                component["_materials"] = invalid
                ir_data["components"][0]["materials"] = []
                manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
                ir.write_text(json.dumps(ir_data), encoding="utf-8")
                with patch.object(spine_materials, "SPINE_EFFECT_STAGE_HASHES", hashes):
                    result = inspect_spine_materials(manifest, ir)
                row = next(row for row in result["binding"]["creator38"]["perComponent"]
                           if row["sourceComponentId"].endswith("/components/0"))
                expected_state = ("explicit_null" if invalid is None else "explicit_empty"
                                  if invalid == [] else "explicit_unknown_or_unmatched")
                self.assertEqual(row["sourceMaterialBinding"]["status"], expected_state)
                self.assertEqual(result["binding"]["status"], "blocked-by-source-variant-mismatch")
                self.assertFalse(result["source"]["irComponentCheck"]["exactMatch"])

    def test_same_effect_name_with_changed_formula_fails_exact_stage_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline, baseline_ir, hashes = _fixture(root / "baseline")
            changed, changed_ir, _ = _fixture(root / "changed", changed_formula=True)
            with patch.object(spine_materials, "SPINE_EFFECT_STAGE_HASHES", hashes):
                with self.assertRaisesRegex(SpineMaterialError, "exact pinned source profile"):
                    inspect_spine_materials(changed, changed_ir)

    def test_rejects_material_override_and_unmatched_ir_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, ir, hashes = _fixture(root, extra_override=True)
            with patch.object(spine_materials, "SPINE_EFFECT_STAGE_HASHES", hashes):
                with self.assertRaisesRegex(SpineMaterialError, "serialized overrides"):
                    inspect_spine_materials(manifest, ir)
            manifest, ir, hashes = _fixture(root / "ir-mismatch")
            payload = json.loads(ir.read_text())
            payload["components"][0]["materials"] = []
            ir.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(spine_materials, "SPINE_EFFECT_STAGE_HASHES", hashes):
                result = inspect_spine_materials(manifest, ir)
            self.assertFalse(result["source"]["irComponentCheck"]["exactMatch"])

    def test_screen_mode_with_straight_alpha_is_rejected_due_runtime_blend_difference(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, ir, hashes = _fixture(Path(temp), blend_mode=3)
            with patch.object(spine_materials, "SPINE_EFFECT_STAGE_HASHES", hashes):
                result = inspect_spine_materials(manifest, ir)
            self.assertEqual(result["binding"]["status"], "blocked-by-source-variant-mismatch")
            self.assertIn("CREATOR_SCREEN_BLEND_FACTOR_MISMATCH", [row["code"] for row in result["blockers"]])

    def test_unity_source_shader_variant_preserves_straight_alpha_additive_factors(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, ir, hashes = _fixture(Path(temp), blend_mode=1)
            with patch.object(spine_materials, "SPINE_EFFECT_STAGE_HASHES", hashes):
                result = inspect_spine_materials(manifest, ir)
            unity = result["binding"]["unity"]["perComponent"][0]
            additive = next(row for row in unity["variants"] if row["blendMode"] == "additive")
            self.assertEqual((additive["sourceBlendFactor"], additive["destinationBlendFactor"]), (5, 1))
            self.assertEqual(unity["shaderSourceSha256"], spine_materials.UNITY_PROFILE_SHADER_SHA256)
            self.assertEqual(unity["sourceAtlasPages"][0]["pageName"], "atlas.png")
            self.assertEqual(unity["sourceAtlasPages"][0]["materialIdentitySeeds"]["additive"],
                             "spineAsset:texture-uuid/spine-source-material/additive")

    def test_unity_shader_source_hash_and_equation_are_pinned(self):
        path = spine_materials.TARGET_DIR / "UnitySpineSourceProfile.shader"
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        self.assertEqual(hashlib.sha256(raw).hexdigest(), spine_materials.UNITY_PROFILE_SHADER_SHA256)
        self.assertIn("Blend [_SrcBlend] [_DstBlend]", text)
        self.assertIn("return tex2D(_MainTex, i.uv) * i.color;", text)
        unity_helper = (spine_materials.TARGET_DIR / "UnitySpineMaterialBindings.cs").read_bytes()
        creator_helper = (spine_materials.TARGET_DIR / "CreatorSpineMaterialBindings.js").read_bytes()
        self.assertEqual(hashlib.sha256(unity_helper).hexdigest(), spine_materials.UNITY_BINDING_HELPER_SHA256)
        self.assertEqual(hashlib.sha256(creator_helper).hexdigest(), spine_materials.CREATOR_BINDING_HELPER_SHA256)

    def test_plan_requires_exact_input_pins_and_emits_only_a_blocker_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, ir, hashes = _fixture(root)
            with patch.object(spine_materials, "SPINE_EFFECT_STAGE_HASHES", hashes):
                with self.assertRaisesRegex(SpineMaterialError, "pin mismatch"):
                    plan_spine_materials(manifest, ir, "wrong", hashlib.sha256(ir.read_bytes()).hexdigest())
                plan = plan_spine_materials(manifest, ir, hashlib.sha256(manifest.read_bytes()).hexdigest(),
                                            hashlib.sha256(ir.read_bytes()).hexdigest())
            self.assertEqual(plan["status"], "creator-builtin-and-unity-shader-candidates-ready-native-bindings-pending")
            self.assertEqual(plan["ownedFiles"], [])
            self.assertEqual(plan["nativeCompilation"], "not_run")
            self.assertEqual(plan["creatorBindingStatus"], "source-semantics-exact-builtin-spine")


if __name__ == "__main__":
    unittest.main()
