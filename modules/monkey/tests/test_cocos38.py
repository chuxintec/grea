import tempfile,unittest,json
from pathlib import Path
from fixtures import FRAME,TEXTURE,PREFAB,custom,normal,fixture
from monkey.io import write_json,load,read
from monkey.package import convert_package
from monkey.sources.compiled import asset_key,ParseError
from monkey.sources.cocos38 import texture_sections


def fixture38(root):
    config=fixture(root);frame=FRAME+'@f9941';texture=TEXTURE+'@6c48a'
    write_json(root/'settings.test.json',dict(CocosEngine='3.8.7'))
    write_json(config,dict(name='main',engineVersion='3.8.7',uuids=[frame,texture,TEXTURE,PREFAB],
        paths={'0':['image/spriteFrame',0],'1':['image/texture',1],'2':['image',2],'3':['View',3]},
        types=['cc.SpriteFrame','cc.Texture2D','cc.ImageAsset','cc.Prefab'],packs={'texpack':[1]},
        versions={'import':[0,'a',2,'a',3,'a','texpack','a'],'native':[2,'b']}))
    payload=dict(name='cropped',rect=dict(x=1,y=1,width=3,height=2),offset=dict(x=0,y=0),originalSize=dict(width=3,height=2),rotated=False,capInsets=[0]*4,pivot=dict(x=.5,y=.5),meshType=0,pixelsToUnit=100)
    write_json(root/'import'/frame[:2]/(frame+'.a.json'),[1,[texture],['_textureSource'],['cc.SpriteFrame'],0,[payload],[0],0,[0],[0],[0]])
    pack=root/'import/te/texpack.a.json';pack.parent.mkdir(parents=True)
    write_json(pack,dict(type='cc.Texture2D',data=[['2,2,0,0,0,0',[TEXTURE]]]))
    write_json(root/'import'/TEXTURE[:2]/(TEXTURE+'.a.json'),custom('cc.ImageAsset',dict(fmt='0',w=6,h=6)))
    write_json(root/'import'/PREFAB[:2]/(PREFAB+'.a.json'),normal([dict(__type__='cc.Prefab',data={'__id__':1}),dict(__type__='cc.Node',_name='No invented identity transform',_lpos=dict(x=17,y=23,z=4),_components=[])]))
    return config


