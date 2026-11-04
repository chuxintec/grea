import unittest
from unittest.mock import patch

from monkey import prefab_static_time_materials as stm


def _material(source_id="gameAsset:material-a", frame_id="gameAsset:frame-a", profile="textured-uv-flow-t0-v1"):
    return {"sourceMaterialId": source_id, "profile": profile, "sourceMaterialUuid": "01234567-89ab-cdef-0123-456789abcdef",
            "sourceMaterialDocumentSha256": "a" * 64, "effectDocumentSha256": "b" * 64,
            "sourceEffectDocumentSha256": "b" * 64, "targetShaderSha256": "c" * 64,
            "staticTimeSeconds": 0.0, "targetProperties": {"sourceTimeSeconds": 0.0,
            "sourceScalar0": 0.25, "sourceScalar1": 0, "sourceScalar2": 0, "sourceScalar3": 0,
            "sourceScalar4": 0, "sourceScalar5": 0, "sourceScalar6": 0,
            "sourceColor": [1, 1, 1, 1]},
            "unity": {"materialGuid": "0123456789abcdef0123456789abcdef",
                      "shaderGuid": "abcdef0123456789abcdef0123456789",
                      "materialPath": "Assets/Materials/a.mat", "shaderPath": "Assets/Shaders/a.shader"},
            "creator": {"materialUuid": "01234567-89ab-cdef-0123-456789abcdef",
                        "effectUuid": "abcdef01-2345-6789-abcd-ef0123456789"},
            "sourceMaterialProperties": [{"name": "speed", "kind": "scalar", "value": 0.25}],
            "sourceSpriteBindings": [{"sourceComponentId": "gameAsset:template#2/components/0",
                                      "sourcePrefabId": "gameAsset:template", "spriteFrameSourceId": frame_id,
                                      "spriteFrameUuid": "frame-a"}]}


def _plan():
    return {"sourceManifestSha256": "d" * 64, "sourceIrSha256": "e" * 64,
            "nodes": [{"sourceId": "gameAsset:template#2"}, {"sourceId": "gameAsset:owner#5"}],
            "components": [
                {"sourceId": "gameAsset:template#2/components/0", "type": "cc.Sprite", "node": "gameAsset:template#2",
                 "materials": ["gameAsset:material-a"], "spriteFrame": "gameAsset:frame-a", "mode": 0,
                 "sizeMode": 0, "trim": True, "enabled": True, "convertible": False},
                {"sourceId": "gameAsset:owner#5::sync-component-abc", "type": "cc.Sprite", "node": "gameAsset:owner#5",
                 "materials": ["gameAsset:material-a"], "spriteFrame": "gameAsset:frame-a", "mode": 0,
                 "sizeMode": 0, "trim": True, "enabled": True, "convertible": False}],
            "assets": [{"sourceId": "gameAsset:frame-a", "kind": "sprite", "path": "assets/frame.spriteframe",
                        "uuid": "frame-uuid"}],
            "syncPrefabBindings": [{"componentOrigins": [{"templateSourceId": "gameAsset:template#2/components/0",
                                                             "instanceSourceId": "gameAsset:owner#5::sync-component-abc"}]}]}


