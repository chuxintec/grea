using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static partial class MonkeyImporter
{
    [Serializable] public class StaticReferenceIdentity { public string field,fieldPath,sourceId,guid,recordField; public int recordIndex; public long localFileId; public bool persistent; }
    [Serializable] public class StaticFieldResult { public UnityStaticFields.Readback binding; public string assetGuid; public long localFileId; public StaticReferenceIdentity[] references; }
    static MonoBehaviour StaticComponent(ComponentSpec c, GameObject node) {
        var candidates=node.GetComponents<MonoBehaviour>().Where(x=>x!=null&&x.GetType().FullName==c.staticFieldBinding.typeName).ToArray();
        Func<MonoBehaviour,string> identity=x=>(string)x.GetType().GetField("__monkeySourceId").GetValue(x);
        var exact=candidates.SingleOrDefault(x=>identity(x)==c.sourceId);
        if(exact!=null||string.IsNullOrEmpty(c.staticFieldBinding.sourceTemplateId))return exact;
        return candidates.SingleOrDefault(x=>identity(x)==c.staticFieldBinding.sourceTemplateId);
    }
    static void CreateStaticFields(Plan plan, Dictionary<string,GameObject> nodes) {
        foreach(var c in plan.components.Where(x=>x.staticFieldBinding!=null&&!string.IsNullOrEmpty(x.staticFieldBinding.typeName)&&nodes.ContainsKey(x.node)))
            if(StaticComponent(c,nodes[c.node])==null)UnityStaticFields.Create(c.staticFieldBinding,nodes[c.node]);
    }
    static UnityEngine.Object StaticReference(Plan plan, Dictionary<string,GameObject> nodes,string id) {
        if(nodes.TryGetValue(id,out var node))return node;
        var c=plan.components.FirstOrDefault(x=>x.sourceId==id);
        if(c!=null&&nodes.TryGetValue(c.node,out node)) {
            if(c.staticFieldBinding!=null&&!string.IsNullOrEmpty(c.staticFieldBinding.typeName))return StaticComponent(c,node);
            if(c.type=="cc.Graphics"&&plan.staticControlBindings!=null)return node.GetComponent<NativeStaticGraphics>();
            if(c.type=="cc.EditBox"&&plan.staticControlBindings!=null)return node.GetComponent<NativeStaticEditBox>();
            if(c.type=="cc.Animation"&&plan.staticCompletionEnabled)return node.GetComponent<NativeStaticAnimationBinding>();
            if(c.type=="cc.ProgressBar"&&!c.convertible&&c.staticProgressBinding!=null&&c.staticProgressBinding.policy=="native-static-progress-v1")return ResolveStaticProgress(plan,nodes,id);
            if(!c.convertible) {
                // Optional native Spine components are created by their pinned
                // stage even when the generic component adapter is unavailable.
                UnityEngine.Object optional=null;ResolveStaticSpineReference(id,nodes,ref optional);return optional;
            }
            if(c.behaviorBinding!=null&&!string.IsNullOrEmpty(c.behaviorBinding.typeName))return node.GetComponents<MonoBehaviour>().SingleOrDefault(x=>x!=null&&x.GetType().FullName==c.behaviorBinding.typeName);
            switch(c.type) {
                case "cc.Sprite":return node.GetComponent<UnityEngine.UI.Image>();
                case "cc.Label":case "cc.RichText":case "cc.LabelOutline":return node.GetComponent<TMPro.TextMeshProUGUI>();
                case "cc.Button":return node.GetComponent<UnityEngine.UI.Button>();
                case "cc.Toggle":return node.GetComponent<UnityEngine.UI.Toggle>();
                case "cc.ToggleContainer":return node.GetComponent<UnityEngine.UI.ToggleGroup>();
                case "cc.Widget":return node.GetComponent<NativeRectConstraints>();
                case "cc.Layout":return node.GetComponent<UnityEngine.UI.LayoutGroup>();
                case "cc.ScrollView":return node.GetComponent<UnityEngine.UI.ScrollRect>();
                case "cc.Mask":return node.GetComponent<UnityEngine.UI.RectMask2D>();
                case "cc.ProgressBar":return node.GetComponent<UnityEngine.UI.Slider>();
                case "cc.BlockInputEvents":return node.GetComponent<NativeInputBlocker>();
            }
            UnityEngine.Object spineComponent=null;ResolveStaticSpineReference(id,nodes,ref spineComponent);if(spineComponent==null)ResolveOptionalSpriteOutline(plan,id,nodes,ref spineComponent);return spineComponent;
        }
        UnityEngine.Object spineAsset=null;ResolveStaticSpineReference(id,nodes,ref spineAsset);if(spineAsset==null)ResolveOptionalSpriteOutline(plan,id,nodes,ref spineAsset);if(spineAsset==null)ResolveOptionalStaticTimeMaterial(plan,id,ref spineAsset);if(spineAsset!=null)return spineAsset;
        if(plan.staticRetainedAssets!=null&&plan.staticRetainedAssets.assets.Any(x=>x.sourceId==id))return ResolveStaticRetainedAsset(plan,id);
        var animation=(plan.staticAnimationAssetReferences??Array.Empty<StaticAnimationAssetRef>()).SingleOrDefault(x=>x.sourceId==id);
        if(animation!=null)return AssetDatabase.LoadAssetAtPath<AnimationClip>(animation.path);
        var bitmap=plan.bitmapFonts.FirstOrDefault(x=>x.id==id);
        if(bitmap!=null)return AssetDatabase.LoadAssetAtPath<TMPro.TMP_FontAsset>(bitmap.fontPath);
        var texture=plan.textures.FirstOrDefault(x=>x.id==id);
        if(texture!=null)return AssetDatabase.LoadAssetAtPath<Sprite>(texture.path);
        if(plan.materialBinding!=null&&plan.materialBinding.materialSourceId==id)
            return AssetDatabase.LoadAssetAtPath<Material>(plan.materialBinding.materialPath);
        var asset=plan.assets.FirstOrDefault(x=>x.id==id);
        if(asset!=null)return AssetDatabase.LoadMainAssetAtPath(asset.path);
        var prefab=(plan.sourcePrefabs??Array.Empty<SourcePrefabSpec>()).FirstOrDefault(x=>x.sourceId==id);
        return prefab==null?null:AssetDatabase.LoadAssetAtPath<GameObject>(prefab.path);
    }
    static void AssignStaticFields(Plan plan, Dictionary<string,GameObject> nodes) {
        foreach(var c in plan.components.Where(x=>x.staticFieldBinding!=null&&!string.IsNullOrEmpty(x.staticFieldBinding.typeName)&&nodes.ContainsKey(x.node))) {
            var component=StaticComponent(c,nodes[c.node]);
            if(component!=null)UnityStaticFields.Assign(c.staticFieldBinding,component,id=>StaticReference(plan,nodes,id));
        }
    }
    static UnityStaticToggle.Readback ReadStaticToggles(Plan plan,Dictionary<string,GameObject> nodes) {
        if(plan.toggleBinding==null)return null;
        var spec=new UnityStaticToggle.Spec{bindings=plan.toggleBinding.bindings.Where(x=>nodes.ContainsKey(x.nodeSourceId)).ToArray()};
        var result=UnityStaticToggle.Read(spec,id=>nodes.TryGetValue(id,out var n)?n:null,id=>StaticReference(plan,nodes,id));
        if(result.fields.Any(x=>!x.verified))throw new InvalidOperationException("STATIC_TOGGLE_SAVED_READBACK_FAILED: "+JsonUtility.ToJson(result));
        return result;
    }
    static StaticFieldResult[] ReadStaticFields(Plan plan, Dictionary<string,GameObject> nodes) {
        return plan.components.Where(x=>x.staticFieldBinding!=null&&!string.IsNullOrEmpty(x.staticFieldBinding.typeName)&&nodes.ContainsKey(x.node)).Select(c=> {
            var component=StaticComponent(c,nodes[c.node]);
            var read=UnityStaticFields.Read(c.staticFieldBinding,component,id=>StaticReference(plan,nodes,id));
            string guid=null;long localId=0;
            if(component!=null)AssetDatabase.TryGetGUIDAndLocalFileIdentifier(component,out guid,out localId);
            var references=new List<StaticReferenceIdentity>();
            if(component!=null)foreach(var f in c.staticFieldBinding.fields??Array.Empty<UnityStaticFields.FieldSpec>()) {
                var field=component.GetType().GetField(f.fieldName);
                if(field==null)continue;
                if(f.storageType=="UnityEngine.Object"&&!f.nullExpected) {
                    AddStaticReference(references,f.sourceFieldName,f.sourceFieldName,f.refValue,field.GetValue(component) as UnityEngine.Object,-1,null);
                } else if(f.storageType=="UnityEngine.Object[]") {
                    var values=field.GetValue(component) as UnityEngine.Object[];var ids=f.refValues??Array.Empty<string>();
                    for(int i=0;i<ids.Length;i++)AddStaticReference(references,f.sourceFieldName,f.sourceFieldName+"["+i+"]",ids[i],values!=null&&i<values.Length?values[i]:null,-1,null);
                } else if(f.elementKind=="record"&&f.recordTypeName!=null) {
                    var values=field.GetValue(component) as Array;var rows=f.recordValues??Array.Empty<UnityStaticFields.RecordValueSpec>();
                    for(int i=0;i<rows.Length;i++) {
                        var instance=values!=null&&i<values.Length?values.GetValue(i):null;
                        foreach(var leaf in rows[i].fields??Array.Empty<UnityStaticFields.RecordFieldValueSpec>()) {
                            if(leaf.storageType!="UnityEngine.Object"||leaf.nullExpected)continue;
                            var leafInfo=instance==null?null:instance.GetType().GetField(leaf.fieldName);
                            AddStaticReference(references,f.sourceFieldName,f.sourceFieldName+"["+i+"]."+leaf.sourceFieldName,leaf.refValue,
                                leafInfo==null?null:leafInfo.GetValue(instance) as UnityEngine.Object,i,leaf.sourceFieldName);
                        }
                    }
                }
            }
            return new StaticFieldResult{binding=read,assetGuid=guid,localFileId=localId,references=references.ToArray()};
        }).ToArray();
    }
    static void AddStaticReference(List<StaticReferenceIdentity> references,string field,string fieldPath,string sourceId,
        UnityEngine.Object value,int recordIndex,string recordField) {
        string guid=null;long localId=0;
        bool persistent=value!=null&&EditorUtility.IsPersistent(value)&&AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value,out guid,out localId);
        references.Add(new StaticReferenceIdentity{field=field,fieldPath=fieldPath,sourceId=sourceId,recordIndex=recordIndex,
            recordField=recordField,guid=guid,localFileId=localId,persistent=persistent});
    }
}
