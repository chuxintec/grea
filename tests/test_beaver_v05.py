"""Only the fixed 0.5 forwarding increment; no Engine or game execution."""
import copy
import tempfile
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator, ValidationError
from grea.integrations import beaver, beaver_operations as ops
from grea.beaver_contracts import documents, validate_result


def request(name, **options):
    return dict(schema_version=1, operation=name, options=options, timeout_seconds=30)


def fixture_path(name):
    return str((Path(tempfile.gettempdir()) / 'grea-fixtures' / name).resolve())


class BeaverV05Tests(unittest.TestCase):
    def capabilities(self):
        return dict(version='0.5.0', **beaver.V03_CONTRACTS,
                    producer_implementation_sha256=beaver.V03_CANDIDATES['0.5.0']['implementation_sha256'],
                    capabilities=[dict(id=n, state='implemented') for n in sorted(beaver.V02_OPERATIONS | beaver.V03_GROUPS | beaver.V05_GROUPS)])

    def test_fixed_identity_and_capabilities_not_just_higher_version(self):
        cap=self.capabilities();beaver.validate_capabilities(cap)
        for key,value in [('version','0.5.1'),('producer_implementation_sha256','a'*64),
                          ('productionTransactionContract','beaver-production-transaction/4')]:
            with self.subTest(key=key),self.assertRaises(ValueError):beaver.validate_capabilities(dict(cap,**{key:value}))
        for missing in beaver.V05_GROUPS:
            bad=copy.deepcopy(cap);bad['capabilities']=[r for r in bad['capabilities'] if r['id']!=missing]
            with self.subTest(missing=missing),self.assertRaises(ValueError):beaver.validate_capabilities(bad)

    def test_five_routes_only_on_new_fixed_provider(self):
        for name in ('ui.inspect','ui.analyze','ui.repair-plan','wiring.plan','diagnostics.summarize'):
            spec=ops.OPERATIONS[name]
            options={k:(1 if k=='timeout' else [fixture_path('input')] if k=='input' else fixture_path(k)) for k in spec['required']}
            value=request(name,**options);ops.validate_provider_version(value,'0.5.0')
            Draft202012Validator(documents()['beaver-operation.schema.json']).validate(value)
            for old in ('0.3.0','0.4.0'):
                with self.subTest(name=name,old=old),self.assertRaises(ValueError):ops.validate_provider_version(value,old)
        # The inherited entry remains legal without enabling unrelated server routes.
        for old in ('0.3.0','0.4.0','0.5.0'):ops.validate_provider_version(request('project.inspect',project=fixture_path('project')),old)
        with self.assertRaises(ValueError):ops.validate(request('server.runtime-inspect',project=fixture_path('project')))

    def test_diagnostic_paths_preserve_order_and_repeat_cli_option(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp).resolve();a=str(base/'first log');b=str(base/'第二条.json')
            value=request('diagnostics.summarize',input=[a,b],limit=4)
            argv=ops.argv_for(value,str(base/'receipt'))
            self.assertEqual(argv[:6],['diagnostics','summarize','--input',a,'--input',b])
            self.assertEqual(argv[-2:],['--out',str(base/'receipt/provider-output')])
            Draft202012Validator(documents()['beaver-operation.schema.json']).validate(value)

    def test_diagnostics_reject_unbounded_or_untyped_paths_and_output(self):
        validator=Draft202012Validator(documents()['beaver-operation.schema.json'])
        for values in ([], fixture_path('file'), [1], [fixture_path('a')]*257):
            value=request('diagnostics.summarize',input=values)
            with self.subTest(values=str(values)[:30]):
                with self.assertRaises(ValueError):ops.validate(value)
                with self.assertRaises(ValidationError):validator.validate(value)
        for options in ({'input':['relative']},{'input':[fixture_path('bad')+'\x00']},{'input':[fixture_path('x')],'limit':True},{'input':[fixture_path('x')],'out':fixture_path('override')}):
            with self.subTest(options=options),self.assertRaises(ValueError):ops.validate(request('diagnostics.summarize',**options))

    def test_editor_inspection_requires_separate_outer_budget(self):
        value=request('ui.inspect',project=fixture_path('project'),spec=fixture_path('spec'),**{'editor-path':fixture_path('editor'),'timeout':25})
        with self.assertRaises(ValueError):ops.validate(value)
        value['timeout_seconds']=35;ops.validate(value)

    def test_new_result_preserves_changes_and_unknown_provider_data(self):
        value=dict(schemaVersion=1,contract='beaver-result/1',operationId='owned',
            producer=dict(name='beaver',version='0.5.0',implementationSha256=beaver.V03_CANDIDATES['0.5.0']['implementation_sha256']),
            status='partial',actualChanges=['Assets/A.prefab',{'field':'kept'}],artifacts=[],diagnostics=[],limitations=[],
            verification=dict(native='not_run',player='not_run',visual='not_run',business='not_run'),data={'caller_supplied':True})
        before=copy.deepcopy(value);validate_result(value);self.assertEqual(value,before)
