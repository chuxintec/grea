from path_support import fixture_path
import unittest
from grea.integrations import beaver,beaver_operations as ops
from grea.beaver_contracts import documents


class Fix23Tests(unittest.TestCase):
    def request(self,operation):
        options=({'candidate':fixture_path('candidate'),'target':fixture_path('target'),'spec':fixture_path('spec.json')} if operation=='intake.plan' else
                 {'plan':fixture_path('plan.json'),'expected-plan':'a'*64,'editor-path':fixture_path('Editor'),'timeout':500} if operation=='intake.apply' else
                 {'transaction':fixture_path('transaction'),'expected-plan':'a'*64,'editor-path':fixture_path('Editor'),'timeout':500})
        return dict(schema_version=1,operation=operation,options=options,timeout_seconds=1630)

    def test_scoped_runtime_and_schema_surface_match(self):
        version=beaver.P0_FIX23_VERSION;wanted={'intake.plan','intake.apply','intake.rollback'}
        self.assertEqual({name for name in ops.OPERATIONS if version in ops.operation_versions(name)},wanted)
        variants=documents()['beaver-operation.schema.json']['oneOf']
        self.assertEqual({v['properties']['operation']['const'] for v in variants if version in v['x-beaver-versions']},wanted)
        self.assertNotIn(version,beaver.P0_VERSIONS);self.assertNotIn(version,beaver.P0_RETIRE_VERSIONS)
        self.assertNotIn(version,beaver.P0_SUMMARY_VERSIONS)
        for name in wanted:
            ops.validate_provider_version(self.request(name),version)
            for old in (beaver.P0_FIX20_VERSION,beaver.P0_FIX21_VERSION,beaver.P0_FIX22_VERSION):
                with self.assertRaises(ValueError):ops.validate_provider_version(self.request(name),old)

    def test_multiphase_budgets_and_required_hashes(self):
        for name,minimum in [('intake.apply',1630),('intake.rollback',1130)]:
            q=self.request(name);q['timeout_seconds']=minimum;ops.validate(q)
            with self.assertRaisesRegex(ValueError,'all native phases'):ops.validate(dict(q,timeout_seconds=minimum-1))
            with self.assertRaises(ValueError):ops.validate(dict(q,options=dict(q['options'],timeout=501)))
            with self.assertRaises(ValueError):ops.validate(dict(q,options=dict(q['options'],timeout=True)))
            with self.assertRaises(ValueError):ops.validate(dict(q,options={k:v for k,v in q['options'].items() if k!='expected-plan'}))

    def test_named_argv_and_no_output_on_rollback(self):
        for name in ('intake.plan','intake.apply','intake.rollback'):
            q=self.request(name);argv=ops.argv_for(q,fixture_path('new'))
            self.assertEqual(argv[:2],['intake',name.split('.')[1]])
            self.assertEqual('--out' in argv,name!='intake.rollback')
            with self.assertRaises(ValueError):ops.validate(dict(q,options=dict(q['options'],summary=True)))
            with self.assertRaises(ValueError):ops.validate(dict(q,options=dict(q['options'],executeMethod='Injected')))

    def test_exact_producer_and_intake_contract(self):
        cap=dict(version=beaver.P0_FIX23_VERSION,**beaver.V03_CONTRACTS,additiveIntakeContract='beaver-additive-intake/1',producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX23_VERSION]['implementation_sha256'],capabilities=[dict(id=n,state='implemented') for n in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS|{'intake.plan/apply/rollback'})])
        beaver.validate_capabilities(cap)
        with self.assertRaises(ValueError):beaver.validate_capabilities(dict(cap,producer_implementation_sha256='0'*64))
        with self.assertRaises(ValueError):beaver.validate_capabilities(dict(cap,additiveIntakeContract='beaver-additive-intake/2'))
        self.assertFalse(beaver.operation_allowed(beaver.P0_FIX23_VERSION,'project.inspect'))
