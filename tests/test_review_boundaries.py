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

from grea import registry, runner
from grea.safe_paths import relative_name, unique_paths
from grea.tools import static_asset_copy as copy, unity_pilot as pilot
from grea.tools import unpack_wxapkg as unpack, export_config_tables as export
from grea.tools import decrypt_v1mmwx_wxapkg as decrypt, package_backup

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

    def test_native_case_alias_never_writes_source(self):
        alias = self.root/'sRC'
        if not alias.exists(): self.skipTest('Filesystem is case-sensitive')
        self.assertTrue(alias.samefile(self.source))
        for maps in [['a=a'], ['.=nested']]:
            with self.assertRaises(ValueError): copy.copy_assets(self.source,alias/'OUT',maps)
        for d in ['Assets','Packages','ProjectSettings']: (self.source/d).mkdir()
        with self.assertRaises(ValueError): pilot.snapshot(self.source,'.',alias/'snapshot.json')
        manifest = self.root/'snapshot.json'; pilot.snapshot(self.source,'.',manifest)
        with self.assertRaises(ValueError): pilot.clone(manifest,alias/'OUT')
        self.assertFalse((self.source/'OUT').exists())
        self.assertTrue(pilot.verify(manifest)['unchanged'])
        self.assertEqual((self.source/'a').read_bytes(),b'original')

    def test_portable_names_and_aliases(self):
        for name in ['../x','/x','C:/x','C:x','x\\..\\z','x:stream','NUL','COM1.txt','x.','x ','a//b','a/./b','a\x00b']:
            with self.subTest(name=name), self.assertRaises(ValueError): relative_name(name)
        for names in [['a','A'],['é','e\u0301'],['a','a/b'],['a/b','a'],['A/x','a/y']]:
            with self.assertRaises(ValueError): unique_paths(names)
        with self.assertRaises(ValueError): copy.copy_assets(self.source,self.output,['a=A','a=a'])
        self.assertFalse(self.output.exists())

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

    def test_package_identity_rejected_before_archive_write(self):
        packages = self.source/'Packages'; packages.mkdir()
        (packages/'packages-lock.json').write_text(json.dumps({'dependencies':{'../../escape':{'source':'registry'}}}))
        with self.assertRaises(ValueError): package_backup.snapshot([self.source],self.output)
        self.assertFalse(self.output.exists())

    def test_package_legal_name_and_semver_build_are_preserved(self):
        name='com.example.my_tool';version='1.0.0-beta.1+build.2'
        packages=self.source/'Packages';package_dir=packages/name;package_dir.mkdir(parents=True)
        (package_dir/'package.json').write_text(json.dumps({'name':name,'version':version,'dependencies':{}}))
        (packages/'packages-lock.json').write_text(json.dumps({'dependencies':{name:{'source':'registry','version':version}}}))
        with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(package_backup.snapshot([self.source],self.output),0)
        data=json.loads((self.output/'catalog.json').read_text())
        self.assertEqual(data['packages'][0]['id'],name+'@'+version)

    def test_registered_helper_uncaught_exceptions_are_errors(self):
        entries = [e for e in registry.load() if 1 in (e.get('execution') or {}).get('finding_exit_codes', [])]
        self.assertGreaterEqual(len(entries),17)
        for entry in entries:
            command = entry['execution']['command']
            if '{grea}/launch_tool.py' not in command:
                continue  # Typed operations already convert exceptions in dispatch.
            module = command[command.index('{grea}/launch_tool.py')+1]
            with self.subTest(tool=entry['id']), patch.object(sys,'argv',['launch_tool.py',module]), \
                    patch('runpy.run_module',side_effect=RuntimeError('injected')), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error: runpy.run_path(str(ROOT/'launch_tool.py'),run_name='__main__')
                self.assertEqual(error.exception.code,2)
        receipt, _, error = runner.execute('unity_pilot',['verify','--snapshot',str(self.root/'missing')],self.root/'receipt')
        self.assertEqual(receipt['status'],'error'); self.assertIsNotNone(error)
        self.assertEqual(receipt['exit_code'],2)


if __name__ == '__main__': unittest.main()
