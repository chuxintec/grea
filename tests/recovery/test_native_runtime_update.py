import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from grea.recovery.native_runtime_update import upgrade
from grea.recovery.sources.compiled import ParseError


TEMPLATES = Path(__file__).parents[2] / 'src/grea/recovery/targets'


class NativeRuntimeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'input'
        self.root.mkdir()
        self.files = []
        for index, name in enumerate(('NativeStaticSortQueueProxyPresenter.cs', 'NativeStaticSortQueueProxyGraphic.cs',
            'NativeStaticSortQueueProxyMarker.cs', 'NativeStaticSortTextSource.cs',
            'NativeInputBlocker.cs', 'NativeInputBlockerSurface.cs')):
            self.add('Assets/Runtime/' + name, (TEMPLATES / name).read_bytes())
            self.add('Assets/Runtime/' + name + '.meta', f'fileFormatVersion: 2\nguid: {index + 1:032x}\n'.encode())
        self.add('Assets/UI.prefab', b'%YAML 1.1\n--- !u!1 &100\nGameObject: {m_Name: Example}\n')
        self.add('Assets/UI.prefab.meta', b'fileFormatVersion: 2\nguid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n')
        self.manifest = dict(schemaVersion=1, targetProfile='unity-6000.6.2f1-ugui', namespace='neutral',
            sourceNativeReadbackSha256='b' * 64, selection={'prefabs': ['Assets/UI.prefab']}, files=self.files)

    def add(self, path, raw):
        target = self.root / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        self.files.append(dict(path=path, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), owner='generated'))

    def seal(self):
        raw = json.dumps(self.manifest).encode(); (self.root / 'manifest.json').write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def test_only_code_changes_and_preserves_original_assets_and_identities(self):
        digest = self.seal(); output = self.root.parent / 'output'
        result = upgrade(self.root, digest, output)
        self.assertEqual((self.root / 'Assets/UI.prefab').read_bytes(), (output / 'Assets/UI.prefab').read_bytes())
        for row in self.files:
            self.assertEqual(hashlib.sha256((self.root / row['path']).read_bytes()).hexdigest(), row['sha256'])
            if row['path'].endswith('.meta'):
                self.assertEqual((self.root / row['path']).read_bytes(), (output / row['path']).read_bytes())
        nodes = {row['path'] for row in result['files']}
        for edge in result['adoptionDependencies']['edges']:
            self.assertIn(edge['path'], nodes)
            self.assertTrue(set(edge['requires']) <= nodes)
        for name in ('NativeStaticSortQueueRuntime.cs', 'NativeStaticSortQueueProxyRaycaster.cs'):
            self.assertIn('Assets/Runtime/' + name + '.meta', nodes)
        self.assertEqual('pending', result['runtimeUpdate']['nativeValidation'])
        second = self.root.parent / 'second'
        again = upgrade(self.root, digest, second)
        self.assertEqual(result, again)

    def test_consumer_edited_helper_is_rejected_without_output(self):
        row = next(x for x in self.files if x['path'].endswith('/NativeStaticSortQueueProxyPresenter.cs'))
        raw = (self.root / row['path']).read_bytes() + b'\n// consumer edit\n'
        (self.root / row['path']).write_bytes(raw)
        row.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        out = self.root.parent / 'rejected'
        with self.assertRaises(ParseError): upgrade(self.root, self.seal(), out)
        self.assertFalse(out.exists())

    def test_non_guid_dependency_or_frozen_meta_cannot_be_omitted(self):
        row = next(x for x in self.files if x['path'].endswith('/NativeInputBlockerSurface.cs'))
        self.files.remove(row); (self.root / row['path']).unlink()
        with self.assertRaises(ParseError): upgrade(self.root, self.seal(), self.root.parent / 'missing')
        self.assertFalse((self.root.parent / 'missing').exists())

    def test_hash_drift_and_symlink_never_write_output(self):
        digest = self.seal()
        (self.root / 'Assets/UI.prefab').write_bytes(b'changed')
        out = self.root.parent / 'drift'
        with self.assertRaises(ParseError): upgrade(self.root, digest, out)
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
