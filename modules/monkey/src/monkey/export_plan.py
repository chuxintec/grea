"""Bounded admission and lossless, resumable shards of an owned export plan."""
import hashlib
import os
import re
import tempfile
from pathlib import Path

from .byte_budgets import UNITY_INSTRUCTION, enforce
from .io import fail, inside, load, read, safe, sha, new_output

DOCUMENT_NODES = 16_000_000
DOCUMENT_LIMIT = 256 * 1024**2
CHUNK = 4 * 1024**2
MAX_FILES = 200_000
MAX_TOTAL = 32 * 1024**3


def read_import_instruction(root, manifest, relative):
    """Bind parsing and saved-readback admission to the same owned bytes."""
    matches = [entry for entry in manifest['files'] if entry['path'] == relative]
    if len(matches) != 1:
        fail('IMPORT_PLAN_OWNERSHIP', relative, 'Expected one import instruction in the candidate manifest')
    entry = matches[0]
    size = entry.get('bytes')
    expected = entry.get('sha256')
    if type(size) is not int or size < 0:
        fail('IMPORT_PLAN_BUDGET', relative, 'Invalid or oversized import instruction')
    instruction = inside(root, relative)
    enforce('unityImportInstruction', instruction.stat().st_size, UNITY_INSTRUCTION, relative,
            'IMPORT_PLAN_BUDGET', basis='file size')
    enforce('unityImportInstruction', size, UNITY_INSTRUCTION, relative,
            'IMPORT_PLAN_BUDGET', basis='manifest size')
    if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
        fail('IMPORT_PLAN_PIN', relative, 'Invalid import instruction fingerprint')
    raw = read(instruction, size)
    if len(raw) != size or sha(raw) != expected:
        fail('IMPORT_PLAN_CHANGED', relative, 'Import instruction differs from candidate manifest')
    return load(raw, max_nodes=DOCUMENT_NODES), expected


