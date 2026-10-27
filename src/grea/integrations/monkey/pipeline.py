"""Explicit monkey CLI plans; conversion stays in the external provider.

Plans bind the actual command, provider files, declared inputs and capabilities.
Execution only accepts an unchanged saved plan; no raw argv or shell strings.
"""
import json
from pathlib import Path
from grea import artifacts, registry, runner
from grea.common import digest, hash_file, write_new
from grea.safe_paths import canonical_path, disjoint
from .identity import read, pinned

# 0.4.1 = 0.4.0 conversion plus the toolkit received from GREA (same CLI options).
SUPPORTED_VERSIONS = ('0.4.0', '0.4.1', '0.6.0')
# Options are transcribed from the versioned CLI, not passed through wholesale.
OPERATIONS = {
    'convert': {
        'required': {'target'},
        'paths': {'source', 'input-set', 'layout', 'provider-python', 'asset-ripper',
                  'unity-texture-cache', 'unity-dependency-manifest', 'unity-prepared-textures',
                  'unity-reuse-provider-export', 'unity-reuse-inspection', 'unity-code-evidence',
                  'unity-schema-manifest', 'numeric-code-contract', 'reuse-source-stages'},
        'values': {'target': ('unity6','cocos38','both'),
                   'source-family': ('cocos','unity'), 'unity-export-scope': ('all',),
                   'cocos-code-language': ('ts','js')},
        'integers': {'provider-budget-seconds': (1,1800), 'unity-object-value-limit': (1,1000000),
                     'unity-container-value-limit': (1,16000000)},
        'flags': {'offline','unity-quarantine-invalid-textures'},
    },
    'prepare-unity-bulk': {
        'required': {'inspection','texture-cache','capture','provider-python'},
        'paths': {'inspection','texture-cache','capture','provider-python'},
        'integers': {'budget-seconds': (1,1800)},
    },
    'export-unity-bulk': {
        'required': {'prepared','asset-ripper','deadline-utc','window-end-utc'},
        'paths': {'prepared','asset-ripper'}, 'integers': {'budget-seconds': (1,1800)},
        'text': {'deadline-utc','window-end-utc'},
    },
    'layout-preview': {'required': {'conversion','layout'}, 'paths': {'conversion','layout'}},
    'layout-migration': {'required': {'from','to'}, 'paths': {'from','to'}},
}


def command_identity():
    entry = registry.tool('monkey')
    return {'command': registry.command(entry), 'probe': registry.command(entry, probe=True)}


def snapshot(roots, max_files=200000, max_bytes=32*1024**3):
    """Keep one aggregate budget across explicitly declared disjoint roots."""
    result=[]
    for root in roots:
        value=artifacts.inspect_target(root,max_files=max_files,max_bytes=max_bytes)
        if value['coverage']!='complete':
            raise ValueError('Input snapshot exceeds declared budget')
        files=value.get('files',[value['target']])
        max_files-=len(files);max_bytes-=sum(f['bytes'] for f in files)
        if max_files<0 or max_bytes<0:raise ValueError('Aggregate input budget exceeded')
        result.append(value)
    return result


def probe(lock, output):
    cfg=pinned(lock)
    if cfg['schema_version']!=2:raise ValueError('Bulk pipeline requires launcher-bound provider lock v2')
    if cfg['version'] not in SUPPORTED_VERSIONS:
        raise ValueError('Unsupported pinned monkey version; use a supported fixed provider or monkey_bridge for historical contracts')
    value,_,error=runner.execute('monkey',[],output,probe=True,timeout_seconds=20,
                                max_output_bytes=1024**2,max_inline_bytes=1024**2)
    cap=value.get('parsed_stdout')
    if error or not value.get('capture_complete') or not isinstance(cap,dict):
        raise ValueError('Provider capability probe failed')
    if cap.get('version')!=cfg['version'] or cap.get('schemaVersion')!=1 or digest(cap)!=cfg['capabilities_sha256']:
        raise ValueError('Provider capabilities differ from lock')
    return cfg,cap


def validate_request(request):
    if set(request)!={'schema_version','operation','options','input_roots','timeout_seconds'} or type(request['schema_version']) is not int or request['schema_version']!=1:
        raise ValueError('Expected pipeline request v1')
    op=request['operation'];spec=OPERATIONS.get(op)
    if spec is None:raise ValueError('Unsupported pipeline operation')
    options=request['options']
    if not isinstance(options,dict):raise ValueError('Expected named options')
    allowed=set().union(*(set(spec.get(k,())) for k in ('paths','values','integers','flags','text')))
    if not spec['required']<=options.keys() or set(options)-allowed:
        raise ValueError('Missing or unsupported operation options')
    budget=request['timeout_seconds']
    if type(budget) is not int or not 1<=budget<=1800:raise ValueError('Timeout must be 1..1800 seconds')
    roots=request['input_roots']
    if not isinstance(roots,list) or not 1<=len(roots)<=64:raise ValueError('Explicit bounded input roots required')
    roots=[canonical_path(p) for p in roots]
    for i,root in enumerate(roots):
        if not root.exists():raise ValueError('Declared input missing')
        disjoint(root,*roots[:i])
    argv=[op]
    for key,value in sorted(options.items()):
        if key in spec.get('paths',()):
            path=Path(value).expanduser().resolve(strict=True) if key in ('provider-python','asset-ripper') else canonical_path(value)
            if not path.exists() or not any(path==r or path.is_relative_to(r) for r in roots):
                raise ValueError('Option path must be inside a declared frozen input root: '+key)
            value=str(Path(value).expanduser().absolute()) if key in ('provider-python','asset-ripper') else str(path)
        elif key in spec.get('values',{}):
            if value not in spec['values'][key]:raise ValueError('Unsupported value: '+key)
        elif key in spec.get('integers',{}):
            low,high=spec['integers'][key]
            if type(value) is not int or not low<=value<=high:raise ValueError('Invalid budget: '+key)
            if key.endswith('seconds') and value>budget:raise ValueError('Provider budget exceeds process budget')
        elif key in spec.get('flags',()):
            if type(value) is not bool:raise ValueError('Expected boolean: '+key)
            if value:argv.append('--'+key)
            continue
        else:
            from datetime import datetime
            if not isinstance(value,str):raise ValueError('Expected UTC timestamp')
            stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
            if stamp.utcoffset() is None:raise ValueError('Timestamp must include timezone')
        argv.extend(['--'+key,str(value)])
    if op=='convert':
        if ('source' in options)==('input-set' in options):raise ValueError('Select source or input-set')
        if options.get('source-family')=='unity':
            if options['target']!='unity6' or options.get('unity-export-scope')!='all' or not {'source','unity-dependency-manifest','provider-python','asset-ripper'}<=options.keys():
                raise ValueError('Unity bulk conversion requires all scope, full dependency manifest and explicit providers')
        elif options.get('source-family')!='cocos':raise ValueError('Declare cocos or unity source family; generic image galleries are not initial projects')
    validate_references(options,roots)
    return argv,roots


