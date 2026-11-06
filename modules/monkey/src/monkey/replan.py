"""Create-only, verified source-stage reuse for the explicit names-metadata migration."""
import os
import shutil
from pathlib import Path
from .io import safe,inside,read,load,sha,write_json,stage_manifest,stage_document,finish
from .sources.containers import fingerprint
from .sources.compiled import fail
from .signatures import phase_signatures
from .stage_contracts import compatible
from .names import source_names
from .layout.standard import analysis_rel

# Reviewed 838d05b geometry/pixel stage; only source-name metadata is added here.
_NAMES_V1_FROM=('87e3c05e3e4c3398cc9b33cae2adb23ff114980b50af651c1ff08695817ab56e',
                '64f902e01c423f08df594009669b9ee7ecb94c66af4fc2610b87c0b8c82eddfa')

# c3e97a3 adds name metadata only; directory/device-name guard changes no geometry.
_NAMES_V1_C3=('30f3edcd872a12cdd43f10bf6b266797b3cd3bdc014c5afadb05b61b8756e1b7',
              'a324312d1a35ac0a85830fceb98fdfe57326d97d4b384f64c45d261b69ce66cb')


def reuse_source_stages(previous,out,selection,namespace):
    old=safe(previous);out=safe(out)
    receipt=load(read(old/'conversion-result.json'))
    if (not receipt.get('completed') or not selection or receipt.get('inputSet',{}).get('sha256')!=selection['sha256']
            or receipt.get('namespace')!=namespace):
        fail('REPLAN_SOURCE_IDENTITY',str(old),'Completed input-set and namespace must match exactly')
    signatures=load(read(old/'Structured/stage-signatures.json'));current=phase_signatures()
    pair=tuple(signatures[k]['sha256'] for k in ('inspect','normalize'))
    if pair not in (_NAMES_V1_FROM,_NAMES_V1_C3) and not all(compatible(signatures,current,k) for k in ('inspect','normalize')):
        fail('REPLAN_ALGORITHM_UNSUPPORTED',str(old),'Only exact current stages or the reviewed names-v1 metadata migration are accepted')
    stages={k:stage_manifest(old/'Structured'/k) for k in ('inspect','normalize')}
    for k,manifest in stages.items():
        root=old/'Structured'/k
        expected={f['path'] for f in manifest['files']}|{'manifest.json'}
        actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
        if actual!=expected:fail('REPLAN_STAGE_DRIFT',k,'Unknown or missing generated source-stage file')
        for f in manifest['files']:
            p=inside(root,f['path'])
            if p.stat().st_size!=f['bytes'] or fingerprint(p)!=f['sha256']:
                fail('REPLAN_STAGE_DRIFT',f['path'],'Source-stage bytes differ from owning manifest')
    source=stage_document(old/'Structured/inspect/source-manifest.json')
    ir=stage_document(old/'Structured/normalize/ir.json')
    if ir['sourceManifestSha256']!=sha(read(old/'Structured/inspect/source-manifest.json',max_bytes=128*1024*1024)):
        fail('REPLAN_SOURCE_IDENTITY','normalize','IR is not bound to the source stage')
    roots={}
    for name,root in source['sourceRoots'].items():
        p=safe(root)
        if not p.is_relative_to(old/'InputTree'):fail('REPLAN_SOURCE_ROOT',name,'Old source root escaped immutable input tree')
        roots[name]=out/'InputTree'/p.relative_to(old/'InputTree')
    for item in source['inputs']:
        path=inside(roots[item.get('bundle',source['bundle'])],item['path'])
        if not path.is_file() or path.stat().st_size!=item['bytes'] or fingerprint(path)!=item['sha256']:
            fail('REPLAN_INPUT_CHANGED',item['path'],'Current supplied bytes differ from frozen source receipt')
    stage=out/'Structured'
    if stage.exists():fail('REPLAN_OUTPUT_EXISTS',str(stage),'Source reuse requires a fresh stage directory')
    stage.mkdir()
    for kind,manifest in stages.items():
        target=stage/kind;target.mkdir()
        document='source-manifest.json' if kind=='inspect' else 'ir.json'
        for f in manifest['files']:
            if f['path']==document:continue
            a=inside(old/'Structured'/kind,f['path']);b=inside(target,f['path']);b.parent.mkdir(parents=True,exist_ok=True)
            from .output_limits import copy_verified
            copy_verified(a,b,f['sha256'],f['bytes'])
    provenance=dict(schemaVersion=1,mode='verified-source-stages-v2',sourceOutput=str(old),
        oldStageSignatures=dict(zip(('inspect','normalize'),pair)),pixelDecoderExecuted=False,sourceReaderExecuted=False,
        sourceStageManifests={k:fingerprint(old/'Structured'/k/'manifest.json') for k in stages})
    source['sourceRoots']={k:str(p) for k,p in roots.items()}
    primary=safe(source['sourceRoot']);source['sourceRoot']=str(out/'InputTree'/primary.relative_to(old/'InputTree'))
    source['stageReuse']=provenance
    write_json(stage/'inspect/source-manifest.json',source);finish(stage/'inspect',dict(source))
    ir.update(sourceNames=source_names(source),sourceRoots=source['sourceRoots'],
        sourceManifestPath=str(stage/'inspect/source-manifest.json'),
        sourceManifestSha256=fingerprint(stage/'inspect/source-manifest.json'),stageReuse=provenance)
    write_json(stage/'normalize/ir.json',ir);finish(stage/'normalize',dict(ir))
    write_json(stage/'stage-signatures.json',current);write_json(stage/'source-stage-reuse.json',provenance)
    return provenance


