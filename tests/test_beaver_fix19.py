import unittest
from grea.integrations import beaver,beaver_operations as ops
from grea.beaver_contracts import documents
import test_beaver_fix18 as fixed18


class Fix19Tests(unittest.TestCase):
    def test_pointer_sync_requires_explicit_backend_and_fixed19(self):
        q=fixed18.Fix18Tests().request(backend='macos-native-ax-pid-pointer-sync/1')
        ops.validate_provider_version(q,beaver.P0_FIX19_VERSION)
        with self.assertRaises(ValueError):ops.validate_provider_version(q,beaver.P0_FIX18_VERSION)
        for version in (beaver.P0_FIX18_VERSION,beaver.P0_FIX19_VERSION):
            ops.validate_provider_version(fixed18.Fix18Tests().request(),version)
            ops.validate_provider_version(fixed18.Fix18Tests().request(backend='macos-native-ax-pid/1'),version)
        self.assertNotIn('--backend',ops.argv_for(fixed18.Fix18Tests().request(),'/fixture/out'))

    def test_contract_exposes_value_gate_and_does_not_allow_cursor_override(self):
        branch=next(x for x in documents()['beaver-operation.schema.json']['oneOf'] if x['properties']['operation']['const']=='qa.bind')
        backend=branch['properties']['options']['properties']['backend']
        self.assertEqual(backend['x-beaver-value-versions']['macos-native-ax-pid-pointer-sync/1'],[beaver.P0_FIX19_VERSION,beaver.P0_FIX21_VERSION,beaver.STABLE_VERSION])
        for value in ('sync-owned-window','global'):
            q=fixed18.Fix18Tests().request(cursorMode=value)
            with self.assertRaises(ValueError):ops.validate(q)

    def test_fixed_producer_cannot_substitute_previous_implementation(self):
        cap=dict(version=beaver.P0_FIX19_VERSION,**beaver.V03_CONTRACTS,producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX19_VERSION]['implementation_sha256'],capabilities=[dict(id=n,state='implemented') for n in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS|beaver.V05_GROUPS|beaver.P0_GROUPS|{'unity.assets.retire/recover'})])
        beaver.validate_capabilities(cap)
        with self.assertRaises(ValueError):beaver.validate_capabilities(dict(cap,producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX18_VERSION]['implementation_sha256']))
