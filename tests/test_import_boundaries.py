import ast
from pathlib import Path
import unittest

class ImportBoundaries(unittest.TestCase):
    def test_evidence_and_authoring_utilities_do_not_import_engine_adapters(self):
        root=Path(__file__).resolve().parents[1]/'src/grea'
        for name in ('data_io.py','authoring_output.py'):
            for node in ast.walk(ast.parse((root/name).read_text())):
                if isinstance(node,ast.ImportFrom):
                    self.assertNotIn(node.module,('grea.tools.cocos_assets','grea.tools.unity_config_candidate'),name)
