import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from grea.recovery.prefab_spine_unity_readback import _verify_editor_runtime_variant, verify


class UnitySpineReadbackTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        root = (Path(temp.name) / 'UnityCandidate').resolve()
        root.mkdir()
        source_manifest = Path(temp.name) / 'source-manifest.json'
        source_manifest.write_text('{"schemaVersion":1}\n', encoding='utf-8')
        manifest_sha = hashlib.sha256(source_manifest.read_bytes()).hexdigest()
        ir_sha = 'b' * 64
        owner = 'gameAsset:prefab-a'
        owner_guid = 'a' * 32

        def asset(path, guid):
            full = root / path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text('native asset', encoding='utf-8')
            Path(str(full) + '.meta').write_text(f'fileFormatVersion: 2\nguid: {guid}\n', encoding='utf-8')

        data_path = 'Assets/Spine/Test/test_SkeletonData.asset'
        atlas_path = 'Assets/Spine/Test/test_SpineAtlas.asset'
        texture_path = 'Assets/Spine/Test/test.png'
        material_path = 'Assets/Spine/Test/test.mat'
        graphic_material_path = 'Assets/Spine/Test/test_graphic.mat'
        prefab_path = 'Assets/Prefabs/owner.prefab'
        ui_shader_path = 'Assets/Shaders/UnitySpineGraphicProfile.shader'
        ui_shader_source = Path(temp.name) / 'UnitySpineGraphicProfile.shader'
        ui_shader_bytes = b'Shader "Monkey/SpineSourceGraphicProfile/Colored" { SubShader {} }\n'
        ui_shader_source.write_bytes(ui_shader_bytes)
        ui_shader_sha = hashlib.sha256(ui_shader_bytes).hexdigest()
        data_guid, atlas_guid = '1' * 32, '2' * 32
        texture_guid, material_guid, graphic_material_guid = '3' * 32, '4' * 32, '5' * 32
        for path, guid in ((data_path, data_guid), (atlas_path, atlas_guid),
                           (texture_path, texture_guid), (material_path, material_guid),
                           (graphic_material_path, graphic_material_guid), (prefab_path, owner_guid)):
            asset(path, guid)
        target_shader = root / ui_shader_path
        target_shader.parent.mkdir(parents=True, exist_ok=True)
        target_shader.write_bytes(ui_shader_bytes)

        data_row = dict(sourceAssetId='spineAsset:test', skeletonDataAssetPath=data_path,
                        atlasAssetPath=atlas_path, nativeDataAssetGuid=None,
                        factoryInput=dict(sourceAssetId='spineAsset:test', skeletonDataAssetPath=data_path,
                                          atlasAssetPath=atlas_path, skeletonSha256='c' * 64,
                                          atlasSha256='d' * 64, expectedSpineVersion='3.8.99',
                                          shaderName='Monkey/SpineSourceProfile/Colored',
                                          shaderSha256='e' * 64, scale=1.0, premultipliedAlpha=True,
                                          graphicShaderAssetPath=ui_shader_path,
                                          graphicShaderName='Monkey/SpineSourceGraphicProfile/Colored',
                                          graphicShaderSha256=ui_shader_sha,
                                          requiredAnimations=['idle'], requiredSkins=['default'],
                                          pages=[dict(sourceAtlasPage='test.png', nativeAtlasPage='test.png',
                                                      sourceTextureSourceId='spineTexture:test',
                                                      textureAssetPath=texture_path,
                                                      normalMaterialAssetPath=material_path, variants=[])]))
        data_row['factoryInput']['pages'][0]['graphicNormalMaterialAssetPath'] = graphic_material_path
        dynamic_gaps = [dict(sourceProperty='playTimes', status='source_only_no_same_component_field'),
                        dict(sourceProperty='caching', status='source_only_runtime_cache_mapping_unresolved')]
        def component(source_id, node_id, has_data, gaps=None):
            return dict(sourceComponentId=source_id, sourcePrefabId=owner, sourceNodeId=node_id,
                        templateOrigin=dict(sourceComponentId=source_id, sourcePrefabId=owner,
                                            sourceNodeId=node_id, componentOriginChain=[source_id],
                                            nodeOriginChain=[node_id]),
                        sourceDataAssetId='spineAsset:test' if has_data else None,
                        sourceHasStaticDataReference=has_data, sourceTimeScale=1.0,
                        sourceTimeScaleVerified=True, persistentVisiblePose=True,
                        rendererKind='derive_from_target_node_transform',
                        rendererSelection=dict(status='declared_not_native_readback',
                                               sourceComponentId=source_id, rendererKind='SkeletonGraphic',
                                               targetNodeTransform='RectTransform', canvasIdentity='canvas:test',
                                               canvasReferencePixelsPerUnit=100.0,
                                               nativeRendererReadback='pending'),
                        targetFieldBindings=[dict(sourceProperty='skin', member='initialSkinName',
                                                  status='explicit', valueType='string', stringValue='default'),
                                             dict(sourceProperty='animation', member='startingAnimation',
                                                  status='explicit', valueType='string', stringValue='idle'),
                                             dict(sourceProperty='premultipliedAlpha', member='pmaVertexColors',
                                                  status='explicit', valueType='bool', boolValue=True)],
                        fieldGaps=gaps or [])
        bound = component(owner + '#4/components/0', owner + '#4', True, dynamic_gaps)
        unbound = component(owner + '#9/components/0', owner + '#9', False)
        stage_plan = dict(schemaVersion=1, contract='monkey-spine-native-binding/1',
                          sourceManifestSha256=manifest_sha, normalizedIrSha256=ir_sha,
                          sourceNativeBindingPlanSha256='f' * 64,
                          visualPolicy='native_renderer_enabled_timeScale_zero_source_timeScale_retained',
                          components=[bound, unbound], dataAssets=[data_row])
        stage_plan['unityGraphicShader'] = dict(status='native_ui_shader_source_hash_verified',
                                                shaderName='Monkey/SpineSourceGraphicProfile/Colored',
                                                sha256=ui_shader_sha, sourcePath=str(ui_shader_source),
                                                targetPath=ui_shader_path)
        stage_path = 'Assets/Game/Editor/Conversion/spine-native-binding-plan.json'
        full_stage_path = root / stage_path
        full_stage_path.parent.mkdir(parents=True, exist_ok=True)
        stage_bytes = (json.dumps(stage_plan, sort_keys=True) + '\n').encode()
        full_stage_path.write_bytes(stage_bytes)
        stage_sha = hashlib.sha256(stage_bytes).hexdigest()
        plan = dict(sourceManifestPath=str(source_manifest), sourceManifestSha256=manifest_sha,
                    sourceIrSha256=ir_sha, sourcePrefabs=[dict(sourceId=owner, path=prefab_path,
                                                                nodes=[bound['sourceNodeId'], unbound['sourceNodeId']])],
                    components=[dict(sourceId=bound['sourceComponentId'], type='sp.Skeleton', node=bound['sourceNodeId']),
                                dict(sourceId=unbound['sourceComponentId'], type='sp.Skeleton', node=unbound['sourceNodeId'])],
                    spineNativeStage=dict(contract='monkey-spine-native-stage/1', componentCount=2,
                                          expandedInstanceComponentCount=2, dataAssetCount=1,
                                          sourceManifestSha256=manifest_sha, sourceIrSha256=ir_sha,
                                          sourceNativeBindingPlanSha256='f' * 64,
                                          nativeBindingPlanPath=stage_path, nativeBindingPlanSha256=stage_sha),
                    nodes=[dict(sourceId=bound['sourceNodeId'], color=[10, 20, 30, 40]),
                           dict(sourceId=unbound['sourceNodeId'], color=[10, 20, 30, 40])])
        plan['nodes'][0].update(active=True, parent=None)
        plan['nodes'][1].update(active=True, parent=None)
        plan['staticMasks'] = dict(masks=[])
        def component_readback(row, has_data):
            is_unbound = not has_data
            return dict(sourceComponentId=row['sourceComponentId'], rendererKind='SkeletonGraphic',
                        nativeComponentType='Spine.Unity.SkeletonGraphic',
                        sourceDataAssetId=row['sourceDataAssetId'] if has_data else '',
                        nativeDataAssetPath=data_path if has_data else None,
                        nativeDataAssetGuid=data_guid if has_data else None,
                        staticDataBound=has_data, sourceDataUnbound=is_unbound, enabled=True,
                        componentTypeVerified=True, dataReferenceVerified=True,
                        dataAssetContentVerified=has_data, mappedStaticFieldsVerified=True,
                        fieldsVerified=not bool(row['fieldGaps']),
                        pmaMaterialProfileRequired=has_data,
                        pmaMaterialProfileVerified=has_data,
                        pmaMaterialProfileNotApplicable=is_unbound,
                        rendererMaterialRequired=has_data,
                        rendererMaterialVerified=True,
                        allowMultipleCanvasRenderers=has_data,
                        customMaterialOverrideCount=0,
                        rendererBaseMaterialShader='Monkey/SpineSourceGraphicProfile/Colored' if has_data else None,
                        rendererBaseMaterialAssetPath=graphic_material_path if has_data else None,
                        rendererBaseMaterialGuid=graphic_material_guid if has_data else None,
                        rendererMaterialForRenderingShader='Monkey/SpineSourceGraphicProfile/Colored' if has_data else None,
                        canvasRendererMaterialShaders=['', 'Monkey/SpineSourceGraphicProfile/Colored'] if has_data else [],
                        canvasRendererMaterialAssetPaths=['', graphic_material_path] if has_data else [],
                        rendererMainTextureAssetPath=texture_path if has_data else None,
                        rendererPresentation=dict(sourceComponentId=row['sourceComponentId'],
                                                 sdkInstructionsType='Spine.Unity.SkeletonRendererInstruction',
                                                 instructionCount=1, canvasRendererCount=1, sdkEventAttached=True,
                                                 materialPairsVerified=True, nativeMaterialStatus='verified_active_submesh_materials',
                                                 nativeMaterialVerified=True, pose=None,
                                                 textureVerificationMethod='serialized RawImage.texture identity plus exact Spine callback SetMaterial(material, texture); Unity CanvasRenderer exposes no public texture getter',
                                                 gaps=[], renderers=[dict(index=0,
                                                    sourceMaterialId='spineAsset:test/test.png/normal',
                                                    textureSourceId='spineTexture:test', blendMode='normal',
                                                    actualMaterialShader='Monkey/SpineSourceGraphicProfile/Colored',
                                                    actualMaterialName='test_normal_graphic', actualTextureName='test',
                                                    rawImageEnabled=True, rawImageMaskable=True,
                                                    rawImageMaterialReferenceVerified=True,
                                                    materialReferenceVerified=True, textureReferenceVerified=True,
                                                    blendVerified=True)]) if has_data else None,
                        nativeComplete=has_data and not row['fieldGaps'],
                        dynamicAssignmentUnverified=is_unbound,
                        sourceOnlyFieldGaps=[f"source_field_unmapped:{x['sourceProperty']}:{x['status']}"
                                             for x in row['fieldGaps']],
                        gaps=(['dynamic_skeleton_data_assignment_unverified'] if is_unbound else []) +
                             [f"source_field_unmapped:{x['sourceProperty']}:{x['status']}" for x in row['fieldGaps']])
        components = [component_readback(bound, True), component_readback(unbound, False)]
        def visual(row):
            return dict(sourceComponentId=row['sourceComponentId'], rendererKind='Spine.Unity.SkeletonGraphic',
                        sourceTimeScale=1.0, nativeTimeScale=0.0, sourceTimeScaleVerified=True,
                        rendererEnabled=True, persistentVisiblePose=True,
                        sourceColor=[10, 20, 30, 40], nativeColor=[10.0, 20.0, 30.0, 40.0],
                        sourceColorVerified=True, nativeColorVerified=True)
        asset_readback = dict(sourceAssetId='spineAsset:test', skeletonDataAssetPath=data_path,
                              skeletonDataAssetGuid=data_guid, atlasAssetPath=atlas_path,
                              atlasAssetGuid=atlas_guid, skeletonSha256='c' * 64,
                              atlasSha256='d' * 64, spineVersion='3.8.99',
                              sourceMaterialProfile='cocos24-builtin-spine-material-v1',
                              profileShaderName='Monkey/SpineSourceProfile/Colored',
                              profileShaderSha256='e' * 64, premultipliedAlpha=True, scale=1.0,
                              uiGraphicShaderName='Monkey/SpineSourceGraphicProfile/Colored',
                              uiGraphicShaderSha256=ui_shader_sha, uiGraphicShaderVerified=True,
                              scaleVerified=True, nativeAssetIdentityVerified=True, boneCount=5, slotCount=1,
                              savedSourceReferencesVerified=True, sourceProfileMaterialsVerified=True,
                              staticDataVerified=True, animations=['idle'], skins=['default'], gaps=[],
                              pages=[dict(sourceAtlasPage='test.png', nativeAtlasPage='test.png',
                                          sourceTextureSourceId='spineTexture:test', textureGuid=texture_guid,
                                          normalMaterialGuid=material_guid, variantModes=[],
                                          variantMaterialGuids=[], graphicNormalMaterialPath=graphic_material_path,
                                          graphicNormalMaterialGuid=graphic_material_guid,
                                          graphicVariantMaterialPaths=[], graphicVariantMaterialGuids=[],
                                          referencesVerified=True)])
        readback = dict(schemaVersion=1, sourcePrefabId=owner, sourceManifestSha256=manifest_sha,
                        normalizedIrSha256=ir_sha, staticNativeVerified=True, dynamicBehaviorComplete=False,
                        visualPolicy=stage_plan['visualPolicy'], componentCount=2, dataAssetCount=1,
                        components=components, dataAssets=[asset_readback],
                        visualComponents=[visual(bound), visual(unbound)], stageGaps=[
                            dict(sourceId=bound['sourceComponentId'], code='SPINE_COMPONENT_READBACK_GAP',
                                 message='source_field_unmapped:playTimes:source_only_no_same_component_field'),
                            dict(sourceId=bound['sourceComponentId'], code='SPINE_COMPONENT_READBACK_GAP',
                                 message='source_field_unmapped:caching:source_only_runtime_cache_mapping_unresolved'),
                            dict(sourceId=unbound['sourceComponentId'], code='SPINE_COMPONENT_READBACK_GAP',
                                 message='dynamic_skeleton_data_assignment_unverified')], failures=[])
        spine_dir = root / 'Analysis/Readback/Spine'
        spine_dir.mkdir(parents=True)
        (spine_dir / f'{owner_guid}.json').write_text(json.dumps(readback), encoding='utf-8')
        editor_readback = dict(sourcePrefabs=[dict(sourceId=owner, guid=owner_guid, path=prefab_path)])
        return temp, root, plan, editor_readback, readback

    def test_accepts_static_readback_and_keeps_dynamic_gaps_incomplete(self):
        temp, root, plan, editor_readback, _ = self.fixture()
        self.addCleanup(temp.cleanup)
        diagnostics = verify(plan, root, editor_readback)
        errors = [row for row in diagnostics if row['severity'] == 'error']
        warnings = [row for row in diagnostics if row['code'] == 'SPINE_DYNAMIC_BEHAVIOR_INCOMPLETE']
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 2)

    def test_rejects_native_renderer_kind_that_differs_from_declared_context(self):
        temp, root, plan, editor_readback, _ = self.fixture()
        self.addCleanup(temp.cleanup)
        path = root / 'Analysis/Readback/Spine' / f'{"a" * 32}.json'
        saved = json.loads(path.read_text())
        saved['components'][0]['rendererKind'] = 'SkeletonAnimation'
        saved['components'][0]['nativeComponentType'] = 'Spine.Unity.SkeletonAnimation'
        path.write_text(json.dumps(saved), encoding='utf-8')
        diagnostics = verify(plan, root, editor_readback)
        self.assertTrue(any('renderer kind differs from declared target context' in d['message']
                            for d in diagnostics if d['severity'] == 'error'))

    def test_rejects_missing_declared_renderer_context(self):
        temp, root, plan, editor_readback, _ = self.fixture()
        self.addCleanup(temp.cleanup)
        stage_path = root / plan['spineNativeStage']['nativeBindingPlanPath']
        stage = json.loads(stage_path.read_text())
        del stage['components'][0]['rendererSelection']
        stage_bytes = (json.dumps(stage, sort_keys=True) + '\n').encode()
        stage_path.write_bytes(stage_bytes)
        plan['spineNativeStage']['nativeBindingPlanSha256'] = hashlib.sha256(stage_bytes).hexdigest()
        diagnostics = verify(plan, root, editor_readback)
        self.assertTrue(any('missing verified visible-pose/timeScale/node evidence' in d['message']
                            for d in diagnostics if d['severity'] == 'error'))

    def test_rejects_source_pin_component_guid_pma_and_dynamic_overclaim(self):
        temp, root, plan, editor_readback, readback = self.fixture()
        self.addCleanup(temp.cleanup)
        self.assertEqual([d for d in verify(plan, root, editor_readback) if d['severity'] == 'error'], [])

        plan['spineNativeStage']['sourceIrSha256'] = '0' * 64
        self.assertTrue(any(d['severity'] == 'error' for d in verify(plan, root, editor_readback)))
        plan['spineNativeStage']['sourceIrSha256'] = plan['sourceIrSha256']

        saved_path = root / 'Analysis/Readback/Spine' / f'{"a" * 32}.json'
        broken = json.loads(saved_path.read_text())
        broken['dynamicBehaviorComplete'] = True
        broken['components'][0]['mappedStaticFieldsVerified'] = False
        broken['components'][0]['pmaMaterialProfileVerified'] = False
        saved_path.write_text(json.dumps(broken), encoding='utf-8')
        diagnostics = verify(plan, root, editor_readback)
        self.assertTrue(any('policy flags differ' in d['message'] for d in diagnostics))
        self.assertTrue(any('mappedStaticFieldsVerified' in d['message'] for d in diagnostics))
        self.assertTrue(any('PMA material profile' in d['message'] for d in diagnostics))

    def test_rejects_guid_path_and_unknown_dynamic_gap(self):
        temp, root, plan, editor_readback, _ = self.fixture()
        self.addCleanup(temp.cleanup)
        plan['nodes'][0]['sourceId'] = 'other-node'
        diagnostics = verify(plan, root, editor_readback)
        self.assertTrue(any('source/native color proof' in d['message'] for d in diagnostics))

        plan['nodes'][0]['sourceId'] = 'gameAsset:prefab-a#4'
        path = root / 'Analysis/Readback/Spine' / f'{"a" * 32}.json'
        saved = json.loads(path.read_text())
        saved['dataAssets'][0]['skeletonDataAssetGuid'] = '9' * 32
        saved['components'][0]['gaps'].append('not-an-allowlisted-gap')
        path.write_text(json.dumps(saved), encoding='utf-8')
        diagnostics = verify(plan, root, editor_readback)
        self.assertTrue(any('readback GUID differs from target meta' in d['message'] for d in diagnostics))
        self.assertTrue(any('gap set differs' in d['message'] for d in diagnostics))

    def test_rejects_wrong_ui_shader_material_texture_and_blend(self):
        mutations = [
            (lambda saved: saved['components'][0]['rendererPresentation']['renderers'][0].update(
                actualMaterialShader='Wrong/UI/Shader'), 'renderer material shader'),
            (lambda saved: saved['components'][0].update(rendererBaseMaterialAssetPath='Assets/Spine/Test/wrong.mat'),
             'base material path/GUID/shader'),
            (lambda saved: saved['dataAssets'][0]['pages'][0].update(graphicNormalMaterialGuid='9' * 32),
             'Graphic normal material GUID'),
            (lambda saved: saved['components'][0]['rendererPresentation']['renderers'][0].update(
                textureSourceId='spineTexture:wrong', textureReferenceVerified=False, actualTextureName='wrong'),
             'material/texture/blend pair'),
            (lambda saved: saved['components'][0]['rendererPresentation']['renderers'][0].update(
                blendMode='multiply', blendVerified=False), 'material/texture/blend pair'),
        ]
        for mutate, expected_message in mutations:
            with self.subTest(expected_message=expected_message):
                temp, root, plan, editor_readback, _ = self.fixture()
                try:
                    saved_path = root / 'Analysis/Readback/Spine' / f'{"a" * 32}.json'
                    saved = json.loads(saved_path.read_text())
                    mutate(saved)
                    saved_path.write_text(json.dumps(saved), encoding='utf-8')
                    diagnostics = verify(plan, root, editor_readback)
                    self.assertTrue(any(expected_message in row['message'] for row in diagnostics),
                                    [row['message'] for row in diagnostics])
                finally:
                    temp.cleanup()

    def test_rejects_wrong_canvas_child_material_but_accepts_empty_root_slot(self):
        mutations = [
            (lambda saved: saved['components'][0].update(
                canvasRendererMaterialShaders=['Wrong/Shader', 'Monkey/SpineSourceGraphicProfile/Colored']),
             'CanvasRenderer material shader set differs'),
            (lambda saved: saved['components'][0].update(
                canvasRendererMaterialAssetPaths=['', 'Assets/Spine/Test/wrong.mat']),
             'CanvasRenderer material asset path set differs'),
        ]
        for mutate, expected_message in mutations:
            with self.subTest(expected_message=expected_message):
                temp, root, plan, editor_readback, _ = self.fixture()
                try:
                    saved_path = root / 'Analysis/Readback/Spine' / f'{"a" * 32}.json'
                    saved = json.loads(saved_path.read_text())
                    mutate(saved)
                    saved_path.write_text(json.dumps(saved), encoding='utf-8')
                    diagnostics = verify(plan, root, editor_readback)
                    self.assertTrue(any(expected_message in row['message'] for row in diagnostics),
                                    [row['message'] for row in diagnostics])
                finally:
                    temp.cleanup()

    def test_accepts_transient_mask_stencil_variant_only_with_exact_base_and_ancestry_proof(self):
        temp, root, plan, editor_readback, _ = self.fixture()
        self.addCleanup(temp.cleanup)
        mask_node = 'gameAsset:prefab-a#3'
        plan['nodes'][0].update(active=False, parent=mask_node)
        plan['nodes'].append(dict(sourceId=mask_node, active=True, parent=None))
        plan['sourcePrefabs'][0]['nodes'].append(mask_node)
        plan['staticMasks']['masks'] = [dict(sourceId=mask_node + '/components/9', node=mask_node, enabled=True)]
        saved_path = root / 'Analysis/Readback/Spine' / f'{"a" * 32}.json'
        saved = json.loads(saved_path.read_text())
        component = saved['components'][0]
        component['canvasRendererMaterialAssetPaths'] = ['', '']
        row = component['rendererPresentation']['renderers'][0]
        row.update(baseMaterialAssetPath='Assets/Spine/Test/test_graphic.mat',
                   baseMaterialAssetGuid='5' * 32, baseMaterialShader='Monkey/SpineSourceGraphicProfile/Colored',
                   baseMaterialTextureAssetPath='Assets/Spine/Test/test.png', baseMaterialTextureGuid='3' * 32,
                   stencilDepth=1, stencilRootSortCanvasPath='CanvasRoot',
                   stencilMaskAncestorSourceIds=[mask_node + '/components/9'],
                   stencilReference=1, stencilComparison=3, stencilOperation=0,
                   stencilReadMask=1, stencilWriteMask=0, stencilColorMask=15, stencilUseAlphaClip=0,
                   baseMaterialPersistentReferenceVerified=True, modifiedMaterialShaderMatchesBase=True,
                   nonStencilMaterialPropertiesMatch=True, stencilAncestryVerified=True,
                   stencilConfigurationVerified=True, transientStencilVariantVerified=True)
        saved_path.write_text(json.dumps(saved), encoding='utf-8')
        self.assertEqual([d for d in verify(plan, root, editor_readback) if d['severity'] == 'error'], [])

    def test_rejects_transient_stencil_without_exact_properties_base_or_mask_ancestry(self):
        mutations = [
            (lambda row, comp: row.update(nonStencilMaterialPropertiesMatch=False), 'nonStencilMaterialPropertiesMatch'),
            (lambda row, comp: row.update(stencilComparison=8), 'stencil material state'),
            (lambda row, comp: row.update(baseMaterialAssetGuid='9' * 32), 'base material GUID'),
            (lambda row, comp: row.update(stencilMaskAncestorSourceIds=['wrong-mask']), 'mask ancestry'),
            (lambda row, comp: row.pop('transientStencilVariantVerified'), 'transientStencilVariantVerified'),
        ]
        for mutate, expected_message in mutations:
            with self.subTest(expected_message=expected_message):
                temp, root, plan, editor_readback, _ = self.fixture()
                try:
                    plan['staticMasks']['masks'] = [dict(sourceId='gameAsset:prefab-a#4/components/9',
                                                         node='gameAsset:prefab-a#4', enabled=True)]
                    saved_path = root / 'Analysis/Readback/Spine' / f'{"a" * 32}.json'
                    saved = json.loads(saved_path.read_text())
                    component = saved['components'][0]
                    component['canvasRendererMaterialAssetPaths'] = ['', '']
                    row = component['rendererPresentation']['renderers'][0]
                    row.update(baseMaterialAssetPath='Assets/Spine/Test/test_graphic.mat',
                               baseMaterialAssetGuid='5' * 32, baseMaterialShader='Monkey/SpineSourceGraphicProfile/Colored',
                               baseMaterialTextureAssetPath='Assets/Spine/Test/test.png', baseMaterialTextureGuid='3' * 32,
                               stencilDepth=1, stencilRootSortCanvasPath='CanvasRoot',
                               stencilMaskAncestorSourceIds=['gameAsset:prefab-a#4/components/9'],
                               stencilReference=1, stencilComparison=3, stencilOperation=0,
                               stencilReadMask=1, stencilWriteMask=0, stencilColorMask=15, stencilUseAlphaClip=0,
                               baseMaterialPersistentReferenceVerified=True, modifiedMaterialShaderMatchesBase=True,
                               nonStencilMaterialPropertiesMatch=True, stencilAncestryVerified=True,
                               stencilConfigurationVerified=True, transientStencilVariantVerified=True)
                    mutate(row, component)
                    saved_path.write_text(json.dumps(saved), encoding='utf-8')
                    diagnostics = verify(plan, root, editor_readback)
                    self.assertTrue(any(expected_message in row['message'] for row in diagnostics),
                                    [row['message'] for row in diagnostics])
                finally:
                    temp.cleanup()

    def test_unbound_null_data_id_accepts_only_exact_empty_graphic_presentation(self):
        def empty_presentation():
            return dict(sourceComponentId='', sdkInstructionsType='', instructionCount=0,
                        canvasRendererCount=0, sdkEventAttached=False, materialPairsVerified=False,
                        nativeMaterialStatus='', nativeMaterialVerified=False, textureVerificationMethod='',
                        pose=dict(initialized=False, animationStateInitialized=False,
                                  sourceDataIdentityVerified=False, dataVersion='', boneCount=0, slotCount=0,
                                  activeDrawableAttachmentCount=0, nonNullAttachmentCount=0,
                                  sourceSkin='', actualSkin='', sourceSkinVerified=False,
                                  runtimeDefaultSkinName='', defaultSkinRuntimeNull=False,
                                  sourceAnimation='', actualAnimation='', trackTime=0.0,
                                  sourceAnimationVerified=False, allSlotsHaveNoDrawableAttachment=False,
                                  emptyRendererStateVerified=False, emptyPoseVerified=False,
                                  gaps=[], activeDrawableAttachments=[]),
                        gaps=[], renderers=[])

        temp, root, plan, editor_readback, _ = self.fixture()
        self.addCleanup(temp.cleanup)
        path = root / 'Analysis/Readback/Spine' / f'{"a" * 32}.json'
        saved = json.loads(path.read_text())
        unbound = saved['components'][1]
        unbound['sourceDataAssetId'] = ''  # source plan pins null; Unity JsonUtility serializes string as empty.
        unbound['rendererPresentation'] = empty_presentation()
        path.write_text(json.dumps(saved), encoding='utf-8')
        diagnostics = verify(plan, root, editor_readback)
        self.assertFalse(any(row['severity'] == 'error' for row in diagnostics),
                         [row['message'] for row in diagnostics])
        self.assertFalse(unbound['nativeComplete'])
        self.assertIn('dynamic_skeleton_data_assignment_unverified', unbound['gaps'])

        mutations = [
            lambda row: row['rendererPresentation'].update(nativeMaterialVerified=True),
            lambda row: row['rendererPresentation']['renderers'].append({'index': 0}),
            lambda row: row['rendererPresentation']['pose'].update(runtimeDefaultSkinName='default'),
            lambda row: row['rendererPresentation']['pose'].update(defaultSkinRuntimeNull=True),
            lambda row: row.update(sourceDataAssetId='unexpected-asset'),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                broken = json.loads(path.read_text())
                mutate(broken['components'][1])
                path.write_text(json.dumps(broken), encoding='utf-8')
                diagnostics = verify(plan, root, editor_readback)
                self.assertTrue(any(row['severity'] == 'error' and (
                    'source data asset ID differs' in row['message'] or
                    'incorrectly claims an applied UI material profile' in row['message'])
                    for row in diagnostics), [row['message'] for row in diagnostics])

    def test_accepts_only_verified_empty_pose_with_persistent_material_pairs(self):
        temp, root, plan, editor_readback, _ = self.fixture()
        self.addCleanup(temp.cleanup)
        path = root / 'Analysis/Readback/Spine' / f'{"a" * 32}.json'
        saved = json.loads(path.read_text())
        presentation = saved['components'][0]['rendererPresentation']
        presentation.update(nativeMaterialStatus='verified_empty_pose_with_persistent_material_pairs',
                            instructionCount=0, canvasRendererCount=0, renderers=[], materialPairsVerified=True,
                            pose=dict(initialized=True, animationStateInitialized=True,
                                      sourceDataIdentityVerified=True, dataVersion='3.8.99',
                                      boneCount=5, slotCount=1, activeDrawableAttachmentCount=0,
                                      nonNullAttachmentCount=0, sourceSkin='default', actualSkin='default',
                                      sourceSkinVerified=True, runtimeDefaultSkinName='default',
                                      defaultSkinRuntimeNull=False, sourceAnimation='idle', actualAnimation='idle',
                                      trackTime=0.0, sourceAnimationVerified=True,
                                      allSlotsHaveNoDrawableAttachment=True, emptyRendererStateVerified=True,
                                      emptyPoseVerified=True, gaps=[], activeDrawableAttachments=[]))
        saved['components'][0]['canvasRendererMaterialShaders'] = ['']
        saved['components'][0]['canvasRendererMaterialAssetPaths'] = ['']
        path.write_text(json.dumps(saved), encoding='utf-8')
        diagnostics = verify(plan, root, editor_readback)
        self.assertEqual([row for row in diagnostics if row['severity'] == 'error'], [])

        default_alias = json.loads(json.dumps(saved))
        alias_pose = default_alias['components'][0]['rendererPresentation']['pose']
        alias_pose.update(actualSkin='', runtimeDefaultSkinName='default', defaultSkinRuntimeNull=True)
        path.write_text(json.dumps(default_alias), encoding='utf-8')
        diagnostics = verify(plan, root, editor_readback)
        self.assertEqual([row for row in diagnostics if row['severity'] == 'error'], [])
        alias_pose['runtimeDefaultSkinName'] = 'other'
        path.write_text(json.dumps(default_alias), encoding='utf-8')
        diagnostics = verify(plan, root, editor_readback)
        self.assertTrue(any(row['severity'] == 'error' and 'skin representation differs' in row['message']
                            for row in diagnostics))

        bad_poses = [
            ('initialized', False), ('animationStateInitialized', False),
            ('sourceDataIdentityVerified', False), ('sourceSkinVerified', False),
            ('sourceAnimationVerified', False), ('trackTime', 0.1),
            ('activeDrawableAttachmentCount', 1), ('allSlotsHaveNoDrawableAttachment', False),
            ('emptyRendererStateVerified', False), ('emptyPoseVerified', False),
        ]
        for key, value in bad_poses:
            with self.subTest(key=key):
                broken = json.loads(json.dumps(saved))
                broken['components'][0]['rendererPresentation']['pose'][key] = value
                path.write_text(json.dumps(broken), encoding='utf-8')
                diagnostics = verify(plan, root, editor_readback)
                self.assertTrue(any(row['severity'] == 'error' and ('empty pose' in row['message'] or
                                'zero drawable pose' in row['message']) for row in diagnostics),
                                [row['message'] for row in diagnostics])

        broken = json.loads(json.dumps(saved))
        broken['components'][0]['rendererPresentation']['materialPairsVerified'] = False
        path.write_text(json.dumps(broken), encoding='utf-8')
        diagnostics = verify(plan, root, editor_readback)
        self.assertTrue(any('presentation identity/verification differs' in row['message'] for row in diagnostics))

    def runtime_fixture(self):
        temp = tempfile.TemporaryDirectory(dir='/private/tmp')
        root = Path(temp.name) / 'UnityCandidate'
        root.mkdir()
        manifest = Path(temp.name) / 'source-manifest.json'
        manifest.write_text('{"schemaVersion":1}\n', encoding='utf-8')
        manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
        ir_sha = 'b' * 64
        unity_rel = 'Assets/Plugins/Spine38/EditorRuntime/spine-unity.dll'
        core_rel = 'Assets/Plugins/Spine38/EditorRuntime/spine-csharp.dll'
        unity_bytes, core_bytes = b'editor unity assembly', b'editor core assembly'
        unity_path, core_path = root / unity_rel, root / core_rel
        unity_path.parent.mkdir(parents=True, exist_ok=True)
        unity_path.write_bytes(unity_bytes)
        core_path.write_bytes(core_bytes)
        unity_sha = hashlib.sha256(unity_bytes).hexdigest()
        core_sha = hashlib.sha256(core_bytes).hexdigest()
        evidence_path = Path(temp.name) / 'editor-runtime-evidence.json'
        runtime_manifest_sha = 'c' * 64
        evidence_path.write_text(json.dumps(dict(status='verified_editor_source_build',
                                                 sourceManifestSha256=runtime_manifest_sha,
                                                 cocosCompatibilityFallbacksIncluded=False)), encoding='utf-8')
        evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        unity_refs = [dict(name='UnityEditor.CoreModule', version='0.0.0.0'),
                      dict(name='spine-csharp', version='0.0.0.0'),
                      dict(name='UnityEngine.CoreModule', version='0.0.0.0')]
        core_refs = [dict(name='netstandard', version='2.1.0.0')]
        variant = dict(status='verified_editor_source_build', sourceEvidencePath=str(evidence_path),
                       sourceEvidenceSha256=evidence_sha, sourceManifestSha256=runtime_manifest_sha,
                       assemblyLoadVerification=dict(status='not_run', expectedAssemblyPath=unity_rel,
                           expectedAssemblySha256=unity_sha, expectedCoreAssemblyPath=core_rel,
                           expectedCoreAssemblySha256=core_sha, expectedUnityEditorReference=True,
                           requiredActualFields=['typeof(SkeletonGraphic).Assembly.Location', 'assemblySha256',
                                                 'referencedAssemblies', 'unityEditorReferencePresent']),
                       assemblies={
                           'spine-unity.dll': dict(runtimeImportPath=unity_rel, sha256=unity_sha,
                                                   assemblyName='spine-unity', assemblyVersion='0.0.0.0',
                                                   references=unity_refs),
                           'spine-csharp.dll': dict(runtimeImportPath=core_rel, sha256=core_sha,
                                                    assemblyName='spine-csharp', assemblyVersion='0.0.0.0',
                                                    references=core_refs),
                       })
        report = dict(schemaVersion=1, status='verified_editor_assembly_loaded',
                      sourceManifestSha256=manifest_sha, normalizedIrSha256=ir_sha,
                      editorVariantRequired=True, expectedSpineUnityPath=unity_rel,
                      expectedSpineUnitySha256=unity_sha, expectedSpineCorePath=core_rel,
                      expectedSpineCoreSha256=core_sha,
                      actualSpineUnityLocation=str(unity_path.resolve()), actualSpineUnityCandidatePath=unity_rel,
                      actualSpineUnitySha256=unity_sha, actualSpineUnityAssemblyName='spine-unity',
                      actualSpineUnityAssemblyVersion='0.0.0.0',
                      actualSpineCoreLocation=str(core_path.resolve()), actualSpineCoreCandidatePath=core_rel,
                      actualSpineCoreSha256=core_sha, actualSpineCoreAssemblyName='spine-csharp',
                      actualSpineCoreAssemblyVersion='0.0.0.0', spineUnityReferences=unity_refs,
                      unityEditorReferencePresent=True, spineCoreReferenceVerified=True, verified=True, gaps=[])
        readback = root / 'Analysis/Readback/Spine/runtime-assembly-load.json'
        readback.parent.mkdir(parents=True)
        readback.write_text(json.dumps(report), encoding='utf-8')
        instruction = dict(sourceManifestPath=str(manifest), sourceManifestSha256=manifest_sha,
                           sourceIrSha256=ir_sha, spineNativeStage=dict(editorRuntimeVariant=variant))
        return temp, root, instruction, readback

    def test_editor_runtime_variant_requires_actual_pair_and_references(self):
        temp, root, instruction, _ = self.runtime_fixture()
        self.addCleanup(temp.cleanup)
        self.assertEqual(_verify_editor_runtime_variant(instruction, root), [])

    def test_editor_runtime_variant_rejects_missing_readback_and_wrong_binary_hash(self):
        temp, root, instruction, readback_path = self.runtime_fixture()
        self.addCleanup(temp.cleanup)
        readback_path.unlink()
        diagnostics = _verify_editor_runtime_variant(instruction, root)
        self.assertTrue(any('readback is missing' in row['message'] for row in diagnostics))

        temp2, root2, instruction2, path2 = self.runtime_fixture()
        self.addCleanup(temp2.cleanup)
        broken = json.loads(path2.read_text())
        broken['actualSpineUnitySha256'] = '0' * 64
        path2.write_text(json.dumps(broken), encoding='utf-8')
        diagnostics = _verify_editor_runtime_variant(instruction2, root2)
        self.assertTrue(any('Loaded Editor assembly SHA differs' in row['message'] for row in diagnostics))

    def test_editor_runtime_variant_rejects_wrong_path_and_core_editor_references(self):
        temp, root, instruction, path = self.runtime_fixture()
        self.addCleanup(temp.cleanup)
        broken = json.loads(path.read_text())
        broken['actualSpineUnityCandidatePath'] = 'Assets/Plugins/Spine38/spine-unity.dll'
        broken['spineUnityReferences'] = [row for row in broken['spineUnityReferences']
                                          if row['name'] != 'UnityEditor.CoreModule']
        broken['unityEditorReferencePresent'] = False
        path.write_text(json.dumps(broken), encoding='utf-8')
        diagnostics = _verify_editor_runtime_variant(instruction, root)
        self.assertTrue(any('Loaded Editor assembly path' in row['message'] for row in diagnostics))
        self.assertTrue(any('required UnityEditor reference' in row['message'] for row in diagnostics))


if __name__ == '__main__':
    unittest.main()
