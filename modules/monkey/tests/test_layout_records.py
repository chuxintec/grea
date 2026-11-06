import contextlib,io,json,tempfile,unittest
from pathlib import Path
from fixtures import fixture
from monkey.cli import main
from monkey.io import read,load,write_json
from monkey.package import convert_package


class LayoutRecordTests(unittest.TestCase):
    def test_generated_docs_describe_layout_and_real_modules(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();convert_package(fixture(root/'source').parent,'both',root/'out')
            for name,module in [('UnityProject','UI'),('CocosProject','UI')]:
                project=root/'out'/name;structure=(project/'Docs/PROJECT-STRUCTURE.md').read_text()
                self.assertIn('monkey-project/2.0.0',structure);self.assertIn('| '+module+' |',structure)
                table=load(read(project/'Analysis/Mappings/modules.json'))['modules']
                self.assertEqual(table[module]['texture'],1)
                self.assertIn('Mappings/',(project/'Analysis/README.md').read_text())
                self.assertTrue((project/'Docs/CONTENT-INDEX.md').is_file())
            self.assertIn('UnityProject/Docs/START-HERE.md',(root/'out/README.md').read_text())

    def test_layout_preview_replays_overrides_without_writing_projects(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();convert_package(fixture(root/'source').parent,'both',root/'out')
            layout=root/'layout.json';write_json(layout,dict(schemaVersion=1,modules=[dict(match='UI',module='Panels')]))
            out=io.StringIO()
            with contextlib.redirect_stdout(out):main(['layout-preview','--conversion',str(root/'out'),'--layout',str(layout),'--out',str(root/'preview')])
            summary=json.loads(out.getvalue());self.assertGreaterEqual(summary['unity']['changed'],1)
            rows=load(read(root/'preview/layout-preview.json'))['rows']
            sprite=next(r for r in rows if r['engine']=='unity' and r['current'].endswith('/panel.png'))
            self.assertEqual(sprite['preview'],'Assets/Game/Content/Textures/Panels/panel.png')
            self.assertFalse((root/'preview/UnityProject').exists())
            unchanged=next(r for r in rows if r['engine']=='creator' and r['current'].endswith('/panel.png'))
            self.assertEqual(unchanged['preview'],'assets/resources/Textures/Panels/panel.png')

    def test_layout_migration_pairs_old_and_new_paths_by_guid(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            for name,path in [('old','Assets/Game/Content/Images/Sprites/gameAsset/Texture/UI/a.original.png'),('new','Assets/Game/Content/Textures/UI/a_untrimmed.png')]:
                file=root/name/path;file.parent.mkdir(parents=True);file.write_bytes(b'png');Path(str(file)+'.meta').write_text('fileFormatVersion: 2\nguid: '+'a'*32+'\n')
            only=root/'old/Assets/Game/Content/Removed.png';only.write_bytes(b'x');Path(str(only)+'.meta').write_text('fileFormatVersion: 2\nguid: '+'b'*32+'\n')
            out=io.StringIO()
            with contextlib.redirect_stdout(out):main(['layout-migration','--from',str(root/'old'),'--to',str(root/'new'),'--out',str(root/'migration')])
            report=load(read(root/'migration/layout-migration.json'))
            self.assertEqual(report['moves'],[dict(source='Assets/Game/Content/Images/Sprites/gameAsset/Texture/UI/a.original.png',target='Assets/Game/Content/Textures/UI/a_untrimmed.png',guid='a'*32)])
            self.assertEqual([r['guid'] for r in report['onlyInOld']],['b'*32])

    def test_duplicate_identity_refuses_ambiguous_migration(self):
        from monkey.layout.records import migration
        from monkey.sources.compiled import ParseError
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            for name in ('old','new'):
                (root/name/'Assets').mkdir(parents=True)
            for name in ('a','b'):
                (root/'new/Assets'/f'{name}.png.meta').write_text('guid: '+'a'*32+'\n')
            with self.assertRaisesRegex(ParseError,'LAYOUT_DUPLICATE_IDENTITY'):
                migration(root/'old',root/'new',root/'result')
            self.assertFalse((root/'result').exists())

    def test_creator_folders_are_excluded_and_added_assets_listed(self):
        from monkey.layout.records import migration
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            for name in ('old','new'):
                assets=root/name/'assets';assets.mkdir(parents=True)
                write_json(assets/'art.meta',dict(uuid='a'*8+'-aaaa-aaaa-aaaa-'+'a'*12,importer='directory'))
            guid='b'*8+'-bbbb-bbbb-bbbb-'+'b'*12
            write_json(root/'new/assets/new.png.meta',dict(uuid=guid,importer='image'))
            migration(root/'old',root/'new',root/'result')
            report=load(read(root/'result/layout-migration.json'))
            self.assertEqual(report['unchanged'],0)
            self.assertEqual(report['addedAssets'],[dict(path='assets/new.png',guid=guid)])

    def test_preview_includes_generated_fonts_and_shared_animation_collisions(self):
        from monkey.layout.allocate import LayoutPlanner
        from monkey.layout.records import preview
        from monkey.io import finish
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();conversion=root/'conversion'
            names={'font':dict(bundle='main',logicalPath='UI/Title.ttf')}
            planner=LayoutPlanner('unity',names)
            owner=dict(bundle='main',logicalPath='Anim/Badge/appear')
            planner.reserve([('clip@a','animation','.anim','',owner,'One'),('clip@b','animation','.anim','',owner,'Two'),
                             ('font','font-asset','.asset','',None,None)])
            controller=planner.path('button','controller','.controller',metadata=dict(bundle='main',logicalPath='Anim/Badge/StartButton'))
            for state in ['normal','pressed']:planner.derived_path('button@'+state,controller,'_'+state,'.anim')
            ir=conversion/'Structured/normalize';ir.mkdir(parents=True)
            write_json(ir/'ir.json',dict(sourceNames=names));finish(ir,{})
            plan=conversion/'Structured/UnityProject-plan';plan.mkdir()
            write_json(plan/'plan.json',dict(naming=planner.report()));finish(plan,{})
            result=preview(conversion,root/'preview')
            self.assertEqual(result['unity']['objects'],6)
            self.assertEqual(result['unity']['changed'],0)
            rows=load(read(root/'preview/layout-preview.json'))['rows']
            self.assertEqual({r['kind'] for r in rows},{'animation','font-asset','controller'})
            self.assertTrue(any(r['preview'].endswith('appear_two.anim') for r in rows))
            result=preview(conversion,root/'renamed',dict(modules=[dict(match='Anim/Badge',module='Medals')]))
            self.assertEqual(result['unity']['changed'],5)
            changed=load(read(root/'renamed/layout-preview.json'))['rows']
            self.assertTrue(all('/Medals/' in row['preview'] for row in changed if row['sourceId'].startswith('button')))

    def test_preview_rejects_empty_conversion_without_success_receipt(self):
        from monkey.layout.records import preview
        from monkey.sources.compiled import ParseError
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();(root/'empty').mkdir()
            with self.assertRaisesRegex(ParseError,'LAYOUT_PREVIEW_UNSUPPORTED'):
                preview(root/'empty',root/'preview')
            self.assertFalse((root/'preview').exists())


if __name__=='__main__':
    unittest.main()
