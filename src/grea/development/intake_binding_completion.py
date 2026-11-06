"""Complete a pinned intake binding plan without running Unity.

This module only composes existing frozen evidence and the candidate-only
``intake_bindings`` planner. It never edits a source or target Unity project.
"""
from pathlib import Path
import hashlib

from .errors import BeaverError, fail
from .io import encoded, load, new_output, safe, write_json
from .intake_bindings import ASSEMBLY, BRIDGE, _assembly, build_plan, preview
from .intake import guid
from .output_limits import digest_file
from .unity import source_files


LINEAGE = "Analysis/BeaverIntakeBindings/lineage.json"
FRAGMENTS = "Analysis/BeaverIntakeBindings/intake-spec-fragments.json"
SOURCE_ORIGIN = "Analysis/BeaverIntakeBindings/source-origin.json"
BRIDGE_ASMDEF = "Assets/BeaverIntakeBindings/Beaver.IntakeBindings.asmdef"


def _read_json(path, where):
    try:
        return load(safe(path).read_bytes())
    except (OSError, ValueError) as error:
        fail("INTAKE_BINDING_EVIDENCE", str(where), str(error))


def _manifest_file_map(candidate):
    manifest_path = candidate / "manifest.json"
    manifest = _read_json(manifest_path, "candidate manifest")
    rows = manifest.get("files")
    if not isinstance(rows, list):
        fail("INTAKE_BINDING_EVIDENCE", str(manifest_path), "Frozen candidate manifest file inventory is missing")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            fail("INTAKE_BINDING_EVIDENCE", str(manifest_path), "Malformed candidate manifest file row")
        if row["path"] in result:
            fail("INTAKE_BINDING_EVIDENCE", row["path"], "Duplicate path in candidate manifest")
        result[row["path"]] = row
    return manifest, result


def _check_manifest_pin(candidate, file_map, rel):
    row = file_map.get(rel)
    path = candidate / rel
    if row is None or not path.is_file() or digest_file(path) != row.get("sha256") or path.stat().st_size != row.get("bytes"):
        fail("INTAKE_BINDING_EVIDENCE_DRIFT", rel, "Required candidate artifact differs from frozen manifest")
    return path


def _meta_guid(root, path):
    meta_path = root / (path + ".meta")
    raw = meta_path.read_bytes()
    return guid(raw, path), digest_file(meta_path)


def _semantic_index(report):
    source_rows = {}
    type_rows = {}
    for assembly in report.get("assemblies", []):
        name = assembly.get("name")
        source_hashes = {r.get("path"): r.get("sha256") for r in assembly.get("sources", [])}
        for row in assembly.get("sourceSemantics", []):
            path = row.get("path")
            if path in source_rows:
                fail("INTAKE_BINDING_EVIDENCE", str(path), "Semantic report contains an ambiguous source path")
            row_with_context = dict(row)
            row_with_context["assembly"] = name
            row_with_context["sourceSha256"] = source_hashes.get(path)
            source_rows[path] = row_with_context
            for type_row in row.get("types", []):
                type_rows.setdefault(path, []).append(type_row)
    return source_rows, type_rows


def _one_type(path, expected_name, source_assembly, semantic_rows, type_rows):
    row = semantic_rows.get(path)
    if row is None or row.get("assembly") != source_assembly or not row.get("sourceSha256"):
        fail("INTAKE_BINDING_SEMANTIC_COVERAGE", path, "Pinned semantic report lacks this source in the expected assembly")
    matches = [t for t in type_rows.get(path, []) if t.get("fullName") == expected_name]
    if len(matches) != 1 or matches[0].get("assembly") != source_assembly or matches[0].get("unityObject") is not True:
        fail("INTAKE_BINDING_TYPE", path, "Expected exactly one compiled Unity object type with the pinned full name")
    if row.get("unresolved"):
        fail("INTAKE_BINDING_SEMANTIC_UNRESOLVED", path, "Source has unresolved compiler diagnostics in the pinned semantic evidence")
    if row.get("lateBoundDependencies"):
        fail("INTAKE_BINDING_LATE_BOUND", path, "Runtime name lookup requires separate closure review")
    return row, matches[0]


