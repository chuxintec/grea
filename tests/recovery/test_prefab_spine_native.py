import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from grea.recovery.prefab_spine_native import SpineNativePlanError, build_unity_native_binding_plan


_RENDERER_EVIDENCE_TMP = tempfile.TemporaryDirectory(dir="/private/tmp")
_RENDERER_EVIDENCE_ROOT = Path(_RENDERER_EVIDENCE_TMP.name)


def _default_context_rows(ids, ppu=100.0):
    return [
        {"sourceComponentId": ids[0], "sourceNodeId": "1",
         "rendererKind": "SkeletonGraphic", "targetNodeTransform": "RectTransform",
         "canvasIdentity": "Canvas/main", "canvasReferencePixelsPerUnit": ppu},
        {"sourceComponentId": ids[1], "sourceNodeId": "2",
         "rendererKind": "SkeletonAnimation", "targetNodeTransform": "Transform"},
    ]


def _write_renderer_contexts(source_sha, ir_sha, component_contexts):
    contexts = []
    for context in component_contexts:
        row = copy.deepcopy(context)
        transform_raw = json.dumps({"component": row["sourceComponentId"],
                                    "node": row["sourceNodeId"],
                                    "transform": row["targetNodeTransform"]}, sort_keys=True).encode()
        transform_sha = hashlib.sha256(transform_raw).hexdigest()
        transform_path = _RENDERER_EVIDENCE_ROOT / f"node-{transform_sha}.json"
        transform_path.write_bytes(transform_raw)
        sources = [{"role": "target-node-transform", "sourcePath": str(transform_path), "sha256": transform_sha}]
        if row["rendererKind"] == "SkeletonGraphic":
            canvas_raw = json.dumps({"canvas": row["canvasIdentity"],
                                     "referencePixelsPerUnit": row["canvasReferencePixelsPerUnit"]},
                                   sort_keys=True).encode()
            canvas_sha = hashlib.sha256(canvas_raw).hexdigest()
            canvas_path = _RENDERER_EVIDENCE_ROOT / f"canvas-{canvas_sha}.json"
            canvas_path.write_bytes(canvas_raw)
            sources.append({"role": "canvas-reference-pixels-per-unit",
                            "sourcePath": str(canvas_path), "sha256": canvas_sha})
        row["evidenceSources"] = sources
        contexts.append(row)
    document = {"schemaVersion": 1, "contract": "monkey-unity-spine-renderer-context/1",
                "status": "declared", "nativeReadback": "not_run",
                "sourceManifestSha256": source_sha, "normalizedIrSha256": ir_sha,
                "contexts": contexts}
    raw = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode()
    digest = hashlib.sha256(raw).hexdigest()
    path = _RENDERER_EVIDENCE_ROOT / f"renderer-contexts-{digest}.json"
    path.write_bytes(raw)
    return {"sourcePath": str(path), "sha256": digest}


