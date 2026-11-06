"""Read-only batching plan for a full-source C# draft candidate.

The planner indexes manifest-owned files and compact per-source reports. It
does not read detailed diagnostic shards or modify the candidate.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

from .io import load, read, safe, sha
from .sources.compiled import fail

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MAX_MANIFEST_BYTES = 128 * 1024 * 1024
_MAX_REPORT_BYTES = 128 * 1024 * 1024
_MAX_SOURCE_FILE_BYTES = 512 * 1024 * 1024
_MAX_INVENTORY_FILES = 500_000
_SOURCE_MODULE_HEADER = re.compile(rb"(?m)^// Source module SHA256: ([0-9a-f]{64})\s*$")


def _relative_path(value, location):
    if (not isinstance(value, str) or not value or "\\" in value or "\x00" in value
            or unicodedata.normalize("NFC", value) != value):
        fail("CODE_POSTPROCESS_PATH", location, "Expected canonical NFC project-relative POSIX path")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or parsed.as_posix() != value or any(p in ("", ".", "..") for p in value.split("/")):
        fail("CODE_POSTPROCESS_PATH", location, "Absolute, noncanonical, and traversal paths are forbidden")
    return value


def _sha(value, location):
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        fail("CODE_POSTPROCESS_SHA", location, "Expected lowercase SHA-256 hex")
    return value


def _inventory(manifest, location):
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) > _MAX_INVENTORY_FILES:
        fail("CODE_POSTPROCESS_INVENTORY", location, "Manifest file inventory is absent or exceeds 500,000 entries")
    by_path, folded = {}, {}
    for index, row in enumerate(files):
        at = f"{location}[{index}]"
        if not isinstance(row, dict):
            fail("CODE_POSTPROCESS_INVENTORY", at, "Expected file inventory object")
        path = _relative_path(row.get("path"), at + ".path")
        if path in by_path:
            fail("CODE_POSTPROCESS_DUPLICATE_PATH", path, "Manifest contains a repeated path")
        key = path.casefold()
        if key in folded and folded[key] != path:
            fail("CODE_POSTPROCESS_CASE_COLLISION", path, "Manifest contains a case-fold path collision")
        folded[key] = path
        size = row.get("bytes")
        if type(size) is not int or not 0 <= size <= _MAX_SOURCE_FILE_BYTES:
            fail("CODE_POSTPROCESS_FILE_SIZE", path, "Invalid or oversized manifest file size")
        _sha(row.get("sha256"), at + ".sha256")
        by_path[path] = row
    return by_path


def _verify_file(root, path, inventory, *, load_json=False, nodes=8_000_000):
    path = _relative_path(path, "file.path")
    entry = inventory.get(path)
    if not isinstance(entry, dict):
        fail("CODE_POSTPROCESS_UNOWNED_FILE", path, "Referenced file is missing from the owning manifest")
    absolute = root / path
    try:
        absolute = safe(absolute)
        if not absolute.is_relative_to(root) or not absolute.is_file():
            fail("CODE_POSTPROCESS_UNSAFE_FILE", path, "Referenced file is not a regular file inside the candidate")
        size = absolute.stat().st_size
        if size != entry["bytes"]:
            fail("CODE_POSTPROCESS_FILE_CHANGED", path, "File size differs from the owning manifest")
        digest = hashlib.sha256()
        with absolute.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        if digest.hexdigest() != entry["sha256"]:
            fail("CODE_POSTPROCESS_FILE_CHANGED", path, "File hash differs from the owning manifest")
        if not load_json:
            return entry, None
        if size > _MAX_REPORT_BYTES:
            fail("CODE_POSTPROCESS_REPORT_BUDGET", path, "Compact report exceeds the 128 MiB read budget")
        raw = read(absolute, max_bytes=_MAX_REPORT_BYTES)
        value = load(raw, max_nodes=nodes, max_depth=96)
        if not isinstance(value, dict):
            fail("CODE_POSTPROCESS_REPORT_SHAPE", path, "Expected a JSON object report")
        return entry, value
    except OSError as exc:
        fail("CODE_POSTPROCESS_READ", path, "Unable to read manifest-owned file: " + type(exc).__name__)


def _span(mapping, source_bytes, location):
    span = mapping.get("sourceBytes")
    if (not isinstance(span, dict) or type(span.get("start")) is not int or type(span.get("end")) is not int
            or span["start"] < 0 or span["end"] < span["start"] or span["end"] > source_bytes):
        fail("CODE_POSTPROCESS_SOURCE_SPAN", location, "Missing or invalid UTF-8 byte span")
    return {"start": span["start"], "end": span["end"]}


def _detail_reference(mapping, detail_paths, location):
    path, index = mapping.get("detailsPath"), mapping.get("detailsIndex")
    if path not in detail_paths or type(index) is not int or not 0 <= index < detail_paths[path]:
        fail("CODE_POSTPROCESS_DETAIL_REFERENCE", location, "Invalid compact-report detail shard reference")
    return {"path": path, "index": index}


def _batch_id(index, digest, group, part):
    safe_group = re.sub(r"[^A-Za-z0-9_-]+", "_", str(group))[:32] or "Group"
    source_tag = digest[:8] if isinstance(digest, str) else "extraCode"
    return f"batch-{index:04d}-{source_tag}-{safe_group}-{part:04d}"


def prepare_plan(candidate, expected_manifest_sha256, max_files=128, max_code_bytes=512 * 1024):
    """Build a deterministic, read-only batch plan from one exact candidate.

    `candidate` is the directory containing `manifest.json`; the expected
    argument pins the exact manifest bytes. All discovered C# files, reports,
    and source inputs are rechecked against that owning manifest.
    """
    if not isinstance(expected_manifest_sha256, str) or not _HEX.fullmatch(expected_manifest_sha256):
        fail("CODE_POSTPROCESS_MANIFEST_PIN", "$", "Expected exact lowercase manifest SHA-256")
    if type(max_files) is not int or not 1 <= max_files <= 4096:
        fail("CODE_POSTPROCESS_BATCH_LIMIT", "max_files", "Expected a batch file limit from 1 to 4096")
    if type(max_code_bytes) is not int or not 1 <= max_code_bytes <= 1024 * 1024:
        fail("CODE_POSTPROCESS_BATCH_LIMIT", "max_code_bytes", "Expected a batch byte limit from 1 byte to 1 MiB")
    root = safe(candidate)
    if not root.is_dir():
        fail("CODE_POSTPROCESS_CANDIDATE", str(candidate), "Candidate must be an existing directory")
    manifest_path = root / "manifest.json"
    manifest_raw = read(manifest_path, max_bytes=_MAX_MANIFEST_BYTES)
    manifest_sha = sha(manifest_raw)
    if manifest_sha != expected_manifest_sha256:
        fail("CODE_POSTPROCESS_MANIFEST_PIN", str(manifest_path), "Manifest does not match expected SHA-256")
    manifest = load(manifest_raw, max_nodes=8_000_000, max_depth=96)
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1:
        fail("CODE_POSTPROCESS_MANIFEST_SCHEMA", str(manifest_path), "Expected schemaVersion 1 manifest")
    inventory = _inventory(manifest, "$.files")

    package_meta = manifest.get("codeDrafts")
    if (not isinstance(package_meta, dict) or package_meta.get("kind") != "full-csharp-drafts-v1"
            or type(package_meta.get("sourceFiles")) is not int or package_meta["sourceFiles"] < 1):
        fail("CODE_POSTPROCESS_PACKAGE", "$.codeDrafts", "Manifest does not own a full-source C# draft package")
    package_path = _relative_path(package_meta.get("report"), "$.codeDrafts.report")
    _, package_report = _verify_file(root, package_path, inventory, load_json=True)
    sources = package_report.get("sources")
    if not isinstance(sources, list) or len(sources) != package_meta["sourceFiles"]:
        fail("CODE_POSTPROCESS_PACKAGE", package_path, "Package report source list differs from manifest")

    csharp_entries = [entry for path, entry in inventory.items()
                      if PurePosixPath(path).suffix.lower() == ".cs"]
    csharp_paths = {entry["path"] for entry in csharp_entries}
    if len(csharp_paths) != len(csharp_entries):
        fail("CODE_POSTPROCESS_DUPLICATE_PATH", "$.files", "Repeated C# target path")
    generated_csharp_entries, blocked_csharp_entries = [], []
    for entry in csharp_entries:
        owner = entry.get("owner")
        if not isinstance(owner, str) or not owner:
            fail("CODE_POSTPROCESS_FILE_OWNER", entry["path"], "C# inventory row needs an explicit owner")
        if owner == "generated":
            generated_csharp_entries.append(entry)
        else:
            blocked_csharp_entries.append(entry)
        _verify_file(root, entry["path"], inventory)
    generated_csharp_paths = {entry["path"] for entry in generated_csharp_entries}
    js_ts_by_sha = defaultdict(list)
    for path, entry in inventory.items():
        if PurePosixPath(path).suffix.lower() in (".js", ".ts"):
            js_ts_by_sha[entry["sha256"]].append(path)
    for paths in js_ts_by_sha.values():
        paths.sort()

    source_infos = []
    extra_source_infos = []
    source_path_to_digest = {}
    report_paths = set()
    function_mapping_count = indexed_count = auxiliary_count = field_mapping_count = 0
    function_ids, field_ids = set(), set()
    planned_files = {}
    class_rows_by_path = {}
    module_path_by_id = {}
    file_dependencies = defaultdict(set)
    all_detail_paths = set()
    diagnostic_total = 0
    for source_index, source_row in enumerate(sources):
        at = f"{package_path}.sources[{source_index}]"
        if not isinstance(source_row, dict):
            fail("CODE_POSTPROCESS_PACKAGE", at, "Expected source report descriptor")
        report_path = _relative_path(source_row.get("reportPath"), at + ".reportPath")
        if report_path in report_paths:
            fail("CODE_POSTPROCESS_DUPLICATE_REPORT", report_path, "Package lists a source report twice")
        report_paths.add(report_path)
        report_entry, report = _verify_file(root, report_path, inventory, load_json=True, nodes=8_000_000)
        if report.get("status") != "full_source_csharp_drafts; compile_excluded":
            fail("CODE_POSTPROCESS_SOURCE_REPORT", report_path, "Source report is not a full-source C# draft report")
        source = report.get("source")
        if not isinstance(source, dict):
            fail("CODE_POSTPROCESS_SOURCE_REPORT", report_path, "Source identity is absent")
        source_sha = _sha(source.get("sha256"), report_path + ".source.sha256")
        source_size = source.get("bytes")
        if type(source_size) is not int or source_size < 0:
            fail("CODE_POSTPROCESS_SOURCE_REPORT", report_path, "Invalid source byte count")
        source_path = _relative_path(report.get("sourcePath"), report_path + ".sourcePath")
        source_entry, _ = _verify_file(root, source_path, inventory)
        if source_entry["sha256"] != source_sha or source_entry["bytes"] != source_size:
            fail("CODE_POSTPROCESS_SOURCE_PIN", source_path, "Source file identity differs from its compact report")
        digest = source_sha[:12]
        if digest in source_path_to_digest.values():
            fail("CODE_POSTPROCESS_DUPLICATE_SOURCE", source_path, "Source digest partition is repeated")
        source_path_to_digest[source_path] = digest
        source_members = PurePosixPath(source_path).parts
        if (len(source_members) < 5 or source_members[:3] != ("SourceRecovery", "Code", "Source")
                or source_members[3] != digest):
            fail("CODE_POSTPROCESS_SOURCE_PATH", source_path, "Source path does not match its SHA partition")
        detail_rows = report.get("details")
        if not isinstance(detail_rows, list):
            fail("CODE_POSTPROCESS_SOURCE_REPORT", report_path, "Detail shard index is absent")
        detail_paths = {}
        for detail in detail_rows:
            if not isinstance(detail, dict):
                fail("CODE_POSTPROCESS_SOURCE_REPORT", report_path, "Invalid detail shard index row")
            detail_path = _relative_path(detail.get("path"), report_path + ".details.path")
            count = detail.get("records")
            if type(count) is not int or count < 0 or detail_path in detail_paths:
                fail("CODE_POSTPROCESS_SOURCE_REPORT", detail_path, "Invalid or duplicate detail shard record count")
            if detail_path not in inventory:
                fail("CODE_POSTPROCESS_UNOWNED_FILE", detail_path, "Detail shard is absent from owning manifest")
            detail_paths[detail_path] = count
            all_detail_paths.add(detail_path)
        diagnostics = report.get("diagnostics", {})
        if not isinstance(diagnostics, dict):
            fail("CODE_POSTPROCESS_SOURCE_REPORT", report_path, "Diagnostic summary is invalid")
        diag_count = diagnostics.get("count", 0)
        by_code = diagnostics.get("countsByCode", {})
        if type(diag_count) is not int or diag_count < 0 or not isinstance(by_code, dict):
            fail("CODE_POSTPROCESS_SOURCE_REPORT", report_path, "Diagnostic counts are invalid")
        if any(not isinstance(k, str) or type(v) is not int or v < 0 for k, v in by_code.items()):
            fail("CODE_POSTPROCESS_SOURCE_REPORT", report_path, "Diagnostic count-by-code entries are invalid")
        diagnostic_total += diag_count
        source_infos.append({"sourceOrder": source_index, "sourceId": source_sha,
            "sha256": source_sha, "sourcePath": source_path,
            "bytes": source_size,
            "reportPath": report_path, "diagnosticSummary": {"count": diag_count,
                "countsByCode": dict(sorted(by_code.items()))},
            "indexedMethods": report.get("coverage", {}).get("indexedMethodsInSource", 0),
            "functions": report.get("coverage", {}).get("functionsEmitted", 0),
            "fields": report.get("coverage", {}).get("fieldRecords", 0)})

        classes_by_path = {}
        for cls in report.get("classes", []):
            target = cls.get("targetPath") if isinstance(cls, dict) else None
            if target not in generated_csharp_paths or target in classes_by_path or target in class_rows_by_path:
                fail("CODE_POSTPROCESS_CLASS_MAPPING", str(target), "Class report target is missing or repeated")
            classes_by_path[target] = cls
            class_rows_by_path[target] = cls
        modules_by_path = defaultdict(list)
        for module in report.get("modules", []):
            if not isinstance(module, dict) or not isinstance(module.get("id"), str):
                fail("CODE_POSTPROCESS_MODULE_MAPPING", report_path, "Invalid source module record")
            module_id = module["id"]
            target_paths = module.get("targetPaths")
            dependencies = module.get("dependencies", [])
            if (not isinstance(target_paths, list) or not target_paths
                    or not isinstance(dependencies, list) or not all(isinstance(d, str) for d in dependencies)):
                fail("CODE_POSTPROCESS_MODULE_MAPPING", module_id, "Invalid module targets or dependencies")
            if module_id in module_path_by_id:
                fail("CODE_POSTPROCESS_MODULE_MAPPING", module_id, "Module ID appears in more than one report")
            module_path_by_id[module_id] = list(target_paths)
            for target in target_paths:
                if target not in generated_csharp_paths:
                    fail("CODE_POSTPROCESS_MODULE_MAPPING", str(target), "Module target is not a manifest-owned C# file")
                modules_by_path[target].append(module_id)
                file_dependencies[target].update(dependencies)

        function_rows = report.get("functions")
        field_rows = report.get("fields")
        if not isinstance(function_rows, list) or not isinstance(field_rows, list):
            fail("CODE_POSTPROCESS_SOURCE_REPORT", report_path, "Compact function or field index is absent")
        function_count_local = indexed_local = auxiliary_local = 0
        for row_index, row in enumerate(function_rows):
            loc = f"{report_path}.functions[{row_index}]"
            if not isinstance(row, dict):
                fail("CODE_POSTPROCESS_FUNCTION_MAPPING", loc, "Expected compact function mapping")
            method_id = row.get("methodId")
            target_path = row.get("targetPath")
            if not isinstance(method_id, str) or target_path not in generated_csharp_paths:
                fail("CODE_POSTPROCESS_FUNCTION_MAPPING", loc, "Function mapping has no valid source id or target C# file")
            identity = (source_sha, method_id)
            if identity in function_ids:
                fail("CODE_POSTPROCESS_FUNCTION_MAPPING", method_id, "Function source mapping is repeated")
            function_ids.add(identity)
            span = _span(row, source_size, loc)
            source_hash = _sha(row.get("sourceSha256"), loc + ".sourceSha256")
            detail_ref = _detail_reference(row, detail_paths, loc)
            mapping = {"kind": row.get("kind"), "methodId": method_id,
                "sourceName": row.get("sourceName"), "sourceSha256": source_hash,
                "sourceBytes": span, "functionBytes": row.get("functionBytes"),
                "targetPath": target_path, "targetClass": row.get("targetClass"),
                "targetMethod": row.get("targetMethod"), "targetLocationMarker": row.get("targetLocationMarker"),
                "status": row.get("status"), "detailsRef": detail_ref}
            if row.get("status") == "embedded_in_owner" and not mapping["targetLocationMarker"]:
                fail("CODE_POSTPROCESS_EMBEDDED_MAPPING", method_id, "Embedded function mapping lacks an exact owner marker")
            target = planned_files.setdefault(target_path, {"path": target_path,
                "sha256": inventory[target_path]["sha256"], "bytes": inventory[target_path]["bytes"],
                "owner": "generated", "sourceId": source_sha, "sourcePath": source_path, "reportPath": report_path,
                "group": PurePosixPath(target_path).parts[3], "class": classes_by_path.get(target_path),
                "sourceSha256": source_sha, "moduleIds": [], "dependencies": [], "functions": [], "fields": [],
                "sourceSpanRefs": [], "diagnosticRefs": []})
            if target["sourceId"] != source_sha:
                fail("CODE_POSTPROCESS_FILE_SOURCE_COLLISION", target_path, "One target file is claimed by multiple source partitions")
            target["functions"].append(mapping)
            target["sourceSpanRefs"].append({"kind": "function", "sourceId": method_id,
                "sourceSha256": source_hash, "sourcePath": source_path, "sourceSpan": span})
            target["diagnosticRefs"].append({"kind": "function", "sourceId": method_id,
                "sourceIdSha256": source_hash, "detailsRef": detail_ref})
            function_count_local += 1
            if row.get("kind") == "indexed_method":
                indexed_local += 1
            else:
                auxiliary_local += 1
        coverage = report.get("coverage", {})
        if (function_count_local != coverage.get("functionsMapped")
                or indexed_local != coverage.get("indexedMethodFunctionsEmitted")
                or function_count_local != coverage.get("functionsEmitted")):
            fail("CODE_POSTPROCESS_FUNCTION_COVERAGE", report_path, "Compact source function mappings differ from coverage counters")
        function_mapping_count += function_count_local
        indexed_count += indexed_local
        auxiliary_count += auxiliary_local

        field_count_local = 0
        for field_index, row in enumerate(field_rows):
            loc = f"{report_path}.fields[{field_index}]"
            if not isinstance(row, dict):
                fail("CODE_POSTPROCESS_FIELD_MAPPING", loc, "Expected compact field mapping")
            field_id, target_path = row.get("fieldId"), row.get("targetPath")
            if not isinstance(field_id, str) or target_path not in generated_csharp_paths:
                # Explicitly unresolved member rows remain traceable in source
                # reports but do not name a generated class file. Do not silently
                # count them as covered; report them in the plan's gaps section.
                if row.get("status") == "unresolved_owner" and target_path is None:
                    continue
                fail("CODE_POSTPROCESS_FIELD_MAPPING", loc, "Field mapping has no valid source id or target C# file")
            identity = (source_sha, field_id)
            if identity in field_ids:
                fail("CODE_POSTPROCESS_FIELD_MAPPING", field_id, "Field source mapping is repeated")
            field_ids.add(identity)
            span = _span(row, source_size, loc)
            source_hash = _sha(row.get("sourceSha256"), loc + ".sourceSha256")
            detail_ref = _detail_reference(row, detail_paths, loc)
            mapping = {"fieldId": field_id, "sourceName": row.get("sourceName"),
                "sourceSha256": source_hash, "sourceBytes": span, "targetPath": target_path,
                "targetClass": row.get("targetClass"), "targetMember": row.get("targetMember"),
                "initializationContext": row.get("initializationContext"),
                "initializationPlacement": row.get("initializationPlacement"), "status": row.get("status"),
                "detailsRef": detail_ref}
            target = planned_files.setdefault(target_path, {"path": target_path,
                "sha256": inventory[target_path]["sha256"], "bytes": inventory[target_path]["bytes"],
                "owner": "generated", "sourceId": source_sha, "sourcePath": source_path, "reportPath": report_path,
                "group": PurePosixPath(target_path).parts[3], "class": classes_by_path.get(target_path),
                "sourceSha256": source_sha, "moduleIds": [], "dependencies": [], "functions": [], "fields": [],
                "sourceSpanRefs": [], "diagnosticRefs": []})
            if target["sourceId"] != source_sha:
                fail("CODE_POSTPROCESS_FILE_SOURCE_COLLISION", target_path, "One target file is claimed by multiple source partitions")
            target["fields"].append(mapping)
            target["sourceSpanRefs"].append({"kind": "field", "sourceId": field_id,
                "sourceSha256": source_hash, "sourcePath": source_path, "sourceSpan": span})
            target["diagnosticRefs"].append({"kind": "field", "sourceId": field_id,
                "sourceSha256": source_hash, "detailsRef": detail_ref})
            field_count_local += 1
        if field_count_local != coverage.get("fieldRecords", field_count_local):
            fail("CODE_POSTPROCESS_FIELD_COVERAGE", report_path, "Compact field mappings differ from field record coverage")
        field_mapping_count += field_count_local

    # Every generated C# target is represented, including empty/class-shell
    # drafts. Unmapped files remain explicit plan items with empty mappings.
    for path in sorted(generated_csharp_paths):
        if path not in planned_files:
            owner_source = next((info for info in source_infos
                if f"/CSharp/{info['sourceId'][:12]}/" in "/" + path), None)
            if owner_source is None:
                parts = PurePosixPath(path).parts
                origin_group = "/".join(parts[:3]) if len(parts) >= 3 else parts[0]
                header_path = safe(root / path)
                try:
                    with header_path.open("rb") as stream:
                        header_bytes = stream.read(4096)
                except OSError as exc:
                    fail("CODE_POSTPROCESS_READ", path, "Unable to inspect C# origin header: " + type(exc).__name__)
                header_match = _SOURCE_MODULE_HEADER.search(header_bytes)
                declared_sha = header_match.group(1).decode("ascii") if header_match else None
                module_source_path = None
                source_kind = "native-generated-CSharp" if path.startswith("Assets/") else "generated-CSharp-no-JS-source"
                source_id = None
                if declared_sha:
                    candidates = js_ts_by_sha.get(declared_sha, [])
                    if candidates:
                        module_source_path = candidates[0]
                        source_entry, _ = _verify_file(root, module_source_path, inventory)
                        if source_entry["sha256"] != declared_sha:
                            fail("CODE_POSTPROCESS_SOURCE_PIN", module_source_path,
                                 "Legacy C# declared source module SHA-256 does not match the owning manifest")
                        source_kind = "hash-proven-legacy-module"
                        source_id = declared_sha
                        if declared_sha not in {info["sourceId"] for info in source_infos} and not any(
                                info["sha256"] == declared_sha for info in extra_source_infos):
                            extra_source_infos.append({"sourceOrder": len(source_infos) + len(extra_source_infos),
                                "sourceId": declared_sha, "sha256": declared_sha,
                                "bytes": source_entry["bytes"], "sourcePath": module_source_path,
                                "reportPath": None, "sourceKind": source_kind, "sourceWholeModule": True,
                                "diagnosticSummary": None, "functions": None, "indexedMethods": None,
                                "fields": None})
                if declared_sha and module_source_path is None:
                    source_kind = "declared-source-module-not-found"
                    absent_reason = ("declared source module SHA256 " + declared_sha
                        + " was not found among manifest-owned .js/.ts files; review exact owning C# bytes, do not fabricate source")
                elif source_kind == "native-generated-CSharp":
                    absent_reason = "native generated C# helper has no source-map contract; review exact owning C# bytes, do not fabricate a JavaScript mapping"
                else:
                    absent_reason = "native generated helper or earlier draft lacks compact full-JS function map; review exact owning C# bytes, do not fabricate source"
                planned_files[path] = {"path": path, "sha256": inventory[path]["sha256"],
                    "bytes": inventory[path]["bytes"], "owner": "generated", "sourceId": source_id,
                    "sourceSha256": source_id, "sourcePath": module_source_path, "reportPath": None,
                    "group": "ExtraCode/" + origin_group, "class": None, "moduleIds": [],
                    "dependencies": [], "functions": [], "fields": [], "sourceSpanRefs": [],
                    "diagnosticRefs": [], "extraCode": True, "sourceKind": source_kind,
                    "sourceWholeModule": bool(source_id), "declaredSourceModuleSha256": declared_sha,
                    "absentSourceReason": absent_reason if not source_id else None}
                continue
            class_row = class_rows_by_path.get(path)
            planned_files[path] = {"path": path, "sha256": inventory[path]["sha256"],
                "bytes": inventory[path]["bytes"], "owner": "generated", "sourceId": owner_source["sourceId"],
                "sourcePath": owner_source["sourcePath"], "reportPath": owner_source["reportPath"],
                "group": PurePosixPath(path).parts[3], "class": class_row, "moduleIds": [],
                "sourceSha256": owner_source["sourceId"], "dependencies": [], "functions": [], "fields": [],
                "sourceSpanRefs": [], "diagnosticRefs": [],
                "mappingStatus": ("class_without_function_or_field_rows" if class_row else "no_class_or_member_mapping")}

    for entry in blocked_csharp_entries:
        path, owner = entry["path"], entry["owner"]
        parts = PurePosixPath(path).parts
        origin_group = "/".join(parts[:3]) if len(parts) >= 3 else parts[0]
        planned_files[path] = {"path": path, "sha256": entry["sha256"], "bytes": entry["bytes"],
            "owner": owner, "sourceId": None, "sourceSha256": None, "sourcePath": None,
            "reportPath": None, "group": "BlockedOwner/" + origin_group, "class": None,
            "moduleIds": [], "dependencies": [], "functions": [], "fields": [],
            "sourceSpanRefs": [], "diagnosticRefs": [], "status": "blocked_owner",
            "blockedReason": "manifest owner is not generated; retained for read-only inspection and never queued for rewrite"}

    for path, file_row in planned_files.items():
        file_row["moduleIds"] = sorted(set(modules_by_path.get(path, [])))
        file_row["dependencies"] = sorted(file_dependencies.get(path, set()))
        file_row["functions"].sort(key=lambda row: (row["sourceBytes"]["start"], row["methodId"]))
        file_row["fields"].sort(key=lambda row: (row["sourceBytes"]["start"], row["fieldId"]))
        file_row["sourceSpanRefs"].sort(key=lambda row: (row["sourceSpan"]["start"], row["sourceId"]))
        file_row["diagnosticRefs"].sort(key=lambda row: (row["detailsRef"]["path"], row["detailsRef"]["index"], row["sourceId"]))

    all_sources = source_infos + extra_source_infos
    source_order = {row["sourceId"]: row["sourceOrder"] for row in all_sources}
    file_rows = sorted(planned_files.values(), key=lambda row: (
        source_order.get(row["sourceId"], 2**31), row["group"], row["path"]))
    batch_file_rows = [row for row in file_rows if row["owner"] == "generated"]
    batches, batch_for_path = [], {}
    bucketed = defaultdict(list)
    for row in batch_file_rows:
        kind = row.get("sourceKind")
        if kind in ("hash-proven-legacy-module", "native-generated-CSharp", "declared-source-module-not-found", "generated-CSharp-no-JS-source"):
            partition_key = "shared:" + kind + ":" + row["group"]
        else:
            partition_key = "source:" + str(row["sourceId"]) + ":" + row["group"]
        bucketed[(partition_key, row["group"])].append(row)
    batch_index = 0
    for (partition_key, group), rows in sorted(bucketed.items(), key=lambda item: (
            min(source_order.get(row["sourceId"], 2**31) for row in item[1]), item[0][1], item[0][0])):
        pending, pending_bytes, part = [], 0, 0
        shared_partition = partition_key.startswith("shared:")
        shared_kind = partition_key.split(":", 2)[1] if shared_partition else None

        def flush(oversize=False):
            nonlocal batch_index, pending, pending_bytes, part
            if not pending:
                return
            part += 1
            batch_index += 1
            rows_for_batch = list(pending)
            source_id = rows_for_batch[0]["sourceId"] if not shared_partition else None
            batch_id = _batch_id(batch_index, source_id, group, part)
            mappings = [{"path": file["path"], "kind": mapping_kind, "index": index,
                         "sourceId": mapping.get("methodId", mapping.get("fieldId"))}
                        for file in rows_for_batch
                        for mapping_kind, field in (("function", "functions"), ("field", "fields"))
                        for index, mapping in enumerate(file[field])]
            diag_refs = [{"path": file["path"], "kind": ref["kind"], "sourceId": ref["sourceId"],
                          "detailsRef": ref["detailsRef"]}
                         for file in rows_for_batch for ref in file["diagnosticRefs"]]
            dependency_refs = [{"fromPath": file["path"], "moduleId": dep,
                "targetPaths": module_path_by_id.get(dep, []), "resolved": dep in module_path_by_id}
                for file in rows_for_batch for dep in file["dependencies"]]
            batch = {"id": batch_id, "paths": [file["path"] for file in rows_for_batch],
                "bytes": pending_bytes,
                "sourceIds": sorted({file["sourceId"] for file in rows_for_batch if file.get("sourceId")}),
                "sourceKind": shared_kind, "group": group,
                "dependsOn": [], "dependencyReferences": dependency_refs,
                "dependencyOrdering": "advisory_only_cycles_never_block_queue",
                "mappingRefs": mappings, "diagnosticRefs": diag_refs,
                "functionMappings": sum(len(file["functions"]) for file in rows_for_batch),
                "indexedMappings": sum(sum(m["kind"] == "indexed_method" for m in file["functions"])
                                        for file in rows_for_batch),
                "fieldMappings": sum(len(file["fields"]) for file in rows_for_batch),
                "oversizeSingleFile": bool(oversize)}
            batches.append(batch)
            for file in rows_for_batch:
                batch_for_path[file["path"]] = batch_id
            pending, pending_bytes = [], 0

        for row in rows:
            size = row["bytes"]
            if size > max_code_bytes:
                flush()
                pending, pending_bytes = [row], size
                flush(oversize=True)
                continue
            if pending and (len(pending) >= max_files or pending_bytes + size > max_code_bytes):
                flush()
            pending.append(row)
            pending_bytes += size
        flush()

    # Dependency targets are references only. Keep the queue acyclic and stable;
    # the source/group batches remain runnable even if modules form strong cycles.
    batch_index_by_id = {row["id"]: index for index, row in enumerate(batches)}
    for batch in batches:
        hints = set()
        for dep in batch["dependencyReferences"]:
            for target_path in dep["targetPaths"]:
                target_batch = batch_for_path.get(target_path)
                if target_batch and target_batch != batch["id"]:
                    hints.add(target_batch)
        batch["dependencyBatchHints"] = sorted(hints, key=lambda item: batch_index_by_id[item])

    occurrences = Counter(path for batch in batches for path in batch["paths"])
    if set(occurrences) != generated_csharp_paths or any(count != 1 for count in occurrences.values()):
        fail("CODE_POSTPROCESS_EXACT_ONCE", "batches", "Generated C# files are not partitioned exactly once")
    if sum(batch["bytes"] for batch in batches) != sum(row["bytes"] for row in batch_file_rows):
        fail("CODE_POSTPROCESS_BATCH_BYTES", "batches", "Batched source bytes differ from file index")
    if sum(batch["functionMappings"] for batch in batches) != function_mapping_count:
        fail("CODE_POSTPROCESS_FUNCTION_COVERAGE", "batches", "Function mappings are not present exactly once")
    if sum(batch["fieldMappings"] for batch in batches) != field_mapping_count:
        fail("CODE_POSTPROCESS_FIELD_COVERAGE", "batches", "Field mappings are not present exactly once")

    return {"schemaVersion": 1, "kind": "csharp-draft-postprocess-plan",
        "candidate": {"manifestSha256": manifest_sha, "schemaVersion": 1,
            "scopeMode": manifest.get("scopeMode"), "path": str(root)},
        "limits": {"maxFiles": max_files, "maxCodeBytes": max_code_bytes,
            "oversizeFilesAreAtomic": True, "diagnosticShardBodiesRead": 0},
        "coverage": {"sourceReports": len(source_infos), "sourceModules": len(extra_source_infos),
            "codeFiles": len(generated_csharp_paths), "manifestCsharpFiles": len(csharp_paths),
            "codeBytes": sum(row["bytes"] for row in batch_file_rows),
            "blockedFiles": len(blocked_csharp_entries),
            "extraCodeFiles": sum(bool(row.get("extraCode")) for row in file_rows),
            "extraCodeBytes": sum(row["bytes"] for row in file_rows if row.get("extraCode")),
            "hashProvenLegacyModules": len(extra_source_infos),
            "nativeGeneratedCSharpFiles": sum(row.get("sourceKind") == "native-generated-CSharp" for row in file_rows),
            "missingLegacySourceModules": sum(row.get("sourceKind") == "declared-source-module-not-found" for row in file_rows),
            "functions": function_mapping_count,
            "indexedMethods": indexed_count, "auxiliaryFunctions": auxiliary_count,
            "fields": field_mapping_count, "diagnostics": diagnostic_total,
            "batches": len(batches), "exactOnceFiles": len(occurrences),
            "unmappedFiles": sum(row.get("mappingStatus") == "no_class_or_member_mapping"
                                  for row in file_rows if row["owner"] == "generated"),
            "classOnlyFiles": sum(row.get("mappingStatus") == "class_without_function_or_field_rows"
                                  for row in file_rows if row["owner"] == "generated")},
        "sources": all_sources, "files": file_rows, "batches": batches,
        "contextEvidence": {"kind": "bounded-read-only-source-fragments",
            "sourceSpanField": "files[].functions[].sourceBytes and files[].fields[].sourceBytes",
            "byteConvention": "UTF-8 source byte offsets, half-open [start,end)",
            "completeFragments": "Caller may build bounded __Context/source-fragments.json from these exact source pins and spans; no source text is duplicated into this plan."},
        "diagnosticPolicy": {"compactCounts": "per-source countsByCode from the compact report",
            "perMapping": "detailsRef path and record index; detail shard bodies were not loaded",
            "queueBehavior": "dependency edges are advisory hints; cycles do not block source-order execution"}}
