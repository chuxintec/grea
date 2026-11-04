"""Prepare source-bound native text/outline plans for Cocos Creator 2.4.15.

This is a metadata-only continuation. It does not rasterize text, read system
fonts, launch Creator/Unity, or claim source/target visual equivalence. The
source Canvas renderer's font metrics and the source device/font face remain
explicitly unknown unless a later, separate receipt proves them.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

from . import io


SCHEMA = "monkey-static-text-continuation/1"
SOURCE_PROFILE = "cocos-2.4.15-bundle"
SOURCE_VERSION = "2.4.15"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GUID = re.compile(r"^[0-9a-f]{32}$")

_RAW_BASE = "https://raw.githubusercontent.com/cocos/cocos-engine/v2.4.15/"
_SOURCE_ENGINE_PINS = {
    "cocos2d/core/components/CCComponent.js": "69c5e561c9d42aea846b96fcc7e741411be0236dd10eb5ec8103610758350222",
    "cocos2d/core/components/CCLabel.js": "064e1f434073f1907490d84316239c3f21ae0857b9f250c2aa724a31045054ef",
    "cocos2d/core/components/CCLabelOutline.js": "878eb5fedb6c4fadfe2fecc9637659d10557decafe471c5d812685724548c35f",
    "cocos2d/core/renderer/utils/label/bmfont.js": "6c85859d7bc0ce061d522e5e3e85943169c9ad4e8f7f2806b4ff44a53f7ff775",
    "cocos2d/core/renderer/utils/label/ttf.js": "491976bc4e4d7cb9866b587592acede432f87860831952698843a74297d3f2b8",
    "cocos2d/core/utils/text-utils.js": "09fd74a03bfaf7b6a0f5a5a10f0a9797a7a12f0e76e9b6ffc586e8bd462c8772",
}


class StaticTextContinuationError(ValueError):
    pass


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(float(value))


def _source_engine_pins(source_evidence: dict | None) -> list[dict]:
    if source_evidence is None:
        raise StaticTextContinuationError("STATIC_TEXT_SOURCE_ENGINE_EVIDENCE_REQUIRED")
    if (not isinstance(source_evidence, dict) or source_evidence.get("sourceVersion") != SOURCE_VERSION
            or source_evidence.get("sourceProfile", SOURCE_PROFILE) != SOURCE_PROFILE):
        raise StaticTextContinuationError("STATIC_TEXT_SOURCE_ENGINE_VERSION_UNSUPPORTED")
    rows = source_evidence.get("files")
    if not isinstance(rows, list):
        raise StaticTextContinuationError("STATIC_TEXT_SOURCE_ENGINE_FILES_MISSING")
    by_path = {}
    for row in rows:
        if not isinstance(row, dict):
            raise StaticTextContinuationError("STATIC_TEXT_SOURCE_ENGINE_FILE_ROW_INVALID")
        logical = row.get("logicalPath")
        if not isinstance(logical, str) or logical in by_path:
            raise StaticTextContinuationError("STATIC_TEXT_SOURCE_ENGINE_FILE_PATH_DUPLICATE_OR_MISSING")
        by_path[logical] = row
    verified = []
    for logical, expected_sha in _SOURCE_ENGINE_PINS.items():
        row = by_path.get(logical)
        if not isinstance(row, dict) or row.get("sha256") != expected_sha:
            raise StaticTextContinuationError("STATIC_TEXT_SOURCE_ENGINE_PIN_MISMATCH:" + logical)
        url = row.get("originUrl")
        if url != _RAW_BASE + logical:
            raise StaticTextContinuationError("STATIC_TEXT_SOURCE_ENGINE_ORIGIN_MISMATCH:" + logical)
        raw_path = row.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise StaticTextContinuationError("STATIC_TEXT_SOURCE_ENGINE_FILE_PATH_MISSING:" + logical)
        path = Path(raw_path).resolve(strict=True)
        if path.is_symlink() or not path.is_file():
            raise StaticTextContinuationError("STATIC_TEXT_SOURCE_ENGINE_FILE_NOT_REGULAR:" + logical)
        raw = path.read_bytes()
        if _sha(raw) != expected_sha or type(row.get("bytes")) is not int or len(raw) != row["bytes"]:
            raise StaticTextContinuationError("STATIC_TEXT_SOURCE_ENGINE_BYTES_CHANGED:" + logical)
        verified.append({"logicalPath": logical, "sha256": expected_sha,
                         "bytes": len(raw), "originUrl": url})
    return verified


def _unique_by_id(rows, key="sourceId"):
    result = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        value = row.get(key)
        if isinstance(value, str) and value:
            result.setdefault(value, []).append(row)
    return result


def _doc_for_source_id(source_manifest: dict, source_id: str):
    """Resolve one serialized object from an explicit asset#instance path."""
    if not isinstance(source_id, str) or "#" not in source_id or "/" in source_id.split("#", 1)[1]:
        return None
    asset_id, instance_text = source_id.rsplit("#", 1)
    if not instance_text.isdigit():
        return None
    assets = _unique_by_id(source_manifest.get("assets"))
    matches = assets.get(asset_id, [])
    if len(matches) != 1:
        return None
    instances = matches[0].get("document", {}).get("instances")
    index = int(instance_text)
    if not isinstance(instances, list) or index >= len(instances) or not isinstance(instances[index], dict):
        return None
    return instances[index]


def _source_component(source_manifest: dict, source_id: str, expected_type: str):
    """Resolve a label/outline from direct component IDs or component IDs used as roots."""
    if not isinstance(source_id, str) or "#" not in source_id:
        return None, None
    asset_id, locator = source_id.rsplit("#", 1)
    pieces = locator.split("/")
    if not pieces or not pieces[0].isdigit():
        return None, None
    assets = _unique_by_id(source_manifest.get("assets"))
    asset_rows = assets.get(asset_id, [])
    if len(asset_rows) != 1:
        return None, None
    instances = asset_rows[0].get("document", {}).get("instances")
    instance_index = int(pieces[0])
    if not isinstance(instances, list) or instance_index >= len(instances):
        return None, None
    value = instances[instance_index]
    if not isinstance(value, dict):
        return None, None
    if len(pieces) == 3 and pieces[1] == "components" and pieces[2].isdigit():
        if value.get("__type__") != "cc.Node":
            return None, None
        component_index = int(pieces[2])
        components = value.get("_components")
        if not isinstance(components, list) or component_index >= len(components):
            return None, None
        component = components[component_index]
        return (component, value) if isinstance(component, dict) and component.get("__type__") == expected_type else (None, None)
    if len(pieces) == 1 and value.get("__type__") == expected_type:
        node_ref = value.get("node")
        node = None
        if isinstance(node_ref, dict) and type(node_ref.get("__id__")) is int and node_ref["__id__"] < len(instances):
            candidate = instances[node_ref["__id__"]]
            node = candidate if isinstance(candidate, dict) and candidate.get("__type__") == "cc.Node" else None
        return value, node
    return None, None


