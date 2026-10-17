import sys
"""M3 transaction tests use a fake Editor; native behavior is tested separately in Unity."""
import json
import asyncio
import subprocess
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from grea.application import dispatch
from grea import unity_generation as g
from grea.common import GreaError
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from grea.unity_project_contracts import documents

ROOT = Path(__file__).resolve().parents[1]


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.profile = json.loads((ROOT / 'tests/fixtures/unity-generation-v1.json').read_text())
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        (self.root / 'grea-project.json').write_text(json.dumps(self.profile))

    def plan(self): return g.plan_generation(self.root)

    def generate(self, run='Evidence/run', **kwargs):
        return g.generate_project(self.root, self.plan()['planId'], run, **kwargs)

    def fake_editor(self, tool_id, arguments, run_dir, **kwargs):
        self.assertEqual(tool_id, 'unity_cli'); self.assertIn('-executeMethod', arguments)
        stage = Path(arguments[1]); request = json.loads((stage / 'Tools/Generated/request.json').read_text())
        assets = [f'Assets/GreaGenerated/{n}' for n in ('ButtonShell.prefab','ModalShell.prefab','UIHost.prefab','BootstrapConfig.asset','Renderer.asset','Pipeline.asset')] + list(self.profile['scenes'].values())
        journal = {'generatorVersion':g.VERSION, 'identity':request['identity'], 'complete':True, 'errorCount':0, 'pending':'', 'assets':[]}
        for index, name in enumerate(assets):
            path=stage/name; path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('synthetic '+name); meta=Path(str(path)+'.meta'); meta.write_text('guid: '+f'{index:032x}'+'\n')
            journal['assets'].append({'path':name,'sha256':g.sha(path.read_bytes()),'metaSha256':g.sha(meta.read_bytes()),'guid':f'{index:032x}','fileIds':['1']})
        (stage/'Tools/Generated/editor-journal.json').write_bytes(g.encoded(journal))
        Path(run_dir).mkdir(); (Path(run_dir)/'run.json').write_text('{"exit_code":0}')
        return {'exit_code':0, 'status':'ok'}, [], None

    def test_recipe_boundary_violation_is_rejected_before_planning_writes(self):
        distribution = self.root / 'distribution'
        for relative in ('tools/unity/framework', 'tools/unity/templates/counter-composition', 'tools/unity/templates/minimal-project'):
            shutil.copytree(ROOT / relative, distribution / relative)
        domain = distribution / 'tools/unity/templates/counter-composition/Assets/Game/Domain/CounterState.cs'
        domain.write_text('using UnityEngine;\n' + domain.read_text())
        with patch.object(g, 'package_root', return_value=distribution):
            with self.assertRaises(GreaError) as error:
                self.plan()
        self.assertEqual(error.exception.code, 'FRAMEWORK_BOUNDARY')
        self.assertFalse((self.root / 'UnityProject').exists())

    def test_boundary_implementation_changes_invalidate_recipe_identity(self):
        first = self.plan()
        with patch.object(g, 'boundary_implementation_hash', return_value='0' * 64):
            second = self.plan()
        self.assertNotEqual(first['recipeId'], second['recipeId'])
        self.assertNotEqual(first['planId'], second['planId'])

    def test_same_profile_static_plan_and_generated_tree_agree(self):
        from grea.unity_projects import validate_project, plan_project
        import hashlib
        self.assertEqual(validate_project(self.root,mode='new')['staticStatus'],'pass')
        static = plan_project(self.root,mode='new')
        self.assertIn('UnityProject/Assets/Game/Bootstrap/ProjectBootstrap.cs',[x['target'] for x in static['items']])
        def imported(*args,**kwargs):
            result=self.fake_editor(*args,**kwargs)
            assets=Path(args[1][1])/'Assets'
            for path in list(assets.rglob('*')):
                if path.suffix!='.meta' and not Path(str(path)+'.meta').exists():
                    Path(str(path)+'.meta').write_text('guid: '+hashlib.md5(str(path).encode()).hexdigest()+'\n')
            return result
        with patch.object(g.runner,'execute',side_effect=imported):self.generate()
        report=validate_project(self.root)
        self.assertEqual(report['staticStatus'],'pass',report['findings'])
        self.assertEqual(report['capability']['generation'],'not_run')

    def test_editor_errors_cannot_be_recovered_or_published(self):
        def failed_editor(*args, **kwargs):
            result = self.fake_editor(*args, **kwargs)
            journal_path = Path(args[1][1])/'Tools/Generated/editor-journal.json'
            journal = json.loads(journal_path.read_text()); journal['errorCount'] = 1
            journal_path.write_text(json.dumps(journal))
            return result
        with patch.object(g.runner, 'execute', side_effect=failed_editor):
            with self.assertRaises(GreaError) as error: self.generate()
        self.assertEqual(error.exception.code, 'VERIFICATION_FAILED')
        with patch.object(g.runner, 'execute') as run:
            with self.assertRaises(GreaError) as error: g.recover_generation(self.root, 'Evidence/run')
            self.assertEqual(error.exception.code, 'RECOVERY_REQUIRED'); run.assert_not_called()
        self.assertFalse((self.root/'UnityProject').exists())

    def test_plan_deterministic_readonly_and_adopt_never_claims_generation(self):
        before=list(self.root.rglob('*')); one=self.plan(); self.assertEqual(one,self.plan()); self.assertEqual(before,list(self.root.rglob('*')))
        Draft202012Validator(documents()['unity-generation-plan.schema.json']).validate(one)
        self.assertTrue(one['generationReady'])
        project=self.root/'UnityProject'; project.mkdir(); (project/'human.txt').write_text('keep')
        self.assertEqual(g.plan_generation(self.root,mode='adopt')['action'],'preserve')
        self.assertFalse(g.plan_generation(self.root,mode='adopt')['generationReady'])
        with self.assertRaises(GreaError):self.plan()
        self.assertEqual((project/'human.txt').read_text(),'keep')

    def test_complete_repeat_and_seed_changes_never_overwritten(self):
        with patch.object(g.runner,'execute',side_effect=self.fake_editor) as run:
            self.assertEqual(self.generate()['state'],'generated'); count=run.call_count
            self.assertEqual(self.generate()['state'],'unchanged');self.assertEqual(run.call_count,count)
            seed=self.root/'UnityProject/Assets/Game/Bootstrap/ProjectBootstrap.cs';seed.write_text('// human code')
            result=self.generate();self.assertIn(seed.relative_to(self.root/'UnityProject').as_posix(),result['seedChanges'])
            self.assertEqual(seed.read_text(),'// human code');self.assertEqual(run.call_count,count)

    def test_missing_published_target_does_not_report_recovery_success(self):
        with patch.object(g.runner,'execute',side_effect=self.fake_editor):self.generate()
        shutil.rmtree(self.root/'UnityProject')
        with self.assertRaises(GreaError) as error:g.recover_generation(self.root,'Evidence/run')
        self.assertEqual(error.exception.code,'RECOVERY_REQUIRED');self.assertFalse((self.root/'UnityProject').exists())

    def test_generated_package_meta_and_missing_manifest_conflicts(self):
        with patch.object(g.runner,'execute',side_effect=self.fake_editor):self.generate()
        target=self.root/'UnityProject'
        for name in ['Assets/GreaGenerated/UIHost.prefab','Assets/GreaGenerated/UIHost.prefab.meta','Packages/com.grea.foundation/package.json',g.MANIFEST]:
            p=target/name; original=p.read_bytes();p.unlink()
            with self.assertRaises(GreaError):self.plan()
            p.write_bytes(original)
        p=target/'Assets/GreaGenerated/UIHost.prefab';p.write_text('human')
        with self.assertRaises(GreaError) as error:self.plan()
        self.assertEqual(error.exception.code,'OWNERSHIP_CONFLICT');self.assertEqual(p.read_text(),'human')

    def test_invalid_combinations_and_path_scopes(self):
        baseline=json.loads(json.dumps(self.profile))
        for group,key,value in [('toolchain','ui','uitk'),('template','version','0.2.0'),('paths','unityProject','../outside'),('paths','evidenceRoot','UnityProject/Evidence')]:
            self.profile=json.loads(json.dumps(baseline));self.profile[group][key]=value;self.save()
            with self.assertRaises(GreaError):self.plan()
        self.profile=baseline;self.save()
        with self.assertRaises(GreaError):self.generate(run='elsewhere/run')

    def test_stale_plan_and_cancel_before_any_project_writes(self):
        plan=self.plan();self.profile['projectId']='changed';self.save()
        with self.assertRaises(GreaError) as error:g.generate_project(self.root,plan['planId'],'Evidence/run')
        self.assertEqual(error.exception.code,'STALE_PLAN');self.assertFalse((self.root/'Evidence').exists())
        event=threading.Event();event.set()
        with self.assertRaises(GreaError):self.generate(cancel=event)
        self.assertFalse((self.root/'UnityProject').exists())

    def test_recovery_after_preparation_verification_and_atomic_publication(self):
        for checkpoint in ['prepared','verified','published']:
            with self.subTest(checkpoint=checkpoint):
                root=self.root/checkpoint;root.mkdir();shutil.copyfile(self.root/'grea-project.json',root/'grea-project.json')
                def stop(stage):
                    if stage==checkpoint:raise RuntimeError('simulated process stop')
                with patch.object(g.runner,'execute',side_effect=self.fake_editor), patch.object(g,'_checkpoint',side_effect=stop):
                    with self.assertRaises(RuntimeError):g.generate_project(root,g.plan_generation(root)['planId'],'Evidence/run')
                with patch.object(g.runner,'execute',side_effect=self.fake_editor):
                    result=g.recover_generation(root,'Evidence/run')
                self.assertIn(result['state'],('generated','recovered'));self.assertTrue((root/'UnityProject'/g.MANIFEST).is_file())

    def test_partial_source_staging_recovers_only_matching_owned_bytes(self):
        def stop(stage):
            if stage.startswith('source:'):raise RuntimeError('stop during copy')
        with patch.object(g,'_checkpoint',side_effect=stop):
            with self.assertRaises(RuntimeError):self.generate()
        with patch.object(g.runner,'execute',side_effect=self.fake_editor):g.recover_generation(self.root,'Evidence/run')
        self.assertTrue((self.root/'UnityProject'/g.MANIFEST).is_file())

    def test_recovery_rejects_changes_old_version_and_uncertain_live_editor(self):
        def stop(stage):
            if stage=='prepared':raise RuntimeError('stop')
        with patch.object(g,'_checkpoint',side_effect=stop):
            with self.assertRaises(RuntimeError):self.generate()
        statefile=self.root/'Evidence/run/state.json';state=json.loads(statefile.read_text())
        stale=dict(state,generatorVersion='0.0.0');statefile.write_text(json.dumps(stale))
        with self.assertRaises(GreaError):g.recover_generation(self.root,'Evidence/run')
        statefile.write_text(json.dumps(dict(state,phase='editor_running',attempts=1)))
        with self.assertRaises(GreaError) as error:g.recover_generation(self.root,'Evidence/run')
        self.assertEqual(error.exception.code,'RECOVERY_REQUIRED')
        statefile.write_text(json.dumps(state));p=self.root/'Evidence/run/staging/Assets/Game/Bootstrap/ProjectBootstrap.cs';p.write_text('human')
        with self.assertRaises(GreaError):g.recover_generation(self.root,'Evidence/run')
        self.assertEqual(p.read_text(),'human');self.assertFalse((self.root/'UnityProject').exists())

    def test_new_target_appearing_during_execution_is_preserved(self):
        def edit(stage):
            if stage=='verified':
                p=self.root/'UnityProject';p.mkdir();(p/'human.txt').write_text('keep')
        with patch.object(g.runner,'execute',side_effect=self.fake_editor),patch.object(g,'_checkpoint',side_effect=edit):
            with self.assertRaises(GreaError):self.generate()
        self.assertEqual((self.root/'UnityProject/human.txt').read_text(),'keep')

    def test_atomic_publish_refuses_even_empty_existing_target(self):
        a=self.root/'a';b=self.root/'b';a.mkdir();b.mkdir();(a/'x').write_text('keep')
        with self.assertRaises(GreaError):g._publish_new(a,b)
        self.assertEqual((a/'x').read_text(),'keep');self.assertEqual(list(b.iterdir()),[])

    def test_busy_root_and_symlink_are_rejected(self):
        with g._lock(self.root):
            with self.assertRaises(GreaError) as error:self.generate()
        self.assertEqual(error.exception.code,'GENERATION_BUSY')
        (self.root/'UnityProject').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(GreaError):self.plan()

    def test_failure_retains_staging_and_returns_recovery_error(self):
        with patch.object(g.runner,'execute',return_value=({'exit_code':1,'reason':'TIMEOUT'},[],GreaError('TIMEOUT','test'))):
            result=dispatch('generate_unity_project',{'project_root':str(self.root),'plan_id':self.plan()['planId'],'run_dir':'Evidence/run'})
        self.assertEqual(result['error']['code'],'RECOVERY_REQUIRED');self.assertFalse((self.root/'UnityProject').exists())
        self.assertTrue((self.root/'Evidence/run/staging').is_dir())

    def test_new_operations_share_envelope_and_m1_stays_readonly(self):
        from grea.contracts import catalog
        by_name={x['name']:x for x in catalog()}
        self.assertTrue(by_name['plan_unity_generation']['annotations']['readOnlyHint'])
        self.assertFalse(by_name['generate_unity_project']['annotations']['readOnlyHint'])
        result=dispatch('plan_unity_generation',{'project_root':str(self.root)})
        self.assertEqual(result['status'],'ok');self.assertEqual(result['result']['planId'],self.plan()['planId'])
        self.assertTrue(by_name['plan_unity_project']['annotations']['readOnlyHint'])

    def test_settled_editor_failure_can_resume_without_replaying_live_process(self):
        def fail(tool_id, arguments, run_dir, **kwargs):
            Path(run_dir).mkdir();(Path(run_dir)/'run.json').write_text('{"exit_code":1}')
            return {'exit_code':1,'reason':'TIMEOUT'},[],GreaError('TIMEOUT','synthetic')
        with patch.object(g.runner,'execute',side_effect=fail):
            with self.assertRaises(GreaError):self.generate()
        with patch.object(g.runner,'execute',side_effect=self.fake_editor):
            self.assertEqual(g.recover_generation(self.root,'Evidence/run')['state'],'generated')

    def test_cli_mcp_parity_and_preflight_rejections(self):
        async def run():
            async with Client(StdioServerParameters(command=sys.executable,args=[str(ROOT/'launch.py'),'mcp']),read_timeout_seconds=30) as client:
                requests=[('plan_unity_generation',{'project_root':str(self.root)}),
                          ('generate_unity_project',{'project_root':str(self.root),'plan_id':'0'*64,'run_dir':'Evidence/mcp'}),
                          ('recover_unity_generation',{'project_root':str(self.root),'run_dir':'../escape'})]
                for operation,request in requests:
                    mcp=(await client.call_tool(operation,request)).structured_content
                    cli=subprocess.run([sys.executable,str(ROOT/'launch.py'),operation.replace('_','-'),json.dumps(request)],capture_output=True,text=True,cwd=tempfile.gettempdir())
                    actual=json.loads(cli.stdout)
                    for key in ('status','result','error'):self.assertEqual(mcp[key],actual[key])
                    self.assertEqual(cli.returncode,{'ok':0,'partial':1,'error':2}[actual['status']])
        asyncio.run(run());self.assertFalse((self.root/'UnityProject').exists())


if __name__=='__main__':unittest.main()
