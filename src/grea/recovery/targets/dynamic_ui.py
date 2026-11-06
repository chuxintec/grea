"""Which native UI properties are driven, and strict save/reopen geometry proof.

Cached source rectangles remain evidence. Only dimensions/coordinates controlled
by an enabled, emitted native component may differ after its layout pass.
"""
import copy,math
from ..io import diagnostic

POLICY='native-ui-layout-roundtrip-v1'

def probe_sources(plan):
    selected={}
    for c in plan['components']:
        if not c.get('convertible')or not c.get('enabled'):continue
        typ=c['type']
        if typ=='cc.Label'and c.get('text'):key=typ+'/'+str(c['overflow']);priority=2
        elif typ=='cc.Widget':key=typ;priority=3
        elif typ=='cc.Layout'and c['layoutType']in(1,2,3):
            key=typ+'/'+str(c['layoutType'])+'/'+str(c['resize'])+'/'+str(bool(c.get('affectedByScale')));priority=0 if c['layoutType']==3 else 1 if c['resize']==2 else 4
        else:continue
        selected.setdefault(key,(priority,c['sourceId']))
    return [sid for _,sid in sorted(selected.values(),key=lambda x:x[0])[:8]]

def driven_fields(plan):
    nodes={n['sourceId']:n for n in plan['nodes']};result={}
    def allow(sid,key,axes):result.setdefault(sid,{}).setdefault(key,set()).update(axes)
    components=list(plan['components'])
    if plan.get('targetProfile')=='cocos-3.8.8':
        for owner in (plan.get('layoutCompletion')or{}).get('nodes',[]):
            for slot in owner.get('layouts',[]):
                if slot.get('status')=='native_algorithm_supported':
                    components.append(dict(slot,**{'type':'cc.Layout','node':owner['sourceNodeId'],'convertible':True,'enabled':slot['sourceEnabled']}))
            for slot in owner.get('widgets',[]):
                if slot.get('status')=='native_constraint_supported':
                    components.append(dict(slot,**{'type':'cc.Widget','node':owner['sourceNodeId'],'flags':slot['alignFlags'],'convertible':True,'enabled':slot['sourceEnabled']}))
    for c in components:
        if not c.get('convertible'):continue
        sid=c['node'];typ=c['type']
        if (typ=='cc.ScrollView' and plan.get('targetProfile')=='cocos-3.8.8' and
              c.get('content') in nodes):
            # Creator's ScrollView.content setter synchronously recalculates
            # bounds and repositions its content, even when the component is
            # disabled. The source-enabled axis flags still gate the move.
            axes=[]
            if c.get('horizontal') is True:axes.append(0)
            if c.get('vertical') is True:axes.append(1)
            if axes:allow(c['content'],'position',axes)
        if not c.get('enabled'):continue
        if typ=='cc.RichText' and plan.get('targetProfile')=='cocos-3.8.8':
            # Creator 2.4 and 3.8 RichText recompute the owning node's size:
            # width is intrinsic when maxWidth is zero (otherwise maxWidth),
            # and height is line-count/lineHeight based. Keep both source
            # constraints intact while accepting only this native size output.
            allow(sid,'size',[0,1])
        elif typ=='cc.Label':
            if c['overflow']==0:allow(sid,'size',[0,1])
            elif c['overflow']==3:allow(sid,'size',[1])
        elif typ=='cc.Sprite'and c.get('spriteFrame')and c.get('sizeMode',0)!=0:allow(sid,'size',[0,1])
        elif (typ=='cc.ProgressBar' and plan.get('targetProfile')=='cocos-3.8.8' and
              c.get('presentationPolicy')=='native-horizontal-tiled-progress-v1' and c.get('barNode') in nodes):
            # Creator's native ProgressBar owns the horizontal bar position and
            # width after initialization. Keep this declaration target/profile
            # bound; Unity's Slider adapter drives the fill width differently.
            allow(c['barNode'],'position',[0]);allow(c['barNode'],'size',[0])
        elif typ=='cc.Widget':
            flags=c['flags']
            if flags&56:allow(sid,'position',[0])
            if flags&7:allow(sid,'position',[1])
            if flags&40==40:allow(sid,'size',[0])
            if flags&5==5:allow(sid,'size',[1])
        elif typ=='cc.Layout':
            axis=c['layoutType']-1
            if c['layoutType']in(1,2):
                if c['resize']==1:allow(sid,'size',[axis])
                for child in nodes[sid]['children']:
                    allow(child,'position',[0,1]if c.get('alignCross')else[axis])
                    if c['resize']==2:allow(child,'size',[axis])
            elif c['layoutType']==3:
                if c['resize']==1:allow(sid,'size',[1-c.get('startAxis',0)])
                for child in nodes[sid]['children']:
                    allow(child,'position',[0,1])
                    if c['resize']==2:allow(child,'size',[0,1])
    return result

