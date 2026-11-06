from pathlib import Path
import tempfile
import unittest

from grea.development.errors import BeaverError
from grea.development.io import encoded, load, read, sha, write_json
from grea.development.unity import directory_guard, plan, source_files, validate_retired_folder_rows
from .test_adoption import candidate


FOLDER_GUID='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
SCENE_GUID='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
CODE_GUID='cccccccccccccccccccccccccccccccc'


def rebind_review(project,spec_path):
    spec=load(read(spec_path));review=spec['retire'][0]['callerReview']
    review['sourceSha256']=sha(encoded(source_files(project)))
    review['directorySetSha256']=directory_guard(project)['sha256']
    write_json(spec_path,spec)


def fixture(root):
    project=candidate(root/'Unity')
    scene=project/'Assets/Game/Scenes/Main.unity';scene.parent.mkdir(parents=True);scene.write_text('%YAML scene')
    Path(str(scene)+'.meta').write_text('fileFormatVersion: 2\nguid: '+SCENE_GUID+'\n')
    code=project/'Assets/Game/Scripts/Main.cs';code.parent.mkdir(parents=True);code.write_text('class Main {}')
    Path(str(code)+'.meta').write_text('fileFormatVersion: 2\nguid: '+CODE_GUID+'\n')
    folder=project/'Assets/Game/RetiredEmpty';folder.mkdir(parents=True)
    Path(str(folder)+'.meta').write_text('fileFormatVersion: 2\nguid: '+FOLDER_GUID+'\n')
    files=source_files(project);guard=directory_guard(project)
    item=dict(path='Assets/Game/RetiredEmpty',role='obsolete-empty-container',reason='No authored child assets remain.',
        sourceEvidence='Reviewed project migration record.',identityPolicy='empty-folder',callerReview=dict(
            reference='Analysis/folder-retirement-review.md',sourceSha256=sha(encoded(files)),
            directorySetSha256=guard['sha256'],dynamicPathReview=dict(status='reviewed-no-use',
                reason='Reviewed known runtime path construction and callers.',evidence='Analysis/folder-retirement-review.md#RetiredEmpty')))
    spec=dict(schemaVersion=1,operation='assets.retire',retire=[item],
        protectedRoots=['Assets/Game/Scenes/Main.unity','Assets/Game/Scripts/Main.cs'],resources=[])
    spec_path=root/'retire.json';write_json(spec_path,spec)
    return project,folder,spec_path


class EmptyFolderRetirementTests(unittest.TestCase):
    def test_plan_binds_folder_meta_native_guid_and_complete_directory_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,folder,spec=fixture(root)
            result=plan(project,spec,root/'preview');data=load(read(Path(result['report'])))
            manifest=data['folderRetireManifest'][0]
            self.assertEqual(manifest['guid'],FOLDER_GUID)
            self.assertEqual(manifest['metaPath'],manifest['path']+'.meta')
            self.assertEqual(manifest['callerReview']['dynamicPathReview']['status'],'reviewed-no-use')
            self.assertIn(manifest['path'],data['sourceDirectoryGuard']['paths'])
            self.assertEqual(data['sourceDirectoryGuard'],directory_guard(project))
            native=dict(path=manifest['path'],guid=FOLDER_GUID,localId=102900000,identityStatus='verified')
            validate_retired_folder_rows([manifest],[native])
            with self.assertRaises(BeaverError):validate_retired_folder_rows([manifest],[dict(native,localId=0)])
            with self.assertRaises(BeaverError):validate_retired_folder_rows([manifest],[dict(native,guid='dddddddddddddddddddddddddddddddd')])

    def test_nonempty_child_and_symlink_folders_are_rejected(self):
        for kind in ('file','child','symlink'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve();project,folder,spec=fixture(root)
                if kind=='file':(folder/'hidden.data').write_bytes(b'x')
                elif kind=='child':(folder/'Child').mkdir()
                else:(folder/'link').symlink_to(project/'Assets/Game/Scripts/Main.cs')
                with self.assertRaises(BeaverError) as error:plan(project,spec,root/'blocked')
                self.assertIn(error.exception.code,('ASSET_RETIRE_FOLDER_NOT_EMPTY','SYMLINK_PATH'))

    def test_static_guid_reference_and_stale_directory_guard_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,folder,spec=fixture(root)
            source=project/'Assets/Game/Scripts/Main.cs';source.write_text('referenced = "'+FOLDER_GUID+'";')
            rebind_review(project,spec)
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'blocked')
            self.assertEqual(error.exception.code,'ASSET_RETIRE_FOLDER_REFERENCED')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,folder,spec=fixture(root)
            (project/'Assets/Game/UntrackedEmpty').mkdir()
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'blocked')
            self.assertEqual(error.exception.code,'ASSET_RETIRE_CALLER_REVIEW')

    def test_missing_caller_review_and_mixed_file_folder_batch_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,folder,spec=fixture(root);doc=load(read(spec))
            del doc['retire'][0]['callerReview'];write_json(spec,doc)
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'blocked')
            self.assertEqual(error.exception.code,'ASSET_RETIRE_CALLER_REVIEW')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,folder,spec=fixture(root);doc=load(read(spec))
            doc['retire'].append(dict(path='Assets/Game/Scripts/Main.cs',role='file',reason='Retire file.',sourceEvidence='review'))
            write_json(spec,doc)
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'blocked')
            self.assertEqual(error.exception.code,'ASSET_RETIRE_MIXED')


