"""Metadata integration uses only two own compiled fixtures; never loads inspected DLLs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from grea.tools.unity_player_audit import audit, AuditError
from grea.native_exit_contracts import documents, MAX_PLAYER_ASSEMBLIES
from jsonschema import Draft202012Validator


class PlayerManifestContracts(unittest.TestCase):
    def test_complete_set_capacity_uses_the_same_schema_limit(self):
        self.assertEqual(MAX_PLAYER_ASSEMBLIES, 256)
        schema = Draft202012Validator(documents()['unity-player-manifest.schema.json'])
        for count in (0, 128, 129, 162, 256, 257):
            with self.subTest(count=count):
                value = dict(schema_version=1, build_id='own', source_sha256='a'*64,
                             platform='synthetic', backend='Mono',
                             assemblies=[dict(path=f'Own{i}.dll', sha256='b'*64) for i in range(count)])
                self.assertEqual(schema.is_valid(value), 1 <= count <= 256)

ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.environ.get('GREA_ASSEMBLY_AUDIT_INTEGRATION')=='1','Explicit .NET/Cecil integration; no automatic SDK/dependency install')
class PlayerAuditIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name).resolve();cls.env=dict(os.environ,DOTNET_CLI_HOME=str(cls.root/'.dotnet'),NUGET_PACKAGES=str(cls.root/'.nuget'),DOTNET_GENERATE_ASPNET_CERTIFICATE='false',DOTNET_CLI_TELEMETRY_OPTOUT='1')
        # Own fixtures use only installed SDK reference packs; no package feeds.
        (cls.root/'NuGet.Config').write_text('<configuration><packageSources><clear /></packageSources></configuration>')
        cls.sentinel=cls.root/'MUST_NOT_EXIST'
        for name,code in [('Alpha','namespace Own { public class State { public class Nested {} public static void Commit() {} } }'),
                          ('Beta','namespace Own { public class Other { public string SaveJson; public static void Call() { State.Commit(); } static Other(){System.IO.File.WriteAllText('+json.dumps(str(cls.sentinel))+',"executed");} } }')]:
            folder=cls.root/name;folder.mkdir();(folder/'Fixture.cs').write_text(code)
            reference='<ItemGroup><ProjectReference Include="../Alpha/Alpha.csproj" /></ItemGroup>' if name=='Beta' else ''
            (folder/(name+'.csproj')).write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>'+reference+'</Project>')
            result=subprocess.run(['dotnet','build',str(folder/(name+'.csproj')),'--nologo','-v:q'],env=cls.env,capture_output=True,text=True)
            if result.returncode:
                raise RuntimeError('Own metadata fixture compilation failed: '+result.stdout+result.stderr)
        cls.managed=cls.root/'Beta/bin/Debug/net8.0'

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def manifest(self):
        import hashlib
        d=dict(schema_version=1,build_id='own-build-001',source_sha256='a'*64,platform='synthetic-net8',backend='Mono',
               assemblies=[dict(path=n+'.dll',sha256=hashlib.sha256((self.managed/(n+'.dll')).read_bytes()).hexdigest()) for n in ('Alpha','Beta')])
        file=self.root/'manifest.json';file.write_text(json.dumps(d));return file

    def test_nested_types_calls_references_and_no_static_constructor_execution(self):
        report=audit(self.manifest(),self.managed,{'schema_version':1,'required_types':['Own.State/Nested','Own.Other'],'forbidden_types':[],'forbidden_references':[],'call_types':['Own.Other']})
        self.assertEqual(report['status'],'metadata_checks_passed')
        self.assertFalse(self.sentinel.exists())
        calls=[c['target'] for a in report['assemblies'] for t in a['types'] for c in t['calls']]
        self.assertTrue(any('Own.State::Commit' in c for c in calls))
        self.assertTrue(any(a['references'] for a in report['assemblies']))

    def test_forbidden_reference_and_corrupt_extra_payload_are_rejected(self):
        manifest=self.manifest()
        policy={'schema_version':1,'required_types':['Own.Other'],'forbidden_references':['Alpha'],'call_types':[]}
        self.assertEqual(audit(manifest,self.managed,policy)['status'],'fail')
        assembly_policy={'schema_version':1,'required_types':['Own.Other'],'forbidden_assemblies':['Alpha']}
        self.assertEqual(audit(manifest,self.managed,assembly_policy)['status'],'fail')
        import hashlib,shutil
        folder=self.root/'corrupt-payload';folder.mkdir(exist_ok=True)
        for n in ('Alpha','Beta'):shutil.copyfile(self.managed/(n+'.dll'),folder/(n+'.dll'))
        (folder/'Broken.dll').write_bytes(b'not a PE assembly')
        d=json.loads(manifest.read_text());d['assemblies'].append({'path':'Broken.dll','sha256':hashlib.sha256((folder/'Broken.dll').read_bytes()).hexdigest()});manifest.write_text(json.dumps(d))
        with self.assertRaises(AuditError) as error:audit(manifest,folder,policy)
        self.assertEqual(error.exception.code,'METADATA_READ_ERROR')
        manifest=self.manifest()
        with self.assertRaises(AuditError) as error:audit(manifest,folder,policy)
        self.assertEqual(error.exception.code,'PAYLOAD_SET_MISMATCH')

    def test_missing_required_type_bad_identity_and_il2cpp_never_green(self):
        manifest=self.manifest()
        report=audit(manifest,self.managed,{'schema_version':1,'required_types':['Missing.Type'],'forbidden_types':['Own.Other'],'forbidden_references':[],'call_types':[]})
        self.assertEqual(report['status'],'fail')
        d=json.loads(manifest.read_text());d['assemblies'][0]['sha256']='0'*64;manifest.write_text(json.dumps(d))
        with self.assertRaises(AuditError):audit(manifest,self.managed,{'schema_version':1})
        d['backend']='IL2CPP';manifest.write_text(json.dumps(d))
        with self.assertRaises(AuditError) as error:audit(manifest,self.managed,{'schema_version':1})
        self.assertEqual(error.exception.code,'UNSUPPORTED_BACKEND')

    def test_full_large_payloads_and_rejected_truncation_identity_and_limits(self):
        import hashlib, shutil
        policy = {'schema_version':1, 'required_types':['Own.State/Nested','Own.Other'],
                  'call_types':['Own.Other']}
        # Two real compiled metadata shapes, renamed files, no inspected IL execution.
        for count in (128, 129, 162, 256):
            with self.subTest(count=count):
                folder=self.root/f'payload-{count}';folder.mkdir()
                rows=[]
                for index in range(count):
                    source=self.managed/('Alpha.dll' if index%2==0 else 'Beta.dll')
                    dest=folder/f'Own{index:03}.dll';shutil.copyfile(source,dest)
                    rows.append(dict(path=dest.name,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
                manifest=self.root/f'payload-{count}.json'
                body=dict(schema_version=1,build_id=f'own-{count}',source_sha256='a'*64,
                          platform='synthetic-net8',backend='Mono',assemblies=rows)
                manifest.write_text(json.dumps(body))
                report=audit(manifest,folder,policy)
                self.assertEqual(report['status'],'metadata_checks_passed')
                self.assertEqual(len(report['assemblies']),count)
                self.assertFalse(self.sentinel.exists())
                # Dropping DLLs from the manifest is never a capacity workaround.
                body['assemblies']=rows[:-1];manifest.write_text(json.dumps(body))
                with self.assertRaises(AuditError) as error:audit(manifest,folder,policy)
                self.assertEqual(error.exception.code,'PAYLOAD_SET_MISMATCH')
                body['assemblies']=rows;rows[0]['sha256']='0'*64;manifest.write_text(json.dumps(body))
                with self.assertRaises(AuditError) as error:audit(manifest,folder,policy)
                self.assertEqual(error.exception.code,'SOURCE_IDENTITY_MISMATCH')
        body['assemblies']=[dict(path=f'Overflow{i}.dll',sha256='a'*64) for i in range(257)]
        manifest.write_text(json.dumps(body))
        with self.assertRaises(AuditError) as error:audit(manifest,folder,policy)
        self.assertEqual(error.exception.code,'INVALID_MANIFEST')

    def test_byte_budget_still_rejects_oversized_sparse_input(self):
        folder=self.root/'over-byte-budget';folder.mkdir()
        file=folder/'Huge.dll'
        with file.open('wb') as stream:stream.truncate(64*1024*1024+1)
        manifest=self.root/'over-byte-budget.json'
        manifest.write_text(json.dumps(dict(schema_version=1,build_id='own-large',source_sha256='a'*64,
            platform='synthetic',backend='Mono',assemblies=[dict(path=file.name,sha256='0'*64)])))
        with self.assertRaises(AuditError) as error:audit(manifest,folder,{'schema_version':1,'required_types':['Own.Other']})
        self.assertEqual(error.exception.code,'ASSEMBLY_BUDGET')

if __name__=='__main__':unittest.main()
