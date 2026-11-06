"""Source-exact Spine binding and closure contracts for recovered Prefabs.

This module records serialized source declarations only. It does not load a
Spine runtime, execute animation data, infer missing UUIDs, or emit native IDs.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

from .assets.spine import atlas_pages, binary_version, recover_closures
from .io import inside, read
from .normalize import expand_nodes

SCHEMA='prefab-spine-binding/1'
FIELD_ALIASES={
    'skeletonData':['_N$skeletonData'],
    'skin':['defaultSkin','_defaultSkin'],
    'animation':['defaultAnimation','_animationName'],
    'loop':['loop'],
    'playTimes':['_playTimes'],
    'timeScale':['timeScale','_timeScale'],
    'premultipliedAlpha':['premultipliedAlpha'],
    'tint':['useTint','_useTint','tint'],
    'debug':['debugSlots','debugBones','debugMesh','_debugSlots','_debugBones','_debugMesh'],
    'caching':['_preCacheMode','preCacheMode','defaultCacheMode'],
}


def _sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()


def _component_fields(component):
    return {k:v for k,v in component.items() if k not in ('__type__','node')}


def _explicit_properties(fields):
    result={}
    for prop,aliases in FIELD_ALIASES.items():
        keys=[key for key in aliases if key in fields]
        result[prop]=({'status':'explicit','sourceFields':{key:fields[key] for key in keys}}
                      if keys else {'status':'not_serialized_default_unresolved','sourceFields':{}})
    return result


def _node_index(component):
    node=component.get('node')
    return node.get('__id__') if isinstance(node,dict) else None


def _node_map(document,namespace):
    flat=list(expand_nodes(document.get('instances',[]),namespace))
    nodes={str(index):obj for index,obj in flat if isinstance(obj,dict) and obj.get('__type__') in ('cc.Node','cc.Scene')}
    def parent_key(node):
        parent=node.get('_parent')
        if not isinstance(parent,dict):return None
        if type(parent.get('__id__')) is int:return str(parent['__id__'])
        source=parent.get('__sourceId__')
        if isinstance(source,str) and source.startswith(namespace+'#'):return source.split('#',1)[1]
        return None
    def node_path(index):
        names=[];seen=set();key=str(index)
        while key in nodes and key not in seen:
            seen.add(key);node=nodes[key];names.append(str(node.get('_name','')));key=parent_key(node)
            if key is None:break
        return '/'.join(reversed(names)) if names else None
    return flat,nodes,node_path


def _iter_skeleton_components(document,namespace):
    flat,_,path_for_node=_node_map(document,namespace)
    for instance_index,obj in flat:
        if not isinstance(obj,dict):continue
        if obj.get('__type__') in ('cc.Node','cc.Scene'):
            for ordinal,value in enumerate(obj.get('_components',[]) or []):
                if isinstance(value,dict) and value.get('__type__')=='sp.Skeleton':
                    inline_index=f'{instance_index}/components/{ordinal}'
                    yield inline_index,value,str(instance_index),path_for_node(instance_index),'inline-node-component'
        elif obj.get('__type__')=='sp.Skeleton':
            node_index=_node_index(obj)
            yield instance_index,obj,str(node_index) if node_index is not None else None,path_for_node(node_index),'top-level-instance'


def _input_receipts(manifest):
    return {(row.get('bundle',manifest.get('bundle')),row.get('path')):row for row in manifest.get('inputs',[])}


def _read_manifest_asset(manifest,asset,receipts,max_bytes=128*1024*1024):
    bundle=asset.get('bundle',manifest.get('bundle'));relative=asset.get('native')
    if not isinstance(relative,str) or not relative:
        return None,{'status':'native_path_missing','path':relative}
    root=manifest.get('sourceRoots',{}).get(bundle)
    if not root:
        return None,{'status':'source_root_missing','bundle':bundle,'path':relative}
    try:raw=read(inside(Path(root),relative),max_bytes=max_bytes)
    except Exception as exc:return None,{'status':'native_read_failed','bundle':bundle,'path':relative,'message':str(exc)}
    receipt=receipts.get((bundle,relative))
    actual=_sha(raw)
    if not receipt:return raw,{'status':'input_receipt_missing','bundle':bundle,'path':relative,'sha256':actual,'bytes':len(raw)}
    valid=receipt.get('sha256')==actual and receipt.get('bytes')==len(raw)
    return raw,{'status':'verified' if valid else 'input_hash_mismatch','bundle':bundle,'path':relative,'sha256':actual,'bytes':len(raw),'receiptSha256':receipt.get('sha256'),'receiptBytes':receipt.get('bytes')}


def _resolve_data_asset(uuid,prefab_bundle,assets_by_source):
    """Resolve component UUID in its source bundle, following only declared redirects."""
    source_id=f'{prefab_bundle}:{uuid}';chain=[];seen=set()
    while True:
        if source_id in seen:return None,{'status':'source_redirect_cycle','uuid':uuid,'redirectChain':chain}
        seen.add(source_id);rows=assets_by_source.get(source_id,[])
        if not rows:return None,{'status':'source_uuid_unresolved','uuid':uuid,'requestedSourceId':source_id,'redirectChain':chain}
        if len(rows)!=1:return None,{'status':'source_uuid_ambiguous','uuid':uuid,'requestedSourceId':source_id,'candidateCount':len(rows),'redirectChain':chain}
        asset=rows[0]
        if asset.get('kind')!='redirect':break
        target=asset.get('redirectTarget')
        chain.append({'sourceId':source_id,'target':target,'targetBundle':asset.get('redirectBundle')})
        if not isinstance(target,str):return None,{'status':'source_redirect_target_missing','uuid':uuid,'redirectChain':chain}
        declared_bundle=asset.get('redirectBundle')
        target_bundle=target.split(':',1)[0] if ':' in target else None
        if declared_bundle and declared_bundle!=target_bundle:
            return None,{'status':'source_redirect_bundle_mismatch','uuid':uuid,'redirectChain':chain}
        source_id=target
    if asset.get('kind')!='sp.SkeletonData':
        return None,{'status':'source_uuid_wrong_kind','uuid':uuid,'candidateSourceId':asset.get('sourceId'),'candidateKind':asset.get('kind'),'redirectChain':chain}
    return asset,{'status':'exact_bundle_uuid_kind_match','sourceId':asset.get('sourceId'),'bundle':asset.get('bundle'),'logicalPath':asset.get('logicalPath'),'redirectChain':chain}


def _resolve_texture(bundle,uuid,assets_by_source):
    source_id=f'{bundle}:{uuid}';chain=[];seen=set()
    while True:
        if source_id in seen:return None,{'status':'redirect_cycle','requestedUuid':uuid,'redirectChain':chain}
        seen.add(source_id);rows=assets_by_source.get(source_id,[])
        if not rows:return None,{'status':'source_id_unresolved','requestedUuid':uuid,'resolvedSourceId':source_id,'redirectChain':chain}
        if len(rows)!=1:return None,{'status':'source_id_ambiguous','requestedUuid':uuid,'resolvedSourceId':source_id,'candidateCount':len(rows),'redirectChain':chain}
        asset=rows[0]
        if asset.get('kind')!='redirect':break
        target=asset.get('redirectTarget')
        chain.append({'sourceId':source_id,'target':target})
        if not isinstance(target,str):return None,{'status':'redirect_target_missing','requestedUuid':uuid,'redirectChain':chain}
        declared_bundle=asset.get('redirectBundle')
        target_bundle=target.split(':',1)[0] if ':' in target else None
        if declared_bundle and declared_bundle!=target_bundle:
            return None,{'status':'redirect_bundle_mismatch','requestedUuid':uuid,'redirectChain':chain}
        source_id=target
    if asset.get('kind')!='cc.Texture2D':
        return None,{'status':'texture_wrong_kind','requestedUuid':uuid,'sourceId':source_id,'kind':asset.get('kind'),'redirectChain':chain}
    return asset,{'status':'exact_bundle_uuid_texture_match','requestedUuid':uuid,'sourceId':source_id,'redirectChain':chain}


def _data_closure(manifest,asset,assets_by_source,receipts):
    result={'sourceId':asset.get('sourceId'),'uuid':asset.get('key'),'bundle':asset.get('bundle'),'logicalPath':asset.get('logicalPath'),
            'nativePath':asset.get('native'),'nativeFormat':Path(asset.get('native') or '').suffix.lower().lstrip('.'),'runtimeLoadClaim':'none'}
    raw,receipt=_read_manifest_asset(manifest,asset,receipts)
    result['skeletonDataReceipt']=receipt
    if raw is not None:
        result['skeletonBinarySha256']=_sha(raw);result['skeletonBinaryBytes']=len(raw)
        result['spineVersion']=binary_version(raw)
        result['versionStatus']='recognized_binary_version' if result['spineVersion'] else 'version_unrecognized'
    else:
        result.update(skeletonBinarySha256=None,skeletonBinaryBytes=None,spineVersion=None,versionStatus='native_binary_unavailable')
    objects=[x for x in asset.get('document',{}).get('instances',[]) if isinstance(x,dict) and x.get('__type__')=='sp.SkeletonData']
    if len(objects)!=1:
        result.update(dataDocumentStatus='skeleton_data_document_missing_or_ambiguous',atlasTextSha256=None,atlasPages=[])
        return result
    obj=objects[0];atlas=obj.get('_atlasText');names=obj.get('textureNames');textures=obj.get('textures')
    if not isinstance(atlas,str) or not isinstance(names,list) or not isinstance(textures,list):
        result.update(dataDocumentStatus='atlas_or_texture_declarations_missing',atlasTextSha256=_sha(str(atlas).encode()) if isinstance(atlas,str) else None,atlasPages=[])
        return result
    try:parsed_pages=atlas_pages(atlas)
    except Exception as exc:
        result.update(dataDocumentStatus='atlas_pages_rejected',atlasParseMessage=str(exc),atlasTextSha256=_sha(atlas.encode('utf-8')),atlasPages=[])
        return result
    if parsed_pages!=names or len(names)!=len(textures):
        result.update(dataDocumentStatus='atlas_page_order_or_texture_count_mismatch',atlasTextSha256=_sha(atlas.encode('utf-8')),atlasPages=[])
        return result
    result.update(dataDocumentStatus='explicit_atlas_and_page_order',atlasTextSha256=_sha(atlas.encode('utf-8')),atlasTextBytes=len(atlas.encode('utf-8')))
    pages=[]
    for index,(page_name,ref) in enumerate(zip(names,textures)):
        uuid=ref.get('__uuid__') if isinstance(ref,dict) else None
        if not isinstance(uuid,str):
            pages.append({'index':index,'pageName':page_name,'status':'texture_uuid_missing'});continue
        texture,match=_resolve_texture(asset.get('bundle',manifest.get('bundle')),uuid,assets_by_source)
        page={'index':index,'pageName':page_name,'textureUuid':uuid,'textureMatch':match}
        if texture:
            page['logicalPath']=texture.get('logicalPath');page['nativePath']=texture.get('native')
            _,page['sourceReceipt']=_read_manifest_asset(manifest,texture,receipts)
        pages.append(page)
    result['atlasPages']=pages
    result['pageClosureStatus']='complete' if all(p.get('textureMatch',{}).get('status')=='exact_bundle_uuid_texture_match' and p.get('sourceReceipt',{}).get('status')=='verified' for p in pages) else 'partial_or_unresolved'
    return result


def build_source_binding_contract(source_manifest,sample_source_prefabs,runtime_evidence=None):
    """Map exact serialized sp.Skeleton UUID references to source assets and receipts."""
    assets=source_manifest.get('assets',[])
    by_source={}
    for a in assets:
        if isinstance(a.get('sourceId'),str):by_source.setdefault(a['sourceId'],[]).append(a)
    receipts=_input_receipts(source_manifest);bindings=[];unbound=[];data_rows={}
    for sample in sample_source_prefabs:
        label=sample.get('id');source_id=sample.get('sourceId');prefab_rows=by_source.get(source_id,[])
        if len(prefab_rows)!=1 or prefab_rows[0].get('kind')!='cc.Prefab':
            status='source_prefab_missing_from_manifest' if not prefab_rows else 'source_prefab_ambiguous_or_wrong_kind'
            unbound.append({'sampleId':label,'prefabSourceId':source_id,'status':status,'candidateCount':len(prefab_rows)})
            continue
        prefab=prefab_rows[0]
        document=prefab.get('document') or {};instances=document.get('instances',[])
        for component_index,component,node_idx,node_path,origin in _iter_skeleton_components(document,source_id):
            raw_fields=_component_fields(component)
            ref=raw_fields.get('_N$skeletonData');uuid=ref.get('__uuid__') if isinstance(ref,dict) else None
            component_id=f'{source_id}#{component_index}'
            row={'sampleId':label,'prefabSourceId':source_id,'prefabSourceUuid':prefab.get('key'),'prefabLogicalPath':prefab.get('logicalPath'),
                 'sourceComponentId':component_id,'sourceComponentType':'sp.Skeleton','componentInstanceIndex':component_index,
                 'sourceOrigin':origin,'nodeInstanceIndex':node_idx,'nodePath':node_path,'serializedFields':raw_fields,
                 'properties':_explicit_properties(raw_fields),'skeletonDataUuid':uuid}
            if uuid is None:
                row.update(status='skeleton_data_uuid_not_serialized',dataAssetSourceId=None)
                unbound.append(row);continue
            data_asset,match=_resolve_data_asset(uuid,prefab.get('bundle',source_manifest.get('bundle')),by_source);row['dataAssetMatch']=match
            if not data_asset:
                row.update(status=match['status'],dataAssetSourceId=None);unbound.append(row);continue
            data_id=data_asset['sourceId'];row.update(status='source_data_uuid_bound',dataAssetSourceId=data_id)
            if data_id not in data_rows:data_rows[data_id]=_data_closure(source_manifest,data_asset,by_source,receipts)
            row['closureStatus']=data_rows[data_id].get('pageClosureStatus','partial_or_unresolved')
            bindings.append(row)
    property_summary={}
    for prop in FIELD_ALIASES:
        rows=[item.get('properties',{}).get(prop,{}) for item in bindings+unbound if item.get('sourceComponentType')=='sp.Skeleton']
        property_summary[prop]={'explicitComponents':sum(row.get('status')=='explicit' for row in rows),
                                'notSerializedDefaultUnresolved':sum(row.get('status')=='not_serialized_default_unresolved' for row in rows)}
    return {'schemaVersion':1,'contractSchema':SCHEMA,'sourceProfile':source_manifest.get('sourceProfile'),
            'sourceVersion':source_manifest.get('sourceVersion'),'sourceManifestSha256':_sha(json_bytes(source_manifest)),
            'sampleCount':len(sample_source_prefabs),'skeletonComponentCount':len(bindings)+len(unbound),
            'boundComponentCount':len(bindings),'unboundComponentCount':len(unbound),
            'uniqueBoundSkeletonDataCount':len(data_rows),'propertySummary':property_summary,'bindings':bindings,'unbound':unbound,
            'skeletonData':list(data_rows.values()),'runtimeEvidence':runtime_evidence or {},
            'nativeIdentityStatus':'not_run','editorStatus':'not_run','playbackStatus':'not_run','callbacksExecuted':False}


def json_bytes(value):
    import json
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')


def recover_private_sidecar(source_manifest,destination,*,allowed_root,namespace):
    """Create an explicit Unity-format closure inside a caller-pinned private root.

    The module has no repository, machine, or sample-specific destination default.
    This writes data/atlas/page files only and does not copy a runtime or claim
    native IDs/playback.
    """
    destination=Path(destination).resolve();allowed=Path(allowed_root).resolve()
    try:destination.relative_to(allowed)
    except ValueError:raise ValueError('Spine sidecar destination must remain inside the authorized private module folder')
    return recover_closures(source_manifest,destination,engine='unity',namespace=namespace)


def freeze_candidate_tree(source_manifest_sha256,closure_report,destination,*,allowed_root):
    """Hash a caller-pinned candidate tree without interpreting GUIDs as native IDs."""
    import json
    destination=Path(destination).resolve();allowed=Path(allowed_root).resolve()
    try:destination.relative_to(allowed)
    except ValueError:raise ValueError('Freeze destination must remain inside the authorized private module folder')
    files=[]
    for path in sorted(destination.rglob('*')):
        if not path.is_file():continue
        raw=path.read_bytes();files.append({'path':path.relative_to(destination).as_posix(),'bytes':len(raw),'sha256':_sha(raw)})
    report_path=destination/'Analysis'/'spine-closures.json'
    return {'schemaVersion':1,'sourceManifestSha256':source_manifest_sha256,'candidatePath':str(destination),
            'closureReportSha256':_sha(report_path.read_bytes()) if report_path.is_file() else None,'fileCount':len(files),
            'files':files,'runtimeCopied':False,'nativeIDs':'not_assigned_or_read_back','editorImport':'not_run','playback':'not_run',
            'closureCounts':{k:closure_report.get(k) for k in ('closed','unresolved','nativeValidation','decodedPages','reusedPages')}}