if __name__=='__main__':
    unittest.main()

class FolderRecoveryOwnershipTests(unittest.TestCase):
    def prepare(self,root):
        from grea.development.output_limits import digest_file
        project,folder,spec=fixture(root);planned=plan(project,spec,root/'preview')
        data=load(read(Path(planned['report'])));item=data['folderRetireManifest'][0]
        stage=root/'transaction';stage.mkdir();write_json(stage/'unity-plan.json',data)
        image=stage/'before'/item['metaPath'];image.parent.mkdir(parents=True);image.write_bytes(Path(str(folder)+'.meta').read_bytes())
        protected=[dict(path=row['path'],guid=row['guid'],sha256=row['sha256'],metaSha256=row['metaSha256'],localIds=[row['guid']+':-100:UnityEngine.Object']) for row in data['protectedManifest']]
        row=dict(path=item['path'],guid=item['guid'],identityStatus='verified',localId=102900000)
        native=dict(status='verified',operation='assets.retire',planSha256=planned['planSha256'],selectedPaths=[],deletedPaths=[],retiredAssets=[],deleteInProgress='',retiredFolders=[row],deletedFolders=[item['path']],folderDeleteInProgress='',folderDynamicPathUseNotProvable=True,protectedRoots=protected,dependencyPaths=[r['path'] for r in protected],dependencyClosures=[dict(root=r['path'],paths=[r['path']]) for r in protected],resources=[],resourcesDynamicUseNotProvable=True,recoveredPaths=[],recoveredFolders=[item['path']])
        write_json(stage/'native-apply.json',native)
        journal=dict(status='recovery-required',operation='assets.retire',planSha256=planned['planSha256'])
        Path(str(folder)+'.meta').unlink();folder.rmdir()
        return project,folder,planned,stage,journal,native,item

    def test_owned_created_directory_can_resume_before_metadata_copy(self):
        from unittest.mock import patch
        from grea.development.unity import recover
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,folder,planned,stage,journal,native,item=self.prepare(root)
            folder.mkdir();journal['recoveryRestoredFolders']=[item['path']];write_json(stage/'journal.json',journal)
            with patch('grea.development.unity.editor_path',return_value=root/'Editor'),patch('grea.development.unity.native_lock'),patch('grea.development.unity.run',return_value=native):
                result=recover(stage,root/'Editor',planned['planSha256'])
            self.assertEqual(result['status'],'recovered');self.assertEqual(result['restoredFiles'],1)
            self.assertEqual(read(Path(str(folder)+'.meta')),read(stage/'before'/item['metaPath']))
            self.assertEqual(directory_guard(project),load(read(stage/'unity-plan.json'))['sourceDirectoryGuard'])

    def test_unowned_recreated_folder_and_lost_owned_metadata_are_refused(self):
        from unittest.mock import patch
        from grea.development.unity import recover
        for owned in (False,True):
            with self.subTest(owned=owned),tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve();project,folder,planned,stage,journal,native,item=self.prepare(root)
                folder.mkdir()
                if owned:
                    journal['recoveryRestoredFolders']=[item['path']];journal['recoveryRestoredPaths']=[item['metaPath']]
                write_json(stage/'journal.json',journal)
                with patch('grea.development.unity.editor_path',return_value=root/'Editor'),patch('grea.development.unity.native_lock'),patch('grea.development.unity.run') as runner,self.assertRaises(BeaverError) as error:
                    recover(stage,root/'Editor',planned['planSha256'])
                self.assertEqual(error.exception.code,'ASSET_RETIRE_RECOVERY_BLOCKED');runner.assert_not_called()
                self.assertFalse(Path(str(folder)+'.meta').exists())
