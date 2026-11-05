"""Keep native diagnostics, retained state, presentation and Player distinct."""
import copy
import json
import re

from .io import diagnostic

NATIVE_IMPORT_STATUSES=('imported','pass','partial')
SAVED_SOURCE_SCOPES=('source-node-subset','saved-source-node-subset')

DYNAMIC_ONLY={'SPINE_DYNAMIC_BEHAVIOR_INCOMPLETE','ANIMATION_DYNAMIC_CURVES_NOT_LOWERED'}
_RECONCILED_FAMILY_REQUIREMENTS={
    'MULTIPLE_LAYOUT_HANDOFF':{'layout-context','layout-algorithm'},
    'WIDGET_CONTEXT_UNSUPPORTED':{'layout-context','layout-algorithm'},
    'LAYOUT_NOT_VERIFIED':{'layout'},
    'MISSING_OUTLINE_LABEL':{'same-node-label'},
}
_COMPONENT_ID=re.compile(r'^[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+(?:#[^\s]*)?$')


def _diagnostic_key(row):
    return (row.get('sourceId')or row.get('sourceComponentId'),row.get('code'),row.get('location'),row.get('message'))


def deduplicate_diagnostics(values):
    """Merge normalized observations without relabelling source as native."""
    grouped={}
    for row in values:
        key=_diagnostic_key(row)
        current=grouped.setdefault(key,copy.deepcopy(row))
        for field in ('sourceEvidence','origins','nativeDiagnosticIndexes'):
            combined=[*(current.get(field)or[]),*(row.get(field)or[])]
            if field=='origins' and row.get('origin'):
                combined.append(row['origin'])
            if field=='nativeDiagnosticIndexes' and type(row.get('nativeDiagnosticIndex'))is int:
                combined.append(row['nativeDiagnosticIndex'])
            unique={json.dumps(value,sort_keys=True,ensure_ascii=False,default=str):value for value in combined}
            if unique:current[field]=list(unique.values())
        # The coverage assessment annotates a matching early native observation
        # using the actual saved counterpart. Preserve that stronger annotation
        # as well as every original observation; statuses still checks coverage.
        if row.get('resolution')=='native-counterpart-present' and isinstance(row.get('resolutionEvidence'),dict):
            current['resolution']=row['resolution'];current['resolutionEvidence']=copy.deepcopy(row['resolutionEvidence'])
            current['resolved']=row.get('resolved')is True
            if row.get('phase'):current['phase']=row['phase']
        if row.get('resolutionClassification')=='resolved' and isinstance(row.get('currentResolutionEvidence'),dict):
            current['resolutionClassification']=row['resolutionClassification']
            current['resolutionScope']=row.get('resolutionScope')
            current['currentResolutionEvidence']=copy.deepcopy(row['currentResolutionEvidence'])
            current['resolved']=True
        ranks={'info':0,'warning':1,'error':2,'fatal':3}
        if ranks.get(row.get('severity'),0)>ranks.get(current.get('severity'),0):current['severity']=row['severity']
    return list(grouped.values())


def native_diagnostics(values):
    if not isinstance(values,list):
        return [diagnostic('NATIVE_DIAGNOSTICS_INVALID','readback.diagnostics','Expected the complete native diagnostic array')]
    rows=[]
    for index,value in enumerate(values):
        if isinstance(value,str):
            code,separator,body=value.partition(':')
            code=code.strip() if separator and code.strip() else 'NATIVE_DIAGNOSTIC'
            subject=body.strip().split(maxsplit=1)[0]if separator and body.strip()else None
            source_id=subject if isinstance(subject,str)and _COMPONENT_ID.fullmatch(subject)else None
            location=source_id or 'readback.diagnostics'
            row=diagnostic(code,location,value,source_id)
            row['rawDiagnostic']=value
            if code=='COMPONENT_NOT_IMPORTED':
                row['phase']='initial-component-creation'
                row['resolution']='pending-source-coverage-join'
        elif isinstance(value,dict) and isinstance(value.get('code'),str) and value['code']:
            row=copy.deepcopy(value)
            if row['code']=='COMPONENT_NOT_IMPORTED' and not row.get('phase'):
                row['phase']='initial-component-creation'
        else:
            row=diagnostic('NATIVE_DIAGNOSTICS_INVALID','readback.diagnostics['+str(index)+']','Malformed native diagnostic')
        row['origin']='native-readback';row['nativeDiagnosticIndex']=index
        row['sourceEvidence']=[{'origin':'native-readback','index':index,'raw':value}]
        rows.append(row)
    deduped=[];by_key={}
    for row in rows:
        key=_diagnostic_key(row)
        if key not in by_key:
            value=dict(row);value['nativeDiagnosticIndexes']=[row.get('nativeDiagnosticIndex')]
            by_key[key]=value;deduped.append(value)
        else:
            existing=by_key[key]
            existing['nativeDiagnosticIndexes'].append(row.get('nativeDiagnosticIndex'))
            existing['sourceEvidence'].extend(row.get('sourceEvidence',[]))
    return deduped


