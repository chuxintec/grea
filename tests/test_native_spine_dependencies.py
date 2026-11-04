import hashlib
import json
from pathlib import Path

import pytest

from monkey.io import sha
from monkey.native_code_dependencies import spine_runtime_closure
from monkey.native_selection import _template_profile
from monkey.sources.compiled import ParseError


def _plugin_meta(index, player):
    if player:
        any_scope = "      enabled: 1\n      settings:\n        Exclude Editor: 1\n"
        editor_enabled = 0
    else:
        any_scope = "      enabled: 0\n      settings: {}\n"
        editor_enabled = 1
    return ("fileFormatVersion: 2\n" + f"guid: {index:032x}\n" +
        "PluginImporter:\n  platformData:\n  - first:\n      Any:\n    second:\n" + any_scope +
        "  - first:\n      Editor: Editor\n    second:\n      enabled: " + str(editor_enabled) + "\n")


def _fixture(tmp_path):
    root = tmp_path / "candidate"
    root.mkdir()
    source_manifest_sha = "1" * 64
    source_ir_sha = "2" * 64
    upstream = "8b4844bd4b193ba9e54487ed397a777993cbad56"
    rows, copies = {}, []

    def add(path, raw, role=None):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        digest = sha(raw)
        rows[path] = dict(path=path, sha256=digest, bytes=len(raw), owner="generated")
        if role:
            copies.append(dict(source="fixture-source/" + Path(path).name, target=path,
                               sha256=digest, bytes=len(raw), role=role))
        return digest, len(raw)

    runtime_root = "Assets/Plugins/Spine38"
    package_payloads = {
        "spine-csharp.dll": b"player-spine-csharp",
        "spine-unity.dll": b"player-spine-unity",
        "Shaders/Spine-SkeletonGraphic.shader": b"Shader \"Spine/Graphic\" {}\n",
        "LICENSE": b"Spine license text\n",
    }
    package_hashes = {name: sha(raw) for name, raw in package_payloads.items()}
    package_raw = json.dumps(dict(name="Spine 3.8 runtime", upstreamCommit=upstream,
        sourceVersion="3.8.99 skeleton compatible branch3.8", compiledAgainst="Unity6000.6.2f1",
        files=package_hashes), sort_keys=True).encode()
    package_path = runtime_root + "/manifest.json"
    package_sha, _ = add(package_path, package_raw, "runtime-manifest")
    for relative, raw in package_payloads.items():
        add(runtime_root + "/" + relative, raw, "verified-runtime-license-or-shader")

    editor_payloads = {"spine-csharp.dll": b"editor-spine-csharp", "spine-unity.dll": b"editor-spine-unity"}
    editor_hashes = {name: sha(raw) for name, raw in editor_payloads.items()}
    evidence = dict(status="verified_editor_source_build", sourceManifestSha256=source_manifest_sha,
        upstreamCommit=upstream, unityVersion="6000.6.2f1", cocosCompatibilityFallbacksIncluded=False,
        pairing={key: True for key in ("playerAssembliesRetainedUnmodified",
            "editorCoreAssemblyNameVersionMatchesPlayerCore", "editorUnityReferencesEditorCore",
            "playerUnityAssemblyReferencesPlayerCore")},
        playerAssemblyHashes={name: package_hashes[name] for name in editor_payloads}, editorAssemblies={})
    evidence_path = tmp_path / "editor-runtime-evidence.json"
    evidence_raw = json.dumps(evidence, sort_keys=True).encode()
    evidence_path.write_bytes(evidence_raw)
    editor_assemblies, editor_targets = {}, []
    for name, raw in editor_payloads.items():
        target = runtime_root + "/EditorRuntime/" + name
        digest, size = add(target, raw, "verified-editor-only-spine-runtime")
        identity = name.removesuffix(".dll")
        record = dict(assemblyName=identity, assemblyVersion="0.0.0.0", bytes=size,
            sha256=digest, runtimeImportPath=target, references=[], unityEditorReference=name == "spine-unity.dll")
        editor_assemblies[name] = record
        evidence["editorAssemblies"][name] = dict(assemblyName=identity, assemblyVersion="0.0.0.0",
            bytes=size, sha256=digest, runtimeImportPath=target,
            playerReferenceIdentity=dict(name=identity, version="0.0.0.0"),
            unityEditorReference=name == "spine-unity.dll")
        editor_targets.append(target)

    player_targets = [runtime_root + "/spine-csharp.dll", runtime_root + "/spine-unity.dll"]
    for index, target in enumerate(player_targets + editor_targets, 1):
        add(target + ".meta", _plugin_meta(index, index <= 2).encode(), "unity-meta")
    # Rewrite the evidence with both independently pinned editor assembly rows.
    evidence_raw = json.dumps(evidence, sort_keys=True).encode()
    evidence_path.write_bytes(evidence_raw)

    spine_targets = Path(__file__).parents[1] / "src/monkey/targets/spine"
    helper_paths = [
        "Assets/Game/Scripts/Presentation/Recovered/Spine/UnitySpineGraphicMaterialPresentation.cs",
        "Assets/Game/Scripts/Presentation/Recovered/Spine/UnitySpineSourceIdentity.cs",
    ]
    for index, path in enumerate(helper_paths, 10):
        add(path, (spine_targets / Path(path).name).read_bytes(), "unity-native-spine-helper")
        add(path + ".meta", f"fileFormatVersion: 2\nguid: {index:032x}\n".encode(), "unity-meta")
    for index, (path, role) in enumerate((
        ("Assets/Game/Content/Shaders/UnitySpineSourceProfile.shader", "source-profile-shader"),
        ("Assets/Game/Content/Shaders/UnitySpineGraphicProfile.shader", "source-profile-ui-graphic-shader")), 20):
        raw = (Path(__file__).parents[1] / "src/monkey/targets/materials/spine" / Path(path).name).read_bytes()
        add(path, raw, role)
        add(path + ".meta", f"fileFormatVersion: 2\nguid: {index:032x}\n".encode(), "unity-meta")

    editor_variant = dict(status="verified_editor_source_build",
        importPolicy="paired_editor_only_assemblies_player_pair_excludes_editor",
        sourceEvidencePath=str(evidence_path), sourceEvidenceSha256=sha(evidence_raw),
        sourceManifestSha256=source_manifest_sha, assemblies=editor_assemblies)
    stage = dict(schemaVersion=1, contract="monkey-spine-native-stage/1", target="unity",
        sourceManifestSha256=source_manifest_sha, sourceIrSha256=source_ir_sha,
        runtimeLicenseIncluded=True, runtimeFilesVerified=4, runtimeManifestSha256=package_sha,
        editorRuntimeVariant=editor_variant, copies=copies)
    plan_path = "Assets/Game/Editor/Conversion/import-plan.json"
    plan_raw = json.dumps(dict(sourceManifestSha256=source_manifest_sha,
        sourceIrSha256=source_ir_sha, spineNativeStage=stage), sort_keys=True).encode()
    add(plan_path, plan_raw)
    manifest = dict(schemaVersion=1, targetProfile="unity-6000.6.2f1-ugui", namespace="fixture-spine",
        projectLayout="monkey-project/2.0.0", files=list(rows.values()))
    return root, rows, manifest, set(helper_paths), stage


