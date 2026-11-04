import json
import hashlib
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monkey import prefab_materials
from monkey.prefab_materials import (MaterialProfileError, _validate_binding_spec, emit_ui_color,
                                    generate_ui_color, inspect_ui_color, plan_ui_color)


def _asset(source_id, kind, index, doc, *, refs=None, path=None, ordinal=None):
    return {
        "sourceId": source_id,
        "kind": kind,
        "index": index,
        "logicalPath": path or kind,
        "bundle": "gameAsset",
        "importPath": "import/00/fixture.json",
        "pack": "fixture",
        "packOrdinal": ordinal if ordinal is not None else index,
        "references": refs or [],
        "document": {"root": 0, "instances": [doc]},
    }


def _fixture(tmp: Path, *, nonzero=True, add_unknown=False, changed_formula=False):
    pack = tmp / "source/import/00/fixture.json"
    pack.parent.mkdir(parents=True)
    pack.write_text('{"fixture":"immutable source bytes"}', encoding="utf-8")
    effect_uuid = "effect-fixture-id"
    mat_uuid = "material-fixture-id"
    vert = "vec4 vert () { return vec4(1.0); }"
    frag = "vec4 frag () { return vec4(1.0); }"
    if changed_formula:
        frag = "vec4 frag () { return vec4(0.0); }"
    effect = {
        "__type__": "cc.EffectAsset", "_uuid": effect_uuid, "_name": "shader-2d-uiColor",
        "shaders": [{"name": "shader-2d-uiColor|vs|fs",
                      "glsl1": {"vert": vert, "frag": frag},
                      "glsl3": {"vert": vert, "frag": frag}}],
        "techniques": [{"passes": [{"program": "shader-2d-uiColor|vs|fs", "properties": {
            "brightness": {"value": [1]}, "saturation": {"value": [1]},
            "constrast": {"value": [1]}, "gray": {"value": [0]},
            "silhouette": {"value": [1, 1, 1, 1]}, "texture": {"value": "white"},
        }}]}],
    }
    held_effect = {"__type__": "cc.EffectAsset", "_name": "unported-effect", "shaders": [], "techniques": []}
    props = ({"brightness": 1.25, "saturation": 0.6, "constrast": 1.4, "gray": 0.35,
              "silhouette": {"__value_type__": 4, "values": [0x336699CC]}} if nonzero
             else {"gray": 0, "saturation": 1})
    material = {"__type__": "cc.Material", "_uuid": mat_uuid, "_name": "shader-2d-uiColor",
                "_effectAsset": {"__uuid__": effect_uuid},
                "_techniqueData": {"0": {"defines": {"USE_TEXTURE": True}, "props": props}}}
    held_material = {"__type__": "cc.Material", "_name": "keep-me",
                     "_effectAsset": {"__uuid__": "held-effect-id"}, "_techniqueData": {"0": {"props": {"unknown": 7}}}}
    prefab = {"__type__": "cc.Prefab", "_name": "Fixture",
              "data": {"__id__": 1}}
    sprite = {"__type__": "cc.Sprite", "_materials": [{"__uuid__": mat_uuid}],
              "_spriteFrame": {"__uuid__": "frame-id"}}
    inline_node = {"__type__": "cc.Node", "_name": "inline-node", "_components": [
        {"__type__": "cc.Sprite", "_materials": [{"__uuid__": mat_uuid}],
         "_spriteFrame": {"__uuid__": "frame-id"}}]}
    frame = {"__type__": "cc.SpriteFrame", "_textureSetter": {"__uuid__": "texture-id"}}
    texture = {"__type__": "cc.Texture2D"}
    assets = [
        _asset("gameAsset:effect-fixture-id", "cc.EffectAsset", 11, effect, path="Shader/shader-2d-uiColor"),
        _asset("gameAsset:material-fixture-id", "cc.Material", 12, material, refs=[effect_uuid], path="Shader/shader-2d-uiColor"),
        _asset("gameAsset:fixture-prefab", "cc.Prefab", 1, prefab, refs=["material-fixture-id", "held-material-id"], path="Prefab/Fixture"),
        _asset("gameAsset:frame-id", "cc.SpriteFrame", 13, frame, path="Sprite/Frame"),
        _asset("gameAsset:texture-id", "cc.Texture2D", 14, texture, path="Texture/Frame"),
        _asset("gameAsset:held-material-id", "cc.Material", 15, held_material, refs=["held-effect-id"], path="Shader/Unported"),
        _asset("gameAsset:held-effect-id", "cc.EffectAsset", 16, held_effect, path="Shader/unported-effect"),
    ]
    assets[2]["document"]["instances"].append(sprite)
    assets[2]["document"]["instances"].append(inline_node)
    if add_unknown:
        assets[1]["document"]["instances"][0]["_techniqueData"]["0"]["props"]["mystery"] = 9
    manifest = {"assets": assets, "selection": [1], "sourceRoots": {"gameAsset": str(tmp / "source")}}
    path = tmp / "source-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _fixture_profile(manifest_path):
    manifest = json.loads(Path(manifest_path).read_text())
    effect = manifest["assets"][0]["document"]["instances"][0]
    return patch.object(prefab_materials, "UI_COLOR_STAGE_HASHES", prefab_materials._stage_hashes(effect))


