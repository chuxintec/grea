"""Selected Unity Prefabs from immutable reader/provider caches, never game code.

The request pins every reused inventory.  This stage copies native provider
assets without editing their YAML and replaces only exact type-proven script
declarations.  Native loading, field verification and presentation are separate.
"""
from collections import deque
from pathlib import Path
import copy
import re

from . import __version__
from .io import inside, load, new_output, read, safe, sha, write_json
from .sources.compiled import fail
from .unity_payloads import validate_payloads
from .unity_prefab_graph import build
from .unity_prefab_types import parse_declarations, propose_schema, emit_schema, emit_disabled_carrier
from .unity_code_model import identifier


CONTRACT = "monkey-unity-prefab-recovery-request/1"
_SCHEMA_PART_THRESHOLD = 32 * 1024 * 1024
_GUID = re.compile(rb"\bguid: ([0-9a-f]{32})\b")
_ENGINE_GUID = re.compile(r"(?:0{32}|0{16}[ef]0{15})")


def pinned(row, limit=128 * 1024 * 1024):
    if not isinstance(row, dict) or not isinstance(row.get("sha256"), str):
        fail("UNITY_PREFAB_INPUT_PIN", "$", "Expected explicit path/SHA input")
    path = safe(row["path"])
    raw = read(path, max_bytes=limit)
    if sha(raw) != row["sha256"] or ("bytes" in row and len(raw) != row["bytes"]):
        fail("UNITY_PREFAB_INPUT_DRIFT", str(path), "Frozen input changed")
    return path, raw


def source_inputs(index_pin, roots):
    _, raw = pinned(index_pin)
    index = load(raw, max_nodes=8_000_000)
    combined = safe(index["indexFromPinnedExistingCombinedSource"]) / "typed-objects.json"
    combined_raw = read(combined, max_bytes=128 * 1024 * 1024)
    if sha(combined_raw) != index["combinedTypedSha256"]:
        fail("UNITY_PREFAB_SOURCE_INDEX_DRIFT", str(combined), "Combined reader cache changed")
    combined_doc = load(combined_raw, max_nodes=8_000_000)
    owners = {}
    for f in combined_doc["files"]:
        owners.setdefault(f["name"], set()).add(f["containerSha256"])
    rows = {r["source"]["sha256"]: r for r in index["sourceInputs"]}
    if len(rows) != len(index["sourceInputs"]):
        fail("UNITY_PREFAB_SOURCE_INDEX_DUPLICATE", "$", "Duplicate container SHA")
    pending, docs, evidence = deque(r["sourceSha256"] for r in roots), {}, []
    while pending:
        digest = pending.popleft()
        if digest in docs:
            continue
        if len(docs) >= 2000 or digest not in rows:
            fail("UNITY_PREFAB_SOURCE_INPUT_MISSING", digest, "No exact cached container")
        row = rows[digest]
        source_path, _ = pinned(row["source"], 1024 * 1024 * 1024)
        inspection_path, inspection_raw = pinned(dict(path=row["inspection"], sha256=row["inspectionSha256"]))
        receipt = load(inspection_raw)
        if (receipt.get("source", {}).get("sha256") != digest or receipt.get("sourceUnchanged") is not True
                or receipt.get("sourceCodeExecuted") is not False or receipt.get("processExited") is not True
                or receipt.get("status") not in ("inspected", "partial")):
            fail("UNITY_PREFAB_INSPECTION_LINEAGE", str(inspection_path), "Reader receipt source differs")
        typed_pin = dict(path=row["typedObjects"], sha256=row["typedObjectsSha256"])
        if receipt.get("typedObjectsSha256") != typed_pin["sha256"]:
            fail("UNITY_PREFAB_INSPECTION_LINEAGE", str(inspection_path), "Reader receipt typed SHA differs")
        typed_path, typed_raw = pinned(typed_pin)
        doc = load(typed_raw, max_nodes=8_000_000)
        if doc.get("source", {}).get("sha256") != digest or doc.get("sourceCodeExecuted") is not False:
            fail("UNITY_PREFAB_INSPECTION_LINEAGE", str(typed_path), "Not a nonexecuting source snapshot")
        validate_payloads(typed_path.parent, doc)
        docs[digest] = dict(sourceSha256=digest, document=doc)
        evidence.append(dict(sourcePath=str(source_path), sourceSha256=digest,
                             inspectionPath=str(inspection_path), inspectionSha256=row["inspectionSha256"],
                             typedObjectsPath=str(typed_path), typedObjectsSha256=typed_pin["sha256"],
                             cacheReaderContractSha256=receipt.get("readerContractSha256"),
                             cacheScope="hash-pinned-prior-reader-output;not-a-new-reader-run-or-equivalence-claim"))
        for f in doc["files"]:
            for external in f["externals"]:
                name = external["path"].rsplit("/", 1)[-1]
                choices = owners.get(name, set())
                if len(choices) > 1:
                    fail("UNITY_PREFAB_EXTERNAL_AMBIGUOUS", name, "Different containers claim the same serialized file")
                pending.extend(choices)
    return list(docs.values()), evidence


