import copy
import hashlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from grea.recovery.unity_mask_clipping_readback import CONTRACT, IMAGE_METHOD, METHOD, PREFIX, _TRUE, _rotate_scale_local, verify


class MaskClippingReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sid = 'source:mask#4/components/0'; self.node = 'source:mask#4'
        self.spec = dict(sourceId=self.sid, node=self.node, maskType=0, inverted=False, enabled=True,
                         sourceActiveSelf=True, sourceActive=False)
        self.plan = dict(staticMasks=dict(contract=CONTRACT,masks=[self.spec]),
                         components=[dict(sourceId=self.sid,node=self.node,type='cc.Mask')],
                         nodes=[dict(sourceId=self.node,size=[200,100],anchor=[.5,.5],scale=[1,1,1],rotation=[0,0,0,1])])
        token=hashlib.sha256(self.sid.encode()).hexdigest()[:20]
        self.jp=PREFIX+'maskclip-'+token+'.json'; self.pp=PREFIX+'maskclip-'+token+'.png'
        self.cp=PREFIX+'maskclip-'+token+'-control.png'
        self.probe=dict.fromkeys(_TRUE,True)
        self.probe.update(sourceId=self.sid,node=self.node,method=METHOD,probeProfile='rect',
            stimulus='owned-white-sprite-child-on-transparent-world-space-canvas',
            evidencePath=self.jp,imagePath=self.pp,controlImagePath=self.cp,
            graphicsDeviceType='Metal',controlContextSha256='f'*64,maskedContextSha256='f'*64,
            controlImageSha256='',unmaskedControlInsideRgba=[255]*4,unmaskedControlOutsideRgba=[255]*4,
            unmaskedControlAlphaSamples=[],sourceAppFrame=False,sourceVisualParityClaimed=False,
            sourceMaskEnabled=True,sourceNodeActiveSelf=True,sourceNodeActiveInHierarchy=False,
            status='native-stencil-clipping-verified',stencilClipVerified=True,disabledNoClipVerified=False,
            maskOutsidePointRejected=True,
            childGraphicOutsideRejected=True,disabledChildGraphicOutsideAccepted=False,
            diagnostics=[],insideLocalPoint=[0,0],outsideLocalPoint=[150,0],
            imageWidth=256,imageHeight=256,probeCanvasSide=1200,
            stimulusChildCenter=[25,0],stimulusChildSize=[300,150],
            insidePixel=[128,128],outsidePixel=[160,128],
            insideViewportPoint=[.5,.5,10],outsideViewportPoint=[.625,.5,10],
            insideRgba=[255]*4,outsideRgba=[0]*4)
        self.row=dict(sourceId=self.sid,verified=True,clipProbeVerified=True,persistentIdentityVerified=True,
                      persistentIdentityGuid='a'*32,persistentIdentityLocalFileId=42,clipProbe=self.probe)
        self.rb=dict(sourcePrefabs=[dict(guid='a'*32,staticMaskFields=[self.row])])
        image=Image.new('RGBA',(256,256)); image.putpixel((128,127),(255,255,255,255))
        self.image=image; self.sync()

    def _project(self,local,size):
        side=self.probe['probeCanvasSide']
        world=_rotate_scale_local(self.plan['nodes'][0],local)
        viewport=[.5+world[0]/side,.5+world[1]/side,10+world[2]]
        return [int(viewport[0]*size),int(viewport[1]*size)],viewport

    def sync(self):
        (self.root/PREFIX).mkdir(parents=True,exist_ok=True)
        self.image.save(self.root/self.pp)
        Image.new('RGBA',self.image.size,(255,255,255,255)).save(self.root/self.cp)
        self.probe['controlImageSha256']=hashlib.sha256((self.root/self.cp).read_bytes()).hexdigest()
        self.probe['imageSha256']=hashlib.sha256((self.root/self.pp).read_bytes()).hexdigest()
        (self.root/self.jp).write_text(json.dumps(self.probe))
        self.rb['staticMaskReadbackFiles']=[dict(path=p,sha256=hashlib.sha256((self.root/p).read_bytes()).hexdigest()) for p in (self.jp,self.pp,self.cp)]

    def check(self): return verify(self.plan,self.rb,self.root)

    def test_inactive_source_is_preserved_while_controlled_probe_is_active(self):
        self.assertEqual([],self.check())

    def test_two_positive_rows_and_mixed_results(self):
        first_files = self.rb['staticMaskReadbackFiles'][:]
        second = copy.deepcopy(self.row)
        sid = self.sid + '-second'
        second['sourceId'] = sid
        self.plan['components'].append(dict(self.plan['components'][0], sourceId=sid))
        self.plan['staticMasks']['masks'].append(dict(self.spec, sourceId=sid))
        self.rb['sourcePrefabs'][0]['staticMaskFields'].append(second)
        self.probe = second['clipProbe']
        self.probe['sourceId'] = sid
        token = hashlib.sha256(sid.encode()).hexdigest()[:20]
        self.jp, self.pp, self.cp = [PREFIX+'maskclip-'+token+suffix for suffix in ('.json','.png','-control.png')]
        self.probe.update(evidencePath=self.jp, imagePath=self.pp, controlImagePath=self.cp)
        for digest in ('f'*64, 'x'):
            self.probe.update(controlContextSha256=digest, maskedContextSha256=digest)
            self.sync()
            self.rb['staticMaskReadbackFiles'].extend(first_files)
            gaps = self.check()
            if digest == 'x':
                self.assertEqual([sid], [gap['sourceId'] for gap in gaps])
            else:
                self.assertEqual([], gaps)

    def test_disabled_mask_requires_visible_outside_stimulus(self):
        self.spec['enabled']=False
        self.probe.update(sourceMaskEnabled=False,status='disabled-mask-no-clip-verified',
                          stencilClipVerified=False,disabledNoClipVerified=True,
                          maskOutsidePointRejected=False,
                          childGraphicOutsideRejected=False,disabledChildGraphicOutsideAccepted=True,
                          outsideRgba=[255]*4)
        self.image.putpixel((160,127),(255,255,255,255));self.sync()
        self.assertEqual([],self.check())

    def test_legacy_plan_does_not_require_new_probe(self):
        self.assertEqual([],verify({}, {}, self.root))

    def test_stale_image_sha_blocks(self):
        (self.root/self.pp).write_bytes(b'changed')
        self.assertTrue(self.check())

    def test_white_outside_cannot_pass_by_repinning_files(self):
        self.image.putpixel((160,127),(255,255,255,255));self.probe['outsideRgba']=[255]*4;self.sync()
        self.assertTrue(self.check())

    def test_forged_pixel_value_differs_from_png(self):
        self.image.putpixel((160,127),(255,255,255,255));self.sync()
        self.assertTrue(self.check())

    def test_source_activity_cleanup_and_parity_flags_are_independent_gates(self):
        original=copy.deepcopy(self.probe)
        for key,value in [('sourceNodeActiveInHierarchy',True),('probeObjectsDestroyed',False),
                          ('sourceStatePreserved',False),('sourceAppFrame',True),('sourceVisualParityClaimed',True)]:
            with self.subTest(key=key):
                self.probe.clear();self.probe.update(copy.deepcopy(original));self.probe[key]=value;self.sync()
                self.assertTrue(self.check())

    def test_projection_or_local_point_tampering_blocks(self):
        self.probe['insidePixel']=[127,128];self.sync();self.assertTrue(self.check())
        self.probe['insidePixel']=[128,128];self.probe['outsideLocalPoint']=[100,0];self.sync()
        self.assertTrue(self.check())

    def test_duplicate_or_missing_mask_denominator_blocks(self):
        self.rb['sourcePrefabs'][0]['staticMaskFields'].append(copy.deepcopy(self.row));self.assertTrue(self.check())
        self.rb['sourcePrefabs'][0]['staticMaskFields']=[];self.assertTrue(self.check())

    def test_sidecar_and_embedded_copy_must_match(self):
        self.probe['method']='different';self.assertTrue(self.check())

    def test_descriptor_must_cover_exact_file_set(self):
        self.rb['staticMaskReadbackFiles'].pop();self.assertTrue(self.check())

    def test_control_requires_bound_camera_scene_same_context_and_opaque_white(self):
        self.probe['probeCameraSceneBound']=False;self.sync();self.assertTrue(self.check())
        self.probe['probeCameraSceneBound']=True;self.probe['unmaskedControlVerified']=False;self.sync();self.assertTrue(self.check())
        self.probe['unmaskedControlVerified']=True;self.probe['maskedContextSha256']='0'*64;self.sync();self.assertTrue(self.check())

    def test_null_graphics_device_is_not_a_rendering_result(self):
        self.probe['graphicsDeviceType']='Null';self.sync();self.assertTrue(self.check())

    def test_unsupported_mask_cannot_inherit_rect_probe(self):
        self.spec['inverted']=True;self.assertTrue(self.check())

    def test_persistent_identity_is_required(self):
        self.row['persistentIdentityLocalFileId']=0;self.assertTrue(self.check())

    def test_persistent_identity_cannot_belong_to_another_prefab(self):
        self.row['persistentIdentityGuid']='b'*32;self.assertTrue(self.check())

    def test_unpinned_json_blocks(self):
        (self.root/PREFIX/'extra.json').write_text('{}');self.assertTrue(self.check())

    def _image_mask_fixture(self,threshold=.1,enabled=True):
        frame='texture-mask-alpha';texture_id='source:'+frame
        texture_path='Assets/Game/Content/Textures/mask-alpha.png'
        source=Image.new('RGBA',(8,8),(255,255,255,255))
        # Pillow rows are top-origin; probe texels use Unity's bottom-origin coordinates.
        source.putpixel((1,6),(255,255,255,0))
        source.putpixel((3,4),(255,255,255,1))
        source_bytes=io.BytesIO();source.save(source_bytes,format='PNG');raw=source_bytes.getvalue()
        source_path=self.root/texture_path;source_path.parent.mkdir(parents=True,exist_ok=True);source_path.write_bytes(raw)
        source_sha=hashlib.sha256(raw).hexdigest()
        self.plan['textures']=[dict(id=texture_id,path=texture_path,size=[8,8],originalSize=[8,8],offset=[0,0],border=[0,0,0,0])]
        self.plan['nodes'][0]['size']=[80,80]
        self.plan['nodes'][0]['anchor']=[.5,.5]
        self.probe['probeCanvasSide']=400
        self.probe['stimulusChildCenter']=[10,0]
        self.probe['stimulusChildSize']=[120,120]
        self.spec.update(maskType=2,inverted=False,enabled=enabled,sourceActiveSelf=True,sourceActive=True,
            spriteFrameUuid=frame,alphaThreshold=threshold,unityMaskMaterialGuid='c'*32,
            unityMaskShaderPath='Assets/Game/Content/Materials/StaticMasks/NativeStaticImageMask.shader',
            unityMaskShaderSha256='d'*64,sourceEffectName='builtin-2d-sprite',sourceEffectDocumentSha256='e'*64)
        self.row.update(unityMaskMaterialGuid='c'*32,unityMaskShaderPath=self.spec['unityMaskShaderPath'],
                        unityMaskShaderSha256='d'*64)
        samples=[]
        for kind,texel,alpha,pixel in (
            ('opaque',[6,6],255,[0,0]),
            ('transparent-zero',[1,1],0,[0,0]),
            ('low-nonzero',[3,3],1,[0,0]),
        ):
            alpha_pass=alpha/255.0>=threshold
            visible=(not enabled) or alpha_pass
            anchor=self.plan['nodes'][0]['anchor']
            local=[(texel[0]+.5)/8*80-anchor[0]*80,(texel[1]+.5)/8*80-anchor[1]*80]
            pixel,viewport=self._project(local,512)
            samples.append(dict(kind=kind,sourceTexturePixel=texel,sourceAlphaByte=alpha,
                sourceAlpha=alpha/255.0,sourceAlphaPass=alpha_pass,expectedVisible=visible,
                localPoint=local,pixel=pixel,viewportPoint=viewport,
                rgba=[255]*4 if visible else [0]*4,pixelVerified=True))
        self.probe.update(method=IMAGE_METHOD,probeProfile='sprite-alpha-threshold',
            sourceSpriteFrameId=frame,sourceSpriteGuid='b'*32,sourceSpriteLocalFileId=21300000,
            sourceTextureId=texture_id,sourceTexturePath=texture_path,sourceTextureGuid='b'*32,
            sourceTextureSha256=source_sha,sourceTextureFormat='RGBA32',sourceTextureImportMode='Single',
            sourceTextureMeshType='FullRect',sourceTextureCompression='Uncompressed',sourceTextureAlphaSource='FromInput',
            sourceTextureWidth=8,sourceTextureHeight=8,sourceTextureAlphaVerified=True,sourceMaskMaterialVerified=True,
            sourceMaterialGuid='c'*32,sourceMaterialShaderPath=self.spec['unityMaskShaderPath'],
            sourceMaterialShaderSha256='d'*64,alphaDiscardPolicy='discard-if-source-alpha-less-than-threshold',
            sourceAlphaThreshold=threshold,sourceAlphaSamples=samples,alphaSamplesVerified=True,
            imageWidth=512,imageHeight=512,probeCanvasSide=400,insideLocalPoint=samples[0]['localPoint'],outsideLocalPoint=[60,0],
            sourceNodeActiveSelf=True,sourceNodeActiveInHierarchy=True,
            insidePixel=samples[0]['pixel'],insideViewportPoint=samples[0]['viewportPoint'],insideRgba=samples[0]['rgba'],
            outsidePixel=self._project([(1.25-self.plan['nodes'][0]['anchor'][0])*80,
                                        (.5-self.plan['nodes'][0]['anchor'][1])*80],512)[0],
            outsideViewportPoint=self._project([(1.25-self.plan['nodes'][0]['anchor'][0])*80,
                                                (.5-self.plan['nodes'][0]['anchor'][1])*80],512)[1],
            outsideRgba=[255]*4 if not enabled else [0]*4,insidePixelVerified=True,outsidePixelVerified=True,
            stencilClipVerified=enabled,disabledNoClipVerified=not enabled,sourceMaskEnabled=enabled,
            maskOutsidePointRejected=enabled,childGraphicOutsideRejected=enabled,
            disabledChildGraphicOutsideAccepted=not enabled,
            status='native-stencil-clipping-verified' if enabled else 'disabled-mask-no-clip-verified')
        self.probe['unmaskedControlAlphaSamples']=[dict(kind=row['kind'],pixel=list(row['pixel']),
            viewportPoint=list(row['viewportPoint']),rgba=[255]*4) for row in samples]
        self.rb['sprites']=[dict(id=texture_id,guid='b'*32,fileId=21300000,size=[8,8])]
        self.owned_files={texture_path:dict(path=texture_path,owner='generated',bytes=len(raw),sha256=source_sha)}
        probe_image=Image.new('RGBA',(512,512),(0,0,0,0))
        for sample in samples:
            x,y=sample['pixel'];probe_image.putpixel((x,511-y),tuple(sample['rgba']))
        x,y=self.probe['outsidePixel'];probe_image.putpixel((x,511-y),tuple(self.probe['outsideRgba']))
        self.image=probe_image;self.sync()

    def image_check(self):
        return verify(self.plan,self.rb,self.root,owned_files=getattr(self,'owned_files',None))

    def test_image_mask_uses_manifest_owned_alpha_and_pinned_material_profile(self):
        self._image_mask_fixture(.1)
        self.assertEqual([],self.image_check())

    def test_image_mask_alpha_zero_and_one_are_explained_at_threshold_zero_and_one(self):
        self._image_mask_fixture(0.0)
        self.assertTrue(all(row['expectedVisible'] for row in self.probe['sourceAlphaSamples']))
        self.assertEqual([],self.image_check())
        self._image_mask_fixture(1.0)
        self.assertTrue(self.probe['sourceAlphaSamples'][0]['expectedVisible'])
        self.assertFalse(self.probe['sourceAlphaSamples'][1]['expectedVisible'])
        self.assertFalse(self.probe['sourceAlphaSamples'][2]['expectedVisible'])
        self.assertEqual([],self.image_check())

    def test_alpha_threshold_uses_float32_equality_at_source_byte_boundary(self):
        self._image_mask_fixture(1/255)
        one=next(row for row in self.probe['sourceAlphaSamples'] if row['kind']=='low-nonzero')
        self.assertTrue(one['sourceAlphaPass'])
        self.assertEqual([],self.image_check())

    def test_image_mask_requires_generated_owned_source_texture_bytes(self):
        self._image_mask_fixture(.1)
        self.assertTrue(verify(self.plan,self.rb,self.root,owned_files=None))
        self.owned_files[self.probe['sourceTexturePath']]['sha256']='0'*64
        self.assertTrue(self.image_check())

    def test_image_mask_rejects_source_alpha_or_material_identity_drift(self):
        self._image_mask_fixture(.1)
        self.probe['sourceAlphaSamples'][1]['sourceAlphaByte']=255
        self.sync();self.assertTrue(self.image_check())
        self._image_mask_fixture(.1)
        self.probe['sourceMaterialGuid']='f'*32
        self.sync();self.assertTrue(self.image_check())

    def test_image_control_samples_must_match_masked_alpha_projection(self):
        self._image_mask_fixture(.1)
        self.probe['unmaskedControlAlphaSamples'][0]['pixel']=[127,128]
        self.sync();self.assertTrue(self.image_check())

    def test_image_alpha_projection_is_derived_for_arbitrary_pivot_rotation_and_scale(self):
        self._image_mask_fixture(.1)
        node=self.plan['nodes'][0]
        node['anchor']=[.2,.75];node['scale']=[1.25,.75,1]
        angle=.35;node['rotation']=[0,0,math.sin(angle/2),math.cos(angle/2)]
        self.probe['outsideLocalPoint']=[(1.25-node['anchor'][0])*80,(.5-node['anchor'][1])*80]
        for sample in self.probe['sourceAlphaSamples']:
            texel=sample['sourceTexturePixel']
            sample['localPoint']=[(texel[0]+.5)/8*80-node['anchor'][0]*80,
                                  (texel[1]+.5)/8*80-node['anchor'][1]*80]
            sample['pixel'],sample['viewportPoint']=self._project(sample['localPoint'],512)
        opaque=next(x for x in self.probe['sourceAlphaSamples'] if x['kind']=='opaque')
        self.probe.update(insideLocalPoint=opaque['localPoint'],insidePixel=opaque['pixel'],
                          insideViewportPoint=opaque['viewportPoint'],insideRgba=opaque['rgba'])
        self.probe['unmaskedControlAlphaSamples']=[dict(kind=row['kind'],pixel=list(row['pixel']),
            viewportPoint=list(row['viewportPoint']),rgba=[255]*4) for row in self.probe['sourceAlphaSamples']]
        self.probe['outsidePixel'],self.probe['outsideViewportPoint']=self._project(self.probe['outsideLocalPoint'],512)
        self.probe['stimulusChildCenter']=[10,0];self.probe['stimulusChildSize']=[120,120]
        self.image=Image.new('RGBA',(512,512),(0,0,0,0))
        for sample in self.probe['sourceAlphaSamples']:
            x,y=sample['pixel'];self.image.putpixel((x,511-y),tuple(sample['rgba']))
        x,y=self.probe['outsidePixel'];self.image.putpixel((x,511-y),tuple(self.probe['outsideRgba']))
        self.sync();self.assertEqual([],self.image_check())

        sample=self.probe['sourceAlphaSamples'][1]
        sample['pixel']=[127,128];sample['viewportPoint']=[127.5/512,128.5/512,10]
        self.sync();self.assertTrue(self.image_check())

    def test_image_sprite_frame_lookup_is_bundle_exact(self):
        self._image_mask_fixture(.1)
        other=dict(self.plan['textures'][0],id='other:texture-mask-alpha',path='Assets/Game/Content/Textures/other.png')
        self.plan['textures'].append(other)
        self.assertEqual([],self.image_check())
        self.plan['textures']=[other]
        self.assertTrue(self.image_check())


if __name__=='__main__':unittest.main()
