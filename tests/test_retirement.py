from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from beaver.errors import BeaverError
from beaver.io import encoded, load, read, sha, write_json
from beaver.unity import apply, plan, recover, run, validate_retire_identity_rows, validate_retire_source_evidence
from beaver.output_limits import digest_file
from test_adoption import candidate


SELECTED_GUID='33333333333333333333333333333333'
SCENE_GUID='44444444444444444444444444444444'
CODE_GUID='55555555555555555555555555555555'


def add_asset(project,path,content,guid):
    asset=project/path;asset.parent.mkdir(parents=True,exist_ok=True);asset.write_bytes(content)
    Path(str(asset)+'.meta').write_text('fileFormatVersion: 2\nguid: '+guid+'\n',encoding='utf-8')
    return asset


def fixture(root,resource=True,source_only=False):
    project=candidate(root/'Unity')
    selected=add_asset(project,Path('Assets/Game/Resources/Legacy.json'),b'{"old":true}',SELECTED_GUID)
    scene=add_asset(project,Path('Assets/Game/Scenes/Main.unity'),b'%YAML synthetic scene',SCENE_GUID)
    code=add_asset(project,Path('Assets/Game/Editor/Writer.cs'),b'// protected writer',CODE_GUID)
    evidence=None
    if source_only:
        snapshot=dict(schemaVersion=1,target='StandaloneOSX',pipeline='URP',buildScenes=[],explicitRoots=[],implicitRoots=[],
            coverage=dict(complete=True,blockers=[]),
            assets=[dict(path='Assets/Game/Resources/Legacy.json',guid=SELECTED_GUID,localIds=[],types=[],status='unknown',
                         identityStatus='no-persistent-object',objectCount=0,error='No persistent Unity objects were returned.')],
            dependencies=[],unresolvedDependencies=[],
            inputState={
                'Assets/Game/Resources/Legacy.json':dict(sha256=digest_file(selected),bytes=selected.stat().st_size),
                'Assets/Game/Resources/Legacy.json.meta':dict(sha256=digest_file(Path(str(selected)+'.meta')),bytes=Path(str(selected)+'.meta').stat().st_size),
            },
            editorExitCode=0,nativeReadback=dict(status='verified'),sourceUnchanged=True,unplannedProjectChanges=[],
            helperCleaned=True,visualAcceptance='not_run',gameplayAcceptance='not_run')
        snapshot_path=root/'collector-snapshot.json';write_json(snapshot_path,snapshot)
        evidence=dict(snapshotPath=str(snapshot_path),snapshotSha256=sha(read(snapshot_path)),assetPath='Assets/Game/Resources/Legacy.json')
    retire_item=dict(path='Assets/Game/Resources/Legacy.json',role='obsolete-runtime-config',reason='Superseded by the approved JSON config.',sourceEvidence='Consumer review 2026-10-28: no longer an active runtime key.')
    if source_only:
        retire_item.update(identityPolicy='source-evidence-only',sourceIdentityEvidence=evidence)
    spec={
        'schemaVersion':1,'operation':'assets.retire',
        'retire':[retire_item],
        'protectedRoots':[str(scene.relative_to(project).as_posix()),str(code.relative_to(project).as_posix())],
        'resources':[dict(key='Legacy',path='Assets/Game/Resources/Legacy.json',guid=SELECTED_GUID,reason='Retire this implicit Resources key.',sourceEvidence='Consumer review explicitly identifies key Legacy.') ] if resource else [],
    }
    spec_path=root/'retire.json';write_json(spec_path,spec)
    return project,selected,spec_path


def two_source_fixture(root):
    project,first,spec_path=fixture(root,source_only=True)
    second=add_asset(project,Path('Assets/Game/Resources/Legacy2.json'),b'{"old":2}',
                     '66666666666666666666666666666666')
    spec=load(read(spec_path));snapshot_path=Path(spec['retire'][0]['sourceIdentityEvidence']['snapshotPath'])
    snapshot=load(read(snapshot_path));second_path='Assets/Game/Resources/Legacy2.json'
    second_meta=Path(str(second)+'.meta')
    snapshot['assets'].append(dict(path=second_path,guid='66666666666666666666666666666666',localIds=[],types=[],status='unknown',
        identityStatus='no-persistent-object',objectCount=0,error='AssetDatabase returned zero objects from main asset and subassets.'))
    snapshot['inputState'][second_path]=dict(sha256=digest_file(second),bytes=second.stat().st_size)
    snapshot['inputState'][second_path+'.meta']=dict(sha256=digest_file(second_meta),bytes=second_meta.stat().st_size)
    write_json(snapshot_path,snapshot);snapshot_sha=sha(read(snapshot_path))
    spec['retire'][0]['sourceIdentityEvidence']['snapshotSha256']=snapshot_sha
    spec['retire'].append(dict(path=second_path,role='obsolete-runtime-config',reason='Superseded.',
        sourceEvidence='Two-source collector snapshot fixture.',identityPolicy='source-evidence-only',
        sourceIdentityEvidence=dict(snapshotPath=str(snapshot_path),snapshotSha256=snapshot_sha,assetPath=second_path)))
    spec['resources'].append(dict(key='Legacy2',path=second_path,guid='66666666666666666666666666666666',
        reason='Retire explicit key Legacy2.',sourceEvidence='Two-source collector snapshot fixture.'))
    write_json(spec_path,spec)
    return project,first,second,snapshot_path,spec_path


