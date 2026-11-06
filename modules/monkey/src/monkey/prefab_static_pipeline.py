"""Preserve source-serialized fields in an independently owned conversion stage.

This is conversion-time evidence, not a target runtime object-graph interpreter.
Native field carriers and declaration defaults remain separately unverified.
"""
from pathlib import Path
from . import __version__, io
from .output_limits import copy_verified
from .sources.compiled import fail
from .prefab_static_fields import extract_static_fields, StaticFieldError


def attach_static_fields(manifest, ir):
    """Attach exact source records without promoting native convertibility."""
    try:
        report = extract_static_fields(manifest, ir)
    except StaticFieldError as error:
        fail('STATIC_FIELDS_INVALID', 'components', str(error))
    ir['diagnostics'] = [d for d in ir.get('diagnostics', []) if not d.get('code', '').startswith('STATIC_FIELDS_')]
    ir['diagnostics'].extend(io.diagnostic('STATIC_FIELDS_' + d['code'], d['sourceId'], d['message'], d['sourceId']) for d in report['diagnostics'])
    by_id = {row['sourceId']: row for row in report['components']}
    for component in ir['components']:
        component.pop('staticFieldSnapshot', None)
        row = by_id.get(component['sourceId'])
        if row is not None:
            component['staticFieldSnapshot'] = dict(row, native='not_run',
                                                   declarationDefaults='unverified')
    report.update(sourceManifestSha256=ir.get('sourceManifestSha256'),
                  componentCount=len(by_id),
                  serializedFieldCount=sum(len(row['fields']) for row in by_id.values()),
                  declarationDefaults='unverified', native='not_run',
                  behaviorPolicy='disabled', behaviorExecuted=False)
    ir['staticFieldPreservation'] = {
        key: report[key] for key in ('componentCount', 'serializedFieldCount',
                                    'declarationDefaults', 'native', 'behaviorPolicy')}
    ir['staticFieldPreservation']['report'] = 'prefab-static-fields.json'
    return report


def project_ir(source_manifest_path, ir_path, output):
    """Reuse frozen normalized resources; never overwrite or re-extract inputs."""
    source_path, ir_path = io.safe(source_manifest_path), io.safe(ir_path)
    source_raw, ir_raw = io.stage_bytes(source_path), io.stage_bytes(ir_path)
    source = io.load(source_raw, max_nodes=8_000_000)
    ir = io.load(ir_raw, max_nodes=8_000_000)
    owner = io.stage_manifest(ir_path.parent)
    digest = io.sha(source_raw)
    if ir.get('sourceManifestSha256') != digest or owner.get('sourceManifestSha256') != digest:
        fail('STATIC_FIELDS_SOURCE_MISMATCH', str(source_path), 'IR and owning stage must bind this exact source manifest')
    if source.get('sourceProfile') != ir.get('sourceProfile') or owner.get('sourceProfile') != ir.get('sourceProfile'):
        fail('STATIC_FIELDS_PROFILE_MISMATCH', str(source_path), 'Source profiles differ')
    report = attach_static_fields(source, ir)
    out = io.new_output(output, [source_path.parent, ir_path.parent])
    seen = set()
    for item in owner.get('files', []):
        relative = item['path']
        if relative in seen:
            fail('STATIC_FIELDS_DUPLICATE_FILE', relative, 'Duplicate source stage path')
        seen.add(relative)
        if relative in ('ir.json', 'prefab-static-fields.json'):
            continue
        copy_verified(io.inside(ir_path.parent, relative), io.inside(out, relative),
                      item['sha256'], item['bytes'])
    ir['staticFieldParentIrSha256'] = io.sha(ir_raw)
    ir['toolVersion'] = __version__
    io.write_json(out / 'prefab-static-fields.json', report)
    io.write_json(out / 'ir.json', ir)
    return io.finish(out, ir)


def ensure_static_fields(ir):
    """Enrich old frozen IR in memory without changing its font/resource identity."""
    if ir.get('staticFieldPreservation') or not ir.get('sourceManifestPath'):
        return
    from .prefab_completeness import SUPPORTED
    if ir.get('sourceProfile') not in SUPPORTED:
        return
    raw = io.stage_bytes(Path(ir['sourceManifestPath']))
    if io.sha(raw) != ir.get('sourceManifestSha256'):
        fail('STATIC_FIELDS_SOURCE_MISMATCH', ir['sourceManifestPath'], 'Frozen source manifest changed')
    attach_static_fields(io.load(raw, max_nodes=8_000_000), ir)


def enrich_declarations(ir, source_path, expected_sha256):
    """Merge AST-proven constructor defaults, then exact serialized overrides."""
    from .prefab_static_declarations import extract_declarations
    if not source_path and not expected_sha256: return
    if not source_path or not expected_sha256:
        fail('STATIC_DECLARATION_PIN_REQUIRED', 'source', 'Both source bundle and SHA-256 are required')
    rows=[c['staticFieldSnapshot']for c in ir['components']if c.get('staticFieldSnapshot')]
    if not rows:return
    report=extract_declarations(io.safe(source_path), expected_sha256, sorted({r['sourceType']for r in rows}))
    fatal=[d for d in report['diagnostics']if not d.get('sourceType')]
    if fatal:fail('STATIC_DECLARATION_FAILED', str(source_path), str(fatal))
    ir.setdefault('diagnostics',[]).extend(io.diagnostic('STATIC_DECLARATION_'+d['code'],d.get('sourceType','source'),str(d))for d in report['diagnostics'])
    def encode(value):
        if value is None:return dict(kind='null',value=None)
        if type(value)is bool:return dict(kind='bool',value=value)
        if type(value)in(int,float):return dict(kind='float',value=value)
        if isinstance(value,str):return dict(kind='string',value=value)
        if isinstance(value,list):return dict(kind='array',value=[encode(v)for v in value])
        if isinstance(value,dict):return dict(kind='object',value={k:encode(v)for k,v in value.items()})
        fail('STATIC_DEFAULT_UNSUPPORTED','value','Unsupported literal default')
    for snapshot in rows:
        record=report['components'].get(snapshot['sourceType'])
        if not record:continue
        types={p['name']:p['types'][0]for p in record.get('propertyTypes',[])if len(p.get('types',[]))==1}
        fields={}
        for f in record['fields']:
            fields[f['name']]=dict(name=f['name'],**encode(f['value']),declarationEvidence={k:v for k,v in f.items()if k not in ('kind','value','name')})
        for f in snapshot['fields']:
            merged=dict(fields.get(f['name'],{}),**f)
            merged['serializedOverride']=True
            fields[f['name']]=merged
        for name,f in fields.items():
            if name in types:f['sourceDeclaredType']=types[name]
        snapshot['fields']=[fields[n]for n in sorted(fields)]
        snapshot['declarationEvidence']=dict(sourceBundleSha256=expected_sha256,**{k:v for k,v in record.items()if k!='fields'})
        snapshot['declarationDefaults']='verified' if not record['gaps'] else 'partial'
        snapshot['gaps']=[g for g in snapshot['gaps']if g!='source_declaration_defaults_not_verified']
        snapshot['gaps'].extend('declaration:'+str(g)for g in record['gaps'])
    ir['staticDeclarationSourceSha256']=expected_sha256
