using System;
using System.IO;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
namespace Grea.LifecycleSample {
 public sealed class CounterController:MonoBehaviour {
  public Button add,start,pause,resume,menu,quit; public Text status; CounterState state; string directory;
  public static string DataDirectory {
   get {string[] args=Environment.GetCommandLineArgs();int index=Array.IndexOf(args,"-grea-data-path");if(index<0 || index+1>=args.Length || !Path.IsPathRooted(args[index+1]))throw new InvalidDataException("Explicit isolated -grea-data-path required");return args[index+1];}
  }
  void Awake(){
   quit.onClick.AddListener(()=>{Trace("quit");Application.Quit();});
   try {
    directory=DataDirectory;
    var asset=Resources.Load<TextAsset>("Config/counter");if(asset==null)throw new InvalidDataException("Missing formal JSON config");
    state=new CounterState(JsonUtility.FromJson<CounterConfig>(asset.text),directory);
    add.onClick.AddListener(()=>{if(state.Increment())Trace("increment");Render();});
    start.onClick.AddListener(()=>{state.Start();Trace("start");Render();});
    pause.onClick.AddListener(()=>{state.Pause();Trace("pause");Render();});
    resume.onClick.AddListener(()=>{state.Resume();Trace("resume");Render();});
    menu.onClick.AddListener(()=>{state.Menu();Trace("menu");Render();});
    Trace("loaded");Render();
   }catch(Exception e){status.text="ERROR: "+e.Message;add.interactable=false;start.interactable=false;Debug.LogException(e);}
  }
  void Render(){
   bool feature=state.Config.goal>0;string phase=state.Save.phase;
   status.text=(feature?"LC2 PLAYABLE INCREMENT":"LC1 NATIVE CONTINUATION")+"\nTOTAL "+state.Save.count+(feature?"\n"+phase.ToUpperInvariant()+"  "+state.Save.roundCount+" / "+state.Config.goal+"\nRUNS COMPLETED "+state.Save.runsCompleted:"");
   add.interactable=!feature || phase=="playing";
   start.gameObject.SetActive(feature && (phase=="menu" || phase=="victory"));start.GetComponentInChildren<Text>().text=phase=="victory"?"PLAY AGAIN":"START";
   pause.gameObject.SetActive(feature && phase=="playing");resume.gameObject.SetActive(feature && phase=="paused");menu.gameObject.SetActive(feature && (phase=="paused" || phase=="victory"));
   if(EventSystem.current!=null)EventSystem.current.SetSelectedGameObject((!feature || phase=="playing"?add:phase=="paused"?resume:start).gameObject);
  }
  public void Trace(string action){
   if(directory==null)return;
   File.AppendAllText(Path.Combine(directory,"events.jsonl"),JsonUtility.ToJson(new SampleEvent {action=action,frame=Time.frameCount,width=Screen.width,height=Screen.height,count=state?.Save.count??-1,phase=state?.Save.phase,version=state?.Config.configVersion})+"\n");
  }
 }
 [Serializable] public class SampleEvent {public string action,phase,version;public int frame,width,height,count;}
}
