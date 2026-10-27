"""Independent counterexamples retained from the product audit."""
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest

from grea.tools.unity_framework_audit import inspect


class AuditRegressions(unittest.TestCase):
    def test_missing_or_empty_framework_input_is_not_clean(self):
        with tempfile.TemporaryDirectory() as folder:
            for root in [Path(folder), Path(folder) / 'missing']:
                report = inspect(root)
                self.assertFalse(report['ok'])
                self.assertEqual(report['assemblies'], 0)
                self.assertTrue(report['findings'])


if __name__ == '__main__':
    unittest.main()
