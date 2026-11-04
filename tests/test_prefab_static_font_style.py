"""Neutral contracts for static SDF fake-bold and outline normalization.

These tests deliberately use only repository source and a small mathematical
oracle. Installed Unity/TMP files and game-specific IR fixtures belong in the
private evidence copy, not in the public package test suite.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
UNITY_SYSTEM_FONTS = ROOT / "src/monkey/targets/UnitySystemFonts.cs"
UNITY_IMPORTER = ROOT / "src/monkey/targets/UnityImporter.cs"


def normalized_style_weight(style_weight: float, sdf_spread: float) -> float:
    """Preserve TMP fake-bold's reference dilation across SDF spreads."""
    reference_dilate_range = 10.0 - 1.0
    target_gradient_scale = 2.0 * sdf_spread + 1.0
    target_dilate_range = target_gradient_scale - 1.0
    if sdf_spread <= 0 or target_dilate_range <= 0:
        raise ValueError("sdf_spread must be positive")
    return style_weight * reference_dilate_range / target_dilate_range


def style_padding(style_weight: float, gradient_scale: float) -> float:
    """TMP's bounded fake-bold padding with the no-outline ratio A."""
    ratio_a = (gradient_scale - 1.0) / gradient_scale
    return style_weight * 0.25 * gradient_scale * ratio_a


def normalized_outline_width(source_width: float, face_point_size: float,
                             label_font_size: float, sdf_spread: float) -> float:
    gradient_scale = 2.0 * sdf_spread + 1.0
    return source_width * face_point_size / max(label_font_size, 1.0) / max(gradient_scale - 1.0, 1.0)


class StaticFontStyleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font_helper = UNITY_SYSTEM_FONTS.read_text(encoding="utf-8")
        cls.importer = UNITY_IMPORTER.read_text(encoding="utf-8")

    def test_fake_bold_normalization_preserves_reference_padding_across_spreads(self):
        reference = style_padding(0.75, 10.0)
        self.assertAlmostEqual(reference, 1.6875)
        for spread in (1, 8, 16, 32, 64):
            gradient = 2.0 * spread + 1.0
            adjusted = normalized_style_weight(0.75, spread)
            self.assertAlmostEqual(style_padding(adjusted, gradient), reference)
        self.assertAlmostEqual(normalized_style_weight(0.75, 32), 0.10546875)
        with self.assertRaises(ValueError):
            normalized_style_weight(0.75, 0)

    def test_font_asset_helper_uses_spread_normalization_and_persisted_readback(self):
        self.assertIn("float ScaleTmpStyleWeight(float styleWeight, float sdfSpread)", self.font_helper)
        self.assertIn("float gradientScale = 2f * sdfSpread + 1f", self.font_helper)
        self.assertIn("TmpDefaultSdfGradientScale - TmpSdfRatioClamp", self.font_helper)
        self.assertIn("gradientScale - TmpSdfRatioClamp", self.font_helper)
        self.assertIn("asset.normalStyle = ScaleTmpStyleWeight(asset.normalStyle, metrics.sdfSpread)", self.font_helper)
        self.assertIn("asset.boldStyle = ScaleTmpStyleWeight(asset.boldStyle, metrics.sdfSpread)", self.font_helper)
        self.assertIn('material.SetFloat("_WeightNormal", asset.normalStyle)', self.font_helper)
        self.assertIn('material.SetFloat("_WeightBold", asset.boldStyle)', self.font_helper)
        self.assertIn("VerifyStaticSdfStyle(saved, item.sdfSpread", self.font_helper)

    def test_label_bold_and_outline_remain_separate_contracts(self):
        self.assertIn("label.fontStyle = SourceFontStyles(spec)", self.importer)
        self.assertIn("spec.bold?TMPro.FontStyles.Bold:TMPro.FontStyles.Normal", self.importer)
        self.assertRegex(self.importer,
            r"spec\.width\*outlineFont\.faceInfo\.pointSize/Mathf\.Max\(label\.fontSize,1\)/Mathf\.Max\(gradient-1,1\)")
        source_width, face_point_size, label_font_size = 1.0, 90.0, 26.0
        for spread in (8, 32):
            width = normalized_outline_width(source_width, face_point_size, label_font_size, spread)
            gradient = 2.0 * spread + 1.0
            reconstructed = width * (gradient - 1.0) * label_font_size / face_point_size
            self.assertAlmostEqual(reconstructed, source_width)
            normalized_bold = normalized_style_weight(0.75, spread)
            outline_dilate = 2 * width
            self.assertLess(normalized_bold / 4.0 + outline_dilate, 1.0)
            self.assertAlmostEqual(style_padding(normalized_bold, gradient), 1.6875)

    def test_helper_has_finite_range_checks_and_does_not_select_a_game_fixture(self):
        self.assertIn("float.IsNaN(styleWeight) || float.IsInfinity(styleWeight)", self.font_helper)
        self.assertIn("float.IsNaN(sdfSpread) || float.IsInfinity(sdfSpread) || sdfSpread <= 0f", self.font_helper)
        self.assertIn("SYSTEM_FONT_STATIC_SDF_STYLE_READBACK_MISMATCH", self.font_helper)
        self.assertNotRegex(self.font_helper, r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


if __name__ == "__main__":
    unittest.main()
