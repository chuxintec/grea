import copy
import json
import pytest
from grea.recovery.targets.unity import label_font_matches, source_ttf_shrink_evidence
from grea.recovery.prefab_static_text_continuation import SCHEMA,SOURCE_PROFILE,SOURCE_VERSION,_SOURCE_ENGINE_PINS,_RAW_BASE


def fixture(kind='system-font',wrap=False):
    binding={'sourceLabelId':'label','sourceSystemFont':True,'nativeFontAssetId':'font'}
    spec={'sourceId':'label','font':'font','systemFont':kind=='system-font','nativeSystemFontBinding':binding,
          'nativeTextSizingPolicy':'cocos24-ttf-shrink-v1','text':'same text','fontSize':42,'overflow':2}
    native={'kind':kind,'binding':binding}if kind=='system-font'else {'kind':kind,'assetIds':['font']}
    group={'sourceLabelId':'label','fontKind':kind,'sourceText':spec['text'],'sourceFontSize':42,
           'sourceOverflow':2,'sourceWrap':wrap,'nativeFontBinding':native,
           'layoutPolicy':{'profile':'cocos-2.4.15-ttf-label-v1','shrinkPolicy':
              'wrapped-integer-binary-search-v2.4.15'if wrap else 'unwrapped-scale-floor-v2.4.15',
              'sourceShrinkLowerBound':0,'targetAutoSizeMin':0,'targetAutoSizing':True,
              'sourceFontSizeMaximum':42,'targetAutoSizeMax':42}}
    fragment={'contract':SCHEMA,'schemaVersion':1,'sourceProfile':SOURCE_PROFILE,'sourceVersion':SOURCE_VERSION,
              'sourceManifestSha256':'a'*64,'components':[group],
              'sourceEngineFiles':[{'logicalPath':p,'sha256':h,'bytes':1,'originUrl':_RAW_BASE+p}
                  for p,h in _SOURCE_ENGINE_PINS.items()]}
    instruction={'sourceManifestSha256':'a'*64,'staticTextContinuationJson':json.dumps(fragment)}
    actual={'fontGuid':'b'*32,'text':spec['text'],'allCharactersPresent':True,'autoSizeReadback':True,
            'autoSizing':True,'fontSizeMin':0,'fontSizeMax':42,'fontSize':19.8}
    return spec,actual,{'guid':'b'*32},instruction,fragment


@pytest.mark.parametrize('kind',['system-font','explicit-ttf'])
@pytest.mark.parametrize('wrap',[False,True])
def test_source_pinned_ttf_zero_floor_accepts_actual_shrink_without_weakening_identity(kind,wrap):
    spec,actual,font,instruction,_=fixture(kind,wrap)
    assert not label_font_matches(spec,actual,font)
    evidence=source_ttf_shrink_evidence(instruction)['label']
    assert label_font_matches(spec,actual,font,source_sizing=evidence)
    for change in ({'fontGuid':'wrong'},{'text':'changed'},{'allCharactersPresent':False},
                   {'fontSizeMin':-1},{'fontSize':43},{'fontSizeMax':41},{'autoSizing':False}):
        assert not label_font_matches(spec,dict(actual,**change),font,source_sizing=evidence)


@pytest.mark.parametrize('mutation',[
    lambda f:f.update(sourceVersion='2.4.14'),
    lambda f:f.update(sourceManifestSha256='c'*64),
    lambda f:f['sourceEngineFiles'][0].update(sha256='0'*64),
    lambda f:f['sourceEngineFiles'][0].update(originUrl='https://untrusted.invalid/source'),
    lambda f:f['components'].append(copy.deepcopy(f['components'][0])),
    lambda f:f['sourceEngineFiles'][0].update(logicalPath=[]),
    lambda f:f['components'][0].update(sourceLabelId=[]),
])
def test_bad_source_version_pins_and_duplicate_denominator_do_not_supply_zero_floor(mutation):
    _,_,_,instruction,fragment=fixture();mutation(fragment)
    instruction['staticTextContinuationJson']=json.dumps(fragment)
    assert source_ttf_shrink_evidence(instruction)=={}


def test_bitmap_and_changed_source_policy_cannot_claim_ttf_zero_floor():
    spec,actual,font,instruction,_=fixture();evidence=source_ttf_shrink_evidence(instruction)['label']
    for policy in ({'targetAutoSizeMin':1},{'sourceShrinkLowerBound':1},{'targetAutoSizeMax':41},
                   {'shrinkPolicy':'unknown'}):
        bad=copy.deepcopy(evidence);bad['layoutPolicy'].update(policy)
        assert not label_font_matches(spec,actual,font,source_sizing=bad)
    assert not label_font_matches(dict(spec,systemFont=False,nativeTextSizingPolicy='bitmap'),actual,font,source_sizing=evidence)
    bad=copy.deepcopy(evidence);bad['nativeFontBinding']['binding']['sourceLabelId']='other'
    assert not label_font_matches(spec,actual,font,source_sizing=bad)
