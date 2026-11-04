"""Keep native diagnostics, retained state, presentation and Player distinct."""
import copy

from .io import diagnostic

DYNAMIC_ONLY={'SPINE_DYNAMIC_BEHAVIOR_INCOMPLETE','ANIMATION_DYNAMIC_CURVES_NOT_LOWERED'}


def native_diagnostics(values):
    if not isinstance(values,list):
        return [diagnostic('NATIVE_DIAGNOSTICS_INVALID','readback.diagnostics','Expected the complete native diagnostic array')]
    rows=[]
    for index,value in enumerate(values):
        if isinstance(value,str):
            code,separator,_=value.partition(':')
            code=code.strip() if separator and code.strip() else 'NATIVE_DIAGNOSTIC'
            row=diagnostic(code,'readback.diagnostics['+str(index)+']',value)
        elif isinstance(value,dict) and isinstance(value.get('code'),str) and value['code']:
            row=copy.deepcopy(value)
        else:
            row=diagnostic('NATIVE_DIAGNOSTICS_INVALID','readback.diagnostics['+str(index)+']','Malformed native diagnostic')
        row['origin']='native-readback';row['nativeDiagnosticIndex']=index
        rows.append(row)
    return rows


def coverage_readback(readback,spine_readback=None):
    """Normalize actual saved records; never infer presence from convertible."""
    result=copy.deepcopy(readback)
    rows=result.get('components')
    if not isinstance(rows,list):rows=[]
    result['components']=[row for row in rows if row.get('status')=='native']
    result['retainedComponents']=[row for row in rows if row.get('status')=='retained']
    result['disabledComponents']=[row for row in rows if row.get('status')=='disabled']
    result['diagnostics']=native_diagnostics(readback.get('diagnostics'))
    fields=[]
    animations={}
    for prefab in readback.get('sourcePrefabs')or[]:
        for row in prefab.get('staticFieldBindings')or[]:
            binding=row.get('binding')or{}
            fields.append(binding)
        for row in prefab.get('staticAnimationFields')or[]:
            animations[row.get('sourceComponentId')]=row.get('binding')or{}
    result['staticFieldBindings']=fields
    # These observations are already normalized at the top level. Retaining
    # their nested copies would count the same evidence twice or treat a
    # retained-only object as an independent native component.
    for prefab in result.get('sourcePrefabs')or[]:
        prefab.pop('components',None);prefab.pop('staticFieldBindings',None)
    by_source={row.get('sourceId'):row for row in fields}
    spine_ids=set((spine_readback or{}).get('sourceComponentIds',[]))if (spine_readback or{}).get('status')=='verified'else set()
    for row in result['retainedComponents']:
        source=row.get('sourceId');binding=by_source.get(source,{})
        animation=animations.get(source,{})
        verified=(binding.get('nativeIdentityVerified')is True and binding.get('fieldsVerified')is True
                  or animation.get('status')=='reference_fields_verified'and animation.get('markerDisabled')is True
                  and animation.get('animatorDisabled')is True or source in spine_ids)
        row['verified']=bool(verified);row['fieldsVerified']=bool(verified)
    for row in result['disabledComponents']:
        row['verified']=row.get('sourceEnabled')is False and row.get('nativeEnabled')is False and row.get('sourceIdentityVerified')is True
        row['fieldsVerified']=row['verified']
    if spine_readback is not None:result['staticSpineContinuation']=spine_readback
    return result


def statuses(editor,diagnostics,coverage,level):
    """Editor execution supplies no Player evidence, including a clean import."""
    if level!='editor' or editor=='not_run':
        return dict(editorValidation=editor,nativeStaticValidation='not_run',
                    retentionValidation='not_run',staticPresentationValidation='not_run',
                    runtimeCheck='not_run',playerValidation='not_run')
    blocking=[row for row in diagnostics if row.get('code') not in DYNAMIC_ONLY]
    # A completed import can have real unrecovered static components. Preserve
    # that partial state; independent native mismatch diagnostics still fail.
    mismatch=any(any(token in row.get('code','')for token in ('MISMATCH','CHANGED','INVALID','FAILED','CONFLICT'))for row in blocking)
    native=coverage.get('nativeStaticValidation','partial')
    presentation=coverage.get('staticPresentationValidation','partial')
    if isinstance(presentation,dict):presentation=presentation.get('status','partial')
    if editor=='fail' or mismatch:native='fail';presentation='fail'
    elif blocking:
        native='partial' if native=='pass' else native
        presentation='partial' if presentation=='pass' else presentation
    completed_editor='fail' if editor=='fail' else 'pass' if not blocking and native=='pass' else 'partial'
    return dict(editorValidation=completed_editor,nativeStaticValidation=native,
                retentionValidation='fail' if mismatch else coverage.get('retentionValidation','not_run'),
                staticPresentationValidation=presentation,runtimeCheck='not_run',playerValidation='not_run')
