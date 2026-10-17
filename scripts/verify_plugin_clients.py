#!/usr/bin/env python3
"""Verify a portable plugin through real clients, without starting a model turn."""
import argparse
import json
import os
from pathlib import Path
import platform
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

from plugin_bundle import encoded, sha256, verify_archive

RPC_METHODS = {'codex': {'initialize', 'initialized', 'skills/list', 'mcpServerStatus/list'},
               'claude': {'initialize', 'mcp_status'}}


def isolated_environment(root):
    """Construct, rather than filter, the child environment; never mutate os.environ."""
    root = Path(root).resolve()
    env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'LANG': 'en_US.UTF-8',
           'LC_ALL': 'en_US.UTF-8', 'TERM': 'dumb', 'NO_COLOR': '1',
           'PYTHONDONTWRITEBYTECODE': '1', 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
           'DISABLE_AUTOUPDATER': '1', 'CLAUDE_CODE_DISABLE_TERMINAL_TITLE': '1'}
    for key, directory in [('HOME','home'), ('CODEX_HOME','codex'),
                           ('CLAUDE_CONFIG_DIR','claude'), ('TMPDIR','tmp'),
                           ('XDG_CONFIG_HOME','xdg-config'), ('XDG_CACHE_HOME','xdg-cache')]:
        path = root/directory
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    if os.name=='nt':
        env.update(SystemRoot=os.environ['SystemRoot'],PATH=str(Path(os.environ['SystemRoot'])/'System32'),USERPROFILE=env['HOME'],TEMP=env['TMPDIR'],TMP=env['TMPDIR'],PYTHONUTF8='1')
    return env


def redact(value, paths=None):
    paths = paths or {}
    if isinstance(value, dict):
        return {key: '[redacted]' if re.search(r'(?:token|password|secret|api.?key|authorization)', key, re.I)
                else redact(item, paths) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, paths) for item in value]
    if not isinstance(value, str):
        return value
    for source, label in sorted(paths.items(), key=lambda item: -len(item[0])):
        value = value.replace(source, label)
    value = re.sub(r'/(?:Users|home)/[^\s"\'<>;]+', '<private-path>', value)
    value = re.sub(r'(?i)\bBearer\s+[^\s"\'<>;,]+', 'Bearer [redacted]', value)
    value = re.sub(r'(?i)((?:token|password|secret|api[_-]?key)\s*[=:]\s*)[^\s"\'<>;,]+',
                   r'\1[redacted]', value)
    value = re.sub(r'\bsk-[A-Za-z0-9_-]{12,}', '[redacted]', value)
    return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', value)


def stop_group(process):
    if os.name=='nt':
        if process.job:process.settle();process.wait(timeout=2)
        return
    # Also stop MCP descendants when the client has already exited.
    for sig, timeout in [(signal.SIGTERM, .5), (signal.SIGKILL, 2)]:
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            continue
        if sig == signal.SIGKILL:
            break
        # The leader exiting does not imply that all descendants have exited.
        time.sleep(.03)


def run_command(command, env, cwd, timeout):
    if os.name=='nt':
        from grea.host.windows_process import OwnedProcess
        process=OwnedProcess(command,cwd,env=env,text=True)
    else:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding='utf-8',start_new_session=True)
    timed_out = False
    try:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop_group(process)
            stdout, stderr = process.communicate(timeout=3)
        return {'returncode': process.returncode, 'stdout': stdout, 'stderr': stderr,
                'timed_out': timed_out}
    finally:
        stop_group(process)
        process.stdout.close()
        process.stderr.close()
        if os.name=='nt':process.close()


def rpc_message(protocol, method, identity, params):
    if method not in RPC_METHODS.get(protocol, set()):
        raise ValueError('Only initialization and discovery requests are permitted')
    if protocol == 'codex':
        value = {'method': method, 'params': params}
        if method != 'initialized':
            value['id'] = identity
        return value
    if 'subtype' in params:
        raise ValueError('Request subtype cannot be overridden')
    return {'type': 'control_request', 'request_id': str(identity),
            'request': {'subtype': method, **params}}


