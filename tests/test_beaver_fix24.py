from path_support import fixture_path
import unittest
from grea.integrations import beaver,beaver_operations as ops
from grea.beaver_contracts import documents


class Fix24Tests(unittest.TestCase):
    def capabilities(self):
        return dict(version=beaver.P0_FIX24_VERSION,**beaver.V03_CONTRACTS,additiveIntakeContract='beaver-additive-intake/2',additiveIntakeSpecVersions=[1,2],producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX24_VERSION]['implementation_sha256'],capabilities=[dict(id=n,state='implemented') for n in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS|{'intake.plan/apply/rollback'})])

    def test_v2_contract_and_exact_producer(self):
        cap=self.capabilities();beaver.validate_capabilities(cap)
        for changes in [dict(additiveIntakeContract='beaver-additive-intake/1'),dict(additiveIntakeSpecVersions=[2]),dict(additiveIntakeSpecVersions=[True,2]),dict(producer_implementation_sha256='0'*64)]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):beaver.validate_capabilities(dict(cap,**changes))

    def test_only_intake_visible_without_changing_old_versions(self):
        actual={name for name in ops.OPERATIONS if beaver.P0_FIX24_VERSION in ops.operation_versions(name)}
        self.assertEqual(actual,{'intake.plan','intake.apply','intake.rollback'})
        variants=documents()['beaver-operation.schema.json']['oneOf']
        self.assertEqual(actual,{v['properties']['operation']['const'] for v in variants if beaver.P0_FIX24_VERSION in v['x-beaver-versions']})
        self.assertNotIn(beaver.P0_FIX24_VERSION,beaver.P0_VERSIONS)
        self.assertNotIn(beaver.P0_FIX24_VERSION,beaver.P0_RETIRE_VERSIONS)
        self.assertFalse(beaver.operation_allowed(beaver.P0_FIX24_VERSION,'project.inspect'))
        self.assertNotIn(beaver.P0_FIX24_VERSION,beaver.P0_SUMMARY_VERSIONS)

    def test_v2_fields_belong_in_provider_spec_not_argv(self):
        q=dict(schema_version=1,operation='intake.plan',options={'candidate':fixture_path('c'),'target':fixture_path('t'),'spec':fixture_path('spec2.json')},timeout_seconds=60)
        ops.validate_provider_version(q,beaver.P0_FIX24_VERSION)
        for name in ['externalAssets','packageScripts','namespace','summary']:
            with self.subTest(name=name),self.assertRaises(ValueError):ops.validate(dict(q,options=dict(q['options'],**{name:True})))

    def test_budget_and_old_runtime_boundaries_unchanged(self):
        for operation,minimum in [('intake.apply',1630),('intake.rollback',1130)]:
            options={'plan' if operation.endswith('apply') else 'transaction':fixture_path('input'),'expected-plan':'a'*64,'editor-path':fixture_path('Editor'),'timeout':500}
            q=dict(schema_version=1,operation=operation,options=options,timeout_seconds=minimum)
            ops.validate_provider_version(q,beaver.P0_FIX24_VERSION)
            with self.assertRaises(ValueError):ops.validate(dict(q,timeout_seconds=minimum-1))
            ops.validate_provider_version(q,beaver.P0_FIX23_VERSION)
            with self.assertRaises(ValueError):ops.validate_provider_version(q,beaver.P0_FIX22_VERSION)
