"""Serial module implementation and isolated candidate assembly from one architecture.

This stage never treats generated code as compiled or runtime-verified. All model
invocations use the existing bounded worker through the module API.
"""
from __future__ import annotations

import fcntl
from pathlib import Path
import time

from . import code_architecture_modules as modules
from . import code_postprocess as worker
from .io import encoded, inside, read, safe, sha
from .output_limits import copy_verified
from .sources.compiled import fail

TERMINAL = frozenset({'generated_unreviewed','partial_unimplemented_seed','evidence_only'})


def task_root(root, item, request=None):
    """Resolve an immutable reused task without copying its private evidence."""
    request = request or modules._json(root/'request.json')
    reused = request.get('reusedModules', {}).get(item['id'])
    if reused is None:
        return inside(root,item['task'])
    if item['status'] not in TERMINAL or reused.get('manifestSha256') != item.get('manifestSha256'):
        fail('CODE_NATIVE_REUSE',item['id'],'Only a pinned terminal module can be reused')
    path=safe(reused['root'])
    if sha(read(path/modules.MANIFEST,worker.FILE_BYTES)) != reused['manifestSha256']:
        fail('CODE_NATIVE_REUSE',item['id'],'Reused module receipt changed')
    return path


def continue_run(previous_root, output, priority_modules, *, stop_after_module=None):
    """Version a stopped schedule; preserve old requests and reuse terminal outputs."""
    previous=safe(previous_root);root=safe(output)
    if root.exists() or root==previous or root.is_relative_to(previous) or previous.is_relative_to(root):
        fail('CODE_NATIVE_OUTPUT',str(root),'Continuation requires a fresh non-overlapping directory')
    with (previous/'pipeline.lock').open('a+b') as lock:
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:fail('CODE_NATIVE_BUSY',str(previous),'Wait for the previous supervisor to exit naturally')
        request_raw=read(previous/'request.json',128*1024*1024)
        state_raw=read(previous/'state.json',128*1024*1024)
        request=modules._json(previous/'request.json');state=modules._json(previous/'state.json')
        stage=_stage(previous,request)
        for source in (safe(stage['root']),safe(stage['request']['sourceRoot'])):
            if root==source or root.is_relative_to(source) or source.is_relative_to(root):
                fail('CODE_NATIVE_OUTPUT',str(root),'Continuation must not overlap architecture or frozen source')
        if state.get('status')=='running':fail('CODE_NATIVE_BUSY',str(previous),'Previous supervisor is not recorded as stopped')
        rows=state.get('modules',[]);ids=[row['id'] for row in rows]
        if ids!=request.get('moduleOrder') or set(ids)!={m['id'] for m in stage['plan']['modules']} or len(set(ids))!=len(ids):
            fail('CODE_NATIVE_REUSE',str(previous),'Previous module order/coverage differs from the architecture')
        if not isinstance(priority_modules,(list,tuple)) or not priority_modules:
            fail('CODE_NATIVE_PRIORITY',str(root),'An explicit priority list is required')
        priorities=list(priority_modules)
        if len(set(priorities))!=len(priorities) or any(mid not in ids for mid in priorities):
            fail('CODE_NATIVE_PRIORITY',str(root),'Priority modules must be unique existing architecture IDs')
        pending=[row['id'] for row in rows if row['status'] not in TERMINAL]
        if stop_after_module is not None and stop_after_module not in pending:
            fail('CODE_NATIVE_PRIORITY',str(root),'Stop-after must name an unfinished module')
        completed=[row for row in rows if row['status'] in TERMINAL];reused={}
        for row in completed:
            if row['status']=='evidence_only':continue
            path=task_root(previous,row,request);current=modules.status(path)
            if root==path or root.is_relative_to(path) or path.is_relative_to(root):
                fail('CODE_NATIVE_OUTPUT',str(root),'Continuation must not overlap reused module evidence')
            if current['status']!=row['status'] or current['manifestSha256']!=row.get('manifestSha256'):
                fail('CODE_NATIVE_REUSE',row['id'],'Terminal module bytes/state differ from the saved receipt')
            reused[row['id']]=dict(root=str(path),manifestSha256=current['manifestSha256'])
        order=[row['id'] for row in completed]+[mid for mid in priorities if mid in pending]+[mid for mid in pending if mid not in priorities]
        next_rows=[];by_id={row['id']:row for row in completed}
        for index,mid in enumerate(order):
            row=dict(by_id[mid]) if mid in by_id else dict(id=mid,status='pending')
            row['task']=f'Modules/{index+1:04d}';next_rows.append(row)
        next_request={**request,'moduleOrder':order,'reusedModules':reused,'createdAt':time.time(),
            'continuation':dict(schemaVersion=1,previousRoot=str(previous),previousRequestSha256=sha(request_raw),
                previousStateSha256=sha(state_raw),previousOrder=ids,priorityModules=priorities),
            'stopAfterModule':stop_after_module}
        # Re-pin the old inputs immediately before publishing the new schedule.
        if read(previous/'request.json',128*1024*1024)!=request_raw or read(previous/'state.json',128*1024*1024)!=state_raw:
            fail('CODE_NATIVE_REUSE',str(previous),'Previous schedule changed during continuation preparation')
        root.mkdir(parents=True)
        modules._save(root/'request.json',next_request)
        modules._save(root/'state.json',dict(status='prepared',modules=next_rows,implementation='in_progress',compilation='not_run',runtime='not_run'))
    return status(root)


