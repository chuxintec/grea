import hashlib

from monkey.unity_prefab_source_ui import classify_source_ui_static
from monkey.unity_prefab_types import parse_declarations


def _classify(tmp_path, body, prefix="public class CustomImage : UnityEngine.UI.Image"):
    raw = (prefix + " {\n" + body + "\n}\n").encode("utf-8")
    path = tmp_path / "CustomImage.cs"
    path.write_bytes(raw)
    parsed = parse_declarations(raw.decode(), assembly="Assembly-CSharp.dll", source_path=str(path),
                                source_sha256=hashlib.sha256(raw).hexdigest())
    return classify_source_ui_static(parsed,
        {"assembly": "Assembly-CSharp.dll", "namespace": "", "name": "CustomImage"},
        "UnityEngine.UI.Image")


def test_hash_pinned_field_only_declaration_does_not_replace_missing_original_method_metadata(tmp_path):
    evidence = _classify(tmp_path, "public float SourceLayoutWeight;")
    assert evidence["status"] == "source-ui-behavior-unverified"
    assert evidence["staticSemanticsProven"] is False
    assert evidence["sourceTextMemberScanStatus"] == "complete"
    assert evidence["methodInventoryStatus"] == "unproven-without-independent-original-method-metadata"
    assert evidence["sourceMethodInventoryProvenanceStatus"] == "missing-independent-original-method-metadata"
    assert evidence["sourceMethodCount"] == 0
    assert evidence["sourceFieldNames"] == ["SourceLayoutWeight"]
    assert evidence["sourceCodeExecuted"] is False
    assert evidence["sourceBaseChain"] == ["CustomImage", "UnityEngine.UI.Image", "UnityEngine.UI.MaskableGraphic",
                                            "UnityEngine.UI.Graphic", "UnityEngine.EventSystems.UIBehaviour",
                                            "UnityEngine.MonoBehaviour"]


def test_render_override_remains_partial_even_when_target_base_can_render(tmp_path):
    evidence = _classify(tmp_path, "protected override void OnPopulateMesh(UnityEngine.UI.VertexHelper vh) { vh.Clear(); }")
    assert evidence["status"] == "source-ui-behavior-unverified"
    assert evidence["staticSemanticsProven"] is False
    assert "method-property-or-block-member-present" in evidence["reasons"]
    assert any(row["name"] == "OnPopulateMesh" for row in evidence["sourceMethods"])


def test_all_supported_native_ui_bases_keep_empty_custom_subclasses_unverified(tmp_path):
    # A base Graphic being drawable is independent from whether the source
    # subclass had renderer/lifecycle behavior. Missing original method
    # metadata keeps each generated native-base carrier partial.
    for base in ("Image", "RawImage", "Text"):
        class_name = "Custom" + base
        source = f"public class {class_name} : UnityEngine.UI.{base} {{ }}\n"
        raw = source.encode("utf-8")
        path = tmp_path / (class_name + ".cs")
        path.write_bytes(raw)
        parsed = parse_declarations(raw.decode(), assembly="Assembly-CSharp.dll", source_path=str(path),
                                    source_sha256=hashlib.sha256(raw).hexdigest())
        evidence = classify_source_ui_static(
            parsed, {"assembly": "Assembly-CSharp.dll", "namespace": "", "name": class_name},
            "UnityEngine.UI." + base)
        assert evidence["targetRenderingIsSeparate"] is True
        assert evidence["staticSemanticsProven"] is False
        assert evidence["status"] == "source-ui-behavior-unverified"
        assert evidence["sourceMethodInventoryProvenanceStatus"] == "missing-independent-original-method-metadata"


def test_native_readback_keeps_renderability_separate_and_blocks_static_pass_for_unknown_ui():
    from pathlib import Path

    path = Path(__file__).parents[1] / "src/monkey/targets/unity_source/UnityPrefabStaticReadback.cs"
    source = path.read_text(encoding="utf-8")
    assert "bool targetCanRender, sourceStaticSemanticsVerified;" in source
    assert "if(!sourceVerified)limitations.Add(\"unverified-source-ui-static-semantics:\"" in source
    assert '"partial-source-ui-static-semantics-unverified"' in source
    assert 'v.StartsWith("unverified-source-ui-static-semantics:", StringComparison.Ordinal)' in source


def test_external_method_declaration_is_unknown_not_assumed_inert(tmp_path):
    evidence = _classify(tmp_path, "public void Rebuild();")
    assert evidence["staticSemanticsProven"] is False
    assert evidence["sourceMethodCount"] == 1


def test_property_and_field_initializer_remain_partial(tmp_path):
    prop = _classify(tmp_path, "public float Scale { get { return 1f; } }")
    initializer = _classify(tmp_path, "public float Scale = 1f;")
    assert prop["staticSemanticsProven"] is False
    assert initializer["staticSemanticsProven"] is False


def test_partial_and_lifecycle_marked_types_remain_partial(tmp_path):
    partial = _classify(tmp_path, "public float Value;", "public partial class CustomImage : UnityEngine.UI.Image")
    lifecycle = _classify(tmp_path, "public float Value;",
                          "[UnityEngine.ExecuteAlways] public class CustomImage : UnityEngine.UI.Image")
    assert partial["staticSemanticsProven"] is False
    assert lifecycle["staticSemanticsProven"] is False


def test_custom_intermediate_base_cannot_inherit_leaf_only_static_proof(tmp_path):
    source = "public class ImageBase : UnityEngine.UI.Image { protected override void OnPopulateMesh(UnityEngine.UI.VertexHelper vh) {} }\n" \
             "public class CustomImage : ImageBase { public float Value; }\n"
    path = tmp_path / "CustomImage.cs"
    raw = source.encode()
    path.write_bytes(raw)
    parsed = parse_declarations(source, assembly="Assembly-CSharp.dll", source_path=str(path),
                                source_sha256=hashlib.sha256(raw).hexdigest())
    evidence = classify_source_ui_static(parsed,
        {"assembly": "Assembly-CSharp.dll", "namespace": "", "name": "CustomImage"},
        "UnityEngine.UI.Image")
    assert evidence["staticSemanticsProven"] is False
    assert evidence["reasons"] == ["source-base-chain-is-not-exactly-proven-to-native-ui-base"]


def test_additional_interface_member_is_not_assumed_presentation_neutral(tmp_path):
    evidence = _classify(tmp_path, "public float Value;",
                         "public class CustomImage : UnityEngine.UI.Image, System.IDisposable")
    assert evidence["staticSemanticsProven"] is False
    assert "additional-interface-or-base-type-unverified" in evidence["reasons"]


def test_changed_source_declaration_hash_fails_closed(tmp_path):
    evidence = _classify(tmp_path, "public float Value;")
    path = tmp_path / "CustomImage.cs"
    original_text = path.read_text(encoding="utf-8")
    path.write_text("public class CustomImage : UnityEngine.UI.Image { public void Draw() {} }", encoding="utf-8")
    parsed = parse_declarations(original_text,
                                assembly="Assembly-CSharp.dll", source_path=str(path),
                                source_sha256=evidence["sourceDeclarationSha256"])
    rejected = classify_source_ui_static(parsed,
        {"assembly": "Assembly-CSharp.dll", "namespace": "", "name": "CustomImage"},
        "UnityEngine.UI.Image")
    assert rejected["status"] == "source-ui-behavior-unverified"
    assert rejected["reasons"] == ["source-declaration-hash-changed"]
