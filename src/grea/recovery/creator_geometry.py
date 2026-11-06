"""Finite Creator 3.8.8 native tiled geometry and project-local buffer budget."""
import math

DEFAULT_KIB=144
VERTEX_BYTES=36
MAX_KIB=2303  # Integer KiB policy, safely below the native uint16 vertex limit.


def tiled_vertices(size,rect,border):
    if (len(size)!=2 or len(rect)!=2 or len(border)!=4 or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in (*size,*rect,*border))):
        raise ValueError('Invalid tiled geometry numbers')
    w,h=rect;l,t,r,b=border
    if min(w,h)<=0 or min(border)<0 or l+r>w or t+b>h:raise ValueError('Invalid tiled frame/insets')
    cw,ch=w-l-r,h-t-b;sx=max(0,abs(size[0])-l-r);sy=max(0,abs(size[1])-t-b)
    offset=2 if any(border) else 0
    cols=math.ceil((sx/cw if cw else sx)+offset);rows=math.ceil((sy/ch if ch else sy)+offset)
    return rows*cols*4


def renderer_budget(nodes,components,assets):
    by_node={n['sourceId']:n for n in nodes};by_asset={a['sourceId']:a for a in assets};entries=[];gaps=[]
    for c in components:
        if c['type']!='cc.Sprite' or c.get('mode')!=2 or not c.get('convertible') or not c.get('spriteFrame'):continue
        frame=by_asset.get(c['spriteFrame'])
        if frame is None:continue
        try:
            sizing=c.get('nativeSizeMode',c.get('sizeMode',0))
            size=frame['originalSize'] if sizing==2 else frame['size'] if sizing==1 else by_node[c['node']]['size']
            vertices=tiled_vertices(size,frame['size'],frame['border'])
            if math.ceil(vertices*VERTEX_BYTES/1024)>MAX_KIB:raise ValueError('Tiled mesh exceeds safe native uint16 buffer capacity')
        except ValueError as error:
            c['convertible']=False;gaps.append((c['sourceId'],str(error)));continue
        c['nativeTiledVertices']=vertices;entries.append(dict(sourceId=c['sourceId'],vertices=vertices))
    maximum=max((r['vertices'] for r in entries),default=0);kib=max(DEFAULT_KIB,math.ceil(maximum*VERTEX_BYTES/1024))
    return dict(profile='creator-3.8.8-tiled-buffer-v1',macroConfig={'BATCHER2D_MEM_INCREMENT':kib},
                vertexCapacity=kib*1024//VERTEX_BYTES,maxTiledVertices=maximum,tiledSprites=entries),gaps


def verify_tiled_readback(plan,readback):
    """Require native topology, buffer allocation and exact frame identity after layout."""
    budget=plan.get('rendererBudget')
    if not budget or not budget.get('tiledSprites'):return True
    proof=readback.get('tiledRenderer') or {};actual=proof.get('sprites',[])
    rows={r.get('sourceId'):r for r in actual};nodes={r['sourceId']:r for r in readback.get('nodes',[])}
    frames={a['sourceId']:a for a in plan['assets']};assets={a['sourceId']:a for a in readback.get('assets',[])}
    expected={c['sourceId']:c for c in plan['components'] if c.get('convertible') and c['type']=='cc.Sprite' and c.get('mode')==2 and c.get('spriteFrame')}
    if (proof.get('profile')!=budget['profile'] or type(proof.get('macroKiB')) is not int or
            proof['macroKiB']!=budget['macroConfig']['BATCHER2D_MEM_INCREMENT'] or len(rows)!=len(actual) or set(rows)!=set(expected)):return False
    for sid,c in expected.items():
        frame=frames[c['spriteFrame']];row=rows[sid];vertices=row.get('vertexCount');indices=row.get('indexCount')
        uuid=assets.get(c['spriteFrame'],{}).get('spriteFrameUuid')
        try:count=tiled_vertices(nodes[c['node']]['size'],frame['size'],frame['border'])
        except (KeyError,TypeError,ValueError):return False
        if (type(vertices) is not int or vertices!=count or not 0<=vertices<=budget['vertexCapacity'] or
                type(indices) is not int or indices!=vertices//4*6 or row.get('allocated') is not True or
                not uuid or row.get('spriteFrameUuid')!=uuid):return False
    return True
