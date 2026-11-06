import tempfile
import shutil
from pathlib import Path
import unittest
from unittest.mock import patch
from PIL import Image

from monkey.io import write_json,sha
from monkey.providers.assetripper import fingerprint
from monkey.sources.compiled import ParseError
from monkey.unity_native import plan,SourceObjects,finish_conversion


def ptr(path, file='0'):return {'$type':'UnityPPtr','fileId':file,'pathId':path}


def fixture(root):
    def emit(path,content):
        p=root/path;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(content) if isinstance(content,str) else write_json(p,content)
    def obj(path,type,data,name=None):
        return dict(file='0',pathId=path,type=type,data=data,name=name,status='parsed',typeTreeSource='embedded')
    root.mkdir()
    script='Assets/Scripts/Game/Pool.cs'
    emit(script,'public class Pool : UnityEngine.MonoBehaviour { public UnityEngine.Sprite[] Items; }')
    h=fingerprint(root/script)
    emit('Assets/Scripts/Game/Game.asmdef',{'name':'Game'})
    emit('Assets/Pool.prefab','--- !u!1 &1\nGameObject:\n  m_Name: Pool\n  m_Script: {fileID: 11500000, guid: '+('1'*32)+', type: 3}\n')
    emit('Assets/Sprites/hero.asset','--- !u!213 &21300000\nSprite:\n  m_Name: hero\n')
    png=root/'Assets/Textures/atlas.png';png.parent.mkdir();im=Image.new('RGBA',(8,8),(13,47,86,255));im.putpixel((0,0),(255,0,0,255));im.save(png)
    for i,path in enumerate([script,'Assets/Scripts/Game/Game.asmdef','Assets/Pool.prefab','Assets/Sprites/hero.asset','Assets/Textures/atlas.png'],1):
        emit(path+'.meta','fileFormatVersion: 2\nguid: '+str(i)*32+'\nNativeFormatImporter:\n  assetBundleName: \n')
    emit('Packages/manifest.json',{'dependencies':{'com.unity.modules.imageconversion':'1.0.0'}})
    instance=dict(file='0',pathId='3')
    model=dict(classes=[dict(assembly='Game.dll',namespace='',name='Pool',targetSha256=h,sourceScript={'file':'0','pathId':'4'},fields=[dict(name='Items',csName='Items',csType='UnityEngine.Sprite[]')],instances=[instance])])
    emit('Analysis/Code/unity-code-model.json',model)
    emit('Analysis/Code/unity-code-quarantine.json',{'schemaApplied':[dict(path=script,sha256=h)]})
    emit('Analysis/Evidence/unity-typed-objects.json',dict(files=[dict(id='0',name='CAB-main',externals=[dict(fileId='1',path='archive:/CAB-dep/CAB-dep')])],objects=[
        obj('1','GameObject',{'m_Component':[{'component':ptr('2')},{'component':ptr('3')}],'m_Name':'Pool','m_IsActive':True}),
        obj('2','Transform',dict(m_GameObject=ptr('1'),m_Father=ptr('0'),m_Children=[],m_LocalPosition=dict(x=0,y=0,z=0),m_LocalScale=dict(x=1,y=1,z=1),m_LocalRotation=dict(x=0,y=0,z=0,w=1))),
        obj('3','MonoBehaviour',dict(m_GameObject=ptr('1'),Items=[ptr('5','1')])),obj('4','MonoScript',{}),obj('9','AssetBundle',{})]))
    rd=dict(texture=ptr('7'),textureRect=dict(x=0,y=0,width=8,height=8),settingsRaw=67,downscaleMultiplier=1,alphaTexture=ptr('0'),secondaryTextures=[])
    emit('Analysis/Evidence/dependency-typed-0.json',dict(files=[dict(id='0',name='CAB-dep',externals=[])],objects=[obj('5','Sprite',dict(m_SpriteAtlas=ptr('6'),m_RenderDataKey=[1,2]),'hero'),
        obj('6','SpriteAtlas',dict(m_IsVariant=False,m_RenderDataMap=[[[1,2],rd]]),'collection'),obj('7','Texture2D',dict(m_Width=8,m_Height=8),'atlas')]))
    emit('Analysis/Readback/texture-hydration.json',dict(consumed=[dict(file='CAB-dep',pathId='7',normalization='BGRA-to-RGBA-no-flip-v1',rgbaRawSha256=sha(bytes([13,47,86,255])*56+bytes([255,0,0,255])+bytes([13,47,86,255])*7))]))
    seal(root)
    return root


def seal(root):
    write_json(root/'recovery-manifest.json',dict(targetVersion='6000.6.2f1',validation={'editor':'not_run'},files=[dict(path=p.relative_to(root).as_posix(),bytes=p.stat().st_size,sha256=fingerprint(p))for p in sorted(root.rglob('*'))if p.is_file()and p.name!='recovery-manifest.json']))


