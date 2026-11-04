// Conversion-only native Editor adapter. No source graph is loaded by the Player.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static partial class MonkeyImporter
{
    [Serializable] public class Plan {
        public UnityStaticToggle.Spec toggleBinding;
        public StaticLayoutCompletionContract layoutCompletion; public StaticMaskContract staticMasks; public Monkey.StaticSortQueueProxy.ProxyQueueSpec[] staticSortQueue;
        public BitmapMissingGlyphContract bitmapMissingGlyphs;
        public string spriteOutlineBindingJson;
        public string staticTimeMaterialsJson,sourceManifestSha256;
        public UnityPreviewState.Spec previewState; public UnityPreviewState.Spec[] previewStates;
        public MonkeyUnityMaterialBindings.Spec materialBinding;
        public UnitySystemFonts.BindingSet systemFontBinding;
        public string staticFontReceiptPath,staticFontReceiptSha256;
        public int uiStateProbeVersion; public string[] uiProbeSources;
        public float[] designSize; public float pixelsPerUnit; public string uiGeometryReadback;
        public TextureSpec[] textures; public AssetSpec[] assets; public BitmapSpec[] bitmapFonts; public int sourceDiagnosticCount;
        public UnityStaticRetainedAssets.Contract staticRetainedAssets; public StaticControlSpec[] staticControlBindings; public bool staticCompletionEnabled; public StaticAnimationEvidenceSpec[] staticAnimationEvidence; public StaticAnimationComponentOrigin[] staticAnimationComponentOrigins; public StaticAnimationAssetRef[] staticAnimationAssetReferences;
        public NodeSpec[] nodes; public ComponentSpec[] components; public MotionSpec[] animations; public bool galleryOnly; public SourcePrefabSpec[] sourcePrefabs; public PrefabInstanceSpec[] prefabInstances; public TmpResourceSpec tmpResources;
    }
    [Serializable] public class StaticAnimationAssetRef {public string sourceId,animationId,path;}
    [Serializable] public class TmpResourceSpec { public string packageName,packageVersion,resource,importMode; }
    [Serializable] public class TmpResourceResult {
        public int schemaVersion=1;public string status,packageName,packageVersion,source,resource,archiveSha256;
        public string bitmapGuid,distanceGuid,mobileGuid,settingsGuid,completionProof;
    }
    static Shader tmpBitmapShader,tmpDistanceShader;
    static TmpResourceResult tmpResourceResult;
    [Serializable] public class SourcePrefabSpec { public string sourceId,root,path; public string[] nodes; public int nodeCount; }
    [Serializable] public class SourcePrefabResult {
        public PrefabInstanceResult[] prefabInstances;
        public StaticSortPrefabReadback staticSortFields; public int generatedSortNodeCount; public StaticLayoutProbeResult staticLayoutProbe; public StaticLayoutNodeReadback[] staticLayoutFields; public Monkey.StaticMaskSort.MaskReadback[] staticMaskFields;
        public NativeBitmapMissingGlyphs.Readback[] bitmapMissingGlyphFields;
        public MonkeyNumericCode.Result[] numericCodeBindings;
        public MonkeyBehaviorBindings.Result[] behaviorBindings; public StaticControlReadback[] staticControlFields; public StaticAnimationReadback[] staticAnimationFields; public StaticProgressResult[] staticProgressFields; public StaticFieldResult[] staticFieldBindings; public UnityStaticToggle.Readback toggleFields;
        public string sourceId,path,guid,geometryPhase,nativePrefabType,isolatedPreviewPath,isolatedPreviewSha256,isolatedPreviewError,isolatedPreviewScope; public int nodeCount,generatedTextSubmeshCount,generatedSpineSubmeshCount,missingScripts,layoutSettlePasses;
        public bool savedReloaded,referencesVerified; public NodeResult[] nodes,nativeInitialNodes; public string[] referenceFailures;
    }
    [Serializable] public class MotionKey { public float time,value; public string interpolation; }
    [Serializable] public class MotionProbe { public float time,value; }
    [Serializable] public class MotionTrack { public string node,path,nativeType,nativeProperty; public MotionKey[] keys; public MotionProbe[] probes; }
    [Serializable] public class MotionSpec { public string id,name,root,path,wrap; public float duration,sample; public bool convertible,assetOnly; public MotionTrack[] tracks; }
    [Serializable] public class MotionTrackResult { public string path,property,nativeType; public float[] times,values,probeTimes,probeValues; public string[] interpolations; }
    [Serializable] public class MotionResult { public string id,path,guid,wrap; public float duration; public int eventCount,curveCount; public MotionTrackResult[] tracks; }
    [Serializable] public class TextureSpec {
        public string id, path, guid; public float[] border, size, originalSize, offset;
    }
    [Serializable] public class AssetSpec { public string id, kind, path, fontAssetPath; }
    [Serializable] public class NodeSpec {
        public string sourceId, name, parent,sourceGeometryProfile; public bool verifyUiColor; public string[] children, components;
        public float[] position, rotation, scale, size, anchor, color;
        public float opacity; public bool active;
    }
    [Serializable] public class NumericMethodsSpec { public string setter,getter; }
    [Serializable] public class ComponentSpec {
        public string[] clips; public string defaultClip; public bool defaultClipKnown,playOnLoad;
        public StaticButtonColors staticButtonBinding; public StaticProgressSpec staticProgressBinding;
        public string nativeStaticTimeMaterialSourceId,nativeStaticTimeSourceComponentId;
        public MonkeyBehaviorBindings.Spec behaviorBinding; public UnityStaticFields.Spec staticFieldBinding; public UnityStaticRichText.Spec staticRichText;
        public string codeClassName,codeNamespace,codeScriptGuid,sourceScriptIdentity; public NumericMethodsSpec numericMethods;
        public string sourceId, type, node, spriteFrame, font, text, nativeLayoutMode,staticPresentationPolicy;
        public string bitmapMissingGlyphPolicy,bitmapMissingGlyphDisplayText;
        public string barNode; public float progress,totalLength;
        public float[] nativeCellSize;
        public int mode, sizeMode, horizontalAlign, verticalAlign, overflow; public float fontSize,lineHeight;
        public bool enabled, convertible, trim, wrap, bold, italic, underline, sourceBold, bitmapLabel,staticBitmapOutline; public float spacing; public BitmapProbe bitmapProbe;
        public string target,content,nativeId,controllerPath,materialPath,normalClipPath,pressedClipPath; public int flags,maskType,layoutType,resize,horizontalDirection,verticalDirection,startAxis,constraint,constraintCount,transition;
        public bool inverted,horizontal,vertical,interactable; public float zoomScale,duration,width;
        public float[] margins,spacingXY,padding,effectiveCellSize,cellSize,outlineColor;
        public bool crossAxisScale; public float crossAxisAlignment; public bool[] absolute,centerAbsolute; public float[] center; public int alignMode; public bool affectedByScale,alignCross;
    }
    static partial void PrepareOptionalSpriteOutline(string json,Plan plan,Dictionary<string,GameObject> nodes,Dictionary<string,Sprite> frames);
    static partial void ResolveOptionalSpriteOutline(Plan plan,string id,Dictionary<string,GameObject> nodes,ref UnityEngine.Object value);
    static partial void ReadSavedOptionalSpriteOutline(Dictionary<string,GameObject> nodes,string prefabId);
    static partial void PrepareOptionalStaticTimeMaterials(string json,Plan plan,Dictionary<string,GameObject> nodes,Dictionary<string,Sprite> frames);
    static partial void ReadSavedOptionalStaticTimeMaterials(Dictionary<string,GameObject> nodes,string prefabId);
    static partial void ResolveOptionalStaticTimeMaterial(Plan plan,string id,ref UnityEngine.Object value);
    static partial void IdentifyOptionalGeneratedSpineChild(Transform child,ref bool generated);
    static partial void InitializeSavedStaticSpine(GameObject root);
    static partial void SkipOptionalSpineDerivedProperty(Component component,string propertyPath,ref bool skip);
    static partial void IdentifyOptionalSpineDerivedComponent(Component component,ref bool generated);
    static partial void PrepareStaticSpine(Plan plan, Dictionary<string,GameObject> nodes);
    static partial void ResolveStaticSpineReference(string id, Dictionary<string,GameObject> nodes, ref UnityEngine.Object value);
    static partial void ReadSavedStaticSpine(Dictionary<string,GameObject> nodes,string prefabId);
    static string SourceOutlineLabel(Plan plan,string nodeId) {
        for(int depth=0;depth<64;depth++) {
            var labels=plan.components.Where(c=>c.node==nodeId&&(c.type=="cc.Label"||c.type=="cc.RichText")).ToArray();
            if(labels.Length!=1)throw new InvalidOperationException("OUTLINE_LABEL_IDENTITY_AMBIGUOUS: "+nodeId);
            var sourceId=labels[0].sourceId;
            if(plan.systemFontBinding.labelBindings.Any(b=>b.sourceLabelId==sourceId))return sourceId;
            var original=(plan.prefabInstances??Array.Empty<PrefabInstanceSpec>()).SelectMany(i=>i.nodes)
                .Where(pair=>pair.instanceObject==nodeId).Select(pair=>pair.templateObject).Distinct().ToArray();
            if(original.Length==0)return null;
            if(original.Length!=1)throw new InvalidOperationException("OUTLINE_FONT_BINDING_AMBIGUOUS: "+nodeId);
            nodeId=original[0];
        }
        throw new InvalidOperationException("OUTLINE_FONT_BINDING_CYCLE");
    }
    [Serializable] public class StaticButtonColors {public float[] normalColor,hoverColor,pressedColor,disabledColor;public bool renderReady,sourceEnabled;}
    static TMPro.FontStyles SourceFontStyles(ComponentSpec spec) {
        if(spec.bitmapLabel)return TMPro.FontStyles.Normal;
        return (spec.bold?TMPro.FontStyles.Bold:TMPro.FontStyles.Normal) | (spec.italic?TMPro.FontStyles.Italic:TMPro.FontStyles.Normal) | (spec.underline?TMPro.FontStyles.Underline:TMPro.FontStyles.Normal);
    }
    static Color ButtonColor(float[] value){if(value==null||value.Length!=4)throw new InvalidOperationException("STATIC_BUTTON_COLOR_MISSING");return new Color(value[0]/255f,value[1]/255f,value[2]/255f,value[3]/255f);}
    static bool StaticButtonMatches(ComponentSpec spec,UnityEngine.UI.Button button,GameObject target) {
        var graphic=target?target.GetComponent<UnityEngine.UI.Graphic>():null;
        if(button==null||button.enabled||button.targetGraphic!=graphic||button.interactable!=spec.interactable||button.transition!=(spec.transition==1?UnityEngine.UI.Selectable.Transition.ColorTint:UnityEngine.UI.Selectable.Transition.None))return false;
        var retained=button.GetComponent<NativeStaticButtonTarget>();
        if(retained==null||retained.enabled||retained.Target!=target||retained.SourceEnabled!=spec.staticButtonBinding.sourceEnabled||retained.SourceTransition!=spec.transition||Mathf.Abs(retained.SourceZoomScale-spec.zoomScale)>.0001f||Mathf.Abs(retained.SourceDuration-spec.duration)>.0001f)return false;
        var c=button.colors;var s=spec.staticButtonBinding;
        return c.normalColor==ButtonColor(s.normalColor)&&c.highlightedColor==ButtonColor(s.hoverColor)&&c.pressedColor==ButtonColor(s.pressedColor)&&c.disabledColor==ButtonColor(s.disabledColor)&&Mathf.Abs(c.fadeDuration-spec.duration)<.0001f;
    }
    [Serializable] public class BitmapProbe { public float advance,inkRight; }
    [Serializable] public class BitmapSpec {
        public string id, path, fontPath, atlasGuid; public float pointSize, lineHeight, ascent, descent;
        public int[] atlasSize; public GlyphSpec[] glyphs; public KerningSpec[] kernings;
    }
    [Serializable] public class GlyphSpec { public uint unicode, index; public int[] rect; public float[] metrics; }
    [Serializable] public class KerningSpec { public uint first, second; public float advance; }
    [Serializable] public class FontResult { public string id, guid, atlasGuid, materialAtlasGuid; public int glyphCount, characterCount; public float pointSize, lineHeight; }
    [Serializable] public class LabelResult { public string sourceId, text, fontGuid, geometryProbe; public bool autoSizeReadback,autoSizing; public float fontSizeMin,fontSizeMax; public float fontSize,lineBoxHeight,lineBoxLineHeight,lineBoxExtra; public string bitmapMissingGlyphPolicy,bitmapDisplayText; public bool bitmapMissingGlyphProofVerified; public int characterCount,lineCount; public bool lineBoxPresent,lineBoxActive; public bool allCharactersPresent; public GlyphBounds[] glyphBounds; }
    [Serializable] public class GlyphBounds { public uint unicode; public float left,top,width,height,quadPadding; }
    [Serializable] public class Readback {
        public StaticPreviewResult staticPreview; public StaticPreviewResult[] staticPreviews;
        public MonkeyUnityMaterialBindings.Readback materialBinding;
        public PrefabInstanceResult[] prefabInstances;
        public PrefabInstanceResult[] candidatePrefabInstances;
        public string nativeScope,sourceGraphVerification; public GalleryResult[] gallery;
        public MonkeyNumericCode.Result[] numericCodeBindings,numericCodeExercise;
        public string status, unityVersion, prefabGuid, sceneGuid;
        public int spriteCount, nodeCount, missingScripts; public bool editableRoundtrip,sceneReopened; public string previewPath,previewSha256,previewError,colorSpace;
        public UnityStaticRetainedAssets.Result[] staticRetainedAssetReadback; public DynamicUiResult[] dynamicUiProbes; public MotionResult[] animations; public string[] diagnostics; public NodeResult[] nodes,nativeInitialNodes; public SpriteResult[] sprites; public FileResult[] nativeFiles; public FontResult[] fonts; public LabelResult[] labels; public ViewReference[] viewReferences; public JsonResult[] jsonAssets; public SourcePrefabResult[] sourcePrefabs; public TmpResourceResult tmpResources;
    }
    [Serializable] public class GalleryResult { public string id,spriteGuid; public bool geometryVerified; }
    [Serializable] public class JsonResult { public string id,guid,textSha256; }
    [Serializable] public class ViewReference { public string sourceId,field; public int index; public long prefabFileId; public bool bound; }
    [Serializable] public class FileResult { public string path, sha256; }
    [Serializable] public class NodeResult {
        public string sourceId, hierarchy; public float[] size, pivot, position,scale,rotation,color; public float opacity;
        public bool active; public string[] componentTypes;
    }
    [Serializable] public class SpriteResult {
        public string id, guid,alphaSource; public float[] size, border;
        public long fileId;
    }
    // Editor-only typed output locations. Original game source and text are never rewritten.
    [Serializable] public class OutputPaths {
        // monkey-project/2.0.0 defaults (docs/PROJECT-SPEC.md); candidates declare their own copy in output-paths.json.
        public string plan="Assets/Game/Editor/Conversion/import-plan.json";
        public string prefab="Assets/Game/Scenes/Preview/ContentPreview.prefab",scene="Assets/Game/Scenes/Preview/ContentPreview.unity",bootstrap="Assets/Game/Scenes/Boot.unity";
        public string artRoot="Assets/Game/Content",controllersRoot="Assets/Game/Content/Animations",materialsRoot="Assets/Game/Content/Materials",animationsRoot="Assets/Game/Content",sourcePrefabsRoot="Assets/Game/Content";
        public string editableProbe="Assets/Game/Scenes/Preview/EditableProbe.prefab";
        public string[] nativeRoots={"Assets/Game/Content","Assets/Game/Scenes","Assets/Game/Presentation","Assets/Game/Domain","Assets/TextMesh Pro"},metaRoots={"Assets/Game/Editor/Conversion"};
    }
    // Analysis receipts are grouped by purpose (monkey-project/2.0.0); an older candidate may still hold the flat file.
    internal static string AnalysisFile(string group,string name) {
        var current="Analysis/"+group+"/"+name;var legacy="Analysis/"+name;
        return File.Exists(current)||!File.Exists(legacy)?current:legacy;
    }
    static OutputPaths outputPaths;
    static OutputPaths Paths {
        get {
            if(outputPaths!=null)return outputPaths;
            // Current layout keeps the host locations beside the importer; older formatted candidates kept them in Analysis.
            var config=new[]{"Assets/Game/Editor/Conversion/output-paths.json","Analysis/output-paths.json"}.FirstOrDefault(File.Exists);
            var data=config!=null?JsonUtility.FromJson<OutputPaths>(File.ReadAllText(config)):new OutputPaths();
            if(data==null||data.nativeRoots==null||data.metaRoots==null||data.nativeRoots.Length<1||data.nativeRoots.Length>8||data.metaRoots.Length<1||data.metaRoots.Length>8)throw new InvalidOperationException("Invalid typed output roots");
            foreach(var path in new[]{data.plan,data.prefab,data.scene,data.bootstrap,data.artRoot,data.controllersRoot,data.materialsRoot,data.animationsRoot,data.sourcePrefabsRoot,data.editableProbe}.Concat(data.nativeRoots).Concat(data.metaRoots))
                if(string.IsNullOrEmpty(path)||!path.StartsWith("Assets/",StringComparison.Ordinal)||path.Contains("..")||path.Contains("\\")||path.Contains(":")||path.Contains("\0"))throw new InvalidOperationException("Unsafe typed output location");
            outputPaths=data;return data;
        }
    }
    static string PrefabPath {get{return Paths.prefab;}}
    static string ScenePath {get{return Paths.scene;}}
    static string BootstrapPath {get{return Paths.bootstrap;}}

    [MenuItem("Tools/Monkey/Import Candidate")]
    public static void ImportCandidate() { BeginAsync(Application.isBatchMode); }
    // Explicit fresh-candidate desktop entry point; never close an existing user's scene.
    public static void ImportNewCandidateVisible() {
        if(Application.isBatchMode)throw new InvalidOperationException("VISIBLE_CANDIDATE_REQUIRES_DESKTOP");
        var scene=SceneManager.GetActiveScene();
        var plan=JsonUtility.FromJson<Plan>(File.ReadAllText(Paths.plan));
        if(SceneManager.sceneCount!=1 || scene.isDirty || !string.IsNullOrEmpty(scene.path)
            || AssetDatabase.FindAssets("t:Scene",new[]{"Assets/Game"}).Length!=0
            || plan.sourcePrefabs.Any(x=>File.Exists(x.path)))
            throw new InvalidOperationException("VISIBLE_IMPORT_REQUIRES_FRESH_UNIMPORTED_CANDIDATE");
        Directory.CreateDirectory("Assets/Game/Preview");
        if(!EditorSceneManager.SaveScene(scene,"Assets/Game/Preview/ImportContext.unity"))
            throw new InvalidOperationException("VISIBLE_IMPORT_CONTEXT_SAVE_FAILED");
        ImportCandidate();
    }
    public static void ImportBatch() { ExecuteImport(); }
    public static void ImportBatchAsync() { BeginAsync(true); }

    [Serializable] public class NativeProgress {
        public int schemaVersion=1,processed,total;
        public string status,phase,planSha256; public double elapsedSeconds;
        public bool nativeResumeSupported=false;
    }
    static System.Diagnostics.Stopwatch nativeClock;
    static NativeProgress nativeProgress;
    static DateTime nativeDeadline=DateTime.MaxValue;
    static double nativeBudget=0;
    static Scene ownedScene;
    static Scene priorScene;
    static string firstEngineError;
    static bool handlingFailure;
    [Serializable] public class EngineErrorResult {public int schemaVersion=1;public string planSha256,phase,logType,errorSha256;}
    static void CaptureEngineError(string condition,string stack,LogType type) {
        if(handlingFailure || firstEngineError!=null || (type!=LogType.Error && type!=LogType.Exception && type!=LogType.Assert))return;
        using(var hash=System.Security.Cryptography.SHA256.Create())
            firstEngineError=BitConverter.ToString(hash.ComputeHash(System.Text.Encoding.UTF8.GetBytes(condition+"\n"+stack))).Replace("-","").ToLowerInvariant();
        // Keep messages/stack in the private Editor log, never copy authentication or user text into telemetry.
        try {
            Directory.CreateDirectory("Analysis/Readback");
            File.WriteAllText("Analysis/Readback/native-engine-error.json",JsonUtility.ToJson(new EngineErrorResult {
                planSha256=nativeProgress.planSha256,phase=nativeProgress.phase,logType=type.ToString(),errorSha256=firstEngineError},true));
        } catch { /* The captured flag still stops work if telemetry cannot be written. */ }
    }
    static void CheckEngineErrors() {
        if(firstEngineError!=null)throw new InvalidOperationException("NATIVE_ENGINE_ERROR_RECORDED: inspect the private Editor log and Analysis/Readback/native-engine-error.json");
    }

    static bool asyncRunning,asyncBatch,packagePending,tmpImportCompleted;
    static double nextAsyncTick;
    static void InitializeImport() {
        Application.logMessageReceived-=CaptureEngineError;firstEngineError=null;handlingFailure=false;
        ownedScene=default(Scene);priorScene=default(Scene);nativeProgress=null;
        nativeClock=System.Diagnostics.Stopwatch.StartNew();
        nativeProgress=new NativeProgress {status="running",phase="preflight",planSha256=Hash(Paths.plan)};
        nativeDeadline=DateTime.MaxValue;nativeBudget=0;ownedScene=default(Scene);priorScene=default(Scene);tmpBitmapShader=null;tmpDistanceShader=null;tmpResourceResult=null;
            var budget=Environment.GetEnvironmentVariable("MONKEY_NATIVE_BUDGET_SECONDS");
            if(!string.IsNullOrEmpty(budget) && (!double.TryParse(budget,System.Globalization.NumberStyles.Float,System.Globalization.CultureInfo.InvariantCulture,out nativeBudget) || double.IsNaN(nativeBudget) || double.IsInfinity(nativeBudget) || nativeBudget<1 || nativeBudget>3600))
                throw new InvalidOperationException("Native budget must be 1..3600 seconds");
            var deadline=Environment.GetEnvironmentVariable("MONKEY_NATIVE_DEADLINE_UTC");
            if(!string.IsNullOrEmpty(deadline) && !DateTime.TryParse(deadline,System.Globalization.CultureInfo.InvariantCulture,System.Globalization.DateTimeStyles.AssumeUniversal|System.Globalization.DateTimeStyles.AdjustToUniversal,out nativeDeadline))
                throw new InvalidOperationException("Invalid native deadline");
        Application.logMessageReceived+=CaptureEngineError;

    }
    static void ExecuteImport() {
        if(asyncRunning)throw new InvalidOperationException("An import is already pending in this Editor");
        tmpImportCompleted=false;
        try {InitializeImport();NativeCheckpoint("preflight",0,1);Run();}
        catch(OperationCanceledException) {WriteNativeProgress("budget_exhausted");CloseOwnedScene();}
        catch {if(nativeProgress!=null)WriteNativeProgress("failed");CloseOwnedScene();throw;}
        finally {Application.logMessageReceived-=CaptureEngineError;}
    }
    static void BeginAsync(bool batch) {
        if(asyncRunning)throw new InvalidOperationException("An import is already pending in this Editor");
        asyncRunning=true;asyncBatch=batch;packagePending=false;tmpImportCompleted=false;continuationStarted=false;nextAsyncTick=0;
        try {
            InitializeImport();ValidateEditorContext();
            if(batch && (!Application.isBatchMode || Environment.GetCommandLineArgs().Any(a=>a.StartsWith("-",StringComparison.Ordinal) && a.TrimStart('-').Split('=')[0].Equals("quit",StringComparison.OrdinalIgnoreCase))))
                throw new InvalidOperationException("ASYNC_ENTRYPOINT_REQUIRES_BATCH_WITHOUT_QUIT: use monkey native-import");
            NativeCheckpoint("preflight",0,1);
            EditorApplication.update+=CheckAsyncBudget;
            var plan=JsonUtility.FromJson<Plan>(File.ReadAllText(Paths.plan));
            if(NeedsTmp(plan) && !TmpFilesPresent()) {
                NativeCheckpoint("tmp-resources",0,1);
                var archive=ResolveTmpArchive(plan.tmpResources);
                tmpResourceResult.status="import_pending";WriteTmpResourceResult();packagePending=true;
                AssetDatabase.importPackageCompleted+=TmpPackageCompleted;
                AssetDatabase.importPackageFailed+=TmpPackageFailed;
                AssetDatabase.importPackageCancelled+=TmpPackageCancelled;
                UnityEditor.AssetPackage.Package.Import(archive,false);
                return; // Return to the Editor event loop; no -quit, busy wait or sleeping on the main thread.
            }
            EditorApplication.delayCall+=ContinueAsync;
        } catch(Exception error) {FailAsync(error);}
    }
    static void DetachPackageCallbacks() {
        AssetDatabase.importPackageCompleted-=TmpPackageCompleted;
        AssetDatabase.importPackageFailed-=TmpPackageFailed;
        AssetDatabase.importPackageCancelled-=TmpPackageCancelled;
    }
    static void TmpPackageCompleted(string name) {
        if(!asyncRunning || !packagePending || name!="TMP Essential Resources")return;
        try {
            packagePending=false;tmpImportCompleted=true;DetachPackageCallbacks();
            tmpResourceResult.status="import_completed";WriteTmpResourceResult();
            EditorApplication.delayCall+=ContinueAsync;
        } catch(Exception error) {FailAsync(error);}
    }
    static void TmpPackageFailed(string name,string message) {
        if(asyncRunning && packagePending && name=="TMP Essential Resources") {
            try {tmpResourceResult.status="import_failed";WriteTmpResourceResult();}
            finally {FailAsync(new InvalidOperationException("TMP_ESSENTIAL_IMPORT_FAILED: package completion failed"));}
        }
    }
    static void TmpPackageCancelled(string name) {
        if(asyncRunning && packagePending && name=="TMP Essential Resources") {
            try {tmpResourceResult.status="import_cancelled";WriteTmpResourceResult();}
            finally {FailAsync(new InvalidOperationException("TMP_ESSENTIAL_IMPORT_CANCELLED: package import cancelled"));}
        }
    }
    static bool continuationStarted;
    static void CheckAsyncBudget() {
        if(!asyncRunning || nativeClock.Elapsed.TotalSeconds<nextAsyncTick)return;
        nextAsyncTick=nativeClock.Elapsed.TotalSeconds+1;
        try {
            if(nativeProgress!=null)NativeCheckpoint(nativeProgress.phase,nativeProgress.processed,nativeProgress.total);
            // Package import can consume a delayCall while refreshing assets.
            // Re-enter only after its completion event, from an idle editor tick.
            if(!packagePending && !continuationStarted && !EditorApplication.isCompiling && !EditorApplication.isUpdating)
                ContinueAsync();
        }
        catch(Exception error) {FailAsync(error);}
    }
    static void ContinueAsync() {
        if(!asyncRunning || packagePending || continuationStarted)return;
        continuationStarted=true;
        try {
            NativeCheckpoint("tmp-resources",tmpImportCompleted?1:0,1);
            if(Hash(Paths.plan)!=nativeProgress.planSha256)
                throw new InvalidOperationException("IMPORT_PLAN_CHANGED_WHILE_PENDING");
            Run();FinishAsync(0);
        } catch(Exception error) {FailAsync(error);}
    }
    static void FailAsync(Exception error) {
        if(!asyncRunning)return;
        handlingFailure=true;
        try {if(nativeProgress!=null)WriteNativeProgress(error is OperationCanceledException?"budget_exhausted":"failed");}
        finally {try {CloseOwnedScene();} finally {Debug.LogException(error);FinishAsync(error is OperationCanceledException?3:1);}}
    }
    static void FinishAsync(int exitCode) {
        bool ownsBatch=asyncBatch;asyncRunning=false;packagePending=false;
        DetachPackageCallbacks();EditorApplication.update-=CheckAsyncBudget;EditorApplication.delayCall-=ContinueAsync;
        Application.logMessageReceived-=CaptureEngineError;
        if(ownsBatch && Application.isBatchMode)EditorApplication.Exit(exitCode);
    }
    static void CloseOwnedScene() {
        if(priorScene.IsValid() && priorScene.isLoaded)SceneManager.SetActiveScene(priorScene);
        if(ownedScene.IsValid() && ownedScene.isLoaded) {
            if(SceneManager.sceneCount>1)EditorSceneManager.CloseScene(ownedScene,true);
            else EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        }
    }
    static void WriteNativeProgress(string status) {
        nativeProgress.status=status;nativeProgress.elapsedSeconds=nativeClock.Elapsed.TotalSeconds;
        Directory.CreateDirectory("Analysis/Readback");
        const string path="Analysis/Readback/native-progress.json";const string temporary=path+".tmp";
        File.WriteAllText(temporary,JsonUtility.ToJson(nativeProgress,true));
        if(File.Exists(path))File.Replace(temporary,path,null);else File.Move(temporary,path);
    }
    static void NativeCheckpoint(string phase,int processed,int total) {
        CheckEngineErrors();
        nativeProgress.phase=phase;nativeProgress.processed=processed;nativeProgress.total=total;
        if((nativeBudget>0 && nativeClock.Elapsed.TotalSeconds>=nativeBudget) || DateTime.UtcNow>=nativeDeadline) {
            WriteNativeProgress("budget_exhausted");throw new OperationCanceledException("Native import time budget exhausted");
        }
        WriteNativeProgress("running");
    }
    static Dictionary<string,Sprite> ImportTextures(Plan plan) {
        var sprites=new Dictionary<string,Sprite>();
        const int batchSize=128;
        NativeCheckpoint("textures",0,plan.textures.Length);
        for(int start=0;start<plan.textures.Length;start+=batchSize) {
            NativeCheckpoint("texture-settings",start,plan.textures.Length);
            var batch=plan.textures.Skip(start).Take(batchSize).ToArray();
            // Resolve existing importers before pausing imports; never load unfinished assets inside a batch.
            var importers=new Dictionary<string,TextureImporter>();
            foreach(var item in batch) {
                var importer=AssetImporter.GetAtPath(item.path) as TextureImporter;
                if(importer==null) {
                    AssetDatabase.ImportAsset(item.path,ImportAssetOptions.ForceUpdate|ImportAssetOptions.ForceSynchronousImport);
                    importer=AssetImporter.GetAtPath(item.path) as TextureImporter;
                }
                if(importer==null)throw new InvalidOperationException("Missing texture importer: "+item.path);
                importers.Add(item.id,importer);
            }
            AssetDatabase.StartAssetEditing();
            try {
                foreach(var item in batch) {
                    var importer=importers[item.id];
            importer.textureType = TextureImporterType.Sprite;
            importer.textureShape = TextureImporterShape.Texture2D;
            importer.spriteImportMode = SpriteImportMode.Single;
            importer.spritePixelsPerUnit = plan.pixelsPerUnit;
            importer.spritePivot = new Vector2(.5f,.5f);
            importer.spriteBorder = new Vector4(item.border[0],item.border[1],item.border[2],item.border[3]);
            var settings = new TextureImporterSettings();
            importer.ReadTextureSettings(settings);
            settings.spriteMeshType = SpriteMeshType.FullRect;
            importer.SetTextureSettings(settings);
            importer.mipmapEnabled = false;
            importer.alphaSource = TextureImporterAlphaSource.FromInput;
            importer.alphaIsTransparency = true;
            importer.npotScale = TextureImporterNPOTScale.None;
            importer.textureCompression = TextureImporterCompression.Uncompressed;
            importer.maxTextureSize = 16384;
            // Color space / alpha origin remains unknown in Analysis, never asserted as matched.

                    AssetDatabase.WriteImportSettingsIfDirty(item.path);
                    AssetDatabase.ImportAsset(item.path,ImportAssetOptions.ForceUpdate);
                }
            } finally {AssetDatabase.StopAssetEditing();}
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            foreach(var item in batch) {
                var sprite=AssetDatabase.LoadAssetAtPath<Sprite>(item.path);
                if(sprite==null)throw new InvalidOperationException("Sprite import failed: "+item.path);
                sprites.Add(item.id,sprite);
            }
            NativeCheckpoint("textures",Math.Min(start+batchSize,plan.textures.Length),plan.textures.Length);
        }
        return sprites;
    }

    const string bitmap="Assets/TextMesh Pro/Shaders/TMP_Bitmap-Custom-Atlas.shader";
    const string distance="Assets/TextMesh Pro/Shaders/TMP_SDF.shader";
    const string mobile="Assets/TextMesh Pro/Shaders/TMP_SDF-Mobile.shader";
    const string settings="Assets/TextMesh Pro/Resources/TMP Settings.asset";
    static bool NeedsTmp(Plan plan) {return plan.bitmapFonts.Length>0 || plan.assets.Any(a=>a.path.EndsWith(".ttf",StringComparison.OrdinalIgnoreCase));}
    static bool TmpFilesPresent() {return File.Exists(bitmap) && File.Exists(distance) && File.Exists(mobile) && File.Exists(settings);}
    static string ResolveTmpArchive(TmpResourceSpec spec) {
        if(spec==null || spec.importMode!="package-completion-callback" || spec.packageName!="com.unity.ugui" || spec.packageVersion!="2.6.0" || spec.resource!="Package Resources/TMP Essential Resources.unitypackage")
            throw new InvalidOperationException("TMP_RESOURCE_CONTRACT_MISMATCH: regenerate the supported candidate");
        var package=UnityEditor.PackageManager.PackageInfo.FindForAssetPath("Packages/com.unity.ugui/package.json");
        if(package==null || string.IsNullOrEmpty(package.resolvedPath))
            throw new InvalidOperationException("TMP_PACKAGE_UNRESOLVED: com.unity.ugui");
        if(package.name!=spec.packageName || package.version!=spec.packageVersion)
            throw new InvalidOperationException("TMP_PACKAGE_VERSION_MISMATCH: "+package.name+" "+package.version);
        var archive=Path.Combine(package.resolvedPath,spec.resource);
        if(!File.Exists(archive))throw new InvalidOperationException("TMP_ESSENTIAL_ARCHIVE_MISSING: "+spec.resource);
        tmpResourceResult=new TmpResourceResult {status="resolved",packageName=package.name,packageVersion=package.version,
            source=package.source.ToString(),resource=spec.resource,archiveSha256=Hash(archive),completionProof=tmpImportCompleted?"package-completed-event":"preexisting-files"};
        WriteTmpResourceResult();

        return archive;
    }
    static void EnsureTmpResources(TmpResourceSpec spec) {
        NativeCheckpoint("tmp-resources",0,1);ResolveTmpArchive(spec);
        if(!TmpFilesPresent()) {
            tmpResourceResult.status=asyncRunning?"import_incomplete":"async_entrypoint_required";WriteTmpResourceResult();
            throw new InvalidOperationException(asyncRunning?"TMP_ESSENTIAL_IMPORT_INCOMPLETE: completion event received but required files are absent":"TMP_RESOURCES_REQUIRE_ASYNC_ENTRYPOINT: use monkey native-import; unity run always adds -quit");
        }
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        tmpBitmapShader=AssetDatabase.LoadAssetAtPath<Shader>(bitmap);
        tmpDistanceShader=AssetDatabase.LoadAssetAtPath<Shader>(distance);
        var mobileShader=AssetDatabase.LoadAssetAtPath<Shader>(mobile);
        var settingsAsset=AssetDatabase.LoadAssetAtPath<TMPro.TMP_Settings>(settings);
        if(tmpBitmapShader==null || tmpDistanceShader==null || mobileShader==null || settingsAsset==null) {
            tmpResourceResult.status="assets_not_ready";WriteTmpResourceResult();
            throw new InvalidOperationException("TMP_ESSENTIAL_ASSETS_NOT_READY: required files exist but native assets did not load");
        }
        if(tmpBitmapShader.name!="TextMeshPro/Bitmap Custom Atlas" || tmpDistanceShader.name!="TextMeshPro/Distance Field" || mobileShader.name!="TextMeshPro/Mobile/Distance Field") {
            tmpResourceResult.status="shader_name_mismatch";WriteTmpResourceResult();
            throw new InvalidOperationException("TMP_SHADER_NAME_MISMATCH: no shader substitution permitted");
        }
        tmpResourceResult.bitmapGuid=AssetDatabase.AssetPathToGUID(bitmap);tmpResourceResult.distanceGuid=AssetDatabase.AssetPathToGUID(distance);
        tmpResourceResult.mobileGuid=AssetDatabase.AssetPathToGUID(mobile);tmpResourceResult.settingsGuid=AssetDatabase.AssetPathToGUID(settings);
        tmpResourceResult.status="ready";WriteTmpResourceResult();NativeCheckpoint("tmp-resources",1,1);
    }
    static void WriteTmpResourceResult() {
        Directory.CreateDirectory("Analysis/Readback");File.WriteAllText("Analysis/Readback/tmp-resources.json",JsonUtility.ToJson(tmpResourceResult,true));
    }

    static void ValidateEditorContext() {
        if (Application.unityVersion != "6000.6.2f1")
            throw new InvalidOperationException("Candidate requires Unity 6000.6.2f1; no automatic version migration");
        if (EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isCompiling)
            throw new InvalidOperationException("Editor must be idle");
        if (File.Exists(PrefabPath) || File.Exists(ScenePath) || File.Exists(BootstrapPath))
            throw new InvalidOperationException("Create-only import: Prefab/Scene already exists. Use a new candidate.");
        for(int i=0;i<SceneManager.sceneCount;i++) {
            var open=SceneManager.GetSceneAt(i);
            if(open.isDirty)throw new InvalidOperationException("Open scene has unsaved work; import refused");
            if(string.IsNullOrEmpty(open.path) && !(Application.isBatchMode && SceneManager.sceneCount==1))
                throw new InvalidOperationException("UNTITLED_SCENE_CONTEXT: save or close the user's untitled scene before menu import");
        }
    }

    static void Run()
    {
        ValidateEditorContext();
        var plan = JsonUtility.FromJson<Plan>(File.ReadAllText(Paths.plan));
        var diagnostics = new List<string>();
        foreach(var directory in new[]{Path.GetDirectoryName(PrefabPath),Path.GetDirectoryName(ScenePath),Path.GetDirectoryName(BootstrapPath),Path.GetDirectoryName(Paths.editableProbe),Paths.artRoot,Paths.controllersRoot,Paths.materialsRoot,"Analysis/Readback"})
            Directory.CreateDirectory(directory);
        foreach(var font in plan.bitmapFonts)Directory.CreateDirectory(Path.GetDirectoryName(font.fontPath));
        foreach(var animation in plan.animations.Where(a=>a.convertible))Directory.CreateDirectory(Path.GetDirectoryName(animation.path));
        foreach(var planned in plan.components.SelectMany(c=>new[]{c.controllerPath,c.materialPath,c.normalClipPath,c.pressedClipPath}).Where(v=>!string.IsNullOrEmpty(v))) {
            if(!planned.StartsWith("Assets/",StringComparison.Ordinal)||planned.Contains("..")||planned.Contains("\\"))throw new InvalidOperationException("Unsafe planned native asset path");
            Directory.CreateDirectory(Path.GetDirectoryName(planned));
        }
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        if (plan.sourceDiagnosticCount > 0) diagnostics.Add("SOURCE_GAPS: " + plan.sourceDiagnosticCount);
        if(NeedsTmp(plan))EnsureTmpResources(plan.tmpResources);
        var spriteMap = ImportTextures(plan);
        MonkeyUnityMaterialBindings.CreatedMaterial recoveredMaterial=null;
        if(plan.materialBinding!=null&&!string.IsNullOrEmpty(plan.materialBinding.profile))
            recoveredMaterial=MonkeyUnityMaterialBindings.CreateSaveReadback(plan.materialBinding);
        NativeCheckpoint("fonts",0,plan.bitmapFonts.Length+plan.assets.Count(a=>a.path.EndsWith(".ttf",StringComparison.OrdinalIgnoreCase)));
        var fonts = new Dictionary<string, TMPro.TMP_FontAsset>();
        if(plan.systemFontBinding!=null&&plan.systemFontBinding.status=="prepared") {
            var systemFontReadback=UnitySystemFonts.Import(plan.systemFontBinding,plan.staticFontReceiptPath,plan.staticFontReceiptSha256);
            File.WriteAllText("Analysis/Readback/system-fonts.json",JsonUtility.ToJson(systemFontReadback,true));
            foreach(var fontSpec in plan.systemFontBinding.systemFonts.fonts) {
                var font=AssetDatabase.LoadAssetAtPath<TMPro.TMP_FontAsset>(fontSpec.assetPath);
                if(font==null)throw new InvalidOperationException("SYSTEM_FONT_NATIVE_ASSET_MISSING: "+fontSpec.assetId);
                fonts.Add(fontSpec.assetId,font);
            }
        }
        int fontProgress=0;int fontTotal=plan.bitmapFonts.Length+plan.assets.Count(a=>a.path.EndsWith(".ttf",StringComparison.OrdinalIgnoreCase));
        foreach (var item in plan.assets.Where(a => a.path.EndsWith(".ttf", StringComparison.OrdinalIgnoreCase)))
        {
            NativeCheckpoint("fonts",fontProgress++,fontTotal);
            var source = AssetDatabase.LoadAssetAtPath<Font>(item.path);
            if (source == null) { diagnostics.Add("FONT_IMPORT_FAILED: " + item.id); continue; }
            if (tmpDistanceShader == null) {
                diagnostics.Add("TMP_SHADER_RESOURCES_MISSING: " + item.id); continue;
            }
            var needed = string.Concat(plan.components.Where(c=>c.type=="cc.Label" && c.convertible && c.font==item.id).Select(c=>c.text));
            // Reserve bounded atlas space for the complete declared text set. A
            // 1024 atlas can overflow even when every glyph exists in the TTF.
            // 128 pixels conservatively covers the fixed 90 point / 16 padding
            // import cell; TryAddCharacters remains the strict capacity proof.
            var cellCount = needed.Where(c=>!char.IsControl(c)).Distinct().Count();
            int atlasSize=1024;
            while(atlasSize<4096 && (atlasSize/128)*(atlasSize/128)<cellCount)atlasSize*=2;
            var font = TMPro.TMP_FontAsset.CreateFontAsset(source,90,16,UnityEngine.TextCore.LowLevel.GlyphRenderMode.SDFAA,atlasSize,atlasSize,TMPro.AtlasPopulationMode.Dynamic,false);
            CheckEngineErrors();
            if (font == null) { diagnostics.Add("TMP_FONT_CREATION_FAILED: " + item.id); continue; }
            // An unused original font has no requested glyphs. TMP returns false for
            // an empty request; retain a native dynamic asset backed by that source.
            if (!string.IsNullOrEmpty(needed) && !font.TryAddCharacters(needed,out string missing)) {diagnostics.Add("TTF_GLYPHS_MISSING: " + missing);UnityEngine.Object.DestroyImmediate(font);continue;}
            font.atlasPopulationMode=string.IsNullOrEmpty(needed)?TMPro.AtlasPopulationMode.Dynamic:TMPro.AtlasPopulationMode.Static;
            font.fallbackFontAssetTable=new List<TMPro.TMP_FontAsset>();
            var path = !string.IsNullOrEmpty(item.fontAssetPath)?item.fontAssetPath:item.path.Substring(0,item.path.Length-4) + ".asset";
            if (File.Exists(path)) throw new InvalidOperationException("Font target exists: " + path);
            AssetDatabase.CreateAsset(font,path);
            if (font.material != null) AssetDatabase.AddObjectToAsset(font.material,font);
            foreach (var atlas in font.atlasTextures)
                if (atlas != null) AssetDatabase.AddObjectToAsset(atlas,font);
            EditorUtility.SetDirty(font);
            AssetDatabase.SaveAssetIfDirty(font);
            fonts[item.id] = font;
        }
        foreach (var spec in plan.bitmapFonts) {
            NativeCheckpoint("fonts",fontProgress++,fontTotal);
            var atlasImporter = AssetImporter.GetAtPath(spec.path) as TextureImporter;
            if (atlasImporter == null) throw new InvalidOperationException("Bitmap atlas missing: " + spec.id);
            atlasImporter.textureType = TextureImporterType.Default;
            atlasImporter.textureShape = TextureImporterShape.Texture2D;
            atlasImporter.mipmapEnabled = false; atlasImporter.npotScale = TextureImporterNPOTScale.None;
            atlasImporter.textureCompression = TextureImporterCompression.Uncompressed; atlasImporter.maxTextureSize = 16384;
            atlasImporter.SaveAndReimport();
            AssetDatabase.ImportAsset(spec.path,ImportAssetOptions.ForceSynchronousImport);
            var atlas = AssetDatabase.LoadAssetAtPath<Texture2D>(spec.path);
            if(atlas==null || AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(atlas))!=spec.atlasGuid)
                throw new InvalidOperationException("Original bitmap atlas did not import: "+spec.id+" expected="+spec.atlasGuid+" file="+AssetDatabase.AssetPathToGUID(spec.path)+" type="+AssetDatabase.GetMainAssetTypeAtPath(spec.path));
            var shader = tmpBitmapShader;
            if (shader == null) throw new InvalidOperationException("Native TMP bitmap shader unavailable after resource import");
            var font = ScriptableObject.CreateInstance<TMPro.TMP_FontAsset>();
            // Custom Atlas shader samples RGBA, retaining the source font's colored outline.
            var material = new Material(shader); material.name=Path.GetFileNameWithoutExtension(spec.fontPath)+" Material";
            material.mainTexture=atlas; material.SetColor("_FaceColor",Color.white);
            font.name = Path.GetFileNameWithoutExtension(spec.fontPath);
            font.faceInfo = new UnityEngine.TextCore.FaceInfo {
                familyName=font.name,styleName="Original",pointSize=(int)spec.pointSize,scale=1,
                lineHeight=spec.lineHeight,ascentLine=spec.ascent,descentLine=spec.descent,
                capLine=spec.ascent,meanLine=spec.ascent*.5f,baseline=0
            };
            font.atlasPopulationMode = TMPro.AtlasPopulationMode.Static;
            font.atlasTextures = new[] { atlas };
            font.fallbackFontAssetTable = new List<TMPro.TMP_FontAsset>();

            var serialized = new SerializedObject(font);
            serialized.FindProperty("m_Version").stringValue = "1.1.0";
            serialized.FindProperty("m_Material").objectReferenceValue=material;
            var atlasReferences=serialized.FindProperty("m_AtlasTextures");atlasReferences.arraySize=1;
            atlasReferences.GetArrayElementAtIndex(0).objectReferenceValue=atlas;
            serialized.FindProperty("m_AtlasWidth").intValue = spec.atlasSize[0];
            serialized.FindProperty("m_AtlasHeight").intValue = spec.atlasSize[1];
            serialized.FindProperty("m_AtlasPadding").intValue = 0;
            serialized.FindProperty("m_AtlasRenderMode").intValue=(int)UnityEngine.TextCore.LowLevel.GlyphRenderMode.RASTER;
            serialized.ApplyModifiedPropertiesWithoutUndo();CheckEngineErrors();
            font.atlasTextures=new[]{atlas};font.material=material;material.SetTexture("_MainTex",atlas);
            foreach (var g in spec.glyphs) {
                var glyph = new UnityEngine.TextCore.Glyph(g.index,
                    new UnityEngine.TextCore.GlyphMetrics(g.metrics[0],g.metrics[1],g.metrics[2],g.metrics[3],g.metrics[4]),
                    new UnityEngine.TextCore.GlyphRect(g.rect[0],g.rect[1],g.rect[2],g.rect[3]),1,0);
                font.glyphTable.Add(glyph);font.characterTable.Add(new TMPro.TMP_Character(g.unicode,font,glyph));
            }
            font.fontFeatureTable.glyphPairAdjustmentRecords = new List<UnityEngine.TextCore.LowLevel.GlyphPairAdjustmentRecord>();
            foreach (var k in spec.kernings) {
                font.fontFeatureTable.glyphPairAdjustmentRecords.Add(new UnityEngine.TextCore.LowLevel.GlyphPairAdjustmentRecord {
                    firstAdjustmentRecord=new UnityEngine.TextCore.LowLevel.GlyphAdjustmentRecord(k.first,new UnityEngine.TextCore.LowLevel.GlyphValueRecord(0,0,k.advance,0)),
                    secondAdjustmentRecord=new UnityEngine.TextCore.LowLevel.GlyphAdjustmentRecord(k.second,new UnityEngine.TextCore.LowLevel.GlyphValueRecord(0,0,0,0))
                });
            }
            AssetDatabase.CreateAsset(font,spec.fontPath);AssetDatabase.AddObjectToAsset(material,font);
            font.ReadFontAssetDefinition();EditorUtility.SetDirty(material);EditorUtility.SetDirty(font);AssetDatabase.SaveAssetIfDirty(font);
            AssetDatabase.ImportAsset(spec.fontPath,ImportAssetOptions.ForceSynchronousImport);
            var persisted=AssetDatabase.LoadAssetAtPath<TMPro.TMP_FontAsset>(spec.fontPath);
            if(persisted==null || persisted.atlasTextures.Length!=1 || persisted.atlasTextures[0]==null || persisted.material==null || persisted.material.mainTexture==null ||
                AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(persisted.atlasTextures[0]))!=spec.atlasGuid ||
                AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(persisted.material.mainTexture))!=spec.atlasGuid)
                throw new InvalidOperationException("Saved bitmap atlas/material binding differs: "+spec.id);
            fonts[spec.id]=persisted;
        }
        // Additive preview scene preserves any previously open scene.
        NativeCheckpoint("hierarchy",0,plan.nodes.Length);
        var previous = SceneManager.GetActiveScene();priorScene=previous;
        bool ownedBatchUntitled=Application.isBatchMode && SceneManager.sceneCount==1 && string.IsNullOrEmpty(previous.path) && !previous.isDirty;
        // Only replace the clean startup scene of our dedicated batch process. Never save a user's scene.
        if(ownedBatchUntitled) {previous=default(Scene);priorScene=default(Scene);}
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,ownedBatchUntitled?NewSceneMode.Single:NewSceneMode.Additive);ownedScene=scene;
        if(!EditorSceneManager.SaveScene(scene,BootstrapPath))throw new InvalidOperationException("Isolated bootstrap scene save failed");
        var canvas = new GameObject("MonkeyCandidate",typeof(RectTransform),typeof(Canvas),
            typeof(UnityEngine.UI.CanvasScaler),typeof(UnityEngine.UI.GraphicRaycaster));
        SceneManager.MoveGameObjectToScene(canvas,scene);
        canvas.layer=5;
        var cr = (RectTransform)canvas.transform;
        cr.pivot = Vector2.zero;
        canvas.GetComponent<Canvas>().renderMode = RenderMode.ScreenSpaceOverlay;
        var scaler = canvas.GetComponent<UnityEngine.UI.CanvasScaler>();
        scaler.uiScaleMode = UnityEngine.UI.CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(plan.designSize[0],plan.designSize[1]);
        scaler.matchWidthOrHeight = .5f;
        var designRoot = new GameObject("DesignRoot",typeof(RectTransform));
        designRoot.transform.SetParent(canvas.transform,false);
        var designRect=(RectTransform)designRoot.transform;
        designRect.anchorMin=designRect.anchorMax=new Vector2(.5f,.5f);designRect.pivot=Vector2.zero;
        designRect.sizeDelta=new Vector2(plan.designSize[0],plan.designSize[1]);
        designRect.anchoredPosition=-designRect.sizeDelta*.5f;
        var nodeMap = new Dictionary<string, GameObject>();
        foreach (var node in plan.nodes)
            nodeMap.Add(node.sourceId,new GameObject(node.name,typeof(RectTransform)) {layer=5});
        var nodeSpecs = plan.nodes.ToDictionary(n=>n.sourceId);
        foreach (var node in plan.nodes)
        {
            var go = nodeMap[node.sourceId];
            var parent = node.parent != null && nodeMap.ContainsKey(node.parent) ? nodeMap[node.parent].transform : designRoot.transform;
            var rect = (RectTransform)go.transform;
            rect.SetParent(parent,false);
            var pr = parent as RectTransform;
            // Parent source data is authoritative even when that node is configured later.
            rect.anchorMin = rect.anchorMax = !string.IsNullOrEmpty(node.parent) && nodeSpecs.ContainsKey(node.parent)?
                new Vector2(nodeSpecs[node.parent].anchor[0],nodeSpecs[node.parent].anchor[1]):pr != null ? pr.pivot : Vector2.zero;
            rect.pivot = new Vector2(node.anchor[0],node.anchor[1]);
            rect.sizeDelta = new Vector2(node.size[0],node.size[1]);
            rect.anchoredPosition3D = new Vector3(node.position[0],node.position[1],node.position[2]);
            rect.localRotation = new Quaternion(node.rotation[0],node.rotation[1],node.rotation[2],node.rotation[3]);
            rect.localScale = new Vector3(node.scale[0],node.scale[1],node.scale[2]);
            go.SetActive(node.active);
            if (node.opacity != 255) {
                var opacity = go.AddComponent<CanvasGroup>();
                opacity.alpha = node.opacity / 255f;
            }
        }
        foreach (var node in plan.nodes)
            for (var i=0;i<node.children.Length;i++)
                if (nodeMap.ContainsKey(node.children[i])) nodeMap[node.children[i]].transform.SetSiblingIndex(i);
        int componentProgress=0;
        foreach (var spec in plan.components)
        {
            if(componentProgress++%128==0)NativeCheckpoint("components",componentProgress-1,plan.components.Length);
            if (!spec.convertible || !nodeMap.ContainsKey(spec.node)) {
                diagnostics.Add("COMPONENT_NOT_IMPORTED: " + spec.sourceId + " " + spec.type); continue;
            }
            var go = nodeMap[spec.node]; var node = nodeSpecs[spec.node];
            var color = new Color(node.color[0]/255f,node.color[1]/255f,node.color[2]/255f,node.color[3]/255f);
            if (spec.type == "cc.Sprite")
            {
                var key = spec.spriteFrame + (spec.trim ? "" : "@original");
                if (!string.IsNullOrEmpty(spec.spriteFrame) && !spriteMap.ContainsKey(key)) { diagnostics.Add("SPRITE_MISSING: " + spec.sourceId); continue; }
                if (go.GetComponent<UnityEngine.UI.Graphic>() != null) {
                    diagnostics.Add("MULTIPLE_GRAPHICS_ON_NODE: " + spec.sourceId); continue;
                }
                var image = go.AddComponent<UnityEngine.UI.Image>();
                image.sprite = string.IsNullOrEmpty(spec.spriteFrame)?null:spriteMap[key]; image.color = color; image.raycastTarget = false;
                image.type = spec.mode == 1 ? UnityEngine.UI.Image.Type.Sliced : spec.mode==2 ? UnityEngine.UI.Image.Type.Tiled : UnityEngine.UI.Image.Type.Simple;
                image.enabled = spec.enabled && !string.IsNullOrEmpty(spec.spriteFrame);
            }
            else if(spec.type=="cc.RichText") {
                if(!fonts.ContainsKey(spec.font))throw new InvalidOperationException("RICHTEXT_FONT_MISSING");
                var label=go.AddComponent<TMPro.TextMeshProUGUI>();label.font=fonts[spec.font];label.color=color;
                UnityStaticRichText.Apply(label,spec.staticRichText);
            }
            else if (spec.type == "cc.Label")
            {
                if (spec.font == null || !fonts.ContainsKey(spec.font)) {
                    diagnostics.Add("MATCHING_FONT_MISSING: " + spec.sourceId); continue;
                }
                if (go.GetComponent<UnityEngine.UI.Graphic>() != null) {
                    diagnostics.Add("MULTIPLE_GRAPHICS_ON_NODE: " + spec.sourceId); continue;
                }
                var label = go.AddComponent<TMPro.TextMeshProUGUI>();
                label.font = fonts[spec.font]; label.text = spec.text; label.fontSize = spec.fontSize;
                label.margin=spec.bitmapProbe==null?Vector4.zero:new Vector4(0,0,spec.bitmapProbe.inkRight-spec.bitmapProbe.advance,0);
                label.fontStyle = SourceFontStyles(spec);
                if(spec.bitmapLabel&&(spec.sourceBold||spec.italic||spec.underline)) {
                    var style=go.AddComponent<NativeStaticLabelStyle>();style.Target=label;
                    style.SourceBold=spec.sourceBold;style.SourceItalic=spec.italic;style.SourceUnderline=spec.underline;style.enabled=false;
                }
                label.characterSpacing=spec.fontSize>0?spec.spacing*100f/spec.fontSize:0;
                label.lineSpacing=spec.fontSize>0?(spec.lineHeight-fonts[spec.font].faceInfo.lineHeight*spec.fontSize/fonts[spec.font].faceInfo.pointSize)*100f/spec.fontSize:0;
                label.enableAutoSizing = false; label.richText = false; label.color = color;
                label.raycastTarget = false; label.enabled = spec.enabled;
                label.textWrappingMode = spec.wrap && spec.overflow!=0 ? TMPro.TextWrappingModes.Normal : TMPro.TextWrappingModes.NoWrap;
                var horizontal = new [] { TMPro.HorizontalAlignmentOptions.Left, TMPro.HorizontalAlignmentOptions.Center, TMPro.HorizontalAlignmentOptions.Right };
                var vertical = new [] { TMPro.VerticalAlignmentOptions.Top, TMPro.VerticalAlignmentOptions.Middle, TMPro.VerticalAlignmentOptions.Bottom };
                label.horizontalAlignment = horizontal[Mathf.Clamp(spec.horizontalAlign,0,2)];
                label.verticalAlignment = vertical[Mathf.Clamp(spec.verticalAlign,0,2)];
                ConfigureLabel(go,label,spec,plan.bitmapFonts.Any(f=>f.id==spec.font));
                if(!string.IsNullOrEmpty(spec.codeClassName))MonkeyNumericCode.Bind(spec,label);
                diagnostics.Add("LABEL_LINE_METRICS_REQUIRE_REFERENCE: " + spec.sourceId);
            }
        }
        if(recoveredMaterial!=null) {
            var materialComponents=plan.materialBinding.spriteBindings.ToDictionary(b=>b.sourceId,b=> {
                var c=plan.components.Single(x=>x.sourceId==b.sourceId&&x.convertible);
                return (Component)nodeMap[c.node].GetComponent<UnityEngine.UI.Image>();
            });
            MonkeyUnityMaterialBindings.Bind(plan.materialBinding,recoveredMaterial.asset,materialComponents);
        }
        foreach(var spec in plan.components.Where(c=>c.convertible)) {
            var go=nodeMap[spec.node];var rect=(RectTransform)go.transform;
            if(spec.behaviorBinding!=null&&!string.IsNullOrEmpty(spec.behaviorBinding.typeName))MonkeyBehaviorBindings.Bind(spec.behaviorBinding,go,spec.enabled);
            else if(spec.type=="cc.Widget")ConfigureWidget(go,spec);
            else if(spec.type=="cc.BlockInputEvents") {
                var blocker=go.AddComponent<NativeInputBlocker>();
                blocker.Configure(go.GetComponent<UnityEngine.UI.Graphic>());blocker.enabled=spec.enabled;
            }
            else if(spec.type=="cc.Mask") {
                var mask=go.AddComponent<UnityEngine.UI.RectMask2D>();mask.enabled=spec.enabled;
            }
            else if(spec.type=="cc.Layout") {
                if(go.GetComponent<UnityEngine.UI.LayoutGroup>()!=null || go.GetComponent<UnityEngine.UI.ContentSizeFitter>()!=null)
                    throw new InvalidOperationException("Native layout conflict: "+spec.sourceId);
                if(spec.layoutType==1||spec.layoutType==2){ConfigureLinearLayout(go,spec);continue;}
                ConfigureNativeGrid(go,spec);
            }
            else if(spec.type=="cc.ScrollView") {
                var scroll=go.AddComponent<UnityEngine.UI.ScrollRect>();scroll.enabled=spec.enabled;
                scroll.content=(RectTransform)nodeMap[spec.content].transform;scroll.viewport=(RectTransform)scroll.content.parent;
                scroll.horizontal=spec.horizontal;scroll.vertical=spec.vertical;scroll.inertia=false;
            }
            else if(spec.type=="cc.ProgressBar") {
                var fill=(RectTransform)nodeMap[spec.barNode].transform;
                var image=fill.GetComponent<UnityEngine.UI.Image>();
                if(image==null || image.sprite==null || image.type!=UnityEngine.UI.Image.Type.Tiled || fill.parent!=rect ||
                    go.GetComponent<UnityEngine.UI.Selectable>()!=null ||
                    Mathf.Abs(fill.rect.width-spec.totalLength*spec.progress)>.01f)
                    throw new InvalidOperationException("Progress source geometry/component conflict: "+spec.sourceId);
                var slider=go.AddComponent<UnityEngine.UI.Slider>();
                slider.transition=UnityEngine.UI.Selectable.Transition.None;
                slider.navigation=new UnityEngine.UI.Navigation {mode=UnityEngine.UI.Navigation.Mode.None};
                slider.interactable=false;slider.fillRect=null;slider.handleRect=null;
                slider.minValue=0;slider.maxValue=1;slider.wholeNumbers=false;slider.normalizedValue=spec.progress;
                var driver=go.AddComponent<NativeHorizontalProgressFill>();
                driver.Configure(slider,fill,spec.totalLength);
                driver.enabled=spec.enabled;slider.enabled=spec.enabled;
            }
            else if(spec.type=="cc.Button") {
                var button=go.AddComponent<UnityEngine.UI.Button>();button.enabled=(spec.staticButtonBinding==null||!spec.staticButtonBinding.renderReady)&&spec.enabled;button.interactable=spec.interactable;
                button.targetGraphic=go.GetComponent<UnityEngine.UI.Graphic>();
                if(button.targetGraphic!=null)button.targetGraphic.raycastTarget=true;
                button.transition=UnityEngine.UI.Selectable.Transition.None;
                if(spec.transition==3&&spec.staticButtonBinding==null)ConfigureScaleButton(go,button,spec);
                // No callback stubs: actual source handlers remain in the handoff.
            }
            else if(spec.type=="cc.LabelOutline" && (spec.enabled||spec.staticPresentationPolicy=="source-evidenced-native-renderer-v1")) {
                var label=go.GetComponent<TMPro.TextMeshProUGUI>();
                if(label==null) {diagnostics.Add("OUTLINE_LABEL_MISSING: "+spec.sourceId);continue;}
                if(spec.staticBitmapOutline) {
                    var style=go.GetComponent<NativeStaticLabelStyle>()??go.AddComponent<NativeStaticLabelStyle>();style.Target=label;
                    style.SourceOutlinePresent=true;style.SourceOutlineEnabled=spec.enabled;style.SourceOutlineWidth=spec.width;
                    style.SourceOutlineColor=new Color(spec.outlineColor[0]/255f,spec.outlineColor[1]/255f,spec.outlineColor[2]/255f,spec.outlineColor[3]/255f);
                    style.SourceOutlineComponentId=spec.sourceId;style.enabled=false;continue;
                }
                if(!spec.enabled) {
                    var retainedOutline=go.GetComponent<NativeStaticTextOutline>()??go.AddComponent<NativeStaticTextOutline>();
                    retainedOutline.enabled=false;
                    retainedOutline.Configure(label,spec.width,new Color(spec.outlineColor[0]/255f,spec.outlineColor[1]/255f,spec.outlineColor[2]/255f,spec.outlineColor[3]/255f));
                    continue;
                }
                if(plan.bitmapFonts.Any(f=>fonts.ContainsKey(f.id) && fonts[f.id]==label.font))continue;
                if(plan.systemFontBinding!=null&&plan.systemFontBinding.labelBindings!=null&&plan.systemFontBinding.labelBindings.Length>0) {
                    var outlineColor=new Color(spec.outlineColor[0]/255f,spec.outlineColor[1]/255f,spec.outlineColor[2]/255f,spec.outlineColor[3]/255f);
                    var systemLabelId=SourceOutlineLabel(plan,spec.node);
                    if(systemLabelId!=null)UnitySystemFonts.ApplySourceOutline(label,plan.systemFontBinding,systemLabelId,spec.width,outlineColor);
                    else {
                        var sourceLabel=plan.components.Single(c=>c.node==spec.node&&(c.type=="cc.Label"||c.type=="cc.RichText"));
                        if(string.IsNullOrEmpty(sourceLabel.font)||!fonts.ContainsKey(sourceLabel.font)||label.font!=fonts[sourceLabel.font])
                            throw new InvalidOperationException("OUTLINE_EXPLICIT_FONT_IDENTITY_MISMATCH: "+spec.sourceId);
                        var outline=go.GetComponent<NativeStaticTextOutline>()??go.AddComponent<NativeStaticTextOutline>();
                        outline.Configure(label,spec.width,outlineColor);
                    }
                    label.margin=new Vector4(spec.width,spec.width,spec.width,spec.width);label.UpdateMeshPadding();continue;
                }
                var material=new Material(label.fontSharedMaterial);
                var outlineFont=label.font;
                if(!outlineFont.HasCharacters(label.text)) {
                    var fallback=outlineFont.fallbackFontAssetTable.FirstOrDefault(f=>f!=null&&f.HasCharacters(label.text));
                    if(fallback!=null)outlineFont=fallback;
                }
                var gradient=outlineFont.material.GetFloat("_GradientScale");
                var width=spec.width*outlineFont.faceInfo.pointSize/Mathf.Max(label.fontSize,1)/Mathf.Max(gradient-1,1);
                material.SetFloat("_OutlineWidth",Mathf.Clamp01(width));
                material.EnableKeyword("OUTLINE_ON");
                material.EnableKeyword("RATIOS_OFF");
                material.SetFloat("_FaceDilate",Mathf.Clamp01(width));
                material.SetColor("_OutlineColor",new Color(spec.outlineColor[0]/255f,spec.outlineColor[1]/255f,spec.outlineColor[2]/255f,spec.outlineColor[3]/255f));
                var path=string.IsNullOrEmpty(spec.materialPath)?Paths.materialsRoot+"/"+spec.nativeId+".mat":spec.materialPath;AssetDatabase.CreateAsset(material,path);
                label.fontSharedMaterial=material;
                label.margin=new Vector4(spec.width,spec.width,spec.width,spec.width);
                label.UpdateMeshPadding();
            }
        }
        foreach(var spec in plan.components.Where(c=>c.convertible&&c.type=="cc.Button"&&c.staticButtonBinding!=null&&c.staticButtonBinding.renderReady)) {
            var button=nodeMap[spec.node].GetComponent<UnityEngine.UI.Button>();
            var target=string.IsNullOrEmpty(spec.target)?nodeMap[spec.node]:nodeMap[spec.target];
            button.targetGraphic=target.GetComponent<UnityEngine.UI.Graphic>();
            var retained=button.gameObject.AddComponent<NativeStaticButtonTarget>();
            retained.Target=target;retained.SourceEnabled=spec.staticButtonBinding.sourceEnabled;retained.SourceTransition=spec.transition;retained.SourceZoomScale=spec.zoomScale;retained.SourceDuration=spec.duration;retained.enabled=false;
            if(spec.transition==1&&button.targetGraphic==null&&plan.components.Any(c=>c.node==spec.target&&(c.type=="cc.Sprite"||c.type=="cc.Label"||c.type=="cc.RichText")))
                throw new InvalidOperationException("STATIC_BUTTON_TARGET_GRAPHIC_MISSING: "+spec.sourceId);
            var colors=button.colors;var s=spec.staticButtonBinding;
            colors.normalColor=ButtonColor(s.normalColor);colors.highlightedColor=ButtonColor(s.hoverColor);colors.selectedColor=colors.normalColor;
            colors.pressedColor=ButtonColor(s.pressedColor);colors.disabledColor=ButtonColor(s.disabledColor);colors.fadeDuration=spec.duration;colors.colorMultiplier=1;
            button.colors=colors;button.transition=spec.transition==1?UnityEngine.UI.Selectable.Transition.ColorTint:UnityEngine.UI.Selectable.Transition.None;
        }
        if(plan.toggleBinding!=null){
            var gaps=UnityStaticToggle.Create(plan.toggleBinding,id=>nodeMap.TryGetValue(id,out var n)?n:null,id=>StaticReference(plan,nodeMap,id));
            if(gaps.Length>0)throw new InvalidOperationException("STATIC_TOGGLE_BINDING_FAILED: "+string.Join(",",gaps));
        }
        if(plan.staticControlBindings!=null)CreateStaticControls(plan.staticControlBindings,nodeMap);
        if(plan.staticRetainedAssets!=null&&plan.staticRetainedAssets.schema=="monkey-prefab-static-retained-assets/1")CreateStaticRetainedAssets(plan);
        CreateStaticProgress(plan,nodeMap);
        CreateStaticLayoutCompletion(plan,nodeMap);
        CreateStaticMasks(plan,nodeMap,spriteMap);
        CreateStaticSortIdentities(plan,nodeMap);
        CreateBitmapMissingGlyphs(plan,nodeMap,fonts);
        CreateStaticFields(plan,nodeMap);
        PrepareStaticSpine(plan,nodeMap);
        // Optional native renderers are created after the ordinary UI pass.
        foreach(var spec in plan.components.Where(c=>c.convertible&&c.type=="cc.Button"&&c.staticButtonBinding!=null&&c.staticButtonBinding.renderReady)) {
            var target=string.IsNullOrEmpty(spec.target)?nodeMap[spec.node]:nodeMap[spec.target];
            nodeMap[spec.node].GetComponent<UnityEngine.UI.Button>().targetGraphic=target.GetComponent<UnityEngine.UI.Graphic>();
        }
        PrepareOptionalSpriteOutline(plan.spriteOutlineBindingJson,plan,nodeMap,spriteMap);
        PrepareOptionalStaticTimeMaterials(plan.staticTimeMaterialsJson,plan,nodeMap,spriteMap);
        WarmNativeUiShaderVariants();
        NativeCheckpoint("static-field-references",0,plan.components.Length);
        AssignStaticFields(plan,nodeMap);
        SettleNativeLayout(canvas);
        if (plan.galleryOnly)
        {
            var i=0;
            foreach (var item in plan.textures.Where(t=>!t.id.EndsWith("@original"))) {
                var go=new GameObject("AssetPreview_"+i,typeof(RectTransform),typeof(UnityEngine.UI.Image));
                var rect=(RectTransform)go.transform;rect.SetParent(designRoot.transform,false);
                rect.anchorMin=rect.anchorMax=Vector2.zero; rect.pivot=new Vector2(.5f,.5f);
                rect.anchoredPosition=new Vector2(120+(i%3)*230,1130-(i/3)*230);
                rect.sizeDelta=new Vector2(180,180);
                var image=go.GetComponent<UnityEngine.UI.Image>();image.sprite=spriteMap[item.id];
                image.type=item.border.Any(v=>v>0)?UnityEngine.UI.Image.Type.Sliced:UnityEngine.UI.Image.Type.Simple;
                image.preserveAspect=image.type==UnityEngine.UI.Image.Type.Simple;image.raycastTarget=false;i++;
            }
        }
        var numericCodeExercise=MonkeyNumericCode.Exercise(plan.components,nodeMap);
        NativeCheckpoint("animations",0,plan.animations.Length);
        var motionReadback=BuildMotions(plan,nodeMap);
        if(plan.staticCompletionEnabled)AttachStaticAnimationBindings(plan,nodeMap,motionReadback,plan.staticAnimationEvidence,plan.staticAnimationComponentOrigins);
        var events=new GameObject("EventSystem",typeof(UnityEngine.EventSystems.EventSystem),typeof(UnityEngine.EventSystems.StandaloneInputModule));
        SceneManager.MoveGameObjectToScene(events,scene);
        var sourcePrefabResults=new List<SourcePrefabResult>();
        prefabTemplateHashes=new Dictionary<string,string>();
        foreach(var spec in plan.sourcePrefabs ?? new SourcePrefabSpec[0]) {
            if(string.IsNullOrEmpty(spec.path) || !spec.path.StartsWith(Paths.sourcePrefabsRoot+"/",StringComparison.Ordinal) || spec.path.Contains(".."))
                throw new InvalidOperationException("Invalid source prefab path");
            Directory.CreateDirectory(Path.GetDirectoryName(spec.path));
        }
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        foreach(var spec in plan.sourcePrefabs ?? new SourcePrefabSpec[0]) {
            NativeCheckpoint("source-prefabs",sourcePrefabResults.Count,plan.sourcePrefabs.Length);
            if(!spec.path.StartsWith(Paths.sourcePrefabsRoot+"/",StringComparison.Ordinal) || spec.path.Contains("..") || File.Exists(spec.path))
                throw new InvalidOperationException("Invalid or existing source prefab path: "+spec.path);
            PrepareNativeInstances(plan,spec.sourceId,nodeMap,nodeSpecs);
            AssignStaticFields(plan,nodeMap);
            SettleNativeLayout(canvas);
            if(plan.staticSortQueue!=null && plan.staticSortQueue.Length>0)CreateStaticSortForPrefab(plan,spec,nodeMap);
            var initialPrefabNodes=spec.nodes.Select(id=>DescribeNode(nodeSpecs[id],(RectTransform)nodeMap[id].transform)).ToArray();
            // SaveAsPrefabAsset serializes this subtree without modifying it.
            // A managed active Instantiate can run layout lifecycle callbacks
            // while the cloned hierarchy is still initializing.
            var sourcePrefab=PrefabUtility.SaveAsPrefabAsset(nodeMap[spec.root],spec.path,out bool saved);
            if(!saved || sourcePrefab==null)throw new InvalidOperationException("Source prefab save failed: "+spec.sourceId);
            var nativePrefabType=PrefabUtility.GetPrefabAssetType(sourcePrefab);
            bool rootVariant=(plan.prefabInstances??new PrefabInstanceSpec[0]).Any(p=>p.owner==spec.sourceId&&p.root==spec.root);
            if(nativePrefabType!=(rootVariant?PrefabAssetType.Variant:PrefabAssetType.Regular))throw new InvalidOperationException("Native Prefab/Variant type differs from source relationship");
            prefabTemplateHashes.Add(spec.sourceId,Hash(spec.path));
            var contents=PrefabUtility.LoadPrefabContents(spec.path);GameObject uiContext=null;
            try {
                // A UI Prefab has no Canvas in LoadPrefabContents. Supply the
                // same declared preview context before measuring wrapped TMP
                // lines, without saving or changing the shared asset.
                uiContext=CreatePrefabUiContext(contents,plan);
                InitializeSavedStaticSpine(contents);
                int passes=SettleNativeLayout(contents);
                var transforms=contents.GetComponentsInChildren<Transform>(true);
                int missing=transforms.Sum(t=>GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject));
                int generatedSortNodeCount=transforms.Count(IsWithinGeneratedSortProxy);
                int generatedTextSubmeshCount=transforms.Count(t=>!IsWithinGeneratedSortProxy(t)&&IsGeneratedTextSubmesh(t));
                int generatedSpineSubmeshCount=transforms.Count(t=>!IsWithinGeneratedSortProxy(t)&&IsGeneratedSpineSubmesh(t));
                int reopenedSourceNodeCount=transforms.Length-generatedTextSubmeshCount-generatedSpineSubmeshCount-generatedSortNodeCount;
                if(reopenedSourceNodeCount!=spec.nodeCount || missing!=0) {
                    var treeDiagnostic=DescribeSourcePrefabReopenMismatch(spec,nodeSpecs,contents.transform,transforms);
                    throw new InvalidOperationException("Source prefab reopen mismatch: "+spec.sourceId+
                        ";transforms="+transforms.Length+";expectedSourceNodes="+spec.nodeCount+
                        ";observedSourceNodes="+reopenedSourceNodeCount+";generatedTextSubmesh="+generatedTextSubmeshCount+
                        ";generatedSpineSubmesh="+generatedSpineSubmeshCount+";generatedSort="+generatedSortNodeCount+
                        ";missingScripts="+missing+";unclassifiedOrMissing="+treeDiagnostic);
                }
                var mapped=SavedNodeMap(plan.nodes,contents,spec,nodeSpecs);
                var persistentMap=SavedNodeMap(plan.nodes,sourcePrefab,spec,nodeSpecs);
                var referenceFailures=new List<string>();
                foreach(var c in plan.components.Where(c=>c.convertible&&mapped.ContainsKey(c.node))) {
                    var go=mapped[c.node].gameObject;bool valid=true;
                    if(c.behaviorBinding!=null&&!string.IsNullOrEmpty(c.behaviorBinding.typeName))valid=MonkeyBehaviorBindings.Read(c.behaviorBinding,go,c.enabled);
                    else if(c.type=="cc.Sprite") {
                        var image=go.GetComponent<UnityEngine.UI.Image>();
                        valid=image!=null && (string.IsNullOrEmpty(c.spriteFrame)?image.sprite==null:image.sprite==spriteMap[c.spriteFrame+(c.trim?"":"@original")]);
                        if(recoveredMaterial!=null&&plan.materialBinding.spriteBindings.Any(b=>b.sourceId==c.sourceId))
                            valid=valid&&MonkeyUnityMaterialBindings.ReadBound(plan.materialBinding,recoveredMaterial.asset,image);
                    } else if(c.type=="cc.Label" || c.type=="cc.LabelOutline" || c.type=="cc.RichText") {
                        var label=go.GetComponent<TMPro.TextMeshProUGUI>();
                        valid=label!=null && (c.type=="cc.LabelOutline" || (label.font==fonts[c.font]&&label.text==(c.type=="cc.RichText"&&c.staticRichText!=null?c.staticRichText.unityMarkup:c.text)));
                        if(c.type=="cc.LabelOutline"&&c.staticPresentationPolicy=="source-evidenced-native-renderer-v1") {
                            var expectedColor=new Color(c.outlineColor[0]/255f,c.outlineColor[1]/255f,c.outlineColor[2]/255f,c.outlineColor[3]/255f);
                            if(c.staticBitmapOutline) {
                                var style=go.GetComponent<NativeStaticLabelStyle>();
                                valid=valid&&style!=null&&!style.enabled&&style.Target==label&&style.SourceOutlinePresent&&style.SourceOutlineEnabled==c.enabled&&style.SourceOutlineComponentId==c.sourceId
                                    &&Mathf.Abs(style.SourceOutlineWidth-c.width)<0.00001f&&style.SourceOutlineColor==expectedColor;
                            } else {
                                var outline=go.GetComponent<NativeStaticTextOutline>();
                                valid=valid&&outline!=null&&outline.Target==label&&outline.enabled==c.enabled&&Mathf.Abs(outline.SourceOutlineWidth-c.width)<0.00001f&&outline.SourceOutlineColor==expectedColor;
                            }
                        }
                        if(c.type=="cc.Label") {
                            valid=valid&&label.fontStyle==SourceFontStyles(c);
                            if(c.bitmapLabel&&(c.sourceBold||c.italic||c.underline)) {
                                var style=go.GetComponent<NativeStaticLabelStyle>();
                                valid=valid&&style!=null&&!style.enabled&&style.Target==label&&style.SourceBold==c.sourceBold&&style.SourceItalic==c.italic&&style.SourceUnderline==c.underline&&style.Policy=="cocos24-bitmap-styles-not-rendered-v1";
                            }
                        }
                    } else if(c.type=="cc.Button") {
                        var button=go.GetComponent<UnityEngine.UI.Button>();
                        if(c.staticButtonBinding!=null&&c.staticButtonBinding.renderReady) {
                            // Selectable.Awake fills a null targetGraphic from its
                            // own node, even when disabled. Check the authored
                            // null target on the saved asset plus its exact source
                            // target marker; no transition behavior is claimed.
                            var savedNode=persistentMap[c.node].gameObject;
                            valid=StaticButtonMatches(c,savedNode.GetComponent<UnityEngine.UI.Button>(),string.IsNullOrEmpty(c.target)?savedNode:persistentMap[c.target].gameObject)&&button!=null&&!button.enabled;
                        } else valid=button!=null&&button.targetGraphic==go.GetComponent<UnityEngine.UI.Graphic>();
                    } else if(c.type=="cc.ScrollView") {
                        var scroll=go.GetComponent<UnityEngine.UI.ScrollRect>();valid=scroll!=null&&mapped.ContainsKey(c.content)&&scroll.content==mapped[c.content];
                    } else if(c.type=="cc.ProgressBar") {
                        var slider=go.GetComponent<UnityEngine.UI.Slider>();
                        var driver=go.GetComponent<NativeHorizontalProgressFill>();
                        valid=slider!=null&&driver!=null&&driver.Progress==slider&&mapped.ContainsKey(c.barNode)&&
                            driver.Fill==mapped[c.barNode]&&Mathf.Abs(driver.FullLength-c.totalLength)<.001f&&
                            Mathf.Abs(slider.normalizedValue-c.progress)<.0001f&&slider.fillRect==null&&slider.handleRect==null&&!slider.interactable;
                    } else if(c.type=="cc.BlockInputEvents")valid=go.GetComponent<NativeInputBlocker>()!=null && go.GetComponent<NativeInputBlocker>().Surface!=null;
                    else if(c.type=="cc.Mask")valid=go.GetComponent<UnityEngine.UI.RectMask2D>()!=null;
                    else if(c.type=="cc.Layout")valid=go.GetComponent<UnityEngine.UI.LayoutGroup>()!=null;
                    if(!valid)referenceFailures.Add(c.sourceId);
                }
                ReadSavedStaticSpine(mapped.ToDictionary(x=>x.Key,x=>x.Value.gameObject),spec.sourceId);
                ReadSavedOptionalSpriteOutline(persistentMap.ToDictionary(x=>x.Key,x=>x.Value.gameObject),spec.sourceId);
                ReadSavedOptionalStaticTimeMaterials(persistentMap.ToDictionary(x=>x.Key,x=>x.Value.gameObject),spec.sourceId);
                var numericBindings=plan.components.Where(c=>c.convertible&&!string.IsNullOrEmpty(c.codeClassName)&&persistentMap.ContainsKey(c.node)).Select(c=>MonkeyNumericCode.Read(c,persistentMap[c.node].gameObject)).ToArray();
                var behaviorBindings=plan.components.Where(c=>c.convertible&&c.behaviorBinding!=null&&!string.IsNullOrEmpty(c.behaviorBinding.typeName)&&persistentMap.ContainsKey(c.node)).Select(c=>MonkeyBehaviorBindings.ReadPersistent(c.behaviorBinding,persistentMap[c.node].gameObject,c.sourceId,c.enabled)).ToArray();
                sourcePrefabResults.Add(new SourcePrefabResult {generatedSortNodeCount=generatedSortNodeCount,staticSortFields=plan.staticSortQueue==null||plan.staticSortQueue.Length==0?null:ReadStaticSortForPrefab(plan,spec,persistentMap.ToDictionary(x=>x.Key,x=>x.Value.gameObject),mapped.ToDictionary(x=>x.Key,x=>x.Value.gameObject)),bitmapMissingGlyphFields=ReadBitmapMissingGlyphs(plan,persistentMap.ToDictionary(x=>x.Key,x=>x.Value.gameObject),mapped.ToDictionary(x=>x.Key,x=>x.Value.gameObject),fonts),staticLayoutProbe=RunStaticLayoutPrefabProbe(plan,spec,contents),staticMaskFields=ReadStaticMasks(plan,mapped.ToDictionary(x=>x.Key,x=>x.Value.gameObject),persistentMap.ToDictionary(x=>x.Key,x=>x.Value.gameObject),spriteMap),staticLayoutFields=ReadStaticLayoutCompletion(plan,persistentMap.ToDictionary(x=>x.Key,x=>x.Value.gameObject)),toggleFields=ReadStaticToggles(plan,persistentMap.ToDictionary(x=>x.Key,x=>x.Value.gameObject)),prefabInstances=ReadNativeInstances(plan,mapped,spec.sourceId),numericCodeBindings=numericBindings,behaviorBindings=behaviorBindings,staticControlFields=plan.staticControlBindings==null?null:ReadStaticControls(plan.staticControlBindings.Where(x=>persistentMap.ContainsKey(x.node)).ToArray(),persistentMap.ToDictionary(x=>x.Key,x=>x.Value.gameObject)),staticAnimationFields=!plan.staticCompletionEnabled?null:ReadSavedStaticAnimationBindings(plan,persistentMap.ToDictionary(x=>x.Key,x=>x.Value.gameObject),motionReadback,plan.staticAnimationEvidence,plan.staticAnimationComponentOrigins),staticProgressFields=ReadStaticProgress(plan,persistentMap.ToDictionary(x=>x.Key,x=>x.Value.gameObject)),staticFieldBindings=ReadStaticFields(plan,persistentMap.ToDictionary(x=>x.Key,x=>x.Value.gameObject)),sourceId=spec.sourceId,path=spec.path,
                    nativePrefabType=nativePrefabType.ToString(),nativeInitialNodes=initialPrefabNodes,
                    guid=AssetDatabase.AssetPathToGUID(spec.path),nodeCount=transforms.Length-generatedTextSubmeshCount-generatedSpineSubmeshCount-generatedSortNodeCount,generatedTextSubmeshCount=generatedTextSubmeshCount,generatedSpineSubmeshCount=generatedSpineSubmeshCount,missingScripts=missing,
                    savedReloaded=true,geometryPhase="native-layout-settled-v1",layoutSettlePasses=passes,
                    nodes=spec.nodes.Select(id=>DescribeNode(nodeSpecs[id],mapped[id])).ToArray(),
                    referencesVerified=referenceFailures.Count==0,referenceFailures=referenceFailures.ToArray()});
                CaptureSourcePrefabPreview(sourcePrefab,spec,plan,sourcePrefabResults[sourcePrefabResults.Count-1]);
                // Preserve actual per-Prefab readback even if a later Prefab fails.
                // This is a partial receipt, never the final aggregate verdict.
                var receiptPath="Analysis/Readback/Prefabs/"+AssetDatabase.AssetPathToGUID(spec.path)+".json";
                Directory.CreateDirectory(Path.GetDirectoryName(receiptPath));
                using(var receipt=new StreamWriter(new FileStream(receiptPath,FileMode.CreateNew,FileAccess.Write)))
                    receipt.Write(JsonUtility.ToJson(sourcePrefabResults[sourcePrefabResults.Count-1],true));
            } finally {
                if(uiContext!=null){contents.transform.SetParent(null,false);UnityEngine.Object.DestroyImmediate(uiContext);}
                PrefabUtility.UnloadPrefabContents(contents);
            }
        }
        foreach(var owner in (plan.prefabInstances??new PrefabInstanceSpec[0]).Select(p=>p.owner).Distinct().Where(s=>!prefabTemplateHashes.ContainsKey(s)))
            PrepareNativeInstances(plan,owner,nodeMap,nodeSpecs);
        var view = canvas.AddComponent<ContentPreviewView>();
        view.Images = canvas.GetComponentsInChildren<UnityEngine.UI.Image>(true);
        view.Labels = canvas.GetComponentsInChildren<TMPro.TextMeshProUGUI>(true);
        view.Buttons = canvas.GetComponentsInChildren<UnityEngine.UI.Button>(true);
        SettleNativeLayout(canvas);
        var initialSceneNodes=plan.nodes.Select(n=>DescribeNode(n,(RectTransform)nodeMap[n.sourceId].transform)).ToArray();
        NativeCheckpoint("candidate-save",0,1);
        var prefab = PrefabUtility.SaveAsPrefabAsset(canvas,PrefabPath,out var success);
        if (!success || prefab == null) throw new InvalidOperationException("Native Prefab save failed");
        var candidatePrefabProofs=new PrefabInstanceResult[0];
        if((plan.prefabInstances??new PrefabInstanceSpec[0]).Any(p=>(p.mountedChildren??new PrefabMountedChildren[0]).Length>0||(p.mountedComponents??new PrefabMountedComponent[0]).Length>0)) {
            var candidateContents=PrefabUtility.LoadPrefabContents(PrefabPath);
            try {candidatePrefabProofs=ReadNativeInstances(plan,SavedNodeMap(plan.nodes,candidateContents),null,PrefabPath,true);}
            finally {PrefabUtility.UnloadPrefabContents(candidateContents);}
        }
        UnityEngine.Object.DestroyImmediate(canvas);
        var instance=(GameObject)PrefabUtility.InstantiatePrefab(prefab,scene);
        if (!EditorSceneManager.SaveScene(scene,ScenePath)) throw new InvalidOperationException("Native scene save failed");
        NativeCheckpoint("scene-reopen",0,1);
        if(ownedBatchUntitled) {
            // Opening the saved scene in Single mode normally closes/reloads the only owned scene.
            scene=EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
        } else {
            if(!EditorSceneManager.CloseScene(scene,true))throw new InvalidOperationException("Owned scene close failed");
            scene=EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Additive);
        }
        ownedScene=scene;
        if(!scene.IsValid() || !scene.isLoaded)throw new InvalidOperationException("Saved scene reopen failed");
        instance=scene.GetRootGameObjects().FirstOrDefault(go=>go.GetComponent<ContentPreviewView>()!=null);
        if(instance==null)throw new InvalidOperationException("Reopened scene has no serialized candidate view");
        SettleNativeLayout(instance);
        if(!EditorSceneManager.SaveScene(scene,ScenePath))throw new InvalidOperationException("Settled native scene save failed");
        NativeCheckpoint("scene-reopen",1,1);
        NativeCheckpoint("native-readback",0,1);
        var gallery=plan.galleryOnly?ReadSavedGallery(plan,instance):new GalleryResult[0];
        var savedNodeMap=plan.galleryOnly?new Dictionary<string,RectTransform>():SavedNodeMap(plan.nodes,instance);
        var readback = new Readback {
            materialBinding=recoveredMaterial==null?null:recoveredMaterial.readback,
            prefabInstances=ReadNativeInstances(plan,savedNodeMap,null,PrefabPath),candidatePrefabInstances=candidatePrefabProofs,
            nativeScope=plan.galleryOnly?"resources-and-gallery-only":"source-node-subset",sourceGraphVerification=plan.galleryOnly?"not_run":"saved-source-node-subset",gallery=gallery,
            numericCodeExercise=numericCodeExercise,numericCodeBindings=plan.components.Where(c=>c.convertible&&!string.IsNullOrEmpty(c.codeClassName)).Select(c=>MonkeyNumericCode.Read(c,savedNodeMap[c.node].gameObject)).ToArray(),
            sourcePrefabs=sourcePrefabResults.ToArray(),tmpResources=tmpResourceResult,sceneReopened=true,
            jsonAssets=plan.assets.Where(a=>a.kind=="cc.JsonAsset").Select(a=> {
                var text=AssetDatabase.LoadAssetAtPath<TextAsset>(a.path);
                if(text==null)throw new InvalidOperationException("JsonAsset TextAsset import failed: "+a.id);
                using(var hash=System.Security.Cryptography.SHA256.Create())return new JsonResult {id=a.id,guid=AssetDatabase.AssetPathToGUID(a.path),
                    textSha256=BitConverter.ToString(hash.ComputeHash(System.Text.Encoding.UTF8.GetBytes(text.text))).Replace("-","").ToLowerInvariant()};
            }).ToArray(),
            dynamicUiProbes=ProbeDynamicUi(plan,instance),nativeInitialNodes=initialSceneNodes,status=diagnostics.Count==0?"imported":"partial",unityVersion=Application.unityVersion,
            prefabGuid=AssetDatabase.AssetPathToGUID(PrefabPath),sceneGuid=AssetDatabase.AssetPathToGUID(ScenePath),
            staticRetainedAssetReadback=plan.staticRetainedAssets==null||plan.staticRetainedAssets.schema!="monkey-prefab-static-retained-assets/1"?null:ReadStaticRetainedAssets(plan),animations=motionReadback,spriteCount=spriteMap.Count,nodeCount=nodeMap.Count,
            missingScripts=instance.GetComponentsInChildren<Transform>(true).Sum(t=>GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject)),
            diagnostics=diagnostics.ToArray(),
            nodes=plan.nodes.Select(n=>{
                // Resolve the reloaded scene once by sibling-index paths, independent of names.
                var target=savedNodeMap[n.sourceId];
                return DescribeNode(n,target);
            }).ToArray(),
            fonts=fonts.Select(pair=>new FontResult { id=pair.Key,guid=AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(pair.Value)),
                atlasGuid=pair.Value.atlasTextures.Length>0 && pair.Value.atlasTextures[0]!=null?AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(pair.Value.atlasTextures[0])):"",
                materialAtlasGuid=pair.Value.material!=null && pair.Value.material.mainTexture!=null?AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(pair.Value.material.mainTexture)):"",
                glyphCount=pair.Value.glyphTable.Count,characterCount=pair.Value.characterTable.Count,
                pointSize=pair.Value.faceInfo.pointSize,lineHeight=pair.Value.faceInfo.lineHeight }).ToArray(),
            labels=plan.components.Where(c=>c.convertible && c.type=="cc.Label").Select(c=>
                ReadSavedLabel(c,savedNodeMap[c.node],plan.bitmapFonts.Any(f=>f.id==c.font))).ToArray(),
            sprites=plan.textures.Select(t=>{
                var s=spriteMap[t.id];AssetDatabase.TryGetGUIDAndLocalFileIdentifier(s,out string g,out long id);
                var textureImporter=AssetImporter.GetAtPath(t.path) as TextureImporter;
                if(textureImporter==null||textureImporter.alphaSource!=TextureImporterAlphaSource.FromInput)throw new InvalidOperationException("SOURCE_TEXTURE_ALPHA_NOT_PRESERVED: "+t.id);
                return new SpriteResult {id=t.id,guid=g,fileId=id,alphaSource=textureImporter.alphaSource.ToString(),size=new[]{s.rect.width,s.rect.height},
                    border=new[]{s.border.x,s.border.y,s.border.z,s.border.w}};
            }).ToArray()
        };
        var savedView=instance.GetComponent<ContentPreviewView>();
        readback.viewReferences=plan.components.Where(c=>c.convertible && new[]{"cc.Sprite","cc.Label","cc.Button"}.Contains(c.type)).Select(c=> {
            var node=savedNodeMap[c.node];
            Component component=null;string field;int index;
            if(c.type=="cc.Sprite") {component=node.GetComponent<UnityEngine.UI.Image>();field="Images";index=Array.IndexOf(savedView.Images,component as UnityEngine.UI.Image);}
            else if(c.type=="cc.Label") {component=node.GetComponent<TMPro.TextMeshProUGUI>();field="Labels";index=Array.IndexOf(savedView.Labels,component as TMPro.TextMeshProUGUI);}
            else {component=node.GetComponent<UnityEngine.UI.Button>();field="Buttons";index=Array.IndexOf(savedView.Buttons,component as UnityEngine.UI.Button);}
            var source=component!=null?PrefabUtility.GetCorrespondingObjectFromSource(component):null;
            long fileId=0;if(source!=null)AssetDatabase.TryGetGUIDAndLocalFileIdentifier(source,out string ignoredGuid,out fileId);
            return new ViewReference {sourceId=c.sourceId,field=field,index=index,prefabFileId=fileId,bound=component!=null && index>=0};
        }).ToArray();
        readback.editableRoundtrip=CheckEditableClone();
        readback.colorSpace=QualitySettings.activeColorSpace.ToString();
        try {
            var preview="Analysis/Readback/native-page.png";
            Capture(instance.GetComponent<Canvas>(),scene,(int)plan.designSize[0],(int)plan.designSize[1],preview);
            readback.previewPath=preview;readback.previewSha256=Hash(preview);
        }
        catch(Exception exception) {readback.previewError=exception.Message;}
        if (!EditorSceneManager.SaveScene(scene,ScenePath)) throw new InvalidOperationException("Scene save after native preview failed");
        Directory.CreateDirectory("Analysis/Readback");
        File.WriteAllText("Analysis/Readback/source-prefabs-readback.json",JsonUtility.ToJson(readback,true));
        readback.staticPreviews=BuildStaticPreviews(plan);
        readback.staticPreview=readback.staticPreviews.LastOrDefault();
        readback.nativeFiles = Paths.nativeRoots.Where(Directory.Exists).SelectMany(folder=>Directory.GetFiles(folder,"*",SearchOption.AllDirectories))
            .Concat(Paths.metaRoots.Where(Directory.Exists).SelectMany(folder=>Directory.GetFiles(folder,"*.meta",SearchOption.AllDirectories)))
            .OrderBy(path=>path,StringComparer.Ordinal).Select(path=>new FileResult {
                path=path.Replace('\\','/'), sha256=Hash(path)
            }).ToArray();
        Directory.CreateDirectory("Analysis/Readback");
        File.WriteAllText("Analysis/Readback/editor-readback.json",JsonUtility.ToJson(readback,true));
        nativeProgress.phase="complete";nativeProgress.processed=1;nativeProgress.total=1;WriteNativeProgress(readback.status=="imported"?"completed":"completed_partial");
        Debug.Log("Monkey native import: "+readback.status+"; readback Analysis/Readback/editor-readback.json");
        if (previous.IsValid()) SceneManager.SetActiveScene(previous);
        if(!Application.isBatchMode&&plan.previewState!=null&&!string.IsNullOrEmpty(plan.previewState.stateSha256))EditorApplication.delayCall+=OpenStaticPreview;
        // Keep the candidate scene open for editing; no global SaveAssets, no other scenes saved.
    }
    static bool CheckEditableClone() {
        var path=Paths.editableProbe;
        if(!AssetDatabase.CopyAsset(PrefabPath,path))throw new InvalidOperationException("Native editable probe copy failed");
        var contents=PrefabUtility.LoadPrefabContents(path);var original=contents.transform.GetChild(0).name;
        try {
            contents.transform.GetChild(0).name=original+"__EditProbe";
            PrefabUtility.SaveAsPrefabAsset(contents,path,out bool saved);
            if(!saved)throw new InvalidOperationException("Native edit/save probe failed");
        }
        finally {PrefabUtility.UnloadPrefabContents(contents);}
        contents=PrefabUtility.LoadPrefabContents(path);
        try {
            bool persisted=contents.transform.GetChild(0).name==original+"__EditProbe";
            contents.transform.GetChild(0).name=original;
            PrefabUtility.SaveAsPrefabAsset(contents,path,out bool saved);
            return persisted && saved && contents.GetComponent<ContentPreviewView>()!=null;
        }
        finally {PrefabUtility.UnloadPrefabContents(contents);}
    }
    static void CaptureSourcePrefabPreview(GameObject prefab,SourcePrefabSpec spec,Plan plan,SourcePrefabResult result) {
        // A separate throwaway scene prevents other windows from covering this
        // diagnostic image. Only root visibility is overridden and disclosed;
        // no source child state, transform, script or asset is repaired here.
        Scene probe=default(Scene);
        result.isolatedPreviewScope="isolated-clone-root-active-source-child-state-no-business-execution";
        try {
            probe=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Additive);
            var context=new GameObject("OwnedIsolatedPrefabPreview",typeof(RectTransform),typeof(Canvas));
            SceneManager.MoveGameObjectToScene(context,probe);
            var canvas=context.GetComponent<Canvas>();canvas.renderMode=RenderMode.WorldSpace;
            ((RectTransform)context.transform).sizeDelta=new Vector2(plan.designSize[0],plan.designSize[1]);
            var clone=UnityEngine.Object.Instantiate(prefab,context.transform,false);
            clone.SetActive(true);SettleNativeLayout(context);
            var path="Analysis/Readback/Prefabs/"+AssetDatabase.AssetPathToGUID(spec.path)+".png";
            Capture(canvas,probe,(int)plan.designSize[0],(int)plan.designSize[1],path);
            result.isolatedPreviewPath=path;result.isolatedPreviewSha256=Hash(path);
        } catch(Exception error) {result.isolatedPreviewError=error.Message;}
        finally {if(probe.IsValid())EditorSceneManager.CloseScene(probe,true);}
    }
    static void Capture(Canvas canvas,Scene scene,int width,int height,string output,bool preserveWorldSpace=false) {
        if(SystemInfo.graphicsDeviceType==UnityEngine.Rendering.GraphicsDeviceType.Null)
            throw new InvalidOperationException("Native preview unavailable: Null graphics device; rerun native-import with --render-preview");
        var cameraObject=new GameObject("MonkeyPreviewCamera",typeof(Camera));SceneManager.MoveGameObjectToScene(cameraObject,scene);
        var camera=cameraObject.GetComponent<Camera>();camera.enabled=false;camera.orthographic=true;camera.orthographicSize=height*.5f;
        camera.cullingMask=1<<5;camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.1f,.11f,.13f,1);
        camera.transform.position=new Vector3(0,0,-10);camera.nearClipPlane=.1f;camera.farClipPlane=100;
        var target=new RenderTexture(width,height,24,RenderTextureFormat.ARGB32);target.Create();camera.targetTexture=target;
        var previousMode=canvas.renderMode;var previousCamera=canvas.worldCamera;var previousDistance=canvas.planeDistance;
        var previousActive=RenderTexture.active;Texture2D image=null;
        try {
            foreach(var transform in canvas.GetComponentsInChildren<Transform>(true))transform.gameObject.layer=5;
            if(preserveWorldSpace) {
                if(previousMode!=RenderMode.WorldSpace||previousCamera==null)throw new InvalidOperationException("STATIC_PREVIEW_CAMERA_CONTEXT_MISSING");
                camera.transform.position=previousCamera.transform.position;
            } else {canvas.renderMode=RenderMode.ScreenSpaceCamera;canvas.planeDistance=1;}
            canvas.worldCamera=camera;
            Canvas.ForceUpdateCanvases();camera.Render();RenderTexture.active=target;
            image=new Texture2D(width,height,TextureFormat.RGBA32,false);
            image.ReadPixels(new Rect(0,0,width,height),0,0);image.Apply();
            Directory.CreateDirectory(Path.GetDirectoryName(output));File.WriteAllBytes(output,image.EncodeToPNG());
        }
        finally {
            canvas.renderMode=previousMode;canvas.worldCamera=previousCamera;canvas.planeDistance=previousDistance;
            RenderTexture.active=previousActive;camera.targetTexture=null;
            target.Release();UnityEngine.Object.DestroyImmediate(target);UnityEngine.Object.DestroyImmediate(cameraObject);
            if(image!=null)UnityEngine.Object.DestroyImmediate(image);
            Canvas.ForceUpdateCanvases();
        }
    }
    static void ConfigureScaleButton(GameObject go,UnityEngine.UI.Button button,ComponentSpec spec) {
        var planned=!string.IsNullOrEmpty(spec.controllerPath);
        var path=planned?spec.controllerPath.Substring(0,spec.controllerPath.Length-".controller".Length):Paths.controllersRoot+"/"+spec.nativeId;
        var separator=planned?"_":"-";
        var normalPath=string.IsNullOrEmpty(spec.normalClipPath)?path+separator+"normal.anim":spec.normalClipPath;
        var pressedPath=string.IsNullOrEmpty(spec.pressedClipPath)?path+separator+"pressed.anim":spec.pressedClipPath;
        var controller=CreateScaleButtonController(path+".controller",normalPath,pressedPath,go.transform.localScale,spec.zoomScale,spec.duration);
        var animator=go.AddComponent<Animator>();animator.runtimeAnimatorController=controller;
        button.transition=UnityEngine.UI.Selectable.Transition.Animation;
        EditorUtility.SetDirty(controller);AssetDatabase.SaveAssetIfDirty(controller);
    }
    static NodeResult DescribeNode(NodeSpec source,RectTransform rect) {
        float opacity=255f;float[] color=null;
        if(!string.IsNullOrEmpty(source.sourceGeometryProfile)) {
            var group=rect.GetComponent<CanvasGroup>();opacity=(group!=null&&group.enabled?group.alpha:1f)*255f;
            if(Math.Abs(opacity-source.opacity)>.001f)throw new InvalidOperationException("Source UI opacity differs: "+source.sourceId);
            if(source.verifyUiColor) {
                var graphic=rect.GetComponent<UnityEngine.UI.Graphic>();
                if(graphic==null)throw new InvalidOperationException("Source UI renderer missing");
                var c=graphic.color;color=new[]{c.r*255f,c.g*255f,c.b*255f,c.a*255f};
                if(color.Where((value,index)=>Math.Abs(value-source.color[index])>.001f).Any())throw new InvalidOperationException("Source UI renderer color differs: "+source.sourceId);
            }
        }
        return new NodeResult {sourceId=source.sourceId,hierarchy=rect.name,size=new[]{rect.rect.width,rect.rect.height},
            pivot=new[]{rect.pivot.x,rect.pivot.y},position=new[]{rect.localPosition.x,rect.localPosition.y,rect.localPosition.z},
            scale=new[]{rect.localScale.x,rect.localScale.y,rect.localScale.z},
            rotation=new[]{rect.localRotation.x,rect.localRotation.y,rect.localRotation.z,rect.localRotation.w},
            color=color,opacity=opacity,active=rect.gameObject.activeSelf,componentTypes=rect.GetComponents<Component>().Select(c=>c.GetType().FullName).ToArray()};
    }
    static void WarmNativeUiShaderVariants() {
        const string folder="Assets/Game/Content/Shaders";
        if(!AssetDatabase.IsValidFolder(folder))return;
        var variants=new ShaderVariantCollection();
        try {
            foreach(var guid in AssetDatabase.FindAssets("t:Shader",new[]{folder})) {
                var shader=AssetDatabase.LoadAssetAtPath<Shader>(AssetDatabase.GUIDToAssetPath(guid));
                if(shader==null||!shader.keywordSpace.FindKeyword("UNITY_UI_CLIP_RECT").isValid)continue;
                variants.Add(new ShaderVariantCollection.ShaderVariant(shader,UnityEngine.Rendering.PassType.Normal,new[]{"UNITY_UI_CLIP_RECT"}));
                if(shader.keywordSpace.FindKeyword("UNITY_UI_ALPHACLIP").isValid)
                    variants.Add(new ShaderVariantCollection.ShaderVariant(shader,UnityEngine.Rendering.PassType.Normal,new[]{"UNITY_UI_CLIP_RECT","UNITY_UI_ALPHACLIP"}));
            }
            variants.WarmUp();CheckEngineErrors();
        } finally {UnityEngine.Object.DestroyImmediate(variants);}
    }
    static int SettleNativeLayout(GameObject root) {
        // Refresh glyph presentation outside serialization/OnValidate callbacks.
        foreach(var outline in root.GetComponentsInChildren<NativeStaticTextOutline>(true).Where(o=>o.enabled)) {
            var outlineState=outline.RefreshNow();
            if(outlineState==null||outlineState.status=="failed")throw new InvalidOperationException("NATIVE_TEXT_OUTLINE_REFRESH_FAILED: "+outline.name+":"+String.Join(",",outlineState?.diagnostics??Array.Empty<string>()));
        }
        var groups=root.GetComponentsInChildren<UnityEngine.UI.LayoutGroup>(true).Where(g=>g.isActiveAndEnabled).Reverse().ToArray();
        var fitters=root.GetComponentsInChildren<UnityEngine.UI.ContentSizeFitter>(true).Where(f=>f.isActiveAndEnabled).ToArray();
        var constraints=root.GetComponentsInChildren<NativeRectConstraints>(true).Where(f=>f.isActiveAndEnabled).ToArray();
        if(groups.Length==0&&fitters.Length==0&&constraints.Length==0)return 0;
        var controllers=groups.Select(g=>(RectTransform)g.transform).Concat(fitters.Select(f=>(RectTransform)f.transform)).Distinct().ToArray();
        var rects=root.GetComponentsInChildren<RectTransform>(true);
        Func<RectTransform,Vector4> value=r=>new Vector4(r.rect.width,r.rect.height,r.localPosition.x,r.localPosition.y);
        for(int pass=0;pass<8;pass++) {
            if(nativeProgress!=null)NativeCheckpoint(nativeProgress.phase,nativeProgress.processed,nativeProgress.total);
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
    static GalleryResult[] ReadSavedGallery(Plan plan,GameObject instance) {
        if(plan.nodes.Length!=0 || plan.components.Length!=0 || plan.sourcePrefabs.Length!=0)throw new InvalidOperationException("Gallery cannot stand in for a source graph");
        var expected=plan.textures.Where(t=>!t.id.EndsWith("@original")).ToArray();var design=instance.transform.Find("DesignRoot");
        if(design==null || design.childCount!=expected.Length)throw new InvalidOperationException("Saved gallery boundary differs");
        var result=new GalleryResult[expected.Length];
        for(int i=0;i<expected.Length;i++) {
            var rect=design.GetChild(i)as RectTransform;var image=rect!=null?rect.GetComponent<UnityEngine.UI.Image>():null;var spec=expected[i];
            var type=spec.border.Any(v=>v>0)?UnityEngine.UI.Image.Type.Sliced:UnityEngine.UI.Image.Type.Simple;
            if(rect==null || rect.name!="AssetPreview_"+i || rect.childCount!=0 || image==null || image.sprite==null || image.type!=type || image.raycastTarget || image.preserveAspect!=(type==UnityEngine.UI.Image.Type.Simple) ||
               AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(image.sprite))!=spec.guid ||
               (rect.anchorMin-Vector2.zero).sqrMagnitude>1e-10f || (rect.anchorMax-Vector2.zero).sqrMagnitude>1e-10f ||
               (rect.pivot-new Vector2(.5f,.5f)).sqrMagnitude>1e-10f || (rect.sizeDelta-new Vector2(180,180)).sqrMagnitude>1e-10f ||
               (rect.anchoredPosition-new Vector2(120+(i%3)*230,1130-(i/3)*230)).sqrMagnitude>1e-10f)
                throw new InvalidOperationException("Saved gallery sprite/rect differs: "+spec.id);
            result[i]=new GalleryResult{id=spec.id,spriteGuid=spec.guid,geometryVerified=true};
        }
        return result;
    }
    // TMP adds nonpersistent fallback-font renderers as first siblings during
    // mesh generation. Exclude only verified native render children from the
    // source hierarchy; arbitrary additional nodes still fail the boundary.
    static bool IsGeneratedTextSubmesh(Transform child) {
        if(child==null || child.parent==null || child.childCount!=0)return false;
        var sub=child.GetComponent<TMPro.TMP_SubMeshUI>();
        var owner=child.parent.GetComponent<TMPro.TextMeshProUGUI>();
        var layout=child.GetComponent<UnityEngine.UI.LayoutElement>();
        if(sub==null || owner==null || sub.textComponent!=owner || sub.fontAsset==null ||
           layout==null || !layout.ignoreLayout ||
           (child.gameObject.hideFlags&HideFlags.DontSave)!=HideFlags.DontSave)return false;
        return child.GetComponents<Component>().All(c=>c is RectTransform || c is CanvasRenderer ||
            c is TMPro.TMP_SubMeshUI || c is UnityEngine.UI.LayoutElement);
    }
    static bool IsGeneratedSpineSubmesh(Transform child) {
        bool generated=false;IdentifyOptionalGeneratedSpineChild(child,ref generated);return generated;
    }
    static bool IsWithinGeneratedSortProxy(Transform child) { for(var current=child;current!=null;current=current.parent)if(Monkey.StaticSortQueueProxy.UnityStaticSortQueueProxy.IsGeneratedSortProxyRoot(current))return true;return false; }
    public static bool IsGeneratedNativePresentationChild(Transform child) => IsGeneratedTextSubmesh(child)||IsGeneratedSpineSubmesh(child)||Monkey.StaticSortQueueProxy.UnityStaticSortQueueProxy.IsGeneratedSortProxyRoot(child);
    static string SourcePrefabTransformPath(Transform node,Transform root) {
        if(node==null||root==null)return "<null>";
        var names=new Stack<string>();var current=node;
        while(current!=null) { names.Push(current.name);if(current==root)break;current=current.parent; }
        if(current!=root)return "<outside-source-root>/"+string.Join("/",names.ToArray());
        return string.Join("/",names.ToArray());
    }
    static string DescribeSourcePrefabReopenMismatch(SourcePrefabSpec spec,Dictionary<string,NodeSpec> nodeSpecs,
        Transform sourceRoot,Transform[] transforms) {
        var expectedPathCounts=new Dictionary<string,int>(StringComparer.Ordinal);var planIssues=new List<string>();
        foreach(var id in spec.nodes??Array.Empty<string>()) {
            if(!nodeSpecs.TryGetValue(id,out var row)||row==null) {planIssues.Add("missing-plan-node:"+id);continue;}
            var segments=new Stack<string>();var current=row;var visited=new HashSet<string>(StringComparer.Ordinal);var reachedRoot=false;
            while(current!=null) {
                if(!visited.Add(current.sourceId)) {planIssues.Add("plan-parent-cycle:"+id);break;}
                segments.Push(current.name??"<null-name>");
                if(current.sourceId==spec.root) {reachedRoot=true;break;}
                if(string.IsNullOrEmpty(current.parent)||!nodeSpecs.TryGetValue(current.parent,out current))break;
            }
            if(!reachedRoot) {planIssues.Add("plan-path-does-not-reach-root:"+id);continue;}
            var path=string.Join("/",segments.ToArray());
            expectedPathCounts[path]=expectedPathCounts.TryGetValue(path,out var count)?count+1:1;
        }
        var unknown=new List<string>();
        foreach(var transform in transforms??Array.Empty<Transform>()) {
            if(transform==null||IsWithinGeneratedSortProxy(transform)||IsGeneratedTextSubmesh(transform)||IsGeneratedSpineSubmesh(transform))continue;
            var path=SourcePrefabTransformPath(transform,sourceRoot);
            if(expectedPathCounts.TryGetValue(path,out var remaining)&&remaining>0) {expectedPathCounts[path]=remaining-1;continue;}
            var kinds=transform.GetComponents<Component>().Select(component=>component==null?"<missing-script>":component.GetType().FullName).ToArray();
            unknown.Add(path+" ["+string.Join(",",kinds)+"]");
        }
        var missingPlanPaths=expectedPathCounts.Where(pair=>pair.Value>0).Select(pair=>pair.Key+" x"+pair.Value).ToArray();
        var missingScriptRows=(transforms??Array.Empty<Transform>()).Where(transform=>transform!=null)
            .Select(transform=>new {transform,count=GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(transform.gameObject)})
            .Where(row=>row.count>0).Select(row=>SourcePrefabTransformPath(row.transform,sourceRoot)+" [missingScripts="+row.count+"]").ToArray();
        string Bounded(IEnumerable<string> values,int limit) {
            var rows=values.Take(limit).ToArray();var suffix=values.Skip(limit).Any()?";more=true":"";
            return string.Join(" | ",rows)+suffix;
        }
        return "unknown="+Bounded(unknown,12)+";missingPlanPaths="+Bounded(missingPlanPaths,12)+
            ";missingScriptNodes="+Bounded(missingScriptRows,12)+";planIssues="+Bounded(planIssues,8);
    }
    static Transform[] SourceChildren(Transform parent) {
        return Enumerable.Range(0,parent.childCount).Select(parent.GetChild).Where(c=>!IsGeneratedNativePresentationChild(c)).ToArray();
    }
    static Dictionary<string,RectTransform> SavedNodeMap(NodeSpec[] nodes,GameObject instance,SourcePrefabSpec prefab=null,Dictionary<string,NodeSpec> byId=null) {
        byId=byId??nodes.ToDictionary(n=>n.sourceId);
        var mapped=new Dictionary<string,RectTransform>();
        var pending=new Stack<KeyValuePair<NodeSpec,Transform>>();
        if(prefab!=null)pending.Push(new KeyValuePair<NodeSpec,Transform>(byId[prefab.root],instance.transform));
        else {
            var roots=nodes.Where(n=>string.IsNullOrEmpty(n.parent) || !byId.ContainsKey(n.parent)).ToArray();
            var design=instance.transform.Find("DesignRoot");
            if(design==null || design.childCount!=roots.Length)throw new InvalidOperationException("Saved source root boundary differs");
            for(int i=roots.Length-1;i>=0;i--)pending.Push(new KeyValuePair<NodeSpec,Transform>(roots[i],design.GetChild(i)));
        }
        while(pending.Count>0) {
            var pair=pending.Pop();var source=pair.Key;var target=pair.Value as RectTransform;
            var children=target==null?new Transform[0]:SourceChildren(target);
            if(target==null || children.Length!=source.children.Length)throw new InvalidOperationException("Saved source node boundary differs: "+source.sourceId);
            mapped.Add(source.sourceId,target);
            for(int i=source.children.Length-1;i>=0;i--)pending.Push(new KeyValuePair<NodeSpec,Transform>(byId[source.children[i]],children[i]));
        }
        if(mapped.Count!=(prefab==null?nodes.Length:prefab.nodeCount))throw new InvalidOperationException("Saved source node count differs");
        return mapped;
    }
    static LabelResult ReadSavedLabel(ComponentSpec spec,RectTransform saved,bool bitmap) {
        var label=saved.GetComponent<TMPro.TextMeshProUGUI>();
        if(label==null)return new LabelResult {sourceId=spec.sourceId,allCharactersPresent=false};
        GameObject probeCanvas=null;var measured=label;string geometryProbe="saved-node";
        try {
            var sourceGlyphFilter=label.GetComponent<NativeBitmapMissingGlyphs>();
            if(sourceGlyphFilter!=null&&!sourceGlyphFilter.InstallDerivedRenderer())throw new InvalidOperationException("BITMAP_GLYPH_FILTER_READ_FAILED");
            label.ForceMeshUpdate(true,true);
            if(!label.gameObject.activeInHierarchy || !label.enabled || (!string.IsNullOrEmpty(label.text) && label.textInfo.characterCount==0)) {
                // An active clone measures hidden text without activating or changing the saved scene tree.
                probeCanvas=new GameObject("MonkeyTextGeometryProbe",typeof(RectTransform),typeof(Canvas));
                SceneManager.MoveGameObjectToScene(probeCanvas,label.gameObject.scene);
                probeCanvas.GetComponent<Canvas>().renderMode=RenderMode.WorldSpace;
                var clone=UnityEngine.Object.Instantiate(label.gameObject,probeCanvas.transform,false);
                measured=clone.GetComponent<TMPro.TextMeshProUGUI>();
                foreach(var behaviour in clone.GetComponentsInChildren<Behaviour>(true))if(behaviour!=measured)behaviour.enabled=false;
                var rect=(RectTransform)clone.transform;rect.anchorMin=rect.anchorMax=new Vector2(.5f,.5f);
                rect.pivot=saved.pivot;rect.sizeDelta=saved.rect.size;rect.anchoredPosition3D=Vector3.zero;
                clone.SetActive(true);measured.enabled=true;geometryProbe="isolated-active-clone";
                var clonedGlyphFilter=measured.GetComponent<NativeBitmapMissingGlyphs>();
                if(clonedGlyphFilter!=null&&!clonedGlyphFilter.InstallDerivedRenderer())throw new InvalidOperationException("BITMAP_GLYPH_FILTER_CLONE_READ_FAILED");
                measured.ForceMeshUpdate(true,true);
            }
            float padding=bitmap?TMPro.ShaderUtilities.GetPadding(measured.fontSharedMaterial,measured.extraPadding,(measured.fontStyle&TMPro.FontStyles.Bold)!=0):0;
            var lineBox=label.GetComponent<NativeTextLineBox>();
            return new LabelResult {bitmapMissingGlyphPolicy=sourceGlyphFilter?.Policy,bitmapDisplayText=sourceGlyphFilter?.GetDisplayText(),bitmapMissingGlyphProofVerified=sourceGlyphFilter!=null&&sourceGlyphFilter.IsContractIntact(label)&&sourceGlyphFilter.SourceComponentId==spec.sourceId&&sourceGlyphFilter.SourceFontId==spec.font,lineBoxPresent=lineBox!=null,lineBoxActive=lineBox!=null&&lineBox.isActiveAndEnabled,
                lineBoxHeight=lineBox!=null?lineBox.preferredHeight:0,lineBoxLineHeight=lineBox!=null?lineBox.LineHeight:0,lineBoxExtra=lineBox!=null?lineBox.ExtraLineFraction:0,
                lineCount=measured.textInfo.lineCount,sourceId=spec.sourceId,text=measured.text,fontGuid=AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(measured.font)),
                autoSizeReadback=true,autoSizing=label.enableAutoSizing,fontSizeMin=label.fontSizeMin,fontSizeMax=label.fontSizeMax,
                fontSize=measured.fontSize,characterCount=measured.textInfo.characterCount,geometryProbe=geometryProbe,
                glyphBounds=measured.textInfo.characterInfo.Take(measured.textInfo.characterCount).Where(info=>info.isVisible).Select(info=>new GlyphBounds {
                    unicode=info.character,left=info.bottomLeft.x,top=info.topLeft.y,width=info.topRight.x-info.topLeft.x,height=info.topLeft.y-info.bottomLeft.y,
                    quadPadding=padding*info.scale
                }).ToArray(),allCharactersPresent=measured.text.Where(ch=>!char.IsWhiteSpace(ch)).All(ch=>measured.font.HasCharacter(ch))};
        } finally {if(probeCanvas!=null)UnityEngine.Object.DestroyImmediate(probeCanvas);}
    }
    static string Hash(string path) {
        using (var algorithm = System.Security.Cryptography.SHA256.Create())
        using (var input = File.OpenRead(path))
            return BitConverter.ToString(algorithm.ComputeHash(input)).Replace("-","").ToLowerInvariant();
    }

    static MotionResult[] BuildMotions(Plan plan,Dictionary<string,GameObject> nodes) {
        var results=new List<MotionResult>();
        foreach(var spec in plan.animations ?? Array.Empty<MotionSpec>()) {
            if(!spec.convertible)continue;
            if(!spec.path.StartsWith(Paths.animationsRoot+"/",StringComparison.Ordinal) || spec.path.Contains("..") || File.Exists(spec.path))
                throw new InvalidOperationException("Unsafe/existing animation output: "+spec.path);
            Directory.CreateDirectory(Paths.animationsRoot);
            var clip=new AnimationClip {name=spec.name,frameRate=spec.sample};
            foreach(var track in spec.tracks) {
                if(!spec.assetOnly&&AnimationUtility.CalculateTransformPath(nodes[track.node].transform,nodes[spec.root].transform)!=track.path)
                    throw new InvalidOperationException("Animation hierarchy mismatch");
                var type=track.nativeType=="CanvasGroup"?typeof(CanvasGroup):track.nativeType=="RectTransform"?typeof(RectTransform):typeof(Transform);
                if(!spec.assetOnly&&type==typeof(CanvasGroup) && nodes[track.node].GetComponent<CanvasGroup>()==null)nodes[track.node].AddComponent<CanvasGroup>();
                var curve=new AnimationCurve(track.keys.Select(k=>new Keyframe(k.time,k.value)).ToArray());
                curve.preWrapMode=curve.postWrapMode=WrapMode.ClampForever;
                for(var i=0;i<track.keys.Length;i++) {
                    AnimationUtility.SetKeyBroken(curve,i,true);
                    AnimationUtility.SetKeyLeftTangentMode(curve,i,AnimationUtility.TangentMode.Linear);
                    AnimationUtility.SetKeyRightTangentMode(curve,i,track.keys[i].interpolation=="step"?AnimationUtility.TangentMode.Constant:AnimationUtility.TangentMode.Linear);
                }
                for(var i=1;i<track.keys.Length;i++)AnimationUtility.SetKeyLeftTangentMode(curve,i,track.keys[i-1].interpolation=="step"?AnimationUtility.TangentMode.Constant:AnimationUtility.TangentMode.Linear);
                AnimationUtility.SetEditorCurve(clip,EditorCurveBinding.FloatCurve(track.path,type,track.nativeProperty),curve);
            }
            var settings=AnimationUtility.GetAnimationClipSettings(clip);settings.loopTime=spec.wrap=="loop";
            AnimationUtility.SetAnimationClipSettings(clip,settings);AnimationUtility.SetAnimationEvents(clip,Array.Empty<AnimationEvent>());
            AssetDatabase.CreateAsset(clip,spec.path);EditorUtility.SetDirty(clip);AssetDatabase.SaveAssetIfDirty(clip);
            AssetDatabase.ImportAsset(spec.path,ImportAssetOptions.ForceUpdate);
            var saved=AssetDatabase.LoadAssetAtPath<AnimationClip>(spec.path);
            results.Add(new MotionResult {id=spec.id,path=spec.path,guid=AssetDatabase.AssetPathToGUID(spec.path),duration=saved.length,
                wrap=AnimationUtility.GetAnimationClipSettings(saved).loopTime?"loop":"normal",eventCount=AnimationUtility.GetAnimationEvents(saved).Length,curveCount=AnimationUtility.GetCurveBindings(saved).Length,
                tracks=spec.tracks.Select(track=>{
                    var type=track.nativeType=="CanvasGroup"?typeof(CanvasGroup):track.nativeType=="RectTransform"?typeof(RectTransform):typeof(Transform);
                    var curve=AnimationUtility.GetEditorCurve(saved,EditorCurveBinding.FloatCurve(track.path,type,track.nativeProperty));
                    return new MotionTrackResult {path=track.path,property=track.nativeProperty,nativeType=track.nativeType,
                        times=curve.keys.Select(k=>k.time).ToArray(),values=curve.keys.Select(k=>k.value).ToArray(),
                        interpolations=Enumerable.Range(0,curve.length).Select(i=>AnimationUtility.GetKeyRightTangentMode(curve,i)==AnimationUtility.TangentMode.Constant?"step":AnimationUtility.GetKeyRightTangentMode(curve,i)==AnimationUtility.TangentMode.Linear?"linear":"unsupported").ToArray(),
                        probeTimes=track.probes.Select(p=>p.time).ToArray(),probeValues=track.probes.Select(p=>curve.Evaluate(p.time)).ToArray()};
                }).ToArray()});
        }
        return results.ToArray();
    }

}
