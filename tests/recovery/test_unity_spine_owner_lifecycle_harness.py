"""Execute extracted production Spine owner lifecycle methods with offline Unity object stubs."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import json
import os
import hashlib

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _declaration(source: str, signature: str) -> str:
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


def test_production_owner_lifecycle_transfer_reopen_refusals_and_cleanup():
    dotnet = shutil.which("dotnet")
    if not dotnet:
        pytest.skip(".NET SDK unavailable")
    source = (ROOT / "src/grea/recovery/targets/UnityStaticSpineRendering.cs").read_text(encoding="utf-8")
    declarations = (
        "[Serializable] sealed class StaticSpineCanvasComponentEvidence",
        "[Serializable] sealed class StaticSpineCanvasContextEvidenceRow",
        "[Serializable] sealed class StaticSpineCanvasContextEvidence\n",
        "[Serializable] sealed class StaticSpineControlledHostContextEvidence",
        "sealed class StaticSpineSourceCanvasLiveRegistration",
        "[Serializable] sealed class StaticSpineOwnerContextLifecycleRow",
        "[Serializable] sealed class StaticSpineOwnerContextLifecycleComponent",
        "[Serializable] sealed class StaticSpineOwnerContextLifecycleEnvelope",
        "sealed class StaticSpineNativeInstanceOwnerRegistration",
        "sealed class StaticSpineControlledCanvasRegistration",
        "sealed class StaticSpineReadbackOwnerRegistration",
        "sealed class StaticSpineReadbackOwnerScope",
        "[Serializable] sealed class StaticSpineRenderingData",
        "[Serializable] sealed class StaticSpineRenderingComponent",
        "[Serializable] sealed class StaticSpineRenderingEnvelope",
        "[Serializable] sealed class StaticSpineRenderingPayload",
    )
    methods = (
        "static string StaticSpineCanvasEvidenceHash(",
        "static string StaticSpineCanvasHashBytes(",
        "static string StaticSpineControlledHostEvidenceHash(",
        "static bool StaticSpineCanvasContextEvidenceMatches(",
        "static StaticSpineCanvasComponentEvidence StaticSpineSourceCanvasComponent(",
        "static bool StaticSpineRendererIdentityMatches(",
        "static string StaticSpineOwnerRelativePath(",
        "static string StaticSpineAssetGuid(",
        "static StaticSpineCanvasContextEvidenceRow StaticSpineSourceCanvasContextRow(",
        "static bool StaticSpineCloneCanvasMatchesSource(",
        "static bool StaticSpineInstanceActivityPathMatches(",
        "static StaticSpineOwnerContextLifecycleRow StaticSpineLifecycleRow(",
        "static void RecordStaticSpineOwnerLifecycle(",
        "static StaticSpineOwnerContextLifecycleComponent StaticSpineLifecycleComponent(",
        "static void InitializeStaticSpineOwnerLifecycleComponents(",
        "static void ResetStaticSpineOwnerLifecycleRegistries(",
        "static void RegisterStaticSpineSourceConstructionOwner(",
        "public static void RecordStaticSpineOwnerContextUse(",
        "static partial void RebindOptionalStaticSpineNativeInstanceContext(",
        "public static bool TryGetStaticSpineSourceCanvasProof(",
        "public static void RegisterStaticSpineReadbackOwnerContext(",
        "public static void UnregisterStaticSpineReadbackOwnerContext(",
        "public static void UnregisterStaticSpineControlledCanvasContext(",
        "public static string WriteStaticSpineOwnerContextLifecycleEvidence(",
    )
    members = "\n".join(_declaration(source, value) for value in declarations + methods)
    derived = (ROOT / "src/grea/recovery/targets/UnityStaticSpineRenderingDerived.cs").read_text(encoding="utf-8")
    members += "\n" + _declaration(derived, "static bool SpineUnitClose(")
    harness = r'''
static readonly string Manifest = new string('a',64), RenderingSha = new string('b',64);
static readonly List<StaticSpineNativeInstanceOwnerRegistration> staticSpineNativeInstanceOwners = new();
static readonly HashSet<Graphic> staticSpineRetiredNativeInstanceOwners = new();
static readonly List<StaticSpineOwnerContextLifecycleRow> staticSpineOwnerContextLifecycleRows = new();
static readonly List<StaticSpineOwnerContextLifecycleComponent> staticSpineOwnerContextLifecycleComponents = new();
static readonly Dictionary<string,StaticSpineSourceCanvasLiveRegistration> staticSpineSourceCanvasOwners = new(StringComparer.Ordinal);
static readonly List<StaticSpineReadbackOwnerScope> staticSpineReadbackOwnerScopes = new();
static readonly List<StaticSpineControlledCanvasRegistration> staticSpineControlledCanvasContexts = new();
static readonly Dictionary<string,UnitySpineNativeFactory.DataAssetReadback> staticSpineRenderingAssets = new(StringComparer.Ordinal);
static int refusalCount;
static StaticSpineRenderingEnvelope staticSpineRenderingPlan;
static StaticSpineCanvasContextEvidence staticSpineSourceCanvasContext;
static string staticSpineRenderingPlanSha;
const string StaticSpineOwnerContextLifecyclePath = "Analysis/Readback/SpineRendering/owner-context-lifecycle.json";

public sealed class Plan { public string sourceManifestSha256,staticSpineRenderingJson; public NodeSpec[] nodes; public ComponentSpec[] components; public SourcePrefabSpec[] sourcePrefabs; public PrefabInstanceSpec[] prefabInstances; }
public sealed class NodeSpec { public string sourceId,parent; public bool active; }
public sealed class ComponentSpec { public string sourceId,type,node; }
public sealed class SourcePrefabSpec { public string sourceId,root,path; }
public sealed class PrefabObjectPair { public string instanceObject,templateObject; }
public sealed class PrefabInstanceSpec { public string owner,root,template; public PrefabObjectPair[] nodes; }
public sealed class DataAssetIdentityPin { public string sourceDataAssetId,skeletonDataAssetPath,assetGuid;public long assetLocalFileId; }
static void ConfigureCanvas(GameObject node,StaticSpineCanvasContextEvidence context,StaticSpineRenderingComponent component){
 var c=context.components.Single(x=>x.sourceComponentId==component.sourceComponentId&&x.sourceDataAssetId==component.sourceDataAssetId);
 var row=context.contexts.Single(x=>x.contextIndex==c.sourceCanvasContextIndex);
 var canvas=node.GetComponent<Canvas>()??node.AddComponent<Canvas>();canvas.renderMode=(RenderMode)Enum.Parse(typeof(RenderMode),row.sourceCanvasRenderMode);canvas.referencePixelsPerUnit=row.sourceCanvasReferencePixelsPerUnit;
 if(row.sourceCanvasScalerPresent){var scaler=node.GetComponent<CanvasScaler>()??node.AddComponent<CanvasScaler>();scaler.referencePixelsPerUnit=row.sourceScalerReferencePixelsPerUnit;
 scaler.matchWidthOrHeight=row.sourceScalerMatchWidthOrHeight;scaler.uiScaleMode=(CanvasScaler.ScaleMode)Enum.Parse(typeof(CanvasScaler.ScaleMode),row.sourceCanvasScaleMode);
 scaler.referenceResolution=new Vector2(row.sourceScalerReferenceResolution[0],row.sourceScalerReferenceResolution[1]);}
}
static StaticSpineControlledHostContextEvidence MakeHostEvidence(StaticSpineCanvasContextEvidence context,string manifest,string renderingSha,float ppu){
 var result=new StaticSpineControlledHostContextEvidence{sourceManifestSha256=manifest,renderingPlanSha256=renderingSha,sourceCanvasEvidenceSha256=context.evidenceSha256,
 sourceCanvasRenderMode=context.contexts.First().sourceCanvasRenderMode,controlledHostCanvasRenderMode="WorldSpace",sourceCanvasReferencePixelsPerUnit=context.sourceReferencePixelsPerUnit,
 sourceScalerReferencePixelsPerUnit=context.contexts.First().sourceScalerReferencePixelsPerUnit,controlledHostReferencePixelsPerUnit=ppu,
 sourceCanvasScalerPresent=context.contexts.All(x=>x.sourceCanvasScalerPresent),sourceContextVerified=context.sourceCanvasContextVerified&&context.sourceNodeGeometryVerified,
 controlledHostCanvasScalerAbsent=true,controlledHostGeometryMatchesPlan=true,verified=true};result.evidenceSha256=StaticSpineControlledHostEvidenceHash(result);return result;
}

static void Require(bool value,string message){if(!value)throw new Exception(message);}
static void ExpectReject(Action action,string token,string name){try{action();}catch(Exception e){if(!e.ToString().Contains(token,StringComparison.Ordinal))throw new Exception(name+" rejected for wrong reason: "+e);return;}throw new Exception(name+" unexpectedly passed");}
static StaticSpineRenderingComponent Expected(string id,string owner,string node,string templateComponent,string templateNode,string data,bool active=true){
 return new StaticSpineRenderingComponent{sourceComponentId=id,sourcePrefabId=owner,sourceNodeId=node,templateComponentId=templateComponent,sourceDataAssetId=data,eligible=true,sourceComponentEnabled=true,sourceVisible=true};
}
static GameObject MakeRoot(string name,RenderMode mode,float ppu,bool scaler){
 var root=new GameObject(name);var canvas=root.AddComponent<Canvas>();canvas.renderMode=mode;canvas.referencePixelsPerUnit=ppu;
 if(scaler){var s=root.AddComponent<CanvasScaler>();s.referencePixelsPerUnit=ppu;s.matchWidthOrHeight=0;s.uiScaleMode=CanvasScaler.ScaleMode.ConstantPixelSize;s.referenceResolution=new Vector2(800,600);}
 return root;
}
static GameObject MakeNode(GameObject root,string name,StaticSpineRenderingComponent expected,SkeletonDataAsset data){
 var node=new GameObject(name);node.transform.parent=root.transform;node.activeSelf=true;
 var graphic=node.AddComponent<SkeletonGraphic>();graphic.enabled=true;graphic.SkeletonDataAsset=data;
 node.AddComponent<UnitySpineSourceIdentity>(new UnitySpineSourceIdentity{renderer=graphic,instanceSourceComponentId=expected.sourceComponentId,
 templateSourcePrefabId=expected.sourcePrefabId,templateSourceId=expected.templateComponentId,rendererKind=typeof(SkeletonGraphic).FullName});
 return node;
}
static StaticSpineCanvasContextEvidence MakeSourceEvidence(StaticSpineRenderingComponent[] rows){
 var e=new StaticSpineCanvasContextEvidence{sourceManifestSha256=Manifest,renderingPlanSha256=RenderingSha,sourceReferencePixelsPerUnit=100,
 sourceNodeGeometryVerified=true,sourceCanvasContextVerified=true,sourceNodeCount=rows.Length,
 contexts=new[]{new StaticSpineCanvasContextEvidenceRow{contextIndex=0,sourceCanvasRenderMode="ScreenSpaceOverlay",sourceCanvasScaleMode="ConstantPixelSize",
 sourceCanvasReferencePixelsPerUnit=100,sourceScalerReferencePixelsPerUnit=100,sourceScalerMatchWidthOrHeight=0,sourceScalerReferenceResolution=new[]{800f,600f},
 sourceCanvasScalerPresent=true,sourceCanvasPpuMatchesScaler=true}},
 components=rows.Select(x=>new StaticSpineCanvasComponentEvidence{sourceComponentId=x.sourceComponentId,sourcePrefabId=x.sourcePrefabId,sourceNodeId=x.sourceNodeId,
 sourceDataAssetId=x.sourceDataAssetId,sourceCanvasContextIndex=0,sourceCanvasContextVerified=true,sourceNodeActive=true,sourceNodeActivityVerified=true,sourceComponentEnabled=true}).ToArray()};
 e.evidenceSha256=StaticSpineCanvasEvidenceHash(e);return e;
}
static void Main(string[] args){
 if(args.Length>0){RunActualFixture(args[0]);return;}
 var a=Expected("owner-A#component","owner-A","owner-A#node","template#34","template#33","data-A");
 var b=Expected("owner-B#component","owner-B","owner-B#node","template#35","template#36","data-B");
 var rows=new[]{a,b};staticSpineRenderingPlanSha=RenderingSha;
 staticSpineRenderingPlan=new StaticSpineRenderingEnvelope{schemaVersion=1,contract="monkey-static-spine-rendering/1",sourceManifestSha256=Manifest,
 components=rows,dataAssets=new[]{new StaticSpineRenderingData{sourceDataAssetId="data-A",eligible=true,factorySpec=new UnitySpineNativeFactory.DataAssetSpec{skeletonDataAssetPath="Assets/data-A.asset"}},
 new StaticSpineRenderingData{sourceDataAssetId="data-B",eligible=true,factorySpec=new UnitySpineNativeFactory.DataAssetSpec{skeletonDataAssetPath="Assets/data-B.asset"}}}};
 staticSpineSourceCanvasContext=MakeSourceEvidence(rows);
 var plan=new Plan{sourceManifestSha256=Manifest,staticSpineRenderingJson="pinned",nodes=rows.SelectMany(x=>new[]{new NodeSpec{sourceId="instance-"+x.sourcePrefabId,active=true},new NodeSpec{sourceId=x.sourceNodeId,parent="instance-"+x.sourcePrefabId,active=true}}).ToArray(),
 components=new[]{new ComponentSpec{sourceId=a.templateComponentId,type="sp.Skeleton",node="template#33"},new ComponentSpec{sourceId=b.templateComponentId,type="sp.Skeleton",node="template#36"}},
 sourcePrefabs=new[]{new SourcePrefabSpec{sourceId="owner-A",root="instance-owner-A",path="Assets/owner-A.prefab"},new SourcePrefabSpec{sourceId="owner-B",root="instance-owner-B",path="Assets/owner-B.prefab"}}};
 var dataA=new SkeletonDataAsset{persistent=true,guid="data-guid-A",localFileId=101,assetPath="Assets/data-A.asset"};
 var dataB=new SkeletonDataAsset{persistent=true,guid="data-guid-B",localFileId=102,assetPath="Assets/data-B.asset"};
 AssetDatabase.Register(dataA);AssetDatabase.Register(dataB);
 SkeletonGraphic staleLoadedOwner=null;StaticSpineRenderingComponent staleExpected=null;SkeletonDataAsset staleData=null;Plan stalePlan=null;
 Dictionary<string,GameObject> stalePersistentNodes=null;
 var originalNodes=new Dictionary<string,GameObject>();var originalOwners=new Dictionary<string,SkeletonGraphic>();var originalRoots=new Dictionary<string,GameObject>();
 foreach(var (expected,data) in new[]{(a,dataA),(b,dataB)}){
  var root=MakeRoot("instance-"+expected.sourcePrefabId,RenderMode.ScreenSpaceOverlay,100,true);var node=MakeNode(root,expected.sourceNodeId,expected,data);
  originalRoots.Add(expected.sourcePrefabId,root);originalNodes.Add(expected.sourceNodeId,node);originalOwners.Add(expected.sourceComponentId,node.GetComponent<SkeletonGraphic>());
  staticSpineSourceCanvasOwners.Add(expected.sourceComponentId,new StaticSpineSourceCanvasLiveRegistration{canvas=root.GetComponent<Canvas>(),sourceNode=node,
   evidence=staticSpineSourceCanvasContext,sourceComponentId=expected.sourceComponentId,sourcePrefabId=expected.sourcePrefabId,sourceNodeId=expected.sourceNodeId,sourceDataAssetId=expected.sourceDataAssetId});
  staticSpineOwnerContextLifecycleComponents.Add(new StaticSpineOwnerContextLifecycleComponent{sourceComponentId=expected.sourceComponentId,sourceDataAssetId=expected.sourceDataAssetId,
   sourcePrefabId=expected.sourcePrefabId,sourceNodeId=expected.sourceNodeId,templateComponentId=expected.templateComponentId,eligible=true});
  RegisterStaticSpineSourceConstructionOwner(expected,node,node.GetComponent<SkeletonGraphic>(),data);
 }
 foreach(var (expected,data) in new[]{(a,dataA),(b,dataB)}){
  var before=new GameObject("unregistered-clone");var g=before.AddComponent<SkeletonGraphic>();g.SkeletonDataAsset=data;
  before.AddComponent<UnitySpineSourceIdentity>(new UnitySpineSourceIdentity{renderer=g,instanceSourceComponentId=expected.sourceComponentId,
   templateSourcePrefabId=expected.sourcePrefabId,templateSourceId=expected.templateComponentId,rendererKind=typeof(SkeletonGraphic).FullName});
  Require(!TryGetStaticSpineSourceCanvasProof(g,expected.sourceComponentId,expected.sourceDataAssetId,Manifest,RenderingSha,out _,out _,out _,out _),"unregistered owner refused");
  var targetRoot=MakeRoot("instance-root-"+expected.sourcePrefabId,RenderMode.ScreenSpaceOverlay,100,true);
  var targetNode=MakeNode(targetRoot,"clone-node",expected,data);var targetGraphic=targetNode.GetComponent<SkeletonGraphic>();
  var map=new Dictionary<string,GameObject>{{"instance-"+expected.sourcePrefabId,targetRoot},{expected.sourceNodeId,targetNode}};
  var replacements=new Dictionary<UnityEngine.Object,UnityEngine.Object>{{originalRoots[expected.sourcePrefabId],targetRoot},{originalNodes[expected.sourceNodeId],targetNode},{originalOwners[expected.sourceComponentId],targetGraphic}};
  var instance=new PrefabInstanceSpec{owner=expected.sourcePrefabId,root="instance-"+expected.sourcePrefabId,template="template",nodes=new[]{new PrefabObjectPair{instanceObject=expected.sourceNodeId,templateObject=expected==a?"template#33":"template#36"}}};
  var cloneMarker=targetNode.GetComponent<UnitySpineSourceIdentity>();cloneMarker.templateSourceId="wrong-template";
  ExpectReject(()=>RebindOptionalStaticSpineNativeInstanceContext(plan,instance,map,replacements),"SPINE_OWNER_LIFECYCLE_NATIVE_INSTANCE_CLONE_UNVERIFIED","wrong source marker");
  refusalCount++;cloneMarker.templateSourceId=expected.templateComponentId;
  RebindOptionalStaticSpineNativeInstanceContext(plan,instance,map,replacements);
  Require(TryGetStaticSpineSourceCanvasProof(targetGraphic,expected.sourceComponentId,expected.sourceDataAssetId,Manifest,RenderingSha,out _,out _,out var kind,out var diag),"exact transferred clone resolves: "+diag);
  Require(kind=="native-instance-clone-lifecycle","clone lifecycle phase recorded");
  cloneMarker.templateSourceId="wrong-template";
  Require(!TryGetStaticSpineSourceCanvasProof(targetGraphic,expected.sourceComponentId,expected.sourceDataAssetId,Manifest,RenderingSha,out _,out _,out _,out _),"wrong source marker refused");
  refusalCount++;cloneMarker.templateSourceId=expected.templateComponentId;
  var expectedData=targetGraphic.SkeletonDataAsset;var otherData=new SkeletonDataAsset{persistent=true,guid="other-guid",localFileId=999,assetPath="Assets/other.asset"};AssetDatabase.Register(otherData);
  targetGraphic.SkeletonDataAsset=otherData;Require(!TryGetStaticSpineSourceCanvasProof(targetGraphic,expected.sourceComponentId,expected.sourceDataAssetId,Manifest,RenderingSha,out _,out _,out _,out _),"wrong data reference refused");
  refusalCount++;targetGraphic.SkeletonDataAsset=expectedData;
  var expectedGuid=expectedData.guid;expectedData.guid=null;Require(!TryGetStaticSpineSourceCanvasProof(targetGraphic,expected.sourceComponentId,expected.sourceDataAssetId,Manifest,RenderingSha,out _,out _,out _,out _),"missing persistent data GUID refused");
  refusalCount++;expectedData.guid=expectedGuid;
  var expectedPpu=targetRoot.GetComponent<Canvas>().referencePixelsPerUnit;targetRoot.GetComponent<Canvas>().referencePixelsPerUnit=99;
  Require(!TryGetStaticSpineSourceCanvasProof(targetGraphic,expected.sourceComponentId,expected.sourceDataAssetId,Manifest,RenderingSha,out _,out _,out _,out _),"canvas PPU drift refused");
  refusalCount++;targetRoot.GetComponent<Canvas>().referencePixelsPerUnit=expectedPpu;
  Require(!TryGetStaticSpineSourceCanvasProof(targetGraphic,expected.sourceComponentId,expected.sourceDataAssetId,"wrong-manifest",RenderingSha,out _,out _,out _,out _),"source pin drift refused");
  refusalCount++;
  var registration=staticSpineNativeInstanceOwners.Single(x=>x.owner==targetGraphic);staticSpineNativeInstanceOwners.Remove(registration);
  Require(!TryGetStaticSpineSourceCanvasProof(targetGraphic,expected.sourceComponentId,expected.sourceDataAssetId,Manifest,RenderingSha,out _,out _,out _,out _),"replaced registry owner refused");
  refusalCount++;staticSpineNativeInstanceOwners.Add(registration);
  targetGraphic.destroyed=true;Require(!TryGetStaticSpineSourceCanvasProof(targetGraphic,expected.sourceComponentId,expected.sourceDataAssetId,Manifest,RenderingSha,out _,out _,out _,out _),"destroyed owner refused");
  refusalCount++;targetGraphic.destroyed=false;
  originalOwners[expected.sourceComponentId].destroyed=true;
  targetGraphic.persistent=true;targetGraphic.guid="renderer-guid-"+expected.sourcePrefabId;targetGraphic.localFileId=expected==a?201:202;targetGraphic.assetPath="Assets/"+expected.sourcePrefabId+".prefab";
  targetRoot.persistent=true;targetRoot.guid="prefab-guid-"+expected.sourcePrefabId;targetRoot.localFileId=expected==a?301:302;targetRoot.assetPath=targetGraphic.assetPath;
  AssetDatabase.Register(targetRoot);AssetDatabase.Register(targetGraphic);
  var host=MakeRoot("controlled-host-"+expected.sourcePrefabId,RenderMode.WorldSpace,100,false);
  var evidence=new StaticSpineControlledHostContextEvidence{sourceManifestSha256=Manifest,renderingPlanSha256=RenderingSha,
   sourceCanvasEvidenceSha256=staticSpineSourceCanvasContext.evidenceSha256,sourceCanvasRenderMode="ScreenSpaceOverlay",controlledHostCanvasRenderMode="WorldSpace",
   sourceCanvasReferencePixelsPerUnit=100,sourceScalerReferencePixelsPerUnit=100,controlledHostReferencePixelsPerUnit=100,sourceCanvasScalerPresent=true,
   sourceContextVerified=true,controlledHostCanvasScalerAbsent=true,controlledHostGeometryMatchesPlan=true,verified=true};
  evidence.evidenceSha256=StaticSpineControlledHostEvidenceHash(evidence);
  staticSpineControlledCanvasContexts.Add(new StaticSpineControlledCanvasRegistration{host=host,canvas=host.GetComponent<Canvas>(),evidence=evidence});
  var loadedRoot=new GameObject("loaded-root");loadedRoot.transform.parent=host.transform;
  var loadedNode=MakeNode(host,expected.sourceNodeId,expected,data);var loadedGraphic=loadedNode.GetComponent<SkeletonGraphic>();
  var persistentNodes=new Dictionary<string,GameObject>{{"instance-"+expected.sourcePrefabId,targetRoot},{expected.sourceNodeId,targetNode}};
  var loadedNodes=new Dictionary<string,GameObject>{{"instance-"+expected.sourcePrefabId,loadedRoot},{expected.sourceNodeId,loadedNode}};
  var otherHost=MakeRoot("wrong-controlled-host",RenderMode.WorldSpace,100,false);var wrongNode=MakeNode(otherHost,"wrong-loaded-node",expected,data);
  var wrongLoadedNodes=new Dictionary<string,GameObject>{{"instance-"+expected.sourcePrefabId,loadedRoot},{expected.sourceNodeId,wrongNode}};
  ExpectReject(()=>RegisterStaticSpineReadbackOwnerContext(plan,expected.sourcePrefabId,persistentNodes,wrongLoadedNodes,host),"SPINE_READBACK_OWNER_NOT_UNDER_REGISTERED_CONTROLLED_CANVAS","wrong saved/reopened host");
  refusalCount++;
  RegisterStaticSpineReadbackOwnerContext(plan,expected.sourcePrefabId,persistentNodes,loadedNodes,host);
  Require(TryGetStaticSpineSourceCanvasProof(loadedGraphic,expected.sourceComponentId,expected.sourceDataAssetId,Manifest,RenderingSha,out _,out _,out kind,out diag),"saved/reopened peer resolves: "+diag);
  Require(kind=="controlled-prefab-reopened-owner","saved/reopened phase recorded");
  staleLoadedOwner=loadedGraphic;staleExpected=expected;staleData=data;stalePlan=plan;stalePersistentNodes=persistentNodes;
  if(expected.sourcePrefabId=="owner-A"){
   UnregisterStaticSpineReadbackOwnerContext(host);
   Require(!TryGetStaticSpineSourceCanvasProof(loadedGraphic,expected.sourceComponentId,expected.sourceDataAssetId,Manifest,RenderingSha,out _,out _,out _,out _),"released host loses owner scope");
   UnregisterStaticSpineControlledCanvasContext(host);
  }
 }
 var outRoot=Environment.GetEnvironmentVariable("MONKEY_OWNER_LIFECYCLE_OUTPUT");if(String.IsNullOrWhiteSpace(outRoot))throw new Exception("MONKEY_OWNER_LIFECYCLE_OUTPUT required");
 Directory.CreateDirectory(Path.Combine(outRoot,"Assets"));Application.dataPath=Path.Combine(outRoot,"Assets");
 var evidencePath=WriteStaticSpineOwnerContextLifecycleEvidence();
 var result=JsonDocument.Parse(File.ReadAllText(evidencePath));var transitions=result.RootElement.GetProperty("transitions").EnumerateArray().ToArray();
 Require(result.RootElement.GetProperty("components").GetArrayLength()==2,"both same-template owners included in denominator");
 Require(transitions.Count(x=>x.GetProperty("phase").GetString()=="source-construction")==2,"source registration events");
 Require(transitions.Count(x=>x.GetProperty("phase").GetString()=="native-instance-clone")==4,"two accepted and two rejected exact same-template clone attempts");
 Require(transitions.Count(x=>x.GetProperty("phase").GetString()=="saved-prefab-owner-pair")==2,"saved and reopened pair events");
 Require(transitions.Count(x=>x.GetProperty("phase").GetString()=="controlled-host-release")==1,"scoped controlled host release event");
 Require(transitions.Count(x=>x.GetProperty("phase").GetString()=="native-instance-clone"&&!x.GetProperty("verified").GetBoolean())==2,"two wrong source marker attempts remain visibly unverified");
 Require(transitions.Where(x=>x.GetProperty("phase").GetString()!="native-instance-clone"||x.GetProperty("verified").GetBoolean()).All(x=>x.GetProperty("verified").GetBoolean()),"all accepted lifecycle phases verified in the stubbed offline model");
 Console.WriteLine("production owner lifecycle harness: source=2 clone=2 rejectedClone=2 savedPair=2 release=1 sameTemplateInstances=2 refusals="+refusalCount);
 Require(TryGetStaticSpineSourceCanvasProof(staleLoadedOwner,staleExpected.sourceComponentId,staleExpected.sourceDataAssetId,Manifest,RenderingSha,out _,out _,out _,out _),"old host is live immediately before startup reset");
 var savedRenderingPlan=staticSpineRenderingPlan;
 ResetStaticSpineOwnerLifecycleRegistries();
 Require(staticSpineReadbackOwnerScopes.Count==0&&staticSpineControlledCanvasContexts.Count==0&&staticSpineNativeInstanceOwners.Count==0,"Observe reset clears old runtime owner registries");
 Require(!TryGetStaticSpineSourceCanvasProof(staleLoadedOwner,staleExpected.sourceComponentId,staleExpected.sourceDataAssetId,Manifest,RenderingSha,out _,out _,out _,out _),"stale loaded owner and host refused after reset");
 staticSpineRenderingPlan=savedRenderingPlan;
 staticSpineRenderingPlanSha=RenderingSha;staticSpineSourceCanvasContext=MakeSourceEvidence(rows);
 var freshHost=MakeRoot("new-run-host",RenderMode.WorldSpace,100,false);
 var freshEvidence=new StaticSpineControlledHostContextEvidence{sourceManifestSha256=Manifest,renderingPlanSha256=RenderingSha,
 sourceCanvasEvidenceSha256=staticSpineSourceCanvasContext.evidenceSha256,sourceCanvasRenderMode="ScreenSpaceOverlay",controlledHostCanvasRenderMode="WorldSpace",
 sourceCanvasReferencePixelsPerUnit=100,sourceScalerReferencePixelsPerUnit=100,controlledHostReferencePixelsPerUnit=100,sourceCanvasScalerPresent=true,
 sourceContextVerified=true,controlledHostCanvasScalerAbsent=true,controlledHostGeometryMatchesPlan=true,verified=true};
 freshEvidence.evidenceSha256=StaticSpineControlledHostEvidenceHash(freshEvidence);
 staticSpineControlledCanvasContexts.Add(new StaticSpineControlledCanvasRegistration{host=freshHost,canvas=freshHost.GetComponent<Canvas>(),evidence=freshEvidence});
 var freshRoot=new GameObject("fresh-loaded-root");freshRoot.transform.parent=freshHost.transform;var freshNode=MakeNode(freshHost,staleExpected.sourceNodeId,staleExpected,staleData);
 var freshLoadedNodes=new Dictionary<string,GameObject>{{"instance-owner-B",freshRoot},{staleExpected.sourceNodeId,freshNode}};
 RegisterStaticSpineReadbackOwnerContext(stalePlan,staleExpected.sourcePrefabId,stalePersistentNodes,freshLoadedNodes,freshHost);
 Require(TryGetStaticSpineSourceCanvasProof(freshNode.GetComponent<SkeletonGraphic>(),staleExpected.sourceComponentId,staleExpected.sourceDataAssetId,Manifest,RenderingSha,out _,out _,out _,out _),"new-run owner pair remains valid after reset");
 UnregisterStaticSpineReadbackOwnerContext(freshHost);UnregisterStaticSpineControlledCanvasContext(freshHost);
 Console.WriteLine("Unity AssetDatabase persistence and Editor lifecycle are simulated, not accepted as native Editor proof");
}
static void RunActualFixture(string fixturePath){
 var root=JsonDocument.Parse(File.ReadAllText(fixturePath)).RootElement;
 var plan=JsonUtility.FromJson<Plan>(root.GetProperty("plan").GetRawText());
 staticSpineRenderingPlan=JsonUtility.FromJson<StaticSpineRenderingEnvelope>(root.GetProperty("renderingPlanJson").GetString());
 staticSpineSourceCanvasContext=JsonUtility.FromJson<StaticSpineCanvasContextEvidence>(root.GetProperty("sourceCanvasContextJson").GetString());
 Require(staticSpineRenderingPlan.components.Length==75&&staticSpineRenderingPlan.dataAssets.Length==18,"fixture denominator 75 components/18 assets");
 var manifest=plan.sourceManifestSha256;staticSpineRenderingPlanSha=staticSpineSourceCanvasContext.renderingPlanSha256;
 plan.staticSpineRenderingJson=root.GetProperty("renderingPlanJson").GetString();
 // JsonUtility is modeled by System.Text.Json offline, so recompute the in-model evidence hash.
 // All source context fields and the separate fixture SHA pins remain untouched.
 staticSpineSourceCanvasContext.evidenceSha256=StaticSpineCanvasEvidenceHash(staticSpineSourceCanvasContext);
 InitializeStaticSpineOwnerLifecycleComponents(staticSpineRenderingPlan);
 using(var renderingDoc=JsonDocument.Parse(root.GetProperty("renderingPlanJson").GetString())){
  foreach(var dataElement in renderingDoc.RootElement.GetProperty("dataAssets").EnumerateArray()){
   var dataId=dataElement.GetProperty("sourceDataAssetId").GetString();var dataPath=dataElement.GetProperty("factorySpec").GetProperty("skeletonDataAssetPath").GetString();
   var row=staticSpineRenderingPlan.dataAssets.Single(x=>x.sourceDataAssetId==dataId);row.factorySpec=new UnitySpineNativeFactory.DataAssetSpec{skeletonDataAssetPath=dataPath};
  }
 }
 var identityPins=root.GetProperty("dataAssetIdPathPins").EnumerateArray()
  .Select(x=>JsonSerializer.Deserialize<DataAssetIdentityPin>(x.GetRawText(),new JsonSerializerOptions{IncludeFields=true})).ToDictionary(x=>x.sourceDataAssetId,StringComparer.Ordinal);
 var assets=new Dictionary<string,SkeletonDataAsset>(StringComparer.Ordinal);long nextLocal=200000;
 foreach(var row in staticSpineRenderingPlan.dataAssets.Where(x=>x!=null&&x.eligible)){
  var pin=identityPins[row.sourceDataAssetId];Require(pin.skeletonDataAssetPath==row.factorySpec.skeletonDataAssetPath,"data asset path pin exact");
  var asset=new SkeletonDataAsset{persistent=true,guid=pin.assetGuid,localFileId=pin.assetLocalFileId,assetPath=pin.skeletonDataAssetPath};
  AssetDatabase.Register(asset);assets.Add(row.sourceDataAssetId,asset);nextLocal=Math.Max(nextLocal,pin.assetLocalFileId+1);
 }
 var oldNodes=(plan.nodes??Array.Empty<NodeSpec>()).ToDictionary(x=>x.sourceId,x=>new GameObject(x.sourceId),StringComparer.Ordinal);
 var nodeSpecs=plan.nodes.ToDictionary(x=>x.sourceId,StringComparer.Ordinal);
 foreach(var spec in plan.nodes){var node=oldNodes[spec.sourceId];node.activeSelf=spec.active;if(!String.IsNullOrWhiteSpace(spec.parent)){Require(oldNodes.ContainsKey(spec.parent),"source node parent pinned");node.transform.parent=oldNodes[spec.parent].transform;}}
 var originalOwners=new Dictionary<string,SkeletonGraphic>(StringComparer.Ordinal);var rows=staticSpineRenderingPlan.components;
 foreach(var expected in rows){
  Require(expected.eligible&&nodeSpecs.ContainsKey(expected.sourceNodeId)&&assets.ContainsKey(expected.sourceDataAssetId),"eligible source row joins plan node/data");
  var node=oldNodes[expected.sourceNodeId];ConfigureCanvas(node,staticSpineSourceCanvasContext,expected);
  var graphic=node.AddComponent<SkeletonGraphic>();graphic.enabled=expected.sourceComponentEnabled;graphic.SkeletonDataAsset=assets[expected.sourceDataAssetId];
  node.AddComponent<UnitySpineSourceIdentity>(new UnitySpineSourceIdentity{renderer=graphic,instanceSourceComponentId=expected.sourceComponentId,
   templateSourcePrefabId=expected.sourcePrefabId,templateSourceId=expected.templateComponentId,rendererKind=typeof(SkeletonGraphic).FullName});
  var ce=staticSpineSourceCanvasContext.components.Single(x=>x.sourceComponentId==expected.sourceComponentId&&x.sourceDataAssetId==expected.sourceDataAssetId);
  staticSpineSourceCanvasOwners.Add(expected.sourceComponentId,new StaticSpineSourceCanvasLiveRegistration{canvas=node.GetComponent<Canvas>(),sourceNode=node,
   evidence=staticSpineSourceCanvasContext,sourceComponentId=expected.sourceComponentId,sourcePrefabId=expected.sourcePrefabId,sourceNodeId=expected.sourceNodeId,sourceDataAssetId=expected.sourceDataAssetId});
  Require(ce.sourceCanvasContextVerified&&ce.sourceNodeActivityVerified,"pinned source canvas/component evidence is verified");
  originalOwners.Add(expected.sourceComponentId,graphic);RegisterStaticSpineSourceConstructionOwner(expected,node,graphic,assets[expected.sourceDataAssetId]);
 }
 Require(originalOwners.Count==75&&staticSpineNativeInstanceOwners.Count==75,"all75 source owners registered through production API");
 foreach(var expected in rows)Require(TryGetStaticSpineSourceCanvasProof(originalOwners[expected.sourceComponentId],expected.sourceComponentId,expected.sourceDataAssetId,
  manifest,staticSpineRenderingPlanSha,out _,out _,out var sourceKind,out var sourceDiagnostic),"source owner exact proof: "+sourceDiagnostic);

 var groups=new List<(PrefabInstanceSpec instance,StaticSpineRenderingComponent[] rows)>();
 foreach(var instance in plan.prefabInstances??Array.Empty<PrefabInstanceSpec>()){
  var candidateRows=rows.Where(expected=>expected.eligible&&expected.sourcePrefabId==instance.owner&&
    !String.IsNullOrWhiteSpace(expected.templateComponentId)&&expected.templateComponentId.StartsWith(instance.template+"#",StringComparison.Ordinal)&&
    (instance.nodes??Array.Empty<PrefabObjectPair>()).Any(pair=>pair!=null&&pair.instanceObject==expected.sourceNodeId)).ToArray();
  if(candidateRows.Length>0)groups.Add((instance,candidateRows));
 }
 var fixtureCandidates=root.GetProperty("instanceTransferCandidates").EnumerateArray().Sum(x=>x.GetProperty("componentIds").GetArrayLength());
 var uniqueCandidates=groups.SelectMany(x=>x.rows).Select(x=>x.sourceComponentId).Distinct(StringComparer.Ordinal).Count();
 Require(fixtureCandidates==36&&uniqueCandidates==36&&groups.Sum(x=>x.rows.Length)==36,"36 exact unique native instance transfer candidates");
 var cloneNodes=new Dictionary<string,GameObject>(StringComparer.Ordinal);var cloneOwners=new Dictionary<string,SkeletonGraphic>(StringComparer.Ordinal);
 int rejectedBatches=0,unregisteredRefusals=0;
 foreach(var (instance,candidates) in groups){
  var targetRoot=new GameObject("clone-root:"+instance.root);targetRoot.activeSelf=nodeSpecs[instance.root].active;
  var instanceNodes=new Dictionary<string,GameObject>(StringComparer.Ordinal){{instance.root,targetRoot}};
  var replacements=new Dictionary<UnityEngine.Object,UnityEngine.Object>{{oldNodes[instance.root],targetRoot}};
  foreach(var expected in candidates){
   var chain=new List<string>();var cursor=expected.sourceNodeId;var seen=new HashSet<string>(StringComparer.Ordinal);
   while(cursor!=instance.root){Require(!String.IsNullOrWhiteSpace(cursor)&&seen.Add(cursor)&&nodeSpecs.ContainsKey(cursor),"source ancestor chain reaches instance root");chain.Add(cursor);cursor=nodeSpecs[cursor].parent;}
   var parent=targetRoot;
   foreach(var id in chain.AsEnumerable().Reverse()){
    if(!instanceNodes.TryGetValue(id,out var copied)){copied=new GameObject("clone:"+id);copied.activeSelf=nodeSpecs[id].active;copied.transform.parent=parent.transform;
     instanceNodes.Add(id,copied);replacements.Add(oldNodes[id],copied);}
    parent=copied;
   }
   var targetNode=instanceNodes[expected.sourceNodeId];ConfigureCanvas(targetNode,staticSpineSourceCanvasContext,expected);
   var target=targetNode.AddComponent<SkeletonGraphic>();target.enabled=expected.sourceComponentEnabled;target.SkeletonDataAsset=assets[expected.sourceDataAssetId];
   targetNode.AddComponent<UnitySpineSourceIdentity>(new UnitySpineSourceIdentity{renderer=target,instanceSourceComponentId=expected.sourceComponentId,
    templateSourcePrefabId=expected.sourcePrefabId,templateSourceId=expected.templateComponentId,rendererKind=typeof(SkeletonGraphic).FullName});
   replacements.Add(originalOwners[expected.sourceComponentId],target);cloneNodes.Add(expected.sourceComponentId,targetNode);cloneOwners.Add(expected.sourceComponentId,target);
  }
  var beforeCount=staticSpineNativeInstanceOwners.Count;var firstUnregistered=candidates[0];
  Require(!TryGetStaticSpineSourceCanvasProof(cloneOwners[firstUnregistered.sourceComponentId],firstUnregistered.sourceComponentId,firstUnregistered.sourceDataAssetId,
   manifest,staticSpineRenderingPlanSha,out _,out _,out _,out _),"unregistered target clone refused before rebind");unregisteredRefusals++;
  if(rejectedBatches==0&&candidates.Length>1){
   var bad=candidates[candidates.Length-1];var badMarker=cloneNodes[bad.sourceComponentId].GetComponent<UnitySpineSourceIdentity>();badMarker.templateSourceId="deliberately-wrong-template";
   ExpectReject(()=>RebindOptionalStaticSpineNativeInstanceContext(plan,instance,instanceNodes,replacements),"SPINE_OWNER_LIFECYCLE_NATIVE_INSTANCE_CLONE_UNVERIFIED","atomic multi-owner clone batch with wrong final marker");
   Require(staticSpineNativeInstanceOwners.Count==beforeCount&&candidates.All(x=>staticSpineNativeInstanceOwners.Any(r=>r.owner==originalOwners[x.sourceComponentId]))&&
     candidates.All(x=>!staticSpineNativeInstanceOwners.Any(r=>r.owner==cloneOwners[x.sourceComponentId])),"failed multi-owner batch committed no owner transfer");
   badMarker.templateSourceId=bad.templateComponentId;rejectedBatches++;
  }
  RebindOptionalStaticSpineNativeInstanceContext(plan,instance,instanceNodes,replacements);
  foreach(var expected in candidates){
   Require(TryGetStaticSpineSourceCanvasProof(cloneOwners[expected.sourceComponentId],expected.sourceComponentId,expected.sourceDataAssetId,
    manifest,staticSpineRenderingPlanSha,out _,out _,out var kind,out var diagnostic),"transferred actual owner resolves: "+diagnostic);
   Require(kind=="native-instance-clone-lifecycle","phase is the exact clone transfer");originalOwners[expected.sourceComponentId].destroyed=true;
  }
 }
 Require(rejectedBatches==1&&cloneOwners.Count==36,"one atomic failure exercise plus all36 accepted clone transfers");
 var sample=rows.First(x=>cloneOwners.ContainsKey(x.sourceComponentId));var sampleTarget=cloneOwners[sample.sourceComponentId];var sampleNode=cloneNodes[sample.sourceComponentId];
 int refusals=unregisteredRefusals;
 var marker=sampleNode.GetComponent<UnitySpineSourceIdentity>();marker.templateSourceId="wrong-template";
 Require(!TryGetStaticSpineSourceCanvasProof(sampleTarget,sample.sourceComponentId,sample.sourceDataAssetId,manifest,staticSpineRenderingPlanSha,out _,out _,out _,out _),"wrong marker lookup refused");refusals++;marker.templateSourceId=sample.templateComponentId;
 var correctData=sampleTarget.SkeletonDataAsset;sampleTarget.SkeletonDataAsset=new SkeletonDataAsset{persistent=true,guid="wrong-guid",localFileId=999,assetPath="Assets/wrong.asset"};
 Require(!TryGetStaticSpineSourceCanvasProof(sampleTarget,sample.sourceComponentId,sample.sourceDataAssetId,manifest,staticSpineRenderingPlanSha,out _,out _,out _,out _),"wrong data asset reference refused");refusals++;sampleTarget.SkeletonDataAsset=correctData;
 var dataGuid=correctData.guid;correctData.guid=null;Require(!TryGetStaticSpineSourceCanvasProof(sampleTarget,sample.sourceComponentId,sample.sourceDataAssetId,manifest,staticSpineRenderingPlanSha,out _,out _,out _,out _),"missing actual data GUID refused");refusals++;correctData.guid=dataGuid;
 var cloneCanvas=sampleNode.GetComponent<Canvas>();var oldPpu=cloneCanvas.referencePixelsPerUnit;cloneCanvas.referencePixelsPerUnit=oldPpu+1;
 Require(!TryGetStaticSpineSourceCanvasProof(sampleTarget,sample.sourceComponentId,sample.sourceDataAssetId,manifest,staticSpineRenderingPlanSha,out _,out _,out _,out _),"clone Canvas PPU drift refused");refusals++;cloneCanvas.referencePixelsPerUnit=oldPpu;
 Require(!TryGetStaticSpineSourceCanvasProof(sampleTarget,sample.sourceComponentId,sample.sourceDataAssetId,"wrong-manifest",staticSpineRenderingPlanSha,out _,out _,out _,out _),"source plan pin drift refused");refusals++;
 var nativeRegistration=staticSpineNativeInstanceOwners.Single(x=>x.owner==sampleTarget);staticSpineNativeInstanceOwners.Remove(nativeRegistration);
 Require(!TryGetStaticSpineSourceCanvasProof(sampleTarget,sample.sourceComponentId,sample.sourceDataAssetId,manifest,staticSpineRenderingPlanSha,out _,out _,out _,out _),"removed lifecycle registration refused");refusals++;staticSpineNativeInstanceOwners.Add(nativeRegistration);
 sampleTarget.destroyed=true;Require(!TryGetStaticSpineSourceCanvasProof(sampleTarget,sample.sourceComponentId,sample.sourceDataAssetId,manifest,staticSpineRenderingPlanSha,out _,out _,out _,out _),"destroyed clone owner refused");refusals++;sampleTarget.destroyed=false;
 foreach(var expected in rows){var owner=cloneOwners.TryGetValue(expected.sourceComponentId,out var clone)?clone:originalOwners[expected.sourceComponentId];
  RecordStaticSpineOwnerContextUse(owner,expected.sourceComponentId,expected.sourceDataAssetId,"static-sort-create-capture",true,null);}
 Require(staticSpineOwnerContextLifecycleRows.Count(x=>x.phase=="static-sort-create-capture")==75,"all75 source owners record creation/capture use");
 var sourcePrefabIds=rows.Select(x=>x.sourcePrefabId).Distinct(StringComparer.Ordinal).ToArray();var activeHosts=new List<(GameObject host,string prefabId,
  Dictionary<string,GameObject> persistentNodes,Dictionary<string,GameObject> loadedNodes,List<(StaticSpineRenderingComponent expected,SkeletonGraphic loaded)> owners)>();
 int savedPairs=0,wrongHostRefusals=0;var planNodeById=plan.nodes.ToDictionary(x=>x.sourceId,StringComparer.Ordinal);
 foreach(var prefabId in sourcePrefabIds){
  var expectedRows=rows.Where(x=>x.sourcePrefabId==prefabId).ToArray();var prefab=plan.sourcePrefabs.Single(x=>x.sourceId==prefabId);
  var persistentRoot=new GameObject("simulated-saved-prefab-root:"+prefabId){persistent=true,guid="simulated-prefab-guid:"+prefabId,
   localFileId=nextLocal++,assetPath=prefab.path};persistentRoot.activeSelf=planNodeById[prefab.root].active;AssetDatabase.Register(persistentRoot);
  var persistentNodes=new Dictionary<string,GameObject>{{prefab.root,persistentRoot}};
  foreach(var expected in expectedRows){var sourceNode=cloneNodes.TryGetValue(expected.sourceComponentId,out var cloneNode)?cloneNode:oldNodes[expected.sourceNodeId];
   var savedNode=new GameObject("simulated-saved:"+expected.sourceNodeId);savedNode.activeSelf=planNodeById[expected.sourceNodeId].active;savedNode.transform.parent=persistentRoot.transform;
   var sourceGraphic=sourceNode.GetComponent<SkeletonGraphic>();var savedGraphic=savedNode.AddComponent<SkeletonGraphic>();savedGraphic.enabled=sourceGraphic.enabled;savedGraphic.SkeletonDataAsset=sourceGraphic.SkeletonDataAsset;
   var sourceMarker=sourceNode.GetComponent<UnitySpineSourceIdentity>();savedNode.AddComponent<UnitySpineSourceIdentity>(new UnitySpineSourceIdentity{renderer=savedGraphic,
    instanceSourceComponentId=sourceMarker.instanceSourceComponentId,templateSourcePrefabId=sourceMarker.templateSourcePrefabId,
    templateSourceId=sourceMarker.templateSourceId,rendererKind=sourceMarker.rendererKind});
   savedGraphic.persistent=true;savedGraphic.guid="simulated-unsaved-prefab-renderer:"+expected.sourceComponentId;savedGraphic.localFileId=nextLocal++;
   savedGraphic.assetPath=prefab.path;AssetDatabase.Register(savedGraphic);persistentNodes.Add(expected.sourceNodeId,savedNode);}
  var host=MakeRoot("controlled-reopen:"+prefabId,RenderMode.WorldSpace,staticSpineSourceCanvasContext.sourceReferencePixelsPerUnit,false);
  var hostEvidence=MakeHostEvidence(staticSpineSourceCanvasContext,manifest,staticSpineRenderingPlanSha,host.GetComponent<Canvas>().referencePixelsPerUnit);
  staticSpineControlledCanvasContexts.Add(new StaticSpineControlledCanvasRegistration{host=host,canvas=host.GetComponent<Canvas>(),evidence=hostEvidence});
  var loadedRoot=new GameObject("loaded-root:"+prefabId);loadedRoot.transform.parent=host.transform;loadedRoot.activeSelf=planNodeById[prefab.root].active;
  var loadedNodes=new Dictionary<string,GameObject>{{prefab.root,loadedRoot}};var loadedOwners=new List<(StaticSpineRenderingComponent,SkeletonGraphic)>();
  foreach(var expected in expectedRows){var loadedNode=MakeNode(loadedRoot,expected.sourceNodeId,expected,assets[expected.sourceDataAssetId]);loadedNode.activeSelf=planNodeById[expected.sourceNodeId].active;
   loadedNodes.Add(expected.sourceNodeId,loadedNode);loadedOwners.Add((expected,loadedNode.GetComponent<SkeletonGraphic>()));}
  var first=expectedRows[0];var otherHost=MakeRoot("wrong-host:"+prefabId,RenderMode.WorldSpace,host.GetComponent<Canvas>().referencePixelsPerUnit,false);
  var badLoaded=MakeNode(otherHost,first.sourceNodeId,first,assets[first.sourceDataAssetId]);badLoaded.activeSelf=planNodeById[first.sourceNodeId].active;
  var wrongMap=new Dictionary<string,GameObject>(loadedNodes){[first.sourceNodeId]=badLoaded};
  var firstPersistentOwner=persistentNodes[first.sourceNodeId].GetComponent<SkeletonGraphic>();var originalPrefabPath=firstPersistentOwner.assetPath;
  firstPersistentOwner.assetPath="Assets/ForeignPrefabPath.prefab";
  ExpectReject(()=>RegisterStaticSpineReadbackOwnerContext(plan,prefabId,persistentNodes,loadedNodes,host),
   "SPINE_READBACK_OWNER_PERSISTENT_COMPONENT_PATH_OR_IDENTITY_MISMATCH","foreign persistent renderer prefab path");
  firstPersistentOwner.assetPath=originalPrefabPath;refusals++;
  ExpectReject(()=>RegisterStaticSpineReadbackOwnerContext(plan,prefabId,persistentNodes,wrongMap,host),"SPINE_READBACK_OWNER_NOT_UNDER_REGISTERED_CONTROLLED_CANVAS","wrong actual reopened host");wrongHostRefusals++;refusals++;
  RegisterStaticSpineReadbackOwnerContext(plan,prefabId,persistentNodes,loadedNodes,host);savedPairs+=expectedRows.Length;
  foreach(var (expected,loaded) in loadedOwners)Require(TryGetStaticSpineSourceCanvasProof(loaded,expected.sourceComponentId,expected.sourceDataAssetId,manifest,
    staticSpineRenderingPlanSha,out _,out _,out var kind,out var diag)&&kind=="controlled-prefab-reopened-owner","actual loaded saved peer resolves: "+diag);
  activeHosts.Add((host,prefabId,persistentNodes,loadedNodes,loadedOwners));
 }
 Require(savedPairs==75&&activeHosts.Sum(x=>x.owners.Count)==75,"all75 saved/reopened owner pairs registered and queried");
 foreach(var item in activeHosts)UnregisterStaticSpineReadbackOwnerContext(item.host);
 foreach(var item in activeHosts)UnregisterStaticSpineControlledCanvasContext(item.host);
 Require(staticSpineOwnerContextLifecycleRows.Count(x=>x.phase=="controlled-host-release")==75,"all75 owner scopes explicitly released");
 var outputRoot=Environment.GetEnvironmentVariable("MONKEY_OWNER_LIFECYCLE_OUTPUT");Require(!String.IsNullOrWhiteSpace(outputRoot),"private harness output root required");
 Directory.CreateDirectory(Path.Combine(outputRoot,"Assets"));Application.dataPath=Path.Combine(outputRoot,"Assets");
 var evidencePath=WriteStaticSpineOwnerContextLifecycleEvidence();var envelope=JsonDocument.Parse(File.ReadAllText(evidencePath)).RootElement;
 var transitions=envelope.GetProperty("transitions").EnumerateArray().ToArray();var serializedComponents=envelope.GetProperty("components").EnumerateArray().ToArray();
 Require(serializedComponents.Length==75,"lifecycle denominator includes exact actual75");
 Require(transitions.Count(x=>x.GetProperty("phase").GetString()=="source-construction")==75,"75 source registrations serialized");
 Require(transitions.Count(x=>x.GetProperty("phase").GetString()=="native-instance-clone")==37,"36 accepted and one atomic rejected clone attempt serialized");
 Require(transitions.Count(x=>x.GetProperty("phase").GetString()=="native-instance-clone"&&x.GetProperty("verified").GetBoolean())==36,"36 clone transfers verified");
 Require(transitions.Count(x=>x.GetProperty("phase").GetString()=="static-sort-create-capture")==75,"75 static sort create/capture uses serialized");
 Require(transitions.Count(x=>x.GetProperty("phase").GetString()=="saved-prefab-owner-pair")==75,"75 saved/reopened owner pairs serialized");
 Require(transitions.Count(x=>x.GetProperty("phase").GetString()=="controlled-host-release")==75,"75 owner releases serialized");
 Require(transitions.Single(x=>x.GetProperty("phase").GetString()=="native-instance-clone"&&!x.GetProperty("verified").GetBoolean()).GetProperty("diagnostic").GetString().Contains("source-template-instance-identity-mismatch"),"single bad final marker stays diagnosed without batch commit");
 var expectedIds=rows.Select(x=>x.sourceComponentId).ToHashSet(StringComparer.Ordinal);
 Require(serializedComponents.Select(x=>x.GetProperty("sourceComponentId").GetString()).ToHashSet(StringComparer.Ordinal).SetEquals(expectedIds),"serialized source IDs equal actual75 denominator");
 foreach(var expected in rows){var events=transitions.Where(x=>x.GetProperty("sourceComponentId").GetString()==expected.sourceComponentId).ToArray();
  Require(events.Count(x=>x.GetProperty("phase").GetString()=="source-construction")==1&&events.Count(x=>x.GetProperty("phase").GetString()=="saved-prefab-owner-pair")==1&&
   events.Count(x=>x.GetProperty("phase").GetString()=="controlled-host-release")==1&&events.Count(x=>x.GetProperty("phase").GetString()=="static-sort-create-capture")==1,"per-ID source/capture/save/release exactly once: "+expected.sourceComponentId);
  Require(events.Count(x=>x.GetProperty("phase").GetString()=="native-instance-clone")== (cloneOwners.ContainsKey(expected.sourceComponentId)?1:0) +
   (events.Any(x=>x.GetProperty("phase").GetString()=="native-instance-clone"&&!x.GetProperty("verified").GetBoolean())?1:0),"per-ID clone phase matches actual sync denominator: "+expected.sourceComponentId);
 }
 var staleHost=activeHosts[0];var staleOwner=staleHost.owners[0];
 // Explicitly create a new live scope before reset so stale-run rejection cannot pass vacuously.
 var liveHost=MakeRoot("live-before-observe-reset",RenderMode.WorldSpace,staticSpineSourceCanvasContext.sourceReferencePixelsPerUnit,false);
 var liveEvidence=MakeHostEvidence(staticSpineSourceCanvasContext,manifest,staticSpineRenderingPlanSha,liveHost.GetComponent<Canvas>().referencePixelsPerUnit);
 staticSpineControlledCanvasContexts.Add(new StaticSpineControlledCanvasRegistration{host=liveHost,canvas=liveHost.GetComponent<Canvas>(),evidence=liveEvidence});
 var expectedLive=staleOwner.expected;var liveRoot=new GameObject("live-root");liveRoot.transform.parent=liveHost.transform;
 var livePersistent=staleHost.persistentNodes;var liveLoaded=new Dictionary<string,GameObject>{{plan.sourcePrefabs.Single(x=>x.sourceId==staleHost.prefabId).root,liveRoot}};
 foreach(var expected in rows.Where(x=>x.sourcePrefabId==staleHost.prefabId)){var loaded=MakeNode(liveRoot,expected.sourceNodeId,expected,assets[expected.sourceDataAssetId]);loaded.activeSelf=planNodeById[expected.sourceNodeId].active;liveLoaded.Add(expected.sourceNodeId,loaded);}
 var liveNode=liveLoaded[expectedLive.sourceNodeId];
 RegisterStaticSpineReadbackOwnerContext(plan,staleHost.prefabId,livePersistent,liveLoaded,liveHost);
 Require(TryGetStaticSpineSourceCanvasProof(liveNode.GetComponent<SkeletonGraphic>(),expectedLive.sourceComponentId,expectedLive.sourceDataAssetId,manifest,
  staticSpineRenderingPlanSha,out _,out _,out _,out _),"live owner/host registered before startup reset");
 var savedRendering=staticSpineRenderingPlan;var savedContext=staticSpineSourceCanvasContext;
 ResetStaticSpineOwnerLifecycleRegistries();
 Require(!TryGetStaticSpineSourceCanvasProof(liveNode.GetComponent<SkeletonGraphic>(),expectedLive.sourceComponentId,expectedLive.sourceDataAssetId,manifest,
  staticSpineRenderingPlanSha,out _,out _,out _,out _),"same alive stale owner/host refused after Observe reset");
 staticSpineRenderingPlan=savedRendering;staticSpineRenderingPlanSha=savedContext.renderingPlanSha256;staticSpineSourceCanvasContext=savedContext;
 var freshHost=MakeRoot("fresh-observe-host",RenderMode.WorldSpace,savedContext.sourceReferencePixelsPerUnit,false);
 staticSpineControlledCanvasContexts.Add(new StaticSpineControlledCanvasRegistration{host=freshHost,canvas=freshHost.GetComponent<Canvas>(),
  evidence=MakeHostEvidence(savedContext,manifest,staticSpineRenderingPlanSha,freshHost.GetComponent<Canvas>().referencePixelsPerUnit)});
 var freshRoot=new GameObject("fresh-loaded-root");freshRoot.transform.parent=freshHost.transform;
 var freshLoaded=new Dictionary<string,GameObject>{{plan.sourcePrefabs.Single(x=>x.sourceId==staleHost.prefabId).root,freshRoot}};
 foreach(var expected in rows.Where(x=>x.sourcePrefabId==staleHost.prefabId)){var loaded=MakeNode(freshRoot,expected.sourceNodeId,expected,assets[expected.sourceDataAssetId]);loaded.activeSelf=planNodeById[expected.sourceNodeId].active;freshLoaded.Add(expected.sourceNodeId,loaded);}
 var freshNode=freshLoaded[expectedLive.sourceNodeId];
 RegisterStaticSpineReadbackOwnerContext(plan,staleHost.prefabId,livePersistent,freshLoaded,freshHost);
 Require(TryGetStaticSpineSourceCanvasProof(freshNode.GetComponent<SkeletonGraphic>(),expectedLive.sourceComponentId,expectedLive.sourceDataAssetId,manifest,
  staticSpineRenderingPlanSha,out _,out _,out _,out _),"freshly registered owner/host works after startup reset");
 Console.WriteLine("production actual16 owner lifecycle: source=75 direct=39 clone=36 rejectedBatch=1 sortCapture=75 savedPair=75 release=75 owners="+sourcePrefabIds.Length+
  " instances="+groups.Count+" dataAssets="+assets.Count+" refusals="+refusals+" wrongHost="+wrongHostRefusals+"; Editor persistence remains simulated");
}
'''
    stubs = r'''
namespace UnityEngine {
 public class Object { public bool persistent,destroyed; public string guid,assetPath;public long localFileId;
  public static bool operator==(Object a,Object b)=>ReferenceEquals(a,b)||(ReferenceEquals(a,null)&&!ReferenceEquals(b,null)&&b.destroyed)||(ReferenceEquals(b,null)&&!ReferenceEquals(a,null)&&a.destroyed);
  public static bool operator!=(Object a,Object b)=>!(a==b);public override bool Equals(object o)=>this==o as Object;public override int GetHashCode()=>base.GetHashCode(); }
 public class Component:Object { public GameObject gameObject;public Transform transform=>gameObject.transform;public T GetComponent<T>() where T:Component=>gameObject.GetComponent<T>();public T[] GetComponents<T>() where T:class=>gameObject.GetComponents<T>();public T GetComponentInParent<T>(bool includeInactive=false) where T:Component=>gameObject.GetComponentInParent<T>(includeInactive); }
 public sealed class GameObject:Object { readonly List<Component> components=new();public string name;public bool activeSelf=true;public Transform transform;
  public GameObject(string n){name=n;transform=new Transform{gameObject=this};}
  public T AddComponent<T>() where T:Component,new(){var c=new T{gameObject=this};components.Add(c);return c;}
  public T AddComponent<T>(T c) where T:Component{c.gameObject=this;components.Add(c);return c;}
  public T GetComponent<T>() where T:Component=>components.OfType<T>().FirstOrDefault();public T[] GetComponents<T>() where T:class=>components.OfType<T>().ToArray();
  public T GetComponentInParent<T>(bool includeInactive=false) where T:Component{for(var t=transform;t!=null;t=t.parent){var x=t.gameObject.GetComponent<T>();if(x!=null)return x;}return null;}
 }
 public sealed class Transform:Object {public GameObject gameObject;public Transform parent;public string name=>gameObject.name;public int GetSiblingIndex()=>0;public bool IsChildOf(Transform other){for(var t=this;t!=null;t=t.parent)if(t==other)return true;return false;} }
 public enum RenderMode{ScreenSpaceOverlay,ScreenSpaceCamera,WorldSpace}public class Canvas:Component{public RenderMode renderMode;public float referencePixelsPerUnit;}
 public static class Application{public static string dataPath;}
 public static class JsonUtility {static readonly System.Text.Json.JsonSerializerOptions O=new(){IncludeFields=true};public static T FromJson<T>(string s)=>System.Text.Json.JsonSerializer.Deserialize<T>(s,O);public static string ToJson(object x,bool pretty=false)=>System.Text.Json.JsonSerializer.Serialize(x,new System.Text.Json.JsonSerializerOptions{IncludeFields=true,WriteIndented=pretty});}
}
namespace UnityEngine.UI {public class Graphic:UnityEngine.Component{}public class CanvasScaler:UnityEngine.Component{public enum ScaleMode{ConstantPixelSize,ScaleWithScreenSize,ConstantPhysicalSize}public ScaleMode uiScaleMode;public float referencePixelsPerUnit,matchWidthOrHeight;public UnityEngine.Vector2 referenceResolution;}}
namespace UnityEngine {public struct Vector2{public float x,y;public Vector2(float a,float b){x=a;y=b;}}}
namespace Spine.Unity {public class SkeletonDataAsset:UnityEngine.Object{}public class SkeletonGraphic:UnityEngine.UI.Graphic{public SkeletonDataAsset SkeletonDataAsset;public bool enabled=true;}}
namespace Monkey.Targets.Spine {public sealed class UnitySpineSourceIdentity:global::UnityEngine.Component{public global::Spine.Unity.SkeletonGraphic renderer;public string instanceSourceComponentId,templateSourcePrefabId,templateSourceId,rendererKind;}
 public static class UnitySpineNativeFactory {public class DataAssetSpec{public string skeletonDataAssetPath;}public class DataAssetReadback{public float scale;}}}
namespace UnityEditor {public static class EditorUtility{public static bool IsPersistent(UnityEngine.Object o)=>o!=null&&o.persistent;}
 public static class AssetDatabase {static readonly Dictionary<string,List<UnityEngine.Object>> Paths=new();public static void Register(UnityEngine.Object o){if(o!=null&&o.assetPath!=null){if(!Paths.TryGetValue(o.assetPath,out var rows))Paths[o.assetPath]=rows=new();if(!rows.Contains(o))rows.Add(o);}}
 public static string GetAssetPath(UnityEngine.Object o)=>o==null?null:o.assetPath;public static T LoadAssetAtPath<T>(string p) where T:UnityEngine.Object=>Paths.TryGetValue(p,out var rows)?rows.OfType<T>().FirstOrDefault():null;
 public static bool TryGetGUIDAndLocalFileIdentifier(UnityEngine.Object o,out string g,out long l){g=o==null?null:o.guid;l=o==null?0:o.localFileId;return o!=null&&!String.IsNullOrWhiteSpace(g)&&l!=0;}}
}
'''
    wrapper = "using System;using System.Collections.Generic;using System.IO;using System.Linq;using System.Security.Cryptography;using System.Text;using System.Text.Json;using UnityEngine;using UnityEngine.UI;using UnityEditor;using Spine.Unity;using Monkey.Targets.Spine;\n" + stubs + "\npublic static partial class Harness {\nstatic partial void RebindOptionalStaticSpineNativeInstanceContext(Plan plan,PrefabInstanceSpec instance,Dictionary<string,GameObject> nodes,Dictionary<UnityEngine.Object,UnityEngine.Object> replacements);\n" + members + "\n" + harness + "\n}"
    with tempfile.TemporaryDirectory(prefix="monkey-owner-lifecycle-") as temporary:
        out = Path(temporary)
        (out / "Harness.cs").write_text(wrapper, encoding="utf-8")
        (out / "Harness.csproj").write_text(
            '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>'
            '<TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings>'
            '<Nullable>disable</Nullable></PropertyGroup></Project>', encoding="utf-8")
        (out / "NuGet.Config").write_text("<configuration><packageSources><clear /></packageSources></configuration>", encoding="utf-8")
        candidate = out / "private-candidate"
        env = {**__import__("os").environ, "MONKEY_OWNER_LIFECYCLE_OUTPUT": str(candidate)}
        result = subprocess.run([dotnet, "run", "--project", str(out / "Harness.csproj"),
            "--property:RestoreConfigFile=" + str(out / "NuGet.Config")], capture_output=True, text=True, timeout=120, env=env)
        if result.returncode:
            debug_root = ROOT / ".private/foodstreet-four-activity-20261104/dev22-owner-lifecycle"
            debug_root.mkdir(parents=True, exist_ok=True)
            (debug_root / "offline-lifecycle-harness.generated.cs").write_text(wrapper, encoding="utf-8")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "source=2 clone=2 rejectedClone=2 savedPair=2 release=1 sameTemplateInstances=2 refusals=18" in result.stdout
        assert "simulated, not accepted" in result.stdout
        evidence = candidate / "Analysis/Readback/SpineRendering/owner-context-lifecycle.json"
        assert evidence.is_file()
        envelope = json.loads(evidence.read_text())
        assert len(envelope["components"]) == 2
        receipt_value = os.environ.get("MONKEY_OWNER_LIFECYCLE_RECEIPT")
        if receipt_value:
            receipt = Path(receipt_value)
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text(json.dumps({
                "schema": "monkey-offline-spine-owner-lifecycle-harness/1",
                "output": result.stdout.strip(),
                "components": len(envelope["components"]),
                "transitionCount": len(envelope["transitions"]),
                "phaseCounts": {phase: sum(row["phase"] == phase for row in envelope["transitions"])
                                for phase in sorted({row["phase"] for row in envelope["transitions"]})},
                "rejectedCloneRows": sum(row["phase"] == "native-instance-clone" and not row["verified"]
                                          for row in envelope["transitions"]),
                "negativeCases": ["unregistered owner", "wrong marker during clone registration",
                                  "wrong marker during lookup", "wrong SkeletonDataAsset reference",
                                  "missing data GUID", "Canvas PPU drift", "manifest pin drift",
                                  "removed owner registry entry", "destroyed owner", "wrong saved/reopened host",
                                  "stale owner and host after reset"],
                "persistentGuidAndUnityEditorBehavior": "simulated only; not native Editor acceptance",
            }, indent=2) + "\n", encoding="utf-8")
        fixture_value = os.environ.get("MONKEY_OWNER_LIFECYCLE_ACTUAL_FIXTURE")
        if fixture_value:
            fixture_path = Path(fixture_value).resolve()
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            input_paths = [Path(item["path"]) for item in fixture["pins"]]
            for item in fixture.get("dataAssetIdPathPins", []):
                candidate_root = Path(item.get("candidateRoot", ""))
                if candidate_root:
                    input_paths.extend([candidate_root / item["skeletonDataAssetPath"],
                                        candidate_root / (item["skeletonDataAssetPath"] + ".meta")])
            before_pins = [(path, hashlib.sha256(path.read_bytes()).hexdigest()) for path in input_paths if path.is_file()]
            actual_output = Path(os.environ.get("MONKEY_OWNER_LIFECYCLE_ACTUAL_OUTPUT",
                ROOT / ".private/foodstreet-four-activity-20261104/dev22-owner-lifecycle/actual-lifecycle-harness-output"))
            actual_output.mkdir(parents=True, exist_ok=True)
            assembly = out / "bin/Debug/net8.0/Harness.dll"
            actual_env = {**__import__("os").environ, "MONKEY_OWNER_LIFECYCLE_OUTPUT": str(actual_output)}
            actual_run = subprocess.run([dotnet, str(assembly), str(fixture_path)], capture_output=True,
                text=True, timeout=240, env=actual_env)
            if actual_run.returncode:
                debug_root = ROOT / ".private/foodstreet-four-activity-20261104/dev22-owner-lifecycle"
                debug_root.mkdir(parents=True, exist_ok=True)
                (debug_root / "offline-lifecycle-harness.generated.cs").write_text(wrapper, encoding="utf-8")
            assert actual_run.returncode == 0, actual_run.stdout + actual_run.stderr
            assert "source=75 direct=39 clone=36 rejectedBatch=1 sortCapture=75 savedPair=75 release=75" in actual_run.stdout
            assert "refusals=32 wrongHost=8" in actual_run.stdout
            actual_evidence_path = actual_output / "Analysis/Readback/SpineRendering/owner-context-lifecycle.json"
            assert actual_evidence_path.is_file()
            actual_evidence = json.loads(actual_evidence_path.read_text(encoding="utf-8"))
            actual_components = actual_evidence["components"]
            actual_transitions = actual_evidence["transitions"]
            assert len(actual_components) == 75
            phase_counts = {phase: sum(row["phase"] == phase for row in actual_transitions)
                            for phase in sorted({row["phase"] for row in actual_transitions})}
            assert phase_counts == {"controlled-host-release": 75, "native-instance-clone": 37,
                                    "saved-prefab-owner-pair": 75, "source-construction": 75,
                                    "static-sort-create-capture": 75}
            assert sum(row["phase"] == "native-instance-clone" and not row["verified"]
                       for row in actual_transitions) == 1
            after_pins = [(path, hashlib.sha256(path.read_bytes()).hexdigest()) for path, _ in before_pins]
            assert after_pins == before_pins, "actual16 fixture inputs changed during offline lifecycle simulation"
            actual_receipt_value = os.environ.get("MONKEY_OWNER_LIFECYCLE_ACTUAL_RECEIPT")
            if actual_receipt_value:
                actual_receipt = Path(actual_receipt_value)
                actual_receipt.parent.mkdir(parents=True, exist_ok=True)
                actual_receipt.write_text(json.dumps({
                    "schema": "monkey-actual16-offline-spine-owner-lifecycle/1",
                    "output": actual_run.stdout.strip(),
                    "componentCount": len(actual_components),
                    "transitionCount": len(actual_transitions),
                    "phaseCounts": phase_counts,
                    "rejectedCloneRows": 1,
                    "actualInputPins": [{"path": str(path), "sha256": digest} for path, digest in before_pins],
                    "inputPinsUnchanged": True,
                    "fixturePins": fixture["pins"],
                    "negativeCases": ["unregistered target clone", "atomic final-marker rejection of a multi-owner batch",
                                      "wrong renderer marker", "wrong data asset", "missing data GUID",
                                      "clone Canvas PPU drift", "source manifest drift", "removed owner registration",
                                      "destroyed clone", "foreign persistent component prefab path", "wrong reopened Canvas host",
                                      "stale live host after startup reset"],
                    "prefabRendererGUIDAndNativeEditorPersistence": "simulated for unsaved prefabs; not native Editor acceptance",
                    "dataAssetGUIDsAndLocalFileIDs": "read from pinned native16 candidate asset metadata, modeled by offline AssetDatabase stub",
                    "staticSortCreateCapture": "producer lifecycle callback recorded for all75 owners; native queue/render/pixel capture not executed",
                    "editorExecuted": False,
                }, indent=2) + "\n", encoding="utf-8")
