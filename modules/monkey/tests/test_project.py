import tempfile
import unittest
import re
from pathlib import Path
from PIL import Image
from monkey.io import write_json, read, load
from monkey.sources.project import inspect, catalog
from monkey.sources.compiled import ParseError
from monkey.normalize import normalize
from monkey.targets.unity import plan, export
from fixtures import FRAME, TEXTURE, PREFAB


class EditableProjectTests(unittest.TestCase):
    def test_meta_and_native_scene_are_separate_from_compiled_reader(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();source=root/'source';(source/'assets').mkdir(parents=True)
            write_json(source/'project.json',dict(version='2.4.15',id='editable-fixture'))
            Image.new('RGBA',(8,6),(0,128,255,255)).save(source/'assets/panel.png')
            write_json(source/'assets/panel.png.meta',dict(uuid=TEXTURE,importer='texture',subMetas={
                'panel':dict(uuid=FRAME,importer='sprite-frame',rawTextureUuid=TEXTURE,
                             trimX=1,trimY=1,width=4,height=3,rawWidth=6,rawHeight=5,offsetX=0,offsetY=0,
                             borderLeft=1,borderTop=1,borderRight=1,borderBottom=1)}))
            write_json(source/'assets/panel.prefab.meta',dict(uuid=PREFAB,importer='prefab'))
            write_json(source/'assets/panel.prefab',[
                {'__type__':'cc.Prefab','data':{'__id__':1}},
                dict(__type__='cc.Node',_name='Editable panel',_parent=None,_children=[],_components=[{'__id__':2}],
                     _contentSize={'width':240,'height':150},_anchorPoint={'x':.5,'y':.5},
                     _trs={'__type__':'TypedArray','ctor':'Float64Array','array':[375,667,0,0,0,0,1,1,1,1]}),
                dict(__type__='cc.Sprite',node={'__id__':1},_spriteFrame={'__uuid__':FRAME},_type=1,_sizeMode=0)])
            c=catalog(source,root/'catalog');index=next(x['index'] for x in c['selection'] if x['key']==PREFAB)
            m=inspect(source,[index],root/'inspect');self.assertEqual(len(m['assets']),3)
            ir=normalize(root/'inspect/source-manifest.json',root/'ir')
            self.assertEqual(ir['diagnostics'],[]);self.assertEqual(ir['nodes'][0]['position'],[375,667,0])
            self.assertEqual(ir['spriteFrames'][0]['trimOrigin'],[1,1])
            plan(root/'ir/ir.json','editable-test',root/'plan');out=export(root/'plan/plan.json',root/'unity')
            self.assertEqual(out['diagnostics'],[])
            empty_slot_script=root/'unity/Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortTextSlotEnumerationIdentity.cs'
            empty_slot_meta=Path(str(empty_slot_script)+'.meta')
            self.assertTrue(empty_slot_script.is_file())
            self.assertIn('public sealed class NativeStaticSortTextSlotEnumerationIdentity',empty_slot_script.read_text())
            self.assertTrue(empty_slot_meta.is_file())
            emitted_guid=re.search(r'^guid: ([0-9a-f]{32})$',empty_slot_meta.read_text(),re.M)
            self.assertIsNotNone(emitted_guid)
            self.assertIn('NativeStaticSortTextSlotEnumerationIdentity',empty_slot_script.read_text())
            self.assertNotIn('class NativeStaticSortTextSlotEnumerationIdentity',
                             (root/'unity/Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortTextSource.cs').read_text())
            for runtime_name in ('NativeInputBlocker.cs','NativeInputBlockerSurface.cs'):
                runtime_script=root/'unity/Assets/Game/Presentation/Common/Layout'/runtime_name
                self.assertTrue(runtime_script.is_file())
                self.assertIn('class '+runtime_name[:-3],runtime_script.read_text())
                runtime_meta=Path(str(runtime_script)+'.meta')
                self.assertTrue(runtime_meta.is_file())
                self.assertRegex(runtime_meta.read_text(),r'(?m)^guid: [0-9a-f]{32}$')
            write_json(source/'project.json',dict(version='3.8.8',id='wrong-version'))
            with self.assertRaises(ParseError):catalog(source,root/'wrong')

if __name__=='__main__':unittest.main()
