import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from monkey import code_architecture_asset_context as assets
from monkey.io import encoded, sha
from monkey.sources.compiled import ParseError


class ArchitectureAssetContextTests(unittest.TestCase):
    def fixture(self, root):
        candidate = root / 'candidate'
        candidate.mkdir()
        region = 'fixture:snapshot/game.js#HouseScreen@120'
        source_asset = 'remoteAsset:544b8138-33da-47b6-94ed-c09b23ecef27'
        source_node = source_asset + '#1'
        source_component = source_node + '/components/1'
        target = 'Assets/Game/Content/Prefabs/House/HouseScreen.prefab'
        preview = 'Assets/Game/Content/Prefabs/Preview/ContentPreview.prefab'
        files = {
            'Analysis/Code/component-code-bindings.json': encoded({'schemaVersion': 1, 'bindings': [{
                'codeRegion': region, 'evidence': 'exact_literal_script_identity', 'nativeComponent': 'not_implemented',
                'sourceAsset': source_asset, 'sourceComponent': source_component, 'sourceNode': source_node}]}),
            'Analysis/Mappings/source-map.json': encoded({'assets': [], 'components': [{
                'sourceId': source_component, 'node': source_node, 'target': preview, 'type': 'cc.Widget',
                'bindingEvidence': 'Actual native fileIDs require editor readback'}],
                'nodes': [{'sourceId': source_node, 'name': 'HouseScreen', 'target': preview}],
                'fonts': [], 'sourceLocations': [], 'sourceRoots': []}),
            'Analysis/Mappings/cocos-assets.json': encoded({'schemaVersion': 1, 'assets': [{
                'sourceId': source_asset, 'uuid': source_asset.split(':', 1)[1], 'sourceType': 'cc.Prefab',
                'logicalKey': ['Prefab/House/HouseScreen', 2], 'targets': []}]}),
            'Analysis/Mappings/resource-paths.json': encoded({'schemaVersion': 1, 'assets': [{
                'sourceId': source_asset, 'path': target, 'type': 'prefab', 'state': 'planned_native_import',
                'address': 'Prefabs/House/HouseScreen'}]}),
            target: b'%YAML 1.1\n--- !u!1001 &1\nPrefabInstance: {}\n',
            target + '.meta': b'fileFormatVersion: 2\nguid: 0123456789abcdef0123456789abcdef\nPrefabImporter:\n',
            preview: b'%YAML 1.1\n--- !u!1 &77\nGameObject: {}\n',
            preview + '.meta': b'fileFormatVersion: 2\nguid: fedcba9876543210fedcba9876543210\nPrefabImporter:\n',
            'Analysis/Readback/editor-readback.json': encoded({'status': 'partial', 'unityVersion': '6000.6.2f1',
                'nativeScope': 'source-node-subset', 'sourceGraphVerification': 'saved-source-node-subset',
                'prefabGuid': 'fedcba9876543210fedcba9876543210', 'sceneGuid': '11111111111111111111111111111111',
                'nodeCount': 1, 'missingScripts': 0, 'editableRoundtrip': True, 'sceneReopened': True,
                'sourcePrefabs': [{'sourceId': source_asset, 'path': target,
                    'guid': '0123456789abcdef0123456789abcdef', 'nativePrefabType': 'Regular', 'nodeCount': 1,
                    'missingScripts': 0, 'savedReloaded': True, 'referencesVerified': True,
                    'geometryPhase': 'native-layout-settled-v1', 'nodes': [{'sourceId': source_node,
                        'hierarchy': 'HouseScreen', 'componentTypes': ['UnityEngine.RectTransform']}]}],
                'viewReferences': [{'sourceId': source_component, 'field': 'View', 'index': 0,
                    'prefabFileId': 77, 'bound': True}]})
        }
        for rel, raw in files.items():
            path = candidate / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        manifest_raw = encoded({'schemaVersion': 1, 'targetProfile': 'unity-6000.6.2f1-ugui',
            'namespace': 'Fixture', 'scopeMode': 'whole-input', 'files': [
                {'path': path, 'sha256': sha(raw), 'bytes': len(raw), 'owner': 'generated'}
                for path, raw in files.items()]})
        (candidate / 'manifest.json').write_bytes(manifest_raw)

        stage_root = root / 'Global'
        (stage_root / 'Evidence').mkdir(parents=True)
        binding_path = stage_root / 'Evidence/component-code-bindings.json'
        binding_raw = files['Analysis/Code/component-code-bindings.json']
        binding_path.write_bytes(binding_raw)
        context_pin = {'sha256': sha(binding_raw), 'bytes': len(binding_raw)}
        (stage_root / 'Task').mkdir()
        (stage_root / 'Task/request.json').write_bytes(encoded({'contextFiles': {
            '__Context/component-code-bindings.json': context_pin}}))

        unit_id = 'module:source:100:200'
        unit = {'id': unit_id, 'sourceIds': [region], 'sourceSha256': 'a' * 64,
                'sourceBytes': {'start': 100, 'end': 200}}
        stage = {'root': stage_root, 'request': {'sourceRoot': str(candidate)},
            'pins': {'sourceManifestSha256': sha(manifest_raw), 'architectureSha256': 'b' * 64},
            'catalog': {'sourceUnits': [unit]}}
        classes = [{'id': 'HouseView', 'sourceUnitIds': [unit_id]}]
        return candidate, stage, classes, source_component, source_node, target

    def test_exact_code_owner_joins_asset_guid_but_never_invents_component_local_id(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory)
            _, stage, classes, source_component, source_node, target = self.fixture(root)
            cache = root / 'private-index'
            result = assets.build_asset_context(stage, classes, cache_root=cache)
            context = result['context']
            self.assertEqual(context['status'], 'mapped-with-unresolved-object-references')
            self.assertEqual(context['editorReadbackSummary']['nativeScope'], 'source-node-subset')
            self.assertEqual(context['editorReadbackSummary']['status'], 'partial')
            self.assertEqual(len(context['bindings']), 1)
            binding = context['bindings'][0]
            self.assertEqual(binding['sourceComponent'], source_component)
            self.assertEqual(binding['sourceNode'], source_node)
            native = binding['assetIdentity']['nativeTargets'][0]
            self.assertEqual(native['path'], target)
            self.assertEqual(native['guid'], '0123456789abcdef0123456789abcdef')
            self.assertTrue(binding['assetIdentity']['sourcePrefabReadback'][0]['identityMatch'])
            preview_ref = binding['previewReadbackReference']
            self.assertEqual(preview_ref['status'], 'verified-preview-object-reference-only')
            self.assertEqual(preview_ref['prefabFileId'], '77')
            self.assertEqual(preview_ref['guid'], 'fedcba9876543210fedcba9876543210')
            self.assertEqual(binding['serializedReference'], None)
            self.assertTrue(any('source-prefab object localID' in reason for reason in binding['unresolvedReasons']))
            reused = assets.build_asset_context(stage, classes, cache_root=cache)
            self.assertEqual(reused['cache']['status'], 'verified-cache')

    def test_no_source_owner_does_not_borrow_another_class_binding(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory)
            _, stage, classes, *_ = self.fixture(root)
            other = [{'id': 'DifferentClass', 'sourceUnitIds': []}]
            result = assets.build_asset_context(stage, other)
            self.assertEqual(result['context']['status'], 'no-source-owned-classes')
            self.assertEqual(result['context']['bindings'], [])

    def test_mapping_hash_drift_is_rejected_before_binding_output(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory)
            candidate, stage, classes, *_ = self.fixture(root)
            target = candidate / assets.MAPPING_PATHS['resourcePaths']
            target.write_bytes(target.read_bytes() + b' ')
            with self.assertRaises(ParseError):
                assets.build_asset_context(stage, classes)

    def test_large_context_is_sharded_and_reconstructed_byte_exactly(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory)
            context = {'schemaVersion': assets.SCHEMA, 'status': 'mapped-with-unresolved-object-references',
                'sourceManifestSha256': 'a' * 64, 'architectureSha256': 'b' * 64,
                'sourceOwners': [{'sourceUnitId': f'unit-{i}', 'sourceSha256': 'c' * 64,
                                  'sourceBytes': {'start': i, 'end': i + 1}, 'sourceIds': [f'id-{i}']}
                                 for i in range(3)],
                'bindings': [{'codeRegion': f'region-{i}', 'payload': 'x' * 1_000_000,
                              'sourceOwnership': {'sourceUnitIds': [f'unit-{i}']}}
                             for i in range(10)],
                'unresolved': [{'codeRegion': f'region-{i}', 'reasons': ['missing localID']}
                               for i in range(10)],
                'runtimeUse': 'serialized native references only'}
            output = root / 'Evidence'
            output.mkdir()
            files = {}
            with patch.object(assets, 'build_asset_context', return_value={'context': context, 'cache': {'status': 'test'}}):
                result = assets.write_module_context({}, [], output, files)
            self.assertEqual(result['format'], assets.INDEX_SCHEMA)
            self.assertEqual(result['contextSha256'], sha(encoded(context)))
            self.assertEqual(result['contextBytes'], len(encoded(context)))
            shards = [row for row in files if row.startswith('module-asset-bindings.shards/')]
            self.assertGreater(len(shards), 1)
            self.assertTrue(all(files[path]['bytes'] <= assets.ASSET_CONTEXT_SHARD_BYTES for path in shards))
            self.assertEqual(assets.load_module_context(output / 'module-asset-bindings.json'), context)

            shard_path = output / shards[0]
            raw = shard_path.read_bytes()
            shard_path.write_bytes(raw[:-1] + (b' ' if raw[-1:] != b' ' else b'\n'))
            with self.assertRaises(ParseError):
                assets.load_module_context(output / 'module-asset-bindings.json')

    def test_single_oversized_binding_row_is_rejected_without_truncation(self):
        context = {'schemaVersion': assets.SCHEMA, 'status': 'large', 'sourceManifestSha256': 'a' * 64,
            'sourceOwners': [], 'bindings': [{'payload': 'z' * assets.ASSET_CONTEXT_SHARD_BYTES}],
            'unresolved': []}
        with self.assertRaises(ParseError):
            assets._shard_context(context, encoded(context))

    def test_aggregate_worker_context_budget_is_checked_before_any_write(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory)
            output = root / 'Evidence'
            output.mkdir()
            context = {'schemaVersion': assets.SCHEMA, 'status': 'small', 'bindings': [],
                       'sourceOwners': [], 'unresolved': []}
            files = {'existing-context.json': {'bytes': assets.ASSET_CONTEXT_GROUP_BYTES}}
            with patch.object(assets, 'build_asset_context', return_value={'context': context, 'cache': {}}):
                with self.assertRaises(ParseError):
                    assets.write_module_context({}, [], output, files)
            self.assertFalse((output / 'module-asset-bindings.json').exists())

    def test_small_context_keeps_legacy_single_file_format(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory)
            output = root / 'Evidence'
            output.mkdir()
            context = {'schemaVersion': assets.SCHEMA, 'status': 'small', 'bindings': [],
                       'sourceOwners': [], 'unresolved': []}
            files = {}
            with patch.object(assets, 'build_asset_context', return_value={'context': context, 'cache': {}}):
                summary = assets.write_module_context({}, [], output, files)
            self.assertEqual(summary['format'], 'single-json')
            self.assertEqual(set(files), {'module-asset-bindings.json'})
            self.assertEqual((output / 'module-asset-bindings.json').read_bytes(), encoded(context))
            self.assertEqual(assets.load_module_context(output / 'module-asset-bindings.json'), context)


if __name__ == '__main__':
    unittest.main()
