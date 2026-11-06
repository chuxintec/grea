import hashlib
import tempfile
import unittest
from pathlib import Path

from monkey.code_graph import facts
from monkey.code_selection import select_modules, write_selection
from monkey.io import write_json
from monkey.sources.compiled import ParseError




class CodeSelectionTests(unittest.TestCase):
    def test_cli_boundary_checks_lowering_and_does_not_write_blocked_contract(self):
        source_bytes=b'var X=(function(){function C(){}; C.run=function(x){return x >> 1;}; return C;})();'
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            root=Path(temporary);source=root/'source.js';source.write_bytes(source_bytes)
            graph=facts(source);cls=graph['classes'][0];method=graph['methods'][0]
            contract=dict(schemaVersion=1,namespace='Test.Recovered',sourceSha256=hashlib.sha256(source_bytes).hexdigest(),records=[],modules=[dict(id='X',targetClass='X',classId=cls['id'],classSha256=cls['sourceSha256'],fields={},methods=[dict(id=method['id'],sha256=method['sourceSha256'],name='Run',parameters=['Number'],returns='Number')])])
            write_json(root/'types.json',contract);write_json(root/'roots.json',[dict(classId=cls['id'],methodId=method['id'])])
            result=write_selection(source,root/'roots.json',root/'out',type_evidence=root/'types.json')
            self.assertEqual(result['status'],'unsupported_semantics');self.assertEqual(result['lowering'],'blocked')
            self.assertFalse((root/'out/module-contract.json').exists())



    def test_async_source_method_is_classified_as_unsupported(self):
        source_bytes = b'var X=(function(){function C(){}; C.prototype.run=async function(){return 1;}; return C;})();\n'
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            source = Path(temporary) / 'mini.js'
            source.write_bytes(source_bytes)
            graph = facts(source)
            cls = graph['classes'][0]
            method = next(m for m in graph['methods'] if m['name'] == 'run')
            evidence = {'schemaVersion': 1, 'sourceSha256': hashlib.sha256(source_bytes).hexdigest(),
                        'namespace': 'Test.Recovered', 'records': [], 'callDomain': 'finite test domain',
                        'modules': [{'id': 'X', 'targetClass': 'X', 'classId': cls['id'], 'classSha256': cls['sourceSha256'],
                                     'fields': {}, 'methods': [{'id': method['id'], 'name': 'run', 'sha256': method['sourceSha256'],
                                                                'parameters': [], 'returns': 'Number', 'locals': {}}]}]}
            result = select_modules(source, [{'classId': cls['id'], 'methodId': method['id']}], evidence)
        self.assertEqual(result['status'], 'unsupported_semantics')
        self.assertEqual(result['diagnostics'][0]['code'], 'CODE_SELECTION_UNSUPPORTED_ASYNC')



if __name__ == '__main__':
    unittest.main()
