import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from grea.recovery.native_font_completion import (
    NativeFontCompletionError, _append_glyphs, _merge_font_plan, _unicode_rows,
    complete_native_font_from_corpus,
)


class NativeFontCompletionTests(unittest.TestCase):
    def test_corpus_unicode_is_unique_and_scalar_bounded(self):
        rows = _unicode_rows(["AB合", "合新"])
        self.assertEqual([65, 66, 21512, 26032], list(rows))
        with self.assertRaises(NativeFontCompletionError):
            _unicode_rows(["\ud800"])

    def test_plan_union_keeps_exact_static_face_and_prior_glyphs(self):
        face = {
            "assetId": "coretext-static-sdf-face", "assetPath": "Assets/Fonts/face.asset",
            "targetFamily": "PingFang SC", "targetStyleName": "Regular",
            "targetPostScriptName": "PingFangSC-Regular", "targetVariationAxes": {"wght": 400},
            "targetSystemFontFileUrl": "/System/PingFang.ttc", "targetSystemFontFileSha256": "f" * 64,
            "requiredGlyphs": [{"unicode": 65, "codepoint": "U+0041", "character": "A"}],
            "sourceLabelIds": ["source-label"], "atlasContract": {"allowedCodepoints": [65]},
        }
        result = _merge_font_plan({"schema": "monkey-unity-coretext-static-sdf-plan/1", "status": "prepared",
                                   "resolutionReceiptSha256": "r" * 64, "systemFonts": [face]},
                                  {**face, "resolutionReceiptSha256": "r" * 64},
                                  [{"unicode": 66, "codepoint": "U+0042", "character": "B"}],
                                  "c" * 64, "s" * 64, "q" * 64)
        updated = result["systemFonts"][0]
        self.assertEqual("coretext-static-sdf-face", updated["assetId"])
        self.assertEqual("f" * 64, updated["targetSystemFontFileSha256"])
        self.assertEqual([65, 66], updated["requiredUnicode"])
        self.assertEqual([65, 66], updated["atlasContract"]["allowedCodepoints"])

    def test_plan_rejects_changed_source_face(self):
        face = {"assetId": "face", "assetPath": "face.asset", "targetFamily": "PingFang SC",
                "targetStyleName": "Regular", "targetPostScriptName": "PingFangSC-Regular",
                "targetVariationAxes": {"wght": 400}, "targetSystemFontFileUrl": "/System/PingFang.ttc",
                "targetSystemFontFileSha256": "f" * 64, "requiredGlyphs": [], "sourceLabelIds": []}
        changed = {**face, "targetSystemFontFileSha256": "e" * 64}
        with self.assertRaises(NativeFontCompletionError):
            _merge_font_plan({"schema": "monkey-unity-coretext-static-sdf-plan/1", "status": "prepared",
                              "systemFonts": [face]}, changed, [], "c" * 64, "s" * 64, "r" * 64)

    def test_append_preserves_old_tile_and_metrics_and_adds_only_new_codepoint(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            base_atlas, fresh_atlas = root / "base.png", root / "fresh.png"
            base = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
            base.putpixel((1, 1), (1, 2, 3, 255))
            base.save(base_atlas)
            fresh = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
            fresh.putpixel((1, 1), (1, 2, 3, 255))
            fresh.putpixel((5, 1), (9, 8, 7, 255))
            fresh.save(fresh_atlas)
            old_row = {"unicode": 65, "codepoint": "U+0041", "character": "A",
                       "metrics": {"advance": 4}, "rect": {"x": 1, "y": 1, "width": 1, "height": 1}}
            new_row = {"unicode": 66, "codepoint": "U+0042", "character": "B",
                       "metrics": {"advance": 5}, "rect": {"x": 5, "y": 1, "width": 1, "height": 1}}
            base_metrics_path = root / "base-metrics.json"
            base_metrics_path.write_text(json.dumps({"glyphs": [old_row]}), encoding="utf-8")
            metrics = {"atlasWidth": 16, "atlasHeight": 16, "glyphs": [old_row]}
            metrics["_sourcePath"] = str(base_metrics_path)
            fresh_metrics = {"atlasWidth": 16, "atlasHeight": 16, "glyphs": [old_row, new_row]}
            out_path = root / "out.png"
            result, counts = _append_glyphs(base_atlas, metrics, fresh_atlas, fresh_metrics, out_path, {66})
            self.assertEqual({"preservedGlyphCount": 1, "addedGlyphCount": 1}, counts)
            self.assertEqual([65, 66], [row["unicode"] for row in result["glyphs"]])
            final = Image.open(out_path).convert("RGBA")
            self.assertEqual((1, 2, 3, 255), final.getpixel((1, 1)))
            self.assertEqual((9, 8, 7, 255), final.getpixel((0, 3)))

    def test_append_rejects_changed_existing_metrics(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
            image.save(root / "base.png")
            image.save(root / "fresh.png")
            metrics_path = root / "metrics.json"
            metrics_path.write_text("{}", encoding="utf-8")
            old = {"unicode": 65, "character": "A", "metrics": {"advance": 4},
                   "rect": {"x": 0, "y": 0, "width": 1, "height": 1}}
            changed = {"unicode": 65, "character": "A", "metrics": {"advance": 5},
                       "rect": {"x": 0, "y": 0, "width": 1, "height": 1}}
            base_metrics = {"glyphs": [old], "_sourcePath": str(metrics_path)}
            fresh_metrics = {"atlasWidth": 8, "atlasHeight": 8, "glyphs": [changed]}
            with self.assertRaises(NativeFontCompletionError):
                _append_glyphs(root / "base.png", base_metrics, root / "fresh.png", fresh_metrics,
                               root / "out.png", set())

    def test_hash_mismatch_fails_before_output_directory_creation(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            corpus = root / "corpus.json"
            corpus.write_text(json.dumps({"schemaVersion": 1, "sourceSha256": "s" * 64,
                                          "strings": ["合成"]}), encoding="utf-8")
            out = root / "candidate"
            with self.assertRaises(NativeFontCompletionError):
                complete_native_font_from_corpus(
                    corpus, "0" * 64, root / "binding.json", "b" * 64,
                    root / "receipt.json", "r" * 64, root / "plan.json", "p" * 64,
                    root / "generator.swift", out, static_font_asset_id="face",
                )
            self.assertFalse(out.exists())
if __name__ == "__main__":
    unittest.main()
