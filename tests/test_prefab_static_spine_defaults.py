import copy
import pytest
from monkey import io,prefab_static_spine_defaults as defaults

@pytest.fixture
def engine(tmp_path,monkeypatch):
    p=tmp_path/'Skeleton.js';p.write_bytes(b'synthetic version-default provider fixture')
    pin=io.sha(p.read_bytes());monkeypatch.setattr(defaults,'ENGINE_SHA',pin)
    return p,pin

def source_plan(*,conflict=False):
    components=[dict(sourceComponentId='spine:node0/component0',
        sourceDataReference=dict(sourceDataAssetId='spine:data0'),
        sourceFieldStates=dict(premultipliedAlpha=dict(present=False,value=None)))]
    if conflict:components.append(dict(sourceComponentId='spine:node1/component0',
        sourceDataReference=dict(sourceDataAssetId='spine:data0'),
        sourceFieldStates=dict(premultipliedAlpha=dict(present=True,value=False))))
    return dict(sourceManifestSha256='a'*64,staticSpineContinuation=dict(
        sourceManifestSha256='a'*64,sourceVersion='2.4.15',sourceProfile='cocos-2.4.15-bundle',
        components=components,dataAssets=[dict(sourceDataAssetId='spine:data0',sourcePma=dict(
            valueKnown=False,value=None,boolValue=False,unknownComponentCount=1,
            knownValues=[False]if conflict else[]))]))

def test_version_default_does_not_rewrite_serialized_source_omission(engine):
    plan=source_plan();before=copy.deepcopy(plan)
    patched,proof=defaults.apply_defaults(plan,*engine)
    data=patched['staticSpineContinuation']['dataAssets'][0]
    assert plan==before
    assert data['sourcePma']==before['staticSpineContinuation']['dataAssets'][0]['sourcePma']
    assert data['effectivePma']['value']is True
    assert defaults.render_pma(data)is True
    assert proof['componentSourceIds']==['spine:node0/component0']
    assert proof['serializedSourceFieldPresencePreserved']is True
    data['effectivePma']['sourceEngineSha256']='0'*64
    assert defaults.render_pma(data)is None

def test_unknown_version_or_changed_engine_refuses(engine):
    plan=source_plan();plan['staticSpineContinuation']['sourceVersion']='2.4.14'
    with pytest.raises(ValueError,match='VERSION_UNSUPPORTED'):defaults.apply_defaults(plan,*engine)
    p,pin=engine;p.write_bytes(b'changed')
    with pytest.raises(ValueError,match='ENGINE_PIN_INVALID'):defaults.apply_defaults(source_plan(),p,pin)

def test_conflicting_effective_component_pma_values_stay_unbound(engine):
    plan=source_plan(conflict=True);patched,proof=defaults.apply_defaults(plan,*engine)
    assert proof['gaps'][0]['code']=='SOURCE_PMA_EFFECTIVE_VALUES_CONFLICT'
    data=patched['staticSpineContinuation']['dataAssets'][0]
    assert 'effectivePma'not in data
    assert defaults.render_pma(data)is None

def test_known_serialized_pma_true_or_false_needs_no_default():
    for value in (True,False):
        assert defaults.render_pma(dict(sourcePma=dict(valueKnown=True,value=value)))is value
    assert defaults.render_pma(dict(sourcePma=dict(valueKnown=False,value=None)))is None
