"""Join UI family coverage only after independent saved-field/algorithm checks."""
import copy
from .prefab_component_coverage import _unity_persistent_identity


def merge_sort(readback, plan, saved, *, queue_verified):
    result=copy.deepcopy(readback)
    continuation=plan.get('staticSortContinuation')or{}
    expected=continuation.get('sourceComponents',[])
    if not expected or queue_verified is not True:return result
    records={}
    for prefab in saved.get('sourcePrefabs',[]):
        for queue in (prefab.get('staticSortFields')or{}).get('persistentAsset',[]):
            for row in queue.get('sourceFields',[])+queue.get('sourceSortRoots',[]):
                records.setdefault(row.get('sourceId'),[]).append((row,queue))
    for source in expected:
        sid=source['sourceId'];matches=records.get(sid,[])
        if len(matches)!=1:raise ValueError('SORT_COVERAGE_IDENTITY_AMBIGUOUS:'+sid)
        marker,queue=matches[0]
        identity=_unity_persistent_identity(dict(guid=marker.get('markerGuid'),localFileId=marker.get('markerLocalFileId')))
        driver=_unity_persistent_identity(dict(guid=queue.get('driverGuid'),localFileId=queue.get('driverLocalFileId')))
        if (identity is None or driver is None or marker.get('markerPersistent')is not True or
                queue.get('driverPersistent')is not True or marker.get('verified')is not True or
                marker.get('actualSourceId')!=sid or marker.get('identityComponentEnabled')is not False):
            raise ValueError('SORT_COVERAGE_SAVED_IDENTITY_INVALID:'+sid)
        native=dict(sourceId=sid,node=source['sourceNodeId'],type=source['sourceType'],
            nativeType=source['expectedMarkerType'],**identity,persistent=True,sourceIdentityVerified=True,
            componentUuid=identity['guid']+':'+str(identity['localFileId']),
            sourceEnabled=source['sourceEnabled'],nativeEnabled=False,nativeStaticFieldsVerified=True,
            representation='native-component',status='disabled',disabledReason='native-static-sort-driver',
            queueDriverGuid=driver['guid'],queueDriverLocalFileId=driver['localFileId'],queueDriverPersistent=True,
            queueProofVerified=True,sourceBehaviorStatus='dynamic_not_run',coverageRole='disabled-component')
        if any(row.get('sourceId')==sid for key in ('components','disabledComponents','retainedComponents')for row in result.get(key,[])):
            raise ValueError('SORT_COVERAGE_NATIVE_COUNTERPART_AMBIGUOUS:'+sid)
        result.setdefault('disabledComponents',[]).append(native)
    return result


def gate_layout(readback,plan,saved):
    """A serialized slot alone cannot prove the source Layout or Widget math."""
    result=copy.deepcopy(readback);proofs={}
    contract=plan.get('layoutCompletion')
    if not contract:return result,proofs
    from .prefab_static_layout_completion import verify_readback,verify_native_probe
    prefabs={row['sourceId']:row for row in plan.get('sourcePrefabs',[])}
    passed=set()
    for actual in saved.get('sourcePrefabs',[]):
        source=prefabs.get(actual.get('sourceId'))
        if source is None:continue
        nodes=set(source.get('nodes',[]))
        subset=dict(contract,nodes=[row for row in contract['nodes']if row['sourceNodeId']in nodes])
        if not subset['nodes']:continue
        fields=verify_readback(subset,actual.get('staticLayoutFields',[]))
        probe=verify_native_probe(subset,actual.get('staticLayoutProbe'))
        if fields['errors']or probe['errors']:continue
        passed.update(slot['sourceComponentId']for node in subset['nodes']for slot in node['layouts']+node['widgets'])
    for key in ('components','disabledComponents'):
        for row in result.get(key,[]):
            if row.get('representation')!='native-component-slot':continue
            sid=row.get('sourceId');row['nativeStaticFieldsVerified']=sid in passed
            if sid not in passed:continue
            identity=_unity_persistent_identity(row)
            if identity is None:continue
            proofs[sid]=dict(verified=True,scope='saved-source-layout-fields-and-disposable-algorithm-probe',
                resolvedCodes=['MULTIPLE_LAYOUT_HANDOFF','WIDGET_CONTEXT_UNSUPPORTED','LAYOUT_NOT_VERIFIED'],
                evidence=dict(sourceId=sid,**identity,nativeType=row.get('nativeType'),representation='native-component-slot',
                    nativeSlotId=sid,persistent=True,sourceIdentityVerified=True,
                    requirements={'layout':True,'layout-context':True,'layout-algorithm':True}))
    return result,proofs
