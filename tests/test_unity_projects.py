"""M1 adversarial and behavior tests. Fixtures only, no Unity or real projects."""
import asyncio
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from grea.application import dispatch
from grea.common import package_root
from grea.contracts import catalog
from grea.unity_project_contracts import REFERENCE, documents
from grea.unity_projects import Reader

ROOT = package_root()
PROFILE_PATH = ROOT/'tests/fixtures/unity-project-v1.json'


def fingerprint(root):
    return {str(p.relative_to(root)): (p.lstat().st_mode, p.read_bytes() if p.is_file() else None)
            for p in root.rglob('*') if not p.is_symlink()}


class UnityProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='grea-工程 空格-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile = json.loads(PROFILE_PATH.read_text())
        self.save_profile()

    def save_profile(self):
        (self.root/'grea-project.json').write_text(json.dumps(self.profile, ensure_ascii=False, indent=2))

    def call(self, operation='validate_unity_project', mode='new', **kwargs):
        return dispatch(operation, {'project_root': str(self.root), 'mode': mode, **kwargs})

    def asset(self, rel, body=b'fixture', guid=None):
        p=self.root/'UnityProject'/rel
        for parent in reversed(list(p.parent.parents)):
            if parent == self.root/'UnityProject/Assets' or not parent.is_relative_to(self.root/'UnityProject/Assets'):
                continue
            parent.mkdir(exist_ok=True)
            Path(str(parent)+'.meta').write_text('guid: '+hashlib.md5(str(parent).encode()).hexdigest()+'\n')
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.parent != self.root/'UnityProject/Assets':
            Path(str(p.parent)+'.meta').write_text('guid: '+hashlib.md5(str(p.parent).encode()).hexdigest()+'\n')
        p.write_bytes(body)
        Path(str(p)+'.meta').write_text('fileFormatVersion: 2\nguid: '+(guid or hashlib.md5(rel.encode()).hexdigest())+'\n')
        return p

    def existing(self):
        project=self.root/'UnityProject'
        for name in ('Assets','Packages','ProjectSettings'):
            (project/name).mkdir(parents=True,exist_ok=True)
        (project/'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.6.2f1\n')
        dependencies=deepcopy(self.profile['toolchain']['packages'])
        (project/'Packages/manifest.json').write_text(json.dumps({'dependencies':dependencies}))
        (project/'Packages/packages-lock.json').write_text(json.dumps({'dependencies':{k:{'version':v,'source':'registry','depth':0} for k,v in dependencies.items()}}))
        self.pin_locks()
        for value in self.profile['scenes'].values():
            self.asset(value)
        return project

    def pin_locks(self):
        for name,key in [('manifest.json','manifestSha256'),('packages-lock.json','packagesLockSha256')]:
            self.profile['dependencyLock'][key]=hashlib.sha256((self.root/'UnityProject/Packages'/name).read_bytes()).hexdigest()
        self.save_profile()

    def finding_codes(self, result):
        self.assertNotEqual(result['status'],'error',result)
        return {x['code'] for x in result['result'].get('report',result['result'])['findings']}

    def test_new_plan_deterministic_read_only_and_schema_valid(self):
        before=fingerprint(self.root)
        one=self.call('plan_unity_project');two=self.call('plan_unity_project')
        self.assertEqual(one['status'],'ok',one)
        self.assertEqual(one['result'],two['result'])
        self.assertEqual(fingerprint(self.root),before)
        self.assertFalse((self.root/'UnityProject').exists())
        self.assertFalse(one['result']['generationReady'])
        self.assertEqual(one['result']['blockers'],['GENERATION_NOT_IMPLEMENTED'])
        self.assertTrue(one['result']['items'])
        Draft202012Validator(documents()['unity-plan.schema.json']).validate(one['result'])
        self.assertEqual(one['result']['report']['capability']['editor'],'not_run')

    def test_second_project_layout_and_absolute_cwd_independence(self):
        self.profile['paths']['unityProject']='游戏 工程'
        self.profile['projectId']='second-project';self.save_profile()
        before=fingerprint(self.root)
        args={'project_root':str(self.root),'mode':'new'}
        process=subprocess.run([str(ROOT/'bin/grea'),'plan-unity-project',json.dumps(args)],cwd='/tmp',capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr)
        expected=self.call('plan_unity_project')['result']
        self.assertEqual(json.loads(process.stdout)['result'],expected)
        self.assertEqual(fingerprint(self.root),before)

    def test_adopt_preserves_existing_files_and_names(self):
        self.existing();before=fingerprint(self.root)
        result=self.call('plan_unity_project',mode='adopt')
        self.assertEqual(result['status'],'ok',result)
        self.assertTrue(all(x['action']=='preserve' for x in result['result']['items']))
        self.assertEqual(fingerprint(self.root),before)

    def test_refactor_is_scoped_and_requires_real_baseline(self):
        self.existing();self.assertEqual(self.call(mode='refactor')['error']['code'],'BASELINE_REQUIRED')
        evidence=self.root/'Evidence';evidence.mkdir();(evidence/'baseline.json').write_text('{"scope":"fixture"}')
        before=fingerprint(self.root)
        result=self.call('plan_unity_project',mode='refactor',scope=['Assets/Game/Scenes'],baseline='Evidence/baseline.json')
        self.assertEqual(result['status'],'ok',result)
        self.assertTrue(all(x['action']=='review' and x['target'].startswith('UnityProject/Assets/Game/Scenes') for x in result['result']['items']))
        self.assertEqual(result['result']['baseline']['path'],'Evidence/baseline.json')
        self.assertEqual(fingerprint(self.root),before)

    def test_nonempty_new_target_is_never_overwritten(self):
        p=self.root/'UnityProject';p.mkdir();(p/'user.txt').write_text('keep')
        before=fingerprint(self.root)
        result=self.call('plan_unity_project')
        self.assertIn('TARGET_NOT_EMPTY',self.finding_codes(result))
        self.assertFalse(any(x['action']=='create' for x in result['result']['items']))
        self.assertEqual(fingerprint(self.root),before)

    def test_unknown_fields_booleans_and_strict_json(self):
        for mutate in [lambda p:p.update(unknown=True),lambda p:p.update(schemaVersion=True),lambda p:p['toolchain'].update(extra=1)]:
            original=deepcopy(self.profile);mutate(self.profile);self.save_profile()
            self.assertEqual(self.call()['error']['code'],'INVALID_PROFILE');self.profile=original
        for raw in ['{"a":1,"a":2}','{"a":NaN}','[]','{']:
            (self.root/'grea-project.json').write_text(raw)
            self.assertIn(self.call()['error']['code'],('INVALID_PROJECT_JSON','INVALID_PROFILE'))

    def test_unsupported_combination_template_and_framework(self):
        self.profile['toolchain']['ui']='uitk';self.profile['template']['id']='unknown'
        self.profile['frameworkPackages']=[{'name':'com.grea.foundation','version':'1.0.0','sha256':'0'*64}];self.save_profile()
        result=self.call('plan_unity_project')
        self.assertEqual(self.finding_codes(result),{'UNKNOWN_TEMPLATE','UNSUPPORTED_COMBINATION','FRAMEWORK_NOT_IMPLEMENTED'})
        self.assertEqual(result['result']['items'],[])
        self.assertEqual(result['result']['report']['capability']['staticPlanning'],'unsupported')

    def test_profile_semantic_and_module_contracts(self):
        original=deepcopy(self.profile)
        mutations=[lambda p:p.update(features=['unknown-feature']),
                   lambda p:p['modules'][0].update(layers=['Network']),
                   lambda p:p['modules'][0].update(name='class'),
                   lambda p:p.update(qaSaveNamespace=p['saveNamespace']),
                   lambda p:p.update(features=['ui','resources']),
                   lambda p:p['scenes'].update(entry='Assets/entry.txt')]
        for mutate in mutations:
            self.profile=deepcopy(original);mutate(self.profile);self.save_profile()
            self.assertEqual(self.call()['error']['code'],'INVALID_PROFILE')

    def test_recorded_editor_version_drift(self):
        project=self.existing()
        (project/'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.0.0f1\n')
        self.assertIn('EDITOR_VERSION_MISMATCH',self.finding_codes(self.call(mode='adopt')))

    def test_portable_path_traversal_and_overlapping_roots(self):
        original=deepcopy(self.profile)
        for bad in ['../escape','/tmp/escape','C:\\escape','NUL','a//b','a/../b','a.','a\\b']:
            self.profile=deepcopy(original);self.profile['paths']['unityProject']=bad;self.save_profile()
            self.assertEqual(self.call()['error']['code'],'INVALID_PROJECT_PATH',bad)
        for bad in ['UnityProject/Assets','Build']:
            self.profile=deepcopy(original);self.profile['paths']['evidenceRoot']=bad;self.save_profile()
            self.assertEqual(self.call()['error']['code'],'INVALID_PROFILE')
        self.profile=original;self.save_profile()
        self.assertEqual(self.call(profile='../outside.json')['error']['code'],'INVALID_PROJECT_PATH')

    def test_symlinks_in_targets_and_scan_are_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root/'UnityProject').symlink_to(outside,target_is_directory=True)
            self.assertEqual(self.call()['error']['code'],'UNSAFE_PROJECT_ENTRY')
            (self.root/'UnityProject').unlink();self.existing()
            (self.root/'UnityProject/Assets/linked').symlink_to(outside,target_is_directory=True)
            self.assertEqual(self.call(mode='adopt')['error']['code'],'UNSAFE_PROJECT_ENTRY')

    def test_case_and_unicode_collisions(self):
        self.profile['modules']=[{'name':'Example','layers':['Domain']},{'name':'example','layers':['Domain']}];self.save_profile()
        self.assertEqual(self.call()['error']['code'],'INVALID_PROFILE')
        self.profile=json.loads(PROFILE_PATH.read_text());self.save_profile();self.existing()
        # Works on case-insensitive hosts too: the algorithm is tested against an explicit observed inventory.
        from grea.unity_projects import _inventory_findings
        reader=Reader(self.root,100,100000,None)
        reader.identities={n:{'kind':'file','guid':None} for n in ['X/A.txt','X/a.txt','X/é.txt','X/e\u0301.txt']}
        findings=[]
        _inventory_findings(reader,lambda code,*a:findings.append(code),'UnityProject/Assets')
        self.assertEqual(findings.count('PATH_COLLISION'),2)

    def test_missing_and_modified_dependency_inputs(self):
        p=self.existing();(p/'Packages/packages-lock.json').unlink()
        self.assertIn('MISSING_DEPENDENCY',self.finding_codes(self.call(mode='adopt')))
        (p/'Packages/packages-lock.json').write_text('{"dependencies":{}}')
        result=self.call(mode='adopt')
        self.assertIn('DEPENDENCY_LOCK_MISMATCH',self.finding_codes(result))
        self.assertIn('MISSING_OR_MISMATCHED_PACKAGE',self.finding_codes(result))

    def test_direct_external_dependencies_not_resolved_or_executed(self):
        p=self.existing();manifest=p/'Packages/manifest.json';d=json.loads(manifest.read_text());d['dependencies']['com.example.external']='file:../../outside';manifest.write_text(json.dumps(d));self.pin_locks()
        self.assertIn('UNSUPPORTED_DEPENDENCY_SOURCE',self.finding_codes(self.call(mode='adopt')))

    def test_lock_cannot_hide_local_dependency_behind_a_version(self):
        p=self.existing();lock=p/'Packages/packages-lock.json';data=json.loads(lock.read_text())
        next(iter(data['dependencies'].values()))['source']='local'
        lock.write_text(json.dumps(data));self.pin_locks()
        self.assertIn('UNSUPPORTED_DEPENDENCY_SOURCE',self.finding_codes(self.call(mode='adopt')))

    def test_guid_conflict_and_missing_meta(self):
        self.existing();self.asset('Assets/a.asset',guid='a'*32);self.asset('Assets/b.asset',guid='a'*32)
        (self.root/'UnityProject/Assets/c.asset').write_text('no meta')
        codes=self.finding_codes(self.call(mode='adopt'))
        self.assertIn('DUPLICATE_GUID',codes);self.assertIn('MISSING_META',codes)

    def test_assembly_cycles_layers_and_editor_leak(self):
        self.existing()
        for folder,name,refs,platforms in [('Domain','Fixture.Domain',['Fixture.Services'],[]),('Services','Fixture.Services',['Fixture.Domain','Fixture.Editor'],[]),('Editor','Fixture.Editor',[],['Editor'])]:
            self.asset('Assets/'+folder+'/'+name+'.asmdef',json.dumps({'name':name,'references':refs,'includePlatforms':platforms,'noEngineReferences':True}).encode())
        codes=self.finding_codes(self.call(mode='adopt'))
        self.assertIn('ASSEMBLY_CYCLE',codes);self.assertIn('ASSEMBLY_LAYER_VIOLATION',codes);self.assertIn('RUNTIME_EDITOR_TEST_REFERENCE',codes)

    def test_guid_based_assembly_references_and_pure_rules(self):
        self.existing()
        self.asset('Assets/Domain/D.asmdef',json.dumps({'name':'Fixture.Domain','noEngineReferences':False}).encode(),guid='d'*32)
        self.asset('Assets/Gameplay/G.asmdef',json.dumps({'name':'Fixture.Gameplay','noEngineReferences':True,'references':['GUID:'+'d'*32]}).encode())
        codes=self.finding_codes(self.call(mode='adopt'))
        self.assertIn('ENGINE_DEPENDENT_RULES',codes);self.assertNotIn('UNRESOLVED_ASSEMBLY_REFERENCE',codes)

    def test_limits_and_cancellation_do_not_produce_complete_plan(self):
        self.existing();before=fingerprint(self.root)
        for limits in [{'max_files':1},{'max_bytes':1}]:
            self.assertEqual(self.call('plan_unity_project',mode='adopt',**limits)['error']['code'],'RESOURCE_LIMIT')
        cancel=threading.Event();cancel.set()
        result=dispatch('plan_unity_project',{'project_root':str(self.root),'mode':'adopt'},cancel)
        self.assertEqual(result['error']['code'],'CANCELLED');self.assertEqual(fingerprint(self.root),before)

    def test_stale_plan_on_profile_asset_meta_and_directory_changes(self):
        self.existing()
        for change in ['profile','asset','meta','directory']:
            first=self.call('plan_unity_project',mode='adopt')['result']['planId']
            if change=='profile':self.profile['projectId']='changed';self.save_profile()
            elif change=='asset':self.asset('Assets/new.asset')
            elif change=='meta':(self.root/'UnityProject/Assets/new.asset.meta').write_text('guid: '+'b'*32+'\n')
            else:(self.root/'UnityProject/Assets/empty').mkdir()
            self.assertEqual(self.call('plan_unity_project',mode='adopt',expected_plan_id=first)['error']['code'],'STALE_PLAN')

    def test_mid_read_change_detected(self):
        self.existing();original=Reader.recheck
        def mutate(reader):
            (self.root/'UnityProject/Assets/change.txt').write_text('concurrent')
            return original(reader)
        with patch.object(Reader,'recheck',mutate):
            self.assertEqual(self.call('plan_unity_project',mode='adopt')['error']['code'],'STALE_INPUT')

    def test_schemas_and_future_manifest_contract(self):
        for schema in documents().values():Draft202012Validator.check_schema(schema)
        manifest={'schemaVersion':1,'standardVersion':'1.0.0','projectId':'fixture','planId':'a'*64,'generatorVersion':'0.1.0','template':REFERENCE['template'],'previousManifestSha256':None,'files':[{'logicalId':'fixture','path':'Assets/a.asset','sha256':'b'*64,'metaSha256':'c'*64,'guid':'d'*32,'fileIds':['1'],'owner':'generated'}]}
        validator=Draft202012Validator(documents()['unity-manifest.schema.json']);validator.validate(manifest)
        manifest['files'][0]['owner']='unknown';self.assertTrue(list(validator.iter_errors(manifest)))

    def test_no_process_execution_and_no_nonstatic_level(self):
        with patch('subprocess.Popen', side_effect=AssertionError('No process allowed')):
            self.assertEqual(self.call('plan_unity_project')['status'], 'ok')
        result = self.call(level='Player')
        self.assertEqual(result['error']['code'], 'INVALID_ARGUMENTS')

    def test_duplicate_assembly_references_and_malformed_metadata_are_findings(self):
        self.existing()
        self.asset('Assets/Example.asmdef', json.dumps({'name':'Fixture.Domain','references':['Missing','Missing'],'noEngineReferences':True}).encode())
        (self.root/'UnityProject/Assets/Example.asmdef.meta').write_text('not a guid')
        (self.root/'UnityProject/Assets/orphan.meta').write_text('guid: '+'e'*32+'\n')
        codes=self.finding_codes(self.call(mode='adopt'))
        self.assertIn('UNRESOLVED_ASSEMBLY_REFERENCE', codes)
        self.assertIn('INVALID_META_GUID', codes)
        self.assertIn('ORPHAN_META', codes)

    @unittest.skipUnless(os.open in os.supports_dir_fd and hasattr(os, 'O_NOFOLLOW'), 'POSIX fd containment')
    def test_ancestor_symlink_race_does_not_read_external_file(self):
        self.existing();self.asset('Assets/value.asset')
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside)/'value.asset').write_text('external sentinel')
            reader=Reader(self.root,100,100000,None)
            original=reader.open_fd
            def swap(rel, directory=False):
                source=self.root/'UnityProject/Assets'
                source.rename(self.root/'SavedAssets')
                source.symlink_to(outside,target_is_directory=True)
                return original(rel,directory)
            with patch.object(reader,'open_fd',side_effect=swap):
                with self.assertRaises(OSError):reader.read('UnityProject/Assets/value.asset')
            self.assertEqual(reader.data,{})

    def test_only_read_only_operations_registered(self):
        by_name={x['name']:x for x in catalog()}
        self.assertNotIn('generate_unity_project',by_name)
        for name in ['plan_unity_project','validate_unity_project']:
            self.assertEqual(by_name[name]['effects'],['filesystem_read'])
            self.assertTrue(by_name[name]['annotations']['readOnlyHint'])
            self.assertTrue(by_name[name]['annotations']['idempotentHint'])
        self.assertEqual(dispatch('generate_unity_project',{})['error']['code'],'UNKNOWN_OPERATION')

    def test_mcp_cli_parity_for_success_findings_and_error(self):
        async def check():
            async with Client(StdioServerParameters(command=str(ROOT/'bin/grea'),args=['mcp']),read_timeout_seconds=20) as client:
                for mode,profile in [('new','grea-project.json'),('adopt','grea-project.json'),('new','../escape.json')]:
                    request={'project_root':str(self.root),'mode':mode,'profile':profile}
                    for operation in ['plan_unity_project','validate_unity_project']:
                        mcp=(await client.call_tool(operation,request)).structured_content
                        cli=subprocess.run([str(ROOT/'bin/grea'),operation.replace('_','-'),json.dumps(request)],capture_output=True,text=True,cwd='/tmp')
                        actual=json.loads(cli.stdout)
                        self.assertEqual(mcp['status'],actual['status']);self.assertEqual(mcp['result'],actual['result']);self.assertEqual(mcp['error'],actual['error'])
                        self.assertEqual(cli.returncode,{'ok':0,'partial':1,'error':2}[actual['status']])
        before=fingerprint(self.root);asyncio.run(check());self.assertEqual(before,fingerprint(self.root))


if __name__=='__main__':unittest.main()