class UnityNativeTests(unittest.TestCase):
    def test_relocated_native_asset_uses_exact_source_mapping_and_guid(self):
        with tempfile.TemporaryDirectory() as t:
            root=fixture(Path(t).resolve()/'candidate')
            old='Assets/Sprites/hero.asset';new='Assets/Sprites/renamed_sprite.asset'
            (root/old).rename(root/new);(root/(old+'.meta')).rename(root/(new+'.meta'))
            write_json(root/'Analysis/Mappings/unity-relocation.json',dict(moves=[dict(source=old,target=new,guid='4'*32)]));seal(root)
            self.assertEqual(plan(root)['spec']['expectedSprites'][0]['guid'],'4'*32)
            mapping=root/'Analysis/Mappings/unity-relocation.json'
            write_json(mapping,dict(moves=[dict(source=old,target=new,guid='6'*32)]));seal(root)
            with self.assertRaisesRegex(ParseError,'identity differs'):plan(root)

    def test_exact_source_reference_preserves_names_and_guid_and_grea_alias_moves_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            root=fixture(Path(t).resolve()/'candidate');p=plan(root,'grea');s=p['spec']
            self.assertEqual(s['expectedArrayLengths'],[1]);self.assertEqual(s['expectedSprites'][0]['fileId'],'21300000')
            # Relocation into monkey-project/1 happens at conversion; the native proof never moves assets.
            self.assertEqual(s['formatMoves'],[])
            self.assertEqual(s['expectedSprites'][0]['textureGuid'],'5'*32)
            self.assertEqual(len(p['nativeIdentitySeals']),5)

    def test_missing_external_and_name_collisions_reject_before_editor(self):
        with tempfile.TemporaryDirectory() as t:
            root=fixture(Path(t).resolve()/'candidate');path=root/'Analysis/Evidence/dependency-typed-0.json'
            from monkey.unity_native import document
            d=document(path);d['files'][0]['name']='CAB-dep-near';write_json(path,d);seal(root)
            with self.assertRaisesRegex(ParseError,'dependency missing'):plan(root)
            d['files'][0]['name']='CAB-dep';d['objects'].append(dict(d['objects'][0],pathId='15'));write_json(path,d);seal(root)
            with self.assertRaisesRegex(ParseError,'Ambiguous source resource name'):plan(root)

    def test_unknown_code_modified_pixels_and_null_slots_are_not_filled(self):
        with tempfile.TemporaryDirectory() as t:
            root=fixture(Path(t).resolve()/'candidate');evil=root/'Assets/unknown.cs';evil.write_text('unknown');seal(root)
            with self.assertRaisesRegex(ParseError,'Unknown executable'):plan(root)
            evil.unlink();png=root/'Assets/Textures/atlas.png';Image.new('RGBA',(8,8),'red').save(png);seal(root)
            with self.assertRaisesRegex(ParseError,'pixels differ'):plan(root)
        with tempfile.TemporaryDirectory() as t:
            root=fixture(Path(t).resolve()/'candidate');from monkey.unity_native import document
            path=root/'Analysis/Evidence/unity-typed-objects.json';d=document(path);d['objects'][2]['data']['Items']=[ptr('0')];write_json(path,d);seal(root)
            with self.assertRaisesRegex(ParseError,'Null or missing'):plan(root)

    def test_bundle_loading_identity_is_pinned_and_manual_changes_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=fixture(Path(t).resolve()/'candidate');meta=root/'Assets/Sprites/hero.asset.meta';meta.write_text(meta.read_text().replace('assetBundleName: ','assetBundleName: original.ab'));seal(root)
            p=plan(root,'grea');self.assertEqual(p['spec']['formatMoves'],[]);self.assertEqual(len(p['pinned']),1)
            (root/'Assets/Pool.prefab').write_text('modified')
            with self.assertRaisesRegex(ParseError,'Owned file changed'):plan(root)

    def test_unsupported_native_scope_retains_successful_base_conversion(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();(root/'UnityProject').mkdir()
            conversion=dict(completed=True,validation=dict(editor='not_run'),format=dict(profile='none',applied=False))
            settings=dict(candidate=root,output=root/'native',editors={'unity-6000.6.2f1-ugui':root/'Unity'},budget=1200)
            with patch('monkey.unity_native.execute',side_effect=ParseError('UNSUPPORTED','$','multiple classes')):
                result=finish_conversion(conversion,settings,'grea')
            self.assertTrue(result['completed']);self.assertEqual(result['nativeExecution']['status'],'blocked');self.assertFalse((root/'native').exists())
            self.assertEqual(result['format']['status'],'retired')


if __name__=='__main__':unittest.main()
