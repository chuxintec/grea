import copy

import pytest

from grea.recovery.unity_scroll_evidence import verify
from grea.recovery.unity_diagnostic_resolution import reconcile
from grea.recovery.unity_verification_contract import unresolved_diagnostics, statuses


SCROLL = 'scroll:prefab#0'
SCROLL_NODE = 'node:scroll#0'
CONTENT_NODE = 'node:content#1'
OWNER = 'prefab:source#0'
OWNER_PATH = 'Assets/Prefabs/Source.prefab'
SCROLL_GUID = 'a' * 32
SCROLL_LOCAL = 123
SCROLL_UUID = f'{SCROLL_GUID}:{SCROLL_LOCAL}'
NODE_IDENTITIES = {
    SCROLL_NODE: ('b' * 32, 10),
    CONTENT_NODE: ('c' * 32, 20),
}
SCENE_SCROLL_GUID = 'e' * 32
SCENE_SCROLL_LOCAL = 456
SCENE_NODE_IDENTITIES = {
    SCROLL_NODE: ('1' * 32, 110),
    CONTENT_NODE: ('2' * 32, 120),
}


def _rect(node_id, *, root=False, identity_override=None):
    defaults = SCENE_NODE_IDENTITIES if root else NODE_IDENTITIES
    guid, local_id = identity_override or defaults[node_id]
    uuid = f'{guid}:{local_id}'
    return {
        'sourceId': node_id,
        'physicalInventoryContract': 'monkey-unity-node-physical-components/1',
        'physicalInventoryPhase': 'persistent-saved-reopened-node',
        'physicalObservationScope': 'saved-scene-correspondence' if root else 'saved-source-prefab',
        'physicalComponents': [{
            'nativeType': 'UnityEngine.RectTransform', 'guid': guid, 'localFileId': local_id,
            'componentUuid': uuid, 'persistent': True,
            'identityOrigin': 'corresponding-prefab-source' if root else 'direct-observation',
            'identityPath': ['d' * 32 + ':900', uuid] if root else [uuid],
        }],
    }


