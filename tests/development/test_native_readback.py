import copy
import tempfile
import unittest
import base64
import json
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from grea.development.errors import BeaverError
from grea.development.native_readback import validate,run_collector
from grea.development.cli import parser


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
        args=parser().parse_args(['structure','inspect','--project','Product/Unity','--product-root','Product','--profile','Product/grea-project.json','--out','Product/Analysis/audit'])
        self.assertEqual(args.product_root,'Product')

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
            with patch('grea.development.native_readback.subprocess.run',side_effect=provider):
                with self.assertRaises(BeaverError) as error:
                    run_collector(project,{'assets':['Assets/Input.asset']},output,editor,'BeaverReadback.cs','BeaverReadback.Run','readback.json')
            self.assertEqual(error.exception.code,'READBACK_PROJECT_MODIFIED')
            guard=json.loads((output/'read-only-guard.json').read_text())
            self.assertFalse(guard['sourceUnchanged']);self.assertIn('Assets/Input.asset',guard['unplannedProjectChanges'])
            self.assertTrue(guard['helperCleaned'])
            self.assertEqual(asset.read_bytes(),b'unexpected mutation')


    def test_collector_report_budget_is_separate_from_ordinary_input_budget(self):
        from grea.development.io import read
        with tempfile.TemporaryDirectory(dir='/private/tmp') as temp:
            root=Path(temp).resolve();project=root/'Project'
            for name in ('Assets','Packages','ProjectSettings'):(project/name).mkdir(parents=True)
            asset=project/'Assets/Input.asset';asset.write_bytes(b'original');Path(str(asset)+'.meta').write_bytes(b'meta')
            editor=root/'Unity';editor.write_text('fake editor');editor.chmod(0o755)
            output=root/'Evidence'
            def provider(*args,**kwargs):
                jobpath=Path(base64.b64decode(kwargs['env']['BEAVER_NATIVE_JOB_BASE64']).decode())
                job=json.loads(jobpath.read_text());report=Path(job['stage'],'readback.json')
                report.write_text(json.dumps({'assets':[],'diagnostic':'x'*(33*1024*1024)}))
                return SimpleNamespace(returncode=0)
            with patch('grea.development.native_readback.subprocess.run',side_effect=provider):
                result=run_collector(project,{'assets':['Assets/Input.asset']},output,editor,'BeaverReadback.cs','BeaverReadback.Run','readback.json')
            self.assertTrue(result['sourceUnchanged']);self.assertTrue(result['helperCleaned'])
            self.assertEqual(len(result['diagnostic']),33*1024*1024)
            with self.assertRaises(BeaverError):read(output/'native/readback.json')

    def test_oversized_native_report_is_retained_but_rejected_after_helper_cleanup(self):
        from grea.development.output_limits import MANIFEST_BYTES
        with tempfile.TemporaryDirectory(dir='/private/tmp') as temp:
            root=Path(temp).resolve();project=root/'Project'
            for name in ('Assets','Packages','ProjectSettings'):(project/name).mkdir(parents=True)
            editor=root/'Unity';editor.write_text('fake editor');editor.chmod(0o755)
            output=root/'Evidence'
            def provider(*args,**kwargs):
                jobpath=Path(base64.b64decode(kwargs['env']['BEAVER_NATIVE_JOB_BASE64']).decode())
                job=json.loads(jobpath.read_text())
                with Path(job['stage'],'readback.json').open('wb') as stream:stream.truncate(MANIFEST_BYTES+1)
                return SimpleNamespace(returncode=0)
            with patch('grea.development.native_readback.subprocess.run',side_effect=provider):
                with self.assertRaises(BeaverError) as error:
                    run_collector(project,{'assets':[]},output,editor,'BeaverReadback.cs','BeaverReadback.Run','readback.json')
            self.assertEqual(error.exception.code,'BYTE_BUDGET')
            self.assertTrue((output/'native/readback.json').exists())
            guard=json.loads((output/'read-only-guard.json').read_text())
            self.assertTrue(guard['sourceUnchanged']);self.assertTrue(guard['helperCleaned'])


