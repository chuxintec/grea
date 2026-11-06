"""Source-pinned event planning contracts; no Editor process is launched."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from grea.development import csharp_rewrite_events as events
from grea.development.errors import BeaverError
from grea.development.io import encoded, sha, write_json


class RewriteEventEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source_path = self.root / 'source.json'
        self.source_document = {'document': {'records': [{'handler': 'onClickTip', 'target': 3}]}}
        write_json(self.source_path, self.source_document)
        self.record = self.source_document['document']['records'][0]
        self.source = dict(path=str(self.source_path), sha256=sha(self.source_path.read_bytes()),
                           recordId='source-record-1', jsonPointer='/document/records/0',
                           recordSha256=sha(encoded(self.record)))

    def tearDown(self):
        self.temp.cleanup()

    def test_rfc6901_pointer_resolves_record_and_escapes(self):
        doc = {'a/b': {'~key': [11]}}
        self.assertEqual(events._pointer(doc, '/a~1b/~0key/0'), 11)

    def test_source_file_and_canonical_record_hash_are_pinned(self):
        source = events._source(self.source, set(), set())
        self.assertEqual(source['recordId'], 'source-record-1')
        self.assertEqual(source['recordSha256'], sha(encoded(self.record)))

    def test_source_record_content_drift_is_rejected(self):
        source = dict(self.source, recordSha256='0' * 64)
        with self.assertRaises(BeaverError) as found:
            events._source(source, set(), set())
        self.assertEqual(found.exception.code, 'REWRITE_EVENT_SOURCE_RECORD_DRIFT')

    def test_same_pointer_cannot_be_recounted_under_an_alias(self):
        ids, pointers = set(), set()
        events._source(self.source, ids, pointers)
        aliased = dict(self.source, recordId='another-id')
        with self.assertRaises(BeaverError) as found:
            events._source(aliased, ids, pointers)
        self.assertEqual(found.exception.code, 'REWRITE_EVENT_SOURCE_ALIAS')

    def test_missing_compile_pin_requires_regenerated_plan(self):
        plan_path = self.root / 'rewrite-plan.json'
        report = dict(contract='beaver-agent-rewrite-plan/1', status='planned',
                      implementationSha256=events.csharp_rewrite.identity(), compileReport=None)
        write_json(plan_path, report)
        with self.assertRaises(BeaverError) as found:
            events._plan_data(plan_path, sha(plan_path.read_bytes()))
        self.assertEqual(found.exception.code, 'REWRITE_EVENT_COMPILE_PIN')

    def test_rewrite_plan_raw_sha_rejects_whitespace_drift(self):
        plan_path = self.root / 'rewrite-plan.json'
        report = dict(contract='beaver-agent-rewrite-plan/1', status='planned',
                      implementationSha256=events.csharp_rewrite.identity(), compileReport=None)
        write_json(plan_path, report)
        original = sha(plan_path.read_bytes())
        plan_path.write_bytes(plan_path.read_bytes() + b' ')
        with self.assertRaises(BeaverError) as found:
            events._plan_data(plan_path, original)
        self.assertEqual(found.exception.code, 'REWRITE_EVENT_PLAN_SHA')


class RewriteEventSemanticTests(RewriteEventEvidenceTests):
    def setUp(self):
        super().setUp()
        self.project = self.root / 'UnityProject'
        (self.project / 'Assets').mkdir(parents=True)
        (self.project / 'Assets/Panel.prefab.meta').write_text('fileFormatVersion: 2\nguid: ' + 'a' * 32 + '\n')
        script = dict(path='Assets/Help.cs', assembly='Assembly-CSharp', fullType='Example.Help', guid='b' * 32)
        self.data = dict(projectRoot=str(self.project),
                         compatibility=[script],
                         fileEdits=[dict(path=script['path'], sha256='c' * 64)],
                         pins=[dict(path=str(self.source_path), sha256=sha(self.source_path.read_bytes()))],
                         instances=[dict(prefabPath='Assets/Panel.prefab', prefabGuid='a' * 32,
                                         nodeLocalId=30, componentLocalId=40, fullType='Example.Help')])
        self.compiled = dict(status='ok', assemblies=[dict(name='Assembly-CSharp', sourceSemantics=[dict(
            path='Assets/Help.cs', types=[dict(fullName='Example.Help', eventMethods=[dict(
                name='Open', returnType='System.Void', parameters=[], genericArity=0)])])])])
        self.event = dict(source=self.source,
                          prefab=dict(path='Assets/Panel.prefab', guid='a' * 32),
                          button=dict(nodePath='Panel/Help', componentType=events.BUTTON,
                                      nodeLocalId=10, componentLocalId=20),
                          target=dict(nodePath='Panel', componentType='Example.Help', fullType='Example.Help',
                                      assembly='Assembly-CSharp', scriptPath='Assets/Help.cs', scriptGuid='b' * 32,
                                      method='Open', nodeLocalId=30, componentLocalId=40))

    def use_source_button_policy(self, button_record):
        document = {'document': {'instances': [{'_components': [button_record]}]}}
        write_json(self.source_path, document)
        record = button_record['clickEvents'][0]
        source = dict(path=str(self.source_path), sha256=sha(self.source_path.read_bytes()),
                      recordId='source-button-event-1',
                      jsonPointer='/document/instances/0/_components/0/clickEvents/0',
                      recordSha256=sha(encoded(record)))
        self.data['pins'] = [dict(path=str(self.source_path), sha256=source['sha256'])]
        self.event['source'] = source
        self.event['inputPolicy'] = 'enable-source-button'

    def test_exact_compiled_method_and_native_target_make_event_action(self):
        result = events._event(self.event, self.data, self.compiled, set(), (set(), set()))
        self.assertEqual(result['action'], dict(kind='binding.event', path='Panel/Help',
                                                component=events.BUTTON, property='onClick', value='empty',
                                                method='Open', targetNode='Panel', targetComponent='Example.Help'))
        self.assertEqual(result['inspect0']['expectedCount'], 0)
        self.assertEqual(result['inspect1']['expectedCount'], 1)
        self.assertIs(type(result['inspect0']['buttonLocalId']), int)

    def test_missing_method_fails_without_inventing_handler(self):
        self.event['target']['method'] = 'Missing'
        with self.assertRaises(BeaverError) as found:
            events._event(self.event, self.data, self.compiled, set(), (set(), set()))
        self.assertEqual(found.exception.code, 'REWRITE_EVENT_METHOD')

    def test_ambiguous_method_overload_fails(self):
        self.compiled['assemblies'][0]['sourceSemantics'][0]['types'][0]['eventMethods'].append(
            dict(name='Open', returnType='System.Void', parameters=[], genericArity=0))
        with self.assertRaises(BeaverError) as found:
            events._event(self.event, self.data, self.compiled, set(), (set(), set()))
        self.assertEqual(found.exception.code, 'REWRITE_EVENT_METHOD')

    def test_missing_native_instance_id_fails(self):
        self.event['target']['componentLocalId'] = 0
        with self.assertRaises(BeaverError) as found:
            events._event(self.event, self.data, self.compiled, set(), (set(), set()))
        self.assertEqual(found.exception.code, 'REWRITE_EVENT_NATIVE_ID')

    def test_duplicate_button_destination_fails(self):
        destinations = set()
        events._event(self.event, self.data, self.compiled, destinations, (set(), set()))
        second_source_path = self.root / 'second-source.json'
        write_json(second_source_path, self.source_document)
        second_source = dict(self.source, path=str(second_source_path), recordId='source-record-2',
                             sha256=sha(second_source_path.read_bytes()))
        self.data['pins'].append(dict(path=str(second_source_path), sha256=second_source['sha256']))
        duplicate = dict(self.event, source=second_source)
        with self.assertRaises(BeaverError) as found:
            events._event(duplicate, self.data, self.compiled, destinations, (set(), set()))
        self.assertEqual(found.exception.code, 'REWRITE_EVENT_DUPLICATE')

    def test_source_button_policy_emits_enable_and_interactable_postcondition(self):
        self.use_source_button_policy(dict(__type__='cc.Button', _enabled=True, _interactable=True,
                                           clickEvents=[dict(handler='Open')]))
        result = events._event(self.event, self.data, self.compiled, set(), (set(), set()))
        self.assertEqual(result['action']['kind'], 'binding.event.enable')
        self.assertNotIn('requireInteractable', result['inspect0'])
        self.assertIs(result['inspect1']['requireInteractable'], True)

    def test_source_button_policy_rejects_non_button_parent(self):
        self.use_source_button_policy(dict(__type__='cc.Component', clickEvents=[dict(handler='Open')]))
        with self.assertRaises(BeaverError) as found:
            events._event(self.event, self.data, self.compiled, set(), (set(), set()))
        self.assertEqual(found.exception.code, 'REWRITE_EVENT_INPUT_POLICY')

    def test_source_button_policy_rejects_explicit_disabled_values(self):
        for field in ('_enabled', '_interactable', 'interactable'):
            self.use_source_button_policy(dict(__type__='cc.Button', clickEvents=[dict(handler='Open')], **{field: False}))
            with self.assertRaises(BeaverError) as found:
                events._event(self.event, self.data, self.compiled, set(), (set(), set()))
            self.assertEqual(found.exception.code, 'REWRITE_EVENT_INPUT_POLICY')

    def test_source_button_policy_requires_source_handler_match(self):
        self.use_source_button_policy(dict(__type__='cc.Button', clickEvents=[dict(handler='Other')]))
        with self.assertRaises(BeaverError) as found:
            events._event(self.event, self.data, self.compiled, set(), (set(), set()))
        self.assertEqual(found.exception.code, 'REWRITE_EVENT_INPUT_POLICY')


class RewriteEventVerifyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'UnityProject'
        assets = self.project / 'Assets'
        assets.mkdir(parents=True)
        self.prefab = assets / 'Panel.prefab'
        self.prefab.write_text('prefab-state-after\n')
        self.event_source = self.root / 'source.json'
        write_json(self.event_source, {'record': {'handler': 'Open'}})
        event_record = {'path': str(self.event_source), 'sha256': sha(self.event_source.read_bytes()),
                        'recordId': 'source-1', 'jsonPointer': '/record',
                        'recordSha256': sha(encoded({'handler': 'Open'}))}
        event_source_pin = dict(path=event_record['path'], sha256=event_record['sha256'],
                                recordId=event_record['recordId'], jsonPointer=event_record['jsonPointer'],
                                recordSha256=event_record['recordSha256'])
        profile = self.root / 'profile.json'
        write_json(profile, {})
        self.original_native_path = self.root / 'original-production-plan.json'
        self.original_spec = dict(schemaVersion=3, operation='production', profile=str(profile),
                                  steps=[], fileEdits=[], readPaths=[])
        self.original_native = dict(contract='beaver-production/3', projectRoot=str(self.project),
                                    spec=self.original_spec, writeSet=[])
        write_json(self.original_native_path, self.original_native)
        self.script = self.project / 'Assets/Help.cs'
        self.script.write_text('class Help { /* rewritten */ }')
        old_script = b'class Help {}'
        self.patch_source = self.root / 'Help.patch.cs'
        self.patch_source.write_bytes(self.script.read_bytes())
        self.file_edit = dict(path='Assets/Help.cs', source=str(self.patch_source),
                              sha256=sha(self.patch_source.read_bytes()), expectedSha256=sha(old_script))
        self.original_spec['fileEdits'] = [self.file_edit]
        self.original_native['spec'] = self.original_spec
        write_json(self.original_native_path, self.original_native)
        self.readonly = assets / 'ReadOnly.json'
        self.readonly.write_text('{}')
        self.script_before = dict(sha256=sha(old_script), bytes=len(old_script))
        self.compile_report_path = self.root / 'compile.json'
        write_json(self.compile_report_path, dict(status='ok'))
        self.rewrite_path = self.root / 'rewrite-plan.json'
        self.rewrite = dict(contract='beaver-agent-rewrite-plan/1', status='planned',
                            implementationSha256=events.csharp_rewrite.identity(), projectRoot=str(self.project),
                            fileEdits=[self.file_edit],
                            pins=[dict(path=str(self.event_source), sha256=event_record['sha256']),
                                  dict(path=str(self.script), sha256=sha(old_script))],
                            compileReport=dict(path=str(self.compile_report_path),
                                               sha256=sha(self.compile_report_path.read_bytes())),
                            production=dict(report=str(self.original_native_path),
                                            planSha256=sha(encoded(self.original_native))))
        write_json(self.rewrite_path, self.rewrite)

        self.per_event = dict(sourceRecordId='source-1', prefabPath='Assets/Panel.prefab', prefabGuid='a' * 32,
                              buttonPath='Panel/Help', buttonLocalId=20, buttonNodeLocalId=10,
                              targetNode='Panel', targetLocalId=40, targetNodeLocalId=30,
                              targetAssembly='Assembly-CSharp', scriptGuid='b' * 32,
                              targetComponent='Example.Help', targetType='Example.Help', method='Open',
                              expectedCount=0, planned=True, failed=False, reason=None)
        inspect = dict(kind='prefab.event.inspect', assetPath='Assets/Panel.prefab', path='Panel/Help',
                       targetNode='Panel', targetComponent='Example.Help', method='Open',
                       buttonLocalId=20, targetLocalId=40, prefabGuid='a' * 32,
                       buttonNodeLocalId=10, targetNodeLocalId=30,
                       targetAssembly='Assembly-CSharp', scriptGuid='b' * 32)
        action = dict(kind='binding.event', path='Panel/Help', component='UnityEngine.UI.Button',
                      property='onClick', value='empty', method='Open', targetNode='Panel',
                      targetComponent='Example.Help')
        self.spec = dict(schemaVersion=3, operation='production', profile=str(profile),
                         steps=[dict(inspect, expectedCount=0),
                                dict(kind='prefab.patch', assetPath='Assets/Panel.prefab', actions=[action]),
                                dict(inspect, expectedCount=1)], fileEdits=[self.file_edit], readPaths=[])
        self.write_set = ['Assets/Help.cs', 'Assets/Panel.prefab']
        from grea.development.batch import state
        self.after = state(self.project, self.write_set)
        self.before = {'Assets/Help.cs': self.script_before, 'Assets/Panel.prefab': None}
        self.plan_before = dict(self.before)
        self.plan_before['Assets/ReadOnly.json'] = dict(sha256=sha(self.readonly.read_bytes()), bytes=self.readonly.stat().st_size)
        self.native_plan_path = self.root / 'event-production-plan.json'
        self.native_plan = dict(contract='beaver-production/3', schemaVersion=3,
                                implementationSha256=events.csharp_rewrite.identity(), projectRoot=str(self.project),
                                spec=self.spec, writeSet=self.write_set, before=self.plan_before)
        write_json(self.native_plan_path, self.native_plan)
        self.transaction = self.root / 'transaction'
        self.transaction.mkdir()
        (self.transaction / 'batch-plan.json').write_bytes(self.native_plan_path.read_bytes())
        self.journal = dict(contract='beaver-production-transaction/3', status='complete',
                            implementationSha256=events.csharp_rewrite.identity(),
                            planSha256=sha(self.native_plan_path.read_bytes()), native=dict(status='verified'),
                            projectRoot=str(self.project), writeSet=self.write_set, before=self.before, after=self.after)
        write_json(self.transaction / 'journal.json', self.journal)
        self.event_plan_path = self.root / 'event-plan.json'
        self.event_plan = dict(contract=events.EVENT_PLAN, status='planned',
                               implementationSha256=events.csharp_rewrite.identity(),
                               projectRoot=str(self.project),
                               rewritePlan=dict(path=str(self.rewrite_path), sha256=sha(self.rewrite_path.read_bytes())),
                               sourcePins=[event_source_pin],
                               production=dict(report=str(self.native_plan_path),
                                               planSha256=sha(self.native_plan_path.read_bytes()),
                                               originalReport=str(self.original_native_path),
                                               originalPlanSha256=sha(encoded(self.original_native))),
                               commands=dict(apply=['beaver', 'production', 'apply', '--out', str(self.transaction)]),
                               perEvent=[self.per_event])
        write_json(self.event_plan_path, self.event_plan)

    def tearDown(self):
        self.temp.cleanup()

    def enable_input_policy(self):
        self.per_event['inputPolicy'] = 'enable-source-button'
        steps = self.spec['steps']
        steps[1]['actions'][0]['kind'] = 'binding.event.enable'
        steps[2]['requireInteractable'] = True
        write_json(self.native_plan_path, self.native_plan)
        (self.transaction / 'batch-plan.json').write_bytes(self.native_plan_path.read_bytes())
        self.journal['planSha256'] = sha(self.native_plan_path.read_bytes())
        write_json(self.transaction / 'journal.json', self.journal)
        self.event_plan['production']['planSha256'] = sha(self.native_plan_path.read_bytes())
        write_json(self.event_plan_path, self.event_plan)

    def test_actual_production_report_journal_and_write_set_are_cross_checked(self):
        output = self.root / 'verify-output'

        def fake_production_plan(project, spec, destination):
            destination.mkdir()
            report = destination / 'batch-plan.json'
            data = dict(contract='beaver-production/3', projectRoot=str(project), spec=spec, writeSet=[])
            write_json(report, data)
            return dict(status='planned', report=str(report), planSha256=sha(report.read_bytes()))

        with patch.object(events, '_production_plan', side_effect=fake_production_plan):
            result = events.verify(self.event_plan_path, sha(self.event_plan_path.read_bytes()),
                                   self.transaction, 'applied', output, '/Unity')
        self.assertEqual(result['status'], 'planned')
        report = __import__('json').loads(Path(result['report']).read_text())
        self.assertEqual(report['expectedCount'], 1)
        self.assertEqual(report['native'], 'not_run')
        self.assertEqual(report['argv'][:4], ['grea', 'develop', 'production', 'apply'])

    def test_transaction_write_set_mismatch_is_rejected(self):
        self.journal['writeSet'] = []
        write_json(self.transaction / 'journal.json', self.journal)
        with self.assertRaises(BeaverError) as found:
            events.verify(self.event_plan_path, sha(self.event_plan_path.read_bytes()),
                          self.transaction, 'applied', self.root / 'blocked', '/Unity')
        self.assertEqual(found.exception.code, 'REWRITE_EVENT_VERIFY_WRITE_SET')

    def test_verify_applied_requires_interactable_but_recovered_does_not(self):
        self.enable_input_policy()
        captured = []

        def fake_production_plan(project, spec, destination):
            captured.append(spec)
            destination.mkdir()
            report = destination / 'batch-plan.json'
            write_json(report, dict(contract='beaver-production/3', projectRoot=str(project), spec=spec, writeSet=[]))
            return dict(status='planned', report=str(report), planSha256=sha(report.read_bytes()))

        with patch.object(events, '_production_plan', side_effect=fake_production_plan):
            events.verify(self.event_plan_path, sha(self.event_plan_path.read_bytes()), self.transaction,
                          'applied', self.root / 'policy-applied', '/Unity')
        applied_inspect = captured[-1]['steps'][0]
        self.assertIs(applied_inspect['requireInteractable'], True)

        self.script.write_bytes(b'class Help {}')
        self.prefab.unlink()
        receipt_path = self.root / 'policy-recovery.json'
        write_json(receipt_path, dict(status='verified', report=str(receipt_path),
                                      nativeReadback='restored_exact_bytes_and_imported',
                                      restored=len(self.write_set)))
        self.journal.update(status='recovered', recoveryReport=str(receipt_path))
        write_json(self.transaction / 'journal.json', self.journal)
        with patch.object(events, '_production_plan', side_effect=fake_production_plan):
            events.verify(self.event_plan_path, sha(self.event_plan_path.read_bytes()), self.transaction,
                          'recovered', self.root / 'policy-recovered', '/Unity')
        recovered_inspect = captured[-1]['steps'][0]
        self.assertNotIn('requireInteractable', recovered_inspect)

    def test_applied_patch_sha_must_match_rewrite_file_edit(self):
        self.journal['after']['Assets/Help.cs']['sha256'] = '0' * 64
        write_json(self.transaction / 'journal.json', self.journal)
        with self.assertRaises(BeaverError) as found:
            events.verify(self.event_plan_path, sha(self.event_plan_path.read_bytes()),
                          self.transaction, 'applied', self.root / 'patch-mismatch', '/Unity')
        self.assertEqual(found.exception.code, 'REWRITE_EVENT_VERIFY_APPLIED')

    def test_recovered_receipt_and_before_state_are_required(self):
        self.script.write_bytes(b'class Help {}')
        self.prefab.unlink()
        receipt_path = self.root / 'recovery.json'
        write_json(receipt_path, dict(status='verified', report=str(receipt_path),
                                      nativeReadback='restored_exact_bytes_and_imported',
                                      restored=len(self.write_set)))
        self.journal.update(status='recovered', recoveryReport=str(receipt_path))
        write_json(self.transaction / 'journal.json', self.journal)

        def fake_production_plan(project, spec, destination):
            destination.mkdir()
            report = destination / 'batch-plan.json'
            write_json(report, dict(contract='beaver-production/3', projectRoot=str(project), spec=spec, writeSet=[]))
            return dict(status='planned', report=str(report), planSha256=sha(report.read_bytes()))

        with patch.object(events, '_production_plan', side_effect=fake_production_plan):
            result = events.verify(self.event_plan_path, sha(self.event_plan_path.read_bytes()),
                                   self.transaction, 'recovered', self.root / 'recovered-output', '/Unity')
        report = __import__('json').loads(Path(result['report']).read_text())
        self.assertEqual(report['expectedCount'], 0)

    def test_bad_recovery_receipt_is_rejected(self):
        receipt_path = self.root / 'bad-recovery.json'
        write_json(receipt_path, dict(status='verified', report='wrong-path',
                                      nativeReadback='restored_exact_bytes_and_imported',
                                      restored=len(self.write_set)))
        self.journal.update(status='recovered', recoveryReport=str(receipt_path))
        write_json(self.transaction / 'journal.json', self.journal)
        with self.assertRaises(BeaverError) as found:
            events.verify(self.event_plan_path, sha(self.event_plan_path.read_bytes()),
                          self.transaction, 'recovered', self.root / 'bad-recovered-output', '/Unity')
        self.assertEqual(found.exception.code, 'REWRITE_EVENT_VERIFY_RECOVERY')


if __name__ == '__main__':
    unittest.main()
