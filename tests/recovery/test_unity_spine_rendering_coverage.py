import copy
import pytest

from grea.recovery.prefab_component_coverage import assess
from grea.recovery.unity_spine_rendering_coverage import merge,load_bound_receipt
from grea.recovery import io


def fixture():
    sid='source:prefab#1';owner='source:prefab';path='Assets/source.prefab';renderer_id=-(1<<63)+1
    retained=dict(sourceId=sid,node='node',type='sp.Skeleton',status='retained',representation='disabled-source-data-carrier',
                  nativeType='NativeStaticSpineReference',guid='d'*32,localFileId=1,componentUuid='d'*32+':1',
                  persistent=True,sourceIdentityVerified=True,sourceEnabled=True,nativeEnabled=False,verified=True,fieldsVerified=True)
    native_renderer=dict(sourceId=sid,node='node',type='sp.Skeleton',status='native',representation='native-component',
                  nativeType='Spine.Unity.SkeletonGraphic',guid='e'*32,localFileId=renderer_id,componentUuid='e'*32+':'+str(renderer_id),
                  persistent=True,sourceIdentityVerified=True,sourceEnabled=True,nativeEnabled=True,nativeStaticFieldsVerified=True,
                  sourceVisible=True,coverageRole='native-renderer')
    physical=[
        dict(guid='d'*32,localFileId=1,componentUuid='d'*32+':1',nativeType='NativeStaticSpineReference',persistent=True,
             enabledKnown=True,enabled=False,nativeBaseTypes=['NativeStaticSpineReference','UnityEngine.MonoBehaviour'],
             sourceComponentIds=[sid],role='source-component',identityOrigin='direct-observation',identityPath=['d'*32+':1']),
        dict(guid='e'*32,localFileId=renderer_id,componentUuid='e'*32+':'+str(renderer_id),nativeType='Spine.Unity.SkeletonGraphic',
             persistent=True,enabledKnown=True,enabled=True,nativeBaseTypes=['Spine.Unity.SkeletonGraphic','UnityEngine.UI.Graphic'],
             sourceComponentIds=[sid],role='source-component',identityOrigin='direct-observation',identityPath=['e'*32+':'+str(renderer_id)]),
        dict(guid='a'*32,localFileId=2,componentUuid='a'*32+':2',nativeType='UnityEngine.RectTransform',persistent=True,
             enabledKnown=True,enabled=True,nativeBaseTypes=['UnityEngine.RectTransform','UnityEngine.Component'],sourceComponentIds=[],role='unmapped',identityOrigin='direct-observation',identityPath=['a'*32+':2']),
        dict(guid='a'*32,localFileId=3,componentUuid='a'*32+':3',nativeType='UnityEngine.CanvasRenderer',persistent=True,
             enabledKnown=True,enabled=True,nativeBaseTypes=['UnityEngine.CanvasRenderer','UnityEngine.Component'],sourceComponentIds=[],role='unmapped',identityOrigin='direct-observation',identityPath=['a'*32+':3'])]
    node=dict(sourceId='node',active=True,parent=None,componentTypes=[item['nativeType'] for item in physical],
              physicalInventoryContract='monkey-unity-node-physical-components/1',
              physicalInventoryPhase='persistent-saved-reopened-node',physicalObservationScope='saved-scene-correspondence',physicalComponents=physical)
    readback=dict(nodes=[copy.deepcopy(node)],components=[],retainedComponents=[retained],
                  sourcePrefabs=[dict(sourceId=owner,path=path,nodes=[dict(copy.deepcopy(node),physicalObservationScope='saved-source-prefab')],components=[retained,native_renderer])],
                  staticSpineContinuation=dict(status='verified',sourceComponentIds=[sid]),
                  staticPresentationValidation=dict(status='partial',components=[dict(sourceId=sid,sourceVisible=True,verified=False,rendered=False)]))
    # Independently authored scene observation. The owner renderer receipt
    # below cannot manufacture this separate scope's identity or fields.
    readback.update(sceneComponentContract='monkey-unity-saved-scene-components/1',sceneComponentPhase='saved-scene-reopened',
        sceneComponents=[dict(copy.deepcopy(native_renderer),observationScope='saved-scene-correspondence',
            identityOrigin='corresponding-prefab-source',identityPath=[native_renderer['componentUuid']])])
    for item in readback['nodes'][0]['physicalComponents']:
        item['identityOrigin']='corresponding-prefab-source'
        if item['nativeType']=='NativeStaticSpineReference':
            item['sourceComponentIds']=[];item['role']='unmapped'
    rendering=dict(components=[dict(sourceComponentId=sid,sourcePrefabId=owner,sourceNodeId='node',sourceDataAssetId='source:data',
                                   eligible=True,sourceVisible=True,sourceComponentEnabled=True)])
    row=dict(sourceComponentId=sid,sourcePrefabId=owner,sourceNodeId='node',sourceDataAssetId='source:data',rendererGuid='e'*32,rendererLocalId=renderer_id,
             dataAssetGuid='f'*32,dataAssetLocalId=11400000,sourceVisible=True,sourceComponentEnabled=True,
             rendererEnabled=True,sourceCodeExecuted=False,meshVertexCount=24,meshTriangleCount=12)
    row.update({key:True for key in ('verified','rendererCreated','persistent','dataPersistent','serializedFieldsVerified',
                                    'poseVerified','colorVerified','materialReferencesVerified','unitMappingVerified','sourceVisibleVerified')})
    return readback,rendering,dict(components=[row])


