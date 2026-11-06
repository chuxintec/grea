"""Read-only batch analysis of candidate assets already owned by a target.

Only byte-identical source/target asset pairs with an exact shared GUID and a
native serialized PPtr identity can be emitted as existing ``externalAssets``
rows. This module does not infer Unity object types from file extensions.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .errors import BeaverError, fail
from .io import inside, load, read, safe

_GUID = re.compile(rb"^guid:\s*([a-f0-9]{32})\s*$", re.M)
_IMPORTER = re.compile(rb"^([A-Za-z][A-Za-z0-9]*)Importer:\s*$", re.M)
_MAX_ADDITIONS = 4096
_MAX_META_INDEX = 100000
_MAX_META_BYTES = 1024 * 1024
_MAX_ORACLE_BYTES = 64 * 1024 * 1024
_REUSABLE_SUFFIXES = {".asset", ".mat", ".png", ".ttf", ".otf", ".shader", ".txt", ".json"}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_rows(files):
    if isinstance(files, list):
        rows = {row.get("path"): row for row in files if isinstance(row, dict)}
    elif isinstance(files, dict):
        rows = files
    else:
        return {}
    return {path: row for path, row in rows.items() if isinstance(path, str) and isinstance(row, dict)}


def _guid(path: Path):
    raw = read(path, _MAX_META_BYTES)
    match = _GUID.search(raw)
    if match and match.start() > 4096:
        fail("ASSET_REUSE_GUID_POSITION", str(path), "Unity meta GUID must occur in the first 4096 bytes")
    if not match and re.search(rb"^guid:", raw, re.M):
        fail("ASSET_REUSE_GUID_FORMAT", str(path), "Unity meta GUID line is malformed")
    return match.group(1).decode("ascii") if match else None


def _importer(raw: bytes):
    matches = _IMPORTER.findall(raw)
    if len(matches) != 1:
        return None
    return matches[0].decode("ascii")


def _target_guid_index(root: Path, wanted: set[str]):
    """Index only GUID lines for candidate GUIDs; keep traversal bounded."""
    result = {guid: [] for guid in wanted}
    assets = root / "Assets"
    if not assets.is_dir():
        return result
    count = 0
    for path in assets.rglob("*.meta"):
        if path.is_symlink():
            fail("ASSET_REUSE_TARGET_SYMLINK", str(path), "Target metadata traversal does not follow symlinks")
        count += 1
        if count > _MAX_META_INDEX:
            fail("ASSET_REUSE_META_BUDGET", str(assets), "Target metadata index exceeds file budget")
        try:
            meta = read(path, _MAX_META_BYTES)
        except OSError as exc:
            fail("ASSET_REUSE_META_READ", str(path), str(exc))
        match = _GUID.search(meta)
        if match and match.start() > 4096:
            fail("ASSET_REUSE_GUID_POSITION", str(path), "Unity meta GUID must occur in the first 4096 bytes")
        if not match and re.search(rb"^guid:", meta, re.M):
            fail("ASSET_REUSE_GUID_FORMAT", str(path), "Unity meta GUID line is malformed")
        if match:
            value = match.group(1).decode("ascii")
            if value in result:
                result[value].append(path.relative_to(root).as_posix()[:-5])
    for values in result.values():
        values.sort()
    return result


def _native_rows(candidate: Path, files: dict, native_oracle: dict):
    oracle_path = candidate / "Analysis/BeaverIntakeBindings/serialized-oracle.json"
    raw = read(oracle_path, _MAX_ORACLE_BYTES)
    digest = _sha(raw)
    pin = files.get("Analysis/BeaverIntakeBindings/serialized-oracle.json")
    if not isinstance(pin, dict) or pin.get("sha256") != digest or pin.get("bytes") != len(raw):
        fail("ASSET_REUSE_ORACLE_PIN", str(oracle_path), "Serialized oracle does not match candidate inventory pins")
    loaded = load(raw, max_nodes=8_000_000)
    if loaded != native_oracle:
        fail("ASSET_REUSE_ORACLE_INPUT", str(oracle_path), "Passed native oracle differs from frozen candidate oracle")
    prefabs = loaded.get("prefabs") if isinstance(loaded, dict) else None
    if not isinstance(prefabs, list):
        fail("ASSET_REUSE_ORACLE_FORMAT", str(oracle_path), "Oracle prefab rows are required")
    by_asset = {}
    for prefab in prefabs:
        if not isinstance(prefab, dict) or not isinstance(prefab.get("owners"), list):
            fail("ASSET_REUSE_ORACLE_FORMAT", str(oracle_path), "Malformed native owner row")
        for owner in prefab["owners"]:
            if not isinstance(owner, dict) or not isinstance(owner.get("properties"), list):
                fail("ASSET_REUSE_ORACLE_FORMAT", str(oracle_path), "Malformed native property row")
            for prop in owner["properties"]:
                ref = prop.get("reference") if isinstance(prop, dict) else None
                if not isinstance(ref, dict) or not ref.get("guid"):
                    continue
                if (not isinstance(ref.get("assetPath"), str) or not isinstance(ref.get("localId"), int)
                        or isinstance(ref.get("localId"), bool) or not ref.get("type")
                        or not isinstance(ref.get("assembly"), str)
                        or not isinstance(ref.get("name"), str)):
                    fail("ASSET_REUSE_ORACLE_REFERENCE", str(oracle_path), "Native PPtr identity is incomplete")
                identity = {key: ref[key] for key in
                            ("guid", "localId", "type", "assembly", "name", "assetPath", "scriptType", "scriptAssembly")}
                by_asset.setdefault(ref["assetPath"], {}).setdefault(ref["guid"], {})[
                    (ref["localId"], ref["type"], ref["assembly"], ref["name"])] = identity
    return by_asset, {"path": str(oracle_path), "sha256": digest, "bytes": len(raw),
                      "planSha256": loaded.get("planSha256")}


def _batch_stage(stage: Path, expected_project: Path | None = None):
    stage = safe(stage)
    plan_path, journal_path, native_path = (stage / name for name in
                                             ("batch-plan.json", "journal.json", "native-result.json"))
    plan_raw, journal_raw, native_raw = (read(path, _MAX_ORACLE_BYTES) for path in
                                         (plan_path, journal_path, native_path))
    plan_sha = _sha(plan_raw)
    plan, journal, native = (load(raw, max_nodes=8_000_000) for raw in (plan_raw, journal_raw, native_raw))
    project_raw = plan.get("projectRoot")
    if not isinstance(project_raw, str) or not Path(project_raw).is_absolute():
        fail("ASSET_REUSE_BATCH_PROJECT", str(plan_path), "Native inspection plan requires an absolute projectRoot")
    project = safe(Path(project_raw))
    if (journal.get("status") != "complete" or journal.get("projectRoot") != str(project)
            or journal.get("planSha256") != plan_sha or native.get("planSha256") != plan_sha
            or journal.get("native") != native or native.get("status") != "verified"
            or native.get("editorVersion") != "6000.6.2f1"
            or journal.get("recoveryWitnessMatches") is not True or journal.get("unplannedPaths") != []
            or journal.get("unplannedDirectories", []) != []):
        fail("ASSET_REUSE_BATCH_RECEIPT", str(stage), "Plan, complete journal, and verified Editor result do not bind")
    if expected_project is not None and project != expected_project:
        fail("ASSET_REUSE_BATCH_PROJECT", str(project), "Inspection project differs from requested project")
    spec = plan.get("spec", {})
    steps = spec.get("steps") if isinstance(spec, dict) else None
    if (plan.get("writeSet") != [] or journal.get("writeSet") not in (None, [])
            or not isinstance(steps, list) or not steps
            or any(not isinstance(step, dict) or set(step) != {"kind", "assetPath"}
                   or step.get("kind") != "asset.inspect" for step in steps)):
        fail("ASSET_REUSE_BATCH_SCOPE", str(plan_path), "Only an all-read-only asset.inspect plan is accepted")
    paths = [step["assetPath"] for step in steps]
    if len(set(paths)) != len(paths):
        fail("ASSET_REUSE_BATCH_SCOPE", str(plan_path), "Inspected asset paths must be unique")
    before = plan.get("before")
    if not isinstance(before, dict):
        fail("ASSET_REUSE_BATCH_BEFORE", str(plan_path), "Plan before-image map is required")
    assets = native.get("assets")
    if (native.get("completedSteps") != len(paths) or not isinstance(assets, list) or len(assets) != len(paths)
            or {row.get("path") for row in assets if isinstance(row, dict)} != set(paths)):
        fail("ASSET_REUSE_BATCH_ASSETS", str(native_path), "Native asset report must exactly cover inspected paths")
    by_path, pins = {}, []
    for row in assets:
        if not isinstance(row, dict) or set(row) != {"path", "guid", "contentSha256", "metaSha256", "importerType",
                                                     "importerAssembly", "completeObjectSet", "objects"}:
            fail("ASSET_REUSE_BATCH_ASSET", str(native_path), "Native asset row has an unsupported schema")
        path = row["path"]
        if (not isinstance(row["guid"], str) or not re.fullmatch(r"[a-f0-9]{32}", row["guid"])
                or not all(isinstance(row[k], str) and row[k] for k in
                           ("contentSha256", "metaSha256", "importerType", "importerAssembly"))
                or row["completeObjectSet"] is not True or not isinstance(row["objects"], list)
                or not row["objects"]):
            fail("ASSET_REUSE_BATCH_OBJECTS", path, "Complete native asset identity and nonempty object set required")
        objects = {}
        object_ids = set()
        for obj in row["objects"]:
            if not isinstance(obj, dict) or set(obj) != {"guid", "localId", "type", "assembly", "name"}:
                fail("ASSET_REUSE_BATCH_OBJECT", path, "Native object identity has an unsupported schema")
            if (obj["guid"] != row["guid"] or isinstance(obj["localId"], bool)
                    or not isinstance(obj["localId"], int) or not -(1 << 63) <= obj["localId"] < (1 << 63)
                    or obj["localId"] == 0 or obj["localId"] in object_ids
                    or not all(isinstance(obj[k], str) for k in ("type", "assembly", "name"))
                    or not obj["type"] or not obj["assembly"]):
                fail("ASSET_REUSE_BATCH_OBJECT", path, "Native object identity is incomplete or belongs to another GUID")
            object_ids.add(obj["localId"])
            ident = (obj["localId"], obj["type"], obj["assembly"], obj["name"])
            if ident in objects:
                fail("ASSET_REUSE_BATCH_OBJECT", path, "Duplicate native object identity")
            objects[ident] = dict(obj)
        for suffix, expected in (("", row["contentSha256"]), (".meta", row["metaSha256"])):
            before_row = before.get(path + suffix)
            if not isinstance(before_row, dict) or before_row.get("sha256") != expected:
                fail("ASSET_REUSE_BATCH_BEFORE", path + suffix, "Plan before-image does not match native asset readback")
            current = project / (path + suffix)
            raw = read(inside(project, path + suffix))
            if _sha(raw) != expected or before_row.get("bytes") != len(raw):
                fail("ASSET_REUSE_BATCH_DRIFT", path + suffix, "Inspected project bytes differ from before-image")
        by_path[path] = {"row": row, "objects": objects}
    pin = {"stage": str(stage), "plan": {"path": str(plan_path), "sha256": plan_sha, "bytes": len(plan_raw)},
           "journal": {"path": str(journal_path), "sha256": _sha(journal_raw), "bytes": len(journal_raw)},
           "nativeResult": {"path": str(native_path), "sha256": _sha(native_raw), "bytes": len(native_raw)},
           "projectRoot": str(project), "editorVersion": native["editorVersion"]}
    return by_path, pin


def _batch_evidence(candidate: Path, target: Path, files: dict, evidence_paths: list | None):
    if not evidence_paths:
        return {}, [], []
    complete, pins, rejected = {}, [], []
    for item in evidence_paths:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            fail("ASSET_REUSE_EVIDENCE_PIN", str(item), "Evidence path and expected SHA-256 are both required")
        bundle_path = safe(Path(item["path"]))
        bundle_raw = read(bundle_path, _MAX_ORACLE_BYTES)
        if _sha(bundle_raw) != item["sha256"]:
            fail("ASSET_REUSE_EVIDENCE_DRIFT", str(bundle_path), "Evidence bundle SHA-256 differs")
        bundle = load(bundle_raw, max_nodes=10000)
        if (not isinstance(bundle, dict) or set(bundle) != {"contract", "sourceStage", "targetStage"}
                or bundle.get("contract") != "beaver-native-asset-reuse-evidence/1"):
            fail("ASSET_REUSE_EVIDENCE_SCHEMA", str(bundle_path), "Closed asset reuse evidence bundle contract required")
        source_rows, source_pin = _batch_stage(Path(bundle["sourceStage"]))
        target_rows, target_pin = _batch_stage(Path(bundle["targetStage"]), expected_project=target)
        for source_path, source_row in source_rows.items():
            srow = source_row["row"]
            targets = [(path, row) for path, row in target_rows.items() if row["row"]["guid"] == srow["guid"]]
            if len(targets) != 1:
                rejected.append({"code": "ASSET_REUSE_NATIVE_TARGET_IDENTITY_MISSING", "source": source_path,
                                 "guid": srow["guid"], "targetMatches": len(targets)})
                continue
            target_path, target_row = targets[0]
            trow = target_row["row"]
            if (srow["contentSha256"], srow["metaSha256"], srow["importerType"], srow["importerAssembly"],
                    source_row["objects"]) != (
                    trow["contentSha256"], trow["metaSha256"], trow["importerType"], trow["importerAssembly"],
                    target_row["objects"]):
                rejected.append({"code": "ASSET_REUSE_NATIVE_IDENTITY_MISMATCH", "source": source_path,
                                 "target": target_path, "guid": srow["guid"]})
                continue
            source_raw, source_hash = _pin_candidate_file(candidate, files, source_path)
            source_meta_raw, source_meta_hash = _pin_candidate_file(candidate, files, source_path + ".meta")
            target_raw = read(inside(target, target_path))
            target_meta_raw = read(inside(target, target_path + ".meta"))
            if (source_hash != srow["contentSha256"] or source_meta_hash != srow["metaSha256"]
                    or _sha(target_raw) != trow["contentSha256"] or _sha(target_meta_raw) != trow["metaSha256"]):
                fail("ASSET_REUSE_NATIVE_FILE_DRIFT", source_path, "Native inspected file/meta pins differ from current candidate/target")
            identities = {}
            for ident, obj in source_row["objects"].items():
                identities[ident] = {"guid": obj["guid"], "localId": obj["localId"], "type": obj["type"],
                                     "assembly": obj["assembly"], "name": obj["name"], "assetPath": source_path,
                                     "scriptType": "", "scriptAssembly": ""}
            complete[(source_path, srow["guid"], target_path)] = {
                "objects": identities, "importerType": srow["importerType"],
                "importerAssembly": srow["importerAssembly"],
                "sourcePlan": source_pin, "targetPlan": target_pin,
            }
        pins.append({"path": str(bundle_path), "sha256": item["sha256"], "bytes": len(bundle_raw),
                     "sourceStage": source_pin, "targetStage": target_pin})
    return complete, pins, rejected


def _pin_candidate_file(candidate: Path, files: dict, path: str):
    row = files.get(path)
    if not isinstance(row, dict) or not isinstance(row.get("sha256"), str):
        fail("ASSET_REUSE_CANDIDATE_PIN", path, "Candidate inventory SHA-256 is missing")
    actual = inside(candidate, path)
    raw = read(actual)
    digest = _sha(raw)
    if digest != row["sha256"] or row.get("bytes", len(raw)) != len(raw):
        fail("ASSET_REUSE_CANDIDATE_DRIFT", path, "Candidate bytes differ from frozen inventory")
    return raw, digest


def scan(candidate: Path, target: Path, additions: list, files: dict, *,
         native_oracle: dict, evidence_paths: list | None = None) -> dict:
    """Scan every mapped addition for an existing source/destination collision.

    A same-source-path target owner is considered as a possible retained
    location even when the proposed copied target is in a new subtree.
    """
    candidate, target = safe(candidate), safe(target)
    conflicts, external_assets, remaining, observations = [], [], [], []
    file_rows = _file_rows(files)
    pins = {"candidate": {}, "target": {}, "evidence": []}
    if not isinstance(additions, list) or len(additions) > _MAX_ADDITIONS:
        return {"additions": [], "externalAssets": [], "conflicts": [
            {"code": "ASSET_REUSE_ADDITIONS_BUDGET", "count": len(additions) if isinstance(additions, list) else None}],
            "evidence": {}, "pins": pins}

    try:
        native_by_asset, oracle_pin = _native_rows(candidate, file_rows, native_oracle)
        pins["evidence"].append(oracle_pin)
    except BeaverError as exc:
        native_by_asset = {}
        conflicts.append(exc.as_dict())
    try:
        complete_native, evidence_rows, evidence_conflicts = _batch_evidence(candidate, target, file_rows, evidence_paths)
        pins["evidence"].extend(evidence_rows)
        conflicts.extend(evidence_conflicts)
        for (source_path, guid, target_path), row in complete_native.items():
            observed = native_by_asset.get(source_path, {}).get(guid, {})
            mismatch = [identity for identity in observed if identity not in row["objects"]]
            if mismatch:
                conflicts.append({"code": "ASSET_REUSE_ORACLE_BATCH_IDENTITY_MISMATCH", "source": source_path,
                                  "target": target_path, "guid": guid, "objects": mismatch})
                continue
    except BeaverError as exc:
        complete_native = {}
        conflicts.append(exc.as_dict())

    seen_sources, seen_destinations = set(), set()
    prepared = []
    candidate_guid_owners = {}
    for row in additions:
        if not isinstance(row, dict) or not isinstance(row.get("source"), str) or not isinstance(row.get("target"), str):
            conflicts.append({"code": "ASSET_REUSE_ADDITION_FORMAT", "row": row})
            continue
        source_path, proposed_target = row["source"], row["target"]
        if source_path in seen_sources or proposed_target in seen_destinations:
            conflicts.append({"code": "ASSET_REUSE_DUPLICATE_MAPPING", "source": source_path, "target": proposed_target})
            remaining.append(row)
            continue
        seen_sources.add(source_path); seen_destinations.add(proposed_target)
        try:
            src = inside(candidate, source_path)
            src_meta = inside(candidate, source_path + ".meta")
        except BeaverError as exc:
            conflicts.append({**exc.as_dict(), "source": source_path, "target": proposed_target})
            remaining.append(row)
            continue
        if not src.is_file() or not src_meta.is_file():
            conflicts.append({"code": "ASSET_REUSE_SOURCE_PAIR_MISSING", "source": source_path, "target": proposed_target})
            remaining.append(row)
            continue
        try:
            source_raw, source_hash = _pin_candidate_file(candidate, file_rows, source_path)
            meta_raw, meta_hash = _pin_candidate_file(candidate, file_rows, source_path + ".meta")
            guid = _guid(src_meta)
        except BeaverError as exc:
            conflicts.append({**exc.as_dict(), "source": source_path, "target": proposed_target})
            remaining.append(row)
            continue
        if not guid:
            conflicts.append({"code": "ASSET_REUSE_SOURCE_GUID_MISSING", "source": source_path, "target": proposed_target})
            remaining.append(row)
            continue
        candidate_guid_owners.setdefault(guid, []).append(source_path)
        prepared.append((row, source_path, proposed_target, guid, source_hash, meta_hash, source_raw, meta_raw))

    wanted_guids = {item[3] for item in prepared}
    candidate_guid_owners = {guid: [] for guid in wanted_guids}
    for meta_path in file_rows:
        if not (meta_path.startswith("Assets/") and meta_path.endswith(".meta") and meta_path[:-5] in file_rows):
            continue
        try:
            _meta_raw, _ = _pin_candidate_file(candidate, file_rows, meta_path)
            owner_guid = _guid(inside(candidate, meta_path))
        except BeaverError as exc:
            conflicts.append({**exc.as_dict(), "candidateMeta": meta_path})
            continue
        if owner_guid in candidate_guid_owners:
            candidate_guid_owners[owner_guid].append(meta_path[:-5])
    duplicate_candidate_guids = {g for g, owners in candidate_guid_owners.items() if len(owners) != 1}
    try:
        target_guid_owners = _target_guid_index(target, wanted_guids)
    except BeaverError as exc:
        conflicts.append(exc.as_dict())
        target_guid_owners = {g: [] for g in wanted_guids}

    for row, source_path, proposed_target, guid, source_hash, meta_hash, source_raw, meta_raw in prepared:
        candidate_hash = file_rows[source_path]["sha256"]
        candidate_meta_hash = file_rows[source_path + ".meta"]["sha256"]
        try:
            proposed_file = inside(target, proposed_target)
            proposed_meta = inside(target, proposed_target + ".meta")
            source_file = inside(target, source_path)
            source_meta = inside(target, source_path + ".meta")
        except BeaverError as exc:
            conflicts.append({**exc.as_dict(), "source": source_path, "proposedTarget": proposed_target})
            remaining.append(row)
            continue
        proposed_occupied = proposed_file.exists() or proposed_meta.exists()
        source_occupied = source_file.exists() or source_meta.exists()
        try:
            source_existing_guid = _guid(source_meta) if source_meta.is_file() else None
        except BeaverError as exc:
            conflicts.append({**exc.as_dict(), "source": source_path, "proposedTarget": proposed_target})
            source_existing_guid = None
        if source_occupied and source_existing_guid != guid:
            observations.append({"code": "ASSET_REUSE_SOURCE_PATH_DIFFERENT_GUID", "source": source_path,
                                 "proposedTarget": proposed_target, "candidateGuid": guid,
                                 "targetGuid": source_existing_guid,
                                 "blocks": bool(proposed_occupied)})
        locations = list(target_guid_owners.get(guid, []))
        if proposed_occupied and proposed_target not in locations:
            locations.append(proposed_target)
        locations = list(dict.fromkeys(locations))
        if not locations:
            remaining.append(row)
            continue
        reusable = False
        row_had_failure = False
        external_start = len(external_assets)
        for target_path in locations:
            try:
                target_file, target_meta = inside(target, target_path), inside(target, target_path + ".meta")
            except BeaverError as exc:
                conflicts.append({**exc.as_dict(), "source": source_path, "collisionTarget": target_path})
                row_had_failure = True
                continue
            collision = {"source": source_path, "proposedTarget": proposed_target, "collisionTarget": target_path,
                         "guid": guid, "candidateSha256": candidate_hash, "candidateMetaSha256": candidate_meta_hash}
            if not target_file.is_file() or not target_meta.is_file():
                conflicts.append({"code": "ASSET_REUSE_TARGET_PAIR_INCOMPLETE", **collision})
                row_had_failure = True
                continue
            try:
                target_raw, target_meta_raw = read(target_file), read(target_meta, _MAX_META_BYTES)
                target_guid = _guid(target_meta)
            except BeaverError as exc:
                conflicts.append({**exc.as_dict(), "source": source_path, "collisionTarget": target_path})
                row_had_failure = True
                continue
            target_hash, target_meta_hash = _sha(target_raw), _sha(target_meta_raw)
            pins["candidate"][source_path] = {"sha256": source_hash, "bytes": len(source_raw)}
            pins["candidate"][source_path + ".meta"] = {"sha256": meta_hash, "bytes": len(meta_raw)}
            pins["target"][target_path] = {"sha256": target_hash, "bytes": len(target_raw)}
            pins["target"][target_path + ".meta"] = {"sha256": target_meta_hash, "bytes": len(target_meta_raw)}
            source_guid = guid
            valid = True
            if source_guid != target_guid:
                conflicts.append({"code": "ASSET_REUSE_PROPOSED_PATH_OCCUPIED" if target_path == proposed_target else "ASSET_REUSE_GUID_MISMATCH",
                                  **collision, "targetGuid": target_guid})
                valid = False
            if source_hash != target_hash:
                conflicts.append({"code": "ASSET_REUSE_CONTENT_MISMATCH", **collision, "targetSha256": target_hash})
                valid = False
            if meta_hash != target_meta_hash:
                conflicts.append({"code": "ASSET_REUSE_META_MISMATCH", **collision, "targetMetaSha256": target_meta_hash})
            source_importer, target_importer = _importer(meta_raw), _importer(target_meta_raw)
            if not source_importer or source_importer != target_importer:
                conflicts.append({"code": "ASSET_REUSE_IMPORTER_SCOPE_MISMATCH", **collision,
                                  "sourceImporter": source_importer, "targetImporter": target_importer})
                valid = False
            if meta_hash != target_meta_hash:
                valid = False
            owners = target_guid_owners.get(guid, [])
            duplicate_owner = (guid in duplicate_candidate_guids
                               or target_guid == guid and sorted(owners) != [target_path]
                               or target_guid != guid and bool(owners))
            if duplicate_owner:
                conflicts.append({"code": "ASSET_REUSE_DUPLICATE_GUID_OWNER", **collision, "targetOwners": owners,
                                  "candidateOwners": candidate_guid_owners.get(guid, [])})
                valid = False
            if Path(source_path).suffix.casefold() not in _REUSABLE_SUFFIXES:
                conflicts.append({"code": "ASSET_REUSE_TYPE_UNSUPPORTED", **collision,
                                  "message": "Prefab or compiler-input paths cannot be declared as externalAssets"})
                valid = False
            native_row = complete_native.get((source_path, guid, target_path))
            native_objects = native_row.get("objects", {}) if native_row else {}
            if not native_row:
                code = "needs_complete_native_object_set" if native_by_asset.get(source_path, {}).get(guid) else "needs_native_identity_evidence"
                conflicts.append({"code": code, **collision,
                                  "message": "A traceable asset.inspect batch must prove complete source and target native object sets"})
                valid = False
            elif (native_row["importerType"] == "" or native_row["importerAssembly"] == ""):
                conflicts.append({"code": "ASSET_REUSE_NATIVE_IMPORTER_IDENTITY", **collision})
                valid = False
            if not valid:
                row_had_failure = True
                continue
            object_rows = [dict(localId=ident[0], type=ident[1], assembly=ident[2], name=ident[3], fields=[])
                           for ident in sorted(native_objects)]
            external_assets.append({"source": source_path, "target": target_path, "guid": guid,
                                    "sha256": source_hash, "metaSha256": meta_hash,
                                    "objects": object_rows,
                                    "reason": "Exact same GUID/content/meta/importer and complete source/target Unity asset.inspect object sets"})
            reusable = True
        if not reusable or row_had_failure:
            del external_assets[external_start:]
            remaining.append(row)

    return {"additions": remaining, "externalAssets": external_assets,
            "conflicts": conflicts,
            "observations": observations,
            "evidence": {"nativeOracle": pins["evidence"][0] if pins["evidence"] else None,
                         "additional": pins["evidence"][1:]},
            "pins": pins}
