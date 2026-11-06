"""Static source BitmapFont missing-glyph policy for native TMP presentation.

The source Creator 2.4 bitmap renderer omits characters with no glyph definition.
This contract preserves the Label text and source font identity while describing
the smaller string a native Unity preprocessor must render.
"""

from __future__ import annotations

POLICY = "cocos24-bitmap-missing-glyph-skip-v1"
SOURCE_EVIDENCE = "cocos2d/core/renderer/utils/label/bmfont.js:235"
_NON_GLYPH_CONTROLS = {0x0A}


class BitmapMissingGlyphError(ValueError):
    pass


def _font_map(plan: dict, manifest: dict) -> dict[str, set[int]]:
    rows_by_source: dict[str, set[int]] = {}
    planned_ids = {
        row.get("sourceId") for row in (plan.get("assets", []) or [])
        if isinstance(row, dict) and row.get("kind") in ("bitmap", "cc.BitmapFont")
        and isinstance(row.get("sourceId"), str)
    }
    planned_ids.update(
        row.get("sourceId") or row.get("id") for row in (plan.get("bitmapFonts", []) or [])
        if isinstance(row, dict) and isinstance(row.get("sourceId") or row.get("id"), str)
    )
    for source in (plan.get("bitmapFonts", []), manifest.get("bitmapFonts", [])):
        for font in source or []:
            if not isinstance(font, dict):
                continue
            source_id = font.get("sourceId") or font.get("id")
            if not isinstance(source_id, str) or not source_id:
                continue
            if planned_ids and source_id not in planned_ids:
                continue
            glyphs = _glyph_rows(font)
            if glyphs is None:
                continue
            values: set[int] = set()
            for glyph in glyphs:
                value = glyph.get("unicode") if isinstance(glyph, dict) else None
                if type(value) is not int or not 0 <= value <= 0x10FFFF or 0xD800 <= value <= 0xDFFF:
                    raise BitmapMissingGlyphError(f"bitmap_font_glyph_unicode_invalid:{source_id}")
                values.add(value)
            if source_id in rows_by_source and rows_by_source[source_id] != values:
                raise BitmapMissingGlyphError(f"bitmap_font_glyph_source_disagreement:{source_id}")
            rows_by_source[source_id] = values
    # Creator plans serialize a bitmap asset reference (sourceId/path/counts)
    # while the hash-bound source manifest retains the actual cc.BitmapFont
    # object graph and its _fntConfig.fontDefDictionary. Read that source object
    # by asset identity; never infer glyph coverage from names or counts.
    for asset in manifest.get("assets", []) or []:
        if not isinstance(asset, dict) or asset.get("kind") != "cc.BitmapFont":
            continue
        source_id = asset.get("sourceId")
        if not isinstance(source_id, str) or not source_id:
            continue
        if planned_ids and source_id not in planned_ids:
            continue
        glyph_map = _font_dictionary(asset)
        if glyph_map is None:
            continue
        values = _unicode_keys(glyph_map, source_id)
        if source_id in rows_by_source and rows_by_source[source_id] != values:
            raise BitmapMissingGlyphError(f"bitmap_font_glyph_source_disagreement:{source_id}")
        rows_by_source[source_id] = values
    return rows_by_source


def _glyph_rows(font: dict) -> list | None:
    glyphs = font.get("glyphs")
    if isinstance(glyphs, list):
        return glyphs
    dictionary = _font_dictionary(font)
    if dictionary is None:
        return None
    source_id = font.get("sourceId") or font.get("id") or "unknown"
    return [{"unicode": value} for value in _unicode_keys(dictionary, source_id)]


def _font_dictionary(font: dict) -> dict | None:
    candidates = [font]
    document = font.get("document")
    if isinstance(document, dict):
        candidates.extend(document.get("instances", []) or [])
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        config = candidate.get("_fntConfig") or candidate.get("fntConfig")
        if isinstance(config, dict):
            dictionary = config.get("fontDefDictionary")
            if isinstance(dictionary, dict):
                return dictionary
        dictionary = candidate.get("fontDefDictionary")
        if isinstance(dictionary, dict):
            return dictionary
    return None


def _unicode_keys(dictionary: dict, source_id: str) -> set[int]:
    values = set()
    for key in dictionary:
        try:
            value = int(key)
        except (TypeError, ValueError) as exc:
            raise BitmapMissingGlyphError(f"bitmap_font_glyph_unicode_invalid:{source_id}") from exc
        if not 0 <= value <= 0x10FFFF or 0xD800 <= value <= 0xDFFF:
            raise BitmapMissingGlyphError(f"bitmap_font_glyph_unicode_invalid:{source_id}")
        values.add(value)
    return values


def _display_text(source_text: str, glyphs: set[int]) -> tuple[str, list[int]]:
    rendered = bytearray()
    missing: list[int] = []
    # Source bmfont.js uses String.charAt, i.e. UTF-16 code units.
    encoded=source_text.encode('utf-16-le',errors='surrogatepass')
    for index in range(0,len(encoded),2):
        codepoint=int.from_bytes(encoded[index:index+2],'little')
        if codepoint==0x0D:continue  # source records a zero-advance placeholder
        if codepoint in glyphs or codepoint in _NON_GLYPH_CONTROLS:
            rendered.extend(encoded[index:index+2])
        else:
            missing.append(codepoint)
    return rendered.decode('utf-16-le',errors='surrogatepass'), sorted(set(missing))


