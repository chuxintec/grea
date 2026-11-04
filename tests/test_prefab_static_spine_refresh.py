import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monkey.io import sha, write_json
from monkey.prefab_static_spine_refresh import (
    SCHEMA,
    StaticSpineRefreshError,
    _CONTINUATION_SUPPORT_FILES,
    _DERIVED_HELPER,
    _RENDER_HELPERS,
    _REFRESH_TARGETS,
    _package_helper_bytes,
    prepare,
)
from monkey.prefab_static_spine_rendering import upgrade_atlas_mapping

_READ_PACKAGE_HELPER = _package_helper_bytes


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StaticSpineHelperRefreshTests(unittest.TestCase):
    def _write_fixture(self, base: Path) -> tuple[Path, Path, dict, dict, dict[str, bytes]]:
        plan_root = base / "input-plan"
        module_stage = "spine_static_rendering"
        module_root = plan_root / module_stage
        payload_root = module_root / "spine-static-rendering-payloads"
        payload_root.mkdir(parents=True)
        source_manifest_sha = "a" * 64
        continuation = {
            "contract": "monkey-prefab-static-spine-continuation/1",
            "moduleStage": "spine_static_continuation",
            "sourceManifestSha256": source_manifest_sha,
            "dataAssets": [], "components": [], "payloadCopies": [], "supportFiles": [],
        }
        (plan_root / continuation["moduleStage"]).mkdir(parents=True)
        for source, (target, role) in _CONTINUATION_SUPPORT_FILES.items():
            package_file = Path(__file__).resolve().parents[1] / "src/monkey" / source
            support_bytes = package_file.read_bytes()
            continuation["supportFiles"].append({"source": source, "target": target, "role": role,
                                                 "sha256": sha(support_bytes), "bytes": len(support_bytes)})
        helper_rows = []
        package_bytes = {}
        for relative, target in (*_RENDER_HELPERS, _DERIVED_HELPER):
            source = Path(__file__).resolve().parents[1] / "src/monkey" / relative
            raw = source.read_bytes()
            package_bytes[target] = raw
            digest = sha(raw)
            row = {
                "source": f"spine-static-rendering-payloads/{digest}/{Path(target).name}",
                "target": target, "sha256": digest, "bytes": len(raw),
                "role": "pinned-spine-rendering-derived-helper" if relative == _DERIVED_HELPER[0]
                    else "pinned-spine-native-helper",
            }
            destination = module_root / row["source"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            helper_rows.append(row)
        untouched = module_root / "retained-support.bin"
        untouched.write_bytes(b"opaque retained support bytes\x00\x01")
        rendering = {
            "schemaVersion": 1, "contract": "monkey-static-spine-rendering/1",
            "moduleStage": module_stage, "status": "prepared_static_spine_renderers",
            "sourceManifestSha256": source_manifest_sha,
            "sourceContinuationSha256": sha(json.dumps(continuation, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()),
            "payloads": helper_rows, "dataAssets": [], "components": [],
            "externalDependencies": [{
                "target": "Assets/Game/Scripts/Presentation/StaticMasks/NativeStaticMaskIdentity.cs",
                "sha256": _digest(Path(__file__).resolve().parents[1] / "src/monkey/targets/NativeStaticMaskIdentity.cs"),
                "providedBy": "standard-unity-static-mask-export", "copy": False,
            }],
        }
        plan = {
            "schemaVersion": 1, "toolVersion": "test", "sourceManifestSha256": source_manifest_sha,
            "staticSpineContinuation": continuation, "staticSpineRendering": rendering,
        }
        write_json(module_root / "spine-static-rendering.json", rendering)
        write_json(plan_root / "plan.json", plan)
        manifest = {
            "schemaVersion": 1, "scopeMode": "asset-selection", "status": "candidate",
            "sourceManifestSha256": source_manifest_sha, "staticSpineContinuation": continuation,
            "staticSpineRendering": rendering,
        }
        manifest["files"] = [
            {"path": path.relative_to(plan_root).as_posix(), "sha256": _digest(path),
             "bytes": path.stat().st_size, "owner": "generated"}
            for path in sorted(plan_root.rglob("*")) if path.is_file()
        ]
        write_json(plan_root / "manifest.json", manifest)
        request = {
            "schema": SCHEMA, "schemaVersion": 1,
            "plan": {"path": str(plan_root / "plan.json"), "sha256": _digest(plan_root / "plan.json")},
            "planManifest": {"path": str(plan_root / "manifest.json"), "sha256": _digest(plan_root / "manifest.json")},
        }
        request_path = base / "request.json"
        write_json(request_path, request)
        return plan_root / "plan.json", request_path, plan, manifest, package_bytes

    def test_fresh_stage_noop_preserves_all_support_and_parent_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            plan_path, request_path, plan, _, package_bytes = self._write_fixture(base)
            parent_plan_sha, request_sha = _digest(plan_path), _digest(request_path)
            with patch("monkey.prefab_static_spine_refresh._upgrade_atlas_mapping", return_value=[]):
                report = prepare(request_path, request_sha, base / "output")
            output_plan_root = Path(report["planPath"]).parent
            output_plan = json.loads(Path(report["planPath"]).read_text())
            self.assertEqual(output_plan["staticSpineRendering"]["ownerContextLifecycleEvidenceContract"],
                             "monkey-static-spine-owner-context-lifecycle/1")
            self.assertEqual(report["schema"], SCHEMA)
            self.assertEqual(report["parentPlanSha256"], parent_plan_sha)
            self.assertTrue(all(item["status"] == "already_current" for item in report["helperReplacements"]))
            self.assertEqual(output_plan["staticSpineContinuation"], plan["staticSpineContinuation"])
            self.assertEqual(output_plan["staticSpineHelperRefresh"]["atlasMapping"], [])
            self.assertEqual((output_plan_root / "spine_static_rendering/retained-support.bin").read_bytes(),
                             b"opaque retained support bytes\x00\x01")
            self.assertEqual(_digest(plan_path), parent_plan_sha)
            self.assertTrue(all(Path(report["planPath"]).exists() for _ in [0]))

    def test_only_changed_factory_helper_is_replaced_in_fresh_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            _, request_path, _, _, package_bytes = self._write_fixture(base)
            target = next(iter(_REFRESH_TARGETS))
            changed = package_bytes[target] + b"\n// verified package factory update\n"
            with patch("monkey.prefab_static_spine_refresh._package_helper_bytes") as source_bytes:
                def get_bytes(candidate):
                    path, raw = _READ_PACKAGE_HELPER(candidate)
                    return path, changed if candidate == target else raw
                source_bytes.side_effect = get_bytes
                with patch("monkey.prefab_static_spine_refresh._upgrade_atlas_mapping", return_value=[]):
                    report = prepare(request_path, _digest(request_path), base / "output")
            replaced = [row for row in report["helperReplacements"] if row["replaced"]]
            self.assertEqual([row["target"] for row in replaced], [target])
            refreshed_plan_root = Path(report["planPath"]).parent
            fragment = json.loads(Path(report["planPath"]).read_text())["staticSpineRendering"]
            refreshed_row = next(row for row in fragment["payloads"] if row["target"] == target)
            refreshed_path = refreshed_plan_root / fragment["moduleStage"] / refreshed_row["source"]
            self.assertEqual(refreshed_path.read_bytes(), changed)
            self.assertEqual(refreshed_row["sha256"], _digest(refreshed_path))
            old_row = next(row for row in _RENDER_HELPERS if row[1] == target)
            self.assertTrue((refreshed_plan_root / fragment["moduleStage"] / refreshed_row["source"]).is_file())
            self.assertEqual(old_row[1], target)

    def test_tampered_owned_helper_payload_is_rejected_without_changing_input(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            plan_path, request_path, _, _, _ = self._write_fixture(base)
            request_sha = _digest(request_path)
            plan = json.loads(plan_path.read_text())
            module_root = plan_path.parent / plan["staticSpineRendering"]["moduleStage"]
            payload = plan["staticSpineRendering"]["payloads"][0]
            (module_root / payload["source"]).write_bytes(b"tampered helper")
            with patch("monkey.prefab_static_spine_refresh._upgrade_atlas_mapping", return_value=[]):
                with self.assertRaisesRegex(StaticSpineRefreshError, "owned plan file differs from inventory"):
                    prepare(request_path, request_sha, base / "output")
            self.assertFalse((base / "output").exists())

    def test_request_hash_change_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            _, request_path, _, _, _ = self._write_fixture(base)
            expected = _digest(request_path)
            request_path.write_bytes(request_path.read_bytes() + b" ")
            with self.assertRaisesRegex(StaticSpineRefreshError, "request bytes differ"):
                prepare(request_path, expected, base / "output")
            self.assertFalse((base / "output").exists())

    def test_request_mutation_during_copy_cannot_publish_a_prepared_manifest(self):
        from monkey.output_limits import copy_verified
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            _, request_path, _, _, _ = self._write_fixture(base)
            expected = _digest(request_path)
            changed = False
            def copy_and_mutate(*args, **kwargs):
                nonlocal changed
                result = copy_verified(*args, **kwargs)
                if not changed:
                    request_path.write_bytes(request_path.read_bytes() + b' ')
                    changed = True
                return result
            with patch('monkey.prefab_static_spine_refresh.copy_verified', side_effect=copy_and_mutate):
                with patch('monkey.prefab_static_spine_refresh._upgrade_atlas_mapping', return_value=[]):
                    with self.assertRaisesRegex(StaticSpineRefreshError, 'changed during refresh'):
                        prepare(request_path, expected, base/'output')
            self.assertFalse((base/'output/manifest.json').exists())

    def test_output_inside_frozen_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            plan, request, _, _, _ = self._write_fixture(base)
            with self.assertRaises(Exception) as error:
                prepare(request, _digest(request), plan.parent/'nested-output')
            self.assertIn('Output overlaps an input', str(error.exception))
            self.assertFalse((plan.parent/'nested-output').exists())

    def test_synthetic_atlas_upgrade_preserves_decoded_texture_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp).resolve() / "plan"
            module = stage / "spine_static_rendering"
            module.mkdir(parents=True)
            atlas_original = b"page.png\nsize: 2,2\nformat: RGBA8888\nfilter: Linear,Linear\nrepeat: none\n"
            atlas_native = atlas_original
            png = b"preserved-decoded-rgba-payload"
            atlas_source = "spine-static-rendering-payloads/source/source.atlas.txt"
            png_source = "spine-static-rendering-payloads/decoded/page.png"
            for relative, raw in ((atlas_source, atlas_native), (png_source, png)):
                path = module / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            original_source = module / "source-atlas.txt"
            original_source.write_bytes(atlas_original)
            retained_root = stage / "spine_static_continuation"
            retained_root.mkdir()
            retained_copy = retained_root / "original/source.atlas.txt"
            retained_copy.parent.mkdir(parents=True)
            retained_copy.write_bytes(atlas_original)
            old_atlas = {"source": atlas_source, "target": "Assets/Spine/source.atlas.txt",
                         "sha256": sha(atlas_native), "bytes": len(atlas_native), "role": "native-spine-atlas-text"}
            texture = {"source": png_source, "target": "Assets/Spine/pages/texture-hash.png",
                       "sha256": sha(png), "bytes": len(png), "role": "decoded-source-astc-spine-page"}
            spec = {"sourceAssetId": "game:spine", "atlasTextAssetPath": old_atlas["target"],
                    "atlasSha256": old_atlas["sha256"], "pages": [{"sourceAtlasPage": "page.png",
                    "nativeAtlasPage": "page.png", "sourceTextureSourceId": "game:texture",
                    "textureAssetPath": texture["target"]}]}
            fragment = {"moduleStage": "spine_static_rendering", "payloads": [old_atlas.copy(), texture.copy()],
                        "dataAssets": [{"sourceDataAssetId": "game:spine", "factorySpec": spec,
                                        "payloads": [old_atlas.copy(), texture.copy()]}]}
            retained_data = {"sourceDataAssetId": "game:spine", "sourceAtlasTextAssetPath": "Assets/source/source.atlas",
                             "sourceAtlasSha256": sha(atlas_original),
                             "sourceAtlasPages": [{"sourcePageName": "page.png", "sourceTextureSourceId": "game:texture"}]}
            retained = {"moduleStage": "spine_static_continuation", "dataAssets": [retained_data],
                        "payloadCopies": [{"source": "original/source.atlas.txt", "target": "Assets/source/source.atlas",
                                           "sha256": sha(atlas_original), "bytes": len(atlas_original)}]}
            plan = {"staticSpineContinuation": retained, "staticSpineRendering": fragment}
            evidence = upgrade_atlas_mapping(plan, stage)
            changed = plan["staticSpineRendering"]
            new_spec = changed["dataAssets"][0]["factorySpec"]
            new_atlas_row = next(row for row in changed["payloads"] if row["target"] == old_atlas["target"])
            new_atlas = (module / new_atlas_row["source"]).read_bytes()
            expected_name = Path(texture["target"]).name
            self.assertIn(expected_name.encode(), new_atlas)
            self.assertNotIn(b"page.png", new_atlas.splitlines()[:1])
            self.assertEqual(new_spec["pages"][0]["nativeAtlasPage"], expected_name)
            self.assertEqual(new_spec["atlasSha256"], sha(new_atlas))
            self.assertEqual((module / png_source).read_bytes(), png)
            self.assertEqual(original_source.read_bytes(), atlas_original)
            self.assertEqual(evidence[0]["textureDecodeInvoked"], False)
            self.assertEqual(evidence[0]["textureBytesChanged"], False)


if __name__ == "__main__":
    unittest.main()


def test_known_external_mask_helper_refresh_requires_explicit_pinned_opt_in(tmp_path):
    owner=StaticSpineHelperRefreshTests()
    plan_path,request_path,plan,manifest,_=owner._write_fixture(tmp_path)
    fragment=plan["staticSpineRendering"]
    fragment["externalDependencies"][0]["sha256"]="e"*64
    write_json(plan_path,plan)
    write_json(plan_path.parent/fragment["moduleStage"]/"spine-static-rendering.json",fragment)
    manifest["staticSpineRendering"]=fragment
    for row in manifest["files"]:
        f=plan_path.parent/row["path"]
        row.update(sha256=_digest(f),bytes=f.stat().st_size)
    write_json(plan_path.parent/"manifest.json",manifest)
    request=json.loads(request_path.read_text())
    request["plan"]["sha256"]=_digest(plan_path)
    request["planManifest"]["sha256"]=_digest(plan_path.parent/"manifest.json")
    write_json(request_path,request)
    import pytest
    with pytest.raises(StaticSpineRefreshError,match="external dependency differs"):
        prepare(request_path,_digest(request_path),tmp_path/"denied")
    assert not (tmp_path/"denied").exists()
    request["refreshExternalDependencies"]=True
    write_json(request_path,request)
    with patch("monkey.prefab_static_spine_refresh._upgrade_atlas_mapping",return_value=[]):
        report=prepare(request_path,_digest(request_path),tmp_path/"approved")
    output=json.loads(Path(report["planPath"]).read_text())
    dependency=output["staticSpineRendering"]["externalDependencies"][0]
    expected=_digest(Path(__file__).resolve().parents[1]/"src/monkey/targets/NativeStaticMaskIdentity.cs")
    assert dependency["sha256"]==expected
    assert report["externalDependencyReplacements"][0]["previousSha256"]=="e"*64
    assert report["textureDecodeInvoked"]is False
    assert fragment["externalDependencies"][0]["sha256"]=="e"*64
