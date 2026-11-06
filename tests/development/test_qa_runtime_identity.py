import copy
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from . import test_qa_runtime as fixtures
from grea.development.errors import BeaverError
from grea.development.io import write_json
from grea.development.output_limits import digest_file
from grea.development.qa_runtime import collect


class QaRuntimeLiveIdentityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.QaRuntimePrepareTests()
        self.fixture.setUp()
        prepared = self.fixture.call_prepare(self.fixture.make_spec("identity-build"))
        self.owner_hash = prepared["ownerSha256"]
        self.owner = prepared["owner"]
        self.profile_root = Path(prepared["profileRoot"])
        self.app = Path(prepared["bundle"]["path"])
        self.project_root = self.app.parent.parent.parent
        self.build_root = self.app.parent
        self.exe = self.app / "Contents" / "MacOS" / "Fixture"
        self.mock_home = self.fixture.mock_home / "Library/Application Support/beaver/unity-qa"
        self.home_patch = patch("grea.development.qa_runtime._home_root", return_value=self.mock_home)
        self.home_patch.start()
        self.run_id = "running-a"
        self.process_path = self.project_root / "data" / "runs" / (self.run_id + ".json")
        self.log_path = self.project_root / "data" / "logs" / "profile-a" / (self.run_id + ".log")
        self.console_path = self.log_path.with_name(self.run_id + ".console.log")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_bytes(b"")
        self.console_path.write_bytes(b"")
        self.record = self.make_record(self.run_id)
        self.write_record()

    def tearDown(self):
        self.home_patch.stop()
        self.fixture.tearDown()

    def make_record(self, run_id, origin=None):
        log = self.project_root / "data" / "logs" / "profile-a" / (run_id + ".log")
        console = log.with_name(run_id + ".console.log")
        env = {
            "HOME": str(Path.home()),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "FIXTURE_CONFIG": self.owner["configInputs"]["private-settings"]["path"],
            "FIXTURE_PROFILE": str(self.profile_root),
        }
        if origin is None:
            origin = dict(status="verified", pid=43210, uniqueId="43210:100:7", startTime=[100, 7], parentPid=123)
        return dict(
            schemaVersion=1, contract="beaver-unity-qa-process/1", runId=run_id,
            projectId="fixture-project", buildId="identity-build", profileId="profile-a",
            expectedOwnerSha256=self.owner_hash, executablePath=str(self.exe),
            executableSha256=digest_file(self.exe), command=[str(self.exe), *self.owner["arguments"], "-logFile", str(log)],
            cwd=str(self.app), cleanEnvironment=env, startedUtc="2026-01-01T00:00:00+00:00",
            budgetSeconds=60, logPath=str(log), consoleLogPath=str(console), mode="normal",
            documentsSandbox={}, pid=43210, owned=True, instanceOrigin=origin, status="running",
        )

    def write_record(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists(): self.log_path.write_bytes(b"")
        if not self.console_path.exists(): self.console_path.write_bytes(b"")
        self.process_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(self.process_path, self.record)

    def collect(self, out_name):
        return collect("fixture-project", "identity-build", "profile-a", self.owner_hash,
                       self.run_id, self.fixture.root / out_name)

    def test_verified_new_origin_uses_strong_owned_resolver(self):
        strong = dict(status="process-verified", pid=43210, uniqueId="43210:100:7")
        with patch("grea.development.qa_binding._resolve", return_value=strong) as resolve, \
                patch("grea.development.qa_runtime._verify_running_process") as legacy:
            report = self.collect("collect-strong")
        resolve.assert_called_once_with("fixture-project", "identity-build", "profile-a", self.owner_hash, self.run_id)
        legacy.assert_not_called()
        self.assertEqual(report["status"], "observed_running")
        self.assertEqual(report["process"]["presence"], "verified-running")
        # Keep the schema-1 process receipt compatible: it contains the existing
        # closed launch environment, not an inherited/raw host environment dump.
        self.assertEqual(report["process"]["cleanEnvironment"], self.record["cleanEnvironment"])

    def test_unknown_or_legacy_origin_cannot_be_upgraded_by_ps_fallback(self):
        for label, origin in (("unknown", dict(status="unknown")), ("legacy", None)):
            with self.subTest(label=label):
                self.run_id = "running-" + label
                self.process_path = self.project_root / "data" / "runs" / (self.run_id + ".json")
                self.log_path = self.project_root / "data" / "logs" / "profile-a" / (self.run_id + ".log")
                self.console_path = self.log_path.with_name(self.run_id + ".console.log")
                self.record = self.make_record(self.run_id, origin)
                if origin is None:
                    self.record.pop("instanceOrigin")
                self.write_record()
                with patch("grea.development.qa_binding._resolve") as strong, \
                        patch("grea.development.qa_runtime._verify_running_process", return_value="verified-running") as legacy:
                    report = self.collect("collect-" + label)
                strong.assert_not_called()
                legacy.assert_not_called()
                self.assertEqual(report["status"], "recovery_required")
                self.assertEqual(report["process"]["presence"], "identity_unknown")

    def test_strong_resolver_failure_stays_identity_unknown(self):
        with patch("grea.development.qa_binding._resolve", side_effect=BeaverError("QA_BIND_PROCESS_CHANGED", "run", "changed")), \
                patch("grea.development.qa_runtime._verify_running_process", return_value="verified-running") as legacy:
            report = self.collect("collect-changed")
        legacy.assert_not_called()
        self.assertEqual(report["status"], "recovery_required")
        self.assertEqual(report["process"]["presence"], "identity_unknown")


if __name__ == "__main__":
    unittest.main()
