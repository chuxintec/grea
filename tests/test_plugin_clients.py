"""Client acceptance must isolate configuration and never start a model turn."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


class PluginClientTests(unittest.TestCase):
    def module(self):
        self.assertTrue((ROOT/'scripts/verify_plugin_clients.py').is_file(),
                        'Real client acceptance runner has not been implemented')
        return importlib.import_module('verify_plugin_clients')

    def test_environment_does_not_inherit_credentials_or_user_configuration(self):
        module = self.module()
        with tempfile.TemporaryDirectory(prefix='client 隔离 ') as tmp:
            root = Path(tmp).resolve()
            with patch.dict(os.environ, {'ANTHROPIC_API_KEY':'sentinel-secret',
                                         'OPENAI_API_KEY':'sentinel-secret',
                                         'NODE_OPTIONS':'--require /private/injected.js',
                                         'PYTHONPATH':'/private/source'}, clear=False):
                env = module.isolated_environment(root)
            self.assertNotIn('ANTHROPIC_API_KEY', env)
            self.assertNotIn('OPENAI_API_KEY', env)
            self.assertNotIn('NODE_OPTIONS', env)
            self.assertNotIn('PYTHONPATH', env)
            for key in ('HOME','CODEX_HOME','CLAUDE_CONFIG_DIR','TMPDIR'):
                self.assertTrue(Path(env[key]).is_relative_to(root))
            self.assertNotIn('/opt/homebrew', env['PATH'])

    def test_report_redacts_nested_credentials_and_private_paths(self):
        module = self.module()
        private_home = '/' + 'Users' + '/example'
        raw = {'error':'failed at ' + private_home + '/Secret Project/bin; Bearer sensitive-value',
               'details':[{'access_token':'sentinel-secret',
                           'path':'/private/tmp/client 中文/x/skills/grea/SKILL.md'}]}
        value = module.redact(raw, {'/private/tmp/client 中文':'<audit>'})
        text = json.dumps(value, ensure_ascii=False)
        for secret in (private_home, 'sensitive-value', 'sentinel-secret', '/private/tmp/client 中文'):
            self.assertNotIn(secret, text)
        self.assertIn('<audit>/x/skills/grea/SKILL.md', text)

    def test_protocol_rejects_model_requests(self):
        module = self.module()
        for protocol, method in [('codex','turn/start'), ('codex','thread/start'),
                                 ('claude','user'), ('claude','side_question')]:
            with self.assertRaises(ValueError):
                module.rpc_message(protocol, method, 1, {})
        self.assertEqual(module.rpc_message('claude','mcp_status',1,{})['request'],
                         {'subtype':'mcp_status'})

    def test_rpc_waits_past_notifications_and_matches_request_id(self):
        module = self.module()
        source = '''import json,sys
for line in sys.stdin:
    value=json.loads(line)
    print(json.dumps({"method":"progress","params":{}}),flush=True)
    print(json.dumps({"id":value["id"],"result":{"tools":{"hello":{}}}}),flush=True)
'''
        with tempfile.TemporaryDirectory() as tmp:
            env = module.isolated_environment(Path(tmp))
            with module.JsonPeer([sys.executable,'-u','-c',source], env, Path(tmp), 2) as peer:
                result = peer.request('codex','mcpServerStatus/list',{})
                self.assertIn('hello', result['tools'])
                self.assertEqual(getattr(peer, 'methods', None), ['mcpServerStatus/list'])
            self.assertIsNotNone(peer.process.returncode)

    def test_timeout_stops_the_process_group(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp)/'orphan-survived'
            child_source = 'import pathlib,time; time.sleep(.7); pathlib.Path(%r).write_text("alive")' % str(marker)
            source = 'import subprocess,sys,time\nchild=subprocess.Popen([sys.executable,"-c",%r])\nprint(child.pid,flush=True)\ntime.sleep(30)\n' % child_source
            result = module.run_command([sys.executable,'-u','-c',source],
                                        module.isolated_environment(Path(tmp)), Path(tmp), .3)
            self.assertTrue(result['timed_out'])
            self.assertTrue(result['stdout'].strip().isdigit(), 'Child did not start')
            time.sleep(.8)
            self.assertFalse(marker.exists(), 'MCP child survived timeout')

    def test_connected_without_tools_is_not_discovery_success(self):
        module = self.module()
        for client in ('codex','claude'):
            with self.assertRaises(ValueError):
                module.check_tools([], {'grea_list_tools'}, client)
            with self.assertRaises(ValueError):
                module.check_tools(['unrelated_tool'], {'grea_list_tools'}, client)
        self.assertEqual(module.check_tools(['grea_list_tools'], {'grea_list_tools'}, 'codex'),
                         ['grea_list_tools'])

    def test_namespaced_skills_must_come_from_enabled_installed_copy(self):
        module = self.module()
        self.assertTrue(callable(getattr(module, 'check_skills', None)),
                        'Namespaced client skill validation is missing')
        cache = Path('/private/tmp/audit/cache')
        item = {'name':'grea:grea', 'enabled':True,
                'path':str(cache/'market/grea/1/plugin/skills/grea/SKILL.md')}
        self.assertEqual(module.check_skills([item], {'grea'}, cache), ['grea:grea'])
        for changed in ({'enabled':False}, {'name':'other:grea'},
                        {'path':'/private/tmp/checkout/plugin/skills/grea/SKILL.md'}):
            with self.assertRaises(ValueError):
                module.check_skills([{**item, **changed}], {'grea'}, cache)

    def test_invalid_bundle_produces_failure_report_without_traceback(self):
        self.module()
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)/'invalid.zip'
            bundle.write_text('not a zip')
            report = Path(tmp)/'report.json'
            result = subprocess.run([sys.executable, str(ROOT/'scripts/verify_plugin_clients.py'),
                                     '--bundle',str(bundle),'--report',str(report)],
                                    capture_output=True,text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(report.is_file(), 'Invalid archive escaped structured failure reporting')
            self.assertEqual(json.loads(report.read_text())['status'], 'blocked')
            self.assertNotIn('Traceback', result.stderr)

    def test_delivered_marketplaces_select_real_root_install_entrypoints(self):
        module = self.module()
        self.assertTrue(callable(getattr(module, 'marketplace_plan', None)),
                        'Delivered marketplace acceptance is missing')
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base/'catalog/plugins/grea'
            for client, relative, source in [('codex','.agents/plugins/marketplace.json',{'source':'local','path':'./'}),
                                             ('claude','.claude-plugin/marketplace.json','./')]:
                path = root/relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({'name':'grea-local','plugins':[{'name':'grea','source':source}]}))
                plan = module.marketplace_plan(root, base, client)
                self.assertEqual(plan['origin'], 'bundled')
                self.assertEqual(plan['plugin_id'], 'grea@grea-local')
                self.assertEqual(plan['directory'], root)
                self.assertEqual(plan['add_source'], '.' if client == 'codex' else './')
                path.write_text(json.dumps({'name':'grea-local','plugins':[{'name':'grea','source':'../outside'}]}))
                with self.assertRaises(ValueError):
                    module.marketplace_plan(root, base, client)

    def test_legacy_fixture_is_explicit_and_does_not_modify_bundle(self):
        module = self.module()
        self.assertTrue(callable(getattr(module, 'marketplace_plan', None)),
                        'Delivered marketplace acceptance is missing')
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base/'catalog/plugins/grea'
            root.mkdir(parents=True)
            for client in ('codex','claude'):
                plan = module.marketplace_plan(root, base, client)
                self.assertEqual(plan['origin'], 'temporary_fixture')
                self.assertEqual(plan['directory'], base/'catalog')
                self.assertEqual(plan['plugin_id'], 'grea@grea-audit')
            self.assertEqual(list(root.iterdir()), [])

    def test_claude_validates_both_explicit_manifests_even_when_one_fails(self):
        module = self.module()
        self.assertTrue(callable(getattr(module, 'validate_claude_manifests', None)),
                        'Separate plugin and marketplace validation is missing')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root/'.claude-plugin'
            directory.mkdir()
            log = root/'calls.jsonl'
            source = 'log_path=' + repr(str(log)) + '\n' + '''import json,pathlib,sys
p=pathlib.Path(sys.argv[3]); value=json.loads(p.read_text())
with pathlib.Path(log_path).open('a') as out: out.write(p.name+'\\n')
kind='plugin' if p.name=='plugin.json' else 'marketplace'
print(json.dumps({'success':value['valid'],'target':str(p),'manifest':{'type':kind}}))
sys.exit(0 if value['valid'] else 1)
'''
            command = [sys.executable, '-c', source]
            for invalid in (None, 'plugin', 'marketplace'):
                for kind in ('plugin','marketplace'):
                    (directory/(kind+'.json')).write_text(json.dumps({'valid':kind != invalid}))
                log.write_text('')
                checks = module.validate_claude_manifests(command, root, root,
                                                        module.isolated_environment(root/'isolated'),root,2)
                self.assertEqual(log.read_text().splitlines(), ['plugin.json','marketplace.json'])
                for kind in ('plugin','marketplace'):
                    self.assertEqual(checks[kind]['status'], 'blocked' if kind == invalid else 'pass')


if __name__ == '__main__':
    unittest.main()
