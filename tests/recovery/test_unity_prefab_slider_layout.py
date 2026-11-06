import hashlib
import json
from pathlib import Path

import pytest

from grea.recovery.io import encoded
from grea.recovery.unity_prefab_slider_layout import SliderLayoutError, planned_slider_overrides


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return sha(raw)


SLIDER_CS = '''namespace UnityEngine.UI {
public class Slider : Selectable {
 public enum Direction { LeftToRight, RightToLeft, BottomToTop, TopToBottom }
 public float normalizedValue { get { if (Mathf.Approximately(minValue, maxValue)) return 0; return Mathf.InverseLerp(minValue, maxValue, value); } }
 [Space]
 protected override void OnEnable() { UpdateCachedReferences(); Set(m_Value, false); UpdateVisuals(); }
 Axis axis { get { return (m_Direction == Direction.LeftToRight || m_Direction == Direction.RightToLeft) ? Axis.Horizontal : Axis.Vertical; } }
 bool reverseValue { get { return m_Direction == Direction.RightToLeft || m_Direction == Direction.TopToBottom; } }
 private void UpdateVisuals() {
   if (m_FillContainerRect != null) {
     m_Tracker.Add(this, m_FillRect, DrivenTransformProperties.Anchors);
     Vector2 anchorMin = Vector2.zero;
     Vector2 anchorMax = Vector2.one;
     if (m_FillImage != null && m_FillImage.type == Image.Type.Filled) { m_FillImage.fillAmount = normalizedValue; }
     else { if (reverseValue) anchorMin[(int)axis] = 1 - normalizedValue; else anchorMax[(int)axis] = normalizedValue; }
     m_FillRect.anchorMin = anchorMin;
     m_FillRect.anchorMax = anchorMax;
   }
 }
}
}'''
IMAGE_CS = '''namespace UnityEngine.UI {
public class Image : MaskableGraphic {
 public enum Type { Simple, Sliced, Tiled, Filled }
}
}'''
SOURCE_IMAGE_CARRIER = '''namespace DodGame {
public class DodImage : UnityEngine.UI.Image { }
}'''
OUTLINE_CS = '''namespace UnityEngine.UI {
public class Outline : Shadow { }
}'''
SHADOW_CS = '''namespace UnityEngine.UI {
public class Shadow : BaseMeshEffect { }
}'''
BASE_MESH_EFFECT_CS = '''namespace UnityEngine.UI {
public abstract class BaseMeshEffect : UnityEngine.EventSystems.UIBehaviour { }
}'''
UI_BEHAVIOUR_CS = '''namespace UnityEngine.EventSystems {
public abstract class UIBehaviour : UnityEngine.MonoBehaviour { }
}'''


