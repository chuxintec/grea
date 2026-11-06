"""Production inventory counters use expanded sizes; disk fixtures never start Unity."""
import hashlib
import json

import pytest

from grea.recovery import byte_budgets as limits
from grea.recovery.export_plan import read_import_instruction
from grea.recovery.inputs import input_set
from grea.recovery.sources.compiled import ParseError
from grea.recovery.sources.containers import Names, entries


def test_default_explicit_and_one_byte_over_batch(tmp_path):
    manifest = tmp_path/'inputs.json'
    (tmp_path/'root').mkdir()
    spec = dict(schemaVersion=1, sourceProfile='generic-image-resources-v1',
                inputs=[dict(id='r', path='root')])
    for override in (None, 37):
        if override is not None:
            spec['limits'] = dict(maxInputBytes=override)
        manifest.write_text(json.dumps(spec))
        effective = input_set(manifest)['maxInputBytes']
        assert effective == (2048*1024**2 if override is None else override)
        names = Names(effective)
        for i in range(16 if override is None else 1):
            names.add(str(i), 128*1024**2 if override is None else override)
        assert names.total == effective
        with pytest.raises(ParseError) as failure:
            names.add('extra', 1)
        detail = failure.value.byte_budget
        assert (detail['object'],detail['measured'],detail['effectiveLimit'],detail['unit']) == (
            'batchInput', effective+1, effective, 'bytes')
        assert names.total == effective


def test_file_boundary_through_directory_reader(tmp_path):
    size = 128*1024**2
    p = tmp_path/'entry'
    with p.open('wb') as f:
        f.truncate(size)
    [(name, payload)] = entries(tmp_path)
    assert name == 'entry' and len(payload) == size
    del payload
    with p.open('ab') as f:
        f.write(b'x')
    with pytest.raises(ParseError) as failure:
        list(entries(tmp_path))
    assert failure.value.byte_budget == limits.record('packageFile', size, size+1, basis='expanded entry')


def test_import_boundary_through_owned_instruction_reader(tmp_path):
    size = 256*1024**2
    p = tmp_path/'instruction'
    block = b' ' * 1024**2
    with p.open('wb') as f:
        f.write(b'{}' + block[2:])
        for _ in range(255):
            f.write(block)
    with p.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    m = dict(files=[dict(path=p.name, bytes=size, sha256=digest)])
    assert read_import_instruction(tmp_path,m,p.name) == ({},digest)
    with p.open('ab') as f:
        f.write(b'x')
    with pytest.raises(ParseError) as failure:
        read_import_instruction(tmp_path,m,p.name)
    assert failure.value.byte_budget == limits.record('unityImportInstruction', size, size+1, basis='file size')
