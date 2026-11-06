"""Generate existing native batch plans for missing complete asset identities.

These plans are diagnostic requests only. The caller must regenerate on its
approved final source before any Editor run; this module never starts Unity.
"""
from pathlib import Path
from .batch import plan as batch_plan
from .io import safe,write_json
from .output_limits import digest_file
from .errors import fail


def requests(output,source_project,target,reuse_scan):
    out=Path(output);source,target=safe(source_project),safe(target)
    # Only exact byte/meta/GUID/importer matches need identity acquisition.
    # Mismatches remain separate conflicts and cannot be repaired by a readback.
    codes={}
    for row in reuse_scan.get('conflicts',[]):
        pair=(row.get('source'),row.get('collisionTarget'))
        if all(pair):codes.setdefault(pair,set()).add(row.get('code'))
    pairs=[p for p,c in codes.items() if c and all('identity' in str(x) or 'object_set' in str(x) for x in c)]
    generated=[]
    for role,project,column in (('source',source,0),('target',target,1)):
        paths=sorted({p[column] for p in pairs})
        if not paths:continue
        steps=[dict(kind='asset.inspect',assetPath=p) for p in paths]
        spec=dict(schemaVersion=2,operation='batch',steps=steps)
        sp=out/(role+'-asset-inspection-spec.json');write_json(sp,spec)
        result=batch_plan(project,sp,out/(role+'-asset-inspection-plan'))
        generated.append(dict(role=role,project=str(project),spec=str(sp),specSha256=digest_file(sp),plan=result,
                              executeAllowedNow=False,rule='Regenerate for the GREA-approved final source/current target; no old partial-source native replay',
                              futureCommand=dict(command='beaver batch apply',requiredInputs=['--plan actual-regenerated-batch-plan','--expected-plan actual-plan-sha256','--editor-path matching-editor','--out new-stage'])))
    doc=dict(contract='beaver-intake-asset-inspection-requests/1',pairs=[dict(source=a,target=b) for a,b in pairs],plans=generated,
             evidenceBundleTemplate=dict(contract='beaver-native-asset-reuse-evidence/1',sourceStage=dict(requiredInput='actual successful source inspection transaction'),targetStage=dict(requiredInput='actual successful target inspection transaction')),
             native='not_run',targetWrites=False,sourceGate='approved_final_source_required')
    write_json(out/'asset-inspection-requests.json',doc)
    return dict(path=str(out/'asset-inspection-requests.json'),sha256=digest_file(out/'asset-inspection-requests.json'),plans=len(generated),native='not_run')
