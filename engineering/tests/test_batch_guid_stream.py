from pathlib import Path
import tempfile
import unittest
from beaver.batch import _yaml_guid_scan
from beaver.errors import BeaverError


class GuidStreamTests(unittest.TestCase):
    def test_guid_crosses_each_chunk_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp).resolve()/'asset'
            raw=b'%YAML\n'+b'a'*73+b'guid: '+b'f'*32+b'\n'+b'b'*80+b'guid: '+b'e'*32
            p.write_bytes(raw)
            for size in (1,7,32,37,64,128):
                found,count=_yaml_guid_scan(p,len(raw),size)
                self.assertEqual(found,{b'f'*32,b'e'*32});self.assertEqual(count,len(raw))

    def test_large_single_line_is_streamed_and_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp).resolve()/'font.asset'
            with p.open('wb') as f:
                f.write(b'%YAML\n')
                for _ in range(33):f.write(b'a'*1024**2)
                f.write(b'guid: '+b'1'*32)
            self.assertEqual(_yaml_guid_scan(p,40*1024**2)[0],{b'1'*32})

    def test_aggregate_budget_refuses_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp).resolve()/'asset';p.write_bytes(b'%YAML\n'+b'a'*100)
            with self.assertRaises(BeaverError) as error:_yaml_guid_scan(p,50)
            self.assertEqual(error.exception.code,'BATCH_DEPENDENCY_BUDGET')

    def test_binary_guid_text_is_not_a_yaml_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp).resolve()/'asset';p.write_bytes(b'BIN\0\0guid: '+b'1'*32)
            self.assertEqual(_yaml_guid_scan(p,100),(set(),5))
