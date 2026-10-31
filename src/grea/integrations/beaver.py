"""Thin local discovery and immutable identity binding; no engineering implementation."""
import json
import os
import shutil
import subprocess
from pathlib import Path
from grea.common import GreaError, digest, hash_file, write_new
from grea.safe_paths import disjoint

V03_VERSION = '0.3.0.dev1'
V03_IMPLEMENTATION = 'b6400dbd7ca13426ce68a2c4034fb647795e3876d38b26c98d2a98e4ee8bc3c0'
V05_VERSION = '0.5.0'
P0_VERSION = '0.5.1.dev20261028'
P0_FIX1_VERSION = '0.5.1.dev20261028+fix1'
P0_FIX2_VERSION = '0.5.1.dev20261028+fix2'
P0_FIX3_VERSION = '0.5.1.dev20261028+fix3'
P0_FIX6_VERSION = '0.5.1.dev20261028+fix6'
P0_FIX7_VERSION = '0.5.1.dev20261029+fix7'
P0_FIX8_VERSION = '0.5.1.dev20261029+fix8'
P0_RETIRE_VERSIONS = {P0_FIX6_VERSION, P0_FIX7_VERSION, P0_FIX8_VERSION}
P0_VERSIONS = {P0_VERSION, P0_FIX1_VERSION, P0_FIX2_VERSION, P0_FIX3_VERSION, *P0_RETIRE_VERSIONS}
P0_GROUPS = {'structure.inspect/plan', 'build-filter.collect/plan', 'native.readback'}
# The historical name is retained; entries pin compatible lineage, never a version range.
V03_CANDIDATES = {
    V03_VERSION:dict(candidate='07',implementation_sha256=V03_IMPLEMENTATION),
    '0.3.0':dict(candidate='08',implementation_sha256='e6191235381d587870291b8a01ba492b4dac4b2f7faeced50590dbc1342f0882'),
    # 0.4.0 = 0.3.0 contracts plus the toolkit received from GREA; released as a GREA module.
    '0.4.0':dict(candidate='module-2026.10.27',implementation_sha256='06a710a70b8e9257e68e6e3b83a34db41e7e1f4e32b2810fe80367db518717f7'),
    P0_FIX8_VERSION:dict(candidate='local-p0-fix8-1b44c0b',implementation_sha256='6e81b67b87a3b5fd4d965dbe952672ca99c9e4149a678863c39f3706165211f3'),
    P0_FIX7_VERSION:dict(candidate='local-p0-fix7-5b765eb',implementation_sha256='b889a59214782d6bcc442a53156150d9729a24d18a2e9349f468e85dcba5725c'),
    P0_FIX6_VERSION:dict(candidate='local-p0-fix6-c1d80d9',implementation_sha256='8e5d595c15c63c222fcc7ece0013ddd97ef3360d8331d76eb4befc61a6fcafc6'),
    P0_FIX3_VERSION:dict(candidate='local-p0-fix3-c62245e',implementation_sha256='978da3ca18b348b5bd2c5534f8c1b4570d2d6bfa8fb066f5a007507c59becf67'),
    P0_FIX2_VERSION:dict(candidate='local-p0-fix2-34ce66e',implementation_sha256='8fa8f6700df4d805792d3decb6f9832f10d62598dc713ab788b7181a89b1e4ad'),
    P0_FIX1_VERSION:dict(candidate='local-p0-fix1-8285fd9',implementation_sha256='d683fbc09e168b423dbf62f11a90269b3238f3c00b3de14229fae2bc29fafc56'),
    P0_VERSION:dict(candidate='local-p0-914adff',implementation_sha256='f9bc89c74cda41b173ed4d20fc4c3f9425950836f580a8b3f491be87fd8abfd3'),
    V05_VERSION:dict(candidate='official-v0.5.0-e0c7e0c',implementation_sha256='bee1d06780155a50735d9e836041cd967a3da0bc2dbe368d1d55cb2cd8700e90'),
}
SUPPORTED_VERSIONS = ('0.1.0', '0.1.0.dev1', '0.2.0', *V03_CANDIDATES)
V02_CONTRACTS = dict(nativeOperationContract='beaver-unity/1', adoptionContract='beaver-adopt/1',
                     batchOperationContract='beaver-batch/2', batchTransactionContract='beaver-batch-transaction/2')
V02_OPERATIONS = {'batch.plan','batch.apply','batch.recover','references',
                  'debug.start','debug.inspect','debug.stop','debug.tail','debug.screenshot','debug.target'}
