import json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from fixtures import fixture
from monkey import native,native_creator
from monkey.package import convert_package
from monkey.sources.containers import fingerprint
from monkey.sources.compiled import ParseError


class CreatorNativeTests(unittest.TestCase):
    def prepare(self,root):
        source=fixture(root/'source');convert_package(source.parent,'cocos38',root/'candidate')
        candidate=root/'candidate/CocosProject';editor=root/'CocosCreator';editor.write_text('#!/bin/sh\nexit 99\n');editor.chmod(0o700)
        instant=datetime.now(timezone.utc)
        return dict(candidate=candidate,editor=editor,expected_manifest=fingerprint(candidate/'manifest.json'),budget_seconds=60,
            deadline_utc=native.stamp(instant+timedelta(minutes=2)),window_end_utc=native.stamp(instant+timedelta(minutes=4)))

    def test_plan_is_nonexecuting_and_drift_prevents_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();options=self.prepare(root)
            with patch.object(native_creator.subprocess,'Popen',side_effect=AssertionError('planning cannot launch')):
                result=native.native_import(output=root/'plan',**options)
            self.assertEqual(result['status'],'planned');self.assertFalse((root/'plan/CocosProject').exists())
            (options['candidate']/'extensions/monkey-import/main.js').write_text('manual edit')
            with self.assertRaises(ParseError) as error:native.native_import(output=root/'bad',execute=True,**options)
            self.assertEqual(error.exception.code,'NATIVE_SOURCE_DRIFT');self.assertFalse((root/'bad').exists())

    def test_deadline_terminates_only_owned_child_and_binds_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();options=self.prepare(root);clock=[native.now()]
            class Child:
                pid=4123;returncode=None;terminated=False
                def poll(self):return self.returncode
                def terminate(self):self.terminated=True;self.returncode=-15
                def wait(self,timeout):return self.returncode
                def kill(self):raise AssertionError('No hard kill')
            child=Child()
            def launch(args,**kwargs):
                self.assertEqual(args,[str(options['editor']),'--project',str(root/'native/CocosProject')])
                self.assertEqual(kwargs['env']['MONKEY_NATIVE_PROJECT'],str(root/'native/CocosProject'))
                self.assertEqual(kwargs['env']['MONKEY_NATIVE_MANIFEST'],options['expected_manifest'])
                self.assertEqual(kwargs['env']['MONKEY_NATIVE_EXECUTE'],'1')
                clock[0]=native.utc(options['deadline_utc'])
                return child
            with patch.object(native_creator,'now',side_effect=lambda:clock[0]),patch.object(native_creator.subprocess,'Popen',side_effect=launch):
                result=native.native_import(output=root/'native',execute=True,**options)
            self.assertTrue(child.terminated);self.assertTrue(result['processExited']);self.assertEqual(result['stopReason'],'internal_deadline')
            self.assertEqual(fingerprint(options['candidate']/'manifest.json'),options['expected_manifest'])

    def test_journal_failure_still_reaps_owned_child(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();options=self.prepare(root)
            class Child:
                pid=4124;returncode=None;terminated=False
                def poll(self):return self.returncode
                def terminate(self):self.terminated=True;self.returncode=-15
                def wait(self,timeout):return self.returncode
            child=Child();write=native_creator.write_json
            def write_failure(path,value):
                if path.name=='execution-journal.json':raise OSError('journal unavailable')
                return write(path,value)
            with patch.object(native_creator.subprocess,'Popen',return_value=child),patch.object(native_creator,'write_json',side_effect=write_failure):
                result=native.native_import(output=root/'native',execute=True,**options)
            self.assertTrue(child.terminated);self.assertTrue(result['processExited']);self.assertEqual(result['reason'],'NATIVE_HOST_FAILED')

    def test_scheduler_cleanup_error_cannot_be_hidden_by_completed_readback(self):
        # Completion may already be on disk before the host observes an SDK
        # destruction error; successful field verification must not mask it.
        for completed in (False,True):
            with self.subTest(completed=completed),tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve();options=self.prepare(root)
                class Child:
                    pid=4125;returncode=None
                    def poll(self):return self.returncode
                    def terminate(self):self.returncode=-15
                    def wait(self,timeout):return self.returncode
                child=Child()
                def launch(args,**kwargs):
                    kwargs['stdout'].write("Error: cc.Scheduler: Illegal target which doesn't have id\n");kwargs['stdout'].flush()
                    if completed:
                        plan_hash=fingerprint(root/'native/CocosProject/extensions/monkey-import/import-plan.json')
                        native_creator.write_json(root/'native/CocosProject/Analysis/Readback/native-progress.json',dict(
                            schemaVersion=1,status='completed',sourceManifestSha256=options['expected_manifest'],
                            planSha256=plan_hash,phase='complete',processed=1,total=1,elapsedSeconds=1,nativeResumeSupported=False))
                    return child
                with patch.object(native_creator.subprocess,'Popen',side_effect=launch),patch.object(native_creator.cocos,'verify',return_value=dict(editorValidation='pass',diagnostics=[])):
                    result=native.native_import(output=root/'native',execute=True,**options)
                self.assertTrue(result['processExited']);self.assertEqual(child.returncode,-15)
                self.assertEqual(result['status'],'partial');self.assertEqual(result['reason'],'NATIVE_CREATOR_LIFECYCLE_ERROR')

    def test_extension_requires_explicit_binding_and_records_failures(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node is required for extension boundary checks')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();options=self.prepare(root);candidate=options['candidate']
            script=root/'check.cjs';script.write_text('''
const fs=require('fs'),path=require('path');
const [root,mode]=process.argv.slice(2);let count=0;
let queries=0;global.Editor={Project:{path:root},App:{version:'3.8.8'},Message:{request:async()=>{queries++;if(mode==='unready'&&queries<=2)return undefined;if(mode==='bad-schema')return {unexpected:true};return true;}}};
const execution=require(path.join(root,'extensions/monkey-import/execution.js'));
(async()=>{
 try {await execution.start(async()=>{count++;if(mode==='failure')throw Error('real method failure');if(mode==='timeout')return new Promise(()=>{});});}
 catch(e){console.log(JSON.stringify({count,error:e.message}));return;}
 const p=path.join(root,'Analysis/Readback/native-progress.json');
 console.log(JSON.stringify({count,progress:fs.existsSync(p)?JSON.parse(fs.readFileSync(p)):null}));
})();
''')
            env=dict(os.environ)
            for key in list(env):
                if key.startswith('MONKEY_NATIVE_'):env.pop(key)
            def run(mode,enabled=True):
                scoped=dict(env)
                if enabled:scoped.update(MONKEY_NATIVE_EXECUTE='1',MONKEY_NATIVE_PROJECT=str(candidate),MONKEY_NATIVE_MANIFEST=options['expected_manifest'],
                    MONKEY_NATIVE_DEADLINE_UTC=options['deadline_utc'],MONKEY_NATIVE_BUDGET_SECONDS='60')
                if mode=='wrong-project':scoped['MONKEY_NATIVE_PROJECT']=str(root)
                if mode=='timeout':scoped['MONKEY_NATIVE_BUDGET_SECONDS']='1'
                completed=subprocess.run([node,str(script),str(candidate),mode],env=scoped,capture_output=True,text=True,timeout=10)
                self.assertEqual(completed.returncode,0,completed.stderr)
                return json.loads(completed.stdout.splitlines()[-1])
            result=run('default',False);self.assertEqual(result['count'],0);self.assertIsNone(result['progress'])
            result=run('wrong-project');self.assertEqual(result['count'],0);self.assertEqual(result['error'],'NATIVE_PROJECT_BINDING_MISMATCH')
            result=run('success');self.assertEqual(result['count'],1);self.assertEqual(result['progress']['status'],'completed')
            result=run('unready');self.assertEqual(result['count'],1);self.assertEqual(result['progress']['status'],'completed')
            result=run('bad-schema');self.assertEqual(result['count'],0);self.assertEqual(result['progress']['status'],'failed')
            result=run('failure');self.assertEqual(result['count'],1);self.assertEqual(result['progress']['status'],'failed')
            failure=json.loads((candidate/'Analysis/Readback/native-error.json').read_text());self.assertEqual(failure['message'],'real method failure')
            self.assertEqual(failure['sourceManifestSha256'],options['expected_manifest'])
            result=run('timeout');self.assertEqual(result['count'],1);self.assertEqual(result['progress']['status'],'budget_exhausted')
