"""Bounded manifest updates for registered monkey outputs; never a general file synchronizer."""
from contextlib import contextmanager
from pathlib import Path
import os
import uuid
from . import __version__
from .io import safe, inside, read, load, sha, encoded, write_json, new_output, finish, diagnostic, stage_document
from .sources.compiled import fail
from .output_limits import digest_file, check_inventory, copy_verified, MANIFEST_BYTES, MANIFEST_NODES
from .layout import standard
from .layout.standard import find_analysis

PROFILES={'unity-6000.6.2f1-ugui','cocos-3.8.8'}
# monkey-project/2.0.0 has no manual folder: ownership is the manifest owner field (PROJECT-SPEC 4.1).
CURRENT_ROOTS={'unity':('Assets/Game/','Assets/TextMesh Pro/','Packages/','ProjectSettings/','Analysis/','Docs/','SourceRecovery/'),
               'creator':('assets/','extensions/monkey-import/','settings/','Analysis/','Docs/','SourceRecovery/')}
CURRENT_SCAN={'unity':(standard.ROOTS['unity']['content'],standard.ROOTS['unity']['scenes'],standard.ROOTS['unity']['conversion'],'Packages','ProjectSettings','Analysis'),
              'creator':('assets/Game','assets/resources',
                         standard.ROOTS['creator']['conversion'],'Analysis')}


def _engine(profile):return 'unity' if profile.startswith('unity-') else 'creator'


def manual(profile,relative,current=False):
    if current:return False
    return relative.startswith('Assets/Manual/' if profile.startswith('unity-') else 'assets/manual/')


def managed(profile,relative,current=False):
    if current:return relative in ('README.md','AGENTS.md','package.json','tsconfig.json') or relative.startswith(CURRENT_ROOTS[_engine(profile)])
    if manual(profile,relative):return False
    prefixes=('Assets/Generated/','Assets/Monkey/Editor/','Packages/','ProjectSettings/','Analysis/') if profile.startswith('unity-') else ('assets/generated/','extensions/monkey-import/','Analysis/')
    return relative in ('README.md','package.json') or relative.startswith(prefixes)


def snapshot(candidate):
    from .candidate_snapshot import snapshot as inventory
    root,m,files,h=inventory(candidate)
    if m['_manifestName']!='manifest.json':
        fail('ADOPT_REQUIRED',str(root),'Unity-source recovery inventories use adopt, not legacy apply')
    current=standard.current(m)
    for relative,f in files.items():
        if not (managed(m['targetProfile'],relative,current) or manual(m['targetProfile'],relative,current)):
            fail('UNMANAGED_PATH',relative,'File is outside target ownership boundary')
        if not current and f['owner']=='manual' and not manual(m['targetProfile'],relative):
            fail('MANUAL_BOUNDARY',relative,'Manual ownership is confined to the declared manual area')
        if not current and manual(m['targetProfile'],relative) and f['owner']=='generated':
            fail('MANUAL_BOUNDARY',relative,'Generator cannot own manual work')
    return root,m,files,h


def actual(root,relative):
    path=inside(root,relative)
    if not path.exists():return None
    if not path.is_file():return 'not-a-file'
    return digest_file(path)


def check_content(root,files):
    return [dict(path=p,reason='modified-or-missing',expected=f['sha256'],actual=actual(root,p))
            for p,f in files.items() if f['owner']!='manual' and actual(root,p)!=f['sha256']]


def identities(root,m,files):
    # Logical source identity is deliberately separate from content hashes.
    source_map=load(read(find_analysis(root,'source-map.json')));mapping={}
    for a in source_map.get('assets',[]):
        path=a.get('path');sid=a.get('sourceId')
        if path and sid:mapping.setdefault(path,[]).append(sid);mapping.setdefault(path+'.meta',[]).append(sid)
    return {p:dict(logicalId=m['targetProfile']+'/'+m['namespace']+'/'+p,sourceIds=sorted(set(mapping.get(p,[])))) for p in files}