def fixture():
    source_sha = "a" * 64
    ir_sha = "b" * 64
    runtime_manifest = "c" * 64
    skeleton_sha = "d" * 64
    atlas_sha = "e" * 64
    texture_sha = "f" * 64
    shader_sha = hashlib.sha256(Path("src/grea/recovery/targets/materials/spine/UnitySpineSourceProfile.shader").read_bytes()).hexdigest()
    ids = ["gameAsset:prefab#1/components/0", "gameAsset:prefab#2/components/0"]
    data_id = "spineAsset:data"
    source_material_ref = "gameAsset:material"
    material_target = "internal:material"
    components = []
    for index, source_id in enumerate(ids):
        components.append({
            "sourceComponentId": source_id,
            "sourcePrefabId": "gameAsset:prefab",
            "sourceNodeId": str(index + 1),
            "sourceNodePath": f"Root/Spine{index}",
            "sourceDataAssetId": data_id if index == 0 else None,
            "sourceSerializedFields": {"_materials": [{"__uuid__": "material"}]},
            "unity": {"fields": {"animation": {"status": "explicit", "sourceValue": "idle"},
                                   "skin": {"status": "explicit", "sourceValue": "default"}}},
        })
    material_rows = [{"sourceComponentId": sid,
                      "sourceMaterialReferenceSourceId": source_material_ref,
                      "sourceMaterialSourceId": material_target} for sid in ids]
    page = {"pageIndex": 0, "pageName": "source-page.png", "sourceTextureSourceId": "gameAsset:texture",
            "materialIdentitySeeds": {"normal": "seed/normal"}}
    unity_material_rows = [
        {"sourceComponentId": ids[0], "status": "profile-materials-defined", "pmaVertexColors": False,
         "sourceAtlasPages": [page], "variants": [{"blendMode": "normal", "sourceSlotCount": 3}]},
        {"sourceComponentId": ids[1], "status": "no-serialized-skeleton-data-no-render-material-closure"},
    ]
    emission = {
        "contract": "monkey-spine-emission/1", "sourceVersion": "2.4.15", "sourceComponentCount": 2,
        "pins": {"sourceManifestSha256": source_sha, "normalizedIrSha256": ir_sha},
        "components": components,
        "assets": [{"sourceId": data_id, "sourceSkeletonSha256": skeleton_sha,
                    "sourceSpineVersion": "3.8.99", "unity": {
                        "candidateInputPath": "Assets/Game/Spine/rig.skel.bytes",
                        "atlasPath": "Assets/Game/Spine/rig.atlas.txt"}}],
        "copies": [
            {"sourceId": data_id, "path": "Assets/Game/Spine/rig.skel.bytes", "sha256": skeleton_sha, "target": "unity"},
            {"sourceId": data_id, "path": "Assets/Game/Spine/rig.atlas.txt", "sha256": atlas_sha, "target": "unity"},
            {"sourceId": data_id, "path": "Assets/Game/Spine/renamed-page.png", "sha256": texture_sha, "target": "unity"},
        ],
    }
    material_contract = {
        "schema": "monkey-spine-material-contract/1", "profile": "cocos24-builtin-spine-material-v1",
        "creatorBindingStatus": "source-semantics-exact-builtin-spine",
        "pins": {"sourceManifestSha256": source_sha, "normalizedIrSha256": ir_sha,
                 "materialReferenceSourceId": source_material_ref, "materialSourceId": material_target},
        "spec": {"creator38": {"targetMaterialUuid": "default-spine-material", "perComponent": material_rows},
                 "unity": {"shaderSourceSha256": shader_sha, "perComponent": unity_material_rows}},
    }
    closure = {"skeletons": [{"sourceId": data_id, "status": "closure_recovered",
        "skeletonPath": "Assets/Game/Spine/rig.skel.bytes", "atlasPath": "Assets/Game/Spine/rig.atlas.txt",
        "sourceSkeletonSha256": skeleton_sha, "sourceAtlasSha256": atlas_sha,
        "dependencies": [{"page": "source-page.png", "sourceId": "gameAsset:texture", "sourceSha256": texture_sha,
                          "targetPage": "renamed-page.png"}]}]}
    file_names = ["spine-csharp.dll", "spine-unity.dll", "Shaders/Spine-SkeletonGraphic.shader", "LICENSE"]
    checks = {name: {"verified": True, "expectedSha256": hashlib} for name, hashlib in
              zip(file_names, ("2" * 64, "3" * 64, "4" * 64, "5" * 64))}
    runtime_evidence = {"unity": {"spinePlugin": {"compiledAgainst": "Unity6000.6.2f1",
        "sourceVersion": "3.8.99", "upstreamCommit": "commit", "manifestSha256": runtime_manifest,
        "fileChecks": checks}}}
    stage = {"verified": True, "destination": "/private/UnityRuntimeStage/Assets/Plugins/Spine38",
             "sourceManifestSha256": runtime_manifest,
             "copiedFiles": {name: {"verified": True, "sha256": data["expectedSha256"]}
                             for name, data in checks.items()}}
    target_unit_evidence = {"status": "verified_unit_mapping", "targetUnitsPerSourcePixel": 1.0,
                           "worldSpaceCanvasScale": 1.0, "pixelsPerUnitConversion": None,
                           "evidenceSource": "neutral fixture",
                           "rendererContexts": _write_renderer_contexts(source_sha, ir_sha, _default_context_rows(ids))}
    return emission, material_contract, closure, runtime_evidence, stage, target_unit_evidence


