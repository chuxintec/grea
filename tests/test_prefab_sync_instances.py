import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from monkey.prefab_sync_instances import (SyncPrefabError, bind_sync_prefab_instances,
                                          load_verified_source_manifest, needs_sync_prefab_binding)
from monkey.targets.prefabs import native_relationships


def _plan():
    owner_a, owner_b, template = "bundle:a", "bundle:b", "bundle:t"
    nodes = [
        dict(sourceId=f"{owner}#2", name="parent", parent=None, children=[f"{owner}#1"], components=[])
        for owner in (owner_a, owner_b)
    ]
    for owner in (owner_a, owner_b):
        nodes.append(dict(sourceId=f"{owner}#1", name="old-placeholder", parent=f"{owner}#2", children=[], components=[],
                          active=True, position=[1, 2, 0], rotation=[0, 0, 0, 1], scale=[1, 1, 1], size=[0, 0], anchor=[.5, .5]))
    nodes.extend([
        dict(sourceId=f"{template}#1", name="TemplateRoot", parent=None, children=[f"{template}#2"], components=[f"{template}#c0"],
             active=True, position=[0, 0, 0], rotation=[0, 0, 0, 1], scale=[2, 2, 1], size=[100, 40], anchor=[.25, .5]),
        dict(sourceId=f"{template}#2", name="Label", parent=f"{template}#1", children=[], components=[],
             active=True, position=[3, 4, 0], rotation=[0, 0, 0, 1], scale=[1, 1, 1], size=[20, 8], anchor=[.5, .5]),
    ])
    components = [dict(sourceId=f"{template}#c0", node=f"{template}#1", type="cc.Custom", convertible=True,
                       font="asset:shared", spriteFrame="asset:shared",
                       controllerPath="Assets/Controllers/Example.controller",
                       normalClipPath="Assets/Controllers/Example_normal.anim",
                       staticFieldBinding={"scriptPath": "Scripts/SharedCarrier.ts", "fields": [{"sourceIds": [f"{template}#2", "asset:shared"],
                                                        "refValues": [f"{template}#2", "asset:shared"],
                                                        "snapshotJson": json.dumps({"node": f"{template}#2", "asset": "asset:shared"})}]})]
    return dict(nodes=nodes, components=components, assets=[{"sourceId": "asset:shared", "path": "shared.png"}],
                staticFieldScripts=[{"target": "Scripts/SharedCarrier.ts"}], sourcePrefabs=[
        dict(sourceId=owner_a, root=f"{owner_a}#2", nodes=[f"{owner_a}#2", f"{owner_a}#1"], nodeCount=2),
        dict(sourceId=owner_b, root=f"{owner_b}#2", nodes=[f"{owner_b}#2", f"{owner_b}#1"], nodeCount=2),
        dict(sourceId=template, root=f"{template}#1", nodes=[f"{template}#1", f"{template}#2"], nodeCount=2),
    ], prefabInstances=[])


def _manifest(*, missing=False, cycle=False, unsupported=False):
    def doc(name, parent, template_uuid, pos, sync=True):
        root = {"__type__": "cc.Node", "_name": name, "_parent": {"__id__": 2}, "_trs": [*pos, 0, 0, 0, 1, 1, 1, 1],
                "_prefab": {"__type__": "cc.PrefabInfo", "asset": {"__uuid__": template_uuid}, "fileId": "file-" + name,
                            "root": {"__id__": 1}, "sync": sync}}
        if unsupported:
            root["_contentSize"] = {"width": 10, "height": 10}
        return {"instances": [{"__type__": "cc.Prefab", "_name": name, "data": {"__id__": 1}}, root,
                              {"__type__": "cc.Node", "_name": "Parent"}], "root": 0}
    uuid_by_owner = {"bundle:a": "uuid-a", "bundle:b": "uuid-b", "bundle:t": "uuid-t"}
    assets = [
        {"sourceId": "bundle:a", "key": uuid_by_owner["bundle:a"], "kind": "cc.Prefab",
         "document": doc("A", None, "uuid-t" if not cycle else "uuid-b", [11, 12, 0])},
        {"sourceId": "bundle:b", "key": uuid_by_owner["bundle:b"], "kind": "cc.Prefab",
         "document": doc("B", None, "uuid-t" if not cycle else "uuid-a", [31, 32, 0])},
        {"sourceId": "bundle:t", "key": uuid_by_owner["bundle:t"], "kind": "cc.Prefab",
         "document": {"instances": [{"__type__": "cc.Prefab", "data": {"__id__": 1}}, {"__type__": "cc.Node"}], "root": 0}},
    ]
    if missing:
        assets[0]["document"]["instances"][1]["_prefab"]["asset"]["__uuid__"] = "unknown"
    return {"assets": assets}


