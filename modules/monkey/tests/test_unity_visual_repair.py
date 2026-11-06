import tempfile
import unittest
from pathlib import Path

from PIL import Image

from monkey.unity_visual_repair import sprite_pixels, write_texture_meta


class VisualRepairTests(unittest.TestCase):
    def test_material_map_pairs_retain_external_textures_and_skip_nulls(self):
        from types import SimpleNamespace
        from monkey.unity_object_dependencies import positive_pointers
        source = SimpleNamespace(name="CAB-local", externals=[SimpleNamespace(path="archive:/CAB-peer")])
        tree = {"m_TexEnvs": [("_MainTex", {"m_Texture": {"m_FileID": 1, "m_PathID": -19}}),
                              ("_Mask", {"m_Texture": {"m_FileID": 0, "m_PathID": 0}})]}
        self.assertEqual(list(positive_pointers(source, tree)), [("cab-peer", -19)])

    def test_dynamic_atlas_retains_empty_source_texture_and_native_reference(self):
        from types import SimpleNamespace
        from monkey.unity_visual_repair import restore_empty_font_atlases
        def obj(kind, data):
            return SimpleNamespace(type=SimpleNamespace(name=kind), peek_name=lambda: data['m_Name'],
                                   read_typetree=lambda: data)
        guid = '1' * 32
        ref = f'{{fileID: 2800000, guid: {guid}, type: 3}}'
        font = obj('MonoBehaviour', dict(m_Name='Dynamic', m_AtlasPopulationMode=1,
                                         m_AtlasTextures=[dict(m_FileID=0, m_PathID=2)]))
        tex = obj('Texture2D', dict(m_Name='Empty atlas', m_Width=0, m_Height=0, m_TextureFormat=1,
                                    m_IsReadable=True, m_MipCount=1, m_ColorSpace=1,
                                    m_TextureSettings=dict(m_FilterMode=1, m_Aniso=1, m_MipBias=0,
                                                           m_WrapU=0, m_WrapV=0, m_WrapW=0),
                                    m_StreamData={'size':0}, **{'image data':b''}))
        file = SimpleNamespace(name='cab', externals=[], objects={1:font, 2:tex})
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            assets = project / 'Assets'
            assets.mkdir()
            owner = assets / 'font.asset'
            owner.write_text(f'  m_Name: Dynamic\n  m_AtlasPopulationMode: 1\n  m_AtlasTextures:\n  - {ref}\n')
            material = assets / 'font.mat'
            material.write_text(f'      _MainTex:\n        m_Texture: {ref}\n')
            result = restore_empty_font_atlases(project, {'cab':file})
            self.assertEqual(len(result), 1)
            self.assertIn('m_Width: 0', (project / result[0]).read_text())
            for path in (owner, material):
                self.assertIn(f'{guid}, type: 2', path.read_text())
            self.assertEqual(restore_empty_font_atlases(project, {'cab':file}), [])

    def test_label_choice_requires_confirmed_sibling_glyph_overlap(self):
        from monkey.unity_visual_repair import reviewed_overlap_states
        hit = dict(root='Assets/A.prefab', first='0/0', second='0/1', coverage=.91)
        rule = dict(keep='Win', hide='Loss', parent='Result', reason='Victory preview')
        nodes = {(hit['root'], path): (name, True) for path, name in
                 [('0','Result'), ('0/0','Win'), ('0/1','Loss')]}
        self.assertEqual([s['node'] for s in reviewed_overlap_states([hit],[rule],nodes)], ['Loss'])
        self.assertEqual(list(reviewed_overlap_states([dict(hit, coverage=.4)],[rule],nodes)), [])

    def test_local_shader_includes_are_staged_transitively(self):
        from monkey.unity_gles_shader import stage_shader_includes
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'original'
            target = root / 'export'
            source.mkdir()
            (source/'shader.shader').write_text('#include "Properties.cginc"\n#include "UnityCG.cginc"')
            (source/'Properties.cginc').write_text('#include "Definitions.cginc"')
            (source/'Definitions.cginc').write_text('float outlineWidth;')
            stage_shader_includes(source/'shader.shader',target/'shader.shader')
            self.assertEqual((target/'Definitions.cginc').read_text(), 'float outlineWidth;')
            self.assertFalse((target/'UnityCG.cginc').exists())

    def test_packed_sprite_restores_flip_trim_and_bottom_left_origin(self):
        page = Image.new('RGBA', (4, 3))
        page.putpixel((1, 0), (255, 0, 0, 255))
        page.putpixel((2, 0), (0, 0, 255, 255))
        data = {'m_Rect': {'width': 4, 'height': 3}}
        region = {'textureRect': {'x': 1, 'y': 0, 'width': 2, 'height': 1},
                  'settingsRaw': 5, 'textureRectOffset': {'x': 1, 'y': 0}}
        image = sprite_pixels(page, data, region)
        self.assertEqual(image.getbbox(), (1, 2, 3, 3))
        self.assertEqual(image.getpixel((1, 2)), (0, 0, 255, 255))
        self.assertEqual(image.getpixel((2, 2)), (255, 0, 0, 255))

    def test_editor_normalization_is_accepted_but_changed_pivot_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'asset.png.meta'
            spec = 'guid: a\nTextureImporter:\n  serializedVersion: 12\n  spritePivot: {x: 0.50000001, y: 0}\n'
            saved = spec.replace('12', '13').replace('0.50000001', '0.5')
            path.write_text(saved)
            write_texture_meta(path, spec)
            self.assertEqual(path.read_text(), saved)
            edited = saved.replace('0.5', '0.25')
            path.write_text(edited)
            with self.assertRaises(ValueError):
                write_texture_meta(path, spec)
            self.assertEqual(path.read_text(), edited)

    def test_tab_policy_requires_two_overlapping_active_siblings(self):
        from monkey.unity_visual_repair import sibling_states
        rect = dict(m_AnchorMin={'x':0.5,'y':0.5},m_AnchorMax={'x':0.5,'y':0.5},
                    m_SizeDelta={'x':500,'y':400},m_Pivot={'x':0.5,'y':0.5},
                    m_AnchoredPosition={'x':0,'y':0})
        first = dict(node='items',path='0/0',active=True,rect=rect)
        second = dict(node='details',path='0/1',active=True,rect=rect)
        rule = dict(keep='items',hide='details',reason='item tab')
        decisions = sibling_states([first,second],[rule],'Assets/Root.prefab')
        self.assertEqual([(x['path'],x['active']) for x in decisions],[('0/1',False)])
        second['rect'] = dict(rect,m_AnchoredPosition={'x':500,'y':0})
        self.assertEqual(sibling_states([first,second],[rule],'Assets/Root.prefab'),[])

    def test_atlas_material_textures_keep_page_names_without_colliding(self):
        from types import SimpleNamespace
        from monkey.unity_visual_repair import SourceImages
        def source():
            texture = SimpleNamespace(type=SimpleNamespace(name='Texture2D'),
                                      read_typetree=lambda: {'m_Name':'page-one'})
            return SimpleNamespace(objects={7:texture})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            images = SourceImages({'cab-a':source(),'cab-b':source()}, root, root)
            images.page = lambda _: (Image.new('RGBA',(2,2),'red'),'page-one.11223344','hash')
            first = images.image(('cab-a',7))
            second = images.image(('cab-b',7))
            self.assertEqual(Path(first['asset']).stem, 'page-one')
            self.assertEqual(Path(second['asset']).stem, 'page-one')
            self.assertNotEqual(first['asset'], second['asset'])

    def test_download_request_cannot_leave_the_explicit_origin(self):
        from monkey.unity_visual_repair import fetch_declared_textures
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                fetch_declared_textures('https://example.com/assets',
                                        [dict(token='x%2fother.abcdef01',width=4,height=4)],Path(folder))
