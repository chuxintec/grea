using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Globalization;
using TMPro;
using Monkey.StaticMaskSort;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.UI;

namespace Monkey.StaticSortQueueProxy
{
    /// <summary>A live, non-serialized binding to one exact TMP material slot.</summary>
    public sealed class TextSlotBinding
    {
        public string sourceComponentId;
        public TMP_Text owner;
        public Graphic sourceGraphic;
        public Mesh sourceMesh;
        public int materialSlot;
        public bool generatedSubmesh;
        public bool sourceGraphicEnabled;
        public bool sourceGraphicActiveSelf;
        public bool sourceRendererSuppressionVerified;
        public bool sourceRectMaskCullVerified;
        public bool sourceCanvasCullBeforeCaptured;
        public bool sourceCanvasCullBeforeRuntime;
        public NativeStaticSortTextSlotEnumeration textSlotEnumeration;
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
        public string fontAssetGuid;
        public long fontAssetLocalFileId;
        public string spriteAssetGuid;
        public long spriteAssetLocalFileId;
        public string sourceMaterialGuid;
        public long sourceMaterialLocalFileId;
        public string sourceShaderGuid;
        public long sourceShaderLocalFileId;
        public string sourceTextureGuid;
        public long sourceTextureLocalFileId;
        public string sourceMeshSha256;
        public string currentSourceMeshSha256;
        public bool sourceMeshContextDerivedVerified;
        public string sourceMeshContextDiagnostic;
        public bool sourceMeshGeneratedByTmpVerified;
        public bool sourceMeshPositionsDiffer;
        public string sourceMeshPositionPairEvidenceSha256;
        public string sourceMeshRegenerationEvidenceSha256;
        public string sourceMeshRegenerationDiagnostic;
        public NativeStaticSortTextScaleContext currentTextScaleContext;
        public bool tmpFallbackMaterialBaked;
        public bool persistentFallbackVariantRegistered;
        public string tmpFallbackAlgorithm;
        public int tmpFallbackAtlasIndex;
        public string ownerFontMaterialGuid;
        public long ownerFontMaterialLocalFileId;
        public string ownerFontMaterialFingerprint;
        public OwnerFontStyleDescriptor ownerStyle;
        public string fallbackFontAssetGuid;
        public long fallbackFontAssetLocalFileId;
        public string fallbackFontMaterialGuid;
        public long fallbackFontMaterialLocalFileId;
        public string fallbackFontMaterialFingerprint;
        public string fallbackAtlasGuid;
        public long fallbackAtlasLocalFileId;
        public string transientFallbackFingerprint;
        public string sourceMaterialFingerprint;
        public string proxyMaterialFingerprint;
        public string proxyMaterialGuid;
        public long proxyMaterialLocalFileId;
        public string bakedProxyMaterialFingerprint;
        public string bakedProxyMaterialGuid;
        public long bakedProxyMaterialLocalFileId;
    }

    [Serializable]
    public sealed class TextSourceReadback
    {
        public string sourceComponentId, diagnostic;
        public int materialSlot;
        public bool ownerScopeVerified, persistentReferencesVerified, generatedSlotResolved, sourceStateVerified;
        public bool fontAssetVerified, spriteAssetVerified, materialVerified, shaderVerified, textureVerified;
        public bool tmpFallbackDescriptorVerified, ownerFontMaterialVerified, fallbackFontAssetVerified;
        public bool persistentFallbackVariantRegistered;
        public bool sourceRendererSuppressionVerified;
        public bool fallbackFontMaterialVerified, fallbackAtlasVerified, transientFallbackVerified, proxyMaterialVerified;
        public bool sourceRectMaskCullVerified, sourceCanvasCullBeforeCaptured, sourceCanvasCullBeforeRuntime;
        public bool bakedProxyMeshVerified, sourceMeshVerified, persistentTextSlotContractVerified, verified;
        public bool sourceMeshContextVerified, sourceMeshContextDerivedVerified;
        public bool sourceSlotMeshVerified;
        public bool sourceMeshRegeneratedFromCurrentTmpVerified;
        public NativeStaticSortTextSlotEnumeration textSlotEnumeration;
        public NativeStaticSortTextSlotEnumeration currentTextSlotEnumeration;
        public bool textInfoMaterialMissing, textInfoCharacterSlotVerified, textInfoCharacterMaterialVerified;
        public bool textInfoFontAssetVerified, textInfoAtlasVerified;
        public int textInfoCharacterCount, textInfoVisibleCharacterCount;
        public string sourceTextSha256;
        public string ownerGuid, fontAssetGuid, spriteAssetGuid, materialGuid, shaderGuid, textureGuid, proxyMaterialGuid,
            ownerFontMaterialGuid, fallbackFontAssetGuid, fallbackFontMaterialGuid, fallbackAtlasGuid,
            sourceSlotMeshGuid, sourceSlotMeshSha256;
        public long ownerLocalFileId, fontAssetLocalFileId, spriteAssetLocalFileId, materialLocalFileId,
            shaderLocalFileId, textureLocalFileId, proxyMeshLocalFileId, proxyMaterialLocalFileId,
            ownerFontMaterialLocalFileId, fallbackFontAssetLocalFileId, fallbackFontMaterialLocalFileId,
            fallbackAtlasLocalFileId, sourceSlotMeshLocalFileId;
        public string sourceMeshSha256, proxyMeshGuid, proxyMeshSha256, tmpFallbackAlgorithm,
            currentSourceMeshSha256, sourceMeshContextFormula, sourceMeshContextEvidenceSha256, sourceMeshContextDiagnostic,
            sourceMeshPositionPairEvidenceSha256, sourceMeshRegenerationEvidenceSha256, sourceMeshRegenerationDiagnostic,
            transientFallbackFingerprint, actualTransientMaterialFingerprint, sourceMaterialFingerprint,
            ownerFontMaterialFingerprint, fallbackFontMaterialFingerprint, bakedProxyMaterialFingerprint,
            textInfoCharacterEvidenceSha256, textInfoCharacterAssetEvidenceSha256, textInfoCharacterMaterialFingerprint,
            ownerStyleProfile, ownerStyleSourceComponentId, ownerStyleSourceFontAssetGuid,
            ownerStyleSourceFontMaterialGuid, ownerStyleSourceFontMaterialFingerprint;
        public long ownerStyleSourceFontAssetLocalFileId, ownerStyleSourceFontMaterialLocalFileId;
        public float ownerStyleOutlineWidth;
        public Color ownerStyleOutlineColor;
        public bool ownerStyleVerified;
    }

    [Serializable]
    public sealed class TextSlotEnumerationReadback
    {
        public string sourceComponentId, diagnostic;
        public bool ownerScopeVerified, persistentReferencesVerified, verified;
        public NativeStaticSortTextSlotEnumeration slotEnumeration;
        public NativeStaticSortTextSlotEnumeration currentSlotEnumeration;
    }

    [Serializable]
    public sealed class OwnerFontStyleDescriptor
    {
        public string profile;
        public string sourceComponentId;
        public float outlineWidth;
        public Color outlineColor;
        public TMP_FontAsset sourceFontAsset;
        public string sourceFontAssetGuid;
        public long sourceFontAssetLocalFileId;
        public Material sourceFontMaterial;
        public string sourceFontMaterialGuid;
        public long sourceFontMaterialLocalFileId;
        public string sourceFontMaterialFingerprint;
    }

    /// <summary>
    /// Exact TMP material/atlas capture and strict post-save resolution for
    /// static sort-queue proxies. This class never substitutes a white texture,
    /// manufactures a TMP material, or retains a generated submesh object in a
    /// serialized identity.
    /// </summary>
    public static class UnityStaticSortTextSource
    {
        const string MainTex = "_MainTex";
        static readonly FieldInfo MaterialSlotField = typeof(TMP_SubMeshUI).GetField(
            "m_materialReferenceIndex", BindingFlags.Instance | BindingFlags.NonPublic);
        static readonly FieldInfo CharacterWidthAdjustmentField = typeof(TMP_Text).GetField(
            "m_charWidthAdjDelta", BindingFlags.Instance | BindingFlags.NonPublic);
        static readonly FieldInfo CharacterHorizontalScaleField = typeof(TMP_Text).GetField(
            "m_characterHorizontalScale", BindingFlags.Instance | BindingFlags.NonPublic);
        static readonly MethodInfo MultiAtlasFallbackMethod = typeof(TMP_MaterialManager).GetMethod(
            "GetFallbackMaterial", BindingFlags.Static | BindingFlags.NonPublic, null,
            new[] { typeof(TMP_FontAsset), typeof(Material), typeof(int) }, null);

