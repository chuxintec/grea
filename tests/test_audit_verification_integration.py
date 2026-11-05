"""Exercise the real evidence-normalization, coverage and status gates together.

Readbacks are authored protocol fixtures, not observations from a Unity process.
No function in the verification chain is mocked.
"""
import copy

from monkey.prefab_component_coverage import assess
from monkey.unity_diagnostic_resolution import reconcile
from monkey.unity_verification_contract import coverage_readback, deduplicate_diagnostics, native_diagnostics, statuses


def fixture():
    source='audit:prefab#2'
    plan={'nodes':[{'sourceId':'audit:prefab#1','active':True,'parent':None}],
          'components':[{'sourceId':source,'node':'audit:prefab#1','type':'cc.Sprite',
                         'convertible':True,'enabled':True,'spriteFrame':'audit:frame'}],
          'diagnostics':[]}
    native={'sourceId':source,'type':'cc.Sprite','status':'native','representation':'native-component',
            'nativeType':'UnityEngine.UI.Image','guid':'1'*32,'localFileId':22,
            'sourceIdentityVerified':True,'persistent':True,'nativeStaticFieldsVerified':True}
    readback={'components':[native],'diagnostics':[],
              'staticPresentationValidation':{'components':[{'sourceId':source,'sourceVisible':True,
                                                            'verified':True,'rendered':True}]}}
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
        if missing:rb['components']=[]
        else:plan['components'].append({'sourceId':'audit:prefab#3','node':'audit:prefab#1',
            'type':'Audit.UnknownVisual','convertible':False,'enabled':True})
        coverage,result,_=pipeline(plan,rb)
        assert len(coverage['components'])==len(plan['components'])
        assert result['nativeStaticValidation']=='fail'


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
    retained=copy.deepcopy(rb['components'][0]);retained.update(status='retained',
        nativeType='NativeStaticSpineReference',representation='disabled-source-data-carrier',
        nativeEnabled=False,verified=True,fieldsVerified=True)
    rb['components']=[retained]
    coverage,result,_=pipeline(plan,rb,{'status':'verified','sourceComponentIds':[source]})
    assert coverage['retentionValidation']=='pass'
    assert result['nativeStaticValidation']!='pass'
    assert result['staticPresentationValidation']!='pass'
    assert any(row['code']=='SOURCE_VISIBLE_SPINE_NOT_RENDERED'for row in coverage['diagnostics'])
