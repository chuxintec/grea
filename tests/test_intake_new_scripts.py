"""Compiler planning guards, independent of native execution tests."""
import tempfile
import unittest
from pathlib import Path
from beaver.intake import build_plan
from beaver.errors import BeaverError
from beaver.io import sha,write_json
from beaver.intake_native import _bind_watcher_before
from test_intake import _candidate,_project,_spec,_write_asset

GUID='4'*32
class NewScriptPlanTests(unittest.TestCase):
 def fixture(self,base):
  c=_candidate(base/'candidate',[('Assets/New.txt',b'guid: '+GUID.encode(),'1'*32),('Assets/Widget.cs',b'public class Widget : UnityEngine.MonoBehaviour {}',GUID)])
  t=_project(base/'target');s=_spec(c,additions=[dict(source='Assets/New.txt',target='Assets/Game/New.txt')]);s.update(schemaVersion=3,externalAssets=[],packageScripts=[],newScripts=[dict(source='Assets/Widget.cs',target='Assets/Runtime/Widget.cs',guid=GUID,sha256=sha((c/'Assets/Widget.cs').read_bytes()),metaSha256=sha((c/'Assets/Widget.cs.meta').read_bytes()),sourceType='Widget',sourceAssembly='SourceDomain',targetType='Widget',targetAssembly='Assembly-CSharp',baseType='UnityEngine.MonoBehaviour',baseAssembly='UnityEngine.CoreModule',localId=11500000,fields=[],reason='Frozen schema only')]);p=base/'spec.json';write_json(p,s);return c,t,s,p
 def error(self,code,fn,*args):
  with self.assertRaises(BeaverError) as caught:fn(*args)
  self.assertEqual(caught.exception.code,code)
 def test_exact_reviewed_source_in_internal_write_set_and_closure(self):
  with tempfile.TemporaryDirectory() as d:
   c,t,s,p=self.fixture(Path(d).resolve());x=build_plan(c,t,p);self.assertEqual(x['contract'],'beaver-additive-intake/3');self.assertEqual(len(x['additions']),2);self.assertEqual(len(x['newScripts']),1)
 def test_existing_guid_is_not_overwritten(self):
  with tempfile.TemporaryDirectory() as d:
   c,t,s,p=self.fixture(Path(d).resolve());_write_asset(t,'Assets/Existing.cs',b'existing',GUID);self.error('INTAKE_GUID_OCCUPIED',build_plan,c,t,p)
 def test_existing_path_is_not_overwritten(self):
  with tempfile.TemporaryDirectory() as d:
   c,t,s,p=self.fixture(Path(d).resolve());_write_asset(t,'Assets/Runtime/Widget.cs',b'existing','7'*32);self.error('INTAKE_DESTINATION',build_plan,c,t,p)
 def test_nondefault_assembly_ancestor_refused(self):
  with tempfile.TemporaryDirectory() as d:
   c,t,s,p=self.fixture(Path(d).resolve());_write_asset(t,'Assets/Runtime/Scope.asmdef',b'{"name":"Other"}','7'*32);self.error('INTAKE_NEW_SCRIPT_DOMAIN',build_plan,c,t,p)
 def test_reviewed_code_pin_required(self):
  with tempfile.TemporaryDirectory() as d:
   c,t,s,p=self.fixture(Path(d).resolve());s['newScripts'][0]['sha256']='0'*64;write_json(p,s);self.error('INTAKE_NEW_SCRIPT_PIN',build_plan,c,t,p)

class WatcherCheckpointTests(unittest.TestCase):
 def test_original_native_checkpoint_is_bound_without_learning_changed_bytes(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d).resolve();raw=b'{"original":"native before-image"}';(p/'intake-watchers-before.json').write_bytes(raw)
   j=dict(planSha256='a'*64);write_json(p/'native-code.json',dict(planSha256=j['planSha256'],written=[0],intakeWatcherBeforeSha256=sha(raw)))
   _bind_watcher_before(p,j);self.assertEqual(j['watcherBeforeSha256'],sha(raw))
   original=(p/'journal.json').read_bytes();(p/'intake-watchers-before.json').write_bytes(b'changed')
   with self.assertRaises(BeaverError) as caught:_bind_watcher_before(p,j)
   self.assertEqual(caught.exception.code,'INTAKE_WATCHER_CHECKPOINT');self.assertEqual((p/'journal.json').read_bytes(),original)
 def test_missing_checkpoint_cannot_cover_a_recorded_compiler_write(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d).resolve();j=dict(planSha256='a'*64);write_json(p/'native-code.json',dict(planSha256=j['planSha256'],written=[0]))
   with self.assertRaises(BeaverError):_bind_watcher_before(p,j)
   self.assertFalse((p/'journal.json').exists())
 def test_failure_before_any_code_write_does_not_invent_a_checkpoint(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d).resolve();j=dict(planSha256='a'*64);write_json(p/'native-code.json',dict(planSha256=j['planSha256'],written=[]))
   _bind_watcher_before(p,j);self.assertNotIn('watcherBeforeSha256',j);self.assertFalse((p/'journal.json').exists())
 def test_foreign_plan_checkpoint_refused_before_binding(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d).resolve();j=dict(planSha256='a'*64);write_json(p/'native-code.json',dict(planSha256='b'*64,written=[]))
   with self.assertRaises(BeaverError):_bind_watcher_before(p,j)
   self.assertFalse((p/'journal.json').exists())
if __name__=='__main__':unittest.main()