def test_bundled_spine_helper_profiles_are_exact_and_minimal():
    spine = Path(__file__).parents[1] / "src/monkey/targets/spine"
    graphic, identity = (spine / name for name in (
        "UnitySpineGraphicMaterialPresentation.cs", "UnitySpineSourceIdentity.cs"))
    assert _template_profile(str(graphic), hashlib.sha256(graphic.read_bytes()).hexdigest()) == (
        "UnitySpineGraphicMaterialPresentation.cs", ("NativeStaticMaskIdentity.cs",))
    assert _template_profile(str(identity), hashlib.sha256(identity.read_bytes()).hexdigest()) == (
        "UnitySpineSourceIdentity.cs", ())


def test_stage_closure_includes_paired_assemblies_and_required_payloads(tmp_path):
    root, rows, manifest, included, _ = _fixture(tmp_path)
    result = spine_runtime_closure(root, rows, {}, manifest, included)
    assert len(result["playerAssemblies"]) == len(result["editorAssemblies"]) == 2
    assert len(result["pluginImporterMetas"]) == 8
    assert result["licensePath"] == "Assets/Plugins/Spine38/LICENSE"
    assert "Assets/Plugins/Spine38/Shaders/Spine-SkeletonGraphic.shader" in result["runtimeShaders"]
    assert result["dynamicRuntime"] == "not_run"


