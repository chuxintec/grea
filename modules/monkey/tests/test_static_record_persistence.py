import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from monkey.prefab_static_carriers import _unity_script


ROOT = Path(__file__).resolve().parents[1]


class UnityStaticRecordPersistenceTests(unittest.TestCase):
    def test_unity_sdk_compiles_static_field_binder_without_starting_editor(self):
        sdk = Path("/Applications/Unity/Hub/Editor/6000.6.2f1/Unity.app/Contents/Resources/Scripting/DotNetSdk/sdk/8.0.318/Roslyn/bincore/csc.dll")
        reference_path = os.environ.get("MONKEY_UNITY_TEST_REFERENCE_RSP")
        if not reference_path:
            self.skipTest("Set MONKEY_UNITY_TEST_REFERENCE_RSP for the local Unity SDK compile probe")
        references = Path(reference_path)
        dotnet = shutil.which("dotnet")
        if not sdk.is_file() or not references.is_file() or not dotnet:
            self.skipTest("Unity 6000.6.2f1 C# SDK and reference response are required")
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            output = directory / "UnityStaticFields.dll"
            refs = []
            for line in references.read_text(encoding="utf-8").splitlines():
                value = line.strip().strip('"')
                if value.startswith("-r:"):
                    refs.append('"' + value + '"')
            response = directory / "compile.rsp"
            response.write_text("\n".join([
                "-nologo", "-target:library", "-langversion:latest",
                '"-out:' + str(output) + '"', *refs,
                '"' + str(ROOT / "src/monkey/targets/UnityStaticFields.cs") + '"',
            ]) + "\n", encoding="utf-8")
            compiled = subprocess.run([dotnet, str(sdk), "@" + str(response)], capture_output=True, timeout=60, check=False)
            self.assertEqual(compiled.returncode, 0, (compiled.stdout + compiled.stderr).decode()[-3000:])
            self.assertTrue(output.is_file())

    def test_generated_unity_record_carrier_declares_serializable_rows_and_exact_ref_leaf(self):
        fields = [{
            "sourceFieldName": "entries", "fieldName": "__sf_000_entries",
            "kind": "array", "elementKind": "record", "storageType": "StaticRecord[]",
            "recordTypeName": "StaticRecord", "recordSchema": [
                {"sourceFieldName": "count", "fieldName": "__sf_000_count", "storageType": "double"},
                {"sourceFieldName": "node", "fieldName": "__sf_001_node", "storageType": "UnityEngine.Object"},
            ],
        }]
        source = _unity_script("Neutral", "Carrier", fields)
        self.assertIn("[Serializable]\n    public sealed class StaticRecord", source)
        self.assertIn("[SerializeField] public double __sf_000_count = 0d;", source)
        self.assertIn("[SerializeField] public UnityEngine.Object __sf_001_node = null;", source)
        self.assertIn("[SerializeField] public StaticRecord[] __sf_000_entries = Array.Empty<StaticRecord>();", source)

    def test_assign_readback_and_mismatch_for_two_record_array_types(self):
        dotnet = shutil.which("dotnet")
        if not dotnet:
            self.skipTest(".NET SDK unavailable")
        helper = (ROOT / "src/monkey/targets/UnityStaticFields.cs").resolve()
        source = r'''using System;using System.Reflection;
namespace UnityEngine {
 public class Object {}
 public struct Color32 { public byte r,g,b,a; public Color32(byte r,byte g,byte b,byte a){this.r=r;this.g=g;this.b=b;this.a=a;} }
 public class GameObject:Object { public object AddComponent(Type t)=>Activator.CreateInstance(t); }
 public class MonoBehaviour:Object { public bool enabled=true; }
 [AttributeUsage(AttributeTargets.Field)] public class SerializeField:Attribute{}
 [AttributeUsage(AttributeTargets.Field)] public class HideInInspector:Attribute{}
 public static class JsonUtility { public static string ToJson(object v)=>throw new Exception("record helper must not JSON-roundtrip nested plan rows"); public static T FromJson<T>(string v)=>throw new Exception("record helper must not JSON-roundtrip nested plan rows"); }
}
namespace Recovered {
 [Serializable] public sealed class FirstRow { public double count; public UnityEngine.Object node; }
 [Serializable] public sealed class SecondRow { public string label; public bool visible; }
 public sealed class Carrier:UnityEngine.MonoBehaviour { public string __monkeySourceId=""; public FirstRow[] first=Array.Empty<FirstRow>(); public SecondRow[] second=Array.Empty<SecondRow>(); }
 public sealed class Asset:UnityEngine.Object {}
}
namespace UnityEditor {
 public class MonoScript:UnityEngine.Object { public Type GetClass()=>typeof(Recovered.Carrier); public static MonoScript FromMonoBehaviour(UnityEngine.MonoBehaviour c)=>new MonoScript(); }
 public static class AssetDatabase { public static string GUIDToAssetPath(string g)=>"Assets/Game/Scripts/Presentation/Recovered/StaticFields/Carrier.cs"; public static T LoadAssetAtPath<T>(string p) where T:class=>new MonoScript() as T; public static string GetAssetPath(UnityEngine.Object o)=>"Assets/Game/Scripts/Presentation/Recovered/StaticFields/Carrier.cs"; public static string AssetPathToGUID(string p)=>"12345678123412341234123456789abc"; }
}
'''
        program = r'''
class Program {
 static UnityStaticFields.RecordFieldValueSpec Leaf(string source,string field,string storage,double number=0,string text="",bool flag=false,string refId=null) => new UnityStaticFields.RecordFieldValueSpec { sourceFieldName=source,fieldName=field,kind=storage,storageType=storage,numberValue=number,stringValue=text,boolValue=flag,refValue=refId,referenceKind=storage=="UnityEngine.Object"?"node_ref":"" };
 static UnityStaticFields.FieldSpec Record(string source,string field,string type,UnityStaticFields.RecordValueSpec[] rows) => new UnityStaticFields.FieldSpec { sourceFieldName=source,fieldName=field,kind="array",elementKind="record",recordTypeName=type,storageType=type+"[]",recordValues=rows };
 static UnityStaticFields.Spec Spec(string source,UnityStaticFields.FieldSpec[] fields) => new UnityStaticFields.Spec { sourceId=source,typeName="Recovered.Carrier",scriptGuid="12345678123412341234123456789abc",behavior="disabled",enabled=false,declarationDefaultsVerified=true,gaps=Array.Empty<string>(),fields=fields };
 static void Main(){
  var node=new Recovered.Asset();
  var first=Record("first","first","FirstRow",new[]{new UnityStaticFields.RecordValueSpec{index=0,fields=new[]{Leaf("count","count","double",3.5),Leaf("node","node","UnityEngine.Object",refId:"asset:node")}},new UnityStaticFields.RecordValueSpec{index=1,fields=new[]{Leaf("count","count","double",8),Leaf("node","node","UnityEngine.Object",refId:"asset:node")}}});
  var second=Record("second","second","SecondRow",new[]{new UnityStaticFields.RecordValueSpec{index=0,fields=new[]{Leaf("label","label","string",text:"kept"),Leaf("visible","visible","bool",flag:true)}}});
  var spec=Spec("neutral#1/components/0",new[]{first,second});var carrier=new Recovered.Carrier();var resolve=new Func<string,UnityEngine.Object>(id=>id=="asset:node"?node:null);
  var assigned=UnityStaticFields.Assign(spec,carrier,resolve);var read=UnityStaticFields.Read(spec,carrier,resolve);
  if(!assigned.fieldsAssigned||!read.fieldsVerified||!read.recordSpecStructureVerified||!read.nativeComplete)throw new Exception("records were not accepted: "+String.Join(",",read.gaps));
  if(carrier.first.Length!=2||carrier.first[0].count!=3.5||carrier.first[1].count!=8||!ReferenceEquals(carrier.first[1].node,node)||carrier.second.Length!=1||carrier.second[0].label!="kept"||!carrier.second[0].visible)throw new Exception("assigned arrays differ");
  carrier.first[0].node=new Recovered.Asset();var mismatch=UnityStaticFields.Read(spec,carrier,resolve);
  if(mismatch.fieldsVerified||!Array.Exists(mismatch.gaps,g=>g.Contains("record_reference_readback_mismatch")))throw new Exception("wrong node reference passed readback");
  var malformed=Spec("neutral#bad/components/0",new[]{Record("first","first","FirstRow",new[]{new UnityStaticFields.RecordValueSpec{index=1,fields=new[]{Leaf("count","count","double",3)}}})});
  var rejected=UnityStaticFields.Assign(malformed,new Recovered.Carrier(),resolve);
  if(rejected.fieldsAssigned||!Array.Exists(rejected.gaps,g=>g.Contains("record_array_spec_invalid")))throw new Exception("malformed row order passed");
  Console.WriteLine("ok");
 }
}'''
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "Probe.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>disable</Nullable><EnableDefaultCompileItems>false</EnableDefaultCompileItems></PropertyGroup><ItemGroup><Compile Include="Probe.cs"/><Compile Include="UnityStaticFields.cs"/></ItemGroup></Project>'
            )
            (directory / "NuGet.Config").write_text('<configuration><packageSources><clear /></packageSources></configuration>')
            (directory / "Probe.cs").write_text(source + program)
            shutil.copy2(helper, directory / "UnityStaticFields.cs")
            restore = subprocess.run([dotnet, "restore", str(directory / "Probe.csproj"), "--configfile", str(directory / "NuGet.Config")], capture_output=True, text=True, check=False)
            self.assertEqual(restore.returncode, 0, restore.stdout + restore.stderr)
            result = subprocess.run([dotnet, "run", "--project", str(directory / "Probe.csproj"), "--no-restore"], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), "ok")


if __name__ == "__main__":
    unittest.main()
