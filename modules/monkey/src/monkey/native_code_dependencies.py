"""Supplement immutable selections with exact producer compilation proofs."""
from pathlib import Path
import re

from . import __version__
from .io import inside, load, new_output, read, safe, sha, write_json
from .native_selection import _relative, _hash_file, _template_profile, _carrier_profiles
from .sources.compiled import fail

_SPINE_ROOT = "Assets/Plugins/Spine38"
_SPINE_UPSTREAM_COMMIT = "8b4844bd4b193ba9e54487ed397a777993cbad56"
_SPINE_RUNTIME_SOURCE_VERSION = "3.8.99 skeleton compatible branch3.8"
_SPINE_RUNTIME_FILES = {
    "spine-csharp.dll": "spine-csharp.dll",
    "spine-unity.dll": "spine-unity.dll",
    "Shaders/Spine-SkeletonGraphic.shader": "Shaders/Spine-SkeletonGraphic.shader",
    "LICENSE": "LICENSE",
}
_SPINE_HELPERS = {
    "Assets/Game/Scripts/Presentation/Recovered/Spine/UnitySpineGraphicMaterialPresentation.cs",
    "Assets/Game/Scripts/Presentation/Recovered/Spine/UnitySpineSourceIdentity.cs",
}


def spine_runtime_closure(candidate, rows, native, manifest, included):
    """Verify and return the exact native Spine stage needed by selected files.

    The owner-manifest-pinned import plan is the stage authority. Stage copy
    source payloads live in the separate UnityPlan producer, so this consumer
    verifies every declared target against the pinned native/owner inventories
    and never resolves those source strings by guessing a neighboring folder.
    """
    included = set(included)
    if not (included & _SPINE_HELPERS or any(path.startswith(_SPINE_ROOT + "/") for path in included)):
        return None
    from .layout import standard
    plan_path = standard.locate(manifest, "importPlan")
    plan_row = rows.get(plan_path)
    if plan_row is None:
        fail("SPINE_STAGE_PLAN_UNOWNED", plan_path, "Spine selection requires the manifest-owned Unity import plan")
    plan_digest, plan_size, plan_raw = _hash_file(candidate, plan_path)
    if plan_digest != plan_row.get("sha256") or plan_size != plan_row.get("bytes"):
        fail("SPINE_STAGE_PLAN_DRIFT", plan_path, "Import plan differs from its frozen manifest identity")
    plan = load(plan_raw, max_nodes=8_000_000)
    stage = plan.get("spineNativeStage")
    if (not isinstance(stage, dict) or stage.get("schemaVersion") != 1
            or stage.get("contract") != "monkey-spine-native-stage/1" or stage.get("target") != "unity"
            or stage.get("sourceManifestSha256") != plan.get("sourceManifestSha256")
            or stage.get("sourceIrSha256") != plan.get("sourceIrSha256")
            or stage.get("runtimeLicenseIncluded") is not True
            or type(stage.get("runtimeFilesVerified")) is not int
            or stage.get("runtimeFilesVerified", 0) < len(_SPINE_RUNTIME_FILES)):
        fail("SPINE_STAGE_UNVERIFIED", plan_path, "Pinned Spine stage is missing a verified runtime/license scope")

    copies = stage.get("copies")
    if not isinstance(copies, list):
        fail("SPINE_STAGE_COPIES_INVALID", plan_path, "Spine stage copies must be a list")
    by_target = {}
    for row in copies:
        if not isinstance(row, dict):
            fail("SPINE_STAGE_COPIES_INVALID", plan_path, "Malformed Spine stage copy row")
        target = _relative(row.get("target"), "spineNativeStage.copies.target")
        if not target.startswith("Assets/") or target in by_target:
            fail("SPINE_STAGE_COPIES_INVALID", target, "Unsafe or duplicate Spine stage target")
        if (not isinstance(row.get("source"), str) or not row["source"]
                or not isinstance(row.get("role"), str)
                or not isinstance(row.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
                or type(row.get("bytes")) is not int or row["bytes"] < 0):
            fail("SPINE_STAGE_COPIES_INVALID", target, "Malformed Spine stage source identity")
        by_target[target] = row

    package_path = _SPINE_ROOT + "/manifest.json"
    package_copy = by_target.get(package_path)
    if (not package_copy or package_copy.get("role") != "runtime-manifest"
            or package_copy.get("sha256") != stage.get("runtimeManifestSha256")):
        fail("SPINE_RUNTIME_MANIFEST_MISSING", package_path, "Stage does not bind its exact runtime manifest")

    selected_targets = {}

    def select_target(path, stage_row=None, *, expected_sha=None, expected_bytes=None):
        row = stage_row or by_target.get(path)
        if row is None or row.get("target") != path:
            fail("SPINE_RUNTIME_DEPENDENCY_MISSING", path, "Required file is absent from the pinned Spine stage")
        if expected_sha and row.get("sha256") != expected_sha:
            fail("SPINE_RUNTIME_DEPENDENCY_HASH", path, "Stage hash differs from its parent runtime/evidence manifest")
        if expected_bytes is not None and row.get("bytes") != expected_bytes:
            fail("SPINE_RUNTIME_DEPENDENCY_SIZE", path, "Stage byte count differs from its parent runtime/evidence manifest")
        if row.get("role") not in ("runtime-manifest", "verified-runtime-license-or-shader",
                                   "verified-editor-only-spine-runtime", "unity-meta",
                                   "source-profile-shader", "source-profile-ui-graphic-shader",
                                   "unity-native-spine-helper"):
            fail("SPINE_RUNTIME_DEPENDENCY_ROLE", path, "Stage role is not an adopted Spine runtime asset")
        expected = native.get(path, rows.get(path, {}).get("sha256"))
        size_authority = rows.get(path, {}).get("bytes")
        if expected is None:
            fail("SPINE_RUNTIME_DEPENDENCY_UNOWNED", path, "Spine target is absent from candidate/native inventories")
        actual, size, _ = _hash_file(candidate, path)
        if actual != row["sha256"] or actual != expected or size != row["bytes"]:
            fail("SPINE_RUNTIME_DEPENDENCY_DRIFT", path, "Candidate target differs from stage and owner/native hashes")
        if size_authority is not None and path not in native and size != size_authority:
            fail("SPINE_RUNTIME_DEPENDENCY_DRIFT", path, "Non-native target differs from generation manifest bytes")
        selected_targets[path] = dict(path=path, sha256=actual, bytes=size, role=row["role"])
        return read(inside(candidate, path), max_bytes=256 * 1024 * 1024)

    package_raw = select_target(package_path, package_copy)
    package_manifest = load(package_raw, max_nodes=100_000)
    package_files = package_manifest.get("files")
    if (package_manifest.get("name") != "Spine 3.8 runtime"
            or package_manifest.get("upstreamCommit") != _SPINE_UPSTREAM_COMMIT
            or package_manifest.get("sourceVersion") != _SPINE_RUNTIME_SOURCE_VERSION
            or not isinstance(package_files, dict)
            or not set(_SPINE_RUNTIME_FILES).issubset(package_files)
            or package_manifest.get("compiledAgainst") != "Unity6000.6.2f1"):
        fail("SPINE_RUNTIME_MANIFEST_INVALID", package_path, "Runtime manifest lacks required versioned files")
    for relative, target_relative in _SPINE_RUNTIME_FILES.items():
        path = _SPINE_ROOT + "/" + target_relative
        expected = package_files.get(relative)
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            fail("SPINE_RUNTIME_MANIFEST_INVALID", package_path,
                 "Runtime manifest has an invalid hash for " + relative)
        copy = by_target.get(path)
        if not copy or copy.get("role") != "verified-runtime-license-or-shader":
            fail("SPINE_RUNTIME_DEPENDENCY_MISSING", path, "Runtime package file lacks its verified stage row")
        select_target(path, copy, expected_sha=expected)

    editor = stage.get("editorRuntimeVariant")
    if (not isinstance(editor, dict) or editor.get("status") != "verified_editor_source_build"
            or editor.get("importPolicy") != "paired_editor_only_assemblies_player_pair_excludes_editor"):
        fail("SPINE_EDITOR_PAIR_UNVERIFIED", plan_path, "Stage does not declare the verified Editor/Player pair policy")
    evidence_path = editor.get("sourceEvidencePath")
    evidence_sha = editor.get("sourceEvidenceSha256")
    if not isinstance(evidence_path, str) or not Path(evidence_path).is_absolute():
        fail("SPINE_EDITOR_EVIDENCE_INVALID", plan_path, "Expected pinned absolute editor build evidence path")
    evidence_file = safe(evidence_path)
    evidence_raw = read(evidence_file, max_bytes=128 * 1024 * 1024)
    if sha(evidence_raw) != evidence_sha:
        fail("SPINE_EDITOR_EVIDENCE_DRIFT", evidence_path, "Editor build evidence differs from stage SHA")
    evidence = load(evidence_raw, max_nodes=8_000_000)
    pairing = evidence.get("pairing")
    if (evidence.get("status") != "verified_editor_source_build"
            or evidence.get("sourceManifestSha256") != editor.get("sourceManifestSha256")
            or evidence.get("upstreamCommit") != package_manifest.get("upstreamCommit")
            or evidence.get("unityVersion") != "6000.6.2f1"
            or evidence.get("cocosCompatibilityFallbacksIncluded") is not False
            or not isinstance(pairing, dict)
            or any(pairing.get(key) is not True for key in (
                "playerAssembliesRetainedUnmodified", "editorCoreAssemblyNameVersionMatchesPlayerCore",
                "editorUnityReferencesEditorCore", "playerUnityAssemblyReferencesPlayerCore"))):
        fail("SPINE_EDITOR_EVIDENCE_INVALID", evidence_path, "Editor runtime pair proof is incomplete or mismatched")
    if evidence.get("playerAssemblyHashes") != {
            "spine-csharp.dll": package_files["spine-csharp.dll"],
            "spine-unity.dll": package_files["spine-unity.dll"]}:
        fail("SPINE_PLAYER_PAIR_MISMATCH", evidence_path, "Editor evidence player pair differs from the pinned runtime manifest")
    assemblies = editor.get("assemblies")
    evidence_assemblies = evidence.get("editorAssemblies")
    if not isinstance(assemblies, dict) or set(assemblies) != {"spine-csharp.dll", "spine-unity.dll"}:
        fail("SPINE_EDITOR_PAIR_MISSING", plan_path, "Expected both Editor assemblies")
    if not isinstance(evidence_assemblies, dict):
        fail("SPINE_EDITOR_PAIR_MISSING", evidence_path, "Editor build evidence lacks its assembly pair")
    editor_targets = []
    for filename in ("spine-csharp.dll", "spine-unity.dll"):
        assembly = assemblies[filename]
        evidence_assembly = evidence_assemblies.get(filename)
        target = _SPINE_ROOT + "/EditorRuntime/" + filename
        copy = by_target.get(target)
        if (not isinstance(evidence_assembly, dict) or not copy
                or copy.get("role") != "verified-editor-only-spine-runtime"
                or assembly.get("runtimeImportPath") != target
                or assembly.get("sha256") != evidence_assembly.get("sha256")
                or assembly.get("bytes") != evidence_assembly.get("bytes")
                or assembly.get("sha256") != copy.get("sha256")
                or assembly.get("bytes") != copy.get("bytes")):
            fail("SPINE_EDITOR_PAIR_MISMATCH", target, "Editor pair differs across stage, runtime evidence or copy row")
        player_ref = evidence_assembly.get("playerReferenceIdentity")
        if (not isinstance(player_ref, dict)
                or player_ref.get("name") != assembly.get("assemblyName")
                or player_ref.get("version") != assembly.get("assemblyVersion")):
            fail("SPINE_EDITOR_PAIR_MISMATCH", target, "Editor assembly identity differs from its Player counterpart")
        select_target(target, copy, expected_sha=evidence_assembly.get("sha256"),
                      expected_bytes=evidence_assembly.get("bytes"))
        editor_targets.append(target)

    # Both runtime pairs require PluginImporter metadata that prevents the two
    # copies from being loaded together. Validate the exact staged and saved
    # metadata bytes, not a filename-based platform assumption.
    player_targets = [_SPINE_ROOT + "/spine-csharp.dll", _SPINE_ROOT + "/spine-unity.dll"]
    meta_targets = []
    for pair, player in ((player_targets, True), (editor_targets, False)):
        for dll in pair:
            meta_path = dll + ".meta"
            meta_copy = by_target.get(meta_path)
            if (not meta_copy or meta_copy.get("role") != "unity-meta"
                    or (meta_path not in rows and meta_path not in native)):
                fail("SPINE_PLUGIN_META_MISSING", meta_path, "DLL importer scope is not hash-pinned by the stage")
            meta_raw = select_target(meta_path, meta_copy)
            meta_text = meta_raw.decode("utf-8")
            if player:
                any_ok = re.search(r"(?m)^      enabled: 1\s*\n      settings:\s*\n        Exclude Editor: 1\s*$", meta_text)
                editor_ok = re.search(r"(?m)^      Editor: Editor\s*\n    second:\s*\n      enabled: 0\s*$", meta_text)
            else:
                any_ok = re.search(r"(?m)^      enabled: 0\s*\n      settings: \{\}\s*$", meta_text)
                editor_ok = re.search(r"(?m)^      Editor: Editor\s*\n    second:\s*\n      enabled: 1\s*$", meta_text)
            if not any_ok or not editor_ok or "PluginImporter:" not in meta_text:
                fail("SPINE_PLUGIN_META_SCOPE_MISMATCH", meta_path, "Player/Editor PluginImporter scope is not paired")
            meta_targets.append(meta_path)

    # Carry the package manifest, license and all shipped shaders with their
    # owner/native GUID metadata. The exact DLL metas above are stage-declared.
    stage_shaders = []
    for role, expected in (
            ("source-profile-shader", "Assets/Game/Content/Shaders/UnitySpineSourceProfile.shader"),
            ("source-profile-ui-graphic-shader", "Assets/Game/Content/Shaders/UnitySpineGraphicProfile.shader")):
        row = by_target.get(expected)
        if not row or row.get("role") != role:
            fail("SPINE_PROFILE_SHADER_MISSING", expected, "Stage does not bind its producer profile shader")
        select_target(expected, row)
        stage_shaders.append(expected)
        meta_path = expected + ".meta"
        meta_copy = by_target.get(meta_path)
        if not meta_copy or meta_copy.get("role") != "unity-meta":
            fail("SPINE_PROFILE_SHADER_META_MISSING", meta_path, "Source-profile shader GUID metadata is not stage-pinned")
        select_target(meta_path, meta_copy)
        meta_targets.append(meta_path)

    helper_paths = []
    for path in sorted(_SPINE_HELPERS & included):
        helper = by_target.get(path)
        if not helper or helper.get("role") != "unity-native-spine-helper":
            fail("SPINE_HELPER_STAGE_MISMATCH", path, "Selected Spine component helper is not the staged producer template")
        profile = _template_profile(path, helper.get("sha256"))
        if profile is None or profile[0] != Path(path).name:
            fail("SPINE_HELPER_TEMPLATE_UNKNOWN", path, "Staged helper differs from the bundled exact producer template")
        selected = rows.get(path) or {}
        if selected.get("sha256") != helper["sha256"] or selected.get("bytes") != helper["bytes"]:
            fail("SPINE_HELPER_TEMPLATE_DRIFT", path, "Saved helper differs from its frozen stage declaration")
        meta_path = path + ".meta"
        meta_copy = by_target.get(meta_path)
        if not meta_copy or meta_copy.get("role") != "unity-meta":
            fail("SPINE_HELPER_META_MISSING", meta_path, "Helper metadata GUID is absent from Spine stage")
        select_target(meta_path, meta_copy)
        helper_paths.append(path)
        meta_targets.append(meta_path)

    # Preserve available owner-bound folder metadata for the added stage files.
    for selected_path in list(selected_targets):
        parent = Path(selected_path).parent
        while str(parent) not in (".", "Assets") and str(parent).startswith("Assets/"):
            folder_meta = str(parent) + ".meta"
            if folder_meta in rows or folder_meta in native:
                actual, size, _ = _hash_file(candidate, folder_meta)
                expected = native.get(folder_meta, rows.get(folder_meta, {}).get("sha256"))
                if expected is None or actual != expected:
                    fail("SPINE_FOLDER_META_DRIFT", folder_meta, "Spine folder metadata differs from saved owner")
                selected_targets.setdefault(folder_meta, dict(path=folder_meta, sha256=actual, bytes=size,
                    role="native-folder-meta" if folder_meta in native else "generated-folder-meta"))
            parent = parent.parent

    included.update(selected_targets)
    return dict(schemaVersion=1, contract=stage["contract"],
        sourceImportPlanPath=plan_path, sourceImportPlanSha256=plan_digest,
        sourceManifestSha256=stage["sourceManifestSha256"], sourceIrSha256=stage["sourceIrSha256"],
        runtimeManifestPath=package_path, runtimeManifestSha256=stage["runtimeManifestSha256"],
        editorEvidenceSha256=evidence_sha, editorEvidenceStatus=evidence["status"],
        editorRuntimeImportPolicy=editor["importPolicy"],
        playerAssemblies=player_targets, editorAssemblies=editor_targets,
        pluginImporterMetas=sorted(set(meta_targets)), licensePath=_SPINE_ROOT + "/LICENSE",
        runtimeShaders=[_SPINE_ROOT + "/Shaders/Spine-SkeletonGraphic.shader", *stage_shaders],
        helperPaths=helper_paths, files=sorted(selected_targets.values(), key=lambda row: row["path"]),
        assemblyLoadVerificationStatus=(editor.get("assemblyLoadVerification") or {}).get("status", "unknown"),
        dynamicRuntime="not_run")



def sdk_producer_declarations(root, files, producer, closure):
    """Describe already-proven SDK payloads; never infer CLR or migration compatibility.

    Assembly names/references below are declarations from the hash-bound build
    receipt, not a second PE reader. The consumer must inspect the actual DLLs
    and resolve historical MonoScript identities with its existing native tools.
    """
    if closure is None:
        return []
    plan_path = closure["sourceImportPlanPath"]
    plan_raw = read(inside(producer, plan_path), max_bytes=128 * 1024 * 1024)
    if sha(plan_raw) != closure["sourceImportPlanSha256"]:
        fail("SDK_DECLARATION_PLAN_DRIFT", plan_path, "SDK declaration plan changed after verification")
    plan = load(plan_raw, max_nodes=8_000_000)
    stage = plan["spineNativeStage"]
    editor = stage["editorRuntimeVariant"]
    evidence_raw = read(safe(editor["sourceEvidencePath"]), max_bytes=128 * 1024 * 1024)
    if sha(evidence_raw) != editor["sourceEvidenceSha256"]:
        fail("SDK_DECLARATION_EVIDENCE_DRIFT", plan_path, "SDK build evidence changed after verification")
    evidence = load(evidence_raw, max_nodes=8_000_000)
    runtime = load(read(inside(root, closure["runtimeManifestPath"])))
    assemblies, by_guid = [], {}
    for role, paths in (("editor-only", closure["editorAssemblies"]),
                        ("player-only", closure["playerAssemblies"])):
        for path in paths:
            meta_path = path + ".meta"
            # Both payload and meta were checked by the closure and target audit.
            # A GUID is still independently required: hashes do not imply one.
            text = read(inside(root, meta_path)).decode("utf-8")
            guids = re.findall(r"(?m)^guid: ([0-9a-f]{32})\s*$", text)
            if len(guids) != 1 or guids[0] == "0" * 32 or guids[0] in by_guid:
                fail("SDK_DECLARATION_GUID_INVALID", meta_path, "SDK DLL GUID must be unique, nonzero and explicit")
            name = Path(path).name
            declared = evidence["editorAssemblies"][name]
            identity = (dict(name=declared["assemblyName"], version=declared["assemblyVersion"])
                        if role == "editor-only" else declared["playerReferenceIdentity"])
            if (not isinstance(identity.get("name"), str) or not identity["name"]
                    or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}", str(identity.get("version")))):
                fail("SDK_DECLARATION_IDENTITY_INVALID", path, "Build evidence lacks its declared assembly identity")
            staged = editor["assemblies"][name]
            if identity != dict(name=staged["assemblyName"], version=staged["assemblyVersion"]):
                fail("SDK_DECLARATION_IDENTITY_INVALID", path, "Stage and build declared identities differ")
            if role == "editor-only" and declared.get("references", []) != staged.get("references", []):
                fail("SDK_DECLARATION_IDENTITY_INVALID", path, "Stage and build declared references differ")
            row = dict(path=path, guid=guids[0], sha256=files[path]["sha256"],
                bytes=files[path]["bytes"], metaPath=meta_path,
                metaSha256=files[meta_path]["sha256"], role=role,
                declaredAssemblyIdentity=identity,
                declaredReferences=declared.get("references", []) if role == "editor-only" else None,
                referenceEvidence="pinned-editor-build" if role == "editor-only" else "consumer-inspection-required",
                nativeMonoScriptTable=dict(status="not_run", scripts=[],
                    reason="existing-native-evidence-does-not-inventory-DLL-MonoScript-localIDs",
                    requiredVerification="consumer-native-GetClass-assembly-and-localID-readback"))
            assemblies.append(row)
            by_guid[guids[0]] = path
    references = []
    for path in sorted(files):
        if not path.endswith((".prefab", ".asset", ".unity")):
            continue
        raw = read(inside(root, path), max_bytes=256 * 1024 * 1024)
        if not any(guid.encode() in raw for guid in by_guid):
            continue
        # Only literal serialized m_Script PPtrs are claimed, without mapping
        # their local IDs to CLR names or rewriting any asset.
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            fail("SDK_SCRIPT_REFERENCE_UNSUPPORTED", path, "SDK script reference is not UTF-8 serialized text")
        local_id = None
        for line in text.splitlines():
            header = re.fullmatch(r"--- !u![0-9]+ &(-?[0-9]+)(?: stripped)?", line)
            if line.startswith("---"):
                local_id = int(header[1]) if header else None
            if not re.match(r"^\s+m_Script:", line):
                continue
            if not any(guid in line for guid in by_guid):
                continue
            match = re.fullmatch(r"\s+m_Script: \{fileID: (-?[0-9]+), guid: ([0-9a-f]{32}), type: 3\}", line)
            if not match or local_id is None or local_id == 0 or int(match[1]) == 0:
                fail("SDK_SCRIPT_REFERENCE_UNSUPPORTED", path, "Expected explicit object and script GUID/localID tuple")
            references.append(dict(path=path, sha256=files[path]["sha256"],
                objectLocalId=local_id, scriptGuid=match[2], scriptLocalId=int(match[1]),
                assemblyPath=by_guid[match[2]], typeResolution="consumer-native-readback-required"))
    license_path = closure["licensePath"]
    return [dict(schemaVersion=1, contract="monkey-native-sdk-declaration/1", sdkId="spine-3.8",
        evidenceClass="producer-declaration-not-migration-approval",
        sourceManifestSha256=closure["sourceManifestSha256"], sourceIrSha256=closure["sourceIrSha256"],
        sourceImportPlanPath=plan_path, sourceImportPlanSha256=closure["sourceImportPlanSha256"],
        runtimeManifestPath=closure["runtimeManifestPath"], runtimeManifestSha256=closure["runtimeManifestSha256"],
        upstreamCommit=runtime["upstreamCommit"], sourceVersion=runtime["sourceVersion"],
        compiledAgainst=runtime["compiledAgainst"],
        editorBuildEvidence=dict(sha256=editor["sourceEvidenceSha256"], status=evidence["status"]),
        assemblies=sorted(assemblies, key=lambda row: row["path"]),
        license=dict(path=license_path, sha256=files[license_path]["sha256"],
            terms="retained-verbatim-not-license-entitlement-or-redistribution-approval"),
        runtimeShaders=closure["runtimeShaders"], producerHelpers=closure["helperPaths"],
        serializedScriptReferences=references,
        coverage=dict(assemblyIdentity="pinned-build-declaration", publicTypes="consumer-pe-cli-inspection-required",
            playerAssemblyReferences="consumer-inspection-required", serializedReferences="literal-selected-m_Script-tuples-only",
            nativeTypeResolution="not-performed", retainedSdkCompatibility="not-claimed",
            migration="not-performed", packageCacheAssemblies="not-analyzed"))]


def audit(candidate, expected_manifest, producer_candidate, expected_producer_manifest, output):
    root, producer = safe(candidate), safe(producer_candidate)
    raw = read(root / "manifest.json", max_bytes=128 * 1024 * 1024)
    source_raw = read(producer / "manifest.json", max_bytes=128 * 1024 * 1024)
    if sha(raw) != expected_manifest or sha(source_raw) != expected_producer_manifest:
        fail("CANDIDATE_SHA_MISMATCH", str(root), "Supplement requires exact target and original producer manifests")
    manifest, source = load(raw, max_nodes=8_000_000), load(source_raw, max_nodes=8_000_000)
    if (manifest.get("sourceCandidateManifestSha256") != expected_producer_manifest
            or manifest.get("targetProfile") != "unity-6000.6.2f1-ugui"
            or source.get("targetProfile") != manifest.get("targetProfile")):
        fail("PRODUCER_LINEAGE_MISMATCH", str(root), "Target must retain this exact original producer identity")
    files, names, folded = {}, {}, set()
    for row in manifest.get("files", []):
        path = _relative(row.get("path"), "files.path")
        if path == "manifest.json" or path.casefold() in folded:
            fail("INVALID_MANIFEST", path, "Duplicate or reserved path")
        folded.add(path.casefold())
        data = read(inside(root, path), max_bytes=256 * 1024 * 1024)
        if sha(data) != row.get("sha256") or len(data) != row.get("bytes"):
            fail("CANDIDATE_DRIFT", path, "Target differs from its frozen inventory")
        files[path] = row
        if path.endswith(".cs"):
            names.setdefault(Path(path).name, []).append(path)
    for path in root.rglob("*"):
        if path.is_symlink():
            fail("SYMLINK_PATH", str(path), "Frozen candidates cannot contain links")
        if path.is_file() and path.relative_to(root).as_posix() not in set(files) | {"manifest.json"}:
            fail("CANDIDATE_UNOWNED", str(path), "Use a clean frozen candidate")
    source_files = {row["path"]: row for row in source.get("files", [])}
    for path in ("Packages/manifest.json", "Packages/packages-lock.json"):
        if path not in files:
            fail("PACKAGE_LOCK_MISSING", path, "External package dependencies require their frozen manifest and lock")
    spine_paths = _SPINE_HELPERS | {path for path in files if path.startswith(_SPINE_ROOT + "/")}
    has_selected_spine = bool(spine_paths & (set(files) | set(manifest.get("selection", {}).get("prefabs", []))))
    expected_spine = None
    if has_selected_spine:
        readback_path = "Analysis/Readback/editor-readback.json"
        readback_raw = read(inside(producer, readback_path), max_bytes=128 * 1024 * 1024)
        if sha(readback_raw) != manifest.get("sourceNativeReadbackSha256"):
            fail("SPINE_SOURCE_READBACK_MISMATCH", readback_path, "Spine supplement source readback is not pinned")
        readback = load(readback_raw, max_nodes=8_000_000)
        native = {row.get("path"): row.get("sha256") for row in readback.get("nativeFiles", [])
                  if isinstance(row, dict)}
        expected_spine = spine_runtime_closure(producer, source_files, native, source, set(files))
        for row in expected_spine["files"]:
            actual = files.get(row["path"])
            if not actual or actual["sha256"] != row["sha256"] or actual["bytes"] != row["bytes"]:
                fail("SPINE_RUNTIME_SELECTION_INCOMPLETE", row["path"], "Selected SDK file must match the complete producer closure")
        if manifest.get("spineRuntimeClosure") != expected_spine:
            fail("SPINE_RUNTIME_CLOSURE_MISMATCH", str(root), "Frozen Spine closure differs from the owner-manifest stage proof")
    elif manifest.get("spineRuntimeClosure") is not None:
        fail("SPINE_RUNTIME_CLOSURE_UNEXPECTED", str(root), "Non-Spine selection contains an unbound Spine runtime closure")
    carrier_profiles, plan_evidence = _carrier_profiles(producer, source_files, source)
    scripts, uncovered = [], []
    for path, row in sorted(files.items()):
        if not path.endswith(".cs"):
            continue
        profile = _template_profile(path, row["sha256"])
        kind = "exact-producer-template"
        if profile is None and path in carrier_profiles:
            source_row = source_files[path]
            if row["sha256"] == source_row["sha256"] and row["bytes"] == source_row["bytes"]:
                profile, kind = carrier_profiles[path], "exact-generated-disabled-static-field-carrier"
        if profile is None:
            uncovered.append(dict(path=path, sha256=row["sha256"], code="UNANALYZED_CSHARP_DEPENDENCIES"))
            continue
        if profile[0] != Path(path).name:
            fail("PRODUCER_TEMPLATE_IDENTITY_MISMATCH", path, "Hash belongs to a differently named producer script")
        requires = []
        for name in profile[1]:
            matches = names.get(name, [])
            if len(matches) != 1:
                fail("DECLARED_CODE_DEPENDENCY_MISSING", path, "Expected exactly one project dependency: " + name)
            dependency = matches[0]
            requires.append(dict(path=dependency, sha256=files[dependency]["sha256"]))
        scripts.append(dict(path=path, sha256=row["sha256"], profile=kind,
            requires=requires, externalDependencies="System/UnityEngine/locked-uGUI"))
    result = dict(schema="monkey-native-code-dependency-supplement/1", toolVersion=__version__,
        producerImplementation=[dict(path=name, sha256=sha(read(Path(__file__).parent / name)))
            for name in ("native_code_dependencies.py", "native_selection.py", "prefab_static_carriers.py")],
        status="proven-subset" if uncovered else "all-inventoried-csharp-producer-proven",
        targetManifestSha256=expected_manifest, producerCandidateManifestSha256=expected_producer_manifest,
        carrierPlanEvidence=plan_evidence, packageFiles=[dict(path=path, sha256=files[path]["sha256"])
            for path in ("Packages/manifest.json", "Packages/packages-lock.json") if path in files],
        scripts=scripts, uncovered=uncovered,
        spineRuntimeClosure=expected_spine,
        sdkProducerDeclarations=sdk_producer_declarations(root, files, producer, expected_spine),
        originalDiagnostics=manifest.get("diagnostics", []),
        boundary="Supplement only; original manifests/warnings unchanged. Compile proofs do not establish native compilation, physical input or recovered business behavior.")
    out = new_output(output, [root, producer])
    write_json(out / "code-dependency-supplement.json", result)
    return result
