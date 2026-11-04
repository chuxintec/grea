import copy

import pytest

from src.monkey.prefab_static_layout_completion import (
    LayoutCompletionError,
    prepare,
    probe_expected,
    simulate_layout,
    simulate_widget_alignment,
    subset_for_nodes,
    verify_native_probe,
    verify_readback,
)


ASSET = "asset:prefab"


def _plan_and_manifest():
    source_layout_a = {
        "__type__": "cc.Layout", "node": {"__id__": 0}, "_N$layoutType": 1,
        "_resize": 0, "_N$paddingLeft": -2.5, "_N$paddingRight": 3,
        "_N$spacingX": 4, "_N$affectedByScale": True,
    }
    source_layout_b = {
        "__type__": "cc.Layout", "node": {"__id__": 0}, "_N$layoutType": 2,
        "_resize": 0, "_N$paddingTop": 5, "_N$spacingY": 7,
    }
    source_widget = {
        "__type__": "cc.Widget", "node": {"__id__": 0}, "_alignFlags": 4,
        "_bottom": -6, "_originalHeight": 25,
    }
    node = {"__type__": "cc.Node", "_components": [source_layout_a, source_layout_b, source_widget]}
    plan = {
        "sourceManifestSha256": "manifest-sha",
        "nodes": [{"sourceId": f"{ASSET}#0", "scale": [1, -1, 1]}],
        "components": [
            {"sourceId": f"{ASSET}#0/components/0", "node": f"{ASSET}#0", "type": "cc.Layout",
             "convertible": False, "enabled": True, "layoutType": 1, "resize": 0,
             "spacingXY": [4, 0], "padding": [-2.5, 0, 3, 0], "cellSize": [40, 40],
             "startAxis": 0, "horizontalDirection": 0, "verticalDirection": 1, "affectedByScale": True},
            {"sourceId": f"{ASSET}#0/components/1", "node": f"{ASSET}#0", "type": "cc.Layout",
             "convertible": False, "enabled": True, "layoutType": 2, "resize": 0,
             "spacingXY": [0, 7], "padding": [0, 0, 0, 5], "cellSize": [40, 40],
             "startAxis": 0, "horizontalDirection": 0, "verticalDirection": 1, "affectedByScale": False},
            {"sourceId": f"{ASSET}#0/components/2", "node": f"{ASSET}#0", "type": "cc.Widget",
             "convertible": False, "enabled": True, "flags": 4, "margins": [0, -6, 0, 0],
             "absolute": [True] * 4, "center": [0, 0], "centerAbsolute": [True, True],
             "alignMode": 1, "target": None},
        ],
    }
    manifest = {"assets": [{"sourceId": ASSET, "document": {"instances": [node]}}]}
    return plan, manifest


def test_prepare_preserves_multiple_layout_order_raw_fields_and_does_not_mutate_plan():
    plan, manifest = _plan_and_manifest()
    before = copy.deepcopy(plan)
    completion = prepare(plan, manifest)
    assert plan == before
    assert completion["status"] == "native_algorithm_supported"
    assert len(completion["nodes"]) == 1
    node = completion["nodes"][0]
    assert [row["componentOrder"] for row in node["layouts"]] == [0, 1]
    assert node["componentSourceOrder"] == [
        f"{ASSET}#0/components/0", f"{ASSET}#0/components/1", f"{ASSET}#0/components/2"
    ]
    assert node["layouts"][0]["sourceSerializedFields"]["_N$paddingLeft"] == -2.5
    assert node["layouts"][0]["affectedByScale"] is True
    assert node["widgets"][0]["sourceOriginalHeightKnown"] is True
    assert node["initialPoseMustRemainUnchangedDuringPrefabSave"] is True
    assert completion["initialPoseUsedAsConstraintProof"] is False


def test_exact_component_origin_is_required_and_ambiguous_origin_is_partial():
    plan, manifest = _plan_and_manifest()
    plan["syncPrefabBindings"] = [{"componentOrigins": [
        {"instanceSourceId": f"{ASSET}#0/components/0", "templateSourceId": f"{ASSET}#0/components/0"},
        {"instanceSourceId": f"{ASSET}#0/components/0", "templateSourceId": "other#0/components/0"},
    ]}]
    completion = prepare(plan, manifest)
    node = completion["nodes"][0]
    assert node["layouts"][0]["sourceComponentId"] == f"{ASSET}#0/components/1"
    assert any(d["status"] == "source_component_origin_ambiguous" for d in node["diagnostics"])
    assert completion["status"] == "partial"


