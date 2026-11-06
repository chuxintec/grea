"""Bind reviewed C# method translations to existing Unity component scripts.

The manifest pins a dump, ordered WASM segments, each method's native table
slot and body hash, the old script and GUID, and the reviewed replacement.
Only the .cs file is updated. Prefabs, their .meta files and the source
modules are never written. Rerunning an interrupted batch is safe.
"""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
import re

from .unity_visual_repair import replace_file, write_owned
from .wasm_code_semantics import _sleb
from .wasm_code_sources import _metadata_v29, _scan_wasm, _u32


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pinned(path, expected):
    data = path.read_bytes()
    if digest(data) != expected:
        raise ValueError(f'Input fingerprint mismatch: {path}')
    return data


def function_table(raw):
    """Read active table-zero segments with constant offsets. Later entries win."""
    table = {}
    pos = 8
    while pos < len(raw):
        section = raw[pos]
        size, start = _u32(raw, pos + 1, len(raw))
        pos = start + size
        if pos > len(raw):
            raise ValueError('Truncated WASM section')
        if section != 9:
            continue
        count, cursor = _u32(raw, start, pos)
        for _ in range(count):
            flags, cursor = _u32(raw, cursor, pos)
            if flags != 0 or cursor >= pos or raw[cursor] != 0x41:
                raise ValueError('Unsupported WASM element expression')
            offset, cursor = _sleb(raw, cursor + 1, 5)
            if cursor >= pos or raw[cursor] != 0x0b or not 0 <= offset <= 0x7fffffff:
                raise ValueError('Unsupported WASM table offset')
            length, cursor = _u32(raw, cursor + 1, pos)
            for slot in range(offset, offset + length):
                table[slot], cursor = _u32(raw, cursor, pos)
        if cursor != pos:
            raise ValueError('Invalid WASM element section length')
    return table


def owner_names(types, indices):
    """Join nested TypeDefs through their declaring IL2CPP type, not a guessed namespace."""
    by_value = {row['byvalTypeIndex']: row for row in types}
    result = {}
    for index in indices:
        if type(index) is not int or not 0 <= index < len(types):
            raise ValueError('Invalid IL2CPP type index')
        row = types[index]
        chain = []
        seen = set()
        while True:
            if row['index'] in seen:
                raise ValueError('Cycle in IL2CPP declaring types')
            seen.add(row['index'])
            chain.append(row['name'])
            declaring = row['declaringIl2CppTypeIndex']
            if declaring == -1:
                break
            if declaring not in by_value:
                raise ValueError('Unknown IL2CPP declaring type')
            row = by_value[declaring]
        result[index] = (row['namespace'], '.'.join(reversed(chain)))
    return result


def declarations(dump, selected):
    rows = {}
    owners = {}
    for block in re.split(r'^// Namespace: ', dump, flags=re.M)[1:]:
        namespace, _, body = block.partition('\n')
        cls = re.search(r'^.*?\b(?:class|struct) ([^\s:]+).*?// TypeDefIndex: (\d+)\s*$', body, re.M)
        if cls is None:
            continue
        index = int(cls[2])
        if index not in selected:
            continue
        outer_namespace, display_name = selected[index]
        if cls[1] != display_name or namespace.strip() not in (outer_namespace, '' if '.' in display_name else outer_namespace):
            raise ValueError(f'Dump type disagrees with metadata: {cls[1]}')
        name = '.'.join(filter(None, (outer_namespace, display_name)))
        owners[name, int(cls[2])] = {
            int(offset, 16): (kind,field) for kind, field, offset in
            re.findall(r'^\s*(?:public|private|protected|internal) (bool|int|float|Vector2|Color) (\w+); // 0x([0-9a-fA-F]+)',body,re.M)
        }
        for kind, prop, offset in re.findall(
                r'^\s*private (bool|int|float|Vector2|Color) <(\w+)>k__BackingField; // 0x([0-9a-fA-F]+)', body, re.M):
            owners[name, index][int(offset, 16)] = (kind, 'recoveredBacking_' + prop)
        signatures = re.findall(r'// RVA: (0x[\dA-Fa-f]+|-1)[^\n]*\n\s*([^\n]+)', body)
        for ordinal, (slot, signature) in enumerate(signatures):
            if slot != '-1':
                key = (name, int(cls[2]), signature.strip())
                if key in rows:
                    raise ValueError(f'Duplicate method declaration: {key}')
                rows[key] = int(slot, 16), ordinal
    return rows, owners


