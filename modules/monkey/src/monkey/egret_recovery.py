"""Reviewed custom Egret source tables and typed JSON, outside target runtime."""
import os
import re
import shutil
import subprocess
import time
from pathlib import Path,PurePosixPath
from .io import read,load,sha,write_json,inside,safe,new_output
from .sources.compiled import fail
from .sources.egret_binary import PROFILE,resource_manifest,plist_pack,bin_json

PINS={
 'readUnsignedShort':'3e43c58f31a78a62b3bb7f28239079af7cfc84cadbbd1cecb3aa71f3b375567e',
 'readAutoNumber':'ac5822bdd5ee9186195c95a0aed99d177f32d2ac17a570dfa2ffcc6d68b68dc7',
 'readFullJson':'b87d39a1fbeb0bbebff057f0bfe8677fd3a9c9855233760116d6b152a34d5de0',
 'readString':'fd0f993f14f8dacb268718d95fc1a97799375a3e669de8e2bafade7cfed552d9',
 'readJsonField':'dfb1c4f06fba3d755f26abbaf5206f2e2d6a891598a418b21009fde5ae36d7e8',
 'binJsonVarInt':'e8b26769a712e6f94d92685fd1745bc282b31c54a23b146a56217a24e7e8d2fd',
 'processor:resourceConfig':'ae61b4cb3db9b57647dcd8bee9e1808297f17716ac9053039665d3a84532cb4d',
 'loadSinglePlistPack':'33c0ea1611d033a234da5100efce2b309153b3dba50d1d6799951cf05d5dcbf7',
 'processor:sheet':'f48c3a5ccf5875b61f8835b20dfe457f9eeaa459ada1d24a9c8c483a0506cacd'}


