import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from monkey.prefab_system_fonts import prepare, prepare_static_coretext_sdf_plan, prepare_static_inputs  # noqa: E402


PRIVATE = ROOT / ".private/v070-prefab-20261029"
PURE03 = PRIVATE / "Pure03"
IR_PATH = PURE03 / "normalize/ir.json"
RESOLUTION_PATH = PRIVATE / "font-binding/macos-system-font-resolution-pure03.json"


class PrefabSystemFontsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ir_raw = IR_PATH.read_bytes()
        cls.ir = json.loads(cls.ir_raw.decode("utf-8"))
        cls.ir_sha = hashlib.sha256(cls.ir_raw).hexdigest()
        cls.resolution_raw = RESOLUTION_PATH.read_bytes()
        cls.resolution_sha = hashlib.sha256(cls.resolution_raw).hexdigest()

    def prepare(self, ir=None, resolution_path=RESOLUTION_PATH, resolution_sha=None):
        return prepare(ir or self.ir, self.ir_sha, resolution_path,
                       resolution_sha or self.resolution_sha)

    def test_prepares_exact_receipt_bound_dynamicos_assets_and_per_label_chains(self):
        result = self.prepare()
        self.assertEqual(result.status, "prepared")
        record = result.record
        system_fonts = record["systemFonts"]
        self.assertEqual(system_fonts["schema"], "monkey-unity-system-fonts/1")
        self.assertEqual(system_fonts["targetOS"], "macOS")
        self.assertEqual(system_fonts["targetOSVersion"], "27.0.1")
        self.assertEqual(system_fonts["runtimePlatformConstraint"], "macOS Player target only; native asset creation requires macOS Editor")
        self.assertEqual(system_fonts["playerTargetEvidence"], "not_run")
        self.assertEqual(system_fonts["irSha256"], self.ir_sha)
        self.assertEqual(system_fonts["resolutionReceiptSha256"], self.resolution_sha)
        self.assertEqual(system_fonts["sourceManifestSha256"], "62a8d82766902363401e2d009fb5502307b4b1f7c8774a23778c82efaef49a8c")
        self.assertFalse(system_fonts["sourceOSIdentityVerified"])
        self.assertFalse(system_fonts["visualEquivalent"])
        self.assertEqual(system_fonts["populationMode"], "Mixed")
        self.assertEqual(system_fonts["pointSize"], 90)
        self.assertEqual(len(record["labelBindings"]), 118)
        self.assertEqual(system_fonts["explicitFontLabelCountExcluded"], 70)
        self.assertEqual(system_fonts["explicitFontLabelsReplaced"], [])

        ids = [font["assetId"] for font in system_fonts["fonts"]]
        paths = [font["assetPath"] for font in system_fonts["fonts"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(paths), len(set(paths)))
        second_pass = self.prepare().record["systemFonts"]["fonts"]
        self.assertEqual([(font["assetId"], font["assetPath"]) for font in system_fonts["fonts"]],
                         [(font["assetId"], font["assetPath"]) for font in second_pass])
        self.assertTrue(all(path.startswith("Assets/Game/Content/Fonts/System/") and path.endswith(".asset") for path in paths))
        self.assertTrue(all(font["populationMode"] in {"DynamicOS", "StaticSDFRequired"} and font["pointSize"] == 90 for font in system_fonts["fonts"]))
        pingfang = [font for font in system_fonts["fonts"] if font["familyName"] == "PingFang SC"]
        self.assertEqual(len(pingfang), 1)
        self.assertEqual(pingfang[0]["populationMode"], "StaticSDFRequired")
        self.assertEqual(pingfang[0]["targetPostScriptName"], "PingFangSC-Regular")
        self.assertEqual(pingfang[0]["matchingPhysicalFaces"], [])
        self.assertEqual(pingfang[0]["generationMode"], "CoreTextRasterizedStaticSDF")
        self.assertTrue(all(font["populationMode"] == "DynamicOS" for font in system_fonts["fonts"] if font["familyName"] in {"Arial", "Hiragino Sans"}))

        font_by_id = {font["assetId"]: font for font in system_fonts["fonts"]}
        label_ids = {label["sourceLabelId"] for label in record["labelBindings"]}
        self.assertEqual(len(label_ids), 118)
        self.assertTrue(all(label["sourceSystemFont"] is True and label["sourceSerializedFontUuid"] is None
                            for label in record["labelBindings"]))
        self.assertTrue(all(label["nativeFontAssetId"] in font_by_id for label in record["labelBindings"]))
        self.assertTrue(all(font["requiredUnicode"] == sorted(set(font["requiredUnicode"])) for font in system_fonts["fonts"]))

        primary_ids = {label["nativeFontAssetId"] for label in record["labelBindings"]}
        self.assertGreater(len(primary_ids), 1, "different CoreText fallback combinations must not share one global chain")
        for label in record["labelBindings"]:
            primary = font_by_id[label["nativeFontAssetId"]]
            self.assertEqual(primary["role"], "primary")
            self.assertEqual(primary["fallbackAssetIds"], label["nativeFallbackAssetIds"])
            self.assertEqual(primary["assetPath"], label["nativeFontAssetPath"])
            self.assertTrue(all(font_by_id[fallback_id]["role"] == "fallback"
                                for fallback_id in label["nativeFallbackAssetIds"]))

        excluded = {
            c.get("sourceId") for c in self.ir["components"]
            if c.get("type") == "cc.Label" and c.get("font") is not None
        }
        self.assertTrue(label_ids.isdisjoint(excluded))

    def test_text_or_family_drift_fails_closed(self):
        labels = [c for c in self.ir["components"] if c.get("type") == "cc.Label" and c.get("systemFont") is True and c.get("font") is None]
        changed_text = json.loads(json.dumps(self.ir))
        changed_text_label = next(c for c in changed_text["components"] if c.get("sourceId") == labels[0]["sourceId"])
        changed_text_label["text"] += "!"
        text_result = self.prepare(changed_text)
        self.assertEqual(text_result.status, "needs_action")
        self.assertIn("text drifted", text_result.record["reason"])

        changed_family = json.loads(json.dumps(self.ir))
        changed_family_label = next(c for c in changed_family["components"] if c.get("sourceId") == labels[0]["sourceId"])
        changed_family_label["fontFamily"] = {"name": "Arial"}
        family_result = self.prepare(changed_family)
        self.assertEqual(family_result.status, "needs_action")
        self.assertIn("invalid source/default font family", family_result.record["reason"])

    def test_receipt_must_be_current_resolved_and_source_os_unproven(self):
        hash_result = self.prepare(resolution_sha="0" * 64)
        self.assertEqual(hash_result.status, "needs_action")
        self.assertIn("SHA-256 drifted", hash_result.record["reason"])

        unproven = json.loads(self.resolution_raw.decode("utf-8"))
        unproven["sourceDefaultEvidence"]["sourceOSIdentityVerified"] = True
        altered = (json.dumps(unproven, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        with tempfile.TemporaryDirectory(prefix="system-font-receipt-", dir=PRIVATE / "font-binding") as temp:
            path = Path(temp) / "unproven.json"
            path.write_bytes(altered)
            result = self.prepare(resolution_path=path, resolution_sha=hashlib.sha256(altered).hexdigest())
        self.assertEqual(result.status, "needs_action")
        self.assertIn("unverified source OS", result.record["reason"])

    def test_uncovered_glyph_is_not_silently_added(self):
        altered = json.loads(self.resolution_raw.decode("utf-8"))
        label = next(row for row in altered["labels"] if row["unicodeScalars"])
        scalar = next(row for row in label["unicodeScalars"] if row["requiredForVisualText"])
        scalar["glyphCovered"] = False
        raw = (json.dumps(altered, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        with tempfile.TemporaryDirectory(prefix="system-font-receipt-", dir=PRIVATE / "font-binding") as temp:
            path = Path(temp) / "missing-glyph.json"
            path.write_bytes(raw)
            result = self.prepare(resolution_path=path, resolution_sha=hashlib.sha256(raw).hexdigest())
        self.assertEqual(result.status, "needs_action")
        self.assertIn("uncovered required glyph", result.record["reason"])

    def test_unproven_or_drifted_face_style_is_not_emitted(self):
        altered = json.loads(self.resolution_raw.decode("utf-8"))
        altered["labels"][0]["resolvedPrimaryStyleName"] = ""
        raw = (json.dumps(altered, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        with tempfile.TemporaryDirectory(prefix="system-font-receipt-", dir=PRIVATE / "font-binding") as temp:
            path = Path(temp) / "unknown-style.json"
            path.write_bytes(raw)
            result = self.prepare(resolution_path=path, resolution_sha=hashlib.sha256(raw).hexdigest())
        self.assertEqual(result.status, "needs_action")
        self.assertIn("lacks primary family/style", result.record["reason"])

    def test_missing_physical_face_evidence_cannot_fall_through_to_dynamic_os(self):
        altered = json.loads(self.resolution_raw.decode("utf-8"))
        altered["coreTextToPhysicalFaceEvidence"] = []
        raw = (json.dumps(altered, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        with tempfile.TemporaryDirectory(prefix="system-font-receipt-", dir=PRIVATE / "font-binding") as temp:
            path = Path(temp) / "missing-physical-face-evidence.json"
            path.write_bytes(raw)
            result = self.prepare(resolution_path=path, resolution_sha=hashlib.sha256(raw).hexdigest())
        self.assertEqual(result.status, "needs_action")
        self.assertIn("physical face identity is missing", result.record["reason"])

    def test_coretext_static_sdf_plan_uses_only_frozen_unicode_and_no_font_file(self):
        result = prepare_static_coretext_sdf_plan(
            self.ir, self.ir_sha, RESOLUTION_PATH, self.resolution_sha,
        )
        self.assertEqual(result.status, "prepared", result.record.get("reason"))
        record = result.record
        self.assertEqual(record["schema"], "monkey-unity-coretext-static-sdf-plan/1")
        self.assertFalse(record["fontFilesCopiedOrExported"])
        self.assertFalse(record["visualEquivalent"])
        self.assertEqual(record["resolutionReceiptSha256"], self.resolution_sha)
        self.assertEqual(len(record["systemFonts"]), 1)
        face = record["systemFonts"][0]
        self.assertEqual(face["targetFamily"], "PingFang SC")
        self.assertEqual(face["targetPostScriptName"], "PingFangSC-Regular")
        self.assertEqual(face["matchingPhysicalFaces"], [])
        self.assertEqual(face["generationMode"], "CoreTextRasterizedStaticSDF")
        self.assertGreater(len(face["requiredGlyphs"]), 200)
        self.assertTrue(face["atlasContract"]["fontFileLicenseReviewRequiredBeforeDistribution"])
        self.assertEqual(face["atlasContract"]["allowedCodepoints"], face["requiredUnicode"])
        self.assertTrue(all(row["scope"].startswith("literal source text") for row in record["labelFallbackOverrides"]))
        prepared = self.prepare().record["systemFonts"]["fonts"]
        native_static = next(font for font in prepared if font["populationMode"] == "StaticSDFRequired")
        self.assertEqual(native_static["assetId"], face["assetId"])
        self.assertEqual(native_static["assetPath"], face["assetPath"])

    def test_static_sdf_inputs_stage_as_portable_hash_pinned_relative_files(self):
        binding = self.prepare().record
        generation_path = PRIVATE / "font-binding/coretext-static-sdf-generation-receipt-pure03.json"
        generation_sha = hashlib.sha256(generation_path.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix="static-sdf-stage-", dir=PRIVATE / "font-binding") as temp:
            first = prepare_static_inputs(generation_path, generation_sha, binding, temp)
            self.assertEqual(first.status, "staged", first.record.get("reason"))
            self.assertEqual(first.record["sourceGenerationReceiptSha256"], generation_sha)
            self.assertFalse(first.record["fontFileCopiedOrExported"])
            self.assertFalse(first.record["fontFileIncluded"])
            self.assertEqual(len(first.record["copies"]), 3)
            relative = first.record["portableReceiptRelativePath"]
            self.assertNotIn("..", Path(relative).parts)
            staged_receipt = Path(temp) / relative
            portable = json.loads(staged_receipt.read_text(encoding="utf-8"))
            self.assertEqual(portable["schema"], "monkey-coretext-static-sdf-portable-generation-receipt/1")
            self.assertEqual(portable["status"], "portable_staged")
            self.assertEqual(portable["sourceGenerationReceiptSha256"], generation_sha)
            self.assertEqual(portable["atlasPath"], "glyph-atlas.png")
            self.assertEqual(portable["metricsPath"], "glyph-metrics.json")
            self.assertFalse(Path(portable["atlasPath"]).is_absolute())
            self.assertFalse(Path(portable["metricsPath"]).is_absolute())
            self.assertEqual(hashlib.sha256(staged_receipt.read_bytes()).hexdigest(), first.record["portableReceiptSha256"])
            second = prepare_static_inputs(generation_path, generation_sha, binding, temp)
            self.assertEqual(second.status, "staged")
            self.assertEqual(second.record["portableReceiptSha256"], first.record["portableReceiptSha256"])

    def test_static_sdf_staging_rejects_generation_receipt_drift_and_conflicting_existing_files(self):
        binding = self.prepare().record
        generation_path = PRIVATE / "font-binding/coretext-static-sdf-generation-receipt-pure03.json"
        generation_sha = hashlib.sha256(generation_path.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix="static-sdf-stage-", dir=PRIVATE / "font-binding") as temp:
            drifted = prepare_static_inputs(generation_path, "0" * 64, binding, temp)
            self.assertEqual(drifted.status, "needs_action")
            self.assertIn("drifted", drifted.record["reason"])
            staged = prepare_static_inputs(generation_path, generation_sha, binding, temp)
            atlas = Path(temp) / next(row["relativePath"] for row in staged.record["copies"] if row["relativePath"].endswith("glyph-atlas.png"))
            atlas.write_bytes(atlas.read_bytes() + b"drift")
            conflict = prepare_static_inputs(generation_path, generation_sha, binding, temp)
            self.assertEqual(conflict.status, "needs_action")
            self.assertIn("refusing to overwrite", conflict.record["reason"])


if __name__ == "__main__":
    unittest.main()
