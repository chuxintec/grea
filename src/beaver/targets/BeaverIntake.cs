#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using UnityEngine;
using UnityEditor;

// Read-only native gates for create-only intake. Asset writes use BeaverAdoption.
public static class BeaverIntake {
    [Serializable] public class RefValue { public string guid,type,assembly; public long localId; }
    [Serializable] public class Field { public string propertyPath,kind,text; public RefValue reference; }
    [Serializable] public class Owner { public long localId; public string type,assembly,name; public Field[] fields; }
    [Serializable] public class Check { public string asset; public Owner[] objects; }
    [Serializable] public class Script { public string target,targetGuid,targetType,targetAssembly,targetSha256,targetMetaSha256; public long targetLocalId; }
    [Serializable] public class Addition { public string target,guid,fileHash,metaHash; }
    [Serializable] public class Job { public string targetRoot,stage,mode,planSha256; public Addition[] additions; public Script[] externalScripts; public Check[] verifications; }
    [Serializable] public class Observed { public string path,guid,type,assembly,name; public long localId; }
    [Serializable] public class Report { public string status,mode,planSha256,error; public int fieldsChecked; public List<Observed> scripts=new List<Observed>(); public List<Observed> objects=new List<Observed>(); }
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
    static void Value(SerializedProperty p,Field f) {
        if(p==null)throw new Exception("Missing serialized property "+f.propertyPath);
        if(f.kind=="integer") {
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
            report=new Report{status="running",mode=job.mode,planSha256=job.planSha256};Scripts();
            if(job.mode!="preflight"&&job.mode!="verify"&&job.mode!="rollback-check")throw new Exception("Unknown intake gate");
            foreach(var a in job.additions) {
                if(job.mode=="preflight"||job.mode=="rollback-check") {
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
