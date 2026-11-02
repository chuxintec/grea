"""Loopback client for Beaver's isolated Unity virtual-pointer companion.

The client has no native-input fallback. It binds an explicit owned QA run to
one private channel and one virtual device, and treats an ambiguous dispatch as
possibly delivered until an explicit status/stop operation resolves it.
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import re
import socket
import stat
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .errors import fail
from .io import encoded, load, new_output, read, safe, sha, write_json
from .output_limits import digest_file

BACKEND = "unity-inputsystem-virtual-pointer/1"
PREPARE_CONTRACT = "beaver-virtual-pointer-prepare/1"
INPUT_CONTRACT = "beaver-virtual-pointer-input/1"
SESSION_CONTRACT = "beaver-virtual-pointer-session/1"
CHANNEL_CONTRACT = "beaver-virtual-pointer-channel/1"
COMMAND_CONTRACT = "beaver-virtual-pointer-command/1"
RECEIPT_CONTRACT = "beaver-virtual-pointer-receipt/1"
CONFIG_CONTRACT = "beaver-virtual-pointer-config/1"
ENV_NAME = "BEAVER_VIRTUAL_POINTER_CONFIG"
MAX_JSON = 64 * 1024
HEX32 = re.compile(r"^[a-f0-9]{32}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")
IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
OPS = {"move", "down", "up", "click", "drag", "scroll", "release", "capture"}
RECEIPT_FIELDS = {
    "schemaVersion", "contract", "backend", "status", "errorCode", "channelId", "instanceId", "pid",
    "buildGUID", "unityVersion", "inputSystemVersion", "deviceId", "deviceNative", "deviceCanRunInBackground",
    "coordinateSpace", "screenWidth", "screenHeight", "focused", "osForeground", "frontmostPid", "applicationBatchMode", "sequence", "lastAcceptedSequence",
    "framesQueued", "framesConsumed", "inputEventsQueued", "buttonDown", "ackFrame", "lastEventFrame",
    "physicalTakeover", "cleanupPerformed", "deviceRemoved", "actionRoutesRestored", "listenerStopped", "backgroundRestored", "endpointRemoved", "sourceIsolation", "targetRoute", "targetHitName", "targetHitFrame",
    "capturePath", "captureSha", "captureSha256", "lastCommandSequence", "lastCommandState", "lastCommandReceipt",
    "lastAckFrame", "lastInputEventsQueued", "reason",
}


def _hash(v, field):
    if not isinstance(v, str) or not HEX64.fullmatch(v): fail("QA_VP_SHA", field, "Expected lowercase SHA256")
    return v


def _id(v, field):
    if not isinstance(v, str) or not IDENT.fullmatch(v) or v in (".", ".."):
        fail("QA_VP_ID", field, "Expected a safe stable identifier")
    return v


def _finite(v, field, low=None, high=None):
    if type(v) not in (int, float) or not math.isfinite(v) or (low is not None and v < low) or (high is not None and v > high):
        fail("QA_VP_NUMBER", field, "Expected a finite number within the documented bounds")
    return float(v)


def _read_spec(path, expected, contract, keys):
    path = safe(path); raw = read(path, 256 * 1024)
    if sha(raw) != _hash(expected, "expectedSpecSha256"): fail("QA_VP_SPEC_DRIFT", str(path), "Explicit expected spec SHA256 does not match")
    try: doc = load(raw, max_nodes=10000)
    except Exception: fail("QA_VP_SPEC", str(path), "Spec is not bounded valid UTF-8 JSON")
    if not isinstance(doc, dict) or set(doc) != keys or type(doc.get("schemaVersion")) is not int or doc["schemaVersion"] != 1 or doc.get("contract") != contract:
        fail("QA_VP_SPEC", str(path), "Expected the closed virtual-pointer contract")
    return doc, sha(raw)


def _private_root():
    return Path.home() / "Library" / "Application Support" / "beaver" / "virtual-pointer" / "channels"


def _secure_dir(path, create=False):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink(): fail("QA_VP_PATH", str(part), "Private channel paths cannot contain symbolic links")
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
    if not path.is_dir(): fail("QA_VP_PATH", str(path), "Expected a private channel directory")
    st = path.stat()
    if st.st_uid != os.getuid():
        fail("QA_VP_PERMISSIONS", str(path), "Private channel directory must be user-owned mode 0700")
    os.chmod(path, 0o700)
    if stat.S_IMODE(path.stat().st_mode) != 0o700:
        fail("QA_VP_PERMISSIONS", str(path), "Private channel directory must be user-owned mode 0700")
    return path


def _write_private(path, value, create=True):
    path = Path(path)
    flags = os.O_WRONLY | os.O_NOFOLLOW | (os.O_CREAT | os.O_EXCL if create else os.O_TRUNC)
    try: fd = os.open(path, flags, 0o600)
    except OSError as exc: fail("QA_VP_PRIVATE_FILE", path.name, f"Private file could not be opened ({type(exc).__name__})")
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.getuid(): fail("QA_VP_PRIVATE_FILE", path.name, "Expected an independent user-owned regular file")
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(encoded(value)); stream.flush(); os.fsync(fd)
    finally: os.close(fd)


def _read_private(path):
    path = Path(path)
    try: fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc: fail("QA_VP_PRIVATE_FILE", path.name, f"Private file could not be opened ({type(exc).__name__})")
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o600:
            fail("QA_VP_PRIVATE_FILE", path.name, "Expected an independent user-owned 0600 file")
        with os.fdopen(fd, "rb", closefd=False) as stream: raw = stream.read(MAX_JSON + 1)
    finally: os.close(fd)
    if len(raw) > MAX_JSON: fail("QA_VP_PRIVATE_FILE", path.name, "Private file exceeds its byte budget")
    try: return load(raw, max_nodes=10000)
    except Exception: fail("QA_VP_PRIVATE_FILE", path.name, "Private file is malformed")


def _config_shape(config):
    keys = {"schemaVersion", "contract", "channelId", "token", "endpointPath", "receiptRoot", "projectId", "buildId", "profileId", "unityVersion", "inputSystemVersion", "leaseSeconds", "idleReleaseSeconds", "commandMaxSeconds", "stopOnTakeover"}
    if not isinstance(config, dict) or set(config) != keys or config.get("schemaVersion") != 1 or config.get("contract") != CONFIG_CONTRACT:
        fail("QA_VP_CONFIG", "config", "Private channel config does not match the closed schema")
    if not HEX32.fullmatch(str(config.get("channelId", ""))) or not HEX64.fullmatch(str(config.get("token", ""))):
        fail("QA_VP_CONFIG", "config", "Private channel credentials have invalid format")
    for key in ("projectId", "buildId", "profileId", "unityVersion", "inputSystemVersion"): _id(config.get(key), key)
    for key, lo, hi in (("leaseSeconds", 30, 1800), ("idleReleaseSeconds", 1, 60), ("commandMaxSeconds", 1, 30)):
        if type(config.get(key)) is not int or not lo <= config[key] <= hi: fail("QA_VP_CONFIG", key, "Config timing value is outside its documented bounds")
    if config.get("stopOnTakeover") is not True: fail("QA_VP_CONFIG", "stopOnTakeover", "Takeover stop is mandatory")
    channel = _private_root() / config["channelId"]
    for key in ("endpointPath", "receiptRoot"):
        value = Path(config.get(key, ""))
        if not value.is_absolute() or not value.is_relative_to(channel): fail("QA_VP_CONFIG", key, "Channel paths must remain under their private channel directory")
    return config


def _redact_value(value, token):
    if isinstance(value, str): return value.replace(token, "[REDACTED]") if token else value
    if isinstance(value, list): return [_redact_value(item, token) for item in value]
    if isinstance(value, dict):
        return {_redact_value(k, token): _redact_value(v, token) for k, v in value.items()}
    return value


def _public_receipt(data, token, depth=0):
    if depth > 2: fail("QA_VP_PROTOCOL", "response", "Nested receipt depth exceeds the protocol bound")
    if not isinstance(data, dict): fail("QA_VP_PROTOCOL", "response", "Server receipt is not a JSON object")
    clean = {k: _redact_value(v, token) for k, v in data.items() if k in RECEIPT_FIELDS and k.lower() not in ("token", "secret", "request")}
    if data.get("schemaVersion") != 1 or data.get("contract") != RECEIPT_CONTRACT or data.get("backend") != BACKEND:
        fail("QA_VP_PROTOCOL", "response", "Server receipt contract is invalid")
    allowed_statuses = ("verified", "consumed", "blocked", "partial", "stopped", "not_supported")
    if data.get("status") not in allowed_statuses + (("pending",) if depth > 0 else ()):
        fail("QA_VP_PROTOCOL", "response", "Server receipt status is invalid")
    if isinstance(data.get("lastCommandReceipt"), dict):
        clean["lastCommandReceipt"] = _public_receipt(data["lastCommandReceipt"], token, depth + 1)
    return clean


def _exchange(discovery, config, request):
    if discovery.get("host") != "127.0.0.1" or type(discovery.get("port")) is not int or not 1 <= discovery["port"] <= 65535:
        fail("QA_VP_ENDPOINT", "discovery", "Only a valid loopback TCP endpoint is accepted")
    payload = (json.dumps(request, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    if len(payload) > MAX_JSON: fail("QA_VP_REQUEST_SIZE", "request", "One command must fit in the protocol byte budget")
    try:
        with socket.create_connection(("127.0.0.1", discovery["port"]), timeout=config["commandMaxSeconds"]) as sock:
            sock.settimeout(config["commandMaxSeconds"])
            sock.sendall(payload)
            chunks = bytearray()
            while len(chunks) <= MAX_JSON:
                block = sock.recv(min(4096, MAX_JSON + 1 - len(chunks)))
                if not block: break
                chunks.extend(block)
                if b"\n" in block: break
    except (OSError, TimeoutError) as exc:
        # The caller already reserved the sequence, so this is unknown/partial.
        raise _DispatchUnknown(type(exc).__name__) from None
    if len(chunks) > MAX_JSON or not chunks.endswith(b"\n") or chunks.count(b"\n") != 1:
        raise _DispatchUnknown("incomplete-receipt")
    line = bytes(chunks).split(b"\n", 1)[0]
    try: raw = load(line, max_nodes=10000)
    except Exception: raise _DispatchUnknown("invalid-receipt") from None
    return _public_receipt(raw, config["token"])


class _DispatchUnknown(Exception):
    pass


def _discovery(config):
    path = safe(config["endpointPath"])
    try: data = load(read(path, 16 * 1024), max_nodes=1000)
    except Exception: fail("QA_VP_ENDPOINT", "discovery", "No valid virtual-pointer discovery record is available")
    keys = {"schemaVersion", "backend", "channelId", "host", "port", "pid", "instanceId", "nonce", "buildGUID", "deviceId", "unityVersion", "inputSystemVersion", "coordinateSpace", "screenWidth", "screenHeight"}
    if not isinstance(data, dict) or set(data) != keys or data.get("schemaVersion") != 1 or data.get("backend") != BACKEND or data.get("channelId") != config["channelId"]:
        fail("QA_VP_ENDPOINT", "discovery", "Discovery identity does not match the prepared channel")
    for key in ("instanceId", "nonce", "buildGUID"):
        if not HEX32.fullmatch(str(data.get(key, ""))): fail("QA_VP_ENDPOINT", key, "Discovery identifier is malformed")
    if not isinstance(data.get("deviceId"), str) or not IDENT.fullmatch(data["deviceId"]):
        fail("QA_VP_ENDPOINT", "deviceId", "Discovery virtual-device identifier is malformed")
    if type(data.get("pid")) is not int or data["pid"] <= 0 or type(data.get("screenWidth")) is not int or type(data.get("screenHeight")) is not int or data["screenWidth"] <= 0 or data["screenHeight"] <= 0:
        fail("QA_VP_ENDPOINT", "discovery", "Discovery process or screen dimensions are invalid")
    for key in ("unityVersion", "inputSystemVersion", "coordinateSpace"): _id(data.get(key), key)
    return data


def _request(config, discovery, operation, sequence=0, **extra):
    req = {"schemaVersion": 1, "contract": COMMAND_CONTRACT, "backend": BACKEND,
           "channelId": config["channelId"], "token": config["token"], "operation": operation,
           "sequence": sequence}
    if operation in ("hello", "inspect"):
        if operation == "inspect" or "instanceId" in extra:
            req["instanceId"] = discovery["instanceId"]
            req["deviceId"] = discovery["deviceId"]
        return req
    req.update({"expiresUnixMs": int(time.time() * 1000) + config["commandMaxSeconds"] * 1000,
                "coordinateSpace": discovery["coordinateSpace"], "screenWidth": discovery["screenWidth"],
                "screenHeight": discovery["screenHeight"], "instanceId": discovery["instanceId"],
                "deviceId": discovery["deviceId"], **extra})
    return req


def _identity(receipt, config, discovery, sequence=None):
    checks = {"channelId": config["channelId"], "instanceId": discovery["instanceId"], "pid": discovery["pid"], "buildGUID": discovery["buildGUID"],
              "unityVersion": discovery["unityVersion"], "inputSystemVersion": discovery["inputSystemVersion"], "deviceId": discovery["deviceId"],
              "deviceNative": False, "coordinateSpace": discovery["coordinateSpace"], "screenWidth": discovery["screenWidth"], "screenHeight": discovery["screenHeight"]}
    for key, value in checks.items():
        if receipt.get(key) != value: fail("QA_VP_RECEIPT_IDENTITY", key, "Server receipt does not match the bound live channel/device")
    if sequence is not None and receipt.get("sequence") != sequence: fail("QA_VP_RECEIPT_SEQUENCE", "sequence", "Receipt sequence does not match the reserved command")


@contextmanager
def _state_lock(path):
    lock_path = Path(path).with_name("client.lock")
    try: fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError as exc: fail("QA_VP_STATE", "client", f"Private client lock unavailable ({type(exc).__name__})")
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.getuid(): fail("QA_VP_STATE", "client", "Client lock is not a private regular file")
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "r+b", closefd=False) as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            yield
    finally: os.close(fd)


def _session(path, expected):
    path = safe(path); raw = read(path, 64 * 1024)
    if sha(raw) != _hash(expected, "expectedSessionSha256"): fail("QA_VP_SESSION_DRIFT", str(path), "Explicit expected session SHA256 does not match")
    try: session = load(raw, max_nodes=5000)
    except Exception: fail("QA_VP_SESSION", str(path), "Session is malformed")
    keys = {"schemaVersion", "contract", "sessionId", "backend", "channelId", "configPath", "configSha256", "statePath", "discovery", "instance", "ownerSha256", "runId", "createdUtc", "launchPerformed"}
    if not isinstance(session, dict) or set(session) != keys or session.get("schemaVersion") != 1 or session.get("contract") != SESSION_CONTRACT or session.get("backend") != BACKEND or session.get("launchPerformed") is not False:
        fail("QA_VP_SESSION", str(path), "Session identity or closed envelope is invalid")
    config = _config_shape(_read_private(session["configPath"]))
    if sha(encoded(config)) != session["configSha256"] or config["channelId"] != session["channelId"]:
        fail("QA_VP_SESSION", str(path), "Private channel config identity changed")
    if Path(session["statePath"]) != Path(session["configPath"]).with_name("client-state.json"):
        fail("QA_VP_SESSION", str(path), "Client state is not in its private channel")
    return path, session, config


def _owned_live(session):
    from .qa_binding import _resolve
    old = session["instance"]
    new = _resolve(old["projectId"], old["buildId"], old["profileId"], session["ownerSha256"], session["runId"])
    for key in ("pid", "uniqueId", "startTime", "executableSha256", "processRecordSha256"):
        if new.get(key) != old.get(key): fail("QA_VP_OWNED_RUN_CHANGED", key, "Owned QA process changed since virtual-pointer binding")
    # Ensure the generated private config is a declared typed QA config and is the exact live environment value.
    from .qa_runtime import _read_owner
    _, _, owner = _read_owner(old["projectId"], old["buildId"], old["profileId"], session["ownerSha256"])
    binding = owner.get("environmentBindings", {}).get(ENV_NAME)
    if not isinstance(binding, dict) or binding.get("kind") != "config" or binding.get("id") not in owner.get("configInputs", {}):
        fail("QA_VP_CONFIG_BINDING", ENV_NAME, "Owned run lacks the explicit typed virtual-pointer config binding")
    cfg_input = owner["configInputs"][binding["id"]]
    if not isinstance(cfg_input.get("path"), str): fail("QA_VP_CONFIG_BINDING", ENV_NAME, "Typed config binding has no controlled path")
    # qa.prepare copies declared configInputs into its controlled Application
    # Support tree. The channel source remains private and immutable; accept the
    # copy only when both byte identity and the live process environment agree.
    if digest_file(cfg_input["path"]) != session["configSha256"]:
        fail("QA_VP_CONFIG_BINDING", ENV_NAME, "Typed config copy differs from this private channel config")
    live = process_identity_snapshot(new["pid"])
    if live.get("status") != "verified" or live.get("uniqueId") != new["uniqueId"] or (live.get("environment") or {}).get(ENV_NAME) != cfg_input["path"]:
        fail("QA_VP_CONFIG_BINDING", ENV_NAME, "Live process environment no longer matches the typed config binding")
    if cfg_input.get("sha256") != session["configSha256"]:
        fail("QA_VP_CONFIG_BINDING", ENV_NAME, "Typed config SHA differs from this private channel")
    return new


def process_identity_snapshot(pid):
    from . import process_identity
    return process_identity.snapshot(pid)


def prepare(spec, expected_spec, out):
    keys = {"schemaVersion", "contract", "projectId", "buildId", "profileId", "unityVersion", "inputSystemVersion", "leaseSeconds", "idleReleaseSeconds", "commandMaxSeconds", "stopOnTakeover"}
    doc, spec_sha = _read_spec(spec, expected_spec, PREPARE_CONTRACT, keys)
    for key in ("projectId", "buildId", "profileId", "unityVersion", "inputSystemVersion"): _id(doc[key], key)
    for key, low, high in (("leaseSeconds", 30, 1800), ("idleReleaseSeconds", 1, 60), ("commandMaxSeconds", 1, 30)):
        if type(doc[key]) is not int or not low <= doc[key] <= high: fail("QA_VP_CONFIG", key, "Timing value is outside its documented bounds")
    if doc["stopOnTakeover"] is not True: fail("QA_VP_CONFIG", "stopOnTakeover", "Takeover stop is mandatory")
    folder = new_output(out, [safe(spec)])
    channel_id = uuid.uuid4().hex
    root = _secure_dir(_private_root(), create=False) if _private_root().exists() else None
    if root is None:
        _private_root().mkdir(mode=0o700, parents=True, exist_ok=True)
        root = _secure_dir(_private_root())
    channel = _secure_dir(root / channel_id, create=True)
    (channel / "receipts").mkdir(mode=0o700)
    token = os.urandom(32).hex()
    config = {"schemaVersion": 1, "contract": CONFIG_CONTRACT, "channelId": channel_id, "token": token,
              "endpointPath": str(channel / "endpoint.json"), "receiptRoot": str(channel / "receipts"),
              "projectId": doc["projectId"], "buildId": doc["buildId"], "profileId": doc["profileId"],
              "unityVersion": doc["unityVersion"], "inputSystemVersion": doc["inputSystemVersion"],
              "leaseSeconds": doc["leaseSeconds"], "idleReleaseSeconds": doc["idleReleaseSeconds"],
              "commandMaxSeconds": doc["commandMaxSeconds"], "stopOnTakeover": True}
    config_path = channel / "config.json"; _write_private(config_path, config)
    config_sha = digest_file(config_path)
    public = {"schemaVersion": 1, "contract": CHANNEL_CONTRACT, "status": "prepared", "backend": BACKEND,
              "channelId": channel_id, "projectId": doc["projectId"], "buildId": doc["buildId"], "profileId": doc["profileId"],
              "configPath": str(config_path), "configSha256": config_sha, "configEnvironmentName": ENV_NAME,
              "specSha256": spec_sha, "launchPerformed": False,
              "limitation": "The owned QA launch must declare this exact config path under BEAVER_VIRTUAL_POINTER_CONFIG; channel credentials are omitted."}
    write_json(folder / "virtual-channel.json", public)
    return {"status": "prepared", "channel": str(folder / "virtual-channel.json"), "channelSha256": digest_file(folder / "virtual-channel.json"),
            "channelId": channel_id, "configPath": str(config_path), "configSha256": config_sha, "launchPerformed": False}


def bind(project, build, profile, expected_owner, run, channel, expected_channel, out):
    channel_path = safe(channel); raw = read(channel_path, 64 * 1024)
    if sha(raw) != _hash(expected_channel, "expectedChannelSha256"): fail("QA_VP_CHANNEL_DRIFT", str(channel_path), "Explicit expected channel SHA256 does not match")
    try: public = load(raw, max_nodes=3000)
    except Exception: fail("QA_VP_CHANNEL", str(channel_path), "Channel receipt is malformed")
    keys = {"schemaVersion", "contract", "status", "backend", "channelId", "projectId", "buildId", "profileId", "configPath", "configSha256", "configEnvironmentName", "specSha256", "launchPerformed", "limitation"}
    if not isinstance(public, dict) or set(public) != keys or public.get("contract") != CHANNEL_CONTRACT or public.get("status") != "prepared" or public.get("backend") != BACKEND or public.get("launchPerformed") is not False:
        fail("QA_VP_CHANNEL", str(channel_path), "Expected the closed prepared channel receipt")
    if (public["projectId"], public["buildId"], public["profileId"]) != (project, build, profile) or public["configEnvironmentName"] != ENV_NAME:
        fail("QA_VP_CHANNEL_IDENTITY", str(channel_path), "Channel project/profile or config binding differs")
    config = _config_shape(_read_private(public["configPath"]))
    config_sha = digest_file(public["configPath"])
    if config_sha != public["configSha256"] or config_sha != sha(encoded(config)) or config["channelId"] != public["channelId"]:
        fail("QA_VP_CONFIG_DRIFT", str(public["configPath"]), "Private channel config differs from prepared identity")
    from .qa_binding import _resolve
    instance = _resolve(project, build, profile, expected_owner, run, True)
    if (config["projectId"], config["buildId"], config["profileId"]) != (project, build, profile): fail("QA_VP_CONFIG_IDENTITY", "config", "Private config is scoped to a different QA identity")
    output = new_output(out, [channel_path, safe(public["configPath"]).parent, safe(instance["launchBundlePath"]), safe(instance["processRecord"]).parent])
    seed_session = {"instance": instance, "ownerSha256": expected_owner, "runId": run, "configPath": public["configPath"], "configSha256": config_sha}
    _owned_live({**seed_session, "channelId": config["channelId"]})
    discovery = _discovery(config)
    if discovery["pid"] != instance["pid"] or discovery["unityVersion"] != config["unityVersion"] or discovery["inputSystemVersion"] != config["inputSystemVersion"]:
        fail("QA_VP_DISCOVERY_IDENTITY", "discovery", "Server PID or runtime versions differ from the owned process/config")
    request = _request(config, discovery, "hello", 0)
    try: receipt = _exchange(discovery, config, request)
    except _DispatchUnknown as exc: fail("QA_VP_HELLO_UNKNOWN", "hello", f"Authenticated hello outcome is unknown ({str(exc)})")
    _identity(receipt, config, discovery, 0)
    if receipt.get("status") not in ("verified", "consumed"): fail("QA_VP_HELLO_REFUSED", "hello", "Companion did not verify the initial channel handshake")
    state = {"schemaVersion": 1, "channelId": config["channelId"], "instanceId": discovery["instanceId"], "deviceId": discovery["deviceId"],
             "nextSequence": 1, "blockedUnknown": False, "stopped": False, "lastReceipt": receipt}
    state_path = Path(public["configPath"]).with_name("client-state.json"); _write_private(state_path, state)
    session = {"schemaVersion": 1, "contract": SESSION_CONTRACT, "sessionId": uuid.uuid4().hex, "backend": BACKEND,
               "channelId": config["channelId"], "configPath": public["configPath"], "configSha256": config_sha,
               "statePath": str(state_path), "discovery": discovery,
               "instance": {k: instance[k] for k in ("projectId", "buildId", "profileId", "runId", "pid", "uniqueId", "startTime", "executableSha256", "processRecordSha256")},
               "ownerSha256": expected_owner, "runId": run, "createdUtc": datetime.now(timezone.utc).isoformat(), "launchPerformed": False}
    session_path = output / "virtual-pointer-session.json"; write_json(session_path, session)
    result = {"status": "bound", "session": str(session_path), "sessionSha256": digest_file(session_path), "channelId": config["channelId"],
              "instanceId": discovery["instanceId"], "deviceId": discovery["deviceId"], "pid": discovery["pid"], "launchPerformed": False}
    write_json(output / "virtual-pointer-bind.json", result)
    return result


def _input_rows(doc, session, config, discovery):
    keys = {"schemaVersion", "contract", "backend", "instanceId", "deviceId", "coordinateSpace", "screenWidth", "screenHeight", "commands"}
    if set(doc) != keys or doc.get("contract") != INPUT_CONTRACT or doc.get("backend") != BACKEND or doc.get("schemaVersion") != 1:
        fail("QA_VP_INPUT_SPEC", "spec", "Expected the closed virtual-pointer input spec")
    for key in ("instanceId", "deviceId", "coordinateSpace", "screenWidth", "screenHeight"):
        if doc.get(key) != discovery[key]: fail("QA_VP_INPUT_IDENTITY", key, "Input spec must bind to the immutable channel/device/coordinate space")
    rows = doc.get("commands")
    if not isinstance(rows, list) or not rows or len(rows) > 64: fail("QA_VP_COMMANDS", "commands", "Expected 1..64 bounded commands")
    clean = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("operation") not in OPS: fail("QA_VP_COMMAND", str(i), "Unknown or malformed operation; no fallback is available")
        op = row["operation"]
        if op in ("move", "down", "up", "click", "drag", "scroll"):
            _finite(row.get("x"), f"commands.{i}.x", 0, discovery["screenWidth"] - 1); _finite(row.get("y"), f"commands.{i}.y", 0, discovery["screenHeight"] - 1)
        allowed = {"operation", "x", "y", "scrollX", "scrollY", "points", "stepFrames"}
        if set(row) - allowed: fail("QA_VP_COMMAND", str(i), "Command has unknown fields")
        if op == "scroll":
            for key in ("scrollX", "scrollY"): _finite(row.get(key), f"commands.{i}.{key}", -10000, 10000)
        if op == "drag":
            points = row.get("points")
            if not isinstance(points, list) or not 1 <= len(points) <= 128 or type(row.get("stepFrames")) is not int or not 1 <= row["stepFrames"] <= 10:
                fail("QA_VP_DRAG", str(i), "Drag requires 1..128 points and stepFrames 1..10")
            for j, p in enumerate(points):
                if not isinstance(p, dict) or set(p) != {"x", "y"}: fail("QA_VP_DRAG", f"commands.{i}.points.{j}", "Each point must contain only x and y")
                _finite(p["x"], "point.x", 0, discovery["screenWidth"] - 1); _finite(p["y"], "point.y", 0, discovery["screenHeight"] - 1)
        clean.append(dict(row))
    return clean


def _persist_receipt(config, sequence, receipt):
    # The companion owns receiptRoot. Keep Python's sanitized transport record
    # in a separate private child to avoid replacing or colliding with its files.
    folder = _secure_dir(Path(config["endpointPath"]).parent / "client-receipts") if (Path(config["endpointPath"]).parent / "client-receipts").exists() else None
    if folder is None:
        folder_path = Path(config["endpointPath"]).parent / "client-receipts"
        folder_path.mkdir(mode=0o700)
        folder = _secure_dir(folder_path)
    target = folder / f"receipt-{sequence:010d}-{uuid.uuid4().hex}.json"
    write_json(target, receipt); os.chmod(target, 0o600)
    return str(target)


def _cleanup_confirmed(receipt):
    return (receipt.get("status") == "stopped" and receipt.get("buttonDown") is False
            and all(receipt.get(k) is True for k in ("cleanupPerformed", "deviceRemoved", "actionRoutesRestored", "listenerStopped", "backgroundRestored", "endpointRemoved")))


def _dispatch(config, discovery, state_path, state, operation, **extra):
    seq = state["nextSequence"]
    state["nextSequence"] = seq + 1
    state["blockedUnknown"] = True  # Durable intent reservation before any bytes leave the client.
    _write_private(state_path, state, create=False)
    request = _request(config, discovery, operation, seq, **extra)
    try: receipt = _exchange(discovery, config, request)
    except _DispatchUnknown as exc:
        receipt = {"schemaVersion": 1, "contract": RECEIPT_CONTRACT, "backend": BACKEND, "status": "partial", "errorCode": "QA_VP_OUTCOME_UNKNOWN", "channelId": config["channelId"], "sequence": seq, "reason": str(exc)}
        receipt["receiptPath"] = _persist_receipt(config, seq, receipt)
        _write_private(state_path, state, create=False)
        return receipt
    _identity(receipt, config, discovery, seq)
    receipt["receiptPath"] = _persist_receipt(config, seq, receipt)
    state["lastReceipt"] = receipt
    state["blockedUnknown"] = receipt.get("status") in ("partial",)
    if operation == "stop":
        stopped_cleanly = _cleanup_confirmed(receipt)
        state["stopped"] = stopped_cleanly
        state["blockedUnknown"] = not stopped_cleanly
    _write_private(state_path, state, create=False)
    return receipt


def _inspect(config, discovery):
    request = _request(config, discovery, "inspect", 0)
    try: receipt = _exchange(discovery, config, request)
    except _DispatchUnknown as exc: fail("QA_VP_STATUS_UNKNOWN", "inspect", f"Read-only status outcome is unknown ({str(exc)})")
    _identity(receipt, config, discovery, 0)
    return receipt


def input_event(session, expected_session, spec, expected_spec, out):
    path, envelope, config = _session(session, expected_session)
    doc, spec_sha = _read_spec(spec, expected_spec, INPUT_CONTRACT, {"schemaVersion", "contract", "backend", "instanceId", "deviceId", "coordinateSpace", "screenWidth", "screenHeight", "commands"})
    discovery = envelope["discovery"]
    rows = _input_rows(doc, envelope, config, discovery)
    _owned_live(envelope)
    output = new_output(out, [path, safe(envelope["configPath"]).parent, safe(spec), safe(config["endpointPath"]), Path(config["receiptRoot"])])
    results = []
    state_path = Path(envelope["statePath"])
    with _state_lock(state_path):
        state = _read_private(state_path)
        if state.get("blockedUnknown") or state.get("stopped"): fail("QA_VP_STATE_BLOCKED", str(state_path), "Channel has an unresolved outcome or is stopped; query status/stop before more gestures")
        for row in rows:
            _owned_live(envelope)
            receipt = _dispatch(config, discovery, state_path, state, row["operation"], **{k: v for k, v in row.items() if k != "operation"})
            results.append(receipt)
            if receipt.get("status") not in ("verified", "consumed"):
                break
    result = {"schemaVersion": 1, "contract": "beaver-virtual-pointer-input-result/1", "status": results[-1]["status"],
              "backend": BACKEND, "channelId": config["channelId"], "instanceId": discovery["instanceId"], "deviceId": discovery["deviceId"],
              "specSha256": spec_sha, "receipts": results, "launchPerformed": False,
              "limitation": "Consumed input events do not claim gameplay or business acceptance."}
    write_json(output / "virtual-pointer-input.json", result)
    return {"status": result["status"], "receipt": str(output / "virtual-pointer-input.json"), "receipts": results, "launchPerformed": False}


def status(session, expected_session, out):
    path, envelope, config = _session(session, expected_session); discovery = envelope["discovery"]
    _owned_live(envelope)
    output = new_output(out, [path, safe(envelope["configPath"]).parent, safe(config["endpointPath"]), Path(config["receiptRoot"])])
    state_path = Path(envelope["statePath"])
    with _state_lock(state_path):
        state = _read_private(state_path)
        receipt = _inspect(config, discovery)
        accepted = receipt.get("lastAcceptedSequence")
        attempted = state.get("nextSequence", 1) - 1
        if type(accepted) is not int or accepted < 0 or accepted > attempted:
            fail("QA_VP_STATUS_SEQUENCE", "lastAcceptedSequence", "Server sequence is outside the client's reserved range")
        if accepted < attempted:
            # The uncertain command was not accepted. Keep gesture dispatch
            # blocked, but align a later explicit stop to the server's sequence.
            state["nextSequence"] = accepted + 1
        state["lastReceipt"] = receipt
        command_receipt = receipt.get("lastCommandReceipt")
        command_seq = receipt.get("lastCommandSequence")
        if isinstance(command_receipt, dict):
            _identity(command_receipt, config, discovery, command_seq)
        if (accepted == attempted and command_seq == attempted and isinstance(command_receipt, dict)
                and command_receipt.get("status") in ("verified", "consumed", "blocked", "not_supported")):
            # The actual last command receipt resolves ambiguity; inspect's own
            # top-level status is read-only and never proves gesture delivery.
            state["blockedUnknown"] = False
        _write_private(state_path, state, create=False)
    result = {"schemaVersion": 1, "contract": "beaver-virtual-pointer-status-result/1", "status": receipt["status"],
              "backend": BACKEND, "channelId": config["channelId"], "instanceId": discovery["instanceId"], "deviceId": discovery["deviceId"],
              "receipt": receipt, "lastReservedSequence": state.get("nextSequence", 1) - 1,
              "outcomeBlocked": state.get("blockedUnknown"), "launchPerformed": False}
    write_json(output / "virtual-pointer-status.json", result)
    return {"status": result["status"], "receipt": str(output / "virtual-pointer-status.json"), "outcomeBlocked": result["outcomeBlocked"], "launchPerformed": False}


def _endpoint_snapshot(config, discovery):
    """Read endpoint ownership without following links; return only guarded identity."""
    path = Path(config["endpointPath"])
    try: fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError: return {"state": "absent"}
    except OSError: return {"state": "unreadable"}
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid(): return {"state": "unreadable"}
        with os.fdopen(fd, "rb", closefd=False) as stream: raw = stream.read(16 * 1024 + 1)
    finally: os.close(fd)
    if len(raw) > 16 * 1024: return {"state": "unreadable"}
    try: current = load(raw, max_nodes=1000)
    except Exception: return {"state": "unreadable"}
    keys = ("channelId", "instanceId", "pid", "nonce", "buildGUID", "deviceId")
    if any(current.get(k) != discovery.get(k) for k in keys): return {"state": "replacement"}
    return {"state": "same", "device": info.st_dev, "inode": info.st_ino}


def _stop_cleanup(config, envelope, discovery, state_path):
    """Remove only this stopped instance's endpoint/config/state after identity checks."""
    endpoint = Path(config["endpointPath"])
    first = _endpoint_snapshot(config, discovery)
    if first["state"] in ("replacement", "unreadable"):
        return False, "Endpoint identity changed or could not be read; private channel files were retained."
    try: _owned_live(envelope)
    except Exception:
        return False, "The original owned process could not be revalidated; private channel files were retained."
    second = _endpoint_snapshot(config, discovery)
    if second["state"] in ("replacement", "unreadable"):
        return False, "A replacement endpoint appeared; private channel files were retained."
    if first["state"] == "same":
        if second["state"] != "same" or (first["device"], first["inode"]) != (second["device"], second["inode"]):
            return False, "Endpoint changed during cleanup; private channel files were retained."
        try:
            current = os.stat(endpoint, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (second["device"], second["inode"]) or stat.S_ISLNK(current.st_mode):
                return False, "Endpoint identity changed during cleanup; private channel files were retained."
            endpoint.unlink()
        except OSError:
            return False, "Owned endpoint could not be safely removed; private channel files were retained."
    # The old runtime may remove its endpoint itself after sending the stop
    # receipt. Recheck absence and the owned process before deleting credentials.
    if _endpoint_snapshot(config, discovery)["state"] != "absent":
        return False, "An endpoint remains or was replaced; private channel files were retained."
    try: _owned_live(envelope)
    except Exception:
        return False, "The original owned process could not be revalidated after stop; private channel files were retained."
    if _endpoint_snapshot(config, discovery)["state"] != "absent":
        return False, "A replacement endpoint appeared before credential cleanup; private channel files were retained."
    config_path = Path(envelope["configPath"])
    try:
        if digest_file(config_path) != envelope["configSha256"]:
            return False, "Private config changed; no channel files were deleted."
        config_path.unlink()
        Path(state_path).unlink()
    except OSError:
        return False, "Owned private files could not be safely removed; follow-up is required."
    return True, None


def stop(session, expected_session, out):
    path, envelope, config = _session(session, expected_session); discovery = envelope["discovery"]
    _owned_live(envelope)
    output = new_output(out, [path, safe(envelope["configPath"]).parent, safe(config["endpointPath"]), Path(config["receiptRoot"])])
    state_path = Path(envelope["statePath"])
    with _state_lock(state_path):
        state = _read_private(state_path)
        if state.get("stopped"):
            receipt = state.get("lastReceipt") or {"status": "stopped", "cleanupPerformed": True}
        else:
            # Stop is explicitly allowed while gesture dispatch is blocked.
            # Reconcile the server's accepted sequence first so a command
            # lost before acceptance cannot make cleanup use a stale sequence.
            inspect = _inspect(config, discovery)
            accepted = inspect.get("lastAcceptedSequence")
            attempted = state.get("nextSequence", 1) - 1
            if type(accepted) is not int or accepted < 0 or accepted > attempted:
                fail("QA_VP_STATUS_SEQUENCE", "lastAcceptedSequence", "Server sequence is outside the client's reserved range")
            state["nextSequence"] = accepted + 1
            receipt = _dispatch(config, discovery, state_path, state, "stop")
        cleanup_ok = False; cleanup_reason = None
        if _cleanup_confirmed(receipt):
            cleanup_ok, cleanup_reason = _stop_cleanup(config, envelope, discovery, state_path)
            if not cleanup_ok:
                state["stopped"] = False; state["blockedUnknown"] = True
                _write_private(state_path, state, create=False)
    clean_stop = _cleanup_confirmed(receipt) and cleanup_ok
    if not clean_stop and cleanup_reason is None:
        cleanup_reason = "Stop receipt did not confirm completed release and companion cleanup."
    result = {"schemaVersion": 1, "contract": "beaver-virtual-pointer-stop-result/1", "status": "stopped" if clean_stop else ("partial" if cleanup_reason else receipt.get("status")),
              "backend": BACKEND, "channelId": config["channelId"], "receipt": receipt,
              "cleanupPerformed": clean_stop, "needsAction": bool(cleanup_reason), "reason": cleanup_reason,
              "launchPerformed": False}
    write_json(output / "virtual-pointer-stop.json", result)
    return {"status": result["status"], "receipt": str(output / "virtual-pointer-stop.json"), "cleanupPerformed": result["cleanupPerformed"],
            "needsAction": result["needsAction"], "launchPerformed": False}
