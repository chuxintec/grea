"""Strict geometry descriptors for the verified Unity 2021.3 tight Sprite profile.

Only float32, planar position + unused UV streams, one uint16 triangle submesh,
and packed tight atlas UV transforms with axis reflections or a half turn are covered.
Reflections use the exact serialized atlas rect center. No hull or pixels are invented.
"""
import base64
import math
import struct

from .io import sha, encoded


def atlas_settings(raw):
    """Decode the verified serialized bit subset, rejecting reserved/unknown modes."""
    if type(raw)is not int or not 0<=raw<=127:raise ValueError('Unsupported Sprite settings bits')
    values=(raw&1,(raw>>1)&1,(raw>>2)&15,(raw>>6)&1)
    if values not in ((1,0,0,1),(1,1,0,1),(1,0,1,1),(1,0,2,1),(1,0,3,1)):
        raise ValueError('Unverified packed/mode/rotation/mesh-type combination: '+str(values))
    return dict(settingsRaw=raw,packed=bool(values[0]),packingMode='Tight'if values[1]==0 else'Rectangle',
                packingRotation=('None','FlipHorizontal','FlipVertical','Rotate180')[values[2]],meshType='Tight')


def _tight_mesh(data):
    def check(ok,message):
        if not ok:raise ValueError(message)
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
    return vertices,triangles


def tight_geometry(data,atlas,width,height):
    def check(ok,message):
        if not ok:raise ValueError(message)
    settings=atlas_settings(atlas.get('settingsRaw',65))
    check(settings['packingMode']=='Tight','Exact tight packing required')
    vertices,triangles=_tight_mesh(data)
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


def unpacked_tight_geometry(data,width,height,pixels_to_units,settings_raw=64,*,pixel_sha256):
    """Separate full-texture, unpacked-tight profile; packed atlas rules stay strict.

    Pixel bytes are verified by the outer hydration layer. This descriptor pins
    that layer's hash together with the exact source Sprite data and geometry.
    It does not assert an existing target GUID or builtin resource identity.
    """
    import re
    def check(ok,message):
        if not ok:raise ValueError(message)
    check(type(width)is int and type(height)is int and 0<width*height<=16*1024*1024
          and width>0 and height>0,'Exact bounded texture dimensions required')
    check(type(pixels_to_units)in(int,float) and math.isfinite(pixels_to_units)
          and pixels_to_units>0 and data.get('m_PixelsToUnits')==pixels_to_units,'Source pixels-to-units differs')
    check(type(settings_raw)is int and settings_raw==64 and data['m_RD'].get('settingsRaw')==64,
          'Only separate unpacked-tight settingsRaw 64 is proven')
    check(isinstance(pixel_sha256,str) and re.fullmatch('[0-9a-f]{64}',pixel_sha256) is not None,
          'Exact hydrated RGBA SHA256 required')
    rd=data['m_RD']
    check(rd.get('alphaTexture',{}).get('fileId')=='0' and rd.get('alphaTexture',{}).get('pathId')=='0'
          and not rd.get('secondaryTextures') and not rd.get('m_Bindpose') and rd.get('downscaleMultiplier')==1,
          'Separate alpha/secondary/skinned/downscaled Sprite requires another profile')
    check(data.get('m_SpriteAtlas',{}).get('pathId')=='0' and not data.get('m_AtlasTags'),
          'Unpacked source Sprite must not reference an atlas')
    rect=data['m_Rect'];pivot=data['m_Pivot'];border=data['m_Border']
    check(rect==dict(x=0,y=0,width=width,height=height),'Only exact full-texture source rect is proven')
    check(set(pivot)=={'x','y'} and all(type(v)in(int,float) and math.isfinite(v) and 0<=v<=1 for v in pivot.values()),
          'Finite normalized source pivot required')
    check(set(border)=={'x','y','z','w'} and all(type(v)in(int,float) and math.isfinite(v) and v>=0 for v in border.values())
          and border['x']+border['z']<=width and border['y']+border['w']<=height,'Finite bounded source border required')
    check(type(data.get('m_Extrude'))is int and 0<=data['m_Extrude']<=64 and data.get('m_IsPolygon')is False,
          'Source extrusion/polygon profile is unsupported')
    for name in ('m_Bones','m_Skin'):
        check(not data.get(name),'Skinned Sprite requires another profile')
    uv=data['m_RD']['uvTransform'];expected=dict(x=pixels_to_units,y=width*pivot['x'],z=pixels_to_units,w=height*pivot['y'])
    check(uv==expected,'Unpacked source UV transform differs from rect/pivot/PPU')
    vertices,triangles=_tight_mesh(data)
    coords=[dict(x=(x*uv['x']+uv['y'])/width,y=(y*uv['z']+uv['w'])/height) for x,y,_ in vertices]
    check(all(math.isfinite(v) and 0<=v<=1 for row in coords for v in row.values()),'Unpacked source UV exceeds texture bounds')
    descriptor=dict(geometryProfile='unity-2021.3-unpacked-tight-v1',sourceSpriteDataSha256=sha(encoded(data)),
        textureRgbaRawSha256=pixel_sha256,textureWidth=width,textureHeight=height,pixelsToUnits=pixels_to_units,
        meshVertices=[dict(x=x,y=y) for x,y,_ in vertices],triangleIndices=triangles,meshUv=coords,verifyMesh=True)
    descriptor['geometrySha256']=sha(encoded(descriptor))
    return descriptor


