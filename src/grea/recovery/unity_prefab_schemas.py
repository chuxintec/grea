"""Public offline API for bounded built-in Unity TypeTree schema readback."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from .io import new_output, safe, write_json


MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_PROVIDER_BYTES = 256 * 1024 * 1024
MAX_WANTED_OBJECTS = 32
MAX_BUDGET_SECONDS = 600
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UNITY_VERSIONS = {"2021.3.30f1"}


class BuiltinSchemaError(ValueError):
    """Request evidence is incomplete or contradicts the pinned source."""


def _hash_file(path: Path, max_bytes: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            if size > max_bytes:
                raise BuiltinSchemaError(f"File exceeds byte budget: {path}")
            digest.update(block)
    return digest.hexdigest(), size


def validate_wanted_objects(wanted_objects: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate and copy an exact, bounded object identity selection."""
    if not isinstance(wanted_objects, Sequence) or isinstance(wanted_objects, (str, bytes)):
        raise BuiltinSchemaError("wanted_objects must be a bounded sequence")
    if not 1 <= len(wanted_objects) <= MAX_WANTED_OBJECTS:
        raise BuiltinSchemaError(f"wanted_objects count must be in 1..{MAX_WANTED_OBJECTS}")
    normalized = []
    seen = set()
    for index, row in enumerate(wanted_objects):
        if not isinstance(row, Mapping):
            raise BuiltinSchemaError(f"wanted_objects[{index}] must be an object")
        serialized_file = row.get("serializedFile")
        path_id = row.get("pathId")
        object_type = row.get("type")
        raw_sha = row.get("rawSha256")
        if not isinstance(serialized_file, str) or not serialized_file.strip() or len(serialized_file) > 256:
            raise BuiltinSchemaError(f"wanted_objects[{index}].serializedFile is invalid")
        if not isinstance(path_id, (str, int)) or isinstance(path_id, bool):
            raise BuiltinSchemaError(f"wanted_objects[{index}].pathId must be a signed 64-bit integer or decimal string")
        try:
            path_number = int(path_id)
        except (TypeError, ValueError) as exc:
            raise BuiltinSchemaError(f"wanted_objects[{index}].pathId is not decimal") from exc
        if str(path_number) != str(path_id) or not -(1 << 63) <= path_number < (1 << 63):
            raise BuiltinSchemaError(f"wanted_objects[{index}].pathId is not canonical signed 64-bit decimal")
        if not isinstance(object_type, str) or not object_type.strip() or len(object_type) > 128:
            raise BuiltinSchemaError(f"wanted_objects[{index}].type is invalid")
        if object_type == "MonoBehaviour":
            raise BuiltinSchemaError("MonoBehaviour uses the existing exact schema path and is excluded")
        if not isinstance(raw_sha, str) or not _SHA256.fullmatch(raw_sha):
            raise BuiltinSchemaError(f"wanted_objects[{index}].rawSha256 must be lowercase SHA256")
        serialized_sha = row.get("serializedFileSha256")
        if serialized_sha is not None and (not isinstance(serialized_sha, str) or not _SHA256.fullmatch(serialized_sha)):
            raise BuiltinSchemaError(f"wanted_objects[{index}].serializedFileSha256 must be lowercase SHA256")
        key = (serialized_file, str(path_number), object_type)
        if key in seen:
            raise BuiltinSchemaError(f"duplicate wanted object identity at index {index}")
        seen.add(key)
        item = {"serializedFile": serialized_file, "pathId": str(path_number), "type": object_type,
                "rawSha256": raw_sha}
        if serialized_sha is not None:
            item["serializedFileSha256"] = serialized_sha
        normalized.append(item)
    return normalized


