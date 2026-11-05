"""Verify pinned JsonUtility aggregates against independently saved Prefab receipts."""
import hashlib
import mmap
import re
import tempfile
from contextlib import ExitStack, contextmanager

from .io import fail, inside, load, read
from .sources.containers import fingerprint

MIB = 1024 * 1024
MAX_AGGREGATE = 1024 * MIB
MAX_ROW = 32 * MIB
FIELD = re.compile(rb'^    "([A-Za-z][A-Za-z0-9]*)": ', re.M)
SEPARATOR = re.compile(rb',\n        (?=[^ \t\r\n])')
FINAL_FIELDS = {'staticPreview', 'staticPreviews', 'nativeFiles', 'staticSpineReadbackFiles',
                'staticTextReadbackFiles', 'staticMaskReadbackFiles', 'buttonMaterialProjectionSha256'}


# Public fields emitted by the Unity Readback DTO for this pinned format.
FIELDS = FINAL_FIELDS | set('''components sceneComponents sceneComponentContract sceneComponentPhase
    staticPresentationValidation materialBinding prefabInstances candidatePrefabInstances nativeScope
    sourceGraphVerification gallery numericCodeBindings numericCodeExercise status unityVersion prefabGuid
    sceneGuid importPlanSha256 sourceManifestSha256 spriteCount nodeCount missingScripts editableRoundtrip
    sceneReopened previewPath previewSha256 previewError colorSpace staticRetainedAssetReadback dynamicUiProbes
    animations diagnostics nodes nativeInitialNodes sprites fonts labels viewReferences jsonAssets sourcePrefabs
    tmpResources'''.split())


def require(condition, message):
    if not condition:
        fail('NATIVE_AGGREGATE_INVALID', 'Analysis/Readback', message)


@contextmanager
def pinned_snapshot(path, expected):
    require(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected), 'Expected a SHA-256 pin')
    with tempfile.TemporaryFile() as copy, path.open('rb') as stream:
        digest = hashlib.sha256()
        punctuation = 0
        for block in iter(lambda: stream.read(MIB), b''):
            require(copy.tell() + len(block) <= MAX_AGGREGATE, 'Native aggregate exceeds 1024 MiB')
            # An upper bound on structural punctuation also rejects unusually dense
            # inputs before the decoder can allocate millions of short values.
            punctuation += sum(block.count(token) for token in (b',', b':', b'{', b'['))
            require(punctuation <= 40_000_000, 'Native aggregate exceeds structural budget')
            digest.update(block)
            copy.write(block)
        require(copy.tell() > 0 and digest.hexdigest() == expected, f'{path.name} SHA-256 differs')
        copy.flush()
        with mmap.mmap(copy.fileno(), 0, access=mmap.ACCESS_READ) as data:
            yield data


def fields(data):
    require(data[:2] == b'{\n' and data[-2:] == b'\n}', 'Incomplete JsonUtility object')
    matches = []
    for match in FIELD.finditer(data):
        require(len(matches) < 96, 'Too many aggregate fields')
        matches.append(match)
    require(matches and matches[0].start() == 2, 'Unexpected object prefix')
    result = {}
    for i, match in enumerate(matches):
        name = match[1].decode('ascii')
        end = len(data) - 2
        if i + 1 < len(matches):
            end = matches[i+1].start() - 2
            require(data[end:end+2] == b',\n', 'Invalid object separator')
        require(name in FIELDS and name not in result, 'Unknown or duplicate aggregate field ' + name)
        result[name] = (match.end(), end)
    return result


def parse_field(data, start, end):
    if data[start:start+2] != b'[\n':
        require(end-start <= MAX_ROW, 'Native object exceeds bounded field size')
        return load(data[start:end], max_nodes=2_000_000)
    require(data[start:start+10] == b'[\n        ' and data[end-6:end] == b'\n    ]', 'Invalid array boundary')
    cursor = start + 10
    rows = []
    for sep in SEPARATOR.finditer(data, cursor, end-6):
        require(len(rows) < 250_000 and sep.start()-cursor <= MAX_ROW, 'Native array exceeds row budget')
        rows.append(load(data[cursor:sep.start()], max_nodes=2_000_000))
        cursor = sep.end()
    require(end-6-cursor <= MAX_ROW, 'Final native row exceeds size budget')
    rows.append(load(data[cursor:end-6], max_nodes=2_000_000))
    return rows


