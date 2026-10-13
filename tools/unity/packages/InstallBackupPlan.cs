using System;
using System.IO;
using UnityEditor;
using UnityEditor.PackageManager;
using UnityEditor.PackageManager.Requests;
using UnityEngine;
public static class InstallBackupPlan {
 [Serializable] public class Plan {public string[] packages;public string[] ids;}
 static AddAndRemoveRequest request;static double deadline;
 public static void Install(){
  var args=Environment.GetCommandLineArgs();int i=Array.IndexOf(args,"-toolingPlan");
  if(i<0||i+1>=args.Length)throw new ArgumentException("-toolingPlan absolute JSON file required");
  var plan=JsonUtility.FromJson<Plan>(File.ReadAllText(args[i+1]));
  if(plan.packages==null||plan.packages.Length==0)throw new Exception("Empty plan");
  foreach(var path in plan.packages)if(!path.StartsWith("file:")||!File.Exists(path.Substring(5)))throw new Exception("Missing local package");
  request=Client.AddAndRemove(plan.packages);deadline=EditorApplication.timeSinceStartup+300;EditorApplication.update+=Poll;
 }
 static void Poll(){
  if(!request.IsCompleted){if(EditorApplication.timeSinceStartup>deadline){Debug.LogError("BACKUP_INSTALL_TIMEOUT");EditorApplication.Exit(2);}return;}
  EditorApplication.update-=Poll;
  if(request.Status==StatusCode.Success){Debug.Log("BACKUP_INSTALL_OK");EditorApplication.Exit(0);}
  else {Debug.LogError(request.Error.message);EditorApplication.Exit(1);}
 }
}
