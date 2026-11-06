import tempfile,unittest
from pathlib import Path
from monkey.io import read,load
from monkey.layout.verify import scan
from monkey.unity_layout import relocate

YAML='%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!{cls} &{fid}\n{body}\n'


def put(root,relative,text,guid,texture_type=None):
    path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    meta='fileFormatVersion: 2\nguid: '+guid+'\n'+('TextureImporter:\n  textureType: '+str(texture_type)+'\n' if texture_type is not None else '')
    Path(str(path)+'.meta').write_text(meta)
    folder=path.parent
    while folder!=root/'Assets':
        Path(str(folder)+'.meta').write_text('fileFormatVersion: 2\nguid: '+'f'*32+'\nfolderAsset: yes\n');folder=folder.parent


def export(root):
    """AssetRipper-shaped provider export: type roots, container folders, Resources, Spine, scenes and scripts."""
    g=lambda c:c*32
    put(root,'Assets/Texture2D/atlas_page.png','png',g('a'),0)
    put(root,'Assets/uiraw/battle/zmzg_btn.asset',YAML.format(cls=213,fid=21300000,body='Sprite:\n  m_RD:\n    texture: {fileID: 2800000, guid: '+g('a')+', type: 3}'),g('b'))
    put(root,'Assets/effect/ui/glow.mat',YAML.format(cls=21,fid=2100000,body='Material: {}'),g('c'))
    put(root,'Assets/MonoBehaviour/hero_SkeletonData.asset',YAML.format(cls=114,fid=11400000,body='MonoBehaviour: {}'),g('d'))
    put(root,'Assets/MonoBehaviour/hero_Atlas.asset',YAML.format(cls=114,fid=11400000,body='MonoBehaviour: {}'),g('e'))
    put(root,'Assets/TextAsset/hero.skel.bytes','skel',g('1'))
    put(root,'Assets/TextAsset/hero.atlas.bytes','\nhero.png\n',g('2'))
    put(root,'Assets/Texture2D/hero.png','png',g('3'),0)
    put(root,'Assets/Resources/config/AudioCfg.bytes','table',g('4'))
    put(root,'Assets/Resources/LineBreaking Leading Characters.bytes','chars',g('5'))
    put(root,'Assets/Resources/TMP Settings.asset',YAML.format(cls=114,fid=11400000,body='MonoBehaviour:\n  m_leadingCharacters: {fileID: 4900000, guid: '+g('5')+', type: 3}'),g('6'))
    put(root,'Assets/Scenes/SceneMain.unity',YAML.format(cls=29,fid=1,body='OcclusionCullingSettings: {}'),g('7'))
    put(root,'Assets/Scenes/SceneMain/Settings.lighting',YAML.format(cls=850595691,fid=1,body='LightingSettings: {}'),g('8'))
    put(root,'Assets/Scripts/GameLogic/T5Game/Hero.cs','public class Hero {}',g('9'))
    put(root,'Assets/Plugins/Spine38/spine-unity.dll','dll',g('0'))


class UnityLayoutTests(unittest.TestCase):
    def test_provider_export_moves_to_monkey_project_with_identities(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();export(root)
            metas={p.relative_to(root).as_posix()[:-5]:p.read_text() for p in (root/'Assets').rglob('*.meta') if 'folderAsset' not in p.read_text()}
            result=relocate(root)
            moves={m['source']:m['target'] for m in load(read(root/'Analysis/Mappings/unity-relocation.json'))['moves']}
            expect={
                'Assets/Texture2D/atlas_page.png':'Assets/Game/Content/Textures/Unsorted/atlas_page.png',
                'Assets/uiraw/battle/zmzg_btn.asset':'Assets/Game/Content/Textures/Battle/zmzg_btn.asset',
                'Assets/effect/ui/glow.mat':'Assets/Game/Content/Materials/Effect/UI/glow.mat',
                'Assets/MonoBehaviour/hero_SkeletonData.asset':'Assets/Game/Content/Spine/Unsorted/Hero/hero_SkeletonData.asset',
                'Assets/TextAsset/hero.skel.bytes':'Assets/Game/Content/Spine/Unsorted/Hero/hero.skel.bytes',
                'Assets/Texture2D/hero.png':'Assets/Game/Content/Spine/Unsorted/Hero/hero.png',
                'Assets/Resources/config/AudioCfg.bytes':'SourceRecovery/Config/Resources/config/AudioCfg.bytes',
                'Assets/Resources/LineBreaking Leading Characters.bytes':'Assets/Game/Content/Data/Resources/LineBreaking Leading Characters.bytes',
                'Assets/Resources/TMP Settings.asset':'Assets/Game/Content/Data/Resources/TMP Settings.asset',
                'Assets/Scenes/SceneMain.unity':'Assets/Game/Content/Scenes/SceneMain.unity',
                'Assets/Scenes/SceneMain/Settings.lighting':'Assets/Game/Content/Scenes/SceneMain/Settings.lighting',
                'Assets/Scripts/GameLogic/T5Game/Hero.cs':'Assets/Game/Scripts/GameLogic/T5Game/Hero.cs'}
            for old,new in expect.items():self.assertEqual(moves.get(old),new,old)
            self.assertEqual(result['moved'],len(moves))
            for old,meta in metas.items():
                new=moves.get(old,old)
                self.assertEqual((root/(new+'.meta')).read_text(),meta,old)
                self.assertTrue((root/new).is_file(),new)
            self.assertTrue((root/'Assets/Plugins/Spine38/spine-unity.dll').is_file())
            for gone in ['Texture2D','MonoBehaviour','TextAsset','uiraw','effect','Scenes','Scripts','Resources']:
                self.assertFalse((root/'Assets'/gone).exists(),gone);self.assertFalse((root/'Assets'/(gone+'.meta')).exists(),gone)
            content=[p.relative_to(root).as_posix() for p in (root/'Assets').rglob('*') if p.is_file()]
            self.assertEqual(scan(content),[])

    def test_layout_overrides_rename_provider_modules(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();export(root)
            relocate(root,dict(schemaVersion=1,modules=[dict(match='uiraw/*',module='UI/{1}')]))
            moves={m['source']:m['target'] for m in load(read(root/'Analysis/Mappings/unity-relocation.json'))['moves']}
            self.assertEqual(moves['Assets/uiraw/battle/zmzg_btn.asset'],'Assets/Game/Content/Textures/UI/Battle/zmzg_btn.asset')

    def test_schema_code_receipt_follows_relocated_file_preserving_provenance(self):
        from monkey.io import write_json,sha
        from monkey.unity_layout import update_receipts
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();export(root)
            old='Assets/Scripts/GameLogic/T5Game/Hero.cs';digest=sha(read(root/old))
            receipt=root/'Analysis/Code/unity-code-quarantine.json'
            write_json(receipt,dict(providerCode=[dict(source=old,preserved='SourceRecovery/Code/Provider/'+old)],schemaApplied=[dict(path=old,sha256=digest)]))
            relocate(root)
            body=load(read(receipt));row=body['schemaApplied'][0]
            self.assertEqual(row['path'],'Assets/Game/Scripts/GameLogic/T5Game/Hero.cs')
            self.assertEqual(row['providerPath'],old)
            self.assertEqual(sha(read(root/row['path'])),row['sha256'])
            self.assertEqual(body['providerCode'][0]['source'],old)
            moves=load(read(root/'Analysis/Mappings/unity-relocation.json'))['moves']
            self.assertEqual(update_receipts(root,moves),0)


if __name__=='__main__':
    unittest.main()
