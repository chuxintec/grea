// Editor-only incremental finish: reuse existing native assets, never rebuild textures/Prefabs.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static partial class MonkeyImporter
{
    [Serializable] public class BulkSceneSpec {public string sourceId,root,path,status,reason;public string[] nodes;public int nodeCount;}
    [Serializable] public class BulkFinishPlan {public string inputPlanSha256,candidatePrefabSha256,priorReadbackSha256,deadlineUtc;public int budgetSeconds;public BulkSceneSpec[] scenes;public string[] fontSourceIds;}
    [Serializable] public class BulkObjectIdentity {public string sourceId,scenePath,sceneGuid,gameObjectFileId,transformFileId;}
    [Serializable] public class BulkSceneResult {public string sourceId,path,guid,status,reason;public int sourceNodes,missingScripts,externalReferencesRemapped;public bool savedReopened;public BulkObjectIdentity[] objects;}
    [Serializable] public class BulkFontEvidence {public string sourceId,fontGuid,text,prefabPath,prefabSha256,status;public bool autoSizing,allCharactersPresent,prefabUnchanged;public float requestedFontSize,fontSizeMin,fontSizeMax,actualFontSize;}
    [Serializable] public class BulkFinishResult {public int schemaVersion=1;public string status,unityVersion,inputPlanSha256,candidatePrefabSha256,priorReadbackSha256,method="MonkeyImporter.FinishBulkBatch";public BulkSceneResult[] scenes;public BulkFontEvidence[] fonts;public bool textureOrPrefabReimport=false;}
    static BulkFinishPlan bulkPlan;static System.Diagnostics.Stopwatch bulkClock;static string bulkError;
    static void BulkCheck() {if(bulkError!=null)throw new InvalidOperationException("Engine error: "+bulkError);if(bulkClock.Elapsed.TotalSeconds>bulkPlan.budgetSeconds||DateTime.UtcNow>=DateTime.Parse(bulkPlan.deadlineUtc,null,DateTimeStyles.AdjustToUniversal|DateTimeStyles.AssumeUniversal))throw new TimeoutException("Bulk finish deadline");}
    static void BulkError(string message,string stack,LogType type) {if(type==LogType.Error||type==LogType.Exception||type==LogType.Assert)bulkError="see private Editor log";}
    static void BulkCopyRect(RectTransform source,RectTransform target) {target.anchorMin=source.anchorMin;target.anchorMax=source.anchorMax;target.pivot=source.pivot;target.sizeDelta=source.sizeDelta;target.anchoredPosition3D=source.anchoredPosition3D;target.localScale=source.localScale;target.localRotation=source.localRotation;}
    static GameObject BulkCanvasShell(GameObject source,out RectTransform design) {
        var root=new GameObject("RecoveredSourceCanvas",typeof(RectTransform),typeof(Canvas),typeof(UnityEngine.UI.CanvasScaler),typeof(UnityEngine.UI.GraphicRaycaster));root.layer=source.layer;BulkCopyRect(source.GetComponent<RectTransform>(),root.GetComponent<RectTransform>());
        var old=source.GetComponent<Canvas>();var canvas=root.GetComponent<Canvas>();canvas.renderMode=old.renderMode;canvas.planeDistance=old.planeDistance;canvas.sortingOrder=old.sortingOrder;canvas.sortingLayerID=old.sortingLayerID;canvas.overrideSorting=old.overrideSorting;canvas.additionalShaderChannels=old.additionalShaderChannels;canvas.pixelPerfect=old.pixelPerfect;
        var a=source.GetComponent<UnityEngine.UI.CanvasScaler>();var b=root.GetComponent<UnityEngine.UI.CanvasScaler>();b.uiScaleMode=a.uiScaleMode;b.referencePixelsPerUnit=a.referencePixelsPerUnit;b.scaleFactor=a.scaleFactor;b.referenceResolution=a.referenceResolution;b.screenMatchMode=a.screenMatchMode;b.matchWidthOrHeight=a.matchWidthOrHeight;b.physicalUnit=a.physicalUnit;b.fallbackScreenDPI=a.fallbackScreenDPI;b.defaultSpriteDPI=a.defaultSpriteDPI;b.dynamicPixelsPerUnit=a.dynamicPixelsPerUnit;
        var oldRay=source.GetComponent<UnityEngine.UI.GraphicRaycaster>();var ray=root.GetComponent<UnityEngine.UI.GraphicRaycaster>();ray.ignoreReversedGraphics=oldRay.ignoreReversedGraphics;ray.blockingObjects=oldRay.blockingObjects;ray.blockingMask=oldRay.blockingMask;
        design=new GameObject("DesignRoot",typeof(RectTransform)).GetComponent<RectTransform>();design.SetParent(root.transform,false);BulkCopyRect((RectTransform)source.transform.Find("DesignRoot"),design);return root;
    }
    static int BulkSettleNativeLayout(GameObject root) {
        var groups=root.GetComponentsInChildren<UnityEngine.UI.LayoutGroup>(true).Where(g=>g.isActiveAndEnabled).Reverse().ToArray();
        var fitters=root.GetComponentsInChildren<UnityEngine.UI.ContentSizeFitter>(true).Where(f=>f.isActiveAndEnabled).ToArray();
        var constraints=root.GetComponentsInChildren<NativeRectConstraints>(true).Where(f=>f.isActiveAndEnabled).ToArray();
        if(groups.Length==0&&fitters.Length==0&&constraints.Length==0)return 0;
        var controllers=groups.Select(g=>(RectTransform)g.transform).Concat(fitters.Select(f=>(RectTransform)f.transform)).Distinct().ToArray();
        var rects=root.GetComponentsInChildren<RectTransform>(true);
        Func<RectTransform,Vector4> value=r=>new Vector4(r.rect.width,r.rect.height,r.localPosition.x,r.localPosition.y);
        for(int pass=0;pass<8;pass++) {
            BulkCheck();
            var before=rects.Select(value).ToArray();
            // DesignRoot is not an ILayoutController: forcing only that root is
            // a no-op. Resolve actual native groups, children before parents.
            foreach(var constraint in constraints)constraint.Refresh();
            foreach(var label in root.GetComponentsInChildren<TMPro.TextMeshProUGUI>(true).Where(l=>l.isActiveAndEnabled))label.ForceMeshUpdate();
            foreach(var controller in controllers)UnityEngine.UI.LayoutRebuilder.ForceRebuildLayoutImmediate(controller);
            Canvas.ForceUpdateCanvases();
            if(rects.Select((r,i)=>(value(r)-before[i]).sqrMagnitude).All(d=>d<1e-10f))return pass+1;
        }
        throw new InvalidOperationException("NATIVE_LAYOUT_DID_NOT_SETTLE");
    }
    public static void FinishBulkBatch() {
        var result=new BulkFinishResult {status="failed",unityVersion=Application.unityVersion,scenes=new BulkSceneResult[0],fonts=new BulkFontEvidence[0]};
        var scenes=new List<BulkSceneResult>();var fonts=new List<BulkFontEvidence>();
        try {
            bulkClock=System.Diagnostics.Stopwatch.StartNew();bulkPlan=JsonUtility.FromJson<BulkFinishPlan>(File.ReadAllText(AnalysisFile("Plans","bulk-finish-plan.json")));
            if(Application.unityVersion!="6000.6.2f1"||bulkPlan.budgetSeconds<1||bulkPlan.budgetSeconds>1500)throw new InvalidOperationException("Exact Editor/window contract differs");
            Application.logMessageReceived+=BulkError;
            if(Hash(Paths.plan)!=bulkPlan.inputPlanSha256||Hash(PrefabPath)!=bulkPlan.candidatePrefabSha256||Hash(AnalysisFile("Readback","editor-readback.json"))!=bulkPlan.priorReadbackSha256)throw new InvalidOperationException("Frozen native inputs changed");
            result.inputPlanSha256=bulkPlan.inputPlanSha256;result.candidatePrefabSha256=bulkPlan.candidatePrefabSha256;result.priorReadbackSha256=bulkPlan.priorReadbackSha256;
            var plan=JsonUtility.FromJson<Plan>(File.ReadAllText(Paths.plan));var old=JsonUtility.FromJson<Readback>(File.ReadAllText(AnalysisFile("Readback","editor-readback.json")));
            // A fresh batch Editor starts with an untitled scene. Use the existing tiny saved bootstrap as context.
            EditorSceneManager.OpenScene(Paths.bootstrap,OpenSceneMode.Single);
            var nodeSpecs=plan.nodes.ToDictionary(n=>n.sourceId);var byPrefab=(plan.sourcePrefabs??new SourcePrefabSpec[0]).ToDictionary(p=>p.sourceId);var fontGuids=old.fonts.ToDictionary(f=>f.id,f=>f.guid);
            foreach(var group in plan.components.Where(c=>bulkPlan.fontSourceIds.Contains(c.sourceId)).GroupBy(c=>c.sourceId.Split('#')[0])) {
                BulkCheck();var spec=byPrefab[group.Key];var before=Hash(spec.path);var contents=PrefabUtility.LoadPrefabContents(spec.path);GameObject context=null;
                try {
                    context=CreatePrefabUiContext(contents,plan);BulkSettleNativeLayout(contents);var mapped=SavedNodeMap(plan.nodes,contents,spec,nodeSpecs);
                    foreach(var c in group) {
                        var rect=mapped[c.node];var label=rect.GetComponent<TMPro.TextMeshProUGUI>();var measured=ReadSavedLabel(c,rect,plan.bitmapFonts.Any(b=>b.id==c.font));
                        bool good=c.overflow==2&&label.enableAutoSizing&&Math.Abs(label.fontSizeMax-c.fontSize)<.001f&&label.fontSizeMin>0&&label.fontSizeMin<=label.fontSizeMax&&measured.fontSize>=label.fontSizeMin-.001f&&measured.fontSize<=label.fontSizeMax+.001f&&measured.fontGuid==fontGuids[c.font]&&measured.text==c.text&&measured.allCharactersPresent;
                        fonts.Add(new BulkFontEvidence {sourceId=c.sourceId,fontGuid=measured.fontGuid,text=measured.text,prefabPath=spec.path,prefabSha256=before,requestedFontSize=c.fontSize,fontSizeMin=label.fontSizeMin,fontSizeMax=label.fontSizeMax,actualFontSize=measured.fontSize,autoSizing=label.enableAutoSizing,allCharactersPresent=measured.allCharactersPresent,status=good?"configuration-verified":"failed"});
                    }
                }finally {if(context!=null){contents.transform.SetParent(null,false);typeof(MonkeyImporter).GetMethod("ReleasePrefabUiContext",System.Reflection.BindingFlags.Static|System.Reflection.BindingFlags.NonPublic)?.Invoke(null,new object[]{context});UnityEngine.Object.DestroyImmediate(context);}PrefabUtility.UnloadPrefabContents(contents);}
                bool unchanged=Hash(spec.path)==before;foreach(var f in fonts.Where(f=>f.prefabPath==spec.path))f.prefabUnchanged=unchanged;
                if(!unchanged)throw new InvalidOperationException("Read-only font audit changed a source Prefab");
            }
            foreach(var spec in bulkPlan.scenes) {
                BulkCheck();if(spec.status=="excluded"){scenes.Add(new BulkSceneResult {sourceId=spec.sourceId,status="excluded",reason=spec.reason,sourceNodes=spec.nodeCount});continue;}
                var row=new BulkSceneResult {sourceId=spec.sourceId,path=spec.path,sourceNodes=spec.nodeCount,status="failed"};scenes.Add(row);Scene scene=default(Scene);GameObject content=null;
                try {
                    if(!spec.path.StartsWith("Assets/",StringComparison.Ordinal)||spec.path.Contains("..")||File.Exists(spec.path))throw new InvalidOperationException("Source Scene output is unsafe or already exists");
                    Directory.CreateDirectory(Path.GetDirectoryName(spec.path));content=PrefabUtility.LoadPrefabContents(PrefabPath);
                    scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Additive);var all=SavedNodeMap(plan.nodes,content);RectTransform design;var clone=BulkCanvasShell(content,out design);SceneManager.MoveGameObjectToScene(clone,scene);var root=UnityEngine.Object.Instantiate(all[spec.root].gameObject,design,false).GetComponent<RectTransform>();
                    var selected=new HashSet<string>(spec.nodes);var reverse=all.ToDictionary(x=>x.Value.gameObject,x=>x.Key);var local=SavedNodeMap(plan.nodes,root.gameObject,new SourcePrefabSpec {root=spec.root,nodes=spec.nodes,nodeCount=spec.nodeCount},nodeSpecs);
                    // Map cross-graph references to exact persistent Prefab objects before removing unrelated roots.
                    var persistent=new Dictionary<string,Dictionary<string,RectTransform>>();
                    foreach(var component in root.GetComponentsInChildren<Component>(true)) {
                        if(component==null)continue;var serialized=new SerializedObject(component);var property=serialized.GetIterator();bool changed=false;
                        while(property.Next(true)) {
                            if(property.propertyType!=SerializedPropertyType.ObjectReference)continue;var value=property.objectReferenceValue;if(value==null||EditorUtility.IsPersistent(value))continue;
                            GameObject go=value as GameObject;if(go==null&&value is Component)go=((Component)value).gameObject;if(go==null)continue;
                            string id;GameObject targetGo;
                            if(!reverse.TryGetValue(go,out id)) {
                                if(go==content)targetGo=clone;
                                else if(go.transform==content.transform.Find("DesignRoot"))targetGo=design.gameObject;
                                else continue;
                            } else if(selected.Contains(id))targetGo=local[id].gameObject;
                            else {
                                string owner=id.Split('#')[0];SourcePrefabSpec target;
                                if(!byPrefab.TryGetValue(owner,out target))throw new InvalidOperationException("Cross-scene source reference has no persistent Prefab: "+id);
                                if(!persistent.ContainsKey(owner))persistent.Add(owner,SavedNodeMap(plan.nodes,AssetDatabase.LoadAssetAtPath<GameObject>(target.path),target,nodeSpecs));
                                targetGo=persistent[owner][id].gameObject;
                            }
                            UnityEngine.Object replacement=targetGo;
                            if(value is Component){var original=(Component)value;var originals=go.GetComponents(original.GetType());var targets=targetGo.GetComponents(original.GetType());int ordinal=Array.IndexOf(originals,original);if(ordinal<0||targets.Length!=originals.Length)throw new InvalidOperationException("Persistent component ordinal differs");replacement=targets[ordinal];}
                            property.objectReferenceValue=replacement;changed=true;row.externalReferencesRemapped++;
                        }
                        if(changed)serialized.ApplyModifiedPropertiesWithoutUndo();
                    }
                    clone.name="RecoveredSourceCanvas";var events=new GameObject("EventSystem",typeof(UnityEngine.EventSystems.EventSystem),typeof(UnityEngine.EventSystems.StandaloneInputModule));SceneManager.MoveGameObjectToScene(events,scene);
                    if(!EditorSceneManager.SaveScene(scene,spec.path))throw new InvalidOperationException("Source Scene save failed");AssetDatabase.ImportAsset(spec.path,ImportAssetOptions.ForceSynchronousImport);EditorSceneManager.CloseScene(scene,true);
                    scene=EditorSceneManager.OpenScene(spec.path,OpenSceneMode.Additive);var wrapper=scene.GetRootGameObjects().Single(g=>g.name=="RecoveredSourceCanvas");var savedRoot=wrapper.transform.Find("DesignRoot").GetChild(0).gameObject;
                    var mapping=SavedNodeMap(plan.nodes,savedRoot,new SourcePrefabSpec {root=spec.root,nodes=spec.nodes,nodeCount=spec.nodeCount},nodeSpecs);string guid=AssetDatabase.AssetPathToGUID(spec.path);
                    row.missingScripts=scene.GetRootGameObjects().SelectMany(g=>g.GetComponentsInChildren<Transform>(true)).Sum(t=>GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject));
                    var identities=new List<BulkObjectIdentity>();foreach(var pair in mapping){var go=GlobalObjectId.GetGlobalObjectIdSlow(pair.Value.gameObject);var tr=GlobalObjectId.GetGlobalObjectIdSlow(pair.Value);if(go.assetGUID.ToString()!=guid||tr.assetGUID.ToString()!=guid||go.targetObjectId==0||tr.targetObjectId==0)throw new InvalidOperationException("Saved Scene object identity unavailable");identities.Add(new BulkObjectIdentity {sourceId=pair.Key,scenePath=spec.path,sceneGuid=guid,gameObjectFileId=go.targetObjectId.ToString(CultureInfo.InvariantCulture),transformFileId=tr.targetObjectId.ToString(CultureInfo.InvariantCulture)});}
                    row.guid=guid;row.objects=identities.ToArray();row.savedReopened=true;row.status=row.missingScripts==0?"saved-reopened":"missing-scripts";
                }catch(Exception error){row.reason=error.GetType().Name+": "+error.Message;break;}
                finally {if(scene.IsValid()&&scene.isLoaded)EditorSceneManager.CloseScene(scene,true);if(content!=null)PrefabUtility.UnloadPrefabContents(content);}
            }
            BulkCheck();result.status=scenes.All(s=>s.status=="excluded"||s.status=="saved-reopened")&&fonts.All(f=>f.status=="configuration-verified"&&f.prefabUnchanged)?"completed":"partial";
        }catch(Exception error){result.status="failed";Debug.LogException(error);}
        finally {Application.logMessageReceived-=BulkError;result.scenes=scenes.ToArray();result.fonts=fonts.ToArray();Directory.CreateDirectory("Analysis/Readback");File.WriteAllText(AnalysisFile("Readback","bulk-finish-readback.json"),JsonUtility.ToJson(result,true));EditorApplication.Exit(result.status=="completed"?0:1);}
    }
}
