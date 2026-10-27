"""Finite named forwarding to explicitly pinned beaver implementations."""
import json
import os
import platform
from contextlib import contextmanager
import re
from pathlib import Path
from grea.common import GreaError, hash_file, write_new
from grea.safe_paths import canonical_path, disjoint
from . import beaver

# Only the verified CLI surface, not arbitrary shell/argv forwarding.
OPERATIONS = {
    'project.inspect': dict(command=['project','inspect'], required={'project'}, paths={'project'}, flags={'assets'}),
    'adoption.plan': dict(command=['adopt','plan'], required={'candidate','target'}, paths={'candidate','baseline','target'}, text={'lineage'}, output='out'),
    'adoption.apply': dict(command=['adopt','apply'], required={'plan','expected-plan','editor-path','timeout'}, paths={'plan','editor-path'}, hashes={'expected-plan'}, integers={'timeout':(1,1700)}, output='out'),
    'adoption.rollback': dict(command=['adopt','rollback'], required={'transaction','editor-path','timeout'}, paths={'transaction','editor-path'}, integers={'timeout':(1,1700)}),
    'unity.plan': dict(command=['unity','plan'], required={'project','spec'}, paths={'project','spec'}, output='out'),
    'unity.apply': dict(command=['unity','apply'], required={'plan','expected-plan','editor-path','timeout'}, paths={'plan','editor-path'}, hashes={'expected-plan'}, integers={'timeout':(1,1700)}, output='out'),
    'player.run': dict(command=['player','run'], required={'manifest','expected-manifest','duration'}, paths={'manifest'}, hashes={'expected-manifest'}, integers={'duration':(1,1700)}, output='out'),
    'payload.verify': dict(command=['payload','verify'], required={'root','manifest'}, paths={'root','manifest'}, text={'scope'}, flags={'allow-unlisted'}),
    'payload.plan': dict(command=['payload','plan'], required={'root','manifest','target'}, paths={'root','manifest','target','overrides','override-root'}, output='out'),
    'payload.apply': dict(command=['payload','apply'], required={'plan','expected-plan'}, paths={'plan'}, hashes={'expected-plan'}, output='out'),
    'image.inspect': dict(command=['image','inspect'], required={'input'}, paths={'input'}),
    'image.compress': dict(command=['image','compress'], required={'input'}, paths={'input'}, hashes={'expected-source'}, flags={'apply'}, output='output'),
    'config.validate': dict(command=['config','validate'], required={'schema','input'}, paths={'schema','input'}),
    'config.generate': dict(command=['config','generate'], required={'schema'}, paths={'schema'}, output='out'),
    'code.inspect': dict(command=['code','inspect'], required={'project'}, paths={'project'}),
    'batch.plan': dict(command=['batch','plan'], required={'project','spec'}, paths={'project','spec'}, output='out', versions={'0.2.0'}),
    'batch.apply': dict(command=['batch','apply'], required={'plan','expected-plan','editor-path','timeout'}, paths={'plan','editor-path'}, hashes={'expected-plan'}, integers={'timeout':(1,1700)}, output='out', versions={'0.2.0'}),
    'batch.recover': dict(command=['batch','recover'], required={'transaction','editor-path','timeout'}, paths={'transaction','editor-path'}, integers={'timeout':(1,1700)}, output='out', versions={'0.2.0'}),
    'references': dict(command=['references'], required={'project'}, paths={'project','cache'}, output='out', versions={'0.2.0'}),
    'debug.start': dict(command=['debug','start'], required={'manifest','expected','duration'}, paths={'manifest'}, hashes={'expected'}, integers={'duration':(1,3600),'width':(64,8192),'height':(64,8192)}, budget_options=set(), output='out', versions={'0.2.0'}),
    'debug.inspect': dict(command=['debug','inspect'], required={'session'}, paths={'session'}, versions={'0.2.0'}),
    'debug.stop': dict(command=['debug','stop'], required={'session'}, paths={'session'}, versions={'0.2.0'}),
    'debug.tail': dict(command=['debug','tail'], required={'session'}, paths={'session'}, integers={'lines':(1,500)}, versions={'0.2.0'}),
    'debug.screenshot': dict(command=['debug','screenshot'], required={'session','input','expected'}, paths={'session','input'}, hashes={'expected'}, versions={'0.2.0'}),
    'debug.target': dict(command=['debug','target'], required={'transaction'}, paths={'transaction'}, versions={'0.2.0'}),
}
OPERATIONS['payload.verify']['flags'].add('unity-artifact')
OPERATIONS['payload.verify']['option_versions']={'unity-artifact':{'0.2.0'}}

