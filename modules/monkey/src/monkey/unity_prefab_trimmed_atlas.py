"""Source-proven unrotated rectangle atlas geometry with source trim metadata.

This helper describes the exact source Sprite, matching SpriteAtlas render-map
entry and a pinned provider correction. It does not edit assets or Unity YAML.
"""
import math
import struct

from .io import encoded, sha
from .unity_sprite import _tight_mesh, atlas_settings


PROFILE = "unity-2021.3-trimmed-unrotated-rectangle-atlas-v1"


def _f32(value):
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _coord(value, scale, offset, size):
    # Match serialized Float32 multiply, add, divide as three separate steps.
    return _f32(_f32(_f32(value * scale) + offset) / size)


def _rect(value, label):
    if not isinstance(value, dict) or set(value) != {"x", "y", "width", "height"}:
        raise ValueError(f"{label} must have exact x/y/width/height fields")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in value.values()):
        raise ValueError(f"{label} contains a non-finite coordinate")
    if value["width"] <= 0 or value["height"] <= 0:
        raise ValueError(f"{label} must have positive dimensions")
    return {key: _f32(value[key]) for key in ("x", "y", "width", "height")}


def _vec2(value, label):
    if not isinstance(value, dict) or set(value) != {"x", "y"}:
        raise ValueError(f"{label} must have exact x/y fields")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in value.values()):
        raise ValueError(f"{label} contains a non-finite coordinate")
    return {key: _f32(value[key]) for key in ("x", "y")}


