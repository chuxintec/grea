#!/usr/bin/env python3
"""Accept a relocated plugin with no source, network, host Python, uv or install writes."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform
import queue
import shutil
import subprocess
import tempfile
import threading
import time

from plugin_bundle import encoded, inventory, sha256, verify_archive

ROOT = Path(__file__).resolve().parents[1]


def client_command(root, client):
    if client == 'codex':
        value = json.loads((root/'.mcp.json').read_text())['mcpServers']['grea']
        cwd = (root/value.get('cwd', '.')).resolve()
        command = (root/value['command']).resolve()
    elif client == 'claude':
        value = json.loads((root/'.claude-plugin/plugin.json').read_text())['mcpServers']['grea']
        command = Path(value['command'].replace('${CLAUDE_PLUGIN_ROOT}', str(root))).resolve()
        cwd = root
    else:
        raise ValueError('Unknown client')
    if root not in command.parents or not command.is_file() or cwd != root:
        raise ValueError('Client launcher escapes installed plugin')
    return [str(command), *value.get('args', [])], cwd


def sandbox_prefix(root, work):
    # The tested server and all its children are denied source/developer tools,
    # network access and writes into their own install. No Python monkeypatches.
    deny_read = [str(ROOT), '/opt/homebrew', str(Path.home()/'.local'), str(Path.home()/'.codex')]
    clauses = ['(version 1)', '(allow default)', '(deny network*)',
               '(deny file-write* (subpath ' + json.dumps(str(root), ensure_ascii=False) + '))']
    for path in deny_read:
        clauses.append('(deny file-read* (subpath ' + json.dumps(path, ensure_ascii=False) + '))')
    profile = work/'acceptance.sb'
    profile.write_text('\n'.join(clauses))
    return ['/usr/bin/sandbox-exec', '-f', str(profile)]


class Rpc:
    def __init__(self, command, cwd, env):
        self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, bufsize=1, start_new_session=True)
        self.queue = queue.Queue(); self.stderr = []; self.counter = 0
        def read():
            for line in self.process.stdout:
                try: self.queue.put(json.loads(line))
                except ValueError: self.queue.put({'invalid_stdout': line[:300]})
            self.queue.put({'eof': True})
        def errors():
            for line in self.process.stderr:
                self.stderr.append(line)
                if len(self.stderr) > 100: del self.stderr[0]
        self.readers = [threading.Thread(target=read, daemon=True), threading.Thread(target=errors, daemon=True)]
        for reader in self.readers: reader.start()

    def send(self, value):
        self.process.stdin.write(json.dumps(value)+'\n'); self.process.stdin.flush()

    def request(self, method, params=None, timeout=30):
        self.counter += 1; identity = self.counter
        self.send({'jsonrpc':'2.0', 'id': identity, 'method': method, 'params': params or {}})
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            try: value = self.queue.get(timeout=max(.01, deadline-time.monotonic()))
            except queue.Empty: break
            if 'eof' in value or 'invalid_stdout' in value:
                raise ValueError('MCP exited or polluted stdout: '+''.join(self.stderr)[-1000:])
            if value.get('id') != identity: continue
            if 'error' in value: raise ValueError('MCP protocol error: '+str(value['error']))
            return value['result']
        raise TimeoutError('MCP request timed out: '+method)

    def close(self):
        import signal
        if not self.process.stdin.closed: self.process.stdin.close()
        try: self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid, signal.SIGTERM)
            try: self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL); self.process.wait()
        for reader in self.readers: reader.join(timeout=2)
        self.process.stdout.close(); self.process.stderr.close()


def check(condition, message):
    if not condition: raise ValueError(message)


def acceptance(bundle):
    if (platform.system(), platform.machine()) != ('Darwin', 'arm64'):
        raise ValueError('Native acceptance requires macOS arm64')
    bundle = Path(bundle).resolve()
    checksums = dict(line.split('  ', 1)[::-1] for line in (bundle.parent/'SHA256SUMS').read_text().splitlines())
    check(checksums.get(bundle.name) == sha256(bundle), 'Plugin external checksum mismatch')
    with tempfile.TemporaryDirectory(prefix='grea 插件 acceptance ', dir='/private/tmp') as tmp:
        base = Path(tmp).resolve()
        manifest = verify_archive(bundle, base/'initial')
        root = base/'移动后 installed grea'
        (base/'initial/grea').rename(root)
        work = base/'empty workspace'; work.mkdir()
        home = base/'clean home'; home.mkdir()
        env = {'HOME': str(home), 'PATH':'/usr/bin:/bin', 'LANG':'en_US.UTF-8', 'TMPDIR':str(work)}
        prefix = sandbox_prefix(root, work)
        before = inventory(root)
        # Prove the isolation policy is enforced, not merely recorded.
        python = root/'runtime/bin/python3'
        probe = '''import pathlib,socket,sys
blocked=[]
for name,fn in [('source',lambda:pathlib.Path(sys.argv[1]).read_bytes()),('install_write',lambda:pathlib.Path(sys.argv[2]).write_text('bad')),('network',lambda:socket.create_connection(('127.0.0.1',9),timeout=1))]:
 try: fn()
 except PermissionError: blocked.append(name)
 except OSError as exc:
  if exc.errno in (1,13): blocked.append(name)
print(','.join(blocked))
'''
        isolated = subprocess.run([*prefix, str(python), '-I', '-B', '-c', probe, str(ROOT/'registry.json'), str(root/'forbidden')],
                                  env=env, cwd=work, capture_output=True, text=True, timeout=20)
        check(isolated.returncode == 0 and isolated.stdout.strip() == 'source,install_write,network',
              'Isolation policy did not enforce all restrictions: '+isolated.stderr[:300]+isolated.stdout[:300])
        catalog = subprocess.run([*prefix, str(root/'bin/grea'), 'catalog'], env=env, cwd=work,
                                 capture_output=True, text=True, timeout=20)
        check(catalog.returncode == 0, 'Relocated CLI catalog failed: '+catalog.stderr[:500])
        expected = json.loads(catalog.stdout)
        tools = sorted(x['name'] for x in expected['operations'])
        results = {}
        for client in ('codex', 'claude'):
            command, _ = client_command(root, client)
            rpc = Rpc([*prefix, *command], work, env)
            try:
                initialized = rpc.request('initialize', {'protocolVersion':'2025-03-26','capabilities':{},
                                                       'clientInfo':{'name':'grea-plugin-acceptance','version':'1'}})
                rpc.send({'jsonrpc':'2.0','method':'notifications/initialized'})
                listing = rpc.request('tools/list')
                check(sorted(x['name'] for x in listing['tools']) == tools, 'CLI/MCP catalog mismatch')
                def call(name, arguments):
                    response = rpc.request('tools/call', {'name':name,'arguments':arguments})
                    return response, response['structuredContent']
                response, session = call('session', {})
                check(session['status'] == 'ok' and session['result']['version'] == manifest['version'], 'Session/version failed')
                check(Path(session['result']['package_root']) == root, 'Session depends on original checkout')
                _, plan = call('plan_workflow', {'mode':'recover','source_engine':'cocos'})
                check(plan['status'] == 'ok', 'Bundled workflow references failed')
                check(all(root in Path(s['reference']).parents and Path(s['reference']).is_file() for s in plan['result']['steps']), 'Missing workflow resource')
                source = work/(client+' source'); source.mkdir()
                (source/'sample.txt').write_text('portable core')
                output = work/(client+' copied')
                _, copied = call('run_tool', {'tool_id':'static_asset_copy', 'arguments':['--source',str(source),'--output',str(output),'--map','sample.txt=renamed.txt'], 'run_dir':str(work/(client+' copy receipt'))})
                check(copied['status'] == 'ok' and (output/'renamed.txt').read_text() == 'portable core', 'Bundled tool subprocess failed')
                _, legacy = call('run_tool', {'tool_id':'validate_unity_project','arguments':['--help'], 'run_dir':str(work/(client+' legacy receipt'))})
                check(legacy['status'] == 'ok', 'Legacy launch.py did not use bundled Python')
                compiled = work/(client+' compiled.json')
                compiled.write_text(json.dumps([1,[],[],[['cc.Node',['_name'],2]],[[0,0,2]],[[0,'portable']],[],[],[],[],[]]))
                decoded = work/(client+' decoded')
                _, cocos = call('run_tool', {'tool_id':'cocos_assets','arguments':['--input',str(compiled),'--output',str(decoded)],'run_dir':str(work/(client+' cocos receipt'))})
                check(cocos['status']=='ok' and json.loads((decoded/'decoded.json').read_text())['instances'][0]['_name']=='portable','Bundled Cocos reader depends on host/source')
                project = work/(client+' synthetic project'); (project/'Assets').mkdir(parents=True)
                (project/'Assets/Entry.unity').write_text('%YAML 1.1\n')
                (project/'Assets/Save.cs').write_text('class Save { public string Json; }')
                policy=work/(client+' exit policy.json'); policy.write_text('{"schema_version":1,"exits":[]}')
                native_report=work/(client+' native report.json')
                _, native=call('run_tool',{'tool_id':'unity_native_exit','arguments':['--project',str(project),'--root','Entry.unity','--policy',str(policy),'--output',str(native_report)],'run_dir':str(work/(client+' native receipt'))})
                check(native['status']=='partial' and not json.loads(native_report.read_text())['native_exit_passed'],'Static native exit must stay pending under bundled Python')
                config_schema=work/(client+' config schema.json'); config_rows=work/(client+' config rows.json'); config_out=work/(client+' config candidate')
                config_schema.write_text(json.dumps(dict(schema_version=1,namespace='Own.Portable',name='Hint',key='Id',fields=[dict(name='Id',type='int'),dict(name='Text',type='string',nullable=True)])))
                config_rows.write_text('[{"Id":1,"Text":null},{"Id":2,"Text":""}]')
                _, config=call('run_tool',dict(tool_id='unity_config_candidate',arguments=['--schema',str(config_schema),'--input',str(config_rows),'--output',str(config_out)],run_dir=str(work/(client+' config receipt'))))
                check(config['status']=='ok' and (config_out/'HintTable.cs').is_file() and json.loads((config_out/'source-rows.json').read_text())[0]['Text'] is None,'Bundled typed config failed')
                recipe=work/(client+' native recipe.json'); native_out=work/(client+' native candidate')
                recipe.write_text(json.dumps(dict(schema_version=1,sprites=[],targets=[dict(path='Widget',scale=[2,3,1])],clips=[dict(name='Move',duration=1,loop=True,curves=[dict(target='Widget',property='m_LocalPosition.x',keys=[[0,0],[1,4]])],events=[])])))
                _, authored=call('run_tool',dict(tool_id='unity_native_assets',arguments=['prepare','--recipe',str(recipe),'--output',str(native_out)],run_dir=str(work/(client+' authoring receipt'))))
                check(authored['status']=='ok' and json.loads((native_out/'native-request.json').read_text())['targets'][0]['scale']==[2,3,1],'Bundled finite authoring failed')
                manifest_file=work/(client+' evidence.json')
                payload=source/'sample.txt'
                manifest_file.write_text(json.dumps(dict(schema_version=1,scope='owned fixture',entries=[dict(id='sample',layer='source',path='sample.txt',bytes=payload.stat().st_size,sha256=sha256(payload))])))
                evidence_report=work/(client+' evidence-report.json')
                _, verified=call('run_tool',dict(tool_id='evidence_manifest',arguments=['--root',str(source),'--manifest',str(manifest_file),'--adapter','flat-v1','--output',str(evidence_report)],run_dir=str(work/(client+' manifest receipt'))))
                check(verified['status']=='ok' and json.loads(evidence_report.read_text())['current_closure']=='verified','Bundled manifest verification failed')
                config_dir=work/(client+' typed export');config_dir.mkdir()
                (config_dir/'rows.json').write_text('[{"Id":1,"Rate":0.123456789012345}]')
                contract=config_dir/'contract.json'
                contract.write_text(json.dumps(dict(schema_version=1,codec='typed-json-v1',tables=[dict(name='A',path='rows.json',authoring='json',key='Id',fields=[dict(name='Id',type='int'),dict(name='Rate',type='double')])],references=[])))
                _, preflight=call('run_tool',dict(tool_id='config_preflight',arguments=['--contract',str(contract),'--output',str(work/(client+' preflight.json'))],run_dir=str(work/(client+' preflight receipt'))))
                check(preflight['status']=='ok','Bundled typed preflight failed')
                observation=work/(client+' observation.json')
                observation.write_text(json.dumps(dict(schema_version=1,candidate_sha256='a'*64,run_instance='own-fixture',frames=[dict(frame=i,phase=phase,nodes=[dict(id='label',active=True,text_length=3,mesh_vertices=12)]) for i,phase in enumerate(['cold_open','closed','reopen'])])))
                _, presentation=call('run_tool',dict(tool_id='presentation_audit',arguments=['--input',str(observation),'--output',str(work/(client+' observation-report.json'))],run_dir=str(work/(client+' observation receipt'))))
                check(presentation['status']=='ok','Bundled observation analysis failed')
                perf=work/(client+' perf.json')
                perf.write_text(json.dumps(dict(schema_version=1,candidate_sha256='b'*64,identity=dict(workload_sha256='a'*64,device='fixture',platform='mac',viewport=[540,900],quality='fixed',seed=1,input_sha256='c'*64,measurement='frame-ms-v1'),samples=[dict(frame=i,phase='steady',focused=True,valid=True,frame_ms=16) for i in range(3)],counters={})))
                _, performance=call('run_tool',dict(tool_id='performance_compare',arguments=['--before',str(perf),'--after',str(perf),'--output',str(work/(client+' performance'))],run_dir=str(work/(client+' performance receipt'))))
                check(performance['status']=='ok','Bundled performance analysis failed')
                case_project=work/(client+' revision case');case_project.mkdir()
                case_source=case_project/'source.bin';case_source.write_bytes(b'owned source')
                candidate=case_project/'candidate.txt';candidate.write_text('revision one')
                _, initialized_case=call('init_case',dict(project_dir=str(case_project),source=str(case_source),mode='fix',source_engine='unity'))
                check(initialized_case['status']=='ok','Bundled case creation failed')
                revision_args=dict(case_dir=str(case_project),candidate_root=str(case_project),candidate_files=['candidate.txt'],platform='editor',qa_profile='owned-fixture')
                _, first_revision=call('start_case_revision',revision_args)
                check(first_revision['status']=='ok','Bundled revision creation failed')
                _, case_status=call('case_status',dict(case_dir=str(case_project)))
                check(case_status['status']=='partial' and case_status['result']['candidate_integrity']=='matched'
                      and case_status['result']['declared_acceptance']=='incomplete',
                      'Bundled candidate readback must preserve the unverified state: '+json.dumps(case_status))
                candidate.write_text('revision two')
                _, stale=call('case_status',dict(case_dir=str(case_project)))
                check(stale['error']['code']=='STALE_CANDIDATE','Changed candidate retained its acceptance identity')
                _, second_revision=call('start_case_revision',revision_args)
                check(second_revision['status']=='ok','Bundled second revision failed')
                _, case_status=call('case_status',dict(case_dir=str(case_project)))
                check(case_status['result']['revision_count']==2 and case_status['result']['declared_acceptance']=='incomplete','Revision history or unverified state was lost')
                for optional in ('cocos_modules','unity_player_audit'):
                    _, unavailable=call('describe_tool',{'tool_id':optional})
                    check(unavailable['result']['availability']['state']=='unavailable','Optional provider must not leak from host: '+optional)
                response, missing = call('describe_tool', {'tool_id':'not_registered'})
                check(response['isError'] and missing['error']['code'] == 'UNKNOWN_TOOL', 'Structured error contract changed')
                _, provider = call('describe_tool', {'tool_id':'assetripper'})
                check(provider['result']['availability']['state'] != 'available', 'External provider unexpectedly leaked from host')
                results[client] = {'status':'pass', 'scope':'manifest launch configuration with independent stdio client; native host loading tested separately',
                                   'protocolVersion':initialized['protocolVersion'], 'tools':tools,
                                   'checks':['initialize','catalog_parity','session','bundled_workflow','core_subprocess',
                                             'evidence_manifest','config_preflight','presentation_audit','performance_compare','case_revision_invalidation','legacy_launch','cocos_core_subprocess','native_exit_core_subprocess','typed_config_core_subprocess','native_authoring_core_subprocess','optional_ast_cecil_missing','structured_failure','external_provider_missing']}
            finally: rpc.close()
        check(inventory(root) == before, 'Installed plugin changed during use')
        return {'status':'pass', 'target':'macos-arm64', 'version':manifest['version'],
                'archive_sha256':sha256(bundle), 'source_tree_sha256':manifest['source_tree_sha256'],
                'source_kind':manifest['source_kind'], 'clients':results,
                'isolation':{'moved_unicode_space_path':True,'independent_home':True,'minimal_path':True,
                             'source_read_denied':True,'network_denied':True,'install_write_denied':True,
                             'installation_unchanged':True},
                'limits':['Native client loading is a separate acceptance layer.', 'Unity Editor and gameplay not run.', 'Other platforms not run.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = acceptance(args.bundle)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_bytes(encoded(result))
    print(json.dumps({'status':result['status'],'target':result['target'],'clients':list(result['clients']),
                      'tools':len(result['clients']['codex']['tools'])}))
