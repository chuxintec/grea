import copy
import json
from pathlib import Path
import unittest

from beaver.errors import BeaverError
from beaver.intake_contract import validate_spec


HASH = "a" * 64
GUID = "b" * 32


def spec():
    return {
        "schemaVersion": 1,
        "operation": "additive-intake",
        "candidateManifestSha256": HASH,
        "additions": [{"source": "Assets/Candidate/Panel.prefab", "target": "Assets/Game/Panel.prefab"}],
        "externalScripts": [],
        "omittedCompilerInputs": [],
        "verifications": [{"asset": "Assets/Candidate/Panel.prefab", "objects": [{
            "localId": 123, "type": "Panel", "assembly": "Game", "name": "Panel",
            "fields": [{"propertyPath": "m_Enabled", "kind": "boolean", "value": True}],
        }]}],
        "protectedAssets": [],
        "evidence": [],
    }


def spec_v2():
    value = spec()
    value["schemaVersion"] = 2
    value["externalAssets"] = []
    value["packageScripts"] = []
    return value


def external_script(**changes):
    item = {
        "source": "Assets/Candidate/Widget.cs", "sourceGuid": GUID,
        "sourceType": "Widget", "sourceAssembly": "Game",
        "target": "Assets/Game/Widget.cs", "targetGuid": GUID,
        "targetType": "Widget", "targetAssembly": "Game.Runtime",
        "targetLocalId": -42, "targetSha256": HASH, "targetMetaSha256": "c" * 64,
        "reason": "Existing source required by serialized prefab reference",
    }
    item.update(changes)
    return item


def external_asset(**changes):
    item = {
        "source": "Assets/Candidate/Shared.asset", "target": "Assets/Game/Shared.asset",
        "guid": "d" * 32, "sha256": HASH, "metaSha256": "c" * 64,
        "objects": [{"localId": 321, "type": "SharedData", "assembly": "Game", "name": "Shared", "fields": []}],
        "reason": "Retained package-independent asset identity referenced by the candidate",
    }
    item.update(changes)
    return item


def package_script(**changes):
    item = {
        "target": "Packages/com.unity.ugui/Runtime/UI/Graphic.cs",
        "guid": "e" * 32, "type": "UnityEngine.UI.Graphic", "assembly": "UnityEngine.UI",
        "localId": 11500000, "name": "Graphic", "packageName": "com.unity.ugui",
        "packageVersion": "1.0.0-pre.2+build.7", "packageSource": "registry",
        "packageJsonSha256": HASH, "sha256": "f" * 64, "metaSha256": "c" * 64,
        "reason": "Existing uGUI package script identity required by retained references",
    }
    item.update(changes)
    return item


