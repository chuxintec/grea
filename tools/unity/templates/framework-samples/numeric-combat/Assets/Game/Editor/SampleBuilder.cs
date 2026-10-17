using System;
using System.IO;
using System.Linq;
using Grea.Editor;
using Grea.Foundation.Runtime;
using Grea.UI.UGUI;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UI;
using Numeric.Bootstrap;
using Numeric.Presentation;
using Object = UnityEngine.Object;
namespace Numeric.Editor
{
    // Project-owned seed authoring: run once in a NEW prepared project, never against a migrated game.
    public static class SampleBuilder
    {
        const string Entry = "Assets/Game/Scenes/Main.unity";
        static void Place(RectTransform rect, Vector2 anchor, Vector2 size)
        { rect.anchorMin = rect.anchorMax = anchor; rect.anchoredPosition = Vector2.zero; rect.sizeDelta = size; }
        static Button Button(string label, Transform parent, Vector2 anchor, Vector2? size = null)
        {
            var go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(ProjectGenerator.BasePath + "/ButtonShell.prefab"));
            go.name = label; go.transform.SetParent(parent, false); Place((RectTransform)go.transform, anchor, size ?? new Vector2(750,140));
            go.GetComponentInChildren<Text>(true).text = label; return go.GetComponent<Button>();
        }
        static Text Label(string value, Transform parent, Vector2 anchor, Vector2 size, int fontSize)
        {
            var go = new GameObject(value, typeof(RectTransform), typeof(Text)); go.transform.SetParent(parent,false);
            Place((RectTransform)go.transform,anchor,size); var text = go.GetComponent<Text>();
            text.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); text.text=value; text.color=Color.white;
            text.alignment=TextAnchor.MiddleCenter; text.fontSize=fontSize; text.raycastTarget=false; return text;
        }
        public static void Seed()
        {
            if (!File.Exists("grea-framework-sample.marker")) throw new InvalidOperationException("Sample marker required");
            var request = new ProjectGenerator.Request { generatorVersion = ProjectGenerator.Version, identity = "numeric-combat-v1",
                bootstrapScene = "Assets/Game/Scenes/Bootstrap.unity", entryScene = Entry, bootstrapType = typeof(SampleBootstrap).FullName,
                playerSaveNamespace="numeric-combat-player", qaSaveNamespace="numeric-combat-qa" };
            ProjectGenerator.Generate(request, "sample-generation-journal.json");
            var scene = EditorSceneManager.OpenScene(Entry, OpenSceneMode.Single);
            var host = Object.FindFirstObjectByType<UIHost>(); host.bindOpenButton = false;
            Object.DestroyImmediate(host.openButton.gameObject); host.openButton = null;
            // Preserve the authored portrait spacing at wide or short desktop viewports.
            // Expand guarantees both logical dimensions are at least the reference resolution.
            var scaler=host.canvas.GetComponent<UnityEngine.UI.CanvasScaler>();
            scaler.screenMatchMode=UnityEngine.UI.CanvasScaler.ScreenMatchMode.Expand;
            PrefabUtility.RecordPrefabInstancePropertyModifications(scaler);
            var view = host.gameObject.AddComponent<BattleView>(); view.host=host;
            Label("Grea Micro Battle", host.pageLayer, new Vector2(.5f,.95f), new Vector2(1000,120), 58);
            view.status=Label("Status",host.pageLayer,new Vector2(.5f,.85f),new Vector2(1020,250),38);

            view.start = Button("START / AGAIN", host.pageLayer, new Vector2(.5f,.68f));
            view.attack = Button("ATTACK", host.pageLayer, new Vector2(.5f,.56f));
            view.pause = Button("PAUSE", host.pageLayer, new Vector2(.5f,.44f));
            view.claim = Button("CLAIM REWARD", host.pageLayer, new Vector2(.5f,.23f));
            view.upgrade = Button("UPGRADE (5 COINS)", host.pageLayer, new Vector2(.5f,.32f));

            view.quit=Button("QUIT",host.pageLayer,new Vector2(.5f,.055f));
            view.failSave=Button("QA: FAIL NEXT SAVE",host.pageLayer,new Vector2(.5f,.115f),new Vector2(750,90));
            view.failSave.gameObject.SetActive(false);
            view.modalAction=Button("RETURN TO MENU",host.modal.ContentSlot,new Vector2(.5f,.5f),new Vector2(700,140));
            var closeText=host.modal.CloseButton.GetComponentInChildren<Text>(true); closeText.text="CLOSE / RESUME";
            PrefabUtility.RecordPrefabInstancePropertyModifications(closeText);
            var closeNav=new Navigation {mode=Navigation.Mode.Explicit,selectOnUp=view.modalAction};
            host.modal.CloseButton.navigation=closeNav;
            view.modalAction.navigation=new Navigation {mode=Navigation.Mode.Explicit,selectOnDown=host.modal.CloseButton};
            PrefabUtility.RecordPrefabInstancePropertyModifications(host.modal.CloseButton);
            PrefabUtility.RecordPrefabInstancePropertyModifications(view.modalAction);
            var bootstrap = new GameObject("Composition").AddComponent<SampleBootstrap>(); bootstrap.view=view;
            bootstrap.config=AssetDatabase.LoadAssetAtPath<BootstrapConfig>(ProjectGenerator.BasePath+"/BootstrapConfig.asset");
            var camera = Object.FindFirstObjectByType<Camera>(); camera.clearFlags=CameraClearFlags.SolidColor; camera.backgroundColor=new Color(.03f,.06f,.1f);
            if (BindingValidator.Inspect(host.gameObject).Count!=0) throw new InvalidOperationException("Sample binding failure");
            PrefabUtility.SaveAsPrefabAsset(host.gameObject,"Assets/SampleView.prefab");
            EditorSceneManager.SaveScene(scene);
            // A single-scene example has one composition owner. The generic two-scene seed is not built.
            EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene(Entry,true)};
            PlayerSettings.companyName="Grea Samples"; PlayerSettings.productName="Grea Micro Battle"; PlayerSettings.bundleVersion="0.1.0";
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Standalone,"org.grea.samples.microbattle");
            PlayerSettings.defaultScreenWidth=540; PlayerSettings.defaultScreenHeight=900;
            PlayerSettings.fullScreenMode=FullScreenMode.Windowed; PlayerSettings.resizableWindow=true; PlayerSettings.runInBackground=false;
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone,ScriptingImplementation.Mono2x);
            PlayerSettings.SetArchitecture(NamedBuildTarget.Standalone,1);
            PlayerSettings.SetManagedStrippingLevel(NamedBuildTarget.Standalone,ManagedStrippingLevel.Medium);
            AssetDatabase.SaveAssets();
            File.WriteAllText("sample-seeded.json", "{\"sample\":\"numeric-combat\",\"generator\":\""+ProjectGenerator.Version+"\"}");
        }
        [Serializable] public sealed class Receipt { public string sample,version,buildId,editor,result,backend,architecture; }
        public static void Build()
        {
            if (!File.Exists("sample-seeded.json")) throw new InvalidOperationException("Run Seed first");
            string[] args=Environment.GetCommandLineArgs(); int index=Array.IndexOf(args,"-buildOutput");
            if (index<0 || index+1>=args.Length) throw new InvalidOperationException("Explicit -buildOutput required");
            if (File.Exists(args[index+1]) || Directory.Exists(args[index+1])) throw new IOException("Build output already exists");
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone,ScriptingImplementation.Mono2x);
            PlayerSettings.SetArchitecture(NamedBuildTarget.Standalone,1);
            PlayerSettings.SetManagedStrippingLevel(NamedBuildTarget.Standalone,ManagedStrippingLevel.Medium);
            var target=EditorUserBuildSettings.activeBuildTarget;
            if(target!=BuildTarget.StandaloneOSX && target!=BuildTarget.StandaloneWindows64)
                throw new InvalidOperationException("Only explicit Mac or Windows x64 sample targets are supported");
            var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions { scenes=new[]{Entry}, locationPathName=args[index+1],
                target=target, options=BuildOptions.None });
            if(report.summary.result==BuildResult.Succeeded)
            {
                var managed=target==BuildTarget.StandaloneWindows64
                    ? Path.Combine(Path.GetDirectoryName(args[index+1]),Path.GetFileNameWithoutExtension(args[index+1])+"_Data","Managed")
                    : Path.Combine(args[index+1],"Contents/Resources/Data/Managed");
                var tests=Directory.GetFiles(managed,"*.dll").Select(Path.GetFileName).Where(x=>x.Contains(".Tests") || x.Contains(".PlayTests") || x.Contains("TestRunner") || x.StartsWith("nunit") || x.StartsWith("UnityEditor")).ToArray();
                if(tests.Length>0) throw new InvalidOperationException("TEST_ASSEMBLIES_IN_PLAYER: "+string.Join(",",tests));
                File.WriteAllText(Path.Combine(Path.GetDirectoryName(args[index+1]),"player-build.json"),JsonUtility.ToJson(new Receipt {
                    sample="numeric-combat", version="0.1.0", buildId=report.summary.guid.ToString(), editor=Application.unityVersion, result=report.summary.result.ToString(), backend="Mono", architecture=target==BuildTarget.StandaloneWindows64?"x64":"arm64" },true));
            }
            if(report.summary.result!=BuildResult.Succeeded) throw new InvalidOperationException("Player build failed");
        }
    }
}
