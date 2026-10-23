using System;
using System.IO;
using UnityEngine;
namespace Grea.LifecycleSample {
 [Serializable] public class CounterConfig {
  public int schema_version; public string configVersion; public int step,goal;
  public void Validate(){if(schema_version!=1 || step!=1 || goal<0 || goal>20 || string.IsNullOrEmpty(configVersion))throw new InvalidDataException("Unsupported counter config");}
 }
 [Serializable] public class SaveHeader {public int schema_version;}
 [Serializable] public class CounterSave {public int schema_version=1;public int count;public string pending="";public int roundCount,runsCompleted;public string phase="menu";}
 public sealed class CounterState {
  public readonly CounterConfig Config; public readonly CounterSave Save; readonly string path;
  public CounterState(CounterConfig config,string directory) {
   config.Validate();Config=config;Directory.CreateDirectory(directory);path=Path.Combine(directory,"save.json");
   if(File.Exists(path)){var header=JsonUtility.FromJson<SaveHeader>(File.ReadAllText(path));if(header==null || header.schema_version<1 || header.schema_version>2)throw new InvalidDataException("Unknown save version; preserved");}
   Save=File.Exists(path)?JsonUtility.FromJson<CounterSave>(File.ReadAllText(path)):new CounterSave();
   if(Save==null || Save.schema_version<1 || Save.schema_version>2 || (config.goal==0 && Save.schema_version!=1) || Save.count<0 || Save.roundCount<0 || Save.runsCompleted<0)throw new InvalidDataException("Unknown or invalid save; preserved");
   if(config.goal>0 && Save.schema_version==1) {
    if(File.Exists(path)) {string backup=path+".v1.backup";if(File.Exists(backup)){if(File.ReadAllText(backup)!=File.ReadAllText(path))throw new InvalidDataException("Existing migration backup differs");}else File.Copy(path,backup);}
    Save.schema_version=2;Save.roundCount=0;Save.phase="menu";Persist();
   }
   if(config.goal>0 && Save.phase!="menu" && Save.phase!="playing" && Save.phase!="paused" && Save.phase!="victory")throw new InvalidDataException("Unknown phase; preserved");
  }
  public bool Increment(){if(Config.goal>0 && Save.phase!="playing")return false;int nextCount=checked(Save.count+Config.step),nextRound=checked(Save.roundCount+Config.step);Save.count=nextCount;Save.roundCount=nextRound;if(Config.goal>0 && Save.roundCount>=Config.goal){Save.phase="victory";Save.runsCompleted++;}Persist();return true;}
  public void Start(){Save.roundCount=0;Save.phase="playing";Persist();}
  public void Pause(){if(Save.phase!="playing")return;Save.phase="paused";Persist();}
  public void Resume(){if(Save.phase!="paused")return;Save.phase="playing";Persist();}
  public void Menu(){Save.roundCount=0;Save.phase="menu";Persist();}
  void Persist(){string temp=path+".tmp";File.WriteAllText(temp,JsonUtility.ToJson(Save,true));if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);}
 }
}
