"""Frozen semantic evidence -> atomic field plan with exact Unity target IDs.

This is an offline gate, not an Editor writer or a metadata schema generator.
Trusted snapshots must be independently established; a caller assertion alone
cannot establish the fidelity of original gameplay or a target scene.
"""
import re
from .io import safe, inside, read, load, sha, new_output, write_json
from .sources.compiled import fail
from .unity_semantics import SemanticError, integer, pointer, validate_component, normalized, array_data
from .unity_code_model import CORE_FIELDS


def digest(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise SemanticError('Expected SHA256 identity')
    return value


def source_key(row):
    name = row.get('file')
    if not isinstance(name, str) or not name or '/' in name or '\\' in name or name in ('.', '..'):
        raise SemanticError('Expected exact serialized file name')
    pid = row.get('pathId')
    if not isinstance(pid, str) or str(integer(pid)) != pid or pid == '0':
        raise SemanticError('Expected nonzero signed64 decimal pathId string')
    return name, pid


def target_key(row):
    guid, local = row.get('assetGuid'), row.get('localId')
    if not isinstance(guid, str) or not re.fullmatch('[0-9a-f]{32}', guid) or guid == '0'*32:
        raise SemanticError('Exact target asset GUID required; hierarchy name alone is unsafe')
    if not isinstance(local, str) or str(integer(local)) != local or local == '0':
        raise SemanticError('Exact target object localId required')
    digest(row.get('assetSha256'))
    if not isinstance(row.get('assetPath'), str) or not row['assetPath'].startswith('Assets/'):
        raise SemanticError('Exact project-relative Assets path required')
    # Hierarchy segments are diagnostic assertions, not keys. Include duplicate
    # sibling ordinals; names may contain slash/# without escaping ambiguity.
    hierarchy = row.get('hierarchy')
    if not isinstance(hierarchy, list) or not 1 <= len(hierarchy) <= 256:
        raise SemanticError('Expected structured hierarchy segments')
    for part in hierarchy:
        if set(part) != {'name', 'ordinal'} or not isinstance(part['name'], str) or type(part['ordinal']) is not int or part['ordinal'] < 0:
            raise SemanticError('Expected explicit same-name sibling ordinal')
    if not isinstance(row.get('type'), str) or not row['type']:
        raise SemanticError('Target component type required')
    return guid, local


def unique(rows, key, description):
    if not isinstance(rows, list) or len(rows) > 250_000:
        raise SemanticError('Invalid ' + description + ' list')
    result = {}
    for row in rows:
        k = key(row)
        if k in result:
            raise SemanticError('Duplicate ' + description + ' identity')
        result[k] = row
    return result


def build(candidate, trusted, bindings, inventory):
    """Return diagnostics only if any selected object/reference is unverified."""
    diagnostics, entries = [], []
    try:
        if any(x.get('schemaVersion') != 1 for x in (candidate, trusted, bindings, inventory)):
            raise SemanticError('Expected schemaVersion 1')
        if not isinstance(inventory.get('unityVersion'),str) or not re.fullmatch(r'6000\.[0-9]+\.[0-9]+[abfp][0-9]+',inventory['unityVersion']):
            raise SemanticError('Exact Unity 6 target version required')
        source = candidate['source']
        for key in ('sha256', 'metadataSha256'):
            digest(source[key])
        if not isinstance(source.get('unityVersion'), str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+[abfp][0-9]+',source['unityVersion']):
            raise SemanticError('Exact source Unity version required')
        if source != trusted['source'] or source != bindings['source']:
            raise SemanticError('Source version/container/metadata identity differs')
        if candidate['files'] != trusted['files']:
            raise SemanticError('Serialized file/external table identity differs')
        files = unique(candidate['files'], lambda r: r['name'], 'serialized file')
        source_objects = unique(trusted['objects'], source_key, 'trusted object')
        selected = unique(candidate['objects'], source_key, 'candidate object')
        if not selected:
            raise SemanticError('No selected objects')
        native = unique(inventory['objects'], target_key, 'target object')
        mapped = unique(bindings['objects'], lambda r: source_key(r['source']), 'source binding')
        used = set()
        for binding in mapped.values():
            src, target = binding['source'], binding['target']
            k = target_key(target)
            if k in used or native.get(k) != target:
                raise SemanticError('Target ambiguous, stale, or differs from exact inventory identity')
            used.add(k)
            known = source_objects.get(source_key(src))
            if known is None or digest(src.get('rawSha256')) != digest(known.get('rawSha256')):
                raise SemanticError('Binding source object identity differs')

        def convert(node, value, file):
            typ = node['type']
            if re.fullmatch(r'PPtr<[^<>]+>',typ):
                fid, pid = pointer(value)
                if pid == 0:
                    return None
                target_file = file
                if fid:
                    ext = files[file].get('externals', [])
                    if fid > len(ext) or not isinstance(ext[fid-1], str) or ext[fid-1] not in files:
                        raise SemanticError('PPtr external file not uniquely resolved')
                    target_file = ext[fid-1]
                binding = mapped.get((target_file, str(pid)))
                if binding is None:
                    raise SemanticError('Non-null field PPtr has no exact target mapping')
                return dict(type='UnityObjectReference', target=binding['target'])
            if typ == 'string': return value
            if isinstance(value, list):
                item = array_data({'children':[node]}) if typ == 'Array' else array_data(node)
                return [convert(item, v, file) for v in value]
            if isinstance(value, dict):
                if value.get('$type') == 'integer': return value
                return {n['name']: convert(n, value[n['name']], file) for n in node['children']}
            if type(value) is int and abs(value) > (1 << 53)-1:
                return {'$type':'integer','decimal':str(value)}
            return value

        for key, row in selected.items():
            try:
                baseline = source_objects.get(key)
                if baseline is None or key[0] not in files:
                    raise SemanticError('No independently trusted object for this identity')
                for field in ('rawSha256', 'typeIdentity'):
                    if row.get(field) != baseline.get(field):
                        raise SemanticError(field + ' differs')
                digest(row.get('rawSha256'))
                typ = row.get('typeIdentity')
                if not isinstance(typ, dict) or not all(isinstance(typ.get(x), str) and typ[x] for x in ('assembly','type')):
                    raise SemanticError('Exact assembly/type identity required')
                digest(typ.get('declarationSha256'))
                for token in ('scriptId', 'typeHash'):
                    value = typ.get(token)
                    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value) or value == '0'*32:
                        raise SemanticError('Exact nonzero script/type hash required')
                evidence = baseline.get('evidence', {})
                if evidence.get('kind') not in ('embedded', 'exact-frozen-bundle'):
                    raise SemanticError('Unsupported trusted schema evidence')
                digest(evidence.get('sha256'))
                # Full dictionary comparison includes alignment/version flags.
                if row['schema'] != baseline['schema']:
                    raise SemanticError('Schema fields/types/array/layout differ from trusted schema')
                validate_component(baseline['schema'], baseline['data'], baseline['header'])
                validate_component(row['schema'], row['data'], baseline['header'])
                if normalized(row['data'],row['schema']) != normalized(baseline['data'],baseline['schema']):
                    raise SemanticError('Fields/references differ from independently trusted values')
                binding = mapped.get(key)
                if binding is None or binding['target']['type'] != typ['type']:
                    raise SemanticError('Exact source component -> target type/identity mapping absent')
                fields = {n['name']: convert(n, row['data'][n['name']], key[0])
                          for n in row['schema']['children'] if n['name'] not in CORE_FIELDS}
                entries.append(dict(source=dict(file=key[0],pathId=key[1],rawSha256=row['rawSha256']),
                                    typeIdentity=typ,target=binding['target'],fields=fields))
            except (SemanticError, KeyError, TypeError) as error:
                diagnostics.append(dict(file=key[0],pathId=key[1],message=str(error)))
    except (SemanticError, KeyError, TypeError, AttributeError, ValueError) as error:
        diagnostics.append(dict(message=str(error)))
    if diagnostics:
        return dict(status='blocked',writable=False,diagnostics=diagnostics)
    return dict(status='validated',writable=True,entries=entries,diagnostics=[],
                scope='Frozen evidence cross-check only; Editor apply/save/reload not_run')


def plan(candidate, trusted, trusted_sha256, bindings, inventory, inventory_sha256, source, metadata, target_root, output):
    paths = [safe(p) for p in (candidate, trusted, bindings, inventory, source, metadata)]
    raw = [read(p, max_bytes=128*1024*1024) for p in paths[:4]]
    if sha(raw[1]) != trusted_sha256:
        fail('UNITY_TRUSTED_CHANGED',str(paths[1]),'Trusted snapshot differs from pinned hash')
    if sha(raw[3]) != inventory_sha256:
        fail('UNITY_TARGET_CHANGED',str(paths[3]),'Target inventory differs from pinned hash')
    docs = [load(b, max_nodes=8_000_000) for b in raw]
    identity = docs[0].get('source', {})
    if sha(read(paths[4], max_bytes=128*1024*1024)) != identity.get('sha256') or sha(read(paths[5], max_bytes=128*1024*1024)) != identity.get('metadataSha256'):
        fail('UNITY_SOURCE_CHANGED',str(paths[4]),'Container or metadata differs from frozen identity')
    root = safe(target_root)
    # Read the exact ForceText target assets, their .meta GUIDs and local IDs.
    # Binary targets need an explicit future native inventory adapter.
    version = read(root/'ProjectSettings/ProjectVersion.txt').decode('utf-8')
    if re.findall(r'^m_EditorVersion: (.+)\r?$',version,re.M) != [docs[3].get('unityVersion')]:
        fail('UNITY_TARGET_CHANGED',str(root),'Target Editor version differs from inventory')
    target_files = {}
    for row in docs[3].get('objects', []):
        try:
            target_key(row)
            asset = inside(root, row['assetPath'])
            if asset not in target_files:
                body = read(asset, max_bytes=128*1024*1024)
                meta = read(asset.with_suffix(asset.suffix+'.meta')).decode('utf-8')
                ids = re.findall(rb'^--- !u![0-9]+ &(-?[0-9]+)(?: stripped)?\r?$',body,re.M)
                if len(ids) != len(set(ids)):
                    raise SemanticError('Duplicate target local ID in ForceText asset')
                guids = re.findall(r'^guid: ([0-9a-f]{32})\r?$',meta,re.M)
                target_files[asset] = sha(body), guids, {x.decode() for x in ids}
            actual_sha, guids, ids = target_files[asset]
            if actual_sha != row['assetSha256'] or guids != [row['assetGuid']] or row['localId'] not in ids:
                raise SemanticError('Target asset bytes/GUID/local ID changed')
        except (SemanticError, UnicodeError, KeyError) as error:
            fail('UNITY_TARGET_CHANGED',str(root),str(error))
    result = build(*docs)
    out = new_output(output, paths+[root])
    report = {k:v for k,v in result.items() if k != 'entries'}
    report.update(schemaVersion=1,source=identity,inputSha256={name:sha(b) for name,b in zip(('candidate','trusted','bindings','inventory'),raw)},
                  entriesValidated=len(result.get('entries', [])),sourceCodeExecuted=False,native='not_run')
    write_json(out/'validation.json',report)
    if result['writable']:
        write_json(out/'field-plan.json',dict(schemaVersion=1,source=identity,entries=result['entries'],
                                            targetInventorySha256=sha(raw[3]),trustedSha256=sha(raw[1]),native='not_run'))
    return dict(status=result['status'],writable=result['writable'],report=str(out/'validation.json'))
