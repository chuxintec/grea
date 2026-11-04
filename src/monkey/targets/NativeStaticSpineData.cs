using UnityEngine;

// Exact opaque source records for a static, non-rendering Spine continuation.
// ASTC pages remain byte TextAssets; no runtime decode or renderer is implied.
public sealed class NativeStaticSpineData : ScriptableObject
{
    public string sourceDataAssetId;
    public string sourceLogicalPath;
    public string sourceSpineVersion;
    public string sourceNativeSha256;
    public long sourceNativeBytes;
    public TextAsset sourceSkeletonBytes;
    public string sourceAtlasSha256;
    public long sourceAtlasBytes;
    public TextAsset sourceAtlasText;
    public string[] sourcePageIds;
    public string[] sourcePageNames;
    public string[] sourcePageSha256;
    public long[] sourcePageBytes;
    public TextAsset[] sourceAstcPageBytes;
    public bool hasSourcePremultipliedAlpha;
    public bool sourcePremultipliedAlpha;
    public string sourcePremultipliedAlphaStatus;
    public bool skeletonParsed;
    public bool atlasDecoded;
    public bool pagesDecoded;
    public bool nonRendering = true;
}
