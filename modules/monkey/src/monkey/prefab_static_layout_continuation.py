"""Activate source-backed native Layout/Widget slots in an immutable UI plan."""
from __future__ import annotations
import copy
import math
from pathlib import Path
from . import io
from .prefab_static_layout_completion import prepare as prepare_layout,_component_origins

CONTRACT='monkey-static-layout-continuation/1'
_ENGINE={
 'cocos2d/core/components/CCComponent.js':'69c5e561c9d42aea846b96fcc7e741411be0236dd10eb5ec8103610758350222',
 'cocos2d/core/components/CCLayout.js':'608e317aeeee5c36fdc9f56f3c0e1d93fda73e868ba81ad4e6486aba6acfee40',
 'cocos2d/core/components/CCWidget.js':'da8f324673e521bd8fcf9f98edf971e318c2428bf1ea33e97e4d8279b2a76d96',
 'cocos2d/core/base-ui/CCWidgetManager.js':'55f66d2f34dc81d97522fbf0ccbab2d6df00f0aa951af6951f55182577aad979',
}

class StaticLayoutContinuationError(ValueError):pass

def _defaults_proven(slot):
    raw=slot['sourceSerializedFields'];values=slot['fieldValues']
    if slot['sourceEnabled']is not raw.get('_enabled',True):return False
    if slot['sourceType']=='cc.Layout':
        expected={'layoutType':raw.get('_N$layoutType',0),'resize':raw.get('_resize',0),
            'padding':[raw.get('_N$padding'+edge,0)for edge in ('Left','Bottom','Right','Top')],
            'spacingXY':[raw.get('_N$spacing'+axis,0)for axis in ('X','Y')],
            'startAxis':raw.get('_N$startAxis',0),'horizontalDirection':raw.get('_N$horizontalDirection',0),
            'verticalDirection':raw.get('_N$verticalDirection',1),
            'affectedByScale':raw.get('_N$affectedByScale',raw.get('_affectedByScale',False))}
        if '_N$cellSize'not in raw:expected['cellSize']=[40,40]
    else:
        expected={'alignFlags':raw.get('_alignFlags',0),'alignMode':raw.get('_alignMode',1),
            'margins':[raw.get('_'+edge,0)for edge in ('left','bottom','right','top')],
            'absolute':[raw.get('_isAbs'+edge,True)for edge in ('Left','Bottom','Right','Top')],
            'center':[raw.get('_horizontalCenter',0),raw.get('_verticalCenter',0)],
            'centerAbsolute':[raw.get('_isAbsHorizontalCenter',True),raw.get('_isAbsVerticalCenter',True)]}
    return all(values.get(k)==v for k,v in expected.items())

def _engine_evidence(evidence):
    if not isinstance(evidence,dict)or evidence.get('sourceVersion')!='2.4.15':
        raise StaticLayoutContinuationError('LAYOUT_ENGINE_VERSION_UNPROVEN')
    rows=evidence.get('files',[])
    by={row.get('logicalPath'):row for row in rows if isinstance(row,dict)}
    if len(by)!=len(rows):raise StaticLayoutContinuationError('LAYOUT_ENGINE_FILE_IDENTITY_AMBIGUOUS')
    result=[]
    for logical,expected in _ENGINE.items():
        row=by.get(logical,{})
        if row.get('sha256')!=expected or not Path(row.get('path','')).is_absolute():
            raise StaticLayoutContinuationError('LAYOUT_ENGINE_SOURCE_PIN_INVALID:'+logical)
        raw=io.read(io.safe(row['path']),max_bytes=2*1024**2)
        if io.sha(raw)!=expected:raise StaticLayoutContinuationError('LAYOUT_ENGINE_SOURCE_CHANGED:'+logical)
        result.append(dict(logicalPath=logical,sha256=expected,bytes=len(raw),originUrl=row.get('originUrl')))
    return result

def _context(slot,nodes):
    owner=nodes[slot['sourceNodeId']]
    target=slot.get('targetSourceNodeId')or owner.get('parent')
    if not isinstance(target,str)or target not in nodes:
        return 'WIDGET_TARGET_CONTEXT_MISSING'
    cursor=owner.get('parent');seen=set()
    while cursor!=target:
        if cursor not in nodes or cursor in seen:return 'WIDGET_TARGET_NOT_ANCESTOR'
        seen.add(cursor)
        node=nodes[cursor];scale=node.get('scale')
        if (not isinstance(scale,list)or len(scale)<2 or
                any(type(v)not in(int,float)or not math.isfinite(v)or v==0 for v in scale[:2])):
            return 'WIDGET_ANCESTOR_XY_SCALE_UNPROVEN'
        cursor=node.get('parent')
    return None