def type_models(evidence, selected_script_identities=None):
    parsed = dict(declarations=[])
    proofs = []
    for row in evidence:
        dll, dll_raw = pinned(row["dummyDll"], 64 * 1024 * 1024)
        # Dummy assemblies are structural evidence only; they are not imported.
        assembly = row["assembly"]
        if dll.name != assembly or not assembly.endswith(".dll"):
            fail("UNITY_PREFAB_TYPE_ASSEMBLY", str(dll), "Dummy DLL/assembly identity differs")
        for source in row["declarations"]:
            path, raw = pinned(source, 8 * 1024 * 1024)
            model = parse_declarations(raw.decode("utf-8"), assembly=assembly,
                                       source_path=str(path), source_sha256=sha(raw))
            parsed["declarations"].extend(model["declarations"])
            proofs.append(dict(path=str(path), sha256=sha(raw), assembly=assembly,
                               dummyDllSha256=sha(dll_raw), methodsRecovered=0))
        for source in row.get("ilDeclarations", []):
            from .unity_prefab_il_fields import parse_il_field_references
            path, raw = pinned(source, 8 * 1024 * 1024)
            wanted = [d["identity"] for d in parsed["declarations"] if d["identity"]["assembly"] == assembly and d["kind"] == "class" and "+" not in d["identity"]["name"]
                      and (selected_script_identities is None or (assembly, d["identity"]["namespace"], d["identity"]["name"]) in selected_script_identities)]
            if not wanted:
                proofs.append(dict(path=str(path), sha256=sha(raw), assembly=assembly, methodsRecovered=0, kind="pinned-unused-IL-declarations"))
                continue
            il = parse_il_field_references(raw.decode("utf-8"), assembly=assembly, wanted_types=wanted, source_path=str(path), source_sha256=sha(raw))
            for ref in il["fieldReferences"]:
                owners = [d for d in parsed["declarations"] if d["identity"] == ref["owner"]]
                if len(owners) != 1:
                    fail("UNITY_PREFAB_IL_FIELD_OWNER", str(ref["owner"]), "Exact decompiled class declaration required")
                owners[0].setdefault("fieldTypeReferences", {})[ref["fieldName"]] = ref
            proofs.append(dict(path=str(path), sha256=sha(raw), assembly=assembly, dummyDllSha256=sha(dll_raw),
                               methodsRecovered=0, kind="static-IL-field-type-references", fieldReferences=il["fieldReferences"]))
    keys = [(r["identity"]["assembly"], r["identity"]["namespace"], r["identity"]["name"])
            for r in parsed["declarations"]]
    if len(set(keys)) != len(keys):
        fail("UNITY_PREFAB_TYPE_DUPLICATE", "$", "Ambiguous decompiler declaration")
    return parsed, proofs


