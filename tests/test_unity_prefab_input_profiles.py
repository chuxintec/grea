import unittest

from monkey import unity_prefab_types
from monkey.unity_prefab_input_profiles import (
    INPUTFIELD,
    UI_INHERITED_FIELDS as INPUT_UI_FIELDS,
    merge_inputfield_native_profile,
    match_inputfield_derived_type,
    validate_inputfield_type_tree,
)
from monkey.unity_prefab_types import emit_schema, parse_declarations, propose_schema


def _neutral_typed_schema(extra=None):
    children = [
        {"name": "m_GameObject", "type": "PPtr<GameObject>", "children": []},
        {"name": "m_Enabled", "type": "UInt8", "children": []},
        {"name": "m_Script", "type": "PPtr<MonoScript>", "children": []},
        {"name": "m_Name", "type": "string", "children": []},
    ]
    children.extend(
        {"name": name, "type": type_tree, "children": []}
        for name, (type_tree, _cs_type) in sorted(INPUT_UI_FIELDS[INPUTFIELD].items())
    )
    if extra:
        children.extend(extra)
    return {"name": "NeutralInputTree", "type": "MonoBehaviour", "children": children}


class InputProfileTests(unittest.TestCase):
    def test_profile_merges_idempotently_without_mutating_caller_maps(self):
        bases = {"UnityEngine.MonoBehaviour": "UnityEngine.MonoBehaviour"}
        chains = {}
        inherited = {}
        merged = merge_inputfield_native_profile(bases, chains, inherited)
        again = merge_inputfield_native_profile(merged["nativeBases"], merged["baseInheritance"],
                                                merged["uiInheritedFields"])
        self.assertEqual(merged, again)
        self.assertEqual({"UnityEngine.MonoBehaviour": "UnityEngine.MonoBehaviour"}, bases)
        self.assertEqual({}, chains)
        self.assertEqual({}, inherited)
        self.assertEqual(28, len(merged["uiInheritedFields"][INPUTFIELD]))

    def test_neutral_derived_class_matches_inherited_tree_and_keeps_unknown_code_disabled(self):
        source = """
using UnityEngine.UI;
namespace NeutralFixture {
    public class TextEntryControl : InputField { }
}
"""
        parsed = parse_declarations(source, assembly="NeutralFixture.dll", source_path="neutral-input.cs")
        identity = {"assembly": "NeutralFixture.dll", "namespace": "NeutralFixture", "name": "TextEntryControl"}
        result = match_inputfield_derived_type(parsed, identity, _neutral_typed_schema())
        self.assertEqual("disabled_schema_carrier", result["status"])
        self.assertEqual(INPUTFIELD, result["nativeSourceBase"])
        self.assertFalse(result["componentEnabled"])
        self.assertEqual("not_recovered_from-static-declarations", result["sourceMethods"])
        self.assertEqual(28, result["nativeInheritedTypeTree"]["serializedFieldCount"])

    def test_existing_planner_still_validates_neutral_custom_enum_fields(self):
        source = """
using UnityEngine.UI;
namespace NeutralFixture {
    public enum CounterMode : int { None = 0, Compact = 2 }
    public class TextEntryControl : InputField { [SerializeField] private CounterMode m_CounterMode; }
}
"""
        parsed = parse_declarations(source, assembly="NeutralFixture.dll", source_path="neutral-input.cs")
        identity = {"assembly": "NeutralFixture.dll", "namespace": "NeutralFixture", "name": "TextEntryControl"}
        tree = _neutral_typed_schema([{"name": "m_CounterMode", "type": "int", "children": []}])
        matched = match_inputfield_derived_type(parsed, identity, tree)
        self.assertEqual("disabled_schema_carrier", matched["status"])
        self.assertEqual("CounterMode", matched["sourceDeclaredFields"][0]["type"])

        merged = merge_inputfield_native_profile({}, {}, {})
        old_bases = dict(unity_prefab_types.NATIVE_BASES)
        old_chains = dict(unity_prefab_types._NATIVE_COMPONENT_CHAINS)
        old_inherited = {key: dict(value) for key, value in unity_prefab_types._UI_INHERITED_FIELDS.items()}
        try:
            unity_prefab_types.NATIVE_BASES.clear()
            unity_prefab_types.NATIVE_BASES.update(merged["nativeBases"])
            unity_prefab_types._NATIVE_COMPONENT_CHAINS.clear()
            unity_prefab_types._NATIVE_COMPONENT_CHAINS.update(merged["nativeComponentChains"])
            unity_prefab_types._UI_INHERITED_FIELDS.clear()
            unity_prefab_types._UI_INHERITED_FIELDS.update(merged["uiInheritedFields"])
            proposal = propose_schema(parsed, identity, tree)
            self.assertEqual("schema_only", proposal["status"])
            enum_field = next(field for field in proposal["fields"] if field["name"] == "m_CounterMode")
            self.assertEqual("CounterMode", enum_field["csType"])
            self.assertIn("public class TextEntryControl : UnityEngine.UI.InputField", emit_schema(proposal))
            self.assertNotIn("LateUpdate", emit_schema(proposal))
        finally:
            unity_prefab_types.NATIVE_BASES.clear()
            unity_prefab_types.NATIVE_BASES.update(old_bases)
            unity_prefab_types._NATIVE_COMPONENT_CHAINS.clear()
            unity_prefab_types._NATIVE_COMPONENT_CHAINS.update(old_chains)
            unity_prefab_types._UI_INHERITED_FIELDS.clear()
            unity_prefab_types._UI_INHERITED_FIELDS.update(old_inherited)

    def test_type_tree_rejects_unproven_extra_or_changed_inherited_field(self):
        tree = _neutral_typed_schema([{"name": "m_Unexplained", "type": "int", "children": []}])
        with self.assertRaisesRegex(ValueError, "differs from profile schema"):
            validate_inputfield_type_tree(tree)

        changed = _neutral_typed_schema()
        child = next(row for row in changed["children"] if row["name"] == "m_AsteriskChar")
        child["type"] = "int"
        with self.assertRaisesRegex(ValueError, "changed=.*m_AsteriskChar"):
            validate_inputfield_type_tree(changed)


if __name__ == "__main__":
    unittest.main()