def test_saved_renderer_supplements_retained_proof_without_mutating_it():
    readback,rendering,receipt=fixture();before=copy.deepcopy((readback,rendering,receipt))
    joined=merge(readback,rendering,receipt)
    assert (readback,rendering,receipt)==before
    assert joined['retainedComponents']==readback['retainedComponents']
    sid=rendering['components'][0]['sourceComponentId']
    plan=dict(nodes=[dict(sourceId='node',active=True,parent=None)],
              sourcePrefabs=[dict(sourceId='source:prefab',path='Assets/source.prefab',nodes=['node'])],
              components=[dict(sourceId=sid,sourcePrefabId='source:prefab',type='sp.Skeleton',node='node',enabled=True)],
              staticSpineContinuation=dict(components=[dict(sourceComponentId=sid)]),
              staticSpineRendering=dict(components=[dict(sourceComponentId=sid,sourcePrefabId='source:prefab',
                  sourceNodeId='node',sourceDataAssetId='source:data',eligible=True,sourceVisible=True,sourceComponentEnabled=True)]))
    coverage=assess(plan,joined,'unity')
    assert coverage['nativeStaticValidation']=='pass'
    assert coverage['retentionValidation']=='pass'
    assert coverage['staticPresentationValidation']['status']=='pass'
    assert coverage['runtimeCheck']=='not_run'
    owner_only=copy.deepcopy(joined)
    owner_only.pop('sceneComponents');owner_only.pop('sceneComponentContract');owner_only.pop('sceneComponentPhase')
    assert assess(plan,owner_only,'unity')['nativeStaticValidation']!='pass'


def test_typed_renderer_sidecar_joins_unmapped_physical_graphic_without_mutating_raw_inventory():
    readback,rendering,receipt=fixture()
    readback['sourcePrefabs'][0]['components']=[readback['sourcePrefabs'][0]['components'][0]]
    # The original source coverage sees only the retained data carrier. The
    # independent saved renderer is present physically but has no raw source ID.
    physical=readback['sourcePrefabs'][0]['nodes'][0]['physicalComponents']
    renderer_physical=next(row for row in physical if row['nativeType']=='Spine.Unity.SkeletonGraphic')
    renderer_physical['sourceComponentIds']=[];renderer_physical['role']='unmapped'
    readback['sourcePrefabs'][0]['nodes'][0]['physicalComponents']=copy.deepcopy(physical)
    before=copy.deepcopy(readback)
    joined=merge(readback,rendering,receipt)
    assert readback==before
    sidecar=joined['staticSpineRendering']['components'][0]
    assert sidecar['contract']=='monkey-unity-saved-spine-renderer-owner/1'
    assert sidecar['sourcePrefabId']=='source:prefab' and sidecar['sourceNodeId']=='node'
    sid=rendering['components'][0]['sourceComponentId']
    plan=dict(nodes=[dict(sourceId='node',active=True,parent=None)],
              sourcePrefabs=[dict(sourceId='source:prefab',path='Assets/source.prefab',nodes=['node'])],
              components=[dict(sourceId=sid,sourcePrefabId='source:prefab',type='sp.Skeleton',node='node',enabled=True)],
              staticSpineContinuation=dict(components=[dict(sourceComponentId=sid)]),
              staticSpineRendering=dict(components=[dict(sourceComponentId=sid,sourcePrefabId='source:prefab',
                  sourceNodeId='node',sourceDataAssetId='source:data',eligible=True,sourceVisible=True,sourceComponentEnabled=True)]))
    coverage=assess(plan,joined,'unity')
    assert coverage['nativeStaticValidation']=='pass'
    assert coverage['retentionValidation']=='pass'
    assert coverage['staticPresentationValidation']['status']=='pass'
    assert next(row for row in joined['sourcePrefabs'][0]['nodes'][0]['physicalComponents']
                if row['nativeType']=='Spine.Unity.SkeletonGraphic')['sourceComponentIds']==[]


