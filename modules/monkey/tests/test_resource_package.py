import json,tempfile,unittest
from pathlib import Path
from PIL import Image
from monkey.resource_package import convert
from monkey.sources.compiled import ParseError


class GenericImageTests(unittest.TestCase):
    def test_explicit_other_engine_exports_only_derived_images_and_preserves_code(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source=root/'input';source.mkdir()
            Image.new('RGBA',(3,2),(18,28,38,255)).save(source/'source.png')
            original='throw Error("This source must never run");'
            (source/'game.js').write_text(original);(source/'manifest.bin').write_bytes(b'unknown')
            result=convert(source,'unity6',root/'out',family='egret',offline=True)
            self.assertTrue(result['completed']);self.assertEqual(result['inputFiles'],3)
            self.assertEqual(result['derivedFullImageFrames'],1);self.assertEqual(result['sourceSpriteFrames'],0)
            self.assertEqual(result['sourceGraphsRestored'],0);self.assertEqual(result['methodsRecovered'],0)
            project=root/'out/UnityProject'
            self.assertEqual((project/'SourceRecovery/Original/source/game.js').read_text(),original)
            self.assertFalse(list((project/'Assets').rglob('*.js')))
            plan=json.loads((project/'Assets/Game/Editor/Conversion/import-plan.json').read_text())
            self.assertTrue(plan['galleryOnly']);self.assertEqual(plan['nodes'],[])
            # Gallery sprites have no trim=false Sprite, so no untrimmed duplicate is planned.
            self.assertEqual(len(plan['textures']),1);self.assertFalse(any(t['id'].endswith('@original') for t in plan['textures']))
            from monkey.targets import cocos
            with self.assertRaises(ParseError):cocos.plan(root/'out/Structured/normalize/ir.json','same',root/'forbidden')
            self.assertFalse((root/'forbidden').exists())

    def test_creator_target_rejects_before_writing(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source=root/'input';source.mkdir()
            with self.assertRaises(ParseError):convert(source,'both',root/'out',family='custom')
            self.assertFalse((root/'out').exists())

    def test_unknown_binary_only_blocks_without_fake_engine_project(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source=root/'input';source.mkdir();(source/'data.bin').write_bytes(b'unknown')
            result=convert(source,'unity6',root/'out',family='laya')
            self.assertFalse(result['completed']);self.assertEqual(result['status'],'blocked')
            self.assertFalse((root/'out/UnityProject').exists())


if __name__=='__main__':unittest.main()
