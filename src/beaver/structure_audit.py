"""Read-only Unity project structure audit and explicit native move-plan builder.

This module never performs asset moves.  Plans are data for the existing
``asset.move`` batch transaction, and require a consumer supplied native
AssetDatabase snapshot before they can be considered ready.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import re
import tempfile

from .errors import fail
from .io import safe
from .references import inspect_graph
from .output_limits import WHOLE_FILES

SCHEMA = "beaver-structure-audit/1"
PLAN_SCHEMA = "beaver-structure-move-plan/1"
CANONICAL_ROOTS = {"Assets", "Packages", "ProjectSettings"}
RETIRED_ROOTS = {"Product", "SourceRecovery", "_Recovery"}
CONTENT_KINDS = {
    "Config", "Prefabs", "Materials", "Shaders", "Images", "Sprites", "Levels", "Models",
    "Animations", "Spine", "Fonts", "Audio",
}
STANDARD_GAME_DIRS = {"Bootstrap", "Domain", "Gameplay", "Presentation", "Services", "Diagnostics",
                      "Content", "Scenes", "Editor", "Tests", "Scripts", "Packages", "ThirdParty", "Plugins"}
PATH_LITERAL_RE = re.compile(r"[\"']((?:Assets|assets)/[^\"']+)[\"']")
MAX_AUDIT_FILES = WHOLE_FILES
MAX_HASH_FILE_BYTES = 64 * 1024 * 1024
MAX_HASH_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
REFERENCE_SOURCE_SUFFIXES = {".cs", ".asmdef", ".asmref", ".rsp", ".asset", ".unity", ".prefab", ".json",
                            ".mat", ".controller", ".overridecontroller", ".anim", ".mask", ".rendertexture", ".meta"}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _rel(project: Path, path: Path) -> str:
    return path.relative_to(project).as_posix()


def _valid_rel(value: str, field: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        fail("STRUCTURE_PATH", field, "Expected a project-relative POSIX path")
    parts = value.split("/")
    if any(p in ("", ".", "..") for p in parts):
        fail("STRUCTURE_PATH", field, "Path must be canonical and remain inside the project")
    return value


def _exception_map(config):
    if config is None:
        return {}
    if not isinstance(config, dict) or set(config) != {"schemaVersion", "exceptions"} or config["schemaVersion"] != 1 or not isinstance(config["exceptions"], list):
        fail("STRUCTURE_EXCEPTIONS", "exceptions", "Expected schemaVersion 1 and an explicit exceptions list")
    result = {}
    required = {"path", "ruleId", "scope", "reason", "alternativeConstraint", "validation", "owner", "reviewTrigger"}
    for i, item in enumerate(config["exceptions"]):
        loc = "exceptions[" + str(i) + "]"
        if not isinstance(item, dict) or set(item) != required:
            fail("STRUCTURE_EXCEPTIONS", loc, "Each exception requires path, ruleId, scope, reason, alternativeConstraint, validation, owner, reviewTrigger")
        path = _valid_rel(item["path"], loc + ".path")
        if (any(not isinstance(item[k], str) or not item[k].strip() for k in required - {"path"})
                or item["scope"] not in {"path", "subtree"}):
            fail("STRUCTURE_EXCEPTIONS", loc, "Exception path+scope+ruleId must be unique and every rationale field must be non-empty")
        key = (path, item["scope"], item["ruleId"])
        if key in result:
            fail("STRUCTURE_EXCEPTIONS", loc, "Exception path+scope+ruleId must be unique and every rationale field must be non-empty")
        result[key] = dict(item)
    return result


def _exception_for(exceptions, path, rule_id):
    if (path, "path", rule_id) in exceptions:
        return exceptions[(path, "path", rule_id)]
    for (base, scope, rule), item in exceptions.items():
        if scope == "subtree" and rule == rule_id and path.startswith(base.rstrip("/") + "/"):
            return item
    return None


def _category_rule(category):
    if category == "retired-root":
        return "STR-01"
    if category in {"editor-tooling-location", "test-location"}:
        return "STR-02"
    if category in {"legacy-assets-root", "content-kind-missing", "content-kind-unknown"}:
        return "STR-05"
    return None


def _case_collisions(paths):
    buckets = defaultdict(list)
    for value in paths:
        buckets[value.casefold()].append(value)
    return [sorted(values) for values in buckets.values() if len(values) > 1]


def _classify(path):
    parts = PurePosixPath(path).parts
    if not parts:
        return "unknown"
    if parts[0] != "Assets":
        return "non-assets-root"
    if len(parts) > 1 and parts[1] in RETIRED_ROOTS:
        return "retired-root"
    if len(parts) > 1 and parts[1] in {"GreaGenerated", "ThirdParty", "Plugins"}:
        return "standard-or-nested"
    if len(parts) > 1 and parts[1] != "Game":
        return "legacy-assets-root"
    if len(parts) > 2 and parts[2] == "Content":
        if len(parts) < 4:
            return "content-kind-missing"
        if parts[3] not in CONTENT_KINDS:
            return "content-kind-unknown"
    if len(parts) > 2 and parts[2] == "Editor" and (len(parts) < 4 or parts[3] not in {"Generators", "Validators", "Build"}):
        return "editor-tooling-location"
    if len(parts) > 2 and parts[2] == "Tests" and (len(parts) < 4 or parts[3] not in {"EditMode", "PlayMode"}):
        return "test-location"
    return "standard-or-nested"


def _standard_target(path):
    parts = PurePosixPath(path).parts
    if len(parts) >= 3 and parts[0] == "Assets" and parts[1] in {"GreaGenerated", "ThirdParty", "Plugins"}:
        return True
    if len(parts) < 3 or parts[:2] != ("Assets", "Game") or parts[2] not in STANDARD_GAME_DIRS:
        return False
    if parts[2] == "Content":
        return len(parts) >= 5 and parts[3] in CONTENT_KINDS
    if parts[2] == "Editor":
        return len(parts) >= 5 and parts[3] in {"Generators", "Validators", "Build"}
    if parts[2] == "Tests":
        return len(parts) >= 5 and parts[3] in {"EditMode", "PlayMode"}
    if parts[2] == "Scenes":
        return len(parts) >= 4 and parts[-1].endswith(".unity")
    if parts[2] == "Scripts":
        return len(parts) >= 5
    return True


def _expected_content_kinds(imported_type):
    """Return only type-to-directory rules supported by native import identity."""
    direct = {
        "UnityEngine.Material": {"Materials"},
        "UnityEngine.Texture2D": {"Images"},
        "UnityEngine.Sprite": {"Sprites"},
        "UnityEngine.AudioClip": {"Audio"},
        "UnityEngine.Font": {"Fonts"},
        "TMPro.TMP_FontAsset": {"Fonts"},
        "UnityEngine.AnimationClip": {"Animations"},
        "UnityEditor.Animations.AnimatorController": {"Animations"},
        "UnityEngine.Avatar": {"Animations"},
        "UnityEngine.Mesh": {"Models"},
        "UnityEngine.GameObject": {"Prefabs"},
    }
    return direct.get(imported_type)


def _type_path_mismatch(path, imported_type):
    expected = _expected_content_kinds(imported_type)
    if not expected:
        return False, None
    parts = PurePosixPath(path).parts
    if len(parts) < 3 or parts[:2] != ("Assets", "Game"):
        return False, None
    if len(parts) >= 4 and parts[2] == "Content" and parts[3] in expected:
        return False, sorted(expected)
    return True, sorted(expected)


def inspect(project, native_snapshot=None, exceptions=None):
    """Inspect project paths and static references without writing to the project.

    ``native_snapshot`` is an optional JSON object captured by Unity.  It maps
    asset paths to imported type and object identities.  Without it, findings
    remain static and no plan can claim native type/subasset completeness.
    """
    root = safe(project)
    if not root.is_dir():
        fail("PROJECT_PATH", str(root), "Project must be an existing directory")
    approved_exceptions = _exception_map(exceptions)
    native = _validate_native_snapshot(native_snapshot) if native_snapshot is not None else None
    top_entries = list(root.iterdir())
    top = [p.name for p in top_entries if p.is_dir() and not p.is_symlink()]
    roots = [n for n in top if n.casefold() in {x.casefold() for x in CANONICAL_ROOTS}]
    root_collisions = _case_collisions(roots)
    assets_roots = [root / n for n in top if n.casefold() == "assets"]
    paths, external_sources = [], []
    symlinks = [_rel(root, p) for p in top_entries if p.is_symlink() and p.name.casefold() in {x.casefold() for x in CANONICAL_ROOTS}]
    scan_roots = [root / n for n in top if n.casefold() in {x.casefold() for x in CANONICAL_ROOTS}]
    scanned_entries = 0
    scan_truncated = False
    for scan_root in scan_roots:
        for base, dirs, files in os.walk(scan_root, followlinks=False):
            base_path = Path(base)
            for name in list(dirs):
                candidate = base_path / name
                if candidate.is_symlink():
                    symlinks.append(_rel(root, candidate)); dirs.remove(name)
                scanned_entries += 1
                if scanned_entries > MAX_AUDIT_FILES:
                    scan_truncated = True
                    break
            if scan_truncated:
                break
            for name in files:
                candidate = base_path / name
                if candidate.is_symlink():
                    symlinks.append(_rel(root, candidate))
                else:
                    scanned_entries += 1
                    if scanned_entries > MAX_AUDIT_FILES:
                        scan_truncated = True
                        break
                    if candidate.is_file() and scan_root.name.casefold() == "assets" and not name.endswith(".meta"):
                        paths.append(_rel(root, candidate))
                    elif candidate.is_file() and scan_root.name.casefold() != "assets" and candidate.suffix.lower() in REFERENCE_SOURCE_SUFFIXES:
                        external_sources.append(_rel(root, candidate))
            if scan_truncated:
                break
        if scan_truncated:
            break
    issues = []
    for collision in root_collisions:
        issues.append({"code": "ROOT_CASE_COLLISION", "paths": collision, "severity": "error"})
    for name in roots:
        if name not in CANONICAL_ROOTS:
            issues.append({"code": "ROOT_CASE_MISMATCH", "path": name, "expected": next(x for x in CANONICAL_ROOTS if x.casefold() == name.casefold()), "severity": "error"})
    for path in symlinks:
        issues.append({"code": "SYMLINK_SCAN_BLOCKED", "path": path, "severity": "error"})
    if scan_truncated:
        issues.append({"code": "STRUCTURE_SCAN_BUDGET_EXCEEDED", "scannedEntries": scanned_entries,
                       "maxEntries": MAX_AUDIT_FILES, "severity": "error"})
    expected_missing = sorted(CANONICAL_ROOTS - set(roots))
    for name in expected_missing:
        issues.append({"code": "STANDARD_ROOT_MISSING", "path": name, "severity": "info"})
    all_asset_paths = [p for p in paths if p.split("/", 1)[0].casefold() == "assets"]
    for required, issue_code in (("grea-project.json", "PROJECT_CONFIG_MISSING"),
                                 ("Docs/PROJECT-STRUCTURE.md", "STRUCTURE_DOCUMENTATION_MISSING")):
        if not (root / required).is_file():
            issues.append({"code": issue_code, "path": required, "severity": "info"})
    for collision in _case_collisions(all_asset_paths):
        issues.append({"code": "PATH_CASE_COLLISION", "paths": collision, "severity": "error"})
    inventory = []
    source_hashes = {}
    hashed_bytes = 0
    for rel in sorted(paths):
        path = root / rel
        category = _classify(rel)
        category_rule = _category_rule(category)
        exception = _exception_for(approved_exceptions, rel, category_rule) if category_rule else None
        size = path.stat().st_size
        digest = None
        if size <= MAX_HASH_FILE_BYTES and hashed_bytes + size <= MAX_HASH_TOTAL_BYTES:
            digest = _sha(path); hashed_bytes += size
        else:
            issues.append({"code": "SOURCE_HASH_BUDGET_EXCEEDED", "path": rel, "bytes": size, "severity": "warning"})
        row = {"path": rel, "category": category, "bytes": size,
               "sha256": digest, "exception": exception,
               "importedType": native["byPath"].get(rel, {}).get("importedType") if native else None,
               "objects": native["byPath"].get(rel, {}).get("objects") if native else None,
               "nativeStatus": "observed" if native and rel in native["byPath"] else "not_in_snapshot"}
        inventory.append(row)
        if digest:
            source_hashes[rel] = digest
        if category in {"retired-root", "legacy-assets-root", "content-kind-missing", "content-kind-unknown", "editor-tooling-location", "test-location"}:
            issue_code = "LEGACY_TEXTURES_PATH" if category == "content-kind-unknown" and PurePosixPath(rel).parts[3:4] == ("Textures",) else category.upper().replace("-", "_")
            issue = {"code": issue_code, "ruleId": category_rule, "path": rel,
                     "severity": "exception" if exception else "warning"}
            if exception:
                issue["exceptionRuleId"] = exception["ruleId"]
            issues.append(issue)

        imported_type = row["importedType"]
        mismatch, expected_kinds = _type_path_mismatch(rel, imported_type) if imported_type else (False, None)
        if mismatch:
            parts = PurePosixPath(rel).parts
            type_exception = _exception_for(approved_exceptions, rel, "STR-05")
            row["typeException"] = type_exception
            type_issue = {"code": "TYPE_DIRECTORY_MISMATCH", "ruleId": "STR-05", "path": rel, "importedType": imported_type,
                           "contentKind": parts[3] if len(parts) > 3 else None,
                           "expectedKinds": expected_kinds, "severity": "exception" if type_exception else "warning"}
            if type_exception:
                type_issue["exceptionRuleId"] = type_exception["ruleId"]
            issues.append(type_issue)

    for rel in sorted(external_sources):
        path = root / rel
        size = path.stat().st_size
        if size > MAX_HASH_FILE_BYTES or hashed_bytes + size > MAX_HASH_TOTAL_BYTES:
            issues.append({"code": "SOURCE_HASH_BUDGET_EXCEEDED", "path": rel, "bytes": size, "severity": "warning"})
            continue
        source_hashes[rel] = _sha(path)
        hashed_bytes += size

    # Existing static graph scanner is authoritative for supported GUID and
    # exact literal-load evidence.  Its scratch report is outside the project.
    if symlinks or scan_truncated:
        graph = {"unknownDynamicLoads": [], "literalLoads": [], "unresolvedJsonStrings": [],
                 "guidToPath": {}, "dependencies": {}, "reverseDependencies": {}, "duplicateGuids": {}}
    else:
        with tempfile.TemporaryDirectory(prefix="beaver-structure-") as scratch:
            graph = inspect_graph(root, Path(scratch).resolve() / "graph.json")
    for row in graph["unknownDynamicLoads"]:
        issues.append({"code": "DYNAMIC_LOAD_UNRESOLVED", "severity": "warning", **row})
    for row in graph["literalLoads"]:
        candidates = sorted(p for p in all_asset_paths if "/Resources/" in p and
                            p.split("/Resources/", 1)[1].rsplit(".", 1)[0] == row["key"])
        row["candidateAssets"] = candidates
        row["importedTypes"] = [native["byPath"][p]["importedType"] for p in candidates
                                if native and p in native["byPath"]]
        if not candidates:
            issues.append({"code": "RESOURCE_KEY_MISSING", "severity": "warning", **row})
        elif len(candidates) > 1:
            issues.append({"code": "RESOURCE_KEY_AMBIGUOUS", "severity": "error", **row})
            if row["importedTypes"] and len(set(row["importedTypes"])) > 1:
                issues.append({"code": "RESOURCE_TYPE_AMBIGUOUS", "severity": "error", **row})
        elif not native or candidates[0] not in native["byPath"]:
            issues.append({"code": "RESOURCE_TYPE_UNOBSERVED", "severity": "warning", **row})
        else:
            issues.append({"code": "RESOURCE_KEY", "severity": "info", **row})
    for row in graph["unresolvedJsonStrings"]:
        value = row.get("value", "")
        if isinstance(value, str) and ("Assets/" in value or "Resources/" in value):
            issues.append({"code": "JSON_ASSET_PATH_UNRESOLVED", "severity": "warning", **row})

    # Inventory static source strings that point at paths under retired roots;
    # these are consumers to review, not proof that all dynamic uses were found.
    path_consumers = []
    for rel in sorted(p for p in paths + external_sources if p.endswith(".cs")):
        try:
            if (root / rel).stat().st_size > MAX_HASH_FILE_BYTES:
                continue
            text = (root / rel).read_text(encoding="utf-8-sig")
        except (UnicodeError, OSError):
            continue
        for match in PATH_LITERAL_RE.finditer(text):
            value = match.group(1)
            if any(value.startswith("Assets/" + old + "/") or value == "Assets/" + old for old in RETIRED_ROOTS):
                path_consumers.append({"file": rel, "value": value, "offset": match.start(1)})
                issues.append({"code": "OLD_PATH_CONSUMER", "severity": "warning", "file": rel, "value": value})

    scene_paths = sorted(p for p in paths if p.endswith(".unity"))
    for scene in scene_paths:
        issues.append({"code": "SCENE_INVENTORY", "path": scene, "severity": "info"})
    build_settings = root / "ProjectSettings/EditorBuildSettings.asset"
    build_entries = []
    if scan_truncated:
        issues.append({"code": "BUILD_SETTINGS_SCAN_INCOMPLETE", "path": "ProjectSettings/EditorBuildSettings.asset", "severity": "warning"})
    elif not build_settings.is_file():
        issues.append({"code": "BUILD_SETTINGS_MISSING", "path": "ProjectSettings/EditorBuildSettings.asset", "severity": "warning"})
    else:
        for scene in graph.get("dependencies", {}).get("ProjectSettings/EditorBuildSettings.asset", []):
            if scene.endswith(".unity"):
                build_entries.append(scene)
                issues.append({"code": "BUILD_SCENE_ENTRY", "ruleId": "STR-05", "path": scene, "severity": "info"})
                if not scene.startswith("Assets/Game/Scenes/"):
                    exception = _exception_for(approved_exceptions, scene, "STR-05")
                    issue = {"code": "BUILD_SCENE_NONSTANDARD_PATH", "ruleId": "STR-05", "path": scene,
                             "expectedRoot": "Assets/Game/Scenes", "severity": "exception" if exception else "warning"}
                    if exception:
                        issue["exceptionRuleId"] = exception["ruleId"]
                    issues.append(issue)
        if not build_entries:
            issues.append({"code": "BUILD_SCENES_EMPTY_OR_UNRESOLVED", "path": "ProjectSettings/EditorBuildSettings.asset", "severity": "warning"})

    return {"schema": SCHEMA, "projectRoot": str(root), "roots": sorted(roots),
            "scanStatus": "partial_budget" if scan_truncated else "blocked_symlink" if symlinks else "complete",
            "rootCaseCollisions": root_collisions, "inventory": inventory,
            "sourceHashes": source_hashes, "issues": issues,
            "resourceLoads": graph["literalLoads"], "dynamicLoads": graph["unknownDynamicLoads"],
            "pathConsumers": path_consumers, "guidToPath": graph["guidToPath"],
            "dependencies": graph["dependencies"], "reverseDependencies": graph["reverseDependencies"],
            "scenePaths": scene_paths, "buildSceneEntries": build_entries,
            "duplicateGuids": graph["duplicateGuids"],
            "nativeSnapshot": native["document"] if native else None,
            "exceptions": list(approved_exceptions.values()),
            "limitations": ["Traversal uses the shared bounded whole-input policy (500,000 entries); a partial-budget result blocks migration audit completion.",
                            "Static scan does not prove reflection, generated paths, package code, or runtime address resolution.",
                            "Imported type, GUID, and localFileID claims are available only from the supplied native snapshot; unknown types are not inferred from filenames."]}


def _validate_native_snapshot(snapshot):
    required = {"schemaVersion", "contract", "status", "editorVersion", "assets", "fields", "capture", "errors",
                "editorExitCode", "sourceUnchanged", "unplannedProjectChanges", "helperCleaned", "inputState",
                "nativeReadback", "visualAcceptance", "gameplayAcceptance"}
    if not isinstance(snapshot, dict) or not required.issubset(snapshot) or snapshot.get("schemaVersion") != 1 or snapshot.get("contract") != "beaver-native-readback/1" or not isinstance(snapshot.get("assets"), list):
        fail("STRUCTURE_NATIVE_SNAPSHOT", "nativeSnapshot", "Expected a complete beaver-native-readback/1 report")
    if (type(snapshot["editorExitCode"]) is not int or snapshot["editorExitCode"] != 0
            or snapshot["sourceUnchanged"] is not True or snapshot["nativeReadback"] != "read_only_native_snapshot"
            or snapshot["helperCleaned"] is not True or snapshot["unplannedProjectChanges"] != []
            or snapshot["errors"] not in ([], None) or snapshot["status"] == "failed"):
        fail("STRUCTURE_NATIVE_SNAPSHOT_UNVERIFIED", "nativeSnapshot", "Editor completion and read-only source guard are not verified")
    if not isinstance(snapshot["inputState"], dict):
        fail("STRUCTURE_NATIVE_SNAPSHOT", "nativeSnapshot.inputState", "Expected input content preconditions")
    out = {}
    for i, row in enumerate(snapshot["assets"]):
        loc = "nativeSnapshot.assets[" + str(i) + "]"
        if not isinstance(row, dict) or not {"path", "importedType", "objects"}.issubset(row):
            fail("STRUCTURE_NATIVE_SNAPSHOT", loc, "Asset rows require path, importedType, objects")
        path = _valid_rel(row["path"], loc + ".path")
        if not isinstance(row["importedType"], str) or not row["importedType"] or not isinstance(row["objects"], list) or path in out:
            fail("STRUCTURE_NATIVE_SNAPSHOT", loc, "Invalid or duplicate native asset row")
        objects = []
        for j, obj in enumerate(row["objects"]):
            fields = {"path", "guid", "type", "name", "state", "localId"}
            if not isinstance(obj, dict) or not fields.issubset(obj) or type(obj["localId"]) is not int or not all(isinstance(obj[k], str) for k in ("path", "type", "name", "state")):
                fail("STRUCTURE_NATIVE_SNAPSHOT", loc + ".objects[" + str(j) + "]", "Native object rows require path, guid, type, name, state, localId")
            if obj["path"] != path:
                fail("STRUCTURE_NATIVE_SNAPSHOT", loc + ".objects[" + str(j) + "]", "Object path must match its imported asset path")
            if obj["state"] == "persistent" and (not isinstance(obj["guid"], str) or not re.fullmatch(r"[0-9a-fA-F]{32}", obj["guid"])):
                fail("STRUCTURE_NATIVE_SNAPSHOT", loc + ".objects[" + str(j) + "]", "Persistent object requires a valid GUID")
            objects.append(dict(obj))
        if len({o["localId"] for o in objects}) != len(objects):
            fail("STRUCTURE_NATIVE_SNAPSHOT", loc, "localFileId values must be unique within each imported asset")
        guids = {o["guid"].lower() for o in objects if o["state"] == "persistent"}
        out[path] = {"guid": next(iter(guids)) if len(guids) == 1 else None,
                     "importedType": row["importedType"], "objects": objects,
                     "identityConsistent": len(guids) == 1 and bool(objects) and all(o["state"] == "persistent" for o in objects)}
    return {"document": dict(snapshot), "byPath": out}


def build_plan(audit, mappings, native_snapshot=None):
    """Build immutable move declarations for existing ``asset.move`` steps.

    ``mappings`` is an explicit list of {source,target}.  No file is moved and
    no consumer key is silently rewritten.  The returned batch spec is ready
    for the existing batch planner after the caller adds any consumer edits.
    """
    if not isinstance(audit, dict) or audit.get("schema") != SCHEMA:
        fail("STRUCTURE_AUDIT", "audit", "Expected beaver-structure-audit/1 result")
    if not isinstance(mappings, list) or not 1 <= len(mappings) <= 256:
        fail("STRUCTURE_MAPPING", "mappings", "Expected 1..256 explicit mapping rows, matching batch limits")
    native_doc = native_snapshot if native_snapshot is not None else audit.get("nativeSnapshot")
    native = _validate_native_snapshot(native_doc) if native_doc is not None else None
    plan_exceptions = _exception_map({"schemaVersion": 1, "exceptions": audit.get("exceptions", [])})
    inventory = {row["path"]: row for row in audit.get("inventory", [])}
    seen_sources, seen_targets, rows, plan_issues = set(), set(), [], []
    global_blockers = [{"code": issue["code"], "paths": issue.get("paths", [issue.get("path")]), "ruleId": issue.get("ruleId")}
                       for issue in audit.get("issues", [])
                       if issue.get("severity") != "exception" and issue.get("code") in {"SYMLINK_SCAN_BLOCKED", "ROOT_CASE_COLLISION", "ROOT_CASE_MISMATCH", "PATH_CASE_COLLISION", "SOURCE_HASH_BUDGET_EXCEEDED", "STRUCTURE_SCAN_BUDGET_EXCEEDED"}]
    for guid, paths in audit.get("duplicateGuids", {}).items():
        global_blockers.append({"code": "DUPLICATE_GUID", "guid": guid, "paths": paths})
    blockers = list(global_blockers)
    # The graph and old-path findings are only current if every inspected
    # source file is unchanged since inspect(). Re-hash the bounded audit set.
    for rel, expected in audit.get("sourceHashes", {}).items():
        current = Path(audit["projectRoot"]) / rel
        if not current.is_file() or _sha(current) != expected:
            blockers.append({"code": "AUDIT_CONSUMER_STALE", "path": rel})
    for i, item in enumerate(mappings):
        loc = "mappings[" + str(i) + "]"
        if not isinstance(item, dict) or set(item) != {"source", "target"}:
            fail("STRUCTURE_MAPPING", loc, "Each mapping requires source and target")
        source = _valid_rel(item["source"], loc + ".source")
        target = _valid_rel(item["target"], loc + ".target")
        if not source.startswith("Assets/") or not target.startswith("Assets/"):
            fail("STRUCTURE_MAPPING_ROOT", loc, "Native asset moves must stay within Assets/")
        if source.endswith(".meta") or target.endswith(".meta") or Path(source).suffix != Path(target).suffix:
            fail("STRUCTURE_MAPPING_EXTENSION", loc, "Move an imported asset with its original extension; do not map .meta files")
        if source == target or source in seen_sources or target in seen_targets:
            fail("STRUCTURE_MAPPING", loc, "Mappings must be one-to-one and change the path")
        seen_sources.add(source); seen_targets.add(target)
        src = inventory.get(source)
        if src is None:
            fail("STRUCTURE_MAPPING_SOURCE", source, "Source is not in the audited inventory")
        if not _standard_target(target):
            plan_issues.append({"code": "TARGET_NOT_STANDARD", "ruleId": "STR-05", "path": target, "severity": "warning"})
            blockers.append({"code": "TARGET_NOT_STANDARD", "ruleId": "STR-05", "path": target})
        source_path = Path(audit["projectRoot"]) / source
        meta = Path(str(source_path) + ".meta")
        meta_hash = _sha(meta) if meta.is_file() and meta.stat().st_size <= MAX_HASH_FILE_BYTES else None
        native_row = native["byPath"].get(source) if native else None
        meta_guid = None
        if meta_hash:
            match = re.search(r"(?m)^guid:\s*([0-9a-fA-F]{32})\s*$", meta.read_text(encoding="utf-8", errors="replace"))
            meta_guid = match.group(1).lower() if match else None
        current_source_hash = _sha(source_path) if source_path.is_file() and source_path.stat().st_size <= MAX_HASH_FILE_BYTES else None
        input_state = native["document"].get("inputState", {}) if native else {}
        observed_source = input_state.get(source)
        observed_meta = input_state.get(source + ".meta")
        source_state_valid = isinstance(observed_source, dict) and observed_source.get("sha256") == current_source_hash and current_source_hash == src.get("sha256")
        meta_state_valid = isinstance(observed_meta, dict) and observed_meta.get("sha256") == meta_hash and bool(meta_hash)
        if not source_state_valid:
            blockers.append({"code": "SOURCE_SNAPSHOT_STALE_OR_MISSING", "path": source})
        if not meta_state_valid:
            blockers.append({"code": "META_SNAPSHOT_STALE_OR_MISSING", "path": source + ".meta"})
        if not meta.is_file():
            blockers.append({"code": "META_MISSING", "path": source})
        elif not meta_hash:
            blockers.append({"code": "META_HASH_BUDGET_EXCEEDED", "path": source + ".meta"})
        elif meta_guid is None:
            blockers.append({"code": "META_GUID_INVALID", "path": source})
        if native_row is None:
            blockers.append({"code": "NATIVE_IDENTITY_MISSING", "path": source})
        elif not native_row["identityConsistent"]:
            blockers.append({"code": "NATIVE_LOCAL_IDS_UNAVAILABLE", "path": source})
        elif meta_guid and meta_guid != native_row["guid"]:
            blockers.append({"code": "META_NATIVE_GUID_MISMATCH", "path": source,
                             "metaGuid": meta_guid, "nativeGuid": native_row["guid"]})
        target_type_exception = None
        if native_row:
            mismatch, expected_kinds = _type_path_mismatch(target, native_row["importedType"])
            if mismatch:
                target_type_exception = _exception_for(plan_exceptions, target, "STR-05")
                plan_issues.append({"code": "TARGET_TYPE_DIRECTORY_MISMATCH", "ruleId": "STR-05", "path": target,
                                    "importedType": native_row["importedType"], "expectedKinds": expected_kinds,
                                    "severity": "exception" if target_type_exception else "warning",
                                    "exceptionRuleId": target_type_exception["ruleId"] if target_type_exception else None})
                if not target_type_exception:
                    blockers.append({"code": "TARGET_TYPE_DIRECTORY_MISMATCH", "ruleId": "STR-05", "path": target,
                                     "importedType": native_row["importedType"], "expectedKinds": expected_kinds})
        resource_key = None
        if "/Resources/" in source:
            old_key = source.split("/Resources/", 1)[1].rsplit(".", 1)[0]
            if "/Resources/" in target:
                new_key = target.split("/Resources/", 1)[1].rsplit(".", 1)[0]
            else:
                new_key = None
            resource_key = {"old": old_key, "new": new_key,
                            "consumerPatchesRequired": old_key != new_key}
        rows.append({"source": source, "target": target, "guid": native_row["guid"] if native_row else None,
                     "importedType": native_row["importedType"] if native_row else None,
                     "objects": native_row["objects"] if native_row else None,
                     "sourceSha256": src["sha256"], "metaSha256": meta_hash, "metaGuid": meta_guid,
                     "reverseDependencies": audit.get("reverseDependencies", {}).get(source, []),
                     "resourceKeyMapping": resource_key,
                     "targetTypeException": target_type_exception,
                     "dynamicKeys": [x for x in audit.get("dynamicLoads", []) if x.get("file") == source],
                     "nativeProvenance": native["document"].get("provenance") if native else None,
                     "status": "blocked" if not source_state_valid or not meta_state_valid or not native_row or not native_row["identityConsistent"] else "observed"})
        for issue in audit.get("issues", []):
            candidate_assets = issue.get("candidateAssets", [])
            unresolved_type = issue.get("code") == "RESOURCE_TYPE_UNOBSERVED" and any(
                not native or p not in native["byPath"] for p in candidate_assets)
            if (issue.get("code") in {"RESOURCE_KEY_AMBIGUOUS", "RESOURCE_TYPE_AMBIGUOUS"} or unresolved_type) and source in candidate_assets:
                blockers.append({"code": "RESOURCE_RESOLUTION_AMBIGUOUS", "path": source, "resourceKey": issue.get("key")})
            if issue.get("code") == "DYNAMIC_LOAD_UNRESOLVED" and "/Resources/" in source:
                blockers.append({"code": "DYNAMIC_RESOURCE_KEY_UNRESOLVED", "source": source, "consumer": issue.get("file"), "span": issue.get("span")})
            if issue.get("code") == "OLD_PATH_CONSUMER":
                value = issue.get("value", "").rstrip("/")
                no_ext = str(PurePosixPath(source).with_suffix(""))
                if value in {source, no_ext} or source.startswith(value + "/"):
                    blockers.append({"code": "OLD_PATH_CONSUMER_UNHANDLED", "source": source, "consumer": issue.get("file"), "value": issue.get("value")})
        if resource_key and resource_key["old"] != resource_key["new"]:
            for load in audit.get("resourceLoads", []):
                if load.get("key") == resource_key["old"] and source in load.get("candidateAssets", []):
                    blockers.append({"code": "RESOURCE_KEY_CONSUMER_UNHANDLED", "source": source,
                                     "consumer": load.get("file"), "key": resource_key["old"],
                                     "targetKey": resource_key["new"], "span": load.get("span")})
    # Case-insensitive target collisions are refused, including unmapped files.
    existing_folded = {p.casefold(): p for p in inventory}
    for row in rows:
        collision = existing_folded.get(row["target"].casefold())
        if collision:
            blockers.append({"code": "TARGET_OCCUPIED", "path": row["target"], "existing": collision})
        if Path(audit["projectRoot"], row["target"]).exists():
            blockers.append({"code": "TARGET_OCCUPIED", "path": row["target"]})
        if Path(audit["projectRoot"], row["target"] + ".meta").exists() or row["target"] + ".meta" in existing_folded:
            blockers.append({"code": "TARGET_META_OCCUPIED", "path": row["target"] + ".meta"})
    complete = not blockers and all(r["status"] == "observed" for r in rows)
    steps = [{"kind": "asset.move", "source": r["source"], "target": r["target"]} for r in rows]
    status = "declaration_only" if complete else "blocked"
    return {"schema": PLAN_SCHEMA, "status": status,
            "batchReadiness": "not_evaluated",
            "projectConformance": "not-established",
            "remainingStructureIssues": [issue for issue in audit.get('issues',[]) if issue.get('code')=='BUILD_SCENE_NONSTANDARD_PATH' and issue.get('path') not in seen_sources],
            "projectRoot": audit["projectRoot"], "mappings": rows, "blockers": blockers,
            "proposedSteps": steps, "issues": plan_issues,
            "batchSpec": {"schemaVersion": 2, "operation": "batch", "steps": steps} if complete else None,
            "nativeEvidence": native["document"] if native else None,
            "nativeSnapshotSha256": hashlib.sha256(json.dumps(native["document"], sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest() if native else None,
            "preconditions": {r["source"]: {"sha256": r["sourceSha256"], "metaSha256": r["metaSha256"],
                                               "guid": r["guid"]} for r in rows},
            "limitations": ["This is a declaration only; it never executes a move.",
                            "Pass through the existing batch planner, which re-hashes dependencies and uses native AssetDatabase moves.",
                            "This output is not a ready batch plan; run the existing batch planner after explicitly resolving all listed consumers.",
                            "Dynamic or reflection-derived loading keys remain explicit unresolved consumers until an authorized consumer update and native re-readback resolve them."]}