def _component_peer_duplicates(readback):
    """Keep source peer multiplicity before normalization coalesces observations."""
    from .prefab_component_coverage import _component_role,_unity_persistent_identity
    result=[];stack=[('root',readback)];visited=set()
    while stack:
        scope,container=stack.pop()
        if id(container) in visited:continue
        visited.add(id(container))
        for key in ('components','retainedComponents','disabledComponents'):
            groups={}
            values=container.get(key)
            for row in values if isinstance(values,list)else[]:
                if not isinstance(row,dict)or not isinstance(row.get('sourceId'),str)or not row['sourceId']:continue
                role=_component_role(row)[0]
                if key=='retainedComponents' and row.get('coverageRole')is None:
                    role='retained-carrier'
                elif key=='disabledComponents' and row.get('coverageRole')is None and role!='native-renderer':
                    role='disabled-component'
                groups.setdefault((row['sourceId'],role),[]).append(row)
            for (sid,role),rows in groups.items():
                if len(rows)<2:continue
                identities=[]
                for row in rows:
                    identity=_unity_persistent_identity(row)
                    if identity not in identities:identities.append(identity)
                result.append(dict(sourceId=sid,coverageRole=role,scope=scope+'/'+key,
                    duplicateCount=len(rows),persistentIdentity=identities[0]if len(identities)==1 else None,
                    persistentIdentities=identities))
        for key in ('sourcePrefabs','prefabInstances','candidatePrefabInstances','instances'):
            values=container.get(key)
            for index,child in enumerate(values if isinstance(values,list)else[]):
                if isinstance(child,dict):stack.append((scope+'/'+key+'/'+str(index),child))
    return result


