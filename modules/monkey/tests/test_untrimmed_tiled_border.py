import tempfile
import unittest
from pathlib import Path
from PIL import Image
from monkey.io import write_json
from monkey.sources.project import inspect,catalog
from monkey.normalize import normalize
from monkey.targets.unity import plan
from fixtures import FRAME,TEXTURE,PREFAB

class UntrimmedTiledBorderTests(unittest.TestCase):
    def test_full_frame_untrimmed_view_preserves_source_nine_slice_insets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();source=root/'source';(source/'assets').mkdir(parents=True)
            write_json(source/'project.json',dict(version='2.4.15',id='border-fixture'))
            Image.new('RGBA',(20,12),(255,200,128,255)).save(source/'assets/panel.png')
            write_json(source/'assets/panel.png.meta',dict(uuid=TEXTURE,importer='texture',subMetas={
                'panel':dict(uuid=FRAME,importer='sprite-frame',rawTextureUuid=TEXTURE,trimX=0,trimY=0,width=20,height=12,rawWidth=20,rawHeight=12,offsetX=0,offsetY=0,borderLeft=3,borderTop=2,borderRight=5,borderBottom=1)}))
            write_json(source/'assets/panel.prefab.meta',dict(uuid=PREFAB,importer='prefab'))
            write_json(source/'assets/panel.prefab',[
                {'__type__':'cc.Prefab','data':{'__id__':1}},
                dict(__type__='cc.Node',_name='Panel',_parent=None,_children=[],_components=[{'__id__':2}],_contentSize={'width':100,'height':12},_anchorPoint={'x':.5,'y':.5},_trs={'__type__':'TypedArray','ctor':'Float64Array','array':[375,667,0,0,0,0,1,1,1,1]}),
                dict(__type__='cc.Sprite',node={'__id__':1},_spriteFrame={'__uuid__':FRAME},_type=2,_sizeMode=0,_isTrimmedMode=False)])
            c=catalog(source,root/'catalog');index=next(x['index']for x in c['selection']if x['key']==PREFAB)
            inspect(source,[index],root/'inspect');normalize(root/'inspect/source-manifest.json',root/'ir')
            result=plan(root/'ir/ir.json','border-test',root/'plan')
            original=next(t for t in result['textures']if t['id'].endswith('@original'))
            self.assertEqual(original['border'],[3,1,5,2])
            self.assertTrue(next(c for c in result['components']if c['type']=='cc.Sprite')['convertible'])
