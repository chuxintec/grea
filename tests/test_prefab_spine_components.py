import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from monkey.prefab_spine_components import build_component_binding_plan, emit_spine_emission, prepare_spine_emission

CACHE_MODE_EVIDENCE = {'values': {'0': 'REALTIME', '1': 'SHARED_CACHE', '2': 'PRIVATE_CACHE'}}
DEFAULT_EVIDENCE = {
    'status': 'verified_source_and_target_defaults', 'valuesMatch': True,
    'sourceValues': {'skeletonData': None, 'defaultSkin': '', 'defaultAnimation': '', 'loop': True, 'playTimes': 0,
                     'timeScale': 1, 'premultipliedAlpha': True, 'useTint': False,
                     'debugBones': False, 'debugSlots': False, 'debugMesh': False,
                     'enableBatch': False, 'cacheMode': 0},
}


def source_component(component_id, data_id, *, fields=None, sample='P01'):
    fields = fields or {}
    properties = {
        'skeletonData': {'status': 'explicit' if data_id else 'not_serialized_default_unresolved',
                         'sourceFields': {'_N$skeletonData': {'__uuid__': data_id.split(':', 1)[1]}} if data_id else {}},
        'skin': {'status': 'explicit' if 'defaultSkin' in fields else 'not_serialized_default_unresolved',
                 'sourceFields': {'defaultSkin': fields['defaultSkin']} if 'defaultSkin' in fields else {}},
        'animation': {'status': 'explicit' if 'defaultAnimation' in fields else 'not_serialized_default_unresolved',
                      'sourceFields': {key: fields[key] for key in ('defaultAnimation', '_animationName') if key in fields}},
        'loop': {'status': 'explicit' if 'loop' in fields else 'not_serialized_default_unresolved',
                 'sourceFields': {'loop': fields['loop']} if 'loop' in fields else {}},
        'playTimes': {'status': 'explicit' if '_playTimes' in fields else 'not_serialized_default_unresolved',
                      'sourceFields': {'_playTimes': fields['_playTimes']} if '_playTimes' in fields else {}},
        'timeScale': {'status': 'explicit' if 'timeScale' in fields else 'not_serialized_default_unresolved',
                      'sourceFields': {'timeScale': fields['timeScale']} if 'timeScale' in fields else {}},
        'premultipliedAlpha': {'status': 'explicit' if 'premultipliedAlpha' in fields else 'not_serialized_default_unresolved',
                               'sourceFields': {'premultipliedAlpha': fields['premultipliedAlpha']} if 'premultipliedAlpha' in fields else {}},
        'caching': {'status': 'explicit' if '_preCacheMode' in fields else 'not_serialized_default_unresolved',
                    'sourceFields': {'_preCacheMode': fields['_preCacheMode']} if '_preCacheMode' in fields else {}},
    }
    return {
        'sampleId': sample, 'prefabSourceId': 'gameAsset:prefab-uuid', 'prefabLogicalPath': 'Prefab/Test',
        'sourceComponentId': component_id, 'sourceComponentType': 'sp.Skeleton',
        'sourceOrigin': 'inline-node-component', 'nodeInstanceIndex': '4', 'nodePath': 'Root/Spine',
        'serializedFields': fields, 'properties': properties,
        'skeletonDataUuid': data_id.split(':', 1)[1] if data_id else None,
        'status': 'source_data_uuid_bound' if data_id else 'skeleton_data_uuid_not_serialized',
        'dataAssetSourceId': data_id, 'closureStatus': 'complete' if data_id else 'unbound',
    }


