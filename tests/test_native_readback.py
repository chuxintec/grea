import copy
import tempfile
import unittest
import base64
import json
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from beaver.errors import BeaverError
from beaver.native_readback import validate,run_collector
from beaver.cli import parser


class ReadbackTests(unittest.TestCase):
    def request(self):
        return {'schemaVersion':1,'assets':['Assets/Game/Panel.prefab'],
                'queries':[{'asset':'Assets/Game/Panel.prefab','nodePath':'','componentType':'Fixture.Probe','propertyPath':'nested.optional'}],
                'aliases':[{'name':'caption','propertyPath':'nested.caption'}]}

    def test_explicit_nested_and_empty_node(self):
        self.assertEqual(validate(self.request())['queries'][0]['nodePath'],'')

    def test_duplicate_alias_is_not_first_match(self):
        r=self.request();r['aliases']*=2
        with self.assertRaises(BeaverError):validate(r)

    def test_traversal_and_duplicate_selection(self):
        for assets in (['Assets/../a.prefab'],['Assets//a.prefab'],['Assets/a.prefab']*2):
            r=self.request();r['assets']=assets
            with self.assertRaises(BeaverError):validate(r)

    def test_capture_has_one_explicit_camera(self):
        r=self.request();r['capture']={'asset':r['assets'][0],'width':750,'height':1334,'cameraPath':'Camera'}
        self.assertEqual(validate(r)['capture']['width'],750)
        r['capture']['camera']={}
        with self.assertRaises(BeaverError):validate(r)

    def test_capture_memory_budget(self):
        r=self.request();r['capture']={'asset':r['assets'][0],'width':4096,'height':4096,'cameraPath':'Camera'}
        with self.assertRaises(BeaverError):validate(r)

    def test_invalid_float_camera(self):
        r=self.request();r['capture']={'asset':r['assets'][0],'width':64,'height':64,'camera':{'position':[0,0,-10],'euler':[0,0,0],'orthographic':True,'size':float('nan'),'background':[0,0,0,0]}}
        with self.assertRaises(BeaverError):validate(r)

    def test_cli_native_and_plan_flags(self):
        args=parser().parse_args(['native','readback','--project','p','--spec','s','--out','o','--editor-path','e'])
        self.assertEqual(args.action,'readback')
        args=parser().parse_args(['structure','plan','--audit','a','--mappings','m','--out','o'])
        self.assertEqual(args.action,'plan')

    def test_read_only_guard_detects_provider_mutation_and_preserves_receipt(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as temp:
            root=Path(temp).resolve();project=root/'Project'
            for name in ('Assets','Packages','ProjectSettings'):(project/name).mkdir(parents=True)
            asset=project/'Assets/Input.asset';asset.write_bytes(b'original');Path(str(asset)+'.meta').write_bytes(b'meta')
            editor=root/'Unity';editor.write_text('fake editor');editor.chmod(0o755)
            output=root/'Evidence'
            def provider(*args,**kwargs):
                jobpath=Path(base64.b64decode(kwargs['env']['BEAVER_NATIVE_JOB_BASE64']).decode())
                job=json.loads(jobpath.read_text());Path(job['stage'],'readback.json').write_text(json.dumps({'assets':[]}))
                asset.write_bytes(b'unexpected mutation')
                return SimpleNamespace(returncode=0)
            with patch('beaver.native_readback.subprocess.run',side_effect=provider):
                with self.assertRaises(BeaverError) as error:
                    run_collector(project,{'assets':['Assets/Input.asset']},output,editor,'BeaverReadback.cs','BeaverReadback.Run','readback.json')
            self.assertEqual(error.exception.code,'READBACK_PROJECT_MODIFIED')
            guard=json.loads((output/'read-only-guard.json').read_text())
            self.assertFalse(guard['sourceUnchanged']);self.assertIn('Assets/Input.asset',guard['unplannedProjectChanges'])
            self.assertTrue(guard['helperCleaned'])
            self.assertEqual(asset.read_bytes(),b'unexpected mutation')


if __name__=='__main__':unittest.main()
