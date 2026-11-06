"""Bounded structural validation for native Unity code architecture plans.

This validates design identity, layer edges, source coverage, and integration
shape. It does not generate code or claim that planned code compiles or restores
source behavior.
"""
import re
from pathlib import PurePosixPath

from monkey.sources import compiled


SCHEMA_VERSION = 'monkey-native-code-architecture/1'
LAYERS = ('Domain', 'Gameplay', 'Presentation', 'Services', 'Bootstrap')
KINDS = ('class', 'struct', 'interface', 'enum', 'record')
DISPOSITIONS = ('planned', 'native-replacement', 'existing-implementation', 'evidence-only', 'blocked')
ALLOWED_LAYER_DEPENDENCIES = {
    'Domain': ['Domain'],
    'Gameplay': ['Domain', 'Gameplay'],
    'Presentation': ['Domain', 'Gameplay', 'Presentation'],
    'Services': ['Domain', 'Gameplay', 'Services'],
    'Bootstrap': ['Domain', 'Gameplay', 'Presentation', 'Services', 'Bootstrap'],
}
ASSEMBLY_REFERENCES = {
    'Domain': [],
    'Gameplay': ['Domain'],
    'Presentation': ['Domain', 'Gameplay'],
    'Services': ['Domain', 'Gameplay'],
    'Bootstrap': ['Domain', 'Gameplay', 'Presentation', 'Services'],
}

_IDENTIFIER = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_SHA256 = re.compile(r'^[0-9a-f]{64}$')
_KEYWORDS = frozenset('''abstract as base bool break byte case catch char checked class const
    continue decimal default delegate do double else enum event explicit extern false finally
    fixed float for foreach goto if implicit in int interface internal is lock long namespace
    new null object operator out override params private protected public readonly ref return
    sbyte sealed short sizeof stackalloc static string struct switch this throw true try typeof
    uint ulong unchecked unsafe ushort using virtual void volatile while add alias ascending
    async await by descending dynamic equals from get global group init into join let managed
    nameof nint not notnull nuint on or orderby partial record remove select set unmanaged value
    var when where with yield'''.split())
_UNITY_TYPE = re.compile(r'(^|[^A-Za-z0-9_])(?:UnityEngine|UnityEditor|MonoBehaviour|ScriptableObject)([^A-Za-z0-9_]|$)', re.I)
_DYNAMIC = re.compile(r'(^|[^A-Za-z0-9_])dynamic([^A-Za-z0-9_]|$)', re.I)
_OBJECT_MAP = re.compile(r'Dictionary\s*<\s*string\s*,\s*object\s*>', re.I)
_MAX_NODES = 8_000_000
_MAX_DEPTH = 96


def _fail(location, message):
    compiled.fail('CODE_ARCHITECTURE_CONTRACT', location, message)


def _object(value, location):
    if not isinstance(value, dict):
        _fail(location, 'Expected an object')
    return value


def _array(value, location):
    if not isinstance(value, list):
        _fail(location, 'Expected an array')
    return value


def _text(value, location, *, nonempty=True):
    if not isinstance(value, str) or (nonempty and not value.strip()):
        _fail(location, 'Expected a non-empty string' if nonempty else 'Expected a string')
    try:
        value.encode('utf-8')
    except UnicodeError:
        _fail(location, 'Invalid Unicode string')
    return value


def _identifier(value, location):
    value = _text(value, location)
    if not _IDENTIFIER.fullmatch(value) or value in _KEYWORDS:
        _fail(location, 'Expected a non-keyword C# identifier')
    return value


def _qualified_identifier(value, location):
    value = _text(value, location)
    parts = value.split('.')
    if not parts or any(not _IDENTIFIER.fullmatch(p) or p in _KEYWORDS for p in parts):
        _fail(location, 'Expected dot-separated non-keyword C# identifiers')
    return value


def _unique_strings(value, location, *, identifiers=False):
    values = _array(value, location)
    result = []
    seen = set()
    for i, item in enumerate(values):
        item_location = f'{location}[{i}]'
        item = _identifier(item, item_location) if identifiers else _text(item, item_location)
        if item in seen:
            _fail(item_location, f'Duplicate value {item!r}')
        seen.add(item)
        result.append(item)
    return result