def binding_fixture(tmp_path):
    root = tmp_path / "ugui"
    slider_rel = "Runtime/UGUI/UI/Core/Slider.cs"
    image_rel = "Runtime/UGUI/UI/Core/Image.cs"
    slider_raw, image_raw = SLIDER_CS.encode(), IMAGE_CS.encode()
    write(root / "package.json", json.dumps({"name": "com.unity.ugui", "version": "2.6.0"}).encode())
    write(root / "Runtime/UGUI/UnityEngine.UI.asmdef", json.dumps({"name": "UnityEngine.UI"}).encode())
    write(root / slider_rel, slider_raw)
    slider_guid = "1" * 32
    slider_meta = f"fileFormatVersion: 2\nguid: {slider_guid}\n".encode()
    slider_meta_sha = write(root / (slider_rel + ".meta"), slider_meta)
    write(root / image_rel, image_raw)
    image_guid = "2" * 32
    image_meta = f"fileFormatVersion: 2\nguid: {image_guid}\n".encode()
    write(root / (image_rel + ".meta"), image_meta)
    rows = []
    for class_name, source_id, code, path, guid in [
        ("Outline", "script-outline", OUTLINE_CS, "Runtime/UGUI/UI/Core/VertexModifiers/Outline.cs", "4" * 32),
        ("Shadow", "script-shadow", SHADOW_CS, "Runtime/UGUI/UI/Core/VertexModifiers/Shadow.cs", "5" * 32),
    ]:
        raw = code.encode()
        write(root / path, raw)
        meta_raw = f"fileFormatVersion: 2\nguid: {guid}\n".encode()
        meta_sha = write(root / (path + ".meta"), meta_raw)
        rows.append({
            "identity": {"assembly": "UnityEngine.UI.dll", "namespace": "UnityEngine.UI", "class": class_name},
            "status": "planned_sdk_binding", "sourceObjectIds": [source_id],
            "sourceTuple": {"guid": "6" * 32, "fileID": 11500000, "type": 3},
            "targetSource": {"path": path, "guid": guid, "assemblyDefinition": "Runtime/UGUI/UnityEngine.UI.asmdef",
                "assemblyDefinitionName": "UnityEngine.UI", "sourceSha256": sha(raw), "metaSha256": meta_sha},
            "expectedTuple": {"guid": guid, "fileID": 11500000, "type": 3},
            "verification": "expected tuple only; native AssetDatabase GUID/GetClass not run",
        })
    write(root / "Runtime/UGUI/UI/Core/VertexModifiers/BaseMeshEffect.cs", BASE_MESH_EFFECT_CS.encode())
    write(root / "Runtime/UGUI/EventSystem/UIBehaviour.cs", UI_BEHAVIOUR_CS.encode())
    script_id = "script-slider"
    binding_plan = {
        "sdkRoot": str(root),
        "bindings": [{
            "identity": {"assembly": "UnityEngine.UI.dll", "namespace": "UnityEngine.UI", "class": "Slider"},
            "status": "planned_sdk_binding",
            "sourceObjectIds": [script_id],
            "sourceTuple": {"guid": "3" * 32, "fileID": 11500000, "type": 3},
            "targetSource": {"path": slider_rel, "guid": slider_guid, "assemblyDefinition": "Runtime/UGUI/UnityEngine.UI.asmdef",
                "assemblyDefinitionName": "UnityEngine.UI", "sourceSha256": sha(slider_raw), "metaSha256": slider_meta_sha},
            "expectedTuple": {"guid": slider_guid, "fileID": 11500000, "type": 3},
            "verification": "expected tuple only; native AssetDatabase GUID/GetClass not run",
        }, *rows],
    }
    return root, binding_plan, script_id


