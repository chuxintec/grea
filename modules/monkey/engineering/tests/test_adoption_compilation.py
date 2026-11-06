"""Compiler-boundary recovery must work before a Unity helper can compile."""
import shutil
import tempfile
import unittest
from pathlib import Path
from beaver.adoption import preview, prepare
from beaver.adoption_native import restore_code, job_spec, compile_operation
from beaver.io import write_json, read, load
from beaver.errors import BeaverError
from test_adoption import candidate, PREFIX


class CompilationRecoveryTests(unittest.TestCase):
    def fixture(self, root):
        base=candidate(root/'base','Code.cs',b'class Old {}')
        incoming=candidate(root/'incoming','Code.cs',b'class New {}')
        target=root/'target';shutil.copytree(base,target)
        preview(incoming,target,root/'preview',base)
        stage,plan,journal=prepare(root/'preview/adoption-plan.json',root/'tx')
        write_json(stage/'native-code.json',dict(planSha256=journal['planSha256'],written=[0]))
        return stage,plan,journal,target

    def test_compiler_before_image_restores_and_can_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            stage,plan,journal,target=self.fixture(Path(temp).resolve())
            (target/(PREFIX+'Code.cs')).write_bytes(b'class New {}')
            restore_code(stage,plan,journal)
            self.assertEqual((target/(PREFIX+'Code.cs')).read_bytes(),b'class Old {}')
            self.assertTrue(journal['codeRestored'])
            restore_code(stage,plan,journal)

    def test_later_edit_and_changed_before_image_refused(self):
        for fault in ['live','backup']:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                stage,plan,journal,target=self.fixture(Path(temp).resolve())
                path=target/(PREFIX+'Code.cs');path.write_bytes(b'class New {}')
                (path if fault=='live' else stage/'before/0/file').write_bytes(b'// manual edit')
                before=path.read_bytes()
                with self.assertRaises(BeaverError):restore_code(stage,plan,journal)
                self.assertEqual(path.read_bytes(),before)

    def test_job_marks_assembly_and_source_changes_but_not_resources(self):
        with tempfile.TemporaryDirectory() as temp:
            stage,plan,journal,target=self.fixture(Path(temp).resolve())
            spec=job_spec(stage,plan,journal,'code',30)
            self.assertTrue(spec['operations'][0]['compileStage'])
            self.assertFalse(spec['codeRestored'])
            for ext in ['.cs','.asmdef','.asmref','.rsp','.dll']:
                self.assertTrue(compile_operation(dict(source=None,target='Assets/Code'+ext)))
            self.assertFalse(compile_operation(dict(source=None,target='Assets/Item.prefab')))

    def test_declared_missing_source_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();base=candidate(root/'base');incoming=candidate(root/'incoming');target=root/'target';shutil.copytree(base,target)
            manifest=load(read(incoming/'manifest.json'))
            manifest['adoptionDependencies']=dict(schemaVersion=1,coverage='producer-declared',edges=[dict(path='Assets/Missing.cs',requires=[],kind='csharp-compile')])
            write_json(incoming/'manifest.json',manifest)
            with self.assertRaises(BeaverError):preview(incoming,target,root/'preview',base)
            self.assertFalse((root/'preview').exists())

    def test_compiler_input_without_owned_meta_blocks_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();base=candidate(root/'base');incoming=candidate(root/'incoming','Code.cs');target=root/'target';shutil.copytree(base,target)
            path=PREFIX+'Code.cs.meta';(incoming/path).unlink()
            manifest=load(read(incoming/'manifest.json'));manifest['files']=[row for row in manifest['files'] if row['path']!=path];write_json(incoming/'manifest.json',manifest)
            result=preview(incoming,target,root/'preview',base)
            self.assertEqual(result['status'],'blocked')
            plan=load(read(root/'preview/adoption-plan.json'))
            self.assertIn('compiler-input-requires-owned-metadata',[c['reason'] for c in plan['conflicts']])
