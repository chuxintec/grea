import tempfile
import unittest
from pathlib import Path
from monkey.io import write_json
from monkey.sources.cache import plan,entries
from monkey.sources.compiled import ParseError


class CacheTests(unittest.TestCase):
    def test_cache_and_temp_wxfile_mapping_no_remote_fetch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();(root/'usr').mkdir();(root/'usr/one').write_bytes(b'local')
            for kind,name,field in [('cache','cacheList.json','url'),('temp','tempFileList.json','path')]:
                p=root/name;write_json(p,dict(version='frozen',files={
                    'https://example.invalid/cdn/gameAsset/import/00/a.json?token=private':
                        dict(bundle='gameAsset',**{field:'wxfile://usr/one'}),
                    'https://example.invalid/cdn/gameAsset/import/00/missing.json':
                        dict(bundle='gameAsset',**{field:'wxfile://usr/absent'})}))
                m=plan(root,p,kind);self.assertEqual(m['records'][0]['path'],'gameAsset/import/00/a.json')
                self.assertEqual(m['missing'][0]['reason'],'input_not_provided')
                self.assertNotIn('token',str(m['records']))
                self.assertEqual(dict(entries(root,p,kind))['gameAsset/import/00/a.json'],b'local')

    def test_package_reports_missing_cache_mapping_without_fetching(self):
        from monkey.package import convert_package
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();source=root/'cache';(source/'usr').mkdir(parents=True)
            write_json(source/'usr/config',dict(name='main',engineVersion='2.4.15',uuids=[],paths={},types=[],packs={}))
            write_json(source/'cacheList.json',dict(files={
                'https://example.invalid/main/config.json':dict(bundle='main',url='wxfile://usr/config'),
                'https://example.invalid/main/native/00/missing.png':dict(bundle='main',url='wxfile://usr/missing')}))
            declaration=root/'inputs.json'
            write_json(declaration,dict(schemaVersion=1,sourceProfile='cocos-2.4.15-bundle',inputs=[
                dict(id='cache',path='cache',cacheList='cacheList.json',cacheKind='cache')]))
            result=convert_package(None,'unity6',root/'out',input_set_path=declaration)
            self.assertTrue(result['completed'])
            self.assertEqual(result['cacheInputs'][0]['availableMappings'],1)
            self.assertEqual(result['cacheInputs'][0]['missing'][0]['reason'],'input_not_provided')
            self.assertEqual(result['inputFiles'],2)

    def test_cache_traversal_duplicate_content_conflict_and_bad_url(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();(root/'a').write_bytes(b'a');(root/'b').write_bytes(b'b');p=root/'cacheList.json'
            for remote,local in [('https://x/game/import/%2e%2e/escape','wxfile://a'),
                                 ('https://x/game/import/a','wxfile://../escape'),
                                 ('https://x/notgame/import/a','wxfile://a'),
                                 ('file:///game/a','wxfile://a')]:
                write_json(p,dict(files={remote:dict(bundle='game',url=local)}))
                with self.assertRaises(ParseError):plan(root,p,'cache')
            write_json(p,dict(files={'https://x/game/import/a?q=1':dict(bundle='game',url='wxfile://a'),
                                    'https://x/game/import/a?q=2':dict(bundle='game',url='wxfile://b')}))
            with self.assertRaises(ParseError):plan(root,p,'cache')


if __name__=='__main__':unittest.main()
