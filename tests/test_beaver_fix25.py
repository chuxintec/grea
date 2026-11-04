from path_support import fixture_path
import unittest
from grea.integrations import beaver,beaver_operations as ops
from grea.beaver_contracts import documents


class Fix25Tests(unittest.TestCase):
    def test_exact_v2_contract_and_producer(self):
        cap=dict(version=beaver.P0_FIX25_VERSION,**beaver.V03_CONTRACTS,additiveIntakeContract='beaver-additive-intake/2',additiveIntakeSpecVersions=[1,2],producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX25_VERSION]['implementation_sha256'],capabilities=[dict(id=n,state='implemented') for n in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS|{'intake.plan/apply/rollback'})])
        beaver.validate_capabilities(cap)
        for changes in [dict(producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX24_VERSION]['implementation_sha256']),dict(additiveIntakeSpecVersions=[2]),dict(additiveIntakeContract='beaver-additive-intake/1')]:
            with self.assertRaises(ValueError):beaver.validate_capabilities(dict(cap,**changes))

    def test_surface_and_schema_are_intake_only(self):
        actual={name for name in ops.OPERATIONS if beaver.P0_FIX25_VERSION in ops.operation_versions(name)}
        self.assertEqual(actual,{'intake.plan','intake.apply','intake.rollback'})
        variants=documents()['beaver-operation.schema.json']['oneOf']
        self.assertEqual(actual,{v['properties']['operation']['const'] for v in variants if beaver.P0_FIX25_VERSION in v['x-beaver-versions']})
        self.assertFalse(beaver.operation_allowed(beaver.P0_FIX25_VERSION,'project.inspect'))
        self.assertNotIn(beaver.P0_FIX25_VERSION,beaver.P0_VERSIONS|beaver.P0_RETIRE_VERSIONS|beaver.P0_SUMMARY_VERSIONS)

    def test_budgets_and_no_traversal_override(self):
        for operation,minimum in [('intake.apply',1630),('intake.rollback',1130)]:
            options={'plan' if operation.endswith('apply') else 'transaction':fixture_path('input'),'expected-plan':'a'*64,'editor-path':fixture_path('Editor'),'timeout':500}
            q=dict(schema_version=1,operation=operation,options=options,timeout_seconds=minimum)
            ops.validate_provider_version(q,beaver.P0_FIX25_VERSION)
            with self.assertRaises(ValueError):ops.validate(dict(q,timeout_seconds=minimum-1))
            with self.assertRaises(ValueError):ops.validate(dict(q,options=dict(options,skipReferences=True)))
