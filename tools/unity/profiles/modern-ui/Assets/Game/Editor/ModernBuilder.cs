using System;
using System.IO;
using System.Linq;
using UnityEngine.InputSystem;
using Grea.UI.Modern;
using Grea.UI.UGUI;
using ModernSample.Bootstrap;
using ModernSample.Domain;
using ModernSample.Presentation;
using TMPro;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.SceneManagement;
using UnityEngine.TextCore.LowLevel;
using UnityEngine.UI;
using Object=UnityEngine.Object;

namespace ModernSample.Editor
{
    public static class ModernBuilder
    {
        const string Scene="Assets/Game/Content/main.unity";
        static TMP_FontAsset font;
        static GameObject Rect(string name,Transform parent,Vector2 anchor,Vector2 size)
        {
            var go=new GameObject(name,typeof(RectTransform));go.transform.SetParent(parent,false);
            var rt=(RectTransform)go.transform;rt.anchorMin=rt.anchorMax=anchor;rt.sizeDelta=size;return go;
        }
        static TMP_Text Label(string text,Transform parent,Vector2 anchor,Vector2 size,int fontSize=40)
        {
            var go=Rect("label",parent,anchor,size);var label=go.AddComponent<TextMeshProUGUI>();label.font=font;label.fontSize=fontSize;
            label.text=text;label.alignment=TextAlignmentOptions.Center;label.raycastTarget=false;return label;
        }
        static Button Button(string text,Transform parent,Vector2 anchor)
        {
            var go=Rect("button",parent,anchor,new Vector2(420,90));var hit=go.AddComponent<Image>();hit.color=Color.clear;
            var visual=Rect("visual",go.transform,new Vector2(.5f,.5f),new Vector2(420,90));var image=visual.AddComponent<Image>();image.color=new Color(.13f,.42f,.65f);image.raycastTarget=false;
            var button=go.AddComponent<Button>();button.targetGraphic=image;
            Label(text,visual.transform,new Vector2(.5f,.5f),new Vector2(400,85),32);
            go.AddComponent<CommandButton>().Configure(button);go.AddComponent<ButtonPressFeedback>().Configure(button,visual.transform,.92f,.08f);return button;
        }
        static RectTransform Layer(string name,Transform parent)
        {
            var rt=(RectTransform)Rect(name,parent,Vector2.zero,Vector2.zero).transform;rt.anchorMax=Vector2.one;rt.offsetMin=rt.offsetMax=Vector2.zero;return rt;
        }
        public static void BindInput(InputSystemUIInputModule input,InputActionAsset actions)
        {
            var references=AssetDatabase.LoadAllAssetsAtPath(AssetDatabase.GetAssetPath(actions)).OfType<InputActionReference>().ToArray();
            InputActionReference Ref(string name)=>references.Single(r=>(r.hideFlags & HideFlags.HideInHierarchy)==0 && r.action.id==actions.FindAction("UI/"+name,true).id);
            input.UnassignActions();
            input.actionsAsset=actions;input.point=Ref("Point");input.leftClick=Ref("Click");
            input.rightClick=Ref("RightClick");input.middleClick=Ref("MiddleClick");input.scrollWheel=Ref("ScrollWheel");
            input.move=Ref("Navigate");input.submit=Ref("Submit");input.cancel=Ref("Cancel");
            if(!EditorUtility.IsPersistent(input.point) || !EditorUtility.IsPersistent(input.leftClick))
                throw new InvalidOperationException("Input references must be persistent subassets");
        }
        public static void Seed()
        {
            if(!File.Exists("modern-profile.marker") || File.Exists(Scene))throw new InvalidOperationException("New modern profile project required");
            if (!Resources.Load<TMP_Settings>("TMP Settings")) throw new InvalidOperationException("Import the pinned UGUI package TMP Essential Resources with unity assets import before Seed");
            Directory.CreateDirectory("Assets/Game/Content");AssetDatabase.Refresh();
            var source=AssetDatabase.LoadAssetAtPath<Font>(File.ReadAllText("font-source.marker").Trim());
            if(!source)throw new InvalidOperationException("Explicit licensed CJK font required");
            font=TMP_FontAsset.CreateFontAsset(source,64,8,GlyphRenderMode.SDFAA,2048,2048,AtlasPopulationMode.Dynamic);
            font.name="sample_cjk";
            AssetDatabase.CreateAsset(font,"Assets/Game/Content/sample_cjk.asset");
            AssetDatabase.AddObjectToAsset(font.material,font);
            foreach(var texture in font.atlasTextures)AssetDatabase.AddObjectToAsset(texture,font);
            string chars="数值战斗敌人生命已保存行动益智步数暂停关闭攻击交换菜单 /:：[]0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
            if(!font.TryAddCharacters(chars,out string missing))throw new InvalidOperationException("Missing glyphs: "+missing);
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var root=Rect("ui_root",null,Vector2.zero,Vector2.zero);var ui=root.AddComponent<ModernUIRoot>();ui.canvas=root.AddComponent<Canvas>();ui.canvas.renderMode=RenderMode.ScreenSpaceOverlay;
            var scaler=root.AddComponent<CanvasScaler>();scaler.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;scaler.referenceResolution=new Vector2(540,900);scaler.screenMatchMode=CanvasScaler.ScreenMatchMode.Expand;
            root.AddComponent<GraphicRaycaster>();ui.pages=Layer("pages",root.transform);ui.modals=Layer("modals",root.transform);ui.toasts=Layer("toasts",root.transform);
            var events=new GameObject("event_system",typeof(EventSystem),typeof(InputSystemUIInputModule));events.transform.SetParent(root.transform,false);
            ui.events=events.GetComponent<EventSystem>();ui.input=events.GetComponent<InputSystemUIInputModule>();
            var inputPackage=UnityEditor.PackageManager.PackageInfo.FindForAssembly(typeof(InputSystem).Assembly);
            const string inputPath="Assets/Game/Content/ui_input.inputactions";
            File.Copy(Path.Combine(inputPackage.resolvedPath,"InputSystem/Runtime/Plugins/PlayerInput/DefaultInputActions.inputactions"),inputPath,false);
            AssetDatabase.ImportAsset(inputPath,ImportAssetOptions.ForceSynchronousImport);
            var actions=AssetDatabase.LoadAssetAtPath<InputActionAsset>(inputPath);
            BindInput(ui.input,actions);
            var dialogRoot=Layer("dialog",ui.modals);var dialog=dialogRoot.gameObject.AddComponent<ModernDialog>();ui.dialog=dialog;
            dialog.content=Layer("content",dialogRoot).gameObject;dialog.content.AddComponent<Image>().color=new Color(0,0,0,.9f);
            dialog.title=Label("暂停 / Pause",dialog.content.transform,new Vector2(.5f,.65f),new Vector2(500,150));
            dialog.close=Button("关闭 / Close",dialog.content.transform,new Vector2(.5f,.4f));dialog.events=ui.events;dialog.content.SetActive(false);
            var view=root.AddComponent<SampleView>();view.root=ui;view.status=Label("",ui.pages,new Vector2(.5f,.72f),new Vector2(510,300));
            var kind=File.ReadAllText("modern-profile.marker").Trim()=="numeric-combat"?GameKind.Combat:GameKind.Puzzle;
            view.action=Button(kind==GameKind.Combat?"攻击 / Attack":"交换 / Swap",ui.pages,new Vector2(.5f,.38f));
            view.menu=Button("菜单 / Menu",ui.pages,new Vector2(.5f,.22f));ui.events.firstSelectedGameObject=view.action.gameObject;
            var config=ScriptableObject.CreateInstance<SampleConfig>();config.kind=kind;
            AssetDatabase.CreateAsset(config,"Assets/Game/Content/sample_config.asset");
            var bootstrap=new GameObject("composition").AddComponent<SampleBootstrap>();bootstrap.config=config;bootstrap.view=view;
            PrefabUtility.SaveAsPrefabAsset(root,"Assets/Game/Content/sample_ui.prefab");
            EditorSceneManager.SaveScene(scene,Scene);EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene(Scene,true)};
            PlayerSettings.companyName="Grea Samples";PlayerSettings.productName="Grea Modern "+kind;
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Standalone,"org.grea.samples.modern."+kind.ToString().ToLowerInvariant());
            PlayerSettings.bundleVersion="0.1.0";PlayerSettings.defaultScreenWidth=540;PlayerSettings.defaultScreenHeight=900;PlayerSettings.fullScreenMode=FullScreenMode.Windowed;
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone,ScriptingImplementation.Mono2x);PlayerSettings.SetArchitecture(NamedBuildTarget.Standalone,1);
            var settings=new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset")[0]);settings.FindProperty("activeInputHandler").intValue=1;settings.ApplyModifiedPropertiesWithoutUndo();
            AssetDatabase.SaveAssets();Debug.Log("MODERN_SEEDED "+kind);
        }
        public static void Build()
        {
            var args=Environment.GetCommandLineArgs();var index=Array.IndexOf(args,"-buildOutput");
            if(index<0 || index+1>=args.Length)throw new ArgumentException("Explicit new build output required");
            var output=args[index+1];if(File.Exists(output)||Directory.Exists(output))throw new IOException("Output exists");
            var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions {scenes=new[]{Scene},locationPathName=output,target=BuildTarget.StandaloneOSX,options=BuildOptions.None});
            if(report.summary.result!=BuildResult.Succeeded)throw new InvalidOperationException("Build failed");
            File.WriteAllText(output+".identity.json","{\"build_id\":\""+report.summary.guid+"\",\"profile\":\"modern-ui-v1\"}");
        }
    }
}
