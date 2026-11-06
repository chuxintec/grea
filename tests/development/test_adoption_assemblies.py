import shutil
import tempfile
import unittest
from pathlib import Path
from grea.development.adoption import preview,build_plan,prepare
from grea.development.adoption_assemblies import importer_roles
from grea.development.io import read,load,write_json,sha
from grea.development.errors import BeaverError
from .helpers import finish
from .test_adoption import candidate
from .test_managed_metadata import managed_dll


def meta(guid,role):
    any_on=role!='editor';editor=role!='player'
    return ('fileFormatVersion: 2\nguid: '+guid+'\nPluginImporter:\n  externalObjects: {}\n  platformData:\n'
        '  - first:\n      Any:\n    second:\n      enabled: '+str(int(any_on))+'\n      settings:\n        Exclude Editor: '+str(int(not editor))+'\n'
        '  - first:\n      Editor: Editor\n    second:\n      enabled: '+str(int(editor))+'\n      settings:\n        CPU: AnyCPU\n').encode()


def add(root,path,name='Sdk',guid='a'*32,role='editor',type_name='Widget'):
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(managed_dll(name,type_name=type_name));Path(str(p)+'.meta').write_bytes(meta(guid,role))


def freeze(root,policy=None):
    m=load(read(root/'manifest.json'));m.pop('files',None)
    if policy:m['managedAssemblyPolicy']=dict(schemaVersion=1,strategy='explicit-disjoint-role-pairs',assemblies=policy)
    finish(root,m)


def pin(root,path,guid,role):
    return dict(path=path,guid=guid,sha256=sha((root/path).read_bytes()),metaSha256=sha((root/(path+'.meta')).read_bytes()),role=role+'-only')


