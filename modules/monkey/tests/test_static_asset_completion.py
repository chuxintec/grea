import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from monkey.io import write_json
from monkey.prefab_static_asset_completion import SCHEMA, apply, emit, prepare_for_target
from monkey.sources.compiled import ParseError, decode_pack_section, source_asset_key


FRAME = "00000000-0000-0000-0000-000000000101"
OPAQUE_TEXTURE = "ab12cd34-ef56-4a78-9abc-def01234567"


def _compiled_pack(frame_data):
    section_frame = [[frame_data], [0], [], [0], ["_textureSetter"], [0]]
    section_texture = [["0,9729,9729,33071,33071,0,0,0"], [1], [], [], [], []]
    return [1, [OPAQUE_TEXTURE], [], ["cc.SpriteFrame", "cc.Texture2D"], [],
            [section_frame, section_texture]]


class StaticAssetCompletionTests(unittest.TestCase):
    @staticmethod
    def _write_json(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        path.write_bytes(raw)
        return raw

    def _fixture(self, root, target_profile="unity-6000.6.2f1-ugui"):
        original = root / "original"
        source_root = original / "cdn/remote/gameAsset"
        cache_root = original / "resource-cache"
        cache_payload = cache_root / "gameAsset/cache-asset.png"
        cache_payload.parent.mkdir(parents=True, exist_ok=True)
        native_bytes_io = __import__("io").BytesIO()
        with Image.new("RGBA", (4, 4), (40, 90, 180, 255)) as image:
            image.save(native_bytes_io, format="PNG", optimize=False)
        native = native_bytes_io.getvalue()
        cache_payload.write_bytes(native)
        native_relative = f"native/{OPAQUE_TEXTURE[:2]}/{OPAQUE_TEXTURE}.nv1.png"
        native_path = source_root / native_relative
        native_path.parent.mkdir(parents=True, exist_ok=True)
        native_path.write_bytes(native)

        frame_data = {"name": "frame", "rect": [0, 0, 4, 4], "originalSize": [4, 4],
                      "offset": [0, 0], "rotated": 0, "capInsets": [1, 1, 1, 1]}
        pack = _compiled_pack(frame_data)
        pack_path = source_root / "import" / "pa" / "pack000.v1.json"
        pack_raw = self._write_json(pack_path, pack)
        config = {"name": "gameAsset", "engineVersion": "2.4.15",
                  "uuids": [FRAME, OPAQUE_TEXTURE], "paths": {
                      "0": ["Texture/Test/frame", 0, 1], "1": ["Texture/Test/frame", 1]},
                  "types": ["cc.SpriteFrame", "cc.Texture2D"], "packs": {"pack000": [0, 1]},
                  "versions": {"import": ["pack000", "v1"], "native": [1, "nv1"]},
                  "redirect": [], "deps": []}
        config_path = source_root / "config.test.json"
        config_raw = self._write_json(config_path, config)
        cdn = "https://cdn.example.test/app/asset/remote/gameAsset/" + native_relative
        cache_list = {"files": {cdn: {"bundle": "gameAsset", "url": "wxfile://usr/gamecaches/gameAsset/cache-asset.png",
                                     "lastTime": "1"}}}
        self._write_json(cache_root / "cacheList.json", cache_list)
        manifest = {"schemaVersion": 1, "sourceProfile": "cocos-2.4.15-bundle", "sourceVersion": "2.4.15",
                    "bundle": "gameAsset", "sourceRoot": str(source_root),
                    "sourceRoots": {"gameAsset": str(source_root)}, "assets": [{
                        "sourceId": "gameAsset:" + FRAME, "bundle": "gameAsset", "key": FRAME,
                        "index": 0, "kind": None, "document": None, "native": None, "references": []}],
                    "inputs": [
                        {"bundle": "gameAsset", "path": "config.test.json", "bytes": len(config_raw),
                         "sha256": hashlib.sha256(config_raw).hexdigest()},
                        {"bundle": "gameAsset", "path": "import/pa/pack000.v1.json", "bytes": len(pack_raw),
                         "sha256": hashlib.sha256(pack_raw).hexdigest()}], "diagnostics": []}
        manifest_path = root / "inspect/source-manifest.json"
        manifest_raw = self._write_json(manifest_path, manifest)
        source_components = [
            {"sourceId": "gameAsset:" + FRAME + "#1/components/0", "node": "n1", "type": "cc.Sprite",
             "spriteFrame": "gameAsset:" + FRAME, "enabled": True, "mode": 1, "trim": True},
            {"sourceId": "gameAsset:" + FRAME + "#2/components/0", "node": "n2", "type": "cc.Sprite",
             "spriteFrame": "gameAsset:" + FRAME, "enabled": False, "mode": 1, "trim": True},
        ]
        plan = {"namespace": "neutral-static-resource-test", "targetProfile": target_profile,
                "sourceManifestPath": str(manifest_path),
                "sourceManifestSha256": hashlib.sha256(manifest_raw).hexdigest(), "sourceIrSha256": "i" * 64,
                "components": source_components, "textures": [], "copies": []}
        return plan, manifest_path, source_root, native_path, native, cache_payload

    def test_declared_opaque_id_is_exact_and_unsafe_paths_stay_rejected(self):
        self.assertEqual(OPAQUE_TEXTURE, source_asset_key(OPAQUE_TEXTURE, declared_source_ids={OPAQUE_TEXTURE}))
        for value in ("../../escape", "a/b", "a\\b", "unsafe:token"):
            with self.assertRaises(ParseError):
                source_asset_key(value, declared_source_ids={value})
        pack = _compiled_pack({"rect": [0, 0, 4, 4]})
        document = decode_pack_section(pack, 0, declared_source_ids={OPAQUE_TEXTURE})
        root = document["instances"][document["root"]]
        self.assertEqual({"__uuid__": OPAQUE_TEXTURE}, root["_textureSetter"])
        with self.assertRaises(ParseError):
            decode_pack_section(pack, 0)

    def test_apply_builds_two_engine_payload_mappings_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            root = Path(temp)
            plan, manifest, source_root, native_path, native, cache_payload = self._fixture(root)
            before = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (manifest, native_path, cache_payload)}
            result = apply(plan, manifest, root / "completion")
            contract = result["contract"]
            self.assertEqual(SCHEMA, contract["schema"])
            self.assertEqual(2, len(contract["assets"]))
            self.assertEqual(2, len(contract["references"]))
            self.assertEqual({True, False}, {row["sourceEnabled"] for row in contract["references"]})
            self.assertEqual(12, len(contract["payloads"]))
            self.assertEqual(2, len(result["plan"]["textures"]))
            self.assertTrue(all(row["status"] == "old-manifest-pinned"
                                for row in contract["oldManifestInputPins"]))
            texture_asset = next(row for row in contract["assets"] if row["sourceType"] == "cc.Texture2D")
            self.assertEqual("gameAsset:" + OPAQUE_TEXTURE, texture_asset["sourceId"])
            self.assertEqual("config-declared-opaque", texture_asset["sourceIdentityEncoding"])
            self.assertEqual(hashlib.sha256(native).hexdigest(), texture_asset["sourceNative"]["sha256"])
            self.assertEqual("absent-and-added-to-completion", texture_asset["sourceNative"]["oldManifestInput"])
            self.assertTrue(any("/Textures/@original/" in row["target"] for row in contract["payloads"]))
            self.assertTrue(any(row["target"].startswith("assets/resources/Textures/")
                                and row["target"].endswith(".png.meta") for row in contract["payloads"]))
            self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest()
                                      for path in (manifest, native_path, cache_payload)})
            self.assertFalse(plan.get("sourceResourceCompletion"))
            self.assertTrue((root / "completion/manifest.json").is_file())

    def test_prepare_for_unity_uses_importer_guid_rule_and_declares_texture2d(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            root = Path(temp)
            plan, manifest, _, _, _, _ = self._fixture(root)
            prepared = prepare_for_target(plan, manifest, root / "unity-completion")
            from monkey.targets.unity import guid
            frame = next(row for row in prepared["contract"]["assets"] if row["sourceType"] == "cc.SpriteFrame")
            texture = next(row for row in prepared["contract"]["assets"] if row["sourceType"] == "cc.Texture2D")
            frame_spec = next(row for row in prepared["plan"]["textures"] if row["id"] == frame["sourceId"])
            self.assertEqual(guid(prepared["plan"]["namespace"], frame["sourceId"]), frame_spec["guid"])
            texture_spec = next(row for row in prepared["plan"]["assets"] if row["id"] == texture["sourceId"])
            self.assertEqual("cc.Texture2D", texture_spec["kind"])
            self.assertEqual(texture["unity"]["guid"], texture_spec["guid"])
            meta = Path(prepared["output"]) / next(row["source"] for row in prepared["contract"]["payloads"]
                if row["kind"] == "unity-sprite-meta")
            self.assertIn("guid: " + frame_spec["guid"], meta.read_text())
            self.assertEqual("payloads/", prepared["plan"]["sourceResourceCompletion"]["payloadPrefix"])

    def test_creator_target_descriptors_and_emit_copy_exact_png_meta_without_double_suffix(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            root = Path(temp)
            plan, manifest, _, _, _, _ = self._fixture(root, "cocos-3.8.8")
            prepared = prepare_for_target(plan, manifest, root / "creator-completion")
            from monkey.targets.cocos import identity
            frame = next(row for row in prepared["plan"]["assets"] if row["sourceId"] == "gameAsset:" + FRAME)
            self.assertEqual("sprite", frame["kind"])
            self.assertEqual(identity(prepared["plan"]["namespace"], frame["sourceId"]), frame["uuid"])
            creator_meta_path = Path(prepared["output"]) / next(row["source"] for row in prepared["contract"]["payloads"]
                if row["kind"] == "creator-sprite-meta")
            creator_meta = json.loads(creator_meta_path.read_text())
            self.assertEqual(frame["uuid"], creator_meta["uuid"])
            self.assertEqual("sprite-frame", creator_meta["userData"]["type"])
            self.assertFalse(any(row["importer"] == "sprite-frame" for row in creator_meta["subMetas"].values()))
            self.assertIsNone(frame["spriteFrameUuid"])
            self.assertEqual("creator-native-importer-assigned-v1", frame["spriteFrameUuidPolicy"])
            self.assertEqual("gameAsset:" + FRAME + "@original",
                             next(row["sourceId"] for row in prepared["plan"]["assets"] if row["sourceId"].endswith("@original")))
            texture_asset = prepared["plan"]["sourceResourceCompletion"]["targetAssets"]["creatorTexture2D"][0]
            self.assertEqual("cc.Texture2D", texture_asset["kind"])
            from monkey.layout.verify import scan
            self.assertEqual([], scan([texture_asset["path"]]))
            self.assertEqual(identity(prepared["plan"]["namespace"], texture_asset["sourceId"]), texture_asset["uuid"])
            texture_meta_path = Path(prepared["output"]) / next(row["source"] for row in prepared["contract"]["payloads"]
                if row["kind"] == "creator-texture-meta")
            texture_meta = json.loads(texture_meta_path.read_text())
            texture_submeta = next(row for row in texture_meta["subMetas"].values() if row["importer"] == "texture")
            self.assertEqual(texture_asset["uuid"], texture_meta["uuid"])
            self.assertEqual(texture_asset["textureUuid"], texture_submeta["uuid"])
            candidate = root / "creator-candidate"
            candidate.mkdir()
            self._write_json(candidate / "manifest.json", {"scopeMode": "asset-selection", "files": []})
            emitted = emit(prepared["plan"], prepared["output"], candidate, "creator")
            self.assertEqual(6, len(emitted["files"]))
            self.assertTrue(emitted["outputManifestSha256"])
            self.assertTrue(all(not row["path"].endswith(".meta.meta") for row in emitted["files"]))
            self.assertTrue((candidate / frame["path"]).is_file())
            self.assertTrue((candidate / (frame["path"] + ".meta")).is_file())
            candidate_manifest = json.loads((candidate / "manifest.json").read_text())
            self.assertEqual(6, len(candidate_manifest["files"]))
            with self.assertRaisesRegex(ValueError, "already owned|filename collision"):
                emit(prepared["plan"], prepared["output"], candidate, "creator")

    def test_emit_rejects_preexisting_target_filename_collision(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            root = Path(temp)
            plan, manifest, _, _, _, _ = self._fixture(root)
            prepared = prepare_for_target(plan, manifest, root / "unity-completion")
            candidate = root / "unity-candidate"
            path = next(row["target"] for row in prepared["contract"]["payloads"] if row["kind"] == "unity-sprite-png")
            collision = candidate / path
            collision.parent.mkdir(parents=True, exist_ok=True)
            collision.write_bytes(b"preexisting")
            with self.assertRaisesRegex(ValueError, "already owned|filename collision"):
                emit(prepared["plan"], prepared["output"], candidate, "unity")
            self.assertEqual(b"preexisting", collision.read_bytes())

    def test_target_descriptor_adds_stable_suffix_for_plan_path_collision(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            root = Path(temp)
            plan, manifest, _, _, _, _ = self._fixture(root)
            plan["copies"] = [{"sourceId": "gameAsset:other-frame", "target":
                "Assets/Game/Content/Textures/Test/frame.png", "sha256": "0" * 64}]
            prepared = prepare_for_target(plan, manifest, root / "unity-completion")
            frame = next(row for row in prepared["plan"]["textures"] if row["id"] == "gameAsset:" + FRAME)
            self.assertNotEqual("Assets/Game/Content/Textures/Test/frame.png", frame["path"])
            self.assertRegex(Path(frame["path"]).stem, r"^frame__[0-9a-f]{10}$")


if __name__ == "__main__":
    unittest.main()
