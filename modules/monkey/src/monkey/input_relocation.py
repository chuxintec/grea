"""Explicit SHA-pinned input-root relocation; never implicit symlink following.

The original document bytes/identities stay unchanged. Existing per-input hash
and ownership checks still run against the canonical physical destination.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import re

_STATE = ContextVar('monkey_input_relocation', default=None)


def relocate(path):
    state = _STATE.get()
    if state is None:
        return path
    for source, target in state['pairs']:
        if path.is_relative_to(source):
            from .sources.compiled import fail
            relative = path.relative_to(source)
            if '..' in relative.parts:
                fail('INPUT_RELOCATION_TRAVERSAL', str(path), 'Mapped inputs cannot traverse their root')
            return target / relative
    return path


def current_evidence():
    state = _STATE.get()
    if state is None:
        return None
    return dict(contract='monkey-input-relocation/1', schemaVersion=1,
                descriptorSha256=state['sha256'], roots=state['roots'],
                assurance='explicit-root-resolution-only;original-documents-and-all-input-SHA-guards-retained')


@contextmanager
def pinned_relocation(path=None, expected_sha256=None):
    from .io import safe, read, load, sha
    from .sources.compiled import fail
    if path is None and expected_sha256 is None:
        yield
        return
    if not path or not isinstance(expected_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        fail('INPUT_RELOCATION_PIN', '$', 'Both relocation descriptor and explicit SHA256 are required')
    if _STATE.get() is not None:
        fail('INPUT_RELOCATION_NESTED', '$', 'Nested relocation maps are not accepted')
    raw = read(safe(path), max_bytes=64 * 1024)
    if sha(raw) != expected_sha256:
        fail('INPUT_RELOCATION_DRIFT', str(path), 'Relocation descriptor changed')
    doc = load(raw, max_nodes=512, max_depth=8)
    if not isinstance(doc, dict):
        fail('INPUT_RELOCATION_CONTRACT', str(path), 'Expected a descriptor object')
    rows = doc.get('roots')
    if (doc.get('contract') != 'monkey-input-relocation/1' or doc.get('schemaVersion') != 1
            or not isinstance(rows, list) or not 1 <= len(rows) <= 8):
        fail('INPUT_RELOCATION_CONTRACT', str(path), 'Versioned descriptor with1–8 explicit roots required')
    pairs = []
    normalized = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'sourceRoot', 'targetRoot'}:
            fail('INPUT_RELOCATION_ROOT', '$', 'Only explicit sourceRoot/targetRoot fields are accepted')
        if not all(isinstance(row[k], str) for k in ('sourceRoot', 'targetRoot')):
            fail('INPUT_RELOCATION_ROOT', '$', 'Root paths must be strings')
        source, target = Path(row['sourceRoot']), Path(row['targetRoot'])
        if (not source.is_absolute() or not target.is_absolute() or '..' in source.parts
                or '..' in target.parts or str(source) != row['sourceRoot'] or str(target) != row['targetRoot']):
            fail('INPUT_RELOCATION_ROOT', '$', 'Normalized absolute roots without traversal required')
        # Check the physical target while no relocation context exists. Symlinks
        # at the target or any of its ancestors remain forbidden by safe().
        target = safe(target)
        if not target.is_dir() or source == target:
            fail('INPUT_RELOCATION_ROOT', str(target), 'Existing distinct physical destination required')
        if any(source.is_relative_to(s) or s.is_relative_to(source) for s, _ in pairs):
            fail('INPUT_RELOCATION_AMBIGUOUS', str(source), 'Overlapping source roots are not accepted')
        pairs.append((source, target))
        normalized.append(dict(sourceRoot=str(source), targetRoot=str(target)))
    if any(t.is_relative_to(s) for _, t in pairs for s, _ in pairs):
        fail('INPUT_RELOCATION_CYCLE', '$', 'Targets cannot fall inside a logical source root')
    token = _STATE.set(dict(pairs=pairs, roots=normalized, sha256=expected_sha256))
    try:
        yield
    finally:
        _STATE.reset(token)


@contextmanager
def command_context(args):
    path = getattr(args, 'input_path_map', None)
    digest = getattr(args, 'expected_input_path_map', None)
    if path is not None or digest is not None:
        from .io import safe
        # Output creation is never redirected through a logical input root.
        safe(args.out)
        out = Path(args.out).absolute()
        with pinned_relocation(path, digest):
            if relocate(out) != out:
                from .sources.compiled import fail
                fail('INPUT_RELOCATION_OUTPUT', str(out), 'Choose a physical output outside logical input roots')
            yield
    else:
        yield
