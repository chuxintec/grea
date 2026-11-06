"""Recover explicit local skeleton/atlas/page closures, without installing a runtime."""
import re
from io import BytesIO
from pathlib import Path
from ..io import read,sha,inside,write_json,encoded
from ..sources.compiled import fail,ParseError
from ..normalize import open_texture
from ..layout.standard import find_analysis,analysis_rel,ROOTS


def binary_version(raw):
    offset=0
    def string():
        nonlocal offset
        value=0
        for shift in range(0,35,7):
            if offset>=len(raw):raise ValueError('Truncated Spine string')
            byte=raw[offset];offset+=1;value|=(byte&127)<<shift
            if not byte&128:break
        else:raise ValueError('Invalid Spine varint')
        length=max(value-1,0)
        if length>256 or offset+length>len(raw):raise ValueError('Unbounded Spine header')
        text=raw[offset:offset+length].decode('utf-8');offset+=length;return text
    try:
        string();version=string()
        return version if re.fullmatch(r'3\.[0-9]+\.[0-9]+',version) else None
    except (ValueError,UnicodeError):return None


def atlas_pages(text):
    lines=text.splitlines();pages=[]
    for i,line in enumerate(lines[:-1]):
        if line and not line[0].isspace() and ':' not in line and lines[i+1].startswith(('size:','format:')):
            path=Path(line)
            if path.is_absolute() or '..' in path.parts or '\\' in line or path.as_posix()!=line:
                fail('SPINE_PAGE_PATH',line,'Atlas page escapes its local closure')
            pages.append(line)
    if not pages or len(pages)!=len(set(pages)):fail('SPINE_ATLAS_PAGES','atlas','Missing or duplicate page declarations')
    return pages


