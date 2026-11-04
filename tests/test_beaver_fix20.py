from path_support import fixture_path
import unittest
from grea.integrations import beaver,beaver_operations as ops
from grea.beaver_contracts import documents
import test_beaver_fix18 as fixed18


class Fix20Tests(unittest.TestCase):
    def test_sdk_migration_gate_and_schema_match(self):
        q=fixed18.Fix18Tests().request('adoption.plan',candidate=fixture_path('candidate'),target=fixture_path('target'),**{'sdk-migration':fixture_path('spec.json'),'expected-sdk-migration':'a'*64})
        ops.validate_provider_version(q,beaver.P0_FIX20_VERSION)
        branch=next(x for x in documents()['beaver-operation.schema.json']['oneOf'] if x['properties']['operation']['const']=='adoption.plan')
        self.assertIn(beaver.P0_FIX20_VERSION,branch['properties']['options']['properties']['sdk-migration']['x-beaver-versions'])
        with self.assertRaises(ValueError):ops.validate_provider_version(q,beaver.P0_FIX17_VERSION)

    def test_sdk_candidate_does_not_implicitly_upgrade_qa_binding(self):
        q=fixed18.Fix18Tests().request(backend='macos-native-ax-pid-pointer-sync/1')
        ops.validate_provider_version(q,beaver.P0_FIX19_VERSION)
        with self.assertRaises(ValueError):ops.validate_provider_version(q,beaver.P0_FIX20_VERSION)
        self.assertNotEqual(beaver.V03_CANDIDATES[beaver.P0_FIX20_VERSION]['implementation_sha256'],beaver.V03_CANDIDATES[beaver.P0_FIX19_VERSION]['implementation_sha256'])
