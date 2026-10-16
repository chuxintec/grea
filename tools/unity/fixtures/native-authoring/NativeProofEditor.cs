using System;
using System.IO;
using System.Linq;
using Own.Configuration;
using Own.Configuration.Editor;
using Own.Proof;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.Build;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using Object=UnityEngine.Object;

public static class NativeProofEditor
{
    static string Arg(string flag) {var a=Environment.GetCommandLineArgs();return a[Array.IndexOf(a,flag)+1];}
    static void Check(bool value,string message) {if(!value)throw new InvalidOperationException(message);}
    const string Root="Assets/NativeOwned";
    public static void Create()
    {
        string fixture=Arg("-greaFixture");Directory.CreateDirectory("Assets/NativeProofData");AssetDatabase.Refresh();
        EnemyImport.Import(fixture+"/Enemy/authoring.json","Assets/NativeProofData/Enemy.asset");
        HintImport.Import(fixture+"/Hint/authoring.json","Assets/NativeProofData/Hint.asset");
        Grea.Tools.NativeAssetImport.Run();
    }
    public static void ReadAndEdit()
    {
        var sprite=AssetDatabase.LoadAssetAtPath<Sprite>(Root+"/Trim.png");
        Check(sprite && sprite.rect==new Rect(0,0,5,4) && sprite.pivot==new Vector2(1.25f,3) && sprite.border==Vector4.one,"Sprite geometry");
        var texture=AssetDatabase.LoadAssetAtPath<Texture2D>(Root+"/Trim.png");
        Check(texture.GetPixel(1,2)==Color.green && texture.GetPixel(0,0).a==0,"Rotation, trim and pixel alpha");
        var clip=AssetDatabase.LoadAssetAtPath<AnimationClip>(Root+"/Move.anim");var bindings=AnimationUtility.GetCurveBindings(clip);
        Check(bindings.Length==2 && AnimationUtility.GetAnimationClipSettings(clip).loopTime && clip.length==1,"Clip shape and loop");
        Check(AnimationUtility.GetAnimationEvents(clip).Single().functionName=="Pulse" && AnimationUtility.GetAnimationEvents(clip).Single().time==0.5f,"Event");
        var binding=bindings.Single(x=>x.path=="Widget");var curve=AnimationUtility.GetEditorCurve(clip,binding);
        Check(curve.Evaluate(0)==0 && curve.Evaluate(1)==4 && Mathf.Abs(curve.Evaluate(0.5f)-2)<0.001f,"Linear interpolation and duration endpoints");
        var root=PrefabUtility.LoadPrefabContents(Root+"/Native.prefab");
        try
        {
            Check(root.transform.Find("Widget").localScale==new Vector3(2,3,1),"Non-unit initial scale");
            var receiver=root.AddComponent<NativeProofReceiver>();receiver.enemies=AssetDatabase.LoadAssetAtPath<EnemyTable>("Assets/NativeProofData/Enemy.asset");receiver.hints=AssetDatabase.LoadAssetAtPath<HintTable>("Assets/NativeProofData/Hint.asset");
            Check(receiver.ConfigurationValid(),"Typed SO null/empty/bool/int readback");
            PrefabUtility.SaveAsPrefabAsset(root,Root+"/Native.prefab");
        }
        finally {PrefabUtility.UnloadPrefabContents(root);}
        // Deliberate user edit through Editor API. No converter invocation is needed to Play.
        var edited=AnimationCurve.Linear(0,0,1,8);AnimationUtility.SetEditorCurve(clip,binding,edited);EditorUtility.SetDirty(clip);AssetDatabase.SaveAssets();
        var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(Root+"/Native.prefab"));
        var camera=new GameObject("Camera").AddComponent<Camera>();camera.orthographic=true;camera.orthographicSize=5;camera.transform.position=new Vector3(0,0,-10);camera.tag="MainCamera";
        EditorSceneManager.SaveScene(scene,"Assets/NativeProof.unity");
        EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene("Assets/NativeProof.unity",true)};
        Check(AssetDatabase.CopyAsset(Root+"/Native.prefab","Assets/Resources/NativeProof.prefab"),"Play fixture copy");AssetDatabase.SaveAssets();
        Debug.Log("GREA_NATIVE_PROOF_EDITOR_READBACK_AND_MANUAL_EDIT_OK");
    }
    public static void Reopen()
    {
        var clip=AssetDatabase.LoadAssetAtPath<AnimationClip>(Root+"/Move.anim");var binding=AnimationUtility.GetCurveBindings(clip).Single(x=>x.path=="Widget");
        Check(AnimationUtility.GetEditorCurve(clip,binding).Evaluate(1)==8,"Manual edit survived Editor reopen");
        var root=PrefabUtility.LoadPrefabContents(Root+"/Native.prefab");try{Check(root.GetComponent<NativeProofReceiver>().ConfigurationValid(),"Typed SO references survived reopen");}finally{PrefabUtility.UnloadPrefabContents(root);}
        Debug.Log("GREA_NATIVE_PROOF_REOPEN_OK");
    }
    public static void ReopenImportAudit()
    {
        Reopen();
        if(!AssetDatabase.LoadMainAssetAtPath("Assets/Resources/NativeProof.prefab")) {Check(AssetDatabase.CopyAsset(Root+"/Native.prefab","Assets/Resources/NativeProof.prefab"),"Play fixture copy");AssetDatabase.SaveAssets();}
        Grea.Tools.NativeAssetImport.Run();
        Grea.Tools.NativeExitEditorAudit.Run();
    }
    public static void MoveGeometryAudit()
    {
        Check(AssetDatabase.MoveAsset(Root+"/Trim.png",Root+"/RenamedTrim.png")=="","GUID preserving move");
        var importer=(TextureImporter)AssetImporter.GetAtPath(Root+"/RenamedTrim.png");importer.spriteBorder=new Vector4(0,1,1,1);importer.SaveAndReimport();
        Grea.Tools.NativeExitEditorAudit.Run();
    }
    public static void RejectOverwrite()
    {
        var clip=AssetDatabase.LoadAssetAtPath<AnimationClip>(Root+"/Move.anim");var binding=AnimationUtility.GetCurveBindings(clip).Single(x=>x.path=="Widget");
        try {Grea.Tools.NativeAssetImport.Run();throw new InvalidOperationException("Expected ownership conflict");}
        catch(IOException) {Check(AnimationUtility.GetEditorCurve(clip,binding).Evaluate(1)==8,"Manual curve overwritten");Debug.Log("GREA_NATIVE_PROOF_OVERWRITE_REJECTED");}
    }
    public static void FinalImport()
    {
        Grea.Tools.NativeAssetImport.Run();string path=Arg("-greaNativeRoot")+"/Trim.png";
        var sprite=AssetDatabase.LoadAssetAtPath<Sprite>(path);var importer=(TextureImporter)AssetImporter.GetAtPath(path);
        Check(sprite.rect==new Rect(0,0,5,4)&&sprite.pivot==new Vector2(1.25f,3)&&sprite.border==Vector4.one&&sprite.pixelsPerUnit==100,"Final import Sprite contract");
        Check(importer.npotScale==TextureImporterNPOTScale.None&&importer.maxTextureSize==4096,"No implicit rescale");
        Debug.Log("GREA_NATIVE_PROOF_FINAL_IMPORT_OK");
    }
    public static void Build()
    {
        PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone,UnityEditor.ScriptingImplementation.Mono2x);
        var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions {scenes=new[]{"Assets/NativeProof.unity"},locationPathName=Arg("-greaProofPlayer"),target=BuildTarget.StandaloneOSX,options=BuildOptions.None});
        Check(report.summary.result==UnityEditor.Build.Reporting.BuildResult.Succeeded,"Player build");
    }
}
