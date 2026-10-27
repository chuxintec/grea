import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from grea import registry
from grea.common import package_root

ROOT = package_root()


class ModuleDelegationTests(unittest.TestCase):
    def providers(self, folder):
        path = Path(folder)/'providers.json'
        path.write_text(json.dumps({'schema_version': 1, 'providers': {
            'beaver': {'command': ['/opt/beaver/bin/beaver'], 'probe': ['/opt/beaver/bin/beaver', 'capabilities'], 'systems': ['Darwin', 'Windows', 'Linux']},
            'monkey': {'command': ['/opt/monkey/bin/monkey'], 'probe': ['/opt/monkey/bin/monkey', 'capabilities', '--json'], 'systems': ['Darwin', 'Windows', 'Linux']}}}))
        return path

    def test_moved_ids_route_to_bound_module_tool_command(self):
        with tempfile.TemporaryDirectory() as t, patch.dict(os.environ, {'GREA_PROVIDERS': str(self.providers(t))}):
            entries = {e['id']: e for e in registry.load()}
            self.assertEqual(entries['verify_payload_tree']['execution']['command'], ['/opt/beaver/bin/beaver', 'tool', 'verify_payload_tree'])
            self.assertEqual(entries['unity_package_backup']['execution']['command'][-2:], ['tool', 'package_backup'])
            self.assertEqual(entries['wxapkg-unpack']['execution']['command'], ['/opt/monkey/bin/monkey', 'tool', 'unpack_wxapkg'])
            self.assertEqual(entries['unpack_xapk']['probe'], ['/opt/monkey/bin/monkey', 'tool', 'unpack_xapk', '--help'])

    def test_every_delegated_id_has_no_local_implementation(self):
        raw = json.loads((ROOT/'registry.json').read_text(encoding='utf-8'))['tools']
        delegated = [t for t in raw if t.get('delegate')]
        self.assertGreaterEqual(len(delegated), 30)
        for t in delegated:
            self.assertIn(t['delegate']['module'], ('monkey', 'beaver'))
            self.assertFalse((ROOT/'src/grea/tools'/(t['delegate']['tool'] + '.py')).exists(), t['id'])
            self.assertEqual(t['ownership']['transition'], 'moved_to_module')

    def test_missing_module_is_reported_not_substituted(self):
        with tempfile.TemporaryDirectory() as t, patch.dict(os.environ, {'HOME': t, 'PATH': '', 'GREA_PROVIDER_STATE_DIR': t + '/state'}):
            os.environ.pop('GREA_PROVIDERS', None)
            entry = registry.tool('compare_traces')
            with self.assertRaises(Exception):
                registry.command(entry)


class BundledModuleTests(unittest.TestCase):
    def test_release_install_runs_bundled_wheel_when_no_module_is_bound(self):
        import shutil, subprocess, sys
        from module_support import wheel_dir
        from grea import modules
        lock = modules.load_lock(ROOT)
        if not all((wheel_dir()/m['wheel']['file']).is_file() for m in lock['modules']):
            self.skipTest('Locked module wheels unavailable')
        with tempfile.TemporaryDirectory() as t:
            home = Path(t)/'grea'; (home/'modules/wheels').mkdir(parents=True)
            for name in ('registry.json', 'modules.lock.json', 'launch_module.py'): shutil.copy(ROOT/name, home/name)
            for m in lock['modules']: shutil.copy(wheel_dir()/m['wheel']['file'], home/'modules/wheels'/m['wheel']['file'])
            env = {'GREA_HOME': str(home), 'HOME': t, 'PATH': '', 'GREA_PROVIDER_STATE_DIR': t + '/state'}
            with patch.dict(os.environ, env):
                os.environ.pop('GREA_PROVIDERS', None)
                entry = registry.tool('verify_payload_tree')
                argv = registry.command(entry)
            self.assertEqual(Path(argv[1]).resolve(), (home/'launch_module.py').resolve())
            self.assertEqual(argv[2:], ['beaver', 'tool', 'verify_payload_tree'])
            result = subprocess.run([sys.executable, str(home/'launch_module.py'), 'monkey', 'tool', '--help'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr); self.assertIn('unpack_xapk', result.stdout)
            (home/'modules/wheels'/lock['modules'][1]['wheel']['file']).write_bytes(b'tampered')
            bad = subprocess.run([sys.executable, str(home/'launch_module.py'), 'beaver', 'tool', '--help'], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2); self.assertIn('differs', bad.stderr)


class ReferenceRoutesTests(unittest.TestCase):
    def test_all_workflow_and_scenario_paths_resolve(self):
        from grea.workflows import WORKFLOWS, plan
        for mode in WORKFLOWS:
            for engine in ['unity', 'cocos', 'laya']:
                for step in plan(mode, engine)['steps']: self.assertTrue(Path(step['reference']).is_file(), step)
        cases = json.loads((ROOT/'tests/scenarios/scenarios.json').read_text())['cases']
        for case in cases:
            self.assertNotIn('primary_reference_numbers', case)
            for name in case['primary_references']: self.assertTrue((ROOT/name).is_file(), (case['id'], name))


if __name__ == '__main__':
    unittest.main()
