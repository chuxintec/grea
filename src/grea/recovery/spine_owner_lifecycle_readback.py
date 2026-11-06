"""Bind source-owner lifetime evidence without treating it as renderer coverage."""
from __future__ import annotations

import math
from pathlib import Path
import re

from .io import load, read, sha

CONTRACT = 'monkey-static-spine-owner-context-lifecycle/1'
EVIDENCE_PATH = 'Analysis/Readback/SpineRendering/owner-context-lifecycle.json'
SOURCE_PATH = 'Analysis/Readback/SpineRendering/source-canvas-context.json'
CONFIG_PATH = 'Assets/Game/Editor/Conversion/spine-static-rendering.json'
IMPORT_PATH = 'Assets/Game/Editor/Conversion/import-plan.json'
_TYPES = ('ScreenSpaceOverlay','ScreenSpaceCamera','WorldSpace')


def _close(a,b):
    return type(a) in (int,float) and type(b) in (int,float) and math.isfinite(a) and math.isfinite(b) and abs(a-b)<=.001


def verify_lifecycle_evidence(rendering, candidate_root, instruction=None, main_readback=None):
    required=rendering.get('ownerContextLifecycleEvidenceContract')
    root=Path(candidate_root).resolve()
    if required is None and not (root/EVIDENCE_PATH).exists():return []
    gaps=[]
    def gap(message,sid=None):
        row={'code':'SPINE_OWNER_LIFECYCLE_UNVERIFIED','message':message,'location':EVIDENCE_PATH}
        if sid:row['sourceId']=sid
        gaps.append(row)
    def raw_file(relative):
        path=root/relative
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):raise ValueError('owned evidence path escapes candidate')
        if any(p.is_symlink() for p in path.parents if p!=root and p.is_relative_to(root)):raise ValueError('symlink ancestor in evidence path')
        return read(path,max_bytes=128*1024*1024)
    try:
        if required not in (None,CONTRACT):raise ValueError('unknown owner lifecycle evidence contract')
        if instruction is None:instruction=load(raw_file(IMPORT_PATH),max_nodes=8_000_000)
        if main_readback is None:main_readback=load(raw_file('Analysis/Readback/editor-readback.json'),max_nodes=8_000_000)
        pins=main_readback.get('staticSpineReadbackFiles')
        if not isinstance(pins,list) or any(not isinstance(x,dict)for x in pins):raise ValueError('main readback does not pin lifecycle evidence')
        pins_by_path={x.get('path'):x.get('sha256')for x in pins}
        if len(pins_by_path)!=len(pins):raise ValueError('repeated auxiliary evidence paths')
        def bound(relative):
            raw=raw_file(relative)
            if sha(raw)!=pins_by_path.get(relative):raise ValueError('auxiliary file SHA differs: '+relative)
            return load(raw,max_nodes=4_000_000)
        envelope=bound(EVIDENCE_PATH);source=bound(SOURCE_PATH)
        config_sha=sha(raw_file(CONFIG_PATH))
        if (envelope.get('schemaVersion')!=1 or envelope.get('contract')!=CONTRACT or envelope.get('phase')!='native-import' or
            envelope.get('sourceManifestSha256')!=rendering.get('sourceManifestSha256') or
            envelope.get('renderingPlanSha256')!=config_sha or
            envelope.get('sourceCanvasEvidenceContract')!='monkey-static-spine-source-canvas-context/1' or
            envelope.get('sourceCanvasEvidenceSha256')!=source.get('evidenceSha256') or
            source.get('renderingPlanSha256')!=config_sha):raise ValueError('lifecycle envelope/source/plan binding differs')
        expected={x['sourceComponentId']:x for x in rendering.get('components',[])if x.get('eligible')is True}
        components=envelope.get('components')
        if not isinstance(components,list) or any(not isinstance(x,dict)for x in components):raise ValueError('lifecycle component table missing')
        observed={x.get('sourceComponentId'):x for x in components}
        if len(observed)!=len(components) or set(observed)!=set(expected):raise ValueError('canonical eligible source component denominator differs')
        source_components={x['sourceComponentId']:x for x in source.get('components',[])}
        source_contexts={x['contextIndex']:x for x in source.get('contexts',[])}
        data_paths={x['sourceDataAssetId']:x['factorySpec']['skeletonDataAssetPath']for x in rendering.get('dataAssets',[])if x.get('eligible')is True}
        native_pins={x['path']:x['sha256']for x in main_readback.get('nativeFiles',[])}
        meta_cache={}
        def asset_guid(path):
            if path not in meta_cache:
                raw=raw_file(path+'.meta')
                if sha(raw)!=native_pins.get(path+'.meta'):raise ValueError('native asset metadata is not pinned: '+path)
                matches=re.findall(r'^guid: ([0-9a-f]{32})$',raw.decode('utf-8'),re.M)
                if len(matches)!=1:raise ValueError('native asset GUID is absent or repeated: '+path)
                meta_cache[path]=matches[0]
            return meta_cache[path]
        saved={}
        for path in pins_by_path:
            if path in (EVIDENCE_PATH,SOURCE_PATH,'Analysis/Readback/spine-static-continuation.json'):continue
            doc=bound(path)
            if doc.get('contract')!='monkey-static-spine-rendering-readback/1':raise ValueError('unexpected saved rendering document')
            for row in doc.get('components',[]):
                sid=row.get('sourceComponentId')
                if sid in saved:raise ValueError('saved renderer component repeats')
                saved[sid]=row
        def identities(row,spec):
            return all(row.get(key) in (None,'') if spec.get(key) in (None,'') else row.get(key)==spec.get(key)
                       for key in ('sourceComponentId','sourceDataAssetId','sourcePrefabId','sourceNodeId','templateComponentId'))
        def persistent_pair_matches(row,spec):
            peer=saved.get(spec['sourceComponentId'],{})
            owners=[x for x in instruction.get('sourcePrefabs',[])if x.get('sourceId')==spec['sourcePrefabId']]
            owner=owners[0] if len(owners)==1 else {}
            return (row.get('priorOwnerPersistent')is True and row.get('actualOwnerPersistent')is False and
                bool(owner.get('path')) and row.get('priorOwnerAssetPath')==owner['path'] and
                row.get('priorOwnerGuid')==asset_guid(owner['path']) and
                row.get('priorOwnerGuid')==peer.get('rendererGuid') and row.get('priorOwnerLocalFileId')==peer.get('rendererLocalId') and
                row.get('dataAssetGuid')==peer.get('dataAssetGuid') and row.get('dataAssetLocalFileId')==peer.get('dataAssetLocalId'))
        for sid,spec in expected.items():
            item=observed[sid];context=source_contexts[source_components[sid]['sourceCanvasContextIndex']]
            path=data_paths[spec['sourceDataAssetId']]
            if (not identities(item,spec) or item.get('eligible')is not True or
                item.get('sourceConstructionOwnerRegistered')is not True or
                item.get('sourceConstructionOwnerType')!='Spine.Unity.SkeletonGraphic' or
                not item.get('sourceConstructionOwnerPath') or
                item.get('sourceConstructionDataAssetPath')!=path or item.get('sourceConstructionDataAssetGuid')!=asset_guid(path) or
                item.get('sourceCanvasEvidenceSha256')!=source.get('evidenceSha256') or
                item.get('sourceCanvasRenderMode')!=context.get('sourceCanvasRenderMode') or
                not _close(item.get('sourceCanvasPpu'),context['sourceCanvasReferencePixelsPerUnit'])):
                gap('construction owner/source/data/context association differs',sid)
        transitions=envelope.get('transitions')
        if not isinstance(transitions,list) or any(not isinstance(x,dict)for x in transitions):raise ValueError('lifecycle transitions missing')
        by_phase={};component_rows={sid:[]for sid in expected}
        for row in transitions:
            sid=row.get('sourceComponentId');spec=expected.get(sid)
            if spec is None:gap('transition has an extra source component',sid);continue
            component_rows[sid].append(row);phase=row.get('phase');by_phase.setdefault(phase,{}).setdefault(sid,[]).append(row)
            context=source_contexts[source_components[sid]['sourceCanvasContextIndex']]
            path=data_paths[spec['sourceDataAssetId']]
            if (not identities(row,spec) or row.get('sourceManifestSha256')!=rendering.get('sourceManifestSha256') or
                row.get('renderingPlanSha256')!=config_sha or row.get('sourceCanvasEvidenceSha256')!=source.get('evidenceSha256') or
                row.get('dataAssetType')!='Spine.Unity.SkeletonDataAsset' or row.get('dataAssetPath')!=path or
                row.get('dataAssetGuid')!=asset_guid(path) or type(row.get('dataAssetLocalFileId'))is not int or not row['dataAssetLocalFileId']):
                gap('transition source/data/provenance association differs',sid)
            if phase=='controlled-host-release':
                if (row.get('registrationStatus')!='released' or row.get('ownerPairRegistered')is not False or
                    row.get('priorOwnerRegistryRevoked')is not True or row.get('verified')is not True or row.get('diagnostic')not in (None,'') or
                    not persistent_pair_matches(row,spec)):
                    gap('controlled host registration was not explicitly released',sid)
                continue
            if (row.get('registrationStatus')!='registered-verified' or row.get('verified')is not True or
                type(row.get('ownerPairRegistered'))is not bool or row.get('diagnostic')not in (None,'') or
                row.get('actualOwnerType')!='Spine.Unity.SkeletonGraphic' or not row.get('actualOwnerPath') or
                row.get('actualCanvasRenderMode')not in _TYPES or
                not _close(row.get('actualCanvasPpu'),context['sourceCanvasReferencePixelsPerUnit']) or
                not _close(row.get('sourceCanvasPpu'),context['sourceCanvasReferencePixelsPerUnit'])):
                gap('owner transition registration or observed Canvas context differs',sid)
            if phase=='native-instance-clone':
                templates=[x for x in instruction.get('components',[])if
                           x.get('sourceId')==spec.get('templateComponentId') and x.get('type')=='sp.Skeleton']
                mappings=[(instance,pair)for instance in instruction.get('prefabInstances',[]) for pair in instance.get('nodes',[])
                          if pair.get('instanceObject')==spec['sourceNodeId'] and instance.get('owner')==spec['sourcePrefabId'] and
                          len(templates)==1 and templates[0].get('node')==pair.get('templateObject')]
                if not any(all(row.get(key)==value for key,value in dict(
                    instanceOwnerPrefabId=instance['owner'],instanceRootNodeId=instance['root'],instanceNodeId=pair['instanceObject'],
                    templatePrefabId=instance['template'],templateNodeId=pair['templateObject']).items())for instance,pair in mappings):
                    gap('native instance source/template node mapping differs',sid)
                if (row.get('ownerPairRegistered')is not True or row.get('priorOwnerType')!='Spine.Unity.SkeletonGraphic' or not row.get('priorOwnerPath') or
                    row.get('priorOwnerPersistent')is not False or row.get('actualOwnerPersistent')is not False or
                    row.get('priorOwnerRegistryRevoked')is not True or row.get('priorOwnerRetired')is not True):
                    gap('replaced owner registry/retirement was not proven',sid)
            if phase=='saved-prefab-owner-pair':
                if row.get('ownerPairRegistered')is not True or not persistent_pair_matches(row,spec):
                    gap('persistent/loaded owner pair differs from saved renderer identity',sid)
        for sid,item in observed.items():
            if item.get('transitions')!=component_rows[sid]:gap('canonical component transition rows differ from event log',sid)
        nested={sid for sid,spec in expected.items()if spec.get('templateComponentId')not in (None,'',sid)}
        capture={x['sourceComponentId']for queue in instruction.get('staticSortQueue',[])for key in ('renderers','nonDrawRenderers')
                 for x in queue.get(key,[])if x.get('sourceType')=='sp.Skeleton' and x.get('sourceComponentId')in expected}
        for phase,ids in [('native-instance-clone',nested),('static-sort-create-capture',capture),
                          ('saved-prefab-owner-pair',set(expected)),('controlled-host-release',set(expected))]:
            missing=ids-set(by_phase.get(phase,{}))
            for sid in sorted(missing):gap('required lifecycle phase is missing: '+phase,sid)
        for sid,events in component_rows.items():
            live_pair=False
            for event in events:
                if event.get('phase')=='saved-prefab-owner-pair':
                    if live_pair:gap('owner pair was rebound before its previous host was released',sid)
                    live_pair=True
                elif event.get('phase')=='controlled-host-release':
                    if not live_pair:gap('owner pair release precedes registration',sid)
                    live_pair=False
            if live_pair:gap('owner pair remains registered at lifecycle completion',sid)
            first_pair=next((i for i,x in enumerate(events)if x.get('phase')=='saved-prefab-owner-pair'),len(events))
            captures=[i for i,x in enumerate(events[:first_pair])if x.get('phase')=='static-sort-create-capture']
            clones=[i for i,x in enumerate(events[:first_pair])if x.get('phase')=='native-instance-clone']
            if sid in capture and not captures:gap('sort creation capture was not recorded before save/reopen',sid)
            if sid in nested and (not clones or sid in capture and not any(c>clones[-1]for c in captures)):
                gap('instance replacement was not registered before its creation capture',sid)
    except (OSError,ValueError,TypeError,KeyError) as error:
        gap(str(error))
    return gaps
