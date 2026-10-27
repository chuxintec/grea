"""GREA modules: pinned monkey/beaver wheels released with GREA, installed into isolated venvs.

GREA never imports module code. A module is installed by extracting its verified pure-Python
wheel into a dedicated venv whose console launcher is then pinned by the existing provider
readiness (monkey_pipeline / beaver_pipeline). Shared binary dependencies come from the GREA
runtime through one .pth line, so the module runs on the same locked interpreter libraries.
"""
import base64
import csv
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import sysconfig
import uuid
import zipfile
from pathlib import Path
from grea.common import package_root, write_new
from grea.safe_paths import disjoint

CONTRACT = 'grea-modules/1'
NAMES = ('monkey', 'beaver')
MAX_WHEEL = 64 * 1024**2


def lock_path(root=None):
    return Path(root or package_root())/'modules.lock.json'


def load_lock(root=None):
    path = lock_path(root)
    value = json.loads(path.read_text(encoding='utf-8'))
    if value.get('schemaVersion') != 1 or value.get('contract') != CONTRACT:
        raise ValueError('Unsupported GREA module lock')
    modules = value.get('modules')
    if not isinstance(modules, list) or [m.get('name') for m in modules] != list(NAMES):
        raise ValueError('GREA module lock must declare exactly monkey and beaver, in order')
    for m in modules:
        w = m.get('wheel', {})
        if not (isinstance(w.get('file'), str) and w['file'].endswith('-py3-none-any.whl') and '/' not in w['file']):
            raise ValueError('Module wheel must be a pure-Python wheel file name: ' + m['name'])
        if not (isinstance(w.get('sha256'), str) and len(w['sha256']) == 64 and isinstance(w.get('bytes'), int)):
            raise ValueError('Module wheel identity incomplete: ' + m['name'])
        for key in ('version', 'import', 'console', 'entry', 'distribution'):
            if not isinstance(m.get(key), str) or not m[key]:
                raise ValueError(f'Module {m["name"]} lacks {key}')
    return value


def module(name, root=None):
    for m in load_lock(root)['modules']:
        if m['name'] == name: return m
    raise ValueError('Unknown GREA module: ' + str(name))


def bundled_dir(root=None):
    return Path(root or package_root())/'modules'/'wheels'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def verify_wheel(path, entry):
    path = Path(path)
    if not path.is_file() or path.is_symlink(): raise ValueError('Missing module wheel: ' + str(path))
    size = path.stat().st_size
    if size > MAX_WHEEL or size != entry['wheel']['bytes'] or sha256(path) != entry['wheel']['sha256']:
        raise ValueError('Module wheel identity differs from modules.lock.json: ' + entry['name'])
    with zipfile.ZipFile(path) as z:
        meta = [n for n in z.namelist() if n.endswith('.dist-info/METADATA')]
        if len(meta) != 1: raise ValueError('Wheel lacks a single METADATA: ' + entry['name'])
        fields = dict(line.split(': ', 1) for line in z.read(meta[0]).decode('utf-8').splitlines()
                      if ': ' in line and line.split(': ', 1)[0] in ('Name', 'Version'))
        if fields.get('Version') != entry['version'] or fields.get('Name', '').replace('_', '-').lower() != entry['distribution']:
            raise ValueError('Wheel metadata differs from modules.lock.json: ' + entry['name'])
    return dict(path=str(path), sha256=entry['wheel']['sha256'], bytes=size)


def status(root=None, state=None):
    """Read-only: lock, bundled wheels and installed module copies. Never spawns or writes."""
    lock = load_lock(root); rows = []
    for m in lock['modules']:
        wheel = bundled_dir(root)/m['wheel']['file']
        try: bundled = dict(state='verified', **verify_wheel(wheel, m))
        except ValueError as error: bundled = dict(state='absent' if not wheel.exists() else 'mismatch', reason=str(error))
        target = install_root(m, state)
        installed = 'installed' if (target/'install.json').is_file() else 'not_installed'
        rows.append(dict(name=m['name'], version=m['version'], role=m['role'], releaseStatus=m.get('releaseStatus'),
                         bundled=bundled, installed=installed, install_root=str(target),
                         launcher=str(launcher(target, m)) if installed == 'installed' else None))
    return dict(contract=CONTRACT, status='ok', modules=rows, executed=False,
                note='Bundled/installed is not readiness; pin through monkey_pipeline/beaver_pipeline or toolchain_check.')


