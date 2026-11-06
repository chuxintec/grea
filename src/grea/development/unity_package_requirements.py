"""Read-only comparison of Unity package requests and resolved package bytes.

This module deliberately recognizes one narrow Unity builtin override: a
project requesting an older com.unity.ugui version while its package lock,
Editor builtin package source, and complete resolved package cache all agree
on the newer package. All other package differences remain conflicts.
"""
from __future__ import annotations

import hashlib
import json
import plistlib
import re
from pathlib import Path

from .errors import BeaverError, fail
from .io import load, read, safe

_UGUI = "com.unity.ugui"
_PROFILE_VERSION = "6000.6.2f1"
_STABLE_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_MAX_PACKAGE_FILES = 20000
_MAX_FILE_BYTES = 128 * 1024 * 1024


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(path: Path):
    return load(read(path, _MAX_FILE_BYTES))


def _project_inputs(root: Path):
    paths = {
        "manifest": root / "Packages/manifest.json",
        "lock": root / "Packages/packages-lock.json",
        "projectVersion": root / "ProjectSettings/ProjectVersion.txt",
    }
    raw = {key: read(path, _MAX_FILE_BYTES) for key, path in paths.items()}
    return ({key: _sha(value) for key, value in raw.items()},
            load(raw["manifest"]), load(raw["lock"]), raw["projectVersion"].decode("utf-8-sig"))


def _editor_info(editor: Path):
    plist = editor / "Contents/Info.plist"
    raw = read(plist, 8 * 1024 * 1024)
    info = plistlib.loads(raw)
    version = info.get("UnityBuildNumber")
    if not isinstance(version, str) or not version:
        fail("PACKAGE_EDITOR_IDENTITY", str(plist), "UnityBuildNumber revision is missing")
    short = info.get("CFBundleShortVersionString", "")
    match = re.search(r"(\d+\.\d+\.\d+[abfp]\d+)", str(short))
    if not match:
        fail("PACKAGE_EDITOR_IDENTITY", str(plist), "Unity editor version is not recognized")
    return match.group(1), version, _sha(raw)


def _stable_version(value):
    match = _STABLE_VERSION.fullmatch(value) if isinstance(value, str) else None
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _project_editor_identity(root: Path):
    version_file = root / "ProjectSettings/ProjectVersion.txt"
    text = read(version_file).decode("utf-8-sig")
    version = re.search(r"^m_EditorVersion:\s*(\S+)\s*$", text, re.M)
    revision = re.search(r"^m_EditorVersionWithRevision:\s*\S+\s*\(([^)]+)\)\s*$", text, re.M)
    if not version or not revision:
        fail("PACKAGE_PROJECT_EDITOR_IDENTITY", str(version_file), "Version and revision are both required")
    return version.group(1), revision.group(1)


def _tree(root: Path):
    root = safe(root)
    if not root.is_dir():
        fail("PACKAGE_CACHE_MISSING", str(root), "Resolved package directory is absent")
    rows = {}
    total_bytes = 0
    for path in root.rglob("*"):
        # Check every directory/file component before following it.
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            fail("PACKAGE_CACHE_SYMLINK", rel, "Package trees may not contain symlinks")
        resolved = safe(path)
        if not resolved.is_relative_to(root):
            fail("PACKAGE_CACHE_PATH", rel, "Package path escapes its root")
        if path.is_file():
            total_bytes += path.stat().st_size
            if total_bytes>512*1024*1024:
                fail('PACKAGE_CACHE_BUDGET',str(root),'Package tree exceeds512MiB')
            if len(rows) >= _MAX_PACKAGE_FILES:
                fail("PACKAGE_CACHE_BUDGET", str(root), "Package file count exceeds limit")
            rows[rel] = _sha(read(path, _MAX_FILE_BYTES))
    if not rows:
        fail("PACKAGE_CACHE_EMPTY", str(root), "Resolved package tree is empty")
    return dict(sorted(rows.items()))


