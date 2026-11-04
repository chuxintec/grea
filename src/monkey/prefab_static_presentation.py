"""Evidence-gated Unity presentation completion contracts for static Prefabs.

This module deliberately does not edit the shared import plan.  ``prepare``
returns a companion contract that the Unity Editor integration can consume to
reuse its Image, TextMeshProUGUI, material-binding and NativeStaticTextOutline
paths while keeping unsupported source cases explicit.
"""
from __future__ import annotations

import math
from typing import Any

from .shader_profiles import EFFECT_SHA256 as BUILTIN_EFFECT_SHA256
from .shader_profiles import SOURCE_ID as BUILTIN_EFFECT_SOURCE_ID
from .shader_profiles import describe as describe_builtin_sprite_effect


SCHEMA = "monkey-prefab-static-presentation/1"
_UI_COLOR_PROFILE = "cocos24-ui-color-sprite-v1"
_UI_COLOR_PROGRAM_SHA256 = "b4e5e249e052cb9370d4e4995b6d5f2f223e8e9cba447d28d2a2d2d0bf4f9b9d"


def _append_material_binding(plan, manifest, component):
    from .prefab_static_toggle import _resolve_component
    spec=plan['materialBinding']['spec']
    origins={r['instanceSourceId']:r['templateSourceId']for r in plan.get('staticAnimationComponentOrigins',[])}
    source=origins.get(component['sourceId'],component['sourceId'])
    raw,_,owner=_resolve_component(manifest,source,'cc.Sprite')
    refs=raw.get('_materials',[])
    if len(refs)!=1 or not isinstance(refs[0],dict):raise ValueError('STATIC_PRESENTATION_SOURCE_MATERIAL_REFERENCE_INVALID')
    by_id,by_uuid=_source_assets(manifest)
    uuid=refs[0].get('__uuid__');sid=owner.split(':')[0]+':'+str(uuid)
    if _resolve_redirect(sid,by_id)!=spec['materialSourceId']:raise ValueError('STATIC_PRESENTATION_SOURCE_MATERIAL_IDENTITY_DIFFERS')
    if component['sourceId']not in spec['sourceComponentIds']:
        spec['sourceComponentIds'].append(component['sourceId'])
        spec.setdefault('staticCompletionSourceBindings',[]).append(dict(sourceId=component['sourceId'],sourceOriginId=source,
            sourceMaterialId=sid,resolvedMaterialId=spec['materialSourceId'],sourceManifestSha256=plan['sourceManifestSha256']))
    if not any(b['sourceId']==component['sourceId']for b in spec['spriteBindings']):spec['spriteBindings'].append({'sourceId':component['sourceId']})


def _root(asset: dict[str, Any]) -> dict[str, Any] | None:
    doc = asset.get("document")
    if not isinstance(doc, dict):
        return None
    rows, index = doc.get("instances"), doc.get("root")
    if not isinstance(rows, list) or type(index) is not int or not 0 <= index < len(rows):
        return None
    value = rows[index]
    return value if isinstance(value, dict) else None


def _source_assets(manifest: dict[str, Any]) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    by_id: dict[str, dict] = {}
    by_uuid: dict[str, list[dict]] = {}
    for asset in manifest.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        sid = asset.get("sourceId")
        if isinstance(sid, str):
            by_id[sid] = asset
        key = asset.get("key")
        if isinstance(key, str):
            by_uuid.setdefault(key, []).append(asset)
    return by_id, by_uuid


def _resolve_redirect(source_id: str, by_id: dict[str, dict]) -> str:
    seen: set[str] = set()
    current = source_id
    while current not in seen:
        seen.add(current)
        asset = by_id.get(current)
        target = asset.get("redirectTarget") if isinstance(asset, dict) else None
        if not isinstance(target, str) or not target:
            break
        current = target
    return current