class StaticTimeMaterialTests(unittest.TestCase):
    def _readback_fixture(self):
        plan = _plan()
        plan["textures"] = [{"id": "gameAsset:frame-a", "path": "Assets/Textures/frame.png"}]
        source_material = _material()
        spec = {"schema": stm.SCHEMA, "profile": stm.PROFILE, "sourceManifestSha256": "d" * 64,
                "normalizedIrSha256": "e" * 64, "materials": [source_material]}
        attached = stm.attach(plan, spec, "unity")["staticTimeMaterials"]
        expected = attached["materials"][0]
        actual_row = {"sourceMaterialId": expected["sourceMaterialId"], "profile": expected["profile"],
            "materialGuid": expected["unity"]["materialGuid"], "shaderGuid": expected["unity"]["shaderGuid"],
            "materialLocalFileId": 2100000, "shaderLocalFileId": 4800000,
            "sourceMaterialDocumentSha256": expected["sourceMaterialDocumentSha256"],
            "sourceEffectDocumentSha256": expected["sourceEffectDocumentSha256"],
            "shaderPayloadSha256": expected["targetShaderSha256"], "staticTimeSeconds": 0.0,
            "sourcePropertiesVerified": True, "targetPropertiesVerified": True,
            "targetProperties": expected["targetProperties"],
            "boundSpriteComponentIds": [item["sourceId"] for item in expected["spriteBindings"]]}
        readback = {"schema": stm.SCHEMA, "profile": stm.PROFILE, "sourceManifestSha256": "d" * 64,
                    "normalizedIrSha256": "e" * 64, "materials": [actual_row]}
        return attached, readback, actual_row

    def test_attach_preserves_root_material_and_expands_nested_clone_bindings(self):
        plan = _plan()
        spec = {"schema": stm.SCHEMA, "profile": stm.PROFILE, "sourceManifestSha256": "d" * 64,
                "normalizedIrSha256": "e" * 64, "staticTimeSeconds": 0.0,
                "materials": [_material()]}
        result = stm.attach(plan, spec, "creator")
        row = result["staticTimeMaterials"]["materials"][0]
        self.assertEqual([binding["sourceId"] for binding in row["spriteBindings"]], [
            "gameAsset:owner#5::sync-component-abc", "gameAsset:template#2/components/0"])
        clone = next(c for c in result["components"] if "sync-component" in c["sourceId"])
        self.assertEqual(clone["nativeStaticTimeMaterialSourceId"], "gameAsset:material-a")
        self.assertEqual(clone["nativeStaticTimeSourceComponentId"], "gameAsset:template#2/components/0")
        self.assertTrue(clone["convertible"])
        self.assertEqual(plan["nodes"], _plan()["nodes"])

    def test_attach_accepts_only_explicit_frozen_material_redirect_id(self):
        plan = _plan()
        material = _material()
        plan['textures']=[{'id':'gameAsset:frame-a','path':'Assets/frame.png','guid':'f'*32}]
        alias = 'lookup:material-a'
        material['sourceMaterialReferenceIds'] = [material['sourceMaterialId'], alias]
        for component in plan['components']:
            component['materials'] = [alias]
        spec = {'schema': stm.SCHEMA, 'profile': stm.PROFILE, 'sourceManifestSha256': 'd'*64,
                'normalizedIrSha256': 'e'*64, 'materials': [material]}
        stm.attach(plan, spec, 'unity')
        self.assertTrue(all(c.get('convertible') for c in plan['components']))
        plan['components'][0]['materials'] = ['lookup:wrong']
        with self.assertRaises(stm.StaticTimeMaterialError):
            stm.attach(plan, spec, 'unity')

    def test_attach_rejects_unexportable_frame_without_relaxing_sprite_checks(self):
        plan = _plan()
        plan["assets"][0]["path"] = ""
        spec = {"schema": stm.SCHEMA, "profile": stm.PROFILE, "sourceManifestSha256": "d" * 64,
                "normalizedIrSha256": "e" * 64, "materials": [_material()]}
        with self.assertRaisesRegex(stm.StaticTimeMaterialError, "exportable target sprite"):
            stm.attach(plan, spec, "creator")

    def test_attach_rejects_component_material_or_frame_drift(self):
        plan = _plan()
        plan["components"][0]["spriteFrame"] = "gameAsset:other-frame"
        spec = {"schema": stm.SCHEMA, "profile": stm.PROFILE, "sourceManifestSha256": "d" * 64,
                "normalizedIrSha256": "e" * 64, "materials": [_material()]}
        with self.assertRaisesRegex(stm.StaticTimeMaterialError, "no longer matches"):
            stm.attach(plan, spec, "creator")

    def test_attach_source_pin_and_unknown_target_fail_closed(self):
        plan = _plan()
        spec = {"schema": stm.SCHEMA, "profile": stm.PROFILE, "sourceManifestSha256": "x" * 64,
                "normalizedIrSha256": "e" * 64, "materials": [_material()]}
        with self.assertRaisesRegex(stm.StaticTimeMaterialError, "source-manifest pin"):
            stm.attach(plan, spec, "creator")
        spec["sourceManifestSha256"] = plan["sourceManifestSha256"]
        with self.assertRaisesRegex(stm.StaticTimeMaterialError, "target must be"):
            stm.attach(plan, spec, "untrusted")

    def test_readback_checks_clock_property_native_identity_and_every_sprite(self):
        attached, readback, actual_row = self._readback_fixture()
        self.assertEqual(stm.verify(attached, readback, "unity"), [])
        actual_row["staticTimeSeconds"] = 1.0
        self.assertTrue(stm.verify(attached, readback, "unity"))
        actual_row["staticTimeSeconds"] = 0.0
        actual_row["materialLocalFileId"] = 0
        self.assertTrue(stm.verify(attached, readback, "unity"))

    def test_readback_rejects_duplicate_missing_extra_and_malformed_material_ids(self):
        attached, readback, actual_row = self._readback_fixture()
        readback["materials"].append(dict(actual_row))
        self.assertTrue(stm.verify(attached, readback, "unity"), "duplicate material identity must fail")
        readback["materials"] = []
        self.assertTrue(stm.verify(attached, readback, "unity"), "missing material identity must fail")
        extra = dict(actual_row, sourceMaterialId="fixture:unplanned-material")
        readback["materials"] = [actual_row, extra]
        self.assertTrue(stm.verify(attached, readback, "unity"), "extra material identity must fail")
        readback["materials"] = ["malformed"]
        self.assertTrue(stm.verify(attached, readback, "unity"), "malformed material identity must fail")

    def test_readback_requires_all_outer_source_pins(self):
        attached, readback, _ = self._readback_fixture()
        readback["normalizedIrSha256"] = "f" * 64
        self.assertTrue(stm.verify(attached, readback, "unity"))

    def test_unity_uv_flow_accepts_only_zero_unused_dto_slots(self):
        expected = {"sourceTimeSeconds": 0.0, "sourceScalar0": 0.1, "sourceColor": [1.0]*4}
        actual = dict(expected, **{f"sourceScalar{i}": 0.0 for i in range(1, 7)})
        self.assertTrue(stm._native_properties_close(actual, expected, "unity", "textured-uv-flow-t0-v1"))
        for key, value in [("sourceScalar1", 0.1), ("sourceScalar2", False), ("unknown", 0)]:
            bad = dict(actual); bad[key] = value
            self.assertFalse(stm._native_properties_close(bad, expected, "unity", "textured-uv-flow-t0-v1"))
        self.assertFalse(stm._native_properties_close(actual, expected, "creator", "textured-uv-flow-t0-v1"))

    def test_readback_measured_properties_allow_only_small_float_roundtrip_error(self):
        self.assertTrue(stm._properties_close({"v": [0.25, 0.5]}, {"v": [0.250001, 0.5]}))
        self.assertFalse(stm._properties_close({"v": [0.25, 0.9]}, {"v": [0.25, 0.5]}))
        self.assertFalse(stm._properties_close({"v": True}, {"v": 1}))

    def test_source_effect_contract_requires_exact_program_and_nonnegative_delay(self):
        effect = {"__type__": "cc.EffectAsset", "shaders": [{"name": "p", "defines": stm._DEFINE_SCHEMA,
                  "glsl1": {"vert": "one", "frag": "two"}, "glsl3": {"vert": "three", "frag": "four"}}],
                  "techniques": [{"passes": [{"program": "p", "blendState": {"targets": [{"blend": True}]},
                  "rasterizerState": {"cullMode": 0}, "properties": {
                      "alphaThreshold": {}, "angle": {}, "delayTime": {}, "direction": {}, "flashColor": {},
                      "flashTime": {}, "loopInterval": {}, "texture": {}, "width": {}}}]}]}
        hashes = {name: stm._canonical_stage_sha(code) for name, code in
                  (("glsl1.vert", "one"), ("glsl1.frag", "two"), ("glsl3.vert", "three"), ("glsl3.frag", "four"))}
        with patch.dict(stm.PROGRAMS, {"textured-flash-sweep-t0-v1": {
                "stageHashes": hashes, "sourceProperties": (), "staticProof": "test"}}):
            profile, _, props = stm._validate_effect(effect)
            self.assertEqual(profile, "textured-flash-sweep-t0-v1")
            self.assertEqual(set(props), stm._EFFECT_PROPERTY_NAMES[profile])
            effect["shaders"][0]["glsl1"]["frag"] = "changed program"
            with self.assertRaisesRegex(stm.StaticTimeMaterialError, "fingerprints"):
                stm._validate_effect(effect)

    def test_target_property_snapshot_refuses_negative_flash_delay(self):
        vals = {"angle": 0, "direction": 1, "width": 1, "flashTime": 1.5,
                "delayTime": -0.1, "loopInterval": 2.5, "alphaThreshold": 0.5,
                "flashColor": [1, 1, 1, 1]}
        with self.assertRaisesRegex(stm.StaticTimeMaterialError, "delayTime"):
            stm._source_property_snapshot("textured-flash-sweep-t0-v1",
                {"_techniqueData": {"0": {"defines": {"USE_TEXTURE": True}, "props": vals}}},
                {key: {"value": value} for key, value in vals.items()})

    def test_unity_material_meta_is_native_asset_meta_with_stable_guid(self):
        guid = "0123456789abcdef0123456789abcdef"
        meta = stm._unity_material_meta(guid).decode("utf-8")
        self.assertIn(f"guid: {guid}", meta)
        self.assertIn("NativeFormatImporter:", meta)
        self.assertIn("mainObjectFileID: 2100000", meta)
        self.assertNotIn("ShaderImporter:", meta)

    def test_target_material_identity_is_stable_and_unique_by_source_material(self):
        snapshot = [{"name": "speed", "kind": "scalar", "value": 0.25}]
        first = stm._target_identities("textured-uv-flow-t0-v1", snapshot, "fixture:material-a")
        again = stm._target_identities("textured-uv-flow-t0-v1", snapshot, "fixture:material-a")
        second = stm._target_identities("textured-uv-flow-t0-v1", snapshot, "fixture:material-b")
        self.assertEqual(first, again)
        self.assertNotEqual(first["unity"]["materialGuid"], second["unity"]["materialGuid"])
        self.assertNotEqual(first["creator"]["materialUuid"], second["creator"]["materialUuid"])


if __name__ == "__main__":
    unittest.main()
