import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_tree', ROOT / 'scripts/audit_public_tree.py')
public_tree = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public_tree)


class PublicTreeTests(unittest.TestCase):
    def test_rejects_private_material_without_echoing_values(self):
        token = 'gh' + 'p_' + 'a' * 36
        findings = public_tree.inspect('config.txt', token.encode())
        self.assertTrue(any(x['code'] == 'access_token' for x in findings))
        self.assertNotIn(token, repr(findings))
        self.assertTrue(public_tree.inspect('.private/notes.txt', b'private'))
        self.assertTrue(public_tree.inspect('bundle.dll', b'\0data'))
        self.assertTrue(public_tree.inspect('linked.txt', b'outside', '120000'))

    def test_scans_staged_bytes_not_worktree_or_ignored_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                subprocess.run(['git', '-C', tmp, *args], check=True, capture_output=True)
            git('init', '-q')
            (root / 'safe.txt').write_text('safe')
            git('add', 'safe.txt')
            (root / 'safe.txt').write_text('gh' + 'p_' + 'b' * 36)
            (root / '.env').write_text('not part of the index')
            self.assertTrue(public_tree.audit(root)['ok'])
            git('add', 'safe.txt')
            self.assertFalse(public_tree.audit(root)['ok'])

    def test_safe_documentation_and_loopback(self):
        self.assertEqual(public_tree.inspect('README.md', b'https://github.com/example/tool 127.0.0.1:5000 Python 3.10.2'), [])


if __name__ == '__main__':
    unittest.main()
