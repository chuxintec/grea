import copy
import json
import tempfile
import unittest
from pathlib import Path

from grea.recovery.io import sha
from grea.recovery.spine_canvas_context_readback import (
    CONTRACT, EVIDENCE_PATH, IMPORT_PLAN_PATH, RENDERING_PATH, verify_context_evidence,
)


class SpineCanvasContextReadbackTests(unittest.TestCase):
    def _fixture(self, *, required=True):
        root = Path(tempfile.mkdtemp())
        sid = "gameAsset:fixture#1/components/0"
        node_id = "gameAsset:fixture#1"
        prefab_id = "gameAsset:fixture"
        data_id = "spineAsset:fixture"
        rendering = {
            "contract": "monkey-static-spine-rendering/1",
            "schemaVersion": 1,
            "sourceManifestSha256": "a" * 64,
            "sourceCanvasContextEvidenceContract": CONTRACT if required else None,
            "unitMapping": {"targetUnitsPerSourcePixel": 2.0},
            "components": [{"sourceComponentId": sid, "sourcePrefabId": prefab_id,
                "sourceNodeId": node_id, "sourceDataAssetId": data_id,
                "sourceComponentEnabled": True, "sourceVisible": True, "eligible": True}],
            "dataAssets": [{"sourceDataAssetId": data_id, "eligible": True,
                "factorySpec": {"sourceAssetId": data_id, "sourceDefaultScale": 1.0,
                    "targetUnitsPerSourcePixel": 2.0}}],
        }
        rendering_raw = json.dumps(rendering, sort_keys=True, separators=(",", ":")).encode()
        rendering_path = root / RENDERING_PATH
        rendering_path.parent.mkdir(parents=True, exist_ok=True)
        rendering_path.write_bytes(rendering_raw)
        import_plan = {"sourceManifestSha256": "a" * 64,
            "nodes": [{"sourceId": node_id, "active": True}],
            "components": [{"sourceId": sid, "node": node_id, "enabled": True}]}
        import_path = root / IMPORT_PLAN_PATH
        import_path.parent.mkdir(parents=True, exist_ok=True)
        import_path.write_text(json.dumps(import_plan), encoding="utf-8")

        context = {"schemaVersion": 1, "contract": CONTRACT,
            "sourceManifestSha256": "a" * 64, "renderingPlanSha256": sha(rendering_raw),
            "evidenceSha256": "c" * 64, "capturePhase": "source-construction-before-prefab-save",
            "sourceReferencePixelsPerUnit": 100.0, "sourceNodeGeometryVerified": True,
            "sourceCanvasContextVerified": True, "sourceNodeCount": 1,
            "contexts": [{"contextIndex": 0, "sourceCanvasRenderMode": "ScreenSpaceOverlay",
                "sourceCanvasScaleMode": "ConstantPixelSize", "sourceCanvasReferencePixelsPerUnit": 100.0,
                "sourceScalerReferencePixelsPerUnit": 100.0, "sourceScalerMatchWidthOrHeight": 0.0,
                "sourceScalerReferenceResolution": [800.0, 600.0], "sourceCanvasScalerPresent": True,
                "sourceCanvasPpuMatchesScaler": True, "sourceNodeIds": [node_id]}],
            "components": [{"sourceComponentId": sid, "sourcePrefabId": prefab_id,
                "sourceNodeId": node_id, "sourceDataAssetId": data_id, "sourceCanvasContextIndex": 0,
                "sourceCanvasContextVerified": True, "sourceNodeActive": True,
                "sourceNodeActivityVerified": True, "sourceComponentEnabled": True}]}
        evidence_raw = json.dumps(context, indent=2).encode()
        evidence_path = root / EVIDENCE_PATH
        evidence_path.parent.mkdir(parents=True)
        evidence_path.write_bytes(evidence_raw)
        host = {"schemaVersion": 1, "contract": "monkey-static-spine-controlled-prefab-host/1",
            "sourceManifestSha256": "a" * 64, "renderingPlanSha256": sha(rendering_raw),
            "sourceCanvasEvidenceSha256": "c" * 64, "evidenceSha256": "d" * 64,
            "contextKind": "created-by-monkey-owned-prefab-ui-context",
            "sourceCanvasRenderMode": "ScreenSpaceOverlay", "controlledHostCanvasRenderMode": "WorldSpace",
            "controlledHostScaleMode": "none", "sourceCanvasReferencePixelsPerUnit": 100.0,
            "sourceScalerReferencePixelsPerUnit": 100.0, "controlledHostReferencePixelsPerUnit": 100.0,
            "sourceCanvasScalerPresent": True, "sourceContextVerified": True,
            "controlledHostCanvasScalerAbsent": True, "controlledHostGeometryMatchesPlan": True, "verified": True}
        saved = {"schemaVersion": 1, "contract": "monkey-static-spine-rendering-readback/1",
            "status": "verified", "phase": "saved-prefab-reopen", "sourcePrefabId": prefab_id,
            "sourceManifestSha256": "a" * 64, "renderingPlanSha256": sha(rendering_raw),
            "sourceCanvasContextEvidencePath": EVIDENCE_PATH,
            "sourceCanvasContextEvidenceFileSha256": sha(evidence_raw), "sourceCanvasContext": context,
            "components": [{"sourceComponentId": sid, "sourceDataAssetId": data_id,
                "sourceComponentEnabled": True, "sourceVisible": True, "verified": True,
                "sourceCanvasContextEvidenceSha256": "c" * 64, "sourceCanvasContextKind": "controlled-prefab-reopened-owner",
                "sourceCanvasContextVerified": True, "sourceCanvasRenderMode": "ScreenSpaceOverlay",
                "sourceNodeActive": True, "sourceNodeActivityVerified": True,
                "controlledHostContextEvidence": host, "controlledHostContextEvidenceSha256": "d" * 64,
                "controlledHostContextKind": "created-by-monkey-owned-prefab-ui-context",
                "controlledHostContextVerified": True, "controlledHostCanvasRenderMode": "WorldSpace",
                "controlledHostCanvasReferencePixelsPerUnit": 100.0,
                "canvasReferencePixelsPerUnit": 100.0, "sourceCanvasReferencePixelsPerUnit": 100.0,
                "sourceScalerReferencePixelsPerUnit": 100.0, "sourceDefaultScale": 1.0,
                "targetUnitsPerSourcePixel": 2.0, "dataScale": 0.02}]}
        return root, rendering, saved, context

    def test_legacy_actual14_style_plan_without_file_is_accepted(self):
        root = Path(tempfile.mkdtemp())
        legacy = {"contract": "monkey-static-spine-rendering/1", "components": []}
        self.assertEqual([], verify_context_evidence(legacy, root, [{"phase": "saved-prefab-reopen"}]))

    def test_required_contract_without_file_fails_closed(self):
        root, rendering, _, _ = self._fixture()
        (root / EVIDENCE_PATH).unlink()
        gaps = verify_context_evidence(rendering, root, [])
        self.assertIn("SPINE_CANVAS_CONTEXT_EVIDENCE_REQUIRED_FILE_MISSING", {row["code"] for row in gaps})

    def test_file_presence_opts_legacy_plan_into_validation(self):
        root, rendering, saved, _ = self._fixture(required=False)
        rendering.pop("sourceCanvasContextEvidenceContract")
        raw = json.dumps(rendering, sort_keys=True, separators=(",", ":")).encode()
        (root / RENDERING_PATH).write_bytes(raw)
        # Keep envelope pins consistent with the candidate plan's revised bytes.
        context_path = root / EVIDENCE_PATH
        context = json.loads(context_path.read_text())
        context["renderingPlanSha256"] = sha(raw)
        context_raw = json.dumps(context, indent=2).encode()
        context_path.write_bytes(context_raw)
        saved["renderingPlanSha256"] = sha(raw)
        saved["sourceCanvasContext"] = context
        saved["sourceCanvasContextEvidenceFileSha256"] = sha(context_raw)
        saved["components"][0]["controlledHostContextEvidence"]["renderingPlanSha256"] = sha(raw)
        gaps = verify_context_evidence(rendering, root, [saved])
        self.assertEqual([], gaps)

    def test_valid_saved_owner_host_pair_and_scale_equation(self):
        root, rendering, saved, _ = self._fixture()
        self.assertEqual([], verify_context_evidence(rendering, root, [saved]))

    def test_source_node_identity_activity_and_component_denominator_are_exact(self):
        mutations = [
            (lambda r, d: d["components"][0].update(sourceNodeId="other"), "SPINE_CANVAS_CONTEXT_SOURCE_IDENTITY_OR_ACTIVITY_MISMATCH"),
            (lambda r, d: d["components"][0].update(sourceNodeActive=False), "SPINE_CANVAS_CONTEXT_NODE_ACTIVE_MISMATCH"),
            (lambda r, d: d["components"].append(dict(d["components"][0], sourceComponentId="extra")), "SPINE_CANVAS_CONTEXT_COMPONENT_DENOMINATOR_MISMATCH"),
        ]
        for mutate, code in mutations:
            with self.subTest(code=code):
                root, rendering, saved, context = self._fixture()
                mutate(rendering, context)
                self._rewrite_context(root, rendering, saved, context)
                gaps = verify_context_evidence(rendering, root, [saved])
                self.assertIn(code, {row["code"] for row in gaps})

    def test_missing_mutated_or_split_host_is_rejected(self):
        for mutation, code in [
            (lambda row: row.pop("controlledHostContextEvidence"), "SPINE_CANVAS_CONTROLLED_HOST_EVIDENCE_MISSING"),
            (lambda row: row["controlledHostContextEvidence"].update(controlledHostReferencePixelsPerUnit=99), "SPINE_CANVAS_CONTROLLED_HOST_PPU_MISMATCH"),
            (lambda row: row["controlledHostContextEvidence"].update(controlledHostGeometryMatchesPlan=False), "SPINE_CANVAS_CONTROLLED_HOST_CONTRACT_MISMATCH"),
        ]:
            with self.subTest(code=code):
                root, rendering, saved, _ = self._fixture()
                mutation(saved["components"][0])
                gaps = verify_context_evidence(rendering, root, [saved])
                self.assertIn(code, {row["code"] for row in gaps})

    def test_file_bytes_embedded_copy_and_rendering_pin_are_bound(self):
        root, rendering, saved, _ = self._fixture()
        saved["sourceCanvasContextEvidenceFileSha256"] = "f" * 64
        gaps = verify_context_evidence(rendering, root, [saved])
        self.assertIn("SPINE_CANVAS_EVIDENCE_FILE_HASH_MISMATCH", {row["code"] for row in gaps})
        root, rendering, saved, _ = self._fixture()
        saved["sourceCanvasContext"]["sourceNodeCount"] = 2
        gaps = verify_context_evidence(rendering, root, [saved])
        self.assertIn("SPINE_CANVAS_EMBEDDED_CONTEXT_DIFFERS_FROM_FILE", {row["code"] for row in gaps})

    def test_scale_mismatch_and_extra_host_document_fail(self):
        root, rendering, saved, _ = self._fixture()
        saved["components"][0]["dataScale"] = 0.01
        self.assertIn("SPINE_CANVAS_DATA_SCALE_EQUATION_MISMATCH",
                      {row["code"] for row in verify_context_evidence(rendering, root, [saved])})
        root, rendering, saved, _ = self._fixture()
        extra = copy.deepcopy(saved)
        extra["sourcePrefabId"] = "gameAsset:extra"
        gaps = verify_context_evidence(rendering, root, [saved, extra])
        self.assertIn("SPINE_CANVAS_SAVED_DOCUMENT_PREFAB_DENOMINATOR_MISMATCH", {row["code"] for row in gaps})

    def test_two_different_controlled_hosts_for_one_prefab_fail(self):
        root, rendering, saved, context = self._fixture()
        second_id = "gameAsset:fixture#2/components/0"
        second = copy.deepcopy(rendering["components"][0])
        second["sourceComponentId"] = second_id
        second["sourceNodeId"] = "gameAsset:fixture#2"
        rendering["components"].append(second)
        context["sourceNodeCount"] = 2
        context["contexts"][0]["sourceNodeIds"].append(second["sourceNodeId"])
        source_component = copy.deepcopy(context["components"][0])
        source_component.update(sourceComponentId=second_id, sourceNodeId=second["sourceNodeId"])
        context["components"].append(source_component)
        saved_component = copy.deepcopy(saved["components"][0])
        saved_component["sourceComponentId"] = second_id
        saved_component["controlledHostContextEvidence"]["evidenceSha256"] = "e" * 64
        saved_component["controlledHostContextEvidenceSha256"] = "e" * 64
        saved["components"].append(saved_component)
        # Add the second source node/component to the source plan used by the verifier.
        import_plan_path = root / IMPORT_PLAN_PATH
        import_plan = json.loads(import_plan_path.read_text())
        import_plan["nodes"].append({"sourceId": second["sourceNodeId"], "active": True})
        import_plan["components"].append({"sourceId": second_id, "node": second["sourceNodeId"], "enabled": True})
        import_plan_path.write_text(json.dumps(import_plan), encoding="utf-8")
        self._rewrite_context(root, rendering, saved, context)
        gaps = verify_context_evidence(rendering, root, [saved])
        self.assertIn("SPINE_CANVAS_PREFAB_HAS_MULTIPLE_CONTROLLED_HOSTS", {row["code"] for row in gaps})

    @staticmethod
    def _rewrite_context(root, rendering, saved, context):
        render_raw = json.dumps(rendering, sort_keys=True, separators=(",", ":")).encode()
        (root / RENDERING_PATH).write_bytes(render_raw)
        context["renderingPlanSha256"] = sha(render_raw)
        context_raw = json.dumps(context, indent=2).encode()
        (root / EVIDENCE_PATH).write_bytes(context_raw)
        saved["renderingPlanSha256"] = sha(render_raw)
        saved["sourceCanvasContext"] = copy.deepcopy(context)
        saved["sourceCanvasContextEvidenceFileSha256"] = sha(context_raw)
        for row in saved["components"]:
            host = row.get("controlledHostContextEvidence")
            if isinstance(host, dict):
                host["renderingPlanSha256"] = sha(render_raw)
                host["sourceCanvasEvidenceSha256"] = context["evidenceSha256"]


if __name__ == "__main__":
    unittest.main()
