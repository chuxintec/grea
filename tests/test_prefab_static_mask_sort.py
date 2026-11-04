import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.monkey import shader_profiles
from src.monkey.prefab_static_mask_sort import StaticMaskSortError, prepare


VERTEX = "void main() { gl_Position = vec4(0.0); }\n"
FRAGMENT = "void main() { gl_FragColor = vec4(1.0); }\n"
VERTEX_SHA = hashlib.sha256(VERTEX.encode()).hexdigest()
FRAGMENT_SHA = hashlib.sha256(FRAGMENT.encode()).hexdigest()
MATERIAL_UUID = "fixture-material"
EFFECT_UUID = "fixture-effect"
FRAME_UUID = "fixture-frame"
PREFAB_ID = "gameAsset:mask-sort-fixture"


def _effect_root():
    declarations = [
        ("USE_TEXTURE", []), ("CC_USE_MODEL", []), ("USE_ALPHA_TEST", []),
        ("CC_USE_ALPHA_ATLAS_texture", ["USE_TEXTURE"]),
        ("INPUT_IS_GAMMA", ["USE_TEXTURE"]), ("USE_BGRA", []),
    ]
    return {
        "__type__": "cc.EffectAsset", "_name": "builtin-2d-sprite",
        "shaders": [{"name": "builtin-2d-sprite|vs|fs",
                     "glsl1": {"vert": VERTEX, "frag": FRAGMENT},
                     "defines": [{"name": name, "type": "boolean", "defines": conditions}
                                 for name, conditions in declarations]}],
        "techniques": [{"passes": [{"program": "builtin-2d-sprite|vs|fs",
                                     "blendState": {"targets": [{"blend": True}]},
                                     "rasterizerState": {"cullMode": 0},
                                     "properties": {"alphaThreshold": {"type": 13, "value": [0.5]},
                                                    "texture": {"type": 29, "value": "white"}}}]}],
    }