        static string HashText(string value)
        {
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(value ?? "")))
                    .Replace("-", "").ToLowerInvariant();
        }

        static string MaterialFingerprint(Material material)
        {
            if (material == null || material.shader == null) return null;
            if (!PersistentAsset(material.shader, out var shaderGuid, out var shaderFileId)) return null;
            var shader = material.shader;
            var sb = new StringBuilder();
            sb.Append("shader=").Append(shaderGuid).Append(':').Append(shaderFileId)
              .Append("|queue=").Append(material.renderQueue)
              .Append("|instancing=").Append(material.enableInstancing)
              .Append("|doubleSidedGI=").Append(material.doubleSidedGI)
              .Append("|giFlags=").Append((int)material.globalIlluminationFlags)
              .Append("|keywords=").Append(string.Join(",", material.shaderKeywords.OrderBy(value => value, StringComparer.Ordinal)));
            for (var index = 0; index < shader.GetPropertyCount(); index++)
            {
                var name = shader.GetPropertyName(index);
                var type = shader.GetPropertyType(index);
                sb.Append("|p=").Append(name).Append(':').Append(type).Append('=');
                if (type == UnityEngine.Rendering.ShaderPropertyType.Color)
                {
                    var value = material.GetColor(name);
                    sb.Append(value.r.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',')
                      .Append(value.g.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',')
                      .Append(value.b.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',')
                      .Append(value.a.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
                }
                else if (type == UnityEngine.Rendering.ShaderPropertyType.Vector)
                    AppendVector(sb, material.GetVector(name));
                else if (type == UnityEngine.Rendering.ShaderPropertyType.Texture)
                {
                    var texture = material.GetTexture(name);
                    if (texture == null) sb.Append("null");
                    else if (texture == Texture2D.whiteTexture) sb.Append("builtin:white");
                    else if (AssetIdentity(texture, out var textureGuid, out var textureFileId))
                        sb.Append(textureGuid).Append(':').Append(textureFileId);
                    else return null;
                    var scale = material.GetTextureScale(name); var offset = material.GetTextureOffset(name);
                    sb.Append(";scale=").Append(scale.x.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',')
                      .Append(scale.y.ToString("R", System.Globalization.CultureInfo.InvariantCulture))
                      .Append(";offset=").Append(offset.x.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',')
                      .Append(offset.y.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
                }
                else if (type == UnityEngine.Rendering.ShaderPropertyType.Int)
                    sb.Append(material.GetInt(name));
                else
                    sb.Append(material.GetFloat(name).ToString("R", System.Globalization.CultureInfo.InvariantCulture));
            }
            return HashText(sb.ToString());
        }

        static string MaterialCacheState(Material material)
        {
            if (ReferenceEquals(material, null)) return "managed-null";
            if (material == null) return "unity-destroyed-reference";
            if (material.shader == null) return "live-without-shader:" + ObjectIdentitySummary(material);
            if (!PersistentAsset(material.shader, out var shaderGuid, out var shaderLocalId))
                return "live-unpinned-shader:" + ObjectIdentitySummary(material.shader);
            var fingerprint = MaterialFingerprint(material);
            return String.IsNullOrEmpty(fingerprint)
                ? "live-fingerprint-unavailable:shader=" + shaderGuid + ":" + shaderLocalId + ":material=" +
                    ObjectIdentitySummary(material) + ":reason=" + MaterialFingerprintFailure(material)
                : "live:" + fingerprint;
        }

        static string MaterialFingerprintFailure(Material material)
        {
            if (ReferenceEquals(material, null)) return "managed-null";
            if (material == null) return "unity-destroyed-reference";
            if (material.shader == null) return "shaderMissing";
            if (!PersistentAsset(material.shader, out var shaderGuid, out var shaderLocalId))
                return "shaderNotPersistent:" + ObjectIdentitySummary(material.shader);
            for (var index = 0; index < material.shader.GetPropertyCount(); index++)
            {
                var name = material.shader.GetPropertyName(index);
                if (material.shader.GetPropertyType(index) != UnityEngine.Rendering.ShaderPropertyType.Texture) continue;
                var texture = material.GetTexture(name);
                if (texture == null || texture == Texture2D.whiteTexture) continue;
                if (!AssetIdentity(texture, out var textureGuid, out var textureLocalId))
                    return "texturePropertyNotPersistent:" + name + ":" + ObjectIdentitySummary(texture);
            }
            return "unknownFingerprintFailure;shader=" + shaderGuid + ":" + shaderLocalId;
        }

        static string MaterialFingerprintDelta(Material expected, Material actual)
        {
            var details = new List<string>();
            if (expected == null || actual == null)
                return "expected=" + (expected == null ? "null" : "present") + ";actual=" + (actual == null ? "null" : "present");
            var expectedShader = expected.shader;
            var actualShader = actual.shader;
            if (expectedShader == null || actualShader == null || expectedShader != actualShader)
                details.Add("shader=" + ObjectIdentitySummary(expectedShader) + "->" + ObjectIdentitySummary(actualShader));
            if (expected.renderQueue != actual.renderQueue) details.Add("renderQueue=" + expected.renderQueue + "->" + actual.renderQueue);
            if (expected.enableInstancing != actual.enableInstancing) details.Add("instancing=" + expected.enableInstancing + "->" + actual.enableInstancing);
            if (expected.doubleSidedGI != actual.doubleSidedGI) details.Add("doubleSidedGI=" + expected.doubleSidedGI + "->" + actual.doubleSidedGI);
            if (expected.globalIlluminationFlags != actual.globalIlluminationFlags)
                details.Add("giFlags=" + expected.globalIlluminationFlags + "->" + actual.globalIlluminationFlags);
            var expectedKeywords = String.Join(",", expected.shaderKeywords.OrderBy(value => value, StringComparer.Ordinal));
            var actualKeywords = String.Join(",", actual.shaderKeywords.OrderBy(value => value, StringComparer.Ordinal));
            if (expectedKeywords != actualKeywords) details.Add("keywords=" + Clip(expectedKeywords) + "->" + Clip(actualKeywords));
            if (expectedShader != null && actualShader != null && expectedShader == actualShader)
            {
                var count = expectedShader.GetPropertyCount();
                for (var index = 0; index < count; index++)
                {
                    var name = expectedShader.GetPropertyName(index);
                    var type = expectedShader.GetPropertyType(index);
                    var left = MaterialPropertyValue(expected, name, type);
                    var right = MaterialPropertyValue(actual, name, type);
                    if (left == right) continue;
                    details.Add(name + "=" + Clip(left) + "->" + Clip(right));
                    if (details.Count >= 16) break;
                }
            }
            if (details.Count == 0) return "no-visible-property-delta;fingerprintNullExpected=" + (MaterialFingerprint(expected) == null) +
                ";fingerprintNullActual=" + (MaterialFingerprint(actual) == null);
            return String.Join("|", details) + (details.Count >= 16 ? "|truncated=true" : "");
        }

        static string MaterialPropertyValue(Material material, string name, UnityEngine.Rendering.ShaderPropertyType type)
        {
            if (type == UnityEngine.Rendering.ShaderPropertyType.Color)
            {
                var value = material.GetColor(name);
                return value.r.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + "," +
                    value.g.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + "," +
                    value.b.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + "," +
                    value.a.ToString("R", System.Globalization.CultureInfo.InvariantCulture);
            }
            if (type == UnityEngine.Rendering.ShaderPropertyType.Vector)
            {
                var value = material.GetVector(name);
                return value.x.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + "," +
                    value.y.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + "," +
                    value.z.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + "," +
                    value.w.ToString("R", System.Globalization.CultureInfo.InvariantCulture);
            }
            if (type == UnityEngine.Rendering.ShaderPropertyType.Texture)
            {
                var texture = material.GetTexture(name);
                var scale = material.GetTextureScale(name); var offset = material.GetTextureOffset(name);
                return ObjectIdentitySummary(texture) + ";scale=" + scale.x.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + "," +
                    scale.y.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + ";offset=" +
                    offset.x.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + "," +
                    offset.y.ToString("R", System.Globalization.CultureInfo.InvariantCulture);
            }
            return type == UnityEngine.Rendering.ShaderPropertyType.Int
                ? material.GetInt(name).ToString(System.Globalization.CultureInfo.InvariantCulture)
                : material.GetFloat(name).ToString("R", System.Globalization.CultureInfo.InvariantCulture);
        }

        static string ObjectIdentitySummary(UnityEngine.Object value)
        {
            if (value == null) return "null";
            if (AssetIdentity(value, out var guid, out var fileId)) return guid + ":" + fileId;
            return "unpersisted:" + value.GetType().Name + ":" + Clip(value.name);
        }

        static string Clip(string value)
        {
            if (String.IsNullOrEmpty(value)) return value ?? "";
            return value.Length <= 96 ? value : value.Substring(0, 93) + "...";
        }

        static void AppendVector(StringBuilder sb, Vector4 value)
        {
            sb.Append(value.x.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',')
              .Append(value.y.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',')
              .Append(value.z.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',')
              .Append(value.w.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(';');
        }

        static int UvDimension(Mesh mesh, int channel)
        {
            if (mesh == null || channel < 0 || channel > 7) return 0;
            var attribute = (UnityEngine.Rendering.VertexAttribute)((int)UnityEngine.Rendering.VertexAttribute.TexCoord0 + channel);
            return mesh.HasVertexAttribute(attribute) ? mesh.GetVertexAttributeDimension(attribute) : 0;
        }

        static string FloatEvidence(float value) => value.ToString("R", CultureInfo.InvariantCulture);
        static bool Finite(float value) => !Single.IsNaN(value) && !Single.IsInfinity(value);

        static NativeStaticSortTextLayoutEvidence TextLayoutEvidence(TMP_Text owner)
        {
            if (owner == null || !(owner.transform is RectTransform rectTransform)) return null;
            var rect = rectTransform.rect;
            var lineBox = owner.GetComponent<NativeTextLineBox>();
            var fitter = owner.GetComponent<UnityEngine.UI.ContentSizeFitter>();
            var lineCount = owner.textInfo == null ? 0 : owner.textInfo.lineCount;
            var lineBoxLineHeight = lineBox == null ? 0f : lineBox.LineHeight;
            var lineBoxExtraFraction = lineBox == null ? 0f : lineBox.ExtraLineFraction;
            var lineBoxNativeHeight = lineBox == null ? 0f : lineBox.preferredHeight;
            var lineBoxSemanticHeight = lineBox == null ? null : TextLineBoxSemanticHeight(
                lineCount, lineBoxLineHeight, lineBoxExtraFraction, owner.margin);
            var lineBoxSemanticDecimal = lineBoxSemanticHeight != null &&
                Decimal.TryParse(lineBoxSemanticHeight, NumberStyles.Float, CultureInfo.InvariantCulture, out var parsedSemanticHeight)
                ? (decimal?)parsedSemanticHeight : null;
            var fitterPreferred = fitter != null && fitter.verticalFit == UnityEngine.UI.ContentSizeFitter.FitMode.PreferredSize;
            var rectHeightDecimal = DecimalFloat(rect.height);
            var authoredHeightMatches = lineBoxSemanticDecimal.HasValue && rectHeightDecimal.HasValue &&
                rectHeightDecimal.Value == lineBoxSemanticDecimal.Value;
            var nativeHeightMatches = lineBox != null && rect.height == lineBoxNativeHeight;
            var lineBoxProvenance = lineBox != null && lineBox.isActiveAndEnabled && fitter != null &&
                fitter.isActiveAndEnabled && fitterPreferred && lineCount > 0 &&
                lineBoxSemanticHeight != null && Finite(lineBoxNativeHeight) &&
                (authoredHeightMatches || nativeHeightMatches);
            return new NativeStaticSortTextLayoutEvidence {
                rectSize = new Vector2(rect.width, rect.height),
                pivot = rectTransform.pivot,
                margin = owner.margin,
                textLineBoxPresent = lineBox != null,
                textLineBoxActive = lineBox != null && lineBox.isActiveAndEnabled,
                textLineBoxLineHeight = lineBoxLineHeight,
                textLineBoxExtraLineFraction = lineBoxExtraFraction,
                textLineBoxLineCount = lineCount,
                contentSizeFitterPresent = fitter != null,
                contentSizeFitterActive = fitter != null && fitter.isActiveAndEnabled,
                contentSizeFitterHorizontalFit = fitter == null ? -1 : (int)fitter.horizontalFit,
                contentSizeFitterVerticalFit = fitter == null ? -1 : (int)fitter.verticalFit,
                textLineBoxNativePreferredHeight = lineBoxNativeHeight,
                textLineBoxAuthoredPreferredHeight = lineBoxSemanticHeight,
                textLineBoxHeightProvenanceVerified = lineBoxProvenance,
                fontSize = owner.fontSize,
                fontSizeMin = owner.fontSizeMin,
                fontSizeMax = owner.fontSizeMax,
                autoSizing = owner.enableAutoSizing,
                fontStyle = (int)owner.fontStyle,
                fontWeight = (int)owner.fontWeight,
                alignment = (int)owner.alignment,
                wrappingMode = (int)owner.textWrappingMode,
                overflowMode = (int)owner.overflowMode,
                maxVisibleCharacters = owner.maxVisibleCharacters,
                maxVisibleWords = owner.maxVisibleWords,
                maxVisibleLines = owner.maxVisibleLines,
                pageToDisplay = owner.pageToDisplay,
                characterSpacing = owner.characterSpacing,
                wordSpacing = owner.wordSpacing,
                lineSpacing = owner.lineSpacing,
                lineSpacingAdjustment = owner.lineSpacingAdjustment,
                paragraphSpacing = owner.paragraphSpacing,
                extraPadding = owner.extraPadding,
                richText = owner.richText,
                parseControlCharacters = owner.parseCtrlCharacters,
                rightToLeft = owner.isRightToLeftText,
                useMaxVisibleDescender = owner.useMaxVisibleDescender,
                fontFeatures = owner.fontFeatures == null ? Array.Empty<int>() :
                    owner.fontFeatures.Select(feature => (int)feature).ToArray(),
            };
        }

        static decimal? DecimalFloat(float value)
        {
            if (!Finite(value)) return null;
            if (Decimal.TryParse(FloatEvidence(value), NumberStyles.Float, CultureInfo.InvariantCulture, out var parsed))
                return parsed;
            return null;
        }

        static string TextLineBoxSemanticHeight(int lineCount, float lineHeight, float extraLineFraction, Vector4 margin)
        {
            var lineHeightDecimal = DecimalFloat(lineHeight);
            var extraDecimal = DecimalFloat(extraLineFraction);
            var marginTopDecimal = DecimalFloat(margin.y);
            var marginBottomDecimal = DecimalFloat(margin.w);
            if (lineCount < 1 || !lineHeightDecimal.HasValue || !extraDecimal.HasValue ||
                !marginTopDecimal.HasValue || !marginBottomDecimal.HasValue) return null;
            var rows = Math.Max(1, lineCount);
            var height = (rows + extraDecimal.Value) * lineHeightDecimal.Value +
                marginTopDecimal.Value + marginBottomDecimal.Value;
            return height.ToString("G29", CultureInfo.InvariantCulture);
        }

        static bool HasVerifiedTextLineBoxHeight(NativeStaticSortTextLayoutEvidence evidence)
        {
            if (evidence == null || !evidence.textLineBoxPresent || !evidence.textLineBoxActive ||
                !evidence.contentSizeFitterPresent || !evidence.contentSizeFitterActive ||
                !Enum.IsDefined(typeof(UnityEngine.UI.ContentSizeFitter.FitMode), evidence.contentSizeFitterHorizontalFit) ||
                evidence.contentSizeFitterVerticalFit != (int)UnityEngine.UI.ContentSizeFitter.FitMode.PreferredSize ||
                evidence.textLineBoxLineCount < 1 || !evidence.textLineBoxHeightProvenanceVerified ||
                !Finite(evidence.textLineBoxLineHeight) || !Finite(evidence.textLineBoxExtraLineFraction) ||
                !Finite(evidence.textLineBoxNativePreferredHeight)) return false;
            var semanticHeight = TextLineBoxSemanticHeight(evidence.textLineBoxLineCount,
                evidence.textLineBoxLineHeight, evidence.textLineBoxExtraLineFraction, evidence.margin);
            if (semanticHeight == null || semanticHeight != evidence.textLineBoxAuthoredPreferredHeight) return false;
            var rawHeight = DecimalFloat(evidence.rectSize.y);
            var authoredHeight = Decimal.TryParse(semanticHeight, NumberStyles.Float, CultureInfo.InvariantCulture, out var authored)
                ? (decimal?)authored : null;
            return rawHeight.HasValue && authoredHeight.HasValue &&
                (rawHeight.Value == authoredHeight.Value || evidence.rectSize.y == evidence.textLineBoxNativePreferredHeight);
        }

        static string TextLayoutEvidenceSha256(NativeStaticSortTextLayoutEvidence evidence)
        {
            if (evidence == null) return null;
            if (!Finite(evidence.rectSize.x) || !Finite(evidence.rectSize.y) ||
                !Finite(evidence.pivot.x) || !Finite(evidence.pivot.y) ||
                !Finite(evidence.margin.x) || !Finite(evidence.margin.y) ||
                !Finite(evidence.margin.z) || !Finite(evidence.margin.w) ||
                !Finite(evidence.fontSize) || !Finite(evidence.fontSizeMin) || !Finite(evidence.fontSizeMax) ||
                !Finite(evidence.characterSpacing) || !Finite(evidence.wordSpacing) ||
                !Finite(evidence.lineSpacing) || !Finite(evidence.lineSpacingAdjustment) ||
                !Finite(evidence.paragraphSpacing) || !Finite(evidence.textLineBoxLineHeight) ||
                !Finite(evidence.textLineBoxExtraLineFraction) || !Finite(evidence.textLineBoxNativePreferredHeight)) return null;
            var sb = new StringBuilder();
            var lineBoxHeightProven = HasVerifiedTextLineBoxHeight(evidence);
            sb.Append("rectSize.width=").Append(FloatEvidence(evidence.rectSize.x))
                .Append("|rectSize.height=").Append(lineBoxHeightProven
                    ? "native-text-line-box:" + evidence.textLineBoxAuthoredPreferredHeight
                    : FloatEvidence(evidence.rectSize.y))
                .Append("|pivot=").Append(FloatEvidence(evidence.pivot.x)).Append(',').Append(FloatEvidence(evidence.pivot.y))
                .Append("|margin="); AppendVector(sb, evidence.margin);
            sb.Append("|lineBoxPresent=").Append(evidence.textLineBoxPresent)
                .Append("|lineBoxActive=").Append(evidence.textLineBoxActive)
                .Append("|lineBoxLineHeight=").Append(FloatEvidence(evidence.textLineBoxLineHeight))
                .Append("|lineBoxExtraFraction=").Append(FloatEvidence(evidence.textLineBoxExtraLineFraction))
                .Append("|lineBoxLineCount=").Append(evidence.textLineBoxLineCount)
                .Append("|contentSizeFitterPresent=").Append(evidence.contentSizeFitterPresent)
                .Append("|contentSizeFitterActive=").Append(evidence.contentSizeFitterActive)
                .Append("|contentSizeFitterHorizontalFit=").Append(evidence.contentSizeFitterHorizontalFit)
                .Append("|contentSizeFitterVerticalFit=").Append(evidence.contentSizeFitterVerticalFit)
                .Append("|lineBoxNativePreferredHeight=").Append(FloatEvidence(evidence.textLineBoxNativePreferredHeight))
                .Append("|lineBoxAuthoredPreferredHeight=").Append(String.IsNullOrEmpty(evidence.textLineBoxAuthoredPreferredHeight)
                    ? "missing" : evidence.textLineBoxAuthoredPreferredHeight)
                .Append("|lineBoxHeightProvenanceVerified=").Append(lineBoxHeightProven)
                .Append("|fontSize=").Append(FloatEvidence(evidence.fontSize))
                .Append("|fontMin=").Append(FloatEvidence(evidence.fontSizeMin))
                .Append("|fontMax=").Append(FloatEvidence(evidence.fontSizeMax))
                .Append("|autoSize=").Append(evidence.autoSizing)
                .Append("|fontStyle=").Append(evidence.fontStyle)
                .Append("|fontWeight=").Append(evidence.fontWeight)
                .Append("|alignment=").Append(evidence.alignment)
                .Append("|wrap=").Append(evidence.wrappingMode)
                .Append("|overflow=").Append(evidence.overflowMode)
                .Append("|maxVisibleCharacters=").Append(evidence.maxVisibleCharacters)
                .Append("|maxVisibleWords=").Append(evidence.maxVisibleWords)
                .Append("|maxVisibleLines=").Append(evidence.maxVisibleLines)
                .Append("|page=").Append(evidence.pageToDisplay)
                .Append("|characterSpacing=").Append(FloatEvidence(evidence.characterSpacing))
                .Append("|wordSpacing=").Append(FloatEvidence(evidence.wordSpacing))
                .Append("|lineSpacing=").Append(FloatEvidence(evidence.lineSpacing))
                .Append("|lineSpacingAdjustment=").Append(FloatEvidence(evidence.lineSpacingAdjustment))
                .Append("|paragraphSpacing=").Append(FloatEvidence(evidence.paragraphSpacing))
                .Append("|extraPadding=").Append(evidence.extraPadding)
                .Append("|richText=").Append(evidence.richText)
                .Append("|parseControlCharacters=").Append(evidence.parseControlCharacters)
                .Append("|rightToLeft=").Append(evidence.rightToLeft)
                .Append("|useMaxVisibleDescender=").Append(evidence.useMaxVisibleDescender)
                .Append("|fontFeatures=").Append(String.Join(",", (evidence.fontFeatures ?? Array.Empty<int>())
                    .Select(value => value.ToString(CultureInfo.InvariantCulture))));
            return HashText(sb.ToString());
        }

        static string TextLayoutEvidenceDifference(NativeStaticSortTextLayoutEvidence captured,
            NativeStaticSortTextLayoutEvidence current)
        {
            if (captured == null || current == null) return captured == current ? "both-null" : "one-missing";
            var differences = new List<string>();
            void Add(string field, string a, string b)
            {
                if (!String.Equals(a, b, StringComparison.Ordinal)) differences.Add(field + "=" + a + "!=" + b);
            }
            Add("rect.width", FloatEvidence(captured.rectSize.x), FloatEvidence(current.rectSize.x));
            var capturedLineBoxHeightVerified = HasVerifiedTextLineBoxHeight(captured);
            var currentLineBoxHeightVerified = HasVerifiedTextLineBoxHeight(current);
            if (!(capturedLineBoxHeightVerified && currentLineBoxHeightVerified &&
                captured.textLineBoxAuthoredPreferredHeight == current.textLineBoxAuthoredPreferredHeight &&
                captured.textLineBoxNativePreferredHeight == current.textLineBoxNativePreferredHeight))
                Add("rect.height", FloatEvidence(captured.rectSize.y), FloatEvidence(current.rectSize.y));
            Add("pivot", FloatEvidence(captured.pivot.x) + "," + FloatEvidence(captured.pivot.y),
                FloatEvidence(current.pivot.x) + "," + FloatEvidence(current.pivot.y));
            Add("margin", FloatEvidence(captured.margin.x) + "," + FloatEvidence(captured.margin.y) + "," +
                FloatEvidence(captured.margin.z) + "," + FloatEvidence(captured.margin.w),
                FloatEvidence(current.margin.x) + "," + FloatEvidence(current.margin.y) + "," +
                FloatEvidence(current.margin.z) + "," + FloatEvidence(current.margin.w));
            Add("lineBoxPresent", captured.textLineBoxPresent.ToString(), current.textLineBoxPresent.ToString());
            Add("lineBoxActive", captured.textLineBoxActive.ToString(), current.textLineBoxActive.ToString());
            Add("lineBoxLineHeight", FloatEvidence(captured.textLineBoxLineHeight), FloatEvidence(current.textLineBoxLineHeight));
            Add("lineBoxExtraFraction", FloatEvidence(captured.textLineBoxExtraLineFraction), FloatEvidence(current.textLineBoxExtraLineFraction));
            Add("lineBoxLineCount", captured.textLineBoxLineCount.ToString(), current.textLineBoxLineCount.ToString());
            Add("contentSizeFitterPresent", captured.contentSizeFitterPresent.ToString(), current.contentSizeFitterPresent.ToString());
            Add("contentSizeFitterActive", captured.contentSizeFitterActive.ToString(), current.contentSizeFitterActive.ToString());
            Add("contentSizeFitterHorizontalFit", captured.contentSizeFitterHorizontalFit.ToString(), current.contentSizeFitterHorizontalFit.ToString());
            Add("contentSizeFitterVerticalFit", captured.contentSizeFitterVerticalFit.ToString(), current.contentSizeFitterVerticalFit.ToString());
            Add("lineBoxNativePreferredHeight", FloatEvidence(captured.textLineBoxNativePreferredHeight),
                FloatEvidence(current.textLineBoxNativePreferredHeight));
            Add("lineBoxAuthoredPreferredHeight", String.IsNullOrEmpty(captured.textLineBoxAuthoredPreferredHeight)
                    ? "missing" : captured.textLineBoxAuthoredPreferredHeight,
                String.IsNullOrEmpty(current.textLineBoxAuthoredPreferredHeight)
                    ? "missing" : current.textLineBoxAuthoredPreferredHeight);
            Add("lineBoxHeightProvenanceVerified", capturedLineBoxHeightVerified.ToString(), currentLineBoxHeightVerified.ToString());
            Add("fontSize", FloatEvidence(captured.fontSize), FloatEvidence(current.fontSize));
            Add("fontSizeMin", FloatEvidence(captured.fontSizeMin), FloatEvidence(current.fontSizeMin));
            Add("fontSizeMax", FloatEvidence(captured.fontSizeMax), FloatEvidence(current.fontSizeMax));
            Add("autoSizing", captured.autoSizing.ToString(), current.autoSizing.ToString());
            Add("fontStyle", captured.fontStyle.ToString(), current.fontStyle.ToString());
            Add("fontWeight", captured.fontWeight.ToString(), current.fontWeight.ToString());
            Add("alignment", captured.alignment.ToString(), current.alignment.ToString());
            Add("wrappingMode", captured.wrappingMode.ToString(), current.wrappingMode.ToString());
            Add("overflowMode", captured.overflowMode.ToString(), current.overflowMode.ToString());
            Add("maxVisibleCharacters", captured.maxVisibleCharacters.ToString(), current.maxVisibleCharacters.ToString());
            Add("maxVisibleWords", captured.maxVisibleWords.ToString(), current.maxVisibleWords.ToString());
            Add("maxVisibleLines", captured.maxVisibleLines.ToString(), current.maxVisibleLines.ToString());
            Add("pageToDisplay", captured.pageToDisplay.ToString(), current.pageToDisplay.ToString());
            Add("characterSpacing", FloatEvidence(captured.characterSpacing), FloatEvidence(current.characterSpacing));
            Add("wordSpacing", FloatEvidence(captured.wordSpacing), FloatEvidence(current.wordSpacing));
            Add("lineSpacing", FloatEvidence(captured.lineSpacing), FloatEvidence(current.lineSpacing));
            Add("lineSpacingAdjustment", FloatEvidence(captured.lineSpacingAdjustment), FloatEvidence(current.lineSpacingAdjustment));
            Add("paragraphSpacing", FloatEvidence(captured.paragraphSpacing), FloatEvidence(current.paragraphSpacing));
            Add("extraPadding", captured.extraPadding.ToString(), current.extraPadding.ToString());
            Add("richText", captured.richText.ToString(), current.richText.ToString());
            Add("parseControlCharacters", captured.parseControlCharacters.ToString(), current.parseControlCharacters.ToString());
            Add("rightToLeft", captured.rightToLeft.ToString(), current.rightToLeft.ToString());
            Add("useMaxVisibleDescender", captured.useMaxVisibleDescender.ToString(), current.useMaxVisibleDescender.ToString());
            Add("fontFeatures", String.Join(",", captured.fontFeatures ?? Array.Empty<int>()),
                String.Join(",", current.fontFeatures ?? Array.Empty<int>()));
            return differences.Count == 0 ? "exact" : String.Join("|", differences.Take(12));
        }

        static bool TryBuildTextScaleContext(TMP_Text owner, Graphic graphic, Mesh mesh,
            string sourceComponentId, int materialSlot,
            out NativeStaticSortTextScaleContext context, out string diagnostic)
        {
            context = null; diagnostic = null;
            var canvas = owner == null ? null : owner.canvas;
            var info = owner == null ? null : owner.textInfo;
            if (!(owner is TextMeshProUGUI) || graphic == null || mesh == null || canvas == null || info == null ||
                info.characterInfo == null || CharacterWidthAdjustmentField == null || CharacterHorizontalScaleField == null ||
                String.IsNullOrWhiteSpace(sourceComponentId) || materialSlot < 0)
                return Fail("TMP_SORT_UV_SCALE_CONTEXT_INPUT_OR_SDK_LAYOUT_INVALID", out diagnostic);
            var textLayoutInputs = TextLayoutEvidence(owner);
            var textLayoutEvidenceSha256 = TextLayoutEvidenceSha256(textLayoutInputs);
            if (!IsSha256(textLayoutEvidenceSha256))
                return Fail("TMP_SORT_UV_SCALE_CONTEXT_TEXT_LAYOUT_EVIDENCE_INVALID", out diagnostic);
            float charWidthAdjustment, characterHorizontalScale;
            try
            {
                charWidthAdjustment = (float)CharacterWidthAdjustmentField.GetValue(owner);
                characterHorizontalScale = (float)CharacterHorizontalScaleField.GetValue(owner);
            }
            catch (Exception error)
            {
                return Fail("TMP_SORT_UV_SCALE_CONTEXT_SDK_FIELD_READ_FAILED:" + error.GetType().Name, out diagnostic);
            }
            if (!Finite(charWidthAdjustment) || !Finite(characterHorizontalScale) ||
                !Finite(canvas.scaleFactor) || canvas.scaleFactor <= 0f ||
                !Finite(owner.transform.lossyScale.y) || !Finite(graphic.transform.lossyScale.y))
                return Fail("TMP_SORT_UV_SCALE_CONTEXT_NONFINITE_INPUT", out diagnostic);

            var characters = new List<NativeStaticSortTextScaleCharacter>();
            for (var index = 0; index < info.characterCount; index++)
            {
                var character = info.characterInfo[index];
                if (character.materialReferenceIndex != materialSlot) continue;
                var unicode = character.textElement == null
                    ? (int)character.character
                    : checked((int)character.textElement.unicode);
                if (!Finite(character.scale) || character.vertexIndex < 0)
                    return Fail("TMP_SORT_UV_SCALE_CONTEXT_CHARACTER_METRICS_INVALID:" + index, out diagnostic);
                characters.Add(new NativeStaticSortTextScaleCharacter {
                    characterIndex = index,
                    materialSlot = character.materialReferenceIndex,
                    vertexIndex = character.vertexIndex,
                    unicode = unicode,
                    scale = character.scale,
                    visible = character.isVisible,
                    textElementType = (int)character.elementType,
                    fontStyle = (int)character.style,
                    usingAlternateTypeface = character.isUsingAlternateTypeface,
                });
            }
            if (characters.Count == 0)
                return Fail("TMP_SORT_UV_SCALE_CONTEXT_CHARACTER_SLOT_EMPTY:" + materialSlot, out diagnostic);
            var meshUv0 = new List<Vector4>();
            mesh.GetUVs(0, meshUv0);
            if (UvDimension(mesh, 0) != 4 || meshUv0.Count != mesh.vertexCount)
                return Fail("TMP_SORT_UV_SCALE_CONTEXT_MESH_UV0_LAYOUT_INVALID:" + UvDimension(mesh, 0) + ":" +
                    meshUv0.Count + "/" + mesh.vertexCount, out diagnostic);
            var meshUv0W = meshUv0.Select(value => value.w).ToArray();

            var sourceTextSha = HashText(owner.text ?? String.Empty);
            var operandBuilder = new StringBuilder();
            operandBuilder.Append(sourceComponentId).Append('|').Append(sourceTextSha).Append('|').Append(materialSlot)
                .Append('|').Append(FloatEvidence(charWidthAdjustment)).Append('|')
                .Append(FloatEvidence(characterHorizontalScale)).Append('|').Append(FloatEvidence(owner.fontSize)).Append('|')
                .Append(owner.enableAutoSizing).Append('|').Append((int)owner.fontStyle).Append('|')
                .Append(FloatEvidence(owner.fontSizeMin)).Append('|').Append(FloatEvidence(owner.fontSizeMax)).Append('|');
            foreach (var character in characters)
                operandBuilder.Append(character.characterIndex).Append(':').Append(character.materialSlot).Append(':')
                    .Append(character.vertexIndex).Append(':').Append(character.unicode).Append(':')
                    .Append(FloatEvidence(character.scale)).Append(':').Append(character.visible).Append(':')
                    .Append(character.textElementType).Append(':').Append(character.fontStyle).Append(':')
                    .Append(character.usingAlternateTypeface).Append(';');
            var operandEvidence = HashText(operandBuilder.ToString());
            var contextBuilder = new StringBuilder(operandBuilder.ToString());
            contextBuilder.Append("|formula=TextMeshProUGUI.GenerateTextMesh.uv0.w-v1|")
                .Append("layout=").Append(textLayoutEvidenceSha256).Append('|')
                .Append((int)canvas.renderMode).Append('|').Append(FloatEvidence(canvas.scaleFactor)).Append('|')
                .Append(canvas.worldCamera != null).Append('|').Append(FloatEvidence(owner.transform.lossyScale.y)).Append('|')
                .Append(FloatEvidence(graphic.transform.lossyScale.y));
            foreach (var value in meshUv0W) contextBuilder.Append("|uv0w=").Append(FloatEvidence(value));
            context = new NativeStaticSortTextScaleContext {
                sourceComponentId = sourceComponentId,
                sourceTextSha256 = sourceTextSha,
                materialSlot = materialSlot,
                formula = "TextMeshProUGUI.GenerateTextMesh.uv0.w-v1",
                canvasRenderMode = (int)canvas.renderMode,
                canvasScaleFactor = canvas.scaleFactor,
                worldCameraAssigned = canvas.worldCamera != null,
                ownerLossyScaleY = owner.transform.lossyScale.y,
                graphicLossyScaleY = graphic.transform.lossyScale.y,
                ownerFontSize = owner.fontSize,
                ownerFontSizeMin = owner.fontSizeMin,
                ownerFontSizeMax = owner.fontSizeMax,
                ownerFontStyle = (int)owner.fontStyle,
                ownerAutoSizing = owner.enableAutoSizing,
                charWidthAdjustmentDelta = charWidthAdjustment,
                characterHorizontalScale = characterHorizontalScale,
                textLayoutInputs = textLayoutInputs,
                characters = characters.ToArray(),
                meshUv0W = meshUv0W,
                operandEvidenceSha256 = operandEvidence,
                textLayoutEvidenceSha256 = textLayoutEvidenceSha256,
                evidenceSha256 = HashText(contextBuilder.ToString()),
            };
            return true;
        }

        static bool IsValidTextScaleContext(NativeStaticSortTextScaleContext context)
        {
            if (context == null || context.formula != "TextMeshProUGUI.GenerateTextMesh.uv0.w-v1" ||
                String.IsNullOrWhiteSpace(context.sourceComponentId) || !IsSha256(context.sourceTextSha256) ||
                context.materialSlot < 0 || context.characters == null || context.characters.Length == 0 ||
                context.meshUv0W == null || context.meshUv0W.Length == 0 || context.textLayoutInputs == null ||
                TextLayoutEvidenceSha256(context.textLayoutInputs) != context.textLayoutEvidenceSha256 ||
                !IsSha256(context.operandEvidenceSha256) || !IsSha256(context.evidenceSha256) ||
                !Enum.IsDefined(typeof(RenderMode), context.canvasRenderMode) ||
                !Finite(context.canvasScaleFactor) || context.canvasScaleFactor <= 0f ||
                !Finite(context.ownerLossyScaleY) || !Finite(context.graphicLossyScaleY) ||
                !Finite(context.ownerFontSize) || !Finite(context.ownerFontSizeMin) || !Finite(context.ownerFontSizeMax) ||
                !Finite(context.charWidthAdjustmentDelta) || !Finite(context.characterHorizontalScale)) return false;
            var operandBuilder = new StringBuilder();
            operandBuilder.Append(context.sourceComponentId).Append('|').Append(context.sourceTextSha256).Append('|')
                .Append(context.materialSlot).Append('|').Append(FloatEvidence(context.charWidthAdjustmentDelta)).Append('|')
                .Append(FloatEvidence(context.characterHorizontalScale)).Append('|').Append(FloatEvidence(context.ownerFontSize)).Append('|')
                .Append(context.ownerAutoSizing).Append('|').Append(context.ownerFontStyle).Append('|')
                .Append(FloatEvidence(context.ownerFontSizeMin)).Append('|').Append(FloatEvidence(context.ownerFontSizeMax)).Append('|');
            foreach (var character in context.characters)
            {
                if (character == null || character.materialSlot != context.materialSlot || character.vertexIndex < 0 ||
                    !Finite(character.scale)) return false;
                operandBuilder.Append(character.characterIndex).Append(':').Append(character.materialSlot).Append(':')
                    .Append(character.vertexIndex).Append(':').Append(character.unicode).Append(':')
                    .Append(FloatEvidence(character.scale)).Append(':').Append(character.visible).Append(':')
                    .Append(character.textElementType).Append(':').Append(character.fontStyle).Append(':')
                    .Append(character.usingAlternateTypeface).Append(';');
            }
            if (HashText(operandBuilder.ToString()) != context.operandEvidenceSha256) return false;
            var contextBuilder = new StringBuilder(operandBuilder.ToString());
            contextBuilder.Append("|formula=TextMeshProUGUI.GenerateTextMesh.uv0.w-v1|")
                .Append("layout=").Append(context.textLayoutEvidenceSha256).Append('|')
                .Append(context.canvasRenderMode).Append('|').Append(FloatEvidence(context.canvasScaleFactor)).Append('|')
                .Append(context.worldCameraAssigned).Append('|').Append(FloatEvidence(context.ownerLossyScaleY)).Append('|')
                .Append(FloatEvidence(context.graphicLossyScaleY));
            foreach (var value in context.meshUv0W)
            {
                if (!Finite(value)) return false;
                contextBuilder.Append("|uv0w=").Append(FloatEvidence(value));
            }
            return HashText(contextBuilder.ToString()) == context.evidenceSha256;
        }

        static float ComputeTmpUvScale(NativeStaticSortTextScaleCharacter character, float charWidthAdjustmentDelta,
            float characterHorizontalScale, int renderMode, bool worldCameraAssigned,
            float ownerLossyScaleY, float canvasScaleFactor)
        {
            if (character == null || character.textElementType != (int)TMP_TextElementType.Character)
                return Single.NaN;
            var xScale = character.scale * (1f - charWidthAdjustmentDelta) * characterHorizontalScale;
            if (!character.usingAlternateTypeface &&
                (((FontStyles)character.fontStyle & FontStyles.Bold) == FontStyles.Bold)) xScale *= -1f;
            switch ((RenderMode)renderMode)
            {
                case RenderMode.ScreenSpaceOverlay:
                    xScale *= Mathf.Abs(ownerLossyScaleY) / canvasScaleFactor;
                    break;
                case RenderMode.ScreenSpaceCamera:
                    xScale *= worldCameraAssigned ? Mathf.Abs(ownerLossyScaleY) : 1f;
                    break;
                case RenderMode.WorldSpace:
                    xScale *= Mathf.Abs(ownerLossyScaleY);
                    break;
                default:
                    return Single.NaN;
            }
            return xScale;
        }

        static string UvScaleFormulaSummary(NativeStaticSortTextScaleContext context)
        {
            if (context == null) return "missing";
            return "formula=" + context.formula + ";mode=" + (RenderMode)context.canvasRenderMode +
                ";scaleFactor=" + FloatEvidence(context.canvasScaleFactor) +
                ";ownerLossyScaleY=" + FloatEvidence(context.ownerLossyScaleY) +
                ";graphicLossyScaleY=" + FloatEvidence(context.graphicLossyScaleY) +
                ";widthAdj=" + FloatEvidence(context.charWidthAdjustmentDelta) +
                ";horizontalScale=" + FloatEvidence(context.characterHorizontalScale) +
                ";operandSha=" + (context.operandEvidenceSha256 ?? "missing");
        }

        static bool TextScaleContextUvMatchesMesh(NativeStaticSortTextScaleContext context, Mesh mesh,
            out string diagnostic)
        {
            diagnostic = null;
            if (!IsValidTextScaleContext(context) || mesh == null || mesh.vertexCount != context.meshUv0W.Length ||
                UvDimension(mesh, 0) != 4)
            { diagnostic = "scale-context-or-mesh-invalid"; return false; }
            var uv0 = new List<Vector4>(); mesh.GetUVs(0, uv0);
            if (uv0.Count != mesh.vertexCount)
            { diagnostic = "uv0-data-unavailable"; return false; }
            for (var vertex = 0; vertex < uv0.Count; vertex++)
                if (uv0[vertex].w != context.meshUv0W[vertex])
                { diagnostic = "uv0-w-context-mismatch:" + vertex; return false; }
            diagnostic = "all-mesh-uv0-w-values-match-captured-context";
            return true;
        }

        static bool MeshChannelsMatchExceptUv0W(Mesh current, Mesh captured, out string diagnostic)
        {
            diagnostic = null;
            if (current == null || captured == null || current.vertexCount != captured.vertexCount ||
                current.subMeshCount != captured.subMeshCount || UvDimension(current, 0) != 4 || UvDimension(captured, 0) != 4)
            {
                diagnostic = "mesh-topology-or-uv0-layout-mismatch";
                return false;
            }
            if (!current.colors32.SequenceEqual(captured.colors32)) { diagnostic = "colors-differ"; return false; }
            if (!current.normals.SequenceEqual(captured.normals)) { diagnostic = "normals-differ"; return false; }
            if (!current.tangents.SequenceEqual(captured.tangents)) { diagnostic = "tangents-differ"; return false; }
            var currentUv0 = new List<Vector4>(); var capturedUv0 = new List<Vector4>();
            current.GetUVs(0, currentUv0); captured.GetUVs(0, capturedUv0);
            if (currentUv0.Count != current.vertexCount || capturedUv0.Count != captured.vertexCount)
            { diagnostic = "uv0-count-mismatch"; return false; }
            for (var index = 0; index < currentUv0.Count; index++)
                if (currentUv0[index].x != capturedUv0[index].x || currentUv0[index].y != capturedUv0[index].y ||
                    currentUv0[index].z != capturedUv0[index].z)
                { diagnostic = "uv0-xyz-differs:" + index; return false; }
            for (var channel = 1; channel < 8; channel++)
            {
                if (UvDimension(current, channel) != UvDimension(captured, channel))
                { diagnostic = "uv-dimension-differs:" + channel; return false; }
                var currentUv = new List<Vector4>(); var capturedUv = new List<Vector4>();
                current.GetUVs(channel, currentUv); captured.GetUVs(channel, capturedUv);
                if (!currentUv.SequenceEqual(capturedUv)) { diagnostic = "uv-channel-differs:" + channel; return false; }
            }
            for (var submesh = 0; submesh < current.subMeshCount; submesh++)
                if (!current.GetTriangles(submesh).SequenceEqual(captured.GetTriangles(submesh)))
                { diagnostic = "indices-differ:" + submesh; return false; }
            var currentVertices = current.vertices; var capturedVertices = captured.vertices;
            if (currentVertices.Any(point => !Finite(point.x) || !Finite(point.y) || !Finite(point.z)) ||
                capturedVertices.Any(point => !Finite(point.x) || !Finite(point.y) || !Finite(point.z)))
            { diagnostic = "nonfinite-position-data"; return false; }
            if (!currentVertices.SequenceEqual(capturedVertices)) { diagnostic = "positions-differ"; return false; }
            diagnostic = "all-non-uv0-w-mesh-data-exact";
            return true;
        }

        static bool VerifyTextScaleFormulaAgainstMesh(NativeStaticSortTextScaleContext context, Mesh mesh,
            out string diagnostic)
        {
            diagnostic = null;
            if (!TextScaleContextUvMatchesMesh(context, mesh, out diagnostic)) return false;
            var uv0 = new List<Vector4>(); mesh.GetUVs(0, uv0);
            var expectedByVertex = new float?[mesh.vertexCount];
            var computed = new List<float>();
            foreach (var character in context.characters)
            {
                if (!character.visible || character.textElementType != (int)TMP_TextElementType.Character) continue;
                var value = ComputeTmpUvScale(character, context.charWidthAdjustmentDelta,
                    context.characterHorizontalScale, context.canvasRenderMode, context.worldCameraAssigned,
                    context.ownerLossyScaleY, context.canvasScaleFactor);
                if (!Finite(value) || character.vertexIndex < 0 || character.vertexIndex + 3 >= mesh.vertexCount)
                { diagnostic = "character-uv-range-or-formula-invalid:" + character.characterIndex; return false; }
                computed.Add(value);
                for (var offset = 0; offset < 4; offset++)
                {
                    var vertex = character.vertexIndex + offset;
                    if (expectedByVertex[vertex].HasValue)
                    { diagnostic = "character-vertex-formula-overlap:" + character.characterIndex + ":" + vertex; return false; }
                    expectedByVertex[vertex] = value;
                }
            }
            if (computed.Count == 0)
            {
                for (var vertex = 0; vertex < uv0.Count; vertex++)
                    if (uv0[vertex].w != context.meshUv0W[vertex])
                    { diagnostic = "non-character-slot-uv0-w-context-differs:" + vertex; return false; }
                diagnostic = "no-visible-sdf-character-scale;uv0-w-exact";
                return true;
            }
            for (var vertex = 0; vertex < expectedByVertex.Length; vertex++)
            {
                if (!expectedByVertex[vertex].HasValue)
                {
                    // TMP's per-slot mesh can contain spare/hidden vertices or
                    // sprite data. They are not covered by the character SDF
                    // equation and must remain byte-for-byte stable across the
                    // capture/current comparison below.
                    if (uv0[vertex].w != context.meshUv0W[vertex])
                    { diagnostic = "unmapped-vertex-context-differs:" + vertex; return false; }
                    continue;
                }
                var expected = expectedByVertex[vertex].Value;
                if (uv0[vertex].w != expected || context.meshUv0W[vertex] != expected)
                {
                    diagnostic = "sdk-uv0-w-equation-mismatch:vertex=" + vertex +
                        ";mesh=" + FloatEvidence(uv0[vertex].w) + ";context=" + FloatEvidence(context.meshUv0W[vertex]) +
                        ";sdk=" + FloatEvidence(expected);
                    return false;
                }
            }
            diagnostic = "sdk-uv0-w-equation-exact;formula=" + context.formula +
                ";mode=" + (RenderMode)context.canvasRenderMode +
                ";scaleFactor=" + FloatEvidence(context.canvasScaleFactor) +
                ";ownerLossyScaleY=" + FloatEvidence(context.ownerLossyScaleY);
            return true;
        }

        static bool UnmappedUv0WMatches(NativeStaticSortTextScaleContext capturedContext,
            NativeStaticSortTextScaleContext currentContext, Mesh capturedMesh, Mesh currentMesh,
            out string diagnostic)
        {
            diagnostic = null;
            if (!IsValidTextScaleContext(capturedContext) || !IsValidTextScaleContext(currentContext) ||
                capturedMesh == null || currentMesh == null || capturedMesh.vertexCount != currentMesh.vertexCount)
            { diagnostic = "uv0-context-or-mesh-invalid"; return false; }
            var mapped = new bool[capturedMesh.vertexCount];
            foreach (var character in capturedContext.characters)
            {
                if (!character.visible || character.textElementType != (int)TMP_TextElementType.Character) continue;
                if (character.vertexIndex < 0 || character.vertexIndex + 3 >= mapped.Length)
                { diagnostic = "captured-character-vertex-range-invalid:" + character.characterIndex; return false; }
                for (var offset = 0; offset < 4; offset++)
                {
                    if (mapped[character.vertexIndex + offset])
                    { diagnostic = "captured-character-vertex-overlap:" + character.characterIndex; return false; }
                    mapped[character.vertexIndex + offset] = true;
                }
            }
            var capturedUv0 = new List<Vector4>(); var currentUv0 = new List<Vector4>();
            capturedMesh.GetUVs(0, capturedUv0); currentMesh.GetUVs(0, currentUv0);
            if (capturedUv0.Count != mapped.Length || currentUv0.Count != mapped.Length)
            { diagnostic = "uv0-channel-count-mismatch"; return false; }
            for (var vertex = 0; vertex < mapped.Length; vertex++)
            {
                if (!mapped[vertex] && capturedUv0[vertex].w != currentUv0[vertex].w)
                { diagnostic = "unmapped-uv0-w-differs:" + vertex + ":" + FloatEvidence(capturedUv0[vertex].w) + "!=" + FloatEvidence(currentUv0[vertex].w); return false; }
            }
            diagnostic = "all-non-character-uv0-w-exact";
            return true;
        }

        static bool VerifyLoadedTextMeshContext(TextSlotBinding binding, NativeStaticSortTextSource identity,
            out NativeStaticSortTextScaleContext currentContext, out string diagnostic)
        {
            currentContext = null; diagnostic = null;
            if (binding == null || identity == null || binding.owner == null || binding.sourceGraphic == null ||
                binding.sourceMesh == null || !IsValidTextScaleContext(identity.textScaleContext))
            { diagnostic = "source-scale-context-or-binding-missing"; return false; }
            var capturedMesh = identity.sourceSlotMesh;
            if (capturedMesh == null || identity.sourceSlotMeshSha256 != identity.sourceMeshSha256 ||
                MeshFingerprint(capturedMesh) != identity.sourceMeshSha256 ||
                !PersistentAsset(capturedMesh, out var capturedSourceGuid, out var capturedSourceLocalId) ||
                capturedSourceGuid != identity.sourceSlotMeshGuid || capturedSourceLocalId != identity.sourceSlotMeshLocalFileId)
            { diagnostic = "captured-source-slot-mesh-reference-or-identity-mismatch"; return false; }
            if (!TryBuildTextScaleContext(binding.owner, binding.sourceGraphic, binding.sourceMesh,
                    binding.sourceComponentId, binding.materialSlot, out currentContext, out diagnostic)) return false;
            var capturedContext = identity.textScaleContext;
            if (capturedContext.sourceComponentId != binding.sourceComponentId ||
                capturedContext.sourceTextSha256 != binding.sourceTextSha256 ||
                capturedContext.materialSlot != binding.materialSlot ||
                capturedContext.operandEvidenceSha256 != currentContext.operandEvidenceSha256)
            {
                diagnostic = "tmp-scale-operands-differ:capture=" + (capturedContext.operandEvidenceSha256 ?? "missing") +
                    ";current=" + (currentContext.operandEvidenceSha256 ?? "missing") +
                    ";capture=" + UvScaleFormulaSummary(capturedContext) + ";current=" + UvScaleFormulaSummary(currentContext);
                return false;
            }
            if (capturedContext.textLayoutEvidenceSha256 != currentContext.textLayoutEvidenceSha256)
            {
                diagnostic = "tmp-text-layout-inputs-differ:capture=" + capturedContext.textLayoutEvidenceSha256 +
                    ";current=" + currentContext.textLayoutEvidenceSha256 +
                    ";field-diff=" + TextLayoutEvidenceDifference(capturedContext.textLayoutInputs, currentContext.textLayoutInputs);
                return false;
            }
            var liveMeshSha = MeshFingerprint(binding.sourceMesh);
            if (liveMeshSha == identity.sourceMeshSha256)
            {
                diagnostic = "loaded-source-mesh-sha-exact;uv-equation-not-needed";
                return true;
            }
            var nonScaleMeshExact = MeshChannelsMatchExceptUv0W(binding.sourceMesh, capturedMesh, out var meshDiagnostic);
            var sourcePositionsDiffer = !nonScaleMeshExact && meshDiagnostic == "positions-differ";
            if (!nonScaleMeshExact && !sourcePositionsDiffer)
            { diagnostic = "non-scale-mesh-data-differs:" + meshDiagnostic; return false; }
            if (!VerifyTextScaleFormulaAgainstMesh(capturedContext, capturedMesh, out var capturedFormulaDiagnostic))
            { diagnostic = "captured-" + capturedFormulaDiagnostic; return false; }
            if (!VerifyTextScaleFormulaAgainstMesh(currentContext, binding.sourceMesh, out var currentFormulaDiagnostic))
            { diagnostic = "current-" + currentFormulaDiagnostic; return false; }
            if (!UnmappedUv0WMatches(capturedContext, currentContext, capturedMesh, binding.sourceMesh,
                    out var unmappedUvDiagnostic))
            { diagnostic = "non-character-uv0-w-differs:" + unmappedUvDiagnostic; return false; }
            if (sourcePositionsDiffer)
            {
                if (!binding.sourceMeshGeneratedByTmpVerified)
                { diagnostic = "source-position-difference-without-exact-TextInfo-CanvasRenderer-slot-proof"; return false; }
                var pairEvidence = HashText(binding.sourceComponentId + "|" + binding.materialSlot + "|" +
                    identity.sourceSlotMeshGuid + ":" + identity.sourceSlotMeshLocalFileId + "|" +
                    identity.sourceMeshSha256 + "|" + liveMeshSha + "|" +
                    capturedContext.textLayoutEvidenceSha256 + "|" + capturedContext.operandEvidenceSha256 + "|" +
                    capturedFormulaDiagnostic + "|" + currentFormulaDiagnostic + "|" + unmappedUvDiagnostic);
                binding.sourceMeshPositionsDiffer = true;
                binding.sourceMeshPositionPairEvidenceSha256 = pairEvidence;
                binding.sourceMeshRegenerationEvidenceSha256 = pairEvidence;
                binding.sourceMeshRegenerationDiagnostic = "captured-source-slot-mesh=" + identity.sourceMeshSha256 +
                    ";current-TMP-slot-mesh=" + liveMeshSha +
                    ";layoutInputsExact=" + capturedContext.textLayoutEvidenceSha256 +
                    ";all-non-position-channels-and-topology-exact=" + meshDiagnostic +
                    ";TMP-CanvasRenderer-slot-mesh-exact=" + binding.sourceMeshGeneratedByTmpVerified +
                    ";world-geometry-proof-required=" + binding.sourceComponentId + ":" + binding.materialSlot;
                diagnostic = "captured-and-current-tmp-source-meshes-have-exact-layout-and-nonposition-data;positions-differ;" +
                    binding.sourceMeshRegenerationDiagnostic + ";" + UvScaleFormulaSummary(capturedContext) +
                    ";" + UvScaleFormulaSummary(currentContext) + ";" + unmappedUvDiagnostic;
                return true;
            }
            diagnostic = "capture-and-current-tmp-uv0-w-sdk-equations-exact;capture=" +
                UvScaleFormulaSummary(capturedContext) + ";current=" + UvScaleFormulaSummary(currentContext) +
                ";mesh=" + meshDiagnostic + ";" + unmappedUvDiagnostic;
            return true;
        }

        /// <summary>Fingerprint compatible with the sort-proxy source mesh contract.</summary>
        public static string MeshFingerprint(Mesh mesh, int submesh = 0)
        {
            if (mesh == null || submesh < 0 || submesh >= mesh.subMeshCount) return null;
            var sb = new StringBuilder();
            sb.Append(mesh.vertexCount).Append('|').Append(mesh.subMeshCount).Append('|').Append(submesh).Append('|');
            foreach (var point in mesh.vertices) AppendVector(sb, point);
            foreach (var color in mesh.colors32) sb.Append(color.r).Append(',').Append(color.g).Append(',')
                .Append(color.b).Append(',').Append(color.a).Append(';');
            for (var channel = 0; channel < 8; channel++)
            {
                var values = new List<Vector4>(); mesh.GetUVs(channel, values);
                sb.Append('#').Append(channel).Append('/').Append(UvDimension(mesh, channel)).Append(':');
                foreach (var uv in values) AppendVector(sb, uv);
            }
            foreach (var normal in mesh.normals) AppendVector(sb, normal);
            foreach (var tangent in mesh.tangents) AppendVector(sb, tangent);
            foreach (var index in mesh.GetTriangles(submesh)) sb.Append(index).Append(',');
            return HashText(sb.ToString());
        }

        static bool AssetIdentity(UnityEngine.Object value, out string guid, out long localFileId)
        {
            guid = null; localFileId = 0;
            return value != null && AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value, out guid, out localFileId) &&
                !String.IsNullOrWhiteSpace(guid) && localFileId != 0;
        }

        static bool SameIdentity(UnityEngine.Object value, string expectedGuid, long expectedLocalFileId,
            out string actualGuid, out long actualLocalFileId)
        {
            return AssetIdentity(value, out actualGuid, out actualLocalFileId) &&
                actualGuid == expectedGuid && actualLocalFileId == expectedLocalFileId;
        }

        static bool TryMaterialSlot(TMP_SubMeshUI generated, out int slot)
        {
            slot = -1;
            if (generated == null || MaterialSlotField == null) return false;
            var value = MaterialSlotField.GetValue(generated);
            if (!(value is int index) || index <= 0) return false;
            slot = index;
            return true;
        }

        static int MeshNonDegenerateTriangleCount(Mesh mesh)
        {
            if (mesh == null) return 0;
            try
            {
                var vertices = mesh.vertices;
                var count = 0;
                for (var submesh = 0; submesh < mesh.subMeshCount; submesh++)
                {
                    var indices = mesh.GetTriangles(submesh);
                    for (var index = 0; index + 2 < indices.Length; index += 3)
                    {
                        var a = indices[index]; var b = indices[index + 1]; var c = indices[index + 2];
                        if (a < 0 || b < 0 || c < 0 || a >= vertices.Length || b >= vertices.Length || c >= vertices.Length)
                            return Int32.MaxValue;
                        if (Vector3.Cross(vertices[b] - vertices[a], vertices[c] - vertices[a]).sqrMagnitude > 1e-12f)
                            count++;
                    }
                }
                return count;
            }
            catch { return Int32.MaxValue; }
        }

        static uint MeshFirstSubmeshIndexCount(Mesh mesh)
        {
            return mesh != null && mesh.subMeshCount > 0 ? mesh.GetIndexCount(0) : 0;
        }

        static uint MeshTotalIndexCount(Mesh mesh)
        {
            if (mesh == null) return 0;
            ulong count = 0;
            for (var submesh = 0; submesh < mesh.subMeshCount; submesh++) count += mesh.GetIndexCount(submesh);
            return count > UInt32.MaxValue ? UInt32.MaxValue : (uint)count;
        }

        static bool MeshHasDrawTriangles(Mesh mesh)
        {
            return MeshNonDegenerateTriangleCount(mesh) > 0;
        }

        static string MeshGeometryDiagnostic(Mesh mesh)
        {
            if (mesh == null) return "null";
            try
            {
                var vertices = mesh.vertices;
                var indices = mesh.triangles;
                var colors = mesh.colors32;
                var vertexSummary = String.Join(",", Enumerable.Range(0, Math.Min(4, vertices.Length)).Select(index =>
                    vertices[index].x.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + "/" +
                    vertices[index].y.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + "/" +
                    vertices[index].z.ToString("R", System.Globalization.CultureInfo.InvariantCulture) +
                    (colors.Length == vertices.Length ? "/a" + colors[index].a : "")));
                var indexSummary = String.Join(",", indices.Take(6));
                return "vertices=" + mesh.vertexCount + ";indices=" + indices.Length +
                    ";nondegenerateTriangles=" + MeshNonDegenerateTriangleCount(mesh) +
                    ";bounds=" + mesh.bounds.size.x.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + "/" +
                    mesh.bounds.size.y.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + "/" +
                    mesh.bounds.size.z.ToString("R", System.Globalization.CultureInfo.InvariantCulture) +
                    ";firstVertices=" + vertexSummary + ";firstIndices=" + indexSummary;
            }
            catch (Exception error) { return "diagnostic_failed:" + error.GetType().Name; }
        }

        /// <summary>Resolve a Graphic captured by TMP owner to its owner-wide material slot.</summary>
        public static bool TryGetMaterialSlot(TMP_Text owner, Graphic sourceGraphic, out int materialSlot,
            out string diagnostic)
        {
            materialSlot = -1; diagnostic = null;
            if (owner == null || sourceGraphic == null) return Fail("TMP_SORT_GRAPHIC_SLOT_OWNER_MISSING", out diagnostic);
            if (sourceGraphic == (Graphic)owner)
            {
                materialSlot = 0;
                return true;
            }
            if (sourceGraphic is TMP_SubMeshUI generated && generated.textComponent == owner &&
                TryMaterialSlot(generated, out materialSlot)) return true;
            materialSlot = -1;
            return Fail("TMP_SORT_GRAPHIC_SLOT_IS_NOT_OWNED_BY_TEXT:" + sourceGraphic.GetType().FullName, out diagnostic);
        }

        static bool PersistentAsset(UnityEngine.Object value, out string guid, out long localFileId)
        {
            return AssetIdentity(value, out guid, out localFileId) &&
                !String.IsNullOrWhiteSpace(AssetDatabase.GetAssetPath(value));
        }

        static bool TextureBelongsToSourceAsset(TMP_FontAsset font, TMP_SpriteAsset sprite, Texture texture)
        {
            if (texture == null) return false;
            var fontOwnsTexture = font != null && font.atlasTextures != null && font.atlasTextures.Any(atlas => atlas == texture);
            var spriteOwnsTexture = sprite != null && sprite.spriteSheet == texture;
            return fontOwnsTexture || spriteOwnsTexture;
        }

        public static bool PrepareSource(TMP_Text owner, string sourceComponentId, out string diagnostic)
        {
            diagnostic = null;
            if (owner == null || String.IsNullOrWhiteSpace(sourceComponentId))
                return Fail("TMP_SORT_SOURCE_OWNER_OR_ID_MISSING", out diagnostic);
            if (!(owner is TextMeshProUGUI))
                return Fail("TMP_SORT_SOURCE_OWNER_TYPE_UNSUPPORTED", out diagnostic);
            try
            {
                var outline = owner.GetComponent<NativeStaticTextOutline>();
                if (outline != null)
                {
                    if (outline.Target != owner)
                        return Fail("TMP_SORT_SOURCE_OUTLINE_OWNER_MISMATCH", out diagnostic);
                    // OnEnable schedules the driver's TMP repair for LateUpdate.
                    // Prefab capture/readback can ForceMeshUpdate before that
                    // frame callback, leaving a newly rebuilt fallback mesh
                    // with different padding from the persisted proxy. Run the
                    // driver's actual SDK lifecycle synchronously first; it
                    // reselects only registered, identity-matched material
                    // variants and reports the resulting material proof.
                    var outlineReadback = outline.RefreshNow();
                    if (outlineReadback == null || outlineReadback.status != "material_values_applied_and_read_back" ||
                        outlineReadback.faces == null || outlineReadback.faces.Length == 0 ||
                        outlineReadback.faces.Any(face => face == null || !face.materialValuesVerified))
                        return Fail("TMP_SORT_SOURCE_OUTLINE_INITIALIZATION_FAILED:" +
                            (outlineReadback == null ? "missing-readback" : outlineReadback.status + ":" +
                             String.Join("|", (outlineReadback.diagnostics ?? Array.Empty<string>()).Take(4))), out diagnostic);
                }
                owner.ForceMeshUpdate(true, true);
            }
            catch (Exception error) { return Fail("TMP_SORT_SOURCE_MESH_PREPARE_FAILED:" + error.GetType().Name, out diagnostic); }
            var info = owner.textInfo;
            if (info == null || info.materialCount <= 0 || info.meshInfo == null || info.meshInfo.Length < info.materialCount)
                return Fail("TMP_SORT_SOURCE_TEXTINFO_SLOTS_UNAVAILABLE", out diagnostic);
            for (var slot = 0; slot < info.materialCount; slot++)
                if (info.meshInfo[slot].mesh == null || info.meshInfo[slot].material == null)
                    return Fail("TMP_SORT_SOURCE_SLOT_INCOMPLETE:" + slot, out diagnostic);
            return true;
        }

        static bool ReadTextInfoSlotEvidence(TMP_Text owner, TMP_SubMeshUI generated, int materialSlot, TMP_FontAsset fontAsset,
            TMP_SpriteAsset spriteAsset, Material graphicMaterial, Material textInfoMaterial,
            out int characterCount, out int visibleCharacterCount, out string evidenceSha256,
            out string characterAssetEvidenceSha256, out string characterMaterialFingerprint, out string diagnostic)
        {
            characterCount = 0; visibleCharacterCount = 0; evidenceSha256 = null; characterAssetEvidenceSha256 = null;
            characterMaterialFingerprint = null; diagnostic = null;
            var info = owner == null ? null : owner.textInfo;
            if (info == null || info.characterInfo == null || graphicMaterial == null)
                return Fail("TMP_SORT_TEXTINFO_SLOT_EVIDENCE_INPUT_MISSING", out diagnostic);
            var graphicTexture = graphicMaterial.GetTexture(MainTex);
            var graphicMaterialFingerprint = MaterialFingerprint(graphicMaterial);
            var evidence = new StringBuilder();
            var characterAssetEvidence = new StringBuilder();
            var characterFingerprints = new SortedSet<string>(StringComparer.Ordinal);
            var materialConflictDetails = new List<string>();
            var firstCharacterMaterialFingerprint = (string)null;
            Material firstCharacterMaterial = null;
            bool destroyedCharacterMaterialReference = false, unassignedCharacterMaterialReference = false;
            int destroyedCharacterMaterialCount = 0, unassignedCharacterMaterialCount = 0;
            bool nonCacheMaterialConflict = false;
            bool outlinedFallbackRelationVerified = false;
            bool fontVerified = true, atlasVerified = true, materialVerified = true;
            int visible = 0;
            for (var index = 0; index < info.characterCount; index++)
            {
                var character = info.characterInfo[index];
                if (character.materialReferenceIndex != materialSlot) continue;
                characterCount++;
                if (characterCount == 1) firstCharacterMaterial = character.material;
                var isSpriteCharacter = character.elementType == TMP_TextElementType.Sprite;
                var expectedAsset = isSpriteCharacter ? (UnityEngine.Object)spriteAsset : fontAsset;
                var characterAsset = character.textElement == null ? null : character.textElement.textAsset;
                var typedAssetMatches = expectedAsset != null && characterAsset == expectedAsset &&
                    (isSpriteCharacter ? spriteAsset != null : fontAsset != null && character.fontAsset == fontAsset);
                fontVerified &= typedAssetMatches;
                int atlasIndex = -1;
                Texture characterAtlas = null;
                if (character.textElement != null && character.textElement.glyph != null)
                    atlasIndex = character.alternativeGlyph != null
                        ? character.alternativeGlyph.atlasIndex : character.textElement.glyph.atlasIndex;
                if (isSpriteCharacter && spriteAsset != null)
                {
                    characterAtlas = spriteAsset.spriteSheet;
                    atlasIndex = 0;
                }
                else if (fontAsset != null && fontAsset.atlasTextures != null && atlasIndex >= 0 &&
                         atlasIndex < fontAsset.atlasTextures.Length)
                    characterAtlas = fontAsset.atlasTextures[atlasIndex];
                if (character.isVisible) atlasVerified &= characterAtlas != null && characterAtlas == graphicTexture;

                string perCharacterMaterialFingerprint = null;
                if (character.material != null)
                {
                    perCharacterMaterialFingerprint = MaterialFingerprint(character.material);
                    if (String.IsNullOrEmpty(perCharacterMaterialFingerprint))
                    {
                        materialVerified = false;
                        nonCacheMaterialConflict = true;
                        materialConflictDetails.Add("characterMaterialFingerprintUnavailable:" + index);
                    }
                    if (character.material.shader != graphicMaterial.shader)
                    {
                        materialVerified = false;
                        nonCacheMaterialConflict = true;
                        materialConflictDetails.Add("characterShaderDiffersFromGraphic:" + index + ":" +
                            ObjectIdentitySummary(character.material.shader) + "!=" + ObjectIdentitySummary(graphicMaterial.shader));
                    }
                    var characterTexture = character.material.GetTexture(MainTex);
                    if (character.isVisible && characterTexture != characterAtlas)
                    {
                        materialVerified = false;
                        nonCacheMaterialConflict = true;
                        materialConflictDetails.Add("characterMainTextureDiffersFromTypedAtlas:" + index + ":" +
                            ObjectIdentitySummary(characterTexture) + "!=" + ObjectIdentitySummary(characterAtlas));
                    }
                    if (textInfoMaterial != null && MaterialFingerprint(textInfoMaterial) != perCharacterMaterialFingerprint)
                    {
                        materialVerified = false;
                        nonCacheMaterialConflict = true;
                        materialConflictDetails.Add("characterMaterialDiffersFromTextInfoSlot:" + index + ":" +
                            (perCharacterMaterialFingerprint ?? "missing") + "!=" +
                            (MaterialFingerprint(textInfoMaterial) ?? "missing") + ";delta=" +
                            MaterialFingerprintDelta(character.material, textInfoMaterial));
                    }
                    if (firstCharacterMaterialFingerprint == null)
                    {
                        firstCharacterMaterialFingerprint = perCharacterMaterialFingerprint;
                    }
                    else if (firstCharacterMaterialFingerprint != perCharacterMaterialFingerprint)
                    {
                        materialVerified = false;
                        nonCacheMaterialConflict = true;
                        materialConflictDetails.Add("mixedCharacterMaterialsInSlot:" + index + ":" +
                            firstCharacterMaterialFingerprint + "!=" + (perCharacterMaterialFingerprint ?? "missing"));
                    }
                    if (!String.IsNullOrEmpty(perCharacterMaterialFingerprint)) characterFingerprints.Add(perCharacterMaterialFingerprint);
                }
                else if (character.isVisible)
                {
                    materialVerified = false;
                    var managedNull = ReferenceEquals(character.material, null);
                    destroyedCharacterMaterialReference |= !managedNull;
                    unassignedCharacterMaterialReference |= managedNull;
                    if (managedNull) unassignedCharacterMaterialCount++;
                    else destroyedCharacterMaterialCount++;
                    materialConflictDetails.Add((managedNull ? "characterMaterialUnassigned:" : "characterMaterialUnityDestroyed:") +
                        index + ":state=" + MaterialCacheState(character.material));
                }

                if (character.isVisible) visible++;
                uint unicode = character.textElement == null ? character.character : character.textElement.unicode;
                evidence.Append(index).Append(':').Append(unicode).Append(':').Append(character.materialReferenceIndex).Append(':')
                    .Append(isSpriteCharacter ? "sprite" : "font").Append(':')
                    .Append(AssetIdentity(expectedAsset, out var assetGuid, out var assetFileId) ? assetGuid + ":" + assetFileId : "missing-asset-id")
                    .Append(':').Append(atlasIndex).Append(':')
                    .Append(AssetIdentity(characterAtlas, out var atlasGuid, out var atlasFileId) ? atlasGuid + ":" + atlasFileId : "missing-atlas-id")
                    .Append(':').Append(perCharacterMaterialFingerprint ?? "missing-character-material").Append(';');
                characterAssetEvidence.Append(index).Append(':').Append(unicode).Append(':')
                    .Append(character.materialReferenceIndex).Append(':').Append(isSpriteCharacter ? "sprite" : "font").Append(':')
                    .Append(AssetIdentity(expectedAsset, out var stableAssetGuid, out var stableAssetFileId)
                        ? stableAssetGuid + ":" + stableAssetFileId : "missing-asset-id")
                    .Append(':').Append(atlasIndex).Append(':')
                    .Append(AssetIdentity(characterAtlas, out var stableAtlasGuid, out var stableAtlasFileId)
                        ? stableAtlasGuid + ":" + stableAtlasFileId : "missing-atlas-id")
                    .Append(':').Append(character.isVisible).Append(';');
            }
            visibleCharacterCount = visible;
            var slotMaterialManagedNull = ReferenceEquals(textInfoMaterial, null);
            var slotMaterialDestroyedReference = !slotMaterialManagedNull && textInfoMaterial == null;
            if (materialVerified == false && destroyedCharacterMaterialReference && !unassignedCharacterMaterialReference &&
                slotMaterialDestroyedReference && !nonCacheMaterialConflict)
            {
                var outlineDriver = owner.GetComponent<NativeStaticTextOutline>();
                string reconstructionDiagnostic = "outline fallback proof unavailable";
                string reconstructedCacheFingerprint;
                if (outlineDriver != null && spriteAsset == null && fontAsset != null &&
                    VerifyOutlinedFallbackMaterial(owner, generated, fontAsset, graphicMaterial, textInfoMaterial,
                        firstCharacterMaterial, true, out reconstructedCacheFingerprint, out reconstructionDiagnostic))
                {
                    materialVerified = true;
                    firstCharacterMaterialFingerprint = reconstructedCacheFingerprint;
                    outlinedFallbackRelationVerified = true;
                    materialConflictDetails.Add("destroyedTmpCacheReconstructedFromTypedFallbackAndOutlineProof");
                }
                else if (outlineDriver != null && fontAsset != null && spriteAsset == null)
                    diagnostic = "TMP_SORT_DESTROYED_CACHE_MATERIAL_RECONSTRUCTION_FAILED:" + reconstructionDiagnostic;
            }
            if (characterCount == 0 || visibleCharacterCount == 0)
                return Fail("TMP_SORT_TEXTINFO_SLOT_HAS_NO_VISIBLE_CHARACTER_REFERENCES:" + materialSlot +
                    ":characters=" + characterCount + ":visible=" + visibleCharacterCount, out diagnostic);
            if (materialVerified && firstCharacterMaterialFingerprint != graphicMaterialFingerprint &&
                !outlinedFallbackRelationVerified)
            {
                var outlineDriver = owner.GetComponent<NativeStaticTextOutline>();
                string outlineMaterialDiagnostic = null;
                string verifiedCacheFingerprint;
                var outlineRelationVerified = outlineDriver != null && spriteAsset == null && fontAsset != null &&
                    VerifyOutlinedFallbackMaterial(owner, generated, fontAsset, graphicMaterial, textInfoMaterial,
                        firstCharacterMaterial, false, out verifiedCacheFingerprint, out outlineMaterialDiagnostic);
                if (!outlineRelationVerified)
                {
                    materialVerified = false;
                    if (outlineDriver != null && fontAsset != null && spriteAsset == null)
                        diagnostic = "TMP_SORT_TEXTINFO_OUTLINE_MATERIAL_RELATION_UNPROVEN:" + materialSlot + ":" + outlineMaterialDiagnostic;
                    else materialConflictDetails.Add("characterCacheFingerprintDiffersFromGraphicWithoutProvenOutline:" +
                        (firstCharacterMaterialFingerprint ?? "missing") + "!=" + (graphicMaterialFingerprint ?? "missing"));
                }
            }
            if (!fontVerified || !atlasVerified || !materialVerified || String.IsNullOrEmpty(graphicMaterialFingerprint))
                return Fail("TMP_SORT_TEXTINFO_SLOT_CHARACTER_ASSET_MATERIAL_OR_ATLAS_CONFLICT:" + materialSlot +
                    ":font=" + fontVerified + ":atlas=" + atlasVerified + ":characterMaterial=" + materialVerified +
                    ":sourceMaterial=" + (graphicMaterialFingerprint ?? "missing") +
                    ":cachedCharacterMaterial=" + (firstCharacterMaterialFingerprint ?? "missing") +
                    ":cachedCharacterMaterialState=" + MaterialCacheState(firstCharacterMaterial) +
                    ":slotCacheMaterial=" + (textInfoMaterial == null ? "missing" : MaterialFingerprint(textInfoMaterial)) +
                    ":slotCacheMaterialState=" + MaterialCacheState(textInfoMaterial) +
                    ":destroyedCacheRefs=" + destroyedCharacterMaterialReference + "/" + slotMaterialDestroyedReference +
                    ":unassignedCacheRefs=" + unassignedCharacterMaterialReference + "/" + slotMaterialManagedNull +
                    ":destroyedCharacterMaterialCount=" + destroyedCharacterMaterialCount +
                    ":unassignedCharacterMaterialCount=" + unassignedCharacterMaterialCount +
                    ":materialRelation=" + (diagnostic ?? "direct-equality") +
                    ":materialSubchecks=" + String.Join("|", materialConflictDetails.Take(8)), out diagnostic);
            characterMaterialFingerprint = firstCharacterMaterialFingerprint;
            evidenceSha256 = HashText(evidence.ToString());
            characterAssetEvidenceSha256 = HashText(characterAssetEvidence.ToString());
            return !String.IsNullOrEmpty(evidenceSha256) || Fail("TMP_SORT_TEXTINFO_SLOT_EVIDENCE_HASH_MISSING", out diagnostic);
        }

        static bool VerifyOutlinedFallbackMaterial(TMP_Text owner, TMP_SubMeshUI generated, TMP_FontAsset fontAsset,
            Material graphicMaterial, Material textInfoMaterial, Material characterMaterial,
            bool destroyedCacheReferences, out string cacheMaterialFingerprint, out string diagnostic)
        {
            diagnostic = null; cacheMaterialFingerprint = null;
            var outline = owner == null ? null : owner.GetComponent<NativeStaticTextOutline>();
            if (outline == null || generated == null || generated.textComponent != owner ||
                generated.fontAsset != fontAsset || fontAsset == owner.font || graphicMaterial == null ||
                owner.fontSharedMaterial == null ||
                generated.fallbackSourceMaterial != owner.fontSharedMaterial ||
                generated.fallbackMaterial != graphicMaterial || generated.sharedMaterial != graphicMaterial)
            {
                diagnostic = "fallbackOwnerOrTypedReferencesMismatch;generated=" + ObjectIdentitySummary(generated) +
                    ";generatedFont=" + ObjectIdentitySummary(generated == null ? null : generated.fontAsset) +
                    ";outline=" + (outline != null) + ";fallbackSourceMatchesOwner=" +
                    (generated != null && generated.fallbackSourceMaterial == (owner == null ? null : owner.fontSharedMaterial)) +
                    ";fallbackMaterialMatchesGraphic=" + (generated != null && generated.fallbackMaterial == graphicMaterial) +
                    ";sharedMaterialMatchesGraphic=" + (generated != null && generated.sharedMaterial == graphicMaterial);
                return false;
            }
            var atlas = graphicMaterial.GetTexture(MainTex);
            if (fontAsset.atlasTextures == null)
            {
                diagnostic = "fallbackFontAtlasArrayMissing";
                return false;
            }
            var atlasIndexes = Enumerable.Range(0, fontAsset.atlasTextures.Length)
                .Where(index => fontAsset.atlasTextures[index] == atlas).ToArray();
            if (atlasIndexes.Length != 1)
            {
                diagnostic = "fallbackAtlasIndexNotUnique:" + atlasIndexes.Length + ";atlas=" + ObjectIdentitySummary(atlas);
                return false;
            }
            Material expectedTextInfoMaterial = null;
            Material expectedOutlineBase = null;
            Material expectedStyledMaterial = null;
            try
            {
                // Reproduce the pinned UGUI TMP_TextProcessing fallback path from
                // TMP_MaterialManager.GetFallbackMaterial and its multi-atlas
                // overload. The live TMP cache may have been destroyed by a
                // generated submesh releasing its last fallback reference.
                expectedTextInfoMaterial = DeriveTmpFallbackMaterial(owner.fontSharedMaterial, fontAsset,
                    atlasIndexes[0], TMP_Settings.matchMaterialPreset);
                if (expectedTextInfoMaterial == null)
                {
                    diagnostic = "pinnedTmpFallbackMaterialMissing";
                    return false;
                }
                // TMP_SubMeshUI.SetSharedMaterial recalculates and stores the
                // padding ratios on the parser's raw fallback material before
                // NativeStaticTextOutline replaces the live child material.
                // Reproduce that pinned SDK mutation on our disposable clone so
                // the cache fingerprint is compared at the same lifecycle point.
                TMPro.ShaderUtilities.GetPadding(expectedTextInfoMaterial, owner.extraPadding, owner.isUsingBold);
                var expectedTextFingerprint = MaterialFingerprint(expectedTextInfoMaterial);
                var characterFingerprint = characterMaterial == null ? null : MaterialFingerprint(characterMaterial);
                var slotFingerprint = textInfoMaterial == null ? null : MaterialFingerprint(textInfoMaterial);
                if (!destroyedCacheReferences && (String.IsNullOrEmpty(expectedTextFingerprint) ||
                    characterFingerprint != expectedTextFingerprint ||
                    textInfoMaterial != null && slotFingerprint != expectedTextFingerprint))
                {
                    diagnostic = "pinnedTmpCacheMaterialMismatch;algorithm=" +
                        (TMP_Settings.matchMaterialPreset ? "GetFallbackMaterial(owner,font)" : "fallbackFont.material") +
                        (atlasIndexes[0] > 0 ? "+GetFallbackMaterial(font,material,atlasIndex)" : String.Empty) +
                        ";atlasIndex=" + atlasIndexes[0] + ";expected=" + (expectedTextFingerprint ?? "missing") +
                        ";character=" + (characterFingerprint ?? "missing") + ";slot=" + (slotFingerprint ?? "missing") +
                        ";characterState=" + MaterialCacheState(characterMaterial) + ";slotState=" + MaterialCacheState(textInfoMaterial) +
                        ";characterDelta=" + MaterialFingerprintDelta(expectedTextInfoMaterial, characterMaterial) +
                        ";slotDelta=" + (textInfoMaterial == null ? "slotCacheNull" : MaterialFingerprintDelta(expectedTextInfoMaterial, textInfoMaterial));
                    return false;
                }
                if (destroyedCacheReferences)
                {
                    if (!CacheRefIsDestroyed(characterMaterial) &&
                        (String.IsNullOrEmpty(characterFingerprint) || characterFingerprint != expectedTextFingerprint) ||
                        !CacheRefIsDestroyed(textInfoMaterial) && !ReferenceEquals(textInfoMaterial, null) &&
                        (String.IsNullOrEmpty(slotFingerprint) || slotFingerprint != expectedTextFingerprint))
                    {
                        diagnostic = "destroyedCacheFallbackHasLiveConflictingCache;expected=" + expectedTextFingerprint +
                            ";characterState=" + MaterialCacheState(characterMaterial) +
                            ";slotState=" + MaterialCacheState(textInfoMaterial) +
                            ";characterDelta=" + MaterialFingerprintDelta(expectedTextInfoMaterial, characterMaterial) +
                            ";slotDelta=" + MaterialFingerprintDelta(expectedTextInfoMaterial, textInfoMaterial);
                        return false;
                    }
                }
                // NativeStaticTextOutline.Apply always asks TMP for the primary
                // material preset fallback, independently of the parser cache's
                // matchMaterialPreset switch, then derives its outline variant.
                expectedOutlineBase = DeriveTmpFallbackMaterial(owner.fontSharedMaterial, fontAsset, 0, true);
                expectedStyledMaterial = new Material(expectedOutlineBase) {
                    name = expectedOutlineBase.name + " [outline-proof]", hideFlags = HideFlags.HideAndDontSave,
                };
                if (!outline.ConfigureCaptureCandidate(expectedStyledMaterial, fontAsset, owner.fontSize, out var styleDiagnostic))
                {
                    diagnostic = "nativeOutlineCandidateDerivationFailed:" + styleDiagnostic;
                    return false;
                }
                TMPro.ShaderUtilities.GetPadding(expectedStyledMaterial, owner.extraPadding, owner.isUsingBold);
                var expectedStyledFingerprint = MaterialFingerprint(expectedStyledMaterial);
                var liveFingerprint = MaterialFingerprint(graphicMaterial);
                if (String.IsNullOrEmpty(expectedStyledFingerprint) || expectedStyledFingerprint != liveFingerprint)
                {
                    diagnostic = "nativeOutlineMaterialDiffersFromSdkDerivation;expected=" +
                        (expectedStyledFingerprint ?? "missing") + ";live=" + (liveFingerprint ?? "missing") +
                        ";delta=" + MaterialFingerprintDelta(expectedStyledMaterial, graphicMaterial);
                    return false;
                }
                cacheMaterialFingerprint = expectedTextFingerprint;
                return true;
            }
            catch (Exception error)
            {
                diagnostic = "outlineMaterialProofException:" + error.GetType().Name + ":" + error.Message;
                return false;
            }
            finally
            {
                if (expectedStyledMaterial != null) UnityEngine.Object.DestroyImmediate(expectedStyledMaterial);
                if (expectedOutlineBase != null) UnityEngine.Object.DestroyImmediate(expectedOutlineBase);
                if (expectedTextInfoMaterial != null) UnityEngine.Object.DestroyImmediate(expectedTextInfoMaterial);
            }
        }

        static bool CacheRefIsDestroyed(Material material)
        {
            return !ReferenceEquals(material, null) && material == null;
        }

        static Material DeriveTmpFallbackMaterial(Material sourceMaterial, TMP_FontAsset targetFont, int atlasIndex,
            bool matchMaterialPreset)
        {
            if (sourceMaterial == null || targetFont == null || targetFont.material == null ||
                targetFont.atlasTextures == null || atlasIndex < 0 || atlasIndex >= targetFont.atlasTextures.Length ||
                targetFont.atlasTextures[atlasIndex] == null) return null;
            var targetMaterial = targetFont.material;
            Material material;
            if (!matchMaterialPreset)
            {
                material = new Material(targetMaterial);
            }
            else if (sourceMaterial.HasProperty(TMPro.ShaderUtilities.ID_GradientScale) &&
                     targetMaterial.HasProperty(TMPro.ShaderUtilities.ID_GradientScale))
            {
                material = new Material(sourceMaterial);
                var targetAtlas = targetMaterial.GetTexture(MainTex);
                material.SetTexture(MainTex, targetAtlas);
                material.SetFloat(TMPro.ShaderUtilities.ID_GradientScale,
                    targetMaterial.GetFloat(TMPro.ShaderUtilities.ID_GradientScale));
                material.SetFloat(TMPro.ShaderUtilities.ID_TextureWidth,
                    targetMaterial.GetFloat(TMPro.ShaderUtilities.ID_TextureWidth));
                material.SetFloat(TMPro.ShaderUtilities.ID_TextureHeight,
                    targetMaterial.GetFloat(TMPro.ShaderUtilities.ID_TextureHeight));
                material.SetFloat(TMPro.ShaderUtilities.ID_WeightNormal,
                    targetMaterial.GetFloat(TMPro.ShaderUtilities.ID_WeightNormal));
                material.SetFloat(TMPro.ShaderUtilities.ID_WeightBold,
                    targetMaterial.GetFloat(TMPro.ShaderUtilities.ID_WeightBold));
            }
            else
            {
                material = new Material(targetMaterial);
            }
            if (atlasIndex > 0)
            {
                var multiAtlasMaterial = new Material(material);
                multiAtlasMaterial.SetTexture(MainTex, targetFont.atlasTextures[atlasIndex]);
                UnityEngine.Object.DestroyImmediate(material);
                material = multiAtlasMaterial;
            }
            material.hideFlags = HideFlags.HideAndDontSave;
            return material;
        }

        /// <summary>
        /// Capture-only persistence for the material instance produced by the
        /// pinned NativeStaticTextOutline/TMP path. The live material is accepted
        /// only when its complete shader/property fingerprint equals a fresh
        /// derivation from the owner's persistent FontAsset material and the
        /// exact serialized outline component bound to this source ID.
        /// </summary>
        public static bool CaptureOwnerFontMaterial(TMP_Text owner, string sourceComponentId,
            string persistentAssetPath, out Material persistentMaterial,
            out OwnerFontStyleDescriptor descriptor, out string diagnostic)
        {
            persistentMaterial = null; descriptor = null; diagnostic = null;
            if (owner == null || !(owner is TextMeshProUGUI) || String.IsNullOrWhiteSpace(sourceComponentId) || owner.font == null)
                return Fail("TMP_SORT_OWNER_STYLE_INPUT_INCOMPLETE", out diagnostic);
            var outline = owner.GetComponent<NativeStaticTextOutline>();
            if (outline == null || outline.Target != owner)
                return Fail("TMP_SORT_OWNER_STYLE_COMPONENT_NOT_BOUND", out diagnostic);
            // The caller resolved this exact owner from sourceNodes and passed
            // the corresponding source component ID. The outline's
            // diagnosticSourceLabelId is nonserialized template history and can
            // name a different occurrence when Unity expands nested prefab
            // instances; it is not source identity. Bind the style contract to
            // this owner and caller ID in the descriptor below, and prove the
            // live material from this owner's font asset and serialized style.
            var sourceFont = owner.font;
            var sourceMaterial = sourceFont.material;
            if (!PersistentAsset(sourceFont, out var fontGuid, out var fontFileId) ||
                !PersistentAsset(sourceMaterial, out var sourceMaterialGuid, out var sourceMaterialFileId))
                return Fail("TMP_SORT_OWNER_STYLE_FONT_SOURCE_NOT_PERSISTENT", out diagnostic);
            var width = outline.SourceOutlineWidth;
            var color = outline.SourceOutlineColor;
            if (Single.IsNaN(width) || Single.IsInfinity(width) || width < 0f ||
                Single.IsNaN(owner.fontSize) || Single.IsInfinity(owner.fontSize) || owner.fontSize <= 0f ||
                !sourceMaterial.HasProperty("_GradientScale") || !sourceMaterial.HasProperty("_OutlineWidth") ||
                !sourceMaterial.HasProperty("_OutlineColor"))
                return Fail("TMP_SORT_OWNER_STYLE_SOURCE_METRICS_OR_SHADER_INVALID", out diagnostic);
            var gradient = sourceMaterial.GetFloat("_GradientScale");
            var pointSize = sourceFont.faceInfo.pointSize;
            if (Single.IsNaN(gradient) || Single.IsInfinity(gradient) || gradient <= 1f ||
                Single.IsNaN(pointSize) || Single.IsInfinity(pointSize) || pointSize <= 0f)
                return Fail("TMP_SORT_OWNER_STYLE_FONT_METRICS_INVALID", out diagnostic);
            var outlineWidth = width * pointSize / owner.fontSize / (gradient - 1f);
            if (Single.IsNaN(outlineWidth) || Single.IsInfinity(outlineWidth))
                return Fail("TMP_SORT_OWNER_STYLE_DERIVED_WIDTH_INVALID", out diagnostic);

            var expected = new Material(sourceMaterial) { hideFlags = HideFlags.HideAndDontSave };
            if (!outline.ConfigureCaptureCandidate(expected, sourceFont, owner.fontSize, out var derivationDiagnostic))
            {
                UnityEngine.Object.DestroyImmediate(expected);
                return Fail("TMP_SORT_OWNER_STYLE_FONT_ASSET_DERIVATION_FAILED:" + derivationDiagnostic, out diagnostic);
            }
            // The native driver calls UpdateMeshPadding after configuring a
            // material. TMP's padding calculation also updates _ScaleRatioA/B/C
            // from outline, softness, weight and shader keywords; reproduce that
            // SDK step on the temporary candidate before comparing fingerprints.
            TMPro.ShaderUtilities.GetPadding(expected, owner.extraPadding, owner.isUsingBold);
            var expectedFingerprint = MaterialFingerprint(expected);
            var liveMaterial = owner.fontSharedMaterial;
            var liveFingerprint = MaterialFingerprint(liveMaterial);
            if (String.IsNullOrEmpty(expectedFingerprint) || expectedFingerprint != liveFingerprint)
            {
                var delta = MaterialFingerprintDelta(expected, liveMaterial);
                var expectedHash = String.IsNullOrEmpty(expectedFingerprint) ? "unavailable" : expectedFingerprint.Substring(0, Math.Min(12, expectedFingerprint.Length));
                var liveHash = String.IsNullOrEmpty(liveFingerprint) ? "unavailable" : liveFingerprint.Substring(0, Math.Min(12, liveFingerprint.Length));
                UnityEngine.Object.DestroyImmediate(expected);
                return Fail("TMP_SORT_OWNER_STYLE_TRANSIENT_DIFFERS_FROM_FONT_ASSET_DERIVATION:expected=" + expectedHash +
                    ";actual=" + liveHash + ";delta=" + delta, out diagnostic);
            }

            if (!PersistentAssetPath(persistentAssetPath, out diagnostic))
            {
                UnityEngine.Object.DestroyImmediate(expected);
                return false;
            }
            var saved = AssetDatabase.LoadAssetAtPath<Material>(persistentAssetPath);
            if (saved == null)
            {
                if (File.Exists(persistentAssetPath))
                {
                    UnityEngine.Object.DestroyImmediate(expected);
                    return Fail("TMP_SORT_OWNER_STYLE_PATH_IS_OWNED_BY_NON_MATERIAL", out diagnostic);
                }
                expected.name = Path.GetFileNameWithoutExtension(persistentAssetPath);
                expected.hideFlags = HideFlags.None;
                try { AssetDatabase.CreateAsset(expected, persistentAssetPath); }
                catch (Exception error)
                {
                    UnityEngine.Object.DestroyImmediate(expected);
                    return Fail("TMP_SORT_OWNER_STYLE_CREATE_ASSET_FAILED:" + error.GetType().Name, out diagnostic);
                }
                saved = AssetDatabase.LoadAssetAtPath<Material>(persistentAssetPath);
            }
            else UnityEngine.Object.DestroyImmediate(expected);
            if (!PersistentAsset(saved, out _, out _) || MaterialFingerprint(saved) != expectedFingerprint)
                return Fail("TMP_SORT_OWNER_STYLE_PERSISTED_MATERIAL_MISMATCH", out diagnostic);

            owner.fontSharedMaterial = saved;
            owner.UpdateMeshPadding();
            EditorUtility.SetDirty(owner);
            PrefabUtility.RecordPrefabInstancePropertyModifications(owner);
            if (owner.fontSharedMaterial != saved || MaterialFingerprint(owner.fontSharedMaterial) != expectedFingerprint)
                return Fail("TMP_SORT_OWNER_STYLE_ASSIGNMENT_READBACK_MISMATCH", out diagnostic);
            var sourceAtlas = sourceMaterial.GetTexture(MainTex);
            string registerDiagnostic = null;
            if (!PersistentAsset(sourceAtlas, out _, out _))
                return Fail("TMP_SORT_OWNER_STYLE_PERSISTENT_VARIANT_ATLAS_NOT_PERSISTENT", out diagnostic);
            if (!outline.RegisterPersistentMaterialVariant(sourceFont, saved, null, owner.fontSize, sourceAtlas, out registerDiagnostic))
                return Fail("TMP_SORT_OWNER_STYLE_PERSISTENT_VARIANT_REGISTRATION_FAILED:" + registerDiagnostic, out diagnostic);
            EditorUtility.SetDirty(outline);
            PrefabUtility.RecordPrefabInstancePropertyModifications(outline);
            descriptor = new OwnerFontStyleDescriptor {
                profile = "native-static-text-outline-font-material-v1",
                sourceComponentId = sourceComponentId,
                outlineWidth = width,
                outlineColor = color,
                sourceFontAsset = sourceFont,
                sourceFontAssetGuid = fontGuid,
                sourceFontAssetLocalFileId = fontFileId,
                sourceFontMaterial = sourceMaterial,
                sourceFontMaterialGuid = sourceMaterialGuid,
                sourceFontMaterialLocalFileId = sourceMaterialFileId,
                sourceFontMaterialFingerprint = MaterialFingerprint(sourceMaterial),
            };
            persistentMaterial = saved;
            return true;
        }

        public static bool TryResolveSlot(TMP_Text owner, TMP_SubMeshUI generated, int expectedSlot,
            string sourceComponentId, out TextSlotBinding binding, out string diagnostic)
        {
            return TryResolveSlot(owner, generated, expectedSlot, sourceComponentId, null, null, out binding, out diagnostic);
        }

        static bool TryResolveSlot(TMP_Text owner, TMP_SubMeshUI generated, int expectedSlot,
            string sourceComponentId, NativeStaticSortQueueProxyPresenter presenter,
            NativeStaticSortTextSource identity, out TextSlotBinding binding, out string diagnostic)
        {
            binding = null; diagnostic = null;
            if (owner == null || expectedSlot < 0 || !(owner is TextMeshProUGUI))
                return Fail("TMP_SORT_SLOT_OWNER_OR_INDEX_INVALID", out diagnostic);
            var info = owner.textInfo;
            if (info == null || info.meshInfo == null || expectedSlot >= info.materialCount || expectedSlot >= info.meshInfo.Length)
                return Fail("TMP_SORT_SLOT_OUT_OF_RANGE:" + expectedSlot, out diagnostic);

            Graphic sourceGraphic;
            Material sourceMaterial;
            TMP_FontAsset fontAsset;
            TMP_SpriteAsset spriteAsset;
            if (expectedSlot == 0)
            {
                if (generated != null) return Fail("TMP_SORT_MAIN_SLOT_HAS_GENERATED_CHILD", out diagnostic);
                sourceGraphic = owner as Graphic;
                sourceMaterial = owner.fontSharedMaterial;
                fontAsset = owner.font;
                spriteAsset = null;
            }
            else
            {
                if (generated == null || generated.textComponent != owner || generated.transform.parent != owner.transform ||
                    !TryMaterialSlot(generated, out var generatedSlot) || generatedSlot != expectedSlot)
                    return Fail("TMP_SORT_GENERATED_SLOT_OWNER_OR_INDEX_MISMATCH:" + expectedSlot, out diagnostic);
                sourceGraphic = generated;
                sourceMaterial = generated.sharedMaterial;
                spriteAsset = generated.spriteAsset;
                fontAsset = spriteAsset == null ? generated.fontAsset : null;
            }
            var slotInfo = info.meshInfo[expectedSlot];
            var sourceMesh = slotInfo.mesh;
            if (sourceGraphic == null || sourceMaterial == null || sourceMesh == null || sourceMesh.vertexCount <= 0)
            {
                var mismatchCanvasMesh = sourceGraphic == null || sourceGraphic.canvasRenderer == null ? null : sourceGraphic.canvasRenderer.GetMesh();
                return Fail("TMP_SORT_SLOT_SOURCE_MATERIAL_OR_MESH_MISMATCH:" + expectedSlot +
                    ";graphicNull=" + (sourceGraphic == null) +
                    ";sharedMaterialNull=" + (sourceMaterial == null) +
                    ";slotMaterialNull=" + (slotInfo.material == null) +
                    ";materialRefEqual=" + (slotInfo.material == sourceMaterial) +
                    ";slotMaterial=" + ObjectIdentitySummary(slotInfo.material) +
                    ";sharedMaterial=" + ObjectIdentitySummary(sourceMaterial) +
                    ";slotMeshNull=" + (sourceMesh == null) +
                    ";slotMeshVertices=" + (sourceMesh == null ? -1 : sourceMesh.vertexCount) +
                    ";canvasMeshNull=" + (mismatchCanvasMesh == null) +
                    ";canvasMeshVertices=" + (mismatchCanvasMesh == null ? -1 : mismatchCanvasMesh.vertexCount) +
                    ";meshFingerprintEqual=" + (mismatchCanvasMesh != null && sourceMesh != null && MeshFingerprint(mismatchCanvasMesh) == MeshFingerprint(sourceMesh)), out diagnostic);
            }
            var sourceTexture = sourceMaterial.GetTexture(MainTex);
            if (!ReadTextInfoSlotEvidence(owner, generated, expectedSlot, fontAsset, spriteAsset, sourceMaterial, slotInfo.material,
                out var textInfoCharacterCount, out var textInfoVisibleCharacterCount,
                out var textInfoCharacterEvidenceSha256, out var textInfoCharacterAssetEvidenceSha256,
                out var textInfoCharacterMaterialFingerprint,
                out var textInfoEvidenceDiagnostic))
                return Fail("TMP_SORT_SLOT_TEXTINFO_CHARACTER_EVIDENCE_FAILED:" + expectedSlot + ";diagnostic=" +
                    textInfoEvidenceDiagnostic, out diagnostic);
            var slotMaterialFingerprint = slotInfo.material == null ? null : MaterialFingerprint(slotInfo.material);
            var characterMaterialMatchesSlotInfo = slotInfo.material == null ||
                !String.IsNullOrEmpty(slotMaterialFingerprint) && slotMaterialFingerprint == textInfoCharacterMaterialFingerprint;
            if (!characterMaterialMatchesSlotInfo)
                return Fail("TMP_SORT_SLOT_TEXTINFO_MATERIAL_DOES_NOT_MATCH_CHARACTER_REFERENCE:" + expectedSlot, out diagnostic);
            var canvasRenderer = sourceGraphic.canvasRenderer;
            var rendererMaterialBeforeInitialization = canvasRenderer == null || canvasRenderer.materialCount == 0
                ? null : canvasRenderer.GetMaterial(0);
            var materialInitializationAttempted = false;
            // Force the exact Graphic's normal pre-render material binding when
            // TMP has produced textInfo/mesh but the CanvasUpdateRegistry has
            // not yet populated this CanvasRenderer. This is not a fallback to
            // Graphic.sharedMaterial: the material is read back from the real
            // renderer after Rebuild and must still match the typed source slot.
            // Do not rebuild a culled or inactive source, and do not issue a
            // global Canvas rebuild here (which can invalidate other renderers).
            if (canvasRenderer != null && (canvasRenderer.materialCount == 0 || rendererMaterialBeforeInitialization == null) && !canvasRenderer.cull &&
                sourceGraphic.isActiveAndEnabled)
            {
                materialInitializationAttempted = true;
                try
                {
                    sourceGraphic.SetMaterialDirty();
                    sourceGraphic.Rebuild(CanvasUpdate.PreRender);
                }
                catch (Exception error)
                {
                    return Fail("TMP_SORT_SLOT_CANVAS_RENDERER_MATERIAL_INITIALIZATION_FAILED:" + expectedSlot +
                        ";error=" + error.GetType().Name, out diagnostic);
                }
            }
            // A suppressed CanvasRenderer does not expose its material. Do not
            // query it after the exact presenter has culled this source; use
            // the authored Graphic material and the presenter scope proof below.
            var presenterSuppressedRenderer = presenter != null && canvasRenderer != null && canvasRenderer.cull;
            var rendererMaterial = canvasRenderer == null || presenterSuppressedRenderer || canvasRenderer.materialCount == 0
                ? null : canvasRenderer.GetMaterial();
            var directRendererMaterialMatches = rendererMaterial != null && (rendererMaterial == sourceMaterial ||
                MaterialFingerprint(rendererMaterial) == MaterialFingerprint(sourceMaterial));
            string stencilMaterialDiagnostic = null;
            var rendererStencilMaterialMatches = !directRendererMaterialMatches && rendererMaterial != null &&
                VerifyMaskStencilMaterial(sourceGraphic, sourceMaterial, rendererMaterial, identity, presenter,
                    out stencilMaterialDiagnostic);
            var rendererMaterialMatches = directRendererMaterialMatches || rendererStencilMaterialMatches;
            string suppressionDiagnostic = null;
            var sourceRectMaskCullVerified = false;
            var sourceCanvasCullBeforeCaptured = false;
            var sourceCanvasCullBeforeRuntime = false;
            var rendererSuppressionVerified = presenter != null && identity != null &&
                VerifyPresenterSuppression(presenter, identity, owner, sourceGraphic,
                    sourceComponentId, expectedSlot, sourceMaterial, out suppressionDiagnostic,
                    out sourceRectMaskCullVerified, out sourceCanvasCullBeforeCaptured, out sourceCanvasCullBeforeRuntime);
            if (presenter != null && !rendererSuppressionVerified)
                return Fail("TMP_SORT_PRESENTER_SOURCE_SCOPE_INVALID:" + expectedSlot + ";" + suppressionDiagnostic, out diagnostic);
            if (!rendererMaterialMatches && !(rendererMaterial == null && rendererSuppressionVerified))
            {
                var rendererDelta = "not_compared";
                try { rendererDelta = MaterialFingerprintDelta(rendererMaterial, sourceMaterial); }
                catch (Exception error) { rendererDelta = "diagnostic_failed:" + error.GetType().Name; }
                var rendererMeshAtMaterialCheck = canvasRenderer == null ? null : canvasRenderer.GetMesh();
                return Fail("TMP_SORT_SLOT_CANVAS_RENDERER_MATERIAL_MISMATCH:" + expectedSlot +
                    ";rendererMaterial=" + ObjectIdentitySummary(rendererMaterial) +
                    ";rendererMaterialBeforeInitialization=" + ObjectIdentitySummary(rendererMaterialBeforeInitialization) +
                    ";materialInitializationAttempted=" + materialInitializationAttempted +
                    ";graphicSharedMaterial=" + ObjectIdentitySummary(sourceMaterial) +
                    ";graphicSharedFingerprint=" + (MaterialFingerprint(sourceMaterial) ?? "missing") +
                    ";rendererMaterialCount=" + (canvasRenderer == null ? -1 : canvasRenderer.materialCount) +
                    ";rendererCull=" + (canvasRenderer != null && canvasRenderer.cull) +
                    ";graphicEnabled=" + sourceGraphic.enabled +
                    ";graphicActiveSelf=" + sourceGraphic.gameObject.activeSelf +
                    ";graphicActiveInHierarchy=" + sourceGraphic.gameObject.activeInHierarchy +
                    ";graphicColorAlpha=" + sourceGraphic.color.a.ToString("R", CultureInfo.InvariantCulture) +
                    ";rendererAlpha=" + (canvasRenderer == null ? -1f : canvasRenderer.GetAlpha()).ToString("R", CultureInfo.InvariantCulture) +
                    ";rendererInheritedAlpha=" + (canvasRenderer == null ? -1f : canvasRenderer.GetInheritedAlpha()).ToString("R", CultureInfo.InvariantCulture) +
                    ";sourceTextCharacters=" + textInfoCharacterCount + ";visibleTextCharacters=" + textInfoVisibleCharacterCount +
                    ";slotMeshVertices=" + (sourceMesh == null ? -1 : sourceMesh.vertexCount) +
                    ";slotMeshTriangles=" + MeshFirstSubmeshIndexCount(sourceMesh) +
                    ";slotMeshNondegenerate=" + MeshNonDegenerateTriangleCount(sourceMesh) +
                    ";rendererMeshVertices=" + (rendererMeshAtMaterialCheck == null ? -1 : rendererMeshAtMaterialCheck.vertexCount) +
                    ";rendererMeshTriangles=" + MeshFirstSubmeshIndexCount(rendererMeshAtMaterialCheck) +
                    ";rendererMeshNondegenerate=" + MeshNonDegenerateTriangleCount(rendererMeshAtMaterialCheck) +
                    ";slotMeshGeometry=" + MeshGeometrySummary(sourceMesh) +
                    ";rendererMeshGeometry=" + MeshGeometrySummary(rendererMeshAtMaterialCheck) +
                    ";slotMaterial=" + ObjectIdentitySummary(slotInfo.material) +
                    ";suppressionPresenter=" + (presenter != null) +
                    ";suppressionProof=" + rendererSuppressionVerified +
                    ";rendererStencilMaterialMatches=" + rendererStencilMaterialMatches +
                    ";stencilMaterialDiagnostic=" + (stencilMaterialDiagnostic ?? "not-evaluated") +
                    ";rendererDelta=" + rendererDelta, out diagnostic);
            }
            if (fontAsset == null && spriteAsset == null)
                return Fail("TMP_SORT_SLOT_FONT_OR_SPRITE_ASSET_MISSING:" + expectedSlot, out diagnostic);
            if (!PersistentAsset(fontAsset != null ? (UnityEngine.Object)fontAsset : spriteAsset, out var assetGuid, out var assetFileId))
                return Fail("TMP_SORT_SLOT_FONT_OR_SPRITE_ASSET_NOT_PERSISTENT:" + expectedSlot, out diagnostic);
            if (!TextureBelongsToSourceAsset(fontAsset, spriteAsset, sourceTexture))
                return Fail("TMP_SORT_SLOT_ATLAS_DOES_NOT_MATCH_SOURCE_ASSET:" + expectedSlot, out diagnostic);
            if (!PersistentAsset(sourceMaterial.shader, out var shaderGuid, out var shaderFileId) ||
                !PersistentAsset(sourceTexture, out var textureGuid, out var textureFileId))
                return Fail("TMP_SORT_SLOT_SHADER_OR_ATLAS_NOT_PERSISTENT:" + expectedSlot, out diagnostic);
            var materialPersistent = PersistentAsset(sourceMaterial, out var materialGuid, out var materialFileId);
            if (!materialPersistent) { materialGuid = null; materialFileId = 0; }
            var ownerFontMaterial = owner.fontSharedMaterial;
            string ownerFontMaterialGuid = null; long ownerFontMaterialFileId = 0;
            if (ownerFontMaterial == null || !PersistentAsset(ownerFontMaterial, out ownerFontMaterialGuid, out ownerFontMaterialFileId))
                return Fail("TMP_SORT_OWNER_FONT_SHARED_MATERIAL_NOT_PERSISTENT:" + expectedSlot, out diagnostic);
            var fallbackFontAsset = generated != null ? fontAsset : null;
            var fallbackFontMaterial = fallbackFontAsset == null ? null : fallbackFontAsset.material;
            string fallbackFontAssetGuid = null; long fallbackFontAssetFileId = 0;
            string fallbackFontMaterialGuid = null; long fallbackFontMaterialFileId = 0;
            string fallbackFontMaterialFingerprint = null;
            if (fallbackFontAsset != null && (!PersistentAsset(fallbackFontAsset, out fallbackFontAssetGuid, out fallbackFontAssetFileId) ||
                !PersistentAsset(fallbackFontMaterial, out fallbackFontMaterialGuid, out fallbackFontMaterialFileId)))
                return Fail("TMP_SORT_FALLBACK_FONT_ASSET_OR_MATERIAL_NOT_PERSISTENT:" + expectedSlot, out diagnostic);
            if (fallbackFontMaterial != null)
            {
                fallbackFontMaterialFingerprint = MaterialFingerprint(fallbackFontMaterial);
                if (String.IsNullOrEmpty(fallbackFontMaterialFingerprint))
                    return Fail("TMP_SORT_FALLBACK_FONT_MATERIAL_FINGERPRINT_UNAVAILABLE:" + expectedSlot, out diagnostic);
            }
            var outlineDriver = owner.GetComponent<NativeStaticTextOutline>();
            var persistentFallbackVariantRegistered = generated != null && fallbackFontAsset != null &&
                fallbackFontAsset != owner.font && outlineDriver != null && outlineDriver.Target == owner &&
                outlineDriver.IsPersistentMaterialVariantSelected(fallbackFontAsset, ownerFontMaterial,
                    sourceTexture, sourceMaterial) && generated.fallbackSourceMaterial == ownerFontMaterial &&
                generated.fallbackMaterial == sourceMaterial && generated.sharedMaterial == sourceMaterial;
            var canvasMesh = sourceGraphic.canvasRenderer == null ? null : sourceGraphic.canvasRenderer.GetMesh();
            var sourceMeshSha = MeshFingerprint(sourceMesh);
            if (canvasMesh == null || MeshFingerprint(canvasMesh) != sourceMeshSha)
                return Fail("TMP_SORT_SLOT_CANVAS_MESH_DIFFERS_FROM_TEXTINFO:" + expectedSlot, out diagnostic);
            var sourceMaterialFingerprint = MaterialFingerprint(sourceMaterial);
            if (String.IsNullOrEmpty(sourceMaterialFingerprint))
                return Fail("TMP_SORT_SLOT_TRANSIENT_MATERIAL_FINGERPRINT_UNAVAILABLE:" + expectedSlot, out diagnostic);
            var ownerFontMaterialFingerprint = ownerFontMaterial == null ? null : MaterialFingerprint(ownerFontMaterial);
            if (ownerFontMaterial != null && String.IsNullOrEmpty(ownerFontMaterialFingerprint))
                return Fail("TMP_SORT_OWNER_FONT_SHARED_MATERIAL_FINGERPRINT_UNAVAILABLE:" + expectedSlot, out diagnostic);
            binding = new TextSlotBinding { sourceComponentId = sourceComponentId, owner = owner,
                sourceGraphic = sourceGraphic, sourceMesh = sourceMesh, materialSlot = expectedSlot,
                generatedSubmesh = generated != null, sourceGraphicEnabled = sourceGraphic.enabled,
                sourceGraphicActiveSelf = sourceGraphic.gameObject.activeSelf,
                sourceMeshGeneratedByTmpVerified = canvasMesh != null && MeshFingerprint(canvasMesh) == sourceMeshSha,
                persistentFallbackVariantRegistered = persistentFallbackVariantRegistered,
                textInfoMaterialMissing = slotInfo.material == null,
                textInfoCharacterSlotVerified = true,
                textInfoCharacterMaterialVerified = true,
                textInfoFontAssetVerified = true,
                textInfoAtlasVerified = true,
                textInfoCharacterCount = textInfoCharacterCount,
                textInfoVisibleCharacterCount = textInfoVisibleCharacterCount,
                sourceTextSha256 = HashText(owner.text ?? String.Empty),
                textInfoCharacterEvidenceSha256 = textInfoCharacterEvidenceSha256,
                textInfoCharacterAssetEvidenceSha256 = textInfoCharacterAssetEvidenceSha256,
                textInfoCharacterMaterialFingerprint = textInfoCharacterMaterialFingerprint,
                fontAsset = fontAsset, spriteAsset = spriteAsset, sourceMaterial = sourceMaterial,
                ownerFontSharedMaterial = ownerFontMaterial, fallbackFontAsset = fallbackFontAsset,
                fallbackFontMaterial = fallbackFontMaterial, proxyMaterial = materialPersistent ? sourceMaterial : null,
                sourceTexture = sourceTexture,
                fontAssetGuid = fontAsset != null ? assetGuid : null,
                fontAssetLocalFileId = fontAsset != null ? assetFileId : 0,
                spriteAssetGuid = spriteAsset != null ? assetGuid : null,
                spriteAssetLocalFileId = spriteAsset != null ? assetFileId : 0,
                sourceMaterialGuid = materialGuid, sourceMaterialLocalFileId = materialFileId,
                sourceShaderGuid = shaderGuid, sourceShaderLocalFileId = shaderFileId,
                sourceTextureGuid = textureGuid, sourceTextureLocalFileId = textureFileId,
                sourceMeshSha256 = sourceMeshSha, sourceMaterialFingerprint = sourceMaterialFingerprint,
                ownerFontMaterialGuid = ownerFontMaterialGuid, ownerFontMaterialLocalFileId = ownerFontMaterialFileId,
                ownerFontMaterialFingerprint = ownerFontMaterialFingerprint,
                fallbackFontAssetGuid = fallbackFontAssetGuid, fallbackFontAssetLocalFileId = fallbackFontAssetFileId,
                fallbackFontMaterialGuid = fallbackFontMaterialGuid, fallbackFontMaterialLocalFileId = fallbackFontMaterialFileId,
                fallbackFontMaterialFingerprint = fallbackFontMaterialFingerprint };
            binding.sourceRendererSuppressionVerified = rendererSuppressionVerified;
            binding.sourceRectMaskCullVerified = sourceRectMaskCullVerified;
            binding.sourceCanvasCullBeforeCaptured = sourceCanvasCullBeforeCaptured;
            binding.sourceCanvasCullBeforeRuntime = sourceCanvasCullBeforeRuntime;
            if (materialPersistent)
            {
                binding.proxyMaterial = sourceMaterial;
                binding.proxyMaterialFingerprint = sourceMaterialFingerprint;
                binding.proxyMaterialGuid = materialGuid;
                binding.proxyMaterialLocalFileId = materialFileId;
            }
            return true;
        }

        static bool VerifyPresenterSuppression(NativeStaticSortQueueProxyPresenter presenter,
            NativeStaticSortTextSource identity, TMP_Text owner, Graphic sourceGraphic,
            string sourceComponentId, int materialSlot, Material sourceMaterial, out string diagnostic,
            out bool sourceRectMaskCullVerified, out bool sourceCanvasCullBeforeCaptured,
            out bool sourceCanvasCullBeforeRuntime)
        {
            diagnostic = null;
            sourceRectMaskCullVerified = false;
            sourceCanvasCullBeforeCaptured = false;
            sourceCanvasCullBeforeRuntime = false;
            var identityOwnerMatches = identity != null && owner != null && identity.sourceOwner == owner;
            var sourceIdMatches = identity != null && identity.sourceComponentId == sourceComponentId;
            var slotMatches = identity != null && identity.materialSlot == materialSlot;
            var presenterRootsValid = presenter != null && presenter.proxyRoot != null && presenter.sourceRoot != null;
            var presenterIsProxyRoot = presenterRootsValid && presenter.gameObject == presenter.proxyRoot;
            var rootsDistinct = presenterRootsValid && presenter.proxyRoot != presenter.sourceRoot;
            var graphicInSourceRoot = sourceGraphic != null && presenterRootsValid &&
                (sourceGraphic.transform == presenter.sourceRoot.transform || sourceGraphic.transform.IsChildOf(presenter.sourceRoot.transform));
            var graphicSlotTypeMatches = sourceGraphic != null && owner != null &&
                (materialSlot == 0 ? sourceGraphic == owner as Graphic :
                    sourceGraphic is TMP_SubMeshUI submesh && submesh.textComponent == owner);
            var graphicEnabled = sourceGraphic != null && sourceGraphic.enabled;
            var graphicActiveSelf = sourceGraphic != null && sourceGraphic.gameObject.activeSelf;
            var graphicActiveInHierarchy = sourceGraphic != null && sourceGraphic.gameObject.activeInHierarchy;
            var canvasRendererPresent = sourceGraphic != null && sourceGraphic.canvasRenderer != null;
            var canvasRendererCulled = canvasRendererPresent && sourceGraphic.canvasRenderer.cull;
            if (presenter == null || identity == null || owner == null || sourceGraphic == null || sourceMaterial == null ||
                !identityOwnerMatches || !sourceIdMatches || !slotMatches || !presenterRootsValid || !presenterIsProxyRoot ||
                !rootsDistinct || !graphicInSourceRoot || !graphicSlotTypeMatches || !graphicEnabled || !graphicActiveSelf ||
                !graphicActiveInHierarchy || !canvasRendererPresent || !canvasRendererCulled)
                return Fail("TMP_SORT_PRESENTER_SUPPRESSION_SCOPE_OR_SOURCE_STATE_INVALID:" + materialSlot +
                    ";presenterNull=" + (presenter == null) + ";identityNull=" + (identity == null) +
                    ";ownerNull=" + (owner == null) + ";sourceGraphicNull=" + (sourceGraphic == null) +
                    ";sourceMaterialNull=" + (sourceMaterial == null) + ";identityOwnerMatches=" + identityOwnerMatches +
                    ";sourceIdMatches=" + sourceIdMatches + ";slotMatches=" + slotMatches +
                    ";presenterRootsValid=" + presenterRootsValid + ";presenterIsProxyRoot=" + presenterIsProxyRoot +
                    ";rootsDistinct=" + rootsDistinct + ";graphicInSourceRoot=" + graphicInSourceRoot +
                    ";graphicSlotTypeMatches=" + graphicSlotTypeMatches + ";graphicEnabled=" + graphicEnabled +
                    ";graphicActiveSelf=" + graphicActiveSelf + ";graphicActiveInHierarchy=" + graphicActiveInHierarchy +
                    ";canvasRendererPresent=" + canvasRendererPresent + ";canvasRendererCulled=" + canvasRendererCulled, out diagnostic);

            var trackedGraphics = presenter.sourceGraphics ?? Array.Empty<Graphic>();
            var trackedBefore = presenter.sourceCullBefore ?? Array.Empty<bool>();
            var sourceIndexes = Enumerable.Range(0, Math.Min(trackedGraphics.Length, trackedBefore.Length))
                .Where(index => trackedGraphics[index] == sourceGraphic).ToArray();
            if (sourceIndexes.Length != 1)
                return Fail("TMP_SORT_PRESENTER_SUPPRESSION_SOURCE_CULL_PROOF_NOT_UNIQUE:" + materialSlot + ":" + sourceIndexes.Length, out diagnostic);

            var proxyGraphic = identity.GetComponent<NativeStaticSortQueueProxyGraphic>();
            var ownerGraphic = owner as Graphic;
            var bindings = (presenter.bindings ?? Array.Empty<ProxyGraphicBinding>())
                .Where(row => row != null && row.sourceGraphic == ownerGraphic &&
                    row.sourceCanvasRenderer == (ownerGraphic == null ? null : ownerGraphic.canvasRenderer) &&
                    row.sourceGraphicEnabled &&
                    (row.proxyGraphics ?? Array.Empty<NativeStaticSortQueueProxyGraphic>()).Contains(proxyGraphic)).ToArray();
            if (bindings.Length != 1)
                return Fail("TMP_SORT_PRESENTER_SUPPRESSION_BINDING_NOT_UNIQUE:" + materialSlot + ":" + bindings.Length, out diagnostic);
            var exactProxyBindings = (bindings[0].proxyGraphics ?? Array.Empty<NativeStaticSortQueueProxyGraphic>())
                .Where(proxy => proxy != null && proxy == proxyGraphic && proxy.sourceComponentId == sourceComponentId &&
                    proxy.sourceOwnerGraphic == ownerGraphic && proxy.sourceGraphic == ownerGraphic &&
                    proxy.sourceOpacityCaptured && !String.IsNullOrWhiteSpace(proxy.sourceNodeId)).ToArray();
            if (exactProxyBindings.Length != 1 || !proxyGraphic.transform.IsChildOf(presenter.proxyRoot.transform))
                return Fail("TMP_SORT_PRESENTER_SUPPRESSION_PROXY_IDENTITY_MISSING:" + materialSlot, out diagnostic);

            var materialForRendering = sourceGraphic.materialForRendering;
            var authoredMaterialMatches = materialForRendering != null &&
                (materialForRendering == sourceMaterial || MaterialFingerprint(materialForRendering) == MaterialFingerprint(sourceMaterial));
            string stencilMaterialDiagnostic = null;
            var exactMaskStencilDerivedMaterial = !authoredMaterialMatches && materialForRendering != null &&
                VerifyMaskStencilMaterial(sourceGraphic, sourceMaterial, materialForRendering, identity, presenter,
                    out stencilMaterialDiagnostic);
            if (!authoredMaterialMatches && !exactMaskStencilDerivedMaterial)
                return Fail("TMP_SORT_PRESENTER_SUPPRESSION_AUTHORED_MATERIAL_MISMATCH:" + materialSlot +
                    ";materialForRendering=" + ObjectIdentitySummary(materialForRendering) +
                    ";sourceMaterial=" + ObjectIdentitySummary(sourceMaterial) +
                    ";exactMaskStencilDerived=" + exactMaskStencilDerivedMaterial +
                    ";stencilDiagnostic=" + (stencilMaterialDiagnostic ?? "not-required"), out diagnostic);

            var runtimeCullBefore = trackedBefore[sourceIndexes[0]];
            var capturedCullBefore = bindings[0].sourceCanvasCullBefore;
            sourceCanvasCullBeforeCaptured = capturedCullBefore;
            sourceCanvasCullBeforeRuntime = runtimeCullBefore;
            // Capture may have run under a different canvas scale/layout. The
            // live presenter proof is tied to this exact loaded source Graphic:
            // false-before proves this presenter performed the cull now.
            var directPresenterCullVerified = !runtimeCullBefore;
            string maskDiagnostic = null;
            if (!directPresenterCullVerified)
                sourceRectMaskCullVerified = VerifyRectMaskCullProof(ownerGraphic, proxyGraphic, presenter, out maskDiagnostic);
            if (!directPresenterCullVerified && !sourceRectMaskCullVerified)
                return Fail("TMP_SORT_PRESENTER_SOURCE_CULL_OR_RECTMASK_PROOF_INVALID:" + materialSlot +
                    ";runtimeCullBefore=" + runtimeCullBefore + ";capturedCullBefore=" + capturedCullBefore +
                    ";maskProof=" + sourceRectMaskCullVerified + ";maskDiagnostic=" + (maskDiagnostic ?? "not-evaluated"), out diagnostic);

            var renderer = sourceGraphic.canvasRenderer;
            var alpha = renderer.GetAlpha();
            var inheritedAlpha = renderer.GetInheritedAlpha();
            if (exactProxyBindings.Any(proxy => Math.Abs(proxy.sourceRendererAlpha - alpha) > 0.00001f ||
                Math.Abs(proxy.sourceInheritedAlpha - inheritedAlpha) > 0.00001f))
                return Fail("TMP_SORT_PRESENTER_SUPPRESSION_OPACITY_PROOF_MISMATCH:" + materialSlot, out diagnostic);
            return true;
        }

        static bool VerifyRectMaskCullProof(Graphic sourceGraphic, NativeStaticSortQueueProxyGraphic proxyGraphic,
            NativeStaticSortQueueProxyPresenter presenter, out string diagnostic)
        {
            diagnostic = null;
            if (!(sourceGraphic is MaskableGraphic sourceMaskable) || !sourceMaskable.maskable ||
                proxyGraphic == null || presenter == null || presenter.proxyRoot == null)
                return Fail("TMP_SORT_RECTMASK_CULL_GRAPHICS_NOT_MASKABLE", out diagnostic);
            var sourceCanvas = sourceGraphic.GetComponentInParent<Canvas>();
            if (sourceCanvas == null || sourceCanvas.rootCanvas == null)
                return Fail("TMP_SORT_RECTMASK_CULL_SOURCE_ROOT_CANVAS_MISSING", out diagnostic);
            var nearestSourceMask = MaskUtilities.GetRectMaskForClippable(sourceMaskable);
            if (nearestSourceMask == null)
                return Fail("TMP_SORT_RECTMASK_CULL_SOURCE_MASK_MISSING", out diagnostic);
            var sourceMasks = new List<RectMask2D>();
            MaskUtilities.GetRectMasksForClip(nearestSourceMask, sourceMasks);
            var activeSourceMasks = sourceMasks.Where(mask => mask != null && mask.isActiveAndEnabled).ToArray();
            if (activeSourceMasks.Length == 0)
                return Fail("TMP_SORT_RECTMASK_CULL_ACTIVE_MASK_CHAIN_EMPTY", out diagnostic);
            if (activeSourceMasks.Any(mask =>
                {
                    var maskCanvas = mask.GetComponentInParent<Canvas>();
                    return maskCanvas == null || maskCanvas.rootCanvas != sourceCanvas.rootCanvas;
                }))
                return Fail("TMP_SORT_RECTMASK_CULL_ROOT_CANVAS_SCOPE_MISMATCH", out diagnostic);

            var clipRect = Clipping.FindCullAndClipWorldRect(activeSourceMasks.ToList(), out var validRect);
            var sourceRect = RectInRootCanvas(sourceGraphic.rectTransform);
            var clippedOutBySourceMask = !validRect || !clipRect.Overlaps(sourceRect, true);
            if (!clippedOutBySourceMask)
                return Fail("TMP_SORT_RECTMASK_CULL_SOURCE_GEOMETRY_OVERLAPS_CLIP:" +
                    ";validRect=" + validRect + ";clip=" + clipRect + ";source=" + sourceRect, out diagnostic);

            var maskProxies = new List<Mask>();
            foreach (var sourceMask in activeSourceMasks)
            {
                var matching = (presenter.maskBindings ?? Array.Empty<ProxyMaskBinding>())
                    .Where(binding => binding != null && binding.sourceMask == sourceMask &&
                        binding.proxyMask != null && binding.proxyMask.isActiveAndEnabled &&
                        binding.proxyMask.transform.IsChildOf(presenter.proxyRoot.transform)).ToArray();
                if (matching.Length != 1)
                    return Fail("TMP_SORT_RECTMASK_CULL_NATIVE_MASK_BINDING_NOT_UNIQUE:" +
                        matching.Length + ";source=" + sourceMask.name, out diagnostic);
                if (!proxyGraphic.transform.IsChildOf(matching[0].proxyMask.transform))
                    return Fail("TMP_SORT_RECTMASK_CULL_PROXY_OUTSIDE_MATCHING_MASK:" + sourceMask.name, out diagnostic);
                maskProxies.Add(matching[0].proxyMask);
            }
            diagnostic = "activeSourceMasks=" + activeSourceMasks.Length + ";clip=" + clipRect +
                ";source=" + sourceRect + ";nativeMasks=" + maskProxies.Count;
            return true;
        }

        static readonly HashSet<string> StencilMaterialProperties = new HashSet<string>(StringComparer.Ordinal)
        { "_Stencil", "_StencilComp", "_StencilOp", "_StencilReadMask", "_StencilWriteMask", "_ColorMask", "_UseUIAlphaClip" };
        static readonly string[] RequiredStencilMaterialProperties =
            { "_Stencil", "_StencilComp", "_StencilOp", "_StencilReadMask", "_StencilWriteMask", "_ColorMask" };
        const string OptionalStencilAlphaClipProperty = "_UseUIAlphaClip";

        static int ReadMaterialInt(Material material, string property)
        {
            return material == null || !material.HasProperty(property) ? Int32.MinValue :
                Mathf.RoundToInt(material.GetFloat(property));
        }

        static bool ShaderDeclaresProperty(Shader shader, string property)
        {
            if (shader == null || String.IsNullOrEmpty(property)) return false;
            for (var index = 0; index < shader.GetPropertyCount(); index++)
                if (String.Equals(shader.GetPropertyName(index), property, StringComparison.Ordinal)) return true;
            return false;
        }

        static bool NonStencilMaterialPropertiesMatch(Material source, Material actual)
        {
            if (source == null || actual == null || source.shader == null || source.shader != actual.shader ||
                source.mainTexture != actual.mainTexture || source.renderQueue != actual.renderQueue ||
                source.enableInstancing != actual.enableInstancing || source.doubleSidedGI != actual.doubleSidedGI ||
                source.globalIlluminationFlags != actual.globalIlluminationFlags) return false;
            var sourceKeywords = (source.shaderKeywords ?? Array.Empty<string>())
                .Where(keyword => keyword != "UNITY_UI_ALPHACLIP").OrderBy(keyword => keyword, StringComparer.Ordinal);
            var actualKeywords = (actual.shaderKeywords ?? Array.Empty<string>())
                .Where(keyword => keyword != "UNITY_UI_ALPHACLIP").OrderBy(keyword => keyword, StringComparer.Ordinal);
            if (!sourceKeywords.SequenceEqual(actualKeywords)) return false;
            var shader = source.shader;
            for (var index = 0; index < shader.GetPropertyCount(); index++)
            {
                var name = shader.GetPropertyName(index);
                if (StencilMaterialProperties.Contains(name)) continue;
                switch (shader.GetPropertyType(index))
                {
                    case ShaderPropertyType.Color:
                        if (source.GetColor(name) != actual.GetColor(name)) return false;
                        break;
                    case ShaderPropertyType.Vector:
                        if (source.GetVector(name) != actual.GetVector(name)) return false;
                        break;
                    case ShaderPropertyType.Float:
                    case ShaderPropertyType.Range:
                        if (!source.GetFloat(name).Equals(actual.GetFloat(name))) return false;
                        break;
                    case ShaderPropertyType.Int:
                        if (source.GetInt(name) != actual.GetInt(name)) return false;
                        break;
                    case ShaderPropertyType.Texture:
                        if (source.GetTexture(name) != actual.GetTexture(name) ||
                            source.GetTextureScale(name) != actual.GetTextureScale(name) ||
                            source.GetTextureOffset(name) != actual.GetTextureOffset(name)) return false;
                        break;
                    default:
                        return false;
                }
            }
            return true;
        }

        static bool VerifyMaskStencilMaterial(Graphic sourceGraphic, Material sourceMaterial, Material actualMaterial,
            NativeStaticSortTextSource identity, NativeStaticSortQueueProxyPresenter presenter, out string diagnostic)
        {
            diagnostic = null;
            if (!(sourceGraphic is MaskableGraphic maskable) || !maskable.maskable || sourceMaterial == null ||
                actualMaterial == null)
            {
                diagnostic = "source-not-maskable-or-material-missing";
                return false;
            }
            var rootCanvas = MaskUtilities.FindRootSortOverrideCanvas(sourceGraphic.transform);
            if (rootCanvas == null)
            {
                diagnostic = "source-root-canvas-missing";
                return false;
            }
            var sourceMasks = new List<Mask>();
            var sourceMaskIds = new List<string>();
            for (var current = sourceGraphic.transform.parent; current != null; current = current.parent)
            {
                var mask = current.GetComponent<Mask>();
                if (mask != null && mask.MaskEnabled() && mask.graphic != null && mask.graphic.IsActive())
                {
                    var maskIdentity = mask.GetComponent<NativeStaticMaskIdentity>();
                    if (maskIdentity == null || String.IsNullOrWhiteSpace(maskIdentity.sourceId))
                    {
                        diagnostic = "active-source-mask-identity-missing:" + current.name;
                        return false;
                    }
                    sourceMasks.Add(mask);
                    sourceMaskIds.Add(maskIdentity.sourceId);
                }
                if (current == rootCanvas) break;
            }
            var sdkDepth = MaskUtilities.GetStencilDepth(sourceGraphic.transform, rootCanvas);
            if (sdkDepth <= 0 || sdkDepth != sourceMasks.Count ||
                sourceMaskIds.Distinct(StringComparer.Ordinal).Count() != sourceMaskIds.Count)
            {
                diagnostic = "source-mask-ancestry-depth-mismatch:active=" + sourceMasks.Count + ";sdk=" + sdkDepth;
                return false;
            }
            var sourceRendererMaterial = sourceGraphic.materialForRendering;
            if (sourceRendererMaterial != actualMaterial)
            {
                diagnostic = "renderer-material-not-source-graphic-materialForRendering:" +
                    ObjectIdentitySummary(actualMaterial) + "!=" + ObjectIdentitySummary(sourceRendererMaterial);
                return false;
            }
            var stencilId = sdkDepth < 31 ? (1 << sdkDepth) - 1 : -1;
            var stencilPropertiesPresent = RequiredStencilMaterialProperties.All(sourceMaterial.HasProperty) &&
                RequiredStencilMaterialProperties.All(actualMaterial.HasProperty);
            var alphaClipSchemaDeclaredBySource = ShaderDeclaresProperty(sourceMaterial.shader, OptionalStencilAlphaClipProperty);
            var alphaClipSchemaDeclaredByActual = ShaderDeclaresProperty(actualMaterial.shader, OptionalStencilAlphaClipProperty);
            // StencilMaterial.Add calls SetFloat("_UseUIAlphaClip", 0) even for
            // shaders that do not declare that property. Compare the shader
            // schema, then inspect the value only when the schema declares it.
            var alphaClipPropertySchemaMatches = sourceMaterial.shader == actualMaterial.shader &&
                alphaClipSchemaDeclaredBySource == alphaClipSchemaDeclaredByActual;
            var alphaClipDisabled = !alphaClipSchemaDeclaredByActual ||
                (sourceMaterial.HasProperty(OptionalStencilAlphaClipProperty) && actualMaterial.HasProperty(OptionalStencilAlphaClipProperty) &&
                ReadMaterialInt(actualMaterial, OptionalStencilAlphaClipProperty) == 0);
            var configurationMatches = stencilId > 0 && stencilPropertiesPresent &&
                alphaClipPropertySchemaMatches && alphaClipDisabled &&
                ReadMaterialInt(actualMaterial, "_Stencil") == stencilId &&
                ReadMaterialInt(actualMaterial, "_StencilComp") == (int)CompareFunction.Equal &&
                ReadMaterialInt(actualMaterial, "_StencilOp") == (int)StencilOp.Keep &&
                ReadMaterialInt(actualMaterial, "_StencilReadMask") == stencilId &&
                ReadMaterialInt(actualMaterial, "_StencilWriteMask") == 0 &&
                ReadMaterialInt(actualMaterial, "_ColorMask") == (int)ColorWriteMask.All &&
                !actualMaterial.IsKeywordEnabled("UNITY_UI_ALPHACLIP");
            var derivedOnlyFromStencil = actualMaterial != sourceMaterial &&
                (actualMaterial.hideFlags & HideFlags.HideAndDontSave) == HideFlags.HideAndDontSave &&
                actualMaterial.shader == sourceMaterial.shader && NonStencilMaterialPropertiesMatch(sourceMaterial, actualMaterial);
            var proxyMaskBindingsVerified = presenter == null;
            if (presenter != null)
            {
                var proxyGraphic = identity == null ? null : identity.GetComponent<NativeStaticSortQueueProxyGraphic>();
                var bindingFailures = new List<string>();
                var matchedProxyMasks = new List<Mask>();
                foreach (var index in Enumerable.Range(0, sourceMasks.Count))
                {
                    var sourceMask = sourceMasks[index];
                    var sourceId = sourceMaskIds[index];
                    var matches = (presenter.maskBindings ?? Array.Empty<ProxyMaskBinding>())
                        .Where(row => row != null && row.sourceMask == sourceMask && row.sourceId == sourceId &&
                            row.proxyMask != null && row.proxyMask.isActiveAndEnabled &&
                            row.proxyMask.transform.IsChildOf(presenter.proxyRoot.transform)).ToArray();
                    if (matches.Length != 1 || proxyGraphic == null ||
                        matches.Length == 1 && !proxyGraphic.transform.IsChildOf(matches[0].proxyMask.transform))
                    {
                        bindingFailures.Add(sourceId + ":matches=" + matches.Length + ":proxyAncestor=" +
                            (matches.Length == 1 && proxyGraphic != null && proxyGraphic.transform.IsChildOf(matches[0].proxyMask.transform)));
                        continue;
                    }
                    matchedProxyMasks.Add(matches[0].proxyMask);
                    var proxyMaskIdentity = matches[0].proxyMask.GetComponent<NativeStaticMaskIdentity>();
                    if (proxyMaskIdentity == null || proxyMaskIdentity.sourceId != sourceId)
                        bindingFailures.Add(sourceId + ":proxy-mask-typed-identity-mismatch");
                }
                for (var index = 0; index + 1 < matchedProxyMasks.Count; index++)
                    if (!matchedProxyMasks[index].transform.IsChildOf(matchedProxyMasks[index + 1].transform))
                        bindingFailures.Add("proxy-mask-nesting-order-mismatch:" + sourceMaskIds[index] + ":" + sourceMaskIds[index + 1]);
                var proxyRootCanvas = proxyGraphic == null ? null : MaskUtilities.FindRootSortOverrideCanvas(proxyGraphic.transform);
                var proxyDepth = proxyGraphic == null || proxyRootCanvas == null ? -1 :
                    MaskUtilities.GetStencilDepth(proxyGraphic.transform, proxyRootCanvas);
                proxyMaskBindingsVerified = bindingFailures.Count == 0 &&
                    presenter.proxyRoot != null && presenter.sourceRoot != null &&
                    proxyDepth == sdkDepth && matchedProxyMasks.Count == sdkDepth &&
                    (sourceGraphic.transform == presenter.sourceRoot.transform ||
                     sourceGraphic.transform.IsChildOf(presenter.sourceRoot.transform));
                if (proxyDepth != sdkDepth || matchedProxyMasks.Count != sdkDepth)
                    bindingFailures.Add("proxy-sdk-depth-mismatch:" + proxyDepth + ":source=" + sdkDepth +
                        ":mapped=" + matchedProxyMasks.Count);
                if (bindingFailures.Count > 0) diagnostic = "proxy-mask-mapping=" + String.Join("|", bindingFailures.Take(4));
            }
            diagnostic = "depth=" + sdkDepth + ";stencilId=" + stencilId +
                ";sourceMaskIds=" + String.Join(",", sourceMaskIds) +
                ";sourceMaterial=" + ObjectIdentitySummary(sourceMaterial) +
                ";actual=" + ObjectIdentitySummary(actualMaterial) +
                ";materialForRenderingMatches=" + (sourceRendererMaterial == actualMaterial) +
                ";stencilPropertiesPresent=" + stencilPropertiesPresent +
                ";alphaClipPropertySchemaMatches=" + alphaClipPropertySchemaMatches +
                ";alphaClipDisabled=" + alphaClipDisabled +
                ";configurationMatches=" + configurationMatches +
                ";nonStencilPropertiesMatch=" + NonStencilMaterialPropertiesMatch(sourceMaterial, actualMaterial) +
                ";ownedTransientStencil=" + derivedOnlyFromStencil +
                ";proxyMaskBindingsVerified=" + proxyMaskBindingsVerified +
                (String.IsNullOrEmpty(diagnostic) ? String.Empty : ";mappingDiagnostic=" + diagnostic);
            return configurationMatches && derivedOnlyFromStencil && proxyMaskBindingsVerified;
        }

        static Rect RectInRootCanvas(RectTransform rectTransform)
        {
            if (rectTransform == null) return new Rect();
            var canvas = rectTransform.GetComponentInParent<Canvas>();
            if (canvas == null || canvas.rootCanvas == null) return new Rect();
            var rootCanvasTransform = canvas.rootCanvas.transform;
            var corners = new Vector3[4];
            rectTransform.GetWorldCorners(corners);
            var first = rootCanvasTransform.InverseTransformPoint(corners[0]);
            var minX = first.x; var maxX = first.x; var minY = first.y; var maxY = first.y;
            for (var i = 1; i < corners.Length; i++)
            {
                var point = rootCanvasTransform.InverseTransformPoint(corners[i]);
                minX = Mathf.Min(minX, point.x); maxX = Mathf.Max(maxX, point.x);
                minY = Mathf.Min(minY, point.y); maxY = Mathf.Max(maxY, point.y);
            }
            return Rect.MinMaxRect(minX, minY, maxX, maxY);
        }

        /// <summary>Enumerate fresh current TMP slots after ForceMeshUpdate; never retain generated child references.</summary>
        public static bool GetCurrentSlots(TMP_Text owner, string sourceComponentId,
            out List<TextSlotBinding> slots, out string diagnostic)
        {
            return GetCurrentSlots(owner, sourceComponentId, out slots, out _, out diagnostic);
        }

        public static bool GetCurrentSlots(TMP_Text owner, string sourceComponentId,
            out List<TextSlotBinding> slots, out NativeStaticSortTextSlotEnumeration enumeration,
            out string diagnostic)
        {
            return GetCurrentSlots(owner, sourceComponentId, null, null, out slots, out enumeration, out diagnostic);
        }

        public static bool GetCurrentSlots(TMP_Text owner, string sourceComponentId,
            NativeStaticSortQueueProxyPresenter presenter, NativeStaticSortTextSource identity,
            out List<TextSlotBinding> slots, out NativeStaticSortTextSlotEnumeration enumeration,
            out string diagnostic)
        {
            slots = new List<TextSlotBinding>(); enumeration = null; diagnostic = null;
            if (owner == null || String.IsNullOrWhiteSpace(sourceComponentId))
                return Fail("TMP_SORT_CURRENT_SLOTS_OWNER_OR_ID_MISSING", out diagnostic);
            var info = owner.textInfo;
            if (info == null || info.materialCount <= 0 || info.meshInfo == null || info.meshInfo.Length < info.materialCount)
                return Fail("TMP_SORT_CURRENT_SLOTS_TEXTINFO_UNAVAILABLE", out diagnostic);
            var children = owner.GetComponentsInChildren<TMP_SubMeshUI>(true)
                .Where(child => IsGeneratedSubmesh(child, owner) && TryMaterialSlot(child, out _)).ToArray();
            var rows = new List<NativeStaticSortTextSlotEvidence>();
            for (var slot = 0; slot < info.materialCount; slot++)
            {
                var textInfoReferences = 0;
                var visibleTextInfoReferences = 0;
                for (var characterIndex = 0; characterIndex < info.characterCount; characterIndex++)
                {
                    var character = info.characterInfo[characterIndex];
                    if (character.materialReferenceIndex != slot) continue;
                    textInfoReferences++;
                    if (character.isVisible) visibleTextInfoReferences++;
                }
                TMP_SubMeshUI generated = null;
                if (slot > 0)
                {
                    var matches = children.Where(child => TryMaterialSlot(child, out var childSlot) && childSlot == slot).ToArray();
                    if (matches.Length > 1 || textInfoReferences > 0 && matches.Length != 1)
                        return Fail("TMP_SORT_CURRENT_SLOT_GENERATED_CHILD_NOT_UNIQUE:" + slot + ":" + matches.Length, out diagnostic);
                    if (matches.Length == 1) generated = matches[0];
                }
                var slotMesh = info.meshInfo[slot].mesh;
                var slotGraphic = slot == 0 ? owner as Graphic : generated as Graphic;
                var rendererMesh = slotGraphic == null || slotGraphic.canvasRenderer == null ? null : slotGraphic.canvasRenderer.GetMesh();
                if (textInfoReferences == 0 || visibleTextInfoReferences == 0)
                {
                    // Preserve the source character denominator even when its
                    // entries are line breaks/control characters with no visible
                    // glyphs. "empty-placeholder" means this slot draws no
                    // geometry, not that its character references are absent.
                    var slotHasTriangles = MeshHasDrawTriangles(slotMesh);
                    var rendererHasTriangles = MeshHasDrawTriangles(rendererMesh);
                    if (slotHasTriangles || rendererHasTriangles)
                        return Fail("TMP_SORT_UNREFERENCED_TEXTINFO_SLOT_HAS_RENDERED_MESH:" + slot +
                            ":references=" + textInfoReferences + ":visible=" + visibleTextInfoReferences +
                            ":slotVertices=" + (slotMesh == null ? -1 : slotMesh.vertexCount) +
                            ":slotTriangles=" + MeshFirstSubmeshIndexCount(slotMesh) +
                            ":canvasVertices=" + (rendererMesh == null ? -1 : rendererMesh.vertexCount) +
                            ":canvasTriangles=" + MeshFirstSubmeshIndexCount(rendererMesh) +
                            ":slotGeometry=" + MeshGeometryDiagnostic(slotMesh) +
                            ":canvasGeometry=" + MeshGeometryDiagnostic(rendererMesh), out diagnostic);
                    var placeholderGraphic = slotGraphic;
                    rows.Add(BuildTextInfoSlotEvidence(owner, slot, placeholderGraphic, generated, null,
                        textInfoReferences, visibleTextInfoReferences, "empty-placeholder"));
                    continue;
                }
                if (slotGraphic == null)
                    return Fail("TMP_SORT_CURRENT_SLOT_GRAPHIC_MISSING:" + slot, out diagnostic);
                var slotIdentity = identity;
                if (presenter != null)
                {
                    var identities = presenter.proxyRoot == null ? Array.Empty<NativeStaticSortTextSource>() :
                        presenter.proxyRoot.GetComponentsInChildren<NativeStaticSortTextSource>(true)
                            .Where(candidate => candidate != null && candidate.sourceComponentId == sourceComponentId &&
                                candidate.materialSlot == slot && candidate.sourceOwner == owner).ToArray();
                    if (identities.Length != 1)
                        return Fail("TMP_SORT_PRESENTER_SLOT_IDENTITY_NOT_UNIQUE:" + slot + ":" + identities.Length, out diagnostic);
                    slotIdentity = identities[0];
                }
                if (!TryResolveSlot(owner, generated, slot, sourceComponentId, presenter, slotIdentity, out var binding, out diagnostic))
                    return false;
                rows.Add(BuildTextInfoSlotEvidence(owner, slot, slotGraphic, generated, binding,
                    textInfoReferences, visibleTextInfoReferences, "drawable"));
                slots.Add(binding);
            }
            var sourceTextSha = HashText(owner.text ?? String.Empty);
            enumeration = new NativeStaticSortTextSlotEnumeration {
                sourceComponentId = sourceComponentId,
                sourceTextSha256 = sourceTextSha,
                slotCount = info.materialCount,
                verified = rows.Count == info.materialCount && rows.All(row => row != null && !String.IsNullOrEmpty(row.evidenceSha256)),
                rows = rows.ToArray(),
            };
            enumeration.evidenceSha256 = TextSlotEnumerationHash(enumeration);
            enumeration.verified = enumeration.verified && IsValidTextSlotEnumeration(enumeration);
            if (!enumeration.verified)
                return Fail("TMP_SORT_TEXTINFO_SLOT_ENUMERATION_INCOMPLETE:" + rows.Count + "/" + info.materialCount, out diagnostic);
            foreach (var binding in slots) binding.textSlotEnumeration = enumeration;
            return true;
        }

        static NativeStaticSortTextSlotEvidence BuildTextInfoSlotEvidence(TMP_Text owner, int slot,
            Graphic sourceGraphic, TMP_SubMeshUI generated, TextSlotBinding binding,
            int characterReferences, int visibleCharacterReferences, string disposition)
        {
            var info = owner.textInfo;
            var slotMesh = info.meshInfo[slot].mesh;
            var rendererMesh = sourceGraphic == null || sourceGraphic.canvasRenderer == null
                ? null : sourceGraphic.canvasRenderer.GetMesh();
            var sourceAsset = binding != null
                ? (UnityEngine.Object)(binding.spriteAsset != null ? (UnityEngine.Object)binding.spriteAsset : binding.fontAsset)
                : generated != null
                    ? (UnityEngine.Object)(generated.spriteAsset != null ? (UnityEngine.Object)generated.spriteAsset : generated.fontAsset)
                    : owner.font;
            var sourceAssetKind = sourceAsset is TMP_SpriteAsset ? "sprite" : sourceAsset is TMP_FontAsset ? "font" : "unresolved";
            var sourceGraphicMaterial = binding != null ? binding.sourceMaterial
                : slot == 0 ? owner.fontSharedMaterial
                : generated != null ? generated.sharedMaterial : null;
            Texture atlas = binding != null ? binding.sourceTexture
                : sourceGraphicMaterial == null ? null : sourceGraphicMaterial.GetTexture(MainTex);
            var textInfoMaterial = info.meshInfo[slot].material;
            AssetIdentity(sourceAsset, out var sourceAssetGuid, out var sourceAssetFileId);
            AssetIdentity(atlas, out var atlasGuid, out var atlasFileId);
            var textInfoMaterialFingerprint = MaterialFingerprint(textInfoMaterial);
            var graphicMaterialFingerprint = MaterialFingerprint(sourceGraphicMaterial);
            var characterProof = binding != null ? binding.textInfoCharacterEvidenceSha256
                : HashText(owner.text + "|slot=" + slot + "|characters=" + characterReferences + "|visible=" + visibleCharacterReferences);
            var characterAssetProof = binding != null ? binding.textInfoCharacterAssetEvidenceSha256
                : HashText(owner.text + "|slot=" + slot + "|assetrefs=" + characterReferences + "|visible=" + visibleCharacterReferences);
            var row = new NativeStaticSortTextSlotEvidence {
                slot = slot,
                characterReferences = characterReferences,
                visibleCharacterReferences = visibleCharacterReferences,
                textInfoMaterialMissing = textInfoMaterial == null,
                textInfoVertexCount = slotMesh == null ? 0 : slotMesh.vertexCount,
                textInfoTriangleIndexCount = MeshTotalIndexCount(slotMesh),
                textInfoNondegenerateTriangleCount = MeshNonDegenerateTriangleCount(slotMesh),
                canvasVertexCount = rendererMesh == null ? 0 : rendererMesh.vertexCount,
                canvasTriangleIndexCount = MeshTotalIndexCount(rendererMesh),
                canvasNondegenerateTriangleCount = MeshNonDegenerateTriangleCount(rendererMesh),
                disposition = disposition,
                sourceAssetKind = sourceAssetKind,
                sourceAssetGuid = sourceAssetGuid,
                sourceAssetLocalFileId = sourceAssetFileId,
                atlasGuid = atlasGuid,
                atlasLocalFileId = atlasFileId,
                textInfoMaterialFingerprint = textInfoMaterialFingerprint,
                sourceGraphicMaterialFingerprint = graphicMaterialFingerprint,
                characterEvidenceSha256 = characterProof,
                characterAssetEvidenceSha256 = characterAssetProof,
                sourceMeshSha256 = binding != null ? binding.sourceMeshSha256 : MeshFingerprint(slotMesh),
            };
            row.evidenceSha256 = TextSlotRowHash(row);
            return row;
        }

        static bool EnumerationIsPlaceholderOnly(NativeStaticSortTextSlotEnumeration enumeration)
        {
            return IsValidTextSlotEnumeration(enumeration) && enumeration.rows.All(row => row.disposition == "empty-placeholder");
        }

        /// <summary>Persist typed slot denominator evidence on an empty text renderer carrier.</summary>
        public static bool AttachEmptyTextSlotEnumeration(GameObject carrier, TMP_Text owner,
            string sourceComponentId, NativeStaticSortTextSlotEnumeration enumeration, out string diagnostic)
        {
            diagnostic = null;
            if (carrier == null || owner == null || String.IsNullOrWhiteSpace(sourceComponentId) ||
                !EnumerationIsPlaceholderOnly(enumeration) || enumeration.sourceComponentId != sourceComponentId ||
                enumeration.sourceTextSha256 != HashText(owner.text ?? String.Empty))
                return Fail("TMP_SORT_EMPTY_TEXT_SLOT_ENUMERATION_INPUT_INVALID", out diagnostic);
            var identity = carrier.GetComponent<NativeStaticSortTextSlotEnumerationIdentity>() ??
                carrier.AddComponent<NativeStaticSortTextSlotEnumerationIdentity>();
            identity.sourceOwner = owner;
            identity.sourceComponentId = sourceComponentId;
            identity.slotEnumeration = enumeration;
            EditorUtility.SetDirty(identity);
            PrefabUtility.RecordPrefabInstancePropertyModifications(identity);
            return true;
        }

        /// <summary>Read-only saved-prefab proof for a typed empty-text source; does not initialize TMP.</summary>
        public static bool ReadPersistentEmptyTextSlotEnumerationIdentity(
            NativeStaticSortTextSlotEnumerationIdentity identity, TMP_Text expectedOwner,
            string expectedSourceComponentId, out TextSlotEnumerationReadback readback)
        {
            readback = new TextSlotEnumerationReadback {
                diagnostic = "TMP_SORT_PERSISTENT_EMPTY_TEXT_ENUMERATION_READBACK_FAILED"
            };
            if (identity == null || expectedOwner == null) return false;
            readback.sourceComponentId = identity.sourceComponentId;
            readback.slotEnumeration = identity.slotEnumeration;
            readback.ownerScopeVerified = identity.sourceOwner == expectedOwner &&
                identity.sourceComponentId == expectedSourceComponentId &&
                identity.slotEnumeration != null &&
                identity.slotEnumeration.sourceComponentId == expectedSourceComponentId &&
                identity.slotEnumeration.sourceTextSha256 == HashText(expectedOwner.text ?? String.Empty);
            var ownerPersistent = AssetIdentity(expectedOwner, out _, out var ownerLocalId) && ownerLocalId != 0;
            var contractValid = readback.ownerScopeVerified && EnumerationIsPlaceholderOnly(identity.slotEnumeration) &&
                String.IsNullOrEmpty(expectedOwner.text);
            readback.persistentReferencesVerified = contractValid && ownerPersistent &&
                AssetIdentity(identity, out _, out var identityLocalId) && identityLocalId != 0;
            readback.verified = contractValid && readback.persistentReferencesVerified;
            readback.diagnostic = readback.verified ? null :
                "TMP_SORT_PERSISTENT_EMPTY_TEXT_OWNER_OR_TYPED_NO_DRAW_CONTRACT_INVALID";
            return readback.verified;
        }

        /// <summary>Read-only current-slot proof for a typed empty-text carrier.</summary>
        public static bool ReadEmptyTextSlotEnumerationIdentity(NativeStaticSortTextSlotEnumerationIdentity identity,
            TMP_Text expectedOwner, string expectedSourceComponentId, out TextSlotEnumerationReadback readback)
        {
            readback = new TextSlotEnumerationReadback { diagnostic = "TMP_SORT_EMPTY_TEXT_ENUMERATION_READBACK_FAILED" };
            if (identity == null || expectedOwner == null) return false;
            readback.sourceComponentId = identity.sourceComponentId;
            readback.slotEnumeration = identity.slotEnumeration;
            readback.ownerScopeVerified = identity.sourceOwner == expectedOwner &&
                identity.sourceComponentId == expectedSourceComponentId;
            readback.persistentReferencesVerified = readback.ownerScopeVerified;
            if (!readback.ownerScopeVerified || !EnumerationIsPlaceholderOnly(identity.slotEnumeration) ||
                identity.slotEnumeration.sourceTextSha256 != HashText(expectedOwner.text ?? String.Empty))
            {
                readback.diagnostic = "TMP_SORT_EMPTY_TEXT_ENUMERATION_SAVED_OWNER_OR_CONTRACT_MISMATCH";
                return false;
            }
            if (!PrepareSource(expectedOwner, expectedSourceComponentId, out var prepareDiagnostic))
            {
                readback.diagnostic = prepareDiagnostic;
                return false;
            }
            if (!GetCurrentSlots(expectedOwner, expectedSourceComponentId, out var slots,
                out var currentEnumeration, out var slotDiagnostic))
            {
                readback.diagnostic = slotDiagnostic;
                return false;
            }
            readback.currentSlotEnumeration = currentEnumeration;
            readback.verified = slots.Count == 0 && EnumerationIsPlaceholderOnly(currentEnumeration) &&
                currentEnumeration.sourceComponentId == identity.sourceComponentId &&
                currentEnumeration.evidenceSha256 == identity.slotEnumeration.evidenceSha256;
            readback.diagnostic = readback.verified ? null : "TMP_SORT_EMPTY_TEXT_ENUMERATION_CURRENT_SLOT_PROOF_CHANGED";
            return readback.verified;
        }

        static string TextSlotRowHash(NativeStaticSortTextSlotEvidence row)
        {
            if (row == null) return null;
            return HashText(row.slot + "|" + row.characterReferences + "|" + row.visibleCharacterReferences +
                "|" + row.textInfoMaterialMissing + "|" + row.textInfoVertexCount + "|" + row.textInfoTriangleIndexCount +
                "|" + row.textInfoNondegenerateTriangleCount + "|" + row.canvasVertexCount + "|" + row.canvasTriangleIndexCount +
                "|" + row.canvasNondegenerateTriangleCount + "|" + row.disposition + "|" + row.sourceAssetKind + "|" +
                row.sourceAssetGuid + ":" + row.sourceAssetLocalFileId + "|" + row.atlasGuid + ":" + row.atlasLocalFileId + "|" +
                row.textInfoMaterialFingerprint + "|" + row.sourceGraphicMaterialFingerprint + "|" + row.characterEvidenceSha256 + "|" +
                row.characterAssetEvidenceSha256 + "|" +
                row.sourceMeshSha256);
        }

        static string TextSlotEnumerationHash(NativeStaticSortTextSlotEnumeration enumeration)
        {
            if (enumeration == null) return null;
            var rowHashes = (enumeration.rows ?? Array.Empty<NativeStaticSortTextSlotEvidence>())
                .Select(row => row == null ? String.Empty : row.evidenceSha256 ?? String.Empty).ToArray();
            return HashText(enumeration.sourceComponentId + "|" + enumeration.sourceTextSha256 + "|" + enumeration.slotCount + "|" +
                String.Join("|", rowHashes));
        }

        static bool IsValidTextSlotEnumeration(NativeStaticSortTextSlotEnumeration enumeration)
        {
            if (enumeration == null || !enumeration.verified || String.IsNullOrWhiteSpace(enumeration.sourceComponentId) ||
                !IsSha256(enumeration.sourceTextSha256) || enumeration.slotCount <= 0 || enumeration.rows == null ||
                enumeration.rows.Length != enumeration.slotCount || !IsSha256(enumeration.evidenceSha256) ||
                TextSlotEnumerationHash(enumeration) != enumeration.evidenceSha256) return false;
            for (var index = 0; index < enumeration.rows.Length; index++)
            {
                var row = enumeration.rows[index];
                if (row == null || row.slot != index || !IsSha256(row.evidenceSha256) ||
                    TextSlotRowHash(row) != row.evidenceSha256 ||
                    (row.disposition != "drawable" && row.disposition != "empty-placeholder") ||
                    (row.sourceAssetKind != "font" && row.sourceAssetKind != "sprite") ||
                    String.IsNullOrWhiteSpace(row.sourceAssetGuid) || row.sourceAssetLocalFileId == 0 ||
                    String.IsNullOrWhiteSpace(row.atlasGuid) || row.atlasLocalFileId == 0 ||
                    !IsSha256(row.characterEvidenceSha256) || !IsSha256(row.characterAssetEvidenceSha256)) return false;
                if (row.disposition == "drawable" &&
                    (row.characterReferences <= 0 || row.visibleCharacterReferences <= 0 ||
                     row.textInfoNondegenerateTriangleCount <= 0 || row.canvasNondegenerateTriangleCount <= 0 ||
                     !IsSha256(row.sourceMeshSha256))) return false;
                if (row.disposition == "empty-placeholder" &&
                    (row.visibleCharacterReferences > 0 || row.textInfoNondegenerateTriangleCount > 0 ||
                     row.canvasNondegenerateTriangleCount > 0)) return false;
            }
            return true;
        }

        /// <summary>
        /// Carry a previously verified TMP SDK fallback proof onto the current
        /// mesh/Graphic after re-preparation. Current material must be the exact
        /// owned asset baked from that proof; generated child object identity is
        /// intentionally discarded.
        /// </summary>
        public static bool RebindCapturedSlot(TextSlotBinding capturedProof, TMP_Text currentOwner,
            Graphic currentGraphic, out TextSlotBinding rebound, out string diagnostic)
        {
            rebound = null; diagnostic = null;
            if (capturedProof == null || currentOwner == null || currentGraphic == null ||
                capturedProof.owner != currentOwner || capturedProof.sourceGraphic == null ||
                String.IsNullOrWhiteSpace(capturedProof.sourceComponentId) ||
                !IsValidTextSlotEnumeration(capturedProof.textSlotEnumeration) ||
                capturedProof.textSlotEnumeration.sourceComponentId != capturedProof.sourceComponentId ||
                capturedProof.textSlotEnumeration.sourceTextSha256 != capturedProof.sourceTextSha256 ||
                capturedProof.materialSlot < 0 ||
                capturedProof.materialSlot >= capturedProof.textSlotEnumeration.rows.Length ||
                capturedProof.textSlotEnumeration.rows[capturedProof.materialSlot].disposition != "drawable")
                return Fail("TMP_SORT_CAPTURE_REBIND_INPUT_INVALID", out diagnostic);
            if (!GetCurrentSlots(currentOwner, capturedProof.sourceComponentId, out var currentSlots,
                out var currentEnumeration, out diagnostic)) return false;
            if (currentEnumeration == null || currentEnumeration.evidenceSha256 != capturedProof.textSlotEnumeration.evidenceSha256)
                return Fail("TMP_SORT_CAPTURE_REBIND_SLOT_ENUMERATION_CHANGED:" +
                    capturedProof.sourceComponentId + ";slot=" + capturedProof.materialSlot, out diagnostic);
            var current = currentSlots.SingleOrDefault(candidate => candidate.materialSlot == capturedProof.materialSlot);
            if (current == null || current.sourceGraphic != currentGraphic)
                return Fail("TMP_SORT_CAPTURE_REBIND_CURRENT_SLOT_GRAPHIC_MISMATCH:" +
                    capturedProof.sourceComponentId + ";slot=" + capturedProof.materialSlot, out diagnostic);
            if (current.sourceGraphic != currentGraphic || current.generatedSubmesh != capturedProof.generatedSubmesh ||
                current.sourceMeshSha256 != capturedProof.sourceMeshSha256 || current.fontAsset != capturedProof.fontAsset ||
                current.spriteAsset != capturedProof.spriteAsset || current.ownerFontSharedMaterial != capturedProof.ownerFontSharedMaterial ||
                current.sourceTexture != capturedProof.sourceTexture || current.fallbackFontAsset != capturedProof.fallbackFontAsset ||
                current.fallbackFontMaterial != capturedProof.fallbackFontMaterial ||
                current.textInfoMaterialMissing != capturedProof.textInfoMaterialMissing ||
                current.textInfoCharacterEvidenceSha256 != capturedProof.textInfoCharacterEvidenceSha256 ||
                current.textInfoCharacterMaterialFingerprint != capturedProof.textInfoCharacterMaterialFingerprint ||
                current.textInfoCharacterCount != capturedProof.textInfoCharacterCount ||
                current.textInfoVisibleCharacterCount != capturedProof.textInfoVisibleCharacterCount ||
                current.sourceTextSha256 != capturedProof.sourceTextSha256 ||
                capturedProof.ownerStyle != null &&
                    (capturedProof.ownerStyle.sourceComponentId != capturedProof.sourceComponentId ||
                     capturedProof.ownerStyle.sourceFontAsset != currentOwner.font ||
                     capturedProof.ownerStyle.sourceFontMaterial != currentOwner.font.material ||
                     capturedProof.ownerStyle.profile != "native-static-text-outline-font-material-v1"))
                return Fail("TMP_SORT_CAPTURE_REBIND_SOURCE_IDENTITY_OR_MESH_CHANGED", out diagnostic);

            if (capturedProof.tmpFallbackMaterialBaked)
            {
                if (capturedProof.persistentFallbackVariantRegistered)
                {
                    var currentIsPersistent = PersistentAsset(current.sourceMaterial, out var currentGuid, out var currentFileId);
                    var currentFingerprint = MaterialFingerprint(current.sourceMaterial);
                    var submesh = current.sourceGraphic as TMP_SubMeshUI;
                    var outlineDriver = currentOwner.GetComponent<NativeStaticTextOutline>();
                    var fallbackSourceIsOwner = submesh != null && submesh.fallbackSourceMaterial == currentOwner.fontSharedMaterial;
                    var fallbackMaterialIsCurrent = submesh != null && submesh.fallbackMaterial == current.sourceMaterial;
                    var sharedMaterialIsCurrent = submesh != null && submesh.sharedMaterial == current.sourceMaterial;
                    var registeredVariantSelected = outlineDriver != null && outlineDriver.IsPersistentMaterialVariantSelected(
                        capturedProof.fallbackFontAsset, capturedProof.ownerFontSharedMaterial,
                        current.sourceTexture, current.sourceMaterial);
                    var registeredVariantFailures = new List<string>();
                    if (!currentIsPersistent) registeredVariantFailures.Add("currentMaterialNotPersistent");
                    if (current.sourceMaterial != capturedProof.proxyMaterial) registeredVariantFailures.Add("materialReferenceChanged");
                    if (currentFingerprint != capturedProof.bakedProxyMaterialFingerprint) registeredVariantFailures.Add("materialFingerprintChanged");
                    if (currentGuid != capturedProof.bakedProxyMaterialGuid) registeredVariantFailures.Add("guidChanged");
                    if (currentFileId != capturedProof.bakedProxyMaterialLocalFileId) registeredVariantFailures.Add("localFileIdChanged");
                    if (capturedProof.bakedProxyMaterialFingerprint != capturedProof.transientFallbackFingerprint)
                        registeredVariantFailures.Add("capturedBakeDiffersFromTransientProfile");
                    if (outlineDriver == null) registeredVariantFailures.Add("outlineDriverMissing");
                    else if (outlineDriver.Target != currentOwner) registeredVariantFailures.Add("outlineTargetMismatch");
                    if (!fallbackSourceIsOwner) registeredVariantFailures.Add("fallbackSourceNotOwnerMaterial");
                    if (!fallbackMaterialIsCurrent) registeredVariantFailures.Add("fallbackMaterialNotSelected");
                    if (!sharedMaterialIsCurrent) registeredVariantFailures.Add("submeshSharedMaterialNotCurrent");
                    if (!registeredVariantSelected) registeredVariantFailures.Add("registeredVariantRecordNotSelected");
                    if (registeredVariantFailures.Count > 0)
                        return Fail("TMP_SORT_CAPTURE_REBIND_REGISTERED_FALLBACK_VARIANT_MISMATCH:" +
                            capturedProof.sourceComponentId + ";slot=" + capturedProof.materialSlot +
                            ";failed=" + String.Join(",", registeredVariantFailures) +
                            ";currentRefMatchesBake=" + (current.sourceMaterial == capturedProof.proxyMaterial) +
                            ";currentGuidLocal=" + (currentGuid ?? "null") + ":" + currentFileId +
                            ";expectedGuidLocal=" + (capturedProof.bakedProxyMaterialGuid ?? "null") + ":" + capturedProof.bakedProxyMaterialLocalFileId +
                            ";currentFingerprint=" + (currentFingerprint ?? "missing") +
                            ";expectedFingerprint=" + (capturedProof.bakedProxyMaterialFingerprint ?? "missing") +
                            ";capturedTransientFingerprint=" + (capturedProof.transientFallbackFingerprint ?? "missing") +
                            ";outlineDriver=" + (outlineDriver != null) +
                            ";outlineTargetMatches=" + (outlineDriver != null && outlineDriver.Target == currentOwner) +
                            ";fallbackSourceIsOwner=" + fallbackSourceIsOwner +
                            ";fallbackMaterialIsCurrent=" + fallbackMaterialIsCurrent +
                            ";sharedMaterialIsCurrent=" + sharedMaterialIsCurrent +
                            ";registeredVariantSelected=" + registeredVariantSelected, out diagnostic);
                }
                else if (PersistentAsset(current.sourceMaterial, out _, out _) || current.sourceMaterial == null ||
                    current.sourceMaterialFingerprint != capturedProof.transientFallbackFingerprint ||
                    capturedProof.bakedProxyMaterialFingerprint != capturedProof.transientFallbackFingerprint)
                    return Fail("TMP_SORT_CAPTURE_REBIND_SDK_TRANSIENT_FALLBACK_PROFILE_MISMATCH", out diagnostic);
            }
            else if (current.sourceMaterial != capturedProof.sourceMaterial ||
                current.sourceMaterialFingerprint != capturedProof.sourceMaterialFingerprint)
                return Fail("TMP_SORT_CAPTURE_REBIND_SOURCE_MATERIAL_CHANGED", out diagnostic);

            current.ownerStyle = capturedProof.ownerStyle;
            current.textSlotEnumeration = capturedProof.textSlotEnumeration;
            current.tmpFallbackMaterialBaked = capturedProof.tmpFallbackMaterialBaked;
            current.persistentFallbackVariantRegistered = capturedProof.persistentFallbackVariantRegistered;
            current.tmpFallbackAlgorithm = capturedProof.tmpFallbackAlgorithm;
            current.tmpFallbackAtlasIndex = capturedProof.tmpFallbackAtlasIndex;
            current.ownerFontMaterialGuid = capturedProof.ownerFontMaterialGuid;
            current.ownerFontMaterialLocalFileId = capturedProof.ownerFontMaterialLocalFileId;
            current.ownerFontMaterialFingerprint = capturedProof.ownerFontMaterialFingerprint;
            current.fallbackFontAssetGuid = capturedProof.fallbackFontAssetGuid;
            current.fallbackFontAssetLocalFileId = capturedProof.fallbackFontAssetLocalFileId;
            current.fallbackFontMaterialGuid = capturedProof.fallbackFontMaterialGuid;
            current.fallbackFontMaterialLocalFileId = capturedProof.fallbackFontMaterialLocalFileId;
            current.fallbackFontMaterialFingerprint = capturedProof.fallbackFontMaterialFingerprint;
            current.fallbackAtlasGuid = capturedProof.fallbackAtlasGuid;
            current.fallbackAtlasLocalFileId = capturedProof.fallbackAtlasLocalFileId;
            current.transientFallbackFingerprint = capturedProof.transientFallbackFingerprint;
            current.sourceMaterialFingerprint = capturedProof.sourceMaterialFingerprint;
            current.proxyMaterial = capturedProof.proxyMaterial;
            current.proxyMaterialFingerprint = capturedProof.proxyMaterialFingerprint;
            current.proxyMaterialGuid = capturedProof.proxyMaterialGuid;
            current.proxyMaterialLocalFileId = capturedProof.proxyMaterialLocalFileId;
            current.bakedProxyMaterialFingerprint = capturedProof.bakedProxyMaterialFingerprint;
            current.bakedProxyMaterialGuid = capturedProof.bakedProxyMaterialGuid;
            current.bakedProxyMaterialLocalFileId = capturedProof.bakedProxyMaterialLocalFileId;
            if (current.tmpFallbackMaterialBaked)
            {
                current.sourceMaterialGuid = null;
                current.sourceMaterialLocalFileId = 0;
            }
            rebound = current;
            return true;
        }

        /// <summary>
        /// Capture-only persistence step for TMP's hidden fallback material.
        /// It asks the pinned TMP SDK for the exact fallback result, compares
        /// every shader property to the transient submesh material, then saves
        /// that exact material profile as an owned .mat asset. Readback paths
        /// never call this method and never create or repair assets.
        /// </summary>
        public static bool CaptureFallbackMaterial(TextSlotBinding binding, string persistentAssetPath,
            out string diagnostic)
        {
            diagnostic = null;
            if (binding == null || binding.sourceMaterial == null || binding.sourceTexture == null)
                return Fail("TMP_SORT_FALLBACK_CAPTURE_BINDING_INCOMPLETE", out diagnostic);
            if (PersistentAsset(binding.sourceMaterial, out var directGuid, out var directFileId))
            {
                binding.persistentFallbackVariantRegistered = false;
                if (binding.generatedSubmesh && binding.owner != null && binding.fallbackFontAsset != null && binding.fallbackFontAsset != binding.owner.font)
                {
                    var outline = binding.owner.GetComponent<NativeStaticTextOutline>();
                    if (outline != null && !outline.RegisterPersistentMaterialVariant(binding.fallbackFontAsset,
                        binding.sourceMaterial, binding.ownerFontSharedMaterial, binding.owner.fontSize,
                        binding.sourceTexture, out var registerDiagnostic))
                        return Fail("TMP_SORT_PERSISTENT_FALLBACK_VARIANT_REGISTRATION_FAILED:" + registerDiagnostic, out diagnostic);
                    if (outline != null)
                    {
                        binding.persistentFallbackVariantRegistered = true;
                        EditorUtility.SetDirty(outline);
                        PrefabUtility.RecordPrefabInstancePropertyModifications(outline);
                    }
                }
                binding.proxyMaterial = binding.sourceMaterial;
                binding.proxyMaterialFingerprint = MaterialFingerprint(binding.sourceMaterial);
                binding.proxyMaterialGuid = directGuid;
                binding.proxyMaterialLocalFileId = directFileId;
                binding.bakedProxyMaterialGuid = directGuid;
                binding.bakedProxyMaterialLocalFileId = directFileId;
                binding.bakedProxyMaterialFingerprint = binding.proxyMaterialFingerprint;
                binding.tmpFallbackMaterialBaked = false;
                return !String.IsNullOrEmpty(binding.proxyMaterialFingerprint) ||
                    Fail("TMP_SORT_SOURCE_MATERIAL_FINGERPRINT_UNAVAILABLE", out diagnostic);
            }

            var owner = binding.owner;
            var sourceBase = binding.ownerFontSharedMaterial;
            var fallbackFont = binding.fallbackFontAsset;
            var fallbackBase = binding.fallbackFontMaterial;
            if (owner == null || sourceBase == null || fallbackFont == null || fallbackBase == null)
                return Fail("TMP_SORT_TRANSIENT_MATERIAL_HAS_NO_EXACT_OWNER_FONT_PROVENANCE", out diagnostic);
            if (!PersistentAsset(sourceBase, out binding.ownerFontMaterialGuid, out binding.ownerFontMaterialLocalFileId) ||
                !PersistentAsset(fallbackFont, out binding.fallbackFontAssetGuid, out binding.fallbackFontAssetLocalFileId) ||
                !PersistentAsset(fallbackBase, out binding.fallbackFontMaterialGuid, out binding.fallbackFontMaterialLocalFileId) ||
                !PersistentAsset(binding.sourceTexture, out binding.fallbackAtlasGuid, out binding.fallbackAtlasLocalFileId))
                return Fail("TMP_SORT_TRANSIENT_FALLBACK_SOURCE_ASSET_NOT_PERSISTENT", out diagnostic);
            if (fallbackFont.atlasTextures == null)
                return Fail("TMP_SORT_FALLBACK_FONT_HAS_NO_ATLAS_ARRAY", out diagnostic);
            var atlasIndexes = Enumerable.Range(0, fallbackFont.atlasTextures.Length)
                .Where(index => fallbackFont.atlasTextures[index] == binding.sourceTexture).ToArray();
            if (atlasIndexes.Length != 1)
                return Fail("TMP_SORT_FALLBACK_ATLAS_IDENTITY_NOT_UNIQUE:" + atlasIndexes.Length, out diagnostic);
            var atlasIndex = atlasIndexes[0];
            binding.tmpFallbackAtlasIndex = atlasIndex;

            Material sdkOutput = null;
            var algorithm = "";
            try
            {
                if (fallbackFont != owner.font)
                {
                    // TMP_TextProcessing uses GetFallbackMaterial(currentMaterial, fallbackFont.material)
                    // when matchMaterialPreset is enabled. The source must be the exact persistent
                    // owner fontSharedMaterial; an alternate style/material chain is not inferred.
                    sdkOutput = TMP_MaterialManager.GetFallbackMaterial(sourceBase, fallbackBase);
                    algorithm = "tmpro-fallback-font-material-v1";
                    if (atlasIndex > 0)
                    {
                        if (MultiAtlasFallbackMethod == null)
                            return Fail("TMP_SORT_PINNED_MULTI_ATLAS_FALLBACK_API_UNAVAILABLE", out diagnostic);
                        sdkOutput = MultiAtlasFallbackMethod.Invoke(null, new object[] { fallbackFont, sdkOutput, atlasIndex }) as Material;
                        algorithm += "+tmpro-multi-atlas-v1";
                    }
                }
                else if (atlasIndex > 0)
                {
                    if (MultiAtlasFallbackMethod == null)
                        return Fail("TMP_SORT_PINNED_MULTI_ATLAS_FALLBACK_API_UNAVAILABLE", out diagnostic);
                    sdkOutput = MultiAtlasFallbackMethod.Invoke(null, new object[] { fallbackFont, sourceBase, atlasIndex }) as Material;
                    algorithm = "tmpro-multi-atlas-v1";
                }
                else
                    return Fail("TMP_SORT_TRANSIENT_MATERIAL_IS_NOT_A_SUPPORTED_TMP_FALLBACK", out diagnostic);
            }
            catch (Exception error)
            {
                return Fail("TMP_SORT_SDK_FALLBACK_EVALUATION_FAILED:" + error.GetType().Name, out diagnostic);
            }
            Material profileOutput = sdkOutput;
            bool ownsProfileOutput = false;
            var outlineDriver = owner.GetComponent<NativeStaticTextOutline>();
            if (outlineDriver != null && fallbackFont != owner.font)
            {
                profileOutput = new Material(sdkOutput) { hideFlags = HideFlags.HideAndDontSave };
                ownsProfileOutput = true;
                if (!outlineDriver.ConfigureCaptureCandidate(profileOutput, fallbackFont, owner.fontSize, out var styleDiagnostic))
                {
                    UnityEngine.Object.DestroyImmediate(profileOutput);
                    return Fail("TMP_SORT_FALLBACK_OUTLINE_STYLE_DERIVATION_FAILED:" + styleDiagnostic, out diagnostic);
                }
                // TextMeshProUGUI.UpdateMeshPadding also calls TMP_SubMeshUI.UpdateMeshPadding
                // for each generated face. That call runs this same shader-ratio update
                // on the fallback material before the rendered slot is read back.
                TMPro.ShaderUtilities.GetPadding(profileOutput, owner.extraPadding, owner.isUsingBold);
                algorithm += "+native-static-text-outline-v1";
            }
            var transientFingerprint = MaterialFingerprint(binding.sourceMaterial);
            var sdkFingerprint = MaterialFingerprint(profileOutput);
            if (sdkOutput == null || String.IsNullOrEmpty(transientFingerprint) ||
                transientFingerprint != sdkFingerprint || profileOutput.GetTexture(MainTex) != binding.sourceTexture)
            {
                if (ownsProfileOutput) UnityEngine.Object.DestroyImmediate(profileOutput);
                return Fail("TMP_SORT_TRANSIENT_FALLBACK_DIFFERS_FROM_PINNED_SDK_OUTPUT", out diagnostic);
            }

            if (!PersistentAssetPath(persistentAssetPath, out diagnostic))
            {
                if (ownsProfileOutput) UnityEngine.Object.DestroyImmediate(profileOutput);
                return false;
            }
            var ownerFingerprint = MaterialFingerprint(sourceBase);
            var fallbackFingerprint = MaterialFingerprint(fallbackBase);
            if (String.IsNullOrEmpty(ownerFingerprint) || String.IsNullOrEmpty(fallbackFingerprint))
                return Fail("TMP_SORT_FALLBACK_BASE_MATERIAL_FINGERPRINT_UNAVAILABLE", out diagnostic);
            var baked = AssetDatabase.LoadAssetAtPath<Material>(persistentAssetPath);
            if (baked == null)
            {
                if (File.Exists(persistentAssetPath))
                {
                    if (ownsProfileOutput) UnityEngine.Object.DestroyImmediate(profileOutput);
                    return Fail("TMP_SORT_FALLBACK_BAKE_PATH_IS_OWNED_BY_NON_MATERIAL", out diagnostic);
                }
                var clone = new Material(profileOutput) { name = Path.GetFileNameWithoutExtension(persistentAssetPath), hideFlags = HideFlags.None };
                if (MaterialFingerprint(clone) != transientFingerprint)
                {
                    UnityEngine.Object.DestroyImmediate(clone);
                    if (ownsProfileOutput) UnityEngine.Object.DestroyImmediate(profileOutput);
                    return Fail("TMP_SORT_FALLBACK_BAKE_CLONE_CHANGED_SHADER_PROPERTIES", out diagnostic);
                }
                try { AssetDatabase.CreateAsset(clone, persistentAssetPath); }
                catch (Exception error)
                {
                    UnityEngine.Object.DestroyImmediate(clone);
                    if (ownsProfileOutput) UnityEngine.Object.DestroyImmediate(profileOutput);
                    return Fail("TMP_SORT_FALLBACK_BAKE_CREATE_ASSET_FAILED:" + error.GetType().Name, out diagnostic);
                }
                baked = AssetDatabase.LoadAssetAtPath<Material>(persistentAssetPath);
            }
            if (ownsProfileOutput) UnityEngine.Object.DestroyImmediate(profileOutput);
            var bakedFingerprint = MaterialFingerprint(baked);
            if (!PersistentAsset(baked, out var bakedGuid, out var bakedFileId) ||
                String.IsNullOrEmpty(bakedFingerprint) || bakedFingerprint != transientFingerprint)
                return Fail("TMP_SORT_PERSISTENT_FALLBACK_BAKE_DIFFERS_FROM_TRANSIENT_SDK_OUTPUT", out diagnostic);

            binding.proxyMaterial = baked;
            binding.proxyMaterialFingerprint = bakedFingerprint;
            binding.proxyMaterialGuid = bakedGuid;
            binding.proxyMaterialLocalFileId = bakedFileId;
            binding.proxyMaterialFingerprint = bakedFingerprint;
            binding.bakedProxyMaterialGuid = bakedGuid;
            binding.bakedProxyMaterialLocalFileId = bakedFileId;
            binding.tmpFallbackMaterialBaked = true;
            binding.persistentFallbackVariantRegistered = false;
            binding.tmpFallbackAlgorithm = algorithm;
            binding.ownerFontMaterialFingerprint = ownerFingerprint;
            binding.fallbackFontMaterialFingerprint = fallbackFingerprint;
            binding.transientFallbackFingerprint = transientFingerprint;
            binding.bakedProxyMaterialFingerprint = bakedFingerprint;
            if (outlineDriver != null && fallbackFont != owner.font &&
                !outlineDriver.RegisterPersistentMaterialVariant(fallbackFont, baked, sourceBase, owner.fontSize,
                    binding.sourceTexture, out var persistentVariantDiagnostic))
                return Fail("TMP_SORT_FALLBACK_PERSISTENT_VARIANT_REGISTRATION_FAILED:" + persistentVariantDiagnostic, out diagnostic);
            if (outlineDriver != null && fallbackFont != owner.font)
            {
                binding.persistentFallbackVariantRegistered = true;
                EditorUtility.SetDirty(outlineDriver);
                PrefabUtility.RecordPrefabInstancePropertyModifications(outlineDriver);
            }
            return true;
        }

        static bool PersistentAssetPath(string value, out string diagnostic)
        {
            diagnostic = null;
            if (String.IsNullOrWhiteSpace(value) || !value.StartsWith("Assets/", StringComparison.Ordinal) ||
                value.Contains("\\") || value.Split('/').Any(part => part == ".." || part == ".") ||
                !String.Equals(Path.GetExtension(value), ".mat", StringComparison.OrdinalIgnoreCase))
                return Fail("TMP_SORT_FALLBACK_BAKE_PATH_UNSAFE", out diagnostic);
            var folder = Path.GetDirectoryName(value)?.Replace("\\", "/");
            if (String.IsNullOrEmpty(folder) || !AssetDatabase.IsValidFolder(folder))
                return Fail("TMP_SORT_FALLBACK_BAKE_FOLDER_NOT_OWNED", out diagnostic);
            return true;
        }

        static string AttachInputFailureSummary(GameObject proxy, TextSlotBinding binding,
            Mesh bakedProxyMesh, string expectedProxyMeshSha256)
        {
            var failed = new List<string>();
            if (proxy == null) failed.Add("proxyMissing");
            if (binding == null) failed.Add("bindingMissing");
            if (bakedProxyMesh == null) failed.Add("bakedMeshMissing");
            if (binding == null) return String.Join(",", failed);
            if (String.IsNullOrWhiteSpace(binding.sourceComponentId)) failed.Add("sourceComponentIdMissing");
            if (binding.owner == null) failed.Add("ownerMissing");
            if (binding.sourceGraphic == null) failed.Add("sourceGraphicMissing");
            if (binding.proxyMaterial == null) failed.Add("proxyMaterialMissing");
            if (String.IsNullOrWhiteSpace(binding.proxyMaterialGuid)) failed.Add("proxyMaterialGuidMissing");
            if (String.IsNullOrWhiteSpace(expectedProxyMeshSha256)) failed.Add("expectedMeshShaMissing");
            var actualMeshSha = bakedProxyMesh == null ? null : MeshFingerprint(bakedProxyMesh);
            if (!String.IsNullOrWhiteSpace(expectedProxyMeshSha256) && actualMeshSha != expectedProxyMeshSha256)
                failed.Add("bakedMeshShaMismatch:" + (actualMeshSha ?? "null") + "!=" + expectedProxyMeshSha256);
            var enumeration = binding.textSlotEnumeration;
            if (enumeration == null) failed.Add("slotEnumerationMissing");
            else
            {
                if (!IsValidTextSlotEnumeration(enumeration)) failed.Add("slotEnumerationInvalid");
                if (enumeration.sourceComponentId != binding.sourceComponentId)
                    failed.Add("slotEnumerationSourceIdMismatch:" + (enumeration.sourceComponentId ?? "null") + "!=" +
                        (binding.sourceComponentId ?? "null"));
                if (enumeration.sourceTextSha256 != binding.sourceTextSha256)
                    failed.Add("slotEnumerationTextShaMismatch:" + (enumeration.sourceTextSha256 ?? "null") + "!=" +
                        (binding.sourceTextSha256 ?? "null"));
                if (enumeration.rows == null || binding.materialSlot < 0 || binding.materialSlot >= enumeration.rows.Length)
                    failed.Add("slotEnumerationRowMissing:" + binding.materialSlot + "/" +
                        (enumeration.rows == null ? "null" : enumeration.rows.Length.ToString()));
                else if (enumeration.rows[binding.materialSlot] == null ||
                    enumeration.rows[binding.materialSlot].disposition != "drawable")
                    failed.Add("slotEnumerationRowNotDrawable:" + binding.materialSlot + ":" +
                        (enumeration.rows[binding.materialSlot] == null ? "null" : enumeration.rows[binding.materialSlot].disposition));
            }
            return String.Join(",", failed);
        }

        static Mesh PersistSourceSlotMeshSnapshot(TextSlotBinding binding, Mesh bakedProxyMesh,
            out string guid, out long localFileId)
        {
            guid = null; localFileId = 0;
            if (binding == null || binding.sourceMesh == null || bakedProxyMesh == null ||
                !IsSha256(binding.sourceMeshSha256) || MeshFingerprint(binding.sourceMesh) != binding.sourceMeshSha256)
                throw new InvalidOperationException("TMP_SORT_SOURCE_SLOT_MESH_SNAPSHOT_INPUT_INVALID");
            var proxyPath = AssetDatabase.GetAssetPath(bakedProxyMesh);
            if (String.IsNullOrWhiteSpace(proxyPath) || !proxyPath.StartsWith("Assets/", StringComparison.Ordinal))
                throw new InvalidOperationException("TMP_SORT_SOURCE_SLOT_MESH_PROXY_ASSET_PATH_INVALID:" + (proxyPath ?? "null"));
            var folder = Path.GetDirectoryName(proxyPath)?.Replace('\\', '/');
            if (String.IsNullOrWhiteSpace(folder))
                throw new InvalidOperationException("TMP_SORT_SOURCE_SLOT_MESH_ASSET_FOLDER_INVALID:" + proxyPath);
            var key = HashText(binding.sourceComponentId + "|" + binding.materialSlot + "|" + binding.sourceMeshSha256).Substring(0, 24);
            var path = folder.TrimEnd('/') + "/TMPTextSourceMesh_" + key + ".asset";
            var existing = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (existing != null)
            {
                if (MeshFingerprint(existing) != binding.sourceMeshSha256)
                    throw new InvalidOperationException("TMP_SORT_SOURCE_SLOT_MESH_SNAPSHOT_COLLISION:" + path);
                if (!PersistentAsset(existing, out guid, out localFileId) || String.IsNullOrWhiteSpace(guid) || localFileId == 0)
                    throw new InvalidOperationException("TMP_SORT_SOURCE_SLOT_MESH_SNAPSHOT_NOT_PERSISTENT:" + path);
                return existing;
            }
            var occupied = AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(path);
            if (occupied != null)
                throw new InvalidOperationException("TMP_SORT_SOURCE_SLOT_MESH_SNAPSHOT_PATH_OCCUPIED_BY_NONMESH:" + path);
            var snapshot = UnityEngine.Object.Instantiate(binding.sourceMesh);
            snapshot.name = "TMPTextSourceMesh_" + key;
            snapshot.hideFlags = HideFlags.None;
            if (MeshFingerprint(snapshot) != binding.sourceMeshSha256)
            {
                UnityEngine.Object.DestroyImmediate(snapshot);
                throw new InvalidOperationException("TMP_SORT_SOURCE_SLOT_MESH_SNAPSHOT_CLONE_MISMATCH:" + binding.sourceComponentId);
            }
            AssetDatabase.CreateAsset(snapshot, path);
            var persisted = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (persisted == null || MeshFingerprint(persisted) != binding.sourceMeshSha256 ||
                !PersistentAsset(persisted, out guid, out localFileId) || String.IsNullOrWhiteSpace(guid) || localFileId == 0)
                throw new InvalidOperationException("TMP_SORT_SOURCE_SLOT_MESH_SNAPSHOT_WRITE_VERIFICATION_FAILED:" + path);
            return persisted;
        }

        public static NativeStaticSortTextSource Attach(GameObject proxy, TextSlotBinding binding,
            Mesh bakedProxyMesh, string expectedProxyMeshSha256)
        {
            var attachFailures = AttachInputFailureSummary(proxy, binding, bakedProxyMesh, expectedProxyMeshSha256);
            if (!String.IsNullOrEmpty(attachFailures))
                throw new InvalidOperationException("TMP_SORT_SOURCE_ATTACH_INPUT_INVALID:sourceComponentId=" +
                    (binding == null ? "null" : binding.sourceComponentId ?? "null") + ";failed=" + attachFailures);
            var sourceSlotMesh = PersistSourceSlotMeshSnapshot(binding, bakedProxyMesh,
                out var sourceSlotMeshGuid, out var sourceSlotMeshLocalFileId);
            if (!TryBuildTextScaleContext(binding.owner, binding.sourceGraphic, sourceSlotMesh,
                    binding.sourceComponentId, binding.materialSlot, out var textScaleContext, out var scaleContextDiagnostic) ||
                !IsValidTextScaleContext(textScaleContext))
                throw new InvalidOperationException("TMP_SORT_UV_SCALE_CONTEXT_CAPTURE_FAILED:sourceComponentId=" +
                    binding.sourceComponentId + ";diagnostic=" + (scaleContextDiagnostic ?? "context-invalid"));
            var identity = proxy.GetComponent<NativeStaticSortTextSource>() ?? proxy.AddComponent<NativeStaticSortTextSource>();
            identity.sourceComponentId = binding.sourceComponentId;
            identity.sourceOwner = binding.owner;
            identity.materialSlot = binding.materialSlot;
            identity.generatedSubmesh = binding.generatedSubmesh;
            identity.sourceGraphicEnabled = binding.sourceGraphicEnabled;
            identity.sourceGraphicActiveSelf = binding.sourceGraphicActiveSelf;
            identity.textSlotEnumeration = binding.textSlotEnumeration;
            identity.textScaleContext = textScaleContext;
            identity.textInfoMaterialMissing = binding.textInfoMaterialMissing;
            identity.textInfoCharacterSlotVerified = binding.textInfoCharacterSlotVerified;
            identity.textInfoCharacterMaterialVerified = binding.textInfoCharacterMaterialVerified;
            identity.textInfoFontAssetVerified = binding.textInfoFontAssetVerified;
            identity.textInfoAtlasVerified = binding.textInfoAtlasVerified;
            identity.textInfoCharacterCount = binding.textInfoCharacterCount;
            identity.textInfoVisibleCharacterCount = binding.textInfoVisibleCharacterCount;
            identity.sourceTextSha256 = binding.sourceTextSha256;
            identity.textInfoCharacterEvidenceSha256 = binding.textInfoCharacterEvidenceSha256;
            identity.textInfoCharacterAssetEvidenceSha256 = binding.textInfoCharacterAssetEvidenceSha256;
            identity.textInfoCharacterMaterialFingerprint = binding.textInfoCharacterMaterialFingerprint;
            identity.fontAsset = binding.fontAsset;
            identity.spriteAsset = binding.spriteAsset;
            identity.ownerFontSharedMaterial = binding.ownerFontSharedMaterial;
            identity.fallbackFontAsset = binding.fallbackFontAsset;
            identity.fallbackFontMaterial = binding.fallbackFontMaterial;
            identity.sourceMaterial = binding.tmpFallbackMaterialBaked ? null : binding.sourceMaterial;
            identity.proxyMaterial = binding.proxyMaterial;
            identity.sourceTexture = binding.sourceTexture;
            identity.tmpFallbackMaterialBaked = binding.tmpFallbackMaterialBaked;
            identity.persistentFallbackVariantRegistered = binding.persistentFallbackVariantRegistered;
            identity.tmpFallbackAlgorithm = binding.tmpFallbackAlgorithm;
            identity.tmpFallbackAtlasIndex = binding.tmpFallbackAtlasIndex;
            identity.ownerFontMaterialGuid = binding.ownerFontMaterialGuid;
            identity.ownerFontMaterialLocalFileId = binding.ownerFontMaterialLocalFileId;
            identity.ownerFontMaterialFingerprint = binding.ownerFontMaterialFingerprint;
            if (binding.ownerStyle != null)
            {
                identity.ownerStyleProfile = binding.ownerStyle.profile;
                identity.ownerStyleSourceComponentId = binding.ownerStyle.sourceComponentId;
                identity.ownerStyleOutlineWidth = binding.ownerStyle.outlineWidth;
                identity.ownerStyleOutlineColor = binding.ownerStyle.outlineColor;
                identity.ownerStyleSourceFontAsset = binding.ownerStyle.sourceFontAsset;
                identity.ownerStyleSourceFontAssetGuid = binding.ownerStyle.sourceFontAssetGuid;
                identity.ownerStyleSourceFontAssetLocalFileId = binding.ownerStyle.sourceFontAssetLocalFileId;
                identity.ownerStyleSourceFontMaterial = binding.ownerStyle.sourceFontMaterial;
                identity.ownerStyleSourceFontMaterialGuid = binding.ownerStyle.sourceFontMaterialGuid;
                identity.ownerStyleSourceFontMaterialLocalFileId = binding.ownerStyle.sourceFontMaterialLocalFileId;
                identity.ownerStyleSourceFontMaterialFingerprint = binding.ownerStyle.sourceFontMaterialFingerprint;
            }
            identity.fallbackFontAssetGuid = binding.fallbackFontAssetGuid;
            identity.fallbackFontAssetLocalFileId = binding.fallbackFontAssetLocalFileId;
            identity.fallbackFontMaterialGuid = binding.fallbackFontMaterialGuid;
            identity.fallbackFontMaterialLocalFileId = binding.fallbackFontMaterialLocalFileId;
            identity.fallbackFontMaterialFingerprint = binding.fallbackFontMaterialFingerprint;
            identity.fallbackAtlasGuid = binding.fallbackAtlasGuid;
            identity.fallbackAtlasLocalFileId = binding.fallbackAtlasLocalFileId;
            identity.transientFallbackFingerprint = binding.transientFallbackFingerprint;
            identity.bakedProxyMaterialFingerprint = binding.bakedProxyMaterialFingerprint;
            identity.bakedProxyMaterialGuid = binding.proxyMaterialGuid;
            identity.bakedProxyMaterialLocalFileId = binding.proxyMaterialLocalFileId;
            identity.fontAssetGuid = binding.fontAssetGuid; identity.fontAssetLocalFileId = binding.fontAssetLocalFileId;
            identity.spriteAssetGuid = binding.spriteAssetGuid; identity.spriteAssetLocalFileId = binding.spriteAssetLocalFileId;
            identity.sourceMaterialGuid = binding.sourceMaterialGuid; identity.sourceMaterialLocalFileId = binding.sourceMaterialLocalFileId;
            identity.sourceShaderGuid = binding.sourceShaderGuid; identity.sourceShaderLocalFileId = binding.sourceShaderLocalFileId;
            identity.sourceTextureGuid = binding.sourceTextureGuid; identity.sourceTextureLocalFileId = binding.sourceTextureLocalFileId;
            identity.sourceMaterialFingerprint = binding.sourceMaterialFingerprint;
            identity.sourceMeshSha256 = binding.sourceMeshSha256;
            identity.sourceSlotMesh = sourceSlotMesh;
            identity.sourceSlotMeshGuid = sourceSlotMeshGuid;
            identity.sourceSlotMeshLocalFileId = sourceSlotMeshLocalFileId;
            identity.sourceSlotMeshSha256 = binding.sourceMeshSha256;
            AssetIdentity(bakedProxyMesh, out identity.proxyMeshGuid, out identity.proxyMeshLocalFileId);
            identity.proxyMeshSha256 = expectedProxyMeshSha256;
            EditorUtility.SetDirty(identity);
            return identity;
        }

        static bool ReadAssetsAndMesh(NativeStaticSortTextSource identity, Mesh bakedProxyMesh,
            TextSourceReadback readback)
        {
            if (identity == null || bakedProxyMesh == null) return false;
            readback.materialGuid = identity.sourceMaterialGuid;
            readback.materialLocalFileId = identity.sourceMaterialLocalFileId;
            readback.proxyMaterialGuid = identity.bakedProxyMaterialGuid;
            readback.proxyMaterialLocalFileId = identity.bakedProxyMaterialLocalFileId;
            readback.ownerFontMaterialGuid = identity.ownerFontMaterialGuid;
            readback.ownerFontMaterialLocalFileId = identity.ownerFontMaterialLocalFileId;
            readback.ownerStyleProfile = identity.ownerStyleProfile;
            readback.ownerStyleSourceComponentId = identity.ownerStyleSourceComponentId;
            readback.ownerStyleOutlineWidth = identity.ownerStyleOutlineWidth;
            readback.ownerStyleOutlineColor = identity.ownerStyleOutlineColor;
            readback.ownerStyleSourceFontAssetGuid = identity.ownerStyleSourceFontAssetGuid;
            readback.ownerStyleSourceFontAssetLocalFileId = identity.ownerStyleSourceFontAssetLocalFileId;
            readback.ownerStyleSourceFontMaterialGuid = identity.ownerStyleSourceFontMaterialGuid;
            readback.ownerStyleSourceFontMaterialLocalFileId = identity.ownerStyleSourceFontMaterialLocalFileId;
            readback.ownerStyleSourceFontMaterialFingerprint = identity.ownerStyleSourceFontMaterialFingerprint;
            readback.sourceMeshSha256 = MeshFingerprint(identity.sourceSlotMesh);
            readback.proxyMeshSha256 = MeshFingerprint(bakedProxyMesh);
            readback.fallbackFontAssetGuid = identity.fallbackFontAssetGuid;
            readback.fallbackFontAssetLocalFileId = identity.fallbackFontAssetLocalFileId;
            readback.fallbackFontMaterialGuid = identity.fallbackFontMaterialGuid;
            readback.fallbackFontMaterialLocalFileId = identity.fallbackFontMaterialLocalFileId;
            readback.fallbackAtlasGuid = identity.fallbackAtlasGuid;
            readback.fallbackAtlasLocalFileId = identity.fallbackAtlasLocalFileId;
            readback.tmpFallbackAlgorithm = identity.tmpFallbackAlgorithm;
            readback.persistentFallbackVariantRegistered = identity.persistentFallbackVariantRegistered;
            readback.textSlotEnumeration = identity.textSlotEnumeration;
            readback.transientFallbackFingerprint = identity.transientFallbackFingerprint;
            readback.sourceMaterialFingerprint = identity.sourceMaterialFingerprint;
            readback.textInfoMaterialMissing = identity.textInfoMaterialMissing;
            readback.textInfoCharacterSlotVerified = identity.textInfoCharacterSlotVerified;
            readback.textInfoCharacterMaterialVerified = identity.textInfoCharacterMaterialVerified;
            readback.textInfoFontAssetVerified = identity.textInfoFontAssetVerified;
            readback.textInfoAtlasVerified = identity.textInfoAtlasVerified;
            readback.textInfoCharacterCount = identity.textInfoCharacterCount;
            readback.textInfoVisibleCharacterCount = identity.textInfoVisibleCharacterCount;
            readback.sourceTextSha256 = identity.sourceTextSha256;
            readback.textInfoCharacterEvidenceSha256 = identity.textInfoCharacterEvidenceSha256;
            readback.textInfoCharacterAssetEvidenceSha256 = identity.textInfoCharacterAssetEvidenceSha256;
            readback.textInfoCharacterMaterialFingerprint = identity.textInfoCharacterMaterialFingerprint;
            readback.ownerFontMaterialFingerprint = identity.ownerFontMaterialFingerprint;
            readback.fallbackFontMaterialFingerprint = identity.fallbackFontMaterialFingerprint;
            readback.bakedProxyMaterialFingerprint = identity.bakedProxyMaterialFingerprint;
            readback.fontAssetVerified = identity.fontAsset == null
                ? String.IsNullOrEmpty(identity.fontAssetGuid) && identity.fontAssetLocalFileId == 0
                : SameIdentity(identity.fontAsset, identity.fontAssetGuid, identity.fontAssetLocalFileId,
                    out readback.fontAssetGuid, out readback.fontAssetLocalFileId);
            readback.spriteAssetVerified = identity.spriteAsset == null
                ? String.IsNullOrEmpty(identity.spriteAssetGuid) && identity.spriteAssetLocalFileId == 0
                : SameIdentity(identity.spriteAsset, identity.spriteAssetGuid, identity.spriteAssetLocalFileId,
                    out readback.spriteAssetGuid, out readback.spriteAssetLocalFileId);
            readback.ownerFontMaterialVerified = identity.ownerFontSharedMaterial != null &&
                SameIdentity(identity.ownerFontSharedMaterial, identity.ownerFontMaterialGuid, identity.ownerFontMaterialLocalFileId,
                    out readback.ownerFontMaterialGuid, out readback.ownerFontMaterialLocalFileId) &&
                MaterialFingerprint(identity.ownerFontSharedMaterial) == identity.ownerFontMaterialFingerprint;
            var hasOwnerStyle = !String.IsNullOrEmpty(identity.ownerStyleProfile);
            var styleFont = identity.ownerStyleSourceFontAsset;
            var styleBase = identity.ownerStyleSourceFontMaterial;
            var expectedStyleWidth = styleFont != null && styleBase != null && styleBase.HasProperty("_GradientScale") &&
                styleBase.GetFloat("_GradientScale") > 1f && identity.sourceOwner != null && identity.sourceOwner.fontSize > 0f
                    ? identity.ownerStyleOutlineWidth * styleFont.faceInfo.pointSize / identity.sourceOwner.fontSize /
                      (styleBase.GetFloat("_GradientScale") - 1f) : Single.NaN;
            readback.ownerStyleVerified = !hasOwnerStyle
                ? String.IsNullOrEmpty(identity.ownerStyleSourceComponentId) && styleFont == null && styleBase == null &&
                  String.IsNullOrEmpty(identity.ownerStyleSourceFontAssetGuid) && identity.ownerStyleSourceFontAssetLocalFileId == 0 &&
                  String.IsNullOrEmpty(identity.ownerStyleSourceFontMaterialGuid) && identity.ownerStyleSourceFontMaterialLocalFileId == 0 &&
                  String.IsNullOrEmpty(identity.ownerStyleSourceFontMaterialFingerprint) && identity.ownerStyleOutlineWidth == 0f &&
                  identity.ownerStyleOutlineColor == default(Color)
                : identity.ownerStyleProfile == "native-static-text-outline-font-material-v1" &&
                  identity.ownerStyleSourceComponentId == identity.sourceComponentId && identity.sourceOwner != null &&
                  identity.sourceOwner.font == styleFont && PersistentAsset(styleFont, out var styleFontGuid, out var styleFontFileId) &&
                  styleFontGuid == identity.ownerStyleSourceFontAssetGuid && styleFontFileId == identity.ownerStyleSourceFontAssetLocalFileId &&
                  styleFont.material == styleBase && SameIdentity(styleBase, identity.ownerStyleSourceFontMaterialGuid,
                      identity.ownerStyleSourceFontMaterialLocalFileId, out _, out _) &&
                  MaterialFingerprint(styleBase) == identity.ownerStyleSourceFontMaterialFingerprint &&
                  !Single.IsNaN(expectedStyleWidth) && !Single.IsInfinity(expectedStyleWidth) &&
                  identity.ownerFontSharedMaterial != null && identity.ownerFontSharedMaterial.HasProperty("_OutlineWidth") &&
                  identity.ownerFontSharedMaterial.HasProperty("_OutlineColor") &&
                  Mathf.Approximately(identity.ownerFontSharedMaterial.GetFloat("_OutlineWidth"), expectedStyleWidth) &&
                  identity.ownerFontSharedMaterial.GetColor("_OutlineColor") == identity.ownerStyleOutlineColor &&
                  identity.sourceOwner.fontSharedMaterial == identity.ownerFontSharedMaterial &&
                  (!identity.ownerFontSharedMaterial.HasProperty("_FaceDilate") || !styleBase.HasProperty("_FaceDilate") ||
                   Mathf.Approximately(identity.ownerFontSharedMaterial.GetFloat("_FaceDilate"), styleBase.GetFloat("_FaceDilate")));
            readback.fallbackFontAssetVerified = identity.fallbackFontAsset == null
                ? String.IsNullOrEmpty(identity.fallbackFontAssetGuid) && identity.fallbackFontAssetLocalFileId == 0
                : SameIdentity(identity.fallbackFontAsset, identity.fallbackFontAssetGuid, identity.fallbackFontAssetLocalFileId,
                    out readback.fallbackFontAssetGuid, out readback.fallbackFontAssetLocalFileId);
            readback.fallbackFontMaterialVerified = identity.fallbackFontMaterial == null
                ? String.IsNullOrEmpty(identity.fallbackFontMaterialGuid) && identity.fallbackFontMaterialLocalFileId == 0
                : SameIdentity(identity.fallbackFontMaterial, identity.fallbackFontMaterialGuid, identity.fallbackFontMaterialLocalFileId,
                    out readback.fallbackFontMaterialGuid, out readback.fallbackFontMaterialLocalFileId) &&
                  MaterialFingerprint(identity.fallbackFontMaterial) == identity.fallbackFontMaterialFingerprint;
            var fallbackAtlas = identity.fallbackFontAsset != null && identity.fallbackFontAsset.atlasTextures != null &&
                identity.tmpFallbackAtlasIndex >= 0 && identity.tmpFallbackAtlasIndex < identity.fallbackFontAsset.atlasTextures.Length
                    ? identity.fallbackFontAsset.atlasTextures[identity.tmpFallbackAtlasIndex] : null;
            readback.fallbackAtlasVerified = !identity.tmpFallbackMaterialBaked ||
                (fallbackAtlas != null && fallbackAtlas == identity.sourceTexture &&
                 SameIdentity(fallbackAtlas, identity.fallbackAtlasGuid, identity.fallbackAtlasLocalFileId,
                     out readback.fallbackAtlasGuid, out readback.fallbackAtlasLocalFileId));
            readback.materialVerified = identity.tmpFallbackMaterialBaked
                ? identity.sourceMaterial == null && String.IsNullOrEmpty(identity.sourceMaterialGuid) &&
                  identity.sourceMaterialLocalFileId == 0 && IsSha256(identity.sourceMaterialFingerprint) &&
                  identity.sourceMaterialFingerprint == identity.transientFallbackFingerprint
                : SameIdentity(identity.sourceMaterial, identity.sourceMaterialGuid, identity.sourceMaterialLocalFileId,
                    out readback.materialGuid, out readback.materialLocalFileId) &&
                  MaterialFingerprint(identity.sourceMaterial) == identity.sourceMaterialFingerprint;
            var sourceShader = identity.proxyMaterial == null ? null : identity.proxyMaterial.shader;
            readback.shaderVerified = sourceShader != null && SameIdentity(sourceShader,
                identity.sourceShaderGuid, identity.sourceShaderLocalFileId, out readback.shaderGuid, out readback.shaderLocalFileId);
            var textureFromMaterial = identity.proxyMaterial == null ? null : identity.proxyMaterial.GetTexture(MainTex);
            readback.textureVerified = textureFromMaterial != null && textureFromMaterial == identity.sourceTexture &&
                SameIdentity(identity.sourceTexture, identity.sourceTextureGuid, identity.sourceTextureLocalFileId,
                    out readback.textureGuid, out readback.textureLocalFileId) &&
                TextureBelongsToSourceAsset(identity.fontAsset, identity.spriteAsset, identity.sourceTexture);
            readback.proxyMaterialVerified = SameIdentity(identity.proxyMaterial, identity.bakedProxyMaterialGuid,
                identity.bakedProxyMaterialLocalFileId, out readback.proxyMaterialGuid, out readback.proxyMaterialLocalFileId) &&
                MaterialFingerprint(identity.proxyMaterial) == identity.bakedProxyMaterialFingerprint &&
                identity.proxyMaterial.GetTexture(MainTex) == identity.sourceTexture;
            if (identity.tmpFallbackMaterialBaked)
            {
                var outlineSuffix = "+native-static-text-outline-v1";
                var hasOutlineSuffix = identity.tmpFallbackAlgorithm != null && identity.tmpFallbackAlgorithm.EndsWith(outlineSuffix, StringComparison.Ordinal);
                var baseAlgorithm = hasOutlineSuffix
                    ? identity.tmpFallbackAlgorithm.Substring(0, identity.tmpFallbackAlgorithm.Length - outlineSuffix.Length)
                    : identity.tmpFallbackAlgorithm;
                var knownAlgorithm = baseAlgorithm == "tmpro-fallback-font-material-v1" ||
                    baseAlgorithm == "tmpro-fallback-font-material-v1+tmpro-multi-atlas-v1" ||
                    baseAlgorithm == "tmpro-multi-atlas-v1";
                var fallbackAssetDiffers = identity.sourceOwner != null && identity.fallbackFontAsset != null &&
                    identity.fallbackFontAsset != identity.sourceOwner.font;
                knownAlgorithm = knownAlgorithm &&
                    (baseAlgorithm == "tmpro-fallback-font-material-v1" && fallbackAssetDiffers && identity.tmpFallbackAtlasIndex == 0 ||
                     baseAlgorithm == "tmpro-fallback-font-material-v1+tmpro-multi-atlas-v1" && fallbackAssetDiffers && identity.tmpFallbackAtlasIndex > 0 ||
                     baseAlgorithm == "tmpro-multi-atlas-v1" && !fallbackAssetDiffers && identity.tmpFallbackAtlasIndex > 0) &&
                    (!hasOutlineSuffix || !String.IsNullOrEmpty(identity.ownerStyleProfile)) &&
                    identity.persistentFallbackVariantRegistered == hasOutlineSuffix;
                readback.tmpFallbackDescriptorVerified = knownAlgorithm && readback.ownerFontMaterialVerified &&
                    readback.fallbackFontAssetVerified && readback.fallbackFontMaterialVerified && readback.fallbackAtlasVerified &&
                    IsSha256(identity.transientFallbackFingerprint) &&
                    identity.bakedProxyMaterialFingerprint == identity.transientFallbackFingerprint &&
                    identity.sourceMaterialFingerprint == identity.transientFallbackFingerprint;
                readback.proxyMaterialVerified = readback.proxyMaterialVerified &&
                    identity.bakedProxyMaterialFingerprint == identity.transientFallbackFingerprint;
            }
            else
            {
                readback.tmpFallbackDescriptorVerified = !identity.tmpFallbackMaterialBaked &&
                    identity.proxyMaterial == identity.sourceMaterial &&
                    identity.bakedProxyMaterialFingerprint == identity.sourceMaterialFingerprint;
                readback.proxyMaterialVerified = readback.proxyMaterialVerified &&
                    identity.bakedProxyMaterialFingerprint == identity.sourceMaterialFingerprint;
            }
            readback.transientFallbackVerified = !identity.tmpFallbackMaterialBaked ||
                (readback.tmpFallbackDescriptorVerified && identity.transientFallbackFingerprint == identity.bakedProxyMaterialFingerprint);
            readback.bakedProxyMeshVerified = PersistentAsset(bakedProxyMesh, out readback.proxyMeshGuid,
                out readback.proxyMeshLocalFileId) && readback.proxyMeshGuid == identity.proxyMeshGuid &&
                readback.proxyMeshLocalFileId == identity.proxyMeshLocalFileId &&
                readback.proxyMeshSha256 == identity.proxyMeshSha256;
            readback.sourceMeshContextEvidenceSha256 = identity.textScaleContext == null
                ? null : identity.textScaleContext.evidenceSha256;
            readback.sourceMeshContextFormula = identity.textScaleContext == null
                ? null : identity.textScaleContext.formula;
            readback.sourceSlotMeshGuid = identity.sourceSlotMeshGuid;
            readback.sourceSlotMeshLocalFileId = identity.sourceSlotMeshLocalFileId;
            readback.sourceSlotMeshSha256 = identity.sourceSlotMeshSha256;
            readback.sourceSlotMeshVerified = identity.sourceSlotMesh != null &&
                identity.sourceSlotMeshSha256 == identity.sourceMeshSha256 &&
                MeshFingerprint(identity.sourceSlotMesh) == identity.sourceMeshSha256 &&
                PersistentAsset(identity.sourceSlotMesh, out var sourceSlotMeshGuid, out var sourceSlotMeshLocalFileId) &&
                sourceSlotMeshGuid == identity.sourceSlotMeshGuid &&
                sourceSlotMeshLocalFileId == identity.sourceSlotMeshLocalFileId;
            var capturedScaleFormulaDiagnostic = "captured-source-slot-mesh-reference-unverified";
            var capturedContextMatchesMesh = TextScaleContextUvMatchesMesh(identity.textScaleContext,
                identity.sourceSlotMesh, out capturedScaleFormulaDiagnostic);
            readback.sourceMeshContextVerified = readback.sourceSlotMeshVerified && capturedContextMatchesMesh &&
                identity.textScaleContext.sourceComponentId == identity.sourceComponentId &&
                identity.textScaleContext.sourceTextSha256 == identity.sourceTextSha256 &&
                identity.textScaleContext.materialSlot == identity.materialSlot;
            readback.sourceMeshContextDiagnostic = readback.sourceMeshContextVerified
                ? "captured-source-slot-mesh-and-uv-context-exact;source-sdk-equation-deferred-unless-loaded-source-mesh-differs"
                : capturedScaleFormulaDiagnostic + ";proxyHash=" + (identity.proxyMeshSha256 ?? "null") +
                    ";sourceSlotHash=" + (identity.sourceMeshSha256 ?? "null");
            var sourceHashOK = IsSha256(identity.sourceMeshSha256);
            NativeStaticSortTextSlotEvidence storedSlotEvidence = null;
            if (identity.textSlotEnumeration != null && identity.materialSlot >= 0 &&
                identity.materialSlot < identity.textSlotEnumeration.rows.Length)
                storedSlotEvidence = identity.textSlotEnumeration.rows[identity.materialSlot];
            var storedSlotAssetGuid = identity.spriteAsset != null ? identity.spriteAssetGuid : identity.fontAssetGuid;
            var storedSlotAssetLocalId = identity.spriteAsset != null
                ? identity.spriteAssetLocalFileId : identity.fontAssetLocalFileId;
            var storedSlotAssetKind = identity.spriteAsset != null ? "sprite" : "font";
            var storedSlotCacheFingerprintMatches = storedSlotEvidence != null &&
                (identity.textInfoMaterialMissing
                    ? String.IsNullOrEmpty(storedSlotEvidence.textInfoMaterialFingerprint)
                    : storedSlotEvidence.textInfoMaterialFingerprint == identity.textInfoCharacterMaterialFingerprint);
            readback.persistentTextSlotContractVerified = storedSlotEvidence != null &&
                storedSlotEvidence.disposition == "drawable" && storedSlotEvidence.slot == identity.materialSlot &&
                storedSlotEvidence.sourceAssetKind == storedSlotAssetKind &&
                storedSlotEvidence.sourceAssetGuid == storedSlotAssetGuid &&
                storedSlotEvidence.sourceAssetLocalFileId == storedSlotAssetLocalId &&
                storedSlotEvidence.atlasGuid == identity.sourceTextureGuid &&
                storedSlotEvidence.atlasLocalFileId == identity.sourceTextureLocalFileId &&
                storedSlotEvidence.characterReferences == identity.textInfoCharacterCount &&
                storedSlotEvidence.visibleCharacterReferences == identity.textInfoVisibleCharacterCount &&
                storedSlotEvidence.textInfoMaterialMissing == identity.textInfoMaterialMissing &&
                storedSlotCacheFingerprintMatches &&
                storedSlotEvidence.characterEvidenceSha256 == identity.textInfoCharacterEvidenceSha256 &&
                storedSlotEvidence.characterAssetEvidenceSha256 == identity.textInfoCharacterAssetEvidenceSha256 &&
                storedSlotEvidence.sourceGraphicMaterialFingerprint == identity.sourceMaterialFingerprint &&
                storedSlotEvidence.sourceMeshSha256 == identity.sourceMeshSha256 && sourceHashOK;
            return readback.fontAssetVerified && readback.spriteAssetVerified && readback.materialVerified &&
                identity.textInfoCharacterSlotVerified && identity.textInfoCharacterMaterialVerified &&
                identity.textInfoFontAssetVerified && identity.textInfoAtlasVerified &&
                identity.textInfoCharacterCount > 0 && identity.textInfoVisibleCharacterCount > 0 &&
                IsSha256(identity.sourceTextSha256) && identity.sourceOwner != null &&
                HashText(identity.sourceOwner.text ?? String.Empty) == identity.sourceTextSha256 &&
                IsSha256(identity.textInfoCharacterEvidenceSha256) && IsSha256(identity.textInfoCharacterMaterialFingerprint) &&
                readback.ownerStyleVerified &&
                IsValidTextSlotEnumeration(identity.textSlotEnumeration) &&
                identity.textSlotEnumeration.sourceComponentId == identity.sourceComponentId &&
                identity.textSlotEnumeration.sourceTextSha256 == identity.sourceTextSha256 &&
                identity.materialSlot >= 0 && identity.materialSlot < identity.textSlotEnumeration.rows.Length &&
                identity.textSlotEnumeration.rows[identity.materialSlot].disposition == "drawable" &&
                readback.persistentTextSlotContractVerified &&
                readback.ownerFontMaterialVerified && readback.fallbackFontAssetVerified && readback.fallbackFontMaterialVerified &&
                readback.fallbackAtlasVerified && readback.tmpFallbackDescriptorVerified && readback.proxyMaterialVerified &&
                readback.shaderVerified && readback.textureVerified && readback.bakedProxyMeshVerified && sourceHashOK &&
                readback.sourceSlotMeshVerified && readback.sourceMeshContextVerified;
        }

        static bool IsSha256(string value)
        {
            return value != null && value.Length == 64 && value.All(Uri.IsHexDigit);
        }

        public static bool ReadPersistent(NativeStaticSortTextSource identity, Mesh bakedProxyMesh,
            TMP_Text expectedOwner, string expectedSourceComponentId, string expectedOwnerGuid,
            long expectedOwnerLocalFileId, out TextSourceReadback readback)
        {
            readback = new TextSourceReadback { diagnostic = "TMP_SORT_PERSISTENT_READBACK_FAILED" };
            if (identity == null || bakedProxyMesh == null) return false;
            readback.sourceComponentId = identity.sourceComponentId;
            readback.materialSlot = identity.materialSlot;
            readback.sourceMeshSha256 = identity.sourceMeshSha256;
            readback.currentSourceMeshSha256 = identity.sourceMeshSha256;
            var ownerRefMatches = expectedOwner != null && identity.sourceOwner == expectedOwner &&
                identity.sourceComponentId == expectedSourceComponentId;
            var ownerAssetMatches = ownerRefMatches && AssetIdentity(expectedOwner, out readback.ownerGuid, out readback.ownerLocalFileId) &&
                readback.ownerGuid == expectedOwnerGuid && readback.ownerLocalFileId == expectedOwnerLocalFileId;
            readback.ownerScopeVerified = ownerAssetMatches;
            readback.persistentReferencesVerified = ownerAssetMatches &&
                AssetIdentity(identity, out var identityGuid, out var identityFileId) && identityFileId != 0;
            var resourcesVerified = ReadAssetsAndMesh(identity, bakedProxyMesh, readback);
            // Persistent prefab validation covers the saved typed source owner,
            // serialized slot enumeration, resource identities and mesh hash.
            // TMP's textInfo.meshInfo/material cache and generated TMP_SubMeshUI
            // are runtime activation state and can legitimately be absent before
            // the prefab is initialized. The loaded/initialized path below still
            // has to regenerate and prove the exact live slot.
            readback.generatedSlotResolved = false;
            readback.sourceMeshVerified = readback.persistentTextSlotContractVerified;
            var textInfoScopeVerified = readback.persistentTextSlotContractVerified;
            var textInfoDiagnostic = textInfoScopeVerified ? null :
                "TMP_SORT_PERSISTENT_STORED_TEXT_SLOT_CONTRACT_MISMATCH:" + identity.materialSlot;
            readback.verified = readback.ownerScopeVerified && readback.persistentReferencesVerified &&
                resourcesVerified && textInfoScopeVerified;
            readback.diagnostic = readback.verified ? null : "TMP_SORT_PERSISTENT_OWNER_SCOPE_OR_ASSET_MATERIAL_ATLAS_MESH_MISMATCH" +
                (String.IsNullOrEmpty(textInfoDiagnostic) ? "" : ";textInfo=" + textInfoDiagnostic);
            return readback.verified;
        }

        static bool TryNormalizeCurrentTextMeshRows(List<TextSlotBinding> currentSlots,
            NativeStaticSortTextSlotEnumeration currentEnumeration, NativeStaticSortTextSource requestedIdentity,
            NativeStaticSortQueueProxyPresenter presenter, out string diagnostic)
        {
            diagnostic = null;
            if (currentSlots == null || !IsValidTextSlotEnumeration(currentEnumeration) ||
                !IsValidTextSlotEnumeration(requestedIdentity == null ? null : requestedIdentity.textSlotEnumeration))
            { diagnostic = "slot-enumeration-invalid"; return false; }
            var savedEnumeration = requestedIdentity.textSlotEnumeration;
            if (currentEnumeration.sourceComponentId != savedEnumeration.sourceComponentId ||
                currentEnumeration.sourceTextSha256 != savedEnumeration.sourceTextSha256 ||
                currentEnumeration.slotCount != savedEnumeration.slotCount)
            { diagnostic = "slot-enumeration-denominator-changed"; return false; }

            var normalizedSlots = new List<string>();
            for (var rowIndex = 0; rowIndex < savedEnumeration.rows.Length; rowIndex++)
            {
                var savedRow = savedEnumeration.rows[rowIndex];
                var currentRow = currentEnumeration.rows[rowIndex];
                if (savedRow.slot != currentRow.slot || savedRow.disposition != currentRow.disposition)
                { diagnostic = "slot-or-disposition-changed:" + rowIndex; return false; }
                var slotBinding = currentSlots.SingleOrDefault(candidate => candidate.materialSlot == currentRow.slot);
                if (slotBinding != null) slotBinding.currentSourceMeshSha256 = slotBinding.sourceMeshSha256;
                if (savedRow.sourceMeshSha256 == currentRow.sourceMeshSha256)
                {
                    if (slotBinding != null)
                    {
                        slotBinding.sourceMeshContextDerivedVerified = false;
                        slotBinding.sourceMeshContextDiagnostic = "raw-mesh-sha256-exact";
                    }
                    continue;
                }
                if (savedRow.disposition != "drawable" || slotBinding == null)
                { diagnostic = "non-drawable-or-unbound-slot-mesh-changed:" + currentRow.slot; return false; }
                NativeStaticSortTextSource savedIdentity = null;
                if (requestedIdentity.materialSlot == currentRow.slot) savedIdentity = requestedIdentity;
                else if (presenter != null && presenter.proxyRoot != null)
                {
                    var siblingIdentities = presenter.proxyRoot.GetComponentsInChildren<NativeStaticSortTextSource>(true)
                        .Where(candidate => candidate != null && candidate.sourceComponentId == currentEnumeration.sourceComponentId &&
                            candidate.materialSlot == currentRow.slot && candidate.sourceOwner == requestedIdentity.sourceOwner).ToArray();
                    if (siblingIdentities.Length == 1) savedIdentity = siblingIdentities[0];
                    else
                    { diagnostic = "saved-slot-identity-not-unique:" + currentRow.slot + ":" + siblingIdentities.Length; return false; }
                }
                var currentContext = (NativeStaticSortTextScaleContext)null;
                var formulaDiagnostic = "saved-identity-missing";
                if (savedIdentity == null ||
                    !VerifyLoadedTextMeshContext(slotBinding, savedIdentity, out currentContext, out formulaDiagnostic))
                {
                    diagnostic = "sdk-scale-context-proof-failed:" + currentRow.slot + ":" +
                        (savedIdentity == null ? "saved-identity-missing" : formulaDiagnostic);
                    return false;
                }
                slotBinding.currentSourceMeshSha256 = slotBinding.sourceMeshSha256;
                slotBinding.sourceMeshContextDerivedVerified = true;
                slotBinding.currentTextScaleContext = currentContext;
                slotBinding.sourceMeshContextDiagnostic = formulaDiagnostic;
                if (slotBinding.sourceMeshPositionsDiffer &&
                    (!slotBinding.sourceMeshGeneratedByTmpVerified ||
                     String.IsNullOrWhiteSpace(slotBinding.sourceMeshPositionPairEvidenceSha256) ||
                     String.IsNullOrWhiteSpace(slotBinding.sourceMeshRegenerationEvidenceSha256)))
                { diagnostic = "source-position-regeneration-evidence-incomplete:" + currentRow.slot; return false; }
                slotBinding.sourceMeshSha256 = savedRow.sourceMeshSha256;
                currentRow.sourceMeshSha256 = savedRow.sourceMeshSha256;
                currentRow.evidenceSha256 = TextSlotRowHash(currentRow);
                normalizedSlots.Add(currentRow.slot + ":" + slotBinding.currentSourceMeshSha256);
            }
            currentEnumeration.evidenceSha256 = TextSlotEnumerationHash(currentEnumeration);
            currentEnumeration.verified = IsValidTextSlotEnumeration(currentEnumeration);
            if (!currentEnumeration.verified)
            { diagnostic = "normalized-enumeration-hash-invalid"; return false; }
            diagnostic = normalizedSlots.Count == 0 ? "raw-mesh-hashes-exact" :
                "source-slot-native-regeneration-proved:" + String.Join("|", normalizedSlots);
            return true;
        }

        public static bool ResolveGeneratedSlot(NativeStaticSortTextSource identity, TMP_Text expectedOwner,
            string expectedSourceComponentId, out TextSlotBinding binding, out string diagnostic)
        {
            return ResolveGeneratedSlot(identity, expectedOwner, expectedSourceComponentId, null, out binding, out diagnostic);
        }

        public static bool ResolveGeneratedSlot(NativeStaticSortTextSource identity, TMP_Text expectedOwner,
            string expectedSourceComponentId, NativeStaticSortQueueProxyPresenter presenter,
            out TextSlotBinding binding, out string diagnostic)
        {
            binding = null; diagnostic = null;
            if (identity == null || expectedOwner == null || identity.sourceOwner != expectedOwner ||
                identity.sourceComponentId != expectedSourceComponentId)
                return Fail("TMP_SORT_GENERATED_OWNER_SCOPE_MISMATCH", out diagnostic);
            if (presenter != null && (presenter.sourceRoot == null || presenter.proxyRoot == null ||
                presenter.gameObject != presenter.proxyRoot || identity.gameObject.transform.root != presenter.proxyRoot.transform.root ||
                !(expectedOwner.transform == presenter.sourceRoot.transform || expectedOwner.transform.IsChildOf(presenter.sourceRoot.transform))))
                return Fail("TMP_SORT_GENERATED_PRESENTER_ROOT_SCOPE_MISMATCH", out diagnostic);
            // TMP can recreate DontSave TMP_SubMeshUI children during
            // ForceMeshUpdate. Recollect their prior cull state and suppress
            // those exact current source Graphics before checking slots.
            // Existing identities retain their originally observed cull state.
            if (presenter != null) presenter.RefreshSourceSuppression();
            if (!GetCurrentSlots(expectedOwner, expectedSourceComponentId, presenter, presenter == null ? null : identity, out var currentSlots,
                out var currentEnumeration, out diagnostic)) return false;
            binding = currentSlots.SingleOrDefault(candidate => candidate.materialSlot == identity.materialSlot);
            if (binding == null)
                return Fail("TMP_SORT_GENERATED_SLOT_NOT_UNIQUE:" + identity.materialSlot + ":0", out diagnostic);
            if (currentEnumeration == null || binding.textSlotEnumeration == null)
                return Fail("TMP_SORT_GENERATED_SLOT_ENUMERATION_BINDING_MISMATCH:" + identity.materialSlot, out diagnostic);
            if (!TryNormalizeCurrentTextMeshRows(currentSlots, currentEnumeration, identity, presenter,
                    out var meshContextDiagnostic))
                return Fail("TMP_SORT_GENERATED_SLOT_RESOURCE_IDENTITY_CHANGED:" + identity.materialSlot +
                    ";sourceMeshContext=" + meshContextDiagnostic + ";" +
                    BindingIdentityMismatchSummary(binding, identity), out diagnostic);
            if (currentEnumeration.evidenceSha256 != binding.textSlotEnumeration.evidenceSha256)
                return Fail("TMP_SORT_GENERATED_SLOT_ENUMERATION_BINDING_MISMATCH:" + identity.materialSlot, out diagnostic);
            binding.ownerStyle = OwnerStyleFromIdentity(identity);
            if (!BindingMatchesIdentity(binding, identity))
            {
                var mismatchSummary = BindingIdentityMismatchSummary(binding, identity);
                binding = null;
                return Fail("TMP_SORT_GENERATED_SLOT_RESOURCE_IDENTITY_CHANGED:" + identity.materialSlot + ";" + mismatchSummary, out diagnostic);
            }
            return true;
        }

        public static bool ReadInitialized(NativeStaticSortTextSource identity, Mesh bakedProxyMesh,
            TMP_Text expectedOwner, string expectedSourceComponentId, out TextSourceReadback readback)
        {
            return ReadInitialized(identity, bakedProxyMesh, expectedOwner, expectedSourceComponentId, null, out readback);
        }

        public static bool ReadInitialized(NativeStaticSortTextSource identity, Mesh bakedProxyMesh,
            TMP_Text expectedOwner, string expectedSourceComponentId,
            NativeStaticSortQueueProxyPresenter presenter, out TextSourceReadback readback)
        {
            readback = new TextSourceReadback { diagnostic = "TMP_SORT_INITIALIZED_READBACK_FAILED" };
            if (identity == null || bakedProxyMesh == null || expectedOwner == null) return false;
            readback.sourceComponentId = identity.sourceComponentId;
            readback.materialSlot = identity.materialSlot;
            readback.sourceMeshSha256 = identity.sourceMeshSha256;
            readback.ownerScopeVerified = identity.sourceOwner == expectedOwner &&
                identity.sourceComponentId == expectedSourceComponentId;
            readback.persistentReferencesVerified = readback.ownerScopeVerified;
            var resourcesVerified = ReadAssetsAndMesh(identity, bakedProxyMesh, readback);
            if (!readback.ownerScopeVerified || !resourcesVerified)
            {
                readback.diagnostic = "TMP_SORT_INITIALIZED_OWNER_SCOPE_OR_ASSET_MATERIAL_ATLAS_MESH_MISMATCH";
                return false;
            }
            if (!PrepareSource(expectedOwner, expectedSourceComponentId, out var prepareDiagnostic))
            {
                readback.diagnostic = prepareDiagnostic;
                return false;
            }
            if (!ResolveGeneratedSlot(identity, expectedOwner, expectedSourceComponentId, presenter, out var binding, out var diagnostic))
            {
                readback.generatedSlotResolved = false;
                readback.diagnostic = diagnostic;
                return false;
            }
            readback.generatedSlotResolved = true;
            readback.sourceRendererSuppressionVerified = binding.sourceRendererSuppressionVerified;
            readback.sourceRectMaskCullVerified = binding.sourceRectMaskCullVerified;
            readback.sourceCanvasCullBeforeCaptured = binding.sourceCanvasCullBeforeCaptured;
            readback.sourceCanvasCullBeforeRuntime = binding.sourceCanvasCullBeforeRuntime;
            readback.currentTextSlotEnumeration = binding.textSlotEnumeration;
            readback.currentSourceMeshSha256 = binding.currentSourceMeshSha256 ?? binding.sourceMeshSha256;
            readback.sourceMeshContextDerivedVerified = binding.sourceMeshContextDerivedVerified;
            readback.sourceMeshRegeneratedFromCurrentTmpVerified = binding.sourceMeshPositionsDiffer &&
                binding.sourceMeshGeneratedByTmpVerified && !String.IsNullOrWhiteSpace(binding.sourceMeshRegenerationEvidenceSha256);
            readback.sourceMeshPositionPairEvidenceSha256 = binding.sourceMeshPositionPairEvidenceSha256;
            readback.sourceMeshRegenerationEvidenceSha256 = binding.sourceMeshRegenerationEvidenceSha256;
            readback.sourceMeshRegenerationDiagnostic = binding.sourceMeshRegenerationDiagnostic;
            readback.sourceMeshContextVerified = readback.sourceMeshContextVerified &&
                (readback.currentSourceMeshSha256 == identity.sourceMeshSha256 || binding.sourceMeshContextDerivedVerified);
            readback.sourceMeshContextDiagnostic = binding.sourceMeshContextDiagnostic ?? readback.sourceMeshContextDiagnostic;
            readback.sourceMeshContextFormula = binding.currentTextScaleContext == null ?
                (identity.textScaleContext == null ? null : identity.textScaleContext.formula) :
                binding.currentTextScaleContext.formula;
            readback.sourceStateVerified = binding.sourceGraphicEnabled == identity.sourceGraphicEnabled &&
                binding.sourceGraphicActiveSelf == identity.sourceGraphicActiveSelf;
            readback.sourceMeshVerified = binding.sourceMeshSha256 == identity.sourceMeshSha256;
            readback.actualTransientMaterialFingerprint = MaterialFingerprint(binding.sourceMaterial);
            readback.transientFallbackVerified = identity.tmpFallbackMaterialBaked
                ? readback.actualTransientMaterialFingerprint == identity.transientFallbackFingerprint &&
                  readback.tmpFallbackDescriptorVerified
                : readback.actualTransientMaterialFingerprint == identity.sourceMaterialFingerprint;
            readback.verified = readback.ownerScopeVerified && resourcesVerified && readback.generatedSlotResolved &&
                readback.sourceStateVerified && readback.sourceMeshVerified && readback.sourceMeshContextVerified &&
                readback.transientFallbackVerified;
            readback.diagnostic = readback.verified ? null : "TMP_SORT_INITIALIZED_SLOT_STATE_OR_MESH_CHANGED";
            return readback.verified;
        }

        static bool BindingMatchesIdentity(TextSlotBinding binding, NativeStaticSortTextSource identity)
        {
            var sourceMaterialMatches = binding != null && identity != null &&
                (identity.tmpFallbackMaterialBaked
                    ? identity.persistentFallbackVariantRegistered
                        ? binding.sourceMaterial != null && binding.sourceMaterial == identity.proxyMaterial &&
                          (binding.sourceMaterialGuid == null && binding.sourceMaterialLocalFileId == 0 ||
                           binding.sourceMaterialGuid == identity.bakedProxyMaterialGuid &&
                           binding.sourceMaterialLocalFileId == identity.bakedProxyMaterialLocalFileId) &&
                          binding.sourceMaterialFingerprint == identity.transientFallbackFingerprint &&
                          PersistentAsset(binding.sourceMaterial, out var currentSourceGuid, out var currentSourceFileId) &&
                          currentSourceGuid == identity.bakedProxyMaterialGuid && currentSourceFileId == identity.bakedProxyMaterialLocalFileId
                        : binding.sourceMaterial != null && !PersistentAsset(binding.sourceMaterial, out _, out _) &&
                          binding.sourceMaterialGuid == null && binding.sourceMaterialLocalFileId == 0 &&
                          binding.sourceMaterialFingerprint == identity.transientFallbackFingerprint
                    : binding.sourceMaterialGuid == identity.sourceMaterialGuid &&
                      binding.sourceMaterialLocalFileId == identity.sourceMaterialLocalFileId &&
                      binding.sourceMaterialFingerprint == identity.sourceMaterialFingerprint);
            return binding != null && identity != null && sourceMaterialMatches && binding.owner == identity.sourceOwner &&
                binding.sourceComponentId == identity.sourceComponentId && binding.materialSlot == identity.materialSlot &&
                binding.persistentFallbackVariantRegistered == identity.persistentFallbackVariantRegistered &&
                binding.generatedSubmesh == identity.generatedSubmesh &&
                binding.textInfoCharacterSlotVerified == identity.textInfoCharacterSlotVerified &&
                binding.textInfoCharacterMaterialVerified == identity.textInfoCharacterMaterialVerified &&
                binding.textInfoFontAssetVerified == identity.textInfoFontAssetVerified &&
                binding.textInfoAtlasVerified == identity.textInfoAtlasVerified &&
                binding.textInfoCharacterCount == identity.textInfoCharacterCount &&
                binding.textInfoVisibleCharacterCount == identity.textInfoVisibleCharacterCount &&
                binding.sourceTextSha256 == identity.sourceTextSha256 &&
                TextSlotEnumerationsMatchForInitialized(binding.textSlotEnumeration, identity.textSlotEnumeration) &&
                binding.textInfoCharacterAssetEvidenceSha256 == identity.textInfoCharacterAssetEvidenceSha256 &&
                binding.textInfoCharacterMaterialFingerprint == identity.textInfoCharacterMaterialFingerprint &&
                binding.fontAssetGuid == identity.fontAssetGuid && binding.fontAssetLocalFileId == identity.fontAssetLocalFileId &&
                (identity.spriteAsset == null
                    ? String.IsNullOrEmpty(binding.spriteAssetGuid) && String.IsNullOrEmpty(identity.spriteAssetGuid) &&
                      binding.spriteAssetLocalFileId == 0 && identity.spriteAssetLocalFileId == 0
                    : binding.spriteAssetGuid == identity.spriteAssetGuid && binding.spriteAssetLocalFileId == identity.spriteAssetLocalFileId) &&
                binding.ownerFontMaterialGuid == identity.ownerFontMaterialGuid &&
                binding.ownerFontMaterialLocalFileId == identity.ownerFontMaterialLocalFileId &&
                binding.ownerFontMaterialFingerprint == identity.ownerFontMaterialFingerprint &&
                (String.IsNullOrEmpty(identity.ownerStyleProfile) ? binding.ownerStyle == null :
                 binding.ownerStyle != null && binding.ownerStyle.profile == identity.ownerStyleProfile &&
                 binding.ownerStyle.sourceComponentId == identity.ownerStyleSourceComponentId &&
                 binding.ownerStyle.sourceFontAssetGuid == identity.ownerStyleSourceFontAssetGuid &&
                 binding.ownerStyle.sourceFontMaterialGuid == identity.ownerStyleSourceFontMaterialGuid) &&
                FallbackAssetContractMatches(binding, identity) &&
                binding.sourceShaderGuid == identity.sourceShaderGuid && binding.sourceShaderLocalFileId == identity.sourceShaderLocalFileId &&
                binding.sourceTextureGuid == identity.sourceTextureGuid && binding.sourceTextureLocalFileId == identity.sourceTextureLocalFileId;
        }

        static bool FallbackAssetContractMatches(TextSlotBinding binding, NativeStaticSortTextSource identity)
        {
            if (binding == null || identity == null) return false;
            return binding.fallbackFontAsset == identity.fallbackFontAsset &&
                String.Equals(binding.fallbackFontAssetGuid ?? String.Empty, identity.fallbackFontAssetGuid ?? String.Empty,
                    StringComparison.Ordinal) && binding.fallbackFontAssetLocalFileId == identity.fallbackFontAssetLocalFileId &&
                binding.fallbackFontMaterial == identity.fallbackFontMaterial &&
                String.Equals(binding.fallbackFontMaterialGuid ?? String.Empty, identity.fallbackFontMaterialGuid ?? String.Empty,
                    StringComparison.Ordinal) && binding.fallbackFontMaterialLocalFileId == identity.fallbackFontMaterialLocalFileId &&
                String.Equals(binding.fallbackFontMaterialFingerprint ?? String.Empty,
                    identity.fallbackFontMaterialFingerprint ?? String.Empty, StringComparison.Ordinal);
        }

        static bool TextSlotEnumerationsMatchForInitialized(NativeStaticSortTextSlotEnumeration saved,
            NativeStaticSortTextSlotEnumeration current)
        {
            if (!IsValidTextSlotEnumeration(saved) || !IsValidTextSlotEnumeration(current) ||
                saved.sourceComponentId != current.sourceComponentId || saved.sourceTextSha256 != current.sourceTextSha256 ||
                saved.slotCount != current.slotCount || saved.rows.Length != current.rows.Length) return false;
            for (var index = 0; index < saved.rows.Length; index++)
            {
                var a = saved.rows[index]; var b = current.rows[index];
                if (a.slot != b.slot || a.disposition != b.disposition ||
                    a.characterReferences != b.characterReferences || a.visibleCharacterReferences != b.visibleCharacterReferences ||
                    a.textInfoVertexCount != b.textInfoVertexCount || a.textInfoTriangleIndexCount != b.textInfoTriangleIndexCount ||
                    a.textInfoNondegenerateTriangleCount != b.textInfoNondegenerateTriangleCount ||
                    a.canvasVertexCount != b.canvasVertexCount || a.canvasTriangleIndexCount != b.canvasTriangleIndexCount ||
                    a.canvasNondegenerateTriangleCount != b.canvasNondegenerateTriangleCount ||
                    a.sourceAssetKind != b.sourceAssetKind || a.sourceAssetGuid != b.sourceAssetGuid ||
                    a.sourceAssetLocalFileId != b.sourceAssetLocalFileId || a.atlasGuid != b.atlasGuid ||
                    a.atlasLocalFileId != b.atlasLocalFileId ||
                    a.characterAssetEvidenceSha256 != b.characterAssetEvidenceSha256 ||
                    a.sourceGraphicMaterialFingerprint != b.sourceGraphicMaterialFingerprint ||
                    a.sourceMeshSha256 != b.sourceMeshSha256) return false;
                // TMP's CharacterInfo and meshInfo material caches are rebuilt
                // during initialization; their presence and pre-outline cache
                // fingerprints can differ from the saved capture. Live slot
                // material/cache authenticity is independently verified by
                // ReadTextInfoSlotEvidence and the SDK/outline material proofs.
            }
            return true;
        }

        static void AddIdentityMismatch(List<string> failures, string field, bool matches, string actual, string expected)
        {
            if (!matches) failures.Add(field + "=" + Clip(actual) + "!=" + Clip(expected));
        }

        static string BindingIdentityMismatchSummary(TextSlotBinding binding, NativeStaticSortTextSource identity)
        {
            if (binding == null || identity == null) return "failed=binding-or-identity-null";
            var failures = new List<string>();
            AddIdentityMismatch(failures, "ownerRef", binding.owner == identity.sourceOwner,
                ObjectIdentitySummary(binding.owner), ObjectIdentitySummary(identity.sourceOwner));
            AddIdentityMismatch(failures, "sourceComponentId", binding.sourceComponentId == identity.sourceComponentId,
                binding.sourceComponentId, identity.sourceComponentId);
            AddIdentityMismatch(failures, "materialSlot", binding.materialSlot == identity.materialSlot,
                binding.materialSlot.ToString(), identity.materialSlot.ToString());
            AddIdentityMismatch(failures, "generatedSubmesh", binding.generatedSubmesh == identity.generatedSubmesh,
                binding.generatedSubmesh.ToString(), identity.generatedSubmesh.ToString());
            AddIdentityMismatch(failures, "persistentFallbackVariantRegistered",
                binding.persistentFallbackVariantRegistered == identity.persistentFallbackVariantRegistered,
                binding.persistentFallbackVariantRegistered.ToString(), identity.persistentFallbackVariantRegistered.ToString());
            AddIdentityMismatch(failures, "textInfoVerifiedFlags",
                binding.textInfoCharacterSlotVerified == identity.textInfoCharacterSlotVerified &&
                binding.textInfoCharacterMaterialVerified == identity.textInfoCharacterMaterialVerified &&
                binding.textInfoFontAssetVerified == identity.textInfoFontAssetVerified &&
                binding.textInfoAtlasVerified == identity.textInfoAtlasVerified,
                binding.textInfoCharacterSlotVerified + "/" + binding.textInfoCharacterMaterialVerified + "/" +
                binding.textInfoFontAssetVerified + "/" + binding.textInfoAtlasVerified,
                identity.textInfoCharacterSlotVerified + "/" + identity.textInfoCharacterMaterialVerified + "/" +
                identity.textInfoFontAssetVerified + "/" + identity.textInfoAtlasVerified);

            var currentSourceIsPersistent = PersistentAsset(binding.sourceMaterial, out var currentSourceGuid, out var currentSourceLocalId);
            var sourceMaterialMatches = identity.tmpFallbackMaterialBaked
                ? identity.persistentFallbackVariantRegistered
                    ? binding.sourceMaterial != null && binding.sourceMaterial == identity.proxyMaterial &&
                      (binding.sourceMaterialGuid == null && binding.sourceMaterialLocalFileId == 0 ||
                       binding.sourceMaterialGuid == identity.bakedProxyMaterialGuid &&
                       binding.sourceMaterialLocalFileId == identity.bakedProxyMaterialLocalFileId) &&
                      binding.sourceMaterialFingerprint == identity.transientFallbackFingerprint &&
                      currentSourceIsPersistent && currentSourceGuid == identity.bakedProxyMaterialGuid &&
                      currentSourceLocalId == identity.bakedProxyMaterialLocalFileId
                    : binding.sourceMaterial != null && !currentSourceIsPersistent &&
                      binding.sourceMaterialGuid == null && binding.sourceMaterialLocalFileId == 0 &&
                      binding.sourceMaterialFingerprint == identity.transientFallbackFingerprint
                : binding.sourceMaterialGuid == identity.sourceMaterialGuid &&
                  binding.sourceMaterialLocalFileId == identity.sourceMaterialLocalFileId &&
                  binding.sourceMaterialFingerprint == identity.sourceMaterialFingerprint;
            AddIdentityMismatch(failures, "sourceMaterialContract", sourceMaterialMatches,
                "ref=" + ObjectIdentitySummary(binding.sourceMaterial) + ";persist=" + currentSourceIsPersistent +
                ";guidLocal=" + (currentSourceGuid ?? "null") + ":" + currentSourceLocalId +
                ";fp=" + (binding.sourceMaterialFingerprint ?? "missing") +
                ";bindingGuidLocal=" + (binding.sourceMaterialGuid ?? "null") + ":" + binding.sourceMaterialLocalFileId,
                "ref=" + ObjectIdentitySummary(identity.proxyMaterial) +
                ";guidLocal=" + (identity.bakedProxyMaterialGuid ?? identity.sourceMaterialGuid ?? "null") + ":" +
                (identity.tmpFallbackMaterialBaked ? identity.bakedProxyMaterialLocalFileId : identity.sourceMaterialLocalFileId) +
                ";fp=" + (identity.transientFallbackFingerprint ?? identity.sourceMaterialFingerprint ?? "missing"));
            AddIdentityMismatch(failures, "textSlotEnumerationSha",
                TextSlotEnumerationsMatchForInitialized(identity.textSlotEnumeration, binding.textSlotEnumeration),
                TextSlotEnumerationMismatchSummary(binding.textSlotEnumeration, identity.textSlotEnumeration),
                TextSlotEnumerationMismatchSummary(identity.textSlotEnumeration, binding.textSlotEnumeration));
            var proxyGraphicForMesh = identity.GetComponent<NativeStaticSortQueueProxyGraphic>();
            var capturedProxyMesh = proxyGraphicForMesh == null ? null : proxyGraphicForMesh.proxyMesh;
            var sourceMeshDataMatches = binding.sourceMeshSha256 == identity.sourceMeshSha256;
            AddIdentityMismatch(failures, "sourceMeshSha256", sourceMeshDataMatches,
                binding.sourceMeshSha256, identity.sourceMeshSha256);
            string sourceSlotGuid = null; long sourceSlotLocalId = 0;
            var sourceSlotMeshPersistent = identity.sourceSlotMesh != null &&
                identity.sourceSlotMeshSha256 == identity.sourceMeshSha256 &&
                MeshFingerprint(identity.sourceSlotMesh) == identity.sourceMeshSha256 &&
                PersistentAsset(identity.sourceSlotMesh, out sourceSlotGuid, out sourceSlotLocalId) &&
                sourceSlotGuid == identity.sourceSlotMeshGuid && sourceSlotLocalId == identity.sourceSlotMeshLocalFileId;
            AddIdentityMismatch(failures, "sourceSlotMeshSnapshot", sourceSlotMeshPersistent && sourceMeshDataMatches,
                "verified=" + sourceSlotMeshPersistent + ";guidLocal=" + (sourceSlotGuid ?? "null") + ":" + sourceSlotLocalId +
                    ";sha=" + (identity.sourceSlotMeshSha256 ?? "missing"),
                "guidLocal=" + (identity.sourceSlotMeshGuid ?? "null") + ":" + identity.sourceSlotMeshLocalFileId +
                    ";sha=" + (identity.sourceMeshSha256 ?? "missing"));
            var sourceMeshDataDiagnostic = sourceMeshDataMatches ? String.Empty :
                ";sourceMeshDataDetails=current={" + BoundMeshDiagnostic(MeshGeometrySummary(binding.sourceMesh)) +
                "};currentCanvas={" + CanvasContextSummary(binding.sourceGraphic) +
                "};captured={" + BoundMeshDiagnostic(MeshGeometrySummary(capturedProxyMesh)) + "}";
            AddIdentityMismatch(failures, "sourceTextSha256", binding.sourceTextSha256 == identity.sourceTextSha256,
                binding.sourceTextSha256, identity.sourceTextSha256);
            AddIdentityMismatch(failures, "characterAssetEvidenceSha256",
                binding.textInfoCharacterAssetEvidenceSha256 == identity.textInfoCharacterAssetEvidenceSha256,
                binding.textInfoCharacterAssetEvidenceSha256, identity.textInfoCharacterAssetEvidenceSha256);
            AddIdentityMismatch(failures, "characterCacheFingerprint",
                binding.textInfoCharacterMaterialFingerprint == identity.textInfoCharacterMaterialFingerprint,
                binding.textInfoCharacterMaterialFingerprint, identity.textInfoCharacterMaterialFingerprint);
            AddIdentityMismatch(failures, "characterCounts",
                binding.textInfoCharacterCount == identity.textInfoCharacterCount &&
                binding.textInfoVisibleCharacterCount == identity.textInfoVisibleCharacterCount,
                binding.textInfoCharacterCount + "/" + binding.textInfoVisibleCharacterCount,
                identity.textInfoCharacterCount + "/" + identity.textInfoVisibleCharacterCount);
            AddIdentityMismatch(failures, "fontAssetGuidLocal",
                binding.fontAssetGuid == identity.fontAssetGuid && binding.fontAssetLocalFileId == identity.fontAssetLocalFileId,
                (binding.fontAssetGuid ?? "null") + ":" + binding.fontAssetLocalFileId,
                (identity.fontAssetGuid ?? "null") + ":" + identity.fontAssetLocalFileId);
            AddIdentityMismatch(failures, "fontAssetObjectRef", binding.fontAsset == identity.fontAsset,
                ObjectIdentitySummary(binding.fontAsset), ObjectIdentitySummary(identity.fontAsset));
            AddIdentityMismatch(failures, "spriteAssetGuidLocal",
                identity.spriteAsset == null
                    ? String.IsNullOrEmpty(binding.spriteAssetGuid) && String.IsNullOrEmpty(identity.spriteAssetGuid) &&
                      binding.spriteAssetLocalFileId == 0 && identity.spriteAssetLocalFileId == 0
                    : binding.spriteAssetGuid == identity.spriteAssetGuid && binding.spriteAssetLocalFileId == identity.spriteAssetLocalFileId,
                (binding.spriteAssetGuid ?? "null") + ":" + binding.spriteAssetLocalFileId,
                (identity.spriteAssetGuid ?? "null") + ":" + identity.spriteAssetLocalFileId);
            AddIdentityMismatch(failures, "spriteAssetObjectRef", binding.spriteAsset == identity.spriteAsset,
                ObjectIdentitySummary(binding.spriteAsset), ObjectIdentitySummary(identity.spriteAsset));
            AddIdentityMismatch(failures, "sourceAtlasObjectRef", binding.sourceTexture == identity.sourceTexture,
                ObjectIdentitySummary(binding.sourceTexture), ObjectIdentitySummary(identity.sourceTexture));
            AddIdentityMismatch(failures, "ownerFontMaterialObjectRef",
                binding.ownerFontSharedMaterial == identity.ownerFontSharedMaterial,
                ObjectIdentitySummary(binding.ownerFontSharedMaterial), ObjectIdentitySummary(identity.ownerFontSharedMaterial));
            AddIdentityMismatch(failures, "ownerFontMaterialGuidLocalFingerprint",
                binding.ownerFontMaterialGuid == identity.ownerFontMaterialGuid &&
                binding.ownerFontMaterialLocalFileId == identity.ownerFontMaterialLocalFileId &&
                binding.ownerFontMaterialFingerprint == identity.ownerFontMaterialFingerprint,
                (binding.ownerFontMaterialGuid ?? "null") + ":" + binding.ownerFontMaterialLocalFileId + ":" +
                (binding.ownerFontMaterialFingerprint ?? "missing"),
                (identity.ownerFontMaterialGuid ?? "null") + ":" + identity.ownerFontMaterialLocalFileId + ":" +
                (identity.ownerFontMaterialFingerprint ?? "missing"));
            var ownerStyleMatches = String.IsNullOrEmpty(identity.ownerStyleProfile)
                ? binding.ownerStyle == null
                : binding.ownerStyle != null && binding.ownerStyle.profile == identity.ownerStyleProfile &&
                  binding.ownerStyle.sourceComponentId == identity.ownerStyleSourceComponentId &&
                  binding.ownerStyle.sourceFontAssetGuid == identity.ownerStyleSourceFontAssetGuid &&
                  binding.ownerStyle.sourceFontMaterialGuid == identity.ownerStyleSourceFontMaterialGuid;
            AddIdentityMismatch(failures, "ownerStyleDescriptor", ownerStyleMatches,
                binding.ownerStyle == null ? "null" : binding.ownerStyle.profile + ":" + binding.ownerStyle.sourceComponentId + ":" +
                binding.ownerStyle.sourceFontAssetGuid + ":" + binding.ownerStyle.sourceFontMaterialGuid,
                identity.ownerStyleProfile == null ? "null" : identity.ownerStyleProfile + ":" + identity.ownerStyleSourceComponentId + ":" +
                identity.ownerStyleSourceFontAssetGuid + ":" + identity.ownerStyleSourceFontMaterialGuid);
            AddIdentityMismatch(failures, "fallbackFontAssetRef", binding.fallbackFontAsset == identity.fallbackFontAsset,
                ObjectIdentitySummary(binding.fallbackFontAsset), ObjectIdentitySummary(identity.fallbackFontAsset));
            AddIdentityMismatch(failures, "fallbackFontAssetGuidLocal",
                String.Equals(binding.fallbackFontAssetGuid ?? String.Empty, identity.fallbackFontAssetGuid ?? String.Empty,
                    StringComparison.Ordinal) && binding.fallbackFontAssetLocalFileId == identity.fallbackFontAssetLocalFileId,
                (binding.fallbackFontAssetGuid ?? "null") + ":" + binding.fallbackFontAssetLocalFileId,
                (identity.fallbackFontAssetGuid ?? "null") + ":" + identity.fallbackFontAssetLocalFileId);
            AddIdentityMismatch(failures, "fallbackFontMaterialRef", binding.fallbackFontMaterial == identity.fallbackFontMaterial,
                ObjectIdentitySummary(binding.fallbackFontMaterial), ObjectIdentitySummary(identity.fallbackFontMaterial));
            AddIdentityMismatch(failures, "fallbackFontMaterialGuidLocalFingerprint",
                String.Equals(binding.fallbackFontMaterialGuid ?? String.Empty, identity.fallbackFontMaterialGuid ?? String.Empty,
                    StringComparison.Ordinal) && binding.fallbackFontMaterialLocalFileId == identity.fallbackFontMaterialLocalFileId &&
                String.Equals(binding.fallbackFontMaterialFingerprint ?? String.Empty,
                    identity.fallbackFontMaterialFingerprint ?? String.Empty, StringComparison.Ordinal),
                (binding.fallbackFontMaterialGuid ?? "null") + ":" + binding.fallbackFontMaterialLocalFileId + ":" +
                (binding.fallbackFontMaterialFingerprint ?? "missing"),
                (identity.fallbackFontMaterialGuid ?? "null") + ":" + identity.fallbackFontMaterialLocalFileId + ":" +
                (identity.fallbackFontMaterialFingerprint ?? "missing"));
            AddIdentityMismatch(failures, "shaderGuidLocal",
                binding.sourceShaderGuid == identity.sourceShaderGuid && binding.sourceShaderLocalFileId == identity.sourceShaderLocalFileId,
                (binding.sourceShaderGuid ?? "null") + ":" + binding.sourceShaderLocalFileId,
                (identity.sourceShaderGuid ?? "null") + ":" + identity.sourceShaderLocalFileId);
            AddIdentityMismatch(failures, "atlasGuidLocal",
                binding.sourceTextureGuid == identity.sourceTextureGuid && binding.sourceTextureLocalFileId == identity.sourceTextureLocalFileId,
                (binding.sourceTextureGuid ?? "null") + ":" + binding.sourceTextureLocalFileId,
                (identity.sourceTextureGuid ?? "null") + ":" + identity.sourceTextureLocalFileId);
            var outline = binding.owner == null ? null : binding.owner.GetComponent<NativeStaticTextOutline>();
            var submesh = binding.sourceGraphic as TMP_SubMeshUI;
            var outlineSelectionEvidence = identity.persistentFallbackVariantRegistered
                ? "outline=" + (outline != null) + ";target=" + (outline != null && outline.Target == binding.owner) +
                  ";registrySelected=" + (outline != null && outline.IsPersistentMaterialVariantSelected(binding.fallbackFontAsset,
                      binding.ownerFontSharedMaterial, binding.sourceTexture, binding.sourceMaterial)) +
                  ";fallbackSource=" + (submesh != null && submesh.fallbackSourceMaterial == binding.ownerFontSharedMaterial) +
                  ";fallbackMaterial=" + (submesh != null && submesh.fallbackMaterial == binding.sourceMaterial) +
                  ";sharedMaterial=" + (submesh != null && submesh.sharedMaterial == binding.sourceMaterial) +
                  ";current=" + ObjectIdentitySummary(binding.sourceMaterial)
                : "not-registered";
            return (failures.Count == 0 ? "failed=none;unclassified=true" : "failed=" + String.Join("|", failures.Take(12))) +
                ";outlineSelection=" + outlineSelectionEvidence +
                ";cacheLifecycle=captured=" + identity.textInfoMaterialMissing + "/" +
                (identity.textInfoCharacterEvidenceSha256 ?? "missing") + ",current=" + binding.textInfoMaterialMissing + "/" +
                (binding.textInfoCharacterEvidenceSha256 ?? "missing") + sourceMeshDataDiagnostic;
        }

        static string BoundMeshDiagnostic(string value)
        {
            const int maxLength = 3600;
            if (String.IsNullOrEmpty(value) || value.Length <= maxLength) return value ?? "missing";
            return value.Substring(0, maxLength - 16) + "...<bounded>";
        }

        static string TextSlotEnumerationMismatchSummary(NativeStaticSortTextSlotEnumeration actual,
            NativeStaticSortTextSlotEnumeration expected)
        {
            if (actual == null || expected == null) return actual == expected ? "both-null" : actual == null ? "missing" : "present";
            var differences = new List<string>();
            void Add(string field, string a, string b)
            {
                if (!String.Equals(a, b, StringComparison.Ordinal)) differences.Add(field + "=" + Clip(a) + "!=" + Clip(b));
            }
            Add("sourceComponentId", actual.sourceComponentId, expected.sourceComponentId);
            Add("sourceTextSha256", actual.sourceTextSha256, expected.sourceTextSha256);
            Add("slotCount", actual.slotCount.ToString(), expected.slotCount.ToString());
            Add("verified", actual.verified.ToString(), expected.verified.ToString());
            Add("rowLength", (actual.rows == null ? -1 : actual.rows.Length).ToString(),
                (expected.rows == null ? -1 : expected.rows.Length).ToString());
            if (actual.rows != null && expected.rows != null)
            {
                for (var i = 0; i < Math.Min(actual.rows.Length, expected.rows.Length); i++)
                {
                    var a = actual.rows[i]; var e = expected.rows[i];
                    if (a == null || e == null)
                    {
                        if (a != e) differences.Add("row[" + i + "]=null-state-diff");
                        continue;
                    }
                    var rowDiffs = new List<string>();
                    void Row(string field, string av, string ev)
                    {
                        if (!String.Equals(av, ev, StringComparison.Ordinal)) rowDiffs.Add(field + ":" + Clip(av) + "!=" + Clip(ev));
                    }
                    Row("slot", a.slot.ToString(), e.slot.ToString());
                    Row("disposition", a.disposition, e.disposition);
                    Row("characterReferences", a.characterReferences.ToString(), e.characterReferences.ToString());
                    Row("visibleCharacterReferences", a.visibleCharacterReferences.ToString(), e.visibleCharacterReferences.ToString());
                    Row("textInfoVertexCount", a.textInfoVertexCount.ToString(), e.textInfoVertexCount.ToString());
                    Row("textInfoTriangleIndexCount", a.textInfoTriangleIndexCount.ToString(), e.textInfoTriangleIndexCount.ToString());
                    Row("textInfoNondegenerateTriangleCount", a.textInfoNondegenerateTriangleCount.ToString(), e.textInfoNondegenerateTriangleCount.ToString());
                    Row("canvasVertexCount", a.canvasVertexCount.ToString(), e.canvasVertexCount.ToString());
                    Row("canvasTriangleIndexCount", a.canvasTriangleIndexCount.ToString(), e.canvasTriangleIndexCount.ToString());
                    Row("canvasNondegenerateTriangleCount", a.canvasNondegenerateTriangleCount.ToString(), e.canvasNondegenerateTriangleCount.ToString());
                    Row("sourceAssetKind", a.sourceAssetKind, e.sourceAssetKind);
                    Row("sourceAssetGuid", a.sourceAssetGuid, e.sourceAssetGuid);
                    Row("sourceAssetLocalFileId", a.sourceAssetLocalFileId.ToString(), e.sourceAssetLocalFileId.ToString());
                    Row("atlasGuid", a.atlasGuid, e.atlasGuid);
                    Row("atlasLocalFileId", a.atlasLocalFileId.ToString(), e.atlasLocalFileId.ToString());
                    Row("characterAssetEvidenceSha256", a.characterAssetEvidenceSha256, e.characterAssetEvidenceSha256);
                    Row("sourceGraphicMaterialFingerprint", a.sourceGraphicMaterialFingerprint, e.sourceGraphicMaterialFingerprint);
                    Row("sourceMeshSha256", a.sourceMeshSha256, e.sourceMeshSha256);
                    if (rowDiffs.Count > 0) differences.Add("row[" + i + "]{" + String.Join(",", rowDiffs.Take(8)) + "}");
                }
            }
            return differences.Count == 0 ? "stable-fields-match" : String.Join(";", differences.Take(8));
        }

        static string MeshGeometrySummary(Mesh mesh)
        {
            if (mesh == null) return "mesh=null";
            const int sampleCount = 4;
            string Vec3(Vector3 value) => value.x.ToString("R", CultureInfo.InvariantCulture) + "," +
                value.y.ToString("R", CultureInfo.InvariantCulture) + "," + value.z.ToString("R", CultureInfo.InvariantCulture);
            string Vec4(Vector4 value) => value.x.ToString("R", CultureInfo.InvariantCulture) + ","+
                value.y.ToString("R", CultureInfo.InvariantCulture) + ","+value.z.ToString("R", CultureInfo.InvariantCulture)+","+
                value.w.ToString("R", CultureInfo.InvariantCulture);
            var positions = mesh.vertices;
            var colors = mesh.colors32;
            var normals = mesh.normals;
            var tangents = mesh.tangents;
            var samples = new List<string>();
            for (var i = 0; i < Math.Min(sampleCount, positions.Length); i++)
            {
                var fields = new List<string> { "v" + i + "=" + Vec3(positions[i]) };
                if (colors != null && i < colors.Length)
                    fields.Add("c=" + colors[i].r + "," + colors[i].g + "," + colors[i].b + "," + colors[i].a);
                if (normals != null && i < normals.Length) fields.Add("n=" + Vec3(normals[i]));
                if (tangents != null && i < tangents.Length) fields.Add("t=" + Vec4(tangents[i]));
                samples.Add(String.Join("/", fields));
            }
            var uvChannels = new List<string>();
            for (var channel = 0; channel < 8; channel++)
            {
                var uv = new List<Vector4>();
                mesh.GetUVs(channel, uv);
                if (uv.Count == 0) continue;
                uvChannels.Add(channel + "[" + uv.Count + "]=" +
                    String.Join(";", uv.Take(sampleCount).Select(Vec4)));
            }
            var indexSamples = new List<string>();
            for (var submesh = 0; submesh < Math.Min(mesh.subMeshCount, 4); submesh++)
            {
                try { indexSamples.Add(submesh + "=" + String.Join(",", mesh.GetTriangles(submesh).Take(6))); }
                catch (Exception error) { indexSamples.Add(submesh + "=error:" + error.GetType().Name); }
            }
            return "vertices=" + mesh.vertexCount + ";submeshes=" + mesh.subMeshCount +
                ";bounds=" + Vec3(mesh.bounds.center) + "/" + Vec3(mesh.bounds.size) +
                ";sample=" + String.Join(";", samples) + ";uv=" + String.Join("|", uvChannels) +
                ";indices=" + String.Join("|", indexSamples);
        }

        static string CanvasContextSummary(Graphic graphic)
        {
            var canvas = graphic == null ? null : graphic.canvas;
            if (canvas == null) return "canvas=missing";
            var root = canvas.rootCanvas;
            var scale = canvas.scaleFactor.ToString("R", CultureInfo.InvariantCulture);
            var lossy = canvas.transform.lossyScale;
            var lossyText = lossy.x.ToString("R", CultureInfo.InvariantCulture) + "," +
                lossy.y.ToString("R", CultureInfo.InvariantCulture) + "," +
                lossy.z.ToString("R", CultureInfo.InvariantCulture);
            return "renderMode=" + canvas.renderMode + ";scaleFactor=" + scale + ";canvasLossyScale=" + lossyText +
                ";rootCanvas=" + (root == null ? "missing" : Clip(root.name)) +
                ";worldCamera=" + ObjectIdentitySummary(canvas.worldCamera);
        }

        static OwnerFontStyleDescriptor OwnerStyleFromIdentity(NativeStaticSortTextSource identity)
        {
            if (identity == null || String.IsNullOrEmpty(identity.ownerStyleProfile)) return null;
            return new OwnerFontStyleDescriptor {
                profile = identity.ownerStyleProfile,
                sourceComponentId = identity.ownerStyleSourceComponentId,
                outlineWidth = identity.ownerStyleOutlineWidth,
                outlineColor = identity.ownerStyleOutlineColor,
                sourceFontAsset = identity.ownerStyleSourceFontAsset,
                sourceFontAssetGuid = identity.ownerStyleSourceFontAssetGuid,
                sourceFontAssetLocalFileId = identity.ownerStyleSourceFontAssetLocalFileId,
                sourceFontMaterial = identity.ownerStyleSourceFontMaterial,
                sourceFontMaterialGuid = identity.ownerStyleSourceFontMaterialGuid,
                sourceFontMaterialLocalFileId = identity.ownerStyleSourceFontMaterialLocalFileId,
                sourceFontMaterialFingerprint = identity.ownerStyleSourceFontMaterialFingerprint,
            };
        }

        static bool IsGeneratedSubmesh(TMP_SubMeshUI child, TMP_Text owner)
        {
            if (child == null || owner == null || child.transform.parent != owner.transform ||
                child.transform.childCount != 0 || !(child.transform is RectTransform) ||
                (child.gameObject.hideFlags & HideFlags.DontSave) != HideFlags.DontSave ||
                child.textComponent != owner) return false;
            if (child.GetComponent<LayoutElement>() is LayoutElement layout && !layout.ignoreLayout) return false;
            return true;
        }

        static bool Fail(string message, out string diagnostic)
        {
            diagnostic = message;
            return false;
        }
    }
}
