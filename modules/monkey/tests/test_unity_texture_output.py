import importlib.util
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from monkey.io import write_json,sha
from monkey.layout.standard import find_analysis
from monkey.normalize import open_texture
from monkey.unity_texture_output import lossless_textures
from monkey.sources.compiled import ParseError


@unittest.skipUnless(importlib.util.find_spec('texture2ddecoder'),'optional ASTC decoder required')
class TextureOutputTests(unittest.TestCase):
    def fixture(self,root):
        relative='Assets/Game/Content/Textures/Effect/Noise.jpg';image=root/relative;image.parent.mkdir(parents=True)
        Image.new('RGB',(4,4),'blue').save(image)
        meta=Path(str(image)+'.meta');meta.write_text('guid: '+'1'*32+'\nTextureImporter:\n  textureType: 0\n')
        logical='Assets/Textures/astc/4/noise.txt';cache=root/'SourceRecovery/TextureCache'/logical;cache.parent.mkdir(parents=True)
        raw=bytes.fromhex('13aba15c040401040000040000010000fcfdffffffffffffffff00000000ffff');cache.write_bytes(raw)
        rgba=open_texture(raw,'.astc').tobytes();source=dict(file='CAB-exact',pathId='42',fileId='0',logicalPath='assets/effect/noise.jpg')
        write_json(find_analysis(root,'full-resource-handoff.json'),dict(sourceToTarget=[dict(source=source,target=dict(path=relative,guid='1'*32))]))
        write_json(find_analysis(root,'texture-hydration.json'),dict(consumed=[dict(file='CAB-exact',pathId='42',logicalPath=logical,cacheBytes=len(raw),cacheSha256=sha(raw),rgbaRawSha256=sha(rgba),astc=dict(width=4,height=4))]))
        write_json(find_analysis(root,'unity-relocation.json'),dict(moves=[dict(source='Assets/effect/noise.jpg',target=relative)]))
        return image,meta,cache,rgba

    def test_replaces_lossy_output_from_exact_source_and_preserves_guid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();old,meta,cache,rgba=self.fixture(root);meta_raw=meta.read_bytes()
            result=lossless_textures(root);self.assertEqual(result['normalized'],1);self.assertFalse(old.exists());self.assertFalse(meta.exists())
            new=old.with_suffix('.png');self.assertEqual(Path(str(new)+'.meta').read_bytes(),meta_raw)
            with Image.open(new) as im:self.assertEqual(im.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes(),rgba)
            self.assertIn('Noise.png',find_analysis(root,'unity-relocation.json').read_text())

    def test_changed_original_stops_before_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();old,meta,cache,rgba=self.fixture(root);before=old.read_bytes();cache.write_bytes(b'changed')
            with self.assertRaises(ParseError):lossless_textures(root)
            self.assertEqual(old.read_bytes(),before);self.assertTrue(meta.exists());self.assertFalse(old.with_suffix('.png').exists())

    def test_does_not_overwrite_existing_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();old,meta,cache,rgba=self.fixture(root);new=old.with_suffix('.png');new.write_bytes(b'manual')
            with self.assertRaises(ParseError):lossless_textures(root)
            self.assertEqual(new.read_bytes(),b'manual');self.assertTrue(old.exists());self.assertTrue(meta.exists())
