import tempfile,unittest
from pathlib import Path
from fixtures import FRAME,TEXTURE,normal
from test_cocos38 import fixture38
from monkey.io import read,load,write_json
from monkey.package import convert_package
from monkey.sources.cocos34 import texture,image_formats
from monkey.sources.compiled import ParseError
from monkey.sources.bundle import Bundle
from monkey.sources.cocos34_graphs import graph


def fixture34(root):
    config=fixture38(root);c=load(read(config));c['engineVersion']='3.4.1';c['packs']['texpack']=['1'];write_json(config,c)
    write_json(root/'settings.test.json',dict(CocosEngine='3.4.1'))
    sf=root/'import'/FRAME[:2]/(FRAME+'@f9941.a.json');d=load(read(sf))
    for k in ('pivot','meshType','pixelsToUnit'):d[5][0].pop(k)
    write_json(sf,d)
    write_json(root/'import/te/texpack.a.json',dict(type='cc.Texture2D',data=[dict(base='2,2,0,0,0,0',mipmaps=[TEXTURE])]))
    return config


class Graph341LifecycleTests(unittest.TestCase):
    def test_disabled_ui_transform_keeps_geometry_and_explicit_lifecycle_state(self):
        a=dict(sourceId='main:disabled',document=dict(root=0,instances=[dict(__type__='cc.Node',_components=[dict(__type__='cc.UITransform',node={'__id__':0},_enabled=False,_contentSize=dict(width=173,height=61),_anchorPoint=dict(x=.2,y=.7))])]))
        ns,_,_=graph(a);self.assertEqual(ns[0]['size'],[173,61]);self.assertEqual(ns[0]['anchor'],[.2,.7]);self.assertIs(ns[0]['sourceUITransformEnabled'],False)


