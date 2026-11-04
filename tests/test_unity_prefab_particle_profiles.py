from copy import deepcopy

import pytest

from monkey.sources.compiled import ParseError
from monkey.unity_prefab_particle_profiles import PROFILE, PREFIX, bounce_constant_profile


def source():
    curve = dict(m_Curve=[], m_PreInfinity=2, m_PostInfinity=2, m_RotationOrder=4)
    obj = dict(type='ParticleSystem', classId=198, sourceObjectId='source-identity', rawSha256='a'*64,
               data=dict(CollisionModule=dict(enabled=False, m_Bounce=dict(minMaxState=0, scalar=1.0,
                   minScalar=1.0, maxCurve=deepcopy(curve), minCurve=deepcopy(curve)))))
    fields = [dict(path=PREFIX+'.minScalar', kind='float', floatValue=1.0),
              dict(path=PREFIX+'.scalar', kind='float', floatValue=1.0),
              dict(path=PREFIX+'.maxCurve.m_Curve.Array.size', kind='integer', intValue=0),
              dict(path='UVModule.frameOverTime.maxCurve.m_Curve.Array.size', kind='integer', intValue=0)]
    return obj, fields


def bridge(obj, fields, versions=None, target='6000.6.2f1'):
    return bounce_constant_profile(obj, versions or ['2021.3.30f1'], target, fields)


def test_exact_source_is_immutable_and_every_raw_value_has_explicit_mapping_evidence():
    obj, fields = source(); before = deepcopy((obj, fields))
    result, evidence = bridge(obj, fields)
    assert (obj, fields) == before
    assert evidence['profile'] == PROFILE and evidence['sourceBounce'] == obj['data']['CollisionModule']['m_Bounce']
    assert evidence['sourceRawSha256'] == obj['rawSha256']
    assert 'not-raw-equality' in evidence['comparison']
    assert result[0]['floatValue'] == 0 and result[0]['sourceExpected'] == '1.0'
    assert result[2]['intValue'] == 2 and result[2]['sourceExpected'] == '0'
    assert result[1] == fields[1] and result[3] == fields[3]  # source scalar/UV remain unchanged
    keys = [row for row in result if '.Array.data[' in row['path']]
    assert len(keys) == 16 and all(row['mapping'] == PROFILE for row in keys)
    assert next(row['floatValue'] for row in keys if row['path'].endswith('[1].time')) == 1
    assert all(row['floatValue'] == 0 for row in keys if row['path'].endswith('.value'))
    result[0]['sourceExpected'] = 'tampered'; evidence['sourceBounce']['scalar'] = 9
    assert (obj, fields) == before


@pytest.mark.parametrize('change', ['enabled','mode','scalar','minScalar','maxCurve','minCurve'])
def test_conditions_never_expand_silently(change):
    obj, fields = source(); collision=obj['data']['CollisionModule']; bounce=collision['m_Bounce']
    if change == 'enabled': collision['enabled'] = True
    elif change == 'mode': bounce['minMaxState'] = 3
    elif change in ('scalar','minScalar'): bounce[change] = 2
    else: bounce[change]['m_Curve'] = [dict(time=0,value=0)]
    with pytest.raises(ParseError, match='UNITY_PREFAB_PARTICLE_PROFILE_CONDITION'): bridge(obj,fields)


@pytest.mark.parametrize('versions,target,cid', [(['2022.3.1f1'],'6000.6.2f1',198),
    (['2021.3.30f1','2021.3.30f1'],'6000.6.2f1',198),(['2021.3.30f1'],'6000.6.1f1',198),
    (['2021.3.30f1'],'6000.6.2f1',199)])
def test_exact_versions_and_builtin_type_are_required(versions,target,cid):
    obj,fields=source();obj['classId']=cid
    with pytest.raises(ParseError,match='UNITY_PREFAB_PARTICLE_PROFILE_VERSION'):bridge(obj,fields,versions,target)


@pytest.mark.parametrize('change',['missing','duplicate','kind','value'])
def test_flattened_plan_cannot_disagree_with_source_data(change):
    obj,fields=source()
    if change=='missing':fields.pop(0)
    elif change=='duplicate':fields.append(deepcopy(fields[0]))
    elif change=='kind':fields[0]['kind']='integer'
    else:fields[0]['floatValue']=2
    with pytest.raises(ParseError,match='UNITY_PREFAB_PARTICLE_PROFILE_FIELDS'):bridge(obj,fields)


def test_unrelated_types_and_fields_are_not_reinterpreted():
    obj,fields=source();obj['type']='MonoBehaviour'
    result,mapping=bridge(obj,fields)
    assert result is fields and mapping is None
    obj['type']='ParticleSystem';obj['data']={}
    assert bridge(obj,fields)==(fields,None)
