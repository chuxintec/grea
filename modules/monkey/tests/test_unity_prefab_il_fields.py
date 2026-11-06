import hashlib

import pytest

from monkey.unity_prefab_il_fields import ILFieldParseError, parse_il_field_references


def _parse(text, *, wanted=None, assembly="Assembly-CSharp.dll", digest=None):
    raw = text.encode("utf-8")
    return parse_il_field_references(
        text,
        assembly,
        wanted or [{"assembly": assembly, "namespace": "", "name": "NeutralOwner"}],
        "fixture.il",
        digest or hashlib.sha256(raw).hexdigest(),
    )


def test_neutral_owner_and_external_valuetype_identity_with_source_span():
    text = ".class public auto ansi beforefieldinit NeutralOwner\n{\n\t.field public valuetype [GameLogic]T5Game.UIBtnSoundType m_clickSound\n}\n"
    result = _parse(text)
    assert result["status"] == "schema_only"
    assert result["sourceMethodsRecovered"] == 0
    assert result["sourceCodeExecuted"] is False
    row = result["fieldReferences"][0]
    assert row["owner"] == {"assembly": "Assembly-CSharp.dll", "namespace": "", "name": "NeutralOwner"}
    assert row["targetType"] == {"assembly": "GameLogic.dll", "namespace": "T5Game", "name": "UIBtnSoundType"}
    assert row["semanticKind"] == "unresolved-valuetype-not-proven-enum"
    source_line = "\t.field public valuetype [GameLogic]T5Game.UIBtnSoundType m_clickSound"
    start, end = row["sourceEvidence"]["byteSpan"]
    assert text.encode()[start:end].decode() == source_line
    assert row["sourceEvidence"]["lineSha256"] == hashlib.sha256(source_line.encode()).hexdigest()


def test_same_named_fields_in_other_owner_nested_type_and_method_are_not_attributed():
    text = '''.class public auto ansi T5Game.Owner
{
  .field public valuetype [GameLogic]T5Game.RealType wantedField
  // .field public valuetype [Wrong]Fake.Type wantedField
  .field public string note
  .method public hidebysig instance void Run() cil managed
  {
    ldstr ".field public valuetype [Wrong]Fake.Type wantedField";
    .field public valuetype [Wrong]Method.Type methodFake
    ret
  }
  .class nested public Inner
  {
    .field public valuetype [Wrong]Nested.Type wantedField
  }
}
.class public auto ansi Other.Owner
{
  .field public valuetype [Wrong]Other.Type wantedField
}
'''
    wanted = [{"assembly": "Assembly-CSharp", "namespace": "T5Game", "name": "Owner"}]
    result = _parse(text, wanted=wanted)
    assert len(result["fieldReferences"]) == 1
    row = result["fieldReferences"][0]
    assert row["fieldName"] == "wantedField"
    assert row["targetType"] == {"assembly": "GameLogic.dll", "namespace": "T5Game", "name": "RealType"}


def test_owner_must_match_full_namespace_and_assembly():
    text = '''.class public T5Game.Owner
{
  .field public valuetype [GameLogic]T5Game.SoundType sound
}
.class public Other.Owner
{
  .field public valuetype [OtherAssembly]Wrong.SoundType sound
}
'''
    result = _parse(text, wanted=[{"assembly": "Assembly-CSharp.dll", "namespace": "T5Game", "name": "Owner"}])
    assert len(result["fieldReferences"]) == 1
    assert result["fieldReferences"][0]["owner"]["namespace"] == "T5Game"
    with pytest.raises(ILFieldParseError, match="owner assembly differs"):
        _parse(text, wanted=[{"assembly": "Wrong.dll", "namespace": "T5Game", "name": "Owner"}])
    with pytest.raises(ILFieldParseError, match="wanted top-level class not found"):
        _parse(text, wanted=[{"assembly": "Assembly-CSharp.dll", "namespace": "Wrong", "name": "Owner"}])


def test_class_pointer_and_vector_pointer_array_preserve_complete_type_without_native_claim():
    text = '''.class public auto ansi NeutralRenamedBinder
{
  .field public class [UnityEngine.UI]UnityEngine.UI.Text m_labelBind
  .field public class [UnityEngine.CoreModule]UnityEngine.Renderer[] m_renderers
  .field private static class [mscorlib]System.Action`1<int32> s_playSoundAction
  .field public literal int32 StaticValue = int32(0)
}
'''
    rows = _parse(text, wanted=[{"assembly": "Assembly-CSharp.dll", "namespace": "", "name": "NeutralRenamedBinder"}])["fieldReferences"]
    assert [row["fieldName"] for row in rows] == ["m_labelBind", "m_renderers"]
    assert rows[0]["fieldTypeKind"] == "class"
    assert rows[0]["targetType"] == {"assembly": "UnityEngine.UI.dll", "namespace": "UnityEngine.UI", "name": "Text"}
    assert rows[0]["arrayRank"] == 0
    assert rows[0]["semanticKind"] == "class-reference-not-proven-native"
    assert rows[1]["targetType"] == {"assembly": "UnityEngine.CoreModule.dll", "namespace": "UnityEngine", "name": "Renderer"}
    assert rows[1]["arrayRank"] == 1


