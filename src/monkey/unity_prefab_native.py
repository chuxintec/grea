"""Source-derived expectations for the selected Unity Prefab native bridge."""
from pathlib import Path
import re
import os
import shutil
import subprocess
import time
import struct

from .io import inside, load, read, safe, sha, write_json, new_output
from .sources.compiled import fail
from .unity_prefab_recovery import source_inputs
from .native_selection import _guid_meta
from .unity_prefab_renderer_profiles import renderer_scalar_mapping


_ASSEMBLIES = {
    **{n: "UnityEngine.CoreModule" for n in ("Transform", "RectTransform", "SpriteRenderer", "MeshRenderer", "MeshFilter", "LineRenderer")},
    **{n: "UnityEngine.UIModule" for n in ("CanvasRenderer", "Canvas", "CanvasGroup")},
    "ParticleSystem": "UnityEngine.ParticleSystemModule", "ParticleSystemRenderer": "UnityEngine.ParticleSystemModule",
    "Animator": "UnityEngine.AnimationModule",
}


def unity_guid_text_from_serialized_hex(raw):
    """UnityGuid prints low nibble first for each byte of its serialized data.

    Format reference: AssetRipper.Primitives/UnityGuid.cs, ToString(Span<char>)
    at 7091ff7f362da3784315a0aee04843771664cdd5. This converts representation;
    it never maps an engine path ID to an assumed resource name or behavior.
    """
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9a-f]{32}", raw):
        fail("UNITY_PREFAB_GUID_ENCODING", str(raw), "Exact serialized 16-byte GUID hex required")
    return "".join(raw[i+1] + raw[i] for i in range(0, 32, 2))


def rect_layout_expectations(graph, driven_fields=None):
    """RectTransform XY is derived from anchors/pivots, not stale Transform XY."""
    f32 = lambda value: struct.unpack("<f", struct.pack("<f", value))[0]
    nodes = {n["sourceObjectId"]: n for n in graph["gameObjects"]}
    objects = {o["sourceObjectId"]: o for o in graph["reachableObjects"]}
    result = {}

    def visit(sid, parent=None):
        node = nodes[sid]
        rect = next((objects[c["sourceObjectId"]] for c in node["orderedComponents"] if c["type"] == "RectTransform"), None)
        layout = None
        if rect:
            data = rect["data"]
            overrides = (driven_fields or {}).get(rect['sourceObjectId'], {})
            if overrides:
                data = dict(data)
                for prop, row in overrides.items():
                    vector, axis = prop.split('.')
                    if vector not in ('m_AnchorMin', 'm_AnchorMax') or axis not in ('x', 'y'):
                        fail('UNITY_PREFAB_DRIVEN_RECT_FIELD', prop, 'Only proven source-driven anchor axes affect this layout bridge')
                    data[vector] = dict(data[vector], **{axis: row['expectedDrivenValue']})
            size, position = {}, {}
            for axis in ("x", "y"):
                span = f32(data["m_AnchorMax"][axis] - data["m_AnchorMin"][axis])
                parent_size = parent["size"][axis] if parent else 0
                size[axis] = f32(f32(parent_size * span) + data["m_SizeDelta"][axis])
                anchor = f32(data["m_AnchorMin"][axis] + f32(span * data["m_Pivot"][axis]))
                position[axis] = f32(data["m_AnchoredPosition"][axis] + f32(parent_size * f32(anchor - parent["pivot"][axis]))) if parent else f32(data["m_AnchoredPosition"][axis])
            layout = dict(size=size, pivot=data["m_Pivot"], position=position)
            result[rect["sourceObjectId"]] = layout
        for child in node["childSourceObjectIds"]:
            visit(child, layout)
    for root in graph["roots"]:
        visit(root["sourceObjectId"])
    return result


def bind_source_root_rows(graph_roots, report_roots, file_names):
    """Join root paths by pinned source identity, independently of list order."""
    by_key = {}
    for root in graph_roots:
        identity = root["identity"]
        key = (identity["containerSha256"], identity["serializedFile"], identity["pathId"])
        if key in by_key:
            fail("UNITY_PREFAB_NATIVE_ROOT_AMBIGUOUS", str(key), "Duplicate source root identity")
        by_key[key] = root["sourceObjectId"]
    bound = {}
    for row in report_roots:
        source = row["source"]
        filename = file_names.get((source["sourceSha256"], source["file"]))
        key = (source["sourceSha256"], filename, source["pathId"])
        sid = by_key.get(key)
        if sid is None or sid in bound:
            fail("UNITY_PREFAB_NATIVE_ROOT_MAPPING", str(key), "One exact source root/path binding required")
        bound[sid] = row
    if set(bound) != set(by_key.values()):
        fail("UNITY_PREFAB_NATIVE_ROOT_MAPPING", "$", "Source root/path sets differ")
    return bound


