"""Durable whole-candidate Codex work queue; deterministic export stays independent."""
from __future__ import annotations
import collections
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
from . import __version__
from .io import safe, read, load, sha, encoded, inside
from .candidate_snapshot import snapshot
from .sources.compiled import fail
from . import code_postprocess as worker

PLAN_BYTES = 128 * 1024 * 1024
STATE_BYTES = 64 * 1024 * 1024
_HEX = re.compile(r'[0-9a-f]{64}\Z')


def _json(path, maximum=STATE_BYTES):
    return load(read(safe(path), max_bytes=maximum), max_nodes=8_000_000)


def _save(path, value):
    worker._atomic(Path(path), encoded(value))


def _event(root, kind, **values):
    with (root/'progress.jsonl').open('ab') as stream:
        stream.write((json.dumps(dict(time=time.time(),event=kind,**values),ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8'))


def prepare(candidate, expected_manifest, output, *, max_files=128,
            max_code_bytes=512*1024, batch_seconds=3600, idle_seconds=900,
            max_attempts=2, codex=worker.DEFAULT_CODEX):
    from .code_postprocess_plan import prepare_plan
    source, manifest, rows, identity = snapshot(candidate)
    if identity != expected_manifest:
        fail('PROJECT_POSTPROCESS_IDENTITY', str(source), 'Owning manifest differs from the requested pin')
    if type(batch_seconds) is not int or not 1 <= batch_seconds <= 3600:
        fail('PROJECT_POSTPROCESS_BUDGET', str(output), 'Batch child time must be 1..3600 seconds')
    if type(idle_seconds) is not int or not 1 <= idle_seconds <= batch_seconds:
        fail('PROJECT_POSTPROCESS_BUDGET', str(output), 'Idle timeout must fit the batch budget')
    if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        fail('PROJECT_POSTPROCESS_BUDGET', str(output), 'Finite attempts must be 1..3 per batch')
    root = safe(output)
    if root.exists() or root.is_relative_to(source) or source.is_relative_to(root):
        fail('PROJECT_POSTPROCESS_OUTPUT', str(root), 'Require a fresh independent output outside the candidate')
    executable, cli_identity = worker._resolve_codex(codex)
    plan = prepare_plan(source, expected_manifest, max_files=max_files, max_code_bytes=max_code_bytes)
    files = {row['path']: row for row in plan['files']}
    paths = [p for batch in plan['batches'] for p in batch['paths']]
    queued={p for p,r in files.items()if r.get('owner','generated')=='generated'}
    if len(paths) != len(queued) or set(paths) != queued:
        fail('PROJECT_POSTPROCESS_PLAN', str(source), 'Every generated C# file must belong to exactly one batch')
    root.mkdir(parents=True, exist_ok=False); root.chmod(0o700)
    _save(root/'plan.json', plan)
    shutil.copyfile(source/manifest.get('_manifestName', 'manifest.json'), root/'original-manifest.json')
    request = dict(schemaVersion=1, version=__version__, sourceRoot=str(source), sourceManifestSha256=identity,
                   planSha256=sha(read(root/'plan.json', max_bytes=PLAN_BYTES)), codex=str(codex),
                   executable=cli_identity, batchSeconds=batch_seconds, idleSeconds=idle_seconds,
                   maxAttempts=max_attempts, maxResumesPerAttempt=2,
                   originalManifestName=manifest.get('_manifestName', 'manifest.json'))
    _save(root/'request.json', request)
    state = dict(schemaVersion=1, status='preparing', sourceManifestSha256=identity,
                 lastManifestSha256=identity, currentBatch=None, integration=None,
                 files={p: dict(status='pending' if p in queued else 'blocked', processed=False, attempts=0,
                     reasons=[] if p in queued else ['read-only non-generated owning file; no modification authorized']) for p in files},
                 batches={b['id']: dict(status='pending', attempts=0, files=b['paths'], attemptRoots=[]) for b in plan['batches']},
                 createdAt=time.time(), updatedAt=time.time(), blockingCondition=None)
    _save(root/'state.json', state)
    project = root/'UnityProject'; project.mkdir()
    # Copy only the pinned owning inventory; no engine/cache recovery is rerun.
    for rel in rows:
        target = inside(project, rel); target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(inside(source, rel), target, follow_symlinks=False)
        if target.stat().st_ino == inside(source, rel).stat().st_ino:
            fail('PROJECT_POSTPROCESS_COPY', rel, 'A writable hard link to the original is forbidden')
    shutil.copyfile(root/'original-manifest.json', project/request['originalManifestName'])
    state.update(status='pending', updatedAt=time.time())
    _save(root/'state.json', state); _event(root, 'prepared', files=len(files), batches=len(plan['batches']))
    return status(root)


def _open(root):
    root = safe(root); request = _json(root/'request.json'); plan_raw = read(root/'plan.json', max_bytes=PLAN_BYTES)
    if sha(plan_raw) != request['planSha256']:
        fail('PROJECT_POSTPROCESS_PLAN_CHANGED', str(root), 'Prepared queue plan was modified')
    plan = load(plan_raw, max_nodes=8_000_000); state = _json(root/'state.json')
    if state.get('strategySupersededBy'):
        fail('PROJECT_POSTPROCESS_SUPERSEDED', str(root),
             'This per-file strategy was replaced by architecture-first recovery; preserve its results and do not resume it')
    if sha(read(Path(request['sourceRoot'])/request['originalManifestName'], max_bytes=PLAN_BYTES)) != request['sourceManifestSha256']:
        fail('PROJECT_POSTPROCESS_SOURCE_CHANGED', request['sourceRoot'], 'Original owning manifest changed')
    return root, request, plan, state


def status(root):
    root=safe(root); request=_json(root/'request.json'); state=_json(root/'state.json')
    current=state.get('currentBatch');live=False
    if state['status']=='running' and current and state['batches'][current].get('attemptRoots'):
        process=root/state['batches'][current]['attemptRoots'][-1]/'process.json'
        if process.is_file():
            info=_json(process);pid=info.get('pid')
            live=info.get('state')=='running' and type(pid)is int
    if live:
        state['batches'][current]['status']='running'
        for path in state['batches'][current]['files']:
            if not state['files'][path].get('processed'):state['files'][path]['status']='running'
    counts = collections.Counter(row['status'] for row in state['files'].values())
    batch_counts = collections.Counter(row['status'] for row in state['batches'].values())
    return dict(status=state['status'], report=str(root/'state.json'), project=str(root/'UnityProject'),
                sourceManifestSha256=request['sourceManifestSha256'], totalFiles=len(state['files']),
                actuallyProcessed=sum(row.get('processed', False) for row in state['files'].values()),
                fileStates=dict(counts), totalBatches=len(state['batches']), batchStates=dict(batch_counts),
                currentBatch=state.get('currentBatch'), blockingCondition=state.get('blockingCondition'),
                strategySupersededBy=state.get('strategySupersededBy'),
                currentManifestSha256=state['lastManifestSha256'], updatedAt=state['updatedAt'],
                originalSourceExecuted=False, editorPlayerRun=False)


def request_pause(root, *, finish_current=False):
    root=safe(root); _json(root/'request.json')
    _save(root/'operator-control.json',dict(pauseRequested=True,finishCurrentAttempt=bool(finish_current),requestedAt=time.time()))
    state=_json(root/'state.json'); batch=state.get('currentBatch')
    if not finish_current and batch and state['batches'][batch].get('attemptRoots'):
        attempt=root/state['batches'][batch]['attemptRoots'][-1]
        if (attempt/'request.json').is_file(): worker.request_pause(attempt)
    return dict(status='pause_requested',report=str(root/'operator-control.json'),
                childStopped=False,finishCurrentAttempt=bool(finish_current),
                description='Finish the current attempt, then stop before new work' if finish_current else 'The supervisor will preserve the current exact-session checkpoint before exiting')


def _pause_requested(root):
    path=root/'operator-control.json'
    return path.is_file() and _json(path).get('pauseRequested') is True


def configure(root, *, batch_seconds, idle_seconds):
    root=safe(root)
    if type(batch_seconds) is not int or not 1<=batch_seconds<=3600 or type(idle_seconds) is not int or not 1<=idle_seconds<=batch_seconds:
        fail('PROJECT_POSTPROCESS_BUDGET',str(root),'Require finite batch seconds 1..3600 and idle seconds within that budget')
    with (root/'run.lock').open('a+b') as lock:
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:fail('PROJECT_POSTPROCESS_BUSY',str(root),'Pause the active supervisor before changing its budgets')
        root,request,plan,state=_open(root)
        batch=state.get('currentBatch')
        if batch and state['batches'][batch].get('attemptRoots'):
            attempt=root/state['batches'][batch]['attemptRoots'][-1]
            if (attempt/'process.json').is_file():
                info=_json(attempt/'process.json')
                if info.get('state') in ('running','starting','unknown'):
                    fail('PROJECT_POSTPROCESS_CHILD_ALIVE',str(attempt),'A recorded child must finish or save a pause checkpoint before budget changes')
            checkpoint=_json(attempt/'request.json')
            if checkpoint.get('state') in ('prepared','checkpoint'):
                worker.configure_checkpoint(attempt,timeout_seconds=batch_seconds,no_progress_seconds=idle_seconds)
        old=dict(batchSeconds=request['batchSeconds'],idleSeconds=request['idleSeconds'])
        request.update(batchSeconds=batch_seconds,idleSeconds=idle_seconds)
        _save(root/'request.json',request)
        _event(root,'budgets_changed',before=old,after=dict(batchSeconds=batch_seconds,idleSeconds=idle_seconds),
               attemptsReset=False,elapsedReset=False,modelChanged=False)
    return dict(status='configured',report=str(root/'request.json'),batchSeconds=batch_seconds,idleSeconds=idle_seconds)


def _contexts(root, request, plan, batch, paths, attempt):
    directory = root/'Evidence'/batch['id']/str(attempt); directory.mkdir(parents=True, exist_ok=False)
    records = {r['path']: r for r in plan['files']}; fragments = []
    source_data = {}
    for path in paths:
        row = records[path]; source_sha = row.get('sourceSha256') or row.get('sourceId')
        source_path = row.get('sourcePath')
        if not source_path:
            source = next((s for s in plan.get('sources', []) if s.get('sha256') == source_sha), None)
            source_path = source and source['sourcePath']
        if not source_path:
            fragments.append(dict(path=path, sourcePath=None, sourceKind=row.get('sourceKind'),
                reason=row.get('absentSourceReason') or row.get('missingSourceReason') or 'No original JS counterpart indexed; review the exact owning C# bytes without inventing provenance',
                originalCSharpSha256=row['sha256'], fragments=[]))
            continue
        if source_path not in source_data:
            raw = read(inside(Path(request['sourceRoot']), source_path), max_bytes=32*1024*1024)
            if source_sha and sha(raw) != source_sha:
                fail('PROJECT_POSTPROCESS_CONTEXT', source_path, 'Original script identity changed')
            source_data[source_path] = raw
        raw = source_data[source_path]; intervals = []
        for member in row.get('functions', []) + row.get('fields', []):
            span = member.get('sourceBytes') or {}; a, b = span.get('start'), span.get('end')
            if type(a) is not int or type(b) is not int or not 0 <= a < b <= len(raw):
                fail('PROJECT_POSTPROCESS_CONTEXT', path, 'Member source span is unavailable')
            if sha(raw[a:b]) != member.get('sourceSha256'):
                fail('PROJECT_POSTPROCESS_CONTEXT', path, 'Member source span hash differs')
            intervals.append((a,b))
        if not intervals and isinstance(row.get('class'), dict):
            c = row['class']; span = c.get('sourceBytes') or {}; a,b = span.get('start'),span.get('end')
            if type(a) is int and type(b) is int and 0 <= a < b <= len(raw):
                if c.get('sourceSha256') and sha(raw[a:b]) != c['sourceSha256']:
                    fail('PROJECT_POSTPROCESS_CONTEXT', path, 'Class source context hash changed')
                intervals.append((a,b))
        if row.get('sourceWholeModule'):
            intervals=[(0,len(raw))]
        merged = []
        for a,b in sorted(intervals):
            if merged and a <= merged[-1][1]: merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else: merged.append((a,b))
        fragments.append(dict(path=path, sourcePath=source_path, sourceSha256=sha(raw),
                              fragments=[dict(start=a,end=b,sha256=sha(raw[a:b]),text=raw[a:b].decode('utf-8')) for a,b in merged]))
    _save(directory/'original-source-fragments.json', dict(sourceExecuted=False, files=fragments))
    scoped=[]; source_ids=set()
    member_keys=('methodId','kind','sourceName','sourceBytes','functionBytes','sourceSha256','targetMethod','targetLocationMarker','status')
    field_keys=('fieldId','sourceName','sourceBytes','sourceSha256','targetMember','initializationContext','status')
    for p in paths:
        row=records[p]; source_ids.add(row.get('sourceSha256'))
        scoped.append(dict(path=p,sha256=row['sha256'],bytes=row['bytes'],sourcePath=row.get('sourcePath'),sourceSha256=row.get('sourceSha256'),
            sourceKind=row.get('sourceKind'),sourceWholeModule=row.get('sourceWholeModule',False),classMetadata=row.get('class'),
            absentSourceReason=row.get('absentSourceReason') or row.get('missingSourceReason'),
            functions=[{k:f.get(k)for k in member_keys}for f in row.get('functions',[])],
            fields=[{k:f.get(k)for k in field_keys}for f in row.get('fields',[])],dependencies=row.get('dependencies',[])))
    _save(directory/'file-mappings.json', dict(files=scoped,sources=[r for r in plan.get('sources',[])if r.get('sha256')in source_ids],
        batchId=batch['id'],dependencies=batch.get('dependencyBatchHints',[])))
    return directory, ['original-source-fragments.json', 'file-mappings.json']


def _task(batch_id):
    return f'''Process the COMPLETE assigned recovery batch {batch_id}; this is whole-project batch processing, not a sample. Read and substantively analyze EVERY selected C# file and all of its mapped source functions/fields, using __Context/file-mappings.json and exact original-source-fragments.json. Where exact original modules exist for older named drafts, recover supported source bodies rather than treating all existing placeholder bodies as final. Do not restrict this pass to formatting or directory statistics. Read large files in bounded chunks; listing filenames, counting lines or reporting hashes alone does not count as review. Repair reliable C# syntax, inferable local types, collection/API calls, closures and scope, declaration/reference consistency, cross-class calls and Unity adaptation drafts. Preserve original business logic and resource identities. Preserve exported class/member names and every existing source-function marker; do not delete functions, replace business bodies by stubs, invent services or fake success. Avoid unnecessary edits: unchanged is valid only with specific findings about the actual code. Unknown dynamic/engine/type semantics must be recorded per file as partial, with exact unresolved details. Report originalLogicPreserved honestly: false with concrete semantic limitations is an analyzed partial draft, not a claim of equivalence; do not mark unexamined files as partial. Review SDK/engine/auxiliary candidates too; labels do not exclude them. Do not execute original JS/WASM/DLL, engines, network tools, other Codex CLIs or agents. Only edit the selected .cs files. You may additionally create exactly __Reviews/file-results.json for the complete review ledger as specified by the worker instructions; create no other files and delete none. Only read supplied immutable __Context files as evidence, and never change __Context, Git metadata, model/configuration or credentials. For EVERY selected path write a ledger entry with concrete summary, status, all required source function IDs from that file map in membersReviewed (including embedded callbacks; empty only if the file map has no functions), unresolved, and originalLogicPreserved. You may derive the exact reviewed ID lists from the map with a script after substantive analysis; do not invent IDs or mark other files processed because their nested source was encountered. Known field IDs may also be included. Do not claim a file reviewed if its body/mapped functions were not analyzed. Local unknowns may be partial; they must not stop review of the other selected files. Apply actual improvements where justified. Preserve a full useful continuation draft; full compilation/gameplay are not required. Return the exact structured response with changedPaths matching actual modified C# files and fileResultsArtifact pointing to the fixed ledger; the ledger is not a changed C# path.'''


def _review_index(plan):
    sources=collections.defaultdict(list)
    for row in plan['files']:
        source=row.get('sourceSha256')
        if not source:continue
        for member in row.get('functions',[]):
            span=member.get('sourceBytes') or {};a,b=span.get('start'),span.get('end')
            if type(a)is int and type(b)is int and a<b:
                sources[source].append((member['methodId'],a,b))
    return sources


def _allowed_review_ids(metadata,index):
    allowed={r['methodId']for r in metadata.get('functions',[])}
    allowed.update(r['fieldId']for r in metadata.get('fields',[]))
    spans=[r.get('sourceBytes')or{}for r in metadata.get('functions',[])+metadata.get('fields',[])]
    if not spans and isinstance(metadata.get('class'),dict):spans=[metadata['class'].get('sourceBytes')or{}]
    for member,a,b in index.get(metadata.get('sourceSha256'),[]):
        if any(type(s.get('start'))is int and type(s.get('end'))is int and s['start']<=a<b<=s['end']for s in spans):
            allowed.add(member)
    return allowed


def _valid_file(path, before, after, result, metadata, allowed_review_ids=None):
    issues = []
    if result.get('path') != path or type(result.get('originalLogicPreserved'))is not bool:
        issues.append('missing per-file path or explicit logic-preservation assessment')
    if result.get('originalLogicPreserved')is False and (result.get('status')!='partial' or not result.get('unresolved')):
        issues.append('unconfirmed logic preservation requires an explicit partial assessment with limitations')
    expected = {r['methodId'] for r in metadata.get('functions', [])}
    actual = set(result.get('membersReviewed', []))
    allowed=(expected|{r['fieldId']for r in metadata.get('fields',[])}) if allowed_review_ids is None else allowed_review_ids
    if not expected<=actual or not actual<=allowed:
        issues.append(f'source function review coverage differs: missing={len(expected-actual)}, unknown={len(actual-allowed)}')
    summary = result.get('summary', '').strip()
    if len(summary) < 16:
        issues.append('review reason is too short to describe actual findings')
    if result.get('status') == 'blocked': issues.append('model explicitly reported this file unprocessed/blocked')
    old_markers = set(re.findall(rb'/\* source-function:([^*]+) \*/', before))
    new_markers = set(re.findall(rb'/\* source-function:([^*]+) \*/', after))
    if not old_markers <= new_markers: issues.append('source callback location markers were removed')
    text = after.decode('utf-8')
    for f in metadata.get('functions', []):
        if f.get('status') == 'embedded_in_owner': continue
        name = f.get('targetMethod')
        if name and not re.search(r'\b(?:public|private|protected|internal)\b[^;{}]*\b'+re.escape(name)+r'\s*\(', text):
            issues.append('exported method name is no longer locatable: '+name)
    if before != after and result.get('status') == 'unchanged': issues.append('reported unchanged but actual bytes changed')
    classes = {f.get('targetClass') for f in metadata.get('functions', []) if f.get('targetClass')}
    if isinstance(metadata.get('class'), dict) and metadata['class'].get('targetClass'):
        classes.add(metadata['class']['targetClass'])
    for name in classes:
        if not re.search(r'\bclass\s+'+re.escape(name)+r'\b', text): issues.append('exported class no longer locatable: '+name)
    for field in metadata.get('fields', []):
        name=field.get('targetMember')
        if name and not re.search(r'\b(?:public|private|protected|internal)\b[^;{}]*\b'+re.escape(name)+r'\s*[=;{]', text):
            issues.append('exported field no longer locatable: '+name)
    for name in re.findall(r'\b(?:class|struct|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)',before.decode('utf-8')):
        if not re.search(r'\b(?:class|struct|interface|enum)\s+'+re.escape(name)+r'\b',text):
            issues.append('original type declaration was removed: '+name)
    return issues


def _integrate(root, request, state):
    journal_path = root/'integration.json'
    if not journal_path.is_file(): return
    journal = _json(journal_path)
    if journal.get('state') == 'committed': return
    project = root/'UnityProject'; manifest_path = project/request['originalManifestName']
    raw = read(manifest_path, max_bytes=PLAN_BYTES); manifest = load(raw, max_nodes=8_000_000)
    rows = {r['path']: r for r in manifest['files']}
    for item in journal['files']:
        path = item['path']; target = inside(project, path); current = sha(read(target, max_bytes=worker.FILE_BYTES))
        if current not in (item['beforeSha256'], item['afterSha256']):
            fail('PROJECT_POSTPROCESS_DIRTY', path, 'Manual/unrelated changes block integration; nothing will overwrite them')
        payload = read(safe(item['payload']), max_bytes=worker.FILE_BYTES)
        if sha(payload) != item['afterSha256']:
            fail('PROJECT_POSTPROCESS_RESULT_CHANGED', path, 'Reviewed derived payload changed before integration')
        if current != item['afterSha256']: worker._atomic(target, payload)
        rows[path].update(sha256=item['afterSha256'], bytes=len(payload))
        state['files'][path] = item['result']
    manifest['files'] = [rows[r['path']] for r in manifest['files']]
    manifest['codePostprocess'] = dict(schemaVersion=1, status='in_progress', sourceManifestSha256=request['sourceManifestSha256'],
                                      runId=root.name, originalDraftsPreservedInOriginalCandidate=True)
    worker._atomic(manifest_path, encoded(manifest))
    state['lastManifestSha256'] = sha(read(manifest_path, max_bytes=PLAN_BYTES))
    state['integration'] = None; state['updatedAt'] = time.time(); _save(root/'state.json', state)
    journal['state'] = 'committed'; _save(journal_path, journal)


def _attempt(root, request, plan, state, batch, remaining):
    entry = state['batches'][batch['id']]; entry['attempts'] += 1; number = entry['attempts']
    evidence, context_files = _contexts(root, request, plan, batch, remaining, number)
    output = root/'Batches'/batch['id']/f'Attempt{number:02d}'
    entry['attemptRoots'].append(str(output.relative_to(root)))
    entry.update(status='running'); state.update(status='running', currentBatch=batch['id'], updatedAt=time.time())
    for path in remaining: state['files'][path].update(status='running', attempts=state['files'][path].get('attempts',0)+1)
    _save(root/'state.json', state); _event(root, 'batch_started', batch=batch['id'], attempt=number, files=len(remaining))
    prepared = worker.prepare(request['sourceRoot'], remaining, request['sourceManifestSha256'], output, _task(batch['id']),
                              context_root=evidence, context_files=context_files, project_batch=True, project_result_ledger=True,
                              codex=request['codex'], timeout_seconds=request['batchSeconds'],
                              no_progress_seconds=request['idleSeconds'], max_resumes=request['maxResumesPerAttempt'])
    if _pause_requested(root): worker.request_pause(output)
    result = worker.run(prepared)
    # Exact-session resumes are local to this attempt; the project can execute many sessions/batches.
    while not result.get('blockingCondition'):
        checkpoint = _json(output/'request.json')
        if checkpoint.get('state') != 'checkpoint' or not checkpoint.get('lastSessionId'): break
        if checkpoint.get('resumeCount',0) >= request['maxResumesPerAttempt']: break
        if checkpoint.get('childElapsedSeconds',0) >= request['batchSeconds']: break
        result = worker.run(prepared, session_id=checkpoint['lastSessionId'])
    return _consume(root, request, plan, state, batch, remaining, output, result)


def _load_saved_result(output):
    result=_json(output/'manifest.json');artifact=result.get('fileResultsArtifact')
    if not isinstance(artifact,dict):return result
    name=artifact.get('archivePath','')
    if not isinstance(name,str)or not re.fullmatch(r'file-results-ledger-[0-9]{2}\.json',name):
        fail('PROJECT_POSTPROCESS_RESULT_CHANGED',str(output),'Saved review ledger archive identity is invalid')
    archive=output/name
    if archive.is_symlink()or not archive.is_file()or archive.stat().st_nlink!=1:
        fail('PROJECT_POSTPROCESS_RESULT_CHANGED',str(archive),'Saved ledger must remain an independent regular file')
    raw=read(archive,max_bytes=worker.LEDGER_BYTES)
    if sha(raw)!=artifact.get('sha256')or len(raw)!=artifact.get('bytes'):
        fail('PROJECT_POSTPROCESS_RESULT_CHANGED',str(archive),'Saved review ledger changed after its recorded hash')
    try:
        parsed=load(raw,max_nodes=worker.LEDGER_NODES,max_depth=32)
        rows=worker._ledger_rows(parsed)
    except ValueError as error:
        return {**result,'fileResultsArtifactIssues':list(result.get('fileResultsArtifactIssues',[]))+
                ['saved ledger shape remains invalid: '+str(getattr(error,'code',type(error).__name__))]}
    normalized,issues,_=worker._normalize_file_results(rows,result['selected'])
    return {**result,'fileResults':normalized,'fileResultIssues':issues,
            'ledgerRevalidatedFrom':dict(sha256=artifact['sha256'],archivePath=name,
                format='fileResults-wrapper'if isinstance(parsed,dict)else'array',rows=len(rows))}


def _consume(root, request, plan, state, batch, remaining, output, result):
    entry = state['batches'][batch['id']]; number = entry['attempts']
    metadata = {r['path']: r for r in plan['files']}
    review_index=_review_index(plan)
    reported = {r['path']: r for r in result.get('fileResults', [])}
    reviewed_hashes={r['path']:r.get('afterSha256')for r in result.get('actualChanges',[])}
    integration = []; rejected = []
    if result.get('sourceVerificationErrors'):
        fail('PROJECT_POSTPROCESS_SOURCE_CHANGED',request['sourceRoot'],'Original candidate/source verification failed during Codex processing')
    unsafe_batch = bool(result.get('workspaceIntegrityErrors') or result.get('unexpectedPaths') or
                        result.get('fileResultsArtifactIssues') or not result.get('gitBoundary',{}).get('valid'))
    for path in remaining:
        raw_result=reported.get(path,{})
        f=dict(raw_result);metadata_issues=[]
        allowed=_allowed_review_ids(metadata[path],review_index)
        unknown=set(f.get('membersReviewed',[]))-allowed
        if unknown:
            metadata_issues.append(dict(kind='unrecognized_review_ids',ids=sorted(unknown)))
            f['membersReviewed']=[v for v in f.get('membersReviewed',[])if v in allowed]
            f['status']='partial'
            f['unresolved']=list(f.get('unresolved',[]))+['Unrecognized additional review IDs are excluded from verified coverage: '+', '.join(sorted(unknown))]
        if f.get('originalLogicPreserved')is False:f['status']='partial'
        before = read(inside(Path(request['sourceRoot']), path), max_bytes=worker.FILE_BYTES)
        if sha(before)!=metadata[path]['sha256']:
            fail('PROJECT_POSTPROCESS_SOURCE_CHANGED',path,'Original code bytes no longer match the prepared queue')
        after_path = output/'workspace'/path
        issues = ['workspace boundary violation'] if unsafe_batch else []
        if raw_result.get('status')=='blocked':issues.append('model explicitly reported this file unprocessed/blocked')
        if raw_result.get('originalLogicPreserved')is False and not raw_result.get('unresolved'):
            issues.append('logic preservation is unconfirmed without concrete semantic limitations')
        try:
            after = read(safe(after_path), max_bytes=worker.FILE_BYTES)
            if sha(after)!=reviewed_hashes.get(path,metadata[path]['sha256']):
                fail('PROJECT_POSTPROCESS_RESULT_CHANGED',path,'Batch workspace changed after its recorded review; it cannot be replayed')
            issues.extend(_valid_file(path, before, after, f, metadata[path],allowed))
        except (OSError,ValueError)as error:
            if getattr(error,'code',None)=='PROJECT_POSTPROCESS_RESULT_CHANGED':raise
            after = before; issues.append('derived code file unavailable')
        if issues:
            rejected.append(path)
            state['files'][path].update(status='blocked' if result.get('blockingCondition') else 'pending', processed=False,
                                         reasons=issues, lastAttempt=str(output.relative_to(root)))
            continue
        state_name = f['status']
        record = dict(status=state_name, processed=True, attempts=state['files'][path]['attempts'],
                      summary=f['summary'], unresolved=f.get('unresolved',[]), membersReviewed=f['membersReviewed'],
                      originalLogicPreservedClaim=f['originalLogicPreserved'],reportedStatus=raw_result.get('status'),
                      reportedMembersReviewed=raw_result.get('membersReviewed',[]),reviewMetadataIssues=metadata_issues,
                      sourceSha256=sha(before), currentSha256=sha(after),
                      changed=before!=after, batch=batch['id'], lastAttempt=str(output.relative_to(root)), sessionId=result.get('sessionId'))
        integration.append(dict(path=path, beforeSha256=sha(before), afterSha256=sha(after),
                                payload=str(after_path), result=record))
    if integration:
        _save(root/'integration.json', dict(schemaVersion=1, state='prepared', batch=batch['id'], files=integration))
        state['integration'] = 'integration.json'; _save(root/'state.json', state); _integrate(root, request, state)
    entry['lastResult'] = dict(status=result['status'], sessionId=result.get('sessionId'), usage=result.get('usage'),
                               model=result.get('model'), reasoningEffort=result.get('reasoningEffort'),
                               blockingCondition=result.get('blockingCondition'), diffSha256=result.get('diffSha256'), rejectedFiles=len(rejected),
                               ledgerRevalidatedFrom=result.get('ledgerRevalidatedFrom'))
    if result.get('blockingCondition'):
        state['blockingCondition'] = dict(kind=result['blockingCondition'], batch=batch['id'], attempt=number,
                                         report=str((output/'manifest.json').relative_to(root)))
        entry['status'] = 'checkpoint' if result['blockingCondition']=='operator_pause' else 'blocked'
        state['status'] = 'paused' if result['blockingCondition']=='operator_pause' else 'blocked'
    else:
        entry['status'] = 'pending' if rejected else 'partial' if any(state['files'][p]['status']=='partial' for p in batch['paths']) else 'processed'
    state['updatedAt'] = time.time(); _save(root/'state.json', state)
    _event(root, 'batch_finished', batch=batch['id'], attempt=number, accepted=len(integration), remaining=len(rejected), status=entry['status'])
    return rejected


def recheck(root):
    """Revalidate saved completed reviews after a validator fix, without a model call."""
    root=safe(root)
    with (root/'run.lock').open('a+b')as lock:
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:fail('PROJECT_POSTPROCESS_BUSY',str(root),'Pause the supervisor before replaying saved review records')
        root,request,plan,state=_open(root);_integrate(root,request,state)
        if sha(read(root/'UnityProject'/request['originalManifestName'],max_bytes=PLAN_BYTES))!=state['lastManifestSha256']:
            fail('PROJECT_POSTPROCESS_DIRTY',str(root),'Derived manifest changed outside recorded integration')
        current=state.get('currentBatch')
        if current and state['batches'][current].get('attemptRoots'):
            process=root/state['batches'][current]['attemptRoots'][-1]/'process.json'
            if process.is_file()and _json(process).get('state')!='exited':
                fail('PROJECT_POSTPROCESS_CHILD_ALIVE',str(process),'Saved reviews can only be replayed while the child is stopped')
        before=sum(v.get('processed',False)for v in state['files'].values())
        for batch in plan['batches']:
            entry=state['batches'][batch['id']]
            original_status=entry['status']
            if not entry.get('attemptRoots'):continue
            for attempt in reversed(entry['attemptRoots']):
                output=root/attempt
                if not(output/'manifest.json').is_file():continue
                result=_load_saved_result(output)
                if result.get('blockingCondition') or not result.get('fileResults'):continue
                reported={r['path']for r in result['fileResults']}
                paths=[p for p in batch['paths']if not state['files'][p].get('processed')and p in reported]
                if paths:_consume(root,request,plan,state,batch,paths,output,result)
            if any(not state['files'][p].get('processed')for p in batch['paths'])and original_status in ('checkpoint','running','blocked'):
                entry['status']=original_status;_save(root/'state.json',state)
        _event(root,'saved_reviews_rechecked',newlyAccepted=sum(v.get('processed',False)for v in state['files'].values())-before,
               validatorSha256=sha(read(Path(__file__),max_bytes=worker.FILE_BYTES)),modelCalled=False)
    return status(root)


def _finish(root, request, plan, state):
    project = root/'UnityProject'; files = state['files']; counts = collections.Counter(r['status'] for r in files.values())
    processed = sum(r.get('processed',False) for r in files.values())
    pending = any(r['status'] in ('pending','running') for r in files.values())
    state['status'] = ('incomplete' if pending or processed != len(files) else 'complete_with_partial' if counts['partial'] else 'complete')
    state.update(currentBatch=None, updatedAt=time.time())
    report = dict(schemaVersion=1, producerVersion=__version__, sourceManifestSha256=request['sourceManifestSha256'],
                  status=state['status'], totalFiles=len(files), actuallyProcessed=processed, fileStates=dict(counts),
                  files=files, batches=state['batches'], sourceExecuted=False, compilation='not_required;not_whole_project_verified',
                  gameplay='not_run', originalCandidateUnchanged=True)
    manifest_path=project/request['originalManifestName'];manifest=_json(manifest_path,PLAN_BYTES);rows={r['path']:r for r in manifest['files']}
    rel='Analysis/Code/project-codex-postprocess.json';docrel='Docs/CODEX-PROJECT-REVISION.md'
    for p in (rel,docrel):
        target=inside(project,p)
        if target.exists():
            if p not in rows or rows[p].get('owner')!='generated' or sha(read(target,max_bytes=STATE_BYTES))!=rows[p]['sha256']:
                fail('PROJECT_POSTPROCESS_REPORT_COLLISION',p,'Existing manual or modified report cannot be overwritten')
    content=encoded(report);target=inside(project,rel);target.parent.mkdir(parents=True,exist_ok=True);worker._atomic(target,content)
    doc=(f'# Whole-project Codex revision\n\nStatus: {state["status"]}. Actually reviewed {processed}/{len(files)} files. '
         'Read Analysis/Code/project-codex-postprocess.json for every file and batch. Partial/failed/blocked entries retain specific limitations. '
         'The original export and source maps remain separate provenance; AI claims are not semantic or whole-project compilation proof. '
         'Code remains in SourceRecovery/CSharp until adoption by game developers. No source game program, Editor or Player was executed.\n').encode()
    worker._atomic(project/docrel,doc)
    for p,raw in ((rel,content),(docrel,doc)):
        if p in rows and rows[p].get('owner')!='generated':
            fail('PROJECT_POSTPROCESS_REPORT_COLLISION',p,'Final report cannot overwrite a manual path')
        rows[p]=dict(path=p,owner='generated',sha256=sha(raw),bytes=len(raw))
    manifest['files']=list(rows.values());manifest['codePostprocess']=dict(schemaVersion=1,status=state['status'],report=rel,
        sourceManifestSha256=request['sourceManifestSha256'],totalFiles=len(files),actuallyProcessed=processed,fileStates=dict(counts))
    worker._atomic(manifest_path,encoded(manifest));state['lastManifestSha256']=sha(read(manifest_path,max_bytes=PLAN_BYTES))
    _save(root/'state.json',state);_event(root,'finished',status=state['status'],actuallyProcessed=processed,totalFiles=len(files))
    return status(root)


def run(root):
    root,request,plan,state=_open(root)
    lock=(root/'run.lock').open('a+b')
    try:
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:fail('PROJECT_POSTPROCESS_BUSY',str(root),'This project queue already has an active runner')
        _integrate(root,request,state)
        manifest_path=root/'UnityProject'/request['originalManifestName']
        if sha(read(manifest_path,max_bytes=PLAN_BYTES))!=state['lastManifestSha256']:
            fail('PROJECT_POSTPROCESS_DIRTY',str(manifest_path),'Derived owning manifest changed outside recorded integration')
        if state['status'] in ('complete','complete_with_partial'):return status(root)
        if _pause_requested(root):
            state.update(status='paused',updatedAt=time.time());_save(root/'state.json',state);return status(root)
        if state['status']=='preparing':fail('PROJECT_POSTPROCESS_PREPARING',str(root),'Candidate copy preparation is incomplete; preserve it for recovery')
        state['blockingCondition']=None;state['status']='running';_save(root/'state.json',state)
        for batch in plan['batches']:
            if _pause_requested(root):
                state.update(status='paused',updatedAt=time.time());_save(root/'state.json',state);return status(root)
            entry=state['batches'][batch['id']]
            remaining=[p for p in batch['paths']if not state['files'][p].get('processed')]
            if not remaining:continue
            # A killed supervisor never trusts an uncommitted mutable workspace as reviewed output.
            if entry['status'] in ('running','checkpoint'):
                old=root/entry['attemptRoots'][-1];live=old/'process.json'
                if live.is_file():
                    info=_json(live)
                    if info.get('state')=='running' and isinstance(info.get('pid'),int):
                        try:os.kill(info['pid'],0)
                        except ProcessLookupError:pass
                        else:fail('PROJECT_POSTPROCESS_CHILD_ALIVE',str(old),'Recorded Codex child is still alive; do not start a second CLI')
                if (old/'manifest.json').is_file():
                    entry['status']='running'
                    for path in remaining:state['files'][path]['status']='running'
                    state['updatedAt']=time.time();_save(root/'state.json',state)
                    result=_load_saved_result(old)
                    checkpoint=_json(old/'request.json')
                    if checkpoint.get('state')=='prepared' and result.get('blockingCondition')=='operator_pause':
                        result=worker.run(old);checkpoint=_json(old/'request.json')
                    while checkpoint.get('state')=='checkpoint' and checkpoint.get('lastSessionId') and checkpoint.get('resumeCount',0)<request['maxResumesPerAttempt'] and checkpoint.get('childElapsedSeconds',0)<request['batchSeconds']:
                        result=worker.run(old,session_id=checkpoint['lastSessionId']);checkpoint=_json(old/'request.json')
                        if result.get('blockingCondition'):break
                    remaining=_consume(root,request,plan,state,batch,remaining,old,result)
                    if state.get('blockingCondition'):return status(root)
                else:entry['status']='pending'
            while remaining and entry['attempts'] < entry.get('attemptLimit',request['maxAttempts']):
                if _pause_requested(root):
                    state.update(status='paused',updatedAt=time.time());_save(root/'state.json',state);return status(root)
                try:remaining=_attempt(root,request,plan,state,batch,remaining)
                except (OSError,ValueError) as error:
                    code=getattr(error,'code',type(error).__name__)
                    entry['lastError']=dict(code=code,message=str(error)[:2000])
                    for p in remaining:state['files'][p].update(status='pending',processed=False,reasons=[str(error)[:2000]])
                    _event(root,'batch_error',batch=batch['id'],code=code)
                    state['updatedAt']=time.time();_save(root/'state.json',state)
                    if code=='POSTPROCESS_BUSY':
                        state.update(status='blocked',blockingCondition=dict(kind='busy',batch=batch['id'],message=str(error)[:1000]))
                        _save(root/'state.json',state);return status(root)
                    if code in ('PROJECT_POSTPROCESS_DIRTY','PROJECT_POSTPROCESS_RESULT_CHANGED','PROJECT_POSTPROCESS_SOURCE_CHANGED'):raise
                if state.get('blockingCondition'):return status(root)
            if remaining:
                entry['status']='failed'
                for p in remaining:state['files'][p].update(status='failed',processed=False)
                _save(root/'state.json',state)
        return _finish(root,request,plan,state)
    finally:lock.close()


def resume(root, *, retry_failed=False):
    root=safe(root)
    with (root/'run.lock').open('a+b') as lock:
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:fail('PROJECT_POSTPROCESS_BUSY',str(root),'A running supervisor owns this queue; resume cannot rewrite its state')
        root,request,plan,state=_open(root)
        if _pause_requested(root):_save(root/'operator-control.json',dict(pauseRequested=False,resumedAt=time.time()))
        if retry_failed:
            for entry in state['batches'].values():
                if entry['status']=='failed':
                    entry['attemptLimit']=entry['attempts']+request['maxAttempts']
                    entry['status']='pending'
            state['status']='pending';state['updatedAt']=time.time();_save(root/'state.json',state)
    return run(root)
