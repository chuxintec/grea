"""Reconcile source diagnostics with exact saved Unity evidence.

This module annotates diagnostics; it never removes or rewrites their history.
Resolution is deliberately scoped to the evidence available in the current
saved readback. A native object proves neither its business behavior nor that
all presentation properties were reproduced.
"""
from __future__ import annotations

import copy
import re
from collections import Counter


_DYNAMIC_CODES = {
    'SPINE_DYNAMIC_BEHAVIOR_INCOMPLETE',
    'ANIMATION_DYNAMIC_CURVES_NOT_LOWERED',
    'ANIMATION_PROPERTY_UNSUPPORTED',
    'ANIMATION_COMPONENT_CURVES_UNSUPPORTED',
    'SCROLL_PHYSICS_NOT_VERIFIED',
    'BUTTON_BUSINESS_UNBOUND',
}

# Codes whose meaning is a named, independently checkable static requirement.
# Merely rendering a component does not prove any of these requirements.
_FAMILY_REQUIREMENTS = {
    'LABEL_LINE_METRICS_REQUIRE_REFERENCE': {'line-metrics'},
    'LABEL_METRICS_NOT_VERIFIED': {'label-metrics'},
    'OUTLINE_METRICS_NOT_VERIFIED': {'outline-metrics'},
    'SYSTEM_FONT_PLATFORM_UNVERIFIED': {
        'font-resolution', 'source-font-os', 'canvas', 'rasterization'},
    'SORT_ORDER_NOT_VERIFIED': {'sort-order'},
    'LAYOUT_NOT_VERIFIED': {'layout'},
    'TEXT_STYLE_NOT_VERIFIED': {'text-style'},
    'MULTIPLE_LAYOUT_HANDOFF': {'layout-context', 'layout-algorithm'},
    'WIDGET_CONTEXT_UNSUPPORTED': {'layout-context', 'layout-algorithm'},
    'MISSING_OUTLINE_LABEL': {'same-node-label'},
}
_HEX_GUID = re.compile(r'^[0-9a-fA-F]{32}$')


def _source_id(row):
    value = row.get('sourceId') or row.get('sourceComponentId')
    return value if isinstance(value, str) and value else None


def _identity(row):
    """Return an exact persistent Unity identity, excluding bool-as-int IDs."""
    if not isinstance(row, dict):
        return None
    guid, local_id = row.get('guid'), row.get('localFileId')
    if (not isinstance(guid, str) or not _HEX_GUID.fullmatch(guid)
            or type(local_id) is not int or local_id == 0
            or not -(1 << 63) <= local_id < (1 << 63)):
        return None
    if row.get('persistent') is not True or row.get('sourceIdentityVerified') is not True:
        return None
    native_type = row.get('nativeType')
    if not isinstance(native_type, str) or not native_type:
        return None
    representation = row.get('representation')
    if representation not in ('native-component', 'native-component-slot', 'disabled-source-data-carrier',
                              'native-static-progress-carrier'):
        return None
    return (guid.lower(), local_id, native_type, representation)


def _coverage_index(coverage):
    rows = coverage.get('components', []) if isinstance(coverage, dict) else []
    counts = Counter(_source_id(row) for row in rows if isinstance(row, dict))
    index = {}
    for row in rows:
        if isinstance(row, dict) and _source_id(row):
            index.setdefault(_source_id(row), row)
    return index, {sid for sid, count in counts.items() if count != 1}


def _native_proof(source_id, covered, *, require_static=True):
    """Validate the current coverage record against its saved native object."""
    if not isinstance(covered, dict) or covered.get('sourceId') != source_id:
        return None
    native = covered.get('nativeComponentReadback')
    identity = _identity(native)
    representation = native.get('representation') if isinstance(native, dict) else None
    layout_binding = covered.get('staticLayoutContinuationBinding')
    slot_valid = (representation == 'native-component-slot'
        and isinstance(layout_binding, dict)
        and layout_binding.get('sourceComponentId') == source_id
        and layout_binding.get('physicalNativeType') == 'NativeStaticLayoutCompletion'
        and covered.get('nativeSlotId') == source_id
        and native.get('nativeSlotId') == source_id
        and native.get('nativeType') == 'NativeStaticLayoutCompletion')
    if (identity is None or native.get('sourceId') != source_id
            or not (representation == 'native-component' or slot_valid)
            or covered.get('disposition') not in ('native', 'disabled')
            or covered.get('nativeStatus') != 'pass'):
        return None
    if require_static and (covered.get('nativeStaticFieldsVerified') is not True
                           or native.get('nativeStaticFieldsVerified') is not True):
        return None
    return identity


def _family_proof(source_id, row, covered, proof):
    if not isinstance(proof, dict) or proof.get('verified') is not True:
        return None
    code = row.get('code')
    requirements = _FAMILY_REQUIREMENTS.get(code)
    if not requirements or code not in (proof.get('resolvedCodes') or []):
        return None
    scope = proof.get('scope')
    if not isinstance(scope, str) or not scope:
        return None
    identity = _native_proof(source_id, covered, require_static=False)
    evidence = proof.get('evidence')
    native = covered.get('nativeComponentReadback') if isinstance(covered, dict) else None
    if identity is None or not isinstance(evidence, dict):
        return None
    if (evidence.get('sourceId') != source_id
            or evidence.get('guid') != identity[0]
            or evidence.get('localFileId') != identity[1]
            or evidence.get('nativeType') != identity[2]
            or evidence.get('representation') != identity[3]
            or evidence.get('persistent') is not True
            or evidence.get('sourceIdentityVerified') is not True):
        return None
    if identity[3] == 'native-component-slot' and evidence.get('nativeSlotId') != source_id:
        return None
    # Proofs name the independently verified requirements. An opaque verified
    # flag or a rendering-exists claim cannot clear a metric/font gap.
    proven = evidence.get('requirements')
    if not isinstance(proven, dict) or not all(proven.get(req) is True for req in requirements):
        return None
    return {'scope': scope, 'resolvedCodes': list(proof['resolvedCodes']),
            'evidence': copy.deepcopy(evidence),
            'nativeIdentity': {'guid': identity[0], 'localFileId': identity[1],
                               'nativeType': identity[2], 'representation': identity[3]}}