def open_plan(path):
    path = safe(path)
    manifest_raw = read(path.parent / 'manifest.json', DOCUMENT_LIMIT)
    manifest_hash = sha(manifest_raw)
    manifest = load(manifest_raw, max_nodes=DOCUMENT_NODES)
    del manifest_raw
    rows = manifest.get('files')
    if not isinstance(rows, list) or len(rows) > MAX_FILES:
        fail('EXPORT_PLAN_FILES', str(path), 'Expected bounded manifest file list')
    entries = {}
    for row in rows:
        name = row['path']
        if (not isinstance(name, str) or not name or Path(name).as_posix() != name or
                Path(name).is_absolute() or '..' in Path(name).parts or name in ('.', 'manifest.json') or
                name in entries or type(row.get('bytes')) is not int or not 0 <= row['bytes'] <= DOCUMENT_LIMIT or
                not isinstance(row.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', row['sha256'])):
            fail('EXPORT_PLAN_FILES', str(path), 'Invalid or duplicate owned file')
        entries[name] = row
    del manifest
    entry = entries.get(path.name)
    if entry is None:
        fail('STAGE_DOCUMENT_BUDGET', str(path), 'Missing owned plan')
    raw = read(path, entry['bytes'])
    if len(raw) != entry['bytes'] or sha(raw) != entry['sha256']:
        fail('PLAN_CHANGED', str(path), 'Plan differs from owning manifest')
    return load(raw, max_nodes=DOCUMENT_NODES), entries, manifest_hash


def _publish(path, data):
    """Concurrent retries can publish only complete identical files."""
    if path.exists():
        if read(path, len(data)) != data:
            fail('EXPORT_SHARD_CHANGED', str(path), 'Existing shard differs')
        return False
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        tmp = Path(stream.name)
    try:
        tmp.write_bytes(data)
        try:
            os.link(tmp, path)
            return True
        except FileExistsError:
            if read(path, len(data)) != data:
                fail('EXPORT_SHARD_CHANGED', str(path), 'Existing shard differs')
            return False
    finally:
        tmp.unlink(missing_ok=True)


def shard(path, output, expected_manifest, max_new=None):
    from .io import encoded
    path = safe(path)
    plan, entries, manifest_hash = open_plan(path)
    if manifest_hash != expected_manifest:
        fail('EXPORT_SHARD_IDENTITY', str(path), 'Owning manifest differs from expected fingerprint')
    if plan.get('targetProfile') != 'unity-6000.6.2f1-ugui' or plan.get('schemaVersion') != 1:
        fail('UNSUPPORTED_PLAN', str(path), 'Expected a Unity export plan')
    for field in ('copies', 'staticFieldScripts', 'behaviorScripts'):
        for resource in plan.get(field, []):
            record = entries.get(resource.get('source'))
            if not record or record['sha256'] != resource.get('sha256'):
                fail('EXPORT_SHARD_SOURCE_UNOWNED', field, 'Referenced payload has no matching manifest entry')
    del plan
    manifest = path.parent / 'manifest.json'
    entries['manifest.json'] = dict(bytes=manifest.stat().st_size, sha256=manifest_hash)
    if sum(r['bytes'] for r in entries.values()) > MAX_TOTAL or (max_new is not None and max_new < 1):
        fail('EXPORT_SHARD_BUDGET', str(path), 'Invalid stage or per-run budget')
    root = safe(output)
    if root.is_relative_to(path.parent) or path.parent.is_relative_to(root):
        fail('OUTPUT_OVERLAP', str(root), 'Use an independent shard directory')
    identity = dict(schema='monkey-unity-export-plan-shards/1', manifestSha256=manifest_hash,
                    plan=path.name, planSha256=entries[path.name]['sha256'], chunkBytes=CHUNK)
    try:
        new_output(root, [path.parent])
    except ValueError:
        if not (root/'identity.json').is_file(): raise
    _publish(root/'identity.json', encoded(identity))
    chunks = safe(root/'chunks')
    chunks.mkdir(exist_ok=True)
    files = []
    written = 0
    for name, row in sorted(entries.items()):
        digest = hashlib.sha256()
        blocks = []
        with inside(path.parent, name).open('rb') as stream:
            remaining = row['bytes']
            while remaining:
                data = stream.read(min(CHUNK, remaining))
                if len(data) != min(CHUNK, remaining):
                    fail('EXPORT_SHARD_TRUNCATED', name, 'Owned file ended early')
                digest.update(data)
                block = sha(data)
                if _publish(chunks/block, data):
                    written += 1
                    if written == max_new:
                        return dict(status='paused', newChunks=written, manifestSha256=manifest_hash)
                blocks.append(block)
                remaining -= len(data)
            if stream.read(1) or digest.hexdigest() != row['sha256']:
                fail('EXPORT_SHARD_CHANGED', name, 'Owned file differs from manifest')
        files.append(dict(path=name, bytes=row['bytes'], sha256=row['sha256'], chunks=blocks))
    index = encoded(dict(identity, files=files))
    if len(index) > 128 * 1024**2:
        fail('EXPORT_SHARD_BUDGET', str(root), 'Shard index exceeds restore budget')
    _publish(root/'index.json', index)
    return dict(status='sharded', indexSha256=sha(index), files=len(files), newChunks=written)


def restore(index, expected, output):
    """Reassemble and verify each owner file before publishing a complete stage."""
    import shutil
    index = safe(index)
    raw = read(index, 128 * 1024**2)
    if sha(raw) != expected:
        fail('EXPORT_SHARD_CHANGED', str(index), 'Index fingerprint differs')
    spec = load(raw)
    if spec.get('schema') != 'monkey-unity-export-plan-shards/1' or spec.get('chunkBytes') != CHUNK:
        fail('EXPORT_SHARD_INDEX', str(index), 'Unknown shard format')
    out = safe(output)
    if out.exists() or out.is_relative_to(index.parent) or index.parent.is_relative_to(out):
        fail('OUTPUT_EXISTS', str(out), 'Restore requires fresh independent output')
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=out.parent))
    try:
        total = 0
        files = spec['files']
        if len(files) > MAX_FILES + 1: fail('EXPORT_SHARD_BUDGET', str(index), 'Too many files')
        for row in files:
            size = row['bytes']
            if type(size) is not int or not 0 <= size <= DOCUMENT_LIMIT or len(row['chunks']) != (size+CHUNK-1)//CHUNK:
                fail('EXPORT_SHARD_INDEX', str(index), 'Invalid file size or chunk count')
            total += size
            if total > MAX_TOTAL: fail('EXPORT_SHARD_BUDGET', str(index), 'Excess total bytes')
            dest = inside(tmp, row['path'])
            dest.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with dest.open('xb') as stream:
                remaining = size
                for key in row['chunks']:
                    if not re.fullmatch('[0-9a-f]{64}', key):
                        fail('EXPORT_SHARD_INDEX', str(index), 'Invalid chunk key')
                    data = read(inside(index.parent/'chunks', key), min(remaining, CHUNK))
                    if len(data) != min(remaining, CHUNK) or sha(data) != key:
                        fail('EXPORT_SHARD_CHANGED', key, 'Chunk differs from index')
                    stream.write(data)
                    digest.update(data)
                    remaining -= len(data)
            if digest.hexdigest() != row['sha256']:
                fail('EXPORT_SHARD_CHANGED', row['path'], 'Reassembled file differs')
        _, entries, mh = open_plan(inside(tmp,spec['plan']))
        owned = {row['path']:(row['bytes'],row['sha256']) for row in files if row['path']!='manifest.json'}
        if (mh != spec['manifestSha256'] or entries[spec['plan']]['sha256'] != spec['planSha256'] or
                owned != {name:(row['bytes'],row['sha256']) for name,row in entries.items()}):
            fail('EXPORT_SHARD_INDEX', str(index), 'Reassembled stage differs from owning manifest')
        tmp.rename(out)
    finally:
        if tmp.exists(): shutil.rmtree(tmp)
    return dict(status='restored', files=len(files), plan=str(out/spec['plan']), manifestSha256=mh)