def test_source_serialized_semantics_override_normalizer_drift_with_explicit_evidence():
    plan, manifest = _plan_and_manifest()
    plan["components"][0]["affectedByScale"] = False
    slot = prepare(plan, manifest)["nodes"][0]["layouts"][0]
    assert slot["affectedByScale"] is True
    assert slot["normalizedPlanMismatch"] == ["_N$affectedByScale"]
    assert slot["sourceSerializedFields"]["_N$affectedByScale"] is True


def test_widget_source_fields_override_plan_drift_without_losing_negative_margin():
    plan, manifest = _plan_and_manifest()
    plan["components"][2]["flags"] = 0
    plan["components"][2]["margins"] = [0, 0, 0, 0]
    slot = prepare(plan, manifest)["nodes"][0]["widgets"][0]
    assert slot["alignFlags"] == 4
    assert slot["margins"] == [0, -6, 0, 0]
    assert "_alignFlags" in slot["normalizedPlanMismatch"]
    assert "_bottom" in slot["normalizedPlanMismatch"]
    assert slot["status"] == "native_constraint_supported"


def test_unknown_source_layout_field_is_retained_and_never_claimed_complete():
    plan, manifest = _plan_and_manifest()
    manifest["assets"][0]["document"]["instances"][0]["_components"][0]["_N$vendorMode"] = 7
    slot = prepare(plan, manifest)["nodes"][0]["layouts"][0]
    assert slot["status"] == "partial"
    assert slot["unknownSourceFields"] == ["_N$vendorMode"]
    assert slot["sourceSerializedFields"]["_N$vendorMode"] == 7


def test_layout_probe_applies_container_resize_and_handles_negative_scale_factor():
    slot = {"layoutType": 1, "resize": 1, "padding": [-2, 0, 3, 0], "spacingXY": [4, 0],
            "affectedByScale": True, "horizontalDirection": 0}
    children = [
        {"active": True, "size": [10, 8], "scale": [-2, 1], "anchor": [0.5, 0.5], "position": [0, 0]},
        {"active": True, "size": [5, 9], "scale": [1, 1], "anchor": [0.5, 0.5], "position": [0, 0]},
    ]
    result = simulate_layout(slot, [100, 40], [0.5, 0.5], children)
    assert result["ownerSize"] == [30, 40]  # -2 + (10*2) + (5) + 4 + 3
    assert result["children"][0]["position"][0] == pytest.approx(-3)


def test_widget_probe_keeps_negative_margin_and_flips_negative_scale_anchor():
    widget = {"alignFlags": 4, "margins": [0, -6, 0, 0], "absolute": [True] * 4,
              "center": [0, 0], "centerAbsolute": [True, True]}
    node = {"size": [20, 25], "position": [0, 0], "scale": [1, -1], "anchor": [0.5, 0.25]}
    target = {"size": [100, 80], "anchor": [0.5, 0.5], "explicit": False}
    result = simulate_widget_alignment(widget, node, target)
    assert result["position"][1] == pytest.approx(-27.25)
    assert result["size"] == [20, 25]


def test_strict_readback_rejects_missing_or_changed_native_slot_and_pose():
    plan, manifest = _plan_and_manifest()
    expected = prepare(plan, manifest)
    node = expected["nodes"][0]
    actual = [{"sourceNodeId": node["sourceNodeId"], "layouts": [], "widgets": []}]
    result = verify_readback(expected, actual)
    assert result["status"] == "mismatch"
    assert any("count_mismatch" in code for code in result["errors"])
    result = verify_readback(expected, [], {"rows": [{"sourceId": "n", "position": [1, 2], "size": [3, 4]}], "actual": []})
    assert result["runtimeInitializationSeparatelyVerified"] is False


def test_unity_null_array_and_parent_target_encodings_keep_source_presence_distinct():
    plan, manifest = _plan_and_manifest()
    expected = prepare(plan, manifest)
    actual = copy.deepcopy(expected["nodes"])
    for slot in actual[0]["layouts"] + actual[0]["widgets"]:
        slot["nativeComponentPresent"] = True
        slot["savedReferenceVerified"] = True
    for slot in actual[0]["layouts"]:
        slot["fieldValues"]["sourceLayoutCacheSize"] = []
    actual[0]["widgets"][0]["fieldValues"]["targetSourceNodeId"] = ""
    assert verify_readback(expected, actual)["status"] == "verified_static_layout_fields"

    actual[0]["widgets"][0]["fieldValues"]["targetUsesParentWhenNull"] = False
    assert verify_readback(expected, actual)["status"] == "mismatch"