class SyncPrefabTests(unittest.TestCase):
    def test_long_multibyte_clone_asset_names_keep_bounded_distinct_roles(self):
        from monkey.prefab_sync_instances import _suffix_generated_paths
        from pathlib import PurePosixPath
        row={key:'Assets/Generated/'+('界面'*25)+tail for key,tail in [('controllerPath','.controller'),('normalClipPath','_normal.anim'),('pressedClipPath','_pressed.anim')]}
        original=copy.deepcopy(row);_suffix_generated_paths(row,'bundle:owner#1')
        self.assertEqual(len(set(row.values())),3)
        self.assertTrue(all(len(PurePosixPath(p).name.encode('utf-8'))<=64 for p in row.values()))
        again=copy.deepcopy(original);_suffix_generated_paths(again,'bundle:owner#1');self.assertEqual(row,again)
        different=copy.deepcopy(original);_suffix_generated_paths(different,'bundle:owner#2');self.assertTrue(set(row.values()).isdisjoint(different.values()))

    def test_spine_instance_owns_target_identity_and_preserves_template_origin(self):
        plan=_plan()
        plan['components'][0]['spineBinding']={'sourceComponentId':'bundle:t#c0','sourcePrefabId':'bundle:t','sourceNodeId':'1','sourceDataId':'asset:shared'}
        result=bind_sync_prefab_instances(plan,_manifest())
        clones=[c for c in result['components']if '::sync-component' in c['sourceId']]
        self.assertEqual(len(clones),2)
        for c in clones:
            b=c['spineBinding']
            self.assertEqual(b['sourceTemplateComponentId'],'bundle:t#c0')
            self.assertEqual(b['sourceComponentId'],c['sourceId'])
            self.assertEqual(b['sourceNodeId'],c['node'])
            self.assertEqual(b['sourcePrefabId'],c['node'].split('#')[0])
            self.assertEqual(b['sourceDataId'],'asset:shared')
        self.assertEqual(plan['components'][0]['spineBinding']['sourcePrefabId'],'bundle:t')

    def test_two_sync_instances_clone_template_and_remap_internal_refs(self):
        plan = _plan()
        original_template = copy.deepcopy(plan["nodes"][-2:])
        result = bind_sync_prefab_instances(plan, _manifest())
        self.assertEqual(plan["prefabInstances"], [])
        self.assertEqual(result["nodes"][-2:], original_template)
        self.assertEqual(len(result["prefabInstances"]), 2)
        self.assertEqual(len(result["syncPrefabBindings"]), 2)
        instances = {item["root"]: item for item in result["prefabInstances"]}
        a, b = instances["bundle:a#1"], instances["bundle:b#1"]
        self.assertEqual(a["template"], "bundle:t")
        self.assertNotEqual(a["nodes"][1]["instanceObject"], b["nodes"][1]["instanceObject"])
        rows = {node["sourceId"]: node for node in result["nodes"]}
        self.assertEqual(rows["bundle:a#1"]["name"], "A")
        self.assertEqual(rows["bundle:a#1"]["position"], [11, 12, 0])
        self.assertEqual(rows["bundle:a#1"]["scale"], [2, 2, 1])
        self.assertEqual(rows["bundle:b#1"]["name"], "B")
        self.assertEqual(rows["bundle:b#1"]["position"], [31, 32, 0])
        cloned = next(c for c in result["components"] if c["sourceId"].startswith("bundle:a#1::sync-component"))
        cloned_b = next(c for c in result["components"] if c["sourceId"].startswith("bundle:b#1::sync-component"))
        self.assertNotEqual(cloned["controllerPath"], cloned_b["controllerPath"])
        self.assertNotEqual(cloned["normalClipPath"], cloned_b["normalClipPath"])
        self.assertTrue(cloned["controllerPath"].startswith("Assets/Controllers/Example__sync_"))
        ref = cloned["staticFieldBinding"]["fields"][0]["sourceIds"]
        self.assertEqual(ref[0], a["nodes"][1]["instanceObject"])
        self.assertEqual(ref[1], "asset:shared")
        self.assertEqual(cloned["staticFieldBinding"]["fields"][0]["refValues"], [a["nodes"][1]["instanceObject"], "asset:shared"])
        snapshot = json.loads(cloned["staticFieldBinding"]["fields"][0]["snapshotJson"])
        self.assertEqual(snapshot, {"asset": "asset:shared", "node": a["nodes"][1]["instanceObject"]})
        self.assertIn("asset:shared", {asset["sourceId"] for asset in result["assets"]})
        self.assertEqual(cloned["font"], "asset:shared")
        self.assertEqual(cloned["spriteFrame"], "asset:shared")
        self.assertIn(cloned["staticFieldBinding"]["scriptPath"], {script["target"] for script in result["staticFieldScripts"]})
        self.assertEqual(len(next(x for x in result["sourcePrefabs"] if x["sourceId"] == "bundle:a")["nodes"]), 3)

    def test_missing_template_cycle_and_unsupported_root_override_fail_closed(self):
        for manifest, code in ((_manifest(missing=True), "SYNC_PREFAB_TEMPLATE_MISSING"),
                               (_manifest(cycle=True), "SYNC_PREFAB_CYCLE"),
                               (_manifest(unsupported=True), "SYNC_PREFAB_OVERRIDE_UNSUPPORTED")):
            with self.subTest(code=code), self.assertRaisesRegex(SyncPrefabError, code):
                bind_sync_prefab_instances(_plan(), manifest)

    def test_creator3_native_relationships_are_untouched(self):
        plan = {"prefabInstances": [{"root": "creator3#root", "template": "creator3#template", "nodes": []}]}
        self.assertEqual(bind_sync_prefab_instances(plan, None, source_profile="cocos-3.8.7-bundle"), plan)

    def test_resource_only_plan_skips_but_node_graph_requires_manifest(self):
        self.assertFalse(needs_sync_prefab_binding({"assets": [{"sourceId": "asset:only"}], "nodes": [], "sourcePrefabs": []}))
        node_plan = {"nodes": [{"sourceId": "source#1"}], "sourcePrefabs": []}
        self.assertTrue(needs_sync_prefab_binding(node_plan))
        with self.assertRaisesRegex(SyncPrefabError, "SYNC_PREFAB_MANIFEST_PIN"):
            load_verified_source_manifest(None, None, "cocos-2.4.15-bundle")

    def test_existing_24_relationship_is_preserved_alongside_sync_edge(self):
        plan = _plan()
        plan["nodes"].append(dict(sourceId="bundle:b#child", name="old child", parent="bundle:b#1", children=[], components=[],
                                   active=True, position=[0, 0, 0], rotation=[0, 0, 0, 1], scale=[1, 1, 1], size=[1, 1], anchor=[.5, .5]))
        b_root = next(n for n in plan["nodes"] if n["sourceId"] == "bundle:b#1")
        b_root["children"] = ["bundle:b#child"]
        b_spec = next(p for p in plan["sourcePrefabs"] if p["sourceId"] == "bundle:b")
        b_spec["nodes"].append("bundle:b#child"); b_spec["nodeCount"] += 1
        source_ir = {"prefabInstances": [{"root": "bundle:b#1", "template": "bundle:t", "sourceInstanceFileId": "legacy-file",
                                           "objects": [{"instanceObject": "bundle:b#1", "templateObject": "bundle:t#1"},
                                                       {"instanceObject": "bundle:b#child", "templateObject": "bundle:t#2"}]}]}
        _, original_native = native_relationships({"nodes": plan["nodes"], "components": plan["components"],
                                                   "prefabInstances": source_ir["prefabInstances"]},
                                                  plan["sourcePrefabs"], plan["components"])
        plan["prefabInstances"] = original_native
        manifest = _manifest()
        next(a for a in manifest["assets"] if a["sourceId"] == "bundle:b")["document"]["instances"][1]["_prefab"]["sync"] = False
        result = bind_sync_prefab_instances(plan, manifest, source_ir=source_ir, source_profile="cocos-2.4.15-bundle")
        roots = {row["root"] for row in result["prefabInstances"]}
        self.assertEqual(roots, {"bundle:a#1", "bundle:b#1"})

    def test_manifest_hash_and_profile_are_pinned(self):
        raw = json.dumps({"sourceProfile": "cocos-2.4.15-bundle", "assets": []}).encode()
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            path = Path(directory) / "source-manifest.json"
            path.write_bytes(raw)
            loaded = load_verified_source_manifest(path, hashlib.sha256(raw).hexdigest(), "cocos-2.4.15-bundle")
            self.assertEqual(loaded["assets"], [])
            with self.assertRaisesRegex(SyncPrefabError, "SYNC_PREFAB_MANIFEST_HASH"):
                load_verified_source_manifest(path, "0" * 64, "cocos-2.4.15-bundle")
            with self.assertRaisesRegex(SyncPrefabError, "SYNC_PREFAB_MANIFEST_PROFILE"):
                load_verified_source_manifest(path, hashlib.sha256(raw).hexdigest(), "cocos-2.4.15-project")


if __name__ == "__main__":
    unittest.main()
