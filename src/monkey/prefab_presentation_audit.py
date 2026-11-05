"""Compare saved native Prefab presentation evidence with its pinned import plan."""
from collections import defaultdict
import hashlib
import json
import re
from pathlib import Path

from . import io


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def serialized_objects(asset):
    # Unity Force Text stores Image components in class-114 documents. For
    # inherited components use the importer's saved-instance reference proof;
    # an inherited override cannot be inferred from the template's YAML alone.
    docs = re.split(r'^--- !u!\d+ &(-?\d+)[^\n]*\n', asset.read_text(), flags=re.M)
    return dict(zip(docs[1::2], docs[2::2]))


def check_images(project, objects, receipt, sprites, textures):
    physical = {c['sourceId']: c for c in receipt['components']}
    bindings = []
    errors = []
    for sprite in sprites:
        if not sprite['convertible'] or not sprite.get('spriteFrame'):
            continue
        key = sprite['spriteFrame']
        if not sprite.get('trim', True) and sprite.get('untrimmedGeometryPolicy') != 'creator24-packed-frame-insets':
            key += '@original'
        path = io.inside(project, textures[key]['path'])
        meta = Path(str(path) + '.meta').read_text()
        guid = re.search(r'^guid: ([0-9a-f]{32})$', meta, re.M).group(1)
        sid = sprite['sourceId']
        component = physical.get(sid, {})
        body = objects.get(str(component.get('localFileId')), '')
        match = re.search(r'^  m_Sprite: \{fileID: (-?\d+), guid: ([0-9a-f]{32}), type: \d+\}$', body, re.M)
        row = dict(sourceId=sid, spriteFrame=key, expectedTexture=guid)
        if component.get('guid') == receipt['guid'] and '  m_Sprite:' in body:
            row['observedTexture'] = match.group(2) if match else None
            if not match or int(match.group(1)) == 0 or match.group(2) != guid:
                errors.append(f'{sid}: saved Image sprite reference differs')
        else:
            row['evidence'] = 'aggregate-native-reference-check'
        bindings.append(row)
    return bindings, errors


def check_parent_links(objects, saved, authored, guid):
    rect_ids = {}
    for identity, node in saved.items():
        for component in node.get('physicalComponents', []):
            if component['nativeType'] == 'UnityEngine.RectTransform' and component['guid'] == guid:
                rect_ids[identity] = str(component['localFileId'])
    verified = 0
    errors = []
    for identity, source in authored.items():
        parent_id = rect_ids.get(source.get('parent'))
        child_id = rect_ids.get(identity)
        body = objects.get(child_id, '')
        if not parent_id or '  m_Father:' not in body:
            continue
        match = re.search(r'^  m_Father: \{fileID: (-?\d+)\}$', body, re.M)
        if not match or match.group(1) != parent_id:
            errors.append(f'{identity}: serialized RectTransform parent differs')
        else:
            verified += 1
    return verified, errors


def inspect(project, plan, plan_hash, spec, receipt):
    issues = []
    asset = io.inside(project, spec['path'])
    if (receipt.get('path') != spec['path'] or receipt.get('importPlanSha256') != plan_hash
            or digest(asset) != receipt.get('prefabSha256')
            or digest(Path(str(asset) + '.meta')) != receipt.get('prefabMetaSha256')):
        raise ValueError(f"Changed source plan or saved prefab: {spec['sourceId']}")
    if not receipt['savedReloaded'] or receipt['missingScripts'] or not receipt['referencesVerified']:
        issues.append('native save/reopen or reference verification failed')
    saved = {node['sourceId']: node for node in receipt['nodes']}
    initial = {node['sourceId']: node for node in receipt['nativeInitialNodes']}
    authored = {node['sourceId']: node for node in plan['nodes'] if node['sourceId'] in saved}
    if (set(spec['nodes']) != set(saved) or set(saved) != set(initial) or
            len(saved) != receipt['nodeCount'] or len(saved) != len(receipt['nodes'])):
        issues.append('node identity coverage differs')
    moved = []
    for identity, node in authored.items():
        actual = saved[identity]
        children = [saved[key] for key in node['children'] if key in saved]
        order = [child.get('nativeSiblingIndex') for child in children]
        if None in order or order != sorted(set(order)):
            issues.append(f'{identity}: sibling ordering missing or changed')
        if any(child.get('nativeParentName') != actual['hierarchy'] for child in children):
            issues.append(f'{identity}: parent differs')
        before = initial.get(identity, {})
        for field in ('position', 'size', 'scale', 'pivot', 'rotation'):
            left, right = before.get(field, []), actual[field]
            if len(left) != len(right) or any(abs(a-b) > .01 for a, b in zip(left, right)):
                issues.append(f'{identity}: saved {field} differs from settled layout')
        if any(abs(a-b) > .01 for a, b in zip(node['position'], actual['position'])):
            moved.append(identity)
    sprites = [c for c in plan['components'] if c['node'] in saved and c['type'] == 'cc.Sprite']
    gaps = [c['sourceId'] for c in sprites if not c['convertible'] or not c.get('spriteFrame')]
    objects = serialized_objects(asset)
    verified_parents, parent_errors = check_parent_links(objects, saved, authored, receipt['guid'])
    issues.extend(parent_errors)
    bindings, errors = check_images(project, objects, receipt, sprites, {t['id']: t for t in plan['textures']})
    issues.extend(errors)
    previews = {}
    for key in ('isolatedPreview', 'framedPreview'):
        path = receipt.get(key+'Path')
        if path:
            png = io.inside(project, path)
            if digest(png) != receipt.get(key+'Sha256'):
                raise ValueError(f'Changed preview: {png}')
            previews[key] = str(png)
    return dict(sourceId=spec['sourceId'], asset=str(asset), nodes=len(saved), sprites=len(sprites),
                packedFrameBindings=[c['sourceId'] for c in sprites if c['convertible'] and
                                     c.get('untrimmedGeometryPolicy') == 'creator24-packed-frame-insets'],
                verifiedSerializedParents=verified_parents, imageBindings=bindings, unresolvedSprites=gaps, authoredToSettledPositionChanges=moved,
                issues=issues, previews=previews)


