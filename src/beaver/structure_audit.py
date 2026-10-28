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
import unicodedata

from .errors import fail, BeaverError
from .io import safe, inside, read, load
from .references import inspect_graph, _csharp_tokens, _decode_csharp_string
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
MAX_GOVERNANCE_BYTES = 32 * 1024 * 1024
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
        buckets[unicodedata.normalize('NFC',value).casefold()].append(value)
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


def _specific_asset_path_prefix(value):
    """Normalize a concrete Assets path/prefix, excluding generic Assets/ root."""
    if not isinstance(value, str):
        return None
    value = unicodedata.normalize("NFC", value.replace("\\", "/")).rstrip("/")
    parts = value.split("/")
    if len(parts) < 2 or parts[0].casefold() != "assets" or any(p in ("", ".", "..") for p in parts):
        return None
    return value


def _is_assets_root(value):
    return isinstance(value, str) and unicodedata.normalize("NFC", value.replace("\\", "/")).casefold() == "assets/"


def _is_substring_length_marker(tokens, index):
    """Narrowly recognize Substring("Assets/".Length) path slicing syntax."""
    if not 0 <= index < len(tokens):
        return False
    token = tokens[index]
    if token[0] != "string" or _decode_csharp_string(token[1]) != "Assets/":
        return False
    before = tokens[max(0, index - 3):index]
    after = tokens[index + 1:index + 4]
    return (len(before) == 3 and before[0][1] == "." and before[1][1] == "Substring" and before[2][1] == "(" and
            len(after) == 3 and after[0][1] == "." and after[1][1] == "Length" and after[2][1] == ")")


def _asset_literal_matches_source(value, source):
    """Match a concrete Assets path/prefix, not the generic Assets root token."""
    value = _specific_asset_path_prefix(value)
    if value is None:
        return False
    source = unicodedata.normalize("NFC", source.replace("\\", "/"))
    folded = value.casefold()
    source_folded = source.casefold()
    source_without_extension = str(PurePosixPath(source).with_suffix("")).casefold()
    return folded in {source_folded, source_without_extension} or source_folded.startswith(folded + "/")


def _resource_key(path):
    if "/Resources/" not in path:
        return None
    return path.split("/Resources/", 1)[1].rsplit(".", 1)[0]


def _resource_keys_equal(left, right):
    if left is None or right is None:
        return left is right
    return left.casefold() == right.casefold()


def _csharp_string_value(token):
    if token[0] == "string":
        return _decode_csharp_string(token[1])
    raw = token[1]
    if raw.startswith('@"') and raw.endswith('"'):
        return raw[2:-1].replace('""', '"')
    return None


def _strip_outer_parens(tokens):
    tokens = list(tokens)
    while len(tokens) >= 2 and tokens[0][1] == "(" and tokens[-1][1] == ")":
        depth = 0
        closes_only_at_end = True
        for index, token in enumerate(tokens):
            if token[1] == "(":
                depth += 1
            elif token[1] == ")":
                depth -= 1
                if depth == 0 and index != len(tokens) - 1:
                    closes_only_at_end = False
                    break
        if not closes_only_at_end or depth != 0:
            break
        tokens = tokens[1:-1]
    return tokens


def _dynamic_resource_prefix(expression):
    """Prove only a leading string literal concatenated with an identifier chain."""
    if not isinstance(expression, str):
        return None
    tokens = _strip_outer_parens(_csharp_tokens(expression))
    if len(tokens) < 3 or tokens[0][0] not in {"string", "opaque"} or tokens[1][1] != "+":
        return None
    prefix = _csharp_string_value(tokens[0])
    if not isinstance(prefix, str) or not prefix.endswith("/") or not prefix or "\\" in prefix:
        return None
    prefix_parts = prefix[:-1].split("/")
    if any(part in ("", ".", "..") for part in prefix_parts):
        return None
    tail = tokens[2:]
    if not tail or tail[0][0] != "id" or len(tail) % 2 == 0:
        return None
    if any(tail[i][1] != "." or tail[i + 1][0] != "id" for i in range(1, len(tail), 2)):
        return None
    return prefix


