import unittest
from grea.integrations import beaver,beaver_operations as ops
from grea.beaver_contracts import documents
import test_beaver_fix18 as fixed18


class Fix21Tests(unittest.TestCase):
    def test_matching_input_fix_is_explicit_and_does_not_replace_sdk_pin(self):
        q=fixed18.Fix18Tests().request(backend='macos-native-ax-pid-pointer-sync/1')
        for version in (beaver.P0_FIX19_VERSION,beaver.P0_FIX21_VERSION):ops.validate_provider_version(q,version)
        with self.assertRaises(ValueError):ops.validate_provider_version(q,beaver.P0_FIX20_VERSION)
        sdk=fixed18.Fix18Tests().request('adoption.plan',candidate='/fixture/candidate',target='/fixture/target',**{'sdk-migration':'/fixture/spec.json','expected-sdk-migration':'a'*64})
        ops.validate_provider_version(sdk,beaver.P0_FIX20_VERSION)
        with self.assertRaises(ValueError):ops.validate_provider_version(sdk,beaver.P0_FIX21_VERSION)
        branch=next(x for x in documents()['beaver-operation.schema.json']['oneOf'] if x['properties']['operation']['const']=='qa.bind')
        self.assertEqual(branch['properties']['options']['properties']['backend']['x-beaver-value-versions']['macos-native-ax-pid-pointer-sync/1'],[beaver.P0_FIX19_VERSION,beaver.P0_FIX21_VERSION,beaver.STABLE_VERSION])