def state_root(state=None):
    return Path(state or os.environ.get('GREA_PROVIDER_STATE_DIR', Path.home()/'.local/share/grea/providers')).expanduser().absolute()


def install_root(entry, state=None):
    return state_root(state)/entry['name']/'modules'/(entry['version'] + '-' + entry['wheel']['sha256'][:12])


def installed_launchers(name, state=None):
    """Launchers of all module installs; discovery treats each as one candidate, never as a binding."""
    root = state_root(state)/name/'modules'
    rows = []
    for receipt in sorted(root.glob('*/install.json')) if root.is_dir() else []:
        try: value = json.loads(receipt.read_text(encoding='utf-8'))
        except ValueError: continue
        path = Path(value.get('launcher', ''))
        if value.get('contract') == CONTRACT and path.is_file() and os.access(path, os.X_OK): rows.append(path)
    return rows


def launcher(target, entry):
    return Path(target)/('Scripts' if os.name == 'nt' else 'bin')/entry['console']


def _extract(wheel, site):
    """Install a pure wheel by extraction, verifying every RECORD hash first."""
    with zipfile.ZipFile(wheel) as z:
        names = z.namelist()
        records = [n for n in names if n.endswith('.dist-info/RECORD')]
        if len(records) != 1: raise ValueError('Wheel lacks a single RECORD')
        rows = list(csv.reader(io.StringIO(z.read(records[0]).decode('utf-8'))))
        listed = {r[0]: r[1] for r in rows if r}
        for name in names:
            if name.endswith('/'): continue
            if name.startswith('/') or '..' in Path(name).parts or '.data/' in name:
                raise ValueError('Unsupported wheel member: ' + name)
            data = z.read(name)
            expected = listed.get(name)
            if expected is None: raise ValueError('Wheel member missing from RECORD: ' + name)
            if expected:
                algorithm, wanted = expected.split('=', 1)
                actual = base64.urlsafe_b64encode(hashlib.new(algorithm, data).digest()).rstrip(b'=').decode()
                if actual != wanted: raise ValueError('Wheel member differs from RECORD: ' + name)
            target = site/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (site/records[0]).with_name('INSTALLER').write_text('grea-modules\n', encoding='utf-8')


def _core_site():
    """The running GREA interpreter's dependency directory (bundled runtime or source venv)."""
    candidates = [Path(p) for p in sys.path if p.endswith('site-packages') and (Path(p)/'PIL').is_dir()]
    if not candidates: candidates = [Path(sysconfig.get_paths()['purelib'])]
    return candidates[0].resolve()


