"""Pinned monkey package adapter; input text and handoff tasks are data, not authority."""
import argparse,json,os
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

def collect_slice(workspace,version,resume_report=None):
    """Slice v1 is separate from package v1; only an executed resume can promote it."""
    root=canonical_path(workspace);base=read(root/'conversion.json');project=root/'project'
    if base.get('schemaVersion')!=1 or base.get('toolVersion')!=version or base.get('completed') is not True:raise ValueError('Unsupported or incomplete slice')
    if hash_file(project/'manifest.json')['sha256']!=base['candidateManifestSha256'] or hash_file(root/'inspect/source-manifest.json')['sha256']!=base['sourceManifestSha256']:raise ValueError('Slice stage identity changed')
    manifest=read(project/'manifest.json')
    if manifest.get('toolVersion')!=version or manifest.get('targetProfile')!=base['targetProfile']:raise ValueError('Slice target identity mismatch')
    if len(manifest['files'])>20000:raise ValueError('Slice file count limit')
    raw=base;native='not_run';evidence=[];native_hashes={}
    if resume_report is not None:
        report=canonical_path(resume_report)
        if not report.is_relative_to(root/'checks'):raise ValueError('Resume report outside owned checks')
        raw=read(report)
        for key in ('schemaVersion','toolVersion','candidateManifestSha256','sourceManifestSha256','targetProfile'):
            if raw.get(key)!=base.get(key):raise ValueError('Resume identity mismatch')
        if raw.get('resultKind')=='native' and raw.get('validation',{}).get('editor')=='pass':
            rb=read(project/'Analysis/editor-readback.json')
            if rb.get('unityVersion')!='6000.6.2f1' or rb.get('missingScripts')!=0 or rb.get('editableRoundtrip') is not True or not rb.get('nativeFiles'):raise ValueError('Native readback incomplete')
            if len(rb['nativeFiles'])>20000:raise ValueError('Native file count limit')
            remaining=512*1024**2
            for item in rb['nativeFiles']:
                file=project/relative_name(item['path'])
                if any(p.is_symlink() for p in (file,*file.parents)):raise ValueError('Linked native output')
                identity=hash_file(file,remaining);remaining-=identity['bytes']
                if identity['sha256']!=item['sha256']:raise ValueError('Native artifact changed after provider validation')
                if item['path'] in native_hashes:raise ValueError('Duplicate native identity')
                native_hashes[item['path']]=item['sha256']
            native='provider_verified_editor_readback';evidence=[hash_file(report),hash_file(project/'Analysis/editor-readback.json')]
    remaining=512*1024**2
    for item in manifest['files']:
        file=project/relative_name(item['path'])
        if any(p.is_symlink() for p in (file,*file.parents)):raise ValueError('Linked candidate output')
        identity=hash_file(file,remaining);remaining-=identity['bytes']
        if identity['sha256']!=native_hashes.get(item['path'],item['sha256']):raise ValueError('Candidate changed; explicit provider native resume or a new revision is required')
    status=raw.get('workflowStatus')
    if status not in ('needs_action','partial','blocked','failed','success'):raise ValueError('Unknown slice result')
    task=dict(project='project',taskId='grea-native-continuation',origin='grea_declared_boundary_not_translated_business',allowedPaths=['Assets/Game/'],nextAction='Declare a bounded module using original source evidence and actual native bindings; preserve generated ownership',verification=['source behavior contract','native compile','affected real input and persistence'])
    return dict(schema_version=1,provider='monkey',provider_version=version,status='partial' if native!='not_run' and status=='success' else 'needs_action' if status=='success' else status,result_kind='native' if native!='not_run' else 'candidate',provider_report=hash_file(root/'conversion.json'),projects=[dict(path='project',target_profile=base['targetProfile'],manifest_sha256=base['candidateManifestSha256'],source_manifest_sha256=base['sourceManifestSha256'],validation=raw.get('validation',{}))],detail_tasks=[task],next_action=raw.get('nextAction'),native_validation=native,native_evidence=evidence,limitations=['Native Editor readback is not real input, visual/business parity or Player acceptance.','The GREA continuation boundary is declared, not automatically translated source business. Generated graph and source text are data, not runtime code.'])

