using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using Monkey.StaticMaskSort;

public static partial class MonkeyImporter
{
    [Serializable] public sealed class MaskClipProbeReadback
    {
        public string sourceId, node, status, method, stimulus, imagePath, imageSha256, evidencePath;
        public string expectedInsidePixelClass, expectedOutsidePixelClass;
        public bool supported, sourceGeometryVerified, sourceNodeActiveSelf, sourceNodeActiveInHierarchy,
            sourceMaskEnabled, sourceStatePreserved, probeHostOwned, probeObjectsDestroyed,
            sourceGeometryPreserved, probeSceneCreated, probeSceneClosed,
            renderCompleted, pixelReadbackVerified, insidePixelVerified, outsidePixelVerified,
            maskInsidePointAccepted, maskOutsidePointRejected, childGraphicInsideAccepted,
            childGraphicOutsideRejected, disabledChildGraphicOutsideAccepted,
            stencilClipVerified, disabledNoClipVerified, probeMaskActiveInHierarchy, probeChildActiveInHierarchy,
            sourceAppFrame, sourceVisualParityClaimed, verified;
        public int imageWidth, imageHeight;
        public float[] insideLocalPoint, outsideLocalPoint, insideWorldPoint, outsideWorldPoint;
        public float[] insideViewportPoint, outsideViewportPoint;
        public int[] insidePixel, outsidePixel, insideRgba, outsideRgba;
        public string[] diagnostics;
    }

    const string MaskClipProbeMethod="unity-ui-mask-stencil-rendertexture-v1";
    const int MaskClipProbeSize=256;

    static bool MaskClipNearly(float a,float b,float epsilon=.001f)
    {
        return !Single.IsNaN(a)&&!Single.IsInfinity(a)&&Mathf.Abs(a-b)<=epsilon;
    }

    static bool MaskClipVector2(Vector2 actual,float[] expected)
    {
        return expected!=null&&expected.Length>=2&&MaskClipNearly(actual.x,expected[0])&&MaskClipNearly(actual.y,expected[1]);
    }

    static bool MaskClipVector3(Vector3 actual,float[] expected)
    {
        return expected!=null&&expected.Length>=3&&MaskClipNearly(actual.x,expected[0])&&
            MaskClipNearly(actual.y,expected[1])&&MaskClipNearly(actual.z,expected[2]);
    }

    static bool MaskClipRotation(Quaternion actual,float[] expected)
    {
        return expected!=null&&expected.Length>=4&&MaskClipNearly(actual.x,expected[0])&&
            MaskClipNearly(actual.y,expected[1])&&MaskClipNearly(actual.z,expected[2])&&MaskClipNearly(actual.w,expected[3]);
    }

    static bool MaskClipExpectedOpaqueWhite(Color32 pixel)
    {
        return pixel.a>=245&&pixel.r>=230&&pixel.g>=230&&pixel.b>=230;
    }

    static bool MaskClipExpectedClear(Color32 pixel)
    {
        return pixel.a<=12;
    }

    static Vector2 MaskClipExpectedOutsidePoint(Rect rect)
    {
        return new Vector2(rect.xMax+rect.width*.25f,rect.center.y);
    }

