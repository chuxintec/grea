from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from monkey.io import encoded, sha
from monkey.prefab_local_behaviors import Lowering, RULE_VERSION, SOURCES
from monkey.prefab_behavior_pipeline import project_ir
from monkey.sources.compiled import ParseError


class PrefabBehaviorPipelineTests(unittest.TestCase):
    SOURCE_TYPE = "5f4dd/aSmJBa6/sLQlXJEBS"
    SOURCE_ID = "gameAsset:fixture-prefab#0/components/0"
    BUNDLE = b"synthetic static code module; the production source bundle is never copied into tests"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.root = Path(self.temp.name)
        self.source_root = self.root / "source" / "main"
        self.source_root.mkdir(parents=True)
        self.bundle_path = self.source_root / "game.js"
        self.bundle_path.write_bytes(self.BUNDLE)
        self.inspect = self.root / "inspect"
        self.normalize = self.root / "normalize"
        self.inspect.mkdir()
        self.normalize.mkdir()
        self.source_manifest_path = self.inspect / "source-manifest.json"
        self.ir_path = self.normalize / "ir.json"
        self.resource_path = self.normalize / "assets" / "preserved.bin"
        self.resource_path.parent.mkdir()
        self.resource_path.write_bytes(b"immutable normalized resource")
        self.output = self.root / "behavior-output"
        self._write_stages()
        self.module_row = {
            "name": "BreathEffect",
            "candidate_id": f"rf@{self.SOURCE_TYPE}@0",
            "confidence": "rf-regions-v1",
            "source_bytes": {"start": 0, "end": len(self.BUNDLE)},
            "sha256": sha(self.BUNDLE),
        }

    def tearDown(self):
        self.temp.cleanup()

    def _write_stages(self, raw_component=None, ir_type=None):
        if raw_component is None:
            raw_component = {"__type__": self.SOURCE_TYPE, "delay": 0.25, "_enabled": True}
        source_manifest = {
            "schemaVersion": "synthetic-source-manifest/1",
            "bundle": "gameAsset",
            "sourceProfile": "cocos-2.4.15-bundle",
            "sourceRoots": {"main": str(self.source_root)},
            "assets": [{
                "sourceId": "gameAsset:fixture-prefab",
                "logicalPath": "Prefab/UI/Fixture",
                "kind": "cc.Prefab",
                "document": {"instances": [
                    {"__type__": "cc.Node", "_components": [{"__id__": 1}]},
                    raw_component,
                ], "root": 0},
            }],
        }
        source_bytes = encoded(source_manifest)
        self.source_manifest_path.write_bytes(source_bytes)
        source_stage_manifest = {"schemaVersion": "synthetic-stage/1", "files": [{
            "path": "source-manifest.json", "sha256": sha(source_bytes), "bytes": len(source_bytes), "owner": "generated"
        }]}
        (self.inspect / "manifest.json").write_bytes(encoded(source_stage_manifest))

        ir = {
            "schemaVersion": "synthetic-ir/1",
            "sourceManifestSha256": sha(source_bytes),
            "sourceProfile": "cocos-2.4.15-bundle",
            "components": [{
                "sourceId": self.SOURCE_ID,
                "node": "gameAsset:fixture-prefab#0",
                "type": ir_type or self.SOURCE_TYPE,
                "enabled": True,
                "supported": False,
            }],
            "assets": [],
        }
        ir_bytes = encoded(ir)
        self.ir_path.write_bytes(ir_bytes)
        resource_bytes = self.resource_path.read_bytes()
        normalize_manifest = {
            "schemaVersion": "synthetic-normalize-stage/1",
            "sourceManifestSha256": sha(source_bytes),
            "sourceProfile": "cocos-2.4.15-bundle",
            "scopeMode": "selected-prefabs",
            "files": [
                {"path": "ir.json", "sha256": sha(ir_bytes), "bytes": len(ir_bytes), "owner": "generated"},
                {"path": "assets/preserved.bin", "sha256": sha(resource_bytes), "bytes": len(resource_bytes), "owner": "generated"},
            ],
        }
        (self.normalize / "manifest.json").write_bytes(encoded(normalize_manifest))

    def _lowering(self, component, source_type, module_bytes, target, fields, **kwargs):
        expected = {"delay": 0.25}
        if fields != expected:
            return Lowering("unsupported", component, target, sha(module_bytes), RULE_VERSION, (),
                            ("serialized source fields differ from the exact input",), reason="serialized source fields differ from the exact input")
        if target == "unity":
            path = "Assets/Monkey/Behaviors/BreathEffect.cs"
            script = "// synthetic test-only C# output\npublic class BreathEffect {}\n"
        else:
            path = "assets/scripts/monkey/behaviors/BreathEffect.ts"
            script = "// synthetic test-only TypeScript output\nexport class BreathEffect {}\n"
        return Lowering("lowered_with_gaps", component, target, sha(module_bytes), RULE_VERSION,
                        ("delay", "tweenTime", "offset"), ("test gap retained",), path, script,
                        field_values={"delay": 0.25, "tweenTime": 0.7, "offset": 0.1})

    def _run(self, *, source_hash=None, lowerer=None):
        bundle_hash = source_hash or sha(self.BUNDLE)
        with patch("monkey.prefab_behavior_pipeline.EXPECTED_SOURCE_BUNDLE_SHA256", bundle_hash), \
             patch("monkey.prefab_behavior_pipeline.static_code_modules", return_value=([self.module_row], None)), \
             patch("monkey.prefab_behavior_pipeline.lower_behavior", side_effect=lowerer or self._lowering):
            return project_ir(self.source_manifest_path, self.ir_path, self.bundle_path, bundle_hash, self.output)

    def test_projects_exact_serialized_fields_copies_stage_resources_and_keeps_gaps(self):
        before = sha(self.bundle_path.read_bytes())
        result = self._run()
        behavior = result["ir"]["components"][0]["nativeBehavior"]
        self.assertEqual(behavior["sourceId"], self.SOURCE_ID)
        self.assertEqual(behavior["node"], "gameAsset:fixture-prefab#0")
        self.assertEqual(behavior["sourceSerialized"]["sourceComponentType"], self.SOURCE_TYPE)
        self.assertEqual(behavior["serializedFields"], {"delay": 0.25})
        self.assertEqual(behavior["targets"]["unity"]["status"], "lowered_with_gaps")
        self.assertEqual(behavior["targets"]["creator"]["status"], "lowered_with_gaps")
        self.assertFalse(behavior["runtimeComplete"])
        self.assertEqual(len(result["emittedBehaviorScripts"]), 2)
        for emitted in result["emittedBehaviorScripts"]:
            artifact = self.output / emitted["artifactPath"]
            self.assertEqual(sha(artifact.read_bytes()), emitted["sha256"])
        self.assertEqual((self.output / "assets/preserved.bin").read_bytes(), b"immutable normalized resource")
        derived_ir = json.loads((self.output / "ir.json").read_text())
        self.assertEqual(derived_ir["components"][0]["sourceId"], self.SOURCE_ID)
        self.assertEqual(derived_ir["emittedBehaviorScripts"], result["manifest"]["emittedBehaviorScripts"])
        for emitted in derived_ir["emittedBehaviorScripts"]:
            self.assertTrue(emitted["targetPath"].startswith(
                "Assets/Game/Scripts/Presentation/Recovered/" if emitted["target"] == "unity"
                else "assets/Game/Scripts/Presentation/Recovered/"))
            self.assertEqual(sha((self.output / emitted["artifactPath"]).read_bytes()), emitted["sha256"])
        self.assertEqual(sha(self.bundle_path.read_bytes()), before)
        self.assertEqual(result["manifest"]["runtimeComplete"], False)
        self.assertEqual(result["manifest"]["status"], "partial")

    def test_scale_back_emits_exactly_pinned_shared_base_effect_dependencies(self):
        scale_type = "scaleBackFixtureType"
        base_type = "baseEffectFixtureType"
        raw = {"__type__": scale_type, "scaleFrom": 0.8}
        self._write_stages(raw, ir_type=scale_type)
        scale_row = dict(self.module_row, name="ScaleBackEffect", candidate_id=f"rf@{scale_type}@0")
        base_row = dict(self.module_row, name="BaseEffect", candidate_id=f"rf@{base_type}@0")
        source_fields = {"BaseEffect": dict(SOURCES["BaseEffect"], source_type=base_type, sha256=sha(self.BUNDLE))}
        def fake_lower(component, source_type, module_bytes, target, fields, **kwargs):
            ext = ".cs" if target == "unity" else ".ts"
            target_path = ("Assets/Monkey/Behaviors/" if target == "unity" else "assets/scripts/monkey/behaviors/") + "ScaleBackEffect" + ext
            return Lowering("lowered_with_gaps", component, target, sha(module_bytes), RULE_VERSION, (),
                            ("owned action gap",), target_path, "// synthetic ScaleBack" + ext,
                            field_values={"scaleFrom": fields.get("scaleFrom", 0.7)},
                            source_evidence={"baseSourceSha256": sha(self.BUNDLE)})
        with patch("monkey.prefab_behavior_pipeline.EXPECTED_SOURCE_BUNDLE_SHA256", sha(self.BUNDLE)),              patch.dict("monkey.prefab_behavior_pipeline.SOURCES", source_fields),              patch("monkey.prefab_behavior_pipeline.static_code_modules", return_value=([scale_row, base_row], None)),              patch("monkey.prefab_behavior_pipeline.lower_behavior", side_effect=fake_lower):
            result = project_ir(self.source_manifest_path, self.ir_path, self.bundle_path, sha(self.BUNDLE), self.output)
        scripts = result["emittedBehaviorScripts"]
        self.assertEqual(len(scripts), 4)
        helpers = [s for s in scripts if s["role"] == "shared-helper"]
        self.assertEqual({s["target"] for s in helpers}, {"unity", "creator"})
        behavior = result["ir"]["components"][0]["nativeBehavior"]
        for target in ("unity", "creator"):
            self.assertEqual(behavior["targets"][target]["status"], "lowered_with_gaps")
            self.assertEqual(behavior["targets"][target]["requiredScripts"][0]["className"], "BaseEffect")
            self.assertTrue(behavior["targets"][target]["scriptPath"].startswith(
                "Assets/Game/Scripts/Presentation/Recovered/" if target == "unity"
                else "assets/Game/Scripts/Presentation/Recovered/"))
            self.assertTrue(behavior["targets"][target]["requiredScripts"][0]["targetPath"].startswith(
                "Assets/Game/Scripts/Presentation/Recovered/" if target == "unity"
                else "assets/Game/Scripts/Presentation/Recovered/"))

    def test_distinct_source_types_cannot_claim_one_fixed_class_path(self):
        second_type = "secondSourceType"
        raw_fields = {"__type__": self.SOURCE_TYPE, "delay": 0.25}
        source_manifest = {
            "schemaVersion": "synthetic-source-manifest/1",
            "bundle": "gameAsset",
            "sourceProfile": "cocos-2.4.15-bundle",
            "sourceRoots": {"main": str(self.source_root)},
            "assets": [
                {"sourceId": "gameAsset:first", "logicalPath": "Prefab/First", "kind": "cc.Prefab",
                 "document": {"instances": [{"__type__": "cc.Node", "_components": [{"__id__": 1}]}, raw_fields], "root": 0}},
                {"sourceId": "gameAsset:second", "logicalPath": "Prefab/Second", "kind": "cc.Prefab",
                 "document": {"instances": [{"__type__": "cc.Node", "_components": [{"__id__": 1}]},
                                            {"__type__": second_type, "delay": 0.25}], "root": 0}},
            ],
        }
        source_bytes = encoded(source_manifest)
        self.source_manifest_path.write_bytes(source_bytes)
        (self.inspect / "manifest.json").write_bytes(encoded({"schemaVersion": "synthetic-stage/1", "files": [{
            "path": "source-manifest.json", "sha256": sha(source_bytes), "bytes": len(source_bytes), "owner": "generated"
        }]}))
        ir = {"schemaVersion": "synthetic-ir/1", "sourceManifestSha256": sha(source_bytes),
              "sourceProfile": "cocos-2.4.15-bundle", "components": [
                  {"sourceId": "gameAsset:first#0/components/0", "node": "gameAsset:first#0", "type": self.SOURCE_TYPE, "enabled": True, "supported": False},
                  {"sourceId": "gameAsset:second#0/components/0", "node": "gameAsset:second#0", "type": second_type, "enabled": True, "supported": False},
              ], "assets": []}
        ir_bytes = encoded(ir)
        self.ir_path.write_bytes(ir_bytes)
        normalize_manifest = json.loads((self.normalize / "manifest.json").read_text())
        normalize_manifest["sourceManifestSha256"] = sha(source_bytes)
        normalize_manifest["files"][0].update(sha256=sha(ir_bytes), bytes=len(ir_bytes))
        (self.normalize / "manifest.json").write_bytes(encoded(normalize_manifest))
        first = dict(self.module_row, name="CollisionClass", candidate_id=f"rf@{self.SOURCE_TYPE}@0")
        second = dict(self.module_row, name="CollisionClass", candidate_id=f"rf@{second_type}@0")
        with patch("monkey.prefab_behavior_pipeline.EXPECTED_SOURCE_BUNDLE_SHA256", sha(self.BUNDLE)), \
             patch("monkey.prefab_behavior_pipeline.static_code_modules", return_value=([first, second], None)), \
             patch("monkey.prefab_behavior_pipeline.lower_behavior", side_effect=self._lowering):
            with self.assertRaisesRegex(ParseError, "BEHAVIOR_CLASS_NAME_COLLISION"):
                project_ir(self.source_manifest_path, self.ir_path, self.bundle_path, sha(self.BUNDLE), self.output)
        self.assertFalse(self.output.exists())

    def test_unrecognized_source_class_is_retained_as_unsupported(self):
        unknown_type = "unmappedSourceClassId"
        raw = {"__type__": unknown_type, "someValue": 42}
        self._write_stages(raw, ir_type=unknown_type)
        module = dict(self.module_row, name="UnknownVisual", candidate_id=f"rf@{unknown_type}@0")
        with patch("monkey.prefab_behavior_pipeline.EXPECTED_SOURCE_BUNDLE_SHA256", sha(self.BUNDLE)), \
             patch("monkey.prefab_behavior_pipeline.static_code_modules", return_value=([module], None)):
            result = project_ir(self.source_manifest_path, self.ir_path, self.bundle_path, sha(self.BUNDLE), self.output)
        behavior = result["ir"]["components"][0]["nativeBehavior"]
        self.assertEqual(behavior["serializedFields"], {"someValue": 42})
        self.assertEqual(behavior["targets"]["unity"]["status"], "unsupported")
        self.assertEqual(behavior["targets"]["creator"]["status"], "unsupported")
        self.assertEqual(result["manifest"]["nativeBehaviorComponentCount"], 1)
        self.assertEqual(result["emittedBehaviorScripts"], [])

    def test_component_type_drift_disables_lowering_but_preserves_original_row(self):
        raw = {"__type__": "wrongSerializedType", "delay": 0.25}
        self._write_stages(raw)
        result = self._run()
        component = result["ir"]["components"][0]
        self.assertEqual(component["type"], self.SOURCE_TYPE)
        behavior = component["nativeBehavior"]
        self.assertEqual(behavior["targets"]["unity"]["status"], "unsupported")
        self.assertIn("type differs", behavior["targets"]["unity"]["reason"])
        self.assertEqual(result["emittedBehaviorScripts"], [])

    def test_unknown_serialized_source_field_is_not_silently_dropped(self):
        raw = {"__type__": self.SOURCE_TYPE, "delay": 0.25, "futureField": {"nested": [1, 2]}}
        self._write_stages(raw)
        result = self._run()
        component = result["ir"]["components"][0]
        behavior = component["nativeBehavior"]
        self.assertEqual(behavior["serializedFields"], {"delay": 0.25, "futureField": {"nested": [1, 2]}})
        self.assertEqual(behavior["targets"]["unity"]["status"], "unsupported")
        self.assertIn("serialized source fields differ", behavior["targets"]["unity"]["reason"])
        self.assertEqual(result["emittedBehaviorScripts"], [])

    def test_bundle_hash_drift_is_rejected_before_creating_output(self):
        self.bundle_path.write_bytes(b"changed bundle")
        with patch("monkey.prefab_behavior_pipeline.EXPECTED_SOURCE_BUNDLE_SHA256", sha(self.BUNDLE)), \
             patch("monkey.prefab_behavior_pipeline.static_code_modules", return_value=([self.module_row], None)):
            with self.assertRaisesRegex(ParseError, "SOURCE_BUNDLE_SHA_MISMATCH"):
                project_ir(self.source_manifest_path, self.ir_path, self.bundle_path, sha(self.BUNDLE), self.output)
        self.assertFalse(self.output.exists())

    def test_ir_drift_from_owning_manifest_is_rejected_before_creating_output(self):
        self.ir_path.write_bytes(self.ir_path.read_bytes() + b" ")
        with patch("monkey.prefab_behavior_pipeline.EXPECTED_SOURCE_BUNDLE_SHA256", sha(self.BUNDLE)):
            with self.assertRaises(ParseError):
                project_ir(self.source_manifest_path, self.ir_path, self.bundle_path, sha(self.BUNDLE), self.output)
        self.assertFalse(self.output.exists())

    def test_module_range_hash_mismatch_cannot_enable_lowering(self):
        corrupt_module = dict(self.module_row, sha256="0" * 64)
        with patch("monkey.prefab_behavior_pipeline.EXPECTED_SOURCE_BUNDLE_SHA256", sha(self.BUNDLE)), \
             patch("monkey.prefab_behavior_pipeline.static_code_modules", return_value=([corrupt_module], None)), \
             patch("monkey.prefab_behavior_pipeline.lower_behavior", side_effect=AssertionError("must not call lowerer")):
            result = project_ir(self.source_manifest_path, self.ir_path, self.bundle_path, sha(self.BUNDLE), self.output)
        behavior = result["ir"]["components"][0]["nativeBehavior"]
        self.assertEqual(behavior["targets"]["unity"]["status"], "unsupported")
        self.assertEqual(result["emittedBehaviorScripts"], [])
        self.assertEqual(result["manifest"]["sourceCodeModuleIndex"]["invalidModules"][0]["reason"], "source byte span hash mismatch")


if __name__ == "__main__":
    unittest.main()
