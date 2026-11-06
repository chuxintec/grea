"""Preparation planning and immutable-input guards; native gates are separate."""
import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from grea.development.errors import BeaverError
from grea.development.io import sha, write_json
from grea.development.intake_bindings import build_plan, preview, validate_spec, execute, failed_native_attempts, snapshot_reference, BRIDGE
from .test_intake import _project, _write_asset


class BindingTests(unittest.TestCase):
    def fixture(self, root):
        source = _project(root/'source'); target = _project(root/'target')
        code = b'public class Widget : UnityEngine.MonoBehaviour { public int count; }'
        _write_asset(source, 'Assets/Widget.cs', code, '1'*32)
        _write_asset(target, 'Assets/Runtime/Widget.cs', code, '2'*32)
        _write_asset(source, 'Assets/Panel.prefab', b'm_Script: {fileID: 11500000, guid: '+b'1'*32+b', type: 3}\n', '3'*32)
        row = dict(source='Assets/Widget.cs', sourceGuid='1'*32, sourceType='Widget', sourceAssembly='Assembly-CSharp', sourceLocalId=11500000,
                   target='Assets/Runtime/Widget.cs', targetGuid='2'*32, targetType='Widget', targetAssembly='Assembly-CSharp', targetLocalId=11500000)
        for side, project in [('source', source), ('target', target)]:
            for suffix, key in [('', 'Sha256'), ('.meta', 'MetaSha256')]:
                row[side+key] = sha((project/(row[side]+suffix)).read_bytes())
        doc = dict(schemaVersion=1, operation='prepare-script-bindings', bindings=[row], prefabs=['Assets/Panel.prefab'], bridgeReferences=[])
        spec = root/'spec.json'; write_json(spec, doc)
        return source, target, spec, doc

    def error(self, code, fn, *args):
        with self.assertRaises(BeaverError) as caught: fn(*args)
        self.assertEqual(caught.exception.code, code)

    def test_byte_equal_different_guid_plan_does_not_write_either_project(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve(); s,t,p,doc=self.fixture(root)
            before={str(x):x.read_bytes() for r in (s,t) for x in r.rglob('*') if x.is_file()}
            plan=build_plan(s,t,p)
            self.assertFalse(plan['targetWrites']);self.assertEqual(plan['native'],'not_run')
            self.assertEqual(before,{str(x):x.read_bytes() for r in (s,t) for x in r.rglob('*') if x.is_file()})

    def test_nonidentical_code_different_type_same_guid_or_wrong_local_id_refused(self):
        with tempfile.TemporaryDirectory() as d:
            s,t,p,doc=self.fixture(Path(d).resolve())
            for change,code in [({'targetSha256':'0'*64},'INTAKE_BINDING_EQUIVALENCE'),({'targetType':'Other'},'INTAKE_BINDING_EQUIVALENCE'),
                                ({'targetGuid':'1'*32},'INTAKE_BINDING_EQUIVALENCE'),({'sourceLocalId':True},'INTAKE_BINDING_LOCAL_ID')]:
                bad=copy.deepcopy(doc);bad['bindings'][0].update(change);self.error(code,validate_spec,bad)

    def test_target_and_source_meta_drift_refused(self):
        for side in ('source','target'):
            with tempfile.TemporaryDirectory() as d:
                s,t,p,doc=self.fixture(Path(d).resolve());r=s if side=='source' else t
                (r/(doc['bindings'][0][side]+'.meta')).write_text('drift')
                self.error('INTAKE_BINDING_DRIFT',build_plan,s,t,p)

    def test_scope_drift_and_unresolved_asmref_refused(self):
        with tempfile.TemporaryDirectory() as d:
            s,t,p,doc=self.fixture(Path(d).resolve())
            write_json(t/'Assets/Runtime/Scope.asmdef',dict(name='Other'))
            self.error('INTAKE_BINDING_ASSEMBLY',build_plan,s,t,p)
            (t/'Assets/Runtime/Scope.asmdef').unlink();write_json(t/'Assets/Runtime/Scope.asmref',dict(reference='Other'))
            self.error('INTAKE_BINDING_ASSEMBLY',build_plan,s,t,p)

    def test_prefab_dependency_closure_required(self):
        with tempfile.TemporaryDirectory() as d:
            s,t,p,doc=self.fixture(Path(d).resolve());_write_asset(s,'Assets/Nested.prefab',b'root', '4'*32)
            with (s/'Assets/Panel.prefab').open('ab') as f:f.write(b'guid: '+b'4'*32)
            self.error('INTAKE_BINDING_CLOSURE',build_plan,s,t,p)

    def test_unused_mapping_and_source_guid_alias_refused(self):
        with tempfile.TemporaryDirectory() as d:
            s,t,p,doc=self.fixture(Path(d).resolve());(s/'Assets/Panel.prefab').write_text('no refs')
            self.error('INTAKE_BINDING_UNUSED',build_plan,s,t,p)
            _write_asset(s,'Assets/Alias.txt',b'alias','2'*32)
            self.error('INTAKE_BINDING_ALIAS',build_plan,s,t,p)

    def test_reserved_directory_overlap_and_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();s,t,p,doc=self.fixture(root)
            (s/BRIDGE).mkdir();self.error('INTAKE_BINDING_RESERVED',build_plan,s,t,p)
            (s/BRIDGE).rmdir();(s/'Assets/Link.cs').symlink_to(s/'Assets/Widget.cs')
            self.error('SYMLINK_PATH',build_plan,s,t,p)

    def test_plan_drift_fails_before_creating_copy_or_spawning_editor(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();s,t,p,doc=self.fixture(root);result=preview(s,t,p,root/'plan')
            (t/'Assets/Runtime/Widget.cs').write_text('later edit')
            with patch('grea.development.intake_bindings._run') as run:
                self.error('INTAKE_BINDING_DRIFT',execute,result['report'],result['planSha256'],root/'prepared','unused')
                run.assert_not_called();self.assertFalse((root/'prepared').exists())

    def test_editor_failure_is_confined_to_new_copy_and_keeps_originals(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();s,t,p,doc=self.fixture(root);result=preview(s,t,p,root/'plan')
            before={str(x):x.read_bytes() for r in (s,t) for x in r.rglob('*') if x.is_file()}
            from grea.development.errors import fail
            with patch('grea.development.intake_bindings.editor_path',return_value=Path('/unused')),patch('grea.development.intake_bindings._run',side_effect=lambda *args:fail('INJECTED_NATIVE_FAILURE','test','injected')):
                self.error('INJECTED_NATIVE_FAILURE',execute,result['report'],result['planSha256'],root/'prepared','unused')
            self.assertTrue((root/'prepared/UnityProject'/BRIDGE/'Widget.cs').is_file())
            self.assertEqual(before,{str(x):x.read_bytes() for r in (s,t) for x in r.rglob('*') if x.is_file()})

    def test_failed_native_process_is_reported_even_when_preparation_raises(self):
        from grea.development.cli import main
        from grea.development.errors import fail
        with tempfile.TemporaryDirectory() as d:
            out=Path(d).resolve()/'isolated'
            def failed(*args):
                out.mkdir();write_json(out/'apply-process.json',dict(pid=12345,exited=True,exitCode=1,interrupted=False))
                fail('INTAKE_BINDING_NATIVE_FAILED',str(out),'native gate failed')
            stdout=io.StringIO()
            with patch('grea.development.intake_bindings.execute',side_effect=failed),contextlib.redirect_stdout(stdout):
                code=main(['intake','prepare-bindings','--plan','unused','--expected-plan','a'*64,'--out',str(out),'--editor-path','unused'])
            data=json.loads(stdout.getvalue());self.assertEqual(code,2);self.assertEqual(data['verification']['native'],'failed')
            self.assertEqual(data['actualChanges'][0]['nativeProcesses'][0]['pid'],12345)
            self.assertFalse(data['actualChanges'][0]['targetProjectWrites'])

    def test_no_native_attempt_inferred_from_preparation_directory_alone(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(failed_native_attempts(Path(d).resolve()),[])
            write_json(Path(d)/'apply-process.json',dict(pid=True,exited=True))
            self.error('INTAKE_BINDING_PROCESS_RECEIPT',failed_native_attempts,Path(d).resolve())

    def test_snapshot_header_pins_bytes_and_rejects_budget_alias_and_drift(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();raw=b'{"planSha256":"test","prefabs":[]}';(root/'apply-snapshot.json').write_bytes(raw)
            header=dict(snapshotFile='apply-snapshot.json',snapshotBytes=len(raw),snapshotSha256=sha(raw))
            self.assertEqual(snapshot_reference(root,header,'apply'),root/'apply-snapshot.json')
            for bad in [dict(header,snapshotBytes=64*1024*1024+1),dict(header,snapshotBytes=True),dict(header,snapshotSha256=0),dict(header,snapshotFile='../outside.json')]:
                self.error('INTAKE_BINDING_SNAPSHOT',snapshot_reference,root,bad,'apply')
            (root/'apply-snapshot.json').write_bytes(raw+b' ');self.error('INTAKE_BINDING_SNAPSHOT',snapshot_reference,root,header,'apply')

    def test_source_owning_identity_and_unowned_working_copy_are_distinguished(self):
        from .helpers import finish
        with tempfile.TemporaryDirectory() as d:
            s,t,p,doc=self.fixture(Path(d).resolve())
            finish(s,dict(schemaVersion=1,targetProfile='unity-6000.6.2f1-ugui',namespace='neutral-source',native='verified',diagnostics=[]))
            origin=build_plan(s,t,p)['sourceOrigin'];self.assertEqual(origin['owningStatus'],'verified')
            self.assertEqual(origin['owningManifest']['sha256'],sha((s/'manifest.json').read_bytes()))
            (s/'Library').mkdir();(s/'Library/cache.txt').write_text('unowned working cache')
            origin=build_plan(s,t,p)['sourceOrigin'];self.assertEqual(origin['owningStatus'],'unverified_diagnostic_source')
            self.assertEqual(origin['diagnostic']['code'],'CANDIDATE_UNOWNED')

    def test_origin_manifest_change_is_pinned_even_when_product_files_unchanged(self):
        from .helpers import finish
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();s,t,p,doc=self.fixture(root)
            finish(s,dict(schemaVersion=1,targetProfile='unity-6000.6.2f1-ugui',namespace='neutral-source'))
            result=preview(s,t,p,root/'plan');manifest=json.loads((s/'manifest.json').read_text());manifest['namespace']='changed-origin';write_json(s/'manifest.json',manifest)
            self.error('INTAKE_BINDING_PRECONDITION',execute,result['report'],result['planSha256'],root/'uncreated','unused')
            self.assertFalse((root/'uncreated').exists())


if __name__=='__main__': unittest.main()
