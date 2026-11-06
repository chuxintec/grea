using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static partial class MonkeyImporter
{
    [Serializable] public class PreviewLabelMaterial {public string sourceId,material,shader,font;public float outlineWidth,gradientScale,scaleRatioA;public float[] outlineColor;public bool fallback;}
    [Serializable] public class StaticPreviewResult {
        public string stateId,stateSha256,sourcePrefabId,prefabPath,scenePath,previewPath,previewSha256;
        public bool savedReloaded,independentReopen;
        public UnityPreviewState.Readback state;
        public UnityPreviewClones.Readback[] clones;
        public UnityStaticSpriteFrames.Result[] spriteProjections;
        public StaticFieldResult[] fields; public PreviewLabelMaterial[] labelMaterials;
    }
    static System.Collections.Generic.Dictionary<string,GameObject> PreviewNodeMap(Plan plan,GameObject root,SourcePrefabSpec spec) {
        var batches=plan.previewState.cloneBatches??Array.Empty<UnityPreviewClones.CloneBatch>();
        if(batches.Length==0&&(plan.previewState.spriteProjection==null||plan.previewState.spriteProjection.entries==null))return SavedNodeMap(plan.nodes,root,spec).ToDictionary(x=>x.Key,x=>x.Value.gameObject);
        var byId=plan.nodes.ToDictionary(x=>x.sourceId);
        var projections=(plan.previewState.spriteProjection==null?Array.Empty<UnityStaticSpriteFrames.Entry>():plan.previewState.spriteProjection.entries??Array.Empty<UnityStaticSpriteFrames.Entry>()).ToDictionary(x=>x.parentSourceId);
        var parents=batches.ToDictionary(x=>x.template.parentSourceId);
        var mapped=new System.Collections.Generic.Dictionary<string,GameObject>();
        Action<string,Transform> walk=null;
        walk=(id,target)=>{
            var source=byId[id];var children=SourceChildren(target);
            mapped.Add(id,target.gameObject);
            if(parents.TryGetValue(id,out var batch)) {
                if(children.Length!=batch.template.expectedChildCount)throw new InvalidOperationException("STATIC_PREVIEW_CLONE_BOUNDARY: "+id);
                if(batch.template.placementMode=="append-external") {
                    if(!source.children.SequenceEqual(batch.template.initialChildSourceIds))throw new InvalidOperationException("STATIC_PREVIEW_CLONE_PREFIX: "+id);
                    for(int i=0;i<source.children.Length;i++)walk(source.children[i],children[i]);
                } else {
                    if(source.children.Length!=1)throw new InvalidOperationException("STATIC_PREVIEW_CLONE_BOUNDARY: "+id);
                    walk(source.children[0],children[0]);
                }
            } else if(projections.ContainsKey(id)) {
                var projection=projections[id];
                if(source.children.Length!=0||projection.expectedParentChildSourceIds.Length!=0||children.Length!=1)
                    throw new InvalidOperationException("STATIC_PREVIEW_PROJECTION_BOUNDARY: "+id);
            } else {
                if(children.Length!=source.children.Length)throw new InvalidOperationException("STATIC_PREVIEW_HIERARCHY: "+id);
                for(int i=0;i<children.Length;i++)walk(source.children[i],children[i]);
            }
        };
        walk(spec.root,root.transform);
        if(mapped.Count!=spec.nodeCount)throw new InvalidOperationException("STATIC_PREVIEW_SOURCE_NODE_COUNT");
        return mapped;
    }
    static UnityEngine.Object PreviewCloneReference(Plan plan,System.Collections.Generic.IDictionary<string,GameObject> nodes,string id) {
        return StaticReference(plan,nodes.ToDictionary(x=>x.Key,x=>x.Value),id);
    }
    static GameObject PreviewCloneTemplate(Plan plan,string prefabId,string rootId) {
        var spec=plan.sourcePrefabs.Single(x=>x.sourceId==prefabId&&x.root==rootId);
        var native=AssetDatabase.LoadAssetAtPath<GameObject>(spec.path);
        var clone=UnityEngine.Object.Instantiate(native);clone.name=native.name;
        var source=plan.nodes.Single(x=>x.sourceId==rootId);
        // Standalone Prefab roots include the design-origin offset. A list
        // template is local to its parent and uses its serialized position.
        ((RectTransform)clone.transform).anchoredPosition3D=new Vector3(source.position[0],source.position[1],source.position[2]);
        return clone;
    }
    static string StaticPreviewStem(Plan plan) {return "Assets/Game/Preview/States/State_"+plan.previewState.stateSha256.Substring(0,16);}
    static StaticPreviewResult[] BuildStaticPreviews(Plan plan) {
        var states=plan.previewStates??(plan.previewState==null?Array.Empty<UnityPreviewState.Spec>():new[]{plan.previewState});
        var primary=plan.previewState;var results=new System.Collections.Generic.List<StaticPreviewResult>();
        try {foreach(var state in states){plan.previewState=state;results.Add(BuildStaticPreview(plan));}}
        finally{plan.previewState=primary;}
        return results.ToArray();
    }
    static StaticPreviewResult BuildStaticPreview(Plan plan) {
        if(plan.previewState==null||string.IsNullOrEmpty(plan.previewState.stateSha256))return null;
        var spec=plan.sourcePrefabs.Single(x=>x.sourceId==plan.previewState.sourcePrefabId);
        string stem=StaticPreviewStem(plan);Directory.CreateDirectory(Path.GetDirectoryName(stem));
        var source=AssetDatabase.LoadAssetAtPath<GameObject>(spec.path);
        var previewScene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Additive);
        try {
            var context=new GameObject("StaticPreviewCanvas",typeof(RectTransform),typeof(Canvas));
            SceneManager.MoveGameObjectToScene(context,previewScene);
            var canvas=context.GetComponent<Canvas>();canvas.renderMode=RenderMode.WorldSpace;
            ((RectTransform)context.transform).sizeDelta=new Vector2(plan.designSize[0],plan.designSize[1]);
            var clone=UnityEngine.Object.Instantiate(source,context.transform,false);clone.name=source.name;
            var nodes=SavedNodeMap(plan.nodes,clone,spec).ToDictionary(x=>x.Key,x=>x.Value.gameObject);
            SettleNativeLayout(context);
            foreach(var batch in plan.previewState.cloneBatches??Array.Empty<UnityPreviewClones.CloneBatch>()) {
                var result=UnityPreviewClones.Apply(batch,nodes,(map,id)=>PreviewCloneReference(plan,map,id),go=>{SettleNativeLayout(go);},
                    (prefabId,rootId)=>PreviewCloneTemplate(plan,prefabId,rootId));
                if(!result.verified)throw new InvalidOperationException("STATIC_PREVIEW_CLONE_APPLY_FAILED");
            }
            if(plan.previewState.spriteProjection!=null&&plan.previewState.spriteProjection.entries!=null)
                if(UnityStaticSpriteFrames.Apply(plan.previewState.spriteProjection,nodes,id=>StaticReference(plan,nodes,id) as Sprite).Any(x=>!x.verified))
                    throw new InvalidOperationException("STATIC_PREVIEW_PROJECTION_APPLY_FAILED");
            nodes=PreviewNodeMap(plan,clone,spec);
            AssignStaticFields(plan,nodes);
            UnityPreviewState.Apply(plan.previewState,id=>StaticReference(plan,nodes,id));
            SettleNativeLayout(context);
            // This derived asset is a frozen static state. Persist the evaluated
            // native geometry so reopening cannot rebuild it before TMP is ready.
            // Original source prefabs retain their enabled layout controllers.
            var liveLayoutNodes=new System.Collections.Generic.HashSet<GameObject>((plan.previewState.cloneBatches??Array.Empty<UnityPreviewClones.CloneBatch>())
                .Where(b=>b.template.layoutMode=="native-layout").Select(b=>nodes[b.template.parentSourceId]));
            foreach(var controller in clone.GetComponentsInChildren<UnityEngine.UI.LayoutGroup>(true))if(!liveLayoutNodes.Contains(controller.gameObject))controller.enabled=false;
            foreach(var fitter in clone.GetComponentsInChildren<UnityEngine.UI.ContentSizeFitter>(true))if(!liveLayoutNodes.Contains(fitter.gameObject))fitter.enabled=false;
            foreach(var constraint in clone.GetComponentsInChildren<NativeRectConstraints>(true))constraint.enabled=false;
            PrefabUtility.SaveAsPrefabAsset(clone,stem+".prefab",out bool saved);
            if(!saved)throw new InvalidOperationException("STATIC_PREVIEW_SAVE_FAILED");
            UnityEngine.Object.DestroyImmediate(clone);
            var savedPrefab=AssetDatabase.LoadAssetAtPath<GameObject>(stem+".prefab");
            clone=(GameObject)PrefabUtility.InstantiatePrefab(savedPrefab,context.transform);
            var cameraObject=new GameObject("StaticPreviewCamera",typeof(Camera));SceneManager.MoveGameObjectToScene(cameraObject,previewScene);
            var camera=cameraObject.GetComponent<Camera>();camera.orthographic=true;camera.orthographicSize=plan.designSize[1]*.5f;camera.transform.position=new Vector3(0,0,-10);camera.nearClipPlane=.1f;camera.farClipPlane=100;camera.cullingMask=1<<5;
            foreach(var transform in context.GetComponentsInChildren<Transform>(true))transform.gameObject.layer=5;
            // Persist design-space coordinates; viewport-dependent screen-space transforms
            // would be baked into the scene and shift off-screen captures after reopen.
            canvas.renderMode=RenderMode.WorldSpace;canvas.worldCamera=camera;
            // Leaf prefabs retain their source list-local position. Frame the root
            // rectangle in the preview camera instead of rewriting that position.
            var rootRect=clone.GetComponent<RectTransform>();
            var center=rootRect.TransformPoint(rootRect.rect.center);
            camera.transform.position=new Vector3(center.x,center.y,-10);
            Canvas.ForceUpdateCanvases();
            camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.1f,.11f,.13f,1);
            if(!EditorSceneManager.SaveScene(previewScene,stem+".unity"))throw new InvalidOperationException("STATIC_PREVIEW_SCENE_SAVE_FAILED");
        } finally {EditorSceneManager.CloseScene(previewScene,true);}
        return ReadStaticPreview(plan,false);
    }
    static StaticPreviewResult ReadStaticPreview(Plan plan,bool independent) {
        string stem=StaticPreviewStem(plan);
        var scene=EditorSceneManager.OpenScene(stem+".unity",OpenSceneMode.Additive);
        try {
            var canvas=scene.GetRootGameObjects().Single(x=>x.name=="StaticPreviewCanvas").GetComponent<Canvas>();
            var root=canvas.transform.GetChild(0).gameObject;
            var source=plan.sourcePrefabs.Single(x=>x.sourceId==plan.previewState.sourcePrefabId);
            var nodes=PreviewNodeMap(plan,root,source);
            SettleNativeLayout(canvas.gameObject);
            var state=UnityPreviewState.Read(plan.previewState,id=>StaticReference(plan,nodes,id));
            string path="Analysis/Readback/PreviewStates/"+plan.previewState.stateSha256.Substring(0,16)+(independent?"-reopen":"")+".png";
            Capture(canvas,scene,(int)plan.designSize[0],(int)plan.designSize[1],path,true);
            var persistent=AssetDatabase.LoadAssetAtPath<GameObject>(stem+".prefab");
            var map=PreviewNodeMap(plan,persistent,source);
            var clones=(plan.previewState.cloneBatches??Array.Empty<UnityPreviewClones.CloneBatch>()).Select(b=>
                UnityPreviewClones.Read(b,nodes,(local,id)=>PreviewCloneReference(plan,local,id),go=>{SettleNativeLayout(go);})).ToArray();
            var projections=plan.previewState.spriteProjection!=null&&plan.previewState.spriteProjection.entries!=null?
                UnityStaticSpriteFrames.Read(plan.previewState.spriteProjection,nodes,id=>StaticReference(plan,nodes,id) as Sprite):Array.Empty<UnityStaticSpriteFrames.Result>();
            if(projections.Any(x=>!x.verified))throw new InvalidOperationException("STATIC_PREVIEW_PROJECTION_READBACK_FAILED");
            if(clones.Any(x=>!x.verified))throw new InvalidOperationException("STATIC_PREVIEW_CLONE_REOPEN_FAILED");
            return new StaticPreviewResult{stateId=plan.previewState.stateId,stateSha256=plan.previewState.stateSha256,sourcePrefabId=source.sourceId,
                prefabPath=stem+".prefab",scenePath=stem+".unity",previewPath=path,previewSha256=Hash(path),savedReloaded=true,independentReopen=independent,state=state,clones=clones,spriteProjections=projections,fields=ReadStaticFields(plan,map),labelMaterials=nodes.SelectMany(pair=> {
                    var label=pair.Value.GetComponent<TMPro.TextMeshProUGUI>();if(label==null)return new PreviewLabelMaterial[0];
                    var materials=new[]{label.fontSharedMaterial}.Concat(label.GetComponentsInChildren<TMPro.TMP_SubMeshUI>(true).Select(x=>x.sharedMaterial)).ToArray();
                    return materials.Where(m=>m!=null).Select((m,i)=>new PreviewLabelMaterial{sourceId=pair.Key,font=label.font.name,material=m.name,shader=m.shader.name,fallback=i>0,
                        outlineWidth=m.HasProperty("_OutlineWidth")?m.GetFloat("_OutlineWidth"):0,gradientScale=m.HasProperty("_GradientScale")?m.GetFloat("_GradientScale"):0,scaleRatioA=m.HasProperty("_ScaleRatioA")?m.GetFloat("_ScaleRatioA"):0,
                        outlineColor=m.HasProperty("_OutlineColor")?new[]{m.GetColor("_OutlineColor").r,m.GetColor("_OutlineColor").g,m.GetColor("_OutlineColor").b,m.GetColor("_OutlineColor").a}:new float[0]}).ToArray();
                }).ToArray()};
        }finally{EditorSceneManager.CloseScene(scene,true);}
    }
    [MenuItem("Tools/Monkey/Reopen Static Preview")]
    public static void ReopenStaticPreview() {
        var plan=JsonUtility.FromJson<Plan>(File.ReadAllText(Paths.plan));
        // Verify the displayed state when a candidate contains several previews.
        var activePath=SceneManager.GetActiveScene().path;
        foreach(var state in plan.previewStates??Array.Empty<UnityPreviewState.Spec>())
            if(activePath=="Assets/Game/Preview/States/State_"+state.stateSha256.Substring(0,16)+".unity")
                {plan.previewState=state;break;}
        var path=StaticPreviewStem(plan)+".unity";
        var loaded=SceneManager.GetSceneByPath(path);bool restore=loaded.IsValid()&&loaded.isLoaded;
        Scene temporary=default(Scene);
        if(restore){
            if(loaded.isDirty)throw new InvalidOperationException("STATIC_PREVIEW_SAVE_BEFORE_REOPEN");
            if(SceneManager.sceneCount==1)temporary=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Additive);
            EditorSceneManager.CloseScene(loaded,true);
        }
        try{
            var readback=ReadStaticPreview(plan,true);
            Directory.CreateDirectory("Analysis/Readback");File.WriteAllText("Analysis/Readback/static-preview-independent-reopen.json",JsonUtility.ToJson(readback,true));
            File.WriteAllText("Analysis/Readback/PreviewStates/"+plan.previewState.stateSha256.Substring(0,16)+"-reopen.json",JsonUtility.ToJson(readback,true));
        }finally{
            if(restore){var reopened=EditorSceneManager.OpenScene(path,OpenSceneMode.Additive);SceneManager.SetActiveScene(reopened);}
            if(temporary.IsValid()&&temporary.isLoaded)EditorSceneManager.CloseScene(temporary,true);
        }
    }
    [MenuItem("Tools/Monkey/Open Static Preview")]
    public static void OpenStaticPreview() {
        var plan=JsonUtility.FromJson<Plan>(File.ReadAllText(Paths.plan));
        var path=plan.previewState!=null&&!string.IsNullOrEmpty(plan.previewState.stateSha256)?StaticPreviewStem(plan)+".unity":ScenePath;
        if(!File.Exists(path))throw new InvalidOperationException("NATIVE_PREVIEW_SCENE_MISSING: "+path);
        EditorSceneManager.OpenScene(path,OpenSceneMode.Single);
        var gameView=Type.GetType("UnityEditor.GameView,UnityEditor");if(gameView!=null)EditorWindow.GetWindow(gameView).Show();
    }
}