def test_missing_player_core_is_rejected(tmp_path):
    root, rows, manifest, included, _ = _fixture(tmp_path)
    path = "Assets/Plugins/Spine38/spine-csharp.dll"
    (root / path).unlink()
    rows.pop(path)
    with pytest.raises(ParseError, match="SPINE_RUNTIME_DEPENDENCY_UNOWNED"):
        spine_runtime_closure(root, rows, {}, manifest, included)


def test_editor_player_pair_hash_drift_is_rejected(tmp_path):
    root, rows, manifest, included, stage = _fixture(tmp_path)
    stage["editorRuntimeVariant"]["assemblies"]["spine-unity.dll"]["sha256"] = "0" * 64
    plan_path = "Assets/Game/Editor/Conversion/import-plan.json"
    raw = json.dumps(dict(sourceManifestSha256=stage["sourceManifestSha256"],
        sourceIrSha256=stage["sourceIrSha256"], spineNativeStage=stage), sort_keys=True).encode()
    (root / plan_path).write_bytes(raw)
    rows[plan_path].update(sha256=sha(raw), bytes=len(raw))
    with pytest.raises(ParseError, match="SPINE_EDITOR_PAIR_MISMATCH"):
        spine_runtime_closure(root, rows, {}, manifest, included)


def test_missing_editor_plugin_meta_is_rejected(tmp_path):
    root, rows, manifest, included, _ = _fixture(tmp_path)
    path = "Assets/Plugins/Spine38/EditorRuntime/spine-csharp.dll.meta"
    (root / path).unlink()
    rows.pop(path)
    with pytest.raises(ParseError, match="SPINE_PLUGIN_META_MISSING"):
        spine_runtime_closure(root, rows, {}, manifest, included)


def test_editor_plugin_meta_scope_drift_is_rejected(tmp_path):
    root, rows, manifest, included, stage = _fixture(tmp_path)
    path = "Assets/Plugins/Spine38/EditorRuntime/spine-csharp.dll.meta"
    bad = _plugin_meta(51, True).encode()
    (root / path).write_bytes(bad)
    rows[path].update(sha256=sha(bad), bytes=len(bad))
    for copy in stage["copies"]:
        if copy["target"] == path:
            copy.update(sha256=sha(bad), bytes=len(bad))
            break
    plan_path = "Assets/Game/Editor/Conversion/import-plan.json"
    plan_raw = json.dumps(dict(sourceManifestSha256=stage["sourceManifestSha256"],
        sourceIrSha256=stage["sourceIrSha256"], spineNativeStage=stage), sort_keys=True).encode()
    (root / plan_path).write_bytes(plan_raw)
    rows[plan_path].update(sha256=sha(plan_raw), bytes=len(plan_raw))
    with pytest.raises(ParseError, match="SPINE_PLUGIN_META_SCOPE_MISMATCH"):
        spine_runtime_closure(root, rows, {}, manifest, included)


def test_non_spine_selection_does_not_add_spine_files(tmp_path):
    root, rows, manifest, _, _ = _fixture(tmp_path)
    included = {"Assets/Game/Content/Prefabs/Plain.prefab"}
    assert spine_runtime_closure(root, rows, {}, manifest, included) is None
    assert not any(path.startswith("Assets/Plugins/Spine38/") for path in included)