def module_order(plan):
    """Prefer implemented dependencies; retain cycles as explicit contract edges."""
    classes={row['id']:row for row in plan['classes']}
    dependencies={row['id']:set() for row in plan['modules']}
    for row in classes.values():
        dependencies[row['module']].update(classes[cid]['module'] for cid in row.get('typeDependencies',[])
                                           if classes[cid]['module']!=row['module'])
    remaining=set(dependencies);order=[];cycles=[]
    while remaining:
        ready=sorted(mid for mid in remaining if not dependencies[mid]&remaining)
        if not ready:
            # A cycle requires the shared typed architecture contract, not fake
            # dependency implementations or a permanently blocked queue.
            selected=min(remaining,key=lambda mid:(-sum(mid in dependencies[other]for other in remaining),len(dependencies[mid]&remaining),mid))
            cycles.append(dict(moduleId=selected,pendingTypeModules=sorted(dependencies[selected]&remaining)))
            ready=[selected]
        order.extend(ready);remaining.difference_update(ready)
    return order,cycles


def prepare(architecture_stage,output,*,codex=worker.DEFAULT_CODEX,timeout_seconds=3600,idle_seconds=900,external_references=None,retained_support_paths=()):
    stage=modules._pin_stage(architecture_stage)
    root=safe(output)
    if root.exists():fail('CODE_NATIVE_OUTPUT',str(root),'Require a new independent pipeline directory')
    for source in (stage['root'],safe(stage['request']['sourceRoot'])):
        if root==source or root.is_relative_to(source) or source.is_relative_to(root):
            fail('CODE_NATIVE_OUTPUT',str(root),'Pipeline must not overlap the architecture or frozen source')
    if type(timeout_seconds)is not int or not 1<=timeout_seconds<=3600 or type(idle_seconds)is not int or not 1<=idle_seconds<=timeout_seconds:
        fail('CODE_NATIVE_BUDGET',str(root),'Each module needs finite total/idle budgets within 3600 seconds')
    order,cycles=module_order(stage['plan']);root.mkdir(parents=True)
    modules._save(root/'request.json',dict(schemaVersion=1,architectureStage=str(stage['root']),**stage['pins'],
        codex=str(codex),timeoutSeconds=timeout_seconds,idleSeconds=idle_seconds,externalReferences=external_references or {},retainedSupportPaths=list(retained_support_paths),
        moduleOrder=order,contractCycleEdges=cycles,createdAt=time.time()))
    modules._save(root/'state.json',dict(status='prepared',modules=[dict(id=mid,status='pending',task=f'Modules/{i+1:04d}')for i,mid in enumerate(order)],
        implementation='not_started',compilation='not_run',runtime='not_run'))
    return status(root)


