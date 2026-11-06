from pathlib import Path
import unittest


PROBE_PATH = Path(__file__).parents[2] / "src/grea/recovery/targets/UnityStaticMaskClipProbe.cs"


def expected_rect_probe_points(rect):
    x_min, y_min, x_max, y_max = rect
    center = ((x_min + x_max) / 2, (y_min + y_max) / 2)
    width = x_max - x_min
    outside = (x_max + width * 0.25, center[1])
    return center, outside


def opaque_white(pixel):
    r, g, b, a = pixel
    return a >= 245 and r >= 230 and g >= 230 and b >= 230


def clear_pixel(pixel):
    return pixel[3] <= 12


class StaticMaskClipProbeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PROBE_PATH.read_text(encoding="utf-8")

    def test_rect_points_are_strictly_inside_and_outside(self):
        inside, outside = expected_rect_probe_points((-12.0, -7.0, 12.0, 7.0))
        self.assertEqual((0.0, 0.0), inside)
        self.assertEqual((18.0, 0.0), outside)
        self.assertLess(abs(inside[0]), 12.0)
        self.assertGreater(outside[0], 12.0)
        self.assertIn("rect.xMax+rect.width*.25f", self.source)
        self.assertIn("var insideLocal=rect.center", self.source)

    def test_pixel_classes_distinguish_enabled_clip_from_disabled_no_clip(self):
        white = (255, 255, 255, 255)
        clear = (0, 0, 0, 0)
        self.assertTrue(opaque_white(white))
        self.assertFalse(opaque_white(clear))
        self.assertTrue(clear_pixel(clear))
        self.assertFalse(clear_pixel(white))
        # An enabled Rect Mask clips the outside point; a disabled Mask leaves
        # the same synthetic child visible there.
        self.assertTrue(opaque_white(white) and clear_pixel(clear))
        self.assertTrue(opaque_white(white) and opaque_white(white))
        self.assertIn("spec.enabled?MaskClipExpectedClear(outside32):MaskClipExpectedOpaqueWhite(outside32)", self.source)

    def test_probe_uses_real_mask_stencil_render_and_raycast_apis(self):
        self.assertIn("probeCamera.Render()", self.source)
        self.assertIn("new RenderTexture(probeSize,probeSize,24,RenderTextureFormat.ARGB32)", self.source)
        self.assertIn("probeMask.IsRaycastLocationValid(insideScreen,probeCamera)", self.source)
        self.assertIn("probeMask.IsRaycastLocationValid(outsideScreen,probeCamera)", self.source)
        self.assertIn("childGraphic.Raycast(insideScreen,probeCamera)", self.source)
        self.assertIn("childGraphic.Raycast(outsideScreen,probeCamera)", self.source)
        self.assertIn("stencilClipVerified=spec.enabled&&result.insidePixelVerified&&result.outsidePixelVerified&&result.alphaSamplesVerified", self.source)
        self.assertIn("stimulusSprite=Sprite.Create(stimulusTexture", self.source)
        self.assertIn("childGraphic.sprite=stimulusSprite", self.source)
        self.assertIn("result.stimulusObjectsDestroyed=stimulusSprite==null&&stimulusTexture==null", self.source)

    def test_preview_camera_is_scene_bound_and_requires_same_context_white_control(self):
        self.assertIn("probeCamera.scene=probeScene", self.source)
        self.assertIn("result.probeCameraSceneBound=probeCamera.scene==probeScene", self.source)
        self.assertIn("GraphicsDeviceType.Null", self.source)
        self.assertIn("result.unmaskedControlVerified=MaskClipExpectedOpaqueWhite(controlInside)", self.source)
        self.assertIn("result.controlContextSha256==result.maskedContextSha256", self.source)
        self.assertIn("maskGraphic.enabled=false;probeMask.enabled=false", self.source)
        self.assertIn("result.controlImagePath=\"Analysis/Readback/MaskClipping/\"+controlPngName", self.source)

    def test_owned_white_quad_covers_rect_and_outside_for_any_pivot(self):
        self.assertIn("childRect.anchoredPosition=new Vector2(rect.width*.125f,0f)", self.source)
        self.assertIn("childRect.sizeDelta=new Vector2(rect.width*1.5f,rect.height*1.5f)", self.source)
        self.assertIn("childMin.x<=-rect.width*.5f", self.source)
        self.assertIn("childMax.x>=rect.width*.75f", self.source)
        self.assertIn("result.stimulusCoverageVerified", self.source)
        self.assertLess(self.source.index("controlPngBytes=readbackTexture.EncodeToPNG()"),
                        self.source.index("if(!result.unmaskedControlVerified)"))

    def test_source_geometry_and_original_activity_are_independent_gates(self):
        self.assertIn("sourceRect.sizeDelta,source.size", self.source)
        self.assertIn("sourceRect.anchorMin-expectedAnchor", self.source)
        self.assertIn("sourceRect.pivot-expectedPivot", self.source)
        self.assertIn("sourceActiveSelf!=source.active||sourceActive!=active", self.source)
        self.assertIn("result.sourceStatePreserved=loadedSource!=null&&loadedSource.activeSelf==sourceActiveSelfBefore", self.source)
        self.assertNotIn("loadedSource.SetActive", self.source)
        self.assertIn("result.probeObjectsDestroyed=host==null&&cameraObject==null", self.source)

    def test_inverted_or_nonrect_masks_are_explicit_gaps(self):
        self.assertIn("!spec.inverted&&(spec.maskType==0||spec.maskType==2)", self.source)
        self.assertIn("clip-probe-supports-only-noninverted-rect-or-pinned-image-alpha-mask", self.source)
        self.assertIn("spec.maskType!=2", self.source)
        self.assertIn("UnityStaticMaskSort.ReadStaticMask(spec,loadedSource", self.source)
        self.assertIn("id==spec.spriteFrameUuid?imageInput.sprite:null", self.source)
        self.assertIn("sourceId.Substring(0,sourceSeparator)+\":\"+spec.spriteFrameUuid", self.source)
        self.assertIn("spec.spriteFrameUuid.Contains(\":\")", self.source)
        self.assertIn("unsupported-mask-clipping-semantics", self.source)

    def test_image_alpha_probe_hashes_and_decodes_the_exact_texture_spec(self):
        self.assertIn("importer.textureCompression!=TextureImporterCompression.Uncompressed", self.source)
        self.assertIn("importer.alphaSource!=TextureImporterAlphaSource.FromInput", self.source)
        self.assertIn("settings.spriteMeshType!=SpriteMeshType.FullRect", self.source)
        self.assertIn("ImageConversion.LoadImage(decoded,sourceBytes,false)", self.source)
        self.assertIn("alphaDiscardPolicy=\"discard-if-source-alpha-less-than-threshold\"", self.source)


if __name__ == "__main__":
    unittest.main()

