"""Stable module identity cannot widen the historically bounded dispatch."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from grea.common import digest
from grea.integrations.monkey import native_steps, pipeline


class StableMonkeyTests(unittest.TestCase):
    def test_stable_identity_rejects_payload_or_capability_drift(self):
        cfg = dict(version=pipeline.STABLE_VERSION, identity_root='/fixed',
                   package_files={'/fixed/cli.py': 'a' * 64})
        cap = dict(implemented=['verify'])
        with patch.object(pipeline, 'STABLE_PACKAGE_SHA256', digest({'cli.py': 'a' * 64})), \
             patch.object(pipeline, 'STABLE_CAPABILITIES_SHA256', digest(cap)):
            pipeline.validate_fixed_candidate(cfg, cap)
            for altered_cfg, altered_cap in (
                (dict(cfg, package_files={'/fixed/cli.py': 'b' * 64}), cap),
                (cfg, dict(cap, sourceExecution=True)),
            ):
                with self.assertRaises(ValueError):
                    pipeline.validate_fixed_candidate(altered_cfg, altered_cap)

    def test_stable_native_step_remains_audit_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = root / 'request.json'
            request.write_text(json.dumps(dict(schema_version=1,
                operation='upgrade-native-runtime', input_roots=[str(root)],
                options={'candidate': str(root), 'expected-manifest': 'a' * 64},
                timeout_seconds=30)))
            with patch.object(native_steps, 'pinned', return_value={
                    'schema_version': 2, 'version': pipeline.STABLE_VERSION}), \
                 patch.object(native_steps.runner, 'execute') as execute:
                with self.assertRaisesRegex(ValueError, 'audit only'):
                    native_steps.run('lock', request, root / 'out')
                execute.assert_not_called()
