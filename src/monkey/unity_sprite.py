"""Strict geometry descriptors for the verified Unity 2021.3 tight Sprite profile.

Only float32, planar position + unused UV streams, one uint16 triangle submesh,
and packed tight atlas UV transforms with axis reflections or a half turn are covered.
Reflections use the exact serialized atlas rect center. No hull or pixels are invented.
"""
import base64
import math
import struct

from .io import sha


def atlas_settings(raw):
    """Decode the verified serialized bit subset, rejecting reserved/unknown modes."""
    if type(raw)is not int or not 0<=raw<=127:raise ValueError('Unsupported Sprite settings bits')
    values=(raw&1,(raw>>1)&1,(raw>>2)&15,(raw>>6)&1)
    if values not in ((1,0,0,1),(1,1,0,1),(1,0,1,1),(1,0,2,1),(1,0,3,1)):
        raise ValueError('Unverified packed/mode/rotation/mesh-type combination: '+str(values))
    return dict(settingsRaw=raw,packed=bool(values[0]),packingMode='Tight'if values[1]==0 else'Rectangle',
                packingRotation=('None','FlipHorizontal','FlipVertical','Rotate180')[values[2]],meshType='Tight')


def tight_geometry(data,atlas,width,height):
    def check(ok,message):
        if not ok:raise ValueError(message)
    settings=atlas_settings(atlas.get('settingsRaw',65))
    check(settings['packingMode']=='Tight','Exact tight packing required')
    rd=data['m_RD'];vd=rd['m_VertexData'];n=vd['m_VertexCount'];channels=vd['m_Channels']
    check(type(n) is int and 3<=n<=10000,'Unsupported tight vertex count')
    active={i:c for i,c in enumerate(channels) if c['dimension']}
    check(active=={0:dict(stream=0,offset=0,format=0,dimension=3),4:dict(stream=1,offset=0,format=0,dimension=2)},'Unsupported tight vertex channels')
    encoded=vd['m_DataSize'];check(encoded.get('$type')=='bytes','Inline exact vertex bytes required')
    raw=base64.b64decode(encoded['base64'],validate=True)
    uv_start=(n*12+15)//16*16
    check(len(raw)==uv_start+n*8 and len(raw)==encoded['bytes'] and sha(raw)==encoded['sha256'],'Tight vertex bytes/hash differ')
    check(not any(raw[n*12:]),'Nonzero stored UV/padding requires another profile')
    vertices=list(struct.iter_unpack('<fff',raw[:n*12]))
    check(all(math.isfinite(v) for row in vertices for v in row) and all(row[2]==0 for row in vertices),'Nonplanar or invalid tight geometry')
    indices=rd['m_IndexBuffer'];check(isinstance(indices,list) and all(type(v) is int and 0<=v<=255 for v in indices),'Inline exact index bytes required')
    check(0<len(indices)<=60000 and len(indices)%6==0,'Invalid tight triangle bytes')
    triangles=list(struct.unpack('<'+'H'*(len(indices)//2),bytes(indices)))
    check(all(i<n for i in triangles),'Tight triangle index outside vertex range')
    meshes=rd['m_SubMeshes']
    check(len(meshes)==1 and all(meshes[0].get(k)==v for k,v in dict(firstByte=0,indexCount=len(triangles),topology=0,baseVertex=0,firstVertex=0,vertexCount=n).items()),'Unsupported tight submesh layout')
    uv=atlas['uvTransform'];values=[uv[k] for k in ('x','y','z','w')]
    check(all(type(v) in (int,float) and math.isfinite(v) for v in (*values,width,height)) and width>0 and height>0,'Invalid tight atlas UV transform')
    coords=[dict(x=(x*uv['x']+uv['y'])/width,y=(y*uv['z']+uv['w'])/height) for x,y,_ in vertices]
    if settings['packingRotation']!='None':
        rect=atlas['textureRect']
        check(set(rect)=={'x','y','width','height'} and all(type(v)in(int,float)and math.isfinite(v)for v in rect.values())and rect['width']>0 and rect['height']>0,'Exact finite packed rect required for atlas rotation')
        for row in coords:
            if settings['packingRotation']in('FlipHorizontal','Rotate180'):row['x']=(2*rect['x']+rect['width'])/width-row['x']
            if settings['packingRotation']in('FlipVertical','Rotate180'):row['y']=(2*rect['y']+rect['height'])/height-row['y']
    check(all(math.isfinite(v) and abs(v)<=1 for row in coords for v in row.values()),'Unbounded or nonfinite tight atlas UV')
    return dict(meshVertices=[dict(x=x,y=y) for x,y,_ in vertices],triangleIndices=triangles,meshUv=coords,verifyMesh=True)
