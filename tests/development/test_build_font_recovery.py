"""Explicit reviewed recovery cannot generalize unknown post-exit source bytes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from grea.development.io import load,read,write_json,sha,encoded
from grea.development.unity import source_files
from grea.development.build_font_recovery import recover_reviewed,FIX11_IMPLEMENTATION
from grea.development.build_policy import certify_after_exit
from grea.development.errors import BeaverError
from . import test_build_policy as fixtures


class ReviewedFontRecoveryTests(unittest.TestCase):
    def fixture(self,root):
        project,stage,_,font=fixtures.BuildRecoveryGuardTests().transaction(root)
        plan=load(read(stage/'unity-plan.json'));plan['implementationSha256']=FIX11_IMPLEMENTATION;write_json(stage/'unity-plan.json',plan);expected=sha(encoded(plan))
        after=source_files(project)
        journal=dict(planSha256=expected,status='recovery-required',diagnostic=dict(code='BUILD_SOURCE_DRIFT'),after=after)
        write_json(stage/'journal.json',journal);write_json(stage/'process.json',dict(owned=True,exited=True,exitCode=0))
        review=dict(schemaVersion=1,contract='beaver-build-font-post-exit-recovery/1',transactionRoot=str(stage),planSha256=expected,sourceImplementationSha256=FIX11_IMPLEMENTATION,journalSha256=sha(read(stage/'journal.json')),processSha256=sha(read(stage/'process.json')),reviewReference='explicit-test-review',reason='Review exact recorded post-exit font change',files=[dict(path=font,beforeSha256=plan['before'][font]['sha256'],afterSha256=after[font]['sha256'])])
        path=root/'review.json';write_json(path,review)
        return project,stage,expected,font,path,plan

    def test_pinned_review_restores_without_editor_and_preserves_original_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,stage,expected,font,review,plan=self.fixture(root);journal=read(stage/'journal.json')
            with patch('grea.development.unity.native_lock'),patch('grea.development.unity.run') as native:
                result=recover_reviewed(stage,expected,review,root/'receipt')
                self.assertEqual(result['status'],'restored');self.assertFalse(result['artifactCertified']);native.assert_not_called()
            self.assertEqual(source_files(project),plan['before']);self.assertEqual(read(stage/'journal.json'),journal)

    def test_later_edit_corrupt_backup_unreviewed_drift_and_other_implementation_refused(self):
        for fault in ['later','backup','unrelated','implementation','evidence']:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve();project,stage,expected,font,review,plan=self.fixture(root)
                if fault=='later':(project/font).write_bytes(b'later user edit')
                elif fault=='backup':(stage/'before'/font).write_bytes(b'corrupt backup')
                elif fault=='unrelated':(project/'Assets/Main.unity').write_bytes(b'later scene edit')
                elif fault=='implementation':
                    d=load(read(review));d['sourceImplementationSha256']='0'*64;write_json(review,d)
                else:write_json(stage/'process.json',dict(owned=True,exited=False,exitCode=0))
                before=source_files(project)
                with patch('grea.development.unity.native_lock'),patch('grea.development.unity.run') as native:
                    with self.assertRaises(BeaverError):recover_reviewed(stage,expected,review,root/'receipt')
                    native.assert_not_called()
                self.assertEqual(source_files(project),before);self.assertFalse((root/'receipt').exists())

    def test_parent_exit_audit_rejects_native_claim_when_shutdown_changed_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,stage,expected,font,review,plan=self.fixture(root)
            report=dict(fontSourcesRestoredInProcess=True,fontSourcesRestored=True,fontInputs=[])
            with self.assertRaises(BeaverError) as caught:certify_after_exit(stage,plan,report,source_files(project),require_build=False)
            self.assertEqual(caught.exception.code,'BUILD_FONT_EXIT_AUDIT')
            (project/font).write_bytes((stage/'before'/font).read_bytes())
            result=certify_after_exit(stage,plan,report,source_files(project),require_build=False)
            self.assertEqual(result['sourceRestorationVerifiedBy'],'parent-after-editor-exit')
            write_json(stage/'process.json',dict(owned=True,exited=False,exitCode=0))
            with self.assertRaises(BeaverError):certify_after_exit(stage,plan,report,source_files(project),require_build=False)
