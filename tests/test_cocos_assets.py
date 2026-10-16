"""Own protocol examples: no shipped game data or source-engine runtime."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from grea.tools.cocos_assets import decode_document, export_document, export_bundle, select_import, ParseError

PLAIN = [1, [], [], [['cc.Node', ['_name'], 2]], [[0, 0, 2]], [[0, 'root']], [], [], [], [], []]
REFERENCES = [1, ['00'+'A'*20], [], [['cc.Node', ['_name','child','texture'], 3,0,1,6]],
              [[0,0,1,2,2],[0,0,2]], [[0,'root',1,0],[1,'child'],0], [], [], [0], ['texture'], [0]]

class CocosAssetsTests(unittest.TestCase):
    def test_plain_object_and_reference_graph(self):
        self.assertEqual(decode_document(PLAIN), {'root':0,'instances':[{'__type__':'cc.Node','_name':'root'}]})
        result=decode_document(REFERENCES)
        self.assertEqual(result['instances'][0]['child'], {'__id__':1})
        self.assertEqual(result['instances'][0]['texture'], {'__uuid__':'00000000-0000-0000-0000-000000000000'})
        self.assertEqual(result['instances'][1]['_name'], 'child')

    def test_explicit_version_unknown_kind_and_bounds(self):
        variants=[]
        item=copy.deepcopy(PLAIN); item[0]=999; variants.append((item,'UNSUPPORTED_VERSION'))
        item=copy.deepcopy(REFERENCES); item[3][0][-1]=99; variants.append((item,'UNSUPPORTED_KIND'))
        item=copy.deepcopy(REFERENCES); item[5][0][2]=20; variants.append((item,'INDEX_OUT_OF_RANGE'))
        item=copy.deepcopy(PLAIN); item[4][0][1]=80; variants.append((item,'INDEX_OUT_OF_RANGE'))
        item=copy.deepcopy(REFERENCES); item[10][0]=1; variants.append((item,'INDEX_OUT_OF_RANGE'))
        for document,code in variants:
            with self.subTest(code=code), self.assertRaises(ParseError) as caught: decode_document(document)
            self.assertEqual(caught.exception.code,code)

    def test_pack_has_explicit_ordinals_and_texture_adapter(self):
        pack=PLAIN[:5]+[[PLAIN[5:],PLAIN[5:]]]
        decoded=decode_document(pack, adapter='cocos-2.4-pack-v1')
        self.assertEqual([e['pack_section_ordinal'] for e in decoded['sections']],[0,1])
        self.assertEqual(decoded['sections'][1]['document']['instances'][0]['_name'],'root')
        self.assertEqual(decode_document({'type':'cc.Texture2D','data':'a|b'},adapter='cocos-2.4-texture-pack-v1')['sections'][1]['data'],'b')

    def test_bundle_selects_configured_version_and_records_pack_ordinal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); bundle=root/'bundle'; folder=bundle/'import'/'pa'; folder.mkdir(parents=True)
            pack=PLAIN[:5]+[[PLAIN[5:],PLAIN[5:]]]
            (folder/'packA.good.json').write_text(json.dumps(pack))
            (folder/'packA.old.json').write_text('[999]')
            config=bundle/'config.json';config.write_text(json.dumps({'uuids':['00'+'A'*20,'01'+'A'*20],
                'packs':{'packA':[1,0]},'versions':{'import':['packA','good']}}))
            report=export_bundle(config,[0],root/'out')
            self.assertEqual(report['selection']['assets'][0]['asset_index'],0)
            self.assertEqual(report['selection']['assets'][0]['pack_section_ordinal'],1)
            self.assertEqual(report['selection']['assets'][0]['version'],'good')
            with self.assertRaises(ParseError) as caught:select_import(bundle,'packA')
            self.assertEqual(caught.exception.code,'AMBIGUOUS_SELECTION')
            self.assertFalse((root/'bad-out').exists())
            with self.assertRaises(ParseError):export_bundle(config,[9],root/'bad-out')
            self.assertFalse((root/'bad-out').exists())

    def test_budget_truncated_tables_invalid_numbers_and_links(self):
        with self.assertRaises(ParseError):decode_document(PLAIN,max_depth=1)
        item=copy.deepcopy(PLAIN);item[5][0][1]=float('inf')
        with self.assertRaises(ParseError):decode_document(item)
        item=copy.deepcopy(REFERENCES);item[8]=[]
        with self.assertRaises(ParseError):decode_document(item)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); source=root/'source.json';source.write_text(json.dumps(PLAIN))
            linked=root/'linked';linked.symlink_to(source)
            with self.assertRaises(ParseError):export_document(linked,root/'new')
            with self.assertRaises(ParseError):export_document(source,root/'new',max_bytes=2)
            self.assertFalse((root/'new').exists())
            with self.assertRaises(ParseError):export_document(source,root/'small-output',max_output_bytes=2)
            self.assertFalse((root/'small-output').exists())

    def test_invalid_unicode_is_structured_and_does_not_create_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();source=root/'bad.json';item=copy.deepcopy(PLAIN)
            item[5][0][1]='\ud800';source.write_text(json.dumps(item))
            with self.assertRaises(ParseError) as caught:export_document(source,root/'out')
            self.assertEqual(caught.exception.code,'INVALID_UNICODE')
            self.assertFalse((root/'out').exists())

    def test_create_only_output_and_source_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); source=root/'source.json'; source.write_text(json.dumps(PLAIN))
            output=root/'candidate'; report=export_document(source,output)
            self.assertEqual(report['status'],'complete')
            self.assertTrue(report['source']['sha256']); self.assertTrue(report['outputs'][0]['sha256'])
            with self.assertRaises(ParseError) as caught: export_document(source,output)
            self.assertEqual(caught.exception.code,'OUTPUT_EXISTS')
            bad=root/'bad.json'; bad.write_text('[999]')
            with self.assertRaises(ParseError): export_document(bad,root/'not-created')
            self.assertFalse((root/'not-created').exists())
            self.assertEqual(json.loads(source.read_text()),PLAIN)

if __name__=='__main__': unittest.main()
