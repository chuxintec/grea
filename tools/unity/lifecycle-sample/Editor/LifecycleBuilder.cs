using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Build.Reporting;
using UnityEditor.Build;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using Grea.LifecycleSample;
public static class LifecycleBuilder {
 const string Scene="Assets/Game/Scenes/Counter.unity";
 public static void Build() {
  if(Application.unityVersion!="6000.6.2f1")throw new Exception("Pinned Editor required");
  CheckRules();
  var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
  var prefab=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Generated/Views/Candidate.prefab");if(prefab==null)throw new Exception("Actual imported candidate prefab required");
  var root=(GameObject)PrefabUtility.InstantiatePrefab(prefab,scene);
  var canvas=root.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceOverlay;canvas.worldCamera=null;
  var scaler=root.GetComponent<CanvasScaler>();scaler.referenceResolution=new Vector2(480,720);scaler.matchWidthOrHeight=.5f;
  var design=root.transform.Find("DesignRoot") as RectTransform;design.sizeDelta=new Vector2(480,720);design.anchoredPosition=new Vector2(-240,-360);
  var panel=design.GetChild(0) as RectTransform;panel.anchoredPosition=new Vector2(240,360);
  var add=root.GetComponentsInChildren<Button>(true).Single(x=>x.name=="AddCounter");
  var controller=root.AddComponent<CounterController>();controller.add=add;root.AddComponent<InputEvidence>().controller=controller;add.targetGraphic.raycastTarget=true;
  Label(add.transform,"ADD +1",0,0,280,70,28);
  controller.status=Label(root.transform,"",0,210,450,180,24);
  controller.start=Button(root.transform,"Start","START",0,50);
  controller.pause=Button(root.transform,"Pause","PAUSE",0,-210);
  controller.resume=Button(root.transform,"Resume","RESUME",0,50);
  controller.menu=Button(root.transform,"Menu","RETURN TO MENU",0,-210);
  controller.quit=Button(root.transform,"Quit","QUIT",0,-300);
  foreach(var b in new[]{add,controller.start,controller.pause,controller.resume,controller.menu,controller.quit})b.gameObject.AddComponent<PointerEvidence>().controller=controller;
  var events=UnityEngine.Object.FindFirstObjectByType<EventSystem>();if(events==null)events=new GameObject("EventSystem",typeof(EventSystem),typeof(StandaloneInputModule)).GetComponent<EventSystem>();
  var config=JsonUtility.FromJson<CounterConfig>(File.ReadAllText("Assets/Game/Resources/Config/counter.json"));events.firstSelectedGameObject=(config.goal>0?controller.start:add).gameObject;
  Directory.CreateDirectory("Assets/Game/Scenes");if(!EditorSceneManager.SaveScene(scene,Scene))throw new Exception("Scene save failed");
  EditorSceneManager.OpenScene(Scene);
  int missing=UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects().Sum(x=>x.GetComponentsInChildren<Transform>(true).Sum(t=>GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject)));
  if(missing!=0)throw new Exception("Missing script");
  var saved=UnityEngine.Object.FindFirstObjectByType<CounterController>();if(saved.add==null || saved.status==null || saved.quit==null || saved.add.image.sprite==null)throw new Exception("Native reference closure failed");
  PlayerSettings.companyName="Grea Samples";PlayerSettings.productName="Grea Lifecycle Counter";PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Standalone,"org.grea.samples.lifecyclecounter");
  PlayerSettings.defaultScreenWidth=480;PlayerSettings.defaultScreenHeight=720;PlayerSettings.fullScreenMode=FullScreenMode.Windowed;PlayerSettings.resizableWindow=true;PlayerSettings.macRetinaSupport=true;PlayerSettings.runInBackground=true;
  EditorUserBuildSettings.standaloneBuildSubtarget=StandaloneBuildSubtarget.Player;
  Directory.CreateDirectory("Build");
  var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{Scene},locationPathName="Build/Grea Lifecycle Counter.app",target=BuildTarget.StandaloneOSX,options=BuildOptions.Development});
  if(report.summary.result!=BuildResult.Succeeded)throw new Exception("Player build failed "+report.summary.result);
  Directory.CreateDirectory("Analysis");File.WriteAllText("Analysis/grea-native-acceptance.json",JsonUtility.ToJson(new Acceptance{unity=Application.unityVersion,missingScripts=missing,build="pass",rules="pass",nativeReferences="pass",bytes=(long)report.summary.totalSize},true));
 }
 [Serializable]class Acceptance {public string unity,build,rules,nativeReferences;public int missingScripts;public long bytes;}
 static Font Font=>Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
 static RectTransform Rect(GameObject go,Transform parent,float x,float y,float w,float h){var r=go.GetComponent<RectTransform>();r.SetParent(parent,false);r.anchorMin=r.anchorMax=new Vector2(.5f,.5f);r.pivot=new Vector2(.5f,.5f);r.anchoredPosition=new Vector2(x,y);r.sizeDelta=new Vector2(w,h);return r;}
 static Text Label(Transform parent,string value,float x,float y,float w,float h,int size){var go=new GameObject("Label",typeof(RectTransform),typeof(Text));Rect(go,parent,x,y,w,h);var t=go.GetComponent<Text>();t.font=Font;t.fontSize=size;t.text=value;t.alignment=TextAnchor.MiddleCenter;t.color=Color.white;t.raycastTarget=false;return t;}
 static Button Button(Transform parent,string name,string title,float x,float y){var go=new GameObject(name,typeof(RectTransform),typeof(Image),typeof(Button));Rect(go,parent,x,y,320,70);go.GetComponent<Image>().color=new Color(.12f,.4f,.65f);var b=go.GetComponent<Button>();b.targetGraphic=go.GetComponent<Image>();Label(go.transform,title,0,0,310,65,24);return b;}
 static void Expect(bool condition,string message){if(!condition)throw new Exception(message);}
 static void CheckRules(){
  string d=Path.Combine("Temp","GreaRules-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(d);
  try {
   var c=new CounterConfig{schema_version=1,configVersion="lc1",step=1,goal=0};var s=new CounterState(c,d);Expect(s.Increment() && s.Save.count==1,"LC1 increment");Expect(new CounterState(c,d).Save.count==1,"LC1 reopen");
   string path=Path.Combine(d,"save.json");var old=JsonUtility.FromJson<CounterSave>(File.ReadAllText(path));old.pending="pending-owned-1";File.WriteAllText(path,JsonUtility.ToJson(old));string before=File.ReadAllText(path);
   c.goal=3;c.configVersion="lc2";s=new CounterState(c,d);Expect(File.ReadAllText(path+".v1.backup")==before && s.Save.pending=="pending-owned-1" && s.Save.count==1,"Migration preservation");
   Expect(!s.Increment(),"Menu guarded");s.Start();s.Increment();s.Pause();Expect(!s.Increment(),"Paused guarded");s.Resume();s.Increment();s.Increment();Expect(s.Save.phase=="victory" && s.Save.runsCompleted==1 && s.Save.count==4,"LC2 victory");Expect(!s.Increment(),"Victory no duplicate award");
   s.Start();s.Increment();s.Menu();Expect(s.Save.runsCompleted==1 && s.Save.roundCount==0,"Cancel no completed run");
   c.configVersion="retuned";c.goal=4;Expect(new CounterState(c,d).Save.count==5,"Config hash/version is not save rejection");
   var future=s.Save;future.schema_version=99;File.WriteAllText(path,JsonUtility.ToJson(future));before=File.ReadAllText(path);bool rejected=false;try{new CounterState(c,d);}catch(InvalidDataException){rejected=true;}Expect(rejected && before==File.ReadAllText(path),"Future save preserved");
   c.step=0;rejected=false;try{c.Validate();}catch(InvalidDataException){rejected=true;}Expect(rejected,"Invalid config rejected");
  }finally{Directory.Delete(d,true);}
 }
}
