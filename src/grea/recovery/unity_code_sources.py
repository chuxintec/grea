"""Evidence-first static recovery of Unity Mono and IL2CPP-WASM code sources.

Original assemblies and WASM are read as bytes only. Mono source uses the
installed ILSpy provider to decompile metadata and method bodies; IL2CPP-WASM
accepts only hash-pinned metadata/method maps and never treats pseudocode as
implemented C#.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from .io import encoded, load, new_output, safe, write_json
from .sources.compiled import fail
from .unity_code_il import parse_csharp, parse_method_map


MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_EVIDENCE_BYTES = 64 * 1024 * 1024
MAX_DECOMPILED_BYTES = 256 * 1024 * 1024
MAX_DECOMPILED_FILES = 100_000
MAX_CSHARP_PARSE_BYTES = 16 * 1024 * 1024
MAX_REPORT_BYTES = 32 * 1024 * 1024
MAX_PROVIDER_LOG_BYTES = 4 * 1024 * 1024
PROVIDER_TIMEOUT_SECONDS = 1200
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _hash_file(path: Path, limit: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > limit:
                fail("UNITY_CODE_FILE_BUDGET", str(path.name), "Input exceeds the module byte budget")
            digest.update(block)
    return digest.hexdigest(), total


def _input_path(path: str | Path | None, name: str, expected_sha256: str | None,
                limit: int = MAX_EVIDENCE_BYTES) -> tuple[Path | None, dict[str, Any] | None, bytes | None]:
    if path is None:
        if expected_sha256 is not None:
            fail("UNITY_CODE_EXPECTED_WITHOUT_INPUT", name, "Expected hash requires an input file")
        return None, None, None
    if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
        fail("UNITY_CODE_EXPECTED_SHA", name, "An exact lowercase SHA-256 is required for each evidence input")
    resolved = safe(path)
    if not resolved.is_file():
        fail("UNITY_CODE_INPUT_TYPE", name, "Expected an existing regular file")
    actual, size = _hash_file(resolved, limit)
    if actual != expected_sha256:
        fail("UNITY_CODE_INPUT_CHANGED", name, "Input SHA-256 differs from the supplied identity")
    raw = resolved.read_bytes()
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != actual:
        fail("UNITY_CODE_INPUT_CHANGED", name, "Input changed between streaming hash and bounded read")
    return resolved, {"path": str(resolved), "sha256": actual, "bytes": size}, raw


def _validate_pe_cli(raw: bytes) -> dict[str, Any] | None:
    """Return PE/CLI facts, or None when bytes are not a managed PE assembly."""
    if len(raw) < 0x40 or raw[:2] != b"MZ":
        return None
    pe = int.from_bytes(raw[0x3C:0x40], "little")
    if pe < 0x40 or pe + 24 > len(raw) or raw[pe:pe + 4] != b"PE\0\0":
        return None
    section_count = int.from_bytes(raw[pe + 6:pe + 8], "little")
    optional_size = int.from_bytes(raw[pe + 20:pe + 22], "little")
    optional = pe + 24
    if section_count > 4096 or optional_size < 96 or optional + optional_size > len(raw):
        return None
    magic = int.from_bytes(raw[optional:optional + 2], "little")
    directory_offset = 96 if magic == 0x10B else 112 if magic == 0x20B else None
    if directory_offset is None or directory_offset + 15 * 8 > optional_size:
        return None
    cli_rva = int.from_bytes(raw[optional + directory_offset + 14 * 8:optional + directory_offset + 14 * 8 + 4], "little")
    cli_size = int.from_bytes(raw[optional + directory_offset + 14 * 8 + 4:optional + directory_offset + 14 * 8 + 8], "little")
    if not cli_rva or cli_size < 0x48:
        return None
    section_table = optional + optional_size
    if section_table + section_count * 40 > len(raw):
        return None
    cli_offset = None
    for index in range(section_count):
        row = section_table + index * 40
        virtual_size = int.from_bytes(raw[row + 8:row + 12], "little")
        virtual_address = int.from_bytes(raw[row + 12:row + 16], "little")
        raw_size = int.from_bytes(raw[row + 16:row + 20], "little")
        raw_offset = int.from_bytes(raw[row + 20:row + 24], "little")
        span = max(virtual_size, raw_size)
        if virtual_address <= cli_rva < virtual_address + span:
            cli_offset = raw_offset + (cli_rva - virtual_address)
            break
    if cli_offset is None or cli_offset + 0x48 > len(raw):
        return None
    header_size = int.from_bytes(raw[cli_offset:cli_offset + 4], "little")
    metadata_rva = int.from_bytes(raw[cli_offset + 8:cli_offset + 12], "little")
    metadata_size = int.from_bytes(raw[cli_offset + 12:cli_offset + 16], "little")
    flags = int.from_bytes(raw[cli_offset + 16:cli_offset + 20], "little")
    if header_size < 0x48 or not metadata_rva or not metadata_size:
        return None
    return {"peMagic": hex(magic), "cliHeaderSize": header_size, "cliFlags": flags,
            "metadataRva": metadata_rva, "metadataBytes": metadata_size}


def _provider_info(provider: str | Path | None) -> tuple[Path, dict[str, Any]]:
    configured = provider or os.environ.get("MONKEY_ILSPY_PROVIDER")
    if not configured:
        fail("UNITY_CODE_PROVIDER_REQUIRED", "$", "Pass provider explicitly or set MONKEY_ILSPY_PROVIDER")
    command = safe(configured)
    if not command.is_file() or not os.access(command, os.X_OK):
        fail("UNITY_CODE_PROVIDER_UNAVAILABLE", str(command), "Configured static decompiler is not executable")
    wrapper_sha, wrapper_bytes = _hash_file(command, 16 * 1024 * 1024)
    try:
        version = subprocess.run([str(command), "--version"], capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        fail("UNITY_CODE_PROVIDER_PROBE", str(command), f"Static decompiler version probe failed ({type(error).__name__})")
    version_text = (version.stdout + version.stderr).decode("utf-8", "replace").strip()
    if version.returncode != 0 or "ilspycmd" not in version_text.casefold():
        fail("UNITY_CODE_PROVIDER_IDENTITY", str(command), "Provider did not identify as ILSpy")
    bin_identity = None
    return command, {"name": "ILSpy", "version": version_text, "commandPath": str(command),
                     "commandSha256": wrapper_sha, "commandBytes": wrapper_bytes,
                     "providerBinary": bin_identity, "staticAnalysisOnly": True,
                     "sourceExecution": False}


def _run_ilspy(source: Path, output: Path, provider: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    decompiled = output / "SourceRecovery" / "Decompiled" / "Mono"
    decompiled.mkdir(parents=True, exist_ok=False)
    log = output / "provider-ilspy.log"
    command = [str(provider), "--disable-updatecheck", "--nested-directories", "-p", "-o", str(decompiled), str(source)]
    try:
        with log.open("xb") as stream:
            completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                       timeout=PROVIDER_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        if log.exists():
            log_sha, log_bytes = _hash_file(log, MAX_PROVIDER_LOG_BYTES)
        else:
            log_sha, log_bytes = None, 0
        return {"command": command, "exitCode": None, "timedOut": True,
                "logSha256": log_sha, "logBytes": log_bytes}, []
    except OSError as error:
        fail("UNITY_CODE_PROVIDER_RUN", str(provider), f"Could not start ILSpy ({type(error).__name__})")
    log_sha, log_bytes = _hash_file(log, MAX_PROVIDER_LOG_BYTES)
    if completed.returncode != 0:
        return {"command": command, "exitCode": completed.returncode, "timedOut": False,
                "logSha256": log_sha, "logBytes": log_bytes}, []
    files = []
    total = 0
    for path in sorted(decompiled.rglob("*")):
        if path.is_symlink():
            fail("UNITY_CODE_PROVIDER_SYMLINK", path.relative_to(output).as_posix(), "Decompiler output may not contain symlinks")
        if not path.is_file():
            continue
        relative = path.relative_to(output).as_posix()
        digest, size = _hash_file(path, MAX_DECOMPILED_BYTES)
        total += size
        if len(files) >= MAX_DECOMPILED_FILES or total > MAX_DECOMPILED_BYTES:
            fail("UNITY_CODE_DECOMPILED_BUDGET", relative, "Decompiler output exceeds the module inventory budget")
        files.append({"path": relative, "sha256": digest, "bytes": size,
                      "role": "decompiled-source" if path.suffix == ".cs" else "provider-project-metadata"})
    return {"command": command, "exitCode": completed.returncode, "timedOut": False,
            "logSha256": log_sha, "logBytes": log_bytes}, files


def _resolve_calls(methods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for method in methods:
        by_name.setdefault(method["name"], []).append(method)
    edges = []
    for method in methods:
        for call in method["calls"]:
            candidates = by_name.get(call["name"], [])
            if call["receiver"]:
                candidates = [candidate for candidate in candidates
                              if candidate["declaringType"].split("+")[-1].split(".")[-1] == call["receiver"].split(".")[-1]]
            else:
                candidates = [candidate for candidate in candidates if candidate["declaringType"] == method["declaringType"]]
            if len(candidates) == 1:
                call.update(resolution="exact-symbol-unique", resolvedMethodId=candidates[0]["methodId"])
                edges.append({"callerMethodId": method["methodId"], "calleeMethodId": candidates[0]["methodId"],
                              "symbol": call["symbol"], "sourceLine": call["line"], "resolution": "exact-symbol-unique"})
            else:
                call.update(resolution="ambiguous-or-external", resolvedMethodId=None)
    return edges


def _mono(source: Path, raw: bytes, source_row: dict[str, Any], output: Path,
          provider: str | Path | None) -> dict[str, Any]:
    pe = _validate_pe_cli(raw)
    if pe is None:
        return {"status": "unsupported", "diagnostics": [{"code": "MONO_INPUT_NOT_MANAGED_PE",
            "location": source.name, "message": "Input does not contain a valid PE CLI header; it was not executed."}],
            "provider": None, "types": [], "methods": [], "outputs": [],
            "summary": {"types": 0, "methods": 0, "decompiledBodies": 0, "implementedMethods": 0}}
    command, provider_identity = _provider_info(provider)
    snapshot_dir = output / "SourceRecovery" / "Original"
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    snapshot = snapshot_dir / (source_row["sha256"][:16] + "-" + source.name)
    with snapshot.open("xb") as stream:
        stream.write(raw)
    snapshot_hash, snapshot_bytes = _hash_file(snapshot, MAX_SOURCE_BYTES)
    if snapshot_hash != source_row["sha256"] or snapshot_bytes != source_row["bytes"]:
        fail("UNITY_CODE_SOURCE_SNAPSHOT_CHANGED", source.name, "Private source snapshot differs from the exact input bytes")
    run, files = _run_ilspy(snapshot, output, command)
    diagnostics = []
    if run["timedOut"]:
        diagnostics.append({"code": "ILSPY_TIMEOUT", "location": source.name,
                            "message": "ILSpy exceeded the bounded static-decompilation timeout."})
    elif run["exitCode"] != 0:
        diagnostics.append({"code": "ILSPY_FAILED", "location": source.name,
                            "message": f"ILSpy exited {run['exitCode']}; see the private bounded provider log."})
    types = []
    methods = []
    for row in files:
        if row["role"] != "decompiled-source" or not row["path"].endswith(".cs"):
            continue
        if row["bytes"] > MAX_CSHARP_PARSE_BYTES:
            diagnostics.append({"code": "ILSPY_SOURCE_FILE_PARSE_BUDGET", "location": row["path"],
                                "message": "Decompiler source is retained by hash but exceeds the per-file static parser budget."})
            continue
        path = output / row["path"]
        try:
            text = path.read_text("utf-8-sig")
        except (UnicodeDecodeError, OSError):
            diagnostics.append({"code": "ILSPY_SOURCE_NOT_UTF8", "location": row["path"],
                                "message": "Decompiler output could not be read as bounded UTF-8 source."})
            continue
        try:
            parsed = parse_csharp(text, row["path"], row["sha256"])
        except ValueError as error:
            diagnostics.append({"code": getattr(error, "code", "ILSPY_SOURCE_PARSE_FAILED"),
                                "location": row["path"], "message": "Decompiler source could not be statically indexed."})
            continue
        types.extend(parsed["types"])
        methods.extend(parsed["methods"])
    edges = _resolve_calls(methods)
    body_count = sum(method["bodyEvidence"] is not None for method in methods)
    if not types:
        diagnostics.append({"code": "ILSPY_NO_TYPES_PARSED", "location": source.name,
                            "message": "No C# type declarations were parsed from the provider output."})
    if any(method["bodyEvidence"] is None for method in methods):
        diagnostics.append({"code": "DECLARATION_WITHOUT_BODY", "location": source.name,
                            "message": "Abstract, external, or otherwise bodyless declarations remain metadata-only."})
    status = "decompiled_body_not_verified" if body_count else "metadata_only"
    if run["exitCode"] != 0 or run["timedOut"]:
        status = "unsupported"
    outputs = [{"path": snapshot.relative_to(output).as_posix(), "sha256": snapshot_hash,
                "bytes": snapshot_bytes, "role": "exact-source-snapshot"}] + files + ([{"path": "provider-ilspy.log", "sha256": run["logSha256"],
                         "bytes": run.get("logBytes"), "role": "private-provider-log"}] if run.get("logSha256") else [])
    return {"status": status, "diagnostics": diagnostics, "provider": dict(provider_identity, run=run),
            "peCli": pe, "types": types, "methods": methods, "callEdges": edges, "outputs": outputs,
            "summary": {"types": len(types), "methods": len(methods), "decompiledBodies": body_count,
                        "implementedMethods": 0, "resolvedInAssemblyCalls": len(edges)}}


def _metadata_identity(path: Path, row: dict[str, Any], raw: bytes) -> dict[str, Any]:
    item = {"path": str(path), "sha256": row["sha256"], "bytes": row["bytes"], "kind": "raw-metadata-evidence"}
    try:
        metadata = load(raw, max_nodes=500_000, max_depth=64)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return item
    if isinstance(metadata, dict):
        for key in ("sourceSha256", "metadataSha256", "revision", "provider", "module"):
            if key in metadata:
                item[key] = metadata[key]
    return item


def _il2cpp(source: Path, source_row: dict[str, Any], output: Path,
             source_raw: bytes, metadata: tuple[Path, dict[str, Any], bytes] | None,
             method_map: tuple[Path, dict[str, Any], bytes] | None) -> dict[str, Any]:
    diagnostics = []
    metadata_row = None
    metadata_doc = None
    if metadata:
        metadata_path, metadata_row, metadata_raw = metadata
        metadata_doc = _metadata_identity(metadata_path, metadata_row, metadata_raw)
        declared_source = metadata_doc.get("sourceSha256")
        if declared_source is not None and declared_source != source_row["sha256"]:
            fail("UNITY_CODE_METADATA_SOURCE_MISMATCH", metadata_path.name, "Metadata declares a different source binary SHA-256")
    map_records = []
    map_identity = None
    map_bound = False
    unbound_rows = 0
    if method_map:
        map_path, map_identity, map_raw = method_map
        parsed = parse_method_map(map_raw)
        if parsed["declaredSourceSha256"] is not None and parsed["declaredSourceSha256"] != source_row["sha256"]:
            fail("UNITY_CODE_MAP_SOURCE_MISMATCH", map_path.name, "Method map declares a different source binary SHA-256")
        metadata_sha = metadata_row["sha256"] if metadata_row else None
        if parsed["declaredMetadataSha256"] is not None and parsed["declaredMetadataSha256"] != metadata_sha:
            fail("UNITY_CODE_MAP_METADATA_MISMATCH", map_path.name, "Method map declares a different metadata SHA-256")
        envelope_bound = (parsed["declaredSourceSha256"] == source_row["sha256"] and
                          metadata_sha is not None and parsed["declaredMetadataSha256"] == metadata_sha)
        map_bound = envelope_bound
        for index, row in enumerate(parsed["rows"]):
            if (not isinstance(row, dict) or any(not isinstance(row.get(key), str) for key in ("type", "name", "module"))
                    or type(row.get("function")) is not int or row["function"] < 0):
                fail("UNITY_CODE_MAP_ROW", str(index), "Method row must contain type/name/module and exact nonnegative function index")
            row_source = row.get("sourceSha256")
            row_metadata = row.get("metadataSha256")
            if row_source is not None and row_source != source_row["sha256"]:
                fail("UNITY_CODE_MAP_SOURCE_MISMATCH", str(index), "Method row maps a different source binary")
            if row_metadata is not None and (metadata_sha is None or row_metadata != metadata_sha):
                fail("UNITY_CODE_MAP_METADATA_MISMATCH", str(index), "Method row maps different metadata")
            row_bound = row_source == source_row["sha256"] and metadata_sha is not None and row_metadata == metadata_sha
            bound = envelope_bound or row_bound
            map_bound = map_bound or row_bound
            if not bound:
                unbound_rows += 1
            type_name = row["type"]
            name = row["name"]
            method_id = f"{row['module']}:{row['function']}:{type_name}::{name}"
            body = row.get("bodyEvidence")
            body_record = None
            status = "metadata_only"
            if isinstance(body, dict) and isinstance(body.get("text"), str):
                body_bytes = body["text"].encode("utf-8")
                if body.get("sha256") != hashlib.sha256(body_bytes).hexdigest():
                    fail("UNITY_CODE_MAP_BODY_HASH", str(index), "Supplied static body evidence hash does not match its text")
                body_record = {"kind": "caller-supplied-static-text", "sha256": body["sha256"],
                               "bytes": len(body_bytes), "verifiedSourceSha256": source_row["sha256"] if bound else None,
                               "verifiedMetadataSha256": metadata_sha if bound else None,
                               "verifiedAgainstOriginalIL": False}
                status = "decompiled_body_not_verified"
            map_records.append({"methodId": method_id, "declaringType": type_name, "name": name,
                                "signature": row.get("signature", ""),
                                "sourceEvidence": {"kind": "method-map-row", "path": str(map_path),
                                                   "sha256": map_identity["sha256"], "row": index,
                                                   "module": row["module"], "function": row["function"],
                                                   "sourceSha256Bound": bound},
                                "bodyEvidence": body_record, "calls": [], "status": status})
        if not map_bound or unbound_rows:
            diagnostics.append({"code": "METHOD_MAP_SOURCE_LINK_UNPROVEN", "location": map_path.name,
                                "message": "Some or all method-map rows lack exact source and metadata SHA binding; those rows remain isolated metadata."})
    if metadata is None:
        diagnostics.append({"code": "IL2CPP_METADATA_MISSING", "location": source.name,
                            "message": "No hash-pinned IL2CPP metadata input was supplied."})
    if method_map is None:
        diagnostics.append({"code": "IL2CPP_METHOD_MAP_MISSING", "location": source.name,
                            "message": "No hash-pinned method map was supplied."})
    raw_magic = source_raw[:8]
    if raw_magic != b"\0asm\x01\0\0\0":
        diagnostics.append({"code": "WASM_CONTAINER_OPAQUE", "location": source.name,
                            "message": "Input is not an uncompressed WebAssembly v1 header; no decompression or binary recovery was attempted."})
    if not map_bound:
        diagnostics.append({"code": "IL2CPP_JOIN_NOT_VERIFIED", "location": source.name,
                            "message": "No metadata, function index, or body is joined to this exact source revision."})
    status = "decompiled_body_not_verified" if map_bound and any(row["bodyEvidence"] for row in map_records) else "metadata_only"
    outputs = []
    return {"status": status, "diagnostics": diagnostics, "provider": None, "metadata": metadata_doc,
            "methodMap": {"path": map_identity["path"], "sha256": map_identity["sha256"],
                          "inputKind": parsed["inputKind"], "queryReportSha256": parsed["queryReportSha256"],
                          "inputArtifacts": parsed["inputArtifacts"],
                          "sourceBinding": ("verified" if map_bound and not unbound_rows else "partially-verified" if map_bound else "not-proven")} if method_map else None,
            "types": [], "methods": map_records, "callEdges": [], "outputs": outputs,
            "summary": {"types": 0, "methods": len(map_records), "decompiledBodies": sum(r["bodyEvidence"] is not None for r in map_records),
                        "implementedMethods": 0, "resolvedInAssemblyCalls": 0}}


def inspect(source: str | Path, output: str | Path, *, expected_sha256: str,
            family: str = "mono", provider: str | Path | None = None,
            metadata: str | Path | None = None, method_map: str | Path | None = None,
            expected_metadata_sha256: str | None = None,
            expected_method_map_sha256: str | None = None) -> dict[str, Any]:
    """Inspect an exact Unity code source without loading or executing its code."""
    if family not in ("mono", "il2cpp-wasm"):
        fail("UNITY_CODE_FAMILY_UNSUPPORTED", family, "Supported code families are mono and il2cpp-wasm")
    source_path, source_row, source_raw = _input_path(source, "source", expected_sha256, MAX_SOURCE_BYTES)
    source_row["family"] = family
    metadata_input = _input_path(metadata, "metadata", expected_metadata_sha256) if metadata is not None else (None, None, None)
    method_map_input = _input_path(method_map, "method_map", expected_method_map_sha256) if method_map is not None else (None, None, None)
    if family == "mono" and (metadata is not None or method_map is not None):
        fail("UNITY_CODE_FAMILY_INPUT", family, "External IL2CPP metadata/method maps are not accepted for Mono assemblies")
    output_path = new_output(output, [item for item in (source_path, metadata_input[0], method_map_input[0]) if item is not None])
    if family == "mono":
        result = _mono(source_path, source_raw, source_row, output_path, provider)
    else:
        result = _il2cpp(source_path, source_row, output_path, source_raw,
                         metadata_input if metadata_input[0] else None,
                         method_map_input if method_map_input[0] else None)
    from . import __version__
    report = {"schemaVersion": 1, "toolVersion": __version__, "status": result["status"], "sourceFamily": family,
              "source": source_row, "sourceCodeExecuted": False,
              "provider": result.get("provider"), "types": result["types"], "methods": result["methods"],
              "callEdges": result.get("callEdges", []), "diagnostics": result["diagnostics"],
              "outputs": result["outputs"], "summary": result["summary"]}
    if result.get("peCli") is not None:
        report["source"]["peCli"] = result["peCli"]
    for name in ("metadata", "methodMap"):
        if result.get(name) is not None:
            report[name] = result[name]
    if len(encoded(report)) > MAX_REPORT_BYTES:
        fail("UNITY_CODE_REPORT_BUDGET", str(output_path.name), "Static code report exceeds the report byte budget")
    write_json(output_path / "unity-code-source.json", report)
    return {"status": report["status"], "report": str(output_path / "unity-code-source.json"),
            "summary": report["summary"], "sourceCodeExecuted": False}