def coverage_readback(readback,spine_readback=None):
    """Normalize actual saved records; never infer presence from convertible."""
    result=copy.deepcopy(readback)
    result['componentPeerDuplicates']=_component_peer_duplicates(readback)
    from .prefab_component_coverage import _dedupe_exact_rows,_nested_rows,_native_identity_verified
    rows=_dedupe_exact_rows(_nested_rows(result,'components'))
    for row in rows:
        if (row.get('type')=='sp.Skeleton' and row.get('nativeType')=='NativeStaticSpineReference'
                and row.get('status')=='retained' and row.get('representation')=='disabled-source-data-carrier'):
            row['coverageRole']='retained-carrier'
    result['components']=[row for row in rows if row.get('status')=='native']
    result['retainedComponents']=_dedupe_exact_rows(
        [*(_nested_rows(result,'retainedComponents')),*[row for row in rows if row.get('status')=='retained']])
    result['disabledComponents']=_dedupe_exact_rows(
        [*(_nested_rows(result,'disabledComponents')),*[row for row in rows if row.get('status')=='disabled']])
    result['diagnostics']=native_diagnostics(readback.get('diagnostics'))
    fields=[]
    animations={}
    for row in _nested_rows(readback,'staticFieldBindings'):
        binding=dict(row.get('binding')) if isinstance(row.get('binding'),dict) else {}
        binding.setdefault('sourceId',row.get('sourceComponentId'))
        fields.append(binding)
    for row in _nested_rows(readback,'staticAnimationFields'):
        binding=row.get('binding')
        animations[row.get('sourceComponentId')]=binding if isinstance(binding,dict) else {}
    result['staticFieldBindings']=_dedupe_exact_rows(fields)
    by_source={row.get('sourceId'):row for row in result['staticFieldBindings']}
    spine_ids=set((spine_readback or{}).get('sourceComponentIds',[]))if (spine_readback or{}).get('status')=='verified'else set()
    for row in result['retainedComponents']:
        source=row.get('sourceId');binding=by_source.get(source,{})
        animation=animations.get(source,{})
        verified=(binding.get('nativeIdentityVerified')is True and binding.get('fieldsVerified')is True
                  or animation.get('status')=='reference_fields_verified'and animation.get('markerDisabled')is True
                  and animation.get('animatorDisabled')is True or source in spine_ids)
        row['verified']=bool(verified);row['fieldsVerified']=bool(verified)
    for row in result['disabledComponents']:
        row['sourceEnabledValuePreserved']=type(row.get('sourceEnabled')) is bool
        reason=row.get('disabledReason')
        row['sourceBehaviorStatus']=('not_restored_business_safety' if reason=='static-button-business-safety'
                                     else 'source_disabled' if reason=='source-disabled' or row.get('sourceEnabled') is False
                                     else 'unknown_disabled_reason')
        row['persistentIdentityVerified']=_native_identity_verified(row,'unity')
        row['disabledReadbackVerified']=(row['nativeEnabled'] is False and row['persistentIdentityVerified']
                                        and row['sourceEnabledValuePreserved'])
        # A business-safety disabled native component is not a retained data
        # carrier. Its source enabled value and identity are separate from the
        # source static field proof supplied by the native importer.
        row['verified']=row.get('sourceEnabled') is False and row['disabledReadbackVerified']
        row['fieldsVerified']=row['verified']
    progress_rows=[]
    for row in _nested_rows(readback,'staticProgressFields'):
        sid=row.get('sourceComponentId')
        if not isinstance(sid,str)or not sid:continue
        progress=dict(row)
        progress.update(sourceId=sid,status='retained',representation='native-static-progress-carrier',
            type='cc.ProgressBar',nativeType='UnityStaticProgress',coverageRole='retained-carrier',
            guid=row.get('carrierGuid'),localFileId=row.get('carrierLocalFileId'),
            componentUuid=(str(row.get('carrierGuid'))+':'+str(row.get('carrierLocalFileId'))
                           if row.get('carrierGuid')and row.get('carrierLocalFileId')is not None else None),
            sourceIdentityVerified=row.get('verified')is True and _native_identity_verified({
                'guid':row.get('carrierGuid'),'localFileId':row.get('carrierLocalFileId'),
                'sourceIdentityVerified':True,'persistent':True},'unity'),
            persistent=row.get('verified')is True and row.get('carrierDisabled')is True and _native_identity_verified({
                'guid':row.get('carrierGuid'),'localFileId':row.get('carrierLocalFileId'),
                'sourceIdentityVerified':True,'persistent':True},'unity'),
            verified=row.get('verified')is True and row.get('carrierDisabled')is True and row.get('barSpritePersistent')is True
                and _native_identity_verified({'guid':row.get('carrierGuid'),'localFileId':row.get('carrierLocalFileId'),
                    'sourceIdentityVerified':True,'persistent':True},'unity'),
            fieldsVerified=row.get('verified')is True and row.get('carrierDisabled')is True and row.get('barSpritePersistent')is True
                and _native_identity_verified({'guid':row.get('carrierGuid'),'localFileId':row.get('carrierLocalFileId'),
                    'sourceIdentityVerified':True,'persistent':True},'unity'),
            nativeEnabled=not row.get('carrierDisabled',False),
            retentionEvidenceKind='static-progress-carrier-readback')
        bar_rows=[item for item in rows if item.get('sourceId')==row.get('barSpriteSourceId')
                  and item.get('nativeType')=='UnityEngine.UI.Image']
        bar_ids={(item.get('guid'),item.get('localFileId')) for item in bar_rows}
        bar_verified=(bool(bar_rows) and len(bar_ids)==1
            and all(_native_identity_verified(item,'unity') for item in bar_rows)
            and _native_identity_verified({'guid':row.get('barSpriteGuid'),'localFileId':row.get('barSpriteLocalFileId'),
                'sourceIdentityVerified':True,'persistent':True},'unity')
            and bar_ids=={(row.get('barSpriteGuid'),row.get('barSpriteLocalFileId'))})
        progress['barSpriteIdentityVerified']=bar_verified
        progress['verified']=progress['verified'] and bar_verified
        progress['fieldsVerified']=progress['fieldsVerified'] and bar_verified
        carriers=[item for item in result['retainedComponents'] if item.get('sourceId')==sid
                  and item.get('nativeType')=='UnityStaticProgress'
                  and _native_identity_verified(item,'unity') and item.get('nativeEnabled')is False
                  and item.get('guid')==progress['guid'] and item.get('localFileId')==progress['localFileId']]
        if len(carriers)==1 and row.get('carrierDisabled')is True:
            # The specialized receipt describes this same physical component,
            # rather than introducing a second retained entity.
            carrier=carriers[0];representation=carrier.get('representation')
            carrier.update(progress);carrier['representation']=representation
            continue
        progress_rows.append(progress)
    result['retainedComponents']=_dedupe_exact_rows([*result['retainedComponents'],*progress_rows])
    if spine_readback is not None:result['staticSpineContinuation']=spine_readback
    return result


