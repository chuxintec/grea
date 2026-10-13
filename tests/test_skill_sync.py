import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('sync_skill', Path(__file__).resolve().parents[1] / 'scripts/sync_skill.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SkillSyncTests(unittest.TestCase):
    def test_relocation_drift_and_pruning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'repo/skill'
            source.mkdir(parents=True)
            (source / 'references').mkdir()
            (source.parent / 'docs').mkdir()
            (source.parent / 'docs/info.md').write_text('info')
            (source / 'references/topic.md').write_text('[info](../../docs/info.md#section)')
            (source / 'SKILL.md').write_text('[topic](references/topic.md) [web](https://example.com)')
            destination = root / 'workspace/.agents/skills/grea'
            sync.synchronize(source, destination)
            self.assertEqual(sync.synchronize(source, destination, True), [])
            self.assertIn('(references/topic.md)', (destination / 'SKILL.md').read_text())
            text = (destination / 'references/topic.md').read_text()
            target = text.split('](')[1].split('#')[0]
            self.assertEqual((destination / 'references' / target).resolve(), (source.parent / 'docs/info.md').resolve())
            (destination / 'SKILL.md').write_text('edited')
            (destination / 'stale.md').write_text('stale')
            self.assertEqual(len(sync.synchronize(source, destination, True)), 2)
            self.assertEqual((destination / 'SKILL.md').read_text(), 'edited')
            sync.synchronize(source, destination)
            self.assertFalse((destination / 'stale.md').exists())
            self.assertEqual(sync.synchronize(source, destination, True), [])

    def test_broken_link_and_overlap_do_not_write(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'grea'
            source.mkdir()
            (source / 'SKILL.md').write_text('[missing](missing.md)')
            destination = Path(temp) / 'installed/grea'
            with self.assertRaises(ValueError):
                sync.synchronize(source, destination)
            self.assertFalse(destination.exists())
            with self.assertRaises(ValueError):
                sync.synchronize(source, source)

    def test_symlink_destination_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'skill'
            source.mkdir()
            (source / 'SKILL.md').write_text('source')
            destination = root / 'grea'
            destination.symlink_to(source, target_is_directory=True)
            with self.assertRaises(ValueError):
                sync.synchronize(source, destination)


if __name__ == '__main__':
    unittest.main()