def _access(body, cursor, opcode):
    if body[cursor:cursor+2] != bytes((opcode, 0)):
        raise ValueError('Expected byte field access with natural alignment')
    return _u32(body, cursor+2, len(body))


def lift_bool_accessor(body, fields, signature):
    """Translate a complete IL2CPP instance bool accessor, rejecting extra instructions."""
    def field(offset):
        if offset not in fields:
            raise ValueError(f'Unknown bool field at byte offset {offset}')
        return fields[offset]

    getter = bytes.fromhex('002000')
    setter = bytes.fromhex('0020002001')
    conditional = bytes.fromhex('0020012000')
    if body.startswith(getter) and re.search(r'\bbool get_\w+\(\)',signature) and 'static ' not in signature:
        offset, end = _access(body, len(getter), 0x2d)
        if body[end:] in (b'\x0b', b'\x0f\x0b'):
            return f'return {field(offset)};'
    is_setter = re.search(r'\bvoid set_\w+\(bool \w+\)',signature) and 'static ' not in signature
    if body.startswith(setter) and is_setter:
        offset, end = _access(body, len(setter), 0x3a)
        if body[end:] == b'\x0b':
            return f'{field(offset)}=value;'
    if body.startswith(conditional) and is_setter:
        offset, end = _access(body, len(conditional), 0x2d)
        branch = bytes.fromhex('47044020004101')
        if body[end:end+len(branch)] == branch:
            dirty, end = _access(body, end+len(branch), 0x3a)
            if body[end:end+4] == bytes.fromhex('20002001'):
                written, end = _access(body, end+4, 0x3a)
                if written==offset and dirty!=offset and body[end:] == b'\x0b\x0b':
                    return f'if(value!={field(offset)}){{{field(dirty)}=true;{field(offset)}=value;}}'
    raise ValueError('Unsupported bool accessor body or signature')


def lift_numeric_accessor(body, fields, signature):
    """Lift complete int32/float32 properties, including a mirrored int-to-float store."""
    if 'static ' in signature or not body.startswith(bytes.fromhex('002000')):
        raise ValueError('Expected an instance numeric accessor')
    getter = re.search(r'\b(int|float) get_\w+\(\)', signature)
    setter = re.search(r'\bvoid set_\w+\((int|float) \w+\)', signature)
    if not getter and not setter:
        raise ValueError('Unsupported numeric signature')
    kind = (getter or setter)[1]

    def access(cursor, opcode, expected):
        if body[cursor:cursor+2] != bytes((opcode, 2)):
            raise ValueError('Unsupported numeric field instruction or alignment')
        offset, cursor = _u32(body, cursor+2, len(body))
        target = fields.get(offset)
        if not target or target[0] != expected:
            raise ValueError(f'No matching {expected} field at offset {offset}')
        return target[1], cursor

    if getter:
        field, cursor = access(3, 0x28 if kind == 'int' else 0x2a, kind)
        if body[cursor:] in (b'\x0b', b'\x0f\x0b'):
            return f'return {field};'
    elif body[3:5] == b'\x20\x01':
        field, cursor = access(5, 0x36 if kind == 'int' else 0x38, kind)
        if body[cursor:] == b'\x0b':
            return f'{field}=value;'
        mirror = bytes.fromhex('20002001b2')
        if kind == 'int' and body[cursor:cursor+len(mirror)] == mirror:
            second, cursor = access(cursor+len(mirror), 0x38, 'float')
            if body[cursor:] == b'\x0b':
                return f'{field}=value;{second}=value;'
    raise ValueError('Unsupported numeric accessor instructions')


def lift_struct_getter(body, fields, signature):
    """Match an entire IL2CPP hidden-return copy of one Vector2 or Color field."""
    match = re.search(r'\b(Vector2|Color) get_\w+\(\)', signature)
    if not match or 'static ' in signature or not body.startswith(bytes.fromhex('01017e')):
        raise ValueError('Expected a struct getter with one i64 temporary')
    words = 2 if match[1] == 'Vector2' else 4
    cursor = 3
    def consume(hex_bytes):
        nonlocal cursor
        instruction = bytes.fromhex(hex_bytes)
        if not body.startswith(instruction, cursor):
            raise ValueError('Unexpected struct copy instruction')
        cursor += len(instruction)

    base = None
    for pair in range(0, words, 2):
        for word in (pair, pair + 1):
            consume('20012802')  # load from this
            offset, cursor = _u32(body, cursor, len(body))
            if base is None:
                base = offset
            if offset != base + word * 4:
                raise ValueError('Noncontiguous source field')
            consume('ad')
        consume('422086842103')  # pack both words into the i64 temporary
        for word in (pair, pair + 1):
            consume('20002003' if word == pair else '20002003422088')
            consume('a73602')
            offset, cursor = _u32(body, cursor, len(body))
            if offset != word * 4:
                raise ValueError('Unexpected return buffer offset')
    field = fields.get(base)
    if body[cursor:] != b'\x0b' or not field or field[0] != match[1]:
        raise ValueError('Struct copy must exactly match the declared field')
    return f'return {field[1]};'