def native_report(plan_data,project):
    item=plan_data['retireManifest'][0]
    source_only=item.get('identityPolicy')=='source-evidence-only'
    protected=[]
    for row in plan_data['protectedManifest']:
        protected.append(dict(path=row['path'],guid=row['guid'],sha256=row['sha256'],metaSha256=row['metaSha256'],
                              localIds=[row['guid']+':-100:UnityEngine.Object']))
    return dict(status='verified',operation='assets.retire',planSha256=sha(encoded(plan_data)),
                deleteInProgress='',selectedPaths=[item['path']],deletedPaths=[item['path']],
                retiredAssets=[dict(path=item['path'],guid=item['guid'],identityPolicy=item.get('identityPolicy','native-object'),
                    identityStatus='no-persistent-object' if source_only else 'verified',nativeObjectCount=0 if source_only else 1,
                    localIds=[] if source_only else [item['guid']+':-200:UnityEngine.Object'],
                    sourceEvidenceSnapshotSha256=item['sourceIdentityEvidence']['snapshotSha256'] if source_only else '',
                    sourceEvidenceTargetRecordSha256=item['sourceIdentityEvidence']['targetRecordSha256'] if source_only else '')],
                protectedRoots=protected,dependencyPaths=[row['path'] for row in plan_data['protectedManifest']],
                dependencyClosures=[dict(root=row['path'],paths=[row['path']]) for row in plan_data['protectedManifest']],
                resources=plan_data['spec']['resources'],resourcesDynamicUseNotProvable=True,
                recoveredPaths=[item['path']])


