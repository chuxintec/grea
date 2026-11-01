import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from grea.common import digest, hash_file
from grea.integrations.monkey import pipeline, saved


class Dev1Tests(unittest.TestCase):
    def test_exact_package_and_capabilities_not_just_version(self):
        cfg=dict(version=pipeline.DEV1_VERSION, identity_root='/fixed', package_files={'/fixed/cli.py':'a'*64})
        cap=dict(implemented=['verify'])
        with patch.object(pipeline,'DEV1_PACKAGE_SHA256',digest({'cli.py':'a'*64})), patch.object(pipeline,'DEV1_CAPABILITIES_SHA256',digest(cap)):
            pipeline.validate_fixed_candidate(cfg, cap)
            with self.assertRaises(ValueError):pipeline.validate_fixed_candidate(dict(cfg,package_files={'/fixed/cli.py':'b'*64}),cap)
            with self.assertRaises(ValueError):pipeline.validate_fixed_candidate(cfg,dict(cap,implemented=['convert']))

    def test_saved_receipt_requires_hashes_and_v2_fixed_lock(self):
        with self.assertRaises(ValueError):saved.verify('unused','unused','unused','editor',None)
        with self.assertRaises(ValueError):saved.verify('unused','unused','unused','editor','a'*64)
        with self.assertRaises(ValueError):saved.verify('unused','unused','unused','static','a'*64,'b'*64)
        with patch.object(saved,'pinned',return_value=dict(schema_version=2,version='0.6.0')):
            with self.assertRaises(ValueError):saved.verify('unused','unused','unused','static','a'*64)

    def test_drift_refused_before_provider_execution(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);candidate=root/'candidate';candidate.mkdir();(candidate/'manifest.json').write_text('{}');(root/'lock').write_text('{}')
            cfg=dict(schema_version=2,version=pipeline.DEV1_VERSION)
            with patch.object(saved,'pinned',return_value=cfg),patch.object(saved.runner,'execute') as run:
                with self.assertRaises(ValueError):saved.verify(root/'lock',candidate,root/'out','static','a'*64)
                run.assert_not_called()

    def test_partial_saved_evidence_keeps_dynamic_boundary(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);candidate=root/'candidate';candidate.mkdir();(candidate/'manifest.json').write_text('{}');lock=root/'lock';lock.write_text('{}')
            manifest=hash_file(candidate/'manifest.json')['sha256'];out=root/'out'
            cfg=dict(schema_version=2,version=pipeline.DEV1_VERSION,identity_files=[])
            def execute(*a,**k):
                report=out/'provider-output';report.mkdir();(report/'verification.json').write_text(json.dumps(dict(schemaVersion=1,toolVersion=pipeline.DEV1_VERSION,candidateManifestSha256=manifest,staticValidation='pass',editorValidation='partial',businessValidation='not_run')))
                return dict(parsed_stdout={'status':'partial'},exit_code=1,capture_complete=True),None,None
            with patch.object(saved,'pinned',return_value=cfg),patch.object(saved,'probe'),patch.object(saved.runner,'execute',side_effect=execute):
                result=saved.verify(lock,candidate,out,'static',manifest)
            self.assertEqual(result['provider_exit_code'],1)
            self.assertEqual(result['verification']['editorValidation'],'partial')
            self.assertFalse(result['editor_started'])
            self.assertFalse(result['handoff_ready'])
            self.assertEqual(result['business_validation'],'not_run')