def reconcile(diagnostics: list[dict], coverage: dict,
              *, family_proofs: dict | None = None) -> dict:
    """Annotate each diagnostic as resolved, remaining, or remaining-dynamic.

    ``coverage`` is the current saved component coverage. ``family_proofs`` is
    keyed by source ID and must include exact native identity plus named
    requirement evidence; a self-asserted ``verified`` bit is insufficient.
    Original fields and any prior resolution/history remain on every row.
    """
    if not isinstance(diagnostics, list):
        raise TypeError('diagnostics must be a list')
    if not isinstance(coverage, dict):
        raise TypeError('coverage must be a dict')
    family_proofs = family_proofs if isinstance(family_proofs, dict) else {}
    index, duplicate_ids = _coverage_index(coverage)
    output = []
    counts = Counter()
    scopes = Counter()
    resolved_codes = Counter()
    for original in diagnostics:
        if not isinstance(original, dict):
            # Preserve malformed evidence as data instead of discarding it.
            row = {'rawDiagnostic': copy.deepcopy(original), 'code': 'MALFORMED_DIAGNOSTIC'}
        else:
            row = copy.deepcopy(original)
        source_id = _source_id(row)
        code = row.get('code') if isinstance(row.get('code'), str) else 'UNKNOWN'
        covered = index.get(source_id)
        classification = 'remaining'
        scope = 'unresolved-requirement'
        evidence = None

        if code in _DYNAMIC_CODES:
            classification, scope = 'remaining-dynamic', 'dynamic-behavior'
        elif code=='SYSTEM_FONT_PLATFORM_UNVERIFIED':
            # The historical device is provenance, not a missing serialized
            # field. Controlled source-reference metrics have their own gates.
            scope='historical-source-platform-provenance'
        elif code == 'COMPONENT_NOT_IMPORTED' and row.get('phase') == 'initial-component-creation':
            identity = None if source_id in duplicate_ids else _native_proof(source_id, covered)
            if identity is not None:
                classification, scope = 'resolved', 'native-static-component-creation'
                native = covered['nativeComponentReadback']
                evidence = {'sourceId': source_id, 'guid': identity[0],
                            'localFileId': identity[1], 'nativeType': identity[2],
                            'representation': identity[3],
                            'nativeStaticFieldsVerified': True,
                            'disposition': covered.get('disposition')}
                if identity[3] == 'native-component-slot':
                    evidence['nativeSlotId'] = source_id
            else:
                scope = 'native-static-component-creation'
        elif code == 'UNSUPPORTED_COMPONENT_SEMANTIC':
            # Generic adapter notices contain unknown component behavior.
            # Unknown-field diagnostics are never interpreted as a named static
            # requirement, even when the component itself was imported.
            message = str(row.get('message', '')).lower()
            unknown_field = 'unknown component field' in message
            named_requirement = any(row.get(key) for key in
                                    ('requiredField', 'field', 'requirement'))
            if not unknown_field and named_requirement:
                proof = (None if source_id in duplicate_ids else
                         _family_proof(source_id, row, covered, family_proofs.get(source_id)))
                if proof:
                    classification, scope, evidence = 'resolved', proof['scope'], proof
                else:
                    scope = 'named-static-semantic-requirement'
            else:
                scope = 'unknown-component-semantics'
        else:
            proof = (None if source_id in duplicate_ids else
                     _family_proof(source_id, row, covered, family_proofs.get(source_id)))
            if proof:
                classification, scope, evidence = 'resolved', proof['scope'], proof
            elif code in _FAMILY_REQUIREMENTS:
                scope = 'static-presentation-requirement'

        row['resolutionClassification'] = classification
        row['resolutionScope'] = scope
        row['resolutionSourceId'] = source_id
        if evidence is not None:
            row['currentResolutionEvidence'] = evidence
            # Compatibility fields are annotations; preserve prior raw/history.
            row['resolved'] = True
            row['resolution'] = 'saved-evidence-present'
        else:
            row['resolved'] = False
            row['resolution'] = 'remaining-dynamic' if classification == 'remaining-dynamic' else 'remaining'
        if source_id in duplicate_ids:
            row['resolutionClassification'] = 'remaining'
            row['resolutionScope'] = 'duplicate-source-identity'
            row['resolved'] = False
            row['resolution'] = 'remaining'
        output.append(row)
        counts[row['resolutionClassification']] += 1
        scopes[row['resolutionScope']] += 1
        if row['resolutionClassification'] == 'resolved':
            resolved_codes[code] += 1

    return {
        'diagnostics': output,
        'summary': {
            'total': len(output),
            'resolved': counts['resolved'],
            'remaining': counts['remaining'],
            'remainingDynamic': counts['remaining-dynamic'],
            'resolutionScopes': dict(sorted(scopes.items())),
            'resolvedCodes': dict(sorted(resolved_codes.items())),
            'duplicateSourceIds': sorted(duplicate_ids),
        },
    }
