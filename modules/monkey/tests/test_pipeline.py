import copy
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from monkey.io import read, load, sha, inside, write_json
from monkey.sources.compiled import decode_document, uuid_full, ParseError
from monkey.sources.bundle import inspect
from monkey.normalize import normalize, sprite
from fixtures import fixture, FRAME, PREFAB, normal


class PipelineTests(unittest.TestCase):
    def test_rotated_trimmed_pixels_and_insets(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();config=fixture(root/'source')
            before={p:sha(read(p)) for p in (root/'source').rglob('*') if p.is_file()}
            report=inspect(config,[0],root/'inspect')
            self.assertEqual(report['diagnostics'],[])
            ir=normalize(root/'inspect/source-manifest.json',root/'normalize')
            f=ir['spriteFrames'][0]
            self.assertEqual(f['trimOrigin'],[3,3])
            self.assertEqual(f['capInsets'],[1,0,1,1])
            with Image.open(root/'normalize'/f['image']) as image:
                self.assertEqual(image.size,(3,2));self.assertEqual(image.getpixel((0,0)),(255,0,0,255))
                self.assertEqual(image.getpixel((2,1)),(0,255,255,255))
            with Image.open(root/'normalize'/f['originalImage']) as image:
                self.assertEqual(image.size,(7,6));self.assertEqual(image.getpixel((3,3)),(255,0,0,255))
                self.assertEqual(image.getpixel((0,0)),(0,0,0,0))
            self.assertEqual(before,{p:sha(read(p)) for p in before})
            again=normalize(root/'inspect/source-manifest.json',root/'again')
            self.assertEqual(ir['files'],again['files'])

    def test_missing_font_and_unicode_remain_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();config=fixture(root/'source')
            inspect(config,[2],root/'inspect')
            ir=normalize(root/'inspect/source-manifest.json',root/'ir')
            label=next(c for c in ir['components'] if c['type']=='cc.Label')
            self.assertEqual(label['text'],'你好\nMonkey')
            self.assertTrue(any(d['code']=='MISSING_NATIVE' for d in ir['diagnostics']))
            self.assertEqual(ir['nodes'][0]['anchor'],[.25,.75])

    def test_version_bounds_pack_order_and_hash_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();config=fixture(root/'source')
            c=load(read(config));c['packs']={'pack':[2,0]};c['versions']['import']=['pack','new',1,'a',3,'a']
            prefab=load(read(root/'source/import/00'/ (PREFAB+'.a.json')))
            # Both normal object sections share class/mask dictionaries here.
            plain=normal([{'__type__':'cc.Prefab','data':{'__id__':0}}])
            pack=plain[:5]+[[plain[5:],plain[5:]]]
            path=root/'source/import/pa/pack.new.json';path.parent.mkdir();write_json(path,pack);write_json(config,c)
            result=inspect(config,[0],root/'inspect')
            self.assertEqual(result['assets'][0]['packOrdinal'],1)
            path.write_text('[]')
            with self.assertRaises(ParseError) as caught:normalize(root/'inspect/source-manifest.json',root/'bad')
            self.assertEqual(caught.exception.code,'SOURCE_CHANGED');self.assertFalse((root/'bad').exists())
            with self.assertRaises(ParseError):inspect(config,[-1],root/'negative')
            c['engineVersion']='3.8.8';write_json(config,c)
            with self.assertRaises(ParseError):inspect(config,[0],root/'wrong')

    def test_outputs_paths_unknown_encoding_and_geometry_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();config=fixture(root/'source');inspect(config,[0],root/'out')
            with self.assertRaises(ParseError):inspect(config,[0],root/'out')
            with self.assertRaises(ParseError):inspect(config,[0],root/'source/output')
            with self.assertRaises(ParseError):inside(root,'../outside')
            link=root/'link';link.symlink_to(config)
            with self.assertRaises(ParseError):read(link)
        with self.assertRaises(ParseError):decode_document([2]+[[]]*10)
        with self.assertRaises(ParseError):decode_document(normal([{'__type__':'cc.Node','n':float('inf')}]))
        image=Image.new('RGBA',(2,2))
        for frame in [dict(rect=[1,1,2,2]),dict(rect=[0,0,2,2],originalSize=[3,3]),
                      dict(rect=[0,0,2,2],capInsets=[2,0,1,0])]:
            with self.assertRaises(ParseError):sprite(image,frame)
        self.assertEqual(uuid_full('00'+'A'*20,'$'),'00000000-0000-0000-0000-000000000000')

if __name__=='__main__':unittest.main()
