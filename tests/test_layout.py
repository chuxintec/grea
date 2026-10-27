"""Public tool IDs survive source moves; new tools may be added to the catalog."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from grea import registry
from grea.common import GreaError, package_root

ROOT = package_root()


class LayoutCompatibilityTests(unittest.TestCase):
    def isolated_environment(self, home):
        home = Path(home).resolve()
        env = {
            'HOME': str(home),
            'USERPROFILE': str(home),
            'GREA_PROVIDER_STATE_DIR': str(home / 'provider-state'),
            'PATH': '',
        }
        if os.name == 'nt':
            env['HOMEDRIVE'] = home.drive
            env['HOMEPATH'] = str(home)[len(home.drive):]
        return env

    def test_release_tool_ids_and_alias_targets_remain_available(self):
        baseline = json.loads((ROOT / 'tests/fixtures/tool-ids-v2026.10.13-rc1.json').read_text())
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, self.isolated_environment(home), clear=True):
            current = {entry['id']: entry for entry in registry.load()}
            for tool_id, alias in baseline.items():
                with self.subTest(tool_id=tool_id):
                    self.assertIn(tool_id, current)
                    self.assertEqual(current[tool_id].get('alias_of'), alias)
                    if alias:
                        self.assertEqual(current[tool_id]['execution'], current[alias]['execution'])
                        self.assertEqual(current[tool_id]['probe'], current[alias].get('probe'))

    def test_bundled_python_tools_launch_by_id_outside_repository(self):
        # Optional third-party programs are excluded: --help is not a runtime probe.
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as cwd, patch.dict(os.environ, self.isolated_environment(home), clear=True):
            for entry in registry.load():
                command = (entry.get('execution') or {}).get('command', [])
                if not command or command[0] != '{python}':
                    continue
                with self.subTest(tool_id=entry['id']):
                    unsupported = None
                    try:
                        registry.command(entry)
                    except GreaError as error:
                        if error.code not in ('UNSUPPORTED_HOST', 'UNSUPPORTED_ARCH', 'PROVIDER_UNAVAILABLE'):
                            raise
                        unsupported = error.code
                    process = subprocess.run(
                        [sys.executable, str(ROOT / 'launch.py'), 'legacy', entry['id'], '--help'],
                        cwd=cwd, capture_output=True, text=True, timeout=20,
                    )
                    if unsupported:
                        # Help respects platform and optional-provider availability; no silent fallback.
                        self.assertEqual(process.returncode, 2, process.stderr)
                        self.assertIn(unsupported + ':', process.stderr)
                        self.assertNotIn('usage:', process.stdout.lower())
                    else:
                        self.assertEqual(process.returncode, 0, process.stderr)
                        self.assertIn('usage:', process.stdout.lower())


if __name__ == '__main__':
    unittest.main()
