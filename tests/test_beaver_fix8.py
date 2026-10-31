import unittest
from grea.integrations import beaver,beaver_operations as ops

class Fix8Tests(unittest.TestCase):
    def test_exact_fix8_producer_and_existing_surface(self):
        cap=dict(version=beaver.P0_FIX8_VERSION,**beaver.V03_CONTRACTS,
            producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX8_VERSION]['implementation_sha256'],
            capabilities=[dict(id=n,state='implemented') for n in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS|beaver.V05_GROUPS|beaver.P0_GROUPS|{'unity.assets.retire/recover'})])
        beaver.validate_capabilities(cap)
        with self.assertRaises(ValueError):beaver.validate_capabilities(dict(cap,producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX7_VERSION]['implementation_sha256']))
        for name in ('build-filter.collect','batch.plan','batch.apply','batch.recover'):
            self.assertIn(beaver.P0_FIX8_VERSION,ops.OPERATIONS[name]['versions'])

    def test_spec_features_are_not_new_cli_options(self):
        for operation,extra in [('build-filter.collect',{'includeObjectIdentities':True}),('batch.plan',{'checkpointPolicy':'move-delta-v1'})]:
            spec=ops.OPERATIONS[operation]
            options={k:1 if k=='timeout' else '/synthetic-fixture/'+k for k in spec['required']}
            req=dict(schema_version=1,operation=operation,options=options,timeout_seconds=30)
            ops.validate_provider_version(req,beaver.P0_FIX8_VERSION)
            with self.assertRaises(ValueError):ops.validate(dict(req,options=dict(options,**extra)))
