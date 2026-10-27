"""Compatibility contract extracted without changing existing tool IDs."""
import json,os
from grea.host.paths import Path
from grea.common import digest,hash_file,write_new,GreaError
from grea.safe_paths import canonical_path,disjoint,relative_name
from grea import runner,artifacts
from .identity import read


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
    return dict(schema_version=1,provider='monkey',provider_version=version,workflow='handoff',status='needs_action' if issues else 'partial',result_kind='bulk_handoff_candidate',handoff_contract=hash_file(contract_path),entry=c['entry'],native_evidence=[hash_file(check_path)] if c['native_check'] is not None else [],handoff_ready=not issues,all_scope_export='not_executed_by_handoff_audit',source_inventory=hash_file(inventory_path),logical_asset_counts=counts,issues=issues,gaps=gaps,native_validation=native,projects=[dict(path=c['project_path'],target_engine=c['target_engine'])],detail_tasks=[],native_file_count=len(native_paths),business_complete='not_proven',authority='Caller-declared logical mapping and native receipt; GREA verifies bytes, not independent engine execution.',limitations=['Lookup/index/IR/media counts and completed flags are never full native handoff.','Native initial project and playable game are separate; unknown methods retain source evidence/TODO, not invented logic.','This audit does not invoke the separate monkey_pipeline exporter.'])

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
