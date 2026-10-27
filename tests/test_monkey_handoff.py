import json,hashlib,tempfile,unittest
from pathlib import Path
from grea.artifacts import inspect_target
from grea.tools.monkey_bridge import collect_handoff
class BulkHandoff(unittest.TestCase):
 def fixture(self,r,category='prefab'):
  source=r/'source';source.mkdir();(source/'one').write_text('owned logical asset')
  inv=r/'inventory.json';inv.write_text(json.dumps(inspect_target(source)))
  project=r/'export/project';(project/'Assets').mkdir(parents=True);(project/'Packages').mkdir();(project/'ProjectSettings').mkdir();(project/'Packages/manifest.json').write_text('{}');(project/'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.6.2f1');(project/'README.md').write_text('Continue business from evidence; no original script execution')
  self.sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
  self.ref=lambda p,base:dict(path=str(p.relative_to(base)),sha256=self.sha(p))
  file=project/('Assets/one.prefab' if category=='prefab' else 'Assets/image.png');file.write_text('Synthetic native declaration; not an executed Editor test')
  c=dict(schema_version=1,provider_version='owned',target_engine='unity',source_inventory=self.ref(inv,r),project_path='project',assets=[dict(source_id='owned-one',category=category,source_files=['one'],disposition='native',outputs=[self.ref(file,project)],reason='')],entry=self.ref(project/'README.md',project),native_check=None);path=r/'contract.json';return source,project,c,path
 def check(self,r,c,p):p.write_text(json.dumps(c));return collect_handoff(r/'export','owned',p)
 def test_catalog_media_and_completed_cannot_promote_source_graph(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td).resolve();source,project,c,p=self.fixture(r);v=self.check(r,c,p);self.assertFalse(v['handoff_ready']);self.assertIn('native_import_compile_not_verified',v['issues'])
   c['assets'][0]['disposition']='retained';c['assets'][0]['reason']='lookup only; completed report irrelevant';v=self.check(r,c,p);self.assertFalse(v['handoff_ready']);self.assertIn('source_graph_not_native:owned-one',v['issues'])
   old=project/'Assets/one.prefab';lookup=project/'Assets/lookup.json';old.rename(lookup);c['assets'][0].update(disposition='native',outputs=[self.ref(lookup,project)],reason='');v=self.check(r,c,p);self.assertFalse(v['handoff_ready']);self.assertIn('source_graph_not_native:owned-one',v['issues'])
 def test_bound_receipt_is_not_business_or_independent_engine_proof(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td).resolve();source,project,c,p=self.fixture(r,'texture');receipt=r/'native.json';receipt.write_text(json.dumps(dict(schema_version=1,target_engine='unity',import_status='pass',compile_status='pass',artifacts=[self.ref(f,project) for f in project.rglob('*') if f.is_file()])));c['native_check']=self.ref(receipt,r);v=self.check(r,c,p);self.assertTrue(v['handoff_ready']);self.assertEqual(v['business_complete'],'not_proven');self.assertEqual(v['all_scope_export'],'not_executed_by_handoff_audit');self.assertNotIn('prefab',v['logical_asset_counts'])
   (project/'Assets/new.cs').write_text('Changed after native receipt')
   with self.assertRaises(ValueError):self.check(r,c,p)
 def test_all_input_dispositions_and_source_bytes_are_required(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td).resolve();source,project,c,p=self.fixture(r);c['assets'][0]['source_files']=['missing']
   with self.assertRaises(ValueError):self.check(r,c,p)
   c['assets'][0]['source_files']=['one'];(source/'new').write_text('Not in inventory')
   with self.assertRaises(ValueError):self.check(r,c,p)
 def test_plan_routes_bulk_first_without_claiming_execution(self):
  from grea.application import dispatch
  for target in ('unity','cocos'):
   v=dispatch('plan_workflow',dict(mode='recover',source_engine='cocos',target_engine=target));self.assertEqual(v['status'],'ok',v);p=v['result'];self.assertEqual(p['initial_project_pipeline']['export_owner'],'monkey');self.assertEqual(p['initial_project_pipeline']['all_scope_export'],'pinned_monkey_0_4_0_pipeline');self.assertFalse(p['steps'][0]['executed']);self.assertNotIn('cocos_convert',[t for step in p['steps'] for t in step['tool_ids']])
  p=dispatch('plan_workflow',dict(mode='fix',source_engine='unity'))['result'];self.assertNotIn('initial_project_pipeline',p)