def test_subset_scope_is_exact_for_individual_source_prefab_readback():
    plan, manifest = _plan_and_manifest()
    expected = prepare(plan, manifest)
    scoped = subset_for_nodes(expected, [f"{ASSET}#0"])
    assert len(scoped["nodes"]) == 1
    with pytest.raises(LayoutCompletionError, match="STATIC_LAYOUT_NODE_SCOPE_UNKNOWN"):
        subset_for_nodes(expected, ["not-in-contract"])


def test_probe_oracle_uses_disposable_input_geometry_and_returns_separate_after_pose():
    owner = "layout-owner"
    child_a, child_b = "child-a", "child-b"
    contract = {"evidenceSources": {"layout": "pinned-source"}, "nodes": [{
        "sourceNodeId": owner, "layouts": [{"componentOrder": 0, "sourceEnabled": True, "layoutType": 1,
            "resize": 1, "padding": [0, 0, 0, 0], "spacingXY": [5, 0], "affectedByScale": False}], "widgets": []
    }]}
    geometry = {
        "nodeOrder": [owner, child_a, child_b],
        owner: {"position": [0, 0, 0], "size": [100, 50], "scale": [1, 1], "anchor": [0.5, 0.5], "children": [child_a, child_b]},
        child_a: {"position": [90, 0, 0], "size": [10, 10], "scale": [1, 1], "anchor": [0.5, 0.5]},
        child_b: {"position": [90, 0, 0], "size": [20, 10], "scale": [1, 1], "anchor": [0.5, 0.5]},
    }
    before = copy.deepcopy(geometry)
    oracle = probe_expected(contract, geometry)
    assert geometry == before
    assert oracle["initialPoseUsedAsConstraintProof"] is False
    assert oracle["rows"][0]["size"] == [35, 50]
    assert oracle["rows"][1]["position"] == pytest.approx([-7.5, 0, 0])


