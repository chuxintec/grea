import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.monkey.prefab_static_sort_queue import (StaticSortQueueError, build_queue, for_root, prepare,
                                                to_creator_proxy_spec, to_unity_proxy_spec)


def node(source_id, parent=None, children=None):
    return {"sourceId": source_id, "parent": parent, "children": list(children or []), "active": True}


def component(source_id, node_id, kind, **fields):
    return {"sourceId": source_id, "nativeId": source_id, "node": node_id,
            "type": kind, "enabled": True, **fields}


def _hash_bound_fixture(directory):
    """Create a neutral Cocos-like prefab and exact on-disk manifest binding."""
    manifest_path = Path(directory) / "source-manifest.json"
    instances = [
        {"__type__": "cc.Node", "_name": "Root", "_components": [], "_children": []},
        {"__type__": "cc.Node", "_name": "Before", "_components": [], "_children": []},
        {"__type__": "cc.Node", "_name": "Mask", "_components": [], "_children": []},
        {"__type__": "cc.Node", "_name": "Inside", "_components": [], "_children": []},
        {"__type__": "cc.Node", "_name": "After", "_components": [], "_children": []},
    ]
    nodes = [node("root", children=["before", "mask", "after"]),
             node("before", "root"), node("mask", "root", ["inside"]),
             node("inside", "mask"), node("after", "root")]
    component_specs = [
        ("before", "cc.Sprite", {}),
        ("before", "cc.SortOrder", {"_sortOrder": 5}),
        ("mask", "cc.Mask", {"_type": 0, "_N$inverted": False, "_N$alphaThreshold": 0.25}),
        ("inside", "cc.Label", {}),
        ("inside", "cc.SortOrder", {"_sortOrder": 2}),
        ("after", "cc.Sprite", {}),
        ("after", "cc.SortOrder", {"_sortOrder": 1}),
    ]
    instance_index = {"root": 0, "before": 1, "mask": 2, "inside": 3, "after": 4}
    plan_rows = []
    for ordinal, (node_id, kind, fields) in enumerate(component_specs):
        raw_index = len(instances)
        raw = {"__type__": kind, **fields}
        instances.append(raw)
        local_ordinal = len(instances[instance_index[node_id]]["_components"])
        instances[instance_index[node_id]]["_components"].append({"__id__": raw_index})
        source_id = f"fixture:prefab#{instance_index[node_id]}/components/{local_ordinal}"
        plan_rows.append(component(source_id, node_id, kind, **({"maskType": 0, "inverted": False, "convertible": True}
                              if kind == "cc.Mask" else fields if kind == "cc.SortOrder" else
                              {"needsSpriteBinding": True} if kind == "cc.Sprite" else {})))
    document = {"root": 0, "instances": instances}
    manifest = {"schemaVersion": 1, "assets": [{"sourceId": "fixture:prefab", "bundle": "fixture",
                "kind": "cc.Prefab", "document": document}], "inputs": []}
    raw_manifest = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    manifest_path.write_bytes(raw_manifest)
    plan = {"namespace": "neutral-sort-queue-fixture",
            "sourceManifestPath": str(manifest_path),
            "sourceManifestSha256": hashlib.sha256(raw_manifest).hexdigest(),
            "nodes": nodes, "components": plan_rows,
            "sourcePrefabs": [{"sourceId": "fixture:prefab", "root": "root",
                               "path": "Assets/Game/Prefabs/Neutral.prefab",
                               "nativeRootName": "Root"}],
            "copies": []}
    return plan, manifest, manifest_path


