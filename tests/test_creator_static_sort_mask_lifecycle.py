import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROXY = ROOT / "src/monkey/targets/CreatorStaticSortQueueProxy.ts"
MASK_SDK = Path("/Applications/Cocos/Creator/3.8.8/CocosCreator.app/Contents/Resources/resources/3d/engine/cocos/2d/components/mask.ts")


class CreatorStaticSortMaskLifecycleTests(unittest.TestCase):
    def test_mask_type_is_selected_before_backing_lifecycle(self):
        source = PROXY.read_text()
        sdk = MASK_SDK.read_text()
        begin = source.index("const maskNode = new Node('__sort_mask_'")
        end = source.index("containerStack.push(maskNode)", begin)
        block = source[begin:end]
        self.assertLess(block.index("maskNode.active = false"), block.index("maskNode.addComponent(Mask)"))
        self.assertLess(block.index("mask.type = nativeType"), block.index("maskNode.active = true"))
        self.assertIn("maskSpec.maskType === 0 ? Mask.Type.GRAPHICS_RECT", block)
        self.assertIn("maskSpec.maskType === 1 ? Mask.Type.GRAPHICS_ELLIPSE", block)
        self.assertIn(": Mask.Type.SPRITE_STENCIL", block)
        self.assertIn("mask.subComp instanceof Graphics", block)
        self.assertIn("const sprite = mask.subComp", block)
        self.assertIn("sprite instanceof Sprite", block)
        self.assertLess(sdk.index("this._changeRenderType();", sdk.index("public onLoad")),
                        sdk.index("this._createGraphics();", sdk.index("private _changeRenderType")))
        self.assertIn("sprite = this._sprite = node.addComponent(Sprite)", sdk)
        self.assertIn("graphics = this._graphics = node.addComponent(Graphics)", sdk)

    def test_sprite_mask_reuses_the_single_native_backing_and_rejects_wrong_target(self):
        source = PROXY.read_text()
        copy_start = source.index("function copyRenderer(")
        copy_end = source.index("function addRendererSortRank", copy_start)
        copy = source[copy_start:copy_end]
        self.assertIn("existingTarget?: Component", source)
        self.assertIn("existingTarget.node !== proxyNode", source)
        self.assertIn("const sprite = mask.subComp", source)
        self.assertIn("copyRenderer(sourceSprite, maskNode, 'cc.Sprite', maskSpec.sourceId, sprite)", source)
        self.assertIn("mask.spriteFrame = frame", source)
        self.assertIn("CREATOR_PROXY_MASK_NATIVE_SPRITE_BACKING_MISSING", source)
        self.assertIn("CREATOR_PROXY_MASK_NATIVE_GRAPHICS_BACKING_MISSING", source)
        self.assertIn("badMaskRows: readback.masks.filter(row => !row.verified).slice(0, 4).map(row => boundedMaskFailureSummary(row))", source)
        self.assertIn("function boundedMaskFailureSummary(row: CreatorProxyMaskReadback, maxChars = 900)", source)
        self.assertIn("failedChecks", source)
        for check in ("sourceAndProxyMaskRefs", "maskType", "alphaThreshold", "backingType",
                      "spriteFrame", "sourceAndNativeSpriteFields", "transform", "opacity", "layer"):
            self.assertIn(f"{check}:", source)
        self.assertIn("sourceSpriteFingerprint", source)
        self.assertIn("nativeSpriteFrameExpectedUuid", source)
        self.assertIn("worldMatrixVerified", source)
        self.assertIn("uiSizeVerified", source)
        self.assertIn("uiAnchorVerified", source)
        self.assertIn("sourceWorldMatrix: source ? matrixValues(source) : null", source)
        self.assertIn("nativeWorldMatrix: matrixValues(node)", source)
        self.assertGreater(copy.rindex("uiProxy.setContentSize(uiSource.contentSize)"), copy.index("proxy.spriteFrame = renderer.spriteFrame"))
        self.assertGreater(copy.rindex("uiProxy.setContentSize(uiSource.contentSize)"), copy.index("proxy.trim = renderer.trim; proxy.sizeMode = renderer.sizeMode"))

    def test_empty_graphics_nondraw_failure_reports_failed_material_and_raw_source_checks(self):
        source = PROXY.read_text()
        for check in ("sourceMaterialIdsPresent", "actualPathsEmpty", "sourceRawGraphicsType",
                      "sourceRawMaterialFieldsPresent", "builtinMaterialIdentity", "rendererMaterialMatchesCustom"):
            self.assertIn(check, source)
        self.assertIn("failedChecks: Object.keys(checks).filter(key => !checks[key])", source)
        self.assertIn("sourceRawMaterials", source)
        self.assertIn("sourceFieldsSha256", source)
        self.assertIn("graphicsPathCount: actualGraphicsPaths", source)
        self.assertIn("nativeMaterialUuid: graphicsMaterial?.materialUuid", source)
        self.assertIn("disabled, empty Graphics is a static carrier", source)
        self.assertIn("creatorStaticEmptyGraphicsEvidence(component.enabled, pathCount", source)

    def test_persistent_mask_backing_is_exact_unique_typed_component(self):
        source = PROXY.read_text()
        sdk = MASK_SDK.read_text()
        self.assertIn("if (!mask.subComp && node.getComponents(Mask).length === 1)", source)
        self.assertIn("node.getComponents(Graphics).length === 1 && node.getComponents(Sprite).length === 0", source)
        self.assertIn("node.getComponents(Sprite).length === 1 && node.getComponents(Graphics).length === 0", source)
        self.assertIn("renderer === node.getComponent(Graphics)", source)
        self.assertIn("renderer === node.getComponent(Sprite)", source)
        self.assertIn("let graphics = this._graphics = this.node.getComponent(Graphics)", sdk)
        self.assertIn("let sprite = this._sprite = this.node.getComponent(Sprite)", sdk)
        self.assertIn("function maskBackingMatches(node: Node, mask: Mask, renderer: UIRenderer, requireResolvedCache: boolean)", source)
        self.assertIn("maskBackingMatches(node, mask, renderer, false)", source)
        self.assertIn("maskBackingMatches(node, mask, expectedBackingRenderer, runtimeSuppressionExpected)", source)
        self.assertIn("if (requireResolvedCache) return false", source)


if __name__ == "__main__":
    unittest.main()
