// Editor-only native adapter for monkey-unity-system-fonts/1.
// Keep source Label fields and current target resolution evidence separate.
// Verified against NativeUnity02 com.unity.ugui 2.6.0 TMP_FontAsset.cs
// (SHA-256 b23841ceaed628a40c08c20c5ed983ad2fa4c07224364089752c6eae08e7a6f0):
// CreateFontAsset(familyName, styleName, pointSize) constructs AtlasPopulationMode.DynamicOS;
// TryAddCharacters(uint[], out uint[], bool) plus HasCharacter(int) verifies pinned scalars.
using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.TextCore;
using UnityEngine.TextCore.LowLevel;

public static class UnitySystemFonts
{
    [Serializable]
    public sealed class Spec
    {
        public string schema;
        public string status;
        public string targetOS;
        public string targetOSVersion;
        public string targetOSBuild;
        public string runtimePlatformConstraint;
        public string playerTargetEvidence;
        public bool sourceOSIdentityVerified;
        public bool visualEquivalent;
        public string irSha256;
        public string sourceManifestSha256;
        public string resolutionReceiptSha256;
        public string sourceProfile;
        public string sourceVersion;
        public string fontAssetDirectory;
        public string fontAssetPathRule;
        public string populationMode;
        public int pointSize;
        public string glyphCoverageScope;
        public string newCharacterBoundary;
        public FontSpec[] fonts;
        public string[] explicitFontLabelsReplaced;
    }

    [Serializable]
    public sealed class FontSpec
    {
        public string assetId;
        public string assetPath;
        public string familyName;
        public string styleName;
        public string role;
        public int pointSize;
        public string populationMode;
        public string generationMode;
        public string targetPostScriptName;
        public string targetVariationAxesJson;
        public string targetSystemFontFileUrl;
        public string targetSystemFontFileSha256;
        public PhysicalFace[] matchingPhysicalFaces;
        public bool fontFileCopiedOrExported;
        public string[] fallbackAssetIds;
        public GlyphSpec[] requiredGlyphs;
        public uint[] requiredUnicode;
        public string[] sourceLabelIds;
    }

    [Serializable]
    public sealed class GlyphSpec
    {
        public uint unicode;
        public string codepoint;
        public string character;
    }

    [Serializable]
    public sealed class PhysicalFace
    {
        public int faceIndex;
        public string family;
        public string subfamily;
        public string postScriptName;
        public string variationAxesCanonical;
    }

    [Serializable]
    public sealed class LabelBindingSpec
    {
        public string sourceLabelId;
        public string sourceText;
        public float pointSize;
        public string sourceFontFamily;
        public string sourceFontFamilyEvidence;
        public string sourceSerializedFontUuid;
        public bool sourceSystemFont;
        public string sourceEffectiveFontPolicy;
        public string sourceEffectiveFamily;
        public string nativeFontAssetId;
        public string nativeFontAssetPath;
        public string[] nativeFallbackAssetIds;
        public string[] nativeFallbackAssetPaths;
        public string resolvedPrimaryFamily;
        public string resolvedPrimaryStyleName;
        public ResolvedFallbackFace[] resolvedFallbackFaces;
        public string newCharacterBoundary;
    }

    [Serializable]
    public sealed class ResolvedFallbackFace
    {
        public string familyName;
        public string styleName;
    }

    [Serializable]
    public sealed class BindingSet
    {
        public string schema;
        public string status;
        public Spec systemFonts;
        public LabelBindingSpec[] labelBindings;
        public string[] diagnostics;
    }

    [Serializable]
    public sealed class Readback
    {
        public int schemaVersion = 1;
        public string status;
        public string targetOS;
        public string targetVersion;
        public string targetBuild;
        public string targetPlatform;
        public string playerTargetEvidence;
        public bool sourceOSIdentityVerified;
        public bool visualEquivalent;
        public string irSha256;
        public string sourceManifestSha256;
        public string resolutionReceiptSha256;
        public string staticSdfGenerationReceiptSha256;
        public string sourceStaticSdfGenerationReceiptSha256;
        public FontReadback[] fonts;
        public LabelReadback[] labelBindings;
        public string[] diagnostics;
    }

    [Serializable]
    public sealed class FontReadback
    {
        public string assetId;
        public string assetPath;
        public string assetGuid;
        public string role;
        public string generationMode;
        public string coreTextTargetPostScriptName;
        public string coreTextTargetVariationAxesJson;
        public string coreTextTargetFontFileSha256;
        public string[] sourceLabelIds;
        public string resolvedFamilyName;
        public string resolvedStyleName;
        public string populationMode;
        public bool fontSourcePathEmpty;
        public bool clearDynamicDataOnBuild;
        public int pointSize;
        public float sdfSpread;
        public float normalStyle;
        public float boldStyle;
        public float gradientScale;
        public float weightNormal;
        public float weightBold;
        public int atlasCount;
        public int characterCount;
        public int requiredUnicodeCount;
        public uint[] requiredUnicode;
        public string[] requiredCodepoints;
        public string[] fallbackAssetIds;
        public NativeGlyphState initialNativeGlyphState;
        public NativeGlyphState savedNativeGlyphState;
    }

    [Serializable]
    public sealed class NativeGlyphState
    {
        public string stage;
        public string assetId;
        public string assetPath;
        public string atlasPopulationMode;
        public string familyName;
        public string styleName;
        public bool tryAddCharactersCalled;
        public bool tryAddCharactersReturned;
        public uint[] tryAddCharactersMissing;
        public uint[] requiredUnicode;
        public uint[] characterTableUnicode;
        public uint[] lookupPresentUnicode;
        public uint[] missingUnicode;
        public int characterCount;
        public int glyphCount;
        public int atlasCount;
        public bool sourceFontFilePresent;
        public string sourceFontFileGuid;
        public string sourceFontFilePath;
        public bool internalDynamicOS;
        public bool clearDynamicDataOnBuild;
    }

    [Serializable]
    public sealed class SystemFontGlyphDiagnosticFile
    {
        public string schema = "monkey-unity-system-font-glyph-diagnostics/1";
        public string status = "needs_action";
        public string targetOS;
        public string targetVersion;
        public string targetBuild;
        public string stage;
        public NativeGlyphState initialFontState;
        public NativeGlyphState currentFontState;
    }

    [Serializable]
    public sealed class LabelReadback
    {
        public string sourceLabelId;
        public string sourceText;
        public string primaryAssetId;
        public string primaryAssetPath;
        public string primaryAssetGuid;
        public string sourceFontFamily;
        public string sourceFontFamilyEvidence;
        public string sourceSerializedFontUuid;
        public bool sourceSystemFont;
        public string sourceEffectiveFontPolicy;
        public string resolvedPrimaryFamily;
        public string resolvedPrimaryStyleName;
        public string newCharacterBoundary;
        public string[] fallbackAssetIds;
        public string[] fallbackAssetPaths;
    }

    // Outline material variants are created only for the isolated preview instance.
    // TMP fallback materials inherit the primary material's shader values, so a
    // spread normalized for the primary face can saturate on a wide-spread static
    // fallback face. This readback records the per-face conversion used below.
    [Serializable]
    public sealed class OutlineFaceReadback
    {
        public string fontAssetPath;
        public string materialName;
        public float pointSize;
        public float gradientScale;
        public float faceDilate;
        public float sourceWidth;
        public float normalizedOutlineWidth;
        public int[] assignedUnicode;
    }

    [Serializable]
    public sealed class OutlineReadback
    {
        public string status;
        public string sourceLabelId;
        public string textSha256;
        public float sourceOutlineWidth;
        public Color sourceOutlineColor;
        public OutlineFaceReadback[] faces;
        public string[] diagnostics;
    }

    [Serializable]
    public sealed class StaticSdfGenerationReceipt
    {
        public string schema;
        public string status;
        public string sourceGenerationReceiptSha256;
        public string targetOS;
        public string targetOSVersion;
        public string targetOSBuild;
        public string resolutionReceiptSha256;
        public string planSha256;
        public string atlasPath;
        public string atlasSha256;
        public string metricsPath;
        public string metricsSha256;
        public int glyphCount;
        public int sourceLabelCount;
        public bool fontFileCopiedOrExported;
        public bool fontFileIncluded;
    }

    [Serializable]
    public sealed class StaticSdfMetrics
    {
        public string schema;
        public string status;
        public string staticPlanSha256;
        public string targetOS;
        public string targetOSVersion;
        public string targetOSBuild;
        public string resolutionReceiptSha256;
        public string family;
        public string styleName;
        public string postScriptName;
        public string variationAxesCanonical;
        public string fontFileSha256;
        public bool fontFileCopiedOrExported;
        public bool fontFileIncluded;
        public int pointSize;
        public float sdfSpread;
        public int glyphPadding;
        public int atlasWidth;
        public int atlasHeight;
        public string atlasOrigin;
        public int requiredGlyphCount;
        public string[] sourceLabelIds;
        public string glyphScope;
        public string glyphRunShaping;
        public bool visualEquivalent;
        public string playerPlatformEvidence;
        public StaticFaceMetrics faceMetrics;
        public StaticGlyphMetrics[] glyphs;
    }

    [Serializable]
    public sealed class StaticFaceMetrics
    {
        public int unitsPerEM;
        public float ascentLine;
        public float descentLine;
        public float lineHeight;
        public float capLine;
        public float meanLine;
        public float underlinePosition;
        public float underlineThickness;
    }