def lift_float_expression(body, fields, signature):
    """Lift side-effect-free f32 expressions using only named float arguments."""
    declaration = re.search(r'\bstatic float \w+\(([^()]*)\)', signature)
    if not declaration or not body.startswith(b'\x00') or len(body) > 256:
        raise ValueError('Expected a small static float expression without locals')
    parameters = []
    for arg in declaration[1].split(',') if declaration[1] else ():
        match = re.fullmatch(r'float ([@a-zA-Z_]\w*)(?: = -?\d+(?:\.\d+)?)?', arg.strip())
        if not match:
            raise ValueError('Expected a named float argument')
        parameters.append(match[1])
    stack = []
    cursor = 1
    operations = {0x92: '+', 0x93: '-', 0x94: '*', 0x95: '/'}
    while cursor < len(body):
        op = body[cursor]
        cursor += 1
        if op == 0x20:
            index, cursor = _u32(body, cursor, len(body))
            if index >= len(parameters):
                raise ValueError('Float expression reads an unknown local')
            stack.append(parameters[index])
        elif op == 0x43 and cursor + 4 <= len(body):
            value = struct.unpack_from('<f', body, cursor)[0]
            if not math.isfinite(value):
                raise ValueError('Unsupported float literal')
            stack.append(format(value, '.9g') + 'f')
            cursor += 4
        elif op == 0x8c and stack:
            operand = stack.pop()
            if operand.startswith('-'):
                operand = f'({operand})'
            stack.append(f'(-{operand})')
        elif op in operations and len(stack) >= 2:
            right = stack.pop()
            left = stack.pop()
            stack.append(f'({left} {operations[op]} {right})')
        elif ((op == 0x0b and cursor == len(body))
              or (op == 0x0f and body[cursor:] == b'\x0b')) and len(stack) == 1:
            return f'return {stack[0]};'
        else:
            raise ValueError('Unsupported float expression instruction or stack')
    raise ValueError('Missing float expression return')


def lift_void_noop(body, _fields, signature):
    """Recognize a complete empty WASM body with no locals or side effects."""
    declaration = re.fullmatch(r'[^()]*\bvoid\s+[A-Za-z_]\w*\(([^()]*)\)\s*\{\s*\}', signature)
    if (not declaration or re.search(r'\bout\s+', declaration[1])
            or not re.fullmatch(rb'\x00\x01*\x0b', body)):
        raise ValueError('Expected a complete empty void method')
    return 'return;'


