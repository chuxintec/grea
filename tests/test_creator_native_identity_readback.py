import copy
import unittest

from monkey.targets.cocos import _verify_creator_native_identity_contract


class CreatorNativeIdentityReadbackTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            'projectUuid': 'project-1',
            'assets': [{'sourceId': 'asset-1', 'uuid': 'asset-uuid-1'}],
            'nodes': [{'sourceId': 'node-1'}],
            'components': [{'sourceId': 'component-1', 'convertible': True}],
            'sourcePrefabs': [{'sourceId': 'prefab-1', 'uuid': 'prefab-uuid-1'}],
        }
        self.readback = {
            'creatorVersion': '3.8.8',
            'projectUuid': 'project-1',
            'manifestSha256': 'manifest-hash',
            'assets': [{'sourceId': 'asset-1', 'uuid': 'asset-uuid-1'}],
            'nodes': [{'sourceId': 'node-1', 'nodeUuid': 'native-node-1'}],
            'components': [{'sourceId': 'component-1', 'componentUuid': 'native-component-1'}],
            'sourcePrefabs': [{'sourceId': 'prefab-1', 'uuid': 'prefab-uuid-1'}],
            'nodeCount': 1,
        }

    def codes(self, plan=None, readback=None):
        return {gap['code'] for gap in _verify_creator_native_identity_contract(
            plan or self.plan, readback or self.readback, 'project-1', 'manifest-hash')}

    def test_matching_readback_passes(self):
        self.assertEqual(self.codes(), set())

    def test_version_and_project_identity_drift_fail(self):
        changed = copy.deepcopy(self.readback)
        changed['creatorVersion'] = '3.8.7'
        changed['projectUuid'] = 'other-project'
        self.assertEqual(self.codes(readback=changed), {
            'CREATOR_VERSION_IDENTITY_MISMATCH', 'CREATOR_PROJECT_IDENTITY_MISMATCH'})

    def test_node_source_and_reported_count_drift_fail(self):
        changed = copy.deepcopy(self.readback)
        changed['nodes'][0]['sourceId'] = 'other-node'
        changed['nodeCount'] = 0
        self.assertEqual(self.codes(readback=changed), {
            'CREATOR_NATIVE_SOURCE_COUNT_MISMATCH', 'CREATOR_NATIVE_NODE_COUNT_MISMATCH'})

    def test_asset_and_prefab_native_identity_drift_fail(self):
        changed = copy.deepcopy(self.readback)
        changed['assets'][0]['uuid'] = 'wrong-asset-uuid'
        changed['sourcePrefabs'][0]['uuid'] = 'wrong-prefab-uuid'
        self.assertEqual(self.codes(readback=changed), {'CREATOR_NATIVE_IDENTITY_MISMATCH'})

    def test_component_source_and_native_identity_drift_fail(self):
        changed = copy.deepcopy(self.readback)
        changed['components'][0]['sourceId'] = 'other-component'
        self.assertEqual(self.codes(readback=changed), {'CREATOR_NATIVE_SOURCE_COUNT_MISMATCH'})

    def test_component_native_identity_missing_fails(self):
        changed = copy.deepcopy(self.readback)
        changed['components'][0]['componentUuid'] = ''
        self.assertEqual(self.codes(readback=changed), {'CREATOR_NATIVE_IDENTITY_MISSING'})

if __name__ == '__main__':
    unittest.main()