def fixture():
    source = {
        'sourceId': SCROLL, 'node': SCROLL_NODE, 'type': 'cc.ScrollView',
        'nativeType': 'UnityEngine.UI.ScrollRect', 'sourcePrefabId': OWNER,
        'enabled': True, 'horizontal': True, 'vertical': False, 'content': CONTENT_NODE,
    }
    plan_nodes = [
        {'sourceId': SCROLL_NODE, 'parent': None, 'active': True},
        {'sourceId': CONTENT_NODE, 'parent': SCROLL_NODE, 'active': True},
    ]
    fields = {
        'contract': 'monkey-unity-saved-scroll-static/1', 'schemaVersion': 1,
        'phase': 'persistent-saved-prefab', 'sourceId': SCROLL, 'node': SCROLL_NODE,
        'guid': SCROLL_GUID, 'localFileId': SCROLL_LOCAL,
        'horizontal': True, 'vertical': False,
        'contentNode': CONTENT_NODE, 'viewportNode': SCROLL_NODE,
        'contentGuid': NODE_IDENTITIES[CONTENT_NODE][0], 'contentLocalFileId': NODE_IDENTITIES[CONTENT_NODE][1],
        'contentPersistent': True,
        'viewportGuid': NODE_IDENTITIES[SCROLL_NODE][0], 'viewportLocalFileId': NODE_IDENTITIES[SCROLL_NODE][1],
        'viewportPersistent': True,
    }
    scene_fields = copy.deepcopy(fields)
    scene_fields.update(phase='saved-scene-correspondence',guid=SCENE_SCROLL_GUID,
        localFileId=SCENE_SCROLL_LOCAL,
        contentGuid=SCENE_NODE_IDENTITIES[CONTENT_NODE][0],
        contentLocalFileId=SCENE_NODE_IDENTITIES[CONTENT_NODE][1],
        viewportGuid=SCENE_NODE_IDENTITIES[SCROLL_NODE][0],
        viewportLocalFileId=SCENE_NODE_IDENTITIES[SCROLL_NODE][1])
    component = {
        'sourceId': SCROLL, 'node': SCROLL_NODE, 'type': 'cc.ScrollView',
        'nativeType': 'UnityEngine.UI.ScrollRect', 'status': 'native',
        'representation': 'native-component', 'guid': SCROLL_GUID, 'localFileId': SCROLL_LOCAL,
        'componentUuid': SCROLL_UUID, 'sourceIdentityVerified': True, 'persistent': True,
        'observationScope': 'saved-source-prefab','identityOrigin':'direct-observation',
        'identityPath':[SCROLL_UUID],
        'sourceEnabled': True, 'nativeEnabled': True, 'nativeStaticFieldsVerified': True,
        'staticScrollFields': copy.deepcopy(fields),
    }
    owner_row = {
        'sourceId': OWNER, 'path': OWNER_PATH,
        'nodes': [_rect(SCROLL_NODE), _rect(CONTENT_NODE)],
        'components': [copy.deepcopy(component)],
    }
    scene_component = {
        **copy.deepcopy(component),
        'guid': SCENE_SCROLL_GUID, 'localFileId': SCENE_SCROLL_LOCAL,
        'componentUuid': f'{SCENE_SCROLL_GUID}:{SCENE_SCROLL_LOCAL}',
        'observationScope': 'saved-scene-correspondence',
        'identityOrigin': 'direct-observation',
        'identityPath': [f'{SCENE_SCROLL_GUID}:{SCENE_SCROLL_LOCAL}'],
        'staticScrollFields': scene_fields,
    }
    plan = {
        'nodes': plan_nodes,
        'sourcePrefabs': [{'sourceId': OWNER, 'path': OWNER_PATH,
                           'root': SCROLL_NODE, 'nodes': [SCROLL_NODE, CONTENT_NODE]}],
        'components': [source],
    }
    readback = {
        'sceneComponentContract': 'monkey-unity-saved-scene-components/1',
        'sceneComponentPhase': 'saved-scene-reopened',
        'sceneComponents': [scene_component],
        'nodes': [_rect(SCROLL_NODE, root=True), _rect(CONTENT_NODE, root=True)],
        'components': [copy.deepcopy(component)],
        'sourcePrefabs': [owner_row],
    }
    coverage = {'components': [{
        'sourceId': SCROLL, 'sourceType': 'cc.ScrollView', 'disposition': 'native',
        'nativeStatus': 'pass', 'nativeStaticFieldsVerified': True,
        'nativeComponentReadback': copy.deepcopy(scene_component),
    }]}
    return plan, readback, coverage


def test_exact_saved_scroll_axes_content_and_viewport_produce_named_family_proof():
    plan, readback, coverage = fixture()
    result = verify(plan, readback, coverage)
    proof = result['familyProofs'][SCROLL]
    assert result['diagnostics'] == []
    assert proof['resolvedCodes'] == ['SCROLL_PHYSICS_NOT_VERIFIED']
    assert proof['evidence']['requirements'] == {
        'scroll-axis': True, 'scroll-content': True, 'scroll-viewport': True}
    resolved = reconcile([{'code': 'SCROLL_PHYSICS_NOT_VERIFIED', 'sourceId': SCROLL}],
        coverage, family_proofs=result['familyProofs'])
    assert resolved['diagnostics'][0]['resolutionClassification'] == 'remaining-dynamic'
    blocking = unresolved_diagnostics(resolved['diagnostics'], coverage)
    assert blocking['blocking'] == []
    assert len(blocking['remainingDynamic']) == 1


def test_shared_blocking_gate_rechecks_current_scroll_static_payload_not_only_requirements_flags():
    plan, readback, coverage = fixture()
    proof = verify(plan, readback, coverage)['familyProofs']
    diagnostics = reconcile([{'code': 'SCROLL_PHYSICS_NOT_VERIFIED', 'sourceId': SCROLL}],
        coverage, family_proofs=proof)['diagnostics']
    coverage['components'][0]['nativeComponentReadback']['staticScrollFields']['horizontal'] = False
    state = unresolved_diagnostics(diagnostics, coverage)
    assert state['blocking'] == diagnostics
    assert state['remainingDynamic'] == []