def _validate_report(report: dict, wanted: list[dict], source_sha: str) -> None:
    if report.get("schemaVersion") != 1 or report.get("status") != "schemas_read":
        raise BuiltinSchemaError("Worker did not return a completed schema read")
    if report.get("source", {}).get("sha256") != source_sha or report.get("sourceCodeExecuted") is not False:
        raise BuiltinSchemaError("Worker result source identity or execution declaration differs")
    if report.get("provider") != {"name": "UnityPy", "version": "1.25.3"}:
        raise BuiltinSchemaError("Worker provider identity differs from pinned UnityPy 1.25.3")
    if "not asserted equivalent" not in report.get("schemaReadRelation", ""):
        raise BuiltinSchemaError("Worker did not distinguish this schema read from prior cache evidence")
    rows = report.get("objects")
    if not isinstance(rows, list) or len(rows) != len(wanted):
        raise BuiltinSchemaError("Worker result object count differs from exact selection")
    expected = {(row["serializedFile"], row["pathId"], row["type"], row["rawSha256"]) for row in wanted}
    expected_serialized = {(row["serializedFile"], row.get("serializedFileSha256")) for row in wanted
                           if row.get("serializedFileSha256") is not None}
    observed = set()
    observed_serialized = set()
    for row in rows:
        identity = row.get("identity", {})
        if identity.get("sourceSha256") != source_sha or identity.get("unityVersion") not in _UNITY_VERSIONS:
            raise BuiltinSchemaError("Worker object identity source or Unity version differs")
        observed.add((identity.get("serializedFile"), identity.get("pathId"), identity.get("type"), identity.get("rawSha256")))
        observed_serialized.add((identity.get("serializedFile"), identity.get("serializedFileSha256")))
        for schema_key, hash_key in (("schemaNode", "schemaNodeSha256"), ("fullSchema", "fullSchemaSha256")):
            value = row.get(schema_key)
            digest = row.get(hash_key)
            if schema_key == "schemaNode" and not isinstance(value, dict):
                raise BuiltinSchemaError("Worker schemaNode is malformed")
            if schema_key == "fullSchema" and not isinstance(value, list):
                raise BuiltinSchemaError("Worker fullSchema is malformed")
            actual = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if not isinstance(digest, str) or actual != digest:
                raise BuiltinSchemaError(f"Worker {hash_key} does not match schema payload")
    if observed != expected:
        raise BuiltinSchemaError("Worker result identities differ from requested exact tuples")
    if any(item not in observed_serialized for item in expected_serialized):
        raise BuiltinSchemaError("Worker serialized-file SHA256 differs from caller pin")