class AssemblyAdoptionTests(unittest.TestCase):
    def fixture(self,w):
        b=candidate(w/'base');a=w/'after';shutil.copytree(b,a);t=w/'target';shutil.copytree(b,t)
        return b,a,t

    def test_renamed_same_assembly_and_other_assembly_same_type_block_without_writes(self):
        for name in ('Sdk','DifferentName'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                w=Path(tmp).resolve();b,a,t=self.fixture(w);add(t,'Assets/Legacy/old.dll',role='both');add(a,'Assets/New/renamed.dll',name=name,guid='b'*32,role='both');freeze(a)
                r=preview(a,t,w/'plan',b);self.assertEqual(r['status'],'blocked')
                self.assertTrue(any('managed-sdk' in c['reason'] for c in load(read(w/'plan/adoption-plan.json'))['conflicts']))
                with self.assertRaises(BeaverError):prepare(w/'plan/adoption-plan.json',w/'transaction')
                self.assertFalse((w/'transaction').exists());self.assertFalse((t/'Assets/New').exists())

    def test_clean_explicit_disjoint_pair_plans_stages_and_stale_role_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            w=Path(tmp).resolve();b,a,t=self.fixture(w)
            paths=['Assets/Sdk/Editor/sdk.dll','Assets/Sdk/Player/sdk.dll'];roles=['editor','player'];guids=['a'*32,'b'*32]
            for p,g,r in zip(paths,guids,roles):add(a,p,guid=g,role=r)
            freeze(a);self.assertEqual(build_plan(a,t,b)['managedAssemblyCompatibility']['status'],'blocked')
            freeze(a,[pin(a,p,g,r) for p,g,r in zip(paths,guids,roles)])
            r=preview(a,t,w/'plan',b);self.assertEqual(r['status'],'planned')
            stage,plan,journal=prepare(w/'plan/adoption-plan.json',w/'stage');self.assertTrue((stage/'after/0/file').exists())
            # Staging is not native adoption and has not created either DLL.
            self.assertFalse((t/paths[0]).exists())
            add(t,'Assets/Other/late.dll',name='Late',type_name='Other')
            with self.assertRaises(BeaverError):prepare(w/'plan/adoption-plan.json',w/'stale')

    def test_explicit_pair_cannot_shadow_retained_sdk_or_replace_existing_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            w=Path(tmp).resolve();b,a,t=self.fixture(w);old='Assets/Canonical/old.dll';new='Assets/New/editor.dll'
            add(t,old,guid='a'*32,role='player');add(a,new,guid='b'*32,role='editor')
            freeze(a,[pin(t,old,'a'*32,'player'),pin(a,new,'b'*32,'editor')])
            p=build_plan(a,t,b);self.assertIn('managed-sdk-existing-identity-needs-native-migration',[c['reason'] for c in p['conflicts']])
        with tempfile.TemporaryDirectory() as tmp:
            w=Path(tmp).resolve();b,a,t=self.fixture(w);path='Assets/Canonical/sdk.dll'
            for root in (b,t):add(root,path,role='editor')
            freeze(b);add(a,path,role='editor',type_name='Changed');freeze(a)
            self.assertIn('managed-sdk-existing-replacement-needs-native-migration',[c['reason'] for c in build_plan(a,t,b)['conflicts']])

    def test_unknown_native_dll_importer_and_false_pin_block(self):
        for fault in ('native','missing-importer','wrong-role-pin','define-constraint'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp:
                w=Path(tmp).resolve();b,a,t=self.fixture(w);p='Assets/Sdk/sdk.dll';add(a,p)
                if fault=='native':(a/p).write_bytes(b'not-managed')
                if fault=='missing-importer':(a/(p+'.meta')).write_text('guid: '+'a'*32+'\n')
                if fault=='define-constraint':
                    q=a/(p+'.meta');q.write_bytes(q.read_bytes()+b'  defineConstraints:\n  - UNITY_EDITOR\n')
                pins=[pin(a,p,'a'*32,'player')] if fault=='wrong-role-pin' else None
                freeze(a,pins);self.assertTrue(build_plan(a,t,b)['conflicts'])

    def test_same_scope_explicit_pins_do_not_override_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            w=Path(tmp).resolve();b,a,t=self.fixture(w);paths=['Assets/Sdk/one.dll','Assets/Sdk/two.dll'];guids=['a'*32,'b'*32]
            for p,g in zip(paths,guids):add(a,p,guid=g)
            freeze(a,[pin(a,p,g,'editor') for p,g in zip(paths,guids)])
            self.assertIn('managed-sdk-assembly-or-type-scope-collision',[c['reason'] for c in build_plan(a,t,b)['conflicts']])

    def test_importer_unknown_platform_constraints_and_default_are_not_guessed(self):
        self.assertEqual(importer_roles(meta('a'*32,'editor')),['editor'])
        self.assertEqual(importer_roles(meta('a'*32,'player')),['player'])
        self.assertEqual(importer_roles(meta('a'*32,'both')),['editor','player'])
        self.assertIsNone(importer_roles(b'guid: '+b'a'*32))
        self.assertIsNone(importer_roles(meta('a'*32,'editor').replace(b'AnyCPU',b'ARM64')))
        self.assertIsNone(importer_roles(meta('a'*32,'player').replace(b'Exclude Editor',b'Exclude Linux')))
        constrained=meta('a'*32,'player').replace(b'Exclude Editor: 1',b'Exclude Editor: 1\n        CPU: x86_64')
        self.assertIsNone(importer_roles(constrained))

    def test_unity_native_keyed_platform_map_allows_disabled_extra_but_blocks_enabled_extra(self):
        base=(b'fileFormatVersion: 2\nguid: '+b'a'*32+b'\nPluginImporter:\n  externalObjects: {}\n  serializedVersion: 3\n'
              b'  defineConstraints: []\n  platformData:\n    Any:\n      enabled: 0\n      settings: {}\n'
              b'    Editor:\n      enabled: 1\n      settings:\n        DefaultValueInitialized: true\n        CPU: AnyCPU\n'
              b'    WindowsStoreApps:\n      enabled: 0\n      settings:\n        CPU: AnyCPU\n')
        self.assertEqual(importer_roles(base),['editor'])
        self.assertIsNone(importer_roles(base.replace(b'WindowsStoreApps:\n      enabled: 0',b'WindowsStoreApps:\n      enabled: 1')))

    def test_different_assemblies_can_have_same_internal_generated_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            w=Path(tmp).resolve();b,a,t=self.fixture(w)
            for index,name in enumerate(('First','Second')):
                p='Assets/Sdk/'+name+'.dll';add(a,p,name=name,guid=str(index+3)*32)
                (a/p).write_bytes(managed_dll(name,type_name='GeneratedHelper',type_visibility=0))
            freeze(a);self.assertFalse(build_plan(a,t,b)['conflicts'])

    def test_policy_cannot_use_boolean_version_or_unknown_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            w=Path(tmp).resolve();b,a,t=self.fixture(w);add(a,'Assets/Sdk/one.dll');freeze(a)
            m=load(read(a/'manifest.json'));m['managedAssemblyPolicy']=dict(schemaVersion=True,strategy='explicit-disjoint-role-pairs',assemblies=[]);write_json(a/'manifest.json',m)
            with self.assertRaises(BeaverError):build_plan(a,t,b)


if __name__=='__main__':unittest.main()
