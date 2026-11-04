import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from monkey.prefab_static_retained_assets import SCHEMA, prepare


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _asset(source_id, kind, bundle, index, document, native=None):
    return {"sourceId": source_id, "kind": kind, "bundle": bundle, "index": index,
            "logicalPath": "retained/" + source_id.split(":", 1)[1], "key": source_id.split(":", 1)[1],
            "importPath": "import/source.json", "native": native, "document": {"instances": [document], "root": 0}}


class StaticRetainedAssetTests(unittest.TestCase):
    def _fixture(self, root):
        source = root / "source"; source.mkdir()
        (source / "import").mkdir()
        (source / "native").mkdir()
        pack = b"frozen-source-pack\n"
        (source / "import/source.json").write_bytes(pack)
        payloads = {
            "native/blob.bin": b"movie clip buffer bytes\x00\xff",
            "native/pixels.astc": (bytes.fromhex("13aba15c") + bytes([4, 4, 1]) +
                (4).to_bytes(3, "little") * 2 + (1).to_bytes(3, "little") + bytes(16)),
        }
        for path, value in payloads.items():
            target = source / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(value)
        mat = {"__type__": "cc.Material", "_name": "movie-clip",
               "_effectAsset": {"__uuid__": "effect-uuid"}, "_techniqueData": {"0": {"defines": {"DYNAMIC": True}}}}
        effect = {"__type__": "cc.EffectAsset", "_name": "movie-clip", "shaders": [{"name": "custom"}]}
        assets = [
            _asset("gameAsset:buffer", "cc.BufferAsset", "gameAsset", 1, {"__type__": "cc.BufferAsset"}, "native/blob.bin"),
            _asset("gameAsset:texture", "cc.Texture2D", "gameAsset", 2, {"__type__": "cc.Texture2D"}, "native/pixels.astc"),
            _asset("gameAsset:material", "cc.Material", "gameAsset", 3, mat),
            _asset("gameAsset:effect-uuid", "cc.EffectAsset", "gameAsset", 4, effect),
        ]
        inputs = [{"bundle": "gameAsset", "path": "import/source.json", "bytes": len(pack),
                   "sha256": hashlib.sha256(pack).hexdigest()}]
        inputs += [{"bundle": "gameAsset", "path": path, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
                   for path, value in payloads.items()]
        manifest = {"schemaVersion": 1, "sourceVersion": "2.4.15", "sourceRoots": {"gameAsset": str(source)},
                    "assets": assets, "inputs": inputs}
        manifest_path = root / "source-manifest.json"
        manifest_path.write_bytes(_canonical(manifest))
        references = [
            {"sourceComponentId": "prefab#3", "sourceNodeId": "prefab#1", "field": "_asset", "index": None,
             "sourceDeclaredType": "cc.Asset", "storageType": "UnityEngine.Object", "sourceAssetId": "gameAsset:buffer"},
            {"sourceComponentId": "prefab#3", "sourceNodeId": "prefab#1", "field": "_textures", "index": 0,
             "sourceDeclaredType": "[cc.Texture2D]", "storageType": "UnityEngine.Object[]", "sourceAssetId": "gameAsset:texture"},
            {"sourceComponentId": "prefab#3", "sourceNodeId": "prefab#1", "field": "_materials", "index": 0,
             "sourceDeclaredType": "", "storageType": "UnityEngine.Object[]", "sourceAssetId": "gameAsset:material"},
        ]
        plan = {"namespace": "retained-test", "sourceManifestSha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "components": [{"sourceId": "prefab#3", "node": "prefab#1", "staticFieldBinding": {"fields": [
                    {"sourceFieldName": "_asset", "storageType": "UnityEngine.Object", "kind": "asset_ref",
                     "sourceDeclaredType": "cc.Asset", "refValue": "gameAsset:buffer"},
                    {"sourceFieldName": "_textures", "storageType": "UnityEngine.Object[]", "elementKind": "asset_ref",
                     "sourceDeclaredType": "[cc.Texture2D]", "refValues": ["gameAsset:texture"]},
                    {"sourceFieldName": "_materials", "storageType": "UnityEngine.Object[]", "elementKind": "asset_ref",
                     "sourceDeclaredType": "", "refValues": ["gameAsset:material"]},
                ]}}]}
        return plan, manifest_path, references, payloads

    def test_prepare_copies_exact_buffer_decodes_astc_and_retains_dynamic_material_nonrendering(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            root = Path(temp); plan, manifest, _, raw = self._fixture(root)
            result = prepare(plan, manifest, root / "retained")
            contract = result["contract"]
            self.assertEqual(contract["schema"], SCHEMA)
            self.assertEqual(plan.get("staticRetainedAssets"), None)
            self.assertEqual(result["plan"]["staticRetainedAssets"], contract)
            self.assertEqual({row["retentionKind"] for row in contract["assets"]},
                             {"buffer-asset", "texture-asset", "retained-source-material"})
            buffer = next(row for row in contract["assets"] if row["sourceType"] == "cc.BufferAsset")
            self.assertEqual(buffer["sourceHashes"]["sourceNativeSha256"], buffer["sourceNative"]["sha256"])
            buffer_copy = next(row for row in contract["payloads"] if row["target"] == buffer["unity"]["path"])
            self.assertEqual((root / "retained" / buffer_copy["source"]).read_bytes(), raw["native/blob.bin"])
            texture = next(row for row in contract["assets"] if row["sourceType"] == "cc.Texture2D")
            self.assertEqual(texture["dimensions"], [4, 4])
            self.assertEqual(len(texture["rgbaSha256"]), 64)
            material = next(row for row in contract["assets"] if row["sourceType"] == "cc.Material")
            self.assertTrue(material["nonRendering"])
            self.assertFalse(material["renderingRecovered"])
            self.assertEqual(material["sourceEffectId"], "gameAsset:effect-uuid")
            self.assertIn("sourceEffectDocumentSha256", material["sourceHashes"])
            self.assertEqual(material["creator"]["type"], "cc.JsonAsset")
            self.assertEqual(material["unity"]["type"], "NativeRetainedMaterial")
            self.assertTrue(any(row["creatorFieldType"] == "Asset[]" for row in contract["references"]
                                if row["field"] == "_materials"))
            self.assertEqual(contract["copies"], [{key: row[key] for key in ("source", "target", "sha256")}
                                                   for row in contract["payloads"]])

    def test_creator_source_asset_array_field_type_is_asset_array(self):
        from monkey.prefab_static_carriers import _creator_script
        script = _creator_script("Monkey.Tests", "RetainedFields", [{"name": "_materials", "fieldName": "__sf_000_materials",
                                   "kind": "array", "storageType": "UnityEngine.Object[]", "elementKind": "asset_ref",
                                   "sourceDeclaredType": "", "refValues": [], "creatorType": "", "creatorElementType": "Asset"}])
        self.assertIn("import { _decorator, Asset, Component } from 'cc';", script)
        self.assertIn("@property([Asset]) public __sf_000_materials: Asset[] = [];", script)

    def test_builtin_material_does_not_fall_back_when_effect_proof_is_missing(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            root = Path(temp); plan, manifest_path, _, _ = self._fixture(root)
            manifest = json.loads(manifest_path.read_text())
            manifest["assets"].append(_asset("internal:default", "cc.Material", "gameAsset", 9,
                {"__type__": "cc.Material", "_name": "builtin-2d-sprite",
                 "_effectAsset": {"__uuid__": "unresolved"},
                 "_techniqueData": {"0": {"defines": {"USE_TEXTURE": True}}}}))
            manifest_path.write_bytes(_canonical(manifest))
            plan["sourceManifestSha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            plan["components"][0]["staticFieldBinding"]["fields"].append({
                "sourceFieldName": "_materials", "storageType": "UnityEngine.Object[]", "elementKind": "asset_ref",
                "sourceDeclaredType": "", "refValues": ["internal:default"]})
            with self.assertRaisesRegex(Exception, "source material effect identity is unresolved|no unique source EffectAsset"):
                prepare(plan, manifest_path, root / "bad-output")
            self.assertFalse((root / "bad-output").exists())


if __name__ == "__main__":
    unittest.main()
