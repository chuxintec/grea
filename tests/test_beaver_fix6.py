import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema import Draft202012Validator
from grea.common import hash_file
from grea.integrations import beaver,beaver_operations as ops
from grea.beaver_contracts import documents


class Fix6Tests(unittest.TestCase):
    def test_exact_producer_and_retirement_group_required(self):
        cap=dict(version=beaver.P0_FIX6_VERSION,**beaver.V03_CONTRACTS,
            producer_implementation_sha256=beaver.V03_CANDIDATES[beaver.P0_FIX6_VERSION]['implementation_sha256'],
            capabilities=[dict(id=n,state='implemented') for n in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS|beaver.V05_GROUPS|beaver.P0_GROUPS|{'unity.assets.retire/recover'})])
        beaver.validate_capabilities(cap)
        for field,value in [('producer_implementation_sha256',beaver.V03_CANDIDATES[beaver.P0_FIX3_VERSION]['implementation_sha256']),('capabilities',[r for r in cap['capabilities'] if r['id']!='unity.assets.retire/recover'])]:
            with self.assertRaises(ValueError):beaver.validate_capabilities(dict(cap,**{field:value}))

    def test_summary_and_consumer_declarations_are_fixed_version_options(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();req=dict(schema_version=1,operation='structure.plan',options={'audit':str(root/'audit'),'mappings':str(root/'mappings'),'consumer-resolutions':str(root/'resolutions'),'summary':True},timeout_seconds=30)
            ops.validate_provider_version(req,beaver.P0_FIX6_VERSION)
            self.assertTrue(Draft202012Validator(documents()['beaver-operation.schema.json']).is_valid(req))
            for old in ('0.5.0',beaver.P0_FIX3_VERSION):
                with self.assertRaises(ValueError):ops.validate_provider_version(req,old)
            argv=ops.argv_for(req,root/'receipt');self.assertIn('--summary',argv);self.assertIn('--consumer-resolutions',argv)

    def test_retirement_apply_and_recover_use_the_explicit_capability(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();plan=root/'plan.json';plan.write_text(json.dumps({'contract':'beaver-unity/1','spec':{'operation':'assets.retire'}}))
            self.assertEqual(ops.required_capability({'operation':'unity.apply','options':{'plan':str(plan)}}),'unity.assets.retire/recover')
            req=dict(schema_version=1,operation='unity.recover',options={'transaction':str(root/'transaction'),'expected-plan':'a'*64,'editor-path':str(root/'editor'),'timeout':1,'summary':True},timeout_seconds=30)
            ops.validate_provider_version(req,beaver.P0_FIX6_VERSION)
            argv=ops.argv_for(req,root/'receipt');self.assertEqual(argv[:2],['unity','recover']);self.assertNotIn('--out',argv)
            with self.assertRaises(ValueError):ops.validate_provider_version(req,beaver.P0_FIX3_VERSION)

    def test_summary_requires_matching_artifact_and_preserves_native_details(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t).resolve()/'full.json';path.write_text('{"complete":"evidence"}')
            actual={'status':'partial','artifacts':[hash_file(path)]};before=copy.deepcopy(actual)
            self.assertEqual(ops.verify_summary_artifacts(actual)[0]['sha256'],actual['artifacts'][0]['sha256']);self.assertEqual(actual,before)
            path.write_text('changed')
            with self.assertRaises(ValueError):ops.verify_summary_artifacts(actual)
            with self.assertRaises(ValueError):ops.verify_summary_artifacts({'status':'partial','artifacts':[]})

    def test_partial_exit_one_is_preserved_with_complete_summary_artifact(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();report=root/'report.json';report.write_text('{"coverage":{"complete":false}}');version=beaver.P0_FIX6_VERSION
            actual=dict(schemaVersion=1,contract='beaver-result/1',operationId='fixture',producer=dict(name='beaver',version=version,implementationSha256=beaver.V03_CANDIDATES[version]['implementation_sha256']),status='partial',actualChanges=[],artifacts=[hash_file(report)],diagnostics=[],limitations=[],verification=dict(native='read_only_native_snapshot',player='not_run',visual='not_run',business='not_run'),data={'report':str(report),'coverage':{'complete':False},'detailStorage':'complete-report-file'})
            req=root/'request.json';req.write_text(json.dumps(dict(schema_version=1,operation='build-filter.collect',options={'project':str(root/'project'),'spec':str(root/'spec'),'editor-path':str(root/'editor'),'timeout':1,'summary':True},timeout_seconds=30)))
            cfg=dict(version=version,command=[str(root/'beaver')],identity_root=str(root/'package'),package_files={},command_files={});lock=root/'lock.json';lock.write_text(json.dumps(cfg))
            def check(out,**kw):
                probe=Path(out)/'probe';probe.mkdir(parents=True);(probe/'run.json').write_text(json.dumps({'parsed_stdout':{'producer':actual['producer'],'data':{'capabilities':[{'id':'build-filter.collect/plan','state':'requires_provider'}]}}}));return {'ready':True}
            with patch('grea.integrations.monkey.local.readiness',return_value={'ready':True}),patch.object(beaver,'check',side_effect=check),patch.object(beaver,'package_identity',return_value={}),patch.object(beaver,'command_identity',return_value={}),patch('grea.runner.execute',return_value=({'parsed_stdout':actual,'capture_complete':True,'exit_code':1},[],None)) as run:
                result=ops.invoke(lock,req,root/'out')
            self.assertEqual(run.call_count,1);self.assertEqual(result['status'],'partial');self.assertEqual(result['provider_result'],actual);self.assertEqual(result['gameplay'],'not_run');self.assertEqual(len(result['provider_artifacts_verified']),1)
