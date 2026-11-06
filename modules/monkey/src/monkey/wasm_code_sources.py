"""Source-bound static extraction of exact IL2CPP/WASM method bodies.

This module reads bytes and metadata only. It never instantiates or executes a
WASM module, DLL, JavaScript, or recovered C#.
"""
from __future__ import annotations

import hashlib
import json
import re
import selectors
import struct
import subprocess
import time
from pathlib import Path
from typing import Any, Sequence

from .io import encoded, load, new_output, safe, write_json
from .sources.compiled import fail

MAX_WASM_SOURCE_BYTES = 64 * 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024 * 1024
MAX_MAP_BYTES = 32 * 1024 * 1024
MAX_SEGMENT_BYTES = 256 * 1024 * 1024
MAX_BODY_BYTES = 4 * 1024 * 1024
MAX_REPORT_BYTES = 32 * 1024 * 1024
MAX_SELECTED_METHODS = 20_000
MAX_BROTLI_SECONDS = 120
MAX_BROTLI_PROVIDER_BYTES = 1024 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_WASM_HEADER = b"\x00asm\x01\x00\x00\x00"
_V29_MAGIC = 0xFAB11BAF


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _input(path: str | Path, label: str, expected_sha256: str, limit: int) -> tuple[Path, dict[str, Any], bytes]:
    if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
        fail("WASM_CODE_EXPECTED_SHA", label, "An exact lowercase SHA-256 is required")
    resolved = safe(path)
    if resolved.is_symlink() or not resolved.is_file():
        fail("WASM_CODE_INPUT_TYPE", label, "Expected an existing regular non-symlink file")
    if resolved.stat().st_size > limit:
        fail("WASM_CODE_INPUT_BUDGET", label, "Input exceeds the byte budget")
    raw = resolved.read_bytes()
    actual = _sha(raw)
    if actual != expected_sha256:
        fail("WASM_CODE_INPUT_CHANGED", label, "Input bytes differ from the exact supplied SHA-256")
    return resolved, {"path": str(resolved), "sha256": actual, "bytes": len(raw)}, raw


def _u32(raw: bytes, offset: int, end: int) -> tuple[int, int]:
    value = 0
    shift = 0
    for _ in range(5):
        if offset >= end:
            raise ValueError("truncated unsigned LEB128")
        byte = raw[offset]
        offset += 1
        value |= (byte & 0x7f) << shift
        if byte < 0x80:
            if value > 0xffffffff:
                raise ValueError("unsigned LEB128 overflow")
            return value, offset
        shift += 7
    raise ValueError("unsigned LEB128 is longer than five bytes")


def _wasm_name(raw: bytes, offset: int, end: int) -> tuple[str, int]:
    length, offset = _u32(raw, offset, end)
    finish = offset + length
    if finish > end:
        raise ValueError("truncated name")
    return raw[offset:finish].decode("utf-8"), finish


def _limits(raw: bytes, offset: int, end: int) -> int:
    flags, offset = _u32(raw, offset, end)
    _, offset = _u32(raw, offset, end)
    if flags & 1:
        _, offset = _u32(raw, offset, end)
    return offset


def _imports(raw: bytes, offset: int, end: int) -> list[int]:
    count, offset = _u32(raw, offset, end)
    functions = []
    for _ in range(count):
        _, offset = _wasm_name(raw, offset, end)
        _, offset = _wasm_name(raw, offset, end)
        if offset >= end:
            raise ValueError("truncated import kind")
        kind = raw[offset]
        offset += 1
        if kind == 0:
            type_index, offset = _u32(raw, offset, end)
            functions.append(type_index)
        elif kind == 1:
            if offset >= end:
                raise ValueError("truncated table type")
            offset += 1
            offset = _limits(raw, offset, end)
        elif kind == 2:
            offset = _limits(raw, offset, end)
        elif kind == 3:
            if offset + 2 > end:
                raise ValueError("truncated global type")
            offset += 2
        elif kind == 4:
            if offset >= end:
                raise ValueError("truncated tag type")
            offset += 1
            _, offset = _u32(raw, offset, end)
        else:
            raise ValueError("unknown import kind")
    if offset != end:
        raise ValueError("trailing bytes in import section")
    return functions