class JsonPeer:
    """Bounded JSON-lines client; unrelated notifications never satisfy a request."""
    def __init__(self, command, env, cwd, timeout):
        self.timeout = timeout
        self.counter = 0
        self.methods = []
        self.errors = []
        self.messages = queue.Queue(maxsize=1024)
        if os.name=='nt':
            from grea.host.windows_process import OwnedProcess
            self.process=OwnedProcess(command,cwd,env=env,interactive=True,text=True)
        else:
            self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True, encoding='utf-8',bufsize=1,start_new_session=True)
        self.closed = threading.Event()

        def stdout_reader():
            try:
                for line in self.process.stdout:
                    if len(line) > 8 * 1024 * 1024:
                        message = {'transport_error': 'Client output exceeded line limit'}
                    else:
                        try:
                            message = json.loads(line)
                        except ValueError:
                            message = {'transport_error': 'Client emitted non-JSON output: ' + line[:300]}
                    while not self.closed.is_set():
                        try:
                            self.messages.put(message, timeout=.1)
                            break
                        except queue.Full:
                            pass
            finally:
                try:
                    self.messages.put_nowait({'transport_error': 'Client exited before response'})
                except queue.Full:
                    pass

        def stderr_reader():
            for line in self.process.stderr:
                self.errors.append(line[-2000:])
                del self.errors[:-50]

        self.readers = [threading.Thread(target=stdout_reader, daemon=True),
                        threading.Thread(target=stderr_reader, daemon=True)]
        for reader in self.readers:
            reader.start()

    def request(self, protocol, method, params, timeout=None):
        self.counter += 1
        identity = self.counter
        message = rpc_message(protocol, method, identity, params)
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()
        self.methods.append(method)
        if method == 'initialized':
            return {}
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        while time.monotonic() < deadline:
            try:
                value = self.messages.get(timeout=max(.01, deadline-time.monotonic()))
            except queue.Empty:
                break
            if 'transport_error' in value:
                raise RuntimeError(value['transport_error'] + ': ' + ''.join(self.errors)[-1800:])
            if protocol == 'codex' and value.get('id') == identity:
                if 'error' in value:
                    raise RuntimeError('Codex RPC error: ' + json.dumps(value['error']))
                return value.get('result', {})
            if protocol == 'claude' and value.get('type') == 'control_response':
                response = value.get('response', {})
                if response.get('request_id') != str(identity):
                    continue
                if response.get('subtype') != 'success':
                    raise RuntimeError('Claude control error: ' + str(response.get('error')))
                return response.get('response', {})
        raise TimeoutError(method + ' timed out: ' + ''.join(self.errors)[-1800:])

    def close(self):
        self.closed.set()
        if not self.process.stdin.closed:
            self.process.stdin.close()
        stop_group(self.process)
        for reader in self.readers:
            reader.join(timeout=2)
        self.process.stdout.close()
        self.process.stderr.close()
        if os.name=='nt':self.process.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def check_tools(names, expected, client):
    names = sorted(set(names))
    canonical = {name.rsplit('__', 1)[-1] for name in names}
    if canonical != set(expected) or len(names) != len(expected):
        raise ValueError(client + ' tool inventory differs: missing=' + str(sorted(set(expected)-canonical))
                         + ', unexpected=' + str(sorted(canonical-set(expected))))
    return names


def check_skills(items, expected, cache=None):
    wanted = {'grea:' + name for name in expected}
    found = sorted(item['name'] for item in items
                   if item.get('name') in wanted and item.get('enabled', True)
                   and (cache is None or Path(item.get('path', '/')).is_relative_to(cache)))
    if set(found) != wanted or len(found) != len(wanted):
        observed = [{key:item.get(key) for key in ('name','path','enabled')} for item in items]
        raise ValueError('Client did not discover every enabled bundled skill from its installed copy: '
                         + str({'matched':found, 'observed':observed}))
    return found


