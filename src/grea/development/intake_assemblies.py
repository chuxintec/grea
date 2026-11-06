"""Read-only retained assembly and source-subset validation for intake spec 5.

This module proves only a static declaration boundary. It does not compile C#,
resolve CLR types, or claim that a schema-only source reproduces original
runtime behavior.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .errors import fail
from .io import inside, load, read, sha

MAX_SOURCE_BYTES = 1024 * 1024
MAX_ASMDEF_BYTES = 1024 * 1024
MAX_ASSEMBLIES = 16
_SHA = re.compile(r"^[a-f0-9]{64}$")
_GUID = re.compile(r"^[a-f0-9]{32}$")
_META_GUID = re.compile(rb"^guid:\s*([a-f0-9]{32})\s*$", re.M)
_IDENTIFIER_START = {"Lu", "Ll", "Lt", "Lm", "Lo", "Nl"}
_IDENTIFIER_PART = _IDENTIFIER_START | {"Mn", "Mc", "Nd", "Pc", "Cf"}
_KEYWORDS = {
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char", "checked", "class", "const",
    "continue", "decimal", "default", "delegate", "do", "double", "else", "enum", "event", "explicit", "extern",
    "false", "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit", "in", "int", "interface",
    "internal", "is", "lock", "long", "namespace", "new", "null", "object", "operator", "out", "override",
    "params", "private", "protected", "public", "readonly", "ref", "return", "sbyte", "sealed", "short", "sizeof",
    "stackalloc", "static", "string", "struct", "switch", "this", "throw", "true", "try", "typeof", "uint",
    "ulong", "unchecked", "unsafe", "ushort", "using", "virtual", "void", "volatile", "while",
}
_ALIASES = {
    "bool": "System.Boolean", "byte": "System.Byte", "sbyte": "System.SByte", "char": "System.Char",
    "decimal": "System.Decimal", "double": "System.Double", "float": "System.Single", "int": "System.Int32",
    "uint": "System.UInt32", "long": "System.Int64", "ulong": "System.UInt64", "short": "System.Int16",
    "ushort": "System.UInt16", "object": "System.Object", "string": "System.String",
}
_WIN_BAD = set('<>:"|?*')
_WIN_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?\Z", re.IGNORECASE)


def _retained_error(kind, where, message):
    fail("INTAKE_RETAINED_ASSEMBLY_" + kind, where, message)


def _source_error(where, message):
    fail("INTAKE_NEW_SCRIPT_SCHEMA", where, message)


def _exact(row, keys, where):
    if not isinstance(row, dict) or set(row) != set(keys):
        _retained_error("FIELDS", where, "Exact retained assembly fields required")


def _source_path(value, suffix, where):
    if (not isinstance(value, str) or not value.startswith("Assets/") or "\\" in value or ":" in value
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)
            or unicodedata.normalize("NFC", value) != value
            or any(part in ("", ".", "..") for part in value.split("/"))
            or not value.lower().endswith(suffix)):
        _retained_error("PATH", where, "Canonical Assets path with the required suffix expected")
    return value


def _simple_name(value, where, *, source=False):
    prefix = "INTAKE_NEW_SCRIPT_SCHEMA" if source else "INTAKE_RETAINED_ASSEMBLY_NAME"
    if (not isinstance(value, str) or not value or value in (".", "..")
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", value) or value.lower().endswith(".dll")):
        fail(prefix, where, "Simple assembly/name identifier required")
    return value


def _read_target_file(target, before, path, limit, where):
    entry = before.get(path)
    if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str) or not _SHA.fullmatch(entry["sha256"]):
        _retained_error("PIN", where, "Pinned target file is missing from targetBefore")
    try: raw = read(inside(target, path), max_bytes=limit)
    except Exception: _retained_error("PIN", where, "Pinned target file cannot be read safely")
    if sha(raw) != entry["sha256"]:
        _retained_error("PIN", where, "Target file differs from its targetBefore hash")
    if type(entry.get("bytes")) is int and entry["bytes"] != len(raw):
        _retained_error("PIN", where, "Target file size differs from its targetBefore record")
    return raw


def _read_candidate_file(incoming, files, path, expected_sha, limit, where):
    entry = files.get(path)
    if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str) or not _SHA.fullmatch(entry["sha256"]):
        _source_error(where, "Candidate path is absent from the verified frozen manifest")
    try: raw = read(inside(incoming, path), max_bytes=limit)
    except Exception: _source_error(where, "Candidate source cannot be read safely")
    if sha(raw) != entry["sha256"] or (expected_sha is not None and sha(raw) != expected_sha):
        _source_error(where, "Candidate bytes differ from the manifest/reviewed pin")
    if type(entry.get("bytes")) is int and entry["bytes"] != len(raw):
        _source_error(where, "Candidate byte count differs from its manifest")
    return raw


def _meta_guid(raw, where, *, source=False):
    found = _META_GUID.findall(raw)
    error = _source_error if source else lambda w, m: _retained_error("GUID", w, m)
    if len(found) != 1:
        error(where, "Exactly one lowercase Unity GUID is required in metadata")
    return found[0].decode("ascii")


def _name(raw, where, *, source=False):
    try: doc = load(raw, max_nodes=20000, max_depth=32)
    except Exception:
        if source: _source_error(where, "Assembly definition is not bounded valid JSON")
        _retained_error("ASMDEF", where, "Assembly definition is not bounded valid JSON")
    if not isinstance(doc, dict):
        if source: _source_error(where, "Assembly definition JSON object required")
        _retained_error("ASMDEF", where, "Assembly definition JSON object required")
    name = doc.get("name")
    if source:
        return _simple_name(name, where + ".name", source=True)
    return _simple_name(name, where + ".name")


def _is_start(ch):
    return ch == "_" or unicodedata.category(ch) in _IDENTIFIER_START


def _is_part(ch):
    return _is_start(ch) or unicodedata.category(ch) in _IDENTIFIER_PART


def _lex_source(raw, where):
    if len(raw) > MAX_SOURCE_BYTES:
        _source_error(where, "C# source exceeds the schema-only parser byte budget")
    try: text = raw.decode("utf-8-sig")
    except UnicodeError: _source_error(where, "C# source must be valid UTF-8")
    if "\x00" in text: _source_error(where, "NUL is forbidden in C# source")
    tokens = []; i = 0; size = len(text)

    def quoted(start, quote, verbatim=False, raw_quotes=0):
        j = start + (raw_quotes if raw_quotes else 1)
        while j < size:
            if raw_quotes:
                if text.startswith('"' * raw_quotes, j): return j + raw_quotes
                j += 1; continue
            ch = text[j]
            if verbatim and ch == '"':
                if j + 1 < size and text[j + 1] == '"': j += 2; continue
                return j + 1
            if ch == "\\" and not verbatim:
                j += 2; continue
            if ch == quote: return j + 1
            if ch in "\r\n" and not verbatim:
                _source_error(where, "Regular C# string/character literal cannot cross a line")
            j += 1
        _source_error(where, "Unterminated C# string/character literal")

    while i < size:
        ch = text[i]
        if ch.isspace(): i += 1; continue
        if text.startswith("//", i):
            end = text.find("\n", i + 2); i = size if end < 0 else end + 1; continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0: _source_error(where, "Unterminated block comment")
            i = end + 2; continue
        if ch == "#": _source_error(where, "Preprocessor directives are outside the schema-only grammar")
        if ch == "@" and i + 1 < size and text[i + 1] == '"':
            tokens.append(("literal", "")); i = quoted(i + 1, '"', verbatim=True); continue
        if ch in ('"', "'"):
            run = 0
            if ch == '"':
                while i + run < size and text[i + run] == '"': run += 1
            if ch == '"' and run >= 3:
                tokens.append(("literal", "")); i = quoted(i, '"', raw_quotes=run); continue
            tokens.append(("literal", "")); i = quoted(i, ch); continue
        if _is_start(ch):
            start = i; i += 1
            while i < size and _is_part(text[i]): i += 1
            tokens.append(text[start:i]); continue
        if ch.isdigit():
            start = i; i += 1
            while i < size and (text[i].isalnum() or text[i] in "._"):
                i += 1
            tokens.append(("number", text[start:i])); continue
        tokens.append(ch); i += 1
        if len(tokens) > 20000: _source_error(where, "C# source exceeds the token budget")
    return tokens


class _Parser:
    def __init__(self, tokens, where): self.tokens = tokens; self.i = 0; self.where = where
    def peek(self): return self.tokens[self.i] if self.i < len(self.tokens) else None
    def take(self, expected=None):
        token = self.peek()
        if token is None or (expected is not None and token != expected):
            _source_error(self.where, f"Expected {expected!r}, found {token!r}")
        self.i += 1
        return token
    def identifier(self):
        token = self.peek()
        if not isinstance(token, str) or not _is_start(token[0]) or any(not _is_part(ch) for ch in token[1:]) or token in _KEYWORDS:
            _source_error(self.where, f"C# identifier required, found {token!r}")
        self.i += 1
        return token
    def qualified(self):
        parts = [self.identifier()]
        while self.peek() == ".":
            self.take("."); parts.append(self.identifier())
        return ".".join(parts)
    def type_name(self, *, aliases=True, arrays=True):
        first = self.peek()
        if aliases and isinstance(first, str) and first in _ALIASES:
            self.i += 1; name = _ALIASES[first]
        else:
            name = self.qualified()
        if arrays:
            while self.peek() == "[":
                self.take("["); self.take("]"); name += "[]"
        return name


def _parse_type_text(value, where):
    if not isinstance(value, str) or not value:
        _source_error(where, "Nonempty field type required")
    parser = _Parser(_lex_source(value.encode("utf-8"), where), where)
    name = parser.type_name()
    if parser.peek() is not None: _source_error(where, "Unsupported C# type syntax")
    return name


def _parse_script(raw, script, where):
    tokens = _lex_source(raw, where); parser = _Parser(tokens, where)
    while parser.peek() == "using":
        parser.take("using"); parser.qualified(); parser.take(";")
    namespace = None
    if parser.peek() == "namespace":
        parser.take("namespace"); namespace = parser.qualified(); parser.take("{")
    parser.take("public"); parser.take("class")
    class_name = parser.identifier()
    target_type = script.get("targetType")
    if not isinstance(target_type, str) or not target_type:
        _source_error(where, "Exact targetType is required")
    expected_namespace, dot, expected_class = target_type.rpartition(".")
    expected_namespace = expected_namespace if dot else None
    if class_name != expected_class or namespace != expected_namespace:
        _source_error(where, "Class and namespace must exactly match targetType")
    parser.take(":")
    base_type = parser.type_name(aliases=False, arrays=False)
    if base_type != script.get("baseType"):
        _source_error(where, "Base type must exactly match the reviewed baseType")
    parser.take("{")
    declared_fields = []
    while parser.peek() != "}":
        parser.take("public")
        field_type = parser.type_name()
        field_name = parser.identifier()
        parser.take(";")
        declared_fields.append((field_name, field_type))
    parser.take("}")
    if namespace is not None: parser.take("}")
    if parser.peek() is not None: _source_error(where, "Only one public class and optional namespace block are permitted")
    fields = script.get("fields")
    if not isinstance(fields, list): _source_error(where, "Reviewed field list required")
    reviewed = []; reviewed_names = set()
    for index, field in enumerate(fields):
        if not isinstance(field, dict) or set(field) != {"name", "type", "assembly"}:
            _source_error(f"{where}.fields[{index}]", "Exact field name/type/assembly tuple required")
        if not isinstance(field["name"], str) or not field["name"] or not isinstance(field["assembly"], str) or not field["assembly"]:
            _source_error(f"{where}.fields[{index}]", "Nonempty reviewed field name and assembly required")
        _simple_name(field["assembly"], f"{where}.fields[{index}].assembly", source=True)
        if field["name"] in reviewed_names:
            _source_error(f"{where}.fields[{index}].name", "Reviewed field names must be unique")
        reviewed_names.add(field["name"])
        reviewed.append((field["name"], _parse_type_text(field["type"], f"{where}.fields[{index}].type")))
    if declared_fields != reviewed:
        _source_error(where, "Public field declarations must exactly match reviewed field names/types and order")


def _canonical_path(value, suffix, kind, where):
    if (not isinstance(value, str) or not value.startswith("Assets/") or "\\" in value or ":" in value
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)
            or any(part in ("", ".", "..") for part in value.split("/"))
            or unicodedata.normalize("NFC", value) != value or not value.lower().endswith(suffix)
            or any(part.endswith((".", " ")) or any(ch in _WIN_BAD for ch in part) or _WIN_RESERVED.fullmatch(part)
                   for part in value.split("/"))):
        if kind == "SCRIPT": _source_error(where, "Canonical Assets path with exact compiler suffix required")
        _retained_error(kind, where, "Canonical Assets path with exact compiler suffix required")
    return value


def _ancestor_dirs(path):
    parts = path.split("/")[:-1]
    return {"/".join(parts[:index]) for index in range(1, len(parts) + 1)}


def _asmdef_paths(inventory):
    return sorted(path for path in inventory if isinstance(path, str) and path.startswith("Assets/") and path.lower().endswith(".asmdef"))


def _asmref_paths(inventory):
    return sorted(path for path in inventory if isinstance(path, str) and path.startswith("Assets/") and path.lower().endswith(".asmref"))


def _asmdef_name(raw, path, *, candidate):
    try: value = load(raw, max_nodes=20000, max_depth=32)
    except Exception:
        if candidate: _source_error(path, "Candidate asmdef must be bounded valid JSON")
        _retained_error("ASMDEF", path, "Target asmdef must be bounded valid JSON")
    if not isinstance(value, dict) or not isinstance(value.get("name"), str) or not value["name"]:
        if candidate: _source_error(path, "Candidate asmdef JSON name is required")
        _retained_error("ASMDEF", path, "Target asmdef JSON name is required")
    _simple_name(value["name"], path + ".name", source=candidate)
    return value["name"]


def _inventory_asmdefs(incoming, files, target, before):
    candidate_names = {}; target_names = {}; candidate_name_by_path = {}; target_scopes = {}
    for path in _asmdef_paths(files):
        raw = _read_candidate_file(incoming, files, path, None, MAX_ASMDEF_BYTES, path)
        name = _asmdef_name(raw, path, candidate=True)
        key = name.casefold()
        if key in candidate_names and candidate_names[key] != path:
            _source_error(path, "Candidate Assets asmdef names must be unique under case-folding")
        candidate_names[key] = path
        candidate_name_by_path[path] = name
    for path in _asmdef_paths(before):
        raw = _read_target_file(target, before, path, MAX_ASMDEF_BYTES, path)
        name = _asmdef_name(raw, path, candidate=False)
        key = name.casefold()
        if key in target_names and target_names[key] != path:
            _retained_error("NAME_DUPLICATE", path, "Target Assets asmdef names must be unique under case-folding")
        target_names[key] = path
        target_scopes.setdefault(path.rpartition("/")[0], []).append(path)
    return candidate_name_by_path, target_scopes


def _source_scope(path, asmdefs, asmrefs, where):
    ancestors = _ancestor_dirs(path)
    refs = [p for p in asmrefs if p.rpartition("/")[0] in ancestors]
    if refs: _retained_error("CANDIDATE_ASMREF", where, "Candidate source is under an asmref scope")
    scopes = [p for p in asmdefs if p.rpartition("/")[0] in ancestors]
    if len(scopes) != 1:
        _retained_error("CANDIDATE_SCOPE", where, "Exactly one candidate asmdef scope is permitted for a named source")
    return scopes[0]


def _target_scope(path, asmdefs, asmrefs, target_scopes, where, default):
    ancestors = _ancestor_dirs(path)
    refs = [p for p in asmrefs if p.rpartition("/")[0] in ancestors]
    scopes = [p for p in asmdefs if p.rpartition("/")[0] in ancestors]
    if refs: _retained_error("TARGET_ASMREF", where, "New target path is under an asmref scope")
    if default:
        if scopes: _retained_error("DEFAULT_SCOPE", where, "Assembly-CSharp targets cannot be under an asmdef scope")
        return None
    if not scopes: _retained_error("TARGET_SCOPE", where, "Named target assembly has no existing asmdef scope")
    max_depth = max(p.rpartition("/")[0].count("/") for p in scopes)
    nearest = [p for p in scopes if p.rpartition("/")[0].count("/") == max_depth]
    nearest_dir = nearest[0].rpartition("/")[0]
    if len(target_scopes.get(nearest_dir, ())) != 1 or len(nearest) != 1:
        _retained_error("TARGET_SCOPE", where, "Multiple asmdef scopes in the nearest target directory are ambiguous")
    return nearest[0]


def validate(spec, incoming, files, target, before, existing_guids):
    """Return the original retainedAssemblies rows after static, read-only checks.

    The caller supplies the verified candidate inventory, target before-image,
    and GUID index. No files are changed. Non-v5 specs return an empty list so
    older intake contracts retain their existing behavior.
    """
    if not isinstance(spec, dict):
        _retained_error("SPEC", "spec", "Spec object required")
    if spec.get("schemaVersion") != 5:
        return []
    incoming = Path(incoming); target = Path(target)
    if not isinstance(files, dict) or not isinstance(before, dict) or not isinstance(existing_guids, dict):
        _retained_error("INPUT", "inventory", "Candidate and target inventories are required")
    rows = spec.get("retainedAssemblies", [])
    if not isinstance(rows, list) or len(rows) > MAX_ASSEMBLIES:
        _retained_error("BOUNDS", "retainedAssemblies", "At most 16 retained assembly rows are allowed")
    scripts = spec.get("newScripts", [])
    if not isinstance(scripts, list) or len(scripts) > 16:
        _source_error("newScripts", "At most 16 schema-only scripts are allowed")

    row_names = {}; row_targets = {}; used_rows = set()
    for index, row in enumerate(rows):
        where = f"retainedAssemblies[{index}]"
        _exact(row, {"target", "guid", "sha256", "metaSha256", "name"}, where)
        path = _canonical_path(row["target"], ".asmdef", "PATH", where + ".target")
        guid = row["guid"]
        if not isinstance(guid, str) or not _GUID.fullmatch(guid): _retained_error("GUID", where + ".guid", "Lowercase Unity GUID required")
        for field in ("sha256", "metaSha256"):
            if not isinstance(row[field], str) or not _SHA.fullmatch(row[field]): _retained_error("PIN", where + "." + field, "Lowercase SHA-256 required")
        name = _simple_name(row["name"], where + ".name")
        key = name.casefold()
        if key in row_names: _retained_error("NAME_DUPLICATE", where, "Retained assembly names must be unique under case-folding")
        if path.casefold() in {p.casefold() for p in row_targets.values()}:
            _retained_error("TARGET_DUPLICATE", where, "Retained assembly targets must be unique")
        row_names[key] = row; row_targets[name] = path
        if existing_guids.get(guid) != [path]:
            _retained_error("GUID_IDENTITY", where, "GUID must identify exactly this retained target path")
        file_raw = _read_target_file(target, before, path, MAX_ASMDEF_BYTES, where + ".target")
        meta_path = path + ".meta"
        meta_raw = _read_target_file(target, before, meta_path, 256 * 1024, where + ".meta")
        if sha(file_raw) != row["sha256"] or sha(meta_raw) != row["metaSha256"]:
            _retained_error("PIN", where, "Retained asmdef bytes/meta differ from reviewed hashes")
        if _meta_guid(meta_raw, where + ".meta") != guid:
            _retained_error("GUID_IDENTITY", where, "Retained asmdef metadata GUID differs from declaration")
        if _asmdef_name(file_raw, path, candidate=False) != name:
            _retained_error("NAME_IDENTITY", where, "Retained asmdef JSON name differs from declaration")

    candidate_asmdefs = _asmdef_paths(files); candidate_asmrefs = _asmref_paths(files)
    target_asmdefs = _asmdef_paths(before); target_asmrefs = _asmref_paths(before)
    candidate_name_by_path, target_scope_dirs = _inventory_asmdefs(incoming, files, target, before)
    # Keep all before-image asmdef parsing/pinning even if no named script uses a
    # given definition: duplicate identities and malformed scopes are globally
    # ambiguous within the Assets tree.
    candidate_script_sources = {}
    for index, script in enumerate(scripts):
        where = f"newScripts[{index}]"
        if not isinstance(script, dict): _source_error(where, "Script declaration object required")
        source = _canonical_path(script.get("source"), ".cs", "SCRIPT", where + ".source")
        _canonical_path(script.get("target"), ".cs", "SCRIPT", where + ".target")
        if not isinstance(script.get("targetAssembly"), str) or not script["targetAssembly"]:
            _source_error(where + ".targetAssembly", "Nonempty target assembly required")
        if not isinstance(script.get("sourceAssembly"), str) or not script["sourceAssembly"]:
            _source_error(where + ".sourceAssembly", "Nonempty source assembly required")
        _simple_name(script["sourceAssembly"], where + ".sourceAssembly", source=True)
        _simple_name(script["targetAssembly"], where + ".targetAssembly", source=True)
        if script.get("sourceType") != script.get("targetType"):
            _source_error(where, "Source and target script types must match")
        if not isinstance(script.get("guid"), str) or not _GUID.fullmatch(script["guid"]):
            _source_error(where + ".guid", "Lowercase Unity source GUID required")
        for field in ("sha256", "metaSha256"):
            if not isinstance(script.get(field), str) or not _SHA.fullmatch(script[field]):
                _source_error(where + "." + field, "Lowercase source SHA-256 required")
        source_raw = _read_candidate_file(incoming, files, source, script["sha256"], MAX_SOURCE_BYTES, where + ".source")
        source_meta = _read_candidate_file(incoming, files, source + ".meta", script["metaSha256"], 256 * 1024, where + ".meta")
        if _meta_guid(source_meta, where + ".meta", source=True) != script["guid"]:
            _source_error(where + ".meta", "Candidate source metadata GUID differs from the script pin")
        _parse_script(source_raw, script, where + ".source")
        target_assembly = script["targetAssembly"]
        if target_assembly == "Assembly-CSharp":
            _target_scope(script["target"], target_asmdefs, target_asmrefs, target_scope_dirs, where, default=True)
            continue
        _simple_name(target_assembly, where + ".targetAssembly", source=True)
        source_assembly = _simple_name(script["sourceAssembly"], where + ".sourceAssembly", source=True)
        if source_assembly != target_assembly:
            _retained_error("SOURCE_TARGET_NAME", where, "Named source/target assembly names must match exactly")
        row = row_names.get(target_assembly.casefold())
        if row is None or row["name"] != target_assembly:
            _retained_error("UNDECLARED", where, "Named target assembly requires an exact retainedAssemblies declaration")
        if row["name"] != source_assembly:
            _retained_error("SOURCE_TARGET_NAME", where, "Source asmdef name must match the retained target assembly")
        source_scope = _source_scope(source, candidate_asmdefs, candidate_asmrefs, where + ".source")
        source_name = candidate_name_by_path.get(source_scope)
        asmdef_meta_path = source_scope + ".meta"
        if asmdef_meta_path not in files:
            _retained_error("CANDIDATE_PIN", asmdef_meta_path, "Candidate asmdef metadata must be in the frozen manifest")
        asmdef_meta = _read_candidate_file(incoming, files, asmdef_meta_path, None, 256 * 1024, asmdef_meta_path)
        _meta_guid(asmdef_meta, asmdef_meta_path, source=True)
        if source_name != source_assembly or source_name != target_assembly:
            _retained_error("CANDIDATE_NAME", where, "Candidate asmdef JSON name must exactly match source and retained target assembly")
        if source_scope not in files:
            _retained_error("CANDIDATE_PIN", source_scope, "Candidate asmdef and metadata must be in the frozen manifest")
        selected = {item.get(key) for item in spec.get("additions", []) if isinstance(item, dict) for key in ("source", "target")}
        if source_scope in selected or source_scope + ".meta" in selected:
            _retained_error("CANDIDATE_SELECTED", source_scope, "Candidate asmdef must be omitted, never added or copied")
        candidate_script_sources.setdefault(source_scope, set()).add(source)
        target_scope = _target_scope(script["target"], target_asmdefs, target_asmrefs, target_scope_dirs, where, default=False)
        if target_scope != row["target"]:
            _retained_error("TARGET_SCOPE", where, "Nearest existing target asmdef must be the declared retained target")
        used_rows.add(row["target"])

    omitted = spec.get("omittedCompilerInputs", [])
    if not isinstance(omitted, list): _retained_error("OMISSION", "omittedCompilerInputs", "Omission list required")
    for path, source_set in candidate_script_sources.items():
        matching = [item for item in omitted if isinstance(item, dict) and item.get("path") == path
                    and item.get("coveredByExternalScript") in source_set]
        if not matching:
            _retained_error("CANDIDATE_OMISSION", path, "Candidate asmdef must be omitted and covered by a schema-only script in its scope")
    unused = [row["name"] for row in rows if row["target"] not in used_rows]
    if unused:
        _retained_error("UNUSED", "retainedAssemblies", "Every retained assembly declaration must be used by a named newScript")
    return rows