def make_plan_inputs(root):
    assets = [
        {'sourceId': 'spineAsset:asset-a', 'logicalPath': 'Spine/A', 'skeletonBinarySha256': 'a' * 64, 'spineVersion': '3.8.99'},
        {'sourceId': 'spineAsset:asset-b', 'logicalPath': 'Spine/B', 'skeletonBinarySha256': 'b' * 64, 'spineVersion': '3.8.99'},
    ]
    components = [
        source_component('gameAsset:prefab-uuid#1', assets[0]['sourceId'], fields={
            '_N$skeletonData': {'__uuid__': 'asset-a'}, 'defaultSkin': 'default',
            'defaultAnimation': 'idle', '_animationName': 'idle', 'loop': False,
            '_playTimes': 1, 'timeScale': 0.5, 'premultipliedAlpha': False, '_preCacheMode': 0,
            '_materials': [{'__uuid__': 'mat-uuid'}],
        }),
        source_component('gameAsset:prefab-uuid#2', assets[1]['sourceId'], fields={'defaultSkin': 'base'}, sample='P02'),
        source_component('gameAsset:prefab-uuid#3', None, fields={'defaultAnimation': 'runtime-later'}, sample='P03'),
    ]
    contract = {
        'contractSchema': 'prefab-spine-binding/1', 'sourceProfile': 'cocos-2.4.15-bundle',
        'sourceManifestFileSha256': 'c' * 64, 'skeletonComponentCount': 3,
        'bindings': components[:2], 'unbound': [components[2]], 'skeletonData': assets,
    }
    creator_rows = []
    for index, data in enumerate(assets):
        char = 'a' if index == 0 else 'b'
        creator_rows.append({
            'sourceId': data['sourceId'], 'skeletonUuid': f'native-{char}',
            'sourceSkeletonSha256': data['skeletonBinarySha256'], 'version': '3.8.99',
            'savedReferenceVerified': True, 'bones': 12, 'slots': 5,
            'animation': 'idle', 'duration': 1.25, 'nativeStateAdvanced': True,
            'poseChanged': True, 'diagnostics': [],
        })
    readback = {'resourceProbes': {'profile': 'creator-spine-3.8-v1', 'spines': creator_rows}}
    execution = {'status': 'candidate', 'verification': {'editor': 'pass', 'diagnostics': 0},
                 'nativeProgress': {'status': 'completed', 'phase': 'complete'}, 'importPlanSha256': 'd' * 64}
    verification = {'editorValidation': 'pass', 'staticValidation': 'pass', 'diagnostics': []}

    unity = root / 'UnityClosureCandidate'
    (unity / 'Analysis/Evidence').mkdir(parents=True)
    closure_rows = []
    for data, guid, char in zip(assets, ('1' * 32, '2' * 32), ('a', 'b')):
        relative = f'Assets/Game/Content/Spine/{char}/{char}.skel.bytes'
        path = unity / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(char.encode())
        Path(str(path) + '.meta').write_text(f'fileFormatVersion: 2\nguid: {guid}\n')
        closure_rows.append({'sourceId': data['sourceId'], 'status': 'closure_recovered',
                             'skeletonPath': relative, 'sourceSkeletonSha256': data['skeletonBinarySha256'],
                             'skeletonVersion': '3.8.99'})
    (unity / 'manifest.json').write_text('{}')
    (unity / 'Analysis/Evidence/spine-closures.json').write_text(json.dumps({'skeletons': closure_rows}))
    return contract, readback, execution, verification, unity


