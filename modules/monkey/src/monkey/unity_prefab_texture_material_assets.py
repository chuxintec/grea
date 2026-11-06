"""Plan a source-selected Texture2D + Material native closure.

This module pins original source graph identities, selected decoded pixels and an
existing relocated Material. It never edits candidate/provider files or Unity YAML.
"""
from pathlib import Path
import re

from .io import encoded, inside, load, read, sha, write_json
from .sources.compiled import fail

CONTRACT = 'monkey-unity-prefab-texture-material-plan/1'
MAX_GRAPH = 64 * 1024 * 1024
MAX_ASSET = 16 * 1024 * 1024
MAX_PIXELS = 16 * 1024 * 1024
MAX_TEXTURES = 64
GUID_RE = re.compile(rb'(?m)^guid: ([0-9a-f]{32})\s*$')
MAT_ID_RE = re.compile(rb'(?m)^--- !u!21 &(-?[0-9]+)\s*$')
MAT_NAME_RE = re.compile(rb'(?m)^\s*m_Name:\s*([^\r\n]+)\s*$')
SHADER_GUID_RE = re.compile(rb'(?m)^\s*m_Shader:\s*\{[^}]*guid: ([0-9a-f]{32})[^}]*\}\s*$')
SHADER_ID_RE = re.compile(rb'(?m)^--- !u!48 &(-?[0-9]+)\s*$')


def _need(ok, code, loc, message):
    if not ok:
        fail(code, str(loc), message)


def _pin(path, expected, maximum=MAX_GRAPH):
    raw = read(path, max_bytes=maximum)
    _need(sha(raw) == expected, 'TEXTURE_MATERIAL_PIN_DRIFT', path, 'Pinned input bytes changed')
    return raw


def _owned(manifest, rel, raw):
    rows = [r for r in manifest.get('files', []) if r.get('path') == rel]
    _need(len(rows) == 1 and rows[0].get('sha256') == sha(raw) and rows[0].get('bytes') == len(raw),
          'TEXTURE_MATERIAL_CANDIDATE_PIN', rel, 'Candidate manifest does not own exact evidence bytes')


def _identity(asset_path, meta_path):
    asset = read(asset_path, MAX_ASSET)
    meta = read(meta_path, 1024 * 1024)
    guids, ids, shader_guids, names = GUID_RE.findall(meta), MAT_ID_RE.findall(asset), SHADER_GUID_RE.findall(asset), MAT_NAME_RE.findall(asset)
    _need(len(guids) == 1 and len(ids) == 1 and len(shader_guids) == 1 and len(names) == 1, 'TEXTURE_MATERIAL_TARGET_IDENTITY', asset_path,
          'Unique native Material GUID and local fileID required')
    return asset, meta, guids[0].decode('ascii'), int(ids[0]), shader_guids[0].decode('ascii'), names[0].decode('utf-8').strip()


def _source_id(objects, raw_id, typ, loc):
    obj = objects.get(raw_id)
    _need(obj is not None and obj.get('type') == typ, 'TEXTURE_MATERIAL_SOURCE_OBJECT', loc,
          f'Exact source {typ} object required')
    return obj


def _source_edge(graph, sid, location):
    rows = [e for e in graph.get('referenceEdges', []) if e.get('sourceObjectId') == sid and e.get('location') == location]
    _need(len(rows) == 1 and rows[0].get('status') == 'resolved', 'TEXTURE_MATERIAL_SOURCE_EDGE', sid,
          'Expected one exact resolved source reference edge')
    return rows[0]


def _native_material_properties(data):
    saved = data.get('m_SavedProperties', {})
    return dict(m_Name=data.get('m_Name'), m_SavedProperties=dict(
        m_Colors=[dict(name=k, value=v) for k, v in saved.get('m_Colors', [])],
        m_Floats=[dict(name=k, value=v) for k, v in saved.get('m_Floats', [])],
        m_Ints=[dict(name=k, value=v) for k, v in saved.get('m_Ints', [])],
        m_TexEnvs=[dict(name=k, scale=v.get('m_Scale'), offset=v.get('m_Offset')) for k, v in saved.get('m_TexEnvs', [])]))


