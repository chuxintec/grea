"""Create-only receipts for a native transaction whose host journal was not finalized.

Recovery observes an old transaction and a pinned outer producer receipt. It
never launches Unity, invokes the verifier, sends a signal, or edits the old
transaction tree.
"""
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

from . import __version__
from .io import safe, inside, read, load, sha, write_json, new_output
from .preflight import validate_progress
from .sources.compiled import fail


SCHEMA = "monkey-native-execution-recovery-request/1"
RECEIPT_SCHEMA = "monkey-native-execution-recovery/1"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACTS = {
    "projectManifest": "UnityProject/manifest.json",
    "nativeProgress": "UnityProject/Analysis/Readback/native-progress.json",
    "importLog": "import.log",
    "consoleLog": "console.log",
}


def _require(condition, code, location, message):
    if not condition:
        fail(code, location, message)


def _sha_pin(value, location):
    _require(isinstance(value, str) and _SHA.fullmatch(value) is not None,
             "NATIVE_RECOVERY_REQUEST_INVALID", location, "Expected lowercase SHA-256")


def _read_pinned(path, digest, byte_count, location, max_bytes=128 * 1024 * 1024):
    _sha_pin(digest, location + ".sha256")
    _require(type(byte_count) is int and 0 <= byte_count <= max_bytes,
             "NATIVE_RECOVERY_REQUEST_INVALID", location + ".bytes", "Invalid pinned byte count")
    raw = read(path, max_bytes=max_bytes)
    _require(len(raw) == byte_count and sha(raw) == digest,
             "NATIVE_RECOVERY_INPUT_CHANGED", str(path), "Pinned transaction input changed")
    return raw


def _option(command, name):
    if not isinstance(command, list):
        return None
    matches = [index for index, value in enumerate(command) if value == name]
    if len(matches) != 1 or matches[0] + 1 >= len(command):
        return None
    return command[matches[0] + 1]


