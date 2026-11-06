"""Owned batch preparation worker. Original containers/code are never written/executed."""
import hashlib,json,sys,time
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from monkey.sources.unity_worker import digest,identifier,texture_payload,astc_header,PROVIDER_VERSION,MAX_BYTES


def checked(row):
    path=Path(row['path']);raw=path.read_bytes()
    if len(raw)!=row['bytes']or len(raw)>MAX_BYTES or digest(raw)!=row['sha256']:raise ValueError('Frozen source/cache changed: '+str(path))
    return raw


def objects(env):
    result={}
    for a in env.assets:
        for o in a.objects.values():
            key=(a.name,identifier(o.path_id))
            if key in result:raise ValueError('Duplicate serialized file/object identity')
            result[key]=(o.type.name,digest(o.get_raw_data()))
    return result


def one(row,pool,missing,dest):
    import UnityPy,texture2ddecoder
    raw=checked(row);env=UnityPy.load(raw);before=objects(env);modified={};removed=[];resolved=[]
    for asset in env.assets:
        if not asset.unity_version.startswith('2021.3.'):raise ValueError('Only proven Unity2021.3 texture token profile supported')
        for obj in list(asset.objects.values()):
            if obj.type.name!='Texture2D':continue
            typed=obj.read_typetree(check_read=True);token=texture_payload(typed)
            if token['kind']=='invalid-inline-etc1':raise ValueError('Undeclared invalid inline texture; explicit new policy required')
            if token['kind']!='external-key-token-candidate':continue
            if typed.get('m_MipCount')!=1 or typed.get('m_ImageCount')!=1:raise ValueError('Only original single-mip2D texture hydration supported')
            logical='Assets/Textures/astc/'+str(max(typed['m_Width'],typed['m_Height']))+'/'+token['key']+'.txt';key=(asset.name,identifier(obj.path_id))
            if logical not in pool:
                if logical not in missing:raise ValueError('Unaccounted source texture key: '+logical)
                removed.append(dict(file=key[0],pathId=key[1],name=typed.get('m_Name'),logicalPath=logical,rawObjectSha256=before[key][1],reason='exact-source-key-HTTP404',references='unresolved-not-replaced'))
                del asset.objects[obj.path_id];continue
            item=pool[logical];cached=checked(item);header=astc_header(cached,typed['m_Width'],typed['m_Height'],token.get('blockSizeHint'))
            decoded=texture2ddecoder.decode_astc(cached[16:],header['width'],header['height'],header['block'],header['block'])
            if len(decoded)!=header['width']*header['height']*4:raise ValueError('Decoded pixel dimensions differ')
            rgba=bytearray(len(decoded));rgba[0::4]=decoded[2::4];rgba[1::4]=decoded[1::4];rgba[2::4]=decoded[0::4];rgba[3::4]=decoded[3::4]
            typed['image data']=bytes(rgba);typed['m_CompleteImageSize']=len(rgba);typed['m_TextureFormat']=4
            obj.save_typetree(typed);modified[key]=digest(rgba)
            resolved.append(dict(file=key[0],pathId=key[1],logicalPath=logical,cacheSha256=item['sha256'],cacheBytes=item['bytes'],rgbaRawSha256=digest(rgba),astc=header))
    encoded=env.file.save(packer='none'if raw.startswith(b'UnityWebData1.0\0')else'lz4')
    if len(encoded)>MAX_BYTES:raise ValueError('Derived container exceeds128MiB')
    check=UnityPy.load(encoded);after=objects(check);excluded={(r['file'],r['pathId'])for r in removed}
    if set(after)!=set(before)-excluded or any(after[k]!=v for k,v in before.items()if k not in excluded and k not in modified):raise ValueError('Retained non-texture object changed')
    for a in check.assets:
        for o in a.objects.values():
            key=(a.name,identifier(o.path_id))
            if key in modified:
                typed=o.read_typetree(check_read=True)
                if texture_payload(typed)['kind']!='inline-payload'or digest(bytes(typed['image data']))!=modified[key]:raise ValueError('Hydrated pixels did not roundtrip')
    checked(row);dest.parent.mkdir(exist_ok=True);temporary=dest.with_suffix(dest.suffix+'.partial');temporary.write_bytes(encoded);temporary.replace(dest)
    return dict(index=row['index'],source=row,derived=str(dest),derivedSha256=digest(encoded),derivedBytes=len(encoded),resolved=resolved,removed=removed,retainedNonTextureObjectsUnchanged=True,pixelsFabricated=False,status='prepared')


def run(job_path,budget):
    from importlib.metadata import version
    import UnityPy
    if UnityPy.__version__!=PROVIDER_VERSION or version('texture2ddecoder')!='1.0.6':raise RuntimeError('Pinned UnityPy1.25.3/texture2ddecoder1.0.6 required')
    root=job_path.parent;job=json.loads(job_path.read_text());deadline=time.monotonic()+budget
    pool={r['logicalPath']:r for r in job['cache']};missing=set(job['missingKeys']);ledger=root/'prepared.jsonl';done={}
    # Validate all acquired bytes once per bounded run; object use is also pinned.
    for row in pool.values():checked(row)
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            row=json.loads(line);idx=row['index'];expected=job['sources'][idx]
            if row['source']!=expected or idx in done:raise ValueError('Resume source/row identity changed')
            checked(expected)
            if row.get('derived')and digest(Path(row['derived']).read_bytes())!=row['derivedSha256']:raise ValueError('Completed derived container changed')
            done[idx]=row
    for row in job['sources']:
        if row['index']in done:continue
        if time.monotonic()>=deadline:break
        if row.get('invalidInline'):raise ValueError('Invalid inline texture requires explicit distinct policy')
        if row['needsTextures']:result=one(row,pool,missing,root/'containers'/Path(row['path']).name)
        else:checked(row);result=dict(index=row['index'],source=row,derived=None,status='source-reused')
        done[row['index']]=result
        with ledger.open('a')as log:log.write(json.dumps(result,ensure_ascii=False)+'\n');log.flush()
        if len(done)%20==0:(root/'progress.json').write_text(json.dumps(dict(prepared=len(done),containers=len(job['sources'])))+'\n')
    body=dict(schemaVersion=1,status='prepared'if len(done)==len(job['sources'])else'partial',jobSha256=digest(job_path.read_bytes()),containers=len(job['sources']),prepared=len(done),hydratedTextures=sum(len(r.get('resolved',[]))for r in done.values()),missingTextureObjects=sum(len(r.get('removed',[]))for r in done.values()),rows=[done[i]for i in sorted(done)],pixelsFabricated=False,sourceCodeExecuted=False,providerExport='not_run')
    (root/'prepared.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':run(Path(sys.argv[1]),int(sys.argv[2]))