def graph_fixture(tmp_path, *, image_type=0, direction=0, value=0.75, minimum=0.0, maximum=1.0,
                  whole=0, enabled=1, active=True, handle=None, second_driver=False,
                  with_outline=False, with_image=True, second_image=False,
                  fill_active=True, image_enabled=1):
    sdk_root, binding_plan, slider_script_id = binding_fixture(tmp_path)
    candidate = tmp_path / "candidate"
    carrier_path = "Assets/Scripts/DodImage.cs"
    carrier_raw = SOURCE_IMAGE_CARRIER.encode()
    carrier_sha = write(candidate / carrier_path, carrier_raw)
    candidate_manifest = {"files": [{"path": carrier_path, "sha256": carrier_sha, "bytes": len(carrier_raw)}]}
    source_hash = "a" * 64
    serialized = "CAB-neutral"
    serialized_hash = "b" * 64

    def identity(path_id):
        return dict(containerSha256=source_hash, serializedFile=serialized, serializedFileSha256=serialized_hash, pathId=str(path_id))

    def ptr(path_id):
        return {"$type": "UnityPPtr", "fileId": "0", "pathId": str(path_id)}

    script = dict(sourceObjectId=slider_script_id, type="MonoScript", identity=identity(20), data={
        "m_AssemblyName": "UnityEngine.UI.dll", "m_Namespace": "UnityEngine.UI", "m_ClassName": "Slider", "m_Name": "Slider"})
    dod_script_id = "script-dodimage"
    dod_script = dict(sourceObjectId=dod_script_id, type="MonoScript", identity=identity(21), data={
        "m_AssemblyName": "GameBase.dll", "m_Namespace": "DodGame", "m_ClassName": "DodImage", "m_Name": "DodImage"})
    outline_script = dict(sourceObjectId="script-outline", type="MonoScript", identity=identity(22), data={
        "m_AssemblyName": "UnityEngine.UI.dll", "m_Namespace": "UnityEngine.UI", "m_ClassName": "Outline", "m_Name": "Outline"})
    shadow_script = dict(sourceObjectId="script-shadow", type="MonoScript", identity=identity(23), data={
        "m_AssemblyName": "UnityEngine.UI.dll", "m_Namespace": "UnityEngine.UI", "m_ClassName": "Shadow", "m_Name": "Shadow"})
    slider_id = "slider-instance"
    second_id = "slider-instance-2"
    slider = dict(sourceObjectId=slider_id, type="MonoBehaviour", rawSha256="c" * 64, identity=identity(30), data={
        "m_Script": ptr(20), "m_GameObject": ptr(10), "m_FillRect": ptr(40),
        "m_HandleRect": ptr(0) if handle is None else ptr(handle), "m_Value": value, "m_MinValue": minimum,
        "m_MaxValue": maximum, "m_Direction": direction, "m_WholeNumbers": whole,
        "m_Enabled": enabled, "m_Interactable": 0})
    slider_rows = [slider]
    if second_driver:
        duplicate = dict(slider, sourceObjectId=second_id, identity=identity(31), rawSha256="d" * 64)
        slider_rows.append(duplicate)
    rect_fill = dict(sourceObjectId="fill-rect", type="RectTransform", identity=identity(40), data={
        "m_GameObject": ptr(11), "m_Father": ptr(41), "m_AnchorMin": dict(x=0.0, y=0.0),
        "m_AnchorMax": dict(x=0.0, y=0.0), "m_Children": []})
    rect_parent = dict(sourceObjectId="fill-container-rect", type="RectTransform", identity=identity(41), data={
        "m_GameObject": ptr(12), "m_Father": ptr(0), "m_Children": [ptr(40)]})
    fill_image_id = "fill-image"
    fill_image = dict(sourceObjectId=fill_image_id, type="MonoBehaviour", rawSha256="e" * 64, identity=identity(42), data={
        "m_Script": ptr(21), "m_GameObject": ptr(11), "m_Enabled": image_enabled, "m_Type": image_type, "m_FillAmount": 1.0})
    fill_components = [dict(sourceObjectId=fill_image_id, component=42)] if with_image else []
    extra_objects = []
    if second_image:
        extra_objects.append(dict(sourceObjectId="fill-image-second", type="MonoBehaviour", rawSha256="1" * 64, identity=identity(44), data={
            "m_Script": ptr(21), "m_GameObject": ptr(11), "m_Enabled": 1, "m_Type": image_type, "m_FillAmount": 1.0}))
        fill_components.append(dict(sourceObjectId="fill-image-second", component=44))
    if with_outline:
        extra_objects.append(dict(sourceObjectId="fill-outline", type="MonoBehaviour", rawSha256="2" * 64, identity=identity(45), data={
            "m_Script": ptr(22), "m_GameObject": ptr(11), "m_Enabled": 1}))
        fill_components.append(dict(sourceObjectId="fill-outline", component=45))
    go_objects = [dict(sourceObjectId="slider-go", type="GameObject", identity=identity(10), data={"m_IsActive": active, "m_Component": [{"component": ptr(30)}]}),
        dict(sourceObjectId="fill-go", type="GameObject", identity=identity(11), data={"m_IsActive": fill_active,
            "m_Component": [{"component": ptr(40)}, {"component": ptr(43)}, *[{"component": ptr(c["component"])} for c in fill_components]]}),
        dict(sourceObjectId="container-go", type="GameObject", identity=identity(12), data={"m_IsActive": True,
            "m_Component": [{"component": ptr(41)}]})]
    canvas = dict(sourceObjectId="fill-canvas", type="CanvasRenderer", identity=identity(43), data={"m_GameObject": ptr(11)})
    objects = [script, dod_script, outline_script, shadow_script, *go_objects, *slider_rows, rect_fill, rect_parent,
               *([fill_image] if with_image else []), canvas, *extra_objects]
    game_objects = [
        dict(sourceObjectId="slider-go", name="SliderRoot", active=active, parentSourceObjectId=None),
        dict(sourceObjectId="fill-go", name="Fill", active=fill_active, parentSourceObjectId="slider-go"),
        dict(sourceObjectId="container-go", name="FillArea", active=True, parentSourceObjectId="slider-go"),
    ]
    edges = [dict(sourceObjectId=slider_id, location="$/m_FillRect", status="resolved", targetSourceObjectId="fill-rect"),
        dict(sourceObjectId="fill-rect", location="$/m_Father", status="resolved", targetSourceObjectId="fill-container-rect"),
        dict(sourceObjectId="slider-go", location="$/m_Component/0/component", status="resolved", targetSourceObjectId=slider_id),
        dict(sourceObjectId="fill-go", location="$/m_Component/0/component", status="resolved", targetSourceObjectId="fill-rect"),
        dict(sourceObjectId="container-go", location="$/m_Component/0/component", status="resolved", targetSourceObjectId="fill-container-rect")]
    edges.append(dict(sourceObjectId="fill-go", location="$/m_Component/1/component", status="resolved", targetSourceObjectId="fill-canvas"))
    for index, row in enumerate(fill_components, 2):
        edges.append(dict(sourceObjectId="fill-go", location=f"$/m_Component/{index}/component", status="resolved", targetSourceObjectId=row["sourceObjectId"]))
    graph = dict(contract="monkey-unity-prefab-source-graph/1", sourceUnityVersions=["2021.3.30f1"],
                 reachableObjects=objects, referenceEdges=edges, gameObjects=game_objects)
    return graph, binding_plan, dict(root=sdk_root, candidate=candidate, manifest=candidate_manifest,
                                     pins={dod_script_id: {"path": carrier_path, "sha256": carrier_sha}})