def expectations(plan,rows,scope,nodes=None):
    source=nodes if nodes is not None else plan['nodes'];expected=copy.deepcopy(source);gaps=[]
    if plan.get('uiGeometryReadback')!=POLICY:return expected,gaps
    rows=rows if isinstance(rows,list)else[];actual={r.get('sourceId'):r for r in rows};ids={n['sourceId']for n in source}
    if len(actual)!=len(rows)or set(actual)!=ids:
        return expected,[diagnostic('DYNAMIC_UI_INITIAL_GEOMETRY_MISSING',scope,'Native pre-save geometry identity set differs')]
    driven=driven_fields(plan)
    for n in expected:
        row=actual[n['sourceId']]
        for key,axes in driven.get(n['sourceId'],{}).items():
            values=row.get(key)
            if not isinstance(values,list)or len(values)!=len(n[key])or any(type(v)not in(int,float)or not math.isfinite(v)for v in values):
                gaps.append(diagnostic('DYNAMIC_UI_INITIAL_GEOMETRY_INVALID',n['sourceId'],'Invalid native layout '+key));continue
            for i in axes:n[key][i]=values[i]
    return expected,gaps

def verify_probes(plan,rows):
    if plan.get('uiGeometryReadback')!=POLICY:return []
    selected={}
    for c in plan['components']:
        if not c.get('convertible')or not c.get('enabled'):continue
        typ=c['type']
        if not(typ=='cc.Label'and c.get('text')or typ=='cc.Widget'or typ=='cc.Layout'and c['layoutType']in(1,2)and c['resize']==1):continue
        selected.setdefault(typ+'/'+str(c['overflow'])if typ=='cc.Label'else typ,c)
    v2=plan.get('uiStateProbeVersion',0)>=2
    expected=([c for sid in probe_sources(plan)for c in plan['components']if c['sourceId']==sid]if v2 else list(selected.values())[:6]);rows=rows if isinstance(rows,list)else[];by_id={r.get('sourceId'):r for r in rows};gaps=[]
    if len(by_id)!=len(rows)or set(by_id)!={c['sourceId']for c in expected}:
        gaps.append(diagnostic('DYNAMIC_UI_PROBE_SET','native-ui','Native state change probe identity set differs'))
    for c in expected:
        row=by_id.get(c['sourceId'],{});states=row.get('states',[])
        actions={'baseline','text-change','show-original-text'}if c['type']=='cc.Label'else{'baseline','parent-resize','show-after-resize'}if c['type']=='cc.Widget'else{'baseline','add-child','hide-child','show-child','remove-child'}
        if v2 and c['type']=='cc.Layout':actions|={'container-resize','scale-child','resize-child','hide-show-container'}
        valid=row.get('type')==c['type']and row.get('status')=='native-state-changes-passed'and isinstance(states,list)and {s.get('action')for s in states}==actions and len(states)==len(actions)
        if valid:
            valid=all(isinstance(s.get(k),list)and len(s[k])==2 and all(type(v)in(int,float)and math.isfinite(v)for v in s[k])for s in states for k in('size','position'))
        if valid and v2 and c['type']=='cc.Layout':
            for state in states:
                children=state.get('children');valid=valid and isinstance(children,list)
                if not valid:break
                valid=valid and all(x.get('index')==i and type(x.get('active'))is bool and all(isinstance(x.get(k),list)and len(x[k])==2 and all(type(v)in(int,float)and math.isfinite(v)for v in x[k])for k in('size','position','scale'))for i,x in enumerate(children))
        if not valid:gaps.append(diagnostic('DYNAMIC_UI_STATE_CHANGE_NOT_VERIFIED',c['sourceId'],'Missing/invalid text, parent resize or child visibility/rebuild evidence'))
    return gaps
