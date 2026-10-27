"""Only the new forwarding boundary; no Editor, Player or provider regression rerun."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema import Draft202012Validator
from grea.integrations import beaver_operations as ops
from grea.beaver_contracts import documents


def request(name='payload.verify',**options):
    return dict(schema_version=1,operation=name,options=options,timeout_seconds=60)


def fixture_path(name):
    return str((Path(tempfile.gettempdir()) / 'grea-fixtures' / name).resolve())


class BeaverOperationTests(unittest.TestCase):
    def test_unknown_options_and_unbounded_effects_rejected(self):
        root,manifest=fixture_path('project'),fixture_path('manifest.json')
        bad=[request('shell',command='echo unsafe'),request(root=root,manifest=manifest,out=fixture_path('override')),
             request(root='relative',manifest=manifest),request(root=root,manifest=manifest,**{'allow-unlisted':'true'}),
             request('adoption.apply',plan=fixture_path('plan.json'),**{'expected-plan':'bad','editor-path':fixture_path('editor'),'timeout':10}),
             request('player.run',manifest=manifest,**{'expected-manifest':'a'*64,'duration':60}),
             request('image.compress',input=root,apply=True)]
        for value in bad:
            with self.subTest(value=value),self.assertRaises(ValueError):ops.validate(value)

    def test_named_argv_and_generated_schema_share_contract(self):
        value=request('adoption.apply',plan=fixture_path('plan.json'),**{'expected-plan':'a'*64,'editor-path':fixture_path('editor'),'timeout':20})
        receipt=fixture_path('receipt')
        argv=ops.argv_for(value,receipt)
        self.assertEqual(argv[:2],['adopt','apply']);self.assertEqual(argv[-2:],['--out',str(Path(receipt)/'provider-output')])
        self.assertEqual(argv[argv.index('--expected-plan')+1],'a'*64)
        schema=documents()['beaver-operation.schema.json'];Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)
        with self.assertRaises(ValueError):ops.validate(dict(value,options=dict(value['options'],**{'execute-shell':'bad'})))

    def test_command_snapshot_is_receipt_local_and_override_restored(self):
        original=fixture_path('original-config')
        command=fixture_path('pinned-beaver')
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'GREA_PROVIDERS':original}):
            with ops.bound_command({'command':[command]},t):
                path=Path(os.environ['GREA_PROVIDERS']);self.assertEqual(path.parent,Path(t))
                cfg=json.loads(path.read_text());self.assertEqual(cfg['providers']['beaver']['command'],[command])
                self.assertEqual(cfg['providers']['beaver']['probe'],[command,'capabilities'])
            self.assertEqual(os.environ['GREA_PROVIDERS'],original)

    def test_request_rewrite_during_read_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/'request.json';p.write_text(json.dumps(request(root=fixture_path('project'),manifest=fixture_path('manifest.json'))))
            original=ops.read_json
            def rewrite(path):
                value=original(path);p.write_text(json.dumps(request(root=fixture_path('different'),manifest=fixture_path('manifest.json'))));return value
            with patch.object(ops,'read_json',side_effect=rewrite),patch('grea.runner.execute')as run:
                with self.assertRaises(ValueError):ops.invoke(root/'lock',p,root/'receipt')
                run.assert_not_called();self.assertFalse((root/'receipt').exists())

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'request';p.write_text('{"operation":"a","operation":"b"}')
            with self.assertRaises(ValueError):ops.read_json(p)

    def test_unity_apply_uses_capability_of_the_frozen_plan(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'plan.json';p.write_text(json.dumps(dict(contract='beaver-unity/1',spec={'operation':'build.macos'})))
            self.assertEqual(ops.required_capability(request('unity.apply',plan=str(p))),'unity.build.macos')

    def run_fixture(self,status='ok',code=0,declared=True,complete=True,drift=False):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();project=root/'project';project.mkdir();manifest=root/'manifest.json';manifest.write_text('{}')
            req=root/'request.json';req.write_text(json.dumps(request(root=str(project),manifest=str(manifest))))
            cfg=dict(identity_root=fixture_path('package'),package_files={'file':'hash'},command=[fixture_path('beaver')],command_files={'cmd':'hash'},version='0.1.0')
            lock=root/'lock.json';lock.write_text(json.dumps(cfg))
            producer=dict(name='beaver',version='0.1.0',implementationSha256='b'*64)
            cap=dict(contract='beaver-result/1',producer=producer,data={'capabilities':[dict(id='payload.verify',state='implemented')]if declared else []})
            def checked(output,**kwargs):
                p=Path(output)/'probe';p.mkdir(parents=True);(p/'run.json').write_text(json.dumps({'parsed_stdout':cap}));return dict(ready=True)
            actual=dict(contract='beaver-result/1',producer=producer,status=status,verification={'native':'not_run'},diagnostics=[{'code':'selected'}])
            with patch('grea.integrations.monkey.local.readiness',return_value={'ready':True}),patch.object(ops.beaver,'check',side_effect=checked),patch.object(ops.beaver,'package_identity',return_value={'different':'hash'}if drift else cfg['package_files']),patch.object(ops.beaver,'command_identity',return_value=cfg['command_files']),patch('grea.runner.execute',return_value=({'parsed_stdout':actual,'capture_complete':complete,'exit_code':code},[],None))as run:
                result=ops.invoke(lock,req,root/'receipt');return result,run.call_count

    def test_semantic_status_and_diagnostics_not_upgraded(self):
        for status,code in [('ok',0),('partial',1),('blocked',3),('failed',2),('not_run',3)]:
            with self.subTest(status=status):
                value,count=self.run_fixture(status,code);self.assertEqual(count,1);self.assertEqual(value['status'],status)
                self.assertEqual(value['provider_result']['diagnostics'],[{'code':'selected'}])

    def test_undeclared_capability_never_invoked(self):
        value,count=self.run_fixture(declared=False);self.assertEqual(count,0);self.assertFalse(value['executed']);self.assertEqual(value['status'],'needs_action')

    def test_truncation_status_mismatch_and_drift_do_not_pass(self):
        for kwargs in [{'complete':False},{'status':'ok','code':1},{'drift':True}]:
            with self.subTest(kwargs=kwargs):self.assertEqual(self.run_fixture(**kwargs)[0]['status'],'needs_action')

if __name__=='__main__':unittest.main()
