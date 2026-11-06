import tempfile
import unittest
from pathlib import Path

from monkey.code_graph import facts, draft_records
from monkey.io import sha
from monkey.sources.compiled import ParseError


SOURCE = '''// 中文 offsets must remain original UTF-8 byte positions.
var Outer = (function () { function e() {}
e.branch = function (e) { var t = e; return t > 2 ? t : 0; };
e.call = function (t) { return e.branch(t); };
return e; })();
throw new Error("Original source must never run");
'''.encode()


class CodeGraphTests(unittest.TestCase):
    def test_full_draft_fields_keep_runtime_writes_out_of_static_initializers(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp).resolve()/'source.js'
            source.write_text('var Rules=(function(){function C(){} C.Value=1; C.Change=function(){C.Value=this.next;C.Value=2;};return C;})();')
            rows=list(draft_records(source))
            fields=[r['field'] for r in rows if r.get('record')=='field']
            self.assertEqual(len(fields),3)
            self.assertEqual(sum(r['initializationContext']=='class_factory'for r in fields),1)
            self.assertEqual(sum(r['initializationContext']=='runtime_write'for r in fields),2)
            raw=source.read_bytes()
            for row in fields:
                span=row['sourceBytes'];self.assertEqual(sha(raw[span['start']:span['end']]),row['sourceSha256'])

    def test_complete_lexical_scope_and_utf8_selected_span(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp).resolve()/'source.js'; source.write_bytes(SOURCE)
            graph=facts(source,sha(SOURCE)); self.assertFalse(graph['sourceExecuted'])
            self.assertEqual(graph['summary']['classes'],1)
            owner=graph['classes'][0]; methods={m['name']:m for m in graph['methods']}
            selected=facts(source,sha(SOURCE),[methods['call']['id']])
            self.assertEqual(len(selected['selected']),1)
            call=selected['selected'][0]['ast']['body']['body'][0]['argument']
            self.assertEqual(call['callee']['object']['bindingId'],owner['constructorBindingId'])
            span=methods['branch']['sourceBytes']
            self.assertEqual(SOURCE[span['start']:span['start']+8],b'e.branch')
            branch=facts(source,sha(SOURCE),[methods['branch']['id']])['selected'][0]['ast']
            self.assertNotEqual(branch['params'][0]['bindingId'],owner['constructorBindingId'])
            self.assertEqual(sha(SOURCE[span['start']:span['end']]),methods['branch']['sourceSha256'])

    def test_source_identity_mutation_and_ambiguous_binding_are_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp).resolve()/'source.js';source.write_bytes(SOURCE+b'Outer = null;')
            graph=facts(source)
            self.assertEqual(len(graph['classes'][0]['bindingMutations']),1)
            with self.assertRaisesRegex(ParseError,'SOURCE_IDENTITY'):facts(source,'0'*64)
            source.write_text('var a=1;var a=2;a.run=function(){return a;};')
            graph=facts(source)
            self.assertTrue(graph['methods'][0]['calls']==[])
            self.assertIsNone(graph['methods'][0]['classId'])


if __name__=='__main__':unittest.main()
