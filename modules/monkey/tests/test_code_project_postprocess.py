import fcntl,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_code_postprocess_plan import CodePostprocessPlanTests
from monkey import code_project_postprocess as project
from monkey.io import encoded,sha
from monkey.sources.compiled import ParseError

class ProjectPostprocessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.source=self.base/'source';self.source.mkdir()
  _,self.paths=CodePostprocessPlanTests().build_candidate(self.source)
  m=json.loads((self.source/'manifest.json').read_bytes());m.update(targetProfile='unity-6000.6.2f1-ugui',namespace='own-source',scopeMode='whole-input')
  for i,path in enumerate(self.paths):
   raw=(f'public class Class{i} {{ public dynamic '+('Outer'if i==0 else'Inner')+'() { return 1; }'+(' public static dynamic Value;'if i else'')+' }\n').encode();(self.source/path).write_bytes(raw)
   row=next(x for x in m['files']if x['path']==path);row.update(bytes=len(raw),sha256=sha(raw))
  (self.source/'manifest.json').write_bytes(encoded(m));self.pin=sha(encoded(m));self.codex=self.base/'own-cli';self.codex.write_text('#!/bin/sh\nexit 0\n');self.codex.chmod(0o755);self.output=self.base/'run'
  project.prepare(self.source,self.pin,self.output,max_files=1,codex=self.codex)
 def fake_prepare(self,source,paths,pin,out,task,**kw):
  out=Path(out);(out/'workspace').mkdir(parents=True)
  self.latest=list(paths)
  for path in paths:
   target=out/'workspace'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((Path(source)/path).read_bytes())
  (out/'request.json').write_bytes(encoded({'state':'finalized'}))
  return type('Prepared',(),{'output':out})()
 def fake_run(self,prepared,**kw):
  plan=json.loads((self.output/'plan.json').read_bytes());records={x['path']:x for x in plan['files']}
  results=[]
  for path in self.latest:
   p=prepared.output/'workspace'/path;p.write_text(p.read_text().replace('return 1','return 2'))
   results.append(dict(path=path,status='partial',summary='Reviewed the literal-return method and original source scope; dynamic domain remains explicit.',unresolved=['Own fixture result only'],membersReviewed=[x['methodId']for x in records[path]['functions']],originalLogicPreserved=True))
  changes=[dict(path=p,afterSha256=sha((prepared.output/'workspace'/p).read_bytes()))for p in self.latest]
  return dict(status='partial',fileResults=results,actualChanges=changes,blockingCondition=None,unexpectedPaths=[],workspaceIntegrityErrors=[],gitBoundary={'valid':True},sessionId='own-fixture',usage={},model='unknown',reasoningEffort='unknown',diffSha256='0'*64)
 def test_all_ready_batches_run_continuously_and_integrate_independent_copy(self):
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',side_effect=self.fake_run) as run:
   result=project.run(self.output)
  self.assertEqual(run.call_count,2);self.assertEqual(result['actuallyProcessed'],2);self.assertEqual(result['status'],'complete_with_partial')
  for p in self.paths:
   self.assertIn('return 1',(self.source/p).read_text());self.assertIn('return 2',(self.output/'UnityProject'/p).read_text())
 def test_superseded_strategy_remains_readable_but_cannot_resume_or_modify_reviews(self):
  state_path=self.output/'state.json';state=json.loads(state_path.read_bytes())
  state.update(status='paused',strategySupersededBy='architecture-first-v1');state_path.write_bytes(encoded(state));before=state_path.read_bytes()
  self.assertEqual(project.status(self.output)['strategySupersededBy'],'architecture-first-v1')
  with patch.object(project.worker,'prepare')as prepare,patch.object(project.worker,'run')as run:
   for operation in (project.run,project.resume,project.recheck):
    with self.assertRaises(ParseError)as error:operation(self.output)
    self.assertEqual(error.exception.code,'PROJECT_POSTPROCESS_SUPERSEDED')
  prepare.assert_not_called();run.assert_not_called();self.assertEqual(state_path.read_bytes(),before)
 def test_real_quota_condition_preserves_pending_scope_and_resume_continues(self):
  blocked=dict(status='failed',fileResults=[],blockingCondition='quota',unexpectedPaths=[],workspaceIntegrityErrors=[],gitBoundary={'valid':True})
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',return_value=blocked):
   first=project.run(self.output)
  self.assertEqual(first['status'],'blocked');self.assertEqual(first['actuallyProcessed'],0);self.assertEqual(first['fileStates']['pending'],1)
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',side_effect=self.fake_run):
   resumed=project.resume(self.output)
  self.assertEqual(resumed['actuallyProcessed'],2)
 def test_manual_change_is_not_overwritten_by_integrated_batch(self):
  path=self.paths[0];target=self.output/'UnityProject'/path;target.write_text('manual work')
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',side_effect=self.fake_run):
   with self.assertRaises(ParseError) as error:project.run(self.output)
  self.assertEqual(error.exception.code,'PROJECT_POSTPROCESS_DIRTY');self.assertEqual(target.read_text(),'manual work')
 def test_pause_before_start_preserves_all_work_and_explicit_resume_runs(self):
  receipt=project.request_pause(self.output)
  self.assertFalse(receipt['childStopped'])
  with patch.object(project.worker,'run') as worker:
   paused=project.run(self.output)
  self.assertEqual(paused['status'],'paused');self.assertEqual(paused['actuallyProcessed'],0);worker.assert_not_called()
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',side_effect=self.fake_run):
   result=project.resume(self.output)
  self.assertEqual(result['actuallyProcessed'],2)
 def test_configure_budgets_does_not_reset_attempt_history_and_busy_refuses(self):
  path=self.output/'state.json';state=json.loads(path.read_bytes());batch=next(iter(state['batches']));state['batches'][batch]['attempts']=1;path.write_bytes(encoded(state))
  project.configure(self.output,batch_seconds=3600,idle_seconds=900)
  self.assertEqual(json.loads(path.read_bytes())['batches'][batch]['attempts'],1)
  self.assertEqual(json.loads((self.output/'request.json').read_bytes())['batchSeconds'],3600)
  with (self.output/'run.lock').open('a+b')as lock:
   fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
   with self.assertRaises(ParseError)as error:project.configure(self.output,batch_seconds=100,idle_seconds=50)
   self.assertEqual(error.exception.code,'PROJECT_POSTPROCESS_BUSY')
   with self.assertRaises(ParseError)as error:project.resume(self.output)
   self.assertEqual(error.exception.code,'PROJECT_POSTPROCESS_BUSY')
  self.assertEqual(json.loads((self.output/'request.json').read_bytes())['batchSeconds'],3600)
 def test_operator_pause_is_checkpoint_not_consumed_fresh_attempt(self):
  paused=dict(status='partial',fileResults=[],blockingCondition='operator_pause',unexpectedPaths=[],workspaceIntegrityErrors=[],gitBoundary={'valid':True})
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',return_value=paused):
   result=project.run(self.output)
  self.assertEqual(result['status'],'paused');self.assertEqual(result['actuallyProcessed'],0)
  state=json.loads((self.output/'state.json').read_bytes());entry=state['batches'][result['currentBatch']]
  self.assertEqual(entry['status'],'checkpoint');self.assertEqual(entry['attempts'],1)
 def test_checkpoint_resume_reuses_same_attempt_and_exact_session(self):
  session='12345678-1234-4234-8234-123456789abc'
  def paused_worker(prepared,**kw):
   result=dict(status='partial',fileResults=[],blockingCondition='operator_pause',unexpectedPaths=[],workspaceIntegrityErrors=[],gitBoundary={'valid':True})
   (prepared.output/'request.json').write_bytes(encoded(dict(state='checkpoint',lastSessionId=session,resumeCount=0,childElapsedSeconds=10)))
   (prepared.output/'manifest.json').write_bytes(encoded(result));return result
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',side_effect=paused_worker):
   paused=project.run(self.output)
  batch=paused['currentBatch'];called=[]
  def continued_worker(prepared,**kw):
   if isinstance(prepared,Path):
    called.append(kw['session_id']);prepared=type('Prepared',(),{'output':prepared})()
    (prepared.output/'request.json').write_bytes(encoded(dict(state='finalized',resumeCount=1,childElapsedSeconds=20)))
   return self.fake_run(prepared,**kw)
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',side_effect=continued_worker):
   result=project.resume(self.output)
  state=json.loads((self.output/'state.json').read_bytes())
  self.assertEqual(called,[session]);self.assertEqual(state['batches'][batch]['attempts'],1)
  self.assertEqual(result['actuallyProcessed'],2)
 def test_reviewed_fields_and_proven_nested_functions_are_valid_without_missing_or_unrelated_ids(self):
  meta={'sourceSha256':'source-a','functions':[dict(methodId='outer',sourceBytes=dict(start=10,end=100))],
        'fields':[dict(fieldId='field@20',sourceBytes=dict(start=20,end=30))]}
  index={'source-a':[('nested',40,60),('outside',101,110)],'source-b':[('other-source',40,60)]}
  allowed=project._allowed_review_ids(meta,index)
  self.assertEqual(allowed,{'outer','nested','field@20'})
  result=dict(path='Own.cs',originalLogicPreserved=True,summary='Reviewed the nested callback and field initialization from the exact original source.',status='partial',membersReviewed=list(allowed))
  raw=b'public class Own {}'
  self.assertEqual(project._valid_file('Own.cs',raw,raw,result,meta,allowed),[])
  for ids in (['nested','field@20'],list(allowed)+['outside'],list(allowed)+['other-source']):
   self.assertTrue(project._valid_file('Own.cs',raw,raw,{**result,'membersReviewed':ids},meta,allowed))
 def test_completed_review_recheck_rejects_changed_payload_without_another_model(self):
  def invalid_review(prepared,**kw):
   result=self.fake_run(prepared,**kw)
   result['fileResults'][0]['membersReviewed'].pop()
   (prepared.output/'manifest.json').write_bytes(encoded(result));return result
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',side_effect=invalid_review):
   result=project.run(self.output)
  self.assertEqual(result['actuallyProcessed'],0)
  state=json.loads((self.output/'state.json').read_bytes());b=next(iter(state['batches'].values()));out=self.output/b['attemptRoots'][-1]
  target=out/'workspace'/b['files'][0];target.write_text(target.read_text()+'// manual change\n')
  with patch.object(project.worker,'run')as run:
   with self.assertRaises(ParseError)as error:project.recheck(self.output)
  self.assertEqual(error.exception.code,'PROJECT_POSTPROCESS_RESULT_CHANGED');run.assert_not_called()
 def test_completed_review_recheck_reuses_saved_results_and_preserves_attempts(self):
  def recorded_review(prepared,**kw):
   result=self.fake_run(prepared,**kw);(prepared.output/'manifest.json').write_bytes(encoded(result));return result
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',side_effect=recorded_review),patch.object(project,'_valid_file',return_value=['old validator rejected valid review metadata']):
   result=project.run(self.output)
  self.assertEqual(result['actuallyProcessed'],0)
  before=json.loads((self.output/'state.json').read_bytes())
  with patch.object(project.worker,'run')as run:
   result=project.recheck(self.output)
  run.assert_not_called();self.assertEqual(result['actuallyProcessed'],2)
  after=json.loads((self.output/'state.json').read_bytes())
  self.assertEqual([v['attempts']for v in before['batches'].values()],[v['attempts']for v in after['batches'].values()])
 def test_status_reports_resumed_child_without_mutating_checkpoint_or_counting_reviewed(self):
  path=self.output/'state.json';state=json.loads(path.read_bytes());batch=next(iter(state['batches']));entry=state['batches'][batch]
  entry.update(status='checkpoint',attemptRoots=['own-checkpoint']);state.update(status='running',currentBatch=batch)
  for p in entry['files']:state['files'][p]['status']='blocked'
  path.write_bytes(encoded(state));before=path.read_bytes();attempt=self.output/'own-checkpoint';attempt.mkdir()
  (attempt/'process.json').write_bytes(encoded(dict(state='running',pid=12345)))
  result=project.status(self.output)
  self.assertEqual(result['actuallyProcessed'],0);self.assertEqual(result['fileStates']['running'],1)
  self.assertEqual(result['batchStates']['running'],1);self.assertEqual(path.read_bytes(),before)
 def test_finish_current_pause_accepts_result_and_stops_before_next_attempt(self):
  def finish_then_pause(prepared,**kw):
   project.request_pause(self.output,finish_current=True)
   return self.fake_run(prepared,**kw)
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',side_effect=finish_then_pause)as run,patch.object(project.worker,'request_pause')as interrupt:
   result=project.run(self.output)
  self.assertEqual(result['status'],'paused');self.assertEqual(result['actuallyProcessed'],1)
  self.assertEqual(run.call_count,1);interrupt.assert_not_called()
  state=json.loads((self.output/'state.json').read_bytes())
  self.assertEqual([v['attempts']for v in state['batches'].values()],[1,0])
 def test_honest_semantic_limitations_and_extra_ids_stay_partial_without_false_claims(self):
  def honest_review(prepared,**kw):
   result=self.fake_run(prepared,**kw)
   for row in result['fileResults']:
    row.update(originalLogicPreserved=False,unresolved=['JavaScript coercion equivalence is unconfirmed.'])
    row['membersReviewed'].append('unproven-extra-id')
   return result
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',side_effect=honest_review):
   result=project.run(self.output)
  self.assertEqual(result['actuallyProcessed'],2);self.assertEqual(result['status'],'complete_with_partial')
  state=json.loads((self.output/'state.json').read_bytes())
  for row in state['files'].values():
   self.assertIs(row['originalLogicPreservedClaim'],False)
   self.assertNotIn('unproven-extra-id',row['membersReviewed']);self.assertIn('unproven-extra-id',row['reportedMembersReviewed'])
   self.assertEqual(row['reviewMetadataIssues'][0]['ids'],['unproven-extra-id'])
 def test_explicit_unprocessed_report_cannot_become_reviewed_partial(self):
  def blocked_review(prepared,**kw):
   result=self.fake_run(prepared,**kw)
   for row in result['fileResults']:row.update(status='blocked',originalLogicPreserved=False,unresolved=['Not analyzed.'])
   return result
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',side_effect=blocked_review):
   result=project.run(self.output)
  self.assertEqual(result['actuallyProcessed'],0)
 def test_invalid_ledger_reference_cannot_integrate_otherwise_valid_rows(self):
  def invalid_artifact(prepared,**kw):
   result=self.fake_run(prepared,**kw);result['fileResultsArtifactIssues']=['response references an unapproved ledger path'];return result
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',side_effect=invalid_artifact):
   result=project.run(self.output)
  self.assertEqual(result['actuallyProcessed'],0)
  for path in self.paths:self.assertIn('return 1',(self.output/'UnityProject'/path).read_text())
 def test_recheck_uses_completed_review_before_newer_prelaunch_pause(self):
  def recorded_review(prepared,**kw):
   result=self.fake_run(prepared,**kw);(prepared.output/'manifest.json').write_bytes(encoded(result));return result
  with patch.object(project.worker,'prepare',side_effect=self.fake_prepare),patch.object(project.worker,'run',side_effect=recorded_review),patch.object(project,'_valid_file',return_value=['old validator rejected review metadata']):
   project.run(self.output)
  path=self.output/'state.json';state=json.loads(path.read_bytes());batch=next(iter(state['batches']));entry=state['batches'][batch]
  latest=self.output/entry['attemptRoots'][-1]
  (latest/'manifest.json').write_bytes(encoded(dict(status='partial',blockingCondition='operator_pause',fileResults=[])))
  state.update(status='paused',currentBatch=batch);entry['status']='checkpoint';path.write_bytes(encoded(state))
  with patch.object(project.worker,'run')as model:
   result=project.recheck(self.output)
  model.assert_not_called();self.assertEqual(result['actuallyProcessed'],2)
  state=json.loads(path.read_bytes());record=state['files'][entry['files'][0]]
  self.assertEqual(record['lastAttempt'],entry['attemptRoots'][0]);self.assertEqual(state['batches'][batch]['attempts'],2)
 def test_saved_wrapped_ledger_revalidates_without_rewriting_and_hash_change_refuses(self):
  prepared=self.fake_prepare(self.source,[self.paths[0]],self.pin,self.base/'saved-ledger','own task')
  result=self.fake_run(prepared);raw=encoded(dict(fileResults=result['fileResults']));out=prepared.output;archive=out/'file-results-ledger-00.json';archive.write_bytes(raw)
  result.update(selected=[dict(path=self.paths[0])],fileResults=[],fileResultIssues=['old missing result'],fileResultsArtifact=dict(archivePath=archive.name,sha256=sha(raw),bytes=len(raw)))
  manifest=out/'manifest.json';manifest.write_bytes(encoded(result));before=manifest.read_bytes()
  replayed=project._load_saved_result(out)
  self.assertEqual(len(replayed['fileResults']),1);self.assertEqual(replayed['fileResultIssues'],[])
  self.assertEqual(replayed['ledgerRevalidatedFrom']['format'],'fileResults-wrapper')
  self.assertEqual(manifest.read_bytes(),before);self.assertEqual(archive.read_bytes(),raw)
  archive.write_bytes(raw+b'\n')
  with self.assertRaises(ParseError)as error:project._load_saved_result(out)
  self.assertEqual(error.exception.code,'PROJECT_POSTPROCESS_RESULT_CHANGED')
 def test_saved_invalid_ledger_shape_stays_isolated_and_unaccepted(self):
  out=self.base/'invalid-ledger';out.mkdir();raw=encoded(dict(unapproved=[]));archive=out/'file-results-ledger-00.json';archive.write_bytes(raw)
  result=dict(fileResults=[],selected=[],fileResultsArtifact=dict(archivePath=archive.name,sha256=sha(raw),bytes=len(raw)))
  (out/'manifest.json').write_bytes(encoded(result));replayed=project._load_saved_result(out)
  self.assertEqual(replayed['fileResults'],[]);self.assertTrue(replayed['fileResultsArtifactIssues'])
