import json
from argparse import Namespace
from pathlib import Path

import pytest

from grea.recovery.input_relocation import command_context, current_evidence, pinned_relocation
from grea.recovery.io import read, safe, sha
from grea.recovery.sources.compiled import ParseError
from grea.recovery.unity_prefab_recovery import pinned


def descriptor(tmp_path, roots):
    path = tmp_path / 'relocation.json'
    raw = json.dumps(dict(contract='monkey-input-relocation/1', schemaVersion=1, roots=roots)).encode()
    path.write_bytes(raw)
    return path, sha(raw)


def fixture(tmp_path):
    physical = tmp_path / 'physical'
    physical.mkdir()
    old = tmp_path / 'old'
    old.symlink_to(physical, target_is_directory=True)
    (physical / 'input.json').write_bytes(b'{"value":7}')
    path, digest = descriptor(tmp_path, [dict(sourceRoot=str(old), targetRoot=str(physical))])
    return old, physical, path, digest


def test_explicit_map_keeps_original_hash_checks_and_document_bytes(tmp_path):
    old, physical, path, digest = fixture(tmp_path)
    raw = (physical / 'input.json').read_bytes()
    with pytest.raises(ParseError, match='SYMLINK_PATH'):
        read(old / 'input.json')
    with pinned_relocation(path, digest):
        actual, data = pinned(dict(path=str(old / 'input.json'), sha256=sha(raw)))
        assert actual == physical / 'input.json'
        assert data == raw
        assert current_evidence()['descriptorSha256'] == digest
        with pytest.raises(ParseError, match='INPUT_DRIFT'):
            pinned(dict(path=str(old / 'input.json'), sha256='f' * 64))
    assert (physical / 'input.json').read_bytes() == raw
    assert current_evidence() is None
    with pytest.raises(ParseError, match='SYMLINK_PATH'):
        read(old / 'input.json')


def test_map_can_resolve_retired_logical_root_without_symlink(tmp_path):
    old, physical, path, digest = fixture(tmp_path)
    old.unlink()
    with pinned_relocation(path, digest):
        assert read(old / 'input.json') == b'{"value":7}'


def test_map_context_resets_on_exception(tmp_path):
    _, _, path, digest = fixture(tmp_path)
    with pytest.raises(RuntimeError):
        with pinned_relocation(path, digest):
            raise RuntimeError('stop')
    assert current_evidence() is None


def test_target_symlinks_and_nested_target_symlinks_remain_forbidden(tmp_path):
    old, physical, path, digest = fixture(tmp_path)
    link = tmp_path / 'destination-alias'
    link.symlink_to(physical, target_is_directory=True)
    p, d = descriptor(tmp_path, [dict(sourceRoot=str(old), targetRoot=str(link))])
    with pytest.raises(ParseError, match='SYMLINK_PATH'):
        with pinned_relocation(p, d):
            pass
    p, d = descriptor(tmp_path, [dict(sourceRoot=str(old), targetRoot=str(physical))])
    (physical / 'alias.json').symlink_to(physical / 'input.json')
    with pinned_relocation(p, d):
        with pytest.raises(ParseError, match='SYMLINK_PATH'):
            read(old / 'alias.json')


def test_ambiguous_maps_and_source_traversal_are_rejected(tmp_path):
    old, physical, _, _ = fixture(tmp_path)
    path, digest = descriptor(tmp_path, [dict(sourceRoot=str(old), targetRoot=str(physical)),
        dict(sourceRoot=str(old / 'nested'), targetRoot=str(physical))])
    with pytest.raises(ParseError, match='AMBIGUOUS'):
        with pinned_relocation(path, digest):
            pass
    path, digest = descriptor(tmp_path, [dict(sourceRoot=str(old), targetRoot=str(physical))])
    with pinned_relocation(path, digest):
        with pytest.raises(ParseError, match='TRAVERSAL'):
            safe(old / '..' / 'outside')


@pytest.mark.parametrize('part', ['missing-pin', 'bad-digest', 'mutated-document'])
def test_map_requires_exact_descriptor_pin(tmp_path, part):
    _, _, path, digest = fixture(tmp_path)
    expected = None if part == 'missing-pin' else '0' * 64 if part == 'bad-digest' else digest
    if part == 'mutated-document':
        path.write_bytes(path.read_bytes() + b'\n')
    with pytest.raises(ParseError, match='INPUT_RELOCATION_'):
        with pinned_relocation(path, expected):
            pass


def test_outputs_cannot_be_redirected_to_logical_source_root(tmp_path):
    old, _, path, digest = fixture(tmp_path)
    with pytest.raises(ParseError, match='SYMLINK_PATH'):
        with command_context(Namespace(input_path_map=str(path), expected_input_path_map=digest, out=str(old / 'output'))):
            pytest.fail('must not enter')
    assert not (old / 'output').exists()


def test_unmapped_paths_still_use_default_safe_policy(tmp_path):
    _, physical, path, digest = fixture(tmp_path)
    external = tmp_path / 'outside.txt'
    external.write_bytes(b'unchanged')
    with pinned_relocation(path, digest):
        assert safe(external) == external
        assert read(external) == b'unchanged'
        with pytest.raises(ParseError, match='NESTED'):
            with pinned_relocation(path, digest):
                pass
    assert not (physical / 'outside.txt').exists()
