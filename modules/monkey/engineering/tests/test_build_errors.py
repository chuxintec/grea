"""A successful-looking native summary cannot certify a build with errors."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from beaver.unity import plan, apply
from beaver.io import write_json, load, read
from beaver.errors import BeaverError
from test_adoption import candidate


class BuildErrorCertificationTests(unittest.TestCase):
    def execute(self, root, native):
        project=candidate(root/'project');(project/'Assets/Main.unity').write_bytes(b'synthetic scene')
        spec=root/'spec.json';write_json(spec,dict(schemaVersion=1,operation='build.macos',scenes=['Assets/Main.unity'],productName='Example'))
        planned=plan(project,spec,root/'plan');stage=root/'transaction'
        def run(*args):
            (stage/'player').mkdir();(stage/'player/test.bin').write_bytes(b'synthetic artifact')
            return dict(status='verified',developmentBuild=False,**native)
        with patch('beaver.unity.editor_path',return_value=root/'Unity'),patch('beaver.unity.native_lock'),patch('beaver.unity._install_native_helper',return_value=(root/'helper','hash')),patch('beaver.unity._remove_native_helper'),patch('beaver.unity.run',side_effect=run):
            return apply(planned['report'],stage,root/'Unity',planned['planSha256'])

    def test_succeeded_zero_errors_can_certify(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();result=self.execute(root,dict(buildResult='Succeeded',buildErrors=0))
            self.assertEqual(result['status'],'verified')
            self.assertTrue((root/'transaction/artifact-manifest.json').exists())
            self.assertEqual(load(read(root/'transaction/journal.json'))['status'],'complete')

    def test_errors_missing_invalid_or_failed_summary_cannot_certify(self):
        reports=[dict(buildResult='Succeeded',buildErrors=value) for value in [2,-1,False,True,0.0,'0',None,[],{}]]
        reports += [dict(buildResult='Succeeded'),dict(buildErrors=0),dict(buildResult='Failed',buildErrors=0)]
        for native in reports:
            with self.subTest(native=native),tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve()
                with self.assertRaises(BeaverError) as caught:self.execute(root,native)
                self.assertEqual(caught.exception.code,'BUILD_RESULT_ERRORS')
                self.assertFalse((root/'transaction/artifact-manifest.json').exists())
                journal=load(read(root/'transaction/journal.json'))
                self.assertEqual(journal['status'],'recovery-required')
                self.assertEqual(journal['diagnostic']['code'],'BUILD_RESULT_ERRORS')