def test_source_gap_aggregate_is_nonblocking_only_when_exact_source_indices_are_adjudicated():
    plan, readback, coverage = fixture()
    proof = verify(plan, readback, coverage)['familyProofs']
    row = {'code': 'SCROLL_PHYSICS_NOT_VERIFIED', 'sourceId': SCROLL,
        'message': 'Native axes/content/viewport retained; drag and inertia remain unverified',
        'origin': 'source', 'origins': ['source'],
        'sourceEvidence': [{'origin': 'source', 'index': 0, 'raw': 'source warning'}]}
    reconciled = reconcile([row], coverage, family_proofs=proof)['diagnostics']
    aggregate = {'code': 'SOURCE_GAPS', 'message': 'SOURCE_GAPS: 1', 'rawDiagnostic': 'SOURCE_GAPS: 1'}
    state = unresolved_diagnostics([aggregate, *reconciled], coverage)
    assert state['blocking'] == []
    assert len(state['remainingDynamic']) == 1
    coverage['nativeStaticValidation'] = 'pass'
    coverage['staticPresentationValidation'] = 'pass'
    outcome = statuses('partial', [aggregate, *reconciled], coverage, 'editor')
    assert outcome['editorValidation'] == 'pass'
    assert outcome['nativeStaticValidation'] == 'pass'

    deduped = copy.deepcopy(row)
    deduped['sourceEvidence'] = [
        {'origin': 'source', 'index': 0, 'raw': 'source warning 0'},
        {'origin': 'source', 'index': 1, 'raw': 'source warning 1'},
    ]
    deduped_rows = reconcile([deduped], coverage, family_proofs=proof)['diagnostics']
    aggregate_two = {'code': 'SOURCE_GAPS', 'message': 'SOURCE_GAPS: 2', 'rawDiagnostic': 'SOURCE_GAPS: 2'}
    state = unresolved_diagnostics([aggregate_two, *deduped_rows], coverage)
    assert state['blocking'] == []
    assert len(state['remainingDynamic']) == 1


@pytest.mark.parametrize(('count', 'indexes', 'static_code'), [
    ("9" * 5000, [0], None),  # invalid oversized decimal remains blocking
    (10**15, [0], None),  # an untrusted count must never allocate its declared range
    (2, [0], None),  # absent raw source index must keep the aggregate blocking
    (1, [0], 'UNKNOWN_STATIC_SOURCE_SEMANTIC'),
])
def test_source_gap_aggregate_never_hides_static_or_unlinked_source_diagnostics(count, indexes, static_code):
    plan, readback, coverage = fixture()
    proof = verify(plan, readback, coverage)['familyProofs']
    scroll = {'code': 'SCROLL_PHYSICS_NOT_VERIFIED', 'sourceId': SCROLL,
        'message': 'Native axes/content/viewport retained; drag and inertia remain unverified',
        'origin': 'source', 'origins': ['source'],
        'sourceEvidence': [{'origin': 'source', 'index': index, 'raw': 'original source warning'}
                           for index in indexes]}
    rows = reconcile([scroll], coverage, family_proofs=proof)['diagnostics']
    if static_code:
        rows.append({'code': static_code, 'sourceId': 'static:unknown',
            'origin': 'source', 'origins': ['source'],
            'sourceEvidence': [{'origin': 'source', 'index': 0, 'raw': 'unknown static gap'}]})
    aggregate = {'code': 'SOURCE_GAPS', 'message': f'SOURCE_GAPS: {count}',
                 'rawDiagnostic': f'SOURCE_GAPS: {count}'}
    state = unresolved_diagnostics([aggregate, *rows], coverage)
    assert aggregate in state['blocking']
    if static_code:
        assert any(row['code'] == static_code for row in state['blocking'])


