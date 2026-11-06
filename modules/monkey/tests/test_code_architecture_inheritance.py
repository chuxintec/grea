import hashlib
import unittest

from monkey.code_architecture_inheritance import (
    InheritanceEvidenceError,
    resolve_inherited_members,
)




def _row(class_id, name, namespace, path, source, *, kind="class"):
    raw = source.encode("utf-8") if isinstance(source, str) else source
    digest = hashlib.sha256(raw).hexdigest()
    return ({"classId": class_id, "name": name, "namespace": namespace, "kind": kind,
             "path": path, "sha256": digest, "bytes": len(raw)},
            {"path": path, "sha256": digest, "bytes": len(raw), "source": raw})


def _resolve(records, mappings, requirements, **kwargs):
    return resolve_inherited_members(records, mappings, requirements, **kwargs)["results"]


class CodeArchitectureInheritanceTests(unittest.TestCase):
    def test_member_evidence_uses_absolute_source_line_numbers(self):
        text='// heading\n\nnamespace Demo {\npublic class Base {\n\n    public int State;\n\n    public void Bind() {}\n}\n}\n'
        base, source = _row('base','Base','Demo','Base.cs',text)
        result = _resolve([base], {'Base.cs':source}, {'base':['Bind','State']})[0]
        self.assertEqual(result['requiredMembers']['State']['line'], 6)
        self.assertEqual(result['requiredMembers']['Bind']['line'], 8)



    def test_conditional_parent_declarations_cannot_supply_inherited_members(self):
        parent, parent_map = _row('base','Base','Demo','Base.cs',
            'namespace Demo { public class Base {\n#if false\npublic void Bind() {}\n#endif\n} }')
        child, child_map = _row('child','Child','Demo','Child.cs',
            'namespace Demo { public class Child : Base { } }')
        result = _resolve([child,parent], {'Child.cs':child_map,'Base.cs':parent_map}, {'child':['Bind']})[0]
        self.assertFalse(result['requiredMembers']['Bind']['satisfied'])
        self.assertIn('conditional_compilation_unsupported', result['blockers'])

    def test_only_public_or_protected_direct_base_members_are_inherited(self):
        base_source = """namespace Demo { public class Base {
            public void Bind() { }
            protected int Snapshot;
            protected internal object Controller { get; set; }
            internal string InternalOnly;
            private void Hidden() { }
            private int LifetimeCancellation;
        } }
        """
        child_source = "namespace Demo { public class Child : Base { } }"
        base, base_map = _row("base", "Base", "Demo", "Base.cs", base_source)
        child, child_map = _row("child", "Child", "Demo", "Child.cs", child_source)
        result = _resolve([child, base], {"Base.cs": base_map, "Child.cs": child_map},
                          {"child": {"Bind": "method", "Snapshot": "field", "Controller": "property",
                                     "Hidden": "method", "LifetimeCancellation": "field", "InternalOnly": "field"}})[0]
        self.assertTrue(result["requiredMembers"]["Bind"]["satisfied"])
        self.assertTrue(result["requiredMembers"]["Snapshot"]["satisfied"])
        self.assertTrue(result["requiredMembers"]["Controller"]["satisfied"])
        self.assertFalse(result["requiredMembers"]["Hidden"]["satisfied"])
        self.assertFalse(result["requiredMembers"]["LifetimeCancellation"]["satisfied"])
        self.assertFalse(result["requiredMembers"]["InternalOnly"]["satisfied"])
        self.assertIn("private_declaration_not_inherited:Hidden", result["blockers"])

    def test_calls_comments_strings_and_nested_types_are_not_member_declarations(self):
        base_source = r'''namespace Demo {
          public class Base {
            private class Nested { public void Render() { } }
            public string Text = "public void Bind() { }";
            // protected void Snapshot();
            /* public void LifetimeCancellation(); */
            public void Run() { Render(); Bind(); Snapshot(); }
          }
        }'''
        child_source = r'''namespace Demo {
          public class Child : Base {
            public void RunAgain() { Bind(); Render(); }
            public string Text2 = "Snapshot LifetimeCancellation";
          }
        }'''
        base, base_map = _row("base", "Base", "Demo", "Base.cs", base_source)
        child, child_map = _row("child", "Child", "Demo", "Child.cs", child_source)
        result = _resolve([base, child], {"Base.cs": base_map, "Child.cs": child_map},
                          {"child": ["Bind", "Render", "Snapshot", "LifetimeCancellation"]})[1]
        for name, evidence in result["requiredMembers"].items():
            self.assertFalse(evidence["satisfied"], name)

    def test_unqualified_bases_resolve_only_in_same_namespace(self):
        other_source = "namespace Other { public class GuideUtil { public void Bind() { } } }"
        child_source = "namespace Demo { public class Child : GuideUtil { } }"
        other, other_map = _row("other", "GuideUtil", "Other", "Other.cs", other_source)
        child, child_map = _row("child", "Child", "Demo", "Child.cs", child_source)
        result = _resolve([other, child], {"Other.cs": other_map, "Child.cs": child_map}, {"child": ["Bind"]})[1]
        self.assertFalse(result["requiredMembers"]["Bind"]["satisfied"])
        self.assertIn("no_exact_class_record", [x["reason"] for x in result["unresolvedBases"]])

    def test_fully_qualified_base_is_exact_and_duplicate_qname_is_ambiguous(self):
        one, one_map = _row("one", "Base", "Demo", "One.cs", "namespace Demo { public class Base { public void Bind() { } } }")
        two, two_map = _row("two", "Base", "Demo", "Two.cs", "namespace Demo { public class Base { public void Render() { } } }")
        child, child_map = _row("child", "Child", "Demo", "Child.cs", "namespace Demo { public class Child : global::Demo.Base { } }")
        result = _resolve([one, two, child], {"One.cs": one_map, "Two.cs": two_map, "Child.cs": child_map},
                          {"child": ["Bind"]})[-1]
        self.assertFalse(result["requiredMembers"]["Bind"]["satisfied"])
        self.assertIn("ambiguous_base_class:Demo.Base", result["blockers"])

    def test_qualified_base_resolves_exactly_and_using_alias_does_not_override_it(self):
        base_source = "namespace Demo { public class Base { public void Bind() { } } }"
        child_source = "using Base = Other.Base; namespace Demo { public class Child : global::Demo.Base { } }"
        base, base_map = _row("base", "Base", "Demo", "Base.cs", base_source)
        child, child_map = _row("child", "Child", "Demo", "Child.cs", child_source)
        result = _resolve([child, base], {"Base.cs": base_map, "Child.cs": child_map}, {"child": ["Bind"]})[0]
        self.assertTrue(result["requiredMembers"]["Bind"]["satisfied"])

        alias_child_source = "using Base = Other.Base; namespace Demo { public class AliasChild : Base { } }"
        alias_child, alias_map = _row("alias", "AliasChild", "Demo", "Alias.cs", alias_child_source)
        alias_result = _resolve([alias_child, base], {"Alias.cs": alias_map, "Base.cs": base_map}, {"alias": ["Bind"]})[0]
        self.assertFalse(alias_result["requiredMembers"]["Bind"]["satisfied"])
        self.assertEqual(alias_result["unresolvedBases"][0]["reason"], "base_name_is_using_alias")

    def test_missing_source_hash_mismatch_cycle_depth_and_generic_boundaries(self):
        child, child_map = _row("child", "Child", "Demo", "Child.cs", "namespace Demo { public class Child : Missing { } }")
        missing = _resolve([child], {"Child.cs": child_map}, {"child": ["Bind"]})[0]
        self.assertEqual(missing["unresolvedBases"][0]["type"], "Missing")

        with self.assertRaisesRegex(InheritanceEvidenceError, "SHA-256 mismatch"):
            resolve_inherited_members([child], {"Child.cs": {**child_map, "sha256": "0" * 64}}, {"child": ["Bind"]})
        absent = _resolve([child], {}, {"child": ["Bind"]})[0]
        self.assertIn("missing_source_mapping", absent["blockers"])

        a, a_map = _row("a", "A", "Demo", "A.cs", "namespace Demo { public class A : B { } }")
        b, b_map = _row("b", "B", "Demo", "B.cs", "namespace Demo { public class B : A { } }")
        cycle = _resolve([a, b], {"A.cs": a_map, "B.cs": b_map}, {"a": ["Bind"]})[0]
        self.assertIn("inheritance_cycle", cycle["blockers"])
        depth = _resolve([a, b], {"A.cs": a_map, "B.cs": b_map}, {"a": ["Bind"]}, max_depth=1)[0]
        self.assertIn("maximum_inheritance_depth_exceeded", depth["blockers"])

        generic, generic_map = _row("generic", "GenericChild", "Demo", "Generic.cs",
                                    "namespace Demo { public class GenericChild<T> : A { } }")
        bounded = _resolve([generic, a], {"Generic.cs": generic_map, "A.cs": a_map}, {"generic": ["Bind"]})[0]
        self.assertIn("generic_class_unsupported", bounded["blockers"])
        self.assertFalse(bounded["requiredMembers"]["Bind"]["satisfied"])

        partial, partial_map = _row("partial", "PartialChild", "Demo", "Partial.cs",
                                    "namespace Demo { public partial class PartialChild : A { } }")
        partial_result = _resolve([partial, a], {"Partial.cs": partial_map, "A.cs": a_map}, {"partial": ["Bind"]})[0]
        self.assertIn("partial_class_unsupported", partial_result["blockers"])


if __name__ == "__main__":
    unittest.main()
