"""Consume generated native-binding specs through the existing intake planner."""
import json
import tempfile
import unittest
from pathlib import Path

from grea.development.errors import BeaverError
from grea.development.intake_binding_spec import generate
from grea.development.io import sha, write_json
from grea.development.output_limits import digest_file
from .test_intake_binding_export import BindingExportTests
from .test_intake import _write_asset


class BindingSpecTests(unittest.TestCase):
    def setup_export(self, root):
        helper = BindingExportTests()
        fixture = helper.fixture(root)
        export = helper.export(fixture)
        mapping = root / 'mapping.json'
        write_json(mapping, dict(additions=[dict(source='Assets/Panel.prefab', target='Assets/Recovered/Panel.prefab'),
                                           dict(source='Assets/Material.mat', target='Assets/Recovered/Material.mat')]))
        return fixture, export, mapping

    def test_normal_spec_is_consumed_and_signed_reference_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            f, export, mapping = self.setup_export(root)
            receipt_path = root / 'old-receipt.json'
            write_json(receipt_path, dict(owningExport='required_GREA_freeze_native_selection', consumerExport=export))
            original = receipt_path.read_bytes()
            result = generate(export['candidate'], f['target'], export['candidateManifestSha256'], mapping, root / 'out', preparation_receipt=receipt_path)
            corrected = json.loads((root / 'out/preparation-receipt.json').read_text())
            self.assertEqual(corrected['owningExport'], 'exported')
            self.assertEqual(receipt_path.read_bytes(), original)
            self.assertEqual(corrected['supersedesReceipt']['sha256'], sha(original))
            self.assertEqual(result['status'], 'planned')
            self.assertEqual(result['uncoveredCompilerInputs'], 0)
            self.assertEqual(result['intakePlan']['externalScripts'], 1)
            spec = json.loads(Path(result['spec']).read_text())
            refs = [field['value'] for obj in spec['verifications'][0]['objects'] for field in obj['fields'] if field['kind'] == 'object']
            self.assertTrue(any(ref['localId'] == -2100000 for ref in refs))
            self.assertFalse((f['target'] / 'Assets/Recovered').exists())

    def test_unclassified_compiler_is_never_falsely_omitted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            f, export, mapping = self.setup_export(root)
            candidate = Path(export['candidate'])
            _write_asset(candidate, 'Assets/Unclassified.cs', b'public class Unclassified {}', '8' * 32)
            manifest_path = candidate / 'manifest.json'
            manifest = json.loads(manifest_path.read_text())
            for name in ('Assets/Unclassified.cs', 'Assets/Unclassified.cs.meta'):
                raw = (candidate / name).read_bytes()
                manifest['files'].append(dict(path=name, sha256=sha(raw), bytes=len(raw), owner='generated'))
            write_json(manifest_path, manifest)
            result = generate(candidate, f['target'], digest_file(manifest_path), mapping, root / 'out')
            self.assertEqual(result['status'], 'blocked')
            self.assertEqual(result['intakePlan']['error']['code'], 'INTAKE_COMPILER_COVERAGE')
            report = json.loads(Path(result['report']).read_text())
            self.assertEqual([r['path'] for r in report['uncoveredCompilerInputs']], ['Assets/Unclassified.cs'])
            self.assertEqual(report['uncoveredCompilerInputs'][0]['nativeScriptTypes'], [])
            spec = json.loads(Path(result['spec']).read_text())
            self.assertNotIn('Assets/Unclassified.cs', [r['path'] for r in spec['omittedCompilerInputs']])
            self.assertFalse((f['target'] / 'Assets/Recovered').exists())

    def test_real_package_conflict_is_reported_without_install(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            f, export, mapping = self.setup_export(root)
            candidate = Path(export['candidate'])
            package = candidate / 'Packages/manifest.json'
            write_json(package, dict(dependencies={'com.unity.ugui': '2.6.0'}))
            manifest_path = candidate / 'manifest.json'
            manifest = json.loads(manifest_path.read_text())
            row = next(r for r in manifest['files'] if r['path'] == 'Packages/manifest.json')
            row.update(sha256=digest_file(package), bytes=package.stat().st_size)
            write_json(manifest_path, manifest)
            target_package = f['target'] / 'Packages/manifest.json'
            write_json(target_package, dict(dependencies={'com.unity.ugui': '2.0.0'}))
            original = target_package.read_bytes()
            result = generate(candidate, f['target'], digest_file(manifest_path), mapping, root / 'out')
            report = json.loads(Path(result['report']).read_text())
            self.assertEqual(result['intakePlan']['error']['code'], 'INTAKE_REQUIREMENTS')
            self.assertEqual(report['requirementConflicts'][0]['current'], '2.0.0')
            self.assertEqual(report['requirementConflicts'][0]['desired'], '2.6.0')
            self.assertEqual(target_package.read_bytes(), original)
            self.assertFalse((f['target'] / 'Assets/Recovered').exists())

    def test_manifest_drift_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            f, export, mapping = self.setup_export(root)
            with self.assertRaises(BeaverError) as error:
                generate(export['candidate'], f['target'], '0' * 64, mapping, root / 'out')
            self.assertEqual(error.exception.code, 'INTAKE_CANDIDATE_DRIFT')
            self.assertFalse((root / 'out').exists())