def _make_bindings(candidate, candidate_file_map, target, source, source_is_origin,
                   lineage, evidence, semantic_report, report_path, report_hash):
    semantic_rows, type_rows = _semantic_index(semantic_report)
    source_bindings = lineage.get("rebind", {}).get("sourceToRetainedBindings")
    if not isinstance(source_bindings, list):
        fail("INTAKE_BINDING_LINEAGE", LINEAGE, "Pinned existing bridge binding list is missing")

    pending = []
    for old in source_bindings:
        pending.append({
            "source": old["source"], "sourceGuid": old["sourceGuid"], "sourceSha256": old["sourceSha256"],
            "sourceMetaSha256": old["sourceMetaSha256"], "expectedSourceMetaSha256": old["sourceMetaSha256"],
            "sourceType": old["type"],
            "expectedSourceAssembly": old["sourceAssembly"], "target": old["target"],
            "expectedTargetGuid": old["targetGuid"], "expectedTargetSha256": old["targetSha256"],
            "expectedTargetMetaSha256": old["targetMetaSha256"], "expectedTargetType": old["type"],
            "expectedTargetAssembly": old["targetAssembly"], "origin": "candidate-lineage-existing-bridge"
        })

    reused = evidence.get("reuseCandidates")
    if not isinstance(reused, list):
        fail("INTAKE_BINDING_EVIDENCE", "reuseCandidates", "Dependency evidence has no reuse candidate list")
    selected_reuse = [r for r in reused if r.get("category") == "retained_type_requires_binding_review" and
                      r.get("nativeReferenced") is True]
    for item in selected_reuse:
        pins = item.get("targetSourcePins")
        if (item.get("inSelectedClosure") is not True or not isinstance(pins, list) or len(pins) != 1):
            fail("INTAKE_BINDING_EVIDENCE", item.get("path", "reuseCandidate"), "Reuse evidence is incomplete for selected native source")
        pin = pins[0]
        byte_identical = item.get("byteIdenticalTargetSources")
        if not isinstance(byte_identical, list) or pin.get("path") not in byte_identical or pin.get("sha256") != item.get("sha256"):
            fail("INTAKE_BINDING_EVIDENCE", item.get("path", "reuseCandidate"), "Native reuse is not proven byte-identical to its target source")
        type_rows_for_item = item.get("types", [])
        if len(type_rows_for_item) != 1:
            fail("INTAKE_BINDING_TYPE", item["path"], "Expected one pinned class type in reuse evidence")
        type_name = type_rows_for_item[0].get("fullName")
        if not isinstance(type_name, str) or not type_name or type_rows_for_item[0].get("unityObject") is not True:
            fail("INTAKE_BINDING_TYPE", item["path"], "Reuse evidence type full name is missing")
        if item.get("guid") == pin.get("guid"):
            fail("INTAKE_BINDING_ALIAS", item["path"], "Native source and retained target must have different GUIDs")
        pending.append({
            "source": item["path"], "sourceGuid": item["guid"], "sourceSha256": item["sha256"],
            "sourceType": type_name, "expectedSourceAssembly": item.get("scope", {}).get("assembly"),
            "expectedSourceMetaSha256": None,
            "target": pin["path"], "expectedTargetGuid": pin["guid"],
            "expectedTargetSha256": pin["sha256"], "expectedTargetMetaSha256": pin["metaSha256"],
            "expectedTargetType": type_name, "expectedTargetAssembly": (item.get("targetAssemblies") or [None])[0],
            "origin": "dependency-evidence-native-input-reuse", "reuseEvidence": item
        })

    if not 1 <= len(pending) <= 16:
        fail("INTAKE_BINDING_COUNT", "bindings", "The completed intake spec must contain 1..16 mappings")

    rows, consumer_scripts, consumer_evidence = [], [], []
    source_paths, target_paths, source_guids, target_guids, type_names = set(), set(), set(), set(), set()
    for item in pending:
        src, dst = item["source"], item["target"]
        if src in source_paths or dst in target_paths or item["sourceGuid"] in source_guids or item["expectedTargetGuid"] in target_guids:
            fail("INTAKE_BINDING_DUPLICATE", src, "Source/target paths or native identities collide")
        source_paths.add(src); target_paths.add(dst)
        source_guids.add(item["sourceGuid"]); target_guids.add(item["expectedTargetGuid"])
        if item["sourceGuid"] == item["expectedTargetGuid"]:
            fail("INTAKE_BINDING_ALIAS", src, "Source and retained Unity GUIDs must differ")

        source_file = source / src
        target_file = target / dst
        if not source_file.is_file() or not target_file.is_file():
            fail("INTAKE_BINDING_SOURCE", src if not source_file.is_file() else dst, "Pinned source/target script is missing")
        source_hash, target_hash = digest_file(source_file), digest_file(target_file)
        if source_hash != item["sourceSha256"] or target_hash != item["expectedTargetSha256"] or source_hash != target_hash:
            fail("INTAKE_BINDING_DRIFT", src, "Source and target scripts must match their exact evidence hashes and each other")
        candidate_source = _check_manifest_pin(candidate, candidate_file_map, src)
        candidate_meta = _check_manifest_pin(candidate, candidate_file_map, src + ".meta")
        candidate_source_hash = digest_file(candidate_source)
        expected_source_guid, expected_source_meta_hash = _meta_guid(candidate, src)
        if candidate_source_hash != item["sourceSha256"]:
            fail("INTAKE_BINDING_SOURCE_EVIDENCE_DRIFT", src, "Frozen candidate copy differs from the lineage/dependency source hash")
        if item.get("expectedSourceMetaSha256") and expected_source_meta_hash != item["expectedSourceMetaSha256"]:
            fail("INTAKE_BINDING_SOURCE_EVIDENCE_DRIFT", src + ".meta", "Frozen candidate source metadata differs from lineage evidence")
        if digest_file(candidate_meta) != expected_source_meta_hash:
            fail("INTAKE_BINDING_SOURCE_EVIDENCE_DRIFT", src + ".meta", "Frozen source metadata file is not pinned by the candidate manifest")
        source_guid, source_meta_hash = _meta_guid(source, src)
        target_guid, target_meta_hash = _meta_guid(target, dst)
        if (expected_source_guid != item["sourceGuid"] or source_guid != expected_source_guid or
                source_meta_hash != expected_source_meta_hash or target_guid != item["expectedTargetGuid"]):
            fail("INTAKE_BINDING_GUID", src, "Source or target metadata GUID differs from the pinned identity")
        if item.get("sourceMetaSha256") and source_meta_hash != item["sourceMetaSha256"]:
            fail("INTAKE_BINDING_DRIFT", src + ".meta", "Source metadata differs from candidate lineage")
        if target_meta_hash != item["expectedTargetMetaSha256"]:
            fail("INTAKE_BINDING_DRIFT", dst + ".meta", "Target metadata differs from candidate evidence")

        source_assembly, source_scope_pins = _assembly(source, src)
        target_assembly, target_scope_pins = _assembly(target, dst)
        if source_assembly != item["expectedSourceAssembly"] or target_assembly != item["expectedTargetAssembly"]:
            fail("INTAKE_BINDING_ASSEMBLY", src, "Source/target compilation scope differs from pinned evidence")
        source_semantic, type_row = _one_type(src, item["sourceType"], source_assembly, semantic_rows, type_rows)
        if source_semantic["sourceSha256"] != source_hash:
            fail("INTAKE_BINDING_SEMANTIC_DRIFT", src, "Semantic report source bytes differ from raw original source")

        if item["sourceType"] in type_names:
            fail("INTAKE_BINDING_DUPLICATE", item["sourceType"], "Each MonoScript mapping must bind a distinct full type")
        type_names.add(item["sourceType"])
        row = dict(source=src, sourceGuid=source_guid, sourceSha256=source_hash, sourceMetaSha256=source_meta_hash,
                   sourceType=item["sourceType"], sourceAssembly=source_assembly, sourceLocalId=11500000,
                   target=dst, targetGuid=target_guid, targetSha256=target_hash, targetMetaSha256=target_meta_hash,
                   targetType=item["sourceType"], targetAssembly=target_assembly, targetLocalId=11500000)
        rows.append(row)
        consumer_scripts.append(dict(source=BRIDGE + "/" + Path(src).name, sourceGuid=target_guid,
            sourceType=item["sourceType"], sourceAssembly=ASSEMBLY, target=dst, targetGuid=target_guid,
            targetType=item["sourceType"], targetAssembly=target_assembly, targetLocalId=11500000,
            targetSha256=target_hash, targetMetaSha256=target_meta_hash,
            status="planned_not_executed", preparedNow=False,
            reason="Future consumer externalScripts declaration after native preparation; not a prepared source project."))
        consumer_evidence.append(dict(source=src, type=item["sourceType"], sourceAssembly=source_assembly,
            target=dst, targetAssembly=target_assembly, sourceScopePins=source_scope_pins,
            targetScopePins=target_scope_pins, sourceTypeEvidence=type_row,
            sourceDependencyEvidence=source_semantic.get("dependencies", []),
            lateBoundDependencies=source_semantic.get("lateBoundDependencies", []),
            semanticReport=dict(path=str(report_path), sha256=report_hash),
            evidenceOrigin=item["origin"],
            dedicatedReuseEvidence=item.get("reuseEvidence"),
            currentSourceSemanticStatus=("verified_from_pinned_compile_context" if source_is_origin else
                "pending_fresh_compile_context_for_future_source"),
            currentFieldsAndReferencesVerified=source_is_origin))

    allowed_sources = {row["source"] for row in rows}
    for evidence_row in consumer_evidence:
        missing = sorted({d["path"] for d in evidence_row["sourceDependencyEvidence"]} - allowed_sources)
        if missing:
            fail("INTAKE_BINDING_DEPENDENCY_CLOSURE", evidence_row["source"],
                 "Bridge source dependency is not among the six explicit bindings: " + ", ".join(missing))

    return rows, consumer_scripts, consumer_evidence


