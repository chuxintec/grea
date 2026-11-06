import copy
import hashlib

import pytest

import monkey.unity_prefab_graph as prefab_graph
from monkey.unity_prefab_graph import CONTRACT, GraphInputError, build


def sha(char):
    return hashlib.sha256(char.encode()).hexdigest()


def ptr(file_id, path_id):
    return {"$type": "UnityPPtr", "fileId": str(file_id), "pathId": str(path_id)}


def make_doc(container_name, file_name, file_hash, objects, externals=()):
    rows = []
    for row in objects:
        row = copy.deepcopy(row)
        refs = []
        def walk(value, location="$", path=()):
            if isinstance(value, dict):
                if value.get("$type") == "UnityPPtr":
                    refs.append({"location": location, "fileId": value["fileId"], "pathId": value["pathId"]})
                else:
                    for key, child in value.items():
                        walk(child, f"{location}/{key}", path + (key,))
            elif isinstance(value, list):
                for i, child in enumerate(value):
                    walk(child, f"{location}/{i}", path + (i,))
        if row.get("status") == "parsed":
            walk(row.get("data", {}))
        row["references"] = refs
        rows.append(row)
    return {
        "sourceFamily": "unity", "files": [{"id": "0", "name": file_name,
            "serializedFileSha256": file_hash, "unityVersion": "2021.3.30f1",
            "externals": list(externals)}], "objects": rows,
        "embeddedSchemas": {}, "borrowedSchemas": {},
    }


def obj(path_id, typ, data, status="parsed", **extra):
    return {"file": "0", "pathId": str(path_id), "classId": 1, "type": typ,
            "rawSha256": sha(f"{typ}:{path_id}"), "status": status, "data": data, **extra}


def sample_inputs():
    root = "100"
    child = "101"
    rt = "200"
    ct = "201"
    mb = "300"
    script = "301"
    external_sha = sha("container-external")
    primary_sha = sha("container-primary")
    primary = make_doc("primary", "CAB-ROOT", sha("serialized-root"), [
        obj(root, "GameObject", {"m_Name": "Root", "m_IsActive": True, "m_Layer": 5,
            "m_Tag": 0, "m_Component": [{"component": ptr(0, rt)}]}),
        obj(child, "GameObject", {"m_Name": "Child", "m_IsActive": False, "m_Layer": 8,
            "m_Tag": 0, "m_Component": [{"component": ptr(0, ct)}, {"component": ptr(0, mb)}]}),
        obj(rt, "RectTransform", {"m_GameObject": ptr(0, root), "m_Father": ptr(0, 0),
            "m_Children": [ptr(0, ct)], "m_LocalPosition": {"x": 0, "y": 0, "z": 0},
            "m_LocalScale": {"x": 1, "y": 1, "z": 1}, "m_AnchorMin": {"x": 0, "y": 0},
            "m_AnchorMax": {"x": 1, "y": 1}, "m_AnchoredPosition": {"x": 4, "y": 6},
            "m_SizeDelta": {"x": 20, "y": 30}, "m_Pivot": {"x": .5, "y": .5},
            "m_LocalRotation": {"x": 0, "y": 0, "z": 0, "w": 1}}),
        obj(ct, "Transform", {"m_GameObject": ptr(0, child), "m_Father": ptr(0, rt),
            "m_Children": [], "m_LocalPosition": {"x": 1, "y": 2, "z": 3},
            "m_LocalScale": {"x": 1, "y": 1, "z": 1}, "m_LocalRotation": {"x": 0, "y": 0, "z": 0, "w": 1}}),
        obj(mb, "MonoBehaviour", {"m_GameObject": ptr(0, child), "m_Script": ptr(0, script),
            "customValue": {"nested": [1, "preserve", {"flag": True}]}, "asset": ptr(1, 900),
            "optional": ptr(0, 0)}, embeddedSchemaId="schema-1", typeTreeSource="embedded"),
        obj(script, "MonoScript", {"m_AssemblyName": "Game.dll", "m_Namespace": "Demo", "m_ClassName": "Widget"}),
    ], [{"fileId": "1", "path": "archive:/CAB-ART/CAB-ART", "guid": "0" * 32}])
    external = make_doc("external", "CAB-ART", sha("serialized-art"), [
        obj(900, "Texture2D", {"m_Name": "icon", "m_Width": 16, "m_Height": 16}),
    ])
    return [{"sourceSha256": primary_sha, "document": primary},
            {"sourceSha256": external_sha, "document": external}], primary_sha


