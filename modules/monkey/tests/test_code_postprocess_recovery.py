import json
import os
from pathlib import Path
import tempfile
import unittest

import monkey.code_postprocess as postprocess
from monkey.code_postprocess import prepare, recover_completed
from monkey.io import encoded, sha


class CodePostprocessRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.root = Path(self.temp.name)
        postprocess.GLOBAL_LOCK_PATH = self.root / 'postprocess.lock'
        postprocess.ACTIVE_PROCESS_PATH = self.root / 'postprocess.active.json'
        self.candidate = self.root / 'candidate'
        (self.candidate / 'Assets').mkdir(parents=True)
        source = b'public class Example { public int Value = 1; }\n'
        (self.candidate / 'Assets/Example.cs').write_bytes(source)
        self.manifest = {'schemaVersion': 1, 'candidateId': 'recovery-test',
                         'files': [{'path': 'Assets/Example.cs', 'owner': 'generated',
                                    'sha256': sha(source), 'bytes': len(source)}]}
        (self.candidate / 'manifest.json').write_bytes(encoded(self.manifest))
        self.manifest_hash = sha((self.candidate / 'manifest.json').read_bytes())
        self.codex = self.root / 'codex'
        self.codex.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
        self.codex.chmod(0o755)
        self.output = self.root / 'revision'
        (self.candidate / 'context.txt').write_text('Pinned read-only context.', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def make_prepared(self):
        return prepare(self.candidate, ['Assets/Example.cs'], self.manifest_hash,
                       self.output, 'Review one bounded C# candidate.', codex=self.codex,
                       context_files=['context.txt'], context_root=self.candidate)

    def _make_finished_events(self, *, bad_event=None, truncated=False, changed_paths=None):
        prepared = self.make_prepared()
        request = json.loads((prepared.output / 'request.json').read_bytes())
        selected = request['selected'][0]['path']
        target = prepared.workspace / selected
        target.write_text('public class Example { public int Value = 2; }\n', encoding='utf-8')
        response = {'status': 'partial', 'changedPaths': [selected] if changed_paths is None else changed_paths,
                    'unresolved': ['model output remains unreviewed'],
                    'summary': 'Recovered a completed agent response for offline review.'}
        events = [
            {'type': 'item.completed', 'item': {'id': 'item_1', 'type': 'agent_message',
             'text': json.dumps(response)}},
            {'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 20}},
        ]
        if bad_event:
            events.insert(0, {'type': bad_event})
        raw = b''.join((json.dumps(event, separators=(',', ':')) + '\n').encode('utf-8')
                       for event in events)
        if truncated:
            raw = raw[:-1]
        (prepared.output / 'events.jsonl').write_bytes(raw)
        process = {'state': 'running', 'pid': 2147483000, 'sessionId': None,
                   'attempt': request.get('resumeCount', 0), 'startedAtUnix': 1.0}
        (prepared.output / 'process.json').write_bytes(encoded(process))
        post_active = {'state': 'running', 'pid': process['pid'], 'attempt': 0}
        (postprocess.ACTIVE_PROCESS_PATH).write_bytes(encoded(post_active))
        return prepared, request, process, response, raw

    def test_recovers_completed_event_offline_as_partial_with_unknown_exit(self):
        prepared, request, process, response, events = self._make_finished_events()
        receipt = recover_completed(prepared.output)
        self.assertEqual(receipt['status'], 'partial')
        self.assertEqual(receipt['exitCode'], None)
        self.assertIsNone(receipt['returnCode'])
        self.assertEqual(receipt['stopReason'], 'completed-event-recovered/exit-not-recorded')
        self.assertEqual(receipt['completionEvidence']['exitStatus'], 'exit-not-recorded')
        self.assertEqual(receipt['completionEvidence']['eventsSha256'], sha(events))
        self.assertEqual(receipt['completionEvidence']['requestSha256'], sha(encoded(request)))
        self.assertEqual((prepared.output / 'process.json').read_bytes(), encoded(process))
        self.assertEqual(json.loads((prepared.output / 'final-response.json').read_bytes()), response)
        finalized = json.loads((prepared.output / 'request.json').read_bytes())
        self.assertEqual(finalized['state'], 'finalized')
        self.assertIsNone(finalized['exitCode'])
        self.assertEqual(recover_completed(prepared.output), receipt)

    def test_rejects_truncated_or_failed_event_stream_without_finalizing(self):
        for options in ({'truncated': True}, {'bad_event': 'turn.failed'}):
            with self.subTest(options=options):
                self.output = self.root / ('revision-' + str(len(list(self.root.glob('revision-*')))))
                prepared, *_ = self._make_finished_events(**options)
                with self.assertRaises(Exception):
                    recover_completed(prepared.output)
                request = json.loads((prepared.output / 'request.json').read_bytes())
                self.assertEqual(request['state'], 'prepared')
                self.assertFalse((prepared.output / 'manifest.json').exists())

    def test_rejects_live_pid_and_does_not_kill_or_finalize_it(self):
        prepared, request, process, *_ = self._make_finished_events()
        process['pid'] = os.getpid()
        (prepared.output / 'process.json').write_bytes(encoded(process))
        with self.assertRaises(Exception):
            recover_completed(prepared.output)
        self.assertEqual(json.loads((prepared.output / 'process.json').read_bytes())['pid'], os.getpid())
        self.assertFalse((prepared.output / 'manifest.json').exists())

    def test_rejects_declared_paths_that_do_not_match_real_diff(self):
        prepared, *_ = self._make_finished_events(changed_paths=[])
        receipt = recover_completed(prepared.output)
        self.assertEqual(receipt['status'], 'partial')
        self.assertNotEqual(receipt['declaredChangedPaths'], [row['path'] for row in receipt['actualChanges']])

    def test_rejects_mutated_read_only_context_before_recovery(self):
        prepared, request, *_ = self._make_finished_events()
        context_path = next(iter(request['contextFiles']))
        path = prepared.workspace / context_path
        path.chmod(0o600)
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaises(Exception):
            recover_completed(prepared.output)
        self.assertEqual(json.loads((prepared.output / 'request.json').read_bytes())['state'], 'prepared')

    def test_replay_rechecks_saved_event_hash(self):
        prepared, *_ = self._make_finished_events()
        recover_completed(prepared.output)
        with (prepared.output / 'events.jsonl').open('ab') as stream:
            stream.write(b'{}\n')
        with self.assertRaises(Exception):
            recover_completed(prepared.output)
