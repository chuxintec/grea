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

ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.environ.get('GREA_ASSEMBLY_AUDIT_INTEGRATION')=='1','Explicit .NET/Cecil integration; no automatic SDK/dependency install')
class PlayerAuditIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name).resolve();cls.env=dict(os.environ,DOTNET_CLI_HOME=str(cls.root/'.dotnet'),NUGET_PACKAGES=str(cls.root/'.nuget'),DOTNET_GENERATE_ASPNET_CERTIFICATE='false',DOTNET_CLI_TELEMETRY_OPTOUT='1')
        cls.sentinel=cls.root/'MUST_NOT_EXIST'
        for name,code in [('Alpha','namespace Own { public class State { public class Nested {} public static void Commit() {} } }'),
                          ('Beta','namespace Own { public class Other { public string SaveJson; public static void Call() { State.Commit(); } static Other(){System.IO.File.WriteAllText('+json.dumps(str(cls.sentinel))+',"executed");} } }')]:
            folder=cls.root/name;folder.mkdir();(folder/'Fixture.cs').write_text(code)
            reference='<ItemGroup><ProjectReference Include="../Alpha/Alpha.csproj" /></ItemGroup>' if name=='Beta' else ''
            (folder/(name+'.csproj')).write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>'+reference+'</Project>')
            subprocess.run(['dotnet','build',str(folder/(name+'.csproj')),'--nologo','-v:q'],env=cls.env,check=True,capture_output=True)
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

if __name__=='__main__':unittest.main()
