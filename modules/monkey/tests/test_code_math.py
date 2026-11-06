import copy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from monkey.code_model import inspect
from monkey import code_math
from monkey.io import write_json,read,load,sha
from monkey.sources.compiled import ParseError

# Handwritten small descriptor fixture, never a copied game/module asset.
SOURCE='''function(exported){var defineClass,legacy;return{setters:[function(ns){defineClass=ns.createClass},function(ns){legacy=ns.cclegacy}],execute:function(){legacy._RF.push({},"fixture-id","Curve",void 0),exported("Curve",function(){function Curve(){}return defineClass(Curve,null,[{key:"mix",value:function(a,b,t){return a+(b-a)*t}},{key:"degrees",value:function(x){return 180*x/Math.PI}},{key:"vector",value:function(x){return x.y}}]),Curve}()),legacy._RF.pop()}}}'''
TYPEOF='function(require,module,exports){module.exports=function(value){return typeof value;};}'
HELPER='function(exported){return {execute:function(){}}}'


class StaticMathTests(unittest.TestCase):
    def fixture(self,root,source=SOURCE,context_edit=''):
        source_path=root/'source.js';source_path.write_text(source)
        helper_path=root/'helper.js';helper_path.write_text(HELPER)
        profile=dict(profile='synthetic-explicit-review',freeAlias='e',typeOfModule='@babel/runtime/helpers/typeof.js',typeOfSha256=sha(TYPEOF.encode()))
        original='define("@babel/runtime/helpers/typeof.js",'+TYPEOF+');define("src/chunks/bundle.js",function(require,module,exports){var e=require("../../@babel/runtime/helpers/typeof");'+context_edit+'System.register("chunks:///_virtual/rollupPluginModLoBabelHelpers.js",[],('+HELPER+'));});'
        tree=root/'InputTree';tree.mkdir();(tree/'original.js').write_text(original);start=original.index(HELPER)
        helper=dict(sourceId='helper',sourceFile='original.js',source_bytes=dict(start=start,end=start+len(HELPER)))
        return source_path,helper_path,helper,tree,profile

    def test_source_descriptor_facts_keep_unsupported_methods_and_prove_literal_shape(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source,_,_,_,_=self.fixture(root);inspect(source,root/'facts','Curve');m=load(read(root/'facts/code-model.json'))
            self.assertEqual(m['summary'],dict(methods=3,semanticCandidates=2,unsupported=1));self.assertTrue(m['descriptorClasses'][0]['literalModuleShape']);self.assertTrue(m['descriptorClasses'][0]['descriptorTablesSafe'])
            self.assertEqual([x['name']for x in m['methods']],['mix','degrees','vector'])
            for method in m['methods']:
                p=method['sourceBytes'];self.assertEqual(sha(read(source)[p['start']:p['end']]),method['sourceSha256'])

    def test_scoped_helper_context_and_number_expression_emit_without_constructor_or_body_eval(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source,helper,row,tree,profile=self.fixture(root);inspect(source,root/'facts','Curve')
            with patch.dict(code_math.HELPER_PROFILES,{sha(read(helper)):profile}):
                context,body=code_math.helper_context(tree,row,read(helper))
                result=code_math.emit(source,root/'facts/code-model.json',helper,[dict(key='0',module='./rollupPluginModLoBabelHelpers.js'),dict(key='1',module='cc')],root/'out',['mix','degrees'],context=context,typeof_source=body)
            self.assertEqual(result['implementedMethods'],2);self.assertEqual(len(result['pendingMethods']),1);self.assertFalse(result['sourceExecuted']);self.assertTrue(context['processExited'])
            code=(root/'out/Unity/Assets/Game/Domain/Math/Curve.cs').read_text();self.assertIn('NoInlining',code);self.assertIn('_monkey_add(a, _monkey_mul(_monkey_sub(b, a), t))',code);self.assertNotIn('classCallCheck',code)
            ts=(root/'out/Cocos/assets/Game/Domain/Math/Curve.ts').read_text();self.assertIn('static mix(a: number, b: number, t: number): number',ts);self.assertNotIn('vector(',ts)

    def test_modified_helper_context_and_unrecognized_review_are_blocked(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source,helper,row,tree,profile=self.fixture(root,context_edit='e=function(){return "wrong";};');inspect(source,root/'facts','Curve')
            with self.assertRaisesRegex(ParseError,'HELPER_UNVERIFIED'):code_math.emit(source,root/'facts/code-model.json',helper,[],root/'out',['mix'])
            with patch.dict(code_math.HELPER_PROFILES,{sha(read(helper)):profile}):
                with self.assertRaisesRegex(ParseError,'CONTEXT_FAILED'):code_math.helper_context(tree,row,read(helper))
            self.assertFalse((root/'out').exists())

    def test_import_shadow_computed_descriptor_and_module_side_effects_do_not_gain_numeric_proof(self):
        variants=[SOURCE.replace('function(){legacy._RF.push','function(){var defineClass=function(){};legacy._RF.push'),SOURCE.replace('Math.PI','Math.random()'),SOURCE.replace('key:"mix"','["key"]:"mix"'),SOURCE.replace('legacy._RF.pop()','legacy._RF.pop(),eval("untrusted")')]
        for i,source_text in enumerate(variants):
            with self.subTest(case=i),tempfile.TemporaryDirectory()as t:
                root=Path(t).resolve();source,_,_,_,_=self.fixture(root,source_text);inspect(source,root/'facts','Curve');m=load(read(root/'facts/code-model.json'))
                if i==0:self.assertEqual(m['descriptorClasses'],[])
                elif i==1:self.assertEqual(m['summary']['semanticCandidates'],1)
                elif i==2:self.assertFalse(m['descriptorClasses'][0]['descriptorTablesSafe'])
                else:self.assertFalse(m['descriptorClasses'][0]['literalModuleShape'])

    def test_public_package_default_ts_and_grea_install_a_static_utility_without_component_binding(self):
        from test_cocos38 import fixture38
        from monkey.package import convert_package
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();config=fixture38(root/'source')
            helper_name='chunks:///_virtual/rollupPluginModLoBabelHelpers.js';module_name='chunks:///_virtual/Curve.ts'
            original='define("@babel/runtime/helpers/typeof.js",'+TYPEOF+');define("src/chunks/bundle.js",function(require,module,exports){var e=require("../../@babel/runtime/helpers/typeof");System.register("'+helper_name+'",[],('+HELPER+'));});System.register("'+module_name+'",["./rollupPluginModLoBabelHelpers.js","cc"],('+SOURCE+'));'
            (config.parent/'game.js').write_text(original)
            contract=root/'numeric.json';write_json(contract,dict(schemaVersion=1,kind=code_math.KIND,moduleName=module_name,moduleSha256=sha(SOURCE.encode()),helperModuleName=helper_name,helperModuleSha256=sha(HELPER.encode()),methods=['mix','degrees']))
            profile=dict(profile='synthetic-explicit-review',freeAlias='e',typeOfModule='@babel/runtime/helpers/typeof.js',typeOfSha256=sha(TYPEOF.encode()))
            for language in ['ts','js']:
                out=root/('out-'+language)
                with patch.dict(code_math.HELPER_PROFILES,{sha(HELPER.encode()):profile}):
                    result=convert_package(config.parent,'both',out,code_contract=contract,format_profile='grea',cocos_code_language=language)
                self.assertTrue(result['completed']);self.assertEqual(result['codeEmission']['implementedMethods'],2);self.assertEqual(result['format']['status'],'retired');self.assertTrue(any(d['code']=='FORMAT_PROFILE_RETIRED' for d in result['diagnostics']))
                for target,script in [('UnityProject','Assets/Game/Domain/Math/Curve.cs'),('CocosProject','assets/Game/Domain/Math/Curve.'+language)]:
                    project=out/target;self.assertTrue((project/script).is_file());m=load(read(project/'manifest.json'))
                    self.assertEqual(m['codeEmission']['scriptPath'],script);self.assertEqual(m['codeEmission']['kind'],code_math.KIND)
                    self.assertEqual(load(read(project/'Analysis/Code/package-code.json'))['sourceBindings'],[])
                    self.assertFalse((out/'Unformatted').exists())
                    if target=='UnityProject':self.assertIn('namespace Game.Domain.Math {',read(project/script).decode())
                    self.assertTrue((project/'SourceRecovery/Code/Source/Emission/ReviewedTypeofHelper.js').exists())
                    work=load(read(project/'Analysis/Tasks/agent-work.json'));task=next(t for t in work['tasks']if t['taskId']=='static-numeric-utility')
                    self.assertEqual(task['pendingMethods'],['vector']);self.assertEqual(task['sourceBindings'],[])
                    self.assertIn('STATIC-NUMERIC-UTILITY.md',(project/'Docs/START-HERE.md').read_text());self.assertIn('Curve.mix',(project/'Docs/STATIC-NUMERIC-UTILITY.md').read_text())

    def test_context_require_shadowing_is_not_treated_as_original_loader(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source,helper,row,tree,profile=self.fixture(root,context_edit='require=function(){return {};};')
            with patch.dict(code_math.HELPER_PROFILES,{sha(read(helper)):profile}):
                with self.assertRaisesRegex(ParseError,'CONTEXT_FAILED'):code_math.helper_context(tree,row,read(helper))

    def test_intrinsic_shadow_duplicate_descriptor_and_alias_updates_are_rejected(self):
        variants=[(SOURCE.replace('var defineClass,legacy','var defineClass,legacy,Math'),'literalModuleShape'),
                  (SOURCE.replace('return 180*x/Math.PI','return 180*x/Math.PI').replace('value:function(x){return 180','value:function Math(x){return 180'),'descriptorTablesSafe'),
                  (SOURCE.replace('key:"mix",value:','key:"mix",key:"alias",value:'),'descriptorTablesSafe'),
                  (SOURCE.replace('legacy._RF.pop()','legacy._RF.pop(),defineClass++'),'classes'),
                  (SOURCE.replace('setters:[','extra:eval("untrusted"),setters:['),'literalModuleShape')]
        for source_text,field in variants:
            with self.subTest(field=field),tempfile.TemporaryDirectory()as t:
                root=Path(t).resolve();source,_,_,_,_=self.fixture(root,source_text);inspect(source,root/'facts','Curve');m=load(read(root/'facts/code-model.json'))
                if field=='classes':self.assertEqual(m['descriptorClasses'],[])
                else:self.assertFalse(m['descriptorClasses'][0][field])

    def test_destructuring_alias_reassignment_does_not_prove_context(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source,helper,row,tree,profile=self.fixture(root,context_edit='({e}=replacement);')
            with patch.dict(code_math.HELPER_PROFILES,{sha(read(helper)):profile}):
                with self.assertRaisesRegex(ParseError,'CONTEXT_FAILED'):code_math.helper_context(tree,row,read(helper))

    def test_tampered_semantic_model_cannot_emit(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source,helper,row,tree,profile=self.fixture(root);inspect(source,root/'facts','Curve')
            data=load(read(root/'facts/code-model.json'));data['methods'][0]['semantic']['expression']={'kind':'literal','value':999};write_json(root/'facts/code-model.json',data)
            with patch.dict(code_math.HELPER_PROFILES,{sha(read(helper)):profile}):
                context,body=code_math.helper_context(tree,row,read(helper))
                with self.assertRaisesRegex(ParseError,'MODEL_CHANGED'):code_math.emit(source,root/'facts/code-model.json',helper,[],root/'out',['mix'],context=context,typeof_source=body)


if __name__=='__main__':unittest.main()
