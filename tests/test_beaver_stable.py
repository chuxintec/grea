"""Stable0.6 keeps exact producer and per-operation safety contracts."""
import unittest
from grea.integrations import beaver
from grea.integrations import beaver_operations as ops


class StableBeaverTests(unittest.TestCase):
    def capabilities(self):
        ids = (beaver.V02_OPERATIONS | beaver.V03_GROUPS | beaver.V05_GROUPS |
               beaver.P0_GROUPS | beaver.VIRTUAL_OPERATIONS | beaver.VIRTUAL_BOOTSTRAP_OPERATIONS |
               {'intake.plan/apply/rollback', 'unity.assets.retire/recover', 'qa.inspect-instance', 'qa.bind', 'qa.input'})
        return dict(version=beaver.STABLE_VERSION, **beaver.V03_CONTRACTS,
                    additiveIntakeContract='beaver-additive-intake/5',
                    additiveIntakeSpecVersions=[1, 2, 3, 4, 5],
                    producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.STABLE_VERSION]['implementation_sha256'],
                    capabilities=[dict(id=n, state='implemented') for n in sorted(ids)])

    def test_contract_and_producer_drift_refused(self):
        cap = self.capabilities()
        beaver.validate_capabilities(cap)
        for change in (dict(producer_implementation_sha256='0' * 64),
                       dict(additiveIntakeSpecVersions=[1, 2]),
                       dict(additiveIntakeContract='beaver-additive-intake/4'),
                       dict(capabilities=cap['capabilities'][:-1])):
            with self.assertRaises(ValueError):
                beaver.validate_capabilities(dict(cap, **change))

    def test_intake_native_budget_and_unsafe_extra_option_refused(self):
        request = dict(schema_version=1, operation='intake.apply', timeout_seconds=1710,
            options={'plan': '/fixture/plan', 'expected-plan': 'a' * 64,
                     'editor-path': '/fixture/Editor', 'timeout': 280})
        ops.validate_provider_version(request, beaver.STABLE_VERSION)
        for altered in (dict(request, timeout_seconds=1709),
                        dict(request, options=dict(request['options'], timeout=281)),
                        dict(request, options=dict(request['options'], executeMethod='unsafe'))):
            with self.assertRaises(ValueError):
                ops.validate_provider_version(altered, beaver.STABLE_VERSION)

    def test_historical_scopes_and_transaction_repair_remain_pinned(self):
        self.assertIn(beaver.STABLE_VERSION, ops.operation_versions('intake.plan'))
        self.assertIn(beaver.STABLE_VERSION, ops.operation_versions('qa.virtual-bind'))
        self.assertNotIn(beaver.STABLE_VERSION, ops.operation_versions('unity.recover-font-source'))
        self.assertNotIn(beaver.P0_FIX29_VERSION, ops.operation_versions('qa.virtual-bind'))
        self.assertNotIn(beaver.P0_FIX31_VERSION, ops.operation_versions('intake.plan'))