def prepare(plan,ir,manifest,stage_root,*,source_evidence=None):
    selected=[c for c in plan.get('components',[])if c.get('type')in('cc.Layout','cc.Widget')and c.get('convertible')is False]
    if not selected:return {'plan':copy.deepcopy(plan),'summary':{'selectedComponents':0,'preparedComponents':0,'native':'not_run'}}
    if manifest.get('sourceVersion')!='2.4.15':raise StaticLayoutContinuationError('LAYOUT_SOURCE_VERSION_UNSUPPORTED')
    origins=_component_origins(plan)
    ir_rows={}
    for c in ir.get('components',[]):ir_rows.setdefault(c.get('sourceId'),[]).append(c)
    for c in selected:
        origin=c['sourceId'];seen=set()
        while origin in origins:
            if origin in seen or len(set(origins[origin]))!=1:
                raise StaticLayoutContinuationError('LAYOUT_SOURCE_IDENTITY_AMBIGUOUS:'+c['sourceId'])
            seen.add(origin);origin=origins[origin][0]
        candidates=ir_rows.get(origin,[])
        if len(candidates)!=1 or candidates[0].get('type')!=c['type']:
            raise StaticLayoutContinuationError('LAYOUT_PLAN_IR_IDENTITY_MISMATCH:'+c['sourceId'])
    evidence=_engine_evidence(source_evidence)
    contract=prepare_layout(dict(plan,components=selected),manifest)
    nodes={n['sourceId']:n for n in plan['nodes']};adopted=[];gaps=[]
    for spec in contract['nodes']:
        reason=None
        if spec['status']!='native_algorithm_supported':reason='LAYOUT_SOURCE_FIELDS_NOT_PROVEN'
        if spec['layouts']and spec['widgets']:reason='LAYOUT_WIDGET_PHASE_ORDER_UNPROVEN'
        if any(not _defaults_proven(slot)for slot in spec['layouts']+spec['widgets']):
            reason='LAYOUT_SOURCE_VERSION_DEFAULT_MISMATCH'
        for slot in spec['widgets']:
            reason=reason or _context(slot,nodes)
        if reason:
            for slot in spec['layouts']+spec['widgets']:
                gaps.append(dict(code=reason,sourceComponentId=slot['sourceComponentId'],
                    unknownSourceFields=slot.get('unknownSourceFields',[])))
        else:adopted.append(spec)
    contract=dict(contract,nodes=adopted,status='native_algorithm_supported'if not gaps else'partial')
    # These source IDs map to explicit, independently read-back slots of one
    # native RectTransform actuator, not fabricated extra LayoutGroups.
    ids={slot['sourceComponentId']for spec in adopted for slot in spec['layouts']+spec['widgets']}
    patched=copy.deepcopy(plan)
    for c in patched['components']:
        if c['sourceId']in ids:
            c['nativeType']='NativeStaticLayoutCompletion'
            c['nativeSlotId']=c['sourceId']
            c['staticLayoutContinuationBinding']={'contract':CONTRACT,'sourceComponentId':c['sourceId'],
                'sourceNodeId':c['node'],'physicalNativeType':'NativeStaticLayoutCompletion'}
    if plan.get('layoutCompletion'):
        prior=copy.deepcopy(plan['layoutCompletion'])
        previous={n['sourceNodeId']for n in prior.get('nodes',[])}
        if previous & {n['sourceNodeId']for n in adopted}:
            raise StaticLayoutContinuationError('LAYOUT_CONTINUATION_WOULD_OVERWRITE_EXISTING_NODE')
        contract=dict(prior,nodes=prior.get('nodes',[])+adopted)
    patched['layoutCompletion']=contract
    metadata={'contract':CONTRACT,'schemaVersion':1,'sourceManifestSha256':plan['sourceManifestSha256'],
        'engineEvidence':evidence,'componentIds':sorted(ids),'gaps':gaps,
        'sourceComponentCount':len(plan['components']),'sourceBusinessExecuted':False,
        'native':'not_run','visual':'not_run','initialPoseUsedAsAlgorithmProof':False}
    metadata['absentSerializedPropertyPolicy']='pinned-2.4.15-component-layout-widget-declarations; unknown-context-is-not-defaulted'
    patched['staticLayoutContinuation']=metadata
    module=io.inside(Path(stage_root),'layout_static_continuation');module.mkdir(exist_ok=False)
    io.write_json(module/'contract.json',dict(metadata,layoutCompletion=contract))
    return {'plan':patched,'summary':{'selectedComponents':len(selected),'preparedComponents':len(ids),
        'nativeNodeCount':len(adopted),'gapCount':len(gaps),'native':'not_run'}}
