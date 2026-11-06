"""Shared producer-state contract used before source acceptance or resource sealing."""
import copy
import pytest
from grea.recovery.native_readback_contract import saved_readback_admission


def observation():
    return dict(status='imported',unityVersion='6000.6.2f1',missingScripts=0,
                editableRoundtrip=True,sceneReopened=True,nativeScope='source-node-subset',
                sourceGraphVerification='saved-source-node-subset',
                nativeFiles=[dict(path='Assets/Native.prefab',sha256='a'*64)])


@pytest.mark.parametrize('status',['imported','pass','partial'])
def test_actual_producer_states_are_admitted_without_claiming_component_acceptance(status):
    rb=observation();rb['status']=status
    result=saved_readback_admission(rb)
    assert result['valid']
    assert result['scope']=='saved-source-node-subset'
    assert 'nativeStaticValidation'not in result


@pytest.mark.parametrize('field,value',[
    ('status','passed'),('status','invented-success'),('missingScripts',3),
    ('missingScripts',False),('missingScripts',0.0),('unityVersion','6000.6.1f1'),
    ('editableRoundtrip',False),('editableRoundtrip',1),('sceneReopened',False),
    ('nativeScope','resources-and-gallery-only'),('sourceGraphVerification','not_run')])
def test_wrong_state_graph_version_or_reopen_is_not_admitted(field,value):
    rb=observation();rb[field]=value
    assert not saved_readback_admission(rb)['valid']


def test_gallery_is_only_admitted_for_explicit_gallery_consumption():
    rb=observation();rb.update(nativeScope='resources-and-gallery-only',sourceGraphVerification='not_run')
    assert not saved_readback_admission(rb)['valid']
    assert saved_readback_admission(rb,gallery=True)['valid']
    assert not saved_readback_admission(observation(),gallery=True)['valid']


@pytest.mark.parametrize('rows',[
    [],None,[None],[dict(path='../escape',sha256='a'*64)],
    [dict(path='Assets//Native.prefab',sha256='a'*64)],
    [dict(path='Assets/Native.prefab',sha256='A'*64)],
    [dict(path='Assets/Native.prefab',sha256='a'*64)]*2])
def test_native_inventory_requires_unique_owned_paths_and_actual_digest_shape(rows):
    rb=observation();rb['nativeFiles']=rows
    before=copy.deepcopy(rb)
    result=saved_readback_admission(rb)
    assert not result['valid']
    assert any(x['code']=='NATIVE_FILE_INVENTORY_INVALID'for x in result['issues'])
    assert rb==before


def test_saved_producer_pins_bind_the_actual_owned_plan_and_original_manifest():
    rb=observation();rb.update(importPlanSha256='b'*64,sourceManifestSha256='c'*64)
    assert saved_readback_admission(rb,expected_plan_sha256='b'*64,expected_source_manifest_sha256='c'*64)['valid']
    for plan,source in [('d'*64,'c'*64),('b'*64,'d'*64),('b'*64,None)]:
        result=saved_readback_admission(rb,expected_plan_sha256=plan,expected_source_manifest_sha256=source)
        assert not result['valid']
        assert any(row['code']=='NATIVE_READBACK_PLAN_IDENTITY_INVALID'for row in result['issues'])
