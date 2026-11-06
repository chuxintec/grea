"""Real filesystem aliases and hostile package names, with legitimate controls."""
import contextlib
import io
import json
from pathlib import Path
import runpy
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from monkey.toolkit.support.safe_paths import relative_name, unique_paths
from monkey.toolkit import unpack_wxapkg as unpack, export_config_tables as export
from monkey.toolkit import decrypt_v1mmwx_wxapkg as decrypt

ROOT = Path(__file__).resolve().parents[1]


def package(names):
    index_size = 4 + sum(12 + len(n.encode()) for n in names)
    offset = 14 + index_size
    entries = b''
    for name in names:
        data = name.encode()
        entries += struct.pack('>I', len(data)) + data + struct.pack('>II', offset, 1)
        offset += 1
    return b'\xbe' + b'\0'*4 + struct.pack('>II', index_size, len(names)) + b'\xed' + struct.pack('>I', len(names)) + entries + b'x'*len(names)


class WriteBoundaryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.source = self.root/'Src'; self.source.mkdir()
        (self.source/'a').write_bytes(b'original')
        self.output = self.root/'out'

    def invoke(self, module, *args):
        with patch.object(sys, 'argv', ['tool', *map(str,args)]), contextlib.redirect_stdout(io.StringIO()):
            return module.main()

    def test_unpack_preflights_all_entries_and_index_conflicts(self):
        source = self.root/'input.wxapkg'
        for name in ['../escape','C:/escape','a\\..\\escape','_WXAPKG_INDEX.json','GOOD','good/child']:
            source.write_bytes(package(['/good',name]))
            with self.assertRaises(ValueError): self.invoke(unpack,source,self.output)
            self.assertFalse(self.output.exists())
        source.write_bytes(package(['/folder/中文','/other']))
        self.invoke(unpack,source,self.output)
        self.assertEqual((self.output/'folder/中文').read_bytes(),b'x')
        with self.assertRaises(FileExistsError): self.invoke(unpack,source,self.output)
        self.assertEqual(len(json.loads((self.output/'_WXAPKG_INDEX.json').read_text())),2)

    def export_assets(self, names):
        source = self.root/'bundle'; source.write_bytes(b'fixture')
        objects = [SimpleNamespace(type=SimpleNamespace(name='TextAsset'),path_id=i,
                    read=lambda name=n: SimpleNamespace(m_Name=name,m_Script=b'\xef\xbb\xbf{"Datas":[]}')) for i,n in enumerate(names)]
        with patch.dict(sys.modules, {'UnityPy':SimpleNamespace(load=lambda _:SimpleNamespace(objects=objects))}):
            self.invoke(export,source,self.output)

    def test_export_names_no_partial_write_and_valid_bom(self):
        for names in [['good','../../escape'],['a','A'],['é','e\u0301'],['/absolute'],['C:stream']]:
            with self.assertRaises(ValueError): self.export_assets(names)
            self.assertFalse(self.output.exists())
        self.export_assets(['Config'])
        self.assertEqual((self.output/'json/Config.json').read_bytes(),b'{"Datas":[]}')
        with self.assertRaises(FileExistsError): self.export_assets(['Config'])

    def test_decrypt_preserves_existing_and_input_alias(self):
        source = self.source/'a'
        with patch.object(decrypt,'decrypt',return_value=b'clear'):
            self.output.write_bytes(b'keep')
            with self.assertRaises(ValueError): self.invoke(decrypt,'appid',source,self.output)
            with self.assertRaises(ValueError): self.invoke(decrypt,'appid',source,source)
            self.assertEqual(self.output.read_bytes(),b'keep')
            self.output.unlink(); self.invoke(decrypt,'appid',source,self.output)
            self.assertEqual(self.output.read_bytes(),b'clear')
            self.assertEqual(source.read_bytes(),b'original')


if __name__ == '__main__': unittest.main()
