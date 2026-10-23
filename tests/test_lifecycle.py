import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from grea.application import dispatch
from grea.change_contracts import validate
from grea.common import GreaError
from test_theme_assets import contract

class Lifecycle(unittest.TestCase):
 def test_default_unity_v1_and_new_modes_stay_bounded(self):
  old=dispatch('plan_workflow',dict(mode='recover',source_engine='cocos'))
  self.assertEqual(old['status'],'ok',old);self.assertEqual(old['result']['target_engine'],'unity');self.assertEqual(old['result']['task']['work_mode'],'faithful')
  self.assertEqual(dispatch('plan_workflow',dict(mode='recover',work_mode='feature'))['error']['code'],'MODE_CONFLICT')
  self.assertEqual(validate(contract())['scope'],'ui_ux')
  self.assertEqual(dispatch('plan_workflow',dict(mode='evolve',work_mode='feature',change_contract=contract()))['error']['code'],'INVALID_CHANGE_CONTRACT')
  self.assertEqual(dispatch('plan_workflow',dict(mode='feature',target_engine='none'))['error']['code'],'TARGET_REQUIRED')
  for mode in ('feature','tuning','prototype','operate'):
   r=dispatch('plan_workflow',dict(mode=mode));self.assertEqual(r['status'],'ok',r);self.assertFalse(r['result']['executed'])
  self.assertEqual(dispatch('plan_workflow',dict(mode='prototype',lifecycle_stage='release'))['error']['code'],'STAGE_CONFLICT')
 def test_v2_case_revision_baseline_and_unknown_version(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td).resolve();source=root/'baseline';source.write_text('own');(root/'candidate').write_text('draft')
   c=dict(schema_version=2,scope='feature',baseline_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),product_id='own',baseline_product_id='own',save_namespace='own',baseline_save_namespace='own',user_source='own-user-reference',objective='Add bounded timer',design=dict(state='candidate',reference='design',sha256='1'*64),allowed_changes=['timer'],invariants=['existing rewards'],verification=['timer cancel and reopen'],compatibility=dict(config='JSON content v2; stable IDs',save='schema v1 unchanged',protocol='unchanged',pending='preserve same operation ID'))
   self.assertEqual(validate(c)['scope'],'feature')
   with self.assertRaises(GreaError):validate(dict(c,schema_version=99))
   self.assertEqual(dispatch('init_case',dict(project_dir=str(root),source=str(source),mode='feature'))['error']['code'],'MISSING_CHANGE_CONTRACT')
   r=dispatch('init_case',dict(project_dir=str(root),source=str(source),mode='feature',change_contract=c));self.assertEqual(r['status'],'ok',r)
   r=dispatch('start_case_revision',dict(case_dir=str(root),candidate_root=str(root),candidate_files=['candidate'],platform='own',qa_profile='scoped'));self.assertEqual(r['status'],'ok',r)
   bad=dict(c,baseline_sha256='0'*64)
   r=dispatch('start_case_revision',dict(case_dir=str(root),candidate_root=str(root),candidate_files=['candidate'],platform='own',qa_profile='scoped',change_contract=bad));self.assertEqual(r['error']['code'],'CHANGE_BASELINE_MISMATCH')
   proto=dict(c,scope='prototype')
   with self.assertRaises(GreaError):validate(proto)
