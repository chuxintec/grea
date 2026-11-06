"""Close static ScrollRect prerequisites from saved owner and node evidence.

This module verifies only source axis/content/viewport binding. It does not
claim that drag, inertia, events, or full source engine physics were restored.
"""
from __future__ import annotations

import re

from .io import diagnostic


CONTRACT = 'monkey-unity-saved-scroll-static/1'
NODE_INVENTORY_CONTRACT = 'monkey-unity-node-physical-components/1'
GUID_RE = re.compile(r'^[0-9a-f]{32}$')


def _id(row):
    value = row.get('sourceId') if isinstance(row, dict) else None
    return value if isinstance(value, str) and value else None


def _unique_by_id(rows, source_id):
    matches = [row for row in rows if isinstance(row, dict) and _id(row) == source_id] \
        if isinstance(rows, list) else []
    return matches[0] if len(matches) == 1 else None


def _guid_local(guid, local_id):
    return (isinstance(guid, str) and GUID_RE.fullmatch(guid) is not None
            and type(local_id) is int and local_id != 0
            and -(1 << 63) <= local_id < (1 << 63))


def _unity_identity(row):
    if (not isinstance(row, dict) or not _guid_local(row.get('guid'), row.get('localFileId'))
            or row.get('persistent') is not True or row.get('sourceIdentityVerified') is not True):
        return None
    uuid = row.get('componentUuid')
    expected = f"{row['guid']}:{row['localFileId']}"
    if uuid != expected:
        return None
    return row['guid'], row['localFileId']


def _node_owners(plan, node_id):
    result = []
    for owner in plan.get('sourcePrefabs', []) if isinstance(plan.get('sourcePrefabs'), list) else []:
        if not isinstance(owner, dict) or not isinstance(owner.get('sourceId'), str):
            continue
        nodes = owner.get('nodes')
        ids = {item.get('sourceId') if isinstance(item, dict) else item
               for item in nodes} if isinstance(nodes, list) else set()
        if node_id in ids:
            result.append(owner['sourceId'])
    return result


def _physical_rect(node, *, root_scope):
    if not isinstance(node, dict):
        return None
    if node.get('physicalInventoryContract') != NODE_INVENTORY_CONTRACT:
        return None
    if node.get('physicalInventoryPhase') != 'persistent-saved-reopened-node':
        return None
    expected_scope = 'saved-scene-correspondence' if root_scope else 'saved-source-prefab'
    if node.get('physicalObservationScope') != expected_scope:
        return None
    rows = node.get('physicalComponents')
    rows = [row for row in rows if isinstance(row, dict)
            and row.get('nativeType') == 'UnityEngine.RectTransform'] if isinstance(rows, list) else []
    if len(rows) != 1:
        return None
    row = rows[0]
    identity = _guid_local(row.get('guid'), row.get('localFileId'))
    uuid = f"{row.get('guid')}:{row.get('localFileId')}"
    if (not identity or row.get('componentUuid') != uuid or row.get('persistent') is not True
            or not isinstance(row.get('identityPath'), list) or uuid not in row['identityPath']):
        return None
    if row.get('identityOrigin') not in ('direct-observation', 'corresponding-prefab-source'):
        return None
    return row


def _owner_component_rows(readback, owner_id, source_id):
    roots = [row for row in readback.get('components', [])
             if isinstance(row, dict) and _id(row) == source_id] \
        if isinstance(readback.get('components'), list) else []
    owners = [row for row in readback.get('sourcePrefabs', [])
              if isinstance(row, dict) and row.get('sourceId') == owner_id] \
        if isinstance(readback.get('sourcePrefabs'), list) else []
    if len(owners) != 1:
        return roots, [], None
    details = [row for row in owners[0].get('components', [])
               if isinstance(row, dict) and _id(row) == source_id] \
        if isinstance(owners[0].get('components'), list) else []
    return roots, details, owners[0]


