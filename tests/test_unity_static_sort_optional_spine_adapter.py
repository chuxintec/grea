import tempfile
import unittest
from pathlib import Path
import shutil
import subprocess

from fixtures import fixture
from monkey.io import load, read
from monkey.layout import standard
from monkey.normalize import normalize
from monkey.sources.bundle import inspect
from monkey.sources.compiled import ParseError
from monkey.targets import unity


ROOT = Path(__file__).resolve().parents[1]


def declaration(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


def statement(source, signature):
    start = source.index(signature)
    end = source.index(";", start) + 1
    return source[start:end]


class OptionalSpineAdapterTests(unittest.TestCase):
    def test_default_no_spine_export_omits_sdk_adapter(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            config = fixture(root / "source")
            inspect(config, [2], root / "inspect")
            normalize(root / "inspect/source-manifest.json", root / "ir")
            plan = unity.plan(root / "ir/ir.json", "optional-spine-no-spine", root / "plan")
            self.assertFalse(plan.get("staticSpineRendering"))
            self.assertFalse(any(row.get("type") == "sp.Skeleton" for row in plan["components"]))

            unity.export(root / "plan/plan.json", root / "candidate")
            adapter_path = root / "candidate" / standard.unity("importer") / "UnityStaticSortSpineBinding.cs"
            self.assertFalse(adapter_path.exists())
            import_plan = load(read(root / "candidate" / standard.unity("importPlan")))
            self.assertIsNone(import_plan.get("staticSpineRenderingJson"))

    def test_export_selector_requires_a_real_nonempty_rendering_contract(self):
        self.assertFalse(unity._requires_cocos_static_spine_adapter({}))
        valid = {
            "schemaVersion": 1,
            "contract": "monkey-static-spine-rendering/1",
            "sourceManifestSha256": "a" * 64,
            "components": [{"sourceComponentId": "source-spine", "sourceDataAssetId": "source-data"}],
            "dataAssets": [{"sourceDataAssetId": "source-data"}],
        }
        self.assertTrue(unity._requires_cocos_static_spine_adapter({"staticSpineRendering": valid}))
        with self.assertRaises(ParseError):
            unity._requires_cocos_static_spine_adapter({"sourceManifestSha256": "b" * 64,
                                                        "staticSpineRendering": valid})
        for fragment in (
            {},
            {"schemaVersion": 1, "contract": "monkey-static-spine-rendering/1", "components": [], "dataAssets": []},
            {"schemaVersion": 1, "contract": "wrong", "components": [{"sourceComponentId": "s"}],
             "dataAssets": [{"sourceDataAssetId": "d"}]},
        ):
            with self.subTest(fragment=fragment), self.assertRaises(ParseError):
                unity._requires_cocos_static_spine_adapter({"staticSpineRendering": fragment})

    def test_sdk_free_queue_signal_fails_closed_and_adapter_keeps_typed_factory(self):
        proxy = (ROOT / "src/monkey/targets/UnityStaticSortQueueProxy.cs").read_text()
        adapter = (ROOT / "src/monkey/targets/UnityStaticSortSpineBinding.cs").read_text()
        self.assertNotIn("using Spine.Unity;", proxy)
        self.assertNotIn("using Monkey.Targets.Spine;", proxy)
        self.assertIn("RegisterOptionalCocosStaticSpineIdentityResolver();", proxy)
        self.assertIn('cocos-static-spine-required-adapter-missing', proxy)
        self.assertIn("applicable = true;", proxy)
        self.assertIn("staticSpineRenderingJson", proxy)
        self.assertIn("static partial void RegisterOptionalCocosStaticSpineIdentityResolver()", adapter)
        self.assertIn("UnitySpineNativeFactory.ReadDataAssetAsset(factorySpec)", adapter)
        self.assertIn("actualDataAsset as SkeletonDataAsset", adapter)

    def test_sdk_free_optional_registration_is_fail_closed_for_a_present_render_plan(self):
        dotnet = shutil.which("dotnet")
        if not dotnet:
            self.skipTest("dotnet SDK unavailable")
        proxy = (ROOT / "src/monkey/targets/UnityStaticSortQueueProxy.cs").read_text()
        signatures = (
            "[Serializable] sealed class CocosStaticSpineImportPlanSignal",
            "[Serializable] sealed class CocosStaticSpineRenderingSignal",
            "[Serializable] sealed class CocosStaticSpineRenderingSignalComponent",
            "[Serializable] sealed class CocosStaticSpineRenderingSignalData",
            "static bool TryReadCocosStaticSpineDataIdentity(",
        )
        members = "\n".join(declaration(proxy, signature) for signature in signatures)
        members += "\n" + statement(proxy, "delegate bool CocosStaticSpineIdentityResolver(")
        members += "\n" + "\n".join(line.strip() for line in proxy.splitlines()
            if line.strip().startswith(("static CocosStaticSpineIdentityResolver cocosStaticSpineIdentityResolver;",
                                        "static partial void RegisterOptionalCocosStaticSpineIdentityResolver();",
                                        "const string CocosStaticSpineImportPlanPath =",
                                        "const string CocosStaticSpineRenderingContract =")))
        program = r'''
static void Require(bool good,string message){if(!good)throw new Exception(message);}
static string Encode(object value)=>JsonSerializer.Serialize(value,new JsonSerializerOptions{IncludeFields=true});
static void Main(){
    var project=Path.Combine(Path.GetTempPath(),"creator-spine-signal-"+Guid.NewGuid().ToString("N"));
    var data=Path.Combine(project,"Assets");Directory.CreateDirectory(data);Application.dataPath=data;
    var planPath=Path.Combine(project,CocosStaticSpineImportPlanPath);Directory.CreateDirectory(Path.GetDirectoryName(planPath));
    var spec=new ProxyQueueSpec{sourceManifestSha256=new string('a',64)};
    SpineDataIdentityEvidence evidence;string diagnostic;bool applicable;
    Require(!TryReadCocosStaticSpineDataIdentity(spec,"source-component",new UnityEngine.Object(),out evidence,out diagnostic,out applicable,null)
        && !applicable,"missing import plan is outside the optional static route");
    File.WriteAllText(planPath,Encode(new CocosStaticSpineImportPlanSignal{sourceManifestSha256=spec.sourceManifestSha256}));
    Require(!TryReadCocosStaticSpineDataIdentity(spec,"source-component",new UnityEngine.Object(),out evidence,out diagnostic,out applicable,null)
        && !applicable,"empty static rendering field selects the existing non-Cocos path");
    File.WriteAllText(planPath,"{broken");
    Require(!TryReadCocosStaticSpineDataIdentity(spec,"source-component",new UnityEngine.Object(),out evidence,out diagnostic,out applicable,null)
        && applicable && diagnostic.StartsWith("cocos-static-spine-import-plan-unreadable:"),"corrupt present plan fails closed");
    var rendering=Encode(new CocosStaticSpineRenderingSignal{schemaVersion=1,
        contract=CocosStaticSpineRenderingContract,sourceManifestSha256=spec.sourceManifestSha256,
        components=new[]{new CocosStaticSpineRenderingSignalComponent{sourceComponentId="source-component",sourceDataAssetId="source-data"}},
        dataAssets=new[]{new CocosStaticSpineRenderingSignalData{sourceDataAssetId="source-data"}}});
    File.WriteAllText(planPath,Encode(new CocosStaticSpineImportPlanSignal{
        sourceManifestSha256=spec.sourceManifestSha256,staticSpineRenderingJson=rendering}));
    Require(!TryReadCocosStaticSpineDataIdentity(spec,"source-component",new UnityEngine.Object(),out evidence,out diagnostic,out applicable,null)
        && applicable && diagnostic=="cocos-static-spine-required-adapter-missing","present Spine plan cannot fall through when SDK adapter is absent");
    File.WriteAllText(planPath,Encode(new CocosStaticSpineImportPlanSignal{
        sourceManifestSha256=new string('b',64),staticSpineRenderingJson=rendering}));
    Require(!TryReadCocosStaticSpineDataIdentity(spec,"source-component",new UnityEngine.Object(),out evidence,out diagnostic,out applicable,null)
        && applicable && diagnostic=="cocos-static-spine-import-plan-manifest-invalid-or-different","manifest mismatch is applicable refusal");
    Console.WriteLine("SDK-free optional Spine registration: pass");
}'''
        unity_stubs = r'''
namespace UnityEngine {
 public class Object {}
 public static class Application { public static string dataPath; }
 public static class JsonUtility {
  public static T FromJson<T>(string raw) => JsonSerializer.Deserialize<T>(raw,
   new JsonSerializerOptions{IncludeFields=true});
 }
}
namespace UnityEngine.UI { public class Graphic : UnityEngine.Object {} }
'''
        wrapper = (
            "using System;using System.IO;using System.Linq;using System.Text.Json;"
            "using System.Text;"
            "using UnityEngine;using UnityEngine.UI;\n" + unity_stubs +
            "\npublic sealed class ProxyQueueSpec { public string sourceManifestSha256; }\n"
            "public sealed class SpineDataIdentityEvidence {}\n"
            "public static partial class UnityStaticSortQueueProxy {\n" + members +
            "\n" + program + "\n}")
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            (out / "Probe.cs").write_text(wrapper)
            (out / "Probe.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>'
                '<TargetFramework>net8.0</TargetFramework><Nullable>disable</Nullable></PropertyGroup></Project>')
            (out / "NuGet.Config").write_text("<configuration><packageSources><clear /></packageSources></configuration>")
            result = subprocess.run([dotnet, "run", "--project", str(out / "Probe.csproj"),
                "--property:RestoreConfigFile=" + str(out / "NuGet.Config")],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("SDK-free optional Spine registration: pass", result.stdout)


if __name__ == "__main__":
    unittest.main()


def test_static_spine_source_pins_do_not_depend_on_unrelated_outline_module():
    from monkey.targets.unity import _native_source_evidence
    source='a'*64
    plan={'sourceManifestSha256':source,'sourceManifestPath':'/pinned/source-manifest.json',
          'sourceIrSha256':'b'*64,'staticSpineRendering':{'sourceManifestSha256':source}}
    assert _native_source_evidence(plan)['sourceManifestSha256']==source
    assert _native_source_evidence(plan)['sourceManifestPath']=='/pinned/source-manifest.json'
    assert _native_source_evidence({'staticSpineRendering':{'sourceManifestSha256':source}})['sourceManifestSha256']==source
    assert _native_source_evidence({})=={}
