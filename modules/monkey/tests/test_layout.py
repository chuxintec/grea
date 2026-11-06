import unittest
from monkey.layout import casing
from monkey.layout.allocate import LayoutPlanner
from monkey.layout.overrides import validate
from monkey.layout.verify import scan
from monkey.sources.compiled import ParseError

DEMO_ASSETS={
    'bundleA:item':dict(bundle='bundleA',logicalPath='Texture/Element/ItemSet/7001'),
    'bundleB:theme':dict(bundle='bundleB',logicalPath='Audio/BGM/theme_Intro'),
    'bundleB:effect':dict(bundle='bundleB',logicalPath='Audio/Merge/sfx_PlaceItem'),
    'zh-tw:label':dict(bundle='zh-tw',logicalPath='Config/label'),
    'zh:label':dict(bundle='zh',logicalPath='Config/label'),
    'bundleA:decor':dict(bundle='bundleA',logicalPath='Prefab/House/Decor/Room2/7100'),
    'bundleC:level':dict(bundle='bundleC',logicalPath='Texture/Grid/Resources/Levels/level_2'),
    'bundleB:clip':dict(bundle='bundleB',logicalPath='Anim/Avatar/PlayerGroup/appear4'),
    'main:scene':dict(bundle='main',logicalPath='main'),
    'main:test':dict(bundle='main',logicalPath='sample_room_test'),
    'resources:button':dict(bundle='resources',logicalPath='textures/ui/button_confirm/spriteFrame'),
    'resources:music':dict(bundle='resources',logicalPath='music/UI/55'),
    'bundleB:cfg':dict(bundle='bundleB',logicalPath='Config/AudioConfig'),
}


class CasingTests(unittest.TestCase):
    def test_pinyin_is_phrase_aware_and_keeps_file_extensions(self):
        self.assertEqual(casing.pascal('重庆银行'),'ChongQingYinHang')
        self.assertEqual(casing.snake('UI奖励板-1'),'ui_jiang_li_ban_1')
        self.assertEqual(casing.safe_path('地图/木板.png'),'DiTu/MuBan.png')
        self.assertEqual(casing.snake('女'),'nv')
        self.assertFalse(casing.HAN.search(casing.pascal('鹅'*200)))

    def test_words_keep_letter_digit_runs_and_split_case_changes(self):
        self.assertEqual(casing.words('SpArea01'),['Sp','Area01'])
        self.assertEqual(casing.words('UIPanel'),['UI','Panel'])
        self.assertEqual(casing.words('Room7Door'),['Room7','Door'])
        self.assertEqual(casing.words('鹅图标'),['E','Tu','Biao'])

    def test_three_casings(self):
        self.assertEqual((casing.pascal('Item_3'),casing.kebab('Item_3'),casing.snake('Item_3')),('Item3','item3','item_3'))
        self.assertEqual(casing.snake('CookGo'),'cook_go')
        self.assertEqual(casing.pascal('ui_main'),'UIMain')
        self.assertEqual(casing.kebab('img_box_23_1'),'img-box23-1')
        self.assertEqual(casing.pascal('700100'),'700100')

    def test_unsafe_device_and_long_names(self):
        self.assertEqual(casing.pascal('CON'),'CON_')
        self.assertNotIn('/',casing.snake('a/b'))
        long=casing.snake('x'*200)
        self.assertLessEqual(len(long.encode()),casing.SEGMENT_BYTES)
        self.assertNotEqual(long,casing.snake('x'*199))


