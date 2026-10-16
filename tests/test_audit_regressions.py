"""Independent counterexamples retained from the product audit."""
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest

from grea.tools.evidence_manifest import verify
from grea.tools.unity_framework_audit import inspect
from grea.tools import export_config_tables


class AuditRegressions(unittest.TestCase):
    def test_removed_identity_is_not_an_unchanged_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / 'a').write_bytes(b'a')
            def entry(name):
                return dict(id=name, layer='source', path=name, bytes=1,
                            sha256=hashlib.sha256(name.encode()).hexdigest())
            previous = dict(schema_version=1, scope='same', entries=[entry('a'), entry('b')])
            current = dict(schema_version=1, scope='same', entries=[entry('a')])
            report = verify(root, current, 'flat-v1', previous)
            self.assertEqual(report['current_closure'], 'verified')
            self.assertEqual(report['manifest_diff']['removed'][0]['id'], 'b')
            self.assertEqual(report['status'], 'needs_review')

    def test_missing_or_empty_framework_input_is_not_clean(self):
        with tempfile.TemporaryDirectory() as folder:
            for root in [Path(folder), Path(folder) / 'missing']:
                report = inspect(root)
                self.assertFalse(report['ok'])
                self.assertEqual(report['assemblies'], 0)
                self.assertTrue(report['findings'])

    def test_textasset_export_does_not_invent_source_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'source.bundle'
            source.write_bytes(b'synthetic-provider-input')
            asset = types.SimpleNamespace(m_Name='ShopSettings', m_Script=b'{"currency":"gold"}')
            obj = types.SimpleNamespace(type=types.SimpleNamespace(name='TextAsset'), path_id=7,
                                        assets_file=types.SimpleNamespace(name='data'), read=lambda: asset)
            environment = types.SimpleNamespace(objects=[obj], container={})
            export_config_tables.export_environment(environment, source, root / 'output')
            report = json.loads((root / 'output/TABLE_INDEX.json').read_text())
            self.assertIsNone(report['tables'][0]['logical_path'])
            summary = json.loads((root / 'output/LEVEL_TABLE_SUMMARY.json').read_text())
            self.assertEqual(summary['status'], 'not_applicable')

    def test_level_adapter_never_passes_without_its_required_tables(self):
        summary = export_config_tables.level_summary({'Shop': {'currency': 'gold'}})
        self.assertEqual(summary['status'], 'not_applicable')
        self.assertEqual(len(summary['missing_tables']), 3)


if __name__ == '__main__':
    unittest.main()
