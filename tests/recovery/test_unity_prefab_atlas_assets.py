import json
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from grea.recovery.io import encoded
from grea.recovery.unity_prefab_atlas_assets import plan_packed_atlas_rebind


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = encoded(value)
    path.write_bytes(raw)
    return digest(raw)


def fixture(tmp_path):
    candidate = tmp_path / "candidate"
    (candidate / "Analysis/Evidence").mkdir(parents=True)
    source_container = tmp_path / "original.bundle"
    source_container.write_bytes(b"neutral source bundle")
    source_hash = digest(source_container.read_bytes())
    serialized = "CAB-neutral-source"
    serialized_hash = "b" * 64
    sprite_id, atlas_id, texture_id = "sprite:501", "atlas:502", "texture:503"
    render_key = [{"data[0]": 7, "data[1]": 11, "data[2]": 13, "data[3]": 17}, 21300000]
    sprite_data = {
        "m_Name": "CompletelyRenamedFixture",
        "m_Rect": {"x": 0.0, "y": 0.0, "width": 2.0, "height": 2.0},
        "m_Pivot": {"x": 0.5, "y": 0.5},
        "m_PixelsToUnits": 100.0,
        "m_Border": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0},
        "m_RD": {"settingsRaw": 64, "m_IndexBuffer": [0, 0, 1, 0, 2, 0],
                 "m_VertexData": {"m_DataSize": {"base64": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}}},
        "m_RenderDataKey": render_key,
        "m_SpriteAtlas": {"$type": "UnityPPtr", "fileId": "0", "pathId": "502"},
    }
    sprite_ident = dict(containerSha256=source_hash, serializedFile=serialized,
                        serializedFileSha256=serialized_hash, pathId="501")
    atlas_ident = dict(containerSha256=source_hash, serializedFile=serialized,
                       serializedFileSha256=serialized_hash, pathId="502")
    texture_ident = dict(containerSha256=source_hash, serializedFile=serialized,
                         serializedFileSha256=serialized_hash, pathId="503")
    render = {
        "settingsRaw": 67, "texture": {"$type": "UnityPPtr", "fileId": "0", "pathId": "503"},
        "alphaTexture": {"$type": "UnityPPtr", "fileId": "0", "pathId": "0"}, "secondaryTextures": [],
        "downscaleMultiplier": 1.0,
        "textureRect": {"x": 3.0, "y": 5.0, "width": 2.0, "height": 2.0},
        "textureRectOffset": {"x": 0.0, "y": 0.0},
        "uvTransform": {"x": 100.0, "y": 4.0, "z": 100.0, "w": 6.0},
    }
    sprite = dict(sourceObjectId=sprite_id, type="Sprite", rawSha256="c" * 64,
                  identity=sprite_ident, data=sprite_data)
    atlas = dict(sourceObjectId=atlas_id, type="SpriteAtlas", rawSha256="d" * 64,
                 identity=atlas_ident, data={"m_PackedSprites": [{"$type": "UnityPPtr", "fileId": "0", "pathId": "501"}],
                                             "m_RenderDataMap": [[render_key, render]]})
    texture = dict(sourceObjectId=texture_id, type="Texture2D", rawSha256="e" * 64,
                   identity=texture_ident, data={"m_Width": 16, "m_Height": 16})
    graph = dict(contract="monkey-unity-prefab-source-graph/1", sourceUnityVersions=["2021.3.30f1"],
        reachableObjects=[sprite, atlas, texture], referenceEdges=[
            dict(sourceObjectId=sprite_id, location="$/m_SpriteAtlas", status="resolved", fileId="0", pathId="502", targetSourceObjectId=atlas_id),
            dict(sourceObjectId=atlas_id, location="$/m_PackedSprites/0", status="resolved", fileId="0", pathId="501", targetSourceObjectId=sprite_id),
            dict(sourceObjectId=atlas_id, location="$/m_RenderDataMap/0/1/texture", status="resolved", fileId="0", pathId="503", targetSourceObjectId=texture_id),
        ])
    graph_sha = dump(candidate / "Analysis/Evidence/source-graph.json", graph)
    inputs_sha = dump(candidate / "Analysis/Evidence/source-inputs.json", [dict(sourcePath=str(source_container), sourceSha256=source_hash)])
    pixels = tmp_path / "pixels/Candidate"
    pixels.mkdir(parents=True)
    png = b"neutral-png-payload"
    (pixels / "picked.png").write_bytes(png)
    pixel_manifest = dict(contract="unity-selected-texture-export/1", status="exported", nativeImport="not_run",
        inputPins={"source": source_hash}, textures=[dict(
            source=dict(file=serialized, pathId="503", sourceRawSha256="e" * 64),
            hydration=dict(logicalPath="Assets/Textures/renamed-atlas.bin", rgbaRawSha256="f" * 64),
            target=dict(path="picked.png", sha256=digest(png), bytes=len(png), nativeGuid="not-assigned", nativeImport="not_run"))])
    pixels_sha = dump(pixels / "manifest.json", pixel_manifest)
    provider = candidate
    asset_path = provider / "Assets/Relocated/neutral.asset"
    meta_path = provider / "Assets/Relocated/neutral.asset.meta"
    asset_path.parent.mkdir(parents=True)
    vertex_hex = bytes(36).hex()
    asset_path.write_text(f"""--- !u!213 &21300000
Sprite:
  m_Name: AnotherNeutralTargetName
  m_Rect:
    x: 3
    y: 5
    width: 2
    height: 2
  m_RD:
      texture: {{fileID: 2800000, guid: 0000000deadbeef15deadf00d0000000, type: 2}}
    textureRect:
      serializedVersion: 2
      x: 3
      y: 5
      width: 2
      height: 2
    settingsRaw: 67
    m_IndexBuffer: 000001000200
    m_VertexData:
      _typelessdata: {vertex_hex}
""", encoding="utf-8")
    meta_path.write_text("fileFormatVersion: 2\nguid: " + "1" * 32 + "\nNativeFormatImporter:\n  mainObjectFileID: 21300000\n")
    relocation_path = candidate / "Analysis/Mappings/unity-relocation.json"
    relocation_path.parent.mkdir(parents=True)
    relocation_sha = dump(relocation_path, dict(layout="monkey-project/2.0.0", moves=[dict(
        source="Assets/uiraw/renamed-source.asset", target="Assets/Relocated/neutral.asset",
        guid="1" * 32, kind="sprite", reason="neutral-fixture")]))
    manifest_sha = dump(candidate / "manifest.json", dict(contract="monkey-unity-prefab-recovery/1",
        sourceVersion="2021.3.30f1", targetProfile="unity-6000.6.2f1-ugui", files=[
            dict(path="Analysis/Evidence/source-graph.json", sha256=graph_sha, bytes=(candidate / "Analysis/Evidence/source-graph.json").stat().st_size),
            dict(path="Analysis/Evidence/source-inputs.json", sha256=inputs_sha, bytes=(candidate / "Analysis/Evidence/source-inputs.json").stat().st_size),
            dict(path="Analysis/Mappings/unity-relocation.json", sha256=relocation_sha, bytes=relocation_path.stat().st_size),
            dict(path="Assets/Relocated/neutral.asset", sha256=digest(asset_path.read_bytes()), bytes=asset_path.stat().st_size),
            dict(path="Assets/Relocated/neutral.asset.meta", sha256=digest(meta_path.read_bytes()), bytes=meta_path.stat().st_size)]))
    geom = dict(geometryProfile="unity-2021.3-unrotated-rectangle-atlas-v1", geometrySha256="9" * 64)
    return dict(candidate=candidate, source_id=sprite_id, manifest_sha=manifest_sha,
        pixels_manifest=pixels / "manifest.json", pixels_sha=pixels_sha, provider=provider,
        target_path="Assets/Relocated/neutral.asset", graph_sha=graph_sha, geometry=geom)


