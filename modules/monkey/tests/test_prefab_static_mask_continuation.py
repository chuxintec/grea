import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.monkey import shader_profiles
from src.monkey.prefab_static_mask_continuation import (
    SOURCE_ENGINE_PATH,
    SOURCE_ENGINE_SHA256,
    SOURCE_ENGINE_URL,
    StaticMaskContinuationError,
    attach_contract,
    build_contract,
    prepare,
)


VERTEX = "void main() { gl_Position = vec4(0.0); }\n"
FRAGMENT = "void main() { gl_FragColor = vec4(1.0); }\n"
VERTEX_SHA = hashlib.sha256(VERTEX.encode()).hexdigest()
FRAGMENT_SHA = hashlib.sha256(FRAGMENT.encode()).hexdigest()
PREFAB = "gameAsset:mask-continuation-fixture"
MATERIAL_UUID = "mask-continuation-material"
EFFECT_UUID = "mask-continuation-effect"


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


class StaticMaskContinuationTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        vertex_patch = patch.object(shader_profiles, "VERTEX_SHA256", VERTEX_SHA)
        fragment_patch = patch.object(shader_profiles, "FRAGMENT_SHA256", FRAGMENT_SHA)
        vertex_patch.start(); fragment_patch.start()
        self.addCleanup(vertex_patch.stop); self.addCleanup(fragment_patch.stop)

        raw_overrides = {
            0: {"_type": 0, "_N$inverted": False, "_N$alphaThreshold": 0.0},
            2: {"_inverted": True},
            4: {"_N$type": 0, "_N$inverted": False},
            6: {"_N$alphaThreshold": 0.0},
            8: {},
        }
        instances = [None] * 12
        components = []
        nodes = []
        ids = {}
        for index, source_name in zip((0, 2, 4, 6, 8), ("a", "b", "c", "d", "inactive")):
            node_id = f"{PREFAB}#{index}"
            source_id = node_id + "/components/0"
            native_id = f"native-mask-{source_name}"
            raw = {"__type__": "cc.Mask", "_materials": [{"__uuid__": MATERIAL_UUID}],
                   **raw_overrides[index]}
            instances[index] = {"__type__": "cc.Node", "_components": [{"__id__": index + 1}]}
            instances[index + 1] = raw
            components.append({"sourceId": source_id, "type": "cc.Mask", "node": node_id,
                               "nativeId": native_id, "enabled": True, "maskType": 0,
                               "inverted": source_name == "b", "convertible": True})
            ids[source_name] = source_id
            parent = "mask-inactive-parent" if source_name == "inactive" else "mask-queue-root"
            nodes.append({"sourceId": node_id, "parent": parent, "children": [], "active": True})

        clone_id = f"{PREFAB}#12::sync-component-clone"
        clone_node = f"{PREFAB}#12::sync-node-clone"
        components.append({"sourceId": clone_id, "type": "cc.Mask", "node": clone_node,
                           "nativeId": components[1]["nativeId"], "enabled": True,
                           "maskType": 0, "inverted": True, "convertible": True})
        ids["clone"] = clone_id
        nodes.append({"sourceId": clone_node, "parent": "mask-queue-root", "children": [], "active": True})
        nodes.extend([
            {"sourceId": "mask-queue-root", "parent": None,
             "children": [f"{PREFAB}#0", f"{PREFAB}#2", f"{PREFAB}#4", f"{PREFAB}#6", "mask-inactive-parent", clone_node],
             "active": True},
            {"sourceId": "mask-inactive-parent", "parent": "mask-queue-root",
             "children": [f"{PREFAB}#8"], "active": False},
        ])
        child_order = [{"node": "mask-queue-root",
                        "children": [f"{PREFAB}#0", f"{PREFAB}#2", f"{PREFAB}#4", f"{PREFAB}#6", "mask-inactive-parent", clone_node]},
                       {"node": "mask-inactive-parent", "children": [f"{PREFAB}#8"]}]
        raw_by_id = {row["sourceId"]: instances[int(row["sourceId"].split("#", 1)[1].split("/", 1)[0]) + 1]
                     for row in components if "/components/" in row["sourceId"]}
        queue_mask_ids = [ids[x] for x in ("a", "b", "c", "d", "clone")]
        queue_masks = []
        for source_id in queue_mask_ids:
            row = next(c for c in components if c["sourceId"] == source_id)
            origin = ids["b"] if source_id == clone_id else source_id
            raw = raw_by_id[origin]
            threshold = raw.get("_alphaThreshold", raw.get("_N$alphaThreshold", 0.1))
            source_index = int(origin.split("#", 1)[1].split("/", 1)[0])
            source_fields = instances[source_index + 1]
            queue_masks.append({"sourceId": source_id, "nativeId": row["nativeId"], "node": row["node"],
                                "maskType": 0, "enabled": True, "inverted": row["inverted"],
                                "alphaThreshold": threshold, "sourceFields": source_fields,
                                "sourceFieldsJson": json.dumps(source_fields, ensure_ascii=False, sort_keys=True,
                                                               separators=(",", ":"))})

        source_manifest = {
            "sourceProfile": "cocos-2.4.15-bundle", "sourceVersion": "2.4.15",
            "assets": [
                {"sourceId": PREFAB, "bundle": "gameAsset", "kind": "cc.Prefab",
                 "document": {"instances": instances}},
                {"sourceId": "gameAsset:" + MATERIAL_UUID, "bundle": "gameAsset", "kind": "cc.Material",
                 "document": {"root": 0, "instances": [{"__type__": "cc.Material", "_name": "builtin-2d-sprite",
                     "_effectAsset": {"__uuid__": EFFECT_UUID},
                     "_techniqueData": {"0": {"defines": {"USE_TEXTURE": True}}}}]}},
                {"sourceId": "internal:" + EFFECT_UUID, "bundle": "internal", "kind": "cc.EffectAsset",
                 "document": {"root": 0, "instances": [_effect_root()]}},
            ],
        }
        manifest_path = Path(temp.name) / "source-manifest.json"
        manifest_bytes = json.dumps(source_manifest, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()
        manifest_path.write_bytes(manifest_bytes)
        queues = [{"sourcePrefabId": PREFAB, "rootScope": "mask-queue-root", "sourceChildOrder": child_order,
                   "masks": queue_masks}]
        plan = {
            "namespace": "mask-continuation-test", "sourceProfile": "cocos-2.4.15-bundle",
            "sourceManifestPath": str(manifest_path),
            "sourceManifestSha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "components": components, "nodes": nodes,
            "staticAnimationComponentOrigins": [{"instanceSourceId": clone_id, "templateSourceId": ids["b"]}],
            "staticSortQueue": queues,
        }
        return plan, source_manifest, ids, temp

    def test_contract_preserves_all_source_masks_and_explains_inactive_queue_omission(self):
        plan, manifest, ids, _ = self.fixture()
        contract = build_contract(plan, manifest)
        by_id = {row["sourceId"]: row for row in contract["masks"]}
        self.assertEqual(set(by_id), set(ids.values()))
        self.assertEqual(6, len(contract["masks"]))
        self.assertEqual(5, sum(row["sourceQueueDisposition"] == "active-mask-barrier-event"
                                for row in contract["masks"]))
        self.assertEqual("outside-active-render-flow-inactive-ancestor",
                         by_id[ids["inactive"]]["sourceQueueDisposition"])
        self.assertTrue(by_id[ids["inactive"]]["sourceActiveSelf"])
        self.assertFalse(by_id[ids["inactive"]]["sourceActive"])
        self.assertTrue(by_id[ids["b"]]["inverted"])
        self.assertEqual(by_id[ids["b"]]["nativeId"], by_id[ids["clone"]]["nativeId"])
        self.assertNotEqual(by_id[ids["b"]]["sourceId"], by_id[ids["clone"]]["sourceId"])
        type_default = next(row for row in contract["sourceDefaults"] if row["field"] == "maskType")
        self.assertEqual("0", type_default["value"])
        self.assertIn(ids["inactive"], type_default["sourceIds"])
        self.assertEqual(SOURCE_ENGINE_PATH, contract["sourceEngine"]["path"])
        self.assertEqual(SOURCE_ENGINE_SHA256, contract["sourceEngine"]["sha256"])
        self.assertEqual("maskType", by_id[ids["inactive"]]["sourceDefaultFields"][0])
        self.assertEqual(0, by_id[ids["a"]]["alphaThreshold"])
        self.assertEqual(0.1, by_id[ids["inactive"]]["alphaThreshold"])

    def test_missing_active_queue_event_fails_without_dropping_component_identity(self):
        plan, manifest, ids, _ = self.fixture()
        plan["staticSortQueue"][0]["masks"] = [row for row in plan["staticSortQueue"][0]["masks"]
                                               if row["sourceId"] != ids["d"]]
        with self.assertRaisesRegex(StaticMaskContinuationError, "active source Mask has no matching queue event"):
            build_contract(plan, manifest)

    def test_unknown_source_default_profile_and_source_manifest_tamper_fail_closed(self):
        plan, manifest, _, _ = self.fixture()
        wrong_profile = copy.deepcopy(manifest)
        wrong_profile["sourceVersion"] = "2.4.16"
        with self.assertRaisesRegex(StaticMaskContinuationError, "pinned Cocos Creator 2.4.15"):
            build_contract(plan, wrong_profile)
        wrong_manifest = copy.deepcopy(manifest)
        wrong_manifest["assets"][0]["document"]["instances"][0]["name"] = "changed"
        with self.assertRaisesRegex(StaticMaskContinuationError, "in-memory manifest differs"):
            build_contract(plan, wrong_manifest)

    def test_attach_changes_only_static_masks_and_rejects_component_or_contract_conflicts(self):
        plan, manifest, _, _ = self.fixture()
        import_plan = copy.deepcopy(plan)
        import_plan.pop("sourceManifestPath")
        original = copy.deepcopy(import_plan)
        attached = attach_contract(import_plan, plan, manifest)
        self.assertEqual(original, {key: value for key, value in attached.items() if key != "staticMasks"})
        self.assertEqual(6, len(attached["staticMasks"]["masks"]))
        self.assertNotIn("staticMasks", import_plan)

        wrong_component = copy.deepcopy(import_plan)
        wrong_component["components"][0]["nativeId"] = "changed"
        with self.assertRaisesRegex(StaticMaskContinuationError, "component field differs"):
            attach_contract(wrong_component, plan, manifest)
        wrong_contract = copy.deepcopy(import_plan)
        wrong_contract["staticMasks"] = {"masks": []}
        with self.assertRaisesRegex(StaticMaskContinuationError, "conflicting static Mask"):
            attach_contract(wrong_contract, plan, manifest)

    def test_prepare_validates_ir_and_pinned_source_engine_without_copying_engine_source(self):
        plan, manifest, ids, temp = self.fixture()
        ir = {"components": [{"sourceId": row["sourceId"], "type": "cc.Mask"}
                              for row in plan["components"] if row["type"] == "cc.Mask" and row["sourceId"] != ids["clone"]]}
        engine_bytes = b"test fixture bytes for a pinned Cocos Mask engine source"
        engine_path = Path(temp.name) / "CCMask.js"
        engine_path.write_bytes(engine_bytes)
        fake_sha = hashlib.sha256(engine_bytes).hexdigest()
        evidence = {"sourceVersion": "2.4.15", "files": [{"logicalPath": SOURCE_ENGINE_PATH,
            "path": str(engine_path), "sha256": fake_sha, "originUrl": SOURCE_ENGINE_URL,
            "bytes": len(engine_bytes)}]}
        stage = Path(temp.name) / "stage"
        stage.mkdir()
        with patch("src.monkey.prefab_static_mask_continuation.SOURCE_ENGINE_SHA256", fake_sha):
            result = prepare(plan, ir, manifest, stage, evidence)
        self.assertEqual(6, len(result["plan"]["staticMasks"]["masks"]))
        self.assertEqual(5, result["summary"]["queueMaskEventCount"])
        self.assertEqual([ids["inactive"]], result["summary"]["inactiveAncestorMaskIds"])
        self.assertTrue((stage / "mask_static_continuation" / "contract.json").is_file())
        self.assertTrue((stage / "mask_static_continuation" / "metadata.json").is_file())
        self.assertTrue(engine_path.is_file())
        broken_ir = {"components": []}
        with self.assertRaisesRegex(StaticMaskContinuationError, "plan/IR identity differs"):
            prepare(plan, broken_ir, manifest, stage, evidence)


if __name__ == "__main__":
    unittest.main()

