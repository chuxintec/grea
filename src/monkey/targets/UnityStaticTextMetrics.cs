// Saved-prefab native text configuration/metric readback for the bounded
// prefab_static_text_continuation.py producer. This helper reports native
// state; it never claims source font-platform or pixel equivalence.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using TMPro;
using UnityEditor;
using UnityEngine;

public static partial class MonkeyImporter
{
    [Serializable]
    public sealed class StaticTextContinuationContract
    {
        public int schemaVersion;
        public string contract, sourceVersion, sourceProfile, sourceManifestSha256, sourceIrSha256, status;
        public StaticTextGroup[] components;
    }

    [Serializable]
    public sealed class StaticTextGroup
    {
        public string sourceLabelId, sourceOutlineId, sourceNodeId, fontKind, sourceFontFamily,
            sourceFontFamilyEvidence, sourceText, sourceTextSha256;
        public string[] nativeFontAssetIds, nativeFontAssetPaths;
        public bool sourceBold, sourceItalic, sourceUnderline, sourceEnabled, sourceOutlineEnabled;
        public float sourceFontSize, sourceLineHeight, sourceOutlineWidth;
        public int sourceOverflow;
        public bool sourceWrap;
        public float[] sourceNodeSize, sourceNodePivot, sourceOutlineColor;
        public StaticTextFontBinding nativeFontBinding;
        public StaticTextLayoutPolicy layoutPolicy;
    }

    [Serializable]
    public sealed class StaticTextFontBinding
    {
        public string kind;
        public string[] assetIds, assetPaths;
        public StaticTextSystemFontBinding binding;
    }

    [Serializable]
    public sealed class StaticTextSystemFontBinding
    {
        public string sourceLabelId, sourceFontFamily, sourceFontFamilyEvidence, sourceText,
            nativeFontAssetId, nativeFontAssetPath;
        public string[] nativeFallbackAssetIds, nativeFallbackAssetPaths;
        public float pointSize;
        public bool sourceSystemFont;
    }

    [Serializable]
    public sealed class StaticTextLayoutPolicy
    {
        public string profile, overflowMeaning, lineHeightPolicy, outlinePaddingPolicy, wrapPolicy, shrinkPolicy;
        public float sourceShrinkLowerBound, sourceFontSizeMaximum, targetAutoSizeMin, targetAutoSizeMax;
        public float[] sourceNodeColor;
        public bool targetAutoSizing, exactSourceMetricParity;
    }

    [Serializable]
    public sealed class StaticTextAssetIdentity
    {
        public string assetPath, guid, name;
        public long localFileId;
        public float pointSize, lineHeight;
        public bool isStaticPopulation;
    }

    [Serializable]
    public sealed class StaticTextBounds
    {
        public float xMin, yMin, xMax, yMax, width, height;
        public int visibleCharacterCount;
        public bool hasVisibleGeometry;
    }

    [Serializable]
    public sealed class StaticTextMetricComponentReadback
    {
        public string sourceLabelId, sourceOutlineId, sourceNodeId, sourceTextSha256, nativeTextSha256, status, fontKind;
        public string labelGuid, outlineGuid, outlineNativeType, fontGuid, nativeText, nativeFontAssetPath, nativeTextStyle;
        public string nativeBoundsKind = "tmp-character-quad-local-bounds-not-pixel-ink";
        public long labelLocalFileId, outlineLocalFileId, fontLocalFileId;
        public bool persistentLabel, persistentOutline, sourceTextMatches, sourceStyleMatches,
            autoSizingConfigVerified, fontBindingVerified, glyphFontChainVerified,
            lineHeightConfigVerified, outlineConfigVerified, outlineMaterialReadbackVerified,
            nativeMeshMeasured, sourceCanvasMetricAvailable, sourceFontPlatformEquivalent,
            visualEquivalent;
        public float nativeFontSize, actualFontSize, nativeFontSizeMin, nativeFontSizeMax, nativeLineSpacing,
            nativeFontPointSize, nativeFaceLineHeight, nativePreferredWidth, nativePreferredHeight;
        public int nativeFontStyle, nativeOverflowMode, nativeWrappingMode, nativeLineCount,
            nativeCharacterCount, nativeVisibleCharacterCount;
        public StaticTextAssetIdentity[] glyphFontAssets,configuredFontAssets;
        public StaticTextBounds inkBounds;
        public NativeStaticTextOutline.Readback outlineReadback;
        public string[] diagnostics;
    }

