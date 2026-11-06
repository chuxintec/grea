"""Exercise the real evidence-normalization, coverage and status gates together.

Readbacks are authored protocol fixtures, not observations from a Unity process.
No function in the verification chain is mocked.
"""
import copy

from grea.recovery.prefab_component_coverage import assess
from grea.recovery.unity_diagnostic_resolution import reconcile
from grea.recovery.unity_verification_contract import coverage_readback, deduplicate_diagnostics, native_diagnostics, statuses


def fixture():
    source='audit:prefab#2'
    node='audit:prefab#1';owner='audit:prefab';path='Assets/audit.prefab'
    base_components=[
        {'guid':'2'*32,'localFileId':1,'componentUuid':'2'*32+':1','nativeType':'UnityEngine.RectTransform',
         'persistent':True,'enabledKnown':True,'enabled':True,'nativeBaseTypes':['UnityEngine.RectTransform','UnityEngine.Component'],
         'sourceComponentIds':[],'role':'unmapped','identityOrigin':'direct-observation','identityPath':['2'*32+':1']},
        {'guid':'2'*32,'localFileId':2,'componentUuid':'2'*32+':2','nativeType':'UnityEngine.CanvasRenderer',
         'persistent':True,'enabledKnown':True,'enabled':True,'nativeBaseTypes':['UnityEngine.CanvasRenderer','UnityEngine.Component'],
         'sourceComponentIds':[],'role':'unmapped','identityOrigin':'direct-observation','identityPath':['2'*32+':2']},
    ]
    image_component={'guid':'1'*32,'localFileId':22,'componentUuid':'1'*32+':22','nativeType':'UnityEngine.UI.Image',
         'persistent':True,'enabledKnown':True,'enabled':True,'nativeBaseTypes':['UnityEngine.UI.Image','UnityEngine.UI.Graphic'],
         'sourceComponentIds':[source],'role':'source-component','identityOrigin':'direct-observation','identityPath':['1'*32+':22']}
    physical=[image_component,*base_components]
    node_row={'sourceId':node,'active':True,'parent':None,'componentTypes':[row['nativeType'] for row in physical],
              'physicalInventoryContract':'monkey-unity-node-physical-components/1',
              'physicalInventoryPhase':'persistent-saved-reopened-node','physicalObservationScope':'saved-scene-correspondence','physicalComponents':physical}
    plan={'nodes':[{'sourceId':node,'active':True,'parent':None}],
          'sourcePrefabs':[{'sourceId':owner,'path':path,'nodes':[node]}],
          'components':[{'sourceId':source,'sourcePrefabId':owner,'node':node,'type':'cc.Sprite',
                         'nativeType':'UnityEngine.UI.Image','convertible':True,'enabled':True,'spriteFrame':'audit:frame'}],
          'diagnostics':[]}
    native={'sourceId':source,'node':node,'type':'cc.Sprite','status':'native','representation':'native-component',
            'nativeType':'UnityEngine.UI.Image','guid':'1'*32,'localFileId':22,'componentUuid':'1'*32+':22',
            'nativeBaseTypes':['UnityEngine.UI.Image','UnityEngine.UI.Graphic'],'sourceIdentityVerified':True,'persistent':True,
            'sourceEnabled':True,'nativeEnabled':True,'sourceVisible':True,'nativeStaticFieldsVerified':True}
    readback={'nodes':[copy.deepcopy(node_row)], 'components':[native],
              'sourcePrefabs':[{'sourceId':owner,'path':path,'nodes':[dict(copy.deepcopy(node_row),physicalObservationScope='saved-source-prefab')],
                                'components':[copy.deepcopy(native)]}],
              'diagnostics':[],
              'staticPresentationValidation':{'components':[{'sourceId':source,'sourceVisible':True,
                                                            'verified':True,'rendered':True}]}}
    readback.update(sceneComponentContract='monkey-unity-saved-scene-components/1',sceneComponentPhase='saved-scene-reopened',
                    sceneComponents=[dict(copy.deepcopy(native),observationScope='saved-scene-correspondence',
                                          identityOrigin='corresponding-prefab-source',identityPath=[native['componentUuid']])])
    for physical_row in readback['nodes'][0]['physicalComponents']:
        physical_row['identityOrigin']='corresponding-prefab-source'
    return plan,readback


def pipeline(plan,readback,spine=None):
    coverage=assess(plan,coverage_readback(readback,spine),'unity')
    diagnostics=deduplicate_diagnostics([*native_diagnostics(readback['diagnostics']),*coverage['diagnostics']])
    reconciliation=reconcile(diagnostics,coverage)
    return coverage,statuses('partial'if readback['diagnostics']else'pass',reconciliation['diagnostics'],coverage,'editor'),reconciliation


