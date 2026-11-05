// Optional Editor entry points. Original business code is never executed.
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;

public static partial class MonkeyImporter
{
    [Serializable] public class StaticCodeRequest {
        public string schemaVersion, stageId, planPath, planSha256, bindingsPath, bindingsSha256;
        public StaticCodeMapping[] mappings;
        public StaticCodePrefab[] prefabs;
        public StaticCodeScript[] scripts;
    }
    [Serializable] public class StaticCodeScript { public string target,sha256,identity; }
    [Serializable] public class StaticCodeCatalog { public StaticCodeMapping[] mappings; public StaticCodeScript[] scripts; }
    [Serializable] public class StaticCodeMapping {
        public string sourceComponent, sourceNode, sourceAsset, codeRegion;
        public UnityStaticFields.Spec spec;
    }
    [Serializable] public class StaticCodePrefab {
        public string sourceId, path, guid, sha256;
    }
    [Serializable] public class StaticCodeObservation {
        public string sourceComponent, sourceNode, sourceAsset, codeRegion, prefabPath;
        public string nodeGuid, componentGuid, fullType, assembly, scriptGuid, error, ownerProofKind, ownerOriginalSourceId;
        public long nodeLocalId, componentLocalId;
        public bool ownerVerified, persistent, identityStable;
        public UnityStaticFields.Readback readback;
        public StaticCodeReference[] references;
    }
    [Serializable] public class StaticCodeReference {
        public string field,fieldPath,sourceId,guid,nativeType,targetNodeGuid,text;
        public long localFileId,targetNodeLocalId;
        public bool persistent;
    }
    [Serializable] public class StaticCodeControl { public string name, sourceComponent; public bool rejected; }
    [Serializable] public class StaticCodeReceipt {
        public string schemaVersion="monkey-static-code-native/2", stageId, phase, unityVersion, requestSha256;
        public int processId; public long processStartUtcTicks, observedUtcTicks; public string priorApplySha256;
        public StaticCodeObservation[] observations;
        public StaticCodeControl[] controls;
        public StaticCodePrefab[] prefabs;
        public string[] errors;
        public bool sourceBehaviorExecuted=false;
    }
    const string StaticCodeRequestPath="Analysis/StaticCodeBindings/request.json";
    static Dictionary<string,UnityStaticFields.Spec> codePriorBindings;
    static string CodeSha(string path) {
        using(var hash=SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(File.ReadAllBytes(path))).Replace("-","").ToLowerInvariant();
    }
    static void CodeRequire(bool valid,string reason) { if(!valid) throw new InvalidOperationException("STATIC_CODE_"+reason); }
    static StaticCodeRequest CodeRequest(out Plan plan) {
        var request=JsonUtility.FromJson<StaticCodeRequest>(File.ReadAllText(StaticCodeRequestPath));
        CodeRequire(request.schemaVersion=="monkey-static-code-bindings-request/1","SCHEMA");
        CodeRequire(CodeSha(request.planPath)==request.planSha256&&CodeSha(request.bindingsPath)==request.bindingsSha256,"INPUT_PIN");
        var catalog=JsonUtility.FromJson<StaticCodeCatalog>(File.ReadAllText(request.bindingsPath));
        plan=JsonUtility.FromJson<Plan>(File.ReadAllText(request.planPath));
        codePriorBindings=new Dictionary<string,UnityStaticFields.Spec>();
        CodeRequire(request.mappings.Select(x=>x.sourceComponent).Distinct().Count()==request.mappings.Length,"DUPLICATE_MAPPING");
        foreach(var row in request.mappings) {
            var original=catalog.mappings.Single(x=>x.sourceComponent==row.sourceComponent);
            CodeRequire(JsonUtility.ToJson(original)==JsonUtility.ToJson(row),"MAPPING_PIN");
            var script=catalog.scripts.Single(x=>x.identity==row.spec.scriptGuid);
            CodeRequire(CodeSha(script.target)==script.sha256&&AssetDatabase.AssetPathToGUID(script.target)==script.identity,"SCRIPT_PIN");
            var c=plan.components.Single(x=>x.sourceId==row.sourceComponent);
            CodeRequire(c.node==row.sourceNode&&row.spec.sourceId==c.sourceId&&row.spec.node==c.node,"SOURCE_NODE");
            CodeRequire(c.type==row.spec.sourceType&&c.node.Split('#')[0]==row.sourceAsset,"SOURCE_TYPE");
            CodeRequire(c.staticFieldBinding!=null&&!String.IsNullOrEmpty(c.staticFieldBinding.typeName),"PRIOR_OWNER_UNPROVEN");
            codePriorBindings.Add(c.sourceId,c.staticFieldBinding);
            c.staticFieldBinding=row.spec;
        }
        return request;
    }
    static bool CodeOwner(StaticCodeMapping row,Dictionary<string,GameObject> nodes,out string kind,out string originalId) {
        kind=null;originalId=null;
        if(!nodes.ContainsKey(row.sourceNode)||!codePriorBindings.ContainsKey(row.sourceComponent))return false;
        var prior=codePriorBindings[row.sourceComponent];
        var found=nodes[row.sourceNode].GetComponents<MonoBehaviour>().Where(x=>x!=null&&x.GetType().FullName==prior.typeName).Where(x=> {
            var field=x.GetType().GetField("__monkeySourceId");if(field==null)return false;
            var identity=field.GetValue(x) as string;
            return identity==row.sourceComponent||(!String.IsNullOrEmpty(prior.sourceTemplateId)&&identity==prior.sourceTemplateId&&PrefabUtility.GetCorrespondingObjectFromSource(x)!=null);
        }).ToArray();
        if(found.Length!=1)return false;
        originalId=found[0].GetType().GetField("__monkeySourceId").GetValue(found[0]) as string;
        kind=originalId==row.sourceComponent?"exact-prior-source-carrier":"native-corresponding-template-carrier";
        return true;
    }
    static MonoBehaviour CodeComponent(StaticCodeMapping row,Dictionary<string,GameObject> nodes) {
        if(!nodes.ContainsKey(row.sourceNode)) return null;
        var found=nodes[row.sourceNode].GetComponents<MonoBehaviour>().Where(x=>x!=null&&x.GetType().FullName==row.spec.typeName)
            .Where(x=>(string)x.GetType().GetField("__monkeySourceId").GetValue(x)==row.sourceComponent).ToArray();
        CodeRequire(found.Length<=1,"DUPLICATE_INSTANCE");
        return found.SingleOrDefault();
    }
    static StaticCodeObservation CodeRead(Plan plan,StaticCodeMapping row,SourcePrefabSpec prefab,Dictionary<string,GameObject> nodes) {
        var result=new StaticCodeObservation{sourceComponent=row.sourceComponent,sourceNode=row.sourceNode,sourceAsset=row.sourceAsset,
            codeRegion=row.codeRegion,prefabPath=prefab.path,references=Array.Empty<StaticCodeReference>()};
        try {
            var component=CodeComponent(row,nodes);
            result.ownerVerified=component!=null&&component.gameObject==nodes[row.sourceNode]&&CodeOwner(row,nodes,out result.ownerProofKind,out result.ownerOriginalSourceId);
            result.readback=UnityStaticFields.Read(row.spec,component,id=>StaticReference(plan,nodes,id));
            if(component!=null) {
                result.fullType=component.GetType().FullName;result.assembly=component.GetType().Assembly.GetName().Name;
                result.scriptGuid=AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(MonoScript.FromMonoBehaviour(component)));
                AssetDatabase.TryGetGUIDAndLocalFileIdentifier(component,out result.componentGuid,out result.componentLocalId);
                AssetDatabase.TryGetGUIDAndLocalFileIdentifier(component.gameObject,out result.nodeGuid,out result.nodeLocalId);
                result.persistent=EditorUtility.IsPersistent(component)&&result.componentLocalId!=0&&result.nodeLocalId!=0;
                var refs=new List<StaticCodeReference>();
                var serialized=new SerializedObject(component);var iterator=serialized.GetIterator();
                while(iterator.Next(true)) if(iterator.propertyType==SerializedPropertyType.ObjectReference&&iterator.propertyPath.StartsWith("__sf_",StringComparison.Ordinal)) {
                    var value=iterator.objectReferenceValue;
                    string guid=null;long localId=0;
                    bool persistent=value!=null&&EditorUtility.IsPersistent(value)&&AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value,out guid,out localId);
                    var field=(row.spec.fields??Array.Empty<UnityStaticFields.FieldSpec>()).SingleOrDefault(f=>iterator.propertyPath==f.fieldName||iterator.propertyPath.StartsWith(f.fieldName+".",StringComparison.Ordinal));
                    string sourceId=field==null?null:field.refValue,sourceField=field==null?null:field.sourceFieldName;
                    var indexMatch=Regex.Match(iterator.propertyPath,@"\.Array\.data\[(\d+)\]");
                    if(field!=null&&indexMatch.Success) {
                        int index=Int32.Parse(indexMatch.Groups[1].Value);sourceField+="["+index+"]";
                        if(field.storageType=="UnityEngine.Object[]")sourceId=field.refValues[index];
                        else if(field.elementKind=="record") {
                            var leaf=field.recordValues[index].fields.Single(f=>iterator.propertyPath.EndsWith("."+f.fieldName,StringComparison.Ordinal));
                            sourceId=leaf.refValue;sourceField+="."+leaf.sourceFieldName;
                        }
                    }
                    var targetNode=value is Component?((Component)value).gameObject:value as GameObject;
                    string nodeGuid=null;long nodeId=0;if(targetNode!=null)AssetDatabase.TryGetGUIDAndLocalFileIdentifier(targetNode,out nodeGuid,out nodeId);
                    refs.Add(new StaticCodeReference{field=sourceField,fieldPath=iterator.propertyPath,sourceId=sourceId,guid=guid,localFileId=localId,persistent=persistent,
                        nativeType=value==null?null:value.GetType().FullName,targetNodeGuid=nodeGuid,targetNodeLocalId=nodeId,text=value is TMPro.TMP_Text?((TMPro.TMP_Text)value).text:null});
                }
                result.references=refs.ToArray();
            }
        } catch(Exception e) { result.error=e.GetType().Name+":"+e.Message; }
        return result;
    }
    static void CodeControls(Plan plan,StaticCodeMapping[] rows,Dictionary<string,GameObject> nodes,List<StaticCodeControl> controls) {
        if(rows.Length==0)return;
        var row=rows.FirstOrDefault(r=>(r.spec.fields??Array.Empty<UnityStaticFields.FieldSpec>()).Any(f=>f.storageType=="UnityEngine.Object"&&!f.nullExpected))??rows[0];
        var component=CodeComponent(row,nodes);if(component==null)return;
        Func<string,UnityEngine.Object> resolve=id=>StaticReference(plan,nodes,id);
        var wrong=nodes.Values.FirstOrDefault(n=>n!=component.gameObject);
        if(wrong!=null) {
            var copy=JsonUtility.FromJson<StaticCodeMapping>(JsonUtility.ToJson(row));
            copy.sourceNode=nodes.First(x=>x.Value==wrong).Key;
            controls.Add(new StaticCodeControl{name="wrong-node",sourceComponent=row.sourceComponent,rejected=CodeComponent(copy,nodes)==null});
            var different=JsonUtility.FromJson<UnityStaticFields.Spec>(JsonUtility.ToJson(row.spec));different.sourceId+="/negative-instance";
            var peer=UnityStaticFields.Create(different,wrong);
            try { controls.Add(new StaticCodeControl{name="same-type-other-instance",sourceComponent=row.sourceComponent,rejected=!UnityStaticFields.Read(row.spec,peer,resolve).nativeIdentityVerified}); }
            finally { UnityEngine.Object.DestroyImmediate(peer); }
        }
        var other=rows.Select(x=>CodeComponent(x,nodes)).FirstOrDefault(x=>x!=null&&x.GetType()!=component.GetType());
        if(other!=null) {
            var read=UnityStaticFields.Read(row.spec,other,resolve);
            controls.Add(new StaticCodeControl{name="wrong-type",sourceComponent=row.sourceComponent,rejected=!read.fieldsVerified&&!read.nativeIdentityVerified});
        }
        var reference=(row.spec.fields??Array.Empty<UnityStaticFields.FieldSpec>()).FirstOrDefault(f=>f.storageType=="UnityEngine.Object"&&!f.nullExpected&&resolve(f.refValue)!=null);
        if(reference!=null) {
            var field=component.GetType().GetField(reference.fieldName);var previous=field.GetValue(component);
            var marker="reference_readback_mismatch:"+reference.sourceFieldName;
            bool baselineValid=!UnityStaticFields.Read(row.spec,component,resolve).gaps.Contains(marker)&&previous!=null;
            try {
                field.SetValue(component,null);
                controls.Add(new StaticCodeControl{name="missing-reference",sourceComponent=row.sourceComponent,rejected=baselineValid&&UnityStaticFields.Read(row.spec,component,resolve).gaps.Contains(marker)});
                var mismatch=nodes.Values.FirstOrDefault(n=>!ReferenceEquals(n,previous));
                if(mismatch!=null) {
                    field.SetValue(component,mismatch);
                    controls.Add(new StaticCodeControl{name="wrong-reference",sourceComponent=row.sourceComponent,rejected=baselineValid&&UnityStaticFields.Read(row.spec,component,resolve).gaps.Contains(marker)});
                }
            } finally { field.SetValue(component,previous); }
        }
        var duplicate=UnityStaticFields.Create(row.spec,component.gameObject);
        bool rejected=false;
        try { CodeComponent(row,nodes); } catch(InvalidOperationException) { rejected=true; }
        finally { UnityEngine.Object.DestroyImmediate(duplicate); }
        controls.Add(new StaticCodeControl{name="duplicate-instance",sourceComponent=row.sourceComponent,rejected=rejected});
    }
    public static void StaticCodeApply() { RunStaticCode(false); }
    public static void StaticCodeCold() { RunStaticCode(true); }
    static void RunStaticCode(bool cold) {
        var errors=new List<string>();var results=new List<StaticCodeObservation>();var controls=new List<StaticCodeControl>();var saved=new List<StaticCodePrefab>();
        var process=System.Diagnostics.Process.GetCurrentProcess();
        long started=process.StartTime.ToUniversalTime().Ticks;
        string priorHash=null;
        StaticCodeRequest request=null;
        try {
            Plan plan;request=CodeRequest(out plan);
            var prior=cold?JsonUtility.FromJson<StaticCodeReceipt>(File.ReadAllText("Analysis/StaticCodeBindings/apply.json")):null;
            if(cold) {
                priorHash=CodeSha("Analysis/StaticCodeBindings/apply.json");
                CodeRequire(prior.requestSha256==CodeSha(StaticCodeRequestPath)&&prior.phase=="apply"&&prior.stageId==request.stageId&&prior.unityVersion==Application.unityVersion&&prior.schemaVersion=="monkey-static-code-native/2"&&prior.processId>0&&prior.observedUtcTicks>0&&started>prior.observedUtcTicks,"COLD_PROCESS_OR_PHASE_MISMATCH");
            }
            foreach(var target in request.prefabs) {
                try {
                    CodeRequire(AssetDatabase.AssetPathToGUID(target.path)==target.guid,"PREFAB_GUID");
                    var pin=cold?prior.prefabs.Single(x=>x.sourceId==target.sourceId).sha256:target.sha256;
                    CodeRequire(CodeSha(target.path)==pin,"PREFAB_BYTES");
                    var prefab=plan.sourcePrefabs.Single(x=>x.sourceId==target.sourceId&&x.path==target.path);
                    var selected=request.mappings.Where(x=>prefab.nodes.Contains(x.sourceNode)).ToArray();
                    if(!cold) {
                        var root=PrefabUtility.LoadPrefabContents(target.path);
                        try {
                            var nodes=SavedNodeMap(plan.nodes,root,prefab).ToDictionary(x=>x.Key,x=>x.Value.gameObject);
                            foreach(var row in selected) {
                                string ownerKind,originalId;CodeRequire(CodeOwner(row,nodes,out ownerKind,out originalId),"PRIOR_OWNER_NODE_MISMATCH:"+row.sourceComponent);
                                if(CodeComponent(row,nodes)==null)UnityStaticFields.Create(row.spec,nodes[row.sourceNode]);
                            }
                            foreach(var row in selected)UnityStaticFields.Assign(row.spec,CodeComponent(row,nodes),id=>StaticReference(plan,nodes,id));
                            // Controls use disposable loaded objects and are restored before save.
                            CodeControls(plan,selected,nodes,controls);
                            PrefabUtility.SaveAsPrefabAsset(root,target.path);
                        } finally { PrefabUtility.UnloadPrefabContents(root); }
                    }
                    AssetDatabase.ImportAsset(target.path,ImportAssetOptions.ForceUpdate);
                    var persistent=AssetDatabase.LoadAssetAtPath<GameObject>(target.path);
                    var persistentNodes=SavedNodeMap(plan.nodes,persistent,prefab).ToDictionary(x=>x.Key,x=>x.Value.gameObject);
                    foreach(var row in selected) {
                        var result=CodeRead(plan,row,prefab,persistentNodes);
                        if(cold) {
                            var old=prior.observations.Single(x=>x.sourceComponent==row.sourceComponent&&x.prefabPath==prefab.path);
                            result.identityStable=old.componentGuid==result.componentGuid&&old.componentLocalId==result.componentLocalId&&old.nodeGuid==result.nodeGuid&&old.nodeLocalId==result.nodeLocalId&&old.fullType==result.fullType&&old.assembly==result.assembly&&old.scriptGuid==result.scriptGuid;
                        }
                        results.Add(result);
                    }
                    saved.Add(new StaticCodePrefab{sourceId=target.sourceId,path=target.path,guid=target.guid,sha256=CodeSha(target.path)});
                } catch(Exception e) { errors.Add(target.sourceId+":"+e); }
            }
        } catch(Exception e) { errors.Add(e.ToString()); }
        var receipt=new StaticCodeReceipt{stageId=request==null?null:request.stageId,phase=cold?"cold":"apply",unityVersion=Application.unityVersion,
            processId=process.Id,processStartUtcTicks=started,observedUtcTicks=DateTime.UtcNow.Ticks,priorApplySha256=priorHash,
            requestSha256=File.Exists(StaticCodeRequestPath)?CodeSha(StaticCodeRequestPath):null,observations=results.ToArray(),controls=controls.ToArray(),prefabs=saved.ToArray(),errors=errors.ToArray()};
        Directory.CreateDirectory("Analysis/StaticCodeBindings");
        File.WriteAllText("Analysis/StaticCodeBindings/"+(cold?"cold":"apply")+".json",JsonUtility.ToJson(receipt,true));
        CodeRequire(errors.Count==0&&controls.All(x=>x.rejected),"RUN_FAILED");
    }
}