# v0.3 retains the verified v0.2 CLI surface. Group declarations are mapped
# explicitly; do not expand arbitrary provider strings or forward unknown argv.
for _spec in OPERATIONS.values():
    if _spec.get('versions')=={'0.2.0'}:_spec['versions'].add(beaver.V03_VERSION)
OPERATIONS['payload.verify']['option_versions']['unity-artifact'].add(beaver.V03_VERSION)
for _name in ('plan','inspect','rebind'):
    _required={'project','spec'} if _name=='plan' else ({'project'} if _name=='inspect' else {'project','profile','expected-profile'})
    OPERATIONS['workspace.'+_name]=dict(command=['workspace',_name],required=_required,
        paths={'project','spec'}if _name=='plan'else({'project','profile'}if _name=='inspect'else{'project','profile','spec'}),
        hashes={'expected-profile'}if _name=='rebind'else set(),flags={'accept-authority-change'}if _name=='rebind'else set(),
        **({'output':'out'}if _name!='inspect'else{}),versions={beaver.V03_VERSION},capability='workspace.plan/apply/inspect/rebind')
OPERATIONS['workspace.apply']=dict(command=['workspace','apply'],required={'plan','expected-plan'},paths={'plan'},hashes={'expected-plan'},output='out',versions={beaver.V03_VERSION},capability='workspace.plan/apply/inspect/rebind')
for _name in ('plan','apply','recover'):
    _original=OPERATIONS['batch.'+_name]
    OPERATIONS['production.'+_name]=dict(_original,command=['production',_name],versions={beaver.V03_VERSION},capability='production.plan/apply/recover')
OPERATIONS.update({
    'config3.validate':dict(command=['config3','validate'],required={'schema','input'},paths={'schema','input','tables','project'},versions={beaver.V03_VERSION},capability='config3.validate/generate/compare'),
    'config3.generate':dict(command=['config3','generate'],required={'schema'},paths={'schema'},output='out',versions={beaver.V03_VERSION},capability='config3.validate/generate/compare'),
    'config3.compare':dict(command=['config3','compare'],required={'before-schema','after-schema'},paths={'before-schema','after-schema','before-input','after-input'},versions={beaver.V03_VERSION},capability='config3.validate/generate/compare'),
    'csharp.inspect':dict(command=['csharp','inspect'],required={'project'},paths={'project','toolchain'},output='out',versions={beaver.V03_VERSION},capability='csharp.inspect/rename/rename-sequence'),
    'csharp.rename':dict(command=['csharp','rename'],required={'project','spec'},paths={'project','spec','toolchain'},output='out',versions={beaver.V03_VERSION},capability='csharp.inspect/rename/rename-sequence'),
    'csharp.rename-sequence':dict(command=['csharp','rename-sequence'],required={'project','spec'},paths={'project','spec','toolchain'},output='out',versions={beaver.V03_VERSION},capability='csharp.inspect/rename/rename-sequence'),
    'csharp.module':dict(command=['csharp','module'],required={'spec'},paths={'spec'},output='out',versions={beaver.V03_VERSION},capability='csharp.module'),
    'resource.image-inspect':dict(command=['resource','image-inspect'],required={'input'},paths={'input'},versions={beaver.V03_VERSION},capability='resource.image-inspect/image-produce/validate-step'),
    'resource.image-produce':dict(command=['resource','image-produce'],required={'input','policy','expected-source'},paths={'input','policy'},hashes={'expected-source'},output='out',versions={beaver.V03_VERSION},capability='resource.image-inspect/image-produce/validate-step'),
    'resource.validate-step':dict(command=['resource','validate-step'],required={'project','spec'},paths={'project','spec'},versions={beaver.V03_VERSION},capability='resource.image-inspect/image-produce/validate-step'),
})
for _name in ('generate','module-generate','module-plan','protocol-diff','migration-plan','compose-plan','toolchain'):
    _required=({'before','after'}if _name=='protocol-diff'else({'project'}if _name=='migration-plan'else({'project','spec'}if _name=='module-plan'else(set()if _name=='toolchain'else{'spec'}))))
    _group=('server.compose-plan/migration-state/migration-apply/runtime-inspect'if _name=='compose-plan'else('server.toolchain/protocol-tools/check/build'if _name=='toolchain'else'server.generate/module-generate/module-plan/protocol-diff/migration-plan'))
    OPERATIONS['server.'+_name]=dict(command=['server',_name],required=_required,paths=_required,
        **({'output':'out'}if _name not in ('protocol-diff','toolchain')else{}),versions={beaver.V03_VERSION},capability=_group)

