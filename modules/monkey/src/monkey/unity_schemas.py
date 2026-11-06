"""Validate an explicit frozen pool of bundles for exact TypeTree borrowing."""
import re
from .io import safe, read, load, sha
from .sources.compiled import fail


def frozen_pool(manifest):
    manifest = safe(manifest)
    raw = read(manifest)
    data = load(raw)
    if data.get('schemaVersion') != 1 or not isinstance(data.get('files'), list) or not 1 <= len(data['files']) <= 2000:
        fail('UNITY_SCHEMA_MANIFEST', str(manifest), 'Expected 1..2000 explicitly frozen bundles')
    files, seen, total = [], set(), 0
    for row in data['files']:
        path = safe(manifest.parent / row['path'])
        size, digest = row.get('bytes'), row.get('sha256')
        if not path.is_file() or path in seen or type(size) is not int or not 0 < size <= 128*1024*1024 or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            fail('UNITY_SCHEMA_ENTRY', str(path), 'Invalid or duplicate frozen input identity')
        seen.add(path)
        total += size
        files.append(dict(path=str(path), bytes=size, sha256=digest))
    if total > 1024*1024*1024:
        fail('UNITY_SCHEMA_BUDGET', str(manifest), 'Aggregate pool exceeds 1 GiB')
    return dict(sourceManifestSha256=sha(raw), files=files)
