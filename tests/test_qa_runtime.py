import json
import os
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beaver.errors import BeaverError
from beaver.io import write_json
from beaver.output_limits import digest_file
from beaver.qa_runtime import prepare, launch, collect, failure_receipt, _guard_root, _hash_tree
from beaver import payload, qa_runtime


class QaRuntimePrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.mock_home = self.root / "mock-home"
        self.source = self.root / "source"
        self.seed = self.root / "seed.json"
        self.config = self.root / "private" / "config.json"
        self.seed.write_text('{"seed":1}\n', encoding="utf-8")
        self.config.parent.mkdir(); self.config.write_text('{"private":true}\n', encoding="utf-8")
        self.bundle = self.source / "player" / "Fixture.app"
        macos = self.bundle / "Contents" / "MacOS"; macos.mkdir(parents=True)
        exe = macos / "Fixture"; exe.write_bytes(b"fixture executable; never launched by tests\n"); exe.chmod(0o751)
        info = self.bundle / "Contents" / "Info.plist"
        info.write_bytes(plistlib.dumps({"CFBundleExecutable": "Fixture", "CFBundleIdentifier": "test.fixture"}))
        resource = self.bundle / "Contents" / "Resources"; resource.mkdir()
        (resource / "settings.json").write_text('{"setting":true}\n', encoding="utf-8")
        self.manifest = self.source / "artifact-manifest.json"

    def tearDown(self): self.temp.cleanup()

    def make_spec(self, build="build-a", profile="profile-a", bad_binding=False, bad_link=False, bad_env=False, bad_args=False, documents_credential=False, with_seed=False, bundle_id=None, test_mode="normal", artifact_policy=None, large_bundle=False):
        if bundle_id:
            (self.bundle / "Contents" / "Info.plist").write_bytes(plistlib.dumps({"CFBundleExecutable": "Fixture", "CFBundleIdentifier": bundle_id}))
        if large_bundle:
            (self.bundle / "Contents" / "MacOS" / "Fixture").write_bytes(b"E" * 4096)
            (self.bundle / "Contents" / "Resources" / "large.assets").write_bytes(b"R" * 8192)
        if bad_link:
            (self.bundle / "Contents" / "Resources" / "external").symlink_to(self.root / "outside", target_is_directory=True)
        files = []
        for parent, dirs, names in os.walk(self.source / "player", followlinks=False):
            for name in dirs + names:
                p = Path(parent) / name
                rel = p.relative_to(self.source).as_posix()
                if p.is_symlink(): files.append({"path": rel, "symlink": os.readlink(p)})
                elif p.is_file(): files.append({"path": rel, "sha256": digest_file(p), "bytes": p.stat().st_size})
        manifest_doc = {"schemaVersion": 1, "sourceSha256": "a" * 64, "files": files}
        if artifact_policy is not None: manifest_doc["artifactPolicy"] = artifact_policy
        write_json(self.manifest, manifest_doc)
        seed_spec = None
        if with_seed:
            seed_root = self.root / "seed-tree"; seed_file = seed_root / "saves" / "slot.json"; seed_file.parent.mkdir(parents=True, exist_ok=True)
            seed_file.write_text('{"slot":1}\n', encoding="utf-8")
            seed_manifest = self.root / "seed-manifest.json"
            write_json(seed_manifest, {"schemaVersion": 1, "files": [{"path": "saves/slot.json", "sha256": digest_file(seed_file), "bytes": seed_file.stat().st_size}]})
            seed_spec = {"root": str(seed_root), "manifest": str(seed_manifest), "manifestSha256": digest_file(seed_manifest)}
        if documents_credential:
            self.config.write_text(json.dumps({"credentialFile": str(Path.home() / "Documents" / "credential.json")}), encoding="utf-8")
        doc = {
            "schemaVersion": 1, "contract": "beaver-unity-qa/1", "projectId": "fixture-project", "buildId": build,
            "artifactManifest": str(self.manifest), "artifactManifestSha256": digest_file(self.manifest), "profileId": profile,
            "profileSeed": seed_spec,
            "configInputs": {"private-settings": {"path": str(self.config), "sha256": digest_file(self.config)}},
            "environmentBindings": {"FIXTURE_CONFIG": {"kind": "config", "id": "private-settings"}, "FIXTURE_PROFILE": {"kind": "profile", "id": "root"}},
            "testMode": test_mode, "arguments": ["-screen-fullscreen", "0", "-screen-width", "960"],
        }
        if bad_binding:
            doc["environmentBindings"]["FIXTURE_CONFIG"] = {"kind": "config", "id": "private-settings", "path": str(self.root / "Documents" / "secret.json")}
        if bad_env: doc["environmentBindings"]["HOME"] = {"kind": "profile", "id": "root"}
        if bad_args: doc["arguments"] = ["-batchmode"]
        if documents_credential: doc["configInputs"]["private-settings"]["sha256"] = digest_file(self.config)
        spec = self.root / (build + ".spec.json"); write_json(spec, doc)
        return spec, digest_file(spec)

    def call_prepare(self, spec):
        spec_path, expected = spec
        with patch("beaver.qa_runtime._home_root", return_value=self.mock_home / "Library/Application Support/beaver/unity-qa"), patch("beaver.qa_runtime._signature", return_value={"status": "unsigned"}):
            return prepare(spec_path, expected)

    def test_copies_bundle_preserving_modes_internal_links_and_input_hash_reports(self):
        (self.bundle / "Contents" / "Resources" / "alias").symlink_to("settings.json")
        spec = self.make_spec()
        result = self.call_prepare(spec)
        app = self.mock_home / "Library/Application Support/beaver/unity-qa/fixture-project/builds/build-a/App.app"
        self.assertEqual((app / "Contents/MacOS/Fixture").stat().st_mode & 0o777, 0o751)
        self.assertTrue((app / "Contents/Resources/alias").is_symlink())
        self.assertEqual(os.readlink(app / "Contents/Resources/alias"), "settings.json")
        report = json.loads(Path(result["report"]).read_text())
        self.assertEqual(report["sourceVerificationBefore"]["manifestSha256"], report["sourceVerificationAfter"]["manifestSha256"])
        self.assertEqual(report["configInputs"]["private-settings"]["sourceBeforeSha256"], report["configInputs"]["private-settings"]["sourceAfterSha256"])
        self.assertIn("project/data/configs/build-a/private-settings.json", report["configInputs"]["private-settings"]["path"])
        self.assertFalse((app / "config").exists())

    def test_seed_applied_once_and_same_profile_survives_new_build(self):
        first = self.call_prepare(self.make_spec("build-a"))
        profile = Path(first["profileRoot"])
        seeded = profile / "runtime-progress.json"
        seeded.write_text('{"runtime-progress":9}\n', encoding="utf-8")
        second = self.call_prepare(self.make_spec("build-b"))
        self.assertEqual(Path(second["profileRoot"]), profile)
        self.assertEqual(seeded.read_text(), '{"runtime-progress":9}\n')
        report = json.loads(Path(second["report"]).read_text())
        self.assertFalse(report["profileSeed"].get("seedApplied", True))

    def test_external_symlink_and_documents_path_binding_are_rejected(self):
        spec = self.make_spec(bad_link=True)
        with self.assertRaises(BeaverError): self.call_prepare(spec)
        spec = self.make_spec("build-b", bad_binding=True)
        with self.assertRaises(BeaverError): self.call_prepare(spec)

    def test_unknown_project_root_is_rejected(self):
        location = self.mock_home / "Library/Application Support/beaver/unity-qa/fixture-project"
        location.mkdir(parents=True); (location / "someone-elses-data").write_text("keep")
        with patch("beaver.qa_runtime._home_root", return_value=self.mock_home / "Library/Application Support/beaver/unity-qa"), patch("beaver.qa_runtime._signature", return_value={"status": "unsigned"}):
            with self.assertRaises(BeaverError) as error: prepare(*self.make_spec())
        self.assertEqual(error.exception.code, "QA_UNKNOWN_OWNERSHIP")
        self.assertTrue((location / "someone-elses-data").exists())

    def test_full_seed_preserves_relative_files_and_untrusted_bindings_reject(self):
        first = self.call_prepare(self.make_spec("seed-a", with_seed=True))
        seeded_file = Path(first["profileRoot"]) / "saves/slot.json"
        self.assertEqual(json.loads(seeded_file.read_text()), {"slot": 1})
        seeded_file.write_text('{"runtime":true}\n')
        self.call_prepare(self.make_spec("seed-b", with_seed=True))
        self.assertEqual(seeded_file.read_text(), '{"runtime":true}\n')
        for suffix, flags in (("env", {"bad_env": True}), ("args", {"bad_args": True}), ("credential", {"documents_credential": True})):
            with self.assertRaises(BeaverError): self.call_prepare(self.make_spec("reject-" + suffix, **flags))

    def test_source_drift_rolls_back_stages_and_exposes_persistent_failure_receipt(self):
        spec = self.make_spec("drift-build")
        original_copy = __import__("beaver.qa_runtime", fromlist=["_copy_app"])._copy_app
        def copy_then_change(*args):
            original_copy(*args)
            (self.bundle / "Contents/MacOS/Fixture").write_bytes(b"changed after snapshot")
        with patch("beaver.qa_runtime._home_root", return_value=self.mock_home / "Library/Application Support/beaver/unity-qa"), patch("beaver.qa_runtime._signature", return_value={"status": "unsigned"}), patch("beaver.qa_runtime._copy_app", side_effect=copy_then_change):
            with self.assertRaises(BeaverError) as raised: prepare(*spec)
        receipt_path = failure_receipt(raised.exception)
        self.assertTrue(receipt_path and Path(receipt_path).is_file())
        failure = json.loads(Path(receipt_path).read_text())
        self.assertEqual(failure["status"], "failed-recovery-required")
        self.assertTrue(failure["retainedPaths"])
        self.assertTrue(all(Path(path).exists() for path in failure["retainedPaths"]))
        project = self.mock_home / "Library/Application Support/beaver/unity-qa/fixture-project"
        self.assertFalse((project / "data/profiles/profile-a").exists())
        self.assertFalse((project / "builds/drift-build").exists())
        self.assertFalse((project / "data/configs/drift-build").exists())

    def test_project_owner_is_bound_to_bundle_identifier(self):
        self.call_prepare(self.make_spec("product-a"))
        changed = self.make_spec("product-b", bundle_id="com.other.fixture")
        with patch("beaver.qa_runtime._home_root", return_value=self.mock_home / "Library/Application Support/beaver/unity-qa"), patch("beaver.qa_runtime._signature", return_value={"status": "unsigned"}):
            with self.assertRaises(BeaverError) as error: prepare(*changed)
        self.assertEqual(error.exception.code, "QA_OWNER_DRIFT")

    def test_large_bundle_uses_only_validated_build2_file_budget_through_copy_hash_and_executable(self):
        with patch.object(qa_runtime, "FILE_BYTES", 1024), patch.object(payload, "FILE_BYTES", 1024):
            with self.assertRaises(BeaverError): self.call_prepare(self.make_spec("large-default", large_bundle=True))
            spec = self.make_spec("large-build2", artifact_policy="beaver-unity-build/2", large_bundle=True)
            original_hash_tree = qa_runtime._hash_tree
            with patch.object(qa_runtime, "_hash_tree", wraps=original_hash_tree) as hash_tree:
                result = self.call_prepare(spec)
            app_calls = [call for call in hash_tree.call_args_list if str(call.args[0]).endswith("App.app")]
            self.assertTrue(app_calls)
            self.assertEqual(app_calls[-1].kwargs["max_file_bytes"], qa_runtime.BUILD_FILE_BYTES)
            self.assertEqual(result["owner"]["artifactPolicy"], "beaver-unity-build/2")
            self.assertEqual(result["owner"]["artifactMaxFileBytes"], qa_runtime.BUILD_FILE_BYTES)
            self.assertEqual(result["owner"]["artifactMaxTotalBytes"], qa_runtime.WHOLE_BYTES)
            self.assertEqual(result["owner"]["artifactMaxFiles"], qa_runtime.WHOLE_FILES)
            fake = unittest.mock.MagicMock(); fake.pid = 54321; fake.wait.return_value = 0
            with patch("beaver.qa_runtime._home_root", return_value=self.mock_home / "Library/Application Support/beaver/unity-qa"), patch("beaver.qa_runtime.subprocess.Popen", return_value=fake):
                launched = launch("fixture-project", "large-build2", "profile-a", result["ownerSha256"], run_id="large-run")
            self.assertEqual(launched["report"]["executableSha256"], digest_file(Path(launched["report"]["executablePath"]), max_bytes=qa_runtime.BUILD_FILE_BYTES))

    def test_bundle_hash_enforces_whole_artifact_byte_and_file_limits(self):
        tree = self.root / "budget-tree"; tree.mkdir()
        (tree / "a").write_bytes(b"123456")
        (tree / "b").write_bytes(b"abcdef")
        with self.assertRaises(BeaverError): _hash_tree(tree, max_file_bytes=8, max_total_bytes=10, max_files=10)
        with self.assertRaises(BeaverError): _hash_tree(tree, max_file_bytes=8, max_total_bytes=20, max_files=1)

    def test_mocked_gui_launch_and_collect_are_run_scoped_and_do_not_spawn_fixture(self):
        result = self.call_prepare(self.make_spec("launch-build"))
        fake = unittest.mock.MagicMock(); fake.pid = 43210; fake.wait.return_value = 0
        with patch("beaver.qa_runtime._home_root", return_value=self.mock_home / "Library/Application Support/beaver/unity-qa"), patch("beaver.qa_runtime.subprocess.Popen", return_value=fake) as popen:
            launched = launch("fixture-project", "launch-build", "profile-a", result["ownerSha256"], run_id="run-a")
            args, kwargs = popen.call_args
            self.assertEqual(args[0][0].endswith("/Fixture"), True)
            self.assertNotIn("-batchmode", args[0])
            self.assertEqual(kwargs["env"]["HOME"], str(Path.home()))
            self.assertNotIn("FOODSTREET_QA_SAVE_PATH", kwargs["env"])
        self.assertEqual(launched["status"], "exited")
        other_log = Path(launched["logPath"]).parent / "unrelated.log"; other_log.write_text("ignore")
        with patch("beaver.qa_runtime._home_root", return_value=self.mock_home / "Library/Application Support/beaver/unity-qa"):
            report = collect("fixture-project", "launch-build", "profile-a", result["ownerSha256"], "run-a")
        self.assertEqual(report["status"], "collected")
        self.assertEqual(len(report["logs"]), 2)
        self.assertEqual(report["logs"][0]["path"], launched["logPath"])
        process_report = launched["report"]
        self.assertEqual(process_report["expectedOwnerSha256"], result["ownerSha256"])
        self.assertEqual(process_report["executableSha256"], digest_file(Path(process_report["executablePath"])))
        self.assertTrue(process_report["cwd"].endswith("App.app"))
        self.assertIn("FIXTURE_PROFILE", process_report["cleanEnvironment"])
        self.assertNotIn("FOODSTREET_QA_SAVE_PATH", process_report["cleanEnvironment"])
        process_path = Path(launched["processRecord"])
        process_record = json.loads(process_path.read_text())
        process_record["logPath"] = str(other_log)
        write_json(process_path, process_record)
        with patch("beaver.qa_runtime._home_root", return_value=self.mock_home / "Library/Application Support/beaver/unity-qa"):
            with self.assertRaises(BeaverError) as error: collect("fixture-project", "launch-build", "profile-a", result["ownerSha256"], "run-a")
        self.assertEqual(error.exception.code, "QA_RUN_LOG")

    def test_dangling_symlinks_and_final_lock_or_sandbox_links_are_rejected_without_touching_targets(self):
        dangling = self.root / "dangling"
        dangling.symlink_to(self.root / "missing-target")
        with self.assertRaises(BeaverError): _guard_root(dangling)
        result = self.call_prepare(self.make_spec("lock-build"))
        base = self.mock_home / "Library/Application Support/beaver/unity-qa/fixture-project/data"
        sentinel = self.root / "sentinel"; sentinel.write_text("preserve")
        lock = base / "locks/profile-a.lock"; lock.parent.mkdir(parents=True, exist_ok=True); lock.symlink_to(sentinel)
        with patch("beaver.qa_runtime._home_root", return_value=self.mock_home / "Library/Application Support/beaver/unity-qa"), patch("beaver.qa_runtime.subprocess.Popen") as popen:
            with self.assertRaises(BeaverError): launch("fixture-project", "lock-build", "profile-a", result["ownerSha256"], run_id="lock-run")
        popen.assert_not_called(); self.assertEqual(sentinel.read_text(), "preserve")
        run_path = base / "runs/receipt-run.json"; run_path.parent.mkdir(parents=True, exist_ok=True); run_path.symlink_to(sentinel)
        with patch("beaver.qa_runtime._home_root", return_value=self.mock_home / "Library/Application Support/beaver/unity-qa"), patch("beaver.qa_runtime.subprocess.Popen") as popen:
            with self.assertRaises(BeaverError): launch("fixture-project", "lock-build", "profile-a", result["ownerSha256"], run_id="receipt-run")
        popen.assert_not_called(); self.assertEqual(sentinel.read_text(), "preserve")
        result = self.call_prepare(self.make_spec("sandbox-build", test_mode="denyDocuments"))
        sandbox = base / "receipts/deny-documents-sandbox-run.sb"
        sandbox.symlink_to(sentinel)
        with patch("beaver.qa_runtime._home_root", return_value=self.mock_home / "Library/Application Support/beaver/unity-qa"), patch("beaver.qa_runtime.subprocess.Popen") as popen:
            with self.assertRaises(BeaverError): launch("fixture-project", "sandbox-build", "profile-a", result["ownerSha256"], run_id="sandbox-run")
        popen.assert_not_called(); self.assertEqual(sentinel.read_text(), "preserve")

    def test_launch_refuses_missing_external_profile_owner(self):
        result = self.call_prepare(self.make_spec("owner-build"))
        root = self.mock_home / "Library/Application Support/beaver/unity-qa/fixture-project"
        (root / "data/profile-owners/profile-a.json").unlink()
        with patch("beaver.qa_runtime._home_root", return_value=self.mock_home / "Library/Application Support/beaver/unity-qa"), patch("beaver.qa_runtime.subprocess.Popen") as popen:
            with self.assertRaises(BeaverError): launch("fixture-project", "owner-build", "profile-a", result["ownerSha256"])
        popen.assert_not_called()

    def test_seed_changed_after_inventory_is_rejected_before_promotion(self):
        import beaver.qa_runtime as runtime
        spec=self.make_spec('seed-drift',with_seed=True);original=runtime.stream_identity
        def change_during_copy(stream,path,**kwargs):
            if path=='saves/slot.json':(self.root/'seed-tree/saves/slot.json').write_text('{"slot":9}\n')
            return original(stream,path,**kwargs)
        with patch('beaver.qa_runtime.stream_identity',side_effect=change_during_copy):
            with self.assertRaises(BeaverError) as raised:self.call_prepare(spec)
        self.assertEqual(raised.exception.code,'QA_PROFILE_SEED_DRIFT')
        self.assertFalse((self.mock_home/'Library/Application Support/beaver/unity-qa/fixture-project/data/profiles/profile-a').exists())