def _stage(root,request):
    stage=modules._pin_stage(request['architectureStage'])
    if stage['pins']!={key:request.get(key)for key in stage['pins']}:
        fail('CODE_NATIVE_SOURCE',str(root),'Global architecture or frozen source identity changed')
    prior=request.get('continuation');seen={str(root)}
    while prior:
        old=safe(prior['previousRoot'])
        if str(old) in seen or len(seen)>32:
            fail('CODE_NATIVE_REUSE',str(old),'Continuation lineage is cyclic or exceeds its bound')
        seen.add(str(old))
        if (sha(read(old/'request.json',128*1024*1024))!=prior['previousRequestSha256'] or
                sha(read(old/'state.json',128*1024*1024))!=prior['previousStateSha256']):
            fail('CODE_NATIVE_REUSE',str(old),'Frozen predecessor schedule changed after continuation')
        prior=modules._json(old/'request.json').get('continuation')
    return stage


def _collect(root,stage,state):
    """Pin model outputs into a fresh aggregate; unreviewed bodies remain partial."""
    aggregate=root/'Implementation'
    if aggregate.exists():fail('CODE_NATIVE_AGGREGATE',str(aggregate),'Existing aggregate may contain manual changes; never overwrite')
    aggregate.mkdir()
    files=[];classes={row['id']:row for row in stage['plan']['classes']};seen=set();module_rows=[]
    for item in state['modules']:
        module_rows.append(dict(id=item['id'],status='partial' if item['status']!='evidence_only' else 'evidence_only'))
        if item['status']=='evidence_only':continue
        task=task_root(root,item);report=modules.status(task)
        if report['manifestSha256']!=item['manifestSha256']:
            fail('CODE_NATIVE_MODULE',str(task),'Module receipt changed after generation')
        manifest=modules._json(task/modules.MANIFEST)
        records={row['classId']:row for row in manifest['classes']}
        for row in manifest['files']:
            path=row['targetPath']
            record=next((v for v in records.values()if v['path']==path),None)
            if record is None or stage['validation']['classPaths'].get(record['classId'])!=path or path in seen:
                fail('CODE_NATIVE_MODULE',path,'Module output violates global class ownership')
            seen.add(path)
            if row['status']!='generated_unreviewed':continue
            raw=read(inside(task,row['artifactPath']),max_bytes=worker.FILE_BYTES)
            if sha(raw)!=row['sha256'] or len(raw)!=row['bytes']:
                fail('CODE_NATIVE_MODULE',path,'Module implementation differs from its pinned receipt')
            planned=classes[record['classId']]
            members=sorted({sid for kind in ('fields','methods')for member in planned.get(kind,[])for sid in member.get('sourceMemberIds',[])})
            copy_verified(inside(task,row['artifactPath']),inside(aggregate,path),row['sha256'],row['bytes'],atomic=False)
            files.append(dict(path=path,sha256=row['sha256'],bytes=row['bytes'],owner='generated',classId=record['classId'],
                              sourceUnitIds=sorted(planned['sourceUnitIds']),sourceMemberIds=members,status='partial',
                              unresolved=['Generated output remains semantically unreviewed.']))
    raw=encoded(dict(schemaVersion=1,sourceManifestSha256=stage['pins']['sourceManifestSha256'],architectureSha256=stage['pins']['architectureSha256'],
        files=files,modules=module_rows,compilation='not_run',runtime='not_run',acceptance='model_outputs_unreviewed'))
    worker._atomic(aggregate/'manifest.json',raw)
    return aggregate,sha(raw)