def _color_from_serialized(value):
    if isinstance(value, list) and len(value) == 4 and all(type(v) is int for v in value):
        return list(value)
    if isinstance(value, dict):
        values = value.get("values")
        if isinstance(values, list) and len(values) == 4 and all(type(v) is int for v in values):
            return list(values)
        if isinstance(values, list) and len(values) == 1 and type(values[0]) is int:
            packed = values[0] & 0xffffffff
            # Creator serializes cc.Color as little-endian RGBA in the packed
            # uint: 0xAABBGGRR (e.g. 0xff177750 -> [80,119,23,255]).
            return [packed & 255, (packed >> 8) & 255, (packed >> 16) & 255, (packed >> 24) & 255]
    return None


def _effective_label_source(raw: dict) -> dict:
    style = raw.get("_styleFlags", 0)
    if type(style) is not int or style < 0:
        raise StaticTextContinuationError("STATIC_TEXT_SOURCE_STYLE_FLAGS_INVALID")
    return {
        "text": raw.get("_string", raw.get("_N$string", "")),
        "fontSize": raw.get("_fontSize", 40),
        "lineHeight": raw.get("_lineHeight", 40),
        "overflow": raw.get("_overflow", raw.get("_N$overflow", 0)),
        "wrap": raw.get("_enableWrapText", True),
        "bold": bool(style & 1),
        "italic": bool(style & 2),
        "underline": bool(style & 4),
        "font": raw.get("_N$file"),
        "systemFont": raw.get("_isSystemFontUsed", True),
        "fontFamily": raw.get("_fontFamily", raw.get("_N$fontFamily", "Arial")),
        "cacheMode": raw.get("_cacheMode", 0),
    }


def _source_font_id(raw_value, source_manifest: dict):
    if raw_value is None:
        return None
    if isinstance(raw_value, dict):
        raw_value = raw_value.get("__uuid__") or raw_value.get("uuid")
    if not isinstance(raw_value, str) or not raw_value:
        return None
    for asset in source_manifest.get("assets", []):
        if not isinstance(asset, dict):
            continue
        asset_id = asset.get("sourceId")
        uuid = asset.get("uuid") or asset.get("assetUuid")
        if raw_value in (asset_id, uuid) or isinstance(asset_id, str) and asset_id.rsplit(":", 1)[-1] == raw_value:
            return asset_id
    return raw_value


def _resolve_alias(value, aliases: dict):
    seen = set()
    while isinstance(value, str) and value in aliases:
        if value in seen:
            raise StaticTextContinuationError("STATIC_TEXT_SOURCE_ALIAS_CYCLE")
        seen.add(value)
        value = aliases[value]
    return value


def _validate_source_label(plan_row: dict, ir_row: dict, raw: dict, aliases: dict,
                           source_manifest: dict) -> None:
    effective = _effective_label_source(raw)
    for key in ("text", "fontSize", "lineHeight", "overflow", "wrap", "bold", "italic", "underline"):
        plan_value = plan_row.get(key)
        if key in ("bold", "italic", "underline") and plan_row.get("bitmapLabel") is True:
            plan_value = plan_row.get("source" + key.capitalize(), effective[key])
        if plan_value != ir_row.get(key):
            raise StaticTextContinuationError("STATIC_TEXT_PLAN_IR_FIELD_DRIFT:" + key)
        if plan_value != effective[key]:
            raise StaticTextContinuationError("STATIC_TEXT_SOURCE_FIELD_DRIFT:" + key)
    source_font = plan_row.get("sourceFont")
    if source_font is None and effective["font"] is not None:
        source_font = plan_row.get("font")
    if (_resolve_alias(source_font, aliases) != _resolve_alias(ir_row.get("font"), aliases)
            or _resolve_alias(_source_font_id(effective["font"], source_manifest), aliases)
            != _resolve_alias(ir_row.get("font"), aliases)):
        raise StaticTextContinuationError("STATIC_TEXT_SOURCE_FONT_REFERENCE_DRIFT")
    if plan_row.get("systemFont") is not ir_row.get("systemFont") or plan_row.get("systemFont") is not effective["systemFont"]:
        raise StaticTextContinuationError("STATIC_TEXT_SOURCE_SYSTEM_FONT_DRIFT")
    if plan_row.get("fontFamily") != ir_row.get("fontFamily") or plan_row.get("fontFamily") != effective["fontFamily"]:
        raise StaticTextContinuationError("STATIC_TEXT_SOURCE_FONT_FAMILY_DRIFT")
    if effective["cacheMode"] not in (0, 1):
        raise StaticTextContinuationError("STATIC_TEXT_CACHE_MODE_NOT_PROFILED")


