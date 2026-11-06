"""Capture only exact serialized texture keys under a literal declared DATA_CDN.

Downloads are TLS/CDN asset reads, never gameplay requests or source execution.
New byte hashes are recorded after capture, not invented as preexisting checksums.
"""
import concurrent.futures
import hashlib
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from .unity_parse_limits import MAX_DOCUMENT_NODES
from .io import safe,inside,read,load,sha,write_json,new_output
from .sources.compiled import fail
from .sources.unity_worker import astc_header


def requests(inspection):
    root=safe(inspection);batch=load(read(root/'BatchInspection/batch.json',max_bytes=128*1024**2),max_nodes=MAX_DOCUMENT_NODES,max_depth=128);wanted={}
    for row in batch['files']:
        receipt=row['receipt'];stage=Path(row['inspection']);raw=read(stage/'typed-objects.json',max_bytes=128*1024**2)
        if sha(raw)!=receipt['typedObjectsSha256']:fail('UNITY_TEXTURE_TYPED_CHANGED',str(stage),'Frozen typed shard changed')
        data=load(raw,max_nodes=MAX_DOCUMENT_NODES,max_depth=128);files={f['id']:f['name']for f in data['files']}
        for obj in data['objects']:
            token=obj.get('texturePayload',{})
            if token.get('kind')!='external-key-token-candidate':continue
            d=obj['data'];width,height=d['m_Width'],d['m_Height'];logical='Assets/Textures/astc/'+str(max(width,height))+'/'+token['key']+'.txt'
            if any(x in ('','.','..')for x in logical.split('/')):fail('UNITY_TEXTURE_KEY',logical,'Unsafe source key')
            identity=dict(width=width,height=height,blockSizeHint=token.get('blockSizeHint'))
            entry=wanted.setdefault(logical,dict(logicalPath=logical,**identity,sources=[]))
            if any(entry[k]!=identity[k]for k in identity):fail('UNITY_TEXTURE_KEY_CONFLICT',logical,'Same logical key has differing source dimensions/block hints')
            entry['sources'].append(dict(containerSha256=receipt['source']['sha256'],file=files[obj['file']],pathId=obj['pathId'],rawSha256=obj['rawSha256']))
    return wanted


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None


