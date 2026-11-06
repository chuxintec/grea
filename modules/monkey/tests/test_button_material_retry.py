import copy
import pytest
from monkey.button_material_retry import _targets
from monkey.sources.compiled import ParseError


def fixture(root):
    sprite = dict(sourceId='a:s', type='cc.Sprite', node='a:target', nativeId='s', convertible=False,
                  materials=['a:m'], enabled=True, mode=2, trim=False, spriteFrame='b:f',
                  untrimmedGeometryPolicy='identity-full-frame-zero-offset')
    button = dict(sourceId='a:b', type='cc.Button', node='a:button', nativeId='b', convertible=True,
                  target='a:target', transition=1, staticButtonBinding={'renderReady':True})
    t = dict(id='b:f', size=[18,20], originalSize=[18,20], border=[2,0,3,0], offset=[0,0],path='f.png')
    saved = dict(components=[sprite,button],diagnostics=[dict(sourceId='a:s',code='CUSTOM_MATERIAL_HANDOFF')],textures=[t, dict(t,id='b:f@original',path='original.png')])
    (root/'original.png.meta').write_text('guid: '+'a'*32+'\n')
    return saved, copy.deepcopy(saved)


def test_target_depends_on_exact_source_image(tmp_path):
    ins, plan = fixture(tmp_path)
    [row]=_targets(ins,plan,tmp_path)
    assert (row['buttonId'],row['nodeId'],row['spriteId'],row['texturePath'])==('a:b','a:target','a:s','original.png')
    ins['components'][0]['materials']=['a:other']
    with pytest.raises(ParseError,match='PLAN_MISMATCH'):
        _targets(ins,plan,tmp_path)


def test_ambiguous_or_trimmed_targets_refuse(tmp_path):
    ins, plan = fixture(tmp_path)
    ins['components'].append(dict(ins['components'][0], sourceId='a:another'))
    with pytest.raises(ParseError,match='AMBIGUOUS_TARGET'):
        _targets(ins,plan,tmp_path)
    ins['components'].pop()
    ins['textures'][1]['offset']=[1,0]
    with pytest.raises(ParseError,match='FRAME_GEOMETRY'):
        _targets(ins,plan,tmp_path)


def test_material_handoff_cannot_cover_an_unrelated_renderer_gap(tmp_path):
    ins, plan = fixture(tmp_path)
    plan['diagnostics'].append(dict(sourceId='a:s', code='SPRITE_FRAME_MISSING'))
    with pytest.raises(ParseError, match='OTHER_SOURCE_GAPS'):
        _targets(ins, plan, tmp_path)
