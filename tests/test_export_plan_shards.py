
import pytest

from monkey import export_plan as export
from monkey.io import write_json
from monkey.sources.compiled import ParseError


def stage(tmp):
    root = tmp/'stage'
    root.mkdir()
    data = b'copied resource'
    asset = root/'asset.bin'
    asset.write_bytes(data)
    plan = root/'plan.json'
    write_json(plan, {'schemaVersion': 1, 'targetProfile': 'unity-6000.6.2f1-ugui',
                      'copies': [{'source': asset.name, 'sha256': export.sha(data)}]})
    write_json(root/'manifest.json', {'files': [
        {'path': f.name, 'bytes': f.stat().st_size, 'sha256': export.sha(f.read_bytes())}
        for f in (plan, asset)]})
    return plan, export.sha((root/'manifest.json').read_bytes())


def test_retry_restore_and_corrupt_chunk(tmp_path, monkeypatch):
    monkeypatch.setattr(export,'CHUNK',32)
    plan, pin = stage(tmp_path)
    root = tmp_path/'sharded'
    assert export.shard(plan, root, pin, 1)['status'] == 'paused'
    assert not (root/'index.json').exists()
    index = export.shard(plan, root, pin)
    assert export.shard(plan, root, pin)['newChunks'] == 0
    j = root/'index.json'
    restored = tmp_path/'restored'
    export.restore(j,index['indexSha256'],restored)
    assert {f.name:f.read_bytes() for f in restored.iterdir()} == {f.name:f.read_bytes() for f in plan.parent.iterdir()}
    block = next((root/'chunks').iterdir())
    block.write_bytes(block.read_bytes()[:-1])
    with pytest.raises(ParseError,match='EXPORT_SHARD_CHANGED'):
        export.restore(j,index['indexSha256'],tmp_path/'invalid')
    assert not (tmp_path/'invalid').exists()


def test_changed_inputs_and_manifest_pin_refuse_publication(tmp_path):
    plan, pin = stage(tmp_path)
    with pytest.raises(ParseError,match='EXPORT_SHARD_IDENTITY'):
        export.shard(plan,tmp_path/'foreign','0'*64)
    asset = plan.parent/'asset.bin'
    asset.write_bytes(asset.read_bytes()[:-1])
    with pytest.raises(ParseError,match='EXPORT_SHARD_TRUNCATED'):
        export.shard(plan,tmp_path/'shards',pin)
    assert not (tmp_path/'shards/index.json').exists()
    plan.write_bytes(plan.read_bytes()[:-1])
    with pytest.raises(ParseError,match='PLAN_CHANGED'):
        export.open_plan(plan)


def test_import_instruction_rejects_ambiguous_or_invalid_manifest_record(tmp_path):
    name = 'import-plan.json'
    raw = b'{}'
    (tmp_path/name).write_bytes(raw)
    entry = dict(path=name, bytes=len(raw), sha256=export.sha(raw))
    for rows, code in (
        ([], 'IMPORT_PLAN_OWNERSHIP'),
        ([entry, entry], 'IMPORT_PLAN_OWNERSHIP'),
        ([dict(entry, bytes=export.DOCUMENT_LIMIT + 1)], 'IMPORT_PLAN_BUDGET'),
        ([dict(entry, sha256='x')], 'IMPORT_PLAN_PIN'),
        ([dict(entry, sha256='0'*64)], 'IMPORT_PLAN_CHANGED'),
    ):
        with pytest.raises(ParseError, match=code):
            export.read_import_instruction(tmp_path, {'files': rows}, name)
