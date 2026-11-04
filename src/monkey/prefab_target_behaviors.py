"""Plan and emit source-bound native behavior files; no runtime source graph."""
import math
import re
from pathlib import Path
from .io import inside, read, sha, write_json
from .sources.compiled import fail

PREFIX = {'unity': 'Assets/Game/Scripts/Presentation/Recovered/',
          'creator': 'assets/Game/Scripts/Presentation/Recovered/'}


def identity(namespace, target, path):
    from .targets import unity, cocos
    return (unity.guid if target == 'unity' else cocos.identity)(namespace, 'prefab-behavior/' + path)


def binding(component, target, namespace):
    row = component.get('nativeBehavior', {}).get('targets', {}).get(target, {})
    if row.get('status') not in ('lowered', 'lowered_with_gaps'):
        return None
    if row.get('requiredProviders'):
        return None
    path = row.get('scriptPath', '')
    if not path.startswith(PREFIX[target]) or Path(path).name != row['component'] + ('.cs' if target == 'unity' else '.ts'):
        fail('BEHAVIOR_TARGET_PATH', component['sourceId'], 'Unexpected generated script path')
    fields = []
    for field in row.get('fields', []):
        name, kind, value = field['name'], field['type'], field['value']
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) or not field.get('valueValidated'):
            fail('BEHAVIOR_FIELD_CONTRACT', component['sourceId'], 'Unvalidated source field')
        if kind == 'float' and type(value) in (int, float) and math.isfinite(value):
            fields.append(dict(name=name, type=kind, numberValue=value))
        elif kind == 'bool' and type(value) is bool:
            fields.append(dict(name=name, type=kind, boolValue=value))
        else:
            fail('BEHAVIOR_FIELD_CONTRACT', component['sourceId'], 'Unsupported native field type')
    return dict(typeName=row['nativeType'], scriptGuid=identity(namespace, target, path),
                fields=fields, runtimeComplete=False, scriptPath=path,
                scriptSha256=row['scriptSha256'], gaps=row.get('unsupportedBehaviors', []))


def prepare(ir, ir_root, target, namespace, output):
    rows = []
    seen = set()
    for item in ir.get('emittedBehaviorScripts', []):
        if item['target'] != target:
            continue
        path = item['targetPath']
        if not path.startswith(PREFIX[target]) or '/' in path.removeprefix(PREFIX[target]) or path in seen:
            fail('BEHAVIOR_TARGET_PATH', path, 'Unexpected or duplicate script destination')
        seen.add(path)
        raw = read(inside(ir_root, item['artifactPath']))
        if sha(raw) != item['sha256']:
            fail('BEHAVIOR_SCRIPT_CHANGED', path, 'Generated script bytes changed')
        relative = 'behavior-scripts/' + Path(path).name
        dest = inside(output, relative); dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(raw)
        rows.append(dict(source=relative, target=path, sha256=item['sha256'],
                         identity=identity(namespace, target, path)))
    return rows


def emit(plan, plan_root, target, output):
    from .targets.cocos import meta
    for item in plan.get('behaviorScripts', []):
        raw = read(inside(plan_root, item['source']))
        if sha(raw) != item['sha256'] or not item['target'].startswith(PREFIX[target]):
            fail('BEHAVIOR_SCRIPT_CHANGED', item['target'], 'Owned script or destination changed')
        dest = inside(output, item['target'])
        if dest.exists():
            fail('BEHAVIOR_SCRIPT_COLLISION', item['target'], 'Refuse to replace an asset')
        dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(raw)
        metadata = Path(str(dest) + '.meta')
        if target == 'unity':
            metadata.write_text('fileFormatVersion: 2\nguid: ' + item['identity'] + '\n')
        else:
            write_json(metadata, meta(item['identity'], 'typescript', '4.0.24'))


def verify_bindings(components, rows, asset_identity, target, owner):
    """Verify persisted declarations, without promoting their runtime status."""
    from .io import diagnostic
    import struct
    expected = {c['sourceId']: c for c in components if c.get('convertible') and c.get('behaviorBinding')}
    if not expected and rows in (None, []):
        return []
    def gap(message):
        return [diagnostic('BEHAVIOR_NATIVE_BINDING_MISMATCH', owner, message)]
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return gap('Persistent behavior readback is absent')
    actual = {row.get('sourceId'): row for row in rows}
    if len(actual) != len(rows) or set(actual) != set(expected):
        return gap('Persistent behavior source identities differ')
    native_ids = set()
    for source_id, component in expected.items():
        row, spec = actual[source_id], component['behaviorBinding']
        local_id = row.get('localFileId')
        valid_id = (type(local_id) is int and local_id != 0) if target == 'unity' else (isinstance(local_id, str) and bool(local_id))
        if not valid_id or local_id in native_ids:
            return gap('Persistent component identities are absent or duplicated')
        native_ids.add(local_id)
        if (row.get('assetGuid') != asset_identity or not asset_identity or
                row.get('typeName') != spec['typeName'] or row.get('scriptGuid') != spec['scriptGuid'] or
                row.get('fieldsVerified') is not True or row.get('enabled') is not component['enabled']):
            return gap('Saved behavior type, asset, script or enabled state differs: ' + source_id)
        fields = row.get('fields')
        if not isinstance(fields, list) or any(not isinstance(f, dict) for f in fields):
            return gap('Saved fields are absent: ' + source_id)
        by_name = {f.get('name'): f for f in fields}
        if len(by_name) != len(fields) or set(by_name) != {f['name'] for f in spec['fields']}:
            return gap('Saved field identities differ: ' + source_id)
        for field in spec['fields']:
            observed = by_name[field['name']]
            key = 'numberValue' if field['type'] == 'float' else 'boolValue'
            value = field[key]
            if field['type'] == 'float' and target == 'unity':
                value = struct.unpack('f', struct.pack('f', value))[0]
            typed = type(observed.get(key)) in (int, float) if field['type'] == 'float' else type(observed.get(key)) is bool
            if observed.get('type') != field['type'] or not typed or observed[key] != value:
                return gap('Saved field value differs: ' + source_id + '/' + field['name'])
    return []
