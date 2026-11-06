"""Conservative source-pinned C# inheritance evidence for architecture classification.

This module reports declarations visible through an explicitly verified class chain. It
is a lexical source aid only: it does not compile C#, resolve `using` aliases, or prove
runtime/engine behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "monkey-code-architecture-inheritance/1"
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_CLASS_RECORDS = 10_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_QUALIFIED_IDENTIFIER = re.compile(r"^@?[A-Za-z_][A-Za-z0-9_]*(?:\.@?[A-Za-z_][A-Za-z0-9_]*)*$")


class InheritanceEvidenceError(ValueError):
    """Malformed or hash-inconsistent evidence; callers must not downgrade this to a miss."""


@dataclass(frozen=True)
class _Member:
    name: str
    kind: str
    accessibility: str
    line: int
    declaration: str


@dataclass(frozen=True)
class _ClassSource:
    record: Mapping[str, Any]
    qualified_name: str
    bases: tuple[str, ...]
    aliases: tuple[str, ...]
    members: Mapping[str, tuple[_Member, ...]]
    blockers: tuple[str, ...]


def _source_bytes(row: Mapping[str, Any], path: str) -> bytes:
    if row.get("path") != path:
        raise InheritanceEvidenceError(f"source mapping path mismatch for {path!r}")
    raw = row.get("source")
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not isinstance(raw, bytes):
        raise InheritanceEvidenceError(f"source mapping for {path!r} needs UTF-8 text or bytes in 'source'")
    if len(raw) > MAX_SOURCE_BYTES:
        raise InheritanceEvidenceError(f"source mapping for {path!r} exceeds the {MAX_SOURCE_BYTES}-byte bound")
    expected = row.get("sha256")
    if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
        raise InheritanceEvidenceError(f"source mapping for {path!r} needs a lowercase SHA-256")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise InheritanceEvidenceError(f"source mapping SHA-256 mismatch for {path!r}")
    if "bytes" in row and row["bytes"] != len(raw):
        raise InheritanceEvidenceError(f"source mapping byte count mismatch for {path!r}")
    return raw


def _mask_non_code(text: str) -> str:
    """Blank comments and literal bodies while preserving offsets, braces, and newlines."""
    out = list(text)
    i = 0
    n = len(text)

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] not in "\r\n":
                out[k] = " "

    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i + 2)
            if j < 0:
                j = n
            blank(i, j)
            i = j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
            continue

        # Recognize regular, verbatim, interpolated, and raw C# string prefixes.
        quote = i
        if text[i] in "$@":
            j = i
            while j < n and text[j] in "$@":
                j += 1
            if j < n and text[j] == '"':
                quote = j
            else:
                quote = -1
        elif text[i] == '"':
            quote = i
        else:
            quote = -1

        if quote >= 0:
            q = quote
            while q < n and text[q] == '"':
                q += 1
            delimiter = q - quote
            if delimiter >= 3:
                close = '"' * delimiter
                end = text.find(close, q)
                end = n if end < 0 else end + delimiter
            else:
                # Adjacent empty string literals `""` are two ordinary delimiters,
                # not a distinct two-quote raw-string form.
                q = quote + 1
                verbatim = "@" in text[i:quote]
                end = q
                while end < n:
                    if text[end] == '"':
                        if verbatim and end + 1 < n and text[end + 1] == '"':
                            end += 2
                            continue
                        end += 1
                        break
                    if not verbatim and text[end] == "\\":
                        end += 2
                    else:
                        end += 1
            blank(i, end)
            i = end
            continue

        if text[i] == "'":
            end = i + 1
            while end < n:
                if text[end] == "\\":
                    end += 2
                elif text[end] == "'":
                    end += 1
                    break
                else:
                    end += 1
            blank(i, min(end, n))
            i = min(end, n)
            continue
        i += 1
    return "".join(out)


def _brace_pairs(mask: str) -> dict[int, int]:
    stack: list[int] = []
    pairs: dict[int, int] = {}
    for index, char in enumerate(mask):
        if char == "{":
            stack.append(index)
        elif char == "}":
            if not stack:
                continue
            opening = stack.pop()
            pairs[opening] = index
    return pairs


def _balanced_braces(mask: str) -> bool:
    depth = 0
    for char in mask:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _namespace_at(mask: str, position: int, pairs: Mapping[int, int]) -> str:
    namespaces: list[tuple[int, int, str]] = []
    pattern = re.compile(r"\bnamespace\s+((?:@?[A-Za-z_][A-Za-z0-9_]*)(?:\s*\.\s*@?[A-Za-z_][A-Za-z0-9_]*)*)\s*([;{])")
    for match in pattern.finditer(mask):
        name = ".".join(part.strip().lstrip("@") for part in match.group(1).split("."))
        if match.group(2) == ";":
            start, end = match.end(), len(mask)
        else:
            opening = match.end() - 1
            end = pairs.get(opening, opening)
            start = opening + 1
        if start <= position < end:
            namespaces.append((start, end, name))
    namespaces.sort(key=lambda item: item[0])
    return ".".join(name for _, _, name in namespaces)


def _split_bases(value: str) -> tuple[str, ...]:
    if not value.strip():
        return ()
    parts: list[str] = []
    start = 0
    angle = square = paren = 0
    for i, char in enumerate(value):
        if char == "<": angle += 1
        elif char == ">": angle -= 1
        elif char == "[": square += 1
        elif char == "]": square -= 1
        elif char == "(": paren += 1
        elif char == ")": paren -= 1
        elif char == "," and angle == square == paren == 0:
            parts.append(value[start:i].strip()); start = i + 1
    parts.append(value[start:].strip())
    return tuple(part for part in parts if part)


def _class_declarations(text: str) -> list[dict[str, Any]]:
    mask = _mask_non_code(text)
    pairs = _brace_pairs(mask)
    pattern = re.compile(r"\bclass\s+(@?[A-Za-z_][A-Za-z0-9_]*)\s*(<[^{};]*>)?([^{};]*)\{")
    declarations: list[dict[str, Any]] = []
    open_ranges: list[tuple[int, int]] = []
    aliases = tuple(match.group(1).lstrip("@") for match in re.finditer(
        r"\b(?:global\s+)?using\s+(@?[A-Za-z_][A-Za-z0-9_]*)\s*=", mask))
    for match in pattern.finditer(mask):
        opening = match.end() - 1
        closing = pairs.get(opening)
        if closing is None:
            continue
        nested = any(a < match.start() < b for a, b in open_ranges)
        open_ranges.append((opening, closing))
        generic = bool(match.group(2))
        header = match.group(3) or ""
        colon = header.find(":")
        bases = _split_bases(header[colon + 1:]) if colon >= 0 else ()
        namespace = _namespace_at(mask, match.start(), pairs)
        prior_delimiters = [mask.rfind(char, 0, match.start()) for char in "{};"]
        declaration_prefix = mask[max(prior_delimiters) + 1:match.start()]
        partial = bool(re.search(r"\bpartial\b", declaration_prefix))
        declarations.append({
            "name": match.group(1).lstrip("@"),
            "namespace": namespace,
            "qualifiedName": f"{namespace}.{match.group(1).lstrip('@')}" if namespace else match.group(1).lstrip("@"),
            "start": match.start(), "open": opening, "close": closing,
            "generic": generic, "partial": partial, "nested": nested, "bases": bases, "aliases": aliases, "mask": mask,
            "text": text, "bracePairs": pairs,
        })
    return declarations


def _strip_attributes(header: str) -> str:
    previous = None
    while previous != header:
        previous = header
        header = re.sub(r"^\s*(?:\[[^\]]*\]\s*)+", "", header, flags=re.S)
    return header.strip()


def _accessibility(header: str) -> str:
    tokens = re.findall(r"\b(public|protected|internal|private)\b", header)
    if not tokens:
        return "private-default"
    if tokens[:2] == ["protected", "internal"] or tokens[:2] == ["internal", "protected"]:
        return "protected-internal"
    if tokens[:2] == ["private", "protected"] or tokens[:2] == ["protected", "private"]:
        return "private-protected"
    return tokens[0]


def _member_from_header(header: str, *, line: int, terminator: str) -> _Member | None:
    header = _strip_attributes(header)
    if not header:
        return None
    if re.search(r"\b(class|struct|interface|enum|delegate)\b", header):
        return None
    # Method declaration (including expression-bodied methods whose header ends at ';').
    method = re.search(r"\b(@?[A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^<>]*>)?\s*\(", header)
    if method:
        name = method.group(1).lstrip("@")
        prefix = header[:method.start()].strip()
        open_paren = header.find("(", method.start())
        paren_depth = 0
        close_paren = -1
        for index in range(open_paren, len(header)):
            if header[index] == "(": paren_depth += 1
            elif header[index] == ")":
                paren_depth -= 1
                if paren_depth == 0:
                    close_paren = index
                    break
        trailing = header[close_paren + 1:].strip() if close_paren >= 0 else "?"
        # A call inside a field initializer (e.g. `Action X = Factory();`) is not a
        # declaration. A block method ends after its parameter list; an expression-body
        # or abstract declaration may have a trailing arrow or no trailer at all.
        initializer_before_call = "=" in prefix
        stripped = re.sub(r"\b(public|protected|internal|private|static|virtual|override|abstract|sealed|new|async|extern|unsafe|partial|readonly|ref|out|in)\b", " ", prefix)
        valid_trailer = not trailing or trailing.startswith("=>")
        if stripped.strip() and valid_trailer and not initializer_before_call:
            access = _accessibility(header)
            return _Member(name, "method", access, line, header.strip())
    # Expression-bodied property; distinguish it from a lambda in a field initializer.
    if terminator == ";" and "=>" in header:
        arrow = header.find("=>")
        before_arrow = header[:arrow].strip()
        property_match = re.search(r"\b(@?[A-Za-z_][A-Za-z0-9_]*)\s*$", before_arrow)
        if property_match and "=" not in before_arrow:
            prefix = before_arrow[:property_match.start()].strip()
            stripped = re.sub(r"\b(public|protected|internal|private|static|virtual|override|abstract|sealed|new|async|extern|unsafe|partial|readonly|required|ref|volatile)\b", " ", prefix)
            if stripped.strip():
                return _Member(property_match.group(1).lstrip("@"), "property", _accessibility(header), line, header.strip())
    # Property declaration: its opening brace terminates the member header.
    property_match = re.search(r"\b(@?[A-Za-z_][A-Za-z0-9_]*)\s*$", header) if terminator == "{" else None
    if property_match:
        name = property_match.group(1).lstrip("@")
        prefix = header[:property_match.start()].strip()
        stripped = re.sub(r"\b(public|protected|internal|private|static|virtual|override|abstract|sealed|new|async|extern|unsafe|partial|readonly|required|ref|volatile)\b", " ", prefix)
        if stripped.strip():
            kind = "event" if re.search(r"\bevent\b", header) else "property"
            return _Member(name, kind, _accessibility(header), line, header.strip())
    # Field/event declarator; discard initializer before looking for the declared name.
    field_header = re.split(r"=(?!=)", header, maxsplit=1)[0].strip()
    field_match = re.search(r"\b(@?[A-Za-z_][A-Za-z0-9_]*)\s*$", field_header)
    if field_match:
        name = field_match.group(1).lstrip("@")
        prefix = field_header[:field_match.start()].strip()
        stripped = re.sub(r"\b(public|protected|internal|private|static|virtual|override|abstract|sealed|new|async|extern|unsafe|partial|readonly|required|ref|volatile|const|event)\b", " ", prefix)
        if stripped.strip():
            kind = "event" if re.search(r"\bevent\b", header) else "field"
            return _Member(name, kind, _accessibility(header), line, header.strip())
    return None


def _split_declarators(header: str) -> list[str]:
    parts: list[str] = []
    start = 0
    angle = square = paren = bracket = 0
    for index, char in enumerate(header):
        if char == "<": angle += 1
        elif char == ">": angle = max(0, angle - 1)
        elif char == "[": square += 1
        elif char == "]": square = max(0, square - 1)
        elif char == "(": paren += 1
        elif char == ")": paren = max(0, paren - 1)
        elif char == "{": bracket += 1
        elif char == "}": bracket = max(0, bracket - 1)
        elif char == "," and angle == square == paren == bracket == 0:
            parts.append(header[start:index].strip())
            start = index + 1
    parts.append(header[start:].strip())
    return parts


def _field_members_from_header(header: str, *, line: int) -> list[_Member]:
    parts = _split_declarators(header)
    if len(parts) < 2:
        member = _member_from_header(header, line=line, terminator=";")
        return [member] if member and member.kind in ("field", "event") else []
    result: list[_Member] = []
    for index, part in enumerate(parts):
        declaration = re.split(r"=(?!=)", part, maxsplit=1)[0].strip()
        if index == 0:
            match = re.search(r"\b(@?[A-Za-z_][A-Za-z0-9_]*)\s*$", declaration)
            if not match:
                return []
            name = match.group(1).lstrip("@")
            prefix = declaration[:match.start()].strip()
            stripped = re.sub(r"\b(public|protected|internal|private|static|virtual|override|abstract|sealed|new|async|extern|unsafe|partial|readonly|required|ref|volatile|const|event)\b", " ", prefix)
            if not stripped.strip():
                return []
            access = _accessibility(header)
            kind = "event" if re.search(r"\bevent\b", header) else "field"
        else:
            match = re.match(r"(@?[A-Za-z_][A-Za-z0-9_]*)", declaration)
            if not match:
                return []
            name = match.group(1).lstrip("@")
        result.append(_Member(name, kind, access, line, header.strip()))
    return result


def _direct_members(text: str, declaration: Mapping[str, Any]) -> tuple[dict[str, tuple[_Member, ...]], list[str]]:
    mask = declaration["mask"]
    start, end = declaration["open"] + 1, declaration["close"]
    depth = 1
    segment_start = start
    members: dict[str, list[_Member]] = {}
    blockers: list[str] = []
    i = start
    while i < end:
        char = mask[i]
        if char == "{":
            if depth == 1:
                header = mask[segment_start:i]
                # Properties and methods open blocks; nested types are intentionally ignored.
                first = re.search(r'\S', header)
                line = text.count("\n", 0, segment_start + (first.start() if first else 0)) + 1
                member = _member_from_header(header, line=line, terminator="{")
                if member:
                    members.setdefault(member.name, []).append(member)
                elif header.strip() and not re.search(r"\b(class|struct|interface|enum|delegate)\b", header):
                    constructor = re.search(r"\b(@?[A-Za-z_][A-Za-z0-9_]*)\s*\(.*\)\s*$", header, re.S)
                    ctor_name = declaration["name"]
                    if not (constructor and constructor.group(1).lstrip("@") == ctor_name):
                        blockers.append("unsupported_member_declaration")
                block_end = declaration["bracePairs"].get(i)
                if block_end is None or block_end >= end:
                    blockers.append("unbalanced_member_body")
                    break
                i = block_end + 1
                segment_start = i
                # An auto-property may have an initializer after its accessor body:
                # `public int Index { get; private set; } = -1;`. Consume that
                # initializer as part of the property instead of treating `= -1` as
                # a separate unsupported declaration.
                while i < end and mask[i].isspace():
                    i += 1
                if i < end and mask[i] == "=":
                    while i < end and mask[i] != ";":
                        i += 1
                    if i < end:
                        i += 1
                    segment_start = i
                continue
            depth += 1
        elif char == "}" and depth > 1:
            depth -= 1
        elif char == ";" and depth == 1:
            header = mask[segment_start:i]
            first = re.search(r'\S', header)
            line = text.count("\n", 0, segment_start + (first.start() if first else 0)) + 1
            member = _member_from_header(header, line=line, terminator=";")
            if member and member.kind in ("field", "event"):
                declarations = _field_members_from_header(header, line=line)
                if declarations:
                    for field_member in declarations:
                        members.setdefault(field_member.name, []).append(field_member)
                else:
                    blockers.append("unsupported_field_declaration")
            elif member:
                members.setdefault(member.name, []).append(member)
            elif header.strip():
                blockers.append("unsupported_member_declaration")
            segment_start = i + 1
        i += 1
    return {name: tuple(rows) for name, rows in members.items()}, blockers


def _canonical_base(base: str, namespace: str) -> tuple[str | None, str | None]:
    value = re.sub(r"\s+", "", base)
    if not value or "<" in value or ">" in value or "[" in value or "]" in value or "?" in value:
        return None, "unsupported_generic_or_complex_base"
    if value.startswith("global::"):
        value = value[len("global::"):]
    elif "::" in value:
        return None, "unsupported_alias_qualified_base"
    value = value.replace("@", "")
    if not _QUALIFIED_IDENTIFIER.fullmatch(value):
        return None, "unsupported_base_syntax"
    if "." not in value and namespace:
        value = namespace + "." + value
    return value, None


def _record_value(record: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in record:
            return record[name]
    return None


def resolve_inherited_members(
    class_records: Sequence[Mapping[str, Any]],
    source_mappings: Mapping[str, Mapping[str, Any]],
    required_members: Mapping[str, Sequence[str] | Mapping[str, str]],
    *,
    max_depth: int = 8,
) -> dict[str, Any]:
    """Resolve direct/inherited C# member declarations using only pinned source inputs.

    A record requires `classId`, `name`, `namespace`, `kind`, `path`, and `sha256`.
    A source mapping is keyed by the exact path and contains `path`, `sha256`, and
    `source` (UTF-8 text or bytes); optional `bytes` is checked as well. Requirements map
    class IDs to member-name sequences or `{name: expected_kind}` mappings.

    Unqualified base names resolve only within the declaring namespace. Fully qualified
    base names resolve exactly. No using/alias, reflection, naming-convention, or external
    API resolution is performed. Positive member evidence remains usable when a separate
    terminal base is unresolved; unresolved edges are always listed.
    """
    if type(max_depth) is not int or max_depth < 1 or max_depth > 64:
        raise InheritanceEvidenceError("max_depth must be an integer between 1 and 64")
    if not isinstance(class_records, Sequence) or isinstance(class_records, (str, bytes)):
        raise InheritanceEvidenceError("class_records must be a sequence of mappings")
    if not isinstance(source_mappings, Mapping) or not isinstance(required_members, Mapping):
        raise InheritanceEvidenceError("source_mappings and required_members must be mappings")

    if len(class_records) > MAX_CLASS_RECORDS:
        raise InheritanceEvidenceError(f"class_records exceeds the {MAX_CLASS_RECORDS}-record bound")
    records_by_id: dict[str, Mapping[str, Any]] = {}
    records_by_qname: dict[str, list[Mapping[str, Any]]] = {}
    for record in class_records:
        if not isinstance(record, Mapping):
            raise InheritanceEvidenceError("every class record must be a mapping")
        class_id = _record_value(record, "classId", "id")
        name = record.get("name")
        namespace = record.get("namespace", "")
        kind = record.get("kind")
        path = _record_value(record, "path", "sourcePath")
        digest = _record_value(record, "sha256", "sourceSha256")
        if not all(isinstance(value, str) and value for value in (class_id, name, path)):
            raise InheritanceEvidenceError("class records require nonempty classId, name, and path")
        if class_id in records_by_id:
            raise InheritanceEvidenceError(f"duplicate classId {class_id!r}")
        if not isinstance(namespace, str) or not isinstance(kind, str):
            raise InheritanceEvidenceError(f"class record {class_id!r} needs namespace and kind")
        if kind != "class":
            raise InheritanceEvidenceError(f"class record {class_id!r} is not kind 'class'")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise InheritanceEvidenceError(f"class record {class_id!r} needs a lowercase SHA-256")
        if path.startswith("/") or ".." in path.replace("\\", "/").split("/"):
            raise InheritanceEvidenceError(f"unsafe source path {path!r}")
        records_by_id[class_id] = record
        qname = f"{namespace}.{name}" if namespace else name
        records_by_qname.setdefault(qname, []).append(record)

    parsed: dict[str, _ClassSource] = {}
    initial_blockers: dict[str, list[str]] = {}
    for class_id, record in records_by_id.items():
        path = _record_value(record, "path", "sourcePath")
        mapping = source_mappings.get(path)
        if not isinstance(mapping, Mapping):
            initial_blockers[class_id] = ["missing_source_mapping"]
            continue
        raw = _source_bytes(mapping, path)
        record_hash = _record_value(record, "sha256", "sourceSha256")
        if hashlib.sha256(raw).hexdigest() != record_hash:
            raise InheritanceEvidenceError(f"class record SHA-256 mismatch for {class_id!r}")
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise InheritanceEvidenceError(f"source {path!r} is not valid UTF-8") from exc
        source_mask = _mask_non_code(text)
        if re.search(r'(?m)^\s*#\s*(?:if|elif|else|endif|define|undef)\b', source_mask):
            initial_blockers[class_id] = ["conditional_compilation_unsupported"]
            continue
        if not _balanced_braces(source_mask):
            initial_blockers[class_id] = ["unbalanced_source_braces"]
            continue
        declarations = _class_declarations(text)
        expected_name = record["name"]
        expected_namespace = record.get("namespace", "")
        matches = [d for d in declarations if not d["nested"] and d["name"] == expected_name and d["namespace"] == expected_namespace]
        if len(matches) != 1:
            initial_blockers[class_id] = ["class_declaration_missing" if not matches else "class_declaration_ambiguous"]
            continue
        declaration = matches[0]
        blockers: list[str] = []
        if declaration["generic"]:
            blockers.append("generic_class_unsupported")
        if declaration["partial"]:
            blockers.append("partial_class_unsupported")
        direct, member_blockers = _direct_members(text, declaration)
        blockers.extend(member_blockers)
        qname = f"{expected_namespace}.{expected_name}" if expected_namespace else expected_name
        parsed[class_id] = _ClassSource(record, qname, declaration["bases"], declaration["aliases"], direct, tuple(blockers))

    results: list[dict[str, Any]] = []
    for class_id, record in records_by_id.items():
        requirements = required_members.get(class_id, ())
        if isinstance(requirements, Mapping):
            wanted = {name: kind for name, kind in requirements.items()}
        elif isinstance(requirements, Sequence) and not isinstance(requirements, (str, bytes)):
            wanted = {name: None for name in requirements}
        else:
            raise InheritanceEvidenceError(f"requirements for {class_id!r} must be a sequence or mapping")
        if any(not isinstance(name, str) or not name for name in wanted):
            raise InheritanceEvidenceError(f"requirements for {class_id!r} contain an invalid member name")
        if any(kind not in (None, "method", "field", "property", "event") for kind in wanted.values()):
            raise InheritanceEvidenceError(f"requirements for {class_id!r} contain an unsupported member kind")

        chain: list[dict[str, Any]] = []
        unresolved: list[dict[str, str]] = []
        blockers = list(initial_blockers.get(class_id, ()))
        resolved_members: dict[str, dict[str, Any]] = {}
        if class_id not in parsed:
            results.append({"classId": class_id, "qualifiedName": f"{record.get('namespace','')}.{record['name']}".strip("."),
                "resolution": "unresolved", "requiredMembers": {name: {"satisfied": False} for name in wanted},
                "baseShaChain": chain, "unresolvedBases": unresolved, "blockers": blockers})
            continue

        current_id = class_id
        visited: set[str] = set()
        depth = 0
        while current_id:
            if current_id in visited:
                blockers.append("inheritance_cycle")
                break
            if depth >= max_depth:
                blockers.append("maximum_inheritance_depth_exceeded")
                break
            visited.add(current_id)
            current = parsed.get(current_id)
            if current is None:
                blocker_rows = initial_blockers.get(current_id, ["base_source_unavailable"])
                blockers.extend(blocker_rows)
                unavailable_record = records_by_id.get(current_id)
                if unavailable_record is not None:
                    unresolved.append({
                        "declaredBy": chain[-1]["classId"] if chain else class_id,
                        "type": f"{unavailable_record.get('namespace', '')}.{unavailable_record['name']}".strip("."),
                        "classId": current_id,
                        "path": _record_value(unavailable_record, "path", "sourcePath"),
                        "sha256": _record_value(unavailable_record, "sha256", "sourceSha256"),
                        "reason": blocker_rows[0],
                    })
                break
            digest = _record_value(current.record, "sha256", "sourceSha256")
            path = _record_value(current.record, "path", "sourcePath")
            chain.append({"classId": current_id, "qualifiedName": current.qualified_name, "path": path, "sha256": digest})
            blockers.extend(x for x in current.blockers if x not in blockers)

            for member_name, expected_kind in wanted.items():
                if member_name in resolved_members:
                    continue
                declarations = current.members.get(member_name, ())
                if not declarations:
                    continue
                visible = [m for m in declarations if m.accessibility in ("public", "protected", "protected-internal")]
                if visible:
                    matching = [m for m in visible if expected_kind is None or m.kind == expected_kind]
                    if matching:
                        m = matching[0]
                        resolved_members[member_name] = {
                            "satisfied": True,
                            "kind": m.kind,
                            "accessibility": m.accessibility,
                            "declaredBy": current_id,
                            "sourcePath": path,
                            "sourceSha256": digest,
                            "line": m.line,
                            "declaration": m.declaration,
                        }
                    else:
                        resolved_members[member_name] = {"satisfied": False, "reason": "member_kind_mismatch", "declaredBy": current_id}
                        blockers.append(f"member_kind_mismatch:{member_name}")
                else:
                    resolved_members[member_name] = {"satisfied": False, "reason": "private_declaration_shadows_base", "declaredBy": current_id}
                    blockers.append(f"private_declaration_not_inherited:{member_name}")

            if current.blockers:
                break
            if not current.bases:
                break
            known_bases: list[str] = []
            for raw_base in current.bases:
                if "." not in raw_base and raw_base.lstrip("@").strip() in current.aliases:
                    unresolved.append({"declaredBy": current_id, "type": raw_base, "reason": "base_name_is_using_alias"})
                    continue
                base_qname, base_error = _canonical_base(raw_base, current.record.get("namespace", ""))
                if base_error:
                    blockers.append(f"{base_error}:{raw_base}")
                    continue
                candidates = records_by_qname.get(base_qname, [])
                if len(candidates) > 1:
                    blockers.append(f"ambiguous_base_class:{base_qname}")
                    continue
                if len(candidates) == 1:
                    candidate_id = _record_value(candidates[0], "classId", "id")
                    known_bases.append(candidate_id)
                else:
                    unresolved.append({"declaredBy": current_id, "type": raw_base, "reason": "no_exact_class_record"})
            if len(known_bases) > 1:
                blockers.append("multiple_known_class_bases")
                break
            if blockers and any(x.startswith(("unsupported_", "ambiguous_base_class", "multiple_known_class_bases")) for x in blockers):
                break
            if not known_bases:
                break
            current_id = known_bases[0]
            depth += 1

        for name in wanted:
            resolved_members.setdefault(name, {"satisfied": False, "reason": "no_visible_declaration_in_verified_chain"})
        found = sum(1 for item in resolved_members.values() if item.get("satisfied"))
        all_found = found == len(wanted)
        resolution = "complete" if all_found and not blockers and not unresolved else "partial" if found else "unresolved"
        results.append({
            "classId": class_id,
            "qualifiedName": f"{record.get('namespace','')}.{record['name']}".strip("."),
            "resolution": resolution,
            "requiredMembers": resolved_members,
            "baseShaChain": chain,
            "unresolvedBases": unresolved,
            "blockers": sorted(set(blockers)),
        })

    return {"schemaVersion": SCHEMA_VERSION, "results": results}