def _material_evidence(component: dict, plan: dict, manifest: dict,
                       by_id: dict[str, dict], by_uuid: dict[str, list[dict]]) -> tuple[dict | None, str | None]:
    materials = component.get("materials") or []
    if not isinstance(materials, list) or not materials:
        return None, "source_material_identity_missing"
    if len(materials) != 1 or not isinstance(materials[0], str):
        return None, "multiple_or_invalid_source_materials"
    source_id = materials[0]
    resolved_id = _resolve_redirect(source_id, by_id)
    asset = by_id.get(resolved_id)
    material = _root(asset) if asset else None
    if not isinstance(material, dict) or material.get("__type__") != "cc.Material":
        return None, "source_material_asset_missing:" + source_id

    if (asset.get("bundle") == "internal" and material.get("_name") == "builtin-2d-sprite" and
            material.get("_techniqueData", {}).get("0", {}).get("defines") == {"USE_TEXTURE": True}):
        ref = material.get("_effectAsset")
        effect_uuid = ref.get("__uuid__") if isinstance(ref, dict) else None
        effects = by_uuid.get(effect_uuid, []) if isinstance(effect_uuid, str) else []
        if len(effects) != 1 or effects[0].get("sourceId") != BUILTIN_EFFECT_SOURCE_ID:
            return None, "builtin_sprite_effect_identity_unproven:" + source_id
        effect = _root(effects[0])
        profile = describe_builtin_sprite_effect(effect, effect_sha256=BUILTIN_EFFECT_SHA256)
        if not profile.get("supported"):
            return None, "builtin_sprite_effect_outside_profile:" + source_id
        return {"kind": "unity-default-ui-image-material", "sourceMaterialId": source_id,
                "resolvedMaterialId": resolved_id, "effectSourceId": BUILTIN_EFFECT_SOURCE_ID,
                "profile": profile["profile"]}, None

    binding = plan.get("materialBinding")
    spec = binding.get("spec") if isinstance(binding, dict) else None
    effect_ref = material.get("_effectAsset")
    effect_uuid = effect_ref.get("__uuid__") if isinstance(effect_ref, dict) else None
    effects = by_uuid.get(effect_uuid, []) if isinstance(effect_uuid, str) else []
    if (isinstance(spec, dict) and spec.get("profile") == _UI_COLOR_PROFILE and
            spec.get("materialSourceId") == source_id and
            spec.get("programCanonicalSha256") == _UI_COLOR_PROGRAM_SHA256 and
            material.get("_name") == "shader-2d-uiColor" and
            len(effects) == 1 and effects[0].get("kind") == "cc.EffectAsset"):
        effect = _root(effects[0])
        if isinstance(effect, dict) and effect.get("__type__") == "cc.EffectAsset" and effect.get("_name") == "shader-2d-uiColor":
            tech = material.get("_techniqueData", {}).get("0", {})
            defines = tech.get("defines", {})
            props = tech.get("props", {})
            if (defines.get("USE_TEXTURE") is True and
                    _near(props.get("gray"), spec.get("gray")) and
                    _near(props.get("saturation"), spec.get("saturation"))):
                return {"kind": "unity-recovered-material-binding", "sourceMaterialId": source_id,
                        "resolvedMaterialId": resolved_id, "effectSourceId": effects[0]["sourceId"],
                        "profile": _UI_COLOR_PROFILE, "requiresMaterialBindingAppend": True}, None
    return None, "source_effect_not_mapped:" + source_id


def _near(a: Any, b: Any) -> bool:
    return (type(a) in (int, float) and type(b) in (int, float) and
            math.isfinite(a) and math.isfinite(b) and abs(float(a) - float(b)) <= 1e-6)


def _texture(component: dict, plan: dict, *, original: bool = False) -> dict | None:
    frame_id = component.get("spriteFrame")
    if original:
        frame_id = frame_id + "@original" if isinstance(frame_id, str) else frame_id
    return next((row for row in plan.get("textures") or []
                 if isinstance(row, dict) and row.get("id") == frame_id), None)