def plan(fx, **kwargs):
    graph, bindings, evidence = fx
    return planned_slider_overrides(graph, sdk_bindings=bindings, sdk_root=evidence["root"],
        source_candidate_root=evidence["candidate"], source_candidate_manifest=evidence["manifest"],
        source_class_pins=evidence["pins"], **kwargs)


def test_simple_fill_derives_exact_anchor_fields_and_preserves_source_values(tmp_path):
    result = plan(graph_fixture(tmp_path))
    row = result["sliders"][0]
    assert row["status"] == "active_enabled_driver"
    assert row["normalizedValue"] == 0.75
    by_path = {r["path"]: r for r in row["overrides"]}
    assert by_path["m_AnchorMax.x"]["sourceStoredValue"] == 0.0
    assert by_path["m_AnchorMax.x"]["expectedDrivenValue"] == 0.75
    assert by_path["m_AnchorMax.y"]["expectedDrivenValue"] == 1.0
    assert by_path["m_AnchorMin.x"]["differs"] is False
    assert row["sourceScriptIdentity"] == {"assembly": "UnityEngine.UI.dll", "namespace": "UnityEngine.UI", "class": "Slider"}
    assert result["nativeGetClass"] == "not_run; SDK expected tuple evidence only"


def test_filled_image_drives_fill_amount_and_full_rect_anchors(tmp_path):
    result = plan(graph_fixture(tmp_path, image_type=3, value=0.25))
    row = result["sliders"][0]
    by_path = {r["path"]: r for r in row["overrides"]}
    assert by_path["m_AnchorMax.x"]["expectedDrivenValue"] == 1.0
    assert by_path["m_AnchorMax.y"]["expectedDrivenValue"] == 1.0
    assert by_path["m_FillAmount"]["expectedDrivenValue"] == 0.25


@pytest.mark.parametrize(("direction", "min_x", "max_x", "min_y", "max_y"), [
    (0, 0.0, 0.25, 0.0, 1.0),
    (1, 0.75, 1.0, 0.0, 1.0),
    (2, 0.0, 1.0, 0.0, 0.25),
    (3, 0.0, 1.0, 0.75, 1.0),
])
def test_four_directions_follow_pinned_sdk_axis_and_reverse(direction, min_x, max_x, min_y, max_y, tmp_path):
    row = plan(graph_fixture(tmp_path, direction=direction, value=0.25))["sliders"][0]
    fields = {r["path"]: r["expectedDrivenValue"] for r in row["overrides"]}
    assert fields["m_AnchorMin.x"] == min_x
    assert fields["m_AnchorMax.x"] == max_x
    assert fields["m_AnchorMin.y"] == min_y
    assert fields["m_AnchorMax.y"] == max_y


