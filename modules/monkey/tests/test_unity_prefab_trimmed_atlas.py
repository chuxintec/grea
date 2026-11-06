import base64
import hashlib
import struct

import pytest

from monkey.unity_prefab_trimmed_atlas import PROFILE, trimmed_rectangle_atlas_geometry


def fixture():
    vertices = [(-0.45, -0.45, 0.0), (0.45, -0.45, 0.0), (0.45, 0.45, 0.0), (-0.45, 0.45, 0.0)]
    vertex_bytes = b"".join(struct.pack("<fff", *row) for row in vertices)
    vertex_bytes += bytes(4 * 8)
    indices = [0, 1, 2, 0, 2, 3]
    source = {
        "m_Name": "RenamedFixture",
        "m_Rect": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0},
        "m_Offset": {"x": 0.0, "y": 0.0},
        "m_Pivot": {"x": 0.5, "y": 0.5},
        "m_PixelsToUnits": 100.0,
        "m_Border": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0},
        "m_Extrude": 1,
        "m_IsPolygon": False,
        "m_Bones": [],
        "m_RD": {
            "settingsRaw": 64,
            "textureRect": {"x": 5.0, "y": 5.0, "width": 90.0, "height": 90.0},
            "textureRectOffset": {"x": 5.0, "y": 5.0},
            "atlasRectOffset": {"x": -1.0, "y": -1.0},
            "uvTransform": {"x": 100.0, "y": 50.0, "z": 100.0, "w": 50.0},
            "downscaleMultiplier": 1.0,
            "alphaTexture": {"fileId": "0", "pathId": "0"},
            "secondaryTextures": [],
            "m_Bindpose": [],
            "m_VertexData": {
                "m_VertexCount": 4,
                "m_Channels": [
                    {"stream": 0, "offset": 0, "format": 0, "dimension": 3},
                    {"stream": 0, "offset": 0, "format": 0, "dimension": 0},
                    {"stream": 0, "offset": 0, "format": 0, "dimension": 0},
                    {"stream": 0, "offset": 0, "format": 0, "dimension": 0},
                    {"stream": 1, "offset": 0, "format": 0, "dimension": 2},
                ] + [{"stream": 0, "offset": 0, "format": 0, "dimension": 0} for _ in range(9)],
                "m_DataSize": {"$type": "bytes", "base64": base64.b64encode(vertex_bytes).decode(),
                               "bytes": len(vertex_bytes), "sha256": hashlib.sha256(vertex_bytes).hexdigest()},
            },
            "m_IndexBuffer": list(struct.pack("<6H", *indices)),
            "m_SubMeshes": [{"firstByte": 0, "indexCount": 6, "topology": 0, "baseVertex": 0,
                             "firstVertex": 0, "vertexCount": 4}],
        },
    }
    atlas = {
        "settingsRaw": 67,
        "texture": {"fileId": "0", "pathId": "900"},
        "alphaTexture": {"fileId": "0", "pathId": "0"},
        "secondaryTextures": [],
        "downscaleMultiplier": 1.0,
        "textureRect": {"x": 205.0, "y": 305.0, "width": 90.0, "height": 90.0},
        "textureRectOffset": {"x": 5.0, "y": 5.0},
        "atlasRectOffset": {"x": 200.0, "y": 300.0},
        "uvTransform": {"x": 100.0, "y": 250.0, "z": 100.0, "w": 350.0},
    }
    return source, atlas


def test_source_full_rect_is_separate_from_atlas_crop():
    source, atlas = fixture()
    result = trimmed_rectangle_atlas_geometry(source, atlas, 512, 512)
    assert result["geometryProfile"] == PROFILE
    assert result["sourceRect"] == source["m_Rect"]
    assert result["sourceTextureRect"] == source["m_RD"]["textureRect"]
    assert result["atlasRect"] == atlas["textureRect"]
    assert result["sourceTrimOffset"] == atlas["textureRectOffset"]
    assert result["atlasRectOffset"] == atlas["atlasRectOffset"]
    assert result["uvTransform"] == atlas["uvTransform"]
    assert result["meshUv"] == [
        {"x": 205 / 512, "y": 305 / 512},
        {"x": 295 / 512, "y": 305 / 512},
        {"x": 295 / 512, "y": 395 / 512},
        {"x": 205 / 512, "y": 395 / 512},
    ]


@pytest.mark.parametrize("field,value", [
    ("textureRectOffset", {"x": 0.0, "y": 5.0}),
    ("atlasRectOffset", {"x": 199.0, "y": 300.0}),
    ("uvTransform", {"x": 100.0, "y": 251.0, "z": 100.0, "w": 350.0}),
])
def test_rejects_inconsistent_trim_mapping(field, value):
    source, atlas = fixture()
    atlas[field] = value
    with pytest.raises(ValueError):
        trimmed_rectangle_atlas_geometry(source, atlas, 512, 512)


def test_rejects_rotated_atlas_entry():
    source, atlas = fixture()
    atlas["settingsRaw"] = 71
    with pytest.raises(ValueError, match="unrotated"):
        trimmed_rectangle_atlas_geometry(source, atlas, 512, 512)


def test_rejects_atlas_region_outside_texture():
    source, atlas = fixture()
    with pytest.raises(ValueError, match="escapes"):
        trimmed_rectangle_atlas_geometry(source, atlas, 250, 512)


def test_rejects_source_crop_dimension_mismatch():
    source, atlas = fixture()
    source["m_RD"]["textureRect"]["width"] = 89.0
    with pytest.raises(ValueError, match="crop dimensions"):
        trimmed_rectangle_atlas_geometry(source, atlas, 512, 512)
