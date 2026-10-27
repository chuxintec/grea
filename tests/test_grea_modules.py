import base64
import hashlib
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from grea import modules
from grea.integrations import beaver
from grea.integrations.monkey import local as monkey_local

ROOT = Path(__file__).resolve().parents[1]


def record_hash(data):
    return 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()


def make_wheel(path, distribution, version, package, extra=None, tamper=False):
    dist = distribution.replace('-', '_') + '-' + version + '.dist-info'
    files = {f'{package}/__init__.py': f'__version__ = "{version}"\n'.encode(),
             f'{package}/cli.py': b'def main():\n    print("ok")\n    return 0\n',
             f'{dist}/METADATA': f'Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\n'.encode()}
    files.update(extra or {})
    rows = [f'{name},{record_hash(data)},{len(data)}' for name, data in files.items()]
    rows.append(f'{dist}/RECORD,,')
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in files.items():
            z.writestr(name, b'tampered' if tamper and name.endswith('cli.py') else data)
        z.writestr(f'{dist}/RECORD', '\n'.join(rows) + '\n')
    return path


def fake_root(directory):
    """A GREA package root with a lock describing two synthetic wheels."""
    root = Path(directory)/'grea'; wheels = root/'modules/wheels'; wheels.mkdir(parents=True)
    lock = json.loads((ROOT/'modules.lock.json').read_text())
    for m in lock['modules']:
        name = m['distribution'].replace('-', '_') + '-' + m['version'] + '-py3-none-any.whl'
        wheel = make_wheel(wheels/name, m['distribution'], m['version'], m['import'])
        m['wheel'] = dict(file=name, sha256=modules.sha256(wheel), bytes=wheel.stat().st_size)
    (root/'modules.lock.json').write_text(json.dumps(lock))
    return root


