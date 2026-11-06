"""Read existing native Sprite identities/importers/references without an Editor."""
import re
from pathlib import Path
from .io import safe,inside,read,load,sha,new_output,write_json
from .sources.compiled import fail
from .layout.standard import find_analysis,find_output_paths


def number(meta,key):
    matches=re.findall(rb'^\s*'+key.encode()+rb':\s*(-?[0-9.eE+]+)\s*$',meta,re.M)
    if len(matches)!=1:return None
    value=float(matches[0]);return int(value)if value.is_integer()else value


def vector(meta,key):
    match=re.search(rb'^\s*'+key.encode()+rb':\s*\{([^\r\n}]+)\}',meta,re.M)
    if not match:return None
    return {k.decode():float(v)for k,v in re.findall(rb'([xyzw]):\s*(-?[0-9.eE+]+)',match[1])}


def prefab_object_ids(body,spec,node_specs):
    """Resolve saved YAML object identities through exact child ordinals, never names."""
    headers=list(re.finditer(rb'^--- !u!([0-9]+) &(-?[0-9]+).*$',body,re.M));blocks={}
    for i,h in enumerate(headers):
        fid=h[2].decode()
        if fid in blocks:fail('NATIVE_PREFAB_DUPLICATE_FILEID',fid,'Duplicate serialized object identity')
        blocks[fid]=(int(h[1]),body[h.end():headers[i+1].start()if i+1<len(headers)else len(body)])
    rects={}
    for fid,(tag,text)in blocks.items():
        if tag!=224:continue
        go=re.search(rb'^  m_GameObject: \{fileID: (-?[0-9]+)\}',text,re.M);father=re.search(rb'^  m_Father: \{fileID: (-?[0-9]+)\}',text,re.M)
        children=re.search(rb'^  m_Children:([^\n]*\n(?:  -[^\n]*\n)*)',text,re.M)
        if not go or not father or not children:fail('NATIVE_PREFAB_RECT_IDENTITY',fid,'Saved RectTransform hierarchy is incomplete')
        rects[fid]=dict(go=go[1].decode(),father=father[1].decode(),children=[x.decode()for x in re.findall(rb'fileID: (-?[0-9]+)',children[1])])
    roots=[fid for fid,r in rects.items()if r['father']=='0']
    if len(roots)!=1:fail('NATIVE_PREFAB_ROOT_IDENTITY',spec['sourceId'],'Exactly one saved source root required')
    result=[];visited=set()
    def walk(source_id,fid):
        if fid in visited or fid not in rects:fail('NATIVE_PREFAB_NODE_IDENTITY',source_id,'Unknown/duplicate saved transform')
        visited.add(fid);row=rects[fid];source=node_specs[source_id]
        if blocks.get(row['go'],(None,))[0]!=1 or len(row['children'])!=len(source['children']):fail('NATIVE_PREFAB_NODE_IDENTITY',source_id,'Saved object/child ordinal graph differs')
        result.append(dict(sourceId=source_id,gameObjectFileId=row['go'],transformFileId=fid))
        for child_source,child_id in zip(source['children'],row['children']):
            if rects.get(child_id,{}).get('father')!=fid:fail('NATIVE_PREFAB_PARENT_IDENTITY',child_source,'Saved child parent differs')
            walk(child_source,child_id)
    walk(spec['root'],roots[0])
    if len(result)!=spec['nodeCount']or set(r['sourceId']for r in result)!=set(spec['nodes']):fail('NATIVE_PREFAB_NODE_COUNT',spec['sourceId'],'Source-to-native node coverage differs')
    return result