def _sprite(component: dict, plan: dict, manifest: dict,
            by_id: dict[str, dict], by_uuid: dict[str, list[dict]]) -> dict:
    sid = component.get("sourceId")
    row = {"sourceComponentId": sid, "sourceNodeId": component.get("node"),
           "sourceType": "cc.Sprite", "nativeComponent": "UnityEngine.UI.Image",
           "status": "blocked", "nativeFields": {}, "evidence": {}, "blockers": []}
    use_original = component.get("trim") is False
    texture = _texture(component, plan, original=use_original)
    source_frame = _texture(component, plan)
    if not isinstance(component.get("spriteFrame"), str) or texture is None or not texture.get("path"):
        row["blockers"].append("sprite_frame_or_target_texture_missing")
    else:
        row["evidence"].update(spriteFrameSourceId=component["spriteFrame"], texturePath=texture["path"])
        row["nativeFields"].update(sprite=component["spriteFrame"],
                                    type={0: "Simple", 1: "Sliced", 2: "Tiled"}.get(component.get("mode")),
                                    enabled=component.get("enabled") is True)
        if component.get("mode") not in (0, 1, 2):
            row["blockers"].append("sprite_mode_unsupported")
        if use_original and component.get("mode") in (1, 2):
            size, original, offset = texture.get("size"), texture.get("originalSize"), texture.get("offset")
            identity = (isinstance(size, list) and isinstance(original, list) and
                        len(size) == len(original) == 2 and size == original and offset == [0, 0])
            if not identity:
                row["blockers"].append("sliced_untrimmed_geometry_not_identity")
            else:
                row["evidence"]["untrimmedGeometryPolicy"] = "identity-full-frame-zero-offset"
        border = texture.get("border")
        # The original-size texture variant is intentionally imported with a
        # zero border by the texture planner because packed-frame geometry can
        # differ. Cocos capInsets remain a source SpriteFrame property and are
        # the authority for the Image slice border on this untrimmed variant.
        if use_original and component.get("mode") == 1 and isinstance(source_frame, dict):
            border = source_frame.get("border")
            row["evidence"]["spriteBorderSource"] = "source SpriteFrame capInsets"
        if component.get("mode") == 1 and isinstance(border, list) and len(border) == 4:
            row["nativeFields"]["border"] = border
            if use_original and component.get("mode") == 1:
                row["nativeFields"]["textureImportBorderOverride"] = border
        if use_original:
            row["nativeFields"]["useOriginalSizeSprite"] = True
            row["evidence"]["textureVariantId"] = texture["id"]

    material, material_error = _material_evidence(component, plan, manifest, by_id, by_uuid)
    if material_error:
        row["blockers"].append(material_error)
    else:
        row["evidence"]["material"] = material
        row["nativeFields"]["materialSourceId"] = material["sourceMaterialId"]
    if not row["blockers"]:
        row["status"] = "ready"
        row["reuse"] = ["UnityImporter.cc.Sprite Image creation", "MonkeyUnityMaterialBindings"]
    return row


def _covered(text: str, coverage: dict) -> bool:
    ranges = coverage.get("unicodeRanges") if isinstance(coverage, dict) else None
    if not isinstance(ranges, list):
        return False
    intervals = [(r[0], r[1]) for r in ranges if isinstance(r, list) and len(r) == 2
                 and type(r[0]) is int and type(r[1]) is int]
    return all(any(lo <= ord(char) <= hi for lo, hi in intervals) for char in text)


