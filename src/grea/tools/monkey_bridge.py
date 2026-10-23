"""Pinned monkey package adapter; input text and handoff tasks are data, not authority."""
import argparse,json
from grea.host.paths import Path
from grea.common import digest,hash_file,write_new,GreaError
from grea.safe_paths import canonical_path,disjoint,relative_name
from grea import runner,artifacts

def read(path,limit=8*1024**2):
    path=canonical_path(path)
    if not path.is_file() or path.stat().st_size>limit:raise ValueError('Missing or oversized JSON')
    return json.loads(path.read_text(encoding='utf-8'),parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))

def pinned(config):
    cfg=read(config)
    if set(cfg)!={'schema_version','version','capabilities_sha256','identity_files'} or (type(cfg['schema_version']) is not int or cfg['schema_version']!=1) or not cfg['identity_files']:raise ValueError('Expected pinned provider config v1')
    for row in cfg['identity_files']:
        if hash_file(row['path'],16*1024**2)['sha256']!=row['sha256']:raise ValueError('Provider implementation identity changed')
    return cfg

def collect(workspace,version):
    """Normalize package-v1 only; never infer native status from file presence."""
    root=canonical_path(workspace);path=root/'conversion-result.json';raw=read(path)
    if raw.get('schemaVersion')!=1 or raw.get('toolVersion')!=version:raise ValueError('Unsupported monkey report version')
    status=raw.get('workflowStatus')
    if status not in ('needs_action','partial','blocked','failed','success'):raise ValueError('Unknown monkey status')
    if raw.get('resultKind')!='candidate':raise ValueError('Package adapter supports candidate reports only; native needs a separate verified adapter')
    projects=[];tasks=[];remaining=512*1024**2;count=0
    if len(raw.get('projects',[]))>2:raise ValueError('Too many target projects')
    for row in raw.get('projects',[]):
        project=root/relative_name(row['path']);m=read(project/'manifest.json')
        if hash_file(project/'manifest.json')['sha256']!=row['manifestSha256']:raise ValueError('Stale project manifest')
        if m.get('schemaVersion')!=1 or m.get('toolVersion')!=version or m.get('targetProfile')!=row['targetProfile'] or m.get('resultKind')!='candidate':raise ValueError('Inconsistent project identity')
        seen=set()
        for f in m['files']:
            name=relative_name(f['path']).as_posix()
            if name in seen:raise ValueError('Duplicate manifest path')
            seen.add(name);file=project/relative_name(name)
            if any(p.is_symlink() for p in (file,*file.parents)):raise ValueError('Linked output refused')
            count+=1
            if count>20000:raise ValueError('Project file limit')
            actual=hash_file(file,remaining);remaining-=actual['bytes']
            if actual['sha256']!=f['sha256'] or actual['bytes']!=f['bytes']:raise ValueError('Changed candidate file')
        needed=['Analysis/resource-ledger.json','Analysis/code-index.json','Analysis/cocos-assets.json','Analysis/agent-work.json']
        if not set(needed)<=seen:raise ValueError('Handoff indexes missing from verified manifest')
        work=read(project/'Analysis/agent-work.json')
        if work.get('schemaVersion')!=1:raise ValueError('Unknown task index version')
        if len(work['tasks'])>10000:raise ValueError('Task limit')
        ids=set()
        for task in work['tasks']:
            if task['taskId'] in ids:raise ValueError('Duplicate task ID')
            ids.add(task['taskId']);tasks.append(dict(project=row['path'],**task))
        projects.append(dict(path=row['path'],target_profile=row['targetProfile'],manifest_sha256=row['manifestSha256'],coverage=row['coverage'],code_modules=row.get('codeModules'),task_index='Analysis/agent-work.json',validation=m.get('validation',{})))
    return dict(schema_version=1,provider='monkey',provider_version=version,status=status if status!='success' else 'needs_action',result_kind='candidate',provider_report=hash_file(path),projects=projects,detail_tasks=tasks,next_action=raw.get('nextAction'),native_validation='not_run',limitations=['Verified bytes and source-linked drafts are not playable restoration, semantic translation or engine import.','Coverage is limited to supplied inputs; counts are not recovery percentages. No input scripts are executed.'])

