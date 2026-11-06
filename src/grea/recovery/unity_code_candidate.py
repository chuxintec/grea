"""Create isolated C# candidates from exact, hash-bound Mono decompiler reports.

This stage copies ILSpy source as a draft. It never loads the original assembly,
and it never promotes recovered source into Unity Assets or an implemented state.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .io import load, new_output, safe, write_json
from .sources.compiled import fail
from .unity_code_il import parse_csharp


MAX_REPORT_BYTES = 32 * 1024 * 1024
MAX_SOURCE_FILE_BYTES = 16 * 1024 * 1024
MAX_CANDIDATE_BYTES = 256 * 1024 * 1024
MAX_CANDIDATE_FILES = 100_000


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_exact(path: Path, expected_hash: str, max_bytes: int) -> bytes:
    path = safe(path)
    if not path.is_file() or path.is_symlink():
        fail("UNITY_CANDIDATE_INPUT_TYPE", path.name, "Expected an existing regular non-symlink file")
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        fail("UNITY_CANDIDATE_FILE_BUDGET", path.name, "Input exceeds the candidate stage byte budget")
    if _hash(raw) != expected_hash:
        fail("UNITY_CANDIDATE_INPUT_CHANGED", path.name, "File hash differs from its bound source report")
    return raw


def _relative_output(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        fail("UNITY_CANDIDATE_UNSAFE_PATH", str(relative), "Expected a non-empty relative output path")
    path = safe(root / relative)
    if not path.is_relative_to(root):
        fail("UNITY_CANDIDATE_UNSAFE_PATH", relative, "Source report path escapes its report directory")
    return path


def _source_report(path: str | Path, expected_sha256: str) -> tuple[Path, bytes, dict[str, Any]]:
    report_path = safe(path)
    if not report_path.is_file() or report_path.is_symlink():
        fail("UNITY_CANDIDATE_REPORT_TYPE", report_path.name, "Expected a regular source report file")
    raw = report_path.read_bytes()
    if len(raw) > MAX_REPORT_BYTES:
        fail("UNITY_CANDIDATE_REPORT_BUDGET", report_path.name, "Source report exceeds the report byte budget")
    if _hash(raw) != expected_sha256:
        fail("UNITY_CANDIDATE_REPORT_HASH", report_path.name, "Source report does not match the expected SHA-256")
    try:
        report = load(raw, max_nodes=2_000_000, max_depth=96)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        fail("UNITY_CANDIDATE_REPORT_INVALID", report_path.name, f"Source report is not valid bounded JSON ({type(error).__name__})")
    if not isinstance(report, dict) or report.get("schemaVersion") != 1:
        fail("UNITY_CANDIDATE_REPORT_SCHEMA", report_path.name, "Expected unity-code-source schema version 1")
    if report.get("sourceCodeExecuted") is not False:
        fail("UNITY_CANDIDATE_SOURCE_EXECUTION", report_path.name, "Source report does not affirm non-execution")
    if not isinstance(report.get("source"), dict) or report["source"].get("family") != "mono":
        fail("UNITY_CANDIDATE_FAMILY", report_path.name, "Candidate generation accepts only Mono source reports")
    source_row = report["source"]
    outputs = report.get("outputs")
    if not isinstance(outputs, list):
        fail("UNITY_CANDIDATE_REPORT_SHAPE", report_path.name, "Source report lacks output inventory")
    snapshot = next((row for row in outputs if isinstance(row, dict)
                     and row.get("role") == "exact-source-snapshot"), None)
    if (not snapshot or snapshot.get("sha256") != source_row.get("sha256")
            or snapshot.get("bytes") != source_row.get("bytes")):
        fail("UNITY_CANDIDATE_SOURCE_BINDING", report_path.name, "Report lacks an exact-source snapshot bound to the Mono input hash")
    snapshot_path = _relative_output(report_path.parent, snapshot.get("path"))
    _read_exact(snapshot_path, source_row["sha256"], 64 * 1024 * 1024)
    if report.get("status") not in ("decompiled_body_not_verified", "metadata_only"):
        fail("UNITY_CANDIDATE_REPORT_STATUS", report_path.name, "Source report is not an accepted static-decompilation result")
    provider = report.get("provider")
    if not isinstance(provider, dict) or provider.get("staticAnalysisOnly") is not True or provider.get("sourceExecution") is not False:
        fail("UNITY_CANDIDATE_PROVIDER", report_path.name, "Report lacks a static-only provider identity")
    run = provider.get("run")
    if not isinstance(run, dict) or run.get("exitCode") != 0 or run.get("timedOut") is not False:
        fail("UNITY_CANDIDATE_PROVIDER_STATUS", report_path.name, "Provider did not complete successfully")
    return report_path, raw, report


def prepare_candidate(source_report: str | Path, output: str | Path, *,
                      expected_report_sha256: str,
                      method_ids: list[str] | None = None) -> dict[str, Any]:
    """Copy exact decompiled C# files into an isolated draft candidate tree.

    Files are copied at file granularity, so all types/methods in a selected
    decompiler source file remain present. A candidate is marked ``closed`` only
    when every included method has a body and every observed call resolves to an
    included method; it remains a draft because original IL parity is unverified.
    """
    report_path, report_raw, report = _source_report(source_report, expected_report_sha256)
    methods = report.get("methods")
    outputs = report.get("outputs")
    if not isinstance(methods, list) or not isinstance(outputs, list):
        fail("UNITY_CANDIDATE_REPORT_SHAPE", report_path.name, "Source report lacks methods or output inventory")
    if method_ids is not None and (not isinstance(method_ids, list) or not method_ids or any(not isinstance(x, str) for x in method_ids)):
        fail("UNITY_CANDIDATE_METHOD_SELECTION", "$", "method_ids must be a non-empty list of method identities")
    method_by_id = {row.get("methodId"): row for row in methods if isinstance(row, dict) and isinstance(row.get("methodId"), str)}
    if len(method_by_id) != len(methods):
        fail("UNITY_CANDIDATE_REPORT_METHODS", report_path.name, "Method identities are missing or duplicated")
    if method_ids is not None and any(method_id not in method_by_id for method_id in method_ids):
        fail("UNITY_CANDIDATE_METHOD_UNKNOWN", "$", "Selection contains an identity absent from the exact source report")

    selected_methods = [method_by_id[mid] for mid in method_ids] if method_ids is not None else methods
    source_paths = sorted({
        row.get("sourceEvidence", {}).get("path") for row in selected_methods
        if isinstance(row.get("sourceEvidence"), dict) and isinstance(row["sourceEvidence"].get("path"), str)
    })
    if not source_paths:
        fail("UNITY_CANDIDATE_NO_METHOD_SOURCE", report_path.name, "No decompiled C# source is bound to the selected methods")
    output_rows = {row.get("path"): row for row in outputs if isinstance(row, dict) and isinstance(row.get("path"), str)}
    source_rows = {}
    for relative in source_paths:
        row = output_rows.get(relative)
        if not row or row.get("role") != "decompiled-source" or not relative.endswith(".cs"):
            fail("UNITY_CANDIDATE_SOURCE_INVENTORY", relative, "Selected method source is not a decompiled C# file in the report inventory")
        if not isinstance(row.get("sha256"), str) or type(row.get("bytes")) is not int:
            fail("UNITY_CANDIDATE_SOURCE_INVENTORY", relative, "Source report lacks exact file identity")
        source_rows[relative] = row

    output_path = new_output(output, [report_path])
    draft_root = output_path / "CandidateDraft" / "CSharp"
    draft_root.mkdir(parents=True, exist_ok=False)
    copied = []
    total_bytes = 0
    for relative, row in source_rows.items():
        source_path = _relative_output(report_path.parent, relative)
        raw = _read_exact(source_path, row["sha256"], MAX_SOURCE_FILE_BYTES)
        if len(raw) != row["bytes"]:
            fail("UNITY_CANDIDATE_SOURCE_SIZE", relative, "Source size differs from report inventory")
        try:
            parsed = parse_csharp(raw.decode("utf-8-sig"), relative, row["sha256"])
        except (UnicodeDecodeError, ValueError) as error:
            fail("UNITY_CANDIDATE_SOURCE_PARSE", relative, f"Hash-bound source did not parse consistently ({type(error).__name__})")
        reported_for_file = [method for method in methods if isinstance(method, dict)
                             and isinstance(method.get("sourceEvidence"), dict)
                             and method["sourceEvidence"].get("path") == relative]
        parsed_by_id = {method["methodId"]: method for method in parsed["methods"]}
        for method in reported_for_file:
            actual = parsed_by_id.get(method.get("methodId"))
            if actual is None or actual.get("signature") != method.get("signature"):
                fail("UNITY_CANDIDATE_METHOD_BINDING", relative, "Reported method identity/signature differs from the hash-bound C# source")
            actual_body = actual.get("bodyEvidence")
            reported_body = method.get("bodyEvidence")
            if (actual_body is None) != (reported_body is None):
                fail("UNITY_CANDIDATE_BODY_BINDING", relative, "Reported body availability differs from the hash-bound C# source")
            if actual_body and (actual_body.get("sha256") != reported_body.get("sha256")
                                or actual_body.get("bytes") != reported_body.get("bytes")):
                fail("UNITY_CANDIDATE_BODY_BINDING", relative, "Reported body hash differs from the hash-bound C# source")
        total_bytes += len(raw)
        if len(copied) >= MAX_CANDIDATE_FILES or total_bytes > MAX_CANDIDATE_BYTES:
            fail("UNITY_CANDIDATE_OUTPUT_BUDGET", relative, "Candidate source inventory exceeds its size budget")
        destination = draft_root / relative.removeprefix("SourceRecovery/Decompiled/Mono/")
        if not destination.resolve().is_relative_to(draft_root.resolve()):
            fail("UNITY_CANDIDATE_UNSAFE_PATH", relative, "Candidate path escapes isolated draft directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        copied.append({"sourcePath": relative, "candidatePath": destination.relative_to(output_path).as_posix(),
                       "sha256": _hash(raw), "bytes": len(raw), "sourceReportSha256": expected_report_sha256})

    included_ids = {row["methodId"] for row in selected_methods}
    selected_source_methods = [row for row in methods
                               if isinstance(row.get("sourceEvidence"), dict)
                               and row["sourceEvidence"].get("path") in source_paths]
    # File-level copying is intentionally explicit: selecting any method includes
    # every declaration from that same source file, including methods not selected.
    included_ids = {row["methodId"] for row in selected_source_methods}
    missing_body = [row["methodId"] for row in selected_source_methods if not isinstance(row.get("bodyEvidence"), dict)]
    unresolved = []
    for row in selected_source_methods:
        for call in row.get("calls", []):
            if not isinstance(call, dict) or call.get("resolution") != "exact-symbol-unique" or call.get("resolvedMethodId") not in included_ids:
                unresolved.append({"methodId": row["methodId"], "symbol": call.get("symbol") if isinstance(call, dict) else None})
    source_diagnostics = report.get("diagnostics", [])
    blocking_diagnostics = [row for row in source_diagnostics if isinstance(row, dict)
                            and (row.get("location") in source_paths
                                 or row.get("code") in {"ILSPY_FAILED", "ILSPY_TIMEOUT", "ILSPY_NO_TYPES_PARSED"})]
    incomplete = bool(missing_body or unresolved or blocking_diagnostics)
    candidate_report = {
        "schemaVersion": 1,
        "kind": "unity-mono-csharp-candidate",
        "status": "draft_incomplete" if incomplete else "draft_closed",
        "sourceCodeExecuted": False,
        "originalAssemblyExecuted": False,
        "implementedMethods": 0,
        "sourceReport": {"path": str(report_path), "sha256": expected_report_sha256,
                         "sourceSha256": report["source"].get("sha256"),
                         "provider": report["provider"]},
        "candidateFiles": copied,
        "methods": [{"methodId": row["methodId"], "declaringType": row["declaringType"],
                     "name": row["name"], "status": row.get("status"),
                     "bodyEvidence": row.get("bodyEvidence")} for row in selected_source_methods],
        "closure": {"closedForObservedCalls": not unresolved,
                    "allMethodsHaveBodies": not missing_body,
                    "unresolvedCalls": unresolved,
                    "methodsWithoutBodies": missing_body,
                    "sourceDiagnostics": source_diagnostics,
                    "blockingDiagnostics": blocking_diagnostics},
        "limitations": ["Candidate C# is copied from static ILSpy output and has not been verified against original IL.",
                        "Even draft_closed means only that parsed in-inventory methods and observed calls close; it does not prove external dependency or behavioral parity."],
    }
    write_json(output_path / "unity-code-candidate.json", candidate_report)
    return {"status": candidate_report["status"], "report": str(output_path / "unity-code-candidate.json"),
            "candidateFiles": copied, "summary": {"methods": len(selected_source_methods),
            "methodsWithoutBodies": len(missing_body), "unresolvedCalls": len(unresolved), "implementedMethods": 0},
            "sourceCodeExecuted": False, "reportSha256": _hash((output_path / "unity-code-candidate.json").read_bytes())}
