"""The five-skill package upgrades managed installs and rejects stale entries."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_plugin
import check_skill_closure
import sync_skill


class FiveSkillDistributionTests(unittest.TestCase):
    def layout(self):
        return json.loads((ROOT / 'plugin/skills/grea/assets/skill-layout.json').read_text())

    def test_upgrade_removes_only_old_managed_skills_and_survives_detachment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / 'old/plugin'
            old_names = set(self.layout()['legacy_skill_names']) | {'grea', 'grea-research'}
            for name in old_names:
                path = old / 'skills' / name
                path.mkdir(parents=True)
                (path / 'SKILL.md').write_text('old managed skill')
                (path / 'old-note.txt').write_text('managed')
            destination = root / 'installed'
            sync_skill.synchronize(old, destination)
            (destination / 'unrelated-user-skill').mkdir()
            (destination / 'unrelated-user-skill/SKILL.md').write_text('user owned')
            current = root / 'new/plugin'
            shutil.copytree(ROOT / 'plugin/skills', current / 'skills')
            shutil.copyfile(ROOT / 'plugin/version.json', current / 'version.json')
            sync_skill.synchronize(current, destination)
            self.assertEqual(sync_skill.synchronize(current, destination, True), [])
            names = {p.parent.name for p in destination.glob('*/SKILL.md')}
            self.assertEqual(names, set(self.layout()['canonical_skills']) | {'unrelated-user-skill'})
            self.assertEqual((destination / 'unrelated-user-skill/SKILL.md').read_text(), 'user owned')
            for name in self.layout()['legacy_skill_names']:
                self.assertFalse((destination / name).exists())
            shutil.rmtree(root / 'old')
            shutil.rmtree(root / 'new')
            # Validate the managed set alone; unrelated user skills are not our content.
            isolated = root / 'portable'
            for name in self.layout()['canonical_skills']:
                shutil.copytree(destination / name, isolated / name)
            result = check_skill_closure.check(isolated)
            self.assertTrue(result['ok'], result['errors'])
            self.assertEqual(result['skills'], 5)

    def test_build_and_sync_reject_stale_sixth_skill_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'plugin'
            shutil.copytree(ROOT / 'plugin/skills', source / 'skills')
            stale = source / 'skills/grea-reskin'
            stale.mkdir()
            (stale / 'SKILL.md').write_text('stale')
            with self.assertRaisesRegex(ValueError, 'Declared Skill set'):
                sync_skill.synchronize(source, root / 'install')
            self.assertFalse((root / 'install').exists())
            result = check_skill_closure.check(source / 'skills')
            self.assertIn('skill_layout_drift', {e['code'] for e in result['errors']})
            files = {p.relative_to(root).as_posix(): (p.read_bytes(), 0o644)
                     for p in source.rglob('*') if p.is_file()}
            with self.assertRaisesRegex(ValueError, 'Skill set'):
                build_plugin.write_product(files, root / 'bundle')
            self.assertFalse((root / 'bundle').exists())


if __name__ == '__main__':
    unittest.main()