def test_typed_renderer_sidecar_wrong_owner_or_identity_does_not_bind_unmapped_graphic():
    readback,rendering,receipt=fixture()
    readback['sourcePrefabs'][0]['components']=[readback['sourcePrefabs'][0]['components'][0]]
    physical=readback['nodes'][0]['physicalComponents']
    renderer_physical=next(row for row in physical if row['nativeType']=='Spine.Unity.SkeletonGraphic')
    renderer_physical['sourceComponentIds']=[];renderer_physical['role']='unmapped'
    readback['sourcePrefabs'][0]['nodes'][0]['physicalComponents']=copy.deepcopy(physical)
    joined=merge(readback,rendering,receipt)
    joined['staticSpineRendering']['components'][0]['sourcePrefabId']='other-prefab'
    sid=rendering['components'][0]['sourceComponentId']
    plan=dict(nodes=[dict(sourceId='node',active=True,parent=None)],
              sourcePrefabs=[dict(sourceId='source:prefab',path='Assets/source.prefab',nodes=['node'])],
              components=[dict(sourceId=sid,sourcePrefabId='source:prefab',type='sp.Skeleton',node='node',enabled=True)],
              staticSpineContinuation=dict(components=[dict(sourceComponentId=sid)]),
              staticSpineRendering=dict(components=[dict(sourceComponentId=sid,sourcePrefabId='source:prefab',
                  sourceNodeId='node',sourceDataAssetId='source:data',eligible=True,sourceVisible=True,sourceComponentEnabled=True)]))
    coverage=assess(plan,joined,'unity')
    assert coverage['nativeStaticValidation']!='pass'
    assert coverage['staticPresentationValidation']['status']!='pass'
    assert any(row['code']=='SPINE_RENDERER_OWNER_SIDECAR_INVALID' for row in coverage['diagnostics'])


def test_typed_renderer_sidecar_wrong_persistent_identity_or_source_data_stays_partial():
    for field,value in (("guid", "0"*32), ("sourceDataAssetId", "other-source-data")):
        readback,rendering,receipt=fixture()
        readback['sourcePrefabs'][0]['components']=[readback['sourcePrefabs'][0]['components'][0]]
        for node in (readback['nodes'][0],readback['sourcePrefabs'][0]['nodes'][0]):
            physical=next(row for row in node['physicalComponents'] if row['nativeType']=='Spine.Unity.SkeletonGraphic')
            physical['sourceComponentIds']=[];physical['role']='unmapped'
        joined=merge(readback,rendering,receipt)
        joined['staticSpineRendering']['components'][0][field]=value
        sid=rendering['components'][0]['sourceComponentId']
        plan=dict(nodes=[dict(sourceId='node',active=True,parent=None)],
                  sourcePrefabs=[dict(sourceId='source:prefab',path='Assets/source.prefab',nodes=['node'])],
                  components=[dict(sourceId=sid,sourcePrefabId='source:prefab',type='sp.Skeleton',node='node',enabled=True)],
                  staticSpineContinuation=dict(components=[dict(sourceComponentId=sid)]),
                  staticSpineRendering=dict(components=[dict(sourceComponentId=sid,sourcePrefabId='source:prefab',
                      sourceNodeId='node',sourceDataAssetId='source:data',eligible=True,sourceVisible=True,sourceComponentEnabled=True)]))
        coverage=assess(plan,joined,'unity')
        assert coverage['nativeStaticValidation']!='pass'
        assert coverage['staticPresentationValidation']['status']!='pass'


@pytest.mark.parametrize('changes',[{'rendererLocalId':True},{'rendererLocalId':1<<63},{'meshVertexCount':0},
                                   {'materialReferencesVerified':False},{'dataAssetGuid':None},{'sourceCodeExecuted':True}])
