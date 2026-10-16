import json
from pathlib import Path
import tempfile
import unittest
from grea.application import dispatch


class RevisionCases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'source.bin').write_bytes(b'original')
        (self.root / 'Assets').mkdir()
        (self.root / 'Assets/code.cs').write_text('version1')
        response = self.call('init_case', source=str(self.root/'source.bin'), project_dir=str(self.root), mode='fix', source_engine='unity')
        self.assertEqual(response['status'], 'ok', response)

    def call(self, operation, **kwargs):
        if operation != 'init_case': kwargs.setdefault('case_dir', str(self.root))
        return dispatch(operation, kwargs)

    def start(self, **kwargs):
        result = self.call('start_case_revision', candidate_root=str(self.root), candidate_files=['Assets'], platform='editor', qa_profile='own-test', **kwargs)
        self.assertEqual(result['status'], 'ok', result)
        return result['result']['revision']['id']

    def test_candidate_change_and_addition_invalidate_claims(self):
        self.start()
        (self.root/'Assets/code.cs').write_text('version2')
        self.assertEqual(self.call('case_status')['error']['code'], 'STALE_CANDIDATE')
        self.start()
        (self.root/'Assets/new.cs').write_text('new')
        self.assertEqual(self.call('case_status')['error']['code'], 'STALE_CANDIDATE')

    def test_revisions_keep_history_and_require_bound_runtime(self):
        first = self.start()
        for kind, dim in [('test_report','rules'), ('candidate_runtime','runtime')]:
            file=self.root/(kind+'.txt');file.write_text('fixture')
            result=self.call('add_evidence',kind=kind,path=str(file),description='fixture')
            evidence=result['result']['evidence']['id']
            reply=self.call('record_verification',dimension=dim,status='passed',evidence_ids=[evidence],note='review')
            if dim=='runtime':
                self.assertEqual(reply['error']['code'],'MISSING_RUN_INSTANCE')
                result=self.call('add_evidence',kind=kind,path=str(file),description='fixture',run_instance='editor-run-1')
                evidence=result['result']['evidence']['id']
                reply=self.call('record_verification',dimension=dim,status='passed',evidence_ids=[evidence],note='review')
            self.assertEqual(reply['status'],'ok',reply)
        self.assertEqual(self.call('case_status')['result']['declared_acceptance'],'ready_for_review')
        self.start()
        status=self.call('case_status')['result']
        self.assertEqual(status['declared_acceptance'],'incomplete')
        self.assertEqual(status['revision_count'],2)
        self.assertTrue((self.root/'.grea/revisions'/f'{first}.json').is_file())

    def test_unbound_case_cannot_accept_current_gameplay(self):
        file=self.root/'test.json';file.write_text('{}')
        evidence=self.call('add_evidence',kind='test_report',path=str(file),description='unbound')['result']['evidence']['id']
        response=self.call('record_verification',dimension='rules',status='passed',evidence_ids=[evidence],note='unbound')
        self.assertEqual(response['error']['code'],'MISSING_CANDIDATE_REVISION')

    def test_project_relocation_uses_relative_identities(self):
        self.start()
        target=self.root.with_name(self.root.name+'-moved')
        self.root.rename(target)
        self.addCleanup(lambda: __import__('shutil').rmtree(target,ignore_errors=True))
        self.root=target
        self.assertEqual(self.call('case_status')['result']['candidate_integrity'],'matched')

    def test_build_source_and_hash_budget(self):
        build=self.root/'build.json';build.write_text('{"build":"one"}')
        first=self.start(build_manifest=str(build),build_id='one')
        self.assertEqual(self.call('case_status',max_hash_bytes=1)['error']['code'],'RESOURCE_LIMIT')
        report=self.call('case_status')['result']['hash_audit'];self.assertTrue(report['complete'])
        build.write_text('{"build":"two"}')
        self.assertEqual(self.call('case_status')['error']['code'],'STALE_BUILD')
        self.start(build_manifest=str(build),build_id='two')
        (self.root/'source.bin').write_bytes(b'new original')
        self.assertEqual(self.call('case_status')['error']['code'],'STALE_SOURCE')

    def test_v1_case_migrates_append_only(self):
        from grea.common import digest
        path=self.root/'.grea/case.json';case=json.loads(path.read_text())
        case['schema_version']=1;case.pop('task');case.pop('case_id');case['case_id']='case_'+digest(case)
        path.write_text(json.dumps(case));original=path.read_bytes()
        self.assertEqual(self.call('case_status',max_hash_bytes=1)['error']['code'],'RESOURCE_LIMIT')
        artifact=self.root/'legacy.txt';artifact.write_text('legacy evidence')
        self.call('add_evidence',kind='test_report',path=str(artifact),description='legacy')
        # The source fits this budget; the cumulative source + evidence does not.
        self.assertEqual(self.call('case_status',max_hash_bytes=8)['error']['code'],'RESOURCE_LIMIT')
        self.assertEqual(self.call('case_status')['result']['hash_audit']['hashed_bytes'],23)
        self.assertEqual(self.call('case_status')['result']['declared_acceptance'],'incomplete')
        self.start()
        self.assertEqual(path.read_bytes(),original)
        self.assertEqual(self.call('case_status')['result']['candidate_integrity'],'matched')


if __name__ == '__main__': unittest.main()
