"""Validate native static-carrier field evidence without declaring source completeness."""
from .io import diagnostic


_SCALAR_VALUE_KEYS = {
    'bool': ('boolValue',),
    'double': ('numberValue',),
    'string': ('stringValue',),
    'bool[]': ('boolValues',),
    'double[]': ('numberValues',),
    'string[]': ('stringValues',),
    'Color': ('colorR', 'colorG', 'colorB', 'colorA'),
    'UnityEngine.Object': ('refValue',),
    'UnityEngine.Object[]': ('refValues',),
}


def _record_leaves(field):
    rows = field.get('recordValues')
    if not isinstance(rows, list):
        return None
    leaves = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get('index') != row_index or not isinstance(row.get('fields'), list):
            return None
        for leaf in row['fields']:
            if not isinstance(leaf, dict):
                return None
            leaves.append((row_index, leaf))
    return leaves


def _compare_value(expected, actual):
    storage = expected.get('storageType')
    keys = _SCALAR_VALUE_KEYS.get(storage)
    if keys is None:
        return False, f'Unknown static field storage type: {storage!r}'
    if any(actual.get(key) != expected.get(key) for key in keys):
        return False, 'Static field value differs'
    if storage == 'UnityEngine.Object' and actual.get('referenceVerified') is not True:
        return False, 'Static object reference differs'
    if storage == 'UnityEngine.Object[]' and actual.get('referencesVerified') is not True:
        return False, 'Static object reference array differs'
    return True, None


def _compare_record_array(expected, actual):
    if (expected.get('elementKind') != 'record' or not expected.get('recordTypeName') or
            actual.get('elementKind') != 'record' or
            actual.get('recordTypeName') != expected.get('recordTypeName')):
        return False, 'Typed record array schema differs'
    expected_rows = expected.get('recordValues')
    actual_rows = actual.get('recordValues')
    if not isinstance(expected_rows, list) or not isinstance(actual_rows, list) or len(expected_rows) != len(actual_rows):
        return False, 'Typed record array shape differs'
    for i, (erow, arow) in enumerate(zip(expected_rows, actual_rows)):
        if (not isinstance(erow, dict) or not isinstance(arow, dict) or
                erow.get('index') != i or arow.get('index') != i):
            return False, 'Typed record array row order differs'
        efields, afields = erow.get('fields'), arow.get('fields')
        if not isinstance(efields, list) or not isinstance(afields, list) or len(efields) != len(afields):
            return False, 'Typed record field shape differs'
        for ef, af in zip(efields, afields):
            if not isinstance(ef, dict) or not isinstance(af, dict):
                return False, 'Typed record leaf is malformed'
            if any(af.get(key) != ef.get(key) for key in
                   ('fieldName', 'sourceFieldName', 'kind', 'storageType', 'referenceKind', 'nullExpected')):
                return False, 'Typed record leaf schema differs'
            ok, reason = _compare_value(ef, af)
            if not ok:
                return False, reason
    return True, None


def _record_array_errors(expected, actual):
    """Return every comparable record-array error instead of stopping at its first leaf."""
    if (expected.get('elementKind') != 'record' or not expected.get('recordTypeName') or
            actual.get('elementKind') != 'record' or
            actual.get('recordTypeName') != expected.get('recordTypeName')):
        return ['Typed record array schema differs']
    expected_rows = expected.get('recordValues')
    actual_rows = actual.get('recordValues')
    if not isinstance(expected_rows, list) or not isinstance(actual_rows, list):
        return ['Typed record array shape differs']
    errors = []
    if len(expected_rows) != len(actual_rows):
        errors.append('Typed record array shape differs')
    for i, erow in enumerate(expected_rows):
        if not isinstance(erow, dict) or erow.get('index') != i or not isinstance(erow.get('fields'), list):
            errors.append(f'Typed record array expected row {i} is malformed')
            continue
        if i >= len(actual_rows):
            continue
        arow = actual_rows[i]
        if not isinstance(arow, dict) or arow.get('index') != i or not isinstance(arow.get('fields'), list):
            errors.append(f'Typed record array row {i} is malformed')
            continue
        efields, afields = erow['fields'], arow['fields']
        if len(efields) != len(afields):
            errors.append(f'Typed record field shape differs at row {i}')
        actual_by_name = {}
        duplicate_names = set()
        for field in afields:
            if not isinstance(field, dict):
                continue
            name = field.get('fieldName')
            if name in actual_by_name:
                duplicate_names.add(name)
            actual_by_name[name] = field
        for leaf_index, expected_leaf in enumerate(efields):
            if not isinstance(expected_leaf, dict):
                errors.append(f'Typed record expected leaf is malformed at row {i}/{leaf_index}')
                continue
            name = expected_leaf.get('fieldName')
            actual_leaf = actual_by_name.get(name)
            if actual_leaf is None:
                errors.append(f'Typed record leaf is missing at row {i}/{name}')
                continue
            if name in duplicate_names:
                errors.append(f'Typed record leaf is duplicated at row {i}/{name}')
                continue
            if any(actual_leaf.get(key) != expected_leaf.get(key) for key in
                   ('fieldName', 'sourceFieldName', 'kind', 'storageType', 'referenceKind', 'nullExpected')):
                errors.append(f'Typed record leaf schema differs at row {i}/{name}')
                continue
            ok, reason = _compare_value(expected_leaf, actual_leaf)
            if not ok:
                errors.append(f'{reason} at row {i}/{expected_leaf.get("sourceFieldName") or name}')
    for i in range(len(expected_rows), len(actual_rows)):
        errors.append(f'Unexpected typed record array row {i}')
    return errors


