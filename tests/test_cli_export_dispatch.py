import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monkey.cli import main


class ExportDispatchTests(unittest.TestCase):
    def test_static_spine_refresh_routes_exact_request_pin_without_decode(self):
        report = {'preparationStatus':'prepared','planPath':'fresh/plan/plan.json','native':'not_run','visual':'not_run'}
        with patch('monkey.prefab_static_spine_refresh.prepare', return_value=report) as prepare:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = main(['refresh-static-spine-helpers', '--request', 'request.json',
                               '--expected-request', 'a'*64, '--out', 'fresh'])
        self.assertEqual(result, 0)
        prepare.assert_called_once_with('request.json', 'a'*64, 'fresh')
        self.assertEqual(json.loads(output.getvalue()), report)

    def test_native_project_export_is_not_shadowed_by_texture_export(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory).resolve() / 'plan.json'
            plan.write_text(json.dumps({'targetProfile': 'unity-6000.6.2f1-ugui'}))
            output = str(Path(directory).resolve() / 'candidate')
            with patch('monkey.cli.export', return_value={'status': 'partial', 'diagnostics': []}) as export:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(['export', '--plan', str(plan), '--out', output]), 1)
                export.assert_called_once_with(str(plan), output)


class TextureMaterialDispatchTests(unittest.TestCase):
    def test_selected_material_command_routes_pins_and_budget(self):
        with patch('monkey.unity_prefab_texture_material_rebuild.execute', return_value={'status': 'native-assets-verified-subset'}) as execute:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = main(['rebuild-unity-prefab-texture-material-assets', '--request', 'request.json',
                               '--expected-request', 'a' * 64, '--unity-editor', '/exact/Unity',
                               '--budget-seconds', '120', '--out', 'fresh-output'])
            self.assertEqual(result, 0)
            execute.assert_called_once_with('request.json', 'a' * 64, 'fresh-output', '/exact/Unity', 120)
            self.assertEqual(json.loads(output.getvalue())['status'], 'native-assets-verified-subset')
