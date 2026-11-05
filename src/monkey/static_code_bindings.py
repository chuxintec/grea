"""Source-proven, inert Unity script types and instance-addressed binding plans.

This optional stage reuses the static-field serializer and Editor binder. It
does not translate business methods or promote draft C# to compiled source.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
from pathlib import Path

from . import prefab_static_carriers as carriers
from .io import inside, write_json

SCHEMA = "monkey-static-code-bindings/1"
_RF = re.compile(rb'''cc\._RF\.push\(\s*\{\s*exports\s*:\s*\{\s*\}\s*\}\s*,\s*(["'])([^"']+)\1\s*,\s*(["'])([^"']+)\3\s*\)''')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _encode(value):
    if value is None:
        return {"kind": "null", "value": None}
    if type(value) in (bool, int, float, str):
        return {"kind": {bool: "bool", int: "float", float: "float", str: "string"}[type(value)], "value": value}
    if isinstance(value, list):
        return {"kind": "array", "value": [_encode(v) for v in value]}
    if isinstance(value, dict):
        return {"kind": "object", "value": {k: _encode(v) for k, v in value.items()}}
    raise ValueError("Unsupported declaration value")


def _alias_gaps(fields):
    gaps = []
    for f in fields:
        declared = f.get("sourceDeclaredType", "").strip()
        scalar = declared[1:-1].strip() if declared.startswith("[") and declared.endswith("]") else declared
        if scalar and not scalar.startswith(("cc.", "sp.", carriers._STATIC_TYPE_PREFIX)) and scalar not in carriers._CREATOR_PRIMITIVES:
            gaps.append("source_declared_type_alias_unresolved:" + f.get("sourceFieldName", f.get("name", "")) + ":" + declared)
    return gaps


def merge_declarations(component, declaration):
    """Merge proven inherited defaults before exact serialized overrides."""
    result = copy.deepcopy(component)
    snapshot = result["staticFieldSnapshot"]
    types = {p["name"]: p["types"][0] for p in declaration.get("propertyTypes", []) if len(p.get("types", [])) == 1}
    fields = {f["name"]: dict(name=f["name"], **_encode(f["value"]), declarationEvidence=f)
              for f in declaration["fields"]}
    for f in snapshot["fields"]:
        fields[f["name"]] = dict(fields.get(f["name"], {}), **f, serializedOverride=True)
    for name, f in fields.items():
        if name in types:
            f["sourceDeclaredType"] = types[name]
    snapshot["fields"] = [fields[n] for n in sorted(fields)]
    snapshot["declarationDefaults"] = "partial" if declaration["gaps"] else "verified"
    snapshot["gaps"] = [g for g in snapshot["gaps"] if g != "source_declaration_defaults_not_verified"]
    snapshot["gaps"].extend("declaration:" + json.dumps(g, sort_keys=True) for g in declaration["gaps"])
    snapshot["gaps"].extend(_alias_gaps(snapshot["fields"]))
    return result


def prepare(ir, bindings, modules, source_files, declarations, output):
    """Keep every supplied mapping row; refuse ambiguous identity per instance.

    ``source_files`` maps sourceSnapshotPath to original immutable bytes.
    ``declarations`` maps the same path to {sha256, result}, from the existing
    pinned static declaration parser. The caller retains those full receipts.
    Native success can only be joined from a later saved and cold Editor run.
    """
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Static code output must be new")
    if not isinstance(bindings, list) or not bindings:
        raise ValueError("Expected a nonempty exact binding denominator")
    components = {}
    for c in ir["components"]:
        if c["sourceId"] in components:
            raise ValueError("Duplicate IR component identity")
        components[c["sourceId"]] = c
    nodes = {n["sourceId"] for n in ir["nodes"]}
    by_region = {}
    for m in modules:
        by_region.setdefault(m.get("sourceId"), []).append(m)
    file_hashes = {path: _sha(raw) for path, raw in source_files.items()}
    rows, scripts, seen = [], {}, set()
    for binding in bindings:
        row = dict(binding, disposition="blocked", nativeStatus="not_executed", reasons=[])
        rows.append(row)
        sid = binding.get("sourceComponent")
        if not isinstance(sid, str) or sid in seen:
            raise ValueError("Duplicate or missing input sourceComponent")
        seen.add(sid)
        try:
            if binding.get("evidence") != "exact_literal_script_identity":
                raise ValueError("binding_identity_unproven")
            c = components.get(sid)
            if c is None or c["node"] != binding.get("sourceNode") or c["node"] not in nodes:
                raise ValueError("source_node_mismatch_or_missing")
            if sid.split("#")[0] != binding.get("sourceAsset") or c["node"].split("#")[0] != binding["sourceAsset"]:
                raise ValueError("source_asset_mismatch")
            matches = by_region.get(binding.get("codeRegion"), [])
            if len(matches) != 1:
                raise ValueError("source_module_missing_or_ambiguous")
            m = matches[0]
            file = m["sourceSnapshotPath"]
            raw = source_files[file]
            span = m["source_bytes"]
            segment = raw[span["start"]:span["end"]]
            literal = _RF.match(segment)
            if _sha(segment) != m["sha256"] or not literal:
                raise ValueError("source_module_bytes_or_literal_mismatch")
            if literal.group(2).decode() != c["type"] or literal.group(4).decode() != m["name"]:
                raise ValueError("source_script_type_mismatch")
            if not binding["codeRegion"].endswith("#" + m["name"] + "@" + str(span["start"])):
                raise ValueError("source_region_locator_mismatch")
            record = declarations[file]
            if record["sha256"] != file_hashes[file]:
                raise ValueError("declaration_source_pin_mismatch")
            declaration = record["result"]["components"].get(c["type"])
            if declaration is None or declaration.get("sourceSha256") != m["sha256"]:
                raise ValueError("declaration_module_identity_missing")
            snapshot = c.get("staticFieldSnapshot")
            if not snapshot or snapshot.get("sourceId") != sid or snapshot.get("node") != c["node"] or snapshot.get("sourceType") != c["type"]:
                raise ValueError("source_snapshot_identity_mismatch")
            if len({f["name"] for f in snapshot["fields"]}) != len(snapshot["fields"]):
                raise ValueError("source_snapshot_field_conflict")
            enriched = merge_declarations(c, declaration)
            if not enriched["staticFieldSnapshot"]["fields"]:
                raise ValueError("no_proven_static_fields;empty_class_not_coverage")
            # Existing carrier generation owns all field/value encoding. The
            # named script identity additionally includes exact code region.
            prepared = carriers.prepare([enriched], "unity", "Monkey.StaticFields.Code", output / "carrier-input")
            spec = prepared["bindings"][sid]
            schema = carriers._schema(c["type"], spec["fields"])
            type_key = _sha(json.dumps({"region": binding["codeRegion"], "schema": schema}, sort_keys=True).encode())
            class_name = carriers._slug(m["name"])
            namespace = "Monkey.StaticFields.Code.N" + type_key[:24]
            path = "Assets/Game/Scripts/Presentation/Recovered/StaticFields/Code/" + type_key[:24] + "/" + class_name + ".cs"
            code = carriers._unity_script(namespace, class_name, spec["fields"]).encode()
            identity = carriers._script_identity("unity", namespace, path)
            spec.update(typeName=namespace + "." + class_name, scriptGuid=identity,
                        scriptPath=path, scriptSha256=_sha(code))
            if path in scripts and scripts[path]["sha256"] != _sha(code):
                raise ValueError("same_type_schema_has_different_generated_bytes")
            scripts[path] = {"target": path, "sha256": _sha(code), "identity": identity, "code": code}
            row.update(disposition="prepared", spec=spec, sourceType=c["type"], targetType=spec["typeName"],
                       proof={"sourceFile": file, "sourceFileSha256": file_hashes[file], "moduleSha256": m["sha256"],
                              "sourceBytes": span, "draft": m.get("draft"),
                              "declarationSha256": _sha(json.dumps(declaration, sort_keys=True).encode())},
                       reasons=list(spec["gaps"]))
        except (KeyError, TypeError, ValueError, carriers.StaticCarrierError) as error:
            row["reasons"] = [str(error)]
    output.mkdir(parents=True, exist_ok=True)
    emitted = []
    for path, script in sorted(scripts.items()):
        destination = inside(output, "generated/" + path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(script.pop("code"))
        Path(str(destination) + ".meta").write_text("fileFormatVersion: 2\nguid: " + script["identity"] + "\n")
        emitted.append(script)
    report = {"schemaVersion": SCHEMA, "sourceManifestSha256": ir["sourceManifestSha256"],
              "behaviorExecuted": False, "dynamicBehaviorComplete": False,
              "mappingCount": len(rows), "sourceModuleCount": len({b["codeRegion"] for b in bindings}),
              "targetTypeCount": len(emitted), "scripts": emitted, "mappings": rows}
    write_json(output / "bindings.json", report)
    return report


def stage_candidate(source, prepared, output, *, stage_id, code_regions=None, compile_all_types=False):
    """Clone a saved candidate; install only generated static types and helper.

    Existing recovery inputs and project Assets remain immutable. The optional
    new helper is a partial Editor entry point, with no shared CLI registration.
    """
    source, prepared, output = Path(source).resolve(), Path(prepared).resolve(), Path(output).resolve()
    if output.exists() or output == source or source in output.parents or output in source.parents:
        raise ValueError("Expected a new independent candidate directory")
    report = json.loads((prepared / "bindings.json").read_bytes())
    plan_path = "Assets/Game/Editor/Conversion/import-plan.json"
    plan = json.loads((source / plan_path).read_bytes())
    known = {c["sourceId"] for c in plan["components"]}
    mappings = [r for r in report["mappings"] if r["disposition"] == "prepared" and r["sourceComponent"] in known
                and (code_regions is None or r["codeRegion"] in code_regions)]
    if not mappings:
        raise ValueError("No prepared instances in the candidate")
    source_readback = source / "Analysis/Readback/source-prefabs-readback.json"
    saved_rows = json.loads(source_readback.read_bytes())["sourcePrefabs"]
    targets, skipped = [], []
    selected_nodes = {r["sourceNode"] for r in mappings}
    eligible_nodes = set()
    for prefab in plan["sourcePrefabs"]:
        if not selected_nodes.intersection(prefab["nodes"]):
            continue
        path = inside(source, prefab["path"])
        matches = [r for r in saved_rows if r.get("sourceId") == prefab["sourceId"] and r.get("path") == prefab["path"]]
        if not path.is_file() or not Path(str(path) + ".meta").is_file() or len(matches) != 1 or matches[0].get("savedReloaded") is not True:
            skipped.append(dict(sourceId=prefab["sourceId"], path=prefab["path"], reason="no_saved_native_prefab"))
            continue
        guid = re.search(r"(?m)^guid: ([0-9a-f]{32})$", Path(str(path) + ".meta").read_text()).group(1)
        if matches[0].get("guid") != guid:
            raise ValueError("Source saved Prefab GUID differs from original readback")
        targets.append(dict(sourceId=prefab["sourceId"], path=prefab["path"], guid=guid, sha256=_sha(path.read_bytes())))
        eligible_nodes.update(prefab["nodes"])
    mappings = [r for r in mappings if r["sourceNode"] in eligible_nodes]
    if not mappings:
        raise ValueError("No source-proven saved Prefabs for prepared mappings")
    # Saved native candidate clones never borrow another project's Library.
    shutil.copytree(source, output, ignore=shutil.ignore_patterns("Library", "Temp", "Logs", "obj", ".git"))
    paths = {r["spec"]["scriptPath"] for r in mappings}
    scripts = [s for s in report["scripts"] if compile_all_types or s["target"] in paths]
    for s in scripts:
        raw = inside(prepared, "generated/" + s["target"]).read_bytes()
        if _sha(raw) != s["sha256"]:
            raise ValueError("Generated source hash mismatch")
        dest = inside(output, s["target"])
        if dest.exists() or Path(str(dest) + ".meta").exists():
            raise ValueError("Refusing existing script ownership")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        shutil.copyfile(inside(prepared, "generated/" + s["target"] + ".meta"), Path(str(dest) + ".meta"))
    helper = Path(__file__).with_name("targets") / "UnityStaticCodeBindings.cs"
    helper_target = output / "Assets/Game/Editor/Conversion/UnityStaticCodeBindings.cs"
    if helper_target.exists():
        raise ValueError("Refusing existing Editor helper")
    shutil.copyfile(helper, helper_target)
    request = {"schemaVersion": "monkey-static-code-bindings-request/1", "stageId": stage_id,
               "planPath": plan_path, "planSha256": _sha((source / plan_path).read_bytes()),
               "bindingsPath": "Analysis/StaticCodeBindings/bindings.json",
               "bindingsSha256": _sha((prepared / "bindings.json").read_bytes()),
               "mappings": mappings, "prefabs": targets, "scripts": scripts, "skippedPrefabs": skipped}
    write_json(output / "Analysis/StaticCodeBindings/request.json", request)
    shutil.copyfile(prepared / "bindings.json", output / request["bindingsPath"])
    write_json(output / "Analysis/StaticCodeBindings/lineage.json", {
        "sourceCandidate": str(source), "prepared": str(prepared), "stageId": stage_id,
        "helperSha256": _sha(helper.read_bytes()), "sourceBehaviorExecuted": False})
    return request


def _compatible_catalog(older, current):
    """Only permit added unresolved-alias diagnostics over identical evidence."""
    if older["sourceManifestSha256"] != current["sourceManifestSha256"] or older["scripts"] != current["scripts"]:
        return False
    a = {r["sourceComponent"]: r for r in older["mappings"]}
    b = {r["sourceComponent"]: r for r in current["mappings"]}
    if a.keys() != b.keys() or len(a) != len(older["mappings"]) or len(b) != len(current["mappings"]):
        return False
    for sid in a:
        left, right = copy.deepcopy(a[sid]), copy.deepcopy(b[sid])
        for row in (left, right):
            row.pop("reasons", None)
        if "spec" in left and "spec" in right:
            old_gaps, new_gaps = set(left["spec"].pop("gaps")), set(right["spec"].pop("gaps"))
            if not old_gaps.issubset(new_gaps) or any(not g.startswith("source_declared_type_alias_unresolved:") for g in new_gaps - old_gaps):
                return False
        if left != right:
            return False
    return True


def _selected_mapping_ids(request, plan):
    nodes = set()
    for target in request["prefabs"]:
        matches = [p for p in plan["sourcePrefabs"] if p["sourceId"] == target["sourceId"] and p["path"] == target["path"]]
        if len(matches) != 1:
            raise ValueError("Native request Prefab scope differs from the source plan")
        nodes.update(matches[0]["nodes"])
    return {r["sourceComponent"] for r in request["mappings"] if r["sourceNode"] in nodes}


def _native_closure(request, apply, cold, plan, candidate):
    """Join both file lists and both instance lists to the requested disk scope.

    Failures stay attached to their own Prefab/instance. Extra receipt rows are
    diagnostics, never an alternative denominator for the requested rows.
    """
    targets, expected, gaps, blocks = {}, {}, {}, {}
    issues = []
    mappings = {r["sourceComponent"]: r for r in request["mappings"]}
    def gap(path, reason):
        if reason not in gaps.setdefault(path, []):
            gaps[path].append(reason)
    for target in request["prefabs"]:
        path = target["path"]
        if path in targets:
            gap(path, "request_prefab_duplicate")
        targets[path] = target
        specs = [p for p in plan["sourcePrefabs"] if p["sourceId"] == target["sourceId"] and p["path"] == path]
        if len(specs) != 1:
            gap(path, "request_prefab_plan_scope_mismatch")
            continue
        nodes = set(specs[0]["nodes"])
        for row in request["mappings"]:
            if row["sourceNode"] in nodes:
                expected[(row["sourceComponent"], path)] = row
    for phase, receipt in (("apply", apply), ("cold", cold)):
        by_path = {}
        for row in receipt["prefabs"]:
            path = row.get("path")
            by_path.setdefault(path, []).append(row)
            if path not in targets:
                issues.append(dict(code=phase + "_prefab_unrequested", prefabPath=path))
        for path, target in targets.items():
            rows = by_path.get(path, [])
            if len(rows) != 1:
                gap(path, phase + "_prefab_missing_or_duplicate")
            elif rows[0].get("sourceId") != target["sourceId"] or rows[0].get("guid") != target["guid"]:
                gap(path, phase + "_prefab_identity_mismatch")
    for path, target in targets.items():
        saved = [r for r in apply["prefabs"] if r.get("path") == path]
        reopened = [r for r in cold["prefabs"] if r.get("path") == path]
        if len(saved) == len(reopened) == 1 and saved[0].get("sha256") != reopened[0].get("sha256"):
            gap(path, "apply_cold_prefab_hash_mismatch")
        try:
            file = inside(candidate, path)
            raw = file.read_bytes()
            metadata = Path(str(file) + ".meta").read_text()
            if not re.search(r"(?m)^guid: " + re.escape(target["guid"]) + r"$", metadata):
                gap(path, "disk_prefab_guid_mismatch")
            for phase, rows in (("apply", saved), ("cold", reopened)):
                if len(rows) == 1 and _sha(raw) != rows[0].get("sha256"):
                    gap(path, phase + "_disk_prefab_hash_mismatch")
            text = raw.decode("utf-8", "strict")
            physical = {}
            for match in re.finditer(r"(?ms)^--- !u!(\d+) &(-?\d+)(?: stripped)?\s*\n(.*?)(?=^--- !u!|\Z)", text):
                identity = int(match.group(2))
                if identity in physical:
                    gap(path, "disk_duplicate_local_file_id")
                physical[identity] = (int(match.group(1)), match.group(3))
            blocks[path] = physical
        except (OSError, UnicodeError, ValueError) as error:
            gap(path, "disk_prefab_unavailable:" + type(error).__name__)
    indexed = {}
    for phase, receipt in (("apply", apply), ("cold", cold)):
        observed = {}
        for row in receipt["observations"]:
            key = (row.get("sourceComponent"), row.get("prefabPath"))
            observed.setdefault(key, []).append(row)
            if key not in expected:
                issues.append(dict(code=phase + "_instance_unrequested", sourceComponent=key[0], prefabPath=key[1]))
        indexed[phase] = observed
    rejected = {}
    for key, mapping in expected.items():
        sid, path = key
        failures = list(gaps.get(path, []))
        target = targets[path]
        for phase in ("apply", "cold"):
            rows = indexed[phase].get(key, [])
            if len(rows) != 1:
                failures.append(phase + "_instance_missing_or_duplicate")
                continue
            row = rows[0]
            if row.get("sourceNode") != mapping["sourceNode"] or row.get("sourceAsset") != mapping["sourceAsset"]:
                failures.append(phase + "_instance_source_owner_mismatch")
            if row.get("componentGuid") != target["guid"] or row.get("nodeGuid") != target["guid"]:
                failures.append(phase + "_instance_prefab_guid_mismatch")
            physical = blocks.get(path, {})
            component = physical.get(row.get("componentLocalId"))
            node = physical.get(row.get("nodeLocalId"))
            if component is None or component[0] != 114 or node is None or node[0] != 1:
                failures.append(phase + "_instance_not_on_disk")
                continue
            body = component[1]
            owner = re.search(r"(?m)^  m_GameObject: \{fileID: (-?\d+)\}", body)
            script = re.search(r"(?m)^  m_Script: \{fileID: 11500000, guid: ([0-9a-f]{32}), type: 3\}", body)
            declared = re.search(r"(?m)^  m_EditorClassIdentifier: (.*)$", body)
            enabled = re.search(r"(?m)^  m_Enabled: ([01])$", body)
            marker = re.search(r"(?m)^  __monkeySourceId: (.*)$", body)
            source_id = marker.group(1).strip() if marker else None
            if source_id and source_id.startswith('"'):
                try:
                    source_id = json.loads(source_id)
                except ValueError:
                    source_id = None
            if not owner or int(owner.group(1)) != row.get("nodeLocalId"):
                failures.append(phase + "_instance_disk_node_mismatch")
            if not script or script.group(1) != mapping["spec"]["scriptGuid"] or source_id != sid:
                failures.append(phase + "_instance_disk_script_or_source_mismatch")
            if not declared or declared.group(1).strip() != str(row.get("assembly")) + "::" + mapping["spec"]["typeName"]:
                failures.append(phase + "_instance_disk_type_or_assembly_mismatch")
            if not enabled or enabled.group(1) != "0":
                failures.append(phase + "_instance_disk_behavior_not_disabled")
        rejected[key] = sorted(set(failures))
    for path, reasons in gaps.items():
        issues.extend(dict(code=reason, prefabPath=path) for reason in reasons)
    for (sid, path), reasons in rejected.items():
        issues.extend(dict(code=reason, sourceComponent=sid, prefabPath=path) for reason in reasons if reason not in gaps.get(path, []))
    return expected, indexed, rejected, issues


def record_destinations(prepared, candidates, output, *, compatible_preparations=()):
    """Join cold evidence without changing the original mapping denominator."""
    prepared = Path(prepared).resolve()
    raw = (prepared / "bindings.json").read_bytes()
    report = json.loads(raw)
    accepted = {_sha(raw): report}
    compatibility = []
    for older_path in compatible_preparations:
        older_raw = (Path(older_path).resolve() / "bindings.json").read_bytes()
        older = json.loads(older_raw)
        if not _compatible_catalog(older, report):
            raise ValueError("Compatible preparation changed source evidence, fields, scripts or non-alias gaps")
        accepted[_sha(older_raw)] = older
        compatibility.append(dict(olderSha256=_sha(older_raw), currentSha256=_sha(raw),
                                  rule="identical_source_fields_scripts_only_added_alias_diagnostics"))
    observed, attempted, unselected = {}, {}, set()
    stages = []
    for candidate in candidates:
        candidate = Path(candidate).resolve()
        folder = candidate / "Analysis/StaticCodeBindings"
        request_raw = (folder / "request.json").read_bytes()
        request = json.loads(request_raw)
        apply = json.loads((folder / "apply.json").read_bytes())
        cold = json.loads((folder / "cold.json").read_bytes())
        candidate_pin = request["bindingsSha256"]
        if candidate_pin not in accepted or _sha((folder / "bindings.json").read_bytes()) != candidate_pin:
            raise ValueError("Native stage uses a different source mapping report")
        if apply["requestSha256"] != _sha(request_raw) or cold["requestSha256"] != _sha(request_raw):
            raise ValueError("Native receipt request hash mismatch")
        plan_raw = inside(candidate, request["planPath"]).read_bytes()
        if _sha(plan_raw) != request["planSha256"]:
            raise ValueError("Source plan bytes changed after native execution")
        selected = _selected_mapping_ids(request, json.loads(plan_raw))
        unselected.update(r["sourceComponent"] for r in request["mappings"] if r["sourceComponent"] not in selected)
        for script in request["scripts"]:
            path = inside(candidate, script["target"])
            metadata = Path(str(path) + ".meta").read_text()
            if _sha(path.read_bytes()) != script["sha256"] or not re.search(r"(?m)^guid: " + re.escape(script["identity"]) + r"$", metadata):
                raise ValueError("Generated script bytes or GUID changed after native execution")
        requested = {r["sourceComponent"] for r in request["mappings"]}
        if len(requested) != len(request["mappings"]):
            raise ValueError("Duplicate native request mapping")
        source_rows = {r["sourceComponent"]: r for r in report["mappings"]}
        original_rows = {r["sourceComponent"]: r for r in accepted[candidate_pin]["mappings"]}
        for r in request["mappings"]:
            if r != original_rows.get(r["sourceComponent"]):
                raise ValueError("Native request changed a generated source mapping")
        expected, receipts, closure_gaps, contract_issues = _native_closure(request, apply, cold, json.loads(plan_raw), candidate)
        stage = {"candidate": str(candidate), "stageId": request["stageId"], "requestSha256": _sha(request_raw),
                 "bindingsSha256": candidate_pin,
                 "applySha256": _sha((folder / "apply.json").read_bytes()), "coldSha256": _sha((folder / "cold.json").read_bytes()),
                 "applyErrors": apply["errors"], "coldErrors": cold["errors"],
                 "evidenceContractGaps": contract_issues}
        stages.append(stage)
        for sid in selected:
            attempted.setdefault(sid, []).append(stage)
        for (sid, prefab_path), mapping in expected.items():
            instance_key = (sid, prefab_path)
            cold_rows = receipts["cold"].get(instance_key, [])
            saved_rows = receipts["apply"].get(instance_key, [])
            native = cold_rows[0] if cold_rows else dict(sourceComponent=sid, prefabPath=prefab_path,
                sourceNode=mapping["sourceNode"], sourceAsset=mapping["sourceAsset"], readback=None)
            spec = source_rows[sid]["spec"]
            before = saved_rows[0] if saved_rows else {}
            read = native.get("readback") or {}
            identity = all(native.get(k) == before.get(k) and native.get(k) not in (None, "", 0)
                           for k in ("nodeGuid", "nodeLocalId", "componentGuid", "componentLocalId", "fullType", "assembly", "scriptGuid"))
            exact = (native.get("sourceNode") == source_rows[sid]["sourceNode"] and
                     native.get("fullType") == spec["typeName"] and native.get("scriptGuid") == spec["scriptGuid"] and
                     read.get("sourceId") == sid and read.get("typeName") == spec["typeName"] and
                     read.get("nativeSourceId") == sid and read.get("nativeScriptGuid") == spec["scriptGuid"])
            verified = all(native.get(k) is True for k in ("ownerVerified", "persistent", "identityStable"))
            verified = verified and identity and exact and not native.get("error")
            verified = verified and all(read.get(k) is True for k in ("fieldsVerified", "nativeIdentityVerified", "nativeComplete"))
            verified = verified and not read.get("gaps") and read.get("enabled") is False and read.get("dynamicBehaviorComplete") is False
            # Older carrier specs allowed a generic Object container for an
            # unresolved source decorator alias. Keep the saved pointer, but
            # never promote that missing source type proof to full success.
            alias_gaps = _alias_gaps(spec["fields"])
            verified = verified and not alias_gaps
            prefab_sources = {r["sourceComponent"] for r in request["mappings"] if r["sourceAsset"] == source_rows[sid]["sourceAsset"]}
            controls = [c for c in apply["controls"] if c["sourceComponent"] in prefab_sources]
            verified = verified and bool(controls) and all(c["rejected"] is True for c in controls)
            # The native producer compares actual values against the source
            # spec; the consumer also checks scalar/array readback values.
            actual = {f["fieldName"]: f for f in read.get("fields", [])}
            if len(actual) != len(spec["fields"]) or len(actual) != len(read.get("fields", [])):
                verified = False
            for field in spec["fields"]:
                value = actual.get(field["fieldName"], {})
                key = {"bool": "boolValue", "double": "numberValue", "string": "stringValue",
                       "bool[]": "boolValues", "double[]": "numberValues", "string[]": "stringValues"}.get(field["storageType"])
                expected_value = field.get("snapshotJson") if key == "stringValue" and field.get("mode") == "snapshot-json" else field.get(key)
                if key and value.get(key) != expected_value:
                    verified = False
                if field["storageType"] == "UnityEngine.Object" and value.get("referenceVerified") is not True:
                    verified = False
                if field["storageType"] == "UnityEngine.Object[]" and value.get("referencesVerified") is not True:
                    verified = False
            disposition = "blocked" if closure_gaps[instance_key] else "success" if verified else "partial"
            evidence = {k: v for k, v in stage.items() if k != "evidenceContractGaps"}
            observed.setdefault(sid, []).append(dict(native, evidence=evidence, consumerGaps=alias_gaps + closure_gaps[instance_key],
                evidenceClosureVerified=not closure_gaps[instance_key], disposition=disposition))
    rows = []
    for original in report["mappings"]:
        row = copy.deepcopy(original)
        destinations = observed.get(row["sourceComponent"], [])
        if destinations:
            row["disposition"] = "blocked" if any(d["disposition"] == "blocked" for d in destinations) else "success" if all(d["disposition"] == "success" for d in destinations) else "partial"
            row["nativeStatus"] = "evidence_rejected" if row["disposition"] == "blocked" else "saved_and_cold_reopened"
        elif row["sourceComponent"] in attempted:
            row["disposition"] = "blocked"
            row["nativeStatus"] = "native_attempt_failed"
            row["attempts"] = attempted[row["sourceComponent"]]
        elif row["disposition"] == "prepared":
            row["disposition"] = "not_executed"
            if row["sourceComponent"] in unselected:
                row["nativeStatus"] = "not_selected_by_prefab_scope"
                row["reasons"].append("source_node_outside_requested_prefab_scope")
        row["destinations"] = destinations
        rows.append(row)
    from collections import Counter
    ledger = {"schemaVersion": "monkey-static-code-destinations/1", "bindingsSha256": _sha(raw),
              "mappingCount": len(rows), "sourceModuleCount": report["sourceModuleCount"],
              "targetTypeCount": report["targetTypeCount"], "counts": dict(Counter(r["disposition"] for r in rows)),
              "sourceBehaviorExecuted": False, "preparationCompatibility": compatibility, "stages": stages, "mappings": rows}
    ledger["hasEvidenceContractGaps"] = any(s["evidenceContractGaps"] for s in stages)
    write_json(Path(output).resolve(), ledger)
    return ledger


def prepare_from_paths(ir_path, bindings_path, code_index_path, source_root, output):
    """Run the pinned parser locally; retain complete declaration receipts."""
    from .prefab_static_declarations import extract_declarations
    ir = json.loads(Path(ir_path).read_bytes())
    bindings = json.loads(Path(bindings_path).read_bytes())["bindings"]
    modules = json.loads(Path(code_index_path).read_bytes())["modules"]
    components = {c["sourceId"]: c for c in ir["components"]}
    regions = {r["codeRegion"] for r in bindings}
    files = {m["sourceSnapshotPath"] for m in modules if m.get("sourceId") in regions}
    raw, declarations = {}, {}
    for file in sorted(files):
        path = inside(Path(source_root).resolve(), file)
        raw[file] = path.read_bytes()
        selected = {m["sourceId"] for m in modules if m.get("sourceSnapshotPath") == file}
        types = sorted({components[b["sourceComponent"]]["type"] for b in bindings if b["codeRegion"] in selected})
        pin = _sha(raw[file])
        declarations[file] = {"sha256": pin, "result": extract_declarations(path, pin, types)}
    report = prepare(ir, bindings, modules, raw, declarations, output)
    write_json(Path(output).resolve() / "declarations.json", declarations)
    return report


def write_destination_index(ledger, output, *, max_bytes=4 * 1024 * 1024, source_ledger_sha256=None):
    """Create bounded, hash-pinned shards without dropping instance evidence."""
    output = Path(output).resolve()
    if output.exists() or max_bytes < 1024:
        raise ValueError("Expected a new index directory and at least 1024 bytes per shard")
    encode = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    rows = ledger["mappings"]
    if len({r["sourceComponent"] for r in rows}) != len(rows) or len(rows) != ledger["mappingCount"]:
        raise ValueError("Index denominator or source identity conflict")
    groups, group, size = [], [], 0
    for row in rows:
        row_size = len(encode(row)) + 1
        if row_size + 128 > max_bytes:
            raise ValueError("One native mapping exceeds the shard budget")
        if group and size + row_size + 128 > max_bytes:
            groups.append(group)
            group, size = [], 0
        group.append(row)
        size += row_size
    if group:
        groups.append(group)
    index = {k: v for k, v in ledger.items() if k != "mappings"}
    index.update(schemaVersion="monkey-static-code-destinations-index/1", sourceLedgerSha256=source_ledger_sha256,
                 maxShardBytes=max_bytes, shards=[], locations=[])
    payloads = []
    for ordinal, group in enumerate(groups):
        name = f"shard-{ordinal:04d}.json"
        raw = encode({"schemaVersion": "monkey-static-code-destinations-shard/1", "mappings": group})
        if len(raw) > max_bytes:
            raise ValueError("Native mapping shard exceeds the byte budget")
        payloads.append((name, raw))
        index["shards"].append(dict(path=name, sha256=_sha(raw), bytes=len(raw), mappingCount=len(group)))
        index["locations"].extend(dict(sourceComponent=r["sourceComponent"], shard=name, row=i) for i, r in enumerate(group))
    raw_index = encode(index)
    if len(raw_index) > max_bytes:
        raise ValueError("Native mapping index exceeds the byte budget")
    output.mkdir(parents=True)
    for name, raw in payloads:
        (output / name).write_bytes(raw)
    (output / "index.json").write_bytes(raw_index)
    return index


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("prepare")
    for name in ("ir", "bindings", "code-index", "source-root", "output"):
        build.add_argument("--" + name, required=True)
    stage = sub.add_parser("stage")
    for name in ("source", "prepared", "output", "stage-id"):
        stage.add_argument("--" + name, required=True)
    stage.add_argument("--code-region", action="append")
    stage.add_argument("--compile-all-types", action="store_true")
    ledger = sub.add_parser("destinations")
    ledger.add_argument("--prepared", required=True)
    ledger.add_argument("--candidate", action="append", required=True)
    ledger.add_argument("--output", required=True)
    ledger.add_argument("--compatible-prepared", action="append", default=[])
    index = sub.add_parser("index")
    index.add_argument("--ledger", required=True)
    index.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare_from_paths(args.ir, args.bindings, args.code_index, args.source_root, args.output)
    elif args.command == "stage":
        result = stage_candidate(args.source, args.prepared, args.output, stage_id=args.stage_id, code_regions=args.code_region, compile_all_types=args.compile_all_types)
    elif args.command == "destinations":
        result = record_destinations(args.prepared, args.candidate, args.output, compatible_preparations=args.compatible_prepared)
    else:
        raw = Path(args.ledger).read_bytes()
        result = write_destination_index(json.loads(raw), args.output, source_ledger_sha256=_sha(raw))
    print(json.dumps({k: v for k, v in result.items() if k in ("schemaVersion", "mappingCount", "sourceModuleCount", "targetTypeCount", "counts", "stageId")}, sort_keys=True))
    if result.get("hasEvidenceContractGaps"):
        raise SystemExit(1)
    return result


if __name__ == "__main__":
    main()
