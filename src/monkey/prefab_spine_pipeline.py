"""Pinned Creator Spine component/resource stage; source assignments stay explicit."""
from pathlib import Path
from .io import read,load,sha,safe,inside,stage_manifest
from .sources.compiled import fail


def load_binding(ir,ir_path,receipt_path,expected_sha,resources):
    if not any((receipt_path,expected_sha,resources)):return None
    if not all((receipt_path,expected_sha,resources)):fail('SPINE_BINDING_ARGUMENTS','spine','Receipt, SHA and frozen resource root are required together')
    raw=read(safe(receipt_path));record=load(raw)
    if sha(raw)!=expected_sha or record.get('contract')!='monkey-spine-emission/1':fail('SPINE_BINDING_CHANGED','spine','Emission receipt differs')
    pins=record.get('pins',{})
    if pins.get('normalizedIrSha256')!=sha(read(ir_path)) or pins.get('sourceManifestSha256')!=ir['sourceManifestSha256']:
        fail('SPINE_BINDING_SOURCE_MISMATCH','spine','Source manifest or current IR pin differs')
    root=safe(resources);manifest=stage_manifest(root)
    if sha(read(root/'manifest.json'))!=pins.get('creatorClosureReceiptSha256'):
        fail('SPINE_CLOSURE_CHANGED','spine','Frozen resource manifest differs')
    material_profile=record.get('creatorMaterialProfile')
    if material_profile is not None:
        if (material_profile.get('contract')!='cocos24-builtin-spine-material-v1'
                or material_profile.get('evidenceStatus')!='source_to_internal_to_creator_builtin_pinned'
                or material_profile.get('targetMaterialUuid')!='default-spine-material'
                or material_profile.get('targetEffect')!='builtin-spine'
                or not isinstance(material_profile.get('contractSha256'),str)
                or len(material_profile.get('contractSha256',''))!=64
                or material_profile.get('contractSha256')!=pins.get('creatorMaterialContractSha256')):
            fail('SPINE_CREATOR_MATERIAL_PROFILE','spine','Creator built-in material profile is not consistently pinned')
    files={x['path']:x for x in manifest['files']};components={x['sourceId']:x for x in ir['components']}
    seen=set()
    for row in record['components']:
        sid=row['sourceComponentId'];c=components.get(sid)
        source_node=row['sourceNodeId']
        numeric_node=type(source_node)is int or (isinstance(source_node,str)and source_node.isascii()and source_node.isdigit())
        node_id=row['sourcePrefabId']+'#'+str(source_node) if numeric_node else source_node
        if sid in seen or not c or c['type']!='sp.Skeleton' or c['node']!=node_id:
            fail('SPINE_COMPONENT_IDENTITY',sid,'Source component or node differs')
        seen.add(sid)
        pose=row.get('creatorStaticPose')
        material=row.get('creatorMaterialBinding')
        if material_profile is not None:
            if (not pose or pose.get('policy')!='enabled_realtime_renderer_with_serialized_timeScale_zero'
                    or pose.get('nativeEnabled') is not True or pose.get('nativeTimeScale')!=0
                    or pose.get('animationFrozenBySerializedTimeScale') is not True
                    or pose.get('businessCallbacksExecuted') is not False
                    or pose.get('targetEngineSourceSha256')!='2e86383e7e7dfb93bc40ec1d7e44c6bb2b8ebe4e95c100ad16620bd24114329'
                    or pose.get('sourceMaterialRoute')!='Creator sp.Skeleton updateMaterial -> builtinResMgr.get(default-spine-material)'):
                fail('SPINE_CREATOR_STATIC_POSE','spine','Creator persistent t0 policy is absent or invalid')
            source_binding = (material.get('sourceMaterialBinding') or
                              ({'status': 'explicit'} if isinstance(material, dict)
                               and isinstance(material.get('sourceMaterialReferenceSourceId'), str)
                               and isinstance(material.get('sourceMaterialSourceId'), str) else {}))
            explicit_material = source_binding.get('status') == 'explicit'
            source_default_material = source_binding.get('status') == 'resolved_source_engine_default'
            if (not material or material.get('sourceComponentId')!=sid
                    or material.get('targetMaterialUuid')!='default-spine-material'
                    or material.get('contract')!='cocos24-builtin-spine-material-v1'
                    or material.get('contractSha256')!=material_profile.get('contractSha256')
                    or material.get('evidenceStatus')!='source_to_internal_to_creator_builtin_pinned'
                    or (explicit_material and (material.get('sourceMaterialReferenceSourceId')!=material_profile.get('sourceMaterialReferenceSourceId')
                                               or material.get('sourceMaterialSourceId')!=material_profile.get('sourceMaterialSourceId')))
                    or (source_default_material and (material.get('sourceMaterialReferenceSourceId') is not None
                                                     or material.get('sourceMaterialSourceId') is not None
                                                     or source_binding.get('sourceSha256')!='7cdc119e26aa6dceec4bd78ae30dd08f39daa2f0da5d914d2197a730b558a5e8'))
                    or not (explicit_material or source_default_material)):
                fail('SPINE_CREATOR_MATERIAL_BINDING',sid,'Exact source-to-built-in material mapping is absent')
            source_scale=pose.get('sourceTimeScale')
            if not isinstance(source_scale,dict) or source_scale.get('status') not in {'explicit','resolved_source_engine_default'}:
                fail('SPINE_CREATOR_SOURCE_TIMESCALE',sid,'Source timeScale evidence is missing')
            creator_scale=row.get('creator',{}).get('fields',{}).get('timeScale',{}).get('creator',{})
            if creator_scale.get('status')!=source_scale.get('status') or creator_scale.get('value')!=source_scale.get('value'):
                fail('SPINE_CREATOR_SOURCE_TIMESCALE',sid,'Frozen source timeScale differs from creator field evidence')
    if len(seen)!=record['sourceComponentCount']:fail('SPINE_COMPONENT_COUNT','spine','Component denominator differs')
    for row in record['copies']:
        if row['target']!='creator':continue
        if not row['path'].startswith('assets/resources/Spine/') or files.get(row['path'],{}).get('sha256')!=row['sha256']:
            fail('SPINE_RESOURCE_IDENTITY',row['path'],'Resource is not owned by the pinned closure')
        raw=read(inside(root,row['path']))
        if sha(raw)!=row['sha256'] or len(raw)!=row['bytes']:fail('SPINE_RESOURCE_CHANGED',row['path'],'Source closure bytes differ')
    return dict(record=record,root=root,receiptSha256=expected_sha)


