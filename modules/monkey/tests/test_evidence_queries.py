import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from monkey.io import encoded,sha,write_json,load,read
from monkey.evidence_stream import JsonRows,VerifiedStream,opened
from monkey.evidence_queries import query_methods,query_tables,inspect_aliases
from monkey.sources.compiled import ParseError
from monkey.unity_code_handoff import declared,attach
from monkey.cli import main


class EvidenceQueryTests(unittest.TestCase):
    def test_fragmented_utf8_envelope_stream_verifies_complete_bytes(self):
        raw=b'\xef\xbb\xbf'+encoded(dict(root='',entries=[dict(name='雪',token=18446744073709551615)]))
        with patch('monkey.evidence_stream.CHUNK',3):
            view=VerifiedStream(io.BytesIO(raw),len(raw),sha(raw),'synthetic')
            rows=list(JsonRows(view).rows('entries'))
        self.assertEqual(rows,[dict(name='雪',token=18446744073709551615)])
        self.assertTrue(view.verified)

    def test_stream_rejects_truncation_duplicates_missing_commas_and_trailing_data(self):
        for raw,field in [(b'[{"x":1}',None),(b'[{"x":1}{"x":2}]',None),(b'[1,]',None),
                          (b'[{"x":1,"x":2}]',None),(b'[] false',None),(b'{"files":[],"files":[]}','files'),
                          (b'{"entries":[{}],}','entries'),(b'{"entries":[]', 'entries')]:
            with self.subTest(raw=raw),self.assertRaises(ParseError):
                list(JsonRows(VerifiedStream(io.BytesIO(raw),len(raw),sha(raw),'synthetic')).rows(field))

    def test_method_limit_never_skips_source_hash_or_module_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();path=r/'map.json'
            rows=[dict(type='.Unit',name='Grow',module=m,function=9,token=18446744073709551615) for m in ('main','split')]
            write_json(path,rows);h=sha(read(path))
            a=query_methods(path,h,r/'all',function=9,limit=1)
            self.assertEqual((a['matches'],a['returned'],a['methodBodiesRecovered']),(2,1,0));self.assertTrue(a['limited'])
            self.assertTrue(a['sources'][0]['verified']);self.assertEqual(a['rows'][0]['token'],rows[0]['token'])
            b=query_methods(path,h,r/'split',function=9,module='split');self.assertEqual(b['rows'],[rows[1]])
            with self.assertRaises(ParseError):query_methods(path,'0'*64,r/'bad',limit=1)
            self.assertFalse((r/'bad').exists())

    def test_rows_stay_bounded_across_many_values_and_oversized_values_refuse(self):
        raw=encoded([{'index':i,'name':'x'*80} for i in range(2000)])
        view=VerifiedStream(io.BytesIO(raw),len(raw),sha(raw),'synthetic');cursor=JsonRows(view)
        for i,row in enumerate(cursor.rows()):
            self.assertEqual(row['index'],i);self.assertLess(len(cursor.text),100000)
        self.assertTrue(view.verified)
        with patch('monkey.evidence_stream.ROW_BYTES',16),self.assertRaises(ParseError):
            list(JsonRows(VerifiedStream(io.BytesIO(raw),len(raw),sha(raw),'synthetic')).rows())

    def tables(self,r):
        values={'display-A.json':b'{"value":"1.0"}','fp-A.json':b'{"value":10000000000}'}
        nested=io.BytesIO()
        with zipfile.ZipFile(nested,'w') as z:
            for n,v in values.items():z.writestr(n,v)
        source=r/'source.zip'
        with zipfile.ZipFile(source,'w') as z:z.writestr('data/tables.zip',nested.getvalue())
        manifest=r/'tables.json';write_json(manifest,dict(files=[dict(name=n,bytes=len(v),sha256=sha(v)) for n,v in values.items()]))
        return source,manifest,values,sha(nested.getvalue())

    def test_nested_tables_extract_only_exact_hashed_variant(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();source,manifest,values,h=self.tables(r)
            listing=query_tables(manifest,sha(read(manifest)),r/'list',contains='A')
            self.assertEqual(listing['matches'],2);self.assertFalse(listing['contentVerified'])
            result=query_tables(manifest,sha(read(manifest)),r/'extract',source=source,member='data/tables.zip',expected=h,extract='fp-A.json')
            self.assertTrue(result['contentVerified']);self.assertEqual(read(r/'extract'/result['extractedPath']),values['fp-A.json'])
            self.assertEqual(result['sources'][1]['selection']['kind'],'zip-member')
            self.assertFalse(result['sources'][1]['selection']['containerHashVerified'])
            self.assertFalse((r/'extract/payload/display-A.json').exists())
            with self.assertRaises(ParseError):query_tables(manifest,sha(read(manifest)),r/'extract',source=source,member='data/tables.zip',expected=h,extract='fp-A.json')

    def test_table_manifest_payload_tamper_and_unsafe_names_never_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();source,manifest,values,h=self.tables(r)
            m=load(read(manifest));m['files'][0]['sha256']='0'*64;write_json(manifest,m)
            with self.assertRaises(ParseError):query_tables(manifest,sha(read(manifest)),r/'bad',source=source,member='data/tables.zip',expected=h,extract='display-A.json')
            self.assertFalse((r/'bad').exists())
            m['files'][0]['name']='../escape.json';write_json(manifest,m)
            with self.assertRaises(ParseError):query_tables(manifest,sha(read(manifest)),r/'unsafe')

    def test_duplicate_case_alias_or_linked_archive_entries_refuse(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();source=r/'source.zip'
            for kind in ('case','link'):
                with zipfile.ZipFile(source,'w') as z:
                    z.writestr('A.json',b'[]')
                    if kind=='case':z.writestr('a.json',b'[]')
                    else:
                        row=zipfile.ZipInfo('link');row.create_system=3;row.external_attr=0o120777<<16;z.writestr(row,b'A.json')
                with self.assertRaises(ParseError):
                    with opened(source,sha(b'[]'),'A.json') as stream:stream.read()

    def test_aliases_preserve_exact_versions_and_validate_real_content(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();(r/'content/payload').mkdir(parents=True);data=b'original';(r/'content/payload/a.bin').write_bytes(data)
            rows=[dict(url=u,path='payload/a.bin',bytes=len(data),sha256=sha(data)) for u in ('/v1/a?rev=1','/v2/a?rev=2')]
            path=r/'routes.json';write_json(path,dict(entries=rows))
            result=inspect_aliases(path,sha(read(path)),r/'out',alias=rows[0]['url'],content_source=r/'content')
            self.assertEqual((result['routes'],result['uniqueContent'],result['matches']),(2,1,2));self.assertTrue(result['contentVerified'])
            with self.assertRaises(ParseError):inspect_aliases(path,sha(read(path)),r/'guess',alias='/v1/a')
            (r/'content/payload/a.bin').write_bytes(b'modified')
            with self.assertRaises(ParseError):inspect_aliases(path,sha(read(path)),r/'bad',alias=rows[0]['url'],content_source=r/'content')
            self.assertFalse((r/'bad').exists())
            rows[1]['sha256']='0'*64;write_json(path,dict(entries=rows))
            with self.assertRaises(ParseError):inspect_aliases(path,sha(read(path)),r/'conflict')

    def test_original_and_adapted_evidence_have_separate_hash_roles(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();original=r/'original.wasm';original.write_bytes(b'original-module')
            adapted=r/'adapter.wasm';adapted.write_bytes(b'adapted-module')
            m=r/'evidence.json';rows=[dict(path=p.name,role=role,bytes=p.stat().st_size,sha256=sha(read(p))) for p,role in ((original,'source-binary'),(adapted,'adapted-binary'))]
            write_json(m,dict(schemaVersion=1,files=rows))
            with self.assertRaises(ParseError):declared(m)
            rows[1]['derivedFromSha256']=rows[0]['sha256'];write_json(m,dict(schemaVersion=1,files=rows))
            project=r/'project';(project/'Assets').mkdir(parents=True)
            attach(m,project)
            copied=list((project/'SourceRecovery/Code/Source').rglob('*.wasm'));self.assertEqual(len(copied),2)
            self.assertEqual({p.parent.name for p in copied},{'source-binary','adapted-binary'})

    def test_public_cli_uses_inspection_and_returns_errors_without_source_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();p=r/'map.json';write_json(p,[dict(type='Unit',name='Tick',module='main',function=1)])
            args=['query-methods','--source',str(p),'--expected-sha',sha(read(p)),'--out',str(r/'out')]
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(args),0)
            self.assertEqual(load(read(r/'out/inspection.json'))['methodBodiesRecovered'],0)
            with contextlib.redirect_stderr(io.StringIO()):self.assertEqual(main(args),2)
