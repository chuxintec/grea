from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from grea.development.errors import BeaverError
from grea.development.io import encoded, load, read, sha, write_json
from grea.development.unity import apply, plan, validate_spec
from .test_adoption import candidate


def unity_project(root):
    project=candidate(root)
    folders=(
        'Assets/Game',
        'Assets/Game/Content',
        'Assets/Game/Content/Data',
        'Assets/Game/Content/Data/Test',
    )
    for index,folder in enumerate(folders,1):
        (project/(folder+'.meta')).write_text(
            'fileFormatVersion: 2\nfolderAsset: yes\nguid: '+format(index,'032x')+'\n',
            encoding='utf-8')
    return project


class FolderMoveTests(unittest.TestCase):
    def test_plan_binds_complete_subtree_paths_hashes_and_folder_metas(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project=unity_project(root/'Unity');spec=root/'move.json'
            write_json(spec,dict(schemaVersion=1,operation='assets.move',directoryMoves=[dict(
                source='Assets/Game/Content/Data',target='Assets/Game/Domain/Data')]))
            result=plan(project,spec,root/'preview')
            document=load(read(Path(result['report'])))
            rows=document['folderMoveManifest'][0]['entries']
            mapping={row['source']:row['target'] for row in rows}
            self.assertEqual(mapping['Assets/Game/Content/Data.meta'],'Assets/Game/Domain/Data.meta')
            self.assertEqual(mapping['Assets/Game/Content/Data/Test/A.txt'],'Assets/Game/Domain/Data/Test/A.txt')
            self.assertEqual(mapping['Assets/Game/Content/Data/Test/A.txt.meta'],'Assets/Game/Domain/Data/Test/A.txt.meta')
            self.assertEqual(mapping['Assets/Game/Content/Data/Test'],'Assets/Game/Domain/Data/Test')
            self.assertTrue(all(row.get('sha256') for row in rows if row['kind']!='folder'))
            self.assertEqual(result['status'],'planned')

    def test_rejects_occupied_targets_incomplete_subtree_meta_and_nested_moves(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project=unity_project(root/'Unity');spec=root/'move.json'
            write_json(spec,dict(schemaVersion=1,operation='assets.move',directoryMoves=[dict(
                source='Assets/Game/Content/Data',target='Assets/Game/Domain/Data')]))
            occupied=project/'Assets/Game/Domain/Data';occupied.mkdir(parents=True)
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'occupied')
            self.assertEqual(error.exception.code,'ASSET_MOVE_DESTINATION')
            occupied.rmdir();(project/'Assets/Game/Content/Data/Test.meta').unlink()
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'missing-meta')
            self.assertEqual(error.exception.code,'ASSET_MOVE_INCOMPLETE_META')
            (project/'Assets/Game/Content/Data/Test.meta').write_text(
                'fileFormatVersion: 2\nfolderAsset: yes\nguid: '+'0'*32+'\n',encoding='utf-8')
            write_json(spec,dict(schemaVersion=1,operation='assets.move',directoryMoves=[dict(
                source='Assets/Game/Content/Data',target='Assets/game/Domain/Data')]))
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'case-collision')
            self.assertEqual(error.exception.code,'ASSET_MOVE_CASE_COLLISION')
            with self.assertRaises(BeaverError):validate_spec(dict(schemaVersion=1,operation='assets.move',directoryMoves=[
                dict(source='Assets/Game/Content',target='Assets/Game/Archive'),
                dict(source='Assets/Game/Content/Data',target='Assets/Game/Other')]))

    def test_apply_checkpoints_verified_before_images_before_native_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project=unity_project(root/'Unity');spec=root/'move.json'
            write_json(spec,dict(schemaVersion=1,operation='assets.move',directoryMoves=[dict(
                source='Assets/Game/Content/Data',target='Assets/Game/Domain/Data')]))
            result=plan(project,spec,root/'preview')
            plan_data=load(read(Path(result['report'])))
            observed=[]

            def native_run(editor, target, stage, mode, native_plan, timeout):
                journal=load(read(stage/'journal.json'))
                observed.append((mode,journal.get('status'),journal.get('checkpoint')))
                self.assertEqual(journal.get('checkpoint'),'source-bytes-verified')
                if mode=='apply':
                    self.assertEqual(journal.get('status'),'before-images-complete')
                    source=target/'Assets/Game/Content/Data';destination=target/'Assets/Game/Domain/Data'
                    destination.parent.mkdir(parents=True);shutil.move(str(source),str(destination))
                    shutil.move(str(target/'Assets/Game/Content/Data.meta'),str(target/'Assets/Game/Domain/Data.meta'))
                else:
                    self.assertEqual(journal.get('status'),'native-apply-complete-pending-reopen')
                return dict(status='verified',planSha256=sha(encoded(native_plan)),moves=[],moveIdentities=[])

            with patch('grea.development.unity.editor_path',return_value=root/'UnityEditor'), \
                 patch('grea.development.unity.native_lock'), patch('grea.development.unity.run',side_effect=native_run):
                applied=apply(result['report'],root/'transaction',root/'UnityEditor',result['planSha256'])
            before=Path(applied['transaction'])/'before/Assets/Game/Content/Data/Test/A.txt'
            self.assertEqual(before.read_bytes(),b'old')
            self.assertEqual(observed,[('apply','before-images-complete','source-bytes-verified'),
                                       ('verify','native-apply-complete-pending-reopen','source-bytes-verified')])
            self.assertEqual(applied['status'],'verified')


if __name__=='__main__':unittest.main()