def run_plan(fx, out, **overrides):
    args = dict(candidate_root=fx["candidate"], expected_manifest_sha256=fx["manifest_sha"],
        selected_pixel_manifest=fx["pixels_manifest"], selected_pixel_manifest_sha256=fx["pixels_sha"],
        source_sprite_ids=[fx["source_id"]], target_assets_root=fx["provider"],
        provider_assets={fx["source_id"]: {"assetPath": fx["target_path"]}}, output_path=out)
    args.update(overrides)
    return plan_packed_atlas_rebind(**args)


def test_neutral_explicit_relocation_and_texture_only_contract(tmp_path):
    fx = fixture(tmp_path)
    geometry = fx["geometry"]
    with patch("grea.recovery.unity_prefab_atlas_assets.rectangle_atlas_geometry", return_value=geometry):
        plan = run_plan(fx, tmp_path / "out/plan.json")
    row = plan["assets"][0]
    assert plan["status"] == "planned-not-applied"
    assert row["providerAsset"]["guid"] == "1" * 32
    assert row["providerAsset"]["localId"] == 21300000
    assert row["providerAsset"]["targetMeshPreserved"] is True
    assert row["sourceRenderDataKey"][1] == 21300000
    assert row["pixelPngSha256"] == digest(b"neutral-png-payload")
    assert row["operation"]["fields"] == ["m_RD.texture", "m_AtlasRD.texture"]
    assert plan["nativeEditorApplied"] is False