def test_native_probe_verifier_requires_size_delta_and_formula_matched_after_geometry():
    plan, manifest = _plan_and_manifest()
    contract = prepare(plan, manifest)
    owner = f"{ASSET}#0"
    parent = "source:parent"
    child = "source:child"
    geometry = {
        "nodeOrder": [parent, owner, child],
        parent: {"sourceNodeId": parent, "parentSourceNodeId": None, "children": [owner], "active": True,
                 "position": [0,0,0], "size": [100,80], "scale": [1,1,1], "anchor": [.5,.5]},
        owner: {"sourceNodeId": owner, "parentSourceNodeId": parent, "children": [child], "active": True,
                "position": [0,0,0], "size": [20,25], "scale": [1,-1,1], "anchor": [.5,.25]},
        child: {"sourceNodeId": child, "parentSourceNodeId": owner, "children": [], "active": True,
                "position": [10,10,0], "size": [8,6], "scale": [1,1,1], "anchor": [.5,.5]},
    }
    before = copy.deepcopy(geometry)
    input_geometry = copy.deepcopy(geometry)
    input_geometry[owner]["size"] = [37,36]
    oracle = probe_expected(contract, input_geometry)
    after_by_id = {row["sourceId"]: row for row in oracle["rows"]}
    probe_rows = []
    for source_id in geometry["nodeOrder"]:
        before_geo = geometry[source_id]
        input_geo = input_geometry[source_id]
        after_geo = dict(before_geo, **after_by_id[source_id])
        probe_rows.append({"sourceNodeId": source_id, "before": {
            "sourceNodeId": source_id, "parentSourceNodeId": before_geo["parentSourceNodeId"],
            "childrenSourceNodeIds": before_geo["children"], "position": before_geo["position"], "size": before_geo["size"],
            "scale": before_geo["scale"], "anchor": before_geo["anchor"], "activeSelf": True, "activeInHierarchy": True},
            "input": {"sourceNodeId": source_id, "parentSourceNodeId": input_geo["parentSourceNodeId"],
            "childrenSourceNodeIds": input_geo["children"], "position": input_geo["position"], "size": input_geo["size"],
            "scale": input_geo["scale"], "anchor": input_geo["anchor"], "activeSelf": True, "activeInHierarchy": True},
            "after": {"sourceNodeId": source_id, "parentSourceNodeId": after_geo["parentSourceNodeId"],
            "childrenSourceNodeIds": after_geo["children"], "position": after_geo["position"], "size": after_geo["size"],
            "scale": after_geo["scale"], "anchor": after_geo["anchor"], "activeSelf": True, "activeInHierarchy": True}})
    probe = {"status": "probe_captured", "disposableCloneRequired": True, "persistentPrefabMutated": False,
             "baselineInitialized": True, "baselineIsConstraintProof": False,
             "appliedSourceComponentIds": sorted(slot["sourceComponentId"] for slot in contract["nodes"][0]["layouts"]+contract["nodes"][0]["widgets"] if slot["sourceEnabled"]),
             "layoutParticipation": [{"sourceComponentId":slot["sourceComponentId"],"ownerSourceNodeId":owner,
                 "layoutType":slot["layoutType"],"algorithmInvoked":True,"effectiveChildSourceNodeIds":[child]}
                 for slot in contract["nodes"][0]["layouts"] if slot["sourceEnabled"]],
             "nodes": probe_rows}
    assert geometry == before
    result = verify_native_probe(contract, probe)
    assert result["status"] == "verified_native_layout_constraints"
    probe_rows[1]["after"]["position"][0] += 1
    result = verify_native_probe(contract, probe)
    assert result["status"] == "mismatch"
    assert any("differs_from_source_formula" in error for error in result["errors"])
    probe_rows[1]["after"]["position"][0] -= 1
    probe_rows[1]["input"]["activeInHierarchy"] = False
    probe_rows[2]["input"]["activeInHierarchy"] = False
    probe["layoutParticipation"][0]["effectiveChildSourceNodeIds"] = []
    result = verify_native_probe(contract, probe)
    assert result["status"] == "mismatch"
    assert any("layout_has_no_active_source_children" in error for error in result["errors"])
    assert any("owner_not_active_in_hierarchy" in error for error in result["errors"])


def test_widget_probe_oracle_converts_explicit_ancestor_through_negative_scaled_parent():
    target, middle, owner = "root", "middle", "widget-owner"
    contract = {"nodes": [{"sourceNodeId": owner, "layouts": [], "widgets": [{
        "sourceComponentId": "widget:explicit", "componentOrder": 0, "sourceEnabled": True,
        "targetSourceNodeId": target, "alignFlags": 4, "margins": [0,-6,0,0], "absolute": [True]*4,
        "center": [0,0], "centerAbsolute": [True,True],
    }]}]}
    geometry = {"nodeOrder": [target,middle,owner],
        target: {"sourceNodeId": target,"parentSourceNodeId": None,"children":[middle],"position":[0,0,0],"size":[100,80],"scale":[1,1,1],"anchor":[.5,.5],"active":True},
        middle: {"sourceNodeId": middle,"parentSourceNodeId":target,"children":[owner],"position":[10,5,0],"size":[50,40],"scale":[2,-1,1],"anchor":[.5,.5],"active":True},
        owner: {"sourceNodeId":owner,"parentSourceNodeId":middle,"children":[],"position":[0,0,0],"size":[20,25],"scale":[1,-1,1],"anchor":[.5,.25],"active":True},
    }
    oracle=probe_expected(contract,geometry)
    assert oracle["rows"][2]["position"][1] == pytest.approx(69.75)


def test_null_widget_target_persists_as_null_reference_with_parent_fallback_policy():
    plan, manifest = _plan_and_manifest()
    slot = prepare(plan, manifest)["nodes"][0]["widgets"][0]
    assert slot["targetSourceNodeId"] is None
    assert slot["targetUsesParentWhenNull"] is True
    assert slot["fieldValues"]["targetSourceNodeId"] is None


def test_unsupported_grid_is_not_claimed_as_native_constraint():
    slot = {"layoutType": 3, "resize": 0, "padding": [0, 0, 0, 0], "spacingXY": [0, 0]}
    with pytest.raises(LayoutCompletionError, match="LAYOUT_ALGORITHM_UNSUPPORTED"):
        simulate_layout(slot, [100, 100], [0.5, 0.5], [])