def _safe_relative_file(value, location):
    value = _text(value, location)
    if '\\' in value or value.startswith('/') or re.match(r'^[A-Za-z]:', value):
        _fail(location, 'Path must be a portable relative path')
    raw_parts = value.split('/')
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(p in ('', '.', '..') for p in raw_parts):
        _fail(location, 'Path must be relative and must not traverse')
    if value.endswith('/'):
        _fail(location, 'Expected a file path, not a directory path')
    return value


def _check_core_type(type_name, location):
    value = _text(type_name, location)
    if _DYNAMIC.search(value) or _UNITY_TYPE.search(value) or _OBJECT_MAP.search(value):
        _fail(location, 'Core Domain/Gameplay signatures cannot depend on dynamic, Unity types, or Dictionary<string, object>')


def _check_budget(*documents):
    pending = [(value, 0) for value in documents]
    visited_containers = set()
    count = 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if count > _MAX_NODES or depth > _MAX_DEPTH:
            _fail('$', 'Architecture contract exceeds depth or node budget')
        if isinstance(value, (dict, list)):
            identity = id(value)
            if identity in visited_containers:
                _fail('$', 'Architecture input must be a tree without cycles or shared containers')
            visited_containers.add(identity)
            if isinstance(value, dict):
                pending.extend((key, depth + 1) for key in value)
                pending.extend((item, depth + 1) for item in value.values())
            else:
                pending.extend((item, depth + 1) for item in value)


def _count_unique(rows, key, location):
    seen = set()
    for i, row in enumerate(rows):
        row = _object(row, f'{location}[{i}]')
        value = _text(row.get(key), f'{location}[{i}].{key}')
        if value in seen:
            _fail(f'{location}[{i}].{key}', f'Duplicate {key} {value!r}')
        seen.add(value)
    return seen


