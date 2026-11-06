"""Bounded static projection of serialized Cocos Creator 2.4 cc.RichText.

This adapter consumes only the serialized component fields. It never imports,
parses, or invokes a component script. Unknown rich-text tags fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import html
import re
from typing import Any


SCHEMA = "monkey-static-richtext/1"
_COLOR_NAMES = {
    "black": "000000", "blue": "0000ff", "cyan": "00ffff",
    "gray": "808080", "grey": "808080", "green": "008000",
    "magenta": "ff00ff", "red": "ff0000", "white": "ffffff",
    "yellow": "ffff00",
}
_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


@dataclass
class _ParseResult:
    unity_markup: str
    creator_markup: str
    plain_text: str
    errors: list[str]


def _parse_markup(value: str) -> _ParseResult:
    output: list[str] = []
    plain: list[str] = []
    errors: list[str] = []
    stack: list[str] = []
    token_re = re.compile(r"(<[^<>]*>)")
    for part in token_re.split(value):
        if not part:
            continue
        if not part.startswith("<") or not part.endswith(">"):
            decoded = html.unescape(part)
            if "<" in part:
                errors.append("malformed or unterminated rich-text tag")
            output.append(decoded.replace("<", "&lt;"))
            plain.append(decoded)
            continue
        token = part[1:-1].strip()
        if token.startswith("/"):
            closing = token[1:].strip().lower()
            if not stack:
                errors.append(f"unmatched rich-text closing tag: </{closing}>")
                continue
            expected = stack[-1]
            # Creator 2.4 HTMLTextParser closes by popping its style stack on any
            # </...> token; source assets use </c> as the color close shorthand.
            # Normalize only the evidenced color shorthand and keep other
            # mismatched closures fail-closed in this static adapter.
            if closing == "c" and expected == "color":
                closing = expected
            if closing not in ("", expected):
                errors.append(f"rich-text tag nesting mismatch: expected </{expected}>, got </{closing}>")
                continue
            stack.pop()
            output.append(f"</{expected}>")
            continue
        if re.fullmatch(r"br\s*/", token):
            output.append("\n")
            plain.append("\n")
            continue
        if token in ("b", "i", "u"):
            output.append(f"<{token}>")
            stack.append(token)
            continue
        match = re.fullmatch(r"(color|size)\s*=\s*(['\"]?)([^\s>'\"]+)\2", token)
        if match:
            tag, _, value_part = match.groups()
            if tag == "color":
                color = value_part.lower()
                if color in _COLOR_NAMES:
                    color = _COLOR_NAMES[color]
                elif _HEX.fullmatch(color):
                    color = color[1:]
                    if len(color) == 3:
                        color = "".join(ch * 2 for ch in color)
                else:
                    errors.append(f"unsupported color value: {value_part}")
                    continue
                output.append(f"<color=#{color}>")
                stack.append("color")
            else:
                if not value_part.isdecimal() or int(value_part) <= 0:
                    errors.append(f"size must be a positive integer: {value_part}")
                    continue
                output.append(f"<size={int(value_part)}>")
                stack.append("size")
            continue
        tag = token.split(None, 1)[0].split("=", 1)[0].rstrip("/").lower()
        errors.append(f"unsupported static rich-text tag: <{tag}>")
    if stack:
        errors.append("unclosed rich-text tags: " + ",".join(stack))
    markup = "".join(output)
    return _ParseResult(markup, markup, "".join(plain), errors)


def convert_static_richtext(
    source: dict[str, Any], *, source_id: str, node_id: str | None = None,
    font_binding: dict[str, Any] | None = None,
    text_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a target-neutral static descriptor for one serialized RichText.

    The recognized Cocos 2.4 fields are `_N$string`, `_N$fontSize`,
    `_N$lineHeight`, `_N$maxWidth`, `_N$horizontalAlign` and
    `_N$verticalAlign`. An absent family is recorded as Creator's Arial
    provenance only; this adapter never selects Arial as a target font.
    Rendering needs explicit static font binding and glyph coverage evidence.
    `img`, `on`, `outline`, and other tags are reported as gaps; no image
    lookup or callback binding is attempted.
    """
    if source.get("__type__") != "cc.RichText":
        return {"schema": SCHEMA, "sourceId": source_id, "status": "needs_action",
                "convertible": False, "gaps": ["source component is not cc.RichText"]}
    serialized_text = source.get("_N$string", "")
    text = serialized_text
    font_size = source.get("_N$fontSize", 40)
    line_height = source.get("_N$lineHeight", 40)
    max_width = source.get("_N$maxWidth", 0)
    horizontal = source.get("_N$horizontalAlign", 0)
    vertical = source.get("_N$verticalAlign", 0)
    state_properties: dict[str, Any] = {}
    errors: list[str] = []
    text_evidence = {"kind": "serialized-component", "sourceId": source_id, "field": "_N$string"}
    if text_override is not None:
        required_evidence = ("text", "sourceId", "sourceSha256", "field", "evidenceType")
        if any(key not in text_override for key in required_evidence):
            errors.append("text override requires text, sourceId, sourceSha256, field, and evidenceType provenance")
        elif (not isinstance(text_override["text"], str) or not text_override["text"] or
              not isinstance(text_override["sourceId"], str) or not text_override["sourceId"] or
              not isinstance(text_override["sourceSha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", text_override["sourceSha256"]) or
              not isinstance(text_override["field"], str) or not text_override["field"] or
              text_override["evidenceType"] != "frozen-static-preview-state"):
            errors.append("text override provenance is invalid or is not a frozen static preview state")
        else:
            text = text_override["text"]
            text_evidence = {key: text_override[key] for key in required_evidence}
            properties = text_override.get("componentProperties", {})
            if not isinstance(properties, dict) or set(properties) - {
                "fontSize", "lineHeight", "maxWidth", "horizontalAlign", "verticalAlign",
            }:
                errors.append("static state componentProperties contain unsupported fields")
            else:
                for key, value in properties.items():
                    if key in ("fontSize", "lineHeight") and (
                        not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0
                    ):
                        errors.append(f"static state {key} must be a positive number")
                    elif key == "maxWidth" and (
                        not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
                    ):
                        errors.append("static state maxWidth must be a nonnegative number")
                    elif key in ("horizontalAlign", "verticalAlign") and (
                        value not in (0, 1, 2) or isinstance(value, bool)
                    ):
                        errors.append(f"static state {key} is outside the supported 0..2 enum")
                    else:
                        state_properties[key] = value
                font_size = state_properties.get("fontSize", font_size)
                line_height = state_properties.get("lineHeight", line_height)
                max_width = state_properties.get("maxWidth", max_width)
                horizontal = state_properties.get("horizontalAlign", horizontal)
                vertical = state_properties.get("verticalAlign", vertical)
    if not isinstance(text, str):
        errors.append("serialized RichText string is not text")
        text = ""
    parsed = _parse_markup(text)
    errors.extend(parsed.errors)
    if not isinstance(font_size, (int, float)) or isinstance(font_size, bool) or font_size <= 0:
        errors.append("fontSize must be a positive number")
    if not isinstance(line_height, (int, float)) or isinstance(line_height, bool) or line_height <= 0:
        errors.append("lineHeight must be a positive number")
    if not isinstance(max_width, (int, float)) or isinstance(max_width, bool) or max_width < 0:
        errors.append("maxWidth must be a nonnegative number")
    if horizontal not in (0, 1, 2) or isinstance(horizontal, bool):
        errors.append("horizontalAlign must be 0(left), 1(center), or 2(right)")
    if vertical not in (0, 1, 2) or isinstance(vertical, bool):
        errors.append("verticalAlign must be 0(top), 1(middle), or 2(bottom)")
    family = source.get("_N$fontFamily", source.get("fontFamily"))
    family_evidence = "serialized" if family is not None else "creator-label-default-Arial-provenance-only"
    if family is None:
        family = "Arial"
    if not isinstance(family, str) or not family.strip():
        errors.append("fontFamily must be a nonempty string")
        family = "Arial"
    binding = None
    font_binding_gap = None
    if font_binding is None:
        font_binding_gap = "explicit static native font binding and glyph coverage evidence are required; source Arial is provenance only"
    else:
        primary = font_binding.get("nativeFontAssetId")
        fallbacks = font_binding.get("nativeFallbackAssetIds", [])
        covered = font_binding.get("coveredUnicode")
        coverage_evidence = font_binding.get("coverageEvidence")
        evidence_ok = (
            isinstance(coverage_evidence, dict)
            and all(isinstance(coverage_evidence.get(key), str) and
                    re.fullmatch(r"[0-9a-f]{64}", coverage_evidence[key])
                    for key in ("metricsSha256", "receiptSha256"))
            and isinstance(coverage_evidence.get("metricsPath"), str)
            and isinstance(coverage_evidence.get("receiptPath"), str)
        )
        if not isinstance(primary, str) or not primary or not isinstance(fallbacks, list):
            font_binding_gap = "font binding must name a native primary and fallback asset list"
        elif not isinstance(covered, list) or not evidence_ok:
            font_binding_gap = "font binding lacks measured coveredUnicode evidence"
        else:
            required = sorted({ord(ch) for ch in parsed.plain_text if ch not in "\r\n\t"})
            covered_scalars = {value for value in covered if isinstance(value, int) and not isinstance(value, bool)}
            absent = sorted(set(required) - covered_scalars)
            if absent:
                font_binding_gap = "static font coverage missing Unicode scalars: " + ",".join(f"U+{cp:04X}" for cp in absent)
            else:
                binding = {
                    "nativeFontAssetId": primary,
                    "nativeFallbackAssetIds": fallbacks,
                    "requiredUnicode": required,
                    "targetSystemFontFamily": font_binding.get("targetSystemFontFamily"),
                    "coverageEvidence": coverage_evidence,
                }
    if font_binding_gap:
        errors.append(font_binding_gap)
    descriptor = {
        "schema": SCHEMA,
        "sourceId": source_id,
        "node": node_id if node_id is not None else source.get("node"),
        "status": "static_content_needs_font_binding" if font_binding_gap and not parsed.errors else "needs_action" if errors else "static",
        "convertible": not errors,
        "contentConvertible": not parsed.errors,
        "renderReady": not errors,
        "componentEnabled": source.get("_enabled", True),
        "text": text,
        "serializedSourceText": serialized_text,
        "textEvidence": text_evidence,
        "stateComponentProperties": state_properties,
        "plainText": parsed.plain_text,
        "unityMarkup": parsed.unity_markup,
        "creatorMarkup": parsed.creator_markup,
        "sourceFontFamily": family,
        "sourceFontFamilyEvidence": family_evidence,
        "fontBinding": binding,
        "fontSize": font_size,
        "lineHeight": line_height,
        "maxWidth": max_width,
        "horizontalAlign": horizontal,
        "verticalAlign": vertical,
        "wrap": max_width > 0,
        "richText": True,
        "staticOnly": True,
        "dynamicScriptExecuted": False,
        "gaps": errors,
    }
    return descriptor
