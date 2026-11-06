import json
import os
import plistlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from monkey.io import write_json
from monkey.diagnostics import diagnose
from monkey.operations import doctor,space_preview


class OperationsTests(unittest.TestCase):
    def test_unparsed_body_class_and_reference_scope_do_not_become_writable(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();p=r/'typed.json'
            write_json(p,dict(source=dict(sha256='a'*64),files=[dict(id='0',name='CAB-source',externals=[dict(fileId='1',path='archive:/CAB-script/CAB-script')]),dict(id='1',name='CAB-script')],
                objects=[dict(file='1',pathId='10',type='MonoScript',status='parsed',data=dict(m_ClassName='Image',m_Namespace='UnityEngine.UI')),
                         dict(file='0',pathId='11',type='MonoBehaviour',status='unparsed',rawSha256='b'*64,
                              requiredSchemaIdentity=['2021.3.30f1','20','script','hash'],referenceCoverage='native-prefix-only',
                              nativePrefix=dict(fields=dict(m_Script=dict(fileId='1',pathId='10'))))]))
            before=p.read_bytes();result=diagnose(p,r/'out');d=json.loads(Path(result['report']).read_bytes())
            issue=next(x for x in d['issues'] if x['code']=='SOURCE_OBJECT_BODY_UNPARSED')
            self.assertEqual(issue['details']['scriptClass'],'UnityEngine.UI.Image');self.assertFalse(issue['details']['bodyWritable'])
            self.assertEqual(issue['source']['serializedFile'],'CAB-source');self.assertEqual(p.read_bytes(),before)
            self.assertFalse(d['coverage']['fullRecoveryCoverage']);self.assertFalse(d['coverage']['nativeExecuted'])

    def test_acquisition_404_runtime_and_shader_are_distinct_actions_and_credentials_are_redacted(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();p=r/'receipt.json'
            write_json(p,dict(files=[dict(path='missing',sourceKey='c'*64,status='unavailable',httpStatus=404)],
                skeletons=[dict(sourceId='spine',runtime='not_installed',skeletonVersion='3.8.99',skeletonPath='Assets/a.skel.bytes')],
                shaders=[dict(sourceId='shader',nativeShader=False),dict(sourceId='generated',nativeShader=True,nativeValidation='not_run',nativeProfile=dict(outputs=dict(shader='Assets/Candidate.shader')))],diagnostics=[dict(code='SOURCE_NOTE',message='https://cdn.example/a?token=never-copy')]))
            result=diagnose(p,r/'out');raw=Path(result['report']).read_text();d=json.loads(raw);codes={x['code']for x in d['issues']}
            self.assertTrue({'CDN_HTTP_404','SPINE_RUNTIME_REQUIRED','SHADER_TARGET_PROFILE_REQUIRED','SHADER_NATIVE_VALIDATION_PENDING'}<=codes)
            self.assertNotIn('never-copy',raw);self.assertNotIn('token=',raw)

    def test_bounded_diagnostics_never_report_complete_when_evidence_or_issues_are_omitted(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();p=r/'huge.json';p.write_text(' '*2000)
            result=diagnose(p,r/'large',max_document_bytes=1024);self.assertFalse(result['coverage']['complete'])
            write_json(p,dict(diagnostics=[dict(code='A',sourceId='one'),dict(code='B',sourceId='two')]))
            result=diagnose(p,r/'bounded',max_issues=1);self.assertFalse(result['coverage']['complete']);self.assertEqual(result['coverage']['omittedIssues'],1)

    def test_target_join_uses_full_source_identity_and_retains_byte_assurance(self):
        with tempfile.TemporaryDirectory()as temp:
            r=Path(temp).resolve();p=r/'typed.json';m=r/'mapping.json'
            write_json(p,dict(source=dict(sha256='a'*64),files=[dict(id='0',name='CAB')],objects=[dict(file='0',pathId='1',status='unparsed')]))
            target=dict(path='Assets/Exact.asset',guid='b'*32,sha256='c'*64)
            write_json(m,dict(sourceToTarget=[dict(source=dict(containerSha256='a'*64,file='CAB',pathId='1'),target=target)]))
            result=diagnose(p,r/'out',evidence=[m]);issue=json.loads(Path(result['report']).read_bytes())['issues'][0]
            self.assertEqual(issue['target'],target);self.assertIn('not-reverified',issue['targetAssurance'])
            write_json(m,dict(sourceToTarget=[dict(source=dict(containerSha256='other',file='CAB',pathId='1'),target=target)]))
            result=diagnose(p,r/'wrong-container',evidence=[m]);issue=json.loads(Path(result['report']).read_bytes())['issues'][0]
            self.assertIsNone(issue['target']);self.assertEqual(issue['targetAssurance'],'no-exact-target-in-selected-evidence')

    def test_doctor_reads_editor_bundle_without_launching_it(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();exe=r/'Unity.app/Contents/MacOS/Unity';exe.parent.mkdir(parents=True);exe.write_text('not executable')
            (exe.parent.parent/'Info.plist').write_bytes(plistlib.dumps(dict(CFBundleVersion='6000.6.2f1')))
            with patch('monkey.operations.platform.machine',return_value='test-architecture'), patch('monkey.operations.subprocess.run',side_effect=AssertionError('Editor must not launch')):
                result=doctor(r/'out',unity_editor=exe)
            self.assertEqual(next(x for x in result['checks']if x['name']=='unity')['status'],'pass')

    @unittest.skipIf(sys.platform=='win32','Symlink creation may require an unavailable Windows privilege')
    def test_doctor_keeps_the_explicit_venv_python_invocation_path(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();exe=r/'venv/bin/python';exe.parent.mkdir(parents=True);exe.symlink_to(sys.executable)
            result=type('Result',(),dict(returncode=0,stdout=json.dumps(dict(python='3.14.7',UnityPy='1.25.3'))))()
            with patch('monkey.operations.subprocess.run',return_value=result)as probe:doctor(r/'out',provider_python=exe)
            self.assertEqual(probe.call_args.args[0][0],str(exe))
            self.assertIn('-B',probe.call_args.args[0])

    def test_space_preview_preserves_current_assets_raw_evidence_manual_and_unknown_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();root=r/'outputs';root.mkdir();candidate=root/'candidate';candidate.mkdir()
            write_json(candidate/'manifest.json',dict(schemaVersion=1,targetProfile='cocos-3.8.8',files=[]))
            files=['candidate/Library/cache','candidate/Assets/Temp/manual','candidate/SourceRecovery/Library/raw','unknown/Library/user-data','candidate/Docs/manual']
            for f in files:
                p=root/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'original')
            result=space_preview(root,r/'preview');d=json.loads(Path(result['report']).read_bytes())
            reviewable={x['path']for x in d['rows']if not x['protected']}
            self.assertEqual(reviewable,{'candidate/Library'});self.assertEqual(result['deletedFiles'],0)
            self.assertTrue(all((root/f).read_bytes()==b'original'for f in files));self.assertFalse(d['deleteSupported'])
            lock=candidate/'Temp/UnityLockfile';lock.parent.mkdir();lock.touch()
            result=space_preview(root,r/'locked');self.assertEqual(result['reviewableCacheLogicalBytes'],0)

    def test_space_file_budget_is_explicit_and_symlinks_are_never_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();root=r/'outputs';root.mkdir();(root/'a').write_bytes(b'a');(root/'b').write_bytes(b'b')
            result=space_preview(root,r/'preview',max_files=1);self.assertEqual(result['status'],'incomplete-preview')
            self.assertEqual(result['filesScanned'],1)
            if sys.platform!='win32':
                (root/'link').symlink_to(r,target_is_directory=True)
                result=space_preview(root,r/'symlink');d=json.loads(Path(result['report']).read_bytes())
                self.assertEqual(d['skipped'][0]['reason'],'symlink-not-followed')
