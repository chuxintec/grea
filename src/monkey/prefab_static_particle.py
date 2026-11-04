"""Preserve serialized particle settings and resources without running particles.

This is deliberately a disabled, editable settings carrier, not a renderer or a
claim that the source particle simulation has been ported. No defaults are
invented for fields absent from the serialized source.
"""
from .prefab_static_toggle import _resolve_component
from .prefab_static_fields import _encode, _asset_uuid_index, _EXCLUDED
from .prefab_static_carriers import prepare as prepare_carriers
from .io import sha
from pathlib import Path


def prepare(plan, manifest, output):
    nodes = {n['sourceId']: n for n in plan['nodes']}
    components = {c['sourceId']: c for c in plan['components']}
    assets = {a['sourceId']: a for a in manifest['assets']}
    uuid_index = _asset_uuid_index(manifest)
    origins = {r['instanceSourceId']: r['templateSourceId']
               for r in plan.get('staticAnimationComponentOrigins', [])}
    snapshots, boundary = [], []
    for component in plan['components']:
        if component['type'] != 'cc.ParticleSystem':
            continue
        source_id = origins.get(component['sourceId'], component['sourceId'])
        raw, _, _ = _resolve_component(manifest, source_id, component['type'])
        owner = source_id.split('#', 1)[0]
        asset = assets[owner]
        fields, diagnostics = [], []
        for name, value in raw.items():
            if name in _EXCLUDED:
                continue
            kind, encoded = _encode(value, owner, asset['bundle'], asset['document']['instances'],
                                    uuid_index, nodes, components, diagnostics, source_id+'.'+name, set())
            field = dict(name=name, kind=kind, value=encoded)
            if isinstance(value, dict) and value.get('__value_type__') == 4:
                field['sourceDeclaredType'] = 'cc.Color'
            elif isinstance(value, dict) and value.get('__value_type__') == 0:
                values = value.get('values')
                if not isinstance(values, list) or len(values) != 2:
                    raise ValueError('STATIC_PARTICLE_VECTOR_INVALID: '+name)
                field.update(kind='array', value=[dict(kind='float', value=v) for v in values])
            elif kind == 'asset_ref':
                field['sourceDeclaredType'] = 'cc.Asset'
            fields.append(field)
        if diagnostics:
            raise ValueError('STATIC_PARTICLE_REFERENCE_UNRESOLVED: '+str(diagnostics))
        snapshots.append(dict(sourceId=component['sourceId'], node=component['node'],
                              sourceType=component['type'], fields=fields,
                              declarationDefaults='unverified', gaps=['particle_simulation_not_restored']))
        boundary.append(dict(sourceId=component['sourceId'], sourceOriginId=source_id,
                             sourceEnabled=component['enabled'], serializedFieldNames=[f['name'] for f in fields],
                             renderingRecovered=False, playbackExecuted=False,
                             absentSourceDefaults='not_inferred', vectorStorage='source_xy_double_array'))
    target = 'creator' if plan['targetProfile'].startswith('cocos-') else 'unity'
    result = prepare_carriers(snapshots, target, 'Monkey.StaticFields.N'+sha(plan['namespace'].encode())[:12], Path(output).resolve())
    plan.setdefault('staticFieldScripts', []).extend(result['scripts'])
    for source_id, binding in result['bindings'].items():
        components[source_id]['staticFieldBinding'] = binding
    plan['staticParticleBoundary'] = boundary
    return result
