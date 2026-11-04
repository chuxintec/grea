import unittest
from pathlib import Path
import re
import tempfile
import json
import sys
import types
from unittest.mock import patch

from monkey.prefab_static_spine_rendering import _RENDER_HELPERS, _DERIVED_HELPER, emit, verify, verify_rendering


def test_prepare_and_emit_with_synthetic_resource_providers(tmp_path, monkeypatch):
    """Exercise real stage/asset/DTO plumbing; these providers prove no rendering."""
    from PIL import Image
    from monkey import io, prefab_static_spine_continuation as continuation, prefab_static_spine_rendering as rendering
    from monkey import prefab_spine_materials as materials, normalize
    from monkey.layout.verify import scan
    from test_prefab_static_spine_continuation import _minimal_full_fixture

    plan,ir,manifest,manifest_path,_,_=_minimal_full_fixture(tmp_path)
    manifest['sourceProfile']='cocos-2.4.15-bundle'
    manifest['assets'][0]['document']['instances'][1]['premultipliedAlpha']=False
    io.write_json(manifest_path,manifest)
    plan['sourceManifestSha256']=ir['sourceManifestSha256']=io.sha(manifest_path.read_bytes())
    plan['nodes']=[dict(sourceId=row['node'],active=True,parent=None,color=[255]*4)for row in plan['components']]
    stage=tmp_path/'plan';stage.mkdir()
    prepared=continuation.prepare(plan,ir,manifest,stage)['plan']
    importer=Path(rendering.__file__).parent/'targets/UnityImporter.cs'
    prepared['staticSpineRenderingTargetUnits']=dict(status='declared_generator_mapping_requires_native_verification',
        targetUnitsPerSourcePixel=1.0,coordinateSpace='source-pixels-to-ugui-local-units',
        runtimeCheck='exact-plan-node-RectTransform-fields-and-actual-canvas-reference-ppu',generatorSourceSha256=io.sha(importer.read_bytes()))
    # Resource codecs/profile readers are separate tested provider boundaries.
    engine=tmp_path/'engine.js';engine.write_text('synthetic source engine fixture')
    monkeypatch.setattr(rendering,'_source_engine',lambda path,pin:(engine,io.sha(engine.read_bytes())))
    monkeypatch.setattr(rendering,'_binary_slot_blend_modes',lambda raw:dict(spineVersion='3.8.99',
        blendModeCounts=dict(normal=2,additive=1,multiply=0,screen=0)))
    monkeypatch.setattr(materials,'_material',lambda *args:{'synthetic':True})
    monkeypatch.setattr(materials,'_program',lambda *args:({},dict(synthetic='profile')))
    monkeypatch.setattr(materials,'_source_semantics',lambda *args:{'synthetic':True})
    monkeypatch.setattr(normalize,'open_texture',lambda *args:Image.new('RGBA',(8,8),(10,40,70,255)))
    sdk=tmp_path/'sdk';files=[]
    for name in ('spine-csharp.dll','spine-unity.dll'):
        relative='Assets/Plugins/Spine38/EditorRuntime/'+name;path=sdk/relative
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'synthetic provider fixture')
        files.append(dict(path=relative,sha256=io.sha(path.read_bytes()),bytes=path.stat().st_size))
    backup=sdk/'manifest.json';io.write_json(backup,dict(files=files,producerManifestSHA256=rendering._RUNTIME_PRODUCER,
        upstream=dict(upstreamCommit=rendering._RUNTIME_COMMIT)))
    runtime=dict(status='pinned',assetsRoot=str(sdk),verifiedFiles=files,manifestPath=str(backup),manifestSha256=io.sha(backup.read_bytes()))
    result=rendering.prepare(prepared,stage,runtime,stage/'spine_static_rendering',source_engine_file=engine,expected_source_engine_sha256='fixture')
    fragment=result['rendering'];spec=fragment['dataAssets'][0]['factorySpec']
    assert spec['skeletonTextAssetPath'].endswith('.skel.bytes')
    assert spec['pages'][0]['sourceAtlasPage']=='page.png'
    assert spec['pages'][0]['nativeAtlasPage']==Path(spec['pages'][0]['textureAssetPath']).name
    assert spec['pages'][0]['textureSha256']
    assert spec['pages'][0]['variants'][0]['blendMode']=='additive'
    assert fragment['summary']['eligibleComponentCount']==2
    assert fragment['summary']['decodedPageCount']==1
    assert all(isinstance(row,dict)for row in fragment['payloads'])
    candidate=tmp_path/'candidate';emit(result['plan'],stage,candidate)
    assert not scan([row['target']for row in fragment['payloads']])
    assert (candidate/spec['atlasTextAssetPath']).read_bytes()==(stage/fragment['moduleStage']/next(
        row['source']for row in fragment['payloads']if row['target']==spec['atlasTextAssetPath'])).read_bytes()
