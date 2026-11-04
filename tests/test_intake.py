"""Pure-Python additive intake plan guards; no Unity Editor is launched here."""

import tempfile
import unittest
from pathlib import Path

from beaver.errors import BeaverError
from beaver.intake import build_plan, checked_plan, preview, recheck
from beaver.io import load, read, sha, write_json
from helpers import finish


ASSET_GUID = "1" * 32
SCRIPT_GUID = "2" * 32
OTHER_GUID = "3" * 32


def _write_asset(root, path, data, guid):
    asset = root / path
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(data)
    Path(str(asset) + ".meta").write_text("fileFormatVersion: 2\nguid: " + guid + "\n", encoding="utf-8")


def _project(root, assets=()):
    (root / "Assets").mkdir(parents=True)
    (root / "ProjectSettings").mkdir()
    (root / "ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: 6000.6.2f1\n", encoding="utf-8")
    (root / "Packages").mkdir()
    write_json(root / "Packages/manifest.json", {"dependencies": {}})
    for path, data, guid in assets:
        _write_asset(root, path, data, guid)
    return root


def _candidate(root, assets=None):
    root.mkdir()
    (root / "Assets").mkdir()
    (root / "ProjectSettings").mkdir()
    (root / "ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: 6000.6.2f1\n", encoding="utf-8")
    (root / "Packages").mkdir()
    write_json(root / "Packages/manifest.json", {"dependencies": {}})
    selected = assets or [("Assets/Candidate/Panel.txt", b"plain text payload\n", ASSET_GUID)]
    for path, data, guid in selected:
        _write_asset(root, path, data, guid)
    finish(root, dict(schemaVersion=1, targetProfile="unity-6000.6.2f1-ugui", namespace="test-game",
                      projectLayout="monkey-project/2.0.0", scopeMode="whole-input", diagnostics=[]))
    return root


def _spec(candidate, additions=None, *, external=None, omitted=None, verifications=None, protected=None, evidence=None):
    return {
        "schemaVersion": 1,
        "operation": "additive-intake",
        "candidateManifestSha256": sha((candidate / "manifest.json").read_bytes()),
        "additions": additions or [{"source": "Assets/Candidate/Panel.txt", "target": "Assets/Game/Panel.txt"}],
        "externalScripts": external or [],
        "omittedCompilerInputs": omitted or [],
        "verifications": verifications or [],
        "protectedAssets": protected or [],
        "evidence": evidence or [],
    }


def _write_spec(path, doc):
    write_json(path, doc)
    return path


def _script_row(candidate, target):
    candidate_script = candidate / "Assets/Candidate/Widget.cs"
    target_script = target / "Assets/Game/Widget.cs"
    return {
        "source": "Assets/Candidate/Widget.cs", "sourceGuid": SCRIPT_GUID,
        "sourceType": "Widget", "sourceAssembly": "Game",
        "target": "Assets/Game/Widget.cs", "targetGuid": SCRIPT_GUID,
        "targetType": "Widget", "targetAssembly": "Game",
        "targetLocalId": 11500000, "targetSha256": sha(target_script.read_bytes()),
        "targetMetaSha256": sha(Path(str(target_script) + ".meta").read_bytes()),
        "reason": "Existing serialized script reference",
    }


