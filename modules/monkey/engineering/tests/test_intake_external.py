"""Exact retained-resource/package planning and recovery preconditions."""
import tempfile
import unittest
from pathlib import Path

from beaver.errors import BeaverError
from beaver.intake import build_plan, recheck
from beaver.intake_external import recheck_packages
from beaver.io import sha, write_json
from test_intake import _candidate, _project, _spec, _write_asset

RESOURCE = '7'*32
PACKAGE = '8'*32


class RetainedDependencyTests(unittest.TestCase):
    def fixture(self, base):
        c = _candidate(base/'candidate', [('Assets/New.txt', b'guid: '+RESOURCE.encode(), '1'*32),
                                         ('Assets/Shared.txt', b'shared', RESOURCE)])
        t = _project(base/'target', [('Assets/Owned.txt', b'shared', RESOURCE)])
        s = _spec(c, additions=[dict(source='Assets/New.txt',target='Assets/New.txt')])
        s.update(schemaVersion=2, externalAssets=[dict(source='Assets/Shared.txt',target='Assets/Owned.txt',guid=RESOURCE,
            sha256=sha(b'shared'),metaSha256=sha((t/'Assets/Owned.txt.meta').read_bytes()),
            objects=[dict(localId=4900000,type='UnityEngine.TextAsset',assembly='UnityEngine.CoreModule',name='Owned',fields=[])],reason='Exact existing pair')],packageScripts=[])
        p=base/'spec.json';write_json(p,s)
        return c,t,s,p

    def error(self, code, fn, *args):
        with self.assertRaises(BeaverError) as caught: fn(*args)
        self.assertEqual(caught.exception.code,code)

    def test_exact_pair_satisfies_dependency_and_creates_only_new(self):
        with tempfile.TemporaryDirectory() as d:
            c,t,s,p=self.fixture(Path(d).resolve());plan=build_plan(c,t,p)
            self.assertEqual(plan['contract'],'beaver-additive-intake/2')
            self.assertEqual(len(plan['additions']),1)
            self.assertEqual(plan['externalAssets'],s['externalAssets'])
            (t/'Assets/Owned.txt').write_bytes(b'later edit')
            self.error('INTAKE_EXTERNAL_BYTES',recheck,plan)

    def test_different_candidate_meta_cannot_be_blessed_by_target_pin(self):
        with tempfile.TemporaryDirectory() as d:
            c,t,s,p=self.fixture(Path(d).resolve());s['externalAssets'][0]['metaSha256']='0'*64;write_json(p,s)
            self.error('INTAKE_EXTERNAL_BYTES',build_plan,c,t,p)

    def test_duplicate_target_guid_refused(self):
        with tempfile.TemporaryDirectory() as d:
            c,t,s,p=self.fixture(Path(d).resolve());_write_asset(t,'Assets/Duplicate.txt',b'shared',RESOURCE)
            self.error('INTAKE_EXTERNAL_IDENTITY',build_plan,c,t,p)

    def test_undeclared_guid_remains_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            c,t,s,p=self.fixture(Path(d).resolve());s['externalAssets']=[];write_json(p,s)
            self.error('INTAKE_DEPENDENCY_CLOSURE',build_plan,c,t,p)

    def package(self,t):
        root=t/'Library/PackageCache/com.unity.ugui@abc';root.mkdir(parents=True)
        write_json(root/'package.json',dict(name='com.unity.ugui',version='2.6.0'))
        _write_asset(root,'Runtime/Button.cs',b'// official neutral fixture',PACKAGE)
        write_json(t/'Packages/manifest.json',dict(dependencies={'com.unity.ugui':'2.6.0'}))
        write_json(t/'Packages/packages-lock.json',dict(dependencies={'com.unity.ugui':dict(version='2.6.0',source='builtin')}))
        return dict(target='Packages/com.unity.ugui/Runtime/Button.cs',guid=PACKAGE,type='UnityEngine.UI.Button',assembly='UnityEngine.UI',
                    localId=11500000,name='Button',packageName='com.unity.ugui',packageVersion='2.6.0',packageSource='builtin',
                    packageJsonSha256=sha((root/'package.json').read_bytes()),sha256=sha((root/'Runtime/Button.cs').read_bytes()),
                    metaSha256=sha((root/'Runtime/Button.cs.meta').read_bytes()),reason='Pinned official package')

    def test_exact_package_and_cache_tree_are_guarded(self):
        with tempfile.TemporaryDirectory() as d:
            c,t,s,p=self.fixture(Path(d).resolve());row=self.package(t)
            write_json(c/'Packages/manifest.json',dict(dependencies={'com.unity.ugui':'2.6.0'}))
            from helpers import finish
            finish(c, dict(schemaVersion=1,targetProfile='unity-6000.6.2f1-ugui',namespace='test-game',projectLayout='monkey-project/2.0.0',scopeMode='whole-input',diagnostics=[]))
            s['candidateManifestSha256']=sha((c/'manifest.json').read_bytes());s['packageScripts']=[row];write_json(p,s)
            plan=build_plan(c,t,p);recheck_packages(plan)
            (t/'Library/PackageCache/com.unity.ugui@abc/Other.cs').write_text('// later change')
            self.error('INTAKE_PACKAGE_DRIFT',recheck_packages,plan)

    def test_nonofficial_registry_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            c,t,s,p=self.fixture(Path(d).resolve());row=self.package(t);row['packageSource']='registry'
            write_json(t/'Packages/packages-lock.json',dict(dependencies={'com.unity.ugui':dict(version='2.6.0',source='registry',url='https://other.invalid')}))
            from beaver.intake_external import package_scripts
            self.error('INTAKE_PACKAGE_SOURCE',package_scripts,dict(packageScripts=[row]),t,{})


if __name__=='__main__':unittest.main()