UNSUPPORTED_V03 = {
    'server.inspect':'CLI exists but fixed candidate does not declare this capability',
    'server.protocol-tools':'Private protocol-tool build is outside this finite consumer increment',
    'server.check':'Go test/build execution is outside this finite consumer increment',
    'server.build':'Go binary build execution is outside this finite consumer increment',
    'server.migration-state':'Live Docker/database access is outside this increment',
    'server.migration-apply':'Live database mutation is outside this increment',
    'server.runtime-inspect':'Live Docker access is outside this increment',
    'creator.apply':'Not supported by the provider', 'creator.build':'Not supported by the provider',
}
for _spec in OPERATIONS.values():
    if beaver.V03_VERSION in _spec.get('versions',set()):_spec['versions'].update(beaver.V03_CANDIDATES)
OPERATIONS['payload.verify']['option_versions']['unity-artifact'].update(beaver.V03_CANDIDATES)

# Fixed 0.5 increment only. Inspection executes an Editor; the other four only
# read caller inputs and write independent reports/plans. No new apply engine.
OPERATIONS.update({
    'ui.inspect':dict(command=['ui','inspect'],required={'project','spec','editor-path','timeout'},paths={'project','spec','editor-path'},integers={'timeout':(1,1700)},output='out',versions={beaver.V05_VERSION},capability='ui.inspect/analyze/repair-plan'),
    'ui.analyze':dict(command=['ui','analyze'],required={'snapshot','spec'},paths={'snapshot','spec'},output='out',versions={beaver.V05_VERSION},capability='ui.inspect/analyze/repair-plan'),
    'ui.repair-plan':dict(command=['ui','repair-plan'],required={'project','snapshot','spec'},paths={'project','snapshot','spec'},output='out',versions={beaver.V05_VERSION},capability='ui.inspect/analyze/repair-plan'),
    'wiring.plan':dict(command=['wiring','plan'],required={'project','snapshot','spec'},paths={'project','snapshot','spec'},output='out',versions={beaver.V05_VERSION},capability='wiring.plan'),
    'diagnostics.summarize':dict(command=['diagnostics','summarize'],required={'input'},path_lists={'input':(1,256)},integers={'limit':(1,10000)},output='out',versions={beaver.V05_VERSION},capability='diagnostics.summarize'),
})


