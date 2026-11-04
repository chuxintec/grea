"""Freeze a verified native script-rebinding copy as a GREA-consumable input.

This export owns only a new private candidate and adjacent analysis receipts.
It does not claim that original source assets were owned, that compiler inputs
are fully covered, or that a target intake was applied.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from . import __version__
from .candidate_snapshot import snapshot as candidate_snapshot, verify as verify_candidate
from .errors import fail
from .implementation import identity
from .intake import guid as parse_guid
from .intake_contract import _engine_object_rows, _owner_rows
from .io import encoded, inside, load, new_output, read, safe, sha, write_json
from .output_limits import copy_verified, digest_file
from .unity import source_files


CONTRACT = "beaver-intake-bindings-export/1"
PREPARATION_CONTRACT = "beaver-intake-bindings/1"
TARGET_PROFILE = "unity-6000.6.2f1-ugui"
PROJECT_LAYOUT = "beaver-intake-prepared/1"
BRIDGE_ROOT = "Assets/BeaverIntakeBindings"
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
MAX_SNAPSHOT_NODES = 8_000_000
MAX_REPORT_BYTES = 1 * 1024 * 1024
MAX_TOTAL_FIELDS = 250_000
MAX_OWNERS_PER_PREFAB = 4096
MAX_TOTAL_OWNERS = 50_000
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_GUID = re.compile(r"[0-9a-f]{32}\Z")
_REFERENCE_KEYS = {
    "guid", "localId", "type", "assembly", "name", "assetPath", "scriptType", "scriptAssembly"
}
_EMPTY_REFERENCE = {
    "guid": "", "localId": 0, "type": "", "assembly": "", "name": "",
    "assetPath": "", "scriptType": "", "scriptAssembly": ""
}


def _compact(value) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        fail("INTAKE_BINDING_EXPORT_JSON", "$", "Canonical UTF-8 JSON required: " + str(error))


def _load_bounded(path: Path, *, max_bytes: int, max_nodes: int = MAX_SNAPSHOT_NODES):
    return load(read(path, max_bytes=max_bytes), max_nodes=max_nodes)


def _write_compact(path: Path, value, *, max_bytes: int, max_nodes: int = MAX_SNAPSHOT_NODES):
    raw = _compact(value)
    load(raw, max_nodes=max_nodes)
    if len(raw) > max_bytes:
        fail("INTAKE_BINDING_EXPORT_BUDGET", str(path), "Compact JSON exceeds the declared byte budget")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"path": str(path), "sha256": sha(raw), "bytes": len(raw)}


def _same_plan(stage: Path, plan: dict):
    saved = _load_bounded(stage / "preparation-plan.json", max_bytes=8 * 1024 * 1024)
    if _compact(saved) != _compact(plan):
        fail("INTAKE_BINDING_EXPORT_PLAN", str(stage), "Plan differs from the exact plan used for native preparation")
    job = _load_bounded(stage / "binding-job.json", max_bytes=1024 * 1024)
    if (job.get("projectRoot") != str(stage / "UnityProject") or
            job.get("bridgeRoot") != BRIDGE_ROOT or job.get("bridgeAssembly") != "Beaver.IntakeBindings"):
        fail("INTAKE_BINDING_EXPORT_JOB", str(stage), "Preparation job project or bridge identity differs")
    plan_sha = job.get("planSha256")
    if not isinstance(plan_sha, str) or not _HASH.fullmatch(plan_sha):
        fail("INTAKE_BINDING_EXPORT_PLAN", str(stage), "Exact preparation plan SHA-256 is required")
    return job, plan_sha


def _snapshot_bytes(snapshot: dict):
    raw = _compact(snapshot)
    if len(raw) > MAX_SNAPSHOT_BYTES:
        fail("INTAKE_BINDING_EXPORT_BUDGET", "snapshot", "Native snapshot exceeds 64 MiB")
    load(raw, max_nodes=MAX_SNAPSHOT_NODES)
    return raw


def _verify_native_snapshot_refs(stage: Path, job: dict, plan_sha: str, snapshot: dict):
    if snapshot.get("planSha256") != plan_sha:
        fail("INTAKE_BINDING_EXPORT_SNAPSHOT", "snapshot.planSha256", "Snapshot belongs to a different preparation plan")
    snapshot_raw = _snapshot_bytes(snapshot)
    pins = []
    for mode in ("apply", "verify"):
        report_path = stage / f"{mode}-report.json"
        report = _load_bounded(report_path, max_bytes=MAX_REPORT_BYTES)
        if (report.get("status") != "verified" or report.get("mode") != mode or
                report.get("planSha256") != plan_sha):
            fail("INTAKE_BINDING_EXPORT_NATIVE", str(report_path), "Successful pinned native phase report required")
        leaf = report.get("snapshotFile")
        digest = report.get("snapshotSha256")
        size = report.get("snapshotBytes")
        if (not isinstance(leaf, str) or Path(leaf).name != leaf or
                leaf != f"{mode}-snapshot.json" or not isinstance(digest, str) or not _HASH.fullmatch(digest) or
                type(size) is not int or not 0 <= size <= MAX_SNAPSHOT_BYTES):
            fail("INTAKE_BINDING_EXPORT_NATIVE", str(report_path), "Bounded snapshot leaf, SHA-256 and byte count required")
        snapshot_path = safe(stage / leaf)
        if not snapshot_path.is_file() or snapshot_path.stat().st_size != size or digest_file(snapshot_path, MAX_SNAPSHOT_BYTES) != digest:
            fail("INTAKE_BINDING_EXPORT_NATIVE", str(snapshot_path), "Native report snapshot file identity differs")
        observed = _load_bounded(snapshot_path, max_bytes=MAX_SNAPSHOT_BYTES)
        if _compact(observed) != snapshot_raw:
            fail("INTAKE_BINDING_EXPORT_SNAPSHOT", str(snapshot_path), "Passed snapshot differs from the pinned native snapshot")
        pins.append({"mode": mode, "snapshotFile": leaf, "sha256": digest, "bytes": size})
    if pins[0]["sha256"] != pins[1]["sha256"] or pins[0]["bytes"] != pins[1]["bytes"]:
        fail("INTAKE_BINDING_EXPORT_NATIVE", str(stage), "Apply and cold-verify snapshots differ")
    return snapshot_raw, pins


def _validate_inventory(project: Path, plan: dict, prepared_files: dict):
    if not isinstance(prepared_files, dict) or not prepared_files:
        fail("INTAKE_BINDING_EXPORT_INVENTORY", str(project), "Nonempty prepared file inventory required")
    actual = source_files(project)
    if actual != prepared_files:
        fail("INTAKE_BINDING_EXPORT_DRIFT", str(project), "Prepared inventory differs from the current isolated project")
    original = plan.get("sourceFiles")
    spec = plan.get("spec")
    if not isinstance(original, dict) or not isinstance(spec, dict):
        fail("INTAKE_BINDING_EXPORT_PLAN", str(project), "Original source inventory and binding spec are required")
    selected = set(spec.get("prefabs", []))
    bindings = spec.get("bindings", [])
    if not selected or not bindings:
        fail("INTAKE_BINDING_EXPORT_PLAN", str(project), "Selected Prefabs and script bindings are required")
    for path, row in prepared_files.items():
        if not isinstance(path, str) or not isinstance(row, dict) or set(row) != {"path", "sha256", "bytes"}:
            fail("INTAKE_BINDING_EXPORT_INVENTORY", str(path), "Exact source_files inventory row required")
        if row["path"] != path or not _HASH.fullmatch(row["sha256"] or "") or type(row["bytes"]) is not int or row["bytes"] < 0:
            fail("INTAKE_BINDING_EXPORT_INVENTORY", str(path), "Invalid path/hash/byte inventory")
        if not path.startswith(("Assets/", "Packages/", "ProjectSettings/")):
            fail("INTAKE_BINDING_EXPORT_SCOPE", path, "Only Assets, Packages and ProjectSettings are product inputs")
        if path.startswith("Assets/BeaverIntakeBindingTools/") or path == "Assets/BeaverIntakeBindingTools.meta":
            fail("INTAKE_BINDING_EXPORT_SCOPE", path, "Temporary helper files must be removed before export")
        source = inside(project, path)
        if digest_file(source) != row["sha256"] or source.stat().st_size != row["bytes"]:
            fail("INTAKE_BINDING_EXPORT_DRIFT", path, "Prepared file differs from its pinned inventory row")
    mutable = set(selected)
    expected_bridge = {BRIDGE_ROOT + ".meta",
                       BRIDGE_ROOT + "/Beaver.IntakeBindings.asmdef",
                       BRIDGE_ROOT + "/Beaver.IntakeBindings.asmdef.meta"}
    for row in bindings:
        name = Path(row["source"]).name
        expected_bridge.update({BRIDGE_ROOT + "/" + name, BRIDGE_ROOT + "/" + name + ".meta"})
        if row["source"] not in original or row["source"] + ".meta" not in original:
            fail("INTAKE_BINDING_EXPORT_SOURCE", row["source"], "Original source script and metadata pins are required")
        bridge_source = BRIDGE_ROOT + "/" + name
        bridge_meta = bridge_source + ".meta"
        if prepared_files[bridge_source]["sha256"] != row["targetSha256"] or prepared_files[bridge_meta]["sha256"] != row["targetMetaSha256"]:
            fail("INTAKE_BINDING_EXPORT_BRIDGE", bridge_source, "Bridge files must be exact retained target source/meta bytes")
        if parse_guid(read(inside(project, bridge_meta)), bridge_meta) != row["targetGuid"]:
            fail("INTAKE_BINDING_EXPORT_OWNER_GUID", bridge_meta, "Bridge Meta GUID must equal the retained target GUID")
    if set(prepared_files) - set(original) - expected_bridge:
        fail("INTAKE_BINDING_EXPORT_UNPLANNED", str(project), "Unexpected product files appeared in the prepared project")
    for path, pin in original.items():
        if path not in prepared_files:
            fail("INTAKE_BINDING_EXPORT_UNPLANNED", path, "Original product file disappeared from prepared project")
        if prepared_files[path] != pin and path not in mutable:
            fail("INTAKE_BINDING_EXPORT_DRIFT", path, "Only selected Prefab bytes may change in the copied source project")
    if not expected_bridge.issubset(set(prepared_files)):
        fail("INTAKE_BINDING_EXPORT_BRIDGE", str(project), "Complete retained-script bridge and assembly inventory required")
    asmdef_path = inside(project, BRIDGE_ROOT + "/Beaver.IntakeBindings.asmdef")
    asmdef = load(read(asmdef_path))
    expected_asmdef = {"name": "Beaver.IntakeBindings", "references": spec["bridgeReferences"], "autoReferenced": False}
    if asmdef != expected_asmdef:
        fail("INTAKE_BINDING_EXPORT_BRIDGE", str(asmdef_path), "Temporary Bridge assembly identity/references differ from the reviewed spec")
    for path in selected:
        if path not in prepared_files or path + ".meta" not in prepared_files:
            fail("INTAKE_BINDING_EXPORT_PREFAB", path, "Selected Prefab and metadata required")
        if prepared_files[path + ".meta"] != original.get(path + ".meta"):
            fail("INTAKE_BINDING_EXPORT_PREFAB", path, "Selected Prefab metadata/GUID must remain unchanged")
    return sha(encoded(original)), sha(encoded(prepared_files)), expected_bridge


def _assembly_type(value, where):
    if not isinstance(value, str) or not value:
        fail("INTAKE_BINDING_EXPORT_TYPE", where, "Nonempty serialized owner type required")
    if value.startswith("binding:"):
        rest = value[len("binding:"):]
        assembly, separator, full_type = rest.partition("/")
        if not separator or not assembly or not full_type:
            fail("INTAKE_BINDING_EXPORT_TYPE", where, "Canonical binding:<assembly>/<fullType> identity required")
        return full_type, assembly
    if "," not in value:
        fail("INTAKE_BINDING_EXPORT_TYPE", where, "Assembly-qualified CLR type required for unbound owners")
    full_type, tail = value.split(",", 1)
    assembly = tail.strip().split(",", 1)[0].strip()
    if not full_type.strip() or not assembly:
        fail("INTAKE_BINDING_EXPORT_TYPE", where, "Malformed assembly-qualified owner type")
    return full_type.strip(), assembly


def _parse_reference(prop, where):
    ref = prop.get("reference")
    if not isinstance(ref, dict) or set(ref) != _REFERENCE_KEYS:
        fail("INTAKE_BINDING_EXPORT_REFERENCE", where, "Atomic ObjectReference identity record required")
    if ref == _EMPTY_REFERENCE:
        if prop.get("value") != "null":
            fail("INTAKE_BINDING_EXPORT_REFERENCE", where, "Null reference must use canonical null value")
        return {"guid": "", "localId": 0, "type": "", "assembly": ""}, None
    if not isinstance(ref["guid"], str) or not _GUID.fullmatch(ref["guid"]):
        fail("INTAKE_BINDING_EXPORT_REFERENCE", where, "Lowercase GUID required")
    if type(ref["localId"]) is not int or ref["localId"] == 0 or not -(1 << 63) <= ref["localId"] < (1 << 63):
        fail("INTAKE_BINDING_EXPORT_REFERENCE", where, "Nonzero signed64 localID required")
    for key in ("type", "assembly", "name", "assetPath", "scriptType", "scriptAssembly"):
        if not isinstance(ref[key], str):
            fail("INTAKE_BINDING_EXPORT_REFERENCE", where + "." + key, "String value required")
    if not ref["type"] or not ref["assembly"]:
        fail("INTAKE_BINDING_EXPORT_REFERENCE", where, "Resolved object reference needs type and assembly")
    expected = (f"{ref['guid']}#{ref['localId']}|{ref['type']}@{ref['assembly']}"
                f"|script:{ref['scriptType']}@{ref['scriptAssembly']}")
    if prop.get("value") != expected:
        fail("INTAKE_BINDING_EXPORT_REFERENCE", where, "Canonical reference value differs from atomic identity")
    mapped = bool(ref["scriptType"] or ref["scriptAssembly"])
    if mapped and (not ref["scriptType"] or not ref["scriptAssembly"]):
        fail("INTAKE_BINDING_EXPORT_REFERENCE", where, "Mapped script reference needs both script type and assembly")
    return {"guid": ref["guid"], "localId": ref["localId"], "type": ref["type"], "assembly": ref["assembly"]}, ref


def _scalar(prop, where):
    kind, separator, _unity_type = prop["type"].partition(":")
    if not separator:
        fail("INTAKE_BINDING_EXPORT_PROPERTY", where, "Canonical SerializedPropertyType:UnityType required")
    value = prop["value"]
    if kind == "Integer":
        return "integer", int(value, 10)
    if kind == "Boolean":
        if value not in ("true", "false"):
            fail("INTAKE_BINDING_EXPORT_PROPERTY", where, "Canonical boolean required")
        return "boolean", value == "true"
    if kind == "Float":
        parsed = float(value)
        if not math.isfinite(parsed):
            fail("INTAKE_BINDING_EXPORT_PROPERTY", where, "Finite float required")
        return "float", parsed
    if kind == "String":
        return "string", value
    if kind == "Character":
        return "character", int(value, 10)
    if kind == "ObjectReference":
        reference, full = _parse_reference(prop, where)
        return "object", reference, full
    return None


def _build_oracle(snapshot: dict, spec: dict):
    if not isinstance(snapshot, dict) or set(snapshot) != {"planSha256", "prefabs"}:
        fail("INTAKE_BINDING_EXPORT_SNAPSHOT", "snapshot", "Exact native snapshot top-level fields required")
    if not isinstance(snapshot["planSha256"], str) or not _HASH.fullmatch(snapshot["planSha256"]):
        fail("INTAKE_BINDING_EXPORT_SNAPSHOT", "snapshot.planSha256", "Lowercase SHA-256 required")
    prefabs = snapshot["prefabs"]
    if not isinstance(prefabs, list) or len(prefabs) != len(spec["prefabs"]) or len(prefabs) > 256:
        fail("INTAKE_BINDING_EXPORT_SNAPSHOT", "snapshot.prefabs", "Exact selected Prefab set required")
    if [p.get("path") for p in prefabs] != sorted(spec["prefabs"]):
        fail("INTAKE_BINDING_EXPORT_SNAPSHOT", "snapshot.prefabs", "Native Prefab rows must match sorted selected paths")
    bindings_by_type = {(row["targetType"], row["targetAssembly"]): row for row in spec["bindings"]}
    verifications = []
    engine_objects = {}
    exclusions = []
    unsupported = []
    owner_total = 0
    total_fields = 0
    total_properties = 0
    seen_prefab_guids = set()
    seen_bindings = set()
    for prefab_index, prefab in enumerate(prefabs):
        where = f"snapshot.prefabs[{prefab_index}]"
        if set(prefab) != {"path", "guid", "owners"}:
            fail("INTAKE_BINDING_EXPORT_SNAPSHOT", where, "Exact Prefab snapshot fields required")
        if not isinstance(prefab["guid"], str) or not _GUID.fullmatch(prefab["guid"]) or prefab["guid"] in seen_prefab_guids:
            fail("INTAKE_BINDING_EXPORT_SNAPSHOT", where + ".guid", "Unique valid Prefab GUID required")
        seen_prefab_guids.add(prefab["guid"])
        owners = prefab["owners"]
        if not isinstance(owners, list) or not owners or len(owners) > MAX_OWNERS_PER_PREFAB:
            fail("INTAKE_BINDING_EXPORT_BUDGET", where + ".owners", "1..4096 serialized owners required")
        objects = []
        local_ids = set()
        for owner_index, owner in enumerate(owners):
            ow = f"{where}.owners[{owner_index}]"
            if set(owner) != {"guid", "localId", "type", "name", "properties"}:
                fail("INTAKE_BINDING_EXPORT_SNAPSHOT", ow, "Exact serialized owner identity required")
            if not isinstance(owner["guid"], str) or not _GUID.fullmatch(owner["guid"]):
                fail("INTAKE_BINDING_EXPORT_SNAPSHOT", ow + ".guid", "Lowercase owner GUID required")
            if type(owner["localId"]) is not int or owner["localId"] == 0 or owner["localId"] in local_ids:
                fail("INTAKE_BINDING_EXPORT_DUPLICATE", ow + ".localId", "Duplicate or invalid object localID in Prefab")
            local_ids.add(owner["localId"])
            if not isinstance(owner["name"], str):
                fail("INTAKE_BINDING_EXPORT_SNAPSHOT", ow + ".name", "Serialized owner name required")
            obj_type, assembly = _assembly_type(owner["type"], ow + ".type")
            props = owner["properties"]
            if not isinstance(props, list):
                fail("INTAKE_BINDING_EXPORT_SNAPSHOT", ow + ".properties", "Property array required")
            prop_paths = []
            for prop_index, prop in enumerate(props):
                pp = f"{ow}.properties[{prop_index}]"
                if not isinstance(prop, dict) or set(prop) - {"path", "type", "value", "reference"} or not {"path", "type", "value"}.issubset(prop):
                    fail("INTAKE_BINDING_EXPORT_PROPERTY", pp, "Property path/type/value and optional reference required")
                if not isinstance(prop["path"], str) or not prop["path"] or not isinstance(prop["type"], str) or not isinstance(prop["value"], str):
                    fail("INTAKE_BINDING_EXPORT_PROPERTY", pp, "Canonical property strings required")
                prop_paths.append(prop["path"])
            if len(set(prop_paths)) != len(prop_paths):
                fail("INTAKE_BINDING_EXPORT_DUPLICATE", ow + ".properties", "Duplicate serialized property path")
            total_properties += len(props)
            if total_properties > MAX_TOTAL_FIELDS:
                fail("INTAKE_BINDING_EXPORT_BUDGET", "snapshot", "Native serialized property budget exceeded")
            children = set(prop_paths)
            fields = []
            mapped_binding = bindings_by_type.get((obj_type, assembly)) if owner["type"].startswith("binding:") else None
            for prop in props:
                path = prop["path"]
                property_kind = prop["type"].split(":", 1)[0]
                if property_kind != "ObjectReference" and prop.get("reference") not in (None, _EMPTY_REFERENCE):
                    fail("INTAKE_BINDING_EXPORT_REFERENCE", ow + "." + path, "Non-ObjectReference property has unexpected identity data")
                if path == "m_EditorClassIdentifier" and mapped_binding is not None:
                    if prop["type"] != "String":
                        fail("INTAKE_BINDING_EXPORT_PROPERTY", ow + "." + path, "Normalized class identifier uses String type")
                    exclusions.append({"asset": prefab["path"], "ownerLocalId": owner["localId"], "path": path,
                                       "reason": "Unity normalizes this value during native script rebinding; target GetClass is the identity proof; do not assert a literal string"})
                    continue
                if prop["type"].startswith("Generic:"):
                    has_children = any(value.startswith(path + ".") for value in children)
                    exclusions.append({"asset": prefab["path"], "ownerLocalId": owner["localId"], "path": path,
                                       "reason": "complex parent structure is covered by serialized child leaves" if has_children else "unsupported complex parent has no expressible child leaf"})
                    if not has_children:
                        unsupported.append({"asset": prefab["path"], "ownerLocalId": owner["localId"], "path": path, "type": prop["type"], "reason": "no child scalar/ObjectReference leaf available to intake schema"})
                    continue
                converted = _scalar(prop, f"{ow}.{path}")
                if converted is None:
                    if any(value.startswith(path + ".") for value in children):
                        exclusions.append({"asset":prefab["path"],"ownerLocalId":owner["localId"],"path":path,
                                           "reason":"structured parent is represented by its serialized child leaves"})
                        continue
                    unsupported.append({"asset": prefab["path"], "ownerLocalId": owner["localId"], "path": path, "type": prop["type"], "reason": "property kind has no exact field representation in existing intake schema"})
                    continue
                kind, value = converted[0], converted[1]
                if kind == "object":
                    reference, full_ref = value, converted[2]
                    if mapped_binding is not None and path == "m_Script":
                        expected_script = (mapped_binding["targetGuid"], mapped_binding["targetLocalId"],
                                           mapped_binding["targetType"], mapped_binding["targetAssembly"])
                        observed_script = ((full_ref or {}).get("guid"), (full_ref or {}).get("localId"),
                                           (full_ref or {}).get("scriptType"), (full_ref or {}).get("scriptAssembly"))
                        if observed_script != expected_script:
                            fail("INTAKE_BINDING_EXPORT_OWNER_GUID", ow + ".m_Script", "Mapped component script identity differs from retained target")
                        seen_bindings.add(mapped_binding["targetGuid"])
                    if full_ref is not None and full_ref["guid"] in (
                            "0000000000000000e000000000000000", "0000000000000000f000000000000000"):
                        key = (full_ref["guid"], full_ref["localId"])
                        row = {"guid": full_ref["guid"], "localId": full_ref["localId"], "type": full_ref["type"],
                               "assembly": full_ref["assembly"], "name": full_ref["name"], "assetPath": full_ref["assetPath"]}
                        if key in engine_objects and engine_objects[key] != row:
                            fail("INTAKE_BINDING_EXPORT_ENGINE", path, "Built-in GUID/localID identity changed within snapshot")
                        engine_objects[key] = row
                    fields.append({"propertyPath": path, "kind": kind, "value": reference})
                else:
                    fields.append({"propertyPath": path, "kind": kind, "value": value})
            obj = {"localId": owner["localId"], "type": obj_type, "assembly": assembly,
                   "name": owner["name"], "fields": fields}
            if mapped_binding is not None and not any(field["propertyPath"] == "m_Script" for field in fields):
                fail("INTAKE_BINDING_EXPORT_OWNER_GUID", ow, "Mapped component has no m_Script ObjectReference leaf")
            objects.append(obj)
            owner_total += 1
            total_fields += len(fields)
            if owner_total > MAX_TOTAL_OWNERS or total_fields > MAX_TOTAL_FIELDS:
                fail("INTAKE_BINDING_EXPORT_BUDGET", "snapshot", "Owner or typed field budget exceeded")
        _owner_rows(objects, f"verifications[{prefab_index}].objects", total_fields=0, allow_character=True)
        verifications.append({"asset": prefab["path"], "objects": objects})
    expected_bindings = {row["targetGuid"] for row in spec["bindings"]}
    if seen_bindings != expected_bindings:
        fail("INTAKE_BINDING_EXPORT_OWNER_GUID", "snapshot", "Every declared retained script type must occur with its exact target GUID")
    engine_rows = sorted(engine_objects.values(), key=lambda row: (row["guid"], row["localId"]))
    _engine_object_rows(engine_rows)
    return ({"verifications": verifications, "engineObjects": engine_rows},
            {"ownerCount": owner_total, "typedFieldCount": total_fields, "unsupportedProperties": unsupported,
             "excludedParentProperties": exclusions, "engineObjectCount": len(engine_rows),
             "coverageStatus": "partial" if unsupported else "typed-leaf-complete-with-explicit-parent-exclusions"})


def _verify_prefab_guids(project: Path, spec: dict, snapshot: dict):
    for prefab in snapshot["prefabs"]:
        path = prefab["path"]
        meta_path = inside(project, path + ".meta")
        actual = parse_guid(read(meta_path), path)
        if actual != prefab["guid"]:
            fail("INTAKE_BINDING_EXPORT_OWNER_GUID", path, "Native snapshot Prefab GUID differs from prepared source Meta")
    if {row["path"] for row in snapshot["prefabs"]} != set(spec["prefabs"]):
        fail("INTAKE_BINDING_EXPORT_SNAPSHOT", "snapshot.prefabs", "Snapshot Prefab paths differ from selected input")


def _intake_fragments(prepared_files: dict, spec: dict, oracle: dict):
    external = []
    omissions = []
    bridge_sources = []
    for row in spec["bindings"]:
        source = BRIDGE_ROOT + "/" + Path(row["source"]).name
        bridge_sources.append(source)
        external.append({
            "source": source,
            "sourceGuid": row["targetGuid"],
            "sourceType": row["targetType"],
            "sourceAssembly": "Beaver.IntakeBindings",
            "target": row["target"],
            "targetGuid": row["targetGuid"],
            "targetType": row["targetType"],
            "targetAssembly": row["targetAssembly"],
            "targetLocalId": row["targetLocalId"],
            "targetSha256": row["targetSha256"],
            "targetMetaSha256": row["targetMetaSha256"],
            "reason": "Native serialized references were rebound in an isolated saved source copy; byte-identical retained target script identity is preserved."
        })
        omissions.append({
            "path": row["source"],
            "reason": "Original source script was not imported; selected Prefab references now use the retained target script GUID.",
            "coveredByExternalScript": source
        })
    bridge_asmdef = BRIDGE_ROOT + "/Beaver.IntakeBindings.asmdef"
    if not bridge_sources:
        fail("INTAKE_BINDING_EXPORT_BRIDGE", BRIDGE_ROOT, "At least one bridge source is required to cover its compilation boundary")
    omissions.append({
        "path": bridge_asmdef,
        "reason": "Preparation-only Bridge assembly scope; the target keeps each retained script in its existing assembly.",
        "coveredByExternalScript": bridge_sources[0]
    })
    compiler_inputs = {path for path in prepared_files
                       if path.startswith("Assets/") and Path(path).suffix.lower() in {".cs", ".asmdef", ".asmref", ".rsp"}}
    covered = set(bridge_sources) | {row["path"] for row in omissions}
    remaining = sorted(compiler_inputs - covered)
    return {
        "externalScripts": external,
        "omittedCompilerInputs": omissions,
        "spec4Fragment": oracle,
        "compilerCoverage": {
            "status": "partial" if remaining else "complete-for-declared-inputs",
            "compilerInputCount": len(compiler_inputs),
            "coveredBindingAndBridgeInputs": len(covered),
            "remainingCompilerInputs": remaining,
            "remainingCoverageRequired": bool(remaining),
            "note": "This fragment covers only the retained four-script bindings and temporary Bridge scope; owner must classify all other compiler inputs before intake."
        }
    }


def _source_origin(plan: dict):
    origin = plan.get("sourceOrigin")
    if not isinstance(origin, dict):
        fail("INTAKE_BINDING_EXPORT_ORIGIN", "plan.sourceOrigin", "Bound source-origin provenance is required")
    status = origin.get("owningStatus")
    if status not in ("verified", "unverified_diagnostic_source", "not_supplied"):
        fail("INTAKE_BINDING_EXPORT_ORIGIN", "plan.sourceOrigin.owningStatus", "Supported source ownership state required")
    snapshot_sha = origin.get("productSnapshotSha256")
    if not isinstance(snapshot_sha, str) or not _HASH.fullmatch(snapshot_sha):
        fail("INTAKE_BINDING_EXPORT_ORIGIN", "plan.sourceOrigin.productSnapshotSha256", "Source product snapshot identity required")
    if snapshot_sha != sha(encoded(plan.get("sourceFiles"))):
        fail("INTAKE_BINDING_EXPORT_ORIGIN", "plan.sourceOrigin.productSnapshotSha256", "Source product snapshot identity differs from pinned original files")
    manifest = origin.get("owningManifest")
    if manifest is not None:
        if not isinstance(manifest, dict) or not {"path", "sha256", "bytes", "claims"}.issubset(manifest):
            fail("INTAKE_BINDING_EXPORT_ORIGIN", "plan.sourceOrigin.owningManifest", "Original manifest provenance record required")
        if not isinstance(manifest["path"], str) or not isinstance(manifest["sha256"], str) or not _HASH.fullmatch(manifest["sha256"]):
            fail("INTAKE_BINDING_EXPORT_ORIGIN", "plan.sourceOrigin.owningManifest", "Original manifest path/hash invalid")
        if type(manifest["bytes"]) is not int or manifest["bytes"] < 0 or not isinstance(manifest["claims"], dict):
            fail("INTAKE_BINDING_EXPORT_ORIGIN", "plan.sourceOrigin.owningManifest", "Original manifest byte count/claims invalid")
    evidence = origin.get("evidence", [])
    if not isinstance(evidence, list):
        fail("INTAKE_BINDING_EXPORT_ORIGIN", "plan.sourceOrigin.evidence", "Evidence array required")
    for index, row in enumerate(evidence):
        if not isinstance(row, dict) or not {"path", "sha256", "bytes"}.issubset(row) or not isinstance(row["path"], str) or not _HASH.fullmatch(row["sha256"] or "") or type(row["bytes"]) is not int or row["bytes"] < 0:
            fail("INTAKE_BINDING_EXPORT_ORIGIN", f"plan.sourceOrigin.evidence[{index}]", "Pinned evidence path/hash/bytes required")
    return origin


def _verify_target_pins(plan: dict):
    target_root = safe(plan.get("targetRoot", ""))
    for row in plan["spec"]["bindings"]:
        path = inside(target_root, row["target"])
        if not path.is_file() or digest_file(path) != row["targetSha256"]:
            fail("INTAKE_BINDING_EXPORT_TARGET_DRIFT", row["target"], "Retained target script bytes changed")
        meta = inside(target_root, row["target"] + ".meta")
        if not meta.is_file() or digest_file(meta) != row["targetMetaSha256"]:
            fail("INTAKE_BINDING_EXPORT_TARGET_DRIFT", row["target"], "Retained target script metadata changed")


def _source_manifest_provenance(source_root: Path):
    rows = []
    for name in ("manifest.json", "recovery-manifest.json"):
        path = source_root / name
        if path.is_symlink():
            fail("SYMLINK_PATH", str(path), "Original manifest cannot be a symlink")
        if path.is_file():
            raw = read(path)
            original = load(raw)
            rows.append({"path": name, "sha256": sha(raw), "bytes": len(raw),
                         "claims": {key: original.get(key) for key in ("namespace", "native", "diagnostics", "source", "producer")},
                         "ownsPreparedProductFiles": False})
    return rows


def _verify_source_origin_files(origin: dict, source_root: Path, manifests: list[dict]):
    expected = origin.get("owningManifest")
    if expected is None:
        if manifests:
            fail("INTAKE_BINDING_EXPORT_ORIGIN", str(source_root), "Source manifest appeared after the plan was pinned")
    else:
        if not isinstance(expected, dict):
            fail("INTAKE_BINDING_EXPORT_ORIGIN", str(source_root), "Malformed pinned source manifest")
        expected_path = safe(expected["path"])
        if not expected_path.is_relative_to(source_root) or expected_path.name not in ("manifest.json", "recovery-manifest.json"):
            fail("INTAKE_BINDING_EXPORT_ORIGIN", str(expected_path), "Pinned source manifest must be at the source project root")
        match = next((row for row in manifests if row["path"] == expected_path.name), None)
        if match is None or match["sha256"] != expected["sha256"] or match["bytes"] != expected["bytes"]:
            fail("INTAKE_BINDING_EXPORT_ORIGIN", str(expected_path), "Source manifest bytes changed after the plan was pinned")
        if match["claims"] != expected["claims"]:
            fail("INTAKE_BINDING_EXPORT_ORIGIN", str(expected_path), "Source manifest claims differ from pinned provenance")
    for row in origin.get("evidence", []):
        evidence = safe(row["path"])
        if not evidence.is_file() or evidence.stat().st_size != row["bytes"] or digest_file(evidence) != row["sha256"]:
            fail("INTAKE_BINDING_EXPORT_ORIGIN", str(evidence), "Pinned source evidence changed")


def _candidate_inventory(candidate: Path):
    rows = []
    for path in sorted(candidate.rglob("*")):
        if path.is_symlink():
            fail("SYMLINK_PATH", str(path), "Frozen candidate cannot contain symlinks")
        if not path.is_file() or (path.name == "manifest.json" and path.parent == candidate):
            continue
        rows.append({"path": path.relative_to(candidate).as_posix(),
                     "sha256": digest_file(path), "bytes": path.stat().st_size,
                     "owner": "generated"})
    if not rows:
        fail("INTAKE_BINDING_EXPORT_INVENTORY", str(candidate), "Frozen candidate inventory cannot be empty")
    return rows


def export_prepared(stage: Path, project: Path, plan: dict, prepared_files: dict, snapshot: dict, *, output=None) -> dict:
    """Freeze an already verified private preparation copy for ordinary intake."""
    stage = safe(stage)
    project = safe(project)
    if project != stage / "UnityProject":
        fail("INTAKE_BINDING_EXPORT_PROJECT", str(project), "Only the plan-owned UnityProject clone may be exported")
    if not isinstance(plan, dict) or plan.get("contract") != PREPARATION_CONTRACT:
        fail("INTAKE_BINDING_EXPORT_PLAN", str(stage), "Exact script-binding preparation plan required")
    origin = _source_origin(plan)
    job, plan_sha = _same_plan(stage, plan)
    if job.get("mode") != "verify":
        fail("INTAKE_BINDING_EXPORT_JOB", str(stage), "Cold verification phase must be the final job mode")
    snapshot_raw, native_pins = _verify_native_snapshot_refs(stage, job, plan_sha, snapshot)
    source_files_sha, prepared_files_sha, _expected_bridge = _validate_inventory(project, plan, prepared_files)
    _verify_target_pins(plan)
    spec = plan["spec"]
    oracle_fragment, coverage = _build_oracle(snapshot, spec)
    _verify_prefab_guids(project, spec, snapshot)
    intake_fragments = _intake_fragments(prepared_files, spec, oracle_fragment)
    source_root = safe(plan["sourceRoot"])
    origin_manifests = _source_manifest_provenance(source_root)
    _verify_source_origin_files(origin, source_root, origin_manifests)
    origin_manifest = origin.get("owningManifest")
    source_claims = origin_manifest.get("claims", {}) if isinstance(origin_manifest, dict) else {}
    original_native = source_claims.get("native")
    if original_native in ("partial", "unknown"):
        output_native = original_native
    elif origin.get("owningStatus") == "not_supplied":
        output_native = "unknown"
    elif origin.get("owningStatus") == "unverified_diagnostic_source":
        output_native = "partial"
    else:
        output_native = original_native if origin.get("owningStatus") == "verified" and isinstance(original_native, str) else "unknown"
    prep_diagnostics = []
    if origin.get("owningStatus") != "verified" or original_native in ("partial", "unknown"):
        prep_diagnostics.append({
            "status": output_native,
            "sourceOwningStatus": origin.get("owningStatus"),
            "sourceNativeStatus": original_native,
            "sourceDiagnostic": origin.get("diagnostic"),
            "reason": "Native script rebinding preparation does not promote original source/static acceptance."
        })

    export_root = stage if output is None else new_output(output, [stage, project, source_root, safe(plan["targetRoot"])])
    candidate_path = export_root / "frozen-candidate"
    if safe(candidate_path).exists():
        fail("OUTPUT_EXISTS", str(candidate_path), "Fresh frozen candidate directory required")
    candidate = new_output(candidate_path, [project, source_root, safe(plan["targetRoot"])])
    for path, row in sorted(prepared_files.items()):
        copy_verified(inside(project, path), candidate / path, row["sha256"], row["bytes"])

    # Keep oracle and provenance inside the frozen candidate so moving the
    # directory alone cannot detach its script-binding evidence.
    analysis = candidate / "Analysis" / "BeaverIntakeBindings"
    snapshot_record = _write_compact(analysis / "serialized-oracle.json", snapshot,
                                     max_bytes=MAX_SNAPSHOT_BYTES, max_nodes=MAX_SNAPSHOT_NODES)
    fragment_record = _write_compact(analysis / "intake-spec-fragments.json", intake_fragments,
                                     max_bytes=MAX_SNAPSHOT_BYTES, max_nodes=MAX_SNAPSHOT_NODES)
    coverage_record = _write_compact(analysis / "typed-coverage.json", coverage,
                                     max_bytes=MAX_SNAPSHOT_BYTES, max_nodes=MAX_SNAPSHOT_NODES)
    origin_record = _write_compact(analysis / "source-origin.json", dict(origin=origin, manifestsFound=origin_manifests),
                                   max_bytes=8*1024*1024, max_nodes=MAX_SNAPSHOT_NODES)
    lineage = {
        "schemaVersion": 1,
        "contract": CONTRACT,
        "status": "prepared-candidate-frozen",
        "planSha256": plan_sha,
        "source": {
            "root": str(source_root),
            "sourceProductSnapshotSha256": origin["productSnapshotSha256"],
            "sourceFilesSha256": source_files_sha,
            "owningStatus": origin["owningStatus"],
            "owningManifest": None if origin_manifest is None else {k:origin_manifest[k] for k in ('path','sha256','bytes')},
            "sourceOriginSidecar": origin_record
        },
        "retainedTarget": {"root": str(plan["targetRoot"]), "wrote": False,
                           "scriptPins": [{"path": row["target"], "guid": row["targetGuid"], "sha256": row["targetSha256"],
                                           "metaSha256": row["targetMetaSha256"], "type": row["targetType"],
                                           "assembly": row["targetAssembly"], "localId": row["targetLocalId"]}
                                          for row in spec["bindings"]]},
        "savedProduct": {"preparedFilesSha256": prepared_files_sha, "fileCount": len(prepared_files),
                         "candidateRoot": str(candidate),
                         "owningManifestOwnsOnlyPreparedProductFiles": True},
        "rebind": {"nativeSnapshots": native_pins,
                   "passedSnapshotFileSha256": sha(snapshot_raw),
                   "sourceToRetainedBindings": [{"source": row["source"], "sourceGuid": row["sourceGuid"],
                                                 "sourceSha256": row["sourceSha256"], "sourceMetaSha256": row["sourceMetaSha256"],
                                                 "target": row["target"], "targetGuid": row["targetGuid"],
                                                 "targetSha256": row["targetSha256"], "targetMetaSha256": row["targetMetaSha256"],
                                                 "type": row["targetType"], "sourceAssembly": row["sourceAssembly"],
                                                 "targetAssembly": row["targetAssembly"], "targetLocalId": row["targetLocalId"]}
                                                for row in spec["bindings"]]},
        "selectedPrefabs": list(spec["prefabs"]),
        "typedCoverage": {key: value for key, value in coverage.items()
                          if key not in ("unsupportedProperties", "excludedParentProperties")},
        "compilerCoverage": intake_fragments["compilerCoverage"],
        "sourceState": {"native": output_native, "diagnosticsSha256": sha(_compact(source_claims.get("diagnostics", []))),
                        "preparationDoesNotPromoteSourceAcceptance": True},
        "sidecars": {"serializedOracle": snapshot_record, "intakeSpecFragments": fragment_record,
                     "typedCoverage": coverage_record,"sourceOrigin":origin_record},
        "limits": ["No formal target changes or intake apply.",
                   "The source owning manifest, if present, is provenance only and does not claim ownership of prepared native files.",
                   "Bridge compiler inputs are not all target compiler coverage.",
                   "Preparation does not prove static-page, visual, player, or business acceptance."]
    }
    lineage_record = _write_compact(analysis / "lineage.json", lineage, max_bytes=MAX_REPORT_BYTES)
    lineage_relative = "Analysis/BeaverIntakeBindings/lineage.json"
    product_files = _candidate_inventory(candidate)
    manifest = {
        "schemaVersion": 1,
        "targetProfile": TARGET_PROFILE,
        "namespace": "beaver-native-rebound/" + prepared_files_sha,
        "projectLayout": PROJECT_LAYOUT,
        "scopeMode": "whole-input",
        "producer": {"name": "beaver", "version": __version__, "implementationSha256": identity()},
        "files": product_files,
        "native": output_native,
        "diagnostics": source_claims.get("diagnostics", []),
        "preparationDiagnostics": prep_diagnostics,
        "preparation": {
            "contract": CONTRACT,
            "status": "verified-preparation-only",
            "planSha256": plan_sha,
            "sourceProductSnapshotSha256": origin["productSnapshotSha256"],
            "originalSourceFilesSha256": source_files_sha,
            "preparedProductFilesSha256": prepared_files_sha,
            "nativeSnapshotSourceSha256": native_pins[1]["sha256"],
            "nativeSnapshotSha256": sha(snapshot_raw),
            "sourceOwningStatus": origin["owningStatus"],
            "lineagePath": lineage_relative,
            "lineageSha256": lineage_record["sha256"],
            "adoption": "not_run",
            "staticPresentation": "inherited-source-state-only",
            "visual": "not_run",
            "business": "not_run"
        }
    }
    for key in ("staticPresentation", "visibleEdits", "player", "business"):
        if key in source_claims:
            manifest[key] = source_claims[key]
    write_json(candidate / "manifest.json", manifest)
    root, parsed_manifest, files, manifest_sha = candidate_snapshot(candidate)
    verify_candidate(root, files)
    if files.get(lineage_relative, {}).get("sha256") != manifest["preparation"]["lineageSha256"]:
        fail("INTAKE_BINDING_EXPORT_LINEAGE", lineage_relative, "Manifest lineage pointer does not bind its owned sidecar")
    receipt = {
        "status": "exported",
        "contract": CONTRACT,
        "planSha256": plan_sha,
        "candidate": str(candidate),
        "candidateManifestSha256": manifest_sha,
        "candidateFileCount": len(files),
        "namespace": parsed_manifest["namespace"],
        "nativePreparation": "verified-two-gates",
        "targetWrites": False,
        "intakeApply": "not_run",
        "sourceNative": output_native,
        "typedCoverageStatus": coverage["coverageStatus"],
        "remainingCompilerCoverage": intake_fragments["compilerCoverage"]["status"],
        "lineage": str(candidate / lineage_relative),
        "oracle": snapshot_record["path"],
        "intakeSpecFragments": fragment_record["path"],
        "typedCoverage": coverage_record["path"],
        "lineageSha256": lineage_record["sha256"]
    }
    write_json(export_root / "export-receipt.json", receipt)
    return receipt
