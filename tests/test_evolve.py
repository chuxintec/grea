import hashlib,json,tempfile,unittest
from pathlib import Path
from grea.application import dispatch
from test_theme_assets import contract

class EvolveCases(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve()
        self.source=self.root/'source.bin';self.source.write_bytes(b'approved-old-baseline')
        (self.root/'Assets').mkdir();(self.root/'Assets/view.txt').write_text('candidate')
        self.contract=contract(hashlib.sha256(self.source.read_bytes()).hexdigest())
    def call(self,op,**kwargs):
        if op not in ('init_case','plan_workflow'):kwargs.setdefault('case_dir',str(self.root))
        return dispatch(op,kwargs)
    def init(self,**kwargs):return self.call('init_case',project_dir=str(self.root),source=str(self.source),mode='evolve',source_engine='cocos',**kwargs)
    def start(self,**kwargs):return self.call('start_case_revision',candidate_root=str(self.root),candidate_files=['Assets'],platform='own-test',qa_profile='isolated',**kwargs)
    def evidence(self,kind,**kwargs):
        p=self.root/(kind+'.txt');p.write_text(kind)
        return self.call('add_evidence',kind=kind,path=str(p),description='own fixture',**kwargs)['result']['evidence']['id']
    def test_plan_requires_bound_scope_and_case_cannot_drop_invariants(self):
        p=self.call('plan_workflow',mode='evolve',source_engine='cocos')
        self.assertEqual(p['status'],'ok',p);self.assertEqual(p['result']['next_decision'],'define_change_contract')
        self.assertIn('native',p['result']['required_dimensions'])
        self.assertEqual(self.init()['error']['code'],'MISSING_CHANGE_CONTRACT')
        bad=dict(self.contract,baseline_sha256='0'*64)
        self.assertEqual(self.init(change_contract=bad)['error']['code'],'CHANGE_BASELINE_MISMATCH')
        self.assertFalse((self.root/'.grea').exists())
        result=self.init(change_contract=self.contract);self.assertEqual(result['status'],'ok',result)
        self.assertEqual(self.start(required_dimensions_override=['rules','runtime','visual','identity'])['error']['code'],'REQUIRED_DIMENSION')
        result=self.start();self.assertEqual(result['status'],'ok',result)
    def test_old_rules_and_new_visual_roles_are_distinct(self):
        self.assertEqual(self.init(change_contract=self.contract)['status'],'ok');self.start()
        test=self.evidence('test_report');old=self.evidence('original_static')
        result=self.call('record_verification',dimension='rules',status='passed',evidence_ids=[test],note='not enough')
        self.assertEqual(result['error']['code'],'INSUFFICIENT_EVIDENCE')
        result=self.call('record_verification',dimension='rules',status='passed',evidence_ids=[old,test],note='own baseline oracle')
        self.assertEqual(result['status'],'ok',result)
        design=self.evidence('approved_design');runtime=self.evidence('candidate_runtime',run_instance='own-run')
        result=self.call('record_verification',dimension='visual',status='passed',evidence_ids=[design,runtime],note='candidate')
        self.assertEqual(result['error']['code'],'UNAPPROVED_DESIGN')
        approved=dict(self.contract,design={'state':'approved','reference':'own-design-v1','sha256':hashlib.sha256(b'approved_design').hexdigest()})
        result=self.start(change_contract=approved);self.assertEqual(result['status'],'ok',result)
        runtime=self.evidence('candidate_runtime',run_instance='own-run-2')
        # A different immutable artifact cannot satisfy the bound design digest.
        other=self.root/'different-design.txt';other.write_text('different design')
        wrong=self.call('add_evidence',kind='approved_design',path=str(other),description='different design')['result']['evidence']['id']
        refused=self.call('record_verification',dimension='visual',status='passed',evidence_ids=[wrong,runtime],note='wrong design')
        self.assertEqual(refused['error']['code'],'WRONG_DESIGN_EVIDENCE')
        result=self.call('record_verification',dimension='visual',status='passed',evidence_ids=[design,runtime],note='caller-declared approval, not authority')
        self.assertEqual(result['status'],'ok',result)
        self.assertEqual(self.call('case_status')['result']['declared_acceptance'],'incomplete')