def _translate_method(method, row, metadata, declared, fields, functions, replacement):
    owner = method.get('type', row['type']), method.get('typeIndex', row['typeIndex'])
    method_index = method['metadataMethodIndex']
    if not (0 <= owner[1] < len(metadata['types']) and 0 <= method_index < len(metadata['methods'])):
        raise ValueError('Invalid IL2CPP type or method index')
    type_row = metadata['types'][owner[1]]
    method_row = metadata['methods'][method_index]
    full_name = metadata['qualifiedNames'][owner[1]]
    method_name = method['signature'].partition('(')[0].split()[-1]
    ordinal = method_index - type_row['methodStart']
    if (owner[0] != full_name or method_row['token'] != method['token']
            or method_row['name'] != method_name or method_row['declaringType'] != owner[1]
            or not 0 <= ordinal < type_row['methodCount']):
        raise ValueError(f'Metadata owner or method identity mismatch: {method_name}')
    slot, dump_ordinal = declared.get((*owner, method['signature']), (None, None))
    if ordinal != dump_ordinal:
        raise ValueError(f'Method overload mismatch: {method_name}')
    body, raw, module_hash = functions.get(slot, (None, None, None))
    if (slot != method['slot'] or not body or body['sha256'] != method['sha256']
            or module_hash != method['segmentSha256'] or body['functionIndex'] != method['functionIndex']):
        raise ValueError(f'Method declaration or body mismatch: {method_name}')
    if 'lift' not in method:
        return replacement
    if method['lift'] not in ('bool-accessor','numeric-accessor','struct-getter','float-expression','void-noop'):
        raise ValueError(f'Unsupported method lift: {method["lift"]}')
    token = f'/*wasm:{method_index}*/'.encode()
    if replacement.count(token) != 1:
        raise ValueError(f'Expected exactly one translation token for {method_name}')
    start = body['offset']
    code = raw[start:start + body['bytes']]
    if method['lift'] == 'void-noop':
        lifted = lift_void_noop(code, fields[owner], method['signature'])
    elif method['lift'] == 'numeric-accessor':
        lifted = lift_numeric_accessor(code, fields[owner], method['signature'])
    elif method['lift'] == 'float-expression':
        lifted = lift_float_expression(code, fields[owner], method['signature'])
    elif method['lift'] == 'struct-getter':
        lifted = lift_struct_getter(code, fields[owner], method['signature'])
    else:
        bool_fields = {k:name for k,(kind,name) in fields[owner].items() if kind=='bool'}
        lifted = lift_bool_accessor(code, bool_fields, method['signature'])
    return replacement.replace(token, lifted.encode())


def _source_evidence(base, spec, indices):
    if not spec['segments']:
        raise ValueError('Expected an ordered WASM segment list')
    metadata = _metadata_v29(pinned(base / spec['metadata']['path'],spec['metadata']['sha256']))
    selected = owner_names(metadata['types'], indices)
    metadata['qualifiedNames'] = {index: '.'.join(filter(None, pieces)) for index, pieces in selected.items()}
    declared, fields = declarations(pinned(base / spec['dump']['path'], spec['dump']['sha256']).decode('utf-8-sig'), selected)
    functions = {}
    for segment in spec['segments']:
        raw = pinned(base / segment['path'], segment['sha256'])
        bodies, _, _ = _scan_wasm(raw)
        by_index = {body['functionIndex']: body for body in bodies}
        for slot, index in function_table(raw).items():
            functions[slot] = (by_index.get(index), raw, segment['sha256'])
    return metadata, declared, fields, functions


def _exclude_overlays(spec, records, paths):
    """Subtract matching method identities only within the selected source scope."""
    by_index = {r['metadataMethodIndex']: r for r in records}
    selected_types = {r['typeIndex'] for r in spec['types']}
    excluded = set()
    pins = [seg['sha256'] for seg in spec['segments']]
    for path in paths:
        overlay = json.loads(Path(path).read_text())
        if (overlay['metadata']['sha256'] != spec['metadata']['sha256']
                or overlay['dump']['sha256'] != spec['dump']['sha256']
                or [s['sha256'] for s in overlay['segments']] != pins):
            raise ValueError(f'Prior overlay belongs to different source inputs: {path}')
        for script in overlay['scripts']:
            for method in script['methods']:
                owner = method.get('typeIndex', script['typeIndex'])
                index = method['metadataMethodIndex']
                if owner not in selected_types and index not in by_index:
                    continue
                record = by_index.get(index)
                if (not record or record['typeIndex'] != owner
                        or record['type'] != method.get('type', script['type'])
                        or any(record.get(k) != method[k] for k in (
                            'token','signature','slot','segmentSha256','functionIndex','sha256'))):
                    raise ValueError(f'Prior overlay method identity differs: {path} / {index}')
                excluded.add(index)
    return [r for r in records if r['metadataMethodIndex'] not in excluded]