def read_json(path, max_bytes=8*1024**2):
    path=canonical_path(path)
    if not path.is_file() or path.stat().st_size>max_bytes:raise ValueError('Missing or oversized request/plan JSON')
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('Duplicate JSON key')
            result[k]=v
        return result
    return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=pairs,
                      parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def validate(request):
    if not isinstance(request,dict) or set(request)!={'schema_version','operation','options','timeout_seconds'} or type(request['schema_version'])is not int or request['schema_version']!=1:
        raise ValueError('Expected beaver operation request v1')
    if not isinstance(request['operation'],str):raise ValueError('Expected a named operation string')
    spec=OPERATIONS.get(request['operation']);options=request['options']
    if spec is None or not isinstance(options,dict):raise ValueError('Unsupported named beaver operation')
    allowed=set().union(*(set(spec.get(k,()))for k in ('paths','path_lists','hashes','integers','text','flags')))
    if set(options)-allowed or not spec['required']<=options.keys():raise ValueError('Unknown or missing named options')
    timeout=request['timeout_seconds']
    if type(timeout)is not int or not 1<=timeout<=1800:raise ValueError('timeout_seconds must be 1..1800')
    values={}
    for name,value in options.items():
        if name in spec.get('path_lists',{}):
            lower,upper=spec['path_lists'][name]
            if not isinstance(value,list) or not lower<=len(value)<=upper:
                raise ValueError('Expected a bounded nonempty path array')
            if any(not isinstance(p,str) or not p or '\x00' in p or not Path(p).expanduser().is_absolute() for p in value):
                raise ValueError('Provider paths must be absolute strings')
            value=[str(canonical_path(p)) for p in value]
        elif name in spec.get('flags',()):
            if type(value)is not bool:raise ValueError('Expected boolean flag')
        elif name in spec.get('integers',{}):
            lower,upper=spec['integers'][name]
            if type(value)is not int or not lower<=value<=upper:raise ValueError('Invalid provider duration')
            if name in spec.get('budget_options',{'timeout','duration'}) and value+10>timeout:
                raise ValueError('Outer budget must exceed provider duration by at least 10 seconds')
        elif not isinstance(value,str) or not value or '\x00' in value:raise ValueError('Expected a nonempty option string')
        elif name in spec.get('paths',()):
            if not Path(value).expanduser().is_absolute():raise ValueError('Provider paths must be absolute')
            value=str(canonical_path(value))
        elif name in spec.get('hashes',()) and not re.fullmatch('[a-f0-9]{64}',value):raise ValueError('Expected a complete SHA256')
        elif name in spec.get('text',()) and len(value)>4096:raise ValueError('Option text too long')
        values[name]=value
    if request['operation']=='image.compress' and values.get('apply') and not values.get('expected-source'):
        raise ValueError('Image apply requires expected-source')
    if request['operation']=='debug.start' and (('width'in values)!=('height'in values)):
        raise ValueError('Debug width and height must be provided together')
    return spec,values


def validate_provider_version(request, version):
    spec,_=validate(request)
    if version not in spec.get('versions',beaver.SUPPORTED_VERSIONS):
        raise ValueError('Operation is not supported by pinned beaver '+str(version))
    for option,versions in spec.get('option_versions',{}).items():
        if option in request['options'] and version not in versions:
            raise ValueError('Option '+option+' is not supported by pinned beaver '+str(version))


def argv_for(request, output):
    spec,values=validate(request);argv=list(spec['command'])
    for name,value in sorted(values.items()):
        if name in spec.get('path_lists',{}):
            for path in value:argv+=['--'+name,path]
        elif name in spec.get('flags',()):
            if value:argv.append('--'+name)
        else:argv+=['--'+name,str(value)]
    if spec.get('output'):
        target=Path(output)/('provider-output.png' if spec['output']=='output' else 'provider-output')
        argv+=['--'+spec['output'],str(target)]
    return argv


def required_capability(request):
    operation=request['operation']
    if operation not in ('unity.apply','batch.apply','workspace.apply','production.apply'):
        return OPERATIONS.get(operation,{}).get('capability',operation)
    plan=read_json(request['options']['plan'],max_bytes=128*1024**2)
    if operation=='workspace.apply':
        if plan.get('contract')!='beaver-project-setup/1':raise ValueError('Expected beaver-project-setup/1 plan')
        return OPERATIONS[operation]['capability']
    if operation=='production.apply':
        if plan.get('contract')!='beaver-production/3' or plan.get('schemaVersion')!=3:
            raise ValueError('Expected beaver-production/3 plan')
        return OPERATIONS[operation]['capability']
    if operation=='batch.apply':
        if plan.get('contract')!='beaver-batch/2':raise ValueError('Expected beaver-batch/2 plan')
        return 'batch.apply'
    if plan.get('contract')!='beaver-unity/1':raise ValueError('Expected beaver-unity/1 plan')
    operation=plan.get('spec',{}).get('operation')
    if not isinstance(operation,str):raise ValueError('Unity plan has no declared operation')
    return 'unity.'+operation


@contextmanager
def bound_command(cfg, output):
    """Use a receipt-local command snapshot, never a mutable provider override file."""
    config=Path(output)/'provider-config.json'
    write_new(config,dict(schema_version=1,providers={'beaver':dict(command=cfg['command'],probe=cfg['command']+['capabilities'],systems=[platform.system()])}))
    previous=os.environ.get('GREA_PROVIDERS');os.environ['GREA_PROVIDERS']=str(config)
    try:yield
    finally:
        if previous is None:os.environ.pop('GREA_PROVIDERS',None)
        else:os.environ['GREA_PROVIDERS']=previous


