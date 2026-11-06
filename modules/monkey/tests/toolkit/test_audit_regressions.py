"""Independent counterexamples retained from the GREA product audit (export_config_tables)."""
import json
import tempfile
import types
import unittest
from pathlib import Path

from monkey.toolkit import export_config_tables


class AuditRegressions(unittest.TestCase):
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
