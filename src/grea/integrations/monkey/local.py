"""Read-only local discovery and explicit, persistent monkey readiness binding."""
import json,os,shutil,subprocess,sys,uuid
from pathlib import Path
from contextlib import contextmanager
from grea.common import GreaError,hash_file,write_new
from grea.safe_paths import canonical_path,disjoint


def state_root():
    configured_root = os.environ.get('GREA_PROVIDER_STATE_DIR')
    root = Path(configured_root) if configured_root is not None else Path.home()/'.local/share/grea/providers'
    return root.expanduser().absolute()/'monkey'


def binding():
    path=state_root()/'binding.json'
    if not path.exists():return None
    from .identity import read
    value=read(path)
    if value.get('schema_version')!=1 or not isinstance(value.get('command'),list) or not value['command'] or not all(isinstance(x,str)and x for x in value['command']):
        raise ValueError('Invalid monkey binding; run readiness to diagnose, do not silently select another installation')
    return value


def discover():
    """No subprocess, installation, network or writes. A binding has priority over PATH."""
    try:bound=binding()
    except (ValueError,OSError,GreaError) as error:return dict(status='invalid_binding',reason=str(error),candidates=[])
    if bound:
        executable=Path(bound['command'][0])
        return dict(status='bound' if executable.is_file() and os.access(executable,os.X_OK) else 'bound_missing',command=bound['command'],lock=bound.get('lock'),version=bound.get('version'),candidates=[str(executable)])
    names=[Path.home()/'.local/bin/monkey',Path.home()/'.local/share/monkey/current/bin/monkey']
    installed=state_root()/'installed.json'
    if installed.is_file():
        try:names.append(Path(json.loads(installed.read_text())['command']))
        except (ValueError,KeyError,TypeError):return dict(status='invalid_install_receipt',candidates=[])
    from grea.modules import installed_launchers
    names+=installed_launchers('monkey',state_root().parent)
    found=shutil.which('monkey')
    if found:names.append(Path(found))
    candidates=[]
    for name in names:
        if name.is_file() and os.access(name,os.X_OK):
            actual=str(name.resolve())
            if actual not in candidates:candidates.append(actual)
    if len(candidates)!=1:return dict(status='not_installed' if not candidates else 'ambiguous',candidates=candidates)
    return dict(status='discovered',command=[candidates[0]],candidates=candidates)


def provider_override():
    """Registry fallback only; explicit GREA_PROVIDERS always takes precedence."""
    result=discover()
    if result['status'] not in ('bound','discovered'):
        if result['status']=='not_installed':return None
        # Preserve an explicit failure instead of switching away from a stale binding.
        command=[str(state_root()/('unavailable-'+result['status']))]
    else:command=result['command']
    import platform
    return dict(command=command,probe=command+['capabilities','--json'],systems=[platform.system()])


def probe_installation(command):
    """Resolve the package actually imported by an installed Python console launcher."""
    if len(command)!=1:raise ValueError('Automatic binding needs a single installed monkey console launcher; custom argv stays explicit')
    launcher=Path(command[0]).resolve(strict=True)
    header=launcher.open('rb').readline(4096).decode('utf-8',errors='strict').strip()
    if not header.startswith('#!'):raise ValueError('Unsupported console launcher; configure an explicit provider lock')
    python=Path(header[2:])
    if not python.is_absolute() or not python.is_file():raise ValueError('Launcher must name its absolute Python interpreter')
    # Keep the venv spelling, not the base executable's resolved path.
    code='import json,sys,monkey;from pathlib import Path;print(json.dumps(dict(package_root=str(Path(monkey.__file__).resolve().parent),version=monkey.__version__,prefix=sys.prefix,python=sys.executable)))'
    result=subprocess.run([str(python),'-I','-B','-c',code],capture_output=True,text=True,timeout=20)
    if result.returncode or len(result.stdout)>16384:raise ValueError('Cannot inspect installed monkey Python package')
    info=json.loads(result.stdout)
    package=Path(info['package_root'])
    if not package.is_relative_to(Path(info['prefix'])):raise ValueError('Editable/source-directory monkey installations are not auto-bound')
    return dict(info,command=[str(launcher)],launcher_identity=hash_file(launcher),python_identity=hash_file(python.resolve()))


