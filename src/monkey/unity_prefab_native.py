"""Source-derived expectations for the selected Unity Prefab native bridge."""
from pathlib import Path
import re
import os
import shutil
import subprocess
import time

from .io import inside, load, read, safe, sha, write_json, new_output
from .sources.compiled import fail
from .unity_prefab_recovery import source_inputs
from .native_selection import _guid_meta


_ASSEMBLIES = {
    **{n: "UnityEngine.CoreModule" for n in ("Transform", "RectTransform", "SpriteRenderer", "MeshRenderer", "MeshFilter", "LineRenderer")},
    **{n: "UnityEngine.UIModule" for n in ("CanvasRenderer", "Canvas", "CanvasGroup")},
    "ParticleSystem": "UnityEngine.ParticleSystemModule", "ParticleSystemRenderer": "UnityEngine.ParticleSystemModule",
    "Animator": "UnityEngine.AnimationModule",
}


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
    resource_bindings, scripts, shapes = {}, {}, {}
    evidence = load(read(project / "Analysis/Evidence/source-inputs.json"))
    for record in evidence:
        typed_path = safe(record["typedObjectsPath"])
        typed_raw = read(typed_path, max_bytes=128 * 1024 * 1024)
        if sha(typed_raw) != record["typedObjectsSha256"]:
            fail("UNITY_PREFAB_NATIVE_SOURCE_DRIFT", str(typed_path), "Source evidence changed after generation")
        doc = load(typed_raw, max_nodes=8_000_000)
        f_names = {f["id"]: f["name"] for f in doc["files"]}
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
                            "Texture2D": {".png", ".jpg", ".jpeg", ".asset"}, "GameObject": {".prefab"}}.get(source_type, set())
                # Only exact original container directory/stem plus a bounded
                # provider extension conversion is accepted, never name search.
                stem = str(Path(logical).with_suffix("")).casefold()
                matches = [p for p in source_files if str(Path(p).with_suffix("")).casefold() == stem
                           and Path(p).suffix.lower() in suffixes]
                if len(matches) == 1:
                    target = moved[matches[0]]
                    resource_bindings[target_sid] = dict(path=target, guid=_guid_meta(project / (target + ".meta")),
                                                        sourceLogicalPath=logical, sourceType=source_type)

    code = load(read(project / "Analysis/Code/schema-carriers.json"))
    disabled = {(c["identity"]["assembly"].removesuffix(".dll"), c["identity"]["namespace"], c["identity"]["name"])
                for c in code if c["state"] == "disabled-unavailable-carrier"}
    exclusions = []

    def flatten(sid, value, prop, loc, schema=None):
        if isinstance(value, dict) and value.get("$type") == "UnityPPtr":
            edge = edges.get((sid, loc))
            if not edge:
                fail("UNITY_PREFAB_REFERENCE_EVIDENCE", loc, "Source PPtr lacks a graph edge")
            row = dict(path=prop, kind="reference", isNull=edge["status"] == "null")
            if row["isNull"]:
                return [row]
            target_sid = edge.get("targetSourceObjectId")
            if target_sid is None:
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
                row.update(refGuid=target["guid"], refType="UnityEngine." + target_obj["type"])
            else:
                fail("UNITY_PREFAB_NATIVE_REFERENCE_MAPPING", loc, "No exact original container or script mapping for " + target_obj["type"])
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
        if isinstance(value, bool) or (schema or {}).get("type") == "bool":
            if value not in (True, False, 0, 1):
                fail("UNITY_PREFAB_NATIVE_BOOLEAN", loc, "Not a source boolean")
            return [dict(path=prop, kind="boolean", boolValue=bool(value))]
        if isinstance(value, int):
            return [dict(path=prop, kind="integer", intValue=value)]
        if isinstance(value, float):
            return [dict(path=prop, kind="float", floatValue=value)]
        if isinstance(value, str):
            return [dict(path=prop, kind="string", stringValue=value)]
        fail("UNITY_PREFAB_NATIVE_FIELD_SHAPE", loc, "Unsupported serialized source shape")

    root_plans = []
    for index, root in enumerate(graph["roots"]):
        source_id = root["sourceObjectId"]
        row = report["roots"][index]
        original = row["providerPath"].removeprefix("ExportedProject/")
        path = moved.get(original, original)
        node_plans = []

        def visit(sid, indices):
            node = nodes[sid]
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
                    if key == "m_Name" and obj["type"] == "MonoBehaviour" and value == "":
                        exclusions.append(dict(sourceObjectId=cid, field=key, reason="source-empty-MonoBehaviour-header;class-identity-verified-separately"))
                        continue
                    if key == "m_Enabled" and obj["type"] == "MonoBehaviour":
                        fields.append(dict(path=key, kind="boolean", boolValue=bool(value)))
                        continue
                    fields.extend(flatten(cid, value, key, "$/" + key, children.get(key)))
                component_plans.append(dict(sourceId=cid, type=comp_type, assembly=assembly,
                                            disabledUnavailable=unavailable, fields=fields))
            node_plans.append(dict(sourceId=sid, indices=indices, name=node["name"], active=node["active"],
                                   layer=node["layer"], components=component_plans))
            for i, child in enumerate(node["childSourceObjectIds"]):
                visit(child, indices + [i])

        visit(source_id, [])
        root_plans.append(dict(path=path, sourceId=source_id, isRepresentative=index == 0, nodes=node_plans))
    return dict(schemaVersion=1, targetUnityVersion="6000.6.2f1", outputRelative="Analysis/Readback/unity-prefab-static.json",
                sourceCandidateManifestSha256=expected_manifest, roots=root_plans,
                fieldMappingExclusions=exclusions, resourceBindings=resource_bindings,
                sourceBusiness="not_run", unavailablePresentation="not-accepted")


def execute(project, expected_manifest, output, editor, budget_seconds=600):
    """Run only a fresh owned candidate; never bind to an existing Editor."""
    from .native import now, stamp, redact_log
    project, editor = safe(project), safe(editor)
    if editor.name not in ("Unity", "Unity.exe") or not editor.is_file():
        fail("UNITY_PREFAB_EDITOR", str(editor), "Existing exact Unity executable required")
    if type(budget_seconds) is not int or not 1 <= budget_seconds <= 1200:
        fail("UNITY_PREFAB_EDITOR_BUDGET", "$", "Expected 1..1200 seconds")
    plan = prepare(project, expected_manifest)
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
    helper_path = work / "Assets/Editor/MonkeyUnitySource/UnityPrefabStaticReadback.cs"
    helper_path.parent.mkdir(parents=True)
    helper_path.write_bytes(read(helper))
    plan_path = work / "Analysis/Tasks/native-prefab-plan.json"
    write_json(plan_path, plan)
    env = dict(os.environ, MONKEY_UNITY_PREFAB_PLAN=str(plan_path),
               MONKEY_UNITY_PREFAB_PLAN_SHA256=sha(read(plan_path)))
    result = dict(schemaVersion=1, status="started", sourceCandidateManifestSha256=expected_manifest,
                  nativePlanSha256=sha(read(plan_path)), helperSha256=sha(read(helper)),
                  startedUtc=stamp(now()), sourceCodeExecuted=False, business="not_run", player="not_run")
    receipt = out / "execution-result.json"
    log, console = out / "editor.log", out / "console.log"
    child = None
    try:
        with console.open("wb") as stream:
            child = subprocess.Popen([str(editor), "-batchmode", "-quit", "-projectPath", str(work),
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
    return result
