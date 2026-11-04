import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from monkey.prefab_static_toggle import StaticToggleError, prepare


def fixture():
    asset_id = "gameAsset:asset-a"
    objects = [
        {"__type__": "cc.Scene", "_children": [{"__id__": 1}]},
        {"__type__": "cc.Node", "_name": "renamed", "_parent": {"__id__": 0}, "_children": [{"__id__": 2}], "_components": [{"__id__": 4}]},
        {"__type__": "cc.Node", "_name": "toggle", "_parent": {"__id__": 1}, "_components": [{"__id__": 3}, {"__id__": 5}]},
        {"__type__": "cc.Sprite", "node": {"__id__": 2}},
        {"__type__": "cc.ToggleContainer", "node": {"__id__": 1}, "allowSwitchOff": True, "checkEvents": [{"handler": "onCheck"}]},
        {"__type__": "cc.Toggle", "node": {"__id__": 2}, "_N$isChecked": False, "_N$interactable": True,
         "_N$target": {"__id__": 2}, "checkMark": {"__id__": 3}, "_N$transition": 2,
         "_N$normalColor": {"__value_type__": 4, "values": [0x80402010]}, "checkEvents": [{"handler": "business"}]},
    ]
    manifest = {"sourceProfile": "test", "assets": [{"sourceId": asset_id, "document": {"instances": objects}}]}
    raw = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
    group = asset_id + "#4"
    toggle = asset_id + "#5"
    sprite = asset_id + "#3"
    plan = {
        "sourceManifestSha256": hashlib.sha256(raw).hexdigest(),
        "nodes": [
            {"sourceId": asset_id + "#1", "parent": asset_id + "#0"},
            {"sourceId": asset_id + "#2", "parent": asset_id + "#1"},
        ],
        "components": [
            {"sourceId": group, "node": asset_id + "#1", "type": "cc.ToggleContainer"},
            {"sourceId": toggle, "node": asset_id + "#2", "type": "cc.Toggle"},
            {"sourceId": sprite, "node": asset_id + "#2", "type": "cc.Sprite"},
        ],
    }
    return raw, manifest, plan, {"group": group, "toggle": toggle, "sprite": sprite, "asset": asset_id}