def _assert_pid_and_group_absent(pid, process_group):
    """Fail closed if either numeric identity is present or cannot be probed.

    `ps` is used instead of signalling a pid. Any reused pid/group is treated
    as present, even if its command is unrelated to the old Unity invocation.
    """
    _require(type(pid) is int and pid > 1 and type(process_group) is int and process_group > 1,
             "NATIVE_RECOVERY_PROCESS_IDENTITY_INVALID", "process", "Expected recorded pid and process group")
    try:
        result = subprocess.run(["/bin/ps", "-axo", "pid=,pgid="], capture_output=True,
                                text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        fail("NATIVE_RECOVERY_PROCESS_PROBE_FAILED", "process", str(error))
    _require(result.returncode == 0, "NATIVE_RECOVERY_PROCESS_PROBE_FAILED", "process",
             "Could not read the local process table")
    seen_pid = False
    seen_group = False
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            observed_pid, observed_group = int(fields[0]), int(fields[1])
        except ValueError:
            continue
        seen_pid |= observed_pid == pid
        seen_group |= observed_group == process_group
    _require(not seen_pid and not seen_group, "NATIVE_RECOVERY_PROCESS_STILL_PRESENT", "process",
             "Recorded pid or process group is present; it may still run or have been reused")


def recover_execution(request_path, expected_request_sha256, output):
    """Create an independent, hash-bound recovery receipt for a stale running journal.

    Request schema is intentionally strict. All paths in the transaction are
    relative to its pinned root; the outer run receipt is an explicitly pinned
    absolute path. Existing journal/log/project files are opened read-only.
    """
    request_path = safe(request_path)
    request_raw = read(request_path, max_bytes=1024 * 1024)
    _sha_pin(expected_request_sha256, "expectedRequestSha256")
    _require(sha(request_raw) == expected_request_sha256, "NATIVE_RECOVERY_REQUEST_HASH_MISMATCH",
             str(request_path), "Recovery request differs from its supplied pin")
    request = load(request_raw, max_nodes=10000, max_depth=32)
    required = {"schema", "schemaVersion", "transactionRoot", "producer", "pins"}
    _require(isinstance(request, dict) and set(request) == required and request.get("schema") == SCHEMA and
             type(request.get("schemaVersion")) is int and request["schemaVersion"] == 1,
             "NATIVE_RECOVERY_REQUEST_INVALID", str(request_path), "Unsupported or incomplete recovery request")

    _require(isinstance(request["transactionRoot"], str) and Path(request["transactionRoot"]).is_absolute(),
             "NATIVE_RECOVERY_REQUEST_INVALID", "transactionRoot", "Expected an absolute transaction path")
    transaction = safe(request["transactionRoot"])
    _require(transaction.is_dir(), "NATIVE_RECOVERY_TRANSACTION_MISSING", str(transaction), "Transaction root is absent")
    producer = request["producer"]
    if not isinstance(producer, dict) or set(producer) != {
            "toolId", "toolVersion", "launcherSha256", "entrypointPath", "entrypointSha256"}:
        fail("NATIVE_RECOVERY_REQUEST_INVALID", "producer", "Producer identity fields are incomplete")
    _require(producer["toolId"] in {"grea", "monkey"} and isinstance(producer["toolVersion"], str) and
             bool(producer["toolVersion"]) and isinstance(producer["entrypointPath"], str) and
             Path(producer["entrypointPath"]).is_absolute(), "NATIVE_RECOVERY_PRODUCER_MISMATCH", "producer",
             "Unsupported producer identity")
    _sha_pin(producer["launcherSha256"], "producer.launcherSha256")
    _sha_pin(producer["entrypointSha256"], "producer.entrypointSha256")

    pins = request["pins"]
    pin_keys = {
        "nativePlanSha256", "nativePlanBytes", "planIdentitySha256", "planIdentityBytes",
        "executionJournalSha256", "executionJournalBytes",
        "sourceManifestSha256", "importPlanSha256", "runReceiptPath", "runReceiptSha256",
        "runReceiptBytes", "projectManifestSha256", "projectManifestBytes",
        "nativeProgressSha256", "nativeProgressBytes", "importLogSha256", "importLogBytes",
        "consoleLogSha256", "consoleLogBytes",
    }
    if not isinstance(pins, dict) or set(pins) != pin_keys:
        fail("NATIVE_RECOVERY_REQUEST_INVALID", "pins", "Input identity fields are incomplete")
    for name in ("nativePlanSha256", "planIdentitySha256", "executionJournalSha256", "sourceManifestSha256",
                 "importPlanSha256", "runReceiptSha256", "projectManifestSha256", "nativeProgressSha256",
                 "importLogSha256", "consoleLogSha256"):
        _sha_pin(pins[name], "pins." + name)
    _require(isinstance(pins["runReceiptPath"], str) and Path(pins["runReceiptPath"]).is_absolute(),
             "NATIVE_RECOVERY_REQUEST_INVALID", "pins.runReceiptPath", "Expected an absolute run receipt path")

    # Read and verify all immutable transaction inputs before interpreting them.
    plan_path = inside(transaction, "native-plan.json")
    plan_raw = _read_pinned(plan_path, pins["nativePlanSha256"], pins["nativePlanBytes"], "nativePlan", 4 * 1024 * 1024)
    identity_path = inside(transaction, "plan-identity.json")
    identity_raw = _read_pinned(identity_path, pins["planIdentitySha256"], pins["planIdentityBytes"], "planIdentity", 1024 * 1024)
    journal_path = inside(transaction, "execution-journal.json")
    journal_raw = _read_pinned(journal_path, pins["executionJournalSha256"], pins["executionJournalBytes"], "executionJournal", 1024 * 1024)
    run_path = safe(pins["runReceiptPath"])
    run_raw = _read_pinned(run_path, pins["runReceiptSha256"], pins["runReceiptBytes"], "runReceipt", 32 * 1024 * 1024)
    artifacts = {}
    for key, relative in _ARTIFACTS.items():
        byte_key = key + "Bytes"
        path = inside(transaction, relative)
        artifacts[key] = (path, _read_pinned(path, pins[key + "Sha256"], pins[byte_key], key,
                                             128 * 1024 * 1024 if key == "projectManifest" else 64 * 1024 * 1024))

    plan = load(plan_raw, max_nodes=100000, max_depth=64)
    identity = load(identity_raw, max_nodes=10000, max_depth=32)
    journal = load(journal_raw, max_nodes=10000, max_depth=32)
    run = load(run_raw, max_nodes=100000, max_depth=64)
    _require(all(isinstance(value, dict) for value in (plan, identity, journal, run)),
             "NATIVE_RECOVERY_INPUT_INVALID", "transaction", "Pinned JSON documents must be objects")
    _require(identity.get("schemaVersion") == 1 and identity.get("sha256") == pins["nativePlanSha256"],
             "NATIVE_RECOVERY_PLAN_IDENTITY_MISMATCH", "plan-identity.json", "Native plan identity is inconsistent")
    _require(plan.get("schemaVersion") == 1 and plan.get("nativeResumeSupported") is False and
             plan.get("status") is None and plan.get("sourceManifestSha256") == pins["sourceManifestSha256"] and
             plan.get("importPlanSha256") == pins["importPlanSha256"] and
             plan.get("toolVersion") == producer["toolVersion"] and
             plan.get("launcherSha256") == producer["launcherSha256"] and
             plan.get("project") == "UnityProject" and plan.get("method") == "MonkeyImporter.ImportBatchAsync",
             "NATIVE_RECOVERY_PLAN_PRODUCER_MISMATCH", "native-plan.json", "Native plan differs from request producer pins")
    _require(journal.get("schemaVersion") == 1 and journal.get("status") == "running" and
             journal.get("processStarted") is True and journal.get("processExited") is False and
             journal.get("pid") is not None and journal.get("sourceManifestSha256") == pins["sourceManifestSha256"] and
             journal.get("importPlanSha256") == pins["importPlanSha256"] and
             journal.get("pid") > 1,
             "NATIVE_RECOVERY_JOURNAL_NOT_RECOVERABLE", "execution-journal.json",
             "Expected the unchanged running journal for this native plan")
    _require(not inside(transaction, "execution-result.json").exists(),
             "NATIVE_RECOVERY_RESULT_ALREADY_EXISTS", "execution-result.json", "An execution result already exists")

    entrypoints = run.get("entrypoint_identities")
    run_identity = [row for row in (entrypoints if isinstance(entrypoints, list) else [])
                    if isinstance(row, dict) and row.get("path") == producer["entrypointPath"] and
                    row.get("sha256") == producer["entrypointSha256"]]
    command = run.get("command")
    run_dir = safe(run["run_dir"]) if isinstance(run.get("run_dir"), str) else None
    _require(run.get("tool_id") == producer["toolId"] and run.get("status") == "partial" and
             type(run.get("exit_code")) is int and run["exit_code"] != 0 and run.get("capture_complete") is True and
             len(run_identity) == 1 and run_dir == run_path.parent and isinstance(command, list) and
             command and command[0] == producer["entrypointPath"] and
             _option(command, "--out") == str(transaction) and _option(command, "--candidate") == plan.get("source") and
             _option(command, "--expected-manifest") == pins["sourceManifestSha256"] and
             _option(command, "--editor-path") == plan.get("editor") and "--execute" in command,
             "NATIVE_RECOVERY_OUTER_PRODUCER_MISMATCH", "runReceipt", "Outer run receipt does not bind this transaction")
    _require(type(run.get("process_group")) is int and run["process_group"] > 1,
             "NATIVE_RECOVERY_PROCESS_IDENTITY_INVALID", "runReceipt.process_group", "Outer producer lacks a process group")
    _assert_pid_and_group_absent(journal["pid"], run["process_group"])

    project_manifest = load(artifacts["projectManifest"][1], max_nodes=8_000_000, max_depth=96)
    progress_raw = artifacts["nativeProgress"][1]
    progress_doc = load(progress_raw, max_nodes=10000, max_depth=32)
    _require(isinstance(project_manifest, dict) and isinstance(progress_doc, dict),
             "NATIVE_RECOVERY_INPUT_INVALID", "UnityProject", "Project manifest and native progress must be JSON objects")
    _require(sha(artifacts["projectManifest"][1]) == pins["sourceManifestSha256"],
             "NATIVE_RECOVERY_PROJECT_MANIFEST_MISMATCH", "UnityProject/manifest.json",
             "Copied project manifest bytes differ from the frozen native source manifest pin")
    manifest_files = project_manifest.get("files")
    import_plan_rows = [row for row in (manifest_files if isinstance(manifest_files, list) else [])
                        if isinstance(row, dict) and isinstance(row.get("path"), str) and
                        row["path"].endswith("/Editor/Conversion/import-plan.json")]
    _require(len(import_plan_rows) == 1 and import_plan_rows[0].get("sha256") == pins["importPlanSha256"],
             "NATIVE_RECOVERY_IMPORT_PLAN_PIN_MISMATCH", "UnityProject/manifest.json",
             "Copied project manifest does not pin exactly one matching import plan")
    copied_import_plan = inside(transaction, "UnityProject/" + import_plan_rows[0]["path"])
    copied_import_plan_raw = read(copied_import_plan, max_bytes=128 * 1024 * 1024)
    _require(sha(copied_import_plan_raw) == pins["importPlanSha256"],
             "NATIVE_RECOVERY_IMPORT_PLAN_PIN_MISMATCH", str(copied_import_plan),
             "Copied import plan bytes differ from the execution plan pin")
    progress = validate_progress(progress_doc, pins["importPlanSha256"])

    request_sha = sha(request_raw)
    request_output = safe(output)
    out = new_output(request_output, [request_path, transaction, run_path])
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "schemaVersion": 1,
        "status": "partial",
        "promotionEligible": False,
        "recoveryProducer": {"toolId": "grea", "toolVersion": __version__,
                             "moduleSha256": sha(read(Path(__file__)))},
        "recoveredAtUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "requestSha256": request_sha,
        "transactionRoot": str(transaction),
        "producer": {
            "toolId": producer["toolId"], "toolVersion": plan["toolVersion"],
            "launcherSha256": plan["launcherSha256"], "entrypointPath": producer["entrypointPath"],
            "entrypointSha256": producer["entrypointSha256"],
        },
        "pins": {
            "nativePlanSha256": pins["nativePlanSha256"], "planIdentitySha256": pins["planIdentitySha256"],
            "executionJournalSha256": pins["executionJournalSha256"],
            "sourceManifestSha256": pins["sourceManifestSha256"], "importPlanSha256": pins["importPlanSha256"],
            "runReceiptPath": str(run_path), "runReceiptSha256": pins["runReceiptSha256"],
            "projectManifestSha256": pins["projectManifestSha256"], "nativeProgressSha256": pins["nativeProgressSha256"],
            "importLogSha256": pins["importLogSha256"], "consoleLogSha256": pins["consoleLogSha256"],
        },
        "process": {
            "recordedUnityPid": journal["pid"], "recordedProcessGroup": run["process_group"],
            "pidAndGroupAbsentAtRecovery": True, "unityProcessExited": True,
            "unityExitCode": None, "unityExitCodeStatus": "not-recorded-before-host-exit",
            "outerProcessExitCode": run["exit_code"], "outerProcessStatus": run["status"],
        },
        "importer": {
            "journalStatusAtRecovery": journal["status"],
            "journalLeftUntouched": True,
            "progress": progress,
            "projectManifestStatus": project_manifest.get("status"),
            "candidateManifestSha256": pins["sourceManifestSha256"],
            "originalSourceManifestSha256": project_manifest.get("sourceManifestSha256"),
        },
        "verification": {"status": "not_completed_by_launcher", "rerun": False,
                          "acceptance": "unknown", "promotionEligible": False},
        "evidence": [
            {"role": "native-plan", "path": "native-plan.json", "sha256": pins["nativePlanSha256"],
             "bytes": len(plan_raw)},
            {"role": "plan-identity", "path": "plan-identity.json", "sha256": pins["planIdentitySha256"],
             "bytes": len(identity_raw)},
            {"role": "execution-journal", "path": "execution-journal.json", "sha256": pins["executionJournalSha256"],
             "bytes": len(journal_raw)},
            {"role": "outer-run-receipt", "path": str(run_path), "sha256": pins["runReceiptSha256"],
             "bytes": len(run_raw)},
            *[{"role": key, "path": _ARTIFACTS[key], "sha256": pins[key + "Sha256"], "bytes": len(raw)}
              for key, (_, raw) in artifacts.items()],
        ],
    }
    write_json(out / "recovery-request.json", request)
    write_json(out / "recovery-receipt.json", receipt)
    manifest = {"schema": "monkey-native-execution-recovery-files/1", "requestSha256": request_sha,
                "files": [{"path": path.name, "sha256": sha(read(path)), "bytes": path.stat().st_size}
                          for path in (out / "recovery-request.json", out / "recovery-receipt.json")]}
    write_json(out / "recovery-manifest.json", manifest)
    return dict(status="partial", receipt=str(out / "recovery-receipt.json"), manifest=str(out / "recovery-manifest.json"),
                unityExitCode=None, outerProcessExitCode=run["exit_code"], verification="not_completed_by_launcher",
                promotionEligible=False)