def _package_entry(lock, name):
    deps = lock.get("dependencies")
    if not isinstance(deps, dict) or not isinstance(deps.get(name), dict):
        fail("PACKAGE_LOCK_MISSING", name, "Resolved package lock entry is missing")
    entry = deps[name]
    if not isinstance(entry.get("version"), str) or not isinstance(entry.get("source"), str):
        fail("PACKAGE_LOCK_INVALID", name, "Resolved package version/source is missing")
    return entry


def _same_resolution(left, right):
    # UPM's depth is graph-position metadata, so a package can resolve to
    # identical bytes/version while being direct in one project and transitive
    # in another. Compare the actual resolution identity and dependency graph.
    return {k: v for k, v in left.items() if k != "depth"} == {
        k: v for k, v in right.items() if k != "depth"}


def _evidence_check(evidence, source, target, source_data, target_data, source_cache, target_cache):
    if not isinstance(evidence, dict) or set(evidence) != {"path", "sha256"}:
        fail("PACKAGE_EVIDENCE_REQUIRED", "evidence", "Pass explicit original evidence path and SHA-256")
    path = safe(Path(evidence["path"]))
    raw = read(path, _MAX_FILE_BYTES)
    if _sha(raw) != evidence["sha256"]:
        fail("PACKAGE_EVIDENCE_DRIFT", str(path), "Original evidence SHA-256 differs")
    report = load(raw)
    rows = report.get("projects") if isinstance(report, dict) else None
    if not isinstance(rows, list) or len(rows) != 2:
        fail("PACKAGE_EVIDENCE_FORMAT", str(path), "Evidence must identify exactly two projects")
    by_path = {row.get("project"): row for row in rows if isinstance(row, dict)}
    if set(by_path) != {str(source), str(target)}:
        fail("PACKAGE_EVIDENCE_PROJECTS", str(path), "Evidence project paths do not match explicit inputs")
    for root, fresh in ((source, source_data), (target, target_data)):
        row = by_path[str(root)]
        hashes = row.get("inputHashes", {})
        expected_hashes = {
            "Packages/manifest.json": fresh[0]["manifest"],
            "Packages/packages-lock.json": fresh[0]["lock"],
            "ProjectSettings/ProjectVersion.txt": fresh[0]["projectVersion"],
        }
        if hashes != expected_hashes:
            fail("PACKAGE_EVIDENCE_INPUT_DRIFT", str(root), "Evidence inputs differ from current project bytes")
        requested = fresh[1].get("dependencies", {}).get(_UGUI)
        resolved = fresh[2].get("dependencies", {}).get(_UGUI)
        if row.get("manifestRequested") != requested or row.get("lockResolved") != resolved:
            fail("PACKAGE_EVIDENCE_RESOLUTION_DRIFT", str(root), "Evidence package resolution differs from current inputs")
        if row.get("packageManifest", {}).get("version") != resolved.get("version"):
            fail("PACKAGE_EVIDENCE_PACKAGE_DRIFT", str(root), "Evidence package metadata differs from locked version")
        actual_cache = source_cache if root == source else target_cache
        cachepath = row.get("cachePath")
        if not isinstance(cachepath, str) or Path(cachepath) != actual_cache[0]:
            fail("PACKAGE_EVIDENCE_CACHE_PATH", str(root), "Evidence cache path differs from freshly resolved package cache")
        if row.get("cacheFileHashes") != actual_cache[2]:
            fail("PACKAGE_EVIDENCE_CACHE_DRIFT", str(root), "Evidence cache file hashes differ")
    if report.get("identicalCacheBytes") is not True or report.get("cacheDifferences") != []:
        fail("PACKAGE_EVIDENCE_CACHE_DIFF", str(path), "Evidence does not state identical package caches")
    if report.get("files") != len(source_cache[2]) or len(source_cache[2]) != len(target_cache[2]):
        fail("PACKAGE_EVIDENCE_CACHE_DRIFT", str(path), "Evidence package cache file count differs")
    return {"path": str(path), "sha256": evidence["sha256"], "bytes": len(raw)}


