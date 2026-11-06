"""Stage pinned original atlas pixels and existing Sprite identities for native repair."""
import shutil

from .io import inside, safe, read, load, sha, encoded
from .sources.compiled import fail


def stage_atlas_specs(request, candidate, manifest_sha256, out, project, objects, selected):
    from .unity_prefab_atlas_assets import plan_packed_atlas_rebind
    from .unity_prefab_recovery import pinned
    from .normalize import open_texture
    pixel_path, pixel_raw = pinned(request['atlasPixelManifest'])
    pixels = load(pixel_raw)
    target_root = safe(request['providerAssetsRoot'])
    plan = plan_packed_atlas_rebind(candidate_root=candidate, expected_manifest_sha256=manifest_sha256,
        selected_pixel_manifest=pixel_path, selected_pixel_manifest_sha256=sha(pixel_raw),
        source_sprite_ids=selected, target_assets_root=target_root, provider_assets=request['providerAssets'],
        output_path=out / 'Evidence/atlas-rebind-plan.json',
        allow_trimmed_source_correction=request.get('allowTrimmedSourceCorrection', False))
    specs, seen, total = [], {}, 0
    for row in plan['assets']:
        sid = row['sourceSpriteId']
        source = objects[sid]
        data = source['data']
        texture_rows = [o for o in objects.values() if o['identity'] == row['sourceTextureIdentity']]
        if len(texture_rows) != 1:
            fail('UNITY_PREFAB_ATLAS_TEXTURE', sid, 'Unique exact source texture identity required')
        texture = texture_rows[0]
        tid, tex = texture['sourceObjectId'], texture['data']
        png = inside(pixel_path.parent, row['pixelPngPath'])
        raw = read(png, max_bytes=128 * 1024 * 1024)
        if sha(raw) != row['pixelPngSha256']:
            fail('UNITY_PREFAB_ATLAS_PIXELS', sid, 'Selected PNG changed after planning')
        matches = [p for p in pixels['textures'] if p['target']['path'] == row['pixelPngPath']]
        if len(matches) != 1 or matches[0]['target']['pixelOrientation'] != 'vertical-flip-for-unity':
            fail('UNITY_PREFAB_ATLAS_PIXELS', sid, 'Exact selected PNG orientation required')
        # Selected PNG exports are top-down. Native LoadRawTextureData expects
        # the original bottom-up byte order pinned by rgbaRawSha256.
        image = open_texture(raw, '.png').convert('RGBA')
        from PIL import Image
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        rgba = image.tobytes()
        if image.size != (tex['m_Width'], tex['m_Height']) or sha(rgba) != row['textureRgbaRawSha256']:
            fail('UNITY_PREFAB_ATLAS_PIXELS', sid, 'Decoded original RGBA/dimensions differ')
        key = sha(encoded(texture['identity']))
        rgba_rel = 'Analysis/SourcePixels/' + key + '.rgba'
        texture_path = 'Assets/SourceAtlas/atlas-' + key + '.asset'
        if tid not in seen:
            total += image.width * image.height
            if total > 16 * 1024 * 1024:
                fail('UNITY_PREFAB_ATLAS_BUDGET', sid, 'Total distinct texture pixel budget exceeded')
            dest = inside(project, rgba_rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(rgba)
            seen[tid] = sha(rgba)
        elif seen[tid] != sha(rgba):
            fail('UNITY_PREFAB_ATLAS_SHARED_PIXELS', sid, 'Shared texture identity has conflicting pixels')
        before = row['providerAsset']
        for rel, expected in [(before['path'], before['assetSha256']), (before['path'] + '.meta', before['metaSha256'])]:
            source_path = inside(target_root, rel)
            source_raw = read(source_path, max_bytes=128 * 1024 * 1024)
            if sha(source_raw) != expected:
                fail('UNITY_PREFAB_ATLAS_BEFORE_DRIFT', rel, 'Before-pinned provider bytes changed')
            dest = inside(project, rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(source_raw)
        settings, rd, geometry = tex['m_TextureSettings'], data['m_RD'], row['geometry']
        atlas = row['atlasRenderData']
        specs.append(dict(sourceId=sid, textureSourceId=tid, preserveExistingSprite=True,
            expectedSpriteGuid=before['guid'], expectedSpriteLocalId=str(before['localId']),
            sourceBeforeAssetSha256=before['assetSha256'], sourceBeforeMetaSha256=before['metaSha256'],
            sourcePackedSettingsRaw=atlas['settingsRaw'], expectedNativeSpriteSettingsRaw=3139,
            texturePath=texture_path, spritePath=before['path'],
            rgbaPath=rgba_rel, rgbaSha256=sha(rgba), spriteName=data['m_Name'], textureName=tex['m_Name'],
            width=image.width, height=image.height, sourceColorSpace=tex['m_ColorSpace'],
            filterMode=settings['m_FilterMode'], aniso=settings['m_Aniso'], wrapU=settings['m_WrapU'],
            wrapV=settings['m_WrapV'], wrapW=settings['m_WrapW'], mipBias=settings['m_MipBias'],
            pixelsToUnits=data['m_PixelsToUnits'], extrude=data['m_Extrude'], rect=geometry.get('targetRect', geometry.get('atlasRect')),
            pivot=data['m_Pivot'], border=data['m_Border'], offset=data['m_Offset'],
            textureRect=atlas['textureRect'], textureRectOffset=atlas['textureRectOffset'],
            atlasRectOffset=atlas['atlasRectOffset'], uvTransform=atlas['uvTransform'],
            vertexBytesBase64=rd['m_VertexData']['m_DataSize']['base64'], indexBytes=rd['m_IndexBuffer'],
            channels=rd['m_VertexData']['m_Channels'], subMeshes=rd['m_SubMeshes'],
            meshVertices=geometry['meshVertices'], triangleIndices=geometry['triangleIndices'], meshUv=geometry['meshUv']))
        specs[-1]['physicsShapes'] = [dict(vertices=points) for points in data.get('m_PhysicsShape', [])]
        if geometry.get('geometryProfile') == 'unity-2021.3-trimmed-unrotated-rectangle-atlas-v1':
            specs[-1].update(geometryCorrectionProfile='trimmed-unrotated-source-derived-v1',
                sourceLogicalRect=geometry['sourceRect'], providerBeforeGeometry=before['providerBeforeGeometry'])
    evidence = out / 'AtlasPixelEvidence'
    evidence.mkdir()
    shutil.copyfile(pixel_path, evidence / 'manifest.json')
    for row in pixels['files']:
        dest = inside(evidence, row['path'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(inside(pixel_path.parent, row['path']), dest)
    return specs, [plan]
