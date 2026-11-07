# Adapted from monkey tests; MIT license retained.
import tempfile
import unittest
import shutil
from pathlib import Path
from unittest.mock import patch
from grea.development.io import write_json,read,load,sha
from .helpers import finish
from grea.development.adoption import preview,build_plan,prepare,commit_state,STATE
from grea.development.errors import BeaverError as ParseError

GUID='11111111111111111111111111111111'
GUID2='22222222222222222222222222222222'
PREFIX='Assets/Game/Content/Data/Test/'


def candidate(root,path='A.txt',content=b'old',guid=GUID,namespace='game'):
    root.mkdir();asset=root/(PREFIX+path);asset.parent.mkdir(parents=True);asset.write_bytes(content)
    Path(str(asset)+'.meta').write_text('fileFormatVersion: 2\nguid: '+guid+'\n')
    (root/'ProjectSettings').mkdir();(root/'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.6.2f1\n')
    (root/'Packages').mkdir();write_json(root/'Packages/manifest.json',{'dependencies':{}})
    finish(root,dict(schemaVersion=1,targetProfile='unity-6000.6.2f1-ugui',namespace=namespace,projectLayout='monkey-project/2.0.0',scopeMode='whole-input',diagnostics=[]))
    return root


class AdoptionTests(unittest.TestCase):
    def test_preview_move_preserves_unknown_files_and_retains_removed_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();b=candidate(w/'base');a=candidate(w/'after','B.txt');t=w/'target';shutil.copytree(b,t)
            human=t/'Assets/Game/Scripts/Human.cs';human.parent.mkdir(parents=True);human.write_bytes(b'human')
            result=preview(a,t,w/'plan',b);self.assertEqual(result['status'],'planned')
            p=load(read(w/'plan/adoption-plan.json'));self.assertEqual(p['operations'][0]['action'],'move');self.assertEqual(p['operations'][0]['guid'],GUID)
            self.assertEqual((t/(PREFIX+'A.txt')).read_bytes(),b'old');self.assertEqual(human.read_bytes(),b'human')
            changed=candidate(w/'different','Other.txt',guid=GUID2)
            p=build_plan(changed,t,b);self.assertEqual(len(p['retainedRemoved']),1)
            self.assertEqual((t/(PREFIX+'A.txt')).read_bytes(),b'old')

    def test_three_way_unchanged_incoming_keeps_local_edits_but_overlapping_changes_block(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();b=candidate(w/'base');a=candidate(w/'after',content=b'new');t=w/'target';shutil.copytree(b,t)
            (t/(PREFIX+'A.txt')).write_bytes(b'human')
            p=build_plan(b,t,b);self.assertFalse(p['operations']);self.assertFalse(p['conflicts'])
            p=build_plan(a,t,b);self.assertEqual(p['conflicts'][0]['reason'],'locally-modified')
            preview(a,t,w/'blocked',b)
            with self.assertRaises(ParseError):prepare(w/'blocked/adoption-plan.json',w/'execute')
            self.assertFalse((w/'execute').exists())

    def test_stale_plan_tamper_foreign_namespace_and_destination_collision_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();b=candidate(w/'base');a=candidate(w/'after','B.txt');t=w/'target';shutil.copytree(b,t)
            result=preview(a,t,w/'plan',b);(t/(PREFIX+'B.txt')).write_bytes(b'unknown')
            with self.assertRaises(ParseError):prepare(w/'plan/adoption-plan.json',w/'execute',result['planSha256'])
            self.assertEqual(build_plan(a,t,b)['conflicts'][0]['reason'],'occupied-destination')
            wrong=candidate(w/'wrong',namespace='another')
            with self.assertRaises(ParseError):build_plan(wrong,t,b)
            with self.assertRaises(ParseError):prepare(w/'plan/adoption-plan.json',w/'tamper','0'*64)

    def test_payload_staging_is_independent_and_commit_catches_unrelated_manual_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();b=candidate(w/'base');a=candidate(w/'after',content=b'new');t=w/'target';shutil.copytree(b,t)
            human=t/'Assets/human.txt';human.write_bytes(b'work');preview(a,t,w/'plan',b)
            stage,plan,journal=prepare(w/'plan/adoption-plan.json',w/'transaction')
            self.assertEqual((stage/'before/0/file').read_bytes(),b'old');self.assertNotEqual((stage/'after/0/file').stat().st_ino,(a/(PREFIX+'A.txt')).stat().st_ino)
            (t/(PREFIX+'A.txt')).write_bytes(b'new');human.write_bytes(b'later')
            with self.assertRaises(ParseError):commit_state(stage,plan,journal,{'status':'verified'})
            self.assertFalse((t/STATE).exists());self.assertEqual((stage/'before/0/file').read_bytes(),b'old')

    def test_saved_generation_supports_next_preview_and_rejects_a_stale_common_baseline(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();b=candidate(w/'base');a=candidate(w/'after',content=b'new');t=w/'target';shutil.copytree(b,t)
            preview(a,t,w/'plan',b);stage,plan,journal=prepare(w/'plan/adoption-plan.json',w/'transaction')
            (t/(PREFIX+'A.txt')).write_bytes(b'new');commit_state(stage,plan,journal,{'status':'verified'})
            p=build_plan(a,t);self.assertFalse(p['operations']);self.assertFalse(p['conflicts'])
            with self.assertRaises(ParseError):build_plan(a,t,b)

    def test_locally_moved_assets_and_duplicate_guid_are_not_silently_claimed(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();b=candidate(w/'base');a=candidate(w/'after','B.txt');t=w/'target';shutil.copytree(b,t)
            (t/(PREFIX+'A.txt')).rename(t/(PREFIX+'Human.txt'));(t/(PREFIX+'A.txt.meta')).rename(t/(PREFIX+'Human.txt.meta'))
            self.assertEqual(build_plan(a,t,b)['conflicts'][0]['reason'],'locally-moved')
            shutil.copyfile(t/(PREFIX+'Human.txt'),t/(PREFIX+'Dup.txt'));shutil.copyfile(t/(PREFIX+'Human.txt.meta'),t/(PREFIX+'Dup.txt.meta'))
            with self.assertRaises(ParseError):build_plan(a,t,b)

    def test_algorithm_change_and_manual_ownership_are_explicit_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();b=candidate(w/'base');a=candidate(w/'after',content=b'new');t=w/'target';shutil.copytree(b,t)
            preview(a,t,w/'plan',b)
            with patch('grea.development.adoption.algorithm_id',return_value='f'*64):
                with self.assertRaises(ParseError):prepare(w/'plan/adoption-plan.json',w/'transaction')
            manifest=load(read(a/'manifest.json'))
            for row in manifest['files']:
                if row['path']==PREFIX+'A.txt':row['owner']='manual'
            write_json(a/'manifest.json',manifest)
            self.assertEqual(build_plan(a,t,b)['conflicts'][0]['reason'],'non-generated-owner')

    def test_editor_lock_uses_executable_and_exact_project_arguments(self):
        from grea.development.adoption import native_lock
        import subprocess
        unity='/Applications/Unity Hub/Editor/6000.6.2f1/Unity.app/Contents/MacOS/Unity'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()/'Target with spaces';(root/'Temp').mkdir(parents=True)
            marker=root/'Temp/UnityLockfile';marker.write_text('marker')
            def run(rows,observed=None):
                with patch('subprocess.run',return_value=subprocess.CompletedProcess([],0,stdout=rows)), \
                     patch('grea.development.process_identity.snapshot',return_value=observed) as snapshot:
                    native_lock(root)
                    return snapshot.call_count
            # The caller, shell and launcher can all carry --project/editor-path.
            rows='12 /usr/bin/python3\n13 /bin/zsh\n14 /usr/bin/env\n'
            self.assertEqual(run(rows),0)
            observed={'status':'verified','executablePath':unity,'arguments':[unity,'-projectPath',str(root)]}
            with self.assertRaises(ParseError) as error:run('20 '+unity,observed)
            self.assertEqual(error.exception.code,'ADOPT_EDITOR_BUSY')
            # A path in an unrelated flag, or a prefix-sharing project, is not this project.
            observed['arguments']=[unity,'-projectPath',str(root)+'-other','-logFile',str(root)+'/Editor.log']
            self.assertEqual(run('20 '+unity,observed),1)
            observed['arguments']=[unity,'-projectPath='+str(root)]
            with self.assertRaises(ParseError) as error:run('20 '+unity,observed)
            self.assertEqual(error.exception.code,'ADOPT_EDITOR_BUSY')
            for args in [[unity],[unity,'-projectPath','relative'],[unity,'-projectPath',str(root),'-projectPath',str(root)+'-other']]:
                observed['arguments']=args
                with self.assertRaises(ParseError) as error:run('20 '+unity,observed)
                self.assertEqual(error.exception.code,'ADOPT_EDITOR_STATE_UNKNOWN')
            for status in ['unknown','missing']:
                observed={'status':status}
                if status=='missing':run('20 '+unity,observed)
                else:
                    with self.assertRaises(ParseError) as error:run('20 '+unity,observed)
                    self.assertEqual(error.exception.code,'ADOPT_EDITOR_STATE_UNKNOWN')
            # PID reuse or executable mismatch remains unknown, never a stale marker clearance.
            with self.assertRaises(ParseError):run('20 '+unity,{'status':'verified','executablePath':'/usr/bin/python3'})
            with self.assertRaises(ParseError):run('malformed')
            self.assertEqual(marker.read_text(),'marker')

    def test_dependencies_and_settings_drift_block_before_an_editor_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();b=candidate(w/'base');a=candidate(w/'after');t=w/'target';shutil.copytree(b,t)
            write_json(t/'Packages/manifest.json',{'dependencies':{'own.package':'1.0.0'}})
            preview(a,t,w/'plan',b)
            write_json(t/'Packages/manifest.json',{'dependencies':{'own.package':'2.0.0'}})
            with self.assertRaises(ParseError):prepare(w/'plan/adoption-plan.json',w/'execute')
            write_json(a/'Packages/manifest.json',{'dependencies':{'required.package':'1.0.0'}})
            finish(a,dict(schemaVersion=1,targetProfile='unity-6000.6.2f1-ugui',namespace='game',projectLayout='monkey-project/2.0.0',scopeMode='whole-input',diagnostics=[]))
            self.assertTrue(any(c['reason']=='package-requirement' for c in build_plan(a,t,b)['conflicts']))

    def test_explicit_unity_source_lineage_survives_new_package_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();b=candidate(w/'base');a=candidate(w/'after');t=w/'target';shutil.copytree(b,t)
            for root,digest in [(b,'a'*64),(a,'b'*64)]:
                m=load(read(root/'manifest.json'));m.pop('namespace');m['source']={'sha256':digest};m['targetVersion']='6000.6.2f1';m['sourceProfile']='unityfs-unitypy-1.25.3-assetripper-2.0.0';write_json(root/'recovery-manifest.json',m);(root/'manifest.json').unlink()
            with self.assertRaises(ParseError):build_plan(a,t,b)
            p=build_plan(a,t,b,lineage='stable-game');self.assertEqual(p['namespace'],'stable-game');self.assertFalse(p['conflicts'])


class ParentSpellingTests(unittest.TestCase):
    def fixture(self,root):
        base=candidate(root/'base');incoming=candidate(root/'incoming','B.txt',guid=GUID2)
        target=root/'target';shutil.copytree(base,target)
        directory=incoming/'Assets/Game/Content/Data/Test'
        directory.rename(directory.with_name('temporary'))
        directory.with_name('temporary').rename(directory.with_name('test'))
        manifest=load(read(incoming/'manifest.json'))
        for row in manifest['files']:row['path']=row['path'].replace('/Test/','/test/')
        write_json(incoming/'manifest.json',manifest)
        return base,incoming,target

    def test_plan_rejects_an_alias_of_an_existing_parent_before_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            base,incoming,target=self.fixture(Path(temp).resolve())
            plan=build_plan(incoming,target,base)
            self.assertEqual(plan['conflicts'][0]['reason'],'existing-parent-path-spelling')
            self.assertFalse(plan['operations'])
            self.assertFalse((target/(PREFIX+'B.txt')).exists())

    def test_legacy_finalization_keeps_actual_parent_and_requires_exact_bytes(self):
        for tamper in (False,True):
            with self.subTest(tamper=tamper),tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve();base,incoming,target=self.fixture(root)
                # Reproduce an immutable plan made before the parent spelling guard.
                with patch('grea.development.adoption.canonical_existing_parent',side_effect=lambda path,parents:path):
                    preview(incoming,target,root/'plan',base)
                stage,plan,journal=prepare(root/'plan/adoption-plan.json',root/'transaction')
                for suffix in ('','.meta'):
                    shutil.copy2(incoming/(PREFIX.replace('/Test/','/test/')+'B.txt'+suffix),target/(PREFIX+'B.txt'+suffix))
                with self.assertRaises(ParseError):commit_state(stage,plan,journal,{'status':'verified'})
                if tamper:
                    (target/(PREFIX+'B.txt')).write_bytes(b'later human edit')
                    with self.assertRaises(ParseError):commit_state(stage,plan,journal,{'status':'verified'},canonicalize_existing_parents=True)
                    self.assertFalse((target/STATE).exists())
                else:
                    commit_state(stage,plan,journal,{'status':'verified'},canonicalize_existing_parents=True)
                    state=load(read(target/STATE));item=state['generation']['guid:'+GUID2]
                    self.assertEqual(item['path'],PREFIX+'B.txt')
                    self.assertEqual(item['file']['path'],PREFIX+'B.txt')
                    self.assertEqual(item['file']['owner'],'generated')
                    self.assertEqual(state['resolvedTargetPaths'],{PREFIX.replace('/Test/','/test/')+'B.txt':PREFIX+'B.txt'})

    def test_parent_resolution_never_changes_the_filename_or_new_directories(self):
        from grea.development.adoption import existing_parent_spellings,canonical_existing_parent
        parents=existing_parent_spellings({'Assets/Existing/old.txt':{}})
        self.assertEqual(canonical_existing_parent('Assets/existing/New/B.TXT',parents),'Assets/Existing/New/B.TXT')
        with self.assertRaises(ParseError):existing_parent_spellings({'Assets/Existing/a':{},'Assets/existing/b':{}})


class FinalizeGuardTests(unittest.TestCase):
    def test_incomplete_rewritten_or_superseded_receipts_never_start_editor(self):
        from grea.development import adoption_native
        from grea.development.output_limits import digest_file
        for fault in ('partial','wrong-helper','candidate-drift','later-state'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve();base=candidate(root/'base');incoming=candidate(root/'incoming',content=b'new');target=root/'target';shutil.copytree(base,target)
                preview(incoming,target,root/'plan',base);stage,plan,journal=prepare(root/'plan/adoption-plan.json',root/'transaction')
                journal.update(state='recovery-required',processExited=True,helperSha256=digest_file(Path(adoption_native.__file__).parent/'targets/BeaverAdoption.cs'))
                report=dict(status='verified',planSha256=journal['planSha256'],assets=[dict(index=0)])
                write_json(stage/'native-apply.json',dict(report,status='running') if fault=='partial' else report)
                write_json(stage/'native-verify.json',report)
                if fault=='wrong-helper':journal['helperSha256']='0'*64
                write_json(stage/'journal.json',journal)
                if fault=='candidate-drift':(incoming/(PREFIX+'A.txt')).write_bytes(b'changed')
                if fault=='later-state':write_json(target/STATE,dict(later=True))
                editor=root/'Unity';editor.touch()
                with patch.object(adoption_native,'run_child') as run:
                    with self.assertRaises(ParseError):adoption_native.finalize(stage,editor)
                    run.assert_not_called()
                self.assertFalse((target/adoption_native.HELPER_ROOT).exists())
