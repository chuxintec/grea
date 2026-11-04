import unittest
from grea.integrations import beaver, beaver_operations as ops
from grea.beaver_contracts import documents


class Fix26Tests(unittest.TestCase):
    def request(self, operation, inner, outer):
        key = 'plan' if operation == 'intake.apply' else 'transaction'
        return dict(schema_version=1, operation=operation, timeout_seconds=outer,
                    options={key:'/fixture/input', 'expected-plan':'a'*64,
                             'editor-path':'/fixture/Editor', 'timeout':inner})

    def test_exact_v3_identity_and_contract(self):
        cap = dict(version=beaver.P0_FIX26_VERSION, **beaver.V03_CONTRACTS,
                   additiveIntakeContract='beaver-additive-intake/3',
                   additiveIntakeSpecVersions=[1,2,3],
                   producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX26_VERSION]['implementation_sha256'],
                   capabilities=[dict(id=n,state='implemented') for n in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS|{'intake.plan/apply/rollback'})])
        beaver.validate_capabilities(cap)
        for change in [dict(producer_implementation_sha256='0'*64),
                       dict(additiveIntakeContract='beaver-additive-intake/2'),
                       dict(additiveIntakeSpecVersions=[1,2]),
                       dict(additiveIntakeSpecVersions=[True,2,3])]:
            with self.assertRaises(ValueError):
                beaver.validate_capabilities(dict(cap, **change))

    def test_only_intake_and_matching_schema_budgets(self):
        version=beaver.P0_FIX26_VERSION
        wanted={'intake.plan','intake.apply','intake.rollback'}
        self.assertEqual({n for n in ops.OPERATIONS if version in ops.operation_versions(n)},wanted)
        variants=documents()['beaver-operation.schema.json']['oneOf']
        self.assertEqual({v['properties']['operation']['const'] for v in variants if version in v['x-beaver-versions']},wanted)
        for v in variants:
            name=v['properties']['operation']['const']
            if name in ('intake.apply','intake.rollback'):
                b=v['x-beaver-version-budgets'][version]
                self.assertEqual((b['nativePhases'],b['overheadSeconds'],b['maximumTimeout']),
                                 (5,310,280) if name=='intake.apply' else (2,160,280))
        self.assertNotIn(version,beaver.P0_VERSIONS|beaver.P0_RETIRE_VERSIONS|beaver.P0_SUMMARY_VERSIONS)

    def test_new_budget_boundaries_and_old_runtime_compatibility(self):
        for operation,phases,overhead in [('intake.apply',5,310),('intake.rollback',2,160)]:
            for inner in (1,180,280):
                q=self.request(operation,inner,phases*inner+overhead)
                ops.validate_provider_version(q,beaver.P0_FIX26_VERSION)
                with self.assertRaises(ValueError):
                    ops.validate_provider_version(dict(q,timeout_seconds=q['timeout_seconds']-1),beaver.P0_FIX26_VERSION)
            with self.assertRaises(ValueError):
                ops.validate_provider_version(self.request(operation,281,1800),beaver.P0_FIX26_VERSION)
            old=self.request(operation,500,1630 if phases==5 else 1130)
            for version in (beaver.P0_FIX23_VERSION,beaver.P0_FIX24_VERSION,beaver.P0_FIX25_VERSION):
                ops.validate_provider_version(old,version)
            with self.assertRaises(ValueError):
                ops.validate_provider_version(old,beaver.P0_FIX26_VERSION)

    def test_no_extra_argv_for_compiler_or_character(self):
        q=self.request('intake.apply',180,1210)
        for key in ('newScripts','skipReferences','executeMethod','maximumNativePhases'):
            with self.assertRaises(ValueError):
                ops.validate_provider_version(dict(q,options=dict(q['options'],**{key:True})),beaver.P0_FIX26_VERSION)
        self.assertEqual(ops.argv_for(q,'/fixture/new')[:2],['intake','apply'])
