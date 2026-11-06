"""Neutral contracts for inset glyph rectangles in padded static SDF atlases.

Game-specific atlas/metrics and installed TMP source are retained in the
private evidence module; the public test uses synthetic geometry and repository
source only.
"""
import math
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION = ROOT / "src/monkey/targets/UnitySystemFonts.cs"


def content_bounds(rect: dict, glyph_padding: int, atlas_height: int) -> tuple[int, int, int, int]:
    padded_x, top_y, padded_width, padded_height = (rect[k] for k in ("x", "y", "width", "height"))
    if glyph_padding < 0 or padded_width <= 2 * glyph_padding or padded_height <= 2 * glyph_padding:
        raise ValueError("padded glyph cell has no positive content area")
    unity_padded_y = atlas_height - top_y - padded_height
    return (padded_x + glyph_padding, unity_padded_y + glyph_padding,
            padded_width - 2 * glyph_padding, padded_height - 2 * glyph_padding)


class StaticFontRenderContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = IMPLEMENTATION.read_text(encoding="utf-8")

    def test_import_insets_allocated_rect_but_preserves_content_metrics(self):
        self.assertIn("glyph.rect.width <= 2 * metrics.glyphPadding", self.source)
        self.assertIn("glyph.rect.height <= 2 * metrics.glyphPadding", self.source)
        self.assertRegex(self.source,
            re.compile(r"new GlyphRect\(row\.rect\.x \+ pad, atlasY \+ pad,\s*"
                       r"row\.rect\.width - 2 \* pad, row\.rect\.height - 2 \* pad\)"))
        self.assertRegex(self.source,
            re.compile(r"new GlyphMetrics\(row\.metrics\.width, row\.metrics\.height,\s*"
                       r"row\.metrics\.bearingX, row\.metrics\.bearingY,\s*row\.metrics\.advance\)"))
        self.assertIn('material.SetFloat("_GradientScale", 2f * metrics.sdfSpread + 1f)', self.source)
        self.assertIn('SetIntProperty(serialized, "m_AtlasPadding", metrics.glyphPadding)', self.source)

    def test_synthetic_padded_cells_recover_content_bounds_and_preserve_identity(self):
        cases = [
            ({"x": 7, "y": 11, "width": 28, "height": 20}, 8, 96, 12.0, 4.0),
            ({"x": 19, "y": 5, "width": 44, "height": 36}, 16, 128, 11.2, 3.7),
            ({"x": 3, "y": 23, "width": 72, "height": 54}, 24, 256, 23.4, 5.8),
        ]
        for rect, pad, atlas_height, metric_width, metric_height in cases:
            original = dict(rect)
            x, y, width, height = content_bounds(rect, pad, atlas_height)
            padded_y = atlas_height - rect["y"] - rect["height"]
            self.assertEqual((x - pad, y - pad), (rect["x"], padded_y))
            self.assertEqual(width, rect["width"] - 2 * pad)
            self.assertEqual(height, rect["height"] - 2 * pad)
            self.assertEqual(width, math.ceil(metric_width))
            self.assertEqual(height, math.ceil(metric_height))
            self.assertEqual(rect, original)

    def test_invalid_padding_cannot_create_an_empty_or_inverted_glyph(self):
        for rect, padding in [({"x": 0, "y": 0, "width": 16, "height": 24}, 8),
                              ({"x": 0, "y": 0, "width": 32, "height": 10}, 8),
                              ({"x": 0, "y": 0, "width": 20, "height": 20}, -1)]:
            with self.assertRaises(ValueError):
                content_bounds(rect, padding, 64)


if __name__ == "__main__":
    unittest.main()
