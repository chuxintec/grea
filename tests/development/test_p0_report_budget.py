"""Large report transport reaches semantic planning without relaxing spec limits."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import hashlib
from grea.development.cli import main, _p0_report
from grea.development.errors import BeaverError
from grea.development.io import read, write_json
from grea.development.output_limits import MANIFEST_BYTES
from grea.development.structure_audit import inspect
from .test_structure_audit import put, native_readback


class P0ReportBudgetTests(unittest.TestCase):
    def test_large_real_shaped_report_reaches_cli_planning(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as tmp:
            product=Path(tmp).resolve();project=product/'Unity'
            for n in ('Assets','Packages','ProjectSettings'):(project/n).mkdir(parents=True)
            write_json(product/'grea-project.json',{'schemaVersion':1,'paths':{'unityProject':'Unity'}})
            put(product,'Docs/PROJECT-STRUCTURE.md','Synthetic transport fixture; no Editor execution.')
            asset='Assets/Legacy/Panel.prefab';put(project,asset,b'SYNTHETIC CONTRACT DATA')
            snapshot=native_readback(project,asset,'UnityEngine.GameObject',77)
            audit=inspect(project,snapshot)
            # Observation rows model a large generated report, not extra source
            # assets or authenticated native observations. Source closure and
            # the selected object remain independently guarded by the planner.
            audit['issues'].extend({'code':'STATIC_OBSERVATION','severity':'info','path':asset,
                'observation':{'index':i,'context':'synthetic transport observation '*16}} for i in range(75000))
            audit_path=product/'large-audit.json';write_json(audit_path,audit)
            self.assertGreater(audit_path.stat().st_size,32*1024**2)
            with self.assertRaises(BeaverError):read(audit_path)
            mapping=product/'mapping.json';write_json(mapping,[{'source':asset,'target':'Assets/Game/Content/Prefabs/Panel.prefab'}])
            stdout=io.StringIO()
            with redirect_stdout(stdout):code=main(['structure','plan','--audit',str(audit_path),'--mappings',str(mapping),'--out',str(product/'plan')])
            result=json.loads(stdout.getvalue())
            self.assertEqual(code,0,result.get('diagnostics'))
            self.assertEqual(result['data']['status'],'declaration_only')
            self.assertEqual(result['verification']['native'],'not_run')
            self.assertEqual(result['data']['projectConformance'],'not-established')
            # A compact transport envelope must retain the entire file and its
            # exact artifact hash, rather than trim inventory or consumers.
            digest=hashlib.sha256(audit_path.read_bytes()).hexdigest()
            with patch('grea.development.cli.dispatch',return_value=dict(audit,report=str(audit_path))):
                stdout=io.StringIO()
                with redirect_stdout(stdout):code=main(['structure','inspect','--project',str(project),'--out',str(product/'unused'),'--summary'])
            self.assertEqual(code,0)
            compact=json.loads(stdout.getvalue())
            self.assertLess(len(stdout.getvalue().encode()),16*1024)
            self.assertEqual(compact['data']['issuesCount'],len(audit['issues']))
            self.assertEqual(compact['artifacts'][0]['sha256'],digest)
            self.assertEqual(hashlib.sha256(audit_path.read_bytes()).hexdigest(),digest)

    def test_report_reader_still_rejects_over_dedicated_budget(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as tmp:
            path=Path(tmp)/'oversized-report.json'
            with path.open('wb') as f:f.truncate(MANIFEST_BYTES+1)
            with self.assertRaises(BeaverError) as error:_p0_report(path)
            self.assertEqual(error.exception.code,'BYTE_BUDGET')


if __name__=='__main__':unittest.main()
