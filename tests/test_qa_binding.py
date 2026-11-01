import copy
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
import test_qa_runtime as fixtures
from beaver import qa_binding as binding
from beaver.errors import BeaverError
from beaver.io import encoded,sha,write_json
from beaver.output_limits import digest_file


class QaBindingTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.QaRuntimePrepareTests();self.f.setUp();self.root=self.f.root
        self.prepared=self.f.call_prepare(self.f.make_spec());self.owner=self.prepared['owner'];self.owner_hash=self.prepared['ownerSha256']
        self.home=self.f.mock_home/'Library/Application Support/beaver/unity-qa'
        self.app=Path(self.prepared['bundle']['path']);self.exe=self.app/'Contents/MacOS/Fixture'
        self.data=self.app.parent.parent.parent/'data';self.log=self.data/'logs/profile-a/run-a.log';self.log.parent.mkdir(parents=True);self.log.write_text('')
        self.argv=[str(self.exe),*self.owner['arguments'],'-logFile',str(self.log)]
        self.env={name:(self.prepared['profileRoot'] if row['kind']=='profile' else self.owner['configInputs'][row['id']]['path']) for name,row in self.owner['environmentBindings'].items()}
        self.origin=dict(status='verified',pid=4321,parentPid=123,uniqueId='4321:100:7',startTime=[100,7],initialPhase='sandbox-exec',expectedArgumentsSha256=sha(encoded(self.argv)))
        self.record=dict(runId='run-a',projectId='fixture-project',buildId='build-a',profileId='profile-a',expectedOwnerSha256=self.owner_hash,pid=4321,owned=True,status='running',cwd=str(self.app),executablePath=str(self.exe),executableSha256=digest_file(self.exe),logPath=str(self.log),cleanEnvironment=self.env,instanceOrigin=self.origin)
        self.run=self.data/'runs/run-a.json';self.run.parent.mkdir();write_json(self.run,self.record)
        self.snapshot=dict(status='verified',pid=4321,ppid=123,uniqueId='4321:100:7',startTime=[100,7],executablePath=str(self.exe),arguments=self.argv,environment=self.env)
        self.patches=[patch('beaver.qa_runtime._home_root',return_value=self.home),patch('beaver.qa_binding.identity',return_value='f'*64)]
        for p in self.patches:p.start()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.f.tearDown()

    def args(self):return ['fixture-project','build-a','profile-a',self.owner_hash,'run-a']

    def native_compile(self,folder):
        p=folder/'native/BeaverAppBinding';p.parent.mkdir();p.write_bytes(b'fixture controller; never run')
        return dict(path=str(p),sha256=digest_file(p),sourceSha256='a'*64)

    def make_binding(self,out='binding'):
        windows=dict(status='verified',windows=[dict(windowId=88,ownerPid=4321,bounds=dict(x=0,y=0,width=300,height=200))])
        with patch.object(binding.process_identity,'snapshot',return_value=self.snapshot),patch.object(binding,'_compile',side_effect=self.native_compile),patch.object(binding,'_native',return_value=windows):
            return binding.bind(*self.args(),self.root/out)

    def test_inspection_proves_wrapper_exec_birth_without_changing_historical_record(self):
        before=self.run.read_bytes()
        with patch.object(binding.process_identity,'snapshot',return_value=self.snapshot),patch('subprocess.Popen') as popen:
            r=binding.inspect_instance(*self.args(),self.root/'inspect')
        self.assertEqual(r['status'],'process-verified');self.assertFalse(r['attachAllowed']);self.assertFalse(r['launchPerformed']);popen.assert_not_called()
        self.assertEqual(self.run.read_bytes(),before)

    def test_legacy_unknown_pid_reuse_other_profile_arguments_and_executable_refused(self):
        for fault in ('legacy','birth','environment','arguments','executable','exited'):
            with self.subTest(fault=fault):
                record=copy.deepcopy(self.record);snap=copy.deepcopy(self.snapshot)
                if fault=='legacy':record.pop('instanceOrigin')
                if fault=='birth':snap['uniqueId']='4321:101:7'
                if fault=='environment':snap['environment']={}
                if fault=='arguments':snap['arguments']=[*self.argv[:-1],self.argv[-1]+'-foreign']
                if fault=='executable':
                    other=self.root/'foreign';other.write_bytes(self.exe.read_bytes());snap['executablePath']=str(other)
                if fault=='exited':record['status']='exited'
                write_json(self.run,record)
                with patch.object(binding.process_identity,'snapshot',return_value=snap),patch('subprocess.Popen') as popen,self.assertRaises(BeaverError):
                    binding.inspect_instance(*self.args(),self.root/('refuse-'+fault))
                popen.assert_not_called()
        write_json(self.run,self.record)

    def test_bind_refuses_ambiguous_window_and_launching_backend_without_selection(self):
        with self.assertRaises(BeaverError) as e:binding.bind(*self.args(),self.root/'unsafe',backend='cua-macos')
        self.assertEqual(e.exception.code,'QA_ATTACH_BACKEND_UNSUPPORTED')
        windows=dict(status='verified',windows=[dict(windowId=1,ownerPid=4321),dict(windowId=2,ownerPid=4321)])
        with patch.object(binding.process_identity,'snapshot',return_value=self.snapshot),patch.object(binding,'_compile',side_effect=self.native_compile),patch.object(binding,'_native',return_value=windows),patch('subprocess.Popen') as popen:
            r=binding.bind(*self.args(),self.root/'ambiguous')
        self.assertEqual(r['status'],'blocked');self.assertFalse((self.root/'ambiguous/qa-binding.json').exists());popen.assert_not_called()

    def test_input_uses_only_bound_pid_window_and_does_not_echo_text(self):
        bound=self.make_binding();spec=self.root/'input-spec.json';write_json(spec,dict(operation='text',text='private-example'))
        with patch.object(binding.process_identity,'snapshot',return_value=self.snapshot),patch.object(binding,'_native',return_value=dict(status='performed',eventsPosted=2)) as native:
            r=binding.input_event(bound['session'],bound['sessionSha256'],spec,digest_file(spec),self.root/'input')
        request=native.call_args.args[1];self.assertEqual(request['pid'],4321);self.assertEqual(request['windowId'],88);self.assertEqual(request['text'],'private-example')
        self.assertNotIn('private-example',json.dumps(r));self.assertFalse(r['launchPerformed'])

    def test_stale_expired_session_and_identity_override_never_send_input(self):
        bound=self.make_binding();path=Path(bound['session']);spec=self.root/'input-spec.json';write_json(spec,dict(operation='click',x=20,y=30,pid=999))
        with patch.object(binding.process_identity,'snapshot',return_value=self.snapshot),patch.object(binding,'_native') as native,self.assertRaises(BeaverError):
            binding.input_event(path,bound['sessionSha256'],spec,digest_file(spec),self.root/'override')
        native.assert_not_called()
        write_json(spec,dict(operation='observe'))
        changed=copy.deepcopy(self.snapshot);changed['uniqueId']='4321:200:9'
        with patch.object(binding.process_identity,'snapshot',return_value=changed),patch.object(binding,'_native') as native,self.assertRaises(BeaverError):
            binding.input_event(path,bound['sessionSha256'],spec,digest_file(spec),self.root/'reused')
        native.assert_not_called()
        session=json.loads(path.read_text());session['expiresUtc']='2000-01-01T00:00:00+00:00';write_json(path,session)
        with patch.object(binding,'_native') as native,self.assertRaises(BeaverError):binding.input_event(path,digest_file(path),spec,digest_file(spec),self.root/'expired')
        native.assert_not_called()

    def test_session_and_input_spec_reject_unknown_fields_before_native_dispatch(self):
        bound=self.make_binding();session_path=Path(bound['session']);session=json.loads(session_path.read_text())
        session['unexpected']='foreign';write_json(session_path,session)
        spec=self.root/'strict-spec.json';write_json(spec,dict(operation='observe'))
        with patch.object(binding.process_identity,'snapshot',return_value=self.snapshot),patch.object(binding,'_native') as native,self.assertRaises(BeaverError) as e:
            binding.input_event(session_path,digest_file(session_path),spec,digest_file(spec),self.root/'bad-session')
        self.assertEqual(e.exception.code,'QA_BIND_SESSION_SCHEMA');native.assert_not_called()
        # Re-create a valid session to independently exercise closed spec keys.
        bound=self.make_binding('binding-strict');session_path=Path(bound['session']);spec.write_text(json.dumps({'operation':'click','x':1,'y':2,'pid':999}),encoding='utf-8')
        with patch.object(binding.process_identity,'snapshot',return_value=self.snapshot),patch.object(binding,'_native') as native,self.assertRaises(BeaverError) as e:
            binding.input_event(session_path,bound['sessionSha256'],spec,digest_file(spec),self.root/'bad-spec')
        self.assertEqual(e.exception.code,'QA_BIND_INPUT_SPEC');native.assert_not_called()
        self.assertFalse((self.root/'bad-spec').exists())

    def test_timeout_after_dispatch_persists_unknown_not_zero_effect_receipt(self):
        bound=self.make_binding('binding-timeout');session_path=Path(bound['session']);session=json.loads(session_path.read_text())
        helper_file=Path(session['helper']['path']);helper_file.write_bytes(b'owned fake native helper')
        source=self.root/'helper-source.m';source.write_bytes(b'owned test helper source')
        session['helper']['sha256']=digest_file(helper_file);session['helper']['sourceSha256']=digest_file(source);write_json(session_path,session)
        bound['sessionSha256']=digest_file(session_path)
        spec=self.root/'timeout-spec.json';write_json(spec,dict(operation='click',x=20,y=30))
        def timeout(*args,**kwargs):
            pending=json.loads((self.root/'timeout-result/qa-input-result.json').read_text())
            self.assertEqual(pending['dispatchState'],'possibly-delivered')
            self.assertEqual(pending['native']['eventsPosted'],'unknown')
            raise subprocess.TimeoutExpired(args[0],20,output=b'private partial native output')
        with patch.object(binding.process_identity,'snapshot',return_value=self.snapshot),patch.object(binding,'_helper_source',return_value=source),patch.object(binding.subprocess,'run',side_effect=timeout):
            result=binding.input_event(session_path,bound['sessionSha256'],spec,digest_file(spec),self.root/'timeout-result')
        receipt=json.loads(Path(result['report']).read_text())
        self.assertEqual(result['status'],'partial');self.assertEqual(result['rawStatus'],'unknown')
        self.assertEqual(receipt['native']['eventsPosted'],'unknown')
        self.assertEqual(receipt['dispatchState'],'possibly-delivered')
        self.assertNotIn('private partial native output',json.dumps(receipt))

    def test_native_block_after_reported_events_is_partial(self):
        helper=self.root/'controller';helper.write_bytes(b'helper')
        source=self.root/'controller.m';source.write_bytes(b'source')
        identity=dict(path=str(helper),sha256=digest_file(helper),sourceSha256=digest_file(source))
        payload=encoded(dict(status='blocked',errorCode='PROCESS_NOT_FOUND',eventsPosted=1,axActionsAttempted=2,axActionsPerformed=1))
        completed=subprocess.CompletedProcess([str(helper)],3,stdout=payload,stderr=b'')
        with patch.object(binding,'_helper_source',return_value=source),patch.object(binding.subprocess,'run',return_value=completed):
            result=binding._native(identity,dict(operation='click'))
        self.assertEqual(result['nativeStatus'],'blocked');self.assertEqual(result['status'],'partial')
        self.assertEqual(result['eventsPosted'],1);self.assertEqual(result['processExitCode'],3)
        no_counts=subprocess.CompletedProcess([str(helper)],3,stdout=encoded(dict(status='blocked',errorCode='PROCESS_IDENTITY_UNAVAILABLE')),stderr=b'')
        with patch.object(binding,'_helper_source',return_value=source),patch.object(binding.subprocess,'run',return_value=no_counts):
            unknown=binding._native(identity,dict(operation='click'))
        self.assertEqual(unknown['status'],'unknown');self.assertEqual(unknown['eventsPosted'],'unknown')
        zero_effect= subprocess.CompletedProcess([str(helper)],0,stdout=encoded(dict(status='performed',eventsPosted=0,axActionsAttempted=0,axActionsPerformed=0)),stderr=b'')
        with patch.object(binding,'_helper_source',return_value=source),patch.object(binding.subprocess,'run',return_value=zero_effect):
            unknown=binding._native(identity,dict(operation='click'))
        self.assertEqual(unknown['status'],'unknown');self.assertEqual(unknown['eventsPosted'],'unknown')

    def test_helper_identity_failure_is_rejected_before_dispatch_receipt(self):
        bound=self.make_binding('binding-helper-drift');spec=self.root/'drift-spec.json';write_json(spec,dict(operation='click',x=10,y=10))
        with patch.object(binding.process_identity,'snapshot',return_value=self.snapshot),patch.object(binding.subprocess,'run') as native,self.assertRaises(BeaverError) as e:
            binding.input_event(bound['session'],bound['sessionSha256'],spec,digest_file(spec),self.root/'drift-result')
        self.assertEqual(e.exception.code,'QA_ATTACH_HELPER_DRIFT');native.assert_not_called()
        self.assertFalse((self.root/'drift-result/qa-input-result.json').exists())

    def test_owned_launch_capture_records_no_raw_environment_and_supports_exact_wrapper(self):
        for exe,args in [(self.exe,self.argv),(self.exe,['/usr/bin/sandbox-exec','-f','/owned/profile',*self.argv])]:
            snap=dict(self.snapshot,ppid=os.getpid(),arguments=args,executablePath=args[0],environment={'PRIVATE':'sensitive'})
            with patch.object(binding.process_identity,'snapshot',return_value=snap):r=binding.capture_origin(4321,exe,args,{'PRIVATE':'sensitive'})
            self.assertEqual(r['status'],'verified');self.assertNotIn('sensitive',json.dumps(r));self.assertNotIn('PRIVATE',json.dumps(r))


if __name__=='__main__':unittest.main()
