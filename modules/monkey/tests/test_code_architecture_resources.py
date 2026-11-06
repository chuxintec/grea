import hashlib
import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from monkey.candidate_snapshot import snapshot, verify
from monkey.code_architecture_resources import (
    PROVENANCE_KIND,
    PROVENANCE_STATEMENT,
    ROLE,
    SCHEMA,
    add_json_assets,
)
from monkey.io import encoded
from monkey.sources.compiled import ParseError


ARCH_SHA = 'b' * 64
ROOT_NAMESPACE = 'RecoveredGame'
CONFIG_PATH = 'Assets/Game/Content/Config/Test/BootstrapSeed.json'
ARTIFACT_PATH = 'generated/bootstrap-seed.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_candidate(root: Path, extra_files=None):
    root.mkdir(parents=True)
    files = {
        'Assets/Game/Domain/Core/State.cs': (
            b'namespace RecoveredGame.Domain.Core { public class State { public int Value { get; set; } } }\n'),
        'Assets/Game/Domain/Core/State.cs.meta': (
            b'fileFormatVersion: 2\nguid: ' + b'a' * 32 + b'\nTextScriptImporter:\n  externalObjects: {}\n'),
        'SourceRecovery/config-source.json': b'{"retainedSourceEvidence":true}\n',
    }
    files.update(extra_files or {})
    rows = []
    for path, raw in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        row = {
            'path': path,
            'sha256': sha(raw),
            'bytes': len(raw),
            'owner': 'generated' if path.startswith('Assets/') else 'retained',
            'sourceKind': 'architecture-module' if path.endswith('.cs') else 'source-evidence',
        }
        if path.endswith('State.cs'):
            row['provenance'] = {'classId': 'RecoveredGame.Domain.Core.State', 'module': 'Core', 'layer': 'Domain'}
        elif path.endswith('.meta'):
            row['sourceKind'] = 'architecture-script-meta'
            row['provenance'] = {'classId': 'RecoveredGame.Domain.Core.State'}
        rows.append(row)
    manifest = {
        'schemaVersion': 1,
        'targetProfile': 'unity-6000.6.2f1-ugui',
        'namespace': ROOT_NAMESPACE,
        'architectureSchemaVersion': 'monkey-native-architecture-candidate/1',
        'provenance': {'kind': 'native-architecture-assembly', 'architecturePlanSha256': ARCH_SHA},
        'status': 'candidate',
        'implementationStatus': 'reviewed',
        'compiled': True,
        'compileStatus': 'passed',
        'runtime': 'passed',
        'runtimeStatus': 'passed',
        'classPaths': {'RecoveredGame.Domain.Core.State': 'Assets/Game/Domain/Core/State.cs'},
        'scriptIdentities': {'RecoveredGame.Domain.Core.State': {'guid': 'a' * 32, 'path': 'Assets/Game/Domain/Core/State.cs'}},
        'implementedClassPaths': ['Assets/Game/Domain/Core/State.cs'],
        'missingClassPaths': [],
        'files': sorted(rows, key=lambda row: row['path']),
    }
    manifest_raw = encoded(manifest)
    (root / 'manifest.json').write_bytes(manifest_raw)
    return manifest, sha(manifest_raw)


def asset_row(path=CONFIG_PATH, artifact_path=ARTIFACT_PATH, raw=None, *,
              role=ROLE, source_id='candidate-local-test:bootstrap-seed',
              kind=PROVENANCE_KIND, statement=PROVENANCE_STATEMENT):
    if raw is None:
        raw = b'{"accountId":"local-test","inventory":[{"itemId":"seed-coin","count":25}]}\n'
    return {
        'path': path,
        'artifactPath': artifact_path,
        'sha256': sha(raw),
        'bytes': len(raw),
        'role': role,
        'provenance': {
            'kind': kind,
            'sourceId': source_id,
            'logicalKey': 'Bootstrap/LocalTestSeed',
            'statement': statement,
        },
    }


class JsonAssetProducerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.root = Path(self.temp.name)
        self.base = self.root / 'base'
        self.base_manifest, self.base_sha = write_candidate(self.base)
        self.inputs = self.root / 'json-inputs'
        self.inputs.mkdir()
        self.spec_path = self.inputs / 'resource-spec.json'
        self.artifact_path = self.inputs / ARTIFACT_PATH
        self.artifact_path.parent.mkdir(parents=True)
        self.artifact_bytes = b'{"accountId":"local-test","inventory":[{"itemId":"seed-coin","count":25}]}\n'
        self.output = self.root / 'output-candidate'
        self.write_spec()

    def tearDown(self):
        self.temp.cleanup()

    def write_spec(self, *, raw=None, row=None, extra=None, revision_id='local-seed-r1'):
        if raw is not None:
            self.artifact_bytes = raw
            self.artifact_path.write_bytes(raw)
        else:
            self.artifact_path.write_bytes(self.artifact_bytes)
        row = row or asset_row(raw=self.artifact_bytes)
        spec = {
            'schemaVersion': SCHEMA,
            'baseManifestSha256': self.base_sha,
            'architecturePlanSha256': ARCH_SHA,
            'revisionId': revision_id,
            'assets': [row],
        }
        if extra:
            spec.update(extra)
        raw_spec = encoded(spec)
        self.spec_path.write_bytes(raw_spec)
        return raw_spec

    def rebuild_candidate(self, extra_files):
        shutil.rmtree(self.base)
        self.base_manifest, self.base_sha = write_candidate(self.base, extra_files)
        self.write_spec()

    def run_producer(self, *, output=None, expected_base=None, expected_spec=None):
        raw_spec = self.spec_path.read_bytes()
        return add_json_assets(
            self.base,
            expected_base or self.base_sha,
            self.spec_path,
            expected_spec or sha(raw_spec),
            output or self.output,
        )

    def test_adds_only_local_test_json_and_meta_to_a_fresh_complete_candidate(self):
        original_snapshot = snapshot(self.base)
        input_hashes = {
            self.spec_path: sha(self.spec_path.read_bytes()),
            self.artifact_path: sha(self.artifact_path.read_bytes()),
            self.base / 'manifest.json': sha((self.base / 'manifest.json').read_bytes()),
        }
        for path, row in original_snapshot[2].items():
            input_hashes[self.base / path] = row['sha256']

        output_manifest = self.run_producer()
        output_root, verified_manifest, output_rows, _ = snapshot(self.output)
        verify(output_root, output_rows)
        self.assertEqual(output_manifest, verified_manifest)
        self.assertEqual(output_manifest['architectureSchemaVersion'], self.base_manifest['architectureSchemaVersion'])
        self.assertEqual(output_manifest['classPaths'], self.base_manifest['classPaths'])
        self.assertEqual(output_manifest['scriptIdentities'], self.base_manifest['scriptIdentities'])
        self.assertFalse(output_manifest['compiled'])
        self.assertEqual(output_manifest['compileStatus'], 'not_run')
        self.assertEqual(output_manifest['runtimeStatus'], 'not_run')
        self.assertTrue(set(original_snapshot[2]).issubset(output_rows))
        self.assertEqual((self.output / CONFIG_PATH).read_bytes(), self.artifact_bytes)
        self.assertFalse(any(path.endswith('.cs') for path in set(output_rows) - set(original_snapshot[2])))

        row = output_rows[CONFIG_PATH]
        self.assertEqual(row['owner'], 'generated')
        self.assertEqual(row['sourceKind'], 'candidate-local-test-json')
        self.assertEqual(row['provenance']['role'], ROLE)
        self.assertEqual(row['provenance']['kind'], PROVENANCE_KIND)
        self.assertIn('not recovered', row['provenance']['statement'])
        self.assertEqual(row['provenance']['artifactSha256'], sha(self.artifact_bytes))
        self.assertIn(row['provenance']['guid'], (self.output / (CONFIG_PATH + '.meta')).read_text())
        meta_row = output_rows[CONFIG_PATH + '.meta']
        self.assertEqual(meta_row['sourceKind'], 'candidate-local-test-json-meta')
        receipt = output_manifest['jsonAssetReceipt']
        self.assertEqual(receipt['schemaVersion'], 'monkey-native-json-asset-receipt/1')
        self.assertEqual(receipt['role'], ROLE)
        self.assertEqual(len(receipt['assets']), 1)

        for path, digest in input_hashes.items():
            self.assertEqual(sha(path.read_bytes()), digest, f'input was modified: {path}')

    def test_guid_is_deterministic_across_new_revision_outputs(self):
        first = self.run_producer()
        self.write_spec(revision_id='local-seed-r2')
        second = self.run_producer(output=self.root / 'output-candidate-2')
        guid1 = first['jsonAssetReceipt']['assets'][0]['guid']
        guid2 = second['jsonAssetReceipt']['assets'][0]['guid']
        self.assertEqual(guid1, guid2)

    def test_strict_json_rejects_duplicate_keys_nonfinite_invalid_utf8_and_non_object_roots(self):
        cases = [
            ('duplicate', b'{"seed":1,"seed":2}'),
            ('nan', b'{"seed":NaN}'),
            ('positive-infinity', b'{"seed":1e999}'),
            ('invalid-utf8', b'{"seed":"\xff"}'),
            ('unpaired-surrogate', b'{"seed":"\\ud800"}'),
            ('bom', b'\xef\xbb\xbf{"seed":1}'),
            ('array-root', b'[1,2]'),
        ]
        for label, raw in cases:
            with self.subTest(label=label):
                self.write_spec(raw=raw)
                with self.assertRaises(ParseError):
                    self.run_producer(output=self.root / ('output-' + label))
                self.assertFalse((self.root / ('output-' + label)).exists())

    def test_role_and_provenance_must_explicitly_mark_self_authored_local_test_values(self):
        rows = [
            asset_row(raw=self.artifact_bytes, role='recovered-original'),
            asset_row(raw=self.artifact_bytes, kind='original-source'),
            asset_row(raw=self.artifact_bytes, source_id='original:identity-table'),
            asset_row(raw=self.artifact_bytes, statement='Recovered from the game.'),
        ]
        for index, row in enumerate(rows):
            with self.subTest(index=index):
                self.write_spec(row=row)
                with self.assertRaises(ParseError):
                    self.run_producer(output=self.root / f'bad-provenance-{index}')
                self.assertFalse((self.root / f'bad-provenance-{index}').exists())

    def test_only_canonical_config_json_paths_are_allowed(self):
        paths = [
            '../Assets/Game/Content/Config/Test/seed.json',
            'Assets/Game/Content/Config/../Test/seed.json',
            'Assets/Game/Content/Config/Test/seed.JSON',
            'Assets/Game/Content/Config/Test/seed.json.meta',
            'Assets/Game/Content/Resources/seed.json',
            'Assets/Game/Content/Audio/seed.json',
        ]
        for index, path in enumerate(paths):
            with self.subTest(path=path):
                self.write_spec(row=asset_row(path=path, raw=self.artifact_bytes))
                with self.assertRaises(ParseError):
                    self.run_producer(output=self.root / f'bad-path-{index}')
                self.assertFalse((self.root / f'bad-path-{index}').exists())

    def test_spec_pin_schema_and_exact_artifact_inventory_fail_closed(self):
        with self.assertRaises(ParseError):
            self.run_producer(expected_spec='0' * 64)
        self.assertFalse(self.output.exists())

        self.write_spec(extra={'unplanned': True})
        with self.assertRaises(ParseError):
            self.run_producer()
        self.assertFalse(self.output.exists())

        self.write_spec()
        extra = self.inputs / 'unplanned.json'
        extra.write_bytes(b'{"unplanned":true}')
        with self.assertRaises(ParseError):
            self.run_producer()
        self.assertFalse(self.output.exists())

    def test_frozen_candidate_must_have_complete_pinned_inventory(self):
        (self.base / 'unowned.bin').write_bytes(b'outside manifest')
        with self.assertRaises(ParseError):
            self.run_producer()
        self.assertFalse(self.output.exists())

    def test_existing_json_receipt_is_never_overwritten(self):
        self.base_manifest['jsonAssetReceipt'] = {'revisionId': 'prior-receipt'}
        manifest_raw = encoded(self.base_manifest)
        (self.base / 'manifest.json').write_bytes(manifest_raw)
        self.base_sha = sha(manifest_raw)
        self.write_spec()
        with self.assertRaises(ParseError):
            self.run_producer()
        self.assertEqual(json.loads((self.base / 'manifest.json').read_text())['jsonAssetReceipt'],
                         {'revisionId': 'prior-receipt'})
        self.assertFalse(self.output.exists())

    def test_target_collisions_orphan_meta_and_guid_collision_are_rejected(self):
        self.rebuild_candidate({CONFIG_PATH: b'{"old":true}'})
        with self.assertRaises(ParseError):
            self.run_producer(output=self.root / 'target-collision')
        self.assertFalse((self.root / 'target-collision').exists())

        self.rebuild_candidate({CONFIG_PATH + '.meta': b'fileFormatVersion: 2\nguid: ' + b'c' * 32 + b'\n'})
        with self.assertRaises(ParseError):
            self.run_producer(output=self.root / 'orphan-meta')
        self.assertFalse((self.root / 'orphan-meta').exists())

        stable_ns = uuid.uuid5(uuid.NAMESPACE_URL, 'monkey-native-local-json-namespace:' + ROOT_NAMESPACE)
        colliding_guid = uuid.uuid5(stable_ns, CONFIG_PATH).hex
        self.rebuild_candidate({'Assets/Game/Other/retained.asset.meta':
                                f'fileFormatVersion: 2\nguid: {colliding_guid}\n'.encode()})
        with self.assertRaises(ParseError):
            self.run_producer(output=self.root / 'guid-collision')
        self.assertFalse((self.root / 'guid-collision').exists())

    def test_all_inputs_are_disjoint_from_output_and_existing_output_is_preserved(self):
        with self.assertRaises(ParseError):
            self.run_producer(output=self.base / 'nested-output')
        with self.assertRaises(ParseError):
            self.run_producer(output=self.inputs / 'nested-output')
        self.assertFalse((self.base / 'nested-output').exists())
        self.assertFalse((self.inputs / 'nested-output').exists())

        existing = self.root / 'existing-output'
        existing.mkdir()
        sentinel = existing / 'keep.txt'
        sentinel.write_text('preserve', encoding='utf-8')
        with self.assertRaises(ParseError):
            self.run_producer(output=existing)
        self.assertEqual(sentinel.read_text(encoding='utf-8'), 'preserve')


if __name__ == '__main__':
    unittest.main()