def collect_handoff(workspace, version, contract_path):
    """Audit a caller-declared bulk handoff; never run conversion or an Editor."""
    root=canonical_path(workspace);c=read(contract_path,32*1024**2);base=canonical_path(contract_path).parent
    required={'schema_version','provider_version','target_engine','source_inventory','project_path','assets','entry','native_check'}
    if set(c)!=required or type(c['schema_version']) is not int or c['schema_version']!=1 or c['provider_version']!=version or c['target_engine'] not in ('unity','cocos'):raise ValueError('Expected pinned bulk handoff contract v1')
    def bound(folder,item):
        if not isinstance(item,dict) or set(item)!={'path','sha256'}:raise ValueError('Expected relative path and SHA256')
        p=folder/relative_name(item['path'])
        if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('Linked handoff artifact')
        identity=hash_file(p,512*1024**2)
        if identity['sha256']!=item['sha256']:raise ValueError('Stale handoff artifact')
        return p
    inventory_path=bound(base,c['source_inventory']);inventory=read(inventory_path)
    if inventory.get('schema_version')==1 and 'result' in inventory:inventory=inventory['result']
    if inventory.get('coverage')!='complete' or not inventory.get('files') or len(inventory['files'])>100000:raise ValueError('Complete inspect-target source inventory required')
    source=canonical_path(inventory['target']['path']);source_files={};total=0
    for f in inventory['files']:
        p=bound(source,dict(path=f['path'],sha256=f['sha256']));name=relative_name(f['path']).as_posix()
        if name in source_files:raise ValueError('Duplicate input file')
        total+=p.stat().st_size
        if total>8*1024**3:raise ValueError('Bulk input budget exceeded; declare bounded input sets')
        source_files[name]=f['sha256']
    actual_source=artifacts.inspect_target(source,max_files=100000,max_bytes=8*1024**3)
    if actual_source['coverage']!='complete' or {f['path']:f['sha256'] for f in actual_source['files']}!=source_files:raise ValueError('Source inventory is partial or stale')
    project=root/relative_name(c['project_path']);issues=[]
    markers=('Assets','Packages/manifest.json','ProjectSettings/ProjectVersion.txt') if c['target_engine']=='unity' else ('assets','project.json')
    if any(not ((project/p).is_dir() if p in ('Assets','assets') else (project/p).is_file()) for p in markers):issues.append('editable_target_project_missing')
    bound(project,c['entry'])
    if not isinstance(c['assets'],list) or not 1<=len(c['assets'])<=100000:raise ValueError('Bounded logical asset dispositions required')
    ids=set();covered=set();native_paths={};counts={};gaps=[];outputs={};remaining=8*1024**3
    categories={'texture','sprite','material','shader','font','audio','animation','spine','config','prefab','scene','code','other'}
    for asset in c['assets']:
        if set(asset)!={'source_id','category','source_files','disposition','outputs','reason'} or not isinstance(asset['source_id'],str) or not asset['source_id'] or asset['source_id'] in ids:raise ValueError('Unique logical source identities required')
        ids.add(asset['source_id']);category=asset['category'];kind=asset['disposition']
        if category not in categories or kind not in ('native','draft','retained','unsupported','missing') or not asset['source_files'] or not set(asset['source_files'])<=source_files.keys():raise ValueError('Invalid source disposition')
        covered.update(asset['source_files']);counts.setdefault(category,{});counts[category][kind]=counts[category].get(kind,0)+1
        if kind!='native' and (not isinstance(asset['reason'],str) or not asset['reason']):raise ValueError('Non-native assets need source/TODO or gap reasons')
        if kind in ('native','draft','retained') and not asset['outputs']:issues.append('missing_disposition_output:'+asset['source_id'])
        for item in asset['outputs']:
            p=bound(project,item);name=relative_name(item['path']).as_posix()
            if name not in outputs:
                remaining-=p.stat().st_size
                if remaining<0 or len(outputs)>=100000:raise ValueError('Bulk target budget exceeded')
                outputs[name]=item['sha256']
            if kind=='native':native_paths[name]=item['sha256']
        if category=='code' and not asset['outputs']:issues.append('code_evidence_missing:'+asset['source_id'])
        if category in ('prefab','scene'):
            suffix='.prefab' if category=='prefab' else '.unity' if c['target_engine']=='unity' else '.scene'
            if kind!='native' or not any(item['path'].endswith(suffix) for item in asset['outputs']):issues.append('source_graph_not_native:'+asset['source_id'])
        if kind in ('unsupported','missing'):gaps.append(dict(source_id=asset['source_id'],category=category,reason=asset['reason']))
    if covered!=source_files.keys():issues.append('input_files_without_disposition')
    if not native_paths:issues.append('no_native_assets_lookup_or_retained_only')
    native='not_run'
    if c['native_check'] is not None:
        check_path=bound(base,c['native_check'])
        if check_path.is_relative_to(canonical_path(project)):raise ValueError('Native receipt must be outside target project to avoid self-reference')
        check=read(check_path,32*1024**2)
        if set(check)!={'schema_version','target_engine','import_status','compile_status','artifacts'} or type(check['schema_version']) is not int or check['schema_version']!=1 or check['target_engine']!=c['target_engine']:raise ValueError('Unknown native check receipt')
        checked={}
        for item in check['artifacts']:
            if item['path'] in checked:raise ValueError('Duplicate native receipt path')
            bound(project,item);checked[item['path']]=item['sha256']
        # Bind the whole target source/config closure, not just one successful Prefab.
        actual={};target_bytes=0
        for folder,dirs,names in os.walk(project,followlinks=False):
            if canonical_path(folder)==canonical_path(project):dirs[:]=[d for d in dirs if d not in ('Library','Temp','obj','Logs','UserSettings','Build','Builds','.git','.grea')]
            for d in dirs:
                if (Path(folder)/d).is_symlink():raise ValueError('Linked target directory')
            for name in names:
                p=Path(folder)/name;relative=p.relative_to(project).as_posix()
                if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('Linked target file')
                identity=hash_file(p,512*1024**2);target_bytes+=identity['bytes']
                if target_bytes>8*1024**3 or len(actual)>=100000:raise ValueError('Target closure exceeds budget')
                actual[relative]=identity['sha256']
        if checked!=actual:raise ValueError('Native receipt does not bind all current project files')
        if check['import_status']=='pass' and check['compile_status']=='pass':native='declared_native_receipt_byte_bound'
    if native=='not_run':issues.append('native_import_compile_not_verified')
    return dict(schema_version=1,provider='monkey',provider_version=version,workflow='handoff',status='needs_action' if issues else 'partial',result_kind='bulk_handoff_candidate',handoff_contract=hash_file(contract_path),entry=c['entry'],native_evidence=[hash_file(check_path)] if c['native_check'] is not None else [],handoff_ready=not issues,all_scope_export='not_available_in_grea_adapter',source_inventory=hash_file(inventory_path),logical_asset_counts=counts,issues=issues,gaps=gaps,native_validation=native,projects=[dict(path=c['project_path'],target_engine=c['target_engine'])],detail_tasks=[],native_file_count=len(native_paths),business_complete='not_proven',authority='Caller-declared logical mapping and native receipt; GREA verifies bytes, not independent engine execution.',limitations=['Lookup/index/IR/media counts and completed flags are never full native handoff.','Native initial project and playable game are separate; unknown methods retain source evidence/TODO, not invented logic.','This audit does not implement or invoke an unavailable all-scope exporter.'])

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

