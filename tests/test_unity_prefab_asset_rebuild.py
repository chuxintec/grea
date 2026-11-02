import copy

import pytest

from monkey.io import encoded, sha, write_json
from monkey.sources.compiled import ParseError
from monkey.unity_prefab_asset_rebuild import CONTRACT, execute, load_supplement


def fixture_supplement(tmp_path):
    root = tmp_path / 'supplement'
    objects = [dict(sourceObjectId=sid, type=typ, rawSha256=raw, data=dict(value=i), identity=dict(
        containerSha256='a' * 64, serializedFile='CAB-fixture', serializedFileSha256='b' * 64, pathId=str(i)))
        for i, (sid, typ, raw) in enumerate([('sprite-source', 'Sprite', 'c' * 64), ('texture-source', 'Texture2D', 'd' * 64)], 1)]
    rows = []
    mappings = []
    asset = dict(sourceId='sprite-source', textureSourceId='texture-source', verified=True, pixelSha256='e' * 64)
    for source, prefix in zip(objects, ['sprite', 'texture']):
        path = 'Assets/Generated/' + prefix + '.asset'
        guid = ('1' if prefix == 'sprite' else '2') * 32
        local_id = '21300000' if prefix == 'sprite' else '2800000'
        p = root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes((prefix + '-fixture-payload').encode())
        p.with_suffix('.asset.meta').write_text('guid: ' + guid + '\n')
        mappings.append(dict(sourceObjectId=source['sourceObjectId'], rawSha256=source['rawSha256'], sourceDataSha256=sha(encoded(source['data'])),
            type=source['type'], path=path, guid=guid, localId=local_id, textureSourceId='texture-source', rgbaRawSha256='e' * 64))
        asset.update({prefix + 'Guid': guid, prefix + 'LocalId': local_id, prefix + 'Path': path})
    processes = []
    for i, label in enumerate(['first', 'cold']):
        p = root / ('Analysis/Evidence/native-' + label + '.json')
        write_json(p, dict(status='completed', error='', assets=[asset]))
        processes.append(dict(pid=100 + i, processExited=True, exitCode=0, readback=dict(sha256=sha(p.read_bytes()), bytes=p.stat().st_size)))
    for p in sorted(root.rglob('*')):
        if p.is_file(): rows.append(dict(path=p.relative_to(root).as_posix(), sha256=sha(p.read_bytes()), bytes=p.stat().st_size))
    manifest = dict(contract=CONTRACT, status='native-assets-verified-subset', targetVersion='6000.6.2f1', sourceVersion='2021.3.30f1',
        nativeIdentityAndBytesStable=True, firstProcess=processes[0], coldProcess=processes[1], files=rows, mappings=mappings)
    p = root / 'manifest.json'
    write_json(p, manifest)
    pin = dict(path=str(p), sha256=sha(p.read_bytes()))
    lineage = dict(selectedSourceInputs=[dict(originalSha256='a' * 64, textureHydration=[dict(file='CAB-fixture', pathId='2', rgbaRawSha256='e' * 64)])])
    return pin, dict(reachableObjects=objects), lineage


def test_exact_native_supplement_joins_source_and_current_pixel_lineage(tmp_path):
    pin, graph, lineage = fixture_supplement(tmp_path)
    _, result, mappings = load_supplement(pin, graph, lineage)
    assert len(mappings) == 2
    assert result['firstProcess']['pid'] != result['coldProcess']['pid']
    assert {r['sourceObjectId'] for r in mappings} == {'sprite-source', 'texture-source'}
    changed = copy.deepcopy(graph)
    changed['reachableObjects'][0]['data']['value'] = 9
    with pytest.raises(ParseError, match='UNITY_PREFAB_ASSET_SOURCE_IDENTITY'):
        load_supplement(pin, changed, lineage)
    changed_pixels = copy.deepcopy(lineage)
    changed_pixels['selectedSourceInputs'][0]['textureHydration'][0]['rgbaRawSha256'] = 'f' * 64
    with pytest.raises(ParseError, match='UNITY_PREFAB_ASSET_SOURCE_PIXELS'):
        load_supplement(pin, graph, changed_pixels)


def test_native_asset_request_wrong_sha_never_creates_an_output(tmp_path):
    request = tmp_path / 'request.json'
    request.write_text('{}')
    with pytest.raises(ParseError, match='UNITY_PREFAB_INPUT_DRIFT'):
        execute(request, '0' * 64, tmp_path / 'output', tmp_path / 'Unity')
    assert not (tmp_path / 'output').exists()