@contextmanager
def configured(command, output):
    """Scope a probe to one candidate without changing global/client settings."""
    import platform
    previous=os.environ.get('GREA_PROVIDERS')
    config={'schema_version':1,'providers':{}}
    if previous:config=json.loads(Path(previous).read_text())
    config['providers']['monkey']=dict(command=command,probe=command+['capabilities','--json'],systems=[platform.system()])
    path=Path(output)/'providers.json';write_new(path,config)
    os.environ['GREA_PROVIDERS']=str(path)
    try:yield
    finally:
        if previous is None:os.environ.pop('GREA_PROVIDERS',None)
        else:os.environ['GREA_PROVIDERS']=previous


def readiness(output, ensure=False, install_missing=False):
    """check is read-only except its receipt; ensure explicitly binds/installs."""
    from .identity import create_lock,pinned
    from .pipeline import SUPPORTED_VERSIONS,probe
    state=state_root();out=disjoint(output,state)
    if out.exists() or not out.parent.is_dir():raise ValueError('Use a fresh readiness output')
    out.mkdir();found=discover()
    try:
        # Explicit caller overrides remain authoritative and never trigger fallback installation.
        if os.environ.get('GREA_PROVIDERS'):
            config=json.loads(Path(os.environ['GREA_PROVIDERS']).read_text())
            override=config.get('providers',{}).get('monkey')
            if override:found=dict(status='explicit_configuration',command=override['command'],candidates=override['command'])
        if found['status']=='not_installed' and ensure and install_missing:
            from .release_install import install_latest
            installed=install_latest(state,out/'download')
            found=dict(status='installed',command=[installed['command']],candidates=[installed['command']])
        if found['status'] not in ('bound','discovered','installed','explicit_configuration'):
            value=dict(status='needs_action',discovery=found,ready=False,next_action='Use ensure --install-if-missing for an absent provider; resolve ambiguity/stale bindings explicitly. No automatic reinstall for an existing broken provider.')
        else:
            info=probe_installation(found['command'])
            if info['version'] not in SUPPORTED_VERSIONS:
                value=dict(status='needs_action',ready=False,discovery=found,installation=info,reason='Installed version is newer/older than the tested adapter; preserved without downgrade. Update the GREA adapter before conversion.')
            elif found['status']=='bound':
                cfg=pinned(found['lock']);probe(found['lock'],out/'capabilities')
                value=dict(status='ready',ready=True,version=cfg['version'],command=found['command'],package_root=info['package_root'],lock=found['lock'],binding=str(state/'binding.json'),installed=False)
            elif not ensure:
                with configured(info['command'],out):
                    cfg=create_lock(info['package_root'],out/'checked-identity')
                value=dict(status='available_unbound',ready=False,version=cfg['version'],command=info['command'],package_root=info['package_root'],next_action='ensure persists this checked installation; no installation needed')
            else:
                state.mkdir(parents=True,exist_ok=True);guard=state/'.binding.lock'
                fd=os.open(guard,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
                try:
                    generations=state/'bindings';generations.mkdir(exist_ok=True);destination=generations/uuid.uuid4().hex
                    with configured(info['command'],out):
                        cfg=create_lock(info['package_root'],destination)
                        if cfg['version']!=info['version']:raise ValueError('CLI and imported package version differ')
                        # Also bind the interpreter executable, beyond the wrapper/module files.
                        cfg['identity_files'].append({k:info['python_identity'][k] for k in ('path','sha256')})
                        (destination/'monkey-lock.json').write_text(json.dumps(cfg,indent=2)+'\n')
                        pinned(destination/'monkey-lock.json')
                    active=dict(schema_version=1,version=cfg['version'],command=info['command'],lock=str(destination/'monkey-lock.json'),package_root=info['package_root'])
                    temporary=state/('.binding-'+uuid.uuid4().hex+'.json');write_new(temporary,active);os.replace(temporary,state/'binding.json')
                    value=dict(active,status='ready',ready=True,installed=found['status']=='installed',binding=str(state/'binding.json'))
                finally:guard.unlink()
        write_new(out/'result.json',value);return value
    except Exception as error:
        write_new(out/'failure.json',dict(status='failed',ready=False,message=str(error)));raise


def default_lock():
    value=binding()
    if not value or not value.get('lock'):raise ValueError('No checked monkey binding; run monkey_pipeline ensure first')
    return value['lock']
