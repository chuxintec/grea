"""Distribution/assembly boundaries; native C# behavior lives in Unity package tests."""
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / 'tools/unity/framework/packages'
SAMPLE = ROOT / 'tools/unity/templates/counter-composition/Assets'
CONSUMERS = tuple(ROOT / 'tools/unity/templates/framework-samples' / name / 'Assets' for name in ('numeric-combat', 'grid-puzzle'))
spec = importlib.util.spec_from_file_location('prepare_m2', ROOT / 'scripts/testing/prepare-unity-framework.py')
prepare_m2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare_m2)


class UnityFrameworkTests(unittest.TestCase):
    def test_prepare_rejects_layer_violations_before_creating_output(self):
        cases = ('domain-engine', 'package-game', 'package-other-consumer', 'cycle', 'test-in-player', 'runtime-editor')
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                packages, sample = root / 'packages', root / 'sample'
                packages.mkdir(); sample.mkdir()

                def assembly(base, name, references=(), pure=False, **extra):
                    folder = base / name
                    folder.mkdir()
                    value = dict(name=name, references=list(references), noEngineReferences=pure,
                                 includePlatforms=[], defineConstraints=[])
                    value.update(extra)
                    (folder / (name + '.asmdef')).write_text(json.dumps(value))
                    return folder

                if case == 'domain-engine':
                    folder = assembly(sample, 'Game.Domain', pure=True)
                    (folder / 'State.cs').write_text('using UnityEngine; class State { Vector3 value; }')
                elif case == 'package-game':
                    assembly(packages, 'Grea.Bad', ['Game.Domain'])
                    assembly(sample, 'Game.Domain', pure=True)
                elif case == 'package-other-consumer':
                    assembly(packages, 'Grea.Bad', ['Example.Domain'])
                    assembly(sample, 'Example.Domain', pure=True)
                elif case == 'cycle':
                    assembly(sample, 'Game.Domain', ['Game.Gameplay'], pure=True)
                    assembly(sample, 'Game.Gameplay', ['Game.Domain'], pure=True)
                elif case == 'test-in-player':
                    assembly(packages, 'Grea.Bad.Tests', optionalUnityReferences=['TestAssemblies'])
                else:
                    assembly(packages, 'Grea.Bad.Runtime', ['UnityEditor'])
                destination = root / 'output'
                with patch.object(prepare_m2, 'ROOT', root), patch.object(prepare_m2, 'PACKAGES', packages), patch.object(prepare_m2, 'SAMPLE', sample):
                    with self.assertRaisesRegex(ValueError, 'FRAMEWORK_BOUNDARY'):
                        prepare_m2.prepare(destination)
                self.assertFalse(destination.exists())

    def test_distinct_samples_are_copied_and_checked_without_game_dependencies_in_packages(self):
        from grea.tools.unity_framework_audit import inspect
        for name in ('numeric-combat', 'grid-puzzle'):
            with self.subTest(sample=name), tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp).resolve() / 'project'
                result = prepare_m2.prepare(dest, sample=name)
                self.assertEqual(result['sample'], name)
                self.assertTrue(inspect(dest / 'Packages', dest / 'Assets')['ok'])
                self.assertFalse(any('Counter' in p.name for p in (dest / 'Assets').rglob('*.cs')))
                self.assertTrue((dest / 'Assets/Game/Editor/SampleBuilder.cs').is_file())
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp).resolve() / 'project'
            with self.assertRaises(ValueError):
                prepare_m2.prepare(dest, sample='../unknown')
            self.assertFalse(dest.exists())

    def test_assemblies_are_acyclic_and_pure_layers_isolated(self):
        assemblies = {}
        for base in (PACKAGES, SAMPLE):
            for file in base.rglob('*.asmdef'):
                data = json.loads(file.read_text())
                self.assertNotIn(data['name'], assemblies)
                assemblies[data['name']] = data
                name = data['name']
                if name in {'Grea.Foundation.Contracts', 'Game.Domain', 'Game.Gameplay', 'Game.Services'}:
                    self.assertTrue(data['noEngineReferences'])
                if 'Tests' in name:
                    self.assertIn('UNITY_INCLUDE_TESTS', data['defineConstraints'])
                    self.assertIn('TestAssemblies', data['optionalUnityReferences'])
                if name == 'Grea.Editor':
                    self.assertEqual(data['includePlatforms'], ['Editor'])
        visiting, done = set(), set()

        def visit(name):
            self.assertNotIn(name, visiting, 'assembly cycle')
            if name in done:
                return
            visiting.add(name)
            data = assemblies[name]
            for ref in data['references']:
                if name.startswith('Grea.'):
                    self.assertFalse(ref.startswith('Game.'))
                if not data['includePlatforms'] and 'Tests' not in name:
                    self.assertNotIn('Tests', ref)
                    self.assertNotIn('Editor', ref)
                if ref in assemblies:
                    if data['noEngineReferences']:
                        self.assertTrue(assemblies[ref]['noEngineReferences'])
                    visit(ref)
                else:
                    self.assertIn(ref, {'UnityEngine.UI', 'Unity.RenderPipelines.Universal.Runtime', 'Unity.RenderPipelines.Core.Runtime'})
            visiting.remove(name)
            done.add(name)

        for name in assemblies:
            visit(name)
        self.assertEqual(len(assemblies), 14)

    def test_meta_identity_complete_unique_and_no_binary_payloads(self):
        guids = set()
        for base in (PACKAGES, SAMPLE, *CONSUMERS):
            for path in base.rglob('*'):
                self.assertFalse(path.is_symlink())
                if path.suffix == '.meta':
                    self.assertTrue(path.with_suffix('').exists(), str(path))
                    guid = re.search(r'^guid: ([0-9a-f]{32})$', path.read_text(), re.M)
                    self.assertIsNotNone(guid, str(path))
                    self.assertNotIn(guid[1], guids)
                    guids.add(guid[1])
                elif not (path.parent == PACKAGES):
                    self.assertTrue(Path(str(path) + '.meta').is_file(), str(path))
                if path.is_file():
                    self.assertNotIn(path.suffix, {'.dll', '.pdb', '.zip', '.unity', '.prefab', '.asset'})

    def test_packages_have_resolvable_locked_dependencies_and_license(self):
        versions = {}
        for package in PACKAGES.iterdir():
            if not package.is_dir():
                continue
            data = json.loads((package / 'package.json').read_text())
            versions[data['name']] = data['version']
            self.assertEqual(data['name'], package.name)
            self.assertEqual(data['unity'], '6000.6')
            self.assertEqual((package / 'LICENSE.md').read_bytes(), (ROOT / 'LICENSE').read_bytes())
            self.assertTrue((package / 'README.md').is_file())
        lock = json.loads((PACKAGES.parent / 'test-packages-lock.json').read_text())['dependencies']
        for package in PACKAGES.iterdir():
            if not package.is_dir():
                continue
            data = json.loads((package / 'package.json').read_text())
            for name, version in data['dependencies'].items():
                self.assertEqual(versions.get(name, lock[name]['version']), version)
        self.assertEqual(lock['com.unity.test-framework']['version'], '1.8.0')

    def test_new_copy_is_self_contained_and_existing_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp).resolve() / '中文 isolated'
            result = prepare_m2.prepare(dest)
            self.assertFalse(result['unityExecuted'])
            inputs = json.loads((dest / 'grea-m2-inputs.json').read_text())
            self.assertGreater(len(inputs), 30)
            for source in PACKAGES.rglob('*'):
                if source.is_file():
                    self.assertEqual(source.read_bytes(), (dest / 'Packages' / source.relative_to(PACKAGES)).read_bytes())
            marker = dest / 'human.txt'; marker.write_text('keep')
            with self.assertRaises(ValueError):
                prepare_m2.prepare(dest)
            self.assertEqual(marker.read_text(), 'keep')
            self.assertFalse((dest / 'Library').exists())

    def test_symlink_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); (root / 'real').mkdir()
            try:
                (root / 'link').symlink_to(root / 'real', target_is_directory=True)
            except OSError:
                self.skipTest('Symlink creation unavailable')
            with self.assertRaises(ValueError):
                prepare_m2.prepare(root / 'link' / 'project')
            self.assertEqual(list((root / 'real').iterdir()), [])

    def test_packages_can_be_prepared_without_game_assemblies(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp).resolve() / 'packages-only'
            result = prepare_m2.prepare(dest, include_sample=False)
            self.assertFalse(result['includesSample'])
            self.assertEqual(list((dest / 'Assets').iterdir()), [])
            self.assertTrue((dest / 'Packages/com.grea.foundation/package.json').is_file())


if __name__ == '__main__':
    unittest.main()
