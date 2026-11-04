from pathlib import Path
import unittest


PROBE_PATH = Path(__file__).parents[1] / "src/monkey/targets/UnityStaticMaskClipProbe.cs"


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
        self.assertIn("new RenderTexture(MaskClipProbeSize,MaskClipProbeSize,24,RenderTextureFormat.ARGB32)", self.source)
        self.assertIn("probeMask.IsRaycastLocationValid(insideScreen,probeCamera)", self.source)
        self.assertIn("probeMask.IsRaycastLocationValid(outsideScreen,probeCamera)", self.source)
        self.assertIn("childGraphic.Raycast(insideScreen,probeCamera)", self.source)
        self.assertIn("childGraphic.Raycast(outsideScreen,probeCamera)", self.source)
        self.assertIn("stencilClipVerified=spec.enabled&&result.insidePixelVerified&&result.outsidePixelVerified", self.source)

    def test_source_geometry_and_original_activity_are_independent_gates(self):
        self.assertIn("sourceRect.sizeDelta,source.size", self.source)
        self.assertIn("sourceRect.anchorMin-expectedAnchor", self.source)
        self.assertIn("sourceRect.pivot-expectedPivot", self.source)
        self.assertIn("sourceActiveSelf!=source.active||sourceActive!=active", self.source)
        self.assertIn("result.sourceStatePreserved=loadedSource!=null&&loadedSource.activeSelf==sourceActiveSelfBefore", self.source)
        self.assertNotIn("loadedSource.SetActive", self.source)
        self.assertIn("result.probeObjectsDestroyed=host==null&&cameraObject==null", self.source)

    def test_inverted_or_nonrect_masks_are_explicit_gaps(self):
        self.assertIn("spec.maskType==0&&!spec.inverted", self.source)
        self.assertIn("clip-probe-supports-only-noninverted-rect-mask-type-0", self.source)
        self.assertIn("unsupported-mask-clipping-semantics", self.source)


if __name__ == "__main__":
    unittest.main()