def _scan_wasm(raw: bytes) -> tuple[list[dict[str, Any]], int, int]:
    if raw[:8] != _WASM_HEADER:
        fail("WASM_CODE_SEGMENT_HEADER", "$", "Decoded segment is not WebAssembly v1")
    cursor = 8
    seen: set[int] = set()
    imported_function_types: list[int] = []
    declared_function_types = None
    wasm_types: list[dict[str, Any]] = []
    body_rows = []
    code_sections = 0
    try:
        while cursor < len(raw):
            section_id = raw[cursor]
            cursor += 1
            payload_size, payload = _u32(raw, cursor, len(raw))
            finish = payload + payload_size
            if finish > len(raw):
                raise ValueError("section exceeds module bytes")
            if section_id != 0:
                if section_id in seen:
                    raise ValueError("duplicate non-custom section")
                seen.add(section_id)
            if section_id == 1:
                count, p = _u32(raw, payload, finish)
                for _ in range(count):
                    if p >= finish or raw[p] != 0x60:
                        raise ValueError("unsupported type form")
                    p += 1
                    param_count, p = _u32(raw, p, finish)
                    if p + param_count > finish:
                        raise ValueError("truncated function parameter types")
                    params = [raw[p + i] for i in range(param_count)]
                    p += param_count
                    result_count, p = _u32(raw, p, finish)
                    if p + result_count > finish:
                        raise ValueError("truncated function result types")
                    results = [raw[p + i] for i in range(result_count)]
                    p += result_count
                    wasm_types.append({"params": params, "results": results})
                if p != finish:
                    raise ValueError("trailing bytes in type section")
            elif section_id == 2:
                imported_function_types = _imports(raw, payload, finish)
            elif section_id == 3:
                declared_count, p = _u32(raw, payload, finish)
                declared_function_types = []
                for _ in range(declared_count):
                    type_index, p = _u32(raw, p, finish)
                    declared_function_types.append(type_index)
                if p != finish:
                    raise ValueError("trailing bytes in function section")
            elif section_id == 10:
                code_sections += 1
                count, p = _u32(raw, payload, finish)
                for index in range(count):
                    body_size, body_start = _u32(raw, p, finish)
                    body_end = body_start + body_size
                    if body_end > finish or body_size > MAX_BODY_BYTES:
                        raise ValueError("function body exceeds its boundary or budget")
                    body = raw[body_start:body_end]
                    function_index = len(imported_function_types) + index
                    if declared_function_types is None or index >= len(declared_function_types):
                        raise ValueError("code body has no function-section type index")
                    type_index = declared_function_types[index]
                    if type_index >= len(wasm_types):
                        raise ValueError("function type index is out of range")
                    body_rows.append({"functionIndex": function_index,
                                      "offset": body_start, "bytes": body_size, "sha256": _sha(body),
                                      "typeIndex": type_index, "typeSignature": wasm_types[type_index]})
                    p = body_end
                if p != finish:
                    raise ValueError("trailing bytes in code section")
            cursor = finish
    except (UnicodeDecodeError, ValueError, IndexError) as error:
        fail("WASM_CODE_SEGMENT_INVALID", "$", f"Malformed static WebAssembly structure ({type(error).__name__})")
    if cursor != len(raw) or code_sections != 1 or declared_function_types is None:
        fail("WASM_CODE_SEGMENT_INVALID", "$", "Expected one bounded function and code section")
    if declared_function_types is None or len(declared_function_types) != len(body_rows):
        fail("WASM_CODE_FUNCTION_COUNT", "$", "Function and code section counts differ")
    return body_rows, len(imported_function_types), len(body_rows)


