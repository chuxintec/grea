"""Collect original MonoBehaviour hosts for an explicit set of recovered Unity prefabs."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
import re

from .unity_object_dependencies import pointer
from .unity_visual_repair import write_owned


def collect(roots, resolve):
    hosts = []
    selections = set()
    for root in roots:
        path = root['asset']
        identity = (path, root['assembly'], root['type'])
        if (identity in selections or not path.startswith('Assets/') or '..' in Path(path).parts
                or not path.endswith('.prefab') or not re.fullmatch(r'[a-f0-9]{32}', root['scriptGuid'])):
            raise ValueError(f'Invalid or duplicate prefab selection: {identity}')
        selections.add(identity)
        cab = root['cab'].lower()
        file = resolve(cab)
        initial = len(hosts)
        seen = set()
        pending = [(int(root['rootId']), '0')]
        while pending:
            game_id, child_path = pending.pop()
            if game_id in seen:
                raise ValueError(f'Duplicate Transform child: {cab}/{game_id}')
            seen.add(game_id)
            node = file.objects[game_id]
            if node.type.name != 'GameObject':
                raise ValueError(f'Expected a GameObject: {cab}/{game_id}')
            data = node.read_typetree()
            children = None
            for index, entry in enumerate(data['m_Component']):
                component = pointer(file, entry['component'])
                if not component or component[0] != cab:
                    raise ValueError(f'Invalid local component on {path} {child_path}')
                obj = file.objects[component[1]]
                if obj.type.name in ('RectTransform', 'Transform'):
                    if children is not None:
                        raise ValueError(f'Multiple transforms on {path} {child_path}')
                    children = obj.read_typetree()['m_Children']
                if obj.type.name != 'MonoBehaviour':
                    continue
                script = pointer(file, obj.read_typetree()['m_Script'])
                if not script:
                    continue
                script_obj = resolve(script[0]).objects[script[1]]
                if script_obj.type.name != 'MonoScript':
                    raise ValueError(f'Invalid script pointer on {path} {child_path}')
                code = script_obj.read_typetree()
                full_name = '.'.join(filter(None, (code['m_Namespace'], code['m_ClassName'])))
                assembly = code['m_AssemblyName'].removesuffix('.dll')
                if full_name == root['type'] and assembly == root['assembly']:
                    hosts.append(dict(asset=path, sourceCab=cab, siblingPath=child_path,
                                      node=data['m_Name'], sourceGameObject=str(game_id),
                                      componentIndex=index, sourceComponent=str(component[1]),
                                      sourceScriptCab=script[0], sourceScriptId=str(script[1]),
                                      type=full_name, assembly=assembly, scriptGuid=root['scriptGuid']))
            if children is None:
                raise ValueError(f'Missing Transform: {path} {child_path}')
            for index, ref in reversed(list(enumerate(children))):
                transform = pointer(file, ref)
                if not transform or transform[0] != cab:
                    raise ValueError(f'Invalid child Transform: {path} {child_path}')
                child_transform = file.objects[transform[1]]
                if child_transform.type.name not in ('Transform','RectTransform'):
                    raise ValueError(f'Child pointer is not a Transform: {path} {child_path}')
                child = pointer(file, child_transform.read_typetree()['m_GameObject'])
                if not child or child[0] != cab:
                    raise ValueError(f'Invalid child GameObject: {path} {child_path}')
                pending.append((child[1], f'{child_path}/{index}'))
        if len(hosts) == initial:
            raise ValueError(f'No original host for {root["assembly"]}/{root["type"]} on {path}')
    return hosts


def prepare(manifest, output, project=None):
    import UnityPy
    manifest = Path(manifest).resolve()
    spec = json.loads(manifest.read_text())

    @lru_cache(maxsize=12)
    def resolve(cab):
        row = spec['files'][cab]
        raw = (manifest.parent / row['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError(f'Source bundle changed: {cab}')
        matches = [f for f in UnityPy.load(raw).assets if f.name.lower() == cab]
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one serialized file: {cab}')
        return matches[0]

    hosts = collect(spec['roots'], resolve)
    data = json.dumps(dict(hosts=hosts), indent=2, ensure_ascii=False).encode()
    if project is not None:
        project = Path(project)
        if not (project/'Assets').is_dir():
            raise ValueError('Expected an existing Unity candidate')
        source = Path(__file__).parent/'targets/unity_source/UnityRuntimeMethodHosts.cs'
        write_owned(project/'Assets/Editor'/source.name, source.read_bytes())
        write_owned(project/'expected-hosts.json', data)
    write_owned(Path(output), data)
    return dict(roots=len({h['asset'] for h in hosts}), hosts=len(hosts), output=str(output))
