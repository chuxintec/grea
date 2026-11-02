"""Native-only reconstruction of explicitly selected, source-proven Sprite assets."""
from pathlib import Path
import os
import shutil
import subprocess

from . import __version__
from .io import inside, safe, read, load, sha, encoded, write_json, new_output
from .sources.compiled import fail
from .unity_prefab_embedded_assets import plan_embedded_sprite_rebuild
from .unity_sprite import unpacked_tight_geometry

REQUEST = 'monkey-unity-prefab-native-assets-request/1'
CONTRACT = 'monkey-unity-prefab-native-assets/1'


def _pin(path):
    raw = read(path, max_bytes=128 * 1024 * 1024)
    return dict(path=str(path), sha256=sha(raw), bytes=len(raw))


def _files(root, scopes):
    return [dict(path=p.relative_to(root).as_posix(), sha256=sha(read(p, max_bytes=128 * 1024 * 1024)), bytes=p.stat().st_size)
            for scope in scopes for p in sorted((root / scope).rglob('*')) if p.is_file()]


def _run(project, editor, plan, label, budget):
    rows = subprocess.check_output(['ps', '-axo', 'pid=,comm='], text=True).splitlines()
    if any(r.strip().endswith(('/Contents/MacOS/Unity', '/Contents/MacOS/CocosCreator', '/Unity.exe', '/CocosCreator.exe')) for r in rows):
        fail('UNITY_PREFAB_EDITOR_BUSY', '$', 'Another main Editor is running')
    plan_path = project / 'Analysis' / (label + '-plan.json')
    result_path = project / 'Analysis' / (label + '-readback.json')
    plan = dict(plan, reopenOnly=label == 'cold', outputAbsolute=str(result_path))
    write_json(plan_path, plan)
    env = dict(os.environ, MONKEY_UNITY_EMBEDDED_PLAN=str(plan_path), MONKEY_UNITY_EMBEDDED_PLAN_SHA256=sha(read(plan_path)))
    stage = project.parent
    result = dict(label=label, plan=_pin(plan_path), graphics='not_run_headless', sourceCodeExecuted=False)
    child = None
    try:
        with (stage / (label + '-console.log')).open('wb') as log:
            child = subprocess.Popen([str(editor), '-batchmode', '-nographics', '-quit', '-projectPath', str(project),
                '-executeMethod', 'MonkeyUnitySource.UnityPrefabEmbeddedAssets.Run', '-logFile', str(stage / (label + '-editor.log'))],
                cwd=project, env=env, stdout=log, stderr=subprocess.STDOUT)
            result['pid'] = child.pid
            try:
                child.wait(timeout=budget)
            except subprocess.TimeoutExpired:
                result['stopReason'] = 'fixed-owned-process-budget'
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
        result.update(processExited=child is not None and child.poll() is not None,
                      exitCode=child.poll() if child is not None else None)
        if result_path.is_file():
            result['readback'] = _pin(result_path)
        write_json(stage / (label + '-process.json'), result)
    if not result['processExited'] or result['exitCode'] != 0 or not result_path.is_file():
        fail('UNITY_PREFAB_ASSET_NATIVE_FAILED', label, 'Owned native asset process did not complete; retain attempt')
    native = load(read(result_path, max_bytes=64 * 1024 * 1024), max_nodes=2_000_000)
    if native.get('status') != 'completed' or native.get('error') or not native.get('assets') or any(a.get('verified') is not True for a in native['assets']):
        fail('UNITY_PREFAB_ASSET_NATIVE_FAILED', label, 'Native source geometry/pixels did not verify')
    return result, native