def _indexed_components(coverage):
    rows=coverage.get('components',[]) if isinstance(coverage,dict) else []
    counts={};index={}
    for row in rows if isinstance(rows,list) else []:
        if not isinstance(row,dict):continue
        source_id=row.get('sourceId')
        if not isinstance(source_id,str)or not source_id:continue
        counts[source_id]=counts.get(source_id,0)+1
        index.setdefault(source_id,row)
    return index,{source_id for source_id,count in counts.items()if count!=1}


def _identity_for(covered,source_id):
    from .prefab_component_coverage import _unity_persistent_identity
    if not isinstance(covered,dict)or covered.get('sourceId')!=source_id:return None,None,None
    native=covered.get('nativeComponentReadback')
    identity=_unity_persistent_identity(native)if isinstance(native,dict)else None
    if identity is None:return native,None,None
    layout_slot=(native.get('representation')=='native-component-slot'
        and native.get('nativeSlotId')==source_id
        and native.get('nativeType')=='NativeStaticLayoutCompletion'
        and covered.get('nativeSlotId')==source_id
        and isinstance(covered.get('staticLayoutContinuationBinding'),dict)
        and covered['staticLayoutContinuationBinding'].get('sourceComponentId')==source_id
        and covered['staticLayoutContinuationBinding'].get('physicalNativeType')=='NativeStaticLayoutCompletion')
    if native.get('representation')!='native-component' and not layout_slot:return native,None,None
    return native,identity,layout_slot


