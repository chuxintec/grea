"""Synthetic wrappers test extraction without evaluating source initializers/factories."""
import hashlib
import json
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from grea.tools.cocos_modules import index_source, export_index
from grea.tools.cocos_assets import ParseError

@unittest.skipUnless(shutil.which('node') and (Path(__file__).resolve().parents[1]/'tools/cocos/node_modules/acorn/package.json').is_file(),'Optional Node/Acorn provider; run locked npm ci explicitly')
class ModuleTests(unittest.TestCase):
    def test_direct_table_preserves_unicode_bytes_and_literal_rf(self):
        source='/*雪*/ (function(a,b,c){} )({"ui/A":[function(require,module,exports){cc._RF.push(module,"identity-A","A");const x="雪";}, {"dep":"b"}], "ui_A":[function(){},{}]}, {}, []);'
        result=index_source(source.encode(),'browserify-table-v1')
        self.assertEqual(result['status'],'complete'); self.assertEqual(len(result['modules']),2)
        a,b=result['modules']; self.assertNotEqual(a['filename'],b['filename'])
        self.assertEqual(a['rf'][0]['identity'],'identity-A')
        raw=source.encode()[a['source_bytes']['start']:a['source_bytes']['end']]
        self.assertTrue(raw.startswith(b'function')); self.assertEqual(hashlib.sha256(raw).hexdigest(),a['sha256'])

    def test_define_wrapper_does_not_execute_initializer_or_factory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); sentinel=root/'MUST_NOT_EXIST'
            attack='require("fs").writeFileSync('+json.dumps(str(sentinel))+',"executed");'
            source='define("subpackages/ui/game.js",function(){'+attack+'window.__require=(function(a,b,c){'+attack+'})({"A":[function(){'+attack+'cc["_RF"]["push"](module,id,"A");},{}]}, {}, []);});'
            result=index_source(source.encode(),'define-browserify-v1')
            self.assertEqual(result['status'],'partial')
            self.assertEqual(result['modules'][0]['rf'][0]['status'],'unresolved')
            self.assertFalse(sentinel.exists())

    def test_unknown_loader_duplicate_module_and_budgets_fail(self):
        for source,code in [('run(loader);','UNSUPPORTED_WRAPPER'),
            ('(function(a,b,c){})({"A":[function(){},{}],"A":[function(){},{}]}, {}, []);','DUPLICATE_MODULE'),
            ('(function(a,b,c){})({A:factory}, {}, []);','UNSUPPORTED_MODULE')]:
            with self.subTest(code=code),self.assertRaises(ParseError) as c:index_source(source.encode(),'browserify-table-v1')
            self.assertEqual(c.exception.code,code)
        with self.assertRaises(ParseError):index_source(b'\xff','browserify-table-v1')

    def test_shadowing_and_assignments_are_unresolved_not_folded(self):
        source='(function(a,b,c){})({A:[function(){let id="outer";{let id="inner";cc._RF.push(module,id,"A");}id="changed";cc._RF.push(module,id,"A");},{}]}, {}, []);'
        result=index_source(source.encode(),'browserify-table-v1')
        self.assertEqual(result['status'],'partial')
        self.assertTrue(all(r['status']=='unresolved' for r in result['modules'][0]['rf']))

    def test_obfuscated_table_exports_candidates_without_guessing_identity(self):
        source='define("x",function(){window[key]=(function(a,b,c){})((function(){let t={};t[id]=[function(){cc[x][y](module,alias,"A");},makeDeps()];return t;})(), {}, []);});'
        result=index_source(source.encode(),'define-factory-candidates-v1')
        self.assertEqual(result['status'],'partial')
        self.assertEqual(len(result['modules']),1)
        self.assertIsNone(result['modules'][0]['name'])
        self.assertEqual(result['modules'][0]['confidence'],'syntax_candidate')
        self.assertTrue(result['modules'][0]['unresolved'])

    def test_nonfinite_javascript_number_is_unresolved_not_null(self):
        result=index_source(b'(function(a,b,c){})({A:[function(){},{dep:1e400}]}, {}, []);','browserify-table-v1')
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['modules'][0]['dependencies'],[])
        self.assertEqual(result['modules'][0]['unresolved'][0]['kind'],'dependency')

    def test_non_scalar_module_names_reject_before_filename_collisions(self):
        raw=r'(function(a,b,c){})({"\ud800":[function(){},{}],"\ud801":[function(){},{}]}, {}, []);'.encode()
        with self.assertRaises(ParseError):index_source(raw,'browserify-table-v1')

    def test_create_only_and_no_output_on_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); source=root/'x.js'
            source.write_text('(function(a,b,c){})({A:[function(){},{}]}, {}, []);')
            report=export_index(source,root/'new','browserify-table-v1')
            self.assertEqual(report['status'],'complete')
            with self.assertRaises(ParseError):export_index(source,root/'new','browserify-table-v1')
            source.write_text('throw Error("must not run");')
            with self.assertRaises(ParseError):export_index(source,root/'no-output','browserify-table-v1')
            self.assertFalse((root/'no-output').exists())

if __name__=='__main__':unittest.main()