    [Serializable]
    public sealed class StaticTextMetricsReadback
    {
        public int schemaVersion = 1;
        public string contract = "monkey-static-text-metrics-readback/1";
        public string phase = "saved-prefab-reopen";
        public string sourceManifestSha256, sourcePrefabId, unityVersion, continuationJsonSha256, status;
        public StaticTextMetricComponentReadback[] components;
        public string[] diagnostics;
    }

    // UnityImporter.cs declares this partial method and calls it after the
    // saved Prefab has reopened, UI context/layout is settled, and source node
    // maps are available. The report is sidecar-bound by the main readback.
    static partial void ReadSavedStaticTextMetrics(Plan plan,
        Dictionary<string, GameObject> persistentNodes,
        Dictionary<string, GameObject> loadedNodes,
        string sourcePrefabId)
    {
        if (plan == null || String.IsNullOrEmpty(plan.staticTextContinuationJson)) return;
        var contract = JsonUtility.FromJson<StaticTextContinuationContract>(plan.staticTextContinuationJson);
        if (contract == null || contract.schemaVersion != 1 ||
            contract.contract != "monkey-static-text-continuation/1" || contract.components == null)
            throw new InvalidOperationException("STATIC_TEXT_CONTINUATION_CONTRACT_INVALID");
        if (persistentNodes == null || loadedNodes == null || String.IsNullOrEmpty(sourcePrefabId))
            throw new InvalidOperationException("STATIC_TEXT_SAVED_NODE_MAP_MISSING");

        var report = new StaticTextMetricsReadback {
            sourceManifestSha256 = plan.sourceManifestSha256,
            sourcePrefabId = sourcePrefabId,
            unityVersion = Application.unityVersion,
            continuationJsonSha256 = ByteHash(Encoding.UTF8.GetBytes(plan.staticTextContinuationJson)),
        };
        var rows = new List<StaticTextMetricComponentReadback>();
        foreach (var spec in contract.components.Where(row => row != null &&
                     !String.IsNullOrEmpty(row.sourceLabelId) && !String.IsNullOrEmpty(row.sourceNodeId) &&
                     persistentNodes.ContainsKey(row.sourceNodeId) && loadedNodes.ContainsKey(row.sourceNodeId)))
        {
            var row = new StaticTextMetricComponentReadback {
                sourceLabelId = spec.sourceLabelId,
                sourceOutlineId = spec.sourceOutlineId,
                sourceNodeId = spec.sourceNodeId,
                sourceTextSha256 = spec.sourceTextSha256,
                fontKind = spec.fontKind,
                sourceCanvasMetricAvailable = false,
                sourceFontPlatformEquivalent = false,
                visualEquivalent = false,
                diagnostics = Array.Empty<string>(),
            };
            var diagnostics = new List<string>();
            var persistentNode = persistentNodes[spec.sourceNodeId];
            var loadedNode = loadedNodes[spec.sourceNodeId];
            var savedLabel = persistentNode == null ? null : persistentNode.GetComponent<TextMeshProUGUI>();
            var loadedLabel = loadedNode == null ? null : loadedNode.GetComponent<TextMeshProUGUI>();
            if (savedLabel == null || loadedLabel == null)
            {
                diagnostics.Add("STATIC_TEXT_NATIVE_TMP_COMPONENT_MISSING");
                row.status = "partial";
                row.diagnostics = diagnostics.ToArray();
                rows.Add(row);
                continue;
            }

            row.nativeText = savedLabel.text;
            row.nativeTextSha256 = ByteHash(Encoding.UTF8.GetBytes(savedLabel.text ?? String.Empty));
            row.sourceTextMatches = savedLabel.text == spec.sourceText;
            row.nativeFontSize = savedLabel.fontSize;
            row.nativeFontSizeMin = savedLabel.fontSizeMin;
            row.nativeFontSizeMax = savedLabel.fontSizeMax;
            row.nativeLineSpacing = savedLabel.lineSpacing;
            row.nativeFontStyle = (int)savedLabel.fontStyle;
            row.nativeOverflowMode = (int)savedLabel.overflowMode;
            row.nativeWrappingMode = (int)savedLabel.textWrappingMode;
            row.nativeTextStyle = savedLabel.fontStyle.ToString();
            row.autoSizingConfigVerified = savedLabel.enableAutoSizing == (spec.layoutPolicy != null && spec.layoutPolicy.targetAutoSizing) &&
                (!savedLabel.enableAutoSizing || (Mathf.Approximately(savedLabel.fontSizeMin, spec.layoutPolicy.targetAutoSizeMin) &&
                                                   Mathf.Approximately(savedLabel.fontSizeMax, spec.layoutPolicy.targetAutoSizeMax)));
            row.sourceStyleMatches = savedLabel.fontStyle == SourceFontStyles(new ComponentSpec {
                bitmapLabel = spec.fontKind == "bitmap-font", bold = spec.sourceBold,
                italic = spec.sourceItalic, underline = spec.sourceUnderline
            }) && (spec.layoutPolicy == null || spec.layoutPolicy.sourceNodeColor == null ||
                   spec.layoutPolicy.sourceNodeColor.Length != 4 ||
                   ColorClose(savedLabel.color, SourceOutlineColor(spec.layoutPolicy.sourceNodeColor)));
            if (!row.sourceTextMatches) diagnostics.Add("STATIC_TEXT_SAVED_TEXT_MISMATCH");
            if (!row.sourceStyleMatches) diagnostics.Add("STATIC_TEXT_SAVED_STYLE_MISMATCH");
            if (!row.autoSizingConfigVerified) diagnostics.Add("STATIC_TEXT_AUTOSIZING_CONFIG_MISMATCH");

            var savedIdentity = CaptureIdentity(savedLabel);
            row.persistentLabel = savedIdentity != null;
            if (savedIdentity != null)
            {
                row.labelGuid = savedIdentity.guid;
                row.labelLocalFileId = savedIdentity.localFileId;
                row.nativeFontAssetPath = savedLabel.font == null ? null : AssetDatabase.GetAssetPath(savedLabel.font);
                if (savedLabel.font != null)
                {
                    var fontIdentity = CaptureIdentity(savedLabel.font);
                    row.nativeFontPointSize = savedLabel.font.faceInfo.pointSize;
                    row.nativeFaceLineHeight = savedLabel.font.faceInfo.lineHeight;
                    if (fontIdentity != null)
                    {
                        row.fontGuid = fontIdentity.guid;
                        row.fontLocalFileId = fontIdentity.localFileId;
                        row.glyphFontAssets = new[] { fontIdentity };
                    }
                }
            }
            if (!row.persistentLabel) diagnostics.Add("STATIC_TEXT_PERSISTENT_LABEL_IDENTITY_MISSING");

            var expectedPrimary = spec.nativeFontBinding == null ? null : spec.nativeFontBinding.binding;
            var expectedFontPath = expectedPrimary != null ? expectedPrimary.nativeFontAssetPath :
                spec.nativeFontBinding != null && spec.nativeFontBinding.assetPaths != null && spec.nativeFontBinding.assetPaths.Length > 0
                    ? spec.nativeFontBinding.assetPaths[0] : null;
            row.fontBindingVerified = savedLabel.font != null && !String.IsNullOrEmpty(expectedFontPath) &&
                String.Equals(row.nativeFontAssetPath, expectedFontPath, StringComparison.Ordinal);
            if (!row.fontBindingVerified) diagnostics.Add("STATIC_TEXT_PRIMARY_FONT_BINDING_MISMATCH");
            row.glyphFontChainVerified = VerifyFontChain(savedLabel.font,
                spec.nativeFontBinding == null ? null : spec.nativeFontBinding.assetPaths);
            row.configuredFontAssets = savedLabel.font == null ? Array.Empty<StaticTextAssetIdentity>() :
                new[] { savedLabel.font }.Concat(savedLabel.font.fallbackFontAssetTable ?? new List<TMP_FontAsset>())
                    .Select(CaptureIdentity).ToArray();
            if (!row.glyphFontChainVerified) diagnostics.Add("STATIC_TEXT_FONT_FALLBACK_CHAIN_MISMATCH");

            var expectedLineSpacing = ExpectedTmpLineSpacing(spec, savedLabel.font);
            row.lineHeightConfigVerified = expectedLineSpacing.HasValue &&
                Mathf.Abs(savedLabel.lineSpacing - expectedLineSpacing.Value) <= 0.001f;
            if (!row.lineHeightConfigVerified) diagnostics.Add("STATIC_TEXT_LINE_HEIGHT_CONFIG_UNVERIFIED");

            // Measure only the initialized reopened Prefab instance. The
            // persistent asset remains untouched; the Editor supplies its
            // already captured native Canvas/UI context.
            var priorCull = loadedLabel.canvasRenderer == null || loadedLabel.canvasRenderer.cull;
            try { loadedLabel.ForceMeshUpdate(true, true); }
            finally { if (loadedLabel.canvasRenderer != null) loadedLabel.canvasRenderer.cull = priorCull; }
            row.actualFontSize = loadedLabel.fontSize;
            var info = loadedLabel.textInfo;
            if (info != null)
            {
                row.nativeLineCount = info.lineCount;
                row.nativeCharacterCount = info.characterCount;
                row.nativePreferredWidth = loadedLabel.preferredWidth;
                row.nativePreferredHeight = loadedLabel.preferredHeight;
                row.inkBounds = MeasureInkBounds(info);
                row.nativeVisibleCharacterCount = row.inkBounds == null ? 0 : row.inkBounds.visibleCharacterCount;
                row.nativeMeshMeasured = row.inkBounds != null && row.inkBounds.hasVisibleGeometry;
                var fonts = CaptureGlyphFontAssets(info);
                if (fonts.Count > 0) row.glyphFontAssets = fonts.ToArray();
            }
            if (!row.nativeMeshMeasured) diagnostics.Add("STATIC_TEXT_NATIVE_MESH_METRIC_MISSING");

            var savedOutline = persistentNode.GetComponent<NativeStaticTextOutline>();
            var loadedOutline = loadedNode.GetComponent<NativeStaticTextOutline>();
            var outlineIdentity = savedOutline == null ? null : CaptureIdentity(savedOutline);
            row.persistentOutline = outlineIdentity != null;
            if (outlineIdentity != null)
            {
                row.outlineGuid = outlineIdentity.guid;
                row.outlineNativeType = savedOutline.GetType().Name;
                row.outlineLocalFileId = outlineIdentity.localFileId;
            }
            if (spec.fontKind == "bitmap-font")
            {
                row.outlineConfigVerified = !spec.sourceOutlineEnabled || savedLabel.font != null;
                row.outlineMaterialReadbackVerified = false;
                if (spec.sourceOutlineEnabled) diagnostics.Add("STATIC_TEXT_BITMAP_OUTLINE_RETAINED_AS_SOURCE_PROFILE");
            }
            else if (String.IsNullOrEmpty(spec.sourceOutlineId))
            {
                row.outlineConfigVerified = true;
                row.outlineMaterialReadbackVerified = true;
            }
            else
            {
                var readback = loadedOutline == null ? null : loadedOutline.LastReadback;
                row.outlineReadback = readback;
                row.outlineConfigVerified = loadedOutline != null && loadedOutline.Target == loadedLabel &&
                    Mathf.Abs(loadedOutline.SourceOutlineWidth - spec.sourceOutlineWidth) <= 0.00001f &&
                    loadedOutline.SourceOutlineColor == SourceOutlineColor(spec.sourceOutlineColor);
                row.outlineMaterialReadbackVerified = spec.sourceOutlineEnabled && readback != null &&
                    readback.status == "material_values_applied_and_read_back" && readback.faces != null &&
                    readback.faces.Length > 0 && readback.faces.All(face => face != null && face.materialValuesVerified);
                if (!row.outlineConfigVerified) diagnostics.Add("STATIC_TEXT_OUTLINE_CONFIG_MISMATCH");
                if (spec.sourceOutlineEnabled && !row.outlineMaterialReadbackVerified)
                    diagnostics.Add("STATIC_TEXT_OUTLINE_MATERIAL_METRICS_UNVERIFIED");
            }

            row.status = diagnostics.Count == 0 ? "native-configuration-metrics-verified" : "partial";
            row.diagnostics = diagnostics.ToArray();
            rows.Add(row);
        }

        report.components = rows.ToArray();
        report.diagnostics = rows.SelectMany(row => row.diagnostics ?? Array.Empty<string>()).ToArray();
        report.status = rows.Count > 0 && rows.All(row => row.status == "native-configuration-metrics-verified")
            ? "verified" : rows.Count > 0 ? "partial" : "no-groups-for-prefab";
        Directory.CreateDirectory("Analysis/Readback/TextMetrics");
        var sidecar = "Analysis/Readback/TextMetrics/" + ByteHash(Encoding.UTF8.GetBytes(sourcePrefabId)) + ".json";
        File.WriteAllText(sidecar, JsonUtility.ToJson(report, true), new UTF8Encoding(false));
    }