def plan(config, request_path, output):
    request=read(request_path);argv,roots=validate_request(request)
    cfg=pinned(config)
    out=disjoint(output,request_path,config,*roots,*[r['path'] for r in cfg['identity_files']])
    if out.exists() or not out.parent.is_dir():raise ValueError('Use a fresh plan output')
    out.mkdir()
    try:
        cfg,cap=probe(config,out/'capabilities')
        if request['operation'] not in cap.get('implemented',[]):raise ValueError('Operation not advertised by pinned provider')
        record=dict(schema_version=1,kind='monkey-execution-plan',provider_version=cfg['version'],
                    lock=hash_file(config),request=hash_file(request_path),command_identity=command_identity(),
                    argv=argv,input_snapshot=snapshot(roots),timeout_seconds=request['timeout_seconds'],
                    executed=False,native_validation='not_run',business_validation='not_run')
        pinned(config);write_new(out/'plan.json',record)
        return record
    except Exception as error:
        write_new(out/'failure.json',dict(status='failed',message=str(error)));raise


def execute(config, plan_path, output):
    p=read(plan_path,128*1024**2)
    if p.get('kind')!='monkey-execution-plan' or p.get('schema_version')!=1 or p.get('executed') is not False:raise ValueError('Expected saved pipeline plan')
    if hash_file(config)!=p['lock'] or hash_file(p['request']['path'])!=p['request']:raise ValueError('Plan request or lock changed')
    request=read(p['request']['path']);argv,roots=validate_request(request)
    if argv!=p['argv'] or request['timeout_seconds']!=p['timeout_seconds']:raise ValueError('Plan arguments changed')
    if command_identity()!=p['command_identity']:raise ValueError('Configured provider command changed')
    if snapshot(roots)!=p['input_snapshot']:raise ValueError('Input set changed since planning')
    cfg=pinned(config)
    out=disjoint(output,plan_path,config,p['request']['path'],*roots,*[r['path'] for r in cfg['identity_files']])
    if out.exists() or not out.parent.is_dir():raise ValueError('Use a fresh execution output')
    out.mkdir()
    try:
        probe(config,out/'capabilities')
        value,_,error=runner.execute('monkey',argv+['--out',str(out/'provider-output')],out/'execution',
                                    timeout_seconds=request['timeout_seconds'],max_output_bytes=8*1024**2,max_inline_bytes=1024**2)
        pinned(config)
        if command_identity()!=p['command_identity'] or hash_file(config)!=p['lock']:raise ValueError('Provider identity changed during execution')
        if snapshot(roots)!=p['input_snapshot']:raise ValueError('Input changed during execution')
        if error or not value.get('capture_complete'):raise ValueError('Provider failed; inspect execution receipt')
        result=dict(schema_version=1,status='needs_action',operation=request['operation'],provider_version=cfg['version'],
                    executed=True,plan=hash_file(plan_path),provider_receipt=str(out/'execution/run.json'),
                    provider_output=str(out/'provider-output'),native_validation='not_run',business_validation='not_run',
                    limitations=['Exit 0/1 and completed do not prove initial-project handoff or gameplay.'])
        if request['operation']=='convert':
            from .audit import audit
            result['audit']=audit(out/'provider-output',cfg['version'])
        write_new(out/'result.json',result)
        return result
    except Exception as error:
        write_new(out/'failure.json',dict(status='failed',message=str(error),partial_output_preserved=True));raise


def validate_references(options, roots):
    """Freeze external roots named by the supported source manifest contracts."""
    def require(path):
        path=canonical_path(path)
        if not path.exists() or not any(path==r or path.is_relative_to(r) for r in roots):
            raise ValueError('Manifest references an input outside frozen roots: '+str(path))
    if 'input-set' in options:
        manifest=canonical_path(options['input-set']);data=read(manifest)
        for item in data.get('inputs',[]):require(manifest.parent/item['path'])
        if data.get('provenance'):require(manifest.parent/data['provenance']['sourceManifest'])
    for key in ('unity-dependency-manifest','unity-schema-manifest'):
        if key in options:
            manifest=canonical_path(options[key]);data=read(manifest)
            if data.get('schemaVersion')!=1 or not data.get('files'):raise ValueError('Expected frozen Unity pool')
            for item in data['files']:
                path=manifest.parent/item['path'];require(path);actual=hash_file(path)
                if actual['sha256']!=item['sha256'] or actual['bytes']!=item['bytes']:raise ValueError('Unity pool identity changed')