def _scene_component_rows(readback, source_id):
    rows = [row for row in readback.get('sceneComponents', [])
            if isinstance(row, dict) and _id(row) == source_id] \
        if isinstance(readback.get('sceneComponents'), list) else []
    return rows


def _validate_scroll_fields(fields, source, *, phase, identity, content_id, viewport_id, scope):
    gaps = []
    if not isinstance(fields, dict):
        return [scope + '-static-scroll-fields-missing']
    expected = {
        'contract': CONTRACT,
        'schemaVersion': 1,
        'phase': phase,
        'sourceId': source.get('sourceId'),
        'node': source.get('node'),
        'guid': identity[0] if identity else None,
        'localFileId': identity[1] if identity else None,
        'horizontal': source.get('horizontal'),
        'vertical': source.get('vertical'),
        'contentNode': content_id,
        'viewportNode': viewport_id,
    }
    for key, value in expected.items():
        if fields.get(key) != value or (key in ('horizontal', 'vertical')
                and type(fields.get(key)) is not bool):
            gaps.append(scope + '-static-scroll-field-mismatch:' + key)
    if type(fields.get('schemaVersion')) is not int:
        gaps.append(scope + '-static-scroll-schema-version-invalid')
    for node_key, guid_key, file_key, persistent_key in (
        ('contentNode', 'contentGuid', 'contentLocalFileId', 'contentPersistent'),
        ('viewportNode', 'viewportGuid', 'viewportLocalFileId', 'viewportPersistent'),
    ):
        if (fields.get(node_key) is None or not _guid_local(fields.get(guid_key), fields.get(file_key))
                or fields.get(persistent_key) is not True):
            gaps.append(scope + '-static-scroll-reference-identity-invalid:' + node_key)
    return gaps


def _observed_component_identity(row, scope):
    identity = _unity_identity(row)
    if identity is None or row.get('observationScope') != scope:
        return None
    if row.get('identityOrigin') not in ('direct-observation', 'corresponding-prefab-source'):
        return None
    path = row.get('identityPath')
    if not isinstance(path, list) or not path or path[-1] != row.get('componentUuid'):
        return None
    return identity


