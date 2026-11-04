import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monkey.cli import main


class ExportDispatchTests(unittest.TestCase):
    def test_native_project_export_is_not_shadowed_by_texture_export(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory).resolve() / 'plan.json'
            plan.write_text(json.dumps({'targetProfile': 'unity-6000.6.2f1-ugui'}))
            output = str(Path(directory).resolve() / 'candidate')
            with patch('monkey.cli.export', return_value={'status': 'partial', 'diagnostics': []}) as export:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(['export', '--plan', str(plan), '--out', output]), 1)
                export.assert_called_once_with(str(plan), output)