def test_freeze_registers_full_spine_pairs_and_assets_in_candidate_manifest(tmp_path, monkeypatch):
    from monkey import native_selection

    root, rows, manifest, _, _ = _fixture(tmp_path)
    def add_owned(path, raw):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        row = dict(path=path, sha256=sha(raw), bytes=len(raw), owner="generated")
        rows[path] = row
        manifest["files"].append(row)
        return raw

    identity_path = "Assets/Game/Scripts/Presentation/StaticMasks/NativeStaticMaskIdentity.cs"
    identity_raw = (Path(__file__).parents[1] / "src/monkey/targets/NativeStaticMaskIdentity.cs").read_bytes()
    add_owned(identity_path, identity_raw)
    identity_meta = f"fileFormatVersion: 2\nguid: {'a' * 32}\n".encode()
    add_owned(identity_path + ".meta", identity_meta)

    helper_guid = {}
    for path in (
        "Assets/Game/Scripts/Presentation/Recovered/Spine/UnitySpineGraphicMaterialPresentation.cs",
        "Assets/Game/Scripts/Presentation/Recovered/Spine/UnitySpineSourceIdentity.cs"):
        meta = (root / (path + ".meta")).read_text()
        helper_guid[path] = meta.split("guid: ", 1)[1].splitlines()[0]
    prefab_path = "Assets/Game/Prefabs/Spine.prefab"
    prefab = ("--- !u!114 &1\nMonoBehaviour:\n" + "\n".join(
        f"  m_Script: {{fileID: 11500000, guid: {helper_guid[path]}, type: 3}}"
        for path in helper_guid) + "\n--- !u!114 &2\nMonoBehaviour:\n"
        + f"  m_Script: {{fileID: -12345, guid: {4:032x}, type: 3}}\n").encode()
    add_owned(prefab_path, prefab)
    add_owned(prefab_path + ".meta", f"fileFormatVersion: 2\nguid: {'b' * 32}\n".encode())
    add_owned("Packages/manifest.json", b'{"dependencies":{"com.unity.ugui":"2.0.0"}}\n')
    add_owned("Packages/packages-lock.json", b'{"dependencies":{"com.unity.ugui":{"version":"2.0.0"}}}\n')
    add_owned("ProjectSettings/ProjectVersion.txt", b"m_EditorVersion: 6000.6.2f1\n")

    manifest_raw = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    (root / "manifest.json").write_bytes(manifest_raw)
    native_files = [dict(path=prefab_path, sha256=sha(prefab))]
    rb = dict(unityVersion="6000.6.2f1", status="partial", missingScripts=0,
        nativeScope="saved-source-node-subset", sourceGraphVerification="saved-source-node-subset",
        editableRoundtrip=True, sceneReopened=True, nativeFiles=native_files)
    rb_raw = json.dumps(rb).encode()
    readback_path = root / "Analysis/Readback/editor-readback.json"
    readback_path.parent.mkdir(parents=True, exist_ok=True)
    readback_path.write_bytes(rb_raw)
    verify = dict(candidateManifestSha256=sha(manifest_raw), staticValidation="pass",
        nativeStaticValidation="pass", editorValidation="partial", diagnostics=[])
    monkeypatch.setattr(native_selection, "_native_verification",
                        lambda *args: (rb, rb_raw, verify))

    output = tmp_path / "frozen-spine"
    result = native_selection.freeze(root, [prefab_path], output, sha(manifest_raw), sha(rb_raw))
    manifest_paths = {row["path"] for row in result["files"]}
    expected = {
        "Assets/Plugins/Spine38/spine-csharp.dll", "Assets/Plugins/Spine38/spine-unity.dll",
        "Assets/Plugins/Spine38/EditorRuntime/spine-csharp.dll",
        "Assets/Plugins/Spine38/EditorRuntime/spine-unity.dll",
        "Assets/Plugins/Spine38/spine-csharp.dll.meta", "Assets/Plugins/Spine38/spine-unity.dll.meta",
        "Assets/Plugins/Spine38/EditorRuntime/spine-csharp.dll.meta",
        "Assets/Plugins/Spine38/EditorRuntime/spine-unity.dll.meta",
        "Assets/Plugins/Spine38/LICENSE", "Assets/Plugins/Spine38/manifest.json",
        "Assets/Plugins/Spine38/Shaders/Spine-SkeletonGraphic.shader",
        "Assets/Game/Content/Shaders/UnitySpineSourceProfile.shader",
        "Assets/Game/Content/Shaders/UnitySpineGraphicProfile.shader",
    }
    assert expected.issubset(manifest_paths)
    assert result["spineRuntimeClosure"]["helperPaths"] == sorted(helper_guid)
    assert {edge["kind"] for edge in result["adoptionDependencies"]["edges"]} == {"csharp-compile"}
    by_path = {row["path"]: row for row in result["files"]}
    for path in expected:
        assert (output / path).is_file()
        assert sha((output / path).read_bytes()) == by_path[path]["sha256"]
    from monkey.native_code_dependencies import audit
    audited = audit(output, sha((output / "manifest.json").read_bytes()), root, sha(manifest_raw),
                    tmp_path / "code-dependency-audit")
    assert audited["spineRuntimeClosure"]["playerAssemblies"] == result["spineRuntimeClosure"]["playerAssemblies"]
    sdk, = audited["sdkProducerDeclarations"]
    assert sdk["contract"] == "monkey-native-sdk-declaration/1"
    assert {row["role"] for row in sdk["assemblies"]} == {"editor-only", "player-only"}
    assert len(sdk["assemblies"]) == 4
    assert all(row["nativeMonoScriptTable"]["status"] == "not_run"
               and row["nativeMonoScriptTable"]["scripts"] == [] for row in sdk["assemblies"])
    assert sdk["license"]["sha256"] == by_path[sdk["license"]["path"]]["sha256"]
    assert sdk["serializedScriptReferences"] == [dict(path=prefab_path, sha256=sha(prefab),
        objectLocalId=2, scriptGuid=f"{4:032x}", scriptLocalId=-12345,
        assemblyPath="Assets/Plugins/Spine38/EditorRuntime/spine-unity.dll",
        typeResolution="consumer-native-readback-required")]
    assert sdk["coverage"]["retainedSdkCompatibility"] == "not-claimed"
    assert sdk["coverage"]["publicTypes"] == "consumer-pe-cli-inspection-required"
    # A self-consistent target manifest cannot omit a non-GUID runtime file.
    removed = "Assets/Plugins/Spine38/spine-csharp.dll"
    (output / removed).unlink()
    result["files"] = [row for row in result["files"] if row["path"] != removed]
    changed = json.dumps(result).encode()
    (output / "manifest.json").write_bytes(changed)
    with pytest.raises(ParseError, match="SPINE_RUNTIME_SELECTION_INCOMPLETE"):
        audit(output, sha(changed), root, sha(manifest_raw), tmp_path / "incomplete-audit")


def test_sdk_declaration_rejects_ambiguous_guid_and_unbound_script_tuple(tmp_path):
    from monkey.native_code_dependencies import sdk_producer_declarations
    root, rows, manifest, included, _ = _fixture(tmp_path)
    closure = spine_runtime_closure(root, rows, {}, manifest, included)
    files = {row["path"]: row for row in closure["files"]}
    dll = closure["editorAssemblies"][0]
    meta = root / (dll + ".meta")
    original = meta.read_text()
    meta.write_text(original.replace(f"{3:032x}", f"{1:032x}"))
    with pytest.raises(ParseError, match="SDK_DECLARATION_GUID_INVALID"):
        sdk_producer_declarations(root, files, root, closure)
    meta.write_text(original)
    asset = "Assets/Bad.asset"
    raw = f"  m_Script: {{fileID: 17, guid: {3:032x}, type: 3}}\n".encode()
    (root / asset).write_bytes(raw)
    files[asset] = dict(path=asset, sha256=sha(raw), bytes=len(raw))
    with pytest.raises(ParseError, match="SDK_SCRIPT_REFERENCE_UNSUPPORTED"):
        sdk_producer_declarations(root, files, root, closure)
