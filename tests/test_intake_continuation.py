import json,tempfile,unittest
from pathlib import Path
from beaver.intake_continuation import connect

class ContinuationTests(unittest.TestCase):
 def test_plan_does_not_invent_future_target_or_approve_partial_source(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp).resolve();mapping=root/'mapping.json';spec=root/'spec.json';mapping.write_text('{}');spec.write_text('{}')
   r=connect(root,candidate=root/'candidate',manifest=dict(native='partial',diagnostics=['source gate']),manifest_sha='1'*64,target=root/'target',mapping=mapping,spec=spec,consumption=dict(status='blocked',error=dict(code='INTAKE_GUID_OCCUPIED')))
   d=json.loads(Path(r['path']).read_text());ids={s['id'] for s in d['stages']}
   self.assertTrue(all(set(s.get('dependsOn',[]))<=ids for s in d['stages']))
   self.assertEqual(d['formalAdoption'],'not_run');self.assertEqual(d['sourceAcceptance'],'not_promoted');self.assertFalse(d['targetWrites'])
   self.assertEqual(d['stages'][0]['status'],'required_before_project_writes')
   self.assertFalse((root/'target').exists())
