import copy
import tempfile
from pathlib import Path

import pytest
from monkey.prefab_static_particle import prepare


def fixture():
    raw = dict(__type__='cc.ParticleSystem', node={'__id__': 0}, _file={'__uuid__': 'effect'},
               _stopped=False, totalParticles=23, gravity={'__value_type__': 0, 'values': [-2, 0.5]},
               _startColor={'__value_type__': 4, 'values': [0xFF123456]})
    node = dict(__type__='cc.Node', _components=[raw])
    manifest = {'assets': [dict(sourceId='bundle:prefab', bundle='bundle', kind='cc.Prefab',
                               document={'instances': [node]}),
                           dict(sourceId='bundle:effect', bundle='bundle', kind='cc.ParticleAsset')]}
    plan = dict(targetProfile='unity-ugui', namespace='example-tool', nodes=[{'sourceId': 'bundle:prefab#0'}],
                components=[dict(sourceId='bundle:prefab#0/components/0', node='bundle:prefab#0',
                                 type='cc.ParticleSystem', enabled=True)])
    return plan, manifest


@pytest.mark.parametrize('target', ['unity-ugui', 'cocos-3.8.8'])
def test_serialized_settings_are_editable_and_simulation_not_claimed(target):
    plan, manifest = fixture()
    original = copy.deepcopy(manifest)
    plan['targetProfile'] = target
    with tempfile.TemporaryDirectory() as directory:
        result = prepare(plan, manifest, Path(directory))
    binding = next(iter(result['bindings'].values()))
    fields = {f['name']: f for f in binding['fields']}
    assert fields['gravity']['numberValues'] == [-2, 0.5]
    assert fields['_startColor']['storageType'] == 'Color'
    assert fields['_file']['refValue'] == 'bundle:effect'
    assert binding['enabled'] is False
    assert binding['dynamicBehaviorComplete'] is False
    assert 'life' not in fields  # absent source defaults are not invented
    assert plan['staticParticleBoundary'][0]['renderingRecovered'] is False
    assert manifest == original


def test_missing_nonempty_particle_reference_fails():
    plan, manifest = fixture()
    manifest['assets'].pop()
    with tempfile.TemporaryDirectory() as directory, pytest.raises(ValueError, match='REFERENCE_UNRESOLVED'):
        prepare(plan, manifest, Path(directory))


def test_retention_selection_excludes_native_node_and_component_references():
    from monkey.prefab_static_retained_assets import _references
    fields = [dict(storageType='UnityEngine.Object', kind=kind, refValue=ref)
              for kind, ref in [('node_ref','prefab#1'), ('component_ref','prefab#2'), ('asset_ref','bundle:file')]]
    rows, gaps = _references({'components': [{'staticFieldBinding': {'fields': fields}}]})
    assert [row['sourceAssetId'] for row in rows] == ['bundle:file']
    assert not gaps
