import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from monkey.io import sha,write_json
from monkey.unity_bulk_prepare import prepare
from monkey.unity_parse_limits import reader_fingerprint
from monkey.sources.compiled import ParseError


class BulkPreparationTests(unittest.TestCase):
    def fixture(self,root):
        inspection=root/'inspection';(inspection/'BatchInspection').mkdir(parents=True);(inspection/'SourceInspection').mkdir();source=root/'source.bundle';source.write_bytes(b'fixed-source');typed=inspection/'SourceInspection/typed-objects.json';typed.write_text('{}');(inspection/'all-inputs.json').write_text('{}')
        worker=Path(__file__).resolve().parents[1]/'src/monkey/sources/unity_worker.py'
        write_json(inspection/'BatchInspection/execution.json',dict(status='inspected',workerSha256=reader_fingerprint()))
        write_json(inspection/'BatchInspection/batch.json',dict(files=[dict(path=str(source),receipt=dict(typedObjectsSha256=sha(typed.read_bytes()),source=dict(sha256=sha(source.read_bytes())),sourceUnchanged=True,summary=dict(externalTextureTokens=1)))]))
        cache=root/'cache.txt';cache.write_bytes(b'cached');manifest=root/'textures.json';write_json(manifest,dict(schemaVersion=1,files=[dict(path=str(cache),logicalPath='Assets/Textures/astc/32/known.hash.txt',bytes=6,sha256=sha(b'cached'))]))
        capture=root/'capture.json';write_json(capture,dict(requestedKeys=2,capturedKeys=1,poolEntries=1,failures=[dict(logicalPath='Assets/Textures/astc/32/missing.hash.txt',status='failed',reason='HTTPError: HTTP Error 404: Not Found')]))
        write_json(root/'capture-job.json',dict(inspectionManifestSha256=sha(b'{}')))
        return dict(inspection=inspection,texture_cache=manifest,capture=capture,provider_python='/usr/bin/python3',output=root/'out',budget=30)

    def test_only_terminal_exact_404_from_same_inspection_is_quarantinable(self):
        for change in ['pending','server-error','wrong-inspection','wrong-pool']:
            with self.subTest(change=change),tempfile.TemporaryDirectory()as temp:
                root=Path(temp).resolve();opts=self.fixture(root);cap=json.loads(opts['capture'].read_text())
                if change=='pending':cap['requestedKeys']=3
                elif change=='server-error':cap['failures'][0]['reason']='HTTPError: HTTP Error 500: Internal Server Error'
                elif change=='wrong-pool':cap['poolEntries']=2
                else:write_json(root/'capture-job.json',dict(inspectionManifestSha256='wrong'))
                write_json(opts['capture'],cap)
                with patch('subprocess.Popen',side_effect=AssertionError('invalid input must not launch')),self.assertRaises(ParseError):prepare(**opts)
                self.assertFalse(opts['output'].exists())

    def test_changed_typed_or_original_source_refuses_before_preparation(self):
        for rel in ['source.bundle','inspection/SourceInspection/typed-objects.json']:
            with self.subTest(rel=rel),tempfile.TemporaryDirectory()as temp:
                root=Path(temp).resolve();opts=self.fixture(root);(root/rel).write_text('changed')
                with patch('subprocess.Popen',side_effect=AssertionError('no reparse fallback')),self.assertRaises(ParseError):prepare(**opts)
                self.assertFalse(opts['output'].exists())

    def test_stage_budget_is_bounded_before_any_output(self):
        with tempfile.TemporaryDirectory()as temp:
            opts=self.fixture(Path(temp).resolve())
            with self.assertRaises(ParseError):prepare(**dict(opts,budget=3600))
            self.assertFalse(opts['output'].exists())


if __name__=='__main__':unittest.main()