def execute(request_path, expected_request, output, editor, budget_seconds=600):
    from .unity_prefab_recovery import pinned
    from .normalize import open_texture
    request_path, raw = pinned(dict(path=str(request_path), sha256=expected_request))
    request = load(raw)
    if request.get('contract') != REQUEST or request.get('schemaVersion') != 1:
        fail('UNITY_PREFAB_ASSET_REQUEST', '$', 'Exact native Sprite request required')
    candidate = safe(request['candidate']['path'])
    _, manifest_raw = pinned(dict(path=str(candidate / 'manifest.json'), sha256=request['candidate']['manifestSha256']))
    manifest = load(manifest_raw)
    if manifest.get('contract') != 'monkey-unity-prefab-recovery/1' or manifest.get('targetProfile') != 'unity-6000.6.2f1-ugui':
        fail('UNITY_PREFAB_ASSET_CANDIDATE', '$', 'Exact source Prefab candidate required')
    for row in manifest['files']:
        pinned(dict(row, path=str(inside(candidate, row['path']))), 128 * 1024 * 1024)
    graph_path = candidate / 'Analysis/Evidence/source-graph.json'
    source_path = candidate / 'Analysis/Evidence/source-inputs.json'
    graph = load(read(graph_path, max_bytes=64 * 1024 * 1024), max_nodes=8_000_000)
    objects = {o['sourceObjectId']: o for o in graph['reachableObjects']}
    selected = request.get('spriteSourceIds')
    if (not isinstance(selected, list) or not 1 <= len(selected) <= 64 or any(not isinstance(s, str) for s in selected)
            or len(set(selected)) != len(selected) or any(s not in objects or objects[s]['type'] != 'Sprite' for s in selected)):
        fail('UNITY_PREFAB_ASSET_SELECTION', '$', 'Select 1..64 distinct exact source Sprite IDs')
    pins = load(read(candidate / 'Analysis/Evidence/request-evidence.json')).get('providerHydration')
    atlas_mode = 'atlasPixelManifest' in request
    if not pins and not atlas_mode:
        fail('UNITY_PREFAB_ASSET_LINEAGE', '$', 'Candidate must retain prepared hydration/job pins')
    if not atlas_mode:
        prepared_path, prepared_raw = pinned(pins['prepared'])
        job_path, _ = pinned(pins['prepareJob'])
        prepared = load(prepared_raw, max_nodes=8_000_000)
    editor = safe(editor)
    if not editor.is_file() or editor.name not in ('Unity', 'Unity.exe') or type(budget_seconds) is not int or not 1 <= budget_seconds <= 1200:
        fail('UNITY_PREFAB_ASSET_EDITOR', '$', 'Exact existing Editor and bounded budget required')
    out = new_output(output, [candidate, editor, request_path])
    project = out / 'UnityProject'
    (project / 'Assets/Editor').mkdir(parents=True)
    (project / 'ProjectSettings').mkdir()
    (project / 'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.6.2f1\n')
    write_json(project / 'Packages/manifest.json', dict(dependencies={}))
    helper = Path(__file__).parent / 'targets/unity_source/UnityPrefabEmbeddedAssets.cs'
    shutil.copyfile(helper, project / 'Assets/Editor/UnityPrefabEmbeddedAssets.cs')
    specs, plans, textures, total_pixels = [], [], set(), 0
    if atlas_mode:
        from .unity_prefab_atlas_rebuild import stage_atlas_specs
        specs, plans = stage_atlas_specs(request, candidate, sha(manifest_raw), out, project, objects, selected)
    else:
        for sid in selected:
            sprite = objects[sid]
            data, identity = sprite['data'], sprite['identity']
            edges = [e for e in sprite['referenceEdges'] if e['location'] == '$/m_RD/texture' and e['status'] == 'resolved']
            if len(edges) != 1:
                fail('UNITY_PREFAB_ASSET_TEXTURE', sid, 'One exact local source texture required')
            texture_sid = edges[0]['targetSourceObjectId']
            if texture_sid in textures:
                fail('UNITY_PREFAB_ASSET_SHARED_TEXTURE', sid, 'This bounded increment requires distinct source textures; do not duplicate one source identity')
            textures.add(texture_sid)
            texture = objects[texture_sid]
            tex = texture['data']
            rows = [r for c in prepared['rows'] if c['source']['sha256'] == identity['containerSha256'] for r in c.get('resolved', [])
                    if r['file'] == identity['serializedFile'] and r['pathId'] == texture['identity']['pathId']]
            if len(rows) != 1:
                fail('UNITY_PREFAB_ASSET_HYDRATION', sid, 'Exact original texture hydration is missing or ambiguous')
            geometry = unpacked_tight_geometry(data, tex['m_Width'], tex['m_Height'], data['m_PixelsToUnits'], pixel_sha256=rows[0]['rgbaRawSha256'])
            gp = out / 'Evidence' / (sha(encoded(identity)) + '-geometry.json')
            write_json(gp, geometry)
            plan = plan_embedded_sprite_rebuild(source_graph_path=graph_path, source_graph_sha256=sha(read(graph_path, max_bytes=64 * 1024 * 1024)),
                source_inputs_path=source_path, source_inputs_sha256=sha(read(source_path)), prepared_path=prepared_path, prepared_sha256=pins['prepared']['sha256'],
                prepare_job_path=job_path, prepare_job_sha256=pins['prepareJob']['sha256'], source_sprite_identity=dict(identity, rawSha256=sprite['rawSha256']),
                source_settings_raw=64, geometry_descriptor_path=gp, geometry_descriptor_sha256=sha(read(gp)))
            cache = plan['sourceTextureHydration']
            cache_raw = read(safe(cache['cachePath']), max_bytes=4 * 1024 * 1024)
            if sha(cache_raw) != cache['cacheSha256']:
                fail('UNITY_PREFAB_ASSET_CACHE_DRIFT', sid, 'Original cached pixels changed')
            image = open_texture(cache_raw, '.astc').convert('RGBA')
            pixels = image.tobytes()
            total_pixels += image.width * image.height
            if image.size != (tex['m_Width'], tex['m_Height']) or sha(pixels) != cache['rgbaRawSha256'] or total_pixels > 16 * 1024 * 1024:
                fail('UNITY_PREFAB_ASSET_PIXELS', sid, 'Decoded source dimensions/pixels or total budget differ')
            pixel_path = 'Analysis/SourcePixels/' + plan['identityKeySha256'] + '.rgba'
            dest = inside(project, pixel_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(pixels)
            settings = tex['m_TextureSettings']
            rd = data['m_RD']
            specs.append(dict(sourceId=sid, textureSourceId=texture_sid, texturePath=plan['target']['texturePath'], spritePath=plan['target']['spriteAssetPath'],
                rgbaPath=pixel_path, rgbaSha256=sha(pixels), spriteName=data['m_Name'], textureName=tex['m_Name'], width=image.width, height=image.height,
                sourceColorSpace=tex['m_ColorSpace'], filterMode=settings['m_FilterMode'], aniso=settings['m_Aniso'], wrapU=settings['m_WrapU'],
                wrapV=settings['m_WrapV'], wrapW=settings['m_WrapW'], mipBias=settings['m_MipBias'], pixelsToUnits=data['m_PixelsToUnits'],
                extrude=data['m_Extrude'], rect=data['m_Rect'], pivot=data['m_Pivot'], border=data['m_Border'], offset=data['m_Offset'],
                textureRect=rd['textureRect'], textureRectOffset=rd['textureRectOffset'], atlasRectOffset=rd['atlasRectOffset'], uvTransform=rd['uvTransform'],
                vertexBytesBase64=rd['m_VertexData']['m_DataSize']['base64'], indexBytes=rd['m_IndexBuffer'], channels=rd['m_VertexData']['m_Channels'],
                subMeshes=rd['m_SubMeshes'], meshVertices=geometry['meshVertices'], triangleIndices=geometry['triangleIndices'], meshUv=geometry['meshUv']))
            plans.append(plan)
    plan = dict(schemaVersion=1, targetUnityVersion='6000.6.2f1', allowSharedTextures=atlas_mode, assets=specs)
    first_process, first = _run(project, editor, plan, 'first', budget_seconds)
    before = _files(project, ['Assets', 'Packages', 'ProjectSettings'])
    cold_process, cold = _run(project, editor, plan, 'cold', budget_seconds)
    if first_process['pid'] == cold_process['pid'] or before != _files(project, ['Assets', 'Packages', 'ProjectSettings']):
        fail('UNITY_PREFAB_ASSET_COLD_DRIFT', str(out), 'Cold process identity or saved bytes changed')
    first_rows = {a['sourceId']: a for a in first['assets']}
    cold_rows = {a['sourceId']: a for a in cold['assets']}
    if set(first_rows) != set(selected) or set(cold_rows) != set(selected) or first_rows != cold_rows:
        fail('UNITY_PREFAB_ASSET_COLD_IDENTITY', str(out), 'Exact source/native asset records differ across processes')
    artifact = out / 'Candidate'
    mappings = []
    mapped_ids = set()
    for spec in specs:
        actual = first_rows[spec['sourceId']]
        for sid, path, prefix, typ in [(spec['sourceId'], spec['spritePath'], 'sprite', 'Sprite'), (spec['textureSourceId'], spec['texturePath'], 'texture', 'Texture2D')]:
            if sid in mapped_ids:
                continue
            mapped_ids.add(sid)
            for rel in (path, path + '.meta'):
                target = inside(artifact, rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(inside(project, rel), target)
            source = objects[sid]
            mappings.append(dict(sourceObjectId=sid, rawSha256=source['rawSha256'], sourceDataSha256=sha(encoded(source['data'])),
                type=typ, path=path, guid=actual[prefix + 'Guid'], localId=actual[prefix + 'LocalId'],
                textureSourceId=spec['textureSourceId'], rgbaRawSha256=spec['rgbaSha256']))
            if prefix == 'sprite' and spec.get('preserveExistingSprite'):
                planned = next(a for a in plans[0]['assets'] if a['sourceSpriteId'] == sid)
                mappings[-1]['replacesProviderAsset'] = dict(path=path, assetSha256=spec['sourceBeforeAssetSha256'],
                    providerPath=planned['providerAsset']['originalPath'],
                    metaSha256=spec['sourceBeforeMetaSha256'], guid=spec['expectedSpriteGuid'], localId=int(spec['expectedSpriteLocalId']))
    evidence = artifact / 'Analysis/Evidence'
    evidence.mkdir(parents=True)
    for path, name in [(request_path, 'request.json'), (graph_path, 'source-graph.json'), (source_path, 'source-inputs.json'),
                       (project / 'Analysis/first-readback.json', 'native-first.json'), (project / 'Analysis/cold-readback.json', 'native-cold.json'),
                       (out / 'first-process.json', 'first-process.json'), (out / 'cold-process.json', 'cold-process.json')]:
        shutil.copyfile(path, evidence / name)
    write_json(evidence / 'rebuild-plans.json', plans)
    write_json(evidence / 'native-plan.json', plan)
    if atlas_mode:
        shutil.copytree(out / 'AtlasPixelEvidence', evidence / 'selected-atlas-pixels')
    files = _files(artifact, ['Assets', 'Analysis'])
    result = dict(schemaVersion=1, contract=CONTRACT, toolVersion=__version__, status='native-assets-verified-subset',
        targetVersion='6000.6.2f1', sourceVersion='2021.3.30f1', files=files, mappings=mappings, firstProcess=first_process, coldProcess=cold_process,
        helperSha256=sha(read(helper)), requestSha256=expected_request, sourceCandidateManifestSha256=sha(manifest_raw),
        nativeIdentityAndBytesStable=True, visual='not_run_headless', sourceCodeExecuted=False,
        assetProfile='preserved-rectangle-atlas' if atlas_mode else 'new-unpacked-tight',
        normalization=['source ASTC decoded to CPU-readable RGBA32/no-mip Texture2D', 'new native GUID/localID; original render-data key is evidence only'])
    if atlas_mode:
        result['normalization'] = ['selected original atlas PNG decoded back to pinned bottom-up RGBA32/no-mip Texture2D',
            'existing Sprite GUID/localID/meta and serialized geometry preserved; only native texture references rebound']
    write_json(artifact / 'manifest.json', result)
    write_json(out / 'result.json', dict(status=result['status'], candidate=str(artifact), manifestSha256=sha(read(artifact / 'manifest.json')), visual='not_run_headless'))
    return load(read(out / 'result.json'))


def load_supplement(pin, graph, lineage):
    """Verify a native-created resource closure against freshly selected source IDs."""
    from .unity_prefab_recovery import pinned
    from .native_selection import _guid_meta
    manifest_path, raw = pinned(pin)
    root = manifest_path.parent
    result = load(raw)
    if (result.get('contract') != CONTRACT or result.get('status') != 'native-assets-verified-subset'
            or result.get('targetVersion') != '6000.6.2f1' or result.get('sourceVersion') != '2021.3.30f1'
            or result.get('nativeIdentityAndBytesStable') is not True):
        fail('UNITY_PREFAB_ASSET_SUPPLEMENT', str(root), 'Actual independently reopened native source assets required')
    for process in [result['firstProcess'], result['coldProcess']]:
        if process.get('processExited') is not True or process.get('exitCode') != 0:
            fail('UNITY_PREFAB_ASSET_SUPPLEMENT', str(root), 'Both native asset processes must have exited normally')
    if result['firstProcess']['pid'] == result['coldProcess']['pid']:
        fail('UNITY_PREFAB_ASSET_SUPPLEMENT', str(root), 'Independent native process identities required')
    owned = {r['path']: r for r in result['files']}
    if len(owned) != len(result['files']):
        fail('UNITY_PREFAB_ASSET_SUPPLEMENT', str(root), 'Duplicate native ownership paths')
    for row in result['files']:
        pinned(dict(row, path=str(inside(root, row['path']))), 128 * 1024 * 1024)
    reports = []
    for label, process in [('first', result['firstProcess']), ('cold', result['coldProcess'])]:
        path = root / ('Analysis/Evidence/native-' + label + '.json')
        report_raw = read(path, max_bytes=64 * 1024 * 1024)
        if sha(report_raw) != process['readback']['sha256'] or len(report_raw) != process['readback']['bytes']:
            fail('UNITY_PREFAB_ASSET_SUPPLEMENT', label, 'Native report differs from exited process receipt')
        report = load(report_raw, max_nodes=2_000_000)
        if report.get('status') != 'completed' or report.get('error') or any(a.get('verified') is not True for a in report['assets']):
            fail('UNITY_PREFAB_ASSET_SUPPLEMENT', label, 'Actual native source assets did not verify')
        rows = {a['sourceId']: a for a in report['assets']}
        if len(rows) != len(report['assets']):
            fail('UNITY_PREFAB_ASSET_SUPPLEMENT', label, 'Duplicate native source asset identities')
        reports.append(rows)
    if not reports[0] or reports[0] != reports[1]:
        fail('UNITY_PREFAB_ASSET_SUPPLEMENT', '$', 'Actual first/cold asset identities or data differ')
    atlas_mode = result.get('assetProfile') == 'preserved-rectangle-atlas'
    pixel_evidence = None
    if atlas_mode:
        pixel_manifest = root / 'Analysis/Evidence/selected-atlas-pixels/manifest.json'
        pixel_evidence = load(read(pixel_manifest))
        plans = load(read(root / 'Analysis/Evidence/rebuild-plans.json', max_bytes=64 * 1024 * 1024))
        if (len(plans) != 1 or plans[0].get('selectedPixelManifestSha256') != sha(read(pixel_manifest))
                or pixel_evidence.get('contract') != 'unity-selected-texture-export/1'
                or pixel_evidence.get('status') != 'exported'):
            fail('UNITY_PREFAB_ASSET_SOURCE_PIXELS', '$', 'Pinned selected original atlas pixel evidence required')
    objects = {o['sourceObjectId']: o for o in graph['reachableObjects']}
    mappings = []
    seen = set()
    for row in result['mappings']:
        source = objects.get(row['sourceObjectId'])
        if source is None or source['type'] != row['type'] or source['rawSha256'] != row['rawSha256'] or sha(encoded(source['data'])) != row['sourceDataSha256']:
            fail('UNITY_PREFAB_ASSET_SOURCE_IDENTITY', row['sourceObjectId'], 'Native supplement differs from exact selected source object')
        if row['path'] not in owned or row['path'] + '.meta' not in owned or _guid_meta(inside(root, row['path'] + '.meta')) != row['guid']:
            fail('UNITY_PREFAB_ASSET_SUPPLEMENT', row['path'], 'Native resource GUID/owned file proof differs')
        if row['sourceObjectId'] in seen or row['type'] not in ('Sprite', 'Texture2D') or not row['path'].startswith('Assets/') or not row['path'].endswith('.asset'):
            fail('UNITY_PREFAB_ASSET_SUPPLEMENT', row['path'], 'Unique typed native asset mapping required')
        seen.add(row['sourceObjectId'])
        prefix = 'sprite' if row['type'] == 'Sprite' else 'texture'
        actual = [a for a in reports[0].values() if a['sourceId' if prefix == 'sprite' else 'textureSourceId'] == row['sourceObjectId']]
        if (not actual or ((prefix == 'sprite' or not atlas_mode) and len(actual) != 1)
                or any(a[prefix + 'Guid'] != row['guid'] or a[prefix + 'LocalId'] != row['localId']
                       or a[prefix + 'Path'] != row['path'] or a['pixelSha256'] != row['rgbaRawSha256'] for a in actual)):
            fail('UNITY_PREFAB_ASSET_SUPPLEMENT', row['path'], 'Mapping differs from actual source/native readback')
        if atlas_mode and prefix == 'sprite':
            before = row.get('replacesProviderAsset', {})
            a = actual[0]
            planned = [p for p in plans[0].get('assets', []) if p.get('sourceSpriteId') == row['sourceObjectId']]
            original = planned[0].get('providerAsset', {}) if len(planned) == 1 else {}
            if (before.get('path') != row['path'] or before.get('guid') != row['guid']
                    or str(before.get('localId')) != str(row['localId'])
                    or before.get('providerPath') != original.get('originalPath')
                    or before.get('assetSha256') != original.get('assetSha256')
                    or before.get('metaSha256') != original.get('metaSha256')
                    or a.get('spriteIdentityDisposition') != 'preserved-existing-provider'
                    or a.get('sourceBeforeAssetSha256') != before.get('assetSha256')
                    or a.get('sourceBeforeMetaSha256') != before.get('metaSha256')):
                fail('UNITY_PREFAB_ASSET_PRESERVED_IDENTITY', row['path'], 'Actual preserved GUID/localID and before-byte evidence required')
        texture = objects.get(row['textureSourceId'])
        if texture is None:
            fail('UNITY_PREFAB_ASSET_SOURCE_IDENTITY', row['path'], 'Exact source texture is absent')
        identity = texture['identity']
        if atlas_mode:
            hydrated = [p['hydration'] for p in pixel_evidence.get('textures', [])
                if pixel_evidence['inputPins']['source'] == identity['containerSha256']
                and p['source']['file'] == identity['serializedFile'] and p['source']['pathId'] == identity['pathId']
                and p['source']['sourceRawSha256'] == texture['rawSha256']]
        else:
            hydrated = [r for c in lineage['selectedSourceInputs'] if c['originalSha256'] == identity['containerSha256']
                        for r in c.get('textureHydration', []) if r['file'] == identity['serializedFile'] and r['pathId'] == identity['pathId']]
        if len(hydrated) != 1 or hydrated[0]['rgbaRawSha256'] != row['rgbaRawSha256']:
            fail('UNITY_PREFAB_ASSET_SOURCE_PIXELS', row['path'], 'Native supplement differs from current pinned original hydration')
        mappings.append(dict(row, supplementManifestSha256=sha(raw)))
    expected_pairs = {(a['sourceId'], 'Sprite') for a in reports[0].values()} | {(a['textureSourceId'], 'Texture2D') for a in reports[0].values()}
    if {(r['sourceObjectId'], r['type']) for r in mappings} != expected_pairs:
        fail('UNITY_PREFAB_ASSET_SUPPLEMENT', '$', 'Complete Sprite and Texture mapping pairs required')
    return root, result, mappings
