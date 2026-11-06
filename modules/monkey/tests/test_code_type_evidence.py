import hashlib
import copy
import tempfile
import unittest
from pathlib import Path

from monkey.code_graph import facts
from monkey.code_type_evidence import extract_type_evidence
from monkey.code_modules import prepare
from monkey.io import write_json
from monkey.sources.compiled import ParseError


SOURCE_TEXT = '''var X=(function(){
function C(){}
C.prototype.scale=function(x){var y=x*2; return y;};
C.prototype.outer=function(v){return this.scale(v);};
C.prototype.add=function(a,b){return a+b;};
C.prototype.concat=function(prefix){return prefix+"!";};
C.prototype.compare=function(v){return v>0;};
C.prototype.bad=function(x){var n=x*2; return x+"!";};
C.prototype.noValue=function(){this.count=1;};
C.prototype.asyncWork=async function(x){return x*2;};
return C;
})();
'''.encode('utf-8')


class CodeTypeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'mini.js'
        self.source.write_bytes(SOURCE_TEXT)
        self.graph = facts(self.source)
        self.cls = self.graph['classes'][0]
        self.by_name = {row['name']: row for row in self.graph['methods']}

    def select(self, name, *, seed=None):
        row = self.by_name[name]
        return extract_type_evidence(self.source, [{'classId': self.cls['id'], 'methodId': row['id']}], seed, namespace='Test.Recovered')

    def test_numeric_operators_and_closed_direct_call_infer_bounded_contract(self):
        result = self.select('outer')
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['dependencies'][self.by_name['outer']['id']], [self.by_name['scale']['id']])
        module = result['contract']['modules'][0]
        methods = {row['name']: row for row in module['methods']}
        self.assertEqual(set(methods), {'outer', 'scale'})
        self.assertEqual(methods['scale']['parameters'], ['Number'])
        self.assertEqual(methods['scale']['returns'], 'Number')
        self.assertEqual(methods['scale']['locals'], {'binding@68': 'Number'})
        self.assertEqual(methods['outer']['parameters'], ['Number'])
        self.assertEqual(methods['outer']['returns'], 'Number')
        self.assertEqual(module['classSha256'], self.cls['sourceSha256'])
        self.assertFalse(result['sourceExecuted'])

    def test_ready_contract_is_accepted_by_existing_module_prepare(self):
        result = self.select('outer')
        contract_path = self.source.parent / 'outer-contract.json'
        write_json(contract_path, result['contract'])
        prepared = prepare(self.source, contract_path)
        self.assertEqual({row['id'] for row in prepared['requests']}, {'RecoveryTypes', 'X', 'SourceEvidence'})

    def test_string_literal_concat_and_numeric_comparison_constrain_parameters(self):
        concat, compare = self.select('concat'), self.select('compare')
        concat_method = concat['contract']['modules'][0]['methods'][0]
        compare_method = compare['contract']['modules'][0]['methods'][0]
        self.assertEqual((concat_method['parameters'], concat_method['returns']), (['String'], 'String'))
        self.assertEqual((compare_method['parameters'], compare_method['returns']), (['Number'], 'Boolean'))

    def test_direct_cross_class_dependency_propagates_parameter_and_return(self):
        source_bytes = b'''var Y=(function(){function B(){}; B.scale=function(x){return x*2;}; return B;})();
var X=(function(){function C(){}; C.prototype.outer=function(v){return Y.scale(v);}; return C;})();\n'''
        source = self.source.parent / 'cross-class.js'
        source.write_bytes(source_bytes)
        graph = facts(source)
        cls = next(row for row in graph['classes'] if row['name'] == 'X')
        method = next(row for row in graph['methods'] if row['name'] == 'outer')
        result = extract_type_evidence(source, [{'classId': cls['id'], 'methodId': method['id']}], namespace='Test.Recovered')
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['contract']['modules'][0]['methods'][0]['parameters'], ['Number'])
        self.assertEqual({module['targetClass'] for module in result['contract']['modules']}, {'X', 'Y'})
        self.assertEqual(result['dependencies'][method['id']], ['method@34'])

    def test_ambiguous_addition_is_a_named_gap_and_does_not_guess_number(self):
        result = self.select('add')
        self.assertEqual(result['status'], 'missing_type_or_dependency_contract')
        self.assertIsNone(result['contract'])
        fillable = result['fillableContract']
        self.assertEqual(fillable['schemaVersion'], 1)
        self.assertEqual(fillable['sourceSha256'], hashlib.sha256(SOURCE_TEXT).hexdigest())
        self.assertEqual(fillable['namespace'], 'Test.Recovered')
        module = fillable['modules'][0]
        self.assertEqual(module['classId'], self.cls['id'])
        self.assertEqual(module['classSha256'], self.cls['sourceSha256'])
        method = module['methods'][0]
        self.assertEqual(method['name'], 'add')
        self.assertEqual(method['parameters'], [None, None])
        self.assertIsNone(method['returns'])
        self.assertEqual({row['field'] for row in fillable['missingEvidence'] if row.get('methodId') == method['id']},
                         {'parameters[0]', 'parameters[1]', 'returns'})
        self.assertTrue(any(row['field'] == 'callDomain' for row in fillable['missingEvidence']))
        self.assertTrue(all(d['code'] != 'CODE_TYPE_EVIDENCE_CONFLICT' for d in result['diagnostics']))

    def test_filled_schema_contract_rechecks_to_ready_and_prepare_accepts_it(self):
        initial = self.select('add')
        filled = copy.deepcopy(initial['fillableContract'])
        method = filled['modules'][0]['methods'][0]
        method['parameters'] = ['Number', 'Number']
        method['returns'] = 'Number'
        filled['callDomain'] = 'Human-reviewed: inputs are finite Number values; addition is numeric.'
        result = self.select('add', seed=filled)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['contract']['callDomain'], filled['callDomain'])
        contract_path = self.source.parent / 'filled-add-contract.json'
        write_json(contract_path, result['contract'])
        prepared = prepare(self.source, contract_path)
        self.assertIn('X', {row['id'] for row in prepared['requests']})

    def test_fillable_schema_keeps_unknown_local_and_field_as_null_with_evidence(self):
        source_bytes = b'var X=(function(){function C(){}; C.prototype.unknown=function(x){var y=x+z; return this.field;}; return C;})();\n'
        source = self.source.parent / 'unknown.js'
        source.write_bytes(source_bytes)
        graph = facts(source)
        cls, method = graph['classes'][0], graph['methods'][0]
        result = extract_type_evidence(source, [{'classId': cls['id'], 'methodId': method['id']}], namespace='Test.Recovered')
        self.assertEqual(result['status'], 'missing_type_or_dependency_contract')
        fillable = result['fillableContract']['modules'][0]
        self.assertIsNone(fillable['fields']['field'])
        self.assertIsNone(fillable['methods'][0]['parameters'][0])
        self.assertIsNone(fillable['methods'][0]['returns'])
        self.assertEqual(fillable['methods'][0]['locals'], {'binding@70': None})
        locations = {item['field'] for item in result['fillableContract']['missingEvidence']}
        self.assertTrue({'fields.field', 'parameters[0]', 'locals.y', 'returns'}.issubset(locations))

    def test_conflicting_constraints_are_rejected(self):
        result = self.select('bad')
        self.assertEqual(result['status'], 'missing_type_or_dependency_contract')
        self.assertTrue(any(row['code'] == 'CODE_TYPE_EVIDENCE_CONFLICT' for row in result['diagnostics']))

    def test_reviewed_seed_is_source_bound_and_supplies_ambiguous_addition(self):
        method = self.by_name['add']
        seed = {'schemaVersion': 1, 'sourceSha256': hashlib.sha256(SOURCE_TEXT).hexdigest(),
                'namespace': 'Test.Recovered', 'records': [], 'modules': [{
                    'id': 'X', 'targetClass': 'X', 'classId': self.cls['id'], 'classSha256': self.cls['sourceSha256'],
                    'fields': {}, 'methods': [{'id': method['id'], 'name': 'add', 'sha256': method['sourceSha256'],
                                               'parameters': ['Number', 'Number'], 'returns': 'Number', 'locals': {}}]}]}
        result = self.select('add', seed=seed)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['contract']['modules'][0]['methods'][0]['parameters'], ['Number', 'Number'])
        wrong = dict(seed, sourceSha256='0' * 64)
        rejected = extract_type_evidence(self.source, [{'classId': self.cls['id'], 'methodId': method['id']}], wrong)
        self.assertEqual(rejected['status'], 'missing_source')
        self.assertEqual(rejected['diagnostics'][0]['code'], 'CODE_GRAPH_SOURCE_IDENTITY')

    def test_reviewed_seed_types_close_calls_and_supply_record_shape_witness(self):
        source_bytes = b'''var X=(function(){function C(){};
C.prototype.get=function(x){return this.check(x);};
C.prototype.check=function(x){return this.item(x)!=null;};
C.prototype.item=function(x){return this._items.get(x);};
C.prototype.read=function(r){return r.ingredients;};
return C;})();\n'''
        source = self.source.parent / 'seeded.js'
        source.write_bytes(source_bytes)
        graph = facts(source)
        cls = graph['classes'][0]
        by_name = {row['name']: row for row in graph['methods']}
        methods = []
        for name, params, returns in (
            ('get', ['Number'], 'Boolean'), ('check', ['Number'], 'Boolean'),
            ('item', ['Number'], 'Optional<Recipe>'), ('read', ['Recipe'], 'Map<Number,Number>'),
        ):
            row = by_name[name]
            methods.append({'id': row['id'], 'name': name, 'sha256': row['sourceSha256'],
                            'parameters': params, 'returns': returns, 'locals': {}})
        seed = {'schemaVersion': 1, 'sourceSha256': hashlib.sha256(source_bytes).hexdigest(),
                'namespace': 'Test.Recovered', 'records': [{'name': 'Recipe', 'fields': {'ingredients': 'Map<Number,Number>'}}],
                'modules': [{'id': 'X', 'targetClass': 'X', 'classId': cls['id'], 'classSha256': cls['sourceSha256'],
                             'fields': {'_items': 'Map<Number,Recipe>'}, 'methods': methods}]}
        result = extract_type_evidence(source, [{'classId': cls['id'], 'methodId': by_name['get']['id']}], seed)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual({m['name'] for m in result['contract']['modules'][0]['methods']}, {'get', 'check', 'item'})
        self.assertEqual(result['contract']['records'], seed['records'])
        self.assertEqual(result['contract']['recordShapeEvidence'], [{'methodId': by_name['read']['id'],
                                                                       'methodSha256': by_name['read']['sourceSha256']}])

    def test_async_method_is_explicitly_unsupported_and_no_value_method_is_void(self):
        async_result = self.select('asyncWork')
        self.assertEqual(async_result['status'], 'unsupported_semantics')
        self.assertTrue(any(row['code'] == 'CODE_TYPE_EVIDENCE_UNSUPPORTED_METHOD' for row in async_result['diagnostics']))
        no_value = self.select('noValue')
        self.assertEqual(no_value['status'], 'ready')
        self.assertEqual(no_value['contract']['modules'][0]['methods'][0]['returns'], 'Void')
        self.assertEqual(no_value['contract']['modules'][0]['fields'], {'count': 'Number'})


if __name__ == '__main__':
    unittest.main()
