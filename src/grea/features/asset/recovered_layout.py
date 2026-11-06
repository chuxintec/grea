"""Stage a complete GUID-preserving, type-first Assets tree from a closed recovered Unity project."""
import hashlib
import json
import sys
import posixpath
import re
import shutil
import tempfile
from functools import lru_cache
import unicodedata
from collections import Counter
from pathlib import Path, PurePosixPath

from grea.development.asset_names import validate_destination
from grea.development.io import load, read, safe
from grea.development.structure_audit import expected_content_kinds
from grea.common import publish_directory
from grea.development.output_limits import digest_file
from grea.recovery.layout import casing, semantic, standard
from grea.recovery.layout.allocate import LayoutPlanner

GUID = re.compile('[0-9a-f]{32}')
META_GUID = re.compile(rb'^guid: ([0-9a-f]{32})\r?$', re.M)
INCLUDE = re.compile(r'^\s*#\s*include(?:_with_pragmas)?\s+"([^"]+)"', re.M)
GROUP_TYPES = {'Spine.Unity.SkeletonDataAsset': 'Spine', 'Spine.Unity.SpineAtlasAsset': 'Spine',
               'TMPro.TMP_FontAsset': 'Fonts', 'UnityEngine.Font': 'Fonts'}
COMPANIONS = {'UnityEngine.Texture2D', 'UnityEngine.Sprite', 'UnityEngine.Material', 'UnityEngine.TextAsset'}
STAGING_FOLDER = re.compile(r'(?:recovered|original|source)(?:source)?(?:images|textures|meshes|atlases|shaders|resources|prefabs)?', re.I)
PASCAL = {'Prefabs', 'Config', 'Levels', 'Scenes'}


def asset_path(value, *, destination=True):
    parts = value.split('/')
    if parts[0] != 'Assets' or len(parts) < 2 or any(x in ('', '.', '..') for x in parts) or '\\' in value or any(ord(c)<32 for c in value):
        raise ValueError('Invalid Unity asset path: ' + value)
    if destination:
        validate_destination(value)
    return PurePosixPath(value)


def inventory(file):
    rows = {}
    paths = set()
    with safe(file).open(encoding='utf-8-sig') as stream:
        for line in stream:
            guid, path, native, refs = line.rstrip('\r\n').split('\t')
            path = asset_path(path, destination=False)
            if not GUID.fullmatch(guid) or guid in rows or path in paths:
                raise ValueError('Duplicate or invalid native identity: ' + str(path))
            rows[guid] = (path, native, refs.split(',') if refs else [])
            paths.add(path)
    if not rows:
        raise ValueError('Empty native inventory')
    return rows


def families(rows):
    """Only traverse native group members and material page references, never shared shaders or scripts."""
    owners = {}
    for guid in sorted(rows, key=lambda g: (rows[g][1] != 'Spine.Unity.SkeletonDataAsset', g)):
        native = rows[guid][1]
        if native not in GROUP_TYPES:
            continue
        typ = GROUP_TYPES[native]
        pending = [guid]
        seen = set()
        while pending:
            member = pending.pop()
            if member in seen:
                continue
            seen.add(member)
            prior = owners.setdefault(member, (typ, guid))
            if prior[0] != typ:
                # A shared page still has one physical identity. Keep it in its own type.
                owners[member] = ('', '')
            for ref in rows[member][2]:
                if ref in rows and (rows[ref][1] in COMPANIONS or GROUP_TYPES.get(rows[ref][1]) == typ):
                    pending.append(ref)
    return owners


def words(value):
    return re.sub(r'[^A-Za-z0-9]+', '_', casing.romanize(value).replace('×', 'x')).strip('_')


@lru_cache(maxsize=32768)
def module(address):
    folders = semantic.derive({'logicalPath': address}, {})['folders']
    return [casing.pascal(word) for s in folders if (word := words(s))
            and not GUID.fullmatch(s.lower()) and not STAGING_FOLDER.fullmatch(s)]


def usage_modules(rows, addresses):
    choices = {}
    for guid, (path, _, deps) in rows.items():
        folders = module(addresses.get(guid, path.name))
        if folders:
            for dep in deps:
                choices.setdefault(dep, set()).add(folders[0])
    return {guid: list(options) for guid, options in choices.items() if len(options) == 1}