class AdditiveIntakeContractTests(unittest.TestCase):
    def assert_invalid(self, value, code_part=None):
        with self.assertRaises(BeaverError) as caught:
            validate_spec(value)
        self.assertTrue(caught.exception.code.startswith("INTAKE_SPEC_"), caught.exception.code)
        if code_part:
            self.assertIn(code_part, caught.exception.code)

    def test_minimal_contract_round_trips_same_dictionary(self):
        value = spec()
        self.assertIs(validate_spec(value), value)

    def test_allowlisted_asset_types_and_structured_external_reuse_are_accepted(self):
        value = spec()
        value["additions"] = [
            {"source": f"Assets/Candidate/A{i}{ext}", "target": f"Assets/Game/A{i}{ext}"}
            for i, ext in enumerate((".prefab", ".asset", ".mat", ".png", ".ttf", ".otf", ".shader", ".txt", ".json"))
        ]
        value["verifications"] = [{"asset": "Assets/Candidate/A0.prefab", "objects": [{
            "localId": -(1 << 63), "type": "Transform", "assembly": "Game", "name": "",
            "fields": [
                {"propertyPath": "number", "kind": "integer", "value": (1 << 63) - 1},
                {"propertyPath": "decimal", "kind": "float", "value": 1},
                {"propertyPath": "label", "kind": "string", "value": ""},
                {"propertyPath": "ref", "kind": "object", "value": {"guid": "", "localId": 0, "type": "", "assembly": ""}},
            ],
        }]}]
        value["externalScripts"] = [external_script()]
        value["omittedCompilerInputs"] = [{"path": "Assets/Candidate/EditorOnly.asmdef", "reason": "Candidate-only editor assembly", "coveredByExternalScript": "Assets/Candidate/Widget.cs"}]
        value["protectedAssets"] = [{"path": "Assets/Game/Existing.asset", "sha256": HASH, "metaSha256": "d" * 64}]
        value["evidence"] = [{"path": "/tmp/evidence/intake.json", "sha256": HASH}]
        self.assertIs(validate_spec(value), value)

    def test_bounded_upper_edges_are_accepted(self):
        value = spec()
        value["additions"] = [{"source": f"Assets/Candidate/P{i}.prefab", "target": f"Assets/Game/P{i}.prefab"} for i in range(256)]
        value["verifications"] = [{"asset": "Assets/Candidate/P0.prefab", "objects": [
            {"localId": i + 1, "type": "Thing", "assembly": "Game", "name": "", "fields": []}
            for i in range(4096)
        ]}]
        self.assertIs(validate_spec(value), value)

    def test_closed_objects_and_exact_top_level_fields(self):
        value = spec(); value["surprise"] = 1
        self.assert_invalid(value, "FIELDS")
        value = spec(); value["additions"][0]["extra"] = False
        self.assert_invalid(value, "FIELDS")
        value = spec(); value["verifications"][0]["objects"][0]["fields"][0]["rawCode"] = "x"
        self.assert_invalid(value, "FIELDS")

    def test_boolean_is_never_accepted_as_integer_and_integer_bounds_are_enforced(self):
        for bad in (True, 1 << 63, -(1 << 63) - 1):
            value = spec(); value["verifications"][0]["objects"][0]["localId"] = bad
            self.assert_invalid(value, "INTEGER")
        value = spec(); value["verifications"][0]["objects"][0]["fields"][0] = {"propertyPath": "n", "kind": "integer", "value": False}
        self.assert_invalid(value, "INTEGER")
        value = spec(); value["verifications"][0]["objects"][0]["localId"] = 0
        self.assert_invalid(value, "INTEGER")

    def test_paths_reject_traversal_aliases_windows_names_meta_and_forbidden_imports(self):
        for path in ("Assets/../Other/A.png", "Assets/./A.png", "Assets\\A.png", "Assets/C:/A.png",
                     "Assets/CON.prefab", "Assets/Game/Foo. ", "Assets/Game/Foo.prefab.meta",
                     "Assets/Game/Bad?.png", "Packages/A.png", "Assets/Game/A.cs", "Assets/Game/A.asmdef",
                     "Assets/Game/A.dll", "Assets/Game/A.unity"):
            value = spec(); value["additions"][0]["source"] = path
            self.assert_invalid(value)
        value = spec(); value["additions"][0]["source"] = "Assets/Candidate/Cafe\u0301.prefab"
        self.assert_invalid(value, "PATH")

    def test_casefold_aliases_and_duplicate_sources_targets_are_rejected(self):
        value = spec(); value["additions"].append({"source": "Assets/candidate/panel.PREFAB", "target": "Assets/Game/Other.prefab"})
        self.assert_invalid(value, "DUPLICATE")
        value = spec(); value["additions"].append({"source": "Assets/Candidate/Other.prefab", "target": "Assets/Game/PANEL.PREFAB"})
        self.assert_invalid(value, "DUPLICATE")
        value = spec(); value["verifications"].append(copy.deepcopy(value["verifications"][0]))
        self.assert_invalid(value, "DUPLICATE")

    def test_source_and_target_extensions_must_match(self):
        value = spec(); value["additions"][0]["target"] = "Assets/Game/Panel.asset"
        self.assert_invalid(value, "EXTENSION")

    def test_external_script_identity_and_no_overlap_rules(self):
        for change in ({"targetGuid": "e" * 32}, {"targetType": "Other"}, {"source": "Assets/Candidate/Panel.prefab"},
                       {"sourceAssembly": "Game.dll"}, {"targetAssembly": "Plugins/Game.dll"}, {"targetLocalId": True},
                       {"targetLocalId": 0}, {"targetGuid": "B" * 32}):
            value = spec(); value["externalScripts"] = [external_script(**change)]
            self.assert_invalid(value)
        value = spec(); value["externalScripts"] = [external_script(), external_script(source="Assets/Candidate/Other.cs", target="Assets/Game/Other.cs")]
        self.assert_invalid(value, "DUPLICATE")

    def test_omitted_compiler_inputs_must_be_declared_and_disjoint(self):
        item = {"path": "Assets/Candidate/OnlyEditor.rsp", "reason": "No runtime compiler settings", "coveredByExternalScript": "Assets/Candidate/Widget.cs"}
        value = spec(); value["externalScripts"] = [external_script()]; value["omittedCompilerInputs"] = [item]
        self.assertIs(validate_spec(value), value)
        value = spec(); value["externalScripts"] = [external_script()]
        value["omittedCompilerInputs"] = [{**item, "path": "Assets/Candidate/Widget.cs"}]
        self.assert_invalid(value, "OVERLAP")
        value = spec(); value["externalScripts"] = [external_script()]
        value["omittedCompilerInputs"] = [{**item, "path": "Assets/Candidate/Code.txt"}]
        self.assert_invalid(value, "EXTENSION")
        value = spec(); value["omittedCompilerInputs"] = [item]
        self.assert_invalid(value, "REFERENCE")

    def test_verification_requires_prefab_source_bounded_objects_unique_ids_fields(self):
        for bad in ("Assets/Game/Panel.prefab", "Assets/Candidate/Other.prefab"):
            value = spec(); value["verifications"][0]["asset"] = bad
            self.assert_invalid(value, "REFERENCE")
        value = spec(); value["verifications"][0]["asset"] = "Assets/Candidate/Panel.asset"
        self.assert_invalid(value)
        value = spec(); value["verifications"][0]["objects"].append(copy.deepcopy(value["verifications"][0]["objects"][0]))
        self.assert_invalid(value, "DUPLICATE")
        value = spec(); value["verifications"][0]["objects"] = []
        self.assert_invalid(value, "BOUNDS")
        value = spec(); value["verifications"][0]["objects"][0]["fields"] = [
            {"propertyPath": "same", "kind": "string", "value": "a"}, {"propertyPath": "same", "kind": "string", "value": "b"}]
        self.assert_invalid(value, "DUPLICATE")

    def test_field_enums_values_and_object_references_are_strict(self):
        for kind, bad in (("int", 1), ("integer", 1.0), ("float", True), ("float", float("nan")),
                          ("float", float("inf")), ("boolean", 1), ("string", "x" * 16385)):
            value = spec(); value["verifications"][0]["objects"][0]["fields"][0] = {"propertyPath": "x", "kind": kind, "value": bad}
            self.assert_invalid(value)
        for ref in ({"guid": "", "localId": 0, "type": "X", "assembly": "Game"},
                    {"guid": GUID, "localId": 0, "type": "X", "assembly": "Game"},
                    {"guid": GUID, "localId": 1, "type": "X", "assembly": "Game.dll"},
                    {"guid": GUID, "localId": True, "type": "X", "assembly": "Game"}):
            value = spec(); value["verifications"][0]["objects"][0]["fields"][0] = {"propertyPath": "ref", "kind": "object", "value": ref}
            self.assert_invalid(value)

    def test_protected_paths_hashes_and_evidence_are_checked_without_file_reads(self):
        value = spec(); value["protectedAssets"] = [{"path": "Assets/Game/Panel.prefab", "sha256": HASH, "metaSha256": HASH}]
        self.assert_invalid(value, "OVERLAP")
        value = spec(); value["protectedAssets"] = [{"path": "Assets/Game/Old.asset", "sha256": "A" * 64, "metaSha256": HASH}]
        self.assert_invalid(value, "HASH")
        value = spec(); value["evidence"] = [{"path": "relative/evidence.json", "sha256": HASH}]
        self.assert_invalid(value, "PATH")
        value = spec(); value["evidence"] = [{"path": "/tmp/evidence/../secret", "sha256": HASH}]
        self.assert_invalid(value, "PATH")
        value = spec(); value["evidence"] = [{"path": "/tmp//evidence.json", "sha256": HASH}]
        self.assert_invalid(value, "PATH")
        value = spec(); value["evidence"] = [{"path": "/missing/but-not-read.json", "sha256": HASH}]
        self.assertIs(validate_spec(value), value)

    def test_total_field_budget_is_enforced_before_field_validation(self):
        value = spec()
        item = {"propertyPath": "x", "kind": "string", "value": ""}
        value["verifications"][0]["objects"][0]["fields"] = [item] * 250001
        self.assert_invalid(value, "BOUNDS")

    def test_top_level_version_and_operation_are_exact(self):
        for key, bad in (("schemaVersion", True), ("schemaVersion", 1.0), ("schemaVersion", 2), ("operation", "replace")):
            value = spec(); value[key] = bad
            self.assert_invalid(value)

    def test_v1_remains_closed_and_unmodified_while_v2_requires_both_new_arrays(self):
        original = spec()
        self.assertIs(validate_spec(original), original)
        version_one_extra = spec(); version_one_extra["externalAssets"] = []
        self.assert_invalid(version_one_extra, "FIELDS")
        for missing in ("externalAssets", "packageScripts"):
            value = spec_v2(); del value[missing]
            self.assert_invalid(value, "FIELDS")
        value = spec_v2(); value["unexpected"] = None
        self.assert_invalid(value, "FIELDS")
        value = spec_v2()
        self.assertIs(validate_spec(value), value)

    def test_v2_accepts_external_asset_object_observations_and_package_script_identity(self):
        value = spec_v2()
        asset = external_asset(objects=[
            {"localId": -5, "type": "SharedData", "assembly": "Game", "name": "", "fields": [
                {"propertyPath": "active", "kind": "boolean", "value": True},
                {"propertyPath": "ref", "kind": "object", "value": {"guid": "", "localId": 0, "type": "", "assembly": ""}},
            ]},
            {"localId": 6, "type": "Secondary", "assembly": "Game", "name": "Secondary", "fields": []},
        ])
        value["externalAssets"] = [asset]
        value["packageScripts"] = [package_script()]
        self.assertIs(validate_spec(value), value)

    def test_v2_external_asset_paths_extensions_ids_and_cross_table_guids_are_guarded(self):
        for bad in (
            {"target": "Assets/Game/Shared.prefab"},
            {"source": "Assets/Candidate/Script.cs"},
            {"guid": "D" * 32},
            {"sha256": "A" * 64},
            {"objects": []},
        ):
            value = spec_v2(); value["externalAssets"] = [external_asset(**bad)]
            self.assert_invalid(value)
        value = spec_v2(); value["externalAssets"] = [external_asset(objects=[
            {"localId": 1, "type": "A", "assembly": "Game", "name": "", "fields": []},
            {"localId": 1, "type": "B", "assembly": "Game", "name": "", "fields": []},
        ])]
        self.assert_invalid(value, "DUPLICATE")
        value = spec_v2(); value["externalAssets"] = [external_asset(), external_asset(source="Assets/Candidate/Other.asset")]
        self.assert_invalid(value, "DUPLICATE")
        value = spec_v2(); value["externalAssets"] = [external_asset(target="Assets/Game/Panel.prefab")]
        self.assert_invalid(value)
        value = spec_v2(); value["externalAssets"] = [external_asset()]
        value["additions"] = [{"source": "Assets/Candidate/Incoming.asset", "target": "Assets/Game/Shared.asset"}]
        value["verifications"] = []
        self.assert_invalid(value, "OVERLAP")
        value = spec_v2(); value["externalScripts"] = [external_script()]
        value["externalAssets"] = [external_asset(guid=GUID)]
        self.assert_invalid(value, "OVERLAP")

    def test_v2_external_asset_combined_object_and_field_budgets_apply_with_verifications(self):
        value = spec_v2()
        def owners(start, count):
            return [{"localId": i, "type": "X", "assembly": "Game", "name": "", "fields": []}
                    for i in range(start, start + count)]
        value["externalAssets"] = [external_asset(objects=owners(1, 2048)),
                                    external_asset(source="Assets/Candidate/Other.asset", target="Assets/Game/Other.asset", guid="9" * 32, objects=owners(1, 2049))]
        self.assert_invalid(value, "BOUNDS")
        value = spec_v2()
        fields = [{"propertyPath": "x", "kind": "string", "value": ""}] * 250000
        owner = {"localId": 1, "type": "X", "assembly": "Game", "name": "", "fields": []}
        value["externalAssets"] = [external_asset(objects=[{**owner, "fields": fields}])]
        self.assert_invalid(value, "BOUNDS")

    def test_v2_external_asset_and_package_script_array_limits(self):
        value = spec_v2(); value["externalAssets"] = [{}] * 257
        self.assert_invalid(value, "BOUNDS")
        value = spec_v2(); value["packageScripts"] = [{}] * 65
        self.assert_invalid(value, "BOUNDS")
        value = spec_v2(); value["externalAssets"] = [external_asset(guid="7" * 32), external_asset(source="Assets/Candidate/Other.asset", target="Assets/Game/Other.asset", guid="7" * 32)]
        self.assert_invalid(value, "DUPLICATE")

    def test_v2_external_asset_guid_cannot_collide_with_external_script_guid(self):
        # The extension allowlists make a literal .cs path collision impossible,
        # but the cross-table guard remains explicit for future-safe closure.
        value = spec_v2(); value["externalScripts"] = [external_script()]
        value["externalAssets"] = [external_asset(guid=GUID)]
        self.assert_invalid(value, "OVERLAP")

    def test_v2_package_script_scope_semver_and_identity_collisions_are_strict(self):
        value = spec_v2(); value["packageScripts"] = [package_script()]
        self.assertIs(validate_spec(value), value)
        for bad in (
            {"target": "Packages/com.unity.ugui/Editor/Graphic.cs"},
            {"target": "Packages/com.unity.textmeshpro/Runtime/Graphic.cs"},
            {"type": "UnityEngine.EventSystems.EventSystem"},
            {"assembly": "UnityEngine.UI.dll"},
            {"packageName": "com.unity.textmeshpro"},
            {"packageVersion": "file:../com.unity.ugui"},
            {"packageVersion": "01.0.0"},
            {"packageSource": "local"},
            {"localId": True},
            {"guid": "F" * 32},
        ):
            value = spec_v2(); value["packageScripts"] = [package_script(**bad)]
            self.assert_invalid(value)
        value = spec_v2(); value["externalAssets"] = [external_asset(guid="8" * 32)]
        value["packageScripts"] = [package_script(guid="8" * 32)]
        self.assert_invalid(value, "OVERLAP")
        value = spec_v2(); value["externalScripts"] = [external_script()]
        value["packageScripts"] = [package_script(guid=GUID)]
        self.assert_invalid(value, "OVERLAP")
        value = spec_v2(); value["packageScripts"] = [package_script(), package_script(target="Packages/com.unity.ugui/Runtime/UI/Image.cs")]
        self.assert_invalid(value, "DUPLICATE")

    def test_schema2_is_closed_and_describes_reused_owner_and_package_fields(self):
        path = Path(__file__).resolve().parents[1] / "docs/schemas/additive-intake-2.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["schemaVersion"], {"const": 2})
        self.assertIs(schema["additionalProperties"], False)
        self.assertIn("externalAssets", schema["required"])
        self.assertIn("packageScripts", schema["required"])
        self.assertIs(schema["$defs"]["externalAsset"]["additionalProperties"], False)
        self.assertIs(schema["$defs"]["packageScript"]["additionalProperties"], False)
        self.assertEqual(len(schema["$defs"]["field"]["oneOf"]), 5)
        self.assertIn("maxItems", schema["properties"]["packageScripts"])
        self.assertEqual(schema["properties"]["packageScripts"]["maxItems"], 64)
        self.assertEqual(schema["properties"]["externalAssets"]["maxItems"], 256)

    def test_schema2_validation_examples_when_optional_jsonschema_is_available(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("optional jsonschema package is not installed")
        path = Path(__file__).resolve().parents[1] / "docs/schemas/additive-intake-2.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        valid = spec_v2(); valid["externalAssets"] = [external_asset()]; valid["packageScripts"] = [package_script()]
        self.assertTrue(validator.is_valid(valid))
        for invalid in (
            {**valid, "unexpected": 1},
            {**valid, "externalAssets": [{**external_asset(), "extra": 1}]},
            {**valid, "packageScripts": [{**package_script(), "packageVersion": "../package"}]},
        ):
            self.assertFalse(validator.is_valid(invalid))

    def test_published_schema_is_loadable_closed_and_describes_typed_field_union(self):
        path = Path(__file__).resolve().parents[1] / "docs/schemas/additive-intake-1.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(set(schema["required"]), {
            "schemaVersion", "operation", "candidateManifestSha256", "additions", "externalScripts",
            "omittedCompilerInputs", "verifications", "protectedAssets", "evidence",
        })
        self.assertEqual(len(schema["$defs"]["field"]["oneOf"]), 5)
        for branch in schema["$defs"]["field"]["oneOf"]:
            self.assertIs(branch["additionalProperties"], False)
            self.assertEqual(set(branch["required"]), {"propertyPath", "kind", "value"})

    def test_published_schema_accepts_and_rejects_examples_when_jsonschema_is_installed(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("optional jsonschema package is not installed")
        path = Path(__file__).resolve().parents[1] / "docs/schemas/additive-intake-1.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        valid = spec()
        self.assertTrue(validator.is_valid(valid))
        valid["externalScripts"] = [external_script()]
        valid["verifications"][0]["objects"][0]["fields"].extend([
            {"propertyPath": "number", "kind": "integer", "value": (1 << 63) - 1},
            {"propertyPath": "decimal", "kind": "float", "value": 1.25},
            {"propertyPath": "text", "kind": "string", "value": ""},
            {"propertyPath": "reference", "kind": "object", "value": {"guid": "", "localId": 0, "type": "", "assembly": ""}},
        ])
        self.assertTrue(validator.is_valid(valid))
        for invalid in (
            dict(valid, surprise=True),
            {**valid, "additions": [{"source": "Assets/A.txt", "target": "Assets/B.txt", "extra": 1}]},
            {**valid, "verifications": [{"asset": "Assets/A.prefab", "objects": [{
                "localId": True, "type": "T", "assembly": "A", "name": "", "fields": []
            }]}]},
            {**valid, "verifications": [{"asset": "Assets/A.prefab", "objects": [{
                "localId": 1, "type": "T", "assembly": "A", "name": "", "fields": [
                    {"propertyPath": "n", "kind": "integer", "value": False}
                ]
            }]}]},
        ):
            self.assertFalse(validator.is_valid(invalid))


if __name__ == "__main__":
    unittest.main()
