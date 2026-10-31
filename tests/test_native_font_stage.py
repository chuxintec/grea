import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from monkey.native_font_stage import NativeFontStageError, finish_stage, stage
from monkey.native_font_stage import _classify_final_files, _validate_dependency_endpoints

BEAVER_SRC = Path(__file__).resolve().parents[3] / "tools/beaver/src"
sys.path.insert(0, str(BEAVER_SRC))
from beaver.candidate_snapshot import snapshot as beaver_snapshot, verify as beaver_verify


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return digest(raw)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def meta(guid):
    return f"fileFormatVersion: 2\nguid: {guid}\nDefaultImporter:\n  externalObjects: {{}}\n  userData: \n".encode()


class NativeFontStageTests(unittest.TestCase):
    def fixture(self, root):
        candidate = root / "saved-selection"
        completion = root / "font-completion"
        static_guid, primary_guid = "1" * 32, "2" * 32
        paths = {
            "Assets/Game/Content/Fonts/System/Static/e2.asset": b"old-static-font",
            "Assets/Game/Content/Fonts/System/Static/e2.asset.meta": meta(static_guid),
            "Assets/Game/Content/Fonts/System/dynamic.asset": b"old-dynamic-font",
            "Assets/Game/Content/Fonts/System/dynamic.asset.meta": meta(primary_guid),
            "Packages/manifest.json": json_bytes({"dependencies": {"com.unity.ugui": "2.6.0"}}),
            "Packages/packages-lock.json": json_bytes({"dependencies": {"com.unity.ugui": {
                "version": "2.6.0", "depth": 0, "source": "builtin", "dependencies": {}}}}),
            "ProjectSettings/ProjectVersion.txt": b"m_EditorVersion: 6000.6.2f1\n",
            "Assets/Game/Content/Prefabs/P04.prefab": b"prefab-before",
        }
        files = []
        for relpath, raw in paths.items():
            files.append({"path": relpath, "sha256": write(candidate / relpath, raw), "bytes": len(raw), "owner": "generated"})
        static_sha = next(row["sha256"] for row in files if row["path"].endswith("e2.asset"))
        primary_sha = next(row["sha256"] for row in files if row["path"].endswith("dynamic.asset"))
        static_path = "Assets/Game/Content/Fonts/System/Static/e2.asset"
        primary_path = "Assets/Game/Content/Fonts/System/dynamic.asset"
        corpus_sha, source_sha = "a" * 64, "b" * 64
        binding = {
            "schema": "monkey-unity-system-fonts/1", "status": "prepared",
            "systemFonts": {"schema": "monkey-unity-system-fonts/1", "status": "prepared",
                "targetOS": "macOS", "targetOSVersion": "27.0.1", "targetOSBuild": "26A434",
                "resolutionReceiptSha256": "c" * 64,
                "fonts": [
                    {"assetId": "coretext-static-sdf-test", "assetPath": static_path, "familyName": "PingFang SC",
                     "styleName": "Regular", "role": "fallback", "pointSize": 90,
                     "populationMode": "StaticSDFRequired", "generationMode": "CoreTextRasterizedStaticSDF",
                     "targetPostScriptName": "PingFangSC-Regular", "targetVariationAxesJson": "{\"wght\":400}",
                     "targetSystemFontFileUrl": "/System/Test.ttc", "targetSystemFontFileSha256": "d" * 64,
                     "fontFileCopiedOrExported": False, "matchingPhysicalFaces": [],
                     "sourceLabelIds": ["source-label"], "fallbackAssetIds": [],
                     "requiredGlyphs": [{"unicode": 65, "codepoint": "U+0041", "character": "A"},
                                        {"unicode": 66, "codepoint": "U+0042", "character": "B"}],
                     "requiredUnicode": [65, 66]},
                    {"assetId": "system-font-primary", "assetPath": primary_path, "familyName": "Arial",
                     "styleName": "Regular", "role": "primary", "populationMode": "DynamicOS",
                     "fallbackAssetIds": ["coretext-static-sdf-test"], "requiredUnicode": [65]},
                ]},
            "labelBindings": [{"sourceLabelId": "source-label", "sourceText": "A",
                               "sourceSystemFont": False,
                               "sourceEffectiveFontPolicy": "creator24-ttf-null-font-effective-family-arial-v1",
                               "sourceEffectiveFamily": "Arial", "nativeFontAssetId": "system-font-primary",
                               "nativeFallbackAssetIds": ["coretext-static-sdf-test"]}],
        }
        resolution = {"schema": "monkey-consumer-text-coretext-resolution/1", "status": "resolved",
                      "corpusSha256": corpus_sha, "labels": [{"text": "AB"}]}
        atlas = b"fake-png-bytes"
        metrics = b"fake-metrics"
        static_plan = json_bytes({"schema": "monkey-unity-coretext-static-sdf-plan/1", "status": "prepared"})
        generator_sha = digest((Path(__file__).resolve().parents[1] / "src/monkey/targets/GenerateCoreTextSdf.swift").read_bytes())
        generation_receipt = {"schema": "monkey-coretext-static-sdf-generation-receipt/1", "status": "generated",
                              "generatorSourceSha256": generator_sha}
        binding_sha = write(completion / "unity-static-font-binding.json", json_bytes(binding))
        resolution_sha = write(completion / "consumer-corpus-resolution.json", json_bytes(resolution))
        plan_sha = write(completion / "static-sdf-plan.json", static_plan)
        generation_sha = write(completion / "generation-receipt.json", json_bytes(generation_receipt))
        atlas_sha = write(completion / "glyph-atlas.png", atlas)
        metrics_sha = write(completion / "glyph-metrics.json", metrics)
        staged_root = completion / "UnityStage/Assets/Game/Content/Fonts/System/StaticSdfInputs/test"
        copy_rows = []
        for name, raw in (("glyph-atlas.png", atlas), ("glyph-metrics.json", metrics),
                          ("generation-receipt.json", b"portable-receipt")):
            file_sha = write(staged_root / name, raw)
            copy_rows.append({"relativePath": f"Assets/Game/Content/Fonts/System/StaticSdfInputs/test/{name}",
                              "sha256": file_sha, "sizeBytes": len(raw), "artifactKind": name})
        portable_sha = digest(b"portable-receipt")
        staged_root.joinpath("generation-receipt.json").write_bytes(b"portable-receipt")
        stage_report = {"schema": "monkey-unity-static-sdf-staged-inputs/1", "status": "staged",
                        "portableReceiptSha256": portable_sha, "copies": copy_rows}
        stage_report_sha = write(completion / "staging-report.json", json_bytes(stage_report))
        completion_record = {
            "schema": "monkey-native-font-completion/1", "status": "prepared",
            "nativeImport": "pending", "saveReopenReadback": "pending", "playerGlyphCheck": "pending",
            "selectedStaticFont": {"assetId": "coretext-static-sdf-test", "assetPath": static_path,
                                   "targetSystemFontFileSha256": "d" * 64},
            "baseGlyphCount": 1, "generatedGlyphCount": 2, "addedGlyphs": ["U+0042"],
            "primaryFontAssetIdsPreserved": ["system-font-primary"],
            "corpusSha256": corpus_sha, "sourceSha256": source_sha,
            "consumerResolutionReceiptSha256": resolution_sha,
            "bindingSha256": binding_sha, "planSha256": plan_sha,
            "generationReceiptSha256": generation_sha, "atlasSha256": atlas_sha,
            "metricsSha256": metrics_sha, "stagingReportSha256": stage_report_sha,
        }
        completion_sha = write(completion / "font-completion.json", json_bytes(completion_record))
        manifest = {
            "schemaVersion": 1, "targetProfile": "unity-6000.6.2f1-ugui",
            "namespace": "saved-selection/test-namespace", "sourceCandidateManifestSha256": "e" * 64,
            "sourceNativeReadbackSha256": "f" * 64,
            "selection": {"coverage": "selected-prefab-guid-closure", "prefabs": ["Assets/Game/Content/Prefabs/P04.prefab"]},
            "runtimeUpdate": {"evidencePath": "Analysis/Adoption/runtime-update.json",
                              "evidenceSha256": "9" * 64, "nativeValidation": "pending"},
            "adoptionDependencies": {"schemaVersion": 1, "coverage": "producer-declared", "edges": [
                {"path": "Assets/Game/Content/Prefabs/P04.prefab", "requires": [], "kind": "fixture"}]},
            "files": files,
            "nativeFontCoverageContract": {"fonts": [
                {"assetId": "coretext-static-sdf-test", "assetPath": static_path,
                 "assetGuid": static_guid, "assetSha256": static_sha, "populationMode": "Static"},
                {"assetId": "system-font-primary", "assetPath": primary_path,
                 "assetGuid": primary_guid, "assetSha256": primary_sha, "populationMode": "DynamicOS"},
            ]},
        }
        manifest_sha = write(candidate / "manifest.json", json_bytes(manifest))
        return candidate, completion, manifest_sha, completion_sha, static_path, static_sha, primary_sha, static_guid

    def test_stage_copies_verified_selection_and_emits_request_without_launching_editor(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            candidate, completion, manifest_sha, completion_sha, static_path, static_sha, primary_sha, static_guid = self.fixture(root)
            result = stage(candidate, manifest_sha, completion, completion_sha, root / "stage")
            project = Path(result["projectRoot"])
            self.assertEqual("staged", result["status"])
            self.assertEqual(static_sha, digest((project / static_path).read_bytes()))
            self.assertEqual(primary_sha, digest((project / "Assets/Game/Content/Fonts/System/dynamic.asset").read_bytes()))
            self.assertEqual(static_guid, (project / (static_path + ".meta")).read_text().split("guid: ")[1][:32])
            self.assertTrue((project / "Assets/Game/Editor/NativeFontCompletion/UnityStaticFontCompletion.cs").is_file())
            helper_path = project / "Assets/Game/Editor/NativeFontCompletion/UnitySystemFonts.cs"
            helper_bytes = helper_path.read_bytes()
            self.assertTrue(helper_bytes.startswith(b"#define MONKEY_STATIC_FONT_COMPLETION_ONLY\n"))
            self.assertTrue((project / "Analysis/NativeFontCompletion/Inputs/test/glyph-atlas.png").is_file())
            self.assertFalse((project / "Assets/Game/Content/Fonts/System/StaticSdfInputs/test/glyph-atlas.png").exists())
            self.assertEqual(static_sha, digest((candidate / static_path).read_bytes()))
            request = json.loads(Path(result["requestPath"]).read_text())
            self.assertEqual(result["stageManifestSha256"], request["stageManifestSha256"])
            self.assertEqual(["AB"], request["consumerTexts"])
            self.assertIn("com.unity.modules.jsonserialize", json.loads((project / "Packages/manifest.json").read_text())["dependencies"])
            self.assertIn("com.unity.modules.imageconversion", json.loads((project / "Packages/packages-lock.json").read_text())["dependencies"])
            self.assertFalse((project / "Assets/Game/Content/Fonts/GameFont/GameFont.asset").exists())
            staged_manifest = json.loads((project / "manifest.json").read_text())
            for key in ("namespace", "selection", "sourceNativeReadbackSha256", "runtimeUpdate", "adoptionDependencies"):
                self.assertEqual(json.loads((candidate / "manifest.json").read_text())[key], staged_manifest[key])
            self.assertEqual(staged_manifest["namespace"], "saved-selection/test-namespace")
            helper_record = next(row for row in staged_manifest["editorToolSources"]
                                 if row["path"].endswith("/UnitySystemFonts.cs"))
            self.assertEqual("font-only-completion-v1", helper_record["profile"])
            self.assertEqual(digest(helper_bytes), helper_record["emittedSha256"])
            template = (Path(__file__).resolve().parents[1] / "src/monkey/targets/UnitySystemFonts.cs").read_bytes()
            self.assertEqual(digest(template), helper_record["templateSha256"])
            self.assertEqual(digest(helper_bytes), helper_record["sha256"])
            _validate_dependency_endpoints(staged_manifest["adoptionDependencies"],
                                           {row["path"]: row for row in staged_manifest["files"]})
            self.assertTrue(all(row["owner"] in {"generated", "retained", "manual"}
                                for row in staged_manifest["files"]))
            snap_root, _, snap_files, snap_sha = beaver_snapshot(project)
            self.assertEqual(result["stageManifestSha256"], snap_sha)
            beaver_verify(snap_root, snap_files)

    def test_dependency_contract_fails_if_an_endpoint_was_dropped(self):
        with self.assertRaises(NativeFontStageError):
            _validate_dependency_endpoints({"edges": [{"path": "A.cs", "requires": ["Missing.cs"]}]},
                                           {"A.cs": {"path": "A.cs"}})

    def test_final_file_classification_keeps_source_editor_metadata_and_drops_only_temporary_helpers(self):
        source_files = {
            "Assets/Game/Editor.meta": {"path": "Assets/Game/Editor.meta", "stageRole": "source-selection-file"},
            "Assets/Game/Content/Prefabs/P04.prefab": {"path": "Assets/Game/Content/Prefabs/P04.prefab"},
            "Packages/manifest.json": {"path": "Packages/manifest.json"},
        }
        stage_files = {
            **source_files,
            "Assets/Game/Editor/NativeFontCompletion.meta": {"stageRole": "font-stage-folder-meta"},
            "Assets/Game/Editor/NativeFontCompletion/UnityStaticFontCompletion.cs": {"stageRole": "font-stage-editor-tool"},
            "Assets/Game/Editor/NativeFontCompletion/UnityStaticFontCompletion.cs.meta": {"stageRole": "font-stage-script-meta"},
            "Analysis/NativeFontCompletion/Inputs/test/glyph-atlas.png": {"stageRole": "font-input"},
            "Temp/EditorCache.asset": {"stageRole": "editor-cache"},
        }
        classified = _classify_final_files(stage_files, source_files, [
            {"path": "Assets/Game/Editor/NativeFontCompletion/UnityStaticFontCompletion.cs"}])
        self.assertEqual("retained-source-selection", classified["Assets/Game/Editor.meta"])
        self.assertEqual("retained-source-selection", classified["Packages/manifest.json"])
        self.assertEqual("retained-stage-evidence", classified["Analysis/NativeFontCompletion/Inputs/test/glyph-atlas.png"])
        self.assertEqual("excluded-editor-execution-helper", classified["Assets/Game/Editor/NativeFontCompletion/UnityStaticFontCompletion.cs.meta"])
        self.assertEqual("excluded-editor-execution-helper", classified["Assets/Game/Editor/NativeFontCompletion.meta"])
        self.assertEqual("excluded-non-evidence-stage-addition", classified["Temp/EditorCache.asset"])

    def test_stage_rejects_manifest_hash_drift_before_output(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            candidate, completion, _, completion_sha, *_ = self.fixture(root)
            output = root / "stage"
            with self.assertRaises(NativeFontStageError):
                stage(candidate, "0" * 64, completion, completion_sha, output)
            self.assertFalse(output.exists())

    def test_stage_rejects_changed_static_face_binding(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            candidate, completion, manifest_sha, completion_sha, *_ = self.fixture(root)
            binding = json.loads((completion / "unity-static-font-binding.json").read_text())
            binding["systemFonts"]["fonts"][0]["targetSystemFontFileSha256"] = "f" * 64
            binding_raw = json_bytes(binding)
            (completion / "unity-static-font-binding.json").write_bytes(binding_raw)
            record = json.loads((completion / "font-completion.json").read_text())
            record["bindingSha256"] = digest(binding_raw)
            (completion / "font-completion.json").write_bytes(json_bytes(record))
            new_completion_sha = digest((completion / "font-completion.json").read_bytes())
            with self.assertRaises(NativeFontStageError):
                stage(candidate, manifest_sha, completion, new_completion_sha, root / "stage")

    def test_finish_refuses_not_run_native_readback_without_emitting_candidate(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            candidate, completion, manifest_sha, completion_sha, static_path, *_ = self.fixture(root)
            stage_result = stage(candidate, manifest_sha, completion, completion_sha, root / "stage")
            project = Path(stage_result["projectRoot"])
            readback = {
                "schema": "monkey-unity-static-font-completion-readback/1", "status": "not_run",
                "stageManifestSha256": stage_result["stageManifestSha256"],
                "sourceSelectionManifestSha256": manifest_sha, "completionReceiptSha256": completion_sha,
            }
            readback_path = project / "Analysis/NativeFontCompletion/native-readback.json"
            readback_sha = write(readback_path, json_bytes(readback))
            with self.assertRaises(NativeFontStageError):
                finish_stage(project, stage_result["stageManifestSha256"], readback_path,
                             readback_sha, root / "final")
            self.assertFalse((root / "final").exists())


if __name__ == "__main__":
    unittest.main()
