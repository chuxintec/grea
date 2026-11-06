"""Bounded typed Unity source inspection through an explicitly selected provider."""
import subprocess
from pathlib import Path
from ..io import safe, read, sha, load, new_output, write_json
from .compiled import fail

from ..unity_parse_limits import parse_limits as resolve_limits,reader_fingerprint,MAX_DOCUMENT_NODES
from ..unity_payloads import validate_payloads

PROFILE = 'unity-serialized-unitypy-1.25.3'
MAX_BYTES = 128 * 1024 * 1024


CONTAINER_SIGNATURES = (b'UnityFS\0', b'UnityRaw\0', b'UnityWeb\0', b'UnityWebData1.0\0')


def container_kind(header):
    """Exact original container signature; serialized contents remain strict provider reads."""
    if header.startswith(b'UnityWebData1.0\0'):
        return 'unitywebdata'
    if header.startswith(CONTAINER_SIGNATURES[:3]):
        return 'unityfs'
    return None


def inspect(source, provider_python, output, budget_seconds=120, schema_manifest=None, parse_limits=None):
    if not 1 <= budget_seconds <= 1200:
        fail('UNITY_PROVIDER_BUDGET', '$', 'Expected 1..1200 seconds')
    limits=resolve_limits(parse_limits)
    source = safe(source)
    if not source.is_file():
        fail('UNITY_INPUT_FILE', str(source), 'Expected one explicit serialized file or AssetBundle')
    requested_python = Path(provider_python).absolute()
    safe(requested_python.parent)
    python = safe(requested_python.resolve(strict=True))
    if not python.is_file():
        fail('UNITY_PROVIDER_MISSING', str(python), 'Explicit provider Python is unavailable')
    raw = read(source, max_bytes=MAX_BYTES)
    pool = None
    if schema_manifest:
        from ..unity_schemas import frozen_pool
        pool = frozen_pool(schema_manifest)
    out = new_output(output, [source, python.parent, *([safe(schema_manifest), *[Path(r['path']) for r in pool['files']]] if pool else [])])
    receipt = dict(schemaVersion=1, sourceProfile=PROFILE, status='started', source=dict(path=str(source), bytes=len(raw), sha256=sha(raw)),
                   providerPythonSha256=sha(read(python,max_bytes=MAX_BYTES)), budgetSeconds=budget_seconds,
                   sourceCodeExecuted=False, editor='not_run', processExited=False)
    write_json(out/'inspection.json',receipt)
    write_json(out/'schema-job.json',dict(source=str(source),schemaPool=pool,parseLimits=limits,readerContractSha256=reader_fingerprint()))
    receipt.update(parseLimits=limits,readerContractSha256=reader_fingerprint())
    if pool:receipt['schemaManifestSha256']=pool['sourceManifestSha256']
    arguments=['--inspect-with-schemas',str(out/'schema-job.json'),str(out/'typed-objects.json')]
    with (out/'provider.log').open('wb') as log:
        process = subprocess.Popen([str(requested_python), '-I', '-B', str(Path(__file__).with_name('unity_worker.py')),*arguments],
                                   cwd=out, stdout=log, stderr=subprocess.STDOUT)
        receipt['pid'] = process.pid
        try:
            receipt['exitCode'] = process.wait(timeout=budget_seconds)
        except subprocess.TimeoutExpired:
            receipt['status'] = 'timeout';process.terminate()
            try:
                receipt['exitCode'] = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                receipt['status'] = 'pending_child_exit'
        receipt['processExited'] = process.poll() is not None
    if receipt.get('exitCode') == 0:
        typed_raw = read(out/'typed-objects.json', max_bytes=MAX_BYTES)
        typed = load(typed_raw,max_nodes=MAX_DOCUMENT_NODES,max_depth=128)
        if typed.get('schemaVersion') != 1 or typed.get('source') != {k:receipt['source'][k] for k in ('bytes','sha256')}:
            fail('UNITY_PROVIDER_RECEIPT',str(out),'Provider source identity differs')
        validate_payloads(out,typed)
        if typed.get('parseLimits')!=limits:fail('UNITY_PROVIDER_LIMITS',str(out),'Parser policy changed')
        receipt['parseUsage']=typed['parseUsage']
        receipt['performance']=load(read(out/'reader-runtime.json'))
        receipt.update(status='partial' if typed['summary']['unparsed'] else 'inspected',
                       summary=typed['summary'], typedObjectsSha256=sha(typed_raw), provider=typed['provider'])
    elif receipt['status'] == 'started':
        receipt['status'] = 'provider_failed'
    receipt['sourceUnchanged'] = sha(read(source,max_bytes=MAX_BYTES)) == receipt['source']['sha256']
    if not receipt['sourceUnchanged']:
        receipt['status'] = 'source_changed'
    write_json(out/'inspection.json',receipt)
    return receipt
