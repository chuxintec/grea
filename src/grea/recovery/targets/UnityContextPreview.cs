using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static partial class MonkeyImporter {
    [Serializable] public class ContextPreviewRequest {
        public string planSha256,sourcePrefabId,prefabSha256;
        public ContextPreviewTarget[] targets;
    }
    [Serializable] public class ContextPreviewTarget {
        public string targetPrefabId,targetNodeId,sourceInstanceFileId,sourceDocumentSha256;
        public string templateGuid,templateSha256Before,templateSha256After; public long templateRootLocalId;
        public bool nativeCorrespondenceVerified;
    }
    [Serializable] public class ContextPreviewNode {
        public string sourceId,name,parentSourceId,path;
        public bool activeSelf,activeInHierarchy;
        public string originalSourceGuid; public long originalSourceLocalId;
        public int siblingIndex,enabledGraphics,allGraphics;
        public float[] anchorMin,anchorMax,pivot,size,position,scale,pixelBounds;
        public string[] ancestorMasks;
    }
    [Serializable] public class ContextPreviewResult {
        public string unityVersion,planSha256,sourcePrefabId,prefabPath,prefabSha256Before,prefabSha256After;
        public string previewPath,previewSha256,scope;
        public bool assetUnchanged,sourceRootActive;
        public ContextPreviewTarget[] targets;
        public ContextPreviewNode[] nodes;
    }
    static float[] ContextPair(Vector2 value) {return new[]{value.x,value.y};}
    static float[] ContextTriple(Vector3 value) {return new[]{value.x,value.y,value.z};}
    static string ContextPath(Transform node,Transform root) {
        var parts=new List<string>();
        for(var current=node;current!=null;current=current.parent) {
            parts.Add(current.name);if(current==root)break;
        }
        parts.Reverse();return string.Join("/",parts.ToArray());
    }
    // Explicit diagnostic entry point. The request is prepared from source
    // PrefabInfo + native plan relationships, never from a matching name.
    public static void CaptureContextPreview() {
        if(!Application.isBatchMode)throw new InvalidOperationException("CONTEXT_PREVIEW_REQUIRES_ISOLATED_BATCH_PROJECT");
        try {
            if(File.Exists("Assets/ContextPreviewHost.unity"))throw new InvalidOperationException("CONTEXT_PREVIEW_HOST_EXISTS");
            var planPath=Paths.plan;
            var request=JsonUtility.FromJson<ContextPreviewRequest>(File.ReadAllText("context-preview-request.json"));
            if(request==null||Hash(planPath)!=request.planSha256||request.targets==null||request.targets.Length==0)
                throw new InvalidOperationException("CONTEXT_PREVIEW_REQUEST_PIN");
            var plan=JsonUtility.FromJson<Plan>(File.ReadAllText(planPath));
            var spec=plan.sourcePrefabs.Single(p=>p.sourceId==request.sourcePrefabId);
            if(Hash(spec.path)!=request.prefabSha256)throw new InvalidOperationException("CONTEXT_PREVIEW_PREFAB_PIN");
            foreach(var target in request.targets) {
                if(string.IsNullOrEmpty(target.sourceDocumentSha256)||target.sourceDocumentSha256.Length!=64)
                    throw new InvalidOperationException("CONTEXT_PREVIEW_SOURCE_PIN");
                var relation=(plan.prefabInstances??Array.Empty<PrefabInstanceSpec>()).Single(p=>
                    p.owner==spec.sourceId&&p.root==target.targetNodeId&&p.template==target.targetPrefabId&&
                    p.sourceInstanceFileId==target.sourceInstanceFileId);
                if(!spec.nodes.Contains(target.targetNodeId))throw new InvalidOperationException("CONTEXT_PREVIEW_TARGET_BOUNDARY");
            }
            var host=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            EditorSceneManager.SaveScene(host,"Assets/ContextPreviewHost.unity");
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Additive);
            ContextPreviewResult result=null;
            try {
                var context=new GameObject("OwnedSourceContextPreview",typeof(RectTransform),typeof(Canvas));
                SceneManager.MoveGameObjectToScene(context,scene);
                var canvas=context.GetComponent<Canvas>();canvas.renderMode=RenderMode.WorldSpace;
                ((RectTransform)context.transform).sizeDelta=new Vector2(plan.designSize[0],plan.designSize[1]);
                var prefab=AssetDatabase.LoadAssetAtPath<GameObject>(spec.path);
                var clone=(GameObject)PrefabUtility.InstantiatePrefab(prefab,context.transform);
                // Preserve the actual parent tree, root and child activity,
                // masks, ordering and source coordinates. No leaf insertion.
                SettleNativeLayout(context);
                var mapped=SavedNodeMap(plan.nodes,clone,spec);
                var sources=plan.nodes.ToDictionary(n=>n.sourceId);
                foreach(var target in request.targets) {
                    var relation=plan.prefabInstances.Single(p=>p.owner==spec.sourceId&&p.root==target.targetNodeId&&p.template==target.targetPrefabId);
                    var template=plan.sourcePrefabs.Single(p=>p.sourceId==target.targetPrefabId);
                    target.templateSha256Before=Hash(template.path);
                    var templateMap=SavedNodeMap(plan.nodes,AssetDatabase.LoadAssetAtPath<GameObject>(template.path),template);
                    foreach(var pair in relation.nodes) {
                        if(!mapped.ContainsKey(pair.instanceObject)||!templateMap.ContainsKey(pair.templateObject)||
                            PrefabUtility.GetCorrespondingObjectFromSourceAtPath(mapped[pair.instanceObject].gameObject,template.path)!=templateMap[pair.templateObject].gameObject)
                            throw new InvalidOperationException("CONTEXT_PREVIEW_NATIVE_TEMPLATE_MISMATCH: "+pair.instanceObject);
                    }
                    if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(templateMap[template.root].gameObject,out target.templateGuid,out target.templateRootLocalId)||target.templateRootLocalId==0)
                        throw new InvalidOperationException("CONTEXT_PREVIEW_NATIVE_TEMPLATE_IDENTITY");
                    target.nativeCorrespondenceVerified=true;
                }
                var stem="Analysis/Readback/ContextPreview/"+request.planSha256.Substring(0,16)+"/"+AssetDatabase.AssetPathToGUID(spec.path);
                if(File.Exists(stem+".png")||File.Exists(stem+".json"))throw new InvalidOperationException("CONTEXT_PREVIEW_OUTPUT_EXISTS");
                Capture(canvas,scene,(int)plan.designSize[0],(int)plan.designSize[1],stem+".png");
                var rootRect=(RectTransform)context.transform;
                var observations=mapped.Select(pair=> {
                    var node=pair.Value;var corners=new Vector3[4];node.GetWorldCorners(corners);
                    var pixels=corners.Select(c=>rootRect.InverseTransformPoint(c)+new Vector3(rootRect.rect.width*.5f,rootRect.rect.height*.5f,0)).ToArray();
                    var graphics=node.GetComponentsInChildren<UnityEngine.UI.Graphic>(true);
                    var original=PrefabUtility.GetCorrespondingObjectFromOriginalSource(node.gameObject);
                    string originalGuid=null;long originalId=0;
                    if(original!=null)AssetDatabase.TryGetGUIDAndLocalFileIdentifier(original,out originalGuid,out originalId);
                    return new ContextPreviewNode {sourceId=pair.Key,name=node.name,parentSourceId=sources[pair.Key].parent,
                        path=ContextPath(node,clone.transform),originalSourceGuid=originalGuid,originalSourceLocalId=originalId,activeSelf=node.gameObject.activeSelf,activeInHierarchy=node.gameObject.activeInHierarchy,
                        siblingIndex=node.GetSiblingIndex(),anchorMin=ContextPair(node.anchorMin),anchorMax=ContextPair(node.anchorMax),
                        pivot=ContextPair(node.pivot),size=ContextPair(node.rect.size),position=ContextTriple(node.anchoredPosition3D),scale=ContextTriple(node.localScale),
                        pixelBounds=new[]{pixels.Min(v=>v.x),pixels.Min(v=>v.y),pixels.Max(v=>v.x),pixels.Max(v=>v.y)},
                        enabledGraphics=graphics.Count(g=>g.isActiveAndEnabled),allGraphics=graphics.Length,
                        ancestorMasks=node.GetComponentsInParent<UnityEngine.UI.Mask>(true).Select(m=>ContextPath(m.transform,clone.transform)+";enabled="+m.enabled).ToArray()};
                }).ToArray();
                foreach(var target in request.targets) {
                    var template=plan.sourcePrefabs.Single(p=>p.sourceId==target.targetPrefabId);
                    target.templateSha256After=Hash(template.path);
                    if(target.templateSha256Before!=target.templateSha256After)throw new InvalidOperationException("CONTEXT_PREVIEW_TEMPLATE_MODIFIED");
                }
                result=new ContextPreviewResult{unityVersion=Application.unityVersion,planSha256=request.planSha256,
                    sourcePrefabId=spec.sourceId,prefabPath=spec.path,prefabSha256Before=request.prefabSha256,prefabSha256After=Hash(spec.path),
                    previewPath=stem+".png",previewSha256=Hash(stem+".png"),sourceRootActive=clone.activeSelf,
                    scope="source-proven-parent-authored-state-no-business-no-activity-or-geometry-override",targets=request.targets,nodes=observations};
                result.assetUnchanged=result.prefabSha256Before==result.prefabSha256After;
                File.WriteAllText(stem+".json",JsonUtility.ToJson(result,true));
                File.WriteAllText("context-preview-result.json",JsonUtility.ToJson(result,true));
            } finally {EditorSceneManager.CloseScene(scene,true);}
            EditorApplication.Exit(result!=null&&result.assetUnchanged?0:2);
        } catch(Exception error) {File.WriteAllText("context-preview-error.txt",error.ToString());EditorApplication.Exit(1);}
    }
}
