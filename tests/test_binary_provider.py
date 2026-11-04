"""Artifact guard tests use inert header fixtures; no native run is inferred."""
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from grea import binary_provider as binary
from grea.common import GreaError, digest, hash_file


def fixture(root):
    root = Path(root)
    entry = root/'beaver'
    entry.write_bytes(b'\xcf\xfa\xed\xfe' + struct.pack('<I', 0x0100000c) + b'inert-test-only')
    entry.chmod(0o755)
    (root/'resource.json').write_text('{}')
    data = dict(schemaVersion=1, contract=binary.CONTRACT, provider='beaver', version='0.6.0',
                sourceCommit=binary.APPROVED_SOURCES[('beaver', '0.6.0')],
                target={'system': 'Darwin', 'architecture': 'arm64'}, entrypoint='beaver',
                capabilitiesSha256='0'*64, capabilitiesProjection='beaver-capabilities-stable/1', sourceBoundary={'status': 'fixture-not-distribution-audit'},
                files=[dict(path=p.name, sha256=hash_file(p)['sha256'], bytes=p.stat().st_size)
                       for p in [entry, root/'resource.json']])
    cap = dict(contract='beaver-result/1',status='ok',operationId='variable-request-id',
               producer=dict(name='beaver',version='0.6.0',implementationSha256=binary.runtime_identity(data)),
               data=dict(contract='beaver-capabilities/1',fixtureOnly=True))
    data['capabilitiesSha256']=digest(binary.capability_identity('beaver',cap))
    path = root/'binary-provider.json'
    path.write_text(json.dumps(data))
    return path, data, cap


def save(path, data):
    path.write_text(json.dumps(data))
    return hash_file(path)['sha256']


def archive_tree(root, archive, extra=None):
    with zipfile.ZipFile(archive, 'w') as z:
        for p in sorted(Path(root).iterdir()):
            z.write(p, 'beaver/' + p.name)
        for name, raw in (extra or {}).items():
            z.writestr(name, raw)
    return hash_file(archive)['sha256']