def test_incomplete_or_malformed_renderer_never_becomes_native_proof(changes):
    readback,rendering,receipt=fixture();receipt['components'][0].update(changes)
    with pytest.raises(ValueError,match='EVIDENCE_INVALID'):merge(readback,rendering,receipt)


def test_other_unknown_presentation_and_full_denominator_are_preserved():
    readback,rendering,receipt=fixture()
    readback['staticPresentationValidation']['components'].append(dict(sourceId='source:unknown',verified=False))
    assert merge(readback,rendering,receipt)['staticPresentationValidation']['status']=='partial'
    receipt['components'].append(copy.deepcopy(receipt['components'][0]))
    with pytest.raises(ValueError,match='DENOMINATOR_INVALID'):merge(readback,rendering,receipt)


def test_auxiliary_bytes_are_sealed_by_the_main_readback(tmp_path):
    carrier=tmp_path/'Analysis/Readback/spine-static-continuation.json'
    renderer=tmp_path/'Analysis/Readback/SpineRendering/saved-prefab.json'
    carrier.parent.mkdir(parents=True);renderer.parent.mkdir()
    io.write_json(carrier,{'components':[]})
    io.write_json(renderer,{'components':[{'sourceComponentId':'source:prefab#1','verified':True}]})
    main=dict(staticSpineReadbackFiles=[dict(path=path.relative_to(tmp_path).as_posix(),sha256=io.sha(path.read_bytes()))
                                      for path in (carrier,renderer)])
    assert len(load_bound_receipt(tmp_path,main)['components'])==1
    io.write_json(renderer,{'components':[{'sourceComponentId':'source:prefab#1','verified':False}]})
    with pytest.raises(ValueError,match='BYTES_CHANGED'):load_bound_receipt(tmp_path,main)


def test_canvas_context_rows_are_hash_bound_without_doubling_renderer_denominator(tmp_path):
    carrier=tmp_path/'Analysis/Readback/spine-static-continuation.json'
    renderer=tmp_path/'Analysis/Readback/SpineRendering/saved-prefab.json'
    context=renderer.with_name('source-canvas-context.json')
    carrier.parent.mkdir(parents=True);renderer.parent.mkdir()
    sid='source:prefab#1'
    io.write_json(carrier,{'components':[{'sourceComponentId':sid}]})
    io.write_json(renderer,{'components':[{'sourceComponentId':sid,'verified':True}]})
    io.write_json(context,{'contract':'monkey-static-spine-source-canvas-context/1',
                           'components':[{'sourceComponentId':sid,'sourceNodeActive':False}]})
    main=dict(staticSpineReadbackFiles=[dict(path=path.relative_to(tmp_path).as_posix(),sha256=io.sha(path.read_bytes()))
                                      for path in (carrier,renderer,context)])
    assert load_bound_receipt(tmp_path,main)['components']==[{'sourceComponentId':sid,'verified':True}]
    context.write_bytes(context.read_bytes()+b' ')
    with pytest.raises(ValueError,match='BYTES_CHANGED'):load_bound_receipt(tmp_path,main)


def test_owner_lifecycle_components_are_bound_without_becoming_renderers(tmp_path):
    carrier=tmp_path/'Analysis/Readback/spine-static-continuation.json'
    renderer=tmp_path/'Analysis/Readback/SpineRendering/saved-prefab.json'
    lifecycle=renderer.with_name('owner-context-lifecycle.json')
    carrier.parent.mkdir(parents=True);renderer.parent.mkdir()
    io.write_json(carrier,{'components':[]})
    io.write_json(renderer,{'components':[{'sourceComponentId':'source:one','verified':True}]})
    io.write_json(lifecycle,{'contract':'monkey-static-spine-owner-context-lifecycle/1',
                             'components':[{'sourceComponentId':'source:one'}], 'transitions':[]})
    main=dict(staticSpineReadbackFiles=[dict(path=path.relative_to(tmp_path).as_posix(),sha256=io.sha(path.read_bytes()))
                                      for path in (carrier,renderer,lifecycle)])
    assert len(load_bound_receipt(tmp_path,main)['components'])==1
    lifecycle.write_bytes(lifecycle.read_bytes()+b' ')
    with pytest.raises(ValueError,match='BYTES_CHANGED'):load_bound_receipt(tmp_path,main)