def includes(project, rows):
    by_path = {str(p): guid for guid, (p, _, _) in rows.items()}
    edges = []
    for guid, (path, _, _) in rows.items():
        if path.suffix.lower() not in ('.shader', '.hlsl', '.cginc', '.compute'):
            continue
        for name in INCLUDE.findall((project/path).read_text(encoding='utf-8-sig')):
            target = posixpath.normpath(posixpath.join(str(path.parent), name))
            if target in by_path:
                edges.append((guid, name, by_path[target]))
            elif name.startswith('Assets/'):
                raise ValueError('Absolute project shader include requires explicit migration: ' + name)
    return edges


def assembly_scopes(project, rows):
    assemblies = {p.parent: json.loads((project/p).read_bytes())['name']
                  for p, _, _ in rows.values() if p.suffix.lower() == '.asmdef'}
    for assembly in assemblies.values():
        if not isinstance(assembly, str) or not assembly or PurePosixPath(assembly).name != assembly or assembly in ('.', '..'):
            raise ValueError('Invalid assembly name: ' + str(assembly))
    return assemblies


def shader_groups(project, rows, addresses):
    edges = includes(project, rows)
    include_ids = {ref for _, _, ref in edges}
    shader_dirs = {rows[g][0].parent for edge in edges for g in (edge[0], edge[2])}
    shader_folders = {}
    for path in sorted(shader_dirs):
        candidates = sorted(g for g in include_ids if rows[g][0].parent == path)
        if not candidates:
            raise ValueError('Cross-directory shader includes require a pinned group mapping: ' + str(path))
        member = candidates[0]
        shader_folders[path] = module(addresses.get(member, rows[member][0].name)) or ['Common']
    return edges, include_ids, shader_folders


def family_directories(rows, groups, addresses):
    group_dirs = {}
    names = set()
    for category, owner in sorted(set(groups.values())):
        if not owner:
            continue
        p = rows[owner][0]
        stem = p.stem.removesuffix('_SkeletonData').removesuffix('_Atlas')
        folder = PurePosixPath(*(module(addresses.get(owner, p.name)) or ['Common']), casing.pascal(words(stem)))
        key = (category, str(folder).casefold())
        if key in names:
            folder = folder.with_name(folder.name + '_' + owner[:10])
        names.add(key)
        group_dirs[owner] = folder
    return group_dirs


def proposed(project, rows, addresses):
    groups = families(rows)
    usage = usage_modules(rows, addresses)
    assemblies = assembly_scopes(project, rows)
    edges, include_ids, shader_folders = shader_groups(project, rows, addresses)
    group_dirs = family_directories(rows, groups, addresses)
    records = []
    for guid, (path, native, deps) in sorted(rows.items()):
        address = addresses.get(guid, path.name)
        ext = path.suffix
        root = standard.ROOTS['unity']['content']
        folders = module(address) or usage.get(guid) or ['Common']
        stem = words(GUID.sub('', path.stem)) or (native.rsplit('.', 1)[-1] + '_' + guid[:10])
        group, owner = groups.get(guid, ('', ''))
        if str(path).startswith(('Assets/Plugins/', 'Assets/ThirdParty/', 'Assets/TextMesh Pro/')):
            target, reason = str(path), 'vendor'
        elif ext.lower() in ('.cs', '.asmdef', '.asmref'):
            parent = next((p for p in path.parents if p in assemblies), None)
            if parent is not None:
                target = str(PurePosixPath(standard.ROOTS['unity']['scripts'], assemblies[parent], path.relative_to(parent)))
            elif ext.lower() == '.cs' and 'Editor' not in path.parts and native == 'UnityEditor.MonoScript':
                namespaces = re.findall(r'^\s*namespace\s+([A-Za-z_][\w.]*)', (project/path).read_text(encoding='utf-8-sig'), re.M)
                namespace = namespaces[0].split('.') if namespaces else []
                target = str(PurePosixPath(standard.ROOTS['unity']['scripts'], 'Assembly-CSharp', *namespace, path.name))
            else:
                raise ValueError('Missing script assembly scope: ' + str(path))
            reason = 'assembly-scope'
        else:
            kind = expected_content_kinds(native, str(path))
            if native == 'UnityEngine.TextAsset' and not group and ext.lower() == '.json':
                load(read(project/path))
                kind = {'Config'}
            if group:
                kind = {group}
            if not kind or len(kind) != 1:
                raise ValueError(f'Unclassified Unity asset {guid} {native}: {path}')
            category = next(iter(kind))
            base = str(PurePosixPath(root, category))
            reason = 'native-type'
            if category == 'Scenes':
                base = standard.ROOTS['unity']['scenes']
            if 'Resources' in path.parts[:-1]:
                target = str(PurePosixPath(base, *path.parts[path.parts.index('Resources'):]))
                reason = 'resources-key'
            elif group:
                name = path.name if group == 'Spine' else LayoutPlanner._filename(casing.snake(stem), ext)
                target = str(PurePosixPath(base, group_dirs[owner], name))
                reason = 'native-family'
            elif guid in include_ids and path.parent in shader_folders:
                target = str(PurePosixPath(base, *shader_folders[path.parent], path.name))
                reason = 'shader-include'
            else:
                if path.parent in shader_folders and category == 'Shaders':
                    folders = shader_folders[path.parent]
                formatter = casing.pascal if category in PASCAL or native in ('UnityEditor.Animations.AnimatorController', 'UnityEngine.AnimatorOverrideController') else casing.snake
                name = LayoutPlanner._filename(formatter(stem), ext)
                target = str(PurePosixPath(base, *folders, name))
        asset_path(target)
        records.append(dict(guid=guid, source=str(path), target=target, importedType=native, address=address, reason=reason))
    reserve_paths(records, include_ids)
    destinations = {r['guid']:r['target'] for r in records}
    for guid, name, ref in edges:
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(destinations[guid]), name))
        if resolved != destinations[ref]:
            raise ValueError('Shader include would change: ' + resolved + ' != ' + destinations[ref])
    return records


