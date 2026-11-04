"""Generate an ordinary intake spec from an owned binding export, then consume it.

No compiler omissions, target types, or field schemas are inferred. Reviewed
policy rows may extend the frozen native fragment under the existing contract.
"""
from pathlib import Path

from .candidate_snapshot import snapshot, verify
from .errors import BeaverError, fail
from .intake import COMPILER, guid, preview
from .intake_contract import validate_spec
from .io import load, read, safe, new_output, write_json
from .output_limits import MANIFEST_BYTES, MANIFEST_NODES, digest_file

ROOT = 'Analysis/BeaverIntakeBindings/'
POLICY_KEYS = {'schemaVersion', 'newScripts', 'externalScripts', 'omittedCompilerInputs',
               'packageScripts', 'externalAssets', 'protectedAssets', 'retainedAssemblies'}


def _document(path):
    return load(read(path, max_bytes=MANIFEST_BYTES), max_nodes=MANIFEST_NODES)


def generate(candidate, target, expected_manifest, mapping, output, policy=None, preparation_receipt=None, package_evidence=None, expected_package_evidence=None, classification=None):
    from .intake import resolution_context
    resolution,_ = resolution_context(package_evidence,expected_package_evidence)
    incoming, manifest, files, manifest_sha = snapshot(candidate)
    verify(incoming, files)
    if manifest_sha != expected_manifest:
        fail('INTAKE_CANDIDATE_DRIFT', str(incoming), 'Exact reviewed candidate manifest required')
    required = [ROOT + leaf for leaf in ('intake-spec-fragments.json', 'serialized-oracle.json', 'typed-coverage.json', 'lineage.json')]
    if any(p not in files for p in required) or manifest.get('projectLayout') != 'beaver-intake-prepared/1':
        fail('INTAKE_BINDING_SPEC_EXPORT', str(incoming), 'Owned native binding export and inventoried sidecars required')
    mapping = safe(mapping)
    mapped = _document(mapping)
    if not isinstance(mapped, dict) or 'additions' not in mapped or set(mapped) - {'additions', 'status', 'targetSubtreeAbsentAtPreparation', 'existingSupport', 'limitations'}:
        fail('INTAKE_BINDING_SPEC_MAPPING', str(mapping), 'Explicit additions mapping required')
    extra = _document(safe(policy)) if policy else {}
    if not isinstance(extra, dict) or set(extra) - POLICY_KEYS:
        fail('INTAKE_BINDING_SPEC_POLICY', str(policy), 'Only existing intake compiler/asset policy rows are accepted')
    fragment = _document(incoming / required[0])
    version = extra.get('schemaVersion', 4)
    if (type(version) is not int or version not in (4, 5) or
            (version == 4 and 'retainedAssemblies' in extra)):
        fail('INTAKE_BINDING_SPEC_POLICY', str(policy), 'Typed native export requires spec 4 or 5')
    evidence = [dict(path=str(mapping), sha256=digest_file(mapping))]
    if policy:
        evidence.append(dict(path=str(safe(policy)), sha256=digest_file(safe(policy))))
    spec = dict(schemaVersion=version, operation='additive-intake', candidateManifestSha256=manifest_sha,
                additions=mapped['additions'], externalScripts=fragment['externalScripts'] + extra.get('externalScripts', []),
                omittedCompilerInputs=fragment['omittedCompilerInputs'] + extra.get('omittedCompilerInputs', []),
                verifications=fragment['spec4Fragment']['verifications'],
                engineObjects=fragment['spec4Fragment']['engineObjects'], evidence=evidence,
                newScripts=extra.get('newScripts', []), packageScripts=extra.get('packageScripts', []),
                externalAssets=extra.get('externalAssets', []), protectedAssets=extra.get('protectedAssets', []))
    if version == 5:
        spec['retainedAssemblies'] = extra.get('retainedAssemblies', [])
    validate_spec(spec)
    # Types below are observations from the saved native oracle, never guessed
    # from filenames or assumed to be a reflection/behavior acceptance gate.
    native = _document(incoming / required[1])
    observed = {}
    for asset in native['prefabs']:
        for owner in asset['owners']:
            for prop in owner['properties']:
                ref = prop.get('reference')
                if ref and ref.get('scriptType'):
                    observed.setdefault(ref['guid'], set()).add((ref['scriptType'], ref['scriptAssembly']))
    covered = {r['source'] for r in spec['externalScripts'] + spec['newScripts']}
    covered.update(r['path'] for r in spec['omittedCompilerInputs'])
    package_guids = {r['guid'] for r in spec['packageScripts']}
    compiler = {p for p in files if p.startswith('Assets/') and Path(p).suffix.lower() in COMPILER}
    uncovered = []
    for path in sorted(compiler):
        asset_guid = guid(read(incoming / (path + '.meta')), path) if path + '.meta' in files else None
        if path in covered or asset_guid in package_guids:
            continue
        uncovered.append(dict(path=path, sha256=files[path]['sha256'], guid=asset_guid,
                              nativeScriptTypes=[dict(type=t, assembly=a) for t, a in sorted(observed.get(asset_guid, set()))],
                              declaration='not_classified'))
    receipt = None
    if preparation_receipt:
        receipt_path = safe(preparation_receipt)
        receipt = _document(receipt_path)
        export = receipt.get('consumerExport', {})
        if (export.get('candidate') != str(incoming) or export.get('candidateManifestSha256') != manifest_sha or export.get('status') != 'exported'):
            fail('INTAKE_BINDING_SPEC_RECEIPT', str(receipt_path), 'Receipt must pin this exact owned exported candidate')
    out = new_output(output, [incoming, safe(target), mapping] + ([safe(policy)] if policy else []) + ([safe(preparation_receipt)] if preparation_receipt else []) + ([safe(resolution['sourceProject']),safe(resolution['editorPath'])] if resolution else []))
    write_json(out / 'intake-spec.json', spec)
    from .adoption import project_requirements
    requirements, conflicts = project_requirements(incoming, safe(target), manifest['targetProfile'], resolution=resolution)
    report = dict(projectRequirements=requirements, requirementConflicts=conflicts, owningExport='exported', contract='beaver-intake-bindings-spec/1', candidateRoot=str(incoming),
                  candidateManifestSha256=manifest_sha, spec=str(out / 'intake-spec.json'),
                  specSha256=digest_file(out / 'intake-spec.json'), compilerInputCount=len(compiler),
                  uncoveredCompilerInputs=uncovered, targetWrites=False, native='not_run', intakeApply='not_run',
                  sourceCandidateValidation={k:manifest.get(k) for k in ('native', 'diagnostics', 'staticPresentation', 'visibleEdits', 'player', 'business')},
                  typedCoverageStatus=_document(incoming / required[2])['coverageStatus'])
    # This is the existing intake.plan implementation; the generated document
    # has no bypass, surrogate baseline, or relaxation of compiler coverage.
    try:
        report['intakePlan'] = preview(incoming, target, out / 'intake-spec.json', out / 'consumer-plan', package_evidence, expected_package_evidence)
        report['status'] = 'planned'
    except BeaverError as error:
        report['status'] = error.status
        report['intakePlan'] = dict(status=error.status, error=error.as_dict())
    if classification is not None:
        from .intake_binding_dependencies import analyze
        report['dependencyAnalysis'] = analyze(incoming,target,classification['sourceProject'],out/'dependency-analysis',dotnet=classification['dotnet'],sdk_root=classification['sdkRoot'],additions=spec['additions'],package_evidence=package_evidence,expected_package_evidence=expected_package_evidence,script_target_root=classification.get('scriptTargetRoot'),runtime_readback=classification.get('runtimeReadback'))
    if receipt is not None:
        receipt['owningExport'] = 'exported'
        receipt['supersedesReceipt'] = dict(path=str(receipt_path), sha256=digest_file(receipt_path), policy='new adjacent correction; original receipt unchanged; no native replay')
        receipt['consumerSpec'] = dict(path=report['spec'], sha256=report['specSha256'], intakePlanStatus=report['status'])
        write_json(out / 'preparation-receipt.json', receipt)
        report['correctedReceipt'] = str(out / 'preparation-receipt.json')
    write_json(out / 'consumption-report.json', report)
    result = dict(status=report['status'], report=str(out / 'consumption-report.json'), spec=report['spec'],
                specSha256=report['specSha256'], uncoveredCompilerInputs=len(uncovered),
                intakePlan=report['intakePlan'], native='not_run', targetWrites=False)
    if 'dependencyAnalysis' in report:result['dependencyAnalysis']=report['dependencyAnalysis']
    return result
