import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from monkey.prefab_sprite_outline_unity_readback import verify


class UnitySpriteOutlineReadbackTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name) / 'UnityCandidate'
        root.mkdir()
        manifest = Path(temp.name) / 'source-manifest.json'
        manifest.write_text('{"schemaVersion":1}\n', encoding='utf-8')
        manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
        ir_sha = 'a' * 64
        owner = 'gameAsset:owner'
        component_id = owner + '#42'
        node_id = owner + '#41'
        frame_id = 'remoteAsset:frame-id'
        material_source_id = 'internal:outline-material'
        material_path, shader_path, prefab_path, texture_path = (
            'Assets/Game/Content/Materials/StaticUI/Shader2DOutline.mat',
            'Assets/Game/Content/Shaders/StaticUI/Shader2DOutline.shader',
            'Assets/Game/Content/Prefabs/UI/Owner.prefab',
            'Assets/Game/Content/Textures/Badge/icon.png')
        material_guid, shader_guid, prefab_guid, texture_guid = ('1' * 32, '2' * 32, '3' * 32, '4' * 32)

        def asset(path, guid, data=b'asset'):
            full = root / path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_bytes(data)
            Path(str(full) + '.meta').write_text(f'fileFormatVersion: 2\nguid: {guid}\n', encoding='utf-8')
        for path, guid in ((material_path, material_guid), (shader_path, shader_guid),
                           (prefab_path, prefab_guid), (texture_path, texture_guid)):
            asset(path, guid)
        spec = dict(schema='monkey-prefab-sprite-outline-binding/1',
                    profile='cocos24-sprite-alpha-outline-v1',
                    programCanonicalSha256='53fbec41d8b524d31908b3b27f1b6cccbd2fcd1eb0be9ace5917be386dad4784',
                    materialSourceId=material_source_id,
                    sourceManifestSha256=manifest_sha, normalizedIrSha256=ir_sha,
                    properties=dict(outlineColor=[0.2, 0.5, 0.8, 1.0], outlineTextureSize=[128.0, 128.0],
                                    outlineWidth=5.0, fillAlpha=0.0, alphaThreshold=0.01),
                    unity=dict(materialPath=material_path, materialGuid=material_guid,
                               shaderPath=shader_path, shaderGuid=shader_guid),
                    sourceComponentIds=[component_id],
                    spriteBindings=[dict(sourceId=component_id, spriteFrameSourceId=frame_id)],
                    sourceBindings=[dict(componentSourceId=component_id, prefabSourceId=owner,
                                         prefabPath='Prefab/UI/Owner', spriteFrameUuid='frame-id')])
        instruction = dict(sourceManifestPath=str(manifest), sourceManifestSha256=manifest_sha,
                           sourceIrSha256=ir_sha, spriteOutlineBindingJson=json.dumps(spec),
                           sourcePrefabs=[dict(sourceId=owner, path=prefab_path, nodes=[node_id])],
                           components=[dict(sourceId=component_id, type='cc.Sprite', convertible=True, node=node_id,
                                            spriteFrame=frame_id,
                                            nativeSpriteOutlineMaterialSourceId=material_source_id)],
                           textures=[dict(id=frame_id, path=texture_path)])
        editor_readback = dict(sourcePrefabs=[dict(sourceId=owner, path=prefab_path, guid=prefab_guid)])
        file = root / 'Analysis/Readback/sprite-outline-materials.json'
        file.parent.mkdir(parents=True)
        file.write_text(json.dumps(dict(schemaVersion=1, prefabs=[dict(
            sourcePrefabId=owner, materialSourceId=material_source_id,
            materialGuid=material_guid, shaderGuid=shader_guid,
            propertiesVerified=True, boundSpriteComponentIds=[component_id])])), encoding='utf-8')
        return temp, root, instruction, editor_readback, file

    def test_accepts_exact_material_shader_owner_and_component_readback(self):
        temp, root, instruction, editor_readback, _ = self.fixture()
        self.addCleanup(temp.cleanup)
        self.assertEqual(verify(instruction, root, editor_readback), [])

    def test_rejects_material_shader_or_property_mismatch(self):
        for field, value, expected in (
                ('materialGuid', '9' * 32, 'material/shader identity'),
                ('shaderGuid', '8' * 32, 'material/shader identity'),
                ('propertiesVerified', False, 'material/shader identity')):
            with self.subTest(field=field):
                temp, root, instruction, editor_readback, path = self.fixture()
                try:
                    readback = json.loads(path.read_text())
                    readback['prefabs'][0][field] = value
                    path.write_text(json.dumps(readback), encoding='utf-8')
                    diagnostics = verify(instruction, root, editor_readback)
                    self.assertTrue(any(expected in row['message'] for row in diagnostics))
                finally:
                    temp.cleanup()

    def test_rejects_owner_component_source_pin_and_target_meta_mismatch(self):
        mutations = ('bound_ids', 'owner', 'manifest_pin', 'material_meta', 'source_frame')
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                temp, root, instruction, editor_readback, path = self.fixture()
                try:
                    if mutation == 'bound_ids':
                        readback = json.loads(path.read_text())
                        readback['prefabs'][0]['boundSpriteComponentIds'] = []
                        path.write_text(json.dumps(readback), encoding='utf-8')
                    elif mutation == 'owner':
                        readback = json.loads(path.read_text())
                        readback['prefabs'][0]['sourcePrefabId'] = 'gameAsset:other-owner'
                        path.write_text(json.dumps(readback), encoding='utf-8')
                    elif mutation == 'manifest_pin':
                        spec = json.loads(instruction['spriteOutlineBindingJson'])
                        spec['normalizedIrSha256'] = 'b' * 64
                        instruction['spriteOutlineBindingJson'] = json.dumps(spec)
                    elif mutation == 'material_meta':
                        (root / 'Assets/Game/Content/Materials/StaticUI/Shader2DOutline.mat.meta').write_text(
                            'fileFormatVersion: 2\nguid: ' + '9' * 32 + '\n', encoding='utf-8')
                    elif mutation == 'source_frame':
                        instruction['components'][0]['spriteFrame'] = 'remoteAsset:other-frame'
                    diagnostics = verify(instruction, root, editor_readback)
                    self.assertTrue(diagnostics, [row['message'] for row in diagnostics])
                finally:
                    temp.cleanup()


if __name__ == '__main__':
    unittest.main()
