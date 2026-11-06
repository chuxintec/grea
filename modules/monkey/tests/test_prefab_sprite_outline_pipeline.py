import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from monkey import io
from monkey.prefab_sprite_outline_materials import PROFILE, PROGRAM_HASH, STAGE_HASHES
from monkey.prefab_sprite_outline_pipeline import attach, emit, emit_attached


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    raw = io.encoded(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


class SpriteOutlinePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.root = Path(self.temp.name)
        self.spec = {
            "schema": "monkey-prefab-sprite-outline-binding/1",
            "profile": PROFILE,
            "programCanonicalSha256": PROGRAM_HASH,
            "programStageCanonicalSha256": STAGE_HASHES,
            "materialSourceId": "fixture:material",
            "sourceManifestSha256": "c" * 64,
            "module": "FixtureOutline",
            "properties": {"outlineColor": [0.2, 0.6, 0.9, 1.0],
                           "outlineTextureSize": [128.0, 128.0],
                           "outlineWidth": 5.0, "fillAlpha": 0.0, "alphaThreshold": 0.01},
            "sourceComponentIds": ["fixture:prefab#4"],
            "spriteBindings": [{"sourceId": "fixture:prefab#4", "spriteFrameSourceId": "fixture:frame"}],
            "unity": {"shaderPath": "Assets/Shader.shader", "shaderGuid": "a" * 32,
                      "materialPath": "Assets/Material.mat", "materialGuid": "b" * 32},
            "creator": {"effectPath": "assets/effect.effect", "effectUuid": "11111111-1111-1111-1111-111111111111",
                        "materialPath": "assets/material.mtl", "materialUuid": "22222222-2222-2222-2222-222222222222",
                        "materialMetaPath": "assets/material.mtl.meta"},
        }
        self.manifest_sha = "c" * 64
        self.source = self.root / "source-stage"
        self.source.mkdir()
        self.plan = {
            "targetProfile": "unity-6000.6.2f1-ugui",
            "sourceManifestSha256": self.manifest_sha,
            "nodes": [{"sourceId": "fixture:prefab#node4"}],
            "components": [{"sourceId": "fixture:prefab#4", "type": "cc.Sprite",
                            "node": "fixture:prefab#node4", "spriteFrame": "fixture:frame",
                            "materials": ["fixture:material"], "convertible": False,
                            "serializedColor": [1, 1, 1, 1]}],
            "spriteFrames": [{"sourceId": "fixture:frame", "size": [128, 128]}],
            "diagnostics": [
                {"sourceId": "fixture:prefab#4", "code": "CUSTOM_MATERIAL_HANDOFF"},
                {"sourceId": "fixture:prefab#4", "code": "COMPONENT_HANDOFF"},
                {"sourceId": "fixture:prefab#other", "code": "UNRELATED_GAP"},
            ],
        }
        self.plan_raw = write_json(self.source / "plan.json", self.plan)
        extra = b"preserve-me\n"
        (self.source / "source-evidence.txt").write_bytes(extra)
        write_json(self.source / "manifest.json", {"schema": "fixture-stage/1", "files": [
            {"path": "plan.json", "sha256": sha(self.plan_raw), "bytes": len(self.plan_raw)},
            {"path": "source-evidence.txt", "sha256": sha(extra), "bytes": len(extra)},
        ]})
        self.binding = self.root / "binding-plan.json"
        self.payload = b"source-profiled shader payload\n"
        self.binding_plan = {"schema": "monkey-prefab-sprite-outline-plan/1", "spec": self.spec,
                             "ownedFiles": [{"path": "Assets/Game/Shader.shader",
                                             "byteLength": len(self.payload), "sha256": sha(self.payload),
                                             "contentBase64": base64.b64encode(self.payload).decode("ascii")},
                                            {"path": "assets/resources/Shaders/Fixture.effect",
                                             "byteLength": len(self.payload), "sha256": sha(self.payload),
                                             "contentBase64": base64.b64encode(self.payload).decode("ascii")}]}
        self.binding_raw = write_json(self.binding, self.binding_plan)

    def tearDown(self):
        self.temp.cleanup()

    def test_attach_preserves_sprite_fields_and_unrelated_diagnostics(self):
        out = self.root / "attached"
        report = attach(self.source / "plan.json", sha(self.plan_raw), self.binding, sha(self.binding_raw), out)
        result = json.loads((out / "plan.json").read_text())
        component = result["components"][0]
        self.assertTrue(component["convertible"])
        self.assertEqual(component["nativeSpriteOutlineMaterialSourceId"], "fixture:material")
        self.assertEqual(component["spriteFrame"], "fixture:frame")
        self.assertEqual(component["serializedColor"], [1, 1, 1, 1])
        self.assertEqual([row["code"] for row in result["diagnostics"]], ["UNRELATED_GAP"])
        self.assertEqual((out / "source-evidence.txt").read_bytes(), b"preserve-me\n")
        self.assertEqual(report["convertedSpriteCount"], 1)
        self.assertEqual(report["nativeCompilation"], "not_run")

    def test_attach_rejects_frame_geometry_that_does_not_match_profile(self):
        bad_plan = dict(self.plan)
        bad_plan["spriteFrames"] = [{"sourceId": "fixture:frame", "size": [64, 128]}]
        source = self.root / "bad-source"
        source.mkdir()
        raw = write_json(source / "plan.json", bad_plan)
        write_json(source / "manifest.json", {"files": [{"path": "plan.json", "sha256": sha(raw), "bytes": len(raw)}]})
        with self.assertRaisesRegex(ValueError, "outlineTextureSize differs"):
            attach(source / "plan.json", sha(raw), self.binding, sha(self.binding_raw), self.root / "reject")

    def test_emit_copies_payload_helpers_and_deterministic_unity_meta(self):
        plan_root = self.root / "repo"
        source_path = plan_root / "owned/shader.bin"
        source_path.parent.mkdir(parents=True)
        source_path.write_bytes(self.payload)
        self.binding_plan["ownedFiles"][0]["sourcePath"] = "owned/shader.bin"
        self.binding_plan["ownedFiles"][0].pop("contentBase64")
        self.binding_raw = write_json(self.binding, self.binding_plan)
        out = self.root / "overlay"
        report = emit(self.binding, sha(self.binding_raw), plan_root, "unity", out)
        self.assertEqual((out / "Assets/Game/Shader.shader").read_bytes(), self.payload)
        helper = out / "Assets/Game/Editor/Conversion/SpriteOutline/UnitySpriteOutlineImporter.cs"
        self.assertTrue(helper.is_file())
        meta = Path(str(helper) + ".meta").read_text()
        self.assertRegex(meta, r"(?m)^guid: [0-9a-f]{32}$")
        hook = json.loads((out / "sprite-outline-hook.json").read_text())
        self.assertEqual(hook["planField"], "spriteOutlineBinding")
        self.assertEqual(report["nativeAssetCreation"], "pending-editor")
        self.assertEqual(report["shaderCompilation"], "not_run")

    def test_emit_creator_overlay_includes_stage_hooks_and_effect_payload(self):
        plan_root = self.root / "creator-repo"
        source_path = plan_root / "owned/effect.bin"
        source_path.parent.mkdir(parents=True)
        self.payload = b"creator effect payload\n"
        source_path.write_bytes(self.payload)
        self.binding_plan["ownedFiles"] = [{"path": "assets/resources/Shaders/FixtureOutline.effect",
                                             "sourcePath": "owned/effect.bin",
                                             "byteLength": len(self.payload), "sha256": sha(self.payload)}]
        self.binding_raw = write_json(self.binding, self.binding_plan)
        out = self.root / "creator-overlay"
        report = emit(self.binding, sha(self.binding_raw), plan_root, "creator", out)
        self.assertEqual((out / "assets/resources/Shaders/FixtureOutline.effect").read_bytes(), self.payload)
        self.assertTrue((out / "extensions/monkey-import/sprite-outline-importer.js").is_file())
        self.assertTrue((out / "extensions/monkey-import/sprite-outline-material-bindings.js").is_file())
        hook = json.loads((out / "sprite-outline-hook.json").read_text())
        self.assertEqual(hook["target"], "creator")
        self.assertIn("createMaterial", hook["prepare"])
        self.assertEqual(report["target"], "creator")

    def _attached_stage(self, target="unity"):
        source = self.source
        if target == "creator":
            source = self.root / "creator-source"
            source.mkdir()
            self.plan["targetProfile"] = "cocos-3.8.8"
            raw = write_json(source / "plan.json", self.plan)
            extra = b"preserve-me\n"
            (source / "source-evidence.txt").write_bytes(extra)
            write_json(source / "manifest.json", {"schema": "fixture-stage/1", "files": [
                {"path": "plan.json", "sha256": sha(raw), "bytes": len(raw)},
                {"path": "source-evidence.txt", "sha256": sha(extra), "bytes": len(extra)},
            ]})
            plan_raw = raw
        else:
            plan_raw = self.plan_raw
        out = self.root / ("attached-" + target)
        attach(source / "plan.json", sha(plan_raw), self.binding, sha(self.binding_raw), out)
        return out

    def test_emit_attached_writes_only_pinned_new_files_into_existing_export(self):
        stage = self._attached_stage()
        output = self.root / "owned-candidate"
        output.mkdir()
        result = emit_attached(stage, stage, output)
        copied = {row["path"]: row for row in result["files"]}
        self.assertIn("Assets/Game/Shader.shader", copied)
        self.assertIn("Assets/Game/Editor/Conversion/SpriteOutline/UnitySpriteOutlineImporter.cs", copied)
        self.assertIn("Assets/Game/Editor/Conversion/SpriteOutline/UnitySpriteOutlineImporter.cs.meta", copied)
        self.assertEqual((output / "Assets/Game/Shader.shader").read_bytes(), self.payload)
        self.assertFalse((output / "manifest.json").exists())
        self.assertFalse(result["candidateManifestUpdated"])

    def test_emit_attached_rejects_collisions_before_writing_any_outline_file(self):
        stage = self._attached_stage()
        output = self.root / "collision-candidate"
        output.mkdir()
        target = output / "Assets/Game/Shader.shader"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"keep-this")
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            emit_attached(stage, stage, output)
        self.assertEqual(target.read_bytes(), b"keep-this")
        self.assertFalse((output / "Assets/Game/Editor/Conversion/SpriteOutline/UnitySpriteOutlineImporter.cs").exists())

    def test_attach_freezes_external_payload_so_export_needs_no_live_repo_file(self):
        source_root = self.root / "external-repo"
        source_root.mkdir()
        payload = source_root / "shader.payload"
        payload.write_bytes(self.payload)
        self.binding_plan["ownedFiles"][0].pop("contentBase64")
        self.binding_plan["ownedFiles"][0]["sourcePath"] = "shader.payload"
        self.binding_raw = write_json(self.binding, self.binding_plan)
        stage = self.root / "frozen-stage"
        attach(self.source / "plan.json", sha(self.plan_raw), self.binding, sha(self.binding_raw), stage,
               plan_root=source_root)
        payload.unlink()
        output = self.root / "frozen-output"
        output.mkdir()
        emitted = emit_attached(stage, stage, output)
        shader = output / "Assets/Game/Shader.shader"
        self.assertEqual(shader.read_bytes(), self.payload)
        self.assertTrue(any(row["path"] == "Assets/Game/Shader.shader" for row in emitted["files"]))

    def test_attach_emits_self_contained_creator_payload_and_helpers(self):
        stage = self._attached_stage("creator")
        attached = json.loads((stage / "plan.json").read_text())
        self.assertEqual(attached["spriteOutlineBindingSource"]["target"], "creator")
        payloads = attached["spriteOutlineBindingSource"]["ownedFiles"]
        self.assertTrue(any(row["targetPath"] == "extensions/monkey-import/sprite-outline-importer.js" for row in payloads))
        output = self.root / "creator-owned-candidate"
        output.mkdir()
        result = emit_attached(stage, stage, output)
        self.assertEqual(result["target"], "creator")
        self.assertTrue((output / "extensions/monkey-import/sprite-outline-importer.js").is_file())
        self.assertTrue((output / "assets/resources/Shaders/Fixture.effect").is_file())
        self.assertFalse((output / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
