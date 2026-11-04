from path_support import fixture_path
import json
import tempfile
import unittest
from pathlib import Path
from grea.integrations import beaver, beaver_operations as ops


class Fix12Tests(unittest.TestCase):
    def test_fixed_producer_and_previous_surface(self):
        version = beaver.P0_FIX12_VERSION
        cap = dict(version=version, **beaver.V03_CONTRACTS,
            producer_implementation_sha256=beaver.V03_CANDIDATES[version]['implementation_sha256'],
            capabilities=[dict(id=n, state='implemented') for n in sorted(
                beaver.V02_OPERATIONS | beaver.V03_GROUPS | beaver.V05_GROUPS |
                beaver.P0_GROUPS | {'unity.assets.retire/recover'})])
        beaver.validate_capabilities(cap)
        with self.assertRaises(ValueError):
            beaver.validate_capabilities(dict(cap, producer_implementation_sha256=
                beaver.V03_CANDIDATES[beaver.P0_FIX8_VERSION]['implementation_sha256']))
        for name in ('native.readback', 'adoption.plan', 'adoption.apply', 'adoption.rollback',
                     'build-filter.collect', 'batch.plan', 'unity.recover'):
            spec = ops.OPERATIONS[name]
            options = {k: 20 if k == 'timeout' else 'a' * 64 if k in spec.get('hashes', ()) else fixture_path('') + k for k in spec['required']}
            ops.validate_provider_version(dict(schema_version=1, operation=name, options=options, timeout_seconds=30), version)

    def test_owner_selector_belongs_to_provider_spec_not_cli(self):
        request = dict(schema_version=1, operation='native.readback', timeout_seconds=30,
            options=dict(project=fixture_path('Unity'), spec=fixture_path('request.json'),
                         **{'editor-path': fixture_path('Editor')}, timeout=20))
        with self.assertRaises(ValueError):
            ops.validate(dict(request, options=dict(request['options'], ownerIdentity={
                'guid': 'a' * 32, 'localId': 123})))

    def test_large_signed_ids_survive_json_file_read(self):
        # Provider owns selector validation; GREA must not round JSON numbers.
        expected = [9223372036854775807, -6705498737901325648, -9223372036854775808]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'query.json'
            path.write_text(json.dumps(dict(queries=[dict(ownerIdentity=dict(
                guid='a' * 32, localId=n)) for n in expected])))
            actual = ops.read_json(path)
        self.assertEqual([q['ownerIdentity']['localId'] for q in actual['queries']], expected)
        self.assertTrue(all(type(q['ownerIdentity']['localId']) is int for q in actual['queries']))

    def test_reviewed_font_recovery_is_fix12_only(self):
        req=dict(schema_version=1,operation='unity.recover-font-source',options={'transaction':fixture_path('transaction'),'review':fixture_path('review.json'),'expected-plan':'a'*64},timeout_seconds=30)
        ops.validate_provider_version(req,beaver.P0_FIX12_VERSION)
        with self.assertRaises(ValueError):ops.validate_provider_version(req,beaver.P0_FIX11_VERSION)
        with self.assertRaises(ValueError):ops.validate(dict(req,options=dict(req['options'],**{'editor-path':fixture_path('Editor')})))