def script_proposals(inputs, parsed, allow_disabled, selected_objects=None):
    output = {}
    source_ui_cache = {}
    for entry in inputs:
        doc = entry["document"]
        file_names = {f["id"]: f["name"] for f in doc["files"]}
        objects = {(o["file"], o["pathId"]): o for o in doc["objects"]}
        for obj in doc["objects"]:
            if obj["type"] != "MonoBehaviour" or obj.get("status") != "parsed":
                continue
            if selected_objects is not None and (entry["sourceSha256"], file_names[obj["file"]], obj["pathId"]) not in selected_objects:
                continue
            ptr = obj["data"].get("m_Script", {})
            if ptr.get("fileId") != "0":
                continue  # Cross-file script evidence remains an explicit gap.
            script = objects.get((obj["file"], ptr.get("pathId")))
            if not script or script.get("type") != "MonoScript" or script.get("status") != "parsed":
                continue
            info = script["data"]
            identity = dict(assembly=info["m_AssemblyName"], namespace=info.get("m_Namespace") or "", name=info["m_ClassName"])
            if identity["assembly"].startswith(("UnityEngine", "UnityEditor", "Unity.")):
                continue
            schema = doc.get("embeddedSchemas", {}).get(obj.get("embeddedSchemaId"))
            if schema is None:
                schema = doc.get("borrowedSchemas", {}).get(obj.get("borrowedSchemaId"))
            if schema is None:
                continue
            proposal = propose_schema(parsed, identity, schema)
            from .unity_prefab_source_ui import classify_source_ui_static
            source_ui_key = (identity["assembly"], identity["namespace"], identity["name"], proposal.get("base"))
            if source_ui_key not in source_ui_cache:
                source_ui_cache[source_ui_key] = classify_source_ui_static(parsed, identity, proposal.get("base"))
            source_ui = source_ui_cache[source_ui_key]
            if source_ui is not None:
                proposal["sourceUiStaticEvidence"] = source_ui
            key = (identity["assembly"], identity["namespace"], identity["name"])
            if proposal.get("status") == "schema_only":
                emitted = copy.deepcopy(proposal)
                emitted["enums"] = []
                code = emit_schema(emitted)
                state = "native-base-schema-only"
                if proposal["base"] in ("UnityEngine.MonoBehaviour", "UnityEngine.EventSystems.UIBehaviour", "UnityEngine.UI.Graphic", "UnityEngine.UI.GridLayoutGroup",
                                        "UnityEngine.UI.InputField", "UnityEngine.UI.Selectable"):
                    state = "disabled-unavailable-carrier"
                    proposal = dict(proposal, disabledCarrier=dict(sourceBaseRestored=True, behavior="disabled-required",
                        staticPresentation="unverified-source-custom-component", methodsRecovered=0))
            elif allow_disabled:
                try:
                    carrier_proposal = copy.deepcopy(proposal)
                    carrier_proposal["enums"] = []
                    fallback = emit_disabled_carrier(carrier_proposal)
                except ValueError:
                    continue
                code, state = fallback["source"], "disabled-unavailable-carrier"
                proposal = dict(proposal, disabledCarrier=fallback["metadata"])
            else:
                continue
            previous = output.get(key)
            if previous and (previous["code"] != code or previous["proposal"].get("fields") != proposal.get("fields")):
                fail("UNITY_PREFAB_SCHEMA_CONFLICT", identity["name"], "Instances disagree on their type/schema")
            if not previous:
                output[key] = dict(identity=identity, proposal=proposal, code=code, state=state, sourceInstances=[])
            output[key]["sourceInstances"].append(dict(containerSha256=entry["sourceSha256"], file=obj["file"], pathId=obj["pathId"],
                sourceScriptPathId=script["pathId"], sourceScriptRawSha256=script["rawSha256"],
                sourceEnabled=obj["data"].get("m_Enabled"), sourceFields=sorted(obj["data"])))
    return output


