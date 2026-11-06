"""Bounded static parsing helpers for decompiled C# and IL2CPP evidence maps.

These routines inspect text only. They never load a managed assembly or WASM.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .io import load
from .sources.compiled import fail


_TOKEN = re.compile(
    r"(?P<space>\s+)"
    r"|(?P<line>//[^\r\n]*)"
    r"|(?P<block>/\*[\s\S]*?\*/)"
    r"|(?P<raw>(?:\$@|@\$|@|\$)?\"\"\"[\s\S]*?\"\"\")"
    r"|(?P<string>(?:\$@|@\$|@|\$)?\"(?:\"\"|\\.|[^\"\\])*\")"
    r"|(?P<char>'(?:\\.|[^'\\])*')"
    r"|(?P<id>@?(?:[^\W\d]|_)\w*)"
    r"|(?P<number>(?:0[xX][0-9A-Fa-f_]+|[0-9][0-9A-Za-z_.]*))"
    r"|(?P<op>=>|::|\?\?|\?\.|\+\+|--|&&|\|\||==|!=|<=|>=|<<|>>|\+=|-=|\*=|/=|\*=|\.\.\.|.)"
)
_TYPE_KEYWORDS = {"class", "struct", "interface", "enum", "record"}
_CONTROL_CALLS = {"if", "else", "for", "foreach", "while", "switch", "catch", "using", "lock",
                  "fixed", "checked", "unchecked", "sizeof", "typeof", "nameof", "default", "new"}
_CALL_EXCLUDE = _CONTROL_CALLS | {"return", "throw", "await", "yield", "when"}


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _ident(token: str) -> bool:
    return token.removeprefix("@").isidentifier()


def tokenize_csharp(text: str) -> list[dict[str, Any]]:
    tokens = []
    line = 1
    for match in _TOKEN.finditer(text):
        kind = match.lastgroup
        value = match.group()
        if kind in ("space", "line", "block"):
            line += value.count("\n")
            continue
        tokens.append({"value": value, "start": match.start(), "end": match.end(), "line": line})
        if len(tokens) > 2_000_000:
            fail("UNITY_CODE_CSHARP_TOKEN_BUDGET", "$", "One C# source file exceeds the static parser token budget")
        line += value.count("\n")
    return tokens


def _pairs(tokens: list[dict[str, Any]], left: str, right: str) -> dict[int, int]:
    stack: list[int] = []
    pairs = {}
    for i, token in enumerate(tokens):
        value = token["value"]
        if value == left:
            stack.append(i)
        elif value == right and stack:
            pairs[stack.pop()] = i
    return pairs


def _scopes(tokens: list[dict[str, Any]], braces: dict[int, int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    namespaces = []
    types = []
    values = [token["value"] for token in tokens]
    for i, value in enumerate(values):
        if value == "namespace":
            j = i + 1
            parts = []
            while j < len(values) and (values[j] == "." or _ident(values[j])):
                if _ident(values[j]):
                    parts.append(values[j].removeprefix("@"))
                j += 1
            if not parts:
                continue
            while j < len(values) and values[j] not in ("{", ";", "}"):
                j += 1
            if j < len(values) and values[j] == "{" and j in braces:
                namespaces.append({"name": ".".join(parts), "start": j, "end": braces[j]})
            elif j < len(values) and values[j] == ";":
                namespaces.append({"name": ".".join(parts), "start": j, "end": len(values)})
        if value not in _TYPE_KEYWORDS:
            continue
        name_index = i + 1
        if value == "record" and name_index < len(values) and values[name_index] in ("class", "struct"):
            name_index += 1
        if name_index >= len(values) or not _ident(values[name_index]):
            continue
        j = name_index + 1
        while j < len(values) and values[j] not in ("{", ";", "}"):
            j += 1
        if j >= len(values) or values[j] != "{" or j not in braces:
            continue
        types.append({"kind": value, "name": values[name_index].removeprefix("@"),
                      "declIndex": i, "nameIndex": name_index, "open": j, "close": braces[j]})
    return namespaces, types


def _full_type_name(type_row: dict[str, Any], namespaces: list[dict[str, Any]], types: list[dict[str, Any]]) -> str:
    i = type_row["declIndex"]
    ns = [row for row in namespaces if row["start"] < i < row["end"]]
    ns.sort(key=lambda row: row["start"])
    parent_types = [row for row in types if row["open"] < i < row["close"]]
    parent_types.sort(key=lambda row: row["open"])
    namespace = ".".join(row["name"] for row in ns)
    nested = "+".join([*(row["name"] for row in parent_types), type_row["name"]])
    return namespace + ("." if namespace else "") + nested


def _member_marker(values: list[str], close_paren: int, type_close: int,
                   parens: dict[int, int], brackets: dict[int, int]) -> tuple[str | None, int]:
    j = close_paren + 1
    while j < type_close:
        value = values[j]
        if value in ("{", "=>", ";", "}"):
            return value, j
        if value == "(" and j in parens:
            j = parens[j] + 1
        elif value == "[" and j in brackets:
            j = brackets[j] + 1
        else:
            j += 1
    return None, j


def _body_calls(values: list[str], start: int, end: int, line_for: list[int]) -> list[dict[str, Any]]:
    calls = []
    for i in range(start, end - 1):
        value = values[i]
        if not _ident(value) or value.removeprefix("@") in _CALL_EXCLUDE or values[i + 1] != "(":
            continue
        raw_name = value.removeprefix("@")
        receiver = None
        if i >= 2 and values[i - 1] in (".", "?.") and _ident(values[i - 2]):
            receiver = values[i - 2].removeprefix("@")
            if i >= 4 and values[i - 3] == "." and _ident(values[i - 4]):
                receiver = values[i - 4].removeprefix("@") + "." + receiver
        if i >= 1 and values[i - 1] == "new":
            calls.append({"symbol": "new " + raw_name, "receiver": None, "name": raw_name,
                          "kind": "constructor", "line": line_for[i]})
        else:
            calls.append({"symbol": (receiver + "." if receiver else "") + raw_name,
                          "receiver": receiver, "name": raw_name, "kind": "method", "line": line_for[i]})
    return calls


def parse_csharp(text: str, relative_path: str, file_sha256: str) -> dict[str, Any]:
    """Extract type/method declaration ranges and call symbols from decompiler text."""
    tokens = tokenize_csharp(text)
    values = [row["value"] for row in tokens]
    lines = [row["line"] for row in tokens]
    braces = _pairs(tokens, "{", "}")
    parens = _pairs(tokens, "(", ")")
    brackets = _pairs(tokens, "[", "]")
    for left, pairs in (("{", braces), ("(", parens), ("[", brackets)):
        if len(pairs) != sum(token["value"] == left for token in tokens):
            fail("UNITY_CODE_CSHARP_DELIMITER", relative_path, "Decompiler C# has an unbalanced declaration delimiter")
    namespaces, type_rows = _scopes(tokens, braces)
    type_records = []
    method_records = []
    for type_row in sorted(type_rows, key=lambda row: (row["open"], row["close"])):
        type_name = _full_type_name(type_row, namespaces, type_rows)
        type_record = {"declaringType": type_name, "kind": type_row["kind"], "sourceEvidence": {
            "path": relative_path, "line": lines[type_row["declIndex"]], "sha256": file_sha256}}
        local_methods = []
        i = type_row["open"] + 1
        member_start = i
        while i < type_row["close"]:
            nested = next((row for row in type_rows if row["declIndex"] == i and row is not type_row), None)
            if nested:
                i = nested["close"] + 1
                member_start = i
                continue
            if values[i] != "(" or i not in parens:
                if values[i] == ";":
                    member_start = i + 1
                elif values[i] == "}" and i in braces:
                    i = braces[i] + 1
                    member_start = i
                    continue
                i += 1
                continue
            close_paren = parens[i]
            name_index = i - 1
            if name_index < member_start or not _ident(values[name_index]):
                i = close_paren + 1
                continue
            name = values[name_index].removeprefix("@")
            prefix = values[member_start:name_index]
            if not prefix or "=" in prefix or "=>" in prefix:
                i = close_paren + 1
                continue
            marker, marker_index = _member_marker(values, close_paren, type_row["close"], parens, brackets)
            if marker not in ("{", "=>", ";"):
                i = close_paren + 1
                continue
            # Ensure the candidate is a member declaration, not a call in a field/property initializer.
            if any(token in prefix for token in ("return", "throw", "new")):
                i = close_paren + 1
                continue
            signature_start = tokens[member_start]["start"] if member_start < name_index else tokens[name_index]["start"]
            signature_end = tokens[marker_index]["start"]
            signature = text[signature_start:signature_end].strip()
            body_start = body_end = None
            body_text = ""
            body_line = lines[marker_index]
            resume = marker_index + 1
            if marker == "{":
                body_start = marker_index
                body_end = braces.get(marker_index)
                if body_end is not None:
                    body_text = text[tokens[marker_index]["end"]:tokens[body_end]["start"]]
                    body_line = lines[marker_index]
                    resume = body_end + 1
            elif marker == "=>":
                body_start = marker_index
                j = marker_index + 1
                while j < type_row["close"] and values[j] != ";":
                    if values[j] == "(" and j in parens:
                        j = parens[j] + 1
                    elif values[j] == "[" and j in brackets:
                        j = brackets[j] + 1
                    else:
                        j += 1
                if j < type_row["close"]:
                    body_end = j
                    body_text = text[tokens[marker_index]["end"]:tokens[j]["start"]]
                    resume = j + 1
            body_available = body_start is not None and body_end is not None
            call_start = marker_index + 1 if marker == "{" else marker_index + 1
            call_end = body_end if marker == "{" and body_end is not None else (body_end if body_end is not None else call_start)
            calls = _body_calls(values, call_start, call_end, lines) if body_available else []
            start_line = lines[member_start] if member_start < len(lines) else lines[name_index]
            end_line = lines[body_end] if body_end is not None else lines[marker_index]
            method_id = f"{relative_path}::{type_name}::{name}#{_digest(signature.encode('utf-8'))[:16]}"
            body_evidence = None
            if body_available:
                body_bytes = body_text.encode("utf-8")
                body_evidence = {"kind": "ilspy-decompiled-csharp-body", "path": relative_path,
                                 "startLine": body_line, "endLine": end_line, "sha256": _digest(body_bytes),
                                 "bytes": len(body_bytes), "sourceFileSha256": file_sha256,
                                 "verifiedAgainstOriginalIL": False}
            method = {"methodId": method_id, "declaringType": type_name, "name": name,
                      "signature": signature, "sourceEvidence": {"kind": "ilspy-decompiled-csharp-signature",
                        "path": relative_path, "startLine": start_line, "endLine": end_line, "sha256": file_sha256},
                      "bodyEvidence": body_evidence, "calls": calls,
                      "status": "decompiled_body_not_verified" if body_available else "metadata_only"}
            method_records.append(method)
            local_methods.append(method_id)
            if body_available:
                i = max(resume, i + 1)
                member_start = i
            else:
                i = marker_index + 1
                member_start = i
        type_record["methodIds"] = local_methods
        type_records.append(type_record)
    return {"types": type_records, "methods": method_records}


def parse_method_map(raw: bytes) -> dict[str, Any]:
    """Parse a JSON method-map envelope, query_methods report, or JSONL rows."""
    try:
        value = load(raw, max_nodes=1_000_000, max_depth=64)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        value = None
    if isinstance(value, dict):
        if value.get("operation") == "query-methods":
            if value.get("sourceCodeExecuted") is not False or not isinstance(value.get("rows"), list):
                fail("UNITY_METHOD_MAP_REPORT", "$", "Expected a read-only query_methods evidence report")
            return {"rows": value["rows"], "declaredSourceSha256": value.get("sourceSha256"),
                    "declaredMetadataSha256": value.get("metadataSha256"), "inputKind": "evidence_queries.query_methods",
                    "inputArtifacts": value.get("sources", []), "queryReportSha256": _digest(raw)}
        rows = value.get("methods", value.get("rows"))
        if not isinstance(rows, list):
            fail("UNITY_METHOD_MAP", "$", "Expected a methods/rows array or query_methods report")
        return {"rows": rows, "declaredSourceSha256": value.get("sourceSha256"),
                "declaredMetadataSha256": value.get("metadataSha256"), "inputKind": "versioned-json-envelope",
                "inputArtifacts": value.get("sources", []), "queryReportSha256": _digest(raw)}
    if isinstance(value, list):
        if not value or any(not isinstance(row, dict) for row in value):
            fail("UNITY_METHOD_MAP", "$", "Expected a non-empty array of method-map objects")
        return {"rows": value, "declaredSourceSha256": None, "declaredMetadataSha256": None,
                "inputKind": "evidence_queries.method-array", "inputArtifacts": [], "queryReportSha256": _digest(raw)}
    try:
        lines = [line for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
        if len(lines) > 200_000:
            fail("UNITY_CODE_METHOD_MAP_BUDGET", "$", "Method map exceeds the row budget")
        rows = [load(line.encode("utf-8"), max_nodes=20_000, max_depth=32) for line in lines]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        fail("UNITY_METHOD_MAP", "$", f"Expected bounded JSON or JSONL rows ({type(error).__name__})")
    if not rows or any(not isinstance(row, dict) for row in rows):
        fail("UNITY_METHOD_MAP", "$", "Expected one or more JSON object rows")
    return {"rows": rows, "declaredSourceSha256": None, "declaredMetadataSha256": None,
            "inputKind": "jsonl", "inputArtifacts": [], "queryReportSha256": _digest(raw)}

