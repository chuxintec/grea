// Renderer helper for the bounded prefab_static_richtext.py static projection.
// It applies already-validated literal data and never resolves or invokes scripts.
using System;
using TMPro;
using UnityEngine;

public static class UnityStaticRichText
{
    [Serializable]
    public sealed class Spec
    {
        public string schema, sourceId, unityMarkup;
        public float fontSize, lineHeight, maxWidth;
        public int horizontalAlign, verticalAlign;
        public bool wrap, richText, staticOnly, convertible, renderReady, componentEnabled;
    }

    public static void Apply(TMP_Text label, Spec spec)
    {
        if (label == null) throw new ArgumentNullException(nameof(label));
        if (spec == null || spec.schema != "monkey-static-richtext/1" || !spec.staticOnly ||
            !spec.convertible || !spec.renderReady || !spec.richText)
            throw new InvalidOperationException("RichText is not a validated static projection: " + (spec?.sourceId ?? "<missing>"));
        if (spec.fontSize <= 0 || spec.lineHeight <= 0 || spec.maxWidth < 0 ||
            spec.horizontalAlign < 0 || spec.horizontalAlign > 2 ||
            spec.verticalAlign < 0 || spec.verticalAlign > 2)
            throw new InvalidOperationException("Static RichText metrics are outside the supported contract: " + spec.sourceId);
        if (label.font == null)
            throw new InvalidOperationException("A source-backed native font/fallback chain must be assigned before static RichText: " + spec.sourceId);
        if (spec.maxWidth > 0 && label.rectTransform != null &&
            Mathf.Abs(label.rectTransform.rect.width - spec.maxWidth) > 0.5f)
            throw new InvalidOperationException("RichText maxWidth differs from the converted source node width: " + spec.sourceId);

        label.text = spec.unityMarkup ?? string.Empty;
        label.fontSize = spec.fontSize;
        label.richText = true;
        label.enableAutoSizing = false;
        label.textWrappingMode = spec.wrap ? TextWrappingModes.Normal : TextWrappingModes.NoWrap;
        label.horizontalAlignment = new[] {
            HorizontalAlignmentOptions.Left,
            HorizontalAlignmentOptions.Center,
            HorizontalAlignmentOptions.Right
        }[spec.horizontalAlign];
        label.verticalAlignment = new[] {
            VerticalAlignmentOptions.Top,
            VerticalAlignmentOptions.Middle,
            VerticalAlignmentOptions.Bottom
        }[spec.verticalAlign];
        if (label.font != null && label.font.faceInfo.pointSize > 0 && spec.fontSize > 0)
            label.lineSpacing = (spec.lineHeight - label.font.faceInfo.lineHeight * spec.fontSize /
                label.font.faceInfo.pointSize) * 100f / spec.fontSize;
        label.raycastTarget = false;
        label.enabled = spec.componentEnabled;
    }
}
