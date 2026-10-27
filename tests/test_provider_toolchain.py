import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from grea.integrations import beaver
from grea import registry
from grea.application import dispatch

def provider_env(root, *, path=''):
    root=Path(root)
    env={'HOME':str(root),'USERPROFILE':str(root),'PATH':str(path),
         'GREA_PROVIDER_STATE_DIR':str(root/'state')}
    if os.name=='nt':
        env['HOMEDRIVE']=root.drive
        env['HOMEPATH']=str(root)[len(root.drive):] or '\\'
    return env


class BeaverReadinessTests(unittest.TestCase):
    def test_discovery_missing_is_readonly(self):
        with tempfile.TemporaryDirectory() as t, patch.dict(os.environ, provider_env(t)), patch.object(beaver.subprocess,'run') as run:
            self.assertEqual(beaver.discover()['status'],'not_installed')
            run.assert_not_called();self.assertFalse((Path(t)/'state').exists())

    def test_stale_binding_does_not_choose_path(self):
        with tempfile.TemporaryDirectory() as t, patch.dict(os.environ,provider_env(t)):
            state=beaver.state_root();state.mkdir(parents=True);(state/'binding.json').write_text(json.dumps(dict(schema_version=1,command=['/missing/beaver'],lock='/missing/lock',version='0.1.0')))
            with patch.object(beaver.shutil,'which') as which:
                self.assertEqual(beaver.discover()['command'],['/missing/beaver']);which.assert_not_called()

    def test_ambiguous_installation_does_not_choose(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);a=r/'.local/bin/beaver';a.parent.mkdir(parents=True);a.write_text('a');a.chmod(0o755)
            b=r/'other';b.write_text('b');b.chmod(0o755)
            with patch.dict(os.environ,provider_env(r,path=str(b.parent))),patch.object(beaver.shutil,'which',return_value=str(b)):
                self.assertEqual(beaver.discover()['status'],'ambiguous')

    def test_capability_success_without_lock_is_not_ready(self):
        with tempfile.TemporaryDirectory() as t,patch.object(beaver,'discover',return_value={'status':'not_installed'}),patch.object(beaver,'capability_probe',return_value=(['/fake'],{'version':'0.1.0'})):
            value=beaver.check(Path(t)/'out');self.assertFalse(value['ready']);self.assertEqual(value['capability_probe'],'passed')

    def test_pin_rejects_wrong_imported_package(self):
        with tempfile.TemporaryDirectory() as t,patch.object(beaver,'capability_probe',return_value=(['/fake'],{'version':'0.1.0'})),patch.object(beaver,'imported_package',return_value=Path(t)/'real'):
            root=Path(t)/'other';root.mkdir();(root/'__init__.py').write_text('')
            value=beaver.check(Path(t)/'out',identity_root=root,pin=True)
            self.assertFalse(value['ready']);self.assertFalse((Path(t)/'out/beaver-lock.json').exists())

    def test_pin_and_check_reject_file_capability_and_launcher_drift(self):
        for drift in ('none','package','capability','launcher'):
            with self.subTest(drift=drift),tempfile.TemporaryDirectory() as t:
                root=Path(t)/'package';root.mkdir();(root/'__init__.py').write_text('version=1')
                command=['/explicit/beaver'];cap={'version':'0.1.0','operations':['inspect']}
                with patch.object(beaver,'capability_probe',return_value=(command,cap)),patch.object(beaver,'command_identity',return_value={'launcher':'hash'}),patch.object(beaver,'imported_package',return_value=root.resolve()),patch.object(registry,'tool',return_value={}),patch.object(registry,'command',return_value=command):
                    pinned=beaver.check(Path(t)/'pin',identity_root=root,pin=True);self.assertTrue(pinned['ready'])
                    if drift=='package':(root/'__init__.py').write_text('changed')
                    if drift=='capability':cap['operations'].append('mutate')
                    current=['/other'] if drift=='launcher' else command
                    with patch.object(registry,'command',return_value=current):
                        checked=beaver.check(Path(t)/'check',lock=pinned['lock'])
                    self.assertEqual(checked['ready'],drift=='none',checked)

    def test_unsupported_or_truncated_capability_is_not_ready(self):
        for cap,complete in [({'version':'99.0.0'},True),({'version':'0.1.0'},False),([],True)]:
            with tempfile.TemporaryDirectory() as t,patch.object(registry,'tool',return_value={}),patch.object(registry,'command',side_effect=[['/fake'],['/fake','capabilities']]),patch('grea.runner.execute',return_value=({'parsed_stdout':{'contract':'beaver-result/1','status':'ok','producer':{'name':'beaver','version':cap.get('version') if isinstance(cap,dict) else None},'data':{'contract':'beaver-capabilities/1','capabilities':[]}},'capture_complete':complete},[],None)):
                value=beaver.check(Path(t)/'out');self.assertFalse(value['ready'])

    def test_capability_lock_excludes_volatile_run_id(self):
        responses=[dict(contract='beaver-result/1',status='ok',operationId=run,
                        producer=dict(name='beaver',version='0.1.0'),
                        data=dict(contract='beaver-capabilities/1',capabilities=[])) for run in ('a','b')]
        results=[]
        with patch.object(registry,'tool',return_value={}),patch.object(registry,'command',side_effect=[['/fake'],['/fake','capabilities']]*2):
            for response in responses:
                with patch('grea.runner.execute',return_value=({'parsed_stdout':response,'capture_complete':True},[],None)):
                    results.append(beaver.capability_probe('/unused')[1])
        self.assertEqual(results[0],results[1])

    def test_missing_monkey_prevents_engineering_invocation(self):
        with tempfile.TemporaryDirectory() as t,patch('grea.integrations.monkey.local.readiness',return_value={'ready':False,'status':'needs_action'}),patch.object(beaver,'check',return_value={'ready':True,'status':'ok'}),patch('grea.runner.execute') as execute:
            r=Path(t);(r/'project').mkdir();(r/'lock.json').write_text('{}')
            value=beaver.inspect_project(r/'lock.json',r/'project',r/'out')
            self.assertFalse(value['executed']);self.assertEqual(value['status'],'needs_action');execute.assert_not_called()

    def test_explicit_provider_configuration_wins(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'providers.json';p.write_text(json.dumps(dict(schema_version=1,providers={'beaver':dict(command=['/explicit/beaver'],probe=['/explicit/beaver','capabilities'],systems=['Darwin'])})))
            with patch.dict(os.environ,{**provider_env(t),'GREA_PROVIDERS':str(p)}),patch.object(beaver,'provider_override') as auto:
                self.assertEqual(registry.tool('beaver')['execution']['command'],['/explicit/beaver']);auto.assert_not_called()

    def test_session_declares_dependencies_without_spawning(self):
        with patch.object(beaver.subprocess,'run') as run:
            result=dispatch('session');self.assertEqual(result['status'],'ok',result)
            self.assertEqual(result['result']['required_toolchain']['providers'],['monkey','beaver']);run.assert_not_called()

    def test_workflow_uses_correct_stage_without_forcing_reexport(self):
        for mode in ('recover','fix','reskin','refactor'):
            result=dispatch('plan_workflow',{'mode':mode,'source_engine':'unity'})['result']
            self.assertEqual(result['required_providers'],['monkey','beaver'])
            self.assertFalse(result['toolchain']['force_reexport_existing_project'])
            self.assertEqual('initial_project_pipeline' in result,mode=='recover')
            for step in result['steps']:
                if step.get('execution_provider'):
                    source_conversion=Path(step['reference']).name in {'Unity工程重建与恢复.md','Unity原生转换规范.md','Unity跨引擎移植与行为一致性.md','Unity源引擎映射-Cocos.md'}
                    expected='monkey' if mode=='recover' and source_conversion else 'beaver'
                    self.assertEqual(step['execution_provider'],expected)

    def test_recovery_with_go_backend_keeps_engineering_in_beaver(self):
        result=dispatch('plan_workflow',{'mode':'recover','source_engine':'unity','backend':'go'})['result']
        server=next(x for x in result['steps'] if Path(x['reference']).name=='Go六服与事务.md')
        self.assertEqual(server['execution_provider'],'beaver')
        self.assertEqual(server['tool_ids'],['beaver_pipeline'])

    def test_double_check_preserves_missing_beaver(self):
        from grea.tools.toolchain_check import main
        with tempfile.TemporaryDirectory() as t,patch('grea.integrations.monkey.local.readiness',return_value={'ready':True,'status':'ok'}),patch.object(beaver,'check',return_value={'ready':False,'status':'needs_action'}):
            self.assertEqual(main(['--output',str(Path(t)/'out')]),1)
            value=json.loads((Path(t)/'out/result.json').read_text());self.assertFalse(value['ready'])
            self.assertEqual(value['providers']['monkey']['status'],'ok')

if __name__=='__main__':unittest.main()