def _font_binding(plan: dict, component: dict, bitmap_fonts: dict) -> dict | None:
    binding = component.get("nativeSystemFontBinding")
    if not isinstance(binding, dict):
        bindings = plan.get("systemFontBinding", {}).get("labelBindings", [])
        matches = [row for row in bindings if isinstance(row, dict) and row.get("sourceLabelId") == component.get("sourceId")]
        binding = matches[0] if len(matches) == 1 else None
    if isinstance(binding, dict):
        sid = component.get("sourceId")
        if (binding.get("sourceLabelId") != sid or binding.get("sourceSystemFont") is not True
                or binding.get("sourceText") != component.get("text")
                or not isinstance(binding.get("nativeFontAssetId"), str)
                or not isinstance(binding.get("nativeFontAssetPath"), str)
                or not isinstance(binding.get("nativeFallbackAssetIds"), list)
                or not isinstance(binding.get("nativeFallbackAssetPaths"), list)
                or len(binding["nativeFallbackAssetIds"]) != len(binding["nativeFallbackAssetPaths"])
                or not _number(binding.get("pointSize")) or float(binding["pointSize"]) != float(component.get("fontSize", -1))):
            return None
        ordered_font_ids = [binding["nativeFontAssetId"], *binding["nativeFallbackAssetIds"]]
        ordered_font_paths = [binding["nativeFontAssetPath"], *binding["nativeFallbackAssetPaths"]]
        if len(set(ordered_font_ids)) != len(ordered_font_ids) or len(set(ordered_font_paths)) != len(ordered_font_paths):
            return None
        fonts = plan.get("systemFontBinding", {}).get("systemFonts", {}).get("fonts", [])
        font_id_rows = [row.get("assetId") for row in fonts if isinstance(row, dict)]
        font_ids = set(font_id_rows)
        required_ids = {binding["nativeFontAssetId"], *binding["nativeFallbackAssetIds"]}
        if len(font_ids) != len(font_id_rows) or not required_ids.issubset(font_ids):
            return None
        font_rows = {row.get("assetId"): row for row in fonts if isinstance(row, dict)}
        if any(font_rows[asset_id].get("assetPath") != asset_path
               for asset_id, asset_path in zip(ordered_font_ids, ordered_font_paths)):
            return None
        required_chars = {char for char in component.get("text", "")
                          if not char.isspace() and unicodedata.category(char) not in ("Cc", "Cf", "Zl", "Zp")}
        available_chars = set()
        for asset_id in required_ids:
            font_row = font_rows.get(asset_id)
            if isinstance(font_row, dict):
                available_chars.update(row.get("character") for row in font_row.get("requiredGlyphs", [])
                                       if isinstance(row, dict))
        if not required_chars.issubset(available_chars):
            return None
        if any(asset_id.startswith("coretext-static-sdf-") for asset_id in binding["nativeFallbackAssetIds"]):
            staged = plan.get("staticFontInputs")
            artifacts = {row.get("artifactKind") for row in staged.get("copies", []) if isinstance(row, dict)} \
                if isinstance(staged, dict) else set()
            if (not isinstance(staged, dict) or staged.get("status") != "staged" or
                    not {"glyph-atlas", "glyph-metrics", "portable-generation-receipt"}.issubset(artifacts)):
                return None
        return {"kind": "system-font", "binding": deepcopy(binding),
                "assetIds": ordered_font_ids, "assetPaths": ordered_font_paths}

    font_id = component.get("font")
    bitmap = bitmap_fonts.get(font_id)
    if isinstance(bitmap, dict):
        atlas_guid = bitmap.get("atlasGuid")
        if not isinstance(bitmap.get("fontPath"), str) or not isinstance(atlas_guid, str) or not re.fullmatch(r"[0-9a-fA-F]{32}", atlas_guid):
            return None
        glyphs = bitmap.get("glyphs")
        if not isinstance(glyphs, list) or not glyphs:
            return None
        return {"kind": "bitmap-font", "assetIds": [font_id], "assetPaths": [bitmap["fontPath"]],
                "atlasGuid": atlas_guid, "glyphCount": len(glyphs)}
    explicit = [row for row in plan.get("assets", []) if isinstance(row, dict)
                and row.get("id") == font_id and row.get("kind") == "cc.TTFFont"]
    if len(explicit) == 1 and isinstance(explicit[0].get("fontAssetPath"), str):
        return {"kind": "explicit-ttf", "assetIds": [font_id], "assetPaths": [explicit[0]["fontAssetPath"]],
                "sourceAssetPath": explicit[0].get("path")}
    return None


