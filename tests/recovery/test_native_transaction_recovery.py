import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from .fixtures import fixture
from grea.recovery import native
from grea.recovery.io import encoded, sha
from grea.recovery.package import convert_package
from grea.recovery.sources.compiled import ParseError


class NativeTransactionRecoveryTests(unittest.TestCase):
    def prepare(self, root):
        config = fixture(root / "source")
        convert_package(config.parent, "unity6", root / "candidate")
        candidate = root / "candidate/UnityProject"
        editor = root / "Unity"
        editor.write_text("unity-fixture", encoding="utf-8")
        editor.chmod(0o700)
        now = datetime.now(timezone.utc)
        options = dict(candidate=candidate, editor=editor, expected_manifest=native.fingerprint(candidate / "manifest.json"),
                       budget_seconds=600, deadline_utc=native.stamp(now + timedelta(minutes=10)),
                       window_end_utc=native.stamp(now + timedelta(minutes=12)))
        return options

    def make_transaction(self, root):
        options = self.prepare(root)
        transaction = root / "old-provider-output"
        native.native_import(output=transaction, execute=False, **options)
        plan_raw = (transaction / "native-plan.json").read_bytes()
        plan = json.loads(plan_raw)
        project = transaction / "UnityProject"
        shutil.copytree(options["candidate"], project)
        project_manifest_path = project / "manifest.json"
        project_manifest = json.loads(project_manifest_path.read_text())
        progress = {"schemaVersion": 1, "processed": 1, "total": 1, "status": "completed_partial",
                    "phase": "complete", "planSha256": plan["importPlanSha256"], "elapsedSeconds": 35.25,
                    "nativeResumeSupported": False}
        progress_path = project / "Analysis/Readback/native-progress.json"
        progress_path.parent.mkdir(parents=True)
        progress_path.write_bytes(encoded(progress))
        (transaction / "import.log").write_bytes(b"Unity import completed; verifier was not persisted\n")
        (transaction / "console.log").write_bytes(b"native host output\n")
        journal = {"schemaVersion": 1, "status": "running", "processStarted": True, "processExited": False,
                   "pid": 4237, "sourceManifestSha256": plan["sourceManifestSha256"],
                   "importPlanSha256": plan["importPlanSha256"], "project": "UnityProject",
                   "startedUtc": native.stamp(datetime.now(timezone.utc))}
        journal_path = transaction / "execution-journal.json"
        journal_path.write_bytes(encoded(journal))

        entrypoint = root / "monkey"
        entrypoint.write_bytes(b"pinned-test-entrypoint")
        entrypoint_sha = native.fingerprint(entrypoint)
        run_path = root / "run.json"
        command = [str(entrypoint), "native-import", "--candidate", str(options["candidate"]),
                   "--expected-manifest", options["expected_manifest"], "--editor-path", str(options["editor"]),
                   "--out", str(transaction), "--budget-seconds", "600", "--deadline-utc", options["deadline_utc"],
                   "--window-end-utc", options["window_end_utc"], "--execute"]
        run = {"tool_id": "monkey", "status": "partial", "exit_code": 1, "capture_complete": True,
               "entrypoint_identities": [{"path": str(entrypoint), "sha256": entrypoint_sha}],
               "run_dir": str(root), "process_group": 4219, "command": command,
               "stderr": "verification raised unexpectedly", "started_at": "2026-11-04T20:05:00Z",
               "finished_at": "2026-11-04T20:05:48Z"}
        run_path.write_bytes(encoded(run))

        def pin(path):
            raw = path.read_bytes()
            return sha(raw), len(raw)

        native_plan_sha, native_plan_bytes = pin(transaction / "native-plan.json")
        identity_sha, identity_bytes = pin(transaction / "plan-identity.json")
        journal_sha, journal_bytes = pin(journal_path)
        run_sha, run_bytes = pin(run_path)
        manifest_sha, manifest_bytes = pin(project_manifest_path)
        progress_sha, progress_bytes = pin(progress_path)
        import_log_sha, import_log_bytes = pin(transaction / "import.log")
        console_log_sha, console_log_bytes = pin(transaction / "console.log")
        request = {
            "schema": "monkey-native-execution-recovery-request/1",
            "schemaVersion": 1,
            "transactionRoot": str(transaction),
            "producer": {"toolId": "monkey", "toolVersion": plan["toolVersion"],
                         "launcherSha256": plan["launcherSha256"], "entrypointPath": str(entrypoint),
                         "entrypointSha256": entrypoint_sha},
            "pins": {
                "nativePlanSha256": native_plan_sha, "nativePlanBytes": native_plan_bytes,
                "planIdentitySha256": identity_sha, "planIdentityBytes": identity_bytes,
                "executionJournalSha256": journal_sha, "executionJournalBytes": journal_bytes,
                "sourceManifestSha256": plan["sourceManifestSha256"], "importPlanSha256": plan["importPlanSha256"],
                "runReceiptPath": str(run_path), "runReceiptSha256": run_sha, "runReceiptBytes": run_bytes,
                "projectManifestSha256": manifest_sha, "projectManifestBytes": manifest_bytes,
                "nativeProgressSha256": progress_sha, "nativeProgressBytes": progress_bytes,
                "importLogSha256": import_log_sha, "importLogBytes": import_log_bytes,
                "consoleLogSha256": console_log_sha, "consoleLogBytes": console_log_bytes,
            },
        }
        request_path = root / "recovery-request.json"
        request_path.write_bytes(encoded(request))
        return options, transaction, request_path, sha(request_path.read_bytes())

    @staticmethod
    def transaction_hashes(root):
        return {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in root.rglob("*") if p.is_file()}

    def test_recovery_emits_independent_receipt_and_leaves_transaction_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            _, transaction, request_path, request_sha = self.make_transaction(root)
            before = self.transaction_hashes(transaction)
            with patch("grea.recovery.native_execution_recovery._assert_pid_and_group_absent"):
                result = native.recover_execution(request_path, request_sha, root / "recovery")
            self.assertEqual(result["status"], "partial")
            receipt_path = Path(result["receipt"])
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(receipt["process"]["outerProcessExitCode"], 1)
            self.assertIsNone(receipt["process"]["unityExitCode"])
            self.assertEqual(receipt["importer"]["progress"]["status"], "completed_partial")
            self.assertEqual(receipt["verification"]["status"], "not_completed_by_launcher")
            self.assertFalse(receipt["promotionEligible"])
            self.assertTrue(receipt["importer"]["journalLeftUntouched"])
            self.assertEqual(before, self.transaction_hashes(transaction))
            self.assertTrue((receipt_path.parent / "recovery-manifest.json").is_file())

    def test_changed_outer_run_receipt_is_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            _, transaction, request_path, request_sha = self.make_transaction(root)
            run_path = root / "run.json"
            run_path.write_bytes(run_path.read_bytes() + b" ")
            out = root / "recovery"
            with self.assertRaises(ParseError) as error, patch("grea.recovery.native_execution_recovery._assert_pid_and_group_absent"):
                native.recover_execution(request_path, request_sha, out)
            self.assertEqual(error.exception.code, "NATIVE_RECOVERY_INPUT_CHANGED")
            self.assertFalse(out.exists())
            self.assertEqual(json.loads((transaction / "execution-journal.json").read_text())["status"], "running")

    def test_request_producer_must_match_the_pinned_outer_entrypoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            _, transaction, request_path, _ = self.make_transaction(root)
            request = json.loads(request_path.read_text())
            request["producer"]["entrypointPath"] = str(root / "different-monkey")
            request_path.write_bytes(encoded(request))
            out = root / "recovery"
            with self.assertRaises(ParseError) as error, patch("grea.recovery.native_execution_recovery._assert_pid_and_group_absent"):
                native.recover_execution(request_path, sha(request_path.read_bytes()), out)
            self.assertEqual(error.exception.code, "NATIVE_RECOVERY_OUTER_PRODUCER_MISMATCH")
            self.assertFalse(out.exists())
            self.assertEqual(json.loads((transaction / "execution-journal.json").read_text())["status"], "running")

    def test_present_or_reused_pid_guard_refuses_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            _, _, request_path, request_sha = self.make_transaction(root)
            out = root / "recovery"
            with self.assertRaises(ParseError) as error, patch(
                    "grea.recovery.native_execution_recovery._assert_pid_and_group_absent",
                    side_effect=ParseError("NATIVE_RECOVERY_PROCESS_STILL_PRESENT", "process", "present")):
                native.recover_execution(request_path, request_sha, out)
            self.assertEqual(error.exception.code, "NATIVE_RECOVERY_PROCESS_STILL_PRESENT")
            self.assertFalse(out.exists())

    def assert_verifier_failure_is_finalized(self, root, exception, expected_reason, reraises=False):
        options = self.prepare(root)
        out = root / "running"
        native.native_import(output=out, execute=False, **options)
        _, _, plan_hash = native.source(options["candidate"], options["expected_manifest"])
        progress_path = root / "progress.json"
        progress_path.write_bytes(encoded({"schemaVersion": 1, "processed": 1, "total": 1,
                                           "status": "completed", "phase": "complete",
                                           "planSha256": plan_hash, "elapsedSeconds": 1.0,
                                           "nativeResumeSupported": False}))

        class Child:
            pid = 4242
            returncode = 0

            def poll(self):
                return self.returncode

        context = patch("grea.recovery.native.subprocess.Popen", return_value=Child()), \
                  patch("grea.recovery.native.find_analysis", return_value=progress_path), \
                  patch("grea.recovery.native.unity.verify", side_effect=exception)
        if reraises:
            with context[0], context[1], context[2], self.assertRaises(type(exception)):
                native.native_import(output=out, execute=True, **options)
            result = json.loads((out / "execution-result.json").read_text())
        else:
            with context[0], context[1], context[2]:
                returned = native.native_import(output=out, execute=True, **options)
            result = json.loads((out / "execution-result.json").read_text())
            self.assertEqual(returned["reason"], expected_reason)
        journal = json.loads((out / "execution-journal.json").read_text())
        self.assertEqual(result["reason"], expected_reason)
        self.assertTrue(result["processExited"])
        self.assertEqual(result["processExitCode"], 0)
        self.assertEqual(journal["journalState"], "finalized")
        self.assertTrue(journal["processExited"])
        self.assertEqual(journal["processExitCode"], 0)
        return result

    def test_native_verifier_attribute_error_finalizes_result_and_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            result = self.assert_verifier_failure_is_finalized(root, AttributeError("verification contract crashed"),
                                                               "NATIVE_VERIFICATION_EXCEPTION")
            self.assertEqual(result["error"], "AttributeError: verification contract crashed")
            self.assertEqual(result["verification"]["exceptionType"], "AttributeError")

    def test_native_verifier_runtime_error_finalizes_result_and_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            result = self.assert_verifier_failure_is_finalized(root, RuntimeError("readback failed"),
                                                               "NATIVE_VERIFICATION_EXCEPTION")
            self.assertEqual(result["verification"]["exceptionType"], "RuntimeError")

    def test_native_verifier_keyboard_interrupt_finalizes_then_reraises(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            result = self.assert_verifier_failure_is_finalized(root, KeyboardInterrupt(),
                                                               "NATIVE_HOST_INTERRUPTED", reraises=True)
            self.assertEqual(result["verification"]["status"], "interrupted")
            self.assertEqual(result["verification"]["exceptionType"], "KeyboardInterrupt")


if __name__ == "__main__":
    unittest.main()