def _font_mapping(component: dict, plan: dict) -> tuple[dict | None, str | None]:
    effective = component.get('nativeEffectiveFontBinding')
    if isinstance(effective, dict) and effective.get('sourceEffectiveFontPolicy') == 'creator24-ttf-null-font-effective-family-arial-v1':
        matches=[b for b in (plan.get('systemFontBinding')or{}).get('labelBindings',[]) if b.get('sourceLabelId')==component['sourceId']]
        if (len(matches)==1 and matches[0].get('sourceSystemFont')is False and matches[0].get('sourceSerializedFontUuid')is None
                and matches[0].get('sourceEffectiveFontPolicy')==effective['sourceEffectiveFontPolicy']
                and matches[0].get('nativeFontAssetId')==effective.get('nativeFontAssetId')
                and matches[0].get('sourceText')==component.get('text')):
            return dict(kind='source-effective-native-font',nativeFontAssetId=effective['nativeFontAssetId'],nativeFontAssetPath=effective['nativeFontAssetPath']),None
        return None,'source_effective_font_binding_changed'
    declared_binding = component.get("nativeSystemFontBinding")
    if (isinstance(declared_binding, dict) and declared_binding.get("sourceSystemFont") is True and
            declared_binding.get("nativeFontAssetId") and declared_binding.get("nativeFontAssetPath") and
            declared_binding.get("sourceLabelId") == component.get("sourceId")):
        return {"kind": "system-font", "nativeFontAssetId": declared_binding["nativeFontAssetId"],
                "nativeFontAssetPath": declared_binding["nativeFontAssetPath"],
                "resolvedPrimaryFamily": declared_binding.get("resolvedPrimaryFamily"),
                "fallbackAssetIds": declared_binding.get("nativeFallbackAssetIds", [])}, None
    font_id = component.get("font")
    if isinstance(font_id, str) and font_id:
        bitmap = next((f for f in plan.get("bitmapFonts") or []
                       if isinstance(f, dict) and f.get("id") == font_id), None)
        if bitmap:
            chars = {g.get("unicode") for g in bitmap.get("glyphs") or [] if isinstance(g, dict)}
            missing = sorted({ord(ch) for ch in component.get("text", "") if ord(ch) not in chars})
            missing_binding=next((b for b in (plan.get('bitmapMissingGlyphs')or{}).get('components',[])if b['sourceComponentId']==component['sourceId']),None)
            if missing and not (missing_binding and missing_binding['sourceFontId']==font_id and missing_binding['sourceText']==component['text'] and missing_binding['sourceGlyphUnicode']==sorted(chars)):
                return None, "bitmap_font_glyphs_missing:" + ",".join(map(str, missing))
            return {"kind": "bitmap", "sourceFontId": font_id, "fontPath": bitmap.get("fontPath")}, None
        asset = next((a for a in plan.get("assets") or []
                      if isinstance(a, dict) and a.get("id") == font_id and a.get("fontAssetPath")), None)
        if asset:
            if not _covered(component.get("text", ""), asset.get("fontCoverage") or {}):
                return None, "source_font_glyph_coverage_missing:" + font_id
            return {"kind": "ttf", "sourceFontId": font_id, "fontPath": asset["fontAssetPath"]}, None
        return None, "source_font_asset_not_imported:" + font_id

    if component.get("systemFont") is True:
        bindings = (plan.get("systemFontBinding") or {}).get("labelBindings") or []
        binding = next((x for x in bindings if isinstance(x, dict) and
                        x.get("sourceLabelId") == component.get("sourceId") and
                        x.get("sourceSystemFont") is True and
                        x.get("sourceFontFamily") == component.get("fontFamily") and
                        x.get("nativeFontAssetId") and x.get("nativeFontAssetPath")), None)
        if binding:
            return {"kind": "system-font", "nativeFontAssetId": binding["nativeFontAssetId"],
                    "nativeFontAssetPath": binding["nativeFontAssetPath"],
                    "resolvedPrimaryFamily": binding.get("resolvedPrimaryFamily"),
                    "fallbackAssetIds": binding.get("nativeFallbackAssetIds", [])}, None
        return None, "source_system_font_has_no_exact_native_binding"
    # Creator 2.4.15's TTF assembler calls renderer/utils.getFontFamily(comp).
    # That function returns literal Arial when useSystemFont is false and
    # comp.font is null. This inconsistent serialized state therefore still
    # has a real source renderer family, but only when the existing target
    # resolver can supply Arial and its exact required fallback glyph set.
    if component.get("font") is None and component.get("systemFont") is False:
        binding_set = plan.get("systemFontBinding") or {}
        bindings = binding_set.get("labelBindings") or []
        bindings = [b for b in bindings if isinstance(b, dict) and
                    b.get("sourceFontFamily") == "Arial" and
                    b.get("resolvedPrimaryFamily") == "Arial" and
                    b.get("nativeFontAssetId") and b.get("nativeFontAssetPath") and
                    b.get("nativeFallbackAssetIds")]
        font_specs = (binding_set.get("systemFonts") or {}).get("fonts") or []
        fallbacks = {f.get("assetId"): f for f in font_specs if isinstance(f, dict) and
                     f.get("generationMode") == "CoreTextRasterizedStaticSDF" and f.get("assetPath")}
        # Require one unambiguous target Arial primary and fallback source.
        fallback_ids = {fid for b in bindings for fid in b.get("nativeFallbackAssetIds", [])
                        if fid in fallbacks}
        bindings = [b for b in bindings if any(fid in fallbacks for fid in b.get("nativeFallbackAssetIds", []))]
        primaries = {(b["nativeFontAssetId"], b["nativeFontAssetPath"])
                     for b in bindings}
        if len(primaries) == 1 and fallback_ids:
            text = component.get("text", "")
            coverage: set[str] = set()
            for fallback_id in fallback_ids:
                for glyph in fallbacks[fallback_id].get("requiredGlyphs") or []:
                    if isinstance(glyph, dict) and isinstance(glyph.get("character"), str):
                        coverage.add(glyph["character"])
            # The mapped text must be wholly present in the pinned static SDF
            # fallback. This avoids relying on host-dependent OS fallback for
            # any source character.
            if isinstance(text, str) and text and all(char in coverage for char in text):
                primary_id, primary_path = next(iter(primaries))
                return {"kind": "creator24-null-font-ttf-default-family",
                        "sourceEffectiveFamily": "Arial", "nativeFontAssetId": primary_id,
                        "nativeFontAssetPath": primary_path,
                        "fallbackAssetIds": sorted(fallback_ids),
                        "fallbackAssetPaths": sorted(fallbacks[fid]["assetPath"] for fid in fallback_ids),
                        "sourceBehavior": "Creator 2.4.15 TTF getFontFamily returns Arial for useSystemFont=false and font=null",
                        "coverage": "all source text characters are present in pinned StaticSDFRequired fallback",
                        "runtimePlatformConstraint": binding_set.get("runtimePlatformConstraint")}, None
            missing = sorted(set(text) - coverage) if isinstance(text, str) else []
            return None, "creator_arial_fallback_glyphs_missing:" + "".join(missing)
    return None, "font_identity_missing_and_source_system_font_disabled"