class RetirementTests(unittest.TestCase):
    def test_source_only_snapshot_without_native_guid_is_not_archive_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,selected,spec=fixture(root,source_only=True)
            doc=load(read(spec));snapshot_path=Path(doc['retire'][0]['sourceIdentityEvidence']['snapshotPath'])
            snapshot=load(read(snapshot_path));snapshot['assets'][0]['guid']=None;write_json(snapshot_path,snapshot)
            doc['retire'][0]['sourceIdentityEvidence']['snapshotSha256']=sha(read(snapshot_path));write_json(spec,doc)
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'blocked')
            self.assertEqual(error.exception.code,'ASSET_RETIRE_SOURCE_EVIDENCE_GUID')
            self.assertTrue(selected.exists())


    def test_case_insensitive_remaining_resources_collision_blocks_retirement(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,selected,spec=fixture(root)
            add_asset(project,Path('Assets/Other/Resources/legacy.asset'),b'synthetic remaining evidence','66666666666666666666666666666666')
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'blocked')
            self.assertEqual(error.exception.code,'ASSET_RETIRE_RESOURCE_AMBIGUOUS')
            self.assertTrue(selected.exists())


    def test_plan_binds_file_meta_guid_role_evidence_roots_and_resources_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,selected,spec=fixture(root,source_only=True)
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

    def test_source_only_evidence_binds_snapshot_and_current_target_input_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,selected,spec=fixture(root,source_only=True)
            planned=plan(project,spec,root/'preview');data=load(read(Path(planned['report'])))
            item=data['retireManifest'][0];evidence=item['sourceIdentityEvidence']
            self.assertEqual(item['identityPolicy'],'source-evidence-only')
            self.assertIs(item['hasSourceIdentityEvidence'],True)
            self.assertEqual(evidence['assetPath'],item['path'])
            self.assertEqual(evidence['targetRecordSha256'],sha(encoded(evidence['targetRecord'])))
            self.assertEqual(evidence['targetInputs'][0]['sha256'],item['sha256'])
            self.assertEqual(evidence['targetInputs'][1]['sha256'],item['metaSha256'])
            snapshot_path=Path(evidence['snapshotPath']);snapshot=load(read(snapshot_path))
            snapshot_path.write_text(json.dumps(snapshot,sort_keys=True,separators=(',',':')),encoding='utf-8')
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'reformatted-artifact')
            self.assertEqual(error.exception.code,'ASSET_RETIRE_SOURCE_EVIDENCE_HASH')
            write_json(snapshot_path,snapshot)
            snapshot['assets'][0]['identityStatus']='persistent-identity-unavailable';snapshot['assets'][0]['objectCount']=1
            write_json(snapshot_path,snapshot)
            spec_data=load(read(spec));spec_data['retire'][0]['sourceIdentityEvidence']['snapshotSha256']=sha(read(snapshot_path))
            write_json(spec,spec_data)
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'unsupported-identity-state')
            self.assertEqual(error.exception.code,'ASSET_RETIRE_SOURCE_EVIDENCE_STATE')
            snapshot=load(read(snapshot_path));snapshot['assets'][0]['identityStatus']='no-persistent-object';snapshot['assets'][0]['objectCount']=0
            snapshot['inputState'][item['path']]['sha256']='0'*64
            write_json(snapshot_path,snapshot)
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'bad-artifact')
            self.assertEqual(error.exception.code,'ASSET_RETIRE_SOURCE_EVIDENCE_HASH')
            spec_data=load(read(spec));spec_data['retire'][0]['sourceIdentityEvidence']['snapshotSha256']=sha(read(snapshot_path))
            write_json(spec,spec_data)
            with self.assertRaises(BeaverError) as error:plan(project,spec,root/'bad-target-input')
            self.assertEqual(error.exception.code,'ASSET_RETIRE_SOURCE_EVIDENCE_INPUT')

    def test_shared_source_only_snapshot_is_read_and_validated_once_per_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,first,second,snapshot_path,spec=two_source_fixture(root)
            from beaver import build_filter
            with patch('beaver.unity.read',wraps=read) as read_spy,patch('beaver.build_filter._snapshot',wraps=build_filter._snapshot) as snapshot_spy:
                result=plan(project,spec,root/'shared-plan')
            self.assertEqual(sum(Path(call.args[0]).resolve()==snapshot_path.resolve() for call in read_spy.call_args_list),1)
            self.assertEqual(snapshot_spy.call_count,1)
            data=load(read(Path(result['report'])));rows=data['retireManifest']
            self.assertEqual([row['sourceIdentityEvidence']['targetRecord']['path'] for row in rows],
                             ['Assets/Game/Resources/Legacy.json','Assets/Game/Resources/Legacy2.json'])
            self.assertTrue(all(row['sourceIdentityEvidence']['targetRecordSha256']==sha(encoded(row['sourceIdentityEvidence']['targetRecord'])) for row in rows))

    def test_shared_snapshot_cache_still_rejects_second_target_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,first,second,snapshot_path,spec=two_source_fixture(root)
            snapshot=load(read(snapshot_path));second_path='Assets/Game/Resources/Legacy2.json'
            snapshot['inputState'][second_path]['sha256']='0'*64
            write_json(snapshot_path,snapshot);snapshot_sha=sha(read(snapshot_path))
            spec_data=load(read(spec))
            for item in spec_data['retire']:item['sourceIdentityEvidence']['snapshotSha256']=snapshot_sha
            write_json(spec,spec_data)
            from beaver import build_filter
            with patch('beaver.unity.read',wraps=read) as read_spy,patch('beaver.build_filter._snapshot',wraps=build_filter._snapshot) as snapshot_spy:
                with self.assertRaises(BeaverError) as error:plan(project,spec,root/'stale-second-target')
            self.assertEqual(error.exception.code,'ASSET_RETIRE_SOURCE_EVIDENCE_INPUT')
            self.assertEqual(sum(Path(call.args[0]).resolve()==snapshot_path.resolve() for call in read_spy.call_args_list),1)
            self.assertEqual(snapshot_spy.call_count,1)

    def test_native_identity_policy_rejects_forged_empty_or_nonempty_id_states(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,_,spec=fixture(root,source_only=True)
            planned=plan(project,spec,root/'source-only-plan');data=load(read(Path(planned['report'])))
            manifest=data['retireManifest'];row=native_report(data,project)['retiredAssets'][0]
            validate_retire_identity_rows(manifest,[row])
            forged=dict(row,localIds=['fake:0:Object'],nativeObjectCount=1)
            with self.assertRaises(BeaverError):validate_retire_identity_rows(manifest,[forged])
            forged_hash=dict(row,sourceEvidenceTargetRecordSha256='0'*64)
            with self.assertRaises(BeaverError):validate_retire_identity_rows(manifest,[forged_hash])
            forged_missing=dict(row,sourceEvidenceSnapshotSha256=None)
            with self.assertRaises(BeaverError):validate_retire_identity_rows(manifest,[forged_missing])
            forged_manifest=dict(manifest[0]);forged_manifest['sourceIdentityEvidence']=dict(manifest[0]['sourceIdentityEvidence'],targetRecordSha256='0'*64)
            with self.assertRaises(BeaverError):validate_retire_source_evidence(forged_manifest)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,_,spec=fixture(root)
            planned=plan(project,spec,root/'native-plan');data=load(read(Path(planned['report'])))
            forged=dict(native_report(data,project)['retiredAssets'][0],identityStatus='no-persistent-object',nativeObjectCount=0,localIds=[])
            with self.assertRaises(BeaverError):validate_retire_identity_rows(data['retireManifest'],[forged])

    def test_native_object_recovery_identity_normalizes_jsonutility_empty_strings(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,_,spec=fixture(root)
            planned=plan(project,spec,root/'native-plan');data=load(read(Path(planned['report'])))
            witness=native_report(data,project)['retiredAssets'][0]
            observed=dict(witness,sourceEvidenceSnapshotSha256=None,sourceEvidenceTargetRecordSha256=None)
            validate_retire_identity_rows(data['retireManifest'],[observed],witnessed=[witness])

    def test_apply_uses_transaction_before_images_and_audits_only_selected_deletions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,selected,spec=fixture(root,source_only=True)
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
            self.assertIs(data['retireManifest'][0]['hasSourceIdentityEvidence'],True)
            self.assertFalse(selected.exists());self.assertFalse(Path(str(selected)+'.meta').exists())
            self.assertEqual({row['path'] for row in result['changes']},{'Assets/Game/Resources/Legacy.json','Assets/Game/Resources/Legacy.json.meta'})

    def test_generated_native_job_carries_derived_evidence_presence_flag(self):
        for source_only in (False,True):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve();project,_,spec=fixture(root,source_only=source_only)
                planned=plan(project,spec,root/'preview');data=load(read(Path(planned['report'])))
                stage=root/'transaction';stage.mkdir()
                import base64

                def editor_environment(control,job_path):
                    return {'BEAVER_NATIVE_JOB_BASE64':base64.b64encode(str(job_path).encode()).decode()}

                def launch(args,cwd,env,stdout,stderr):
                    job_path=Path(base64.b64decode(env['BEAVER_NATIVE_JOB_BASE64']).decode())
                    job=load(read(job_path))
                    report=dict(status='verified',planSha256=job['planSha256'])
                    write_json(stage/'native-apply.json',report)

                    class Process:
                        pid=9876
                        returncode=0
                        def wait(self,timeout):return 0
                    return Process()

                with patch('beaver.unity.subprocess.Popen',side_effect=launch), \
                     patch('beaver.native_environment.editor_environment',side_effect=editor_environment):
                    run(root/'UnityEditor',project,stage,'apply',data,30)
                job=load(read(stage/'job-apply.json'))
                item=job['retireManifest'][0]
                self.assertIs(item['hasSourceIdentityEvidence'],source_only)
                self.assertEqual('sourceIdentityEvidence' in item,source_only)

    def test_recovery_restores_only_witnessed_deleted_before_images(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,selected,spec=fixture(root,source_only=True)
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
            root=Path(temp).resolve();project,selected,spec=fixture(root,source_only=True)
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

    def test_source_only_recovery_stays_required_if_import_restores_native_objects(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,selected,spec=fixture(root,source_only=True)
            planned=plan(project,spec,root/'preview');data=load(read(Path(planned['report'])))
            stage=root/'transaction';stage.mkdir();write_json(stage/'unity-plan.json',data)
            checkpoint=native_report(data,project);(stage/'before').mkdir()
            for item in data['retireManifest']:
                for path in (item['path'],item['metaPath']):
                    source=project/path;target=stage/'before'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
            write_json(stage/'journal.json',dict(status='complete',operation='assets.retire',planSha256=planned['planSha256']))
            write_json(stage/'native-apply.json',checkpoint)
            selected.unlink();Path(str(selected)+'.meta').unlink()

            def native_run(editor,target,transaction,mode,native_plan,timeout):
                self.assertTrue((target/'Assets/BeaverTools/Editor/BeaverNative.cs').is_file())
                report=native_report(native_plan,target)
                changed=dict(report['retiredAssets'][0],identityStatus='verified',nativeObjectCount=1,localIds=['new-native-id'])
                report['retiredAssets']=[changed]
                report['recoveredPaths']=checkpoint['deletedPaths']
                return report

            with patch('beaver.unity.editor_path',return_value=root/'UnityEditor'),patch('beaver.unity.native_lock'),patch('beaver.unity.run',side_effect=native_run):
                with self.assertRaises(BeaverError) as error:recover(stage,root/'UnityEditor',planned['planSha256'])
            self.assertEqual(error.exception.code,'ASSET_RETIRE_IDENTITY')
            self.assertEqual(load(read(stage/'journal.json'))['status'],'recovery-required')
            self.assertEqual(selected.read_bytes(),b'{"old":true}')
            self.assertTrue(Path(str(selected)+'.meta').is_file())
            self.assertFalse((project/'Assets/BeaverTools').exists())


if __name__=='__main__':unittest.main()
