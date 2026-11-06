import unittest

from monkey.prefab_static_richtext import convert_static_richtext


class StaticRichTextTests(unittest.TestCase):
    @staticmethod
    def binding_for(text):
        return {
            "nativeFontAssetId": "font-static-test",
            "nativeFallbackAssetIds": ["font-fallback-test"],
            "coveredUnicode": sorted({ord(ch) for ch in text if ch not in "\r\n\t"}),
            "coverageEvidence": {
                "metricsPath": "fixture/glyph-metrics.json", "metricsSha256": "a" * 64,
                "receiptPath": "fixture/generation-receipt.json", "receiptSha256": "b" * 64,
            },
        }

    def test_static_nested_markup_and_layout_fields_are_projected(self):
        source = {
            "__type__": "cc.RichText",
            "_N$string": "普通<color=#f00><b>红字</b></color><br/><size=24><i>小字</i></size>",
            "_N$fontSize": 30,
            "_N$lineHeight": 42,
            "_N$maxWidth": 600,
            "_N$horizontalAlign": 1,
            "_N$verticalAlign": 1,
        }
        result = convert_static_richtext(source, source_id="fixture#1", node_id="fixture#0",
                                         font_binding=self.binding_for(source["_N$string"]))
        self.assertTrue(result["convertible"])
        self.assertEqual(result["plainText"], "普通红字\n小字")
        self.assertEqual(result["unityMarkup"], "普通<color=#ff0000><b>红字</b></color>\n<size=24><i>小字</i></size>")
        self.assertEqual(result["fontSize"], 30)
        self.assertEqual(result["lineHeight"], 42)
        self.assertEqual(result["maxWidth"], 600)
        self.assertEqual(result["horizontalAlign"], 1)
        self.assertEqual(result["verticalAlign"], 1)
        self.assertTrue(result["wrap"])
        self.assertFalse(result["dynamicScriptExecuted"])
        self.assertEqual(result["fontBinding"]["nativeFontAssetId"], "font-static-test")

    def test_cocos_empty_close_tag_is_accepted_for_nested_static_tags(self):
        result = convert_static_richtext({
            "__type__": "cc.RichText", "_N$string": "<size=50>Creator</>",
        }, source_id="fixture#2", font_binding=self.binding_for("Creator"))
        self.assertTrue(result["convertible"], result["gaps"])
        self.assertEqual(result["unityMarkup"], "<size=50>Creator</size>")

    def test_creator_24_color_short_close_is_normalized(self):
        result = convert_static_richtext({
            "__type__": "cc.RichText",
            "_N$string": "<color=#cb945a>建造</c><color=#de551f>5</color><color=#cb945a>次</c>",
        }, source_id="fixture#creator-color-short-close", font_binding=self.binding_for("建造5次"))
        self.assertTrue(result["contentConvertible"], result["gaps"])
        self.assertTrue(result["renderReady"], result["gaps"])
        self.assertEqual(result["plainText"], "建造5次")
        self.assertEqual(result["creatorMarkup"], "<color=#cb945a>建造</color><color=#de551f>5</color><color=#cb945a>次</color>")

    def test_img_event_outline_and_unknown_tags_fail_closed(self):
        for markup in (
            "before<img src='icon' />after",
            "<on click='handler'>click</on>",
            "<outline color=red width=4>outlined</outline>",
            "<blink>unknown</blink>",
        ):
            with self.subTest(markup=markup):
                result = convert_static_richtext({"__type__": "cc.RichText", "_N$string": markup}, source_id="fixture#3")
                self.assertFalse(result["convertible"])
                self.assertTrue(any("unsupported" in gap for gap in result["gaps"]), result["gaps"])

    def test_missing_or_incomplete_static_font_evidence_blocks_rendering(self):
        source = {"__type__": "cc.RichText", "_N$string": "今天"}
        no_binding = convert_static_richtext(source, source_id="fixture#font")
        self.assertTrue(no_binding["contentConvertible"])
        self.assertFalse(no_binding["renderReady"])
        self.assertTrue(any("source Arial is provenance only" in gap for gap in no_binding["gaps"]))
        incomplete = convert_static_richtext(source, source_id="fixture#font", font_binding={
            "nativeFontAssetId": "font", "nativeFallbackAssetIds": [], "coveredUnicode": [ord("今")],
            "coverageEvidence": {
                "metricsPath": "fixture/glyph-metrics.json", "metricsSha256": "a" * 64,
                "receiptPath": "fixture/generation-receipt.json", "receiptSha256": "b" * 64,
            },
        })
        self.assertFalse(incomplete["renderReady"])
        self.assertTrue(any("U+5929" in gap for gap in incomplete["gaps"]))

    def test_static_preview_text_override_requires_frozen_state_provenance(self):
        source = {"__type__": "cc.RichText", "_N$string": "serialized placeholder"}
        result = convert_static_richtext(source, source_id="fixture#state", text_override={
            "text": "source-backed preview", "sourceId": "state#label", "sourceSha256": "a" * 64,
            "field": "label.text", "evidenceType": "frozen-static-preview-state",
            "componentProperties": {"fontSize": 40, "lineHeight": 50},
        })
        self.assertEqual(result["serializedSourceText"], "serialized placeholder")
        self.assertEqual(result["text"], "source-backed preview")
        self.assertEqual(result["textEvidence"]["sourceId"], "state#label")
        self.assertEqual(result["fontSize"], 40)
        self.assertEqual(result["lineHeight"], 50)
        rejected = convert_static_richtext(source, source_id="fixture#state", text_override={"text": "unattributed"})
        self.assertFalse(rejected["renderReady"])
        self.assertTrue(any("provenance" in gap for gap in rejected["gaps"]))

    def test_mismatched_tags_and_invalid_layout_fail_closed(self):
        result = convert_static_richtext({
            "__type__": "cc.RichText", "_N$string": "<b>no</i>",
            "_N$fontSize": 0, "_N$maxWidth": -1, "_N$horizontalAlign": 3,
        }, source_id="fixture#4")
        self.assertFalse(result["convertible"])
        self.assertTrue(any("nesting mismatch" in gap for gap in result["gaps"]))
        self.assertTrue(any("fontSize" in gap for gap in result["gaps"]))
        self.assertTrue(any("maxWidth" in gap for gap in result["gaps"]))
        self.assertTrue(any("horizontalAlign" in gap for gap in result["gaps"]))


if __name__ == "__main__":
    unittest.main()
