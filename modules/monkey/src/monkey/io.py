"""Create-only output and bounded immutable source reads."""
import hashlib
import json
from pathlib import Path
from .sources.compiled import budget, fail

MAX_BYTES = 32 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe(path):
    from .input_relocation import relocate
    path = relocate(Path(path).absolute())
    if any(p.is_symlink() for p in (path, *path.parents)):
        fail('SYMLINK_PATH', str(path), 'Symbolic links are not accepted')
    return path.resolve()


def inside(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        fail('UNSAFE_PATH', str(relative), 'Expected relative path')
    path = safe(root / relative)
    if not path.is_relative_to(root):
        fail('UNSAFE_PATH', relative, 'Path escapes root')
    return path


def read(path, max_bytes=MAX_BYTES):
    path = safe(path)
    with path.open('rb') as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        fail('BYTE_BUDGET', str(path), 'Input exceeds declared byte budget')
    return raw


def load(raw, max_nodes=3_000_000, max_depth=96):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                fail('DUPLICATE_KEY', '$', key)
            out[key] = value
        return out
    result = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs,
                        parse_constant=lambda x: fail('NONFINITE_NUMBER', '$', x))
    budget(result, max_nodes=max_nodes, max_depth=max_depth)
    return result


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('utf-8')


def write_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(encoded(value))


def stage_bytes(path):
    """Larger generated documents still require an owning manifest and bounded bytes."""
    path=safe(path)
    manifest=load(read(path.parent/'manifest.json',max_bytes=128*1024*1024),max_nodes=8_000_000)
    entry=next((f for f in manifest.get('files',[]) if f['path']==path.name),{})
    if not entry or entry.get('bytes',0)>128*1024*1024:fail('STAGE_DOCUMENT_BUDGET',str(path),'Missing or oversized generated document')
    raw=read(path,max_bytes=128*1024*1024)
    if entry.get('sha256')!=sha(raw) or entry.get('bytes')!=len(raw):
        fail('STAGE_DOCUMENT_CHANGED',str(path),'Document differs from its owning stage manifest')
    return raw


def stage_manifest(directory):
    return load(read(safe(directory)/'manifest.json',max_bytes=128*1024*1024),max_nodes=8_000_000)


def stage_document(path):
    """Verify the generated document against its owning stage manifest."""
    return load(stage_bytes(path),max_nodes=8_000_000)


def new_output(path, inputs=()):
    path = safe(path)
    for item in inputs:
        item = safe(item)
        if path == item or path.is_relative_to(item) or item.is_relative_to(path):
            fail('OUTPUT_OVERLAP', str(path), 'Output overlaps an input')
    if path.exists():
        fail('OUTPUT_EXISTS', str(path), 'Use a fresh candidate directory')
    path.mkdir(parents=True, exist_ok=False)
    return path


def diagnostic(code, location, message, source_id=None):
    severe = any(token in code for token in ('MISSING','INVALID','CYCLE','BOUNDS','EXCEEDED','CHANGED'))
    return dict(code=code, location=location, message=message, sourceId=source_id,
                severity='error' if severe else 'warning', affectedScope=source_id or 'selection')


def finish(out, report, *, blocking_diagnostics=None):
    from .output_limits import digest_file, check_inventory
    report['files'] = [dict(path=p.relative_to(out).as_posix(), sha256=digest_file(p),
                            bytes=p.stat().st_size, owner=('manual' if p.relative_to(out).as_posix().startswith(('Assets/Manual/','assets/manual/')) else 'generated'))
                       for p in sorted(out.rglob('*')) if p.is_file() and p != out / 'manifest.json']
    report['limits'] = check_inventory(report['files'], report, str(out))
    from .identities import assigned
    assigned(out,report)
    report['status'] = 'partial' if (report.get('diagnostics') if blocking_diagnostics is None else blocking_diagnostics) else 'candidate'
    write_json(out / 'manifest.json', report)
    return report