def test_multidimensional_class_array_is_rejected():
    text = ".class public NeutralOwner {\n.field public class [Engine]UnityEngine.Renderer[,] values\n}\n"
    with pytest.raises(ILFieldParseError, match="one-dimensional class arrays"):
        _parse(text)


def test_class_pointer_and_vector_pointer_array_preserve_complete_type_without_native_claim():
    text = '''.class public auto ansi NeutralRenamedBinder
{
  .field public class [UnityEngine.UI]UnityEngine.UI.Text m_labelBind
  .field public class [UnityEngine.CoreModule]UnityEngine.Renderer[] m_renderers
  .field private static class [mscorlib]System.Action`1<int32> s_playSoundAction
  .field public literal int32 StaticValue = int32(0)
}
'''
    rows = _parse(text, wanted=[{"assembly": "Assembly-CSharp.dll", "namespace": "", "name": "NeutralRenamedBinder"}])["fieldReferences"]
    assert [row["fieldName"] for row in rows] == ["m_labelBind", "m_renderers"]
    assert rows[0]["fieldTypeKind"] == "class"
    assert rows[0]["targetType"] == {"assembly": "UnityEngine.UI.dll", "namespace": "UnityEngine.UI", "name": "Text"}
    assert rows[0]["arrayRank"] == 0
    assert rows[0]["semanticKind"] == "class-reference-not-proven-native"
    assert rows[1]["targetType"] == {"assembly": "UnityEngine.CoreModule.dll", "namespace": "UnityEngine", "name": "Renderer"}
    assert rows[1]["arrayRank"] == 1


def test_multidimensional_class_array_is_rejected():
    text = ".class public NeutralOwner {\n.field public class [Engine]UnityEngine.Renderer[,] values\n}\n"
    with pytest.raises(ILFieldParseError, match="one-dimensional class arrays"):
        _parse(text)


@pytest.mark.parametrize("type_ref", [
    "[GameLogic]T5Game.Outer/Inner",
    "[GameLogic]T5Game.Generic`1<int32>",
    '[GameLogic]"T5Game.QuotedType"',
])
def test_unsupported_nested_generic_or_quoted_valuetype_is_rejected(type_ref):
    text = f".class public NeutralOwner\n{{\n .field public valuetype {type_ref} value\n}}\n"
    with pytest.raises(ILFieldParseError, match="unsupported"):
        _parse(text)


def test_rejects_duplicate_owner_duplicate_field_and_hash_drift():
    duplicate_owner = ".class public NeutralOwner { }\n.class public NeutralOwner { }\n"
    with pytest.raises(ILFieldParseError, match="ambiguous duplicate owner"):
        _parse(duplicate_owner)
    duplicate_field = ".class public NeutralOwner {\n.field public valuetype [A]Ns.Type field\n.field public valuetype [B]Ns.Type field\n}\n"
    with pytest.raises(ILFieldParseError, match="duplicate field"):
        _parse(duplicate_field)
    duplicate_with_primitive = ".class public NeutralOwner {\n.field public class [Engine]Engine.Object field\n.field public string field\n}\n"
    with pytest.raises(ILFieldParseError, match="duplicate field"):
        _parse(duplicate_with_primitive)
    with pytest.raises(ILFieldParseError, match="SHA256"):
        _parse(".class public NeutralOwner { }\n", digest="0" * 64)




def test_token_budget_is_enforced(monkeypatch):
    monkeypatch.setattr("monkey.unity_prefab_il_fields.MAX_TOKENS", 1)
    text = ".class public NeutralOwner { }\n"
    with pytest.raises(ILFieldParseError, match="token count exceeds budget"):
        _parse(text)


def test_static_generic_with_nested_valuetype_marker_is_not_serialized_field_data():
    text = '.class public NeutralOwner {\n.field private static class [Base]List`1<valuetype [Engine]Engine.Vertex> cache\n.field public valuetype [Settings]Config.Mode choice\n}\n'
    result = _parse(text)
    assert [r['fieldName'] for r in result['fieldReferences']] == ['choice']
