import hashlib,json,tempfile,unittest
from pathlib import Path
from grea.tools.monkey_bridge import collect,handoff,pinned
class MonkeyBridge(unittest.TestCase):
 def test_candidate_hashes_status_and_task_pool(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td).resolve();project=r/'UnityProject';(project/'Analysis').mkdir(parents=True)
   tasks=[dict(taskId=str(i),allowedPaths=['Assets/Game/']) for i in range(50)]
   docs={'resource-ledger.json':{},'code-index.json':{},'cocos-assets.json':{},'agent-work.json':dict(schemaVersion=1,tasks=tasks)}
   files=[]
   for name,value in docs.items():
    p=project/'Analysis'/name;p.write_text(json.dumps(value));files.append(dict(path='Analysis/'+name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size))
   m=project/'manifest.json';m.write_text(json.dumps(dict(schemaVersion=1,toolVersion='owned',targetProfile='unity-test',resultKind='candidate',files=files,validation=dict(editor='not_run'))))
   raw=dict(schemaVersion=1,toolVersion='owned',workflowStatus='needs_action',resultKind='candidate',projects=[dict(path='UnityProject',targetProfile='unity-test',manifestSha256=hashlib.sha256(m.read_bytes()).hexdigest(),coverage=dict(scope='local only'))])
   report=r/'conversion-result.json';report.write_text(json.dumps(raw))
   value=collect(r,'owned');self.assertEqual(value['status'],'needs_action');self.assertEqual(handoff(value)['detail_count'],50);self.assertEqual(len(handoff(value)['groups']),1);self.assertEqual(handoff(value)['agents_started'],0)
   with self.assertRaises(ValueError):collect(r,'wrong-version')
   raw['resultKind']='native';report.write_text(json.dumps(raw))
   with self.assertRaises(ValueError):collect(r,'owned')
   raw['resultKind']='candidate';report.write_text(json.dumps(raw));(project/'Analysis/code-index.json').write_text('changed')
   with self.assertRaises(ValueError):collect(r,'owned')
 def test_pin_and_module_evidence_writers_are_bound(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td).resolve();source=r/'source';source.write_text('owned');sha=hashlib.sha256(source.read_bytes()).hexdigest()
   config=r/'pin.json';config.write_text(json.dumps(dict(schema_version=1,version='owned',capabilities_sha256='0'*64,identity_files=[dict(path=str(source),sha256=sha)])));self.assertEqual(pinned(config)['version'],'owned')
   task=dict(project='P',taskId='one',allowedPaths=['Assets/Game/']);value=dict(status='needs_action',detail_tasks=[task,dict(task,taskId='two')]);module=dict(id='m',objective='owned',project='P',task_ids=['one'],writable_paths=['Assets/Game/Feature.cs'],invariants=['old'],verification=['affected'],evidence=[dict(path=str(source),sha256=sha)])
   plan=r/'modules.json'
   def check(modules):plan.write_text(json.dumps(dict(schema_version=1,modules=modules)));return handoff(value,plan)
   self.assertEqual(check([module])['groups'][0]['status'],'declared_module_not_executed')
   with self.assertRaises(ValueError):check([module,dict(module,id='other',task_ids=['two'])])
   with self.assertRaises(ValueError):check([dict(module,writable_paths=['ProjectSettings/Settings.asset'])])
   source.write_text('changed')
   with self.assertRaises(ValueError):pinned(config)
   with self.assertRaises(ValueError):check([module])
