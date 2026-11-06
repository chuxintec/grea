from types import SimpleNamespace

import pytest

from grea.recovery.unity_runtime_hosts import collect


def test_repeated_script_type_keeps_each_prefab_and_original_slot():
    def obj(kind, **data):
        return SimpleNamespace(type=SimpleNamespace(name=kind), read_typetree=lambda: data)
    def ptr(pid):
        return dict(m_FileID=0,m_PathID=pid)
    source = SimpleNamespace(name='cab',externals=[],objects={})
    for root in (1, 11):
        source.objects[root] = obj('GameObject', m_Name='Button', m_Component=[
            {'component':ptr(root+1)}, {'component':ptr(root+2)}, {'component':ptr(root+3)}])
        source.objects[root+1] = obj('RectTransform',m_Children=[])
        source.objects[root+2] = obj('MonoBehaviour',m_Script=ptr(100))
        source.objects[root+3] = obj('MonoBehaviour',m_Script=ptr(101))
    source.objects[100]=obj('MonoScript',m_ClassName='Button',m_Namespace='A',m_AssemblyName='One.dll')
    source.objects[101]=obj('MonoScript',m_ClassName='Button',m_Namespace='A',m_AssemblyName='Two.dll')
    roots=[dict(asset=f'Assets/{r}.prefab',type='A.Button',assembly='Two',scriptGuid='a'*32,
                rootId=r,cab='CAB') for r in (1,11)]
    hosts=collect(roots,lambda cab:source)
    assert [(h['asset'],h['componentIndex'],h['sourceComponent']) for h in hosts]==[
        ('Assets/1.prefab',2,'4'),('Assets/11.prefab',2,'14')]
    both=collect([roots[0],dict(roots[0],assembly='One',scriptGuid='b'*32)],lambda cab:source)
    assert [h['sourceScriptId'] for h in both]==['101','100']
    with pytest.raises(ValueError,match='No original host'):
        collect([dict(roots[0],assembly='Three')],lambda cab:source)
    with pytest.raises(ValueError,match='duplicate'):
        collect([roots[0],roots[0]],lambda cab:source)
