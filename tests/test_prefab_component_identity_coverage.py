import copy
import json
import unittest

from monkey.prefab_component_coverage import assess


GUID_A = "0123456789abcdef0123456789abcdef"
GUID_B = "fedcba9876543210fedcba9876543210"


def source_component(source_id="asset:panel#2/components/0", node="asset:panel#1", kind="cc.Sprite", **extra):
    defaults = {
        "sourceId": source_id, "node": node, "type": kind,
        "nativeType": "UnityEngine.UI.Image" if kind == "cc.Sprite" else
                      "TMPro.TextMeshProUGUI" if kind in ("cc.Label", "cc.LabelOutline") else kind,
        "enabled": True, "convertible": True, "spriteFrame": "asset:frame" if kind == "cc.Sprite" else None,
    }
    defaults.update(extra)
    return defaults


def target_component(source, guid=GUID_A, local=10, **extra):
    defaults = {
        "sourceId": source["sourceId"], "node": source["node"], "type": source["type"],
        "nativeType": source["nativeType"], "status": "native", "representation": "native-component",
        "componentUuid": f"{guid}:{local}", "guid": guid, "localFileId": local,
        "sourceIdentityVerified": True, "persistent": True, "sourceEnabled": source["enabled"],
        "nativeEnabled": True, "sourceVisible": source["type"] in ("cc.Sprite", "cc.Label", "cc.LabelOutline") and source.get("enabled") is not False, "nativeStaticFieldsVerified": True,
    }
    defaults.update(extra)
    return defaults


def _physical_inventory(targets, node_id):
    grouped = {}
    for target in targets:
        if target.get("node") != node_id:
            continue
        key = (target["guid"].lower(), target["localFileId"])
        row = grouped.get(key)
        if row is None:
            bases = [target["nativeType"]]
            if target["nativeType"] in ("UnityEngine.UI.Image", "UnityEngine.UI.RawImage",
                                         "TMPro.TextMeshProUGUI", "TMPro.TMP_SubMeshUI", "Spine.Unity.SkeletonGraphic"):
                bases.append("UnityEngine.UI.Graphic")
            bases.extend(("UnityEngine.Behaviour", "UnityEngine.Component", "UnityEngine.Object", "System.Object"))
            row = {"guid": target["guid"], "localFileId": target["localFileId"],
                   "componentUuid": target["componentUuid"], "nativeType": target["nativeType"],
                   "persistent": True, "enabledKnown": True, "enabled": target["nativeEnabled"],
                   "nativeBaseTypes": bases, "sourceComponentIds": [], "role": "source-component",
                   "identityOrigin": "direct-observation", "identityPath": [target["componentUuid"]]}
            grouped[key] = row
        if target["sourceId"] not in row["sourceComponentIds"]:
            row["sourceComponentIds"].append(target["sourceId"])
    extras = []
    for index, type_name in enumerate(("UnityEngine.RectTransform", "UnityEngine.CanvasRenderer"), 100):
        local = index
        guid = GUID_B
        extras.append({"guid": guid, "localFileId": local, "componentUuid": f"{guid}:{local}",
                       "nativeType": type_name, "persistent": True, "enabledKnown": True, "enabled": True,
                       "nativeBaseTypes": [type_name, "UnityEngine.Component", "UnityEngine.Object", "System.Object"],
                       "sourceComponentIds": [], "role": "unmapped", "identityOrigin": "direct-observation",
                       "identityPath": [f"{guid}:{local}"]})
    return [*grouped.values(), *extras]


