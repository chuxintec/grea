import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('sync_skill', Path(__file__).resolve().parents[1] / 'scripts/sync_skill.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def plugin(root):
    source = root / 'repo/plugin'
    (source / 'skills/grea').mkdir(parents=True)
    (source / 'skills/grea-port/references').mkdir(parents=True)
    (source / 'shared').mkdir()
    (source / '.codex-plugin').mkdir()
    (source / '.codex-plugin/plugin.json').write_text('{}')
    (source.parent / 'docs').mkdir()
    (source.parent / 'docs/info.md').write_text('info')
    (source / 'version.json').write_text('{}')
    (source / 'shared/common.md').write_text('[info](../../docs/info.md#section) [version](../version.json)')
    (source / 'skills/grea/SKILL.md').write_text('[common](../../shared/common.md) [port](../grea-port/SKILL.md) [web](https://example.com)')
    (source / 'skills/grea-port/SKILL.md').write_text('[topic](references/topic.md)')
    (source / 'skills/grea-port/references/topic.md').write_text('[common](../../../shared/common.md)')
    return source


class SkillSyncTests(unittest.TestCase):
    def test_layout_relocation_drift_and_pruning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = plugin(root)
            destination = root / 'workspace/.agents/skills'
            (destination / 'unrelated').mkdir(parents=True)
            (destination / 'unrelated/SKILL.md').write_text('keep')
            sync.synchronize(source, destination)
            self.assertEqual(sync.synchronize(source, destination, True), [])
            self.assertTrue((destination / 'grea/shared/common.md').is_file())
            self.assertTrue((destination / 'grea/version.json').is_file())
            self.assertFalse((destination / 'grea/.codex-plugin').exists())
            self.assertIn('(shared/common.md)', (destination / 'grea/SKILL.md').read_text())
            text = (destination / 'grea/shared/common.md').read_text()
            target = text.split('](')[1].split('#')[0]
            self.assertEqual((destination / 'grea/shared' / target).resolve(), (source.parent / 'docs/info.md').resolve())
            linked = (destination / 'grea-port/references/topic.md').read_text().split('](')[1].rstrip(')')
            self.assertEqual((destination / 'grea-port/references' / linked).resolve(), (destination / 'grea/shared/common.md').resolve())
            (destination / 'grea/SKILL.md').write_text('edited')
            (destination / 'grea-port/stale.md').write_text('stale')
            self.assertEqual(len(sync.synchronize(source, destination, True)), 2)
            self.assertEqual((destination / 'grea/SKILL.md').read_text(), 'edited')
            sync.synchronize(source, destination)
            self.assertFalse((destination / 'grea-port/stale.md').exists())
            self.assertEqual((destination / 'unrelated/SKILL.md').read_text(), 'keep')
            self.assertEqual(sync.synchronize(source, destination, True), [])

    def test_removed_skill_is_pruned_only_when_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = plugin(root)
            destination = root / 'skills'
            sync.synchronize(source, destination)
            self.assertEqual(json.loads((destination / 'grea/.grea-install.json').read_text())['skills'], ['grea', 'grea-port'])
            for item in sorted((source / 'skills/grea-port').rglob('*'), reverse=True):
                item.unlink() if item.is_file() else item.rmdir()
            (source / 'skills/grea-port').rmdir()
            (source / 'skills/grea/SKILL.md').write_text('[common](../../shared/common.md)')
            sync.synchronize(source, destination)
            self.assertFalse((destination / 'grea-port').exists())

    def test_broken_link_missing_router_and_overlap_do_not_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = plugin(root)
            (source / 'shared/common.md').write_text('[missing](missing.md)')
            destination = root / 'installed'
            with self.assertRaises(ValueError):
                sync.synchronize(source, destination)
            self.assertFalse(destination.exists())
            with self.assertRaises(ValueError):
                sync.synchronize(source, source / 'skills')
            (source / 'skills/grea/SKILL.md').unlink()
            with self.assertRaises(ValueError):
                sync.synchronize(source, destination)

    def test_symlink_and_foreign_directory_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = plugin(root)
            destination = root / 'skills'
            destination.symlink_to(source, target_is_directory=True)
            with self.assertRaises(ValueError):
                sync.synchronize(source, destination)
            other = root / 'other'
            (other / 'grea').mkdir(parents=True)
            (other / 'grea/notes.txt').write_text('not a skill')
            with self.assertRaises(ValueError):
                sync.synchronize(source, other)


if __name__ == '__main__':
    unittest.main()