def _plan_groups(plan: dict, ir: dict, source_manifest: dict, engine_pins: list[dict]):
    plan_components = _unique_by_id(plan.get("components"))
    ir_components = _unique_by_id(ir.get("components"))
    origin_rows = {}
    sync_bindings = plan.get("syncPrefabBindings", [])
    for binding in sync_bindings if isinstance(sync_bindings, list) else []:
        if not isinstance(binding, dict):
            continue
        component_origins = binding.get("componentOrigins", [])
        for origin in component_origins if isinstance(component_origins, list) else []:
            if not isinstance(origin, dict):
                continue
            instance_id, template_id = origin.get("instanceSourceId"), origin.get("templateSourceId")
            if isinstance(instance_id, str) and instance_id and isinstance(template_id, str) and template_id:
                origin_rows.setdefault(instance_id, []).append(template_id)

    def canonical_source_id(source_id):
        current, seen = source_id, set()
        while current in origin_rows:
            if current in seen:
                return None, "STATIC_TEXT_SOURCE_COMPONENT_ORIGIN_CYCLE"
            seen.add(current)
            targets = sorted(set(origin_rows[current]))
            if len(targets) != 1:
                return None, "STATIC_TEXT_SOURCE_COMPONENT_ORIGIN_AMBIGUOUS"
            current = targets[0]
        return current, None
    labels_by_node = {}
    outlines_by_node = {}
    for rows in plan_components.values():
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("type") == "cc.Label":
                labels_by_node.setdefault(row.get("node"), []).append(row)
            elif row.get("type") == "cc.LabelOutline":
                outlines_by_node.setdefault(row.get("node"), []).append(row)
    bitmap_fonts = {row.get("id"): row for row in plan.get("bitmapFonts", []) if isinstance(row, dict)}
    deltas = []
    groups = []
    gaps = []
    for node_id in sorted(set(labels_by_node) | set(outlines_by_node), key=str):
        outlines = outlines_by_node.get(node_id, [])
        labels = labels_by_node.get(node_id, [])
        if len(labels) != 1 or len(outlines) > 1 or (not labels and outlines):
            gaps.extend({"code": "STATIC_TEXT_SAME_NODE_LABEL_OUTLINE_AMBIGUOUS",
                         "sourceId": row.get("sourceId"), "nodeId": node_id,
                         "labelCount": len(labels), "outlineCount": len(outlines)} for row in outlines)
            if labels:
                gaps.extend({"code": "STATIC_TEXT_SAME_NODE_LABEL_OUTLINE_AMBIGUOUS",
                             "sourceId": row.get("sourceId"), "nodeId": node_id,
                             "labelCount": len(labels), "outlineCount": len(outlines)} for row in labels)
            continue
        outline = outlines[0] if outlines else None
        label = labels[0]
        outline_id, label_id = outline.get("sourceId") if outline else None, label.get("sourceId")
        if not isinstance(label_id, str) or (outline is not None and not isinstance(outline_id, str)):
            gaps.append({"code": "STATIC_TEXT_COMPONENT_ID_INVALID", "sourceId": label_id or outline_id})
            continue
        canonical_label_id, label_origin_error = canonical_source_id(label_id)
        canonical_outline_id, outline_origin_error = canonical_source_id(outline_id) if outline_id else (None, None)
        if label_origin_error or outline_origin_error:
            gaps.append({"code": label_origin_error or outline_origin_error,
                         "sourceIds": [label_id, outline_id]})
            continue
        ir_label_rows = ir_components.get(canonical_label_id, [])
        ir_outline_rows = ir_components.get(canonical_outline_id, []) if canonical_outline_id else []
        if not ir_label_rows or (outline is not None and not ir_outline_rows):
            gaps.append({"code": "STATIC_TEXT_IR_COMPONENT_ID_NOT_FOUND", "sourceIds": [label_id, outline_id],
                         "canonicalSourceIds": [canonical_label_id, canonical_outline_id]})
            continue
        ir_label = ir_label_rows[0]
        ir_outline = ir_outline_rows[0] if ir_outline_rows else None
        source_semantic_keys = ("text", "fontSize", "lineHeight", "overflow", "wrap", "bold", "italic", "underline",
                                "font", "fontFamily", "systemFont", "enabled")
        semantic_signatures = {_canonical({key: row.get(key) for key in source_semantic_keys}) for row in ir_label_rows}
        if len(semantic_signatures) != 1:
            gaps.append({"code": "STATIC_TEXT_IR_COMPONENT_SEMANTICS_AMBIGUOUS", "sourceId": label_id})
            continue
        raw_label, raw_label_node = _source_component(source_manifest, canonical_label_id, "cc.Label")
        raw_outline, raw_outline_node = (_source_component(source_manifest, canonical_outline_id, "cc.LabelOutline")
                                         if canonical_outline_id else (None, None))
        if not isinstance(raw_label, dict) or (outline is not None and not isinstance(raw_outline, dict)):
            gaps.append({"code": "STATIC_TEXT_SOURCE_SERIALIZATION_UNRESOLVED", "sourceIds": [label_id, outline_id]})
            continue
        try:
            _validate_source_label(label, ir_label, raw_label, ir.get("aliases", {}), source_manifest)
        except StaticTextContinuationError as exc:
            gaps.append({"code": str(exc), "sourceId": label_id})
            continue
        source_outline_width, source_outline_color, source_outline_enabled = 0, None, False
        if outline is not None:
            raw_outline_node_ref = raw_outline.get("node") if isinstance(raw_outline.get("node"), dict) else {}
            raw_label_node_ref = raw_label.get("node") if isinstance(raw_label.get("node"), dict) else {}
            if raw_outline.get("__type__") != "cc.LabelOutline" or raw_outline_node_ref.get("__id__") != raw_label_node_ref.get("__id__"):
                gaps.append({"code": "STATIC_TEXT_SOURCE_OUTLINE_NODE_DRIFT", "sourceIds": [label_id, outline_id]})
                continue
            source_outline_width = raw_outline.get("_width", 1)
            source_outline_color = _color_from_serialized(raw_outline.get("_color", {"values": [255, 255, 255, 255]}))
            source_outline_enabled = raw_outline.get("enabled", raw_outline.get("_enabled", True))
            if (outline.get("width") != ir_outline.get("width") or outline.get("outlineColor") != ir_outline.get("outlineColor")
                    or outline.get("width") != source_outline_width or outline.get("outlineColor") != source_outline_color
                    or outline.get("enabled") != source_outline_enabled):
                gaps.append({"code": "STATIC_TEXT_PLAN_IR_OUTLINE_DRIFT", "sourceId": outline_id})
                continue
        native_font = _font_binding(plan, label, bitmap_fonts)
        if native_font is None:
            gaps.append({"code": "STATIC_TEXT_NATIVE_FONT_BINDING_INCOMPLETE", "sourceId": label_id,
                         "sourceOutlineId": outline_id, "sourceFont": ir_label.get("font"),
                         "systemFont": ir_label.get("systemFont")})
            continue
        node_rows = plan.get("nodes", [])
        node_matches = [row for row in node_rows if isinstance(row, dict) and row.get("sourceId") == node_id]
        if len(node_matches) != 1:
            gaps.append({"code": "STATIC_TEXT_SOURCE_NODE_PLAN_NOT_UNIQUE", "sourceId": label_id, "nodeId": node_id})
            continue
        node = node_matches[0]
        size = node.get("size")
        if not isinstance(size, list) or len(size) != 2 or not all(_number(value) and float(value) >= 0 for value in size):
            gaps.append({"code": "STATIC_TEXT_SOURCE_NODE_SIZE_UNPROVEN", "sourceId": label_id, "nodeId": node_id})
            continue
        raw_size = raw_label_node.get("_contentSize") if isinstance(raw_label_node, dict) else None
        raw_size = raw_size.get("values") if isinstance(raw_size, dict) else None
        locator = node_id.rsplit("#", 1)
        raw_label_asset = canonical_label_id.split("#", 1)[0]
        same_source_node = (len(locator) == 2 and locator[0] == raw_label_asset and locator[1].isdigit()
                            and type(raw_label_node_ref_id := (raw_label.get("node", {}).get("__id__")
                                if isinstance(raw_label.get("node"), dict) else None)) is int
                            and int(locator[1]) == raw_label_node_ref_id)
        if same_source_node and (not isinstance(raw_size, list) or len(raw_size) != 2 or
                                 any(float(raw_size[i]) != float(size[i]) for i in range(2))):
            gaps.append({"code": "STATIC_TEXT_SOURCE_NODE_SIZE_DRIFT", "sourceId": label_id, "nodeId": node_id})
            continue
        if not isinstance(label.get("text"), str) or not _number(label.get("fontSize")) or not _number(label.get("lineHeight")):
            gaps.append({"code": "STATIC_TEXT_SOURCE_FIELDS_INCOMPLETE", "sourceId": label_id})
            continue
        if label.get("overflow") not in (0, 1, 2, 3) or type(label.get("wrap")) is not bool:
            gaps.append({"code": "STATIC_TEXT_SOURCE_OVERFLOW_PROFILE_UNSUPPORTED", "sourceId": label_id})
            continue
        cache_mode = _effective_label_source(raw_label)["cacheMode"]
        if cache_mode not in (0, 1):
            gaps.append({"code": "STATIC_TEXT_CACHE_MODE_NOT_PROFILED", "sourceId": label_id,
                         "cacheMode": cache_mode})
            continue

        group_id = "static-text-" + _sha(_canonical({"label": label_id, "outline": outline_id,
                                                       "node": node_id}))[:20]
        bitmap_font = native_font["kind"] == "bitmap-font"
        shrink_lower_bound = 0.1 if bitmap_font else 0.0
        text_binding = {
            "groupId": group_id,
            "sourceLabelId": label_id,
            "sourceOutlineId": outline_id,
            "sourceNodeId": node_id,
            "fontKind": native_font["kind"],
            "nativeFontAssetIds": native_font["assetIds"],
            "nativeFontAssetPaths": native_font["assetPaths"],
            "sourceFontFamily": label.get("fontFamily"),
            "sourceFontFamilyEvidence": label.get("fontFamilyEvidence"),
            "sourceFontSize": float(label["fontSize"]),
            "sourceLineHeight": float(label["lineHeight"]),
            "sourceOverflow": label["overflow"],
            "sourceWrap": label["wrap"],
            "sourceBold": (label.get("sourceBold") if label.get("bitmapLabel") is True else label.get("bold")) is True,
            "sourceItalic": (label.get("sourceItalic", label.get("italic")) if label.get("bitmapLabel") is True else label.get("italic")) is True,
            "sourceUnderline": (label.get("sourceUnderline", label.get("underline")) if label.get("bitmapLabel") is True else label.get("underline")) is True,
            "sourceEnabled": label.get("enabled") is True,
            "sourceText": label["text"],
            "sourceTextSha256": _sha(label["text"].encode("utf-8")),
            "sourceNodeSize": [float(value) for value in size],
            "sourceNodeGeometryProvenance": "source-manifest-node-bytes" if same_source_node else "frozen-plan-after-prefab-resolution",
            "sourceNodePivot": deepcopy(node.get("anchor")),
            "sourceNodeColor": deepcopy(node.get("color")),
            "sourceOutlineEnabled": outline is not None and outline.get("enabled") is True,
            "sourceOutlineWidth": float(outline["width"]) if outline is not None and _number(outline.get("width")) else None,
            "sourceOutlineColor": deepcopy(outline.get("outlineColor")) if outline is not None else None,
            "sourceRasterization": {"status": "unknown-source-platform-and-renderer"},
            "sourceFontFace": {"status": "source-os-and-resolved-face-unknown"},
            "sourceCanvasMeasurement": {"status": "source-canvas-context-and-measureText-unavailable"},
            "nativeFontBinding": native_font,
            "layoutPolicy": {
                "profile": "cocos-2.4.15-bitmap-label-v1" if bitmap_font else "cocos-2.4.15-ttf-label-v1",
                "overflowMeaning": {0: "none", 1: "clamp", 2: "shrink", 3: "resize-height"}[label["overflow"]],
                "lineHeightPolicy": "source-line-height-scales-with-effective-font-size-and-is-integer-truncated",
                "outlinePaddingPolicy": "enabled-outline-adds-width-on-each-side-before-shrink-measurement",
                "wrapPolicy": "source-enableWrapText-applies-for-clamp-or-shrink",
                "shrinkPolicy": (("bitmap-integer-binary-search-v2.4.15" if bitmap_font else
                                  "unwrapped-scale-floor-v2.4.15" if not label["wrap"] else
                                  "wrapped-integer-binary-search-v2.4.15") if label["overflow"] == 2
                                 else "not-applicable"),
                "sourceShrinkLowerBound": shrink_lower_bound if label["overflow"] == 2 else None,
                "sourceFontSizeMaximum": float(label["fontSize"]) if label["overflow"] == 2 else None,
                "targetAutoSizing": label["overflow"] == 2 and not bitmap_font,
                "targetAutoSizeMin": 0.0 if label["overflow"] == 2 and not bitmap_font else None,
                "targetAutoSizeMax": float(label["fontSize"]) if label["overflow"] == 2 and not bitmap_font else None,
                "nativeLineHeightConversion": "existing-unity-source-line-height-formula-v1",
                "exactSourceMetricParity": False,
            },
        }
        groups.append(text_binding)
        label_delta = {"sourceNodeId": node_id, "convertible": True, "staticTextContinuationGroupId": group_id,
                       "nativeTextSizingPolicy": "cocos24-ttf-shrink-v1" if label["overflow"] == 2 else "cocos24-ttf-fixed-v1"}
        deltas.append({"sourceComponentId": label_id, "fields": label_delta})
        if outline_id:
            outline_delta = {"sourceNodeId": node_id, "convertible": True, "staticTextContinuationGroupId": group_id,
                             "staticBitmapOutline": native_font["kind"] == "bitmap-font",
                             "staticPresentationPolicy": "source-evidenced-native-renderer-v1"}
            deltas.append({"sourceComponentId": outline_id, "fields": outline_delta})

    patched = deepcopy(plan)
    by_id = {}
    for row in patched.get("components", []):
        if isinstance(row, dict):
            by_id.setdefault((row.get("sourceId"), row.get("node")), []).append(row)
    for delta in deltas:
        component_rows = by_id.get((delta["sourceComponentId"], delta["fields"].get("sourceNodeId")), [])
        if len(component_rows) != 1:
            raise StaticTextContinuationError("STATIC_TEXT_COMPONENT_DELTA_SOURCE_ID_NOT_FOUND")
        component_rows[0].update({key: deepcopy(value) for key, value in delta["fields"].items()
                                  if key != "sourceNodeId"})
    fragment = {
        "schemaVersion": 1,
        "contract": SCHEMA,
        "sourceVersion": SOURCE_VERSION,
        "sourceProfile": SOURCE_PROFILE,
        "sourceManifestSha256": plan.get("sourceManifestSha256"),
        "sourceIrSha256": plan.get("sourceIrSha256"),
        "sourceEngineFiles": engine_pins,
        "status": "prepared" if groups else "no_eligible_source_groups",
        "components": groups,
        "componentDeltas": deltas,
        "gaps": gaps,
        "verificationPolicy": {
            "nativeTextMetrics": "required-from-saved-prefab-reopen",
            "sourceFontPlatformEquivalence": "not-claimed",
            "sourceCanvasMeasureText": "not-available",
            "sourceRasterizationParity": "not-claimed",
            "visualEquivalence": False,
            "clearWarningsOnlyWhen": ["exact-source-fields", "exact-native-font-identity",
                                      "native-sizing-and-linebox-readback", "outline-material-readback",
                                      "source-font-metric-and-canvas-evidence"],
        },
    }
    patched["staticTextContinuation"] = fragment
    patched["staticTextContinuationJson"] = json.dumps(fragment, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    summary = {
        "schema": SCHEMA,
        "preparationStatus": fragment["status"],
        "sourceGroupCount": len(groups),
        "systemFontGroupCount": sum(row["fontKind"] == "system-font" for row in groups),
        "bitmapFontGroupCount": sum(row["fontKind"] == "bitmap-font" for row in groups),
        "explicitTtfGroupCount": sum(row["fontKind"] == "explicit-ttf" for row in groups),
        "sourceMetricWarningsResolved": False,
        "sourceCanvasMetricStatus": "unknown",
        "sourceRasterizationStatus": "unknown",
        "visualEquivalent": False,
        "gapCount": len(gaps),
    }
    patched["staticTextContinuationSummary"] = summary
    return {"plan": patched, "continuation": fragment, "summary": summary, "status": fragment["status"]}


def prepare(plan: dict, ir: dict, manifest: dict, stage_root: str | Path, *, source_evidence: dict | None = None) -> dict:
    """Build a fresh plan delta for paired Labels/Outlines with pinned fonts.

    The caller must verify input file pins and owns copying a frozen plan to a
    fresh stage. This function itself writes no payloads and never runs a
    Cocos/Unity script or renderer.
    """
    if not isinstance(plan, dict) or not isinstance(ir, dict) or not isinstance(manifest, dict):
        raise StaticTextContinuationError("STATIC_TEXT_INPUT_DOCUMENT_INVALID")
    if plan.get("projectLayout") != "monkey-project/2.0.0":
        raise StaticTextContinuationError("STATIC_TEXT_TARGET_PROJECT_LAYOUT_UNSUPPORTED")
    if manifest.get("sourceVersion") != SOURCE_VERSION or ir.get("sourceProfile") != SOURCE_PROFILE:
        raise StaticTextContinuationError("STATIC_TEXT_SOURCE_PROFILE_OR_VERSION_MISMATCH")
    manifest_sha = plan.get("sourceManifestSha256")
    if not isinstance(manifest_sha, str) or not _SHA256.fullmatch(manifest_sha):
        raise StaticTextContinuationError("STATIC_TEXT_SOURCE_MANIFEST_SHA_MISSING")
    if ir.get("sourceManifestSha256") != manifest_sha:
        raise StaticTextContinuationError("STATIC_TEXT_IR_MANIFEST_SHA_MISMATCH")
    source_ir_sha = plan.get("sourceIrSha256")
    if not isinstance(source_ir_sha, str) or not _SHA256.fullmatch(source_ir_sha):
        raise StaticTextContinuationError("STATIC_TEXT_SOURCE_IR_SHA_MISSING")
    output = Path(stage_root).resolve(strict=True)
    if not output.is_dir() or output.is_symlink():
        raise StaticTextContinuationError("STATIC_TEXT_STAGE_ROOT_INVALID")
    if manifest.get("assets") is None or not isinstance(manifest.get("assets"), list):
        raise StaticTextContinuationError("STATIC_TEXT_SOURCE_MANIFEST_ASSETS_MISSING")
    if plan.get("staticTextContinuation"):
        raise StaticTextContinuationError("STATIC_TEXT_CONTINUATION_ALREADY_PRESENT")
    pins = _source_engine_pins(source_evidence)
    return _plan_groups(plan, ir, manifest, pins)


def _continuation(plan: dict) -> dict | None:
    fragment = plan.get("staticTextContinuation")
    if isinstance(fragment, dict):
        return fragment
    raw = plan.get("staticTextContinuationJson")
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) else None
    return None