def native_client(name, explicit=None):
    path = Path(explicit) if explicit else Path(shutil.which(name) or '/nonexistent-client')
    path = path.expanduser().resolve()
    if name == 'codex' and path.suffix == '.js':
        candidates = sorted(path.parent.parent.glob('node_modules/@openai/codex-*/vendor/*/bin/codex'))
        target = {'arm64': 'aarch64', 'x86_64': 'x86_64'}.get(platform.machine(), platform.machine())
        candidates = [item for item in candidates if target in str(item)]
        if len(candidates) == 1:
            path = candidates[0]
    if not path.is_file() or not os.access(path, os.X_OK):
        raise FileNotFoundError(name + ' native executable is unavailable; use --' + name + '-bin')
    with path.open('rb') as stream:
        if stream.read(2) == b'#!':
            raise ValueError(name + ' requires a native binary for minimal-PATH acceptance')
    return path


def layer(client, name, status, **details):
    client['layers'][name] = {'status': status, **details}
    print(client['name'] + '.' + name + ': ' + status, file=sys.stderr, flush=True)


def checked_command(command, env, cwd, timeout):
    result = run_command(command, env, cwd, timeout)
    if result['timed_out'] or result['returncode'] != 0:
        raise RuntimeError(('Command timed out' if result['timed_out'] else
                            'Command exited ' + str(result['returncode'])) + ': ' +
                           (result['stderr'] + '\n' + result['stdout'])[-2400:])
    return result['stdout']


def server_tools(server):
    tools = server.get('tools', {})
    if isinstance(tools, dict):
        return [value.get('name', key) if isinstance(value, dict) else key for key, value in tools.items()]
    return [value['name'] for value in tools if isinstance(value, dict) and 'name' in value]


def marketplace_plan(bundle_root, base, client):
    relative = '.agents/plugins/marketplace.json' if client == 'codex' else '.claude-plugin/marketplace.json'
    delivered = bundle_root/relative
    if delivered.is_file():
        data = json.loads(delivered.read_text(encoding='utf-8'))
        plugins = [item for item in data.get('plugins', []) if item.get('name') == 'grea']
        expected_source = {'source':'local', 'path':'./'} if client == 'codex' else './'
        if data.get('name') != 'grea-local' or len(plugins) != 1 or plugins[0].get('source') != expected_source:
            raise ValueError('Bundled marketplace must install grea@grea-local from its own root')
        return {'origin':'bundled', 'directory':bundle_root, 'plugin_id':'grea@grea-local',
                'name':'grea-local', 'add_source':'.' if client == 'codex' else './'}
    # Compatibility for older preview artifacts; this does not pass the delivered-entrypoint gate.
    directory = base/'catalog'
    source = './' + bundle_root.relative_to(directory).as_posix()
    entry = {'name':'grea', 'source':source}
    data = {'name':'grea-audit', 'plugins':[entry]}
    if client == 'codex':
        entry.update(source={'source':'local', 'path':source},
                     policy={'installation':'AVAILABLE', 'authentication':'ON_USE'}, category='Developer Tools')
    else:
        data['owner'] = {'name':'grea acceptance fixture'}
    fixture = directory/relative
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_bytes(encoded(data))
    return {'origin':'temporary_fixture', 'directory':directory, 'plugin_id':'grea@grea-audit',
            'name':'grea-audit', 'add_source':'.' if client == 'codex' else './'}


def validate_claude_manifests(command, bundle_root, marketplace_root, env, work, timeout):
    # A directory target prefers marketplace.json and can silently leave plugin.json unchecked.
    checks = {}
    for kind, root in [('plugin', bundle_root), ('marketplace', marketplace_root)]:
        path = root/'.claude-plugin'/(kind + '.json')
        try:
            output = checked_command([*command, 'plugin', 'validate', str(path), '--strict', '--json'],
                                     env, work, timeout)
            value = json.loads(output)
            manifest = value.get('manifest') if isinstance(value, dict) else None
            if not isinstance(manifest, dict) or value.get('success') is not True or manifest.get('type') != kind:
                raise ValueError('Claude validator did not confirm the requested ' + kind + ' manifest')
            checks[kind] = {'status':'pass', 'target':'.claude-plugin/' + kind + '.json'}
        except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
            checks[kind] = {'status':'blocked', 'target':'.claude-plugin/' + kind + '.json', 'reason':str(exc)}
    return checks


