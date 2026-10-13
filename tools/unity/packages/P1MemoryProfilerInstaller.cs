using System;
using System.IO;
using UnityEditor;
using UnityEditor.PackageManager;
using UnityEditor.PackageManager.Requests;
using UnityEngine;
// Explicitly invoked installer only. No automatic startup or runtime code.
public static class P1MemoryProfilerInstaller {
 static AddRequest request;static double deadline;
 public static void Install(){request=Client.Add("com.unity.memoryprofiler@1.1.12");deadline=EditorApplication.timeSinceStartup+300;EditorApplication.update+=Poll;}
 public static void Verify(){
  var info=UnityEditor.PackageManager.PackageInfo.FindForAssetPath("Packages/com.unity.memoryprofiler");
  if(info==null||info.version!="1.1.12")throw new Exception("Memory Profiler version mismatch");
  bool found=false;foreach(var a in UnityEditor.Compilation.CompilationPipeline.GetAssemblies())if(a.name.Contains("MemoryProfiler")&&File.Exists(a.outputPath))found=true;
  if(!found)throw new Exception("Memory Profiler compiled assembly missing");
  Debug.Log("P1_VERIFY_OK Memory Profiler "+info.version);
 }
 static void Poll(){
  if(!request.IsCompleted){if(EditorApplication.timeSinceStartup>deadline){Debug.LogError("P1_UPM_TIMEOUT");EditorApplication.Exit(2);}return;}
  EditorApplication.update-=Poll;
  if(request.Status!=StatusCode.Success){Debug.LogError("P1_UPM_FAILED "+request.Error.message);EditorApplication.Exit(1);return;}
  Debug.Log("P1_UPM_OK "+request.Result.name+"@"+request.Result.version);EditorApplication.Exit(0);
 }
}