class PrefabSpineNativePlanTests(unittest.TestCase):
    def test_join_preserves_bound_and_unbound_components_and_material_source_identity(self):
        plan = build_unity_native_binding_plan(*fixture())
        self.assertEqual(plan["componentCount"], 2)
        self.assertEqual(plan["sourceStaticDataBoundCount"], 1)
        self.assertEqual(plan["sourceStaticDataUnboundCount"], 1)
        self.assertEqual(plan["dataAssetCount"], 1)
        self.assertEqual(plan["components"][1]["staticDataState"], "source_uuid_absent_component_preserved_unbound")
        self.assertEqual(plan["components"][0]["creatorMaterialBinding"]["targetMaterialUuid"], "default-spine-material")
        self.assertEqual(plan["dataAssets"][0]["pages"][0]["nativeAtlasPage"], "renamed-page.png")
        self.assertEqual(plan["dataAssets"][0]["scale"], 0.01)
        self.assertEqual(plan["scaleEvidence"]["status"], "verified_source_renderer_unit_mapping")
        self.assertEqual(plan["dataAssets"][0]["factoryInput"]["scale"], 0.01)
        self.assertEqual(plan["dataAssets"][0]["scaleEvidence"]["formula"],
                         "sourceDefaultScale * targetUnitsPerSourcePixel / canvasReferencePixelsPerUnit")
        self.assertEqual(plan["components"][0]["rendererSelection"]["rendererKind"], "SkeletonGraphic")
        self.assertEqual(plan["components"][0]["rendererSelection"]["status"], "declared_not_native_readback")
        factory = plan["dataAssets"][0]["factoryInput"]
        self.assertEqual(factory["graphicShaderName"], "Monkey/SpineSourceGraphicProfile/Colored")
        self.assertTrue(factory["pages"][0]["graphicNormalMaterialAssetPath"].endswith("_normal_graphic.mat"))
        self.assertEqual(plan["unityGraphicShader"]["sha256"],
                         hashlib.sha256(Path(plan["unityGraphicShader"]["sourcePath"]).read_bytes()).hexdigest())
        self.assertEqual(plan["unityGraphicShader"]["targetPath"], "Assets/Game/Content/Shaders/UnitySpineGraphicProfile.shader")

    def test_changed_nonempty_source_material_ref_is_rejected(self):
        values = list(fixture())
        values[0] = copy.deepcopy(values[0])
        values[0]["components"][0]["sourceSerializedFields"]["_materials"][0]["__uuid__"] = "wrong"
        with self.assertRaisesRegex(SpineNativePlanError, "serialized material references"):
            build_unity_native_binding_plan(*values)

    def test_runtime_license_or_dll_hash_mismatch_is_rejected(self):
        values = list(fixture())
        values[4] = copy.deepcopy(values[4])
        values[4]["copiedFiles"]["LICENSE"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(SpineNativePlanError, "runtime copy differs"):
            build_unity_native_binding_plan(*values)

    def test_verified_paired_editor_variant_is_joined_and_identity_pinned(self):
        values = list(fixture())
        runtime = copy.deepcopy(values[3]["unity"]["spinePlugin"])
        stage = copy.deepcopy(values[4])
        editor_hashes = {"spine-csharp.dll": "6" * 64, "spine-unity.dll": "7" * 64}
        refs_core = [{"name": "netstandard", "version": "2.1.0.0"}]
        refs_unity = [{"name": "spine-csharp", "version": "0.0.0.0"},
                      {"name": "UnityEditor.CoreModule", "version": "0.0.0.0"}]
        runtime["editorVariant"] = {
            "status": "verified_editor_source_build", "upstreamCommit": "commit",
            "compiledAgainst": "Unity6000.6.2f1", "compileDefines": ["UNITY_EDITOR"],
            "sourceManifestSha256": "8" * 64,
            "importPolicy": "paired_editor_only_assemblies_player_pair_excludes_editor",
            "cocosCompatibilityFallbacksIncluded": False,
            "evidencePath": "/private/evidence.json", "evidenceSha256": "9" * 64,
            "playerAssemblyHashes": {name: runtime["fileChecks"][name]["expectedSha256"]
                                     for name in ("spine-csharp.dll", "spine-unity.dll")},
            "assemblies": {
                "spine-csharp.dll": {"sha256": editor_hashes["spine-csharp.dll"], "bytes": 8,
                    "assemblyName": "spine-csharp", "assemblyVersion": "0.0.0.0",
                    "playerReferenceIdentity": {"name": "spine-csharp", "version": "0.0.0.0"},
                    "references": refs_core, "runtimeImportPath": "Assets/Plugins/Spine38/EditorRuntime/spine-csharp.dll"},
                "spine-unity.dll": {"sha256": editor_hashes["spine-unity.dll"], "bytes": 8,
                    "assemblyName": "spine-unity", "assemblyVersion": "0.0.0.0",
                    "playerReferenceIdentity": {"name": "spine-unity", "version": "0.0.0.0"},
                    "references": refs_unity, "runtimeImportPath": "Assets/Plugins/Spine38/EditorRuntime/spine-unity.dll"},
            },
        }
        stage["editorVariant"] = {"status": "verified_editor_source_build",
            "sourceManifestSha256": "8" * 64,
            "copiedFiles": {name: {"sha256": digest, "verified": True}
                            for name, digest in editor_hashes.items()}}
        values[3]["unity"]["spinePlugin"] = runtime
        values[4] = stage
        plan = build_unity_native_binding_plan(*values)
        self.assertEqual(plan["runtime"]["editorVariant"]["status"], "verified_editor_source_build")
        self.assertEqual(plan["runtime"]["editorVariant"]["assemblies"]["spine-unity.dll"]["sha256"],
                         editor_hashes["spine-unity.dll"])
        self.assertEqual(plan["runtime"]["editorVariant"]["assemblyLoadVerification"]["status"], "not_run")

    def test_editor_variant_rejects_unpaired_core_api_or_missing_editor_define(self):
        for failure in ("core_ref", "define"):
            with self.subTest(failure=failure):
                values = list(fixture())
                runtime = copy.deepcopy(values[3]["unity"]["spinePlugin"])
                stage = copy.deepcopy(values[4])
                runtime["editorVariant"] = {
                    "status": "verified_editor_source_build", "upstreamCommit": "commit",
                    "compiledAgainst": "Unity6000.6.2f1", "compileDefines": ["UNITY_EDITOR"],
                    "sourceManifestSha256": "8" * 64,
                    "importPolicy": "paired_editor_only_assemblies_player_pair_excludes_editor",
                    "cocosCompatibilityFallbacksIncluded": False,
                    "playerAssemblyHashes": {name: runtime["fileChecks"][name]["expectedSha256"]
                                             for name in ("spine-csharp.dll", "spine-unity.dll")},
                    "assemblies": {
                        name: {"sha256": char * 64, "bytes": 8, "assemblyName": name[:-4],
                            "assemblyVersion": "0.0.0.0", "playerReferenceIdentity": {"name": name[:-4], "version": "0.0.0.0"},
                            "references": ([{"name": "netstandard", "version": "2.1.0.0"}] if name == "spine-csharp.dll"
                                else [{"name": "UnityEditor.CoreModule", "version": "0.0.0.0"},
                                      {"name": "spine-csharp", "version": "0.0.0.0"}]),
                            "runtimeImportPath": "Assets/Plugins/Spine38/EditorRuntime/" + name}
                        for name, char in (("spine-csharp.dll", "6"), ("spine-unity.dll", "7"))},
                }
                if failure == "core_ref":
                    runtime["editorVariant"]["assemblies"]["spine-unity.dll"]["references"] = [
                        row for row in runtime["editorVariant"]["assemblies"]["spine-unity.dll"]["references"]
                        if row["name"] != "spine-csharp"]
                else:
                    runtime["editorVariant"]["compileDefines"] = ["UNITY_6000_6_2"]
                stage["editorVariant"] = {"status": "verified_editor_source_build", "sourceManifestSha256": "8" * 64,
                    "copiedFiles": {name: {"sha256": char * 64, "verified": True}
                                    for name, char in (("spine-csharp.dll", "6"), ("spine-unity.dll", "7"))}}
                values[3]["unity"]["spinePlugin"] = runtime
                values[4] = stage
                with self.assertRaises(SpineNativePlanError):
                    build_unity_native_binding_plan(*values)

    def test_missing_target_unit_evidence_does_not_use_unity_scale_fallback(self):
        values = list(fixture())
        values[5] = None
        plan = build_unity_native_binding_plan(*values)
        self.assertIsNone(plan["dataAssets"][0]["factoryInput"]["scale"])
        self.assertEqual(plan["scaleEvidence"]["status"], "target_unit_evidence_missing")
        self.assertIn("UNITY_SPINE_SCALE_EVIDENCE_MISSING", {row["code"] for row in plan["diagnostics"]})

    def test_world_renderer_uses_source_to_target_units_without_canvas_divisor(self):
        values = list(fixture())
        values[5] = copy.deepcopy(values[5])
        # Regenerate a properly pinned document with a world renderer context.
        values[5]["rendererContexts"] = _write_renderer_contexts(
            values[0]["pins"]["sourceManifestSha256"], values[0]["pins"]["normalizedIrSha256"], [
                {"sourceComponentId": "gameAsset:prefab#1/components/0", "sourceNodeId": "1",
                 "rendererKind": "SkeletonAnimation", "targetNodeTransform": "Transform"},
                {"sourceComponentId": "gameAsset:prefab#2/components/0", "sourceNodeId": "2",
                 "rendererKind": "SkeletonAnimation", "targetNodeTransform": "Transform"},
            ])
        plan = build_unity_native_binding_plan(*values)
        self.assertEqual(plan["dataAssets"][0]["scale"], 1.0)
        self.assertEqual(plan["dataAssets"][0]["scaleEvidence"]["formula"],
                         "sourceDefaultScale * targetUnitsPerSourcePixel")

    def test_missing_or_legacy_renderer_context_never_certifies_graphic_scale(self):
        for mode in ("missing_component", "legacy_evidence"):
            with self.subTest(mode=mode):
                values = list(fixture())
                values[5] = copy.deepcopy(values[5])
                if mode == "missing_component":
                    values[5]["rendererContexts"] = _write_renderer_contexts(
                        values[0]["pins"]["sourceManifestSha256"], values[0]["pins"]["normalizedIrSha256"],
                        _default_context_rows(["gameAsset:prefab#1/components/0",
                                              "gameAsset:prefab#2/components/0"])[1:])
                else:
                    values[5].pop("rendererContexts")
                plan = build_unity_native_binding_plan(*values)
                self.assertIsNone(plan["dataAssets"][0]["scale"])
                self.assertEqual(plan["dataAssets"][0]["factoryInput"]["scale"], None)
                self.assertIn("UNITY_SPINE_RENDERER_UNIT_CONTEXT_MISSING",
                              {row["code"] for row in plan["diagnostics"]})
                self.assertNotEqual(plan["scaleEvidence"]["status"], "verified_source_renderer_unit_mapping")

    def test_invalid_graphic_canvas_ppu_is_rejected_without_fallback(self):
        values = list(fixture())
        values[5] = copy.deepcopy(values[5])
        values[5]["rendererContexts"] = _write_renderer_contexts(
            values[0]["pins"]["sourceManifestSha256"], values[0]["pins"]["normalizedIrSha256"],
            _default_context_rows(["gameAsset:prefab#1/components/0",
                                   "gameAsset:prefab#2/components/0"], ppu=0.0))
        with self.assertRaisesRegex(SpineNativePlanError, "Canvas PPU must be positive and finite"):
            build_unity_native_binding_plan(*values)

    def test_shared_source_data_with_different_renderer_or_canvas_ppu_is_explicitly_unresolved(self):
        source_id = "spineAsset:data"
        component_ids = ["gameAsset:prefab#1/components/0", "gameAsset:prefab#2/components/0"]
        for contexts in (
            [
                {"sourceComponentId": component_ids[0], "sourceNodeId": "1", "rendererKind": "SkeletonGraphic",
                 "targetNodeTransform": "RectTransform", "canvasIdentity": "Canvas/A", "canvasReferencePixelsPerUnit": 100.0},
                {"sourceComponentId": component_ids[1], "sourceNodeId": "2", "rendererKind": "SkeletonAnimation",
                 "targetNodeTransform": "Transform"},
            ],
            [
                {"sourceComponentId": component_ids[0], "sourceNodeId": "1", "rendererKind": "SkeletonGraphic",
                 "targetNodeTransform": "RectTransform", "canvasIdentity": "Canvas/A", "canvasReferencePixelsPerUnit": 100.0},
                {"sourceComponentId": component_ids[1], "sourceNodeId": "2", "rendererKind": "SkeletonGraphic",
                 "targetNodeTransform": "RectTransform", "canvasIdentity": "Canvas/B", "canvasReferencePixelsPerUnit": 200.0},
            ],
        ):
            with self.subTest(contexts=contexts):
                values = list(fixture())
                values[0] = copy.deepcopy(values[0])
                values[0]["components"][1]["sourceDataAssetId"] = source_id
                values[1] = copy.deepcopy(values[1])
                first = values[1]["spec"]["unity"]["perComponent"][0]
                values[1]["spec"]["unity"]["perComponent"][1] = dict(first, sourceComponentId=component_ids[1])
                values[5] = copy.deepcopy(values[5])
                values[5]["rendererContexts"] = _write_renderer_contexts(
                    values[0]["pins"]["sourceManifestSha256"], values[0]["pins"]["normalizedIrSha256"], contexts)
                plan = build_unity_native_binding_plan(*values)
                self.assertIsNone(plan["dataAssets"][0]["scale"])
                self.assertIn("UNITY_SPINE_RENDERER_CONTEXT_CONFLICT",
                              {row["code"] for row in plan["diagnostics"]})
                self.assertNotEqual(plan["scaleEvidence"]["status"], "verified_source_renderer_unit_mapping")

    def test_renderer_context_document_and_evidence_source_hashes_are_verified(self):
        values = list(fixture())
        pin = copy.deepcopy(values[5]["rendererContexts"])
        context_path = Path(pin["sourcePath"])
        context_path.write_text(context_path.read_text() + " ", encoding="utf-8")
        values[5] = copy.deepcopy(values[5]); values[5]["rendererContexts"] = pin
        with self.assertRaisesRegex(SpineNativePlanError, "renderer context source bytes differ"):
            build_unity_native_binding_plan(*values)

    def test_persistent_visible_pose_is_pinned_to_actual_spine_38_renderer_lifecycle(self):
        import os
        path = os.environ.get("GREA_TEST_SPINE38_COMPONENTS")
        if not path:
            self.skipTest("Requires the pinned Spine 3.8 component sources via GREA_TEST_SPINE38_COMPONENTS")
        runtime = Path(path)
        graphic = (runtime / "SkeletonGraphic.cs").read_bytes()
        animation = (runtime / "SkeletonAnimation.cs").read_bytes()
        renderer = (runtime / "SkeletonRenderer.cs").read_bytes()
        self.assertEqual(hashlib.sha256(graphic).hexdigest(),
                         "ce83a9686b6d79f94ad7bc4ff06c6d732dbca194ae921abfd0a69bc28df7afb4")
        self.assertEqual(hashlib.sha256(animation).hexdigest(),
                         "91674944a815287a9f7ef4f242d9f748db71d5585f2d36bce7559208948b1339")
        self.assertEqual(hashlib.sha256(renderer).hexdigest(),
                         "a56bc75ccd170f3cbb6523e318e02a99fb0af41713836cbd12df3b10e0971525")
        self.assertIn(b"canvasRenderer.Clear();", graphic)
        self.assertIn(b"deltaTime *= timeScale;", graphic)
        self.assertIn(b"UpdateMesh(keepRendererCount : true)", graphic)
        self.assertIn(b"deltaTime *= timeScale;", animation)



if __name__ == "__main__":
    unittest.main()
