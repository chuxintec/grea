import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from monkey.prefab_static_animation import (
    build_prefab_static_animation_bindings,
    plan_source_asset_animation_clips,
    prepare_static_animation_assets,
    resolve_source_clip_native_assets,
    verify_prefab_static_animation_readback,
)


class PrefabStaticAnimationTests(unittest.TestCase):
    def setUp(self):
        self.component_id = "fixture:prefab#4/components/0"
        self.node_id = "fixture:prefab#4"
        self.clip_id = "fixture:clip"
        self.component = {
            "sourceId": self.component_id,
            "node": self.node_id,
            "type": "cc.Animation",
            "clips": [self.clip_id],
            "defaultClip": self.clip_id,
            "enabled": True,
            "playOnLoad": False,
        }
        self.ir = {"components": [self.component]}
        self.source_manifest = {"assets": [{
            "sourceId": self.clip_id,
            "kind": "cc.AnimationClip",
            "bundle": "fixture",
            "key": "fixture-clip-key",
            "importPath": "import/clip.pack.json",
            "logicalPath": "Animations/Idle",
            "index": 7,
            "native": None,
            "document": {"root": 0, "instances": [{
                "__type__": "cc.AnimationClip",
                "_name": "Idle",
                "_duration": 0,
                "curveData": {"props": {"scale": [
                    {"frame": 0, "value": [1, 1, 1]},
                ]}},
            }]},
        }]}
        self.animation = {
            "id": self.clip_id + "@" + self.component_id,
            "name": "Idle",
            "duration": 0,
            "convertible": False,
            "partial": True,
            "tracks": [{"property": "scale.x", "keys": [{"time": 0, "value": 1}]}],
            "gaps": [{"code": "ANIMATION_TIMING_UNSUPPORTED"}],
        }

    def test_zero_duration_partial_clip_can_bind_real_native_asset_and_remains_partial(self):
        native = {
            "path": "Assets/Animations/Idle.anim",
            "guid": "a" * 32,
            "assetSha256": "b" * 64,
            "nativeType": "AnimationClip",
            "contentReadbackStatus": "verified",
        }
        result = build_prefab_static_animation_bindings(
            self.ir, [self.animation], self.source_manifest,
            native_assets={self.animation["id"]: native},
            target_node_ids={self.node_id: "native-node-17"},
            target_component_ids={self.component_id: "native-component-3"},
        )
        binding = result["bindings"][0]
        slot = binding["clips"][0]
        self.assertEqual(slot["nativeReferenceStatus"], "native_asset_reference_resolved")
        self.assertEqual(slot["bindingObjectType"], "AnimationClip")
        self.assertFalse(slot["nativeAsset"]["guid"] == "")
        self.assertTrue(slot["partial"])
        self.assertEqual(binding["staticReferenceStatus"], "verified_static_references")
        self.assertEqual(binding["curveCompleteness"], "partial")
        self.assertFalse(binding["nativePlaybackEnabled"])
        self.assertEqual(binding["targetComponentId"], "native-component-3")

    def test_unsupported_clip_requires_actual_source_evidence_asset_and_is_not_animationclip(self):
        evidence = {
            "path": "Assets/Game/Content/SourceEvidence/Animations/fixture.json",
            "guid": "c" * 32,
            "assetSha256": "d" * 64,
            "nativeType": "TextAsset",
        }
        result = build_prefab_static_animation_bindings(
            self.ir, [dict(self.animation, tracks=[], convertible=False)], self.source_manifest,
            source_evidence_assets={self.clip_id: evidence},
        )
        slot = result["bindings"][0]["clips"][0]
        self.assertEqual(slot["bindingObjectType"], "TextAsset")
        self.assertIsNone(slot["nativeAsset"])
        self.assertEqual(slot["sourceEvidenceAsset"]["path"], evidence["path"])
        self.assertEqual(slot["nativeReferenceStatus"], "native_asset_evidence_missing")
        self.assertEqual(result["bindings"][0]["curveCompleteness"], "partial")
        self.assertEqual(result["bindings"][0]["staticReferenceStatus"], "verified_static_references")

    def test_missing_all_object_references_stays_partial_and_never_emits_placeholder(self):
        result = build_prefab_static_animation_bindings(self.ir, [self.animation], self.source_manifest)
        slot = result["bindings"][0]["clips"][0]
        self.assertIsNone(slot["nativeAsset"])
        self.assertIsNone(slot["sourceEvidenceAsset"])
        self.assertIsNone(slot["bindingObjectType"])
        self.assertEqual(result["bindings"][0]["staticReferenceStatus"], "partial")
        self.assertFalse(result["placeholderClipsCreated"])

    def test_prepare_extracts_exact_source_object_to_jsonasset_payload(self):
        plan = {
            "sourceManifestPath": "/frozen/source-manifest.json",
            "sourceManifestSha256": "e" * 64,
            "targetProfile": "unity-6000.6.2f1",
            "components": [self.component],
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = prepare_static_animation_assets(plan, self.source_manifest, tmp)
            asset = result["assets"][0]
            self.assertEqual(asset["status"], "prepared_source_evidence_not_imported")
            self.assertEqual(asset["nativeAssetType"], "TextAsset")
            self.assertFalse(asset["runtimeCurveData"])
            payload = (Path(tmp) / asset["path"]).read_bytes()
            source_object = self.source_manifest["assets"][0]["document"]["instances"][0]
            expected = (json.dumps(source_object, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":"), allow_nan=False) + "\n").encode()
            self.assertEqual(payload, expected)
            self.assertEqual(asset["nativeAssetSha256"], hashlib.sha256(payload).hexdigest())

    def test_creator_evidence_uses_resource_root(self):
        plan = {
            "sourceManifestPath": "/frozen/source-manifest.json",
            "sourceManifestSha256": "e" * 64,
            "targetProfile": "creator-3.8.8",
            "components": [self.component],
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = prepare_static_animation_assets(plan, self.source_manifest, tmp)
            self.assertTrue(result["assets"][0]["path"].startswith("assets/resources/SourceEvidence/Animations/"))

    def test_creator_native_asset_uuid_format_is_preserved(self):
        uuid = "12345678-1234-5678-9abc-def012345678"
        result = build_prefab_static_animation_bindings(
            self.ir, [self.animation], self.source_manifest,
            native_assets={self.animation["id"]: {
                "path": "assets/resources/Animations/Idle.anim", "guid": uuid,
                "assetSha256": "f" * 64, "nativeType": "AnimationClip",
            }},
        )
        self.assertEqual(result["bindings"][0]["clips"][0]["nativeAsset"]["guid"], uuid)

    def test_rejects_invalid_native_guid_hash_and_ambiguous_source_asset(self):
        bad = {"path": "Assets/a.anim", "guid": "not-guid", "assetSha256": "x" * 64,
               "nativeType": "AnimationClip"}
        result = build_prefab_static_animation_bindings(
            self.ir, [self.animation], self.source_manifest,
            native_assets={self.animation["id"]: bad},
        )
        slot = result["bindings"][0]["clips"][0]
        self.assertEqual(slot["nativeReferenceStatus"], "native_asset_hash_invalid")

        manifest = {"assets": self.source_manifest["assets"] * 2}
        result = build_prefab_static_animation_bindings(self.ir, [self.animation], manifest)
        self.assertEqual(result["bindings"][0]["clips"][0]["sourceAssetIdentityStatus"],
                         "source_asset_identity_ambiguous")

    def test_sync_prefab_origin_maps_exact_component_and_node(self):
        sync = [{
            "componentOrigins": [{
                "instanceSourceId": "fixture:instance::sync-component-a",
                "templateSourceId": self.component_id,
            }],
            "origins": [{
                "instanceSourceId": "fixture:instance::sync-node-a",
                "templateSourceId": self.node_id,
            }],
        }]
        result = build_prefab_static_animation_bindings(
            self.ir, [self.animation], self.source_manifest,
            sync_prefab_bindings=sync,
        )
        binding = result["bindings"][0]
        self.assertEqual(binding["targetComponentId"], "fixture:instance::sync-component-a")
        self.assertEqual(binding["targetNodeId"], "fixture:instance::sync-node-a")

    def test_asset_only_plan_lowers_nonempty_source_curves_without_node_lookup(self):
        ir = {
            "sourceNames": {self.clip_id: {"sourceId": self.clip_id, "logicalPath": "Animations/Idle"}},
            "animationClips": [{
                "sourceId": self.clip_id,
                "name": "Idle",
                "duration": 0.0,
                "sample": 24,
                "wrap": "normal",
                "timingSupported": False,
                "partial": True,
                "events": [],
                "tracks": [{
                    "sourceId": self.clip_id + "@/scale.x",
                    "nodePath": "part",
                    "property": "scale.x",
                    "sourceLocation": "fixture.json#/curveData/paths/part/props/scale",
                    "keys": [{"time": 0, "value": 1, "interpolation": "linear"}],
                }],
            }],
        }
        class Naming:
            def reserve(self, requests):
                self.ids = [request[0] for request in requests]

            def path(self, sid, kind, suffix, metadata=None):
                return "Assets/Animations/Idle.anim"

        result = plan_source_asset_animation_clips(ir, [self.clip_id], "unity-6000.6.2f1", Naming())
        spec = result["clips"][0]
        self.assertTrue(spec["assetOnly"])
        self.assertIsNone(spec["root"])
        self.assertIsNone(spec["tracks"][0]["node"])
        self.assertEqual(spec["tracks"][0]["path"], "part")
        self.assertEqual(spec["tracks"][0]["nativeProperty"], "m_LocalScale.x")
        self.assertEqual(spec["tracks"][0]["keys"][0]["value"], 1)
        self.assertEqual(len(spec["tracks"]), 1)
        self.assertFalse(spec["convertible"])
        self.assertTrue(spec["partial"])
        self.assertFalse(result["nativePlaybackEnabled"])

    def test_source_id_asset_reuse_requires_equal_canonical_curves(self):
        base = {
            "sourceClipId": self.clip_id,
            "duration": 1,
            "wrap": "normal",
            "tracks": [{"path": "child", "property": "scale.x", "nativeProperty": "m_LocalScale.x",
                        "nativeType": "Transform", "keys": [{"time": 0, "value": 1, "interpolation": "linear"}]}],
        }
        a = dict(base, id=self.clip_id + "@owner-a")
        b = dict(base, id=self.clip_id + "@owner-b")
        evidence = {
            a["id"]: {"path": "Assets/a.anim", "guid": "a" * 32, "assetSha256": "b" * 64,
                       "nativeType": "AnimationClip"},
            b["id"]: {"path": "Assets/b.anim", "guid": "c" * 32, "assetSha256": "d" * 64,
                       "nativeType": "AnimationClip"},
        }
        result = resolve_source_clip_native_assets([a, b], evidence)[self.clip_id]
        self.assertEqual(result["resolution"], "canonical_curve_equivalence")
        self.assertEqual(result["equivalentPlanAnimationIds"], [a["id"], b["id"]])

        b["tracks"] = [{"path": "different-child", "property": "scale.x", "nativeProperty": "m_LocalScale.x",
                         "nativeType": "Transform", "keys": [{"time": 0, "value": 1, "interpolation": "linear"}]}]
        result = resolve_source_clip_native_assets([a, b], evidence)[self.clip_id]
        self.assertEqual(result["status"], "source_clip_native_plan_ambiguous")

    def test_strict_readback_allows_dynamic_gap_only_when_static_object_reference_is_real(self):
        native = {"path": "Assets/Game/Content/Animations/Idle.anim", "guid": "a" * 32,
                  "assetSha256": "b" * 64, "nativeType": "AnimationClip"}
        expected = build_prefab_static_animation_bindings(
            self.ir, [self.animation], self.source_manifest,
            native_assets={self.animation["id"]: native},
            target_component_ids={self.component_id: self.component_id},
            target_node_ids={self.node_id: self.node_id},
        )
        slot = expected["bindings"][0]["clips"][0]
        actual = [{
            "sourceComponentId": self.component_id,
            "targetComponentId": self.component_id,
            "staticReferenceStatus": "reference_fields_verified",
            "curveCompleteness": "partial",
            "playbackExecuted": False,
            "binding": {"status": "reference_fields_verified", "playbackExecuted": False,
                        "sourceClipOrder": [self.clip_id],
                        "clips": [{"order": 0, "sourceClipId": self.clip_id,
                                   "referenceMatches": True, "bindingObjectType": "AnimationClip"}]},
        }]
        result = verify_prefab_static_animation_readback(expected, actual)
        self.assertEqual(result["status"], "verified_static_references")
        self.assertEqual(len(result["dynamicCurveGaps"]), 1)
        actual[0]["binding"]["clips"][0]["referenceMatches"] = False
        result = verify_prefab_static_animation_readback(expected, actual)
        self.assertEqual(result["status"], "mismatch")
        self.assertTrue(result["staticReferenceFailures"])


if __name__ == "__main__":
    unittest.main()