def _label(component: dict, plan: dict) -> dict:
    row = {"sourceComponentId": component.get("sourceId"), "sourceNodeId": component.get("node"),
           "sourceType": "cc.Label", "nativeComponent": "TMPro.TextMeshProUGUI",
           "status": "blocked", "nativeFields": {}, "evidence": {}, "blockers": []}
    text = component.get("text")
    if not isinstance(text, str) or not text:
        row["blockers"].append("source_label_text_empty")
    font, error = _font_mapping(component, plan)
    if error:
        row["blockers"].append(error)
    else:
        row["evidence"]["font"] = font
    row["nativeFields"] = {"text": text, "fontSize": component.get("fontSize"),
                           "lineHeight": component.get("lineHeight"), "spacing": component.get("spacing"),
                           "horizontalAlign": component.get("horizontalAlign"),
                           "verticalAlign": component.get("verticalAlign"),
                           "overflow": component.get("overflow"), "wrap": component.get("wrap"),
                           "bold": component.get("bold"), "italic": component.get("italic"),
                           "underline": component.get("underline"), "enabled": component.get("enabled") is True}
    if not row["blockers"]:
        row["status"] = "ready"
        row["reuse"] = ["UnityImporter.cc.Label TMP creation", "UnitySystemFonts.ApplySourceOutline"]
    return row


def _outline(component: dict, plan: dict, label_rows: dict[str, dict]) -> dict:
    sid = component.get("sourceId")
    node = component.get("node")
    row = {"sourceComponentId": sid, "sourceNodeId": node, "sourceType": "cc.LabelOutline",
           "nativeComponent": "NativeStaticTextOutline", "status": "blocked",
           "nativeFields": {}, "evidence": {}, "blockers": []}
    label = next((c for c in plan.get("components") or [] if c.get("node") == node and c.get("type") == "cc.Label"), None)
    target_id = label.get("sourceId") if label else None
    target = label_rows.get(target_id) if target_id else None
    if target is None or target.get("status") != "ready":
        row["blockers"].append("same_node_target_label_has_no_verified_native_font:" + (target_id or "missing"))
    color = component.get("outlineColor")
    width = component.get("width")
    if not isinstance(color, list) or len(color) != 4 or any(type(v) is not int or not 0 <= v <= 255 for v in color):
        row["blockers"].append("source_outline_rgba_invalid")
    if type(width) not in (int, float) or not math.isfinite(width) or width < 0:
        row["blockers"].append("source_outline_width_invalid")
    row["nativeFields"] = {"targetLabelSourceId": target_id, "colorRgba8": color,
                           "width": width, "enabled": component.get("enabled") is True}
    row['nativeFields']['bitmapOutlineIgnored'] = bool(target and target.get('evidence',{}).get('font',{}).get('kind')=='bitmap')
    if not row["blockers"]:
        row["status"] = "ready"
        row["reuse"] = ["NativeStaticTextOutline.Configure(TMP_Text, width, Color, sourceLabelId)"]
    return row


