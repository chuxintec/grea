// beaver native Unity 6 companion. Editor-only, explicit versioned jobs, no shell/eval.
#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Build.Reporting;

public static class BeaverNative {
    static string JobPath() {
        var encoded=Environment.GetEnvironmentVariable("BEAVER_NATIVE_JOB_BASE64");
        if(String.IsNullOrEmpty(encoded)||encoded.Length>65536)throw new Exception("Explicit ASCII-encoded native job required");
        return new System.Text.UTF8Encoding(false,true).GetString(Convert.FromBase64String(encoded));
    }

    [Serializable] public class Node {
        public string id, name, parent, kind, text, spriteGuid;
        public long spriteLocalId;
        public float x,y,width,height,fontSize;
        public float[] color;
    }
    [Serializable] public class Edit {
        public string nodePath, component, property, kind, targetNode, targetComponent, assetGuid;
        public long localId;
        public string value;
    }
    [Serializable] public class Job {
        public int schemaVersion,width,height,durationSeconds,maxSize;
        public string operation, targetRoot, stage, mode, planSha256, sourceSha256;
        public string prefabPath, scenePath, fontAssetPath, sourceFontPath, tmpSettingsPath, productName;
        public string[] scenes;
        public Node[] nodes;
        public Edit[] edits;
        public Move[] moves;
        public FolderMoveManifest[] folderMoveManifest;
        public RetireItem[] retireManifest;
        public RetireFolder[] folderRetireManifest;
        public string[] sourceDirectoryPaths;
        public ProtectedItem[] protectedManifest;
        public ResourceRetirement[] resources;
        public string assetPath;
        public float pixelsPerUnit;
        public float[] pivot;
        public bool alphaIsTransparency;
    }
    [Serializable] public class Move { public string source,target; }
    [Serializable] public class MoveRow { public string source,target,guid; public string[] localIds; }
    [Serializable] public class FolderMoveManifest { public string source,target; public long bytes; public MoveEntry[] entries; }
    [Serializable] public class MoveEntry { public string source,target,kind,sha256; public long bytes; }
    [Serializable] public class RetireItem { public string path,role,reason,sourceEvidence,sha256,metaPath,metaSha256,guid,identityPolicy; public long bytes,metaBytes; public bool hasSourceIdentityEvidence; public SourceIdentityEvidence sourceIdentityEvidence; }
    [Serializable] public class RetireFolder { public string path,role,reason,sourceEvidence,metaPath,metaSha256,guid,directorySetSha256; public long metaBytes; public CallerReview callerReview; }
    [Serializable] public class CallerReview { public string reference,sourceSha256,directorySetSha256; public DynamicPathReview dynamicPathReview; }
    [Serializable] public class DynamicPathReview { public string status,reason,evidence; }
    [Serializable] public class SourceIdentityEvidence { public string snapshotPath,snapshotSha256,assetPath,targetRecordSha256; public CollectorAssetRecord targetRecord; public CollectorInputState[] targetInputs; }
    [Serializable] public class CollectorAssetRecord { public string path,guid,status,identityStatus,error; public int objectCount; public long[] localIds; public string[] types; }
    [Serializable] public class CollectorInputState { public string path,sha256; public long bytes; }
    [Serializable] public class ProtectedItem { public string path,sha256,metaPath,metaSha256,guid; public long bytes,metaBytes; }
    [Serializable] public class ResourceRetirement { public string key,path,guid,reason,sourceEvidence; }
    [Serializable] public class RetireIdentity { public string path,guid,identityPolicy,identityStatus,sourceEvidenceSnapshotSha256,sourceEvidenceTargetRecordSha256; public int nativeObjectCount; public string[] localIds; }
    [Serializable] public class RetiredFolderIdentity { public string path,guid,identityStatus; public long localId; }
    [Serializable] public class ProtectedIdentity { public string path,guid,sha256,metaSha256; public string[] localIds; }
    [Serializable] public class DependencyClosure { public string root; public string[] paths; }
    [Serializable] public class Row {
        public string path,parent,guid;
        public long localId;
        public string[] components;
        public float width,height;
        public bool active,interactable,raycastTarget,fontPresent;
        public string text,spriteGuid;
        public long spriteLocalId;
        public string spriteTexturePath;
        public float spritePixelsPerUnit;
        public Vector2 spritePivot;
        public Rect spriteRect;
    }
    [Serializable] public class Report {
        public string status,operation,mode,planSha256,sourceSha256,error,prefabGuid;
        public List<Row> nodes=new List<Row>();
        public int missingScripts,eventSystems,canvasRaycasters,bindingChecks;
        public string buildResult,buildPath;
        public ulong buildBytes;
        public int buildErrors;
        public List<MoveRow> moves=new List<MoveRow>();
        public List<MoveRow> moveIdentities=new List<MoveRow>();
        public string deleteInProgress;
        public bool resourcesDynamicUseNotProvable;
        public bool folderDynamicPathUseNotProvable;
        public List<string> selectedPaths=new List<string>();
        public List<string> deletedPaths=new List<string>();
        public List<string> recoveredPaths=new List<string>();
        public string folderDeleteInProgress;
        public List<string> deletedFolders=new List<string>();
        public List<string> recoveredFolders=new List<string>();
        public List<string> dependencyPaths=new List<string>();
        public List<DependencyClosure> dependencyClosures=new List<DependencyClosure>();
        public List<RetireIdentity> retiredAssets=new List<RetireIdentity>();
        public List<RetiredFolderIdentity> retiredFolders=new List<RetiredFolderIdentity>();
        public List<ProtectedIdentity> protectedRoots=new List<ProtectedIdentity>();
        public List<ResourceRetirement> resources=new List<ResourceRetirement>();
        public int playFrames,playErrors;
        public double playSeconds;
        public string spriteGuid;
        public long spriteLocalId;
        public float spritePixelsPerUnit;
        public Vector2 spritePivot;
        public Rect spriteRect;
    }
    static Job job;
    static Report report;
    const string PlayKey="Beaver.Native.PlayJob";
    static DateTime playStart;
    static bool playStopping;
    [InitializeOnLoadMethod] static void ResumePlay() {
        var path=SessionState.GetString(PlayKey,"");
        if(String.IsNullOrEmpty(path)||!File.Exists(path))return;
        job=JsonUtility.FromJson<Job>(File.ReadAllText(path));
        report=JsonUtility.FromJson<Report>(File.ReadAllText(Path.Combine(job.stage,"native-"+job.mode+".json")));
        playStart=DateTime.UtcNow;playStopping=false;
        EditorApplication.playModeStateChanged+=PlayState;
        EditorApplication.update+=PlayUpdate;
        Application.logMessageReceived+=PlayLog;
    }
    static void PlayLog(string message,string stack,LogType type) {
        if(type==LogType.Error||type==LogType.Exception||type==LogType.Assert){report.playErrors++;Save();}
    }
    static void PlayState(PlayModeStateChange state) {
        if(state==PlayModeStateChange.EnteredPlayMode){playStart=DateTime.UtcNow;}
        if(state==PlayModeStateChange.EnteredEditMode) {
            SessionState.EraseString(PlayKey);EditorApplication.update-=PlayUpdate;EditorApplication.playModeStateChanged-=PlayState;
            Application.logMessageReceived-=PlayLog;
            report.status=report.playErrors==0&&report.playFrames>0?"verified":"failed";Save();EditorApplication.Exit(report.status=="verified"?0:1);
        }
    }
    static void PlayUpdate() {
        if(!EditorApplication.isPlaying||playStopping)return;
        report.playFrames=Math.Max(report.playFrames,Time.frameCount);report.playSeconds=(DateTime.UtcNow-playStart).TotalSeconds;
        if(report.playSeconds>=job.durationSeconds) {
            playStopping=true;Save();EditorApplication.ExitPlaymode();
        }
    }
    static void Play() {
        EditorSceneManager.OpenScene(job.scenePath,OpenSceneMode.Single);
        SessionState.SetString(PlayKey,JobPath());
        ResumePlay();EditorApplication.EnterPlaymode();
    }
    static void Save() {
        File.WriteAllText(Path.Combine(job.stage,"native-"+job.mode+".json"),JsonUtility.ToJson(report,true));
    }
    static string Full(string relative) {
        if(String.IsNullOrEmpty(relative)||!relative.StartsWith("Assets/",StringComparison.Ordinal)||relative.Contains("\\")||relative.Split('/').Any(p=>p==""||p=="."||p==".."))throw new Exception("Unsafe asset path");
        return Path.Combine(job.targetRoot,relative);
    }
    static string HashFile(string path) {
        using(var stream=File.OpenRead(path)) using(var sha=SHA256.Create()) {
            var bytes=sha.ComputeHash(stream);var result=new System.Text.StringBuilder(bytes.Length*2);
            foreach(var value in bytes)result.Append(value.ToString("x2"));
            return result.ToString();
        }
    }
    static void Folder(string relative) {
        var parent=Path.GetDirectoryName(relative).Replace('\\','/');
        if(parent=="Assets"||AssetDatabase.IsValidFolder(parent))return;
        Folder(parent);
        var grand=Path.GetDirectoryName(parent).Replace('\\','/');
        if(String.IsNullOrEmpty(AssetDatabase.CreateFolder(grand,Path.GetFileName(parent))))throw new Exception("Could not create native folder: "+parent);
    }
    static void NewPath(string path) {
        if(File.Exists(Full(path))||File.Exists(Full(path+".meta")))throw new Exception("Create-only destination occupied: "+path);
        Folder(path);
    }
    static Color ColorFor(Node n,Color fallback) {
        return n.color!=null && n.color.Length==4?new Color(n.color[0],n.color[1],n.color[2],n.color[3]):fallback;
    }
    static UnityEngine.Object Asset(string guid,long id) {
        var path=AssetDatabase.GUIDToAssetPath(guid);
        if(String.IsNullOrEmpty(path))throw new Exception("Asset GUID missing: "+guid);
        foreach(var obj in AssetDatabase.LoadAllAssetsAtPath(path)) {
            string observed;long local;
            if(obj!=null && AssetDatabase.TryGetGUIDAndLocalFileIdentifier(obj,out observed,out local) && observed==guid && local==id)return obj;
        }
        throw new Exception("Asset localID missing: "+guid+":"+id);
    }
    static TMPro.TMP_FontAsset FontAsset() {
        NewPath(job.fontAssetPath);
        var font=AssetDatabase.LoadAssetAtPath<Font>(job.sourceFontPath);
        if(font==null)throw new Exception("Explicit source font missing: "+job.sourceFontPath);
        var asset=TMPro.TMP_FontAsset.CreateFontAsset(font);
        if(asset==null)throw new Exception("Could not generate self-contained TMP font");
        asset.name="BeaverFont";
        AssetDatabase.CreateAsset(asset,job.fontAssetPath);
        foreach(var texture in asset.atlasTextures)if(texture!=null && !EditorUtility.IsPersistent(texture))AssetDatabase.AddObjectToAsset(texture,asset);
        if(asset.material!=null && !EditorUtility.IsPersistent(asset.material))AssetDatabase.AddObjectToAsset(asset.material,asset);
        var characters=new String(("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .:-_+"+String.Join("",job.nodes.Where(n=>n.text!=null).Select(n=>n.text))).Distinct().ToArray());
        string missing;
        if(!asset.TryAddCharacters(characters,out missing))throw new Exception("Source font missing required characters: "+missing);
        EditorUtility.SetDirty(asset);AssetDatabase.SaveAssets();
        return asset;
    }
    static void CreateUI() {
        if(Shader.Find("TextMeshPro/Mobile/Distance Field")==null)throw new Exception("UI_TMP_PROVIDER_MISSING: TMP Essentials shaders must be explicitly initialized in the project before UI generation");
        NewPath(job.prefabPath);NewPath(job.scenePath);
        if(!String.IsNullOrEmpty(job.tmpSettingsPath)) {
            if(Resources.Load<TMPro.TMP_Settings>("TMP Settings")!=null)throw new Exception("Existing TMP settings must be reused, not duplicated");
            NewPath(job.tmpSettingsPath);
            AssetDatabase.CreateAsset(ScriptableObject.CreateInstance<TMPro.TMP_Settings>(),job.tmpSettingsPath);
            AssetDatabase.SaveAssets();
        }
        if(TMPro.TMP_Settings.GetSettings()==null)throw new Exception("UI_TMP_SETTINGS_MISSING: explicitly create TMP Settings or supply an existing project resource");
        var font=FontAsset();
        if(!String.IsNullOrEmpty(job.tmpSettingsPath)) {
            var settings=TMPro.TMP_Settings.GetSettings();var serialized=new SerializedObject(settings);
            serialized.FindProperty("m_defaultFontAsset").objectReferenceValue=font;
            serialized.ApplyModifiedPropertiesWithoutUndo();EditorUtility.SetDirty(settings);AssetDatabase.SaveAssets();
        }
        var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        var root=new GameObject("BeaverWindow",typeof(RectTransform),typeof(Canvas),typeof(UnityEngine.UI.CanvasScaler),typeof(UnityEngine.UI.GraphicRaycaster));
        root.GetComponent<Canvas>().renderMode=RenderMode.ScreenSpaceOverlay;
        var scaler=root.GetComponent<UnityEngine.UI.CanvasScaler>();
        scaler.uiScaleMode=UnityEngine.UI.CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution=new Vector2(job.width,job.height);scaler.matchWidthOrHeight=.5f;
        var table=new Dictionary<string,GameObject>();
        foreach(var n in job.nodes) {
            var parent=String.IsNullOrEmpty(n.parent)?root:table[n.parent];
            var go=new GameObject(n.name,typeof(RectTransform));
            go.transform.SetParent(parent.transform,false);
            var rect=go.GetComponent<RectTransform>();
            rect.anchorMin=rect.anchorMax=rect.pivot=new Vector2(.5f,.5f);
            rect.sizeDelta=new Vector2(n.width,n.height);rect.anchoredPosition=new Vector2(n.x,n.y);
            if(n.kind=="text") {
                var text=go.AddComponent<TMPro.TextMeshProUGUI>();
                text.font=font;text.text=n.text ?? "";text.fontSize=n.fontSize>0?n.fontSize:28;
                text.color=ColorFor(n,Color.white);text.alignment=TMPro.TextAlignmentOptions.Center;
                text.raycastTarget=false;
            } else {
                var image=go.AddComponent<UnityEngine.UI.Image>();
                image.color=ColorFor(n,n.kind=="button"?new Color(.15f,.45f,.85f,1):new Color(.08f,.1f,.16f,1));
                image.raycastTarget=n.kind=="button";
                if(!String.IsNullOrEmpty(n.spriteGuid)) {
                    image.sprite=Asset(n.spriteGuid,n.spriteLocalId) as Sprite;
                    if(image.sprite==null)throw new Exception("Image reference is not a Sprite");
                    image.preserveAspect=true;
                }
                if(n.kind=="button") {var button=go.AddComponent<UnityEngine.UI.Button>();button.targetGraphic=image;button.interactable=true;}
                if(n.kind=="list") {
                    var layout=go.AddComponent<UnityEngine.UI.VerticalLayoutGroup>();
                    layout.childControlWidth=false;layout.childControlHeight=false;
                    layout.childForceExpandWidth=false;layout.childForceExpandHeight=false;
                    layout.spacing=12;layout.childAlignment=TextAnchor.MiddleCenter;
                }
            }
            table.Add(n.id,go);
        }
        UnityEngine.UI.LayoutRebuilder.ForceRebuildLayoutImmediate(root.GetComponent<RectTransform>());
        bool success;
        var prefab=PrefabUtility.SaveAsPrefabAsset(root,job.prefabPath,out success);
        if(!success || prefab==null)throw new Exception("Prefab save failed");
        UnityEngine.Object.DestroyImmediate(root);
        PrefabUtility.InstantiatePrefab(prefab,scene);
        new GameObject("EventSystem",typeof(UnityEngine.EventSystems.EventSystem),typeof(UnityEngine.EventSystems.StandaloneInputModule));
        if(!EditorSceneManager.SaveScene(scene,job.scenePath))throw new Exception("Scene save failed");
        AssetDatabase.SaveAssets();
    }
    static Transform Find(GameObject root,string path) {
        var t=String.IsNullOrEmpty(path)?root.transform:root.transform.Find(path);
        if(t==null)throw new Exception("Unknown native node: "+path);
        return t;
    }
    static Component ComponentAt(GameObject root,string nodePath,string type) {
        var go=Find(root,nodePath).gameObject;
        var items=go.GetComponents<Component>().Where(c=>c!=null && c.GetType().FullName==type).ToArray();
        if(items.Length!=1)throw new Exception("Expected one existing component: "+nodePath+":"+type);
        return items[0];
    }
    static void Bind(GameObject root,Edit edit,bool write) {
        var component=ComponentAt(root,edit.nodePath,edit.component);
        var so=new SerializedObject(component);so.Update();
        var p=so.FindProperty(edit.property);
        if(p==null)throw new Exception("Unknown serialized property: "+edit.property);
        if(edit.property=="m_Script"||edit.property=="m_GameObject"||edit.property=="m_Father"||edit.property=="m_Children")throw new Exception("Identity fields cannot be changed");
        if(edit.kind=="string") {
            if(p.propertyType!=SerializedPropertyType.String)throw new Exception("Wrong property type");
            if(write)p.stringValue=edit.value;else if(p.stringValue!=edit.value)throw new Exception("String readback differs");
        } else if(edit.kind=="bool") {
            if(p.propertyType!=SerializedPropertyType.Boolean)throw new Exception("Wrong property type");
            var v=Boolean.Parse(edit.value);if(write)p.boolValue=v;else if(p.boolValue!=v)throw new Exception("Boolean readback differs");
        } else if(edit.kind=="int") {
            if(p.propertyType!=SerializedPropertyType.Integer)throw new Exception("Wrong property type");
            var v=Int32.Parse(edit.value,System.Globalization.CultureInfo.InvariantCulture);if(write)p.intValue=v;else if(p.intValue!=v)throw new Exception("Integer readback differs");
        } else if(edit.kind=="float") {
            if(p.propertyType!=SerializedPropertyType.Float)throw new Exception("Wrong property type");
            var v=Single.Parse(edit.value,System.Globalization.CultureInfo.InvariantCulture);if(Single.IsNaN(v)||Single.IsInfinity(v))throw new Exception("Nonfinite value");
            if(write)p.floatValue=v;else if(p.floatValue!=v)throw new Exception("Float readback differs");
        } else if(edit.kind=="object") {
            if(p.propertyType!=SerializedPropertyType.ObjectReference)throw new Exception("Wrong property type");
            UnityEngine.Object value;
            if(!String.IsNullOrEmpty(edit.assetGuid))value=Asset(edit.assetGuid,edit.localId);
            else if(!String.IsNullOrEmpty(edit.targetComponent))value=ComponentAt(root,edit.targetNode,edit.targetComponent);
            else value=Find(root,edit.targetNode).gameObject;
            if(write)p.objectReferenceValue=value;else if(p.objectReferenceValue!=value)throw new Exception("Reference readback differs");
        } else throw new Exception("Unknown edit kind");
        if(write){so.ApplyModifiedPropertiesWithoutUndo();EditorUtility.SetDirty(component);}
        else report.bindingChecks++;
    }
    static void EditPrefab() {
        var asset=AssetDatabase.LoadAssetAtPath<GameObject>(job.prefabPath);
        if(asset==null)throw new Exception("Prefab missing");
        if(PrefabUtility.GetPrefabAssetType(asset)==PrefabAssetType.Variant)throw new Exception("PREFAB_VARIANT_UNSUPPORTED: edit the base explicitly or use a later override adapter");
        var originalGuid=AssetDatabase.AssetPathToGUID(job.prefabPath);
        var root=PrefabUtility.LoadPrefabContents(job.prefabPath);
        try {
            foreach(var edit in job.edits)Bind(root,edit,true);
            bool saved;PrefabUtility.SaveAsPrefabAsset(root,job.prefabPath,out saved);
            if(!saved)throw new Exception("Edited prefab save failed");
        } finally {PrefabUtility.UnloadPrefabContents(root);}
        if(AssetDatabase.AssetPathToGUID(job.prefabPath)!=originalGuid)throw new Exception("Prefab GUID changed");
    }
    static string NodePath(Transform node,Transform root) {
        if(node==root)return "";
        var parts=new List<string>();
        while(node!=root){parts.Insert(0,node.name);node=node.parent;}
        return String.Join("/",parts);
    }
    static void InspectPrefab() {
        var asset=AssetDatabase.LoadAssetAtPath<GameObject>(job.prefabPath);
        if(asset==null)throw new Exception("Prefab missing");
        report.prefabGuid=AssetDatabase.AssetPathToGUID(job.prefabPath);
        var root=PrefabUtility.LoadPrefabContents(job.prefabPath);
        try {
            Canvas.ForceUpdateCanvases();
            foreach(var t in root.GetComponentsInChildren<Transform>(true)) {
                report.missingScripts+=GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject);
                var rect=t as RectTransform;
                var row=new Row{path=NodePath(t,root.transform),parent=t==root.transform?null:NodePath(t.parent,root.transform),components=t.GetComponents<Component>().Where(c=>c!=null).Select(c=>c.GetType().FullName).ToArray(),active=t.gameObject.activeSelf,width=rect!=null?rect.rect.width:0,height=rect!=null?rect.rect.height:0};
                var persistent=String.IsNullOrEmpty(row.path)?asset.transform:asset.transform.Find(row.path);
                if(persistent==null || !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(persistent,out row.guid,out row.localId))throw new Exception("Saved native node identity missing: "+row.path);
                var button=t.GetComponent<UnityEngine.UI.Button>();
                if(button!=null){row.interactable=button.interactable;row.raycastTarget=button.targetGraphic!=null&&button.targetGraphic.raycastTarget;}
                var text=t.GetComponent<TMPro.TMP_Text>();
                if(text!=null){row.text=text.text;row.fontPresent=text.font!=null;if(!row.fontPresent)throw new Exception("TMP font missing");}
                var image=t.GetComponent<UnityEngine.UI.Image>();
                if(image!=null&&image.sprite!=null){string guid;long id;AssetDatabase.TryGetGUIDAndLocalFileIdentifier(image.sprite,out guid,out id);row.spriteGuid=guid;row.spriteLocalId=id;row.spriteRect=image.sprite.rect;row.spritePixelsPerUnit=image.sprite.pixelsPerUnit;row.spritePivot=image.sprite.pivot;row.spriteTexturePath=AssetDatabase.GetAssetPath(image.sprite.texture);}
                report.nodes.Add(row);
            }
            if(report.missingScripts!=0)throw new Exception("Missing scripts retained; refusing successful validation");
            if(job.operation=="prefab.edit")foreach(var edit in job.edits)Bind(root,edit,false);
        } finally {PrefabUtility.UnloadPrefabContents(root);}
        if(job.operation=="ui.create") {
            if(report.nodes.Count!=job.nodes.Length+1)throw new Exception("Saved node count differs");
            var scene=EditorSceneManager.OpenScene(job.scenePath,OpenSceneMode.Single);
            foreach(var go in scene.GetRootGameObjects()) {
                report.eventSystems+=go.GetComponentsInChildren<UnityEngine.EventSystems.EventSystem>(true).Length;
                report.canvasRaycasters+=go.GetComponentsInChildren<UnityEngine.UI.GraphicRaycaster>(true).Length;
            }
            if(report.eventSystems!=1||report.canvasRaycasters!=1)throw new Exception("Scene interaction prerequisites missing or duplicated");
        }
    }
    static void Build() {
        foreach(var scene in job.scenes)if(AssetDatabase.LoadAssetAtPath<SceneAsset>(scene)==null)throw new Exception("Build scene missing: "+scene);
        var directory=Path.Combine(job.stage,"player");Directory.CreateDirectory(directory);
        var path=Path.Combine(directory,job.productName+".app");
        if(Directory.Exists(path))throw new Exception("Build output exists");
        var result=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=job.scenes,locationPathName=path,target=BuildTarget.StandaloneOSX,options=BuildOptions.None});
        report.buildResult=result.summary.result.ToString();report.buildBytes=result.summary.totalSize;report.buildErrors=result.summary.totalErrors;report.buildPath=path;
        if(result.summary.result!=BuildResult.Succeeded)throw new Exception("Build failed: "+report.buildResult);
    }
    static void SpriteImport(bool write) {
        var importer=AssetImporter.GetAtPath(job.assetPath) as TextureImporter;
        if(importer==null)throw new Exception("Source image has no TextureImporter");
        if(write) {
            importer.textureType=TextureImporterType.Sprite;importer.spriteImportMode=SpriteImportMode.Single;
            importer.spritePixelsPerUnit=job.pixelsPerUnit;importer.spritePivot=new Vector2(job.pivot[0],job.pivot[1]);
            var settings=new TextureImporterSettings();importer.ReadTextureSettings(settings);settings.spriteAlignment=(int)SpriteAlignment.Custom;settings.spritePivot=importer.spritePivot;importer.SetTextureSettings(settings);
            importer.maxTextureSize=job.maxSize;importer.mipmapEnabled=false;importer.alphaIsTransparency=job.alphaIsTransparency;
            importer.textureCompression=TextureImporterCompression.Uncompressed;importer.SaveAndReimport();
        }
        var sprite=AssetDatabase.LoadAssetAtPath<Sprite>(job.assetPath);
        if(sprite==null||importer.spriteImportMode!=SpriteImportMode.Single||importer.textureType!=TextureImporterType.Sprite)throw new Exception("Sprite import readback differs");
        if(importer.spritePixelsPerUnit!=job.pixelsPerUnit||importer.spritePivot!=new Vector2(job.pivot[0],job.pivot[1])||importer.maxTextureSize!=job.maxSize||importer.alphaIsTransparency!=job.alphaIsTransparency)throw new Exception("Sprite importer parameters differ");
        if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(sprite,out report.spriteGuid,out report.spriteLocalId))throw new Exception("Sprite local identity missing");
        report.spritePixelsPerUnit=sprite.pixelsPerUnit;report.spritePivot=sprite.pivot;report.spriteRect=sprite.rect;
    }
    static UnityEngine.Object[] PersistentObjects(string path) {
        var main=AssetDatabase.LoadMainAssetAtPath(path);
        return AssetDatabase.LoadAllAssetsAtPath(path).Concat(main==null?new UnityEngine.Object[0]:new[]{main}).Where(a=>a!=null).Distinct().ToArray();
    }
    static string[] Ids(string path) { return Ids(PersistentObjects(path)); }
    static string[] Ids(UnityEngine.Object[] objects) {
        return objects.Select(a=>{
            string guid;long id;if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(a,out guid,out id))throw new Exception("Missing asset identity");
            return guid+":"+id+":"+a.GetType().FullName;
        }).OrderBy(s=>s,StringComparer.Ordinal).ToArray();
    }
    static void Moves(bool write) {
        var fileMoves=job.moves??new Move[0];var folderMoves=job.folderMoveManifest??new FolderMoveManifest[0];
        // Validate every endpoint and complete manifest before the first move.
        foreach(var move in fileMoves) {
            bool verifying=job.mode=="verify";var expected=verifying?move.target:move.source;var other=verifying?move.source:move.target;
            if(!File.Exists(Full(expected))||!File.Exists(Full(expected+".meta")))throw new Exception("Move source or meta missing: "+expected);
            if(!verifying&&(File.Exists(Full(other))||File.Exists(Full(other+".meta"))||Directory.Exists(Full(other))||AssetDatabase.IsValidFolder(other)))throw new Exception("Move destination occupied: "+other);
        }
        foreach(var manifest in folderMoves) {
            bool verifying=job.mode=="verify";
            var expectedPath=verifying?manifest.target:manifest.source;var otherPath=verifying?manifest.source:manifest.target;
            if(manifest.entries==null||!Directory.Exists(Full(expectedPath))||!File.Exists(Full(expectedPath+".meta")))throw new Exception("Folder source or manifest missing: "+expectedPath);
            if(!verifying&&(Directory.Exists(Full(otherPath))||AssetDatabase.IsValidFolder(otherPath)||File.Exists(Full(otherPath))||File.Exists(Full(otherPath+".meta"))))throw new Exception("Folder destination occupied: "+otherPath);
            foreach(var entry in manifest.entries) {
                var expectedEntry=verifying?entry.target:entry.source;
                if(entry.kind=="folder") {
                    if(!Directory.Exists(Full(expectedEntry)))throw new Exception("Manifest folder missing: "+expectedEntry);
                } else {
                    var source=Full(expectedEntry);
                    if(!File.Exists(source)||HashFile(source)!=entry.sha256||new FileInfo(source).Length!=entry.bytes)throw new Exception("Folder source bytes drifted: "+expectedEntry);
                }
            }
        }
        // Register/create all destination parents before AssetDatabase mutation.
        if(write) {
            foreach(var move in fileMoves)Folder(move.target);
            foreach(var move in folderMoves)Folder(move.target);
        }
        foreach(var move in fileMoves) {
            var row=new MoveRow{source=move.source,target=move.target};
            if(write) {
                row.guid=AssetDatabase.AssetPathToGUID(move.source);row.localIds=Ids(move.source);
                if(String.IsNullOrEmpty(row.guid))throw new Exception("Invalid move source identity");
                report.moves.Add(row);Save();Folder(move.target);
                var error=AssetDatabase.MoveAsset(move.source,move.target);if(error!="")throw new Exception(error);
                if(AssetDatabase.AssetPathToGUID(move.target)!=row.guid||!row.localIds.SequenceEqual(Ids(move.target)))throw new Exception("Move changed GUID/localID");
                Save();
            } else {
                row.guid=AssetDatabase.AssetPathToGUID(move.target);row.localIds=Ids(move.target);report.moves.Add(row);
                if(String.IsNullOrEmpty(row.guid)||File.Exists(Full(move.source)))throw new Exception("Move save/reopen mismatch");
            }
        }
        foreach(var manifest in folderMoves) {
            if(write) {
                var before=FolderIdentities(manifest,false);report.moveIdentities.AddRange(before);Save();
                var error=AssetDatabase.MoveAsset(manifest.source,manifest.target);if(error!="")throw new Exception(error);
                var after=FolderIdentities(manifest,true);
                if(!SameIdentities(before,after))throw new Exception("Folder move changed GUID/localID or path mapping: "+manifest.source);
                Save();
            } else {
                var observed=FolderIdentities(manifest,true);report.moveIdentities.AddRange(observed);
                if(Directory.Exists(Full(manifest.source))||File.Exists(Full(manifest.source+".meta")))throw new Exception("Folder source remained after reopen: "+manifest.source);
            }
        }
        AssetDatabase.SaveAssets();
    }
    static List<MoveRow> FolderIdentities(FolderMoveManifest manifest,bool target) {
        var rows=new List<MoveRow>();
        foreach(var entry in manifest.entries.Where(e=>e.kind=="folder"||e.kind=="asset").OrderBy(e=>e.source,StringComparer.Ordinal)) {
            var path=target?entry.target:entry.source;var guid=AssetDatabase.AssetPathToGUID(path);
            if(String.IsNullOrEmpty(guid))throw new Exception("Moved asset/folder GUID missing: "+path);
            rows.Add(new MoveRow{source=entry.source,target=entry.target,guid=guid,localIds=entry.kind=="asset"?Ids(path):new string[0]});
        }
        foreach(var entry in manifest.entries.Where(e=>e.kind!="folder")) {
            var path=target?entry.target:entry.source;
            if(!File.Exists(Full(path))||HashFile(Full(path))!=entry.sha256||new FileInfo(Full(path)).Length!=entry.bytes)throw new Exception("Moved folder manifest differs: "+path);
        }
        return rows;
    }
    static bool SameIdentities(List<MoveRow> left,List<MoveRow> right) {
        if(left.Count!=right.Count)return false;
        for(int i=0;i<left.Count;i++)if(left[i].source!=right[i].source||left[i].target!=right[i].target||left[i].guid!=right[i].guid||!left[i].localIds.SequenceEqual(right[i].localIds))return false;
        return true;
    }
    static string MetaGuid(string path) {
        var matches=Regex.Matches(File.ReadAllText(Full(path)),@"(?m)^guid:\s*([a-f0-9]{32})\s*$");
        if(matches.Count!=1)throw new Exception("Expected one static Unity GUID in metadata: "+path);
        return matches[0].Groups[1].Value;
    }
    static string BackupFull(string relative) { return Path.Combine(job.stage,"before",relative); }
    static bool Hash(string value) { return !String.IsNullOrEmpty(value)&&Regex.IsMatch(value,"^[a-f0-9]{64}$"); }
    static void ValidateSourceIdentityEvidence(RetireItem item) {
        if(!item.hasSourceIdentityEvidence)throw new Exception("Source-evidence-only policy requires an explicit evidence-presence flag: "+item.path);
        var evidence=item.sourceIdentityEvidence;var row=evidence==null?null:evidence.targetRecord;
        if(evidence==null||String.IsNullOrEmpty(evidence.snapshotPath)||!Hash(evidence.snapshotSha256)||evidence.assetPath!=item.path||!Hash(evidence.targetRecordSha256)||
           row==null||row.path!=item.path||!String.Equals(row.guid,item.guid,StringComparison.OrdinalIgnoreCase)||row.status!="unknown"||row.identityStatus!="no-persistent-object"||row.objectCount!=0||
           row.localIds==null||row.localIds.Length!=0||row.types==null||row.types.Length!=0||String.IsNullOrEmpty(row.error)||
           evidence.targetInputs==null||evidence.targetInputs.Length!=2)
            throw new Exception("Source-evidence-only collector record is incomplete or inconsistent: "+item.path);
        var asset=evidence.targetInputs.FirstOrDefault(x=>x!=null&&x.path==item.path);
        var meta=evidence.targetInputs.FirstOrDefault(x=>x!=null&&x.path==item.metaPath);
        if(asset==null||asset.sha256!=item.sha256||asset.bytes!=item.bytes||meta==null||meta.sha256!=item.metaSha256||meta.bytes!=item.metaBytes)
            throw new Exception("Collector source/meta hashes or byte counts differ: "+item.path);
    }
    static void ValidateRetirementBytes(RetireItem item) {
        var asset=Full(item.path);var meta=Full(item.metaPath);
        if(!File.Exists(asset)||!File.Exists(meta)||new FileInfo(asset).Length!=item.bytes||HashFile(asset)!=item.sha256||
           new FileInfo(meta).Length!=item.metaBytes||HashFile(meta)!=item.metaSha256||MetaGuid(item.metaPath)!=item.guid)
            throw new Exception("Retirement source/hash/static meta GUID precondition failed: "+item.path);
    }
    static string[] CurrentAssetDirectories() {
        var root=Path.Combine(job.targetRoot,"Assets");
        return new[]{root}.Concat(Directory.GetDirectories(root,"*",SearchOption.AllDirectories))
            .Select(x=>x.Substring(Path.GetFullPath(job.targetRoot).Length+1).Replace('\\','/'))
            .Where(x=>x!="Assets/BeaverTools"&&!x.StartsWith("Assets/BeaverTools/",StringComparison.Ordinal))
            .OrderBy(x=>x,StringComparer.Ordinal).ToArray();
    }
    static void ValidateDirectorySet(IEnumerable<string> expected) {
        var actual=CurrentAssetDirectories();var wanted=(expected??new string[0]).OrderBy(x=>x,StringComparer.Ordinal).ToArray();
        if(!actual.SequenceEqual(wanted))throw new Exception("Assets directory-set guard differs from the planned state");
    }
    static RetiredFolderIdentity FolderIdentity(RetireFolder item) {
        if(item==null||String.IsNullOrEmpty(item.path)||String.IsNullOrEmpty(item.guid)||String.IsNullOrEmpty(item.metaPath))throw new Exception("Explicit empty-folder identity required");
        var directory=Full(item.path);var meta=Full(item.metaPath);
        if(!AssetDatabase.IsValidFolder(item.path)||!Directory.Exists(directory)||Directory.GetFileSystemEntries(directory).Length!=0||
           !File.Exists(meta)||new FileInfo(meta).Length!=item.metaBytes||HashFile(meta)!=item.metaSha256||MetaGuid(item.metaPath)!=item.guid)
            throw new Exception("Empty folder/meta precondition failed: "+item.path);
        var asset=AssetDatabase.LoadMainAssetAtPath(item.path);
        if(asset==null||!(asset is DefaultAsset))throw new Exception("Folder main asset is not a native DefaultAsset: "+item.path);
        if(AssetDatabase.AssetPathToGUID(item.path,AssetPathToGUIDOptions.OnlyExistingAssets)!=item.guid||AssetDatabase.GUIDToAssetPath(item.guid)!=item.path)
            throw new Exception("Folder AssetDatabase GUID/path round trip differs from its metadata: "+item.path);
        string guid;long localId;
        if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset,out guid,out localId)||guid!=item.guid||localId==0)
            throw new Exception("Native DefaultAsset GUID/localID unavailable or differs: "+item.path);
        return new RetiredFolderIdentity{path=item.path,guid=guid,localId=localId,identityStatus="verified"};
    }
    static void ValidateFolderReview(RetireFolder item) {
        var review=item.callerReview;
        if(review==null||String.IsNullOrWhiteSpace(review.reference)||review.sourceSha256!=job.sourceSha256||
           review.directorySetSha256!=item.directorySetSha256||String.IsNullOrEmpty(item.directorySetSha256)||
           review.dynamicPathReview==null||review.dynamicPathReview.status!="reviewed-no-use"||
           String.IsNullOrWhiteSpace(review.dynamicPathReview.reason)||String.IsNullOrWhiteSpace(review.dynamicPathReview.evidence))
            throw new Exception("Source-bound caller/dynamic-path review is incomplete: "+item.path);
    }
    static void ValidateNoFolderReferences(IEnumerable<RetireFolder> folders) {
        var selected=new HashSet<string>((folders??new RetireFolder[0]).Select(x=>x.path),StringComparer.Ordinal);
        if(selected.Count==0)return;
        foreach(var source in AssetDatabase.GetAllAssetPaths().Where(x=>(x.StartsWith("Assets/",StringComparison.Ordinal)||x.StartsWith("Packages/",StringComparison.Ordinal))&&!selected.Contains(x)).OrderBy(x=>x,StringComparer.Ordinal)) {
            string[] dependencies;
            try { dependencies=AssetDatabase.GetDependencies(source,false); }
            catch(Exception error) { throw new Exception("Cannot establish native static dependency state for "+source,error); }
            if(dependencies.Any(selected.Contains))throw new Exception("Imported source has a static dependency on a selected empty folder: "+source);
        }
    }
    static string ExistingPathGuid(string path) {
        var guid=AssetDatabase.AssetPathToGUID(path,AssetPathToGUIDOptions.OnlyExistingAssets);
        if(String.IsNullOrEmpty(guid))throw new Exception("No existing Unity asset GUID: "+path);
        return guid;
    }
    static void ValidateGuidPathRoundTrip(string path,string guid) {
        var mapped=AssetDatabase.GUIDToAssetPath(guid);
        if(mapped!=path)throw new Exception("GUID does not map back to the exact source-evidence path: "+path+" -> "+mapped);
    }
    static RetireIdentity RetirementIdentity(RetireItem item) {
        if(item.identityPolicy!="native-object"&&item.identityPolicy!="source-evidence-only")throw new Exception("Unknown retirement identity policy: "+item.path);
        if(item.identityPolicy=="source-evidence-only") {
            ValidateSourceIdentityEvidence(item);
            AssetDatabase.ImportAsset(item.path,ImportAssetOptions.ForceSynchronousImport);
            ValidateRetirementBytes(item);
        } else if(item.hasSourceIdentityEvidence)throw new Exception("Collector evidence is forbidden by native-object policy: "+item.path);
        var guid=ExistingPathGuid(item.path);
        if(String.IsNullOrEmpty(guid)||guid!=item.guid)throw new Exception("Native retirement GUID missing or differs: "+item.path);
        var objects=PersistentObjects(item.path);var ids=Ids(objects);
        if(item.identityPolicy=="source-evidence-only") {
            ValidateGuidPathRoundTrip(item.path,guid);
            if(objects.Length!=0||ids.Length!=0)throw new Exception("Source-only identity policy requires exactly zero persistent native objects: "+item.path);
            var proof=item.sourceIdentityEvidence;
            return new RetireIdentity{path=item.path,guid=guid,identityPolicy=item.identityPolicy,identityStatus="no-persistent-object",nativeObjectCount=0,
                localIds=new string[0],sourceEvidenceSnapshotSha256=proof.snapshotSha256,sourceEvidenceTargetRecordSha256=proof.targetRecordSha256};
        }
        if(objects.Length==0||ids.Length==0)throw new Exception("Native-object policy requires persistent local IDs: "+item.path);
        return new RetireIdentity{path=item.path,guid=guid,identityPolicy=item.identityPolicy,identityStatus="verified",nativeObjectCount=objects.Length,
            localIds=ids,sourceEvidenceSnapshotSha256="",sourceEvidenceTargetRecordSha256=""};
    }
    static bool OptionalEvidenceEquals(string left,string right) {
        if(String.IsNullOrEmpty(left)||String.IsNullOrEmpty(right))return String.IsNullOrEmpty(left)&&String.IsNullOrEmpty(right);
        return left==right;
    }
    static string RetirementIdentityDifference(RetireIdentity left,RetireIdentity right) {
        if(left==null||right==null)return "identityRow";
        if(left.path!=right.path)return "path";
        if(left.guid!=right.guid)return "guid";
        if(left.identityPolicy!=right.identityPolicy)return "identityPolicy";
        if(left.identityStatus!=right.identityStatus)return "identityStatus";
        if(left.nativeObjectCount!=right.nativeObjectCount)return "nativeObjectCount";
        if(left.identityPolicy=="source-evidence-only"&&(!Hash(left.sourceEvidenceSnapshotSha256)||!Hash(right.sourceEvidenceSnapshotSha256)))return "sourceEvidenceSnapshotSha256";
        if(left.identityPolicy=="source-evidence-only"&&(!Hash(left.sourceEvidenceTargetRecordSha256)||!Hash(right.sourceEvidenceTargetRecordSha256)))return "sourceEvidenceTargetRecordSha256";
        if(!OptionalEvidenceEquals(left.sourceEvidenceSnapshotSha256,right.sourceEvidenceSnapshotSha256))return "sourceEvidenceSnapshotSha256";
        if(!OptionalEvidenceEquals(left.sourceEvidenceTargetRecordSha256,right.sourceEvidenceTargetRecordSha256))return "sourceEvidenceTargetRecordSha256";
        if(left.localIds==null||right.localIds==null||!left.localIds.SequenceEqual(right.localIds))return "localIds";
        return "";
    }
    static ProtectedIdentity ProtectedSnapshot(ProtectedItem item) {
        var file=Full(item.path);var meta=Full(item.metaPath);
        var guid=AssetDatabase.AssetPathToGUID(item.path, AssetPathToGUIDOptions.OnlyExistingAssets);
        if(!File.Exists(file)||!File.Exists(meta)||new FileInfo(file).Length!=item.bytes||HashFile(file)!=item.sha256||
           new FileInfo(meta).Length!=item.metaBytes||HashFile(meta)!=item.metaSha256||MetaGuid(item.metaPath)!=item.guid||guid!=item.guid)
            throw new Exception("Protected root bytes or GUID changed: "+item.path);
        var ids=Ids(item.path);if(ids.Length==0)throw new Exception("Protected root local identity missing: "+item.path);
        return new ProtectedIdentity{path=item.path,guid=guid,sha256=item.sha256,metaSha256=item.metaSha256,localIds=ids};
    }
    static List<ProtectedIdentity> ProtectedSnapshots() {
        if(job.protectedManifest==null||job.protectedManifest.Length==0)throw new Exception("Explicit protected roots required");
        return job.protectedManifest.Select(ProtectedSnapshot).ToList();
    }
    static bool SameProtected(List<ProtectedIdentity> left,List<ProtectedIdentity> right) {
        if(left.Count!=right.Count)return false;
        for(int i=0;i<left.Count;i++)if(left[i].path!=right[i].path||left[i].guid!=right[i].guid||left[i].sha256!=right[i].sha256||left[i].metaSha256!=right[i].metaSha256||!left[i].localIds.SequenceEqual(right[i].localIds))return false;
        return true;
    }
    static Report PriorRetirement(string name) {
        var path=Path.Combine(job.stage,name);
        if(!File.Exists(path))throw new Exception("Retirement checkpoint missing: "+name);
        var prior=JsonUtility.FromJson<Report>(File.ReadAllText(path));
        if(prior==null||prior.operation!="assets.retire"||prior.planSha256!=job.planSha256)throw new Exception("Retirement checkpoint identity differs");
        return prior;
    }
    static void ValidateRetirementCheckpoint(Report prior,bool requireComplete) {
        var planned=(job.retireManifest??new RetireItem[0]).Select(x=>x.path).ToArray();
        if(prior.selectedPaths==null||!prior.selectedPaths.SequenceEqual(planned)||prior.retiredAssets==null||
           !prior.retiredAssets.Select(x=>x.path).SequenceEqual(planned)||prior.protectedRoots==null||
           !prior.protectedRoots.Select(x=>x.path).SequenceEqual((job.protectedManifest??new ProtectedItem[0]).Select(x=>x.path)))
            throw new Exception("Retirement identity checkpoint is incomplete");
        if(!String.IsNullOrEmpty(prior.deleteInProgress))throw new Exception("Uncertain DeleteAsset checkpoint blocks recovery");
        if(prior.deletedPaths==null||prior.deletedPaths.Distinct().Count()!=prior.deletedPaths.Count||prior.deletedPaths.Any(x=>!planned.Contains(x)))
            throw new Exception("Retirement deleted-path checkpoint is invalid");
        if(!prior.resourcesDynamicUseNotProvable||prior.dependencyPaths==null||prior.dependencyClosures==null||
           !prior.dependencyClosures.Select(x=>x.root).SequenceEqual((job.protectedManifest??new ProtectedItem[0]).Select(x=>x.path)))
            throw new Exception("Resources/dependency scope checkpoint is incomplete");
        var plannedResources=job.resources??new ResourceRetirement[0];var witnessedResources=prior.resources??new List<ResourceRetirement>();
        if(witnessedResources.Count!=plannedResources.Length)throw new Exception("Resources declaration checkpoint differs");
        for(int i=0;i<plannedResources.Length;i++)if(witnessedResources[i].key!=plannedResources[i].key||witnessedResources[i].path!=plannedResources[i].path||witnessedResources[i].guid!=plannedResources[i].guid||witnessedResources[i].reason!=plannedResources[i].reason||witnessedResources[i].sourceEvidence!=plannedResources[i].sourceEvidence)throw new Exception("Resources declaration checkpoint differs");
        foreach(var path in prior.deletedPaths)if(!prior.retiredAssets.Any(x=>x.path==path&&!String.IsNullOrEmpty(x.guid)&&x.localIds!=null))throw new Exception("Deleted asset lacks a witnessed GUID/identity-policy checkpoint: "+path);
        foreach(var item in job.protectedManifest)if(!prior.protectedRoots.Any(x=>x.path==item.path&&x.guid==item.guid&&x.sha256==item.sha256&&x.metaSha256==item.metaSha256&&x.localIds!=null&&x.localIds.Length>0))throw new Exception("Protected-root checkpoint differs: "+item.path);
        for(int i=0;i<job.retireManifest.Length;i++)ValidateRetireIdentityWitness(job.retireManifest[i],prior.retiredAssets[i]);
        if(requireComplete&&(prior.status!="verified"||!prior.deletedPaths.SequenceEqual(planned)))throw new Exception("Complete retirement checkpoint required");
    }
    static void ValidateRetireIdentityWitness(RetireItem item,RetireIdentity row) {
        if(row==null||row.path!=item.path||row.guid!=item.guid||row.identityPolicy!=item.identityPolicy||row.localIds==null)
            throw new Exception("Retirement identity policy/GUID checkpoint differs: "+item.path);
        if(item.identityPolicy=="source-evidence-only") {
            ValidateSourceIdentityEvidence(item);var evidence=item.sourceIdentityEvidence;
            if(row.identityStatus!="no-persistent-object"||row.nativeObjectCount!=0||row.localIds.Length!=0||
               row.sourceEvidenceSnapshotSha256!=evidence.snapshotSha256||row.sourceEvidenceTargetRecordSha256!=evidence.targetRecordSha256)
                throw new Exception("Source-evidence-only checkpoint must preserve zero objects, empty IDs, and collector digests: "+item.path);
        } else if(item.identityPolicy=="native-object") {
            if(item.hasSourceIdentityEvidence||row.identityStatus!="verified"||row.nativeObjectCount<=0||row.localIds.Length==0||row.nativeObjectCount!=row.localIds.Length||
               !String.IsNullOrEmpty(row.sourceEvidenceSnapshotSha256)||!String.IsNullOrEmpty(row.sourceEvidenceTargetRecordSha256))
                throw new Exception("Native-object checkpoint requires verified persistent IDs: "+item.path);
        } else throw new Exception("Unknown retirement identity policy: "+item.path);
    }
    static void ValidateFolderCheckpoint(Report prior,bool requireComplete) {
        var folders=job.folderRetireManifest??new RetireFolder[0];var paths=folders.Select(x=>x.path).ToArray();
        if(folders.Length==0)return;
        if(prior.retiredFolders==null||!prior.retiredFolders.Select(x=>x.path).SequenceEqual(paths)||
           prior.deletedFolders==null||prior.deletedFolders.Distinct().Count()!=prior.deletedFolders.Count||prior.deletedFolders.Any(x=>!paths.Contains(x))||
           !String.IsNullOrEmpty(prior.folderDeleteInProgress)||!prior.folderDynamicPathUseNotProvable)throw new Exception("Empty-folder identity/deletion checkpoint is incomplete");
        for(int i=0;i<folders.Length;i++) {
            var item=folders[i];var row=prior.retiredFolders[i];ValidateFolderReview(item);
            if(row==null||row.path!=item.path||row.guid!=item.guid||row.identityStatus!="verified"||row.localId==0)throw new Exception("Empty-folder GUID/localID witness differs: "+item.path);
        }
        if(requireComplete&&(prior.status!="verified"||!prior.deletedFolders.SequenceEqual(paths)))throw new Exception("Complete empty-folder deletion checkpoint required");
        var expected=(job.sourceDirectoryPaths??new string[0]).Where(x=>!prior.deletedFolders.Contains(x)).ToArray();ValidateDirectorySet(expected);
        foreach(var item in folders) {
            var deleted=prior.deletedFolders.Contains(item.path);
            if(deleted&&(Directory.Exists(Full(item.path))||File.Exists(Full(item.metaPath))||AssetDatabase.IsValidFolder(item.path)))throw new Exception("Retired folder is present after deletion: "+item.path);
            if(!deleted&&(!AssetDatabase.IsValidFolder(item.path)||Directory.GetFileSystemEntries(Full(item.path)).Length!=0))throw new Exception("Undeleted folder no longer matches empty precondition: "+item.path);
        }
    }
    static void ValidateRetirementInputs() {
        var items=job.retireManifest??new RetireItem[0];var selected=new HashSet<string>(items.Select(x=>x.path),StringComparer.Ordinal);
        var folders=job.folderRetireManifest??new RetireFolder[0];
        if(items.Length+folders.Length==0||selected.Count!=items.Length||folders.Select(x=>x.path).Distinct().Count()!=folders.Length||selected.Overlaps(folders.Select(x=>x.path)))throw new Exception("Explicit unique retirement file/folder manifest required");
        if(folders.Length>0){ValidateDirectorySet(job.sourceDirectoryPaths);ValidateNoFolderReferences(folders);}
        foreach(var item in items) {
            ValidateRetirementBytes(item);
            var backup=BackupFull(item.path);var backupMeta=BackupFull(item.metaPath);
            if(!File.Exists(backup)||new FileInfo(backup).Length!=item.bytes||HashFile(backup)!=item.sha256||
               !File.Exists(backupMeta)||new FileInfo(backupMeta).Length!=item.metaBytes||HashFile(backupMeta)!=item.metaSha256)
                throw new Exception("Verified before-image is incomplete: "+item.path);
        }
        foreach(var folder in folders) {
            ValidateFolderReview(folder);FolderIdentity(folder);
            var backup=BackupFull(folder.metaPath);
            if(!File.Exists(backup)||new FileInfo(backup).Length!=folder.metaBytes||HashFile(backup)!=folder.metaSha256)
                throw new Exception("Verified folder metadata before-image is incomplete: "+folder.path);
        }
        var protectedNow=ProtectedSnapshots();
        foreach(var root in job.protectedManifest) {
            if(selected.Contains(root.path))throw new Exception("Protected root selected for retirement: "+root.path);
            var closure=AssetDatabase.GetDependencies(root.path,true).Distinct().OrderBy(x=>x,StringComparer.Ordinal).ToArray();
            report.dependencyClosures.Add(new DependencyClosure{root=root.path,paths=closure});
            foreach(var dependency in closure) {
                if(!report.dependencyPaths.Contains(dependency))report.dependencyPaths.Add(dependency);
                if(selected.Contains(dependency))throw new Exception("Protected root still depends on selected asset: "+root.path+" -> "+dependency);
            }
        }
        report.dependencyPaths=report.dependencyPaths.OrderBy(x=>x,StringComparer.Ordinal).ToList();
        report.selectedPaths.AddRange(items.Select(x=>x.path));
        report.retiredAssets.AddRange(items.Select(RetirementIdentity));
        report.retiredFolders.AddRange(folders.Select(FolderIdentity));
        report.folderDynamicPathUseNotProvable=folders.Length>0;
        report.protectedRoots.AddRange(protectedNow);
        report.resources.AddRange(job.resources??new ResourceRetirement[0]);
        // Resources.Load and reflection-based keys cannot be proven unused by
        // AssetDatabase.GetDependencies; the explicit declarations record the
        // user's source-backed decision without claiming static closure.
        report.resourcesDynamicUseNotProvable=true;
        Save();
    }
    static void Retire(bool write) {
        if(write) {
            ValidateRetirementInputs();
            foreach(var item in job.folderRetireManifest??new RetireFolder[0]) {
                report.folderDeleteInProgress=item.path;Save();
                if(!AssetDatabase.DeleteAsset(item.path))throw new Exception("AssetDatabase.DeleteAsset returned false for empty folder: "+item.path);
                if(Directory.Exists(Full(item.path))||File.Exists(Full(item.metaPath))||AssetDatabase.IsValidFolder(item.path))throw new Exception("DeleteAsset did not remove the exact empty folder and metadata: "+item.path);
                report.deletedFolders.Add(item.path);report.folderDeleteInProgress="";Save();
            }
            foreach(var item in job.retireManifest) {
                report.deleteInProgress=item.path;Save();
                if(!AssetDatabase.DeleteAsset(item.path))throw new Exception("AssetDatabase.DeleteAsset returned false: "+item.path);
                if(File.Exists(Full(item.path))||File.Exists(Full(item.metaPath))||!String.IsNullOrEmpty(AssetDatabase.AssetPathToGUID(item.path, AssetPathToGUIDOptions.OnlyExistingAssets)))
                    throw new Exception("DeleteAsset did not remove the exact asset and metadata: "+item.path);
                report.deletedPaths.Add(item.path);report.deleteInProgress="";Save();
            }
            AssetDatabase.SaveAssets();AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            foreach(var item in job.retireManifest)
                if(File.Exists(Full(item.path))||File.Exists(Full(item.metaPath))||!String.IsNullOrEmpty(AssetDatabase.AssetPathToGUID(item.path, AssetPathToGUIDOptions.OnlyExistingAssets)))throw new Exception("Retired asset reappeared: "+item.path);
            if((job.folderRetireManifest??new RetireFolder[0]).Length>0)ValidateDirectorySet((job.sourceDirectoryPaths??new string[0]).Except((job.folderRetireManifest??new RetireFolder[0]).Select(x=>x.path)));
            var protectedAfter=ProtectedSnapshots();
            if(!SameProtected(report.protectedRoots,protectedAfter))throw new Exception("Protected root identity changed during retirement");
        } else {
            var prior=PriorRetirement("native-apply.json");ValidateRetirementCheckpoint(prior,true);
            if((job.folderRetireManifest??new RetireFolder[0]).Length>0)ValidateFolderCheckpoint(prior,true);
            foreach(var item in job.retireManifest)
                if(File.Exists(Full(item.path))||File.Exists(Full(item.metaPath))||!String.IsNullOrEmpty(AssetDatabase.AssetPathToGUID(item.path, AssetPathToGUIDOptions.OnlyExistingAssets)))throw new Exception("Retired asset is present after reopen: "+item.path);
            var protectedNow=ProtectedSnapshots();
            if(!SameProtected(prior.protectedRoots,protectedNow))throw new Exception("Protected roots differ after reopen");
            report.selectedPaths.AddRange(prior.selectedPaths);report.deletedPaths.AddRange(prior.deletedPaths);
            report.retiredAssets.AddRange(prior.retiredAssets);report.protectedRoots.AddRange(protectedNow);
            report.retiredFolders.AddRange(prior.retiredFolders);report.deletedFolders.AddRange(prior.deletedFolders);
            report.folderDynamicPathUseNotProvable=prior.folderDynamicPathUseNotProvable;
            report.dependencyPaths.AddRange(prior.dependencyPaths);
            report.dependencyClosures.AddRange(prior.dependencyClosures??new List<DependencyClosure>());
            report.resources.AddRange(prior.resources??new List<ResourceRetirement>());report.resourcesDynamicUseNotProvable=prior.resourcesDynamicUseNotProvable;
        }
        AssetDatabase.SaveAssets();
    }
    static void RecoverRetiredAssets(bool verification) {
        var prior=PriorRetirement(verification?"native-recover.json":"native-apply.json");
        ValidateRetirementCheckpoint(prior,false);
        if(prior.deletedPaths.Count==0&&(prior.deletedFolders==null||prior.deletedFolders.Count==0))throw new Exception("No witnessed deletion checkpoint; recovery is blocked");
        var folders=job.folderRetireManifest??new RetireFolder[0];var folderPaths=folders.Select(x=>x.path).ToArray();
        if(prior.retiredFolders==null||!prior.retiredFolders.Select(x=>x.path).SequenceEqual(folderPaths)||prior.deletedFolders==null||
           prior.deletedFolders.Distinct().Count()!=prior.deletedFolders.Count||prior.deletedFolders.Any(x=>!folderPaths.Contains(x))||!String.IsNullOrEmpty(prior.folderDeleteInProgress))
            throw new Exception("Empty-folder deletion checkpoint is absent or uncertain");
        if(prior.folderDynamicPathUseNotProvable!=(folders.Length>0))throw new Exception("Dynamic folder path-use boundary is missing from the deletion checkpoint");
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        var expected=prior.retiredAssets.ToDictionary(x=>x.path,StringComparer.Ordinal);
        foreach(var item in job.retireManifest) {
            var file=Full(item.path);var meta=Full(item.metaPath);
            if(!File.Exists(file)||!File.Exists(meta)||new FileInfo(file).Length!=item.bytes||HashFile(file)!=item.sha256||
               new FileInfo(meta).Length!=item.metaBytes||HashFile(meta)!=item.metaSha256||MetaGuid(item.metaPath)!=item.guid)
                throw new Exception("Restored before-image bytes or meta GUID differ: "+item.path);
            var identity=RetirementIdentity(item);report.retiredAssets.Add(identity);Save();
            var witness=expected[item.path];var difference=RetirementIdentityDifference(identity,witness);
            if(difference!="")throw new Exception("Restored identity differs from deletion checkpoint at "+difference+": "+item.path);
        }
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        foreach(var item in folders) {
            if(!prior.deletedFolders.Contains(item.path))continue;
            var identity=FolderIdentity(item);var witness=prior.retiredFolders.First(x=>x.path==item.path);
            if(identity.guid!=witness.guid||identity.localId!=witness.localId)throw new Exception("Restored empty-folder GUID/localID differs from deletion witness: "+item.path);
            report.retiredFolders.Add(identity);report.recoveredFolders.Add(item.path);Save();
        }
        if(folders.Length>0)ValidateDirectorySet(job.sourceDirectoryPaths);
        var protectedNow=ProtectedSnapshots();
        if(!SameProtected(prior.protectedRoots,protectedNow))throw new Exception("Protected roots differ during recovery");
        report.selectedPaths.AddRange(prior.selectedPaths);report.deletedPaths.AddRange(prior.deletedPaths);
        if(report.retiredFolders.Count==0)report.retiredFolders.AddRange(prior.retiredFolders);
        report.deletedFolders.AddRange(prior.deletedFolders);report.recoveredFolders=prior.deletedFolders.ToList();
        report.recoveredPaths.AddRange(prior.deletedPaths);
        report.dependencyPaths.AddRange(prior.dependencyPaths);
        report.dependencyClosures.AddRange(prior.dependencyClosures??new List<DependencyClosure>());
        report.protectedRoots.AddRange(protectedNow);report.resources.AddRange(prior.resources??new List<ResourceRetirement>());
        report.resourcesDynamicUseNotProvable=prior.resourcesDynamicUseNotProvable;
        report.folderDynamicPathUseNotProvable=prior.folderDynamicPathUseNotProvable;
        AssetDatabase.SaveAssets();
    }
    public static void Run() {
        int code=1;
        try {
            job=JsonUtility.FromJson<Job>(File.ReadAllText(JobPath()));
            report=new Report{status="running",operation=job.operation,mode=job.mode,planSha256=job.planSha256,sourceSha256=job.sourceSha256};Save();
            if(Application.unityVersion!="6000.6.2f1")throw new Exception("Unexpected Editor version");
            if(Path.GetFullPath(Directory.GetParent(Application.dataPath).FullName)!=Path.GetFullPath(job.targetRoot))throw new Exception("Wrong project");
            if(job.operation=="validate.play") {Play();return;}
            if(job.mode=="apply") {
                if(job.operation=="ui.create")CreateUI();
                else if(job.operation=="prefab.edit")EditPrefab();
                else if(job.operation=="build.macos")Build();
                else if(job.operation=="assets.move")Moves(true);
                else if(job.operation=="assets.retire")Retire(true);
                else if(job.operation=="sprite.configure")SpriteImport(true);
                else if(job.operation=="project.import") {AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);AssetDatabase.SaveAssets();}
                else if(job.operation!="prefab.inspect")throw new Exception("Unknown operation");
            } else if(job.mode!="verify"&&job.mode!="recover"&&job.mode!="recover-verify")throw new Exception("Unknown native mode");
            if(job.operation=="assets.move") {if(job.mode=="verify")Moves(false);}
            else if(job.operation=="assets.retire") {
                if(job.mode=="verify")Retire(false);
                else if(job.mode=="recover")RecoverRetiredAssets(false);
                else if(job.mode=="recover-verify")RecoverRetiredAssets(true);
            }
            else if(job.operation=="sprite.configure") {if(job.mode=="verify")SpriteImport(false);}
            else if(job.operation=="project.import") { }
            else if(job.operation!="build.macos")InspectPrefab();
            report.status="verified";Save();code=0;
        } catch(Exception error) {
            if(report!=null){report.status="failed";report.error=error.ToString();Save();}
            Debug.LogException(error);
        }
        EditorApplication.Exit(code);
    }
}
#endif