def reused_code(previous,selection,namespace,rows):
    old=safe(previous);receipt=load(read(old/'conversion-result.json'))
    if not selection or receipt.get('inputSet',{}).get('sha256')!=selection['sha256'] or receipt.get('namespace')!=namespace or not receipt.get('completed'):
        fail('REPLAN_SOURCE_IDENTITY',str(old),'Code reuse requires the exact completed input-set and namespace')
    signatures=load(read(old/'Structured/stage-signatures.json'));current=phase_signatures()
    for file in ('sources/code.py','sources/index-modules.cjs'):
        if signatures['package']['files'].get(file)!=current['package']['files'].get(file):
            fail('REPLAN_CODE_ALGORITHM_CHANGED',file,'Source parser changed; do not reuse recovered modules')
    project=receipt['projects'][0];root=old/project['path']
    if fingerprint(root/'manifest.json')!=project['manifestSha256']:fail('REPLAN_STAGE_DRIFT','manifest','Old candidate identity changed')
    owned={f['path']:f for f in stage_manifest(root)['files']}
    def checked(relative):
        raw=read(inside(root,relative),max_bytes=128*1024*1024)
        if relative not in owned or sha(raw)!=owned[relative]['sha256']:fail('REPLAN_STAGE_DRIFT',relative,'Recovered source evidence changed')
        return raw
    previous_rows=load(checked(analysis_rel(root,'resource-ledger.json')),max_nodes=8_000_000)['files']
    if {r['path']:(r['sha256'],r['bytes']) for r in previous_rows}!={r['path']:(r['sha256'],r['bytes']) for r in rows}:
        fail('REPLAN_INPUT_CHANGED',str(old),'Current full input inventory differs from the frozen source cache')
    modules=load(checked(analysis_rel(root,'code-index.json')),max_nodes=8_000_000)['modules']
    for mod in modules:
        if mod.get('entryType')=='module_candidate':mod['source']=checked(mod['sourceEvidence']).decode('utf-8')
        for key in ('targetBindings','draft','sourceEvidence','source_recovered','translated_supported','compiled','behavior_verified'):mod.pop(key,None)
    diagnostics=[d for d in receipt.get('diagnostics',[]) if d['code'] in ('UNSUPPORTED_WRAPPER','MODULE_RECOVERY_PARTIAL')]
    return modules,diagnostics