def test_rejects_manifest_pin_drift(tmp_path):
    fx = fixture(tmp_path)
    with pytest.raises(Exception, match="ATLAS_ASSET_PIN_DRIFT"):
        run_plan(fx, tmp_path / "out/plan.json", expected_manifest_sha256="0" * 64)


def test_rejects_ambiguous_exact_render_key(tmp_path):
    fx = fixture(tmp_path)
    graph_path = fx["candidate"] / "Analysis/Evidence/source-graph.json"
    graph = json.loads(graph_path.read_text())
    atlas = next(o for o in graph["reachableObjects"] if o["type"] == "SpriteAtlas")
    atlas["data"]["m_RenderDataMap"].append(atlas["data"]["m_RenderDataMap"][0])
    graph_sha = dump(graph_path, graph)
    manifest_path = fx["candidate"] / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    row = next(x for x in manifest["files"] if x["path"] == "Analysis/Evidence/source-graph.json")
    row.update(sha256=graph_sha, bytes=graph_path.stat().st_size)
    fx["manifest_sha"] = dump(manifest_path, manifest)
    with patch("grea.recovery.unity_prefab_atlas_assets.rectangle_atlas_geometry", return_value=fx["geometry"]):
        with pytest.raises(Exception, match="ATLAS_ASSET_RENDER_KEY"):
            run_plan(fx, tmp_path / "out/plan.json")


def test_rejects_target_path_substitution_or_missing_binding(tmp_path):
    fx = fixture(tmp_path)
    with patch("grea.recovery.unity_prefab_atlas_assets.rectangle_atlas_geometry", return_value=fx["geometry"]):
        with pytest.raises(Exception, match="ATLAS_ASSET_TARGET_SELECTION"):
            run_plan(fx, tmp_path / "out/plan.json", provider_assets={})


def test_rejects_missing_pixel_crosswalk(tmp_path):
    fx = fixture(tmp_path)
    p = fx["pixels_manifest"]
    data = json.loads(p.read_text())
    data["textures"][0]["source"]["pathId"] = "999"
    fx["pixels_sha"] = dump(p, data)
    with patch("grea.recovery.unity_prefab_atlas_assets.rectangle_atlas_geometry", return_value=fx["geometry"]):
        with pytest.raises(Exception, match="ATLAS_ASSET_PIXEL_CROSSWALK"):
            run_plan(fx, tmp_path / "out/plan.json")


def test_rejects_already_modified_native_target(tmp_path):
    fx = fixture(tmp_path)
    target = fx["provider"] / fx["target_path"]
    target.write_text(target.read_text().replace("0000000deadbeef15deadf00d0000000", "2" * 32))
    manifest_path = fx["candidate"] / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    row = next(x for x in manifest["files"] if x["path"] == fx["target_path"])
    row.update(sha256=digest(target.read_bytes()), bytes=target.stat().st_size)
    fx["manifest_sha"] = dump(manifest_path, manifest)
    with patch("grea.recovery.unity_prefab_atlas_assets.rectangle_atlas_geometry", return_value=fx["geometry"]):
        with pytest.raises(Exception, match="ATLAS_ASSET_TARGET_REBIND"):
            run_plan(fx, tmp_path / "out/plan.json")


def test_rejects_second_write_to_same_evidence_path(tmp_path):
    fx = fixture(tmp_path)
    with patch("grea.recovery.unity_prefab_atlas_assets.rectangle_atlas_geometry", return_value=fx["geometry"]):
        out = tmp_path / "out/plan.json"
        run_plan(fx, out)
        with pytest.raises(Exception, match="ATLAS_ASSET_OUTPUT_EXISTS"):
            run_plan(fx, out)
