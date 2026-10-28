"""The opt-in declaration crosses CLI/file boundaries without relaxing lookup guards."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from beaver.cli import main
from beaver.io import write_json
from beaver.structure_audit import inspect
from test_structure_audit import put, native_readback


class ConsumerResolutionCliTests(unittest.TestCase):
    def test_exact_reviewed_comparison_file_reaches_immutable_cli_plan(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as tmp:
            product=Path(tmp).resolve();project=product/'Unity'
            for folder in ('Assets','Packages','ProjectSettings'):(project/folder).mkdir(parents=True)
            write_json(product/'grea-project.json',{'schemaVersion':1,'paths':{'unityProject':'Unity'}})
            put(product,'Docs/PROJECT-STRUCTURE.md','Synthetic declaration contract.')
            asset='Assets/Legacy/Panel.prefab';put(project,asset,b'synthetic asset')
            native=native_readback(project,asset,'UnityEngine.GameObject',77)
            source_path='Assets/Game/Services/SourceIdentity.cs'
            source=put(project,source_path,
                'class SourceIdentity { void Check(Source source) { if(source.containerPath != "Assets/Legacy/Panel.prefab") throw new System.Exception("wrong source"); } }')
            audit=inspect(project,native);row=next(r for r in audit['pathConsumers'] if r['file']==source_path)
            declaration={'schemaVersion':1,'resolutions':[dict(file=source_path,
                fileSha256=hashlib.sha256(source.read_bytes()).hexdigest(),span=row['span'],literal=row['value'],
                kind='source-identity-comparison',reason='Retain the original source container identity.',
                evidence='Synthetic explicit review of source identity comparison; no gameplay proof.')]}
            audit_file=product/'audit.json';write_json(audit_file,audit)
            mapping=product/'mapping.json';write_json(mapping,[{'source':asset,'target':'Assets/Game/Content/Prefabs/Panel.prefab'}])
            declaration_file=product/'comparisons.json';write_json(declaration_file,declaration)
            args=['structure','plan','--audit',str(audit_file),'--mappings',str(mapping),'--summary']
            def invoke(flags):
                output=io.StringIO()
                with contextlib.redirect_stdout(output):code=main(args+flags)
                return code,json.loads(output.getvalue())
            blocked_code,blocked=invoke(['--out',str(product/'blocked')])
            # Blocked declarations remain data, rather than native execution.
            self.assertEqual(blocked['data']['status'],'blocked')
            code,result=invoke(['--consumer-resolutions',str(declaration_file),'--out',str(product/'resolved')])
            self.assertEqual(code,0,result.get('diagnostics'))
            report=Path(result['data']['report']);full=json.loads(report.read_text())
            self.assertEqual(full['status'],'declaration_only')
            self.assertEqual(full['consumerResolutions'],declaration)
            self.assertTrue(full['consumerResolutionsSha256'])
            self.assertEqual(result['verification']['native'],'not_run')
            self.assertEqual(hashlib.sha256(report.read_bytes()).hexdigest(),result['artifacts'][0]['sha256'])
            self.assertEqual(json.loads(declaration_file.read_text()),declaration)
            declaration['schemaVersion']=True
            write_json(declaration_file,declaration)
            code,rejected=invoke(['--consumer-resolutions',str(declaration_file),'--out',str(product/'invalid-version')])
            self.assertEqual(code,3)
            self.assertEqual(rejected['diagnostics'][0]['code'],'CONSUMER_RESOLUTION_SCHEMA')
