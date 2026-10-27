"""Only GREA's new version/argument/identity boundary; never launches an engine."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema import Draft202012Validator, ValidationError
from grea.common import GreaError
from grea.integrations import beaver, beaver_operations as ops
from grea.beaver_contracts import documents


def request(operation='references', **options):
    return dict(schema_version=1, operation=operation, options=options, timeout_seconds=30)


def fixture_path(name):
    return str((Path(tempfile.gettempdir()) / 'grea-fixtures' / name).resolve())


class BeaverV02Tests(unittest.TestCase):
    def test_explicit_v02_contracts_and_future_versions(self):
        cap=dict(version='0.2.0', **beaver.V02_CONTRACTS,
                 capabilities=[dict(id=name,state='implemented') for name in sorted(beaver.V02_OPERATIONS)])
        beaver.validate_capabilities(cap)
        for bad in (dict(cap,version='0.3.0.dev1'),dict(cap,batchOperationContract='beaver-batch/3'),
                    dict(cap,capabilities=[]),dict(cap,capabilities=cap['capabilities']*2)):
            with self.subTest(bad=bad),self.assertRaises(ValueError):beaver.validate_capabilities(bad)
        beaver.validate_capabilities({'version':'0.1.0'})

    def test_new_operations_and_large_artifact_flag_cannot_leak_to_v01(self):
        for value in (request(project=fixture_path('project')),request('payload.verify',root=fixture_path('root'),manifest=fixture_path('manifest'),**{'unity-artifact':True})):
            with self.subTest(value=value):
                ops.validate_provider_version(value,'0.2.0')
                with self.assertRaises(ValueError):ops.validate_provider_version(value,'0.1.0')
        ops.validate_provider_version(request('payload.verify',root=fixture_path('root'),manifest=fixture_path('manifest')),'0.1.0')

    def test_async_duration_is_separate_from_call_budget_and_dimensions_are_paired(self):
        value=request('debug.start',manifest=fixture_path('manifest'),expected='a'*64,duration=3600,width=8192,height=8192)
        ops.validate(value);Draft202012Validator(documents()['beaver-operation.schema.json']).validate(value)
        for change in ({'height':None},{'duration':3601},{'width':63}):
            options=dict(value['options'],**change)
            if change.get('height','present') is None:options.pop('height')
            with self.subTest(change=change),self.assertRaises(ValueError):ops.validate(dict(value,options=options))
        invalid=dict(value,options={k:v for k,v in value['options'].items()if k!='height'})
        with self.assertRaises(ValidationError):Draft202012Validator(documents()['beaver-operation.schema.json']).validate(invalid)

    def test_tail_limits_are_not_treated_as_process_seconds(self):
        ops.validate(request('debug.tail',session=fixture_path('session'),lines=500))
        for count in (0,501,True):
            with self.subTest(count=count),self.assertRaises(ValueError):ops.validate(request('debug.tail',session=fixture_path('session'),lines=count))
        with self.assertRaises(ValueError):ops.validate(dict(request('batch.apply',plan=fixture_path('plan'),**{'expected-plan':'a'*64,'editor-path':fixture_path('editor'),'timeout':30}),timeout_seconds=30))

    def test_batch_apply_rejects_legacy_plan_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'plan.json'
            for contract,accepted in [('beaver-batch/2',True),('beaver-unity/1',False)]:
                path.write_text(json.dumps(dict(contract=contract)))
                value=request('batch.apply',plan=str(path))
                if accepted:self.assertEqual(ops.required_capability(value),'batch.apply')
                else:
                    with self.assertRaises(ValueError):ops.required_capability(value)

    def invoke_fixture(self, status='partial', code=1, version='0.2.0', producer_drift=False, lock_drift=False):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project=root/'project';project.mkdir()
            req=root/'request.json';req.write_text(json.dumps(request(project=str(project))))
            cfg=dict(identity_root=fixture_path('package'),package_files={'file':'hash'},command=[fixture_path('beaver')],command_files={'cmd':'hash'},version=version)
            lock=root/'lock.json';lock.write_text(json.dumps(cfg))
            producer=dict(name='beaver',version=version,implementationSha256='b'*64)
            probe=dict(producer=producer,data={'capabilities':[dict(id='references',state='implemented')]})
            def checked(output, **kwargs):
                path=Path(output)/'probe';path.mkdir(parents=True);(path/'run.json').write_text(json.dumps({'parsed_stdout':probe}))
                if lock_drift:lock.write_text(json.dumps(dict(cfg,command=[fixture_path('changed-beaver')])))
                return {'ready':True}
            actual=dict(contract='beaver-result/1',producer=dict(producer,implementationSha256='c'*64)if producer_drift else producer,
                        status=status,verification={'native':'not_run'},diagnostics=[{'code':'UNKNOWN_DYNAMIC_KEYS'}])
            error=GreaError('TOOL_FAILED','fixture exit') if code not in (0,1) else None
            with patch('grea.integrations.monkey.local.readiness',return_value={'ready':True}),patch.object(beaver,'check',side_effect=checked),patch.object(beaver,'package_identity',return_value=cfg['package_files']),patch.object(beaver,'command_identity',return_value=cfg['command_files']),patch('grea.runner.execute',return_value=({'parsed_stdout':actual,'capture_complete':True,'exit_code':code},[],error))as run:
                result=ops.invoke(lock,req,root/'receipt');return result,run.call_count

    def test_v02_status_and_nonzero_diagnostics_are_preserved(self):
        for status,code in [('ok',0),('partial',1),('blocked',3),('failed',2),('not_run',3)]:
            with self.subTest(status=status):
                result,count=self.invoke_fixture(status,code)
                self.assertEqual(count,1);self.assertEqual(result['status'],status)
                self.assertEqual(result['provider_result']['diagnostics'],[{'code':'UNKNOWN_DYNAMIC_KEYS'}])
                self.assertEqual(result['native'],'not_run');self.assertEqual(result['gameplay'],'not_run')
                if code in (2,3):self.assertEqual(result['transport_error']['code'],'TOOL_FAILED')

    def test_old_provider_cannot_execute_new_operation_even_if_it_declares_it(self):
        result,count=self.invoke_fixture(version='0.1.0')
        self.assertEqual(count,0);self.assertFalse(result['executed']);self.assertEqual(result['status'],'needs_action')

    def test_producer_drift_or_inconsistent_exit_cannot_pass(self):
        for options in ({'producer_drift':True},{'status':'blocked','code':2}):
            with self.subTest(options=options):
                result,count=self.invoke_fixture(**options)
                self.assertEqual(count,1);self.assertEqual(result['status'],'needs_action')

    def test_mutated_lock_is_rejected_before_execution(self):
        result,count=self.invoke_fixture(lock_drift=True)
        self.assertEqual(count,0);self.assertFalse(result['executed']);self.assertIn('lock changed',result['diagnostic'])


if __name__=='__main__':unittest.main()
