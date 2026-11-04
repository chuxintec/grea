"""Exact observation candidate, closed options and legacy compatibility."""
import unittest
from jsonschema import Draft202012Validator
from grea.beaver_contracts import documents
from grea.integrations import beaver
from grea.integrations import beaver_operations as ops
from path_support import fixture_path


class ObservationTests(unittest.TestCase):
    def request(self, **changes):
        options = {'manifest': fixture_path('manifest.json'), 'expected': 'a'*64,
                   'duration': 60, 'observation-spec': fixture_path('observation.json'),
                   'expected-observation': 'b'*64, 'deadline-utc': '2030-01-02T03:04:05Z'}
        options.update(changes)
        return dict(schema_version=1, operation='debug.start', options=options, timeout_seconds=30)

    def test_new_options_exact_version_gated_and_old_start_unchanged(self):
        request = self.request()
        ops.validate_provider_version(request, beaver.OBSERVATION_VERSION)
        with self.assertRaises(ValueError):
            ops.validate_provider_version(request, beaver.STABLE_VERSION)
        legacy = dict(request, options={k:v for k,v in request['options'].items()
                                       if k not in ('observation-spec','expected-observation','deadline-utc')})
        ops.validate_provider_version(legacy, beaver.STABLE_VERSION)
        self.assertEqual({name for name in ops.OPERATIONS
                          if beaver.OBSERVATION_VERSION in ops.operation_versions(name)},
                         {'debug.start','debug.inspect','debug.stop','debug.tail'})

    def test_pair_hash_paths_and_arbitrary_execution_options_refused(self):
        request = self.request()
        for missing in ('observation-spec','expected-observation'):
            altered = dict(request['options']); altered.pop(missing)
            with self.assertRaises(ValueError):ops.validate(dict(request, options=altered))
        for change in ({'expected-observation':'bad'}, {'observation-spec':'relative.json'},
                       {'raw-args':['-x']}, {'env':{}}, {'callback':'code'}, {'pid':123}):
            with self.assertRaises(ValueError):ops.validate(self.request(**change))

    def test_utc_deadline_lexical_and_calendar_bounds(self):
        for deadline in ('2030-01-02T03:04:05Z','2030-01-02T03:04:05.123456+00:00'):
            ops.validate(self.request(**{'deadline-utc':deadline}))
        for deadline in ('2030-01-02T03:04:05','2030-01-02T03:04:05+08:00',
                         '2030-13-02T03:04:05Z','2030-01-02T03:04:05.1234567Z','tomorrow'):
            with self.assertRaises(ValueError):ops.validate(self.request(**{'deadline-utc':deadline}))

    def test_schema_pairing_and_version_annotations_match_runtime(self):
        schema = next(row for row in documents()['beaver-operation.schema.json']['oneOf']
                      if row['properties']['operation']['const']=='debug.start')
        validator = Draft202012Validator(schema)
        validator.validate(self.request())
        for name in ('observation-spec','expected-observation','deadline-utc'):
            self.assertEqual(schema['properties']['options']['properties'][name]['x-beaver-versions'],
                             [beaver.OBSERVATION_VERSION])
        options = dict(self.request()['options']); options.pop('expected-observation')
        self.assertFalse(validator.is_valid(dict(self.request(),options=options)))
        self.assertFalse(validator.is_valid(self.request(**{'deadline-utc':'2030-01-02T03:04:05+08:00'})))

    def test_exact_producer_required(self):
        cap = dict(version=beaver.OBSERVATION_VERSION, **beaver.V03_CONTRACTS,
            producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.OBSERVATION_VERSION]['implementation_sha256'],
            capabilities=[dict(id=name,state='implemented')
                          for name in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS)])
        beaver.validate_capabilities(cap)
        with self.assertRaises(ValueError):
            beaver.validate_capabilities(dict(cap,producer_implementation_sha256='0'*64))
