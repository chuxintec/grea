import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SDK = Path("/Applications/Cocos/Creator/3.8.8/CocosCreator.app/Contents/Resources/resources/3d/engine")


class CreatorStaticSortSerializationTypeTests(unittest.TestCase):
    def test_sort_order_array_uses_creator_integer_primitive(self):
        presenter = (ROOT / "src/monkey/targets/CreatorStaticSortQueueProxyPresenter.ts").read_text()
        self.assertIn("CCInteger", presenter)
        self.assertIn("@property({ type: [CCInteger] }) public proxySortOrders: number[]", presenter)
        self.assertNotIn("@property([Number]) public proxySortOrders", presenter)

    def test_syntax_matches_installed_creator_sdk_typed_integer_array(self):
        lod_source = (SDK / "cocos/3d/lod/lodgroup-component.ts").read_text()
        self.assertIn("@type([CCInteger])", lod_source)
        attribute_source = (SDK / "cocos/core/data/utils/attribute.ts").read_text()
        self.assertIn("export const CCInteger = new PrimitiveType('Integer'", attribute_source)

    def test_nested_prefab_presenters_are_resolved_from_exact_proxy_roots(self):
        presenter = (ROOT / "src/monkey/targets/CreatorStaticSortQueueProxyPresenter.ts").read_text()
        proxy = (ROOT / "src/monkey/targets/CreatorStaticSortQueueProxy.ts").read_text()
        self.assertNotIn("nestedProxyPresenters", presenter)
        self.assertIn("@property({ type: [CCBoolean] }) public nestedProxyRootActiveBefore", presenter)
        self.assertIn("nestedRoot.getComponent(CreatorStaticSortQueueProxyPresenter)", proxy)
        self.assertIn("nestedProxyRootReadbacks.every(row => row.verified)", proxy)
        self.assertIn("nestedProxyRootReadbacks", proxy)
        self.assertIn("private serializationPrepared = false", presenter)
        self.assertIn("if (!this.serializationPrepared) this.restoreNestedProxyRoots()", presenter)
        self.assertIn("this.serializationPrepared = true", presenter)
        self.assertIn("this.disableNestedProxyRoots()", presenter)

    def test_typed_renderer_field_divergence_reports_bounded_source_keyed_diff(self):
        proxy = (ROOT / "src/monkey/targets/CreatorStaticSortQueueProxy.ts").read_text()
        self.assertIn("function boundedFingerprintDiff", proxy)
        self.assertIn("maxDifferences = 16", proxy)
        self.assertIn("const parseEmbeddedObject = (value: unknown)", proxy)
        self.assertIn("const parsedLeft = parseEmbeddedObject(left), parsedRight = parseEmbeddedObject(right)", proxy)
        self.assertIn("visit(path, parsedLeft, parsedRight)", proxy)
        self.assertIn("copyRenderer(source, proxyNode, row.sourceType, row.sourceComponentId)", proxy)
        self.assertIn("CREATOR_PROXY_TYPED_RENDERER_FIELDS_DIVERGED', type + ':' + sourceComponentId", proxy)
        self.assertIn("differences: boundedFingerprintDiff(sourceFingerprint, proxyFingerprint)", proxy)


if __name__ == "__main__":
    unittest.main()