def _verify_one(plan, readback, coverage_row, source, plan_nodes):
    sid = source.get('sourceId')
    gaps = []
    if (type(source.get('horizontal')) is not bool or type(source.get('vertical')) is not bool
            or type(source.get('enabled')) is not bool):
        gaps.append('source-axis-or-enabled-values-not-boolean')
    content_id = source.get('content')
    content = plan_nodes.get(content_id) if isinstance(content_id, str) else None
    viewport_id = content.get('parent') if isinstance(content, dict) else None
    if not isinstance(content, dict) or not isinstance(viewport_id, str) or not viewport_id:
        gaps.append('source-content-or-viewport-node-unresolved')
    source_nodes = [node for node in plan.get('nodes', []) if isinstance(node, dict)
                    and node.get('sourceId') in {source.get('node'), content_id, viewport_id}]
    if len(source_nodes) != len({source.get('node'), content_id, viewport_id}):
        gaps.append('source-node-identity-ambiguous')

    # The source owner is a source graph join. Candidate scene objects are a
    # separate saved asset scope, not assumed to share owner Prefab GUIDs.
    from .prefab_component_coverage import _planned_owner
    owner_id, owner_error = _planned_owner(plan, source)
    expected_node_ids = {source.get('node'), content_id, viewport_id}
    if owner_error or None in expected_node_ids or any(
            _node_owners(plan, node_id) != [owner_id] for node_id in expected_node_ids if node_id):
        gaps.append('source-scroll-content-viewport-owner-scope-mismatch')
        owner_id = None

    root_rows, owner_rows, owner_readback = _owner_component_rows(readback, owner_id, sid) \
        if owner_id is not None else ([], [], None)
    planned_owners = [row for row in plan.get('sourcePrefabs', [])
                      if isinstance(row, dict) and row.get('sourceId') == owner_id] \
        if isinstance(plan.get('sourcePrefabs'), list) else []
    if (len(planned_owners) != 1 or owner_readback is None
            or not isinstance(planned_owners[0].get('path'), str)
            or not planned_owners[0].get('path')
            or owner_readback.get('path') != planned_owners[0].get('path')):
        gaps.append('saved-scroll-owner-prefab-identity-mismatch')
    if len(root_rows) != 1 or len(owner_rows) != 1 or owner_readback is None:
        gaps.append('owner-scroll-component-rows-not-unique')
        top_fields = owner_fields = None
        owner_identity = None
    else:
        top, owned = root_rows[0], owner_rows[0]
        top_fields, owner_fields = top.get('staticScrollFields'), owned.get('staticScrollFields')
        owner_identity = _observed_component_identity(owned, 'saved-source-prefab')
        if top.get('node') != source.get('node') or owned.get('node') != source.get('node'):
            gaps.append('saved-scroll-component-node-mismatch')
        if (top.get('sourceEnabled') is not source.get('enabled')
                or owned.get('sourceEnabled') is not source.get('enabled')
                or top.get('nativeEnabled') is not source.get('enabled')
                or owned.get('nativeEnabled') is not source.get('enabled')):
            gaps.append('saved-scroll-component-enabled-state-mismatch')
        if (top.get('sourceId') != owned.get('sourceId') or top.get('guid') != owned.get('guid')
                or top.get('localFileId') != owned.get('localFileId')
                or top.get('componentUuid') != owned.get('componentUuid')):
            gaps.append('top-owner-scroll-identity-mismatch')
        if top_fields != owner_fields:
            gaps.append('top-owner-static-scroll-fields-disagree')
        if (top.get('nativeType') != 'UnityEngine.UI.ScrollRect'
                or owned.get('nativeType') != 'UnityEngine.UI.ScrollRect'
                or top.get('status') not in ('native', 'disabled')
                or owned.get('status') not in ('native', 'disabled')):
            gaps.append('saved-scroll-component-type-or-status-invalid')
        if owner_identity is None:
            gaps.append('saved-owner-scroll-identity-unverified')

    owner_fields = owner_fields if isinstance(owner_fields, dict) else None
    if owner_fields is None:
        gaps.append('owner-static-scroll-fields-missing')
    gaps.extend(_validate_scroll_fields(owner_fields, source,
        phase='persistent-saved-prefab', identity=owner_identity,
        content_id=content_id, viewport_id=viewport_id, scope='owner'))

    if (readback.get('sceneComponentContract') != 'monkey-unity-saved-scene-components/1'
            or readback.get('sceneComponentPhase') != 'saved-scene-reopened'):
        gaps.append('saved-scene-component-inventory-header-invalid')
    scene_rows = _scene_component_rows(readback, sid)
    scene_row = scene_rows[0] if len(scene_rows) == 1 else None
    if scene_row is None:
        gaps.append('saved-scene-scroll-component-not-unique')
        scene_identity = None
        scene_fields = None
    else:
        scene_identity = _observed_component_identity(scene_row, 'saved-scene-correspondence')
        scene_fields = scene_row.get('staticScrollFields')
        if (scene_identity is None or scene_row.get('type') != 'cc.ScrollView'
                or scene_row.get('nativeType') != 'UnityEngine.UI.ScrollRect'
                or scene_row.get('node') != source.get('node')
                or scene_row.get('status') not in ('native', 'disabled')
                or scene_row.get('sourceEnabled') is not source.get('enabled')
                or scene_row.get('nativeEnabled') is not source.get('enabled')
                or scene_row.get('nativeStaticFieldsVerified') is not True):
            gaps.append('saved-scene-scroll-component-identity-or-state-invalid')
        if (not isinstance(coverage_row, dict)
                or _unity_identity(coverage_row.get('nativeComponentReadback')) != scene_identity
                or not isinstance(coverage_row.get('nativeComponentReadback'), dict)
                or coverage_row['nativeComponentReadback'].get('componentUuid') != scene_row.get('componentUuid')):
            gaps.append('assessed-scroll-identity-does-not-match-saved-scene-component')
    gaps.extend(_validate_scroll_fields(scene_fields, source,
        phase='saved-scene-correspondence', identity=scene_identity,
        content_id=content_id, viewport_id=viewport_id, scope='scene'))

    native = coverage_row.get('nativeComponentReadback') if isinstance(coverage_row, dict) else None
    if (not isinstance(coverage_row, dict) or coverage_row.get('sourceType') != 'cc.ScrollView'
            or coverage_row.get('nativeStatus') != 'pass'
            or coverage_row.get('disposition') not in ('native', 'disabled')
            or coverage_row.get('nativeStaticFieldsVerified') is not True
            or not isinstance(native, dict)
            or native.get('nativeType') != 'UnityEngine.UI.ScrollRect'
            or native.get('representation') != 'native-component'
            or native.get('status') not in ('native', 'disabled')
            or native.get('sourceId') != sid or native.get('node') != source.get('node')
            or native.get('sourceEnabled') is not source.get('enabled')
            or native.get('nativeEnabled') is not source.get('enabled')):
        gaps.append('assessed-scrollrect-native-identity-unverified')
    if isinstance(scene_fields, dict) and isinstance(native, dict):
        if native.get('staticScrollFields') != scene_fields:
            gaps.append('assessed-scene-scroll-fields-mismatch')

    owner_nodes = owner_readback.get('nodes') if isinstance(owner_readback, dict) else None
    scene_nodes = readback.get('nodes') if isinstance(readback.get('nodes'), list) else []
    owner_node_evidence = {}
    scene_node_evidence = {}
    for node_id, guid_key, file_key in (
        (content_id, 'contentGuid', 'contentLocalFileId'),
        (viewport_id, 'viewportGuid', 'viewportLocalFileId'),
    ):
        if not isinstance(node_id, str) or not isinstance(owner_fields, dict) or not isinstance(scene_fields, dict):
            continue
        owner_node = _unique_by_id(owner_nodes, node_id)
        scene_node = _unique_by_id(scene_nodes, node_id)
        owner_rect = _physical_rect(owner_node, root_scope=False)
        scene_rect = _physical_rect(scene_node, root_scope=True)
        owner_uuid = str(owner_fields.get(guid_key)) + ':' + str(owner_fields.get(file_key))
        scene_uuid = str(scene_fields.get(guid_key)) + ':' + str(scene_fields.get(file_key))
        if (owner_rect is None or owner_rect.get('guid') != owner_fields.get(guid_key)
                or owner_rect.get('localFileId') != owner_fields.get(file_key)
                or owner_rect.get('componentUuid') != owner_uuid):
            gaps.append('saved-owner-recttransform-identity-mismatch:' + node_id)
        else:
            owner_node_evidence[node_id] = {'guid': owner_fields[guid_key],
                'localFileId': owner_fields[file_key], 'componentUuid': owner_rect['componentUuid'],
                'identityOrigin': owner_rect['identityOrigin'],
                'identityPath': list(owner_rect['identityPath'])}
        if (scene_rect is None or scene_rect.get('guid') != scene_fields.get(guid_key)
                or scene_rect.get('localFileId') != scene_fields.get(file_key)
                or scene_rect.get('componentUuid') != scene_uuid):
            gaps.append('saved-scene-recttransform-identity-mismatch:' + node_id)
        else:
            scene_node_evidence[node_id] = {'sourceNodeId': node_id,
                'guid': scene_fields[guid_key], 'localFileId': scene_fields[file_key],
                'ownerComponentUuid': scene_rect['componentUuid'],
                'identityOrigin': scene_rect['identityOrigin'],
                'identityPath': list(scene_rect['identityPath'])}

    if gaps:
        return None, diagnostic('SCROLL_STATIC_EVIDENCE_UNVERIFIED', sid,
            'Saved ScrollRect static evidence failed: ' + ', '.join(dict.fromkeys(gaps)), sid)

    scene_identity = _unity_identity(native)
    evidence = {
        'sourceId': sid,
        'guid': scene_identity[0],
        'localFileId': scene_identity[1],
        'nativeType': 'UnityEngine.UI.ScrollRect',
        'representation': 'native-component',
        'persistent': True,
        'sourceIdentityVerified': True,
        'requirements': {'scroll-axis': True, 'scroll-content': True, 'scroll-viewport': True},
        'sourceNodeId': source['node'],
        'contentNode': content_id,
        'viewportNode': viewport_id,
        'horizontal': source['horizontal'],
        'vertical': source['vertical'],
        'contentIdentity': scene_node_evidence[content_id],
        'viewportIdentity': scene_node_evidence[viewport_id],
        'staticScrollFields': dict(scene_fields),
        'ownerStaticScrollFields': dict(owner_fields),
        'ownerScrollIdentity': {'guid': owner_identity[0], 'localFileId': owner_identity[1]},
        'ownerRectTransformIdentity': owner_node_evidence,
        'contract': CONTRACT,
        'schemaVersion': 1,
        'phase': 'saved-scene-correspondence',
    }
    return {
        'verified': True,
        'scope': 'saved-native-scroll-static-fields',
        'resolvedCodes': ['SCROLL_PHYSICS_NOT_VERIFIED'],
        'evidence': evidence,
    }, None


