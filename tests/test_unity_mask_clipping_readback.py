import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from monkey.unity_mask_clipping_readback import CONTRACT, METHOD, PREFIX, _TRUE, verify


class MaskClippingReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sid = 'source:mask#4/components/0'; self.node = 'source:mask#4'
        self.spec = dict(sourceId=self.sid, node=self.node, maskType=0, inverted=False, enabled=True,
                         sourceActiveSelf=True, sourceActive=False)
        self.plan = dict(staticMasks=dict(contract=CONTRACT,masks=[self.spec]),
                         components=[dict(sourceId=self.sid,node=self.node,type='cc.Mask')],
                         nodes=[dict(sourceId=self.node,size=[200,100],anchor=[.5,.5])])
        token=hashlib.sha256(self.sid.encode()).hexdigest()[:20]
        self.jp=PREFIX+'maskclip-'+token+'.json'; self.pp=PREFIX+'maskclip-'+token+'.png'
        self.probe=dict.fromkeys(_TRUE,True)
        self.probe.update(sourceId=self.sid,node=self.node,method=METHOD,
            stimulus='temporary-white-child-image-on-transparent-world-space-canvas',
            evidencePath=self.jp,imagePath=self.pp,sourceAppFrame=False,sourceVisualParityClaimed=False,
            sourceMaskEnabled=True,sourceNodeActiveSelf=True,sourceNodeActiveInHierarchy=False,
            status='native-stencil-clipping-verified',stencilClipVerified=True,disabledNoClipVerified=False,
            maskOutsidePointRejected=True,
            childGraphicOutsideRejected=True,disabledChildGraphicOutsideAccepted=False,
            diagnostics=[],insideLocalPoint=[0,0],outsideLocalPoint=[150,0],
            imageWidth=256,imageHeight=256,insidePixel=[128,128],outsidePixel=[224,128],
            insideViewportPoint=[.5,.5,10],outsideViewportPoint=[.875,.5,10],
            insideRgba=[255]*4,outsideRgba=[0]*4)
        self.row=dict(sourceId=self.sid,verified=True,clipProbeVerified=True,persistentIdentityVerified=True,
                      persistentIdentityGuid='a'*32,persistentIdentityLocalFileId=42,clipProbe=self.probe)
        self.rb=dict(sourcePrefabs=[dict(guid='a'*32,staticMaskFields=[self.row])])
        image=Image.new('RGBA',(256,256)); image.putpixel((128,127),(255,255,255,255))
        self.image=image; self.sync()

    def sync(self):
        (self.root/PREFIX).mkdir(parents=True,exist_ok=True)
        self.image.save(self.root/self.pp)
        self.probe['imageSha256']=hashlib.sha256((self.root/self.pp).read_bytes()).hexdigest()
        (self.root/self.jp).write_text(json.dumps(self.probe))
        self.rb['staticMaskReadbackFiles']=[dict(path=p,sha256=hashlib.sha256((self.root/p).read_bytes()).hexdigest()) for p in (self.jp,self.pp)]

    def check(self): return verify(self.plan,self.rb,self.root)

    def test_inactive_source_is_preserved_while_controlled_probe_is_active(self):
        self.assertEqual([],self.check())

    def test_disabled_mask_requires_visible_outside_stimulus(self):
        self.spec['enabled']=False
        self.probe.update(sourceMaskEnabled=False,status='disabled-mask-no-clip-verified',
                          stencilClipVerified=False,disabledNoClipVerified=True,
                          maskOutsidePointRejected=False,
                          childGraphicOutsideRejected=False,disabledChildGraphicOutsideAccepted=True,
                          outsideRgba=[255]*4)
        self.image.putpixel((224,127),(255,255,255,255));self.sync()
        self.assertEqual([],self.check())

    def test_legacy_plan_does_not_require_new_probe(self):
        self.assertEqual([],verify({}, {}, self.root))

    def test_stale_image_sha_blocks(self):
        (self.root/self.pp).write_bytes(b'changed')
        self.assertTrue(self.check())

    def test_white_outside_cannot_pass_by_repinning_files(self):
        self.image.putpixel((224,127),(255,255,255,255));self.probe['outsideRgba']=[255]*4;self.sync()
        self.assertTrue(self.check())

    def test_forged_pixel_value_differs_from_png(self):
        self.image.putpixel((224,127),(255,255,255,255));self.sync()
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

    def test_unsupported_mask_cannot_inherit_rect_probe(self):
        self.spec['inverted']=True;self.assertTrue(self.check())

    def test_persistent_identity_is_required(self):
        self.row['persistentIdentityLocalFileId']=0;self.assertTrue(self.check())

    def test_persistent_identity_cannot_belong_to_another_prefab(self):
        self.row['persistentIdentityGuid']='b'*32;self.assertTrue(self.check())

    def test_unpinned_json_blocks(self):
        (self.root/PREFIX/'extra.json').write_text('{}');self.assertTrue(self.check())


if __name__=='__main__':unittest.main()
