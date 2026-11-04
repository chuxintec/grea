import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from monkey.prefab_font_binding import (  # noqa: E402
    I18N_SOURCE_SHA256,
    SOURCE_WRAPPER_SHA256,
    _label_config,
    _font_file_face_evidence,
    analyze_prefab_font_binding_files,
    resolve_macos_system_font_runs,
    resolve_ir_macos_system_font_files,
)


PRIVATE = ROOT / ".private/v070-prefab-20261029"
IR = PRIVATE / "Pure01/normalize/ir.json"
MANIFEST = PRIVATE / "Pure01/inspect/source-manifest.json"
I18N_SOURCE = PRIVATE / "source-modules/i18nLabel.js"
RUNTIME_SOURCE = ROOT / "outputs/v050-foodstreet-source-reuse/InputTree/snapshot/_subpackages_main_/subpackages/main/game.js"
ZH_CACHE = ROOT / "outputs/v050-foodstreet-source-reuse/InputTree/original/resource-cache/zh/17924613037582.json"


class PrefabFontBindingTests(unittest.TestCase):
    def test_frozen_prefab_inventory_translation_and_exact_font_identities(self):
        report = analyze_prefab_font_binding_files(
            IR, MANIFEST, I18N_SOURCE, RUNTIME_SOURCE, {"zh": ZH_CACHE}
        )
        self.assertEqual(report.status, "source_bound_with_explicit_gaps")
        record = report.record
        self.assertEqual(record["inventory"], {
            "labels": 164,
            "systemFontUnboundLabels": 113,
            "labelsWithSerializedFontUuid": 51,
            "i18nComponents": 53,
            "rawSerializedI18nComponents": 2,
        })
        self.assertEqual(record["sourceProvenance"]["i18nComponentSourceSha256"], I18N_SOURCE_SHA256)
        self.assertEqual(record["sourceProvenance"]["runtimeWrapperSourceSha256"], SOURCE_WRAPPER_SHA256)
        system = record["bindingDeclarations"]["systemFontLabels"]
        self.assertIsNone(system["fontAssetUuid"])
        self.assertEqual(system["count"], 113)

        fonts = {item["sourceFontId"]: item for item in record["bindingDeclarations"]["sourceSerializedCustomFonts"]}
        bitmap_id = "gameAsset:118619d0-817c-4cd4-906b-db1cc70d3baf"
        ttf_id = "gameAsset:35e08b37-cc3c-4568-97a3-998dca149303"
        self.assertEqual(fonts[bitmap_id]["count"], 47)
        self.assertEqual(fonts[bitmap_id]["resolvedSourceId"], "main:118619d0-817c-4cd4-906b-db1cc70d3baf")
        self.assertEqual(fonts[bitmap_id]["serializedSourceLogicalPath"], "Texture/UI/Home/Font/Font_GYM")
        self.assertEqual(fonts[bitmap_id]["bitmapGlyphCount"], 90)
        self.assertEqual(fonts[bitmap_id]["bitmapAtlasRef"], "main:b441550f-1bdc-4360-b0db-6c8a6ece9534")
        self.assertEqual(fonts[ttf_id]["count"], 4)
        self.assertEqual(fonts[ttf_id]["sourceAssetLogicalPath"], "Font/en")
        coverage_audit = record["glyphMetadataAudit"]["staticSystemLabelTextCoverageAgainstExistingSerializedBitmapFonts"][bitmap_id]
        self.assertEqual(coverage_audit["systemFontLabelCount"], 113)
        self.assertGreater(coverage_audit["sourceTextsWithMissingGlyphs"], 0)

        translations = {item["i18nKey"]: item for item in record["localizedSourceComponents"]}
        self.assertEqual(translations["mm.desc"]["translations"]["zh"], "加油完成订单，收集更多金铲子吧！")
        self.assertEqual(translations["cardShow_continue"]["translations"]["zh"], "继续")
        self.assertTrue(translations["mm.desc"]["normalizedLabelSystemFont"])
        coverage = translations["mm.desc"]["coverageAgainstExistingSerializedBitmapFonts"][bitmap_id]["zh"]
        self.assertEqual(coverage["missingCharacters"], "加单吧多子完成收更油订金铲集！，")
        self.assertEqual(translations["cardShow_continue"]["coverageAgainstExistingSerializedBitmapFonts"][bitmap_id]["zh"]["missingCharacters"], "继续")
        self.assertNotIn(ttf_id, translations["mm.desc"]["coverageAgainstExistingSerializedBitmapFonts"])

        lifecycle = record["i18nLifecycleContract"]
        self.assertTrue(lifecycle["managerAndComponentShareExactWrapper"])
        self.assertFalse(lifecycle["serializedDefaults"]["bitmapEn"])
        self.assertEqual(lifecycle["managerCallSites"].get("getBitmapFont"), None)
        self.assertNotIn("decode", lifecycle["managerCallSites"])
        self.assertEqual(lifecycle["fontReplacementStatus"], "not_source_proven")

    def test_raw_cache_parser_extracts_config_label_payload(self):
        labels, digest = _label_config(ZH_CACHE)
        self.assertEqual(labels["mm.desc"], "加油完成订单，收集更多金铲子吧！")
        self.assertEqual(labels["cardShow_continue"], "继续")
        self.assertEqual(digest, hashlib.sha256(ZH_CACHE.read_bytes()).hexdigest())

    def test_modified_source_bytes_fail_closed_before_binding(self):
        ir = json.loads(IR.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        component = I18N_SOURCE.read_bytes() + b"\n// modified"
        runtime = RUNTIME_SOURCE.read_bytes()
        from monkey.prefab_font_binding import analyze_prefab_font_bindings
        report = analyze_prefab_font_bindings(ir, manifest, component, runtime, {"zh": ZH_CACHE})
        self.assertEqual(report.status, "unsupported")
        self.assertIn("component source hash", report.record["reason"])

    def test_pure02_macos_coretext_query_reports_current_target_and_source_uncertainty(self):
        if sys.platform != "darwin":
            self.skipTest("CoreText target evidence is macOS-only")
        pure02 = PRIVATE / "Pure02"
        report = resolve_ir_macos_system_font_files(
            pure02 / "normalize/ir.json", pure02 / "inspect/source-manifest.json"
        )
        self.assertIn(report.status, {"resolved", "partial"})
        record = report.record
        self.assertEqual(record["targetOS"], "macOS")
        self.assertTrue(record["targetOSVersion"])
        self.assertEqual(record["requestedFamily"], "Arial")
        self.assertEqual(record["sourceDefaultEvidence"]["sourceVersion"], "2.4.15")
        self.assertFalse(record["sourceDefaultEvidence"]["sourceOSIdentityVerified"])
        self.assertFalse(record["visualEquivalent"])
        self.assertEqual(record["sourceSample"]["normalizedSystemFontLabelCount"], 118)
        self.assertEqual(record["glyphCoverage"]["requiredUnicodeOccurrences"], 675)
        self.assertEqual(record["glyphCoverage"]["missingUnicodeOccurrences"], 0)
        self.assertTrue(record["resolvedPrimaryFonts"])
        self.assertTrue(record["fallbackFonts"])
        self.assertTrue(record["resolver"]["officialDocumentation"])

    def test_pure03_generic_file_entry_pins_ir_source_manifest_and_family_styles(self):
        if sys.platform != "darwin":
            self.skipTest("CoreText target evidence is macOS-only")
        pure03 = PRIVATE / "Pure03"
        ir_path = pure03 / "normalize/ir.json"
        source_path = pure03 / "inspect/source-manifest.json"
        report = resolve_ir_macos_system_font_files(ir_path, source_path)
        self.assertIn(report.status, {"resolved", "partial"})
        record = report.record
        source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
        ir_sha = hashlib.sha256(ir_path.read_bytes()).hexdigest()
        self.assertEqual(record["sourceSample"]["name"], "Pure03")
        self.assertEqual(record["sourceSample"]["sourceManifestSha256"], source_sha)
        self.assertEqual(record["sourceSample"]["frozenInputs"]["sourceManifest"]["sha256"], source_sha)
        self.assertEqual(record["sourceSample"]["frozenInputs"]["ir"]["sha256"], ir_sha)
        self.assertEqual(record["sourceSample"]["normalizedSystemFontLabelCount"], 118)
        family_bindings = record["sourceSample"]["sourceFamilyBindings"]
        self.assertEqual(len(family_bindings), 118)
        self.assertEqual({row["requestedFamily"] for row in family_bindings}, {"Arial"})
        self.assertEqual({row["familyBindingSource"] for row in family_bindings}, {"creator-label-default-Arial"})
        self.assertTrue(all("styleName" in font for font in record["resolvedPrimaryFonts"]))
        self.assertTrue(all("styleName" in font for font in record["fallbackFonts"]))
        self.assertTrue(all("styleName" in row["resolutions"][0]
                            for row in record["glyphCoverage"]["perUnicodeScalar"]))
        self.assertFalse(record["sourceDefaultEvidence"]["sourceOSIdentityVerified"])
        self.assertFalse(record["visualEquivalent"])

    def test_generic_run_resolver_preserves_each_requested_family(self):
        if sys.platform != "darwin":
            self.skipTest("CoreText target evidence is macOS-only")
        report = resolve_macos_system_font_runs([
            {"id": "label-a", "text": "A", "pointSize": 24, "requestedFamily": "Arial"},
            {"id": "label-b", "text": "B", "pointSize": 24, "requestedFamily": "Helvetica"},
        ])
        self.assertIn(report.status, {"resolved", "partial"})
        self.assertEqual(report.record["requestedFamily"], "per-label")
        self.assertEqual(report.record["requestedFamilies"], ["Arial", "Helvetica"])
        by_id = {row["targetLabelId"]: row for row in report.record["labels"]}
        self.assertEqual(by_id["label-a"]["requestedFamily"], "Arial")
        self.assertEqual(by_id["label-b"]["requestedFamily"], "Helvetica")

    def test_macos_resolver_returns_needs_action_off_target_without_querying(self):
        with patch("monkey.prefab_font_binding.platform.system", return_value="Linux"):
            report = resolve_macos_system_font_runs([{"id": "x", "text": "测试", "pointSize": 16}])
        self.assertEqual(report.status, "needs_action")
        self.assertIn("only on macOS", report.record["reason"])

    def test_coretext_font_file_evidence_resolves_exact_physical_ttc_face_without_export(self):
        if sys.platform != "darwin":
            self.skipTest("CoreText font file evidence is macOS-only")
        evidence = _font_file_face_evidence(
            "/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc"
        )
        self.assertEqual(evidence["status"], "inspected")
        self.assertEqual(evidence["container"], "TTC")
        self.assertFalse(evidence["fontBytesCopiedOrExported"])
        exact = [face for face in evidence["faces"] if face.get("postScriptName") == "PingFangSC-Regular"]
        same_family = [face for face in evidence["faces"] if face.get("family") == "PingFang SC"]
        self.assertEqual(exact, [])
        self.assertEqual(same_family, [{
            "faceIndex": 20,
            "family": "PingFang SC",
            "subfamily": "Medium",
            "fullName": "PingFang SC",
            "postScriptName": "PingFangSC-Medium",
        }])


if __name__ == "__main__":
    unittest.main()
