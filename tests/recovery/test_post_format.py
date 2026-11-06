import contextlib,io,json,tempfile,unittest
from pathlib import Path
from .fixtures import fixture
from grea.recovery.cli import main
from grea.recovery.package import convert_package
from grea.recovery.io import read,load,sha
from grea.recovery.layout.verify import scan

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
                self.assertEqual(plain['projectLayout'],'grea-project-layout/2.1.0');self.assertEqual(alias['projectLayout'],plain['projectLayout'])
                # Absolute output roots change the inspected source receipt hash. Confirm each
                # plan pins its own real manifest and compare all other project content.
                plans = {"UnityProject":"Assets/Game/Editor/Conversion/import-plan.json",
                         "CocosProject":"extensions/monkey-import/import-plan.json"}
                def content(manifest, output):
                    import hashlib
                    files = {row["path"]:row["sha256"] for row in manifest["files"] if not row["path"].startswith("Analysis/")}
                    plan = load(read(output/name/plans[name]))
                    frozen = output/"Structured/inspect/source-manifest.json"
                    self.assertEqual(plan.pop("sourceManifestSha256"), hashlib.sha256(frozen.read_bytes()).hexdigest())
                    files[plans[name]] = plan
                    return files
                self.assertEqual({f['path'] for f in plain['files']},{f['path'] for f in alias['files']})
                self.assertEqual(content(plain,root/'none'),content(alias,root/'grea'))
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

if __name__=='__main__':unittest.main()
