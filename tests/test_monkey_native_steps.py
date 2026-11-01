import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from grea.integrations.monkey import native_steps as n
class NativeStepsTests(unittest.TestCase):
    def test_finite_named_options_and_hashes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for operation,spec in n.SPECS.items():
                opts={k:str(root) if typ=='path' else 'a'*64 for k,typ in spec.items()}
                q=dict(schema_version=1,operation=operation,options=opts,input_roots=[str(root)],timeout_seconds=30)
                argv,_=n.validate(q);self.assertEqual(argv[0],operation)
                with self.assertRaises(ValueError):n.validate(dict(q,options=dict(opts,**{'executeMethod':'Injected'})))
                with self.assertRaises(ValueError):n.validate(dict(q,timeout_seconds=True))
    def test_external_option_and_overlapping_roots_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);child=root/'source';child.mkdir()
            q=dict(schema_version=1,operation='upgrade-native-runtime',options={'candidate':str(root),'expected-manifest':'a'*64},input_roots=[str(child)],timeout_seconds=30)
            with self.assertRaises(ValueError):n.validate(q)
            with self.assertRaises(ValueError):n.validate(dict(q,input_roots=[str(root),str(child)]))
    def test_wrong_version_refused_before_provider_call(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);q=root/'request.json';q.write_text(json.dumps(dict(schema_version=1,operation='upgrade-native-runtime',options={'candidate':str(root),'expected-manifest':'a'*64},input_roots=[str(root)],timeout_seconds=30)))
            with patch.object(n,'pinned',return_value={'schema_version':2,'version':'0.7.0.dev2'}),patch.object(n.runner,'execute') as run:
                with self.assertRaises(ValueError):n.run('lock',q,root/'out')
                run.assert_not_called()

    def test_dependency_supplement_cannot_change_parent_identity(self):
        with self.assertRaises(ValueError):n.audit_dependency_result({'schema':'monkey-native-code-dependency-supplement/1','targetManifestSha256':'b'*64},{'expected-manifest':'a'*64,'expected-producer-manifest':'c'*64},Path('/fixture'))
