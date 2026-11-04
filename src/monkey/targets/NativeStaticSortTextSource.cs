using System;
using TMPro;
using UnityEngine;

namespace Monkey.StaticSortQueueProxy
{
    [Serializable]
    public sealed class NativeStaticSortTextSlotEvidence
    {
        public int slot;
        public int characterReferences;
        public int visibleCharacterReferences;
        public bool textInfoMaterialMissing;
        public int textInfoVertexCount;
        public uint textInfoTriangleIndexCount;
        public int textInfoNondegenerateTriangleCount;
        public int canvasVertexCount;
        public uint canvasTriangleIndexCount;
        public int canvasNondegenerateTriangleCount;
        public string disposition;
        public string sourceAssetKind;
        public string sourceAssetGuid;
        public long sourceAssetLocalFileId;
        public string atlasGuid;
        public long atlasLocalFileId;
        public string textInfoMaterialFingerprint;
        public string sourceGraphicMaterialFingerprint;
        public string characterEvidenceSha256;
        public string characterAssetEvidenceSha256;
        public string sourceMeshSha256;
        public string evidenceSha256;
    }

    [Serializable]
    public sealed class NativeStaticSortTextSlotEnumeration
    {
        public string sourceComponentId;
        public string sourceTextSha256;
        public int slotCount;
        public bool verified;
        public string evidenceSha256;
        public NativeStaticSortTextSlotEvidence[] rows;
    }

    [Serializable]
    public sealed class NativeStaticSortTextScaleCharacter
    {
        public int characterIndex;
        public int materialSlot;
        public int vertexIndex;
        public int unicode;
        public float scale;
        public bool visible;
        public int textElementType;
        public int fontStyle;
        public bool usingAlternateTypeface;
        public string fontAssetGuid;
        public long fontAssetLocalFileId;
    }

    /// <summary>
    /// The exact TMP UV0.w equation inputs at source capture. This permits a
    /// loaded prefab's mesh to be checked against each Canvas context without
    /// weakening positions, topology, or the saved proxy-mesh hash.
    /// </summary>
    [Serializable]
    public sealed class NativeStaticSortTextScaleContext
    {
        public string sourceComponentId;
        public string sourceTextSha256;
        public int materialSlot;
        public string formula;
        public int canvasRenderMode;
        public float canvasScaleFactor;
        public bool worldCameraAssigned;
        public float ownerLossyScaleY;
        public float graphicLossyScaleY;
        public float ownerFontSize;
        public float ownerFontSizeMin;
        public float ownerFontSizeMax;
        public int ownerFontStyle;
        public bool ownerAutoSizing;
        public float charWidthAdjustmentDelta;
        public float characterHorizontalScale;
        public NativeStaticSortTextLayoutEvidence textLayoutInputs;
        public NativeStaticSortTextScaleCharacter[] characters;
        public float[] meshUv0W;
        public string operandEvidenceSha256;
        public string textLayoutEvidenceSha256;
        public string evidenceSha256;
    }

    /// <summary>Serializable TMP mesh-generation operands, excluding parent/global transforms.</summary>
    [Serializable]
    public sealed class NativeStaticSortTextLayoutEvidence
    {
        public Vector2 rectSize;
        public Vector2 pivot;
        public Vector4 margin;
        public bool textLineBoxPresent;
        public bool textLineBoxActive;
        public float textLineBoxLineHeight;
        public float textLineBoxExtraLineFraction;
        public int textLineBoxLineCount;
        public bool contentSizeFitterPresent;
        public bool contentSizeFitterActive;
        public int contentSizeFitterHorizontalFit;
        public int contentSizeFitterVerticalFit;
        public float textLineBoxNativePreferredHeight;
        public string textLineBoxAuthoredPreferredHeight;
        public bool textLineBoxHeightProvenanceVerified;
        public float fontSize, fontSizeMin, fontSizeMax;
        public bool autoSizing;
        public int fontStyle, fontWeight, alignment, wrappingMode, overflowMode;
        public int maxVisibleCharacters, maxVisibleWords, maxVisibleLines, pageToDisplay;
        public float characterSpacing, wordSpacing, lineSpacing, lineSpacingAdjustment, paragraphSpacing;
        public bool extraPadding, richText, parseControlCharacters, rightToLeft, useMaxVisibleDescender;
        public int[] fontFeatures;
    }