def prepare(plan: dict, manifest: dict) -> dict:
    """Return a reviewable source-to-Unity presentation plan without mutation.

    Ready rows are recipes only. The caller must attach the corresponding
    native renderer and preserve the row's source identity in readback.
    Unsupported rows carry stable blocker codes and never create empty render
    carriers.
    """
    if not isinstance(plan, dict) or not isinstance(manifest, dict):
        raise ValueError("plan and source manifest must be objects")
    by_id, by_uuid = _source_assets(manifest)
    rows: list[dict] = []
    label_rows: dict[str, dict] = {}
    components = [c for c in plan.get("components") or [] if isinstance(c, dict)]
    for component in components:
        if component.get("type") == "cc.Label":
            row = _label(component, plan)
            label_rows[row["sourceComponentId"]] = row
            if not component.get("convertible"):
                rows.append(row)
    for component in components:
        if component.get("type") == "cc.Sprite" and not component.get("convertible"):
            rows.append(_sprite(component, plan, manifest, by_id, by_uuid))
        elif component.get("type") == "cc.LabelOutline":
            node_labels = [c for c in components if c.get("node") == component.get("node")
                           and c.get("type") == "cc.Label"]
            if not component.get("convertible") or any(not c.get("convertible") for c in node_labels):
                rows.append(_outline(component, plan, label_rows))
    rows.sort(key=lambda r: (r.get("sourceNodeId") or "", r.get("sourceType") or "", r.get("sourceComponentId") or ""))
    return {"schema": SCHEMA, "sourceManifestSha256": plan.get("sourceManifestSha256"),
            "contract": {"readyRowsAreRecipes": True, "sourceIdsRequiredInReadback": True,
                         "imageMode": {0: "Simple", 1: "Sliced", 2: "Tiled"},
                         "outlineAdapter": "NativeStaticTextOutline",
                         "shaderBindingAdapter": "MonkeyUnityMaterialBindings"},
            "components": rows,
            "blockers": [{"sourceComponentId": r["sourceComponentId"], "sourceType": r["sourceType"],
                          "code": code} for r in rows for code in r["blockers"]]}


def apply_unity(plan: dict, manifest: dict) -> dict:
    """Wire supported recipes into existing native renderer creation paths."""
    import copy
    if manifest.get('sourceProfile') != 'cocos-2.4.15-bundle':
        raise ValueError('STATIC_PRESENTATION_SOURCE_PROFILE_UNSUPPORTED')
    for component in plan['components']:
        effective=component.get('nativeEffectiveFontBinding')
        if effective:
            font,error=_font_mapping(component,plan)
            if error:raise ValueError(error)
            component.update(sourceFont=None,font=font['nativeFontAssetId'],staticPresentationPolicy='source-evidenced-native-renderer-v1')
    report = prepare(plan, manifest)
    components = {c['sourceId']: c for c in plan['components']}
    for row in report['components']:
        if row['status'] != 'ready':
            continue
        component = components[row['sourceComponentId']]
        if row['sourceType'] == 'cc.Sprite':
            material = row['evidence']['material']
            if material['kind'] == 'unity-recovered-material-binding':
                _append_material_binding(plan,manifest,component)
                component['nativeMaterialSourceId'] = material['sourceMaterialId']
            if 'textureImportBorderOverride' in row['nativeFields']:
                texture = next(t for t in plan['textures'] if t['id'] == row['evidence']['textureVariantId'])
                texture['border'] = row['nativeFields']['textureImportBorderOverride']
        elif row['sourceType'] == 'cc.Label':
            font = row['evidence']['font']
            if font['kind'] == 'creator24-null-font-ttf-default-family':
                binding_set = plan['systemFontBinding']
                template = next(b for b in binding_set['labelBindings'] if b['nativeFontAssetId'] == font['nativeFontAssetId'])
                binding = copy.deepcopy(template)
                binding.update(sourceLabelId=component['sourceId'], sourceText=component['text'],
                               pointSize=component['fontSize'], sourceSystemFont=False,
                               sourceEffectiveFontPolicy='creator24-null-font-ttf-Arial',
                               sourceFontFamilyEvidence='creator24-renderer-utils-getFontFamily-null-branch')
                binding_set['labelBindings'].append(binding)
                component.update(sourceFont=None, font=font['nativeFontAssetId'], nativeSystemFontBinding=binding,
                                 sourceEffectiveFontPolicy='creator24-null-font-ttf-Arial')
            elif font.get('nativeFontAssetId'):
                component['font'] = font['nativeFontAssetId']
        elif row['sourceType']=='cc.LabelOutline':
            component['staticBitmapOutline']=row['nativeFields'].get('bitmapOutlineIgnored',False)
        component['convertible'] = True
        component['staticPresentationPolicy'] = 'source-evidenced-native-renderer-v1'
    plan['staticPresentation'] = report
    return report


