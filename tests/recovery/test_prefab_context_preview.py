import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from grea.recovery.prefab_context_preview import contexts, prepare


class ContextPreviewTests(unittest.TestCase):
    def fixture(self):
        manifest = {"sourceProfile": "cocos-2.4.15-bundle", "assets": [
            {"sourceId": "b:parent", "key": "parent", "kind": "cc.Prefab", "document": {"instances": [
                {"__type__": "cc.Prefab", "data": {"__id__": 1}},
                {"__type__": "cc.Node"},
                {"__type__": "cc.Node", "_parent": {"__id__": 1}, "_prefab": {
                    "__type__": "cc.PrefabInfo", "sync": True, "root": {"__id__": 2},
                    "asset": {"__uuid__": "leaf"}, "fileId": "exact-instance"}}]}},
            {"sourceId": "b:leaf", "key": "leaf", "kind": "cc.Prefab"}]}
        plan = {"sourcePrefabs": [
            {"sourceId": "b:parent", "root": "b:parent#1", "nodes": ["b:parent#1", "b:parent#2"]},
            {"sourceId": "b:leaf", "root": "b:leaf#1", "nodes": ["b:leaf#1"]}],
            "nodes": [{"sourceId": "b:parent#1", "parent": None, "active": True},
                      {"sourceId": "b:parent#2", "parent": "b:parent#1", "active": False}],
            "prefabInstances": [{"owner": "b:parent", "root": "b:parent#2", "template": "b:leaf",
                                 "sourceInstanceFileId": "exact-instance", "nodes": [
                                     {"instanceObject": "b:parent#2", "templateObject": "b:leaf#1"}]}]}
        return manifest, plan

    def test_source_identity_preserves_inactive_parent_context(self):
        manifest, plan = self.fixture()
        before = copy.deepcopy((manifest, plan))
        row, = contexts(manifest, plan, "b:leaf")
        self.assertEqual(row["sourceParentChain"], ["b:parent#1", "b:parent#2"])
        self.assertFalse(row["targetSourceState"]["active"])
        self.assertEqual((manifest, plan), before)
        self.assertEqual(contexts(manifest, plan, "b:unknown"), [])

    def test_same_name_wrong_template_file_id_and_parent_are_refused(self):
        for mutation in ("instance", "template", "cycle", "outside"):
            with self.subTest(mutation=mutation):
                manifest, plan = self.fixture()
                if mutation == "instance": plan["prefabInstances"][0]["sourceInstanceFileId"] = "other"
                elif mutation == "template": plan["prefabInstances"][0]["nodes"][0]["templateObject"] = "b:other#1"
                elif mutation == "cycle": plan["nodes"][1]["parent"] = "b:parent#2"
                else: plan["nodes"][1]["parent"] = "b:outside#1"
                with self.assertRaises(ValueError): contexts(manifest, plan, "b:leaf")

    def test_raw_manifest_drift_refused_before_context_admission(self):
        manifest, plan = self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            raw = json.dumps(manifest).encode()
            plan["sourceManifestSha256"] = hashlib.sha256(raw).hexdigest()
            (root/"source.json").write_bytes(raw)
            (root/"plan.json").write_text(json.dumps(plan))
            self.assertEqual(len(prepare(root/"plan.json", root/"source.json", "b:leaf")["contexts"]), 1)
            (root/"source.json").write_bytes(raw+b" ")
            with self.assertRaisesRegex(ValueError, "CONTEXT_SOURCE_MANIFEST_PIN"):
                prepare(root/"plan.json", root/"source.json", "b:leaf")
