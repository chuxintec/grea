import json
from pathlib import Path
import tempfile
import unittest
from grea.tools.cocos3_evidence import inspect_ccon, inspect_index
from grea.tools.cocos_assets import ParseError
from grea.tools.cocos_modules import index_source


class Cocos3Tests(unittest.TestCase):
    def test_chunk_bounds_and_version(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root).resolve()/'clip.json';p.with_suffix('.bin').write_bytes(b'1234')
            d={'version':1,'document':[{'bytes':{'__type__':'TypedArrayRef','ctor':'Uint8Array','offset':1,'length':3}}],'chunks':['.bin']}
            p.write_text(json.dumps(d));self.assertEqual(inspect_ccon(p)['references'][0]['length'],3)
            d['document'][0]['bytes']['length']=4;p.write_text(json.dumps(d))
            with self.assertRaisesRegex(ParseError,'INDEX_OUT_OF_RANGE'):inspect_ccon(p)
            d['version']=2;p.write_text(json.dumps(d))
            with self.assertRaisesRegex(ParseError,'UNSUPPORTED_VERSION'):inspect_ccon(p)
            d['version']=1;p.write_text(json.dumps(d));p.with_suffix('.bin').unlink()
            with self.assertRaisesRegex(ParseError,'MISSING_CHUNK'):inspect_ccon(p)

    def test_creator_index_identity_and_pack(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root).resolve()/'config.json'; uid='00000000-0000-0000-0000-000000000001'
            d={'importBase':'import','nativeBase':'native','extensionMap':{},'types':['cc.AudioClip'],'uuids':[uid,'pack1'],'packs':{'pack1':['0']},'versions':{'import':[1,'hash'],'native':[0,'nat']}}
            source=p.parent/'import'/'pa'/'pack1.hash.json';source.parent.mkdir(parents=True)
            source.write_text(json.dumps([1,0,0, [['cc.AudioClip',['_name'],0]], [[0,0,2]], [[[[0,'sound'],-1],0,0,[],[],[]]]]))
            p.write_text(json.dumps(d));r=inspect_index(p,[0]);self.assertEqual(r['assets'][0]['pack_section_ordinal'],0)
            d['uuids'].append(uid);p.write_text(json.dumps(d))
            with self.assertRaisesRegex(ParseError,'DUPLICATE_UUID'):inspect_index(p,[0])
            p.write_text('{"uuids":[]}')
            with self.assertRaisesRegex(ParseError,'UNSUPPORTED_FORMAT'):inspect_index(p,[0])

    def test_system_register_syntax_never_executes(self):
        s=b'System.register("a",["cc"],function(){throw new Error("DO NOT EXECUTE");});'
        r=index_source(s,'system-register-v1');self.assertEqual(r['status'],'complete');self.assertEqual(r['modules'][0]['name'],'a')
        r=index_source(b'System.register(name, [dynamic()], function(){});','system-register-v1')
        self.assertEqual(r['status'],'partial')
        with self.assertRaisesRegex(ParseError,'DUPLICATE_MODULE'):index_source(s+s,'system-register-v1')