def inventory(manifest, output, *, exclude_overlays=(), include_body_bytes=False):
    """Inventory all methods of selected TypeDefs without writing candidate scripts."""
    path = Path(manifest).resolve()
    spec = json.loads(path.read_text())
    requested = spec['types']
    indices = {row['typeIndex'] for row in requested}
    if not indices or len(indices) != len(requested):
        raise ValueError('Expected a nonempty, distinct list of TypeDefs')
    metadata, declared, fields, functions = _source_evidence(path.parent, spec, indices)
    by_ordinal = {(index, ordinal): (signature, slot) for (_, index, signature), (slot, ordinal) in declared.items()}
    records = []
    for selection in requested:
        index = selection['typeIndex']
        owner = metadata['qualifiedNames'][index], index
        if selection['type'] != owner[0]:
            raise ValueError(f'Selected type disagrees with metadata: {owner}')
        row = metadata['types'][index]
        for ordinal in range(row['methodCount']):
            mi = row['methodStart'] + ordinal
            method = metadata['methods'][mi]
            record = dict(type=owner[0], typeIndex=index, name=method['name'], token=method['token'],
                          metadataMethodIndex=mi, status='unresolved')
            records.append(record)
            slot_row = by_ordinal.get((index, ordinal))
            if slot_row is None:
                record['reason'] = 'no-addressed-declaration'
                continue
            signature, slot = slot_row
            if method['declaringType'] != index or signature.partition('(')[0].split()[-1] != method['name']:
                raise ValueError(f'Method ordinal disagrees with metadata: {owner} / {mi}')
            record.update(signature=signature, slot=slot)
            body, raw, module_hash = functions.get(slot, (None, None, None))
            if not body:
                record['reason'] = 'no-local-body-at-slot'
                continue
            record.update(status='needs-review', segmentSha256=module_hash, functionIndex=body['functionIndex'],
                          sha256=body['sha256'])
            code = raw[body['offset']:body['offset']+body['bytes']]
            owner_fields = fields[owner]
            bool_fields = {offset:name for offset,(kind,name) in owner_fields.items() if kind=='bool'}
            candidates = [('void-noop', lift_void_noop, owner_fields), ('float-expression', lift_float_expression, owner_fields)]
            if method['name'].startswith(('get_', 'set_')):
                candidates.extend([('bool-accessor',lift_bool_accessor,bool_fields),
                                       ('numeric-accessor',lift_numeric_accessor,owner_fields),
                                       ('struct-getter',lift_struct_getter,owner_fields)])
            for kind, lift, layout in candidates:
                try:
                    expression = lift(code, layout, signature)
                except ValueError:
                    continue
                record.update(status='automatic', lift=kind, source=expression)
                break
    selected_count = len(records)
    if exclude_overlays:
        records = _exclude_overlays(spec, records, exclude_overlays)
    if include_body_bytes:
        for record in records:
            if 'sha256' not in record:
                continue
            body, raw, _ = functions[record['slot']]
            offset = body['offset']
            code = raw[offset:offset + body['bytes']]
            if digest(code) != record['sha256']:
                raise ValueError(f"WASM body hash mismatch at slot {record['slot']}")
            record.update(bodyOffset=offset, bodyHex=code.hex())
    report = dict(metadataSha256=spec['metadata']['sha256'], dumpSha256=spec['dump']['sha256'],
                  segmentHashes=[s['sha256'] for s in spec['segments']], methods=records)
    if exclude_overlays:
        report.update(selectedMethods=selected_count, excludedMethods=selected_count-len(records))
    write_owned(Path(output), json.dumps(report, indent=2, ensure_ascii=False).encode())
    return dict(methods=len(records), automatic=sum(r['status']=='automatic' for r in records),
                unresolved=sum(r['status']=='unresolved' for r in records), output=str(output))


def native_signature(script, method):
    """Preserve dump parameter types and by-reference direction for Editor readback."""
    signature = method['signature']
    match = re.fullmatch(r'([^()]+)\((.*)\)\s*\{\s*\}', signature)
    if not match:
        raise ValueError(f'Unsupported native method signature: {signature}')
    head = match[1].strip().rsplit(None, 1)
    if len(head) != 2:
        raise ValueError(f'Missing return type or method name: {signature}')
    modifiers_and_return, name = head
    result = re.sub(r'^(?:(?:public|private|internal|protected|static|abstract|new|virtual|override|sealed|extern|unsafe)\s+)+', '', modifiers_and_return)
    result = re.sub(r'\s+', '', result)
    params = []
    current = []
    depth = 0
    quote = None
    escaped = False
    for char in match[2] + ',':
        if char == ',' and depth == 0 and quote is None:
            arg = ''.join(current).strip()
            current.clear()
            if arg:
                decl = arg.partition('=')[0].strip()
                part = re.fullmatch(r'(.+?)\s+@?\w+', decl)
                # Roslyn may omit the metadata name of a local function's closure parameter.
                if re.fullmatch(r'ref [\w.]+\.<>c__DisplayClass\d+_\d+', decl):
                    parameter_type = decl
                elif part:
                    parameter_type = part[1].removeprefix('params ').strip()
                else:
                    raise ValueError(f'Unsupported native parameter: {decl}')
                direction = re.match(r'(ref|out|in)\s+', parameter_type)
                prefix = direction[1] + ' ' if direction else ''
                if direction:
                    parameter_type = parameter_type[direction.end():]
                params.append(prefix + re.sub(r'\s+', '', parameter_type))
            continue
        current.append(char)
        if quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif char in '<[(':
            depth += 1
        elif char in '>])':
            depth -= 1
    if depth or quote or current:
        raise ValueError(f'Unsupported native method signature: {signature}')
    return dict(scriptGuid=script['guid'], owner=method.get('type',script['type']),
                index=method['metadataMethodIndex'], name=name, result=result,
                isStatic='static' in modifiers_and_return.split() or name=='.cctor', parameters=params)