def verify(plan, readback, coverage):
    """Return exact ScrollRect static proofs and unresolved evidence gaps."""
    if not isinstance(plan, dict) or not isinstance(readback, dict) or not isinstance(coverage, dict):
        return {'familyProofs': {}, 'diagnostics': [diagnostic(
            'SCROLL_STATIC_INPUT_INVALID', 'scrollStaticFields',
            'Plan, raw Unity readback, and assessed coverage objects are required')]}
    source_rows = [row for row in plan.get('components', []) if isinstance(row, dict)
                   and row.get('type') == 'cc.ScrollView'] if isinstance(plan.get('components'), list) else []
    nodes = plan.get('nodes') if isinstance(plan.get('nodes'), list) else []
    node_ids = [row.get('sourceId') for row in nodes if isinstance(row, dict)
                and isinstance(row.get('sourceId'), str)]
    node_map = {row['sourceId']: row for row in nodes if isinstance(row, dict)
                and isinstance(row.get('sourceId'), str)}
    coverage_rows = coverage.get('components') if isinstance(coverage.get('components'), list) else []
    counts = {}
    for row in coverage_rows:
        sid = _id(row)
        if sid:
            counts[sid] = counts.get(sid, 0) + 1

    proofs = {}
    diagnostics = []
    for source in source_rows:
        sid = source.get('sourceId')
        if not isinstance(sid, str) or not sid:
            diagnostics.append(diagnostic('SCROLL_STATIC_SOURCE_ID_INVALID', 'plan.components',
                'ScrollView source component has no stable sourceId'))
            continue
        if node_ids.count(source.get('node')) != 1:
            diagnostics.append(diagnostic('SCROLL_STATIC_SOURCE_NODE_AMBIGUOUS', sid,
                'ScrollView source node must be unique in the frozen plan', sid))
            continue
        covered = _unique_by_id(coverage_rows, sid)
        if counts.get(sid) != 1 or covered is None:
            diagnostics.append(diagnostic('SCROLL_STATIC_COVERAGE_AMBIGUOUS', sid,
                'ScrollView requires one exact component coverage row', sid))
            continue
        proof, gap = _verify_one(plan, readback, covered, source, node_map)
        if proof is not None:
            proofs[sid] = proof
        if gap is not None:
            diagnostics.append(gap)
    return {'familyProofs': proofs, 'diagnostics': diagnostics}
