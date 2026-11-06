import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import monkey.prefab_static_controls as controls
from monkey.prefab_static_controls import StaticControlError, emit_unity, verify


class PrefabStaticControlsTests(unittest.TestCase):
    def fixture(self):
        manifest = {
            'assets': [
                {'sourceId': 'gameAsset:prefab', 'bundle': 'gameAsset', 'kind': 'cc.Prefab',
                 'document': {'root': 0, 'instances': [
                     {'__type__': 'cc.Prefab'},
                     {'__type__': 'cc.Node'},
                     {'__type__': 'cc.EditBox', 'node': {'__id__': 1}, '_N$background': {'__id__': 7},
                      '_N$placeholderLabel': {'__id__': 9}, '_N$textLabel': {'__id__': 8}, 'maxLength': 150},
                     {'__type__': 'cc.Node'},
                     {'__type__': 'cc.Node'},
                     {'__type__': 'cc.Graphics', 'node': {'__id__': 3}, '_materials': [{'__uuid__': 'mat'}]},
                     {'__type__': 'cc.Graphics', 'node': {'__id__': 4}, '_materials': [{'__uuid__': 'mat'}]},
                     {'__type__': 'cc.Sprite', 'node': {'__id__': 1}},
                     {'__type__': 'cc.Label', 'node': {'__id__': 1}},
                     {'__type__': 'cc.Label', 'node': {'__id__': 1}},
                 ]}},
                {'sourceId': 'gameAsset:mat', 'bundle': 'gameAsset', 'kind': 'redirect',
                 'redirectTarget': 'internal:mat'},
                {'sourceId': 'internal:mat', 'bundle': 'internal', 'kind': 'cc.Material',
                 'document': {'root': 0, 'instances': [
                     {'__type__': 'cc.Material', '_name': 'builtin-2d-graphics', '_techniqueData': {'0': {'defines': {}}},
                      '_effectAsset': {'__uuid__': 'effect'}}]}},
                {'sourceId': 'internal:effect', 'bundle': 'internal', 'kind': 'cc.EffectAsset',
                 'document': {'root': 0, 'instances': [
                     {'__type__': 'cc.EffectAsset', '_name': 'builtin-2d-graphics', 'shaders': [
                         {'glsl1': {'vert': 'void main () { }', 'frag': 'void main () { }'}}]}]}},
            ]
        }
        plan = {'namespace': 'static-controls-fixture', 'sourceManifestPath': '', 'sourceManifestSha256': '', 'components': [
            {'sourceId': 'gameAsset:prefab#2', 'node': 'gameAsset:prefab#1', 'type': 'cc.EditBox', 'enabled': True},
            {'sourceId': 'gameAsset:prefab#5', 'node': 'gameAsset:prefab#3', 'type': 'cc.Graphics', 'enabled': True},
            {'sourceId': 'gameAsset:prefab#6', 'node': 'gameAsset:prefab#4', 'type': 'cc.Graphics', 'enabled': True},
            {'sourceId': 'gameAsset:prefab#7', 'node': 'gameAsset:prefab#1', 'type': 'cc.Sprite', 'enabled': True},
            {'sourceId': 'gameAsset:prefab#8', 'node': 'gameAsset:prefab#1', 'type': 'cc.Label', 'enabled': True},
            {'sourceId': 'gameAsset:prefab#9', 'node': 'gameAsset:prefab#1', 'type': 'cc.Label', 'enabled': True},
        ]}
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / 'source-manifest.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        plan['sourceManifestPath'] = str(path)
        plan['sourceManifestSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.addCleanup(tmp.cleanup)
        return plan, manifest, path

    def prepare_bound(self, plan, manifest):
        effect = next(a for a in manifest['assets'] if a['sourceId'] == 'internal:effect')['document']['instances'][0]
        glsl = effect['shaders'][0]['glsl1']
        normalize = lambda text: '\n'.join(line.rstrip() for line in text.replace('\r\n', '\n').replace('\r', '\n').strip().splitlines()).strip()
        profile = hashlib.sha256((normalize(glsl['vert']) + '\0' + normalize(glsl['frag'])).encode()).hexdigest()
        with patch.object(controls, '_SUPPORTED_GRAPHICS_PROFILE_SHA256', profile):
            return controls.prepare(plan, manifest)

    def test_prepare_preserves_exact_editbox_refs_and_builtin_graphics_material(self):
        plan, manifest, _ = self.fixture()
        report = self.prepare_bound(plan, manifest)
        self.assertEqual(len(report['bindings']), 3)
        edit = report['bindings'][0]
        self.assertEqual(edit['maxLength'], 150)
        self.assertEqual({r['field']: r['sourceId'] for r in edit['references']}, {
            'background': 'gameAsset:prefab#7',
            'placeholderLabel': 'gameAsset:prefab#9',
            'textLabel': 'gameAsset:prefab#8'})
        graphics = report['bindings'][1]
        self.assertEqual(graphics['materials'][0]['resolvedSourceId'], 'internal:mat')
        self.assertEqual(graphics['materials'][0]['effectName'], 'builtin-2d-graphics')
        self.assertEqual(graphics['sourceDrawingCommands'], 'not-serialized-empty-in-fixed-state')

    def test_prepare_rejects_source_manifest_hash_drift(self):
        plan, manifest, path = self.fixture()
        path.write_text(path.read_text() + ' ', encoding='utf-8')
        with self.assertRaisesRegex(StaticControlError, 'SHA-256 differs'):
            self.prepare_bound(plan, manifest)

    def test_emit_unity_copies_exact_profile_shader_and_stable_guid(self):
        plan, manifest, _ = self.fixture()
        report = self.prepare_bound(plan, manifest)
        for binding in report['bindings']:
            for material in binding.get('materials', []):
                material['sourceEffectNormalizedGlslSha256'] = controls._SUPPORTED_GRAPHICS_PROFILE_SHA256
        with tempfile.TemporaryDirectory() as temp:
            rows = emit_unity(report, temp)
            self.assertEqual(len(rows), 1)
            shader_path = Path(temp) / rows[0]['path']
            self.assertTrue(shader_path.is_file())
            self.assertEqual(hashlib.sha256(shader_path.read_bytes()).hexdigest(), rows[0]['sha256'])
            meta = Path(str(shader_path) + '.meta').read_text(encoding='utf-8')
            self.assertIn(rows[0]['guid'], meta)

    def test_prepare_rejects_editbox_reference_type_mismatch(self):
        plan, manifest, path = self.fixture()
        manifest = copy.deepcopy(manifest)
        manifest['assets'][0]['document']['instances'][7]['__type__'] = 'cc.Label'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        plan['sourceManifestSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(StaticControlError, 'expected cc.Sprite'):
            self.prepare_bound(plan, manifest)

    def test_prepare_rejects_non_builtin_graphics_effect_and_draw_commands(self):
        plan, manifest, _ = self.fixture()
        changed = copy.deepcopy(manifest)
        changed['assets'][-1]['document']['instances'][0]['_name'] = 'unproven-effect'
        path = Path(plan['sourceManifestPath'])
        path.write_text(json.dumps(changed), encoding='utf-8')
        plan['sourceManifestSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(StaticControlError, 'outside the proven native profile'):
            self.prepare_bound(plan, changed)

        plan, manifest, path = self.fixture()
        manifest['assets'][0]['document']['instances'][5]['commands'] = [{'op': 'lineTo'}]
        path.write_text(json.dumps(manifest), encoding='utf-8')
        plan['sourceManifestSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(StaticControlError, 'non-empty command payload'):
            self.prepare_bound(plan, manifest)

    def test_native_readback_contract_positive_and_negative(self):
        plan, manifest, _ = self.fixture()
        bindings = self.prepare_bound(plan, manifest)['bindings']
        actual = [
            {'sourceId': 'gameAsset:prefab#2', 'nativeType': 'MonkeyStaticEditBox', 'enabled': False, 'maxLength': 150,
             'references': [{'field': r['field'], 'sourceId': r['sourceId'], 'verified': True} for r in bindings[0]['references']]},
            *[{'sourceId': b['sourceId'], 'nativeType': 'cc.Graphics', 'enabled': False,
               'sourceDrawingCommands': b['sourceDrawingCommands'],
               'materials': [{'sourceId': b['materials'][0]['sourceId'], 'effectName': 'builtin-2d-graphics',
                              'nativeUuid': 'f0416e68-0200-4b77-a926-4f9d16e494da','nativeEffectUuid':'1c02ae6f-4492-4915-b8f8-7492a3b1e4cd', 'verified': True}]}
              for b in bindings[1:]],
        ]
        self.assertEqual(verify(bindings, actual), [])
        actual[0]['references'][0]['sourceId'] = 'wrong-reference'
        actual[1]['materials'][0]['verified'] = False
        actual[2]['enabled'] = True
        errors = verify(bindings, actual)
        self.assertEqual(len(errors), 3)
        self.assertTrue(any('EditBox native reference differs' in error for error in errors))
        self.assertTrue(any('Graphics native material identity differs' in error for error in errors))
        self.assertTrue(any('type/disabled state differs' in error for error in errors))


if __name__ == '__main__':
    unittest.main()
