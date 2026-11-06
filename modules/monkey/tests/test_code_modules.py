import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from monkey.code_graph import facts
from monkey.code_modules import emit
from monkey.io import read,sha,write_json
from monkey.sources.compiled import ParseError
from monkey.cli import main


SOURCE=b'''var MathRules=(function(){function e(){}
e.half=function(x){if(x<0)throw "negative";return x/2;};
e.sum=function(xs){var total=0;for(var i=0;i<xs.length;i++)total+=xs[i];return total;};
return e;})();
var OrderRules=(function(){function e(){}
e.price=function(x){return MathRules.half(x)+1;};return e;})();
'''


def fixture(root,raw=SOURCE):
    source=root/'source.js';source.write_bytes(raw);graph=facts(source)
    modules=[]
    for cls in graph['classes']:
        selected=[]
        for method in graph['methods']:
            if method['classId']!=cls['id']:continue
            selected.append(dict(id=method['id'],sha256=method['sourceSha256'],name=method['name'],parameters=['List<Number>']if method['name']=='sum'else['Number'],returns='Number',locals={'i':'Index'}if method['name']=='sum'else{}))
        modules.append(dict(id=cls['name'],targetClass=cls['name'],classId=cls['id'],classSha256=cls['sourceSha256'],fields={},methods=selected))
    contract=root/'contract.json';write_json(contract,dict(schemaVersion=1,namespace='Game.Domain.Recovered',sourceSha256=sha(raw),records=[],modules=modules))
    return source,contract


class CodeModulesTests(unittest.TestCase):
    def test_real_bodies_cross_class_and_deterministic_fresh_reuse(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp).resolve();source,contract=fixture(root)
            result=emit(source,contract,root/'first');self.assertEqual(result['implementedMethods'],3)
            manifest=json.loads(read(root/'first/manifest.json'))
            order=next(m for m in manifest['codeModules']if m['id']=='OrderRules')
            self.assertIn('MathRules',order['dependencies'])
            cs=read(root/'first/Assets/Game/Domain/Recovered/MathRules.cs').decode()
            self.assertIn('for (int i = 0;',cs);self.assertIn('throw new InvalidOperationException("negative")',cs)
            # Independent outputs are deterministic, including each owned byte.
            emit(source,contract,root/'again')
            for row in manifest['files']:self.assertEqual(read(root/'first'/row['path']),read(root/'again'/row['path']))
            reused=emit(source,contract,root/'warm',reuse_from=root/'first',expected_manifest_sha256=sha(read(root/'first/manifest.json')))
            self.assertTrue(all(a['action']=='reuse'for a in reused['regeneration'].values()))
            path=root/'first/Assets/Game/Domain/Recovered/MathRules.cs';path.write_text(cs+'// manual edit')
            with self.assertRaisesRegex(ParseError,'REUSE_BLOCKED'):
                emit(source,contract,root/'dirty',reuse_from=root/'first',expected_manifest_sha256=sha(read(root/'first/manifest.json')))
            self.assertFalse((root/'dirty').exists())

    def test_source_change_missing_callee_and_forged_method_rejected_before_output(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp).resolve();source,contract=fixture(root);spec=json.loads(read(contract))
            original=read(source);source.write_bytes(original+b' ')
            with self.assertRaisesRegex(ParseError,'SOURCE_IDENTITY'):emit(source,contract,root/'changed')
            source.write_bytes(original)
            spec['modules'][0]['methods']=spec['modules'][0]['methods'][1:];write_json(contract,spec)
            with self.assertRaisesRegex(ParseError,'Callee absent'):emit(source,contract,root/'callee')
            self.assertFalse((root/'callee').exists())
            source,contract=fixture(root);spec=json.loads(read(contract));spec['modules'][0]['methods'][0]['sha256']='0'*64;write_json(contract,spec)
            with self.assertRaisesRegex(ParseError,'METHOD_IDENTITY'):emit(source,contract,root/'forged')

    def test_dynamic_unknown_and_nullish_semantics_do_not_become_default_success(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp).resolve()
            for expr in ('window.remote(x)','x >> 1','x === null','eval(x)'):
                raw=SOURCE.replace(b'return x/2;',('return '+expr+';').encode())
                source,contract=fixture(root,raw)
                with self.assertRaises(ParseError):emit(source,contract,root/'unsupported')
                self.assertFalse((root/'unsupported').exists())

    def test_cli_module_contract_and_graph_do_not_require_legacy_numeric_flags(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp).resolve();source,contract=fixture(root)
            with contextlib.redirect_stdout(io.StringIO()):
                result=main(['code-emit','--source',str(source),'--module-contract',str(contract),'--out',str(root/'cli')])
            self.assertEqual(result,1)
            with contextlib.redirect_stdout(io.StringIO()):
                result=main(['code-model','--source',str(source),'--lexical-graph','--expected-source',sha(read(source)),'--out',str(root/'graph')])
            self.assertEqual(result,1);self.assertTrue((root/'graph/code-graph.json').is_file())

    def test_overwritten_source_member_and_dynamic_callback_this_are_not_restored(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp).resolve()
            raw=SOURCE.replace(b'return e;})();',b'e.half=function(x){return x+9;};return e;})();',1)
            source,contract=fixture(root,raw);spec=json.loads(read(contract))
            # Explicitly select only the earlier definition; later overwrite is
            # still visible in the full class graph and must reject that choice.
            spec['modules'][0]['methods']=spec['modules'][0]['methods'][:-1];write_json(contract,spec)
            with self.assertRaisesRegex(ParseError,'MEMBER_AMBIGUOUS'):emit(source,contract,root/'overwritten')
            raw=SOURCE.replace(b'var total=0;',b'var total=0;xs.forEach(function(x){total+=this.half(x);});')
            source,contract=fixture(root,raw)
            with self.assertRaisesRegex(ParseError,'Dynamic this'):emit(source,contract,root/'dynamic-this')
            self.assertFalse((root/'dynamic-this').exists())


if __name__=='__main__':unittest.main()
