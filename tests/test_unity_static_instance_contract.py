"""Run production carrier creation and strict counterpart pairing offline.

The managed GameObject stub covers component lists only. Native serialization,
Prefab connections and saved/cold identities remain real Editor checks.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from test_unity_static_family_contract import declaration

ROOT=Path(__file__).resolve().parents[1]


class UnityStaticInstanceContractTests(unittest.TestCase):
    def test_source_instances_have_real_typed_counterparts_and_reference_pairs(self):
        dotnet=shutil.which('dotnet')
        if not dotnet:self.skipTest('dotnet SDK unavailable')
        targets=ROOT/'src/monkey/targets'
        source=(targets/'UnityStaticSpineContinuation.cs').read_text()
        members='\n'.join(declaration(source,key)for key in (
            '[Serializable] sealed class SpineEnvelope', '[Serializable] sealed class SpineComponent',
            '[Serializable] sealed class SpineDataReference', '[Serializable] sealed class SpineField',
            '[Serializable] sealed class SpineObjectReference', '[Serializable] sealed class SpineData\n',
            '[Serializable] sealed class SpinePage', '[Serializable] sealed class SpinePma',
            'static NativeStaticSpineReference SpineCarrier(', 'static void PrepareStaticSpineCarriers(',
            'static void SpineAssignFields(', 'static UnityEngine.Object SpineResolveObject(',
            'static bool SpineCarrierIdentityMatches('))
        members+=declaration(source,'static partial void ResolveOptionalStaticSpineInstanceCounterpart(').replace('static partial void','static void')
        members+=declaration((targets/'UnityPrefabInstances.cs').read_text(),'static void PairNativeInstanceComponents(')
        runtime='\n'.join(re.sub(r'^using .*;\n','', (targets/name).read_text(),flags=re.M)
                          for name in ('NativeStaticSpineData.cs','NativeStaticSpineReference.cs','NativeStaticAnimationBinding.cs'))
        stubs=r'''
namespace UnityEngine {
public class Object{}
public class Component:Object {public GameObject gameObject;}
public class MonoBehaviour:Component {public bool enabled;}
public class Transform:Component{} public class CanvasGroup:Component{} public class Animator:Component{}
public class AnimationClip:Object{} public class TextAsset:Object{} public class ScriptableObject:Object{}
public class SerializeField:Attribute{} public class DisallowMultipleComponent:Attribute{}
public class GameObject:Object {
    readonly List<Component> components=new List<Component>();
    public T[] GetComponents<T>(){return components.OfType<T>().ToArray();}
    public Component[] GetComponents(Type t){return components.Where(t.IsInstanceOfType).ToArray();}
    public T AddComponent<T>()where T:Component,new(){var c=new T();c.gameObject=this;components.Add(c);return c;}
    public Component AddComponent(Type t){var c=(Component)Activator.CreateInstance(t);c.gameObject=this;components.Add(c);return c;}
}}
public class NativeRetainedMaterial:UnityEngine.Object {public bool retentionOnly=true,renderingRecovered;}
static class EditorUtility {public static void SetDirty(UnityEngine.Object value){}}
static class AssetDatabase {
    public static readonly Dictionary<string,UnityEngine.Object> Assets=new Dictionary<string,UnityEngine.Object>();
    public static T LoadAssetAtPath<T>(string path)where T:UnityEngine.Object{return Assets.TryGetValue(path,out var value)?value as T:null;}
}
static class UnityStaticRetainedAssets {
    public static NativeRetainedMaterial Material;
    public static UnityEngine.Object Resolve(object contract,string id){return id=="material"?Material:null;}
}
'''
        program=r'''
class Plan {public object staticRetainedAssets=new object();}
static Plan spineStaticPlan;static SpineEnvelope spineStaticEnvelope;
static void IdentifyOptionalSpineDerivedComponent(Component c,ref bool derived){}
static void Require(bool value,string message){if(!value)throw new Exception(message);}
static SpineComponent Row(string id,string node){return new SpineComponent{
    sourceComponentId=id,sourceTemplateComponentId="template",sourcePrefabId="owner",sourceNodeId=node,sourceTemplateNodeId="T",
    sourceComponentEnabledStatus="plan-source-value",sourceComponentEnabled=true,
    sourceDataReference=new SpineDataReference{sourceDataAssetId="data"},
    sourceFields=new[]{new SpineField{name="defaultSkin",present=true,stringValue=""}},
    sourceFieldsJson="original fields",sourceFieldsSha256="fields hash",sourceComponentEnvelopeJson="original component",
    sourceObjectReferences=new[]{new SpineObjectReference{sourceAssetId="data",sourceUuid="data-uuid",fieldPath="/data",targetReferenceKind="source-spine-data"},
        new SpineObjectReference{sourceAssetId="material",sourceUuid="material-uuid",fieldPath="/materials/0",targetReferenceKind="retained-source-material"}}};}
static void Animation(GameObject node,string id){
    node.AddComponent<Animator>();var c=node.AddComponent<NativeStaticAnimationBinding>();
    c.Configure(id,id+"-node",null,false,true,true,true,true,true,Array.Empty<string>(),null,Array.Empty<NativeStaticAnimationBinding.ClipSlot>());
}
static void Main(){
    var nodes=new Dictionary<string,GameObject>{{"T",new GameObject()},{"A",new GameObject()},{"B",new GameObject()}};
    var rows=new[]{Row("template","T"),Row("instance-A","A"),Row("instance-B","B")};
    var data=new NativeStaticSpineData{sourceDataAssetId="data"};AssetDatabase.Assets["data.asset"]=data;
    UnityStaticRetainedAssets.Material=new NativeRetainedMaterial();
    spineStaticPlan=new Plan();spineStaticEnvelope=new SpineEnvelope{components=rows,dataAssets=new[]{new SpineData{sourceDataAssetId="data",nativeStaticSpineDataAssetPath="data.asset"}}};
    PrepareStaticSpineCarriers(spineStaticPlan,nodes);PrepareStaticSpineCarriers(spineStaticPlan,nodes);
    foreach(var row in rows){var c=SpineCarrier(row,nodes);
        Require(c!=null&&nodes[row.sourceNodeId].GetComponents<NativeStaticSpineReference>().Length==1,"one real counterpart per node");
        Require(SpineCarrierIdentityMatches(c,row)&&c.sourceFieldsJson=="original fields","exact source identity and fields");
        Require(c.sourceData==data&&c.sourceObjectReferences[0]==data&&c.sourceMaterials[0]==UnityStaticRetainedAssets.Material,"exact owned references");
        Require(!c.enabled&&c.nonRendering&&!c.dynamicBehaviorRestored,"disabled nonrendering scope");}
    foreach(var row in rows.Skip(1)){
        var old=nodes[row.sourceNodeId];Animation(old,row.sourceComponentId+"-animation");
        var target=new GameObject();var destination=target.AddComponent<NativeStaticSpineReference>();destination.sourceTemplateComponentId="template";Animation(target,"template-animation");
        var map=new Dictionary<UnityEngine.Object,UnityEngine.Object>();var pairs=new List<KeyValuePair<Component,Component>>();
        PairNativeInstanceComponents(old,target,map,pairs);
        var original=SpineCarrier(row,nodes);
        Require(pairs.Count==3&&map[original]==destination,"Spine and Animation counterpart pairing");
        Require(map[old.GetComponents<NativeStaticAnimationBinding>()[0]]==target.GetComponents<NativeStaticAnimationBinding>()[0],"exact Animation reference replacement");
        Require(map.Values.Distinct().Count()==3,"one-to-one component replacement");
        Require(SpineCarrierIdentityMatches(original,row)&&original.sourceData==data,"source state survives mapping");
    }
    var extra=nodes["A"].AddComponent<NativeStaticSpineReference>();extra.sourceComponentId="extra-A";extra.sourceTemplateComponentId="extra-template";
    var reversed=new GameObject();var targetExtra=reversed.AddComponent<NativeStaticSpineReference>();targetExtra.sourceTemplateComponentId="extra-template";
    var targetMain=reversed.AddComponent<NativeStaticSpineReference>();targetMain.sourceTemplateComponentId="template";Animation(reversed,"template-animation");
    var exactMap=new Dictionary<UnityEngine.Object,UnityEngine.Object>();var exactPairs=new List<KeyValuePair<Component,Component>>();
    PairNativeInstanceComponents(nodes["A"],reversed,exactMap,exactPairs);
    Require(exactMap[SpineCarrier(rows[1],nodes)]==targetMain&&exactMap[extra]==targetExtra,"same-type components use exact template identity, not order");
    var absent=new GameObject();var unsupported=new GameObject();unsupported.AddComponent<NativeStaticSpineReference>();
    bool refused=false;try{PairNativeInstanceComponents(absent,unsupported,new Dictionary<UnityEngine.Object,UnityEngine.Object>(),new List<KeyValuePair<Component,Component>>());}
    catch(InvalidOperationException e){refused=e.Message.Contains("no supported instance counterpart");}
    Require(refused,"missing source counterpart still refused");
    nodes["A"]=nodes["T"];Require(SpineCarrier(rows[1],nodes)==null,"template carrier cannot impersonate instance");
    Console.WriteLine("production static instance counterparts: pass");
}'''
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp).resolve();(out/'Probe.cs').write_text('using System;using System.Linq;using System.Collections.Generic;using UnityEngine;'+stubs+runtime+'class Probe{'+members+program+'}')
            (out/'Probe.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><Nullable>disable</Nullable><NoWarn>CS0649</NoWarn></PropertyGroup></Project>')
            (out/'NuGet.Config').write_text('<configuration><packageSources><clear /></packageSources></configuration>')
            result=subprocess.run([dotnet,'run','--project',str(out/'Probe.csproj'),'--property:RestoreConfigFile='+str(out/'NuGet.Config')],capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('production static instance counterparts: pass',result.stdout)