V03_CONTRACTS = dict(V02_CONTRACTS, productionOperationContract='beaver-production/3',
                     productionTransactionContract='beaver-production-transaction/3',projectProfileContract='beaver-project/1')
V03_GROUPS = {
    'workspace.plan/apply/inspect/rebind', 'production.plan/apply/recover',
    'config3.validate/generate/compare', 'csharp.inspect/rename/rename-sequence', 'csharp.module',
    'resource.image-inspect/image-produce/validate-step',
    'server.generate/module-generate/module-plan/protocol-diff/migration-plan',
    'server.toolchain/protocol-tools/check/build',
    'server.compose-plan/migration-state/migration-apply/runtime-inspect',
}
V05_GROUPS = {'ui.inspect/analyze/repair-plan', 'wiring.plan', 'diagnostics.summarize', 'toolkit.grea'}


def validate_capabilities(cap):
    version=cap.get('version')
    if version not in SUPPORTED_VERSIONS: raise ValueError('Unsupported beaver version: '+str(version))
    if version in ('0.2.0',*V03_CANDIDATES):
        contracts=V03_CONTRACTS if version in V03_CANDIDATES else V02_CONTRACTS
        if any(cap.get(k)!=v for k,v in contracts.items()):
            raise ValueError('Unsupported beaver operation/transaction contracts for '+version)
        rows=cap.get('capabilities',[])
        if any(not isinstance(row,dict) or not isinstance(row.get('id'),str) or row.get('state') not in
               ('implemented','requires_provider','not_supported') for row in rows):
            raise ValueError('Invalid beaver capability declaration')
        ids=[row['id'] for row in rows]
        required=V02_OPERATIONS | V03_GROUPS if version in V03_CANDIDATES else V02_OPERATIONS
        if version in {V05_VERSION} | P0_VERSIONS: required = required | V05_GROUPS
        if version in P0_VERSIONS: required = required | P0_GROUPS
        if version in P0_RETIRE_VERSIONS: required = required | {'unity.assets.retire/recover'}
        if len(ids)!=len(set(ids)) or not required<=set(ids):
            raise ValueError('Missing or duplicated beaver capabilities')
        if version in V03_CANDIDATES and cap.get('producer_implementation_sha256')!=V03_CANDIDATES[version]['implementation_sha256']:
            raise ValueError('Only the fixed beaver '+V03_CANDIDATES[version]['candidate']+' implementation is supported')


def state_root():
    configured_root = os.environ.get('GREA_PROVIDER_STATE_DIR')
    root = Path(configured_root) if configured_root is not None else Path.home()/'.local/share/grea/providers'
    return root.expanduser().absolute()/'beaver'


def discover():
    """Presence only. Never spawn, install, bind, or silently change a stale binding."""
    binding = state_root()/'binding.json'
    if binding.exists():
        try:
            value = json.loads(binding.read_text())
            if value['schema_version'] != 1 or not isinstance(value['command'], list) or not value['command'] or not all(isinstance(x,str) and x for x in value['command']):
                raise ValueError('Invalid binding')
            return dict(status='bound', **{k:value[k] for k in ('command','lock','version')})
        except (ValueError, KeyError, TypeError, OSError) as error:
            return dict(status='invalid_binding', reason=str(error))
    candidates = []
    paths = [Path.home()/'.local/bin/beaver', Path.home()/'.local/share/beaver/current/bin/beaver']
    from grea.modules import installed_launchers
    paths += installed_launchers('beaver', state_root().parent)
    found = shutil.which('beaver')
    if found: paths.append(Path(found))
    for p in paths:
        if p.is_file() and os.access(p, os.X_OK) and str(p.resolve()) not in candidates:
            candidates.append(str(p.resolve()))
    if len(candidates) != 1:
        return dict(status='not_installed' if not candidates else 'ambiguous', candidates=candidates)
    return dict(status='discovered', command=[candidates[0]], candidates=candidates)


def provider_override():
    value = discover()
    if value['status'] == 'not_installed': return None
    command = value.get('command', [str(state_root()/'unavailable')])
    import platform
    return dict(command=command, probe=command+['capabilities'], systems=[platform.system()])


