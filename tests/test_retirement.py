from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from beaver.errors import BeaverError
from beaver.io import encoded, load, read, sha, write_json
from beaver.unity import apply, plan, recover
from test_adoption import candidate


SELECTED_GUID='33333333333333333333333333333333'
SCENE_GUID='44444444444444444444444444444444'
CODE_GUID='55555555555555555555555555555555'


def add_asset(project,path,content,guid):
    asset=project/path;asset.parent.mkdir(parents=True,exist_ok=True);asset.write_bytes(content)
    Path(str(asset)+'.meta').write_text('fileFormatVersion: 2\nguid: '+guid+'\n',encoding='utf-8')
    return asset


def fixture(root,resource=True):
    project=candidate(root/'Unity')
    selected=add_asset(project,Path('Assets/Game/Resources/Legacy.json'),b'{"old":true}',SELECTED_GUID)
    scene=add_asset(project,Path('Assets/Game/Scenes/Main.unity'),b'%YAML synthetic scene',SCENE_GUID)
    code=add_asset(project,Path('Assets/Game/Editor/Writer.cs'),b'// protected writer',CODE_GUID)
    spec={
        'schemaVersion':1,'operation':'assets.retire',
        'retire':[dict(path='Assets/Game/Resources/Legacy.json',role='obsolete-runtime-config',reason='Superseded by the approved JSON config.',sourceEvidence='Consumer review 2026-10-28: no longer an active runtime key.')],
        'protectedRoots':[str(scene.relative_to(project).as_posix()),str(code.relative_to(project).as_posix())],
        'resources':[dict(key='Legacy',path='Assets/Game/Resources/Legacy.json',guid=SELECTED_GUID,reason='Retire this implicit Resources key.',sourceEvidence='Consumer review explicitly identifies key Legacy.') ] if resource else [],
    }
    spec_path=root/'retire.json';write_json(spec_path,spec)
    return project,selected,spec_path


def native_report(plan_data,project):
    item=plan_data['retireManifest'][0]
    protected=[]
    for row in plan_data['protectedManifest']:
        protected.append(dict(path=row['path'],guid=row['guid'],sha256=row['sha256'],metaSha256=row['metaSha256'],
                              localIds=[row['guid']+':-100:UnityEngine.Object']))
    return dict(status='verified',operation='assets.retire',planSha256=sha(encoded(plan_data)),
                deleteInProgress='',selectedPaths=[item['path']],deletedPaths=[item['path']],
                retiredAssets=[dict(path=item['path'],guid=item['guid'],localIds=[item['guid']+':-200:UnityEngine.Object'])],
                protectedRoots=protected,dependencyPaths=[row['path'] for row in plan_data['protectedManifest']],
                dependencyClosures=[dict(root=row['path'],paths=[row['path']]) for row in plan_data['protectedManifest']],
                resources=plan_data['spec']['resources'],resourcesDynamicUseNotProvable=True,
                recoveredPaths=[item['path']])


