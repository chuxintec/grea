"""Fail-closed MonoBehaviour value checks shared by offline readers and field plans.

Schema provenance must be established by the caller. Byte consumption alone is
never evidence of field semantics. No assemblies or original code are executed.
"""
import math
import re


class SemanticError(ValueError):
    pass


def integer(value, bits=64, signed=True):
    if isinstance(value, dict) and set(value) == {'$type', 'decimal'} and value['$type'] == 'integer':
        value = value['decimal']
        if not isinstance(value,str): raise SemanticError('Tagged integer decimal must be a string')
    if isinstance(value, str) and re.fullmatch(r'-?(0|[1-9][0-9]*)', value) and value != '-0':
        value = int(value)
    if type(value) is not int or not (-(1 << (bits-1)) if signed else 0) <= value < (1 << (bits-1) if signed else 1 << bits):
        raise SemanticError('Invalid integer identity/value')
    return value


def pointer(value):
    if not isinstance(value, dict):
        raise SemanticError('Expected typed PPtr')
    if set(value) == {'m_FileID', 'm_PathID'}:
        fid, pid = value['m_FileID'], value['m_PathID']
    elif set(value) == {'$type', 'fileId', 'pathId'} and value['$type'] == 'UnityPPtr':
        fid, pid = value['fileId'], value['pathId']
    else:
        raise SemanticError('Expected exact PPtr shape')
    file_id = integer(fid, 32, True)
    if file_id < 0: raise SemanticError('Negative PPtr file ID')
    return file_id, integer(pid)


def array_data(node):
    children = node.get('children', [])
    if len(children) != 1 or children[0].get('type') != 'Array':
        raise SemanticError('Unsupported array schema')
    parts = children[0].get('children', [])
    if len(parts) != 2 or parts[0].get('name') != 'size' or parts[0].get('type') not in ('int', 'SInt32') or parts[1].get('name') != 'data':
        raise SemanticError('Invalid array size/data schema')
    return parts[1]


INTEGERS = {'char': (8, False), 'SInt8': (8, True), 'UInt8': (8, False),
            'short': (16, True), 'SInt16': (16, True), 'UInt16': (16, False), 'unsigned short': (16, False),
            'int': (32, True), 'SInt32': (32, True), 'UInt32': (32, False), 'unsigned int': (32, False),
            'SInt64': (64, True), 'long long': (64, True), 'UInt64': (64, False), 'unsigned long long': (64, False)}


def validate_value(node, value, location='$', depth=0):
    if depth > 64:
        raise SemanticError('Schema depth exceeded')
    typ = node.get('type')
    if typ == 'string':
        # A string's character array is different from an array of strings,
        # including when both malformed interpretations consume zero elements.
        if node.get('children') and array_data(node).get('type') != 'char':
            raise SemanticError(location + ': scalar string has non-character Array/data')
        if not isinstance(value, str):
            raise SemanticError(location + ': expected string')
    elif typ in ('vector', 'Array') or (len(node.get('children', [])) == 1 and node['children'][0].get('type') == 'Array'):
        data = array_data({'children': [node]}) if typ == 'Array' else array_data(node)
        if not isinstance(value, list) or len(value) > 250_000:
            raise SemanticError(location + ': expected bounded array')
        for i, item in enumerate(value):
            validate_value(data, item, location + '/' + str(i), depth+1)
    elif isinstance(typ, str) and re.fullmatch(r'PPtr<[^<>]+>', typ):
        pointer(value)
    elif typ in INTEGERS:
        # Numeric fields cannot silently accept decimal strings as values.
        if isinstance(value, str):
            raise SemanticError(location + ': string used as integer')
        integer(value, *INTEGERS[typ])
    elif typ == 'bool':
        if type(value) is not bool:
            raise SemanticError(location + ': expected bool')
    elif typ in ('float', 'double'):
        try:
            finite = type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise SemanticError(location + ': expected finite number')
    elif node.get('children'):
        children = node['children']
        names = [n['name'] for n in children]
        if not isinstance(value, dict) or len(names) != len(set(names)) or set(value) != set(names):
            raise SemanticError(location + ': struct fields differ from schema')
        for child in children:
            validate_value(child, value[child['name']], location + '/' + child['name'], depth+1)
    else:
        raise SemanticError(location + ': unsupported field type ' + str(typ))


def validate_component(shape, data, header):
    """Compare independently read native header pointers as well as typed fields."""
    validate_value(shape, data)
    for name in ('m_Script', 'm_GameObject'):
        if pointer(data.get(name)) != pointer(header.get(name)):
            raise SemanticError(name + ': independently read header identity differs')
    if 'm_Enabled' in data and (type(data['m_Enabled']) not in (int, bool) or data['m_Enabled'] not in (0, 1)):
        raise SemanticError('m_Enabled is not 0/1')


def normalized(value, node=None):
    if node is not None:
        typ = node['type']
        if typ == 'string': return value
        if re.fullmatch(r'PPtr<[^<>]+>',typ):
            fid, pid = pointer(value)
            return {'$type':'UnityPPtr','fileId':str(fid),'pathId':str(pid)}
        if isinstance(value,list):
            item = array_data({'children':[node]}) if typ == 'Array' else array_data(node)
            return [normalized(v,item) for v in value]
        if isinstance(value,dict) and node.get('children'):
            return {n['name']:normalized(value[n['name']],n) for n in node['children']}
        if isinstance(value,dict) and value.get('$type') == 'integer': return int(value['decimal'])
        return value
    if isinstance(value, dict):
        if set(value) == {'m_FileID', 'm_PathID'} or value.get('$type') == 'UnityPPtr':
            return {'$type': 'UnityPPtr', 'fileId': str(pointer(value)[0]), 'pathId': str(pointer(value)[1])}
        if value.get('$type') == 'integer':
            # Keep UInt64 lossless too; field schema checks signedness.
            return int(value['decimal'])
        return {k: normalized(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    return value