def cold_reopen(native_output, editor, budget_seconds=600):
    """Read the saved candidate in a different headless process; never save again."""
    from .native import now, stamp
    out, editor = safe(native_output), safe(editor)
    receipt = load(read(out / "execution-result.json"))
    if receipt.get("processExited") is not True or receipt.get("status") not in ("native-partial", "native-verified-subset"):
        fail("UNITY_PREFAB_COLD_PRECONDITION", str(out), "Prior owned native save must have completed")
    work = out / "UnityProject"
    plan = load(read(work / "Analysis/Tasks/native-prefab-plan.json"))
    if sha(read(work / "Assets/Editor/MonkeyUnitySource/UnityPrefabStaticReadback.cs")) != receipt["helperSha256"]:
        fail("UNITY_PREFAB_COLD_HELPER_DRIFT", str(out), "Use the exact first-process helper")
    for helper in receipt.get("helpers", []):
        if sha(read(inside(work, helper["path"]))) != helper["sha256"]:
            fail("UNITY_PREFAB_COLD_HELPER_DRIFT", helper["path"], "Native helper set changed")
    first = load(read(receipt["readbackPath"], max_bytes=128 * 1024 * 1024), max_nodes=8_000_000)
    if sha(read(receipt["readbackPath"], max_bytes=128 * 1024 * 1024)) != receipt["readbackSha256"]:
        fail("UNITY_PREFAB_COLD_RECEIPT_DRIFT", str(out), "First readback changed")
    if any(not r.get("saved") or not r.get("reopened") or r.get("failures") for r in first["roots"]):
        fail("UNITY_PREFAB_COLD_ROOT_UNSAVED", str(out), "All roots require actual save/reload with no field failure")
    processes = subprocess.check_output(["ps", "-axo", "pid=,comm="], text=True).splitlines()
    if any(r.strip().endswith(("/Contents/MacOS/Unity", "/Contents/MacOS/CocosCreator", "/Unity.exe", "/CocosCreator.exe")) for r in processes):
        fail("UNITY_PREFAB_EDITOR_BUSY", "$", "Another main Editor is running")
    plan.update(headless=True, reopenOnly=True, outputRelative="Analysis/Readback/unity-prefab-cold.json")
    stage = new_output(out / "ColdReopen", [editor])
    plan_path = stage / "plan.json"
    write_json(plan_path, plan)
    env = dict(os.environ, MONKEY_UNITY_PREFAB_PLAN=str(plan_path), MONKEY_UNITY_PREFAB_PLAN_SHA256=sha(read(plan_path)))
    result = dict(schemaVersion=1, status="started", firstReadbackSha256=receipt["readbackSha256"],
                  firstPid=receipt["pid"], startedUtc=stamp(now()), graphics="not_run_headless", savedAgain=False)
    child = None
    try:
        with (stage / "console.log").open("wb") as log:
            child = subprocess.Popen([str(editor), "-batchmode", "-nographics", "-quit", "-projectPath", str(work),
                "-executeMethod", "MonkeyUnitySource.UnityPrefabStaticReadback.Run", "-logFile", str(stage / "editor.log")],
                cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT)
            result["pid"] = child.pid
            try:
                child.wait(timeout=budget_seconds)
            except subprocess.TimeoutExpired:
                result["stopReason"] = "fixed-cold-budget"
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
        result.update(processExited=child is not None and child.poll() is not None,
                      exitCode=child.poll() if child is not None else None, endedUtc=stamp(now()))
        result["status"] = "pending_child_exit" if child is not None and child.poll() is None else "failed"
        rb = work / plan["outputRelative"]
        if rb.is_file():
            raw = read(rb, max_bytes=128 * 1024 * 1024)
            second = load(raw, max_nodes=8_000_000)
            result.update(readbackPath=str(rb), readbackSha256=sha(raw))
            stable = len(first["roots"]) == len(second.get("roots", []))
            for before, after in zip(first["roots"], second.get("roots", [])):
                stable = stable and before["sourceId"] == after["sourceId"] and after.get("reopened") and not after.get("failures")
                stable = stable and before["nativeIdentitiesAfter"] == after.get("nativeIdentitiesAfter")
                stable = stable and before["assetReferencesAfter"] == after.get("assetReferencesAfter")
                stable = stable and before["fieldsExpected"] == after.get("fieldsCheckedAfterReopen")
            result["nativeIdentityAndReferencesStable"] = bool(stable)
            if stable and child is not None and child.poll() in (0, 1) and second.get("status") in ("completed", "partial"):
                result["status"] = "cold-reopen-verified-subset"
        write_json(stage / "result.json", result)
    return result