def fixture(sources=None, targets=None):
    sources = sources or [source_component()]
    targets = targets or [target_component(source) for source in sources]
    node_ids = sorted({source["node"] for source in sources})
    plan = {
        "nodes": [{"sourceId": node_id, "parent": None, "active": True, "opacity": 255}
                  for node_id in node_ids],
        "sourcePrefabs": [{"sourceId": "asset:panel", "path": "Assets/panel.prefab", "nodes": node_ids}],
        "components": sources,
        "diagnostics": [],
    }
    node_rows = []
    for node_id in node_ids:
        physical = _physical_inventory(targets, node_id)
        node_rows.append({"sourceId": node_id, "active": True, "parent": None, "opacity": 255,
                          "componentTypes": [row["nativeType"] for row in physical],
                          "physicalObservationScope": "saved-scene-correspondence",
                          "physicalInventoryContract": "monkey-unity-node-physical-components/1",
                          "physicalInventoryPhase": "persistent-saved-reopened-node",
                          "physicalComponents": physical})
    owner_nodes = copy.deepcopy(node_rows)
    for owner_node in owner_nodes:
        owner_node["physicalObservationScope"] = "saved-source-prefab"
    owner = {"sourceId": "asset:panel", "path": "Assets/panel.prefab", "nodes": owner_nodes,
             "components": copy.deepcopy(targets)}
    readback = {
        "nodes": copy.deepcopy(node_rows), "components": copy.deepcopy(targets), "sourcePrefabs": [owner],
        "staticPresentationValidation": {"status": "pass", "components": [
            {"sourceId": source["sourceId"], "sourceVisible": True, "verified": True, "rendered": True}
            for source in sources if source["type"] in ("cc.Sprite", "cc.Label", "cc.LabelOutline")
        ]},
    }
    return plan, readback


