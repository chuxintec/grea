import copy
import unittest
from grea.integrations import beaver,beaver_operations as ops
from grea.beaver_contracts import validate_result

class Fix7Tests(unittest.TestCase):
    def test_exact_fix7_identity_and_inherited_routes(self):
        cap=dict(version=beaver.P0_FIX7_VERSION,**beaver.V03_CONTRACTS,
            producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX7_VERSION]['implementation_sha256'],
            capabilities=[dict(id=n,state='implemented') for n in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS|beaver.V05_GROUPS|beaver.P0_GROUPS|{'unity.assets.retire/recover'})])
        beaver.validate_capabilities(cap)
        with self.assertRaises(ValueError):
            beaver.validate_capabilities(dict(cap,producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX6_VERSION]['implementation_sha256']))
        for name in ('structure.inspect','structure.plan','unity.plan','unity.apply','unity.recover'):
            spec=ops.OPERATIONS[name]
            self.assertIn(beaver.P0_FIX7_VERSION,spec.get('versions',beaver.SUPPORTED_VERSIONS))
            self.assertIn('summary',spec['flags'])
            if 'summary' in spec.get('option_versions',{}):self.assertIn(beaver.P0_FIX7_VERSION,spec['option_versions']['summary'])

    def test_folder_recovery_summary_is_preserved_without_assuming_identity(self):
        value=dict(schemaVersion=1,contract='beaver-result/1',operationId='recorded-shape-fixture',producer=dict(name='beaver',version=beaver.P0_FIX7_VERSION,implementationSha256=beaver.V03_CANDIDATES[beaver.P0_FIX7_VERSION]['implementation_sha256']),status='partial',actualChanges=[{'operation':'unity.recover','changeRecords':2,'restoredFiles':2}],artifacts=[],diagnostics=[],limitations=[],verification=dict(native='recovery-required',player='not_run',visual='not_run',business='not_run'),data={'deletedFoldersCount':2,'restoredFiles':2,'detailStorage':'complete-report-file'})
        before=copy.deepcopy(value);validate_result(value);self.assertEqual(value,before)
        self.assertNotIn('localId',value['data'])
