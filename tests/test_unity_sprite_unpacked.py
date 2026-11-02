import base64
import copy
import struct

import pytest

from monkey.io import encoded, sha
from monkey.unity_sprite import atlas_settings, rectangle_atlas_geometry, unpacked_tight_geometry


def source_sprite():
    vertices = [(-.25, -.25, 0), (.25, -.25, 0), (0, .25, 0)]
    raw = b''.join(struct.pack('<fff', *v) for v in vertices) + bytes(12 + 3 * 8)
    channels = [dict(stream=0, offset=0, format=0, dimension=0) for _ in range(5)]
    channels[0].update(dimension=3)
    channels[4].update(stream=1, dimension=2)
    return dict(m_Rect=dict(x=0, y=0, width=8, height=8), m_Pivot=dict(x=.5, y=.5),
        m_Border=dict(x=1, y=1, z=1, w=1), m_PixelsToUnits=8, m_Extrude=1,
        m_IsPolygon=False, m_Bones=[], m_Skin=[], m_SpriteAtlas=dict(fileId="0", pathId="0"), m_AtlasTags=[],
        m_RD=dict(settingsRaw=64, alphaTexture=dict(fileId="0", pathId="0"), secondaryTextures=[], m_Bindpose=[], downscaleMultiplier=1,
            uvTransform=dict(x=8, y=4, z=8, w=4),
            m_VertexData=dict(m_VertexCount=3, m_Channels=channels,
                m_DataSize={'$type': 'bytes', 'base64': base64.b64encode(raw).decode(), 'bytes': len(raw), 'sha256': sha(raw)}),
            m_IndexBuffer=list(struct.pack('<HHH', 0, 1, 2)),
            m_SubMeshes=[dict(firstByte=0, indexCount=3, topology=0, baseVertex=0, firstVertex=0, vertexCount=3)]))


def test_unpacked_descriptor_preserves_source_mesh_and_pixel_binding_without_builtin_guess():
    data = source_sprite()
    result = unpacked_tight_geometry(data, 8, 8, 8, pixel_sha256='a' * 64)
    assert result['meshVertices'] == [dict(x=-.25, y=-.25), dict(x=.25, y=-.25), dict(x=0, y=.25)]
    assert result['triangleIndices'] == [0, 1, 2]
    assert result['meshUv'] == [dict(x=.25, y=.25), dict(x=.75, y=.25), dict(x=.5, y=.75)]
    assert result['sourceSpriteDataSha256'] == sha(encoded(data))
    assert result['textureRgbaRawSha256'] == 'a' * 64
    assert result['geometrySha256'] == sha(encoded({k: v for k, v in result.items() if k != 'geometrySha256'}))
    assert 'guid' not in result
    with pytest.raises(ValueError):
        atlas_settings(64)


@pytest.mark.parametrize('change', [
    lambda d: d['m_RD'].update(settingsRaw=65),
    lambda d: d['m_RD']['uvTransform'].update(y=5),
    lambda d: d['m_RD']['m_VertexData']['m_DataSize'].update(sha256='f' * 64),
    lambda d: d['m_RD'].update(m_IndexBuffer=list(struct.pack('<HHH', 0, 1, 9))),
    lambda d: d.update(m_PixelsToUnits=16),
    lambda d: d.update(m_IsPolygon=True),
    lambda d: d.update(m_Bones=[{}]),
    lambda d: d['m_Rect'].update(x=1),
])
def test_unpacked_profile_rejects_unproven_or_changed_geometry(change):
    data = copy.deepcopy(source_sprite())
    change(data)
    with pytest.raises(ValueError):
        unpacked_tight_geometry(data, 8, 8, 8, pixel_sha256='a' * 64)


def rectangle_atlas():
    return dict(settingsRaw=67, downscaleMultiplier=1,
                alphaTexture=dict(fileId='0', pathId='0'), secondaryTextures=[],
                textureRect=dict(x=12, y=20, width=8, height=8),
                textureRectOffset=dict(x=0, y=0),
                uvTransform=dict(x=8, y=16, z=8, w=24))


def test_rectangle_atlas_proves_region_uv_without_relabelling_packed_flags():
    data = source_sprite()
    result = rectangle_atlas_geometry(data, rectangle_atlas(), 64, 64)
    assert result['targetRect'] == dict(x=12, y=20, width=8, height=8)
    assert result['sourceRect'] == data['m_Rect']
    assert result['meshUv'] == [dict(x=14/64, y=22/64), dict(x=18/64, y=22/64), dict(x=16/64, y=26/64)]
    assert result['sourcePackedSettingsRaw'] == 67
    assert result['representation'] == 'native-unpacked-atlas-region;source-packed-flags-not-equated'
    assert result['geometrySha256'] == sha(encoded({k: v for k, v in result.items() if k != 'geometrySha256'}))


@pytest.mark.parametrize('change', [
    lambda a: a.update(settingsRaw=65),
    lambda a: a.update(settingsRaw=71),
    lambda a: a.update(downscaleMultiplier=.5),
    lambda a: a['textureRectOffset'].update(x=1),
    lambda a: a['textureRect'].update(width=9),
    lambda a: a['uvTransform'].update(y=17),
    lambda a: a['alphaTexture'].update(pathId='9'),
])
def test_rectangle_atlas_rejects_unproven_packing_or_trim(change):
    atlas = rectangle_atlas()
    change(atlas)
    with pytest.raises(ValueError):
        rectangle_atlas_geometry(source_sprite(), atlas, 64, 64)


def test_rectangle_atlas_uses_float32_edge_arithmetic_without_clipping():
    data, atlas = source_sprite(), rectangle_atlas()
    data['m_Rect']['width'] = 393
    data['m_PixelsToUnits'] = 100
    atlas['textureRect'].update(x=0, width=393)
    atlas['uvTransform'] = dict(x=100, y=196.5, z=100, w=24)
    vd = data['m_RD']['m_VertexData']
    raw = base64.b64decode(vd['m_DataSize']['base64'])
    raw = b''.join(struct.pack('<fff', *v) for v in [(-1.965, -.01, 0), (.25, -.01, 0), (0, .01, 0)]) + raw[36:]
    vd['m_DataSize'] = dict(vd['m_DataSize'], base64=base64.b64encode(raw).decode(), sha256=sha(raw))
    source_x = struct.unpack('<f', raw[:4])[0]
    assert source_x * 100 + 196.5 < 0
    assert rectangle_atlas_geometry(data, atlas, 1024, 64)['meshUv'][0]['x'] == 0
    raw = struct.pack('<f', -2) + raw[4:]
    vd['m_DataSize'].update(base64=base64.b64encode(raw).decode(), sha256=sha(raw))
    with pytest.raises(ValueError, match='Atlas UV outside texture'):
        rectangle_atlas_geometry(data, atlas, 1024, 64)
