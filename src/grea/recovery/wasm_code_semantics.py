"""Lift a deliberately small, auditable IL2CPP/WASM body subset into C#.

Only pure fixed-point operators whose entire function body is a two-operand
WebAssembly i64 operation are emitted. All other bodies remain exact evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Sequence

from .io import encoded, load, new_output, safe, write_json
from .sources.compiled import fail

MAX_BODY_BYTES = 4 * 1024 * 1024
MAX_CANDIDATE_BYTES = 4 * 1024 * 1024
MAX_REPORT_BYTES = 16 * 1024 * 1024

_PURE_FP_OPERATORS = {
    "op_Addition": {"opcode": 0x7c, "symbol": "+", "return": "FP", "body": "add"},
    "op_Subtraction": {"opcode": 0x7d, "symbol": "-", "return": "FP", "body": "sub"},
    "op_Equality": {"opcode": 0x51, "symbol": "==", "return": "bool", "body": "compare"},
    "op_Inequality": {"opcode": 0x52, "symbol": "!=", "return": "bool", "body": "compare"},
    "op_LessThan": {"opcode": 0x53, "symbol": "<", "return": "bool", "body": "compare"},
    "op_GreaterThan": {"opcode": 0x55, "symbol": ">", "return": "bool", "body": "compare"},
    "op_LessThanOrEqual": {"opcode": 0x57, "symbol": "<=", "return": "bool", "body": "compare"},
    "op_GreaterThanOrEqual": {"opcode": 0x59, "symbol": ">=", "return": "bool", "body": "compare"},
}
_OPERATOR_PEERS = {"==": "!=", "!=": "==", "<": ">", ">": "<", "<=": ">=", ">=": "<="}
_OPCODE_TO_CSHARP = {0x51: "==", 0x52: "!=", 0x53: "<", 0x54: "<", 0x55: ">",
                     0x56: ">", 0x57: "<=", 0x58: "<=", 0x59: ">=", 0x5a: ">="}


def _u32(raw: bytes, cursor: int) -> tuple[int, int]:
    value = 0
    shift = 0
    for _ in range(5):
        if cursor >= len(raw):
            raise ValueError("truncated LEB128")
        byte = raw[cursor]
        cursor += 1
        value |= (byte & 0x7f) << shift
        if byte < 0x80:
            return value, cursor
        shift += 7
    raise ValueError("LEB128 overflow")


def _sleb(raw: bytes, cursor: int, max_bytes: int) -> tuple[int, int]:
    value = 0
    shift = 0
    for _ in range(max_bytes):
        if cursor >= len(raw):
            raise ValueError("truncated signed LEB128")
        byte = raw[cursor]
        cursor += 1
        value |= (byte & 0x7f) << shift
        shift += 7
        if byte < 0x80:
            if byte & 0x40:
                value |= -(1 << shift)
            return value, cursor
    raise ValueError("signed LEB128 overflow")


def _body_features(raw: bytes) -> dict[str, Any]:
    """Collect calls, locals, and memory offsets from common MVP instructions."""
    cursor = 0
    local_groups, cursor = _u32(raw, cursor)
    local_count = 0
    for _ in range(local_groups):
        count, cursor = _u32(raw, cursor)
        if cursor >= len(raw):
            raise ValueError("truncated local type")
        cursor += 1
        local_count += count
    calls = []
    memory = []
    opcodes = set()
    unparsed = []
    while cursor < len(raw):
        opcode = raw[cursor]
        cursor += 1
        opcodes.add(f"0x{opcode:02x}")
        if opcode in (0x02, 0x03, 0x04):
            if cursor >= len(raw): raise ValueError("truncated block type")
            if raw[cursor] not in (0x40, 0x7c, 0x7d, 0x7e, 0x7f, 0x7b, 0x70, 0x6f):
                _, cursor = _sleb(raw, cursor, 5)
            else:
                cursor += 1
        elif opcode in (0x0c, 0x0d, 0x10, 0x14, 0x20, 0x21, 0x22, 0x23, 0x24, 0xd2):
            immediate, cursor = _u32(raw, cursor)
            if opcode == 0x10:
                calls.append(immediate)
        elif opcode == 0x0e:
            count, cursor = _u32(raw, cursor)
            for _ in range(count + 1):
                _, cursor = _u32(raw, cursor)
        elif opcode == 0x11:
            _, cursor = _u32(raw, cursor)
            _, cursor = _u32(raw, cursor)
        elif 0x28 <= opcode <= 0x3e:
            alignment, cursor = _u32(raw, cursor)
            offset, cursor = _u32(raw, cursor)
            memory.append({"opcode": f"0x{opcode:02x}", "alignment": alignment, "offset": offset})
        elif opcode in (0x3f, 0x40):
            _, cursor = _u32(raw, cursor)
        elif opcode == 0x41:
            _, cursor = _sleb(raw, cursor, 5)
        elif opcode == 0x42:
            _, cursor = _sleb(raw, cursor, 10)
        elif opcode == 0x43:
            cursor += 4
        elif opcode == 0x44:
            cursor += 8
        elif opcode == 0xd0:
            if cursor >= len(raw): raise ValueError("truncated ref.null type")
            cursor += 1
        elif opcode == 0xfc:
            subopcode, cursor = _u32(raw, cursor)
            if subopcode == 8:
                _, cursor = _u32(raw, cursor); _, cursor = _u32(raw, cursor)
            elif subopcode in (9, 13, 15, 16, 17):
                _, cursor = _u32(raw, cursor)
            elif subopcode == 10 or subopcode == 12 or subopcode == 14:
                _, cursor = _u32(raw, cursor); _, cursor = _u32(raw, cursor)
            elif subopcode > 7:
                unparsed.append(f"0xfc/{subopcode}")
        elif opcode in (0xfd, 0xfe, 0xfb, 0x12, 0x13, 0x15, 0x16, 0x17):
            unparsed.append(f"0x{opcode:02x}")
            break
        elif opcode in (0x00, 0x01, 0x05, 0x0b, 0x0f, 0x1a, 0x1b, 0xd1) or 0x45 <= opcode <= 0xc4:
            pass
        else:
            unparsed.append(f"0x{opcode:02x}")
            break
        if cursor > len(raw):
            raise ValueError("instruction immediate exceeds body bounds")
    return {"localGroups": local_groups, "declaredLocals": local_count,
            "opcodes": sorted(opcodes), "directCalls": calls, "memoryAccesses": memory,
            "unparsedInstructions": unparsed}


def _decode_pure_i64_body(raw: bytes) -> tuple[int, str]:
    """Return the only operation in an exact two-parameter i64 expression body."""
    if not isinstance(raw, bytes) or len(raw) > MAX_BODY_BYTES:
        raise ValueError("body exceeds bounded input")
    cursor = 0
    local_groups, cursor = _u32(raw, cursor)
    if local_groups != 0:
        raise ValueError("locals are outside the pure two-parameter subset")
    ops = []
    while cursor < len(raw):
        opcode = raw[cursor]
        cursor += 1
        if opcode == 0x20:  # local.get
            index, cursor = _u32(raw, cursor)
            ops.append(("local", index))
        elif opcode in _PURE_OPCODE_SET:
            ops.append(("operator", opcode))
        elif opcode in (0x0f, 0x0b):  # return, end
            ops.append(("terminal", opcode))
        else:
            raise ValueError(f"unsupported opcode 0x{opcode:02x}")
    if len(ops) != 5 or ops[0] != ("local", 0) or ops[1] != ("local", 1):
        raise ValueError("body is not local0/local1/operator/return/end")
    operation = ops[2]
    if operation[0] != "operator" or ops[3] != ("terminal", 0x0f) or ops[4] != ("terminal", 0x0b):
        raise ValueError("body does not end with a single returned operation")
    return operation[1], "two-parameter-i64-expression"


_PURE_OPCODE_SET = set(_OPCODE_TO_CSHARP) | {0x7c, 0x7d}


def _report_input(value: Any) -> tuple[Path, dict[str, Any], str]:
    expected = value.get('expectedSha256') if isinstance(value,dict) else None
    if isinstance(value, dict) and isinstance(value.get("report"), str):
        path = safe(value["report"])
    elif isinstance(value, (str, Path)):
        path = safe(value)
    else:
        fail("WASM_SEMANTICS_REPORT_REQUIRED", "$", "Pass a wasm-code-source.json path or inspect_wasm result")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        fail("WASM_SEMANTICS_REPORT_INVALID", str(path), "Expected a bounded regular WASM source report")
    try:
        raw=path.read_bytes()
        if expected is not None and (not isinstance(expected,str)or hashlib.sha256(raw).hexdigest()!=expected):
            fail('WASM_SEMANTICS_REPORT_CHANGED',path.name,'Source report differs from the expected SHA256')
        report = load(raw,max_nodes=500_000,max_depth=64)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        fail("WASM_SEMANTICS_REPORT_INVALID", path.name, f"WASM source report is invalid JSON ({type(error).__name__})")
    if not isinstance(report, dict) or report.get("schemaVersion") != 1 or report.get("sourceFamily") != "il2cpp-wasm":
        fail("WASM_SEMANTICS_REPORT_SCHEMA", path.name, "Expected a source-bound IL2CPP-WASM report")
    return path.parent, report, hashlib.sha256(raw).hexdigest()


def _fragment(record: dict[str, Any], raw: bytes) -> dict[str, Any] | None:
    method = record.get("method")
    spec = _PURE_FP_OPERATORS.get(method)
    if spec is None or record.get("declaringType") != "BattleCore.FP":
        return None
    if not any(isinstance(field, dict) and field.get("name") == "_serializedValue"
               for field in record.get("typeFields", [])):
        return None
    signature = record.get("wasmTypeSignature")
    expected_results = [0x7e] if spec["return"] == "FP" else [0x7f]
    if not isinstance(signature, dict) or signature.get("params") != [0x7e, 0x7e, 0x7f] or signature.get("results") != expected_results:
        return None
    opcode, pattern = _decode_pure_i64_body(raw)
    if opcode != spec["opcode"]:
        return None
    mapped_signature = record.get("signatureFromMap")
    signature_pattern = re.compile(
        r"^public static " + re.escape(spec["return"]) + r" " + re.escape(method) +
        r"\(FP ([A-Za-z_][A-Za-z0-9_]*), FP ([A-Za-z_][A-Za-z0-9_]*)\) \{ \}$"
    )
    matched = signature_pattern.fullmatch(mapped_signature or "")
    if not matched:
        return None
    left, right = matched.groups()
    if spec["body"] in ("add", "sub"):
        token = "+" if spec["body"] == "add" else "-"
        body = ("FP result = default(FP);\n"
                f"result._serializedValue = unchecked({left}._serializedValue {token} {right}._serializedValue);\n"
                "return result;")
    else:
        csharp_operator = _OPCODE_TO_CSHARP.get(opcode)
        if csharp_operator is None or csharp_operator != spec["symbol"]:
            return None
        body = f"return {left}._serializedValue {csharp_operator} {right}._serializedValue;"
    declaration = f"public static {spec['return']} operator {spec['symbol']}(FP {left}, FP {right})"
    return {"methodId": record["methodId"], "sourceMethod": f"{record['declaringType']}::{method}",
            "metadataToken": record["token"], "signatureFromMap": mapped_signature,
            "candidateDeclaration": declaration, "candidateBody": body,
            "bodyShape": pattern, "wasmOpcode": f"0x{opcode:02x}",
            "status": "csharp_body_recovered_candidate",
            "assumptions": ["FP has a metadata-declared _serializedValue field; the raw WASM operand type is i64.",
                            "The body fragment replaces this method inside the existing BattleCore.FP declaration.",
                            "Caller must independently verify the host raw-long field and supplied method-to-function binding; codeRegistration and object layout are not established here."],
            "sourceExecuted": False}


def recover_wasm_subset(report_or_receipt: Any, output: str | Path, *, selections: Sequence[str]) -> dict[str, Any]:
    """Emit C# replacement fragments only for verified pure FP operator bodies.

    `selections` accepts exact source report method IDs or unique fully-qualified
    symbols such as `BattleCore.FP::op_Addition`. Unsupported bodies are retained
    in the report with a precise limitation; they are never guessed from names.
    """
    if not isinstance(selections, Sequence) or isinstance(selections, (str, bytes)) or not selections:
        fail("WASM_SEMANTICS_SELECTION_REQUIRED", "$", "Select at least one exact method ID or unique qualified method")
    if len(selections)>256 or any(not isinstance(item,str)or not item for item in selections):
        fail('WASM_SEMANTICS_SELECTION_BUDGET','$','Select at most256 exact nonempty IDs or qualified symbols')
    reports = report_or_receipt if isinstance(report_or_receipt, (list, tuple)) else [report_or_receipt]
    if not 1<=len(reports)<=8: fail('WASM_SEMANTICS_REPORT_BUDGET','$','Use one to eight bounded source reports')
    report_items = [_report_input(item) for item in reports]
    identities={(r.get('metadata',{}).get('sha256'),r.get('methodMap',{}).get('sha256'))for _,r,_ in report_items}
    if len(identities)!=1 or any(not isinstance(v,str)or not re.fullmatch(r'[0-9a-f]{64}',v)for pair in identities for v in pair):
        fail('WASM_SEMANTICS_SOURCE_SET','$','Reports must use one exact metadata and method-map identity; do not mix revisions')
    roots = [item[0] for item in report_items]
    rows_with_roots = []
    for root, source_report, report_sha in report_items:
        if source_report.get("sourceExecuted") is not False or source_report.get("wasmInstantiated") is not False:
            fail("WASM_SEMANTICS_SOURCE_EXECUTION", str(root), "Source report does not affirm a static-only workflow")
        rows = source_report.get("methods")
        if not isinstance(rows, list):
            fail("WASM_SEMANTICS_METHODS_MISSING", str(root), "Source report has no method inventory")
        rows_with_roots.extend((root, row) for row in rows)
    ids=[row.get('methodId')for _,row in rows_with_roots]
    if len(set(ids))!=len(ids): fail('WASM_SEMANTICS_METHOD_DUPLICATE','$','Repeated exact method identities across source reports')
    for symbol in selections:
        matches={row.get('methodId')for _,row in rows_with_roots if f"{row.get('declaringType')}::{row.get('method')}"==symbol}
        if len(matches)>1: fail('WASM_SEMANTICS_METHOD_AMBIGUOUS',symbol,'Qualified method is ambiguous; supply its exact method ID')
    requested = [(root, row) for root, row in rows_with_roots if row.get("methodId") in selections or
                 f"{row.get('declaringType')}::{row.get('method')}" in selections]
    resolved_names = {f"{row.get('declaringType')}::{row.get('method')}" for _, row in requested}
    resolved_ids = {row.get("methodId") for _, row in requested}
    missing = [item for item in selections if item not in resolved_ids and item not in resolved_names]
    if missing:
        fail("WASM_SEMANTICS_METHOD_NOT_FOUND", "$", "One or more selected methods are absent from the bound report")
    requested_ids = {row.get("methodId") for _, row in requested}
    for root, row in list(requested):
        spec = _PURE_FP_OPERATORS.get(row.get("method"))
        peer = _OPERATOR_PEERS.get(spec["symbol"]) if spec else None
        peer_name = next((name for name, value in _PURE_FP_OPERATORS.items() if value["symbol"] == peer), None)
        if peer_name:
            peer_pair = next(((peer_root, candidate) for peer_root, candidate in rows_with_roots
                              if candidate.get("declaringType") == "BattleCore.FP"
                             and candidate.get("method") == peer_name), None)
            if peer_pair is not None and peer_pair[1].get("methodId") not in requested_ids:
                requested.append(peer_pair)
                requested_ids.add(peer_pair[1].get("methodId"))
    candidate_methods = []
    not_lifted = []
    for root, row in requested:
        body = row.get("bodyEvidence")
        if not isinstance(body, dict) or body.get("verifiedAgainstSegment") is not True:
            not_lifted.append({"methodId": row.get("methodId"), "status": "metadata_only",
                               "limitation": "No verified exact body slice is attached."})
            continue
        body_path = safe(root / body.get("snapshot", ""))
        if not body_path.is_file() or body_path.is_symlink() or body_path.stat().st_size > MAX_BODY_BYTES:
            fail("WASM_SEMANTICS_BODY_MISSING", str(body_path), "Verified body snapshot is missing or exceeds the byte budget")
        raw = body_path.read_bytes()
        if len(raw) != body.get("bytes") or hashlib.sha256(raw).hexdigest() != body.get("sha256"):
            fail("WASM_SEMANTICS_BODY_CHANGED", body_path.name, "Body snapshot differs from the source report identity")
        try:
            method = _fragment(row, raw)
        except ValueError as error:
            method = None
            limitation = str(error)
        else:
            limitation = "Body opcode/signature is outside the implemented exact C# lift subset."
        if method is None:
            try:
                features = _body_features(raw)
            except ValueError as error:
                features = {"unparsedInstructions": [str(error)], "directCalls": [], "memoryAccesses": []}
            mapped_functions = {item.get("functionIndex") for _, item in rows_with_roots
                                if item.get('segment')==row.get('segment') and item.get('sourceEvidence',{}).get('decodedSegmentSha256')==row.get('sourceEvidence',{}).get('decodedSegmentSha256')}
            unresolved_calls = [index for index in features.get("directCalls", []) if index not in mapped_functions]
            if features.get("memoryAccesses"):
                missing_semantics = "Raw memory offsets are verified, but no type-layout field map is part of this module input."
            elif unresolved_calls:
                missing_semantics = "Direct call target identities are absent from the supplied selected-method reports."
            else:
                missing_semantics = limitation
            not_lifted.append({"methodId": row["methodId"], "segment":row.get('segment'), "sourceMethod": f"{row['declaringType']}::{row['method']}",
                               "sourceSignature": row.get("signatureFromMap"),
                               "wasmTypeSignature": row.get("wasmTypeSignature"),
                               "status": "body_evidence_only", "limitation": missing_semantics,
                               "bodyFeatures": features, "unresolvedCallFunctions": unresolved_calls,
                               "bodySha256": body["sha256"], "bodyBytes": body["bytes"]})
        else:
            candidate_methods.append(method)
    symbols_to_remove = set()
    available_candidates = {item["sourceMethod"] for item in candidate_methods}
    for method in candidate_methods:
        symbol = method["sourceMethod"]
        operator = method["candidateDeclaration"].split(" operator ", 1)[1].split("(", 1)[0]
        peer = _OPERATOR_PEERS.get(operator)
        peer_method = next((item for item, spec in _PURE_FP_OPERATORS.items() if spec["symbol"] == peer), None)
        if peer_method and f"BattleCore.FP::{peer_method}" not in available_candidates:
            not_lifted.append({"methodId": method["methodId"], "sourceMethod": symbol,
                               "status": "body_evidence_only", "limitation": f"C# requires paired operator {peer}; its exact body is not in the bound report."})
            symbols_to_remove.add(symbol)
    candidate_methods = [method for method in candidate_methods if method["sourceMethod"] not in symbols_to_remove]

    output_path = new_output(output, roots)
    fragment_path = None
    code = b""
    if candidate_methods:
        fragment_lines = ["// Generated by monkey from verified WebAssembly opcode bodies.",
                          "// Merge into the existing BattleCore.FP declaration; this file is a candidate fragment.",
                          "namespace BattleCore", "{", "    public partial struct FP", "    {"]
        for method in candidate_methods:
            fragment_lines.append("        " + method["candidateDeclaration"])
            fragment_lines.append("        {")
            for line in method["candidateBody"].splitlines():
                fragment_lines.append("            " + line)
            fragment_lines.append("        }")
            fragment_lines.append("")
        fragment_lines.extend(["    }", "}", ""])
        code = "\n".join(fragment_lines).encode("utf-8")
        if len(code) > MAX_CANDIDATE_BYTES:
            fail("WASM_SEMANTICS_CANDIDATE_BUDGET", "$", "Generated C# fragments exceed the byte budget")
        fragment_path = output_path / "CSharpCandidate/FP.RecoveredOperators.cs"
        fragment_path.parent.mkdir(parents=True)
        fragment_path.write_bytes(code)
    result = {"schemaVersion": 1, "status": "candidate_fragments_generated" if candidate_methods else "no_csharp_body_lift",
              "sourceReportSha256": [item[2] for item in report_items],
              "sourceExecuted": False, "wasmInstantiated": False,
              "candidate": ({"path": fragment_path.relative_to(output_path).as_posix(),
                             "sha256": hashlib.sha256(code).hexdigest(), "bytes": len(code),
                             "hostType": "BattleCore.FP", "requiresMergeIntoExistingDeclaration": True}
                            if fragment_path else None),
              "methods": candidate_methods, "notLifted": not_lifted,
              "diagnostics": [{"code": "IL2CPP_BUILD_RELATION_WITHHELD",
                               "message": "Candidate is based on exact mapped body bytes and metadata IDs; no common build-id or runtime behavior claim is made."}],
              "summary": {"selected": len(requested), "csharpBodies": len(candidate_methods),
                          "bodyEvidenceOnly": len(not_lifted), "implementedMethods": 0}}
    if len(encoded(result)) > MAX_REPORT_BYTES:
        fail("WASM_SEMANTICS_REPORT_BUDGET", str(output_path.name), "C# candidate report exceeds its byte budget")
    write_json(output_path / "wasm-code-candidate.json", result)
    return {"status": result["status"], "report": str(output_path / "wasm-code-candidate.json"),
            "candidate": str(fragment_path) if fragment_path else None, "summary": result["summary"], "sourceExecuted": False,
            "wasmInstantiated": False}
