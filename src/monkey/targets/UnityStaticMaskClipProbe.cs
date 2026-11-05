using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using Monkey.StaticMaskSort;

public static partial class MonkeyImporter
{
    [Serializable] public sealed class MaskClipProbeReadback
    {
        public string sourceId, node, status, method, probeProfile, stimulus, imagePath, imageSha256, evidencePath,
            controlImagePath, controlImageSha256, graphicsDeviceType, controlContextSha256, maskedContextSha256;
        public string expectedInsidePixelClass, expectedOutsidePixelClass;
        public bool supported, sourceGeometryVerified, sourceNodeActiveSelf, sourceNodeActiveInHierarchy,
            sourceMaskEnabled, sourceStatePreserved, probeHostOwned, probeObjectsDestroyed,
            sourceGeometryPreserved, probeSceneCreated, probeSceneClosed,
            renderCompleted, pixelReadbackVerified, insidePixelVerified, outsidePixelVerified,
            maskInsidePointAccepted, maskOutsidePointRejected, childGraphicInsideAccepted,
            childGraphicOutsideRejected, disabledChildGraphicOutsideAccepted,
            stencilClipVerified, disabledNoClipVerified, probeMaskActiveInHierarchy, probeChildActiveInHierarchy,
            sourceAppFrame, sourceVisualParityClaimed, verified, stimulusSpriteVerified, stimulusObjectsDestroyed,
            graphicsBackendAvailable, probeCameraSceneBound, unmaskedControlRenderCompleted,
            unmaskedControlVerified, unmaskedControlSameRenderContext;
        public bool sourceTextureAlphaVerified, sourceMaskMaterialVerified, alphaSamplesVerified;
        public string sourceSpriteFrameId, sourceSpriteGuid, sourceTextureId, sourceTexturePath, sourceTextureGuid,
            sourceTextureSha256, sourceTextureFormat, sourceTextureImportMode, sourceTextureMeshType,
            sourceTextureCompression, sourceTextureAlphaSource, sourceMaterialGuid, sourceMaterialShaderPath,
            sourceMaterialShaderSha256, alphaDiscardPolicy;
        public long sourceSpriteLocalFileId;
        public int sourceTextureWidth, sourceTextureHeight;
        public float sourceAlphaThreshold;
        public MaskClipAlphaSample[] sourceAlphaSamples;
        public int imageWidth, imageHeight;
        public float[] insideLocalPoint, outsideLocalPoint, insideWorldPoint, outsideWorldPoint;
        public float[] insideViewportPoint, outsideViewportPoint;
        public int[] insidePixel, outsidePixel, insideRgba, outsideRgba;
        public int[] unmaskedControlInsideRgba, unmaskedControlOutsideRgba;
        public MaskClipControlAlphaSample[] unmaskedControlAlphaSamples;
        public string[] diagnostics;
    }

    [Serializable] public sealed class MaskClipAlphaSample
    {
        public string kind;
        public bool sourceAlphaPass, expectedVisible, pixelVerified;
        public int sourceAlphaByte;
        public float sourceAlpha;
        public int[] sourceTexturePixel, pixel, rgba;
        public float[] localPoint, viewportPoint;
    }

    [Serializable] public sealed class MaskClipControlAlphaSample
    {
        public string kind;
        public int[] pixel,rgba;
        public float[] viewportPoint;
    }

    sealed class MaskClipImageInput
    {
        public TextureSpec textureSpec;
        public Sprite sprite;
        public Texture2D decodedSourceTexture;
        public TextureImporter importer;
        public byte[] sourceBytes;
        public Rect textureRect;
        public string textureGuid,spriteGuid,materialGuid,shaderPath,shaderSha256,textureFormat;
        public long spriteLocalFileId;
        public Color32[] sourcePixels;
        public int width,height;
    }

    const string MaskClipRectMethod="unity-ui-mask-stencil-rendertexture-v2";
    const string MaskClipImageMethod="unity-ui-mask-alpha-stencil-rendertexture-v1";
    const string MaskClipImageProfile="sprite-alpha-threshold";
    const int MaskClipRectProbeSize=256;
    const int MaskClipImageProbeSize=512;

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

    static string MaskClipRenderContextSha256(Scene scene,Camera camera,Canvas canvas,RenderTexture target)
    {
        if(camera==null||canvas==null||target==null)return null;
        var value=String.Join("|",new[]{scene.handle.ToString(),camera.GetEntityId().ToString(),camera.scene.handle.ToString(),
            camera.cullingMask.ToString(),camera.clearFlags.ToString(),camera.orthographic.ToString(),camera.orthographicSize.ToString("R"),
            camera.aspect.ToString("R"),camera.nearClipPlane.ToString("R"),camera.farClipPlane.ToString("R"),
            canvas.GetEntityId().ToString(),canvas.renderMode.ToString(),canvas.sortingOrder.ToString(),canvas.overrideSorting.ToString(),
            canvas.worldCamera==null?"null":canvas.worldCamera.GetEntityId().ToString(),target.GetEntityId().ToString(),
            target.width.ToString(),target.height.ToString(),target.depth.ToString(),target.format.ToString()});
        return MaskClipHash(Encoding.UTF8.GetBytes(value));
    }

