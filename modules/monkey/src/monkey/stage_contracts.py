"""Per-stage reader/data contracts; layout edits do not invalidate source stages."""
import ast
from importlib.metadata import version,PackageNotFoundError
from pathlib import Path
from .io import sha, encoded

ROOT = Path(__file__).parent
CORE_IO = ('sha','safe','inside','read','load','encoded','write_json','stage_bytes','stage_manifest','stage_document','new_output','diagnostic')
LEGACY_IO = 'f80c07fafd104436040adc83e89bdd7726f911524822840aef1e6154258fa5b2'
# Reviewed v0.4.0 source I/O functions; finish()'s inventory policy is excluded.
LEGACY_CORE = '8a69389ea89bbdbb4d2c1c18e19d7ad1deb8e8388c44d5fb077d4392ece36850'


def io_contract():
    tree = ast.parse((ROOT/'io.py').read_text())
    units = {n.name: ast.dump(n, include_attributes=False) for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in CORE_IO}
    units['MAX_BYTES'] = next(ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MAX_BYTES' for t in n.targets))
    return sha(encoded(units))


def source_contracts():
    core = dict(io=io_contract())
    libraries={}
    for name in ('Pillow','texture2ddecoder'):
        try:libraries[name]=version(name)
        except PackageNotFoundError:libraries[name]=None
    groups = {
        'inspect': ['inputs.py','sources/bundle.py','sources/project.py','sources/compiled.py','sources/cocos34.py',
                    'sources/cocos34_graphs.py','sources/cocos38.py','sources/cocos38_graphs.py',
                    'sources/cocos38_prefabs.py','sources/cocos_legacy.py'],
        'normalize': ['normalize.py',*[str(p.relative_to(ROOT)) for p in sorted((ROOT/'assets').glob('*.py'))],
                      'sources/compiled.py','sources/cocos34.py','sources/cocos34_graphs.py','sources/cocos38.py',
                      'sources/cocos38_graphs.py','sources/cocos38_prefabs.py'],
    }
    return {name: dict(contractVersion=2, files={p:sha((ROOT/p).read_bytes()) for p in paths},
                       core=core, libraries=libraries if name=='normalize' else {}, sha256=sha(encoded(dict(files={p:sha((ROOT/p).read_bytes()) for p in paths},core=core,libraries=libraries if name=='normalize' else {}))))
            for name, paths in groups.items()}


def compatible(saved, current, phase):
    """Legacy acceptance verifies each relevant file, never just a tool version."""
    previous = saved.get(phase, {})
    if previous.get('contractVersion') == 2:
        return previous == current[phase]
    if phase not in ('inspect','normalize') or not previous.get('files'):
        return previous == current.get(phase)
    files = dict(previous['files'])
    for peer in ('inspect','normalize'):
        for name,digest in saved.get(peer,{}).get('files',{}).items():
            if name in files and files[name] != digest: return False
            files[name] = digest
    required = current[phase]['files']
    if any(files.get(p) != digest for p, digest in required.items()): return False
    return (files.get('io.py') == LEGACY_IO and current[phase]['core']['io'] == LEGACY_CORE
            and (phase!='normalize' or current[phase]['libraries']=={'Pillow':'12.2.0','texture2ddecoder':'1.0.6'}))