def _shader_closure(candidate, manifest, guid):
    matches = []
    for row in manifest.get('files', []):
        rel = row.get('path')
        if not isinstance(rel, str) or not rel.endswith('.meta') or row.get('bytes', 0) > 1024 * 1024:
            continue
        meta_path = inside(candidate, rel); meta = read(meta_path, 1024 * 1024)
        _owned(manifest, rel, meta)
        if GUID_RE.findall(meta) == [guid.encode('ascii')]: matches.append((rel[:-5], rel, meta))
    _need(len(matches) == 1, 'TEXTURE_MATERIAL_SHADER_CLOSURE', guid,
          'Exact unique candidate-owned native Shader GUID closure required')
    asset_rel, meta_rel, meta = matches[0]
    asset_path = inside(candidate, asset_rel); asset = read(asset_path, MAX_ASSET)
    _owned(manifest, asset_rel, asset)
    ids = SHADER_ID_RE.findall(asset)
    _need(len(ids) == 1, 'TEXTURE_MATERIAL_SHADER_CLOSURE', asset_rel,
          'Candidate Shader asset must have one exact native Shader localID')
    return dict(assetPath=asset_rel, metaPath=meta_rel, guid=guid, localId=int(ids[0]),
                absoluteAssetPath=str(asset_path), absoluteMetaPath=str(inside(candidate, meta_rel)),
                assetSha256=sha(asset), assetBytes=len(asset), metaSha256=sha(meta), metaBytes=len(meta),
                role='candidate-owned-native-shader-closure-only-source-semantic-equivalence-not-claimed')