    /// <summary>
    /// Persistent identity for one TextMeshPro material/mesh slot used by a
    /// static sort-queue proxy. Generated TMP_SubMeshUI objects are deliberately
    /// not serialized here: TMP creates them from the persistent owner.
    /// </summary>
    [AddComponentMenu("")]
    [DisallowMultipleComponent]
    public sealed class NativeStaticSortTextSource : MonoBehaviour
    {
        public string sourceComponentId;
        public TMP_Text sourceOwner;
        public int materialSlot;
        public bool generatedSubmesh;
        public bool sourceGraphicEnabled;
        public bool sourceGraphicActiveSelf;
        public NativeStaticSortTextSlotEnumeration textSlotEnumeration;
        public NativeStaticSortTextScaleContext textScaleContext;
        public bool textInfoMaterialMissing;
        public bool textInfoCharacterSlotVerified;
        public bool textInfoCharacterMaterialVerified;
        public bool textInfoFontAssetVerified;
        public bool textInfoAtlasVerified;
        public int textInfoCharacterCount;
        public int textInfoVisibleCharacterCount;
        public string sourceTextSha256;
        public string textInfoCharacterEvidenceSha256;
        public string textInfoCharacterAssetEvidenceSha256;
        public string textInfoCharacterMaterialFingerprint;

        public TMP_FontAsset fontAsset;
        public TMP_SpriteAsset spriteAsset;
        public Material ownerFontSharedMaterial;
        public TMP_FontAsset fallbackFontAsset;
        public Material fallbackFontMaterial;
        public Material sourceMaterial;
        public Material proxyMaterial;
        public Texture sourceTexture;

        public bool tmpFallbackMaterialBaked;
        public bool persistentFallbackVariantRegistered;
        public string tmpFallbackAlgorithm;
        public int tmpFallbackAtlasIndex;
        public string ownerFontMaterialGuid;
        public long ownerFontMaterialLocalFileId;
        public string ownerFontMaterialFingerprint;
        public string ownerStyleProfile;
        public string ownerStyleSourceComponentId;
        public float ownerStyleOutlineWidth;
        public Color ownerStyleOutlineColor;
        public TMP_FontAsset ownerStyleSourceFontAsset;
        public string ownerStyleSourceFontAssetGuid;
        public long ownerStyleSourceFontAssetLocalFileId;
        public Material ownerStyleSourceFontMaterial;
        public string ownerStyleSourceFontMaterialGuid;
        public long ownerStyleSourceFontMaterialLocalFileId;
        public string ownerStyleSourceFontMaterialFingerprint;
        public string fallbackFontAssetGuid;
        public long fallbackFontAssetLocalFileId;
        public string fallbackFontMaterialGuid;
        public long fallbackFontMaterialLocalFileId;
        public string fallbackFontMaterialFingerprint;
        public string fallbackAtlasGuid;
        public long fallbackAtlasLocalFileId;
        public string transientFallbackFingerprint;
        public string bakedProxyMaterialFingerprint;
        public string bakedProxyMaterialGuid;
        public long bakedProxyMaterialLocalFileId;

        public string fontAssetGuid;
        public long fontAssetLocalFileId;
        public string spriteAssetGuid;
        public long spriteAssetLocalFileId;
        public string sourceMaterialGuid;
        public long sourceMaterialLocalFileId;
        public string sourceMaterialFingerprint;
        public string sourceShaderGuid;
        public long sourceShaderLocalFileId;
        public string sourceTextureGuid;
        public long sourceTextureLocalFileId;

        public string sourceMeshSha256;
        public Mesh sourceSlotMesh;
        public string sourceSlotMeshGuid;
        public long sourceSlotMeshLocalFileId;
        public string sourceSlotMeshSha256;
        public string proxyMeshGuid;
        public long proxyMeshLocalFileId;
        public string proxyMeshSha256;
    }

}
