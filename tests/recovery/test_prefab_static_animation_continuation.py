import copy
import tempfile
import unittest
from pathlib import Path

from grea.recovery.prefab_static_animation_continuation import prepare


class StaticAnimationContinuationTests(unittest.TestCase):
    def setUp(self):
        self.component_id = "source:prefab#1/components/0"
        self.node_id = "source:prefab#1"
        self.clip_id = "source:clip"
        self.component = {
            "sourceId": self.component_id, "node": self.node_id,
            "type": "cc.Animation", "clips": [self.clip_id],
            "defaultClip": self.clip_id, "enabled": True, "playOnLoad": True,
            "convertible": False,
        }
        self.ir_component = copy.deepcopy(self.component)
        self.ir = {
            "sourceManifestSha256": "b" * 64,
            "components": [self.ir_component],
        }
        self.source_manifest = {
            "sourceProfile": "cocos-2.4.15-bundle",
            "assets": [{
                "sourceId": self.clip_id, "kind": "cc.AnimationClip",
                "bundle": "main", "key": "clip-key", "importPath": "import/clip.json",
                "logicalPath": "Animations/Idle", "index": 0,
                "document": {"root": 0, "instances": [{"__type__": "cc.AnimationClip", "_name": "Idle"}]},
            }],
        }
        self.motion = {
            "id": self.clip_id + "@" + self.component_id,
            "path": "Assets/Game/Content/Animations/Idle.anim",
            "convertible": False, "partial": True,
            "tracks": [{"path": "child", "nativeProperty": "m_LocalScale.x", "keys": []}],
        }
        self.plan = {
            "namespace": "fixture", "targetProfile": "unity-6000.6.2f1-ugui",
            "sourceProfile": "cocos-2.4.15-bundle",
            "sourceManifestPath": "/frozen/source-manifest.json",
            "sourceManifestSha256": "b" * 64,
            "sourceIrSha256": "a" * 64,
            "components": [self.component], "animations": [self.motion],
            "copies": [], "syncPrefabBindings": [],
        }

    def run_prepare(self, plan=None, ir=None, manifest=None):
        with tempfile.TemporaryDirectory() as tmp:
            result = prepare(plan or self.plan, ir or self.ir, manifest or self.source_manifest, tmp)
            payload_path = Path(tmp) / result["evidence"]["assets"][0]["path"]
            self.assertTrue(payload_path.is_file())
            return copy.deepcopy(result)

    def test_adds_disabled_static_carrier_contract_without_global_completion(self):
        result = self.run_prepare()
        plan = result["plan"]
        self.assertNotIn("staticCompletion", plan)
        self.assertTrue(plan["staticAnimationBindingsEnabled"])
        self.assertFalse(plan["staticAnimationContinuation"]["nativePlaybackEnabled"])
        self.assertFalse(plan["staticAnimationContinuation"]["nativeAnimatorEnabled"])
        self.assertEqual(plan["staticAnimationContinuation"]["clipSlotCount"], 1)
        self.assertEqual(plan["staticAnimationContinuation"]["partialOrEvidenceOnlyCurveSlotCount"], 1)
        self.assertFalse(plan["components"][0]["convertible"])
        self.assertTrue(plan["components"][0]["defaultClipKnown"])
        self.assertEqual(plan["staticAnimationEvidence"][0]["sourceClipId"], self.clip_id)
        self.assertEqual(plan["copies"][0]["sourceId"], self.clip_id + "@static-animation-evidence")
        self.assertEqual(result["continuation"]["bindings"][0]["curveStatus"], "partial_curves")

    def test_missing_source_clip_document_is_a_hard_gap(self):
        manifest = copy.deepcopy(self.source_manifest)
        manifest["assets"][0]["document"] = None
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "STATIC_ANIMATION_SOURCE_EVIDENCE_UNAVAILABLE"):
                prepare(self.plan, self.ir, manifest, tmp)

    def test_component_origin_is_exact_flattened_and_cycle_rejected(self):
        template_id = "source:template/components/0"
        instance_id = "source:instance/components/0"
        plan = copy.deepcopy(self.plan)
        plan["components"] = [dict(self.component, sourceId=instance_id)]
        plan["syncPrefabBindings"] = [{"componentOrigins": [
            {"instanceSourceId": instance_id, "templateSourceId": template_id},
            {"instanceSourceId": "source:instance2/components/0", "templateSourceId": instance_id},
        ]}]
        ir = copy.deepcopy(self.ir)
        ir["components"] = [dict(self.ir_component, sourceId=template_id)]
        result = self.run_prepare(plan, ir)
        self.assertEqual(result["plan"]["staticAnimationComponentOrigins"], [
            {"instanceSourceId": instance_id, "templateSourceId": template_id},
            {"instanceSourceId": "source:instance2/components/0", "templateSourceId": template_id},
        ])

        cyclic = copy.deepcopy(plan)
        cyclic["syncPrefabBindings"] = [{"componentOrigins": [
            {"instanceSourceId": instance_id, "templateSourceId": "source:instance2/components/0"},
            {"instanceSourceId": "source:instance2/components/0", "templateSourceId": instance_id},
        ]}]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "STATIC_ANIMATION_COMPONENT_ORIGIN_CYCLE"):
                prepare(cyclic, ir, self.source_manifest, tmp)

    def test_plan_animation_motion_is_not_rewritten_or_promoted(self):
        original = copy.deepcopy(self.plan["animations"])
        result = self.run_prepare()
        self.assertEqual(result["plan"]["animations"], original)
        self.assertFalse(result["plan"]["animations"][0]["convertible"])

    def test_source_component_fields_cannot_be_redefined_by_plan(self):
        for field, value in (("clips", []), ("defaultClip", None),
                             ("enabled", False), ("playOnLoad", False)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                changed = copy.deepcopy(self.plan)
                changed["components"][0][field] = value
                with self.assertRaisesRegex(ValueError, "STATIC_ANIMATION_COMPONENT_FIELD_CHANGED"):
                    prepare(changed, self.ir, self.source_manifest, tmp)

    def test_exact_static_component_reference_targets_animation_carrier(self):
        plan = copy.deepcopy(self.plan)
        plan["components"].append({
            "sourceId": "source:holder", "node": "source:holder-node", "type": "cc.Component",
            "staticFieldBinding": {"fields": [{
                "kind": "component_ref", "name": "animation", "sourceFieldName": "animation",
                "refValue": self.component_id, "refValues": [],
            }]},
        })
        continuation = self.run_prepare(plan)["continuation"]
        self.assertEqual(continuation["componentReferenceCount"], 1)
        self.assertEqual(continuation["componentReferences"][0]["sourceAnimationComponentId"], self.component_id)
        self.assertEqual(continuation["componentReferences"][0]["carrierType"], "NativeStaticAnimationBinding")
        self.assertFalse(continuation["componentReferences"][0]["playbackEnabled"])

    def test_source_identity_mismatch_is_rejected(self):
        ir = copy.deepcopy(self.ir)
        ir["sourceManifestSha256"] = "c" * 64
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "STATIC_ANIMATION_IR_MANIFEST_IDENTITY_MISMATCH"):
                prepare(self.plan, ir, self.source_manifest, tmp)


if __name__ == "__main__":
    unittest.main()
