import pytest

from monkey.io import encoded, sha
from monkey.sources.compiled import ParseError
from monkey.unity_prefab_native import freeze, rect_layout_expectations


def test_rect_anchor_layout_uses_source_anchors_and_retains_stale_transform_as_evidence():
    def rect(sid, amin, amax, pivot, size, position):
        return dict(sourceObjectId=sid, data=dict(m_AnchorMin=amin, m_AnchorMax=amax,
            m_Pivot=pivot, m_SizeDelta=size, m_AnchoredPosition=position,
            m_LocalPosition=dict(x=0, y=0, z=0)))
    xy = lambda x, y: dict(x=x, y=y)
    root = rect('rt', xy(0, 0), xy(0, 0), xy(.5, .5), xy(200, 100), xy(0, 0))
    child = rect('ct', xy(.25, .5), xy(.75, 1), xy(.2, .3), xy(20, 30), xy(5, 7))
    graph = dict(roots=[dict(sourceObjectId='r')], reachableObjects=[root, child], gameObjects=[
        dict(sourceObjectId='r', orderedComponents=[dict(type='RectTransform', sourceObjectId='rt')], childSourceObjectIds=['c']),
        dict(sourceObjectId='c', orderedComponents=[dict(type='RectTransform', sourceObjectId='ct')], childSourceObjectIds=[])])
    layouts = rect_layout_expectations(graph)
    assert layouts['ct']['size'] == dict(x=120, y=80)
    assert layouts['ct']['position']['x'] == pytest.approx(-25)
    assert layouts['ct']['position']['y'] == pytest.approx(22)
    assert child['data']['m_LocalPosition'] == dict(x=0, y=0, z=0)


def test_freeze_rejects_old_same_process_only_receipt(tmp_path):
    raw = encoded(dict(status='native-partial', processExited=True))
    (tmp_path / 'execution-result.json').write_bytes(raw)
    with pytest.raises(ParseError, match='UNITY_PREFAB_COLD_NOT_COMPLETE'):
        freeze(tmp_path, sha(raw), tmp_path / 'selected')
    assert not (tmp_path / 'selected').exists()
