import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from grea.recovery.prefab_static_sort_continuation import (
    SCHEMA,
    StaticSortContinuationError,
    prepare,
)


SORT_ROOT_ID = "fixture:prefab#0/components/0"
SORT_ORDER_ID = "fixture:prefab#1/components/0"
SPRITE_ID = "fixture:prefab#1/components/1"
ROOT_ID = "fixture:prefab#0"
LEAF_ID = "fixture:prefab#1"


def _fixture(stage_root: Path):
    instances = [
        {"__type__": "cc.Node", "_name": "Root", "_children": [{"__id__": 1}],
         "_components": [{"__id__": 2}]},
        {"__type__": "cc.Node", "_name": "Leaf", "_children": [],
         "_components": [{"__id__": 3}, {"__id__": 4}]},
        {"__type__": "cc.SortRoot", "node": {"__id__": 0}},
        {"__type__": "cc.SortOrder", "_sortOrder": 17, "node": {"__id__": 1}},
        {"__type__": "cc.Sprite", "_spriteFrame": None, "node": {"__id__": 1}},
    ]
    manifest = {
        "schemaVersion": 1,
        "sourceProfile": "cocos-2.4.15-bundle",
        "sourceVersion": "2.4.15",
        "assets": [{"sourceId": "fixture:prefab", "bundle": "fixture",
                    "kind": "cc.Prefab", "document": {"instances": instances}}],
    }
    manifest_path = stage_root / "source-manifest.json"
    raw_manifest = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    manifest_path.write_bytes(raw_manifest)
    manifest_sha = hashlib.sha256(raw_manifest).hexdigest()
    plan = {
        "targetProfile": "unity-6000.6.2f1-ugui",
        "namespace": "monkey-project",
        "sourceProfile": None,
        "sourceManifestPath": str(manifest_path),
        "sourceManifestSha256": manifest_sha,
        "sourceIrSha256": "a" * 64,
        "nodes": [
            {"sourceId": ROOT_ID, "parent": None, "children": [LEAF_ID], "active": True},
            {"sourceId": LEAF_ID, "parent": ROOT_ID, "children": [], "active": True},
        ],
        "components": [
            {"sourceId": SORT_ROOT_ID, "nativeId": "sort-root-native", "node": ROOT_ID,
             "type": "cc.SortRoot", "enabled": True, "convertible": False},
            {"sourceId": SORT_ORDER_ID, "nativeId": "sort-order-native", "node": LEAF_ID,
             "type": "cc.SortOrder", "enabled": True, "convertible": False},
            {"sourceId": SPRITE_ID, "nativeId": "sprite-native", "node": LEAF_ID,
             "type": "cc.Sprite", "enabled": True, "convertible": True, "spriteFrame": None},
        ],
        "sourcePrefabs": [{"sourceId": "fixture:prefab", "root": ROOT_ID,
                           "path": "Assets/Game/Prefabs/Fixture.prefab"}],
    }
    ir = {"sourceManifestSha256": manifest_sha, "components": [
        {"sourceId": SORT_ROOT_ID, "type": "cc.SortRoot", "enabled": True},
        {"sourceId": SORT_ORDER_ID, "type": "cc.SortOrder", "enabled": True},
    ]}
    return plan, ir, manifest