def diff_data(before,after):
    br,b,bf,bh=snapshot(before);ar,a,af,ah=snapshot(after)
    if (b['targetProfile'],b['namespace'])!=(a['targetProfile'],a['namespace']):
        fail('LINEAGE_MISMATCH',str(ar),'Target profile/namespace must match')
    conflicts=check_content(br,bf);incoming=check_content(ar,af)
    conflicts += [dict(x,reason='incoming-'+x['reason']) for x in incoming]
    ids=identities(ar,a,af);old_ids=identities(br,b,bf)
    entries=[]
    for p in sorted(set(bf)|set(af)):
        old,new=bf.get(p),af.get(p)
        state='added' if old is None else ('removed' if new is None else ('unchanged' if old['sha256']==new['sha256'] else 'changed'))
        if (old and old['owner']=='manual') or (new and new['owner']=='manual'):
            state='manual'
        if old and old['owner']=='retained' and (new is not None and state!='unchanged'):
            conflicts.append(dict(path=p,reason='manual-or-retained-owner',expected=old['sha256'],actual=actual(br,p)))
        if new and new['owner']!='generated' and state in ('added','changed'):
            conflicts.append(dict(path=p,reason='incoming-manual-owner',expected=None,actual=actual(ar,p)))
        if old is None and state!='manual' and actual(br,p) is not None:
            conflicts.append(dict(path=p,reason='untracked-destination',expected=None,actual=actual(br,p)))
        entries.append(dict(path=p,state=state,beforeSha256=old['sha256'] if old else None,afterSha256=new['sha256'] if new else None,
                            **ids.get(p,old_ids.get(p))))
    # Unknown files in generated boundaries are human/engine work, never silently adopted.
    current=standard.current(b)
    if current:prefixes=CURRENT_SCAN[_engine(b['targetProfile'])]
    else:prefixes=('Assets/Generated','Assets/Monkey/Editor','Packages','ProjectSettings','Analysis') if b['targetProfile'].startswith('unity-') else ('assets/generated','extensions/monkey-import','Analysis')
    scanned=[]
    prefixes=tuple(p for p in dict.fromkeys(prefixes) if not any(p!=q and p.startswith(q+'/') for q in prefixes))
    for relative in prefixes:
        folder=inside(br,relative)
        if folder.is_dir():scanned.extend(folder.rglob('*'))
    for p in sorted(scanned):
        if p.is_symlink():fail('SYMLINK_PATH',str(p),'Output contains symbolic link')
        if p.is_file():
            relative=p.relative_to(br).as_posix()
            if relative not in bf and relative!='manifest.json' and managed(b['targetProfile'],relative,current):
                if not any(x['path']==relative for x in conflicts):conflicts.append(dict(path=relative,reason='untracked-generated-file',actual=digest_file(p),expected=None))
    return dict(schemaVersion=1,beforeRoot=str(br),afterRoot=str(ar),beforeManifestSha256=bh,afterManifestSha256=ah,
                targetProfile=a['targetProfile'],namespace=a['namespace'],entries=entries,manualConflicts=conflicts,
                counts={state:sum(e['state']==state for e in entries) for state in ['added','changed','removed','unchanged','manual']})


def diff(before,after,output):
    d=diff_data(before,after);out=new_output(output,[safe(before),safe(after)])
    write_json(out/'diff.json',d)
    return finish(out,dict(toolVersion=__version__,diagnostics=[diagnostic('MANUAL_CONFLICT',x['path'],x['reason']) for x in d['manualConflicts']],**d))


def workspace_paths(workspace):
    workspace=safe(workspace);state=inside(workspace,'.monkey');registry=inside(workspace,'.monkey/outputs.json')
    return workspace,state,registry


def registry_load(workspace):
    ws,state,path=workspace_paths(workspace)
    data=load(read(path)) if path.exists() else dict(schemaVersion=1,workspace=str(ws),outputs={})
    if data.get('schemaVersion')!=1 or data.get('workspace')!=str(ws):fail('REGISTRY_MISMATCH',str(path),'Registry is bound to this workspace')
    return data