def client_acceptance(name, binary, bundle_root, base, expected_skills, expected_tools, timeout, offline):
    client = {'name': name, 'version': None, 'layers': {}, 'skills': [], 'tools': [], 'protocol_requests': []}
    phases = ['version', 'entrypoint', *(['manifest'] if name == 'claude' else []),
              'install', 'registration', *(['connection'] if name == 'claude' else []),
              'initialize', 'skills', 'tools']
    for phase in phases:
        client['layers'][phase] = {'status': 'not_run', 'reason': 'Earlier prerequisite has not passed'}
    phase = 'version'
    try:
        binary = native_client(name, binary)
        env = isolated_environment(base/name)
        work = base/name/'空白 workspace'
        work.mkdir()
        prefix = []
        if offline:
            if platform.system() != 'Darwin' or not Path('/usr/bin/sandbox-exec').is_file():
                raise RuntimeError('Network isolation requires macOS sandbox-exec; use --allow-network explicitly')
            prefix = ['/usr/bin/sandbox-exec', '-p', '(version 1)(allow default)(deny network*)']
        command = [*prefix, str(binary)]
        client['version'] = checked_command([*command, '--version'], env, work, timeout).strip()
        layer(client, phase, 'pass')
        phase = 'entrypoint'
        plan = marketplace_plan(bundle_root, base, name)
        client['catalog_origin'] = plan['origin']
        layer(client, phase, 'pass' if plan['origin'] == 'bundled' else 'not_run',
              reason='Uses the delivered marketplace' if plan['origin'] == 'bundled' else
                     'Legacy bundle has no marketplace; temporary fixture proves client loading only')
        if name == 'codex':
            config = Path(env['CODEX_HOME'])/'config.toml'
            config.write_text('cli_auth_credentials_store = "file"\n'
                              '[features]\nplugins = true\n[analytics]\nenabled = false\n' +
                              ''.join('[projects.' + json.dumps(str(path)) + ']\ntrust_level = "trusted"\n'
                                      for path in (work, plan['directory'])), encoding='utf-8')
            phase = 'install'
            checked_command([*command, 'plugin', 'marketplace', 'add', plan['add_source'], '--json'],
                            env, plan['directory'], timeout)
            checked_command([*command, 'plugin', 'add', plan['plugin_id'], '--json'], env, plan['directory'], timeout)
            layer(client, phase, 'pass')
            phase = 'registration'
            listing = json.loads(checked_command([*command, 'plugin', 'list', '--marketplace', plan['name'], '--json'],
                                                  env, work, timeout))
            installed = [item for item in listing.get('installed', []) if item.get('pluginId') == plan['plugin_id']
                         and item.get('installed') is True and item.get('enabled') is True]
            if len(installed) != 1:
                raise ValueError('Installed grea plugin missing from client listing')
            layer(client, phase, 'pass', scope='Client installation readback; tool discovery checked separately',
                  observed=listing)
            phase = 'initialize'
            with JsonPeer([*command, 'app-server', '--stdio'], env, work, timeout) as peer:
                client['protocol_requests'] = peer.methods
                peer.request(name, 'initialize', {'clientInfo': {'name':'grea_audit', 'version':'1'},
                                                 'capabilities': {'experimentalApi':True}})
                peer.request(name, 'initialized', {})
                layer(client, phase, 'pass')
                phase = 'skills'
                values = peer.request(name, 'skills/list', {'cwds':[str(work)], 'forceReload':True})
                cache = Path(env['CODEX_HOME'])/'plugins/cache'
                items = [skill for row in values.get('data', []) for skill in row.get('skills', [])]
                found = check_skills(items, expected_skills, cache)
                client['skills'] = found
                layer(client, phase, 'pass', count=len(found), source='isolated installed plugin cache')
                phase = 'tools'
                servers = []
                cursor = None
                for _ in range(100):
                    values = peer.request(name, 'mcpServerStatus/list', {'limit':100, 'cursor':cursor})
                    servers.extend(values.get('data', []))
                    cursor = values.get('nextCursor')
                    if not cursor:
                        break
                else:
                    raise ValueError('MCP status pagination did not terminate')
                candidates = [item for item in servers if 'grea' in item.get('name', '').lower()]
                if len(candidates) != 1:
                    raise ValueError('Expected one grea server, observed ' + str([s.get('name') for s in servers]))
                client['tools'] = check_tools(server_tools(candidates[0]), expected_tools, name)
                layer(client, phase, 'pass', count=len(client['tools']))
        else:
            phase = 'manifest'
            checks = validate_claude_manifests(command, bundle_root, plan['directory'], env, work, timeout)
            manifest_status = 'pass' if all(item['status'] == 'pass' for item in checks.values()) else 'blocked'
            layer(client, phase, manifest_status, checks=checks)
            if manifest_status != 'pass':
                client['status'] = 'blocked'
                return client
            phase = 'install'
            checked_command([*command, 'plugin', 'marketplace', 'add', plan['add_source'], '--json'],
                            env, plan['directory'], timeout)
            checked_command([*command, 'plugin', 'install', plan['plugin_id'], '--json'], env, plan['directory'], timeout)
            layer(client, phase, 'pass')
            phase = 'registration'
            listing = json.loads(checked_command([*command, 'plugin', 'list', '--json'], env, work, timeout))
            cache = Path(env['CLAUDE_CONFIG_DIR'])/'plugins/cache'
            installed = [item for item in listing if item.get('id') == plan['plugin_id'] and item.get('enabled') is True
                         and Path(item.get('installPath', '/')).is_relative_to(cache)]
            if len(installed) != 1:
                raise ValueError('Enabled grea plugin missing from isolated Claude installation readback')
            layer(client, phase, 'pass', observed=installed)
            # Only the isolated user settings carry the just-installed plugin. No --plugin-dir override.
            common = [*command, '--setting-sources', 'user', '--settings', '{"disableAllHooks":true}']
            phase = 'connection'
            text = checked_command([*common, 'mcp', 'list'], env, work, timeout)
            if not any('grea' in line.lower() and re.search(r'\bconnected\b', line, re.I) for line in text.splitlines()):
                raise ValueError('Claude MCP health check did not report grea connected: ' + text[-1800:])
            layer(client, phase, 'pass', scope='Real Claude plugin loader and MCP connection health')
            phase = 'initialize'
            with JsonPeer([*common, '-p', '--verbose', '--input-format', 'stream-json',
                           '--output-format', 'stream-json', '--no-session-persistence'], env, work, timeout) as peer:
                client['protocol_requests'] = peer.methods
                values = peer.request(name, 'initialize', {})
                layer(client, phase, 'pass')
                phase = 'skills'
                found = check_skills(values.get('commands', []), expected_skills)
                client['skills'] = found
                layer(client, phase, 'pass', count=len(found))
                phase = 'tools'
                deadline = time.monotonic() + timeout
                while True:
                    values = peer.request(name, 'mcp_status', {}, timeout=max(.1, deadline-time.monotonic()))
                    candidates = [item for item in values.get('mcpServers', []) if 'grea' in item.get('name', '').lower()]
                    if len(candidates) == 1 and candidates[0].get('status') == 'connected' and server_tools(candidates[0]):
                        break
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Claude MCP discovery timed out: ' + str(values))
                    time.sleep(.2)
                client['tools'] = check_tools(server_tools(candidates[0]), expected_tools, name)
                layer(client, phase, 'pass', count=len(client['tools']))
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        layer(client, phase, 'not_run' if isinstance(exc, FileNotFoundError) else 'blocked', reason=str(exc))
    client['status'] = 'pass' if all(item['status'] == 'pass' for item in client['layers'].values()) else 'blocked'
    return client


