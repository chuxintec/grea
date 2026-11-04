import copy
import pytest

from monkey.prefab_component_coverage import assess
from monkey.unity_spine_rendering_coverage import merge,load_bound_receipt
from monkey import io


def fixture():
    sid='source:prefab#1'
    retained=dict(sourceId=sid,status='retained',representation='disabled-source-data-carrier',
                  guid='d'*32,localFileId=1,persistent=True,sourceIdentityVerified=True,verified=True,fieldsVerified=True)
    readback=dict(components=[],retainedComponents=[retained],staticSpineContinuation=dict(status='verified',sourceComponentIds=[sid]),
                  staticPresentationValidation=dict(status='partial',components=[dict(sourceId=sid,sourceVisible=True,verified=False,rendered=False)]))
    rendering=dict(components=[dict(sourceComponentId=sid,sourceNodeId='node',sourceDataAssetId='source:data',
                                   eligible=True,sourceVisible=True,sourceComponentEnabled=True)])
    row=dict(sourceComponentId=sid,sourceDataAssetId='source:data',rendererGuid='e'*32,rendererLocalId=-(1<<63)+1,
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
    plan=dict(nodes=[dict(sourceId='node',active=True,parent=None)],components=[dict(sourceId=sid,type='sp.Skeleton',node='node',enabled=True)],
              staticSpineContinuation=dict(components=[dict(sourceComponentId=sid)]))
    coverage=assess(plan,joined,'unity')
    assert coverage['nativeStaticValidation']=='pass'
    assert coverage['retentionValidation']=='pass'
    assert coverage['staticPresentationValidation']['status']=='pass'
    assert coverage['runtimeCheck']=='not_run'


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