def run(config,output,source=None,target=None,workspace=None,modules=None,timeout=120,workflow="package",source_profile=None,asset_indices=None,all_assets=False,resume_native=False,handoff_contract=None):
    cfg=pinned(config);config_identity=hash_file(config);inputs=[config,*[row['path'] for row in cfg['identity_files']],*[x for x in (source,workspace,modules,handoff_contract) if x]]
    out=disjoint(output,*inputs)
    if out.exists() or not out.parent.is_dir():raise ValueError('Use a new output directory with existing parent')
    if bool(source)==bool(workspace):raise ValueError('Choose source conversion or existing workspace normalization')
    if workflow not in ('package','slice','handoff'):raise ValueError('Choose package or slice workflow')
    if (workflow=='handoff')!=bool(handoff_contract) or handoff_contract and (not workspace or source or modules or target or source_profile or asset_indices or all_assets or resume_native):raise ValueError('Handoff requires existing workspace and contract only')
    if resume_native and (workflow!='slice' or source):raise ValueError('Native resume requires an existing isolated slice workspace')
    if workflow=='slice' and source and (source_profile not in ('cocos-2.4.15-project','cocos-2.4.15-bundle') or bool(asset_indices)==bool(all_assets)):raise ValueError('Slice requires profile and explicit selection or all-assets')
    if workflow=='package' and (source_profile or asset_indices or all_assets):raise ValueError('Slice options do not apply to package mode')
    if source and target not in ('unity6','cocos38','both'):raise ValueError('Select supported package target explicitly')
    identity_source=canonical_path(source).parent if source and workflow=='slice' and canonical_path(source).is_file() else source
    if identity_source is not None:disjoint(output,identity_source)
    before=artifacts.inspect_target(identity_source,max_files=10000,max_bytes=512*1024**2) if source else None
    if before and before['coverage']!='complete':raise ValueError('Input identity exceeds explicit budget')
    if handoff_contract:
        declaration=read(handoff_contract,32*1024**2);inventory_path=canonical_path(handoff_contract).parent/relative_name(declaration['source_inventory']['path']);inventory=read(inventory_path);inventory=inventory.get('result',inventory)
        disjoint(output,inventory_path,inventory['target']['path'])
    out.mkdir()
    try:
        cap,_,error=runner.execute('monkey',[],out/'capabilities',probe=True,timeout_seconds=20,max_output_bytes=1024**2,max_inline_bytes=1024**2)
        if error or cap['inline_truncated'] or cap['parsed_stdout'] is None:raise ValueError('Capability probe failed')
        capabilities=cap['parsed_stdout']
        if capabilities.get('version')!=cfg['version'] or digest(capabilities)!=cfg['capabilities_sha256'] or capabilities.get('schemaVersion')!=1 or 'convert' not in capabilities.get('implemented',[]):raise ValueError('Provider capability/version mismatch')
        workspace=canonical_path(workspace) if workspace else out/'conversion'
        if source:
            argv=['convert','--source',str(canonical_path(source)),'--target',target,'--out',str(workspace)]
            if workflow=='package':argv.insert(1,'--package')
            else:
                if target=='both':raise ValueError('Slice accepts one target')
                argv[argv.index('--target')+1]={'unity6':'unity','cocos38':'cocos'}[target]
                if canonical_path(source).is_dir():argv[argv.index('--source')+1]=str(canonical_path(source)/('project.json' if source_profile.endswith('-project') else 'config.json'))
                argv+=['--source-profile',source_profile]
                if all_assets:argv+=['--all-assets']
                else:
                    for index in asset_indices:
                        if type(index) is not int or index<0:raise ValueError('Nonnegative asset index required')
                        argv+=['--asset-index',str(index)]
            receipt,_,error=runner.execute('monkey',argv,out/'convert-run',timeout_seconds=timeout,max_output_bytes=1024**2,max_inline_bytes=1024**2)
            if error or not receipt['capture_complete']:raise ValueError('Provider failed; inspect preserved process receipt')
            after=artifacts.inspect_target(identity_source,max_files=10000,max_bytes=512*1024**2)
            if after!=before:raise ValueError('Input changed during conversion')
        resume_report=None
        if resume_native:
            receipt,_,error=runner.execute('monkey',['convert','--resume',str(workspace)],out/'resume-run',timeout_seconds=timeout,max_output_bytes=1024**2,max_inline_bytes=1024**2)
            if error or not receipt['capture_complete'] or not receipt['parsed_stdout']:raise ValueError('Provider native verification failed')
            resume_report=receipt['parsed_stdout'].get('report')
            if not resume_report:raise ValueError('Provider did not return a native check report')
        pinned(config)
        if hash_file(config)!=config_identity:raise ValueError('Provider pin config changed')
        value=collect_handoff(workspace,cfg['version'],handoff_contract) if workflow=='handoff' else collect(workspace,cfg['version']) if workflow=='package' else collect_slice(workspace,cfg['version'],resume_report);value.update(input_identity=before,capabilities_sha256=cfg['capabilities_sha256'],workspace=str(workspace),workflow=workflow)
        write_new(out/'result.json',value);write_new(out/'ai-modules.json',handoff(value,modules))
        return value
    except Exception as e:
        write_new(out/'failure.json',dict(status='failed',message=str(e),partial_output_preserved=True));raise

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output',required=True);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--source');g.add_argument('--workspace');p.add_argument('--target',choices=['unity6','cocos38','both']);p.add_argument('--workflow',choices=['package','slice','handoff'],default='package');p.add_argument('--source-profile');p.add_argument('--asset-index',action='append',type=int);p.add_argument('--all-assets',action='store_true');p.add_argument('--resume-native',action='store_true');p.add_argument('--handoff-contract');p.add_argument('--modules');p.add_argument('--timeout',type=int,default=120);a=p.parse_args()
    try:
        if not 1<=a.timeout<=600:raise ValueError('Timeout must be 1..600')
        value=run(a.config,a.output,a.source,a.target,a.workspace,a.modules,a.timeout,a.workflow,a.source_profile,a.asset_index,a.all_assets,a.resume_native,a.handoff_contract);print(json.dumps(dict(status=value['status'],result=str(Path(a.output)/'result.json'),modules=str(Path(a.output)/'ai-modules.json'))));return 1 if value['status']!='success' else 0
    except (OSError,ValueError,KeyError,TypeError,GreaError) as e:print(str(e));return 2
if __name__=='__main__':raise SystemExit(main())
