"""Create a new static TMP fallback candidate from a pinned consumer text corpus.

The base binding, atlas, metrics, and source font are read-only inputs. Output is
written to a new directory; system font bytes are inspected by CoreText but are
never copied or exported. Unity Editor import/save remains a separate step.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Mapping

from PIL import Image, ImageChops

from .prefab_font_binding import resolve_macos_system_font_runs
from .prefab_system_fonts import prepare_static_inputs


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_STATIC_SCHEMA = "monkey-unity-coretext-static-sdf-plan/1"


class NativeFontCompletionError(ValueError):
    """Pinned input or exact-face evidence does not support this completion."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_pinned_json(path: str | Path, expected_sha256: str, label: str) -> tuple[dict[str, Any], bytes]:
    if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
        raise NativeFontCompletionError(f"{label} expected SHA-256 is malformed")
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise NativeFontCompletionError(f"{label} must be a regular, non-symlink file")
    raw = source.read_bytes()
    if _sha(raw) != expected_sha256:
        raise NativeFontCompletionError(f"{label} SHA-256 differs from its supplied pin")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeFontCompletionError(f"{label} is not UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise NativeFontCompletionError(f"{label} root must be an object")
    return value, raw


def _write_json(path: Path, value: Any) -> str:
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return _sha(raw)


def _unicode_rows(strings: list[str]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for text in strings:
        for char in text:
            scalar = ord(char)
            if 0xD800 <= scalar <= 0xDFFF:
                raise NativeFontCompletionError("corpus contains a surrogate, not a Unicode scalar")
            result[scalar] = {"unicode": scalar, "codepoint": f"U+{scalar:04X}", "character": char}
    return dict(sorted(result.items()))


def _exact_face_resolution(record: Mapping[str, Any], face: Mapping[str, Any], requested_family: str,
                           requested_style: str) -> None:
    expected_primary = {
        "family": requested_family,
        "styleName": requested_style,
    }
    primaries = record.get("resolvedPrimaryFonts") or []
    primary_files = {row.get("path"): row for row in record.get("resolvedFontFiles") or []
                     if isinstance(row, Mapping)}
    base_primary_faces = face.get("_basePrimaryFaces") or []
    if not any(
        row.get("family") == expected_primary["family"] and row.get("styleName") == expected_primary["styleName"]
        and any(row.get("postScriptName") == base.get("targetPostScriptName")
                and row.get("variationAxes", {}) == json.loads(base.get("targetVariationAxesJson") or "{}")
                and primary_files.get(row.get("systemFontFileUrl"), {}).get("fileSha256") == base.get("targetSystemFontFileSha256")
                for base in base_primary_faces)
        for row in primaries if isinstance(row, Mapping)
    ):
        raise NativeFontCompletionError("consumer corpus did not resolve the pinned primary family/style")

    wanted = {
        "family": face.get("targetFamily"),
        "styleName": face.get("targetStyleName"),
        "postScriptName": face.get("targetPostScriptName"),
        "systemFontFileUrl": face.get("targetSystemFontFileUrl"),
        "variationAxes": face.get("targetVariationAxes", {}),
    }
    files = {row.get("path"): row for row in record.get("resolvedFontFiles") or [] if isinstance(row, Mapping)}
    matched = []
    for row in record.get("fallbackFonts") or []:
        if not isinstance(row, Mapping):
            continue
        identity = {key: row.get(key) for key in wanted}
        file_row = files.get(row.get("systemFontFileUrl"), {})
        if identity == wanted and file_row.get("fileSha256") == face.get("targetSystemFontFileSha256"):
            matched.append(row)
    if not matched:
        raise NativeFontCompletionError("consumer corpus fallback face/file/variation differs from the pinned static asset")
    physical = record.get("coreTextToPhysicalFaceEvidence") or []
    if not any(row.get("family") == wanted["family"] and row.get("styleName") == wanted["styleName"]
               and row.get("postScriptName") == wanted["postScriptName"]
               and row.get("systemFontFileUrl") == wanted["systemFontFileUrl"]
               and row.get("exactPostScriptFaceCount") == 0
               for row in physical if isinstance(row, Mapping)):
        raise NativeFontCompletionError("consumer fallback face lacks the pinned static-SDF physical-face evidence")


def _merge_font_plan(base_plan: dict[str, Any], face: Mapping[str, Any], glyph_rows: list[dict[str, Any]],
                     corpus_sha256: str, corpus_source_sha256: str, resolution_sha256: str) -> dict[str, Any]:
    result = deepcopy(base_plan)
    if result.get("schema") != _STATIC_SCHEMA or result.get("status") != "prepared":
        raise NativeFontCompletionError("base static font plan is not a prepared CoreText SDF plan")
    faces = result.get("systemFonts")
    if not isinstance(faces, list) or len(faces) != 1:
        raise NativeFontCompletionError("base static plan must contain exactly one bounded fallback face")
    base_face = faces[0]
    for key in ("assetId", "assetPath", "targetFamily", "targetStyleName", "targetPostScriptName",
                "targetSystemFontFileSha256", "targetVariationAxes", "targetSystemFontFileUrl"):
        if base_face.get(key) != face.get(key):
            raise NativeFontCompletionError(f"base static plan and saved binding differ at {key}")
    old_by_unicode = {row.get("unicode"): row for row in base_face.get("requiredGlyphs") or []
                      if isinstance(row, Mapping)}
    merged = dict(old_by_unicode)
    for row in glyph_rows:
        code = row["unicode"]
        prior = merged.get(code)
        if prior is not None and prior.get("character") != row.get("character"):
            raise NativeFontCompletionError(f"existing glyph identity conflicts at U+{code:04X}")
        merged.setdefault(code, row)
    base_face["requiredGlyphs"] = [merged[code] for code in sorted(merged)]
    base_face["requiredUnicode"] = sorted(merged)
    base_face["sourceLabelIds"] = sorted(set(base_face.get("sourceLabelIds") or []))
    if isinstance(base_face.get("atlasContract"), dict):
        base_face["atlasContract"]["allowedCodepoints"] = sorted(merged)
    result["resolutionReceiptSha256"] = face.get("resolutionReceiptSha256", result.get("resolutionReceiptSha256"))
    result["consumerCorpus"] = {
        "schema": "monkey-consumer-text-corpus/1",
        "corpusSha256": corpus_sha256,
        "sourceSha256": corpus_source_sha256,
        "resolutionReceiptSha256": resolution_sha256,
        "addedCodepoints": [row["codepoint"] for row in glyph_rows],
        "scope": "explicit consumer text scalars routed through this exact saved fallback face",
    }
    result["newCharacterBoundary"] = (
        "the prior static glyph set plus the explicitly pinned consumer corpus; all other runtime, localized, "
        "or user-generated text remains unverified"
    )
    return result


def _append_glyphs(base_atlas_path: Path, base_metrics: Mapping[str, Any], fresh_atlas_path: Path,
                   fresh_metrics: Mapping[str, Any], output_atlas_path: Path,
                   expected_new: set[int]) -> tuple[dict[str, Any], dict[str, Any]]:
    old_image = Image.open(base_atlas_path).convert("RGBA")
    fresh_image = Image.open(fresh_atlas_path).convert("RGBA")
    if old_image.size != fresh_image.size or old_image.size != (base_metrics.get("atlasWidth"), base_metrics.get("atlasHeight")):
        raise NativeFontCompletionError("fresh generator atlas dimensions differ from the pinned base atlas")
    old_rows = base_metrics.get("glyphs")
    fresh_rows = fresh_metrics.get("glyphs")
    if not isinstance(old_rows, list) or not isinstance(fresh_rows, list):
        raise NativeFontCompletionError("base or generated glyph metrics are missing")
    old_by_code = {row.get("unicode"): row for row in old_rows if isinstance(row, dict)}
    fresh_by_code = {row.get("unicode"): row for row in fresh_rows if isinstance(row, dict)}
    if len(old_by_code) != len(old_rows) or set(old_by_code) - set(fresh_by_code):
        raise NativeFontCompletionError("fresh generator output lost or duplicated an existing base glyph")
    if set(fresh_by_code) - set(old_by_code) != expected_new:
        raise NativeFontCompletionError("fresh glyph output does not equal the pinned missing corpus scalar set")
    for code, old in old_by_code.items():
        fresh = fresh_by_code[code]
        if {k: v for k, v in old.items() if k != "rect"} != {k: v for k, v in fresh.items() if k != "rect"}:
            raise NativeFontCompletionError(f"CoreText metrics changed for preserved U+{code:04X}")
        old_rect, new_rect = old.get("rect"), fresh.get("rect")
        if not isinstance(old_rect, Mapping) or not isinstance(new_rect, Mapping):
            raise NativeFontCompletionError(f"glyph rectangle missing at U+{code:04X}")
        old_box = (old_rect["x"], old_rect["y"], old_rect["x"] + old_rect["width"], old_rect["y"] + old_rect["height"])
        new_box = (new_rect["x"], new_rect["y"], new_rect["x"] + new_rect["width"], new_rect["y"] + new_rect["height"])
        if ImageChops.difference(old_image.crop(old_box), fresh_image.crop(new_box)).getbbox() is not None:
            raise NativeFontCompletionError(f"CoreText pixels changed for preserved U+{code:04X}")

    final_image = old_image.copy()
    draw_x = 0
    draw_y = max((row["rect"]["y"] + row["rect"]["height"] for row in old_rows), default=0) + 1
    row_h = 0
    added_rows: list[dict[str, Any]] = []
    for code in sorted(expected_new, key=lambda cp: (-fresh_by_code[cp]["rect"]["height"], cp)):
        row = deepcopy(fresh_by_code[code])
        rect = row["rect"]
        width, height = rect["width"], rect["height"]
        if draw_x + width > final_image.width:
            draw_x, draw_y, row_h = 0, draw_y + row_h + 1, 0
        if draw_y + height > final_image.height:
            raise NativeFontCompletionError("new glyphs do not fit in the existing atlas; a new atlas geometry is required")
        box = (draw_x, draw_y, draw_x + width, draw_y + height)
        if final_image.crop(box).getbbox() is not None:
            raise NativeFontCompletionError("new glyph placement overlaps non-empty base atlas pixels")
        source_rect = fresh_by_code[code]["rect"]
        crop = (source_rect["x"], source_rect["y"], source_rect["x"] + width, source_rect["y"] + height)
        final_image.paste(fresh_image.crop(crop), (draw_x, draw_y))
        row["rect"] = {**rect, "x": draw_x, "y": draw_y}
        added_rows.append(row)
        draw_x += width + 1
        row_h = max(row_h, height)
    final_image.save(output_atlas_path, format="PNG", optimize=False)
    final_image = Image.open(output_atlas_path).convert("RGBA")
    for code, old in old_by_code.items():
        rect = old["rect"]
        box = (rect["x"], rect["y"], rect["x"] + rect["width"], rect["y"] + rect["height"])
        if ImageChops.difference(final_image.crop(box), old_image.crop(box)).getbbox() is not None:
            raise NativeFontCompletionError(f"final atlas changed preserved U+{code:04X}")
    final_metrics = deepcopy(dict(fresh_metrics))
    final_metrics["glyphs"] = sorted([deepcopy(row) for row in old_rows] + added_rows, key=lambda row: row["unicode"])
    final_metrics["requiredGlyphCount"] = len(final_metrics["glyphs"])
    final_metrics["preservedAtlas"] = {
        "baseAtlasSha256": _sha(base_atlas_path.read_bytes()),
        "baseMetricsSha256": _sha(Path(base_metrics["_sourcePath"]).read_bytes()),
        "preservedGlyphCount": len(old_by_code),
        "addedGlyphs": [row["codepoint"] for row in added_rows],
    }
    return final_metrics, {"preservedGlyphCount": len(old_by_code), "addedGlyphCount": len(added_rows)}


def complete_native_font_from_corpus(
    corpus_path: str | Path,
    expected_corpus_sha256: str,
    base_binding_path: str | Path,
    expected_base_binding_sha256: str,
    base_generation_receipt_path: str | Path,
    expected_base_generation_receipt_sha256: str,
    base_static_plan_path: str | Path,
    expected_base_static_plan_sha256: str,
    generator_path: str | Path,
    output_dir: str | Path,
    *,
    static_font_asset_id: str,
    requested_primary_family: str = "Arial",
    expected_primary_style: str = "Regular",
    watch_files: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Resolve a consumer corpus and append its missing glyphs to a new SDF.

    All four JSON inputs are hash pinned. The selected static font is joined to
    its saved binding, source generation receipt, and CoreText metrics. Output
    is fail-closed and must be a fresh directory. The function never edits the
    base candidate, Unity Editor assets, or system font files.
    """
    corpus, corpus_raw = _read_pinned_json(corpus_path, expected_corpus_sha256, "consumer text corpus")
    binding, binding_raw = _read_pinned_json(base_binding_path, expected_base_binding_sha256, "base font binding")
    base_receipt, base_receipt_raw = _read_pinned_json(
        base_generation_receipt_path, expected_base_generation_receipt_sha256, "base generation receipt")
    base_plan, base_plan_raw = _read_pinned_json(base_static_plan_path, expected_base_static_plan_sha256, "base static plan")
    watched_before: dict[str, str] = {}
    for name, row in (watch_files or {}).items():
        path = Path(row.get("path", "")) if isinstance(row, Mapping) else Path("")
        digest = row.get("sha256") if isinstance(row, Mapping) else None
        if (not isinstance(name, str) or not name or path.is_symlink() or not path.is_file()
                or not isinstance(digest, str) or not _SHA256.fullmatch(digest)):
            raise NativeFontCompletionError("watch_files entries require a named regular file and a lowercase pinned SHA-256")
        actual = _sha(path.read_bytes())
        if actual != digest:
            raise NativeFontCompletionError(f"watched source asset SHA-256 differs from pin: {name}")
        watched_before[name] = actual
    if corpus.get("schemaVersion") != 1 or not isinstance(corpus.get("strings"), list) or not corpus["strings"]:
        raise NativeFontCompletionError("consumer corpus must be a non-empty schemaVersion 1 string list")
    if any(not isinstance(value, str) for value in corpus["strings"]):
        raise NativeFontCompletionError("consumer corpus strings must all be text")
    if sum(map(len, corpus["strings"])) > 250_000 or len(corpus["strings"]) > 1000:
        raise NativeFontCompletionError("consumer corpus exceeds the bounded text budget")
    source_sha = corpus.get("sourceSha256")
    if not isinstance(source_sha, str) or not _SHA256.fullmatch(source_sha):
        raise NativeFontCompletionError("consumer corpus sourceSha256 is missing or malformed")

    system_fonts = binding.get("systemFonts")
    fonts = system_fonts.get("fonts") if isinstance(system_fonts, Mapping) else None
    if not isinstance(fonts, list):
        raise NativeFontCompletionError("base binding does not contain a systemFonts.fonts list")
    selected = [row for row in fonts if isinstance(row, Mapping) and row.get("assetId") == static_font_asset_id]
    if len(selected) != 1 or selected[0].get("populationMode") != "StaticSDFRequired":
        raise NativeFontCompletionError("selected asset ID must identify exactly one saved StaticSDFRequired face")
    face = deepcopy(dict(selected[0]))
    primary_faces = [row for row in fonts if isinstance(row, Mapping) and row.get("role") == "primary"]
    matching_primary = [row for row in primary_faces if row.get("familyName") == requested_primary_family
                       and row.get("styleName") == expected_primary_style]
    if not matching_primary:
        raise NativeFontCompletionError("base binding lacks the requested primary family/style")
    if face.get("fontFileCopiedOrExported") is not False:
        raise NativeFontCompletionError("base static font does not preserve the no-font-copy boundary")

    base_receipt_path = Path(base_generation_receipt_path)
    try:
        base_atlas_path = Path(base_receipt["atlasPath"])
        base_metrics_path = Path(base_receipt["metricsPath"])
        if not base_atlas_path.is_absolute():
            base_atlas_path = base_receipt_path.parent / base_atlas_path
        if not base_metrics_path.is_absolute():
            base_metrics_path = base_receipt_path.parent / base_metrics_path
        base_atlas_raw = base_atlas_path.read_bytes()
        base_metrics_raw = base_metrics_path.read_bytes()
        base_metrics = json.loads(base_metrics_raw.decode("utf-8"))
    except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeFontCompletionError(f"cannot read pinned base atlas/metrics: {exc}") from exc
    if (base_receipt.get("schema") != "monkey-coretext-static-sdf-generation-receipt/1"
            or base_receipt.get("status") != "generated"
            or base_receipt.get("fontFileCopiedOrExported") is not False
            or base_receipt.get("fontFileIncluded") is not False
            or _sha(base_atlas_raw) != base_receipt.get("atlasSha256")
            or _sha(base_metrics_raw) != base_receipt.get("metricsSha256")):
        raise NativeFontCompletionError("base generation receipt does not pin a generated, font-byte-free atlas")
    if not isinstance(base_metrics, dict) or base_metrics.get("schema") != "monkey-coretext-static-sdf-glyph-metrics/1":
        raise NativeFontCompletionError("base glyph metrics use an unsupported schema")
    face_identity = {
        "assetId": face.get("assetId"), "assetPath": face.get("assetPath"),
        "targetFamily": face.get("familyName"), "targetStyleName": face.get("styleName"),
        "targetPostScriptName": face.get("targetPostScriptName"),
        "targetVariationAxes": json.loads(face.get("targetVariationAxesJson") or "{}"),
        "targetVariationAxesJson": face.get("targetVariationAxesJson"),
        "targetSystemFontFileUrl": face.get("targetSystemFontFileUrl"),
        "targetSystemFontFileSha256": face.get("targetSystemFontFileSha256"),
        "sourceLabelIds": sorted(face.get("sourceLabelIds") or []),
        "resolutionReceiptSha256": system_fonts.get("resolutionReceiptSha256"),
    }
    for key in ("family", "styleName", "postScriptName", "fontFileSha256", "variationAxesCanonical"):
        expected = {
            "family": face_identity["targetFamily"], "styleName": face_identity["targetStyleName"],
            "postScriptName": face_identity["targetPostScriptName"],
            "fontFileSha256": face_identity["targetSystemFontFileSha256"],
            "variationAxesCanonical": face_identity["targetVariationAxesJson"],
        }[key]
        if base_metrics.get(key) != expected:
            raise NativeFontCompletionError(f"base metrics do not match selected face identity at {key}")
    if base_metrics.get("generatorSourceSha256") != base_receipt.get("generatorSourceSha256"):
        raise NativeFontCompletionError("base generator identity differs between receipt and glyph metrics")
    if base_receipt.get("planSha256") != expected_base_static_plan_sha256:
        raise NativeFontCompletionError("base generation receipt is not pinned to the supplied static plan")
    if (base_receipt.get("targetOSVersion") != base_metrics.get("targetOSVersion")
            or base_receipt.get("targetOSBuild") != base_metrics.get("targetOSBuild")
            or base_metrics.get("resolutionReceiptSha256") != system_fonts.get("resolutionReceiptSha256")):
        raise NativeFontCompletionError("base receipt, metrics, and binding do not share the same OS/resolution pins")
    base_codes = sorted(row.get("unicode") for row in base_metrics.get("glyphs", []) if isinstance(row, Mapping))
    bound_codes = sorted(face.get("requiredUnicode") or [])
    if (base_codes != bound_codes or len(base_codes) != len(set(base_codes))
            or base_metrics.get("requiredGlyphCount") != len(base_codes)
            or sorted(face_identity["sourceLabelIds"]) != sorted(base_metrics.get("sourceLabelIds") or [])):
        raise NativeFontCompletionError("base binding glyph/source-label set differs from pinned atlas metrics")

    generator = Path(generator_path)
    if generator.is_symlink() or not generator.is_file():
        raise NativeFontCompletionError("CoreText generator must be a regular, non-symlink file")
    generator_sha = _sha(generator.read_bytes())
    if generator_sha != base_metrics.get("generatorSourceSha256"):
        raise NativeFontCompletionError("CoreText generator differs from the generator pinned by the base atlas")

    corpus_glyphs = _unicode_rows(corpus["strings"])
    base_code_set = set(base_codes)

    runs = [{"id": f"consumerCorpus:{expected_corpus_sha256}#text:{index}", "text": text,
             "pointSize": float(face.get("pointSize", 90)), "requestedFamily": requested_primary_family}
            for index, text in enumerate(corpus["strings"])]
    resolved = resolve_macos_system_font_runs(runs, requested_primary_family)
    if resolved.status != "resolved":
        raise NativeFontCompletionError("CoreText consumer-text resolution was not complete: " + str(resolved.record.get("reason") or resolved.record.get("glyphCoverage")))
    face_identity["_basePrimaryFaces"] = [deepcopy(dict(row)) for row in matching_primary]
    _exact_face_resolution(resolved.record, face_identity, requested_primary_family, expected_primary_style)
    if (resolved.record.get("targetOSVersion") != base_receipt.get("targetOSVersion")
            or resolved.record.get("targetOSBuild") != base_receipt.get("targetOSBuild")):
        raise NativeFontCompletionError("CoreText target OS version/build differs from the pinned base atlas")
    consumer_resolution = {
        "schema": "monkey-consumer-text-coretext-resolution/1",
        "status": "resolved",
        "corpusSha256": expected_corpus_sha256,
        "sourceSha256": source_sha,
        "requestedFamily": requested_primary_family,
        "targetOS": resolved.record.get("targetOS"),
        "targetOSVersion": resolved.record.get("targetOSVersion"),
        "targetOSBuild": resolved.record.get("targetOSBuild"),
        "resolutionMethod": "read-only lookup of fonts available to the current macOS process",
        "fontBytesCopiedOrExported": False,
        "resolvedPrimaryFonts": resolved.record.get("resolvedPrimaryFonts", []),
        "fallbackFonts": resolved.record.get("fallbackFonts", []),
        "resolvedFontFiles": resolved.record.get("resolvedFontFiles", []),
        "coreTextToPhysicalFaceEvidence": resolved.record.get("coreTextToPhysicalFaceEvidence", []),
        "glyphCoverage": resolved.record.get("glyphCoverage", {}),
        "labels": resolved.record.get("labels", []),
    }
    resolved_by_code = {row.get("scalarValue"): row for row in resolved.record.get("glyphCoverage", {}).get("perUnicodeScalar", [])
                        if isinstance(row, Mapping)}
    missing_glyphs: list[dict[str, Any]] = []
    primary_file_evidence = {row.get("path"): row for row in resolved.record.get("resolvedFontFiles") or []
                             if isinstance(row, Mapping)}
    for code, glyph in corpus_glyphs.items():
        if code in base_code_set:
            continue
        scalar_row = resolved_by_code.get(glyph["unicode"])
        if not isinstance(scalar_row, Mapping):
            raise NativeFontCompletionError(f"CoreText did not return evidence for {glyph['codepoint']}")
        exact_face = any(
            resolution.get("family") == face_identity["targetFamily"]
            and resolution.get("styleName") == face_identity["targetStyleName"]
            and resolution.get("postScriptName") == face_identity["targetPostScriptName"]
            and resolution.get("systemFontFileUrl") == face_identity["targetSystemFontFileUrl"]
            and resolution.get("variationAxes") == face_identity["targetVariationAxes"]
            and resolution.get("fallback") is True and resolution.get("glyphCovered") is True
            for resolution in scalar_row.get("resolutions", []) if isinstance(resolution, Mapping)
        )
        if exact_face:
            missing_glyphs.append(glyph)
            continue
        exact_primary = any(
            resolution.get("family") == requested_primary_family
            and resolution.get("styleName") == expected_primary_style
            and resolution.get("fallback") is False and resolution.get("glyphCovered") is True
            and any(resolution.get("postScriptName") == base.get("targetPostScriptName")
                    and resolution.get("variationAxes", {}) == json.loads(base.get("targetVariationAxesJson") or "{}")
                    and primary_file_evidence.get(resolution.get("systemFontFileUrl"), {}).get("fileSha256") == base.get("targetSystemFontFileSha256")
                    for base in matching_primary)
            for resolution in scalar_row.get("resolutions", []) if isinstance(resolution, Mapping)
        )
        if not exact_primary:
            raise NativeFontCompletionError(f"{glyph['codepoint']} is not covered by the exact pinned fallback face")
    if not missing_glyphs:
        raise NativeFontCompletionError("pinned consumer corpus has no missing glyphs; no extension candidate is needed")

    destination = Path(output_dir).expanduser().absolute()
    if destination.exists():
        raise NativeFontCompletionError("output directory already exists; choose a new candidate identity")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    try:
        resolution_path = destination / "consumer-corpus-resolution.json"
        resolution_sha = _write_json(resolution_path, consumer_resolution)
        plan = _merge_font_plan(base_plan, face_identity, missing_glyphs, expected_corpus_sha256, source_sha, resolution_sha)
        plan["resolutionReceiptSha256"] = face_identity["resolutionReceiptSha256"]
        plan_path = destination / "static-sdf-plan.json"
        plan_sha = _write_json(plan_path, plan)
        generated_dir = destination / "fresh-coretext-generation"
        proc = subprocess.run([shutil.which("swift") or "swift", str(generator.resolve()), str(plan_path), str(generated_dir)],
                              capture_output=True, text=True, timeout=240, check=False)
        (destination / "coretext-generation.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        if proc.returncode:
            raise NativeFontCompletionError("CoreText SDF generator failed; candidate is incomplete")
        fresh_atlas_path = generated_dir / "glyph-atlas.png"
        fresh_metrics_path = generated_dir / "glyph-metrics.json"
        try:
            fresh_metrics = json.loads(fresh_metrics_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise NativeFontCompletionError(f"CoreText generator did not produce valid metrics: {exc}") from exc
        if (fresh_metrics.get("fontFileSha256") != face_identity["targetSystemFontFileSha256"]
                or fresh_metrics.get("generatorSourceSha256") != generator_sha
                or fresh_metrics.get("variationAxesCanonical") != face_identity["targetVariationAxesJson"]
                or fresh_metrics.get("staticPlanSha256") != plan_sha
                or fresh_metrics.get("resolutionReceiptSha256") != face_identity["resolutionReceiptSha256"]):
            raise NativeFontCompletionError("generated metrics differ from the exact font/plan identity")
        final_atlas_path = destination / "glyph-atlas.png"
        final_metrics, merge_counts = _append_glyphs(
            base_atlas_path, {**base_metrics, "_sourcePath": str(base_metrics_path)},
            fresh_atlas_path, fresh_metrics, final_atlas_path, {row["unicode"] for row in missing_glyphs})
        final_metrics["staticPlanSha256"] = plan_sha
        final_metrics["consumerCorpusSha256"] = expected_corpus_sha256
        final_metrics["consumerResolutionReceiptSha256"] = resolution_sha
        final_metrics["resolutionReceiptSha256"] = face_identity["resolutionReceiptSha256"]
        metrics_path = destination / "glyph-metrics.json"
        metrics_sha = _write_json(metrics_path, final_metrics)
        atlas_sha = _sha(final_atlas_path.read_bytes())
        receipt = {
            "schema": "monkey-coretext-static-sdf-generation-receipt/1", "status": "generated",
            "atlasPath": str(final_atlas_path), "atlasSha256": atlas_sha,
            "metricsPath": str(metrics_path), "metricsSha256": metrics_sha,
            "planSha256": plan_sha, "resolutionReceiptSha256": face_identity["resolutionReceiptSha256"],
            "consumerCorpusSha256": expected_corpus_sha256, "consumerSourceSha256": source_sha,
            "consumerResolutionReceiptSha256": resolution_sha,
            "targetOS": base_receipt["targetOS"], "targetOSVersion": base_receipt["targetOSVersion"],
            "targetOSBuild": base_receipt.get("targetOSBuild"),
            "glyphCount": len(final_metrics["glyphs"]), "sourceLabelCount": len(face_identity["sourceLabelIds"]),
            "fontFileCopiedOrExported": False, "fontFileIncluded": False,
            "editorImport": "not_run", "saveReopenReadback": "not_run", "playerPlatformEvidence": "not_run",
            "visualEquivalent": False, "generatorSourceSha256": generator_sha,
            "preservedBase": {**merge_counts, "baseGenerationReceiptSha256": expected_base_generation_receipt_sha256,
                              "baseBindingSha256": expected_base_binding_sha256,
                              "baseStaticPlanSha256": expected_base_static_plan_sha256,
                              "baseAtlasSha256": _sha(base_atlas_raw), "baseMetricsSha256": _sha(base_metrics_raw)},
        }
        receipt_path = destination / "generation-receipt.json"
        receipt_sha = _write_json(receipt_path, receipt)
        updated_binding = deepcopy(binding)
        target_system = updated_binding["systemFonts"]
        updated_face = next(row for row in target_system["fonts"] if row.get("assetId") == static_font_asset_id)
        updated_face["requiredGlyphs"] = [
            {key: row[key] for key in ("unicode", "codepoint", "character")}
            for row in final_metrics["glyphs"]
        ]
        updated_face["requiredUnicode"] = sorted(row["unicode"] for row in final_metrics["glyphs"])
        target_system["consumerCorpusSha256"] = expected_corpus_sha256
        target_system["consumerCoverageBoundary"] = plan["newCharacterBoundary"]
        binding_path = destination / "unity-static-font-binding.json"
        binding_sha = _write_json(binding_path, updated_binding)
        stage = prepare_static_inputs(receipt_path, receipt_sha, updated_binding, destination / "UnityStage")
        if stage.status != "staged":
            raise NativeFontCompletionError("static input staging rejected generated artifacts: " + str(stage.record.get("reason")))
        stage_path = destination / "staging-report.json"
        stage_sha = _write_json(stage_path, stage.record)

        # Verify that no source files changed while generating the independent output.
        after_hashes = {
            "corpus": _sha(Path(corpus_path).read_bytes()),
            "binding": _sha(Path(base_binding_path).read_bytes()),
            "generationReceipt": _sha(Path(base_generation_receipt_path).read_bytes()),
            "staticPlan": _sha(Path(base_static_plan_path).read_bytes()),
            "atlas": _sha(base_atlas_path.read_bytes()), "metrics": _sha(base_metrics_path.read_bytes()),
            "generator": _sha(generator.read_bytes()),
        }
        watched_after = {name: _sha(Path(row["path"]).read_bytes()) for name, row in (watch_files or {}).items()}
        expected_before = {"corpus": expected_corpus_sha256, "binding": expected_base_binding_sha256,
                           "generationReceipt": expected_base_generation_receipt_sha256,
                           "staticPlan": expected_base_static_plan_sha256,
                           "atlas": base_receipt["atlasSha256"], "metrics": base_receipt["metricsSha256"],
                           "generator": generator_sha}
        if after_hashes != expected_before:
            raise NativeFontCompletionError("a pinned read-only input changed during generation")
        if watched_after != watched_before:
            raise NativeFontCompletionError("a watched consumer font asset changed during candidate preparation")
        result = {
            "schema": "monkey-native-font-completion/1", "status": "prepared",
            "outputDir": str(destination), "corpusSha256": expected_corpus_sha256,
            "sourceSha256": source_sha, "consumerResolutionReceiptSha256": resolution_sha,
            "baseBindingSha256": expected_base_binding_sha256,
            "baseGenerationReceiptSha256": expected_base_generation_receipt_sha256,
            "baseStaticPlanSha256": expected_base_static_plan_sha256,
            "selectedStaticFont": {key: face_identity[key] for key in (
                "assetId", "assetPath", "targetFamily", "targetStyleName", "targetPostScriptName",
                "targetVariationAxesJson", "targetSystemFontFileUrl", "targetSystemFontFileSha256")},
            "primaryFontAssetIdsPreserved": sorted(row.get("assetId") for row in primary_faces),
            "baseGlyphCount": merge_counts["preservedGlyphCount"],
            "addedGlyphs": [row["codepoint"] for row in missing_glyphs],
            "addedGlyphCount": len(missing_glyphs), "generatedGlyphCount": len(final_metrics["glyphs"]),
            "atlasSha256": atlas_sha, "metricsSha256": metrics_sha, "planSha256": plan_sha,
            "generationReceiptSha256": receipt_sha, "bindingSha256": binding_sha,
            "stagingReportSha256": stage_sha,
            "sourceBeforeAfterSha256": {key: {"before": value, "after": after_hashes[key], "unchanged": value == after_hashes[key]}
                                         for key, value in expected_before.items()},
            "watchedFontAssetBeforeAfterSha256": {
                name: {"before": digest, "after": watched_after[name], "unchanged": digest == watched_after[name]}
                for name, digest in watched_before.items()
            },
            "systemFontBytesCopiedOrExported": False,
            "nativeImport": "pending", "saveReopenReadback": "pending", "playerGlyphCheck": "pending",
            "pendingNativeChecks": [
                "import only into a new isolated candidate and record before/after hashes for selected font assets",
                "verify Unity Editor side effects on DynamicOS Arial assets and legacy GameFont separately",
                "save, close, reopen and confirm every corpus glyph through the saved primary/fallback binding",
            ],
            "visualEquivalent": False,
        }
        _write_json(destination / "font-completion.json", result)
        return result
    except Exception:
        # Keep incomplete output evidence for diagnosis, but never touch inputs.
        raise