def extract_builtin_schemas(
    source_path: str | Path,
    source_sha256: str,
    provider_python: str | Path,
    wanted_objects: Sequence[Mapping[str, Any]],
    out: str | Path,
    *,
    budget_seconds: int = 120,
    prior_reader_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Read exact built-in TypeTrees in a fresh, isolated UnityPy 1.25.3 process.

    This operation never runs source assemblies or game methods. It accepts only
    Unity 2021.3.30f1, non-MonoBehaviour objects, and a fresh output directory.
    """
    if not isinstance(source_sha256, str) or not _SHA256.fullmatch(source_sha256):
        raise BuiltinSchemaError("source_sha256 must be lowercase SHA256")
    if isinstance(budget_seconds, bool) or not isinstance(budget_seconds, int) or not 1 <= budget_seconds <= MAX_BUDGET_SECONDS:
        raise BuiltinSchemaError(f"budget_seconds must be in 1..{MAX_BUDGET_SECONDS}")
    wanted = validate_wanted_objects(wanted_objects)
    if prior_reader_evidence is not None and not isinstance(prior_reader_evidence, Mapping):
        raise BuiltinSchemaError("prior_reader_evidence must be an object when provided")

    source = safe(source_path)
    if not source.is_file():
        raise BuiltinSchemaError("source_path must identify one existing bundle file")
    actual_source_sha, source_bytes = _hash_file(source, MAX_SOURCE_BYTES)
    if actual_source_sha != source_sha256:
        raise BuiltinSchemaError("source bundle SHA256 does not match the requested pin")
    requested_python = Path(provider_python).absolute()
    try:
        python_path = safe(requested_python.resolve(strict=True))
    except OSError as exc:
        raise BuiltinSchemaError("provider_python must resolve to an existing Python executable") from exc
    if not python_path.is_file():
        raise BuiltinSchemaError("provider_python must identify an existing Python executable")
    provider_sha, provider_bytes = _hash_file(python_path, MAX_PROVIDER_BYTES)
    worker = Path(__file__).with_name("sources") / "unity_prefab_schema_worker.py"
    if not worker.is_file():
        raise BuiltinSchemaError("schema worker module is missing")

    output = new_output(out, [source, python_path])
    job = {
        "schemaVersion": 1,
        "sourcePath": str(source),
        "sourceSha256": source_sha256,
        "wantedObjects": wanted,
        "supportedUnityVersions": sorted(_UNITY_VERSIONS),
    }
    write_json(output / "job.json", job)
    receipt: dict[str, Any] = {
        "schemaVersion": 1,
        "status": "started",
        "source": {"path": str(source), "bytes": source_bytes, "sha256": source_sha256},
        "providerPython": {"requestedPath": str(requested_python), "resolvedPath": str(python_path),
                            "bytes": provider_bytes, "sha256": provider_sha},
        "budgetSeconds": budget_seconds,
        "priorReaderEvidence": dict(prior_reader_evidence or {"status": "not_supplied"}),
        "schemaReadRelation": "fresh pinned-bundle TypeTree read; not asserted equivalent to prior cached reader output",
        "sourceCodeExecuted": False,
        "processExited": False,
    }
    write_json(output / "receipt.json", receipt)
    result_path = output / "worker-result.json"
    started = time.monotonic()
    with (output / "provider.log").open("wb") as log:
        process = subprocess.Popen(
            [str(requested_python), "-I", "-B", str(worker), "--extract-builtin-schemas", str(output / "job.json"), str(result_path)],
            cwd=output,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        receipt["pid"] = process.pid
        try:
            receipt["exitCode"] = process.wait(timeout=budget_seconds)
        except subprocess.TimeoutExpired:
            receipt["timedOut"] = True
            receipt["status"] = "timeout"
            process.terminate()
            try:
                receipt["exitCode"] = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    receipt["exitCode"] = process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    receipt["status"] = "timeout_process_not_exited"
        receipt["processExited"] = process.poll() is not None
    receipt["elapsedSeconds"] = round(time.monotonic() - started, 3)

    try:
        after_sha, after_bytes = _hash_file(source, MAX_SOURCE_BYTES)
        receipt["sourceUnchanged"] = after_sha == source_sha256 and after_bytes == source_bytes
    except (OSError, BuiltinSchemaError):
        receipt["sourceUnchanged"] = False
    if result_path.is_file():
        if result_path.stat().st_size > 16 * 1024 * 1024:
            receipt["workerError"] = {"type": "ValueError", "message": "Worker result exceeds byte budget"}
        else:
            result_raw = result_path.read_bytes()
            receipt["workerResultSha256"] = hashlib.sha256(result_raw).hexdigest()
            try:
                report = json.loads(result_raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                report = None
            if isinstance(report, dict) and report.get("status") == "failed":
                receipt["workerError"] = report.get("error")
            elif isinstance(report, dict) and process.returncode == 0 and receipt["processExited"]:
                try:
                    _validate_report(report, wanted, source_sha256)
                    receipt["status"] = "schemas_read"
                    receipt["objects"] = report["objects"]
                    receipt["provider"] = report["provider"]
                except BuiltinSchemaError as exc:
                    receipt["status"] = "worker_result_rejected"
                    receipt["workerError"] = {"type": type(exc).__name__, "message": str(exc)}
            elif report is None:
                receipt["workerError"] = {"type": "ValueError", "message": "Worker result is not valid JSON"}
    elif receipt.get("status") == "started":
        receipt["workerError"] = {"type": "FileNotFoundError", "message": "Worker did not produce a result file"}

    if not receipt["sourceUnchanged"]:
        receipt["status"] = "source_changed"
    elif receipt.get("timedOut") and receipt["status"] != "timeout_process_not_exited":
        receipt["status"] = "timeout"
    elif receipt["status"] == "started":
        receipt["status"] = "worker_failed"
    write_json(output / "receipt.json", receipt)
    return receipt