    static bool MaskClipSourceGeometry(Plan plan,MaskSpec spec,GameObject loadedSource,
        out RectTransform sourceRect,out bool sourceActiveSelf,out bool sourceActive,out string diagnostic)
    {
        sourceRect=loadedSource==null?null:loadedSource.transform as RectTransform;
        sourceActiveSelf=loadedSource!=null&&loadedSource.activeSelf;
        sourceActive=loadedSource!=null&&loadedSource.activeInHierarchy;
        diagnostic=null;
        if(plan==null||spec==null||sourceRect==null)
        {diagnostic="source-plan-or-RectTransform-absent";return false;}
        var rows=(plan.nodes??Array.Empty<NodeSpec>()).Where(row=>row!=null&&row.sourceId==spec.node).ToArray();
        if(rows.Length!=1)
        {diagnostic="source-node-spec-absent-or-ambiguous";return false;}
        var source=rows[0];
        var parents=(plan.nodes??Array.Empty<NodeSpec>()).Where(row=>row!=null&&row.sourceId==source.parent).ToArray();
        if(!String.IsNullOrEmpty(source.parent)&&parents.Length!=1)
        {diagnostic="source-parent-geometry-absent-or-ambiguous";return false;}
        if(parents.Length==1&&(parents[0].anchor==null||parents[0].anchor.Length<2))
        {diagnostic="source-parent-anchor-fields-absent";return false;}
        var expectedAnchor=parents.Length==1?new Vector2(parents[0].anchor[0],parents[0].anchor[1]):Vector2.zero;
        if(source.size==null||source.size.Length<2||source.anchor==null||source.anchor.Length<2||
            source.position==null||source.position.Length<3||source.scale==null||source.scale.Length<3||
            source.rotation==null||source.rotation.Length<4)
        {diagnostic="source-node-geometry-fields-absent";return false;}
        var expectedPivot=new Vector2(source.anchor[0],source.anchor[1]);
        var sizeMatches=MaskClipVector2(sourceRect.sizeDelta,source.size)&&
            MaskClipNearly(sourceRect.rect.width,source.size[0])&&MaskClipNearly(sourceRect.rect.height,source.size[1]);
        var anchorsMatch=(sourceRect.anchorMin-expectedAnchor).sqrMagnitude<1e-8f&&
            (sourceRect.anchorMax-expectedAnchor).sqrMagnitude<1e-8f;
        var geometryMatches=sizeMatches&&anchorsMatch&&
            (sourceRect.pivot-expectedPivot).sqrMagnitude<1e-8f&&
            MaskClipVector3(sourceRect.anchoredPosition3D,source.position)&&
            MaskClipVector3(sourceRect.localScale,source.scale)&&MaskClipRotation(sourceRect.localRotation,source.rotation);
        var sourceNodes=(plan.nodes??Array.Empty<NodeSpec>()).Where(row=>row!=null)
            .GroupBy(row=>row.sourceId,StringComparer.Ordinal).ToDictionary(group=>group.Key,group=>group.Count()==1?group.First():null,StringComparer.Ordinal);
        var active=source.active;var cursor=source.parent;var seen=new HashSet<string>(StringComparer.Ordinal);
        while(active&&!String.IsNullOrEmpty(cursor))
        {
            if(!seen.Add(cursor)||!sourceNodes.TryGetValue(cursor,out var ancestor)||ancestor==null)
            {diagnostic="source-ancestor-activity-ambiguous";return false;}
            active=ancestor.active;cursor=ancestor.parent;
        }
        if(sourceActiveSelf!=source.active||sourceActive!=active)
        {diagnostic="source-node-activity-does-not-match-frozen-plan";return false;}
        diagnostic=geometryMatches?null:"source-RectTransform-does-not-match-frozen-node-geometry";
        return geometryMatches;
    }

    static int[] MaskClipPixel(Color32 value)
    {
        return new[]{(int)value.r,(int)value.g,(int)value.b,(int)value.a};
    }

