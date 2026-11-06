import unittest

from monkey.prefab_static_asset_dependencies import (
    PrefabDependencyError,
    plan_source_prefab_dependencies,
)


def prefab(source_id, nodes):
    return {'sourceId': source_id, 'nodes': nodes}


def static_component(source_id, node, fields):
    return {'sourceId': source_id, 'node': node,
            'staticFieldBinding': {'fields': fields}}


class PrefabStaticAssetDependencyTests(unittest.TestCase):
    def test_orders_prefab_instances_scalar_array_and_record_targets_before_owners(self):
        plan = {
            'sourcePrefabs': [
                prefab('owner', ['n-owner']), prefab('leaf-a', ['n-a']),
                prefab('leaf-b', ['n-b']), prefab('nested-owner', ['n-nested']),
            ],
            'prefabInstances': [{'owner': 'nested-owner', 'template': 'leaf-a', 'root': 'n-nested'}],
            'components': [
                static_component('owner-comp', 'n-owner', [
                    {'name': 'reward', 'sourceFieldName': 'reward', 'sourceDeclaredType': 'cc.Prefab',
                     'storageType': 'UnityEngine.Object', 'refValue': 'leaf-a'},
                    {'name': 'items', 'sourceFieldName': 'items', 'sourceDeclaredType': '[cc.Prefab]',
                     'storageType': 'UnityEngine.Object[]', 'refValues': ['leaf-b', 'leaf-a']},
                    {'name': 'config', 'sourceFieldName': 'config', 'sourceDeclaredType': '__record__',
                     'elementKind': 'record', 'recordValues': [{'index': 0, 'fields': [
                         {'sourceFieldName': 'template', 'sourceDeclaredType': 'cc.Prefab',
                          'storageType': 'UnityEngine.Object', 'refValue': 'leaf-b'}]}]},
                    # A prefab-looking value with a different declaration is not an edge.
                    {'name': 'opaque', 'sourceFieldName': 'opaque', 'sourceDeclaredType': 'cc.Asset',
                     'storageType': 'UnityEngine.Object', 'refValue': 'leaf-a'},
                ]),
            ],
        }
        result = plan_source_prefab_dependencies(plan)
        self.assertLess(result['order'].index('leaf-a'), result['order'].index('owner'))
        self.assertLess(result['order'].index('leaf-b'), result['order'].index('owner'))
        self.assertLess(result['order'].index('leaf-a'), result['order'].index('nested-owner'))
        edges = {(edge['owner'], edge['target']): edge['evidence'] for edge in result['dependencies']}
        self.assertIn(('nested-owner', 'leaf-a'), edges)
        self.assertEqual(len(edges[('owner', 'leaf-a')]), 2)
        self.assertEqual(len(edges[('owner', 'leaf-b')]), 2)
        self.assertEqual(result['gaps'], [])
        for _ in range(3):
            self.assertEqual(plan_source_prefab_dependencies(plan), result)

    def test_missing_target_and_missing_reference_id_are_explicit_gaps(self):
        plan = {
            'sourcePrefabs': [prefab('owner', ['n-owner']), prefab('known', ['n-known'])],
            'prefabInstances': [{'owner': 'owner', 'template': 'not-in-plan'}],
            'components': [static_component('c', 'n-owner', [
                {'sourceFieldName': 'single', 'sourceDeclaredType': 'cc.Prefab',
                 'storageType': 'UnityEngine.Object', 'refValue': 'missing'},
                {'sourceFieldName': 'array', 'sourceDeclaredType': '[cc.Prefab]',
                 'storageType': 'UnityEngine.Object[]', 'refValues': ['known', '']},
                {'sourceFieldName': 'nullPrefab', 'sourceDeclaredType': 'cc.Prefab',
                 'storageType': 'UnityEngine.Object', 'nullExpected': True},
            ])],
        }
        result = plan_source_prefab_dependencies(plan)
        self.assertEqual(set(result['order']), {'owner', 'known'})
        self.assertEqual([(edge['owner'], edge['target']) for edge in result['dependencies']], [('owner', 'known')])
        codes = [gap['code'] for gap in result['gaps']]
        self.assertIn('PREFAB_DEPENDENCY_TARGET_MISSING', codes)
        self.assertIn('PREFAB_DEPENDENCY_REFERENCE_INVALID', codes)
        self.assertEqual(len(result['gaps']), 3)

    def test_ambiguous_node_owner_is_a_gap_and_does_not_guess(self):
        plan = {
            'sourcePrefabs': [prefab('a', ['shared']), prefab('b', ['shared']), prefab('target', ['t'])],
            'components': [static_component('c', 'shared', [
                {'sourceFieldName': 'view', 'sourceDeclaredType': 'cc.Prefab',
                 'storageType': 'UnityEngine.Object', 'refValue': 'target'},
            ])],
        }
        result = plan_source_prefab_dependencies(plan)
        self.assertEqual(result['dependencies'], [])
        self.assertEqual(result['gaps'][0]['code'], 'PREFAB_DEPENDENCY_OWNER_AMBIGUOUS')
        self.assertEqual(result['gaps'][0]['candidateOwners'], ['a', 'b'])

    def test_cycle_fails_with_explicit_cycle_path(self):
        plan = {
            'sourcePrefabs': [prefab('a', ['na']), prefab('b', ['nb'])],
            'components': [
                static_component('ca', 'na', [{'sourceFieldName': 'b', 'sourceDeclaredType': 'cc.Prefab',
                    'storageType': 'UnityEngine.Object', 'refValue': 'b'}]),
                static_component('cb', 'nb', [{'sourceFieldName': 'a', 'sourceDeclaredType': 'cc.Prefab',
                    'storageType': 'UnityEngine.Object', 'refValue': 'a'}]),
            ],
        }
        with self.assertRaises(PrefabDependencyError) as error:
            plan_source_prefab_dependencies(plan)
        self.assertEqual(error.exception.code, 'PREFAB_DEPENDENCY_CYCLE')
        self.assertEqual(error.exception.details['cycle'][0], error.exception.details['cycle'][-1])

    def test_duplicate_source_prefab_identity_fails_closed(self):
        with self.assertRaises(PrefabDependencyError) as error:
            plan_source_prefab_dependencies({'sourcePrefabs': [prefab('a', []), prefab('a', [])]})
        self.assertEqual(error.exception.code, 'PREFAB_DEPENDENCY_SOURCE_ID_DUPLICATE')


if __name__ == '__main__':
    unittest.main()
