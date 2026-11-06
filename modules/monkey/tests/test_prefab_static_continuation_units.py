import copy
from pathlib import Path
import tempfile
import unittest
from monkey import io
from monkey import prefab_static_continuation as continuation
from monkey.prefab_static_spine_rendering import _RENDER_HELPERS,_DERIVED_HELPER


class ContinuedRenderUnitsTests(unittest.TestCase):
    def fixture(self):
        package=Path(continuation.__file__).parent
        mapping=dict(generatorSourceSha256='a'*64,targetUnitsPerSourcePixel=1.0)
        fragment=dict(payloads=[dict(target=target,sha256=io.sha((package/source).read_bytes()))
            for source,target in (*_RENDER_HELPERS,_DERIVED_HELPER)],unitMapping=copy.deepcopy(mapping),
            moduleStage='spine_static_rendering',dataAssets=[dict(factorySpec=dict(unitMappingEvidence=copy.deepcopy(mapping)))])
        return dict(staticSpineRendering=fragment,staticSpineRenderingTargetUnits=copy.deepcopy(mapping))

    def test_reused_render_payloads_require_fresh_generator_observation(self):
        plan=self.fixture();before=copy.deepcopy(plan)
        with tempfile.TemporaryDirectory()as folder:
            stage=Path(folder).resolve();(stage/'spine_static_rendering').mkdir()
            receipt=continuation._refresh_existing_spine_generator(plan,stage)
        current=io.sha((Path(continuation.__file__).parent/'targets/UnityImporter.cs').read_bytes())
        self.assertEqual(plan['staticSpineRendering']['unitMapping']['generatorSourceSha256'],current)
        self.assertEqual(plan['staticSpineRendering']['dataAssets'][0]['factorySpec']['unitMappingEvidence']['generatorSourceSha256'],current)
        self.assertEqual(plan['staticSpineRendering']['payloads'],before['staticSpineRendering']['payloads'])
        self.assertTrue(receipt['requiresFreshNativeUnitObservation'])
        self.assertFalse(receipt['textureDecodeInvoked'])

    def test_changed_helpers_and_conflicting_generator_pins_are_refused(self):
        for mutation,code in ((lambda p:p['staticSpineRendering']['payloads'][0].update(sha256='0'*64),'HELPER_CHANGED'),
                (lambda p:p['staticSpineRenderingTargetUnits'].update(generatorSourceSha256='b'*64),'UNIT_PIN_INVALID')):
            plan=self.fixture();mutation(plan)
            with tempfile.TemporaryDirectory()as folder:
                with self.assertRaisesRegex(ValueError,code):
                    continuation._refresh_existing_spine_generator(plan,Path(folder).resolve())
