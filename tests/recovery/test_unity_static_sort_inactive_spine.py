"""Execute the production inactive-source Spine queue proof without an Editor."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


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


class StaticSortInactiveSpineTests(unittest.TestCase):
    def test_proxy_uses_inactive_source_flow_without_fabricating_renderer_list_state(self):
        source = (ROOT / "src/grea/recovery/targets/UnityStaticSortQueueProxy.cs").read_text()
        start = source.index("if (!listReadable && inactiveFlowProof != null && inactiveFlowProof.applicable && inactiveFlowProof.verified)")
        end = source.index("\n                if (ownerOnlyProof != null)", start)
        branch = source[start:end]

        self.assertIn('noDrawReason = "inactive-source-subtree-no-render-flow"', branch)
        self.assertIn('contract = "monkey-static-spine-inactive-source-flow/1"',
                      (ROOT / "src/grea/recovery/targets/UnityStaticSortQueue.cs").read_text())
        self.assertIn("ownerRendererListReadable = listReadable", branch)
        self.assertIn("currentOwnerRendererListReadable = listReadable", branch)
        self.assertIn("ownerOnlyNoRegisteredChildren = true", branch)
        self.assertIn("childReferencePersistent = dataOK", branch)
        self.assertIn('registrationEvidenceDisposition = "captured-registered-child-and-persisted-owner-references;current-list-not-required"', branch)
        self.assertIn("ownerOnlyNoRegisteredChildren = true", branch)
        self.assertNotIn("ownerRendererListReadable = true", branch)
        self.assertNotIn("currentOwnerRendererListReadable = true", branch)
        self.assertNotIn("ownerRendererListEmpty = true", branch)
        self.assertNotIn("currentOwnerRendererListEmpty = true", branch)
        self.assertNotIn("listReadable = true", branch)

    def test_production_proof_is_fail_closed_and_does_not_mutate_source_activity(self):
        dotnet = shutil.which("dotnet")
        if not dotnet:
            self.skipTest("dotnet SDK unavailable")
        source = (ROOT / "src/grea/recovery/targets/UnityStaticSortQueue.cs").read_text()
        members = "\n".join(declaration(source, signature) for signature in (
            "[Serializable] public sealed class QueueInactiveSpineReadback",
            "public static QueueInactiveSpineReadback ReadInactiveSpineNoRender(",
            "static Component ExactSpineGraphic(",
            "static bool HasExactSpineIdentity(",
        ))
        members = "\n".join(line.strip() for line in source.splitlines() if line.strip().startswith((
            "const string SpineGraphicType", "const string SpineIdentityType", "const BindingFlags SpineIdentityFieldFlags"))) + "\n" + members
        stubs = r'''
namespace UnityEngine {
 public class Object {}
 public class Component:Object {
  public GameObject gameObject; public Transform transform=>gameObject.transform;
  public T[] GetComponents<T>() where T:Component=>gameObject.GetComponents<T>();
 }
 public class Behaviour:Component { public bool enabled=true; }
 public class GameObject:Object {
  readonly System.Collections.Generic.List<Component> components=new();
  public readonly Transform transform; public bool activeSelf=true;
  public bool activeInHierarchy=>activeSelf&&(transform.parent==null||transform.parent.gameObject.activeInHierarchy);
  public GameObject(){transform=new Transform{gameObject=this};components.Add(transform);}
  public T Add<T>() where T:Component,new(){var c=new T{gameObject=this};components.Add(c);return c;}
  public T[] GetComponents<T>() where T:Component=>components.OfType<T>().ToArray();
 }
 public class Transform:Component {
  public Transform parent;
  public bool IsChildOf(Transform root){for(var p=this;p!=null;p=p.parent)if(p==root)return true;return false;}
 }
}
namespace Spine.Unity { public sealed class SkeletonGraphic:UnityEngine.Behaviour{} }
public sealed class UnitySpineSourceIdentity:UnityEngine.Behaviour {
 public string instanceSourceComponentId; public UnityEngine.Behaviour renderer;
}
'''
        program = r'''
static void Require(bool value,string label){if(!value)throw new Exception(label);}
static (Dictionary<string,UnityEngine.GameObject>,Dictionary<string,UnityEngine.GameObject>,
 Dictionary<string,bool>,Dictionary<string,string>,UnityEngine.GameObject,UnityEngine.Behaviour,UnityEngine.Behaviour)
 Build(bool ancestorActive=false,bool loadedOwnerEnabled=true,bool addPersistentMarker=true,bool hostActive=true){
 var host=new UnityEngine.GameObject{activeSelf=hostActive};
 var pRoot=new UnityEngine.GameObject();var pAncestor=new UnityEngine.GameObject{activeSelf=ancestorActive};var pOwner=new UnityEngine.GameObject{activeSelf=true};
 var lRoot=new UnityEngine.GameObject();var lAncestor=new UnityEngine.GameObject{activeSelf=ancestorActive};var lOwner=new UnityEngine.GameObject{activeSelf=true};
 pAncestor.transform.parent=pRoot.transform;pOwner.transform.parent=pAncestor.transform;
 lRoot.transform.parent=host.transform;lAncestor.transform.parent=lRoot.transform;lOwner.transform.parent=lAncestor.transform;
 var pg=pOwner.Add<Spine.Unity.SkeletonGraphic>();var lg=lOwner.Add<Spine.Unity.SkeletonGraphic>();lg.enabled=loadedOwnerEnabled;
 if(addPersistentMarker){var m=pOwner.Add<UnitySpineSourceIdentity>();m.instanceSourceComponentId="sid";m.renderer=pg;}
 var lm=lOwner.Add<UnitySpineSourceIdentity>();lm.instanceSourceComponentId="sid";lm.renderer=lg;
 var p=new Dictionary<string,UnityEngine.GameObject>{{"root",pRoot},{"ancestor",pAncestor},{"owner",pOwner}};
 var l=new Dictionary<string,UnityEngine.GameObject>{{"root",lRoot},{"ancestor",lAncestor},{"owner",lOwner}};
 var active=new Dictionary<string,bool>{{"root",true},{"ancestor",ancestorActive},{"owner",true}};
 var parents=new Dictionary<string,string>{{"ancestor","root"},{"owner","ancestor"}};
 return(p,l,active,parents,host,pg,lg);
}
static void Main(){
 var x=Build();var (p,l,a,parents,host,pg,lg)=x;
 var path=new[]{"owner","ancestor","root"};
 var valid=UnityStaticSortQueue.ReadInactiveSpineNoRender("sid","owner","root",true,path,a,p,l,host);
 Require(valid.applicable&&valid.verified&&!valid.sourceEffectiveActive,"inactive ancestor is proven outside render flow");
 Require(!valid.runtimeRendererListRequired&&valid.rendererListDisposition=="not-required-source-inactive-subtree","list is not claimed empty");
 Require(pg.enabled&&lg.enabled&&p["ancestor"].activeSelf==false&&l["ancestor"].activeSelf==false,"proof does not mutate source activity or enabled state");
 Require(valid.inactiveSourceAncestorId=="ancestor"&&valid.sourceActivityPath.SequenceEqual(new[]{"owner","ancestor","root"}),"exact source inactive path");
 x=Build(ancestorActive:true);var active=UnityStaticSortQueue.ReadInactiveSpineNoRender("sid","owner","root",true,path,x.Item3,x.Item1,x.Item2,x.Item5);
 Require(!active.applicable&&!active.verified,"active source cannot use inactive fallback");
 x=Build(loadedOwnerEnabled:false);var disabled=UnityStaticSortQueue.ReadInactiveSpineNoRender("sid","owner","root",true,path,x.Item3,x.Item1,x.Item2,x.Item5);
 Require(disabled.applicable&&!disabled.verified,"changed loaded enabled state rejected");
 x=Build(addPersistentMarker:false);var identity=UnityStaticSortQueue.ReadInactiveSpineNoRender("sid","owner","root",true,path,x.Item3,x.Item1,x.Item2,x.Item5);
 Require(identity.applicable&&!identity.verified,"missing persistent counterpart identity rejected");
 x=Build(hostActive:false);var hostBad=UnityStaticSortQueue.ReadInactiveSpineNoRender("sid","owner","root",true,path,x.Item3,x.Item1,x.Item2,x.Item5);
 Require(hostBad.applicable&&!hostBad.verified,"inactive controlled host cannot explain inactive source owner");
 x=Build();x.Item2["ancestor"].activeSelf=true;
 var activity=UnityStaticSortQueue.ReadInactiveSpineNoRender("sid","owner","root",true,path,x.Item3,x.Item1,x.Item2,x.Item5);
 Require(activity.applicable&&!activity.verified,"loaded source activity mutation rejected");
 x=Build();var badPath=UnityStaticSortQueue.ReadInactiveSpineNoRender("sid","owner","root",true,
    new[]{"owner","root"},x.Item3,x.Item1,x.Item2,x.Item5);
 Require(!badPath.applicable&&!badPath.verified,"incomplete activity path rejected");
 Console.WriteLine("production inactive Spine render-flow proof: pass");
}'''
        wrapper = ("using System;using System.Linq;using System.Collections.Generic;using System.Reflection;using UnityEngine;\n" +
                   stubs + "\npublic static class UnityStaticSortQueue {\n" + members + "\n" + program + "\n}")
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            (out / "Probe.cs").write_text(wrapper)
            (out / "Probe.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>'
                '<TargetFramework>net8.0</TargetFramework><Nullable>disable</Nullable>'
                '<NoWarn>CS0649</NoWarn></PropertyGroup></Project>')
            (out / "NuGet.Config").write_text("<configuration><packageSources><clear /></packageSources></configuration>")
            result = subprocess.run([dotnet, "run", "--project", str(out / "Probe.csproj"),
                "--property:RestoreConfigFile=" + str(out / "NuGet.Config")],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("production inactive Spine render-flow proof: pass", result.stdout)


if __name__ == "__main__":
    unittest.main()
