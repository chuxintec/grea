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
from module_support import with_modules
from unittest.mock import patch

from grea import registry, runner
from grea.safe_paths import relative_name, unique_paths

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

    def test_portable_names_and_aliases(self):
        for name in ['../x','/x','C:/x','C:x','x\\..\\z','x:stream','NUL','COM1.txt','x.','x ','a//b','a/./b','a\x00b']:
            with self.subTest(name=name), self.assertRaises(ValueError): relative_name(name)
        for names in [['a','A'],['é','e\u0301'],['a','a/b'],['a/b','a'],['A/x','a/y']]:
            with self.assertRaises(ValueError): unique_paths(names)

    @with_modules

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