def _metadata_v29(raw: bytes) -> dict[str, Any]:
    if len(raw) < 8 + 31 * 8:
        fail("WASM_CODE_METADATA_HEADER", "$", "Metadata is too short for the v29 header")
    magic, version = struct.unpack_from("<II", raw)
    if magic != _V29_MAGIC or version != 29:
        fail("WASM_CODE_METADATA_VERSION", "$", "Only exact IL2CPP global-metadata v29 input is supported")
    pairs = [struct.unpack_from("<II", raw, 8 + i * 8) for i in range(31)]
    for index, (offset, count) in enumerate(pairs):
        if offset > len(raw) or count > len(raw) - offset:
            fail("WASM_CODE_METADATA_BOUNDS", str(index), "Metadata table lies outside the exact metadata bytes")
    string_offset, string_bytes = pairs[2]

    def string_at(index: int) -> str:
        if index < 0 or index >= string_bytes:
            raise ValueError("string index out of bounds")
        start = string_offset + index
        stop = raw.find(b"\0", start, string_offset + string_bytes)
        if stop < 0:
            raise ValueError("unterminated metadata string")
        return raw[start:stop].decode("utf-8")

    field_offset, field_bytes = pairs[11]
    method_offset, method_bytes = pairs[5]
    type_offset, type_bytes = pairs[19]
    if field_bytes % 12 or method_bytes % 32 or type_bytes % 88:
        fail("WASM_CODE_METADATA_TABLE_SIZE", "$", "v29 type, method, or field table size is invalid")
    fields = []
    methods = []
    types = []
    try:
        for index in range(field_bytes // 12):
            name_index, type_index, token = struct.unpack_from("<IiI", raw, field_offset + index * 12)
            if token >> 24 != 4:
                raise ValueError("field token table mismatch")
            fields.append({"index": index, "name": string_at(name_index), "typeIndex": type_index,
                           "token": f"0x{token:08x}"})
        for index in range(method_bytes // 32):
            name_index, declaring, ret_index, param_start, generic, token, flags, iflags, slot, param_count = struct.unpack_from(
                "<IiiiiIHHHH", raw, method_offset + index * 32)
            if token >> 24 != 6 or declaring < 0 or declaring >= type_bytes // 88:
                raise ValueError("method token or declaring type is invalid")
            methods.append({"index": index, "name": string_at(name_index), "declaringType": declaring,
                            "returnTypeIndex": ret_index, "parameterStart": param_start,
                            "parameterCount": param_count, "token": f"0x{token:08x}"})
        type_count = type_bytes // 88
        for index in range(type_count):
            values = struct.unpack_from("<IIiiiiiIiiiiiiiiHHHHHHHHII", raw, type_offset + index * 88)
            name_index, namespace_index, byval, declaring, parent, element, generic, flags, *rest = values
            starts, counts = rest[:8], rest[8:16]
            bitfield, token = rest[16:]
            field_start, method_start = starts[:2]
            method_count, _, field_count = counts[:3]
            if token >> 24 != 2:
                raise ValueError("type token table mismatch")
            if field_count and (field_start < 0 or field_start + field_count > len(fields)):
                raise ValueError("type field range out of bounds")
            if method_count and (method_start < 0 or method_start + method_count > len(methods)):
                raise ValueError("type method range out of bounds")
            types.append({"index": index, "name": string_at(name_index), "namespace": string_at(namespace_index),
                          "parentTypeIndex": parent, "byvalTypeIndex": byval,
                          "methodStart": method_start, "methodCount": method_count,
                          "fieldStart": field_start, "fieldCount": field_count,
                          "token": f"0x{token:08x}"})
        for type_row in types:
            for method in methods[type_row["methodStart"]:type_row["methodStart"] + type_row["methodCount"]]:
                if method["declaringType"] != type_row["index"]:
                    raise ValueError("method declaring type does not match its TypeDef range")
    except (UnicodeDecodeError, ValueError, struct.error) as error:
        fail("WASM_CODE_METADATA_INVALID", "$", f"Malformed IL2CPP v29 metadata table ({type(error).__name__})")
    return {"version": version, "typeCount": len(types), "methodCount": len(methods),
            "fieldCount": len(fields), "types": types, "methods": methods, "fields": fields}


def _read_json(raw: bytes, label: str, limit_nodes: int = 3_000_000) -> Any:
    try:
        return load(raw, max_nodes=limit_nodes, max_depth=96)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        fail("WASM_CODE_JSON_INVALID", label, f"Input is not bounded JSON ({type(error).__name__})")


def _method_id(source_sha: str, segment: int, function_index: int, type_index: int, method_index: int) -> str:
    return f"{source_sha[:16]}:seg{segment}:fn{function_index}:t{type_index}:m{method_index}"


def _brotli_provider(path: str | Path) -> tuple[Path, dict[str, Any]]:
    try:
        provider = Path(path).resolve(strict=True)
    except (OSError, RuntimeError):
        fail("WASM_CODE_BROTLI_PROVIDER", Path(path).name, "Explicit provider path cannot be resolved")
    if not provider.is_file() or not provider.stat().st_mode & 0o111:
        fail("WASM_CODE_BROTLI_PROVIDER", provider.name, "Expected an executable regular Brotli CLI file")
    if provider.stat().st_size > MAX_BROTLI_PROVIDER_BYTES:
        fail("WASM_CODE_BROTLI_PROVIDER", provider.name, "Provider file exceeds its byte budget")
    raw = provider.read_bytes()
    return provider, {"path": str(provider), "sha256": _sha(raw), "bytes": len(raw)}


def _decode_brotli(provider: Path, source: Path, expected: bytes) -> dict[str, Any]:
    """Decode one source with a fixed CLI contract and bounded output/deadline."""
    try:
        process = subprocess.Popen([str(provider), "-d", "-c", str(source)],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, close_fds=True)
    except OSError as error:
        fail("WASM_CODE_BROTLI_START", provider.name, f"Could not start explicit Brotli provider ({type(error).__name__})")
    output = bytearray()
    deadline = time.monotonic() + MAX_BROTLI_SECONDS
    selector = selectors.DefaultSelector()
    assert process.stdout is not None
    selector.register(process.stdout, selectors.EVENT_READ)
    eof = False
    try:
        while not eof:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                fail("WASM_CODE_BROTLI_TIMEOUT", provider.name, "Brotli decode exceeded 120 seconds")
            events = selector.select(min(remaining, 0.5))
            if not events:
                if process.poll() is not None:
                    # Drain any bytes still buffered after process exit.
                    chunk = process.stdout.read(65536)
                    if not chunk:
                        eof = True
                    else:
                        output.extend(chunk)
                continue
            chunk = process.stdout.read1(65536)
            if not chunk:
                eof = True
                selector.unregister(process.stdout)
                continue
            output.extend(chunk)
            if len(output) > len(expected):
                fail("WASM_CODE_BROTLI_OUTPUT_BUDGET", provider.name,
                     "Decoded output exceeded the exact expected segment byte length")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            fail("WASM_CODE_BROTLI_TIMEOUT", provider.name, "Brotli provider did not exit within 120 seconds")
        try:
            return_code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            fail("WASM_CODE_BROTLI_TIMEOUT", provider.name, "Brotli provider did not exit within 120 seconds")
        if return_code != 0:
            fail("WASM_CODE_BROTLI_FAILED", provider.name, "Brotli provider returned a nonzero exit status")
        decoded = bytes(output)
        if len(decoded) != len(expected) or decoded != expected or _sha(decoded) != _sha(expected):
            fail("WASM_CODE_BROTLI_MISMATCH", provider.name,
                 "Decoded bytes do not exactly match the expected segment bytes and SHA-256")
        return {"status": "verified_brotli_bytes", "bytes": len(decoded), "sha256": _sha(decoded),
                "deadlineSeconds": MAX_BROTLI_SECONDS, "outputLimitBytes": len(expected)}
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()


def inspect_wasm(source: str | Path, output: str | Path, *, expected_source_sha256: str,
                 metadata: str | Path, expected_metadata_sha256: str,
                 method_map: str | Path, expected_method_map_sha256: str,
                 decoded_segments: Sequence[dict[str, Any]], method_ids: Sequence[str] | None = None,
                 brotli_provider: str | Path | None = None) -> dict[str, Any]:
    """Verify one compressed WASM source and the explicitly linked decoded segments.

    `decoded_segments` rows contain `segment`, `path`, `expected_sha256`,
    `index_path`, `expected_index_sha256`, `source_sha256`, and optionally
    `source_path`. The caller-provided decode manifest is recorded as evidence;
    this function verifies both actual byte sets and all function-body boundaries
    but does not claim to have independently decompressed Brotli input unless
    an explicit `brotli_provider` path is supplied.
    """
    if not isinstance(decoded_segments, Sequence) or isinstance(decoded_segments, (str, bytes)) or not decoded_segments:
        fail("WASM_CODE_SEGMENTS_REQUIRED", "$", "At least one exact decoded segment mapping is required")
    if method_ids is not None and (not isinstance(method_ids, Sequence) or isinstance(method_ids, (str, bytes))
                                   or any(not isinstance(item, str) for item in method_ids)):
        fail("WASM_CODE_METHOD_SELECTION", "$", "method_ids must be a sequence of exact method IDs")
    source_path, source_row, source_raw = _input(source, "source", expected_source_sha256, MAX_WASM_SOURCE_BYTES)
    metadata_path, metadata_row, metadata_raw = _input(metadata, "metadata", expected_metadata_sha256, MAX_METADATA_BYTES)
    map_path, map_row, map_raw = _input(method_map, "method_map", expected_method_map_sha256, MAX_MAP_BYTES)
    metadata_doc = _metadata_v29(metadata_raw)
    map_doc = _read_json(map_raw, map_path.name)
    if not isinstance(map_doc, dict) or map_doc.get("schemaVersion") != 1 or map_doc.get("sourceCodeExecuted") is not False:
        fail("WASM_CODE_MAP_SCHEMA", map_path.name, "Expected schema v1 static method map with sourceCodeExecuted=false")
    map_methods = map_doc.get("methods")
    if not isinstance(map_methods, list) or len(map_methods) > MAX_SELECTED_METHODS:
        fail("WASM_CODE_MAP_METHODS", map_path.name, "Method map inventory is absent or exceeds the selected-method budget")

    segment_rows: dict[int, dict[str, Any]] = {}
    for row_index, mapping in enumerate(decoded_segments):
        if not isinstance(mapping, dict) or type(mapping.get("segment")) is not int or mapping["segment"] < 0:
            fail("WASM_CODE_SEGMENT_MAPPING", str(row_index), "Segment mapping requires a nonnegative segment index")
        segment_no = mapping["segment"]
        if segment_no in segment_rows:
            fail("WASM_CODE_SEGMENT_DUPLICATE", str(segment_no), "A segment index was supplied more than once")
        linked_source_sha = mapping.get("source_sha256")
        if linked_source_sha != source_row["sha256"]:
            fail("WASM_CODE_SOURCE_SEGMENT_LINK", str(segment_no), "Decoded segment mapping does not name this exact compressed source hash")
        if mapping.get("source_path") is not None and safe(mapping["source_path"]) != source_path:
            fail("WASM_CODE_SOURCE_SEGMENT_LINK", str(segment_no), "Decoded segment mapping names a different compressed source path")
        seg_path, seg_identity, seg_raw = _input(mapping.get("path"), f"segment-{segment_no}",
                                                 mapping.get("expected_sha256"), MAX_SEGMENT_BYTES)
        index_path, index_identity, index_raw = _input(mapping.get("index_path"), f"segment-{segment_no}-index",
                                                       mapping.get("expected_index_sha256"), MAX_MAP_BYTES)
        index_doc = _read_json(index_raw, index_path.name)
        if (not isinstance(index_doc, dict) or index_doc.get("schemaVersion") != 1 or
                index_doc.get("codeExecuted") is not False or index_doc.get("source") != seg_path.name or
                index_doc.get("sha256") != seg_identity["sha256"]):
            fail("WASM_CODE_SEGMENT_INDEX", str(segment_no), "Segment index is not bound to the decoded segment bytes")
        actual_bodies, imported_count, function_count = _scan_wasm(seg_raw)
        indexed_bodies = index_doc.get("bodies")
        if (not isinstance(indexed_bodies, list) or len(indexed_bodies) != len(actual_bodies) or
                any(any(indexed.get(key) != actual.get(key) for key in ("functionIndex", "offset", "bytes", "sha256"))
                    for indexed, actual in zip(indexed_bodies, actual_bodies))):
            fail("WASM_CODE_SEGMENT_BODY_INDEX", str(segment_no), "Existing body index differs from an independent code-section boundary scan")
        if index_doc.get("importedFunctions") != imported_count:
            fail("WASM_CODE_SEGMENT_IMPORT_INDEX", str(segment_no), "Imported function count differs from the raw module")
        segment_rows[segment_no] = {"segment": segment_no, "source": mapping.get("source_path", str(source_path)),
                                    "sourceSha256": linked_source_sha, "decoded": seg_identity,
                                    "index": index_identity, "bodies": {item["functionIndex"]: item for item in actual_bodies},
                                    "imports": imported_count, "functions": function_count,
                                    "raw": seg_raw, "path": seg_path}

    decode_evidence: dict[str, Any] | None = None
    provider_evidence: dict[str, Any] | None = None
    if brotli_provider is not None:
        if len(segment_rows) != 1:
            fail("WASM_CODE_BROTLI_SEGMENT_COUNT", "$",
                 "Explicit Brotli verification requires exactly one decoded segment for this compressed source")
        provider_path, provider_evidence = _brotli_provider(brotli_provider)
        decoded_row = next(iter(segment_rows.values()))
        # The target segment file is the exact expected byte sequence; the CLI
        # output is capped at its length before the full bytes/hash comparison.
        decode_evidence = _decode_brotli(provider_path, source_path, decoded_row["raw"])
        try:
            source_now = source_path.read_bytes()
        except OSError:
            fail("WASM_CODE_BROTLI_SOURCE_CHANGED", source_path.name, "Compressed source became unreadable after decode")
        if _sha(source_now) != source_row["sha256"]:
            fail("WASM_CODE_BROTLI_SOURCE_CHANGED", source_path.name, "Compressed source changed during decode")

    output_path = new_output(output, [source_path, metadata_path, map_path,
                                     *[row["path"] for row in segment_rows.values()]])
    (output_path / "body-slices").mkdir()
    types = {row["index"]: row for row in metadata_doc["types"]}
    methods = {row["index"]: row for row in metadata_doc["methods"]}
    selected_set = set(method_ids) if method_ids is not None else None
    records = []
    slice_files = []
    total_body_bytes = 0
    for map_index, row in enumerate(map_methods):
        if not isinstance(row, dict):
            fail("WASM_CODE_MAP_ROW", str(map_index), "Map method row is not an object")
        binding = row.get("binding")
        if not isinstance(binding, dict) or type(binding.get("segment")) is not int:
            continue
        seg_no = binding["segment"]
        if seg_no not in segment_rows:
            continue
        body_info = binding.get("body")
        if not isinstance(body_info, dict):
            continue
        function_index = binding.get("functionIndex")
        type_index = row.get("typeIndex")
        method_index = row.get("metadataMethodIndex")
        if type(function_index) is not int or type(type_index) is not int or type(method_index) is not int:
            fail("WASM_CODE_MAP_IDENTITY", str(map_index), "Map row lacks exact integer function/type/method indices")
        method_id = _method_id(source_row["sha256"], seg_no, function_index, type_index, method_index)
        if selected_set is not None and method_id not in selected_set:
            continue
        type_row = types.get(type_index)
        method_row = methods.get(method_index)
        if (type_row is None or method_row is None or method_row["declaringType"] != type_index or
                not type_row["methodStart"] <= method_index < type_row["methodStart"] + type_row["methodCount"]):
            fail("WASM_CODE_METADATA_MAP_JOIN", method_id, "Map type/method indices do not join within the exact v29 metadata bytes")
        expected_type_name = (type_row["namespace"] + "." if type_row["namespace"] else "") + type_row["name"]
        if row.get("type") != expected_type_name or row.get("method") != method_row["name"] or row.get("token") != method_row["token"]:
            fail("WASM_CODE_METADATA_MAP_JOIN", method_id, "Map type/name/token differs from the exact metadata TypeDef/MethodDef")
        type_fields = metadata_doc["fields"][type_row["fieldStart"]:type_row["fieldStart"] + type_row["fieldCount"]]
        indexed_body = segment_rows[seg_no]["bodies"].get(function_index)
        if indexed_body is None:
            fail("WASM_CODE_FUNCTION_MISSING", method_id, "Mapped function index is absent from the decoded code section")
        if any(body_info.get(key) != indexed_body.get(key) for key in ("functionIndex", "offset", "bytes", "sha256")):
            fail("WASM_CODE_BODY_BOUNDARY", method_id, "Method-map body offset/size/hash differs from the decoded function body index")
        body_start, body_size = indexed_body["offset"], indexed_body["bytes"]
        body_bytes = segment_rows[seg_no]["raw"][body_start:body_start + body_size]
        if len(body_bytes) != body_size or _sha(body_bytes) != indexed_body["sha256"]:
            fail("WASM_CODE_BODY_HASH", method_id, "Exact body slice differs from its mapped SHA-256")
        body_path = row.get("bodyPath")
        if isinstance(body_path, str):
            # Existing method maps use project-root-relative body paths.
            project_root = segment_rows[seg_no]["path"].parent.parent.parent
            existing_path = safe(project_root / body_path)
            if existing_path.is_file() and not existing_path.is_symlink():
                existing = existing_path.read_bytes()
                if existing != body_bytes:
                    fail("WASM_CODE_BODY_SNAPSHOT", method_id, "Existing selected body file differs from the segment's exact byte slice")
        total_body_bytes += len(body_bytes)
        if total_body_bytes > MAX_MAP_BYTES:
            fail("WASM_CODE_BODY_BUDGET", "$", "Selected method body snapshots exceed the output byte budget")
        filename = hashlib.sha256(method_id.encode("utf-8")).hexdigest()[:24] + ".bin"
        relative_slice = "body-slices/" + filename
        (output_path / relative_slice).write_bytes(body_bytes)
        slice_files.append({"path": relative_slice, "sha256": _sha(body_bytes), "bytes": len(body_bytes)})
        records.append({"methodId": method_id, "declaringType": expected_type_name, "method": method_row["name"],
                        "token": method_row["token"], "typeIndex": type_index, "metadataMethodIndex": method_index,
                        "metadataMethodToFunctionAssociation": "caller-map; codeRegistration not parsed",
                        "typeFields": [{"name": field["name"], "typeIndex": field["typeIndex"]} for field in type_fields],
                        "signatureFromMap": row.get("signature"), "signatureAuthority": "map-text; identity fields cross-checked against raw metadata",
                        "segment": seg_no, "functionIndex": function_index,
                        "wasmTypeIndex": indexed_body["typeIndex"], "wasmTypeSignature": indexed_body["typeSignature"],
                        "sourceEvidence": {"compressedSourceSha256": source_row["sha256"],
                                           "decodedSegmentSha256": segment_rows[seg_no]["decoded"]["sha256"],
                                           "decodeLink": ("verified_brotli_bytes" if decode_evidence else
                                                          "caller-supplied-manifest-only; monkey did not decompress")},
                        "metadataEvidence": {"sha256": metadata_row["sha256"], "version": 29,
                                             "relationshipToWasm": "same-evidence-group; no independent build-id claim"},
                        "bodyEvidence": {"kind": "exact-wasm-function-body-slice", "offset": body_start,
                                         "bytes": body_size, "sha256": _sha(body_bytes),
                                         "snapshot": relative_slice, "verifiedAgainstSegment": True},
                        "status": "body_bytes_verified"})
    if selected_set is not None:
        found = {row["methodId"] for row in records}
        missing = selected_set - found
        if missing:
            fail("WASM_CODE_METHOD_SELECTION_MISSING", "$", "One or more selected method IDs are absent from the supplied map/segment set")
    report = {"schemaVersion": 1, "status": "body_bytes_verified" if records else "metadata_only",
              "sourceFamily": "il2cpp-wasm", "source": source_row, "sourceExecuted": False,
              "wasmInstantiated": False, "metadata": dict(metadata_row, version=29,
                  typeCount=metadata_doc["typeCount"], methodCount=metadata_doc["methodCount"],
                  methodIdentityJoin="raw v29 type/method index+token verified; same-build claim withheld"),
              "methodMap": dict(map_row, schemaVersion=map_doc["schemaVersion"], methodRows=len(map_methods),
                                sourceCodeExecuted=False),
              "decodedSegments": [{k: v for k, v in row.items() if k not in ("raw", "bodies", "path")} for row in segment_rows.values()],
              "brotliDecode": ({"provider": provider_evidence, **decode_evidence} if decode_evidence else None),
              "methodMapAssociation": {"metadataMethodIndexToFunctionIndex": "caller-map; not independently verified",
                                       "codeRegistrationParsed": False},
              "methods": records, "outputs": slice_files,
              "diagnostics": [{"code": "METADATA_WASM_BUILD_RELATION_UNPROVEN",
                               "message": "The supplied map associates metadata method identities with WASM function indices; codeRegistration was not parsed, and no common build identifier is independently available."}],
              "summary": {"methods": len(records), "exactBodySlices": len(records),
                          "sourceToDecoded": ("verified_brotli_bytes" if decode_evidence else "caller-supplied-manifest-only"),
                          "methodAssociation": "caller-map-unverified", "implementedMethods": 0}}
    if len(encoded(report)) > MAX_REPORT_BYTES:
        fail("WASM_CODE_REPORT_BUDGET", str(output_path.name), "WASM source report exceeds its byte budget")
    write_json(output_path / "wasm-code-source.json", report)
    return {"status": report["status"], "report": str(output_path / "wasm-code-source.json"),
            "summary": report["summary"], "sourceExecuted": False, "wasmInstantiated": False}
