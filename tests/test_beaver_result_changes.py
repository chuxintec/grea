"""Regression for the real post-execution actualChanges path-list rejection."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from grea.beaver_contracts import validate_result
from grea.integrations import beaver, beaver_operations as ops


PATHS=['Assets/Game/ViewA.cs','Assets/Game/ViewB.cs','Assets/Game/StorageView.cs','Assets/Game/Tests/ViewTests.cs']


def payload(changes):
    return dict(schemaVersion=1,contract='beaver-result/1',operationId='recorded-shape-fixture',
        producer=dict(name='beaver',version='0.3.0',implementationSha256=beaver.V03_CANDIDATES['0.3.0']['implementation_sha256']),
        status='ok',actualChanges=changes,artifacts=[],diagnostics=[],limitations=[],
        verification=dict(native='saved_and_reloaded_same_editor',player='not_run',visual='not_run',business='not_run'),
        data=dict(status='verified',changes=changes,nativeReadback='saved_and_reloaded_same_editor'))


class BeaverResultChangesTests(unittest.TestCase):
    def test_real_path_list_and_existing_object_shapes_are_preserved(self):
        for changes in (PATHS,[dict(operation='adoption.apply',transaction='/receipt')],[PATHS[0],dict(operation='production.recover',restored=4)]):
            with self.subTest(changes=changes):validate_result(payload(changes))

    def test_malformed_change_rows_still_fail(self):
        for row in (None,False,1,1.5,[], ''):
            with self.subTest(row=row),self.assertRaises(ValueError):validate_result(payload([row]))

    def invoke_recorded_shape(self, actual):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp).resolve();plan=root/'plan.json';plan.write_text(json.dumps(dict(contract='beaver-production/3',schemaVersion=3)))
            req=root/'request.json';req.write_text(json.dumps(dict(schema_version=1,operation='production.apply',options={'plan':str(plan),'expected-plan':'a'*64,'editor-path':'/not-a-live-editor','timeout':1},timeout_seconds=30)))
            cfg=dict(identity_root='/package',package_files={'file':'hash'},command=['/beaver'],command_files={'cmd':'hash'},version='0.3.0')
            lock=root/'lock.json';lock.write_text(json.dumps(cfg))
            def checked(output,**kwargs):
                probe=Path(output)/'probe';probe.mkdir(parents=True)
                (probe/'run.json').write_text(json.dumps({'parsed_stdout':dict(producer=actual['producer'],data={'capabilities':[dict(id='production.plan/apply/recover',state='requires_provider')]})}))
                return {'ready':True}
            with patch('grea.integrations.monkey.local.readiness',return_value={'ready':True}),patch.object(beaver,'check',side_effect=checked),patch.object(beaver,'package_identity',return_value=cfg['package_files']),patch.object(beaver,'command_identity',return_value=cfg['command_files']),patch('grea.runner.execute',return_value=({'parsed_stdout':actual,'capture_complete':True,'exit_code':0},[],None))as run:
                result=ops.invoke(lock,req,root/'receipt');return result,run.call_count

    def test_completed_production_path_list_is_not_rejected_or_retried(self):
        value,calls=self.invoke_recorded_shape(payload(PATHS))
        self.assertEqual(calls,1);self.assertTrue(value['executed']);self.assertEqual(value['status'],'ok')
        self.assertEqual(value['native'],'saved_and_reloaded_same_editor');self.assertEqual(value['gameplay'],'not_run')
        self.assertEqual(value['provider_result']['actualChanges'],PATHS)

    def test_post_execution_validation_failure_is_not_reported_as_zero_execution(self):
        value,calls=self.invoke_recorded_shape(payload([1]))
        self.assertEqual(calls,1);self.assertTrue(value['executed']);self.assertEqual(value['status'],'needs_action')
        self.assertEqual(value['native'],'unverified');self.assertIn('Do not replay automatically',value['next_action'])
        self.assertEqual(value['provider_result']['actualChanges'],[1])
        self.assertEqual(value['provider_result']['verification']['native'],'saved_and_reloaded_same_editor')


if __name__=='__main__':unittest.main()
