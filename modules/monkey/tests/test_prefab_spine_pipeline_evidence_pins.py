import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from monkey.prefab_spine_pipeline import load_binding, material_origin_diagnostics


PRIVATE = Path(__file__).resolve().parents[1] / ".private/audit-remediation-20261105/evidence-font"


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


class SpinePipelineEvidencePinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PRIVATE.mkdir(parents=True, exist_ok=True)

    def _fixture(self, root: Path, material_sha="a" * 64):
        source_manifest_dir = root / "Input" / "inspect"
        source_manifest_dir.mkdir(parents=True)
        source_manifest_path = source_manifest_dir / "source-manifest.json"
        source_manifest_raw = encoded({"schemaVersion": 1, "assets": [], "inputs": []})
        source_manifest_path.write_bytes(source_manifest_raw)
        (source_manifest_dir / "manifest.json").write_bytes(encoded({"files": [{
            "path": source_manifest_path.name,
            "sha256": hashlib.sha256(source_manifest_raw).hexdigest(),
            "bytes": len(source_manifest_raw),
        }]}))

        ir_dir = root / "Input" / "normalize"
        ir_dir.mkdir(parents=True)
        ir_path = ir_dir / "ir.json"
        ir = {"sourceManifestPath": str(source_manifest_path),
              "sourceManifestSha256": hashlib.sha256(source_manifest_raw).hexdigest(),
              "components": []}
        ir_raw = encoded(ir)
        ir_path.write_bytes(ir_raw)
        (ir_dir / "manifest.json").write_bytes(encoded({"files": [{
            "path": ir_path.name,
            "sha256": hashlib.sha256(ir_raw).hexdigest(),
            "bytes": len(ir_raw),
        }]}))

        resources = root / "resources"
        resources.mkdir()
        closure_raw = encoded({"files": []})
        (resources / "manifest.json").write_bytes(closure_raw)
        profile = {
            "contract": "cocos24-builtin-spine-material-v1",
            "evidenceStatus": "source_to_internal_to_creator_builtin_pinned",
            "targetMaterialUuid": "default-spine-material",
            "targetEffect": "builtin-spine",
            "contractSha256": material_sha,
        }
        record = {
            "contract": "monkey-spine-emission/1",
            "pins": {
                "normalizedIrSha256": hashlib.sha256(ir_raw).hexdigest(),
                "sourceManifestSha256": hashlib.sha256(source_manifest_raw).hexdigest(),
                "creatorClosureReceiptSha256": hashlib.sha256(closure_raw).hexdigest(),
                "creatorMaterialContractSha256": material_sha,
            },
            "creatorMaterialProfile": profile,
            "components": [], "sourceComponentCount": 0, "copies": [],
        }
        receipt_path = root / "emission.json"
        receipt_raw = encoded(record)
        receipt_path.write_bytes(receipt_raw)
        return ir, ir_path, receipt_path, hashlib.sha256(receipt_raw).hexdigest(), resources, source_manifest_path

    def test_load_binding_accepts_exact_byte_pins_and_lowercase_digest(self):
        with TemporaryDirectory(dir=PRIVATE) as temp:
            ir, ir_path, receipt, receipt_sha, resources, _ = self._fixture(Path(temp))
            binding = load_binding(ir, ir_path, receipt, receipt_sha, resources)
            self.assertEqual(binding["receiptSha256"], receipt_sha)
            self.assertEqual(binding["record"]["pins"]["sourceManifestSha256"], ir["sourceManifestSha256"])

    def test_equal_receipt_digest_is_not_independent_source_material_provenance(self):
        from monkey.targets.cocos import _creator_validation_summary
        with TemporaryDirectory(dir=PRIVATE) as temp:
            ir, ir_path, receipt, receipt_sha, resources, _ = self._fixture(Path(temp))
            binding=load_binding(ir,ir_path,receipt,receipt_sha,resources)
            self.assertFalse(binding['materialProvenance']['contractBytesVerified'])
            diagnostics=material_origin_diagnostics(binding)
            self.assertEqual(diagnostics[0]['code'],'SPINE_MATERIAL_ORIGIN_NOT_VERIFIED')
            summary=_creator_validation_summary({'nativeStaticValidation':'pass',
                'staticPresentationValidation':{'status':'pass'}},diagnostics,'pass')
            self.assertNotEqual(summary['nativeStaticValidation'],'pass')
            self.assertNotEqual(summary['staticPresentationStatus'],'pass')
            self.assertEqual(material_origin_diagnostics(None),[])

    def test_load_binding_rejects_nonhex_or_short_creator_contract_sha(self):
        for invalid in ("z" * 64, "a" * 63, "A" * 64):
            with self.subTest(invalid=invalid[:4], size=len(invalid)), TemporaryDirectory(dir=PRIVATE) as temp:
                ir, ir_path, receipt, receipt_sha, resources, _ = self._fixture(Path(temp), invalid)
                with self.assertRaises(Exception):
                    load_binding(ir, ir_path, receipt, receipt_sha, resources)

    def test_load_binding_rejects_source_manifest_byte_drift_behind_ir_pin(self):
        with TemporaryDirectory(dir=PRIVATE) as temp:
            ir, ir_path, receipt, receipt_sha, resources, manifest_path = self._fixture(Path(temp))
            changed_raw = encoded({"schemaVersion": 1, "assets": [{"sourceId": "foreign"}], "inputs": []})
            manifest_path.write_bytes(changed_raw)
            (manifest_path.parent / "manifest.json").write_bytes(encoded({"files": [{
                "path": manifest_path.name,
                "sha256": hashlib.sha256(changed_raw).hexdigest(),
                "bytes": len(changed_raw),
            }]}))
            with self.assertRaises(Exception):
                load_binding(ir, ir_path, receipt, receipt_sha, resources)


if __name__ == "__main__":
    unittest.main()