    static string MaskClipHash(byte[] bytes)
    {
        using(var sha=SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();
    }

    static string MaskClipEvidenceRoot()
    {
        var projectRoot=Directory.GetParent(Application.dataPath);
        if(projectRoot==null)throw new InvalidOperationException("MASK_CLIP_PROJECT_ROOT_MISSING");
        return Path.Combine(projectRoot.FullName,"Analysis","Readback","MaskClipping");
    }

    static MaskClipProbeReadback ProbeStaticMaskClipping(Plan plan,MaskSpec spec,GameObject loadedSource)
    {
        var result=new MaskClipProbeReadback
        {
            sourceId=spec==null?null:spec.sourceId,node=spec==null?null:spec.node,
            status="gap",method=MaskClipProbeMethod,stimulus="temporary-white-child-image-on-transparent-world-space-canvas",
            supported=spec!=null&&spec.maskType==0&&!spec.inverted,
            sourceMaskEnabled=spec!=null&&spec.enabled,
            sourceNodeActiveSelf=loadedSource!=null&&loadedSource.activeSelf,
            sourceNodeActiveInHierarchy=loadedSource!=null&&loadedSource.activeInHierarchy,
            sourceAppFrame=false,sourceVisualParityClaimed=false,verified=false,
            expectedInsidePixelClass="opaque-white",
            diagnostics=Array.Empty<string>()
        };
        var diagnostics=new List<string>();var pngBytes=null as byte[];
        GameObject host=null,cameraObject=null;Camera probeCamera=null;Canvas probeCanvas=null;
        RectTransform probeMaskRect=null;Mask probeMask=null;Image childGraphic=null;
        RenderTexture renderTexture=null;Texture2D readbackTexture=null;var priorActiveTexture=RenderTexture.active;
        Scene probeScene=default(Scene);
        var sourceActiveSelfBefore=loadedSource!=null&&loadedSource.activeSelf;
        var sourceActiveHierarchyBefore=loadedSource!=null&&loadedSource.activeInHierarchy;
        var sourceMask=loadedSource==null?null:loadedSource.GetComponent<Mask>();
        var sourceMaskEnabledBefore=sourceMask!=null&&sourceMask.enabled;
        RectTransform sourceRect=null;bool sourceActiveSelf=false,sourceActive=false;string geometryDiagnostic=null;
        try
        {
            do
            {
            if(spec==null||loadedSource==null)
            {diagnostics.Add("source-mask-or-loaded-node-absent");break;}
            if(!result.supported)
            {diagnostics.Add("clip-probe-supports-only-noninverted-rect-mask-type-0");break;}
            if(sourceMask==null||loadedSource.GetComponent<NativeStaticMaskIdentity>()==null)
            {diagnostics.Add("source-native-mask-or-identity-absent");break;}
            if(!MaskClipSourceGeometry(plan,spec,loadedSource,out sourceRect,out sourceActiveSelf,out sourceActive,out geometryDiagnostic))
            {result.sourceNodeActiveSelf=sourceActiveSelf;result.sourceNodeActiveInHierarchy=sourceActive;
                diagnostics.Add(geometryDiagnostic??"source-geometry-unverified");break;}
            var identity=loadedSource.GetComponent<NativeStaticMaskIdentity>();
            var sourceGraphic=loadedSource.GetComponent<Graphic>();
            var sourceTypedReadback=UnityStaticMaskSort.ReadStaticMask(spec,loadedSource,id=>null);
            if(identity.sourceId!=spec.sourceId||identity.nativeId!=spec.nativeId||sourceMask.enabled!=spec.enabled||
                sourceMask.showMaskGraphic||sourceGraphic==null||!(sourceGraphic is Image)||
                sourceGraphic.enabled!=spec.enabled||sourceGraphic.raycastTarget||!sourceTypedReadback.verified)
            {diagnostics.Add("source-mask-typed-identity-or-graphic-setup-differs");break;}
            var rect=sourceRect.rect;
            if(rect.width<=0||rect.height<=0||Single.IsNaN(rect.width)||Single.IsNaN(rect.height)||
                Single.IsInfinity(rect.width)||Single.IsInfinity(rect.height))
            {diagnostics.Add("source-rect-mask-geometry-degenerate");break;}
            var outsideLocal=MaskClipExpectedOutsidePoint(rect);var insideLocal=rect.center;
            result.insideLocalPoint=new[]{insideLocal.x,insideLocal.y};
            result.outsideLocalPoint=new[]{outsideLocal.x,outsideLocal.y};
            result.sourceGeometryVerified=true;result.sourceNodeActiveSelf=sourceActiveSelf;
            result.sourceNodeActiveInHierarchy=sourceActive;result.sourceMaskEnabled=spec.enabled;
            result.expectedOutsidePixelClass=spec.enabled?"clear":"opaque-white-disabled-no-clip";

            var worldScale=sourceRect.localScale;
            var spanX=Mathf.Abs(rect.width*worldScale.x)+Mathf.Abs(rect.height*worldScale.y);
            var spanY=Mathf.Abs(rect.width*worldScale.x)+Mathf.Abs(rect.height*worldScale.y);
            var canvasSide=Mathf.Max(4f*Mathf.Max(spanX,spanY),4f);
            const int probeLayer=31;
            probeScene=EditorSceneManager.NewPreviewScene();result.probeSceneCreated=probeScene.IsValid();
            if(!result.probeSceneCreated){diagnostics.Add("disposable-preview-scene-unavailable");break;}
            host=new GameObject("__MaskClipProbeHost",typeof(RectTransform),typeof(Canvas));
            host.hideFlags=HideFlags.HideAndDontSave;host.layer=probeLayer;
            SceneManager.MoveGameObjectToScene(host,probeScene);result.probeHostOwned=true;
            probeCanvas=host.GetComponent<Canvas>();probeCanvas.renderMode=RenderMode.WorldSpace;
            probeCanvas.overrideSorting=true;probeCanvas.sortingOrder=32760;probeCanvas.pixelPerfect=false;
            var canvasRect=(RectTransform)host.transform;
            canvasRect.anchorMin=canvasRect.anchorMax=new Vector2(.5f,.5f);canvasRect.pivot=new Vector2(.5f,.5f);
            canvasRect.sizeDelta=new Vector2(canvasSide,canvasSide);canvasRect.position=Vector3.zero;

            cameraObject=new GameObject("__MaskClipProbeCamera",typeof(Camera));
            cameraObject.hideFlags=HideFlags.HideAndDontSave;cameraObject.layer=probeLayer;
            SceneManager.MoveGameObjectToScene(cameraObject,probeScene);
            probeCamera=cameraObject.GetComponent<Camera>();probeCamera.enabled=false;
            probeCamera.clearFlags=CameraClearFlags.SolidColor;probeCamera.backgroundColor=Color.clear;
            probeCamera.orthographic=true;probeCamera.orthographicSize=canvasSide*.5f;
            probeCamera.aspect=1f;probeCamera.nearClipPlane=.01f;probeCamera.farClipPlane=100f;
            probeCamera.cullingMask=1<<probeLayer;probeCamera.allowHDR=false;probeCamera.allowMSAA=false;
            cameraObject.transform.position=new Vector3(0,0,-10);cameraObject.transform.rotation=Quaternion.identity;
            probeCanvas.worldCamera=probeCamera;

            var probeMaskObject=new GameObject("__MaskClipProbeRect",typeof(RectTransform),typeof(CanvasRenderer));
            probeMaskObject.hideFlags=HideFlags.HideAndDontSave;probeMaskObject.layer=probeLayer;
            probeMaskObject.transform.SetParent(host.transform,false);probeMaskObject.SetActive(false);
            probeMaskRect=(RectTransform)probeMaskObject.transform;
            var probePivot=sourceRect.pivot;
            probeMaskRect.anchorMin=probeMaskRect.anchorMax=new Vector2(.5f,.5f);
            probeMaskRect.pivot=probePivot;probeMaskRect.sizeDelta=sourceRect.sizeDelta;
            probeMaskRect.localScale=sourceRect.localScale;probeMaskRect.localRotation=sourceRect.localRotation;
            var centerFromPivot=new Vector3((.5f-probePivot.x)*rect.width,(.5f-probePivot.y)*rect.height,0);
            probeMaskRect.anchoredPosition3D=-(probeMaskRect.localRotation*Vector3.Scale(probeMaskRect.localScale,centerFromPivot));
            var maskGraphic=probeMaskObject.AddComponent<Image>();maskGraphic.color=Color.white;
            maskGraphic.raycastTarget=false;maskGraphic.enabled=spec.enabled;
            probeMask=probeMaskObject.AddComponent<Mask>();probeMask.showMaskGraphic=false;probeMask.enabled=spec.enabled;

            var childObject=new GameObject("__MaskClipProbeChild",typeof(RectTransform),typeof(CanvasRenderer));
            childObject.hideFlags=HideFlags.HideAndDontSave;childObject.layer=probeLayer;
            childObject.transform.SetParent(probeMaskObject.transform,false);
            var childRect=(RectTransform)childObject.transform;
            childRect.anchorMin=childRect.anchorMax=new Vector2(.5f,.5f);childRect.pivot=new Vector2(.5f,.5f);
            childRect.sizeDelta=new Vector2(rect.width*1.5f,rect.height*.75f);
            childRect.anchoredPosition=new Vector2((outsideLocal.x-insideLocal.x)*.5f,0);
            childRect.localScale=Vector3.one;childRect.localRotation=Quaternion.identity;
            childGraphic=childObject.AddComponent<Image>();childGraphic.color=Color.white;
            childGraphic.raycastTarget=true;childGraphic.maskable=true;
            probeMaskObject.SetActive(true);childObject.SetActive(true);
            result.probeMaskActiveInHierarchy=probeMaskObject.activeInHierarchy;
            result.probeChildActiveInHierarchy=childObject.activeInHierarchy;
            if(!result.probeMaskActiveInHierarchy||!result.probeChildActiveInHierarchy)
            {diagnostics.Add("disposable-mask-or-child-not-active-for-probe");break;}
            renderTexture=new RenderTexture(MaskClipProbeSize,MaskClipProbeSize,24,RenderTextureFormat.ARGB32);
            renderTexture.name="__MaskClipProbeRT";renderTexture.hideFlags=HideFlags.HideAndDontSave;
            if(!renderTexture.Create()||renderTexture.depth<24||!SystemInfo.SupportsRenderTextureFormat(RenderTextureFormat.ARGB32))
            {diagnostics.Add("stencil-rendertexture-backend-unavailable");break;}
            probeCamera.targetTexture=renderTexture;
            Canvas.ForceUpdateCanvases();
            probeCamera.Render();result.renderCompleted=true;
            var insideWorld=probeMaskRect.TransformPoint(new Vector3(insideLocal.x,insideLocal.y,0));
            var outsideWorld=probeMaskRect.TransformPoint(new Vector3(outsideLocal.x,outsideLocal.y,0));
            var insideViewport=probeCamera.WorldToViewportPoint(insideWorld);
            var outsideViewport=probeCamera.WorldToViewportPoint(outsideWorld);
            result.insideWorldPoint=new[]{insideWorld.x,insideWorld.y,insideWorld.z};
            result.outsideWorldPoint=new[]{outsideWorld.x,outsideWorld.y,outsideWorld.z};
            result.insideViewportPoint=new[]{insideViewport.x,insideViewport.y,insideViewport.z};
            result.outsideViewportPoint=new[]{outsideViewport.x,outsideViewport.y,outsideViewport.z};
            var ix=Mathf.FloorToInt(insideViewport.x*MaskClipProbeSize);var iy=Mathf.FloorToInt(insideViewport.y*MaskClipProbeSize);
            var ox=Mathf.FloorToInt(outsideViewport.x*MaskClipProbeSize);var oy=Mathf.FloorToInt(outsideViewport.y*MaskClipProbeSize);
            result.insidePixel=new[]{ix,iy};result.outsidePixel=new[]{ox,oy};
            if(ix<0||iy<0||ix>=MaskClipProbeSize||iy>=MaskClipProbeSize||ox<0||oy<0||
                ox>=MaskClipProbeSize||oy>=MaskClipProbeSize||insideViewport.z<=0||outsideViewport.z<=0)
            {diagnostics.Add("inside-or-outside-sample-point-falls-outside-camera");break;}
            readbackTexture=new Texture2D(MaskClipProbeSize,MaskClipProbeSize,TextureFormat.RGBA32,false,true);
            RenderTexture.active=renderTexture;
            readbackTexture.ReadPixels(new Rect(0,0,MaskClipProbeSize,MaskClipProbeSize),0,0,false);
            readbackTexture.Apply(false,false);
            var insidePixel=readbackTexture.GetPixel(ix,iy);var outsidePixel=readbackTexture.GetPixel(ox,oy);
            var inside32=(Color32)insidePixel;var outside32=(Color32)outsidePixel;
            result.insideRgba=MaskClipPixel(inside32);result.outsideRgba=MaskClipPixel(outside32);
            result.imageWidth=MaskClipProbeSize;result.imageHeight=MaskClipProbeSize;
            pngBytes=readbackTexture.EncodeToPNG();result.imageSha256=MaskClipHash(pngBytes);
            result.pixelReadbackVerified=true;
            result.insidePixelVerified=MaskClipExpectedOpaqueWhite(inside32);
            result.outsidePixelVerified=spec.enabled?MaskClipExpectedClear(outside32):MaskClipExpectedOpaqueWhite(outside32);
            var insideScreen=RectTransformUtility.WorldToScreenPoint(probeCamera,insideWorld);
            var outsideScreen=RectTransformUtility.WorldToScreenPoint(probeCamera,outsideWorld);
            result.maskInsidePointAccepted=probeMask.IsRaycastLocationValid(insideScreen,probeCamera);
            result.maskOutsidePointRejected=!probeMask.IsRaycastLocationValid(outsideScreen,probeCamera);
            result.childGraphicInsideAccepted=childGraphic.Raycast(insideScreen,probeCamera);
            var childOutsideAccepted=childGraphic.Raycast(outsideScreen,probeCamera);
            result.childGraphicOutsideRejected=spec.enabled&&!childOutsideAccepted;
            result.disabledChildGraphicOutsideAccepted=!spec.enabled&&childOutsideAccepted;
            result.stencilClipVerified=spec.enabled&&result.insidePixelVerified&&result.outsidePixelVerified;
            result.disabledNoClipVerified=!spec.enabled&&result.insidePixelVerified&&result.outsidePixelVerified;
            if(!result.insidePixelVerified)diagnostics.Add("inside-stimulus-pixel-is-not-opaque-white");
            if(!result.outsidePixelVerified)diagnostics.Add(spec.enabled?"outside-stimulus-pixel-was-not-stencil-clipped":"disabled-mask-outside-stimulus-was-not-visible");
            if(!result.maskInsidePointAccepted||(spec.enabled?!result.maskOutsidePointRejected:result.maskOutsidePointRejected))
                diagnostics.Add("Mask.IsRaycastLocationValid-inside-outside-contract-failed");
            if(!result.childGraphicInsideAccepted||
                (spec.enabled&&!result.childGraphicOutsideRejected)||(!spec.enabled&&!result.disabledChildGraphicOutsideAccepted))
                diagnostics.Add("child-Graphic.Raycast-inside-outside-contract-failed");
            }while(false);
        }
        catch(Exception exception)
        {
            diagnostics.Add("probe-exception:"+exception.GetType().Name+":"+exception.Message);
        }
        finally
        {
            RenderTexture.active=priorActiveTexture;
            if(probeCamera!=null)probeCamera.targetTexture=null;
            if(readbackTexture!=null)UnityEngine.Object.DestroyImmediate(readbackTexture);
            if(renderTexture!=null){renderTexture.Release();UnityEngine.Object.DestroyImmediate(renderTexture);}
            if(cameraObject!=null)UnityEngine.Object.DestroyImmediate(cameraObject);
            if(host!=null)UnityEngine.Object.DestroyImmediate(host);
            if(result.probeSceneCreated&&probeScene.IsValid())EditorSceneManager.ClosePreviewScene(probeScene);
            result.probeSceneClosed=result.probeSceneCreated&&!probeScene.IsValid();
            result.probeObjectsDestroyed=host==null&&cameraObject==null&&renderTexture==null&&readbackTexture==null;
            result.sourceStatePreserved=loadedSource!=null&&loadedSource.activeSelf==sourceActiveSelfBefore&&
                loadedSource.activeInHierarchy==sourceActiveHierarchyBefore&&sourceMask!=null&&sourceMask.enabled==sourceMaskEnabledBefore;
            RectTransform afterRect;bool afterActiveSelf,afterActive;string afterDiagnostic;
            result.sourceGeometryPreserved=loadedSource!=null&&sourceRect!=null&&
                MaskClipSourceGeometry(plan,spec,loadedSource,out afterRect,out afterActiveSelf,out afterActive,out afterDiagnostic)&&
                afterRect==sourceRect&&afterActiveSelf==sourceActiveSelfBefore&&afterActive==sourceActiveHierarchyBefore;
            if(!result.sourceStatePreserved)diagnostics.Add("original-source-activity-or-mask-enabled-state-changed");
            if(sourceRect!=null&&!result.sourceGeometryPreserved)diagnostics.Add("original-source-RectTransform-changed-during-probe");
        }
        var outputRoot=MaskClipEvidenceRoot();
        var token=MaskClipHash(Encoding.UTF8.GetBytes(spec.sourceId)).Substring(0,20);
        var pngName="maskclip-"+token+".png";var jsonName="maskclip-"+token+".json";
        try
        {
            Directory.CreateDirectory(outputRoot);
            if(pngBytes!=null)
            {
                File.WriteAllBytes(Path.Combine(outputRoot,pngName),pngBytes);
                result.imagePath="Analysis/Readback/MaskClipping/"+pngName;
            }
            result.evidencePath="Analysis/Readback/MaskClipping/"+jsonName;
        }
        catch(Exception exception){diagnostics.Add("evidence-output-failed:"+exception.GetType().Name);}
        result.diagnostics=diagnostics.ToArray();
        result.verified=result.supported&&result.sourceGeometryVerified&&result.sourceGeometryPreserved&&
            result.sourceStatePreserved&&result.probeHostOwned&&
            result.probeSceneCreated&&result.probeSceneClosed&&
            result.probeMaskActiveInHierarchy&&result.probeChildActiveInHierarchy&&
            result.probeObjectsDestroyed&&result.renderCompleted&&result.pixelReadbackVerified&&
            result.insidePixelVerified&&result.outsidePixelVerified&&result.maskInsidePointAccepted&&
            (spec.enabled?result.maskOutsidePointRejected:!result.maskOutsidePointRejected)&&result.childGraphicInsideAccepted&&
            (spec.enabled?result.childGraphicOutsideRejected:result.disabledChildGraphicOutsideAccepted)&&
            (spec.enabled?result.stencilClipVerified:result.disabledNoClipVerified)&&String.IsNullOrEmpty(result.imagePath)==false;
        result.status=result.verified?(spec.enabled?"native-stencil-clipping-verified":"disabled-mask-no-clip-verified"):
            result.supported?"native-clipping-probe-gap":"unsupported-mask-clipping-semantics";
        try{File.WriteAllText(Path.Combine(MaskClipEvidenceRoot(),jsonName),JsonUtility.ToJson(result,true));}
        catch(Exception){result.verified=false;result.status="native-clipping-probe-gap";}
        return result;
    }
}
