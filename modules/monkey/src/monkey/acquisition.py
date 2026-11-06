"""Bounded acquisition of explicitly declared CDN files; never executes them."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request
from urllib.error import HTTPError
import hashlib
import json
import os
import re
import time

from .io import safe, inside, read, load, write_json, new_output, sha, stage_manifest
from .inputs import input_set
from .sources.containers import relative, fingerprint, MAX_FILE
from .sources.compiled import fail
from .layout.standard import find_analysis

MAX_TOTAL=1024*1024*1024


def origin(url):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.fragment:
        fail('REMOTE_URL_INVALID','remote manifest','Expected explicit HTTP(S) URL without credentials or fragment')
    return p.scheme+'://'+p.netloc.lower()


def prepare(manifest,output,selection,cache_root=None,budget_seconds=900,protected_roots=(),derive_input_set=True,resume_from=None,max_attempts=3):
    if type(budget_seconds) is not int or not 30<=budget_seconds<=3600:
        fail('REMOTE_BUDGET','remote manifest','Expected a 30..3600 second acquisition window')
    if type(max_attempts) is not int or not 1<=max_attempts<=3:fail('REMOTE_ATTEMPTS','remote manifest','Expected 1..3 attempts')
    manifest=safe(manifest);raw=read(manifest);data=load(raw)
    rows=data if isinstance(data,list) else data.get('files') if isinstance(data,dict) and data.get('schemaVersion')==1 else None
    if not isinstance(rows,list) or not 1<=len(rows)<=50000:
        fail('REMOTE_MANIFEST_SCHEMA',str(manifest),'Expected 1..50000 declared file entries')
    cache=safe(cache_root) if cache_root else None
    if cache and not cache.is_dir():fail('REMOTE_CACHE_MISSING',str(cache),'Expected a local cache directory')
    entries=[];paths=set();origins=set()
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('url'),str):fail('REMOTE_MANIFEST_SCHEMA','files','Expected file objects with url/path')
        path=relative(row.get('path',''));key=path.casefold()
        if key in paths:fail('REMOTE_PATH_COLLISION',path,'Repeated destination path')
        paths.add(key);origins.add(origin(row['url']))
        expected=row.get('sha256');size=row.get('bytes')
        if expected is not None and (not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected)):
            fail('REMOTE_IDENTITY_INVALID',path,'Expected lowercase SHA256')
        if size is not None and (type(size) is not int or not 0<=size<=MAX_FILE):fail('REMOTE_FILE_BUDGET',path,'Invalid expected byte count')
        entries.append(dict(path=path,url=row['url'],sha256=expected,bytes=size))
    for entry in entries:
        if any(p.as_posix().casefold() in paths for p in Path(entry['path']).parents if p.as_posix()!='.'):
            fail('REMOTE_PATH_COLLISION',entry['path'],'A destination file is also another file parent')
    if len(origins)>32:fail('REMOTE_ORIGIN_BUDGET','remote manifest','At most 32 explicit origins')
    previous=safe(resume_from) if resume_from else None;reused={};previous_sha=None
    if previous:
        receipt_path=previous/'acquisition.json';previous_raw=read(receipt_path);prior=load(previous_raw);previous_sha=sha(previous_raw)
        source_key='sourceInputSetSha256' if derive_input_set else 'sourceSelectionSha256'
        if prior.get('schemaVersion')!=1 or prior.get('sourceManifestSha256')!=sha(raw) or prior.get(source_key)!=selection['sha256']:
            fail('REMOTE_RESUME_IDENTITY',str(previous),'Exact remote manifest and input selection required')
        by_path={r['path']:r for r in entries};seen=set()
        for row in prior.get('files',[]):
            path=row.get('path');item=by_path.get(path)
            if item is None or path in seen or row.get('sourceKey')!=sha(item['url'].encode()):
                fail('REMOTE_RESUME_IDENTITY',str(path),'Unknown, duplicate or changed source key')
            seen.add(path)
            if row.get('status') not in ('local_verified','downloaded','reused_verified') or row.get('includedByOriginalRoot'):continue
            digest=row.get('sha256');size=row.get('bytes')
            if (not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest) or type(size) is not int or not 0<=size<=MAX_FILE or
                    (item['sha256'] is not None and item['sha256']!=digest) or (item['bytes'] is not None and item['bytes']!=size)):
                fail('REMOTE_RESUME_IDENTITY',path,'Prior content receipt differs from declared identity')
            payload=inside(previous/'files',path)
            if not payload.is_file() or payload.stat().st_size!=size or fingerprint(payload)!=digest:
                fail('REMOTE_RESUME_CHANGED',path,'Previously acquired bytes changed; preserve the old layer')
            reused[path]=dict(path=payload,sha256=digest,bytes=size)
        if seen!=set(by_path):fail('REMOTE_RESUME_IDENTITY',str(previous),'Previous receipt does not cover this exact request set')
    destination=safe(output);protected=[manifest,*[r['path'] for r in selection['inputs']],*map(safe,protected_roots)]+([cache] if cache else [])+([previous] if previous else [])
    if destination.exists() or any(destination==r or destination.is_relative_to(r) or r.is_relative_to(destination) for r in protected):
        fail('REMOTE_OUTPUT_CONFLICT',str(destination),'Choose a fresh acquisition directory outside source roots')
    return dict(manifest=manifest,manifestSha256=sha(raw),output=destination,selection=selection,cache=cache,
                entries=entries,origins=origins,budget=budget_seconds,deriveInputSet=derive_input_set,resume=reused,
                resumeFrom=previous,resumeReceiptSha256=previous_sha,maxAttempts=max_attempts)


def acquire(settings,offline=False):
    roots=[r['path'] for r in settings['selection']['inputs']]
    out=new_output(settings['output'],[settings['manifest'],*roots,*([settings['resumeFrom']] if settings.get('resumeFrom') else [])]);fetched=out/'files';fetched.mkdir();temporary_root=out/'Temporary';temporary_root.mkdir()
    lock=Lock();used=0;deadline=time.monotonic()+settings['budget']-20
    def reserve(count):
        nonlocal used
        with lock:
            if used+count>MAX_TOTAL:raise ValueError('REMOTE_TOTAL_BYTE_BUDGET')
            used+=count
    class Redirects(HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if origin(newurl) not in settings['origins']:raise ValueError('REMOTE_REDIRECT_ORIGIN')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    def attempt(item,number):
        row=dict(path=item['path'],sourceKey=sha(item['url'].encode()),origin=origin(item['url']),
                 expectedSha256=item['sha256'],expectedBytes=item['bytes'],attempts=number,
                 identityAssurance='declared-sha256' if item['sha256'] else 'captured-bytes-without-declared-hash')
        temporary=None
        try:
            if time.monotonic()>=deadline:raise TimeoutError('REMOTE_DEADLINE')
            prior=settings.get('resume',{}).get(item['path']);local=prior['path'] if prior else None
            candidates=[inside(settings['cache'],item['path'])] if settings['cache'] else [inside(r,item['path']) for r in roots if r.is_dir()]
            if local is None and item['sha256']:
                for candidate in candidates:
                    if candidate.is_file() and candidate.stat().st_size<=MAX_FILE and (item['bytes'] is None or candidate.stat().st_size==item['bytes']) and fingerprint(candidate)==item['sha256']:
                        local=candidate;break
            covered=local is not None and any(local.is_relative_to(r) for r in roots if r.is_dir())
            if covered:
                reserve(local.stat().st_size)
                return dict(row,status='local_verified',bytes=local.stat().st_size,sha256=item['sha256'],includedByOriginalRoot=True)
            if local is None and offline:return dict(row,status='unavailable_offline')
            target=inside(fetched,item['path']);target.parent.mkdir(parents=True,exist_ok=True)
            temporary=temporary_root/sha(item['path'].encode())
            digest=hashlib.sha256();count=0
            if local is not None:stream=local.open('rb')
            else:
                stream=build_opener(Redirects()).open(Request(item['url'],headers={'User-Agent':'MonkeyResourceArchive/0.3'}),timeout=min(20,max(.1,deadline-time.monotonic())))
                if getattr(stream,'status',200)!=200:raise ValueError('REMOTE_HTTP_STATUS')
            with stream,temporary.open('xb') as writer:
                while True:
                    if time.monotonic()>=deadline:raise TimeoutError('REMOTE_DEADLINE')
                    block=stream.read(65536)
                    if not block:break
                    count+=len(block)
                    if count>MAX_FILE:raise ValueError('REMOTE_SINGLE_BYTE_BUDGET')
                    reserve(len(block));digest.update(block);writer.write(block)
            actual=digest.hexdigest()
            if (item['sha256'] and actual!=item['sha256']) or (item['bytes'] is not None and count!=item['bytes']) or (prior and (actual!=prior['sha256'] or count!=prior['bytes'])):
                quarantine=out/'Quarantine'/sha(item['path'].encode());quarantine.parent.mkdir(exist_ok=True);os.link(temporary,quarantine);temporary.unlink();temporary=None
                return dict(row,status='identity_mismatch',sha256=actual,bytes=count,quarantine=quarantine.relative_to(out).as_posix())
            os.link(temporary,target);temporary.unlink();temporary=None
            return dict(row,status='reused_verified' if prior else 'local_verified' if local else 'downloaded',sha256=actual,bytes=count,includedByOriginalRoot=False)
        except HTTPError as error:
            error.close();return dict(row,status='unavailable',httpStatus=error.code)
        except Exception as error:
            code=str(error) if re.fullmatch('REMOTE_[A-Z_]+',str(error)) else None
            return dict(row,status='failed',errorType=type(error).__name__,errorCode=code)
        finally:
            if temporary is not None and temporary.exists():temporary.unlink()
    def one(item):
        for number in range(1,settings.get('maxAttempts',3)+1):
            row=attempt(item,number)
            transient=(row.get('httpStatus') in (408,429,500,502,503,504) or row.get('errorType') in ('URLError','TimeoutError','ConnectionResetError','IncompleteRead'))
            if not transient or number==settings.get('maxAttempts',3) or time.monotonic()+.5>=deadline:return row
            time.sleep(min(.25*number,max(0,deadline-time.monotonic())))
    with ThreadPoolExecutor(max_workers=4) as executor:rows=list(executor.map(one,settings['entries']))
    available=[r for r in rows if r['status'] in ('local_verified','downloaded','reused_verified')]
    summary=dict(requestedFiles=len(rows),availableFiles=len(available),missingFiles=len(rows)-len(available),
                 downloadedFiles=sum(r['status']=='downloaded' for r in rows),localVerifiedFiles=sum(r['status']=='local_verified' for r in rows),
                 reusedVerifiedFiles=sum(r['status']=='reused_verified' for r in rows),attemptedBytes=used,
                 accountedBytes=sum(r['bytes'] for r in available),offline=offline,allDeclaredAvailable=len(available)==len(rows))
    receipt=dict(schemaVersion=1,sourceManifestSha256=settings['manifestSha256'],sourceInputSetSha256=settings['selection']['sha256'],
                 status='complete' if summary['allDeclaredAvailable'] else 'partial',summary=summary,files=rows,
                 resumeReceiptSha256=settings.get('resumeReceiptSha256'),maxAttempts=settings.get('maxAttempts',3))
    write_json(out/'acquisition.json',receipt)
    selected=settings['selection'];derived=selected['path']
    if not settings.get('deriveInputSet',True):
        receipt.pop('sourceInputSetSha256')
        receipt.update(sourceSelectionSha256=selected['sha256'],sourceSelectionKind='unity-container')
        write_json(out/'acquisition.json',receipt)
        return dict(receipt=out/'acquisition.json',summary=summary,filesRoot=fetched)
    materialized=[r for r in available if not r['includedByOriginalRoot']]
    if materialized:
        entries=[]
        for unit in selected['inputs']:
            entry=dict(id=unit['id'],path=str(unit['path']))
            for key in ('config','cacheList'):
                if unit[key] is not None:entry[key]=unit[key].relative_to(unit['path']).as_posix()
            if unit['cacheList'] is not None:entry['cacheKind']=unit['cacheKind']
            entries.append(entry)
        if len(entries)>=16:fail('INPUT_ROOT_BUDGET','acquisition','No room for a separate acquired root')
        name='acquired'
        while any(r['id'].casefold()==name for r in entries):name+='-remote'
        entries.append(dict(id=name,path=str(fetched)))
        derived=out/'input-set.json'
        write_json(derived,dict(schemaVersion=1,sourceProfile=selected['sourceProfile'],game=selected['identity'],inputs=entries,
                               limits=dict(maxInputBytes=selected['maxInputBytes'])))
        input_set(derived)
    return dict(inputSet=derived,receipt=out/'acquisition.json',summary=summary)


def attach(conversion,output,acquired):
    """Finalize only a freshly generated candidate before publishing its hashes."""
    if not conversion.get('completed'):return
    root=safe(output);record=root/'conversion-result.json'
    if load(read(record))!=conversion:fail('REMOTE_CONVERSION_CHANGED',str(root),'Fresh generation receipt differs')
    original=fingerprint(record);receipt=load(read(acquired['receipt']))
    for row in conversion['projects']:
        project=root/row['path'];manifest=project/'manifest.json'
        if fingerprint(manifest)!=row['manifestSha256']:fail('REMOTE_CONVERSION_CHANGED',str(project),'Candidate identity differs')
        data=stage_manifest(project);expected={f['path'] for f in data['files']}
        actual={p.relative_to(project).as_posix() for p in project.rglob('*') if p.is_file() and p!=manifest}
        if actual!=expected:fail('REMOTE_CONVERSION_CHANGED',str(project),'Unknown generated files')
        for item in data['files']:
            if fingerprint(inside(project,item['path']))!=item['sha256']:fail('REMOTE_CONVERSION_CHANGED',item['path'],'Generated content changed')
        target=find_analysis(project,'acquisition.json')
        if target.exists():fail('REMOTE_CONVERSION_CHANGED',str(target),'Acquisition evidence already exists')
        write_json(target,dict(receipt,preAcquisitionConversionSha256=original))
        data['files'].append(dict(path='Analysis/Ledger/acquisition.json',sha256=fingerprint(target),bytes=target.stat().st_size,owner='generated'))
        data['acquisition']=acquired['summary'];write_json(manifest,data);row['manifestSha256']=fingerprint(manifest)
    conversion['acquisition']=acquired['summary'];write_json(record,conversion)