def prepare(project, expected_manifest):
    project = safe(project)
    raw = read(project / "manifest.json", max_bytes=128 * 1024 * 1024)
    if sha(raw) != expected_manifest:
        fail("UNITY_PREFAB_CANDIDATE_SHA", str(project), "Exact generated candidate manifest required")
    manifest = load(raw, max_nodes=8_000_000)
    if manifest.get("contract") != "monkey-unity-prefab-recovery/1" or manifest.get("targetProfile") != "unity-6000.6.2f1-ugui":
        fail("UNITY_PREFAB_NATIVE_PROFILE", str(project), "Not a selected Unity-source candidate")
    for row in manifest["files"]:
        body = read(inside(project, row["path"]), max_bytes=256 * 1024 * 1024)
        if len(body) != row["bytes"] or sha(body) != row["sha256"]:
            fail("UNITY_PREFAB_CANDIDATE_DRIFT", row["path"], "Generated candidate changed")
    report = load(read(project / "Analysis/Tasks/unity-prefab-recovery.json"))
    graph = load(read(project / "Analysis/Evidence/source-graph.json", max_bytes=128 * 1024 * 1024), max_nodes=8_000_000)
    objects = {o["sourceObjectId"]: o for o in graph["reachableObjects"]}
    nodes = {o["sourceObjectId"]: o for o in graph["gameObjects"]}
    edges = {(e["sourceObjectId"], e["location"]): e for e in graph["referenceEdges"]}
    moves = load(read(project / "Analysis/Mappings/unity-relocation.json"))["moves"]
    moved = {r["source"]: r["target"] for r in moves}
    source_files = [r["source"] for r in moves]
    resource_bindings, scripts, shapes, source_file_names = {}, {}, {}, {}
    sdk_path = project / "Analysis/Mappings/native-sdk-scripts.json"
    sdk_document = load(read(sdk_path)) if sdk_path.is_file() else {}
    sdk_bindings = sdk_document.get("bindings", [])
    sdk_scripts = {}
    for binding in sdk_bindings:
        if binding.get("status") != "planned_sdk_binding":
            fail("UNITY_PREFAB_NATIVE_SDK_BINDING", str(sdk_path), "Exact SDK script plan required")
        for sid in binding["sourceObjectIds"]:
            if sid in sdk_scripts:
                fail("UNITY_PREFAB_NATIVE_SDK_DUPLICATE", sid, "Ambiguous source SDK mapping")
            sdk_scripts[sid] = binding
    evidence = load(read(project / "Analysis/Evidence/source-inputs.json"))
    for record in evidence:
        typed_path = safe(record["typedObjectsPath"])
        typed_raw = read(typed_path, max_bytes=128 * 1024 * 1024)
        if sha(typed_raw) != record["typedObjectsSha256"]:
            fail("UNITY_PREFAB_NATIVE_SOURCE_DRIFT", str(typed_path), "Source evidence changed after generation")
        doc = load(typed_raw, max_nodes=8_000_000)
        f_names = {f["id"]: f["name"] for f in doc["files"]}
        source_file_names.update({(record["sourceSha256"], fid): name for fid, name in f_names.items()})
        ids = {(o["identity"]["serializedFile"], o["identity"]["pathId"]): sid for sid, o in objects.items()
               if o["identity"]["containerSha256"] == record["sourceSha256"]}
        for obj in doc["objects"]:
            sid = ids.get((f_names[obj["file"]], obj["pathId"]))
            if sid is None and obj["type"] != "AssetBundle":
                continue
            schema = doc.get("embeddedSchemas", {}).get(obj.get("embeddedSchemaId")) or doc.get("borrowedSchemas", {}).get(obj.get("borrowedSchemaId"))
            if sid is not None and schema:
                shapes[sid] = schema
            if obj["type"] == "MonoScript" and obj.get("status") == "parsed":
                info = obj["data"]
                if sid in sdk_scripts:
                    binding = sdk_scripts[sid]
                    identity, target = binding["identity"], binding["expectedTuple"]
                    if (identity["assembly"], identity["namespace"], identity["class"]) != (info["m_AssemblyName"], info.get("m_Namespace") or "", info["m_ClassName"]):
                        fail("UNITY_PREFAB_NATIVE_SDK_IDENTITY", sid, "SDK plan/source class identity differs")
                    scripts[sid] = dict(type=(identity["namespace"] + "." if identity["namespace"] else "") + identity["class"],
                        assembly=binding["targetSource"]["assemblyDefinitionName"], guid=target["guid"], localId=str(target["fileID"]))
                    continue
                original = "Assets/Scripts/" + info["m_AssemblyName"].removesuffix(".dll") + "/"
                original += (info["m_Namespace"].replace(".", "/") + "/") if info.get("m_Namespace") else ""
                original += info["m_ClassName"] + ".cs"
                target = moved.get(original, original)
                if not (project / target).is_file():
                    continue
                scripts[sid] = dict(type=(info.get("m_Namespace") + "." if info.get("m_Namespace") else "") + info["m_ClassName"],
                                    assembly=info["m_AssemblyName"].removesuffix(".dll"), path=target,
                                    guid=_guid_meta(project / (target + ".meta")), localId="11500000")
            if obj["type"] != "AssetBundle" or obj.get("status") != "parsed":
                continue
            for logical, value in obj["data"].get("m_Container", []):
                ptr = value.get("asset", {})
                if ptr.get("fileId") != "0":
                    continue
                target_sid = ids.get((f_names[obj["file"]], ptr.get("pathId")))
                if target_sid is None:
                    continue
                source_type = objects[target_sid]["type"]
                suffixes = {"Sprite": {".asset"}, "Font": {".ttf", ".otf", ".fontsettings"},
                            "Material": {".mat"}, "Shader": {".asset", ".shader"},
                            "Texture2D": {".png", ".jpg", ".jpeg", ".asset"}, "GameObject": {".prefab"},
                            "AnimatorController": {".controller"}, "AnimationClip": {".anim"}}.get(source_type, set())
                # Only exact original container directory/stem plus a bounded
                # provider extension conversion is accepted, never name search.
                stem = str(Path(logical).with_suffix("")).casefold()
                matches = [p for p in source_files if str(Path(p).with_suffix("")).casefold() == stem
                           and Path(p).suffix.lower() in suffixes]
                if len(matches) == 1:
                    target = moved[matches[0]]
                    resource_bindings[target_sid] = dict(path=target, guid=_guid_meta(project / (target + ".meta")),
                                                        sourceLogicalPath=logical, sourceType=source_type)

    native_asset_path = project / "Analysis/Mappings/native-source-assets.json"
    native_asset_bindings = load(read(native_asset_path)) if native_asset_path.is_file() else []
    for row in native_asset_bindings:
        sid = row["sourceObjectId"]
        obj = objects.get(sid)
        if obj is None or obj["rawSha256"] != row["rawSha256"] or obj["type"] != row["type"]:
            fail("UNITY_PREFAB_NATIVE_ASSET_SOURCE", sid, "Exact source identity for native resource differs")
        preserved = row.get("replacesProviderAsset")
        if sid in resource_bindings and (not preserved or resource_bindings[sid]["guid"] != row["guid"]
                                          or resource_bindings[sid]["sourceType"] != row["type"]):
            fail("UNITY_PREFAB_NATIVE_ASSET_CONFLICT", sid, "Do not replace an already mapped original native resource")
        target_path = moved.get(row["path"], row["path"])
        if _guid_meta(project / (target_path + ".meta")) != row["guid"]:
            fail("UNITY_PREFAB_NATIVE_ASSET_GUID", sid, "Pinned native-created resource GUID changed")
        resource_bindings[sid] = dict(path=target_path, guid=row["guid"], localId=row["localId"], sourceType=row["type"],
                                     nativeSupplement=row["supplementManifestSha256"])
    code = load(read(project / "Analysis/Code/schema-carriers.json"))
    builtin_path = project / "Analysis/Evidence/builtin-schemas.json"
    if builtin_path.is_file():
        for receipt in load(read(builtin_path, max_bytes=32 * 1024 * 1024)):
            for obj in receipt["objects"]:
                identity = obj["identity"]
                matches = [sid for sid, source in objects.items() if source["identity"]["containerSha256"] == identity["sourceSha256"]
                    and source["identity"]["serializedFileSha256"] == identity["serializedFileSha256"]
                    and source["identity"]["serializedFile"] == identity["serializedFile"] and source["identity"]["pathId"] == identity["pathId"]]
                if len(matches) != 1:
                    continue  # Unreachable peer objects do not become native expectations.
                source = objects[matches[0]]
                if source["type"] != identity["type"] or source["rawSha256"] != identity["rawSha256"]:
                    fail("UNITY_PREFAB_BUILTIN_SCHEMA_IDENTITY", matches[0], "Schema/source object identity differs")
                shapes[matches[0]] = obj["schemaNode"]
    boolean_paths, character_paths = {}, {}
    for carrier in code:
        proposal = carrier["proposal"]
        paths = {f["name"] for f in proposal.get("fields", []) + proposal.get("inheritedFields", []) if f["csType"] == "bool"}
        characters = {f["name"] for f in proposal.get("fields", []) + proposal.get("inheritedFields", []) if f["csType"] == "char"}
        # Bounded 2021.3 UI.FontData declaration profile, checked against source
        # DummyDLL declaration and target uGUI. UInt8 alone is not a bool proof.
        if any(f["csType"] == "UnityEngine.UI.FontData" for f in proposal.get("inheritedFields", [])):
            paths.update("m_FontData." + n for n in ("m_BestFit", "m_AlignByGeometry", "m_RichText"))
        for source in carrier["sourceInstances"]:
            matches = [s for s, o in objects.items() if o["identity"]["containerSha256"] == source["containerSha256"]
                       and o["identity"]["pathId"] == source["pathId"]]
            if len(matches) > 1:
                fail("UNITY_PREFAB_BOOLEAN_IDENTITY_AMBIGUOUS", str(source), "Do not choose one serialized file by path ID alone")
            if matches:
                boolean_paths[matches[0]] = paths
                character_paths[matches[0]] = characters
    disabled = {(c["identity"]["assembly"].removesuffix(".dll"), c["identity"]["namespace"], c["identity"]["name"])
                for c in code if c["state"] == "disabled-unavailable-carrier"}
    exclusions = []
    driven_fields = {}
    slider_plan = None
    if any(o['type'] == 'MonoScript' and o['data'].get('m_ClassName') == 'Slider'
           and o['data'].get('m_Namespace') == 'UnityEngine.UI' and o['data'].get('m_AssemblyName') == 'UnityEngine.UI.dll'
           for o in objects.values()):
        from .unity_prefab_slider_layout import planned_slider_overrides
        owned = {r['path']: r for r in manifest['files']}
        class_pins = {sid: dict(path=row['path'], sha256=owned[row['path']]['sha256'])
                      for sid, row in scripts.items() if row.get('path') in owned}
        slider_plan = planned_slider_overrides(graph, sdk_bindings=sdk_document,
            source_candidate_root=project, source_candidate_manifest=manifest, source_class_pins=class_pins)
        for slider in slider_plan['sliders']:
            for row in slider['overrides']:
                target = driven_fields.setdefault(row['sourceObjectId'], {})
                if row['path'] in target:
                    fail('UNITY_PREFAB_DRIVEN_FIELD_COLLISION', row['path'], 'Only one proven driver may own a source field')
                target[row['path']] = row
    rect_geometry = rect_layout_expectations(graph, driven_fields)

    def flatten(sid, value, prop, loc, schema=None):
        driven = driven_fields.get(sid, {}).get(prop)
        if driven:
            if type(value) not in (int, float) or value != driven['sourceStoredValue']:
                fail('UNITY_PREFAB_DRIVEN_SOURCE_VALUE', loc, 'Driver plan must retain exact source field value')
            return [dict(path=prop, kind='float', floatValue=driven['expectedDrivenValue'],
                sourceStoredValue=value, mapping=driven['mapping'], driverEvidence=driven['driver'])]
        if isinstance(value, dict) and value.get("$type") == "UnityPPtr":
            edge = edges.get((sid, loc))
            if not edge:
                fail("UNITY_PREFAB_REFERENCE_EVIDENCE", loc, "Source PPtr lacks a graph edge")
            row = dict(path=prop, kind="reference", isNull=edge["status"] == "null")
            if row["isNull"]:
                return [row]
            target_sid = edge.get("targetSourceObjectId")
            if target_sid is None:
                if edge["status"] == "engine-provided-unverified":
                    match = re.fullmatch(r"PPtr<\$?([A-Za-z0-9_]+)>", (schema or {}).get("type", ""))
                    native_assets = {"Mesh", "Material", "Shader", "Font", "Texture", "Texture2D", "Sprite"}
                    raw_guid = edge.get("externalIdentity", {}).get("guid")
                    guid = unity_guid_text_from_serialized_hex(raw_guid) if raw_guid else None
                    if match and match[1] in native_assets and guid and re.fullmatch(r"0{16}[ef]0{15}", guid):
                        row.update(refGuid=guid, refLocalId=edge["pathId"], refType="UnityEngine." + match[1],
                                   sourceEngineIdentity=edge["externalIdentity"], sourceEnginePayload="not_exported;native-identity-readback-required")
                        return [row]
                fail("UNITY_PREFAB_NATIVE_REFERENCE_UNRESOLVED", loc, "Do not infer a missing source reference")
            target_obj = objects[target_sid]
            if target_sid in nodes or any(target_sid == c.get("sourceObjectId") for n in nodes.values() for c in n["orderedComponents"]):
                row["refSourceId"] = target_sid
            elif target_sid in scripts:
                target = scripts[target_sid]
                row.update(refGuid=target["guid"], refLocalId=target["localId"], refType="UnityEditor.MonoScript")
            elif target_sid in resource_bindings:
                target = resource_bindings[target_sid]
                if not target["guid"]:
                    fail("UNITY_PREFAB_NATIVE_REFERENCE_GUID", target["path"], "Missing native resource metadata")
                row.update(refGuid=target["guid"], refType="UnityEditor.Animations.AnimatorController"
                           if target_obj["type"] == "AnimatorController" else "UnityEngine." + target_obj["type"])
                if target.get("localId"):
                    row["refLocalId"] = target["localId"]
            else:
                fail("UNITY_PREFAB_NATIVE_REFERENCE_MAPPING", loc, "No exact original container or script mapping for " + target_obj["type"] + ": " + target_sid)
            return [row]
        if isinstance(value, dict):
            children = {c["name"]: c for c in (schema or {}).get("children", [])}
            result = []
            for key, child in value.items():
                result.extend(flatten(sid, child, prop + "." + key if prop else key, loc + "/" + key, children.get(key)))
            return result
        if isinstance(value, list):
            result = [dict(path=prop + ".Array.size", kind="integer", intValue=len(value))]
            node = next((c for c in (schema or {}).get("children", []) if c.get("type") == "Array"), {})
            child_schema = next((c for c in node.get("children", []) if c.get("name") == "data"), None)
            for i, child in enumerate(value):
                result.extend(flatten(sid, child, prop + ".Array.data[" + str(i) + "]", loc + "/" + str(i), child_schema))
            return result
        if isinstance(value, bool) or (schema or {}).get("type") == "bool" or prop in boolean_paths.get(sid, ()):
            if value not in (True, False, 0, 1):
                fail("UNITY_PREFAB_NATIVE_BOOLEAN", loc, "Not a source boolean")
            return [dict(path=prop, kind="boolean", boolValue=bool(value))]
        if isinstance(value, int):
            if prop in character_paths.get(sid, set()):
                if not 0 <= value <= 65535:
                    fail("UNITY_PREFAB_NATIVE_CHARACTER", loc, "Source char must be one UTF-16 code unit")
                return [dict(path=prop, kind="character", intValue=value)]
            if (schema or {}).get("type") in ("UInt8", "unsigned char"):
                if not 0 <= value <= 255:
                    fail("UNITY_PREFAB_NATIVE_BYTE", loc, "Source byte exceeds UInt8 storage")
                return [dict(path=prop, kind="byte", intValue=value)]
            return [dict(path=prop, kind="integer", intValue=value)]
        if isinstance(value, float):
            return [dict(path=prop, kind="float", floatValue=value)]
        if isinstance(value, str):
            return [dict(path=prop, kind="string", stringValue=value)]
        fail("UNITY_PREFAB_NATIVE_FIELD_SHAPE", loc, "Unsupported serialized source shape")

    root_plans = []
    root_rows = bind_source_root_rows(graph["roots"], report["roots"], source_file_names)
    for index, root in enumerate(graph["roots"]):
        source_id = root["sourceObjectId"]
        row = root_rows[source_id]
        original = row["providerPath"].removeprefix("ExportedProject/")
        path = moved.get(original, original)
        node_plans = []

        def visit(sid, indices):
            node = nodes[sid]
            if node.get("tag") != 0:
                fail("UNITY_PREFAB_NATIVE_TAG_MAPPING", sid, "Source custom/builtin tag ID requires original tag-name evidence")
            component_plans = []
            for component in node["orderedComponents"]:
                cid = component["sourceObjectId"]
                obj = objects[cid]
                comp_type, assembly, unavailable = "UnityEngine." + obj["type"], _ASSEMBLIES.get(obj["type"]), False
                if obj["type"] == "MonoBehaviour":
                    script_edge = edges[(cid, "$/m_Script")]
                    script = scripts.get(script_edge["targetSourceObjectId"])
                    if not script:
                        fail("UNITY_PREFAB_NATIVE_SCRIPT_MAPPING", cid, "Exact native script class mapping unavailable")
                    comp_type, assembly = script["type"], script["assembly"]
                    namespace, _, name = comp_type.rpartition(".")
                    unavailable = (assembly, namespace, name) in disabled
                if not assembly:
                    fail("UNITY_PREFAB_NATIVE_COMPONENT_TYPE", obj["type"], "Target SDK assembly mapping needs exact evidence")
                fields = []
                children = {c["name"]: c for c in shapes.get(cid, {}).get("children", [])}
                for key, value in obj["data"].items():
                    renderer_field = renderer_scalar_mapping(obj["type"], obj.get("classId"), graph["sourceUnityVersions"],
                        "6000.6.2f1", key, value, children.get(key))
                    if renderer_field is not None:
                        fields.append(renderer_field)
                        continue
                    if key == "m_LocalPosition" and cid in rect_geometry:
                        for axis in ("x", "y"):
                            fields.append(dict(path=key + "." + axis, kind="float", floatValue=rect_geometry[cid]["position"][axis],
                                               sourceStoredValue=value[axis], mapping="RectTransform-anchor-pivot-derived-XY"))
                        fields.extend(flatten(cid, value["z"], key + ".z", "$/" + key + "/z"))
                        continue
                    if key == "m_Name" and obj["type"] == "MonoBehaviour" and value == "":
                        exclusions.append(dict(sourceObjectId=cid, field=key, reason="source-empty-MonoBehaviour-header;class-identity-verified-separately"))
                        continue
                    if key == "m_Enabled":
                        if value not in (True, False, 0, 1):
                            fail("UNITY_PREFAB_NATIVE_BOOLEAN", cid, "Invalid source enabled byte")
                        fields.append(dict(path=key, kind="boolean", boolValue=bool(value)))
                        continue
                    fields.extend(flatten(cid, value, key, "$/" + key, children.get(key)))
                component_plans.append(dict(sourceId=cid, type=comp_type, assembly=assembly,
                                            disabledUnavailable=unavailable, fields=fields))
            node_plans.append(dict(sourceId=sid, indices=indices, name=node["name"], active=node["active"],
                                   layer=node["layer"], tag="Untagged", components=component_plans))
            for i, child in enumerate(node["childSourceObjectIds"]):
                visit(child, indices + [i])

        visit(source_id, [])
        root_plans.append(dict(path=path, sourceId=source_id, isRepresentative=index == 0, nodes=node_plans))
    return dict(schemaVersion=1, targetUnityVersion="6000.6.2f1", outputRelative="Analysis/Readback/unity-prefab-static.json",
                sourceCandidateManifestSha256=expected_manifest, roots=root_plans,
                reconstructRoots=bool(sdk_bindings or native_asset_bindings),
                fieldMappingExclusions=exclusions, resourceBindings=resource_bindings, sourceDrivenSliderPlan=slider_plan,
                sourceBusiness="not_run", unavailablePresentation="not-accepted")


