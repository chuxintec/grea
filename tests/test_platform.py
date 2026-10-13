import json,os,sys,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from grea import registry
from grea.application import dispatch
from grea.common import package_root,GreaError
ROOT=package_root()

class PlatformTests(unittest.TestCase):
    def test_wrapper_does_not_hide_missing_optional_provider(self):
        with tempfile.TemporaryDirectory() as d:
            payload=Path(d)/'provider.bin'
            entry={'id':'fixture','execution':{'command':[sys.executable]},'files':[sys.executable],'required_files':[str(payload)]}
            self.assertEqual(registry.presence(entry)['state'],'unavailable')
            with self.assertRaises(GreaError) as error:registry.command(entry)
            self.assertEqual(error.exception.code,'PROVIDER_UNAVAILABLE')
            payload.write_bytes(b'fixture')
            self.assertEqual(registry.presence(entry)['state'],'detected')

    def test_aliases_share_contract(self):
        for alias,canonical in [('decode-doctor','registry_doctor'),('check_game_build_skill','check_grea_skill'),('android_emulator_arm32_legacy','android-emulator-arm32')]:
            a=registry.tool(alias);c=registry.tool(canonical)
            self.assertEqual(a['execution'],c['execution']);self.assertEqual(a['probe'],c.get('probe'))
            self.assertEqual(a['canonical_id'],canonical)

    def test_windows_rejects_mac_bundle_but_keeps_inventory(self):
        with patch('grea.registry.platform.system',return_value='Windows'):
            tool=registry.tool('assetripper')
            self.assertEqual(registry.presence(tool)['state'],'unsupported')
            with self.assertRaises(GreaError) as error:registry.command(tool)
            self.assertEqual(error.exception.code,'UNSUPPORTED_HOST')
            self.assertEqual(registry.command(registry.tool('compare_traces'))[0],sys.executable)

    def test_architecture_guard(self):
        with patch('grea.registry.platform.system',return_value='Darwin'),patch('grea.registry.platform.machine',return_value='x86_64'):
            self.assertEqual(registry.presence(registry.tool('assetripper'))['reason'],'UNSUPPORTED_ARCH')

    def test_explicit_provider_override_and_unknown_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'providers.json';config={'schema_version':1,'providers':{'assetripper':{'systems':['Windows'],'command':[sys.executable,'-c','print("fixture")'],'probe':[sys.executable,'--version']}}};path.write_text(json.dumps(config))
            with patch.dict(os.environ,{'GREA_PROVIDERS':str(path)}),patch('grea.registry.platform.system',return_value='Windows'):
                e=registry.tool('assetripper');self.assertEqual(registry.command(e)[0],sys.executable)
                self.assertEqual(e['configuration_source'],str(path.resolve()))
                self.assertEqual(dispatch('doctor',{'tool_ids':['assetripper'],'probe':True})['status'],'ok')
                config['providers']['missing']=config['providers'].pop('assetripper');path.write_text(json.dumps(config))
                self.assertEqual(dispatch('session')['error']['code'],'INVALID_PROVIDER_CONFIG')

    def test_doctor_default_is_presence_only(self):
        p=subprocess.run([sys.executable,str(ROOT/'recovery/registry_doctor.py'),'--json'],capture_output=True,text=True)
        self.assertIn(p.returncode,(0,1),p.stderr)
        report=json.loads(p.stdout)
        self.assertTrue(all(row['level'] in ('presence','host') for row in report['result']['checks']))
        p=subprocess.run([sys.executable,str(ROOT/'recovery/registry_doctor.py'),'--json','--probe'],capture_output=True,text=True)
        self.assertEqual(json.loads(p.stdout)['error']['code'],'EXPLICIT_SELECTION_REQUIRED')

    def test_platform_tools_name_not_rewritten(self):
        command=registry.tool('adb')['execution']['command']
        self.assertIn('platform-tools',command[0]);self.assertNotIn('platform-grea',command[0])

    def test_event_wrapper_keeps_schema_and_difference_semantics(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a.jsonl';b=Path(d)/'b.jsonl'
            a.write_text('{"seq":1,"event":"start","state":{"n":1}}\n')
            b.write_text(a.read_text())
            cmd=[sys.executable,str(ROOT/'recovery/compare_events.py'),str(a),str(b)]
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
            b.write_text('{"seq":1,"event":"start","state":{"n":2}}\n')
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,1)
            b.write_text('{}\n');self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,2)

    def test_portable_launcher(self):
        p=subprocess.run([sys.executable,str(ROOT/'launch.py'),'session'],cwd=tempfile.gettempdir(),capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['status'],'ok')

if __name__=='__main__':unittest.main()