def prefab_rows(root, data, bounds, instruction, plan_sha):
    start, end = bounds
    cursor = start
    directory = inside(root, 'Analysis/Readback/Prefabs')
    files = {p.name for p in directory.iterdir()}
    specs = instruction['sourcePrefabs']
    require(0 < len(specs) == len(files) <= 25_000, 'Independent receipt count differs')
    rows = []
    sequence = hashlib.sha256()
    for index, spec in enumerate(specs):
        path = spec['path']
        meta = inside(root, path+'.meta')
        ids = re.findall(rb'(?m)^guid: ([a-f0-9]{32})$', read(meta, max_bytes=MIB))
        require(len(ids) == 1, 'Missing native GUID for '+path)
        guid = ids[0].decode()
        name = guid+'.json'
        require(name in files, 'Missing or duplicate receipt '+name)
        files.remove(name)
        raw = read(inside(directory, name), max_bytes=MAX_ROW)
        row = load(raw, max_nodes=2_000_000)
        require(row.get('sourceId') == spec['sourceId'] and row.get('path') == path and row.get('guid') == guid
                and row.get('importPlanSha256') == plan_sha
                and row.get('sourceManifestSha256') == instruction['sourceManifestSha256']
                and row.get('prefabSha256') == fingerprint(inside(root, path))
                and row.get('prefabMetaSha256') == fingerprint(meta), 'Prefab receipt identity differs: '+path)
        embedded = (b'[\n        ' if index == 0 else b',\n        ') + raw.replace(b'\n', b'\n        ')
        require(cursor+len(embedded) <= end and data[cursor:cursor+len(embedded)] == embedded,
                'Aggregate Prefab order or content differs: '+path)
        cursor += len(embedded)
        rows.append(row)
        sequence.update(hashlib.sha256(raw).digest())
    require(end-cursor == 6 and data[cursor:end] == b'\n    ]' and not files, 'Extra or missing Prefab data')
    return rows, sequence.hexdigest()


def read_pair(root, instruction, plan_sha, editor_pin, source_pin):
    with ExitStack() as stack:
        def snapshot(name, pin):
            path = inside(root, 'Analysis/Readback/'+name+'-readback.json')
            return stack.enter_context(pinned_snapshot(path, pin))
        editor = snapshot('editor', editor_pin)
        source = snapshot('source-prefabs', source_pin)
        main, prior = fields(editor), fields(source)
        require(list(main) == list(prior), 'Aggregate field order or names differ')
        require('sourcePrefabs' in main, 'Missing aggregate sourcePrefabs')
        result = {}
        for name, (start, end) in main.items():
            old_start, old_end = prior[name]
            if name not in FINAL_FIELDS:
                with memoryview(editor)[start:end] as a, memoryview(source)[old_start:old_end] as b:
                    require(len(a) == len(b) and hashlib.sha256(a).digest() == hashlib.sha256(b).digest(),
                            'Aggregate field signature differs: '+name)
            else:
                parse_field(source, old_start, old_end)
            if name == 'sourcePrefabs':
                result[name], order_pin = prefab_rows(root, editor, (start,end), instruction, plan_sha)
            else:
                result[name] = parse_field(editor, start, end)
        require(result.get('importPlanSha256') == plan_sha and
                result.get('sourceManifestSha256') == instruction['sourceManifestSha256'], 'Aggregate source pins differ')
        return result, dict(editorSha256=editor_pin, sourcePrefabsSha256=source_pin,
                            prefabCount=len(result['sourcePrefabs']), orderedReceiptSha256=order_pin,
                            editorBytes=len(editor), sourcePrefabsBytes=len(source))


def write_verified_report(out, result, blockers):
    """Keep the full evidence and publish a bounded manifest for pinned aggregates."""
    import gzip
    import io
    import json
    from collections import Counter
    from .io import finish, write_json

    report_path = out/'verification.json.gz'
    with report_path.open('xb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', compresslevel=1, mtime=0) as packed:
            with io.TextIOWrapper(packed, encoding='utf-8') as stream:
                json.dump(result, stream, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    detailed = {'componentCoverage', 'diagnostics', 'nativeDiagnostics', 'blockingDiagnostics',
                'remainingDynamicDiagnostics', 'resolvedNativeDiagnostics', 'savedGeneratedMetaReadback'}
    summary = {key:value for key,value in result.items() if key not in detailed}
    summary['reportFormat'] = 'monkey-unity-verification-gzip/1'
    summary['fullVerificationReport'] = dict(path=report_path.name, sha256=fingerprint(report_path),
                                             bytes=report_path.stat().st_size, encoding='gzip+utf-8-json')
    summary['diagnosticCount'] = len(result['diagnostics'])
    summary['blockingCodes'] = dict(Counter(row['code'] for row in result.get('blockingDiagnostics', [])))
    examples = {}
    for row in result.get('blockingDiagnostics', []):
        examples.setdefault(row['code'], {key:row.get(key) for key in ('code','sourceId','location','message')})
    summary['blockingExamples'] = list(examples.values())
    write_json(out/'verification.json', summary)
    stored = finish(out,summary,blocking_diagnostics=blockers)
    return dict(result, **{key:stored[key] for key in ('status','files','limits','fullVerificationReport')})