def _exact_current_resolution(row,covered,source_id,*,allow_dynamic=False):
    native,identity,layout_slot=_identity_for(covered,source_id)
    if identity is None or not isinstance(native,dict):return False
    current=row.get('currentResolutionEvidence')
    detail=current.get('evidence')if isinstance(current,dict)and isinstance(current.get('evidence'),dict)else current
    exact=(isinstance(detail,dict)and detail.get('sourceId')==source_id
        and detail.get('guid')==identity['guid']and detail.get('localFileId')==identity['localFileId']
        and detail.get('nativeType')==native.get('nativeType')
        and detail.get('representation')==native.get('representation')
        and (not layout_slot or detail.get('nativeSlotId')==source_id))
    if not exact:return False
    if (covered.get('nativeStatus')!='pass' or covered.get('disposition')not in('native','disabled')):
        return False
    if (allow_dynamic and row.get('code')=='SCROLL_PHYSICS_NOT_VERIFIED'
            and (covered.get('nativeStaticFieldsVerified')is not True
                 or native.get('nativeStaticFieldsVerified')is not True)):
        return False
    if row.get('code')=='COMPONENT_NOT_IMPORTED':
        return (row.get('resolutionClassification')=='resolved'
            and row.get('resolutionScope')=='native-static-component-creation'
            and isinstance(current,dict)and current.get('sourceId')==source_id
            and current.get('guid')==identity['guid']and current.get('localFileId')==identity['localFileId']
            and current.get('nativeStaticFieldsVerified')is True
            and current.get('disposition')==covered.get('disposition')
            and covered.get('nativeStatus')=='pass'and covered.get('disposition')in('native','disabled')
            and covered.get('nativeStaticFieldsVerified')is True
            and native.get('nativeStaticFieldsVerified')is True)
    from .unity_diagnostic_resolution import _FAMILY_REQUIREMENTS
    requirements=_FAMILY_REQUIREMENTS.get(row.get('code'))
    if not requirements:return False
    expected_class='remaining-dynamic' if allow_dynamic else 'resolved'
    scope_matches=(isinstance(current,dict) and (row.get('resolutionScope')==current.get('scope')
        or allow_dynamic and row.get('code')=='SCROLL_PHYSICS_NOT_VERIFIED'
           and row.get('resolutionScope')=='dynamic-scroll-physics'))
    family_valid=(row.get('resolutionClassification')==expected_class and isinstance(current,dict)
        and scope_matches
        and row.get('code')in current.get('resolvedCodes',[])
        and isinstance(detail.get('requirements'),dict)
        and all(detail['requirements'].get(name)is True for name in requirements)
        and detail.get('persistent')is True and detail.get('sourceIdentityVerified')is True
        and isinstance(current.get('nativeIdentity'),dict)
        and current['nativeIdentity'].get('guid')==identity['guid']
        and current['nativeIdentity'].get('localFileId')==identity['localFileId']
        and current['nativeIdentity'].get('nativeType')==native.get('nativeType')
        and current['nativeIdentity'].get('representation')==native.get('representation'))
    if not family_valid:return False
    if row.get('code')=='SCROLL_PHYSICS_NOT_VERIFIED':
        return _scroll_static_evidence_still_matches(detail,native,source_id)
    return True


def _legacy_creation_resolution(row,covered,source_id):
    native,identity,layout_slot=_identity_for(covered,source_id)
    evidence=row.get('resolutionEvidence')
    return (row.get('code')=='COMPONENT_NOT_IMPORTED'
        and row.get('phase')=='initial-component-creation'
        and row.get('resolved')is True and row.get('resolution')=='native-counterpart-present'
        and isinstance(evidence,dict)and source_id is not None and identity is not None
        and covered.get('nativeStatus')=='pass'and covered.get('disposition')in('native','disabled')
        and covered.get('nativeStaticFieldsVerified')is True
        and evidence.get('sourceId')==source_id and evidence.get('guid')==identity['guid']
        and evidence.get('localFileId')==identity['localFileId']
        and evidence.get('disposition')==covered.get('disposition')
        and evidence.get('nativeStaticFieldsVerified')is True
        and (not layout_slot or evidence.get('representation')=='native-component-slot'
             and evidence.get('nativeSlotId')==source_id))


