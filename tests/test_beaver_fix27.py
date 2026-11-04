from path_support import fixture_path
import unittest
from grea.integrations import beaver, beaver_operations as ops
from grea.beaver_contracts import documents

class Fix27Tests(unittest.TestCase):
    def test_exact_combined_capabilities_and_no_old_identity(self):
        wanted=beaver.V02_OPERATIONS|beaver.V03_GROUPS|beaver.VIRTUAL_OPERATIONS|beaver.VIRTUAL_BOOTSTRAP_OPERATIONS|{'intake.plan/apply/rollback'}
        cap=dict(version=beaver.P0_FIX27_VERSION,**beaver.V03_CONTRACTS,additiveIntakeContract='beaver-additive-intake/3',additiveIntakeSpecVersions=[1,2,3],producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX27_VERSION]['implementation_sha256'],capabilities=[dict(id=n,state='implemented') for n in sorted(wanted)])
        beaver.validate_capabilities(cap)
        for change in [dict(producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.VIRTUAL4_VERSION]['implementation_sha256']),dict(additiveIntakeSpecVersions=[1,2]),dict(capabilities=[r for r in cap['capabilities'] if r['id']!='qa.virtual-stop']),dict(capabilities=[r for r in cap['capabilities'] if r['id']!='intake.plan/apply/rollback'])]:
            with self.assertRaises(ValueError):beaver.validate_capabilities(dict(cap,**change))

    def test_exact_eleven_routes_in_runtime_and_schema(self):
        version=beaver.P0_FIX27_VERSION;wanted=beaver.VIRTUAL_OPERATIONS|beaver.VIRTUAL_BOOTSTRAP_OPERATIONS|{'intake.plan','intake.apply','intake.rollback'}
        self.assertEqual({n for n in ops.OPERATIONS if version in ops.operation_versions(n)},wanted)
        variants=documents()['beaver-operation.schema.json']['oneOf']
        self.assertEqual({v['properties']['operation']['const'] for v in variants if version in v['x-beaver-versions']},wanted)
        for name in ('qa.bind','qa.input','project.inspect','unity.assets.retire'):
            self.assertFalse(beaver.operation_allowed(version,name))
        self.assertNotIn(version,beaver.P0_VERSIONS)

    def test_same_intake_phase_budget_and_closed_stop_request(self):
        for operation,phases,overhead in [('intake.apply',5,310),('intake.rollback',2,160)]:
            key='plan' if operation=='intake.apply' else 'transaction'
            q=dict(schema_version=1,operation=operation,options={key:fixture_path('input'),'expected-plan':'a'*64,'editor-path':fixture_path('Editor'),'timeout':180},timeout_seconds=phases*180+overhead)
            ops.validate_provider_version(q,beaver.P0_FIX27_VERSION)
            with self.assertRaises(ValueError):ops.validate_provider_version(dict(q,timeout_seconds=q['timeout_seconds']-1),beaver.P0_FIX27_VERSION)
            self.assertEqual(ops.OPERATIONS[operation]['version_budgets'][beaver.P0_FIX27_VERSION],ops.OPERATIONS[operation]['version_budgets'][beaver.P0_FIX26_VERSION])
        q=dict(schema_version=1,operation='qa.virtual-stop',options={'session':fixture_path('original'),'expected-session':'a'*64},timeout_seconds=90)
        ops.validate_provider_version(q,beaver.P0_FIX27_VERSION)
        for key in ('force','pid','retiredAfterCleanExit','skipLifecycle','fallback'):
            with self.assertRaises(ValueError):ops.validate(dict(q,options=dict(q['options'],**{key:True})))
