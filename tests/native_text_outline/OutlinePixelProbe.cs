using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

public static class OutlinePixelProbe {
    [Serializable] public class Case { public string name,path,text; }
    [Serializable] public class Cases { public Case[] rows; }
    [Serializable] public class Slot {
        public int index; public string font,fontGuid,atlasGuid,shader; public long atlasId;
        public bool outline,ratiosOff,atlasMatches; public float width,dilate,ratio,weightNormal,weightBold,gradient; public Color color;
    }
    [Serializable] public class GraphicState {
        public string objectName,type,shader,atlas; public bool raycast,cull,outline; public float width,dilate,ratio,bold;
    }
    [Serializable] public class Draw {
        public string name,sourcePrefabGuid,text,style,font; public float size;
        public string[] glyphFonts; public int[] glyphSlots; public float[] left,right;
        public bool driver,enabled; public int textLayers; public Slot[] slots; public GraphicState[] graphics;
    }
    const int Width=320, Height=96;
    public static void Render() {
        var dir=Environment.GetEnvironmentVariable("MONKEY_OUTLINE_CAPTURE");
        var cases=JsonUtility.FromJson<Cases>(File.ReadAllText(Environment.GetEnvironmentVariable("MONKEY_OUTLINE_CASES")));
        Directory.CreateDirectory(dir);
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        var cam=new GameObject("Camera",typeof(Camera)).GetComponent<Camera>();
        cam.orthographic=true;cam.orthographicSize=Height/2f;cam.aspect=(float)Width/Height;
        cam.transform.position=new Vector3(0,0,-10);cam.clearFlags=CameraClearFlags.SolidColor;cam.backgroundColor=new Color32(255,226,165,255);cam.allowHDR=false;cam.allowMSAA=false;
        var can=new GameObject("Canvas",typeof(RectTransform),typeof(Canvas)).GetComponent<Canvas>();
        can.renderMode=RenderMode.WorldSpace;can.worldCamera=cam;((RectTransform)can.transform).sizeDelta=new Vector2(Width,Height);
        var rt=RenderTexture.GetTemporary(Width,Height,24,RenderTextureFormat.ARGB32,RenderTextureReadWrite.sRGB);
        cam.targetTexture=rt;
        Action<string> capture=name=>{
            cam.Render();var prev=RenderTexture.active;RenderTexture.active=rt;
            var tex=new Texture2D(Width,Height,TextureFormat.RGBA32,false);
            tex.ReadPixels(new Rect(0,0,Width,Height),0,0);tex.Apply();
            File.WriteAllBytes(Path.Combine(dir,name+".png"),tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);RenderTexture.active=prev;
        };
        capture("bg");
        foreach(var c in cases.rows) {
            var prefab=AssetDatabase.LoadAssetAtPath<GameObject>(c.path);
            if(prefab==null)throw new Exception("Missing converted prefab "+c.path);
            var go=(GameObject)PrefabUtility.InstantiatePrefab(prefab,can.transform);
            var label=go.GetComponent<TextMeshProUGUI>();
            var rect=(RectTransform)go.transform;
            // Center the independent original roots in the same measuring viewport.
            rect.position=Vector3.zero;
            for(int i=0;i<3;i++){Canvas.ForceUpdateCanvases();label.ForceMeshUpdate(true,true);Canvas.ForceUpdateCanvases();cam.Render();}
            capture(c.name);
            var chars=label.textInfo.characterInfo.Take(label.textInfo.characterCount).ToArray();
            if(label.text!=c.text || chars.Length!=c.text.Length || chars.Any(x=>!x.isVisible) || label.fontSize!=24 || (label.fontStyle&FontStyles.Bold)==0) throw new Exception("Glyph or source style mismatch: "+c.name);
            var slots=new List<Slot>();
            foreach(var index in chars.Select(ch=>ch.materialReferenceIndex).Distinct()){
                var ch=chars.First(x=>x.materialReferenceIndex==index);
                var mesh=label.textInfo.meshInfo[index].mesh;
                var graphic=index==0?(Graphic)label:label.GetComponentsInChildren<TMP_SubMeshUI>(true).Single(x=>x.mesh==mesh);
                var m=graphic.canvasRenderer.GetMaterial(0);
                var atlas=m.mainTexture;
                AssetDatabase.TryGetGUIDAndLocalFileIdentifier(atlas,out string guid,out long local);
                slots.Add(new Slot{index=index,font=ch.fontAsset.faceInfo.familyName,fontGuid=AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(ch.fontAsset)),
                    atlasGuid=guid,atlasId=local,atlasMatches=ch.fontAsset.atlasTextures.Contains(atlas),shader=m.shader.name,outline=m.IsKeywordEnabled("OUTLINE_ON"),
                    ratiosOff=m.IsKeywordEnabled("RATIOS_OFF"),width=m.GetFloat("_OutlineWidth"),dilate=m.GetFloat("_FaceDilate"),ratio=m.GetFloat("_ScaleRatioA"),
                    weightNormal=m.GetFloat("_WeightNormal"),weightBold=m.GetFloat("_WeightBold"),gradient=m.GetFloat("_GradientScale"),color=m.GetColor("_OutlineColor")});
            }
            var driver=label.GetComponent<NativeStaticTextOutline>();
            var row=new Draw{name=c.name,sourcePrefabGuid=AssetDatabase.AssetPathToGUID(c.path),text=label.text,size=label.fontSize,
                style=label.fontStyle.ToString(),font=label.font.faceInfo.familyName,textLayers=go.GetComponentsInChildren<TMP_Text>(true).Length+(driver!=null&&driver.StrokeTarget!=null?1:0),driver=driver!=null,enabled=driver!=null&&driver.enabled,
                glyphFonts=chars.Select(ch=>ch.fontAsset.faceInfo.familyName).ToArray(),glyphSlots=chars.Select(ch=>ch.materialReferenceIndex).ToArray(),
                left=chars.Select(ch=>ch.origin).ToArray(),right=chars.Select(ch=>ch.xAdvance).ToArray(),slots=slots.ToArray()};
            row.graphics=can.GetComponentsInChildren<Graphic>(true).Select(g=>{
                var cr=g.canvasRenderer;
                var mat=cr.materialCount>0?cr.GetMaterial(0):null;
                return new GraphicState{objectName=g.name,type=g.GetType().Name,raycast=g.raycastTarget,cull=cr.cull,
                    shader=mat==null?null:mat.shader.name,atlas=mat==null||mat.mainTexture==null?null:mat.mainTexture.name,
                    outline=mat!=null&&mat.IsKeywordEnabled("OUTLINE_ON"),width=mat!=null&&mat.HasProperty("_OutlineWidth")?mat.GetFloat("_OutlineWidth"):0,
                    dilate=mat!=null&&mat.HasProperty("_FaceDilate")?mat.GetFloat("_FaceDilate"):0,
                    ratio=mat!=null&&mat.HasProperty("_ScaleRatioA")?mat.GetFloat("_ScaleRatioA"):0,
                    bold=mat!=null&&mat.HasProperty("_WeightBold")?mat.GetFloat("_WeightBold"):0};
            }).ToArray();
            File.WriteAllText(Path.Combine(dir,c.name+".json"),JsonUtility.ToJson(row,true));
            cam.backgroundColor=Color.white;capture(c.name+"-white");
            cam.backgroundColor=new Color32(255,226,165,255);
            UnityEngine.Object.DestroyImmediate(go);Canvas.ForceUpdateCanvases();
        }
        cam.targetTexture=null;RenderTexture.ReleaseTemporary(rt);
    }
}