def trimmed_rectangle_atlas_geometry(source_sprite, atlas_render_data, width, height):
    """Validate source full rect, trim crop, atlas transform and mesh exactly.

    ``source_sprite`` is the typed Sprite ``data`` from the pinned source graph;
    ``atlas_render_data`` is the unique SpriteAtlas ``m_RenderDataMap`` value
    selected by that Sprite's exact ``m_RenderDataKey``. Width/height belong to
    the exact resolved atlas Texture2D.
    """
    if type(width) is not int or type(height) is not int or min(width, height) <= 0:
        raise ValueError("Exact positive atlas texture dimensions are required")
    if width * height > 16 * 1024 * 1024:
        raise ValueError("Atlas texture exceeds the bounded pixel profile")
    source_rect = _rect(source_sprite.get("m_Rect"), "source m_Rect")
    atlas_rect = _rect(atlas_render_data.get("textureRect"), "Atlas textureRect")
    trim = _vec2(atlas_render_data.get("textureRectOffset"), "Atlas textureRectOffset")
    source_rd = source_sprite.get("m_RD")
    if not isinstance(source_rd, dict):
        raise ValueError("Source Sprite m_RD is required")
    if source_rd.get("alphaTexture", {}).get("pathId") != "0" or source_rd.get("secondaryTextures") or \
            source_rd.get("downscaleMultiplier") != 1 or source_rd.get("m_Bindpose"):
        raise ValueError("Source Sprite alpha/secondary/skinned/downscaled data requires another profile")
    source_rd_rect = _rect(source_rd.get("textureRect"), "source m_RD.textureRect")
    source_rd_trim = _vec2(source_rd.get("textureRectOffset"), "source m_RD.textureRectOffset")
    if source_rd_trim != trim:
        raise ValueError("Source m_RD textureRectOffset differs from the exact Atlas render entry")
    if source_rd_rect["width"] != atlas_rect["width"] or source_rd_rect["height"] != atlas_rect["height"]:
        raise ValueError("Source crop dimensions differ from the Atlas textureRect")
    if source_rd_rect["x"] != trim["x"] or source_rd_rect["y"] != trim["y"]:
        raise ValueError("Source m_RD.textureRect origin differs from the source trim offset")
    if not (0 <= trim["x"] < source_rect["width"] and 0 <= trim["y"] < source_rect["height"]):
        raise ValueError("Source trim offset escapes the logical full rect")
    if trim["x"] + atlas_rect["width"] > source_rect["width"] or trim["y"] + atlas_rect["height"] > source_rect["height"]:
        raise ValueError("Atlas crop plus trim offset exceeds the logical full rect")
    if atlas_rect["x"] < 0 or atlas_rect["y"] < 0 or atlas_rect["x"] + atlas_rect["width"] > width or atlas_rect["y"] + atlas_rect["height"] > height:
        raise ValueError("Atlas textureRect escapes its exact atlas texture dimensions")
    if atlas_rect["width"] >= source_rect["width"] and atlas_rect["height"] >= source_rect["height"] and trim == {"x": 0.0, "y": 0.0}:
        raise ValueError("This profile is only for an actual trimmed source Sprite")

    source_offset = _vec2(source_sprite.get("m_Offset"), "source m_Offset")
    pivot = _vec2(source_sprite.get("m_Pivot"), "source m_Pivot")
    ppu = source_sprite.get("m_PixelsToUnits")
    if type(ppu) not in (int, float) or not math.isfinite(ppu) or ppu <= 0:
        raise ValueError("Source pixelsPerUnit must be finite and positive")
    ppu = _f32(ppu)
    if any(not 0 <= pivot[key] <= 1 for key in ("x", "y")):
        raise ValueError("Source normalized pivot must be within 0..1")

    settings_raw = atlas_render_data.get("settingsRaw")
    try:
        settings = atlas_settings(settings_raw)
    except ValueError as error:
        raise ValueError("Atlas settings do not prove the supported unrotated rectangle profile") from error
    if settings["packingMode"] != "Rectangle" or settings["packingRotation"] != "None":
        raise ValueError("Only unrotated rectangle SpriteAtlas entries are supported")
    if atlas_render_data.get("downscaleMultiplier") != 1 or atlas_render_data.get("alphaTexture", {}).get("pathId") != "0" or atlas_render_data.get("secondaryTextures"):
        raise ValueError("Separate alpha/secondary/downscaled atlas resources require another profile")

    atlas_offset = _vec2(atlas_render_data.get("atlasRectOffset"), "Atlas atlasRectOffset")
    expected_offset = {
        "x": _f32(atlas_rect["x"] - trim["x"]),
        "y": _f32(atlas_rect["y"] - trim["y"]),
    }
    if atlas_offset != expected_offset:
        raise ValueError("Atlas atlasRectOffset is not the atlas region origin minus exact source trim offset")

    transform = atlas_render_data.get("uvTransform")
    if not isinstance(transform, dict) or set(transform) != {"x", "y", "z", "w"}:
        raise ValueError("Atlas uvTransform must contain exact x/y/z/w values")
    expected_transform = {
        "x": ppu,
        "y": _f32(atlas_offset["x"] + _f32(source_rect["width"] * pivot["x"])),
        "z": ppu,
        "w": _f32(atlas_offset["y"] + _f32(source_rect["height"] * pivot["y"])),
    }
    if {key: _f32(transform[key]) for key in ("x", "y", "z", "w")} != expected_transform:
        raise ValueError("Atlas uvTransform differs from the exact full-rect pivot and atlasRectOffset mapping")

    vertices, triangles = _tight_mesh(source_sprite)
    coords = [
        dict(x=_coord(x, expected_transform["x"], expected_transform["y"], width),
             y=_coord(y, expected_transform["z"], expected_transform["w"], height))
        for x, y, _ in vertices
    ]
    if any(not math.isfinite(value) or value < 0 or value > 1 for row in coords for value in row.values()):
        raise ValueError("Source mesh UVs leave the pinned atlas texture")

    source_rd_transform = source_rd.get("uvTransform")
    source_border = source_sprite.get("m_Border")
    if source_rd.get("settingsRaw") != 64 or source_rd_transform != {
        "x": ppu, "y": _f32(source_rect["width"] * pivot["x"]),
        "z": ppu, "w": _f32(source_rect["height"] * pivot["y"]),
    }:
        raise ValueError("Source un-packed render-data transform/settings do not prove the full-rect geometry")
    if not isinstance(source_border, dict) or set(source_border) != {"x", "y", "z", "w"}:
        raise ValueError("Exact source Sprite border fields are required")
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in source_border.values()) or \
            source_border["x"] + source_border["z"] > source_rect["width"] or \
            source_border["y"] + source_border["w"] > source_rect["height"]:
        raise ValueError("Source Sprite border is non-finite, negative, or escapes the logical full rect")
    if type(source_sprite.get("m_Extrude")) is not int or not 0 <= source_sprite["m_Extrude"] <= 65535:
        raise ValueError("Source Sprite extrusion is outside the bounded native range")
    if source_sprite.get("m_IsPolygon") is not False or source_sprite.get("m_Bones") or source_sprite.get("m_RD", {}).get("m_Bindpose"):
        raise ValueError("Polygon or skinned source Sprite requires another profile")

    result = dict(
        geometryProfile=PROFILE,
        sourceRect=source_rect,
        sourceOffset=source_offset,
        atlasRect=atlas_rect,
        sourceTrimOffset=trim,
        atlasRectOffset=atlas_offset,
        sourceTextureRect=source_rd_rect,
        sourceSettingsRaw=source_rd["settingsRaw"],
        atlasSettingsRaw=settings_raw,
        sourcePixelsToUnits=ppu,
        sourcePivot=pivot,
        sourceBorder={key: _f32(source_border[key]) for key in ("x", "y", "z", "w")},
        sourceExtrude=source_sprite["m_Extrude"],
        uvTransform=expected_transform,
        uvArithmetic="float32-multiply-add-divide-separate-operations-no-clamp",
        meshVertices=[dict(x=x, y=y) for x, y, _ in vertices],
        triangleIndices=triangles,
        meshUv=coords,
        verifyMesh=True,
        representation="source-logical-full-rect-with-trimmed-unrotated-atlas-region",
    )
    result["geometrySha256"] = sha(encoded(result))
    return result