def package_identity(root):
    root = Path(root).absolute()
    if root.is_symlink() or not (root/'__init__.py').is_file():
        raise ValueError('An explicit beaver package identity root is required')
    result = {}; total = 0
    for parent, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__')
        if any((Path(parent)/d).is_symlink() for d in dirs): raise ValueError('Linked package directory')
        for name in sorted(names):
            if name.endswith(('.pyc','.pyo')): continue
            p = Path(parent)/name
            row = hash_file(p, 32*1024**2); total += row['bytes']
            if total > 128*1024**2 or len(result) >= 10000: raise ValueError('Identity budget exceeded')
            result[str(p)] = row['sha256']
    return result


def command_identity(command):
    result = {}
    for arg in command:
        p = Path(arg)
        if p.is_absolute() and p.is_file():
            actual = p.resolve(); result[str(actual)] = hash_file(actual,128*1024**2)['sha256']
    if not result: raise ValueError('Provider command has no hashable executable identity')
    # Pin the interpreter of a console launcher too, including its venv spelling.
    try: header = Path(command[0]).open('rb').readline(4096).decode('utf-8').strip()
    except UnicodeDecodeError: header = ''
    if header.startswith('#!'):
        interpreter = Path(header[2:])
        if not interpreter.is_absolute() or not interpreter.is_file(): raise ValueError('Explicit interpreter required')
        result[str(interpreter)] = hash_file(interpreter.resolve(),128*1024**2)['sha256']
    return result


def imported_package(command):
    """Prove which beaver package a standard Python console launcher imports."""
    if len(command) != 1: raise ValueError('Pin a single isolated beaver console launcher, not arbitrary argv')
    launcher=Path(command[0]).resolve(strict=True)
    header=launcher.open('rb').readline(4096).decode('utf-8').strip()
    if not header.startswith('#!'): raise ValueError('Expected an isolated Python beaver console launcher')
    interpreter=Path(header[2:])
    if not interpreter.is_absolute() or not interpreter.is_file(): raise ValueError('Expected an absolute Python interpreter')
    code='import json,beaver;from pathlib import Path;print(json.dumps({"package_root":str(Path(beaver.__file__).resolve().parent)}))'
    probe=subprocess.run([str(interpreter),'-I','-B','-c',code],capture_output=True,text=True,timeout=20)
    if probe.returncode or len(probe.stdout)>16384: raise ValueError('Cannot inspect actual beaver package')
    return Path(json.loads(probe.stdout)['package_root']).resolve(strict=True)


def capability_probe(output):
    from grea import registry, runner
    entry = registry.tool('beaver'); command = registry.command(entry)
    if registry.command(entry,probe=True) != command+['capabilities']:
        raise ValueError('Capabilities must come from the actual beaver command')
    receipt, _, error = runner.execute('beaver', [], output, probe=True, timeout_seconds=20,
                                      max_output_bytes=1024**2, max_inline_bytes=1024**2)
    response = receipt.get('parsed_stdout')
    if error or not receipt.get('capture_complete') or not isinstance(response,dict) or response.get('contract')!='beaver-result/1' or response.get('status')!='ok':
        raise ValueError('beaver capability result failed or is incomplete')
    producer=response.get('producer',{}); data=response.get('data',{})
    if producer.get('name')!='beaver' or data.get('contract')!='beaver-capabilities/1' or not isinstance(data.get('capabilities'),list):
        raise ValueError('Unsupported beaver capability contract')
    cap=dict(data,version=producer.get('version'))
    if cap['version'] in V03_CANDIDATES:
        from grea.beaver_contracts import validate_result
        validate_result(response)
        cap['producer_implementation_sha256']=producer.get('implementationSha256')
    if not isinstance(cap.get('version'),str):
        raise ValueError('beaver capability probe failed or is incomplete')
    validate_capabilities(cap)
    return command, cap


