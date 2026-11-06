import unittest

from grea.recovery.unity_prefab_types import emit_disabled_carrier, emit_schema, parse_declarations, propose_schema


def parse(text, assembly="GameBase.dll"):
    return parse_declarations(text, assembly=assembly, source_path="fixture.cs")


class UnityPrefabTypesTests(unittest.TestCase):
    def test_native_image_subclass_with_no_own_fields_is_valid(self):
        parsed = parse("using UnityEngine.UI; namespace DodGame { public class DodImage : Image { } }")
        proposal = propose_schema(parsed, {"assembly": "GameBase.dll", "namespace": "DodGame", "name": "DodImage"},
                                  {"children": [
                                      {"name": "m_Material", "type": "PPtr<$Material>"},
                                      {"name": "m_Color", "type": "ColorRGBA"},
                                      {"name": "m_RaycastTarget", "type": "UInt8"},
                                      {"name": "m_RaycastPadding", "type": "Vector4f"},
                                      {"name": "m_Maskable", "type": "UInt8"},
                                      {"name": "m_OnCullStateChanged", "type": "CullStateChangedEvent"},
                                      {"name": "m_Sprite", "type": "PPtr<$Sprite>"},
                                  ]})
        self.assertEqual(proposal["status"], "schema_only")
        self.assertEqual(proposal["base"], "UnityEngine.UI.Image")
        self.assertEqual(proposal["fields"], [])
        self.assertEqual({field["name"] for field in proposal["inheritedFields"]},
                         {"m_Material", "m_Color", "m_RaycastTarget", "m_RaycastPadding",
                          "m_Maskable", "m_OnCullStateChanged", "m_Sprite"})
        emitted = emit_schema(proposal)
        self.assertIn("DodImage : UnityEngine.UI.Image", emitted)
        self.assertNotIn("void ", emitted)

    def test_text_subclass_preserves_exact_enum_storage_and_constants(self):
        source = """using UnityEngine.UI;
namespace DodGame {
 public enum EGameTextType { None = 0, UiText = 1, CodeText = 2 }
 public class DodText : Text { public int TextId; public EGameTextType GameTextType; public int ReadOnlyProperty { get; } }
}
"""
        parsed = parse(source)
        schema = {"children": [
            {"name": "m_Material", "type": "PPtr<$Material>"},
            {"name": "m_Color", "type": "ColorRGBA"},
            {"name": "m_RaycastTarget", "type": "UInt8"},
            {"name": "m_RaycastPadding", "type": "Vector4f"},
            {"name": "m_Maskable", "type": "UInt8"},
            {"name": "m_OnCullStateChanged", "type": "CullStateChangedEvent"},
            {"name": "m_FontData", "type": "FontData", "children": [{"name": "m_FontSize", "type": "int"}]},
            {"name": "m_Text", "type": "string"},
            {"name": "TextId", "type": "int"},
            {"name": "GameTextType", "type": "int"},
        ]}
        proposal = propose_schema(parsed, {"assembly": "GameBase.dll", "namespace": "DodGame", "name": "DodText"}, schema)
        self.assertEqual(proposal["status"], "schema_only", proposal["gaps"])
        self.assertEqual([f["name"] for f in proposal["fields"]], ["TextId", "GameTextType"])
        self.assertEqual({field["name"] for field in proposal["inheritedFields"]},
                         {"m_Material", "m_Color", "m_RaycastTarget", "m_RaycastPadding",
                          "m_Maskable", "m_OnCullStateChanged", "m_FontData", "m_Text"})
        self.assertEqual(proposal["enums"][0]["values"][-1], {"name": "CodeText", "value": 2})
        emitted = emit_schema(proposal)
        self.assertIn("public int TextId;", emitted)
        self.assertIn("public EGameTextType GameTextType;", emitted)
        self.assertNotIn("m_FontData", emitted)
        self.assertNotIn("m_OnCullStateChanged", emitted)
        self.assertIn("CodeText = 2", emitted)
        self.assertNotIn("ReadOnlyProperty", emitted)

    def test_implicit_enum_values_follow_csharp_language_rules(self):
        parsed = parse("""using Il2CppDummyDll;
using UnityEngine.UI;
namespace X {
 public enum Kind : short {
  [Token(Token = "0x01")] None,
  [Token(Token = "0x02")] A = 4,
  [Token(Token = "0x03")] B,
  [Token(Token = "0x04")] C = -2,
  [Token(Token = "0x05")] D
 }
 public class C : Text { public Kind Value; }
}
""")
        proposal = propose_schema(parsed, {"assembly": "GameBase.dll", "namespace": "X", "name": "C"},
                                  {"children": [{"name": "Value", "type": "short"}]})
        self.assertEqual(proposal["status"], "schema_only", proposal["gaps"])
        self.assertEqual([row["value"] for row in proposal["enums"][0]["values"]], [0, 4, 5, -2, -1])

    def test_enum_expression_and_underlying_overflow_stay_gaps(self):
        expression = parse("using UnityEngine.UI; namespace X { public enum Kind { A = 1 + 2 } public class C : Text { public Kind Value; } }")
        proposal = propose_schema(expression, {"assembly": "GameBase.dll", "namespace": "X", "name": "C"},
                                  {"children": [{"name": "Value", "type": "int"}]})
        self.assertEqual(proposal["status"], "gap")
        overflow = parse("using UnityEngine.UI; namespace X { public enum Kind : byte { A = 255, B } public class C : Text { public Kind Value; } }")
        proposal = propose_schema(overflow, {"assembly": "GameBase.dll", "namespace": "X", "name": "C"},
                                  {"children": [{"name": "Value", "type": "byte"}]})
        self.assertEqual(proposal["status"], "gap")

    def test_unknown_and_ambiguous_bases_are_gaps(self):
        unknown = parse("namespace X { public class C : GameBase { public int Value; } }")
        proposal = propose_schema(unknown, {"assembly": "GameBase.dll", "namespace": "X", "name": "C"},
                                  {"children": [{"name": "Value", "type": "int"}]})
        self.assertEqual(proposal["status"], "gap")
        self.assertIn("base", proposal["reason"] if "reason" in proposal else proposal["gaps"][0])

        ambiguous = parse("using A; using B; namespace X { public class C : Image { } }\nnamespace A { public class Image {} }\nnamespace B { public class Image {} }")
        proposal = propose_schema(ambiguous, {"assembly": "GameBase.dll", "namespace": "X", "name": "C"}, {"children": []})
        self.assertEqual(proposal["status"], "gap")

    def test_nested_custom_field_reference_stays_a_gap(self):
        parsed = parse("using UnityEngine.UI; namespace X { public struct Inner { public int X; } public class C : Image { public Inner Nested; } }")
        proposal = propose_schema(parsed, {"assembly": "GameBase.dll", "namespace": "X", "name": "C"},
                                  {"children": [{"name": "Nested", "type": "Inner", "children": [{"name": "X", "type": "int"}]}]})
        self.assertEqual(proposal["status"], "gap")
        with self.assertRaises(Exception):
            emit_schema(proposal)

    def test_base_mesh_effect_keeps_abstract_behavior_gap(self):
        parsed = parse("using UnityEngine.UI; namespace X { public class Outline : BaseMeshEffect { public float Width; } }")
        proposal = propose_schema(parsed, {"assembly": "GameBase.dll", "namespace": "X", "name": "Outline"},
                                  {"children": [{"name": "Width", "type": "float"}]})
        self.assertEqual(proposal["status"], "gap")
        self.assertTrue(any("ModifyMesh" in gap for gap in proposal["gaps"]))
        self.assertFalse(any("ModifyMesh" in str(proposal.get("fields")) for _ in [0]))
        with self.assertRaises(Exception):
            emit_schema(proposal)
        disabled = emit_disabled_carrier(proposal)
        self.assertIn("public class Outline : UnityEngine.MonoBehaviour", disabled["source"])
        self.assertIn("public float Width;", disabled["source"])
        self.assertNotIn("ModifyMesh", disabled["source"])
        metadata = disabled["metadata"]
        self.assertEqual(metadata["sourceIdentity"], {"assembly": "GameBase.dll", "namespace": "X", "name": "Outline"})
        self.assertEqual(metadata["declaredSourceBase"], "UnityEngine.UI.BaseMeshEffect")
        self.assertEqual(metadata["nativeTargetBase"], "UnityEngine.MonoBehaviour")
        self.assertEqual(metadata["behavior"], "disabled-required")
        self.assertEqual(metadata["staticPresentation"], "unsupported")
        self.assertFalse(metadata["sourceBaseRestored"])
        self.assertEqual(metadata["status"], "disabled_schema_carrier")

    def test_disabled_carrier_rejects_unknown_fields(self):
        parsed = parse("using UnityEngine.UI; namespace X { public class Outline : BaseMeshEffect { public float Width; } }")
        proposal = propose_schema(parsed, {"assembly": "GameBase.dll", "namespace": "X", "name": "Outline"},
                                  {"children": [{"name": "Width", "type": "float"}, {"name": "m_Unknown", "type": "int"}]})
        self.assertEqual(proposal["status"], "gap")
        with self.assertRaises(Exception):
            emit_disabled_carrier(proposal)

    def test_unsafe_source_identifiers_are_rejected(self):
        parsed = parse("using UnityEngine.UI; namespace X { public class C : Image { public int bad-name; } }")
        proposal = propose_schema(parsed, {"assembly": "GameBase.dll", "namespace": "X", "name": "C"},
                                  {"children": [{"name": "bad-name", "type": "int"}]})
        self.assertEqual(proposal["status"], "gap")

    def test_foreign_enum_requires_exact_il_field_assembly_reference(self):
        parsed = parse("using UnityEngine; using Shared; namespace App { public class Panel : MonoBehaviour { public Mode Selection; } }")
        other = parse("namespace Shared { public enum Mode { Off = 0, On = 4 } }", assembly="Settings.dll")
        parsed['declarations'].extend(other['declarations'])
        identity = dict(assembly='GameBase.dll', namespace='App', name='Panel')
        schema = dict(children=[dict(name='Selection', type='int')])
        self.assertEqual(propose_schema(parsed, identity, schema)['status'], 'gap')
        owner = next(d for d in parsed['declarations'] if d['identity'] == identity)
        owner['fieldTypeReferences'] = {'Selection': dict(targetType=dict(assembly='Settings.dll', namespace='Shared', name='Mode'))}
        proposal = propose_schema(parsed, identity, schema)
        self.assertEqual(proposal['status'], 'schema_only')
        self.assertEqual(proposal['fields'][0]['csType'], 'global::Shared.Mode')
        self.assertEqual(proposal['enums'][0]['identity']['assembly'], 'Settings.dll')

    def test_raw_image_base_retains_native_texture_and_uv_without_fake_methods(self):
        parsed = parse('using UnityEngine.UI; namespace Renamed { public class Preview : RawImage {} }')
        proposal = propose_schema(parsed, dict(assembly='GameBase.dll', namespace='Renamed', name='Preview'),
            dict(children=[dict(name='m_Texture', type='PPtr<$Texture>'), dict(name='m_UVRect', type='Rectf')]))
        self.assertEqual(proposal['status'], 'schema_only')
        self.assertEqual(proposal['fields'], [])
        self.assertIn('UnityEngine.UI.RawImage', emit_schema(proposal))
        self.assertNotIn('OnPopulateMesh', emit_schema(proposal))

    def test_native_ui_pointer_needs_exact_framework_field_metadata(self):
        parsed = parse('using UnityEngine; using UnityEngine.UI; namespace App { public class Binder : MonoBehaviour { public Text Label; } }')
        identity = dict(assembly='GameBase.dll', namespace='App', name='Binder')
        schema = dict(children=[dict(name='Label', type='PPtr<$Text>')])
        self.assertEqual(propose_schema(parsed, identity, schema)['status'], 'gap')
        parsed['declarations'][0]['fieldTypeReferences'] = {'Label': dict(fieldTypeKind='class', arrayRank=0,
            targetType=dict(assembly='UnityEngine.UI.dll', namespace='UnityEngine.UI', name='Text'))}
        proposal = propose_schema(parsed, identity, schema)
        self.assertEqual(proposal['status'], 'schema_only')
        self.assertEqual(proposal['fields'][0]['csType'], 'UnityEngine.UI.Text')

    def test_native_renderer_array_preserves_element_type_and_rank(self):
        parsed = parse('using UnityEngine; namespace App { public class Binder : MonoBehaviour { public Renderer[] Targets; } }')
        parsed['declarations'][0]['fieldTypeReferences'] = {'Targets': dict(fieldTypeKind='class', arrayRank=1,
            targetType=dict(assembly='UnityEngine.CoreModule.dll', namespace='UnityEngine', name='Renderer'))}
        schema = dict(children=[dict(name='Targets', type='vector', children=[dict(name='Array', type='Array', children=[
            dict(name='size', type='int'), dict(name='data', type='PPtr<$Renderer>')])])])
        proposal = propose_schema(parsed, dict(assembly='GameBase.dll', namespace='App', name='Binder'), schema)
        self.assertEqual(proposal['status'], 'schema_only')
        self.assertEqual(proposal['fields'][0]['csType'], 'UnityEngine.Renderer[]')

    def test_custom_same_name_class_is_not_replaced_by_native_gameobject(self):
        parsed = parse('using UnityEngine; namespace App { public class Binder : MonoBehaviour { public GameObject Value; } }')
        parsed['declarations'][0]['fieldTypeReferences'] = {'Value': dict(fieldTypeKind='class', arrayRank=0,
            targetType=dict(assembly='Custom.dll', namespace='App', name='GameObject'))}
        proposal = propose_schema(parsed, dict(assembly='GameBase.dll', namespace='App', name='Binder'), dict(children=[dict(name='Value', type='PPtr<GameObject>')]))
        self.assertEqual(proposal['status'], 'gap')

    def test_declared_bool_stored_as_uint8_does_not_become_an_integer_field(self):
        parsed = parse('using UnityEngine; namespace Renamed { public class Flag : MonoBehaviour { public bool Visible; } }')
        proposal = propose_schema(parsed, dict(assembly='GameBase.dll', namespace='Renamed', name='Flag'), dict(children=[dict(name='Visible', type='UInt8')]))
        self.assertEqual(proposal['status'], 'schema_only')
        self.assertEqual(proposal['fields'][0]['csType'], 'bool')


if __name__ == "__main__":
    unittest.main()
