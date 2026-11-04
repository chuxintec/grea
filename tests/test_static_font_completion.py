import unittest
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from monkey.prefab_static_font_completion import (
    ENGINE_EVIDENCE, SOURCE_EFFECTIVE_POLICY, _font_fallback_mapping,
    _merge_glyph_rows, _merge_resolution, _merge_static_plan, apply_prepared,
    _select_labels, _validate_preserved_glyph_denominator,
)


def label_component(sid, node, text, size=24):
    return {"sourceId": sid, "node": node, "type": "cc.Label", "convertible": False,
            "enabled": True, "font": None, "systemFont": False, "text": text, "fontSize": size,
            "fontFamily": "Arial", "fontFamilyEvidence": "creator-label-default-Arial"}


class StaticFontCompletionTests(unittest.TestCase):
    @staticmethod
    def write_json(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
        path.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest(), len(raw)

    def test_select_active_null_font_false_labels_from_raw_source(self):
        pref = "gameAsset:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        manifest = {"assets": [{"sourceId": pref, "document": {"root": 0, "instances": [
            {"__type__": "cc.Node", "_components": [
                {"__type__": "cc.Label", "_string": "出", "_fontSize": 24, "_isSystemFontUsed": False},
                {"__type__": "cc.Label", "_string": "隐藏", "_fontSize": 24, "_isSystemFontUsed": False}]},
            {"__type__": "cc.Prefab"}]}}]}
        sid1, sid2 = pref + "#0/components/0", pref + "#0/components/1"
        plan = {"nodes": [{"sourceId": "n1", "parent": None, "active": True},
                           {"sourceId": "n2", "parent": "n1", "active": False}],
                "components": [label_component(sid1, "n1", "出"), label_component(sid2, "n2", "隐藏")]}
        rows = _select_labels(plan, manifest)
        self.assertEqual([sid1, sid2], [row["sourceComponentId"] for row in rows])
        self.assertIsNone(rows[0]["sourceFont"])
        self.assertFalse(rows[0]["sourceSystemFont"])
        self.assertFalse(rows[1]["effectiveActive"])

    def test_glyph_union_keeps_existing_rows_and_rejects_identity_collision(self):
        old = [{"unicode": 12, "codepoint": "U+000C", "character": "\f"},
               {"unicode": 123, "codepoint": "U+007B", "character": "{"}]
        result = _merge_glyph_rows(old, [{"unicode": 20986, "codepoint": "U+51FA", "character": "出"}])
        self.assertEqual([12, 123, 20986], [row["unicode"] for row in result])
        with self.assertRaises(ValueError):
            _merge_glyph_rows(old, [{"unicode": 123, "codepoint": "U+007B", "character": "wrong"}])

    def test_resolution_merge_preserves_pinned_source_and_false_policy(self):
        source = "gameAsset:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa#1/components/0"
        base = {"schema": "monkey-macos-system-font-resolution/1", "status": "resolved", "targetOS": "macOS",
                "targetOSVersion": "27", "targetOSBuild": "B", "labels": [], "resolvedPrimaryFonts": [],
                "fallbackFonts": [], "resolvedFontFiles": [], "coreTextToPhysicalFaceEvidence": [],
                "glyphCoverage": {}, "sourceSample": {"sourceProfile": "cocos-2.4.15-bundle", "sourceVersion": "2.4.15",
                    "sourceManifestSha256": "m" * 64, "normalizedSystemFontLabelCount": 0,
                    "sourceStaticTextLabelCount": 0, "sourceFamilyBindings": []}}
        added = {"labels": [{"targetLabelId": source, "text": "出", "pointSize": 24,
                             "resolvedPrimaryFamily": "Arial", "unicodeScalars": []}],
                 "resolvedPrimaryFonts": [], "fallbackFonts": [], "resolvedFontFiles": [],
                 "coreTextToPhysicalFaceEvidence": [], "glyphCoverage": {"requiredUnicodeOccurrences": 1,
                    "coveredUnicodeOccurrences": 1, "missingUnicodeOccurrences": 0, "missing": [], "perUnicodeScalar": []}}
        label = {"sourceComponentId": source, "sourceText": "出", "fontSize": 24,
                 "sourceFontFamilyEvidence": "creator-label-default-Arial"}
        ir = {"components": [label_component(source, "n", "出")]}
        merged = _merge_resolution(base, added, [label], __import__("pathlib").Path("prep.json"),
                                   "i" * 64, __import__("pathlib").Path("manifest.json"), "m" * 64)
        binding = merged["sourceSample"]["sourceFamilyBindings"][0]
        self.assertFalse(binding["sourceSystemFont"])
        self.assertEqual(SOURCE_EFFECTIVE_POLICY, binding["sourceEffectiveFontPolicy"])
        self.assertFalse(merged["visualEquivalent"])

    def test_static_face_union_preserves_asset_identity_and_existing_glyphs(self):
        base_face = {"assetId": "coretext-static-sdf-123456789012345678901234",
                     "targetSystemFontFileSha256": "f" * 64,
                     "requiredGlyphs": [{"unicode": 12, "codepoint": "U+000C", "character": "\f"}],
                     "sourceLabelIds": ["old-label"]}
        fresh_face = {"assetId": base_face["assetId"], "targetSystemFontFileSha256": "f" * 64,
                      "requiredGlyphs": [{"unicode": 20986, "codepoint": "U+51FA", "character": "出"}],
                      "sourceLabelIds": ["new-label"], "atlasContract": {"allowedCodepoints": [20986]}}
        plan = {"systemFonts": [fresh_face]}
        result = _merge_static_plan(base_face, plan, base_face, ["new-label"])
        face = result["systemFonts"][0]
        self.assertEqual([12, 20986], face["requiredUnicode"])
        self.assertEqual(["new-label", "old-label"], face["sourceLabelIds"])
        self.assertEqual(face["requiredUnicode"], face["atlasContract"]["allowedCodepoints"])

    def test_output_binding_keeps_source_system_font_false(self):
        source = "label-source"
        binding = {"labelBindings": [{"sourceLabelId": source, "sourceSystemFont": True,
                                      "sourceSerializedFontUuid": None, "nativeFontAssetId": "arial",
                                      "nativeFallbackAssetIds": ["sdf"], "nativeFontAssetPath": "Arial.asset",
                                      "nativeFallbackAssetPaths": ["Fallback.asset"]}]}
        row = _font_fallback_mapping(binding, source, "出")
        self.assertIs(binding["labelBindings"][0], row)
        self.assertFalse(row["sourceSystemFont"])
        self.assertEqual("Arial", row["sourceEffectiveFamily"])
        self.assertEqual(ENGINE_EVIDENCE, ENGINE_EVIDENCE)

    def test_glyph_denominator_is_derived_from_three_old_glyphs(self):
        old = {"glyphs": [
            {"unicode": 32, "character": " "},
            {"unicode": 65, "character": "A"},
            {"unicode": 66, "character": "B"},
        ]}
        completion = {"preservedGlyphCount": 3, "generatedGlyphCount": 4,
                      "supplementalGlyphs": [{"unicode": 67, "character": "C"}]}
        supplemental = _validate_preserved_glyph_denominator(completion, old, [32, 65, 66, 67])
        self.assertEqual({67}, supplemental)

    def test_apply_prepared_accepts_two_labels_and_three_preserved_glyphs(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            base_stage = root / "BaseStage"
            out_stage = root / "CandidateStage"
            completion_root = root / "Completion"
            relative_dir = Path("Assets/Game/Content/Fonts/System/StaticSdfInputs/fallback")
            names = ("glyph-atlas.png", "glyph-metrics.json", "generation-receipt.json")
            old_copies, new_copies = [], []
            old_metrics = {"schema": "metrics", "glyphs": [
                {"unicode": 1, "character": "a"}, {"unicode": 2, "character": "b"},
                {"unicode": 3, "character": "c"}]}
            for i, name in enumerate(names):
                path = base_stage / relative_dir / name
                if name == "glyph-metrics.json":
                    old_hash, old_size = self.write_json(path, old_metrics)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(f"old-{i}".encode())
                    old_hash, old_size = hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size
                old_copies.append({"artifactKind": ("glyph-atlas", "glyph-metrics", "portable-generation-receipt")[i],
                                   "relativePath": (relative_dir / name).as_posix(), "sha256": old_hash, "sizeBytes": old_size})

            label_ids = ["source-label-a", "source-label-b"]
            source_labels = [label_component(sid, "node", text) for sid, text in zip(label_ids, ("a", "b"))]
            plan = {"sourceManifestSha256": "m" * 64, "sourceIrSha256": "i" * 64,
                    "components": source_labels,
                    "systemFontBinding": {"systemFonts": {"resolutionReceiptSha256": "base-resolution",
                        "fonts": [{"assetId": "fallback", "populationMode": "StaticSDFRequired",
                                   "requiredGlyphs": old_metrics["glyphs"], "sourceLabelIds": []}]}},
                    "staticFontInputs": {"candidateOutput": "BaseStage", "stageRoot": str(base_stage),
                                         "copies": old_copies}}
            plan_path = root / "Plan" / "plan.json"
            plan_sha, _ = self.write_json(plan_path, plan)

            binding_rows = [{"sourceLabelId": sid, "sourceSystemFont": False,
                "sourceSerializedFontUuid": None, "sourceEffectiveFontPolicy": SOURCE_EFFECTIVE_POLICY,
                "sourceEffectiveFamily": "Arial", "nativeFontAssetId": "arial",
                "nativeFontAssetPath": "Assets/Arial.asset", "nativeFallbackAssetIds": ["fallback"],
                "nativeFallbackAssetPaths": ["Assets/Fallback.asset"]} for sid in label_ids]
            glyphs = [{"unicode": i, "codepoint": f"U+{i:04X}", "character": chr(i)} for i in (1, 2, 3, 4)]
            binding = {"schema": "monkey-unity-system-fonts/1", "status": "prepared",
                "labelBindings": binding_rows, "systemFonts": {"resolutionReceiptSha256": "merged-resolution",
                    "sourceManifestSha256": "m" * 64, "staticCompletionPlanSha256": "",
                    "fonts": [{"assetId": "fallback", "populationMode": "StaticSDFRequired",
                        "targetSystemFontFileSha256": "f" * 64, "requiredGlyphs": glyphs,
                        "sourceLabelIds": label_ids}]}}
            static_plan = {"schema": "monkey-unity-coretext-static-sdf-plan/1", "targetOS": "macOS",
                           "targetOSVersion": "27", "systemFonts": []}
            static_sha, _ = self.write_json(completion_root / "static-sdf-plan.json", static_plan)
            binding["systemFonts"]["staticCompletionPlanSha256"] = static_sha
            binding_sha, _ = self.write_json(completion_root / "unity-static-font-binding.json", binding)
            metrics = {"schema": "monkey-coretext-static-sdf-glyph-metrics/1", "staticPlanSha256": static_sha,
                       "resolutionReceiptSha256": "merged-resolution", "fontFileSha256": "f" * 64,
                       "glyphs": glyphs}
            metrics_sha, _ = self.write_json(completion_root / "glyph-metrics.json", metrics)
            atlas_path = completion_root / "glyph-atlas.png"
            atlas_path.write_bytes(b"new-atlas")
            atlas_sha = hashlib.sha256(atlas_path.read_bytes()).hexdigest()
            receipt = {"schema": "monkey-coretext-static-sdf-generation-receipt/1", "status": "generated",
                "metricsPath": str(completion_root / "glyph-metrics.json"), "metricsSha256": metrics_sha,
                "atlasPath": str(atlas_path), "atlasSha256": atlas_sha, "planSha256": static_sha,
                "resolutionReceiptSha256": "merged-resolution", "targetOS": "macOS", "targetOSVersion": "27",
                "glyphCount": 4, "sourceLabelCount": 2}
            receipt_sha, _ = self.write_json(completion_root / "generation-receipt.json", receipt)
            source_stage = completion_root / "UnityStage"
            for i, row in enumerate(old_copies):
                name = Path(row["relativePath"]).name
                source = source_stage / row["relativePath"]
                if name == "glyph-metrics.json":
                    content = (json.dumps(metrics, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
                else:
                    content = f"new-{i}".encode()
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(content)
                new_copies.append({**row, "sha256": hashlib.sha256(content).hexdigest(), "sizeBytes": len(content)})
            portable = {"schema": "portable", "status": "portable_staged"}
            portable_content = (json.dumps(portable, sort_keys=True, indent=2) + "\n").encode()
            (source_stage / old_copies[2]["relativePath"]).write_bytes(portable_content)
            new_copies[2]["sha256"] = hashlib.sha256(portable_content).hexdigest()
            new_copies[2]["sizeBytes"] = len(portable_content)
            staging = {"schema": "monkey-unity-static-sdf-staged-inputs/1", "status": "staged",
                "sourceGenerationReceiptSha256": receipt_sha, "portableReceiptRelativePath": old_copies[2]["relativePath"],
                "portableReceiptSha256": new_copies[2]["sha256"], "stageRoot": str(source_stage), "copies": new_copies}
            staging_sha, _ = self.write_json(completion_root / "staging-report.json", staging)
            completion = {"schema": "monkey-unity-static-font-completion/1", "status": "prepared",
                "generationReceiptSha256": receipt_sha, "bindingPath": str(completion_root / "unity-static-font-binding.json"),
                "sourceManifestSha256": "m" * 64, "sourceIrSha256": "i" * 64,
                "sourceResolutionReceiptSha256": "base-resolution", "mergedResolutionReceiptSha256": "merged-resolution",
                "staticPlanSha256": static_sha, "preservedGlyphCount": 3, "generatedGlyphCount": 4,
                "supplementalGlyphs": [{"unicode": 4}], "stagingReportSha256": staging_sha,
                "planPath": str(plan_path), "planSha256": plan_sha,
                "labels": [{"sourceComponentId": sid, "sourceText": text, "sourceFontSize": 24,
                    "nativeFontAssetId": "arial", "nativeFontAssetPath": "Assets/Arial.asset",
                    "nativeFallbackAssetIds": ["fallback"], "nativeFallbackAssetPaths": ["Assets/Fallback.asset"]}
                    for sid, text in zip(label_ids, ("a", "b"))], "labelCount": 2}
            self.write_json(completion_root / "font-completion.json", completion)

            # Parent workflow may have already copied the old stage; only its pinned
            # old hashes are allowed to be replaced by the completion artifact hashes.
            for row in old_copies:
                target = out_stage / row["relativePath"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(base_stage / row["relativePath"], target)
            result = apply_prepared(plan, completion_root / "generation-receipt.json", receipt_sha,
                                    binding_sha, out_stage)
            self.assertEqual(2, result["updatedLabelCount"])
            self.assertEqual(3, len(result["plan"]["staticFontInputs"]["copies"]))
            for row in new_copies:
                target = out_stage / row["relativePath"]
                self.assertEqual(row["sha256"], hashlib.sha256(target.read_bytes()).hexdigest())
            self.assertTrue(all(c["convertible"] and c["systemFont"] is False and c["font"] is None
                                for c in result["plan"]["components"]))


if __name__ == "__main__":
    unittest.main()
