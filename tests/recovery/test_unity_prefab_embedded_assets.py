import base64
import hashlib
import json
import struct

import pytest

from grea.recovery.io import encoded
from grea.recovery.unity_sprite import unpacked_tight_geometry
from grea.recovery.unity_prefab_embedded_assets import EmbeddedSpritePlanError, plan_embedded_sprite_rebuild


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    raw = encoded(value)
    path.write_bytes(raw)
    return sha(raw)


def fixture_inputs(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_container = tmp_path / "source.bundle"
    source_container.write_bytes(b"source-container")
    container_sha = sha(source_container.read_bytes())
    serialized = "CAB-neutral"
    serialized_sha = "b" * 64
    sprite_path = "-101"
    texture_path = "202"
    sprite_data_bytes = b"sprite-object"
    texture_data_bytes = b"texture-object"
    texture_pixels_sha = "c" * 64
    cache_raw = b"pinned-astc-cache"
    cache_sha = sha(cache_raw)
    cache_path = tmp_path / "TextureCache" / "Fixture.abcdef12.txt"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_bytes(cache_raw)

    positions = [(-0.01, -0.01, 0.0), (0.01, -0.01, 0.0), (-0.01, 0.01, 0.0), (0.01, 0.01, 0.0)]
    vertex_bytes = b"".join(struct.pack("<fff", *row) for row in positions) + bytes(32)
    channels = [dict(stream=0, offset=0, format=0, dimension=3)] + [dict(stream=0, offset=0, format=0, dimension=0) for _ in range(3)] + [dict(stream=1, offset=0, format=0, dimension=2)] + [dict(stream=0, offset=0, format=0, dimension=0) for _ in range(9)]
    indices = [0, 0, 1, 0, 2, 0, 2, 0, 1, 0, 3, 0]
    sprite_data = {
        "m_Name": "RenamedFixtureSprite",
        "m_Rect": dict(x=0.0, y=0.0, width=2.0, height=2.0),
        "m_Offset": dict(x=0.0, y=0.0),
        "m_Border": dict(x=0.25, y=0.25, z=0.25, w=0.25),
        "m_PixelsToUnits": 100.0,
        "m_Pivot": dict(x=0.5, y=0.5),
        "m_Extrude": 1,
        "m_IsPolygon": False,
        "m_AtlasTags": [],
        "m_SpriteAtlas": {"$type": "UnityPPtr", "fileId": "0", "pathId": "0"},
        "m_RD": {
            "settingsRaw": 64, "downscaleMultiplier": 1.0, "m_Bindpose": [], "secondaryTextures": [],
            "texture": {"$type": "UnityPPtr", "fileId": "0", "pathId": texture_path},
            "alphaTexture": {"$type": "UnityPPtr", "fileId": "0", "pathId": "0"},
            "uvTransform": dict(x=100.0, y=1.0, z=100.0, w=1.0),
            "m_VertexData": {
                "m_VertexCount": 4,
                "m_Channels": channels,
                "m_DataSize": {"$type": "bytes", "base64": base64.b64encode(vertex_bytes).decode(), "bytes": len(vertex_bytes), "sha256": sha(vertex_bytes)},
            },
            "m_IndexBuffer": indices,
            "m_SubMeshes": [dict(firstByte=0, indexCount=6, topology=0, baseVertex=0, firstVertex=0, vertexCount=4, localAABB=dict(m_Center=dict(x=0, y=0, z=0), m_Extent=dict(x=0, y=0, z=0)))],
        },
    }
    sprite_raw_sha = sha(sprite_data_bytes)
    texture_raw_sha = sha(texture_data_bytes)
    sprite = {
        "type": "Sprite", "rawSha256": sprite_raw_sha,
        "identity": dict(containerSha256=container_sha, serializedFile=serialized, serializedFileSha256=serialized_sha, pathId=sprite_path),
        "data": sprite_data,
    }
    texture = {
        "type": "Texture2D", "rawSha256": texture_raw_sha,
        "identity": dict(containerSha256=container_sha, serializedFile=serialized, serializedFileSha256=serialized_sha, pathId=texture_path),
        "data": dict(m_Width=2, m_Height=2, m_TextureFormat=34, m_MipCount=1, m_StreamData=dict(path="", offset=0, size=0)),
        "texturePayload": dict(kind="external-key-token-candidate", key="Fixture.abcdef12", wireKey="Fixture.abcdef12", nativePixelsVerified=False),
    }
    graph = dict(sourceUnityVersions=["2021.3.30f1"], reachableObjects=[sprite, texture])
    graph_path = tmp_path / "source-graph.json"
    graph_sha = write_json(graph_path, graph)
    typed_path = tmp_path / "typed-objects.json"
    typed = {
        "provider": {"name": "UnityPy", "version": "1.25.3"},
        "source": {"sha256": container_sha},
        "files": [{"id": "0", "name": serialized, "serializedFileSha256": serialized_sha}],
        "objects": [{"file": "0", "pathId": sprite_path, "type": "Sprite", "rawSha256": sprite_raw_sha}],
    }
    typed_sha = write_json(typed_path, typed)
    source_inputs_path = tmp_path / "source-inputs.json"
    source_inputs_sha = write_json(source_inputs_path, [{"sourcePath": str(source_container), "sourceSha256": container_sha,
                                                        "typedObjectsPath": str(typed_path), "typedObjectsSha256": typed_sha,
                                                        "cacheReaderContractSha256": "9" * 64,
                                                        "cacheScope": "prior cached reader only"}])
    geometry = unpacked_tight_geometry(sprite_data, 2, 2, 100.0, settings_raw=64, pixel_sha256=texture_pixels_sha)
    geometry_path = tmp_path / "unpacked-geometry.json"
    geometry_sha = write_json(geometry_path, geometry)
    hydration = dict(file=serialized, pathId=texture_path, logicalPath="Assets/Textures/astc/2/Fixture.abcdef12.txt", cacheSha256=cache_sha, cacheBytes=len(cache_raw), rgbaRawSha256=texture_pixels_sha, astc=dict(block=8, width=2, height=2, payloadBytes=len(cache_raw)))
    prepared_row = dict(source=dict(sha256=container_sha), resolved=[hydration], pixelsFabricated=False, status="prepared")
    prepared = dict(status="prepared", pixelsFabricated=False, rows=[prepared_row])
    prepared_path = tmp_path / "prepared.json"
    prepared_sha = write_json(prepared_path, prepared)
    prepare_job = dict(cache=[dict(logicalPath=hydration["logicalPath"], path=str(cache_path), bytes=len(cache_raw), sha256=cache_sha)])
    prepare_job_path = tmp_path / "prepare-job.json"
    prepare_job_sha = write_json(prepare_job_path, prepare_job)
    identity = dict(containerSha256=container_sha, serializedFile=serialized, serializedFileSha256=serialized_sha, pathId=sprite_path, rawSha256=sprite_raw_sha)
    call = dict(source_graph_path=graph_path, source_graph_sha256=graph_sha,
                source_inputs_path=source_inputs_path, source_inputs_sha256=source_inputs_sha,
                prepared_path=prepared_path, prepared_sha256=prepared_sha,
                prepare_job_path=prepare_job_path, prepare_job_sha256=prepare_job_sha, source_sprite_identity=identity,
                source_settings_raw=64, geometry_descriptor_path=geometry_path, geometry_descriptor_sha256=geometry_sha)
    return call, cache_path, sprite, texture


def test_builds_deterministic_independent_sprite_plan_from_pinned_pixels_and_geometry(tmp_path):
    call, _, sprite, _ = fixture_inputs(tmp_path)
    result = plan_embedded_sprite_rebuild(**call)
    again = plan_embedded_sprite_rebuild(**call)
    assert result == again
    assert result["status"] == "native_sprite_rebuild_plan"
    assert result["sourceSpriteIdentity"]["rawSha256"] == sprite["rawSha256"]
    assert result["sourceTextureHydration"]["rgbaRawSha256"] == "c" * 64
    assert result["sourceTextureHydration"]["cacheSha256"] == sha((tmp_path / "TextureCache/Fixture.abcdef12.txt").read_bytes())
    assert result["sourceSpriteDescriptor"]["settingsRaw"] == 64
    assert result["sourceSpriteDescriptor"]["geometry"]["meshVertices"]
    assert result["target"]["texturePath"].startswith("Assets/Game/Content/Images/EmbeddedSprites/")
    assert result["target"]["nativeGuid"] is None
    assert result["target"]["nativeLocalFileID"] is None
    assert result["provenance"]["m_RenderDataKeyUsedAsIdentity"] is False
    assert result["nativeAssetDatabaseVerified"] is False


def test_source_cache_hash_and_prepared_binding_are_mandatory(tmp_path):
    call, cache_path, _, _ = fixture_inputs(tmp_path)
    cache_path.write_bytes(b"drift")
    with pytest.raises(EmbeddedSpritePlanError, match="cache file bytes/hash differ"):
        plan_embedded_sprite_rebuild(**call)

    call, _, _, _ = fixture_inputs(tmp_path / "second")
    prepared = json.loads(call["prepared_path"].read_text())
    prepared["rows"][0]["resolved"][0]["pathId"] = "203"
    call["prepared_sha256"] = write_json(call["prepared_path"], prepared)
    with pytest.raises(EmbeddedSpritePlanError, match="hydration rows"):
        plan_embedded_sprite_rebuild(**call)


def test_rejects_wrong_source_tuple_or_non_unpacked_profile(tmp_path):
    call, _, _, _ = fixture_inputs(tmp_path)
    call["source_sprite_identity"]["rawSha256"] = "d" * 64
    with pytest.raises(EmbeddedSpritePlanError, match="prior typed receipt has 0 exact Sprite rows"):
        plan_embedded_sprite_rebuild(**call)

    call, _, _, _ = fixture_inputs(tmp_path / "second")
    call["source_settings_raw"] = 65
    with pytest.raises(EmbeddedSpritePlanError, match="settingsRaw=64"):
        plan_embedded_sprite_rebuild(**call)


def test_rejects_geometry_or_pixel_proof_mismatch(tmp_path):
    call, _, _, _ = fixture_inputs(tmp_path)
    descriptor = json.loads(call["geometry_descriptor_path"].read_text())
    descriptor["textureRgbaRawSha256"] = "f" * 64
    call["geometry_descriptor_sha256"] = write_json(call["geometry_descriptor_path"], descriptor)
    with pytest.raises(EmbeddedSpritePlanError, match="pixel hash differs"):
        plan_embedded_sprite_rebuild(**call)


def test_target_asset_root_is_safe_and_editor_identity_remains_pending(tmp_path):
    call, _, _, _ = fixture_inputs(tmp_path)
    call["target_asset_root"] = "Assets/Generated/../Other"
    with pytest.raises(EmbeddedSpritePlanError, match="safe Assets-relative"):
        plan_embedded_sprite_rebuild(**call)
