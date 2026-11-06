import copy
import json
import tempfile
import unittest
from pathlib import Path

from grea.development.errors import BeaverError
from grea.development.io import sha
from grea.development.intake_assemblies import validate


TARGET_GUID = "a" * 32
CANDIDATE_GUID = "b" * 32
SCRIPT_GUID = "c" * 32
OTHER_GUID = "d" * 32
ASSEMBLY = "GameBase"
TARGET_ASMDEF = "Assets/Game/GameBase/GameBase.asmdef"
CANDIDATE_ASMDEF = "Assets/Candidate/GameBase.asmdef"
SCRIPT_SOURCE = "Assets/Candidate/DamageTipMesh.cs"
SCRIPT_TARGET = "Assets/Game/GameBase/Runtime/DamageTipMesh.cs"


def source_text(body=""):
    return f"""// Only a frozen schema carrier; comments are not declarations.
using UnityEngine;
namespace GameBase {{
    public class DamageTipMesh : UnityEngine.MonoBehaviour {{
{body}
    }}
}}
"""


class IntakeAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.incoming = self.root / "incoming"
        self.target = self.root / "target"
        (self.incoming / "Assets/Candidate").mkdir(parents=True)
        (self.target / "Assets/Game/GameBase").mkdir(parents=True)
        self.files = {}
        self.before = {}
        self.add_candidate(CANDIDATE_ASMDEF, '{"name":"GameBase","references":[]}\n')
        self.add_candidate(CANDIDATE_ASMDEF + ".meta", self.meta(CANDIDATE_GUID))
        self.add_candidate(SCRIPT_SOURCE, source_text("        public int damage;"))
        self.add_candidate(SCRIPT_SOURCE + ".meta", self.meta(SCRIPT_GUID))
        target_def_bytes = b'{"name":"GameBase","references":[],"autoReferenced":true}\n'
        self.add_target(TARGET_ASMDEF, target_def_bytes)
        target_meta = self.meta(TARGET_GUID)
        self.add_target(TARGET_ASMDEF + ".meta", target_meta)
        self.existing_guids = {TARGET_GUID: [TARGET_ASMDEF]}
        self.script = {
            "source": SCRIPT_SOURCE, "target": SCRIPT_TARGET, "guid": SCRIPT_GUID,
            "sha256": self.files[SCRIPT_SOURCE]["sha256"], "metaSha256": self.files[SCRIPT_SOURCE + ".meta"]["sha256"],
            "sourceType": "GameBase.DamageTipMesh", "sourceAssembly": ASSEMBLY,
            "targetType": "GameBase.DamageTipMesh", "targetAssembly": ASSEMBLY,
            "baseType": "UnityEngine.MonoBehaviour", "baseAssembly": "UnityEngine.CoreModule",
            "localId": 11500000,
            "fields": [{"name": "damage", "type": "System.Int32", "assembly": "System.Private.CoreLib"}],
            "reason": "Schema-only source validation fixture",
        }
        self.row = {
            "target": TARGET_ASMDEF, "guid": TARGET_GUID,
            "sha256": self.before[TARGET_ASMDEF]["sha256"],
            "metaSha256": self.before[TARGET_ASMDEF + ".meta"]["sha256"], "name": ASSEMBLY,
        }
        self.spec = {
            "schemaVersion": 5,
            "retainedAssemblies": [self.row],
            "newScripts": [self.script],
            "omittedCompilerInputs": [{"path": CANDIDATE_ASMDEF, "reason": "Compiler boundary kept explicit",
                                       "coveredByExternalScript": SCRIPT_SOURCE}],
            "additions": [],
        }

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def meta(guid):
        return f"fileFormatVersion: 2\nguid: {guid}\n".encode()

    def add_candidate(self, path, content):
        raw = content.encode("utf-8") if isinstance(content, str) else content
        file = self.incoming / path
        file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(raw)
        self.files[path] = {"path": path, "sha256": sha(raw), "bytes": len(raw)}

    def add_target(self, path, content):
        raw = content.encode("utf-8") if isinstance(content, str) else content
        file = self.target / path
        file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(raw)
        self.before[path] = {"path": path, "sha256": sha(raw), "bytes": len(raw)}

    def refresh_script_pin(self, text):
        self.add_candidate(SCRIPT_SOURCE, text)
        self.script["sha256"] = self.files[SCRIPT_SOURCE]["sha256"]

    def validate(self):
        return validate(self.spec, self.incoming, self.files, self.target, self.before, self.existing_guids)

    def assert_family(self, prefix, fn=None):
        with self.assertRaises(BeaverError) as caught:
            (fn or self.validate)()
        self.assertTrue(caught.exception.code.startswith(prefix), caught.exception.code)

    def test_valid_retained_scope_and_empty_schema_only_class_return_original_rows(self):
        original = self.spec["retainedAssemblies"]
        result = self.validate()
        self.assertIs(result, original)
        self.assertEqual(result[0]["guid"], TARGET_GUID)
        self.assertNotEqual(CANDIDATE_GUID, TARGET_GUID)

    def test_empty_damage_tip_class_and_comment_markers_are_accepted(self):
        self.refresh_script_pin(source_text("        // public void fakeMethod() { }\n        /* public int fakeField; */"))
        self.script["fields"] = []
        self.validate()

    def test_candidate_asmdef_requires_exact_omission_and_source_coverage(self):
        self.spec["omittedCompilerInputs"] = []
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")
        self.spec["omittedCompilerInputs"] = [{"path": CANDIDATE_ASMDEF, "reason": "omitted", "coveredByExternalScript": "Assets/Candidate/Other.cs"}]
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")
        self.spec["omittedCompilerInputs"] = [{"path": CANDIDATE_ASMDEF, "reason": "omitted", "coveredByExternalScript": SCRIPT_SOURCE}]
        self.assertIs(self.validate(), self.spec["retainedAssemblies"])

    def test_candidate_asmdef_guid_can_differ_but_asmdef_cannot_be_an_addition(self):
        self.assertNotEqual(CANDIDATE_GUID, TARGET_GUID)
        self.validate()
        self.spec["additions"] = [{"source": CANDIDATE_ASMDEF, "target": "Assets/Game/Candidate.asmdef"}]
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")

    def test_candidate_asmref_and_multiple_scopes_are_refused(self):
        self.add_candidate("Assets/Candidate/Scripts/Hook.asmref", '{"reference":"' + CANDIDATE_GUID + '"}')
        self.refresh_script_pin(source_text().replace("Assets/Candidate", "Assets/Candidate"))
        # Put the source under the asmref's scope.
        old_source = self.files.pop(SCRIPT_SOURCE)
        old_meta = self.files.pop(SCRIPT_SOURCE + ".meta")
        (self.incoming / SCRIPT_SOURCE).unlink(); (self.incoming / (SCRIPT_SOURCE + ".meta")).unlink()
        nested = "Assets/Candidate/Scripts/DamageTipMesh.cs"
        self.add_candidate(nested, source_text())
        self.add_candidate(nested + ".meta", self.meta(SCRIPT_GUID))
        self.script.update(source=nested, sha256=self.files[nested]["sha256"], metaSha256=self.files[nested + ".meta"]["sha256"], fields=[])
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")

        # Two candidate asmdefs in one source scope are ambiguous even if names differ.
        self.spec["omittedCompilerInputs"] = [{"path": CANDIDATE_ASMDEF, "reason": "omitted", "coveredByExternalScript": nested}]
        self.add_candidate("Assets/Candidate/Scripts/Other.asmdef", '{"name":"Other"}')
        self.add_candidate("Assets/Candidate/Scripts/Other.asmdef.meta", self.meta(OTHER_GUID))
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")

    def test_retained_target_pin_guid_name_and_target_before_are_exact(self):
        self.row["sha256"] = "f" * 64
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")
        self.row["sha256"] = self.before[TARGET_ASMDEF]["sha256"]
        self.row["guid"] = OTHER_GUID
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")
        self.row["guid"] = TARGET_GUID
        self.row["name"] = "Other"
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")
        self.row["name"] = ASSEMBLY
        self.before.pop(TARGET_ASMDEF)
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")

    def test_target_asmdef_names_are_unique_casefolded_across_assets(self):
        other = "Assets/Other/gamebase.asmdef"
        self.add_target(other, '{"name":"GAMEBASE"}')
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")

    def test_target_asmref_nearer_scope_and_same_directory_ambiguity_are_refused(self):
        asmref = "Assets/Game/GameBase/Runtime/Local.asmref"
        self.add_target(asmref, '{"reference":"' + TARGET_GUID + '"}')
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")
        self.before.pop(asmref); (self.target / asmref).unlink()
        nearer = "Assets/Game/GameBase/Runtime/Local.asmdef"
        self.add_target(nearer, '{"name":"Local"}')
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")
        self.before.pop(nearer); (self.target / nearer).unlink()
        same_dir = "Assets/Game/GameBase/Other.asmdef"
        self.add_target(same_dir, '{"name":"Other"}')
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")

    def test_retained_assembly_must_be_used_and_target_assembly_must_match(self):
        self.spec["newScripts"] = []
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")
        self.spec["newScripts"] = [dict(self.script, targetAssembly="Other")]
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")

    def test_default_assembly_csharp_still_rejects_existing_target_scopes(self):
        self.spec["newScripts"] = [dict(self.script, targetAssembly="Assembly-CSharp")]
        self.spec["retainedAssemblies"] = []
        self.assert_family("INTAKE_RETAINED_ASSEMBLY_")

    def test_default_assembly_csharp_is_allowed_without_target_scope(self):
        self.spec["newScripts"] = [dict(self.script, target="Assets/Default/Runtime/DamageTipMesh.cs", targetAssembly="Assembly-CSharp")]
        self.spec["retainedAssemblies"] = []
        self.assertEqual(self.validate(), [])

    def test_candidate_source_and_meta_are_checked_against_exact_pins(self):
        source_file = self.incoming / SCRIPT_SOURCE
        source_file.write_text(source_text("        public int changed;"), encoding="utf-8")
        self.assert_family("INTAKE_NEW_SCRIPT_SCHEMA")
        self.add_candidate(SCRIPT_SOURCE, source_text("        public int damage;"))
        self.script["sha256"] = self.files[SCRIPT_SOURCE]["sha256"]
        self.add_candidate(SCRIPT_SOURCE + ".meta", self.meta(OTHER_GUID))
        self.script["metaSha256"] = self.files[SCRIPT_SOURCE + ".meta"]["sha256"]
        self.assert_family("INTAKE_NEW_SCRIPT_SCHEMA")

    def test_schema_source_field_types_match_exact_order_and_canonical_system_names(self):
        self.script["fields"] = [
            {"name": "damage", "type": "System.Int32", "assembly": "System.Private.CoreLib"},
            {"name": "items", "type": "System.String[]", "assembly": "System.Private.CoreLib"},
        ]
        self.refresh_script_pin(source_text("        public int damage;\n        public string[] items;"))
        self.validate()
        self.script["fields"][0]["name"] = "health"
        self.assert_family("INTAKE_NEW_SCRIPT_SCHEMA")
        self.script["fields"][0]["name"] = "damage"
        self.script["fields"][0]["type"] = "System.Single"
        self.assert_family("INTAKE_NEW_SCRIPT_SCHEMA")

    def test_source_methods_constructors_properties_initializers_attributes_and_extra_types_refuse(self):
        rejected = (
            "public void Tick() {}",
            "public DamageTipMesh() {}",
            "public int damage = 5;",
            "public int Damage { get; set; }",
            "[System.Serializable] public class DamageTipMesh : UnityEngine.MonoBehaviour {}",
            "public class Other : UnityEngine.MonoBehaviour {}",
            "public int damage; } public class Extra {}",
        )
        for body in rejected:
            with self.subTest(body=body):
                self.refresh_script_pin(source_text(body))
                self.assert_family("INTAKE_NEW_SCRIPT_SCHEMA")

    def test_source_strings_and_preprocessor_directives_cannot_fake_allowed_declarations(self):
        self.refresh_script_pin(source_text('        public string note = "// public int damage;";'))
        self.assert_family("INTAKE_NEW_SCRIPT_SCHEMA")
        self.refresh_script_pin("#if DEBUG\n" + source_text() + "#endif\n")
        self.assert_family("INTAKE_NEW_SCRIPT_SCHEMA")
        self.refresh_script_pin(source_text().replace("using UnityEngine;", "using Alias = UnityEngine;"))
        self.assert_family("INTAKE_NEW_SCRIPT_SCHEMA")

    def test_multiple_scripts_may_share_one_candidate_asmdef_and_one_exact_omission(self):
        second_source = "Assets/Candidate/OtherThing.cs"
        code = source_text().replace("DamageTipMesh", "OtherThing").replace("GameBase.OtherThing", "GameBase.OtherThing")
        self.add_candidate(second_source, code)
        self.add_candidate(second_source + ".meta", self.meta("e" * 32))
        second = dict(self.script, source=second_source, target="Assets/Game/GameBase/Runtime/OtherThing.cs",
                      guid="e" * 32, sha256=self.files[second_source]["sha256"], metaSha256=self.files[second_source + ".meta"]["sha256"],
                      sourceType="GameBase.OtherThing", targetType="GameBase.OtherThing", fields=[])
        self.spec["newScripts"].append(second)
        # One omission for this source asmdef may be covered by one script from its shared domain.
        self.assertIs(self.validate(), self.spec["retainedAssemblies"])


if __name__ == "__main__":
    unittest.main()
