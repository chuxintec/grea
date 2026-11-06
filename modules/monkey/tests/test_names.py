import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fixtures import fixture
from monkey.names import Names
from monkey.io import read,load,write_json,sha
from monkey.package import convert_package
from monkey.sources.compiled import ParseError

class NameTests(unittest.TestCase):
    def test_paths_variants_collisions_and_unsafe_sources(self):
        metadata={
            'b:1':dict(bundle='游戏',logicalPath='界面/图标/鹅.png'),
            'b:2':dict(bundle='游戏',logicalPath='界面/图标/鹅.png'),
            'b:3':dict(bundle='other',logicalPath='界面/图标/鹅.png'),
            'b:4':dict(bundle='b',logicalPath='../escape'),
            'b:5':dict(bundle='b',sourceName='CON'),
            'b:6':dict(bundle='b',logicalPath='UI/Icon'),
            'b:7':dict(bundle='b',logicalPath='ui/icon'),
        }
        names=Names(metadata)
        a=names.path('b:1','.png','images');self.assertEqual(a,'images/YouXi/JieMian/TuBiao/E.png')
        original=names.path('b:1@original','.png','images');self.assertEqual(original,'images/YouXi/JieMian/TuBiao/E.original.png')
        self.assertNotEqual(names.path('b:2','.png','images'),a)
        self.assertNotIn('--',names.path('b:3','.png','images'))
        safe=names.path('b:4','.json','data');self.assertNotIn('..',safe);self.assertIn('unknown--',safe)
        self.assertEqual(names.path('b:5','.ttf','fonts'),'fonts/b/CON_.ttf')
        upper=names.path('b:6','.png','images');lower=names.path('b:7','.png','images')
        self.assertNotEqual(upper.casefold(),lower.casefold())
        self.assertEqual(names.path('b:1','.png','images'),a)
        self.assertEqual(names.report()['collisionPaths'],2)
        self.assertNotEqual(Path(upper).parent.name.casefold(),Path(lower).parent.name.casefold())
        self.assertEqual(Names().path('con','.ttf','fonts',metadata=dict(bundle='main',logicalPath='CON.ttf')),'fonts/main/CON_.ttf')
        self.assertEqual(names.path('b:1','','spine'),'spine/YouXi/JieMian/TuBiao/E')
        self.assertEqual(Names().path('id','.js','code',metadata=dict(bundle='main',logicalPath='scripts/game.js')),'code/main/scripts/game.js')

    def test_verified_source_reuse_does_not_run_reader_or_decode_and_refuses_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();fixture(root/'source');declaration=root/'inputs.json'
            write_json(declaration,dict(schemaVersion=1,sourceProfile='cocos-2.4.15-bundle',inputs=[dict(id='main',path='source')]))
            first=convert_package(None,'both',root/'first',input_set_path=declaration)
            self.assertNotEqual(first['structuredRecovery']['status'],'failed')
            original=(root/'first/Structured/normalize/ir.json').read_bytes()
            with patch('monkey.structured.bundle.inspect',side_effect=AssertionError('reader re-run')),patch('monkey.structured.normalize',side_effect=AssertionError('pixel decode re-run')):
                second=convert_package(None,'both',root/'second',input_set_path=declaration,reuse_source_stages=root/'first')
            self.assertNotEqual(second['structuredRecovery']['status'],'failed')
            self.assertFalse(second['sourceStageReuse']['pixelDecoderExecuted'])
            self.assertEqual((root/'first/Structured/normalize/ir.json').read_bytes(),original)
            plan=load(read(root/'second/UnityProject/Analysis/Mappings/name-map.json'))
            self.assertTrue(any(r['target']=='Assets/Game/Content/Textures/UI/panel.png' for r in plan['records']))
            added=root/'source/new.js';added.write_text('unexecuted source change')
            with self.assertRaises(ParseError) as changed:
                convert_package(None,'both',root/'changed',input_set_path=declaration,reuse_source_stages=root/'first')
            self.assertEqual(changed.exception.code,'REPLAN_INPUT_CHANGED');added.unlink()
            image=next((root/'first/Structured/normalize/assets').glob('*.png'));image.write_bytes(b'manual drift')
            with self.assertRaises(ParseError) as error:
                convert_package(None,'both',root/'third',input_set_path=declaration,reuse_source_stages=root/'first')
            self.assertEqual(error.exception.code,'REPLAN_STAGE_DRIFT')
