import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from grea.recovery.prefab_materials import inspect_ui_color, plan_ui_color
from .test_prefab_materials import _fixture, _fixture_profile

from grea.recovery.prefab_static_presentation import prepare


def source_asset(source_id, key, kind, root, bundle="gameAsset"):
    return {"sourceId": source_id, "key": key, "bundle": bundle, "kind": kind,
            "document": {"instances": [root], "root": 0}}


class StaticPresentationTests(unittest.TestCase):
    def base(self):
        return {"sourceManifestSha256": "a" * 64, "textures": [], "assets": [],
                "bitmapFonts": [], "components": []}

    def test_sprite_material_mapping_modes_and_untrimmed_sliced(self):
        plan = self.base()
        plan["textures"] = [
            {"id": "frame", "path": "Assets/frame_trimmed.png", "size": [60, 60],
             "originalSize": [64, 64], "offset": [2, 2], "border": [4, 4, 4, 4]},
            {"id": "frame@original", "path": "Assets/frame.png", "size": [64, 64],
             "originalSize": [64, 64], "offset": [0, 0], "border": [0, 0, 0, 0]}]
        # Generate the same source-bound material spec consumed by the static pipeline.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            manifest_path = _fixture(root)
            profile = _fixture_profile(manifest_path)
            profile.start()
            self.addCleanup(profile.stop)
            manifest = json.loads(manifest_path.read_bytes())
            source_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            source = inspect_ui_color(manifest_path)["source"]
            material = source["materialSourceId"]
            components = [{"type":"cc.Sprite","materials":[material],"sourceId":row["componentSourceId"],
                           "spriteFrame":"gameAsset:"+row["spriteFrameUuid"]} for row in source["prefabOccurrences"]]
            ir_path = root/"ir.json"
            ir_path.write_text(json.dumps({"sourceManifestSha256":source_hash,"components":components}))
            binding = plan_ui_color(manifest_path,ir_path,"UiColorModule",source_hash,
                                    hashlib.sha256(ir_path.read_bytes()).hexdigest())
            plan["materialBinding"] = binding
            expected = patch("grea.recovery.prefab_static_presentation._UI_COLOR_PROGRAM_SHA256",
                             binding["spec"]["programCanonicalSha256"])
            expected.start()
            self.addCleanup(expected.stop)
        plan["components"] = [{"sourceId": components[0]["sourceId"], "node": "n", "type": "cc.Sprite",
            "convertible": False, "enabled": True, "spriteFrame": "frame", "mode": 1,
            "trim": False, "materials": [material]}]
        row = prepare(plan, manifest)["components"][0]
        self.assertEqual("ready", row["status"])
        self.assertEqual("Sliced", row["nativeFields"]["type"])
        self.assertEqual([4, 4, 4, 4], row["nativeFields"]["border"])
        self.assertEqual("Assets/frame.png", row["evidence"]["texturePath"])
        self.assertEqual([4, 4, 4, 4], row["nativeFields"]["textureImportBorderOverride"])
        self.assertTrue(row["evidence"]["material"]["requiresMaterialBindingAppend"])

        plan["textures"][1]["offset"] = [3, 0]
        row = prepare(plan, manifest)["components"][0]
        self.assertIn("sliced_untrimmed_geometry_not_identity", row["blockers"])

    def test_unrecognized_effect_is_blocked_not_treated_as_default(self):
        plan = self.base()
        plan["textures"] = [{"id": "frame", "path": "Assets/frame.png", "size": [32, 32],
                            "originalSize": [32, 32], "offset": [0, 0], "border": [0, 0, 0, 0]}]
        plan["components"] = [{"sourceId": "sprite", "node": "n", "type": "cc.Sprite",
            "convertible": False, "enabled": True, "spriteFrame": "frame", "mode": 2,
            "trim": True, "materials": ["gameAsset:custom"]}]
        custom = source_asset("gameAsset:custom", "custom", "cc.Material", {
            "__type__": "cc.Material", "_name": "shader-2d-bgFlow",
            "_effectAsset": {"__uuid__": "effect"}})
        effect = source_asset("gameAsset:effect", "effect", "cc.EffectAsset", {
            "__type__": "cc.EffectAsset", "_name": "shader-2d-bgFlow"})
        row = prepare(plan, {"assets": [custom, effect]})["components"][0]
        self.assertEqual("blocked", row["status"])
        self.assertIn("source_effect_not_mapped:gameAsset:custom", row["blockers"])

    def test_null_font_uses_source_ttf_assembler_arial_only_with_complete_fallback(self):
        plan = self.base()
        plan["systemFontBinding"] = {
            "runtimePlatformConstraint": "macOS Player only",
            "labelBindings": [{"sourceFontFamily": "Arial", "resolvedPrimaryFamily": "Arial",
                "nativeFontAssetId": "arial-id", "nativeFontAssetPath": "Assets/Arial.asset",
                "nativeFallbackAssetIds": ["fallback-id"]}],
            "systemFonts": {"fonts": [{"assetId": "fallback-id", "assetPath": "Assets/Fallback.asset",
                "generationMode": "CoreTextRasterizedStaticSDF",
                "requiredGlyphs": [{"character": "免"}, {"character": "费"}]}]}}
        plan["components"] = [{"sourceId": "label", "node": "n", "type": "cc.Label",
            "convertible": False, "enabled": True, "font": None, "systemFont": False,
            "fontFamily": "Arial", "fontFamilyEvidence": "creator-label-default-Arial",
            "fontSize": 24, "lineHeight": 24, "text": "免费"}]
        row = prepare(plan, {"assets": []})["components"][0]
        self.assertEqual("ready", row["status"])
        self.assertEqual("Arial", row["evidence"]["font"]["sourceEffectiveFamily"])
        self.assertEqual("Assets/Arial.asset", row["evidence"]["font"]["nativeFontAssetPath"])

        plan["components"][0]["text"] = "解锁"
        row = prepare(plan, {"assets": []})["components"][0]
        self.assertEqual("blocked", row["status"])
        self.assertIn("creator_arial_fallback_glyphs_missing:解锁", row["blockers"])

    def test_missing_font_and_non_system_flag_does_not_guess_family(self):
        plan = self.base()
        plan["components"] = [{"sourceId": "label", "node": "n", "type": "cc.Label",
            "convertible": False, "enabled": True, "font": None, "systemFont": False,
            "fontFamily": "SomeOtherFamily", "text": "免费"}]
        row = prepare(plan, {"assets": []})["components"][0]
        self.assertEqual("blocked", row["status"])
        self.assertIn("font_identity_missing_and_source_system_font_disabled", row["blockers"])

    def test_outline_reuses_same_node_native_tmp_and_requires_target(self):
        plan = self.base()
        plan["assets"] = [{"id": "font-id", "fontAssetPath": "Assets/font.asset",
                          "fontCoverage": {"unicodeRanges": [[0, 0x10ffff]]}}]
        plan["components"] = [
            {"sourceId": "label", "node": "n", "type": "cc.Label", "convertible": False,
             "font": "font-id", "text": "免费", "fontSize": 24, "enabled": True},
            {"sourceId": "outline", "node": "n", "type": "cc.LabelOutline", "convertible": False,
             "enabled": True, "width": 3, "outlineColor": [12, 24, 36, 255]}]
        rows = {r["sourceType"]: r for r in prepare(plan, {"assets": []})["components"]}
        self.assertEqual("ready", rows["cc.Label"]["status"])
        self.assertEqual("ready", rows["cc.LabelOutline"]["status"])
        self.assertEqual("label", rows["cc.LabelOutline"]["nativeFields"]["targetLabelSourceId"])

        plan["components"][0]["font"] = None
        plan["components"][0]["systemFont"] = False
        rows = prepare(plan, {"assets": []})["components"]
        outline = next(r for r in rows if r["sourceType"] == "cc.LabelOutline")
        self.assertIn("same_node_target_label_has_no_verified_native_font:label", outline["blockers"])


if __name__ == "__main__":
    unittest.main()