def validate_architecture(plan: dict, catalog: dict) -> dict:
    """Validate a source-bound architecture plan and return deterministic paths.

    Invalid plans raise ``monkey.sources.compiled.ParseError`` with code
    ``CODE_ARCHITECTURE_CONTRACT``. The operation reads no files and has no
    filesystem or engine side effects.
    """
    plan = _object(plan, '$plan')
    catalog = _object(catalog, '$catalog')
    _check_budget(plan, catalog)
    if plan.get('schemaVersion') != SCHEMA_VERSION:
        _fail('$plan.schemaVersion', f'Expected {SCHEMA_VERSION!r}')
    for key in ('sourceManifestSha256', 'rootNamespace', 'modules', 'classes', 'sourceCoverage', 'entryPoint', 'integrationChains', 'limitations'):
        if key not in plan:
            _fail(f'$plan.{key}', 'Required field is missing')

    plan_sha = _text(plan.get('sourceManifestSha256'), '$plan.sourceManifestSha256')
    catalog_sha = _text(catalog.get('sourceManifestSha256'), '$catalog.sourceManifestSha256')
    if not _SHA256.fullmatch(plan_sha) or not _SHA256.fullmatch(catalog_sha):
        _fail('$plan.sourceManifestSha256', 'Source manifest identities must be lowercase SHA-256 hex')
    if plan_sha != catalog_sha:
        _fail('$plan.sourceManifestSha256', 'Plan source manifest SHA-256 does not match the catalog')
    root_namespace = _qualified_identifier(plan.get('rootNamespace'), '$plan.rootNamespace')
    _array(plan.get('limitations'), '$plan.limitations')
    for i, limitation in enumerate(plan['limitations']):
        _text(limitation, f'$plan.limitations[{i}]')

    source_rows = _array(catalog.get('sourceUnits'), '$catalog.sourceUnits')
    source_ids = _count_unique(source_rows, 'id', '$catalog.sourceUnits')
    source_members={r['id']:{m['id']for m in r.get('members',[])if isinstance(m,dict)and isinstance(m.get('id'),str)}for r in source_rows}

    modules = _array(plan.get('modules'), '$plan.modules')
    module_ids = _count_unique(modules, 'id', '$plan.modules')
    module_table = {}
    for i, module in enumerate(modules):
        loc = f'$plan.modules[{i}]'
        module = _object(module, loc)
        module_id = _qualified_identifier(module.get('id'), loc + '.id')
        _text(module.get('responsibility'), loc + '.responsibility')
        srcs = _unique_strings(module.get('sourceUnitIds'), loc + '.sourceUnitIds')
        for j, source_id in enumerate(srcs):
            if source_id not in source_ids:
                _fail(f'{loc}.sourceUnitIds[{j}]', f'Unknown source unit {source_id!r}')
        class_ids = _unique_strings(module.get('classIds'), loc + '.classIds')
        module_table[module_id] = {'sourceUnitIds': set(srcs), 'classIds': set(class_ids)}

    classes = _array(plan.get('classes'), '$plan.classes')
    class_ids = _count_unique(classes, 'id', '$plan.classes')
    class_table = {}
    class_paths = {}
    used_paths = set()
    for i, record in enumerate(classes):
        loc = f'$plan.classes[{i}]'
        record = _object(record, loc)
        class_id = _text(record.get('id'), loc + '.id')
        name = _identifier(record.get('name'), loc + '.name')
        if name.startswith(('Function_', 'Unresolved_')) and re.fullmatch(r'(?:Function|Unresolved)_[A-Za-z0-9_-]+', name):
            _fail(loc + '.name', 'Synthetic Function_/Unresolved_ hash names are not architecture class names')
        layer = _text(record.get('layer'), loc + '.layer')
        if layer not in LAYERS:
            _fail(loc + '.layer', f'Expected one of {", ".join(LAYERS)}')
        module_id = _qualified_identifier(record.get('module'), loc + '.module')
        if module_id not in module_table:
            _fail(loc + '.module', f'Unknown module {module_id!r}')
        kind = _text(record.get('kind'), loc + '.kind')
        if kind not in KINDS:
            _fail(loc + '.kind', f'Expected one of {", ".join(KINDS)}')
        for key in ('responsibility', 'stateOwnership', 'lifecycle'):
            _text(record.get(key), loc + '.' + key)
        if 'baseType' in record and 'base' in record:
            _fail(loc, 'Specify at most one of base or baseType')
        for base_key in ('baseType', 'base'):
            if base_key in record and record[base_key] is not None:
                base_type = _text(record[base_key], loc + '.' + base_key)
                if layer in ('Domain', 'Gameplay'):
                    _check_core_type(base_type, loc + '.' + base_key)
        depends = _unique_strings(record.get('dependsOn'), loc + '.dependsOn')
        type_dependencies = _unique_strings(record.get('typeDependencies'), loc + '.typeDependencies')
        allowed = set(ALLOWED_LAYER_DEPENDENCIES[layer])
        for j, dependency in enumerate(depends):
            if dependency not in LAYERS:
                _fail(f'{loc}.dependsOn[{j}]', f'Unknown dependency layer {dependency!r}')
            if dependency not in allowed:
                _fail(f'{loc}.dependsOn[{j}]', f'{layer} cannot depend on {dependency}')
        srcs = _unique_strings(record.get('sourceUnitIds'), loc + '.sourceUnitIds')
        for j, source_id in enumerate(srcs):
            if source_id not in source_ids:
                _fail(f'{loc}.sourceUnitIds[{j}]', f'Unknown source unit {source_id!r}')
        if not set(srcs).issubset(module_table[module_id]['sourceUnitIds']):
            _fail(loc + '.sourceUnitIds', 'Class source units must be present in its module inputs')
        for source_id in _unique_strings(record.get('sourceInputUnitIds',[]),loc+'.sourceInputUnitIds'):
            if source_id not in source_ids:_fail(loc+'.sourceInputUnitIds','Unknown analysis/dependency source unit')
        allowed_members=set().union(*(source_members[sid]for sid in srcs)) if srcs else set()
        fields = _array(record.get('fields'), loc + '.fields')
        field_names = set()
        for j, field in enumerate(fields):
            floc = f'{loc}.fields[{j}]'
            field = _object(field, floc)
            fname = _identifier(field.get('name'), floc + '.name')
            if fname in field_names:
                _fail(floc + '.name', f'Duplicate field {fname!r}')
            field_names.add(fname)
            ftype = _text(field.get('type'), floc + '.type')
            _text(field.get('role'), floc + '.role')
            field_members=_unique_strings(field.get('sourceMemberIds',[]),floc+'.sourceMemberIds')
            if not set(field_members).issubset(allowed_members):
                _fail(floc+'.sourceMemberIds','Field source IDs must exist in this class source units')
            if layer in ('Domain', 'Gameplay'):
                _check_core_type(ftype, floc + '.type')
        methods = _array(record.get('methods'), loc + '.methods')
        method_signatures = set()
        for j, method in enumerate(methods):
            mloc = f'{loc}.methods[{j}]'
            method = _object(method, mloc)
            mname = _identifier(method.get('name'), mloc + '.name')
            return_type = _text(method.get('returnType'), mloc + '.returnType')
            if layer in ('Domain', 'Gameplay'):
                _check_core_type(return_type, mloc + '.returnType')
            params = _array(method.get('parameters'), mloc + '.parameters')
            param_names = set()
            param_types = []
            for k, param in enumerate(params):
                ploc = f'{mloc}.parameters[{k}]'
                param = _object(param, ploc)
                pname = _identifier(param.get('name'), ploc + '.name')
                if pname in param_names:
                    _fail(ploc + '.name', f'Duplicate parameter {pname!r}')
                param_names.add(pname)
                ptype = _text(param.get('type'), ploc + '.type')
                param_types.append(ptype)
                if layer in ('Domain', 'Gameplay'):
                    _check_core_type(ptype, ploc + '.type')
            member_ids = _unique_strings(method.get('sourceMemberIds'), mloc + '.sourceMemberIds')
            if not set(member_ids).issubset(allowed_members):
                _fail(mloc + '.sourceMemberIds', 'Method source IDs must exist in this class source units')
            signature = (mname, tuple(param_types))
            if signature in method_signatures:
                _fail(mloc + '.name', f'Duplicate method signature {mname!r}')
            method_signatures.add(signature)
        module_table[module_id]['classIds'].add(class_id)
        namespace = '.'.join((root_namespace, layer, module_id))
        path = 'Assets/Game/' + layer + '/' + module_id.replace('.', '/') + '/' + name + '.cs'
        if path.casefold() in used_paths:
            _fail(loc + '.name', f'Output path collision at {path!r}')
        used_paths.add(path.casefold())
        class_paths[class_id] = path
        class_table[class_id] = {'layer': layer, 'module': module_id, 'sourceUnitIds': set(srcs), 'namespace': namespace,
                                 'typeDependencies':type_dependencies,'dependsOn':depends}

    for class_id,record in class_table.items():
        for dependency in record['typeDependencies']:
            if dependency not in class_table:
                _fail(f'$plan.classes[{class_id}].typeDependencies',f'Unknown target class {dependency!r}')
            target_layer=class_table[dependency]['layer']
            if target_layer not in ALLOWED_LAYER_DEPENDENCIES[record['layer']]:
                _fail(f'$plan.classes[{class_id}].typeDependencies','Target type crosses the allowed layer dependency')
            if target_layer!=record['layer'] and target_layer not in record['dependsOn']:
                _fail(f'$plan.classes[{class_id}].typeDependencies','Cross-layer target type must also be declared in dependsOn')

    # Verify every module's declared class membership exactly matches class records.
    declared_by_module = {m['id']: set(_unique_strings(m.get('classIds'), f'$plan.modules[{i}].classIds')) for i, m in enumerate(modules)}
    for module_id, details in module_table.items():
        if details['classIds'] != declared_by_module[module_id]:
            _fail(f'$plan.modules[{module_id}].classIds', 'Module classIds must exactly match classes assigned to this module')
    for i, module in enumerate(modules):
        module_id = module['id']
        declared = declared_by_module[module_id]
        for class_id in declared:
            if class_id not in class_table:
                _fail(f'$plan.modules[{i}].classIds', f'Unknown class {class_id!r}')
            if class_table[class_id]['module'] != module_id:
                _fail(f'$plan.modules[{i}].classIds', f'Class {class_id!r} belongs to another module')

    coverage = _array(plan.get('sourceCoverage'), '$plan.sourceCoverage')
    coverage_seen = set()
    for i, row in enumerate(coverage):
        loc = f'$plan.sourceCoverage[{i}]'
        row = _object(row, loc)
        sid = _text(row.get('sourceUnitId'), loc + '.sourceUnitId')
        if sid not in source_ids:
            _fail(loc + '.sourceUnitId', f'Unknown source unit {sid!r}')
        if sid in coverage_seen:
            _fail(loc + '.sourceUnitId', f'Duplicate coverage row for {sid!r}')
        coverage_seen.add(sid)
        disposition = _text(row.get('disposition'), loc + '.disposition')
        if disposition not in DISPOSITIONS:
            _fail(loc + '.disposition', f'Expected one of {", ".join(DISPOSITIONS)}')
        mapped = _unique_strings(row.get('classIds'), loc + '.classIds')
        for j, class_id in enumerate(mapped):
            if class_id not in class_table:
                _fail(f'{loc}.classIds[{j}]', f'Unknown class {class_id!r}')
            if sid not in class_table[class_id]['sourceUnitIds']:
                _fail(f'{loc}.classIds[{j}]', f'Class {class_id!r} does not declare source unit {sid!r}')
        if disposition == 'planned' and not mapped:
            _fail(loc + '.classIds', 'planned source units must map to at least one class')
        _text(row.get('reason'), loc + '.reason')
    if coverage_seen != source_ids:
        missing = sorted(source_ids - coverage_seen)
        _fail('$plan.sourceCoverage', f'Every catalog source unit needs exactly one coverage row; missing {missing[:5]!r}')
    for class_id, record in class_table.items():
        for sid in record['sourceUnitIds']:
            row = next((r for r in coverage if r.get('sourceUnitId') == sid), None)
            if row is not None and class_id not in row.get('classIds', []):
                _fail(f'$plan.classes[{class_id}].sourceUnitIds', f'Coverage row for {sid!r} omits class {class_id!r}')

    entry = _object(plan.get('entryPoint'), '$plan.entryPoint')
    entry_id = _text(entry.get('classId'), '$plan.entryPoint.classId')
    if entry_id not in class_table or class_table[entry_id]['layer'] != 'Bootstrap':
        _fail('$plan.entryPoint.classId', 'entryPoint must reference a Bootstrap class')
    init_order = _unique_strings(entry.get('initializationOrder'), '$plan.entryPoint.initializationOrder')
    if not init_order or init_order[0] != entry_id:
        _fail('$plan.entryPoint.initializationOrder', 'Initialization order must begin with the entryPoint classId')
    for i, class_id in enumerate(init_order):
        if class_id not in class_table:
            _fail(f'$plan.entryPoint.initializationOrder[{i}]', f'Unknown class {class_id!r}')

    chains = _array(plan.get('integrationChains'), '$plan.integrationChains')
    if not chains:
        _fail('$plan.integrationChains', 'At least one integration chain is required')
    _count_unique(chains, 'id', '$plan.integrationChains')
    for i, chain in enumerate(chains):
        loc = f'$plan.integrationChains[{i}]'
        chain = _object(chain, loc)
        ids = _unique_strings(chain.get('classIds'), loc + '.classIds')
        chain_layers = set()
        for j, class_id in enumerate(ids):
            if class_id not in class_table:
                _fail(f'{loc}.classIds[{j}]', f'Unknown class {class_id!r}')
            chain_layers.add(class_table[class_id]['layer'])
        needed = {'Bootstrap', 'Gameplay', 'Domain', 'Presentation'}
        if not needed.issubset(chain_layers):
            _fail(loc + '.classIds', f'Integration chain must include classIds from layers {sorted(needed)!r}')
        configs = _array(chain.get('configPaths'), loc + '.configPaths')
        if i == 0 and not configs:
            _fail(loc + '.configPaths', 'The first core integration chain must name a configuration file path')
        has_config_file = False
        for j, path in enumerate(configs):
            path = _safe_relative_file(path, f'{loc}.configPaths[{j}]')
            has_config_file |= PurePosixPath(path).suffix.lower() == '.json'
        if configs and not has_config_file:
            _fail(loc + '.configPaths', 'At least one configuration path must identify a JSON file')
        assets = _array(chain.get('assetPaths'), loc + '.assetPaths')
        for j, path in enumerate(assets):
            _safe_relative_file(path, f'{loc}.assetPaths[{j}]')
        _text(chain.get('behavior'), loc + '.behavior')
        chain_sources = _unique_strings(chain.get('sourceUnitIds'), loc + '.sourceUnitIds')
        for j, sid in enumerate(chain_sources):
            if sid not in source_ids:
                _fail(f'{loc}.sourceUnitIds[{j}]', f'Unknown source unit {sid!r}')

    return {
        'valid': True,
        'counts': {
            'modules': len(modules),
            'classes': len(classes),
            'sourceUnits': len(source_ids),
            'fields': sum(len(c.get('fields', [])) for c in classes),
            'methods': sum(len(c.get('methods', [])) for c in classes),
            'integrationChains': len(chains),
        },
        'classPaths': class_paths,
        'assemblyReferences': {layer: list(ASSEMBLY_REFERENCES[layer]) for layer in LAYERS},
    }