def audit(projects, selection, output):
    items = json.loads(Path(selection).read_text())
    ids = [item['sourceId'] if isinstance(item, dict) else item for item in items]
    if not ids or len(set(ids)) != len(ids) or not all(isinstance(i, str) for i in ids):
        raise ValueError('Expected unique selected source IDs')
    wanted = set(ids)
    matches = defaultdict(list)
    projects = [Path(p).resolve() for p in projects]
    for project in projects:
        plan_path = project/'Assets/Game/Editor/Conversion/import-plan.json'
        plan = json.loads(plan_path.read_bytes())
        plan_hash = digest(plan_path)
        specs = {s['sourceId']: s for s in plan['sourcePrefabs']}
        for path in sorted((project/'Analysis/Readback/Prefabs').glob('*.json')):
            receipt = json.loads(path.read_bytes())
            sid = receipt['sourceId']
            if sid in wanted:
                matches[sid].append(inspect(project, plan, plan_hash, specs[sid], receipt))
    rows = [matches[sid][0] if len(matches[sid]) == 1 else
            dict(sourceId=sid, issues=[f'Expected one saved receipt, found {len(matches[sid])}'])
            for sid in ids]
    out = io.new_output(output, projects + [Path(selection).resolve()])
    report = dict(schema='monkey-prefab-presentation-audit/1', selected=len(ids), rows=rows,
                  structuralIssues=sum(bool(row['issues']) for row in rows))
    io.write_json(out/'audit.json', report)
    return report


def _ids(path):
    entries = json.loads(Path(path).read_text())
    return {entry['sourceId'] if isinstance(entry, dict) else entry for entry in entries}


def select(ir_path, limit, output, pool=None, exclude=None):
    """Freeze a deterministic sample of static Cocos UI prefabs by failure mode."""
    if limit < 1:
        raise ValueError('Expected a positive sample count')
    ir = io.stage_document(Path(ir_path))
    allowed = _ids(pool) if pool else None
    excluded = _ids(exclude) if exclude else set()
    frames = {row['sourceId']: row for row in ir['spriteFrames']}
    components = defaultdict(list)
    nodes = defaultdict(list)
    for row in ir['components']:
        components[row['node'].split('#')[0]].append(row)
    for row in ir['nodes']:
        nodes[row['sourceId'].split('#')[0]].append(row)
    buckets = defaultdict(list)
    for sid, tree in nodes.items():
        if sid in excluded or (allowed is not None and sid not in allowed):
            continue
        name = ir['sourceNames'].get(sid, {})
        if name.get('sourceType') != 'cc.Prefab' or not 2 <= len(tree) <= 130:
            continue
        items = components[sid]
        sprites = [c for c in items if c['type'] == 'cc.Sprite' and c.get('spriteFrame')]
        if not sprites:
            continue
        groups = set()
        for sprite in sprites:
            key = sprite['spriteFrame']
            frame = frames.get(ir.get('aliases', {}).get(key, key))
            if sprite['mode'] in (1, 2):
                groups.add('sliced' if sprite['mode'] == 1 else 'tiled')
                if frame and not sprite['trim'] and (frame['rect'][2:] != frame['originalSize'] or
                                                     frame['offset'] != [0, 0]):
                    groups.add('packed')
        if 'packed' not in groups and any(c['type'] == 'sp.Skeleton' for c in items):
            continue
        if any(c['type'] == 'cc.Layout' for c in items):
            groups.add('layout')
        if any(n['anchor'] != [.5, .5] for n in tree):
            groups.add('pivot')
        if len(tree) >= 10:
            groups.add('hierarchy')
        for group in groups:
            buckets[group].append(sid)
    selected = {}
    for group in ('packed', 'tiled', 'sliced', 'layout', 'pivot', 'hierarchy', 'additional'):
        candidates = buckets[group] if group != 'additional' else set().union(*buckets.values())
        quota = limit if group in ('hierarchy', 'additional') else max(1, limit * (10 if group == 'packed' else 8) // 50)
        available = sorted((sid for sid in candidates if sid not in selected),
                           key=lambda sid: hashlib.sha256(sid.encode()).digest())
        for sid in available[:min(quota, limit-len(selected))]:
            selected[sid] = dict(sample=len(selected)+1, sourceId=sid, group=group,
                                 path=ir['sourceNames'][sid]['logicalPath'])
    if len(selected) != limit:
        raise ValueError(f'Only {len(selected)} matching prefabs available for {limit} requested')
    out = io.new_output(output, [Path(p) for p in (ir_path, pool, exclude) if p])
    io.write_json(out/'selection.json', list(selected.values()))
    return len(selected)