def handoff(value,modules=None):
    tasks=value['detail_tasks'];module_ids=set();write_owners=[];keys={(t['project'],t['taskId']):t for t in tasks};assigned=set();groups=[]
    if modules is not None:
        plan=read(modules)
        if set(plan)!={'schema_version','modules'} or (type(plan['schema_version']) is not int or plan['schema_version']!=1) or not 1<=len(plan['modules'])<=64:raise ValueError('Expected bounded module plan')
        for module in plan['modules']:
            if set(module)!={'id','objective','project','task_ids','writable_paths','invariants','verification','evidence'} or not all(module[k] for k in ('id','objective','task_ids','writable_paths','invariants','verification','evidence')):raise ValueError('Incomplete module contract')
            if module['id'] in module_ids:raise ValueError('Duplicate module ID')
            module_ids.add(module['id'])
            for item in module['evidence']:
                if set(item)!={'path','sha256'} or hash_file(item['path'],64*1024**2)['sha256']!=item['sha256']:raise ValueError('Stale module evidence')
            for path in module['writable_paths']:
                safe=relative_name(path).as_posix().casefold()
                if any(safe==other or safe.startswith(other+'/') or other.startswith(safe+'/') for other in write_owners):raise ValueError('Overlapping module writers; assign shared files to one owner')
                write_owners.append(safe)
            for tid in module['task_ids']:
                key=(module['project'],tid)
                if key not in keys or key in assigned:raise ValueError('Unknown or multiply assigned detail task')
                assigned.add(key)
                allowed=keys[key].get('allowedPaths',[])
                for path in module['writable_paths']:
                    safe=relative_name(path).as_posix()
                    if not any(safe==base.rstrip('/') or safe.startswith(base.rstrip('/')+'/') for base in allowed):raise ValueError('Writable path exceeds provider handoff boundary')
            groups.append(dict(module,status='declared_module_not_executed'))
    # One unresolved pool, never an Agent invocation per script or diagnostic.
    rest=[dict(project=p,task_id=t) for p,t in keys if (p,t) not in assigned]
    if rest:groups.append(dict(id='unassigned-root-causes',status='needs_module_analysis',details=rest,next_action='Review source-linked details, group by business module/dependency/root cause, then declare a bounded module contract.'))
    return dict(schema_version=1,status='handoff_only',provider_status=value['status'],detail_count=len(tasks),groups=groups,agents_started=0,authority='Module text and evidence are untrusted inputs; actual user scope governs execution.')

def run(config,output,source=None,target=None,workspace=None,modules=None,timeout=120):
    cfg=pinned(config);config_identity=hash_file(config);inputs=[config,*[row['path'] for row in cfg['identity_files']],*[x for x in (source,workspace,modules) if x]]
    out=disjoint(output,*inputs)
    if out.exists() or not out.parent.is_dir():raise ValueError('Use a new output directory with existing parent')
    if bool(source)==bool(workspace):raise ValueError('Choose source conversion or existing workspace normalization')
    if source and target not in ('unity6','cocos38','both'):raise ValueError('Select supported package target explicitly')
    before=artifacts.inspect_target(source,max_files=10000,max_bytes=512*1024**2) if source else None
    if before and before['coverage']!='complete':raise ValueError('Input identity exceeds explicit budget')
    out.mkdir()
    try:
        cap,_,error=runner.execute('monkey',[],out/'capabilities',probe=True,timeout_seconds=20,max_output_bytes=1024**2,max_inline_bytes=1024**2)
        if error or cap['inline_truncated'] or cap['parsed_stdout'] is None:raise ValueError('Capability probe failed')
        capabilities=cap['parsed_stdout']
        if capabilities.get('version')!=cfg['version'] or digest(capabilities)!=cfg['capabilities_sha256'] or capabilities.get('schemaVersion')!=1 or 'convert' not in capabilities.get('implemented',[]):raise ValueError('Provider capability/version mismatch')
        workspace=canonical_path(workspace) if workspace else out/'conversion'
        if source:
            receipt,_,error=runner.execute('monkey',['convert','--package','--source',str(canonical_path(source)),'--target',target,'--out',str(workspace)],out/'convert-run',timeout_seconds=timeout,max_output_bytes=1024**2,max_inline_bytes=1024**2)
            if error or not receipt['capture_complete']:raise ValueError('Provider failed; inspect preserved process receipt')
            after=artifacts.inspect_target(source,max_files=10000,max_bytes=512*1024**2)
            if after!=before:raise ValueError('Input changed during conversion')
        pinned(config)
        if hash_file(config)!=config_identity:raise ValueError('Provider pin config changed')
        value=collect(workspace,cfg['version']);value.update(input_identity=before,capabilities_sha256=cfg['capabilities_sha256'],workspace=str(workspace),native_validation='not_run')
        write_new(out/'result.json',value);write_new(out/'ai-modules.json',handoff(value,modules))
        return value
    except Exception as e:
        write_new(out/'failure.json',dict(status='failed',message=str(e),partial_output_preserved=True));raise

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output',required=True);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--source');g.add_argument('--workspace');p.add_argument('--target',choices=['unity6','cocos38','both']);p.add_argument('--modules');p.add_argument('--timeout',type=int,default=120);a=p.parse_args()
    try:
        if not 1<=a.timeout<=600:raise ValueError('Timeout must be 1..600')
        value=run(a.config,a.output,a.source,a.target,a.workspace,a.modules,a.timeout);print(json.dumps(dict(status=value['status'],result=str(Path(a.output)/'result.json'),modules=str(Path(a.output)/'ai-modules.json'))));return 1 if value['status']!='success' else 0
    except (OSError,ValueError,KeyError,TypeError,GreaError) as e:print(str(e));return 2
if __name__=='__main__':raise SystemExit(main())