class RetirementTests(unittest.TestCase):
    def test_plan_binds_file_meta_guid_role_evidence_roots_and_resources_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,selected,spec=fixture(root)
            planned=plan(project,spec,root/'preview');data=load(read(Path(planned['report'])))
            self.assertEqual(data['retireManifest'][0]['guid'],SELECTED_GUID)
            self.assertEqual(data['retireManifest'][0]['metaSha256'],data['before']['Assets/Game/Resources/Legacy.json.meta']['sha256'])
            self.assertEqual(data['protectedManifest'][0]['path'],'Assets/Game/Scenes/Main.unity')
            self.assertEqual(data['spec']['resources'][0]['key'],'Legacy')
            self.assertTrue(selected.is_file())

    def test_plan_requires_explicit_resources_declaration_and_rejects_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,selected,spec=fixture(root,resource=False)
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'missing-resources')
            self.assertEqual(error.exception.code,'ASSET_RETIRE_RESOURCE_DECLARATION')
            spec_data=load(read(spec));spec_data['retire'][0]['path']='Assets/Game/Resources'
            write_json(spec,spec_data)
            with self.assertRaises(BeaverError):plan(project,spec,root/'directory')

    def test_apply_uses_transaction_before_images_and_audits_only_selected_deletions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,selected,spec=fixture(root)
            planned=plan(project,spec,root/'preview');data=load(read(Path(planned['report'])))

            def native_run(editor,target,stage,mode,native_plan,timeout):
                report=native_report(native_plan,target)
                if mode=='apply':
                    backup=stage/'before/Assets/Game/Resources/Legacy.json'
                    self.assertEqual(backup.read_bytes(),b'{"old":true}')
                    selected.unlink();Path(str(selected)+'.meta').unlink()
                write_json(stage/('native-'+mode+'.json'),report)
                return report

            with patch('beaver.unity.editor_path',return_value=root/'UnityEditor'),patch('beaver.unity.native_lock'),patch('beaver.unity.run',side_effect=native_run):
                result=apply(planned['report'],root/'transaction',root/'UnityEditor',planned['planSha256'])
            self.assertEqual(result['status'],'verified')
            self.assertFalse(selected.exists());self.assertFalse(Path(str(selected)+'.meta').exists())
            self.assertEqual({row['path'] for row in result['changes']},{'Assets/Game/Resources/Legacy.json','Assets/Game/Resources/Legacy.json.meta'})

    def test_recovery_restores_only_witnessed_deleted_before_images(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,selected,spec=fixture(root)
            planned=plan(project,spec,root/'preview');plan_data=load(read(Path(planned['report'])))
            stage=root/'transaction';stage.mkdir();write_json(stage/'unity-plan.json',plan_data)
            checkpoint=native_report(plan_data,project)
            (stage/'before').mkdir()
            for item in plan_data['retireManifest']:
                for path in (item['path'],item['metaPath']):
                    source=project/path;target=stage/'before'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
            write_json(stage/'journal.json',dict(status='complete',operation='assets.retire',planSha256=planned['planSha256']))
            write_json(stage/'native-apply.json',checkpoint)
            selected.unlink();Path(str(selected)+'.meta').unlink()

            expected_modes=iter(('recover','recover-verify'))
            def native_run(editor,target,transaction,mode,native_plan,timeout):
                self.assertEqual(mode,next(expected_modes))
                self.assertTrue((target/'Assets/BeaverTools/Editor/BeaverNative.cs').is_file())
                report=native_report(native_plan,target)
                report['recoveredPaths']=checkpoint['deletedPaths']
                report['retiredAssets']=checkpoint['retiredAssets'];report['protectedRoots']=checkpoint['protectedRoots']
                report['dependencyPaths']=checkpoint['dependencyPaths'];report['resources']=checkpoint['resources']
                return report

            with patch('beaver.unity.editor_path',return_value=root/'UnityEditor'),patch('beaver.unity.native_lock'),patch('beaver.unity.run',side_effect=native_run):
                result=recover(stage,root/'UnityEditor',planned['planSha256'])
            self.assertEqual(result['status'],'recovered')
            self.assertEqual(selected.read_bytes(),b'{"old":true}')
            self.assertTrue(Path(str(selected)+'.meta').is_file())
            self.assertEqual(load(read(stage/'journal.json'))['status'],'recovered')
            self.assertFalse((project/'Assets/BeaverTools').exists())
            with patch('beaver.unity.editor_path',return_value=root/'UnityEditor'):
                with self.assertRaises(BeaverError) as error:recover(stage,root/'UnityEditor',planned['planSha256'])
            self.assertEqual(error.exception.code,'ASSET_RETIRE_RECOVERY_BLOCKED')

    def test_recovery_refuses_to_overwrite_changed_asset_or_unwitnessed_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,selected,spec=fixture(root)
            planned=plan(project,spec,root/'preview');data=load(read(Path(planned['report'])))
            stage=root/'transaction';stage.mkdir();write_json(stage/'unity-plan.json',data)
            (stage/'before').mkdir()
            for item in data['retireManifest']:
                for path in (item['path'],item['metaPath']):
                    source=project/path;target=stage/'before'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
            write_json(stage/'journal.json',dict(status='recovery-required',operation='assets.retire',planSha256=planned['planSha256']))
            write_json(stage/'native-apply.json',native_report(data,project))
            original_meta=Path(str(selected)+'.meta').read_bytes()
            selected.unlink();Path(str(selected)+'.meta').unlink();selected.write_bytes(b'later human bytes')
            with patch('beaver.unity.editor_path',return_value=root/'UnityEditor'):
                with self.assertRaises(BeaverError) as error:recover(stage,root/'UnityEditor',planned['planSha256'])
            self.assertEqual(error.exception.code,'ASSET_RETIRE_RECOVERY_BLOCKED')
            self.assertEqual(selected.read_bytes(),b'later human bytes')
            selected.unlink();Path(str(selected)+'.meta').write_bytes(original_meta)
            with patch('beaver.unity.editor_path',return_value=root/'UnityEditor'):
                with self.assertRaises(BeaverError) as error:recover(stage,root/'UnityEditor',planned['planSha256'])
            self.assertEqual(error.exception.code,'ASSET_RETIRE_RECOVERY_BLOCKED')
            Path(str(selected)+'.meta').unlink()
            write_json(stage/'native-apply.json',dict(status='failed',operation='assets.retire',planSha256=sha(encoded(data)),
                deleteInProgress='Assets/Game/Resources/Legacy.json',deletedPaths=[],selectedPaths=['Assets/Game/Resources/Legacy.json'],
                retiredAssets=native_report(data,project)['retiredAssets'],protectedRoots=native_report(data,project)['protectedRoots'],
                resourcesDynamicUseNotProvable=True,resources=data['spec']['resources'],dependencyPaths=[],
                dependencyClosures=[dict(root=row['path'],paths=[row['path']]) for row in data['protectedManifest']]))
            selected.unlink(missing_ok=True)
            with patch('beaver.unity.editor_path',return_value=root/'UnityEditor'):
                with self.assertRaises(BeaverError) as error:recover(stage,root/'UnityEditor',planned['planSha256'])
            self.assertEqual(error.exception.code,'ASSET_RETIRE_RECOVERY_BLOCKED')


if __name__=='__main__':unittest.main()