@patch('grea.binary_provider.platform.system', return_value='Darwin')
@patch('grea.binary_provider.platform.machine', return_value='arm64')
class BinaryIdentityTests(unittest.TestCase):
    def test_real_inventory_is_separate_from_python_identity(self, *_):
        with tempfile.TemporaryDirectory() as t:
            path, data, cap = fixture(t)
            value = binary.validate(path, hash_file(path)['sha256'], 'beaver', command=[str((Path(t)/'beaver').resolve())], capabilities=cap)
            self.assertEqual(len(value['runtime_files']), 2)
            self.assertNotIn('package_files', value)
            cfg = dict(identity_mode='binary', binary_manifest=value['manifest'], identity_root=value['root'],
                       version='0.6.0', command=value['command'], runtime_files=value['runtime_files'])
            binary.check_lock(cfg, 'beaver', capabilities=cap)
            cfg['runtime_files'] = {}
            with self.assertRaisesRegex(ValueError, 'identity differs'):
                binary.check_lock(cfg, 'beaver')

    def test_manifest_and_capability_drift_are_refused(self, *_):
        with tempfile.TemporaryDirectory() as t:
            path, data, cap = fixture(t)
            with self.assertRaisesRegex(ValueError, 'manifest drift'):
                binary.validate(path, '0' * 64, 'beaver')
            changed = dict(cap, data=dict(cap['data'],changed=True))
            with self.assertRaisesRegex(ValueError, 'capabilities differ'):
                binary.validate(path, hash_file(path)['sha256'], 'beaver', capabilities=changed)

    def test_named_projection_excludes_only_volatile_envelope_fields(self, *_):
        with tempfile.TemporaryDirectory() as t:
            path, data, cap = fixture(t); expected=hash_file(path)['sha256']
            binary.validate(path,expected,'beaver',capabilities=dict(cap,operationId='different',diagnostics=[]))
            wrong=dict(cap,producer=dict(cap['producer'],implementationSha256='0'*64))
            data['capabilitiesSha256']=digest(binary.capability_identity('beaver',wrong))
            with self.assertRaisesRegex(ValueError,'actual runtime inventory'):
                binary.validate(path,save(path,data),'beaver',capabilities=wrong)
            data['capabilitiesProjection']='implicit-or-full-envelope'
            with self.assertRaisesRegex(ValueError,'explicit binary capability projection'):
                binary.validate(path,save(path,data),'beaver')

    def test_source_provider_target_and_host_mismatch_are_refused(self, *_):
        for field, value in [('sourceCommit', '0' * 40), ('provider', 'monkey'), ('target', {'system': 'Windows', 'architecture': 'x64'})]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as t:
                path, data, cap = fixture(t); data[field] = value
                with self.assertRaises(ValueError):
                    binary.validate(path, save(path, data), 'beaver')
        with tempfile.TemporaryDirectory() as t:
            path, data, cap = fixture(t)
            with patch('grea.binary_provider.platform.machine', return_value='x86_64'):
                with self.assertRaisesRegex(ValueError, 'actual host'):
                    binary.validate(path, hash_file(path)['sha256'], 'beaver')

    def test_shell_and_wrong_architecture_cannot_impersonate_binary(self, *_):
        for raw in (b'#!/usr/bin/python\n', b'\xcf\xfa\xed\xfe' + struct.pack('<I', 0x01000007)):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as t:
                path, data, cap = fixture(t); entry = Path(t)/'beaver'; entry.write_bytes(raw)
                data['files'][0].update(sha256=hash_file(entry)['sha256'], bytes=len(raw))
                with self.assertRaisesRegex(ValueError, 'actual ARM64 Mach-O'):
                    binary.validate(path, save(path, data), 'beaver')

    def test_changed_missing_unlisted_and_linked_resources_are_refused(self, *_):
        for change in ('changed', 'missing', 'unlisted', 'linked'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as t:
                path, data, cap = fixture(t); expected = hash_file(path)['sha256']; resource = Path(t)/'resource.json'
                if change == 'changed': resource.write_text('changed')
                elif change == 'missing': resource.unlink()
                elif change == 'unlisted': (Path(t)/'extra').write_text('x')
                else: (Path(t)/'linked').symlink_to(resource)
                with self.assertRaises((ValueError, GreaError)):
                    binary.validate(path, expected, 'beaver')

    def test_no_source_fallback_duplicate_or_escaping_path(self, *_):
        for name in ('../escape', '/absolute', 'folder\\escape', 'module.py', 'module.pyc', 'private.whl'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as t:
                path, data, cap = fixture(t)
                data['files'][1]['path'] = name
                with self.assertRaises(ValueError):
                    binary.validate(path, save(path, data), 'beaver')
        with tempfile.TemporaryDirectory() as t:
            path, data, cap = fixture(t); data['files'].append(data['files'][0])
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                binary.validate(path, save(path, data), 'beaver')

    def test_configured_command_must_be_the_actual_entrypoint(self, *_):
        with tempfile.TemporaryDirectory() as t:
            path, data, cap = fixture(t)
            with self.assertRaisesRegex(ValueError, 'actual binary entrypoint'):
                binary.validate(path, hash_file(path)['sha256'], 'beaver', command=['/usr/bin/python', str(Path(t)/'beaver')])

    def test_nested_source_archive_is_refused_even_with_changed_extension(self, *_):
        with tempfile.TemporaryDirectory() as t:
            path, data, cap = fixture(t); p = Path(t)/'resource.json'
            p.write_bytes(b'PK\x03\x04private-fallback')
            data['files'][1].update(sha256=hash_file(p)['sha256'], bytes=p.stat().st_size)
            with self.assertRaisesRegex(ValueError, 'Nested archive'):
                binary.validate(path, save(path, data), 'beaver')

    def test_local_install_is_relocatable_and_keeps_binding_unchanged(self, *_):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); source = root/'source'; source.mkdir(); path, data, cap = fixture(source)
            manifest_sha = hash_file(path)['sha256']; archive = root/'beaver.zip'; archive_sha = archive_tree(source, archive)
            result = binary.install_archive('beaver', archive, archive_sha, manifest_sha, root/'retained', root/'receipt')
            self.assertTrue(result['installed']); self.assertEqual(result['binding'], 'not_changed'); self.assertEqual(result['probe'], 'not_run')
            binary.validate(result['binary_manifest']['path'], manifest_sha, 'beaver')
            again = binary.install_archive('beaver', archive, archive_sha, manifest_sha, root/'retained', root/'receipt2')
            self.assertTrue(again['reused']); self.assertFalse(again['installed'])
            self.assertFalse((root/'retained'/'beaver'/'binding.json').exists())

    def test_install_rejects_hashes_and_archive_escape_before_any_execution(self, *_):
        for extra in ({'beaver/../escape': b'x'}, {'elsewhere': b'x'}):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as t:
                root = Path(t); source = root/'source'; source.mkdir(); path, data, cap = fixture(source)
                archive = root/'beaver.zip'; sha = archive_tree(source, archive, extra)
                with self.assertRaises(ValueError):
                    binary.install_archive('beaver', archive, sha, hash_file(path)['sha256'], root/'state', root/'out')
                self.assertFalse((root/'escape').exists())
                self.assertEqual(list((root/'state').iterdir()), [])
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); source = root/'source'; source.mkdir(); path, data, cap = fixture(source)
            archive = root/'beaver.zip'; archive_tree(source, archive)
            with self.assertRaisesRegex(ValueError, 'archive differs'):
                binary.install_archive('beaver', archive, '0'*64, hash_file(path)['sha256'], root/'state', root/'out')
            self.assertFalse((root/'state').exists())

    def test_bad_binary_pin_never_probes_a_provider(self, *_):
        from grea.integrations import beaver
        from grea.integrations.monkey.identity import create_binary_lock
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); source = root/'source'; source.mkdir(); path, data, cap = fixture(source)
            command = [str((source/'beaver').resolve())]
            with patch('grea.registry.command', return_value=command), patch.object(beaver, 'capability_probe') as probe:
                result = beaver.check(root/'beaver-pin',pin=True,binary_manifest=path,expected_binary_manifest='0'*64)
                self.assertFalse(result['ready']); self.assertIn('manifest drift', result['diagnostic']); probe.assert_not_called()
            with patch('grea.registry.command', side_effect=[command,command+['capabilities','--json']]), patch('grea.runner.execute') as probe:
                with self.assertRaisesRegex(ValueError, 'manifest drift'):
                    create_binary_lock(path,'0'*64,root/'monkey-pin')
                probe.assert_not_called()

    def test_binary_distribution_disables_source_wheel_download_and_install(self, *_):
        from grea import modules
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); (root/'plugin').mkdir()
            (root/'plugin/version.json').write_text(json.dumps({'moduleDistribution': {'mode': 'binary'}}))
            with patch('urllib.request.urlopen') as network, patch('grea.modules.subprocess.run') as process:
                with self.assertRaisesRegex(ValueError, 'Source-wheel fallback is disabled'):
                    modules.fetch(root/'download', root=root)
                with self.assertRaisesRegex(ValueError, 'Source-wheel fallback is disabled'):
                    modules.install('beaver',root/'receipt',root=root)
                network.assert_not_called(); process.assert_not_called()
            self.assertFalse((root/'download').exists())
