"""Source-pinned event planning contracts; no Editor process is launched."""
import tempfile
from pathlib import Path
import unittest

from beaver import csharp_rewrite_events as events
from beaver.errors import BeaverError
from beaver.io import encoded, sha, write_json


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


if __name__ == '__main__':
    unittest.main()
