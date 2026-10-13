using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Security.Cryptography;
using Grea.UI.UGUI;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using Object = UnityEngine.Object;

namespace Grea.Reference.Editor
{
    public static class ReferenceBuilder
    {
        public const string ScenePath = "Assets/Reference/Scenes/Reference.unity";
        public const string ViewPath = "Assets/Reference/Content/ReferenceView.prefab";
        public const string ConfigPath = "Assets/Reference/Content/ReferenceConfig.asset";
        static readonly Color Ink = new Color(.035f,.065f,.10f), Accent = new Color(.25f,.95f,.75f), White = new Color(.90f,.95f,.97f);
        [Serializable] public sealed class Identity { public string path, sha256; }
        [Serializable] public sealed class Manifest { public string version = "1.0.0"; public List<Identity> files = new List<Identity>(); }
        static string Hash(string path) { using (var sha=SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-", "").ToLowerInvariant(); }
        static GameObject Rect(string name, Transform parent, Vector2 pos, Vector2 size)
        {
            var go=new GameObject(name,typeof(RectTransform));if(parent)go.transform.SetParent(parent,false);
            var rt=(RectTransform)go.transform;rt.anchoredPosition=pos;rt.sizeDelta=size;return go;
        }
        static GameObject Panel(string name,Transform parent,Color color)
        {
            var go=Rect(name,parent,Vector2.zero,Vector2.zero);var rt=(RectTransform)go.transform;rt.anchorMin=Vector2.zero;rt.anchorMax=Vector2.one;rt.offsetMin=rt.offsetMax=Vector2.zero;
            go.AddComponent<Image>().color=color;return go;
        }
        static Text Label(string name,Transform parent,string value,int size,Vector2 pos,Vector2 dimensions,Color color)
        {
            var go=Rect(name,parent,pos,dimensions);var text=go.AddComponent<Text>();text.font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            text.text=value;text.fontSize=size;text.color=color;text.alignment=TextAnchor.MiddleCenter;text.raycastTarget=false;return text;
        }
        static CommandButton Button(string name,Transform parent,string text,Vector2 pos,Vector2 size,bool primary=true)
        {
            var prefab=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/GreaGenerated/ButtonShell.prefab");
            var go=(GameObject)PrefabUtility.InstantiatePrefab(prefab);go.name=name;go.transform.SetParent(parent,false);
            var rt=(RectTransform)go.transform;rt.anchoredPosition=pos;rt.sizeDelta=size;
            var image=go.GetComponent<Image>();image.color=primary?Accent:new Color(.13f,.20f,.27f);
            Label("Label",go.transform,text,18,Vector2.zero,size,primary?Ink:White);
            PrefabUtility.RecordPrefabInstancePropertyModifications(rt);PrefabUtility.RecordPrefabInstancePropertyModifications(image);
            return go.GetComponent<CommandButton>();
        }
        static ReferenceView MakeView()
        {
            var root=Rect("SignalGarden",null,Vector2.zero,Vector2.zero);var canvas=root.AddComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceOverlay;
            var scaler=root.AddComponent<CanvasScaler>();scaler.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;scaler.referenceResolution=new Vector2(960,600);scaler.matchWidthOrHeight=.5f;
            root.AddComponent<GraphicRaycaster>();var view=root.AddComponent<ReferenceView>();
            var events=new GameObject("EventSystem",typeof(EventSystem),typeof(StandaloneInputModule));events.transform.SetParent(root.transform,false);
            Panel("Backdrop",root.transform,Ink);
            Label("Brand",root.transform,"grea  /  REFERENCE 01",14,new Vector2(0,265),new Vector2(800,30),Accent);
            Label("Footer",root.transform,"Unity 6000.6.2f1  |  local-only save  |  MIT source",13,new Vector2(0,-272),new Vector2(900,30),new Color(.45f,.58f,.66f));
            view.menu=Rect("Menu",root.transform,Vector2.zero,new Vector2(960,460));
            Label("Title",view.menu.transform,"SIGNAL GARDEN",48,new Vector2(0,135),new Vector2(850,70),White);
            Label("Subtitle",view.menu.transform,"Find five signals. Pause any time. Come back for another run.",18,new Vector2(0,65),new Vector2(860,50),new Color(.6f,.74f,.79f));
            view.startButton=Button("Start",view.menu.transform,"START RUN",new Vector2(0,-15),new Vector2(250,58));
            view.winsText=Label("Wins",view.menu.transform,"RUNS COMPLETED  0",16,new Vector2(0,-95),new Vector2(600,35),Accent);
            view.quitButton=Button("Quit",view.menu.transform,"QUIT",new Vector2(0,-155),new Vector2(140,42),false);
            view.game=Rect("Game",root.transform,Vector2.zero,new Vector2(960,460));
            view.scoreText=Label("Score",view.game.transform,"SIGNALS  0 / 5",24,new Vector2(-220,190),new Vector2(380,42),White);
            view.pauseButton=Button("Pause",view.game.transform,"PAUSE  /  ESC",new Vector2(295,190),new Vector2(190,44),false);
            view.targetButton=Button("Signal",view.game.transform,"COLLECT",new Vector2(-250,5),new Vector2(120,100));
            Label("Hint",view.game.transform,"CLICK THE MINT SIGNAL",14,new Vector2(0,-195),new Vector2(600,35),new Color(.55f,.70f,.75f));
            view.progress=new Image[5];for(int i=0;i<5;i++) { var go=Rect("Progress"+i,view.game.transform,new Vector2((i-2)*34,140),new Vector2(20,5));view.progress[i]=go.AddComponent<Image>();view.progress[i].raycastTarget=false; }
            view.pause=Panel("PauseOverlay",root.transform,new Color(.025f,.045f,.07f,.98f));
            view.pauseText=Label("Paused",view.pause.transform,"PAUSED",28,new Vector2(0,110),new Vector2(850,60),White);
            view.resumeButton=Button("Resume",view.pause.transform,"RESUME",new Vector2(0,15),new Vector2(250,58));
            view.leaveButton=Button("Leave",view.pause.transform,"RETURN TO MENU",new Vector2(0,-65),new Vector2(250,50),false);
            view.result=Panel("Result",root.transform,Ink);
            Label("Complete",view.result.transform,"SIGNAL COMPLETE",42,new Vector2(0,140),new Vector2(850,65),Accent);
            view.resultText=Label("Summary",view.result.transform,"",18,new Vector2(0,60),new Vector2(850,50),White);
            view.againButton=Button("Again",view.result.transform,"PLAY AGAIN",new Vector2(0,-25),new Vector2(250,58));
            view.menuButton=Button("Menu",view.result.transform,"RETURN TO MENU",new Vector2(0,-105),new Vector2(250,50),false);
            view.error=Panel("Error",root.transform,Ink);view.errorText=Label("ErrorMessage",view.error.transform,"Cannot start.",24,Vector2.zero,new Vector2(860,180),new Color(1,.6f,.45f));
            view.game.SetActive(false);view.pause.SetActive(false);view.result.SetActive(false);view.error.SetActive(false);view.Validate();return view;
        }
        public static void Author()
        {
            if(Application.unityVersion!="6000.6.2f1")throw new InvalidOperationException("Wrong Editor");
            const string receipt="reference-authoring.json";
            if(File.Exists(receipt))
            {
                var prior=JsonUtility.FromJson<Manifest>(File.ReadAllText(receipt));
                if(prior.version!="1.0.0" || prior.files.Any(x=>!File.Exists(x.path)||Hash(x.path)!=x.sha256))throw new InvalidOperationException("REFERENCE_OWNERSHIP_CONFLICT");
                Validate();return;
            }
            foreach(var path in new[]{ViewPath,ConfigPath,ScenePath})if(File.Exists(path)||File.Exists(path+".meta"))throw new InvalidOperationException("Refusing existing output "+path);
            if(!AssetDatabase.IsValidFolder("Assets/Reference/Content"))AssetDatabase.CreateFolder("Assets/Reference","Content");
            if(!AssetDatabase.IsValidFolder("Assets/Reference/Scenes"))AssetDatabase.CreateFolder("Assets/Reference","Scenes");
            var view=MakeView();try { PrefabUtility.SaveAsPrefabAsset(view.gameObject,ViewPath); } finally { Object.DestroyImmediate(view.gameObject); }
            var config=ScriptableObject.CreateInstance<ReferenceConfig>();config.Validate();AssetDatabase.CreateAsset(config,ConfigPath);
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var app=new GameObject("ReferenceBootstrap").AddComponent<ReferenceApp>();app.config=config;app.viewPrefab=AssetDatabase.LoadAssetAtPath<GameObject>(ViewPath).GetComponent<ReferenceView>();
            var camera=new GameObject("Camera").AddComponent<Camera>();camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=Ink;camera.gameObject.AddComponent<AudioListener>();
            EditorSceneManager.SaveScene(scene,ScenePath);
            EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene(ScenePath,true)};
            ConfigurePlayer();AssetDatabase.SaveAssets();Validate();
            var manifest=new Manifest();foreach(var path in new[]{ViewPath,ConfigPath,ScenePath})foreach(var f in new[]{path,path+".meta"})manifest.files.Add(new Identity{path=f,sha256=Hash(f)});
            File.WriteAllText(receipt,JsonUtility.ToJson(manifest,true));
        }
        public static void Validate()
        {
            var view=AssetDatabase.LoadAssetAtPath<GameObject>(ViewPath);if(!view)throw new InvalidOperationException("Missing reference view");view.GetComponent<ReferenceView>().Validate();
            if(view.GetComponentsInChildren<EventSystem>(true).Length!=1)throw new InvalidOperationException("EventSystem count");
            foreach(var component in view.GetComponentsInChildren<MonoBehaviour>(true))if(!component)throw new InvalidOperationException("Missing script");
            AssetDatabase.LoadAssetAtPath<ReferenceConfig>(ConfigPath).Validate();
            var scene=EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
            var apps=scene.GetRootGameObjects().SelectMany(x=>x.GetComponentsInChildren<ReferenceApp>(true)).ToArray();
            if(apps.Length!=1||!apps[0].config||!apps[0].viewPrefab)throw new InvalidOperationException("Bootstrap binding");
        }
        static void ConfigurePlayer()
        {
            PlayerSettings.companyName="Grea";PlayerSettings.productName="Grea Signal Garden";PlayerSettings.bundleVersion="1.0.0";
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Standalone,"org.grea.signalgarden");
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone,ScriptingImplementation.Mono2x);
            PlayerSettings.SetArchitecture(NamedBuildTarget.Standalone,1);
            PlayerSettings.SetManagedStrippingLevel(NamedBuildTarget.Standalone,ManagedStrippingLevel.Medium);
            PlayerSettings.defaultScreenWidth=960;PlayerSettings.defaultScreenHeight=600;PlayerSettings.fullScreenMode=FullScreenMode.Windowed;PlayerSettings.resizableWindow=true;
            PlayerSettings.runInBackground=true;
        }
        public static void Build()
        {
            Validate();ConfigurePlayer();
            var args=Environment.GetCommandLineArgs();int i=Array.IndexOf(args,"-buildOutput");
            if(i<0||i+1>=args.Length)throw new ArgumentException("Explicit -buildOutput required");
            var output=Path.GetFullPath(args[i+1]);if(File.Exists(output)||Directory.Exists(output))throw new IOException("Build output already exists");
            var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{ScenePath},locationPathName=output,target=BuildTarget.StandaloneOSX,options=BuildOptions.None});
            var receipt=new { }; // Build receipt below uses a stable serializable type.
            if (report.summary.result == BuildResult.Succeeded)
            {
                var managed = Path.Combine(output,"Contents/Resources/Data/Managed");
                var tests = Directory.GetFiles(managed,"*.dll").Select(Path.GetFileName).Where(x => x.Contains(".Tests.") || x.EndsWith(".Tests.dll") || x.Contains("TestRunner") || x.StartsWith("nunit") || x.StartsWith("UnityEditor")).ToArray();
                if (tests.Length > 0) throw new InvalidOperationException("TEST_ASSEMBLIES_IN_PLAYER: " + string.Join(", ", tests));
            }
            File.WriteAllText(Path.Combine(Path.GetDirectoryName(output),"player-build.json"),JsonUtility.ToJson(new BuildReceipt{result=report.summary.result.ToString(),buildId=report.summary.guid.ToString(),bytes=report.summary.totalSize,editor=Application.unityVersion,architecture="arm64",backend="Mono"},true));
            if(report.summary.result!=BuildResult.Succeeded)throw new InvalidOperationException("PLAYER_BUILD_FAILED");
        }
        [Serializable] public sealed class BuildReceipt { public string result,buildId,editor,architecture,backend; public ulong bytes; }
    }
}