def apply_creator(plan: dict, manifest: dict) -> dict:
    """Reuse Creator Sprite/Label components, retaining source fallback policy."""
    if manifest.get('sourceProfile') != 'cocos-2.4.15-bundle':
        raise ValueError('STATIC_PRESENTATION_SOURCE_PROFILE_UNSUPPORTED')
    by_id, by_uuid = _source_assets(manifest)
    assets = {a['sourceId']: a for a in plan['assets']}
    rows = []
    for component in plan['components']:
        if component.get('convertible') or component['type'] not in ('cc.Sprite', 'cc.Label'):
            continue
        row = dict(sourceComponentId=component['sourceId'], sourceNodeId=component['node'],
                   sourceType=component['type'], status='blocked', blockers=[])
        if component['type'] == 'cc.Sprite':
            frame = assets.get(component.get('spriteFrame'))
            if not frame or frame['kind'] != 'sprite':
                row['blockers'].append('sprite_frame_or_target_texture_missing')
            if component.get('mode') not in (0, 1, 2):
                row['blockers'].append('sprite_mode_unsupported')
            material, error = _material_evidence(component, plan, manifest, by_id, by_uuid)
            if error:
                row['blockers'].append(error)
            if not row['blockers']:
                if material['kind'] == 'unity-recovered-material-binding':
                    _append_material_binding(plan,manifest,component)
                    component['nativeMaterialSourceId'] = material['sourceMaterialId']
                component.update(nativeSizeMode=component['sizeMode'], sizingPolicy='native-sprite-sizing-v1')
        elif component.get('font') is None and component.get('systemFont') is False:
            component.update(nativeSystemFont=True, fontFamily='Arial', nativeOverflow=component['overflow'],
                             sourceEffectiveFontPolicy='creator24-null-font-ttf-Arial',
                             sizingPolicy='native-label-sizing-v1')
        else:
            row['blockers'].append('source_font_not_available_or_outside_native_profile')
        if not row['blockers']:
            row['status'] = 'ready'
            component.update(convertible=True, nativeType=component['type'],
                             staticPresentationPolicy='source-evidenced-native-renderer-v1')
        rows.append(row)
    labels = {c['node']: c for c in plan['components'] if c['type'] == 'cc.Label' and c.get('convertible')}
    for component in plan['components']:
        if component['type'] == 'cc.LabelOutline' and not component.get('convertible') and component['node'] in labels:
            component.update(convertible=True, nativeType='cc.Label', staticPresentationPolicy='source-evidenced-native-renderer-v1')
            rows.append(dict(sourceComponentId=component['sourceId'], sourceNodeId=component['node'],
                             sourceType=component['type'], status='ready', blockers=[]))
    report = dict(schema=SCHEMA, sourceManifestSha256=plan['sourceManifestSha256'], components=rows)
    plan['staticPresentation'] = report
    return report