def provider_lineage(provider, source_evidence):
    """Verify the existing whole-export binding, rehash only selected sources.

    Full inventory metadata stays pinned, while unchanged unrelated original
    bundles and texture payloads are not reparsed or exported again.
    """
    _, raw = pinned(provider["receipt"])
    exported = load(raw)
    _, binding_raw = pinned(provider["binding"])
    binding = load(binding_raw)
    prepared_path, prepared_raw = pinned(provider["prepared"])
    prepared = load(prepared_raw, max_nodes=8_000_000)
    _, job_raw = pinned(provider["prepareJob"])
    job = load(job_raw, max_nodes=8_000_000)
    if (binding.get("preparedJobSha256") != sha(job_raw) or binding.get("preparedSha256") != sha(prepared_raw)
            or prepared.get("jobSha256") != sha(job_raw) or prepared.get("status") != "prepared"
            or exported.get("status") != "exported_partial" or exported.get("targetVersion") != "6000.6.2f1"
            or exported.get("processExited") is not True or exported.get("sourceUnchanged") is not True
            or binding.get("sourceCodeExecuted") is not False):
        fail("UNITY_PREFAB_PROVIDER_LINEAGE", str(prepared_path), "Frozen provider/preparation binding differs")
    records = prepared.get("rows", [])
    if len(records) != len(job["sources"]) or prepared.get("prepared") != len(records):
        fail("UNITY_PREFAB_PROVIDER_LINEAGE", str(prepared_path), "Incomplete preparation source denominator")
    for expected, row in zip(job["sources"], records):
        if row.get("source") != expected or row.get("index") != expected["index"]:
            fail("UNITY_PREFAB_PROVIDER_LINEAGE", str(prepared_path), "Preparation source rows differ")
    exported_hashes = {exported["source"]["sha256"]} | {r["sha256"] for r in exported["dependencies"]}
    original_rows = {r["source"]["sha256"]: r for r in records}
    checked = []
    for source in source_evidence:
        row = original_rows.get(source["sourceSha256"])
        if row is None:
            fail("UNITY_PREFAB_PROVIDER_SOURCE_MISSING", source["sourceSha256"], "Selected original absent from provider preparation")
        derived = row.get("derived")
        digest = row.get("derivedSha256") if derived else source["sourceSha256"]
        if digest not in exported_hashes:
            fail("UNITY_PREFAB_PROVIDER_SOURCE_MISSING", digest, "Selected prepared source absent from completed export")
        if derived:
            path, _ = pinned(dict(path=derived, sha256=digest, bytes=row["derivedBytes"]), 1024 * 1024 * 1024)
            if not path.is_relative_to(prepared_path.parent / "containers"):
                fail("UNITY_PREFAB_PROVIDER_DERIVED_PATH", str(path), "Prepared derivative escaped its owner")
            if row.get("retainedNonTextureObjectsUnchanged") is not True or row.get("pixelsFabricated") is not False:
                fail("UNITY_PREFAB_PROVIDER_DERIVED_SCOPE", str(path), "Texture preparation lacks nontexture/source-pixel preservation proof")
        checked.append(dict(originalSha256=source["sourceSha256"], exportedInputSha256=digest,
                            textureHydration=row.get("resolved", []), textureRemovals=row.get("removed", [])))
    return dict(exportReceiptSha256=sha(raw), bindingSha256=sha(binding_raw), preparedSha256=sha(prepared_raw),
                prepareJobSha256=sha(job_raw), selectedSourceInputs=checked, sourceCodeExecuted=False,
                scope="selected-original-and-derived-bytes-rehashed;complete-metadata-binding-pinned;no-full-reexport")


