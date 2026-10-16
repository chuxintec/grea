using System.Collections;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using Own.Proof;
using System;
using System.IO;
using Object=UnityEngine.Object;

public sealed class NativeProofRenderTests
{
    [UnityTest] public IEnumerator VisibleNativePatternIsRendered()
    {
        yield return SceneManager.LoadSceneAsync("NativeProof");
        // This fixture deliberately uses the built-in unlit Sprite path, independent of URP post effects.
        GraphicsSettings.defaultRenderPipeline=null;QualitySettings.renderPipeline=null;yield return null;
        Assert.That(SystemInfo.graphicsDeviceType,Is.Not.EqualTo(GraphicsDeviceType.Null),"Real graphics device required");
        var camera=Camera.main;Assert.IsNotNull(camera);
        var rt=new RenderTexture(480,300,24,RenderTextureFormat.ARGB32);var previous=camera.targetTexture;var active=RenderTexture.active;
        var image=new Texture2D(480,300,TextureFormat.RGB24,false);
        try
        {
            camera.targetTexture=rt;camera.Render();RenderTexture.active=rt;image.ReadPixels(new Rect(0,0,480,300),0,0);image.Apply();
            int green=0;foreach(var p in image.GetPixels32())if(p.g>180&&p.r<40&&p.b<40)green++;
            Assert.That(green,Is.GreaterThan(8),"Native green source texel must actually appear in the camera frame");
        }
        finally{camera.targetTexture=previous;RenderTexture.active=active;Object.Destroy(image);rt.Release();Object.Destroy(rt);}
    }
    [UnityTest] public IEnumerator RenderedPixelsFollowEditedCurvesScaleLoopAndInterruption()
    {
        yield return SceneManager.LoadSceneAsync("NativeProof");yield return null;
        var visual=Object.FindFirstObjectByType<NativeProofVisual>();Assert.IsNotNull(visual);
        for(int phase=0;phase<NativeProofVisual.Phases.Length;phase++)
        {
            visual.Pose(phase);yield return null;var image=visual.Render();
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"-greaRenderFrames");
            if(at>=0&&at+1<args.Length){Directory.CreateDirectory(args[at+1]);File.WriteAllBytes(Path.Combine(args[at+1],phase+"-"+NativeProofVisual.Phases[phase]+".png"),image.EncodeToPNG());}
            var graphic=visual.actor.transform.Find("Widget/Graphic").GetComponent<SpriteRenderer>();
            Debug.Log("NATIVE_VISUAL_GEOMETRY root="+visual.actor.transform.position+" widget="+graphic.transform.parent.position+" scale="+graphic.transform.lossyScale+" bounds="+graphic.bounds+" pivot="+graphic.sprite.pivot+" cameraAspect="+visual.proofCamera.aspect+" frame="+image.width+"x"+image.height);
            try{Assert.That(visual.Check(image,phase),Is.EqualTo(25),NativeProofVisual.Phases[phase]);}
            finally{Object.Destroy(image);}
        }
    }
}
