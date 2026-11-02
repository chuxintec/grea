import base64
import copy
import struct

import pytest

from monkey.io import encoded, sha
from monkey.unity_sprite import atlas_settings, unpacked_tight_geometry


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