def prepare(plan: dict, manifest: dict) -> dict:
    """Build source-derived skip contracts for BitmapFont labels with missing glyphs."""
    font_glyphs = _font_map(plan, manifest)
    slots = []
    for component in plan.get("components", []):
        if not isinstance(component, dict) or component.get("type") != "cc.Label":
            continue
        if component.get("bitmapLabel") is not True or not isinstance(component.get("text"), str):
            continue
        font_id = component.get("font")
        if not isinstance(font_id, str) or font_id not in font_glyphs:
            raise BitmapMissingGlyphError(f"bitmap_label_source_font_unresolved:{component.get('sourceId')}")
        source_text = component["text"]
        display_text, missing = _display_text(source_text, font_glyphs[font_id])
        if not missing:
            continue
        if not isinstance(component.get("sourceId"), str) or not isinstance(component.get("node"), str):
            raise BitmapMissingGlyphError("bitmap_label_source_identity_missing")
        slots.append({
            "sourceComponentId": component["sourceId"],
            "sourceNodeId": component["node"],
            "sourceEnabled": component.get("enabled") is True,
            "sourceText": source_text,
            "sourceFontId": font_id,
            "sourceGlyphUnicode": sorted(font_glyphs[font_id]),
            "missingGlyphUnicode": missing,
            "displayText": display_text,
            "policy": POLICY,
            "sourceCodeEvidence": SOURCE_EVIDENCE,
            "missingGlyphsAreVisibleTextRecovered": False,
        })
    slots.sort(key=lambda row: row["sourceComponentId"])
    return {
        "schema": "monkey-prefab-bitmap-missing-glyphs/1",
        "status": "source_missing_glyphs_retained_and_skipped" if slots else "not_applicable",
        "policy": POLICY,
        "sourceCodeEvidence": SOURCE_EVIDENCE,
        "components": slots,
        "missingGlyphsAreVisibleTextRecovered": False,
    }


def verify_readback(contract: dict, actual: list[dict] | None) -> dict:
    """Strictly verify persistent component refs, source fields, glyph set and derived text."""
    expected_rows = contract.get("components", []) if isinstance(contract, dict) else []
    actual_rows = actual if isinstance(actual, list) else []
    by_id: dict[str, list[dict]] = {}
    errors = []
    if not isinstance(contract, dict) or contract.get("schema") != "monkey-prefab-bitmap-missing-glyphs/1" or contract.get("policy") != POLICY:
        errors.append("bitmap_missing_glyph_contract_invalid")
    if isinstance(contract, dict) and contract.get("missingGlyphsAreVisibleTextRecovered") is not False:
        errors.append("bitmap_missing_glyph_boundary_misrepresented")
    for row in actual_rows:
        if isinstance(row, dict) and isinstance(row.get("sourceComponentId"), str):
            by_id.setdefault(row["sourceComponentId"], []).append(row)
    if not isinstance(actual, list):
        errors.append("bitmap_missing_glyph_readback_missing")
    if set(by_id) != {row.get("sourceComponentId") for row in expected_rows}:
        errors.append("bitmap_missing_glyph_component_set_mismatch")
    fields = (
        "sourceNodeId", "sourceEnabled", "sourceText", "sourceFontId", "sourceGlyphUnicode",
        "missingGlyphUnicode", "displayText", "policy", "sourceCodeEvidence",
        "missingGlyphsAreVisibleTextRecovered",
    )
    for expected in expected_rows:
        source_id = expected.get("sourceComponentId")
        matches = by_id.get(source_id, [])
        if len(matches) != 1:
            errors.append(f"{source_id}:component_readback_identity_mismatch")
            continue
        row = matches[0]
        for field in fields:
            if row.get(field) != expected.get(field):
                errors.append(f"{source_id}:{field}_mismatch")
        if row.get("targetReferenceVerified") is not True:
            errors.append(f"{source_id}:target_reference_unverified")
        if row.get("targetFontReferenceVerified") is not True:
            errors.append(f"{source_id}:target_font_reference_unverified")
        if row.get("persistedTargetReferenceVerified") is not True:
            errors.append(f"{source_id}:persistent_target_reference_unverified")
        if row.get("persistedFontReferenceVerified") is not True:
            errors.append(f"{source_id}:persistent_font_reference_unverified")
        if not isinstance(row.get("targetGuid"), str) or not row["targetGuid"]:
            errors.append(f"{source_id}:persistent_target_guid_missing")
        if not isinstance(row.get("targetFontGuid"), str) or not row["targetFontGuid"]:
            errors.append(f"{source_id}:persistent_font_guid_missing")
        if row.get("rendererInstalled") is not True:
            errors.append(f"{source_id}:derived_renderer_not_installed")
        if row.get("targetSourceComponentId") != source_id:
            errors.append(f"{source_id}:target_component_reference_mismatch")
        if row.get("targetFontSourceId") != expected.get("sourceFontId"):
            errors.append(f"{source_id}:target_font_reference_mismatch")
        if row.get("targetText") != expected.get("sourceText"):
            errors.append(f"{source_id}:target_source_text_mismatch")
    return {
        "status": "verified_bitmap_missing_glyph_policy" if not errors else "mismatch",
        "errors": errors,
        "sourceTextRetained": not errors,
        "missingGlyphsAreVisibleTextRecovered": False,
    }