from monkey.prefab_static_spine_rendering import prepare_rendering, StaticSpineRenderingError


def test_native_atlas_rewrite_changes_only_ordered_page_headers():
    from monkey.prefab_static_spine_rendering import rewrite_native_atlas
    raw = (b'\xef\xbb\xbfsource.png\r\nsize: 8,8\r\nsource.png\r\n  xy: 1,2\r\n\r\n'
           b'folder/second.png\nsize: 4,4\nregion\n  xy: 0,0\n')
    pages = [{'sourceAtlasPage': name, 'nativeAtlasPage': name, 'textureAssetPath': 'Assets/pages/'+target}
             for name, target in [('source.png','firsthash.png'), ('folder/second.png','secondhash.png')]]
    result, mapping = rewrite_native_atlas(raw, pages)
    assert result == raw.replace(b'\xef\xbb\xbfsource.png\r\n', b'\xef\xbb\xbffirsthash.png\r\n', 1).replace(
        b'folder/second.png\n', b'secondhash.png\n', 1)
    assert b'\r\nsource.png\r\n  xy: 1,2' in result  # region name is untouched
    assert [p['nativeAtlasPage'] for p in pages] == ['firsthash.png', 'secondhash.png']
    assert [p['sourceAtlasPage'] for p in mapping] == ['source.png', 'folder/second.png']


def test_native_atlas_rewrite_rejects_missing_reordered_or_ambiguous_pages():
    from monkey.prefab_static_spine_rendering import rewrite_native_atlas
    import pytest
    for pages in (
        [{'sourceAtlasPage':'b.png','nativeAtlasPage':'b.png','textureAssetPath':'Assets/h.png'}],
        [{'sourceAtlasPage':p,'nativeAtlasPage':p,'textureAssetPath':'Assets/h.png'} for p in ('a.png','b.png')],
    ):
        with pytest.raises(StaticSpineRenderingError):
            rewrite_native_atlas(b'a.png\nsize: 8,8\n\nb.png\nsize: 4,4\n', pages)


