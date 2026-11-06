"""Narrow metadata-only reader for ILSpy field type references."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from .unity_code_il import _ident, _pairs, tokenize_csharp


MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_TOKENS = 500_000
MAX_WANTED_TYPES = 64
MAX_FIELD_REFERENCES = 20_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ASSEMBLY = re.compile(r"^[A-Za-z0-9_.-]{1,200}(?:\.dll)?$")
_CLASS_MODIFIERS = {
    "public", "private", "family", "assembly", "famandassem", "famorassem",
    "nested", "nestedpublic", "nestedprivate", "nestedfamily", "nestedassembly",
    "nestedfamandassem", "nestedfamorassem", "auto", "sequential", "explicit",
    "ansi", "unicode", "autochar", "abstract", "sealed", "specialname",
    "rtspecialname", "import", "serializable", "windowsruntime", "beforefieldinit",
}


class ILFieldParseError(ValueError):
    """IL metadata did not prove one unique, supported field identity."""


def _assembly(name: Any, label: str) -> str:
    if not isinstance(name, str) or not _ASSEMBLY.fullmatch(name):
        raise ILFieldParseError(f"{label}: invalid assembly identity")
    return name if name.lower().endswith(".dll") else name + ".dll"


def _identity(row: Mapping[str, Any], label: str) -> tuple[str, str, str]:
    if not isinstance(row, Mapping):
        raise ILFieldParseError(f"{label}: expected full assembly/namespace/name object")
    assembly = _assembly(row.get("assembly"), label)
    namespace = row.get("namespace")
    name = row.get("name", row.get("class"))
    if not isinstance(namespace, str) or not isinstance(name, str) or not name:
        raise ILFieldParseError(f"{label}: missing namespace or class name")
    if any(not _ident(part) for part in namespace.split(".")) if namespace else False:
        raise ILFieldParseError(f"{label}: unsupported namespace identity")
    if not _ident(name) or "." in name or "/" in name or "+" in name or "`" in name:
        raise ILFieldParseError(f"{label}: wanted class must be a top-level simple name")
    return assembly, namespace, name


def _line_ranges(text: str) -> list[tuple[int, int, int]]:
    result = []
    offset = 0
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        end = offset + len(line.rstrip("\r\n"))
        result.append((number, offset, end))
        offset += len(line)
    if not result or offset < len(text):
        result.append((len(result) + 1, offset, len(text)))
    return result


def _line_bytes(text: str, ranges: list[tuple[int, int, int]], line: int) -> tuple[int, int, str, str]:
    number, start, end = ranges[line - 1]
    raw = text[start:end].encode("utf-8")
    byte_start = len(text[:start].encode("utf-8"))
    return byte_start, byte_start + len(raw), text[start:end], hashlib.sha256(raw).hexdigest()


def _is_directive_line(text: str, token: dict[str, Any]) -> bool:
    start = text.rfind("\n", 0, token["start"]) + 1
    return text[start:token["start"]].strip() == ""


def _parse_type_path(values: list[str], source_path: str, line: int) -> tuple[str, str]:
    """Parse only a simple, non-generic, non-nested namespace-qualified IL type path."""
    if not values or len(values) % 2 == 0:
        raise ILFieldParseError(f"{source_path}:{line}: unsupported type path shape (nested/generic/quoted types are not supported)")
    parts = []
    for index, value in enumerate(values):
        if index % 2 == 0:
            if not _ident(value):
                raise ILFieldParseError(f"{source_path}:{line}: unsupported type identifier {value!r}")
            parts.append(value.removeprefix("@"))
        elif value != ".":
            raise ILFieldParseError(f"{source_path}:{line}: unsupported nested/generic valuetype path")
    return ".".join(parts[:-1]), parts[-1]


def _parse_class_name(header: list[str], wanted_names: set[str], source_path: str, line: int) -> tuple[str, str] | None:
    if "extends" in header:
        header = header[:header.index("extends")]
    remaining = list(header)
    while remaining and remaining[0] in _CLASS_MODIFIERS:
        remaining.pop(0)
    if not remaining:
        return None
    if any(token in remaining for token in ("<", ">", "`", "/", "+", "[", "]")):
        if any(_ident(v) and v.removeprefix("@").split(".")[-1] in wanted_names for v in remaining):
            raise ILFieldParseError(f"{source_path}:{line}: wanted class has unsupported generic/nested/quoted identity")
        return None
    if any(not (_ident(v) or v == ".") for v in remaining):
        return None
    if len(remaining) % 2 == 0 or any(remaining[i] != "." for i in range(1, len(remaining), 2)):
        return None
    names = [remaining[i].removeprefix("@") for i in range(0, len(remaining), 2)]
    if not names:
        return None
    return ".".join(names[:-1]), names[-1]


def parse_il_field_references(
    text: str,
    assembly: str,
    wanted_types: Sequence[Mapping[str, Any]],
    source_path: str,
    source_sha256: str,
) -> dict[str, Any]:
    """Return exact top-level `valuetype [Assembly]Namespace.Type field` references.

    Only field metadata inside selected top-level classes is inspected. Method
    bodies, attributes, comments and strings are not analyzed as source behavior.
    A `valuetype` is not asserted to be an enum.
    """
    source_assembly = _assembly(assembly, "source")
    if not isinstance(source_path, str) or not source_path:
        raise ILFieldParseError("source_path is required")
    if not isinstance(text, str):
        raise ILFieldParseError("IL text must be decoded UTF-8 text")
    raw = text.encode("utf-8")
    if len(raw) > MAX_SOURCE_BYTES:
        raise ILFieldParseError(f"IL text exceeds {MAX_SOURCE_BYTES}-byte budget")
    if not isinstance(source_sha256, str) or not _SHA256.fullmatch(source_sha256) or hashlib.sha256(raw).hexdigest() != source_sha256:
        raise ILFieldParseError("IL text does not match pinned source SHA256")
    if not isinstance(wanted_types, Sequence) or isinstance(wanted_types, (str, bytes)) or not 1 <= len(wanted_types) <= MAX_WANTED_TYPES:
        raise ILFieldParseError(f"wanted_types count must be in 1..{MAX_WANTED_TYPES}")
    wanted = [_identity(row, f"wanted_types[{i}]") for i, row in enumerate(wanted_types)]
    if len(set(wanted)) != len(wanted):
        raise ILFieldParseError("duplicate wanted class identity")
    if any(row[0] != source_assembly for row in wanted):
        raise ILFieldParseError("wanted owner assembly differs from the explicitly supplied IL assembly")

    tokens = tokenize_csharp(text)
    if len(tokens) > MAX_TOKENS:
        raise ILFieldParseError(f"IL token count exceeds budget of {MAX_TOKENS}")
    values = [token["value"] for token in tokens]
    braces = _pairs(tokens, "{", "}")
    if len(braces) != values.count("{") or values.count("{") != values.count("}"):
        raise ILFieldParseError("unbalanced IL type/method braces")
    depth_before = []
    depth = 0
    for value in values:
        depth_before.append(depth)
        if value == "{":
            depth += 1
        elif value == "}":
            depth -= 1
    if depth != 0:
        raise ILFieldParseError("unbalanced IL type/method braces")

    wanted_by_short = {identity[2] for identity in wanted}
    selected = []
    for index in range(len(values) - 1):
        if values[index:index + 2] != [".", "class"] or depth_before[index] != 0 or not _is_directive_line(text, tokens[index]):
            continue
        open_index = next((j for j in range(index + 2, len(values)) if values[j] == "{" and depth_before[j] == 0), None)
        if open_index is None or open_index not in braces:
            raise ILFieldParseError(f"{source_path}:{tokens[index]['line']}: top-level .class has no matched body")
        header = values[index + 2:open_index]
        parsed_name = _parse_class_name(header, wanted_by_short, source_path, tokens[index]["line"])
        if parsed_name is None:
            continue
        namespace, name = parsed_name
        owner = (source_assembly, namespace, name)
        if owner in wanted:
            selected.append({"identity": owner, "directiveIndex": index, "openIndex": open_index,
                             "closeIndex": braces[open_index], "line": tokens[index]["line"]})

    for identity in wanted:
        matches = [row for row in selected if row["identity"] == identity]
        if not matches:
            raise ILFieldParseError(f"wanted top-level class not found: {identity[0]}:{identity[1]}.{identity[2]}")
        if len(matches) != 1:
            raise ILFieldParseError(f"ambiguous duplicate owner class: {identity[0]}:{identity[1]}.{identity[2]}")

    lines = _line_ranges(text)
    results = []
    for owner_row in selected:
        field_names: set[str] = set()
        open_index, close_index = owner_row["openIndex"], owner_row["closeIndex"]
        owner_depth = depth_before[open_index] + 1
        for index in range(open_index + 1, close_index - 1):
            if values[index:index + 2] != [".", "field"] or depth_before[index] != owner_depth or not _is_directive_line(text, tokens[index]):
                continue
            line = tokens[index]["line"]
            end_index = index + 2
            while end_index < close_index and tokens[end_index]["line"] == line:
                end_index += 1
            row_tokens = tokens[index:end_index]
            row_values = [token["value"] for token in row_tokens]
            if len(row_values) < 4:
                raise ILFieldParseError(f"{source_path}:{line}: incomplete .field declaration")
            type_markers = [i for i, value in enumerate(row_values) if value in ("valuetype", "class")]
            prefix_end = type_markers[0] if type_markers else len(row_values)
            if any(value in ("static", "literal") for value in row_values[2:prefix_end]):
                continue
            if len(type_markers) > 1:
                raise ILFieldParseError(f"{source_path}:{line}: ambiguous field type metadata")
            field_name = row_values[-1]
            if not _ident(field_name):
                if type_markers:
                    raise ILFieldParseError(f"{source_path}:{line}: unsupported quoted or malformed field name")
                continue
            field_name = field_name.removeprefix("@")
            if field_name in field_names:
                owner = owner_row["identity"]
                raise ILFieldParseError(f"{source_path}:{line}: duplicate field declaration {owner[1]}.{owner[2]}.{field_name}")
            field_names.add(field_name)
            if not type_markers:
                continue
            type_marker = type_markers[0]
            # Static/literal fields are not serialized component data. Skip
            # before inspecting type syntax (for example generic Action<T>).
            if any(value in ("static", "literal") for value in row_values[2:type_marker]):
                continue
            type_kind = row_values[type_marker]
            type_index = type_marker + 1
            if type_index >= len(row_values) or row_values[type_index] != "[":
                raise ILFieldParseError(f"{source_path}:{line}: {type_kind} lacks explicit assembly reference")
            try:
                close_bracket = row_values.index("]", type_index + 1)
            except ValueError as exc:
                raise ILFieldParseError(f"{source_path}:{line}: unterminated type assembly reference") from exc
            assembly_tokens = row_values[type_index + 1:close_bracket]
            if not assembly_tokens or len(assembly_tokens) % 2 == 0:
                raise ILFieldParseError(f"{source_path}:{line}: unsupported type assembly reference")
            assembly_parts = []
            for assembly_index, value in enumerate(assembly_tokens):
                if assembly_index % 2 == 0:
                    if not _ident(value):
                        raise ILFieldParseError(f"{source_path}:{line}: unsupported type assembly reference")
                    assembly_parts.append(value.removeprefix("@"))
                elif value != ".":
                    raise ILFieldParseError(f"{source_path}:{line}: unsupported type assembly reference")
            target_assembly = _assembly(".".join(assembly_parts), "field target")
            suffix = row_values[close_bracket + 1:-1]
            array_rank = 0
            if type_kind == "class" and suffix:
                array_start = next((i for i, value in enumerate(suffix) if value in ("[", "]")), len(suffix))
                type_path, array_suffix = suffix[:array_start], suffix[array_start:]
                if array_suffix == ["[", "]"]:
                    array_rank = 1
                elif array_suffix:
                    raise ILFieldParseError(f"{source_path}:{line}: only one-dimensional class arrays are supported")
                suffix = type_path
            elif type_kind == "valuetype" and any(value in ("[", "]") for value in suffix):
                raise ILFieldParseError(f"{source_path}:{line}: valuetype arrays or suffixes are unsupported")
            target_namespace, target_name = _parse_type_path(suffix, source_path, line)
            byte_start, byte_end, source_line, line_sha = _line_bytes(text, lines, line)
            owner = owner_row["identity"]
            results.append({
                "owner": {"assembly": owner[0], "namespace": owner[1], "name": owner[2]},
                "fieldName": field_name,
                "fieldTypeKind": type_kind,
                "targetType": {"assembly": target_assembly, "namespace": target_namespace, "name": target_name},
                "semanticKind": ("unresolved-valuetype-not-proven-enum" if type_kind == "valuetype"
                                  else "class-reference-not-proven-native"),
                "sourceEvidence": {"path": source_path, "line": line, "byteSpan": [byte_start, byte_end],
                                   "lineSha256": line_sha, "lineText": source_line},
            })
            if type_kind == "class":
                results[-1]["arrayRank"] = array_rank
            if len(results) > MAX_FIELD_REFERENCES:
                raise ILFieldParseError(f"field reference count exceeds budget of {MAX_FIELD_REFERENCES}")

    return {
        "schemaVersion": 1,
        "status": "schema_only",
        "source": {"path": source_path, "assembly": source_assembly, "bytes": len(raw), "sha256": source_sha256},
        "selectedTypes": [dict(assembly=a, namespace=n, name=c) for a, n, c in wanted],
        "fieldReferences": results,
        "sourceMethodsRecovered": 0,
        "sourceCodeExecuted": False,
        "limitations": ["valuetype references are not asserted to be enums", "nested/generic/quoted referenced types are unsupported"],
    }