class PrefabComponentIdentityCoverageTests(unittest.TestCase):
    def test_owner_and_aggregate_exact_identity_pair_is_accepted(self):
        plan, rb = fixture()
        result = assess(plan, rb, "unity")
        self.assertEqual(result["nativeStaticValidation"], "pass")
        self.assertEqual(result["staticPresentationValidation"]["status"], "pass")
        self.assertEqual(result["components"][0]["nativeComponentReadback"]["localFileId"], 10)

    def test_missing_owner_detail_cannot_be_repaired_by_aggregate(self):
        plan, rb = fixture()
        rb["sourcePrefabs"][0]["components"] = []
        result = assess(plan, rb, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertTrue(any(row["code"] == "COMPONENT_OWNER_DETAIL_MISSING" for row in result["diagnostics"]))

    def test_missing_aggregate_cannot_be_repaired_by_owner_detail(self):
        plan, rb = fixture()
        rb["components"] = []
        result = assess(plan, rb, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertTrue(any(row["code"] == "COMPONENT_TOP_LEVEL_MIRROR_MISSING" for row in result["diagnostics"]))

    def test_top_and_owner_node_or_persistent_identity_must_agree(self):
        plan, rb = fixture()
        rb["components"][0]["node"] = "asset:other#1"
        result = assess(plan, rb, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertTrue(any(row["code"] in ("COMPONENT_SCOPE_IDENTITY_MISMATCH", "COMPONENT_OWNER_NODE_MISMATCH")
                            for row in result["diagnostics"]))

        plan, rb = fixture()
        rb["sourcePrefabs"][0]["components"][0]["localFileId"] = 11
        rb["sourcePrefabs"][0]["components"][0]["componentUuid"] = f"{GUID_A}:11"
        result = assess(plan, rb, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertTrue(any(row["code"] == "COMPONENT_SCOPE_IDENTITY_MISMATCH" for row in result["diagnostics"]))

    def test_unknown_target_id_is_a_partial_identity_result(self):
        plan, rb = fixture()
        rogue = copy.deepcopy(rb["components"][0])
        rogue.update(sourceId="asset:panel#99/components/0", localFileId=99,
                     componentUuid=f"{GUID_B}:99", guid=GUID_B)
        rb["components"].append(rogue)
        result = assess(plan, rb, "unity")
        self.assertEqual(result["nativeStaticValidation"], "partial")
        self.assertTrue(any(row["code"] == "COMPONENT_UNKNOWN_TARGET_SOURCE_ID" for row in result["diagnostics"]))

    def test_two_sprite_sources_cannot_claim_one_physical_identity(self):
        first = source_component("asset:panel#2/components/0")
        second = source_component("asset:panel#2/components/1")
        first_target = target_component(first, GUID_A, 21)
        second_target = target_component(second, GUID_A, 21)
        plan, rb = fixture([first, second], [first_target, second_target])
        result = assess(plan, rb, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertEqual([row["disposition"] for row in result["components"]], ["missing", "missing"])
        self.assertTrue(any(row["code"] == "COMPONENT_PHYSICAL_IDENTITY_ALIAS" for row in result["diagnostics"]))

    def test_disabled_native_renderer_cannot_claim_rendered(self):
        plan, rb = fixture()
        rb["components"][0]["nativeEnabled"] = False
        rb["sourcePrefabs"][0]["components"][0]["nativeEnabled"] = False
        result = assess(plan, rb, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertNotEqual(result["staticPresentationValidation"]["status"], "pass")
        self.assertTrue(any(row["code"] == "VISIBLE_SOURCE_NATIVE_COMPONENT_DISABLED" for row in result["diagnostics"]))
        self.assertTrue(any(row["code"] == "COMPONENT_NATIVE_ENABLED_MISMATCH" for row in result["diagnostics"]))

    def test_source_disabled_component_cannot_be_reopened_enabled(self):
        plan, rb = fixture()
        plan["components"][0]["enabled"] = False
        for row in (rb["components"][0], rb["sourcePrefabs"][0]["components"][0]):
            row["sourceEnabled"] = False
            row["nativeEnabled"] = True
            row["sourceVisible"] = False
        result = assess(plan, rb, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertTrue(any(row["code"] == "COMPONENT_NATIVE_ENABLED_MISMATCH" for row in result["diagnostics"]))

    def test_shared_layout_slots_are_allowed_only_with_distinct_source_bindings(self):
        sources = []
        targets = []
        for index, kind in enumerate(("cc.Layout", "cc.Widget")):
            sid = f"asset:panel#2/components/{index}"
            binding = {"contract": "monkey-static-layout-continuation/1", "sourceComponentId": sid,
                       "sourceNodeId": "asset:panel#1", "physicalNativeType": "NativeStaticLayoutCompletion"}
            source = source_component(sid, kind=kind, nativeType="NativeStaticLayoutCompletion",
                                      staticLayoutContinuationBinding=binding)
            row = target_component(source, GUID_A, 80, nativeType="NativeStaticLayoutCompletion",
                                   representation="native-component-slot", nativeSlotId=sid)
            sources.append(source)
            targets.append(row)
        plan, rb = fixture(sources, targets)
        result = assess(plan, rb, "unity")
        self.assertEqual(result["nativeStaticValidation"], "pass")
        self.assertFalse(any(row["code"] == "COMPONENT_PHYSICAL_IDENTITY_ALIAS" for row in result["diagnostics"]))

    def test_unmapped_graphic_in_saved_physical_inventory_keeps_result_partial(self):
        plan, rb = fixture()
        extra = {"guid": "a" * 32, "localFileId": 404, "componentUuid": "a" * 32 + ":404",
                 "nativeType": "Recovered.UnknownGraphic", "persistent": True, "enabledKnown": True,
                 "enabled": True, "nativeBaseTypes": ["Recovered.UnknownGraphic", "UnityEngine.UI.Graphic"],
                 "sourceComponentIds": [], "role": "unmapped", "identityOrigin": "direct-observation",
                 "identityPath": ["a" * 32 + ":404"]}
        for node in (rb["nodes"][0], rb["sourcePrefabs"][0]["nodes"][0]):
            node["physicalComponents"].append(copy.deepcopy(extra))
            node["componentTypes"].append(extra["nativeType"])
        result = assess(plan, rb, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertNotEqual(result["staticPresentationValidation"]["status"], "pass")
        self.assertTrue(any(row["code"] == "COMPONENT_UNOWNED_NATIVE_GRAPHIC" for row in result["diagnostics"]))

    def test_missing_full_node_inventory_is_explicitly_unverified(self):
        plan, rb = fixture()
        for node in (rb["nodes"][0], rb["sourcePrefabs"][0]["nodes"][0]):
            node.pop("physicalInventoryContract")
            node.pop("physicalInventoryPhase")
            node.pop("physicalComponents")
        result = assess(plan, rb, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertTrue(any(row["code"] == "COMPONENT_PHYSICAL_INVENTORY_UNVERIFIED" for row in result["diagnostics"]))

    def test_malicious_shared_identity_declaration_cannot_alias_two_sprites(self):
        sids = ["asset:panel#2/components/0", "asset:panel#2/components/1"]
        declaration = {"contract": "monkey-source-shared-native-identity/1", "role": "engine-auxiliary",
                       "groupId": "caller-invented", "members": sids, "nativeType": "UnityEngine.UI.Image"}
        sources = [source_component(sid, sharedNativeIdentity=declaration) for sid in sids]
        targets = [target_component(source, GUID_A, 170) for source in sources]
        plan, rb = fixture(sources, targets)
        result = assess(plan, rb, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertTrue(any(row["code"] == "COMPONENT_PHYSICAL_IDENTITY_ALIAS" for row in result["diagnostics"]))

    def test_mask_stencil_graphic_is_allowed_only_with_source_mask_and_saved_fields(self):
        sid = "asset:panel#2/components/0"
        mask_source = source_component(sid, kind="cc.Mask", nativeType="UnityEngine.UI.Mask",
            nativeId="native-mask", maskType=0, inverted=False, alphaThreshold=0.1)
        mask_target = target_component(mask_source, GUID_A, 210, nativeType="UnityEngine.UI.Mask")
        plan, rb = fixture([mask_source], [mask_target])
        plan["sourceManifestSha256"] = "a" * 64
        source_fields_json = json.dumps({"_type": 0}, separators=(",", ":"), sort_keys=True)
        expected_mask = {"sourceId": sid, "sourceOriginId": sid, "node": mask_source["node"],
            "nativeId": "native-mask", "maskType": 0, "enabled": True, "inverted": False,
            "alphaThreshold": 0.1, "sourceFieldsJson": source_fields_json,
            "sourceMaterialId": "source-material", "resolvedSourceMaterialId": "resolved-material",
            "sourceEffectId": "source-effect", "sourceEffectName": "builtin", "sourceEffectDocumentSha256": "b" * 64}
        plan["staticMasks"] = {"schemaVersion": 1, "contract": "", "sourceManifestSha256": plan["sourceManifestSha256"],
                               "masks": [expected_mask]}
        aux_guid = "c" * 32
        aux = {"guid": aux_guid, "localFileId": 211, "componentUuid": f"{aux_guid}:211",
            "nativeType": "UnityEngine.UI.Image", "persistent": True, "enabledKnown": True, "enabled": True,
            "nativeBaseTypes": ["UnityEngine.UI.Image", "UnityEngine.UI.Graphic", "UnityEngine.Behaviour",
                                "UnityEngine.Component", "UnityEngine.Object", "System.Object"],
            "sourceComponentIds": [], "role": "engine-auxiliary", "auxiliaryKind": "mask-stencil-graphic",
            "auxiliaryOwnerComponentUuid": mask_target["componentUuid"], "identityOrigin": "direct-observation",
            "identityPath": [f"{aux_guid}:211"]}
        identity_guid = "d" * 32
        native_mask_identity = {"guid": identity_guid, "localFileId": 212, "componentUuid": f"{identity_guid}:212",
            "nativeType": "Monkey.StaticMaskSort.NativeStaticMaskIdentity", "persistent": True,
            "enabledKnown": False, "enabled": True,
            "nativeBaseTypes": ["Monkey.StaticMaskSort.NativeStaticMaskIdentity", "UnityEngine.MonoBehaviour",
                                "UnityEngine.Behaviour", "UnityEngine.Component", "UnityEngine.Object", "System.Object"],
            "sourceComponentIds": [], "role": "unmapped", "identityOrigin": "direct-observation",
            "identityPath": [f"{identity_guid}:212"]}
        for node in (rb["nodes"][0], rb["sourcePrefabs"][0]["nodes"][0]):
            node["physicalComponents"].extend([copy.deepcopy(aux), copy.deepcopy(native_mask_identity)])
            node["componentTypes"].extend([aux["nativeType"], native_mask_identity["nativeType"]])
        mask_readback = {"sourceId": sid, "node": mask_source["node"], "nativeType": "UnityEngine.UI.Mask",
            "enabled": True, "maskType": 0, "inverted": False, "alphaThreshold": 0.1,
            "sourceFieldsJson": source_fields_json, "verified": True, "persistentIdentityVerified": True,
            "persistentIdentityGuid": identity_guid, "persistentIdentityLocalFileId": 212}
        rb["sourcePrefabs"][0]["staticMaskFields"] = [mask_readback]
        result = assess(plan, rb, "unity")
        self.assertEqual(result["nativeStaticValidation"], "pass")
        self.assertFalse(any(row["code"] == "COMPONENT_UNOWNED_NATIVE_GRAPHIC" for row in result["diagnostics"]))

        bad = copy.deepcopy(rb)
        bad["sourcePrefabs"][0]["staticMaskFields"][0]["persistentIdentityLocalFileId"] = 0
        result = assess(plan, bad, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertTrue(any(row["code"] == "COMPONENT_UNOWNED_NATIVE_GRAPHIC" for row in result["diagnostics"]))

        bad = copy.deepcopy(rb)
        # A wrong auxiliary owner reference cannot be repaired from the role label.
        bad_aux = next(row for row in bad["sourcePrefabs"][0]["nodes"][0]["physicalComponents"]
                       if row.get("auxiliaryKind") == "mask-stencil-graphic")
        bad_aux["auxiliaryOwnerComponentUuid"] = "e" * 32 + ":999"
        result = assess(plan, bad, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertTrue(any(row["code"] in ("COMPONENT_UNOWNED_NATIVE_GRAPHIC", "COMPONENT_PHYSICAL_SCOPE_INVENTORY_MISMATCH")
                            for row in result["diagnostics"]))

    def test_label_outline_shared_text_target_is_explicitly_legal(self):
        label = source_component("asset:panel#2/components/0", kind="cc.Label", text="Hello")
        outline = source_component("asset:panel#2/components/1", kind="cc.LabelOutline", width=1)
        rows = [target_component(label, GUID_A, 90), target_component(outline, GUID_A, 90)]
        plan, rb = fixture([label, outline], rows)
        result = assess(plan, rb, "unity")
        self.assertEqual(result["nativeStaticValidation"], "pass")
        self.assertFalse(any(row["code"] == "COMPONENT_PHYSICAL_IDENTITY_ALIAS" for row in result["diagnostics"]))

    def test_enabled_outline_follows_disabled_unique_label_owner(self):
        label = source_component("asset:panel#2/components/0", kind="cc.Label", enabled=False, text="Hello")
        outline = source_component("asset:panel#2/components/1", kind="cc.LabelOutline", enabled=True, width=1)
        rows = [
            target_component(label, GUID_A, 91, status="disabled", nativeEnabled=False,
                             disabledReason="source-disabled"),
            target_component(outline, GUID_A, 91, status="disabled", nativeEnabled=False,
                             disabledReason="owning-label-disabled", sourceVisible=False),
        ]
        plan, rb = fixture([label, outline], rows)
        result = assess(plan, rb, "unity")
        self.assertFalse(any(row["code"] == "COMPONENT_NATIVE_ENABLED_MISMATCH" for row in result["diagnostics"]))
        self.assertFalse(any(row["code"] == "NATIVE_DISABLED_REASON_UNPROVEN" for row in result["diagnostics"]))
        outline_result = next(row for row in result["components"] if row["sourceId"] == outline["sourceId"])
        self.assertEqual(outline_result["disposition"], "disabled")
        self.assertFalse(outline_result["sourceVisible"])

    def test_label_outline_disabled_owner_cannot_hide_enabled_native_target(self):
        label = source_component("asset:panel#2/components/0", kind="cc.Label", enabled=False, text="Hello")
        outline = source_component("asset:panel#2/components/1", kind="cc.LabelOutline", enabled=True, width=1)
        rows = [
            target_component(label, GUID_A, 92, status="disabled", nativeEnabled=False,
                             disabledReason="source-disabled"),
            target_component(outline, GUID_A, 92, status="native", nativeEnabled=True,
                             sourceVisible=False),
        ]
        plan, rb = fixture([label, outline], rows)
        result = assess(plan, rb, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertTrue(any(row["code"] == "COMPONENT_NATIVE_ENABLED_MISMATCH" for row in result["diagnostics"]))

    def test_owning_label_disabled_reason_cannot_replace_same_physical_identity(self):
        label = source_component("asset:panel#2/components/0", kind="cc.Label", enabled=False, text="Hello")
        outline = source_component("asset:panel#2/components/1", kind="cc.LabelOutline", enabled=True, width=1)
        rows = [
            target_component(label, GUID_A, 93, status="disabled", nativeEnabled=False,
                             disabledReason="source-disabled"),
            target_component(outline, GUID_B, 94, status="disabled", nativeEnabled=False,
                             disabledReason="owning-label-disabled", sourceVisible=False),
        ]
        plan, rb = fixture([label, outline], rows)
        result = assess(plan, rb, "unity")
        self.assertNotEqual(result["nativeStaticValidation"], "pass")
        self.assertTrue(any(row["code"] in ("NATIVE_DISABLED_REASON_UNPROVEN", "COMPONENT_PHYSICAL_IDENTITY_ALIAS",
                                              "COMPONENT_SHARED_IDENTITY_ROLE_INVALID")
                            for row in result["diagnostics"]))


if __name__ == "__main__":
    unittest.main()
