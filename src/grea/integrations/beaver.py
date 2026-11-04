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
STABLE_VERSION = '0.6.0'
P0_VERSION = '0.5.1.dev20261028'
P0_FIX1_VERSION = '0.5.1.dev20261028+fix1'
P0_FIX2_VERSION = '0.5.1.dev20261028+fix2'
P0_FIX3_VERSION = '0.5.1.dev20261028+fix3'
P0_FIX6_VERSION = '0.5.1.dev20261028+fix6'
P0_FIX7_VERSION = '0.5.1.dev20261029+fix7'
P0_FIX8_VERSION = '0.5.1.dev20261029+fix8'
P0_FIX9_VERSION = '0.5.1.dev20261031+fix9'
P0_FIX10_VERSION = '0.5.1.dev20261031+fix10'
P0_FIX11_VERSION = '0.5.1.dev20261031+fix11'
P0_FIX12_VERSION = '0.5.1.dev20261031+fix12'
P0_FIX14_VERSION = '0.5.1.dev20261031+fix14'
P0_FIX15_VERSION = '0.5.1.dev20261031+fix15'
P0_FIX16_VERSION = '0.5.1.dev20261031+fix16'
P0_FIX17_VERSION = '0.5.1.dev20261101+fix17'
P0_FIX18_VERSION = '0.5.1.dev20261101+fix18'
P0_FIX19_VERSION = '0.5.1.dev20261101+fix19'
P0_FIX20_VERSION = '0.5.1.dev20261101+fix20'
P0_FIX21_VERSION = '0.5.1.dev20261101+fix21'
P0_RETIRE_VERSIONS = {P0_FIX21_VERSION, P0_FIX20_VERSION, P0_FIX19_VERSION, P0_FIX18_VERSION, P0_FIX17_VERSION, P0_FIX16_VERSION, P0_FIX15_VERSION, P0_FIX14_VERSION, P0_FIX12_VERSION, P0_FIX11_VERSION, P0_FIX6_VERSION, P0_FIX7_VERSION, P0_FIX8_VERSION, P0_FIX9_VERSION, P0_FIX10_VERSION}
P0_FIX22_VERSION = '0.5.1.dev20261102+fix22'
P0_FIX23_VERSION = '0.5.1.dev20261102+fix23'
P0_FIX24_VERSION = '0.5.1.dev20261102+fix24'
P0_FIX25_VERSION = '0.5.1.dev20261102+fix25'
P0_FIX26_VERSION = '0.5.1.dev20261102+fix26'
P0_FIX31_VERSION = '0.6.0.dev20261103+fix31'
P0_FIX30_VERSION = '0.6.0.dev20261103+fix30'
P0_FIX29_VERSION = '0.6.0.dev20261102+fix29'
P0_FIX28_VERSION = '0.6.0.dev20261102+fix28'
P0_FIX27_VERSION = '0.6.0.dev20261102+fix27'
VIRTUAL2_VERSION = '0.6.0.dev20261102+virtual2'
VIRTUAL4_VERSION = '0.6.0.dev20261102+virtual4'
VIRTUAL_VERSIONS = {VIRTUAL2_VERSION, VIRTUAL4_VERSION, P0_FIX27_VERSION, P0_FIX30_VERSION, P0_FIX31_VERSION}
VIRTUAL_OPERATIONS = frozenset('qa.virtual-'+name for name in ('prepare','bind','input','status','stop'))
VIRTUAL_BOOTSTRAP_OPERATIONS = frozenset({'qa.prepare','qa.launch','qa.collect'})
SCOPED_OPERATIONS = {P0_FIX31_VERSION: VIRTUAL_OPERATIONS | VIRTUAL_BOOTSTRAP_OPERATIONS,P0_FIX30_VERSION: VIRTUAL_OPERATIONS | VIRTUAL_BOOTSTRAP_OPERATIONS,P0_FIX29_VERSION: frozenset({'intake.plan','intake.apply','intake.rollback'}),P0_FIX28_VERSION: frozenset({'intake.plan','intake.apply','intake.rollback'}),P0_FIX27_VERSION: VIRTUAL_OPERATIONS | VIRTUAL_BOOTSTRAP_OPERATIONS | frozenset({'intake.plan','intake.apply','intake.rollback'}),P0_FIX22_VERSION: frozenset({'build-filter.collect'}),
                     VIRTUAL2_VERSION: VIRTUAL_OPERATIONS | VIRTUAL_BOOTSTRAP_OPERATIONS,
                     VIRTUAL4_VERSION: VIRTUAL_OPERATIONS | VIRTUAL_BOOTSTRAP_OPERATIONS,
                     P0_FIX23_VERSION: frozenset({'intake.plan','intake.apply','intake.rollback'}),
                     P0_FIX24_VERSION: frozenset({'intake.plan','intake.apply','intake.rollback'}),
                     P0_FIX25_VERSION: frozenset({'intake.plan','intake.apply','intake.rollback'}),
                     P0_FIX26_VERSION: frozenset({'intake.plan','intake.apply','intake.rollback'})}
