import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = str(Path(__file__).resolve().parents[3]/'src')


class ImportSideEffects(unittest.TestCase):
    def test_tool_modules_import_without_execution(self):
        # These modules formerly parsed argv/wrote output during import.
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, '-c', 'import sys;sys.path.insert(0,%r);import grea.features.asset.shader_probe, grea.features.source.unpack_xapk' % SRC],
                                    cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr); self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
