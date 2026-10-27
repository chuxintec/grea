"""Compatibility contract extracted without changing existing tool IDs."""
import json,os
from grea.host.paths import Path
from grea.common import digest,hash_file,write_new,GreaError
from grea.safe_paths import canonical_path,disjoint,relative_name
from grea import runner,artifacts
from .identity import read


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
