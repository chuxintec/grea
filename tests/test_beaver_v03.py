"""Fixed candidate07 compatibility, not an engine/server or upstream test rerun."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema import Draft202012Validator
from grea.common import GreaError
from grea.integrations import beaver, beaver_operations as ops
from grea.beaver_contracts import BEAVER_RESULT_SCHEMA, documents, validate_result


def request(operation='workspace.inspect',**options):
    return dict(schema_version=1,operation=operation,options=options,timeout_seconds=30)


def fixture_path(name):
    return str((Path(tempfile.gettempdir()) / 'grea-fixtures' / name).resolve())


def result(status='ok',version=beaver.V03_VERSION):
    data=dict(schemaVersion=1,contract='beaver-result/1',operationId='fixture',
              producer=dict(name='beaver',version=version,implementationSha256=beaver.V03_CANDIDATES[version]['implementation_sha256']),
              status=status,actualChanges=[],artifacts=[],diagnostics=[{'code':'fixture'}],limitations=[],
              verification=dict(native='not_run',player='not_run',visual='not_run',business='not_run'))
    if status in ('ok','partial'):data['data']={'status':status}
    return data


class BeaverV03Tests(unittest.TestCase):
    def capabilities(self):
        return dict(version=beaver.V03_VERSION,producer_implementation_sha256=beaver.V03_IMPLEMENTATION,
                    **beaver.V03_CONTRACTS,capabilities=[dict(id=name,state='implemented')for name in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS)])

    def test_fixed_candidate_contracts_and_identity_not_a_generic_dev_version(self):
        cap=self.capabilities();beaver.validate_capabilities(cap)
        for update in ({'producer_implementation_sha256':'e799831e07798347fcbb4e9c0338877b1e7c33f652e6f41c5f3295a79bd1ea1e'},
                       {'version':'0.3.0'},{'productionOperationContract':'beaver-production/2'},
                       {'projectProfileContract':'beaver-project/2'},{'capabilities':cap['capabilities']*2}):
            with self.subTest(update=update),self.assertRaises(ValueError):beaver.validate_capabilities(dict(cap,**update))

    def test_finite_route_version_matrix_and_explicit_unsupported_operations(self):
        for version in ('0.2.0',*beaver.V03_CANDIDATES):ops.validate_provider_version(request('references',project=fixture_path('project')),version)
        value=request(project=fixture_path('project'));ops.validate_provider_version(value,beaver.V03_VERSION)
        for version in ('0.1.0','0.2.0','0.3.1','0.3.0.dev2'):
            with self.subTest(version=version),self.assertRaises(ValueError):ops.validate_provider_version(value,version)
        for name in ops.UNSUPPORTED_V03:
            with self.subTest(name=name),self.assertRaises(ValueError):ops.validate(request(name))

    def test_named_groups_are_explicit_not_split_or_guessed(self):
        self.assertEqual(ops.required_capability(request()),'workspace.plan/apply/inspect/rebind')
        self.assertEqual(ops.required_capability(request('server.module-plan')),'server.generate/module-generate/module-plan/protocol-diff/migration-plan')
        self.assertEqual(ops.required_capability(request('csharp.rename-sequence')),'csharp.inspect/rename/rename-sequence')
        schema=documents()['beaver-operation.schema.json'];Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(request('workspace.rebind',project=fixture_path('project'),profile=fixture_path('profile'),**{'expected-profile':'a'*64,'accept-authority-change':True}))

    def test_new_request_parameters_reject_untyped_authority_and_output_override(self):
        for value in [request('workspace.rebind',project=fixture_path('project'),profile=fixture_path('profile'),**{'expected-profile':'a'*64,'accept-authority-change':'yes'}),
                      request('workspace.rebind',project=fixture_path('project'),profile=fixture_path('profile'),**{'expected-profile':'short'}),
                      request('production.plan',project=fixture_path('project'),spec='relative'),
                      request('csharp.rename-sequence',project=fixture_path('project'),spec=fixture_path('spec'),out=fixture_path('escape')),
                      request('resource.image-produce',input=fixture_path('input'),policy=fixture_path('policy'),**{'expected-source':'bad'}),
                      request('server.migration-apply',project=fixture_path('project')),request(['shell'])]:
            with self.subTest(value=value),self.assertRaises(ValueError):ops.validate(value)

    def test_workspace_and_production_apply_plan_contracts_do_not_accept_old_transactions(self):
        with tempfile.TemporaryDirectory()as temp:
            p=Path(temp)/'plan.json'
            for op,contract,schema in [('workspace.apply','beaver-project-setup/1',None),('production.apply','beaver-production/3',3)]:
                good={'contract':contract}
                if schema:good['schemaVersion']=schema
                p.write_text(json.dumps(good));self.assertIn('/',ops.required_capability(request(op,plan=str(p))))
                p.write_text(json.dumps(dict(contract='beaver-batch/2',schemaVersion=2)))
                with self.assertRaises(ValueError):ops.required_capability(request(op,plan=str(p)))

    def test_result_schema_checks_envelope_without_rewriting_provider_engineering_data(self):
        Draft202012Validator.check_schema(BEAVER_RESULT_SCHEMA)
        for status in ('ok','partial','blocked','failed','not_run'):validate_result(result(status))
        value=result();value['data']={'provider_owned':{'unknown':['retained']}};value['verification']['native']={'actual_readback':True};validate_result(value)
        for field,bad in [('diagnostics','hidden'),('actualChanges',[1]),('verification',{'native':'not_run'}),('producer',{'name':'beaver'}),('data',[]),('status','verified')]:
            with self.subTest(field=field),self.assertRaises(ValueError):validate_result(dict(result(),**{field:bad}))

    def invoke_fixture(self,status='ok',code=0,declared=None,mutate=None,version=None,provider_version=beaver.V03_VERSION):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();project=root/'project';project.mkdir()
            req=root/'request.json';req.write_text(json.dumps(request(project=str(project))))
            cfg=dict(identity_root=fixture_path('package'),package_files={'file':'hash'},command=[fixture_path('beaver')],command_files={'cmd':'hash'},version=version or provider_version)
            lock=root/'lock.json';lock.write_text(json.dumps(cfg));probe=result(version=provider_version)
            probe['data']={'capabilities':[dict(id=declared or 'workspace.plan/apply/inspect/rebind',state='implemented')]}
            def checked(output,**kwargs):
                path=Path(output)/'probe';path.mkdir(parents=True);(path/'run.json').write_text(json.dumps({'parsed_stdout':probe}));return {'ready':True}
            actual=result(status,provider_version)
            if mutate:mutate(actual)
            error=GreaError('TOOL_FAILED','fixture exit')if code in (2,3)else None
            with patch('grea.integrations.monkey.local.readiness',return_value={'ready':True}),patch.object(beaver,'check',side_effect=checked),patch.object(beaver,'package_identity',return_value=cfg['package_files']),patch.object(beaver,'command_identity',return_value=cfg['command_files']),patch('grea.runner.execute',return_value=({'parsed_stdout':actual,'capture_complete':True,'exit_code':code},[],error))as run:
                value=ops.invoke(lock,req,root/'receipt');return value,run.call_count

    def test_group_mismatch_and_old_lock_prevent_execution(self):
        for options in ({'declared':'workspace.inspect'},{'version':'0.2.0'}):
            with self.subTest(options=options):
                value,count=self.invoke_fixture(**options)
                self.assertEqual(count,0);self.assertFalse(value['executed']);self.assertEqual(value['status'],'needs_action')

    def test_v03_status_and_nonzero_diagnostics_are_preserved(self):
        for status,code in [('ok',0),('partial',1),('blocked',3),('failed',2),('not_run',3)]:
            with self.subTest(status=status):
                value,count=self.invoke_fixture(status,code)
                self.assertEqual(count,1);self.assertEqual(value['status'],status);self.assertEqual(value['provider_result']['diagnostics'],[{'code':'fixture'}])
                self.assertEqual(value['gameplay'],'not_run')

    def test_invalid_result_schema_or_identity_stays_needs_action_with_raw_receipt(self):
        for mutate in (lambda r:r.update(diagnostics='invalid'),lambda r:r['producer'].update(implementationSha256='a'*64),lambda r:r['producer'].update(version='0.3.0')):
            with self.subTest(mutate=mutate):
                value,count=self.invoke_fixture(mutate=mutate);self.assertEqual(count,1)
                self.assertEqual(value['status'],'needs_action');self.assertTrue(value['executed']);self.assertIn('provider_result',value)
        value,_=self.invoke_fixture('blocked',2);self.assertEqual(value['status'],'needs_action')

    def test_candidate08_requires_its_own_exact_producer_and_preserves07(self):
        cap=self.capabilities();beaver.validate_capabilities(cap)
        candidate08=dict(cap,version='0.3.0',producer_implementation_sha256=beaver.V03_CANDIDATES['0.3.0']['implementation_sha256'])
        beaver.validate_capabilities(candidate08)
        for bad in (dict(candidate08,producer_implementation_sha256=beaver.V03_IMPLEMENTATION),dict(cap,producer_implementation_sha256=candidate08['producer_implementation_sha256'])):
            with self.subTest(bad=bad),self.assertRaises(ValueError):beaver.validate_capabilities(bad)

    def test_candidate08_has_same_finite_routes_without_future_version_support(self):
        for name,spec in ops.OPERATIONS.items():
            if beaver.V03_VERSION in spec.get('versions',()):self.assertIn('0.3.0',spec['versions'],name)
        ops.validate_provider_version(request(project=fixture_path('project')),'0.3.0')
        with self.assertRaises(ValueError):ops.validate_provider_version(request(project=fixture_path('project')),'0.3.0.rc1')

    def test_candidate08_status_schema_and_cross_candidate_result_drift(self):
        value,count=self.invoke_fixture('blocked',3,provider_version='0.3.0')
        self.assertEqual(count,1);self.assertEqual(value['status'],'blocked')
        value,count=self.invoke_fixture(provider_version='0.3.0',mutate=lambda r:r['producer'].update(implementationSha256=beaver.V03_IMPLEMENTATION))
        self.assertEqual(count,1);self.assertEqual(value['status'],'needs_action')

    def test_large_provider_plan_does_not_expand_request_or_lock_json_budget(self):
        with tempfile.TemporaryDirectory()as temp:
            path=Path(temp)/'large-plan.json'
            path.write_text(json.dumps(dict(contract='beaver-production/3',schemaVersion=3,provider_owned_metadata='x'*(9*1024**2))))
            self.assertEqual(ops.required_capability(request('production.apply',plan=str(path))),'production.plan/apply/recover')
            with self.assertRaises(ValueError):ops.read_json(path)


if __name__=='__main__':unittest.main()