def _resource_key_matches_prefix(key, prefix):
    if (not isinstance(key, str) or not isinstance(prefix, str) or not prefix.endswith("/")
            or "\\" in key or "\\" in prefix):
        return False
    parts = key.split("/")
    prefix_parts = prefix[:-1].split("/")
    if any(part in ("", ".", "..") for part in parts) or any(part in ("", ".", "..") for part in prefix_parts):
        return False
    return key.casefold().startswith(prefix.casefold())


def _source_identity_exact(value, source):
    normalized = _specific_asset_path_prefix(value)
    if normalized is None:
        return False
    folded = normalized.casefold()
    return folded in {source.casefold(), str(PurePosixPath(source).with_suffix("")).casefold()}


def _source_comparison_context(tokens, index):
    if _inside_asset_lookup_call(tokens, index):
        return False
    def op_pair(pair):
        return pair in (("=", "="), ("!", "="))
    if index >= 2 and op_pair((tokens[index - 2][1], tokens[index - 1][1])):
        return True
    if index + 2 < len(tokens) and op_pair((tokens[index + 1][1], tokens[index + 2][1])):
        return True
    # Minimal method form: obj.Equals(literal) or String.Equals(value,literal,...).
    for call in range(max(0, index - 24), index - 1):
        if not (call > 0 and tokens[call][0] == "id" and tokens[call][1] == "Equals"
                and tokens[call - 1][1] == "." and tokens[call + 1][1] == "("):
            continue
        depth = 0
        for cursor in range(call + 1, index + 1):
            if tokens[cursor][1] == "(":
                depth += 1
            elif tokens[cursor][1] == ")":
                depth -= 1
        if depth == 1 and index > 0 and tokens[index - 1][1] in {"(", ","}:
            return True
    return False


def _inside_asset_lookup_call(tokens, index):
    asset_database_methods = {"LoadAssetAtPath", "LoadMainAssetAtPath", "LoadAssetAtGUID", "LoadAssetAtPathFromGUID"}
    for method in range(index):
        if tokens[method][0] != "id":
            continue
        name = tokens[method][1]
        owner = tokens[method - 2][1] if method >= 2 and tokens[method - 1][1] == "." else None
        lookup = ((owner == "Resources" and name in {"Load", "LoadAll"})
                  or (owner == "Addressables" and name == "LoadAssetAsync")
                  or name in asset_database_methods)
        if not lookup:
            continue
        call_open = None
        for cursor in range(method + 1, min(len(tokens), method + 24)):
            if tokens[cursor][1] == "(":
                call_open = cursor
                break
            if tokens[cursor][1] in {";", "{", "}"}:
                break
        if call_open is None or call_open > index:
            continue
        depth = 0
        for cursor in range(call_open, len(tokens)):
            if tokens[cursor][1] == "(":
                depth += 1
            elif tokens[cursor][1] == ")":
                depth -= 1
                if depth == 0:
                    if cursor >= index:
                        return True
                    break
    return False


def _governance_file(path, product_root=None):
    path = Path(path).absolute()
    try:
        resolved = safe(path)
    except BeaverError:
        return {"path": str(path), "productRelativePath": None,
                "present": path.exists() or path.is_symlink(), "sha256": None, "blocked": True}
    product_relative = None
    if product_root is not None and resolved.is_relative_to(product_root):
        product_relative = resolved.relative_to(product_root).as_posix()
    exists = resolved.is_file()
    if exists and resolved.stat().st_size > MAX_GOVERNANCE_BYTES:
        fail("STRUCTURE_GOVERNANCE_BUDGET", str(resolved), "Governance file exceeds 32 MiB")
    return {"path": str(resolved), "productRelativePath": product_relative,
            "present": exists, "sha256": hashlib.sha256(read(resolved, MAX_GOVERNANCE_BYTES)).hexdigest() if exists else None}


