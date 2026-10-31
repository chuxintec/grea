"""Shader evidence gates must not turn a local package or declarations into native proof."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema import Draft202012Validator
from grea.common import digest
from grea.integrations.monkey import shader
from grea.monkey_contracts import SHADER_HANDOFF_SCHEMA


class ShaderTests(unittest.TestCase):
    def test_same_version_without_fixed_capabilities_and_package_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();cap={'implemented':['classify-unity-shaders'],'unitySourceProfile':{'shaderHandoff':'monkey-shader-handoff/1'}}
            cfg={'version':'0.6.0','identity_root':str(root),'package_files':{str(root/'cli.py'):'a'*64}}
            with self.assertRaises(ValueError):shader.validate_candidate(cfg,cap)
            with patch.object(shader,'CAPABILITIES_SHA256',digest(cap)),patch.object(shader,'PACKAGE_SHA256',digest({'cli.py':'a'*64})):
                shader.validate_candidate(cfg,cap)
                for other in (dict(cfg,version='0.6.1'),dict(cfg,package_files={str(root/'cli.py'):'b'*64})):
                    with self.assertRaises(ValueError):shader.validate_candidate(other,cap)
                with self.assertRaises(ValueError):shader.validate_candidate(cfg,dict(cap,implemented=[]))

    def test_invalid_pins_and_mapping_pairs_never_launch_provider(self):
        with tempfile.TemporaryDirectory() as t, patch.object(shader.runner,'execute') as run:
            root=Path(t).resolve()
            for options in ({'expected_manifest':'bad'},{'source_mapping':str(root/'mapping')},{'expected_source_mapping':'a'*64},{'timeout_seconds':True}):
                values=dict(config=root/'lock',project=root,manifest=root/'owner',expected_manifest='a'*64,output=root/'out');values.update(options)
                with self.assertRaises(ValueError):shader.classify(**values)
            run.assert_not_called()

    def test_handoff_contract_rejects_compilation_claims_and_extra_top_level(self):
        validator=Draft202012Validator(SHADER_HANDOFF_SCHEMA)
        item=dict(path='Assets/Game/Content/Shaders/Test.shader',bytes=1,sha256='a'*64,classification='source-text',source={},target=None,dialect=None,platformEvidence=[],nativeCompilation='not_run',runtimeDisposition='source-review',evidenceId='fixture')
        self.assertTrue(validator.is_valid({'schema':'monkey-shader-handoff/1','items':[item]}))
        for value in ({'schema':'monkey-shader-handoff/1','items':[dict(item,nativeCompilation='passed')]},{'schema':'monkey-shader-handoff/1','items':[item],'native':'passed'}):
            self.assertFalse(validator.is_valid(value))
