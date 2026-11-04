"""Conservative, offline proof for a native horizontal tiled progress control."""
import math


def configure_progress(components, nodes):
    """Annotate static field bindings, then select the legacy horizontal fill subset.

    The static binding is a disabled native carrier contract. It retains the
    authored scalar fields and the actual mapped Sprite component reference; it
    makes no claim that a target ProgressBar reproduces source geometry.
    """
    from ..io import diagnostic
    by_id={row['sourceId']:row for row in components}
    bars={}
    owners={}
    for row in components:
        if row['type']=='cc.ProgressBar':
            bars.setdefault(row.get('barSprite'),[]).append(row)
            owners.setdefault(row['node'],[]).append(row)
    gaps=[]
    for row in components:
        if row['type']!='cc.ProgressBar':continue
        # Preserve all explicit source fields in a typed, disabled carrier even
        # where the visual horizontal-fill adapter below cannot safely run.
        # Cocos 3.8.8's enum values are HORIZONTAL=0, VERTICAL=1, FILLED=2.
        bar=by_id.get(row.get('barSprite'),{})
        value,length,mode,reverse=(row.get('progress'),row.get('totalLength'),
                                   row.get('progressMode'),row.get('progressReverse'))
        finite=lambda v:type(v) in (int,float) and math.isfinite(v)
        if (isinstance(row.get('sourceId'),str) and row['sourceId'] and
            isinstance(row.get('node'),str) and row['node'] and
            isinstance(row.get('enabled'),bool) and
            bar.get('type')=='cc.Sprite' and bar.get('convertible') is True and
            isinstance(bar.get('sourceId'),str) and bar['sourceId'] and
            finite(value) and finite(length) and
            type(mode) is int and mode in (0,1,2) and type(reverse) is bool):
            row['staticProgressBinding']={
                'policy':'native-static-progress-v1',
                'sourceComponentId':row['sourceId'],
                'sourceNodeId':row['node'],
                'barSpriteSourceId':bar['sourceId'],
                'progress':float(value),
                'totalLength':float(length),
                'mode':mode,
                'reverse':reverse,
                'sourceEnabled':row['enabled'],
                'carrierEnabled':False,
            }
            bar_node=bar.get('node');geometry=nodes.get(bar_node,{})
            size=geometry.get('size');anchor=geometry.get('anchor')
            axis=0 if mode==0 else 1 if mode==1 else None
            geometry_match=(axis is not None and isinstance(size,list) and len(size)==2 and
                            finite(size[axis]) and abs(size[axis]-float(length)*float(value))<=.001)
            row['staticProgressBinding'].update(
                barNodeSourceId=bar_node,
                sourceBarSize=list(size) if isinstance(size,list) and len(size)==2 else None,
                sourceBarAnchor=list(anchor) if isinstance(anchor,list) and len(anchor)==2 else None,
                displayGeometryEvidence=(
                    'source-bar-axis-matches-progress' if geometry_match else
                    'filled-mode-needs-source-fill-state' if mode==2 else
                    'source-bar-axis-does-not-match-progress'))
        reason=None
        node=nodes.get(row['node'],{})
        fill=nodes.get(bar.get('node'),{})
        value,length=row.get('progress'),row.get('totalLength')
        numeric=lambda v:type(v) in (int,float) and math.isfinite(v)
        if not row.get('convertible'):
            reason='Source component or material is outside the native subset'
        elif not numeric(value) or not numeric(length) or not 0<=value<=1 or length<=0:
            reason='Explicit finite progress in [0,1] and positive total length required'
        elif (row.get('progressMode') is not None and (type(row['progressMode']) is not int or row['progressMode']!=0)) or row.get('progressReverse') not in (None,False) or (row.get('progressReverse') is not None and type(row['progressReverse']) is not bool):
            reason='Only horizontal forward progress is supported'
        elif (row.get('progressMode') is None or row.get('progressReverse') is None) and not 0<value<1:
            reason='An endpoint cannot establish omitted direction from source geometry'
        elif bar.get('type')!='cc.Sprite' or not bar.get('convertible') or bar.get('mode')!=2 or not bar.get('spriteFrame'):
            reason='An imported source Tiled Sprite is required'
        elif len(bars.get(row.get('barSprite'),[]))!=1 or len(owners.get(row['node'],[]))!=1:
            reason='Multiple progress controls share a node or fill'
        elif fill.get('parent')!=row['node'] or bar.get('node') not in node.get('children',[]):
            reason='Fill must be an existing direct child of the progress node'
        elif fill.get('anchor',[None])[0]!=0 or fill.get('scale')!=[1,1,1] or fill.get('rotation')!=[0,0,0,1]:
            reason='A left-pivot, unrotated, unit-scale source fill is required'
        elif (not all(numeric(v) for v in fill.get('size',[])) or len(fill.get('size',[]))!=2 or
              fill['size'][1]<=0 or abs(fill['size'][0]-length*value)>.001):
            reason='Source fill width must agree with total length times progress'
        elif any(c.get('enabled',True) and (c['node']==bar.get('node') and c['type'] in ('cc.Widget','cc.Animation') or
                     c['node']==row['node'] and c['type'] in ('cc.Layout','cc.Button','cc.Animation')) for c in components):
            reason='Another source controller may drive geometry or the Selectable'
        if reason:
            row['convertible']=False
            gaps.append(diagnostic('PROGRESS_SUBSET_HANDOFF',row['sourceId'],reason,row['sourceId']))
            continue
        row.update(barNode=bar['node'],presentationPolicy='native-horizontal-tiled-progress-v1',
                   directionEvidence='explicit-source-direction' if row.get('progressMode') is not None and row.get('progressReverse') is not None else 'source-left-pivot-and-intermediate-width')
    return gaps