class StaticSortContinuationTests(unittest.TestCase):
    def test_prepare_attaches_source_bound_unity_queue_and_manifest_in_fresh_module_stage(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp)
            stage = root / "stage"
            stage.mkdir()
            plan, ir, manifest = _fixture(root)
            original = copy.deepcopy(plan)
            result = prepare(plan, ir, manifest, stage)
            patched = result["plan"]
            summary = result["summary"]
            self.assertEqual(plan, original)
            self.assertEqual(summary["schema"], SCHEMA)
            self.assertEqual(summary["sortOrderCount"], 1)
            self.assertEqual(summary["sortRootCount"], 1)
            self.assertEqual(summary["unityQueueMappedCount"], 1)
            self.assertEqual(len(patched["staticSortQueue"]), 1)
            self.assertEqual(patched["staticSortQueue"][0]["sourceFields"][0]["sortOrder"], 17)
            self.assertEqual(patched["staticSortQueue"][0]["sourceSortRoots"][0]["sourceId"], SORT_ROOT_ID)
            self.assertEqual(patched["staticSortContinuation"]["sourceComponents"][0]["sourceSortOrder"], None)
            self.assertEqual(patched["staticSortContinuation"]["sourceComponents"][1]["sourceSortOrder"], 17)
            self.assertTrue(patched["staticSortContinuation"]["queueReadbackRequired"])
            self.assertEqual(patched["staticSortContinuation"]["sourceComponents"][1]["expectedMarkerType"],
                             "Monkey.StaticSortQueueProxy.NativeStaticSortOrderIdentity")
            self.assertEqual(patched["staticSortContinuation"]["sourceComponents"][1]["sourceBehaviorStatus"],
                             "dynamic_not_run")
            module_stage = Path(summary["moduleStage"])
            self.assertEqual(module_stage.parent, stage)
            contract = json.loads((module_stage / "sort-queue-contract.json").read_text())
            self.assertEqual(contract["sourceSortComponents"], patched["staticSortSourceComponents"])
            manifest_json = json.loads((module_stage / "manifest.json").read_text())
            self.assertEqual(manifest_json["files"][0]["path"], "sort-queue-contract.json")

    def test_unknown_sortorder_is_never_defaulted_to_zero(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp); stage = root / "stage"; stage.mkdir()
            plan, ir, manifest = _fixture(root)
            source = manifest["assets"][0]["document"]["instances"][3]
            del source["_sortOrder"]
            manifest_path = Path(plan["sourceManifestPath"])
            raw = json.dumps({k: v for k, v in manifest.items() if k != "sourceManifestPath"},
                             ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
            manifest_path.write_bytes(raw)
            pin = hashlib.sha256(raw).hexdigest()
            plan["sourceManifestSha256"] = pin
            ir["sourceManifestSha256"] = pin
            with self.assertRaisesRegex(StaticSortContinuationError, "source component fields are not the pinned built-in profile"):
                prepare(plan, ir, manifest, stage)
            self.assertFalse((stage / "static_sort_continuation").exists())

    def test_plan_ir_and_manifest_must_agree_on_all_sort_source_ids(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp); stage = root / "stage"; stage.mkdir()
            plan, ir, manifest = _fixture(root)
            ir["components"] = [row for row in ir["components"] if row["sourceId"] != SORT_ORDER_ID]
            with self.assertRaisesRegex(StaticSortContinuationError, "plan/IR source sort denominator differs"):
                prepare(plan, ir, manifest, stage)

    def test_unknown_source_component_field_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp); stage = root / "stage"; stage.mkdir()
            plan, ir, manifest = _fixture(root)
            manifest["assets"][0]["document"]["instances"][2]["_customSort"] = 1
            manifest_path = Path(plan["sourceManifestPath"])
            clean = {key: value for key, value in manifest.items() if key != "sourceManifestPath"}
            raw = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
            manifest_path.write_bytes(raw)
            pin = hashlib.sha256(raw).hexdigest()
            plan["sourceManifestSha256"] = pin;ir["sourceManifestSha256"] = pin
            with self.assertRaisesRegex(StaticSortContinuationError, "source component fields are not the pinned built-in profile"):
                prepare(plan, ir, manifest, stage)

    def test_version_or_target_profile_change_blocks_pinned_adapter(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp); stage = root / "stage"; stage.mkdir()
            plan, ir, manifest = _fixture(root)
            manifest["sourceVersion"] = "3.8.0"
            with self.assertRaisesRegex(StaticSortContinuationError, "source profile/version"):
                prepare(plan, ir, manifest, stage)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp); stage = root / "stage"; stage.mkdir()
            plan, ir, manifest = _fixture(root)
            plan["targetProfile"] = "creator-3.8"
            with self.assertRaisesRegex(StaticSortContinuationError, "requires a Unity plan"):
                prepare(plan, ir, manifest, stage)

    def test_fresh_subtree_and_source_evidence_pins_are_enforced(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp); stage = root / "stage"; stage.mkdir()
            plan, ir, manifest = _fixture(root)
            source = root / "source.js"; source.write_text("source", encoding="utf-8")
            evidence = {"sourceVersion": "2.4.15", "files": [{
                "logicalPath": "engine-source/fixture.js", "path": str(source),
                "sha256": hashlib.sha256(b"source").hexdigest(), "bytes": 6,
                "originUrl": "https://example.invalid/engine-source/fixture.js"}]}
            result = prepare(plan, ir, manifest, stage, source_evidence=evidence)
            self.assertEqual(result["summary"]["sourceBehaviorBoundary"],
                             "static import-state ordering only; dynamic runtime sort mutation not restored")
            bad = copy.deepcopy(evidence);bad["files"][0]["bytes"] = 5
            next_stage = root / "next-stage";next_stage.mkdir()
            with self.assertRaisesRegex(StaticSortContinuationError, "differs from its pin"):
                prepare(plan, ir, manifest, next_stage, source_evidence=bad)
            existing = root / "existing-stage";existing.mkdir();(existing / "static_sort_continuation").mkdir()
            with self.assertRaisesRegex(StaticSortContinuationError, "fresh stage subtree"):
                prepare(plan, ir, manifest, existing)

    def test_source_order_plan_values_cannot_disagree_with_manifest(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp); stage = root / "stage"; stage.mkdir()
            plan, ir, manifest = _fixture(root)
            plan["components"][1]["sortOrder"] = 18
            with self.assertRaisesRegex(StaticSortContinuationError, "plan SortOrder value differs"):
                prepare(plan, ir, manifest, stage)


if __name__ == "__main__":
    unittest.main()