class PlannerTests(unittest.TestCase):
    def test_homophones_keep_distinct_stable_identities(self):
        metadata={sid:dict(bundle='main',logicalPath='UI/'+name) for sid,name in [('a','工'),('b','公')]}
        mappings=[]
        for order in (['a','b'],['b','a']):
            planner=LayoutPlanner('unity',metadata)
            planner.reserve([(sid,'sprite','.png','',None,None) for sid in order])
            mappings.append({sid:planner.path(sid,'sprite','.png') for sid in order})
        self.assertEqual(mappings[0],mappings[1]);self.assertEqual(len(set(mappings[0].values())),2)

    def test_packaging_type_words_and_variants_leave_production_paths(self):
        p=LayoutPlanner('unity',DEMO_ASSETS)
        self.assertEqual(p.path('bundleA:item','sprite','.png'),'Assets/Game/Content/Textures/Element/ItemSet/7001.png')
        self.assertEqual(p.path('bundleA:item@original','sprite','.png'),'Assets/Game/Content/Textures/Element/ItemSet/7001_untrimmed.png')
        self.assertEqual(p.path('bundleA:decor','prefab','.prefab'),'Assets/Game/Content/Prefabs/House/Decor/Room2/7100.prefab')
        self.assertEqual(p.path('bundleB:clip','animation','.anim'),'Assets/Game/Content/Animations/Avatar/PlayerGroup/appear4.anim')
        self.assertEqual(p.path('resources:button','sprite','.png'),'Assets/Game/Content/Textures/UI/button_confirm.png')

    def test_audio_is_never_an_image_and_is_split_by_category(self):
        p=LayoutPlanner('unity',DEMO_ASSETS)
        self.assertEqual(p.path('bundleB:theme','native','.mp3'),'Assets/Game/Content/Audio/Music/Common/theme_intro.mp3')
        self.assertEqual(p.path('bundleB:effect','cc.AudioClip','.mp3'),'Assets/Game/Content/Audio/Sfx/Merge/sfx_place_item.mp3')
        self.assertEqual(p.path('resources:music','native','.mp3'),'Assets/Game/Content/Audio/Sfx/UI/55.mp3')

    def test_locale_bundles_become_localization_and_configs_become_tables(self):
        p=LayoutPlanner('unity',DEMO_ASSETS)
        self.assertEqual(p.path('zh-tw:label','cc.JsonAsset','.json'),'Assets/Game/Content/Strings/ZhHant/Label.json')
        self.assertEqual(p.path('zh:label','cc.JsonAsset','.json'),'Assets/Game/Content/Strings/ZhHans/Label.json')
        self.assertEqual(p.path('bundleB:cfg','cc.JsonAsset','.json'),'Assets/Game/Content/Config/Common/AudioTable.json')
        self.assertEqual(p.path('bundleC:level','cc.JsonAsset','.json'),'Assets/Game/Content/Config/Grid/Resources/Levels/Level2.json')

    def test_scenes_and_unknown_sources(self):
        p=LayoutPlanner('unity',DEMO_ASSETS)
        self.assertEqual(p.path('main:scene','scene',''),'Assets/Game/Content/Scenes/Common/Main.unity')
        self.assertEqual(p.path('main:test','scene',''),'Assets/Game/Content/Scenes/Tests/SampleRoomTest.unity')
        hashed=p.path('x:1','native','.png',metadata=dict(bundle='x',logicalPath='native/ab/abcd.png',nameProvenance='input-relative-path'))
        self.assertTrue(hashed.startswith('Assets/Game/Content/Textures/Unsorted/texture_'))
        unsafe=p.path('x:2','native','.png',metadata=dict(bundle='x',logicalPath='../escape'))
        self.assertIn('/Unsorted/',unsafe);self.assertNotIn('..',unsafe)

    def test_creator_uses_pascalcase_folders_and_same_modules(self):
        p=LayoutPlanner('creator',DEMO_ASSETS)
        self.assertEqual(p.path('bundleA:item','sprite','.png'),'assets/resources/Textures/Element/ItemSet/7001.png')
        self.assertEqual(p.path('bundleB:clip','animation','.anim'),'assets/resources/Animations/Avatar/PlayerGroup/appear4.anim')
        self.assertEqual(p.path('zh-tw:label','cc.JsonAsset','.json'),'assets/resources/Strings/ZhHant/Label.json')
        self.assertEqual(p.folder('skeleton:x',metadata=dict(bundle='skeletonAsset',logicalPath='SpineSample/House/Room9/r9_lamp1')),'assets/resources/Spine/SpineSample/House/Room9/R9Lamp1')

    def test_collision_winner_is_independent_of_request_order(self):
        meta={'b:2':dict(bundle='resources',logicalPath='UI/Icon'),'a:1':dict(bundle='resources',logicalPath='ui/icon'),'c:3':dict(bundle='resources',logicalPath='Ui/ICON')}
        requests=[(sid,'sprite','.png','',None,None) for sid in meta]
        first=LayoutPlanner('unity',meta);first.reserve(requests)
        second=LayoutPlanner('unity',meta);second.reserve(list(reversed(requests)))
        mapping=lambda p:{sid:p.path(sid,'sprite','.png') for sid in meta}
        self.assertEqual(mapping(first),mapping(second))
        self.assertEqual(mapping(first)['a:1'],'Assets/Game/Content/Textures/UI/icon.png')
        self.assertEqual(len({v.casefold() for v in mapping(first).values()}),3)
        self.assertEqual(first.report()['collisionPaths'],2)

    def test_hash_names_are_not_names_and_shared_clips_use_owner_qualifiers(self):
        p=LayoutPlanner('unity',{'m:1':dict(bundle='miniGameRes',logicalPath='Texture/cattle/Map/3942396cc7b0fad2b18e8909565e25fe'),
                                 'm:2':dict(bundle='miniGameRes',logicalPath='Texture/cattle/Map/0b44e06ac5a2a0899058be7d60c34733ba9f_zp1z_nk')})
        self.assertRegex(p.path('m:1','sprite','.png'),r'^Assets/Game/Content/Textures/MiniGames/Cattle/Map/sprite_[0-9a-f]{6}\.png$')
        self.assertEqual(p.path('m:2','sprite','.png'),'Assets/Game/Content/Textures/MiniGames/Cattle/Map/zp1z_nk.png')
        clip=dict(bundle='gameAsset',logicalPath='Anim/Badge/appear')
        q=LayoutPlanner('unity');q.reserve([('c@a','animation','.anim','',clip,'BadgeItem_icon'),('c@b','animation','.anim','',clip,'ShopBadge_icon')])
        self.assertEqual({q.path('c@a','animation','.anim'),q.path('c@b','animation','.anim')},
                         {'Assets/Game/Content/Animations/Badge/appear.anim','Assets/Game/Content/Animations/Badge/appear_shop_badge_icon.anim'})

    def test_case_variant_folders_merge_into_one_spelling(self):
        p=LayoutPlanner('unity',{'a:1':dict(bundle='a',logicalPath='floorAndWall/x'),'a:2':dict(bundle='a',logicalPath='FloorAndWall/y')})
        one,two=p.path('a:1','sprite','.png'),p.path('a:2','sprite','.png')
        self.assertEqual(one.rsplit('/',1)[0],two.rsplit('/',1)[0])

    def test_existing_claims_from_another_stage_are_not_reused(self):
        p=LayoutPlanner('unity',DEMO_ASSETS);p.claim('Assets/Game/Content/Audio/Music/Common/theme_intro.mp3')
        self.assertNotEqual(p.path('bundleB:theme','native','.mp3'),'Assets/Game/Content/Audio/Music/Common/theme_intro.mp3')

    def test_layout_overrides_change_paths_only(self):
        overrides=validate(dict(schemaVersion=1,modules=[dict(match='uiraw/icon_*',module='Icons/{1}')],renames={'u:1':'street_sweeper'},
                               bundles={'events':dict(role='minigame')}))
        p=LayoutPlanner('unity',{'u:1':dict(bundle='game',logicalPath='uiraw/icon_item/a2_saodiji3'),
                                 'u:2':dict(bundle='events',logicalPath='Texture/Disco/bg')},overrides)
        self.assertEqual(p.path('u:1','sprite','.png'),'Assets/Game/Content/Textures/Icons/Item/street_sweeper.png')
        self.assertEqual(p.path('u:2','sprite','.png'),'Assets/Game/Content/Textures/MiniGames/Disco/Common/bg.png')

    def test_invalid_overrides_are_rejected(self):
        for bad in [dict(schemaVersion=2),dict(schemaVersion=1,extra=1),dict(schemaVersion=1,modules=[dict(match='../x',module='Y')]),
                    dict(schemaVersion=1,modules=[dict(match='a/*',module='{2}')]),dict(schemaVersion=1,renames={'a':'x/y'}),
                    dict(schemaVersion=1,rootNamespace='lower.case'),dict(schemaVersion=1,code={'A':dict(layer='Runtime')})]:
            with self.assertRaises(ParseError):validate(bad)


