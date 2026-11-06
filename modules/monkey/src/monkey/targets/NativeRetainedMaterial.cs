using UnityEngine;

// Non-rendering evidence record for a source Cocos Material outside a native
// shader profile. It is an asset-field target only; never assign it to a Graphic.
public sealed class NativeRetainedMaterial : ScriptableObject
{
    public string sourceMaterialId;
    public string sourceMaterialName;
    public string sourceMaterialDocumentSha256;
    public string sourceEffectId;
    public string sourceEffectName;
    public string sourceEffectDocumentSha256;
    public TextAsset sourceMaterialDocument;
    public TextAsset sourceEffectDocument;
    public bool retentionOnly = true;
    public bool renderingRecovered;
}
