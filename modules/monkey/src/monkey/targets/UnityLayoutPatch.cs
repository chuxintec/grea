// Conversion-only replacement of an exactly audited legacy layout subset.
// Placement, wrapping, sizing and fitting are performed by Unity uGUI.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UI;

public static partial class MonkeyImporter
{
    [Serializable] public class LayoutPatchCase {public string sourceId,node,mode,oldComponentFileId,sourceRoot;public string[] sourceNodes;public int nodeCount;public bool enabled,fitVertical;public float[] cellSize;}
    [Serializable] public class LayoutPatchIdentity {public string sourceId,gameObjectFileId,transformFileId;}
    [Serializable] public class LayoutPatchTarget {public string sourceId,path,guid,sha256,convertedSha256;public bool aggregate,reusedPriorEvidence;public LayoutPatchCase[] cases;public NodeResult[] baseline;public LayoutPatchIdentity[] identities;}
    [Serializable] public class LayoutPatchPlan {public string sourceManifestSha256,targetImportPlanSha256,flowScriptGuid,deadlineUtc,priorReadbackPath,priorReadbackSha256;public int budgetSeconds,reusedAssets;public LayoutPatchTarget[] targets;}
    [Serializable] public class LayoutPatchMapping {public string sourceId,node,oldComponentFileId,newComponentFileId,nativeType,scriptGuid,fitterFileId;public bool enabled;}
    [Serializable] public class LayoutPatchAssetResult {public string sourceId,path,guid,beforeSha256,afterSha256,status,priorReadbackSha256;public int missingBefore,missingAfter,identityNodes,geometryNodes;public bool reusedPriorEvidence;public LayoutPatchMapping[] mappings;}
    [Serializable] public class LayoutPatchResult {public int schemaVersion=1,reusedAssets;public string status,reason,unityVersion,planSha256,method="MonkeyImporter.ReplaceAuditedLayouts";public LayoutPatchAssetResult[] assets;public DynamicUiResult[] probes;public string[] limitations;public bool sourceRuntimeTypeAbsent,legacyReferencesAbsent;public string timing="Editor-native-forced-update;Player-not_run";}
    static LayoutPatchPlan layoutPatch;static System.Diagnostics.Stopwatch layoutPatchClock;static string layoutPatchError;
    static void LayoutPatchCheck() {
        if(layoutPatchError!=null)throw new InvalidOperationException(layoutPatchError);
        if(layoutPatchClock.Elapsed.TotalSeconds>layoutPatch.budgetSeconds||DateTime.UtcNow>=DateTime.Parse(layoutPatch.deadlineUtc,null,DateTimeStyles.AdjustToUniversal|DateTimeStyles.AssumeUniversal))throw new TimeoutException("Layout patch deadline");
    }
    static void LayoutPatchLog(string message,string stack,LogType type) {if(type==LogType.Error||type==LogType.Exception||type==LogType.Assert)layoutPatchError="Engine error; see private Editor log";}
    static int LayoutMissing(GameObject root) {return root.GetComponentsInChildren<Transform>(true).Sum(t=>GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject));}
    static string LayoutId(UnityEngine.Object value,string guid) {
        string actual;long id;
        if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value,out actual,out id)||actual!=guid||id==0)throw new InvalidOperationException("Persistent native object identity unavailable");
        return id.ToString(CultureInfo.InvariantCulture);
    }
    static void LayoutSettle(GameObject root) {
        var rects=root.GetComponentsInChildren<RectTransform>(true);
        Func<RectTransform,Vector4> snapshot=r=>new Vector4(r.rect.width,r.rect.height,r.localPosition.x,r.localPosition.y);
        for(int pass=0;pass<8;pass++) {
            LayoutPatchCheck();var before=rects.Select(snapshot).ToArray();
            foreach(var constraint in root.GetComponentsInChildren<NativeRectConstraints>(true).Where(c=>c.isActiveAndEnabled))constraint.Refresh();
            foreach(var label in root.GetComponentsInChildren<TMPro.TextMeshProUGUI>(true).Where(c=>c.isActiveAndEnabled))label.ForceMeshUpdate();
            var controllers=root.GetComponentsInChildren<LayoutGroup>(true).Where(c=>c.isActiveAndEnabled).Select(c=>(RectTransform)c.transform)
                .Concat(root.GetComponentsInChildren<ContentSizeFitter>(true).Where(c=>c.isActiveAndEnabled).Select(c=>(RectTransform)c.transform)).Distinct().Reverse();
            foreach(var rect in controllers)LayoutRebuilder.ForceRebuildLayoutImmediate(rect);
            Canvas.ForceUpdateCanvases();
            if(rects.Select((r,i)=>(snapshot(r)-before[i]).sqrMagnitude).All(v=>v<1e-10f))return;
        }
        throw new InvalidOperationException("Native layout did not settle in eight passes");
    }
    static void LayoutCompare(NodeResult expected,RectTransform actual) {
        Func<float[],float[],bool> differs=(a,b)=>a.Length!=b.Length||a.Where((v,i)=>Math.Abs(v-b[i])>.03f).Any();
        if(differs(expected.size,new[]{actual.rect.width,actual.rect.height})||differs(expected.position,new[]{actual.localPosition.x,actual.localPosition.y,actual.localPosition.z})||
           differs(expected.pivot,new[]{actual.pivot.x,actual.pivot.y})||differs(expected.scale,new[]{actual.localScale.x,actual.localScale.y,actual.localScale.z})||
           differs(expected.rotation,new[]{actual.localRotation.x,actual.localRotation.y,actual.localRotation.z,actual.localRotation.w})||expected.active!=actual.gameObject.activeSelf)
            throw new InvalidOperationException("Frozen geometry differs: "+expected.sourceId+" expected size "+string.Join(",",expected.size)+" actual "+actual.rect.size+" expected position "+string.Join(",",expected.position)+" actual "+actual.localPosition);
    }
    static Dictionary<string,RectTransform> LayoutMap(Plan plan,GameObject root,LayoutPatchTarget target) {
        var first=target.cases[0];return SavedNodeMap(plan.nodes,root,target.aggregate?null:new SourcePrefabSpec{root=first.sourceRoot,nodes=first.sourceNodes,nodeCount=first.nodeCount});
    }
    static bool LayoutProbeSelected(LayoutPatchCase c,LayoutPatchTarget target,HashSet<string> groups,out string key) {
        key=!c.enabled?"disabled-authored":c.mode=="unity-horizontal-row"?"heterogeneous-row":c.sourceId.Contains("b4b4aa5a-e124")?"inactive-exact-template":
            c.mode=="unity-grid"?"fixed-cell-grid":target.path.Contains("WeekTaskLastReward")?"dynamic-wrap-grid":c.sourceId.Contains("5031e7ac")?"bottom-right-grid":null;
        return key!=null&&!groups.Contains(key);
    }
    static DynamicUiResult LayoutProbe(Plan plan,LayoutPatchTarget target,LayoutPatchCase c,string key,List<string> limitations) {
        GameObject root=null,context=null;
        try {
            root=PrefabUtility.LoadPrefabContents(target.path);context=CreatePrefabUiContext(root,plan);var map=LayoutMap(plan,root,target);var rect=map[c.node];
            for(var t=rect.transform;t!=null;t=t.parent)t.gameObject.SetActive(true);
            LayoutSettle(root);var states=new List<DynamicUiState>{UiState("active-baseline",rect)};var group=rect.GetComponent<LayoutGroup>();
            if(group==null||group.enabled!=c.enabled)throw new InvalidOperationException("Native layout enabled policy differs");
            if(!c.enabled) {
                var original=UiState("disabled-original",rect);rect.gameObject.SetActive(false);rect.gameObject.SetActive(true);LayoutSettle(root);
                var after=UiState("disabled-hide-show",rect);states.Add(after);
                if(original.children.Where((x,i)=>x.position.Where((v,j)=>Math.Abs(v-after.children[i].position[j])>.03f).Any()).Any())throw new InvalidOperationException("Disabled layout changed authored child positions");
            } else if(c.mode=="unity-horizontal-row") {
                var labelSpec=plan.components.Single(s=>s.type=="cc.Label"&&map.ContainsKey(s.node)&&map[s.node].parent==rect);
                var child=map[labelSpec.node];var label=child.GetComponent<TMPro.TextMeshProUGUI>();float oldHeight=child.rect.height;string oldText=label!=null?label.text:null;
                if(label!=null)label.text=oldText+"\n"+oldText;
                else {child.SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical,oldHeight+60);limitations.Add("Source Label not recovered at "+labelSpec.sourceId+"; row probe resizes the existing exact child RectTransform only. Text change remains not_run; no substitute Label was added.");}
                LayoutSettle(root);states.Add(UiState(label!=null?"row-text-change":"row-existing-child-rect-height-change",rect));
                if(child.rect.height<=oldHeight+.03f||rect.rect.height<=states[0].size[1]+.03f)throw new InvalidOperationException("Native row failed to follow changed child height");
                if(label!=null)label.text=oldText;else child.SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical,oldHeight);
                LayoutSettle(root);states.Add(UiState("row-restore",rect));
                if(Math.Abs(rect.rect.height-states[0].size[1])>.03f)throw new InvalidOperationException("Native row restore differs");
            } else {
                var grid=rect.GetComponent<GridLayoutGroup>();var added=new List<GameObject>();
                var inactive=rect.Cast<Transform>().FirstOrDefault(t=>!t.gameObject.activeSelf);
                for(int i=0;i<12;i++) {
                    var go=key=="inactive-exact-template"&&inactive!=null?UnityEngine.Object.Instantiate(inactive.gameObject):new GameObject("OwnedGridProbe",typeof(RectTransform));
                    go.transform.SetParent(rect,false);go.SetActive(true);added.Add(go);
                }
                LayoutSettle(root);states.Add(UiState("add-active-items",rect));
                foreach(var go in added)if((((RectTransform)go.transform).rect.size-grid.cellSize).sqrMagnitude>.001f)throw new InvalidOperationException("Unity grid did not assign declared cell size");
                foreach(var go in added)go.SetActive(false);LayoutSettle(root);states.Add(UiState("hide-added-items",rect));
                if((rect.rect.size-new Vector2(states[0].size[0],states[0].size[1])).sqrMagnitude>.001f)throw new InvalidOperationException("Hide did not restore native extent");
                foreach(var go in added)go.SetActive(true);LayoutSettle(root);states.Add(UiState("show-added-items",rect));
                var positions=added.Select(go=>go.transform.localPosition).ToArray();
                var constraint=rect.GetComponent<NativeRectConstraints>();if(constraint!=null)constraint.enabled=false;
                float probeWidth=grid.padding.horizontal+2*grid.cellSize.x+grid.spacing.x;
                if(Math.Abs(rect.rect.width-probeWidth)<.1f)probeWidth+=grid.cellSize.x+grid.spacing.x;
                rect.SetSizeWithCurrentAnchors(RectTransform.Axis.Horizontal,probeWidth);
                LayoutSettle(root);states.Add(UiState("resize-native-container",rect));
                if(!added.Where((go,i)=>(go.transform.localPosition-positions[i]).sqrMagnitude>.001f).Any())throw new InvalidOperationException("Native grid did not reflow after width change");
                foreach(var go in added)UnityEngine.Object.DestroyImmediate(go);
                foreach(Transform child in rect)child.gameObject.SetActive(false);
                LayoutSettle(root);states.Add(UiState("no-active-items",rect));
                if(c.fitVertical&&Math.Abs(rect.rect.height-grid.padding.vertical)>.03f)throw new InvalidOperationException("Empty native content did not collapse to padding");
            }
            return new DynamicUiResult{sourceId=c.sourceId,type=key,status="native-state-changes-passed",states=states.ToArray()};
        } finally {
            if(context!=null){if(root!=null)root.transform.SetParent(null,false);ReleasePrefabUiContext(context);UnityEngine.Object.DestroyImmediate(context);}
            if(root!=null)PrefabUtility.UnloadPrefabContents(root);
        }
    }
    public static void ReplaceAuditedLayouts() {
        var result=new LayoutPatchResult{status="failed",unityVersion=Application.unityVersion};var rows=new List<LayoutPatchAssetResult>();var probes=new List<DynamicUiResult>();var limitations=new List<string>();
        try {
            layoutPatchClock=System.Diagnostics.Stopwatch.StartNew();layoutPatch=JsonUtility.FromJson<LayoutPatchPlan>(File.ReadAllText(AnalysisFile("Plans","layout-patch-plan.json")));
            if(Application.unityVersion!="6000.6.2f1"||layoutPatch.budgetSeconds<1||layoutPatch.budgetSeconds>900||layoutPatch.targets.Length!=50)throw new InvalidOperationException("Exact native subset/window contract differs");
            result.planSha256=Hash(AnalysisFile("Plans","layout-patch-plan.json"));LayoutPatchCheck();
            result.sourceRuntimeTypeAbsent=!AppDomain.CurrentDomain.GetAssemblies().Any(a=>a.GetType("NativeFlowLayoutGroup",false)!=null);
            if(!result.sourceRuntimeTypeAbsent||Hash(Paths.plan)!=layoutPatch.targetImportPlanSha256)throw new InvalidOperationException("Runtime type retired or import plan binding differs");
            var plan=JsonUtility.FromJson<Plan>(File.ReadAllText(Paths.plan));var specs=plan.components.ToDictionary(c=>c.sourceId);var groups=new HashSet<string>();
            LayoutPatchResult prior=null;
            if(layoutPatch.reusedAssets>0) {
                if(string.IsNullOrEmpty(layoutPatch.priorReadbackPath)||!(layoutPatch.priorReadbackPath.StartsWith("Analysis/Readback/layout-patch-history/",StringComparison.Ordinal)||layoutPatch.priorReadbackPath.StartsWith("Analysis/layout-patch-history/",StringComparison.Ordinal))||layoutPatch.priorReadbackPath.Contains("..")||Hash(layoutPatch.priorReadbackPath)!=layoutPatch.priorReadbackSha256)throw new InvalidOperationException("Previous saved native evidence binding differs");
                prior=JsonUtility.FromJson<LayoutPatchResult>(File.ReadAllText(layoutPatch.priorReadbackPath));
                if(!prior.sourceRuntimeTypeAbsent)throw new InvalidOperationException("Previous production runtime type was not retired");
            }
            EditorSceneManager.OpenScene(BootstrapPath,OpenSceneMode.Single);Application.logMessageReceived+=LayoutPatchLog;
            foreach(var target in layoutPatch.targets.OrderBy(t=>t.aggregate)) {
                LayoutPatchCheck();if(!target.path.StartsWith("Assets/",StringComparison.Ordinal)||target.path.Contains("..")||Hash(target.path)!=(target.reusedPriorEvidence?target.convertedSha256:target.sha256)||AssetDatabase.AssetPathToGUID(target.path)!=target.guid)throw new InvalidOperationException("Frozen or previously saved target identity changed: "+target.path);
                if(target.reusedPriorEvidence) {
                    if(prior==null)throw new InvalidOperationException("Missing prior saved asset evidence");
                    var reused=prior.assets.Single(a=>a.path==target.path);
                    if((reused.status!="saved-reopened-identity-and-geometry-verified"&&reused.status!="reused-prior-saved-native-evidence")||reused.afterSha256!=target.convertedSha256||reused.beforeSha256!=target.sha256||reused.guid!=target.guid||reused.missingAfter!=0||reused.mappings.Length!=target.cases.Length)throw new InvalidOperationException("Previous saved native asset proof differs");
                    reused.reusedPriorEvidence=true;reused.priorReadbackSha256=layoutPatch.priorReadbackSha256;reused.status="reused-prior-saved-native-evidence";rows.Add(reused);result.reusedAssets++;
                    if(!target.aggregate)foreach(var c in target.cases){string key;if(LayoutProbeSelected(c,target,groups,out key)){probes.Add(LayoutProbe(plan,target,c,key,limitations));groups.Add(key);}}
                    continue;
                }
                var row=new LayoutPatchAssetResult{sourceId=target.sourceId,path=target.path,guid=target.guid,beforeSha256=target.sha256,status="started"};rows.Add(row);
                GameObject root=null,context=null;
                try {
                    root=PrefabUtility.LoadPrefabContents(target.path);var map=LayoutMap(plan,root,target);row.missingBefore=LayoutMissing(root);
                    if(row.missingBefore!=target.cases.Length)throw new InvalidOperationException("Unexpected missing scripts outside audited layout slots");
                    foreach(var c in target.cases) {
                        var go=map[c.node].gameObject;
                        if(GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(go)!=1||go.GetComponent<LayoutGroup>()!=null||go.GetComponents<ContentSizeFitter>().Length>1)throw new InvalidOperationException("Audited missing slot differs: "+c.sourceId);
                        GameObjectUtility.RemoveMonoBehavioursWithMissingScript(go);ConfigureNativeGrid(go,specs[c.sourceId]);
                    }
                    context=CreatePrefabUiContext(root,plan);LayoutSettle(root);
                    foreach(var expected in target.baseline)LayoutCompare(expected,map[expected.sourceId]);row.geometryNodes=target.baseline.Length;
                    row.missingAfter=LayoutMissing(root);if(row.missingAfter!=0)throw new InvalidOperationException("Missing script remains after replacement");
                    root.transform.SetParent(null,false);ReleasePrefabUiContext(context);UnityEngine.Object.DestroyImmediate(context);context=null;
                    bool saved;var asset=PrefabUtility.SaveAsPrefabAsset(root,target.path,out saved);if(!saved||asset==null)throw new InvalidOperationException("Incremental Prefab save failed");
                } finally {if(context!=null){if(root!=null)root.transform.SetParent(null,false);ReleasePrefabUiContext(context);UnityEngine.Object.DestroyImmediate(context);}if(root!=null)PrefabUtility.UnloadPrefabContents(root);}
                var persistent=LayoutMap(plan,AssetDatabase.LoadAssetAtPath<GameObject>(target.path),target);
                foreach(var identity in target.identities) {
                    var rect=persistent[identity.sourceId];if(LayoutId(rect.gameObject,target.guid)!=identity.gameObjectFileId||LayoutId(rect,target.guid)!=identity.transformFileId)throw new InvalidOperationException("Stable GameObject/RectTransform identity changed: "+identity.sourceId);
                }
                row.identityNodes=target.identities.Length;var mappings=new List<LayoutPatchMapping>();
                foreach(var c in target.cases) {
                    var go=persistent[c.node].gameObject;var group=go.GetComponent<LayoutGroup>();var fitter=go.GetComponent<ContentSizeFitter>();
                    if(group==null||group.enabled!=c.enabled||go.GetComponents<LayoutGroup>().Length!=1||c.fitVertical&&(fitter==null||fitter.enabled!=c.enabled))throw new InvalidOperationException("Saved native layout/fitter configuration differs");
                    mappings.Add(new LayoutPatchMapping{sourceId=c.sourceId,node=c.node,oldComponentFileId=c.oldComponentFileId,newComponentFileId=LayoutId(group,target.guid),nativeType=group.GetType().FullName,scriptGuid=AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(MonoScript.FromMonoBehaviour(group))),fitterFileId=fitter!=null?LayoutId(fitter,target.guid):null,enabled=group.enabled});
                }
                row.mappings=mappings.ToArray();
                root=null;context=null;
                try {
                    root=PrefabUtility.LoadPrefabContents(target.path);context=CreatePrefabUiContext(root,plan);LayoutSettle(root);var map=LayoutMap(plan,root,target);
                    foreach(var expected in target.baseline)LayoutCompare(expected,map[expected.sourceId]);
                    if(LayoutMissing(root)!=0||AssetDatabase.AssetPathToGUID(target.path)!=target.guid)throw new InvalidOperationException("Saved/reopened Prefab identity or script closure differs");
                } finally {if(context!=null){if(root!=null)root.transform.SetParent(null,false);ReleasePrefabUiContext(context);UnityEngine.Object.DestroyImmediate(context);}if(root!=null)PrefabUtility.UnloadPrefabContents(root);}
                row.afterSha256=Hash(target.path);row.status="saved-reopened-identity-and-geometry-verified";
                if(!target.aggregate)foreach(var c in target.cases){string key;if(LayoutProbeSelected(c,target,groups,out key)){probes.Add(LayoutProbe(plan,target,c,key,limitations));groups.Add(key);}}
            }
            LayoutPatchCheck();result.legacyReferencesAbsent=!Directory.GetFiles("Assets","*",SearchOption.AllDirectories).Where(p=>new[]{".prefab",".unity",".asset",".anim",".controller"}.Contains(Path.GetExtension(p))).Any(p=>File.ReadAllText(p).Contains(layoutPatch.flowScriptGuid));
            if(!result.legacyReferencesAbsent||groups.Count!=6||result.reusedAssets!=layoutPatch.reusedAssets)throw new InvalidOperationException("Runtime closure, reuse count or representative native behavior coverage incomplete");
            result.status="completed";
        } catch(Exception error){result.reason=error.GetType().Name+": "+error.Message;Debug.LogException(error);}
        finally {Application.logMessageReceived-=LayoutPatchLog;result.assets=rows.ToArray();result.probes=probes.ToArray();result.limitations=limitations.ToArray();Directory.CreateDirectory("Analysis/Readback");File.WriteAllText(AnalysisFile("Readback","layout-patch-readback.json"),JsonUtility.ToJson(result,true));EditorApplication.Exit(result.status=="completed"?0:1);}
    }
}