def _resolve_profile(project, product_root, profile_path):
    product = safe(product_root)
    if not product.is_dir():
        fail("STRUCTURE_PROFILE_ROOT", str(product), "Product root must be an existing directory")
    if isinstance(profile_path, Path):
        profile_path = str(profile_path)
    if not isinstance(profile_path, str) or not profile_path:
        fail("STRUCTURE_PROFILE_PATH", "profilePath", "Explicit profile path required")
    profile = safe(Path(profile_path) if Path(profile_path).is_absolute() else inside(product, profile_path))
    if not profile.is_relative_to(product) or not profile.is_file():
        fail("STRUCTURE_PROFILE_PATH", str(profile), "Profile must be an existing file inside the product root")
    relative = profile.relative_to(product).as_posix()
    raw_profile = read(profile)
    doc = load(raw_profile)
    if not isinstance(doc, dict) or doc.get("schemaVersion") != 1 or not isinstance(doc.get("paths"), dict):
        fail("STRUCTURE_PROFILE_SCHEMA", relative, "Expected schemaVersion 1 and paths object; full upstream schema is not validated")
    unity_rel = doc["paths"].get("unityProject")
    if not isinstance(unity_rel, str) or not unity_rel:
        fail("STRUCTURE_PROFILE_BINDING", relative, "paths.unityProject must be an explicit relative path")
    if unity_rel != ".":
        _valid_rel(unity_rel, relative + ".paths.unityProject")
    bound_project = inside(product, unity_rel)
    if bound_project != project:
        fail("STRUCTURE_PROFILE_BINDING", relative, "paths.unityProject does not resolve to the selected Unity project")
    digest = hashlib.sha256(raw_profile).hexdigest()
    identity = {"path": relative, "sha256": digest, "unityProject": unity_rel,
                "schemaVersion": doc["schemaVersion"]}
    return product, identity, profile


def _bind_product(project, product_root=None, profile_path=None):
    explicit = product_root is not None or profile_path is not None
    if explicit and (product_root is None or profile_path is None):
        fail("STRUCTURE_PROFILE_BINDING", "profile", "product_root and profile_path must be supplied together")
    if explicit:
        product, identity, profile = _resolve_profile(project, product_root, profile_path)
        docs = inside(product, "Docs/PROJECT-STRUCTURE.md")
        governance = [_governance_file(profile, product), _governance_file(docs, product)]
        return product, identity, governance, []

    candidates = [project / "grea-project.json", project.parent / "grea-project.json"]
    governance = [_governance_file(path) for path in candidates]
    invalid = []
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            product, identity, profile = _resolve_profile(project, candidate.parent, candidate.name)
        except (BeaverError, ValueError, UnicodeError, OSError) as error:
            invalid.append({"code": "PROFILE_BINDING_INVALID", "path": str(candidate), "detail": getattr(error, "message", str(error)),
                            "severity": "warning"})
            continue
        docs = inside(product, "Docs/PROJECT-STRUCTURE.md")
        governance.append(_governance_file(docs, product))
        return product, identity, governance, invalid
    invalid.extend([
        {"code": "PRODUCT_ROOT_UNLOCATED", "severity": "warning"},
        {"code": "PROFILE_MISSING", "candidates": [str(p) for p in candidates], "severity": "warning"},
        {"code": "STRUCTURE_DOCUMENTATION_UNLOCATED", "severity": "info"},
    ])
    return None, None, governance, invalid


