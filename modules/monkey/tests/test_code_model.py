import json,tempfile,unittest
from pathlib import Path
from monkey.code_model import inspect
from monkey.sources.compiled import ParseError


class CodeModelTests(unittest.TestCase):
    def test_named_copy_methods_keep_unicode_source_ranges_without_execution(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();source=root/'source.js'
            source.write_text('/*中文*/ function Box(){}; Box.prototype.set=function(input){this.value=input;}; Box.prototype.get=function(){return this.value;}; Box.prototype.add=function(x){this.value+=x;}; process.exit(91);')
            result=inspect(source,root/'out','Box');self.assertEqual(result['summary'],{'methods':3,'semanticCandidates':2,'unsupported':1})
            d=json.loads((root/'out/code-model.json').read_text());self.assertFalse(d['sourceExecuted']);self.assertFalse(d['compiled'])
            self.assertEqual([m['name'] for m in d['methods']],['set','get','add'])
            self.assertTrue(all(m['sourceBytes']['start']>len('/*中文*/') for m in d['methods']))
            with self.assertRaises(ParseError):inspect(source,root/'out','Box')

    def test_computed_names_and_reassignment_are_not_silently_merged(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();source=root/'source.js'
            source.write_text('function Box(){}; Box.prototype.set=function(x){this.x=x;}; Box.prototype.set=function(y){this.y=y;};')
            with self.assertRaises(ParseError) as e:inspect(source,root/'out','Box')
            self.assertEqual(e.exception.code,'CODE_METHOD_AMBIGUOUS')


if __name__=='__main__':unittest.main()