class StaticMaskSortContractTests(unittest.TestCase):
    def fixture(self, threshold=1):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        # The fixture is a deliberately small mock of the pinned source profile;
        # bind the verifier's profile hashes to its known deterministic GLSL.
        vertex_patch = patch.object(shader_profiles, "VERTEX_SHA256", VERTEX_SHA)
        fragment_patch = patch.object(shader_profiles, "FRAGMENT_SHA256", FRAGMENT_SHA)
        vertex_patch.start(); fragment_patch.start()
        self.addCleanup(vertex_patch.stop)
        self.addCleanup(fragment_patch.stop)
        mask_id = PREFAB_ID + "#0/components/0"
        order_a_id = PREFAB_ID + "#2/components/0"
        order_b_id = PREFAB_ID + "#4/components/0"
        root_id = PREFAB_ID + "#6/components/0"
        mask_raw = {"__type__": "cc.Mask", "_type": 2, "_N$inverted": False,
                    "_N$alphaThreshold": threshold, "_spriteFrame": {"__uuid__": FRAME_UUID},
                    "_materials": [{"__uuid__": MATERIAL_UUID}]}
        material_root = {"__type__": "cc.Material", "_name": "builtin-2d-sprite",
                         "_effectAsset": {"__uuid__": EFFECT_UUID},
                         "_techniqueData": {"0": {"defines": {"USE_TEXTURE": True}}}}
        instances = [
            {"__type__": "cc.Node", "_components": [{"__id__": 1}]}, mask_raw,
            {"__type__": "cc.Node", "_components": [{"__id__": 3}]},
            {"__type__": "cc.SortOrder", "_sortOrder": 4},
            {"__type__": "cc.Node", "_components": [{"__id__": 5}]},
            {"__type__": "cc.SortOrder", "_sortOrder": -2},
            {"__type__": "cc.Node", "_components": [{"__id__": 7}]},
            {"__type__": "cc.SortRoot"},
        ]
        manifest = {"assets": [
            {"sourceId": PREFAB_ID, "bundle": "gameAsset", "kind": "cc.Prefab",
             "document": {"instances": instances}},
            {"sourceId": "gameAsset:" + MATERIAL_UUID, "bundle": "gameAsset", "kind": "cc.Material",
             "document": {"root": 0, "instances": [material_root]}},
            {"sourceId": "internal:" + EFFECT_UUID, "bundle": "internal", "kind": "cc.EffectAsset",
             "document": {"root": 0, "instances": [_effect_root()]}},
        ]}
        plan = {"components": [
            {"sourceId": mask_id, "type": "cc.Mask", "node": PREFAB_ID + "#0", "nativeId": "native-mask",
             "enabled": True, "maskType": 2, "inverted": False},
            {"sourceId": order_a_id, "type": "cc.SortOrder", "node": PREFAB_ID + "#2", "nativeId": "native-order-a"},
            {"sourceId": order_b_id, "type": "cc.SortOrder", "node": PREFAB_ID + "#4", "nativeId": "native-order-b"},
            {"sourceId": root_id, "type": "cc.SortRoot", "node": PREFAB_ID + "#6", "nativeId": "native-sort-root"},
        ], "nodes": [
            {"sourceId": PREFAB_ID + "#0", "parent": None, "children": []},
            {"sourceId": PREFAB_ID + "#2", "parent": PREFAB_ID + "#6", "children": []},
            {"sourceId": PREFAB_ID + "#4", "parent": PREFAB_ID + "#6", "children": []},
            {"sourceId": PREFAB_ID + "#6", "parent": None,
             "children": [PREFAB_ID + "#2", PREFAB_ID + "#4"]},
        ]}
        source_path = Path(temp.name) / "source-manifest.json"
        self.seal(plan, manifest, source_path)
        return plan, manifest, source_path

    @staticmethod
    def seal(plan, manifest, source_path):
        payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        source_path.write_bytes(payload)
        plan["sourceManifestPath"] = str(source_path)
        plan["sourceManifestSha256"] = hashlib.sha256(payload).hexdigest()

    @staticmethod
    def source_asset(manifest, source_id):
        return next(asset for asset in manifest["assets"] if asset["sourceId"] == source_id)

    def test_neutral_fixture_preserves_source_fields_profile_and_sort_scopes(self):
        plan, manifest, _ = self.fixture()
        result = prepare(plan, manifest)
        self.assertEqual(len(result["masks"]), 1)
        self.assertEqual(len(result["sortOrders"]), 2)
        self.assertEqual(len(result["sortRoots"]), 1)
        mask = result["masks"][0]
        self.assertEqual(mask["alphaThreshold"], 1)
        self.assertEqual(mask["spriteFrameUuid"], FRAME_UUID)
        self.assertEqual(mask["sourceEffectProgramSha256"], {"glsl1.vert": VERTEX_SHA, "glsl1.frag": FRAGMENT_SHA})
        self.assertEqual(mask["sourceMaterialName"], "builtin-2d-sprite")
        self.assertTrue(result["sortGroups"][0]["representableBySiblingOrder"])
        self.assertEqual(result["sortGroups"][0]["expectedSiblingOrder"], [PREFAB_ID + "#4", PREFAB_ID + "#2"])

    def test_threshold_zero_and_one_are_preserved_and_shader_uses_exact_less_than_boundary(self):
        shader_path = Path(__file__).resolve().parents[1] / "src/monkey/targets/materials/static_mask/NativeStaticImageMask.shader"
        shader = shader_path.read_text(encoding="utf-8")
        self.assertIn("if (tex.a < _AlphaThreshold) discard;", shader)
        self.assertNotIn("clip(tex.a", shader)
        self.assertNotIn("tex.a - _AlphaThreshold", shader)
        for threshold in (0, 1):
            with self.subTest(threshold=threshold):
                plan, manifest, _ = self.fixture(threshold)
                self.assertEqual(prepare(plan, manifest)["masks"][0]["alphaThreshold"], threshold)

    def test_source_material_defines_and_properties_must_match_exact_profile(self):
        for mutate in (
            lambda root: root["_techniqueData"]["0"]["defines"].update({"USE_ALPHA_TEST": True}),
            lambda root: root["_techniqueData"]["0"].update({"properties": {"alphaThreshold": 0.5}}),
            lambda root: root.update({"_props": {"alphaThreshold": 0.5}}),
        ):
            with self.subTest(mutate=mutate):
                plan, manifest, source_path = self.fixture()
                material = self.source_asset(manifest, "gameAsset:" + MATERIAL_UUID)
                mutate(material["document"]["instances"][0])
                self.seal(plan, manifest, source_path)
                with self.assertRaisesRegex(StaticMaskSortError, "material defines/properties|material fields"):
                    prepare(plan, manifest)

    def test_effect_glsl_stage_hash_and_effect_properties_are_pinned(self):
        plan, manifest, source_path = self.fixture()
        effect = self.source_asset(manifest, "internal:" + EFFECT_UUID)["document"]["instances"][0]
        effect["shaders"][0]["glsl1"]["vert"] += "// tamper\n"
        self.seal(plan, manifest, source_path)
        with self.assertRaisesRegex(StaticMaskSortError, "GLSL hashes"):
            prepare(plan, manifest)

        plan, manifest, source_path = self.fixture()
        effect = self.source_asset(manifest, "internal:" + EFFECT_UUID)["document"]["instances"][0]
        effect["techniques"][0]["passes"][0]["properties"]["alphaThreshold"]["value"] = [0.25]
        self.seal(plan, manifest, source_path)
        with self.assertRaisesRegex(StaticMaskSortError, "effect properties/render state"):
            prepare(plan, manifest)

    def test_hash_bound_manifest_and_component_id_tampering_fail_closed(self):
        plan, manifest, _ = self.fixture()
        changed = copy.deepcopy(manifest)
        changed["assets"][0]["kind"] = "tampered"
        with self.assertRaisesRegex(StaticMaskSortError, "in-memory manifest differs from hash-bound"):
            prepare(plan, changed)
        plan["components"][0]["sourceId"] += "/missing"
        with self.assertRaises(StaticMaskSortError):
            prepare(plan, manifest)

    def test_missing_image_frame_and_unknown_mask_type_are_rejected(self):
        plan, manifest, source_path = self.fixture()
        self.source_asset(manifest, PREFAB_ID)["document"]["instances"][1].pop("_spriteFrame")
        self.seal(plan, manifest, source_path)
        with self.assertRaisesRegex(StaticMaskSortError, "no exact SpriteFrame UUID"):
            prepare(plan, manifest)
        plan, manifest, source_path = self.fixture()
        self.source_asset(manifest, PREFAB_ID)["document"]["instances"][1]["_type"] = 7
        self.seal(plan, manifest, source_path)
        with self.assertRaisesRegex(StaticMaskSortError, "unsupported or missing source mask fields"):
            prepare(plan, manifest)


if __name__ == "__main__":
    unittest.main()