class Creator34Tests(unittest.TestCase):
    def test_named_font_config_is_parsed_with_original_glyph_metrics(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();config=fixture34(root/'source');c=load(read(config));font='55555555-5555-5555-5555-555555555555';index=len(c['uuids']);c['uuids'].append(font);c['types'].append('cc.BitmapFont');c['paths'][str(index)]=['font',len(c['types'])-1];c['versions']['import'] += [index,'a'];write_json(config,c)
            p=config.parent/'import'/font[:2]/(font+'.a.json');p.parent.mkdir(parents=True,exist_ok=True)
            write_json(p,normal([dict(__type__='cc.BitmapFont',fontSize=10,spriteFrame={'__uuid__':FRAME+'@f9941'},fntConfig=dict(fontSize=10,commonHeight=12,fontDefDictionary={'65':dict(rect=dict(x=0,y=0,width=1,height=1),xOffset=0,yOffset=1,xAdvance=2)},kerningDict={}))]))
            report=convert_package(config.parent,'both',root/'out');self.assertNotEqual(report['structuredRecovery']['status'],'failed',report['structuredRecovery'])
            ir=load(read(root/'out/Structured/normalize/ir.json'));self.assertEqual(len(ir['bitmapFonts']),1);value=ir['bitmapFonts'][0]
            self.assertEqual(value['pointSize'],10);self.assertEqual(value['glyphs'][0]['metrics'],[1,1,0,9,2]);self.assertEqual(value['kerningConvention'],'source-3.4.1-unscaled-pair-offset')

    def test_public_both_targets_keep_version_specific_resources_and_audited_graph_defaults(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();config=fixture34(root/'source');report=convert_package(config.parent,'both',root/'out')
            self.assertTrue(report['completed']);self.assertNotEqual(report['structuredRecovery']['status'],'failed',report['structuredRecovery'])
            ir=load(read(root/'out/Structured/normalize/ir.json'))
            self.assertEqual(ir['sourceProfile'],'cocos-3.4.1-bundle');self.assertEqual(len(ir['spriteFrames']),1);self.assertEqual(len(ir['nodes']),1)
            self.assertEqual(ir['nodes'][0]['sourceGeometryProfile'],'cocos-3.4.1-node-ui-v1');self.assertEqual(ir['nodes'][0]['position'],[17,23,4]);self.assertEqual(ir['nodes'][0]['scale'],[1,1,1])
            self.assertEqual(ir['spriteFrames'][0]['textureRef'],'main:'+TEXTURE)
            self.assertEqual(ir['spriteFrames'][0]['sourceResourceEvidence']['resourceProfile'],'cocos-3.4.1-bundle')
            self.assertEqual(load(read(root/'out/Structured/inspect/source-manifest.json'))['sourceVersion'],'3.4.1')
            for target in ('UnityProject','CocosProject'):self.assertTrue((root/'out'/target/'manifest.json').is_file())

    def test_settings_proof_is_required_and_later_profile_is_not_accepted(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();config=fixture34(root/'source');declaration=root/'inputs.json'
            write_json(declaration,dict(schemaVersion=1,sourceProfile='cocos-3.4.1-bundle',inputs=[dict(id='source',path=str(config.parent))]))
            (config.parent/'settings.test.json').unlink()
            with self.assertRaisesRegex(ParseError,'COCOS3_VERSION_EVIDENCE_REQUIRED'):convert_package(None,'both',root/'missing-proof',input_set_path=declaration)
            write_json(config.parent/'settings.test.json',dict(CocosEngine='3.8.7'))
            with self.assertRaisesRegex(ParseError,'COCOS3_VERSION_EVIDENCE_REQUIRED'):convert_package(None,'both',root/'wrong-proof',input_set_path=declaration)

    def test_mipmap_and_later_positional_layouts_are_not_silently_collapsed(self):
        self.assertEqual(texture(dict(base='2,2,0,0,0,0',mipmaps=[TEXTURE]),'test')[1],TEXTURE)
        for value in [dict(base='2,2,0,0,0,0',mipmaps=[TEXTURE,FRAME]),['2,2,0,0,0,0',[TEXTURE]],dict(base='bad',mipmaps=[TEXTURE])]:
            with self.assertRaises(ParseError):texture(value,'test')

    def test_pack_envelope_identity_is_not_decoded_as_an_extra_source_object(self):
        with tempfile.TemporaryDirectory()as temp:
            config=fixture34(Path(temp).resolve()/'source');data=load(read(config));data['uuids'].append('texpack');write_json(config,data)
            row=Bundle(config,'cocos-3.4.1-bundle').asset(len(data['uuids'])-1)
            self.assertEqual(row['kind'],'source-pack-container');self.assertIsNone(row['document'])

    def test_public_input_set_joins_acquired_resources_without_copying_into_original_root(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();config=fixture34(root/'source');image=root/'source/native'/TEXTURE[:2]/(TEXTURE+'.b.png')
            moved=root/'remote/main/native'/TEXTURE[:2]/image.name;moved.parent.mkdir(parents=True);image.rename(moved)
            declaration=root/'inputs.json';write_json(declaration,dict(schemaVersion=1,sourceProfile='cocos-3.4.1-bundle',inputs=[dict(id='source',path=str(config.parent)),dict(id='remote',path=str(root/'remote'))]))
            report=convert_package(None,'both',root/'out',input_set_path=declaration)
            self.assertNotEqual(report['structuredRecovery']['status'],'failed',report['structuredRecovery'])
            ir=load(read(root/'out/Structured/normalize/ir.json'));self.assertEqual(len(ir['spriteFrames']),1);self.assertFalse(image.exists())
            objects=load(read(root/'out/UnityProject/Analysis/Evidence/structured-objects.json'))['objects'];source=next(a for a in objects if a['sourceId']=='main:'+TEXTURE)
            self.assertTrue(any('remote/main/native/'in x for x in source['sourceInputs']))
            self.assertFalse(any(d['code']=='INVALID_BUNDLE_TABLE'for d in report['diagnostics']))

    def test_different_bytes_for_same_acquired_version_are_an_explicit_conflict(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();config=fixture34(root/'source');remote=root/'remote/main/native'/TEXTURE[:2]/(TEXTURE+'.b.png');remote.parent.mkdir(parents=True);remote.write_bytes(b'different bytes')
            bundle=Bundle(config,'cocos-3.4.1-bundle');bundle.provided_tree(root,[root/'source',root/'remote'])
            with self.assertRaisesRegex(ParseError,'CONFLICTING_PROVIDED_RESOURCE'):bundle.select('native',TEXTURE,'b','.png')

    def test_multiple_encodings_use_declared_policy_and_retain_both_locations(self):
        self.assertEqual(image_formats(dict(fmt='7@93_0'),'test'),['.astc','.png'])
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();config=fixture34(root/'source');astc=root/'source/native'/TEXTURE[:2]/(TEXTURE+'.b.astc');astc.write_bytes(b'path selection only; decoder validates bytes later')
            bundle=Bundle(config,'cocos-3.4.1-bundle');entry=dict(sourceId='main:'+TEXTURE,key=TEXTURE,kind='cc.ImageAsset',document=dict(root=0,instances=[dict(data=dict(fmt='7@93_0'))]))
            selected=bundle.native_file(entry,'b');self.assertEqual(selected.suffix,'.astc');self.assertEqual(len(entry['nativeVariantSelection']['available']),2)
