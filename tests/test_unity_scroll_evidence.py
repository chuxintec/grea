import copy

import pytest

from monkey.unity_scroll_evidence import verify
from monkey.unity_diagnostic_resolution import reconcile
from monkey.unity_verification_contract import unresolved_diagnostics


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


def _rect(node_id, *, root=False, identity_override=None):
    guid, local_id = identity_override or NODE_IDENTITIES[node_id]
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
    component = {
        'sourceId': SCROLL, 'node': SCROLL_NODE, 'type': 'cc.ScrollView',
        'nativeType': 'UnityEngine.UI.ScrollRect', 'status': 'native',
        'representation': 'native-component', 'guid': SCROLL_GUID, 'localFileId': SCROLL_LOCAL,
        'componentUuid': SCROLL_UUID, 'sourceIdentityVerified': True, 'persistent': True,
        'sourceEnabled': True, 'nativeEnabled': True, 'nativeStaticFieldsVerified': True,
        'staticScrollFields': copy.deepcopy(fields),
    }
    owner_row = {
        'sourceId': OWNER, 'path': OWNER_PATH,
        'nodes': [_rect(SCROLL_NODE), _rect(CONTENT_NODE)],
        'components': [copy.deepcopy(component)],
    }
    plan = {
        'nodes': plan_nodes,
        'sourcePrefabs': [{'sourceId': OWNER, 'path': OWNER_PATH,
                           'root': SCROLL_NODE, 'nodes': [SCROLL_NODE, CONTENT_NODE]}],
        'components': [source],
    }
    readback = {
        'nodes': [_rect(SCROLL_NODE, root=True), _rect(CONTENT_NODE, root=True)],
        'components': [copy.deepcopy(component)],
        'sourcePrefabs': [owner_row],
    }
    coverage = {'components': [{
        'sourceId': SCROLL, 'sourceType': 'cc.ScrollView', 'disposition': 'native',
        'nativeStatus': 'pass', 'nativeStaticFieldsVerified': True,
        'nativeComponentReadback': copy.deepcopy(component),
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


@pytest.mark.parametrize(('mutate', 'expected_gap'), [
    (lambda p, r, c: p['components'][0].update(horizontal=False), 'static-scroll-field-mismatch:horizontal'),
    (lambda p, r, c: r['sourcePrefabs'][0]['components'][0]['staticScrollFields'].update(vertical=True),
     'top-owner-static-scroll-fields-disagree'),
    (lambda p, r, c: r['sourcePrefabs'][0]['components'][0]['staticScrollFields'].update(contentGuid='e' * 32),
     'saved-recttransform-identity-mismatch:' + CONTENT_NODE),
    (lambda p, r, c: r['nodes'][1]['physicalComponents'][0].update(identityOrigin='direct-observation'),
     'saved-recttransform-identity-mismatch:' + CONTENT_NODE),
    (lambda p, r, c: r['sourcePrefabs'][0]['nodes'][1]['physicalComponents'][0].update(persistent=False),
     'saved-recttransform-identity-mismatch:' + CONTENT_NODE),
    (lambda p, r, c: p['nodes'][1].update(parent='node:wrong#9'),
     'source-scroll-content-viewport-owner-scope-mismatch'),
    (lambda p, r, c: c['components'][0]['nativeComponentReadback'].update(localFileId=True),
     'saved-scrollrect-native-identity-unverified'),
    (lambda p, r, c: r['components'].clear(), 'top-and-owner-scroll-component-rows-not-unique'),
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
    assert 'top-and-owner-scroll-component-rows-not-unique' in result['diagnostics'][0]['message']

    plan, readback, coverage = fixture()
    readback['nodes'].pop()
    result = verify(plan, readback, coverage)
    assert not result['familyProofs']
    assert 'saved-recttransform-identity-mismatch:' + CONTENT_NODE in result['diagnostics'][0]['message']


def test_disabled_scroll_can_prove_static_fields_without_claiming_dynamic_behavior():
    plan, readback, coverage = fixture()
    plan['components'][0]['enabled'] = False
    for row in [readback['components'][0], readback['sourcePrefabs'][0]['components'][0],
                coverage['components'][0]['nativeComponentReadback']]:
        row.update(status='disabled', sourceEnabled=False, nativeEnabled=False,
                   disabledReason='source-disabled')
    coverage['components'][0]['disposition'] = 'disabled'
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