class PrefabMaterialTests(unittest.TestCase):
    def test_inspection_follows_selected_prefab_material_effect_spriteframe_texture(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = _fixture(Path(temp))
            with _fixture_profile(manifest):
                result = inspect_ui_color(manifest)
            self.assertEqual(result["profile"], "cocos24-ui-color-sprite-v1")
            self.assertEqual(result["source"]["effectSourceId"], "gameAsset:effect-fixture-id")
            self.assertEqual(result["source"]["materialSourceId"], "gameAsset:material-fixture-id")
            self.assertEqual(len(result["source"]["prefabOccurrences"]), 2)
            self.assertIn("gameAsset:fixture-prefab#2/components/0",
                          [row["componentSourceId"] for row in result["source"]["prefabOccurrences"]])
            self.assertEqual(result["source"]["textures"][0]["sourceId"], "gameAsset:texture-id")
            self.assertEqual(result["material"]["properties"]["silhouette"], [0x33 / 255, 0x66 / 255, 0x99 / 255, 0xCC / 255])
            self.assertEqual(result["source"]["selectedMaterialScope"]["retainedOutsideProfileCount"], 1)
            retained = next(row for row in result["source"]["selectedMaterialScope"]["materials"]
                            if row["materialSourceId"] == "gameAsset:held-material-id")
            self.assertEqual(retained["status"], "retained-outside-profile")
            self.assertEqual(retained["effectName"], "unported-effect")

    def test_dual_target_candidate_preserves_nonzero_parameter_counterexample(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = _fixture(root)
            with _fixture_profile(manifest):
                report = generate_ui_color(manifest, root / "candidate")
            self.assertEqual(report["nativeCompilation"], "not_run")
            self.assertEqual(report["creatorEditorImport"], "not_run")
            self.assertEqual(report["unity"]["properties"]["gray"], 0.35)
            self.assertEqual(report["unity"]["properties"]["brightness"], 1.25)
            self.assertEqual(report["creator38"]["properties"]["constrast"], 1.4)
            unity_mat = (root / "candidate/Unity/Shader2DUIColor.mat").read_text()
            creator_contract = json.loads((root / "candidate/Creator38/Shader2DUIColor.material-contract.json").read_text())
            self.assertIn("_Gray: 0.35", unity_mat)
            self.assertEqual(creator_contract["properties"]["silhouette"], [0x33 / 255, 0x66 / 255, 0x99 / 255, 0xCC / 255])
            self.assertTrue((root / "candidate/Unity/Shader2DUIColor.shader").is_file())
            self.assertTrue((root / "candidate/Creator38/Shader2DUIColor.effect").is_file())
            self.assertEqual(report["creator38"]["materialStatus"], "runtime-editor-contract-only-native-material-identity-pending")

    def test_rejects_unaccounted_material_parameter_instead_of_dropping_it(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = _fixture(Path(temp), add_unknown=True)
            with _fixture_profile(manifest):
                with self.assertRaisesRegex(MaterialProfileError, "outside the supported property contract"):
                    inspect_ui_color(manifest)

    def test_refuses_candidate_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = _fixture(root)
            output = root / "candidate"
            output.mkdir()
            (output / "keep.txt").write_text("human-owned")
            with _fixture_profile(manifest):
                with self.assertRaises(FileExistsError):
                    generate_ui_color(manifest, output)
            self.assertEqual((output / "keep.txt").read_text(), "human-owned")

    def test_same_program_name_with_changed_shader_formula_is_rejected_by_stage_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline = _fixture(root / "baseline")
            changed = _fixture(root / "changed", changed_formula=True)
            with _fixture_profile(baseline):
                with self.assertRaisesRegex(MaterialProfileError, "expected one exact uiColor source program profile"):
                    inspect_ui_color(changed)

    def test_pinned_plan_and_emit_keep_native_materials_out_of_owned_yaml_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = _fixture(root)
            with _fixture_profile(manifest):
                source = inspect_ui_color(manifest)
                source_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
                ir = {"sourceManifestSha256": source_sha,
                      "components": [{"type": "cc.Sprite", "materials": [source["source"]["materialSourceId"]],
                                      "sourceId": row["componentSourceId"]}
                                     for row in source["source"]["prefabOccurrences"]]}
                ir_path = root / "ir.json"
                ir_path.write_text(json.dumps(ir), encoding="utf-8")
                ir_sha = hashlib.sha256(ir_path.read_bytes()).hexdigest()
                plan = plan_ui_color(manifest, ir_path, "UiColorModule", source_sha, ir_sha)
                self.assertEqual(plan["spec"]["materialSourceId"], "gameAsset:material-fixture-id")
                self.assertNotIn("sourceMaterialId", plan["spec"])
                self.assertEqual(plan["spec"]["sourceIrComponentIds"]["exactMatch"], True)
                self.assertEqual(plan["spec"]["creator"]["materialPath"],
                                 "assets/resources/Materials/UiColorModule/Shader2DUIColor.mtl")
                self.assertEqual(plan["spec"]["unity"]["materialPath"],
                                 "Assets/Game/Content/Materials/UiColorModule/Shader2DUIColor.mat")
                self.assertFalse(any(row["path"].endswith(".mat") or row["path"].endswith(".mtl")
                                     for row in plan["ownedFiles"]))
                emitted = emit_ui_color(plan, Path(__file__).parents[1], root / "candidate")
                self.assertEqual(emitted["status"], "owned-files-emitted-native-assets-pending")
                self.assertTrue((root / "candidate/Assets/Game/Content/Shaders/UiColorModule/Shader2DUIColor.shader").is_file())
                self.assertTrue((root / "candidate/assets/resources/Shaders/UiColorModule/Shader2DUIColor.effect").is_file())
                self.assertTrue((root / "candidate/Assets/Game/Content/Materials/UiColorModule/Shader2DUIColor.mat.meta").is_file())
                self.assertFalse((root / "candidate/Assets/Game/Content/Materials/UiColorModule/Shader2DUIColor.mat").exists())

    def test_native_spec_structure_rejects_legacy_material_id_alias(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = _fixture(root)
            with _fixture_profile(manifest):
                source = inspect_ui_color(manifest)
                source_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
                ir = {"sourceManifestSha256": source_sha,
                      "components": [{"type": "cc.Sprite", "materials": [source["source"]["materialSourceId"]],
                                      "sourceId": row["componentSourceId"]}
                                     for row in source["source"]["prefabOccurrences"]]}
                ir_path = root / "ir.json"; ir_path.write_text(json.dumps(ir), encoding="utf-8")
                ir_sha = hashlib.sha256(ir_path.read_bytes()).hexdigest()
                spec = plan_ui_color(manifest, ir_path, "UiColorModule", source_sha, ir_sha)["spec"]
                _validate_binding_spec(spec)
                bad = copy.deepcopy(spec)
                bad["sourceMaterialId"] = bad.pop("materialSourceId")
                with self.assertRaisesRegex(MaterialProfileError, "canonical materialSourceId"):
                    _validate_binding_spec(bad)

    def test_plan_requires_explicit_matching_manifest_and_ir_pins(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = _fixture(root)
            source_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
            ir_path = root / "ir.json"
            ir_path.write_text(json.dumps({"sourceManifestSha256": source_sha, "components": []}), encoding="utf-8")
            ir_sha = hashlib.sha256(ir_path.read_bytes()).hexdigest()
            with _fixture_profile(manifest):
                with self.assertRaisesRegex(MaterialProfileError, "explicit source manifest/IR pin mismatch"):
                    plan_ui_color(manifest, ir_path, "UiColorModule", "0" * 64, ir_sha)

    def test_binding_helpers_use_native_asset_creation_and_persisted_readback_apis(self):
        target = Path(__file__).parents[1] / "src/monkey/targets/materials/ui_color"
        unity = (target / "UnityMaterialBindings.cs").read_text()
        creator = (target / "CreatorMaterialBindings.js").read_text()
        self.assertIn("AssetDatabase.CreateAsset(material, spec.materialPath)", unity)
        self.assertIn("AssetDatabase.TryGetGUIDAndLocalFileIdentifier", unity)
        self.assertIn("EnsurePlannedMaterialMeta(spec)", unity)
        self.assertIn("ShaderUtil.ShaderHasError(shader)", unity)
        self.assertIn("EditorExtends.serialize(material)", creator)
        self.assertIn("saveAndReload({ assetPath: spec.creator.materialPath", creator)
        self.assertIn("record.metaContents", creator)
        self.assertIn("record.metaPath !== spec.creator.materialMetaPath", creator)
        self.assertIn("meta.uuid !== spec.creator.materialUuid", creator)
        self.assertIn("sprite.customMaterial = savedMaterial", creator)
        self.assertIn("MATERIAL_PROFILE_UNSUPPORTED", creator)


if __name__ == "__main__":
    unittest.main()
