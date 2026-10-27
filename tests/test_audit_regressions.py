"""Independent counterexamples retained from the product audit."""
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from grea.tools.unity_framework_audit import inspect


class AuditRegressions(unittest.TestCase):
    def test_explicit_provider_state_does_not_require_a_home_directory(self):
        from grea.integrations import beaver
        from grea.integrations.monkey import local
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict('os.environ', {'GREA_PROVIDER_STATE_DIR': folder}, clear=True), patch.object(Path, 'home', side_effect=RuntimeError('No home')):
                self.assertEqual(beaver.state_root(), Path(folder).absolute() / 'beaver')
                self.assertEqual(local.state_root(), Path(folder).absolute() / 'monkey')

    def test_package_source_guard_infers_consumer_namespace(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            packages, sample = root / 'packages', root / 'sample'
            packages.mkdir(); sample.mkdir()
            (packages / 'Runtime.asmdef').write_text(json.dumps({'name': 'Grea.Runtime'}))
            (sample / 'Domain.asmdef').write_text(json.dumps({'name': 'Example.Domain', 'noEngineReferences': True}))
            (packages / 'Consumer.cs').write_text('using Example.Domain; class Consumer {}')
            report = inspect(packages, sample)
            self.assertIn('PACKAGE_PROJECT_SOURCE', {row['code'] for row in report['findings']})
            (packages / 'Consumer.cs').write_text('using ExampleTools; class Consumer {}')
            self.assertTrue(inspect(packages, sample)['ok'])

    def test_missing_or_empty_framework_input_is_not_clean(self):
        with tempfile.TemporaryDirectory() as folder:
            for root in [Path(folder), Path(folder) / 'missing']:
                report = inspect(root)
                self.assertFalse(report['ok'])
                self.assertEqual(report['assemblies'], 0)
                self.assertTrue(report['findings'])


if __name__ == '__main__':
    unittest.main()