def rectangle_atlas_geometry(data,atlas,width,height):
    """Source-proven unrotated rectangle atlas region, without trimmed offsets.

    Native standalone Sprite.rect uses the atlas region rather than the source
    local zero-origin rect. Sizes, pivot, source unit vertices and UVs are proven
    explicitly; the source packed flag is not asserted native-equivalent.
    """
    def check(ok,message):
        if not ok:raise ValueError(message)
    settings=atlas_settings(atlas['settingsRaw'])
    check(settings['packingMode']=='Rectangle' and settings['packingRotation']=='None',
          'Only unrotated rectangle atlas regions are supported')
    check(type(width)is int and type(height)is int and width>0 and height>0 and width*height<=16*1024*1024,
          'Exact bounded atlas dimensions required')
    check(atlas.get('downscaleMultiplier')==1 and atlas.get('alphaTexture',{}).get('pathId')=='0'
          and not atlas.get('secondaryTextures'),'Separate alpha/secondary/downscaled atlas requires another profile')
    rect=atlas['textureRect'];local=data['m_Rect'];pivot=data['m_Pivot'];ppu=data['m_PixelsToUnits']
    check(set(rect)=={'x','y','width','height'} and all(type(v)in(int,float) and math.isfinite(v)for v in rect.values())
          and min(rect['x'],rect['y'])>=0 and rect['width']>0 and rect['height']>0
          and rect['x']+rect['width']<=width and rect['y']+rect['height']<=height,'Bounded exact atlas region required')
    check(local==dict(x=0,y=0,width=rect['width'],height=rect['height'])
          and atlas['textureRectOffset']==dict(x=0,y=0),'Trimmed/local-offset atlas Sprite requires another profile')
    check(set(pivot)=={'x','y'} and all(type(v)in(int,float) and math.isfinite(v) and 0<=v<=1 for v in pivot.values())
          and type(ppu)in(int,float) and math.isfinite(ppu) and ppu>0,'Exact finite pivot/PPU required')
    uv=atlas['uvTransform']
    check(uv==dict(x=ppu,y=rect['x']+rect['width']*pivot['x'],z=ppu,w=rect['y']+rect['height']*pivot['y']),
          'Atlas UV transform does not prove the standalone region representation')
    vertices,triangles=_tight_mesh(data)
    # Serialized positions and atlas transforms are float32. Preserve that
    # arithmetic at each operation; widening first creates false negative UVs
    # at exact atlas edges. No clipping or epsilon expansion is applied.
    def f32(value):return struct.unpack('<f',struct.pack('<f',value))[0]
    def coord(value,scale,offset,size):return f32(f32(f32(value*scale)+offset)/size)
    coords=[dict(x=coord(x,uv['x'],uv['y'],width),y=coord(y,uv['z'],uv['w'],height))for x,y,_ in vertices]
    check(all(math.isfinite(v) and 0<=v<=1 for row in coords for v in row.values()),'Atlas UV outside texture')
    result=dict(geometryProfile='unity-2021.3-unrotated-rectangle-atlas-v1',sourceSpriteDataSha256=sha(encoded(data)),
        sourcePackedSettingsRaw=atlas['settingsRaw'],sourceRect=local,targetRect=rect,
        uvArithmetic='float32-multiply-add-divide-separate-operations-no-clamp',
        meshVertices=[dict(x=x,y=y)for x,y,_ in vertices],triangleIndices=triangles,meshUv=coords,verifyMesh=True,
        representation='native-unpacked-atlas-region;source-packed-flags-not-equated')
    result['geometrySha256']=sha(encoded(result))
    return result