def prepare(binding,output):
    if not binding:return None
    record=binding['record'];copies=[]
    for row in record['copies']:
        if row['target']!='creator':continue
        source='spine-payloads/'+sha(row['path'].encode())+Path(row['path']).suffix
        raw=read(inside(binding['root'],row['path']));dest=inside(output,source);dest.parent.mkdir(exist_ok=True);dest.write_bytes(raw)
        copies.append(dict(source=source,target=row['path'],sha256=row['sha256']))
    return dict(components=record['components'],assets=record['assets'],copies=copies,
                creatorMaterialProfile=record.get('creatorMaterialProfile'),
                emissionReceiptSha256=binding['receiptSha256'],sourceComponentCount=record['sourceComponentCount'])


def emit(binding,plan_root,output):
    if not binding:return
    for row in binding['copies']:
        raw=read(inside(plan_root,row['source']))
        if sha(raw)!=row['sha256']:fail('SPINE_RESOURCE_CHANGED',row['source'],'Plan-owned bytes differ')
        dest=inside(output,row['target'])
        if dest.exists():fail('SPINE_RESOURCE_COLLISION',row['target'],'Refuse to replace an existing asset')
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)


def verify(components,rows,owner):
    from .io import diagnostic
    expected={c['sourceId'] for c in components if c.get('convertible') and c.get('spineBinding')}
    if not expected and rows in (None,[]):return []
    if not isinstance(rows,list) or any(not isinstance(row,dict)for row in rows):
        return [diagnostic('SPINE_NATIVE_READBACK_MISSING',owner,'Source component readback absent')]
    actual={r.get('sourceComponentId'):r for r in rows}
    if len(actual)!=len(rows) or set(actual)!=expected:
        return [diagnostic('SPINE_NATIVE_IDENTITY_MISMATCH',owner,'Source component denominator differs')]
    gaps=[]
    expected_specs={c['sourceId']:c.get('spineBinding',{}) for c in components}
    for sid,row in actual.items():
        status=row.get('status')
        failures=row.get('failures')
        spec=expected_specs[sid]
        checks=row.get('checks')or{}
        unbound_checks=('sourceNodeActiveMatchesPlan','sourceTimeScaleRetainedInPinnedSpec','nativeTimeScaleFrozenAtT0',
            'nativeRendererEnabled','exactBuiltinMaterialContract','usesDefaultBuiltinMaterialRoute','skinFieldMatchesSource',
            'animationFieldMatchesSource','loopFieldMatchesSource','premultipliedAlphaFieldMatchesSource','tintFieldMatchesSource',
            'debugSlotsFieldMatchesSource','debugBonesFieldMatchesSource','debugMeshFieldMatchesSource','enableBatchFieldMatchesSource','cachingFieldMatchesSource')
        if (status=='incomplete_dynamic_assignment' and failures==[] and spec.get('sourceDataAssetId') is None
            and spec.get('runtimeDynamicAssignment',{}).get('status')=='source_static_uuid_absent_runtime_assignment_unverified'
            and spec.get('runtimeDynamicAssignment',{}).get('targetDefaultAssetFallback') is False
            and row.get('staticDataBoundBySource') is False and row.get('runtimeDataAvailable') is False
            and row.get('observedDataWithoutStaticSourceReference') is False
            and row.get('actual',{}).get('skeletonDataUuid') is None and bool(row.get('actual',{}).get('nativeComponentUuid'))
            and all(checks.get(key)is True for key in unbound_checks)):
            gaps.append(diagnostic('SPINE_SOURCE_UNBOUND_DYNAMIC_NOT_RUN',sid,
                'Source SkeletonData is absent; saved native null reference and mapped static fields verified. Runtime data assignment is not run.',sid))
            continue
        if status=='verified_source_inactive_runtime_uninitialized' and not failures:
            # Source node/hierarchy is inactive by the exact target-plan tree.
            # Serialized SkeletonData, requested names/default fields and native
            # references are verified; no visible runtime pose is expected until
            # the source hierarchy becomes active.
            continue
        if status=='incomplete_active_source_runtime_pose_uninitialized' and not failures:
            gaps.append(diagnostic('SPINE_NATIVE_STATIC_POSE_NOT_INITIALIZED',sid,
                'Source hierarchy is active and serialized SkeletonData/requested animation/skin identity is verified, but the saved-asset readback did not initialize a runtime Skeleton pose',sid))
            continue
        if status=='incomplete_source_activity_unknown_runtime_uninitialized' and not failures:
            gaps.append(diagnostic('SPINE_NATIVE_COMPONENT_INCOMPLETE',sid,
                'Runtime Skeleton state is uninitialized and source hierarchy activity is not proven',sid))
            continue
        if status!='verified' or failures:
            gaps.append(diagnostic('SPINE_NATIVE_COMPONENT_INCOMPLETE',sid,str(row.get('status'))+': '+str(row.get('failures',[])),sid))
    return gaps
