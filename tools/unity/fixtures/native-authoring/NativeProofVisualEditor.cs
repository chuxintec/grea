using System;
using System.IO;
using Own.Proof;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using Object=UnityEngine.Object;

public static class NativeProofVisualEditor
{
    static SpriteRenderer Graphic(Transform parent,string name,Sprite sprite,Vector3 scale)
    {
        var go=new GameObject(name);go.transform.SetParent(parent,false);go.transform.localScale=scale;
        var renderer=go.AddComponent<SpriteRenderer>();renderer.sprite=sprite;return renderer;
    }
    public static void Configure()
    {
        Grea.Tools.NativeAssetImport.Run();
        ConfigureScene();
    }
    public static void ConfigureScene()
    {
        // Set the fixture pipeline BEFORE AddComponent chooses renderer default materials.
        GraphicsSettings.defaultRenderPipeline=null;
        int active=QualitySettings.GetQualityLevel();for(int i=0;i<QualitySettings.names.Length;i++){QualitySettings.SetQualityLevel(i);QualitySettings.renderPipeline=null;}QualitySettings.SetQualityLevel(active);
        const string path="Assets/NativeOwned/Native.prefab";
        var trim=AssetDatabase.LoadAssetAtPath<Sprite>("Assets/NativeOwned/RenamedTrim.png");if(!trim)trim=AssetDatabase.LoadAssetAtPath<Sprite>("Assets/NativeOwned/Trim.png");
        var nine=AssetDatabase.LoadAssetAtPath<Sprite>("Assets/VisualNine/Nine.png");if(!trim||!nine)throw new InvalidOperationException("Own converted sprites required");
        foreach(var sprite in new[]{trim,nine}){var importer=(TextureImporter)AssetImporter.GetAtPath(AssetDatabase.GetAssetPath(sprite));importer.filterMode=FilterMode.Point;importer.SaveAndReimport();}
        var root=PrefabUtility.LoadPrefabContents(path);
        try
        {
            if(root.transform.Find("Widget/Graphic"))throw new IOException("New visual fixture copy required");
            root.transform.position=new Vector3(-4,2.2f,0);root.GetComponent<SpriteRenderer>().enabled=false;
            var widget=root.transform.Find("Widget");Graphic(widget,"Graphic",trim,new Vector3(20,20,1));
            var pivot=Graphic(widget,"Pivot",nine,new Vector3(0.06f/(0.9f*2),0.06f/(0.9f*3),1));pivot.color=Color.black;pivot.sortingOrder=10;
            var other=root.transform.Find("Other");other.localPosition=new Vector3(4,-3.8f,0);Graphic(other,"Graphic",nine,Vector3.one);
            root.GetComponent<Animator>().cullingMode=AnimatorCullingMode.AlwaysAnimate;
            PrefabUtility.SaveAsPrefabAsset(root,path);
        }
        finally{PrefabUtility.UnloadPrefabContents(root);}
        var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        var actor=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(path));
        var camera=new GameObject("Camera").AddComponent<Camera>();camera.transform.position=new Vector3(0,0,-10);camera.tag="MainCamera";camera.orthographic=true;camera.orthographicSize=5;camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(0.07f,0.09f,0.13f);camera.allowHDR=false;camera.allowMSAA=false;
        var visual=new GameObject("NativeVisualQA").AddComponent<NativeProofVisual>();visual.actor=actor;visual.proofCamera=camera;
        visual.shortSlice=Graphic(null,"ShortNineSlice",nine,Vector3.one);visual.shortSlice.drawMode=SpriteDrawMode.Sliced;visual.shortSlice.size=new Vector2(2.4f,1.2f);visual.shortSlice.transform.position=new Vector3(-4.8f,-3.7f,0);
        visual.longSlice=Graphic(null,"LongNineSlice",nine,Vector3.one);visual.longSlice.drawMode=SpriteDrawMode.Sliced;visual.longSlice.size=new Vector2(3.6f,1.8f);visual.longSlice.transform.position=new Vector3(4.8f,-3.7f,0);
        EditorSceneManager.SaveScene(scene,"Assets/NativeProof.unity");EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene("Assets/NativeProof.unity",true)};
        AssetDatabase.DeleteAsset("Assets/Resources/NativeProof.prefab");if(!AssetDatabase.CopyAsset(path,"Assets/Resources/NativeProof.prefab"))throw new IOException("Own Play prefab refresh failed");AssetDatabase.SaveAssets();
        Debug.Log("GREA_NATIVE_VISUAL_SCENE_CONFIGURED");
    }
    public static void RepairFixtureMaterials()
    {
        var scene=EditorSceneManager.OpenScene("Assets/NativeProof.unity");var visual=Object.FindFirstObjectByType<NativeProofVisual>();
        if(!visual||!visual.shortSlice.sharedMaterial)throw new InvalidOperationException("Own visual fixture required");
        var material=visual.shortSlice.sharedMaterial;
        if(material.shader.name!="Sprites/Default")throw new InvalidOperationException("Expected known built-in unlit material");
        var root=PrefabUtility.LoadPrefabContents("Assets/NativeOwned/Native.prefab");
        try{foreach(var renderer in root.GetComponentsInChildren<SpriteRenderer>(true))renderer.sharedMaterial=material;PrefabUtility.SaveAsPrefabAsset(root,"Assets/NativeOwned/Native.prefab");}
        finally{PrefabUtility.UnloadPrefabContents(root);}
        foreach(var renderer in Object.FindObjectsByType<SpriteRenderer>(FindObjectsSortMode.None))renderer.sharedMaterial=material;
        EditorSceneManager.MarkSceneDirty(scene);EditorSceneManager.SaveScene(scene);
        AssetDatabase.DeleteAsset("Assets/Resources/NativeProof.prefab");if(!AssetDatabase.CopyAsset("Assets/NativeOwned/Native.prefab","Assets/Resources/NativeProof.prefab"))throw new IOException("Own fixture copy failed");AssetDatabase.SaveAssets();
        Debug.Log("GREA_NATIVE_VISUAL_MATERIALS_FIXED");
    }
}
