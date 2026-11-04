import copy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

import monkey.prefab_local_behaviors as behaviors
from monkey.prefab_local_behaviors import (
    RULE_VERSION, lower_behavior, sample_back_scale, sample_breath_cycle,
    source_scale_x, uniform_scale_xyz,
)


ROOT = Path(__file__).resolve().parents[1]


class PrefabLocalBehaviorTests(unittest.TestCase):
    def setUp(self):
        # Neutral synthetic module bytes keep private game/source payloads out
        # of the public test tree while exercising the same pin/fail-closed API.
        self.fixtures = {
            "BaseEffect": b"neutral-base-fixture: delay; tweenTime; show; reset; stopAllActions;",
            "ScaleBackEffect": b"neutral-scale-fixture: base.show.call(this,t); tweenHide; backOut; backIn; kt(1000*tweenTime);",
            "BreathEffect": b"neutral-breath-fixture: delay; tweenTime; offset; onLoad-scale; stopAllActions; quadInOut; recurse-playEffect;",
            "AutoScaleComp": b"neutral-auto-scale-fixture: initialY; statusNotchHeight; visibleSize; setScale;",
        }
        self.rules = copy.deepcopy(behaviors.SOURCES)
        for name, raw in self.fixtures.items():
            self.rules[name]["sha256"] = hashlib.sha256(raw).hexdigest()
            self.rules[name]["markers"] = (raw.split(b": ", 1)[1].split(b"; ", 1)[0],)
        self.proof = copy.deepcopy(behaviors._SCALE_BACK_SCOPE_PROOF)
        self.proof["sourceBundleSha256"] = "fixture-placeholder"
        self.proof["moduleSha256"] = {
            name: hashlib.sha256(self.fixtures[name]).hexdigest()
            for name in ("BaseEffect", "ScaleBackEffect")
        }
        self.proof["moduleSha256"]["kt"] = hashlib.sha256(b"neutral timer fixture").hexdigest()
        self.proof["astScope"] = {"id": "fixture-scope", "utf16Range": [0, 1]}
        self.proof["bindings"] = {
            "BaseEffect.Se": "fixture-scope",
            "ScaleBackEffect.Se": "fixture-scope",
            "kt": "fixture-scope",
        }
        self.patcher = patch.object(behaviors, "SOURCES", self.rules)
        self.proof_patcher = patch.object(behaviors, "_SCALE_BACK_SCOPE_PROOF", self.proof)
        self.patcher.start()
        self.proof_patcher.start()
        self.addCleanup(self.patcher.stop)
        self.addCleanup(self.proof_patcher.stop)

    def source(self, name):
        return self.fixtures[name]

    def scale_bundle(self):
        base, scale, timer = (self.source("BaseEffect"), self.source("ScaleBackEffect"), b"neutral timer fixture")
        bundle = b"prefix|" + base + b"|" + scale + b"|" + timer
        self.proof["sourceBundleSha256"] = hashlib.sha256(bundle).hexdigest()
        base_start = len(b"prefix|")
        scale_start = base_start + len(base) + 1
        timer_start = scale_start + len(scale) + 1
        self.proof["byteRanges"] = {
            "BaseEffect": [base_start, base_start + len(base)],
            "ScaleBackEffect": [scale_start, scale_start + len(scale)],
            "kt": [timer_start, len(bundle)],
        }
        self.proof["astScope"] = {"id": "fixture-scope", "utf16Range": [10, 20]}
        self.proof["bindings"] = {
            "BaseEffect.Se": "fixture-scope",
            "ScaleBackEffect.Se": "fixture-scope",
            "kt": "fixture-scope",
        }
        external = dict(self.proof, verification="externally_verified")
        return bundle, base, scale, external

    def test_breath_effect_lowers_to_both_native_targets_with_source_provenance(self):
        raw = self.source("BreathEffect")
        for target, suffix in (("unity", "BreathEffect.cs"), ("creator3.8", "BreathEffect.ts")):
            with self.subTest(target=target):
                result = lower_behavior("BreathEffect", "5f4dd/aSmJBa6/sLQlXJEBS", raw, target,
                                        {"delay": 0.45, "tweenTime": 0.8, "offset": 0.12})
                self.assertEqual(result.status, "lowered_with_gaps")
                self.assertEqual(result.rule_version, RULE_VERSION)
                self.assertEqual(result.source_sha256, hashlib.sha256(raw).hexdigest())
                self.assertTrue(result.script_path.endswith(suffix))
                self.assertEqual(result.applied_fields, ("delay", "offset", "tweenTime"))
                self.assertEqual(result.plan()["serializedValues"],
                                 {"delay": 0.45, "tweenTime": 0.8, "offset": 0.12})
                self.assertEqual(result.plan()["scriptFilename"], suffix)
                self.assertEqual(result.plan()["className"], "BreathEffect")
                self.assertEqual(result.plan()["requiredProviders"], [])
                self.assertEqual(len(result.unsupported_behaviors), 1)
                self.assertIn("stopAllActions", result.record()["unsupportedBehaviors"][0])
                self.assertTrue("quadInOut" in result.script if target != "unity" else "2f * t * t" in result.script)
                self.assertIn("onDisable" if target != "unity" else "OnDisable", result.script)
                self.assertEqual(result.record()["originalSourceSha256"], result.source_sha256)

    def test_source_identity_hash_and_semantic_variants_fail_closed(self):
        raw = self.source("BreathEffect")
        cases = (
            ("wrong class", "BreathEffect", "other-type", raw),
            ("wrong source identity", "BreathEffect", "d08bdTxpX1NbJhf6/sTgRao", raw),
            ("modified bytes", "BreathEffect", "5f4dd/aSmJBa6/sLQlXJEBS", raw + b" changed"),
            ("missing semantic marker", "BreathEffect", "5f4dd/aSmJBa6/sLQlXJEBS", raw.replace(b"quadInOut", b"linear", 1)),
        )
        for label, component, source_type, source in cases:
            with self.subTest(label=label):
                self.assertEqual(lower_behavior(component, source_type, source, "unity").status, "unsupported")

    def test_unknown_or_malformed_serialized_properties_are_rejected(self):
        raw = self.source("BreathEffect")
        self.assertIn("unsupported serialized fields", lower_behavior(
            "BreathEffect", "5f4dd/aSmJBa6/sLQlXJEBS", raw, "unity", {"callback": "update"}
        ).reason)
        self.assertIn("invalid serialized field", lower_behavior(
            "BreathEffect", "5f4dd/aSmJBa6/sLQlXJEBS", raw, "creator", {"offset": True}
        ).reason)

    def test_autoscale_without_viewport_context_is_explicitly_unsupported(self):
        result = lower_behavior("AutoScaleComp", "86fdf0LcnRPjKXp4EJh0Q2V",
                                self.source("AutoScaleComp"), "creator3.8")
        self.assertEqual(result.status, "unsupported")
        self.assertTrue(result.unsupported_behaviors)
        self.assertTrue(result.reason)
        self.assertIsNone(result.script)

    def test_autoscale_requires_provider_and_blocks_same_node_widget(self):
        raw = self.source("AutoScaleComp")
        source_type = "86fdf0LcnRPjKXp4EJh0Q2V"
        context = {"viewportProvider": "monkey.viewport-notch/1", "sameNodeComponentTypes": []}
        result = lower_behavior("AutoScaleComp", source_type, raw, "unity", native_context=context)
        self.assertEqual(result.status, "lowered")
        self.assertTrue(result.script_path.endswith("AutoScaleComp.cs"))
        self.assertEqual(result.plan()["requiredProviders"], ["monkey.viewport-notch/1"])
        self.assertEqual(result.record()["sourceEvidence"]["viewportMetrics"],
                         ["visibleSize.width", "visibleSize.height", "statusNotchHeight"])
        blocked = lower_behavior("AutoScaleComp", source_type, raw, "creator3.8",
                                 native_context={"viewportProvider": "monkey.viewport-notch/1",
                                                 "sameNodeComponentTypes": ["cc.Widget"]})
        self.assertEqual(blocked.status, "unsupported")
        self.assertIn("blocked", blocked.reason)
        for name in ("ViewportNotchProvider.cs", "ViewportNotchProvider.ts"):
            provider = (ROOT / "src/monkey/targets/behaviors" / name).read_text()
            self.assertIn("statusNotchHeight = -1", provider)
        for name in ("AutoScaleComp.cs", "AutoScaleComp.ts"):
            script = (ROOT / "src/monkey/targets/behaviors" / name).read_text()
            self.assertIn("AutoScaleComp blocked", script)
            self.assertIn("Widget", script)

    def test_scale_back_requires_full_bundle_and_rejects_caller_asserted_proof(self):
        bundle, base, scale, external = self.scale_bundle()
        fields = {"delay": 0.0, "tweenTime": 0.3, "tweenHide": True, "scaleFrom": 0.62}
        context = {"sameNodeComponentTypes": []}
        for target, suffix in (("unity", "ScaleBackEffect.cs"), ("creator3.8", "ScaleBackEffect.ts")):
            with self.subTest(target=target):
                missing = lower_behavior("ScaleBackEffect", "d08bdTxpX1NbJhf6/sTgRao", scale,
                                         target, fields, base_source_bytes=base, native_context=context)
                self.assertEqual(missing.status, "unsupported")
                asserted = lower_behavior("ScaleBackEffect", "d08bdTxpX1NbJhf6/sTgRao", scale,
                                           target, fields, base_source_bytes=base,
                                           scope_proof=external, native_context=context)
                self.assertEqual(asserted.status, "unsupported")
                self.assertIn("not source verification", asserted.reason)
                result = lower_behavior("ScaleBackEffect", "d08bdTxpX1NbJhf6/sTgRao", scale,
                                        target, fields, base_source_bytes=base,
                                        source_bundle_bytes=bundle, native_context=context)
                self.assertEqual(result.status, "lowered_with_gaps")
                self.assertTrue(result.script_path.endswith(suffix))
                self.assertEqual(result.plan()["scriptFilename"], suffix)
                self.assertEqual(result.plan()["className"], "ScaleBackEffect")
                self.assertEqual(result.plan()["serializedValues"], fields)
                proof = result.record()["sourceEvidence"]["scopeProof"]
                self.assertEqual(proof["sourceBundleSha256"], hashlib.sha256(bundle).hexdigest())
                self.assertEqual(proof["verification"], "whole_bundle_bytes_and_ranges_verified")
                self.assertIn("setTimeout", proof["ktSemantics"])
                self.assertEqual(result.record()["sourceEvidence"]["showOrder"],
                                 ["await BaseEffect.show/reset", "set scaleFrom",
                                  "start backOut tween", "await kt(1000*tweenTime)"])
                changed_bundle = bundle[:-1] + b"X"
                self.assertEqual(lower_behavior("ScaleBackEffect", "d08bdTxpX1NbJhf6/sTgRao", scale,
                                                target, fields, base_source_bytes=base,
                                                source_bundle_bytes=changed_bundle, native_context=context).status, "unsupported")
        bundle, base, scale, external = self.scale_bundle()
        widget_context = {"sameNodeComponentTypes": ["cc.Widget"],
                          "widgetAlignmentProvider": "monkey.widget-alignment/1"}
        unity_widget = lower_behavior("ScaleBackEffect", "d08bdTxpX1NbJhf6/sTgRao", scale,
                                      "unity", fields, base_source_bytes=base,
                                      source_bundle_bytes=bundle, native_context={"sameNodeComponentTypes": ["cc.Widget"]})
        self.assertEqual(unity_widget.status, "unsupported")
        bound_widget = lower_behavior("ScaleBackEffect", "d08bdTxpX1NbJhf6/sTgRao", scale,
                                      "unity", fields, base_source_bytes=base,
                                      source_bundle_bytes=bundle, native_context=widget_context)
        self.assertEqual(bound_widget.status, "lowered_with_gaps")
        self.assertEqual(bound_widget.record()["sourceEvidence"]["baseEffectWidget"], "updateAlignment called")
        self.assertEqual(bound_widget.plan()["requiredProviders"], ["monkey.widget-alignment/1"])

    def test_scale_back_native_adapters_keep_base_show_hide_order(self):
        unity = (ROOT / "src/monkey/targets/behaviors/ScaleBackEffect.cs").read_text()
        creator = (ROOT / "src/monkey/targets/behaviors/ScaleBackEffect.ts").read_text()
        for text, base_call, start, wait, zero in (
            (unity, "await base.Show(data)", "transform.localScale = Vector3.one * scaleFrom",
             "Task.Delay", "transform.localScale = Vector3.zero"),
            (creator, "await super.show(data)", "this.node.setScale(new Vec3(this.scaleFrom",
             "setTimeout", "this.node.setScale(new Vec3(0, 0, 0))"),
        ):
            self.assertLess(text.index(base_call), text.index(start))
            self.assertLess(text.index(start), text.index(wait))
            self.assertTrue("backOut" in text or "BackOut" in text)
            self.assertTrue("backIn" in text or "BackIn" in text)
            self.assertIn(zero, text)

    def test_breath_source_timing_samples_and_lifecycle_cancellation_are_bounded(self):
        points = [0, 0.35, 0.7, 1.05, 1.4, 1.7]
        values = [sample_breath_cycle(1.0, 0.1, 0.7, 0.3, t) for t in points]
        for actual, expected in zip(values, [1.0, 1.05, 1.1, 1.05, 1.0, 1.0]):
            self.assertAlmostEqual(actual, expected, places=6)
        for filename, disable in (("BreathEffect.cs", "OnDisable"), ("BreathEffect.ts", "onDisable")):
            source = (ROOT / "src/monkey/targets/behaviors" / filename).read_text()
            self.assertIn(disable, source)
            self.assertIn("StopCoroutine(cycle)" if filename.endswith(".cs") else "this.action?.stop()", source)
            self.assertNotIn("GetComponents<MonoBehaviour>", source)
            self.assertNotIn("stopAllByTarget", source)
            self.assertIn("running", source)
            self.assertIn("onEnable" if filename.endswith(".ts") else "OnEnable", source)
            self.assertIn("playEffect" if filename.endswith(".ts") else "PlayEffect", source)
            if filename.endswith(".cs"):
                self.assertIn("TweenScale(transform.localScale.x, endValue, tweenTime)", source)
                self.assertIn("if (running == value) return;", source)
                self.assertNotIn("transform.localScale = Vector3.zero", source)
            else:
                self.assertIn(".to(this.tweenTime, { scale: new Vec3(this.endValue", source)
                self.assertIn("if (this._running === value) return;", source)
                self.assertNotIn("this.node.setScale(new Vec3(0, 0, 0))", source)
        held_on_disable = values[1]
        self.assertAlmostEqual(held_on_disable, 1.05)
        # Re-enabling resumes from the current scale toward the captured end value.
        self.assertAlmostEqual(held_on_disable + (1.1 - held_on_disable) * 0.5, 1.075)

    def test_nonuniform_source_scale_uses_x_scalar_then_uniform_xyz_on_both_targets(self):
        initial = (2.0, 3.0, 4.0)
        start = source_scale_x(initial)
        self.assertEqual(start, 2.0)
        self.assertEqual(uniform_scale_xyz(start), (2.0, 2.0, 2.0))
        # Before a tween tick, source code has only read scale.x, so the node
        # remains nonuniform; after the first write all axes use the scalar.
        self.assertEqual(initial, (2.0, 3.0, 4.0))
        half = sample_breath_cycle(start, 0.1, 0.7, 0.3, 0.35)
        end = sample_breath_cycle(start, 0.1, 0.7, 0.3, 0.7)
        self.assertEqual(uniform_scale_xyz(half), (2.05, 2.05, 2.05))
        self.assertEqual(uniform_scale_xyz(end), (2.1, 2.1, 2.1))

        for filename in ("BreathEffect.cs", "BreathEffect.ts"):
            script = (ROOT / "src/monkey/targets/behaviors" / filename).read_text()
            self.assertIn("transform.localScale.x" if filename.endswith(".cs") else "this.node.scale.x", script)
            self.assertIn("Vector3.one * scale" if filename.endswith(".cs") else "setScale(scale, scale, scale)", script)
            self.assertIn("startValue + offset" if filename.endswith(".cs") else "this.startValue + this.offset", script)

    def test_scale_back_uses_scalar_x_and_uniform_writes_for_show_and_hide(self):
        show_start = uniform_scale_xyz(0.7)
        show_half = sample_back_scale(show_start, 1.0, 0.5, outgoing=True)
        show_end = sample_back_scale(show_start, 1.0, 1.0, outgoing=True)
        self.assertEqual(show_start, (0.7, 0.7, 0.7))
        self.assertTrue(show_half[0] > 1.0)
        self.assertEqual(show_half[0], show_half[1])
        self.assertEqual(show_end, (1.0, 1.0, 1.0))

        hide_half = sample_back_scale((2.0, 3.0, 4.0), 0.7, 0.5, outgoing=False)
        hide_end = sample_back_scale((2.0, 3.0, 4.0), 0.7, 1.0, outgoing=False)
        self.assertEqual(hide_half[0], hide_half[1])
        self.assertEqual(hide_half[1], hide_half[2])
        for axis in hide_end:
            self.assertAlmostEqual(axis, 0.7, places=6)

        for filename in ("ScaleBackEffect.cs", "ScaleBackEffect.ts"):
            script = (ROOT / "src/monkey/targets/behaviors" / filename).read_text()
            self.assertIn("transform.localScale.x" if filename.endswith(".cs") else "node.scale.x", script)
            self.assertIn("Vector3.one * scale" if filename.endswith(".cs") else "setScale(scale, scale, scale)", script)
        for filename in ("AutoScaleComp.cs", "AutoScaleComp.ts"):
            script = (ROOT / "src/monkey/targets/behaviors" / filename).read_text()
            self.assertIn("new Vector3(scale, scale, scale)" if filename.endswith(".cs") else "new Vec3(scale, scale, scale)", script)


if __name__ == "__main__":
    unittest.main()
