import hashlib
import tempfile
import unittest
from pathlib import Path

from beaver.build_filter import plan, validate_collect_spec, _snapshot
from beaver.errors import BeaverError


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fixture(project):
    assets = {
        "Assets/Game/Main.unity": ("scene-bytes", "4" * 32, 1004, "UnityEditor.SceneAsset"),
        "Assets/Game/ship.bin": ("runtime-bytes", "1" * 32, 1001, "UnityEngine.Mesh"),
        "Assets/SourceRecovery/Recovered.shader": ("source-bytes", "2" * 32, 1002, "UnityEditor.DefaultAsset"),
        "Assets/SourceRecovery/mystery.asset": ("mystery-bytes", "3" * 32, 1003, "UnityEngine.Material"),
    }
    records = []
    for path, (content, guid, local_id, type_name) in assets.items():
        target = project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        meta = target.with_name(target.name + ".meta")
        meta.write_text("guid: " + guid + "\n", encoding="utf-8")
        records.append({"path": path, "guid": guid, "localIds": [local_id], "types": [type_name]})
    packages = project / "Packages"; packages.mkdir(exist_ok=True)
    (packages / "manifest.json").write_text("{}\n", encoding="utf-8")
    settings = project / "ProjectSettings"; settings.mkdir(exist_ok=True)
    for name in ("EditorBuildSettings.asset", "GraphicsSettings.asset", "QualitySettings.asset"):
        (settings / name).write_text("fixture " + name + "\n", encoding="utf-8")
    input_state = {}
    for path, (content, _, _, _) in assets.items():
        for tracked_path in (path, path + ".meta"):
            data = (project / tracked_path).read_bytes()
            input_state[tracked_path] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    for scope in ("Packages", "ProjectSettings"):
        for item in (project / scope).rglob("*"):
            if item.is_file():
                data = item.read_bytes(); rel = item.relative_to(project).as_posix()
                input_state[rel] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    snap = {
        "schemaVersion": 1,
        "target": "StandaloneWindows64",
        "pipeline": "com.unity.render-pipelines.universal:17.0.3",
        "buildScenes": ["Assets/Game/Main.unity"],
        "explicitRoots": [],
        "implicitRoots": [],
        "coverage": {"complete": True, "blockers": []},
        "inputState": input_state,
        "assets": records,
        "dependencies": [{"path": "Assets/Game/Main.unity", "guid": "4" * 32, "localId": 1004,
                           "type": "UnityEditor.SceneAsset", "roots": ["Assets/Game/Main.unity"]},
                          {"path": "Assets/Game/ship.bin", "guid": "1" * 32, "localId": 1001,
                           "type": "UnityEngine.Mesh", "roots": ["Assets/Game/Main.unity"]}],
    }
    handoff = [{"path": "Assets/SourceRecovery/Recovered.shader", "classification": "source",
                "sourceSha256": digest("source-bytes"),
                "metaSha256": hashlib.sha256((project / "Assets/SourceRecovery/Recovered.shader.meta").read_bytes()).hexdigest(),
                "evidenceId": "monkey-evidence-shader-001"}]
    return snap, handoff