def inspect(project, native_snapshot=None, exceptions=None, product_root=None, profile_path=None):
    """Inspect project paths and static references without writing to the project.

    ``native_snapshot`` is an optional JSON object captured by Unity.  It maps
    asset paths to imported type and object identities.  Without it, findings
    remain static and no plan can claim native type/subasset completeness.
    """
    root = safe(project)
    if not root.is_dir():
        fail("PROJECT_PATH", str(root), "Project must be an existing directory")
    bound_product_root, profile_identity, governance_files, profile_issues = _bind_product(root, product_root, profile_path)
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
                    elif candidate.is_file():
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
    issues.extend(profile_issues)
    structure_doc = None
    if bound_product_root is not None:
        structure_doc_path = inside(bound_product_root, "Docs/PROJECT-STRUCTURE.md")
        structure_doc = next((item for item in governance_files if item["path"] == str(structure_doc_path)), None)
        if not structure_doc or not structure_doc["present"]:
            issues.append({"code": "STRUCTURE_DOCUMENTATION_MISSING", "path": "Docs/PROJECT-STRUCTURE.md", "severity": "info"})
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
        row["staticPrefix"] = _dynamic_resource_prefix(row.get("key"))
        issues.append({"code": "DYNAMIC_LOAD_UNRESOLVED", "severity": "warning", **row})
    for row in graph["literalLoads"]:
        candidates = sorted(p for p in all_asset_paths if "/Resources/" in p and
                            p.split("/Resources/", 1)[1].rsplit(".", 1)[0].casefold() == row["key"].casefold())
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

    # Reuse the existing C# tokenizer: every Assets path can be a consumer,
    # including generators under already-standard roots. Comments are excluded.
    path_consumers = []
    for rel in sorted(p for p in paths + external_sources if p.endswith(".cs")):
        try:
            if (root / rel).stat().st_size > MAX_HASH_FILE_BYTES:
                continue
            text = (root / rel).read_text(encoding="utf-8-sig")
        except (UnicodeError, OSError):
            continue
        tokens=_csharp_tokens(text)
        for token_index,(kind,token,start,end) in enumerate(tokens):
            value = _decode_csharp_string(token) if kind=='string' else token[2:-1].replace('""','"') if token.startswith('@"') and token.endswith('"') else None
            if _is_substring_length_marker(tokens,token_index):
                continue
            specific_prefix=_specific_asset_path_prefix(value)
            if _is_assets_root(value) or specific_prefix is not None:
                value="Assets/" if _is_assets_root(value) else specific_prefix
                path_consumers.append({"file": rel, "value": value, "offset": start, "span":[start,end]})
                issues.append({"code": "OLD_PATH_CONSUMER", "severity": "warning", "file": rel,
                               "value": value, "span": [start, end]})
            elif kind=='opaque' and 'Assets/' in token:
                prefix=token[token.index('Assets/'):].split('{',1)[0].split('"',1)[0]
                issues.append({'code':'DYNAMIC_ASSET_PATH_UNRESOLVED','severity':'warning','file':rel,'prefix':prefix,'span':[start,end]})

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

    return {"schema": SCHEMA, "projectRoot": str(root), "productRoot": str(bound_product_root) if bound_product_root else None,
            "profileIdentity": profile_identity,
            "structureDocumentationIdentity": ({"path": "Docs/PROJECT-STRUCTURE.md", "present": structure_doc["present"], "sha256": structure_doc["sha256"]} if structure_doc else None),
            "governanceFiles": governance_files, "roots": sorted(roots),
            "scanStatus": "partial_budget" if scan_truncated else "blocked_symlink" if symlinks else "complete",
            "rootCaseCollisions": root_collisions, "inventory": inventory,
            "sourceHashes": source_hashes, "scannedInputPaths": sorted(paths+external_sources), "issues": issues,
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


def _validate_consumer_resolutions(audit, root, supplied):
    document = {"schemaVersion": 1, "resolutions": []} if supplied is None else supplied
    if (not isinstance(document, dict) or set(document) != {"schemaVersion", "resolutions"}
            or type(document.get("schemaVersion")) is not int or document.get("schemaVersion") != 1 or not isinstance(document.get("resolutions"), list)
            or len(document["resolutions"]) > 256):
        fail("CONSUMER_RESOLUTION_SCHEMA", "consumerResolutions", "Expected schemaVersion 1 and at most 256 strict resolutions")
    source_hashes = audit.get("sourceHashes", {})
    issues = audit.get("issues", [])
    result, seen = {}, set()
    required = {"file", "fileSha256", "span", "literal", "kind", "reason", "evidence"}
    for index, row in enumerate(document["resolutions"]):
        location = "consumerResolutions.resolutions[" + str(index) + "]"
        if not isinstance(row, dict) or set(row) != required:
            fail("CONSUMER_RESOLUTION_SCHEMA", location, "Resolution fields must be file,fileSha256,span,literal,kind,reason,evidence")
        file = _valid_rel(row["file"], location + ".file")
        if (not isinstance(row["fileSha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["fileSha256"])
                or not isinstance(row["span"], list) or len(row["span"]) != 2
                or any(type(value) is not int for value in row["span"])
                or row["span"][0] < 0 or row["span"][1] <= row["span"][0]
                or not isinstance(row["literal"], str) or not row["literal"]
                or row["kind"] != "source-identity-comparison"
                or any(not isinstance(row[key], str) or not row[key].strip() for key in ("reason", "evidence"))):
            fail("CONSUMER_RESOLUTION_SCHEMA", location, "Invalid hash, span, literal, kind, reason, or evidence")
        key = (file, row["span"][0], row["span"][1])
        if key in seen:
            fail("CONSUMER_RESOLUTION_DUPLICATE", location, "Repeated file/span declaration")
        seen.add(key)
        if source_hashes.get(file) != row["fileSha256"]:
            fail("CONSUMER_RESOLUTION_SOURCE_STALE", location, "fileSha256 must equal the inspected source hash")
        path = inside(root, file)
        if not path.is_file() or _sha(path) != row["fileSha256"]:
            fail("CONSUMER_RESOLUTION_SOURCE_STALE", location, "Consumer source changed after inspect")
        try:
            source = path.read_text(encoding="utf-8-sig")
        except (UnicodeError, OSError) as error:
            fail("CONSUMER_RESOLUTION_SOURCE", location, "Consumer source is unreadable: " + str(error))
        start, end = row["span"]
        if end > len(source):
            fail("CONSUMER_RESOLUTION_SPAN", location, "Span is outside the current source")
        tokens = _csharp_tokens(source)
        matches = [(i, token) for i, token in enumerate(tokens) if token[2] == start and token[3] == end]
        if len(matches) != 1:
            fail("CONSUMER_RESOLUTION_SPAN", location, "Span must identify exactly one current C# token")
        token_index, token = matches[0]
        if _csharp_string_value(token) != row["literal"]:
            fail("CONSUMER_RESOLUTION_LITERAL", location, "Declared literal does not match the current source token")
        if not _source_comparison_context(tokens, token_index):
            fail("CONSUMER_RESOLUTION_NOT_COMPARISON", location, "Literal is not in a supported ==, !=, or Equals comparison context")
        issue_match = any(issue.get("code") == "OLD_PATH_CONSUMER" and issue.get("file") == file
                          and issue.get("span") == row["span"] and issue.get("value") == row["literal"]
                          for issue in issues)
        if not issue_match:
            fail("CONSUMER_RESOLUTION_NOT_AUDITED", location, "Declaration must match an exact OLD_PATH_CONSUMER audit row")
        result[key] = dict(row)
    encoded = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return result, document, hashlib.sha256(encoded).hexdigest()


def build_plan(audit, mappings, native_snapshot=None, consumer_resolutions=None):
    """Build immutable move declarations for existing ``asset.move`` steps.

    ``mappings`` is an explicit list of {source,target}.  No file is moved and
    no consumer key is silently rewritten.  The returned batch spec is ready
    for the existing batch planner after the caller adds any consumer edits.
    """
    if not isinstance(audit, dict) or audit.get("schema") != SCHEMA or not isinstance(audit.get('projectRoot'),str):
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
    root=safe(audit['projectRoot']);current_inputs=[];current_directories=[]
    resolution_map, resolution_document, resolution_sha = _validate_consumer_resolutions(audit, root, consumer_resolutions)
    used_resolutions, accepted_resolutions = set(), []
    product_root_value = audit.get("productRoot")
    profile_identity = audit.get("profileIdentity")
    if not isinstance(product_root_value, str) or not isinstance(profile_identity, dict):
        blockers.append({"code": "PROFILE_BINDING_MISSING", "reason": "No verified product-root/profile binding was available during inspect"})
    else:
        try:
            product = safe(product_root_value)
            selected_profile = profile_identity.get("path")
            if not isinstance(selected_profile, str):
                raise BeaverError("STRUCTURE_PROFILE_BINDING", "profileIdentity.path", "Profile identity path is missing")
            _, current_identity, _ = _resolve_profile(root, product, selected_profile)
            if current_identity != profile_identity:
                blockers.append({"code": "GOVERNANCE_INPUT_STALE", "path": selected_profile})
        except BeaverError as error:
            blockers.append({"code": "GOVERNANCE_INPUT_STALE", "path": error.location, "detail": error.message})
    for record in audit.get("governanceFiles", []):
        try:
            path = safe(record["path"])
            current_present = path.is_file()
            if current_present and path.stat().st_size > MAX_GOVERNANCE_BYTES:
                raise BeaverError("STRUCTURE_GOVERNANCE_BUDGET", str(path), "Governance file exceeds 32 MiB")
            current_sha = hashlib.sha256(read(path, MAX_GOVERNANCE_BYTES)).hexdigest() if current_present else None
            if current_present != record.get("present") or current_sha != record.get("sha256"):
                blockers.append({"code": "GOVERNANCE_INPUT_STALE", "path": record.get("productRelativePath") or record.get("path")})
        except (BeaverError, KeyError, TypeError) as error:
            blockers.append({"code": "GOVERNANCE_INPUT_STALE", "path": record.get("path") if isinstance(record, dict) else None,
                             "detail": str(error)})
    for scope in ('Assets','Packages','ProjectSettings'):
        for base,dirs,files in os.walk(inside(root,scope),followlinks=False):
            for name in dirs+files:
                p=Path(base)/name
                if p.is_symlink():fail('STRUCTURE_AUDIT_STALE',str(p),'A source symlink was added after inspection; re-audit without following it')
            current_directories.extend((Path(base)/d).relative_to(root).as_posix() for d in dirs)
            current_inputs.extend((Path(base)/f).relative_to(root).as_posix() for f in files)
            if len(current_inputs)+len(current_directories)>MAX_AUDIT_FILES:fail('STRUCTURE_FILE_BUDGET',str(root),'Current input scope exceeds bounded audit policy')
    if sorted(current_inputs)!=audit.get('scannedInputPaths'):
        blockers.append({'code':'AUDIT_INPUT_SET_STALE','reason':'Source, metadata, package or settings paths changed; repeat inspect before planning'})
    # The graph and old-path findings are only current if every inspected
    # source file is unchanged since inspect(). Re-hash the bounded audit set.
    for rel, expected in audit.get("sourceHashes", {}).items():
        current = inside(root,_valid_rel(rel,'sourceHashes'))
        if not current.is_file() or _sha(current) != expected:
            blockers.append({"code": "AUDIT_CONSUMER_STALE", "path": rel})
    dynamic_prefixes = {}
    dynamic_coverage = []
    for row in audit.get("dynamicLoads", []):
        prefix = None
        file, span = row.get("file"), row.get("span")
        if isinstance(file, str) and isinstance(span, list) and len(span) == 2 and all(type(v) is int for v in span):
            path = inside(root, _valid_rel(file, "dynamicLoads.file"))
            try:
                text = path.read_text(encoding="utf-8-sig")
            except (UnicodeError, OSError):
                text = ""
            if 0 <= span[0] < span[1] <= len(text):
                expression = text[span[0]:span[1]].strip()
                if expression == row.get("key"):
                    prefix = _dynamic_resource_prefix(expression)
        dynamic_prefixes[(file, tuple(span) if isinstance(span, list) else None)] = prefix
        dynamic_coverage.append({**row, "staticPrefix": prefix,
                                 "prefixStatus": "lexical-prefix-proven" if prefix else "unresolved-expression"})
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
        source_path = inside(root,source)
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
        resource_key_unique = False
        old_key = _resource_key(source)
        if old_key is not None:
            new_key = _resource_key(target)
            candidates = sorted(path for path in inventory if _resource_key(path) is not None
                                and _resource_key(path).casefold() == old_key.casefold())
            resource_key_unique = candidates == [source]
            resource_key = {"old": old_key, "new": new_key,
                            "consumerPatchesRequired": not _resource_keys_equal(old_key, new_key),
                            "candidateAssets": candidates}
            if not resource_key_unique:
                blockers.append({"code": "RESOURCE_KEY_CANDIDATE_AMBIGUOUS", "source": source,
                                 "key": old_key, "candidateAssets": candidates})
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
            if issue.get("code") == "DYNAMIC_LOAD_UNRESOLVED" and resource_key:
                prefix = dynamic_prefixes.get((issue.get("file"), tuple(issue.get("span", []))))
                old_key, new_key = resource_key["old"], resource_key["new"]
                relevant = (prefix is None or _resource_key_matches_prefix(old_key, prefix)
                            or _resource_key_matches_prefix(new_key, prefix))
                if relevant and (not _resource_keys_equal(old_key, new_key) or not resource_key_unique):
                    blockers.append({"code": "DYNAMIC_RESOURCE_KEY_UNRESOLVED", "source": source,
                                     "consumer": issue.get("file"), "span": issue.get("span"),
                                     "staticPrefix": prefix})
            if issue.get("code") == "OLD_PATH_CONSUMER":
                value = issue.get("value", "")
                resolution_key = (issue.get("file"), *issue.get("span", [])) if isinstance(issue.get("span"), list) else None
                resolution = resolution_map.get(resolution_key) if resolution_key else None
                if resolution and resolution.get("literal") == value and _source_identity_exact(value, source):
                    used_resolutions.add(resolution_key)
                    if resolution_key not in {tuple((x["file"], *x["span"])) for x in accepted_resolutions}:
                        accepted_resolutions.append({**resolution, "state": "caller-reviewed-not-native-proof"})
                elif _is_assets_root(value) or _asset_literal_matches_source(value, source):
                    blockers.append({"code": "OLD_PATH_CONSUMER_UNHANDLED", "source": source, "consumer": issue.get("file"), "value": issue.get("value")})
            if issue.get('code')=='DYNAMIC_ASSET_PATH_UNRESOLVED':
                prefix=issue.get('prefix','Assets/').replace('\\','/').casefold()
                if source.replace('\\','/').casefold().startswith(prefix):blockers.append({'code':'DYNAMIC_ASSET_PATH_UNRESOLVED','source':source,'consumer':issue.get('file'),'span':issue.get('span')})
            if issue.get('code')=='JSON_ASSET_PATH_UNRESOLVED':
                value=issue.get('value','')
                if _asset_literal_matches_source(value, source):
                    blockers.append({'code':'JSON_ASSET_PATH_CONSUMER_UNHANDLED','source':source,'consumer':issue.get('file'),'value':value})
        if resource_key and not _resource_keys_equal(resource_key["old"], resource_key["new"]):
            for load in audit.get("resourceLoads", []):
                if isinstance(load.get("key"), str) and load["key"].casefold() == resource_key["old"].casefold() and source in load.get("candidateAssets", []):
                    blockers.append({"code": "RESOURCE_KEY_CONSUMER_UNHANDLED", "source": source,
                                     "consumer": load.get("file"), "key": resource_key["old"],
                                     "targetKey": resource_key["new"], "span": load.get("span")})
    unused_resolutions = set(resolution_map) - used_resolutions
    if unused_resolutions:
        fail("CONSUMER_RESOLUTION_UNUSED", "consumerResolutions", "Every declaration must match an affected mapped OLD_PATH_CONSUMER")
    # Case-insensitive target collisions are refused, including unmapped files.
    folded=lambda p:unicodedata.normalize('NFC',p).casefold()
    existing_folded = {folded(p): p for p in current_inputs+current_directories}
    proposed_paths=set()
    for row in rows:
        proposed_paths.add(row['target']);proposed_paths.update(p.as_posix() for p in PurePosixPath(row['target']).parents if p.as_posix()!='.')
    for collision in _case_collisions(sorted(proposed_paths)):
        blockers.append({'code':'TARGET_CASE_COLLISION','paths':collision})
    for row in rows:
        inside(root,row['target'])
        collision = existing_folded.get(folded(row["target"]))
        if collision:
            blockers.append({"code": "TARGET_OCCUPIED", "path": row["target"], "existing": collision})
        if Path(audit["projectRoot"], row["target"]).exists():
            blockers.append({"code": "TARGET_OCCUPIED", "path": row["target"]})
        if inside(root,row["target"] + ".meta").exists() or folded(row["target"] + ".meta") in existing_folded:
            blockers.append({"code": "TARGET_META_OCCUPIED", "path": row["target"] + ".meta"})
        for parent in PurePosixPath(row['target']).parents:
            parent=parent.as_posix()
            actual=existing_folded.get(folded(parent))
            if actual and (actual!=parent or actual in current_inputs):blockers.append({'code':'TARGET_PARENT_CONFLICT','path':parent,'existing':actual})
            if any(other['target']==parent for other in rows):blockers.append({'code':'TARGET_HIERARCHY_COLLISION','path':row['target'],'parent':parent})
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
            "dynamicLoadCoverage": dynamic_coverage,
            "consumerResolutions": resolution_document,
            "consumerResolutionsSha256": resolution_sha,
            "acceptedConsumerResolutions": accepted_resolutions,
            "nativeSnapshotSha256": hashlib.sha256(json.dumps(native["document"], sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest() if native else None,
            "preconditions": {r["source"]: {"sha256": r["sourceSha256"], "metaSha256": r["metaSha256"],
                                               "guid": r["guid"]} for r in rows},
            "limitations": ["This is a declaration only; it never executes a move.",
                            "Pass through the existing batch planner, which re-hashes dependencies and uses native AssetDatabase moves.",
                            "This output is not a ready batch plan; run the existing batch planner after explicitly resolving all listed consumers.",
                            "Dynamic or reflection-derived loading keys remain explicit unresolved consumers until an authorized consumer update and native re-readback resolve them."]}
