from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from monkey.source_system_font_preparation import generate, prepare  # noqa: E402
from monkey.sources.compiled import ParseError  # noqa: E402


PROFILE = "cocos-2.4.15-bundle"
SCHEMA = "monkey-source-system-font-preparation/1"


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


class SourceSystemFontPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="source-system-font-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.ir_path = self.root / "ir.json"
        self.manifest_path = self.root / "source-manifest.json"
        self.request_path = self.root / "request.json"
        self.manifest_raw = encoded({"sourceProfile": PROFILE, "sourceVersion": "2.4.15"})
        self.manifest_path.write_bytes(self.manifest_raw)
        self.ir_raw = encoded({
            "sourceProfile": PROFILE,
            "sourceManifestSha256": hashlib.sha256(self.manifest_raw).hexdigest(),
            "components": [],
        })
        self.ir_path.write_bytes(self.ir_raw)
        self._write_request()

    def _write_request(self, *, ir_hash=None, schema=SCHEMA, profile=None):
        ir_hash = ir_hash or hashlib.sha256(self.ir_raw).hexdigest()
        request = {
            "schema": schema,
            "schemaVersion": 1,
            "ir": {"path": str(self.ir_path), "sha256": ir_hash},
            "sourceManifest": {
                "path": str(self.manifest_path),
                "sha256": hashlib.sha256(self.manifest_raw).hexdigest(),
            },
        }
        if profile is not None:
            doc = json.loads(self.ir_raw)
            doc["sourceProfile"] = profile
            self.ir_raw = encoded(doc)
            self.ir_path.write_bytes(self.ir_raw)
            request["ir"]["sha256"] = hashlib.sha256(self.ir_raw).hexdigest()
        self.request_path.write_bytes(encoded(request))
        self.request_sha = hashlib.sha256(self.request_path.read_bytes()).hexdigest()

    def _resolution(self):
        return SimpleNamespace(status="resolved", record={
            "schema": "monkey-macos-system-font-resolution/1",
            "status": "resolved",
            "targetOS": "macOS",
            "targetOSVersion": "test-host",
            "sourceOSIdentityVerified": False,
            "visualEquivalent": False,
            "sourceDefaultEvidence": {"sourceProfile": PROFILE, "sourceVersion": "2.4.15"},
            "sourceSample": {
                "frozenInputs": {
                    "ir": {"path": str(self.ir_path), "sha256": hashlib.sha256(self.ir_path.read_bytes()).hexdigest()},
                    "sourceManifest": {"path": str(self.manifest_path), "sha256": hashlib.sha256(self.manifest_path.read_bytes()).hexdigest()},
                },
            },
        })

    def _binding(self, status="prepared", static_required=False):
        fonts = [{"populationMode": "StaticSDFRequired" if static_required else "DynamicOS"}]
        return SimpleNamespace(status=status, record={"status": status, "systemFonts": {"fonts": fonts}})

    def test_dynamic_preparation_writes_pinned_receipts_and_no_static_plan(self):
        out = self.root / "out-dynamic"
        with patch("monkey.source_system_font_preparation.resolve_ir_macos_system_font_files", return_value=self._resolution()), \
                patch("monkey.source_system_font_preparation.prepare_unity_system_fonts", return_value=self._binding()):
            result = prepare(self.request_path, self.request_sha, out)
        self.assertEqual(result.status, "prepared")
        self.assertTrue((out / "resolution.json").is_file())
        self.assertTrue((out / "unity-system-font-binding.json").is_file())
        self.assertFalse((out / "static-sdf-plan.json").exists())
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertFalse(manifest["sourceOSIdentityVerified"])
        self.assertFalse(manifest["visualEquivalent"])
        self.assertEqual(manifest["inputs"]["ir"]["sha256"], hashlib.sha256(self.ir_raw).hexdigest())

    def test_static_population_is_explicitly_waiting_for_generation(self):
        out = self.root / "out-static"
        plan = SimpleNamespace(status="prepared", record={"schema": "monkey-unity-coretext-static-sdf-plan/1", "status": "prepared"})
        with patch("monkey.source_system_font_preparation.resolve_ir_macos_system_font_files", return_value=self._resolution()), \
                patch("monkey.source_system_font_preparation.prepare_unity_system_fonts", return_value=self._binding(static_required=True)), \
                patch("monkey.source_system_font_preparation.prepare_static_coretext_sdf_plan", return_value=plan):
            result = prepare(self.request_path, self.request_sha, out)
        self.assertEqual(result.status, "needs_static_generation")
        self.assertTrue((out / "static-sdf-plan.json").is_file())
        self.assertEqual(result.record["nextAction"]["code"], "GENERATE_STATIC_SDF_INPUTS")
        self.assertFalse((out / "glyph-atlas.png").exists())

    def test_explicit_population_policy_preserves_original_coretext_receipt(self):
        request=json.loads(self.request_path.read_bytes())
        request['unityPopulationPolicy']='coretext-static-fallbacks-v1'
        self.request_path.write_bytes(encoded(request))
        request_sha=hashlib.sha256(self.request_path.read_bytes()).hexdigest()
        original=self._resolution()
        out=self.root/'explicit-static-policy'
        with patch('monkey.source_system_font_preparation.resolve_ir_macos_system_font_files',return_value=original), \
                patch('monkey.source_system_font_preparation.prepare_unity_system_fonts',return_value=self._binding()):
            result=prepare(self.request_path,request_sha,out)
        raw=json.loads((out/'coretext-resolution.json').read_bytes())
        derived=json.loads((out/'resolution.json').read_bytes())
        self.assertEqual(raw,original.record)
        self.assertNotIn('unityPopulationPolicy',raw)
        self.assertEqual(derived['unityPopulationPolicy'],'coretext-static-fallbacks-v1')
        self.assertEqual(derived['unityPopulationPolicyRequestSha256'],request_sha)
        self.assertEqual(derived['coreTextResolutionSha256'],hashlib.sha256((out/'coretext-resolution.json').read_bytes()).hexdigest())
        self.assertEqual(result.record['unityPopulationPolicy'],'coretext-static-fallbacks-v1')

    def test_resolver_needs_action_is_preserved_without_binding(self):
        out = self.root / "out-needs-action"
        result_record = {"schema": "monkey-macos-system-font-resolution/1", "status": "needs_action", "reason": "No eligible labels"}
        unresolved = SimpleNamespace(status="needs_action", record=result_record)
        with patch("monkey.source_system_font_preparation.resolve_ir_macos_system_font_files", return_value=unresolved):
            result = prepare(self.request_path, self.request_sha, out)
        self.assertEqual(result.status, "needs_action")
        self.assertTrue((out / "resolution.json").is_file())
        self.assertFalse((out / "unity-system-font-binding.json").exists())
        self.assertIn("SOURCE_FONT_RESOLUTION_NEEDS_ACTION", [d["code"] for d in result.record["diagnostics"]])

    def test_request_and_input_hashes_fail_before_native_resolver(self):
        with patch("monkey.source_system_font_preparation.resolve_ir_macos_system_font_files") as resolver:
            with self.assertRaises(ParseError):
                prepare(self.request_path, "0" * 64, self.root / "bad-request-hash")
            self._write_request(ir_hash="0" * 64)
            with self.assertRaises(ParseError):
                prepare(self.request_path, self.request_sha, self.root / "bad-ir-hash")
        resolver.assert_not_called()

    def test_wrong_source_profile_fails_before_native_resolver(self):
        self._write_request(profile="cocos-3.8-bundle")
        with patch("monkey.source_system_font_preparation.resolve_ir_macos_system_font_files") as resolver:
            with self.assertRaises(ParseError):
                prepare(self.request_path, self.request_sha, self.root / "bad-profile")
        resolver.assert_not_called()

    def test_input_mutation_during_resolver_is_reported_and_receipt_retained(self):
        out = self.root / "out-mutated"

        def mutate_and_resolve(ir_path, manifest_path):
            self.ir_path.write_bytes(self.ir_raw + b" ")
            return self._resolution()

        with patch("monkey.source_system_font_preparation.resolve_ir_macos_system_font_files", side_effect=mutate_and_resolve):
            result = prepare(self.request_path, self.request_sha, out)
        self.assertEqual(result.status, "needs_action")
        self.assertTrue((out / "resolution.json").is_file())
        self.assertEqual(result.record["diagnostics"][0]["code"], "SOURCE_FONT_INPUT_CHANGED")

    def test_existing_output_is_never_overwritten(self):
        out = self.root / "existing"
        out.mkdir()
        marker = out / "manual.txt"
        marker.write_text("keep")
        with patch("monkey.source_system_font_preparation.resolve_ir_macos_system_font_files") as resolver:
            with self.assertRaises(ParseError):
                prepare(self.request_path, self.request_sha, out)
        resolver.assert_not_called()
        self.assertEqual(marker.read_text(), "keep")

    def _write_static_preparation(self):
        prep_root = self.root / "preparation"
        prep_root.mkdir()
        plan_path = prep_root / "static-sdf-plan.json"
        binding_path = prep_root / "unity-system-font-binding.json"
        resolution_path = prep_root / "resolution.json"
        face_id = "coretext-static-sdf-0123456789abcdef01234567"
        resolution_sha = "a" * 64
        font_file_sha = "f" * 64
        glyph = {"unicode": 65, "codepoint": "U+0041", "character": "A"}
        face = {
            "assetId": face_id,
            "targetFamily": "Example Sans",
            "targetStyleName": "Regular",
            "targetPostScriptName": "ExampleSans-Regular",
            "targetVariationAxes": {},
            "targetSystemFontFileSha256": font_file_sha,
            "sourceLabelIds": ["label-source-1"],
            "requiredGlyphs": [glyph],
            "generationMode": "CoreTextRasterizedStaticSDF",
            "sourceOnly": True,
            "fontBytesCopiedOrExported": False,
            "fontFileDistribution": "none",
        }
        plan = {
            "schema": "monkey-unity-coretext-static-sdf-plan/1",
            "status": "prepared",
            "targetOS": "macOS",
            "targetOSVersion": "15.0",
            "targetOSBuild": None,
            "resolutionReceiptSha256": resolution_sha,
            "sourceOSIdentityVerified": False,
            "visualEquivalent": False,
            "systemFonts": [face],
        }
        spec = {
            "assetId": face_id,
            "familyName": "Example Sans",
            "styleName": "Regular",
            "populationMode": "StaticSDFRequired",
            "targetPostScriptName": "ExampleSans-Regular",
            "targetVariationAxes": {},
            "targetVariationAxesJson": "{}",
            "targetSystemFontFileSha256": font_file_sha,
            "sourceLabelIds": ["label-source-1"],
            "requiredGlyphs": [glyph],
        }
        binding = {
            "schema": "monkey-unity-system-fonts/1",
            "status": "prepared",
            "systemFonts": {"resolutionReceiptSha256": resolution_sha, "fonts": [spec]},
        }
        resolution = {"schema": "monkey-macos-system-font-resolution/1", "status": "resolved"}
        for path, value in ((plan_path, plan), (binding_path, binding), (resolution_path, resolution)):
            path.write_bytes(encoded(value))
        outputs = {}
        for name, path in (("staticSdfPlan", plan_path), ("unitySystemFontBinding", binding_path), ("resolution", resolution_path)):
            raw = path.read_bytes()
            outputs[name] = {"path": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        prep_manifest = {
            "schema": SCHEMA,
            "schemaVersion": 1,
            "status": "needs_static_generation",
            "requestSha256": "b" * 64,
            "resolutionStatus": "resolved",
            "unityBindingStatus": "prepared",
            "staticSdfPlanStatus": "prepared",
            "sourceOSIdentityVerified": False,
            "visualEquivalent": False,
            "inputs": {
                "ir": {"path": str(self.ir_path), "bytes": len(self.ir_raw), "sha256": hashlib.sha256(self.ir_raw).hexdigest()},
                "sourceManifest": {"path": str(self.manifest_path), "bytes": len(self.manifest_raw), "sha256": hashlib.sha256(self.manifest_raw).hexdigest()},
            },
            "outputs": outputs,
        }
        preparation_path = prep_root / "manifest.json"
        preparation_path.write_bytes(encoded(prep_manifest))
        preparation_sha = hashlib.sha256(preparation_path.read_bytes()).hexdigest()
        return preparation_path, preparation_sha, plan, face, spec

    def _fake_generator(self, plan_path, generated_dir, *, corrupt_glyph=False, mutate_input=False):
        plan_raw = plan_path.read_bytes()
        plan = json.loads(plan_raw)
        face = plan["systemFonts"][0]
        glyphs = list(face["requiredGlyphs"])
        if corrupt_glyph:
            glyphs = [{"unicode": 66, "codepoint": "U+0042", "character": "B"}]
        generator = ROOT / "src/monkey/targets/GenerateCoreTextSdf.swift"
        metrics = {
            "schema": "monkey-coretext-static-sdf-glyph-metrics/1",
            "status": "generated",
            "staticPlanSha256": hashlib.sha256(plan_raw).hexdigest(),
            "generatorSourceSha256": hashlib.sha256(generator.read_bytes()).hexdigest(),
            "targetOS": plan["targetOS"],
            "targetOSVersion": plan["targetOSVersion"],
            "targetOSBuild": plan.get("targetOSBuild"),
            "resolutionReceiptSha256": plan["resolutionReceiptSha256"],
            "family": face["targetFamily"],
            "styleName": face["targetStyleName"],
            "postScriptName": face["targetPostScriptName"],
            "variationAxesCanonical": "{}",
            "fontFileSha256": face["targetSystemFontFileSha256"],
            "fontFileCopiedOrExported": False,
            "fontFileIncluded": False,
            "sourceLabelIds": face["sourceLabelIds"],
            "requiredGlyphCount": len(face["requiredGlyphs"]),
            "atlasWidth": 64,
            "atlasHeight": 64,
            "glyphs": glyphs,
        }

        def run(argv, *, capture_output, text, timeout, check):
            generated_dir.mkdir(parents=True)
            (generated_dir / "glyph-atlas.png").write_bytes(b"bounded fake atlas")
            (generated_dir / "glyph-metrics.json").write_bytes(encoded(metrics))
            if mutate_input:
                self.ir_path.write_bytes(self.ir_raw + b" ")
            return SimpleNamespace(returncode=0, stdout="generated 1 glyph", stderr="")

        return run

    def test_generate_checks_pins_stages_valid_single_face_and_does_not_import_unity(self):
        preparation_path, preparation_sha, _, _, _ = self._write_static_preparation()
        out = self.root / "generated-candidate"
        with patch("monkey.source_system_font_preparation.shutil.which", return_value=str(Path(sys.executable).resolve())), \
                patch("monkey.source_system_font_preparation.subprocess.run", side_effect=self._fake_generator(
                    preparation_path.parent / "static-sdf-plan.json", out / "generated")) as run:
            result = generate(preparation_path, preparation_sha, out, budget_seconds=123)
        self.assertEqual(result.status, "prepared")
        self.assertEqual(run.call_args.kwargs["timeout"], 123)
        self.assertEqual(result.record["stagingStatus"], "staged")
        self.assertTrue((out / "generation-receipt.json").is_file())
        self.assertTrue((out / "static-inputs-stage/Assets/Game/Content/Fonts/System/StaticSdfInputs/0123456789abcdef01234567/glyph-atlas.png").is_file())
        self.assertEqual(result.record["nextAction"]["code"], "NATIVE_STATIC_FONT_IMPORT_PENDING")
        self.assertFalse(result.record["visualEquivalent"])

    def test_generate_rejects_metrics_glyph_drift(self):
        preparation_path, preparation_sha, _, _, _ = self._write_static_preparation()
        out = self.root / "generated-drift"
        with patch("monkey.source_system_font_preparation.shutil.which", return_value=str(Path(sys.executable).resolve())), \
                patch("monkey.source_system_font_preparation.subprocess.run", side_effect=self._fake_generator(
                    preparation_path.parent / "static-sdf-plan.json", out / "generated", corrupt_glyph=True)):
            result = generate(preparation_path, preparation_sha, out)
        self.assertEqual(result.status, "needs_action")
        self.assertIn("STATIC_SDF_METRICS_MISMATCH", [item["code"] for item in result.record["diagnostics"]])
        self.assertFalse((out / "generation-receipt.json").exists())

    def test_staging_exception_preserves_generation_and_reports_needs_action(self):
        preparation_path, preparation_sha, _, _, _ = self._write_static_preparation()
        out = self.root / "generated-staging-failure"
        with patch("monkey.source_system_font_preparation.shutil.which", return_value=str(Path(sys.executable).resolve())), \
                patch("monkey.source_system_font_preparation.subprocess.run", side_effect=self._fake_generator(
                    preparation_path.parent / "static-sdf-plan.json", out / "generated")), \
                patch("monkey.source_system_font_preparation.prepare_static_inputs", side_effect=OSError("stage unavailable")):
            result = generate(preparation_path, preparation_sha, out)
        self.assertEqual(result.status, "needs_action")
        self.assertEqual(result.record["staticInputsStaging"]["reason"], "stage unavailable")
        self.assertTrue((out / "generation-receipt.json").is_file())
        self.assertTrue((out / "manifest.json").is_file())

    def test_generate_rejects_preparation_file_drift_before_swift(self):
        preparation_path, preparation_sha, _, _, _ = self._write_static_preparation()
        binding_path = preparation_path.parent / "unity-system-font-binding.json"
        binding_path.write_bytes(binding_path.read_bytes() + b" ")
        with patch("monkey.source_system_font_preparation.subprocess.run") as run:
            with self.assertRaises(ParseError):
                generate(preparation_path, preparation_sha, self.root / "generated-changed")
        run.assert_not_called()

    def test_generate_rejects_source_input_drift_after_swift(self):
        preparation_path, preparation_sha, _, _, _ = self._write_static_preparation()
        out = self.root / "generated-input-drift"
        with patch("monkey.source_system_font_preparation.shutil.which", return_value=str(Path(sys.executable).resolve())), \
                patch("monkey.source_system_font_preparation.subprocess.run", side_effect=self._fake_generator(
                    preparation_path.parent / "static-sdf-plan.json", out / "generated", mutate_input=True)):
            result = generate(preparation_path, preparation_sha, out)
        self.assertEqual(result.status, "needs_action")
        self.assertIn("SOURCE_FONT_PREPARATION_CHANGED", [item["code"] for item in result.record["diagnostics"]])


if __name__ == "__main__":
    unittest.main()
