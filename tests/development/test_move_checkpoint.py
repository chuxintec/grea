from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from grea.development.batch import (MOVE_DELTA_POLICY, directory_inventory, plan, recover, state,
                          unplanned_move_directories, validate, validate_native_checkpoint)
from grea.development.errors import BeaverError
from grea.development.io import load, read, write_json
from grea.development.unity import identity
from .test_adoption import candidate


def fixture(root,policy=MOVE_DELTA_POLICY):
    project=candidate(root/'project')
    moves=[]
    for index in range(2):
        source=f'Assets/Source/File{index}.txt';asset=project/source
        asset.parent.mkdir(parents=True,exist_ok=True);asset.write_bytes(f'file-{index}'.encode())
        Path(str(asset)+'.meta').write_text(f'guid: {index+1:032x}\n')
        target=f'Assets/Target/Nested/File{index}.txt'
        moves.append(dict(kind='asset.move',source=source,target=target))
    spec=dict(schemaVersion=2,operation='batch',steps=moves)
    if policy is not None:spec['checkpointPolicy']=policy
    spec_path=root/'spec.json';write_json(spec_path,spec)
    return project,spec_path


def native_report(data,project,state_name='full-final'):
    observed=state(project,data['writeSet'])
    rows=[dict(path=path,exists=value is not None,sha256=value['sha256'] if value else '',bytes=value['bytes'] if value else 0)
          for path,value in observed.items()]
    return dict(planSha256='a'*64,checkpointPolicy=MOVE_DELTA_POLICY,checkpointState=state_name,
        checkpointComplete=state_name=='full-final',checkpointCount=4,
        checkpointPaths=sorted(data['writeSet']) if state_name=='full-final' else data['writeSet'][:2],files=rows)


class MoveCheckpointTests(unittest.TestCase):
    def test_opt_in_plans_only_pure_non_scene_moves_and_binds_created_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,spec=fixture(root)
            result=plan(project,spec,root/'plan');data=load(read(Path(result['report'])))
            self.assertEqual(data['checkpointPolicy'],MOVE_DELTA_POLICY)
            self.assertIn('Assets/Target',data['moveDirectoryGuard']['created'])
            self.assertIn('Assets/Target/Nested',data['moveDirectoryGuard']['created'])
            self.assertEqual(data['moveDirectoryGuard']['before'],directory_inventory(project))

    def test_policy_rejects_unknown_scene_runtime_read_and_non_move_specs(self):
        base=dict(schemaVersion=2,operation='batch',checkpointPolicy=MOVE_DELTA_POLICY,
                  steps=[dict(kind='asset.move',source='Assets/A.txt',target='Assets/B.txt')])
        validate(base)
        cases=[dict(base,checkpointPolicy='unknown'),dict(base,steps=[dict(kind='asset.move',source='Assets/A.unity',target='Assets/B.unity')]),
               dict(base,runtimeRoot='Assets/Runtime'),dict(base,readPaths=['Assets/Read.txt']),
               dict(base,steps=[dict(kind='prefab.inspect',assetPath='Assets/A.prefab')])]
        for value in cases:
            with self.subTest(value=value),self.assertRaises(BeaverError):validate(value)

    def test_delta_rows_are_never_a_recovery_witness_even_if_they_cover_the_write_set(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,spec=fixture(root);data=load(read(Path(plan(project,spec,root/'plan')['report'])))
            report=native_report(data,project,'delta')
            report['checkpointPaths']=sorted(data['writeSet'])
            self.assertFalse(validate_native_checkpoint(report,data['writeSet'],MOVE_DELTA_POLICY))
            report['checkpointState']='full-final';report['checkpointComplete']=True
            self.assertTrue(validate_native_checkpoint(report,data['writeSet'],MOVE_DELTA_POLICY))
            report['checkpointPaths']=list(reversed(report['checkpointPaths']))
            self.assertTrue(validate_native_checkpoint(report,data['writeSet'],MOVE_DELTA_POLICY))

    def test_partial_failure_allows_only_not_yet_created_planned_destination_directories(self):
        before=['Assets','Assets/Source']
        planned=['Assets/Target/A','Assets/Target/B','Assets/Target/C']
        partial=before+planned[:1]
        self.assertEqual(unplanned_move_directories(before,planned,partial),[])
        self.assertTrue(unplanned_move_directories(before,planned,partial,complete=True))
        self.assertTrue(unplanned_move_directories(before,planned,partial+['Assets/Unexpected']))

    def test_public_recovery_rejects_cached_delta_checkpoint_before_editor(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,spec=fixture(root);planned=plan(project,spec,root/'plan')
            data=load(read(Path(planned['report'])));tx=root/'transaction';tx.mkdir()
            write_json(tx/'batch-plan.json',data)
            before={path:data['before'][path] for path in data['writeSet']}
            for path,value in before.items():
                if value is not None:
                    dest=tx/'before'/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((project/path).read_bytes())
            witnessed=state(project,data['writeSet']);report=native_report(data,project,'delta')
            report['planSha256']=planned['planSha256']
            journal=dict(contract='beaver-batch-transaction/2',status='recovery-required',projectRoot=str(project),
                planSha256=planned['planSha256'],implementationSha256=identity(),writeSet=data['writeSet'],before=before,
                after=witnessed,unplannedPaths=[],unplannedDirectories=[],directorySetAfter=directory_inventory(project),native=report)
            write_json(tx/'journal.json',journal)
            with patch('grea.development.batch.editor_path',return_value=root/'Unity'),patch('grea.development.batch.native_lock'),patch('grea.development.batch.launch') as launch:
                with self.assertRaises(BeaverError) as error:recover(tx,root/'recovery',root/'Unity')
            self.assertEqual(error.exception.code,'BATCH_RECOVERY_UNCERTAIN')
            launch.assert_not_called()

    def test_later_source_edit_after_full_final_checkpoint_blocks_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,spec=fixture(root);planned=plan(project,spec,root/'plan')
            data=load(read(Path(planned['report'])));tx=root/'transaction';tx.mkdir();write_json(tx/'batch-plan.json',data)
            before={path:data['before'][path] for path in data['writeSet']}
            for path,value in before.items():
                if value is not None:
                    dest=tx/'before'/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((project/path).read_bytes())
            witnessed=state(project,data['writeSet']);report=native_report(data,project)
            report.update(status='failed',planSha256=planned['planSha256'])
            write_json(tx/'journal.json',dict(contract='beaver-batch-transaction/2',status='recovery-required',projectRoot=str(project),
                planSha256=planned['planSha256'],implementationSha256=identity(),writeSet=data['writeSet'],before=before,
                after=witnessed,unplannedPaths=[],unplannedDirectories=[],directorySetAfter=directory_inventory(project),native=report))
            (project/'Assets/Source/File0.txt').write_bytes(b'later edit')
            with patch('grea.development.batch.editor_path',return_value=root/'Unity'),patch('grea.development.batch.native_lock'),patch('grea.development.batch.launch') as launch:
                with self.assertRaises(BeaverError) as error:recover(tx,root/'recovery',root/'Unity')
            self.assertEqual(error.exception.code,'BATCH_LATER_EDIT')
            launch.assert_not_called()


if __name__=='__main__':
    unittest.main()
