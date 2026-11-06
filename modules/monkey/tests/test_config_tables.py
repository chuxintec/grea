import json
import struct
import tempfile
import unittest
from pathlib import Path
from monkey.assets.bon import decode,BonError
from monkey.assets.config import export_tables
from monkey.layout import LayoutPlanner,casing
from monkey.io import sha


def bon(value):
    def count(n):
        out=[]
        while n>127:out.append((n&127)|128);n>>=7
        return bytes(out+[n])
    if value is None:return b'\0'
    if isinstance(value,bool):return b'\6'+bytes([int(value)])
    if isinstance(value,int):return b'\2'+struct.pack('<q',value)
    if isinstance(value,float):return b'\4'+struct.pack('<d',value)
    if isinstance(value,str):
        raw=value.encode();return b'\5'+count(len(raw))+raw
    if isinstance(value,list):return b'\11'+count(len(value))+b''.join(map(bon,value))
    return b'\10'+count(len(value))+b''.join(bon(k)+bon(v) for k,v in value.items())


CODEC=b'globalThis.bon={encode:x,decode:y};case 1:return this.dr.readInt32();case 2:return this.dr.readInt64();case 99:return this.strArr[this.dr.read7BitInt()]'


class ConfigTests(unittest.TestCase):
    def test_exact_json_values_and_string_references(self):
        data={'奖励表':{'9007199254740993':{'id':9007199254740993,'text':'中文','float':0.25,'nil':None,'flags':[True,False]}}}
        self.assertEqual(decode(bon(data)),data)
        self.assertEqual(decode(b'\10\1\5\1x\143\0'),{'x':'x'})

    def test_malformed_and_unrepresentable_data_are_not_silently_exported(self):
        bad=[b'',b'\10\0x',b'\10\1\143\0\0',b'\10\1'+bon('x')+b'\6\2',
             b'\10\2'+bon('x')+bon(1)+bon('x')+bon(2),bon({'x':float('nan')}),
             b'\10\1'+bon('x')+b'\7\0',b'\10\1'+bon('x')+b'\12'+b'\0'*8,
             b'\10\1'+bon(1)+bon(2),b'\10\xff\xff\xff\xff\x7f',bon({'x':[1]})[:-1]]
        for raw in bad:
            with self.subTest(raw=raw):
                with self.assertRaises(BonError):decode(raw)
        with self.assertRaises(BonError):decode(bon({'x':[[1]]}),max_depth=2)
        with self.assertRaises(BonError):decode(bon({'x':[1,2]}),max_nodes=3)

    def test_export_reconstructs_packs_and_preserves_homophone_tables(self):
        data={'奖励表':{'100':{'id':100,'名称':'鹅'}},'工':{'v':1},'公':{'v':2}}
        payloads={'game.js':CODEC,'a.bin':bon(data),'b.bin':bon({}), 'c.bin':bon({'x':1})+b'bad'}
        rows=[dict(path=p,suffix=Path(p).suffix,bytes=len(v),sha256=sha(v)) for p,v in payloads.items()]
        assets=[dict(sourceId=p,bundle='gameAsset',logicalKey=['Config/'+p,0],sourceType='cc.BufferAsset',sourceFiles=[p]) for p in ('a.bin','b.bin','c.bin')]
        for engine in ('unity','creator'):
            with self.subTest(engine=engine),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);naming=LayoutPlanner(engine)
                result=export_tables(root,assets,rows,lambda row:payloads[row['path']],naming,'test')
                self.assertEqual((result['exportedPacks'],result['exportedTables'],result['needsAdapter']),(2,3,1))
                tables=result['packs'][0]['tables']
                self.assertEqual(len({t['path'].casefold() for t in tables}),3)
                self.assertEqual({t['key']:json.loads((root/t['path']).read_text()) for t in tables},data)
                self.assertTrue(all(not casing.HAN.search(t['path']) for t in tables))
                if engine=='creator':
                    self.assertTrue(all(json.loads((root/(t['path']+'.meta')).read_text())['ver']=='2.0.1' for t in tables))
                self.assertEqual(result['packs'][1]['tables'],[])
                self.assertTrue((root/'Analysis/Mappings/config.json').exists())
        with tempfile.TemporaryDirectory() as temp:
            result=export_tables(Path(temp),assets,rows[1:],lambda row:payloads[row['path']],LayoutPlanner('unity'),'test')
            self.assertEqual(result['exportedTables'],0)
            self.assertEqual(result['needsAdapter'],3)