def invoke(lock, request_file, output):
    from grea import runner
    from grea.integrations.monkey.local import readiness, state_root as monkey_state
    request_file=canonical_path(request_file)
    before=hash_file(request_file,8*1024**2)
    request=read_json(request_file);spec,values=validate(request)
    if hash_file(request_file,8*1024**2)!=before:raise ValueError('Request changed while reading')
    lock=canonical_path(lock);lock_before=hash_file(lock,8*1024**2)
    paths=[v for k,v in values.items()if k in spec.get('paths',())]
    paths += [p for k,v in values.items() if k in spec.get('path_lists',{}) for p in v]
    out=disjoint(output,lock,request_file,beaver.state_root(),monkey_state(),*paths)
    if out.exists() or not out.parent.is_dir():raise ValueError('Use a fresh invocation directory')
    out.mkdir()
    write_new(out/'request.json',request)
    result=dict(status='needs_action',operation=request['operation'],executed=False,
                request_identity=before,native='not_run',gameplay='not_run')
    try:
        providers={'monkey':readiness(out/'monkey-check'),'beaver':beaver.check(out/'beaver-check',lock=lock)}
        result['providers']=providers
        if not all(p.get('ready')is True for p in providers.values()):
            result['diagnostic']='Both pinned providers are required; no legacy fallback'
        else:
            if hash_file(lock,8*1024**2)!=lock_before:raise ValueError('Provider lock changed during readiness')
            cfg=read_json(lock)
            probe=read_json(out/'beaver-check/probe/run.json')['parsed_stdout']
            validate_provider_version(request,cfg['version'])
            if cfg['version']!=probe['producer']['version']:raise ValueError('Probe version differs from lock')
            needed=required_capability(request)
            declarations=probe['data']['capabilities']
            available=any(row.get('id')==needed and row.get('state')in ('implemented','requires_provider') for row in declarations if isinstance(row,dict))
            if not available:result['diagnostic']='Capability not declared by pinned beaver: '+needed
            else:
                if hash_file(request_file,8*1024**2)!=before:raise ValueError('Request changed before launch')
                if hash_file(lock,8*1024**2)!=lock_before:raise ValueError('Provider lock changed before launch')
                with bound_command(cfg,out):
                    invocation,_,error=runner.execute('beaver',argv_for(request,out),out/'invocation',
                        timeout_seconds=request['timeout_seconds'],max_output_bytes=4*1024**2,max_inline_bytes=4*1024**2)
                actual=invocation.get('parsed_stdout');result['executed']=True
                if isinstance(actual,dict):result['provider_result']=actual
                if beaver.package_identity(cfg['identity_root'])!=cfg['package_files'] or beaver.command_identity(cfg['command'])!=cfg['command_files']:
                    raise ValueError('Provider implementation changed during invocation')
                if not invocation.get('capture_complete') or not isinstance(actual,dict) or actual.get('contract')!='beaver-result/1' or actual.get('producer',{}).get('name')!='beaver' or actual.get('producer',{}).get('version')!=cfg['version']:
                    raise ValueError('Incomplete or unsupported beaver result')
                if cfg['version'] in beaver.V03_CANDIDATES:
                    from grea.beaver_contracts import validate_result
                    validate_result(actual)
                if actual['producer'].get('implementationSha256')!=probe['producer'].get('implementationSha256'):
                    raise ValueError('Producer identity differs from capability probe')
                status=actual.get('status');codes={'ok':0,'partial':1,'blocked':3,'failed':2,'not_run':3}
                result['provider_result']=actual
                if status not in codes or invocation.get('exit_code')!=codes[status]:raise ValueError('Provider status/exit contract mismatch')
                result.update(status=status,verification=actual.get('verification',{}),native=actual.get('verification',{}).get('native','not_run'),transport_error=error.as_dict()if error else None)
    except (OSError,ValueError,KeyError,TypeError,GreaError) as error:
        result.update(status='needs_action',diagnostic=str(error))
        if result['executed']:
            result.update(native='unverified',
                next_action='Inspect the preserved invocation and provider transaction: changes may already be applied. Do not replay automatically.')
    write_new(out/'result.json',result)
    return result
