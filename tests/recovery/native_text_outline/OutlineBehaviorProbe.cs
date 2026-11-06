using System;
using System.IO;
using System.Linq;
using TMPro;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UI;

public static class OutlineBehaviorProbe {
    [Serializable] public class Result {public bool pair,faceUntouched,opacity,raycast,rectMask,stencilMask,clone,disabled,transparent,empty,destroyed;}
    public static void Run() {
        var output=Environment.GetEnvironmentVariable("MONKEY_OUTLINE_BEHAVIOR");Directory.CreateDirectory(output);
        var path=Environment.GetEnvironmentVariable("MONKEY_OUTLINE_PREFAB");
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        var camera=new GameObject("Camera",typeof(Camera)).GetComponent<Camera>();camera.orthographic=true;camera.orthographicSize=48;camera.aspect=320f/96;camera.transform.position=new Vector3(0,0,-10);camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=Color.black;camera.allowMSAA=false;camera.allowHDR=false;
        var canvas=new GameObject("Canvas",typeof(RectTransform),typeof(Canvas)).GetComponent<Canvas>();canvas.renderMode=RenderMode.WorldSpace;canvas.worldCamera=camera;((RectTransform)canvas.transform).sizeDelta=new Vector2(320,96);
        var parent=new GameObject("Clip",typeof(RectTransform));parent.transform.SetParent(canvas.transform,false);((RectTransform)parent.transform).sizeDelta=new Vector2(60,36);
        var go=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(path),parent.transform);go.transform.localPosition=Vector3.zero;
        var face=go.GetComponent<TextMeshProUGUI>();var driver=go.GetComponent<NativeStaticTextOutline>();
        if(driver==null)throw new Exception("Persistent outline component missing");
        var material=face.fontSharedMaterial;var font=face.font;var margin=face.margin;var style=face.fontStyle;var rect=(RectTransform)face.transform;var size=rect.sizeDelta;
        Action refresh=()=>{face.ForceMeshUpdate(true,true);driver.RefreshNow();Canvas.ForceUpdateCanvases();};refresh();
        var stroke=driver.StrokeTarget;
        var result=new Result();result.pair=stroke!=null&&stroke.transform.parent==face.transform.parent&&stroke.transform.GetSiblingIndex()+1==face.transform.GetSiblingIndex()&&NativeStaticTextOutline.IsGeneratedStroke(stroke.transform)&&stroke.GetComponent<LayoutElement>().ignoreLayout;
        result.faceUntouched=face.fontSharedMaterial==material&&face.font==font&&face.margin==margin&&face.fontStyle==style&&rect.sizeDelta==size;
        result.raycast=!stroke.raycastTarget&&stroke.GetComponentsInChildren<TMP_SubMeshUI>(true).All(s=>!s.raycastTarget);
        var opacity=go.AddComponent<CanvasGroup>();opacity.alpha=.4f;refresh();result.opacity=Mathf.Abs(stroke.canvasRenderer.GetInheritedAlpha()-face.canvasRenderer.GetInheritedAlpha())<.0001f;opacity.alpha=1;refresh();
        var buffer=RenderTexture.GetTemporary(320,96,24,RenderTextureFormat.ARGB32,RenderTextureReadWrite.sRGB);camera.targetTexture=buffer;
        Func<string,bool> clipped=tag=>{refresh();camera.Render();var prev=RenderTexture.active;RenderTexture.active=buffer;var tex=new Texture2D(320,96,TextureFormat.RGBA32,false);tex.ReadPixels(new Rect(0,0,320,96),0,0);tex.Apply();File.WriteAllBytes(Path.Combine(output,tag+".png"),tex.EncodeToPNG());var pixels=tex.GetPixels32();bool any=false,valid=true;for(int y=0;y<96;y++)for(int x=0;x<320;x++){var p=pixels[y*320+x];if(p.r>5||p.g>5||p.b>5){any=true;if(x<129||x>190||y<29||y>66)valid=false;}}UnityEngine.Object.DestroyImmediate(tex);RenderTexture.active=prev;return any&&valid;};
        var mask=parent.AddComponent<RectMask2D>();result.rectMask=clipped("rect-mask");UnityEngine.Object.DestroyImmediate(mask);
        parent.AddComponent<Image>().raycastTarget=false;var stencil=parent.AddComponent<Mask>();stencil.showMaskGraphic=false;result.stencilMask=clipped("stencil-mask");UnityEngine.Object.DestroyImmediate(stencil);UnityEngine.Object.DestroyImmediate(parent.GetComponent<Image>());
        var clone=UnityEngine.Object.Instantiate(go,parent.transform);var cloneDriver=clone.GetComponent<NativeStaticTextOutline>();cloneDriver.RefreshNow();result.clone=cloneDriver.StrokeTarget!=null&&cloneDriver.StrokeTarget!=driver.StrokeTarget&&cloneDriver.Target==clone.GetComponent<TMP_Text>();UnityEngine.Object.DestroyImmediate(clone);
        driver.enabled=false;result.disabled=stroke==null||!stroke.enabled;driver.enabled=true;refresh();
        driver.ConfigurePaired(face,3,new Color(1,1,1,0),"behavior");result.transparent=driver.StrokeTarget==null;
        var text=face.text;face.text="";driver.ConfigurePaired(face,3,Color.white,"behavior");result.empty=driver.StrokeTarget==null;face.text=text;driver.ConfigurePaired(face,3,Color.white,"behavior");stroke=driver.StrokeTarget;UnityEngine.Object.DestroyImmediate(go);result.destroyed=stroke==null||!stroke.enabled;
        camera.targetTexture=null;RenderTexture.ReleaseTemporary(buffer);
        File.WriteAllText(Path.Combine(output,"result.json"),JsonUtility.ToJson(result,true));
        if(!(result.pair&&result.faceUntouched&&result.opacity&&result.raycast&&result.rectMask&&result.stencilMask&&result.clone&&result.disabled&&result.transparent&&result.empty&&result.destroyed))throw new Exception("Native outline behavior check failed: "+JsonUtility.ToJson(result));
    }
}