def _expected_config_sha(plan: dict, fragment: dict) -> str:
    raw = plan.get("staticTextContinuationJson")
    if isinstance(raw, str):
        return _sha(raw.encode("utf-8"))
    return _sha(_canonical(fragment))


def verify(plan: dict, candidate_root: str | Path, main_readback: dict) -> dict:
    """Verify saved-prefab native text configuration and its bound metric sidecars.

    The result only proves the fields represented by the Unity readback. It does
    not prove source OS face selection, Cocos Canvas measurement, source
    rasterization parity, or visual equivalence.
    """
    diagnostics = []

    def issue(code, source_id=None, message=None, location="Analysis/Readback/TextMetrics"):
        diagnostics.append(io.diagnostic(code, location, message or code, source_id))

    if not isinstance(plan, dict) or not isinstance(main_readback, dict):
        issue("STATIC_TEXT_VERIFY_INPUT_INVALID", message="Plan and main readback must be objects")
        return {"status": "partial", "diagnostics": diagnostics, "family_proofs": [], "gaps": []}
    fragment = _continuation(plan)
    if (not isinstance(fragment, dict) or fragment.get("contract") != SCHEMA or
            fragment.get("schemaVersion") != 1 or not isinstance(fragment.get("components"), list)):
        issue("STATIC_TEXT_CONTINUATION_CONTRACT_INVALID", message="Pinned continuation contract is missing or malformed")
        return {"status": "partial", "diagnostics": diagnostics, "family_proofs": [], "gaps": []}
    if fragment.get("sourceManifestSha256") != plan.get("sourceManifestSha256"):
        issue("STATIC_TEXT_SOURCE_MANIFEST_PIN_MISMATCH", message="Continuation and plan source manifest pins differ")
    config_sha = _expected_config_sha(plan, fragment)
    groups = fragment["components"]
    if any(not isinstance(group, dict) for group in groups):
        issue("STATIC_TEXT_GROUP_ROW_INVALID", message="Continuation contains a malformed group")
        return {"status": "partial", "diagnostics": diagnostics, "family_proofs": [], "gaps": fragment.get("gaps", [])}

    by_prefab = {}
    for group in groups:
        prefab_id = group.get("sourceNodeId", "").rsplit("#", 1)[0]
        if not prefab_id or not isinstance(group.get("sourceLabelId"), str) or (
                group.get("sourceOutlineId") is not None and not isinstance(group.get("sourceOutlineId"), str)):
            issue("STATIC_TEXT_GROUP_ID_INVALID", group.get("sourceLabelId"), "Group identities are incomplete")
            continue
        by_prefab.setdefault(prefab_id, []).append(group)
    expected_files = {}
    for prefab_id in sorted(by_prefab):
        relative = "Analysis/Readback/TextMetrics/" + _sha(prefab_id.encode("utf-8")) + ".json"
        expected_files[relative] = prefab_id
    descriptors = main_readback.get("staticTextReadbackFiles")
    if not isinstance(descriptors, list):
        descriptors = []
    descriptor_by_path = {}
    duplicate_paths = set()
    for descriptor in descriptors:
        if not isinstance(descriptor, dict) or not isinstance(descriptor.get("path"), str):
            issue("STATIC_TEXT_READBACK_DESCRIPTOR_INVALID", message="A sidecar descriptor is malformed")
            continue
        path = descriptor["path"].replace("\\", "/")
        if path in descriptor_by_path:
            duplicate_paths.add(path)
        descriptor_by_path[path] = descriptor
    if set(descriptor_by_path) != set(expected_files):
        issue("STATIC_TEXT_READBACK_FILE_SET_MISMATCH", message="Main readback sidecar list does not equal the text-group prefab set")
    for duplicate in sorted(duplicate_paths):
        issue("STATIC_TEXT_READBACK_DESCRIPTOR_DUPLICATE", message="Duplicate descriptor: " + duplicate)

    root = io.safe(candidate_root)
    expected_sidecars = {root / path for path in expected_files}
    sidecar_dir = root / "Analysis/Readback/TextMetrics"
    actual_sidecars = set(sidecar_dir.glob("*.json")) if sidecar_dir.is_dir() else set()
    if actual_sidecars != expected_sidecars:
        issue("STATIC_TEXT_SIDECAR_DIRECTORY_SET_MISMATCH",
              message="Text sidecar directory contains missing or unbound JSON files")
    proofs = []
    for relative, prefab_id in expected_files.items():
        groups_for_prefab = by_prefab[prefab_id]
        descriptor = descriptor_by_path.get(relative)
        if not isinstance(descriptor, dict):
            issue("STATIC_TEXT_READBACK_SIDECAR_MISSING", groups_for_prefab[0].get("sourceLabelId"),
                  "No main-readback-bound text sidecar exists for this prefab", relative)
            continue
        expected_sha = descriptor.get("sha256")
        if not isinstance(expected_sha, str) or not _SHA256.fullmatch(expected_sha):
            issue("STATIC_TEXT_READBACK_SIDECAR_PIN_INVALID", groups_for_prefab[0].get("sourceLabelId"),
                  "Sidecar descriptor does not contain a lowercase SHA-256", relative)
            continue
        try:
            sidecar = io.inside(root, relative)
            raw = io.read(sidecar, max_bytes=16 * 1024 * 1024)
            if _sha(raw) != expected_sha:
                issue("STATIC_TEXT_READBACK_SIDECAR_BYTES_CHANGED", groups_for_prefab[0].get("sourceLabelId"),
                      "Sidecar bytes differ from the main readback pin", relative)
                continue
            report = io.load(raw, max_nodes=500_000)
        except Exception as error:
            issue("STATIC_TEXT_READBACK_SIDECAR_UNREADABLE", groups_for_prefab[0].get("sourceLabelId"), str(error), relative)
            continue
        if (not isinstance(report, dict) or report.get("contract") != "monkey-static-text-metrics-readback/1" or
                report.get("phase") != "saved-prefab-reopen" or report.get("sourcePrefabId") != prefab_id or
                report.get("sourceManifestSha256") != plan.get("sourceManifestSha256") or
                report.get("continuationJsonSha256") != config_sha):
            issue("STATIC_TEXT_READBACK_ENVELOPE_MISMATCH", groups_for_prefab[0].get("sourceLabelId"),
                  "Sidecar contract, prefab, manifest, or configuration pin differs", relative)
            continue
        actual_rows = report.get("components")
        if not isinstance(actual_rows, list):
            issue("STATIC_TEXT_READBACK_COMPONENTS_MISSING", groups_for_prefab[0].get("sourceLabelId"),
                  "Sidecar has no component rows", relative)
            continue
        by_label = {}
        for row in actual_rows:
            if isinstance(row, dict) and isinstance(row.get("sourceLabelId"), str):
                by_label.setdefault(row["sourceLabelId"], []).append(row)
        expected_ids = {group["sourceLabelId"] for group in groups_for_prefab}
        if set(by_label) != expected_ids:
            issue("STATIC_TEXT_READBACK_COMPONENT_SET_MISMATCH", groups_for_prefab[0].get("sourceLabelId"),
                  "Saved-prefab rows do not exactly cover the source Label IDs", relative)
        for group in groups_for_prefab:
            sid = group["sourceLabelId"]
            rows = by_label.get(sid, [])
            if len(rows) != 1:
                issue("STATIC_TEXT_READBACK_COMPONENT_NOT_UNIQUE", sid,
                      "Expected exactly one saved text row", relative)
                continue
            row = rows[0]
            font_binding = group.get("nativeFontBinding") if isinstance(group.get("nativeFontBinding"), dict) else {}
            expected_font = font_binding.get("binding") if isinstance(font_binding.get("binding"), dict) else {}
            expected_paths = font_binding.get("assetPaths", [])
            if not isinstance(expected_paths, list):
                expected_paths = []
            glyph_rows = row.get("glyphFontAssets") if isinstance(row.get("glyphFontAssets"), list) else []
            glyph_paths = {item.get("assetPath") for item in glyph_rows if isinstance(item, dict)}
            actual_path = row.get("nativeFontAssetPath")
            expected_primary_path = expected_font.get("nativeFontAssetPath") or (expected_paths[0] if expected_paths else None)
            expected_style_bits = 0 if group.get("fontKind") == "bitmap-font" else (
                (1 if group.get("sourceBold") else 0) |
                (2 if group.get("sourceItalic") else 0) |
                (4 if group.get("sourceUnderline") else 0))
            expected_overflow = 2 if group.get("sourceOverflow") == 1 else 0
            expected_wrapping = 0 if group.get("sourceWrap") is True and group.get("sourceOverflow") != 0 else 1
            def file_id_valid(value):
                return type(value) is int and value != 0 and -(1 << 63) <= value < (1 << 63)
            configured=row.get('configuredFontAssets')
            configured_valid=(isinstance(configured,list)and len(configured)==len(expected_paths)
                and all(isinstance(item,dict)and item.get('assetPath')==path
                    and isinstance(item.get('guid'),str)and _GUID.fullmatch(item['guid'])
                    and file_id_valid(item.get('localFileId'))for item,path in zip(configured,expected_paths)))
            expected_line_spacing = None
            point_size = row.get("nativeFontPointSize")
            face_line_height = row.get("nativeFaceLineHeight")
            if (_number(point_size) and float(point_size) > 0 and _number(face_line_height) and
                    _number(group.get("sourceFontSize")) and float(group["sourceFontSize"]) > 0 and
                    _number(group.get("sourceLineHeight"))):
                expected_line_spacing = (float(group["sourceLineHeight"]) - float(face_line_height) *
                    float(group["sourceFontSize"]) / float(point_size)) * 100.0 / float(group["sourceFontSize"])
            auto_size_expected = group.get("layoutPolicy", {}).get("targetAutoSizing") is True
            font_size = row.get("actualFontSize")
            font_size_bounds_ok = (_number(font_size) and
                (not auto_size_expected or _number(row.get("nativeFontSizeMin")) and _number(row.get("nativeFontSizeMax")) and
                 float(row["nativeFontSizeMin"]) <= float(font_size) <= float(row["nativeFontSizeMax"])) and
                (auto_size_expected or abs(float(font_size) - float(group["sourceFontSize"])) <= 0.01))
            checks = {
                "sourceOutlineIdentity": row.get("sourceOutlineId") == group["sourceOutlineId"],
                "sourceNodeIdentity": row.get("sourceNodeId") == group["sourceNodeId"],
                "persistentLabelIdentity": row.get("persistentLabel") is True and isinstance(row.get("labelGuid"), str) and bool(_GUID.fullmatch(row["labelGuid"])) and file_id_valid(row.get("labelLocalFileId")),
                "sourceText": row.get("sourceTextMatches") is True and row.get("nativeText") == group.get("sourceText") and row.get("sourceTextSha256") == group.get("sourceTextSha256") and row.get("nativeTextSha256") == group.get("sourceTextSha256"),
                "sourceStyle": row.get("sourceStyleMatches") is True and type(row.get("nativeFontStyle")) is int and row.get("nativeFontStyle") == expected_style_bits,
                "overflowAndWrap": row.get("nativeOverflowMode") == expected_overflow and row.get("nativeWrappingMode") == expected_wrapping,
                "autosizing": row.get("autoSizingConfigVerified") is True and font_size_bounds_ok and
                    (not auto_size_expected or abs(float(row["nativeFontSizeMin"]) - float(group["layoutPolicy"]["targetAutoSizeMin"])) <= 0.001 and
                     abs(float(row["nativeFontSizeMax"]) - float(group["layoutPolicy"]["targetAutoSizeMax"])) <= 0.001),
                "primaryFontBinding": row.get("fontBindingVerified") is True and isinstance(actual_path, str) and actual_path == expected_primary_path,
                "persistentFontIdentity": isinstance(row.get("fontGuid"), str) and bool(_GUID.fullmatch(row["fontGuid"])) and
                    file_id_valid(row.get("fontLocalFileId")),
                "glyphFallbackChain": row.get("glyphFontChainVerified") is True and configured_valid and bool(glyph_rows) and
                    all(isinstance(path, str) and path in expected_paths for path in glyph_paths) and expected_primary_path in expected_paths,
                "lineHeight": row.get("lineHeightConfigVerified") is True and expected_line_spacing is not None and
                    _number(row.get("nativeLineSpacing")) and abs(float(row["nativeLineSpacing"]) - expected_line_spacing) <= 0.001,
                "nativeMeshMetrics": row.get("nativeMeshMeasured") is True and isinstance(row.get("inkBounds"), dict)
                    and row.get('nativeBoundsKind')=='tmp-character-quad-local-bounds-not-pixel-ink',
            }
            if group.get("fontKind") != "bitmap-font":
                checks["outlineIdentity"] = (not group.get("sourceOutlineEnabled") or
                    row.get("persistentOutline") is True and row.get("outlineNativeType") == "NativeStaticTextOutline" and isinstance(row.get("outlineGuid"), str) and
                    bool(_GUID.fullmatch(row["outlineGuid"])) and
                    file_id_valid(row.get("outlineLocalFileId")))
                checks["outlineConfiguration"] = row.get("outlineConfigVerified") is True
                checks["outlineMaterial"] = (not group.get("sourceOutlineEnabled") or row.get("outlineMaterialReadbackVerified") is True)
            failed = [name for name, passed in checks.items() if not passed]
            if failed:
                for name in failed:
                    issue("STATIC_TEXT_NATIVE_METRIC_OR_IDENTITY_UNVERIFIED", sid,
                          "Saved-prefab evidence did not verify " + name, relative)
                proof = {"sourceLabelId": sid, "sourceOutlineId": group["sourceOutlineId"],
                               "sourceNodeId": group["sourceNodeId"], "status": "partial",
                               "verifiedChecks": [name for name, passed in checks.items() if passed],
                               "missingChecks": failed, "sourceCanvasMetric": "unknown",
                               "sourceFontPlatform": "unknown", "sourceRasterization": "unknown",
                               "visualEquivalent": False,
                               "verified": False, "scope": "saved-native-text-configuration-and-metrics",
                               "evidence": {"sidecar": relative, "checks": [name for name, passed in checks.items() if passed]},
                               "resolvedCodes": [], "unresolvedCodes": ["LABEL_METRICS_NOT_VERIFIED"]}
            else:
                proof = {"sourceLabelId": sid, "sourceOutlineId": group["sourceOutlineId"],
                               "sourceNodeId": group["sourceNodeId"], "status": "native-configuration-metrics-verified",
                               "verifiedChecks": list(checks), "missingChecks": [],
                               "sourceCanvasMetric": "unknown", "sourceFontPlatform": "unknown",
                               "sourceRasterization": "unknown", "visualEquivalent": False,
                               "verified": True, "scope": "saved-native-text-configuration-and-metrics",
                               "evidence": {"sidecar": relative, "checks": list(checks)},
                               "resolvedCodes": [], "unresolvedCodes": ["LABEL_METRICS_NOT_VERIFIED"]}
                if group.get("sourceOutlineId"):
                    proof["outlineProof"] = {"sourceId": group["sourceOutlineId"],
                        "guid": row.get("outlineGuid"), "localFileId": row.get("outlineLocalFileId"),
                        "sameNodeLabel": checks["sourceOutlineIdentity"] and checks["sourceNodeIdentity"],
                        "persistentIdentity": checks.get("outlineIdentity", False),
                        "materialReadback": checks.get("outlineMaterial", False),
                        "verified": checks.get("outlineIdentity", False) and checks.get("outlineConfiguration", False) and checks.get("outlineMaterial", False),
                        "status": "verified-native-outline-identity-and-material" if checks.get("outlineIdentity", False) and checks.get("outlineConfiguration", False) and checks.get("outlineMaterial", False) else "partial",
                        "scope": "same-node-label-outline-identity-and-material-readback",
                        "nativeType": row.get("outlineNativeType"), "representation": "native-component",
                        "persistent": checks.get("outlineIdentity", False),
                        "sourceIdentityVerified": checks.get("sourceOutlineIdentity", False) and checks.get("sourceNodeIdentity", False),
                        "requirements": {"same-node-label": checks.get("sourceOutlineIdentity", False) and checks.get("sourceNodeIdentity", False)},
                        "resolvedCodes": (["MISSING_OUTLINE_LABEL"] if
                            checks.get("outlineIdentity", False) and checks.get("outlineConfiguration", False) and checks.get("sourceOutlineIdentity", False) and checks.get("sourceNodeIdentity", False) else []),
                        "unresolvedCodes": (["OUTLINE_METRICS_NOT_VERIFIED"] if
                            checks.get("outlineIdentity", False) and checks.get("outlineConfiguration", False) and checks.get("sourceOutlineIdentity", False) and checks.get("sourceNodeIdentity", False)
                            else ["MISSING_OUTLINE_LABEL", "OUTLINE_METRICS_NOT_VERIFIED"])}
            proofs.append(proof)
    proof_map = {}
    for proof in proofs:
        proof_map[proof["sourceLabelId"]] = proof
        outline_proof = proof.get("outlineProof")
        if isinstance(outline_proof, dict):
            outline_proof['evidence']={key:deepcopy(outline_proof[key])for key in (
                'sourceId','guid','localFileId','nativeType','representation','persistent','sourceIdentityVerified','requirements')}
            proof_map[outline_proof["sourceId"]] = outline_proof
    status = "verified-native-configuration-only" if proofs and not diagnostics and not fragment.get("gaps") and all(
        proof["status"] == "native-configuration-metrics-verified" for proof in proofs) else "partial"
    return {"status": status, "diagnostics": diagnostics, "family_proofs": proof_map,
            "gaps": deepcopy(fragment.get("gaps", [])), "sourceCanvasMetric": "unknown",
            "sourceFontPlatform": "unknown", "sourceRasterization": "unknown", "visualEquivalent": False}