def check(output, lock=None, identity_root=None, pin=False):
    """Explicit probe/pin. A lock covers supplied package bytes and the capability response."""
    roots = [state_root()]
    if lock: roots.append(lock)
    if identity_root: roots.append(identity_root)
    out = disjoint(output,*roots)
    if out.exists() or not out.parent.is_dir(): raise ValueError('Use a fresh receipt directory')
    out.mkdir()
    result = dict(status='needs_action', ready=False, provider='beaver', executed=False,
                  native='not_run', gameplay='not_run', limitations=['Readiness is not an engineering operation or native acceptance.'])
    try:
        if lock is None and not pin:
            found = discover()
            lock = found.get('lock')
        cfg = json.loads(Path(lock).read_text()) if lock else None
        if cfg:
            if cfg.get('schema_version') != 1 or cfg.get('provider') != 'beaver': raise ValueError('Invalid beaver lock')
            if package_identity(cfg['identity_root']) != cfg['package_files']: raise ValueError('Provider package drift')
            from grea import registry
            if registry.command(registry.tool('beaver')) != cfg['command']: raise ValueError('Provider launcher drift')
            if imported_package(cfg['command']) != Path(cfg['identity_root']).resolve(): raise ValueError('Provider imported package drift')
            if command_identity(cfg['command']) != cfg['command_files']: raise ValueError('Provider command drift')
        command, cap = capability_probe(out/'probe')
        result.update(version=cap['version'], capabilities_sha256=digest(cap), capability_probe='passed')
        if cfg and cfg['version'] != cap['version']: raise ValueError('Provider version differs from lock')
        if cfg and digest(cap) != cfg['capabilities_sha256']: raise ValueError('Provider capability drift')
        if pin:
            if not identity_root: raise ValueError('pin requires --identity-root; development source must be explicit')
            if imported_package(command) != Path(identity_root).resolve(): raise ValueError('Identity root is not the actually imported beaver package')
            cfg = dict(schema_version=1,provider='beaver',version=cap['version'],command=command,
                       command_files=command_identity(command),identity_root=str(Path(identity_root).absolute()),
                       package_files=package_identity(identity_root),capabilities_sha256=digest(cap),
                       provenance='explicit-local-binding-not-published-acceptance')
            write_new(out/'beaver-lock.json',cfg)
            result['lock'] = str(out/'beaver-lock.json')
        if cfg:
            result.update(status='ok',ready=True,locked=True)
        else:
            result.update(diagnostic='unbound_provider',next_action='Pin an explicit installed or development package identity before engineering execution.')
    except (ValueError,OSError,KeyError,TypeError,GreaError,subprocess.SubprocessError) as error:
        result.update(status='needs_action',ready=False,diagnostic=str(error))
    write_new(out/'result.json',result)
    return result


def inspect_project(lock, project, output):
    """One typed read-only engineering call, matching beaver-result/1; no raw argv."""
    from grea import runner
    from grea.integrations.monkey.local import readiness, state_root as monkey_state
    out=disjoint(output,lock,project,state_root(),monkey_state())
    if out.exists() or not out.parent.is_dir(): raise ValueError('Use a fresh inspect receipt directory')
    out.mkdir()
    monkey=readiness(out/'monkey-check')
    beaver=check(out/'beaver-check',lock=lock)
    result=dict(status='needs_action',executed=False,operation='project.inspect',providers={'monkey':monkey,'beaver':beaver},native='not_run',gameplay='not_run')
    if monkey.get('ready') and beaver.get('ready'):
        # Use the complete parsed capture in runner receipt, not a guessed capability.
        receipt=json.loads((out/'beaver-check/probe/run.json').read_text())
        response=receipt.get('parsed_stdout',{})
        declarations=response.get('data',{}).get('capabilities',[])
        if not any(row.get('id')=='project.inspect' and row.get('state')=='implemented' for row in declarations if isinstance(row,dict)):
            result['diagnostic']='beaver project.inspect not implemented in pinned capabilities'
        else:
            cfg=json.loads(Path(lock).read_text())
            invocation,_,error=runner.execute('beaver',['project','inspect','--project',str(Path(project).resolve(strict=True))],out/'inspect',timeout_seconds=30,max_output_bytes=1024**2,max_inline_bytes=1024**2)
            actual=invocation.get('parsed_stdout')
            result['executed']=True
            if package_identity(cfg['identity_root'])!=cfg['package_files'] or command_identity(cfg['command'])!=cfg['command_files']:
                result['diagnostic']='Provider implementation drift during operation'
            elif error or not invocation.get('capture_complete') or not isinstance(actual,dict) or actual.get('contract')!='beaver-result/1' or actual.get('producer',{}).get('name')!='beaver' or actual.get('producer',{}).get('version')!=cfg['version']:
                result['diagnostic']='beaver project.inspect failed or returned an unsupported/incomplete result'
            else:
                if cfg['version'] in V03_CANDIDATES:
                    from grea.beaver_contracts import validate_result
                    try:
                        validate_result(actual)
                        if actual['producer']['implementationSha256']!=V03_CANDIDATES[cfg['version']]['implementation_sha256']:
                            raise ValueError('Unsupported fixed candidate implementation')
                    except ValueError as error:
                        result.update(diagnostic=str(error),provider_result=actual)
                    else:result.update(status=actual['status'],provider_result=actual)
                else:result.update(status=actual.get('status','failed'),provider_result=actual)
    write_new(out/'result.json',result)
    return result