def test_complete_static_fixture_and_explicit_dynamic_limit_keep_player_unexecuted():
    for dynamic in (False,True):
        plan,rb=fixture()
        if dynamic:rb['diagnostics']=['ANIMATION_DYNAMIC_CURVES_NOT_LOWERED: audit:prefab#2 explicitly unexecuted dynamic curves']
        coverage,result,_=pipeline(plan,rb)
        assert coverage['sourceComponentCount']==coverage['uniqueSourceComponentCount']==1
        assert result['nativeStaticValidation']==result['staticPresentationValidation']=='pass'
        assert result['runtimeCheck']==result['playerValidation']=='not_run'
        assert rb['diagnostics']==([]if not dynamic else ['ANIMATION_DYNAMIC_CURVES_NOT_LOWERED: audit:prefab#2 explicitly unexecuted dynamic curves'])


def test_unimported_native_diagnostic_remains_visible_and_prevents_static_pass():
    plan,rb=fixture();rb['diagnostics']=['COMPONENT_NOT_IMPORTED: audit:missing#4 unknown-renderer']
    _,result,reconciliation=pipeline(plan,rb)
    assert any(row['code']=='COMPONENT_NOT_IMPORTED'for row in reconciliation['diagnostics'])
    assert result['nativeStaticValidation']!='pass'
    assert result['staticPresentationValidation']!='pass'


def test_missing_source_component_and_unknown_nonconvertible_are_in_denominator():
    for missing in (True,False):
        plan,rb=fixture()
        if missing:
            rb['components']=[]
            rb['sourcePrefabs'][0]['components']=[]
            rb['sceneComponents']=[]
        else:plan['components'].append({'sourceId':'audit:prefab#3','node':'audit:prefab#1',
            'type':'Audit.UnknownVisual','convertible':False,'enabled':True})
        coverage,result,_=pipeline(plan,rb)
        assert len(coverage['components'])==len(plan['components'])
        assert coverage['nativeStaticValidation']=='fail'


def test_missing_visible_proof_or_wrong_identity_cannot_promote_static_pass():
    for mutate in ('presentation','identity','fields'):
        plan,rb=fixture()
        if mutate=='presentation':rb['staticPresentationValidation']['components']=[]
        elif mutate=='identity':rb['components'][0]['sourceIdentityVerified']=False
        else:rb['components'][0]['nativeStaticFieldsVerified']=False
        _,result,_=pipeline(plan,rb)
        assert result['nativeStaticValidation']!='pass'or result['staticPresentationValidation']!='pass'


def test_retained_nonrendering_spine_cannot_close_missing_picture():
    plan,rb=fixture();source=plan['components'][0]['sourceId']
    plan['components'][0].update(type='sp.Skeleton',convertible=False)
    plan['staticSpineContinuation']={'components':[{'sourceComponentId':source}]}
    retained=copy.deepcopy(rb['components'][0]);retained.update(type='sp.Skeleton',nativeBaseTypes=['NativeStaticSpineReference','UnityEngine.MonoBehaviour'],status='retained',
        nativeType='NativeStaticSpineReference',representation='disabled-source-data-carrier',
        nativeEnabled=False,verified=True,fieldsVerified=True)
    rb['components']=[retained]
    rb['sourcePrefabs'][0]['components']=[copy.deepcopy(retained)]
    retained_physical={'guid':retained['guid'],'localFileId':retained['localFileId'],
        'componentUuid':retained['componentUuid'],'nativeType':retained['nativeType'],'persistent':True,
        'enabledKnown':True,'enabled':False,'nativeBaseTypes':['NativeStaticSpineReference','UnityEngine.MonoBehaviour'],
        'sourceComponentIds':[source],'role':'source-component','identityOrigin':'direct-observation','identityPath':['1'*32+':22']}
    for saved_node in [rb['nodes'][0],rb['sourcePrefabs'][0]['nodes'][0]]:
        saved_node['physicalComponents']=[retained_physical,*[row for row in saved_node['physicalComponents']
            if row['nativeType'] in ('UnityEngine.RectTransform','UnityEngine.CanvasRenderer')]]
        saved_node['componentTypes']=[row['nativeType'] for row in saved_node['physicalComponents']]
    coverage,result,_=pipeline(plan,rb,{'status':'verified','sourceComponentIds':[source]})
    assert coverage['retentionValidation']=='pass'
    assert result['nativeStaticValidation']!='pass'
    assert result['staticPresentationValidation']!='pass'
    assert any(row['code']=='SOURCE_VISIBLE_SPINE_NOT_RENDERED'for row in coverage['diagnostics'])
