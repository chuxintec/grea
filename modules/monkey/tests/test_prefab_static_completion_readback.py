import copy,unittest
from monkey.prefab_static_completion_readback import verify_prefab,verify_assets
from monkey.prefab_spine_pipeline import verify as verify_spine

class StaticCompletionReadbackTests(unittest.TestCase):
    def fixture(self):
        component=dict(sourceId='component-a',node='node-a',type='cc.Animation',clips=['clip-a'],defaultClip=None,enabled=True,playOnLoad=False)
        plan=dict(animations=[dict(id='clip-a@component-a',path='Assets/a.anim',convertible=True)],staticAnimationEvidence=[dict(sourceClipId='clip-a',path='Assets/a.json',sha256='a'*64)])
        slot=dict(sourceClipId='clip-a',order=0,status='native_clip_reference_resolved',nativeClipPath='Assets/a.anim',nativeClipGuid='b'*32,referenceMatches=True,assetHashStatus='verified',metaHashStatus='verified',sourceEvidencePath='Assets/a.json',sourceEvidenceGuid='c'*32,sourceEvidenceHashStatus='verified')
        binding=dict(status='reference_fields_verified',markerDisabled=True,animatorDisabled=True,playbackExecuted=False,sourceEnabled=True,sourcePlayOnLoad=False,sourceClipOrder=['clip-a'],sourceDefaultClipId='',clips=[slot])
        saved=dict(staticAnimationFields=[dict(sourceComponentId='component-a',playbackExecuted=False,binding=binding)])
        return plan,component,saved
    def test_exact_animation_and_wrong_asset_order_hash_rejected(self):
        plan,c,saved=self.fixture();self.assertEqual(verify_prefab(plan,[c],saved,'unity','owner'),[])
        for key,value in [('nativeClipPath','Assets/wrong.anim'),('order',1),('sourceEvidenceHashStatus','mismatch'),('referenceMatches',False)]:
            broken=copy.deepcopy(saved);broken['staticAnimationFields'][0]['binding']['clips'][0][key]=value
            self.assertTrue(verify_prefab(plan,[c],broken,'unity','owner'),key)
    def test_source_missing_static_clip_does_not_pass_with_null_object(self):
        plan,c,saved=self.fixture();plan['animations']=[]
        slot=saved['staticAnimationFields'][0]['binding']['clips'][0];slot['status']='source_evidence_retained';slot['sourceEvidenceGuid']=''
        self.assertTrue(any(x['code']=='STATIC_COMPLETION_NATIVE_MISMATCH'for x in verify_prefab(plan,[c],saved,'unity','owner')))
    def test_source_unbound_spine_requires_all_native_static_checks(self):
        checks={k:True for k in ['sourceNodeActiveMatchesPlan','sourceTimeScaleRetainedInPinnedSpec','nativeTimeScaleFrozenAtT0','nativeRendererEnabled','exactBuiltinMaterialContract','usesDefaultBuiltinMaterialRoute','skinFieldMatchesSource','animationFieldMatchesSource','loopFieldMatchesSource','premultipliedAlphaFieldMatchesSource','tintFieldMatchesSource','debugSlotsFieldMatchesSource','debugBonesFieldMatchesSource','debugMeshFieldMatchesSource','enableBatchFieldMatchesSource','cachingFieldMatchesSource']}
        spec=dict(sourceId='s',convertible=True,spineBinding=dict(sourceDataAssetId=None,runtimeDynamicAssignment=dict(status='source_static_uuid_absent_runtime_assignment_unverified',targetDefaultAssetFallback=False)))
        row=dict(sourceComponentId='s',status='incomplete_dynamic_assignment',failures=[],staticDataBoundBySource=False,runtimeDataAvailable=False,observedDataWithoutStaticSourceReference=False,actual=dict(skeletonDataUuid=None,nativeComponentUuid='uuid'),checks=checks)
        self.assertEqual(verify_spine([spec],[row],'o')[0]['code'],'SPINE_SOURCE_UNBOUND_DYNAMIC_NOT_RUN')
        for changed in ['source-data','target-data','static-field']:
            c=copy.deepcopy(spec);r=copy.deepcopy(row)
            if changed=='source-data':c['spineBinding']['sourceDataAssetId']='nonempty'
            elif changed=='target-data':r['actual']['skeletonDataUuid']='invented'
            else:r['checks']['loopFieldMatchesSource']=False
            self.assertEqual(verify_spine([c],[r],'o')[0]['code'],'SPINE_NATIVE_COMPONENT_INCOMPLETE')


def test_creator_canvas_pixels_require_both_independent_native_and_source_proofs():
    spec=dict(sourceId='t',retentionKind='texture-asset',rgbaSha256='a'*64,creatorPngSha256='b'*64,dimensions=[2,2],creator=dict(uuid='texture-id',imageUuid='image-id'))
    plan=dict(staticRetainedAssets=dict(assets=[spec]))
    row=dict(sourceId='t',retentionKind='texture-asset',verified=True,persistent=True,uuid='texture-id',imageUuid='image-id',width=2,height=2,sourceRgbaSha256='a'*64,pngSha256='b'*64,nativePixelAccess='image-canvas',pixelComparison='browser-decoded-png-to-native-image-canvas-exact-v1',nativePixelsEqualPng=True,pngPixelSha256='c'*64,nativeImagePixelSha256='c'*64)
    assert not verify_assets(plan,[row],'creator')
    for key,value in [('pngSha256','bad'),('nativeImagePixelSha256','d'*64),('imageUuid','wrong'),('nativePixelsEqualPng',False),('nativePixelAccess','unknown')]:
        broken=dict(row,**{key:value})
        assert verify_assets(plan,[broken],'creator')


def test_creator_image_mask_requires_loaded_backing_not_only_saved_fields():
    spec=dict(sourceId='mask',node='node',maskType=2,inverted=False,enabled=True,alphaThreshold=.2,sourceFieldsJson='{}')
    plan=dict(staticMasks=dict(masks=[spec]));components=[dict(sourceId='mask',node='node',type='cc.Mask')]
    row=dict(spec,verified=True)
    initialized=dict(row,initialized=True,initializedBackingVerified=True,nativeSpriteFrameUuid='native-frame',maskSpriteFrameUuid='native-frame')
    saved=dict(staticMaskFields=[row],staticMaskInitializedFields=[initialized])
    assert not verify_prefab(plan,components,saved,'creator','owner')
    for key,value in [('initialized',False),('initializedBackingVerified',False),('maskSpriteFrameUuid','foreign')]:
        broken=dict(saved,staticMaskInitializedFields=[dict(initialized,**{key:value})])
        assert verify_prefab(plan,components,broken,'creator','owner')
