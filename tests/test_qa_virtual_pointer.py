import json
import os
import socketserver
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from beaver import qa_virtual_pointer as vp
from beaver.io import encoded, sha, write_json

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
        from beaver import qa_binding, qa_runtime, process_identity
        return (patch.object(qa_binding, "_resolve", return_value={**self.instance, "launchBundlePath": str(self.fake_app), "processRecord": str(self.fake_app / "run.json")}),
                patch.object(qa_runtime, "_read_owner", return_value=(self.root, self.root, owner)),
                patch.object(process_identity, "snapshot", return_value=self.snapshot))

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


if __name__ == "__main__":
    unittest.main()
