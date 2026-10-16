import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image
from grea.brand_assets import validate_asset, validate_interface

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_skill
import build_plugin
import test_plugin_bundle as bundle_tests
import test_skill_distribution as skill_tests


def png():
    image=Image.new('RGBA',(64,64));image.paste((30,220,170,255),(8,8,56,56));stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()


class BrandTests(unittest.TestCase):
    def test_narrow_asset_validation(self):
        self.assertEqual(validate_asset('plugin/assets/icon_64.png',png())['width'],64)
        for name,data in [('plugin/assets/anything.png',png()),('elsewhere/icon_64.png',png()),('plugin/assets/icon_64.png',png()+b'executable'),('plugin/assets/logo_dark.svg',b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>')]:
            with self.subTest(name=name),self.assertRaises(ValueError):validate_asset(name,data)

    def test_both_package_roots_and_manifest_paths(self):
        source=skill_tests.SkillDistributionTests().source();manifest=json.loads(source['plugin/.codex-plugin/plugin.json'][0]);manifest['interface']={'composerIcon':'./assets/icon_64.png','logo':'./assets/icon_64.png','brandColor':'#20C8A0'};source['plugin/.codex-plugin/plugin.json']=(json.dumps(manifest).encode(),0o100644);source['plugin/assets/icon_64.png']=(png(),0o100644)
        files=build_skill.render(source,'1.2.3rc1','a'*40);self.assertEqual(files['grea/assets/icon_64.png'],png())
        validate_interface(json.loads(files['grea/.codex-plugin/plugin.json']),lambda p:files['grea/'+p])
        full=bundle_tests.PluginBundleTests().source_fixture();full['plugin/assets/icon_64.png']=(png(),0o100644);m=json.loads(full['plugin/.codex-plugin/plugin.json'][0]);m['interface']=manifest['interface'];full['plugin/.codex-plugin/plugin.json']=(json.dumps(m).encode(),0o100644)
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve()/'中文 moved plugin';build_plugin.write_product(full,root)
            actual=json.loads((root/'.codex-plugin/plugin.json').read_text());self.assertEqual(actual['interface']['composerIcon'],'./plugin/assets/icon_64.png');validate_interface(actual,lambda p:(root/p).read_bytes())
        source.pop('plugin/assets/icon_64.png')
        with self.assertRaises((ValueError,KeyError)):build_skill.render(source,'1.2.3rc1','a'*40)