def write_native_signatures(project, methods):
    """Extend an immutable baseline without replacing a previous batch's expectations."""
    baseline = project / 'expected-method-signatures.json'
    folder = project / 'expected-method-signatures.d'
    by_key = {}
    additions = {}
    if not baseline.exists() and any(folder.glob('*.json')):
        raise ValueError(f'Missing baseline for existing native signatures: {baseline}')
    if baseline.exists():
        records = json.loads(baseline.read_text())['methods']
        if not records:
            raise ValueError(f'Empty native signature baseline: {baseline}')
        for record in records:
            key = (record['scriptGuid'], record['index'])
            if key in by_key and record != by_key[key]:
                raise ValueError(f'Conflicting baseline overload: {key}')
            by_key[key] = record
    for record in methods:
        key = (record['scriptGuid'], record['index'])
        if key in by_key:
            if record != by_key[key]:
                raise ValueError(f'Conflicting compiled overload: {key}')
            continue
        by_key[key] = record
        item = folder / f'{key[0]}-{key[1]}.json'
        data = json.dumps(dict(methods=[record]), indent=2).encode()
        if item.exists() and item.read_bytes() != data:
            raise ValueError(f'Conflicting generated asset: {item}')
        additions[item] = data

    if not baseline.exists():
        write_owned(baseline, json.dumps(dict(methods=list(by_key.values())), indent=2).encode())
    else:
        for path, data in additions.items():
            write_owned(path, data)


def apply(project, manifest, *, native_signatures=False):
    project, manifest = Path(project).resolve(), Path(manifest).resolve()
    spec = json.loads(manifest.read_text())
    if not spec['scripts']:
        raise ValueError('Expected a nonempty script batch')
    base = manifest.parent
    indices = {method.get('typeIndex',row['typeIndex']) for row in spec['scripts'] for method in row['methods']}
    metadata, declared, fields, functions = _source_evidence(base, spec, indices)
    changes = {}
    for row in spec['scripts']:
        target = (project / row['asset']).resolve()
        if (not target.is_relative_to(project / 'Assets') or target.suffix != '.cs' or target in changes
                or row['type'].split('.')[-1] != target.stem):
            raise ValueError(f'Invalid or duplicate script path: {target}')
        meta = Path(str(target) + '.meta').read_text()
        if not re.fullmatch(r'[0-9a-f]{32}',row['guid']) or not re.search(r'^guid: '+re.escape(row['guid'])+r'$', meta, re.M):
            raise ValueError(f'Component GUID mismatch: {target}')
        replacement = pinned(base / row['translation'], row.get('templateSha256',row['after']))
        before = digest(target.read_bytes())
        if before not in (row['before'], row['after']):
            raise ValueError(f'Component source has changed: {target}')
        if not row['methods']:
            raise ValueError(f'No reviewed methods for {target}')
        for method in row['methods']:
            replacement = _translate_method(method, row, metadata, declared, fields, functions, replacement)
        if digest(replacement)!=row['after']:
            raise ValueError(f'Reconstructed script fingerprint mismatch: {target}')
        changes[target] = (before, replacement)
    if native_signatures:
        methods = [native_signature(script, method) for script in spec['scripts'] for method in script['methods']]
        write_native_signatures(project, methods)
    for target, (before, replacement) in changes.items():
        current = digest(target.read_bytes())
        if current == digest(replacement):
            continue
        if current != before:
            raise ValueError(f'Concurrent edit: {target}')
        replace_file(target, replacement)
    return {'scripts': len(changes), 'methods': sum(len(s['methods']) for s in spec['scripts'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--native-signatures', action='store_true')
    args = parser.parse_args()
    print(json.dumps(apply(args.project, args.manifest, native_signatures=args.native_signatures)))


if __name__ == '__main__':
    main()
