import json,tempfile,unittest
from pathlib import Path
from PIL import Image
from monkey.sources.cocos_legacy import inspect,document,unpack,texture_options
from monkey.normalize import normalize
from monkey.io import load,read
from monkey.sources.compiled import ParseError


class LegacyResourcesTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'source';source.mkdir();key='12345678-1234-1234-1234-123456789abc';texture='012345678'
        settings=dict(uuids=[key,texture],packedAssets={},md5AssetsMap={'import':[key,'abcde'],'raw-assets':[texture,'12345']})
        (source/'engine.js').write_text('cc.ENGINE_VERSION="2.1.2";window._CCSettings='+json.dumps(settings)+';')
        (source/('res-import-12-'+key+'.abcde.json')).write_text(json.dumps({'__type__':'cc.SpriteFrame','content':dict(name='original',texture=texture,rect=[0,0,2,2],offset=[0,0],originalSize=[2,2],capInsets=[0,0,0,0])}))
        Image.new('RGBA',(2,2),(24,36,48,255)).save(source/('res-raw-assets-01-'+texture+'.12345.png'))
        return source

    def test_original_identity_version_and_full_pixels_feed_shared_ir(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source=self.fixture(root);result=inspect(source,root/'inspect')
            self.assertFalse(result['sourceCodeExecuted']);self.assertEqual(result['missingDeclaredAssets'],[])
            ir=normalize(root/'inspect/source-manifest.json',root/'normalize')
            self.assertEqual(len(ir['spriteFrames']),1);self.assertEqual(ir['nodes'],[])
            with Image.open(root/'normalize'/ir['spriteFrames'][0]['image'])as image:self.assertEqual(image.getpixel((0,0)),(24,36,48,255))

    def test_wrong_cache_version_is_a_gap_and_never_selected(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source=self.fixture(root)
            path=next(source.glob('*.png'));path.rename(path.with_name(path.name.replace('12345.png','fffff.png')))
            result=inspect(source,root/'inspect');self.assertTrue(result['missingDeclaredAssets'])
            ir=normalize(root/'inspect/source-manifest.json',root/'normalize');self.assertEqual(ir['spriteFrames'],[])
            self.assertTrue(any(d['code']=='LEGACY_CACHE_VERSION_MISMATCH'for d in result['diagnostics']))

    def test_stale_equivalent_image_never_deduplicates_into_runtime_assets(self):
        from monkey.package import convert_package
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source=self.fixture(root);selected=next(source.glob('*.png'))
            stale=selected.with_name(selected.name.replace('12345.png','fffff.png'));stale.write_bytes(selected.read_bytes())
            declaration=root/'inputs.json';declaration.write_text(json.dumps(dict(schemaVersion=1,sourceProfile='cocos-2.1.2-resource',inputs=[dict(id='original',path=str(source))])))
            result=convert_package(None,'both',root/'out',input_set_path=declaration,offline=True)
            self.assertEqual(len(result['sourceInputExclusions']),1)
            for target in ('UnityProject','CocosProject'):
                rows=load(read(root/'out'/target/'Analysis/Ledger/resource-ledger.json'))['files'];old=next(r for r in rows if r['localPath']==stale.name)
                new=next(r for r in rows if r['localPath']==selected.name)
                self.assertTrue(old['target'].startswith('SourceRecovery/Excluded/'));self.assertEqual(old['targetState'],'excluded_from_runtime')
                self.assertNotEqual(old['target'],new['target'])
                # The selected image is carried by its normalized sprite; its raw bytes are evidence, never runtime content.
                self.assertTrue(new['target'].startswith('SourceRecovery/Original/'));self.assertEqual(new['disposition'],'structured_candidate')

    def test_unknown_geometry_is_not_silently_projected(self):
        with self.assertRaises(ParseError):document({'__type__':'cc.SpriteFrame','content':{'vertices':[1,2]}})

    def test_source_only_graph_body_stays_in_original_bytes_and_public_mapping(self):
        from monkey.package import convert_package
        from monkey.io import sha
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source=self.fixture(root);settings=dict(uuids=['12345678-1234-1234-1234-123456789abc','012345678','11111111-1111-1111-1111-111111111111'],packedAssets={},md5AssetsMap={'import':['12345678-1234-1234-1234-123456789abc','abcde','11111111-1111-1111-1111-111111111111','eeeee'],'raw-assets':['012345678','12345']})
            (source/'engine.js').write_text('cc.ENGINE_VERSION="2.1.2";window._CCSettings='+json.dumps(settings)+';')
            body=[dict(__type__='cc.Prefab',data={'__id__':1}),dict(__type__='cc.Node',_name='Original',_children=[])]
            raw=json.dumps(body).encode();path=source/'res-import-11-11111111-1111-1111-1111-111111111111.eeeee.json';path.write_bytes(raw)
            for key,kind in [('22222222-2222-2222-2222-222222222222','cc.BitmapFont'),('33333333-3333-3333-3333-333333333333','sp.SkeletonData')]:
                settings['uuids'].append(key);settings['md5AssetsMap']['import'].extend([key,'fffff'])
                (source/('res-import-'+key[:2]+'-'+key+'.fffff.json')).write_text(json.dumps(dict(__type__=kind)))
            (source/'engine.js').write_text('cc.ENGINE_VERSION="2.1.2";window._CCSettings='+json.dumps(settings)+';')
            declaration=root/'inputs.json';declaration.write_text(json.dumps(dict(schemaVersion=1,sourceProfile='cocos-2.1.2-resource',inputs=[dict(id='original',path=str(source))])))
            result=convert_package(None,'unity6',root/'out',input_set_path=declaration,offline=True)
            self.assertTrue(result['completed']);self.assertEqual(result['structuredRecovery']['normalized']['spriteFrames'],1)
            inspected=load(read(root/'out/Structured/inspect/source-manifest.json'));asset=next(a for a in inspected['assets']if a['kind']=='cc.Prefab')
            self.assertIsNone(asset['document']);self.assertEqual(asset['sourceDocument']['payloadSha256'],sha(raw))
            objects=load(read(root/'out/UnityProject/Analysis/Evidence/structured-objects.json'))['objects'];obj=next(a for a in objects if a['kind']=='cc.Prefab')
            self.assertTrue(obj['sourceInputs']);self.assertEqual(obj['sourceDocument']['memberKey'],asset['key'])
            self.assertEqual(result['projects'][0]['coverage']['spineClosures']['unresolved'],1)
            ledger=load(read(root/'out/UnityProject/Analysis/Ledger/resource-ledger.json'))
            row=next(r for r in ledger['files']if r['localPath']==path.name);self.assertEqual((root/'out/UnityProject'/row['target']).read_bytes(),raw)

    def test_texture_unpacker_preserves_original_format_sampler_and_alpha(self):
        rows=unpack(['png','jpg'],dict(type='cc.Texture2D',data='0,9729,9729,33071,33071,0|1,9728,9729,10497,33071,1'),'fixture')
        self.assertEqual([key for key,_ in rows],['png','jpg'])
        png=document(rows[0][1])['instances'][0]['textureOptions'];jpg=document(rows[1][1])['instances'][0]['textureOptions']
        self.assertEqual(png['nativeExtension'],'.png');self.assertEqual(jpg['nativeExtension'],'.jpg');self.assertTrue(jpg['premultiplyAlpha']);self.assertEqual(jpg['wrapS'],10497)
        self.assertEqual(texture_options('0,9729,9729,33071,33071,0,12@8')['originalSize'],[12,8])
        with self.assertRaisesRegex(ParseError,'PACK_LENGTH'):unpack(['one'],dict(type='cc.Texture2D',data='a|b'),'fixture')
        with self.assertRaisesRegex(ParseError,'TEXTURE_FORMAT'):texture_options('0_7,9729,9729,33071,33071,0')

    def test_package_directory_texture_pack_and_equivalent_native_alias_are_read(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source=self.fixture(root);settings=dict(uuids=['12345678-1234-1234-1234-123456789abc','012345678'],packedAssets={'0abcdef12':[1]},md5AssetsMap={'import':['12345678-1234-1234-1234-123456789abc','abcde','0abcdef12','aaaaa'],'raw-assets':['012345678','12345']})
            (source/'engine.js').write_text('cc.ENGINE_VERSION="2.1.2";window._CCSettings='+json.dumps(settings)+';')
            package=source/'res/import/0a';package.mkdir(parents=True);(package/'0abcdef12.aaaaa.json').write_text(json.dumps(dict(type='cc.Texture2D',data='0,9729,9729,33071,33071,0')))
            native=source/'res/raw-assets/01';native.mkdir(parents=True);(native/'012345678.12345.png').write_bytes(next(source.glob('*.png')).read_bytes())
            result=inspect(source,root/'inspect');texture=next(a for a in result['assets']if a['key']=='012345678')
            self.assertEqual(texture['document']['instances'][0]['textureOptions']['nativeExtension'],'.png');self.assertTrue(texture['nativeAliases'])
            ir=normalize(root/'inspect/source-manifest.json',root/'normalize');self.assertEqual(len(ir['spriteFrames']),1)


if __name__=='__main__':unittest.main()
