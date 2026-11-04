"""Join independently verified saved renderers with retained source carriers."""
import copy
from pathlib import Path

from .prefab_component_coverage import _unity_persistent_identity
from .io import inside,read,sha,load


def _retained_spine_carrier(row):
    if not isinstance(row,dict):return False
    signature=(row.get('nativeType')=='NativeStaticSpineReference' and
               row.get('representation')=='disabled-source-data-carrier' and row.get('status')=='retained')
    if row.get('coverageRole')=='retained-carrier' and not signature:
        raise ValueError('SPINE_RENDERING_ROLE_MISMATCH')
    if row.get('nativeType')=='NativeStaticSpineReference' and not signature:
        raise ValueError('SPINE_RENDERING_ROLE_MISMATCH')
    return signature


def load_bound_receipt(candidate,readback):
    """Bind auxiliary receipt bytes to the main, externally pinned readback."""
    root=Path(candidate)
    paths=['Analysis/Readback/spine-static-continuation.json']
    rendering=root/'Analysis/Readback/SpineRendering'
    paths.extend(path.relative_to(root).as_posix() for path in sorted(rendering.glob('*.json'))if path.name!='prepare.json')
    if len(paths)==1:raise ValueError('SPINE_RENDERING_SAVED_RECEIPT_MISSING')
    records=readback.get('staticSpineReadbackFiles')
    if (not isinstance(records,list)or any(not isinstance(row,dict)for row in records)
            or len({row.get('path')for row in records})!=len(records)
            or {row.get('path')for row in records}!=set(paths)):
        raise ValueError('SPINE_RENDERING_RECEIPT_BINDING_INVALID')
    pins={row['path']:row.get('sha256')for row in records};components=[]
    for relative in paths:
        path=inside(root,relative)
        if path.is_symlink():raise ValueError('SPINE_RENDERING_RECEIPT_LINK_INVALID')
        raw=read(path,max_bytes=32*1024*1024)
        if sha(raw)!=pins[relative]:raise ValueError('SPINE_RENDERING_RECEIPT_BYTES_CHANGED')
        if relative not in ('Analysis/Readback/spine-static-continuation.json',
                            'Analysis/Readback/SpineRendering/source-canvas-context.json',
                            'Analysis/Readback/SpineRendering/owner-context-lifecycle.json'):
            components.extend(load(raw)['components'])
    return {'components':components}


def merge(readback, rendering, receipt):
    """Called only after the rendering module checks bytes and saved receipts."""
    result=copy.deepcopy(readback)
    expected={row['sourceComponentId']:row for row in rendering['components']}
    if len(expected)!=len(rendering['components']):raise ValueError('SPINE_RENDERING_SOURCE_ID_DUPLICATE')
    rows=receipt.get('components')
    if (not isinstance(rows,list)or any(not isinstance(row,dict)for row in rows)
            or len(rows)!=len(expected)or {row.get('sourceComponentId')for row in rows}!=set(expected)):
        raise ValueError('SPINE_RENDERING_COVERAGE_DENOMINATOR_INVALID')
    source_ids=[]
    presentation=result.get('staticPresentationValidation')or{}
    if not isinstance(presentation,dict):raise ValueError('SPINE_RENDERING_PRESENTATION_CONTRACT_INVALID')
    presentations={row['sourceId']:row for row in presentation.get('components',[])if isinstance(row,dict)and row.get('sourceId')}
    for row in rows:
        sid=row['sourceComponentId'];source=expected[sid]
        if source.get('eligible')is not True:
            if row.get('rendererCreated')is True:raise ValueError('SPINE_RENDERING_INELIGIBLE_RENDERER')
            continue
        identity=_unity_persistent_identity({'guid':row.get('rendererGuid'),'localFileId':row.get('rendererLocalId')})
        data_identity=_unity_persistent_identity({'guid':row.get('dataAssetGuid'),'localFileId':row.get('dataAssetLocalId')})
        flags=('verified','rendererCreated','persistent','dataPersistent','serializedFieldsVerified',
               'poseVerified','colorVerified','materialReferencesVerified','unitMappingVerified','sourceVisibleVerified')
        visible=source.get('sourceVisible')is True
        if (identity is None or data_identity is None or any(row.get(flag)is not True for flag in flags)
                or row.get('sourceCodeExecuted')is not False
                or row.get('sourceDataAssetId')!=source.get('sourceDataAssetId')
                or row.get('sourceVisible')is not visible
                or type(row.get('rendererEnabled'))is not bool
                or row['rendererEnabled']is not source.get('sourceComponentEnabled')
                or visible and (type(row.get('meshVertexCount'))is not int or row['meshVertexCount']<=0
                                or type(row.get('meshTriangleCount'))is not int or row['meshTriangleCount']<=0)):
            raise ValueError('SPINE_RENDERING_COVERAGE_EVIDENCE_INVALID: '+sid)
        enabled=row['rendererEnabled']
        native=dict(sourceId=sid,node=source['sourceNodeId'],type='sp.Skeleton',nativeType='Spine.Unity.SkeletonGraphic',
                    componentUuid=identity['guid']+':'+str(identity['localFileId']),**identity,
                    coverageRole='native-renderer',
                    sourceIdentityVerified=True,persistent=True,sourceEnabled=source['sourceComponentEnabled'],
                    nativeEnabled=enabled,sourceVisible=visible,nativeStaticFieldsVerified=True,
                    representation='native-component',status='native'if enabled else'disabled',
                    disabledReason=None if enabled else'source-disabled',
                    renderingEvidence='saved-prefab-reopen-spine-static-rendering')
        collection='components'if enabled else'disabledComponents'
        peer_rows=[existing for key in ('components','disabledComponents')
                   for existing in result.get(key,[]) if isinstance(existing,dict) and existing.get('sourceId')==sid]
        renderer_rows=[existing for existing in peer_rows if not _retained_spine_carrier(existing)]
        if renderer_rows:
            raise ValueError('SPINE_RENDERING_NATIVE_COUNTERPART_AMBIGUOUS: '+sid)
        for existing in peer_rows:
            if _retained_spine_carrier(existing):
                existing.setdefault('coverageRole','retained-carrier')
        result.setdefault(collection,[]).append(native)
        # This supplements the carrier receipt rather than replacing it.
        source_ids.append(sid)
        presentations[sid]=dict(sourceId=sid,sourceVisible=visible,verified=True,rendered=visible,
                                reason='saved-native-renderer-and-source-time-zero-pose-verified')
    result['staticSpineRendering']=dict(status='verified',sourceComponentIds=source_ids)
    presentation.update(components=list(presentations.values()),
        status='pass'if presentations and all(row.get('verified')is True for row in presentations.values())else'partial')
    result['staticPresentationValidation']=presentation
    return result