def plan_texture_material_rebuild(*, candidate_root, expected_manifest_sha256,
                                  selected_pixel_manifest, selected_pixel_manifest_sha256,
                                  source_texture_ids, source_material_ids, provider_assets, output_path):
    """Produce one immutable native execution plan for source Materials and selected pixels.

    ``provider_assets`` maps exact source Material IDs to ``{assetPath: ...}``, and
    each path must be the candidate relocation target. The selected pixel export
    can be container-partial when the exact selected texture is complete; all
    untouched/deferred rows remain pinned as evidence.
    """
    candidate = Path(candidate_root).resolve()
    manifest_raw = _pin(candidate / 'manifest.json', expected_manifest_sha256, 32 * 1024 * 1024)
    manifest = load(manifest_raw)
    _need(manifest.get('contract') == 'monkey-unity-prefab-recovery/1', 'TEXTURE_MATERIAL_CANDIDATE', candidate,
          'Exact Unity Prefab source candidate required')
    graph_path = candidate / 'Analysis/Evidence/source-graph.json'
    inputs_path = candidate / 'Analysis/Evidence/source-inputs.json'
    relocation_path = candidate / 'Analysis/Mappings/unity-relocation.json'
    graph_raw = read(graph_path, MAX_GRAPH); _owned(manifest, 'Analysis/Evidence/source-graph.json', graph_raw)
    inputs_raw = read(inputs_path, 8 * 1024 * 1024); _owned(manifest, 'Analysis/Evidence/source-inputs.json', inputs_raw)
    relocation_raw = read(relocation_path, 16 * 1024 * 1024); _owned(manifest, 'Analysis/Mappings/unity-relocation.json', relocation_raw)
    graph, inputs, relocation = load(graph_raw, 8_000_000), load(inputs_raw, 200_000), load(relocation_raw, 500_000)
    _need(graph.get('contract') == 'monkey-unity-prefab-source-graph/1' and graph.get('sourceUnityVersions') == ['2021.3.30f1'],
          'TEXTURE_MATERIAL_GRAPH', graph_path, 'Exact supported source graph required')
    _need(relocation.get('layout') == 'monkey-project/2.0.0', 'TEXTURE_MATERIAL_RELOCATION', relocation_path,
          'Exact candidate relocation report required')
    pix_path = Path(selected_pixel_manifest).resolve()
    pix_raw = _pin(pix_path, selected_pixel_manifest_sha256, 16 * 1024 * 1024)
    pixels = load(pix_raw, 1_000_000)
    _need(pixels.get('contract') == 'unity-selected-texture-export/1' and pixels.get('nativeImport') == 'not_run'
          and pixels.get('exportComplete') is True and pixels.get('sourceAndDerivativeUnchanged') is True,
          'TEXTURE_MATERIAL_PIXEL_MANIFEST', pix_path, 'Pinned selected-texture export required')
    _need(pixels.get('status') in ('exported', 'partial') and pixels.get('scope') == 'selected-texture-pngs',
          'TEXTURE_MATERIAL_PIXEL_STATUS', pix_path, 'Selected-texture export status is unsupported')
    textures = source_texture_ids
    materials = source_material_ids
    _need(isinstance(textures, list) and 1 <= len(textures) <= MAX_TEXTURES and len(set(textures)) == len(textures),
          'TEXTURE_MATERIAL_SELECTION', '$', 'Select 1..64 unique source Texture2D IDs')
    _need(isinstance(materials, list) and 1 <= len(materials) <= MAX_TEXTURES and len(set(materials)) == len(materials),
          'TEXTURE_MATERIAL_SELECTION', '$', 'Select unique exact source Material IDs')
    _need(isinstance(provider_assets, dict) and set(provider_assets) == set(materials),
          'TEXTURE_MATERIAL_TARGET_SELECTION', '$', 'Exact existing Material relocation required for every selected Material')
    objects = {o['sourceObjectId']: o for o in graph.get('reachableObjects', [])}
    _need(len(objects) == len(graph.get('reachableObjects', [])), 'TEXTURE_MATERIAL_GRAPH', graph_path, 'Duplicate source object IDs')
    pixel_rows = pixels.get('textures', [])
    _need(len(pixel_rows) == len(textures), 'TEXTURE_MATERIAL_PIXEL_SELECTION', '$',
          'Selected pixel manifest must contain exactly the selected Texture2D set')
    selected_specs = {}
    total_pixels = 0
    from PIL import Image
    for tid in textures:
        tex = _source_id(objects, tid, 'Texture2D', tid)
        ident, data = tex['identity'], tex['data']
        _need(ident.get('containerSha256') == pixels.get('inputPins', {}).get('source'),
              'TEXTURE_MATERIAL_PIXEL_SOURCE_PIN', tid, 'Selected pixel source container pin differs')
        matches = [r for r in pixel_rows if r.get('source', {}).get('file') == ident.get('serializedFile')
                   and str(r.get('source', {}).get('pathId')) == str(ident.get('pathId'))
                   and r.get('source', {}).get('sourceRawSha256') == tex.get('rawSha256')]
        _need(len(matches) == 1, 'TEXTURE_MATERIAL_PIXEL_CROSSWALK', tid,
              'Selected pixels must pin exact source serialized file/path/raw tuple')
        row = matches[0]; hydration = row.get('hydration', {}); target = row.get('target', {})
        _need(row.get('source', {}).get('sourceName') == data.get('m_Name')
              and target.get('nativeGuid') == 'not-assigned' and target.get('nativeImport') == 'not_run'
              and hydration.get('rgbaRawSha256') and isinstance(hydration.get('logicalPath'), str),
              'TEXTURE_MATERIAL_PIXEL_IDENTITY', tid, 'Selected source/pixel identity incomplete')
        png_rel = target.get('path')
        _need(isinstance(png_rel, str), 'TEXTURE_MATERIAL_PIXEL_PNG', tid, 'Selected PNG path required')
        png_path = inside(pix_path.parent, png_rel); png_raw = read(png_path, 128 * 1024 * 1024)
        _need(sha(png_raw) == target.get('sha256') and len(png_raw) == target.get('bytes'),
              'TEXTURE_MATERIAL_PIXEL_PNG', tid, 'PNG differs from selected-pixel manifest')
        with Image.open(png_path) as img:
            rgba = img.convert('RGBA')
            _need(rgba.size == (data.get('m_Width'), data.get('m_Height'))
                  and target.get('width') == rgba.width and target.get('height') == rgba.height,
                  'TEXTURE_MATERIAL_PIXEL_DIMENSIONS', tid, 'Selected PNG dimensions differ from source Texture2D')
            rgba = rgba.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            pixel_bytes = rgba.tobytes()
        total_pixels += rgba.width * rgba.height
        _need(total_pixels <= MAX_PIXELS and sha(pixel_bytes) == hydration.get('rgbaRawSha256'),
              'TEXTURE_MATERIAL_PIXEL_HASH', tid, 'Reversed selected PNG pixels differ from hydrated source RGBA')
        file_rows = pixels.get('files', [])
        _need(sum(1 for f in file_rows if f.get('path') == png_rel and f.get('sha256') == sha(png_raw)) == 1,
              'TEXTURE_MATERIAL_PIXEL_OWNERSHIP', tid, 'Selected PNG must be uniquely owned by export manifest')
        if pixels.get('sourceContainerStatus') == 'partial':
            _need(pixels.get('wholeContainerComplete') is False and pixels.get('unselectedObjectsUnchanged') is True,
                  'TEXTURE_MATERIAL_PIXEL_PARTIAL', tid, 'Partial export must retain explicit untouched-object evidence')
        selected_specs[tid] = dict(sourceTextureId=tid, sourceTextureIdentity=ident, sourceTextureRawSha256=tex['rawSha256'],
            sourceTextureDataSha256=sha(encoded(data)),
            textureName=data.get('m_Name'), width=rgba.width, height=rgba.height, rgbaRawSha256=sha(pixel_bytes), rgbaPath='Analysis/SourcePixels/'+tid+'.rgba',
            pngPath=png_rel, pngSha256=sha(png_raw), pngBytes=len(png_raw), sampling=data.get('m_TextureSettings'),
            colorSpace=data.get('m_ColorSpace'), mipCount=data.get('m_MipCount'), sourceContainerStatus=pixels.get('sourceContainerStatus'),
            hydration=dict(logicalPath=hydration['logicalPath'], cacheSha256=hydration.get('cacheSha256'), rgbaRawSha256=hydration['rgbaRawSha256']), _pixelBytes=pixel_bytes)
    provider_root = candidate
    planned = []
    for mid in materials:
        mat = _source_id(objects, mid, 'Material', mid); ident, data = mat['identity'], mat['data']
        inputs_match = [r for r in inputs if r.get('sourceSha256') == ident.get('containerSha256')]
        _need(len(inputs_match) == 1, 'TEXTURE_MATERIAL_SOURCE_INPUT', mid, 'Unique exact original Material bundle input required')
        source_input = inputs_match[0]; source_raw = read(Path(source_input['sourcePath']), 512 * 1024 * 1024)
        _need(sha(source_raw) == source_input['sourceSha256'], 'TEXTURE_MATERIAL_SOURCE_INPUT', mid, 'Original source bundle bytes differ')
        texenvs = data.get('m_SavedProperties', {}).get('m_TexEnvs', [])
        wanted = [(i, value) for i, (name, value) in enumerate(texenvs) if name == '_MainTex']
        _need(len(wanted) == 1, 'TEXTURE_MATERIAL_MAIN_TEX', mid, 'Exactly one source _MainTex entry required')
        main_index, main_value = wanted[0]
        ptr = main_value.get('m_Texture', {})
        _need(ptr.get('$type') == 'UnityPPtr' and isinstance(ptr.get('fileId'), str) and ptr.get('fileId')
              and isinstance(ptr.get('pathId'), str) and ptr.get('pathId'),
              'TEXTURE_MATERIAL_MAIN_TEX', mid, 'Typed _MainTex PPtr requires exact fileId and pathId')
        location = f'$/m_SavedProperties/m_TexEnvs/{main_index}/1/m_Texture'
        edge = _source_edge(graph, mid, location)
        texture_id = edge.get('targetSourceObjectId')
        _need(texture_id in selected_specs and edge.get('fileId') == ptr.get('fileId')
              and str(edge.get('pathId')) == str(ptr.get('pathId')),
              'TEXTURE_MATERIAL_MAIN_TEX', mid, 'Source _MainTex PPtr and unique graph edge disagree')
        binding = provider_assets[mid]
        _need(isinstance(binding, dict) and set(binding) == {'assetPath'}, 'TEXTURE_MATERIAL_TARGET_PATH', mid,
              'Provider material binding must contain only assetPath')
        rel = binding['assetPath']; _need(isinstance(rel, str) and rel.startswith('Assets/') and rel.endswith('.mat'),
              'TEXTURE_MATERIAL_TARGET_PATH', mid, 'Exact relocated candidate Material path required')
        asset_path = inside(provider_root, rel); meta_path = inside(provider_root, rel+'.meta')
        asset, meta, guid, local_id, shader_guid, target_name = _identity(asset_path, meta_path)
        _owned(manifest, rel, asset); _owned(manifest, rel+'.meta', meta)
        moved = [r for r in relocation.get('moves', []) if r.get('target') == rel and r.get('kind') == 'material']
        _need(len(moved) == 1 and moved[0].get('guid') == guid, 'TEXTURE_MATERIAL_RELOCATION', rel,
              'Exact unique candidate Material relocation/GUID required')
        _need(local_id == 2100000, 'TEXTURE_MATERIAL_TARGET_FILEID', rel, 'Existing native Material main localID must be 2100000')
        _need(target_name == data.get('m_Name'), 'TEXTURE_MATERIAL_TARGET_NAME', rel, 'Provider Material name differs from pinned source Material')
        shader_closure = _shader_closure(candidate, manifest, shader_guid)
        _need(b'guid: 0000000deadbeef15deadf00d0000000' in asset,
              'TEXTURE_MATERIAL_TARGET_REBIND', rel, 'Expected dead placeholder texture binding before selected repair')
        shader_edge = _source_edge(graph, mid, '$/m_Shader')
        shader = objects.get(shader_edge.get('targetSourceObjectId'))
        _need(shader is not None and shader.get('type') == 'Shader', 'TEXTURE_MATERIAL_SHADER', mid,
              'Exact original source Shader identity is required as evidence')
        planned.append(dict(sourceMaterialId=mid, sourceMaterialIdentity=ident, sourceMaterialRawSha256=mat['rawSha256'],
            sourceMaterialData=data, nativeSourceMaterialProperties=_native_material_properties(data), sourceMaterialDataSha256=sha(encoded(data)),
            sourceInputPath=source_input['sourcePath'], sourceInputSha256=source_input['sourceSha256'],
            sourceTextureId=texture_id, sourceMainTextureReference=dict(location=location, fileId=ptr['fileId'], pathId=ptr['pathId'], targetSourceObjectId=texture_id),
            texture=selected_specs[texture_id], sourceShaderIdentity=shader['identity'], sourceShaderRawSha256=shader['rawSha256'], candidateShaderClosure=shader_closure,
            providerMaterial=dict(originalPath=moved[0]['source'], assetPath=rel, guid=guid, localId=local_id,
                assetSha256=sha(asset), assetBytes=len(asset), metaSha256=sha(meta), metaBytes=len(meta), shaderGuid=shader_guid, absoluteAssetPath=str(asset_path), absoluteMetaPath=str(meta_path)),
            operation=dict(kind='native-SerializedObject-material-texture-rebind', propertyPath='m_SavedProperties.m_TexEnvs._MainTex.m_Texture',
                preserveExistingMaterialGuidLocalIdMeta=True, preserveShaderAndUnknownFields=True, createTextureGuid='Unity-generated',
                textureNormalization='CPU-readable RGBA32/no-mip', noYamlWrite=True)))
    out = Path(output_path).resolve()
    _need(out != candidate and not out.is_relative_to(candidate) and not candidate.is_relative_to(out),
          'TEXTURE_MATERIAL_OUTPUT_OVERLAP', out, 'Plan output must not overlap candidate')
    _need(not out.exists(), 'TEXTURE_MATERIAL_OUTPUT_EXISTS', out, 'Plan output is immutable; use a fresh path')
    pixel_dir = out.parent / (out.stem + '-pixels')
    _need(not pixel_dir.exists(), 'TEXTURE_MATERIAL_OUTPUT_EXISTS', pixel_dir, 'Pixel staging directory already exists')
    pixel_dir.mkdir(parents=True)
    for spec in selected_specs.values():
        pixel_file = pixel_dir / (sha(spec['sourceTextureId'].encode('utf-8')) + '.rgba')
        pixel_file.write_bytes(spec.pop('_pixelBytes'))
        spec['rgbaAbsolutePath'] = str(pixel_file)
    result = dict(schemaVersion=1, contract=CONTRACT, status='planned-not-applied', sourceVersion='2021.3.30f1',
        targetVersion=manifest.get('targetProfile'), candidateManifestSha256=sha(manifest_raw), sourceGraphSha256=sha(graph_raw),
        sourceInputsSha256=sha(inputs_raw), relocationSha256=sha(relocation_raw), selectedPixelManifestSha256=sha(pix_raw),
        selectedPixelManifestStatus=pixels['status'], selectedPixelWholeContainerComplete=pixels.get('wholeContainerComplete'),
        totalPixels=total_pixels, assets=planned, nativeEditorApplied=False, sourceCodeExecuted=False,
        shaderSemanticSupport='candidate-native-shader-reference-closure-only;source compiled shader and visual equivalence unverified',
        limitation='Plan only; target Material source Shader may be unavailable or semantically unsupported. No Editor import/save/reopen or visual verification was run.')
    write_json(out, result)
    return result