class StaticToggleTests(unittest.TestCase):
    def run_prepare(self, raw, plan):
        temporary = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / "manifest.json"
        source.write_bytes(raw)
        spec = prepare(source, plan, "creator", root / "out")
        return spec, root

    def test_preserves_static_fields_refs_events_and_ancestor_binding(self):
        raw, _, plan, ids = fixture()
        spec, root = self.run_prepare(raw, plan)
        toggle = spec["bindings"][ids["toggle"]]
        group = spec["bindings"][ids["group"]]
        self.assertEqual(toggle["checkedValue"], False)
        self.assertTrue(toggle["interactableValue"])
        self.assertEqual(toggle["checkMarkSourceId"], ids["sprite"])
        self.assertEqual(toggle["targetSourceId"], ids["asset"] + "#2")
        self.assertTrue(toggle["targetHasSourceRenderer"])
        self.assertEqual(toggle["targetRendererSourceIds"], [ids["sprite"]])
        self.assertTrue(toggle["zoomScaleSourceDefaultVerified"])
        self.assertEqual(toggle["zoomScaleValue"], 1.2)
        self.assertEqual(toggle["groupSourceId"], ids["group"])
        self.assertEqual(toggle["normalColorValue"], {"r": 16, "g": 32, "b": 64, "a": 128, "packed": 0x80402010})
        self.assertEqual(toggle["transitionValue"], 2)
        self.assertTrue(toggle["staticComplete"])
        self.assertIn("dynamic_toggle_events_not_executed", toggle["gaps"])
        self.assertIn("dynamic_toggle_container_events_not_executed", group["gaps"])
        self.assertIn('"handler":"business"', toggle["dynamicEventsJson"])
        self.assertTrue((root / "out" / "toggle-bindings.json").is_file())

    def test_target_renderer_evidence_distinguishes_graphic_from_grouping_node_and_button_coexistence(self):
        raw, manifest, plan, ids = fixture()
        objects = manifest["assets"][0]["document"]["instances"]
        # Same GameObject has both Button and Toggle, but the referenced target
        # is a grouping node with no source renderer. Its exact identity must be
        # retained while native targetGraphic remains null.
        objects[2]["_components"].append({"__id__": 6})
        objects.append({"__type__": "cc.Button", "node": {"__id__": 2}})
        self.assertEqual(objects[5]["node"]["__id__"], objects[6]["node"]["__id__"])
        objects[5]["_N$target"] = {"__id__": 1}
        raw = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
        plan["sourceManifestSha256"] = hashlib.sha256(raw).hexdigest()
        spec, _ = self.run_prepare(raw, plan)
        toggle = spec["bindings"][ids["toggle"]]
        self.assertFalse(toggle["targetHasSourceRenderer"])
        self.assertEqual(toggle["targetRendererSourceIds"], [])
        self.assertEqual(toggle["targetSourceId"], ids["asset"] + "#1")

        # A Sprite attached directly to the target node requires an actual
        # native Graphic; it cannot take the grouping-node null-target path.
        objects[5]["_N$target"] = {"__id__": 2}
        raw = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
        plan["sourceManifestSha256"] = hashlib.sha256(raw).hexdigest()
        spec, _ = self.run_prepare(raw, plan)
        toggle = spec["bindings"][ids["toggle"]]
        self.assertTrue(toggle["targetHasSourceRenderer"])
        self.assertEqual(toggle["targetRendererSourceIds"], [ids["asset"] + "#3"])

        # A non-UI renderer also blocks the null-target fallback; it cannot
        # satisfy targetGraphic unless target import maps it to a Graphic.
        objects[5]["_N$target"] = {"__id__": 1}
        objects[1]["_components"].append({"__id__": 7})
        objects.append({"__type__": "cc.Graphics", "node": {"__id__": 1}})
        raw = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
        plan["sourceManifestSha256"] = hashlib.sha256(raw).hexdigest()
        spec, _ = self.run_prepare(raw, plan)
        toggle = spec["bindings"][ids["toggle"]]
        self.assertTrue(toggle["targetHasSourceRenderer"])
        self.assertEqual(toggle["targetRendererSourceIds"], [ids["asset"] + "#7"])

    def test_inherited_button_zoom_scale_is_source_mapped_and_defaults_are_pinned(self):
        raw, manifest, plan, ids = fixture()
        manifest["assets"][0]["document"]["instances"][5]["zoomScale"] = 0.9
        raw = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
        plan["sourceManifestSha256"] = hashlib.sha256(raw).hexdigest()
        spec, _ = self.run_prepare(raw, plan)
        toggle = spec["bindings"][ids["toggle"]]
        self.assertTrue(toggle["zoomScalePresent"])
        self.assertFalse(toggle["zoomScaleSourceDefaultVerified"])
        self.assertEqual(toggle["zoomScaleValue"], 0.9)
        self.assertTrue(toggle["staticComplete"])
        self.assertNotIn("source_fields_preserved_not_native_mapped:zoomScale", toggle["staticGaps"])
        self.assertIn("inherited Toggle.zoomScale; default 1.2", toggle["sourceDefaultsEvidence"]["CCButton.zoomScale"])
        source_fields = json.loads(toggle["sourceFieldsJson"])
        self.assertEqual(source_fields["_N$transition"], 2)
        self.assertEqual(source_fields["_N$target"], {"__id__": 2})
        self.assertNotIn("duration", source_fields)
        self.assertIn("duration 0.1", toggle["sourceDefaultsEvidence"]["CCButton.js"])

        manifest["assets"][0]["document"]["instances"][5].pop("zoomScale")
        raw = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
        plan["sourceManifestSha256"] = hashlib.sha256(raw).hexdigest()
        spec, _ = self.run_prepare(raw, plan)
        toggle = spec["bindings"][ids["toggle"]]
        self.assertFalse(toggle["zoomScalePresent"])
        self.assertTrue(toggle["zoomScaleSourceDefaultVerified"])
        self.assertEqual(toggle["zoomScaleValue"], 1.2)

    def test_source_engine_defaults_are_explicitly_verified(self):
        raw, manifest, plan, ids = fixture()
        toggle_raw = manifest["assets"][0]["document"]["instances"][5]
        toggle_raw.pop("_N$isChecked")
        toggle_raw.pop("_N$interactable")
        toggle_raw.pop("_N$transition")
        toggle_raw.pop("_N$normalColor")
        manifest["assets"][0]["document"]["instances"][4].pop("allowSwitchOff")
        raw = json.dumps(manifest, separators=(",", ":")).encode()
        plan["sourceManifestSha256"] = hashlib.sha256(raw).hexdigest()
        spec, _ = self.run_prepare(raw, plan)
        row = spec["bindings"][ids["toggle"]]
        self.assertFalse(row["checkedPresent"])
        self.assertTrue(row["checkedSourceDefaultVerified"])
        self.assertTrue(row["checkedValue"])
        self.assertTrue(row["interactableSourceDefaultVerified"])
        self.assertTrue(row["interactableValue"])
        self.assertTrue(row["transitionSourceDefaultVerified"])
        self.assertEqual(row["transitionValue"], 0)
        self.assertTrue(row["normalColorSourceDefaultVerified"])
        self.assertEqual(row["normalColorValue"]["a"], 255)
        container = spec["bindings"][ids["group"]]
        self.assertTrue(container["allowSwitchOffSourceDefaultVerified"])
        self.assertFalse(container["allowSwitchOffValue"])
        self.assertTrue(container["staticComplete"])
        self.assertIn("dynamic_toggle_container_events_not_executed", container["gaps"])
        self.assertTrue(all(item["category"] == "dynamic" for item in spec["diagnostics"]))

    def test_source_scale_transition_is_retained_but_inactive_on_unity(self):
        raw, manifest, plan, ids = fixture()
        manifest["assets"][0]["document"]["instances"][5]["_N$transition"] = 3
        raw = json.dumps(manifest, separators=(",", ":")).encode()
        plan["sourceManifestSha256"] = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            path = Path(directory) / "manifest.json"
            path.write_bytes(raw)
            unity = prepare(path, plan, "unity", Path(directory) / "out")
        unity_row = unity["bindings"][ids["toggle"]]
        self.assertEqual(unity_row["transitionValue"], 3)
        self.assertTrue(unity_row["staticComplete"])
        self.assertEqual(unity_row["unityTransition"], "None")
        self.assertIn("disabled static carrier", unity_row["targetTransitionMapping"])

        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            path = Path(directory) / "manifest.json"
            path.write_bytes(raw)
            creator = prepare(path, plan, "creator", Path(directory) / "out")
        creator_row = creator["bindings"][ids["toggle"]]
        self.assertEqual(creator_row["transitionValue"], 3)
        self.assertTrue(creator_row["staticComplete"])

    def test_bad_refs_and_duplicate_toggle_are_rejected(self):
        raw, manifest, plan, ids = fixture()
        manifest["assets"][0]["document"]["instances"][5]["checkMark"] = {"__id__": 999}
        raw = json.dumps(manifest, separators=(",", ":")).encode()
        plan["sourceManifestSha256"] = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            path = Path(directory) / "manifest.json"
            path.write_bytes(raw)
            with self.assertRaises(StaticToggleError):
                prepare(path, plan, "unity", Path(directory) / "out")
        raw, _, plan, ids = fixture()
        manifest = json.loads(raw)
        manifest["assets"][0]["document"]["instances"].append(
            {"__type__": "cc.Toggle", "node": {"__id__": 2}, "_N$isChecked": True})
        raw = json.dumps(manifest, separators=(",", ":")).encode()
        plan["sourceManifestSha256"] = hashlib.sha256(raw).hexdigest()
        plan["components"].append({"sourceId": ids["asset"] + "#6", "node": ids["asset"] + "#2", "type": "cc.Toggle"})
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            path = Path(directory) / "manifest.json"
            path.write_bytes(raw)
            with self.assertRaises(StaticToggleError):
                prepare(path, plan, "unity", Path(directory) / "out")

    def test_direct_parent_container_is_bound_and_a_missing_plan_group_fails_closed(self):
        raw, _, plan, ids = fixture()
        spec, _ = self.run_prepare(raw, plan)
        toggle = spec["bindings"][ids["toggle"]]
        self.assertEqual(toggle["groupSourceId"], ids["group"])
        self.assertEqual(toggle["groupNodeSourceId"], ids["asset"] + "#1")

        missing_group_plan = json.loads(json.dumps(plan))
        missing_group_plan["components"] = [row for row in missing_group_plan["components"]
                                             if row["sourceId"] != ids["group"]]
        with self.assertRaisesRegex(StaticToggleError, "parent ToggleContainer is missing or ambiguous"):
            self.run_prepare(raw, missing_group_plan)

    def test_ancestor_container_does_not_capture_toggle_when_direct_parent_has_none(self):
        raw, manifest, plan, ids = fixture()
        objects = manifest["assets"][0]["document"]["instances"]
        objects[1]["_children"] = [{"__id__": 6}]
        objects[2]["_parent"] = {"__id__": 6}
        objects.append({"__type__": "cc.Node", "_name": "intermediate", "_parent": {"__id__": 1},
                        "_children": [{"__id__": 2}], "_components": []})
        raw = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
        plan["sourceManifestSha256"] = hashlib.sha256(raw).hexdigest()
        plan["nodes"].append({"sourceId": ids["asset"] + "#6", "parent": ids["asset"] + "#1"})
        next(row for row in plan["nodes"] if row["sourceId"] == ids["asset"] + "#2")["parent"] = ids["asset"] + "#6"
        spec, _ = self.run_prepare(raw, plan)
        toggle = spec["bindings"][ids["toggle"]]
        self.assertIsNone(toggle["groupSourceId"])
        self.assertTrue(toggle["staticComplete"])

    def test_explicit_legacy_toggle_group_is_not_replaced_by_parent_container(self):
        raw, manifest, plan, ids = fixture()
        objects = manifest["assets"][0]["document"]["instances"]
        objects[1]["_components"].append({"__id__": 6})
        objects[5]["toggleGroup"] = {"__id__": 6}
        objects.append({"__type__": "cc.ToggleGroup", "node": {"__id__": 1}})
        raw = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
        plan["sourceManifestSha256"] = hashlib.sha256(raw).hexdigest()
        plan["components"].append({"sourceId": ids["asset"] + "#6", "node": ids["asset"] + "#1", "type": "cc.ToggleGroup"})
        spec, _ = self.run_prepare(raw, plan)
        toggle = spec["bindings"][ids["toggle"]]
        self.assertTrue(toggle["explicitToggleGroupPresent"])
        self.assertIsNone(toggle["groupSourceId"])
        self.assertIn("explicit_toggle_group_reference_unsupported", toggle["staticGaps"])
    def test_manifest_hash_mismatch_is_rejected(self):
        raw, _, plan, _ = fixture()
        plan["sourceManifestSha256"] = "0" * 64
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            path = Path(directory) / "manifest.json"
            path.write_bytes(raw)
            with self.assertRaises(StaticToggleError):
                prepare(path, plan, "creator", Path(directory) / "out")

    def test_native_helpers_are_static_disabled_and_expose_readback(self):
        base = Path(__file__).resolve().parents[1]
        unity = (base / "src/monkey/targets/UnityStaticToggle.cs").read_text()
        creator = (base / "src/monkey/targets/CreatorStaticToggle.js").read_text()
        for text in (unity, creator):
            self.assertIn("dynamicBehaviorComplete", text)
            self.assertIn("Read(", text)
            self.assertIn("enabled = false", text)
            self.assertNotIn("onValueChanged.AddListener", text)
            self.assertNotIn("checkEvents", text)
        self.assertIn("SetIsOnWithoutNotify", unity)
        self.assertIn("setIsCheckedWithoutNotify", creator)

    def test_unity_toggle_requires_graphic_for_source_renderer_and_retains_nonrender_target(self):
        base = Path(__file__).resolve().parents[1]
        unity = (base / "src/monkey/targets/UnityStaticToggle.cs").read_text()
        creator = (base / "src/monkey/targets/CreatorStaticToggle.js").read_text()
        marker = (base / "src/monkey/targets/NativeStaticButtonTarget.cs").read_text()
        apply = unity.split("public static Readback Read(", 1)[0]
        self.assertLess(apply.index("toggle.graphic = image"), apply.index("toggle.SetIsOnWithoutNotify"))
        self.assertLess(apply.index("toggle.group = group"), apply.index("toggle.SetIsOnWithoutNotify"))
        self.assertIn("toggle.graphic.gameObject.SetActive(row.checkedValue)", apply)
        self.assertIn("toggle.graphic.canvasRenderer.SetAlpha(row.checkedValue ? 1f : 0f)", apply)
        self.assertIn("toggle.graphic.gameObject.activeSelf", unity)
        self.assertNotIn("canvasRenderer.GetAlpha()", unity)
        self.assertIn("if (row.targetHasSourceRenderer)", apply)
        self.assertIn("row.sourceId + \":target_graphic_unresolved\"", apply)
        self.assertIn("retained.SourceToggleTarget = targetNode", apply)
        self.assertIn("retained.HasSourceToggleTarget = true", apply)
        self.assertIn("retained.SourceToggleZoomScale = row.zoomScaleValue", apply)
        self.assertIn("retained.HasSourceToggleZoomScale = true", apply)
        self.assertIn("retained.SourceToggleTarget == targetNode", unity)
        self.assertIn("public GameObject SourceToggleTarget", marker)
        self.assertIn("public bool HasSourceToggleTarget", marker)
        self.assertIn("public float SourceToggleZoomScale", marker)
        self.assertIn("retained.SourceToggleZoomScale - row.zoomScaleValue", unity)
        self.assertNotIn("retained.Target =", apply)
        self.assertNotIn("retained.SourceEnabled =", apply)
        self.assertIn("targetGraphic && toggle.targetGraphic == targetGraphic", unity)
        self.assertLess(unity.index("row.kind != \"cc.ToggleContainer\" || invalidGroupIds"),
                        unity.index("row == null || row.kind == \"cc.ToggleContainer\") continue"))
        self.assertIn("toggle.group == group", unity)
        self.assertIn("node.parent === groupNode", creator)
        self.assertIn("toggle.zoomScale = row.zoomScaleValue", creator)
        self.assertIn("toggle.zoomScale === row.zoomScaleValue", creator)


if __name__ == "__main__":
    unittest.main()
