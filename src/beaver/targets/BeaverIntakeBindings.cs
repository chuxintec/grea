// Native preparation for existing additive intake. MIT license.
#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;

public static class BeaverIntakeBindings {
    [Serializable] public class Binding {
        public string source,sourceGuid,sourceSha256,sourceMetaSha256,sourceType,sourceAssembly;
        public string target,targetGuid,targetSha256,targetMetaSha256,targetType,targetAssembly;
        public long sourceLocalId,targetLocalId;
    }
    [Serializable] public class Job { public string projectRoot,stage,planSha256,mode,bridgeRoot,bridgeAssembly; public Binding[] bindings; public string[] prefabs; }
    [Serializable] public class Property { public string path,type,value; }
    [Serializable] public class Owner { public string guid,type; public long localId; public List<Property> properties=new List<Property>(); }
    [Serializable] public class Prefab { public string path,guid; public List<Owner> owners=new List<Owner>(); }
    [Serializable] public class Snapshot { public string planSha256; public List<Prefab> prefabs=new List<Prefab>(); }
    [Serializable] public class Report { public string status,error,planSha256,mode; public int referencesMapped; public List<string> mappedSourceGuids=new List<string>(); public Snapshot snapshot; }
    [Serializable] class Box<T> { public T value; }
    [Serializable] class Curve { public Keyframe[] keys; public int pre,post; }
    [Serializable] class GradientValue { public GradientColorKey[] colors; public GradientAlphaKey[] alphas; public int mode; }
    static Job job; static Report report;
    static readonly CultureInfo Culture=CultureInfo.InvariantCulture;
    static readonly Dictionary<string,MonoScript> replacements=new Dictionary<string,MonoScript>(StringComparer.Ordinal);
    static string Full(string relative) {
        if(String.IsNullOrEmpty(relative)||!relative.StartsWith("Assets/",StringComparison.Ordinal)||relative.Contains("\\")||relative.Split('/').Any(x=>x==""||x=="."||x==".."))throw new Exception("Unsafe preparation asset path");
        var result=Path.GetFullPath(Path.Combine(job.projectRoot,relative));
        if(!result.StartsWith(Path.GetFullPath(job.projectRoot)+Path.DirectorySeparatorChar,StringComparison.Ordinal))throw new Exception("Escaped preparation project");
        return result;
    }
    static string Hash(string path) { using(var s=File.OpenRead(path))using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(s)).Replace("-","").ToLowerInvariant(); }
    static string Id(UnityEngine.Object value,bool normalize=true) {
        if(value==null)return "null";
        string guid;long local;
        if(!EditorUtility.IsPersistent(value)||!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value,out guid,out local)||String.IsNullOrEmpty(guid)||local==0)throw new Exception("Nonpersistent or unidentified reference");
        if(!normalize)return guid+"#"+local.ToString(Culture);
        var runtime=value.GetType();
        var semantic=job.bindings.SingleOrDefault(b=>b.sourceType==runtime.FullName&&(b.sourceAssembly==runtime.Assembly.GetName().Name||job.bridgeAssembly==runtime.Assembly.GetName().Name));
        var type=semantic==null?runtime.FullName+"@"+runtime.Assembly.GetName().Name:"binding:"+semantic.targetAssembly+"/"+semantic.targetType;
        var script=value as MonoScript;
        if(script!=null) {
            var resolved=script.GetClass();if(resolved==null)throw new Exception("MonoScript reference class is unresolved");
            var b=job.bindings.SingleOrDefault(r=>r.sourceGuid==guid||r.targetGuid==guid);
            if(b!=null) {
                if(local!=b.sourceLocalId||resolved.FullName!=b.sourceType||(resolved.Assembly.GetName().Name!=b.sourceAssembly&&resolved.Assembly.GetName().Name!=job.bridgeAssembly))throw new Exception("MonoScript persistent type/localID differs");
                return b.targetGuid+"#"+b.targetLocalId+"|"+type+"|binding:"+b.targetAssembly+"/"+b.targetType;
            }
            type+="|script:"+resolved.FullName+"@"+resolved.Assembly.GetName().Name;
        }
        return guid+"#"+local.ToString(Culture)+"|"+type;
    }
    static string Json<T>(T value) { return JsonUtility.ToJson(new Box<T>{value=value}); }
    static string Value(SerializedProperty p) {
        switch(p.propertyType) {
            case SerializedPropertyType.Generic:return "structure:"+p.type+(p.isArray?":"+p.arraySize.ToString(Culture):"");
            case SerializedPropertyType.Integer:return p.longValue.ToString(Culture);
            case SerializedPropertyType.Boolean:return p.boolValue?"true":"false";
            case SerializedPropertyType.Float:return p.doubleValue.ToString("R",Culture);
            case SerializedPropertyType.String:return p.stringValue;
            case SerializedPropertyType.Color:return Json(p.colorValue);
            case SerializedPropertyType.ObjectReference:
                if(p.objectReferenceValue==null&&p.objectReferenceEntityIdValue!=EntityId.None)throw new Exception("Unresolved serialized reference "+p.propertyPath);
                return Id(p.objectReferenceValue);
            case SerializedPropertyType.LayerMask:case SerializedPropertyType.Enum:case SerializedPropertyType.ArraySize:case SerializedPropertyType.Character:return p.intValue.ToString(Culture);
            case SerializedPropertyType.Vector2:return Json(p.vector2Value);
            case SerializedPropertyType.Vector3:return Json(p.vector3Value);
            case SerializedPropertyType.Vector4:return Json(p.vector4Value);
            case SerializedPropertyType.Rect:return Json(p.rectValue);
            case SerializedPropertyType.Bounds:return Json(p.boundsValue);
            case SerializedPropertyType.Quaternion:return Json(p.quaternionValue);
            case SerializedPropertyType.Vector2Int:return Json(p.vector2IntValue);
            case SerializedPropertyType.Vector3Int:return Json(p.vector3IntValue);
            case SerializedPropertyType.RectInt:return Json(p.rectIntValue);
            case SerializedPropertyType.BoundsInt:return Json(p.boundsIntValue);
            case SerializedPropertyType.Hash128:return p.hash128Value.ToString();
            case SerializedPropertyType.AnimationCurve:
                var c=p.animationCurveValue;return c==null?"null":JsonUtility.ToJson(new Curve{keys=c.keys,pre=(int)c.preWrapMode,post=(int)c.postWrapMode});
            case SerializedPropertyType.Gradient:
                var g=p.gradientValue;return g==null?"null":JsonUtility.ToJson(new GradientValue{colors=g.colorKeys,alphas=g.alphaKeys,mode=(int)g.mode});
            default:throw new Exception("Unsupported exact property kind "+p.propertyType+" at "+p.propertyPath);
        }
    }
    static void Scripts() {
        foreach(var b in job.bindings) {
            var bridge=job.bridgeRoot+"/"+Path.GetFileName(b.source);
            if(b.sourceGuid==b.targetGuid||b.sourceType!=b.targetType||b.sourceSha256!=b.targetSha256)throw new Exception("Non-equivalent script mapping");
            foreach(var side in new[]{false,true}) {
                var path=side?bridge:b.source;
                if(Hash(Full(path))!=(side?b.targetSha256:b.sourceSha256)||Hash(Full(path+".meta"))!=(side?b.targetMetaSha256:b.sourceMetaSha256))throw new Exception("Script source/meta pin differs "+path);
                var script=AssetDatabase.LoadAssetAtPath<MonoScript>(path);var type=script==null?null:script.GetClass();
                var expectedGuid=side?b.targetGuid:b.sourceGuid;var expectedAssembly=side?job.bridgeAssembly:b.sourceAssembly;
                if(type==null||type.FullName!=b.sourceType||type.Assembly.GetName().Name!=expectedAssembly||Id(script,false)!=expectedGuid+"#"+(side?b.targetLocalId:b.sourceLocalId).ToString(Culture)||AssetDatabase.GUIDToAssetPath(expectedGuid)!=path)throw new Exception("Native MonoScript type/assembly/GUID/localID differs "+path);
                if(side)replacements.Add(b.sourceGuid,script);
            }
        }
    }
    static GameObject Load(string path) {
        var asset=AssetDatabase.LoadAssetAtPath<GameObject>(path);
        if(asset==null||PrefabUtility.GetPrefabAssetType(asset)!=PrefabAssetType.Regular)throw new Exception("Only regular native Prefabs are supported "+path);
        foreach(var dep in AssetDatabase.GetDependencies(path,true))
            if(dep.EndsWith(".prefab",StringComparison.OrdinalIgnoreCase)&&!job.prefabs.Contains(dep))throw new Exception("Unselected nested Prefab dependency "+dep);
        return asset;
    }
    static IEnumerable<UnityEngine.Object> Objects(GameObject asset) {
        foreach(var t in asset.GetComponentsInChildren<Transform>(true)) {
            yield return t.gameObject;
            foreach(var component in t.GetComponents<Component>()) {
                if(component==null)throw new Exception("Missing script in preparation Prefab");
                yield return component;
            }
        }
    }
    static UnityEngine.Object ResolveOwner(string path,string guid,long localId) {
        // Replacing m_Script destroys the old managed component wrapper. Never
        // retain that wrapper across ApplyModifiedPropertiesWithoutUndo.
        var found=new List<UnityEngine.Object>();
        foreach(var candidate in Objects(Load(path))) {
            string currentGuid;long currentLocal;
            if(AssetDatabase.TryGetGUIDAndLocalFileIdentifier(candidate,out currentGuid,out currentLocal)&&currentGuid==guid&&currentLocal==localId)found.Add(candidate);
        }
        if(found.Count!=1)throw new Exception("Exact persistent owner was lost/duplicated after native script replacement "+path+"#"+guid+":"+localId);
        return found[0];
    }
    static Snapshot Capture(bool cold) {
        var snap=new Snapshot{planSha256=job.planSha256};int count=0;
        foreach(var path in job.prefabs.OrderBy(x=>x,StringComparer.Ordinal)) {
            var asset=Load(path);var prefab=new Prefab{path=path,guid=AssetDatabase.AssetPathToGUID(path)};snap.prefabs.Add(prefab);
            foreach(var value in Objects(asset)) {
                if(++count>50000)throw new Exception("Preparation object budget exceeded");
                string guid;long local;
                if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value,out guid,out local)||local==0)throw new Exception("Object identity unavailable");
                var type=value.GetType();var binding=job.bindings.SingleOrDefault(b=>b.sourceType==type.FullName&&(b.sourceAssembly==type.Assembly.GetName().Name||job.bridgeAssembly==type.Assembly.GetName().Name));
                var owner=new Owner{guid=guid,localId=local,type=binding==null?type.AssemblyQualifiedName:"binding:"+binding.targetAssembly+"/"+binding.targetType};prefab.owners.Add(owner);
                using(var so=new SerializedObject(value)) {
                    so.UpdateIfRequiredOrScript();var p=so.GetIterator();int properties=0;bool enterChildren=true;
                    while(p.Next(enterChildren)) {
                        // A PPtr is an atomic persistent reference. Unity's
                        // internal m_FileID below it is a transient instance
                        // handle, not its AssetDatabase file/local identifier.
                        enterChildren=p.propertyType!=SerializedPropertyType.ObjectReference;
                        if(++properties>250000)throw new Exception("Serialized property budget exceeded");
                        if(p.propertyPath=="m_Script"&&binding!=null) {
                            var actual=Id(p.objectReferenceValue,false);
                            if(cold&&(actual!=binding.targetGuid+"#"+binding.targetLocalId||type.Assembly.GetName().Name!=job.bridgeAssembly))throw new Exception("Cold reopened component retained the old script identity");
                            if(actual!=binding.sourceGuid+"#"+binding.sourceLocalId&&actual!=binding.targetGuid+"#"+binding.targetLocalId)throw new Exception("Unexpected component script identity");
                        }
                        if(p.propertyPath=="m_EditorClassIdentifier"&&binding!=null) {
                            var v=p.stringValue;
                            if(v!=""&&v!=binding.sourceAssembly+"::"+binding.sourceType&&v!=job.bridgeAssembly+"::"+binding.sourceType)throw new Exception("Unexpected Editor class identifier");
                            owner.properties.Add(new Property{path=p.propertyPath,type=p.propertyType.ToString(),value="binding:"+binding.targetType});
                        } else owner.properties.Add(new Property{path=p.propertyPath,type=p.propertyType.ToString()+":"+p.type,value=Value(p)});
                    }
                }
                owner.properties=owner.properties.OrderBy(p=>p.path,StringComparer.Ordinal).ToList();
            }
            prefab.owners=prefab.owners.OrderBy(o=>o.guid,StringComparer.Ordinal).ThenBy(o=>o.localId).ToList();
        }
        return snap;
    }
    static void Apply() {
        foreach(var path in job.prefabs) {
            bool changed=false;
            var keys=Objects(Load(path)).Select(value=>{string g;long id;if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value,out g,out id)||id==0)throw new Exception("Missing persistent owner before native binding");return new Owner{guid=g,localId=id};}).ToArray();
            foreach(var key in keys) {
                var value=ResolveOwner(path,key.guid,key.localId);bool edit=false;
                using(var so=new SerializedObject(value)) {
                    so.UpdateIfRequiredOrScript();var p=so.GetIterator();bool enterChildren=true;
                    while(p.Next(enterChildren)) {
                        enterChildren=p.propertyType!=SerializedPropertyType.ObjectReference;
                        if(p.propertyType!=SerializedPropertyType.ObjectReference||!(p.objectReferenceValue is MonoScript))continue;
                        var script=(MonoScript)p.objectReferenceValue;string guid;long local;
                        if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(script,out guid,out local))throw new Exception("MonoScript reference identity unavailable");
                        MonoScript replacement;if(!replacements.TryGetValue(guid,out replacement))continue;
                        var b=job.bindings.Single(x=>x.sourceGuid==guid);
                        if(local!=b.sourceLocalId)throw new Exception("Source MonoScript reference localID differs");
                        p.objectReferenceValue=replacement;report.referencesMapped++;report.mappedSourceGuids.Add(guid);edit=true;
                    }
                    if(edit&&!so.ApplyModifiedPropertiesWithoutUndo())throw new Exception("Native serialized binding was not applied");
                }
                if(edit) { EditorUtility.SetDirty(ResolveOwner(path,key.guid,key.localId));changed=true; }
            }
            if(changed)PrefabUtility.SavePrefabAsset(Load(path));
        }
        AssetDatabase.SaveAssets();
        if(!report.mappedSourceGuids.Distinct(StringComparer.Ordinal).OrderBy(x=>x,StringComparer.Ordinal).SequenceEqual(job.bindings.Select(b=>b.sourceGuid).OrderBy(x=>x,StringComparer.Ordinal)))throw new Exception("At least one declared binding had no native serialized reference");
    }
    public static void Run() {
        int exit=1;bool writableJob=false;
        try {
            var encoded=Environment.GetEnvironmentVariable("BEAVER_INTAKE_BINDINGS_JOB_BASE64");
            if(String.IsNullOrEmpty(encoded)||encoded.Length>65536)throw new Exception("Explicit preparation job required");
            var path=new System.Text.UTF8Encoding(false,true).GetString(Convert.FromBase64String(encoded));job=JsonUtility.FromJson<Job>(File.ReadAllText(path));
            if(Application.unityVersion!="6000.6.2f1"||job.bridgeAssembly!="Beaver.IntakeBindings"||job.bridgeRoot!="Assets/BeaverIntakeBindings"||Path.GetFullPath(job.projectRoot)!=Path.GetFullPath(Directory.GetParent(Application.dataPath).FullName)||job.bindings==null||job.bindings.Length==0||job.bindings.Length>16||job.prefabs==null||job.prefabs.Length==0||job.prefabs.Length>256)throw new Exception("Wrong preparation project/version/bounds");
            if(job.mode!="apply"&&job.mode!="verify"||Path.GetFullPath(job.stage)!=Directory.GetParent(Path.GetFullPath(job.projectRoot)).FullName||!Directory.Exists(job.stage)||(File.GetAttributes(job.stage)&FileAttributes.ReparsePoint)!=0)throw new Exception("Wrong isolated preparation stage/mode");
            foreach(var name in new[]{"binding-before.json","apply-report.json","verify-report.json"}) {
                var file=Path.Combine(job.stage,name);
                if(File.Exists(file)&&(File.GetAttributes(file)&FileAttributes.ReparsePoint)!=0)throw new Exception("Preparation evidence path is a link");
            }
            writableJob=true;
            report=new Report{planSha256=job.planSha256,mode=job.mode,status="running"};Scripts();
            var checkpoint=Path.Combine(job.stage,"binding-before.json");Snapshot before;
            if(job.mode=="apply") { before=Capture(false);File.WriteAllText(checkpoint,JsonUtility.ToJson(before));Apply(); }
            else if(job.mode=="verify")before=JsonUtility.FromJson<Snapshot>(File.ReadAllText(checkpoint));
            else throw new Exception("Unknown preparation mode");
            if(before.planSha256!=job.planSha256)throw new Exception("Foreign preparation checkpoint");
            report.snapshot=Capture(job.mode=="verify");
            if(JsonUtility.ToJson(before)!=JsonUtility.ToJson(report.snapshot))throw new Exception("Native fields/references/object IDs changed beyond the declared script bindings");
            if(job.mode=="apply"&&report.referencesMapped==0)throw new Exception("No declared references were rebound");
            report.status="verified";exit=0;
        }catch(Exception e){if(report==null)report=new Report();report.status="failed";report.error=e.ToString();}
        finally {if(writableJob)File.WriteAllText(Path.Combine(job.stage,job.mode+"-report.json"),JsonUtility.ToJson(report,true));EditorApplication.Exit(exit);}
    }
}
#endif