def acceptance(bundle, codex_bin=None, claude_bin=None, timeout=45, offline=True, clients=('codex','claude')):
    bundle = Path(bundle).resolve()
    result = {'schema_version':1, 'status':'blocked', 'archive_sha256':sha256(bundle), 'clients':{},
              'isolation': {'independent_child_configuration':True, 'credential_environment_inherited':False,
                            'network_denied':offline, 'unicode_space_path':True},
              'model_requests_sent':0, 'limits':['Client loading and discovery only; no model inference or business tools called.',
                                               'Unity Editor, gameplay, and other platforms not tested.']}
    with tempfile.TemporaryDirectory(prefix='grea 客户端 audit ', dir=None if os.name=='nt' else '/private/tmp') as tmp:
        base = Path(tmp).resolve()
        try:
            manifest = verify_archive(bundle, base/'catalog/plugins')
            bundle_root = base/'catalog/plugins/grea'
            result['version'] = manifest.get('version')
            result['source_tree_sha256'] = manifest.get('source_tree_sha256')
            result['archive'] = {'status':'pass'}
            skills = set()
            for path in sorted((bundle_root/'plugin/skills').glob('*/SKILL.md')):
                match = re.search(r'^name:\s*["\']?([^\n"\']+)', path.read_text(encoding='utf-8'), re.M)
                if match:
                    skills.add(match.group(1).strip())
            operations = json.loads((bundle_root/'schemas/operations.json').read_text(encoding='utf-8'))['operations']
            tools = {item['name'] for item in operations}
            if not skills or not tools:
                raise ValueError('Bundle expected skill/tool inventory is empty')
            result['expected'] = {'skills':sorted(skills), 'tools':sorted(tools)}
            for name, binary in [('codex',codex_bin), ('claude',claude_bin)]:
                if name not in clients:continue
                result['clients'][name] = client_acceptance(name, binary, bundle_root, base, skills, tools, timeout, offline)
            result['status'] = 'pass' if all(item['status'] == 'pass' for item in result['clients'].values()) else 'blocked'
        except (OSError, ValueError, RuntimeError) as exc:
            result['archive'] = {'status':'blocked', 'reason':str(exc)}
        result = redact(result, {str(base):'<audit>', str(Path.home()):'<user-home>', str(bundle.parent):'<bundle-directory>'})
    result['temporary_directory_removed'] = not base.exists()
    if not result['temporary_directory_removed']:
        result['status'] = 'blocked'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--codex-bin', type=Path)
    parser.add_argument('--claude-bin', type=Path)
    parser.add_argument('--client',action='append',choices=('codex','claude'),help='Only install/verify the explicitly selected client in temporary configuration')
    parser.add_argument('--timeout', type=float, default=45, help='Bound each command or discovery phase in seconds')
    parser.add_argument('--allow-network', action='store_true', help='Explicitly omit the macOS network-denial sandbox')
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 300:
        parser.error('--timeout must be between 0 and 300 seconds')
    try:
        report = acceptance(args.bundle, args.codex_bin, args.claude_bin, args.timeout, not args.allow_network,tuple(args.client or ('codex','claude')))
    except Exception as exc:
        report = {'schema_version':1, 'status':'blocked',
                  'reason':redact(type(exc).__name__ + ': ' + str(exc), {str(Path.home()):'<user-home>'}),
                  'model_requests_sent':0}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_bytes(encoded(report))
    print(json.dumps({'status':report['status'], 'clients':{name:{'status':item['status'],
        'skills':len(item['skills']), 'tools':len(item['tools'])} for name,item in report.get('clients',{}).items()},
        'model_requests_sent':0}))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