def acquire(inspection,cache_manifest,cdn_source,cdn_root,output,cache_root=None,budget=1200,workers=8,resume=False):
    if not 30<=budget<=1500 or not 1<=workers<=8:fail('UNITY_TEXTURE_CAPTURE_BUDGET','$','Expected30..1500 seconds and1..8 workers')
    inspection=safe(inspection);manifest=safe(cache_manifest);source=safe(cdn_source);source_raw=read(source,max_bytes=32*1024**2)
    parsed=urllib.parse.urlsplit(cdn_root)
    if parsed.scheme!='https'or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or not cdn_root.endswith('/'):
        fail('UNITY_TEXTURE_CDN',cdn_root,'Explicit HTTPS directory root required')
    pattern=rb'\bDATA_CDN\s*[:=]\s*([\x22\x27])'+re.escape(cdn_root.encode())+rb'\1'
    if not re.search(pattern,source_raw):fail('UNITY_TEXTURE_CDN_SOURCE',str(source),'Root must be a literal DATA_CDN in the explicit original source')
    wanted=requests(inspection);base=load(read(manifest));cache={};declared=[]
    if base.get('schemaVersion')!=1:fail('UNITY_TEXTURE_POOL',str(manifest),'Expected frozen texture pool')
    for row in base['files']:
        path=safe(manifest.parent/row['path']);raw=read(path,max_bytes=128*1024**2)
        if len(raw)!=row['bytes']or sha(raw)!=row['sha256']:fail('UNITY_TEXTURE_CACHE_CHANGED',str(path),'Known frozen texture bytes changed')
        entry=dict(row,path=str(path));cache[row['logicalPath']]=entry;declared.append(entry)
    root=safe(cache_root)if cache_root else None
    definition=dict(schemaVersion=1,inspectionManifestSha256=sha(read(inspection/'all-inputs.json')),cacheManifestSha256=sha(read(manifest)),
                    cdnSourceSha256=sha(source_raw),cdnRoot=cdn_root,keys={k:{x:v for x,v in row.items()if x!='sources'}for k,row in wanted.items()})
    out=safe(output)
    if resume:
        if load(read(out/'capture-job.json'))!=definition:fail('UNITY_TEXTURE_CAPTURE_DRIFT',str(out),'Resume requires exact unchanged source/key set')
    else:
        out=new_output(out,[inspection,manifest,source,*([root]if root else [])]);write_json(out/'capture-job.json',definition)
    ledger=out/'capture.jsonl';results={}
    if resume and ledger.exists():
        for line in ledger.read_text().splitlines():
            row=json.loads(line);results[row['logicalPath']]=row
    opener=urllib.request.build_opener(urllib.request.ProxyHandler(),NoRedirect())
    # Establish the exact CDN namespace by matching one already frozen payload.
    probe=next((v for k,v in cache.items()if k in wanted),None)
    if not probe:fail('UNITY_TEXTURE_CDN_PROOF','$','At least one known source-key cache payload required')
    if not (out/'cdn-proof.json').exists():
        url=cdn_root+urllib.parse.quote(probe['logicalPath'],safe='/%')
        with opener.open(urllib.request.Request(url,headers={'User-Agent':'monkey-source-capture/1'}),timeout=20)as response:raw=response.read(probe['bytes']+1)
        if sha(raw)!=probe['sha256']or len(raw)!=probe['bytes']:fail('UNITY_TEXTURE_CDN_PROOF',url,'Known frozen bytes do not match the literal CDN namespace')
        write_json(out/'cdn-proof.json',dict(url=url,bytes=len(raw),sha256=sha(raw),sameAsFrozen=True,sourceSha256=sha(source_raw)))
    deadline=time.monotonic()+budget;total=[0];stop=threading.Event()
    def task(item):
        logical,spec=item
        if stop.is_set()or time.monotonic()>=deadline:return dict(logicalPath=logical,status='deferred',reason='bounded-stage-deadline')
        try:
            known=cache.get(logical)
            if known:path=Path(known['path']);raw=read(path,max_bytes=128*1024**2);origin='frozen-cache'
            elif root and inside(root,logical).is_file():path=inside(root,logical);raw=read(path,max_bytes=128*1024**2);origin='exact-key-local-cache'
            else:
                path=inside(out/'Files',logical);path.parent.mkdir(parents=True,exist_ok=True);url=cdn_root+urllib.parse.quote(logical,safe='/%')
                remaining=max(.1,min(20,deadline-time.monotonic()))
                with opener.open(urllib.request.Request(url,headers={'User-Agent':'monkey-source-capture/1'}),timeout=remaining)as response:
                    if response.status!=200:raise ValueError('Unexpected CDN HTTP status')
                    chunks=[];size=0
                    while True:
                        if time.monotonic()>=deadline:raise TimeoutError('bounded stage deadline')
                        part=response.read(64*1024)
                        if not part:break
                        size+=len(part)
                        if size>128*1024**2:raise ValueError('Texture byte budget')
                        chunks.append(part)
                    raw=b''.join(chunks)
                path.write_bytes(raw);origin='exact-declared-CDN-key'
            header=astc_header(raw,spec['width'],spec['height'],spec.get('blockSizeHint'))
            return dict(logicalPath=logical,status='captured',path=str(path),bytes=len(raw),sha256=sha(raw),origin=origin,astc=header,
                        sourceReference='literal DATA_CDN + exact serialized texture key',remoteHash='recorded-after-capture')
        except Exception as error:
            return dict(logicalPath=logical,status='deferred'if time.monotonic()>=deadline else'failed',reason=type(error).__name__+': '+str(error)[:240])
    pending=[]
    for key,spec in wanted.items():
        old=results.get(key)
        if old and old.get('status')=='captured':
            path=safe(old['path']);raw=read(path,max_bytes=128*1024**2)
            if sha(raw)!=old['sha256']or len(raw)!=old['bytes']:fail('UNITY_TEXTURE_CAPTURE_CHANGED',str(path),'Captured bytes changed')
        elif not old or old.get('status')=='deferred':pending.append((key,spec))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers)as executor:
        futures=[executor.submit(task,item)for item in pending]
        for future in concurrent.futures.as_completed(futures):
            row=future.result();results[row['logicalPath']]=row
            with ledger.open('a')as stream:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
            total[0]+=row.get('bytes',0)
            if total[0]>8*1024**3:stop.set()
            if len(results)%32==0:write_json(out/'progress.json',dict(processed=len(results),total=len(wanted),captured=sum(r['status']=='captured'for r in results.values()),stageDeadlineReached=time.monotonic()>=deadline))
    pool={r['logicalPath']:r for r in declared}
    for key,row in results.items():
        if row['status']=='captured':pool[key]={k:row[k]for k in ('logicalPath','path','bytes','sha256')}
    write_json(out/'textures.json',dict(schemaVersion=1,files=list(pool.values())))
    failed=[dict(logicalPath=k,**{x:v for x,v in r.items()if x!='logicalPath'})for k,r in results.items()if r['status']!='captured']
    report=dict(schemaVersion=1,status='captured'if not failed and len(results)==len(wanted)else'partial',requestedKeys=len(wanted),capturedKeys=sum(r['status']=='captured'for r in results.values()),
                poolEntries=len(pool),failures=failed,sourceCodeExecuted=False,gameplayRequests=False,cdnSourceSha256=sha(source_raw),cdnRoot=cdn_root,
                sourceReferenceHash='exact keys and namespace; new payload SHA256 recorded after capture, not a guessed source checksum')
    write_json(out/'capture.json',report);return {k:v for k,v in report.items()if k!='failures'}
