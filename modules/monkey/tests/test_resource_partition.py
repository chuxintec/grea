import tempfile,unittest
from pathlib import Path
from PIL import Image
from monkey.layout import LayoutPlanner
from monkey.layout.overrides import validate
from monkey.layout.records import resource_paths
from monkey.assets.catalog import export_catalog
from monkey.io import write_json,load,read,sha
from monkey.sources.compiled import ParseError


class ResourceLayoutTests(unittest.TestCase):
    def test_full_texture_dedup_preserves_sprite_metadata_and_distinct_pixels(self):
        from monkey.targets import cocos
        from monkey.layout.standard import ROOTS
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();source=root/'source';source.mkdir()
            Image.new('RGBA',(8,4),(1,2,3,255)).save(source/'same.png')
            Image.new('RGBA',(8,4),(3,2,1,255)).save(source/'different.png')
            manifest=dict(bundle='main',sourceRoots={'main':str(source)},inputs=[dict(path=p.name,sha256=sha(read(p))) for p in source.iterdir()],assets=[
                dict(sourceId=s,kind='cc.Texture2D',native=n,logicalPath='Texture/UI/icon') for s,n in [('main:a','same.png'),('main:b','same.png'),('main:c','different.png')]])
            for engine in ('unity','creator'):
                project=root/engine;relative=ROOTS[engine]['content']+'/Textures/UI/icon.png';image=project/relative
                image.parent.mkdir(parents=True);image.write_bytes(read(source/'same.png'));meta=Path(str(image)+'.meta')
                if engine=='unity':meta.write_text('fileFormatVersion: 2\nguid: '+'a'*32+'\nTextureImporter:\n  spriteMode: 1\n')
                else:write_json(meta,cocos.meta(cocos.identity('test','frame'),'image','1.0.27',dict(type='sprite-frame')))
                original_meta=read(meta)
                write_json(project/'Analysis/Mappings/name-map.json',dict(records=[dict(sourceId='frame',identity='frame',kind='sprite',type='sprite',target=relative)]))
                report=export_catalog(manifest,project,engine,'test',root/'cache')
                self.assertEqual(report['deduplicatedTextures'],2);self.assertEqual(report['writtenTextures'],1)
                self.assertEqual(read(meta),original_meta);self.assertEqual(read(image),read(source/'same.png'))
                distinct=next(r for r in report['textures'] if r['sourceId']=='main:c')
                self.assertNotEqual(distinct['path'],relative);self.assertEqual(read(project/distinct['path']),read(source/'different.png'))
                self.assertEqual(len(list(image.parent.glob('*.png'))),2)
                resource_paths(project,engine);rows=load(read(project/'Analysis/Mappings/resource-paths.json'))['assets']
                self.assertEqual({r['sourceId'] for r in rows if r['path']==relative},{'frame','main:a','main:b'})
                if engine=='creator':
                    self.assertTrue(next(r for r in rows if r['sourceId']=='frame')['loadKey'].endswith('/spriteFrame'))
                    self.assertTrue(next(r for r in rows if r['sourceId']=='main:a')['loadKey'].endswith('/texture'))

    def test_module_spelling_is_shared_by_texture_and_audio(self):
        metadata={'t':dict(bundle='miniGameRes',logicalPath='Texture/cupmerge/Icon/pic'),
                  'a':dict(bundle='miniGameRes',logicalPath='Audio/CupMerge/beep')}
        for engine in ('unity','creator'):
            p=LayoutPlanner(engine,metadata)
            self.assertIn('/MiniGames/CupMerge/',p.path('t','texture','.png'))
            self.assertIn('/MiniGames/CupMerge/',p.path('a','cc.AudioClip','.wav'))

    def test_shared_ir_audio_is_physically_exported_by_both_targets(self):
        import wave
        from fixtures import fixture,custom
        from monkey.package import convert_package
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();config=fixture(root/'source');data=load(read(config))
            uid='00000000-0000-0000-0000-000000000005';index=len(data['uuids']);data['uuids'].append(uid)
            data['types'].append('cc.AudioClip');data['paths'][str(index)]=['Audio/BGM/测试音乐',len(data['types'])-1]
            data['versions']['import'] += [index,'a'];data['versions']['native'] += [index,'b'];write_json(config,data)
            write_json(config.parent/'import/00'/(uid+'.a.json'),custom('cc.AudioClip',dict(_name='测试音乐',_duration=.1)))
            native=config.parent/'native/00'/(uid+'.b.wav')
            with wave.open(str(native),'wb') as audio:
                audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(8000);audio.writeframes(b'\0\0'*800)
            convert_package(config.parent,'both',root/'out')
            for name in ('UnityProject','CocosProject'):
                project=root/'out'/name;manifest=load(read(project/'manifest.json'))
                exported=[r for r in manifest['files'] if r['path'].startswith(('Assets/','assets/')) and r['path'].endswith('.wav')]
                self.assertEqual(len(exported),1);self.assertEqual(read(project/exported[0]['path']),read(native))
                self.assertIn('/Audio/Music/',exported[0]['path'])

    def test_shader_asset_named_after_source_type_is_not_a_source_container(self):
        from monkey.layout.verify import scan
        self.assertEqual(scan(['Assets/Game/Content/Shaders/Common/MovieClip/EffectDescription.json']),[])
        self.assertTrue(scan(['Assets/Game/Content/Shaders/MovieClip/Unrelated/file.json']))
        self.assertTrue(scan(['assets/resources/Textures/Original/file.png']))
        self.assertEqual(scan(['assets/resources/Strings/En/Label.json']),[])

    def test_source_bundles_never_become_directories(self):
        for source in ('remoteAsset','main','original','snapshot'):
            metadata={'r:1':dict(bundle=source,logicalPath='Texture/UI/按钮')}
            paths=[]
            for engine in ('unity','creator'):
                p=LayoutPlanner(engine,metadata);paths.append(p.path('r:1','sprite','.png'))
                self.assertEqual(p.records[0]['sourceId'],'r:1')
                self.assertNotIn('partition',p.records[0])
            self.assertEqual(paths,['Assets/Game/Content/Textures/UI/an_niu.png','assets/resources/Textures/UI/an_niu.png'])
        with self.assertRaises(ParseError):validate(dict(schemaVersion=1,partitions=[dict(match='*',group='Boot',placement='resources')]))

    def test_source_collisions_keep_distinct_identity_and_loading_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp).resolve();naming=LayoutPlanner('creator',{s:dict(bundle=s,logicalPath='UI/Icon') for s in ('a','b')})
            naming.reserve([(s,'sprite','.png','',None,None) for s in ('a','b')])
            write_json(project/'Analysis/Mappings/name-map.json',naming.report())
            resource_paths(project,'creator')
            records=load(read(project/'Analysis/Mappings/resource-paths.json'))['assets']
            self.assertEqual(len({r['loadKey'] for r in records}),2)
            self.assertTrue(all(r['loadKey'].startswith('Textures/UI/icon') for r in records))
            self.assertFalse((project/'assets/Bundles').exists())

    def test_final_filename_budget_includes_variant_and_extension(self):
        p=LayoutPlanner('unity',{'a':dict(bundle='main',logicalPath='UI/'+'Word'*40)})
        names=[p.path('a','sprite','.png'),p.path('a@original','sprite','.png')]
        self.assertEqual(len(set(names)),2)
        self.assertTrue(all(len(Path(n).name.encode())<=64 for n in names))

    def test_full_texture_and_shader_source_have_provenance_and_no_fake_shader(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();source=root/'source';source.mkdir();Image.new('RGBA',(8,4),(1,2,3,255)).save(source/'page.png')
            raw=(source/'page.png').read_bytes();effect={'__type__':'cc.EffectAsset','shaders':[{'glsl1':{'vert':'void main() {}','frag':'original fragment'}}]}
            manifest=dict(bundle='main',sourceRoots={'main':str(source)},inputs=[dict(path='page.png',sha256=sha(raw))],assets=[
                dict(sourceId='main:t',kind='cc.Texture2D',native='page.png',logicalPath='Texture/UI/page'),
                dict(sourceId='main:s',kind='cc.EffectAsset',logicalPath='Shaders/UI/glow',document=dict(instances=[effect]))])
            for engine in ('unity','creator'):
                project=root/engine;project.mkdir();report=export_catalog(manifest,project,engine,'test',root/'cache')
                with Image.open(project/report['textures'][0]['path']) as image:self.assertEqual(image.size,(8,4));self.assertEqual(image.getpixel((0,0)),(1,2,3,255))
                shader=report['shaders'][0];self.assertFalse(shader['nativeShader']);self.assertEqual(len(shader['files']),3)
                frag=next(f for f in shader['files'] if f['path'].endswith('.frag.glsl'))
                self.assertEqual((project/frag['path']).read_text(),'original fragment')
                self.assertFalse(list(project.rglob('*.shader')))
                resource_paths(project,engine)
                groups=load(read(project/'Analysis/Mappings/resource-paths.json'))
                self.assertFalse(groups['remoteConfigured']);self.assertNotIn('groups',groups)
                closure=next(r for r in groups['assets'] if r['entryKind']=='closure-prefix');self.assertIsNone(closure['loadKey'])
