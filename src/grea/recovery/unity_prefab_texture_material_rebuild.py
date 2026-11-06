"""Owned native execution and verified resource supplements for selected materials."""
from pathlib import Path
import shutil

from . import __version__
from .io import read, load, sha, encoded, inside, safe, new_output, write_json
from .sources.compiled import fail
from .unity_prefab_asset_rebuild import _run, _files

REQUEST = 'monkey-unity-prefab-texture-material-request/1'
CONTRACT = 'monkey-unity-prefab-texture-material-assets/1'


def execute(request_path, expected_request, output, editor, budget_seconds=600):
    from .unity_prefab_recovery import pinned
    from .unity_prefab_texture_material_assets import plan_texture_material_rebuild
    request_path, raw = pinned(dict(path=str(request_path), sha256=expected_request))
    request = load(raw)
    if request.get('contract') != REQUEST or request.get('schemaVersion') != 1:
        fail('UNITY_PREFAB_TEXTURE_MATERIAL_REQUEST', '$', 'Versioned selected material request required')
    candidate = safe(request['candidate']['path'])
    _, manifest_raw = pinned(dict(path=str(candidate / 'manifest.json'), sha256=request['candidate']['manifestSha256']))
    manifest = load(manifest_raw)
    if manifest.get('contract') != 'monkey-unity-prefab-recovery/1' or manifest.get('targetProfile') != 'unity-6000.6.2f1-ugui':
        fail('UNITY_PREFAB_TEXTURE_MATERIAL_CANDIDATE', '$', 'Pinned native-source candidate required')
    for row in manifest['files']:
        pinned(dict(row, path=str(inside(candidate, row['path']))), 128 * 1024 * 1024)
    pixel_path, pixel_raw = pinned(request['selectedPixelManifest'])
    editor = safe(editor)
    if not editor.is_file() or editor.name not in ('Unity', 'Unity.exe') or type(budget_seconds) is not int or not 1 <= budget_seconds <= 1200:
        fail('UNITY_PREFAB_TEXTURE_MATERIAL_EDITOR', '$', 'Exact existing Editor and bounded budget required')
    out = new_output(output, [candidate, pixel_path, request_path, editor])
    plan_path = out / 'Evidence/rebuild-plan.json'
    plan = plan_texture_material_rebuild(candidate_root=candidate, expected_manifest_sha256=sha(manifest_raw),
        selected_pixel_manifest=pixel_path, selected_pixel_manifest_sha256=sha(pixel_raw),
        source_texture_ids=request['textureSourceIds'], source_material_ids=request['materialSourceIds'],
        provider_assets=request['providerAssets'], output_path=plan_path)
    project = out / 'UnityProject'
    (project / 'Assets/Editor').mkdir(parents=True)
    (project / 'ProjectSettings').mkdir()
    (project / 'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.6.2f1\n')
    write_json(project / 'Packages/manifest.json', dict(dependencies={}))
    helper = Path(__file__).parent / 'targets/unity_source/UnityPrefabTextureMaterialAssets.cs'
    shutil.copyfile(helper, project / 'Assets/Editor/UnityPrefabTextureMaterialAssets.cs')
    native_plan = load(encoded(plan), max_nodes=2_000_000)
    for spec in native_plan['assets']:
        texture = spec['texture']
        rgba = read(safe(texture['rgbaAbsolutePath']), max_bytes=64 * 1024 * 1024)
        if sha(rgba) != texture['rgbaRawSha256']:
            fail('UNITY_PREFAB_TEXTURE_MATERIAL_PIXELS', spec['sourceTextureId'], 'Pinned staging pixels changed')
        dest = project / 'Analysis/SourcePixels' / (sha(encoded(spec['sourceTextureId'])) + '.rgba')
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and read(dest, max_bytes=64 * 1024 * 1024) != rgba:
            fail('UNITY_PREFAB_TEXTURE_MATERIAL_SHARED_PIXELS', spec['sourceTextureId'], 'Shared source texture differs')
        dest.write_bytes(rgba)
        texture['rgbaAbsolutePath'] = str(dest)
    kwargs = dict(method='MonkeyUnitySource.UnityPrefabTextureMaterialAssets.Run',
                  plan_variable='MONKEY_UNITY_TEXTURE_MATERIAL_PLAN', readback_variable='MONKEY_UNITY_TEXTURE_MATERIAL_READBACK')
    first_process, first = _run(project, editor, native_plan, 'first', budget_seconds, **kwargs)
    before = _files(project, ['Assets', 'Packages', 'ProjectSettings'])
    cold_process, cold = _run(project, editor, native_plan, 'cold', budget_seconds, **kwargs)
    if first_process['pid'] == cold_process['pid'] or before != _files(project, ['Assets', 'Packages', 'ProjectSettings']):
        fail('UNITY_PREFAB_TEXTURE_MATERIAL_COLD_DRIFT', '$', 'Independent read-only process and unchanged saved files required')
    first_rows = {a['sourceMaterialId']: a for a in first['assets']}
    cold_rows = {a['sourceMaterialId']: a for a in cold['assets']}
    if len(first_rows) != len(first['assets']) or first_rows != cold_rows or set(first_rows) != set(request['materialSourceIds']):
        fail('UNITY_PREFAB_TEXTURE_MATERIAL_COLD_IDENTITY', '$', 'Complete source/native material identities must match across processes')
    for row in first_rows.values():
        if any(row.get(k) is not True for k in ('verified', 'materialPersistent', 'texturePersistent', 'sourcePropertyArraysPreserved', 'shaderReferencePreserved')):
            fail('UNITY_PREFAB_TEXTURE_MATERIAL_NATIVE', '$', 'All native identity/property/pixel checks must pass')
    artifact = out / 'Candidate'
    graph_path = candidate / 'Analysis/Evidence/source-graph.json'
    graph = load(read(graph_path, max_bytes=64 * 1024 * 1024), max_nodes=8_000_000)
    objects = {o['sourceObjectId']: o for o in graph['reachableObjects']}
    mappings, seen = [], set()
    for spec in plan['assets']:
        actual = first_rows[spec['sourceMaterialId']]
        for sid, typ, prefix in [(spec['sourceMaterialId'], 'Material', 'material'), (spec['sourceTextureId'], 'Texture2D', 'texture')]:
            if sid in seen:
                continue
            seen.add(sid)
            relative = actual[prefix + 'Path']
            for rel in (relative, relative + '.meta'):
                dest = inside(artifact, rel)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(inside(project, rel), dest)
            source = objects[sid]
            mapping = dict(sourceObjectId=sid, rawSha256=source['rawSha256'], sourceDataSha256=sha(encoded(source['data'])),
                type=typ, path=relative, guid=actual[prefix + 'Guid'], localId=str(actual[prefix + 'LocalId']),
                textureSourceId=spec['sourceTextureId'], rgbaRawSha256=spec['texture']['rgbaRawSha256'])
            if typ == 'Material':
                before_material = spec['providerMaterial']
                mapping['replacesProviderAsset'] = dict(path=relative, providerPath=before_material['originalPath'],
                    assetSha256=before_material['assetSha256'], metaSha256=before_material['metaSha256'],
                    guid=before_material['guid'], localId=before_material['localId'])
            mappings.append(mapping)
        closure = spec['candidateShaderClosure']
        for relative, key in [(closure['assetPath'], 'assetSha256'), (closure['metaPath'], 'metaSha256')]:
            if sha(read(inside(project, relative), max_bytes=16 * 1024 * 1024)) != closure[key]:
                fail('UNITY_PREFAB_TEXTURE_MATERIAL_SHADER_DRIFT', relative, 'Shader closure must stay byte-identical; semantic support is unverified')
    evidence = artifact / 'Analysis/Evidence'
    evidence.mkdir(parents=True)
    for path, name in [(request_path, 'request.json'), (plan_path, 'rebuild-plan.json'), (graph_path, 'source-graph.json'),
        (project / 'Analysis/first-readback.json', 'native-first.json'), (project / 'Analysis/cold-readback.json', 'native-cold.json'),
        (out / 'first-process.json', 'first-process.json'), (out / 'cold-process.json', 'cold-process.json')]:
        shutil.copyfile(path, evidence / name)
    write_json(evidence / 'native-plan.json', native_plan)
    pixel_evidence = evidence / 'selected-pixels'
    pixel_evidence.mkdir()
    shutil.copyfile(pixel_path, pixel_evidence / 'manifest.json')
    for row in load(pixel_raw)['files']:
        dest = inside(pixel_evidence, row['path'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(inside(pixel_path.parent, row['path']), dest)
    result = dict(contract=CONTRACT, schemaVersion=1, toolVersion=__version__, status='native-assets-verified-subset',
        sourceVersion='2021.3.30f1', targetVersion='6000.6.2f1', files=_files(artifact, ['Assets', 'Analysis']), mappings=mappings,
        firstProcess=first_process, coldProcess=cold_process, nativeIdentityAndBytesStable=True, helperSha256=sha(read(helper)),
        sourceCandidateManifestSha256=sha(manifest_raw), selectedPixelManifestSha256=sha(pixel_raw), sourceCodeExecuted=False,
        shaderSemanticSupport='native-reference-closure-only;source shader/visual equivalence unverified', visual='not_run_headless')
    write_json(artifact / 'manifest.json', result)
    summary = dict(status=result['status'], candidate=str(artifact), manifestSha256=sha(read(artifact / 'manifest.json')), visual='not_run_headless')
    write_json(out / 'result.json', summary)
    return summary


def load_supplement(pin, graph, lineage):
    from .unity_prefab_recovery import pinned
    from .native_selection import _guid_meta
    manifest_path, raw = pinned(pin)
    root, result = manifest_path.parent, load(raw)
    if (result.get('contract') != CONTRACT or result.get('status') != 'native-assets-verified-subset'
            or result.get('nativeIdentityAndBytesStable') is not True or result.get('targetVersion') != '6000.6.2f1'
            or result.get('sourceVersion') != '2021.3.30f1'):
        fail('UNITY_PREFAB_TEXTURE_MATERIAL_SUPPLEMENT', '$', 'Actual first/cold native resource evidence required')
    for row in result['files']:
        pinned(dict(row, path=str(inside(root, row['path']))), 128 * 1024 * 1024)
    processes = [result['firstProcess'], result['coldProcess']]
    if processes[0]['pid'] == processes[1]['pid'] or any(p.get('processExited') is not True or p.get('exitCode') != 0 for p in processes):
        fail('UNITY_PREFAB_TEXTURE_MATERIAL_PROCESS', '$', 'Two independently exited successful native processes required')
    reports = []
    for label, process in zip(('first', 'cold'), processes):
        path = root / ('Analysis/Evidence/native-' + label + '.json')
        body = read(path, max_bytes=16 * 1024 * 1024)
        if sha(body) != process['readback']['sha256'] or len(body) != process['readback']['bytes']:
            fail('UNITY_PREFAB_TEXTURE_MATERIAL_REPORT', label, 'Native report differs from process receipt')
        report = load(body)
        if report.get('status') != 'completed' or report.get('error') or any(a.get('verified') is not True for a in report['assets']):
            fail('UNITY_PREFAB_TEXTURE_MATERIAL_REPORT', label, 'Native resource report is incomplete')
        reports.append({a['sourceMaterialId']: a for a in report['assets']})
    if not reports[0] or reports[0] != reports[1]:
        fail('UNITY_PREFAB_TEXTURE_MATERIAL_REPORT', '$', 'Source/native identities and values must be stable')
    plan = load(read(root / 'Analysis/Evidence/rebuild-plan.json', max_bytes=64 * 1024 * 1024), max_nodes=2_000_000)
    pixels_raw = read(root / 'Analysis/Evidence/selected-pixels/manifest.json')
    pixels = load(pixels_raw)
    if sha(pixels_raw) != result['selectedPixelManifestSha256'] or sha(pixels_raw) != plan['selectedPixelManifestSha256']:
        fail('UNITY_PREFAB_TEXTURE_MATERIAL_PIXELS', '$', 'Selected original pixel evidence changed')
    objects = {o['sourceObjectId']: o for o in graph['reachableObjects']}
    owned = {r['path'] for r in result['files']}
    seen, mappings = set(), []
    for row in result['mappings']:
        sid = row['sourceObjectId']
        source = objects.get(sid)
        if (source is None or source['type'] != row['type'] or source['rawSha256'] != row['rawSha256']
                or sha(encoded(source['data'])) != row['sourceDataSha256'] or sid in seen or row['type'] not in ('Material', 'Texture2D')):
            fail('UNITY_PREFAB_TEXTURE_MATERIAL_SOURCE', sid, 'Unique exact source object/data identity required')
        seen.add(sid)
        if row['path'] not in owned or row['path'] + '.meta' not in owned or _guid_meta(inside(root, row['path'] + '.meta')) != row['guid']:
            fail('UNITY_PREFAB_TEXTURE_MATERIAL_GUID', sid, 'Owned native asset/meta GUID required')
        prefix = 'material' if row['type'] == 'Material' else 'texture'
        actual = [a for a in reports[0].values() if a['sourceMaterialId' if prefix == 'material' else 'sourceTextureId'] == sid]
        if not actual or any(str(a[prefix + 'LocalId']) != str(row['localId']) or a[prefix + 'Guid'] != row['guid']
                             or a[prefix + 'Path'] != row['path'] or a['rgbaSha256'] != row['rgbaRawSha256'] for a in actual):
            fail('UNITY_PREFAB_TEXTURE_MATERIAL_MAPPING', sid, 'Mapping differs from actual native resource identity')
        texture = objects[row['textureSourceId']]
        ti = texture['identity']
        hydrated = [p for p in pixels['textures'] if pixels['inputPins']['source'] == ti['containerSha256']
            and p['source']['file'] == ti['serializedFile'] and p['source']['pathId'] == ti['pathId']
            and p['source']['sourceRawSha256'] == texture['rawSha256'] and p['hydration']['rgbaRawSha256'] == row['rgbaRawSha256']]
        if len(hydrated) != 1:
            fail('UNITY_PREFAB_TEXTURE_MATERIAL_PIXELS', sid, 'Exact original selected Texture2D tuple/pixels required')
        if prefix == 'material':
            specs = [s for s in plan['assets'] if s['sourceMaterialId'] == sid]
            before = row.get('replacesProviderAsset', {})
            p = specs[0]['providerMaterial'] if len(specs) == 1 else {}
            if (before.get('providerPath') != p.get('originalPath') or before.get('assetSha256') != p.get('assetSha256')
                    or before.get('metaSha256') != p.get('metaSha256') or before.get('guid') != row['guid']
                    or str(before.get('localId')) != str(row['localId'])):
                fail('UNITY_PREFAB_TEXTURE_MATERIAL_BEFORE', sid, 'Exact before-pinned Material repair required')
        mappings.append(dict(row, supplementManifestSha256=sha(raw)))
    expected = {(a['sourceMaterialId'], 'Material') for a in reports[0].values()} | {(a['sourceTextureId'], 'Texture2D') for a in reports[0].values()}
    if {(r['sourceObjectId'], r['type']) for r in mappings} != expected:
        fail('UNITY_PREFAB_TEXTURE_MATERIAL_MAPPING', '$', 'Complete unique Material/Texture source pairs required')
    return root, result, mappings
