import copy
import json

import pytest

from src.monkey.prefab_bitmap_missing_glyphs import (
    BitmapMissingGlyphError,
    POLICY,
    prepare,
    verify_readback,
)


def _inputs():
    source_font = {"sourceId": "font:neutral", "glyphs": [
        {"unicode": ord("A")}, {"unicode": ord("过")}, {"unicode": 32},
    ]}
    plan = {
        "bitmapFonts": [source_font],
        "components": [
            {"sourceId": "label:positive", "node": "node:positive", "type": "cc.Label",
             "bitmapLabel": True, "enabled": True, "font": "font:neutral", "text": "跳过A"},
            {"sourceId": "label:complete", "node": "node:complete", "type": "cc.Label",
             "bitmapLabel": True, "enabled": True, "font": "font:neutral", "text": "A 过"},
            {"sourceId": "label:not-bitmap", "node": "node:other", "type": "cc.Label",
             "bitmapLabel": False, "font": "font:neutral", "text": "跳过"},
        ],
    }
    return plan, {"bitmapFonts": [copy.deepcopy(source_font)]}


def test_prepare_derives_skip_policy_without_changing_source_text_or_complete_labels():
    plan, manifest = _inputs()
    before = copy.deepcopy(plan)
    contract = prepare(plan, manifest)
    assert plan == before
    assert contract["status"] == "source_missing_glyphs_retained_and_skipped"
    assert len(contract["components"]) == 1
    row = contract["components"][0]
    assert row["sourceComponentId"] == "label:positive"
    assert row["sourceText"] == "跳过A"
    assert row["sourceFontId"] == "font:neutral"
    assert row["sourceGlyphUnicode"] == [32, ord("A"), ord("过")]
    assert row["missingGlyphUnicode"] == [ord("跳")]
    assert row["displayText"] == "过A"
    assert row["policy"] == POLICY
    assert row["missingGlyphsAreVisibleTextRecovered"] is False
    assert contract["missingGlyphsAreVisibleTextRecovered"] is False


def test_supplementary_text_uses_source_javascript_utf16_char_at():
    plan, manifest = _inputs()
    plan["components"][0]["text"] = "😀过😀"
    contract = prepare(plan, manifest)
    row = contract["components"][0]
    assert row["missingGlyphUnicode"] == [0xD83D,0xDE00]
    assert row["displayText"] == "过"


def test_conflicting_font_glyph_evidence_is_rejected():
    plan, manifest = _inputs()
    manifest["bitmapFonts"][0]["glyphs"].append({"unicode": ord("跳")})
    with pytest.raises(BitmapMissingGlyphError, match="source_disagreement"):
        prepare(plan, manifest)


def test_unresolved_source_font_does_not_fallback_or_fabricate_glyph_coverage():
    plan, manifest = _inputs()
    plan["components"][0]["font"] = "font:missing"
    with pytest.raises(BitmapMissingGlyphError, match="source_font_unresolved"):
        prepare(plan, manifest)


def test_source_manifest_cc_bitmap_font_definition_supplies_glyphset_when_creator_plan_has_only_asset_refs():
    source_id = "font:manifest-backed"
    plan = {
        "bitmapFonts": [],
        "assets": [{"sourceId": source_id, "kind": "bitmap", "glyphCount": 2}],
        "components": [{"sourceId": "label:manifest-backed", "node": "node:manifest-backed",
            "type": "cc.Label", "bitmapLabel": True, "enabled": True,
            "font": source_id, "text": "跳A"}],
    }
    manifest = {"assets": [{"sourceId": source_id, "kind": "cc.BitmapFont", "document": {
        "instances": [{"__type__": "cc.BitmapFont", "_fntConfig": {
            "fontDefDictionary": {"10": {}, "65": {}, str(ord("过")): {}},
        }}],
    }}]}
    contract = prepare(plan, manifest)
    assert len(contract["components"]) == 1
    row = contract["components"][0]
    assert row["sourceFontId"] == source_id
    assert row["sourceGlyphUnicode"] == [10, 65, ord("过")]
    assert row["missingGlyphUnicode"] == [ord("跳")]
    assert row["displayText"] == "A"


def test_source_manifest_font_must_be_present_in_the_plan_asset_identity_set():
    source_id = "font:manifest-backed"
    plan = {"assets": [{"sourceId": "font:another", "kind": "bitmap"}],
        "components": [{"sourceId": "label:x", "node": "node:x", "type": "cc.Label",
            "bitmapLabel": True, "enabled": True, "font": source_id, "text": "跳"}]}
    manifest = {"assets": [{"sourceId": source_id, "kind": "cc.BitmapFont", "document": {
        "instances": [{"_fntConfig": {"fontDefDictionary": {"65": {}}}}],
    }}]}
    with pytest.raises(BitmapMissingGlyphError, match="source_font_unresolved"):
        prepare(plan, manifest)
