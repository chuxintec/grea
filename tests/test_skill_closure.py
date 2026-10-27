"""Document portability is observable without a checkout or a tool runtime."""
import importlib.util
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


closure = module('check_skill_closure', 'check_skill_closure.py')
sync = module('sync_skill_closure', 'sync_skill.py')


class SkillClosureTests(unittest.TestCase):
    def test_frida_pair_diagnostic_does_not_read_a_repository_manual(self):
        from grea.tools import registry_doctor
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / 'plugin/skills/grea-recover/assets/frida-pair.reference.json'
            reference.parent.mkdir(parents=True)
            archive = root / '.private/providers/frida/server.xz'
            archive.parent.mkdir(parents=True)
            archive.write_bytes(b'owned archive fixture')
            reference.write_text(json.dumps({'version': '17.18.0', 'archive': archive.name,
                                            'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}))
            for changed in (False, True):
                if changed:
                    archive.write_bytes(b'changed archive')
                report = {'status': 'ok', 'error': None,
                          'result': {'checks': [{'tool_id': 'frida', 'output': '17.18.0'}]}}
                with patch.object(registry_doctor, 'ROOT', root), patch.object(registry_doctor, 'dispatch', return_value=report), contextlib.redirect_stdout(io.StringIO()):
                    code = registry_doctor.main(['--verify-frida-pair', '--json'])
                self.assertEqual(code, 1 if changed else 0)
                self.assertEqual(report['result']['frida_pair'], {'matched': not changed, 'server_executed': False})
            self.assertFalse((root / 'docs').exists())

    def test_actual_skills_remain_readable_after_source_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'checkout/plugin'
            shutil.copytree(ROOT / 'plugin/skills', source / 'skills')
            shutil.copyfile(ROOT / 'plugin/version.json', source / 'version.json')
            installed = root / 'installed'
            sync.synchronize(source, installed)
            shutil.rmtree(root / 'checkout')
            result = closure.check(installed)
            self.assertTrue(result['ok'], result['errors'])
            self.assertEqual(result['skills'], len(list((ROOT / 'plugin/skills').glob('*/SKILL.md'))))
            self.assertTrue((installed / 'grea-develop/assets/art-ledger.example.json').is_file())

    def test_authored_input_schemas_are_identical_to_runtime_and_examples_validate(self):
        for name, skill in [('research-input.schema.json', 'grea-research'),
                            ('change-contract.schema.json', 'grea-develop'),
                            ('theme-map.schema.json', 'grea-develop'),
                            ('art-ledger.schema.json', 'grea-develop')]:
            with self.subTest(name=name):
                asset = ROOT / 'plugin/skills' / skill / 'assets' / name
                self.assertEqual(asset.read_bytes(), (ROOT / 'schemas' / name).read_bytes())
                Draft202012Validator.check_schema(json.loads(asset.read_text()))
        assets = ROOT / 'plugin/skills/grea-develop/assets'
        for name in ('theme-map', 'art-ledger'):
            Draft202012Validator(json.loads((assets / f'{name}.schema.json').read_text())).validate(
                json.loads((assets / f'{name}.example.json').read_text()))
        schema = ROOT / 'plugin/skills/grea-research/assets/research-input.schema.json'
        Draft202012Validator(json.loads(schema.read_text())).validate(
            {'schema_version': 1, 'game': 'owned fixture', 'sources': [], 'items': [], 'protocols': []})

    def test_links_cannot_escape_even_when_repository_document_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / 'skills'
            (skills / 'grea').mkdir(parents=True)
            (root / 'manual.md').write_text('present')
            for text in ('[manual](../../manual.md)', '![image](../../manual.md)',
                         '[manual][ref]\n\n[ref]: ../../manual.md'):
                with self.subTest(text=text):
                    (skills / 'grea/SKILL.md').write_text(text)
                    self.assertIn('link_outside_skills', {e['code'] for e in closure.check(skills)['errors']})

    def test_literal_docs_dependency_and_missing_resources_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp)
            (skills / 'grea').mkdir()
            entry = skills / 'grea/SKILL.md'
            entry.write_text('Read `docs/providers/research.md`.\n[example](assets/missing.json)')
            self.assertEqual({e['code'] for e in closure.check(skills)['errors']},
                             {'repository_document_reference', 'missing_target'})
            entry.write_text('[official](https://frida.re/docs/installation/)')
            self.assertTrue(closure.check(skills)['ok'])

    def test_unreachable_reference_and_symlink_are_not_portable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / 'skills'
            (skills / 'grea/references').mkdir(parents=True)
            (skills / 'grea/SKILL.md').write_text('entry')
            (skills / 'grea/references/orphan.md').write_text('orphan')
            self.assertIn('unreachable_reference', {e['code'] for e in closure.check(skills)['errors']})
            target = root / 'external.txt'
            target.write_text('external')
            (skills / 'grea/external.txt').symlink_to(target)
            self.assertIn('symlink_not_portable', {e['code'] for e in closure.check(skills)['errors']})


if __name__ == '__main__':
    unittest.main()