def folded(path):
    return unicodedata.normalize('NFC', str(path)).casefold()


def reserve_paths(records, include_ids):
    # Reserve exact-key and compiler paths first. Other collisions get a stable identity suffix.
    claimed = set()
    dirs = {}
    for row in sorted(records, key=lambda r: (r['reason'] == 'native-type', r['guid'])):
        p = PurePosixPath(row['target'])
        parent = PurePosixPath()
        for part in p.parent.parts:
            parent = PurePosixPath(dirs.setdefault(folded(parent / part), str(parent / part)))
        p = parent / p.name
        if folded(p) in claimed:
            if row['reason'] not in ('native-type', 'native-family') or row['guid'] in include_ids:
                raise ValueError('Protected path collision: ' + str(p))
            # Family filenames can be runtime keys (e.g. atlas page names). Separate the containers.
            if row['reason'] == 'native-family':
                p = p.parent / ('Variant' + row['guid'][:10]) / p.name
            else:
                p = p.with_name(LayoutPlanner._filename(p.stem + '_' + row['guid'][:10], p.suffix))
        if folded(p) in claimed:
            raise ValueError('Unresolved collision: ' + str(p))
        claimed.add(folded(p))
        row['target'] = str(p)
        if row['reason'] == 'resources-key' and row['target'].partition('/Resources/')[2] != row['source'].partition('/Resources/')[2]:
            raise ValueError('Resources key would change: ' + row['source'])


def copy_asset(source, target):
    # The candidate must be independent of later source writes. APFS can share blocks until a write.
    if sys.platform == 'darwin':
        from ctypes import get_errno
        import errno
        import os
        if clonefile()(os.fsencode(source), os.fsencode(target), 0) == 0:
            return
        error = get_errno()
        if error not in (errno.ENOTSUP, errno.EXDEV, errno.ENOSYS):
            raise OSError(error, 'Cannot clone asset', str(source))
    shutil.copy2(source, target)


@lru_cache(maxsize=1)
def clonefile():
    from ctypes import CDLL, c_char_p, c_int
    clone = CDLL(None, use_errno=True).clonefile
    clone.argtypes = [c_char_p, c_char_p, c_int]
    return clone


def stage(args):
    project, dest = safe(args.project), safe(args.output)
    inputs = [project, safe(args.inventory)]
    if args.addresses:
        inputs.append(safe(args.addresses))
    if dest.exists() or any(dest == i or dest in i.parents or i in dest.parents for i in inputs):
        raise ValueError('Independent, new output directory required')
    if (project/'Temp/UnityLockfile').exists():
        raise ValueError('Close the project before staging recovered assets')
    rows = inventory(args.inventory)
    addresses = load(read(args.addresses, max_bytes=128 << 20)) if args.addresses else {}
    if not isinstance(addresses, dict) or set(addresses) - rows.keys() or not all(isinstance(v, str) and v for v in addresses.values()):
        raise ValueError('Source address map does not match native identities')
    files = active_files(project)
    if files != {str(p) for p, _, _ in rows.values()}:
        raise ValueError('Native inventory and active files differ: ' + str(sorted(files ^ {str(p) for p, _, _ in rows.values()})[:8]))
    unaccounted = {dep for _, _, deps in rows.values() for dep in deps if dep not in rows}
    if unaccounted:
        raise ValueError('Dependencies outside file inventory (including referenced folders): ' + str(sorted(unaccounted)[:8]))
    records = proposed(project, rows, addresses)
    from .prefab_names import root_alias
    for row in records:
        if row['target'].endswith('.prefab'):
            alias = root_alias((project/row['source']).read_bytes(), row['source'], row['target'])
            if alias:
                row['prefabRootAlias'] = alias
    validate_consumers(project, records)
    return materialize(project, dest, records, args.inventory, args.addresses)


