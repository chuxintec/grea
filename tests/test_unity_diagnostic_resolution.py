import copy

import pytest

from monkey.unity_diagnostic_resolution import reconcile


def native(source_id='src:1', *, local_id=123, guid='a' * 32, **overrides):
    row = {
        'sourceId': source_id,
        'guid': guid,
        'localFileId': local_id,
        'nativeType': 'UnityEngine.UI.Text',
        'representation': 'native-component',
        'persistent': True,
        'sourceIdentityVerified': True,
        'nativeStaticFieldsVerified': True,
    }
    row.update(overrides)
    return row


def component(source_id='src:1', *, readback=None, **overrides):
    row = {
        'sourceId': source_id,
        'sourceType': 'cc.Label',
        'disposition': 'native',
        'nativeStatus': 'pass',
        'nativeStaticFieldsVerified': True,
        'nativeComponentReadback': readback or native(source_id),
        'retainedComponentReadback': None,
        'retentionStatus': 'not_applicable',
        'staticPresentationStatus': 'partial',
    }
    row.update(overrides)
    return row


def diagnostic(code='COMPONENT_NOT_IMPORTED', source_id='src:1', **overrides):
    row = {
        'code': code,
        'sourceId': source_id,
        'phase': 'initial-component-creation',
        'rawDiagnostic': f'{code}: {source_id}',
        'sourceEvidence': [{'origin': 'source', 'raw': 'original'}],
        'nativeDiagnosticIndexes': [7],
        'history': [{'resolution': 'pending-source-coverage-join'}],
    }
    row.update(overrides)
    return row


def test_exact_component_creation_identity_resolves_and_keeps_history():
    original = diagnostic()
    result = reconcile([original], {'components': [component()]})
    row = result['diagnostics'][0]
    assert row['resolutionClassification'] == 'resolved'
    assert row['resolutionScope'] == 'native-static-component-creation'
    assert row['rawDiagnostic'] == original['rawDiagnostic']
    assert row['sourceEvidence'] == original['sourceEvidence']
    assert row['nativeDiagnosticIndexes'] == [7]
    assert row['history'] == original['history']
    assert result['summary']['resolved'] == 1


def test_source_id_mismatch_does_not_resolve_even_if_native_identity_is_valid():
    result = reconcile([diagnostic(source_id='src:2')], {'components': [component('src:1')]})
    row = result['diagnostics'][0]
    assert row['resolutionClassification'] == 'remaining'
    assert row['resolved'] is False


@pytest.mark.parametrize('local_id', [True, False, 0, 1 << 63, -(1 << 63) - 1])
def test_invalid_unity_file_ids_do_not_resolve(local_id):
    result = reconcile([diagnostic()], {
        'components': [component(readback=native(local_id=local_id))],
    })
    assert result['diagnostics'][0]['resolutionClassification'] == 'remaining'


def test_duplicate_source_ids_block_resolution():
    result = reconcile([diagnostic()], {
        'components': [component(), component(readback=native(local_id=124))],
    })
    assert result['diagnostics'][0]['resolutionScope'] == 'duplicate-source-identity'
    assert result['summary']['duplicateSourceIds'] == ['src:1']


def test_creation_proof_does_not_clear_unknown_component_field_semantics():
    rows = [
        diagnostic('UNSUPPORTED_COMPONENT_SEMANTIC', message='unknown component field: anim_new'),
        diagnostic('UNSUPPORTED_COMPONENT_SEMANTIC', message='component cc.Label requires adapter or AI implementation'),
    ]
    result = reconcile(rows, {'components': [component()]})
    assert [r['resolutionClassification'] for r in result['diagnostics']] == ['remaining', 'remaining']
    assert result['diagnostics'][0]['resolutionScope'] == 'unknown-component-semantics'


def test_dynamic_boundaries_remain_separate_from_static_failure():
    rows = [
        diagnostic('SCROLL_PHYSICS_NOT_VERIFIED'),
        diagnostic('ANIMATION_DYNAMIC_CURVES_NOT_LOWERED'),
        diagnostic('BUTTON_BUSINESS_UNBOUND'),
    ]
    result = reconcile(rows, {'components': [component()]})
    assert all(r['resolutionClassification'] == 'remaining-dynamic' for r in result['diagnostics'])
    assert result['summary']['remainingDynamic'] == 3
    assert result['summary']['remaining'] == 0


def test_metric_and_font_proofs_need_named_requirements_and_exact_identity():
    rows = [
        diagnostic('LABEL_LINE_METRICS_REQUIRE_REFERENCE'),
        diagnostic('SYSTEM_FONT_PLATFORM_UNVERIFIED'),
    ]
    family = {
        'src:1': {
            'verified': True,
            'scope': 'saved-static-presentation',
            'resolvedCodes': ['LABEL_LINE_METRICS_REQUIRE_REFERENCE', 'SYSTEM_FONT_PLATFORM_UNVERIFIED'],
            'evidence': {
                'sourceId': 'src:1', 'guid': 'a' * 32, 'localFileId': 123,
                'nativeType': 'UnityEngine.UI.Text', 'representation': 'native-component',
                'persistent': True, 'sourceIdentityVerified': True,
                # Rendering existence and font resolution do not prove OS,
                # Canvas behavior, or rasterization equivalence.
                'requirements': {'line-metrics': True, 'font-resolution': True},
                'renderingExists': True,
            },
        },
    }
    result = reconcile(rows, {'components': [component()]}, family_proofs=family)
    assert result['diagnostics'][0]['resolutionClassification'] == 'resolved'
    assert result['diagnostics'][1]['resolutionClassification'] == 'remaining'