    // The shared importer Hash helper accepts a path. Keep receipt byte hashes
    // local so the exact serialized contract bytes are bound without a temp file.
    static string ByteHash(byte[] bytes)
    {
        using (var sha = SHA256.Create())
            return String.Concat(sha.ComputeHash(bytes).Select(value => value.ToString("x2")));
    }

    // Called after the shared label setup so TTF shrink uses the source-pinned
    // Creator 2.4.15 lower bound (0), while BMFont keeps its own 0.1 floor.
    static partial void ConfigureStaticTextLabel(Plan plan, ComponentSpec source, TextMeshProUGUI label)
    {
        if (plan == null || source == null || label == null || String.IsNullOrEmpty(plan.staticTextContinuationJson)) return;
        var contract = JsonUtility.FromJson<StaticTextContinuationContract>(plan.staticTextContinuationJson);
        if (contract == null || contract.components == null || contract.contract != "monkey-static-text-continuation/1")
            throw new InvalidOperationException("STATIC_TEXT_CONTINUATION_CONTRACT_INVALID");
        var matches = contract.components.Where(row => row != null && row.sourceLabelId == source.sourceId &&
            row.sourceNodeId == source.node).ToArray();
        if (matches.Length == 0) return;
        if (matches.Length != 1 || matches[0].layoutPolicy == null)
            throw new InvalidOperationException("STATIC_TEXT_LABEL_POLICY_NOT_UNIQUE_OR_UNSUPPORTED: " + source.sourceId);
        var spec = matches[0];
        if (spec.sourceFontSize != source.fontSize || spec.sourceOverflow != source.overflow ||
            spec.sourceWrap != source.wrap || spec.sourceText != source.text)
            throw new InvalidOperationException("STATIC_TEXT_SOURCE_IDENTITY_OR_POLICY_DRIFT: " + source.sourceId);
        label.enableAutoSizing = spec.layoutPolicy.targetAutoSizing;
        if (spec.layoutPolicy.targetAutoSizing)
        {
            label.fontSizeMin = spec.layoutPolicy.targetAutoSizeMin;
            label.fontSizeMax = spec.layoutPolicy.targetAutoSizeMax;
        }
    }

