#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using UnityEngine;
using UnityEditor;
using System.Reflection;

// Read-only native gates for create-only intake. Asset writes use BeaverAdoption.
public static class BeaverIntake {
    [Serializable] public class RefValue { public string guid,type,assembly; public long localId; }
    [Serializable] public class Field { public string propertyPath,kind,text; public RefValue reference; }
    [Serializable] public class Owner { public long localId; public string type,assembly,name; public Field[] fields; }
    [Serializable] public class Check { public string asset; public Owner[] objects; }
    [Serializable] public class Script { public string target,targetGuid,targetType,targetAssembly,targetSha256,targetMetaSha256; public long targetLocalId; }
    [Serializable] public class Addition { public string target,guid,fileHash,metaHash; }
    [Serializable] public class External { public string target,guid,sha256,metaSha256; public Owner[] objects; }
    [Serializable] public class PackageScript { public string target,guid,type,assembly,name,packageName,packageVersion,packageSource,packageJsonSha256,sha256,metaSha256,resolvedRoot; public long localId; }
    [Serializable] public class Member { public string name,type,assembly; }
    [Serializable] public class NewScript { public string target,guid,sha256,metaSha256,targetType,targetAssembly,baseType,baseAssembly; public long localId; public Member[] fields; }
    [Serializable] public class NewObserved { public Observed identity; public string baseType,baseAssembly; public Member[] fields; }
    [Serializable] public class Job { public string targetRoot,stage,mode,planSha256; public Addition[] additions; public Script[] externalScripts; public External[] externalAssets; public PackageScript[] packageScripts; public NewScript[] newScripts; public Check[] verifications; }
    [Serializable] public class Observed { public string path,guid,type,assembly,name; public long localId; }
    [Serializable] public class Reference { public string asset,propertyPath; public long ownerLocalId; public Observed value; }
    [Serializable] public class SkippedArray { public string propertyPath,elementType,scalarPropertyType; public int length; }
    [Serializable] public class Traversal { public string asset; public long ownerLocalId; public int visited; public List<SkippedArray> scalarArrays=new List<SkippedArray>(); }
    [Serializable] public class Report { public string status,mode,planSha256,error; public int fieldsChecked; public List<Observed> scripts=new List<Observed>(); public List<Observed> objects=new List<Observed>(); public List<Observed> externalObjects=new List<Observed>(); public List<Reference> externalReferences=new List<Reference>(); public List<Observed> packageScripts=new List<Observed>(); public List<Traversal> referenceTraversals=new List<Traversal>(); public List<NewObserved> newScripts=new List<NewObserved>(); }
    static Job job; static Report report; static string root;
    static string Full(string relative) {
        if(String.IsNullOrEmpty(relative)||!relative.StartsWith("Assets/",StringComparison.Ordinal)||relative.Contains("\\")||relative.Split('/').Any(p=>p==""||p=="."||p==".."))throw new Exception("Unsafe intake path");
        var p=Path.GetFullPath(Path.Combine(root,relative));if(!p.StartsWith(root+Path.DirectorySeparatorChar,StringComparison.Ordinal))throw new Exception("Intake path escaped");return p;
    }
    static string Hash(string p) { if(!File.Exists(p))return null;using(var f=File.OpenRead(p))using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(f)).Replace("-","").ToLowerInvariant(); }
    static Observed Identity(UnityEngine.Object value,string path) {
        string guid;long id;
        if(value==null||!EditorUtility.IsPersistent(value)||!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value,out guid,out id)||String.IsNullOrEmpty(guid)||id==0)throw new Exception("Persistent identity unavailable "+path);
        var t=value.GetType();return new Observed{path=path,guid=guid,localId=id,type=t.FullName,assembly=t.Assembly.GetName().Name,name=value.name};
    }
    static void Scripts() {
        foreach(var s in job.externalScripts) {
            if(Hash(Full(s.target))!=s.targetSha256||Hash(Full(s.target+".meta"))!=s.targetMetaSha256||AssetDatabase.GUIDToAssetPath(s.targetGuid)!=s.target)throw new Exception("Retained script drift "+s.target);
            var script=AssetDatabase.LoadAssetAtPath<MonoScript>(s.target);var t=script==null?null:script.GetClass();
            if(t==null||t.FullName!=s.targetType||t.Assembly.GetName().Name!=s.targetAssembly)throw new Exception("Retained script GetClass/domain mismatch "+s.target);
            var found=Identity(script,s.target);if(found.guid!=s.targetGuid||found.localId!=s.targetLocalId)throw new Exception("Retained script localID mismatch "+s.target);
            found.type=t.FullName;found.assembly=t.Assembly.GetName().Name;report.scripts.Add(found);
        }
    }
    // Unity arrays are homogeneous. Require both the engine's element type and
    // a childless scalar element; user structs, PPtrs and managed references do
    // not qualify even if their type name resembles a primitive alias.
    static bool ScalarArray(SerializedProperty p,Traversal traversal) {
        if(!p.isArray||p.propertyType!=SerializedPropertyType.Generic||p.arraySize==0)return false;
        string kind=p.arrayElementType;SerializedPropertyType expected;
        switch(kind) {
            case "bool":expected=SerializedPropertyType.Boolean;break;
            case "float":case "double":expected=SerializedPropertyType.Float;break;
            case "string":expected=SerializedPropertyType.String;break;
            case "char":expected=SerializedPropertyType.Character;break;
            case "SInt8":case "UInt8":case "SInt16":case "UInt16":case "SInt32":case "UInt32":case "SInt64":case "UInt64":
            case "byte":case "sbyte":case "short":case "ushort":case "int":case "uint":case "long":case "ulong":
            case "unsigned char":case "unsigned short":case "unsigned int":case "unsigned long long":case "long long":
                expected=SerializedPropertyType.Integer;break;
            default:return false;
        }
        using(var first=p.GetArrayElementAtIndex(0)) {
            if(first.hasChildren||first.isArray||!(first.propertyType==expected||kind=="char"&&first.propertyType==SerializedPropertyType.Integer))return false;
            traversal.scalarArrays.Add(new SkippedArray{propertyPath=p.propertyPath,elementType=kind,scalarPropertyType=first.propertyType.ToString(),length=p.arraySize});
        }
        return true;
    }
    static void NewScripts() {
        foreach(var s in job.newScripts??new NewScript[0]) {
            var types=AppDomain.CurrentDomain.GetAssemblies().Select(a=>a.GetType(s.targetType,false)).Where(t=>t!=null).ToArray();
            if(job.mode=="preflight"||job.mode=="rollback-check") {
                if(types.Length!=0)throw new Exception("New script type already exists "+s.targetType);
                continue;
            }
            if(Hash(Full(s.target))!=s.sha256||Hash(Full(s.target+".meta"))!=s.metaSha256||AssetDatabase.GUIDToAssetPath(s.guid)!=s.target)throw new Exception("New script source/GUID drift "+s.target);
            var script=AssetDatabase.LoadAssetAtPath<MonoScript>(s.target);var type=script==null?null:script.GetClass();var found=Identity(script,s.target);
            if(type==null||types.Length!=1||types[0]!=type||type.FullName!=s.targetType||type.Assembly.GetName().Name!=s.targetAssembly||type.BaseType==null||type.BaseType.FullName!=s.baseType||type.BaseType.Assembly.GetName().Name!=s.baseAssembly||found.guid!=s.guid||found.localId!=s.localId)throw new Exception("New script GetClass/domain/base/unique type mismatch "+s.target);
            foreach(var field in s.fields) {
                var member=type.GetField(field.name,BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic);
                if(member==null||member.FieldType.FullName!=field.type||member.FieldType.Assembly.GetName().Name!=field.assembly)throw new Exception("New script field mismatch "+s.target+":"+field.name);
            }
            found.type=type.FullName;found.assembly=type.Assembly.GetName().Name;report.newScripts.Add(new NewObserved{identity=found,baseType=type.BaseType.FullName,baseAssembly=type.BaseType.Assembly.GetName().Name,fields=s.fields});
        }
    }
    static void Dependencies() {
        foreach(var s in job.packageScripts??new PackageScript[0]) {
            var info=UnityEditor.PackageManager.PackageInfo.FindForAssetPath(s.target);
            if(info==null||info.name!=s.packageName||info.version!=s.packageVersion||info.source.ToString().ToLowerInvariant()!=s.packageSource||Path.GetFullPath(info.resolvedPath)!=s.resolvedRoot)throw new Exception("Package identity/source mismatch "+s.target);
            string relative=s.target.Substring(("Packages/"+s.packageName+"/").Length);string file=Path.Combine(info.resolvedPath,relative);
            if(Hash(Path.Combine(info.resolvedPath,"package.json"))!=s.packageJsonSha256||Hash(file)!=s.sha256||Hash(file+".meta")!=s.metaSha256||AssetDatabase.GUIDToAssetPath(s.guid)!=s.target)throw new Exception("Package source/meta drift "+s.target);
            var script=AssetDatabase.LoadAssetAtPath<MonoScript>(s.target);var type=script==null?null:script.GetClass();
            var observed=Identity(script,s.target);
            if(type==null||type.FullName!=s.type||type.Assembly.GetName().Name!=s.assembly||observed.guid!=s.guid||observed.localId!=s.localId||observed.name!=s.name)throw new Exception("Package GetClass/identity mismatch "+s.target);
            observed.type=type.FullName;observed.assembly=type.Assembly.GetName().Name;report.packageScripts.Add(observed);
        }
        foreach(var e in job.externalAssets??new External[0]) {
            if(Hash(Full(e.target))!=e.sha256||Hash(Full(e.target+".meta"))!=e.metaSha256||AssetDatabase.GUIDToAssetPath(e.guid)!=e.target)throw new Exception("Retained resource drift "+e.target);
            var values=AssetDatabase.LoadAllAssetsAtPath(e.target).Concat(new[]{AssetDatabase.LoadMainAssetAtPath(e.target)}).Where(v=>v!=null).Distinct().Select(v=>new{value=v,id=Identity(v,e.target)}).OrderBy(v=>v.id.localId).ToArray();
            if(values.Length!=e.objects.Length||values.Select(v=>v.id.localId).Distinct().Count()!=values.Length)throw new Exception("Retained resource exact object set mismatch "+e.target);
            foreach(var v in values) {
                var o=e.objects.SingleOrDefault(expected=>expected.localId==v.id.localId);
                if(o==null||v.id.guid!=e.guid||v.id.type!=o.type||v.id.assembly!=o.assembly||v.id.name!=o.name)throw new Exception("Retained resource object identity mismatch "+e.target);
                report.externalObjects.Add(v.id);var so=new SerializedObject(v.value);so.UpdateIfRequiredOrScript();
                foreach(var f in o.fields)Value(so.FindProperty(f.propertyPath),f);
                var iterator=so.GetIterator();var traversal=new Traversal{asset=e.target,ownerLocalId=o.localId};report.referenceTraversals.Add(traversal);bool enterChildren=true;
                while(iterator.Next(enterChildren)) {
                    if(++traversal.visited>250000)throw new Exception("Retained resource reference traversal budget");
                    enterChildren=!ScalarArray(iterator,traversal);
                    if(iterator.propertyType!=SerializedPropertyType.ObjectReference)continue;
                    var value=iterator.objectReferenceValue;
                    if(value==null&&iterator.objectReferenceEntityIdValue!=EntityId.None)throw new Exception("Unresolved retained resource reference "+iterator.propertyPath);
                    report.externalReferences.Add(new Reference{asset=e.target,ownerLocalId=o.localId,propertyPath=iterator.propertyPath,value=value==null?null:Identity(value,AssetDatabase.GetAssetPath(value))});
                    if(report.externalReferences.Count>250000)throw new Exception("Retained resource reference budget");
                }
            }
        }
    }
    static void Value(SerializedProperty p,Field f) {
        if(p==null)throw new Exception("Missing serialized property "+f.propertyPath);
        if(f.kind=="character") {
            long value=Int64.Parse(f.text,CultureInfo.InvariantCulture);
            if(value<0||value>65535||p.propertyType!=SerializedPropertyType.Character||p.intValue!=value)throw new Exception("UTF16 Character field/type/range mismatch "+f.propertyPath);
        } else if(f.kind=="integer") {
            if(p.propertyType!=SerializedPropertyType.Integer&&p.propertyType!=SerializedPropertyType.Enum&&p.propertyType!=SerializedPropertyType.LayerMask&&p.propertyType!=SerializedPropertyType.ArraySize)throw new Exception("Integer property type mismatch");
            long value=(p.propertyType==SerializedPropertyType.Enum||p.propertyType==SerializedPropertyType.ArraySize)?p.intValue:p.longValue;
            if(value!=Int64.Parse(f.text,CultureInfo.InvariantCulture))throw new Exception("Integer field mismatch "+f.propertyPath);
        } else if(f.kind=="float") {
            if(p.propertyType!=SerializedPropertyType.Float)throw new Exception("Float property type mismatch");
            double actual=p.doubleValue,expected=Double.Parse(f.text,CultureInfo.InvariantCulture);
            if(Double.IsNaN(actual)||Double.IsInfinity(actual)||Math.Abs(actual-expected)>0.00001)throw new Exception("Float field mismatch "+f.propertyPath);
        } else if(f.kind=="boolean") {
            if(p.propertyType!=SerializedPropertyType.Boolean||p.boolValue!=(f.text=="true"))throw new Exception("Boolean field mismatch "+f.propertyPath);
        } else if(f.kind=="string") {
            if(p.propertyType!=SerializedPropertyType.String||p.stringValue!=f.text)throw new Exception("String field mismatch "+f.propertyPath);
        } else if(f.kind=="object") {
            if(p.propertyType!=SerializedPropertyType.ObjectReference)throw new Exception("Reference property type mismatch");
            var v=p.objectReferenceValue;var e=f.reference;
            if(e.guid=="") { if(v!=null)throw new Exception("Expected null reference "+f.propertyPath); }
            else { var found=Identity(v,f.propertyPath);if(found.guid!=e.guid||found.localId!=e.localId||found.type!=e.type||found.assembly!=e.assembly)throw new Exception("Reference identity/type mismatch "+f.propertyPath); }
        } else throw new Exception("Unknown field kind");
        report.fieldsChecked++;
    }
    static void Prefab(Check check,Addition addition) {
        var prefab=AssetDatabase.LoadAssetAtPath<GameObject>(check.asset);if(prefab==null)throw new Exception("Prefab missing "+check.asset);
        var owners=new Dictionary<long,UnityEngine.Object>();
        foreach(var transform in prefab.GetComponentsInChildren<Transform>(true)) {
            foreach(var value in new UnityEngine.Object[]{transform.gameObject}.Concat(transform.GetComponents<Component>().Cast<UnityEngine.Object>())) {
                if(value==null)throw new Exception("Missing prefab component "+check.asset);
                var observed=Identity(value,check.asset);if(observed.guid!=addition.guid||owners.ContainsKey(observed.localId))throw new Exception("Prefab identity duplicate or foreign GUID");owners.Add(observed.localId,value);
            }
        }
        if(owners.Count!=check.objects.Length)throw new Exception("Exact prefab owner coverage differs "+check.asset);
        foreach(var expected in check.objects) {
            UnityEngine.Object value;if(!owners.TryGetValue(expected.localId,out value))throw new Exception("Expected prefab localID missing");
            var observed=Identity(value,check.asset);report.objects.Add(observed);
            if(observed.type!=expected.type||observed.assembly!=expected.assembly||observed.name!=expected.name)throw new Exception("Prefab type/domain/name mismatch "+expected.localId+"; observed "+JsonUtility.ToJson(observed));
            var serialized=new SerializedObject(value);serialized.UpdateIfRequiredOrScript();
            foreach(var field in expected.fields)Value(serialized.FindProperty(field.propertyPath),field);
        }
    }
    public static void Run() {
        int exit=1;
        try {
            string encoded=Environment.GetEnvironmentVariable("BEAVER_INTAKE_JOB_BASE64");if(String.IsNullOrEmpty(encoded)||encoded.Length>65536)throw new Exception("Explicit intake job required");
            var path=new System.Text.UTF8Encoding(false,true).GetString(Convert.FromBase64String(encoded));job=JsonUtility.FromJson<Job>(File.ReadAllText(path));
            root=Path.GetFullPath(job.targetRoot).TrimEnd(Path.DirectorySeparatorChar);
            if(Application.unityVersion!="6000.6.2f1"||root!=Path.GetFullPath(Directory.GetParent(Application.dataPath).FullName).TrimEnd(Path.DirectorySeparatorChar))throw new Exception("Wrong Editor/project");
            report=new Report{status="running",mode=job.mode,planSha256=job.planSha256};Scripts();Dependencies();NewScripts();
            if(job.mode!="preflight"&&job.mode!="verify"&&job.mode!="rollback-check"&&job.mode!="code-check")throw new Exception("Unknown intake gate");
            foreach(var a in job.additions) {
                if(job.mode=="preflight"||job.mode=="rollback-check"||job.mode=="code-check"&&!(job.newScripts??new NewScript[0]).Any(s=>s.target==a.target)) {
                    if(File.Exists(Full(a.target))||File.Exists(Full(a.target+".meta"))||AssetDatabase.GUIDToAssetPath(a.guid)!="")throw new Exception("New asset identity/destination is occupied "+a.target);
                } else {
                    if(Hash(Full(a.target))!=a.fileHash||Hash(Full(a.target+".meta"))!=a.metaHash||AssetDatabase.AssetPathToGUID(a.target)!=a.guid)throw new Exception("Imported payload changed "+a.target);
                    var values=AssetDatabase.LoadAllAssetsAtPath(a.target).Concat(new[]{AssetDatabase.LoadMainAssetAtPath(a.target)}).Where(v=>v!=null).Distinct().ToArray();
                    if(values.Length==0)throw new Exception("New asset has no native object "+a.target);
                    foreach(var v in values) { var observed=Identity(v,a.target);if(observed.guid!=a.guid)throw new Exception("Foreign imported subresource GUID");if(!a.target.EndsWith(".prefab",StringComparison.OrdinalIgnoreCase))report.objects.Add(observed); }
                }
            }
            if(job.mode=="verify")foreach(var c in job.verifications)Prefab(c,job.additions.Single(a=>a.target==c.asset));
            report.status="verified";exit=0;
        } catch(Exception e) { if(report==null)report=new Report();report.status="failed";report.error=e.ToString(); }
        finally {
            if(job!=null&&report!=null)File.WriteAllText(Path.Combine(job.stage,"native-intake-"+job.mode+".json"),JsonUtility.ToJson(report,true));
            EditorApplication.Exit(exit);
        }
    }
}
#endif