def _expected_references(spec):
    result = []
    for field in spec.get('fields', []):
        storage = field.get('storageType')
        name = field.get('sourceFieldName')
        if storage == 'UnityEngine.Object' and not field.get('nullExpected'):
            result.append((name, field.get('refValue'), -1, None))
        elif storage == 'UnityEngine.Object[]':
            for index, ref in enumerate(field.get('refValues') or []):
                result.append((f'{name}[{index}]', ref, -1, None))
        elif field.get('elementKind') == 'record':
            leaves = _record_leaves(field)
            if leaves is None:
                return None
            for record_index, leaf in leaves:
                if leaf.get('storageType') == 'UnityEngine.Object' and not leaf.get('nullExpected'):
                    result.append((f'{name}[{record_index}].{leaf.get("sourceFieldName")}',
                                   leaf.get('refValue'), record_index, leaf.get('sourceFieldName')))
    return result


def verify(components, rows, asset_identity, target, owner):
    expected = {c['sourceId']: c['staticFieldBinding'] for c in components if c.get('staticFieldBinding')}
    if not expected and rows in (None, []):
        return []

    def gaps(messages):
        return [diagnostic('STATIC_FIELD_NATIVE_MISMATCH', owner, message, owner) for message in messages]

    if not isinstance(rows, list) or any(not isinstance(r, dict) or not isinstance(r.get('binding'), dict) for r in rows):
        return gaps(['Static field readback is absent'])
    actual = {}
    for row in rows:
        source_id = row['binding'].get('sourceId')
        if not isinstance(source_id, str) or not source_id or source_id in actual:
            return gaps(['Static component identities differ'])
        actual[source_id] = row
    if len(actual) != len(rows) or set(actual) != set(expected):
        return gaps(['Static component identities differ'])
    identities = set()
    failures = []
    for sid, spec in expected.items():
        row = actual[sid]
        binding = row['binding']
        identity = row.get('localFileId') if target == 'unity' else row.get('componentUuid')
        valid = type(identity) is int and identity != 0 if target == 'unity' else isinstance(identity, str) and bool(identity)
        if not valid or identity in identities:
            failures.append('Missing or duplicate persistent component identity: ' + sid)
        elif valid:
            identities.add(identity)
        if row.get('assetGuid' if target == 'unity' else 'assetUuid') != asset_identity or not asset_identity:
            failures.append('Carrier belongs to a different asset: ' + sid)
        if (binding.get('typeName') != spec['typeName'] or binding.get('nativeScriptGuid') != spec['scriptGuid'] or
                binding.get('nativeSourceId') != sid or binding.get('nativeIdentityVerified') is not True or
                binding.get('enabled') is not False or binding.get('fieldsVerified') is not True):
            failures.append('Saved carrier identity, disabled policy or fields differ: ' + sid)
        fields = binding.get('fields')
        if not isinstance(fields, list) or any(not isinstance(f, dict) for f in fields):
            failures.append('Missing fields: ' + sid)
            fields = []
        expected_fields = spec.get('fields') if isinstance(spec.get('fields'), list) else []
        by_name = {}
        duplicate_names = set()
        for field in fields:
            name = field.get('fieldName')
            if name in by_name:
                duplicate_names.add(name)
            by_name[name] = field
        expected_names = {f.get('fieldName') for f in expected_fields if isinstance(f, dict)}
        if duplicate_names or set(by_name) != expected_names:
            failures.append('Field coverage differs: ' + sid)
        for field_spec in spec['fields']:
            field_name = field_spec.get('fieldName')
            field = by_name.get(field_name)
            if field is None:
                continue
            if field_name in duplicate_names:
                failures.append(f'Duplicate field: {sid}/{field_name}')
                continue
            if any(field.get(k) != field_spec.get(k) for k in ('kind', 'storageType', 'sourceFieldName')):
                failures.append(f'Field schema differs: {sid}/{field_spec.get("sourceFieldName", field_name)}')
            if field_spec.get('elementKind') == 'record':
                record_errors = _record_array_errors(field_spec, field)
                failures.extend(f'{reason}: {sid}/{field_spec.get("sourceFieldName", field_name)}' for reason in record_errors)
            else:
                ok, reason = _compare_value(field_spec, field)
                if not ok:
                    failures.append(f'{reason}: {sid}/{field_spec.get("sourceFieldName", field_name)}')
        if target == 'unity':
            refs = row.get('references')
            wanted = _expected_references(spec)
            if wanted is None:
                failures.append('Typed record array reference shape is unknown: ' + sid)
            elif not isinstance(refs, list):
                failures.append('Persistent reference identities missing: ' + sid)
            else:
                remaining = list(refs)
                if len(refs) != len(wanted):
                    failures.append('Persistent reference identity count differs: ' + sid)
                for field_path, source_id, record_index, record_field in wanted:
                    match = next((ref for ref in remaining if isinstance(ref, dict) and
                                  ref.get('fieldPath', ref.get('field')) == field_path and
                                  ref.get('sourceId') == source_id and
                                  (record_index < 0 or (ref.get('recordIndex') == record_index and
                                                        ref.get('recordField') == record_field))), None)
                    if (match is None or match.get('persistent') is not True or not match.get('guid') or
                            type(match.get('localFileId')) is not int or match.get('localFileId') == 0):
                        failures.append('Persistent reference identity differs: ' + sid + '/' + field_path)
                        continue
                    remaining.remove(match)
    return gaps(failures)