def execute(project, expected_manifest, output, editor, budget_seconds=600, headless=False):
    """Run only a fresh owned candidate; never bind to an existing Editor."""
    from .native import now, stamp, redact_log
    project, editor = safe(project), safe(editor)
    if editor.name not in ("Unity", "Unity.exe") or not editor.is_file():
        fail("UNITY_PREFAB_EDITOR", str(editor), "Existing exact Unity executable required")
    if type(budget_seconds) is not int or not 1 <= budget_seconds <= 1200:
        fail("UNITY_PREFAB_EDITOR_BUDGET", "$", "Expected 1..1200 seconds")
    plan = prepare(project, expected_manifest)
    plan["headless"] = headless
    processes = subprocess.check_output(["ps", "-axo", "pid=,comm="], text=True).splitlines()
    conflicts = [r for r in processes if r.strip().split(maxsplit=1)[-1].endswith(
        ("/Contents/MacOS/Unity", "/Contents/MacOS/CocosCreator", "/Unity.exe", "/CocosCreator.exe"))]
    if conflicts:
        fail("UNITY_PREFAB_EDITOR_BUSY", "$", "Another main Editor is running; retain offline candidate")
    out = new_output(output, [project, editor])
    work = out / "UnityProject"
    shutil.copytree(project, work)
    for row in load(read(project / "manifest.json"))["files"]:
        if sha(read(inside(work, row["path"]), max_bytes=256 * 1024 * 1024)) != row["sha256"]:
            fail("UNITY_PREFAB_NATIVE_COPY_DRIFT", row["path"], "Candidate changed while copying")
    helper = Path(__file__).parent / "targets/unity_source/UnityPrefabStaticReadback.cs"
    helper_dir = work / "Assets/Editor/MonkeyUnitySource"
    helper_dir.mkdir(parents=True)
    helpers = []
    for source in sorted(helper.parent.glob("*.cs")):
        dest = helper_dir / source.name
        dest.write_bytes(read(source))
        helpers.append(dict(path=dest.relative_to(work).as_posix(), sha256=sha(read(source))))
    plan_path = work / "Analysis/Tasks/native-prefab-plan.json"
    write_json(plan_path, plan)
    env = dict(os.environ, MONKEY_UNITY_PREFAB_PLAN=str(plan_path),
               MONKEY_UNITY_PREFAB_PLAN_SHA256=sha(read(plan_path)))
    result = dict(schemaVersion=1, status="started", sourceCandidateManifestSha256=expected_manifest,
                  nativePlanSha256=sha(read(plan_path)), helperSha256=sha(read(helper)),
                  startedUtc=stamp(now()), sourceCodeExecuted=False, business="not_run", player="not_run")
    result["helpers"] = helpers
    result["graphics"] = "not_run_headless" if headless else "requested"
    receipt = out / "execution-result.json"
    log, console = out / "editor.log", out / "console.log"
    child = None
    try:
        with console.open("wb") as stream:
            child = subprocess.Popen([str(editor), "-batchmode", *( ["-nographics"] if headless else []), "-quit", "-projectPath", str(work),
                "-executeMethod", "MonkeyUnitySource.UnityPrefabStaticReadback.Run", "-logFile", str(log)],
                env=env, cwd=work, stdout=stream, stderr=subprocess.STDOUT)
            result["pid"] = child.pid
            write_json(receipt, result)
            try:
                child.wait(timeout=budget_seconds)
            except subprocess.TimeoutExpired:
                result["stopReason"] = "fixed-native-budget"
                child.terminate()
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    pass
    finally:
        if child is not None and child.poll() is None:
            if "stopReason" not in result:
                result["stopReason"] = "caller-interruption"
                child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass
        result.update(endedUtc=stamp(now()), processExited=child is not None and child.poll() is not None,
                      exitCode=child.poll() if child is not None else None)
        result["status"] = "pending_child_exit" if child is not None and child.poll() is None else "failed"
        rb = inside(work, plan["outputRelative"])
        if rb.exists():
            body = read(rb, max_bytes=128 * 1024 * 1024)
            result.update(readbackPath=str(rb), readbackSha256=sha(body))
            readback = load(body, max_nodes=8_000_000)
            result["nativeReadbackStatus"] = readback.get("status")
            if child is not None and child.poll() == 0 and readback.get("status") == "completed":
                result["status"] = "native-verified-subset"
            elif child is not None and child.poll() == 1 and readback.get("status") == "partial":
                result["status"] = "native-partial"
        result["redactedLog"] = redact_log(log) if log.exists() else None
        write_json(receipt, result)
    if result["status"] in ("native-partial", "native-verified-subset"):
        result["independentReopen"] = cold_reopen(out, editor, budget_seconds)
        if result["independentReopen"]["status"] != "cold-reopen-verified-subset":
            result["status"] = "failed-independent-reopen"
        result["savedFiles"] = [dict(path=p.relative_to(work).as_posix(), sha256=sha(read(p, max_bytes=256 * 1024 * 1024)), bytes=p.stat().st_size)
            for folder in ("Assets", "Packages", "ProjectSettings", "Analysis")
            for p in sorted((work / folder).rglob("*")) if p.is_file()
            and not p.relative_to(work).as_posix().startswith("Assets/Editor/MonkeyUnitySource")]
        write_json(receipt, result)
    return result


