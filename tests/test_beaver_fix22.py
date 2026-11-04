import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from grea.integrations import beaver,beaver_operations as ops
from grea.beaver_contracts import documents


class Fix22Tests(unittest.TestCase):
    def test_only_collect_visible_in_runtime_and_schema(self):
        version=beaver.P0_FIX22_VERSION
        actual={name for name in ops.OPERATIONS if version in ops.operation_versions(name)}
        self.assertEqual(actual,{'build-filter.collect'})
        schema={x['properties']['operation']['const'] for x in documents()['beaver-operation.schema.json']['oneOf'] if version in x['x-beaver-versions']}
        self.assertEqual(schema,actual)
        self.assertNotIn(version,beaver.P0_VERSIONS)
        self.assertNotIn(version,beaver.P0_RETIRE_VERSIONS)

    def test_collect_summary_and_fixed_producer(self):
        q=dict(schema_version=1,operation='build-filter.collect',options={'project':'/fixture/project space','spec':'/fixture/spec.json','editor-path':'/fixture/Editor','timeout':20,'summary':True},timeout_seconds=30)
        ops.validate_provider_version(q,beaver.P0_FIX22_VERSION)
        argv=ops.argv_for(q,'/fixture/receipt');self.assertIn('--summary',argv);self.assertIn('/fixture/project space',argv)
        self.assertIn(beaver.P0_FIX22_VERSION,beaver.P0_SUMMARY_VERSIONS)
        with self.assertRaises(ValueError):ops.validate(dict(q,options=dict(q['options'],includeObjectIdentities=True)))
        cap=dict(version=beaver.P0_FIX22_VERSION,**beaver.V03_CONTRACTS,producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX22_VERSION]['implementation_sha256'],capabilities=[dict(id=n,state='implemented') for n in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS|{'build-filter.collect/plan'})])
        beaver.validate_capabilities(cap)
        with self.assertRaises(ValueError):beaver.validate_capabilities(dict(cap,producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX21_VERSION]['implementation_sha256']))

    def test_legacy_inspect_cannot_bypass_scoped_gate(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();project=root/'project';project.mkdir();lock=root/'lock.json';lock.write_text(json.dumps({'version':beaver.P0_FIX22_VERSION}))
            with patch('grea.integrations.monkey.local.readiness',return_value={'ready':True}),patch.object(beaver,'check',return_value={'ready':True}),patch('grea.runner.execute') as execute:
                result=beaver.inspect_project(lock,project,root/'out')
            self.assertFalse(result['executed']);self.assertIn('scoped',result['diagnostic']);execute.assert_not_called()