def source_facts(snapshot,rows):
    node=shutil.which('node')
    if not node:fail('DEPENDENCY_MISSING','Node','Static tokenizer required for reviewed source profile')
    facts=[];bindings=[];worker=Path(__file__).parent/'sources/egret-facts.cjs'
    scripts=[row for row in rows if row['path'].endswith('.js')]
    if len(scripts)>128 or sum(row['bytes']for row in scripts)>64*1024*1024:fail('EGRET_SOURCE_BUDGET','$','Explicit source script budget exceeded')
    env={k:v for k,v in os.environ.items()if k not in ('NODE_OPTIONS','NODE_PATH')}
    deadline=time.monotonic()+120
    for row in scripts:
        remaining=deadline-time.monotonic()
        if remaining<=0:fail('EGRET_SOURCE_BUDGET','$','Aggregate source proof deadline reached')
        raw=read(inside(snapshot,row['path']))
        if sha(raw)!=row['sha256']:fail('SOURCE_CHANGED',row['path'],'Snapshot differs before static source proof')
        child=subprocess.Popen([node,'--max-old-space-size=256',str(worker)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        try:stdout,stderr=child.communicate(raw,timeout=min(30,remaining))
        except subprocess.TimeoutExpired:
            child.terminate()
            try:child.communicate(timeout=5)
            except subprocess.TimeoutExpired:fail('EGRET_SOURCE_CHILD_PENDING',row['path'],'Owned tokenizer did not exit after TERM')
            fail('EGRET_SOURCE_BUDGET',row['path'],'Static tokenizer exceeded deadline')
        if child.returncode:fail('EGRET_SOURCE_PARSE',row['path'],'Source tokens could not be parsed; nothing was executed')
        document=load(stdout)
        if document.get('sourceSha256')!=sha(raw)or document.get('sourceExecuted')is not False:fail('EGRET_SOURCE_CHANGED',row['path'],'Tokenizer identity differs')
        for fact in document['facts']:
            span=fact['sourceBytes'];body=raw[span['start']:span['end']]
            if sha(body)!=fact['sha256']:fail('EGRET_SOURCE_SPAN',row['path'],'Static source byte range differs')
            if PINS.get(fact['name'])==fact['sha256']:facts.append(dict(fact,sourceFile=row['path'],sourceFileSha256=sha(raw)))
        binding=document.get('lexicalVarIntBinding')
        if binding:
            p=binding['definitionBytes']
            if sha(raw[p['start']:p['end']])!=PINS['binJsonVarInt']or binding.get('definitionSha256')!=PINS['binJsonVarInt']or binding.get('sourceExecuted')is not False:fail('EGRET_VARINT_BINDING',row['path'],'BinJson lexical variable integer helper differs from reviewed source')
            bindings.append(dict(binding,sourceFile=row['path'],sourceFileSha256=sha(raw)))
    if set(f['name']for f in facts)!=set(PINS):fail('EGRET_PROFILE_UNVERIFIED','$','Exact reviewed resource, variable integer, Plist and BinJson callbacks required in supplied scripts')
    if not bindings:fail('EGRET_VARINT_BINDING','$','Exact BinJson lexical helper binding required')
    return dict(schemaVersion=1,profile=PROFILE,facts=facts,lexicalVarIntBindings=bindings,workerSha256=sha(read(worker)),
                algorithmFiles={p.name:sha(read(p))for p in [Path(__file__),Path(__file__).parent/'sources/egret_binary.py']},sourceExecuted=False)


def skin_records(value,source_file):
    """EUI class definitions and package metadata are different root records."""
    if not isinstance(value,dict):fail('EGRET_SKIN_ROOT',source_file,'Expected compiled EUI class table')
    skins=[];metadata=[];unknown=[]
    for name,definition in value.items():
        record=dict(name=name,sourceFile=source_file,native='not_restored')
        if name in('$skins','$styles'):metadata.append(dict(record,kind='eui-package-metadata'))
        elif isinstance(definition,dict)and isinstance(definition.get('$sC'),str):
            skins.append(dict(record,sourcePath=definition.get('$path'),baseClass=definition['$sC']))
        else:unknown.append(dict(record,kind='unclassified-ui-root-record'))
    return skins,metadata,unknown


def inspect(snapshot,rows,output):
    """Decode supplied tables, retaining missing dependencies rather than guessing URLs."""
    snapshot=safe(snapshot);output=new_output(output,[snapshot]);(output/'Decoded').mkdir();proof=source_facts(snapshot,rows);write_json(output/'source-proof.json',proof)
    by_logical={}
    for row in rows:by_logical.setdefault(row['path'].split('/',1)[1],[]).append(row)
    def matches(manifest,url):
        path=PurePosixPath(url)
        if not url or url.startswith('/')or any(x in url for x in ['\\','?', '#',':'])or '..'in path.parts:fail('EGRET_RESOURCE_PATH',url,'Only explicit relative logical resource paths supported')
        parent=PurePosixPath(manifest['sourceFile'].split('/',1)[1]).parent
        return by_logical.get((parent/path).as_posix(),[])
    manifests=[];resources=[];decoded=[];sheets=[];skins=[];skin_metadata=[];unknown_ui=[];expanded=0
    def budget(document):
        nonlocal expanded
        expanded+=document['expandedBytes']
        if expanded>128*1024*1024 or len(resources)>200_000 or sum(len(s['frames'])for s in sheets)>200_000 or len(skins)+len(skin_metadata)+len(unknown_ui)>50_000:
            fail('EGRET_AGGREGATE_BUDGET','$','Expanded source, resource, frame or Skin aggregate limit exceeded')
    for row in rows:
        if not re.fullmatch(r'default\.res(?:_[A-Za-z0-9]+)*\.bin',PurePosixPath(row['path']).name):continue
        doc=resource_manifest(read(inside(snapshot,row['path'])))
        if len(resources)+len(doc['resources'])>200_000:fail('EGRET_AGGREGATE_BUDGET','$','Aggregate resource declarations exceed limit')
        budget(doc);doc['sourceFile']=row['path'];manifests.append(doc)
        dest='Decoded/'+sha(row['path'].encode())[:24]+'.json';write_json(output/dest,doc);decoded.append(dict(sourceFile=row['path'],kind=doc['kind'],decoded=dest))
        for item in doc['resources']:
            item=dict(item,sourceManifest=row['path']);found=matches(doc,item['url'])
            digests={r['sha256']for r in found}
            if len(digests)>1:fail('EGRET_RESOURCE_CONFLICT',item['url'],'Same exact logical path has differing supplied contents')
            item['localSources']=[r['path']for r in found];item['availability']='provided'if found else'missing';resources.append(item)
            if found and item['declaredBytes']and any(r['bytes']!=item['declaredBytes']for r in found):fail('EGRET_RESOURCE_BYTES',item['name'],'Local exact logical resource differs from declared size')
            if not found:continue
            record=found[0];raw=read(inside(snapshot,record['path']));parsed=None
            if item['name']in ('plist_pack_bin','plist_lang_pack_bin'):
                parsed=plist_pack(raw)
                for sheet in parsed['sheets']:
                    candidates=[r for r in doc['resources']if r['name']==sheet['textureName']and r['type']in ('image','imageWithGrid')]
                    texture=candidates[0]if len(candidates)==1 else None
                    local=matches(doc,texture['url'])if texture else []
                    sheets.append(dict(sheet,sourcePack=record['path'],sourcePackSha256=sha(raw),sourceManifest=row['path'],textureResource=texture,
                                       localTextures=[r['path']for r in local],status='provided_texture'if local else'missing_texture'if texture else'missing_texture_declaration'))
            elif item['name']in ('gameEui_start_bin','gameEui_bin'):
                parsed=bin_json(raw)
                if item['name'].startswith('gameEui'):
                    value=parsed['value']
                    if not isinstance(value,dict):fail('EGRET_SKIN_ROOT',item['name'],'Expected named source Skin table')
                    classes,metadata,unknown=skin_records(value,record['path'])
                    skins.extend(classes);skin_metadata.extend(metadata);unknown_ui.extend(unknown)
            if parsed:
                budget(parsed)
                dest='Decoded/'+sha(record['path'].encode())[:24]+'.json';write_json(output/dest,parsed);decoded.append(dict(sourceFile=record['path'],kind=parsed['kind'],decoded=dest))
    if not manifests:fail('EGRET_RESOURCE_MANIFEST','$','No supplied reviewed binary resource manifests')
    if len(resources)>200_000:fail('EGRET_AGGREGATE_BUDGET','$','Aggregate resource declarations exceed limit')
    # Manifest duplicates remain independent declarations, never collapsed by basename.
    summary=dict(manifests=len(manifests),declaredResources=len(resources),providedResourceDeclarations=sum(r['availability']=='provided'for r in resources),
                 missingResourceDeclarations=sum(r['availability']=='missing'for r in resources),plistSheets=len(sheets),parsedSourceFrames=sum(len(s['frames'])for s in sheets),
                 sheetsWithLocalTexture=sum(s['status']=='provided_texture'for s in sheets),sourceSkins=len(skins),sourceSkinClasses=len(skins),
                 sourceUiRootRecords=len(skins)+len(skin_metadata)+len(unknown_ui),skinMetadataRecords=len(skin_metadata),unknownUiRootRecords=len(unknown_ui),nativeSourceGraphs=0,methodsRecovered=0)
    report=dict(schemaVersion=1,profile=PROFILE,sourceProof='source-proof.json',resources=resources,sheets=sheets,skins=skins,skinMetadata=skin_metadata,unknownUiRecords=unknown_ui,decoded=decoded,summary=summary,sourceExecuted=False)
    write_json(output/'recovery.json',report);return report


def materialize_frames(recovery,images,normalized,ir,namespace):
    """Source top-left offsets become normalized centers; no invented pixels."""
    from .normalize import sprite
    from .sources.compiled import ParseError
    from .io import diagnostic
    from PIL import Image
    available={name:(digest,image)for name,digest,image in images};pixels=0;count=0;mapping=[]
    for sheet in recovery['sheets']:
        if sheet['status']!='provided_texture':continue
        paths=sheet['localTextures'];matches=[p for p in paths if p in available]
        if not matches:
            ir['diagnostics'].append(diagnostic('EGRET_ATLAS_IMAGE_UNAVAILABLE',sheet['name'],'Exact local page is not an accepted PNG/JPEG within image decode budgets'));continue
        digest,atlas=available[matches[0]]
        if len({available[p][0]for p in matches})!=1:fail('EGRET_ATLAS_IMAGE_CONFLICT',sheet['name'],'Ambiguous exact page pixels')
        for frame in sheet['frames']:
            sid=namespace+':egret-plist:'+sheet['sourceManifest']+'#'+sheet['name']+'#'+frame['name']
            try:
                w,h=frame['rect'][2:];ow,oh=frame['originalSize'];left,top=frame['trimOrigin']
                if pixels+ow*oh>64_000_000:fail('EGRET_FRAME_PIXEL_BUDGET',sid,'Aggregate reconstructed source frame pixel limit exceeded')
                trimmed,full,semantic=sprite(atlas,dict(rect=frame['rect'],originalSize=frame['originalSize'],rotated=0,offset=[left-(ow-w)/2,(oh-h)/2-top],capInsets=[0,0,0,0]))
                relative='assets/'+sha(sid.encode())[:24];trimmed.save(normalized/(relative+'.png'));full.save(normalized/(relative+'-original.png'));pixels+=ow*oh
                ir['spriteFrames'].append(dict(sourceId=sid,textureRef=namespace+':original-image:'+matches[0],image=relative+'.png',originalImage=relative+'-original.png',**semantic,
                    derivation='source-egret-plist-frame; not-source-graph',sourceResourceEvidence=dict(sourceManifest=sheet['sourceManifest'],sourcePack=sheet['sourcePack'],sourcePackSha256=sheet['sourcePackSha256'],
                    expandedSourceBytes=frame['sourceBytes'],textureFile=matches[0],textureSha256=digest)))
                ir['sourceNames'][sid]=dict(bundle='egret',logicalPath='Plist/'+sheet['name']+'/'+frame['name'],sourceType='egret-plist-frame',nameProvenance='literal-original-sheet-and-frame-name')
                mapping.append(dict(sourceFrame=sid,sourcePack=sheet['sourcePack'],sourceBytes=frame['sourceBytes'],texture=matches[0],textureSha256=digest,trimmedSha256=sha(read(normalized/(relative+'.png'))),fullSha256=sha(read(normalized/(relative+'-original.png')))))
                count+=1
            except (ParseError,OSError,Image.DecompressionBombError)as error:
                ir['diagnostics'].append(diagnostic(getattr(error,'code','EGRET_FRAME_IMAGE'),sid,str(error),sid))
    return dict(sourceSpriteFrames=count,sourceFramePixels=pixels,frames=mapping)
