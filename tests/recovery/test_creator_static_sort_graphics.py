import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class CreatorStaticSortGraphicsTests(unittest.TestCase):
    def test_empty_static_graphics_is_a_disabled_typed_non_draw_carrier(self):
        proxy = (ROOT / "src/grea/recovery/targets/CreatorStaticSortQueueProxy.ts").read_text()
        controls = (ROOT / "src/grea/recovery/targets/CreatorStaticControls.js").read_text()
        self.assertIn("component.enabled = false", controls)
        self.assertIn("not-serialized-empty-in-fixed-state", controls)
        self.assertIn("sourceRenderer(node, row.sourceType, false, false)", proxy)
        self.assertIn("row.noDrawReason === 'empty-command-stream'", proxy)
        self.assertIn("row.nativeEnabledExpected === false && !component.enabled", proxy)
        self.assertIn("row.initialCommandStreamEmpty === true", proxy)
        self.assertIn("actualGraphicsPaths === 0", proxy)
        self.assertIn("creatorStaticGraphicsMaterialVerified(component)", proxy)
        self.assertIn("CREATOR_PROXY_UNCOVERED_SOURCE_UIRENDERER", proxy)
        self.assertIn("sourceOriginalDrawEvents: CreatorProxyEvent[]", proxy)
        self.assertIn("CREATOR_PROXY_ORIGINAL_QUEUE_PROJECTION_MISMATCH", proxy)
        self.assertIn("CREATOR_PROXY_EMPTY_GRAPHICS_SOURCE_EVENT_MISSING", proxy)
        self.assertIn("sourceEventIndex", proxy)

    def test_sprite_needs_binding_uses_creator_scene_policy_for_enabled_readback(self):
        proxy = (ROOT / "src/grea/recovery/targets/CreatorStaticSortQueueProxy.ts").read_text()
        scene = (ROOT / "src/grea/recovery/targets/CreatorScene.js").read_text()
        self.assertIn("comp.enabled=c.enabled&&!c.needsSpriteBinding", scene)
        self.assertIn("sourceNeedsSpriteBinding: boolean", proxy)
        self.assertIn("row.sourceEnabled && row.sourceNeedsSpriteBinding === false", proxy)
        self.assertNotIn("unresolved-sprite-binding", proxy)
        self.assertIn("row.sourceSpriteFrameUuid === null &&", proxy)
        self.assertIn("row.nativeSpriteFrameUuidExpected === null && actualSpriteFrame === null", proxy)
        self.assertIn("actualSpriteFrame === row.nativeSpriteFrameUuidExpected", proxy)
        self.assertIn("sourceSpriteFrameAssetId: string | null", proxy)
        self.assertIn("nativeSpriteImageUuidExpected: string | null", proxy)
        self.assertIn("sourceSpriteFrameAssetId: row.sourceSpriteFrameAssetId", proxy)
        self.assertIn("nativeSpriteImageUuidExpected: row.nativeSpriteImageUuidExpected", proxy)
        self.assertIn("component.enabled === nativeEnabledPolicyExpected && actualSpriteFrame === null", proxy)
        self.assertIn("nativeEnabledPolicy: row.nativeEnabledExpected === nativeEnabledPolicyExpected", proxy)


if __name__ == "__main__":
    unittest.main()