class PersistentOwnerSelectorTests(unittest.TestCase):
    def request(self):
        return dict(schemaVersion=1,assets=['Assets/Panel.prefab'],queries=[dict(asset='Assets/Panel.prefab',nodePath='Mid/Effect',componentType='Fixture.Probe',propertyPath='marker',ownerIdentity=dict(guid='A'*32,localId=-123))])

    def test_owner_identity_accepts_exact_signed_id_without_rewriting_request(self):
        spec=self.request();self.assertEqual(validate(spec),spec)
        self.assertNotIn('hasOwnerIdentity',spec['queries'][0])

    def test_malformed_or_internal_selector_fields_are_rejected(self):
        for value in (None,{},dict(guid='a'*32),dict(guid='bad',localId=1),dict(guid='a'*32,localId=0),dict(guid='a'*32,localId=True),dict(guid='a'*32,localId=2**63),dict(guid='a'*32,localId=-(2**63)-1),dict(guid='a'*32,localId=1,extra=True)):
            with self.subTest(value=value),self.assertRaises(BeaverError):
                spec=self.request();spec['queries'][0]['ownerIdentity']=value;validate(spec)
        spec=self.request();spec['queries'][0]['hasOwnerIdentity']=False
        with self.assertRaises(BeaverError):validate(spec)

    def test_runtime_selector_presence_is_derived_for_both_old_and_new_queries(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as temp:
            root=Path(temp).resolve();project=root/'Project'
            for name in ('Assets','Packages','ProjectSettings'):(project/name).mkdir(parents=True)
            asset=project/'Assets/Panel.prefab';asset.write_bytes(b'unit fixture');Path(str(asset)+'.meta').write_bytes(b'meta')
            editor=root/'Unity';editor.write_text('fake');editor.chmod(0o755)
            request=self.request();request['queries'].append({k:v for k,v in request['queries'][0].items() if k!='ownerIdentity'})
            jobs=[]
            def provider(*args,**kwargs):
                jobpath=Path(base64.b64decode(kwargs['env']['BEAVER_NATIVE_JOB_BASE64']).decode());job=json.loads(jobpath.read_text());jobs.append(job)
                Path(job['stage'],'readback.json').write_text(json.dumps(dict(assets=[dict(path='Assets/Panel.prefab')])))
                return SimpleNamespace(returncode=0)
            with patch('grea.development.native_readback.subprocess.run',side_effect=provider):run_collector(project,request,root/'Evidence',editor,'BeaverReadback.cs','BeaverReadback.Run','readback.json')
            self.assertTrue(jobs[0]['queries'][0]['hasOwnerIdentity']);self.assertFalse(jobs[0]['queries'][1]['hasOwnerIdentity'])
            self.assertNotIn('hasOwnerIdentity',request['queries'][0])

    def report(self,spec,local_id=-123,status='observed'):
        query=spec['queries'][0]
        field=dict(asset=query['asset'],nodePath=query['nodePath'],componentType=query['componentType'],requestedPath=query['propertyPath'],propertyPath=query['propertyPath'],status=status,owner=dict(guid='a'*32,localId=local_id,type='Fixture.Probe',state='persistent'))
        return dict(contract='beaver-native-readback/1',schemaVersion=1,errors=[],status='observed' if status=='observed' else 'partial',assets=[dict(path=query['asset'])],fields=[field])

    def test_observed_owner_mismatch_is_never_silently_accepted(self):
        from grea.development.native_readback import inspect
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();spec=self.request();path=root/'spec.json';path.write_text(json.dumps(spec))
            with patch('grea.development.native_readback.run_collector',return_value=self.report(spec,1)),self.assertRaises(BeaverError) as error:inspect(root,path,root/'out',root/'Editor')
            self.assertEqual(error.exception.code,'READBACK_OWNER_IDENTITY')

    def test_exact_observed_owner_and_unknown_negative_keep_their_states(self):
        from grea.development.native_readback import inspect
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();spec=self.request();path=root/'spec.json';path.write_text(json.dumps(spec))
            for status in ('observed','unknown'):
                with self.subTest(status=status),patch('grea.development.native_readback.run_collector',return_value=self.report(spec,-123,status)):
                    report=inspect(root,path,root/'out',root/'Editor');self.assertEqual(report['fields'][0]['status'],status)


if __name__=='__main__':unittest.main()