def _cache_for(root: Path, name: str, fingerprint: str):
    cache_root = root / "Library/PackageCache"
    if not cache_root.is_dir():
        fail("PACKAGE_CACHE_MISSING", str(cache_root), "Unity package cache is absent")
    candidates = []
    for path in cache_root.glob(name + "@*"):
        if path.is_symlink():
            fail("PACKAGE_CACHE_SYMLINK", str(path), "Package cache may not be a symlink")
        if path.is_dir():
            candidates.append(path)
    if len(candidates) != 1:
        fail("PACKAGE_CACHE_AMBIGUOUS", str(cache_root), "Expected exactly one cached package version")
    path = candidates[0]
    suffix = path.name.removeprefix(name + "@")
    if len(suffix) < 12 or not re.fullmatch(r"[0-9a-f]+", suffix):
        fail("PACKAGE_CACHE_FINGERPRINT", str(path), "Cache directory fingerprint does not match package metadata")
    rows = _tree(path)
    package_path = path / "package.json"
    package = _json(package_path)
    return path, package, rows


def _builtin_ugui_proof(source: Path, target: Path, editor: Path, source_data, target_data, evidence_ref):
    source_manifest, source_lock = source_data[1], source_data[2]
    target_manifest, target_lock = target_data[1], target_data[2]
    source_req = source_manifest.get("dependencies", {}).get(_UGUI)
    target_req = target_manifest.get("dependencies", {}).get(_UGUI)
    source_entry = _package_entry(source_lock, _UGUI)
    target_entry = _package_entry(target_lock, _UGUI)
    requested_tuple = _stable_version(target_req)
    resolved_tuple = _stable_version(target_entry["version"])
    if not (source_req == target_entry["version"] and requested_tuple is not None
            and resolved_tuple is not None and requested_tuple < resolved_tuple):
        fail("PACKAGE_BUILTIN_OVERRIDE_SHAPE", _UGUI, "Only a lower target request resolving to source request is supported")
    if not _same_resolution(source_entry, target_entry) or source_entry.get("source") != "builtin":
        fail("PACKAGE_BUILTIN_LOCK_MISMATCH", _UGUI, "Source and target must resolve the same builtin package lock entry")
    version, revision, info_hash = _editor_info(editor)
    for root in (source, target):
        if _project_editor_identity(root) != (version, revision):
            fail("PACKAGE_EDITOR_REVISION", str(root), "Project Editor version/revision differs from supplied Editor")
    builtin_root = editor / "Contents/Resources/PackageManager/BuiltInPackages"
    pm_manifest_path = editor / "Contents/Resources/PackageManager/Editor/manifest.json"
    editor_manifest = _json(pm_manifest_path)
    builtin_path = builtin_root / _UGUI / "package.json"
    builtin_package = _json(builtin_path)
    if builtin_package.get("name") != _UGUI or builtin_package.get("version") != source_entry["version"]:
        fail("PACKAGE_BUILTIN_VERSION", str(builtin_path), "Editor builtin UGUI package identity/version differs")
    pm_info = editor_manifest.get("packages", {}).get(_UGUI)
    if not isinstance(pm_info, dict) or pm_info.get("version") != source_entry["version"]:
        fail("PACKAGE_EDITOR_BUILTIN_INDEX", str(pm_manifest_path), "Editor package index does not declare the builtin UGUI version")
    dependencies = builtin_package.get("dependencies", {})
    if not isinstance(dependencies, dict) or dependencies != source_entry.get("dependencies", {}):
        fail("PACKAGE_BUILTIN_DEPENDENCIES", str(builtin_path), "Builtin package dependencies differ from lock")
    builtin_closure, pending = set(), list(dependencies.items())
    while pending:
        name, requested = pending.pop()
        if name in builtin_closure:
            continue
        builtin_closure.add(name)
        source_dep = _package_entry(source_lock, name)
        target_dep = _package_entry(target_lock, name)
        if (not _same_resolution(source_dep, target_dep) or source_dep.get("source") != "builtin"
                or source_dep.get("version") != requested):
            fail("PACKAGE_BUILTIN_DEPENDENCY_LOCK", name, "Builtin dependency lock is missing or differs")
        dep_path = builtin_root / name / "package.json"
        dep_package = _json(dep_path)
        if dep_package.get("name") != name or dep_package.get("version") != requested:
            fail("PACKAGE_BUILTIN_DEPENDENCY_SOURCE", str(dep_path), "Editor builtin dependency source differs")
        dep_dependencies = dep_package.get("dependencies", {})
        if not isinstance(dep_dependencies, dict) or dep_dependencies != source_dep.get("dependencies", {}):
            fail("PACKAGE_BUILTIN_DEPENDENCY_GRAPH", name, "Editor dependency closure differs from package lock")
        pending.extend(dep_dependencies.items())
    fingerprint = ""
    source_cache, source_cached_package, source_files = _cache_for(source, _UGUI, "")
    target_cache, target_cached_package, target_files = _cache_for(target, _UGUI, "")
    for cache, cached in ((source_cache, source_cached_package), (target_cache, target_cached_package)):
        fp = cached.get("_fingerprint")
        if not isinstance(fp, str) or not re.fullmatch(r"[0-9a-f]{40}", fp) or not cache.name.endswith(fp[:12]):
            fail("PACKAGE_CACHE_FINGERPRINT", str(cache), "Cached UGUI package fingerprint is missing or mismatched")
        fingerprint = fp
    if source_files != target_files:
        fail("PACKAGE_CACHE_DIFFERENT", _UGUI, "Source and target package cache trees differ")
    editor_files = _tree(builtin_root / _UGUI)
    source_compare = dict(source_files)
    editor_compare = dict(editor_files)
    # Package Manager injects the fingerprint into the cached package.json.
    cached_normalized = _json(source_cache / "package.json")
    cached_normalized.pop("_fingerprint", None)
    if cached_normalized != builtin_package:
        fail("PACKAGE_CACHE_METADATA", str(source_cache), "Cached package.json differs beyond injected fingerprint")
    source_compare.pop("package.json", None)
    editor_compare.pop("package.json", None)
    if source_compare != editor_compare:
        fail("PACKAGE_BUILTIN_BYTES", str(builtin_root / _UGUI), "Cached package bytes differ from Editor builtin source")
    source_package_hash = _sha(read(source_cache / "package.json", _MAX_FILE_BYTES))
    evidence_ref = _evidence_check(evidence_ref, source, target, source_data, target_data,
                                   (source_cache, source_cached_package, source_files),
                                   (target_cache, target_cached_package, target_files))
    return {
        "package": _UGUI, "requestedOverride": {"target": target_req, "resolved": source_entry["version"]},
        "sourceRequested": source_req, "resolved": source_entry["version"], "source": "builtin",
        "dependencies": dict(sorted(dependencies.items())),
        "sourceCache": {"path": str(source_cache), "files": len(source_files), "fileHashes": source_files},
        "targetCache": {"path": str(target_cache), "files": len(target_files), "fileHashes": target_files},
        "editorBuiltin": {"path": str(builtin_root / _UGUI), "version": version,
                          "revision": revision, "infoPlistSha256": info_hash,
                          "packageJsonSha256": _sha(read(builtin_path, _MAX_FILE_BYTES)),
                          "packageManagerManifestSha256": _sha(read(pm_manifest_path, _MAX_FILE_BYTES)),
                          "fingerprint": fingerprint},
        "evidence": evidence_ref,
        "resolvedPackages": {
            _UGUI: {"requestedSource": source_req, "requestedTarget": target_req,
                    "resolvedVersion": source_entry["version"], "source": "builtin",
                    "sourceRoot": str(source_cache), "targetRoot": str(target_cache),
                    "editorRoot": str(builtin_root / _UGUI),
                    "packageJsonSha256": source_package_hash,
                    "sourceTreeSha256": _sha(json.dumps(source_files, sort_keys=True, separators=(",", ":")).encode()),
                    "targetTreeSha256": _sha(json.dumps(target_files, sort_keys=True, separators=(",", ":")).encode()),
                    "editorPackageJsonSha256": _sha(read(builtin_path, _MAX_FILE_BYTES)),
                    "editorVersion": version, "editorRevision": revision,
                    "dependencies": dict(sorted(dependencies.items()))}
        },
    }


