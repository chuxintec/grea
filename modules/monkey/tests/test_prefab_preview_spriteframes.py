import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from monkey.prefab_preview_spriteframes import SpriteProjectionError, prepare


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if isinstance(value, bytes) else (json.dumps(value, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _fixture(tmp_path):
    source_id = "gameAsset:frame-1"
    prefab_id = "gameAsset:prefab-1"
    source_manifest_sha = "a" * 64
    stage = tmp_path / "stage"
    plan = {
        "sourceManifestSha256": source_manifest_sha,
        "sourcePrefabs": [{"sourceId": prefab_id}],
        "nodes": [{"sourceId": prefab_id + "#7", "children": []}],
        "textures": [],
    }
    plan_sha = _write(stage / "plan.json", plan)
    _write(stage / "manifest.json", {"files": [{"path": "plan.json", "bytes": (stage / "plan.json").stat().st_size, "sha256": plan_sha}]})
    source_manifest = {
        "assets": [{
            "sourceId": source_id, "kind": "cc.SpriteFrame", "logicalPath": "Texture/Test/frame",
            "index": 4, "document": {"instances": [{
                "__type__": "cc.SpriteFrame", "_textureSetter": {"__uuid__": "texture-1"},
                "data": {"rect": [0, 0, 8, 6], "originalSize": [8, 6], "offset": [0, 0]},
            }]},
        }],
    }
    source_manifest_path = tmp_path / "source-manifest.json"
    _write(source_manifest_path, source_manifest)
    js = tmp_path / "game.js"
    _write(js, b"source-code-fixture")
    evidence_path = tmp_path / "recipe" / "evidence.json"
    evidence_sha = _write(evidence_path, {"source": "fixture"})
    recipe = {
        "schema": "monkey-prefab-static-sprite-projection/1", "recipeId": "fixture",
        "sourcePrefabId": prefab_id, "sourceManifestSha256": source_manifest_sha,
        "sourceAssetManifestSha256": hashlib.sha256(source_manifest_path.read_bytes()).hexdigest(),
        "sourcePlanSha256": plan_sha, "sourceGameJsSha256": hashlib.sha256(js.read_bytes()).hexdigest(),
        "sourceVersion": "fixture", "referenceVersion": "static-only",
        "evidenceFiles": [{"id": "evidence", "path": "evidence.json", "sha256": evidence_sha}],
        "entries": [{
            "projectionId": "projection-1", "parentSourceId": prefab_id + "#7",
            "expectedParentChildSourceIds": [],
            "root": {"name": "GeneratedRoot", "size": [10, 10], "localPosition": [0, 0, 0],
                     "localScale": [1, 1, 1], "active": True},
            "spriteChild": {"name": "sprite", "spriteFrameSourceId": source_id,
                            "logicalPath": "Texture/Test/frame", "sourceRect": [0, 0, 8, 6],
                            "originalSize": [8, 6], "sizeMode": "TRIMMED",
                            "localPosition": [0, 0, 0], "anchor": [0.5, 0.5],
                            "color": [255, 255, 255, 255], "enabled": True},
        }],
    }
    recipe_path = tmp_path / "recipe" / "recipe.json"
    recipe_sha = _write(recipe_path, recipe)
    return recipe_path, recipe_sha, stage / "plan.json", source_manifest_path, js


class PrefabPreviewSpriteFramesTests(unittest.TestCase):
    def test_prepare_keeps_missing_target_spriteframe_explicit(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            tmp_path = Path(temp)
            recipe, recipe_sha, plan, source_manifest, js = _fixture(tmp_path)
            result = prepare(recipe, recipe_sha, plan, source_manifest, js, tmp_path / "output")
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["sourceSpriteFramesVerified"], 1)
            self.assertEqual(result["targetResourceBoundCount"], 0)
            projection = json.loads((tmp_path / "output" / "projection-plan.json").read_text())
            self.assertEqual(projection["entries"][0]["spriteChild"]["sourceRect"], [0, 0, 8, 6])
            self.assertFalse(projection["entries"][0]["targetResourceBound"])
            self.assertEqual(projection["diagnostics"][0]["code"], "SPRITE_FRAME_TARGET_RESOURCE_NOT_BOUND")

    def test_prepare_rejects_recipe_geometry_that_disagrees_with_source(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            tmp_path = Path(temp)
            recipe, _, plan, source_manifest, js = _fixture(tmp_path)
            data = json.loads(recipe.read_text())
            data["entries"][0]["spriteChild"]["sourceRect"] = [0, 0, 7, 6]
            recipe_sha = _write(recipe, data)
            with self.assertRaisesRegex(SpriteProjectionError, "source frame"):
                prepare(recipe, recipe_sha, plan, source_manifest, js, tmp_path / "output")


if __name__ == "__main__":
    unittest.main()