def atomic(path,raw):
    path=safe(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=inside(path.parent,'.'+path.name+'.monkey-'+uuid.uuid4().hex+'.tmp')
    try:
        with tmp.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()


@contextmanager
def lock(workspace):
    ws,state,_=workspace_paths(workspace);state.mkdir(exist_ok=True)
    path=inside(state,'update.lock')
    try:stream=path.open('x')
    except FileExistsError:fail('UPDATE_LOCKED',str(path),'Previous update active/interrupted; inspect its journal before recovery')
    stream.write(str(os.getpid()));stream.close()
    try:yield
    finally:path.unlink()


def register(candidate,workspace):
    root,m,files,h=snapshot(candidate);ws,state,registry_path=workspace_paths(workspace)
    allowed=inside(ws,'outputs')
    if root==allowed or not root.is_relative_to(allowed):fail('UNREGISTERED_OUTPUT_ROOT',str(root),'Only this workspace outputs/<candidate> may be enrolled')
    source_map=load(read(find_analysis(root,'source-map.json')))
    roots=m.get('sourceRoots',source_map.get('sourceRoots',{}))
    for src in roots.values():
        source=safe(src)
        if root==source or root.is_relative_to(source) or source.is_relative_to(root):fail('OUTPUT_OVERLAP',str(root),'Candidate overlaps recorded source')
    conflicts=check_content(root,files)
    if conflicts:fail('REGISTRATION_CONFLICT',conflicts[0]['path'],'Generated content changed before enrollment')
    with lock(ws):
        registry=registry_load(ws);existing=registry['outputs'].get(str(root))
        record=dict(targetProfile=m['targetProfile'],namespace=m['namespace'],manifestSha256=h,sourceRoots=roots)
        if existing and existing!=record:fail('REGISTRATION_CONFLICT',str(root),'Registered baseline differs; use controlled apply')
        registry['outputs'][str(root)]=record;atomic(registry_path,encoded(registry))
    return record


def _preview(target,candidate,expected_manifest,workspace):
    root,m,files,h=snapshot(target);ws,state,_=workspace_paths(workspace);registry=registry_load(ws)
    record=registry['outputs'].get(str(root))
    if not record:fail('OUTPUT_NOT_REGISTERED',str(root),'Enroll an unmodified monkey output first')
    if not root.is_relative_to(inside(ws,'outputs')):fail('UNREGISTERED_OUTPUT_ROOT',str(root),'Target escaped registered area')
    if h!=expected_manifest or h!=record['manifestSha256']:fail('EXPECTED_MANIFEST_MISMATCH',str(root),'Expected/current/registered manifest hashes must agree')
    d=diff_data(target,candidate)
    if (record['targetProfile'],record['namespace'])!=(d['targetProfile'],d['namespace']):fail('REGISTRY_MISMATCH',str(root),'Target lineage differs')
    incoming=snapshot(candidate)[0]
    if incoming==root or incoming.is_relative_to(root) or root.is_relative_to(incoming):fail('OUTPUT_OVERLAP',str(incoming),'Incoming candidate overlaps target')
    incoming_map=load(read(find_analysis(incoming,'source-map.json')))
    for src in list(record['sourceRoots'].values())+list(incoming_map.get('sourceRoots',{}).values()):
        source=safe(src)
        if root==source or root.is_relative_to(source) or source.is_relative_to(root):fail('OUTPUT_OVERLAP',str(root),'Registered target now overlaps source')
    return dict(d,registrationSha256=sha(encoded(record)),application='blocked' if d['manualConflicts'] else 'dry-run',
                removalsPolicy='retain-with-recorded-hash',writePaths=[e['path'] for e in d['entries'] if e['state'] in ('added','changed')],
                retainedPaths=[e['path'] for e in d['entries'] if e['state']=='removed'])


def apply(target,candidate,expected_manifest,output,workspace,write=False,preview_path=None):
    """Dry-run first. --write requires its unchanged, stage-hashed preview receipt."""
    d=_preview(target,candidate,expected_manifest,workspace)
    if write:
        if preview_path is None:fail('PREVIEW_REQUIRED',str(target),'Write requires a prior apply dry-run receipt')
        preview=stage_document(preview_path)
        if preview!=d or preview.get('application')!='dry-run':fail('PREVIEW_STALE',str(preview_path),'Inputs/ownership changed since dry-run')
        if d['manualConflicts']:fail('MANUAL_CONFLICT',str(target),'Resolve conflicts before apply')
    out=new_output(output,[safe(target),safe(candidate)])
    diagnostics=[diagnostic('MANUAL_CONFLICT',x['path'],x['reason']) for x in d['manualConflicts']]
    if write:
        root,m,bf,bh=snapshot(target);incoming,a,af,ah=snapshot(candidate);ws,state,registry_path=workspace_paths(workspace)
        with lock(ws):
            if _preview(target,candidate,expected_manifest,workspace)!=d:fail('PREVIEW_STALE',str(target),'Target changed before acquiring update lock')
            transaction=inside(state,'transactions/'+uuid.uuid4().hex);transaction.mkdir(parents=True)
            changes=[p for p in d['writePaths'] if p in af]
            # Every prior file stays recoverable; removed files remain at their original paths.
            backups={p:(bf[p] if p in bf else None) for p in changes}
            before_manifest=read(root/'manifest.json',max_bytes=MANIFEST_BYTES);before_registry=read(registry_path)
            for p,raw in backups.items():
                if raw is not None:
                    dest=inside(transaction,'before/'+p)
                    copy_verified(inside(root,p),dest,raw['sha256'],raw['bytes'])
            (transaction/'before-manifest.json').write_bytes(before_manifest)
            (transaction/'before-registry.json').write_bytes(before_registry)
            merged=dict(a);merged.pop('_manifestName',None)
            merged['files']=[dict(f,owner=bf[p]['owner']) if p in bf and bf[p]['owner']!='generated' else dict(f) for p,f in af.items() if f['owner']!='manual' and not (p in bf and bf[p]['owner']=='manual')]
            merged['files'] += [dict(f) for f in bf.values() if f['owner']=='manual']
            merged['files'] += [dict(bf[p],owner='manual' if bf[p]['owner']=='manual' else 'retained') for p in d['retainedPaths']]
            merged['files']=sorted(merged['files'],key=lambda f:f['path'])
            merged['appliedFromManifestSha256']=bh;merged['desiredManifestSha256']=ah
            merged['retainedRemovedPaths']=d['retainedPaths'];after_manifest=encoded(merged)
            journal=dict(schemaVersion=1,target=str(root),candidate=str(incoming),state='prepared',beforeManifestSha256=bh,
                         desiredManifestSha256=ah,afterManifestSha256=sha(after_manifest),changed=changes,
                         added=[p for p,v in backups.items() if v is None],written=[],retainedPaths=d['retainedPaths'])
            write_json(transaction/'journal.json',journal)
            try:
                journal['state']='committing';write_json(transaction/'journal.json',journal)
                for p in changes:
                    if actual(root,p)!=(bf[p]['sha256'] if p in bf else None):fail('TARGET_DRIFT',p,'Target changed during apply')
                    journal['written'].append(p);write_json(transaction/'journal.json',journal)
                    copy_verified(inside(incoming,p),inside(root,p),af[p]['sha256'],af[p]['bytes'])
                if sha(read(root/'manifest.json',max_bytes=MANIFEST_BYTES))!=bh:fail('TARGET_DRIFT','manifest.json','Manifest changed during apply')
                for f in merged['files']:
                    if f['owner']!='manual' and actual(root,f['path'])!=f['sha256']:fail('TARGET_DRIFT',f['path'],'Final content differs before manifest adoption')
                atomic(root/'manifest.json',after_manifest)
                registry=registry_load(ws);registry['outputs'][str(root)]['manifestSha256']=sha(after_manifest)
                atomic(registry_path,encoded(registry));journal['state']='complete';write_json(transaction/'journal.json',journal)
            except Exception:
                recovery=[]
                for p in reversed(journal['written']):
                    current_file=actual(root,p)
                    if current_file==(backups[p]['sha256'] if backups[p] is not None else None):continue
                    if current_file!=af[p]['sha256']:recovery.append(p);continue
                    if backups[p] is None:inside(root,p).unlink()
                    else:copy_verified(inside(transaction,'before/'+p),inside(root,p),backups[p]['sha256'],backups[p]['bytes'])
                current=sha(read(root/'manifest.json',max_bytes=MANIFEST_BYTES))
                if current==sha(after_manifest):atomic(root/'manifest.json',before_manifest)
                elif current!=bh:recovery.append('manifest.json')
                # Registry changes are restored only if this transaction wrote its baseline.
                reg=registry_load(ws)
                if reg['outputs'].get(str(root),{}).get('manifestSha256')==sha(after_manifest):atomic(registry_path,before_registry)
                journal.update(state='recovery-required' if recovery else 'rolled-back',recoveryPaths=recovery);write_json(transaction/'journal.json',journal)
                raise
            d.update(application='applied',appliedManifestSha256=sha(after_manifest),transaction=str(transaction))
    write_json(out/'application.json',d)
    return finish(out,dict(schemaVersion=1,toolVersion=__version__,diagnostics=diagnostics,application=d['application'],
                           appliedManifestSha256=d.get('appliedManifestSha256'),retainedPaths=d['retainedPaths']))
