using System;
using UnityEngine;

// Typed native uGUI references only; no source object graph or runtime lookup.
[ExecuteAlways, DisallowMultipleComponent]
public sealed class NativeHorizontalProgressFill : MonoBehaviour
{
    [SerializeField] private UnityEngine.UI.Slider progress;
    [SerializeField] private RectTransform fill;
    [SerializeField] private float fullLength;
    private UnityEngine.UI.Slider subscribed;

    public UnityEngine.UI.Slider Progress => progress;
    public RectTransform Fill => fill;
    public float FullLength => fullLength;

    public void Configure(UnityEngine.UI.Slider control, RectTransform imageRect, float length)
    {
        if (control == null || imageRect == null) throw new ArgumentNullException();
        if (control.fillRect != null) throw new ArgumentException("Slider must not also drive the fill rectangle.");
        if (float.IsNaN(length) || float.IsInfinity(length) || length < 0f)
            throw new ArgumentOutOfRangeException(nameof(length));
        if (Mathf.Abs(imageRect.pivot.x) > 0.0001f ||
            Mathf.Abs(imageRect.anchorMin.x - imageRect.anchorMax.x) > 0.0001f)
            throw new ArgumentException("A fixed horizontal anchor and left pivot are required.");
        Unsubscribe();
        progress = control;
        fill = imageRect;
        fullLength = length;
        Subscribe();
        Apply(progress.normalizedValue);
    }

    private void OnEnable() { Subscribe(); if (progress != null) Apply(progress.normalizedValue); }
    private void OnDisable() { Unsubscribe(); }
    private void OnDestroy() { Unsubscribe(); }
    private void Subscribe()
    {
        if (progress == null || fill == null || subscribed == progress) return;
        Unsubscribe();
        subscribed = progress;
        subscribed.onValueChanged.AddListener(OnValueChanged);
    }
    private void Unsubscribe()
    {
        if (subscribed != null) subscribed.onValueChanged.RemoveListener(OnValueChanged);
        subscribed = null;
    }
    private void OnValueChanged(float value) { Apply(progress.normalizedValue); }
    private void Apply(float normalized)
    {
        if (fill != null) fill.SetSizeWithCurrentAnchors(RectTransform.Axis.Horizontal,
            fullLength * Mathf.Clamp01(normalized));
    }
}