    [Serializable]
    public sealed class StaticGlyphMetrics
    {
        public uint unicode;
        public string codepoint;
        public string character;
        public uint glyphIndex;
        public StaticGlyphRect rect;
        public StaticGlyphFaceMetrics metrics;
    }

    [Serializable]
    public sealed class StaticGlyphRect
    {
        public int x;
        public int y;
        public int width;
        public int height;
    }

    [Serializable]
    public sealed class StaticGlyphFaceMetrics
    {
        public float width;
        public float height;
        public float bearingX;
        public float bearingY;
        public float advance;
    }

    sealed class PendingFont
    {
        public FontSpec spec;
        public TMP_FontAsset asset;
        public NativeGlyphState initialGlyphState;
        public float sdfSpread;
    }

    sealed class StaticSdfInput
    {
        public StaticSdfMetrics metrics;
        public byte[] atlasBytes;
        public string generationReceiptSha256;
        public string sourceGenerationReceiptSha256;
    }

    const string ExpectedSchema = "monkey-unity-system-fonts/1";
    const string ExpectedFontRoot = "Assets/Game/Content/Fonts/System/";
    // TMP 2.6.0 CreateFontAsset(family, style, pointSize) uses SDFAA padding 9
    // plus a 1 px packing modifier, so its canonical GradientScale is 10.
    const float TmpDefaultSdfGradientScale = 10f;
    const float TmpSdfRatioClamp = 1f;
    const float TmpDefaultBoldStyle = 0.75f;

    /// <summary>
    /// Create, persist, reopen and verify DynamicOS TMP assets on macOS Editor.
    /// No font files are registered, copied, downloaded or exported.
    /// </summary>
    public static Readback Import(BindingSet bindingSet)
    {
        return Import(bindingSet, null, null);
    }

#if !MONKEY_STATIC_FONT_COMPLETION_ONLY
    /// <summary>
    /// Editor-side source validation and persistent NativeStaticTextOutline setup.
    /// The runtime component stores only presentation values and reapplies them on
    /// each TMP pre-render; source identity/text checks remain editor input checks.
    /// </summary>
    public static OutlineReadback ApplySourceOutline(TMP_Text label, BindingSet bindingSet,
        string sourceLabelId, float sourceOutlineWidth, Color sourceOutlineColor)
    {
        if (label == null || bindingSet == null || bindingSet.labelBindings == null
            || string.IsNullOrWhiteSpace(sourceLabelId))
            throw new InvalidOperationException("SYSTEM_FONT_OUTLINE_INPUT_MISSING");
        if (float.IsNaN(sourceOutlineWidth) || float.IsInfinity(sourceOutlineWidth) || sourceOutlineWidth < 0f)
            throw new InvalidOperationException("SYSTEM_FONT_OUTLINE_WIDTH_INVALID");
        var bindings = bindingSet.labelBindings.Where(row => row != null && row.sourceLabelId == sourceLabelId).ToArray();
        if (bindings.Length != 1)
            throw new InvalidOperationException("SYSTEM_FONT_OUTLINE_LABEL_BINDING_NOT_UNIQUE: " + sourceLabelId);
        var binding = bindings[0];
        if (!string.Equals(label.text ?? string.Empty, binding.sourceText ?? string.Empty, StringComparison.Ordinal))
            throw new InvalidOperationException("SYSTEM_FONT_OUTLINE_TEXT_BINDING_MISMATCH: " + sourceLabelId);
        if (label.font == null || AssetDatabase.GetAssetPath(label.font) != binding.nativeFontAssetPath)
            throw new InvalidOperationException("SYSTEM_FONT_OUTLINE_PRIMARY_FONT_MISMATCH: " + sourceLabelId);
        if (float.IsNaN(label.fontSize) || float.IsInfinity(label.fontSize) || label.fontSize <= 0f)
            throw new InvalidOperationException("SYSTEM_FONT_OUTLINE_LABEL_SIZE_INVALID: " + sourceLabelId);

        var component = label.GetComponent<NativeStaticTextOutline>();
        if (component == null) component = label.gameObject.AddComponent<NativeStaticTextOutline>();
        component.Configure(label, sourceOutlineWidth, sourceOutlineColor, sourceLabelId);
        EditorUtility.SetDirty(component);
        PrefabUtility.RecordPrefabInstancePropertyModifications(component);
        var serializedOutline = new SerializedObject(component);
        serializedOutline.Update();
        if (serializedOutline.FindProperty("target") == null
            || serializedOutline.FindProperty("target").objectReferenceValue != label
            || serializedOutline.FindProperty("sourceOutlineWidth") == null
            || !Mathf.Approximately(serializedOutline.FindProperty("sourceOutlineWidth").floatValue, sourceOutlineWidth)
            || serializedOutline.FindProperty("sourceOutlineColor") == null
            || serializedOutline.FindProperty("sourceOutlineColor").colorValue != sourceOutlineColor)
            throw new InvalidOperationException("SYSTEM_FONT_OUTLINE_SERIALIZED_STATE_READBACK_MISMATCH: " + sourceLabelId);
        var native = component.LastReadback;
        bool noGlyphsByEmptyText = native != null && native.status == "not_visible_empty_text"
            && native.sourceLabelId == sourceLabelId
            && string.IsNullOrEmpty(label.text);
        bool noGlyphsByInactiveState = native != null && native.status == "not_visible_inactive"
            && native.sourceLabelId == sourceLabelId
            && (!label.enabled || !label.gameObject.activeInHierarchy);
        if ((noGlyphsByEmptyText || noGlyphsByInactiveState)
            && Mathf.Approximately(native.sourceOutlineWidth, sourceOutlineWidth)
            && native.sourceOutlineColor == sourceOutlineColor)
            return new OutlineReadback {
                status = native.status,
                sourceLabelId = sourceLabelId,
                textSha256 = Sha256(Encoding.UTF8.GetBytes(label.text ?? string.Empty)),
                sourceOutlineWidth = sourceOutlineWidth,
                sourceOutlineColor = sourceOutlineColor,
                faces = Array.Empty<OutlineFaceReadback>(),
                diagnostics = native.diagnostics ?? Array.Empty<string>(),
            };
        if (native == null || native.status != "material_values_applied_and_read_back"
            || native.faces == null || native.faces.Length == 0)
            throw new InvalidOperationException("SYSTEM_FONT_OUTLINE_NATIVE_READBACK_FAILED: "
                + string.Join(",", native == null ? Array.Empty<string>() : native.diagnostics ?? Array.Empty<string>()));

        var allowedPaths = new List<string> { binding.nativeFontAssetPath };
        allowedPaths.AddRange(binding.nativeFallbackAssetPaths ?? Array.Empty<string>());
        var faces = new List<OutlineFaceReadback>();
        foreach (var row in native.faces)
        {
            if (row == null || row.fontAsset == null || !row.materialValuesVerified)
                throw new InvalidOperationException("SYSTEM_FONT_OUTLINE_FACE_READBACK_INCOMPLETE: " + sourceLabelId);
            string path = AssetDatabase.GetAssetPath(row.fontAsset);
            if (!allowedPaths.Contains(path, StringComparer.Ordinal))
                throw new InvalidOperationException("SYSTEM_FONT_OUTLINE_UNBOUND_RENDER_FONT: " + path);
            foreach (int unicode in row.assignedUnicode ?? Array.Empty<int>())
            {
                // TMP's textInfo reports the face it actually selected after
                // applying its style/typeface and fallback search rules. The
                // first allowed asset whose lookup contains a codepoint is not
                // necessarily that face (for example, duplicate glyph coverage
                // or an alternative typeface can route the rendered character
                // to a later declared fallback). Verify the reported face is in
                // the exact declared chain above and that it owns this glyph.
                if (!row.fontAsset.HasCharacter(unicode))
                    throw new InvalidOperationException("SYSTEM_FONT_OUTLINE_GLYPH_FONT_ASSIGNMENT_MISMATCH: U+"
                        + unicode.ToString("X4") + " actual=" + path + " actualOwnsGlyph=false");
            }
            faces.Add(new OutlineFaceReadback {
                fontAssetPath = path,
                materialName = row.materialName,
                pointSize = row.pointSize,
                gradientScale = row.gradientScale,
                faceDilate = row.faceDilate,
                sourceWidth = row.sourceOutlineWidth,
                normalizedOutlineWidth = row.normalizedOutlineWidth,
                assignedUnicode = row.assignedUnicode ?? Array.Empty<int>(),
            });
        }
        return new OutlineReadback {
            status = native.status,
            sourceLabelId = sourceLabelId,
            textSha256 = Sha256(Encoding.UTF8.GetBytes(label.text ?? string.Empty)),
            sourceOutlineWidth = native.sourceOutlineWidth,
            sourceOutlineColor = native.sourceOutlineColor,
            faces = faces.ToArray(),
            diagnostics = new[] { "Serialized NativeStaticTextOutline state was applied and its current material values were read back; save/reopen persistence and visual equivalence require separate validation." },
        };
    }

#endif

