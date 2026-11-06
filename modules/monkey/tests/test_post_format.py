import contextlib,io,json,tempfile,unittest
from pathlib import Path
from fixtures import fixture
from monkey.cli import main
from monkey.package import convert_package
from monkey.io import read,load,sha
from monkey.layout.verify import scan

class RetiredFormatTests(unittest.TestCase):
    def test_grea_alias_produces_the_same_canonical_projects_as_none(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();source=fixture(root/'source').parent
            none=convert_package(source,'both',root/'none');grea=convert_package(source,'both',root/'grea',format_profile='grea')
            self.assertEqual(none['format']['status'],'not_requested');self.assertEqual(grea['format']['status'],'retired')
            self.assertTrue(any(d['code']=='FORMAT_PROFILE_RETIRED' for d in grea['diagnostics']))
            self.assertFalse(any(d['code']=='FORMAT_PROFILE_RETIRED' for d in none['diagnostics']))
            for name in ['UnityProject','CocosProject']:
                plain=load(read(root/'none'/name/'manifest.json'));alias=load(read(root/'grea'/name/'manifest.json'))
                self.assertEqual(plain['projectLayout'],'monkey-project/2.0.0');self.assertEqual(alias['projectLayout'],plain['projectLayout'])
                # Analysis receipts embed each run's absolute source/output roots; everything else is byte-identical.
                content=lambda m:{f['path']:f['sha256'] for f in m['files'] if not f['path'].startswith('Analysis/')}
                self.assertEqual({f['path'] for f in plain['files']},{f['path'] for f in alias['files']});self.assertEqual(content(plain),content(alias))
                self.assertEqual(scan([f['path'] for f in plain['files']]),[])
            for folder in ['Unformatted','Formatting']:self.assertFalse((root/'grea'/folder).exists())

    def test_json_payload_bytes_are_relocated_not_rewritten(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();source=fixture(root/'source').parent
            convert_package(source,'both',root/'out')
            ir=load(read(root/'out/Structured/normalize/ir.json'))
            for asset in [a for a in ir['assets'] if a['kind']=='cc.JsonAsset']:
                raw=read(root/'out/Structured/normalize'/asset['path'])
                plan=load(read(root/'out/UnityProject/Assets/Game/Editor/Conversion/import-plan.json'))
                target=next(a['path'] for a in plan['assets'] if a['id']==asset['sourceId'])
                self.assertEqual(sha(read(root/'out/UnityProject'/target)),sha(raw))

    def test_format_project_command_is_an_explicit_refusal(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();out=io.StringIO()
            with contextlib.redirect_stderr(out):code=main(['format-project','--project',str(root),'--preview','--out',str(root/'x')])
            self.assertNotEqual(code,0);self.assertEqual(json.loads(out.getvalue())['code'],'FORMAT_RETIRED');self.assertFalse((root/'x').exists())

if __name__=='__main__':unittest.main()
