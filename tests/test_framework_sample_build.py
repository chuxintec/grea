import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('sample_build', Path(__file__).resolve().parents[1] / 'scripts/testing/build-framework-sample.py')
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)


class SampleBuildTests(unittest.TestCase):
    def source(self, root):
        source = root / 'source'
        for name in ('Assets', 'Packages', 'ProjectSettings'):
            (source / name).mkdir(parents=True)
            (source / name / 'owned.txt').write_text('original')
        (source / 'grea-framework-sample.marker').write_text('numeric-combat')
        (source / 'sample-seeded.json').write_text('{}')
        return source

    def test_unity_cache_mutation_is_confined_to_the_new_working_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); source = self.source(root); output = root / 'app'
            def execute(command, **kwargs):
                work = Path(command[2]); self.assertFalse((work / 'Library').exists())
                (work / 'Assets/owned.txt').write_text('engine build cache')
                output.mkdir()
                self.assertNotIn('--allow-install', command)
                return subprocess.CompletedProcess(command, 0, '{"success":true}', '')
            result = builder.build(source, root / 'work', output, execute=execute)
            self.assertTrue(result['sourceAssetsUnchanged'])
            self.assertEqual((source / 'Assets/owned.txt').read_text(), 'original')

    def test_failure_preserves_source_and_working_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); source = self.source(root)
            def execute(command, **kwargs):
                return subprocess.CompletedProcess(command, 6, '{"success":false}', 'compile error')
            with self.assertRaises(RuntimeError):
                builder.build(source, root / 'work', root / 'app', execute=execute)
            self.assertEqual((source / 'Assets/owned.txt').read_text(), 'original')
            self.assertTrue((root / 'work/build-command.json').is_file())

    def test_existing_nested_or_linked_paths_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); source = self.source(root)
            for work, output in [(source / 'nested', root / 'app'), (root / 'work', source / 'app'), (source, root / 'app')]:
                with self.assertRaises(ValueError): builder.build(source, work, output)
            (source / 'Assets/link').symlink_to(source / 'Packages/owned.txt')
            with self.assertRaises(ValueError): builder.build(source, root / 'work', root / 'app')
            self.assertFalse((root / 'work').exists())
