using System;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;

public static class NativeProofBuild
{
    public static void Run()
    {
        var args=Environment.GetCommandLineArgs();int index=Array.IndexOf(args,"-greaProofPlayer");
        if(index<0 || index+1>=args.Length)throw new ArgumentException("Explicit Player output required");
        PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone,ScriptingImplementation.Mono2x);
        PlayerSettings.productName="Grea Native Authoring Proof";
        PlayerSettings.SetArchitecture(NamedBuildTarget.Standalone,1);
        var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions {scenes=new[]{"Assets/NativeProof.unity"},locationPathName=args[index+1],target=BuildTarget.StandaloneOSX,options=BuildOptions.None});
        if(report.summary.result!=BuildResult.Succeeded)throw new InvalidOperationException("Build failed");
    }
}