def freeze(native_output, expected_execution, output):
    """Select exact native-saved bytes, excluding Library and verifier code."""
    from . import __version__
    from .io import encoded
    out = safe(native_output)
    raw = read(out / "execution-result.json", max_bytes=128 * 1024 * 1024)
    if sha(raw) != expected_execution:
        fail("UNITY_PREFAB_NATIVE_RECEIPT_DRIFT", str(out), "Exact completed execution receipt required")
    receipt = load(raw, max_nodes=8_000_000)
    if receipt.get("status") not in ("native-partial", "native-verified-subset") or receipt.get("processExited") is not True:
        fail("UNITY_PREFAB_NATIVE_NOT_COMPLETE", str(out), "A failed or pending native run cannot be selected")
    cold = receipt.get("independentReopen", {})
    if cold.get("status") != "cold-reopen-verified-subset" or cold.get("processExited") is not True:
        fail("UNITY_PREFAB_COLD_NOT_COMPLETE", str(out), "Actual independent reopen is required")
    work = out / "UnityProject"
    manifest = load(read(work / "manifest.json"))
    if sha(read(work / "manifest.json")) != receipt["sourceCandidateManifestSha256"]:
        fail("UNITY_PREFAB_NATIVE_SOURCE_MANIFEST", str(work), "Original generated manifest changed")
    for row in receipt["savedFiles"]:
        data = read(inside(work, row["path"]), max_bytes=256 * 1024 * 1024)
        if len(data) != row["bytes"] or sha(data) != row["sha256"]:
            fail("UNITY_PREFAB_SAVED_DRIFT", row["path"], "Native-saved candidate changed after process exit")
    for r in (receipt, cold):
        path = safe(r["readbackPath"])
        if not path.is_relative_to(work) or sha(read(path, max_bytes=128 * 1024 * 1024)) != r["readbackSha256"]:
            fail("UNITY_PREFAB_NATIVE_READBACK_DRIFT", str(path), "Readback does not match completed receipt")
    selected = new_output(output, [out])
    for row in receipt["savedFiles"]:
        dest = inside(selected, row["path"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(inside(work, row["path"]), dest)
    write_json(selected / "Analysis/Native/execution-result.json", receipt)
    files = [dict(path=p.relative_to(selected).as_posix(), sha256=sha(read(p, max_bytes=256 * 1024 * 1024)), bytes=p.stat().st_size)
             for p in sorted(selected.rglob("*")) if p.is_file()]
    namespace = manifest.get("namespace") or "unity-source/" + sha(encoded(sorted(manifest["selectedSourceRoots"], key=lambda r: (r["sourceSha256"], r["file"], r["pathId"]))))[:24]
    result = dict(manifest, files=files, namespace=namespace, toolVersion=__version__, native=receipt["status"],
                  independentReopen=cold["status"], sourceCandidateManifestSha256=receipt["sourceCandidateManifestSha256"],
                  executionReceiptSha256=expected_execution, staticPresentation="not_run_headless" if receipt.get("graphics") == "not_run_headless" else "see-native-readback",
                  business="not_run", player="not_run")
    write_json(selected / "manifest.json", result)
    return dict(status="needs_action", candidate=str(selected), manifestSha256=sha(read(selected / "manifest.json")),
                native=receipt["status"], independentReopen=cold["status"], staticPresentation=result["staticPresentation"])
