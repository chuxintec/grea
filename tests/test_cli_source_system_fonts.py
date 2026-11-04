import contextlib
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from monkey.cli import main


class SourceSystemFontCliTests(unittest.TestCase):
    def test_preparation_needing_static_generation_is_explicit_partial(self):
        result=SimpleNamespace(status='needs_static_generation',record={
            'status':'needs_static_generation','nextAction':{'code':'GENERATE_STATIC_SDF_INPUTS'}})
        stdout=io.StringIO()
        with patch('monkey.source_system_font_preparation.prepare',return_value=result) as prepare, contextlib.redirect_stdout(stdout):
            code=main(['prepare-source-system-fonts','--request','request.json',
                       '--expected-request','a'*64,'--out','new-output'])
        self.assertEqual(code,1)
        self.assertEqual(json.loads(stdout.getvalue()),result.record)
        prepare.assert_called_once_with('request.json','a'*64,'new-output')

    def test_generation_forwards_explicit_budget_and_reports_readiness(self):
        result=SimpleNamespace(status='prepared',record={'status':'prepared','nativeImport':'not_run'})
        stdout=io.StringIO()
        with patch('monkey.source_system_font_preparation.generate',return_value=result) as generate, contextlib.redirect_stdout(stdout):
            code=main(['generate-source-system-fonts','--preparation','manifest.json',
                       '--expected-preparation','b'*64,'--out','new-output','--budget-seconds','17'])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(stdout.getvalue()),result.record)
        generate.assert_called_once_with('manifest.json','b'*64,'new-output',budget_seconds=17)
