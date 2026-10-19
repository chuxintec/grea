"""Compile/execute the Editor companion against own API stubs, never a Unity process.

This verifies bounded IO/rollback control flow only, not actual Unity APIs/imports.
"""
import json,os,shutil,subprocess,unittest
from pathlib import Path
import test_theme_assets as fixtures
from grea.tools.theme_assets import create

STUBS=r'''
using System;using System.IO;using System.Text.Json;
namespace UnityEngine {
 public static class Application { public static string dataPath => Path.Combine(Environment.GetEnvironmentVariable("GREA_THEME_TEST_ROOT"),"Assets"); }
 public class Sprite { public V pivot=new V(8,8),rect=new V(16,16),border=new V(2,2); public float pixelsPerUnit=100; }
 public class V { public float x,y,z=2,w=2,width,height;public V(float a,float b){x=width=a;y=height=b;} }
 public static class Mathf {public static float Abs(float f)=>Math.Abs(f);}
 public static class JsonUtility { public static T FromJson<T>(string s)=>JsonSerializer.Deserialize<T>(s,new JsonSerializerOptions{IncludeFields=true});public static string ToJson<T>(T value,bool pretty)=>JsonSerializer.Serialize(value,new JsonSerializerOptions{IncludeFields=true,WriteIndented=pretty}); }
}
namespace UnityEditor {
 public static class PlayerSettings {public static string productName="Derived";}
 public enum SpriteImportMode {Single,Multiple}
 public enum ImportAssetOptions {ForceSynchronousImport=1,ForceUpdate=2}
 public class AssetImporter {public static AssetImporter GetAtPath(string p)=>new TextureImporter();}
 public class TextureImporter:AssetImporter {public SpriteImportMode spriteImportMode=SpriteImportMode.Single;public void GetSourceTextureWidthAndHeight(out int w,out int h){w=h=16;}}
 public static class AssetDatabase {
  public static T LoadAssetAtPath<T>(string p) where T:class => new UnityEngine.Sprite() as T;
  public static bool TryGetGUIDAndLocalFileIdentifier(object s,out string guid,out long id){guid=new string('1',32);id=21300000;return true;}
  public static string AssetPathToGUID(string p)=>new string('1',32);
  public static void ImportAsset(string p,ImportAssetOptions o){if(Environment.GetEnvironmentVariable("GREA_THEME_TEST_FAIL_IMPORT")=="1")throw new InvalidOperationException("Own simulated import failure");}
 }
}
class Program {static int Main(){try{Grea.Tools.ThemeAssetApply.Run();return 0;}catch(Exception e){Console.Error.WriteLine(e.Message);return 1;}}}
'''

@unittest.skipUnless(os.environ.get('GREA_THEME_EDITOR_HARNESS')=='1','Explicit own .NET stub harness; no Unity/SDK install')
class EditorControlFlow(unittest.TestCase):
    setUp=fixtures.ThemeFixtures.setUp
    sha=fixtures.ThemeFixtures.sha
    save=fixtures.ThemeFixtures.save
    def test_apply_idempotence_partial_failure_rollback_and_foreign_edit(self):
        code=self.root/'stub';code.mkdir();(code/'NuGet.Config').write_text('<configuration><packageSources><clear /></packageSources></configuration>')
        (code/'Stub.cs').write_text(STUBS)
        shutil.copyfile(Path(__file__).resolve().parents[1]/'tools/unity/audit/ThemeAssetApply.cs',code/'ThemeAssetApply.cs')
        (code/'Harness.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework><OutputType>Exe</OutputType></PropertyGroup></Project>')
        env=dict(os.environ,DOTNET_CLI_HOME=str(self.root/'.dotnet'),NUGET_PACKAGES=str(self.root/'.nuget'),DOTNET_GENERATE_ASPNET_CERTIFICATE='false',DOTNET_CLI_TELEMETRY_OPTOUT='1',GREA_THEME_TEST_ROOT=str(self.project))
        build=subprocess.run(['dotnet','build',str(code/'Harness.csproj'),'--nologo','-v:q'],capture_output=True,text=True,env=env)
        self.assertEqual(build.returncode,0,build.stdout+build.stderr)
        bundle=self.root/'bundle';create(self.project,self.art,self.manifest,bundle)
        exe=code/'bin/Debug/net8.0/Harness.dll'
        def run(action,name,fail=False):
            report=self.root/(name+'.json');args=['dotnet',str(exe),'-greaThemeBundle',str(bundle),'-greaThemeAction',action,'-greaThemeReport',str(report)]
            process=subprocess.run(args,capture_output=True,text=True,env=dict(env,GREA_THEME_TEST_FAIL_IMPORT='1' if fail else '0'))
            return process,json.loads(report.read_text())
        original=self.target.read_bytes();meta=self.meta.read_bytes()
        p,r=run('apply','first',True);self.assertEqual(p.returncode,1);self.assertEqual(r['outcomes'][0]['state'],'attempted')
        self.assertNotEqual(self.target.read_bytes(),original)
        p,r=run('rollback','recover');self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(self.target.read_bytes(),original)
        p,r=run('apply','apply');self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(r['outcomes'][0]['state'],'verified')
        p,r=run('apply','same');self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(r['outcomes'][0]['state'],'unchanged')
        p,r=run('rollback','rollback');self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(self.target.read_bytes(),original);self.assertEqual(self.meta.read_bytes(),meta)
        self.target.write_bytes(b'foreign local edit')
        p,r=run('apply','foreign');self.assertEqual(p.returncode,1);self.assertEqual(r['outcomes'],[]);self.assertEqual(self.target.read_bytes(),b'foreign local edit')