def _propose(candidate, target, source_project, output, dependency_report):
    candidate, target, source = safe(candidate), safe(target), safe(source_project)
    dependency = safe(dependency_report) if dependency_report else None
    inputs = [candidate, target, source] + ([dependency] if dependency else [])
    out = new_output(output, inputs)
    try:
        if dependency is None:
            default = candidate / "Analysis/BeaverIntakeBindings/dependency-evidence.json"
            if not default.is_file():
                fail("INTAKE_BINDING_EVIDENCE_REQUIRED", str(default), "Six-binding completion requires the pinned dependency-evidence report")
            dependency = safe(default)
        manifest, candidate_file_map = _manifest_file_map(candidate)
        lineage_path = _check_manifest_pin(candidate, candidate_file_map, LINEAGE)
        candidate_manifest_hash = digest_file(candidate / "manifest.json")
        evidence = _read_json(dependency, "dependency evidence")
        if evidence.get("contract") != "beaver-intake-dependencies/1":
            fail("INTAKE_BINDING_EVIDENCE", str(dependency), "Expected beaver-intake-dependencies/1")
        if evidence.get("candidateManifestSha256") != candidate_manifest_hash:
            fail("INTAKE_BINDING_EVIDENCE_DRIFT", str(candidate / "manifest.json"), "Dependency report does not pin this frozen candidate manifest")
        context_pins = evidence.get("contextPins")
        if not isinstance(context_pins, dict):
            fail("INTAKE_BINDING_EVIDENCE", str(dependency), "Compiler context pins are required for semantic evidence")
        for context_path, expected_hash in context_pins.items():
            pinned_context = safe(context_path)
            if not pinned_context.is_file() or digest_file(pinned_context) != expected_hash:
                fail("INTAKE_BINDING_EVIDENCE_DRIFT", context_path, "Pinned compiler input/response file changed")

        lineage = _read_json(lineage_path, LINEAGE)
        source_origin = lineage.get("source", {})
        origin_source = safe(source_origin.get("root", ""))
        source_is_origin = source == origin_source
        source_inventory_hash = hashlib.sha256(encoded(source_files(source))).hexdigest()
        if source_is_origin and source_inventory_hash != source_origin.get("sourceFilesSha256"):
            fail("INTAKE_BINDING_SOURCE_DRIFT", str(source), "Original source inventory differs from frozen lineage")
        if evidence.get("sourceProject") not in (str(source), source_origin.get("root")):
            # Dependency evidence may have been collected in a derived prep project.
            # The candidate lineage remains the authority for original source identity.
            if not isinstance(evidence.get("sourceProject"), str) or not evidence.get("sourceProject"):
                fail("INTAKE_BINDING_EVIDENCE", str(dependency), "Dependency evidence lacks its source project identity")

        fragment_path = _check_manifest_pin(candidate, candidate_file_map, FRAGMENTS)
        _check_manifest_pin(candidate, candidate_file_map, SOURCE_ORIGIN)
        asmdef_path = _check_manifest_pin(candidate, candidate_file_map, BRIDGE_ASMDEF)
        fragment = _read_json(fragment_path, FRAGMENTS)
        asmdef = _read_json(asmdef_path, BRIDGE_ASMDEF)
        if asmdef.get("name") != ASSEMBLY or not isinstance(asmdef.get("references"), list):
            fail("INTAKE_BINDING_ASSEMBLY", BRIDGE_ASMDEF, "Frozen bridge assembly identity/references are missing")
        prefabs = [row.get("asset") for row in fragment.get("spec4Fragment", {}).get("verifications", [])]
        if not prefabs or any(not isinstance(path, str) for path in prefabs) or len(set(prefabs)) != len(prefabs):
            fail("INTAKE_BINDING_PREFABS", FRAGMENTS, "Frozen selected Prefab evidence is missing or ambiguous")

        semantic_info = evidence.get("semanticReport")
        if not isinstance(semantic_info, dict) or not isinstance(semantic_info.get("path"), str):
            fail("INTAKE_BINDING_EVIDENCE", str(dependency), "Semantic report pin is missing")
        semantic_report_path = safe(semantic_info["path"])
        if digest_file(semantic_report_path) != semantic_info.get("sha256"):
            fail("INTAKE_BINDING_EVIDENCE_DRIFT", str(semantic_report_path), "Pinned semantic report changed")
        semantic_report = _read_json(semantic_report_path, semantic_info)
        if semantic_report.get("status") != "ok":
            fail("INTAKE_BINDING_SEMANTIC_COVERAGE", str(semantic_report_path), "Pinned source semantic report is not complete")
        semantic_report_hash = semantic_info["sha256"]

        rows, consumer_scripts, consumer_evidence = _make_bindings(candidate, candidate_file_map, target, source,
            source_is_origin, lineage, evidence, semantic_report, semantic_report_path, semantic_report_hash)
        spec = dict(schemaVersion=1, operation="prepare-script-bindings", bindings=rows,
                    prefabs=prefabs, bridgeReferences=asmdef["references"])
        spec_path = out / "binding-spec.json"
        write_json(spec_path, spec)

        # Use the existing immutable intake planner, then independently re-run its
        # fresh-input precondition builder before publishing this review artifact.
        planned = preview(source, target, spec_path, out / "intake-binding-plan")
        plan_path = Path(planned["report"])
        plan = _read_json(plan_path, plan_path)
        fresh = build_plan(source, target, spec_path)
        if fresh != plan:
            fail("INTAKE_BINDING_PLAN_DRIFT", str(plan_path), "Independent planner result differs from preview output")
        completion = dict(contract="beaver-intake-binding-completion/1", status="planned",
            candidate=str(candidate), candidateManifestSha256=candidate_manifest_hash,
            dependencyEvidence=dict(path=str(dependency), sha256=digest_file(dependency)),
            sourceLineage=dict(path=str(lineage_path), sha256=digest_file(lineage_path),
                sourceRoot=str(source), sourceInventorySha256=source_inventory_hash,
                lineageSourceRoot=str(origin_source), lineageSourceFilesSha256=source_origin["sourceFilesSha256"],
                sourceIsLineageRoot=source_is_origin, lineageRootInventoryChecked=source_is_origin,
                sourceOrigin=plan.get("sourceOrigin")),
            semanticReport=dict(path=str(semantic_report_path), sha256=semantic_report_hash),
            plan=dict(path=str(plan_path), sha256=digest_file(plan_path), planSha256=planned["planSha256"]),
            bindingCount=len(rows), bindings=rows, consumerExternalScripts=consumer_scripts,
            consumerDependencyEvidence=consumer_evidence, consumerPreparation="planned_not_executed",
            currentSourceFieldValidation=("verified_from_pinned_compile_context" if source_is_origin else
                "pending_fresh_compile_context_for_future_source"),
            native="not_run", targetWrites=False,
            limitations=["Consumer externalScripts rows describe a future sourceAssembly Beaver.IntakeBindings; this output is not a prepared source project.",
                "No Editor/native rebind ran. Original source and target files remain untouched.",
                "The selected Prefab list comes from the frozen existing bridge spec fragment; parent owns subsequent full intake/compiler closure work."])
        report_path = out / "completion.json"
        write_json(report_path, completion)
        return dict(status="planned", report=str(report_path), plan=str(plan_path),
            planSha256=planned["planSha256"], bindings=len(rows), native="not_run", targetWrites=False)
    except BeaverError as error:
        if error.code == "INTAKE_BINDING_SOURCE_DRIFT":
            recipe = "Reacquire the lineage-pinned original source project or establish a new reviewed lineage; do not replace its inventory hash."
        elif error.code == "INTAKE_BINDING_CLOSURE":
            recipe = "Use the diagnostic's missing nested Prefab paths to prepare an explicit successor selected-Prefab evidence set, then regenerate this proposal from unchanged source and target pins."
        elif error.code == "INTAKE_BINDING_RESERVED":
            recipe = "Select the exact unprepared source project or create a separately reviewed source lineage; never remove or rewrite the existing Bridge root for this plan."
        else:
            recipe = "Revalidate the reported source, target, semantic, and assembly pins; regenerate only after the evidence relationship is established."
        result = dict(contract="beaver-intake-binding-completion/1", status="blocked",
            diagnostics=[error.as_dict()], native="not_run", targetWrites=False,
            nextStep=recipe)
        report_path = out / "completion.json"
        write_json(report_path, result)
        return dict(status="blocked", report=str(report_path), native="not_run", targetWrites=False,
                    code=error.code)


def propose(candidate, target, source_project, output, *, dependency_report=None):
    """Write a reviewable binding proposal in a fresh private output.

    ``candidate`` must contain the frozen candidate lineage and manifest;
    ``source_project`` is explicit and may be a future source root. Every mapped
    source, metadata identity, assembly scope, and selected-Prefab closure is
    rechecked. Future roots require a fresh compile context to validate fields.
    """
    try:
        return _propose(candidate, target, source_project, output, dependency_report)
    except BeaverError as error:
        return dict(status="blocked", code=error.code, native="not_run", targetWrites=False,
                    diagnostics=[error.as_dict()])