def resolve_requirements(incoming: Path, target: Path, profile: str, *,
                         source_project: Path | None = None, editor_path: Path | None = None,
                         evidence: dict | None = None) -> tuple[dict, list[dict]]:
    """Compare package requirements without installing or modifying anything.

    ``evidence`` must be ``{"path": ..., "sha256": ...}`` and is mandatory
    only for the UGUI builtin override. Paths are explicit; no sibling project
    discovery is performed.
    """
    conflicts: list[dict] = []
    try:
        source = safe(source_project if source_project is not None else incoming)
        incoming_root = safe(incoming)
        destination = safe(target)
        if profile not in (_PROFILE_VERSION, "unity-6000.6.2f1-ugui"):
            fail("PACKAGE_PROFILE", "profile", f"Unity package profile must be {_PROFILE_VERSION}")
        incoming_hashes, _, _, _ = _project_inputs(incoming_root)
        source_hashes, source_manifest, source_lock, source_version_text = _project_inputs(source)
        target_hashes, target_manifest, target_lock, target_version_text = _project_inputs(destination)
        if incoming_hashes != source_hashes:
            fail("PACKAGE_INCOMING_SOURCE_DRIFT", str(incoming_root),
                 "Incoming candidate package inputs differ from the explicitly pinned source project")
        editor_root = safe(editor_path) if editor_path is not None else None
        if editor_root is None:
            fail("PACKAGE_EDITOR_REQUIRED", "editor_path", "Explicit Unity Editor is required for the selected profile")
        editor_version, editor_revision, editor_info_hash = _editor_info(editor_root)
        if editor_version != _PROFILE_VERSION:
            fail("PACKAGE_EDITOR_PROFILE", str(editor_root), "Unity Editor version differs from package profile")
        source_editor_identity = _project_editor_identity(source)
        target_editor_identity = _project_editor_identity(destination)
        if (source_editor_identity[0] != _PROFILE_VERSION or target_editor_identity[0] != _PROFILE_VERSION
                or source_editor_identity[0] != target_editor_identity[0]
                or source_editor_identity[1] != target_editor_identity[1]
                or source_editor_identity != (editor_version, editor_revision)
                or target_editor_identity != (editor_version, editor_revision)):
            fail("PACKAGE_EDITOR_REVISION", "ProjectSettings/ProjectVersion.txt",
                 "Incoming and target projects must match the profile Editor version and revision")
        src_requested = source_manifest.get("dependencies", {})
        dst_requested = target_manifest.get("dependencies", {})
        src_locked = source_lock.get("dependencies", {})
        dst_locked = target_lock.get("dependencies", {})
        if not all(isinstance(value, dict) for value in (src_requested, dst_requested, src_locked, dst_locked)):
            fail("PACKAGE_MANIFEST_FORMAT", "Packages", "Manifest dependencies and lock dependencies must be objects")
        differences = []
        source_only = sorted(set(src_requested) - set(dst_requested))
        if source_only:
            differences.append({"kind": "incomingPackageMissingFromTarget", "packages": source_only})
        target_only = sorted(set(dst_requested) - set(src_requested))
        override = (src_requested.get(_UGUI) != dst_requested.get(_UGUI)
                    and _UGUI in src_requested and _UGUI in dst_requested)
        exceptional = None
        if override:
            if source_project is None:
                fail("PACKAGE_SOURCE_PROJECT_REQUIRED", "source_project", "Builtin override requires an explicit incoming Unity project root")
            exceptional = _builtin_ugui_proof(source, destination, safe(editor_path),
                                               (source_hashes, source_manifest, source_lock, source_version_text),
                                               (target_hashes, target_manifest, target_lock, target_version_text), evidence)
        for name in sorted(src_requested):
            if name not in dst_requested:
                continue
            if name == _UGUI and exceptional:
                continue
            if src_requested[name] != dst_requested[name]:
                differences.append({"kind": "requestedVersion", "package": name,
                                    "source": src_requested[name], "target": dst_requested[name]})
            left = _package_entry(source_lock, name)
            right = _package_entry(target_lock, name)
            if not _same_resolution(left, right):
                differences.append({"kind": "resolvedPackage", "package": name, "source": left, "target": right})
            if left.get("version") != src_requested[name] or right.get("version") != dst_requested[name]:
                differences.append({"kind": "requestResolution", "package": name,
                                    "sourceRequested": src_requested[name], "sourceResolved": left.get("version"),
                                    "targetRequested": dst_requested[name], "targetResolved": right.get("version")})
        # Validate the complete resolved closure actually required by the
        # incoming project. Additional retained target packages are recorded
        # but do not change the incoming package contract.
        closure, pending = set(), list(src_requested)
        while pending:
            name = pending.pop()
            if name in closure:
                continue
            closure.add(name)
            source_entry = _package_entry(source_lock, name)
            target_entry = _package_entry(target_lock, name)
            if not (name == _UGUI and exceptional) and not _same_resolution(source_entry, target_entry):
                differences.append({"kind": "transitiveResolution", "package": name,
                                    "source": source_entry, "target": target_entry})
            dependencies = source_entry.get("dependencies", {})
            if not isinstance(dependencies, dict):
                fail("PACKAGE_LOCK_INVALID", name, "Resolved dependencies must be an object")
            pending.extend(dependencies)
        if differences:
            conflicts.extend({"code": "PACKAGE_REQUIREMENT_MISMATCH", **item} for item in differences)
        document = {
            "contract": "beaver-unity-package-requirements/1", "profile": profile,
            "incomingProject": str(incoming_root), "sourceProject": str(source), "targetProject": str(destination),
            "inputPins": {"incoming": incoming_hashes, "source": source_hashes, "target": target_hashes},
            "requested": {"source": dict(sorted(src_requested.items())), "target": dict(sorted(dst_requested.items()))},
            "resolved": {"source": dict(sorted(src_locked.items())), "target": dict(sorted(dst_locked.items()))},
            "resolvedPackages": {
                name: {"requestedSource": src_requested.get(name), "requestedTarget": dst_requested.get(name),
                       "resolvedVersion": _package_entry(source_lock, name)["version"],
                       "source": _package_entry(source_lock, name)["source"],
                       "sourceRoot": None, "targetRoot": None, "editorRoot": None,
                       "packageJsonSha256": None}
                for name in sorted(set(src_requested) & set(dst_requested))
            },
            "editor": {"version": editor_version, "revision": editor_revision,
                       "infoPlistSha256": editor_info_hash,
                       "sourceProjectVersion": list(source_editor_identity),
                       "targetProjectVersion": list(target_editor_identity)},
            "builtinOverrides": [exceptional] if exceptional else [],
            "targetOnlyRequestedPackages": target_only,
            "status": "verified" if not conflicts else "blocked",
        }
        if exceptional:
            document["resolvedPackages"].update(exceptional["resolvedPackages"])
        return document, conflicts
    except BeaverError as exc:
        return {"contract": "beaver-unity-package-requirements/1", "profile": profile,
                "status": "blocked"}, [exc.as_dict()]
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return {"contract": "beaver-unity-package-requirements/1", "profile": profile,
                "status": "blocked"}, [dict(code="PACKAGE_PROOF_UNREADABLE", location="explicit package/Editor evidence",
                message=str(exc)[:1000],status="blocked",retry="new_plan_after_resolving_precondition")]
