import hashlib
import json
from pathlib import Path

import pytest

from monkey.sources.compiled import ParseError
from monkey.unity_aggregate_readback import read_pair


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pretty(value):
    return json.dumps(value, indent=4).encode()


@pytest.fixture
def native_pair(tmp_path):
    root = tmp_path.resolve()
    readback = root/'Analysis/Readback'
    directory = readback/'Prefabs'
    directory.mkdir(parents=True)
    plan_pin = 'f'*64
    specs, rows = [], []
    for i in (1, 2):
        guid = str(i)*32
        path = f'{i}.prefab'
        meta = f'guid: {guid}\n'.encode()
        (root/path).write_bytes(b'prefab')
        (root/(path+'.meta')).write_bytes(meta)
        row = dict(path=path, guid=guid, sourceId=guid, importPlanSha256=plan_pin, sourceManifestSha256='a'*64,
                   prefabSha256=sha(b'prefab'), prefabMetaSha256=sha(meta))
        (directory/(guid+'.json')).write_bytes(pretty(row))
        specs.append(dict(sourceId=guid, path=path))
        rows.append(row)
    doc = dict(importPlanSha256=plan_pin, sourceManifestSha256='a'*64, sourcePrefabs=rows,
               components=[dict(label='quote ", escaped\n', children=[1, 2]), dict(label='end')])
    paths = [readback/(n+'-readback.json') for n in ('editor', 'source-prefabs')]
    for p in paths:
        p.write_bytes(pretty(doc))
    def verify(pins=None):
        return read_pair(root, dict(sourceManifestSha256='a'*64,sourcePrefabs=specs), plan_pin,
                         *(pins or [sha(p.read_bytes()) for p in paths]))
    return paths, doc, verify


def test_native_pair_matches_standalone_receipts(native_pair):
    _, doc, verify = native_pair
    data, proof = verify()
    assert data == doc and proof['prefabCount'] == 2


@pytest.mark.parametrize('damage', ['pin','truncated','order','content','source','extra','meta'])
def test_native_pair_refuses_mismatches(native_pair, damage):
    paths, doc, verify = native_pair
    pins = [sha(p.read_bytes()) for p in paths] if damage == 'pin' else None
    if damage in ('truncated','pin'):
        paths[0].write_bytes(paths[0].read_bytes()[:-1])
    elif damage == 'source':
        paths[1].write_bytes(pretty(dict(doc, components=[])))
    elif damage == 'extra':
        (paths[0].parent/'Prefabs/extra.json').write_bytes(b'{}')
    elif damage == 'meta':
        f=paths[0].parents[2]/'1.prefab.meta'
        f.write_bytes(f.read_bytes()+b'changed')
    else:
        if damage == 'order':
            doc['sourcePrefabs'].reverse()
        else:
            doc['sourcePrefabs'][0]['referencesVerified'] = True
        for p in paths:
            p.write_bytes(pretty(doc))
    with pytest.raises(ParseError,match='NATIVE_AGGREGATE_INVALID'):
        verify(pins)