class ModuleLockTests(unittest.TestCase):
    def test_repository_lock_names_both_modules(self):
        lock = modules.load_lock(ROOT)
        self.assertEqual([m['name'] for m in lock['modules']], ['monkey', 'beaver'])
        self.assertTrue(all(m['wheel']['file'].endswith('-py3-none-any.whl') for m in lock['modules']))

    def test_lock_is_a_release_gate_for_adapters(self):
        """A GREA release may only pin module identities its thin adapters were verified against."""
        from grea.integrations.monkey.pipeline import SUPPORTED_VERSIONS as monkey_versions
        monkey_entry, beaver_entry = modules.load_lock(ROOT)['modules']
        self.assertIn(monkey_entry['version'], monkey_versions)
        self.assertIn(beaver_entry['version'], beaver.SUPPORTED_VERSIONS)
        if beaver_entry['version'] in beaver.V03_CANDIDATES:
            self.assertEqual(beaver_entry['implementationSha256'], beaver.V03_CANDIDATES[beaver_entry['version']]['implementation_sha256'])

    def test_lock_rejects_missing_module(self):
        with tempfile.TemporaryDirectory() as t:
            lock = json.loads((ROOT/'modules.lock.json').read_text()); lock['modules'].pop()
            Path(t, 'modules.lock.json').write_text(json.dumps(lock))
            with self.assertRaises(ValueError): modules.load_lock(t)

    def test_status_is_readonly_and_reports_absent_wheels(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)/'r'; root.mkdir(); (root/'modules.lock.json').write_bytes((ROOT/'modules.lock.json').read_bytes())
            value = modules.status(root, state=Path(t)/'state')
            self.assertEqual({row['bundled']['state'] for row in value['modules']}, {'absent'})
            self.assertFalse((Path(t)/'state').exists())

    def test_verify_rejects_identity_drift(self):
        with tempfile.TemporaryDirectory() as t:
            root = fake_root(t); entry = modules.module('beaver', root)
            path = root/'modules/wheels'/entry['wheel']['file']
            modules.verify_wheel(path, entry)
            path.write_bytes(path.read_bytes() + b'x')
            with self.assertRaises(ValueError): modules.verify_wheel(path, entry)

    def test_extract_rejects_member_differing_from_record(self):
        with tempfile.TemporaryDirectory() as t:
            wheel = make_wheel(Path(t)/'w.whl', 'beaver-game-tools', '0.3.0', 'beaver', tamper=True)
            with self.assertRaises(ValueError): modules._extract(wheel, Path(t)/'site')

    def test_extract_rejects_data_and_traversal_members(self):
        with tempfile.TemporaryDirectory() as t:
            wheel = make_wheel(Path(t)/'w.whl', 'beaver-game-tools', '0.3.0', 'beaver',
                               extra={'beaver_game_tools-0.3.0.data/scripts/x': b'x'})
            with self.assertRaises(ValueError): modules._extract(wheel, Path(t)/'site')

    @unittest.skipIf(os.name == 'nt', 'POSIX launcher')
    def test_install_creates_isolated_launcher_without_binding(self):
        with tempfile.TemporaryDirectory() as t:
            root = fake_root(t); state = Path(t)/'state'
            value = modules.install('beaver', Path(t)/'receipt', state=state, root=root)
            self.assertEqual(value['status'], 'ok'); self.assertEqual(value['binding'], 'not_changed')
            self.assertTrue(Path(value['launcher']).is_file())
            self.assertTrue(value['identity_root'].endswith('/beaver'))
            self.assertFalse((state/'beaver/binding.json').exists())
            again = modules.install('beaver', Path(t)/'receipt2', state=state, root=root)
            self.assertTrue(again['reused'])
            self.assertEqual(modules.installed_launchers('beaver', state), [Path(value['launcher'])])

    @unittest.skipIf(os.name == 'nt', 'POSIX launcher')
    def test_discovery_sees_module_install_and_stays_ambiguous_with_path(self):
        with tempfile.TemporaryDirectory() as t:
            root = fake_root(t); state = Path(t)/'state'
            installed = modules.install('beaver', Path(t)/'receipt', state=state, root=root)
            with patch.dict(os.environ, {'HOME': t, 'PATH': '', 'GREA_PROVIDER_STATE_DIR': str(state)}):
                found = beaver.discover()
                self.assertEqual(found['status'], 'discovered')
                self.assertEqual(found['command'], [str(Path(installed['launcher']).resolve())])
                other = Path(t)/'.local/bin/beaver'; other.parent.mkdir(parents=True); other.write_text('x'); other.chmod(0o755)
                self.assertEqual(beaver.discover()['status'], 'ambiguous')

    @unittest.skipIf(os.name == 'nt', 'POSIX launcher')
    def test_monkey_binding_keeps_priority_over_module_install(self):
        with tempfile.TemporaryDirectory() as t:
            root = fake_root(t); state = Path(t)/'state'
            modules.install('monkey', Path(t)/'receipt', state=state, root=root)
            with patch.dict(os.environ, {'HOME': t, 'PATH': '', 'GREA_PROVIDER_STATE_DIR': str(state)}):
                self.assertEqual(monkey_local.discover()['status'], 'discovered')
                (state/'monkey/binding.json').write_text(json.dumps(dict(schema_version=1, command=['/missing/monkey'], version='0.4.0')))
                self.assertEqual(monkey_local.discover()['status'], 'bound_missing')

    def test_stage_copies_exact_wheels_for_release(self):
        with tempfile.TemporaryDirectory() as t:
            root = fake_root(t)
            rows = modules.stage(root/'modules/wheels', Path(t)/'tree/modules/wheels', root=root)
            self.assertEqual([r['name'] for r in rows], ['monkey', 'beaver'])
            with self.assertRaises(FileExistsError): modules.stage(root/'modules/wheels', Path(t)/'tree/modules/wheels', root=root)


if __name__ == '__main__':
    unittest.main()