def test_family_proof_cannot_self_assert_or_match_wrong_native_id():
    row = diagnostic('LABEL_METRICS_NOT_VERIFIED')
    proof = {
        'verified': True, 'scope': 'saved-static-presentation',
        'resolvedCodes': ['LABEL_METRICS_NOT_VERIFIED'],
        'evidence': {
            'sourceId': 'src:1', 'guid': 'b' * 32, 'localFileId': 123,
            'nativeType': 'UnityEngine.UI.Text', 'representation': 'native-component',
            'persistent': True, 'sourceIdentityVerified': True,
            'requirements': {'label-metrics': True},
        },
    }
    result = reconcile([row], {'components': [component()]}, family_proofs={'src:1': proof})
    assert result['diagnostics'][0]['resolutionClassification'] == 'remaining'
    proof['evidence']['guid'] = 'a' * 32
    proof['evidence'].pop('requirements')
    result = reconcile([row], {'components': [component()]}, family_proofs={'src:1': proof})
    assert result['diagnostics'][0]['resolutionClassification'] == 'remaining'


def test_input_diagnostics_are_not_mutated():
    rows = [diagnostic()]
    before = copy.deepcopy(rows)
    reconcile(rows, {'components': [component()]})
    assert rows == before


@pytest.mark.parametrize(('code', 'requirements'), [
    ('MULTIPLE_LAYOUT_HANDOFF', {'layout-context': True, 'layout-algorithm': True}),
    ('WIDGET_CONTEXT_UNSUPPORTED', {'layout-context': True, 'layout-algorithm': True}),
    ('MISSING_OUTLINE_LABEL', {'same-node-label': True}),
])
def test_layout_context_and_outline_diagnostics_need_named_requirement_proofs(code, requirements):
    row = diagnostic(code)
    proof = {
        'verified': True, 'scope': 'saved-native-layout-proof', 'resolvedCodes': [code],
        'evidence': {
            'sourceId': 'src:1', 'guid': 'a' * 32, 'localFileId': 123,
            'nativeType': 'UnityEngine.UI.Text', 'representation': 'native-component',
            'persistent': True, 'sourceIdentityVerified': True, 'requirements': requirements,
        },
    }
    result = reconcile([row], {'components': [component()]}, family_proofs={'src:1': proof})
    assert result['diagnostics'][0]['resolutionClassification'] == 'resolved'
    incomplete = copy.deepcopy(proof)
    incomplete['evidence']['requirements'] = {}
    result = reconcile([row], {'components': [component()]}, family_proofs={'src:1': incomplete})
    assert result['diagnostics'][0]['resolutionClassification'] == 'remaining'


def test_component_creation_can_resolve_exact_layout_slot_but_not_unbound_slot():
    sid = 'src:layout/components/0'
    binding = {'sourceComponentId': sid, 'physicalNativeType': 'NativeStaticLayoutCompletion'}
    native_row = native(sid, nativeType='NativeStaticLayoutCompletion',
                        representation='native-component-slot', nativeSlotId=sid)
    covered = component(sid, readback=native_row, staticLayoutContinuationBinding=binding,
                        nativeSlotId=sid)
    result = reconcile([diagnostic(source_id=sid)], {'components': [covered]})
    assert result['diagnostics'][0]['resolutionClassification'] == 'resolved'
    broken = copy.deepcopy(covered)
    broken['nativeSlotId'] = 'src:other/slot'
    result = reconcile([diagnostic(source_id=sid)], {'components': [broken]})
    assert result['diagnostics'][0]['resolutionClassification'] == 'remaining'


def test_layout_family_resolution_requires_exact_slot_id_in_proof_evidence():
    sid = 'src:layout/components/0'
    binding = {'sourceComponentId': sid, 'physicalNativeType': 'NativeStaticLayoutCompletion'}
    native_row = native(sid, nativeType='NativeStaticLayoutCompletion',
                        representation='native-component-slot', nativeSlotId=sid)
    covered = component(sid, readback=native_row, staticLayoutContinuationBinding=binding,
                        nativeSlotId=sid)
    proof = {
        'verified': True, 'scope': 'saved-native-layout-proof',
        'resolvedCodes': ['MULTIPLE_LAYOUT_HANDOFF'],
        'evidence': {'sourceId': sid, 'guid': 'a' * 32, 'localFileId': 123,
            'nativeType': 'NativeStaticLayoutCompletion', 'representation': 'native-component-slot',
            'nativeSlotId': sid, 'persistent': True, 'sourceIdentityVerified': True,
            'requirements': {'layout-context': True, 'layout-algorithm': True}},
    }
    row = diagnostic('MULTIPLE_LAYOUT_HANDOFF', source_id=sid)
    result = reconcile([row], {'components': [covered]}, family_proofs={sid: proof})
    assert result['diagnostics'][0]['resolutionClassification'] == 'resolved'
    proof['evidence']['nativeSlotId'] = 'other-slot'
    result = reconcile([row], {'components': [covered]}, family_proofs={sid: proof})
    assert result['diagnostics'][0]['resolutionClassification'] == 'remaining'