def install(name, output, *, wheel=None, state=None, root=None):
    """Explicit install of one locked module into an isolated venv; never binds or replaces."""
    entry = module(name, root)
    if os.name == 'nt':
        raise ValueError('Module install on Windows is not supported yet; the provider readiness requires a POSIX console launcher')
    source = Path(wheel) if wheel else bundled_dir(root)/entry['wheel']['file']
    identity = verify_wheel(source, entry)
    target = install_root(entry, state)
    out = disjoint(output, target, source)
    if out.exists() or not out.parent.is_dir(): raise ValueError('Use a fresh install receipt directory')
    out.mkdir()
    if (target/'install.json').is_file():
        previous = json.loads((target/'install.json').read_text())
        if previous.get('wheel_sha256') != entry['wheel']['sha256']: raise ValueError('Existing install root holds a different wheel')
        result = dict(status='ok', installed=False, reused=True, **previous)
        write_new(out/'result.json', result); return result
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent/('.staging-' + uuid.uuid4().hex)
    try:
        subprocess.run([sys.executable, '-I', '-m', 'venv', '--without-pip', str(staging)], check=True,
                       capture_output=True, timeout=120)
        python = staging/'bin/python3'
        site = Path(subprocess.check_output([str(python), '-I', '-c', 'import sysconfig;print(sysconfig.get_paths()["purelib"])'],
                                            text=True, timeout=30).strip())
        _extract(source, site)
        core = _core_site()
        (site/'grea-core-runtime.pth').write_text(str(core) + '\n', encoding='utf-8')
        module_name, function = entry['entry'].split(':')
        script = staging/'bin'/entry['console']
        # Shebang must name the final venv interpreter; provider readiness reads it.
        script.write_text(f'#!{target}/bin/python3\nimport sys\nfrom {module_name} import {function}\nsys.exit({function}())\n', encoding='utf-8')
        script.chmod(0o755)
        record = dict(contract=CONTRACT, module=name, version=entry['version'], wheel_sha256=identity['sha256'],
                      wheel_bytes=identity['bytes'], install_root=str(target), launcher=str(launcher(target, entry)),
                      identity_root=None, core_runtime_site=str(core), python=sys.executable,
                      platform=f'{platform.system()}-{platform.machine()}', binding='not_changed')
        write_new(staging/'install.json', record)
        os.replace(staging, target)
    except BaseException:
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
        raise
    # Re-resolve paths now the venv lives at its final location.
    python = target/'bin/python3'
    probe = subprocess.run([str(python), '-I', '-B', '-c',
                            f'import json,{entry["import"]} as m;from pathlib import Path;print(json.dumps(dict(root=str(Path(m.__file__).resolve().parent),version=getattr(m,"__version__",None))))'],
                           capture_output=True, text=True, timeout=30)
    if probe.returncode: raise ValueError('Installed module does not import: ' + probe.stderr[-400:])
    imported = json.loads(probe.stdout)
    record = json.loads((target/'install.json').read_text()); record['identity_root'] = imported['root']
    (target/'install.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    result = dict(status='ok', installed=True, reused=False, **record,
                  next_action=f'Pin explicitly: {name}_pipeline (beaver: pin --identity-root {imported["root"]}) under a GREA_PROVIDERS entry naming {record["launcher"]}; existing bindings are not replaced.')
    write_new(out/'result.json', result)
    return result


def fetch(destination, root=None, timeout=60):
    """Download the locked wheels (build/CI only), verifying size and SHA256; reuses verified files."""
    import tempfile
    import urllib.request
    destination = Path(destination); destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in load_lock(root)['modules']:
        target = destination/m['wheel']['file']
        if target.is_file():
            try:
                rows.append(dict(name=m['name'], state='cached', **verify_wheel(target, m))); continue
            except ValueError:
                target.unlink()
        url = m['wheel'].get('url')
        if not url or not url.startswith('https://'): raise ValueError('Module wheel has no https URL in modules.lock.json: ' + m['name'])
        with tempfile.NamedTemporaryFile(dir=destination, suffix='.download', delete=False) as output:
            temporary = Path(output.name)
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'grea-modules'})
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block: break
                        output.write(block)
                        if output.tell() > MAX_WHEEL: raise ValueError('Module wheel exceeds size budget')
            except BaseException:
                temporary.unlink(missing_ok=True); raise
        try:
            verify_wheel(temporary, m)
        except ValueError:
            temporary.unlink(); raise
        temporary.replace(target)
        rows.append(dict(name=m['name'], state='downloaded', **verify_wheel(target, m)))
    return rows


def stage(source_dir, destination, root=None):
    """Build-time: copy the exact locked wheels into a plugin tree."""
    lock = load_lock(root); destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    for m in lock['modules']:
        source = Path(source_dir)/m['wheel']['file']
        verify_wheel(source, m)
        (destination/m['wheel']['file']).write_bytes(source.read_bytes())
        rows.append(dict(name=m['name'], version=m['version'], file=m['wheel']['file'], sha256=m['wheel']['sha256'],
                         bytes=m['wheel']['bytes'], releaseStatus=m.get('releaseStatus')))
    return rows
