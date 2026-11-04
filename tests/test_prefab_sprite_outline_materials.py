import copy
import json
import unittest
from pathlib import Path

from monkey.prefab_sprite_outline_materials import (
    PROGRAM_HASH,
    PROFILE,
    STAGE_HASHES,
    SpriteOutlineProfileError,
    _exact_effect_profile,
    _decode_source_color,
    _validate_binding_spec,
    inspect_sprite_outline,
)


class SpriteOutlineMaterialTests(unittest.TestCase):
    def test_cocos24_color_integer_uses_aabbggrr_packing(self):
        self.assertEqual(_decode_source_color({"__value_type__": 4, "values": [0xFF41F1A4]}),
                         [164 / 255, 241 / 255, 65 / 255, 1.0])

    def _spec(self):
        return {
            "schema": "monkey-prefab-sprite-outline-binding/1",
            "profile": PROFILE,
            "programCanonicalSha256": PROGRAM_HASH,
            "programStageCanonicalSha256": STAGE_HASHES,
            "materialSourceId": "fixture:material",
            "module": "Outline",
            "properties": {
                "outlineColor": [1.0, 0.25, 0.9, 0.65],
                "outlineTextureSize": [128.0, 128.0],
                "outlineWidth": 5.0,
                "fillAlpha": 0.0,
                "alphaThreshold": 0.01,
            },
            "sourceComponentIds": ["fixture:prefab#4"],
            "spriteBindings": [{"sourceId": "fixture:prefab#4", "spriteFrameSourceId": "fixture:frame"}],
            "unity": {"shaderPath": "Assets/Shader.shader", "shaderGuid": "a" * 32,
                      "materialPath": "Assets/Material.mat", "materialGuid": "b" * 32},
            "creator": {"effectPath": "assets/effect.effect", "effectUuid": "11111111-1111-1111-1111-111111111111",
                        "materialPath": "assets/material.mtl", "materialUuid": "22222222-2222-2222-2222-222222222222",
                        "materialMetaPath": "assets/material.mtl.meta"},
        }

    def test_binding_spec_accepts_only_exact_profile_and_typed_sprite_bindings(self):
        _validate_binding_spec(self._spec())
        bad = self._spec()
        bad["programCanonicalSha256"] = "0" * 64
        with self.assertRaises(SpriteOutlineProfileError):
            _validate_binding_spec(bad)
        bad = self._spec()
        bad["spriteBindings"].append(copy.deepcopy(bad["spriteBindings"][0]))
        with self.assertRaises(SpriteOutlineProfileError):
            _validate_binding_spec(bad)



if __name__ == "__main__":
    unittest.main()
