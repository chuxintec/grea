"""Finite dev3 generation steps with explicit, bounded frozen input roots."""
import re
from grea import runner
from grea.common import hash_file, write_new
from grea.safe_paths import canonical_path, disjoint, relative_name, unique_paths
from .identity import read, pinned
from .pipeline import probe, snapshot, DEV3_VERSION, DEV4_VERSION

SPECS = {
    'audit-native-code-dependencies': {'candidate':'path','expected-manifest':'hash','producer-candidate':'path','expected-producer-manifest':'hash'},
    'upgrade-native-runtime': {'candidate':'path','expected-manifest':'hash'},
    'complete-native-font': {'request':'path','expected-request':'hash'},
    'stage-native-font': {'candidate':'path','expected-manifest':'hash','completion':'path','expected-completion':'hash'},
    'finish-native-font': {'project':'path','expected-stage-manifest':'hash','readback':'path','expected-readback':'hash'},
}


def validate(request):
    if set(request)!={'schema_version','operation','options','input_roots','timeout_seconds'} or type(request['schema_version']) is not int or request['schema_version']!=1:
        raise ValueError('Expected native step request v1')
    spec=SPECS.get(request['operation']);options=request['options']
    if not spec or not isinstance(options,dict) or set(options)!=set(spec):raise ValueError('Unknown or missing native step options')
    if type(request['timeout_seconds']) is not int or not 1<=request['timeout_seconds']<=1800:raise ValueError('Invalid timeout')
    raw=request['input_roots']
    if not isinstance(raw,list) or not 1<=len(raw)<=64:raise ValueError('Explicit input roots required')
    roots=[canonical_path(x) for x in raw]
    for i,p in enumerate(roots):
        if not p.exists():raise ValueError('Input root missing')
        disjoint(p,*roots[:i])
    argv=[request['operation']]
    for k,kind in spec.items():
        value=options[k]
        if kind=='path':
            value=canonical_path(value)
            if not value.exists() or not any(value==r or value.is_relative_to(r) for r in roots):raise ValueError('Option outside frozen inputs: '+k)
        elif not isinstance(value,str) or not re.fullmatch('[a-f0-9]{64}',value):raise ValueError('Expected SHA256: '+k)
        argv+=['--'+k,str(value)]
    return argv,roots


def audit_dependency_result(report, options, identity_root):
    if (report.get('schema')!='monkey-native-code-dependency-supplement/1' or report.get('targetManifestSha256')!=options['expected-manifest'] or report.get('producerCandidateManifestSha256')!=options['expected-producer-manifest']):raise ValueError('Dependency supplement parent mismatch')
    target=canonical_path(options['candidate']);manifest=read(target/'manifest.json',128*1024**2)
    if report.get('originalDiagnostics')!=manifest.get('diagnostics',[]):raise ValueError('Original diagnostics changed')
    rows=report['scripts']+report['uncovered']+report['packageFiles']
    rows += [item for row in report['scripts'] for item in row['requires']]
    for row in rows:
        path=canonical_path(target/relative_name(row['path']))
        if not path.is_relative_to(target) or hash_file(path,128*1024**2)['sha256']!=row['sha256']:raise ValueError('Supplement target identity mismatch')
    for row in report['producerImplementation']:
        path=canonical_path(identity_root/relative_name(row['path']))
        if not path.is_relative_to(identity_root) or hash_file(path,128*1024**2)['sha256']!=row['sha256']:raise ValueError('Supplement implementation mismatch')