def recover_closures(manifest,destination,previous=None,engine='unity',namespace='monkey-project',overrides=None):
    destination=Path(destination);assets={a['sourceId']:a for a in manifest['assets']}
    inputs={(i.get('bundle',manifest['bundle']),i['path']):i for i in manifest['inputs']}
    def resource(asset):
        bundle=asset.get('bundle',manifest['bundle']);relative=asset.get('native')
        if not relative:fail('SPINE_NATIVE_MISSING',asset['sourceId'],'Native resource not provided')
        expected=inputs.get((bundle,relative));raw=read(inside(Path(manifest['sourceRoots'][bundle]),relative),max_bytes=128*1024*1024)
        if expected is None or expected['sha256']!=sha(raw):fail('SPINE_SOURCE_CHANGED',relative,'Native resource differs from frozen receipt')
        return raw,relative
    from ..names import source_names
    from ..layout import LayoutPlanner,casing
    from ..layout.standard import RECOVERY
    # Export real skeleton/atlas/page data under Content/Spine. Unity data is importable
    # TextAsset evidence until a compatible licensed runtime is explicitly connected.
    naming=LayoutPlanner(engine,source_names(manifest),overrides)
    old_rows={};old_root=None;old_owned={};decoded_pages=0;reused_pages=0
    if previous:
        from ..io import stage_manifest,load,safe
        from ..sources.containers import fingerprint
        old_root=safe(previous[0])
        if fingerprint(old_root/'manifest.json')!=previous[1]:fail('REPLAN_STAGE_DRIFT','spine','Frozen candidate manifest changed')
        old_owned={f['path']:f for f in stage_manifest(old_root)['files']}
        def old_bytes(path):
            raw=read(inside(old_root,path),max_bytes=128*1024*1024)
            if path not in old_owned or sha(raw)!=old_owned[path]['sha256']:fail('REPLAN_STAGE_DRIFT',path,'Frozen Spine bytes changed')
            return raw
        old_rows={r['sourceId']:r for r in load(old_bytes(analysis_rel(old_root,'spine-closures.json')))['skeletons']}
    results=[]
    for asset in manifest['assets']:
        if asset.get('kind')!='sp.SkeletonData':continue
        row=dict(sourceId=asset['sourceId'],status='needs_action',nativeValidation='not_run',runtime='not_installed',files=[])
        if asset.get('sourceDocument') and asset.get('document')is None:
            row.update(reason='SPINE_SOURCE_DOCUMENT_DEFERRED',sourceDocument=asset['sourceDocument'],
                       message='Source-only profile preserves original packed payload; no native skeleton closure is claimed')
            results.append(row);continue
        try:
            obj=next(o for o in asset.get('document',{}).get('instances',[]) if isinstance(o,dict) and o.get('__type__')=='sp.SkeletonData')
            atlas=obj.get('_atlasText');names=obj.get('textureNames');textures=obj.get('textures')
            if not isinstance(atlas,str) or not isinstance(names,list) or not isinstance(textures,list):
                fail('SPINE_FIELDS_UNSUPPORTED',asset['sourceId'],'Explicit atlas, textureNames and textures required')
            if atlas_pages(atlas)!=names or len(names)!=len(textures):
                fail('SPINE_PAGE_MAPPING',asset['sourceId'],'Atlas page order and explicit texture mapping differ')
            inline=obj.get('_skeletonJson')
            if not asset.get('native') and isinstance(inline,dict):
                version=inline.get('skeleton',{}).get('spine') if isinstance(inline.get('skeleton'),dict) else None
                if (not isinstance(version,str) or not version or not isinstance(inline.get('bones'),list)
                        or not isinstance(inline.get('slots'),list) or not isinstance(inline.get('animations'),dict)
                        or not isinstance(inline.get('skins'),(dict,list))):
                    fail('SPINE_JSON_SCHEMA_UNSUPPORTED',asset['sourceId'],'Expected explicit skeleton version, bones, slots, skins and animations')
                raw=encoded(inline);skeleton_name='skeleton.json'
                row.update(skeletonSource='inline-json',runtimeCompatibility='not_validated',sourceNativeSha256=None)
            else:
                raw,relative=resource(asset);version=binary_version(raw);skeleton_name='skeleton.bin'
                if version is None:fail('SPINE_BINARY_VERSION_UNSUPPORTED',asset['sourceId'],'Only recognizable 3.x binary header supported; no guessed runtime')
                row.update(skeletonSource='native-binary',runtimeCompatibility='not_validated',sourceNativeSha256=sha(raw))
            # Preserve nonstandard source version labels exactly; a data closure is not runtime compatibility.
            row['skeletonVersion']=version
            files={skeleton_name:raw,'source.atlas':atlas.encode('utf-8')};dependencies=[]
            for name,ref in zip(names,textures):
                if Path(name).suffix.lower()!='.png':fail('SPINE_PAGE_FORMAT',name,'Only explicit PNG atlas page outputs supported')
                key=ref.get('__uuid__') if isinstance(ref,dict) else None
                sid=asset.get('bundle',manifest['bundle'])+':'+str(key);seen=set()
                while sid in assets and assets[sid].get('kind')=='redirect':
                    if sid in seen:fail('SPINE_REDIRECT_CYCLE',sid,'Texture redirect cycle')
                    seen.add(sid);sid=assets[sid].get('redirectTarget')
                texture=assets.get(sid)
                if not texture or texture.get('kind')!='cc.Texture2D':fail('SPINE_TEXTURE_MISSING',str(sid),'Explicit texture dependency not provided')
                image_raw,image_path=resource(texture)
                prior=old_rows.get(asset['sourceId'])
                if prior and prior['status']=='closure_recovered':
                    atlas_file=next((f for f in prior['files'] if f['path'].endswith(('.atlas','.atlas.txt'))),None)
                    dependency=next((d for d in prior['dependencies'] if d['page']==name),None)
                    page_name=dependency.get('targetPage',name) if dependency else name
                    page=next((f for f in prior['files'] if f['path'].endswith('/'+page_name)),None)
                    if (prior.get('sourceSkeletonSha256')!=sha(raw) or atlas_file is None
                            or prior.get('sourceAtlasSha256',sha(old_bytes(atlas_file['path'])))!=sha(atlas.encode('utf-8'))
                            or dependency is None or dependency['sourceId']!=sid or dependency['sourceSha256']!=sha(image_raw) or page is None):
                        fail('REPLAN_SPINE_SOURCE_CHANGED',asset['sourceId'],'Frozen closure does not match current skeleton/atlas/texture identities')
                    files[name]=old_bytes(page['path']);reused_pages+=1
                else:
                    image=open_texture(image_raw,Path(image_path).suffix.lower())
                    stream=BytesIO();image.save(stream,format='PNG');files[name]=stream.getvalue();decoded_pages+=1
                dependencies.append(dict(page=name,sourceId=sid,sourceSha256=sha(image_raw)))
            folder=naming.folder(asset['sourceId'],'spine',root=ROOTS[engine]['content'])
            stem=casing.snake(naming.record(asset['sourceId'],'spine','','folder')['stem'])
            page_map={};claimed=set()
            for name in names:
                target=casing.safe_path(name)
                if target.casefold() in claimed:
                    p=Path(target);target=str(p.with_name(p.stem+'_'+sha(name.encode())[:10]+p.suffix))
                if target.casefold() in claimed:fail('SPINE_PAGE_COLLISION',name,'Unresolved pinyin collision')
                claimed.add(target.casefold());page_map[name]=target
            # Replace only page declaration lines, never region/attachment names.
            lines=atlas.splitlines(keepends=True)
            for index,line in enumerate(lines[:-1]):
                name=line.rstrip('\r\n')
                if name in page_map and lines[index+1].startswith(('size:','format:')):
                    lines[index]=page_map[name]+line[len(name):]
            files['source.atlas']=''.join(lines).encode('utf-8')
            compatible=bool(re.fullmatch(r'3\.8\.\d+',str(version)))
            skeleton_suffix=('.skel' if engine=='creator' else '.skel.bytes') if skeleton_name.endswith('.bin') else ('.json' if engine=='unity' or compatible else '.json.txt')
            atlas_name=stem+('.atlas' if engine=='creator' else '.atlas.txt')
            files={(stem+skeleton_suffix if name==skeleton_name else atlas_name if name=='source.atlas' else page_map[name]):data for name,data in files.items()}
            from ..targets import cocos,unity
            atlas_uuid=cocos.identity(namespace,asset['sourceId']+'/atlas')
            for dependency in dependencies:dependency['targetPage']=page_map[dependency['page']]
            for name,data in files.items():
                path=inside(destination/folder,name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
                row['files'].append(dict(path=folder+'/'+name,sha256=sha(data),bytes=len(data)))
                identity=asset['sourceId']+('/atlas' if name==atlas_name else '/skeleton' if name==stem+skeleton_suffix else '/page/'+name)
                if engine=='unity':
                    Path(str(path)+'.meta').write_text('fileFormatVersion: 2\nguid: '+unity.guid(namespace,identity)+'\n',encoding='utf-8')
                else:
                    uid=cocos.identity(namespace,identity)
                    if name==stem+skeleton_suffix and compatible:meta=cocos.meta(uid,'spine-data','1.2.7',dict(atlasUuid=atlas_uuid))
                    elif name.endswith('.png'):meta=cocos.meta(uid,'image','1.0.27',dict(type='texture',fixAlphaTransparencyArtifacts=False,hasAlpha=True))
                    else:meta=cocos.meta(uid,'*','1.0.0')
                    write_json(Path(str(path)+'.meta'),meta)
            row.update(status='closure_recovered',dependencies=dependencies,sourceSkeletonSha256=sha(raw),sourceAtlasSha256=sha(atlas.encode('utf-8')),
                       nativeImportCandidate=engine=='creator' and compatible,
                       skeletonPath=folder+'/'+stem+skeleton_suffix,atlasPath=folder+'/'+atlas_name,
                       runtime='creator-builtin-3.8' if engine=='creator' and compatible else 'not_installed' if engine=='unity' else 'source_version_requires_adapter',
                       remaining='File export only; native importer identity and playback require separate verification')
        except (ParseError,ValueError,OSError,KeyError,TypeError,StopIteration) as error:
            row.update(reason=getattr(error,'code','SPINE_SOURCE_UNSUPPORTED'),message=str(error))
        results.append(row)
    report=dict(schemaVersion=1,skeletons=results,closed=sum(r['status']=='closure_recovered' for r in results),
                unresolved=sum(r['status']!='closure_recovered' for r in results),nativeValidation='not_run',naming=naming.report(),decodedPages=decoded_pages,reusedPages=reused_pages)
    (destination/'Analysis').mkdir(parents=True,exist_ok=True)
    write_json(find_analysis(destination,'spine-closures.json'),report);return report