def export(candidate,output):
    root=safe(candidate);manifest_raw=read(root/'manifest.json',max_bytes=128*1024**2);manifest=load(manifest_raw,max_nodes=16_000_000,max_depth=128)
    raw=read(find_analysis(root,'editor-readback.json'),max_bytes=128*1024**2);rb=load(raw,max_nodes=16_000_000,max_depth=128)
    source=load(read(find_analysis(root,'source-map.json'),max_bytes=128*1024**2),max_nodes=16_000_000,max_depth=128)
    locations=load(read(find_output_paths(root)));plan_path=inside(root,locations['plan']);plan=load(read(plan_path,max_bytes=128*1024**2),max_nodes=16_000_000,max_depth=128)
    if rb.get('status')not in ('partial','passed')or not rb.get('sceneReopened'):fail('NATIVE_CONTRACT_READBACK',str(root),'Existing saved/reopened native readback required')
    by_id={r['sourceId']:r for r in source['assets']};specs={r['id']:r for r in plan['textures']};old_hashes={f['path']:f['sha256']for f in rb['nativeFiles']};sprites=[];by_guid={}
    for native in rb['sprites']:
        asset=by_id[native['id']];path=asset['path'];meta_path=inside(root,path+'.meta');meta=read(meta_path)
        if old_hashes.get(path+'.meta')!=sha(meta):fail('NATIVE_CONTRACT_META_CHANGED',path,'Importer metadata differs from actual readback snapshot')
        guid=re.findall(rb'^guid: ([0-9a-f]{32})\r?$',meta,re.M)
        if guid!=[native['guid'].encode()]or native['fileId']==0:fail('NATIVE_CONTRACT_IDENTITY',path,'Actual Sprite GUID/localID differs')
        importer=dict(type=number(meta,'textureType'),spriteMode=number(meta,'spriteMode'),pixelsPerUnit=number(meta,'spritePixelsToUnits'),configuredPivot=vector(meta,'spritePivot'),configuredBorder=vector(meta,'spriteBorder'))
        if importer['type']!=8 or importer['spriteMode']!=1:fail('NATIVE_CONTRACT_IMPORTER',path,'Expected actual single-Sprite importer semantics')
        row=dict(sourceId=native['id'],path=path,guid=native['guid'],nativeType='Sprite',actualSpriteFileId=str(native['fileId']),
                 actualSize=native['size'],actualBorder=native['border'],importer=importer,importerMetaSha256=sha(meta),
                 sourceGeometry={k:specs[native['id']].get(k)for k in ('size','originalSize','offset','border')},
                 pivotEvidence='Importer metadata matched to previous native snapshot; Sprite.pivot was not separately captured')
        sprites.append(row);by_guid.setdefault(row['guid'],[]).append(row)
    prefab_specs={s['sourceId']:s for s in plan['sourcePrefabs']};node_specs={n['sourceId']:n for n in plan['nodes']}
    prefabs=[]
    for prefab in rb['sourcePrefabs']:
        path=inside(root,prefab['path']);body=read(path,max_bytes=128*1024**2)
        if old_hashes.get(prefab['path'])!=sha(body):fail('NATIVE_CONTRACT_PREFAB_CHANGED',prefab['path'],'Prefab differs from saved native snapshot')
        meta=read(inside(root,prefab['path']+'.meta'))
        if old_hashes.get(prefab['path']+'.meta')!=sha(meta)or re.findall(rb'^guid: ([0-9a-f]{32})\r?$',meta,re.M)!=[prefab['guid'].encode()]:fail('NATIVE_CONTRACT_PREFAB_GUID',prefab['path'],'Saved Prefab GUID differs')
        objects=prefab_object_ids(body,prefab_specs[prefab['sourceId']],node_specs)
        refs=[]
        for fid,guid in re.findall(rb'^\s*m_Sprite:\s*\{fileID:\s*(-?[0-9]+),\s*guid:\s*([0-9a-f]{32}),\s*type:\s*[0-9]+\}',body,re.M):
            key=guid.decode();candidates=by_guid.get(key,[])
            if not candidates or any(c['actualSpriteFileId']!=fid.decode()for c in candidates):fail('NATIVE_CONTRACT_SPRITE_PPTR',prefab['path'],'Prefab Sprite pointer not in actual native Sprite identity set')
            refs.append(dict(guid=key,fileId=fid.decode(),sourceSpriteIds=[c['sourceId']for c in candidates]))
        prefabs.append(dict(sourceId=prefab['sourceId'],path=prefab['path'],guid=prefab['guid'],sha256=sha(body),savedReloaded=prefab['savedReloaded'],referencesVerified=prefab['referencesVerified'],objects=objects,spriteReferences=refs))
    scenes=[];finish_path=find_analysis(root,'bulk-finish-readback.json')
    if finish_path.exists():
        finish=load(read(finish_path))
        if finish.get('status')!='completed'or finish.get('priorReadbackSha256')!=sha(raw)or finish.get('inputPlanSha256')!=sha(read(plan_path,max_bytes=128*1024**2)):fail('NATIVE_CONTRACT_SCENE_READBACK',str(finish_path),'Exact successful native incremental proof required')
        for row in finish['scenes']:
            if row['status']=='excluded':scenes.append(dict(sourceId=row['sourceId'],status='excluded',reason=row['reason'],sourceNodes=row['sourceNodes']));continue
            path=inside(root,row['path']);body=read(path,max_bytes=128*1024**2);meta=read(inside(root,row['path']+'.meta'));guid=re.findall(rb'^guid: ([0-9a-f]{32})\r?$',meta,re.M)
            ids={fid.decode():int(tag)for tag,fid in re.findall(rb'^--- !u!([0-9]+) &(-?[0-9]+)',body,re.M)}
            if row.get('savedReopened')is not True or row.get('missingScripts')!=0 or guid!=[row['guid'].encode()]or len(row.get('objects',[]))!=row['sourceNodes']:fail('NATIVE_CONTRACT_SCENE_IDENTITY',row['sourceId'],'Source Scene save/reopen or object count differs')
            objects=row['objects'];source_ids=[r['sourceId']for r in objects]
            if len(set(source_ids))!=len(source_ids)or any(r['sceneGuid']!=row['guid']or not r['sourceId'].startswith(row['sourceId']+'#')or ids.get(r['gameObjectFileId'])!=1 or ids.get(r['transformFileId'])!=224 for r in objects):fail('NATIVE_CONTRACT_SCENE_FILEID',row['sourceId'],'Actual Scene GameObject/RectTransform fileIDs differ')
            refs=[]
            for fid,g in re.findall(rb'^\s*m_Sprite:\s*\{fileID:\s*(-?[0-9]+),\s*guid:\s*([0-9a-f]{32}),\s*type:\s*[0-9]+\}',body,re.M):
                candidates=by_guid.get(g.decode(),[])
                if not candidates or any(c['actualSpriteFileId']!=fid.decode()for c in candidates):fail('NATIVE_CONTRACT_SCENE_SPRITE',row['sourceId'],'Scene Sprite pointer differs from actual importer identity')
                refs.append(dict(guid=g.decode(),fileId=fid.decode(),sourceSpriteIds=[c['sourceId']for c in candidates]))
            scenes.append(dict(row,sha256=sha(body),metaSha256=sha(meta),spriteReferences=refs))
    out=new_output(output,[root]);report=dict(schemaVersion=1,sourceManifestSha256=sha(manifest_raw),nativeReadbackSha256=sha(raw),
        sprites=sprites,prefabs=prefabs,sourceScenes=scenes,counts=dict(sourceScenes=sum(s['status']=='saved-reopened'for s in scenes),excludedScenes=sum(s['status']=='excluded'for s in scenes),sourceSceneNodes=sum(s['sourceNodes']for s in scenes if s['status']=='saved-reopened'),sprites=len(sprites),sourceFrames=len({r['sourceId'].removesuffix('@original')for r in sprites}),sourcePrefabs=len(prefabs),sourcePrefabNodes=sum(len(p['objects'])for p in prefabs),prefabSpritePointers=sum(len(p['spriteReferences'])for p in prefabs)),
        mergePolicy=dict(hashOnlyReuse=False,guidOnlyReuse=False,requires=['nativeType','importer semantics','geometry','actual Sprite local fileID','Prefab PPtr mapping'],preserveTargetManualBorderAndGeometry=True),
        sceneRecovery='Exact source SceneAsset native identity proof included'if scenes else'Source scenes not exported; auxiliary Candidate/ImportBootstrap not counted as source scenes',newEditorRun=False)
    write_json(out/'native-contract.json',report);return dict(status='contracted',counts=report['counts'],report=str(out/'native-contract.json'))