def run(config, request_path, output):
    request_identity=hash_file(request_path);q=read(request_path);argv,roots=validate(q);cfg=pinned(config)
    if cfg['schema_version']!=2 or cfg['version'] not in (DEV3_VERSION,DEV4_VERSION):raise ValueError('Exact dev3/dev4 launcher lock required')
    if q['operation']=='audit-native-code-dependencies' and cfg['version']!=DEV4_VERSION:raise ValueError('Code dependency audit requires fixed dev4')
    out=disjoint(output,config,request_path,*roots,*[x['path'] for x in cfg['identity_files']])
    if out.exists() or not out.parent.is_dir():raise ValueError('Fresh output required')
    before=snapshot(roots)
    # This command can inspect platform fonts through the fixed provider. The provider
    # binds those environment identities; callers must declare all payload roots.
    if q['operation']=='complete-native-font':
        corpus=read(q['options']['request'])
        paths=[v for k,v in corpus.items() if k.endswith('_path')]
        paths += [x['path'] for x in corpus.get('watch_files',{}).values()]
        for value in paths:
            p=canonical_path(value)
            if not any(p==r or p.is_relative_to(r) for r in roots):raise ValueError('Font request refers outside frozen input roots')
    options=q['options']
    pins=[]
    if 'candidate' in options:pins.append((canonical_path(options['candidate'])/'manifest.json',options['expected-manifest']))
    if 'producer-candidate' in options:pins.append((canonical_path(options['producer-candidate'])/'manifest.json',options['expected-producer-manifest']))
    if 'project' in options:pins.append((canonical_path(options['project'])/'manifest.json',options['expected-stage-manifest']))
    if 'completion' in options:pins.append((canonical_path(options['completion'])/'font-completion.json',options['expected-completion']))
    for name in ('request','readback'):
        if name in options:pins.append((canonical_path(options[name]),options['expected-'+name]))
    for path,expected in pins:
        if hash_file(path,128*1024**2)['sha256']!=expected:raise ValueError('Expected input hash differs: '+str(path))
    out.mkdir();executed=False
    try:
        probe(config,out/'capabilities')
        lock_identity=hash_file(config)
        actual,_,error=runner.execute('monkey',argv+['--out',str(out/'provider-output')],out/'invocation',timeout_seconds=q['timeout_seconds'],max_output_bytes=8*1024**2,max_inline_bytes=1024**2)
        executed=True;pinned(config)
        if hash_file(config)!=lock_identity or hash_file(request_path)!=request_identity or snapshot(roots)!=before:raise ValueError('Frozen input/provider identity changed')
        if error or actual.get('exit_code')!=0 or not actual.get('capture_complete'):raise ValueError('Native step failed; inspect preserved provider receipt')
        payload=actual.get('parsed_stdout')
        if not isinstance(payload,dict):raise ValueError('Expected structured provider result')
        inventory=snapshot([out/'provider-output'])
        if q['operation']=='audit-native-code-dependencies':audit_dependency_result(read(out/'provider-output/code-dependency-supplement.json',128*1024**2),q['options'],canonical_path(cfg['identity_root']))
        for manifest in (out/'provider-output').rglob('manifest.json'):
            data=read(manifest,128*1024**2);files=data.get('files',[])
            if not isinstance(files,list):raise ValueError('Invalid output manifest file list')
            if files:
                unique_paths(row['path'] for row in files)
                for row in files:
                    path=canonical_path(manifest.parent/relative_name(row['path']))
                    if not path.is_relative_to(out/'provider-output'):raise ValueError('Output file escapes candidate')
                    value=hash_file(path,32*1024**3)
                    if value['sha256']!=row['sha256'] or value['bytes']!=row['bytes']:raise ValueError('Output manifest file mismatch')
        # Stage output contains launch instructions; never execute them here.
        result=dict(status='needs_action',executed=True,provider_version=cfg['version'],operation=q['operation'],provider_result=payload,output_inventory=inventory,input_snapshot=before,request=request_identity,native_validation='not_run_by_grea',business_validation='not_run',editor_started=False,handoff_ready=False)
        write_new(out/'result.json',result);return result
    except Exception as error:
        write_new(out/'failure.json',dict(status='failed',message=str(error),executed=executed,partial_output_preserved=True));raise