def test_builds_hierarchy_component_order_custom_fields_and_exact_external_link():
    inputs, source = sample_inputs()
    result = build(inputs, [{"sourceSha256": source, "file": "0", "pathId": "100"}])
    assert result["contract"] == CONTRACT
    assert result["execution"] == {"sourceCode": "not_run", "nativeEditor": "not_run", "runtime": "not_run"}
    assert len(result["reachableObjects"]) == 7
    root = next(row for row in result["gameObjects"] if row["name"] == "Root")
    child = next(row for row in result["gameObjects"] if row["name"] == "Child")
    assert root["active"] is True and root["layer"] == 5
    assert root["childSourceObjectIds"] == [child["sourceObjectId"]]
    assert [row["type"] for row in child["orderedComponents"]] == ["Transform", "MonoBehaviour"]
    assert root["transformType"] == "RectTransform"
    assert root["transformData"]["m_AnchoredPosition"] == {"x": 4, "y": 6}
    component = next(row for row in result["reachableObjects"] if row["type"] == "MonoBehaviour")
    assert component["data"]["customValue"]["nested"][1] == "preserve"
    assert component["monoScriptIdentity"]
    script = next(row for row in result["reachableObjects"] if row["type"] == "MonoScript")
    assert script["monoScript"] == {"m_AssemblyName": "Game.dll", "m_Namespace": "Demo", "m_ClassName": "Widget"}
    assert any(edge["status"] == "resolved" and edge["pathId"] == "900" for edge in result["referenceEdges"])
    assert any(edge["status"] == "null" and edge["pathId"] == "0" for edge in result["referenceEdges"])


def test_missing_external_reference_is_a_gap_with_pointer_evidence():
    inputs, source = sample_inputs()
    inputs = inputs[:1]
    result = build(inputs, [{"sourceSha256": source, "file": "0", "pathId": "100"}])
    edge = next(e for e in result["referenceEdges"] if e["pathId"] == "900")
    assert edge["status"] == "unresolved"
    gap = next(g for g in result["gaps"] if g["kind"] == "reference-unresolved" and g["pointer"]["pathId"] == "900")
    assert gap["pointer"] == {"fileId": "1", "pathId": "900"}


def test_same_serialized_name_with_different_bytes_is_rejected():
    inputs, _ = sample_inputs()
    duplicate = copy.deepcopy(inputs[1]["document"])
    duplicate["files"][0]["name"] = "CAB-ROOT"
    inputs.append({"sourceSha256": sha("duplicate-container"), "document": duplicate})
    with pytest.raises(GraphInputError, match="different bytes"):
        build(inputs, [{"sourceSha256": inputs[0]["sourceSha256"], "file": "0", "pathId": "100"}])


def test_cycle_and_inconsistent_parent_child_are_explicit():
    source = sha("cycle-container")
    doc = make_doc("cycle", "CAB-CYCLE", sha("cycle-file"), [
        obj(1, "GameObject", {"m_Name": "A", "m_IsActive": True, "m_Layer": 0, "m_Tag": 0,
            "m_Component": [{"component": ptr(0, 11)}]}),
        obj(2, "GameObject", {"m_Name": "B", "m_IsActive": True, "m_Layer": 0, "m_Tag": 0,
            "m_Component": [{"component": ptr(0, 12)}]}),
        obj(11, "Transform", {"m_GameObject": ptr(0, 1), "m_Father": ptr(0, 12), "m_Children": [ptr(0, 12)]}),
        obj(12, "Transform", {"m_GameObject": ptr(0, 2), "m_Father": ptr(0, 11), "m_Children": [ptr(0, 11)]}),
    ])
    result = build([{"sourceSha256": source, "document": doc}], [{"sourceSha256": source, "file": "0", "pathId": "1"}])
    kinds = {gap["kind"] for gap in result["gaps"]}
    assert "hierarchy-cycle" in kinds


def test_unparsed_reachable_object_marks_reference_closure_incomplete():
    source = sha("partial-container")
    doc = make_doc("partial", "CAB-PARTIAL", sha("partial-file"), [
        obj(1, "GameObject", {"m_Name": "Root", "m_IsActive": True, "m_Layer": 0, "m_Tag": 0,
            "m_Component": [{"component": ptr(0, 2)}]}),
        obj(2, "Transform", {}, status="unparsed", references=[]),
    ])
    result = build([{"sourceSha256": source, "document": doc}], [{"sourceSha256": source, "file": "0", "pathId": "1"}])
    assert any(g["kind"] == "reference-closure-incomplete" for g in result["gaps"])


def test_document_source_hash_must_match_input_identity():
    inputs, source = sample_inputs()
    inputs[0]["document"]["source"] = {"sha256": sha("another-source")}
    with pytest.raises(GraphInputError, match="source.sha256 differs"):
        build(inputs, [{"sourceSha256": source, "file": "0", "pathId": "100"}])


