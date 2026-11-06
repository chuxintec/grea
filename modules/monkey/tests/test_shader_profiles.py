import hashlib
import tempfile
import unittest
from pathlib import Path

from monkey.shader_profiles import EFFECT_SHA256, SOURCE_ID, describe, export_profile, prepare_probe


class ShaderProfileTests(unittest.TestCase):
    def test_describe_requires_raw_identity_and_exact_program_bytes(self):
        self.assertFalse(describe({"__type__": "cc.EffectAsset"})["supported"])
        changed = {"__type__": "cc.EffectAsset", "_name": "builtin-2d-sprite", "shaders": [
            {"name": "builtin-2d-sprite|vs|fs", "glsl1": {"vert": "changed", "frag": "changed"}}
        ]}
        result = describe(changed, effect_sha256=EFFECT_SHA256)
        self.assertFalse(result["supported"])
        self.assertIn("differs from the pinned program", result["reason"])

    def test_exporter_fails_closed_without_exact_profile_and_creates_no_files(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp).resolve()
            (project / "Assets").mkdir()
            result = export_profile({"__type__": "cc.EffectAsset"}, project, "candidate", SOURCE_ID, effect_sha256=EFFECT_SHA256)
            self.assertFalse(result["written"])
            self.assertEqual(result["files"], [])
            self.assertEqual(list((project / "Assets").iterdir()), [])

    def test_prepare_probe_verifies_shader_and_material_identity_and_creates_owned_project(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            candidate = root / "candidate"
            folder = "Assets/Game/Content/Shaders/RecoveredBuiltin2DSprite"
            shader_rel = folder + "/RecoveredSprite.shader"
            shader = candidate / shader_rel
            shader.parent.mkdir(parents=True)
            payload = b"Shader \\\"Monkey/RecoveredSprite\\\" {}\n"
            shader.write_bytes(payload)
            shader_guid = "1" * 32
            material_guid = "2" * 32
            shader_meta_rel = shader_rel + ".meta"
            material_rel = folder + "/RecoveredSprite.mat"
            material_meta_rel = material_rel + ".meta"
            material = candidate / material_rel
            material.write_text(f"m_Shader: {{guid: {shader_guid}}}\n")
            (candidate / shader_meta_rel).write_text(f"guid: {shader_guid}\n")
            (candidate / material_meta_rel).write_text(f"guid: {material_guid}\n")
            manifest = {
                "status": "candidate-generated-native-validation-pending",
                "outputs": {"folder": folder, "shader": shader_rel, "shaderSha256": hashlib.sha256(payload).hexdigest(),
                            "shaderMeta": shader_meta_rel, "shaderGuid": shader_guid,
                            "material": material_rel, "materialSha256": hashlib.sha256(material.read_bytes()).hexdigest(),
                            "materialMeta": material_meta_rel, "materialGuid": material_guid},
            }
            out = root / "probe-out"
            plan = prepare_probe(candidate, manifest, SOURCE_ID, out)
            project = Path(plan["probeProject"])
            self.assertEqual(plan["status"], "prepared-not-run")
            self.assertEqual(plan["executionBudgetSeconds"], 1200)
            self.assertEqual((project / shader_rel).read_bytes(), payload)
            self.assertEqual((project / material_rel).read_bytes(), material.read_bytes())
            source = (project / "Assets/Editor/UnityShaderProbe.cs").read_text()
            self.assertIn(shader_rel, source)
            self.assertIn(material_rel, source)
            self.assertTrue((out / "probe-plan.json").is_file())
            with self.assertRaises(FileExistsError):
                prepare_probe(candidate, manifest, SOURCE_ID, out)

    def test_prepare_probe_rejects_tampered_shader_and_unowned_path(self):
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp).resolve() / "candidate"
            folder = "Assets/Game/Content/Shaders/RecoveredBuiltin2DSprite"
            shader_rel = folder + "/RecoveredSprite.shader"
            shader = candidate / shader_rel
            shader.parent.mkdir(parents=True)
            shader.write_text("tampered")
            manifest = {"status": "candidate-generated-native-validation-pending",
                        "outputs": {"folder": folder, "shader": shader_rel, "shaderSha256": "0" * 64,
                                    "shaderMeta": shader_rel + ".meta", "shaderGuid": "1" * 32,
                                    "material": folder + "/RecoveredSprite.mat", "materialSha256": "0" * 64,
                                    "materialMeta": folder + "/RecoveredSprite.mat.meta", "materialGuid": "2" * 32}}
            with self.assertRaisesRegex(ValueError, "differs from expected manifest"):
                prepare_probe(candidate, manifest, SOURCE_ID, candidate.parent / "probe")
            manifest["outputs"]["material"] = "Assets/../private-file"
            with self.assertRaisesRegex(ValueError, "owned asset layout"):
                prepare_probe(candidate, manifest, SOURCE_ID, candidate.parent / "probe2")


if __name__ == "__main__":
    unittest.main()
