import unittest
from unittest.mock import patch
from grea.integrations.monkey.selection import freeze
from grea.integrations.monkey import pipeline
from grea.common import digest
class SelectionTests(unittest.TestCase):
    def test_wrong_hash_and_unsafe_selection_rejected_before_execution(self):
        for prefabs,h in [(['Assets/A.prefab'],'bad'),(['../A.prefab'],'a'*64),(['Assets/A.prefab','Assets/A.prefab'],'a'*64)]:
            with patch('grea.integrations.monkey.selection.runner.execute') as run:
                with self.assertRaises(ValueError):freeze('lock','candidate',prefabs,h,'b'*64,'out')
                run.assert_not_called()
    def test_dev2_requires_exact_package_and_caps(self):
        cfg=dict(version=pipeline.DEV2_VERSION,identity_root='/pkg',package_files={'/pkg/cli.py':'a'*64});cap=dict(implemented=['verify','freeze-native-selection'])
        with patch.object(pipeline,'DEV2_PACKAGE_SHA256',digest({'cli.py':'a'*64})),patch.object(pipeline,'DEV2_CAPABILITIES_SHA256',digest(cap)):
            pipeline.validate_fixed_candidate(cfg,cap)
            with self.assertRaises(ValueError):pipeline.validate_fixed_candidate(dict(cfg,package_files={'/pkg/cli.py':'b'*64}),cap)