def recover(request_path, expected_request, output):
    request_path, raw = pinned(dict(path=str(request_path), sha256=expected_request))
    request = load(raw, max_nodes=8_000_000)
    if request.get("contract") != CONTRACT or request.get("schemaVersion") != 1 or request.get("targetUnityVersion") != "6000.6.2f1":
        fail("UNITY_PREFAB_REQUEST", str(request_path), "Exact versioned Unity Prefab request required")
    request_evidence = {}
    for name in ("selectionEvidence", "sourceMetadata"):
        if name in request:
            pinned(request[name], 128 * 1024 * 1024)
            request_evidence[name] = request[name]
    roots = request["roots"]
    inputs, source_evidence = source_inputs(request["inputIndex"], roots)
    graph = build(inputs, roots)
    builtin_receipts = []
    receipt_bytes = 0
    for pin in request.get("builtinSchemaReceipts", []):
        _, data = pinned(pin, 16 * 1024 * 1024)
        receipt = load(data)
        if receipt.get("status") != "schemas_read" or receipt.get("exitCode") != 0 or receipt.get("processExited") is not True or receipt.get("sourceUnchanged") is not True:
            fail("UNITY_PREFAB_BUILTIN_SCHEMA_RECEIPT", str(pin), "Completed immutable source schema read required")
        from .unity_prefab_schemas import _validate_report
        wanted = [dict(serializedFile=o["identity"]["serializedFile"], serializedFileSha256=o["identity"]["serializedFileSha256"],
                       pathId=o["identity"]["pathId"], type=o["identity"]["type"], rawSha256=o["identity"]["rawSha256"]) for o in receipt["objects"]]
        _validate_report(receipt, wanted, receipt["source"]["sha256"])
        receipt_bytes += len(data)
        if receipt_bytes <= _SCHEMA_PART_THRESHOLD:
            builtin_receipts.append(receipt)
        else:
            builtin_receipts.clear()
    if graph["sourceUnityVersions"] != ["2021.3.30f1"]:
        fail("UNITY_PREFAB_SOURCE_VERSION", "$", "This fixed profile requires exact source Unity 2021.3.30f1")
    selected_scripts = {(o["data"]["m_AssemblyName"], o["data"].get("m_Namespace") or "", o["data"]["m_ClassName"])
                        for o in graph["reachableObjects"] if o["type"] == "MonoScript" and o.get("status") == "parsed"}
    parsed, type_evidence = type_models(request.get("typeEvidence", []), selected_scripts)
    selected_objects = {(o["identity"]["containerSha256"], o["identity"]["serializedFile"], o["identity"]["pathId"]) for o in graph["reachableObjects"]}
    proposals = script_proposals(inputs, parsed, request.get("allowDisabledUnavailableCarriers") is True, selected_objects)
    provider = request["providerExport"]
    lineage = provider_lineage(provider, source_evidence)
    request_evidence["providerHydration"] = {k: provider[k] for k in ("prepared", "prepareJob")}
    export_root = safe(provider["root"])
    _, inventory_raw = pinned(provider["inventory"])
    inventory = load(inventory_raw, max_nodes=8_000_000)
    rows = {r["path"]: r for r in inventory["files"]}
    if len(rows) != len(inventory["files"]):
        fail("UNITY_PREFAB_EXPORT_DUPLICATE", str(export_root), "Duplicate provider inventory path")

    def payload(path):
        if path not in rows:
            fail("UNITY_PREFAB_EXPORT_UNOWNED", path, "Provider inventory does not own this dependency")
        return pinned(dict(rows[path], path=str(inside(export_root, path))), 256 * 1024 * 1024)[1]

    by_guid = {}
    for path in rows:
        if not path.startswith("ExportedProject/Assets/") or not path.endswith(".meta"):
            continue
        meta = payload(path)
        matches = re.findall(rb"(?m)^guid: ([0-9a-f]{32})\s*$", meta)
        if len(matches) != 1:
            continue
        guid = matches[0].decode()
        if _ENGINE_GUID.fullmatch(guid):
            continue
        asset = path[:-5]
        if asset not in rows:  # Folder metadata is not a referenced asset.
            continue
        if guid in by_guid:
            fail("UNITY_PREFAB_EXPORT_GUID_COLLISION", guid, "Two provider assets share one GUID")
        by_guid[guid] = asset

    selected_roots = []
    for root in roots:
        doc = next(x["document"] for x in inputs if x["sourceSha256"] == root["sourceSha256"])
        matches = []
        for obj in doc["objects"]:
            if obj["type"] != "AssetBundle" or obj.get("status") != "parsed" or obj["file"] != root["file"]:
                continue
            for logical, value in obj["data"].get("m_Container", []):
                ptr = value.get("asset", {})
                if ptr.get("fileId") == "0" and ptr.get("pathId") == root["pathId"]:
                    matches.append(logical)
        if len(matches) != 1 or not matches[0].lower().endswith(".prefab"):
            fail("UNITY_PREFAB_CONTAINER_ROOT", str(root), "One exact original Prefab container path required")
        original = matches[0]
        matches = [path for path in rows if path.startswith("ExportedProject/") and path[len("ExportedProject/"):].casefold() == original.casefold()]
        if len(matches) != 1:
            fail("UNITY_PREFAB_EXPORT_ROOT", original, "Original logical path has no unique provider asset")
        selected_roots.append(dict(source=root, logicalPath=original, providerPath=matches[0]))

    pending, selected, gaps = deque(r["providerPath"] for r in selected_roots), {}, []
    while pending:
        path = pending.popleft()
        if path in selected:
            continue
        if len(selected) >= 100_000:
            fail("UNITY_PREFAB_CLOSURE_BUDGET", path, "Selected native closure exceeds budget")
        data = payload(path)
        selected[path] = data
        if path + ".meta" in rows:
            selected[path + ".meta"] = payload(path + ".meta")
        if data.startswith(b"%YAML"):
            for guid in sorted(set(x.decode() for x in _GUID.findall(data))):
                if _ENGINE_GUID.fullmatch(guid):
                    continue
                target = by_guid.get(guid)
                if target is None:
                    gaps.append(dict(code="UNITY_PREFAB_TARGET_GUID_UNRESOLVED", path=path, guid=guid))
                else:
                    pending.append(target)

    out = new_output(output, [request_path, export_root, *[safe(r["typedObjectsPath"]).parent for r in source_evidence]])
    project = out / "UnityProject"
    project.mkdir()
    code_records, enums = [], {}
    sdk_plan = None
    if request.get("sdkEvidence"):
        from .unity_prefab_sdk import plan_sdk_script_bindings
        sdk = request["sdkEvidence"]
        native_scripts = {}
        for obj in graph["reachableObjects"]:
            if obj["type"] != "MonoScript" or obj.get("status") != "parsed":
                continue
            info = obj["data"]
            if info["m_AssemblyName"] != "UnityEngine.UI.dll":
                continue
            namespace, name = info.get("m_Namespace") or "", info["m_ClassName"]
            path = "ExportedProject/Assets/Scripts/UnityEngine.UI/" + (namespace.replace(".", "/") + "/" if namespace else "") + name + ".cs"
            matches = re.findall(rb"(?m)^guid: ([0-9a-f]{32})\s*$", payload(path + ".meta"))
            if len(matches) != 1:
                fail("UNITY_PREFAB_SDK_SOURCE_GUID", path, "One exact provider MonoScript GUID required")
            key = (namespace, name)
            row = native_scripts.setdefault(key, dict(identity=dict(assembly="UnityEngine.UI.dll", namespace=namespace, name=name),
                sourceTuple=dict(guid=matches[0].decode(), fileID=11500000, type=3), sourceObjectIds=[]))
            row["sourceObjectIds"].append(obj["sourceObjectId"])
        sdk_plan = plan_sdk_script_bindings(native_scripts.values(), sdk_root=sdk["root"], pinned_files=sdk["pinnedFiles"])
        for binding in sdk_plan["bindings"]:
            identity = binding["identity"]
            binding["sourceObjectIds"] = native_scripts[(identity["namespace"], identity["class"])]["sourceObjectIds"]
    sdk_tuples = {}
    if request.get("bindSdkScriptTuples") is True:
        if not sdk_plan:
            fail("UNITY_PREFAB_SDK_SOURCE_GUID", "bindSdkScriptTuples", "Pinned SDK evidence required")
        from .unity_prefab_script_tuples import rebind
        for binding in sdk_plan["bindings"]:
            original, target = binding["sourceTuple"], binding["expectedTuple"]
            key = (original["guid"], original["fileID"], original["type"])
            sdk_tuples[key] = (target["guid"], target["fileID"], target["type"])
    for path, data in sorted(selected.items()):
        relative = path.removeprefix("ExportedProject/")
        if relative.endswith(".cs.meta") and path[:-5] in selected:
            code_path = path[:-5].removeprefix("ExportedProject/")
            parts = code_path[len("Assets/Scripts/"):].split("/") if code_path.startswith("Assets/Scripts/") else []
            key = (parts[0] + ".dll", ".".join(parts[1:-1]), Path(parts[-1]).stem) if len(parts) >= 2 else None
            if key not in proposals:
                dest = inside(project, "SourceRecovery/UnsupportedProviderCode/" + relative)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                continue
        if relative.endswith(".cs"):
            prefix = "Assets/Scripts/"
            parts = relative[len(prefix):].split("/") if relative.startswith(prefix) else []
            key = (parts[0] + ".dll", ".".join(parts[1:-1]), Path(parts[-1]).stem) if len(parts) >= 2 else None
            model = proposals.get(key)
            if model is None:
                sdk_binding = next((b for b in (sdk_plan or {}).get("bindings", [])
                    if key == (b["identity"]["assembly"], b["identity"]["namespace"], b["identity"]["class"])), None)
                gaps.append(dict(code="UNITY_PREFAB_NATIVE_SCRIPT_REBIND_PENDING" if sdk_binding else "UNITY_PREFAB_SCRIPT_SCHEMA_UNSUPPORTED",
                                 path=relative))
                dest = inside(project, "SourceRecovery/UnsupportedProviderCode/" + relative)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                continue
            data = model["code"].encode()
            code_record = dict(path=relative, **{k: v for k, v in model.items() if k != "code"})
            ui_evidence = model.get("proposal", {}).get("sourceUiStaticEvidence")
            if ui_evidence is not None:
                code_record["staticPresentation"] = ("source-static-behavior-neutral" if ui_evidence.get("staticSemanticsProven") is True
                                                      else "partial-source-ui-semantics-unverified")
                if ui_evidence.get("staticSemanticsProven") is not True:
                    gaps.append(dict(code="UNITY_PREFAB_SOURCE_UI_STATIC_UNVERIFIED", path=relative,
                        sourceIdentity=ui_evidence.get("sourceIdentity"),
                        staticPresentation=code_record["staticPresentation"], reasons=ui_evidence.get("reasons", []),
                        targetCanRender="assessed separately by native readback"))
            code_records.append(code_record)
            for enum in model["proposal"].get("enums", []):
                enum_key = (enum["identity"]["assembly"], enum["namespace"], enum["name"])
                if enum_key in enums and enums[enum_key] != enum:
                    fail("UNITY_PREFAB_ENUM_CONFLICT", enum["name"], "Exact enum declarations differ")
                enums[enum_key] = enum
        elif Path(relative).suffix.lower() in (".dll", ".js", ".wasm", ".asmdef", ".asmref"):
            fail("UNITY_PREFAB_UNVERIFIED_CODE", relative, "No original executable/provider assembly is admitted")
        if sdk_tuples and Path(relative).suffix.lower() in (".prefab", ".asset", ".controller", ".mat", ".anim"):
            data = rebind(data, sdk_tuples)
        dest = inside(project, relative)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    for (assembly, namespace, name), enum in enums.items():
        text = "namespace " + namespace + " {\n" if namespace else ""
        text += "public enum " + identifier(name) + " : " + enum["underlyingType"] + " {\n"
        text += "".join("  " + identifier(v["name"]) + " = " + str(v["value"]) + ",\n" for v in enum["values"])
        text += "}\n" + ("}\n" if namespace else "")
        dest = project / "Assets/Scripts" / assembly.removesuffix(".dll") / Path(*namespace.split(".")) / (name + ".cs")
        if dest.exists():
            fail("UNITY_PREFAB_ENUM_PATH_COLLISION", str(dest), "Enum would overwrite a selected file")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
    for assembly in sorted({r["identity"]["assembly"] for r in code_records} | {key[0] for key in enums}):
        if assembly == "Assembly-CSharp.dll":
            continue
        path = project / "Assets/Scripts" / assembly.removesuffix(".dll") / (assembly.removesuffix(".dll") + ".asmdef")
        dependencies = {e["identity"]["assembly"] for r in code_records if r["identity"]["assembly"] == assembly for e in r["proposal"].get("enums", [])} - {assembly}
        if "Assembly-CSharp.dll" in dependencies:
            fail("UNITY_PREFAB_ENUM_ASSEMBLY", assembly, "A named assembly cannot reference the default script assembly")
        write_json(path, dict(name=assembly.removesuffix(".dll"), references=["UnityEngine.UI", *sorted(d.removesuffix(".dll") for d in dependencies)], autoReferenced=True))
    (project / "ProjectSettings").mkdir()
    tags = "ExportedProject/ProjectSettings/TagManager.asset"
    if tags in rows:
        (project / "ProjectSettings/TagManager.asset").write_bytes(payload(tags))
    (project / "ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: 6000.6.2f1\n")
    write_json(project / "Packages/manifest.json", dict(dependencies={"com.unity.ugui": "2.6.0"}))
    write_json(project / "Analysis/Evidence/source-graph.json", graph)
    write_json(project / "Analysis/Evidence/source-inputs.json", source_evidence)
    write_json(project / "Analysis/Evidence/type-evidence.json", type_evidence)
    write_json(project / "Analysis/Evidence/provider-lineage.json", lineage)
    from .input_relocation import current_evidence
    relocation = current_evidence()
    if relocation is not None:
        request_evidence["inputRelocation"] = relocation
    write_json(project / "Analysis/Evidence/request-evidence.json", request_evidence)
    native_asset_mappings = []
    for supplement in request.get("nativeAssetEvidence", []):
        from .unity_prefab_asset_rebuild import load_supplement
        source_root, asset_manifest, mappings = load_supplement(supplement, graph, lineage)
        for mapping in mappings:
            replacement = mapping.get("replacesProviderAsset")
            destination = mapping["path"]
            if replacement:
                destination = replacement["providerPath"]
                for relative, expected in [(destination, replacement["assetSha256"]),
                                           (destination + ".meta", replacement["metaSha256"])]:
                    dest = inside(project, relative)
                    if not dest.is_file() or sha(read(dest, max_bytes=128 * 1024 * 1024)) != expected:
                        fail("UNITY_PREFAB_ASSET_BEFORE_DRIFT", relative, "Exact provider before bytes required for isolated native repair")
                if replacement["guid"] != mapping["guid"] or str(replacement["localId"]) != str(mapping["localId"]):
                    fail("UNITY_PREFAB_ASSET_PRESERVED_IDENTITY", destination, "Native repair must retain provider GUID/localID")
            for relative in (mapping["path"], mapping["path"] + ".meta"):
                dest_relative = destination + (".meta" if relative.endswith(".meta") else "")
                dest = inside(project, dest_relative)
                if dest.exists() and not replacement:
                    fail("UNITY_PREFAB_ASSET_DESTINATION", relative, "Native supplement cannot overwrite a candidate asset")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(read(inside(source_root, relative), max_bytes=128 * 1024 * 1024))
        supplement_sha = sha(read(safe(supplement["path"])))
        for row in asset_manifest["files"]:
            if row["path"].startswith("Analysis/"):
                dest = inside(project, "Analysis/Evidence/native-asset-supplements/" + supplement_sha + "/" + row["path"])
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(read(inside(source_root, row["path"]), max_bytes=128 * 1024 * 1024))
        native_asset_mappings.extend(dict(m, path=m["replacesProviderAsset"]["providerPath"]) if m.get("replacesProviderAsset") else m for m in mappings)
    if native_asset_mappings:
        ids = [r["sourceObjectId"] for r in native_asset_mappings]
        guids = [r["guid"] for r in native_asset_mappings]
        if len(set(ids)) != len(ids) or len(set(guids)) != len(guids):
            fail("UNITY_PREFAB_ASSET_MAPPING_COLLISION", "$", "Native supplemental source identities and GUIDs must be unique")
        existing_guids = {}
        for meta in (project / "Assets").rglob("*.meta"):
            match = re.findall(rb"(?m)^guid: ([0-9a-f]{32})\s*$", read(meta))
            if len(match) == 1:
                guid = match[0].decode()
                if guid in existing_guids:
                    fail("UNITY_PREFAB_ASSET_GUID_COLLISION", guid, "Native supplement collides with an owned candidate GUID")
                existing_guids[guid] = str(meta)
        write_json(project / "Analysis/Mappings/native-source-assets.json", native_asset_mappings)
    if receipt_bytes:
        evidence = project / "Analysis/Evidence"
        if receipt_bytes > _SCHEMA_PART_THRESHOLD:
            # Keep large native batches within the per-document reader limits.
            parts = []
            for pin in request["builtinSchemaReceipts"]:
                _, data = pinned(pin, 16 * 1024 * 1024)
                relative = "builtin-schema-parts/" + pin["sha256"] + ".json"
                part = inside(evidence, relative)
                part.parent.mkdir(parents=True, exist_ok=True)
                part.write_bytes(data)
                parts.append(dict(path=relative, sha256=pin["sha256"]))
            write_json(evidence / "builtin-schemas.json", dict(format="receipt-parts/1", parts=parts))
        else:
            write_json(evidence / "builtin-schemas.json", builtin_receipts)
    if sdk_plan is not None:
        write_json(project / "Analysis/Mappings/native-sdk-scripts.json", sdk_plan)
    write_json(project / "Analysis/Code/schema-carriers.json", code_records)
    for r in code_records:
        if r["state"] == "disabled-unavailable-carrier":
            gaps.append(dict(code="UNITY_PREFAB_UNAVAILABLE_PRESENTATION", path=r["path"], sourceBase=r["proposal"]["base"],
                             behavior="must-disable-before-native-save", staticPresentation="unsupported"))
    # Reuse the existing source-native layout transformation, preserving GUIDs.
    from .unity_layout import relocate
    relocation = relocate(project)
    report = dict(schemaVersion=1, contract="monkey-unity-prefab-recovery/1", toolVersion=__version__,
        requestSha256=expected_request, sourceUnityVersions=graph["sourceUnityVersions"], targetVersion="6000.6.2f1",
        roots=selected_roots, codeCarriers=code_records, sourceGraphGaps=graph["gaps"], diagnostics=gaps,
        providerInventorySha256=sha(inventory_raw), reusedProvider=True, relocation=relocation,
        sourceCodeExecuted=False, methodsRecovered=0, native="not_run", staticPresentation="not_run", business="not_run",
        status="needs_action", boundary="Generated selected candidate; native/static/edit/reopen and consumer adoption are separate.")
    write_json(project / "Analysis/Tasks/unity-prefab-recovery.json", report)
    files = [dict(path=p.relative_to(project).as_posix(), sha256=sha(read(p, max_bytes=256 * 1024 * 1024)), bytes=p.stat().st_size)
             for p in sorted(project.rglob("*")) if p.is_file()]
    from .io import encoded
    source_namespace = "unity-source/" + sha(encoded(sorted(roots, key=lambda r: (r["sourceSha256"], r["file"], r["pathId"]))))[:24]
    write_json(project / "manifest.json", dict(schemaVersion=1, contract=report["contract"], toolVersion=__version__, namespace=source_namespace,
        targetProfile="unity-6000.6.2f1-ugui", projectLayout=relocation["layout"], sourceFamily="unity", requestSha256=expected_request,
        selectedSourceRoots=roots, files=files, diagnostics=gaps, native="not_run", business="not_run"))
    write_json(out / "result.json", report)
    return report