def run(output):
    root=safe(output);request=modules._json(root/'request.json')
    with (root/'pipeline.lock').open('a+b')as lock:
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:fail('CODE_NATIVE_BUSY',str(root),'Another supervisor owns this pipeline')
        state=modules._json(root/'state.json');stage=_stage(root,request)
        if state['status']=='candidate_assembled_unvalidated':return status(root)
        module_table={row['id']:row for row in stage['plan']['modules']}
        state.update(status='running',implementation='in_progress');modules._save(root/'state.json',state)
        for item in state['modules']:
            if item['status']in ('generated_unreviewed','partial_unimplemented_seed','evidence_only'):continue
            task=inside(root,item['task'])
            if not module_table[item['id']]['classIds']:
                item.update(status='evidence_only');modules._save(root/'state.json',state);continue
            try:
                if not task.exists():
                    dependencies=[str(task_root(root,prior,request))for prior in state['modules']if prior['status']in ('generated_unreviewed','partial_unimplemented_seed')]
                    modules.prepare(stage['root'],item['id'],task,dependency_roots=dependencies,codex=request['codex'],
                        timeout_seconds=request['timeoutSeconds'],idle_seconds=request['idleSeconds'])
                current=modules.status(task)
                item.update(status=current['status']);state['activeModule']=item['id'];modules._save(root/'state.json',state)
                while current['status']in ('prepared','checkpoint'):
                    current=modules.run(task,session_id=current.get('sessionId')if current['status']=='checkpoint' else None)
                    item.update(status=current['status']);modules._save(root/'state.json',state)
            except (ValueError,OSError) as error:
                state.update(status='blocked',blocker=getattr(error,'code','module-execution-error'))
                item.update(status='blocked');state['activeModule']=item['id']
                modules._save(root/'state.json',state);raise
            if current['status']not in ('generated_unreviewed','partial_unimplemented_seed'):
                state.update(status='blocked',blocker=current.get('blocker')or current.get('reason')or current['status'])
                modules._save(root/'state.json',state);return status(root)
            item.update(status=current['status'],manifestSha256=current['manifestSha256']);modules._save(root/'state.json',state)
            if item['id']==request.get('stopAfterModule'):
                state.update(status='integration_checkpoint',implementation='model_outputs_unreviewed')
                state.pop('activeModule',None);modules._save(root/'state.json',state)
                return status(root)
        try:
            aggregate,pin=_collect(root,stage,state)
            from .code_architecture_candidate import assemble_native_candidate
            assembled=assemble_native_candidate(stage['request']['sourceRoot'],request['sourceManifestSha256'],stage['root']/'architecture.json',
                request['architectureSha256'],stage['root']/'validation.json',request['validationSha256'],aggregate,pin,root/'UnityProject',
                external_references=request['externalReferences'],retained_support_paths=request.get('retainedSupportPaths',()),allow_partial=True)
        except (ValueError,OSError) as error:
            state.update(status='blocked',implementation='model_outputs_unreviewed',
                         blocker=getattr(error,'code','assembly-execution-error'))
            state.pop('activeModule',None)
            modules._save(root/'state.json',state)
            raise
        state.update(status='candidate_assembled_unvalidated',implementation='model_outputs_unreviewed',candidate=str(root/'UnityProject'),
            candidateManifestSha256=sha(read(root/'UnityProject/manifest.json',max_bytes=128*1024*1024)),assemblyStatus=assembled['status'])
        state.pop('activeModule',None);modules._save(root/'state.json',state)
        return status(root)


def status(output):
    root=safe(output);state=modules._json(root/'state.json')
    if state['status']=='running' and state.get('activeModule'):
        active=next((row for row in state['modules']if row['id']==state['activeModule']),None)
        process=inside(root,active['task'])/'Task/process.json' if active else None
        if process and process.is_file():
            child=modules._json(process)
            state.update(childState=child.get('state'),childPid=child.get('pid'))
            if child.get('state')in ('starting','running'):active['status']='running'
    counts={}
    for row in state['modules']:counts[row['status']]=counts.get(row['status'],0)+1
    return {**state,'moduleCounts':counts,'report':str(root/'state.json')}