class ForbiddenNameTests(unittest.TestCase):
    def test_legacy_layout_is_caught_and_canonical_layout_passes(self):
        legacy=['Assets/Game/Content/Images/Sprites/bundleA/Texture/Element/Item_3/700100.original.png',
                'Assets/Game/Content/Materials/002aba30c8bc53ce83ca705ea6b1b7fb.mat',
                'Assets/Game/Content/Config/Recovered/zh-tw/Config/label.json',
                'Assets/Generated/Views/Candidate.prefab','Assets/Texture2D/6.png','Assets/uiraw/battle/a.asset',
                'assets/art/images/Original/main/a.png']
        self.assertEqual(len({d['location'] for d in scan(legacy)}),len(legacy))
        p=LayoutPlanner('unity',DEMO_ASSETS)
        clean=[p.path(sid,kind,suffix) for sid,kind,suffix in [('bundleA:item','sprite','.png'),('zh-tw:label','cc.JsonAsset','.json'),
               ('bundleB:theme','native','.mp3'),('main:scene','scene',''),('bundleA:decor','prefab','.prefab')]]
        clean+=['Assets/Game/Editor/Conversion/MonkeyImporter.cs','Assets/TextMesh Pro/Shaders/TMP_SDF.shader']
        self.assertEqual(scan(clean),[])

    def test_class_prefix_check_reads_code(self):
        path='Assets/Game/Presentation/Shop/ShopView.cs'
        self.assertTrue(scan([path],{path:'namespace Recovered.Gameplay { public class ShopView {} }'}))
        self.assertFalse(scan([path],{path:'namespace Demo.Presentation.Shop { public class ShopView {} }'}))


if __name__=='__main__':
    unittest.main()
