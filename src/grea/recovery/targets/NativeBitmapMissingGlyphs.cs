using System;
using System.Collections.Generic;
using System.Text;
using TMPro;
using UnityEngine;

/// <summary>
/// Preserves a Creator 2.4 BitmapFont Label's full serialized text while TMP
/// renders only codepoints present in the source font definition. Missing source
/// glyphs were omitted by the source renderer; this does not recover their text.
/// </summary>
[ExecuteAlways]
public sealed class NativeBitmapMissingGlyphs : MonoBehaviour, ITextPreprocessor
{
    public TMP_Text Target;
    public TMP_FontAsset TargetFontAsset;
    public string SourceComponentId, SourceNodeId;
    public string SourceFontId;
    public string SourceText;
    public bool SourceEnabled;
    public int[] SourceGlyphUnicode = Array.Empty<int>();
    public int[] MissingGlyphUnicode = Array.Empty<int>();
    public string Policy = "cocos24-bitmap-missing-glyph-skip-v1";
    public string SourceCodeEvidence = "cocos2d/core/renderer/utils/label/bmfont.js:235";

    static readonly HashSet<int> NonGlyphControls = new HashSet<int> { 10 };

    void OnEnable()
    {
        InstallDerivedRenderer();
    }

    [Serializable]
    public sealed class Readback
    {
        public string sourceComponentId, sourceNodeId, sourceFontId, sourceText, targetText, displayText, policy, sourceCodeEvidence;
        public string targetSourceComponentId, targetFontSourceId;
        public int[] sourceGlyphUnicode, missingGlyphUnicode;
        public string targetGuid, targetFontGuid;
        public long targetLocalFileId, targetFontLocalFileId;
        public bool sourceEnabled, targetReferenceVerified, targetFontReferenceVerified, rendererInstalled;
        public bool persistedTargetReferenceVerified, persistedFontReferenceVerified;
        public bool missingGlyphsAreVisibleTextRecovered;
    }

    public string PreprocessText(string text)
    {
        if (text == null) return string.Empty;
        var glyphs = new HashSet<int>(SourceGlyphUnicode ?? Array.Empty<int>());
        var output = new StringBuilder(text.Length);
        for (int index = 0; index < text.Length;index++)
        {
            int codepoint=text[index]; // Creator 2.4 String.charAt semantics.
            if(codepoint==13)continue;
            if (glyphs.Contains(codepoint) || NonGlyphControls.Contains(codepoint))
                output.Append(text[index]);
        }
        return output.ToString();
    }

    public string GetDisplayText()
    {
        return PreprocessText(SourceText);
    }

    /// <summary>Install derived rendering on a saved prefab instance without changing Target.text or serialized contract fields.</summary>
    public bool InstallDerivedRenderer()
    {
        if (Target == null || TargetFontAsset == null || Target.font != TargetFontAsset ||
            Policy != "cocos24-bitmap-missing-glyph-skip-v1" ||
            String.IsNullOrEmpty(SourceComponentId) || String.IsNullOrEmpty(SourceNodeId) || String.IsNullOrEmpty(SourceFontId) ||
            SourceText == null || Target.text != SourceText)
            return false;
        Target.textPreprocessor = this;
        Target.ForceMeshUpdate(true, true);
        return Target.text == SourceText && Target.font == TargetFontAsset && System.Object.ReferenceEquals(Target.textPreprocessor, this);
    }

    public bool IsContractIntact(TMP_Text expectedTarget)
    {
        return expectedTarget != null && Target == expectedTarget &&
            TargetFontAsset != null && Target.font == TargetFontAsset && Target.text == SourceText &&
            Policy == "cocos24-bitmap-missing-glyph-skip-v1";
    }

    public Readback Read(TMP_Text expectedTarget, string expectedNodeId)
    {
        var targetMatches = expectedTarget != null && Target == expectedTarget && SourceNodeId == expectedNodeId;
        return new Readback
        {
            sourceComponentId=SourceComponentId, sourceNodeId=SourceNodeId, sourceEnabled=SourceEnabled,
            sourceFontId=SourceFontId, sourceText=SourceText, targetText=Target == null ? null : Target.text,
            displayText=GetDisplayText(), policy=Policy, sourceCodeEvidence=SourceCodeEvidence,
            targetSourceComponentId=targetMatches ? SourceComponentId : null,
            targetFontSourceId=Target != null && Target.font == TargetFontAsset ? SourceFontId : null,
            sourceGlyphUnicode=(int[])(SourceGlyphUnicode ?? Array.Empty<int>()).Clone(),
            missingGlyphUnicode=(int[])(MissingGlyphUnicode ?? Array.Empty<int>()).Clone(),
            targetReferenceVerified=targetMatches,
            targetFontReferenceVerified=Target != null && TargetFontAsset != null && Target.font == TargetFontAsset,
            rendererInstalled=Target != null && System.Object.ReferenceEquals(Target.textPreprocessor, this),
            missingGlyphsAreVisibleTextRecovered=false
        };
    }
}