class StaticSortQueueTests(unittest.TestCase):
    def test_parent_background_precedes_descendant_content_with_equal_sort_keys(self):
        # Normal Cocos RenderFlow submits a parent's Sprite before descending
        # into its Label/Sprite children; postorder would cover all content.
        nodes = [node("root", children=["panel", "overlay"]),
                 node("panel", "root", ["title", "button"]),
                 node("title", "panel", ["text"]), node("text", "title"),
                 node("button", "panel"), node("overlay", "root")]
        rows = [component("panel-sprite", "panel", "cc.Sprite"),
                component("title-sprite", "title", "cc.Sprite"),
                component("title-label", "text", "cc.Label"),
                component("button-sprite", "button", "cc.Sprite"),
                component("overlay-sprite", "overlay", "cc.Sprite")]
        result = build_queue({"nodes": nodes, "components": rows})
        self.assertEqual(["panel", "title", "text", "button", "overlay"],
                         [row["node"] for row in result["queueByRoot"]["root"]])
        # Explicit source sort values remain authoritative over equal-key DFS.
        rows.append(component("panel-order", "panel", "cc.SortOrder", sourceSortOrder=2))
        sorted_result = build_queue({"nodes": nodes, "components": rows})
        self.assertEqual(["title", "text", "button", "overlay", "panel"],
                         [row["node"] for row in sorted_result["queueByRoot"]["root"]])

    def test_creator_empty_graphics_retains_original_event_and_typed_no_draw_mapping(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            plan, manifest, manifest_path = _hash_bound_fixture(temp)
            root_instance = manifest["assets"][0]["document"]["instances"][0]
            raw_index = len(manifest["assets"][0]["document"]["instances"])
            root_instance["_components"].append({"__id__": raw_index})
            manifest["assets"][0]["document"]["instances"].append({"__type__": "cc.Graphics",
                "_materials": [{"__uuid__": "fixture-graphics-material"}], "node": {"__id__": 0}})
            source_id = "fixture:prefab#0/components/0"
            plan["components"].append(component(source_id, "root", "cc.Graphics", staticControlBinding={
                "sourceDrawingCommands": "not-serialized-empty-in-fixed-state",
                "materials": [{"sourceId": "fixture-graphics-material", "unityMaterialGuid": "fixture-unity-material",
                    "nativeCreatorMaterialLookup": "builtin-graphics"}]}))
            raw_manifest = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            manifest_path.write_bytes(raw_manifest)
            plan["sourceManifestSha256"] = hashlib.sha256(raw_manifest).hexdigest()

            creator = to_creator_proxy_spec(plan, manifest, "root")
            unity = to_unity_proxy_spec(plan, manifest, "root")
            original_event = next((index, event) for index, event in enumerate(creator["sourceOriginalDrawEvents"])
                                  if event["kind"] == "renderer" and event["sourceComponentId"] == source_id)
            self.assertNotIn(source_id, {event["sourceComponentId"] for event in creator["sourceDrawEvents"]
                                         if event["kind"] == "renderer"})
            row = next(row for row in creator["nonDrawRenderers"] if row["sourceId"] == source_id)
            mapping = next(row for row in creator["sourceNonDrawRenderers"] if row["sourceComponentId"] == source_id)
            self.assertEqual("empty-command-stream", row["noDrawReason"])
            self.assertFalse(row["nativeEnabledExpected"])
            self.assertEqual("not-serialized-empty-in-fixed-state", row["sourceDrawingCommands"])
            self.assertEqual("source-render-event", mapping["disposition"])
            self.assertEqual(original_event[0], mapping["sourceEventIndex"])
            self.assertIn(source_id, {event["sourceComponentId"] for event in unity["drawEvents"]
                                      if event["kind"] == "renderer"})

    def test_creator_null_sprite_policy_must_agree_with_source_binding(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            plan, manifest, _ = _hash_bound_fixture(temp)
            sprite = next(row for row in plan["components"] if row["type"] == "cc.Sprite")
            sprite["needsSpriteBinding"] = False
            with self.assertRaisesRegex(ValueError, "null source frame conflicts with native binding policy"):
                to_creator_proxy_spec(plan, manifest, "root")

    def test_creator_nonempty_source_sprite_reference_cannot_pass_as_no_draw(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            plan, manifest, manifest_path = _hash_bound_fixture(temp)
            raw = next(row for row in manifest["assets"][0]["document"]["instances"]
                       if isinstance(row, dict) and row.get("__type__") == "cc.Sprite")
            raw["_spriteFrame"] = {"__uuid__": "source-frame-uuid"}
            raw_manifest = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            manifest_path.write_bytes(raw_manifest)
            plan["sourceManifestSha256"] = hashlib.sha256(raw_manifest).hexdigest()
            sprite = next(row for row in plan["components"] if row["type"] == "cc.Sprite")
            sprite["needsSpriteBinding"] = True
            with self.assertRaisesRegex(ValueError, "source reference is nonempty but its native binding is unresolved"):
                to_creator_proxy_spec(plan, manifest, "root")

    def test_hash_bound_neutral_manifest_emits_both_proxy_specs_and_mask_queue(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            plan, manifest, manifest_path = _hash_bound_fixture(temp)
            result = prepare(plan, manifest)
            self.assertEqual(result["sourceManifestSha256"], plan["sourceManifestSha256"])
            self.assertEqual(["root"], result["roots"])
            root = for_root(result, "root")
            self.assertTrue(root["nativeRanks"])
            self.assertTrue(root["unityMasks"])
            self.assertTrue(all(mask["sourceFieldsJson"] for mask in root["unityMasks"]))
            self.assertTrue(root["sourceDrawEvents"])
            self.assertTrue(any(event[0] == "maskEnter" for event in root["sourceDrawEvents"]))

            unity_spec = to_unity_proxy_spec(plan, manifest, "root")
            creator_spec = to_creator_proxy_spec(plan, manifest, "root")
            self.assertEqual(plan["sourceManifestSha256"], unity_spec["sourceManifestSha256"])
            self.assertEqual(plan["sourceManifestSha256"], creator_spec["sourceManifestSha256"])
            self.assertTrue(unity_spec["prefabPath"].startswith("Assets/"))
            self.assertIn("sourceFields", unity_spec)
            self.assertIn("sourceSortRoots", unity_spec)
            self.assertTrue(unity_spec["unityProxyTree"]["children"])
            sprite_row = next(row for row in unity_spec["renderers"] if row["sourceType"] == "cc.Sprite")
            self.assertTrue(sprite_row["sourceEnabled"])
            self.assertFalse(sprite_row["sourceTextureBound"])
            label_row = next(row for row in unity_spec["renderers"] if row["sourceType"] == "cc.Label")
            self.assertTrue(label_row["sourceTextEmpty"])
            self.assertTrue(creator_spec["sourceDrawEvents"])
            self.assertTrue(creator_spec["masks"])
            null_sprite = next(row for row in creator_spec["nonDrawRenderers"] if row["sourceType"] == "cc.Sprite")
            self.assertTrue(null_sprite["sourceEnabled"])
            self.assertTrue(null_sprite["sourceNeedsSpriteBinding"])
            self.assertFalse(null_sprite["nativeEnabledExpected"])
            self.assertEqual("null-sprite-frame", null_sprite["noDrawReason"])
            self.assertEqual("fixture:prefab", unity_spec["sourcePrefabId"])

            # Manifest bytes are the binding. A changed in-memory or on-disk
            # source document must not be accepted under the frozen plan hash.
            changed = copy.deepcopy(manifest)
            changed["assets"][0]["document"]["instances"][0]["_name"] = "tampered"
            with self.assertRaisesRegex(ValueError, "in-memory manifest differs"):
                prepare(plan, changed)
            manifest_path.write_text(json.dumps(changed, sort_keys=True), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                prepare(plan, changed)

    def test_richtext_is_a_renderer_and_inactive_source_goes_to_typed_non_draw_contract(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            plan, manifest, manifest_path = _hash_bound_fixture(temp)
            # Rebind a neutral Label source object as exact serialized RichText
            # fields, and deactivate another source node while keeping its
            # source component enabled. The latter must remain typed evidence,
            # but must not enter the draw event queue.
            label = next(row for row in plan["components"] if row["type"] == "cc.Label")
            raw = {"__type__": "cc.RichText", "_N$string": "<color=#fff>hi</color>",
                   "node": {"__id__": 3}}
            instances = manifest["assets"][0]["document"]["instances"]
            raw_label = next(index for index, row in enumerate(instances) if isinstance(row, dict) and row.get("__type__") == "cc.Label")
            instances[raw_label] = raw
            label.update({"type": "cc.RichText", "text": "hi", "sourceRichText": raw, "font": "font:fixture",
                          "staticRichText": {"renderReady": True, "serializedSourceText": "hi", "creatorMarkup": "hi",
                              "fontBinding": {"nativeFontAssetId": "native-font-fixture",
                                  "nativeFallbackAssetIds": [], "targetSystemFontFamily": "Arial"}}})
            before = next(row for row in plan["nodes"] if row["sourceId"] == "before")
            before["active"] = False
            manifest_bytes = __import__("json").dumps(manifest, ensure_ascii=False, sort_keys=True,
                separators=(",", ":")).encode("utf-8") + b"\n"
            manifest_path.write_bytes(manifest_bytes)
            plan["sourceManifestSha256"] = hashlib.sha256(manifest_bytes).hexdigest()

            creator = to_creator_proxy_spec(plan, manifest, "root")
            unity = to_unity_proxy_spec(plan, manifest, "root")
            rich = next(row for row in creator["renderers"] if row["sourceType"] == "cc.RichText")
            self.assertEqual("<color=#fff>hi</color>", rich["sourceFields"]["_N$string"])
            self.assertEqual(hashlib.sha256(rich["sourceFieldsJson"].encode("utf-8")).hexdigest(), rich["sourceFieldsSha256"])
            self.assertEqual("native-font-fixture", rich["nativeFontAssetId"])
            self.assertEqual("Arial", rich["targetSystemFontFamily"])
            self.assertTrue(any(row["sourceActive"] is False and row["sourceEnabled"] is True and
                                row["sourceType"] == "cc.Sprite" for row in creator["nonDrawRenderers"]))
            self.assertTrue(any(row["sourceComponentId"] in {x["sourceComponentId"] for x in creator["sourceOriginalDrawEvents"]
                                                               if x["kind"] == "renderer"} and
                                row["disposition"] == "source-render-event" and row["sourceEventIndex"] is not None
                                for row in creator["sourceNonDrawRenderers"]))
            self.assertTrue(any(row["disposition"] == "source-component-only" and row["sourceEventIndex"] is None
                                for row in creator["sourceNonDrawRenderers"]))
            self.assertNotIn("before", [event["node"] for event in creator["sourceDrawEvents"] if event["kind"] == "renderer"])
            unity_rich = next(row for row in unity["renderers"] if row["sourceType"] == "cc.RichText")
            self.assertEqual("TMPro.TextMeshProUGUI", unity_rich["expectedGraphicType"])
            self.assertEqual("hi", unity_rich["sourceText"])
            self.assertTrue(any(row["sourceActive"] is False and row["sourceType"] == "cc.Sprite"
                                for row in unity["nonDrawRenderers"]))

    def test_creator_unresolved_nonempty_sprite_reference_is_a_blocking_gap(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            plan, manifest, manifest_path = _hash_bound_fixture(temp)
            document = manifest["assets"][0]["document"]["instances"]
            sprite = next(row for row in plan["components"] if row["type"] == "cc.Sprite")
            node_index = next(index for index, row in enumerate(document)
                              if row.get("__type__") == "cc.Node" and row.get("_name", "").lower() == sprite["node"].lower())
            component_index = int(sprite["sourceId"].rsplit("/", 1)[1])
            raw_index = document[node_index]["_components"][component_index]["__id__"]
            source_uuid = "fixture-unresolved-sprite-frame"
            document[raw_index]["_spriteFrame"] = {"__uuid__": source_uuid}
            sprite["spriteFrame"] = None
            sprite["needsSpriteBinding"] = True
            raw_manifest = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            manifest_path.write_bytes(raw_manifest)
            plan["sourceManifestSha256"] = hashlib.sha256(raw_manifest).hexdigest()

            with self.assertRaisesRegex(StaticSortQueueError, "source reference is nonempty but its native binding is unresolved"):
                to_creator_proxy_spec(plan, manifest, "root")

    def test_creator_disabled_bound_sprite_keeps_exact_native_frame_asset(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            plan, manifest, manifest_path = _hash_bound_fixture(temp)
            document = manifest["assets"][0]["document"]["instances"]
            sprite = next(row for row in plan["components"] if row["type"] == "cc.Sprite")
            node_index = next(index for index, row in enumerate(document)
                              if row.get("__type__") == "cc.Node" and row.get("_name", "").lower() == sprite["node"].lower())
            component_index = int(sprite["sourceId"].rsplit("/", 1)[1])
            raw_index = document[node_index]["_components"][component_index]["__id__"]
            source_uuid = "fixture-bound-sprite-frame"
            target_uuid = "12345678-1234-4234-8234-1234567890ab"
            document[raw_index]["_spriteFrame"] = {"__uuid__": source_uuid}
            sprite.update({"enabled": False, "spriteFrame": "fixture:frame", "needsSpriteBinding": False})
            plan["assets"] = [{"sourceId": "fixture:frame", "uuid": target_uuid, "kind": "sprite"}]
            raw_manifest = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            manifest_path.write_bytes(raw_manifest)
            plan["sourceManifestSha256"] = hashlib.sha256(raw_manifest).hexdigest()

            creator = to_creator_proxy_spec(plan, manifest, "root")
            row = next(row for row in creator["nonDrawRenderers"] if row["sourceId"] == sprite["sourceId"])
            self.assertEqual("disabled-source", row["noDrawReason"])
            self.assertEqual(source_uuid, row["sourceSpriteFrameUuid"])
            self.assertEqual("fixture:frame", row["sourceSpriteFrameAssetId"])
            self.assertEqual(target_uuid, row["nativeSpriteImageUuidExpected"])
            self.assertFalse(row["sourceNeedsSpriteBinding"])
            self.assertFalse(row["sourceEnabled"])
            self.assertFalse(row["nativeEnabledExpected"])

    def test_creator_valid_bound_sprite_without_optional_flag_defaults_false(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            plan, manifest, manifest_path = _hash_bound_fixture(temp)
            document = manifest["assets"][0]["document"]["instances"]
            sprite = next(row for row in plan["components"] if row["type"] == "cc.Sprite")
            node_index = next(index for index, row in enumerate(document)
                              if row.get("__type__") == "cc.Node" and row.get("_name", "").lower() == sprite["node"].lower())
            component_index = int(sprite["sourceId"].rsplit("/", 1)[1])
            raw_index = document[node_index]["_components"][component_index]["__id__"]
            document[raw_index]["_spriteFrame"] = {"__uuid__": "fixture-bound-frame"}
            sprite["spriteFrame"] = "fixture:frame"
            sprite.pop("needsSpriteBinding")
            image_uuid = "12345678-1234-4234-8234-1234567890ab"
            plan["assets"] = [{"sourceId": "fixture:frame", "uuid": image_uuid, "kind": "sprite"}]
            raw_manifest = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            manifest_path.write_bytes(raw_manifest)
            plan["sourceManifestSha256"] = hashlib.sha256(raw_manifest).hexdigest()

            active = to_creator_proxy_spec(plan, manifest, "root")
            self.assertTrue(any(row["sourceComponentId"] == sprite["sourceId"] for row in active["renderers"]))
            self.assertFalse(any(row["sourceId"] == sprite["sourceId"] for row in active["nonDrawRenderers"]))

            source_node = next(row for row in plan["nodes"] if row["sourceId"] == sprite["node"])
            source_node["active"] = False
            inactive = to_creator_proxy_spec(plan, manifest, "root")
            row = next(row for row in inactive["nonDrawRenderers"] if row["sourceId"] == sprite["sourceId"])
            self.assertFalse(row["sourceNeedsSpriteBinding"])
            self.assertFalse(row["sourceNeedsSpriteBindingDeclared"])
            self.assertEqual("fixture:frame", row["sourceSpriteFrameAssetId"])
            self.assertEqual(image_uuid, row["nativeSpriteImageUuidExpected"])
            self.assertEqual("inactive-source", row["noDrawReason"])
            self.assertTrue(row["nativeEnabledExpected"])

            # The omission is only optional for an existing exact source
            # frame. A null frame still requires explicit source policy.
            plan, manifest, manifest_path = _hash_bound_fixture(temp)
            for component_row in plan["components"]:
                if component_row["type"] == "cc.Sprite":
                    component_row.pop("needsSpriteBinding")
            with self.assertRaisesRegex(StaticSortQueueError, "null source frame conflicts with native binding policy"):
                to_creator_proxy_spec(plan, manifest, "root")

    def test_proxy_plan_rejects_unbalanced_mask_events(self):
        nodes = [node("root", children=["mask"]), node("mask", "root", ["inside"]), node("inside", "mask")]
        rows = [component("mask", "mask", "cc.Mask"), component("sprite", "inside", "cc.Sprite")]
        contract = build_queue({"nodes": nodes, "components": rows})
        contract.update({"sourceManifestSha256": "a" * 64, "nodeRoot": {"root": "root", "mask": "root", "inside": "root"},
                         "sourceChildOrder": {"root": ["mask"], "mask": ["inside"], "inside": []},
                         "sourceNodeActive": {"root": True, "mask": True, "inside": True},
                         "sortOrderOccurrences": [], "sortRootOccurrences": [],
                         "creatorAdapter": "cc.Sorting2D.defaultLayer.compressedStableRenderRank",
                         "unityAdapter": "native-proxy"})
        contract["maskBarriers"][0]["sourceDrawEvents"].pop()
        with self.assertRaisesRegex(StaticSortQueueError, "unclosed source mask block"):
            for_root(contract, "root")

    def test_neutral_nested_mask_and_proxy_events_preserve_source_fields(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            plan, manifest, _ = _hash_bound_fixture(temp)
            contract = prepare(plan, manifest)
            root = for_root(contract, "root")
            mask = root["unityMasks"][0]
            self.assertEqual("cc.Mask", mask["sourceFields"]["__type__"])
            self.assertEqual(0.25, mask["alphaThreshold"])
            proxy = root["unityProxyTree"]
            self.assertEqual("root", proxy["sourceNode"])
            self.assertTrue(any(item["kind"] == "maskGroup" for item in proxy["children"]))
            draws = [event for event in root["sourceDrawEvents"] if event[0] == "renderer"]
            self.assertEqual(3, len(draws))

    def test_two_level_nested_proxy_scope_has_no_duplicate_draw_and_rejects_bad_owner(self):
        # Neutral lifecycle model for A -> nested B -> nested C. Each proxy
        # contains its full prefab closure, so only the active outermost
        # presentation proxy may contribute draws.
        source_draws = {"A": ["a", "b", "c"], "B": ["b", "c"], "C": ["c"]}

        def visible_draws(active):
            return [item for scope in ("A", "B", "C") if active[scope] for item in source_draws[scope]]

        # A initialization disables both nested roots before its proxy draws.
        active = {"A": True, "B": False, "C": False}
        self.assertEqual(visible_draws(active), ["a", "b", "c"])
        # Disabling A restores deepest-to-shallowest; B then suppresses C again.
        active = {"A": False, "B": True, "C": False}
        self.assertEqual(visible_draws(active), ["b", "c"])
        # Missing nested suppression is a concrete duplicate-render negative.
        overlapping = visible_draws({"A": True, "B": True, "C": True})
        self.assertGreater(len(overlapping), len(set(overlapping)))

        def generated_root(marker_kind, marker_owner, actual_parent, presenter_owner, presenter_root):
            return marker_kind == "root" and marker_owner == actual_parent and presenter_owner == marker_owner and presenter_root == actual_parent

        self.assertTrue(generated_root("root", "B", "B", "B", "B"))
        self.assertFalse(generated_root("root", "B", "A", "B", "B"))

    def test_nested_sortroot_flattens_stable_queue_without_mutating_hierarchy(self):
        nodes = [node("root", children=["a", "scope", "b"]), node("a", "root"),
                 node("scope", "root", ["c", "d"]), node("c", "scope"), node("d", "scope"), node("b", "root")]
        rows = [component("sprite-a", "a", "cc.Sprite"), component("sprite-c", "c", "cc.Sprite"),
                component("sprite-d", "d", "cc.Sprite"), component("sprite-b", "b", "cc.Sprite"),
                component("order-a", "a", "cc.SortOrder", sourceSortOrder=5),
                component("order-scope", "scope", "cc.SortOrder", sourceSortOrder=10),
                component("root-scope", "scope", "cc.SortRoot"),
                component("order-c", "c", "cc.SortOrder", sourceSortOrder=6),
                component("order-d", "d", "cc.SortOrder", sourceSortOrder=2)]
        before = copy.deepcopy(nodes)
        result = build_queue({"nodes": nodes, "components": rows})
        order = [r["node"] for r in result["queueByRoot"]["root"] if r["kind"] == "renderer"]
        self.assertEqual(order, ["b", "a", "d", "c"])
        self.assertTrue(result["creatorQueueMapped"])
        self.assertEqual(nodes, before)
        self.assertEqual([r["nativeSortingOrder"] for r in result["nativeRanks"]], [0, 1, 2, 3])

    def test_mask_combined_with_sorting_is_supported_when_queue_barrier_stays_in_place(self):
        nodes = [node("root", children=["mask", "after"]), node("mask", "root", ["inside"]),
                 node("inside", "mask"), node("after", "root")]
        rows = [component("mask", "mask", "cc.Mask"), component("sprite-in", "inside", "cc.Sprite"),
                component("sprite-after", "after", "cc.Sprite"),
                component("sort-after", "after", "cc.SortOrder", sourceSortOrder=8),
                component("sort-inside", "inside", "cc.SortOrder", sourceSortOrder=3)]
        result = build_queue({"nodes": nodes, "components": rows})
        self.assertTrue(result["creatorQueueMapped"])
        self.assertEqual([(r["kind"], r["node"]) for r in result["queueByRoot"]["root"]],
                         [("maskEnter", "mask"), ("renderer", "inside"), ("maskExit", "mask"), ("renderer", "after")])

    def test_mask_block_crossing_a_preceding_renderer_is_not_claimed_as_creator_pass(self):
        nodes = [node("root", children=["before", "mask", "after"]), node("before", "root"),
                 node("mask", "root", ["inside"]), node("inside", "mask"), node("after", "root")]
        rows = [component("sprite-before", "before", "cc.Sprite"), component("mask", "mask", "cc.Mask"),
                component("sprite-in", "inside", "cc.Sprite"), component("sprite-after", "after", "cc.Sprite"),
                component("sort-before", "before", "cc.SortOrder", sourceSortOrder=7),
                component("sort-in", "inside", "cc.SortOrder", sourceSortOrder=3),
                component("sort-after", "after", "cc.SortOrder", sourceSortOrder=9)]
        result = build_queue({"nodes": nodes, "components": rows})
        self.assertFalse(result["creatorQueueMapped"])
        self.assertEqual(result["maskBarriers"][0]["diagnostic"], "CREATOR_MASK_BARRIER_REORDERS_SOURCE_QUEUE")

    def test_multiple_renderers_or_overlapping_structural_components_fail_closed(self):
        nodes = [node("root", children=["both"]), node("both", "root")]
        rows = [component("sprite", "both", "cc.Sprite"), component("skeleton", "both", "sp.Skeleton")]
        with self.assertRaisesRegex(StaticSortQueueError, "multiple source UIRenderers"):
            build_queue({"nodes": nodes, "components": rows})


if __name__ == "__main__":
    unittest.main()
