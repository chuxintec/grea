import ast
import unittest
from pathlib import Path


class ImportBoundaries(unittest.TestCase):
    def test_evidence_and_authoring_utilities_do_not_import_engine_adapters(self):
        from grea.features import helper
        for name in ('evidence_manifest.py', 'unity_asset_ledger.py', 'config_preflight.py', 'performance_compare.py', 'presentation_audit.py'):
            for node in ast.walk(ast.parse(Path(helper(name[:-3]).__file__).read_text())):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn(node.module, ('grea.development.toolkit.cocos_assets', 'grea.features.config.unity_config_candidate'), name)


if __name__ == '__main__':
    unittest.main()