class Creator38Tests(unittest.TestCase):
    def test_auto_versioned_resource_export_preserves_subasset_and_exact_texture_image_chain(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();config=fixture38(root/'source')
            report=convert_package(config.parent,'both',root/'out')
            self.assertTrue(report['completed']);self.assertEqual(report['structuredRecovery']['sourceProfile'],'cocos-3.8.7-bundle')
            self.assertNotEqual(report['structuredRecovery']['status'],'failed',report['structuredRecovery'])
            ir=load(read(root/'out/Structured/normalize/ir.json'))
            self.assertEqual(len(ir['spriteFrames']),1);self.assertEqual(len(ir['nodes']),1);self.assertEqual(ir['nodes'][0]['position'],[17,23,4]);self.assertEqual(ir['nodes'][0]['scale'],[1,1,1])
            frame=ir['spriteFrames'][0]
            self.assertTrue(frame['sourceId'].endswith('@f9941'));self.assertTrue(frame['sourceResourceEvidence']['sourceTexture'].endswith('@6c48a'))
            self.assertEqual(frame['textureRef'],'main:'+TEXTURE)
            self.assertEqual(ir['nodes'][0]['sourceGeometryProfile'],'cocos-3.8.7-node-ui-v1')
            for name,plan in [('UnityProject','Assets/Game/Editor/Conversion/import-plan.json'),('CocosProject','extensions/monkey-import/import-plan.json')]:
                data=load(read(root/'out'/name/plan));self.assertEqual(len(data['nodes']),1)
                self.assertTrue((root/'out'/name/'manifest.json').exists())
            self.assertEqual(load(read(root/'out/Structured/inspect/source-manifest.json'))['sourceVersion'],'3.8.7')
            declaration=root/'wrong-profile.json';write_json(declaration,dict(schemaVersion=1,sourceProfile='cocos-2.4.15-bundle',inputs=[dict(id='source',path=str(config.parent))]))
            with self.assertRaisesRegex(ParseError,'SOURCE_ENGINE_PROFILE_CONFLICT'):convert_package(None,'both',root/'wrong',input_set_path=declaration)

    def test_unsupported_v3_widget_is_retained_without_breaking_either_target_emission(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();config=fixture38(root/'source')
            write_json(config.parent/'import'/PREFAB[:2]/(PREFAB+'.a.json'),normal([dict(__type__='cc.Prefab',data={'__id__':1}),dict(__type__='cc.Node',_components=[dict(__type__='cc.Widget',node={'__id__':1},_alignFlags=128)])]))
            report=convert_package(config.parent,'both',root/'out')
            self.assertNotEqual(report['structuredRecovery']['status'],'failed',report['structuredRecovery'])
            plan=load(read(root/'out/Structured/CocosProject-plan/plan.json'))
            self.assertFalse(plan['components'][0]['convertible']);self.assertIsNone(plan['components'][0]['nativeType'])
            self.assertTrue((root/'out/CocosProject/extensions/monkey-import/execution.js').is_file())

    def test_array_texture_pack_does_not_guess_multi_image_or_strip_subassets(self):
        self.assertNotEqual(asset_key(FRAME+'@f9941'),asset_key(FRAME+'@6c48a'))
        self.assertEqual(asset_key('1113c2c5c@6c48a'),'1113c2c5c@6c48a')
        for value in [FRAME+'@../x',FRAME+'@f9941@6c48a']:
            with self.assertRaises(ParseError):asset_key(value)
        for data in [[['2,2,0,0,0,0',[TEXTURE,FRAME]]],[['bad',[TEXTURE]]]]:
            with self.assertRaises(ParseError):texture_sections(dict(type='cc.Texture2D',data=data))
        mixed=dict(type='cc.Texture2D',data=[['2,2,0,0,0,0',[TEXTURE]],['bad',[FRAME,TEXTURE]]])
        self.assertEqual(len(texture_sections(mixed,0)),1)
        with self.assertRaises(ParseError):texture_sections(mixed,1)
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();config=fixture38(root/'source');(config.parent/'settings.test.json').unlink()
            declaration=root/'inputs.json';write_json(declaration,dict(schemaVersion=1,sourceProfile='cocos-3.8.7-bundle',inputs=[dict(id='source',path=str(config.parent))]))
            with self.assertRaisesRegex(ParseError,'VERSION_EVIDENCE_REQUIRED'):convert_package(None,'both',root/'bad',input_set_path=declaration)

    def test_cocos3_redirect_dependency_decimal_string_is_bounded_not_treated_as_bundle_name(self):
        from monkey.sources.bundle import Bundle
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();config=fixture38(root/'source');c=load(read(config));c.update(deps=['internal'],redirect=[0,'0']);write_json(config,c)
            self.assertEqual(Bundle(config,'cocos-3.8.7-bundle').redirects,{0:'internal'})
            for value in ['00','internal','-1','1']:
                c['redirect']=[0,value];write_json(config,c)
                with self.assertRaises(ParseError):Bundle(config,'cocos-3.8.7-bundle')
            c['redirect']=[];c['uuids'].append('01eec59a1');c['versions']['import']+=[len(c['uuids'])-1,'newver'];write_json(config,c)
            self.assertEqual(Bundle(config,'cocos-3.8.7-bundle').version('import',None,'01eec59a1'),'newver')

    def test_shared_asset_pack_variants_require_equal_decoded_source_not_first_match(self):
        from monkey.sources.bundle import Bundle
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();config=fixture38(root/'source');c=load(read(config));c['packs']['otherpack']=[1];c['versions']['import']+=['otherpack','b'];write_json(config,c)
            bundle=Bundle(config,'cocos-3.8.7-bundle');self.assertEqual(len(bundle.asset(1)['equivalentPackSources']),1)
            other=config.parent/'import/ot/otherpack.b.json';other.parent.mkdir()
            write_json(other,dict(type='cc.Texture2D',data=[['2,2,0,0,0,0',[TEXTURE]]]))
            bundle=Bundle(config,'cocos-3.8.7-bundle');self.assertEqual(len(bundle.asset(1)['equivalentPackSources']),2)
            write_json(other,dict(type='cc.Texture2D',data=[['1,1,0,0,0,0',[TEXTURE]]]))
            with self.assertRaisesRegex(ParseError,'AMBIGUOUS_PACK_CONTENTS'):Bundle(config,'cocos-3.8.7-bundle').asset(1)


if __name__=='__main__':unittest.main()
