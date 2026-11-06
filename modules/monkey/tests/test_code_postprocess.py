import json
import os
from pathlib import Path
import threading
import tempfile
import time
import unittest

import monkey.code_postprocess as postprocess
from monkey.code_postprocess import (_ledger_rows, _normalize_file_results,
                                     configure_checkpoint, prepare, request_pause, run)
from monkey.io import sha, encoded
from monkey.sources.compiled import ParseError


SESSION = '123e4567-e89b-42d3-a456-426614174000'


class CodePostprocessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.root = Path(self.temp.name)
        postprocess.GLOBAL_LOCK_PATH = self.root / 'postprocess.lock'
        postprocess.ACTIVE_PROCESS_PATH = self.root / 'postprocess.active.json'
        self.candidate = self.root / 'candidate'
        self.candidate.mkdir()
        code = b'public class Example { public int Value = 1; }\n'
        (self.candidate / 'Assets').mkdir()
        (self.candidate / 'Assets' / 'Example.cs').write_bytes(code)
        self.manifest = {
            'schemaVersion': 1, 'candidateId': 'synthetic-candidate',
            'files': [{'path': 'Assets/Example.cs', 'owner': 'generated',
                       'sha256': sha(code), 'bytes': len(code)}],
        }
        (self.candidate / 'manifest.json').write_bytes(encoded(self.manifest))
        self.manifest_hash = sha((self.candidate / 'manifest.json').read_bytes())
        self.codex = self.root / 'codex'
        self.output = self.root / 'revision'
        self.fake_cli('import sys\nsys.stdin.read()\n')

    def tearDown(self):
        for before in self.root.glob('*/before'):
            for path in before.rglob('*'):
                if path.is_dir(): path.chmod(0o700)
                elif path.is_file(): path.chmod(0o600)
            before.chmod(0o700)
        self.temp.cleanup()

    def fake_cli(self, body):
        script = '''#!/usr/bin/env python3
import sys
if '--version' in sys.argv:
    print('codex-cli synthetic-1')
    raise SystemExit(0)
''' + body
        self.codex.write_text(script, encoding='utf-8')
        self.codex.chmod(0o755)

    def make_prepared(self, **kwargs):
        return prepare(self.candidate, ['Assets/Example.cs'], self.manifest_hash,
                       self.output, 'Fix only mechanically clear C# issues.',
                       codex=self.codex, **kwargs)

    def architecture_inputs(self, files, *, contract=True):
        rows = []
        for relative, (content, owner) in files.items():
            path = self.candidate.joinpath(*relative.split('/'))
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = content if isinstance(content, bytes) else content.encode('utf-8')
            path.write_bytes(raw)
            rows.append({'path': relative, 'owner': owner, 'sha256': sha(raw), 'bytes': len(raw)})
        manifest = {'schemaVersion': 1, 'candidateId': 'architecture-seed-test', 'files': rows}
        manifest_path = self.candidate / 'manifest.json'
        manifest_path.write_bytes(encoded(manifest))
        self.manifest = manifest
        self.manifest_hash = sha(manifest_path.read_bytes())
        contract_path = self.candidate / 'architecture-contract.json'
        if contract:
            contract_path.write_bytes(encoded({'schemaVersion': 1, 'targetTypes': [],
                                               'ownership': [], 'sourceMappings': []}))
        elif contract_path.exists():
            contract_path.unlink()
        return contract_path

    def prepare_architecture(self, paths, output=None, **kwargs):
        return prepare(self.candidate, paths, self.manifest_hash,
                       output or self.output, 'Build the selected architecture seed capsule.',
                       context_files=kwargs.pop('context_files', ['architecture-contract.json']),
                       context_root=self.candidate, codex=self.codex,
                       architecture_stage=True, **kwargs)

    def test_large_architecture_seed_uses_existing_output_bound_without_loosening_legacy_input(self):
        relative='Analysis/Architecture/architecture.json';raw=b'{}'+b' '*(9*1024*1024)
        self.architecture_inputs({relative:(raw,'generated')})
        prepared=self.prepare_architecture([relative])
        request=json.loads((prepared.output/'request.json').read_bytes())
        self.assertEqual(request['selectedFileMaxBytes'],postprocess.WORKSPACE_FILE_BYTES)
        self.assertEqual(postprocess._source_integrity(request),[])
        self.assertEqual((prepared.workspace/relative).read_bytes(),raw)
        self.architecture_inputs({'Assets/Large.cs':(raw,'generated')})
        with self.assertRaises(ParseError):
            prepare(self.candidate,['Assets/Large.cs'],self.manifest_hash,self.root/'legacy','Review code.',codex=self.codex)

    def test_prepare_copies_only_selected_generated_cs_and_keeps_source_immutable(self):
        evidence = self.candidate / 'map.json'
        evidence.write_text('{"note":"context"}', encoding='utf-8')
        prepared = self.make_prepared(evidence_files=['map.json'])
        copied = prepared.workspace / 'Assets/Example.cs'
        self.assertEqual(copied.read_bytes(), (self.candidate / 'Assets/Example.cs').read_bytes())
        self.assertNotEqual(copied.stat().st_ino, (self.candidate / 'Assets/Example.cs').stat().st_ino)
        self.assertFalse((prepared.workspace / 'map.json').exists())
        self.assertEqual(sha((self.candidate / 'manifest.json').read_bytes()), self.manifest_hash)
        self.assertFalse(os.access(prepared.output / 'before/Assets/Example.cs', os.W_OK))
        self.assertTrue((prepared.workspace / '.git').is_dir())

    def test_rejects_manifest_drift_paths_and_non_generated_files(self):
        (self.candidate / 'manifest.json').write_bytes(encoded({**self.manifest, 'candidateId': 'changed'}))
        with self.assertRaises(ParseError):
            self.make_prepared()
        self.output = self.root / 'revision2'
        (self.candidate / 'manifest.json').write_bytes(encoded(self.manifest))
        self.manifest_hash = sha((self.candidate / 'manifest.json').read_bytes())
        with self.assertRaises(ParseError):
            prepare(self.candidate, ['../outside.cs'], self.manifest_hash,
                    self.root / 'revision2', 'task', codex=self.codex)
        with self.assertRaises(ParseError):
            prepare(self.candidate, ['manifest.json'], self.manifest_hash,
                    self.root / 'revision2', 'task', codex=self.codex)

    def test_cli_complete_records_real_diff_and_limits_scope(self):
        self.fake_cli(f'''import json, pathlib, sys
prompt = sys.stdin.read()
path = pathlib.Path('Assets/Example.cs')
path.write_text(path.read_text().replace('Value = 1', 'Value = 2'))
print(json.dumps({{"type":"thread.started","thread_id":"{SESSION}"}}), flush=True)
print(json.dumps({{"type":"turn.completed","model":"gpt-6-luna","reasoning_effort":"high","usage":{{"input_tokens":12,"output_tokens":3}}}}), flush=True)
response = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])
response.write_text(json.dumps({{"status":"complete","changedPaths":["Assets/Example.cs"],"unresolved":[],"summary":"synthetic"}}))
''')
        prepared = self.make_prepared()
        revision = run(prepared)
        self.assertEqual(revision['status'], 'complete')
        self.assertEqual(revision['fileResultsArtifactIssues'], [])
        self.assertEqual(revision['sessionId'], SESSION)
        self.assertEqual(revision['actualChanges'][0]['path'], 'Assets/Example.cs')
        self.assertIn('Value = 1', (self.output / 'changes.patch').read_text())
        self.assertEqual(revision['diffSha256'], sha((self.output / 'changes.patch').read_bytes()))
        self.assertTrue(revision['gitBoundary']['valid'])
        self.assertEqual(revision['model'], 'gpt-6-luna')
        self.assertEqual(revision['reasoningEffort'], 'high')
        self.assertEqual(revision['usage'], {'input_tokens': 12, 'output_tokens': 3})
        self.assertEqual((self.candidate / 'Assets/Example.cs').read_text(), 'public class Example { public int Value = 1; }\n')
        invocation = json.loads((self.output / 'invocation.json').read_text())
        args = invocation['command']
        self.assertIn('--sandbox', args)
        self.assertIn('workspace-write', args)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', args)

    def test_extra_file_turns_success_into_partial_and_is_recorded(self):
        self.fake_cli(f'''import json, pathlib, sys
pathlib.Path('extra.txt').write_text('unexpected')
response = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])
response.write_text(json.dumps({{"status":"complete","changedPaths":[],"unresolved":[],"summary":"synthetic"}}))
''')
        revision = run(self.make_prepared())
        self.assertEqual(revision['status'], 'partial')
        self.assertEqual(revision['unexpectedPaths'], ['extra.txt'])

    def test_source_hash_is_rechecked_after_cli(self):
        source = self.candidate / 'Assets/Example.cs'
        self.fake_cli(f'''import pathlib, sys
sys.stdin.read()
pathlib.Path({str(source)!r}).write_text('tampered')
''')
        revision = run(self.make_prepared())
        self.assertEqual(revision['status'], 'failed')
        self.assertEqual(revision['stopReason'], 'source-identity-changed')
        self.assertTrue(revision['sourceVerificationErrors'])

    def test_hardlink_is_not_accepted_as_a_revision(self):
        source = self.candidate / 'Assets/Example.cs'
        self.fake_cli(f'''import os, pathlib, sys
sys.stdin.read()
path = pathlib.Path('Assets/Example.cs')
path.unlink()
os.link({str(source)!r}, path)
''')
        revision = run(self.make_prepared())
        self.assertNotEqual(revision['status'], 'complete')
        self.assertTrue(any('hard link' in item for item in revision['workspaceIntegrityErrors']))

    def test_custom_codex_symlink_is_rejected(self):
        link = self.root / 'codex-link'
        link.symlink_to(self.codex)
        with self.assertRaises(ParseError):
            prepare(self.candidate, ['Assets/Example.cs'], self.manifest_hash,
                    self.root / 'linked-revision', 'task', codex=link)

    def test_project_batch_readonly_context_and_file_results(self):
        context = self.candidate / 'module-map.json'
        context.write_text('{"members":["Assembly.Example::OnStart"]}', encoding='utf-8')
        self.fake_cli(f'''import json, pathlib, sys
path = pathlib.Path('Assets/Example.cs')
path.write_text(path.read_text().replace('Value = 1', 'Value = 2'))
print(json.dumps({{"type":"turn.completed","usage":{{"input_tokens":4,"output_tokens":2}}}}),flush=True)
response=pathlib.Path(sys.argv[sys.argv.index('-o')+1])
response.write_text(json.dumps({{"status":"complete","changedPaths":["Assets/Example.cs"],"unresolved":[],"summary":"Reviewed module mapping and made a bounded source correction.","fileResults":[{{"path":"Assets/Example.cs","status":"processed","summary":"Reviewed source member OnStart and retained the original control flow while correcting the generated type reference.","unresolved":[],"membersReviewed":["Assembly.Example::OnStart"],"originalLogicPreserved":True}}]}}))
''')
        prepared = prepare(self.candidate, ['Assets/Example.cs'], self.manifest_hash,
                           self.output, 'Process the selected module.', codex=self.codex,
                           project_batch=True, context_files=['module-map.json'],
                           context_root=self.candidate, max_resumes=2)
        context_copy = prepared.workspace / '__Context/module-map.json'
        self.assertEqual(context_copy.read_text(), context.read_text())
        self.assertFalse(os.access(context_copy, os.W_OK))
        prompt = (self.output / 'prompt.txt').read_text()
        self.assertIn('__Context/module-map.json', prompt)
        self.assertNotIn('Assembly.Example::OnStart', prompt)
        self.assertNotIn('public class Example', prompt)
        response_schema = json.loads((self.output / 'output-schema.json').read_text())
        self.assertIn('fileResults', response_schema['required'])
        self.assertEqual(json.loads((self.output / 'request.json').read_text())['maxResumes'], 2)
        revision = run(prepared)
        self.assertEqual(revision['status'], 'complete')
        self.assertEqual(revision['fileResults'][0]['membersReviewed'], ['Assembly.Example::OnStart'])
        self.assertEqual(revision['fileResultsArtifactIssues'], [])
        self.assertEqual(revision['contextFiles']['__Context/module-map.json']['sha256'], sha(context.read_bytes()))
        self.assertEqual(json.loads((self.output / 'process.json').read_text())['state'], 'exited')

    def test_changed_context_is_detected_and_cannot_complete(self):
        context = self.candidate / 'map.json'; context.write_text('{"members":[]}', encoding='utf-8')
        self.fake_cli('import json,pathlib,sys\np=pathlib.Path("__Context/map.json"); p.chmod(0o600); p.write_text("tampered")\nr=pathlib.Path(sys.argv[sys.argv.index("-o")+1]); r.write_text(json.dumps({"status":"complete","changedPaths":["__Context/map.json"],"unresolved":[],"summary":"The selected source remained unchanged after review.","fileResults":[{"path":"Assets/Example.cs","status":"unchanged","summary":"Reviewed the only generated member and found its current source mapping already consistent.","unresolved":[],"membersReviewed":[],"originalLogicPreserved":True}]}))\n')
        prepared = prepare(self.candidate, ['Assets/Example.cs'], self.manifest_hash,
                           self.output, 'Inspect one generated file.', codex=self.codex,
                           project_batch=True, context_files=['map.json'], context_root=self.candidate)
        revision = run(prepared)
        self.assertEqual(revision['status'], 'partial')
        self.assertTrue(any('context bytes changed' in item for item in revision['workspaceIntegrityErrors']))

    def test_project_batch_missing_result_is_blocked_not_processed(self):
        self.fake_cli('import json, pathlib, sys\nresponse=pathlib.Path(sys.argv[sys.argv.index("-o")+1])\nresponse.write_text(json.dumps({"status":"complete","changedPaths":[],"unresolved":[],"summary":"No file results returned." ,"fileResults":[]}))\n')
        prepared = prepare(self.candidate, ['Assets/Example.cs'], self.manifest_hash,
                           self.output, 'Process the selected module.', codex=self.codex,
                           project_batch=True)
        revision = run(prepared)
        self.assertEqual(revision['status'], 'partial')
        self.assertEqual(revision['fileResults'][0]['status'], 'blocked')
        self.assertIn('not counted as processed', revision['fileResults'][0]['summary'])

    def test_project_result_ledger_keeps_response_small_and_is_archived_separately(self):
        result = {'path': 'Assets/Example.cs', 'status': 'processed',
                  'summary': 'Reviewed the generated member mapping and preserved the existing branch and mutation order.',
                  'unresolved': [], 'membersReviewed': ['Assembly.Example::Update'],
                  'originalLogicPreserved': True}
        ledger_bytes = encoded([result])
        self.fake_cli(f'''import json, pathlib, sys
path=pathlib.Path('Assets/Example.cs')
path.write_text(path.read_text().replace('Value = 1','Value = 2'))
ledger=pathlib.Path('__Reviews/file-results.json')
ledger.write_bytes({ledger_bytes!r})
response=pathlib.Path(sys.argv[sys.argv.index('-o')+1])
response.write_text(json.dumps({{"status":"complete","changedPaths":["Assets/Example.cs"],"unresolved":[],"summary":"Reviewed the selected source and preserved its logic.","fileResultsArtifact":"__Reviews/file-results.json"}}))
''')
        prepared = self.make_prepared(project_batch=True, project_result_ledger=True)
        request = json.loads((self.output / 'request.json').read_text())
        schema = json.loads((self.output / 'output-schema.json').read_text())
        self.assertTrue(request['projectResultLedger'])
        self.assertIn('fileResultsArtifact', schema['required'])
        self.assertNotIn('fileResults', schema['required'])
        prompt = (self.output / 'prompt.txt').read_text()
        self.assertIn('__Reviews/file-results.json', prompt)
        self.assertIn('same actual per-file analysis', prompt)
        revision = run(prepared)
        self.assertEqual(revision['status'], 'complete')
        self.assertEqual([row['path'] for row in revision['actualChanges']], ['Assets/Example.cs'])
        artifact = revision['fileResultsArtifact']
        self.assertEqual(artifact['workspacePath'], '__Reviews/file-results.json')
        self.assertEqual(artifact['sha256'], sha(ledger_bytes))
        self.assertEqual(artifact['bytes'], len(ledger_bytes))
        self.assertEqual((self.output / artifact['archivePath']).read_bytes(), ledger_bytes)
        self.assertEqual(revision['fileResults'][0]['membersReviewed'], ['Assembly.Example::Update'])

    def test_project_result_ledger_accepts_exact_file_results_wrapper(self):
        result = {'path': 'Assets/Example.cs', 'status': 'unchanged',
                  'summary': 'Reviewed the generated member mapping and found no mechanical correction needed.',
                  'unresolved': [], 'membersReviewed': ['Assembly.Example::Update'],
                  'originalLogicPreserved': True}
        wrapped = encoded({'fileResults': [result]})
        self.fake_cli(f'''import json, pathlib, sys
pathlib.Path('__Reviews/file-results.json').write_bytes({wrapped!r})
response=pathlib.Path(sys.argv[sys.argv.index('-o')+1])
response.write_text(json.dumps({{"status":"complete","changedPaths":[],"unresolved":[],"summary":"Reviewed the selected source.","fileResultsArtifact":"__Reviews/file-results.json"}}))
''')
        revision = run(self.make_prepared(project_batch=True, project_result_ledger=True))
        self.assertEqual(revision['status'], 'complete')
        self.assertEqual(revision['fileResults'][0]['path'], 'Assets/Example.cs')
        self.assertEqual(revision['fileResultsArtifact']['format'], 'fileResults-wrapper')
        self.assertEqual(_ledger_rows([result]), [result])
        self.assertEqual(_ledger_rows({'fileResults': [result]}), [result])
        with self.assertRaises(ParseError):
            _ledger_rows({'fileResults': [result], 'extra': True})

    def test_project_result_ledger_path_is_not_a_declared_code_change(self):
        result = {'path': 'Assets/Example.cs', 'status': 'unchanged',
                  'summary': 'Reviewed the generated member mapping and found no mechanical correction needed.',
                  'unresolved': [], 'membersReviewed': ['Assembly.Example::Update'],
                  'originalLogicPreserved': True}
        self.fake_cli(f'''import json, pathlib, sys
pathlib.Path('__Reviews/file-results.json').write_bytes({encoded([result])!r})
response=pathlib.Path(sys.argv[sys.argv.index('-o')+1])
response.write_text(json.dumps({{"status":"complete","changedPaths":["__Reviews/file-results.json"],"unresolved":[],"summary":"Reviewed the selected file.","fileResultsArtifact":"__Reviews/file-results.json"}}))
''')
        revision = run(self.make_prepared(project_batch=True, project_result_ledger=True))
        self.assertEqual(revision['status'], 'failed')
        self.assertIn('ledger artifact path must not appear in changedPaths', revision['fileResultIssues'])
        self.assertIn('ledger artifact path must not appear in changedPaths', revision['fileResultsArtifactIssues'])
        self.assertEqual(revision['actualChanges'], [])

    def test_project_result_ledger_rejects_symlink_and_extra_review_files(self):
        context = self.candidate / 'review-map.json'
        context.write_text('{"members":[]}', encoding='utf-8')
        self.fake_cli(f'''import json, pathlib, sys
reviews=pathlib.Path('__Reviews')
(reviews/'file-results.json').symlink_to(pathlib.Path('Assets/Example.cs'))
(reviews/'extra.json').write_text('{{}}')
response=pathlib.Path(sys.argv[sys.argv.index('-o')+1])
response.write_text(json.dumps({{"status":"complete","changedPaths":[],"unresolved":[],"summary":"Inspected the selected source file carefully.","fileResultsArtifact":"__Reviews/file-results.json"}}))
''')
        prepared = prepare(self.candidate, ['Assets/Example.cs'], self.manifest_hash,
                           self.output, 'Review selected source files.', codex=self.codex,
                           project_batch=True, project_result_ledger=True,
                           context_files=['review-map.json'], context_root=self.candidate)
        revision = run(prepared)
        self.assertNotEqual(revision['status'], 'complete')
        self.assertTrue(any('symbolic link' in item for item in revision['workspaceIntegrityErrors']))
        self.assertTrue(any('unselected path' in item for item in revision['workspaceIntegrityErrors']))
        self.assertTrue(revision['fileResultsArtifactIssues'])

    def test_malformed_project_result_ledger_is_archived_but_never_processed(self):
        raw = b'{not-json'
        self.fake_cli(f'''import json, pathlib, sys
pathlib.Path('__Reviews/file-results.json').write_bytes({raw!r})
response=pathlib.Path(sys.argv[sys.argv.index('-o')+1])
response.write_text(json.dumps({{"status":"complete","changedPaths":[],"unresolved":[],"summary":"Reviewed the selected source carefully.","fileResultsArtifact":"__Reviews/file-results.json"}}))
''')
        revision = run(self.make_prepared(project_batch=True, project_result_ledger=True))
        self.assertNotEqual(revision['status'], 'complete')
        self.assertEqual(revision['fileResults'], [{'path': 'Assets/Example.cs', 'status': 'blocked',
                         'summary': 'No per-file result was returned; not counted as processed.',
                         'unresolved': ['Missing per-file analysis result.'], 'membersReviewed': [],
                         'originalLogicPreserved': False}])
        artifact = revision['fileResultsArtifact']
        self.assertEqual(artifact['sha256'], sha(raw))
        self.assertEqual((self.output / artifact['archivePath']).read_bytes(), raw)
        self.assertTrue(revision['fileResultsArtifactIssues'])

    def test_missing_per_file_row_does_not_become_artifact_issue(self):
        second_code = b'public class ExtraExample { public int Value = 2; }\n'
        (self.candidate / 'Assets' / 'ExtraExample.cs').write_bytes(second_code)
        self.manifest['files'].append({'path': 'Assets/ExtraExample.cs', 'owner': 'generated',
                                       'sha256': sha(second_code), 'bytes': len(second_code)})
        (self.candidate / 'manifest.json').write_bytes(encoded(self.manifest))
        self.manifest_hash = sha((self.candidate / 'manifest.json').read_bytes())
        result = {'path': 'Assets/Example.cs', 'status': 'unchanged',
                  'summary': 'Reviewed the generated member mapping and found no mechanical correction needed.',
                  'unresolved': [], 'membersReviewed': ['Assembly.Example::Update'],
                  'originalLogicPreserved': True}
        self.fake_cli(f'''import json, pathlib, sys
pathlib.Path('__Reviews/file-results.json').write_bytes({encoded([result])!r})
response=pathlib.Path(sys.argv[sys.argv.index('-o')+1])
response.write_text(json.dumps({{"status":"partial","changedPaths":[],"unresolved":[],"summary":"Reviewed available source results.","fileResultsArtifact":"__Reviews/file-results.json"}}))
''')
        prepared = prepare(self.candidate, ['Assets/Example.cs', 'Assets/ExtraExample.cs'],
                           self.manifest_hash, self.output, 'Review both selected files.',
                           codex=self.codex, project_batch=True, project_result_ledger=True)
        revision = run(prepared)
        self.assertEqual(revision['fileResults'][0]['status'], 'unchanged')
        self.assertEqual(revision['fileResults'][1]['status'], 'blocked')
        self.assertTrue(any('missing file result' in item for item in revision['fileResultIssues']))
        self.assertEqual(revision['fileResultsArtifactIssues'], [])

    def test_project_result_ledger_requires_project_batch(self):
        with self.assertRaises(ParseError):
            self.make_prepared(project_result_ledger=True)

    def test_malformed_per_file_row_without_stable_ids_is_blocked_but_valid_partial_survives(self):
        selected = [{'path': 'Assets/NativeHelper.cs'}]
        malformed = [{'path': 'Assets/NativeHelper.cs', 'status': 'partial',
                      'summary': 'Reviewed helper but result is missing the required fields.',
                      'membersReviewed': [], 'originalLogicPreserved': False}]
        rows, issues, shape_ok = _normalize_file_results(malformed, selected)
        self.assertFalse(shape_ok)
        self.assertTrue(any('malformed file result' in issue for issue in issues))
        self.assertEqual(rows[0]['status'], 'blocked')
        self.assertEqual(rows[0]['membersReviewed'], [])
        self.assertIn('analysis was not accepted', rows[0]['summary'])

        valid_partial = [{'path': 'Assets/NativeHelper.cs', 'status': 'partial',
                          'summary': 'Reviewed helper behavior and found a concrete semantic difference in retry handling.',
                          'unresolved': ['Retry handling differs from the source behavior.'],
                          'membersReviewed': [], 'originalLogicPreserved': False}]
        rows, issues, shape_ok = _normalize_file_results(valid_partial, selected)
        self.assertTrue(shape_ok)
        self.assertEqual(rows[0]['status'], 'partial')
        self.assertFalse(rows[0]['originalLogicPreserved'])

    def test_safe_blocker_summary_only_uses_cli_error_events(self):
        self.fake_cli('import sys\nsys.stdin.read()\nprint("{\\\"type\\\":\\\"turn.failed\\\",\\\"error\\\":{\\\"message\\\":\\\"Unauthorized: do not expose this raw message\\\"}}", flush=True)\nraise SystemExit(1)\n')
        revision = run(self.make_prepared())
        self.assertEqual(revision['blockingCondition'], 'auth')
        self.assertNotIn('Unauthorized', revision['blocker']['safeSummary'])

    def test_blocker_classifier_ignores_tool_output(self):
        self.fake_cli('import sys\nsys.stdin.read()\nprint("{\\\"type\\\":\\\"item.completed\\\",\\\"item\\\":{\\\"type\\\":\\\"command_execution\",\\\"output\\\":\\\"quota exceeded\"}}", flush=True)\nraise SystemExit(1)\n')
        revision = run(self.make_prepared())
        self.assertIsNone(revision['blockingCondition'])

    def test_safe_blocker_summary_reads_only_prefixed_stderr_errors(self):
        self.fake_cli('import sys\nsys.stdin.read()\nprint("Error: rate limit reached; never expose this line", file=sys.stderr, flush=True)\nraise SystemExit(1)\n')
        revision = run(self.make_prepared())
        self.assertEqual(revision['blockingCondition'], 'quota')
        self.assertNotIn('rate limit reached', revision['blocker']['safeSummary'])
        self.assertTrue((self.output / 'stderr.log').is_file())

    def test_run_refuses_an_already_running_recorded_child_without_killing_it(self):
        prepared = self.make_prepared()
        (self.output / 'process.json').write_text(json.dumps({'state': 'running', 'pid': os.getpid()}))
        with self.assertRaises(ParseError) as error:
            run(prepared)
        self.assertEqual(error.exception.code, 'POSTPROCESS_CHILD_ACTIVE')
        self.assertEqual(json.loads((self.output / 'process.json').read_text())['pid'], os.getpid())

    def test_resume_requires_exact_recorded_session(self):
        self.fake_cli(f'''import json, pathlib, sys, time
if 'resume' in sys.argv:
    response = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])
    response.write_text(json.dumps({{"status":"partial","changedPaths":[],"unresolved":["synthetic"],"summary":"partial"}}))
else:
    print(json.dumps({{"type":"thread.started","thread_id":"{SESSION}"}}), flush=True)
    time.sleep(3)
''')
        prepared = self.make_prepared(timeout_seconds=4, no_progress_seconds=1)
        revision = run(prepared)
        self.assertEqual(revision['stopReason'], 'no-progress')
        self.assertEqual(json.loads((self.output / 'request.json').read_text())['state'], 'checkpoint')
        with self.assertRaises(ParseError):
            run(prepared, session_id='223e4567-e89b-42d3-a456-426614174000')
        request_path = self.output / 'request.json'
        legacy = json.loads(request_path.read_text())
        legacy.pop('runId')
        elapsed = legacy['childElapsedSeconds']
        resumes = legacy.get('resumeCount', 0)
        request_path.write_text(json.dumps(legacy))
        configure_checkpoint(prepared.output, timeout_seconds=30, no_progress_seconds=10)
        migrated = json.loads(request_path.read_text())
        self.assertEqual(migrated['identityMigration']['from'], 'legacy-no-runId')
        self.assertEqual(migrated['childElapsedSeconds'], elapsed)
        self.assertEqual(migrated.get('resumeCount', 0), resumes)
        resumed = run(prepared, session_id=SESSION)
        self.assertEqual(resumed['status'], 'partial')
        self.assertEqual(json.loads((self.output / 'invocation.json').read_text())['command'][2], 'resume')

    def test_exhausted_total_budget_keeps_checkpoint_but_cannot_resume(self):
        self.fake_cli(f'''import json,sys,time
print(json.dumps({{"type":"thread.started","thread_id":"{SESSION}"}}),flush=True)
time.sleep(3)
''')
        prepared=self.make_prepared(timeout_seconds=1,no_progress_seconds=1)
        revision=run(prepared)
        self.assertEqual(revision['stopReason'],'timeout')
        with self.assertRaises(ParseError) as error:
            run(prepared,session_id=SESSION)
        self.assertEqual(error.exception.code,'POSTPROCESS_TOTAL_BUDGET')
        self.assertEqual(json.loads((self.output/'request.json').read_text())['state'],'checkpoint')

    def test_cooperative_pause_waits_for_child_exit_then_exact_resume_consumes_control(self):
        self.fake_cli(f'''import json, pathlib, signal, sys, time
if 'resume' in sys.argv:
    response=pathlib.Path(sys.argv[sys.argv.index('-o')+1])
    response.write_text(json.dumps({{"status":"partial","changedPaths":[],"unresolved":["review pending"],"summary":"resumed safely"}}))
else:
    def finish(signum, frame):
        time.sleep(0.7)
        raise SystemExit(130)
    signal.signal(signal.SIGINT, finish)
    print(json.dumps({{"type":"thread.started","thread_id":"{SESSION}"}}),flush=True)
    while True: time.sleep(0.1)
''')
        prepared = self.make_prepared(timeout_seconds=60, no_progress_seconds=30)
        result = {}
        worker = threading.Thread(target=lambda: result.setdefault('revision', run(prepared)))
        worker.start()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                process = json.loads((self.output / 'process.json').read_text())
                if process.get('state') == 'running': break
            except (FileNotFoundError, json.JSONDecodeError): pass
            time.sleep(0.02)
        else: self.fail('synthetic Codex child did not start')
        receipt = request_pause(prepared.output)
        self.assertEqual(receipt['outcome'], 'pause_requested')
        worker.join(timeout=8)
        self.assertFalse(worker.is_alive(), 'pause must stop and reap the owned child')
        paused = result['revision']
        self.assertEqual(paused['outcome'], 'operator_paused')
        self.assertEqual(paused['blockingCondition'], 'operator_pause')
        self.assertEqual(paused['sessionId'], SESSION)
        control = json.loads((self.output / 'control.json').read_text())
        self.assertEqual(control['state'], 'acknowledged')
        self.assertEqual(json.loads((self.output / 'process.json').read_text())['state'], 'exited')

        before = json.loads((self.output / 'request.json').read_text())
        adjusted = configure_checkpoint(prepared.output, timeout_seconds=60, no_progress_seconds=20)
        after = json.loads((self.output / 'request.json').read_text())
        self.assertEqual(adjusted['outcome'], 'budget_configured')
        self.assertEqual(after['childElapsedSeconds'], before['childElapsedSeconds'])
        self.assertEqual(after.get('resumeCount', 0), before.get('resumeCount', 0))
        self.assertEqual(after.get('maxResumes', 1), before.get('maxResumes', 1))
        resumed = run(prepared, session_id=SESSION)
        self.assertEqual(resumed['status'], 'partial')
        self.assertEqual(json.loads((self.output / 'control.json').read_text())['state'], 'consumed')

    def test_prestart_pause_returns_typed_pause_without_spawning_child(self):
        prepared = self.make_prepared(project_batch=True, project_result_ledger=True)
        receipt = request_pause(prepared.output)
        self.assertEqual(receipt['outcome'], 'pause_requested')
        self.assertTrue(receipt['idempotent'] is False)
        revision = run(prepared)
        self.assertEqual(revision['outcome'], 'operator_paused')
        self.assertEqual(revision['blockingCondition'], 'operator_pause')
        self.assertFalse((self.output / 'process.json').exists())
        self.assertEqual(json.loads((self.output / 'control.json').read_text())['state'], 'acknowledged')
        self.assertIn('ledger not generated', revision['fileResultsArtifactIssues'][0])

    def test_legacy_prepared_revision_gets_stable_identity_without_counter_reset(self):
        prepared = self.make_prepared(max_resumes=2)
        request_path = self.output / 'request.json'
        request = json.loads(request_path.read_text())
        request.pop('runId')
        request['childElapsedSeconds'] = 17.25
        request['resumeCount'] = 1
        request_path.write_text(json.dumps(request))
        first = configure_checkpoint(prepared.output, timeout_seconds=90, no_progress_seconds=20)
        migrated = json.loads(request_path.read_text())
        second = configure_checkpoint(prepared.output, timeout_seconds=100, no_progress_seconds=20)
        self.assertEqual(first['runId'], second['runId'])
        self.assertEqual(migrated['identityMigration']['from'], 'legacy-no-runId')
        self.assertEqual(migrated['childElapsedSeconds'], 17.25)
        self.assertEqual(migrated['resumeCount'], 1)

    def test_pause_request_after_child_exit_is_safe_noop(self):
        self.fake_cli('import json,pathlib,sys\nr=pathlib.Path(sys.argv[sys.argv.index("-o")+1]); r.write_text(json.dumps({"status":"partial","changedPaths":[],"unresolved":["x"],"summary":"done"}))\n')
        prepared = self.make_prepared()
        run(prepared)
        receipt = request_pause(prepared.output)
        self.assertEqual(receipt['outcome'], 'pause_not_needed')

    def test_architecture_mode_allows_only_planned_seed_extensions_and_records_source_kind(self):
        files = {
            'Assets/Game/Domain/Board.cs': ('namespace Seed; public class Board {}', 'generated'),
            'Assets/Game/Config/items.json': ('{"items":[]}', 'generated'),
            'Assets/Game/Gameplay/Game.asmdef': ('{"name":"Seed.Gameplay"}', 'generated'),
            'Analysis/Architecture/target-types.json': ('{"targets":[]}', 'generated'),
            'Analysis/Mappings/source-map.json': ('{"mappings":[]}', 'generated'),
        }
        self.architecture_inputs(files)
        prepared = self.prepare_architecture(list(files))
        request = json.loads((prepared.output / 'request.json').read_text())
        self.assertFalse(request['projectBatch'])
        self.assertFalse(request['projectResultLedger'])
        self.assertEqual(request['architectureStage']['selectedSourceKind'], 'architecture-seed')
        self.assertEqual({row['sourceKind'] for row in request['selected']}, {'architecture-seed'})
        self.assertEqual(request['architectureStage']['contract']['path'], '__Context/architecture-contract.json')
        self.assertEqual(request['architectureStage']['contract']['version'], 1)
        self.assertEqual(json.loads((prepared.output / 'output-schema.json').read_text())['required'],
                         ['status', 'changedPaths', 'unresolved', 'summary'])
        self.assertEqual((prepared.workspace / '__Context/architecture-contract.json').stat().st_mode & 0o222, 0)

    def test_default_mode_still_rejects_planned_json_targets(self):
        files = {'Assets/Game/Config/items.json': ('{"items":[]}', 'generated')}
        self.architecture_inputs(files)
        with self.assertRaises(ParseError):
            prepare(self.candidate, list(files), self.manifest_hash, self.output,
                    'Review a planned JSON seed.', codex=self.codex)

    def test_architecture_mode_rejects_missing_contract_and_mixed_project_batch(self):
        files = {'Assets/Game/Domain/Board.cs': ('public class Board {}', 'generated')}
        self.architecture_inputs(files, contract=False)
        with self.assertRaises(ParseError):
            self.prepare_architecture(list(files), self.root / 'no-contract', context_files=[])
        self.architecture_inputs(files)
        with self.assertRaises(ParseError):
            self.prepare_architecture(list(files), self.root / 'mixed-batch', project_batch=True)
        with self.assertRaises(ParseError):
            self.prepare_architecture(list(files), self.root / 'mixed-ledger', project_result_ledger=True)

    def test_architecture_mode_rejects_unplanned_roots_extensions_and_non_generated_entries(self):
        cases = [
            {'Assets/Other/Board.cs': ('public class Board {}', 'generated')},
            {'Assets/Game/Notes.txt': ('notes', 'generated')},
            {'Assets/Game/Manual.cs': ('public class Manual {}', 'manual')},
        ]
        for index, files in enumerate(cases):
            with self.subTest(files=list(files)):
                self.architecture_inputs(files)
                with self.assertRaises(ParseError):
                    self.prepare_architecture(list(files), self.root / f'invalid-{index}')

    def test_architecture_prompt_uses_contract_without_legacy_name_or_marker_lock(self):
        files = {'Assets/Game/Gameplay/OrderService.cs':
                 ('// source marker: src-123\npublic class Function_001 {}', 'generated')}
        self.architecture_inputs(files)
        prepared = self.prepare_architecture(list(files))
        prompt = (prepared.output / 'prompt.txt').read_text()
        self.assertIn('architecture-contract.json', prompt)
        self.assertIn('architecture seed', prompt.lower())
        self.assertIn('Do not preserve old anonymous class names or source-function markers', prompt)
        self.assertNotIn('Preserve every existing source-function marker and exported declaration name exactly.', prompt)

    def test_architecture_mode_rechecks_source_and_contract_context_after_cli(self):
        files = {'Assets/Game/Domain/Board.cs': ('public class Board {}', 'generated')}
        contract_path = self.architecture_inputs(files)
        source_path = self.candidate / 'Assets/Game/Domain/Board.cs'
        original_source = source_path.read_bytes()
        self.fake_cli(f'''import json, pathlib, sys
if '--help' in sys.argv:
    print('usage: resume [SESSION_ID] [PROMPT] --json -o')
    raise SystemExit(0)
sys.stdin.read()
pathlib.Path({str(source_path)!r}).write_text('public class TamperedBoard {{}}')
response=pathlib.Path(sys.argv[sys.argv.index('-o')+1])
response.write_text(json.dumps({{"status":"complete","changedPaths":[],"unresolved":[],"summary":"Reviewed architecture seed and its contract."}}))
''')
        prepared = self.prepare_architecture(list(files))
        source_revision = run(prepared)
        self.assertEqual(source_revision['status'], 'failed')
        self.assertEqual(source_revision['stopReason'], 'source-identity-changed')
        source_path.write_bytes(original_source)

        self.output = self.root / 'revision-context-tamper'
        context_copy = self.output / 'workspace/__Context/architecture-contract.json'
        self.fake_cli(f'''import json, pathlib, sys
if '--help' in sys.argv:
    print('usage: resume [SESSION_ID] [PROMPT] --json -o')
    raise SystemExit(0)
sys.stdin.read()
context=pathlib.Path({str(context_copy)!r})
context.chmod(0o600)
context.write_text('{{"schemaVersion":1,"tampered":true}}')
response=pathlib.Path(sys.argv[sys.argv.index('-o')+1])
response.write_text(json.dumps({{"status":"complete","changedPaths":[],"unresolved":[],"summary":"Reviewed architecture seed and its contract."}}))
''')
        prepared = self.prepare_architecture(list(files), self.output)
        request = json.loads((self.output / 'request.json').read_text())
        self.assertEqual(postprocess._workspace_changes(prepared.workspace, request, request['workspaceBudgetBytes']), [])
        context_revision = run(prepared)
        self.assertNotEqual(context_revision['status'], 'complete')
        self.assertTrue(any('read-only context bytes changed' in issue
                            for issue in context_revision['workspaceIntegrityErrors']))


if __name__ == '__main__':
    unittest.main()