def active_files(project):
    assets = safe(project/'Assets')
    if not assets.is_dir():
        raise ValueError('Missing Unity Assets directory')
    files = set()
    for path in assets.rglob('*'):
        if path.is_symlink():
            raise ValueError('Linked asset: ' + str(path))
        if path.is_file() and path.suffix != '.meta' and not path.name.startswith('.'):
            files.add(path.relative_to(project).as_posix())
    return files


def validate_consumers(project, records):
    """Exact path literals and scene settings must be migrated by their owning consumer."""
    moves = {r['source'] for r in records if r['source'] != r['target']}
    names = {r['prefabRootAlias']['sourceName'] for r in records if 'prefabRootAlias' in r}
    paths = [project/r['source'] for r in records if Path(r['source']).suffix.lower() in ('.cs', '.json', '.asmdef', '.asmref')]
    paths.extend((project/'ProjectSettings').glob('*.asset'))
    aliases = {r['guid'] for r in records if 'prefabRootAlias' in r}
    if aliases:
        for r in records:
            if r['source'].endswith('.prefab'):
                raw = (project/r['source']).read_bytes()
                nested = re.findall(rb'^  m_SourcePrefab: \{fileID: -?\d+, guid: ([a-f0-9]{32}),', raw, re.M)
                if any(ref.decode() in aliases for ref in nested):
                    raise ValueError('Nested Prefab consumes a renamed root: ' + r['source'])
    literals = re.compile(rb'Assets/[^"\r\n\x00]+')
    for p in paths:
        data = p.read_bytes()
        if p.suffix == '.cs':
            keys = {x.decode('utf-8') for x in re.findall(rb'"([^"\r\n]*)"', data)}
            used = keys & names
            if used:
                raise ValueError(f'Prefab root name has a literal code consumer: {p} -> {sorted(used)}')
        for raw in literals.findall(data):
            literal = raw.decode('utf-8', errors='replace').strip()
            if literal in moves:
                raise ValueError(f'Path consumer requires coordinated migration: {p} -> {literal}')


def materialize(project, dest, records, native, addresses):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        pending = Path(tmp)/'output'
        pending.mkdir()
        with (pending/'layout.jsonl').open('w', encoding='utf-8') as ledger:
            for r in records:
                src, target = project/r['source'], pending/r['target']
                target.parent.mkdir(parents=True, exist_ok=True)
                meta = Path(str(src)+'.meta').read_bytes()
                match = META_GUID.search(meta)
                if not match or match[1].decode() != r['guid']:
                    raise ValueError('Stale native identity: ' + r['source'])
                copy_asset(src, target)
                Path(str(target)+'.meta').write_bytes(meta)
                r['sha256'] = digest_file(target)
                r['metaSha256'] = hashlib.sha256(meta).hexdigest()
                ledger.write(json.dumps(r, ensure_ascii=False) + '\n')
        for folder in (pending/'Assets').rglob('*'):
            if folder.is_dir():
                source_meta = project/(folder.relative_to(pending).as_posix()+'.meta')
                if source_meta.is_file():
                    shutil.copy2(source_meta, str(folder)+'.meta')
        counts = dict(Counter(r['reason'] for r in records))
        summary = dict(layout=standard.VERSION, assets=len(records), reasons=counts,
                       inventorySha256=digest_file(Path(native)),
                       addressesSha256=digest_file(Path(addresses)) if addresses else None,
                       ledgerSha256=digest_file(pending/'layout.jsonl'),
                       prefabRootAliases=sum('prefabRootAlias' in r for r in records),
                       moved=sum(r['source'] != r['target'] for r in records))
        (pending/'summary.json').write_text(json.dumps(summary, indent=2))
        publish_directory(pending, dest)
    return dict(**summary, report=str(dest/'summary.json'))
