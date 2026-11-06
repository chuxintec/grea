"""Explicit compiler-only intake retains the existing compile/reference gates."""
import tempfile
import unittest
from pathlib import Path
from grea.development.intake import build_plan
from grea.development.intake_contract import validate_spec
from grea.development.intake_native import _native_plan, _job
from grea.development.errors import BeaverError
from grea.development.io import write_json
from . import test_intake_new_scripts as fixtures

class ScriptOnlyTests(unittest.TestCase):
    def fixture(self,root):
        candidate,target,spec,path=fixtures.NewScriptPlanTests().fixture(root)
        spec.update(schemaVersion=4,operation='script-only-intake',additions=[],engineObjects=[])
        write_json(path,spec)
        return candidate,target,spec,path

    def test_only_scripts_enter_existing_native_compiler_and_guarded_write_set(self):
        with tempfile.TemporaryDirectory() as temp:
            c,t,s,p=self.fixture(Path(temp).resolve())
            plan=build_plan(c,t,p)
            self.assertEqual([r['source'] for r in plan['additions']],['Assets/Widget.cs'])
            self.assertEqual(len(plan['newScripts']),1)
            native=_native_plan(plan)
            self.assertEqual([o['target'] for o in native['operations']],['Assets/Runtime/Widget.cs'])
            self.assertEqual(len(native['intakeNewScripts']),1)
            self.assertFalse((t/'Assets/Runtime').exists())

    def test_noop_asset_padding_and_over_limit_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            _,_,s,_=self.fixture(Path(temp).resolve())
            for change in ({'newScripts':[]},{'additions':[dict(source='Assets/New.txt',target='Assets/New.txt')]},{'newScripts':s['newScripts']*17},{'schemaVersion':3}):
                with self.subTest(change=list(change)):
                    with self.assertRaises(BeaverError):validate_spec(dict(s,**change))

    def test_additive_operation_keeps_nonempty_asset_requirement(self):
        with tempfile.TemporaryDirectory() as temp:
            _,_,s,_=self.fixture(Path(temp).resolve())
            with self.assertRaises(BeaverError):validate_spec(dict(s,operation='additive-intake'))

    def test_published_schemas_describe_explicit_mode_only(self):
        import json
        from jsonschema import Draft202012Validator
        with tempfile.TemporaryDirectory() as temp:
            _,_,s,_=self.fixture(Path(temp).resolve())
            schema=json.loads((Path(__file__).parents[2]/'schemas/development/additive-intake-4.schema.json').read_text())
            validator=Draft202012Validator(schema)
            self.assertFalse(list(validator.iter_errors(s)))
            self.assertTrue(list(validator.iter_errors(dict(s,newScripts=[]))))
            self.assertTrue(list(validator.iter_errors(dict(s,operation='additive-intake'))))