def test_builtin_external_is_unverified_engine_identity_not_missing_source_bundle():
    inputs, source = sample_inputs()
    primary = inputs[0]["document"]
    primary["files"][0]["externals"][0]["path"] = "archive:/unity default resources"
    mb = next(o for o in primary["objects"] if o["type"] == "MonoBehaviour")
    mb["data"]["asset"] = ptr(1, 10101)
    mb["references"] = [r for r in mb["references"] if r["location"] != "$/asset"]
    mb["references"].append({"location": "$/asset", "fileId": "1", "pathId": "10101"})
    result = build(inputs[:1], [{"sourceSha256": source, "file": "0", "pathId": "100"}])
    edge = next(e for e in result["referenceEdges"] if e["pathId"] == "10101")
    assert edge["status"] == "engine-provided-unverified"
    assert edge["targetSourceObjectId"] is None
    assert edge["externalIdentity"]["category"] == "unity-default-resources"
    assert edge["externalIdentity"]["fileId"] == "1"
    assert edge["externalIdentity"]["path"] == "archive:/unity default resources"
    assert any(g["kind"] == "engine-reference-unverified" and g["pointer"]["pathId"] == "10101"
               for g in result["gaps"])
    assert not any(g["kind"] == "reference-unresolved" and g["pointer"]["pathId"] == "10101"
                   for g in result["gaps"])


def test_duplicate_serialized_file_with_different_schema_evidence_fails():
    inputs, _ = sample_inputs()
    primary = inputs[0]
    clone = copy.deepcopy(primary)
    clone["sourceSha256"] = sha("schema-different-container")
    clone["document"]["files"][0]["name"] = "CAB-ROOT"
    clone["document"]["files"][0]["serializedFileSha256"] = primary["document"]["files"][0]["serializedFileSha256"]
    clone["document"]["embeddedSchemas"] = {"schema-1": {"fields": ["changed"]}}
    primary["document"]["embeddedSchemas"] = {"schema-1": {"fields": ["original"]}}
    inputs.append(clone)
    with pytest.raises(GraphInputError, match="different object identities/data"):
        build(inputs, [{"sourceSha256": primary["sourceSha256"], "file": "0", "pathId": "100"}])


def test_typed_value_depth_budget_is_enforced_iteratively(monkeypatch):
    source = sha("deep-values")
    doc = make_doc("deep", "CAB-DEEP", sha("deep-file"), [
        obj(1, "GameObject", {"m_Name": "Root", "m_IsActive": True, "m_Layer": 0, "m_Tag": 0,
            "m_Component": [{"component": ptr(0, 2)}], "custom": {"a": {"b": {"c": 1}}}}),
        obj(2, "Transform", {"m_GameObject": ptr(0, 1), "m_Father": ptr(0, 0), "m_Children": []}),
    ])
    monkeypatch.setattr(prefab_graph, "MAX_TYPED_VALUE_DEPTH", 3)
    with pytest.raises(GraphInputError, match="depth budget exceeded"):
        build([{"sourceSha256": source, "document": doc}], [{"sourceSha256": source, "file": "0", "pathId": "1"}])


def test_typed_value_node_budget_is_enforced(monkeypatch):
    source = sha("many-values")
    doc = make_doc("many", "CAB-MANY", sha("many-file"), [
        obj(1, "GameObject", {"m_Name": "Root", "m_IsActive": True, "m_Layer": 0, "m_Tag": 0,
            "m_Component": [{"component": ptr(0, 2)}]}),
        obj(2, "Transform", {"m_GameObject": ptr(0, 1), "m_Father": ptr(0, 0), "m_Children": []}),
    ])
    monkeypatch.setattr(prefab_graph, "MAX_TYPED_VALUE_NODES", 5)
    with pytest.raises(GraphInputError, match="node budget exceeded"):
        build([{"sourceSha256": source, "document": doc}], [{"sourceSha256": source, "file": "0", "pathId": "1"}])


def test_unreferenced_library_values_do_not_consume_selected_graph_budget(monkeypatch):
    source = sha("selected-root-library")
    doc = make_doc("selected", "CAB-SELECTED", sha("selected-file"), [
        obj(1, "GameObject", {"m_Name": "Root", "m_IsActive": True, "m_Layer": 0, "m_Tag": 0,
            "m_Component": [{"component": ptr(0, 2)}]}),
        obj(2, "Transform", {"m_GameObject": ptr(0, 1), "m_Father": ptr(0, 0), "m_Children": []}),
        obj(3, "Shader", {"unused": list(range(1000))}),
    ])
    monkeypatch.setattr(prefab_graph, "MAX_TYPED_VALUE_NODES", 200)
    result = build([{"sourceSha256": source, "document": doc}], [{"sourceSha256": source, "file": "0", "pathId": "1"}])
    assert len(result['reachableObjects']) == 2
    assert result['budgetUsage']['typedValueNodes'] < 200
