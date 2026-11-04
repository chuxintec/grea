from path_support import fixture_path
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema import Draft202012Validator
from grea.integrations import beaver, beaver_operations as ops
from grea.beaver_contracts import documents
from test_beaver_result_changes import payload


class Fix18Tests(unittest.TestCase):
    def request(self,operation='qa.bind',**options):
        base=dict(project='example',build='build-1',profile='stable',run='run-1',**{'expected-owner':'a'*64})
        if not operation.startswith('qa.') or operation=='qa.input':base={}
        return dict(schema_version=1,operation=operation,options=dict(base,**options),timeout_seconds=90)

    def test_fixed_producer_and_previous_surface(self):
        from test_beaver_fix17 import Fix17Tests
        with patch.object(beaver,'P0_FIX17_VERSION',beaver.P0_FIX18_VERSION):
            # Reuse producer identity/retained operation assertions against the new fixed version.
            # The wrong producer must be a different old identity.
            Fix17Tests().test_fixed_producer_and_previous_surface()

    def test_sdk_options_paired_version_gated_and_schema_agrees(self):
        q=self.request('adoption.plan',candidate=fixture_path('candidate'),target=fixture_path('target'),**{'sdk-migration':fixture_path('sdk.json'),'expected-sdk-migration':'a'*64})
        ops.validate_provider_version(q,beaver.P0_FIX18_VERSION)
        with self.assertRaises(ValueError):ops.validate_provider_version(q,beaver.P0_FIX17_VERSION)
        validator=Draft202012Validator(documents()['beaver-operation.schema.json']);validator.validate(q)
        for field in ('sdk-migration','expected-sdk-migration'):
            options=dict(q['options']);options.pop(field);bad=dict(q,options=options)
            with self.assertRaises(ValueError):ops.validate(bad)
            self.assertFalse(validator.is_valid(bad))

    def test_qa_closed_identity_backend_and_window_range(self):
        validator=Draft202012Validator(documents()['beaver-operation.schema.json'])
        for window in (1,4294967295):
            q=self.request(window=window,backend='macos-native-ax-pid/1');ops.validate_provider_version(q,beaver.P0_FIX18_VERSION);validator.validate(q)
        for change in ({'window':0},{'window':True},{'window':4294967296},{'backend':'getApp'},{'run':'../other'},{'project':'/tmp/project'}):
            q=self.request(**change)
            with self.assertRaises(ValueError):ops.validate(q)
            self.assertFalse(validator.is_valid(q))
        q=self.request('qa.inspect-instance');q['options'].pop('run')
        with self.assertRaises(ValueError):ops.validate(q)
        with self.assertRaises(ValueError):ops.validate_provider_version(self.request(),beaver.P0_FIX17_VERSION)

    def test_input_cannot_override_pid_or_owned_session(self):
        q=self.request('qa.input',session=fixture_path('session.json'),spec=fixture_path('input.json'),**{'expected-session':'a'*64,'expected-spec':'b'*64})
        ops.validate_provider_version(q,beaver.P0_FIX18_VERSION)
        argv=ops.argv_for(q,fixture_path('receipt'));self.assertEqual(argv[:2],['qa','input']);self.assertEqual(argv[-2:],['--out',fixture_path('receipt/provider-output')])
        for changes in ({'pid':123},{'backend':'other'},{'expected-session':'bad'}):
            with self.assertRaises(ValueError):ops.validate(dict(q,options=dict(q['options'],**changes)))

    def test_partial_input_keeps_unknown_and_posted_effects_without_replay(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();q=self.request('qa.input',session=str(root/'session'),spec=str(root/'spec'),**{'expected-session':'a'*64,'expected-spec':'b'*64});request=root/'request.json';request.write_text(json.dumps(q));cfg=dict(identity_root=str(root/'package'),package_files={'f':'h'},command=[str(root/'beaver')],command_files={'cmd':'h'},version=beaver.P0_FIX18_VERSION);lock=root/'lock.json';lock.write_text(json.dumps(cfg))
            for index,data in enumerate(({'rawStatus':'unknown','eventsPosted':None,'delivery':'possibly-delivered'},{'rawStatus':'blocked','eventsPosted':2,'axActionsPerformed':1},{'rawStatus':'blocked','eventsPosted':0,'cursorSync':{'attempted':True,'completed':True},'cursorState':'changed'})):
                actual=payload([dict(operation='qa.input',effects=data)]);actual.update(status='partial',producer=dict(name='beaver',version=cfg['version'],implementationSha256=beaver.V03_CANDIDATES[cfg['version']]['implementation_sha256']),data=dict(nativeResult=data,launchPerformed=False))
                def check(output,**kw):
                    folder=Path(output)/'probe';folder.mkdir(parents=True);(folder/'run.json').write_text(json.dumps({'parsed_stdout':dict(producer=actual['producer'],data={'capabilities':[dict(id='qa.input',state='requires_provider')]})}));return {'ready':True}
                with patch('grea.integrations.monkey.local.readiness',return_value={'ready':True}),patch.object(beaver,'check',side_effect=check),patch.object(beaver,'package_identity',return_value=cfg['package_files']),patch.object(beaver,'command_identity',return_value=cfg['command_files']),patch('grea.runner.execute',return_value=({'parsed_stdout':actual,'capture_complete':True,'exit_code':1},[],None)) as execute:
                    result=ops.invoke(lock,request,root/('case-'+str(index)))
                self.assertEqual(execute.call_count,1);self.assertTrue(result['executed']);self.assertEqual(result['status'],'partial');self.assertEqual(result['provider_result'],actual)
