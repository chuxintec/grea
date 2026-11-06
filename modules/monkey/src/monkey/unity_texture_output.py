"""Keep exact hydrated Texture2D pixels when a provider selects lossy JPEG output."""
from io import BytesIO
from pathlib import Path
from PIL import Image
from .io import read,load,sha,inside,write_json
from .layout.standard import find_analysis
from .normalize import open_texture
from .sources.compiled import fail


def lossless_textures(project):
    root=Path(project)
    resources=load(read(find_analysis(root,'full-resource-handoff.json'),max_bytes=128*1024**2),max_nodes=16_000_000)
    hydration=load(read(find_analysis(root,'texture-hydration.json'),max_bytes=128*1024**2),max_nodes=16_000_000)
    hydrated={}
    for row in hydration['consumed']:
        hydrated.setdefault((row['file'],row['pathId']),[]).append(row)
    targets={}
    for row in resources['sourceToTarget']:
        target=row.get('target')
        if target and Path(target['path']).suffix.lower() in ('.jpg','.jpeg'):
            targets.setdefault(target['path'],[]).append(row)
    normalized=[];pending=[]
    for relative,rows in sorted(targets.items()):
        sources={(r['source']['file'],r['source']['pathId'],r['source']['fileId']) for r in rows}
        if len(sources)!=1:
            pending.append(dict(path=relative,reason='ambiguous-source-identity'));continue
        file,path_id,file_id=next(iter(sources));matches=hydrated.get((file,path_id),[])
        if file_id!='0' or len(matches)!=1:
            pending.append(dict(path=relative,reason='exact-local-hydration-proof-unavailable'));continue
        proof=matches[0];cache=inside(root,'SourceRecovery/TextureCache/'+proof['logicalPath']);raw=read(cache,max_bytes=128*1024**2)
        if len(raw)!=proof['cacheBytes'] or sha(raw)!=proof['cacheSha256']:
            fail('UNITY_TEXTURE_OUTPUT_IDENTITY',relative,'Retained original texture differs from hydration proof')
        if 'dds'in proof:
            from .sources.unity_dds import decode_dds_dxt5
            header=proof['dds'];rgba,_=decode_dds_dxt5(raw,header['width'],header['height']);decoded=Image.frombytes('RGBA',(header['width'],header['height']),rgba)
        else:
            header=proof['astc'];decoded=open_texture(raw,'.astc')
        with decoded as im:
            if im.size!=(header['width'],header['height']) or sha(im.tobytes())!=proof['rgbaRawSha256']:
                fail('UNITY_TEXTURE_OUTPUT_PIXELS',relative,'Source decode differs from canonical hydrated pixels')
            buffer=BytesIO();im.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(buffer,format='PNG');png=buffer.getvalue()
        old=inside(root,relative);new=old.with_suffix('.png');old_meta=Path(str(old)+'.meta');new_meta=Path(str(new)+'.meta')
        if new.exists() or new_meta.exists() or not old_meta.is_file():
            fail('UNITY_TEXTURE_OUTPUT_COLLISION',relative,'Fresh PNG path and existing native meta required')
        old_hash=sha(read(old));meta_hash=sha(read(old_meta))
        new.write_bytes(png);old_meta.rename(new_meta);old.unlink()
        normalized.append(dict(source=rows[0]['source'],previousPath=relative,path=new.relative_to(root).as_posix(),
            providerSha256=old_hash,sha256=sha(png),metaSha256=meta_hash,guid=rows[0]['target']['guid'],
            logicalPath=proof['logicalPath'],rgbaRawSha256=proof['rgbaRawSha256'],encoding='PNG',pixels='exact-source-DDS-DXT5-to-RGBA-flipped-for-Unity'if'dds'in proof else'exact-source-BGRA-to-RGBA-flipped-for-Unity'))
    if normalized:
        path=find_analysis(root,'unity-relocation.json');relocation=load(read(path,max_bytes=128*1024**2),max_nodes=16_000_000)
        changes={r['previousPath']:r['path'] for r in normalized}
        for row in relocation['moves']:
            if row['target'] in changes:row['target']=changes[row['target']]
        write_json(path,relocation)
    write_json(find_analysis(root,'unity-texture-normalization.json'),dict(schemaVersion=1,normalized=normalized,pending=pending))
    return dict(normalized=len(normalized),pending=len(pending),report='Analysis/Readback/unity-texture-normalization.json')
