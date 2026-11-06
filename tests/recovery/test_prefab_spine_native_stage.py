import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from grea.recovery.prefab_spine_native_stage import (
    SpineNativeStageError,
    _meta_payload,
    attach_unity_stage,
    creator_profile_handoff,
    emit_unity_stage,
    prepare_unity_stage,
)
from grea.recovery.prefab_spine_native import SOURCE_SCALE_EVIDENCE


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return path


class SpineNativeStageTests(unittest.TestCase):
    def test_plugin_platform_metadata_separates_player_and_editor_pairs(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            root = Path(temp)
            player = _meta_payload("Test", "Assets/Plugins/Spine38/spine-unity.dll", root,
                                   "plugin", plugin_scope="player_exclude_editor")
            editor = _meta_payload("Test", "Assets/Plugins/Spine38/EditorRuntime/spine-unity.dll", root,
                                   "plugin", plugin_scope="editor_only")
            player_body = (root / player["source"]).read_text()
            editor_body = (root / editor["source"]).read_text()
            self.assertIn("Any:\n    second:\n      enabled: 1", player_body)
            self.assertIn("Editor: Editor\n    second:\n      enabled: 0", player_body)
            self.assertIn("Exclude Editor: 1", player_body)
            self.assertIn("Any:\n    second:\n      enabled: 0", editor_body)
            self.assertIn("Editor: Editor\n    second:\n      enabled: 1", editor_body)
            self.assertIn("DefaultValueInitialized: true", editor_body)
            with self.assertRaises(SpineNativeStageError):
                _meta_payload("Test", "Assets/a.dll", root, "plugin", plugin_scope="all_platforms")

    def test_stage_copies_editor_pair_and_excludes_player_pair_from_editor(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            args = self.make_fixture(Path(temp))
            target, native, emission, source_ir, closure, closure_freeze, runtime_path, stage_path, runtime_root, plan_root, _ = args
            runtime = json.loads(runtime_path.read_text())
            stage_evidence = json.loads(stage_path.read_text())
            base = runtime["unity"]["spinePlugin"]
            base["upstreamCommit"] = "commit"
            player_hashes = {name: base["fileChecks"][name]["expectedSha256"]
                             for name in ("spine-csharp.dll", "spine-unity.dll")}
            editor_refs = {
                "spine-csharp.dll": [{"name": "netstandard", "version": "2.1.0.0"}],
                "spine-unity.dll": [{"name": "spine-csharp", "version": "0.0.0.0"},
                                    {"name": "UnityEditor.CoreModule", "version": "0.0.0.0"}],
            }
            editor_rows = {}
            copied_rows = {}
            for name in ("spine-csharp.dll", "spine-unity.dll"):
                payload = ("editor core" if name == "spine-csharp.dll" else "editor unity").encode()
                source = runtime_root / "EditorRuntime" / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(payload)
                digest_value = digest(payload)
                editor_rows[name] = {"path": str(source), "sha256": digest_value, "bytes": len(payload),
                    "assemblyName": name[:-4], "assemblyVersion": "0.0.0.0",
                    "playerReferenceIdentity": {"name": name[:-4], "version": "0.0.0.0"},
                    "references": editor_refs[name],
                    "runtimeImportPath": "Assets/Plugins/Spine38/EditorRuntime/" + name}
                copied_rows[name] = {"sha256": digest_value, "bytes": len(payload), "verified": True,
                    "target": "Assets/Plugins/Spine38/EditorRuntime/" + name}
            source_manifest_sha = "a" * 64
            evidence_doc = {"status": "verified_editor_source_build", "sourceManifestSha256": source_manifest_sha,
                "upstreamCommit": "commit", "cocosCompatibilityFallbacksIncluded": False}
            evidence_path = Path(temp) / "editor-evidence.json"
            write_json(evidence_path, evidence_doc)
            evidence_sha = digest(evidence_path.read_bytes())
            base["editorVariant"] = {"status": "verified_editor_source_build", "upstreamCommit": "commit",
                "compiledAgainst": "Unity6000.6.2f1", "compileDefines": ["UNITY_EDITOR"],
                "sourceManifestSha256": source_manifest_sha, "importPolicy": "paired_editor_only_assemblies_player_pair_excludes_editor",
                "cocosCompatibilityFallbacksIncluded": False, "evidencePath": str(evidence_path),
                "evidenceSha256": evidence_sha, "playerAssemblyHashes": player_hashes, "assemblies": editor_rows}
            stage_evidence["editorVariant"] = {"status": "verified_editor_source_build",
                "sourceManifestSha256": source_manifest_sha, "copiedFiles": copied_rows}
            write_json(runtime_path, runtime)
            write_json(stage_path, stage_evidence)
            stage = prepare_unity_stage(target, native, emission, source_ir, closure, closure_freeze,
                                        runtime_path, stage_path, runtime_root, plan_root)
            player_meta = next(row for row in stage["copies"] if row["target"] == "Assets/Plugins/Spine38/spine-unity.dll.meta")
            editor_meta = next(row for row in stage["copies"] if row["target"] == "Assets/Plugins/Spine38/EditorRuntime/spine-unity.dll.meta")
            self.assertEqual(stage["editorRuntimeVariant"]["status"], "verified_editor_source_build")
            self.assertEqual(sum(row["role"] == "verified-editor-only-spine-runtime" for row in stage["copies"]), 2)
            self.assertIn("Exclude Editor: 1", (plan_root / player_meta["source"]).read_text())
            self.assertIn("Editor: Editor\n    second:\n      enabled: 1", (plan_root / editor_meta["source"]).read_text())
            emitted = emit_unity_stage(stage, plan_root, Path(temp) / "unity-editor-pair")
            self.assertTrue((Path(temp) / "unity-editor-pair/Assets/Plugins/Spine38/EditorRuntime/spine-csharp.dll").is_file())
            self.assertEqual(emitted["nativeImport"], "not_run")
            self.assertEqual(stage["editorRuntimeVariant"]["assemblyLoadVerification"]["status"], "not_run")

    def make_fixture(self, root):
        source_manifest = root / "frozen" / "source-manifest.json"
        manifest_bytes = b'{"assets":[]}\n'
        source_manifest.parent.mkdir(parents=True)
        source_manifest.write_bytes(manifest_bytes)
        manifest_sha = digest(manifest_bytes)
        source_ir = root / "frozen" / "ir.json"
        source_ir.write_bytes(b'{"components":[]}\n')
        ir_sha = digest(source_ir.read_bytes())

        closure = root / "closure"
        closure_file = closure / "Assets/Game/Content/Spine/Test/test.skel.bytes"
        closure_file.parent.mkdir(parents=True)
        closure_file.write_bytes(b"spine skeleton bytes")
        closure_meta = Path(str(closure_file) + ".meta")
        closure_meta.write_text("fileFormatVersion: 2\nguid: 12345678901234567890123456789012\n")
        page_texture = closure / "Assets/Game/Content/Spine/Test/test.png"
        page_texture.parent.mkdir(parents=True, exist_ok=True)
        page_texture.write_bytes(b"exact spine page texture")
        page_texture_meta = Path(str(page_texture) + ".meta")
        page_texture_meta.write_text("fileFormatVersion: 2\nguid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
        page_atlas = closure / "Assets/Game/Content/Spine/Test/test.atlas.txt"
        page_atlas.write_text("test.png\nsize: 16,16\nformat: RGBA8888\nfilter: Linear,Linear\nrepeat: none\n")

        closure_report = write_json(closure / "Analysis/Evidence/spine-closures.json", {"skeletons": []})
        closure_freeze = {
            "schemaVersion": 1, "sourceManifestSha256": manifest_sha,
            "candidatePath": str(closure.resolve()), "closureReportSha256": digest(closure_report.read_bytes()),
            "files": [
                {"path": "Analysis/Evidence/spine-closures.json", "sha256": digest(closure_report.read_bytes()),
                 "bytes": closure_report.stat().st_size},
                {"path": "Assets/Game/Content/Spine/Test/test.skel.bytes", "sha256": digest(closure_file.read_bytes()),
                 "bytes": closure_file.stat().st_size},
                {"path": "Assets/Game/Content/Spine/Test/test.png", "sha256": digest(page_texture.read_bytes()),
                 "bytes": page_texture.stat().st_size},
                {"path": "Assets/Game/Content/Spine/Test/test.png.meta", "sha256": digest(page_texture_meta.read_bytes()),
                 "bytes": page_texture_meta.stat().st_size},
                {"path": "Assets/Game/Content/Spine/Test/test.atlas.txt", "sha256": digest(page_atlas.read_bytes()),
                 "bytes": page_atlas.stat().st_size},
                {"path": "Assets/Game/Content/Spine/Test/test.skel.bytes.meta", "sha256": digest(closure_meta.read_bytes()),
                 "bytes": closure_meta.stat().st_size},
            ],
        }
        closure_freeze_path = write_json(root / "closure-freeze.json", closure_freeze)

        emission = {
            "schemaVersion": 1, "contract": "monkey-spine-emission/1",
            "pins": {"sourceManifestSha256": manifest_sha, "normalizedIrSha256": ir_sha,
                     "unityClosureReceiptSha256": digest(closure_freeze_path.read_bytes())},
            "copies": [
                {"target": "unity", "path": "Assets/Game/Content/Spine/Test/test.skel.bytes",
                 "sha256": digest(closure_file.read_bytes()), "bytes": closure_file.stat().st_size,
                 "sourceId": "asset:test"},
                {"target": "unity", "path": "Assets/Game/Content/Spine/Test/test.skel.bytes.meta",
                 "sha256": digest(closure_meta.read_bytes()), "bytes": closure_meta.stat().st_size,
                 "sourceId": "asset:test"},
                {"target": "unity", "path": "Assets/Game/Content/Spine/Test/test.png",
                 "sha256": digest(page_texture.read_bytes()), "bytes": page_texture.stat().st_size,
                 "sourceId": "texture:test"},
                {"target": "unity", "path": "Assets/Game/Content/Spine/Test/test.png.meta",
                 "sha256": digest(page_texture_meta.read_bytes()), "bytes": page_texture_meta.stat().st_size,
                 "sourceId": "texture:test"},
                {"target": "unity", "path": "Assets/Game/Content/Spine/Test/test.atlas.txt",
                 "sha256": digest(page_atlas.read_bytes()), "bytes": page_atlas.stat().st_size,
                 "sourceId": "atlas:test"},
            ],
        }
        emission_path = write_json(root / "emission.json", emission)

        runtime_root = root / "runtime-stage"
        runtime_root.mkdir()
        runtime_manifest = b'{"version":"3.8.99"}\n'
        (runtime_root / "manifest.json").write_bytes(runtime_manifest)
        files = {
            "spine-csharp.dll": b"csharp-runtime",
            "spine-unity.dll": b"unity-runtime",
            "Shaders/Spine-SkeletonGraphic.shader": b"graphic-shader",
            "LICENSE": b"license text",
        }
        checks = {}
        for relative, data in files.items():
            path = runtime_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            value = digest(data)
            checks[relative] = {"expectedSha256": value, "observedSha256": value, "verified": True}
        runtime_evidence = {
            "unity": {"spinePlugin": {"manifestSha256": digest(runtime_manifest), "path": str(root / "runtime-source" / "manifest.json"),
                                       "compiledAgainst": "Unity6000.6.2f1",
                                       "fileChecks": checks}},
        }
        runtime_source_manifest = Path(runtime_evidence["unity"]["spinePlugin"]["path"])
        runtime_source_manifest.parent.mkdir(parents=True)
        runtime_source_manifest.write_bytes(runtime_manifest)
        runtime_evidence_path = write_json(root / "runtime-evidence.json", runtime_evidence)
        stage_evidence = {
            "verified": True, "sourceManifestSha256": digest(runtime_manifest),
            "copiedFiles": {name: {"sha256": checks[name]["expectedSha256"], "verified": True} for name in checks},
        }
        stage_evidence_path = write_json(root / "runtime-stage-evidence.json", stage_evidence)

        repo_root = Path(__file__).resolve().parents[2]
        shader_path = repo_root / "src/grea/recovery/targets/materials/spine/UnitySpineSourceProfile.shader"
        graphic_shader_path = repo_root / "src/grea/recovery/targets/materials/spine/UnitySpineGraphicProfile.shader"
        native_plan = {
            "schemaVersion": 1, "contract": "monkey-spine-native-binding/1",
            "sourceManifestSha256": manifest_sha, "normalizedIrSha256": ir_sha,
            "sourceMaterialProfile": {
                "creatorMappingStatus": "exact_source_builtin_profile_mapping",
                "sourceReferenceSourceId": "bundle:source-material-ref",
                "resolvedSourceMaterialId": "bundle:source-material",
                "creatorTargetMaterialUuid": "default-spine-material",
            },
            "scaleEvidence": {"status": "verified_source_renderer_unit_mapping",
                              "source": dict(SOURCE_SCALE_EVIDENCE),
                              "target": {"status": "verified_unit_mapping", "targetUnitsPerSourcePixel": 1.0,
                                         "worldSpaceCanvasScale": 1.0, "pixelsPerUnitConversion": None},
                              "resolvedSkeletonDataAssetScales": {"spine-data:test": 0.01}},
            "persistentVisiblePose": True,
            "visualPolicy": "native_renderer_enabled_timeScale_zero_source_timeScale_retained",
            "persistentVisiblePoseEvidence": {"status": "verified_pinned_spine_unity_3_8_runtime_source",
                "upstreamCommit": "8b4844bd4b193ba9e54487ed397a777993cbad56",
                "runtimeVersion": "3.8.99",
                "targetPolicy": "keep_native_renderer_enabled_and_set_timeScale_zero; preserve verified sourceTimeScale in identity/readback; no recovered game behavior"},
            "componentCount": 1, "sourceStaticDataBoundCount": 1, "sourceStaticDataUnboundCount": 0,
            "components": [{"sourceComponentId": "asset:test#0/components/0", "sourcePrefabId": "asset:test", "sourceNodeId": "0",
                            "sourceDataAssetId": "spine-data:test", "sourceHasStaticDataReference": True,
                            "rendererSelection": {"status": "declared_not_native_readback",
                                "sourceComponentId": "asset:test#0/components/0", "rendererKind": "SkeletonGraphic",
                                "targetNodeTransform": "RectTransform", "canvasIdentity": "canvas:test",
                                "canvasReferencePixelsPerUnit": 100.0, "nativeRendererReadback": "pending"},
                            "behavior": "disabled", "sourceCallbacksExecuted": False,
                            "persistentVisiblePose": True, "sourceTimeScale": 1.0, "sourceTimeScaleVerified": True}],
            "dataAssetCount": 1,
            "dataAssets": [{"sourceAssetId": "spine-data:test", "atlasTextAssetPath": "Assets/Game/Content/Spine/Test/test.atlas.txt",
                             "premultipliedAlpha": False, "scale": 0.01,
                             "factoryInput": {"scale": 0.01},
                             "scaleEvidence": {"status": "verified_source_renderer_unit_mapping",
                                "source": dict(SOURCE_SCALE_EVIDENCE),
                                "resolvedSkeletonDataAssetScale": 0.01,
                                "rendererContexts": [{"sourceComponentId": "asset:test#0/components/0",
                                    "rendererKind": "SkeletonGraphic", "targetNodeTransform": "RectTransform",
                                    "canvasIdentity": "canvas:test", "canvasReferencePixelsPerUnit": 100.0}]},
                             "pages": [{"sourceAtlasPage": "test.png", "sourceTextureSourceId": "texture:test",
                                        "textureAssetPath": "Assets/Game/Content/Spine/Test/test.png",
                                        "textureSha256": digest(page_texture.read_bytes())}]}],
            "unityShader": {"sourcePath": str(shader_path),
                            "targetPath": "Assets/Game/Content/Shaders/UnitySpineSourceProfile.shader",
                            "sha256": digest(shader_path.read_bytes())},
            "unityGraphicShader": {"sourcePath": str(graphic_shader_path),
                                   "targetPath": "Assets/Game/Content/Shaders/UnitySpineGraphicProfile.shader",
                                   "shaderName": "Monkey/SpineSourceGraphicProfile/Colored",
                                   "sha256": digest(graphic_shader_path.read_bytes())},
        }
        native_path = write_json(root / "native-plan.json", native_plan)
        target_plan = {
            "schemaVersion": 1, "targetProfile": "unity-6000.6.2f1-ugui", "namespace": "Recovered.Tests",
            "sourceManifestSha256": manifest_sha, "sourceManifestPath": str(source_manifest),
            "sourceIrSha256": ir_sha,
            "sourcePrefabs": [{"sourceId": "asset:test", "nodes": ["asset:test#0"]}],
            "nodes": [{"sourceId": "asset:test#0"}],
            "components": [{"sourceId": "asset:test#0/components/0", "type": "sp.Skeleton", "node": "asset:test#0"}],
            "syncPrefabBindings": [],
        }
        output = root / "target-plan"
        output.mkdir()
        return (target_plan, native_path, emission_path, source_ir, closure, closure_freeze_path, runtime_evidence_path,
                stage_evidence_path, runtime_root, output, native_plan)

    def test_attach_emit_includes_real_closure_runtime_helpers_and_plan(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            args = self.make_fixture(Path(temp))
            target, native, emission, source_ir, closure, closure_freeze, runtime, stage_evidence, runtime_root, plan_root, native_doc = args
            stage = prepare_unity_stage(target, native, emission, source_ir, closure, closure_freeze, runtime, stage_evidence, runtime_root, plan_root)
            attached = attach_unity_stage(target, stage)
            self.assertIs(attached["spineNativeStage"], stage)
            self.assertEqual(stage["componentCount"], 1)
            self.assertEqual(stage["sourceTemplateComponentCount"], 1)
            self.assertEqual(stage["expandedInstanceComponentCount"], 1)
            self.assertEqual(stage["dataAssetCount"], 1)
            self.assertEqual(stage["resolvedSkeletonDataScale"], 0.01)
            self.assertEqual(stage["resolvedSkeletonDataScales"], {"spine-data:test": 0.01})
            self.assertTrue(stage["runtimeLicenseIncluded"])
            self.assertTrue(any(row["target"].endswith("spine-native-binding-plan.json") for row in stage["copies"]))
            self.assertTrue(any(row["target"].endswith("spine-native-source-binding-plan.json") for row in stage["copies"]))
            self.assertTrue(any(row["target"].endswith("UnitySpineNativeStage.cs") for row in stage["copies"]))
            self.assertTrue(any(row["target"].endswith("UnitySpineGraphicMaterialPresentation.cs") for row in stage["copies"]))
            self.assertTrue(any(row["target"].endswith("UnitySpineGraphicProfile.shader") for row in stage["copies"]))
            self.assertTrue(any(row["target"].endswith("UnitySpineImporterIntegration.cs") for row in stage["copies"]))
            self.assertTrue(any(row["target"].endswith("UnitySpineSourceIdentity.cs") for row in stage["copies"]))
            plugin_meta = next(row for row in stage["copies"] if row["target"].endswith("spine-unity.dll.meta"))
            self.assertNotIn(b"platformData: []", (plan_root / plugin_meta["source"]).read_bytes())
            unity = Path(temp) / "unity-candidate"
            report = emit_unity_stage(stage, plan_root, unity)
            self.assertEqual(report["componentCount"], 1)
            self.assertEqual(report["dataAssetCount"], 1)
            self.assertEqual((unity / "Assets/Plugins/Spine38/LICENSE").read_bytes(), b"license text")
            self.assertTrue((unity / "Assets/Game/Content/Spine/Test/test.skel.bytes").is_file())
            page_meta = unity / "Assets/Game/Content/Spine/Test/test.png.meta"
            self.assertTrue(page_meta.is_file())
            metadata = page_meta.read_text()
            self.assertNotIn("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", metadata)
            self.assertIn("serializedVersion: 13", metadata)
            self.assertIn("textureType: 0", metadata)
            self.assertIn("textureShape: 1", metadata)
            self.assertIn("alphaUsage: 1", metadata)
            self.assertIn("alphaIsTransparency: 0", metadata)
            self.assertIn("enableMipMap: 0", metadata)
            self.assertIn("filterMode: 1", metadata)
            self.assertIn("wrapU: 1", metadata)
            self.assertIn("wrapV: 1", metadata)
            self.assertIn("nPOTScale: 0", metadata)
            self.assertIn("maxTextureSize: 16384", metadata)
            self.assertIn("textureCompression: 0", metadata)
            self.assertEqual(stage["pageTextureCount"], 1)
            self.assertEqual(stage["pageTextureSourceMetasIgnored"], ["Assets/Game/Content/Spine/Test/test.png.meta"])
            self.assertEqual(stage["pageTextureProfiles"][0]["sourcePremultipliedAlphaProfiles"], [False])
            self.assertEqual(stage["pageTextureProfiles"][0]["sampling"]["atlasFilter"], "Linear,Linear")
            self.assertEqual(stage["pageTextureProfiles"][0]["sampling"]["atlasRepeat"], "none")
            self.assertEqual(stage["pageTextureProfiles"][0]["sampling"]["alphaSourceEnum"], 1)
            self.assertTrue((unity / "Assets/Game/Editor/Conversion/spine-native-binding-plan.json").is_file())
            stage_plan = json.loads((unity / "Assets/Game/Editor/Conversion/spine-native-binding-plan.json").read_text())
            self.assertEqual(stage_plan["components"][0]["templateOrigin"]["sourceComponentId"], "asset:test#0/components/0")

    def test_stage_rejects_scale_that_differs_from_frozen_context_formula(self):
        for invalid_scale in (1.0, 0.0, -0.01, float('inf')):
            with self.subTest(scale=invalid_scale), tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
                args = self.make_fixture(Path(temp))
                target, native_path, emission, source_ir, closure, closure_freeze, runtime, stage_evidence, runtime_root, plan_root, native_doc = args
                native_doc["dataAssets"][0]["scale"] = invalid_scale
                native_doc["dataAssets"][0]["factoryInput"] = {"scale": invalid_scale}
                write_json(native_path, native_doc)
                with self.assertRaises(SpineNativeStageError):
                    prepare_unity_stage(target, native_path, emission, source_ir, closure, closure_freeze,
                                        runtime, stage_evidence, runtime_root, plan_root)

    def test_stage_rejects_synchronized_source_scale_tampering_and_boolean_unit_values(self):
        for mutation in ("synchronized_source_scale", "boolean_target_units", "boolean_world_scale",
                         "boolean_pixels_conversion"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
                args = self.make_fixture(Path(temp))
                target, native_path, emission, source_ir, closure, closure_freeze, runtime, stage_evidence, runtime_root, plan_root, native_doc = args
                if mutation == "synchronized_source_scale":
                    native_doc["scaleEvidence"]["source"]["sourceDefaultScale"] = 2.0
                    native_doc["scaleEvidence"]["resolvedSkeletonDataAssetScales"]["spine-data:test"] = 0.02
                    asset_row = native_doc["dataAssets"][0]
                    asset_row["scale"] = 0.02
                    asset_row["factoryInput"]["scale"] = 0.02
                    asset_row["scaleEvidence"]["source"]["sourceDefaultScale"] = 2.0
                    asset_row["scaleEvidence"]["resolvedSkeletonDataAssetScale"] = 0.02
                elif mutation == "boolean_target_units":
                    native_doc["scaleEvidence"]["target"]["targetUnitsPerSourcePixel"] = True
                elif mutation == "boolean_world_scale":
                    native_doc["scaleEvidence"]["target"]["worldSpaceCanvasScale"] = True
                else:
                    native_doc["scaleEvidence"]["target"]["pixelsPerUnitConversion"] = True
                write_json(native_path, native_doc)
                with self.assertRaises(SpineNativeStageError):
                    prepare_unity_stage(target, native_path, emission, source_ir, closure, closure_freeze,
                                        runtime, stage_evidence, runtime_root, plan_root)

    def test_stage_expands_sync_instance_using_exact_component_and_node_origins(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            args = self.make_fixture(Path(temp))
            target, native, emission, source_ir, closure, closure_freeze, runtime, stage_evidence, runtime_root, plan_root, _ = args
            target["sourcePrefabs"].append({"sourceId": "asset:owner", "nodes": ["asset:owner#8", "asset:owner#8::sync-node-x"]})
            target["nodes"].append({"sourceId": "asset:owner#8::sync-node-x"})
            instance_component = "asset:owner#8::sync-component-x"
            target["components"].append({"sourceId": instance_component, "type": "sp.Skeleton",
                                          "node": "asset:owner#8::sync-node-x"})
            target["syncPrefabBindings"] = [{
                "owner": "asset:owner", "root": "asset:owner#8", "template": "asset:test",
                "componentOrigins": [{"instanceSourceId": instance_component,
                                      "templateSourceId": "asset:test#0/components/0"}],
                "origins": [{"instanceSourceId": "asset:owner#8::sync-node-x",
                             "templateSourceId": "asset:test#0"}],
            }]
            stage = prepare_unity_stage(target, native, emission, source_ir, closure, closure_freeze,
                                        runtime, stage_evidence, runtime_root, plan_root)
            expanded = next(row for row in stage["copies"] if row["role"] == "expanded-stage-native-binding-plan")
            plan = json.loads((plan_root / expanded["source"]).read_text())
            clone = next(row for row in plan["components"] if row["sourceComponentId"] == instance_component)
            self.assertEqual(stage["componentCount"], 2)
            self.assertEqual(stage["instanceExpansion"]["mappedInstanceCount"], 2)
            self.assertEqual(clone["sourcePrefabId"], "asset:owner")
            self.assertEqual(clone["sourceNodeId"], "asset:owner#8::sync-node-x")
            self.assertEqual(clone["templateOrigin"]["sourceComponentId"], "asset:test#0/components/0")
            self.assertEqual(clone["templateOrigin"]["sourcePrefabId"], "asset:test")
            self.assertEqual(clone["templateOrigin"]["sourceNodeId"], "asset:test#0")

    def test_emit_rejects_changed_payload_and_conflicting_target(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            args = self.make_fixture(Path(temp))
            target, native, emission, source_ir, closure, closure_freeze, runtime, stage_evidence, runtime_root, plan_root, _ = args
            stage = prepare_unity_stage(target, native, emission, source_ir, closure, closure_freeze, runtime, stage_evidence, runtime_root, plan_root)
            first = stage["copies"][0]
            (plan_root / first["source"]).write_bytes(b"changed")
            with self.assertRaises(SpineNativeStageError):
                emit_unity_stage(stage, plan_root, Path(temp) / "unity")

    def test_creator_handoff_requires_exact_source_material_identity(self):
        profile = {"creatorMappingStatus": "exact_source_builtin_profile_mapping",
                   "sourceReferenceSourceId": "bundle:ref", "resolvedSourceMaterialId": "bundle:material",
                   "creatorTargetMaterialUuid": "default-spine-material"}
        contract = creator_profile_handoff({"sourceMaterialProfile": profile})
        self.assertEqual(contract["profile"], "cocos24-builtin-spine-material-v1")
        self.assertEqual(contract["targetMaterialUuid"], "default-spine-material")
        profile["creatorMappingStatus"] = "unresolved"
        with self.assertRaises(SpineNativeStageError):
            creator_profile_handoff({"sourceMaterialProfile": profile})

    def test_unity_domain_reload_read_paths_reload_frozen_plan_without_creating_native_objects(self):
        integration = (Path(__file__).resolve().parents[2] /
                       "src/grea/recovery/targets/spine/UnitySpineImporterIntegration.cs").read_text()
        self.assertIn("static UnitySpineNativeStage.Plan LoadFrozenStaticSpinePlan()", integration)
        self.assertIn("UnitySpineNativeStage.Parse(File.ReadAllText(StaticSpinePlanPath))", integration)
        resolver = integration.split("static partial void ResolveStaticSpineReference", 1)[1].split("static partial void ReadSavedStaticSpine", 1)[0]
        readback = integration.split("static partial void ReadSavedStaticSpine", 1)[1].split("static string ResolveSpineNodeId", 1)[0]
        self.assertIn("LoadFrozenStaticSpinePlan()", resolver)
        self.assertIn("LoadFrozenStaticSpinePlan()", readback)
        self.assertNotIn("CreateDataAssets", resolver + readback)
        self.assertNotIn("CreateComponents", resolver + readback)
        self.assertIn("AssetDatabase.LoadAssetAtPath<SkeletonDataAsset>", resolver)
        self.assertIn("marker.sourceComponentId == componentRow.templateOrigin.sourceComponentId", resolver)
        self.assertIn("componentRow.templateOrigin.sourcePrefabId", resolver)
        self.assertNotIn("GetComponentInChildren", resolver)

    def test_unity_data_asset_create_failure_persists_serializable_diagnostic_wrapper(self):
        integration = (Path(__file__).resolve().parents[2] /
                       "src/grea/recovery/targets/spine/UnitySpineImporterIntegration.cs").read_text()
        stage = (Path(__file__).resolve().parents[2] /
                 "src/grea/recovery/targets/spine/UnitySpineNativeStage.cs").read_text()
        factory = (Path(__file__).resolve().parents[2] /
                   "src/grea/recovery/targets/spine/UnitySpineNativeFactory.cs").read_text()
        self.assertIn("sealed class StaticSpineCreateAttempt", integration)
        self.assertIn('evidenceClass = "native_create_attempt_diagnostic_only"', integration)
        self.assertIn('acceptanceStatus = "not_claimed"', integration)
        for field in ("sourceManifestSha256", "normalizedIrSha256", "DataAssetRow[] data",
                      "DataAssetReadback[] readback", "StageGap[] gaps"):
            self.assertIn(field, integration)
        self.assertIn('const string StaticSpineReadbackRoot = "Analysis/Readback/Spine"', integration)
        self.assertIn('"create-attempt.json"', integration)
        self.assertIn("JsonUtility.ToJson(attempt, true)", integration)
        self.assertIn('gap.sourceId + ":" + gap.code + ":" + gap.message', integration)
        self.assertNotIn("JsonUtility.ToJson(staticSpineAssets.gaps.ToArray())", integration)
        for field in ("string phase;", "string exceptionType;", "string stackTrace;"):
            self.assertIn(field, stage)
        self.assertIn("BoundDiagnosticText(originalStack)", stage)
        self.assertIn("originalStackTrace = full.Length <= DiagnosticStackMaxChars", factory)
        self.assertIn("DataAssetCreateException(spec.sourceAssetId, phase, error)", factory)
        for phase in ("create_atlas_asset_instance", "parse_saved_atlas",
                      "create_skeleton_data_asset_instance", "save_skeleton_data_asset",
                      "read_saved_skeleton_data_asset"):
            self.assertIn('phase = "' + phase + '"', factory)
        self.assertIn("SPINE_ATLAS_ASSET_INSTANCE_CREATE_FAILED", factory)
        self.assertIn("SPINE_SKELETON_DATA_ASSET_INSTANCE_CREATE_FAILED", factory)
        self.assertNotIn("parsed.Skins.Items.Select", factory)
        self.assertNotIn("parsed.Animations.Items.Select", factory)
        self.assertIn("ReadCatalogNames(parsed.Animations", factory)
        self.assertIn("ReadCatalogNames(parsed.Skins", factory)
        self.assertIn("ValidateCatalogStructure(parsed.Bones", factory)
        self.assertIn("ValidateCatalogStructure(parsed.Slots", factory)
        self.assertIn("for (int index = 0; index < catalog.Count; index++)", factory)
        self.assertIn('"native_" + kind + "_catalog_null_item:" + index', factory)
        self.assertIn("global::Spine.ExposedList<T>", factory)
        self.assertIn("global::Spine.Animation animation", factory)
        self.assertIn("global::Spine.Skin skin", factory)

    def test_spine_page_texture_resolution_is_exact_and_diagnostic_without_importer_mutation(self):
        factory = (Path(__file__).resolve().parents[2] /
                   "src/grea/recovery/targets/spine/UnitySpineNativeFactory.cs").read_text()
        resolver = factory.split("static Texture2D LoadSpinePageTexture", 1)[1].split("static bool VerifyFields", 1)[0]
        self.assertIn("AssetDatabase.GetMainAssetTypeAtPath(path)", resolver)
        self.assertIn("AssetDatabase.LoadAllAssetsAtPath(path)", resolver)
        self.assertIn("AssetDatabase.GetAssetPath(value)", resolver)
        self.assertIn("SPINE_PAGE_TEXTURE_MISSING", resolver)
        self.assertNotIn("AssetDatabase.ImportAsset", resolver)
        self.assertNotIn("AssetDatabase.LoadAssetAtPath<Sprite>", resolver)
        self.assertNotIn("textureType =", resolver)

    def test_unity_spine_assets_use_registered_assetdatabase_folders_and_clean_owned_empty_folders(self):
        factory = (Path(__file__).resolve().parents[2] /
                   "src/grea/recovery/targets/spine/UnitySpineNativeFactory.cs").read_text()
        create_data = factory.split("public static DataAssetReadback CreateDataAsset", 1)[1].split(
            "public static DataAssetReadback ReadDataAssetAsset", 1)[0]
        ensure = factory.split("static List<string> EnsureAssetDirectoriesForPaths", 1)[1].split(
            "static void EnsureRegisteredAssetParent", 1)[0]
        cleanup = factory.split("static void DeleteCreatedEmptyFolders", 1)[1].split(
            "static Texture2D LoadSpinePageTexture", 1)[0]
        self.assertIn("EnsureAssetDirectoriesForPaths(", create_data)
        self.assertIn("page.normalMaterialAssetPath", create_data)
        self.assertIn("variant.materialAssetPath", create_data)
        self.assertIn("spec.atlasAssetPath", create_data)
        self.assertIn("spec.skeletonDataAssetPath", create_data)
        self.assertLess(create_data.index("EnsureAssetDirectoriesForPaths("), create_data.index("CreateProfileMaterial("))
        self.assertIn("AssetDatabase.CreateFolder(parent, segments[index])", ensure)
        self.assertIn("AssetDatabase.IsValidFolder(child)", ensure)
        self.assertIn("SPINE_ASSET_DIRECTORY_UNREGISTERED", ensure)
        self.assertIn("Directory.Exists(absolute)", ensure)
        self.assertNotIn("Directory.CreateDirectory", factory)
        self.assertIn("EnsureRegisteredAssetParent(path)", factory)
        self.assertIn("DeleteCreatedEmptyFolders(createdFolders)", create_data)
        self.assertIn("!Directory.EnumerateFileSystemEntries(absolute).Any()", cleanup)

    def test_spine_graphic_pma_is_mapped_to_mesh_generator_and_dynamic_only_gaps_do_not_gate_static_bind(self):
        root = Path(__file__).resolve().parents[2]
        factory = (root / "src/grea/recovery/targets/spine/UnitySpineNativeFactory.cs").read_text()
        stage = (root / "src/grea/recovery/targets/spine/UnitySpineNativeStage.cs").read_text()
        integration = (root / "src/grea/recovery/targets/spine/UnitySpineImporterIntegration.cs").read_text()
        self.assertIn("graphic.MeshGenerator", factory)
        self.assertIn("settings.pmaVertexColors = value", factory)
        self.assertIn("generator.settings.pmaVertexColors != value", factory)
        self.assertIn("VerifySkeletonGraphicPmaVertexColors", factory)
        self.assertIn("mappedStaticFieldsVerified = fieldsVerified && pmaMaterialEvidenceSatisfied", factory)
        self.assertNotIn("pma_vertex_color_member_not_applicable_on_skeleton_graphic", factory)
        self.assertIn("public bool mappedStaticFieldsVerified", factory)
        self.assertIn("readback.fieldsVerified = false", stage)
        self.assertIn("readback.nativeComplete = false", stage)
        self.assertIn("readback.sourceOnlyFieldGaps = sourceOnly.ToArray()", stage)
        self.assertIn('row.sourceProperty == "playTimes" && row.status == "source_only_no_same_component_field"', stage)
        self.assertIn('row.sourceProperty == "caching" && row.status == "source_only_runtime_cache_mapping_unresolved"', stage)
        self.assertIn("readback.mappedStaticFieldsVerified &= everyGapExplicitlyAllowlisted", stage)
        self.assertEqual(integration.count("!readback.mappedStaticFieldsVerified"), 2)
        self.assertNotIn("!readback.fieldsVerified", integration)
        self.assertIn("staticNativeVerified = failures.Count == 0", integration)
        self.assertIn("dynamicBehaviorComplete = false", integration)
        self.assertIn('gap.code.Contains("READBACK_FAILED") || gap.code.Contains("IDENTITY_MISMATCH")', integration)

    def test_unbound_spine_graphic_marks_material_profile_not_applicable_without_claiming_verified(self):
        root = Path(__file__).resolve().parents[2]
        factory = (root / "src/grea/recovery/targets/spine/UnitySpineNativeFactory.cs").read_text()
        integration = (root / "src/grea/recovery/targets/spine/UnitySpineImporterIntegration.cs").read_text()
        self.assertIn("public bool pmaMaterialProfileRequired", factory)
        self.assertIn("public bool pmaMaterialProfileVerified", factory)
        self.assertIn("public bool pmaMaterialProfileNotApplicable", factory)
        self.assertIn("bool pmaMaterialVerified = false", factory)
        self.assertIn("expectedFields.ContainsKey(\"pmaVertexColors\") && sourceHasStaticDataReference", factory)
        self.assertIn("!sourceHasStaticDataReference && sourceUnbound", factory)
        self.assertIn("if (pmaMaterialProfileRequired)", factory)
        self.assertIn("mappedStaticFieldsVerified = fieldsVerified && pmaMaterialEvidenceSatisfied", factory)
        self.assertIn("!row.sourceHasStaticDataReference && !readback.sourceDataUnbound", integration)
        self.assertIn("dynamicAssignmentUnverified = sourceUnbound", factory)
        self.assertNotIn("pmaMaterialProfileNotApplicable = !sourceHasStaticDataReference", factory)

    def test_spine_graphic_ui_material_path_is_read_and_unverified_renderer_blocks_static_gate(self):
        factory = (Path(__file__).resolve().parents[2] /
                   "src/grea/recovery/targets/spine/UnitySpineNativeFactory.cs").read_text()
        self.assertIn("public bool rendererMaterialRequired", factory)
        self.assertIn("public bool rendererMaterialVerified", factory)
        self.assertIn("rendererMaterialRequired = isGraphic && sourceHasStaticDataReference", factory)
        self.assertIn("rendererMaterialVerified = !rendererMaterialRequired", factory)
        self.assertIn("graphic.materialForRendering", factory)
        self.assertIn("graphic.canvasRenderer.GetMaterial()", factory)
        self.assertIn("rendererBaseMaterialShader =", factory)
        self.assertIn("rendererMainTextureAssetPath =", factory)
        self.assertIn("skeleton_graphic_renderer_material_profile_not_bound_or_readback_unverified", factory)
        self.assertIn("ConfigureGraphicMaterialPresentation", factory)
        self.assertIn("skeleton_graphic_multiple_canvas_renderers_disabled", factory)
        self.assertIn("(!rendererMaterialRequired || rendererMaterialVerified)", factory)

    def test_spine_graphic_material_adapter_is_material_identity_keyed_mask_aware_and_read_only_on_readback(self):
        root = Path(__file__).resolve().parents[2]
        helper = (root / "src/grea/recovery/targets/spine/UnitySpineGraphicMaterialPresentation.cs").read_text()
        shader = (root / "src/grea/recovery/targets/materials/spine/UnitySpineGraphicProfile.shader").read_text()
        integration = (root / "src/grea/recovery/targets/spine/UnitySpineImporterIntegration.cs").read_text()
        self.assertIn("binding.sourceMaterial == sourceMaterial", helper)
        self.assertIn("rawImage.materialForRendering", helper)
        self.assertIn("OnMeshAndMaterialsUpdated += OnMeshAndMaterialsUpdated", helper)
        self.assertIn("canvasRenderer.SetMaterial(modified, sourceMaterial.mainTexture)", helper)
        self.assertIn("ExpectedSdkInstructionsType", helper)
        self.assertIn("saved_raw_image_texture_reference_mismatch", helper)
        self.assertIn("_StencilComp", shader)
        self.assertIn("_StencilWriteMask", shader)
        self.assertIn("Stencil", shader)
        self.assertIn("UnityUI.cginc", shader)
        self.assertIn("UnityGet2DClipping", shader)
        self.assertIn("_PREMULTIPLIED_ALPHA", shader)
        self.assertIn("ConfigureGraphicProfileMaterial", (root / "src/grea/recovery/targets/spine/UnitySpineNativeFactory.cs").read_text())
        self.assertIn('material.SetInt("_StraightAlphaInput", 0)', (root / "src/grea/recovery/targets/spine/UnitySpineNativeFactory.cs").read_text())
        self.assertIn("IdentifyOptionalGeneratedSpineChild", integration)
        self.assertIn("row == renderer && row.gameObject == child.gameObject", integration)

    def test_spine_zero_submesh_is_verified_only_with_initialized_empty_pose_and_persisted_pairs(self):
        root = Path(__file__).resolve().parents[2]
        helper = (root / "src/grea/recovery/targets/spine/UnitySpineGraphicMaterialPresentation.cs").read_text()
        factory = (root / "src/grea/recovery/targets/spine/UnitySpineNativeFactory.cs").read_text()
        self.assertIn("skeleton_runtime_not_initialized", helper)
        self.assertIn("sourceDataIdentityVerified", helper)
        self.assertIn("activeDrawableAttachmentCount", helper)
        self.assertIn("expectedSkinKnown && expectedAnimationKnown", helper)
        self.assertIn("runtimeDefaultSkinName", helper)
        self.assertIn("defaultSkinRuntimeNull", helper)
        self.assertIn("defaultNullAlias=", helper)
        self.assertIn("allSlotsHaveNoDrawableAttachment", helper)
        self.assertIn("emptyRendererStateVerified", helper)
        self.assertIn("verified_empty_pose_with_persistent_material_pairs", helper)
        self.assertIn("VerifyPersistedPairsMatch(expectedPairBindings, bindings, gaps)", helper)
        self.assertIn("expectedPresentationBindings", factory)
        self.assertIn("presentationReadback.nativeMaterialVerified", factory)

    def test_spine_saved_initialization_rehydrates_only_sdk_derived_renderer_links(self):
        root = Path(__file__).resolve().parents[2]
        integration = (root / "src/grea/recovery/targets/spine/UnitySpineImporterIntegration.cs").read_text()
        helper = (root / "src/grea/recovery/targets/spine/UnitySpineGraphicMaterialPresentation.cs").read_text()
        self.assertIn("static partial void InitializeSavedStaticSpine(GameObject root)", integration)
        initialize = integration.split("static partial void InitializeSavedStaticSpine(GameObject root)", 1)[1].split(
            "static partial void SkipOptionalSpineDerivedProperty", 1)[0]
        self.assertIn("graphic.Initialize(true)", initialize)
        self.assertIn("graphic.Update(0f)", initialize)
        self.assertIn("graphic.UpdateMesh(keepRendererCount: false)", initialize)
        self.assertIn("graphic.TrimRenderers()", initialize)
        self.assertIn("helper.AttachForSavedInitialization()", initialize)
        self.assertNotIn("LoadFrozenStaticSpinePlan", initialize)
        self.assertNotIn("UnitySpineBinding.Apply", initialize)
        self.assertIn('propertyPath == "canvasRenderers"', integration)
        self.assertIn('propertyPath.StartsWith("canvasRenderers.", StringComparison.Ordinal)', integration)
        self.assertIn("HasBoundGraphicMaterial(rawImage.material)", integration)
        self.assertIn("RestoreSdkRendererLinksFromSavedChildren", helper)
        self.assertIn("SyncRawImagesWithCanvasRenderers", helper)
        self.assertIn("rawImages/currentInstructions/meshes are protected", integration)
        self.assertIn("or private and lack [SerializeField]", integration)
        self.assertIn("component.GetType() != typeof(SkeletonGraphic)", integration)

    def test_static_sort_finalizer_accepts_only_proven_zero_instruction_empty_pose(self):
        root = Path(__file__).resolve().parents[2]
        integration = (root / "src/grea/recovery/targets/spine/UnitySpineImporterIntegration.cs").read_text()
        finalize = integration.split("static void FinalizeSavedStaticSortSpineMeshes(Graphic[] sourceOwners)", 1)[1].split(
            "static bool IsSpineStaticSortGeneratedChild", 1)[0]
        self.assertIn("if (bindingReadback.instructionCount == 0)", finalize)
        self.assertIn('bindingReadback.nativeMaterialStatus == "verified_empty_pose_with_persistent_material_pairs"', finalize)
        for proof in ("pose.emptyPoseVerified", "pose.sourceDataIdentityVerified", "pose.sourceSkinVerified",
                      "pose.sourceAnimationVerified", "pose.allSlotsHaveNoDrawableAttachment",
                      "pose.emptyRendererStateVerified", "pose.activeDrawableAttachmentCount == 0",
                      "graphic.canvasRenderers.Count == 0", "rootMesh == null"):
            self.assertIn(proof, finalize)
        self.assertIn("SPINE_STATIC_SORT_FINALIZE_ZERO_RENDERER_POSE_NOT_PROVEN_EMPTY", finalize)
        self.assertIn("SPINE_STATIC_SORT_FINALIZE_RENDERER_LIST_EMPTY_WITH_DRAW_INSTRUCTIONS", finalize)

    def test_saved_prefab_instance_markers_are_verified_only_through_exact_template_origin(self):
        integration = (Path(__file__).resolve().parents[2] /
                       "src/grea/recovery/targets/spine/UnitySpineImporterIntegration.cs").read_text()
        readback = integration.split("static partial void ReadSavedStaticSpine", 1)[1].split("static string ResolveSpineNodeId", 1)[0]
        self.assertIn("row.templateOrigin.sourceComponentId", readback)
        self.assertIn("row.templateOrigin.sourcePrefabId", readback)
        self.assertIn("ResolveSpineNodeId(sourcePrefab, row.sourceNodeId)", readback)
        self.assertNotIn("marker.sourceComponentId == row.sourceComponentId", readback)

    def test_unity_spine_graphic_color_uses_source_node_rgba_and_readback_does_not_repair(self):
        integration = (Path(__file__).resolve().parents[2] /
                       "src/grea/recovery/targets/spine/UnitySpineImporterIntegration.cs").read_text()
        prepare = integration.split("static partial void PrepareStaticSpine", 1)[1].split("LoadFrozenStaticSpinePlan()", 1)[0]
        readback = integration.split("static partial void ReadSavedStaticSpine", 1)[1].split("static string ResolveSpineNodeId", 1)[0]
        self.assertIn("SourceSpineNodeColor(sourceNode, row.sourceComponentId)", prepare)
        self.assertIn("graphic.color = expectedColor", prepare)
        self.assertIn("channels[0] / 255f", integration)
        self.assertIn("channels[3] / 255f", integration)
        self.assertIn("CanvasGroup", integration)
        self.assertIn("saved_spine_graphic_color_mismatch", readback)
        self.assertIn("SpineGraphicColorMatches(graphic, sourceNodeSpec", readback)
        self.assertNotIn("graphic.color =", readback)


if __name__ == "__main__":
    unittest.main()
