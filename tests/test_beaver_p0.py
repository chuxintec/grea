"""Finite P0 dispatch: fixed producer, owned output and honest blocked results."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema import Draft202012Validator
from grea.integrations import beaver, beaver_operations as ops
from grea.beaver_contracts import documents


class P0Tests(unittest.TestCase):
    def test_candidate_requires_exact_identity_and_three_groups(self):
        value=dict(version=beaver.P0_VERSION, **beaver.V03_CONTRACTS,
                   producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_VERSION]['implementation_sha256'],
                   capabilities=[dict(id=n,state='implemented') for n in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS|beaver.V05_GROUPS|beaver.P0_GROUPS)])
        beaver.validate_capabilities(value)
        for missing in beaver.P0_GROUPS:
            bad=copy.deepcopy(value);bad['capabilities']=[x for x in bad['capabilities'] if x['id']!=missing]
            with self.assertRaises(ValueError):beaver.validate_capabilities(bad)
        for change in ({'version':'0.5.1'},{'producer_implementation_sha256':'0'*64}):
            with self.assertRaises(ValueError):beaver.validate_capabilities(dict(value,**change))

    def test_fix1_is_pinned_and_preserves_initial_candidate(self):
        value=dict(version=beaver.P0_FIX1_VERSION, **beaver.V03_CONTRACTS,
                   producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX1_VERSION]['implementation_sha256'],
                   capabilities=[dict(id=n,state='implemented') for n in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS|beaver.V05_GROUPS|beaver.P0_GROUPS)])
        beaver.validate_capabilities(value)
        with self.assertRaises(ValueError):
            beaver.validate_capabilities(dict(value,producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_VERSION]['implementation_sha256']))
        for name in ('structure.inspect','structure.plan','build-filter.collect','build-filter.plan','native.readback','ui.inspect'):
            self.assertTrue(beaver.P0_VERSIONS <= ops.OPERATIONS[name]['versions'])

    def test_fix2_requires_its_own_producer(self):
        cap=dict(version=beaver.P0_FIX2_VERSION, **beaver.V03_CONTRACTS,
                 producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX2_VERSION]['implementation_sha256'],
                 capabilities=[dict(id=n,state='implemented') for n in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS|beaver.V05_GROUPS|beaver.P0_GROUPS)])
        beaver.validate_capabilities(cap)
        for old in (beaver.P0_VERSION,beaver.P0_FIX1_VERSION):
            with self.assertRaises(ValueError):
                beaver.validate_capabilities(dict(cap,producer_implementation_sha256=beaver.V03_CANDIDATES[old]['implementation_sha256']))
        for op in ('structure.inspect','structure.plan'):
            self.assertIn(beaver.P0_FIX2_VERSION,ops.OPERATIONS[op]['versions'])

    def test_fix3_options_are_paired_and_version_gated(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();options={'project':str(root/'Unity'),'product-root':str(root),'profile':str(root/'grea-project.json')}
            req=dict(schema_version=1,operation='structure.inspect',options=options,timeout_seconds=30)
            ops.validate_provider_version(req,beaver.P0_FIX3_VERSION)
            validator=Draft202012Validator(documents()['beaver-operation.schema.json'])
            self.assertTrue(validator.is_valid(req))
            for key in ('profile','product-root'):
                broken=dict(req,options={k:v for k,v in options.items() if k!=key})
                with self.assertRaises(ValueError):ops.validate(broken)
                self.assertFalse(validator.is_valid(broken))
            for old in (beaver.P0_VERSION,beaver.P0_FIX1_VERSION,beaver.P0_FIX2_VERSION):
                with self.assertRaises(ValueError):ops.validate_provider_version(req,old)

    def test_full_profile_schema_and_safe_parent_discovery(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();project=root/'UnityProject';project.mkdir()
            path=root/'grea-project.json';data=json.loads((Path(__file__).parent/'fixtures/unity-project-v1.json').read_text());path.write_text(json.dumps(data))
            values={'project':str(project),'product-root':str(root),'profile':str(path)}
            self.assertEqual(ops.structure_profile(values)['path'],str(path))
            self.assertEqual(ops.structure_profile({'project':str(project)})['path'],str(path))
            data.pop('toolchain');path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'Invalid full GREA'):ops.structure_profile(values)
            path.write_text(json.dumps({'paths':[]}))
            with self.assertRaises(ValueError):ops.structure_profile(values)
            path.write_text(json.dumps({'paths':{'unityProject':'../outside'}}))
            with self.assertRaises(ValueError):ops.structure_profile(values)

    def test_routes_match_cli_and_do_not_unlock_old_versions(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve()
            for name in ('structure.inspect','structure.plan','build-filter.collect','build-filter.plan','native.readback'):
                spec=ops.OPERATIONS[name]
                options={k:1 if k=='timeout' else str(root/k) for k in spec['required']}
                req=dict(schema_version=1,operation=name,options=options,timeout_seconds=30)
                ops.validate_provider_version(req,beaver.P0_VERSION)
                Draft202012Validator(documents()['beaver-operation.schema.json']).validate(req)
                argv=ops.argv_for(req,root/'receipt')
                self.assertEqual(argv[:2],name.split('.'))
                self.assertEqual(argv[-2:],['--out',str(root/'receipt/provider-output')])
                for old in ('0.3.0','0.4.0','0.5.0'):
                    with self.assertRaises(ValueError):ops.validate_provider_version(req,old)
                with self.assertRaises(ValueError):ops.validate(dict(req,options=dict(options,out=str(root/'override'))))
                if 'timeout' in options:
                    with self.assertRaises(ValueError):ops.validate(dict(req,timeout_seconds=10))

    def test_blocked_result_keeps_classification_and_is_never_replayed(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve()
            req=dict(schema_version=1,operation='build-filter.plan',options={k:str(root/k) for k in ('project','snapshot','sources')},timeout_seconds=30)
            req['options']['target']=str(root/'target.json')
            request=root/'request.json';request.write_text(json.dumps(req))
            cfg=dict(version=beaver.P0_VERSION,command=[str(root/'beaver')],identity_root=str(root/'package'),package_files={},command_files={})
            lock=root/'lock.json';lock.write_text(json.dumps(cfg))
            actual=dict(schemaVersion=1,contract='beaver-result/1',operationId='fixture',producer=dict(name='beaver',version=beaver.P0_VERSION,implementationSha256=beaver.V03_CANDIDATES[beaver.P0_VERSION]['implementation_sha256']),status='blocked',actualChanges=[],artifacts=[],diagnostics=[],limitations=[],verification=dict(native='not_run',player='not_run',visual='not_run',business='not_run'),data={'mode':'plan-only','classification':['unknown'],'execution':{'status':'blocked'}})
            def check(out,**kw):
                probe=Path(out)/'probe';probe.mkdir(parents=True)
                (probe/'run.json').write_text(json.dumps({'parsed_stdout':dict(producer=actual['producer'],data={'capabilities':[{'id':'build-filter.collect/plan','state':'requires_provider'}]})}))
                return {'ready':True}
            with patch('grea.integrations.monkey.local.readiness',return_value={'ready':True}),patch.object(beaver,'check',side_effect=check),patch.object(beaver,'package_identity',return_value={}),patch.object(beaver,'command_identity',return_value={}),patch('grea.runner.execute',return_value=({'parsed_stdout':actual,'capture_complete':True,'exit_code':3},[],None)) as run:
                result=ops.invoke(lock,request,root/'out')
            self.assertEqual(run.call_count,1)
            self.assertEqual(result['status'],'blocked')
            self.assertEqual(result['provider_result'],actual)
            self.assertEqual(result['gameplay'],'not_run')