class PrefabSpineComponentBindingTests(unittest.TestCase):
    def test_static_only_resource_proof_binds_saved_identity_without_claiming_animation(self):
        with tempfile.TemporaryDirectory() as temp:
            contract, readback, execution, verification, unity = make_plan_inputs(Path(temp))
            readback = {'resourceProbes': {'profile': 'creator-spine-3.8-v1', 'spines': []}}
            proofs = [{
                'schemaVersion': 1, 'profile': 'creator-spine-3.8-v1',
                'status': 'static_resource_identity_verified', 'nativeImportCompleted': True,
                'sourceCodeExecuted': False, 'dynamicAnimationComplete': False,
                'spines': [{'sourceId': asset['sourceId'], 'skeletonUuid': 'static-' + asset['sourceId'][-1],
                            'sourceSkeletonSha256': asset['skeletonBinarySha256'], 'version': '3.8.99',
                            'savedReferenceVerified': True, 'bones': 12, 'slots': 5,
                            'textureIdentitiesVerified': True, 'dynamicPoseStatus': 'partial_no_observed_bone_motion',
                            'diagnostics': [{'code': 'NO_OBSERVED_BONE_MOTION'}]}],
            } for asset in contract['skeletonData']]
            plan = build_component_binding_plan(contract, readback, unity,
                                                creator_execution_result=execution,
                                                creator_verification=verification,
                                                creator_import_plan_sha256='d' * 64,
                                                creator_candidate_manifest_sha256='e' * 64,
                                                creator_cache_mode_evidence=CACHE_MODE_EVIDENCE,
                                                creator_static_resource_proofs=proofs)
        self.assertFalse(plan['creatorNativeReadback']['verified'])
        self.assertEqual(plan['creatorNativeReadback']['status'], 'partial_static_resource_readback')
        self.assertEqual(plan['dataAssets'][0]['creator']['status'], 'native_static_resource_readback_verified')
        self.assertTrue(plan['dataAssets'][0]['creator']['staticResourceVerified'])
        self.assertFalse(plan['dataAssets'][0]['creator']['nativePlaybackVerified'])
        self.assertEqual(plan['dataAssets'][0]['creator']['dynamicPoseStatus'], 'partial_no_observed_bone_motion')

    def test_exact_source_denominator_dual_target_refs_and_unbound_dynamic_gap(self):
        with tempfile.TemporaryDirectory() as temp:
            contract, readback, execution, verification, unity = make_plan_inputs(Path(temp))
            plan = build_component_binding_plan(contract, readback, unity,
                                                creator_execution_result=execution,
                                                creator_verification=verification,
                                                creator_import_plan_sha256='d' * 64,
                                                creator_candidate_manifest_sha256='e' * 64,
                                                creator_cache_mode_evidence=CACHE_MODE_EVIDENCE)
        self.assertEqual(plan['componentCount'], 3)
        self.assertEqual(plan['staticAssetBoundComponents'], 2)
        self.assertEqual(plan['staticAssetUnboundComponents'], 1)
        self.assertEqual(plan['uniqueStaticDataAssets'], 2)
        first, second, unbound = plan['components']
        self.assertIsNone(first['unity']['componentType'])
        self.assertEqual(first['unity']['componentTypeChoices'], ['Spine.Unity.SkeletonGraphic', 'Spine.Unity.SkeletonAnimation'])
        self.assertEqual(first['unity']['componentTypeSelection'], 'caller must choose from exact target node UI context')
        self.assertEqual(first['creator']['fields']['skeletonData']['creator']['nativeUuid'], 'native-a')
        self.assertEqual(first['unity']['fields']['skeletonData']['unity']['candidateInputMetaGuid'], '1' * 32)
        self.assertIsNone(first['unity']['fields']['skeletonData']['unity']['nativeSkeletonDataAssetGuid'])
        self.assertEqual(first['unity']['fields']['loop']['unity']['member'], 'startingLoop')
        self.assertEqual(first['unity']['fields']['premultipliedAlpha']['unity']['member'], 'pmaVertexColors')
        self.assertFalse(first['unity']['fields']['loop']['unity']['value'])
        self.assertEqual(first['creator']['fields']['timeScale']['creator']['value'], 0.5)
        self.assertEqual(first['creator']['fields']['caching']['creator']['member'], 'defaultCacheMode')
        self.assertEqual(first['creator']['fields']['animation']['nativeProbeComparison'], 'same_name_observed_in_native_probe')
        self.assertEqual(second['unity']['fields']['skin']['unity']['value'], 'base')
        self.assertIn('_materials', first['unsupportedSourceFields'])
        self.assertEqual(unbound['runtimeDynamicAssignment']['status'], 'source_static_uuid_absent_runtime_assignment_unverified')
        self.assertFalse(unbound['runtimeDynamicAssignment']['targetDefaultAssetFallback'])
        self.assertIsNone(unbound['unity']['fields']['skeletonData']['unity']['candidateInputMetaGuid'])
        self.assertEqual(plan['creatorNativeReadback']['resourceReadbackCount'], 2)
        self.assertTrue(plan['creatorNativeReadback']['verified'])
        self.assertFalse(plan['unityRuntimeEvidence']['unityNativeAssetIdsReadBack'])

    def test_source_current_animation_field_is_preserved_separately(self):
        with tempfile.TemporaryDirectory() as temp:
            contract, readback, execution, verification, unity = make_plan_inputs(Path(temp))
            row = contract['bindings'][0]
            row['serializedFields']['defaultAnimation'] = 'idle'
            row['serializedFields']['_animationName'] = 'walk'
            row['properties']['animation']['sourceFields'] = {'defaultAnimation': 'idle', '_animationName': 'walk'}
            plan = build_component_binding_plan(contract, readback, unity,
                                                creator_execution_result=execution,
                                                creator_verification=verification,
                                                creator_import_plan_sha256='d' * 64)
        anim = plan['components'][0]['creator']['fields']['animation']
        self.assertEqual(anim['status'], 'explicit')
        self.assertEqual(anim['sourceValue'], 'idle')
        self.assertEqual(anim['creatorCurrentAnimationSourceField']['value'], 'walk')

    def test_creator_resource_hash_mismatch_does_not_claim_native_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            contract, readback, execution, verification, unity = make_plan_inputs(Path(temp))
            readback['resourceProbes']['spines'][0]['sourceSkeletonSha256'] = 'f' * 64
            plan = build_component_binding_plan(contract, readback, unity,
                                                creator_execution_result=execution,
                                                creator_verification=verification,
                                                creator_import_plan_sha256='d' * 64)
        self.assertEqual(plan['dataAssets'][0]['creator']['status'], 'readback_present_but_proof_incomplete')

    def test_cache_enum_assignment_requires_explicit_verified_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            contract, readback, execution, verification, unity = make_plan_inputs(Path(temp))
            blocked = build_component_binding_plan(contract, readback, unity,
                                                   creator_execution_result=execution,
                                                   creator_verification=verification,
                                                   creator_import_plan_sha256='d' * 64)
            allowed = build_component_binding_plan(contract, readback, unity,
                                                   creator_execution_result=execution,
                                                   creator_verification=verification,
                                                   creator_import_plan_sha256='d' * 64,
                                                   creator_cache_mode_evidence=CACHE_MODE_EVIDENCE)
        blocked_row = blocked['components'][0]['creator']['fields']['caching']['creator']
        allowed_row = allowed['components'][0]['creator']['fields']['caching']['creator']
        self.assertEqual(blocked_row['status'], 'enum_translation_unverified_blocked_no_assignment')
        self.assertNotIn('member', blocked_row)
        self.assertEqual(allowed_row['member'], 'defaultCacheMode')

    def test_proven_creator_24_defaults_resolve_omitted_fields_and_keep_playtimes_gap(self):
        with tempfile.TemporaryDirectory() as temp:
            contract, readback, execution, verification, unity = make_plan_inputs(Path(temp))
            plan = build_component_binding_plan(contract, readback, unity,
                                                creator_execution_result=execution,
                                                creator_verification=verification,
                                                creator_import_plan_sha256='d' * 64,
                                                creator_cache_mode_evidence=CACHE_MODE_EVIDENCE,
                                                source_default_evidence=DEFAULT_EVIDENCE)
        second = plan['components'][1]['creator']['fields']
        self.assertEqual(second['animation']['status'], 'resolved_source_engine_default')
        self.assertEqual(second['animation']['creator']['value'], '')
        self.assertEqual(second['loop']['sourceValue'], True)
        self.assertEqual(second['loop']['creator']['status'], 'resolved_source_engine_default')
        self.assertEqual(second['timeScale']['sourceValue'], 1)
        self.assertEqual(second['premultipliedAlpha']['sourceValue'], True)
        self.assertEqual(second['tint']['sourceValue'], False)
        self.assertEqual(second['debugBones']['sourceValue'], False)
        self.assertEqual(second['caching']['creator']['member'], 'defaultCacheMode')
        self.assertEqual(second['playTimes']['sourceValue'], 0)
        self.assertEqual(second['playTimes']['creator']['status'], 'source_only_no_same_component_field')
        self.assertIsNone(plan['components'][2]['creator']['fields']['skeletonData']['sourceDefault'])
        self.assertEqual(plan['components'][2]['runtimeDynamicAssignment']['status'],
                         'source_static_uuid_absent_runtime_assignment_unverified')

    def test_pinned_emission_prepares_relative_assets_copies_and_all_components(self):
        with tempfile.TemporaryDirectory() as temp:
            contract, readback, execution, verification, unity = make_plan_inputs(Path(temp))
            component_plan = build_component_binding_plan(contract, readback, unity,
                                                          creator_execution_result=execution,
                                                          creator_verification=verification,
                                                          creator_import_plan_sha256='d' * 64,
                                                          creator_cache_mode_evidence=CACHE_MODE_EVIDENCE,
                                                          source_default_evidence=DEFAULT_EVIDENCE)
            source_ids = ['gameAsset:prefab-uuid#1', 'gameAsset:prefab-uuid#2', 'gameAsset:prefab-uuid#3']
            source_manifest = {'sourceProfile': 'cocos-2.4.15-bundle', 'sourceVersion': '2.4.15',
                               'assets': [{'sourceId': 'gameAsset:prefab-uuid'},
                                          {'sourceId': 'spineAsset:asset-a'}, {'sourceId': 'spineAsset:asset-b'}]}
            normalized_ir = {'sourceManifestSha256': 'c' * 64,
                             'components': [{'type': 'sp.Skeleton', 'sourceId': sid} for sid in source_ids]}
            receipts = {}
            for engine, target_prefix, receipt_hash in (
                ('creator', 'assets/resources/Spine', 'd' * 64),
                ('unity', 'Assets/Game/Content/Spine', 'e' * 64),
            ):
                skeletons = []
                files = []
                for data, char in zip(contract['skeletonData'], ('a', 'b')):
                    stem = f'{target_prefix}/{char}/{char}'
                    paths = [(stem + ('.skel.bytes' if engine == 'unity' else '.skel'), data['skeletonBinarySha256'], 1),
                             (stem + ('.atlas.txt' if engine == 'unity' else '.atlas'), 'f' * 64, 2),
                             (stem + '.png', 'e' * 64, 3)]
                    for path, digest, size in paths:
                        files.append({'path': path, 'sha256': digest, 'bytes': size})
                        files.append({'path': path + '.meta', 'sha256': '9' * 64, 'bytes': 32})
                    skeletons.append({'sourceId': data['sourceId'], 'status': 'closure_recovered',
                                      'sourceSkeletonSha256': data['skeletonBinarySha256'],
                                      'skeletonVersion': '3.8.99', 'skeletonPath': paths[0][0],
                                      'atlasPath': paths[1][0], 'files': [
                                          {'path': path, 'sha256': digest, 'bytes': size} for path, digest, size in paths]})
                receipts[engine] = {'sourceManifestSha256': 'c' * 64, 'receiptSha256': receipt_hash,
                                    'skeletons': skeletons, 'files': files}
                if engine == 'creator':
                    receipts[engine]['nativeAssetUuids'] = {'spineAsset:asset-a': 'native-a',
                                                            'spineAsset:asset-b': 'native-b'}
            prepared = prepare_spine_emission(source_manifest, 'c' * 64, normalized_ir, 'b' * 64,
                                              receipts, component_plan)
            self.assertEqual(prepared['sourcePrefabCount'], 1)
            self.assertEqual(prepared['sourceComponentCount'], 3)
            self.assertEqual(prepared['staticAssetUnboundComponents'], 1)
            self.assertEqual(len(prepared['assets']), 2)
            self.assertEqual(len(prepared['copies']), 24)
            self.assertEqual(prepared['components'][2]['sourceDataAssetId'], None)
            self.assertFalse(prepared['components'][2]['runtimeDynamicAssignment']['targetDefaultAssetFallback'])
            self.assertTrue(all(not Path(row['path']).is_absolute() for row in prepared['copies']))
            out = Path(temp) / 'emission.json'
            emission_hash = emit_spine_emission(prepared, out)
            self.assertEqual(len(emission_hash), 64)
            self.assertEqual(json.loads(out.read_text())['contract'], 'monkey-spine-emission/1')

            material_contract = {
                'schema': 'monkey-spine-material-contract/1',
                'profile': 'cocos24-builtin-spine-material-v1',
                'creatorBindingStatus': 'source-semantics-exact-builtin-spine',
                'pins': {'sourceManifestSha256': 'c' * 64, 'normalizedIrSha256': 'b' * 64,
                         'materialReferenceSourceId': 'gameAsset:material-reference',
                         'materialSourceId': 'internal:material-source', 'effectSourceId': 'internal:spine-effect',
                         'effectProgramCanonicalSha256': 'f' * 64},
                'spec': {'creator38': {
                    'strategy': 'explicit-native-builtin-spine-material-reference',
                    'targetMaterialUuid': 'default-spine-material', 'effect': 'builtin-spine',
                    'perComponent': [{
                        'sourceComponentId': row['sourceComponentId'],
                        'sourceMaterialReferenceSourceId': 'gameAsset:material-reference',
                        'sourceMaterialSourceId': 'internal:material-source',
                        'targetMaterialUuid': 'default-spine-material',
                        'runtimeMaterialStrategy': 'Creator Spine runtime creates per-slot MaterialInstance over builtin-spine and selects blend factors from component PMA',
                    } for row in component_plan['components']],
                }},
            }
            prepared = prepare_spine_emission(source_manifest, 'c' * 64, normalized_ir, 'b' * 64,
                                              receipts, component_plan, material_contract, 'a' * 64)
            self.assertEqual(prepared['creatorMaterialProfile']['targetMaterialUuid'], 'default-spine-material')
            self.assertEqual(len(prepared['creatorMaterialProfile']['contractSha256']), 64)
            self.assertTrue(all(row['creatorStaticPose']['nativeEnabled'] for row in prepared['components']))
            self.assertTrue(all(row['creatorStaticPose']['nativeTimeScale'] == 0 for row in prepared['components']))
            self.assertEqual(prepared['components'][0]['creatorStaticPose']['sourceTimeScale']['value'], 0.5)
            self.assertEqual(prepared['components'][2]['sourceDataAssetId'], None)
            self.assertEqual(prepared['components'][2]['creatorMaterialBinding']['targetMaterialUuid'], 'default-spine-material')
            broken_material = json.loads(json.dumps(material_contract))
            broken_material['spec']['creator38']['perComponent'].pop()
            with self.assertRaises(ValueError):
                prepare_spine_emission(source_manifest, 'c' * 64, normalized_ir, 'b' * 64,
                                       receipts, component_plan, broken_material, 'a' * 64)

    def test_pinned_emission_rejects_ir_component_denominator_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            contract, readback, execution, verification, unity = make_plan_inputs(Path(temp))
            component_plan = build_component_binding_plan(contract, readback, unity,
                                                          source_default_evidence=DEFAULT_EVIDENCE)
            source_manifest = {'sourceProfile': 'cocos-2.4.15-bundle', 'sourceVersion': '2.4.15', 'assets': []}
            normalized_ir = {'sourceManifestSha256': 'c' * 64, 'components': []}
            with self.assertRaises(ValueError):
                prepare_spine_emission(source_manifest, 'c' * 64, normalized_ir, 'b' * 64, {}, component_plan)

    def test_animation_name_falls_back_only_when_default_animation_is_absent(self):
        with tempfile.TemporaryDirectory() as temp:
            contract, readback, execution, verification, unity = make_plan_inputs(Path(temp))
            row = contract['bindings'][0]
            row['serializedFields'].pop('defaultAnimation')
            row['properties']['animation']['sourceFields'].pop('defaultAnimation')
            row['serializedFields']['_animationName'] = 'walk'
            row['properties']['animation']['sourceFields']['_animationName'] = 'walk'
            plan = build_component_binding_plan(contract, readback, unity,
                                                creator_execution_result=execution,
                                                creator_verification=verification,
                                                creator_import_plan_sha256='d' * 64)
        animation = plan['components'][0]['creator']['fields']['animation']
        self.assertEqual(animation['sourceValue'], 'walk')
        self.assertEqual(animation['sourceFallback'], '_animationName')
        self.assertEqual(animation['creator']['member'], 'defaultAnimation')

    def test_pipeline_keeps_active_uninitialized_pose_incomplete_but_accepts_source_inactive_identity(self):
        from monkey.prefab_spine_pipeline import verify

        components = [{'sourceId': 'spine#inactive', 'convertible': True, 'spineBinding': {'creator': {}}},
                      {'sourceId': 'spine#active', 'convertible': True, 'spineBinding': {'creator': {}}}]
        rows = [
            {'sourceComponentId': 'spine#inactive', 'status': 'verified_source_inactive_runtime_uninitialized',
             'serializedRequestedIdentityVerified': True, 'runtimeSkeletonInitialized': False,
             'failures': [], 'sourceActivity': {'hierarchyActive': False}},
            {'sourceComponentId': 'spine#active', 'status': 'incomplete_active_source_runtime_pose_uninitialized',
             'serializedRequestedIdentityVerified': True, 'runtimeSkeletonInitialized': False,
             'failures': [], 'sourceActivity': {'hierarchyActive': True}},
        ]
        diagnostics = verify(components, rows, 'prefab:test')
        self.assertEqual([d['code'] for d in diagnostics], ['SPINE_NATIVE_STATIC_POSE_NOT_INITIALIZED'])
        self.assertEqual(diagnostics[0]['sourceId'], 'spine#active')

        rows[0]['status'] = 'mismatch'
        rows[0]['failures'] = ['requestedAnimationActive']
        diagnostics = verify(components, rows, 'prefab:test')
        self.assertEqual({d['sourceId'] for d in diagnostics}, {'spine#inactive', 'spine#active'})

    def test_creator_helper_binds_exact_data_and_leaves_unbound_data_unset(self):
        helper = Path(__file__).resolve().parents[1] / 'src/monkey/targets/spine/creator_spine_binding.js'
        js = r"""
const api=require(process.argv[1]);
const bound={sourceComponentId:'source#1',creator:{fields:{
 skeletonData:{sourceAssetId:'asset:a'}, skin:{creator:{member:'defaultSkin',value:'default',status:'explicit'}},
 animation:{creator:{member:'defaultAnimation',value:'idle',status:'explicit'}},
 loop:{creator:{member:'loop',value:false,status:'explicit'}},
 timeScale:{creator:{member:'timeScale',value:0.5,status:'explicit'}},
 premultipliedAlpha:{creator:{member:'premultipliedAlpha',value:false,status:'explicit'}},
 caching:{creator:{member:'defaultCacheMode',value:0,status:'explicit'}}
}}};
const component={defaultSkin:'',defaultAnimation:'',loop:true,timeScale:1,premultipliedAlpha:true,defaultCacheMode:1};
const result=api.applyCreatorSpineBinding(bound,()=>component,id=>id==='asset:a'?{uuid:'native'}:null);
if(component.skeletonData.uuid!=='native'||component.loop!==false||component.timeScale!==0.5||component.defaultCacheMode!==0)throw Error('explicit fields were not applied');
const defaulted={sourceComponentId:'source#defaults',creator:{fields:{
 skeletonData:{sourceAssetId:'asset:a'},
 animation:{creator:{member:'defaultAnimation',value:'',status:'resolved_source_engine_default'}},
 loop:{creator:{member:'loop',value:true,status:'resolved_source_engine_default'}}
}}};
const defaultsComponent={defaultAnimation:'left',loop:false};
api.applyCreatorSpineBinding(defaulted,()=>defaultsComponent,()=>({uuid:'native'}));
if(defaultsComponent.defaultAnimation!==''||defaultsComponent.loop!==true)throw Error('verified source defaults were omitted');
const unbound={sourceComponentId:'source#2',creator:{fields:{skeletonData:{sourceAssetId:null}}}};
const untouched={skeletonData:'keep'};
const skipped=api.applyCreatorSpineBinding(unbound,()=>untouched,()=>{throw Error('fallback resource requested')});
if(untouched.skeletonData!=='keep'||!skipped.unresolvedDynamicAssignment)throw Error('unbound source was overwritten');
const staticBinding={sourceComponentId:'source#static',creator:{fields:{
 skeletonData:{sourceAssetId:'asset:static',creator:{nativeUuid:'asset-native'}},
 timeScale:{creator:{member:'timeScale',value:1,status:'explicit'}},
 animation:{creator:{member:'defaultAnimation',value:'idle',status:'explicit'}}
}},creatorStaticPose:{policy:'enabled_realtime_renderer_with_serialized_timeScale_zero',nativeEnabled:true,nativeTimeScale:0,
 sourceTimeScale:{value:1,status:'explicit'},sourceFieldValueRetainedInEmission:true,
 animationFrozenBySerializedTimeScale:true,businessCallbacksExecuted:false,
 sourceMaterialRoute:'Creator sp.Skeleton updateMaterial -> builtinResMgr.get(default-spine-material)'},
 creatorMaterialBinding:{sourceComponentId:'source#static',sourceMaterialReferenceSourceId:'material:source',sourceMaterialSourceId:'internal:material',targetMaterialUuid:'default-spine-material',contract:'cocos24-builtin-spine-material-v1',contractSha256:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',evidenceStatus:'source_to_internal_to_creator_builtin_pinned'}};
const staticComponent={timeScale:1,enabled:false,defaultAnimation:'',customMaterial:null,updateMaterial(){this.materialRouteUpdated=true;}};
const staticApply=api.applyCreatorSpineBinding(staticBinding,()=>staticComponent,()=>({uuid:'asset-native'}));
if(staticComponent.timeScale!==0||staticComponent.enabled!==true||!staticComponent.materialRouteUpdated||staticApply.sourceTimeScale!==1)
 throw Error('static Creator Spine pose must remain visible at serialized t0 while preserving the source timescale');
const staticRead=api.readCreatorSpineBinding(staticBinding,()=>({uuid:'native-component',enabled:true,timeScale:0,customMaterial:null,
 skeletonData:{uuid:'asset-native',getRuntimeData:()=>({animations:[{name:'idle'}],skins:[]})},defaultAnimation:'idle',defaultSkin:'',animation:'idle',loop:true,
 premultipliedAlpha:true,defaultCacheMode:0,findAnimation:name=>({name}),getCurrent:()=>({animation:{name:'idle'}}),isAnimationCached:()=>false}));
if(!staticRead.checks.nativeTimeScaleFrozenAtT0||!staticRead.checks.nativeRendererEnabled||!staticRead.checks.sourceTimeScaleRetainedInPinnedSpec||!staticRead.checks.usesDefaultBuiltinMaterialRoute)
 throw Error('Creator static pose/material route readback did not verify');
const unboundStatic={...staticBinding,sourceComponentId:'source#unknown-data',creator:{fields:{
 skeletonData:{sourceAssetId:null},timeScale:{creator:{member:'timeScale',value:1,status:'explicit'}}}},
 creatorMaterialBinding:{...staticBinding.creatorMaterialBinding,sourceComponentId:'source#unknown-data'}};
const emptyNative={timeScale:1,enabled:false,customMaterial:null};
api.applyCreatorSpineBinding(unboundStatic,()=>emptyNative,()=>{throw Error('must not guess unknown SkeletonData')});
if(emptyNative.skeletonData!==undefined||emptyNative.timeScale!==0||emptyNative.enabled!==true)
 throw Error('unknown SkeletonData must leave an empty, visible native component without fallback');
const unboundRead=api.readCreatorSpineBinding(unboundStatic,()=>({enabled:true,timeScale:0,customMaterial:null,skeletonData:null}));
if(unboundRead.status!=='incomplete_dynamic_assignment'||!unboundRead.checks.nativeTimeScaleFrozenAtT0)
 throw Error('unknown source data must remain explicitly incomplete despite native empty component preservation');
const readSpec={sourceComponentId:'source#3',creator:{fields:{
 skeletonData:{sourceAssetId:'spineAsset:exact-source',creator:{nativeUuid:'native'}},
 skin:{creator:{member:'defaultSkin',value:'default',status:'explicit'}},
 animation:{creator:{member:'defaultAnimation',value:'z_idle',status:'explicit'}},
 loop:{creator:{member:'loop',value:false,status:'explicit'}},
 timeScale:{creator:{member:'timeScale',value:1,status:'explicit'}},
 premultipliedAlpha:{creator:{member:'premultipliedAlpha',value:false,status:'explicit'}},
 caching:{creator:{member:'defaultCacheMode',value:0,status:'explicit'}}
}}};
const native={uuid:'component-native',skeletonData:{uuid:'native',getRuntimeData:()=>({animations:[{name:'b_idle'}],skins:[{name:'default'}]})},
 defaultSkin:'default',defaultAnimation:'z_idle',animation:'b_idle',loop:false,timeScale:1,premultipliedAlpha:false,defaultCacheMode:0,
 findAnimation:name=>name==='b_idle'?{name}:null,getCurrent:()=>({animation:{name:'b_idle'}}),isAnimationCached:()=>false,
 _skeleton:{skin:{name:'default'}}};
const read=api.readCreatorSpineBinding(readSpec,()=>native);
if(read.status!=='mismatch'||read.checks.requestedAnimationExists!==false||read.checks.requestedAnimationActive!==false)throw Error('a different current animation cannot satisfy the requested source animation');
if(read.actual.runtimeAnimationNames.join(',')!=='b_idle')throw Error('readback must expose the actual runtime animation list');
// Serialized identity and runtime pose are separate evidence. A source-active
// hierarchy with an uninitialized runtime skeleton remains incomplete; an
// inactive ancestor explains the missing runtime pose without weakening the
// exact serialized animation/skin and SkeletonData checks.
const sourcePlan={nodes:[
 {sourceId:'root',parent:null,active:false},
 {sourceId:'spine-node',parent:'root',active:true}
]};
const activity=api.sourceNodeActivity(sourcePlan,'spine-node');
if(activity.hierarchyActive!==false||activity.nodeActive!==true)throw Error('source node activity must include the exact inactive ancestor');
const serializedOnly={uuid:'native-component',node:{active:true},enabled:true,customMaterial:null,
 skeletonData:{uuid:'native',getRuntimeData:()=>({animations:[{name:'z_idle'}],skins:[{name:'default'}]})},
 defaultSkin:'default',defaultAnimation:'z_idle',loop:false,timeScale:1,premultipliedAlpha:false,defaultCacheMode:0,
 isAnimationCached:()=>false,getCurrent:()=>null};
const inactiveRead=api.readCreatorSpineBinding(readSpec,()=>serializedOnly,
 {sourceActivity:activity,readbackScope:'instantiated_mapped'});
if(inactiveRead.status!=='verified_source_inactive_runtime_uninitialized'||!inactiveRead.serializedRequestedIdentityVerified||
 inactiveRead.runtimeSkeletonInitialized||inactiveRead.readbackScope!=='instantiated_mapped'||
 inactiveRead.serializedIdentityStatus!=='verified'||inactiveRead.instantiatedRuntimeStatus!=='not_initialized')
 throw Error('inactive source must report serialized identity separately from uninitialized instance pose');
const activeRead=api.readCreatorSpineBinding(readSpec,()=>serializedOnly,
 {sourceActivity:{...activity,hierarchyActive:true,status:'verified_source_hierarchy_active'},readbackScope:'instantiated_mapped'});
if(activeRead.status!=='incomplete_active_source_runtime_pose_uninitialized'||activeRead.serializedIdentityStatus!=='verified'||
 activeRead.instantiatedRuntimeStatus!=='not_initialized')
 throw Error('active source without initialized runtime pose must remain incomplete');
const catalog=api.readCreatorSpineDataCatalog('spineAsset:source',{uuid:'native',getRuntimeData:()=>({animations:[{name:'b_idle'},{name:'z_idle'}],skins:[{name:'default'}],bones:[{},{}],slots:[{}]})},
 {nativeUuid:'native',animationName:'z_idle',skinName:'default'});
if(catalog.status!=='verified'||!catalog.animationNames.includes('z_idle')||catalog.boneCount!==2)throw Error('complete native SkeletonData names/counts were not read');
const unresolved=api.readCreatorSpineBinding({sourceComponentId:'source#4',creator:{fields:{skeletonData:{creator:{nativeUuid:null}}}}},
 ()=>({uuid:'component-empty',skeletonData:null,loop:true,timeScale:1,premultipliedAlpha:true}));
if(unresolved.status!=='incomplete_dynamic_assignment'||unresolved.checks.exactSkeletonDataUuid!==null)throw Error('unbound source data was treated as a passing static binding');
"""
        subprocess.run(['node', '-e', js, str(helper)], check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