class AdditiveIntakePlanTests(unittest.TestCase):
    def setup_roots(self, root, *, candidate_assets=None, target_assets=()):
        candidate = _candidate(root / "candidate", candidate_assets)
        target = _project(root / "target", target_assets)
        spec_path = root / "intake-spec.json"
        _write_spec(spec_path, _spec(candidate))
        return candidate, target, spec_path

    def assert_code(self, code, function, *args):
        with self.assertRaises(BeaverError) as caught:
            function(*args)
        self.assertEqual(caught.exception.code, code)

    def test_text_asset_preview_is_a_declarative_plan_and_does_not_claim_native_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); candidate, target, spec_path = self.setup_roots(root)
            result = preview(candidate, target, spec_path, root / "plan")
            plan = load(read(Path(result["report"])))
            self.assertEqual(result["status"], "planned")
            self.assertEqual(plan["native"], "not_run")
            self.assertEqual(plan["visual"], "not_run")
            self.assertEqual(plan["business"], "not_run")
            self.assertEqual(plan["additions"][0]["file"]["sha256"], sha(b"plain text payload\n"))

    def test_synthetic_prefab_can_form_a_plan_but_still_has_no_native_asset_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            candidate = _candidate(root / "candidate", [("Assets/Candidate/Panel.prefab", b"synthetic fixture\n", ASSET_GUID)])
            target = _project(root / "target")
            spec_path = root / "intake-spec.json"
            doc = _spec(candidate, additions=[{"source": "Assets/Candidate/Panel.prefab", "target": "Assets/Game/Panel.prefab"}],
                        verifications=[{"asset": "Assets/Candidate/Panel.prefab", "objects": [{
                            "localId": 42, "type": "SyntheticFixture", "assembly": "Tests", "name": "Root", "fields": []
                        }]}])
            _write_spec(spec_path, doc)
            plan = build_plan(candidate, target, spec_path)
            self.assertEqual(plan["native"], "not_run")
            self.assertEqual(plan["spec"]["verifications"][0]["objects"][0]["type"], "SyntheticFixture")

    def test_existing_target_guid_cannot_be_reimported_as_a_new_asset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            candidate = _candidate(root / "candidate")
            target = _project(root / "target", [("Assets/Game/Old.txt", b"old", ASSET_GUID)])
            spec_path = _write_spec(root / "spec.json", _spec(candidate))
            self.assert_code("INTAKE_GUID_OCCUPIED", build_plan, candidate, target, spec_path)

    def test_duplicate_resources_key_is_rejected_even_at_a_different_destination_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            candidate = _candidate(root / "candidate", [("Assets/Candidate/Logo.png", b"image bytes", ASSET_GUID)])
            target = _project(root / "target", [("Assets/Resources/Icons/Logo.asset", b"existing", OTHER_GUID)])
            doc = _spec(candidate, additions=[{"source": "Assets/Candidate/Logo.png", "target": "Assets/Game/Resources/Icons/Logo.png"}])
            spec_path = _write_spec(root / "spec.json", doc)
            self.assert_code("INTAKE_RESOURCE_KEY", build_plan, candidate, target, spec_path)

    def test_candidate_source_and_target_changes_after_preview_fail_recheck(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); candidate, target, spec_path = self.setup_roots(root)
            plan = build_plan(candidate, target, spec_path)
            (candidate / "Assets/Candidate/Panel.txt").write_bytes(b"changed after manifest\n")
            self.assert_code("CANDIDATE_DRIFT", recheck, plan)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); candidate, target, spec_path = self.setup_roots(root)
            plan = build_plan(candidate, target, spec_path)
            _write_asset(target, "Assets/Manual/Note.txt", b"new target file", OTHER_GUID)
            self.assert_code("INTAKE_PRECONDITION_DRIFT", recheck, plan)

    def test_checked_plan_rejects_tampered_payload_and_expected_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); candidate, target, spec_path = self.setup_roots(root)
            result = preview(candidate, target, spec_path, root / "plan")
            self.assertEqual(checked_plan(result["report"], result["planSha256"])["contract"], "beaver-additive-intake/1")
            plan_path = Path(result["report"])
            plan = load(read(plan_path)); plan["native"] = "verified"; write_json(plan_path, plan)
            self.assert_code("INTAKE_PLAN_CHANGED", checked_plan, plan_path, result["planSha256"])
            self.assert_code("INTAKE_PLAN_CHANGED", checked_plan, plan_path, "0" * 64)

    def test_candidate_compiler_input_cannot_be_silently_omitted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            candidate = _candidate(root / "candidate", [
                ("Assets/Candidate/Panel.txt", b"plain text payload\n", ASSET_GUID),
                ("Assets/Candidate/Unlisted.cs", b"class Unlisted {}\n", OTHER_GUID),
            ])
            target = _project(root / "target")
            spec_path = _write_spec(root / "spec.json", _spec(candidate))
            self.assert_code("INTAKE_COMPILER_COVERAGE", build_plan, candidate, target, spec_path)

    def test_external_script_is_explicit_and_target_byte_drift_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            candidate = _candidate(root / "candidate", [
                ("Assets/Candidate/Panel.txt", b"plain text payload\n", ASSET_GUID),
                ("Assets/Candidate/Widget.cs", b"public class Widget {}\n", SCRIPT_GUID),
            ])
            target = _project(root / "target", [("Assets/Game/Widget.cs", b"public class Widget {}\n", SCRIPT_GUID)])
            doc = _spec(candidate, external=[_script_row(candidate, target)])
            spec_path = _write_spec(root / "spec.json", doc)
            plan = build_plan(candidate, target, spec_path)
            target_script = target / "Assets/Game/Widget.cs"
            target_script.write_bytes(b"public class Widget { public int Changed; }\n")
            self.assert_code("INTAKE_SCRIPT_DRIFT", build_plan, candidate, target, spec_path)
            self.assert_code("INTAKE_SCRIPT_DRIFT", recheck, plan)

    def test_external_script_candidate_guid_must_match_declared_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            candidate = _candidate(root / "candidate", [
                ("Assets/Candidate/Panel.txt", b"plain text payload\n", ASSET_GUID),
                ("Assets/Candidate/Widget.cs", b"public class Widget {}\n", SCRIPT_GUID),
            ])
            target = _project(root / "target", [("Assets/Game/Widget.cs", b"public class Widget {}\n", SCRIPT_GUID)])
            row = _script_row(candidate, target); row["sourceGuid"] = OTHER_GUID; row["targetGuid"] = OTHER_GUID
            spec_path = _write_spec(root / "spec.json", _spec(candidate, external=[row]))
            self.assert_code("INTAKE_SCRIPT_SOURCE", build_plan, candidate, target, spec_path)

    def test_every_added_prefab_needs_owner_expectations_before_plan_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            candidate = _candidate(root / "candidate", [("Assets/Candidate/Panel.prefab", b"synthetic fixture\n", ASSET_GUID)])
            target = _project(root / "target")
            doc = _spec(candidate, additions=[{"source": "Assets/Candidate/Panel.prefab", "target": "Assets/Game/Panel.prefab"}])
            spec_path = _write_spec(root / "spec.json", doc)
            self.assert_code("INTAKE_PREFAB_EXPECTATIONS", build_plan, candidate, target, spec_path)

    def test_unknown_guid_reference_in_added_text_asset_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            candidate = _candidate(root / "candidate", [("Assets/Candidate/Panel.txt", b"guid: " + b"f" * 32 + b"\n", ASSET_GUID)])
            target = _project(root / "target")
            spec_path = _write_spec(root / "spec.json", _spec(candidate))
            self.assert_code("INTAKE_DEPENDENCY_CLOSURE", build_plan, candidate, target, spec_path)

    def test_external_omitted_compiler_input_must_exist_and_be_the_only_declared_gap(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            candidate = _candidate(root / "candidate", [
                ("Assets/Candidate/Panel.txt", b"plain text payload\n", ASSET_GUID),
                ("Assets/Candidate/Widget.cs", b"public class Widget {}\n", SCRIPT_GUID),
                ("Assets/Candidate/EditorOnly.asmdef", b"{}", OTHER_GUID),
            ])
            target = _project(root / "target", [("Assets/Game/Widget.cs", b"public class Widget {}\n", SCRIPT_GUID)])
            external = [_script_row(candidate, target)]
            omission = [{"path": "Assets/Candidate/EditorOnly.asmdef", "reason": "Candidate editor-only assembly", "coveredByExternalScript": "Assets/Candidate/Widget.cs"}]
            spec_path = _write_spec(root / "spec.json", _spec(candidate, external=external, omitted=omission))
            plan = build_plan(candidate, target, spec_path)
            self.assertEqual(len(plan["externalScripts"]), 1)
            self.assertEqual(len(plan["spec"]["omittedCompilerInputs"]), 1)
            omission[0]["path"] = "Assets/Candidate/Missing.asmdef"
            _write_spec(spec_path, _spec(candidate, external=external, omitted=omission))
            self.assert_code("INTAKE_COMPILER_OMISSION", build_plan, candidate, target, spec_path)

    def test_protected_asset_and_evidence_pins_are_rechecked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            candidate = _candidate(root / "candidate")
            target = _project(root / "target", [("Assets/Game/Keep.asset", b"keep", OTHER_GUID)])
            keep = target / "Assets/Game/Keep.asset"
            evidence = root / "evidence.json"; evidence.write_bytes(b"reviewed\n")
            doc = _spec(candidate, protected=[{"path": "Assets/Game/Keep.asset", "sha256": sha(keep.read_bytes()),
                                               "metaSha256": sha(Path(str(keep)+".meta").read_bytes())}],
                        evidence=[{"path": str(evidence), "sha256": sha(evidence.read_bytes())}])
            spec_path = _write_spec(root / "spec.json", doc)
            plan = build_plan(candidate, target, spec_path)
            evidence.write_bytes(b"changed\n")
            self.assert_code("INTAKE_INPUT_DRIFT", recheck, plan)


if __name__ == "__main__":
    unittest.main()