class StaticSpineRenderingVerificationTests(unittest.TestCase):
    def _plan(self):
        return {"staticSpineRendering": {"contract": "monkey-static-spine-rendering/1",
            "sourceManifestSha256": "a" * 64,
            "sourceEngine": {"sourceDefaultScale": 1.0},
            "unitMapping": {"targetUnitsPerSourcePixel": 1.0},
            "dataAssets": [{"sourceDataAssetId": "data-1", "factorySpec": {"sourceDefaultScale": 1.0}}], "components": [
            {"sourceComponentId": "prefab#1", "sourceNodeId": "prefab#0", "sourcePrefabId": "prefab", "sourceDataAssetId": "data-1",
             "eligible": True, "sourceVisible": True, "sourceComponentEnabled": True,
             "sourceSkinSerialized": False, "sourceAnimationSerialized": False, "sourceLoopSerialized": False},
            {"sourceComponentId": "prefab#2", "sourceNodeId": "prefab#0", "sourcePrefabId": "prefab", "sourceDataAssetId": "data-1",
             "eligible": True, "sourceVisible": False, "sourceComponentEnabled": True,
             "sourceSkinSerialized": False, "sourceAnimationSerialized": False, "sourceLoopSerialized": False},
            {"sourceComponentId": "prefab#3", "sourceNodeId": "prefab#0", "eligible": False,
             "sourceVisible": False, "gap": "SOURCE_PMA_UNKNOWN_OR_TRUE"},
        ]}}

    def _readback(self):
        return {"components": [
            {"sourceComponentId": "prefab#1", "verified": True, "rendererCreated": True, "sourceVisible": True,
             "sourceComponentEnabled": True, "sourceVisibleVerified": True, "rendererEnabled": True,
             "sourceCodeExecuted": False, "unitMappingVerified": True, "rendererGuid": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", "rendererLocalId": 1,
             "sourceDataAssetId": "data-1", "sourceDefaultScale": 1.0, "targetUnitsPerSourcePixel": 1.0,
             "canvasReferencePixelsPerUnit": 100.0, "dataScale": 0.01,
             "timeScale": 0.0,"trackTime": 0.0,
             "dataAssetGuid": "dddddddddddddddddddddddddddddddd", "dataAssetLocalId": 2, "poseVerified": True, "colorVerified": True,
             "materialReferencesVerified": True, "serializedFieldsVerified": True, "persistent": True, "dataPersistent": True,
             "meshVertexCount": 12, "meshTriangleCount": 6},
            {"sourceComponentId": "prefab#2", "verified": True, "rendererCreated": True, "sourceVisible": False,
             "sourceComponentEnabled": True, "sourceVisibleVerified": True, "rendererEnabled": True,
             "sourceCodeExecuted": False, "unitMappingVerified": True, "rendererGuid": "ffffffffffffffffffffffffffffffff", "rendererLocalId": 3,
             "sourceDataAssetId": "data-1", "sourceDefaultScale": 1.0, "targetUnitsPerSourcePixel": 1.0,
             "canvasReferencePixelsPerUnit": 100.0, "dataScale": 0.01,
             "timeScale": 0.0,"trackTime": 0.0,
             "dataAssetGuid": "dddddddddddddddddddddddddddddddd", "dataAssetLocalId": 2, "poseVerified": True, "colorVerified": True,
             "materialReferencesVerified": True, "serializedFieldsVerified": True, "persistent": True, "dataPersistent": True,
             "meshVertexCount": 0, "meshTriangleCount": 0},
            {"sourceComponentId": "prefab#3", "rendererCreated": False},
        ]}

    def test_hidden_eligible_renderer_keeps_structure_without_visible_mesh_requirement(self):
        self.assertEqual(verify_rendering(self._plan(), self._readback()), [])

    def test_missing_visible_mesh_is_a_gap(self):
        readback = self._readback()
        readback["components"][0]["meshVertexCount"] = 0
        gaps = verify_rendering(self._plan(), readback)
        self.assertIn("SPINE_RENDERING_VISIBLE_MESH_MISSING", {row["code"] for row in gaps})

    def test_nonfinite_pose_and_malformed_saved_identity_are_rejected(self):
        for changes,code in [({'trackTime':float('nan')},'SPINE_RENDERING_TRACK_TIME_NOT_ZERO'),
                             ({'timeScale':float('nan')},'SPINE_RENDERING_TIME_SCALE_NOT_FROZEN'),
                             ({'rendererLocalId':True},'SPINE_RENDERING_PERSISTENT_IDENTITY_INVALID')]:
            readback=self._readback();readback['components'][0].update(changes)
            self.assertIn(code,{row['code']for row in verify_rendering(self._plan(),readback)})

    def test_ineligible_source_cannot_be_promoted_to_renderer(self):
        readback = self._readback()
        readback["components"][2]["rendererCreated"] = True
        gaps = verify_rendering(self._plan(), readback)
        self.assertIn("SPINE_RENDERING_INELIGIBLE_HAS_RENDERER", {row["code"] for row in gaps})

    def test_missing_source_component_row_fails_full_denominator(self):
        readback = self._readback()
        readback["components"].pop(1)
        gaps = verify_rendering(self._plan(), readback)
        self.assertIn("SPINE_RENDERING_COMPONENT_DENOMINATOR_MISMATCH", {row["code"] for row in gaps})

    def test_graphic_fields_match_the_existing_unity_spine_binding_api(self):
        root = Path(__file__).resolve().parents[1]
        binding = (root / "src/monkey/targets/spine/UnitySpineBinding.cs").read_text()
        helper = (root / "src/monkey/targets/UnityStaticSpineRendering.cs").read_text()
        allowed = set(re.findall(r'pair\.Key != "([^"]+)"', binding))
        requested = set(re.findall(r'fields\["([^"]+)"\]', helper))
        self.assertTrue({"initialSkinName", "startingAnimation", "startingLoop", "timeScale", "pmaVertexColors"}.issubset(requested))
        self.assertTrue(requested.issubset(allowed))
        self.assertNotIn('fields["skin"]', helper)
        self.assertNotIn('fields["animation"]', helper)
        self.assertNotIn('fields["loop"]', helper)

    def test_helper_closure_excludes_legacy_conflicting_importer_and_stage(self):
        included = {source for source, _ in _RENDER_HELPERS}
        self.assertIn("targets/UnityStaticSpineRendering.cs", included)
        self.assertIn("targets/spine/UnitySpineNativeFactory.cs", included)
        self.assertNotIn("targets/spine/UnitySpineImporterIntegration.cs", included)
        self.assertNotIn("targets/spine/UnitySpineNativeStage.cs", included)
        self.assertEqual(_DERIVED_HELPER[0], "targets/UnityStaticSpineRenderingDerived.cs")

    def test_prepare_rejects_non_authoritative_continuation_contract(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "src/monkey/prefab_static_spine_continuation.py").read_text()
        match = re.search(r'^CONTRACT\s*=\s*["\']([^"\']+)', source, re.MULTILINE)
        self.assertIsNotNone(match)
        contract = match.group(1)
        stub = types.ModuleType("monkey.prefab_static_spine_continuation")
        stub.CONTRACT = contract
        engine = Path("unread-synthetic-engine.js")
        with tempfile.TemporaryDirectory() as temp, patch.dict(sys.modules, {"monkey.prefab_static_spine_continuation": stub}):
            with self.assertRaisesRegex(StaticSpineRenderingError, "source continuation"):
                prepare_rendering({"staticSpineContinuation": {"contract": "monkey-static-spine-continuation/1"}},
                    temp, {}, Path(temp) / "out", source_engine_file=engine,
                    expected_source_engine_sha256="d0a4b5323687196dc5ee3ff8f8cdc328e49148c1cf523b08b542e63dfb97b1329")

    def test_emit_and_verify_pin_candidate_payloads_and_saved_sidecar(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            plan_root = base / "plan"
            module = plan_root / "spine_static_rendering"
            payload = module / "spine-static-rendering-payloads" / "fixed" / "helper.cs"
            payload.parent.mkdir(parents=True)
            payload.write_bytes(b"static spine helper\n")
            row = self._readback()["components"][0]
            plan = {"staticSpineRendering": {
                "schemaVersion": 1, "contract": "monkey-static-spine-rendering/1",
                "sourceManifestSha256": "a" * 64,
                "sourceEngine": {"sourceDefaultScale": 1.0}, "unitMapping": {"targetUnitsPerSourcePixel": 1.0},
                "dataAssets": [{"sourceDataAssetId": "data-1", "factorySpec": {"sourceDefaultScale": 1.0}}],
                "moduleStage": "spine_static_rendering",
                "payloads": [{"source": "spine-static-rendering-payloads/fixed/helper.cs",
                              "target": "Assets/Game/Editor/Conversion/helper.cs", "sha256": __import__("hashlib").sha256(payload.read_bytes()).hexdigest(),
                              "bytes": payload.stat().st_size, "role": "helper"}],
                "components": [{"sourceComponentId": row["sourceComponentId"], "sourcePrefabId": "prefab", "eligible": True,
                                "sourceDataAssetId": row["sourceDataAssetId"], "sourceVisible": True,
                                "sourceComponentEnabled": True}],
            }}
            for name in ('spine-csharp.dll','spine-unity.dll'):
                source=payload.parent/name;source.write_bytes(b'synthetic SDK fixture')
                plan['staticSpineRendering']['payloads'].append(dict(source=source.relative_to(module).as_posix(),
                    target='Assets/Plugins/Spine38/EditorRuntime/'+name,
                    sha256=__import__('hashlib').sha256(source.read_bytes()).hexdigest(),bytes=source.stat().st_size))
            candidate = base / "candidate"
            emit(plan, plan_root, candidate)
            sidecar = candidate / "Analysis/Readback/SpineRendering/prefab.json"
            sidecar.parent.mkdir(parents=True)
            rendering = plan["staticSpineRendering"]
            plan_sha = __import__("hashlib").sha256((json.dumps(rendering, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()).hexdigest()
            sidecar.write_text(json.dumps({"contract": "monkey-static-spine-rendering-readback/1",
                "phase": "saved-prefab-reopen", "sourceManifestSha256": rendering["sourceManifestSha256"],
                "renderingPlanSha256": plan_sha, "sourcePrefabId": "prefab", "unityVersion": "6000.6.2f1",
                "runtimeAssemblies":[dict(target=p['target'],expectedSha256=p['sha256'],loadedSha256=p['sha256'],
                    loadedPath='/synthetic/'+Path(p['target']).name,verified=True)for p in rendering['payloads']if p['target'].endswith('.dll')],
                "components": [row]}))
            self.assertEqual(verify(plan, candidate), [])
            (candidate / "Assets/Game/Editor/Conversion/helper.cs").write_bytes(b"changed")
            self.assertIn("SPINE_RENDERING_CANDIDATE_PAYLOAD_PIN_MISMATCH",
                          {item["code"] for item in verify(plan, candidate)})


if __name__ == "__main__":
    unittest.main()