    /// <summary>
    /// Create and save the evidence-split DynamicOS + bounded Static SDF assets.
    /// Static inputs are hash-pinned artifacts generated from the exact CoreText receipt.
    /// </summary>
    public static Readback Import(BindingSet bindingSet, string staticSdfGenerationReceiptPath,
                                  string expectedStaticSdfGenerationReceiptSha256)
    {
        ValidateSpec(bindingSet);
        var staticInputs = LoadAndValidateStaticSdfInputs(bindingSet, staticSdfGenerationReceiptPath,
                                                          expectedStaticSdfGenerationReceiptSha256);
        if (Application.platform != RuntimePlatform.OSXEditor)
            throw new InvalidOperationException("SYSTEM_FONT_TARGET_OS_MISMATCH: DynamicOS receipt is macOS-only; run this importer in macOS Editor.");

        var spec = bindingSet.systemFonts;
        string currentOSVersion = ReadMacOSVersion("-productVersion");
        string currentOSBuild = ReadMacOSVersion("-buildVersion");
        if (!string.Equals(currentOSVersion, spec.targetOSVersion, StringComparison.Ordinal)
            || (!string.IsNullOrEmpty(spec.targetOSBuild) && !string.Equals(currentOSBuild, spec.targetOSBuild, StringComparison.Ordinal)))
            throw new InvalidOperationException("SYSTEM_FONT_TARGET_OS_VERSION_MISMATCH: rerun CoreText resolution on the current macOS build.");
        ValidateInstalledFontFiles(spec.fonts);
        var byId = spec.fonts.ToDictionary(f => f.assetId, StringComparer.Ordinal);
        ValidateReferences(bindingSet, byId);
        foreach (var font in spec.fonts)
        {
            if (AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(font.assetPath) != null || File.Exists(font.assetPath))
                throw new InvalidOperationException("SYSTEM_FONT_ASSET_PATH_EXISTS: refusing to overwrite " + font.assetPath);
        }

        var pending = new Dictionary<string, PendingFont>(StringComparer.Ordinal);
        foreach (var fontSpec in spec.fonts.OrderBy(f => f.role == "fallback" ? 0 : 1).ThenBy(f => f.assetId, StringComparer.Ordinal))
        {
            var font = fontSpec.populationMode == "StaticSDFRequired"
                ? CreateStaticSdfFontAsset(fontSpec, staticInputs)
                : TMP_FontAsset.CreateFontAsset(fontSpec.familyName, fontSpec.styleName, fontSpec.pointSize);
            if (font == null) {
                RecordAvailableFaces();
                throw new InvalidOperationException("SYSTEM_FONT_FAMILY_STYLE_UNAVAILABLE: " + fontSpec.familyName + " / " + fontSpec.styleName);
            }
            PreserveGeneratedDynamicGlyphData(font, fontSpec);
            VerifyFace(font, fontSpec);
            var glyphState = InspectRequiredGlyphs(font, fontSpec, "before-save-populate", true);
            if (glyphState.missingUnicode.Length > 0
                || (glyphState.tryAddCharactersCalled && !glyphState.tryAddCharactersReturned))
            {
                WriteGlyphDiagnostic(glyphState, glyphState);
                throw new InvalidOperationException("SYSTEM_FONT_GLYPHS_UNAVAILABLE: " + fontSpec.assetId + " "
                    + fontSpec.familyName + " / " + fontSpec.styleName + " missing "
                    + string.Join(",", glyphState.missingUnicode.Select(value => "U+" + value.ToString("X4")))
                    + "; TryAddCharacters=" + glyphState.tryAddCharactersReturned);
            }
            VerifyRuntimeResources(font, fontSpec);
            pending.Add(fontSpec.assetId, new PendingFont {
                spec = fontSpec, asset = font, initialGlyphState = glyphState,
                sdfSpread = fontSpec.populationMode == "StaticSDFRequired" && staticInputs != null
                    ? staticInputs.metrics.sdfSpread : 0f
            });
        }

        foreach (var item in pending.Values)
        {
            var fallbackIds = item.spec.fallbackAssetIds ?? Array.Empty<string>();
            item.asset.fallbackFontAssetTable = fallbackIds.Select(id => pending[id].asset).ToList();
            EditorUtility.SetDirty(item.asset);
        }

        var createdPaths = new List<string>();
        try
        {
            foreach (var item in pending.Values.OrderBy(p => p.spec.role == "fallback" ? 0 : 1)
                         .ThenBy(p => p.spec.assetPath, StringComparer.Ordinal))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(item.spec.assetPath));
                AssetDatabase.CreateAsset(item.asset, item.spec.assetPath);
                createdPaths.Add(item.spec.assetPath);
                PersistFontSubassets(item.asset);
                EditorUtility.SetDirty(item.asset);
            }
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            return BuildReadback(bindingSet, pending,
                staticInputs == null ? null : staticInputs.generationReceiptSha256,
                staticInputs == null ? null : staticInputs.sourceGenerationReceiptSha256);
        }
        catch
        {
            foreach (var path in createdPaths.AsEnumerable().Reverse())
                AssetDatabase.DeleteAsset(path);
            AssetDatabase.SaveAssets();
            throw;
        }
    }

    [Serializable]
    public sealed class StaticSdfUpgradeReadback
    {
        public string assetId, assetPath, status;
        public int atlasWidth, atlasHeight, characterCount, glyphCount;
        public uint[] requiredUnicode;
        public bool tryAddCharactersCalled;
    }

    /// <summary>
    /// Upgrade one already-frozen static fallback in a disposable derived candidate.
    /// The caller owns project/hash guards and save/reopen verification. Native object
    /// identities are retained; DynamicOS primaries are never populated or rewritten.
    /// </summary>
    public static StaticSdfUpgradeReadback UpgradeStaticSdfAsset(BindingSet bindingSet, string assetId,
        string generationReceiptPath, string expectedGenerationReceiptSha256, TMP_FontAsset targetFont)
    {
        ValidateSpec(bindingSet);
        var input = LoadAndValidateStaticSdfInputs(bindingSet, generationReceiptPath, expectedGenerationReceiptSha256);
        var spec = bindingSet.systemFonts.fonts.Single(f => f.assetId == assetId);
        if (targetFont == null || spec.populationMode != "StaticSDFRequired" ||
            targetFont.atlasPopulationMode != AtlasPopulationMode.Static ||
            AssetDatabase.GetAssetPath(targetFont) != spec.assetPath)
            throw new InvalidOperationException("STATIC_FONT_UPGRADE_TARGET_IDENTITY_MISMATCH");
        VerifyFace(targetFont, spec);
        var oldAtlas = targetFont.atlasTextures;
        var oldMaterial = targetFont.material;
        if (oldAtlas == null || oldAtlas.Length != 1 || oldAtlas[0] == null || oldMaterial == null ||
            AssetDatabase.GetAssetPath(oldAtlas[0]) != spec.assetPath ||
            AssetDatabase.GetAssetPath(oldMaterial) != spec.assetPath)
            throw new InvalidOperationException("STATIC_FONT_UPGRADE_REQUIRES_OWNED_SUBASSETS");
        var fresh = CreateStaticSdfFontAsset(spec, input);
        var temporaryAtlas = fresh.atlasTextures[0];
        var temporaryMaterial = fresh.material;
        try
        {
            fresh.ReadFontAssetDefinition();
            foreach (var old in targetFont.characterTable)
            {
                if (!fresh.characterLookupTable.TryGetValue(old.unicode, out var next) ||
                    old.glyphIndex != next.glyphIndex || !old.glyph.glyphRect.Equals(next.glyph.glyphRect) ||
                    !old.glyph.metrics.Equals(next.glyph.metrics) || old.scale != next.scale)
                    throw new InvalidOperationException("STATIC_FONT_UPGRADE_OLD_GLYPH_CHANGED: " + old.unicode);
            }
            // Existing normalized UVs remain valid only with the same atlas dimensions.
            if (oldAtlas[0].width != temporaryAtlas.width || oldAtlas[0].height != temporaryAtlas.height)
                throw new InvalidOperationException("STATIC_FONT_UPGRADE_ATLAS_RESIZE_REQUIRES_MESH_RECAPTURE");
            var oldPixels = oldAtlas[0].GetPixels32();
            var newPixels = temporaryAtlas.GetPixels32();
            foreach (var glyph in targetFont.glyphTable)
            {
                var rect = glyph.glyphRect;
                for (var y = rect.y; y < rect.y + rect.height; y++)
                for (var x = rect.x; x < rect.x + rect.width; x++)
                    if (!oldPixels[y * oldAtlas[0].width + x].Equals(newPixels[y * temporaryAtlas.width + x]))
                        throw new InvalidOperationException("STATIC_FONT_UPGRADE_OLD_GLYPH_PIXELS_CHANGED: " + glyph.index);
            }
            if (!ImageConversion.LoadImage(oldAtlas[0], input.atlasBytes, false))
                throw new InvalidOperationException("STATIC_FONT_UPGRADE_ATLAS_DECODE_FAILED");
            EditorUtility.CopySerialized(temporaryMaterial, oldMaterial);
            oldMaterial.mainTexture = oldAtlas[0];
            fresh.atlasTextures = oldAtlas;
            fresh.material = oldMaterial;
            var fallbackTable = targetFont.fallbackFontAssetTable;
            EditorUtility.CopySerialized(fresh, targetFont);
            targetFont.fallbackFontAssetTable = fallbackTable;
            // CopySerialized carries glyph indices, not TMP's nonserialized
            // character.glyph links. Rejoin against the new serialized table.
            var glyphsByIndex = targetFont.glyphTable.ToDictionary(g => g.index);
            var characters = targetFont.characterTable.Select(c =>
                new TMP_Character(c.unicode, targetFont, glyphsByIndex[c.glyphIndex]) { scale = c.scale }).ToList();
            targetFont.characterTable.Clear(); targetFont.characterTable.AddRange(characters);
            targetFont.ReadFontAssetDefinition();
            foreach (var scalar in spec.requiredUnicode)
                if (!targetFont.characterLookupTable.ContainsKey(scalar))
                    throw new InvalidOperationException("STATIC_FONT_UPGRADE_LOOKUP_MISSING: " + scalar);
            EditorUtility.SetDirty(oldAtlas[0]); EditorUtility.SetDirty(oldMaterial); EditorUtility.SetDirty(targetFont);
            return new StaticSdfUpgradeReadback { assetId = assetId, assetPath = spec.assetPath,
                status = "updated_pending_save_reopen", atlasWidth = oldAtlas[0].width, atlasHeight = oldAtlas[0].height,
                requiredUnicode = spec.requiredUnicode, characterCount = targetFont.characterTable.Count,
                glyphCount = targetFont.glyphTable.Count, tryAddCharactersCalled = false };
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(temporaryMaterial);
            UnityEngine.Object.DestroyImmediate(temporaryAtlas);
            UnityEngine.Object.DestroyImmediate(fresh);
        }
    }

    static StaticSdfInput LoadAndValidateStaticSdfInputs(BindingSet bindingSet, string receiptPath, string expectedReceiptSha)
    {
        var staticSpecs = bindingSet.systemFonts.fonts.Where(font => font.populationMode == "StaticSDFRequired").ToArray();
        if (staticSpecs.Length == 0)
        {
            if (!string.IsNullOrEmpty(receiptPath) || !string.IsNullOrEmpty(expectedReceiptSha))
                throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_RECEIPT_UNEXPECTED: spec has no static SDF faces");
            return null;
        }
        if (staticSpecs.Length != 1 || string.IsNullOrEmpty(receiptPath) || !IsSha256(expectedReceiptSha))
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_ARTIFACTS_REQUIRED: pass one hash-pinned CoreText SDF generation receipt");
        byte[] receiptBytes = File.ReadAllBytes(receiptPath);
        string receiptSha = Sha256(receiptBytes);
        if (!string.Equals(receiptSha, expectedReceiptSha, StringComparison.Ordinal))
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_RECEIPT_HASH_MISMATCH");
        var receipt = JsonUtility.FromJson<StaticSdfGenerationReceipt>(Encoding.UTF8.GetString(receiptBytes));
        var spec = bindingSet.systemFonts;
        bool portableReceipt = receipt != null && receipt.schema == "monkey-coretext-static-sdf-portable-generation-receipt/1";
        bool originalReceipt = receipt != null && receipt.schema == "monkey-coretext-static-sdf-generation-receipt/1";
        if (receipt == null || (!portableReceipt && !originalReceipt)
            || (portableReceipt ? receipt.status != "portable_staged" : receipt.status != "generated")
            || receipt.targetOS != "macOS" || receipt.targetOSVersion != spec.targetOSVersion
            || (!string.IsNullOrEmpty(spec.targetOSBuild) && receipt.targetOSBuild != spec.targetOSBuild)
            || receipt.resolutionReceiptSha256 != spec.resolutionReceiptSha256
            || receipt.fontFileCopiedOrExported || receipt.fontFileIncluded)
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_RECEIPT_MISMATCH: target or source evidence drifted");
        if (portableReceipt && !IsSha256(receipt.sourceGenerationReceiptSha256))
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_SOURCE_RECEIPT_PROVENANCE_MISSING");
        if (!IsSha256(receipt.atlasSha256) || !IsSha256(receipt.metricsSha256))
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_HASH_INVALID");
        string atlasPath = ResolveStaticInputPath(receiptPath, receipt.atlasPath, "glyph-atlas.png", portableReceipt);
        string metricsPath = ResolveStaticInputPath(receiptPath, receipt.metricsPath, "glyph-metrics.json", portableReceipt);
        byte[] atlasBytes = File.ReadAllBytes(atlasPath);
        byte[] metricsBytes = File.ReadAllBytes(metricsPath);
        if (Sha256(atlasBytes) != receipt.atlasSha256 || Sha256(metricsBytes) != receipt.metricsSha256)
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_ARTIFACT_HASH_MISMATCH");
        var metrics = JsonUtility.FromJson<StaticSdfMetrics>(Encoding.UTF8.GetString(metricsBytes));
        var font = staticSpecs[0];
        if (metrics == null || metrics.schema != "monkey-coretext-static-sdf-glyph-metrics/1" || metrics.status != "generated"
            || metrics.staticPlanSha256 != receipt.planSha256 || !IsSha256(metrics.staticPlanSha256)
            || metrics.targetOS != receipt.targetOS || metrics.targetOSVersion != receipt.targetOSVersion
            || metrics.targetOSBuild != receipt.targetOSBuild || metrics.resolutionReceiptSha256 != spec.resolutionReceiptSha256
            || metrics.family != font.familyName || metrics.styleName != font.styleName
            || metrics.postScriptName != font.targetPostScriptName
            || metrics.variationAxesCanonical != font.targetVariationAxesJson
            || metrics.fontFileSha256 != font.targetSystemFontFileSha256
            || metrics.fontFileCopiedOrExported || metrics.fontFileIncluded || metrics.visualEquivalent
            || metrics.playerPlatformEvidence != "not_run" || metrics.atlasOrigin != "top-left"
            || metrics.pointSize != font.pointSize || metrics.atlasWidth <= 0 || metrics.atlasHeight <= 0
            || metrics.atlasWidth > 4096 || metrics.atlasHeight > 4096 || metrics.glyphPadding <= 0
            || metrics.sdfSpread < metrics.glyphPadding || metrics.glyphs == null || metrics.faceMetrics == null
            || receipt.glyphCount != metrics.requiredGlyphCount || metrics.requiredGlyphCount != metrics.glyphs.Length)
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_METRICS_MISMATCH: face, scope or dimensions drifted");
        var required = (font.requiredUnicode ?? Array.Empty<uint>()).Distinct().OrderBy(value => value).ToArray();
        var included = metrics.glyphs.Select(glyph => glyph.unicode).OrderBy(value => value).ToArray();
        var sourceGlyphs = (font.requiredGlyphs ?? Array.Empty<GlyphSpec>()).ToDictionary(glyph => glyph.unicode);
        if (!required.SequenceEqual(included) || included.Distinct().Count() != included.Length
            || metrics.glyphs.Any(glyph => glyph.rect == null || glyph.metrics == null || glyph.glyphIndex == 0
                                          || !sourceGlyphs.TryGetValue(glyph.unicode, out var sourceGlyph)
                                          || sourceGlyph.codepoint != glyph.codepoint || sourceGlyph.character != glyph.character
                                          || glyph.rect.x < 0 || glyph.rect.y < 0 || glyph.rect.width <= 0 || glyph.rect.height <= 0
                                          || glyph.rect.width <= 2 * metrics.glyphPadding || glyph.rect.height <= 2 * metrics.glyphPadding
                                          || glyph.rect.x + glyph.rect.width > metrics.atlasWidth
                                          || glyph.rect.y + glyph.rect.height > metrics.atlasHeight))
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_GLYPH_SET_MISMATCH: only exact receipt glyphs may be imported");
        if (string.IsNullOrEmpty(font.targetSystemFontFileUrl) || !Path.IsPathRooted(font.targetSystemFontFileUrl)
            || !File.Exists(font.targetSystemFontFileUrl)
            || Sha256(File.ReadAllBytes(font.targetSystemFontFileUrl)) != font.targetSystemFontFileSha256)
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_TARGET_FONT_FILE_DRIFTED: installed system face evidence changed");
        var expectedLabels = (font.sourceLabelIds ?? Array.Empty<string>()).OrderBy(value => value, StringComparer.Ordinal).ToArray();
        var suppliedLabels = (metrics.sourceLabelIds ?? Array.Empty<string>()).OrderBy(value => value, StringComparer.Ordinal).ToArray();
        if (receipt.sourceLabelCount != expectedLabels.Length || !expectedLabels.SequenceEqual(suppliedLabels, StringComparer.Ordinal))
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_SOURCE_LABEL_SET_MISMATCH");
        return new StaticSdfInput { metrics = metrics, atlasBytes = atlasBytes,
            generationReceiptSha256 = receiptSha,
            sourceGenerationReceiptSha256 = portableReceipt ? receipt.sourceGenerationReceiptSha256 : null };
    }

    static string ResolveStaticInputPath(string receiptPath, string inputPath, string expectedFileName, bool portableReceipt)
    {
        if (!portableReceipt)
        {
            if (string.IsNullOrEmpty(inputPath) || !Path.IsPathRooted(inputPath))
                throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_PATH_OR_HASH_INVALID");
            return inputPath;
        }
        if (inputPath != expectedFileName || Path.IsPathRooted(inputPath)
            || inputPath.IndexOf('\\') >= 0 || inputPath.Split('/').Any(part => part == ".." || part == "." || part.Length == 0))
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_RELATIVE_PATH_INVALID: only adjacent fixed filenames are allowed");
        string receiptDirectory = Path.GetDirectoryName(Path.GetFullPath(receiptPath));
        if (string.IsNullOrEmpty(receiptDirectory) || HasReparsePointInAncestors(receiptDirectory))
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_RECEIPT_DIRECTORY_UNSAFE");
        string candidate = Path.GetFullPath(Path.Combine(receiptDirectory, inputPath));
        string prefix = receiptDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
        if (!candidate.StartsWith(prefix, StringComparison.Ordinal) || !File.Exists(candidate)
            || (File.GetAttributes(candidate) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_RELATIVE_PATH_ESCAPES_RECEIPT_DIRECTORY");
        return candidate;
    }

    static bool HasReparsePointInAncestors(string path)
    {
        var current = new DirectoryInfo(path);
        while (current != null)
        {
            if ((current.Attributes & FileAttributes.ReparsePoint) != 0)
                return true;
            current = current.Parent;
        }
        return false;
    }

    static TMP_FontAsset CreateStaticSdfFontAsset(FontSpec spec, StaticSdfInput input)
    {
        if (input == null || spec.populationMode != "StaticSDFRequired")
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_INPUT_MISSING: " + spec.assetId);
        var metrics = input.metrics;
        var asset = ScriptableObject.CreateInstance<TMP_FontAsset>();
        asset.name = spec.assetId;
        asset.atlasPopulationMode = AtlasPopulationMode.Static;
        asset.isMultiAtlasTexturesEnabled = false;
        // TMP_Text applies synthetic bold as style * 0.25 * GradientScale *
        // ScaleRatioA. With no outline, UpdateShaderRatios makes ScaleRatioA
        // (GradientScale - 1) / GradientScale. Keep the actual dilation equal
        // to TMP's normal G=10 SDF when our atlas uses a wider distance range.
        asset.normalStyle = ScaleTmpStyleWeight(asset.normalStyle, metrics.sdfSpread);
        asset.boldStyle = ScaleTmpStyleWeight(asset.boldStyle, metrics.sdfSpread);
        var face = asset.faceInfo;
        face.familyName = metrics.family;
        face.styleName = metrics.styleName;
        face.pointSize = metrics.pointSize;
        face.scale = 1f;
        face.ascentLine = metrics.faceMetrics.ascentLine;
        face.descentLine = metrics.faceMetrics.descentLine;
        face.lineHeight = metrics.faceMetrics.lineHeight;
        face.capLine = metrics.faceMetrics.capLine;
        face.meanLine = metrics.faceMetrics.meanLine;
        face.baseline = 0f;
        face.underlineOffset = metrics.faceMetrics.underlinePosition;
        face.underlineThickness = metrics.faceMetrics.underlineThickness;
        face.strikethroughOffset = metrics.faceMetrics.capLine * 0.5f;
        face.strikethroughThickness = metrics.faceMetrics.underlineThickness;
        face.tabWidth = metrics.pointSize * 0.5f;
        asset.faceInfo = face;

        var atlas = new Texture2D(2, 2, TextureFormat.RGBA32, false, true);
        if (!ImageConversion.LoadImage(atlas, input.atlasBytes, false))
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_ATLAS_DECODE_FAILED");
        if (atlas.width != metrics.atlasWidth || atlas.height != metrics.atlasHeight)
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_ATLAS_DIMENSION_MISMATCH");
        atlas.name = spec.assetId + " Atlas";
        atlas.filterMode = FilterMode.Bilinear;
        atlas.wrapMode = TextureWrapMode.Clamp;
        atlas.anisoLevel = 1;
        asset.atlasTextures = new[] { atlas };
        var shader = Shader.Find("TextMeshPro/Mobile/Distance Field");
        if (shader == null)
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_SHADER_UNAVAILABLE");
        var material = new Material(shader);
        material.name = spec.assetId + " Material";
        material.SetTexture("_MainTex", atlas);
        material.SetFloat("_TextureWidth", metrics.atlasWidth);
        material.SetFloat("_TextureHeight", metrics.atlasHeight);
        // CoreText encodes [-spread,+spread] into [0,1]; TMP needs that full range.
        material.SetFloat("_GradientScale", 2f * metrics.sdfSpread + 1f);
        material.SetFloat("_WeightNormal", asset.normalStyle);
        material.SetFloat("_WeightBold", asset.boldStyle);
        if (!Mathf.Approximately(material.GetFloat("_GradientScale"), 2f * metrics.sdfSpread + 1f)
            || !Mathf.Approximately(material.GetFloat("_WeightNormal"), asset.normalStyle)
            || !Mathf.Approximately(material.GetFloat("_WeightBold"), asset.boldStyle))
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_STYLE_MATERIAL_MISMATCH: " + spec.assetId);
        asset.material = material;

        // The lookup-table getters call ReadFontAssetDefinition, which expects
        // a non-null material. Fill the serialized tables directly first, then
        // initialize TMP's dictionaries once the face, atlas and material exist.
        asset.glyphTable.Clear();
        asset.characterTable.Clear();
        foreach (var row in metrics.glyphs.OrderBy(glyph => glyph.unicode))
        {
            int atlasY = metrics.atlasHeight - row.rect.y - row.rect.height;
            int pad = metrics.glyphPadding;
            // CoreText rects cover the raster plus SDF padding. TMP glyph metrics
            // describe the visible outline and its bearings, so keep the GlyphRect
            // aligned to that content; TMP adds only material-derived UV padding.
            var glyphRect = new GlyphRect(row.rect.x + pad, atlasY + pad,
                                          row.rect.width - 2 * pad, row.rect.height - 2 * pad);
            var glyphMetrics = new GlyphMetrics(row.metrics.width, row.metrics.height,
                                                row.metrics.bearingX, row.metrics.bearingY,
                                                row.metrics.advance);
            var glyph = new Glyph(row.glyphIndex, glyphMetrics, glyphRect, 1f, 0);
            asset.glyphTable.Add(glyph);
            asset.characterTable.Add(new TMP_Character(row.unicode, asset, glyph));
        }
        var serialized = new SerializedObject(asset);
        SetIntProperty(serialized, "m_AtlasWidth", metrics.atlasWidth);
        SetIntProperty(serialized, "m_AtlasHeight", metrics.atlasHeight);
        SetIntProperty(serialized, "m_AtlasPadding", metrics.glyphPadding);
        SetIntProperty(serialized, "m_AtlasRenderMode", (int)GlyphRenderMode.SDFAA);
        SetBoolProperty(serialized, "m_ClearDynamicDataOnBuild", false);
        SetIntProperty(serialized, "m_AtlasTextureIndex", 0);
        SetStringProperty(serialized, "m_SourceFontFileGUID", string.Empty);
        SetStringProperty(serialized, "m_SourceFontFilePath", string.Empty);
        SetStringProperty(serialized, "m_Version", "1.1.0");
        var atlasRef = serialized.FindProperty("m_AtlasTexture");
        if (atlasRef != null) atlasRef.objectReferenceValue = atlas;
        serialized.ApplyModifiedPropertiesWithoutUndo();
        if (asset.sourceFontFile != null)
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_SOURCE_FONT_PRESENT: static asset must not retain a font file");
        asset.ReadFontAssetDefinition();
        return asset;
    }

    internal static float ScaleTmpStyleWeight(float styleWeight, float sdfSpread)
    {
        if (float.IsNaN(styleWeight) || float.IsInfinity(styleWeight)
            || float.IsNaN(sdfSpread) || float.IsInfinity(sdfSpread) || sdfSpread <= 0f)
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_STYLE_RANGE_INVALID");
        float gradientScale = 2f * sdfSpread + 1f;
        float referenceDilateRange = TmpDefaultSdfGradientScale - TmpSdfRatioClamp;
        float targetDilateRange = gradientScale - TmpSdfRatioClamp;
        if (targetDilateRange <= 0f)
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_STYLE_GRADIENT_INVALID");
        return styleWeight * referenceDilateRange / targetDilateRange;
    }

    static void VerifyStaticSdfStyle(TMP_FontAsset asset, float sdfSpread, string assetId)
    {
        float gradientScale = 2f * sdfSpread + 1f;
        float expectedNormal = ScaleTmpStyleWeight(0f, sdfSpread);
        float expectedBold = ScaleTmpStyleWeight(TmpDefaultBoldStyle, sdfSpread);
        if (asset.material == null || !asset.material.HasProperty("_GradientScale")
            || !asset.material.HasProperty("_WeightNormal") || !asset.material.HasProperty("_WeightBold")
            || !Mathf.Approximately(asset.material.GetFloat("_GradientScale"), gradientScale)
            || !Mathf.Approximately(asset.normalStyle, expectedNormal)
            || !Mathf.Approximately(asset.boldStyle, expectedBold)
            || !Mathf.Approximately(asset.material.GetFloat("_WeightNormal"), expectedNormal)
            || !Mathf.Approximately(asset.material.GetFloat("_WeightBold"), expectedBold))
            throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_STYLE_READBACK_MISMATCH: " + assetId);
    }

    static void SetStringProperty(SerializedObject serialized, string propertyName, string value)
    {
        var property = serialized.FindProperty(propertyName);
        if (property != null && property.propertyType == SerializedPropertyType.String)
            property.stringValue = value;
    }

    static void SetIntProperty(SerializedObject serialized, string propertyName, int value)
    {
        var property = serialized.FindProperty(propertyName);
        if (property != null && (property.propertyType == SerializedPropertyType.Integer
                                 || property.propertyType == SerializedPropertyType.Enum))
            property.intValue = value;
    }

    static void SetBoolProperty(SerializedObject serialized, string propertyName, bool value)
    {
        var property = serialized.FindProperty(propertyName);
        if (property != null && property.propertyType == SerializedPropertyType.Boolean)
            property.boolValue = value;
    }

    static string GetStringProperty(SerializedObject serialized, string propertyName)
    {
        var property = serialized.FindProperty(propertyName);
        return property != null && property.propertyType == SerializedPropertyType.String ? property.stringValue : null;
    }

    static bool IsSha256(string value)
    {
        return value != null && System.Text.RegularExpressions.Regex.IsMatch(value, "^[0-9a-f]{64}$");
    }

    static void ValidateInstalledFontFiles(IEnumerable<FontSpec> fonts)
    {
        foreach (var font in fonts.GroupBy(item => item.targetSystemFontFileUrl, StringComparer.Ordinal).Select(group => group.First()))
        {
            if (string.IsNullOrEmpty(font.targetSystemFontFileUrl) || !Path.IsPathRooted(font.targetSystemFontFileUrl)
                || !IsSha256(font.targetSystemFontFileSha256) || !File.Exists(font.targetSystemFontFileUrl)
                || Sha256(File.ReadAllBytes(font.targetSystemFontFileUrl)) != font.targetSystemFontFileSha256)
                throw new InvalidOperationException("SYSTEM_FONT_INSTALLED_FACE_FILE_DRIFTED: " + font.familyName + " / " + font.styleName);
        }
    }

    static string Sha256(byte[] bytes)
    {
        using (var sha = SHA256.Create())
            return string.Concat(sha.ComputeHash(bytes).Select(value => value.ToString("x2")));
    }

    static void RecordAvailableFaces()
    {
        var lines=new List<string>();
        foreach(var name in Font.GetOSInstalledFontNames())lines.Add("UnityFontOS: "+name);
        foreach(var name in new[]{"GetSystemFontNames","GetSystemFontReferences"}) {
            var method=typeof(FontEngine).GetMethod(name,System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Static,null,Type.EmptyTypes,null);
            if(method==null){lines.Add(name+": unavailable");continue;}
            var values=method.Invoke(null,null) as System.Collections.IEnumerable;
            if(values==null)continue;
            int count=0;
            foreach(var value in values) {
                if(++count>4096){lines.Add("budget exceeded");break;}
                if(value is string text){lines.Add(name+": "+text);continue;}
                if(value==null)continue;
                var fields=value.GetType().GetFields(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Instance);
                lines.Add(name+": "+string.Join("; ",fields.Select(f=>f.Name+"="+Convert.ToString(f.GetValue(value)))));
            }
        }
        Directory.CreateDirectory("Analysis/Readback");
        File.WriteAllLines("Analysis/Readback/system-font-engine-faces.txt",lines);
    }

    static string ReadMacOSVersion(string argument)
    {
        var start = new ProcessStartInfo("/usr/bin/sw_vers", argument) {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        using (var process = Process.Start(start))
        {
            if (process == null) throw new InvalidOperationException("SYSTEM_FONT_OS_VERSION_UNAVAILABLE");
            string value = process.StandardOutput.ReadToEnd().Trim();
            process.WaitForExit();
            if (process.ExitCode != 0 || string.IsNullOrEmpty(value))
                throw new InvalidOperationException("SYSTEM_FONT_OS_VERSION_UNAVAILABLE: " + process.StandardError.ReadToEnd());
            return value;
        }
    }

    static void ValidateSpec(BindingSet bindingSet)
    {
        if (bindingSet == null || bindingSet.schema != ExpectedSchema || bindingSet.status != "prepared" || bindingSet.systemFonts == null)
            throw new InvalidOperationException("SYSTEM_FONT_SPEC_INVALID: unsupported binding-set schema or status");
        var spec = bindingSet.systemFonts;
        if (spec.schema != ExpectedSchema || spec.status != "prepared" || spec.targetOS != "macOS" || string.IsNullOrEmpty(spec.targetOSVersion))
            throw new InvalidOperationException("SYSTEM_FONT_TARGET_RECEIPT_INVALID: expected a prepared macOS receipt");
        if (spec.runtimePlatformConstraint != "macOS Player target only; native asset creation requires macOS Editor"
            || spec.playerTargetEvidence != "not_run")
            throw new InvalidOperationException("SYSTEM_FONT_RUNTIME_PLATFORM_CONSTRAINT_MISSING");
        if (spec.sourceOSIdentityVerified || spec.visualEquivalent)
            throw new InvalidOperationException("SYSTEM_FONT_SOURCE_BOUNDARY_INVALID: source OS and visual equivalence must remain unverified");
        if ((spec.populationMode != "DynamicOS" && spec.populationMode != "Mixed") || spec.pointSize != 90)
            throw new InvalidOperationException("SYSTEM_FONT_POPULATION_MODE_INVALID: expected DynamicOS or evidence-split Mixed mode at point size 90");
        if (string.IsNullOrEmpty(spec.irSha256) || string.IsNullOrEmpty(spec.sourceManifestSha256) || string.IsNullOrEmpty(spec.resolutionReceiptSha256))
            throw new InvalidOperationException("SYSTEM_FONT_EVIDENCE_PIN_MISSING: IR, source manifest and resolution receipt hashes are required");
        if (spec.fonts == null || spec.fonts.Length == 0 || bindingSet.labelBindings == null || bindingSet.labelBindings.Length == 0)
            throw new InvalidOperationException("SYSTEM_FONT_SPEC_EMPTY: no font assets or label bindings were supplied");
        if (spec.explicitFontLabelsReplaced != null && spec.explicitFontLabelsReplaced.Length != 0)
            throw new InvalidOperationException("SYSTEM_FONT_EXPLICIT_FONT_REPLACEMENT: explicit TTF/bitmap Label bindings must not be replaced");
        if (!string.Equals(spec.fontAssetDirectory, "Assets/Game/Content/Fonts/System", StringComparison.Ordinal))
            throw new InvalidOperationException("SYSTEM_FONT_ASSET_DIRECTORY_INVALID");
    }

    static void ValidateReferences(BindingSet bindingSet, Dictionary<string, FontSpec> byId)
    {
        var labelIds = new HashSet<string>(StringComparer.Ordinal);
        foreach (var font in byId.Values)
        {
            if (string.IsNullOrEmpty(font.assetId) || string.IsNullOrEmpty(font.familyName) || string.IsNullOrEmpty(font.styleName))
                throw new InvalidOperationException("SYSTEM_FONT_FACE_IDENTITY_INVALID");
            if (font.role != "primary" && font.role != "fallback")
                throw new InvalidOperationException("SYSTEM_FONT_ROLE_INVALID: " + font.assetId);
            if (font.pointSize != 90 || (font.populationMode != "DynamicOS" && font.populationMode != "StaticSDFRequired"))
                throw new InvalidOperationException("SYSTEM_FONT_MODE_MISMATCH: " + font.assetId);
            if (font.populationMode == "StaticSDFRequired"
                && (font.generationMode != "CoreTextRasterizedStaticSDF" || font.fontFileCopiedOrExported
                    || string.IsNullOrEmpty(font.targetPostScriptName) || !IsSha256(font.targetSystemFontFileSha256)
                    || font.matchingPhysicalFaces == null || font.matchingPhysicalFaces.Length != 0))
                throw new InvalidOperationException("SYSTEM_FONT_STATIC_SDF_CONTRACT_INVALID: " + font.assetId);
            if (font.populationMode == "DynamicOS"
                && (string.IsNullOrEmpty(font.targetPostScriptName) || !IsSha256(font.targetSystemFontFileSha256)
                    || font.matchingPhysicalFaces == null || font.matchingPhysicalFaces.Length != 1
                    || font.fontFileCopiedOrExported))
                throw new InvalidOperationException("SYSTEM_FONT_DYNAMIC_OS_FACE_IDENTITY_UNPROVEN: " + font.assetId);
            if (font.assetPath == null || !font.assetPath.StartsWith(ExpectedFontRoot, StringComparison.Ordinal)
                || font.assetPath.Contains("..") || font.assetPath.Contains("\\"))
                throw new InvalidOperationException("SYSTEM_FONT_ASSET_PATH_UNSAFE: " + font.assetPath);
            if (font.requiredUnicode == null)
                throw new InvalidOperationException("SYSTEM_FONT_GLYPH_SET_MISSING: " + font.assetId);
            foreach (var codepoint in font.requiredUnicode)
                if (codepoint > 0x10FFFF || (codepoint >= 0xD800 && codepoint <= 0xDFFF))
                    throw new InvalidOperationException("SYSTEM_FONT_CODEPOINT_INVALID: " + codepoint);
            var fallbackIds = font.fallbackAssetIds ?? Array.Empty<string>();
            foreach (var fallbackId in fallbackIds)
                if (!byId.ContainsKey(fallbackId) || byId[fallbackId].role != "fallback")
                    throw new InvalidOperationException("SYSTEM_FONT_FALLBACK_ASSET_MISSING: " + fallbackId);
            if (font.role == "fallback" && fallbackIds.Length != 0)
                throw new InvalidOperationException("SYSTEM_FONT_FALLBACK_LEAF_HAS_CHAIN: " + font.assetId);
        }

        foreach (var label in bindingSet.labelBindings)
        {
            if (string.IsNullOrEmpty(label.sourceLabelId) || !labelIds.Add(label.sourceLabelId))
                throw new InvalidOperationException("SYSTEM_FONT_LABEL_ID_INVALID_OR_DUPLICATE");
            // JsonUtility materializes a JSON null string as an empty string.
            // The producer has already verified that the source UUID is absent.
            bool sourceNullFontFallback = !label.sourceSystemFont
                && label.sourceFontFamily == "Arial"
                && ((label.sourceEffectiveFontPolicy == "creator24-null-font-ttf-Arial"
                     && label.sourceFontFamilyEvidence == "creator24-renderer-utils-getFontFamily-null-branch")
                    || (label.sourceEffectiveFontPolicy == "creator24-ttf-null-font-effective-family-arial-v1"
                        && label.sourceEffectiveFamily == "Arial"));
            if ((!label.sourceSystemFont && !sourceNullFontFallback) || !string.IsNullOrEmpty(label.sourceSerializedFontUuid))
                throw new InvalidOperationException("SYSTEM_FONT_SOURCE_BINDING_INVALID: explicit source font cannot enter this plan");
            if (!byId.TryGetValue(label.nativeFontAssetId, out var primary) || primary.role != "primary")
                throw new InvalidOperationException("SYSTEM_FONT_PRIMARY_ASSET_MISSING: " + label.nativeFontAssetId);
            if (!string.Equals(primary.assetPath, label.nativeFontAssetPath, StringComparison.Ordinal)
                || !string.Equals(primary.familyName, label.resolvedPrimaryFamily, StringComparison.Ordinal)
                || !string.Equals(primary.styleName, label.resolvedPrimaryStyleName, StringComparison.Ordinal))
                throw new InvalidOperationException("SYSTEM_FONT_LABEL_PRIMARY_MISMATCH: " + label.sourceLabelId);
            if (string.IsNullOrEmpty(label.sourceFontFamily) || string.IsNullOrEmpty(label.resolvedPrimaryFamily)
                || string.IsNullOrEmpty(label.resolvedPrimaryStyleName))
                throw new InvalidOperationException("SYSTEM_FONT_LABEL_FAMILY_MISSING: " + label.sourceLabelId);
            var fallbackIds = label.nativeFallbackAssetIds ?? Array.Empty<string>();
            var paths = label.nativeFallbackAssetPaths ?? Array.Empty<string>();
            if (!primary.fallbackAssetIds.SequenceEqual(fallbackIds, StringComparer.Ordinal)
                || fallbackIds.Length != paths.Length)
                throw new InvalidOperationException("SYSTEM_FONT_LABEL_FALLBACK_CHAIN_MISMATCH: " + label.sourceLabelId);
            for (int i = 0; i < fallbackIds.Length; i++)
            {
                if (!byId.TryGetValue(fallbackIds[i], out var fallback) || fallback.role != "fallback"
                    || !string.Equals(fallback.assetPath, paths[i], StringComparison.Ordinal))
                    throw new InvalidOperationException("SYSTEM_FONT_LABEL_FALLBACK_IDENTITY_MISMATCH: " + label.sourceLabelId);
            }
            if (string.IsNullOrEmpty(label.newCharacterBoundary))
                throw new InvalidOperationException("SYSTEM_FONT_NEW_CHARACTER_BOUNDARY_MISSING: " + label.sourceLabelId);
        }
    }

    static void VerifyFace(TMP_FontAsset asset, FontSpec spec)
    {
        if (!string.Equals(asset.faceInfo.familyName, spec.familyName, StringComparison.Ordinal)
            || !string.Equals(asset.faceInfo.styleName, spec.styleName, StringComparison.Ordinal))
            throw new InvalidOperationException("SYSTEM_FONT_FACE_READBACK_MISMATCH: requested " + spec.familyName + " / " + spec.styleName
                + ", resolved " + asset.faceInfo.familyName + " / " + asset.faceInfo.styleName);
        var expectedMode = spec.populationMode == "StaticSDFRequired" ? AtlasPopulationMode.Static : AtlasPopulationMode.DynamicOS;
        if (asset.atlasPopulationMode != expectedMode)
            throw new InvalidOperationException("SYSTEM_FONT_POPULATION_MODE_READBACK_MISMATCH: " + spec.assetId);
        if (expectedMode == AtlasPopulationMode.Static)
        {
            var serialized = new SerializedObject(asset);
            if (asset.sourceFontFile != null || !string.IsNullOrEmpty(GetStringProperty(serialized, "m_SourceFontFilePath"))
                || !string.IsNullOrEmpty(GetStringProperty(serialized, "m_SourceFontFileGUID")))
                throw new InvalidOperationException("SYSTEM_FONT_STATIC_SOURCE_PATH_NOT_EMPTY: " + spec.assetId);
        }
        var fontState = new SerializedObject(asset);
        if (GetBoolProperty(fontState, "m_ClearDynamicDataOnBuild"))
            throw new InvalidOperationException("SYSTEM_FONT_DYNAMIC_DATA_WOULD_BE_CLEARED: " + spec.assetId);
    }

    static void PreserveGeneratedDynamicGlyphData(TMP_FontAsset asset, FontSpec spec)
    {
        if (spec.populationMode != "DynamicOS")
            return;
        var serialized = new SerializedObject(asset);
        var property = serialized.FindProperty("m_ClearDynamicDataOnBuild");
        if (property == null || property.propertyType != SerializedPropertyType.Boolean)
            throw new InvalidOperationException("SYSTEM_FONT_DYNAMIC_CLEAR_SETTING_UNAVAILABLE: " + spec.assetId);
        property.boolValue = false;
        serialized.ApplyModifiedPropertiesWithoutUndo();
        EditorUtility.SetDirty(asset);
        if (GetBoolProperty(new SerializedObject(asset), "m_ClearDynamicDataOnBuild"))
            throw new InvalidOperationException("SYSTEM_FONT_DYNAMIC_CLEAR_SETTING_NOT_PERSISTED: " + spec.assetId);
    }

    static bool GetBoolProperty(SerializedObject serialized, string propertyName)
    {
        var property = serialized.FindProperty(propertyName);
        return property != null && property.propertyType == SerializedPropertyType.Boolean && property.boolValue;
    }

    static NativeGlyphState InspectRequiredGlyphs(TMP_FontAsset asset, FontSpec spec, string stage, bool populateDynamicOs)
    {
        var required = (spec.requiredUnicode ?? Array.Empty<uint>()).Distinct().OrderBy(value => value).ToArray();
        bool addCalled = populateDynamicOs && spec.populationMode == "DynamicOS" && required.Length > 0;
        bool addReturned = false;
        uint[] addMissing = Array.Empty<uint>();
        if (addCalled)
            addReturned = asset.TryAddCharacters(required, out addMissing, false);

        // On save/reopen readback, do not repopulate a DynamicOS face. TMP may
        // resolve it through a different OS lookup path after AssetDatabase.Refresh;
        // mutating at that point would mask whether the saved table is complete.
        var tableUnicode = (asset.characterTable ?? new List<TMP_Character>())
            .Where(character => character != null).Select(character => character.unicode)
            .Distinct().OrderBy(value => value).ToArray();
        var present = required.Where(codepoint => asset.HasCharacter((int)codepoint)).ToArray();
        var missing = required.Except(present).OrderBy(value => value).ToArray();
        var serialized = new SerializedObject(asset);
        var internalDynamic = serialized.FindProperty("InternalDynamicOS");
        return new NativeGlyphState {
            stage = stage,
            assetId = spec.assetId,
            assetPath = spec.assetPath,
            atlasPopulationMode = asset.atlasPopulationMode.ToString(),
            familyName = asset.faceInfo.familyName,
            styleName = asset.faceInfo.styleName,
            tryAddCharactersCalled = addCalled,
            tryAddCharactersReturned = addReturned,
            tryAddCharactersMissing = addMissing ?? Array.Empty<uint>(),
            requiredUnicode = required,
            characterTableUnicode = tableUnicode,
            lookupPresentUnicode = present,
            missingUnicode = missing,
            characterCount = asset.characterTable == null ? 0 : asset.characterTable.Count,
            glyphCount = asset.glyphTable == null ? 0 : asset.glyphTable.Count,
            atlasCount = asset.atlasTextures == null ? 0 : asset.atlasTextures.Count(texture => texture != null),
            sourceFontFilePresent = asset.sourceFontFile != null,
            sourceFontFileGuid = GetStringProperty(serialized, "m_SourceFontFileGUID"),
            sourceFontFilePath = GetStringProperty(serialized, "m_SourceFontFilePath"),
            internalDynamicOS = internalDynamic != null && internalDynamic.propertyType == SerializedPropertyType.Boolean && internalDynamic.boolValue,
            clearDynamicDataOnBuild = GetBoolProperty(serialized, "m_ClearDynamicDataOnBuild"),
        };
    }

    static void WriteGlyphDiagnostic(NativeGlyphState initialState, NativeGlyphState currentState)
    {
        try
        {
            Directory.CreateDirectory("Analysis/Readback");
            var record = new SystemFontGlyphDiagnosticFile {
                targetOS = "macOS",
                targetVersion = ReadMacOSVersion("-productVersion"),
                targetBuild = ReadMacOSVersion("-buildVersion"),
                stage = currentState == null ? "unknown" : currentState.stage,
                initialFontState = initialState,
                currentFontState = currentState,
            };
            File.WriteAllText("Analysis/Readback/system-font-glyph-diagnostics.json", JsonUtility.ToJson(record, true));
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogWarning("SYSTEM_FONT_GLYPH_DIAGNOSTIC_WRITE_FAILED: " + ex.Message);
        }
    }

    static void VerifyRuntimeResources(TMP_FontAsset asset, FontSpec spec)
    {
        if (asset.material == null || asset.atlasTextures == null || asset.atlasTextures.Length == 0
            || asset.atlasTextures.Any(texture => texture == null))
            throw new InvalidOperationException("SYSTEM_FONT_NATIVE_RESOURCES_MISSING: " + spec.assetId);
    }

    static void PersistFontSubassets(TMP_FontAsset asset)
    {
        if (asset.material != null && !AssetDatabase.Contains(asset.material))
            AssetDatabase.AddObjectToAsset(asset.material, asset);
        foreach (var atlas in asset.atlasTextures ?? Array.Empty<Texture2D>())
            if (atlas != null && !AssetDatabase.Contains(atlas))
                AssetDatabase.AddObjectToAsset(atlas, asset);
        EditorUtility.SetDirty(asset);
        if (asset.material != null) EditorUtility.SetDirty(asset.material);
        foreach (var atlas in asset.atlasTextures ?? Array.Empty<Texture2D>())
            if (atlas != null) EditorUtility.SetDirty(atlas);
    }

    static Readback BuildReadback(BindingSet bindingSet, Dictionary<string, PendingFont> pending,
                                  string staticSdfGenerationReceiptSha256,
                                  string sourceStaticSdfGenerationReceiptSha256)
    {
        var spec = bindingSet.systemFonts;
        var readback = new Readback {
            status = "readback_pass",
            targetOS = "macOS",
            targetVersion = ReadMacOSVersion("-productVersion"),
            targetBuild = ReadMacOSVersion("-buildVersion"),
            targetPlatform = Application.platform.ToString(),
            playerTargetEvidence = "not_run",
            sourceOSIdentityVerified = false,
            visualEquivalent = false,
            irSha256 = spec.irSha256,
            sourceManifestSha256 = spec.sourceManifestSha256,
            resolutionReceiptSha256 = spec.resolutionReceiptSha256,
            staticSdfGenerationReceiptSha256 = staticSdfGenerationReceiptSha256,
            sourceStaticSdfGenerationReceiptSha256 = sourceStaticSdfGenerationReceiptSha256,
            diagnostics = Array.Empty<string>(),
        };
        readback.fonts = pending.Values.OrderBy(p => p.spec.assetId, StringComparer.Ordinal).Select(item => {
            var saved = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(item.spec.assetPath);
            if (saved == null) throw new InvalidOperationException("SYSTEM_FONT_SAVE_READBACK_FAILED: " + item.spec.assetPath);
            VerifyFace(saved, item.spec);
            var savedGlyphState = InspectRequiredGlyphs(saved, item.spec, "save-reopen-readback", false);
            if (savedGlyphState.missingUnicode.Length > 0)
            {
                WriteGlyphDiagnostic(item.initialGlyphState, savedGlyphState);
                throw new InvalidOperationException("SYSTEM_FONT_GLYPH_SAVE_READBACK_MISSING: " + item.spec.assetId
                    + " " + item.spec.familyName + " / " + item.spec.styleName
                    + " missing " + string.Join(",", savedGlyphState.missingUnicode.Select(value => "U+" + value.ToString("X4")))
                    + "; initialTryAdd=" + (item.initialGlyphState != null && item.initialGlyphState.tryAddCharactersReturned)
                    + "; savedMode=" + savedGlyphState.atlasPopulationMode
                    + "; sourcePath=" + savedGlyphState.sourceFontFilePath);
            }
            VerifyRuntimeResources(saved, item.spec);
            if (item.sdfSpread > 0f)
                VerifyStaticSdfStyle(saved, item.sdfSpread, item.spec.assetId);
            var actualFallbacks = saved.fallbackFontAssetTable ?? new List<TMP_FontAsset>();
            var expectedFallbackIds = item.spec.fallbackAssetIds ?? Array.Empty<string>();
            if (actualFallbacks.Count != expectedFallbackIds.Length)
                throw new InvalidOperationException("SYSTEM_FONT_FALLBACK_READBACK_COUNT_MISMATCH: " + item.spec.assetId);
            for (int i = 0; i < actualFallbacks.Count; i++) {
                if (actualFallbacks[i] == null || AssetDatabase.GetAssetPath(actualFallbacks[i]) != pending[expectedFallbackIds[i]].spec.assetPath)
                    throw new InvalidOperationException("SYSTEM_FONT_FALLBACK_READBACK_MISMATCH: " + item.spec.assetId);
            }
            return new FontReadback {
                assetId = item.spec.assetId,
                assetPath = item.spec.assetPath,
                assetGuid = AssetDatabase.AssetPathToGUID(item.spec.assetPath),
                role = item.spec.role,
                generationMode = item.spec.generationMode ?? item.spec.populationMode,
                coreTextTargetPostScriptName = item.spec.targetPostScriptName,
                coreTextTargetVariationAxesJson = item.spec.targetVariationAxesJson,
                coreTextTargetFontFileSha256 = item.spec.targetSystemFontFileSha256,
                sourceLabelIds = item.spec.sourceLabelIds ?? Array.Empty<string>(),
                resolvedFamilyName = saved.faceInfo.familyName,
                resolvedStyleName = saved.faceInfo.styleName,
                populationMode = saved.atlasPopulationMode.ToString(),
                clearDynamicDataOnBuild = GetBoolProperty(new SerializedObject(saved), "m_ClearDynamicDataOnBuild"),
                fontSourcePathEmpty = saved.atlasPopulationMode != AtlasPopulationMode.Static
                                      || (saved.sourceFontFile == null
                                          && string.IsNullOrEmpty(GetStringProperty(new SerializedObject(saved), "m_SourceFontFilePath"))),
                pointSize = item.spec.pointSize,
                sdfSpread = item.sdfSpread,
                normalStyle = saved.normalStyle,
                boldStyle = saved.boldStyle,
                gradientScale = saved.material != null && saved.material.HasProperty("_GradientScale")
                    ? saved.material.GetFloat("_GradientScale") : 0f,
                weightNormal = saved.material != null && saved.material.HasProperty("_WeightNormal")
                    ? saved.material.GetFloat("_WeightNormal") : 0f,
                weightBold = saved.material != null && saved.material.HasProperty("_WeightBold")
                    ? saved.material.GetFloat("_WeightBold") : 0f,
                atlasCount = saved.atlasTextures == null ? 0 : saved.atlasTextures.Count(texture => texture != null),
                characterCount = saved.characterTable == null ? 0 : saved.characterTable.Count,
                requiredUnicodeCount = item.spec.requiredUnicode == null ? 0 : item.spec.requiredUnicode.Distinct().Count(),
                requiredUnicode = item.spec.requiredUnicode ?? Array.Empty<uint>(),
                requiredCodepoints = item.spec.requiredGlyphs == null ? Array.Empty<string>() : item.spec.requiredGlyphs.Select(g => g.codepoint).ToArray(),
                fallbackAssetIds = expectedFallbackIds,
                initialNativeGlyphState = item.initialGlyphState,
                savedNativeGlyphState = savedGlyphState,
            };
        }).ToArray();
        var byId = pending.ToDictionary(entry => entry.Key, entry => entry.Value.spec, StringComparer.Ordinal);
        readback.labelBindings = bindingSet.labelBindings.OrderBy(label => label.sourceLabelId, StringComparer.Ordinal).Select(label => {
            var primary = byId[label.nativeFontAssetId];
            var primaryGuid = AssetDatabase.AssetPathToGUID(primary.assetPath);
            var fallbacks = label.nativeFallbackAssetIds ?? Array.Empty<string>();
            return new LabelReadback {
                sourceLabelId = label.sourceLabelId,
                sourceText = label.sourceText,
                primaryAssetId = label.nativeFontAssetId,
                primaryAssetPath = primary.assetPath,
                primaryAssetGuid = primaryGuid,
                sourceFontFamily = label.sourceFontFamily,
                sourceFontFamilyEvidence = label.sourceFontFamilyEvidence,
                sourceSerializedFontUuid = label.sourceSerializedFontUuid,
                sourceSystemFont = label.sourceSystemFont,
                sourceEffectiveFontPolicy = label.sourceEffectiveFontPolicy,
                resolvedPrimaryFamily = label.resolvedPrimaryFamily,
                resolvedPrimaryStyleName = label.resolvedPrimaryStyleName,
                newCharacterBoundary = label.newCharacterBoundary,
                fallbackAssetIds = fallbacks,
                fallbackAssetPaths = fallbacks.Select(id => byId[id].assetPath).ToArray(),
            };
        }).ToArray();
        return readback;
    }
}
