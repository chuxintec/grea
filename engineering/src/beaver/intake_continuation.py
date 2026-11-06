"""Connect real diagnostic plans without fabricating future project state."""
from pathlib import Path
from .io import write_json
from .output_limits import digest_file


def connect(output, *, candidate, manifest, manifest_sha, target, mapping, spec, consumption,
            analysis=None, completion=None, reuse=None):
    out=Path(output)
    def artifact(path):
        return dict(path=str(path),sha256=digest_file(Path(path)))
    stages=[dict(id='approved-final-source',status='required_before_project_writes',
                 current=dict(candidate=str(candidate),manifestSha256=manifest_sha,
                              sourceState={k:manifest.get(k) for k in ('native','diagnostics','staticPresentation','visibleEdits','player','business')}),
                 rule='Current diagnostic/preparation evidence is not approval; GREA must choose a verified final source and regenerate all pinned plans')]
    if completion:
        stages.append(dict(id='complete-script-bindings',dependsOn=['approved-final-source'],status='planned_not_executed' if completion.get('status')=='planned' else 'blocked',artifacts=completion,
                           regenerate=dict(command='beaver intake bindings-plan',requiredInputs=['--source approved-final-source','--target retained-target','--complete-from verified-identity-candidate','--expected-candidate actual-manifest-sha256','--dependency-report fresh-dependency-evidence','--out new-directory']),
                           executeAfterApproval=dict(command='beaver intake prepare-bindings',requiredInputs=['--plan exact-regenerated-plan','--expected-plan actual-plan-sha256','--editor-path matching-editor','--out independent-new-copy']),
                           native='not_run',rule='All six original/retained identities and fields must pass native save and independent reopen on the accepted final source; old partial gates are not replayed here'))
    else:
        stages.append(dict(id='complete-script-bindings',dependsOn=['approved-final-source'],status='requires_explicit_binding_source',native='not_run'))
    stages.append(dict(id='owned-prepared-export',dependsOn=['complete-script-bindings'],status='future_actual_output_required',rule='Use the owned export produced from actual successful binding preparation. No predicted manifest, rewritten YAML or surrogate baseline',requiredOutputs=['actual candidate root','actual manifest SHA256','native oracle','complete bindings fragment','lineage']))
    stages.append(dict(id='script-only-batches',dependsOn=['owned-prepared-export'],status='diagnostic_plans_generated' if analysis else 'requires_final_source_analysis',artifacts=analysis or {},
                       rule='Regenerate on the real accepted source and current target. Every batch <=16 new scripts, no padding textures. After predecessor native success, replan against actual target; later snapshots are never invented',native='not_run'))
    stages.append(dict(id='retained-resource-closure',dependsOn=['owned-prepared-export'],status='complete_scan_generated' if reuse else 'requires_exact_asset_scan',
                       artifacts=reuse or {},rule='Same GUID/content/meta/importer plus native object identity evidence are required for externalAssets. All mismatches and missing evidence stay blocked; no collision is ignored'))
    stages.append(dict(id='complete-prefab-consumer',dependsOn=['script-only-batches','retained-resource-closure'],status=consumption.get('status','not_run'),
                       spec=artifact(spec),currentDiagnosticConsumption=consumption,
                       regenerate=dict(command='beaver intake spec-bindings',requiredInputs=['--candidate actual-six-binding-owned-export','--expected-manifest actual-sha256','--target actual-retained-target','--mapping reviewed-mapping','--reuse-exact-assets','--classify with actual source/SDK/runtime readback','--package-evidence fresh-matching-context and SHA256','--out new-directory']),
                       rule='Current diagnostic spec is not the future final target plan. Formal apply requires complete compiler/resource/reference coverage and original source/static/audit acceptance; plan success does not mean adoption',native='not_run'))
    document=dict(contract='beaver-intake-continuation/1',candidateManifestSha256=manifest_sha,target=str(target),mapping=artifact(mapping),stages=stages,targetWrites=False,native='not_run',formalAdoption='not_run',sourceAcceptance='not_promoted')
    write_json(out/'continuation-plan.json',document)
    return dict(path=str(out/'continuation-plan.json'),sha256=digest_file(out/'continuation-plan.json'),status='requires_final_source_and_actual_native_results')
