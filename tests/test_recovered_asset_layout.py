import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from grea.features.asset.recovered_layout import stage
from grea.features.asset.verify_recovered import verify
from grea.development.intake import enforce_layout
from grea.development.errors import BeaverError
from grea.recovery.layout import standard


def write_set(tmp, entries):
    project = tmp/'project'
    lines = []
    for guid, path, typ, refs, content in entries:
        asset = project/path
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_text(content)
        Path(str(asset)+'.meta').write_text(f'fileFormatVersion: 2\nguid: {guid}\n')
        lines.append('\t'.join((guid, path, typ, ','.join(refs))))
    native = tmp/'native.tsv'
    native.write_text('\n'.join(lines)+'\n')
    return SimpleNamespace(project=project, inventory=native, output=tmp/'candidate', addresses=None)


def test_recovery_layout_round_trip(tmp_path):
    a,b,c,d,e = [str(i)*32 for i in range(1,6)]
    req = write_set(tmp_path, [
        (a, 'Assets/export/ActorHp.prefab', 'UnityEngine.GameObject', [b], 'prefab'),
        (b, 'Assets/export/HpBar.asset', 'UnityEngine.Sprite', [c], 'sprite'),
        (c, 'Assets/RecoveredSourceImages/'+c+'/HP Border.png', 'UnityEngine.Texture2D', [], 'image'),
        (d, 'Assets/export/health icon.png', 'UnityEngine.Texture2D', [], 'one'),
        (e, 'Assets/export/health_icon.png', 'UnityEngine.Texture2D', [], 'two')])
    req.addresses = tmp_path/'addresses.json'
    req.addresses.write_text(json.dumps({a:'assets/resources/battle/ActorHp.prefab', b:'uiraw/battle/HpBar.asset',
                                        c:'Assets/RecoveredSourceImages/'+c+'/HP Border.png'}))
    result = stage(req)
    out = req.output
    rows = [json.loads(x) for x in (out/'layout.jsonl').read_text().splitlines()]
    paths = {r['guid']:r['target'] for r in rows}
    assert paths[a] == 'Assets/Game/Content/Prefabs/Battle/ActorHp.prefab'
    assert paths[b] == 'Assets/Game/Content/Sprites/Battle/hp_bar.asset'
    assert paths[c] == 'Assets/Game/Content/Images/Battle/hp_border.png'
    assert paths[e].endswith('/health_icon_'+e[:10]+'.png')
    assert result['assets'] == 5
    after = tmp_path/'import.tsv'
    after.write_text('\n'.join('\t'.join([g, paths[g], t, deps]) for g, _, t, deps in
                                (line.split('\t') for line in req.inventory.read_text().splitlines())))
    check = SimpleNamespace(project=out, inventory=after, before=req.inventory,
                            ledger=out/'layout.jsonl', output=tmp_path/'verified')
    assert verify(check)['contentAndMetaFiles'] == 10
    (out/paths[c]).write_text('changed')
    with pytest.raises(ValueError, match='differs from ledger'):
        verify(check)
    assert (req.project/rows[2]['source']).read_text() == 'image'


def test_assembly_resources_and_spine_names(tmp_path):
    ids = [format(i, '032x') for i in range(1, 7)]
    paths = ['Assets/export/scripts/logic.asmdef','Assets/export/scripts/Game/FontUI.cs',
             'Assets/export/Resources/ui/sPeCiAl.png','Assets/export/Track_SkeletonData.asset',
             'Assets/export/Track.atlas.txt','Assets/export/Track.png']
    types = ['UnityEditorInternal.AssemblyDefinitionAsset','UnityEditor.MonoScript','UnityEngine.Texture2D',
             'Spine.Unity.SkeletonDataAsset','UnityEngine.TextAsset','UnityEngine.Texture2D']
    req = write_set(tmp_path, [(g,p,t,ids[4:] if i == 3 else [],
                                '{"name":"Actual.Logic"}' if i == 0 else 'data')
                               for i,(g,p,t) in enumerate(zip(ids,paths,types))])
    stage(req)
    dest = {r['guid']:r['target'] for r in map(json.loads,(req.output/'layout.jsonl').read_text().splitlines())}
    assert dest[ids[1]] == 'Assets/Game/Scripts/Actual.Logic/Game/FontUI.cs'
    assert dest[ids[2]].endswith('/Images/Resources/ui/sPeCiAl.png')
    assert len({Path(dest[i]).parent for i in ids[3:]}) == 1
    assert dest[ids[4]].endswith('/Track.atlas.txt')


@pytest.mark.parametrize('case', ['unknown', 'stale', 'missing-ref', 'path-consumer'])
def test_refuses_unproven_layout(tmp_path, case):
    g = 'a'*32
    rows = [(g, 'Assets/raw/file.asset', 'custom.Type' if case == 'unknown' else 'UnityEngine.Mesh',
             ['b'*32] if case == 'missing-ref' else [], 'mesh')]
    if case == 'path-consumer':
        rows.append(('b'*32,'Assets/raw/Consumer.cs','UnityEditor.MonoScript',[],
                     'class Consumer { string path = "Assets/raw/file.asset"; }'))
    req = write_set(tmp_path, rows)
    if case == 'stale':
        (req.project/'Assets/raw/file.asset.meta').write_text('guid: '+'b'*32)
    with pytest.raises(ValueError):
        stage(req)
    assert not req.output.exists()


def test_historical_scene_lookup_and_adoption_gate():
    old = {'projectLayout':standard.V2_LAYOUT}
    assert standard.locate(old, 'bootScene') == 'Assets/Game/Content/Scenes/Boot/Boot.unity'
    assert standard.unity('bootScene') == 'Assets/Game/Scenes/Boot/Boot.unity'
    src = 'Assets/Game/Content/Prefabs/UI/ActorHp.prefab'
    enforce_layout(src, src)
    with pytest.raises(BeaverError):
        enforce_layout(src, 'Assets/Game/Content/Images/UI/ActorHp.prefab')
    with pytest.raises(BeaverError):
        enforce_layout(src, 'Assets/Game/Content/Prefabs/UI/actor_hp.prefab')


def test_native_root_rename_allows_only_exact_gameobject_field(tmp_path):
    from grea.features.asset.prefab_names import root_alias
    import hashlib
    raw = (b'%YAML 1.1\n--- !u!1 &13\nGameObject:\n  m_Name: old_root\n'
           b'--- !u!4 &14\nTransform:\n  m_GameObject: {fileID: 13}\n  m_Father: {fileID: 0}\n'
           b'--- !u!1 &15\nGameObject:\n  m_Name: old_root\n')
    alias = root_alias(raw, 'old_root.prefab', 'OldRoot.prefab')
    assert alias['rootLocalId'] == 13
    assert alias['savedSha256'] == hashlib.sha256(raw.replace(b'm_Name: old_root', b'm_Name: OldRoot', 1)).hexdigest()
    assert alias['savedSha256'] != hashlib.sha256(raw.replace(b'm_Name: old_root', b'm_Name: OldRoot')).hexdigest()
    req = write_set(tmp_path,[('a'*32, 'Assets/old_root.prefab','UnityEngine.GameObject',[],raw.decode()),
                              ('b'*32,'Assets/Loader.cs','UnityEditor.MonoScript',[],
                               'class Loader { const string root = "old_root"; }')])
    with pytest.raises(ValueError, match='literal code consumer'):
        stage(req)
