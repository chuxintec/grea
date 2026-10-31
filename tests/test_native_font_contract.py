import unittest

from monkey.native_font_contract import audit_saved_font_coverage


GUID = "0123456789abcdef0123456789abcdef"
HASH = "a" * 64


def font(*, mode="Static", present=(65, 66), internal=False, source_present=False):
    return {
        "assetId": "font-a", "assetPath": "Assets/Fonts/A.asset", "assetGuid": GUID,
        "populationMode": mode, "clearDynamicDataOnBuild": False,
        "savedNativeGlyphState": {
            "atlasPopulationMode": mode, "internalDynamicOS": internal,
            "sourceFontFilePresent": source_present,
            "sourceFontFileGuid": "", "sourceFontFilePath": "systemArial.ttf" if mode == "DynamicOS" else "",
            "lookupPresentUnicode": list(present), "characterTableUnicode": list(present),
        },
    }


def readback(font_row=None, labels=None, os="macOS", constraint=None):
    result = {
        "targetOS": os,
        "targetPlatform": "StandaloneOSX",
        "fonts": [font_row] if font_row else [],
        "labelBindings": labels if labels is not None else [{
            "sourceLabelId": "label-a", "sourceText": "AB", "primaryAssetId": "font-a",
            "fallbackAssetIds": [],
        }],
    }
    if constraint is not None:
        result["runtimePlatformConstraint"] = constraint
    return result


class NativeFontContractTests(unittest.TestCase):
    def test_static_coverage_is_bounded_and_identity_is_pinned(self):
        result = audit_saved_font_coverage(
            readback(font()), [{"path": "Assets/Fonts/A.asset", "sha256": HASH}],
            selected_asset_ids=["font-a"], expected_target_os="macOS",
        )
        self.assertEqual("covered", result["labelBindings"][0]["staticCoverage"]["status"])
        self.assertEqual(HASH, result["fonts"][0]["assetSha256"])
        self.assertEqual(GUID, result["fonts"][0]["assetGuid"])
        self.assertEqual("bounded", result["fonts"][0]["staticCoverage"]["status"])
        self.assertEqual("unknown", audit_saved_font_coverage(
            readback(font()), [{"path": "Assets/Fonts/A.asset", "sha256": HASH}],
            expected_target_os="macOS",
        )["platformStatus"])
        self.assertEqual([], result["consumerActions"])

    def test_static_missing_scalar_requires_font_binding(self):
        result = audit_saved_font_coverage(readback(font(present=(65,))),
                                           [{"path": "Assets/Fonts/A.asset", "sha256": HASH}])
        self.assertEqual("missing", result["labelBindings"][0]["staticCoverage"]["status"])
        self.assertEqual([66], result["labelBindings"][0]["staticCoverage"]["missingUnicode"])
        self.assertIn("fontbinding", result["labelBindings"][0]["needConsumer"])

    def test_dynamic_os_null_source_file_is_platform_face_and_coverage_unknown(self):
        row = font(mode="DynamicOS", present=(65,), internal=True, source_present=False)
        result = audit_saved_font_coverage(readback(row),
                                           [{"path": "Assets/Fonts/A.asset", "sha256": HASH}])
        face = result["fonts"][0]
        self.assertIn("platform system face", face["sourceFontFile"]["meaning"])
        self.assertEqual("unknown", face["staticCoverage"]["status"])
        self.assertEqual("unknown", result["labelBindings"][0]["dynamicCoverage"])
        self.assertIn("explicitdynamictextcheck", result["consumerActions"])
        # Static lookup omissions are not treated as proof that DynamicOS lacks glyphs.
        self.assertEqual("unknown", result["labelBindings"][0]["staticCoverage"]["status"])

    def test_missing_identity_or_coverage_fields_do_not_gain_proofs(self):
        result = audit_saved_font_coverage(
            readback({"assetId": "font-a", "assetPath": "Assets/Fonts/A.asset"}), []
        )
        self.assertIsNone(result["fonts"][0]["assetGuid"])
        self.assertIsNone(result["fonts"][0]["assetSha256"])
        self.assertFalse(result["fonts"][0]["identityComplete"])
        self.assertEqual("unknown", result["fonts"][0]["staticCoverage"]["status"])
        self.assertIn("fontbinding", result["consumerActions"])

    def test_unsupported_os_and_selected_asset_filter_are_explicit(self):
        result = audit_saved_font_coverage(
            readback(font(), os="macOS", constraint="macOS Player target only; native asset creation requires macOS Editor"),
            [{"path": "Assets/Fonts/A.asset", "sha256": HASH}],
            expected_target_os="Windows", selected_asset_ids=["some-other-font"],
        )
        self.assertEqual([], result["fonts"])
        self.assertEqual("unsupported", result["platformStatus"])
        self.assertIn("unsupported_target_os", result["diagnostics"])
        self.assertIn("explicitdynamictextcheck", result["labelBindings"][0]["needConsumer"])

    def test_explicit_consumer_text_is_not_promoted_to_dynamic_coverage(self):
        row = font(mode="DynamicOS", internal=True)
        result = audit_saved_font_coverage(
            readback(row), [{"path": "Assets/Fonts/A.asset", "sha256": HASH}],
            required_text_by_label_id={"label-a": "A新字"},
        )
        self.assertEqual([65, 66, 23383, 26032], result["labelBindings"][0]["requiredUnicode"])
        self.assertEqual("unknown", result["labelBindings"][0]["staticCoverage"]["status"])
        self.assertEqual("A新字", result["labelBindings"][0]["consumerRequiredText"])


if __name__ == "__main__":
    unittest.main()