    static StaticTextAssetIdentity CaptureIdentity(UnityEngine.Object value)
    {
        if (value == null || !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value, out string guid, out long localId)) return null;
        var font = value as TMP_FontAsset;
        return new StaticTextAssetIdentity {
            assetPath = AssetDatabase.GetAssetPath(value), guid = guid, localFileId = localId,
            name = value.name,
            pointSize = font == null ? 0f : font.faceInfo.pointSize,
            lineHeight = font == null ? 0f : font.faceInfo.lineHeight,
            isStaticPopulation = font == null || font.atlasPopulationMode == AtlasPopulationMode.Static,
        };
    }

    static float? ExpectedTmpLineSpacing(StaticTextGroup spec, TMP_FontAsset font)
    {
        if (spec == null || font == null || spec.sourceFontSize <= 0f || font.faceInfo.pointSize <= 0f) return null;
        return (spec.sourceLineHeight - font.faceInfo.lineHeight * spec.sourceFontSize / font.faceInfo.pointSize) *
               100f / spec.sourceFontSize;
    }

    static bool VerifyFontChain(TMP_FontAsset primary, string[] expectedPaths)
    {
        if (primary == null || expectedPaths == null || expectedPaths.Length == 0) return false;
        var expected = expectedPaths.Select(path => AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(path)).ToArray();
        if (expected.Any(font => font == null) || expected[0] != primary) return false;
        var actual = new List<TMP_FontAsset> { primary };
        actual.AddRange(primary.fallbackFontAssetTable ?? new List<TMP_FontAsset>());
        if (actual.Count != expected.Length) return false;
        for (int i = 0; i < actual.Count; i++) if (actual[i] != expected[i]) return false;
        return true;
    }

    static bool ColorClose(Color actual, Color expected)
    {
        return Mathf.Abs(actual.r - expected.r) < 0.00001f && Mathf.Abs(actual.g - expected.g) < 0.00001f &&
               Mathf.Abs(actual.b - expected.b) < 0.00001f && Mathf.Abs(actual.a - expected.a) < 0.00001f;
    }

    static StaticTextBounds MeasureInkBounds(TMP_TextInfo info)
    {
        if (info == null || info.characterInfo == null) return null;
        var result = new StaticTextBounds {
            xMin = Single.PositiveInfinity, yMin = Single.PositiveInfinity,
            xMax = Single.NegativeInfinity, yMax = Single.NegativeInfinity,
        };
        for (int i = 0; i < info.characterCount; i++)
        {
            var character = info.characterInfo[i];
            if (!character.isVisible) continue;
            result.visibleCharacterCount++;
            result.hasVisibleGeometry = true;
            result.xMin = Mathf.Min(result.xMin, character.bottomLeft.x);
            result.yMin = Mathf.Min(result.yMin, character.bottomLeft.y);
            result.xMax = Mathf.Max(result.xMax, character.topRight.x);
            result.yMax = Mathf.Max(result.yMax, character.topRight.y);
        }
        if (!result.hasVisibleGeometry)
        {
            result.xMin = result.yMin = result.xMax = result.yMax = 0f;
            return result;
        }
        result.width = result.xMax - result.xMin;
        result.height = result.yMax - result.yMin;
        return result;
    }

    static List<StaticTextAssetIdentity> CaptureGlyphFontAssets(TMP_TextInfo info)
    {
        var found = new Dictionary<string, StaticTextAssetIdentity>(StringComparer.Ordinal);
        if (info == null || info.characterInfo == null) return found.Values.ToList();
        for (int i = 0; i < info.characterCount; i++)
        {
            var character = info.characterInfo[i];
            if (!character.isVisible || character.fontAsset == null) continue;
            var identity = CaptureIdentity(character.fontAsset);
            if (identity != null) found[identity.guid + ":" + identity.localFileId] = identity;
        }
        return found.Values.OrderBy(row => row.guid, StringComparer.Ordinal).ThenBy(row => row.localFileId).ToList();
    }

    static Color SourceOutlineColor(float[] values)
    {
        if (values == null || values.Length != 4) return Color.clear;
        return new Color(values[0] / 255f, values[1] / 255f, values[2] / 255f, values[3] / 255f);
    }
}