def test_rejects_whole_numbers_and_out_of_range_values(tmp_path):
    with pytest.raises(SliderLayoutError, match="SLIDER_LAYOUT_WHOLE"):
        plan(graph_fixture(tmp_path, whole=1))
    with pytest.raises(SliderLayoutError, match="SLIDER_LAYOUT_RANGE"):
        plan(graph_fixture(tmp_path / "range", value=2.0))


def test_rejects_multiple_slider_drivers_and_non_null_handle(tmp_path):
    with pytest.raises(SliderLayoutError, match="SLIDER_LAYOUT_MULTIPLE_DRIVERS"):
        plan(graph_fixture(tmp_path, second_driver=True))
    with pytest.raises(SliderLayoutError, match="SLIDER_LAYOUT_HANDLE"):
        plan(graph_fixture(tmp_path / "handle", handle=99))


def test_inactive_or_disabled_slider_has_no_driven_overrides(tmp_path):
    result = plan(graph_fixture(tmp_path, enabled=0))
    assert result["sliders"][0]["status"] == "inactive_or_disabled_no_visual_update"
    assert result["sliders"][0]["overrides"] == []


def test_rejects_sdk_binding_type_or_code_pin_drift(tmp_path):
    fx = graph_fixture(tmp_path)
    graph, bindings, evidence = fx
    bindings["bindings"][0]["identity"]["assembly"] = "Other.dll"
    with pytest.raises(SliderLayoutError, match="SLIDER_LAYOUT_SDK_BINDING"):
        plan(fx)


def test_rejects_unproven_image_derived_type(tmp_path):
    fx = graph_fixture(tmp_path)
    graph, bindings, evidence = fx
    evidence["pins"].clear()
    with pytest.raises(SliderLayoutError, match="SLIDER_LAYOUT_SOURCE_TYPE"):
        plan(fx)


def test_exact_outline_shadow_chain_is_proven_nonimage_and_excluded(tmp_path):
    row = plan(graph_fixture(tmp_path, with_outline=True))["sliders"][0]
    assert row["fillImageType"] == "Simple"
    excluded = row["overrides"][0]["driver"]["provenNonImageComponents"]
    outline = next(item for item in excluded if item["typeProof"]["identity"]["class"] == "Outline")
    assert outline["typeProof"]["classification"] == "non_image"
    assert [node["identity"]["class"] for node in outline["typeProof"]["baseChain"]] == ["Outline", "Shadow", "BaseMeshEffect", "UIBehaviour", "MonoBehaviour"]


def test_proven_null_fill_image_still_drives_rect_anchors(tmp_path):
    row = plan(graph_fixture(tmp_path, with_outline=True, with_image=False))["sliders"][0]
    assert row["fillImageId"] is None
    assert row["fillImageType"] == "null"
    assert row["overrides"][0]["driver"]["fillBranch"] == "anchors"
    assert {x["path"]: x["expectedDrivenValue"] for x in row["overrides"] if x["path"].startswith("m_AnchorMax")} == {
        "m_AnchorMax.x": 0.75, "m_AnchorMax.y": 1.0}


def test_rejects_unknown_component_without_sdk_or_source_declaration(tmp_path):
    fx = graph_fixture(tmp_path, with_outline=True)
    fx[1]["bindings"] = [b for b in fx[1]["bindings"] if b["identity"]["class"] != "Outline"]
    with pytest.raises(SliderLayoutError, match="SLIDER_LAYOUT_SOURCE_TYPE"):
        plan(fx)


def test_rejects_ambiguous_multiple_image_components(tmp_path):
    with pytest.raises(SliderLayoutError, match="SLIDER_LAYOUT_FILL_IMAGE"):
        plan(graph_fixture(tmp_path, second_image=True))


def test_slider_drives_fill_even_when_fill_object_and_image_are_inactive(tmp_path):
    row = plan(graph_fixture(tmp_path, image_type=3, value=0.5, fill_active=False, image_enabled=0))["sliders"][0]
    assert row["status"] == "active_enabled_driver"
    assert row["fillActiveHierarchy"] == ["fill-go", "slider-go"]
    assert row["overrides"][-1]["path"] == "m_FillAmount"
    assert row["overrides"][-1]["expectedDrivenValue"] == 0.5