P0_SUMMARY_VERSIONS = {*P0_RETIRE_VERSIONS, P0_FIX22_VERSION, STABLE_VERSION}
P0_VERSIONS = {P0_VERSION, P0_FIX1_VERSION, P0_FIX2_VERSION, P0_FIX3_VERSION, *P0_RETIRE_VERSIONS}
P0_GROUPS = {'structure.inspect/plan', 'build-filter.collect/plan', 'native.readback'}
# The historical name is retained; entries pin compatible lineage, never a version range.
V03_CANDIDATES = {
    STABLE_VERSION:dict(candidate='official-v0.6.0-1074816',implementation_sha256='cf372a0a11256f44d512580ab42aba5cff8f02e53f2008818235314c2b2fe76e'),
    V03_VERSION:dict(candidate='07',implementation_sha256=V03_IMPLEMENTATION),
    '0.3.0':dict(candidate='08',implementation_sha256='e6191235381d587870291b8a01ba492b4dac4b2f7faeced50590dbc1342f0882'),
    # 0.4.0 = 0.3.0 contracts plus the toolkit received from GREA; released as a GREA module.
    '0.4.0':dict(candidate='module-2026.10.27',implementation_sha256='06a710a70b8e9257e68e6e3b83a34db41e7e1f4e32b2810fe80367db518717f7'),
    P0_FIX22_VERSION:dict(candidate='local-collect-fix22-ab64214',implementation_sha256='315db9ff12497eeb026e86f22d494395dcc228384212e9d16ed907cad8fc155a'),
    P0_FIX23_VERSION:dict(candidate='local-intake-fix23-eccea05',implementation_sha256='c32043e594be592194b20f25c81b8a5624b16530dd5cb14287150ea99e4cc1ea'),
    P0_FIX24_VERSION:dict(candidate='local-reuse-fix24-3565efc',implementation_sha256='0a2594ed2370418655c1ab126d4a9a4547bc1320f94bfb9b63395476f76061b4'),
    P0_FIX25_VERSION:dict(candidate='local-font-walk-fix25-43adf74',implementation_sha256='3c3425936301e7a0c4b988b8d9405cff7a9cd61541c959cb3db76597750495ee'),
    P0_FIX31_VERSION:dict(candidate='local-ownership-fix31-ba7281d',implementation_sha256='fe3c863caf3180382f48d0e01670b1a129a6361523062924322e4443f9d29714'),
    P0_FIX30_VERSION:dict(candidate='local-takeover-diagnostic-fix30-62c400e',implementation_sha256='cc6a7800eb12bfed6b73f58333737554e50c678817cdaefb529971dae499d682'),
    P0_FIX29_VERSION:dict(candidate='local-retained-assembly-fix29-722ebf2',implementation_sha256='24d91ac09ad2c9c49453f3743757d766b4632af51d5626d6cb083258634bb23a'),
    P0_FIX28_VERSION:dict(candidate='local-engine-intake-fix28-347f106',implementation_sha256='ddc3b92126803069ce8029f01dc5fa451cd61c00beccebc94e499bcdbe850e33'),
    P0_FIX27_VERSION:dict(candidate='local-fix27-8bb6bf3',implementation_sha256='88acc905abc700070e4b7761bf97416d0eb0c09966ceec2849c3a02ff32656eb'),
    P0_FIX26_VERSION:dict(candidate='local-compiler-intake-fix26-8c26168',implementation_sha256='e62c40cf03d5be2eeba64bb11a8b4badef945df8cbe139aaea13f06323403fb3'),
    VIRTUAL4_VERSION:dict(candidate='local-virtual4-5f38f07',implementation_sha256='795c717f7fe4a4d4ffc9336eb1dea5a88d95bb66b33f0278b7fea8389c2bd5ad'),
    VIRTUAL2_VERSION:dict(candidate='local-virtual2-b8fd14f',implementation_sha256='e2c81d485ff3f5e6224ca7f5696101692660df8ea83b095592f64e5963354f57'),
    P0_FIX21_VERSION:dict(candidate='local-p0-fix21-b690d00',implementation_sha256='5be43addbe78635ed4e760bc3989bd2e148ba865260d13307316c4a7b19e689b'),
    P0_FIX20_VERSION:dict(candidate='local-p0-fix20-ec305d7',implementation_sha256='3e23e23450f16e5f9ea0073b5fc69126d88f13dc99ea169d01f44dc699ff3a28'),
    P0_FIX19_VERSION:dict(candidate='local-p0-fix19-27d21d2',implementation_sha256='3b12ef5aa779d1e95033237346ab3d9fe248d77193d9f92347f3c31042ebf72c'),
    P0_FIX18_VERSION:dict(candidate='local-p0-fix18-b5e9b03',implementation_sha256='878a710de4899861adf497f46bc56b8853c1725bcae5fec679d53008d1c2c1f2'),
    P0_FIX17_VERSION:dict(candidate='local-p0-fix17-9e587a7',implementation_sha256='912606877e9725ba1bd4dc3513b36f9dde80bb5321d7172dfc88e9533d2941af'),
    P0_FIX16_VERSION:dict(candidate='local-p0-fix16-ee13bdd',implementation_sha256='d2c25c5bbc6e21b48adae58c13801ea2edf217b35eee8a65b8a1f46b73853678'),
    P0_FIX15_VERSION:dict(candidate='local-p0-fix15-3096fde',implementation_sha256='7f32aaf491fed8a32168b1cb633b62209b350309b1e299ac1f06c9277745deb7'),
    P0_FIX14_VERSION:dict(candidate='local-p0-fix14-d4ff4c6',implementation_sha256='b657770aafa92fc98eb9fc47235e14c3ec22fc3acfe619d234ff34909d1c5a7a'),
    P0_FIX12_VERSION:dict(candidate='local-p0-fix12-61fc30b',implementation_sha256='8733083d0a3c153679282a1b77c7375744aca02042d6a184545ff62680e4c9cb'),
    P0_FIX11_VERSION:dict(candidate='local-p0-fix11-6b7e74f',implementation_sha256='44a1280aa75d7b720fa0bdfada800441e09dc76c95911ed1b00e2993725f766c'),
    P0_FIX10_VERSION:dict(candidate='local-p0-fix10-8e25793',implementation_sha256='3a64f4f5301e1ec1591df6e3ad92a8236e504cb0a9379a21e63c01f81419ed89'),
    P0_FIX9_VERSION:dict(candidate='local-p0-fix9-b85d44e',implementation_sha256='554075acb4960db076c49c60e26b39c427c37c0029aac5f2f30dc6f49cbd13eb'),
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
        if version==P0_FIX22_VERSION: required=required|{'build-filter.collect/plan'}
        if version in VIRTUAL_VERSIONS: required=required|VIRTUAL_OPERATIONS|VIRTUAL_BOOTSTRAP_OPERATIONS
        if version==P0_FIX23_VERSION:
            required=required|{'intake.plan/apply/rollback'}
            if cap.get('additiveIntakeContract')!='beaver-additive-intake/1':
                raise ValueError('Unsupported additive intake contract')
        if version in (P0_FIX24_VERSION,P0_FIX25_VERSION):
            required=required|{'intake.plan/apply/rollback'}
            versions=cap.get('additiveIntakeSpecVersions')
            if cap.get('additiveIntakeContract')!='beaver-additive-intake/2' or versions!=[1,2] or any(type(v)is not int for v in versions):
                raise ValueError('Unsupported additive intake v2 contract or spec versions')
        if version in (P0_FIX26_VERSION,P0_FIX27_VERSION):
            required=required|{'intake.plan/apply/rollback'}
            versions=cap.get('additiveIntakeSpecVersions')
            if cap.get('additiveIntakeContract')!='beaver-additive-intake/3' or versions!=[1,2,3] or any(type(v)is not int for v in versions):
                raise ValueError('Unsupported additive intake v3 contract or spec versions')
        if version==P0_FIX28_VERSION:
            required=required|{'intake.plan/apply/rollback'}
            versions=cap.get('additiveIntakeSpecVersions')
            if cap.get('additiveIntakeContract')!='beaver-additive-intake/4' or versions!=[1,2,3,4] or any(type(v)is not int for v in versions):
                raise ValueError('Unsupported additive intake v4 contract or spec versions')
        if version in (P0_FIX29_VERSION,STABLE_VERSION):
            required=required|{'intake.plan/apply/rollback'}
            versions=cap.get('additiveIntakeSpecVersions')
            if cap.get('additiveIntakeContract')!='beaver-additive-intake/5' or versions!=[1,2,3,4,5] or any(type(v)is not int for v in versions):
                raise ValueError('Unsupported additive intake v5 contract or spec versions')
        if version==STABLE_VERSION:
            required |= V05_GROUPS | P0_GROUPS | VIRTUAL_OPERATIONS | VIRTUAL_BOOTSTRAP_OPERATIONS | {'unity.assets.retire/recover','qa.inspect-instance','qa.bind','qa.input'}
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


def operation_allowed(version, operation):
    return version not in SCOPED_OPERATIONS or operation in SCOPED_OPERATIONS[version]


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
    cfg=json.loads(Path(lock).read_text())
    if not operation_allowed(cfg.get('version'), 'project.inspect'):
        result['diagnostic']='Pinned version is scoped to other operations; project.inspect is not enabled'
    elif monkey.get('ready') and beaver.get('ready'):
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
