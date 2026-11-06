import json
import tempfile
import unittest
from pathlib import Path
from collections import Counter
from fixtures import fixture, normal, FRAME,TEXTURE,PREFAB,FONT
from monkey.io import load,read,write_json,sha
from monkey.package import convert_package
from monkey.inputs import input_set
from monkey.sources.compiled import ParseError

JSON_ID='00000000-0000-0000-0000-000000000020'


class StructuredTests(unittest.TestCase):
    def test_multi_root_shared_ir_json_payload_and_standard_native_plans(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();main=fixture(root/'main');external=root/'external';external.mkdir()
            original=load(read(main));original['uuids']=[FRAME,PREFAB,FONT,JSON_ID]
            original['paths']={'0':['UI/panel',0],'1':['UI/fixture',1],'3':['data/test',2]}
            original['types'].append('cc.JsonAsset');original['versions']={'import':[0,'a',1,'a',2,'a',3,'a'],'native':[]}
            write_json(main,original)
            for folder,version,suffix in [('import','a','.json'),('native','b','.png')]:
                old=main.parent/folder/TEXTURE[:2]/(TEXTURE+'.'+version+suffix)
                new=external/folder/TEXTURE[:2]/old.name;new.parent.mkdir(parents=True);new.write_bytes(old.read_bytes());old.unlink()
            write_json(external/'config.json',dict(name='textures',engineVersion='2.4.15',uuids=[TEXTURE],paths={},types=[],packs={},
                    versions=dict(import_=[])))
            c=load(read(external/'config.json'));c['versions']={'import':[0,'a'],'native':[0,'b']};write_json(external/'config.json',c)
            payload={'path':'/keep-original','name':'Assets/Generated/Art/source','value':12,'items':[1,2]}
            p=main.parent/'import'/JSON_ID[:2]/(JSON_ID+'.a.json');p.parent.mkdir(exist_ok=True)
            write_json(p,normal([dict(__type__='cc.JsonAsset',json=payload)]))
            declaration=root/'inputs.json'
            write_json(declaration,dict(schemaVersion=1,sourceProfile='cocos-2.4.15-bundle',game=dict(gameId='synthetic'),
                 inputs=[dict(id='main',path='main',config='config.json'),dict(id='textures',path='external',config='config.json')]))
            before={p:p.read_bytes() for folder in (main.parent,external) for p in folder.rglob('*') if p.is_file()}
            result=convert_package(None,'both',root/'out',input_set_path=declaration,format_profile='grea')
            recovery=result['structuredRecovery'];self.assertNotEqual(recovery['status'],'failed',recovery)
            self.assertEqual(recovery['normalized']['spriteFrames'],1)
            self.assertEqual(recovery['normalized']['jsonAssets'],1)
            self.assertEqual(recovery['normalized']['nodes'],1)
            inspect=load(read(root/'out/Structured/inspect/source-manifest.json'))
            alias=next(a for a in inspect['assets'] if a.get('sourceId')=='synthetic:'+TEXTURE)
            self.assertEqual(alias['redirectTarget'],'textures:'+TEXTURE)
            for name in ('UnityProject','CocosProject'):
                project=root/'out'/name;m=load(read(project/'manifest.json'))
                self.assertEqual(m['projectLayout'],'monkey-project/2.0.0')
                self.assertFalse([d for d in (m.get('diagnostics') or []) if d['code']=='LAYOUT_FORBIDDEN_NAME'])
                self.assertEqual(m['validation']['editor'],'not_run')
                if name=='UnityProject':
                    plan=load(read(project/'Assets/Game/Editor/Conversion/import-plan.json'))
                    self.assertEqual(plan['tmpResources'],dict(packageName='com.unity.ugui',packageVersion='2.6.0',resource='Package Resources/TMP Essential Resources.unitypackage',importMode='package-completion-callback'))
                    self.assertEqual(load(read(project/'Packages/manifest.json'))['dependencies']['com.unity.ugui'],'2.6.0')
                    self.assertEqual(len(plan['sourcePrefabs']),1)
                    self.assertTrue(plan['sourcePrefabs'][0]['path'].startswith('Assets/Game/Content/Prefabs/'),plan['sourcePrefabs'][0]['path'])
                    asset=next(a for a in plan['assets'] if a['kind']=='cc.JsonAsset')
                    self.assertTrue(asset['path'].startswith('Assets/Game/Content/Config/'),asset['path'])
                    self.assertTrue((project/'Assets/Game/Presentation/Preview/ContentPreviewView.cs').exists())
                else:
                    plan=load(read(project/'extensions/monkey-import/import-plan.json'))
                    asset=next(a for a in plan['assets'] if a['kind']=='json')
                    self.assertEqual(load(read(project/(asset['path']+'.meta')))['ver'],'2.0.1')
                self.assertEqual(load(read(project/asset['path'])),payload)
                for row in m['files']:self.assertEqual(sha(read(project/row['path'])),row['sha256'])
            self.assertEqual(before,{p:p.read_bytes() for p in before})

    def test_equivalent_cached_index_kept_in_ledger_without_shadowing_payload_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();config=fixture(root/'source')
            cache=root/'cache';cache.mkdir();(cache/'123456.json').write_bytes(config.read_bytes())
            declaration=root/'inputs.json'
            write_json(declaration,dict(schemaVersion=1,sourceProfile='cocos-2.4.15-bundle',inputs=[
                dict(id='cache',path='cache'),dict(id='source',path='source')]))
            result=convert_package(None,'both',root/'out',input_set_path=declaration)
            recovery=result['structuredRecovery']
            self.assertNotEqual(recovery['status'],'failed',recovery)
            self.assertEqual(recovery['normalized']['spriteFrames'],1)
            self.assertEqual(len(recovery['bundleIndexAliases']),1)
            self.assertEqual(recovery['bundleIndexAliases'][0]['selected'],'source/config.json')
            indexed=load(read(root/'out/UnityProject/Analysis/Mappings/cocos-assets.json'))['assets']
            self.assertEqual(len(indexed),len(load(read(config))['uuids']))
            self.assertEqual(len({(a['bundle'],a['index']) for a in indexed}),len(indexed))
            self.assertEqual(result['projects'][0]['coverage']['inputFiles'],sum(1 for base in (cache,config.parent) for p in base.rglob('*') if p.is_file()))

    def test_resume_preserves_checkpoint_and_refuses_manual_edits(self):
        from monkey.package import resume_package
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();config=fixture(root/'source')
            declaration=root/'inputs.json'
            write_json(declaration,dict(schemaVersion=1,sourceProfile='cocos-2.4.15-bundle',
                inputs=[dict(id='main',path='source',config='config.json')]))
            first=convert_package(None,'unity6',root/'out',input_set_path=declaration)
            self.assertTrue(first['completed'])
            project=root/'out/UnityProject';manual=project/'Docs/START-HERE.md'
            original=manual.read_bytes();manual.write_bytes(original+b'personal edit')
            with self.assertRaises(ParseError) as error:resume_package(root/'out',declaration)
            self.assertEqual(error.exception.code,'RESUME_MANUAL_CONFLICT')
            self.assertEqual(manual.read_bytes(),original+b'personal edit')
            manual.write_bytes(original)
            second=resume_package(root/'out',declaration)
            self.assertTrue(second['completed'])
            self.assertEqual(len(second['structuredRecovery']['reused']),3)
            backup=root/'out'/second['resumeBackup']
            self.assertTrue((backup/'UnityProject/manifest.json').exists())
            # Simulate a failure after a fully owned candidate was published.
            failed=dict(second,completed=False,status='failed')
            write_json(root/'out/conversion-result.json',failed)
            third=resume_package(root/'out',declaration)
            self.assertTrue(third['completed'])
            self.assertTrue((root/'out'/third['resumeBackup']/'Interrupted/UnityProject/manifest.json').exists())
            signatures=root/'out/Structured/stage-signatures.json'
            original=signatures.read_bytes();data=load(original);data['inspect']['sha256']='changed-algorithm'
            write_json(signatures,data)
            before_projects=list((root/'out/Previous').iterdir())
            with self.assertRaises(ParseError) as mismatch:resume_package(root/'out',declaration)
            self.assertEqual(mismatch.exception.code,'RESUME_ALGORITHM_CHANGED')
            self.assertEqual(list((root/'out/Previous').iterdir()),before_projects)
            self.assertEqual(load(read(signatures)),data)
            signatures.write_bytes(original)

    def test_input_identity_and_casefold_root_conflicts_prevent_any_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();(root/'a').mkdir();(root/'b').mkdir();manifest=root/'inputs.json'
            data=dict(schemaVersion=1,sourceProfile='cocos-2.4.15-bundle',inputs=[
                dict(id='main',path='a',identity=dict(appId='first')),dict(id='dep',path='b',identity=dict(appId='second'))])
            write_json(manifest,data)
            with self.assertRaises(ParseError):convert_package(None,'both',root/'out',input_set_path=manifest)
            self.assertFalse((root/'out').exists())
            data['inputs'][1]=dict(id='MAIN',path='b');write_json(manifest,data)
            with self.assertRaises(ParseError):input_set(manifest)


if __name__=='__main__':unittest.main()