    static bool TryMaskClipImageInput(Plan plan,MaskSpec spec,Image sourceImage,out MaskClipImageInput input,out string diagnostic)
    {
        input=null;diagnostic=null;
        if(spec.maskType!=2||String.IsNullOrEmpty(spec.spriteFrameUuid)||sourceImage==null||sourceImage.sprite==null)
        {diagnostic="image-mask-source-sprite-absent";return false;}
        var sourceSeparator=(spec.sourceId??String.Empty).IndexOf(':');
        if(sourceSeparator<=0||sourceSeparator==spec.sourceId.Length-1||spec.spriteFrameUuid.Contains(":"))
        {diagnostic="image-mask-source-and-sprite-bundle-identity-invalid";return false;}
        var textureId=spec.sourceId.Substring(0,sourceSeparator)+":"+spec.spriteFrameUuid;
        var textureRows=(plan.textures??Array.Empty<TextureSpec>()).Where(row=>row!=null&&row.id==textureId).ToArray();
        if(textureRows.Length!=1)
        {diagnostic="image-mask-source-texture-id-absent-or-ambiguous";return false;}
        var textureSpec=textureRows[0];
        if(String.IsNullOrEmpty(textureSpec.path)||!textureSpec.path.StartsWith("Assets/",StringComparison.Ordinal)||
            textureSpec.path.Contains("..")||textureSpec.size==null||textureSpec.size.Length<2)
        {diagnostic="image-mask-source-texture-plan-row-invalid";return false;}
        var sprite=sourceImage.sprite;var sourceTexture=sprite.texture;
        var sourceSpritePath=AssetDatabase.GetAssetPath(sprite);
        var sourceTexturePath=AssetDatabase.GetAssetPath(sourceTexture);
        if(sourceTexture==null||sprite.packed||sourceSpritePath!=textureSpec.path||sourceTexturePath!=textureSpec.path)
        {diagnostic="image-mask-source-sprite-does-not-map-to-one-unpacked-plan-texture";return false;}
        if(sourceImage.type!=Image.Type.Simple||sourceImage.useSpriteMesh||sourceImage.preserveAspect||
            sourceImage.pixelsPerUnitMultiplier!=1f||sprite.border.sqrMagnitude>0.000001f)
        {diagnostic="image-mask-source-Image-layout-is-outside-verified-Simple-FullRect-profile";return false;}
        var importer=AssetImporter.GetAtPath(textureSpec.path) as TextureImporter;
        if(importer==null||importer.textureType!=TextureImporterType.Sprite||importer.spriteImportMode!=SpriteImportMode.Single||
            importer.textureCompression!=TextureImporterCompression.Uncompressed||importer.alphaSource!=TextureImporterAlphaSource.FromInput||
            importer.mipmapEnabled||importer.npotScale!=TextureImporterNPOTScale.None)
        {diagnostic="image-mask-source-texture-import-settings-are-not-verified-Single-FullRect-uncompressed-alpha";return false;}
        var settings=new TextureImporterSettings();importer.ReadTextureSettings(settings);
        if(settings.spriteMeshType!=SpriteMeshType.FullRect)
        {diagnostic="image-mask-source-Sprite-mesh-is-not-FullRect";return false;}
        var textureRect=sprite.textureRect;
        if(!MaskClipNearly(textureRect.x,0)||!MaskClipNearly(textureRect.y,0)||
            !MaskClipNearly(textureRect.width,sourceTexture.width)||!MaskClipNearly(textureRect.height,sourceTexture.height)||
            !MaskClipNearly(textureSpec.size[0],sourceTexture.width)||!MaskClipNearly(textureSpec.size[1],sourceTexture.height)||
            !MaskClipNearly(sprite.rect.width,sourceTexture.width)||!MaskClipNearly(sprite.rect.height,sourceTexture.height))
        {diagnostic="image-mask-source-Sprite-does-not-cover-the-exact-plan-texture-rectangle";return false;}
        var material=sourceImage.material;
        if(material==null||material.shader==null||material.shader.name!="Monkey/NativeStaticImageMask"||
            !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material,out var materialGuid,out long _)||
            materialGuid!=spec.unityMaskMaterialGuid||material.GetFloat("_AlphaThreshold")!=spec.alphaThreshold)
        {diagnostic="image-mask-source-material-identity-or-alpha-threshold-differs";return false;}
        var shaderPath=AssetDatabase.GetAssetPath(material.shader);
        if(shaderPath!=spec.unityMaskShaderPath||String.IsNullOrEmpty(shaderPath))
        {diagnostic="image-mask-source-shader-path-differs";return false;}
        var shaderAbsolute=Path.GetFullPath(Path.Combine(Application.dataPath,"..",shaderPath));
        if(!File.Exists(shaderAbsolute))
        {diagnostic="image-mask-source-shader-file-absent";return false;}
        var shaderSha=MaskClipHash(File.ReadAllBytes(shaderAbsolute));
        if(shaderSha!=spec.unityMaskShaderSha256)
        {diagnostic="image-mask-source-shader-hash-differs";return false;}
        var textureAbsolute=Path.GetFullPath(Path.Combine(Application.dataPath,"..",textureSpec.path));
        if(!File.Exists(textureAbsolute))
        {diagnostic="image-mask-source-PNG-file-absent";return false;}
        var sourceBytes=File.ReadAllBytes(textureAbsolute);
        var decoded=new Texture2D(2,2,TextureFormat.RGBA32,false,true);
        decoded.name="__MaskClipSourceAlpha";decoded.hideFlags=HideFlags.HideAndDontSave;
        if(!ImageConversion.LoadImage(decoded,sourceBytes,false)||decoded.width!=sourceTexture.width||decoded.height!=sourceTexture.height)
        {UnityEngine.Object.DestroyImmediate(decoded);diagnostic="image-mask-source-PNG-decode-or-dimension-check-failed";return false;}
        if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(sprite,out var spriteGuid,out long spriteLocal)||
            String.IsNullOrEmpty(spriteGuid)||spriteLocal==0)
        {UnityEngine.Object.DestroyImmediate(decoded);diagnostic="image-mask-source-Sprite-persistent-identity-absent";return false;}
        var textureGuid=AssetDatabase.AssetPathToGUID(textureSpec.path);
        if(String.IsNullOrEmpty(textureGuid)||textureGuid!=spriteGuid)
        {UnityEngine.Object.DestroyImmediate(decoded);diagnostic="image-mask-source-texture-and-Sprite-GUID-differ";return false;}
        input=new MaskClipImageInput{textureSpec=textureSpec,sprite=sprite,decodedSourceTexture=decoded,importer=importer,
            sourceBytes=sourceBytes,textureRect=textureRect,textureGuid=textureGuid,spriteGuid=spriteGuid,
            spriteLocalFileId=spriteLocal,materialGuid=materialGuid,shaderPath=shaderPath,shaderSha256=shaderSha,
            textureFormat=sourceTexture.format.ToString(),sourcePixels=decoded.GetPixels32(),width=decoded.width,height=decoded.height};
        return true;
    }

    static bool MaskClipAlphaPass(byte alpha,float threshold)
    {
        return alpha/255f>=threshold;
    }

    static Vector2 MaskClipImageLocalPoint(Rect localRect,Rect textureRect,int x,int y)
    {
        var u=(x+.5f-textureRect.x)/textureRect.width;
        var v=(y+.5f-textureRect.y)/textureRect.height;
        return new Vector2(localRect.xMin+u*localRect.width,localRect.yMin+v*localRect.height);
    }

    static bool MaskClipAlphaPixel(MaskClipImageInput input,int alpha,float threshold,bool nonzeroOnly,out int x,out int y)
    {
        x=y=-1;
        var xMin=Mathf.Max(0,Mathf.CeilToInt(input.textureRect.x));
        var yMin=Mathf.Max(0,Mathf.CeilToInt(input.textureRect.y));
        var xMax=Mathf.Min(input.width,Mathf.FloorToInt(input.textureRect.xMax));
        var yMax=Mathf.Min(input.height,Mathf.FloorToInt(input.textureRect.yMax));
        var best=-1;
        for(var py=yMin+2;py<yMax-2;py++)for(var px=xMin+2;px<xMax-2;px++)
        {
            var value=input.sourcePixels[py*input.width+px].a;
            var matches=alpha==-1?(MaskClipAlphaPass(value,threshold)&&(!nonzeroOnly||value>0)):
                alpha==-2?(!MaskClipAlphaPass(value,threshold)&&value>0):value==alpha&&(!nonzeroOnly||value>0);
            if(!matches)continue;
            var stable=true;
            for(var dy=-2;dy<=2&&stable;dy++)for(var dx=-2;dx<=2;dx++)
            {
                var neighbor=input.sourcePixels[(py+dy)*input.width+px+dx].a;
                var neighborMatches=alpha==-1?(MaskClipAlphaPass(neighbor,threshold)&&(!nonzeroOnly||neighbor>0)):
                    alpha==-2?(!MaskClipAlphaPass(neighbor,threshold)&&neighbor>0):neighbor==alpha&&(!nonzeroOnly||neighbor>0);
                if(!neighborMatches){stable=false;break;}
            }
            if(stable&&value>best){best=value;x=px;y=py;}
        }
        return x>=0&&y>=0;
    }

    static MaskClipAlphaSample MaskClipBuildAlphaSample(MaskClipImageInput input,Rect localRect,
        MaskSpec spec,string kind,int requestedAlpha)
    {
        if(input==null)return null;
        if(!MaskClipAlphaPixel(input,requestedAlpha,spec.alphaThreshold,false,out var x,out var y))return null;
        var alpha=input.sourcePixels[y*input.width+x].a;
        var passes=MaskClipAlphaPass(alpha,spec.alphaThreshold);
        var point=MaskClipImageLocalPoint(localRect,input.textureRect,x,y);
        return new MaskClipAlphaSample{kind=kind,sourceAlphaByte=alpha,sourceAlpha=alpha/255f,
            sourceAlphaPass=passes,expectedVisible=!spec.enabled||passes,
            sourceTexturePixel=new[]{x,y},localPoint=new[]{point.x,point.y}};
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
            status="gap",method=spec!=null&&spec.maskType==2?MaskClipImageMethod:MaskClipRectMethod,
            probeProfile=spec!=null&&spec.maskType==2?MaskClipImageProfile:"rect",
            stimulus="owned-white-sprite-child-on-transparent-world-space-canvas",
            supported=spec!=null&&!spec.inverted&&(spec.maskType==0||spec.maskType==2),
            sourceMaskEnabled=spec!=null&&spec.enabled,
            sourceNodeActiveSelf=loadedSource!=null&&loadedSource.activeSelf,
            sourceNodeActiveInHierarchy=loadedSource!=null&&loadedSource.activeInHierarchy,
            graphicsDeviceType=SystemInfo.graphicsDeviceType.ToString(),
            sourceAppFrame=false,sourceVisualParityClaimed=false,verified=false,
            expectedInsidePixelClass="opaque-white",
            diagnostics=Array.Empty<string>()
        };
        var diagnostics=new List<string>();var pngBytes=null as byte[];var controlPngBytes=null as byte[];
        GameObject host=null,cameraObject=null;Camera probeCamera=null;Canvas probeCanvas=null;
        GameObject childObject=null;RectTransform probeMaskRect=null;Mask probeMask=null;Image childGraphic=null;
        RenderTexture renderTexture=null;Texture2D readbackTexture=null,stimulusTexture=null;
        Sprite stimulusSprite=null;MaskClipImageInput imageInput=null;var priorActiveTexture=RenderTexture.active;
        var probeSize=spec!=null&&spec.maskType==2?MaskClipImageProbeSize:MaskClipRectProbeSize;
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
            if(SystemInfo.graphicsDeviceType==GraphicsDeviceType.Null)
            {result.graphicsBackendAvailable=false;diagnostics.Add("graphics-device-null");break;}
            result.graphicsBackendAvailable=SystemInfo.supportsRenderTextures&&SystemInfo.SupportsRenderTextureFormat(RenderTextureFormat.ARGB32);
            if(!result.graphicsBackendAvailable)
            {diagnostics.Add("graphics-rendertexture-backend-unavailable");break;}
            if(!result.supported)
            {diagnostics.Add("clip-probe-supports-only-noninverted-rect-or-pinned-image-alpha-mask");break;}
            if(sourceMask==null||loadedSource.GetComponent<NativeStaticMaskIdentity>()==null)
            {diagnostics.Add("source-native-mask-or-identity-absent");break;}
            if(!MaskClipSourceGeometry(plan,spec,loadedSource,out sourceRect,out sourceActiveSelf,out sourceActive,out geometryDiagnostic))
            {result.sourceNodeActiveSelf=sourceActiveSelf;result.sourceNodeActiveInHierarchy=sourceActive;
                diagnostics.Add(geometryDiagnostic??"source-geometry-unverified");break;}
            var identity=loadedSource.GetComponent<NativeStaticMaskIdentity>();
            var sourceGraphic=loadedSource.GetComponent<Graphic>();
            var sourceImage=sourceGraphic as Image;
            if(spec.maskType==2)
            {
                if(!TryMaskClipImageInput(plan,spec,sourceImage,out imageInput,out var imageInputDiagnostic))
                {diagnostics.Add(imageInputDiagnostic??"image-mask-source-input-unverified");break;}
                result.probeProfile=MaskClipImageProfile;result.sourceSpriteFrameId=spec.spriteFrameUuid;
                result.sourceSpriteGuid=imageInput.spriteGuid;result.sourceSpriteLocalFileId=imageInput.spriteLocalFileId;
                result.sourceTextureId=imageInput.textureSpec.id;result.sourceTexturePath=imageInput.textureSpec.path;
                result.sourceTextureGuid=imageInput.textureGuid;result.sourceTextureSha256=MaskClipHash(imageInput.sourceBytes);
                result.sourceTextureFormat=imageInput.textureFormat;
                result.sourceTextureImportMode=imageInput.importer.spriteImportMode.ToString();
                result.sourceTextureMeshType="FullRect";result.sourceTextureCompression=imageInput.importer.textureCompression.ToString();
                result.sourceTextureAlphaSource=imageInput.importer.alphaSource.ToString();
                result.sourceTextureWidth=imageInput.width;result.sourceTextureHeight=imageInput.height;
                result.sourceMaterialGuid=imageInput.materialGuid;result.sourceMaterialShaderPath=imageInput.shaderPath;
                result.sourceMaterialShaderSha256=imageInput.shaderSha256;result.alphaDiscardPolicy="discard-if-source-alpha-less-than-threshold";
                result.sourceAlphaThreshold=spec.alphaThreshold;result.sourceTextureAlphaVerified=true;result.sourceMaskMaterialVerified=true;
            }
            var sourceTypedReadback=UnityStaticMaskSort.ReadStaticMask(spec,loadedSource,
                id=>imageInput!=null&&id==spec.spriteFrameUuid?imageInput.sprite:null);
            if(identity.sourceId!=spec.sourceId||identity.nativeId!=spec.nativeId||sourceMask.enabled!=spec.enabled||
                sourceMask.showMaskGraphic||sourceGraphic==null||sourceImage==null||
                sourceGraphic.enabled!=spec.enabled||sourceGraphic.raycastTarget||!sourceTypedReadback.verified)
            {diagnostics.Add("source-mask-typed-identity-or-graphic-setup-differs");break;}
            var rect=sourceRect.rect;
            if(rect.width<=0||rect.height<=0||Single.IsNaN(rect.width)||Single.IsNaN(rect.height)||
                Single.IsInfinity(rect.width)||Single.IsInfinity(rect.height))
            {diagnostics.Add("source-rect-mask-geometry-degenerate");break;}
            var outsideLocal=MaskClipExpectedOutsidePoint(rect);var insideLocal=rect.center;
            if(imageInput!=null)
            {
                var samples=new List<MaskClipAlphaSample>();
                var alphaZero=MaskClipBuildAlphaSample(imageInput,rect,spec,"transparent-zero",0);
                var alphaOpaque=MaskClipBuildAlphaSample(imageInput,rect,spec,"opaque",255);
                var alphaOne=MaskClipBuildAlphaSample(imageInput,rect,spec,"low-nonzero",1);
                if(alphaOne==null&&spec.alphaThreshold>0)
                    alphaOne=MaskClipBuildAlphaSample(imageInput,rect,spec,"under-threshold-nonzero",-2);
                if(alphaZero==null||alphaOpaque==null)
                {diagnostics.Add("image-mask-source-lacks-stable-transparent-or-passing-alpha-sample");break;}
                samples.Add(alphaOpaque);samples.Add(alphaZero);if(alphaOne!=null)samples.Add(alphaOne);
                result.sourceAlphaSamples=samples.ToArray();insideLocal=new Vector2(alphaOpaque.localPoint[0],alphaOpaque.localPoint[1]);
            }
            result.insideLocalPoint=new[]{insideLocal.x,insideLocal.y};
            result.outsideLocalPoint=new[]{outsideLocal.x,outsideLocal.y};
            result.sourceGeometryVerified=true;result.sourceNodeActiveSelf=sourceActiveSelf;
            result.sourceNodeActiveInHierarchy=sourceActive;result.sourceMaskEnabled=spec.enabled;
            result.expectedOutsidePixelClass=spec.enabled?"clear":"opaque-white-disabled-no-clip";

            var worldScale=sourceRect.localScale;
            var spanX=Mathf.Abs(rect.width*worldScale.x)+Mathf.Abs(rect.height*worldScale.y);
            var spanY=Mathf.Abs(rect.width*worldScale.x)+Mathf.Abs(rect.height*worldScale.y);
            var canvasSide=Mathf.Max((imageInput!=null?2.5f:4f)*Mathf.Max(spanX,spanY),4f);
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
            probeCamera.scene=probeScene;
            result.probeCameraSceneBound=probeCamera.scene==probeScene;
            if(!result.probeCameraSceneBound){diagnostics.Add("probe-camera-not-bound-to-preview-scene");break;}

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
            stimulusTexture=new Texture2D(1,1,TextureFormat.RGBA32,false,true);
            stimulusTexture.name="__MaskClipOpaqueWhite";stimulusTexture.hideFlags=HideFlags.HideAndDontSave;
            stimulusTexture.filterMode=FilterMode.Point;stimulusTexture.wrapMode=TextureWrapMode.Clamp;
            stimulusTexture.SetPixel(0,0,Color.white);stimulusTexture.Apply(false,false);
            stimulusSprite=Sprite.Create(stimulusTexture,new Rect(0,0,1,1),new Vector2(.5f,.5f),1f,0,SpriteMeshType.FullRect);
            stimulusSprite.name="__MaskClipOpaqueWhiteSprite";stimulusSprite.hideFlags=HideFlags.HideAndDontSave;
            result.stimulusSpriteVerified=stimulusTexture.GetPixel(0,0).a>=.999f&&stimulusSprite!=null&&stimulusSprite.rect.width==1&&stimulusSprite.rect.height==1;
            if(!result.stimulusSpriteVerified){diagnostics.Add("owned-white-sprite-stimulus-invalid");break;}
            var maskGraphic=probeMaskObject.AddComponent<Image>();maskGraphic.color=Color.white;
            maskGraphic.type=Image.Type.Simple;maskGraphic.preserveAspect=false;maskGraphic.useSpriteMesh=false;
            maskGraphic.sprite=imageInput==null?stimulusSprite:imageInput.sprite;
            maskGraphic.material=imageInput==null?null:sourceImage.material;
            maskGraphic.raycastTarget=false;maskGraphic.enabled=spec.enabled;
            probeMask=probeMaskObject.AddComponent<Mask>();probeMask.showMaskGraphic=false;probeMask.enabled=spec.enabled;

            childObject=new GameObject("__MaskClipProbeChild",typeof(RectTransform),typeof(CanvasRenderer));
            childObject.hideFlags=HideFlags.HideAndDontSave;childObject.layer=probeLayer;
            childObject.transform.SetParent(probeMaskObject.transform,false);
            var childRect=(RectTransform)childObject.transform;
            childRect.anchorMin=childRect.anchorMax=new Vector2(.5f,.5f);childRect.pivot=new Vector2(.5f,.5f);
            childRect.sizeDelta=new Vector2(rect.width*1.5f,rect.height*1.5f);
            childRect.anchoredPosition=new Vector2(rect.center.x+rect.width*.5f,rect.center.y);
            childRect.localScale=Vector3.one;childRect.localRotation=Quaternion.identity;
            childGraphic=childObject.AddComponent<Image>();childGraphic.color=Color.white;
            childGraphic.type=Image.Type.Simple;childGraphic.preserveAspect=false;childGraphic.useSpriteMesh=false;
            childGraphic.sprite=stimulusSprite;
            childGraphic.raycastTarget=true;childGraphic.maskable=true;
            result.stimulusObjectsDestroyed=false;
            probeMaskObject.SetActive(true);childObject.SetActive(true);
            result.probeMaskActiveInHierarchy=probeMaskObject.activeInHierarchy;
            result.probeChildActiveInHierarchy=childObject.activeInHierarchy;
            if(!result.probeMaskActiveInHierarchy||!result.probeChildActiveInHierarchy)
            {diagnostics.Add("disposable-mask-or-child-not-active-for-probe");break;}
            renderTexture=new RenderTexture(probeSize,probeSize,24,RenderTextureFormat.ARGB32);
            renderTexture.name="__MaskClipProbeRT";renderTexture.hideFlags=HideFlags.HideAndDontSave;
            if(!renderTexture.Create()||renderTexture.depth<24||!SystemInfo.SupportsRenderTextureFormat(RenderTextureFormat.ARGB32))
            {diagnostics.Add("stencil-rendertexture-backend-unavailable");break;}
            probeCamera.targetTexture=renderTexture;
            readbackTexture=new Texture2D(probeSize,probeSize,TextureFormat.RGBA32,false,true);
            Canvas.ForceUpdateCanvases();
            var insideWorld=probeMaskRect.TransformPoint(new Vector3(insideLocal.x,insideLocal.y,0));
            var outsideWorld=probeMaskRect.TransformPoint(new Vector3(outsideLocal.x,outsideLocal.y,0));
            var insideViewport=probeCamera.WorldToViewportPoint(insideWorld);
            var outsideViewport=probeCamera.WorldToViewportPoint(outsideWorld);
            result.insideWorldPoint=new[]{insideWorld.x,insideWorld.y,insideWorld.z};
            result.outsideWorldPoint=new[]{outsideWorld.x,outsideWorld.y,outsideWorld.z};
            result.insideViewportPoint=new[]{insideViewport.x,insideViewport.y,insideViewport.z};
            result.outsideViewportPoint=new[]{outsideViewport.x,outsideViewport.y,outsideViewport.z};
            var ix=Mathf.FloorToInt(insideViewport.x*probeSize);var iy=Mathf.FloorToInt(insideViewport.y*probeSize);
            var ox=Mathf.FloorToInt(outsideViewport.x*probeSize);var oy=Mathf.FloorToInt(outsideViewport.y*probeSize);
            result.insidePixel=new[]{ix,iy};result.outsidePixel=new[]{ox,oy};
            if(ix<0||iy<0||ix>=probeSize||iy>=probeSize||ox<0||oy<0||
                ox>=probeSize||oy>=probeSize||insideViewport.z<=0||outsideViewport.z<=0)
            {diagnostics.Add("inside-or-outside-sample-point-falls-outside-camera");break;}

            // A same-scene, same-camera, same-Canvas and same-RenderTexture
            // unmasked control distinguishes a broken preview render context
            // from a real stencil result. It must visibly draw the owned white
            // child before the masked pass is interpreted.
            maskGraphic.enabled=false;probeMask.enabled=false;Canvas.ForceUpdateCanvases();
            result.controlContextSha256=MaskClipRenderContextSha256(probeScene,probeCamera,probeCanvas,renderTexture);
            probeCamera.Render();result.unmaskedControlRenderCompleted=true;
            RenderTexture.active=renderTexture;
            readbackTexture.ReadPixels(new Rect(0,0,probeSize,probeSize),0,0,false);
            readbackTexture.Apply(false,false);
            var controlInside=(Color32)readbackTexture.GetPixel(ix,iy);
            var controlOutside=(Color32)readbackTexture.GetPixel(ox,oy);
            result.unmaskedControlInsideRgba=MaskClipPixel(controlInside);
            result.unmaskedControlOutsideRgba=MaskClipPixel(controlOutside);
            var controlSamples=new List<MaskClipControlAlphaSample>();var controlAlphaOk=true;
            foreach(var sample in result.sourceAlphaSamples??Array.Empty<MaskClipAlphaSample>())
            {
                var local=new Vector2(sample.localPoint[0],sample.localPoint[1]);
                var world=probeMaskRect.TransformPoint(new Vector3(local.x,local.y,0));
                var viewport=probeCamera.WorldToViewportPoint(world);
                var sx=Mathf.FloorToInt(viewport.x*probeSize);var sy=Mathf.FloorToInt(viewport.y*probeSize);
                if(sx<0||sy<0||sx>=probeSize||sy>=probeSize||viewport.z<=0)
                {controlAlphaOk=false;controlSamples.Add(new MaskClipControlAlphaSample{kind=sample.kind,rgba=Array.Empty<int>()});continue;}
                var color=(Color32)readbackTexture.GetPixel(sx,sy);var rgba=MaskClipPixel(color);
                controlSamples.Add(new MaskClipControlAlphaSample{kind=sample.kind,pixel=new[]{sx,sy},
                    viewportPoint=new[]{viewport.x,viewport.y,viewport.z},rgba=rgba});
                controlAlphaOk&=MaskClipExpectedOpaqueWhite(color);
            }
            result.unmaskedControlAlphaSamples=controlSamples.ToArray();
            result.unmaskedControlVerified=MaskClipExpectedOpaqueWhite(controlInside)&&MaskClipExpectedOpaqueWhite(controlOutside)&&controlAlphaOk;
            if(!result.unmaskedControlVerified)
            {diagnostics.Add("unmasked-control-white-stimulus-not-visible");break;}
            controlPngBytes=readbackTexture.EncodeToPNG();result.controlImageSha256=MaskClipHash(controlPngBytes);
            maskGraphic.enabled=spec.enabled;probeMask.enabled=spec.enabled;Canvas.ForceUpdateCanvases();
            result.maskedContextSha256=MaskClipRenderContextSha256(probeScene,probeCamera,probeCanvas,renderTexture);
            result.unmaskedControlSameRenderContext=!String.IsNullOrEmpty(result.controlContextSha256)&&
                result.controlContextSha256==result.maskedContextSha256;
            if(!result.unmaskedControlSameRenderContext)
            {diagnostics.Add("unmasked-control-and-masked-render-context-differ");break;}
            probeCamera.Render();result.renderCompleted=true;
            RenderTexture.active=renderTexture;
            readbackTexture.ReadPixels(new Rect(0,0,probeSize,probeSize),0,0,false);
            readbackTexture.Apply(false,false);
            var insidePixel=readbackTexture.GetPixel(ix,iy);var outsidePixel=readbackTexture.GetPixel(ox,oy);
            var inside32=(Color32)insidePixel;var outside32=(Color32)outsidePixel;
            result.insideRgba=MaskClipPixel(inside32);result.outsideRgba=MaskClipPixel(outside32);
            result.imageWidth=probeSize;result.imageHeight=probeSize;
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
            result.alphaSamplesVerified=imageInput==null;
            if(imageInput!=null)
            {
                var alphaSamples=result.sourceAlphaSamples??Array.Empty<MaskClipAlphaSample>();
                var alphaPass=true;
                foreach(var sample in alphaSamples)
                {
                    var local=new Vector2(sample.localPoint[0],sample.localPoint[1]);
                    var world=probeMaskRect.TransformPoint(new Vector3(local.x,local.y,0));
                    var viewport=probeCamera.WorldToViewportPoint(world);
                    sample.viewportPoint=new[]{viewport.x,viewport.y,viewport.z};
                    var sx=Mathf.FloorToInt(viewport.x*probeSize);var sy=Mathf.FloorToInt(viewport.y*probeSize);
                    if(sx<0||sy<0||sx>=probeSize||sy>=probeSize||viewport.z<=0)
                    {sample.pixelVerified=false;alphaPass=false;continue;}
                    sample.pixel=new[]{sx,sy};
                    var pixel=(Color32)readbackTexture.GetPixel(sx,sy);sample.rgba=MaskClipPixel(pixel);
                    var expectedVisible=!spec.enabled||sample.sourceAlphaPass;
                    sample.expectedVisible=expectedVisible;
                    sample.pixelVerified=expectedVisible?MaskClipExpectedOpaqueWhite(pixel):MaskClipExpectedClear(pixel);
                    alphaPass&=sample.pixelVerified;
                }
                result.alphaSamplesVerified=alphaSamples.Length>=2&&alphaPass;
                if(!result.alphaSamplesVerified)diagnostics.Add("source-alpha-threshold-samples-do-not-match-native-stencil-output");
            }
            result.stencilClipVerified=spec.enabled&&result.insidePixelVerified&&result.outsidePixelVerified&&result.alphaSamplesVerified;
            result.disabledNoClipVerified=!spec.enabled&&result.insidePixelVerified&&result.outsidePixelVerified&&result.alphaSamplesVerified;
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
            if(stimulusSprite!=null)UnityEngine.Object.DestroyImmediate(stimulusSprite);
            if(stimulusTexture!=null)UnityEngine.Object.DestroyImmediate(stimulusTexture);
            if(imageInput!=null&&imageInput.decodedSourceTexture!=null)UnityEngine.Object.DestroyImmediate(imageInput.decodedSourceTexture);
            if(result.probeSceneCreated&&probeScene.IsValid())EditorSceneManager.ClosePreviewScene(probeScene);
            result.probeSceneClosed=result.probeSceneCreated&&!probeScene.IsValid();
            result.probeObjectsDestroyed=host==null&&cameraObject==null&&renderTexture==null&&readbackTexture==null&&childObject==null;
            result.stimulusObjectsDestroyed=stimulusSprite==null&&stimulusTexture==null&&
                (imageInput==null||imageInput.decodedSourceTexture==null);
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
        var pngName="maskclip-"+token+".png";var controlPngName="maskclip-"+token+"-control.png";
        var jsonName="maskclip-"+token+".json";
        try
        {
            Directory.CreateDirectory(outputRoot);
            if(controlPngBytes!=null)
            {
                File.WriteAllBytes(Path.Combine(outputRoot,controlPngName),controlPngBytes);
                result.controlImagePath="Analysis/Readback/MaskClipping/"+controlPngName;
            }
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
            result.probeObjectsDestroyed&&result.stimulusSpriteVerified&&result.stimulusObjectsDestroyed&&
            result.graphicsBackendAvailable&&result.probeCameraSceneBound&&result.unmaskedControlRenderCompleted&&
            result.unmaskedControlVerified&&result.unmaskedControlSameRenderContext&&
            result.renderCompleted&&result.pixelReadbackVerified&&
            result.insidePixelVerified&&result.outsidePixelVerified&&result.maskInsidePointAccepted&&
            (spec.enabled?result.maskOutsidePointRejected:!result.maskOutsidePointRejected)&&result.childGraphicInsideAccepted&&
            (spec.enabled?result.childGraphicOutsideRejected:result.disabledChildGraphicOutsideAccepted)&&
            (imageInput==null||(result.sourceTextureAlphaVerified&&result.sourceMaskMaterialVerified&&result.alphaSamplesVerified))&&
            (spec.enabled?result.stencilClipVerified:result.disabledNoClipVerified)&&String.IsNullOrEmpty(result.imagePath)==false;
        result.status=result.verified?(spec.enabled?"native-stencil-clipping-verified":"disabled-mask-no-clip-verified"):
            result.supported?"native-clipping-probe-gap":"unsupported-mask-clipping-semantics";
        try{File.WriteAllText(Path.Combine(MaskClipEvidenceRoot(),jsonName),JsonUtility.ToJson(result,true));}
        catch(Exception){result.verified=false;result.status="native-clipping-probe-gap";}
        return result;
    }
}