@pytest.mark.parametrize(('mutate', 'expected_gap'), [
    (lambda p, r, c: p['components'][0].update(horizontal=False), 'static-scroll-field-mismatch:horizontal'),
    (lambda p, r, c: r['sourcePrefabs'][0]['components'][0]['staticScrollFields'].update(vertical=True),
     'top-owner-static-scroll-fields-disagree'),
    (lambda p, r, c: r['sceneComponents'][0]['staticScrollFields'].update(horizontal=False),
     'scene-static-scroll-field-mismatch:horizontal'),
    (lambda p, r, c: r['sceneComponents'][0].update(localFileId=457),
     'saved-scene-scroll-component-identity-or-state-invalid'),
    (lambda p, r, c: r['sourcePrefabs'][0]['components'][0]['staticScrollFields'].update(contentGuid='e' * 32),
     'saved-owner-recttransform-identity-mismatch:' + CONTENT_NODE),
    (lambda p, r, c: r['sceneComponents'][0]['staticScrollFields'].update(contentLocalFileId=121),
     'saved-scene-recttransform-identity-mismatch:' + CONTENT_NODE),
    (lambda p, r, c: r['nodes'][1]['physicalComponents'][0].update(identityPath=['d'*32+':999']),
     'saved-scene-recttransform-identity-mismatch:' + CONTENT_NODE),
    (lambda p, r, c: r['sourcePrefabs'][0]['nodes'][1]['physicalComponents'][0].update(persistent=False),
     'saved-owner-recttransform-identity-mismatch:' + CONTENT_NODE),
    (lambda p, r, c: p['nodes'][1].update(parent='node:wrong#9'),
     'source-scroll-content-viewport-owner-scope-mismatch'),
    (lambda p, r, c: c['components'][0]['nativeComponentReadback'].update(localFileId=True),
     'assessed-scroll-identity-does-not-match-saved-scene-component'),
    (lambda p, r, c: r['components'].clear(), 'owner-scroll-component-rows-not-unique'),
])
def test_unproven_or_mismatched_scroll_static_evidence_stays_blocking(mutate, expected_gap):
    plan, readback, coverage = fixture()
    mutate(plan, readback, coverage)
    result = verify(plan, readback, coverage)
    assert SCROLL not in result['familyProofs']
    assert len(result['diagnostics']) == 1
    assert result['diagnostics'][0]['code'] == 'SCROLL_STATIC_EVIDENCE_UNVERIFIED'
    assert expected_gap in result['diagnostics'][0]['message']


def test_duplicate_prefab_owner_or_missing_root_node_chain_cannot_resolve_scroll():
    plan, readback, coverage = fixture()
    readback['sourcePrefabs'].append(copy.deepcopy(readback['sourcePrefabs'][0]))
    result = verify(plan, readback, coverage)
    assert not result['familyProofs']
    assert 'owner-scroll-component-rows-not-unique' in result['diagnostics'][0]['message']

    plan, readback, coverage = fixture()
    readback['nodes'].pop()
    result = verify(plan, readback, coverage)
    assert not result['familyProofs']
    assert 'saved-scene-recttransform-identity-mismatch:' + CONTENT_NODE in result['diagnostics'][0]['message']


def test_disabled_scroll_can_prove_static_fields_without_claiming_dynamic_behavior():
    plan, readback, coverage = fixture()
    plan['components'][0]['enabled'] = False
    for row in [readback['components'][0], readback['sourcePrefabs'][0]['components'][0],
                readback['sceneComponents'][0],
                coverage['components'][0]['nativeComponentReadback']]:
        row.update(status='disabled', sourceEnabled=False, nativeEnabled=False,
                   disabledReason='source-disabled')
    coverage['components'][0]['disposition'] = 'disabled'
    result = verify(plan, readback, coverage)
    assert SCROLL in result['familyProofs']


def test_owner_recttransform_identity_may_follow_exact_prefab_source_chain():
    plan, readback, coverage = fixture()
    for node in readback['sourcePrefabs'][0]['nodes']:
        for physical in node['physicalComponents']:
            physical['identityOrigin'] = 'corresponding-prefab-source'
    result = verify(plan, readback, coverage)
    assert SCROLL in result['familyProofs']


@pytest.mark.parametrize(('mutate', 'reason'), [
    (lambda p, r, c: r['sourcePrefabs'][0].update(path='Assets/Other.prefab'),
     'saved-scroll-owner-prefab-identity-mismatch'),
    (lambda p, r, c: (r['components'][0]['staticScrollFields'].update(schemaVersion=True),
                      r['sourcePrefabs'][0]['components'][0]['staticScrollFields'].update(schemaVersion=True)),
     'static-scroll-schema-version-invalid'),
])
def test_scroll_owner_path_and_schema_version_are_not_coerced(mutate, reason):
    plan, readback, coverage = fixture()
    mutate(plan, readback, coverage)
    result = verify(plan, readback, coverage)
    assert not result['familyProofs']
    assert reason in result['diagnostics'][0]['message']