def _scroll_static_evidence_still_matches(detail,native,source_id):
    fields=native.get('staticScrollFields') if isinstance(native,dict) else None
    if not isinstance(detail,dict)or not isinstance(fields,dict):return False
    if detail.get('staticScrollFields')!=fields:return False
    if (fields.get('contract')!='monkey-unity-saved-scroll-static/1'
            or type(fields.get('schemaVersion'))is not int or fields.get('schemaVersion')!=1
            or fields.get('phase')!='persistent-saved-prefab'
            or fields.get('sourceId')!=source_id or fields.get('node')!=native.get('node')
            or fields.get('guid')!=native.get('guid') or fields.get('localFileId')!=native.get('localFileId')
            or type(fields.get('horizontal'))is not bool or type(fields.get('vertical'))is not bool
            or fields.get('horizontal')is not detail.get('horizontal')
            or fields.get('vertical')is not detail.get('vertical')
            or fields.get('contentNode')!=detail.get('contentNode')
            or fields.get('viewportNode')!=detail.get('viewportNode')
            or fields.get('contentPersistent')is not True
            or fields.get('viewportPersistent')is not True):
        return False
    for prefix in ('content','viewport'):
        payload=detail.get(prefix+'Identity')
        if not isinstance(payload,dict):return False
        guid=payload.get('guid');local_id=payload.get('localFileId')
        if (not isinstance(guid,str)or re.fullmatch(r'[0-9a-f]{32}',guid)is None
                or type(local_id)is not int or local_id==0 or not -(1<<63)<=local_id<(1<<63)):
            return False
        uuid=guid+':'+str(local_id)
        path=payload.get('rootIdentityPath')
        if (fields.get(prefix+'Guid')!=guid or fields.get(prefix+'LocalFileId')!=local_id
                or payload.get('ownerComponentUuid')!=uuid
                or not isinstance(path,list)or uuid not in path):
            return False
    return True


def unresolved_diagnostics(diagnostics,coverage):
    """Return revalidated blocking, resolved, and remaining-dynamic observations.

    This is the shared verification/freeze gate. Resolution annotations are
    history only unless their exact saved identity and named requirements are
    revalidated against current component coverage.
    """
    from .unity_diagnostic_resolution import is_dynamic_boundary
    if not isinstance(diagnostics,list):
        return {'blocking':[{'code':'NATIVE_DIAGNOSTICS_INVALID',
            'message':'Native diagnostics must be an array','rawDiagnostic':repr(diagnostics)}],
            'resolved':[],'remainingDynamic':[]}
    index,duplicates=_indexed_components(coverage)
    blocking=[];resolved=[];remaining_dynamic=[]
    for row in diagnostics:
        if not isinstance(row,dict):
            blocking.append({'code':'NATIVE_DIAGNOSTIC_INVALID',
                'message':'Malformed diagnostic row blocks verification','rawDiagnostic':repr(row)});continue
        source_id=row.get('sourceId')or row.get('sourceComponentId')
        covered=index.get(source_id)
        current_ok=(source_id not in duplicates and _exact_current_resolution(row,covered,source_id))
        legacy_ok=(source_id not in duplicates and _legacy_creation_resolution(row,covered,source_id))
        if row.get('code')=='SCROLL_PHYSICS_NOT_VERIFIED':
            # Scroll is dynamic only after axes, content and viewport have a
            # scoped, identity-bound native proof.
            scroll_static_ok=(source_id not in duplicates and
                isinstance(covered,dict) and covered.get('sourceType')=='cc.ScrollView'
                and _exact_current_resolution(row,covered,source_id,allow_dynamic=True))
            if scroll_static_ok:
                remaining_dynamic.append(row)
            else:
                blocking.append(row)
        elif is_dynamic_boundary(row,covered):
            remaining_dynamic.append(row)
        elif current_ok or legacy_ok:
            resolved.append(row)
        else:
            blocking.append(row)
    return {'blocking':blocking,'resolved':resolved,'remainingDynamic':remaining_dynamic}


def statuses(editor,diagnostics,coverage,level):
    """Editor execution supplies no Player evidence, including a clean import."""
    if level!='editor' or editor=='not_run':
        return dict(editorValidation=editor,nativeStaticValidation='not_run',
                    retentionValidation='not_run',staticPresentationValidation='not_run',
                    runtimeCheck='not_run',playerValidation='not_run')
    state=unresolved_diagnostics(diagnostics,coverage)
    blocking=state['blocking'];resolved=state['resolved']
    mismatch=any(any(token in str(row.get('code',''))for token in ('MISMATCH','CHANGED','INVALID','FAILED','CONFLICT'))
                 for row in blocking if isinstance(row,dict))
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
                staticPresentationValidation=presentation,runtimeCheck='not_run',playerValidation='not_run',
                resolvedNativeDiagnostics=resolved,blockingDiagnostics=blocking,
                remainingDynamicDiagnostics=state['remainingDynamic'])
