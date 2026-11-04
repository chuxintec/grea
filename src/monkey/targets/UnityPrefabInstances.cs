// Development-only native Prefab construction. No source identities enter Player components.
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static partial class MonkeyImporter
{
    [Serializable] public class PrefabObjectPair { public string instanceObject,templateObject; }
    [Serializable] public class PrefabMountedChildren { public string parent; public string[] roots,nodes; }
    [Serializable] public class PrefabMountedComponent { public string node,component,sourceType,nativeType; }
    [Serializable] public class PrefabInstanceSpec {
        public string owner,root,template,sourceInstanceFileId; public bool outermost; public PrefabObjectPair[] nodes;
        public PrefabMountedChildren[] mountedChildren; public PrefabMountedComponent[] mountedComponents;
    }
    [Serializable] public class PrefabInstanceResult {
        public string root,templateSourceId,templatePath,templateGuid;
        public bool nativeInstance,correspondingSourceVerified,nodeCorrespondenceVerified,templateUnchanged;
        public int nodeCount,propertyModificationCount; public long templateRootFileId;
        public bool mountedChildrenVerified,mountedComponentsVerified; public int mountedRootCount,mountedNodeCount,mountedComponentCount;
    }
    static Dictionary<string,string> prefabTemplateHashes;
    static readonly Dictionary<string,PrefabInstanceResult> savedMountProofs=new Dictionary<string,PrefabInstanceResult>();
    static readonly Dictionary<string,string> savedMountProofHashes=new Dictionary<string,string>();
    static readonly Dictionary<string,string> savedMountProofAssets=new Dictionary<string,string>();
    static readonly HashSet<string> PrefabInternalProperties=new HashSet<string> {
        "m_ObjectHideFlags","m_CorrespondingSourceObject","m_PrefabInstance","m_PrefabAsset","m_GameObject","m_Script"
    };
    static void CopyNativeProperties(Component source,Component destination) {
        if(source.GetType()!=destination.GetType() || source is Transform)throw new InvalidOperationException("Invalid native property transfer");
        var from=new SerializedObject(source);var to=new SerializedObject(destination);var property=from.GetIterator();bool enter=true;
        while(property.Next(enter)) {
            enter=false;
            if(PrefabInternalProperties.Contains(property.propertyPath))continue;
            bool derived=false;SkipOptionalSpineDerivedProperty(source,property.propertyPath,ref derived);if(derived)continue;
            if(to.FindProperty(property.propertyPath)==null)throw new InvalidOperationException("Native serialized property unavailable: "+property.propertyPath);
            to.CopyFromSerializedPropertyIfDifferent(property);
        }
        to.ApplyModifiedPropertiesWithoutUndo();
    }
    static void RemapNativeReferences(Component component,Dictionary<UnityEngine.Object,UnityEngine.Object> replacements) {
        // Transform parent/children are exclusively maintained by SetParent and
        // DestroyImmediate. Rewriting m_Children would duplicate live child links.
        if(component is Transform)return;
        var serialized=new SerializedObject(component);var property=serialized.GetIterator();bool changed=false;
        while(property.Next(true)) {
            if(PrefabInternalProperties.Contains(property.propertyPath))continue;
            if(property.propertyType!=SerializedPropertyType.ObjectReference || property.objectReferenceValue==null)continue;
            if(replacements.TryGetValue(property.objectReferenceValue,out var replacement)) {
                property.objectReferenceValue=replacement;changed=true;
            }
        }
        if(changed)serialized.ApplyModifiedPropertiesWithoutUndo();
        if(PrefabUtility.IsPartOfPrefabInstance(component))PrefabUtility.RecordPrefabInstancePropertyModifications(component);
    }
    static void PrepareNativeInstances(Plan plan,string owner,Dictionary<string,GameObject> nodes,Dictionary<string,NodeSpec> sourceNodes) {
        var specs=(plan.sourcePrefabs??new SourcePrefabSpec[0]).ToDictionary(s=>s.sourceId);
        foreach(var instance in (plan.prefabInstances??new PrefabInstanceSpec[0]).Where(s=>s.owner==owner&&s.outermost)) {
            if(!specs.TryGetValue(instance.template,out var template) || !prefabTemplateHashes.ContainsKey(instance.template))
                throw new InvalidOperationException("Template must be saved before instance: "+instance.template);
            if(Hash(template.path)!=prefabTemplateHashes[instance.template])throw new InvalidOperationException("Shared template changed before instantiate");
            var asset=AssetDatabase.LoadAssetAtPath<GameObject>(template.path);
            var previousRoot=nodes[instance.root];var previousParent=previousRoot.transform.parent;int sibling=previousRoot.transform.GetSiblingIndex();
            var root=(GameObject)PrefabUtility.InstantiatePrefab(asset,previousRoot.scene);
            root.transform.SetParent(previousParent,false);root.transform.SetSiblingIndex(sibling);
            try {
                var templateNodes=SavedNodeMap(plan.nodes,root,template,sourceNodes);
                if(instance.nodes.Length!=template.nodeCount)throw new InvalidOperationException("Incomplete template node correspondence");
                var replacements=new Dictionary<UnityEngine.Object,UnityEngine.Object>();
                var pairs=new List<KeyValuePair<Component,Component>>();
                foreach(var pair in instance.nodes) {
                    if(!templateNodes.ContainsKey(pair.templateObject)||!nodes.ContainsKey(pair.instanceObject))throw new InvalidOperationException("Native instance mapping unavailable");
                    var old=nodes[pair.instanceObject];var target=templateNodes[pair.templateObject].gameObject;
                    replacements.Add(old,target);replacements.Add(old.transform,target.transform);
                    var counters=new Dictionary<Type,int>();
                    foreach(var component in old.GetComponents<Component>().Where(c=>!(c is Transform))) {
                        if(component==null)throw new InvalidOperationException("Missing component in native instance source");
                        bool derived=false;IdentifyOptionalSpineDerivedComponent(component,ref derived);if(derived)continue;
                        var type=component.GetType();int index=counters.TryGetValue(type,out var count)?count:0;counters[type]=index+1;
                        var candidates=target.GetComponents(type);
                        var destination=index<candidates.Length?candidates[index]:target.AddComponent(type);
                        if(destination==null)throw new InvalidOperationException("Native instance component unavailable");
                        replacements.Add(component,destination);pairs.Add(new KeyValuePair<Component,Component>(component,destination));
                    }
                    foreach(var component in target.GetComponents<Component>().Where(c=>!(c is Transform))) {
                        if(component is CanvasGroup)continue;
                        bool derived=false;IdentifyOptionalSpineDerivedComponent(component,ref derived);if(derived)continue;
                        if(!pairs.Any(p=>p.Value==component))throw new InvalidOperationException("Native template component has no supported instance counterpart: "+component.GetType().Name);
                    }
                }
                foreach(var group in instance.mountedChildren??new PrefabMountedChildren[0]) {
                    if(!nodes.ContainsKey(group.parent))throw new InvalidOperationException("Mounted parent missing");
                    var oldParent=nodes[group.parent];var parent=replacements.TryGetValue(oldParent,out var mappedParent)?(GameObject)mappedParent:oldParent;
                    foreach(var sid in group.roots) {
                        if(!nodes.ContainsKey(sid))throw new InvalidOperationException("Mounted child missing");
                        nodes[sid].transform.SetParent(parent.transform,false);
                        nodes[sid].transform.SetAsLastSibling();
                    }
                }
                foreach(var pair in instance.nodes) {
                    var old=nodes[pair.instanceObject];var target=(GameObject)replacements[old];var from=(RectTransform)old.transform;var to=(RectTransform)target.transform;
                    target.name=old.name;target.layer=old.layer;target.SetActive(old.activeSelf);
                    to.anchorMin=from.anchorMin;to.anchorMax=from.anchorMax;to.pivot=from.pivot;to.sizeDelta=from.sizeDelta;
                    to.anchoredPosition3D=from.anchoredPosition3D;to.localRotation=from.localRotation;to.localScale=from.localScale;
                    var opacity=target.GetComponent<CanvasGroup>();if(opacity!=null)opacity.alpha=sourceNodes[pair.instanceObject].opacity/255f;
                    PrefabUtility.RecordPrefabInstancePropertyModifications(target);PrefabUtility.RecordPrefabInstancePropertyModifications(to);
                    if(opacity!=null)PrefabUtility.RecordPrefabInstancePropertyModifications(opacity);
                }
                foreach(var pair in pairs)CopyNativeProperties(pair.Key,pair.Value);
                foreach(var pair in instance.nodes)nodes[pair.instanceObject]=(GameObject)replacements[nodes[pair.instanceObject]];
                // Repair references inside the cloned subtree and references from the
                // rest of this source graph before retiring temporary construction nodes.
                foreach(var item in nodes.Where(p=>p.Key.Split('#')[0]==owner))
                    foreach(var component in item.Value.GetComponents<Component>())if(component!=null)RemapNativeReferences(component,replacements);
                if(firstEngineError!=null)throw new InvalidOperationException("NATIVE_ENGINE_ERROR_RECORDED during native reference transfer");
                UnityEngine.Object.DestroyImmediate(previousRoot);
                InitializeSavedStaticSpine(root);
                if(Hash(template.path)!=prefabTemplateHashes[instance.template])throw new InvalidOperationException("Instance override mutated shared template");
            } catch { if(root!=null)UnityEngine.Object.DestroyImmediate(root);throw; }
        }
    }
    static Type MountedNativeComponentType(string sourceType) {
        switch(sourceType) {
            case "cc.Widget":return typeof(NativeRectConstraints);
            case "cc.Sprite":return typeof(UnityEngine.UI.Image);
            case "cc.Label":return typeof(TMPro.TextMeshProUGUI);
            case "cc.Button":return typeof(UnityEngine.UI.Button);
            case "cc.ScrollView":return typeof(UnityEngine.UI.ScrollRect);
            case "cc.BlockInputEvents":return typeof(NativeInputBlocker);
            case "cc.Mask":return typeof(UnityEngine.UI.RectMask2D);
            default:throw new InvalidOperationException("Mounted native component proof requires a typed adapter: "+sourceType);
        }
    }
    static PrefabInstanceResult[] ReadNativeInstances(Plan plan,Dictionary<string,RectTransform> nodes,string owner=null,string outerAssetPath=null,bool captureAssetProof=false) {
        var templates=(plan.sourcePrefabs??new SourcePrefabSpec[0]).ToDictionary(p=>p.sourceId);var results=new List<PrefabInstanceResult>();
        foreach(var instance in (plan.prefabInstances??new PrefabInstanceSpec[0]).Where(s=>owner==null||s.owner==owner)) {
            if(!nodes.ContainsKey(instance.root)||!templates.ContainsKey(instance.template))throw new InvalidOperationException("Saved native instance missing");
            var template=templates[instance.template];var root=nodes[instance.root].gameObject;
            var corresponding=PrefabUtility.GetCorrespondingObjectFromSourceAtPath(root,template.path);
            bool linked=PrefabUtility.IsPartOfPrefabInstance(root),matched=corresponding!=null&&AssetDatabase.GetAssetPath(corresponding)==template.path;
            string guid="";long fileId=0;
            if(corresponding!=null)AssetDatabase.TryGetGUIDAndLocalFileIdentifier(corresponding,out guid,out fileId);
            bool unchanged=Hash(template.path)==prefabTemplateHashes[instance.template];
            if(!linked||!matched||!unchanged||guid!=AssetDatabase.AssetPathToGUID(template.path)||fileId==0)throw new InvalidOperationException("Saved native template relationship differs: "+instance.root);
            var persistentNodes=SavedNodeMap(plan.nodes,AssetDatabase.LoadAssetAtPath<GameObject>(template.path),template);
            foreach(var pair in instance.nodes) {
                if(!nodes.ContainsKey(pair.instanceObject)||!persistentNodes.ContainsKey(pair.templateObject)||
                    PrefabUtility.GetCorrespondingObjectFromSourceAtPath(nodes[pair.instanceObject].gameObject,template.path)!=persistentNodes[pair.templateObject].gameObject)
                    throw new InvalidOperationException("Saved nested node lost its template correspondence");
            }
            var modifications=PrefabUtility.GetPropertyModifications(PrefabUtility.GetNearestPrefabInstanceRoot(root));
            Dictionary<string,RectTransform> owningAssetNodes=null;
            bool InheritedMount(UnityEngine.Object current,string sid,Type componentType=null) {
                // Scene instances inherit mounts from the assembled Candidate
                // Prefab, so IsAdded*Override is false against that outer asset.
                // Require its independent native added-override proof, unchanged
                // bytes and exact object correspondence to that actual asset.
                if(captureAssetProof||string.IsNullOrEmpty(outerAssetPath)||!savedMountProofs.TryGetValue(instance.root,out var proof)||
                    proof.templateGuid!=guid||!proof.mountedChildrenVerified||!proof.mountedComponentsVerified||
                    savedMountProofAssets[instance.root]!=outerAssetPath||Hash(outerAssetPath)!=savedMountProofHashes[instance.root])return false;
                if(owningAssetNodes==null)owningAssetNodes=SavedNodeMap(plan.nodes,AssetDatabase.LoadAssetAtPath<GameObject>(outerAssetPath));
                if(!owningAssetNodes.ContainsKey(sid))return false;
                UnityEngine.Object expected=componentType==null?(UnityEngine.Object)owningAssetNodes[sid].gameObject:owningAssetNodes[sid].GetComponent(componentType);
                return expected!=null&&PrefabUtility.GetCorrespondingObjectFromSourceAtPath(current,outerAssetPath)==expected;
            }
            int mountedRoots=0,mountedNodes=0,mountedComponents=0;
            foreach(var group in instance.mountedChildren??new PrefabMountedChildren[0]) {
                foreach(var sid in group.roots) {
                    if(!nodes.ContainsKey(sid)||nodes[sid].parent!=nodes[group.parent]||
                        (!PrefabUtility.IsAddedGameObjectOverride(nodes[sid].gameObject)&&!InheritedMount(nodes[sid].gameObject,sid)))
                        throw new InvalidOperationException("Saved mounted child is not a native added-object override");
                    mountedRoots++;
                }
                foreach(var sid in group.nodes) {
                    if(!nodes.ContainsKey(sid)||PrefabUtility.GetCorrespondingObjectFromSourceAtPath(nodes[sid].gameObject,template.path)!=null)
                        throw new InvalidOperationException("Mounted subtree unexpectedly belongs to the shared template");
                    mountedNodes++;
                }
            }
            foreach(var mounted in instance.mountedComponents??new PrefabMountedComponent[0]) {
                var component=nodes[mounted.node].GetComponent(MountedNativeComponentType(mounted.sourceType));
                if(component==null||(!PrefabUtility.IsAddedComponentOverride(component)&&!InheritedMount(component,mounted.node,MountedNativeComponentType(mounted.sourceType)))||PrefabUtility.GetCorrespondingObjectFromSourceAtPath(component,template.path)!=null)
                    throw new InvalidOperationException("Saved mounted component is not a native added-component override");
                mountedComponents++;
            }
            var row=new PrefabInstanceResult {root=instance.root,templateSourceId=instance.template,templatePath=template.path,templateGuid=guid,
                templateRootFileId=fileId,nativeInstance=linked,correspondingSourceVerified=matched,nodeCorrespondenceVerified=true,templateUnchanged=unchanged,
                nodeCount=instance.nodes.Length,propertyModificationCount=modifications==null?0:modifications.Length,
                mountedChildrenVerified=true,mountedComponentsVerified=true,mountedRootCount=mountedRoots,mountedNodeCount=mountedNodes,mountedComponentCount=mountedComponents};
            results.Add(row);
            if(captureAssetProof){savedMountProofs[instance.root]=row;savedMountProofHashes[instance.root]=Hash(outerAssetPath);savedMountProofAssets[instance.root]=outerAssetPath;}
        }
        return results.ToArray();
    }
}
