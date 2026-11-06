"""Read-only build asset classification and reversible quarantine planning.

This module deliberately does not move or delete assets. A plan is only eligible
for later native isolation when the Editor dependency snapshot proves that the
asset is outside build roots and an independently hashed source-evidence record
matches the current asset bytes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .errors import fail
from .io import safe, inside, load, read, write_json

_TARGET = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_CLASSES = {"source", "binary", "unknown"}
_HEX = re.compile(r"^[0-9a-f]{64}$")
_GUID = re.compile(r"^[0-9a-fA-F]{32}$")


def _path(value, where):
    if (not isinstance(value, str) or not value.startswith("Assets/") or "\\" in value
            or any(part in ("", ".", "..") for part in value.split("/"))):
        fail("BUILD_FILTER_PATH", where, "Expected normalized project-relative Assets/... path")
    return value


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _meta_guid(path):
    match = re.search(rb"(?m)^guid:\s*([0-9a-fA-F]{32})\s*$", path.read_bytes())
    return match.group(1).decode("ascii").lower() if match else None


def _closed(obj, keys, where):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        fail("BUILD_FILTER_SCHEMA", where, f"Expected exactly fields {sorted(keys)}")


def _snapshot(snapshot, target, require_runner=False):
    required = {"schemaVersion", "target", "pipeline", "buildScenes", "explicitRoots", "implicitRoots", "coverage", "assets", "dependencies", "unresolvedDependencies"}
    runner_fields = {"editorExitCode", "inputState", "nativeReadback", "sourceUnchanged", "unplannedProjectChanges",
                     "helperCleaned", "visualAcceptance", "gameplayAcceptance"}
    if not isinstance(snapshot, dict) or not required <= set(snapshot) or set(snapshot) - required - runner_fields:
        fail("BUILD_FILTER_SCHEMA", "snapshot", "Missing snapshot fields or unknown native runner metadata")
    if require_runner and not runner_fields <= set(snapshot):
        fail("BUILD_FILTER_NATIVE_GUARD", "snapshot", "Shared collector read-only guard receipt is incomplete")
    for field in ("sourceUnchanged", "helperCleaned"):
        if field in snapshot and snapshot[field] is not True:
            fail("BUILD_FILTER_NATIVE_GUARD", field, "Native read-only runner guard did not pass")
    if "editorExitCode" in snapshot and (type(snapshot["editorExitCode"]) is not int or snapshot["editorExitCode"] != 0):
        fail("BUILD_FILTER_NATIVE_EXIT", "editorExitCode", "Native Editor collector did not exit successfully")
    if "unplannedProjectChanges" in snapshot and snapshot["unplannedProjectChanges"] != []:
        fail("BUILD_FILTER_NATIVE_GUARD", "unplannedProjectChanges", "Native collector changed project files")
    if type(snapshot["schemaVersion"]) is not int or snapshot["schemaVersion"] != 1 or snapshot["target"] != target["platform"]:
        fail("BUILD_FILTER_SNAPSHOT_IDENTITY", "snapshot", "Schema or platform does not match request")
    if not isinstance(snapshot["pipeline"], str) or not snapshot["pipeline"]:
        fail("BUILD_FILTER_PIPELINE", "snapshot.pipeline", "Exact active render pipeline identity is required")
    for field in ("buildScenes", "explicitRoots"):
        if not isinstance(snapshot[field], list):
            fail("BUILD_FILTER_SCHEMA", "snapshot." + field, "Expected array")
        for i, path in enumerate(snapshot[field]):
            _path(path, f"snapshot.{field}[{i}]")
    if not isinstance(snapshot["implicitRoots"], list) or any(value not in ("implicit:Resources", "implicit:StreamingAssets", "implicit:PreloadedAssets") for value in snapshot["implicitRoots"]):
        fail("BUILD_FILTER_SCHEMA", "snapshot.implicitRoots", "Unknown Unity implicit build root")
    if (not isinstance(snapshot["coverage"], dict) or set(snapshot["coverage"]) != {"complete", "blockers"}
            or type(snapshot["coverage"]["complete"]) is not bool or not isinstance(snapshot["coverage"]["blockers"], list)
            or any(not isinstance(value, str) for value in snapshot["coverage"]["blockers"])):
        fail("BUILD_FILTER_SCHEMA", "snapshot.coverage", "Expected explicit dependency coverage state")
    if not isinstance(snapshot["inputState"], dict):
        fail("BUILD_FILTER_INPUT_STATE", "snapshot.inputState", "Expected path-to-content-hash preconditions")
    assets = {}
    object_identity_mode = None
    for i, row in enumerate(snapshot["assets"]):
        legacy_fields = {"path", "guid", "localIds", "types"}
        prior_fields = legacy_fields | {"status", "error"}
        current_fields = prior_fields | {"identityStatus", "objectCount"}
        object_fields = current_fields | {"objects"}
        if not isinstance(row, dict) or set(row) not in (legacy_fields, prior_fields, current_fields,
                                                         legacy_fields | {"objects"}, prior_fields | {"objects"}, object_fields):
            fail("BUILD_FILTER_SCHEMA", f"snapshot.assets[{i}]", "Expected persistent asset identity or explicit unknown identity row")
        has_objects = "objects" in row
        if object_identity_mode is None:
            object_identity_mode = has_objects
        elif object_identity_mode != has_objects:
            fail("BUILD_FILTER_ASSET_IDENTITY", f"snapshot.assets[{i}]", "Object identity records must be present consistently for the full native catalog")
        path = _path(row["path"], f"snapshot.assets[{i}].path")
        status = row.get("status", "observed")
        error = row.get("error", "")
        guid = row["guid"]
        identity_status = row.get("identityStatus", "verified" if status == "observed" else "inspection-failed")
        object_count = row.get("objectCount", max(1, len(row["localIds"])) if status == "observed" else -1)
        valid_guid = isinstance(guid, str) and bool(_GUID.fullmatch(guid))
        if path in assets or status not in ("observed", "unknown"):
            fail("BUILD_FILTER_ASSET_IDENTITY", path, "Duplicate path or unsupported native asset status")
        if status == "observed" and not valid_guid:
            fail("BUILD_FILTER_ASSET_IDENTITY", path, "Observed assets require an exact Unity GUID")
        if status == "unknown" and (guid not in ("", None) and not valid_guid):
            fail("BUILD_FILTER_ASSET_IDENTITY", path, "Unknown rows may retain a valid native GUID or leave it explicitly empty")
        if not isinstance(row["localIds"], list) or any(type(value) is not int or value == 0 for value in row["localIds"]):
            fail("BUILD_FILTER_ASSET_IDENTITY", path, "Known local IDs must be persistent nonzero integers")
        if not isinstance(row["types"], list) or any(not isinstance(value, str) or not value for value in row["types"]):
            fail("BUILD_FILTER_ASSET_IDENTITY", path, "Known Unity types must be nonempty strings")
        if identity_status not in ("verified", "no-persistent-object", "persistent-identity-unavailable", "inspection-failed"):
            fail("BUILD_FILTER_ASSET_IDENTITY", path, "Unknown identity status is unsupported")
        if type(object_count) is not int or object_count < -1:
            fail("BUILD_FILTER_ASSET_IDENTITY", path, "Expected objectCount >= 0 or -1 when inspection failed")
        if status == "observed" and (identity_status != "verified" or object_count <= 0 or not row["localIds"] or not row["types"] or error):
            fail("BUILD_FILTER_ASSET_IDENTITY", path, "Observed rows require persistent identities/types and no error")
        if status == "unknown" and (not isinstance(error, str) or not error.strip()):
            fail("BUILD_FILTER_ASSET_IDENTITY", path, "Unknown identity requires a specific native failure reason")
        if status == "unknown":
            consistent_status = ((identity_status == "no-persistent-object" and object_count == 0 and not row["localIds"] and not row["types"])
                                 or (identity_status == "persistent-identity-unavailable" and object_count > 0)
                                 or (identity_status == "inspection-failed" and object_count == -1))
            if not consistent_status:
                fail("BUILD_FILTER_ASSET_IDENTITY", path, "Unknown status, objectCount and available identities disagree")
        if has_objects:
            objects = row["objects"]
            if not isinstance(objects, list):
                fail("BUILD_FILTER_ASSET_IDENTITY", path, "objects must be an array when requested")
            object_keys = set()
            object_ids = set()
            object_types = set()
            for index, obj in enumerate(objects):
                _closed(obj, {"guid", "localId", "type", "name", "state"}, f"snapshot.assets[{i}].objects[{index}]")
                if (not isinstance(obj["guid"], str) or not _GUID.fullmatch(obj["guid"])
                        or type(obj["localId"]) is not int or obj["localId"] == 0
                        or not isinstance(obj["type"], str) or not obj["type"]
                        or not isinstance(obj["name"], str) or obj["state"] != "persistent"):
                    fail("BUILD_FILTER_ASSET_IDENTITY", path, "Objects require an actual persistent GUID/localID/type/name pair")
                if valid_guid and obj["guid"].lower() != guid.lower():
                    fail("BUILD_FILTER_ASSET_IDENTITY", path, "Object GUID differs from its AssetDatabase catalog GUID")
                key = (obj["guid"].lower(), obj["localId"])
                if key in object_keys:
                    fail("BUILD_FILTER_ASSET_IDENTITY", path, "Duplicate persistent object identity")
                object_keys.add(key)
                object_ids.add(obj["localId"])
                object_types.add(obj["type"])
            if not object_ids <= set(row["localIds"]) or not object_types <= set(row["types"]):
                fail("BUILD_FILTER_ASSET_IDENTITY", path, "Objects must be represented in the legacy localIds and types unions")
            if status == "observed" and (object_ids != set(row["localIds"]) or object_types != set(row["types"])):
                fail("BUILD_FILTER_ASSET_IDENTITY", path, "Fully observed objects must exactly match the legacy localIds and types unions")
            if object_count == 0 and objects:
                fail("BUILD_FILTER_ASSET_IDENTITY", path, "Zero-object assets must have an empty objects array")
            if status == "observed" and len(objects) > object_count:
                fail("BUILD_FILTER_ASSET_IDENTITY", path, "Persistent object pairs cannot exceed objectCount")
        assets[path] = dict(row, status=status, identityStatus=identity_status, objectCount=object_count,
                            error=error, guid=guid or "")
    dependencies = {}
    for i, row in enumerate(snapshot["dependencies"]):
        _closed(row, {"path", "guid", "localId", "type", "roots"}, f"snapshot.dependencies[{i}]")
        path = _path(row["path"], f"snapshot.dependencies[{i}].path")
        if (path not in assets or not isinstance(row["guid"], str) or not _GUID.fullmatch(row["guid"])
                or not _GUID.fullmatch(assets[path]["guid"]) or row["guid"].lower() != assets[path]["guid"].lower()):
            fail("BUILD_FILTER_DEPENDENCY_IDENTITY", path, "Dependency does not resolve to the active asset catalog identity")
        if (type(row["localId"]) is not int or row["localId"] == 0 or not isinstance(row["type"], str)
                or not row["type"] or row["localId"] not in assets[path]["localIds"] or row["type"] not in assets[path]["types"]):
            fail("BUILD_FILTER_DEPENDENCY_IDENTITY", path, "Dependency needs persistent localID and type")
        allowed_roots = snapshot["buildScenes"] + snapshot["explicitRoots"] + snapshot["implicitRoots"]
        if not isinstance(row["roots"], list) or any(root not in allowed_roots for root in row["roots"]):
            fail("BUILD_FILTER_DEPENDENCY_ROOT", path, "Dependency roots must name declared build scenes or explicit roots")
        key = (path, row["localId"])
        if key in dependencies:
            fail("BUILD_FILTER_DEPENDENCY_DUPLICATE", path, "Duplicate dependency identity")
        dependencies[key] = row
    unresolved = {}
    allowed_roots = snapshot["buildScenes"] + snapshot["explicitRoots"] + snapshot["implicitRoots"]
    if not isinstance(snapshot["unresolvedDependencies"], list):
        fail("BUILD_FILTER_SCHEMA", "snapshot.unresolvedDependencies", "Expected array of explicit path-only dependency failures")
    for i, row in enumerate(snapshot["unresolvedDependencies"]):
        _closed(row, {"path", "guid", "roots", "error"}, f"snapshot.unresolvedDependencies[{i}]")
        path = _path(row["path"], f"snapshot.unresolvedDependencies[{i}].path")
        guid = row["guid"]
        if guid not in ("", None) and (not isinstance(guid, str) or not _GUID.fullmatch(guid)):
            fail("BUILD_FILTER_DEPENDENCY_IDENTITY", path, "Unresolved dependency may retain only an exact native GUID or empty value")
        if path in assets and assets[path]["status"] != "unknown":
            fail("BUILD_FILTER_DEPENDENCY_IDENTITY", path, "Unresolved dependency must map to an explicitly unknown catalog row")
        if not isinstance(row["roots"], list) or not row["roots"] or any(root not in allowed_roots for root in row["roots"]):
            fail("BUILD_FILTER_DEPENDENCY_ROOT", path, "Unresolved dependency roots must be explicit build or implicit roots")
        if not isinstance(row["error"], str) or not row["error"].strip() or path in unresolved:
            fail("BUILD_FILTER_DEPENDENCY_IDENTITY", path, "Unresolved dependency requires one unique path and a failure reason")
        unresolved[path] = dict(row, guid=guid or "")
    return assets, dependencies, unresolved


def _native_identity_blockers(snapshot):
    blockers = [f"Native asset identity unavailable: {row['path']} — {row['error']}"
                for row in snapshot["assets"] if row.get("status") == "unknown"]
    blockers.extend(f"Native dependency identity unavailable: {row['path']} — {row['error']}"
                    for row in snapshot["unresolvedDependencies"])
    return blockers


def _project_source_files(root):
    """Enumerate current source inputs that can invalidate a native closure."""
    result = set()
    for scope in ("Assets", "Packages", "ProjectSettings"):
        base = inside(root, scope)
        if not base.is_dir():
            fail("BUILD_FILTER_INPUT_STATE", scope, "Project source root is missing")
        for directory, subdirs, files in os.walk(base, followlinks=False):
            parent = Path(directory)
            for name in subdirs + files:
                candidate = parent / name
                if candidate.is_symlink():
                    fail("BUILD_FILTER_INPUT_STATE", str(candidate), "Symlink prevents complete native input verification")
            for name in files:
                candidate = parent / name
                relative = candidate.relative_to(root).as_posix()
                if relative == "Assets/BeaverReadbackTools" or relative.startswith("Assets/BeaverReadbackTools/"):
                    continue
                if relative.endswith(".meta") and candidate.with_name(candidate.name[:-5]).is_dir():
                    continue
                result.add(relative)
    return result


def _verify_input_state(project, snapshot):
    """Reject stale snapshots if any source, settings, package, or catalog path changed."""
    root = safe(project)
    state = snapshot["inputState"]
    if not all(isinstance(path, str) and (path.startswith("Assets/") or path.startswith("Packages/") or path.startswith("ProjectSettings/"))
               for path in state):
        fail("BUILD_FILTER_INPUT_STATE", "snapshot.inputState", "Only project-relative Assets, Packages, and ProjectSettings inputs are accepted")
    catalog_paths = {asset["path"] for asset in snapshot["assets"]}
    explicitly_selected = set(snapshot["buildScenes"] + snapshot["explicitRoots"])
    unresolved_paths = {row["path"] for row in snapshot["unresolvedDependencies"]}
    required_asset_paths = catalog_paths | explicitly_selected | unresolved_paths
    required_assets = {path for asset_path in required_asset_paths for path in (asset_path, asset_path + ".meta")}
    required = set(required_assets)
    missing = sorted(required - set(state))
    if missing:
        fail("BUILD_FILTER_INPUT_STATE_INCOMPLETE", "snapshot.inputState", "Missing required content preconditions: " + ", ".join(missing[:8]))
    optional_settings = {"ProjectSettings/EditorBuildSettings.asset", "ProjectSettings/GraphicsSettings.asset", "ProjectSettings/QualitySettings.asset"}
    optional_missing = set()
    for path, recorded in state.items():
        if recorded is None and path in optional_settings:
            if inside(root, path).exists():
                fail("BUILD_FILTER_STALE_SNAPSHOT", path, "Previously missing build setting appeared after collection")
            optional_missing.add(path)
            continue
        if (not isinstance(recorded, dict) or set(recorded) != {"sha256", "bytes"}
                or not isinstance(recorded["sha256"], str) or not _HEX.fullmatch(recorded["sha256"])
                or type(recorded["bytes"]) is not int or recorded["bytes"] < 0):
            fail("BUILD_FILTER_INPUT_STATE", path, "Expected SHA-256 and byte count for every tracked project input")
        current = inside(root, path)
        if not current.is_file() or current.is_symlink():
            fail("BUILD_FILTER_STALE_SNAPSHOT", path, "A recorded project input was removed or replaced")
        if current.stat().st_size != recorded["bytes"] or _sha(current) != recorded["sha256"]:
            fail("BUILD_FILTER_STALE_SNAPSHOT", path, "Project input changed after native dependency collection")
    current_files = _project_source_files(root)
    recorded_assets = {path for path in state if path.startswith("Assets/")}
    if recorded_assets != required_assets:
        fail("BUILD_FILTER_INPUT_STATE_INCOMPLETE", "snapshot.inputState", "Assets preconditions must contain each catalog/selected path and adjacent .meta")
    current_assets = {path for path in current_files if path.startswith("Assets/")}
    missing_assets = sorted(required_assets - current_assets)
    if missing_assets:
        fail("BUILD_FILTER_STALE_SNAPSHOT", "snapshot.inputState", "A catalog asset or .meta was removed: " + ", ".join(missing_assets[:8]))
    # Unimported filesystem items cannot be safely classified from this closure.
    uncovered = sorted(current_assets - required_assets)
    unimported_selected = sorted((explicitly_selected | unresolved_paths) - catalog_paths)
    recorded_non_assets = {path for path in state if (path.startswith("Packages/") or path.startswith("ProjectSettings/")) and path not in optional_missing}
    current_non_assets = current_files - current_assets
    if recorded_non_assets != current_non_assets:
        added = sorted(current_non_assets - recorded_non_assets)
        removed = sorted(recorded_non_assets - current_non_assets)
        fail("BUILD_FILTER_STALE_SNAPSHOT", "snapshot.inputState", f"Packages/ProjectSettings changed after collection; added={added[:8]} removed={removed[:8]}")
    blockers = ["Unimported Assets filesystem entries are outside the native AssetDatabase catalog: " + path for path in uncovered]
    blockers.extend("Selected root has no imported AssetDatabase catalog identity: " + path for path in unimported_selected)
    for path in ("ProjectSettings/EditorBuildSettings.asset", "ProjectSettings/GraphicsSettings.asset", "ProjectSettings/QualitySettings.asset"):
        if path not in state or path in optional_missing:
            blockers.append("Required build settings were not captured: " + path)
    return blockers


def validate_collect_spec(project, spec):
    required = {"schemaVersion", "platform", "renderPipeline", "assets", "roots"}
    if not isinstance(spec, dict) or not required <= set(spec) or set(spec) - required - {"includeObjectIdentities"}:
        fail("BUILD_FILTER_SCHEMA", "spec", "Missing required collection fields or unknown optional fields")
    if "includeObjectIdentities" in spec and type(spec["includeObjectIdentities"]) is not bool:
        fail("BUILD_FILTER_SPEC", "includeObjectIdentities", "Expected an explicit boolean when provided")
    if type(spec["schemaVersion"]) is not int or spec["schemaVersion"] != 1 or not isinstance(spec["platform"], str) or not _TARGET.fullmatch(spec["platform"]):
        fail("BUILD_FILTER_SPEC", "spec", "Expected schemaVersion 1 and explicit Unity BuildTarget name")
    if not isinstance(spec["renderPipeline"], str) or not spec["renderPipeline"]:
        fail("BUILD_FILTER_SPEC", "renderPipeline", "Exact current pipeline identity required")
    if (not isinstance(spec["assets"], list) or len(spec["assets"]) > 256
            or any(not isinstance(path, str) for path in spec["assets"]) or len(set(spec["assets"])) != len(spec["assets"])):
        fail("BUILD_FILTER_SPEC", "assets", "Expected at most 256 unique enabled build scene paths")
    if (not isinstance(spec["roots"], list) or len(spec["roots"]) > 256
            or any(not isinstance(path, str) for path in spec["roots"]) or len(set(spec["roots"])) != len(spec["roots"])):
        fail("BUILD_FILTER_SPEC", "roots", "Expected at most 256 unique explicit roots")
    if not spec["assets"] and not spec["roots"]:
        fail("BUILD_FILTER_SPEC", "assets", "At least one enabled scene or explicit root is required")
    for i, path in enumerate(spec["assets"]):
        _path(path, f"spec.assets[{i}]")
        if not path.endswith(".unity"):
            fail("BUILD_FILTER_SPEC", f"spec.assets[{i}]", "Enabled build scene path must end in .unity")
    for i, path in enumerate(spec["roots"]):
        _path(path, f"spec.roots[{i}]")
    root = safe(project)
    for path in spec["assets"] + spec["roots"]:
        if not inside(root, path).is_file():
            fail("BUILD_FILTER_INPUT", path, "Selected scene/root must be an existing regular Assets file")
    return spec


def collect(project, spec_path, output, editor, timeout=600):
    """Run a guarded collector and return a CLI summary outside the saved snapshot.

    The UTF-8 build-snapshot.json remains schemaVersion=1 and contains coverage,
    not a top-level status field. The returned summary adds `status` and `report`
    for CLI presentation; its coverage content matches the persisted snapshot.
    """
    spec = validate_collect_spec(project, load(read(safe(spec_path))))
    from .native_readback import run_collector
    report = run_collector(project, spec, output, editor, "BeaverBuildFilter.cs", "BeaverBuildFilter.Run",
                           "build-snapshot.json", timeout)
    if sorted(report["buildScenes"]) != sorted(spec["assets"]) or sorted(report["explicitRoots"]) != sorted(spec["roots"]):
        fail("BUILD_FILTER_SNAPSHOT_IDENTITY", "snapshot", "Native scene/root set differs from request")
    requested_object_identities = spec.get("includeObjectIdentities", False)
    if any(("objects" in row) != requested_object_identities for row in report.get("assets", []) if isinstance(row, dict)):
        fail("BUILD_FILTER_SNAPSHOT_IDENTITY", "snapshot.assets", "Native object identity payload differs from collection request")
    _snapshot(report, {"platform": spec["platform"], "pipeline": spec["renderPipeline"]}, require_runner=True)
    blockers = _verify_input_state(project, report)
    blockers.extend(_native_identity_blockers(report))
    if blockers:
        report["coverage"] = {"complete": False, "blockers": sorted(set(report["coverage"]["blockers"] + blockers))}
        write_json(safe(output) / "build-snapshot.json", report)
    report_path = str(safe(output) / "build-snapshot.json")
    partial = (report["coverage"]["complete"] is not True or bool(report["coverage"]["blockers"])
               or any(row.get("status") == "unknown" for row in report["assets"])
               or bool(report["unresolvedDependencies"]))
    summary = dict(report, status="partial" if partial else "observed", report=report_path)
    if requested_object_identities:
        # Keep the full pair list in the saved, guarded snapshot; CLI output stays compact.
        summary["assets"] = [{key: value for key, value in row.items() if key != "objects"}
                             for row in report["assets"]]
        summary["objectIdentityCount"] = sum(len(row.get("objects", [])) for row in report["assets"])
    return summary


def _plan_root(value, where):
    if (not isinstance(value, str) or not value or value.startswith("/") or "\\" in value
            or any(part in ("", ".", "..") for part in value.split("/")) or value == "Assets" or value.startswith("Assets/")):
        fail("BUILD_FILTER_PATH", where, "Expected normalized project-relative path outside Assets")
    return value


def plan(project, target, snapshot, source_manifest, backup_root=".beaver/build-filter/backups",
         quarantine_root=".beaver/build-filter/quarantine"):
    """Create a deterministic, read-only build filter plan from native evidence.

    ``source_manifest`` is the monkey handoff list. It conveys source/binary
    evidence, but a record is accepted only when both current file and .meta
    hashes match. No path suffix is interpreted as a compiler or runtime fact.
    """
    _closed(target, {"platform", "pipeline"}, "target")
    if not isinstance(target["platform"], str) or not _TARGET.fullmatch(target["platform"]) or not isinstance(target["pipeline"], str) or not target["pipeline"]:
        fail("BUILD_FILTER_TARGET", "target", "Explicit Unity BuildTarget name and render pipeline identity required")
    if not isinstance(snapshot, dict) or snapshot.get("pipeline") != target["pipeline"]:
        fail("BUILD_FILTER_PIPELINE_MISMATCH", "snapshot.pipeline", "Native snapshot pipeline must exactly match target")
    assets, dependencies, unresolved_dependencies = _snapshot(snapshot, target)
    if isinstance(source_manifest, dict):
        if set(source_manifest) != {"schema", "items"} or source_manifest["schema"] != "monkey-shader-handoff/1" or not isinstance(source_manifest["items"], list):
            fail("BUILD_FILTER_SOURCE_MANIFEST", "sourceManifest", "Expected monkey-shader-handoff/1 with an items array")
        source_manifest = source_manifest["items"]
    if not isinstance(source_manifest, list):
        fail("BUILD_FILTER_SOURCE_MANIFEST", "sourceManifest", "Expected monkey source evidence array")
    evidence = {}
    for i, row in enumerate(source_manifest):
        # The initial closed beaver handoff uses file+meta hashes. The monkey
        # protocol variant is normalized below; in both cases extension names
        # and `nativeCompilation=not_run` never assert successful compilation.
        if isinstance(row, dict) and set(row) == {"path", "classification", "sourceSha256", "metaSha256", "evidenceId"}:
            normalized = dict(path=row["path"], classification=row["classification"],
                              sourceSha256=row["sourceSha256"], metaSha256=row["metaSha256"], evidenceId=row["evidenceId"], bytes=None,
                              requiresTargetIdentity=False)
        elif isinstance(row, dict) and {"path", "bytes", "sha256", "classification", "nativeCompilation", "runtimeDisposition"} <= set(row) and set(row) <= {
                "path", "bytes", "sha256", "classification", "source", "target", "dialect", "platformEvidence",
                "nativeCompilation", "runtimeDisposition", "evidenceId"}:
            classes = {"source-text": "source", "platform-compiled": "binary", "recovered-binary": "binary",
                       "unsupported": "unknown", "unknown": "unknown"}
            if row["classification"] not in classes:
                fail("BUILD_FILTER_SOURCE_CLASS", f"sourceManifest[{i}].classification", "Unknown monkey shader classification")
            if (type(row["bytes"]) is not int or row["bytes"] < 0 or row["nativeCompilation"] != "not_run"
                    or row["runtimeDisposition"] not in ("source-review", "evidence-only", "blocked")):
                fail("BUILD_FILTER_SOURCE_EVIDENCE", f"sourceManifest[{i}]", "Only bounded, not-yet-compiled monkey evidence is accepted")
            normalized = dict(path=row["path"], classification=classes[row["classification"]],
                              sourceSha256=row["sha256"], metaSha256=None,
                              evidenceId=row.get("evidenceId") or "monkey-shader-handoff/1", bytes=row["bytes"],
                              requiresTargetIdentity=True)
            source_info = row.get('source')
            if isinstance(source_info, dict) and source_info.get('metaSha256') is not None:
                if not _HEX.fullmatch(str(source_info['metaSha256'])):
                    fail('BUILD_FILTER_SOURCE_EVIDENCE', row['path'], 'Invalid upstream metadata SHA-256')
                normalized['metaSha256'] = source_info['metaSha256']
            normalized["handoffClassification"] = row["classification"]
            normalized["target"] = row.get("target")
        else:
            fail("BUILD_FILTER_SOURCE_MANIFEST_FIELDS", f"sourceManifest[{i}]", "Unsupported exact monkey handoff item shape")
        row = normalized
        path = _path(row["path"], f"sourceManifest[{i}].path")
        if path in evidence or row["classification"] not in _CLASSES:
            fail("BUILD_FILTER_SOURCE_CLASS", path, "Unique path and source/binary/unknown classification required")
        if (not _HEX.fullmatch(str(row["sourceSha256"])) or (row["metaSha256"] is not None and not _HEX.fullmatch(str(row["metaSha256"])))
                or not isinstance(row["evidenceId"], str) or not row["evidenceId"]):
            fail("BUILD_FILTER_SOURCE_EVIDENCE", path, "Source record needs SHA-256 identity and evidence ID")
        evidence[path] = row

    root = safe(project)
    input_blockers = _verify_input_state(root, snapshot)
    backup_root = _plan_root(backup_root, "backupRoot")
    quarantine_root = _plan_root(quarantine_root, "quarantineRoot")
    rows = []
    dep_paths = {path for path, _ in dependencies} | set(unresolved_dependencies)
    identity_blockers = _native_identity_blockers(snapshot)
    for path, asset in sorted(assets.items()):
        source_path = inside(root, path)
        meta_path = inside(root, path + ".meta")
        if source_path.is_symlink() or meta_path.is_symlink() or not source_path.is_file() or not meta_path.is_file():
            fail("BUILD_FILTER_ASSET_MISSING", path, "Catalog asset and adjacent .meta must be regular files")
        file_hash, meta_hash = _sha(source_path), _sha(meta_path)
        meta_guid = _meta_guid(meta_path)
        native_guid = asset["guid"].lower() if _GUID.fullmatch(asset["guid"]) else None
        can_review_empty_source = asset["identityStatus"] == "no-persistent-object" and asset["objectCount"] == 0
        if native_guid and meta_guid and native_guid != meta_guid:
            fail("BUILD_FILTER_NATIVE_META_GUID_MISMATCH", path, "AssetDatabase native GUID differs from the current .meta GUID")
        report = evidence.get(path)
        mapped_identity = bool(report and not report["requiresTargetIdentity"])
        if report and report.get("target") is not None:
            target_identity = report["target"]
            if isinstance(target_identity, dict) and set(target_identity) == {"guid", "localFileID"}:
                guid_match = isinstance(target_identity["guid"], str) and target_identity["guid"].lower() == asset["guid"].lower()
                id_match = (type(target_identity["localFileID"]) is int and target_identity["localFileID"] != 0
                            and target_identity["localFileID"] in asset["localIds"])
                empty_identity_match = (target_identity["localFileID"] is None
                                        and can_review_empty_source and not asset["localIds"])
                mapped_identity = guid_match and (id_match or empty_identity_match)
        elif can_review_empty_source and report and not report["requiresTargetIdentity"]:
            mapped_identity = native_guid is not None and meta_guid == native_guid
        matched = bool(report and (asset["status"] == "observed" or can_review_empty_source) and report["sourceSha256"] == file_hash
                       and (report["bytes"] is None or report["bytes"] == source_path.stat().st_size)
                       and (report["metaSha256"] is None or report["metaSha256"] == meta_hash) and mapped_identity)
        classification = report["classification"] if matched else "unknown"
        refs = [dict(guid=dep["guid"].lower(), localId=dep["localId"], type=dep["type"], roots=sorted(dep["roots"]))
                for (dep_path, _), dep in sorted(dependencies.items()) if dep_path == path]
        unresolved_refs = [item for item in unresolved_dependencies.values() if item["path"] == path]
        if unresolved_refs:
            state = "runtime-reference-unresolved"
            eligibility = "retain-unknown"
            reason = "Unity reports this path in a dependency closure but could not provide persistent object identity."
        elif path in dep_paths:
            explicit_reference=any(any(not root.startswith('implicit:') for root in ref['roots']) for ref in refs)
            state = "runtime-referenced" if explicit_reference else 'implicit-build-included'
            eligibility = "retain-referenced" if explicit_reference else 'requires-explicit-retirement-scope'
            reason = "Present in the native closure of an explicit scene/root; retain until references are resolved." if explicit_reference else 'Included by a Unity implicit build root; this does not prove current business dynamic use. Retirement needs explicit protected roots and per-key declarations.'
        elif classification in ("source", "binary") and matched:
            state = "source-evidence-only"
            # Static build references are absent, but dynamic/reflection loading
            # cannot be ruled out. The plan remains retained until a native
            # consumer audit supplies proof and a runner with safe .meta moves.
            eligibility = "blocked-unproven-runtime-usage"
            reason = "Has hash-matched monkey provenance and no static build dependency; dynamic use is not proven absent."
        else:
            state = "unknown"
            eligibility = "retain-unknown"
            reason = "No matching source provenance or static evidence is insufficient; preserve the asset."
        if asset["status"] == "observed" and not meta_guid:
            identity_blockers.append(f"Native asset metadata has no valid GUID: {path}")
        backup_identity = native_guid or "unknown-" + hashlib.sha256(path.encode("utf-8")).hexdigest()
        backup_base = f"{backup_root}/{backup_identity}/{path.removeprefix('Assets/')}"
        quarantine_base = f"{quarantine_root}/{path.removeprefix('Assets/')}"
        rows.append({"path": path, "guid": native_guid, "nativeStatus": asset["status"],
                     "identityStatus": asset["identityStatus"], "objectCount": asset["objectCount"],
                     "nativeError": asset["error"] or None,
                     "metaGuid": meta_guid, "localIds": sorted(set(asset["localIds"])),
                     "types": sorted(set(asset["types"])), "sourceSha256": file_hash, "metaSha256": meta_hash,
                     "sourceClassification": classification,
                     "handoffClassification": report.get("handoffClassification") if matched else None,
                     "sourceEvidenceId": report["evidenceId"] if matched else None,
                     "buildState": state, "references": refs, "unresolvedReferences": unresolved_refs,
                     "quarantineEligibility": eligibility, "reason": reason,
                     "backup": {"source": path, "meta": path + ".meta", "copySourceTo": backup_base,
                                "copyMetaTo": backup_base + ".meta",
                                "sourceSha256": file_hash, "metaSha256": meta_hash},
                     "isolation": {"moveSourceTo": quarantine_base, "moveMetaTo": quarantine_base + ".meta",
                                   "preserveGuid": native_guid, "preserveLocalIds": sorted(set(asset["localIds"]))},
                     "rollback": {"restoreSourceFrom": quarantine_base, "restoreMetaFrom": quarantine_base + ".meta",
                                  "restoreSourceTo": path, "restoreMetaTo": path + ".meta",
                                  "expectedPostIsolation": {"sourceAbsent": True, "metaAbsent": True}}})
    result = {"schemaVersion": 1, "target": dict(target), "snapshotIdentity": _snapshot_digest(snapshot),
              "mode": "plan-only", "execution": {"status": "blocked", "code": "BUILD_FILTER_RETIREMENT_SCOPE_REQUIRED",
                           "reason": "Classification alone does not authorize retirement. Use a separately reviewed unity assets.retire plan with protected roots, source roles and explicit Resources retirement declarations; native dependency guards still apply."},
              "assets": rows, "counts": {"runtimeReferenced": sum(r["buildState"] == "runtime-referenced" for r in rows),
                                           "implicitBuildIncluded": sum(r['buildState']=='implicit-build-included' for r in rows),
                                           "sourceEvidenceOnly": sum(r["buildState"] == "source-evidence-only" for r in rows),
                                           "unknown": sum(r["buildState"] in ("unknown", "runtime-reference-unresolved") for r in rows),
                                           "quarantineEligible": sum(r["quarantineEligibility"] == "eligible" for r in rows)}}
    coverage_blockers = sorted(set(snapshot["coverage"]["blockers"] + input_blockers + identity_blockers))
    if not snapshot["coverage"]["complete"] or coverage_blockers:
        result["execution"] = {"status": "blocked", "code": "BUILD_FILTER_DEPENDENCY_COVERAGE_INCOMPLETE",
                                "reason": "Native snapshot reports uncollected implicit build dependencies; no isolation is supportable.",
                                "blockers": coverage_blockers}
    result["planSha256"] = hashlib.sha256(_canonical(result)).hexdigest()
    return result


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _snapshot_digest(snapshot):
    return hashlib.sha256(_canonical(snapshot)).hexdigest()