class BuildFilterTests(unittest.TestCase):
    def test_classifies_referenced_source_evidence_and_unknown(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            snapshot, handoff = fixture(root)
            result = plan(root, {"platform": snapshot["target"], "pipeline": snapshot["pipeline"]}, snapshot, handoff)
            rows = {row["path"]: row for row in result["assets"]}
            runtime = rows["Assets/Game/ship.bin"]
            scene = rows["Assets/Game/Main.unity"]
            source = rows["Assets/SourceRecovery/Recovered.shader"]
            unknown = rows["Assets/SourceRecovery/mystery.asset"]
            self.assertEqual(runtime["buildState"], "runtime-referenced")
            self.assertEqual(runtime["references"][0]["localId"], 1001)
            self.assertEqual(scene["buildState"], "runtime-referenced")
            self.assertEqual(scene["guid"], "4" * 32)
            self.assertEqual(scene["localIds"], [1004])
            self.assertEqual(source["buildState"], "source-evidence-only")
            self.assertEqual(source["sourceClassification"], "source")
            self.assertEqual(source["quarantineEligibility"], "blocked-unproven-runtime-usage")
            self.assertEqual(unknown["buildState"], "unknown")
            self.assertEqual(unknown["sourceClassification"], "unknown")
            self.assertEqual(result["execution"]["status"], "blocked")
            self.assertEqual(result["counts"]["quarantineEligible"], 0)
            self.assertEqual(source["backup"]["sourceSha256"], digest("source-bytes"))
            self.assertEqual(source["rollback"]["restoreMetaTo"], source["path"] + ".meta")

    def test_extension_or_unverified_self_report_does_not_make_source_evidence(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            snapshot, handoff = fixture(root)
            handoff[0]["sourceSha256"] = "f" * 64
            result = plan(root, {"platform": snapshot["target"], "pipeline": snapshot["pipeline"]}, snapshot, handoff)
            row = next(row for row in result["assets"] if row["path"].endswith("Recovered.shader"))
            self.assertEqual(row["buildState"], "unknown")
            self.assertIsNone(row["sourceEvidenceId"])

    def test_monkey_shader_handoff_preserves_binary_label_and_checks_target_mapping(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            snapshot, _ = fixture(root)
            binary_path = "Assets/SourceRecovery/mystery.asset"
            content = (root / binary_path).read_bytes()
            binary_handoff = {"schema": "monkey-shader-handoff/1", "items": [{
                "path": binary_path, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                "classification": "recovered-binary", "nativeCompilation": "not_run",
                "runtimeDisposition": "evidence-only", "target": {"guid": "3" * 32, "localFileID": 1003},
                "source": "unmapped", "dialect": "unknown", "platformEvidence": [],
            }]}
            result = plan(root, {"platform": snapshot["target"], "pipeline": snapshot["pipeline"]}, snapshot, binary_handoff)
            row = next(row for row in result["assets"] if row["path"] == binary_path)
            self.assertEqual(row["sourceClassification"], "binary")
            self.assertEqual(row["buildState"], "source-evidence-only")
            self.assertEqual(row["handoffClassification"], "recovered-binary")
            self.assertEqual(row["quarantineEligibility"], "blocked-unproven-runtime-usage")
            binary_handoff["items"][0]["target"]["localFileID"] = 999
            mismapped = plan(root, {"platform": snapshot["target"], "pipeline": snapshot["pipeline"]}, snapshot, binary_handoff)
            row = next(row for row in mismapped["assets"] if row["path"] == binary_path)
            self.assertEqual(row["buildState"], "unknown")

    def test_monkey_handoff_never_treats_a_compilation_claim_as_validation(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            snapshot, _ = fixture(root)
            path = "Assets/SourceRecovery/Recovered.shader"
            content = (root / path).read_bytes()
            handoff = {"schema": "monkey-shader-handoff/1", "items": [{
                "path": path, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                "classification": "source-text", "nativeCompilation": "compiled", "runtimeDisposition": "source-review",
            }]}
            with self.assertRaisesRegex(BeaverError, "BUILD_FILTER_SOURCE_EVIDENCE"):
                plan(root, {"platform": snapshot["target"], "pipeline": snapshot["pipeline"]}, snapshot, handoff)

    def test_rejects_pipeline_mismatch_and_bad_native_identity(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            snapshot, handoff = fixture(root)
            with self.assertRaisesRegex(BeaverError, "BUILD_FILTER_PIPELINE_MISMATCH"):
                plan(root, {"platform": snapshot["target"], "pipeline": "built-in"}, snapshot, handoff)
            snapshot["dependencies"][0]["guid"] = "9" * 32
            with self.assertRaisesRegex(BeaverError, "BUILD_FILTER_DEPENDENCY_IDENTITY"):
                plan(root, {"platform": snapshot["target"], "pipeline": snapshot["pipeline"]}, snapshot, handoff)

    def test_rejects_traversal_and_duplicate_dependency(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            snapshot, handoff = fixture(root)
            snapshot["assets"][0]["path"] = "Assets/../escape.bin"
            with self.assertRaisesRegex(BeaverError, "BUILD_FILTER_PATH"):
                plan(root, {"platform": snapshot["target"], "pipeline": snapshot["pipeline"]}, snapshot, handoff)
            snapshot, handoff = fixture(root)
            snapshot["dependencies"].append(dict(snapshot["dependencies"][0]))
            with self.assertRaisesRegex(BeaverError, "BUILD_FILTER_DEPENDENCY_DUPLICATE"):
                plan(root, {"platform": snapshot["target"], "pipeline": snapshot["pipeline"]}, snapshot, handoff)

    def test_incomplete_coverage_keeps_the_entire_plan_blocked(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            snapshot, handoff = fixture(root)
            snapshot["coverage"] = {"complete": False, "blockers": ["unmapped preloaded asset"]}
            result = plan(root, {"platform": snapshot["target"], "pipeline": snapshot["pipeline"]}, snapshot, handoff)
            self.assertEqual(result["execution"]["code"], "BUILD_FILTER_DEPENDENCY_COVERAGE_INCOMPLETE")
            self.assertEqual(result["execution"]["blockers"], ["unmapped preloaded asset"])

    def test_implicit_resource_inclusion_is_not_business_usage(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root=Path(directory);snapshot,handoff=fixture(root)
            snapshot['implicitRoots']=['implicit:Resources']
            snapshot['dependencies'][0]['roots']=['implicit:Resources']
            result=plan(root,{'platform':snapshot['target'],'pipeline':snapshot['pipeline']},snapshot,handoff)
            row=next(r for r in result['assets'] if r['path']==snapshot['dependencies'][0]['path'])
            self.assertEqual(row['buildState'],'implicit-build-included')
            self.assertEqual(row['quarantineEligibility'],'requires-explicit-retirement-scope')
            self.assertEqual(result['execution']['status'],'blocked')

    def test_collection_spec_is_bounded_and_native_receipt_requires_all_guards(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            snapshot, _ = fixture(root)
            spec = {"schemaVersion": 1, "platform": snapshot["target"], "renderPipeline": snapshot["pipeline"],
                    "assets": ["Assets/Game/Main.unity"], "roots": []}
            scene = root / spec["assets"][0]
            scene.parent.mkdir(parents=True, exist_ok=True)
            scene.write_text("synthetic scene", encoding="utf-8")
            self.assertIs(validate_collect_spec(root, spec), spec)
            with self.assertRaisesRegex(BeaverError, "BUILD_FILTER_NATIVE_GUARD"):
                _snapshot(snapshot, {"platform": snapshot["target"], "pipeline": snapshot["pipeline"]}, require_runner=True)

    def test_changed_assets_or_project_settings_invalidate_the_native_closure(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            snapshot, handoff = fixture(root)
            (root / "Assets/Game/ship.bin").write_text("changed after collection", encoding="utf-8")
            with self.assertRaisesRegex(BeaverError, "BUILD_FILTER_STALE_SNAPSHOT"):
                plan(root, {"platform": snapshot["target"], "pipeline": snapshot["pipeline"]}, snapshot, handoff)
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            snapshot, handoff = fixture(root)
            (root / "ProjectSettings/GraphicsSettings.asset").write_text("changed pipeline settings", encoding="utf-8")
            with self.assertRaisesRegex(BeaverError, "BUILD_FILTER_STALE_SNAPSHOT"):
                plan(root, {"platform": snapshot["target"], "pipeline": snapshot["pipeline"]}, snapshot, handoff)

    def test_new_unimported_assets_are_explicit_coverage_blockers(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            snapshot, handoff = fixture(root)
            (root / "Assets/Game/not-imported.bin").write_text("untracked", encoding="utf-8")
            result = plan(root, {"platform": snapshot["target"], "pipeline": snapshot["pipeline"]}, snapshot, handoff)
            self.assertEqual(result["execution"]["code"], "BUILD_FILTER_DEPENDENCY_COVERAGE_INCOMPLETE")
            self.assertTrue(any("not-imported.bin" in message for message in result["execution"]["blockers"]))


if __name__ == "__main__":
    unittest.main()
