import json
import os
import shutil
import socketserver
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from grea.development import qa_virtual_pointer as vp
from grea.development.errors import BeaverError
from grea.development.io import encoded, sha, write_json
from grea.development.output_limits import digest_file

READONLY_REQUEST_KEYS = {"schemaVersion", "contract", "backend", "channelId", "token", "operation", "sequence"}


class MockPointerServer:
    def __init__(self, responder):
        self.requests = []
        outer = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                line = self.rfile.readline(vp.MAX_JSON + 1)
                request = json.loads(line)
                outer.requests.append(request)
                reply = responder(request, len(outer.requests))
                if reply is not None:
                    self.wfile.write((json.dumps(reply, separators=(",", ":")) + "\n").encode())
                    self.wfile.flush()

        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.server_thread.start()
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)

    @property
    def port(self):
        return self.server.server_address[1]


class VirtualPointerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.home())
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.fake_app = self.root.parent / ("vp-fixture-app-" + uuid.uuid4().hex)
        self.fake_app.mkdir()
        self.home_patcher = patch.object(Path, "home", return_value=self.home)
        self.home_patcher.start()
        self.ids = dict(project="project-a", build="build-a", profile="profile-a", run="run-a", owner="a" * 64)
        self.instance = {"projectId": self.ids["project"], "buildId": self.ids["build"], "profileId": self.ids["profile"],
                         "runId": self.ids["run"], "pid": 4321, "uniqueId": "4321:10:20", "startTime": [10, 20],
                         "executableSha256": "b" * 64, "processRecordSha256": "c" * 64}
        self.discovery = {"schemaVersion": 1, "backend": vp.BACKEND, "channelId": None, "host": "127.0.0.1", "port": None,
                          "pid": 4321, "instanceId": "1" * 32, "nonce": "2" * 32, "buildGUID": "3" * 32,
                          "deviceId": "4" * 32, "unityVersion": "6000.6.2f1", "inputSystemVersion": "1.20.1",
                          "coordinateSpace": "screen-pixels", "screenWidth": 800, "screenHeight": 600}
        self.snapshot = {"status": "verified", "uniqueId": self.instance["uniqueId"], "environment": {}}

    def tearDown(self):
        self.home_patcher.stop()
        self.temp.cleanup()
        import shutil
        shutil.rmtree(self.fake_app, ignore_errors=True)

    def fixture(self, port):
        spec_path = self.root / "prepare.json"
        prepare_spec = {"schemaVersion": 1, "contract": vp.PREPARE_CONTRACT, "projectId": self.ids["project"], "buildId": self.ids["build"],
                        "profileId": self.ids["profile"], "unityVersion": "6000.6.2f1", "inputSystemVersion": "1.20.1",
                        "leaseSeconds": 300, "idleReleaseSeconds": 10, "commandMaxSeconds": 3, "stopOnTakeover": True}
        write_json(spec_path, prepare_spec)
        prepared = vp.prepare(spec_path, sha(encoded(prepare_spec)), self.root / ("prepared-" + uuid.uuid4().hex))
        channel_path = Path(prepared["channel"])
        public = json.loads(channel_path.read_text())
        config = vp._read_private(public["configPath"])
        self.active_config = config
        self.discovery.update(channelId=config["channelId"], port=port)
        write_json(Path(config["endpointPath"]), self.discovery)
        # qa.prepare's owner points at a controlled copy whose bytes equal
        # the private channel config, as required by the typed env binding.
        typed_config = self.root / ("qa-controlled-config-" + uuid.uuid4().hex + ".json")
        typed_config.write_bytes(Path(public["configPath"]).read_bytes())
        owner = {"environmentBindings": {vp.ENV_NAME: {"kind": "config", "id": "virtual-pointer"}},
                 "configInputs": {"virtual-pointer": {"path": str(typed_config), "sha256": public["configSha256"]}}}
        self.snapshot["environment"] = {vp.ENV_NAME: str(typed_config)}
        return prepared, public, config, owner

    def patches(self, owner):
        from grea.development import qa_binding, qa_runtime, process_identity
        return (patch.object(qa_binding, "_resolve", return_value={**self.instance, "launchBundlePath": str(self.fake_app), "processRecord": str(self.fake_app / "run.json")}),
                patch.object(qa_runtime, "_read_owner", return_value=(self.root, self.root, owner)),
                patch.object(process_identity, "snapshot", return_value=self.snapshot))

    def make_retirement_case(self):
        from grea.development import qa_runtime
        from .test_qa_runtime import QaRuntimePrepareTests

        fixture = QaRuntimePrepareTests(); fixture.setUp(); self.addCleanup(fixture.tearDown)
        prepare_spec = {"schemaVersion": 1, "contract": vp.PREPARE_CONTRACT, "projectId": "fixture-project", "buildId": "build-a",
                        "profileId": "profile-a", "unityVersion": "6000.6.2f1", "inputSystemVersion": "1.20.1",
                        "leaseSeconds": 300, "idleReleaseSeconds": 10, "commandMaxSeconds": 3, "stopOnTakeover": True}
        vp_spec = self.root / ("retire-prepare-" + uuid.uuid4().hex + ".json")
        write_json(vp_spec, prepare_spec)
        vp_prepared = vp.prepare(vp_spec, sha(encoded(prepare_spec)), self.root / ("retire-vp-prepared-" + uuid.uuid4().hex))
        channel = json.loads(Path(vp_prepared["channel"]).read_text())
        private_config = vp._read_private(channel["configPath"])

        qa_spec, _ = fixture.make_spec(profile="profile-a", test_mode="denyDocuments")
        qa_doc = json.loads(Path(qa_spec).read_text())
        qa_doc["configInputs"]["virtualPointer"] = {"path": channel["configPath"], "sha256": channel["configSha256"]}
        qa_doc["environmentBindings"][vp.ENV_NAME] = {"kind": "config", "id": "virtualPointer"}
        write_json(qa_spec, qa_doc)
        prepared = fixture.call_prepare((qa_spec, digest_file(qa_spec)))
        owner = prepared["owner"]; owner_sha = prepared["ownerSha256"]
        build_root = fixture.mock_home / "Library/Application Support/beaver/unity-qa/fixture-project/builds/build-a"
        app = build_root / "App.app"; exe = app / "Contents/MacOS/Fixture"
        data = build_root.parent.parent / "data"
        run_id = "archived-run-a"; pid = 4321; unique = "4321:100:7"; start = [100, 7]
        log = data / "logs/profile-a" / (run_id + ".log"); log.parent.mkdir(parents=True, exist_ok=True); log.write_bytes(b"safe test log\n")
        console_log = log.with_name(run_id + ".console.log"); console_log.write_bytes(b"safe console log\n")
        expected_args = [str(exe), *owner["arguments"], "-logFile", str(log)]
        docs = (Path.home() / "Documents").resolve()
        escaped = str(docs).replace("\\", "\\\\").replace('"', '\\"')
        policy = f'(version 1)\n(allow default)\n(deny file-read* (subpath "{escaped}"))\n(deny file-write* (subpath "{escaped}"))\n'
        policy_path = data / "receipts" / ("deny-documents-" + run_id + ".sb")
        policy_path.parent.mkdir(parents=True, exist_ok=True); policy_path.write_text(policy, encoding="utf-8")
        sandbox = {"requested": True, "profilePath": str(policy_path), "profileSha256": sha(policy.encode()),
                   "launchCompleted": True, "enforcementIndependentlyVerified": False}
        command = ["/usr/bin/sandbox-exec", "-p", policy, *expected_args]
        env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(Path.home()),
               "TMPDIR": str(data / "tmp/profile-a"), "LANG": "en_US.UTF-8"}
        profile_root = prepared["profileRoot"]
        for name, binding in owner["environmentBindings"].items():
            env[name] = str(profile_root) if binding["kind"] == "profile" else owner["configInputs"][binding["id"]]["path"]
        origin = {"status": "verified", "pid": pid, "parentPid": 123, "uniqueId": unique, "startTime": start,
                  "initialExecutablePath": str(exe), "initialPhase": "player", "expectedArgumentsSha256": sha(encoded(expected_args)),
                  "environmentMatched": True, "birthIdentitySource": "PROC_PIDTBSDINFO"}
        record = {"schemaVersion": 1, "contract": "beaver-unity-qa-process/1", "runId": run_id,
                  "projectId": "fixture-project", "buildId": "build-a", "profileId": "profile-a", "expectedOwnerSha256": owner_sha,
                  "pid": pid, "owned": True, "status": "exited", "exitCode": 0, "stoppedByBudget": False,
                  "startedUtc": "2026-11-02T12:10:00+00:00", "budgetSeconds": 120,
                  "exitedUtc": "2026-11-02T12:17:42.692185+00:00", "cwd": str(app), "executablePath": str(exe),
                  "executableSha256": digest_file(exe), "command": command, "logPath": str(log), "mode": "denyDocuments",
                  "consoleLogPath": str(console_log), "documentsSandbox": sandbox, "cleanEnvironment": env,
                  "pidIdentity": {"status": "verified", "pid": pid, "uniqueId": unique, "startTime": start},
                  "instanceOrigin": origin}
        run_path = data / "runs" / (run_id + ".json"); run_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        qa_runtime._write_control_json(run_path, record, create=True)
        running_record = dict(record); running_record["status"] = "running"
        for key in ("exitCode", "exitedUtc", "stoppedByBudget"): running_record.pop(key, None)
        running_sandbox = dict(sandbox); running_sandbox["launchCompleted"] = False
        running_record["documentsSandbox"] = running_sandbox
        running_record_sha = sha(encoded(running_record))

        instance_id = "5" * 32; nonce = "6" * 32; build_guid = "7" * 32; device_id = "42"
        discovery = {"schemaVersion": 1, "backend": vp.BACKEND, "channelId": private_config["channelId"], "host": "127.0.0.1", "port": 45678,
                     "pid": pid, "instanceId": instance_id, "nonce": nonce, "buildGUID": build_guid, "deviceId": device_id,
                     "unityVersion": private_config["unityVersion"], "inputSystemVersion": private_config["inputSystemVersion"],
                     "coordinateSpace": "unity-screen-pixels", "screenWidth": 640, "screenHeight": 480}
        lifecycle = {"schemaVersion": 1, "contract": "beaver-virtual-pointer-lifecycle/1", "status": "stopped", "reason": "application_quit",
                     "channelId": private_config["channelId"], "instanceId": instance_id, "pid": pid, "physicalTakeover": False,
                     "unityFocused": True, "applicationBatchMode": True, "osForeground": False, "osFrontmostAvailable": True,
                     "osFrontmostPid": 420, "screenWidth": 640, "screenHeight": 480, "observedScreenWidth": 640,
                     "observedScreenHeight": 480, "frame": 1000, "framesQueued": 4, "framesConsumed": 4,
                     "inputEventsQueued": 4, "ackFrame": 998, "lastEventFrame": 998, "buttonDown": False,
                     "deviceCreated": True, "listenerStarted": True, "endpointPublished": True, "cleanupPerformed": True,
                     "actionRoutesRestored": True, "uiRoutesRestored": 1, "deviceRemoved": True, "listenerStopped": True,
                     "endpointRemoved": True, "backgroundRestored": True}
        receipt_root = Path(private_config["receiptRoot"])
        lifecycle_path = receipt_root / ("lifecycle-" + instance_id + ".json")
        write_json(lifecycle_path, lifecycle); os.chmod(lifecycle_path, 0o644)
        state_path = Path(private_config["endpointPath"]).parent / "client-state.json"
        state = {"schemaVersion": 1, "channelId": private_config["channelId"], "instanceId": instance_id,
                 "deviceId": device_id, "nextSequence": 5, "blockedUnknown": False, "stopped": False,
                 "lastReceipt": {"status": "consumed"}}
        vp._write_private(state_path, state)
        instance = {"projectId": "fixture-project", "buildId": "build-a", "profileId": "profile-a", "runId": run_id,
                    "pid": pid, "uniqueId": unique, "startTime": start, "executableSha256": digest_file(exe),
                    "processRecordSha256": running_record_sha}
        session = {"schemaVersion": 1, "contract": vp.SESSION_CONTRACT, "sessionId": uuid.uuid4().hex, "backend": vp.BACKEND,
                   "channelId": private_config["channelId"], "configPath": channel["configPath"],
                   "configSha256": channel["configSha256"], "statePath": str(state_path), "discovery": discovery,
                   "instance": instance, "ownerSha256": owner_sha, "runId": run_id,
                   "createdUtc": "2026-11-02T12:00:00+00:00", "launchPerformed": False}
        session_path = self.root / ("retire-session-" + uuid.uuid4().hex + ".json"); write_json(session_path, session)
        return {"fixture": fixture, "homeRoot": fixture.mock_home / "Library/Application Support/beaver/unity-qa",
                "owner": owner, "ownerSha": owner_sha, "runPath": run_path, "record": record, "app": app,
                "config": private_config, "channel": channel, "lifecyclePath": lifecycle_path, "lifecycle": lifecycle,
                "statePath": state_path, "state": state, "session": session, "sessionPath": session_path,
                "sessionSha": digest_file(session_path), "policyPath": policy_path, "typedConfigPath": owner["configInputs"]["virtualPointer"]["path"],
                "out": self.root / ("retire-out-" + uuid.uuid4().hex)}

    def archived_stop_context(self, case):
        from grea.development import process_identity, qa_binding, qa_runtime
        resolve_error = BeaverError("QA_BIND_NOT_RUNNING", case["session"]["runId"], "Only running records use live binding")
        stack = [patch.object(qa_binding, "_resolve", side_effect=resolve_error),
                 patch.object(qa_runtime, "_home_root", return_value=case["homeRoot"]),
                 patch.object(process_identity, "snapshot", return_value={"status": "missing", "pid": case["session"]["instance"]["pid"]}),
                 patch.object(vp, "_exchange", side_effect=AssertionError("retired stop must not dispatch"))]
        return stack

    def call_archived_stop(self, case, patches=None):
        contexts = self.archived_stop_context(case) if patches is None else patches
        for p in contexts: p.__enter__()
        try:
            return vp.stop(case["sessionPath"], case["sessionSha"], case["out"])
        finally:
            for p in reversed(contexts): p.__exit__(None, None, None)

    def repin_archived_run(self, case, record):
        from grea.development import qa_runtime
        qa_runtime._write_control_json(case["runPath"], record, create=False)
        case["record"] = record
        running = dict(record); running["status"] = "running"
        for key in ("exitCode", "exitedUtc", "stoppedByBudget"): running.pop(key, None)
        sandbox = dict(record["documentsSandbox"]); sandbox["launchCompleted"] = False
        running["documentsSandbox"] = sandbox
        case["session"]["instance"]["processRecordSha256"] = sha(encoded(running))
        write_json(case["sessionPath"], case["session"])
        case["sessionSha"] = digest_file(case["sessionPath"])

    def receipt(self, request, status="consumed", **extra):
        base = {"schemaVersion": 1, "contract": vp.RECEIPT_CONTRACT, "backend": vp.BACKEND, "status": status,
                "channelId": self.discovery["channelId"], "instanceId": self.discovery["instanceId"], "pid": self.discovery["pid"],
                "buildGUID": self.discovery["buildGUID"], "unityVersion": self.discovery["unityVersion"],
                "inputSystemVersion": self.discovery["inputSystemVersion"], "deviceId": self.discovery["deviceId"], "deviceNative": False,
                "coordinateSpace": self.discovery["coordinateSpace"], "screenWidth": 800, "screenHeight": 600,
                "osForeground": True, "frontmostPid": self.discovery["pid"], "applicationBatchMode": False,
                "sequence": request["sequence"], "lastAcceptedSequence": request["sequence"], "framesQueued": 1,
                "framesConsumed": 1, "inputEventsQueued": 1, "buttonDown": False, "ackFrame": 12, "lastEventFrame": 11,
                "physicalTakeover": False, "cleanupPerformed": False, "sourceIsolation": "device-specific-ui-actions", "targetRoute": "InputSystemUIInputModule"}
        if status == "stopped" and extra.get("cleanupPerformed") is True:
            base.update({k: True for k in ("deviceRemoved", "actionRoutesRestored", "listenerStopped", "backgroundRestored", "endpointRemoved")})
        base.update(extra)
        return base

    def bind_session(self, responder):
        server = MockPointerServer(responder)
        server.__enter__()
        prepared, public, config, owner = self.fixture(server.port)
        contexts = self.patches(owner)
        for context in contexts: context.__enter__()
        try:
            result = vp.bind(self.ids["project"], self.ids["build"], self.ids["profile"], self.ids["owner"], self.ids["run"],
                             prepared["channel"], prepared["channelSha256"], self.root / "bound")
            return server, prepared, public, config, owner, result, contexts
        except Exception:
            for context in reversed(contexts): context.__exit__(None, None, None)
            server.__exit__(None, None, None)
            raise

    def test_prepare_bind_and_input_are_private_and_identity_bound(self):
        def answer(req, _):
            state = "verified" if req["operation"] == "hello" else "consumed"
            reason = self.active_config["token"] if req["operation"] == "click" else ""
            return self.receipt(req, state, reason=reason)

        server, prepared, public, config, owner, bound, contexts = self.bind_session(answer)
        try:
            session = Path(bound["session"])
            spec = self.root / "input.json"
            input_doc = {"schemaVersion": 1, "contract": vp.INPUT_CONTRACT, "backend": vp.BACKEND,
                         "instanceId": self.discovery["instanceId"], "deviceId": self.discovery["deviceId"], "coordinateSpace": self.discovery["coordinateSpace"],
                         "screenWidth": 800, "screenHeight": 600, "commands": [{"operation": "click", "x": 100, "y": 200}]}
            write_json(spec, input_doc)
            with patch.object(Path, "home", return_value=self.home):
                result = vp.input_event(session, bound["sessionSha256"], spec, sha(encoded(input_doc)), self.root / "input-result")
            self.assertEqual(result["status"], "consumed")
            self.assertEqual([r["operation"] for r in server.requests], ["hello", "click"])
            self.assertEqual(set(server.requests[0]), READONLY_REQUEST_KEYS)
            pointer_keys = {"expiresUnixMs", "coordinateSpace", "screenWidth", "screenHeight", "instanceId", "deviceId", "x", "y"}
            self.assertTrue(pointer_keys <= set(server.requests[1]))
            self.assertEqual(server.requests[-1]["sequence"], 1)
            self.assertEqual(server.requests[-1]["instanceId"], self.discovery["instanceId"])
            self.assertEqual(server.requests[-1]["deviceId"], self.discovery["deviceId"])
            input_text = Path(result["receipt"]).read_text()
            self.assertNotIn(config["token"], input_text)
            saved_receipt = json.loads(input_text)["receipts"][0]
            self.assertEqual(saved_receipt["reason"], "[REDACTED]")
            self.assertEqual((saved_receipt["osForeground"], saved_receipt["frontmostPid"], saved_receipt["applicationBatchMode"]), (True, 4321, False))
            client_receipts = Path(public["configPath"]).parent / "client-receipts"
            self.assertTrue(client_receipts.is_dir())
            self.assertTrue(all(config["token"] not in p.read_text() for p in client_receipts.glob("*.json")))
            self.assertEqual(vp._redact_value(["prefix-" + config["token"]], config["token"]), ["prefix-[REDACTED]"])
            self.assertEqual(os.stat(public["configPath"]).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(Path(public["configPath"]).parent).st_mode & 0o777, 0o700)
        finally:
            for context in reversed(contexts): context.__exit__(None, None, None)
            server.__exit__(None, None, None)

    def test_unknown_dispatch_is_reserved_once_and_status_does_not_replay(self):
        def answer(req, index):
            if req["operation"] == "hello": return self.receipt(req, "verified")
            if req["operation"] == "move": return None  # received, then transport outcome is unknown
            if req["operation"] == "inspect":
                last = self.receipt({"sequence": 1}, "consumed")
                last["reason"] = self.active_config["token"]
                return self.receipt(req, "verified", lastAcceptedSequence=1, lastCommandSequence=1,
                                    lastCommandState="consumed", lastCommandReceipt=last)
            return self.receipt(req, "stopped", cleanupPerformed=True)

        server, prepared, public, config, owner, bound, contexts = self.bind_session(answer)
        try:
            spec = self.root / "input.json"
            input_doc = {"schemaVersion": 1, "contract": vp.INPUT_CONTRACT, "backend": vp.BACKEND,
                         "instanceId": self.discovery["instanceId"], "deviceId": self.discovery["deviceId"], "coordinateSpace": self.discovery["coordinateSpace"],
                         "screenWidth": 800, "screenHeight": 600, "commands": [{"operation": "move", "x": 5, "y": 8}]}
            write_json(spec, input_doc)
            with patch.object(Path, "home", return_value=self.home):
                result = vp.input_event(bound["session"], bound["sessionSha256"], spec, sha(encoded(input_doc)), self.root / "partial")
                with self.assertRaises(Exception): vp.input_event(bound["session"], bound["sessionSha256"], spec, sha(encoded(input_doc)), self.root / "blocked")
                status = vp.status(bound["session"], bound["sessionSha256"], self.root / "status")
                stopped = vp.stop(bound["session"], bound["sessionSha256"], self.root / "stopped")
            self.assertEqual(result["status"], "partial")
            self.assertEqual(status["status"], "verified")
            status_text = Path(status["receipt"]).read_text()
            self.assertNotIn(config["token"], status_text)
            self.assertEqual(json.loads(status_text)["receipt"]["lastCommandReceipt"]["reason"], "[REDACTED]")
            self.assertTrue(stopped["cleanupPerformed"])
            self.assertEqual([r["operation"] for r in server.requests], ["hello", "move", "inspect", "inspect", "stop"])
            readonly_inspect = READONLY_REQUEST_KEYS | {"instanceId", "deviceId"}
            self.assertEqual(set(server.requests[2]), readonly_inspect)
            self.assertEqual(set(server.requests[3]), readonly_inspect)
            self.assertEqual(server.requests[1]["sequence"], 1)
            self.assertEqual(server.requests[4]["sequence"], 2)
            self.assertFalse(Path(public["configPath"]).exists())
        finally:
            for context in reversed(contexts): context.__exit__(None, None, None)
            server.__exit__(None, None, None)

    def test_bad_device_identity_never_dispatches(self):
        server, prepared, public, config, owner, bound, contexts = self.bind_session(lambda req, _: self.receipt(req, "verified"))
        try:
            spec = self.root / "bad.json"
            doc = {"schemaVersion": 1, "contract": vp.INPUT_CONTRACT, "backend": vp.BACKEND,
                   "instanceId": "f" * 32, "deviceId": self.discovery["deviceId"], "coordinateSpace": self.discovery["coordinateSpace"],
                   "screenWidth": 800, "screenHeight": 600, "commands": [{"operation": "move", "x": 1, "y": 1}]}
            write_json(spec, doc)
            with patch.object(Path, "home", return_value=self.home), self.assertRaises(Exception):
                vp.input_event(bound["session"], bound["sessionSha256"], spec, sha(encoded(doc)), self.root / "bad-result")
            self.assertEqual([r["operation"] for r in server.requests], ["hello"])
        finally:
            for context in reversed(contexts): context.__exit__(None, None, None)
            server.__exit__(None, None, None)

    def test_unaccepted_unknown_is_not_replayed_and_stop_uses_server_next_sequence(self):
        def answer(req, _):
            if req["operation"] == "hello": return self.receipt(req, "verified")
            if req["operation"] == "move": return None
            if req["operation"] == "inspect": return self.receipt(req, "verified", lastAcceptedSequence=0, lastCommandSequence=0, lastCommandState="verified")
            return self.receipt(req, "stopped", cleanupPerformed=True)

        server, prepared, public, config, owner, bound, contexts = self.bind_session(answer)
        try:
            spec = self.root / "input-not-accepted.json"
            doc = {"schemaVersion": 1, "contract": vp.INPUT_CONTRACT, "backend": vp.BACKEND,
                   "instanceId": self.discovery["instanceId"], "deviceId": self.discovery["deviceId"], "coordinateSpace": self.discovery["coordinateSpace"],
                   "screenWidth": 800, "screenHeight": 600, "commands": [{"operation": "move", "x": 5, "y": 8}]}
            write_json(spec, doc)
            result = vp.input_event(bound["session"], bound["sessionSha256"], spec, sha(encoded(doc)), self.root / "not-accepted")
            self.assertEqual(result["status"], "partial")
            with self.assertRaises(Exception):
                vp.input_event(bound["session"], bound["sessionSha256"], spec, sha(encoded(doc)), self.root / "still-blocked")
            status = vp.status(bound["session"], bound["sessionSha256"], self.root / "not-accepted-status")
            self.assertTrue(status["outcomeBlocked"])
            stopped = vp.stop(bound["session"], bound["sessionSha256"], self.root / "not-accepted-stop")
            self.assertTrue(stopped["cleanupPerformed"])
            self.assertEqual([r["operation"] for r in server.requests], ["hello", "move", "inspect", "inspect", "stop"])
            self.assertEqual(server.requests[1]["sequence"], 1)
            self.assertEqual(server.requests[-1]["sequence"], 1)
        finally:
            for context in reversed(contexts): context.__exit__(None, None, None)
            server.__exit__(None, None, None)

    def test_nonterminal_stop_receipt_keeps_gestures_blocked(self):
        def answer(req, _):
            if req["operation"] == "hello": return self.receipt(req, "verified")
            if req["operation"] == "inspect": return self.receipt(req, "verified", lastAcceptedSequence=0)
            return self.receipt(req, "verified", cleanupPerformed=False)

        server, prepared, public, config, owner, bound, contexts = self.bind_session(answer)
        try:
            stopped = vp.stop(bound["session"], bound["sessionSha256"], self.root / "not-stopped")
            self.assertEqual(stopped["status"], "partial")
            self.assertTrue(stopped["needsAction"])
            spec = self.root / "input-after-stop.json"
            doc = {"schemaVersion": 1, "contract": vp.INPUT_CONTRACT, "backend": vp.BACKEND,
                   "instanceId": self.discovery["instanceId"], "deviceId": self.discovery["deviceId"], "coordinateSpace": self.discovery["coordinateSpace"],
                   "screenWidth": 800, "screenHeight": 600, "commands": [{"operation": "move", "x": 5, "y": 8}]}
            write_json(spec, doc)
            with self.assertRaises(Exception):
                vp.input_event(bound["session"], bound["sessionSha256"], spec, sha(encoded(doc)), self.root / "blocked-after-stop")
            self.assertEqual([r["operation"] for r in server.requests], ["hello", "inspect", "stop"])
            self.assertTrue(Path(public["configPath"]).exists())
            state_path = json.loads(Path(bound["session"]).read_text())["statePath"]
            self.assertTrue(Path(state_path).exists())
        finally:
            for context in reversed(contexts): context.__exit__(None, None, None)
            server.__exit__(None, None, None)

    def test_incomplete_cleanup_never_retires_private_state(self):
        for field in ("deviceRemoved", "actionRoutesRestored", "listenerStopped", "backgroundRestored", "endpointRemoved"):
            with self.subTest(field=field):
                def answer(req, _):
                    if req["operation"] == "hello": return self.receipt(req, "verified")
                    if req["operation"] == "inspect": return self.receipt(req, "verified", lastAcceptedSequence=0)
                    return self.receipt(req, "stopped", cleanupPerformed=True, **{field: False})
                server, prepared, public, config, owner, bound, contexts = self.bind_session(answer)
                try:
                    output = self.root / ("incomplete-" + field)
                    result = vp.stop(bound["session"], bound["sessionSha256"], output)
                    self.assertEqual(result["status"], "partial")
                    self.assertFalse(result["cleanupPerformed"])
                    self.assertTrue(result["needsAction"])
                    self.assertTrue(Path(public["configPath"]).exists())
                    state_path = Path(json.loads(Path(bound["session"]).read_text())["statePath"])
                    state = vp._read_private(state_path)
                    self.assertFalse(state["stopped"])
                    self.assertTrue(state["blockedUnknown"])
                finally:
                    for context in reversed(contexts): context.__exit__(None, None, None)
                    server.__exit__(None, None, None)
                    # Each subcase starts a fresh immutable session in its own output.
                    import shutil
                    shutil.rmtree(self.root / "bound")

    def test_replacement_endpoint_preserves_all_channel_files(self):
        def answer(req, _):
            if req["operation"] == "hello": return self.receipt(req, "verified")
            if req["operation"] == "inspect": return self.receipt(req, "verified", lastAcceptedSequence=0)
            replacement = dict(self.discovery, instanceId="f" * 32, nonce="e" * 32, pid=9876, deviceId="9876")
            write_json(Path(self.active_config["endpointPath"]), replacement)
            return self.receipt(req, "stopped", cleanupPerformed=True)

        server, prepared, public, config, owner, bound, contexts = self.bind_session(answer)
        try:
            state_path = Path(json.loads(Path(bound["session"]).read_text())["statePath"])
            result = vp.stop(bound["session"], bound["sessionSha256"], self.root / "replacement-stop")
            self.assertEqual(result["status"], "partial")
            self.assertTrue(result["needsAction"])
            self.assertFalse(result["cleanupPerformed"])
            self.assertTrue(Path(public["configPath"]).exists())
            self.assertTrue(state_path.exists())
            self.assertEqual(json.loads(Path(config["endpointPath"]).read_text())["instanceId"], "f" * 32)
        finally:
            for context in reversed(contexts): context.__exit__(None, None, None)
            server.__exit__(None, None, None)

    def test_pending_inspect_keeps_gestures_blocked_but_allows_explicit_stop(self):
        def answer(req, _):
            if req["operation"] == "hello": return self.receipt(req, "verified")
            if req["operation"] == "move": return None
            if req["operation"] == "inspect":
                pending = self.receipt({"sequence": 1}, "pending")
                return self.receipt(req, "verified", lastAcceptedSequence=1, lastCommandSequence=1,
                                    lastCommandState="pending", lastCommandReceipt=pending)
            return self.receipt(req, "stopped", cleanupPerformed=True)

        server, prepared, public, config, owner, bound, contexts = self.bind_session(answer)
        try:
            spec = self.root / "pending-input.json"
            doc = {"schemaVersion": 1, "contract": vp.INPUT_CONTRACT, "backend": vp.BACKEND,
                   "instanceId": self.discovery["instanceId"], "deviceId": self.discovery["deviceId"], "coordinateSpace": self.discovery["coordinateSpace"],
                   "screenWidth": 800, "screenHeight": 600, "commands": [{"operation": "move", "x": 5, "y": 8}]}
            write_json(spec, doc)
            result = vp.input_event(bound["session"], bound["sessionSha256"], spec, sha(encoded(doc)), self.root / "pending-unknown")
            self.assertEqual(result["status"], "partial")
            status = vp.status(bound["session"], bound["sessionSha256"], self.root / "pending-status")
            self.assertTrue(status["outcomeBlocked"])
            self.assertEqual(json.loads(Path(status["receipt"]).read_text())["receipt"]["lastCommandReceipt"]["status"], "pending")
            with self.assertRaises(Exception):
                vp.input_event(bound["session"], bound["sessionSha256"], spec, sha(encoded(doc)), self.root / "pending-blocked")
            stopped = vp.stop(bound["session"], bound["sessionSha256"], self.root / "pending-stop")
            self.assertTrue(stopped["cleanupPerformed"])
            self.assertEqual([r["operation"] for r in server.requests], ["hello", "move", "inspect", "inspect", "stop"])
            self.assertEqual(server.requests[-1]["sequence"], 2)
        finally:
            for context in reversed(contexts): context.__exit__(None, None, None)
            server.__exit__(None, None, None)

    def test_pending_is_rejected_as_a_top_level_receipt(self):
        receipt = self.receipt({"sequence": 0}, "pending")
        with self.assertRaises(Exception):
            vp._public_receipt(receipt, "a" * 64)

    def test_archived_clean_exit_retires_only_original_private_files_without_dispatch(self):
        case = self.make_retirement_case()
        case["state"]["blockedUnknown"] = True
        vp._write_private(case["statePath"], case["state"], create=False)
        lifecycle_sha = digest_file(case["lifecyclePath"])
        typed_copy = Path(case["typedConfigPath"])
        evidence_path = case["out"] / "retirement-evidence.json"
        original_unlink = os.unlink

        def assert_evidence_before_unlink(name, *args, **kwargs):
            if name in ("config.json", "client-state.json"):
                self.assertTrue(evidence_path.is_file())
                self.assertEqual(os.stat(evidence_path).st_mode & 0o777, 0o600)
                evidence = json.loads(evidence_path.read_text())
                self.assertEqual(evidence["phase"], "prepared")
                self.assertFalse(evidence["cleanupPerformed"])
                self.assertTrue(evidence["blockedUnknown"])
                self.assertEqual(evidence["nextSequence"], case["state"]["nextSequence"])
                self.assertEqual(evidence["stateBeforeSha256"], digest_file(case["statePath"]))
                self.assertFalse(evidence["cleanupResolvesBusinessOutcome"])
            return original_unlink(name, *args, **kwargs)

        contexts = self.archived_stop_context(case)
        contexts.append(patch.object(vp.os, "unlink", side_effect=assert_evidence_before_unlink))
        output = self.call_archived_stop(case, contexts)
        data = json.loads(Path(output["receipt"]).read_text())
        self.assertEqual(output["status"], "stopped")
        self.assertTrue(output["retiredAfterCleanExit"])
        self.assertFalse(output["dispatchPerformed"])
        self.assertEqual(data["cleanupEvidence"], "lifecycle-receipt")
        self.assertEqual(data["lifecycleReceiptSha256"], lifecycle_sha)
        evidence = json.loads(evidence_path.read_text())
        self.assertEqual(evidence["blockedUnknown"], True)
        self.assertEqual(data["retirementEvidenceSha256"], digest_file(evidence_path))
        self.assertFalse(data["cleanupResolvesBusinessOutcome"])
        self.assertFalse(Path(case["channel"]["configPath"]).exists())
        self.assertFalse(case["statePath"].exists())
        self.assertTrue(case["lifecyclePath"].exists())
        self.assertEqual(digest_file(case["lifecyclePath"]), lifecycle_sha)
        self.assertTrue(typed_copy.exists())
        self.assertTrue(case["app"].exists())
        self.assertTrue(case["runPath"].exists())

    def test_archived_retirement_holds_state_lock_for_full_validation_and_delete(self):
        from contextlib import contextmanager
        case = self.make_retirement_case()
        active = {"held": False}
        original_lock = vp._state_lock
        original_retire = vp._retire_clean_exit

        @contextmanager
        def traced_lock(path):
            with original_lock(path) as channel_fd:
                active["held"] = True
                try: yield channel_fd
                finally: active["held"] = False

        def traced_retire(*args):
            self.assertTrue(active["held"], "archived validation/deletion must run under the private state lock")
            return original_retire(*args)

        contexts = self.archived_stop_context(case)
        contexts.extend((patch.object(vp, "_state_lock", side_effect=traced_lock),
                         patch.object(vp, "_retire_clean_exit", side_effect=traced_retire)))
        result = self.call_archived_stop(case, contexts)
        self.assertTrue(result["retiredAfterCleanExit"])
        self.assertFalse(active["held"])

    def test_state_lock_rejects_symlink_parent_without_touching_outside_lock(self):
        channels = vp._private_root()
        channels.mkdir(mode=0o700, parents=True, exist_ok=True)
        channel_id = "a" * 32
        outside = self.root / "outside-lock-target"; outside.mkdir(mode=0o750)
        before_mode = os.stat(outside).st_mode & 0o777
        link = channels / channel_id; os.symlink(outside, link)
        with self.assertRaises(BeaverError):
            with vp._state_lock(link / "client-state.json"):
                self.fail("symlink parent must never be locked")
        self.assertFalse((outside / "client.lock").exists())
        self.assertEqual(os.stat(outside).st_mode & 0o777, before_mode)

    def test_state_lock_directory_swap_before_open_does_not_create_outside_lock(self):
        channels = vp._private_root()
        channels.mkdir(mode=0o700, parents=True, exist_ok=True)
        channel_id = "b" * 32
        channel = channels / channel_id; channel.mkdir(mode=0o700)
        held = channels / (channel_id + ".held-test")
        outside = self.root / "outside-lock-race"; outside.mkdir(mode=0o750)
        before_mode = os.stat(outside).st_mode & 0o777
        original_open = os.open

        def swap_then_open(path, flags, *args, **kwargs):
            if Path(path) == channel and flags & getattr(os, "O_DIRECTORY", 0):
                os.rename(channel, held)
                os.symlink(outside, channel)
            return original_open(path, flags, *args, **kwargs)

        with patch.object(vp.os, "open", side_effect=swap_then_open):
            with self.assertRaises(BeaverError):
                with vp._state_lock(channel / "client-state.json"):
                    self.fail("directory swap must be rejected before opening/creating the lock")
        self.assertFalse((outside / "client.lock").exists())
        self.assertEqual(os.stat(outside).st_mode & 0o777, before_mode)
        self.assertTrue(held.is_dir())

    def test_archived_parent_swap_race_never_unlinks_outside_channel_files(self):
        import shutil
        case = self.make_retirement_case()
        channel_root = Path(case["config"]["endpointPath"]).parent
        channels_root = channel_root.parent
        held_root = channels_root / (channel_root.name + ".held-test")
        outside = self.root / "replacement-channel-copy"
        outside_mode = 0o700
        from grea.development import qa_virtual_pointer as virtual_module
        original_snapshot = virtual_module._archive_snapshot

        def swap_after_snapshot(*args):
            result = original_snapshot(*args)
            shutil.copytree(channel_root, outside, copy_function=shutil.copy2)
            os.chmod(outside, outside_mode)
            os.rename(channel_root, held_root)
            os.symlink(outside, channel_root)
            return result

        contexts = self.archived_stop_context(case)
        contexts.append(patch.object(vp, "_archive_snapshot", side_effect=swap_after_snapshot))
        with self.assertRaises(BeaverError):
            self.call_archived_stop(case, contexts)
        self.assertTrue((outside / "config.json").exists())
        self.assertTrue((outside / "client-state.json").exists())
        self.assertEqual(os.stat(outside).st_mode & 0o777, outside_mode)
        self.assertTrue((held_root / "config.json").exists())
        self.assertTrue((held_root / "client-state.json").exists())
        self.assertTrue((outside / "client.lock").exists())  # copied lock only; no path-based external creation

    def test_sandbox_exec_birth_phase_must_match_exact_owned_launch_mode(self):
        accepted = self.make_retirement_case()
        origin = dict(accepted["record"]["instanceOrigin"], initialPhase="sandbox-exec", initialExecutablePath="/usr/bin/sandbox-exec")
        self.repin_archived_run(accepted, dict(accepted["record"], instanceOrigin=origin))
        self.assertTrue(self.call_archived_stop(accepted)["retiredAfterCleanExit"])

        rejected = self.make_retirement_case()
        origin = dict(rejected["record"]["instanceOrigin"], initialPhase="player", initialExecutablePath="/usr/bin/sandbox-exec")
        self.repin_archived_run(rejected, dict(rejected["record"], instanceOrigin=origin))
        with self.assertRaises(BeaverError): self.call_archived_stop(rejected)
        self.assertTrue(Path(rejected["channel"]["configPath"]).exists())
        self.assertTrue(rejected["statePath"].exists())

    def test_archived_retirement_requires_kernel_proven_missing_pid(self):
        from grea.development import process_identity
        snapshots = [
            {"status": "verified", "pid": 4321, "uniqueId": "4321:100:7"},
            {"status": "verified", "pid": 4321, "uniqueId": "4321:999:1"},
            {"status": "unknown", "pid": 4321},
        ]
        for i, snapshot in enumerate(snapshots):
            with self.subTest(snapshot=snapshot["status"], unique=snapshot.get("uniqueId")):
                case = self.make_retirement_case()
                contexts = self.archived_stop_context(case)
                contexts[2] = patch.object(process_identity, "snapshot", return_value=snapshot)
                with self.assertRaises(BeaverError): self.call_archived_stop(case, contexts)
                self.assertTrue(Path(case["channel"]["configPath"]).exists())
                self.assertTrue(case["statePath"].exists())

    def test_archived_retirement_requires_owned_zero_exit_nonbudget_record(self):
        from grea.development import qa_runtime
        changes = (("status", "running"), ("status", "failed"), ("exitCode", 7), ("stoppedByBudget", True), ("owned", False))
        for i, (key, value) in enumerate(changes):
            with self.subTest(field=key, value=value):
                case = self.make_retirement_case()
                changed = dict(case["record"]); changed[key] = value
                qa_runtime._write_control_json(case["runPath"], changed, create=False)
                with self.assertRaises(BeaverError): self.call_archived_stop(case)
                self.assertTrue(Path(case["channel"]["configPath"]).exists())
                self.assertTrue(case["statePath"].exists())

    def test_archived_record_origin_owner_typed_copy_and_bundle_drift_refuse_retirement(self):
        from grea.development import qa_runtime
        cases = ("origin", "archive-args", "archive-unrelated-field", "owner", "typed-copy", "bundle", "profile")
        for kind in cases:
            with self.subTest(kind=kind):
                case = self.make_retirement_case()
                if kind == "origin":
                    changed = dict(case["record"]); changed["instanceOrigin"] = dict(changed["instanceOrigin"], uniqueId="4321:999:1")
                    qa_runtime._write_control_json(case["runPath"], changed, create=False)
                elif kind == "archive-args":
                    changed = dict(case["record"]); changed["command"] = list(changed["command"]); changed["command"][-1] = "foreign.log"
                    qa_runtime._write_control_json(case["runPath"], changed, create=False)
                elif kind == "archive-unrelated-field":
                    changed = dict(case["record"]); changed["budgetSeconds"] = 121
                    qa_runtime._write_control_json(case["runPath"], changed, create=False)
                elif kind == "owner":
                    owner_path = case["app"].parent / "qa-owner.json"
                    owner = json.loads(owner_path.read_text()); owner["arguments"] = ["foreign"]
                    write_json(owner_path, owner)
                elif kind == "typed-copy":
                    Path(case["typedConfigPath"]).write_text("{}", encoding="utf-8")
                elif kind == "bundle":
                    (case["app"] / "Contents/Resources/extra.txt").write_text("drift", encoding="utf-8")
                elif kind == "profile":
                    changed = dict(case["record"]); changed["cleanEnvironment"] = dict(changed["cleanEnvironment"], FOODSTREET_PROFILE_DIRECTORY="/foreign/profile")
                    qa_runtime._write_control_json(case["runPath"], changed, create=False)
                with self.assertRaises(BeaverError): self.call_archived_stop(case)
                self.assertTrue(Path(case["channel"]["configPath"]).exists())
                self.assertTrue(case["statePath"].exists())

    def test_lifecycle_receipt_must_match_exact_identity_reason_and_all_cleanup_flags(self):
        corruptions = (("reason", "object_destroyed"), ("channelId", "f" * 32), ("instanceId", "f" * 32),
                       ("pid", 9999), ("screenWidth", 800), ("buttonDown", True), ("deviceCreated", False),
                       ("listenerStarted", False), ("endpointPublished", False), ("actionRoutesRestored", False),
                       ("uiRoutesRestored", 0), ("deviceRemoved", False), ("listenerStopped", False),
                       ("endpointRemoved", False), ("backgroundRestored", False), ("cleanupPerformed", False),
                       ("deviceCreated", 1), ("listenerStarted", 1), ("endpointPublished", 1),
                       ("cleanupPerformed", 1), ("buttonDown", 0), ("physicalTakeover", 0))
        for key, value in corruptions:
            with self.subTest(field=key):
                case = self.make_retirement_case()
                altered = dict(case["lifecycle"]); altered[key] = value
                write_json(case["lifecyclePath"], altered); os.chmod(case["lifecyclePath"], 0o644)
                with self.assertRaises(BeaverError): self.call_archived_stop(case)
                self.assertTrue(Path(case["channel"]["configPath"]).exists())
                self.assertTrue(case["statePath"].exists())

    def test_existing_replacement_endpoint_refuses_and_preserves_channel_files(self):
        case = self.make_retirement_case()
        endpoint = Path(case["config"]["endpointPath"])
        write_json(endpoint, dict(case["session"]["discovery"], instanceId="f" * 32, nonce="e" * 32, pid=9876))
        with self.assertRaises(BeaverError): self.call_archived_stop(case)
        self.assertTrue(Path(case["channel"]["configPath"]).exists())
        self.assertTrue(case["statePath"].exists())
        self.assertEqual(json.loads(endpoint.read_text())["instanceId"], "f" * 32)

    def test_predelete_race_rechecks_endpoint_lifecycle_config_state_and_archive(self):
        from grea.development import process_identity
        for target in ("endpoint", "lifecycle", "config", "state", "archive"):
            with self.subTest(target=target):
                case = self.make_retirement_case()
                contexts = self.archived_stop_context(case)
                calls = {"n": 0}

                def snapshot(pid):
                    calls["n"] += 1
                    if calls["n"] == 3:
                        if target == "endpoint":
                            write_json(Path(case["config"]["endpointPath"]), dict(case["session"]["discovery"], instanceId="f" * 32))
                        elif target == "lifecycle":
                            changed = dict(case["lifecycle"]); changed["frame"] += 1
                            write_json(case["lifecyclePath"], changed); os.chmod(case["lifecyclePath"], 0o644)
                        elif target == "config":
                            Path(case["channel"]["configPath"]).write_text("{}", encoding="utf-8")
                        elif target == "state":
                            changed = dict(case["state"], nextSequence=case["state"]["nextSequence"] + 1)
                            vp._write_private(case["statePath"], changed, create=False)
                        elif target == "archive":
                            changed = dict(case["record"], exitedUtc="2026-11-03T00:00:00+00:00")
                            from grea.development import qa_runtime
                            qa_runtime._write_control_json(case["runPath"], changed, create=False)
                    return {"status": "missing", "pid": pid}

                contexts[2] = patch.object(process_identity, "snapshot", side_effect=snapshot)
                with self.assertRaises(BeaverError): self.call_archived_stop(case, contexts)
                self.assertTrue(Path(case["channel"]["configPath"]).exists())
                self.assertTrue(case["statePath"].exists())


if __name__ == "__main__":
    unittest.main()
