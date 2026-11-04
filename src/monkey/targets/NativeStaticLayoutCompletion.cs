using System;
using UnityEngine;
using UnityEngine.UI;

// Source-backed Cocos Creator 2.4 Layout / Widget completion carrier.
// The pinned source algorithms are CCLayout.js and CCWidgetManager.js (v2.4.15).
// This component never edits a prefab pose during import or in Edit Mode. Start/Update
// apply constraints only in Play Mode; validation should call ApplyNow on a disposable clone.
[DisallowMultipleComponent, RequireComponent(typeof(RectTransform))]
public sealed class NativeStaticLayoutCompletion : MonoBehaviour
{
    [Serializable]
    public sealed class LayoutSlot
    {
        public string sourceComponentId;
        public int componentOrder;
        public bool sourceEnabled;
        public int layoutType, resize, startAxis, horizontalDirection, verticalDirection;
        public bool affectedByScale;
        public Vector4 padding; // left, bottom, right, top; fractional and negative values are preserved.
        public Vector2 spacingXY, cellSize, sourceLayoutCacheSize;
        public bool hasSourceLayoutCacheSize;
        public string[] sourceFieldPresence, unknownSourceFields;
    }

    [Serializable]
    public sealed class WidgetSlot
    {
        public string sourceComponentId;
        public int componentOrder;
        public bool sourceEnabled;
        public int alignFlags, alignMode;
        public Vector4 margins; // left, bottom, right, top.
        public Vector4 absoluteMargins; // left, bottom, right, top, each 0/1.
        public Vector2 center;
        public Vector2 centerAbsolute;
        public RectTransform target;
        public string targetSourceNodeId;
        public bool targetUsesParentWhenNull;
        public Vector2 sourceOriginalSize;
        public bool hasSourceOriginalWidth, hasSourceOriginalHeight;
        public string[] sourceFieldPresence, unknownSourceFields;
    }

    [Serializable]
    public sealed class SlotReadback
    {
        public string sourceComponentId;
        public int componentOrder;
        public bool sourceEnabled;
        public bool nativeComponentPresent;
        public bool savedReferenceVerified;
        public LayoutSlot layoutValue;
        public WidgetSlot widgetValue;
    }

    public LayoutSlot[] layouts = Array.Empty<LayoutSlot>();
    public WidgetSlot widget;
    public string sourceNodeId;
    public bool sourceContractConfigured;

    RectTransform Rect => (RectTransform)transform;
    bool applying;
    bool widgetInitialized;
    Vector2 widgetViewport;

    void Start() { if (Application.isPlaying && enabled) ApplyRuntime(false); }
    void LateUpdate() { if (Application.isPlaying && enabled) ApplyRuntime(false); }

    public void Configure(string sourceNode, LayoutSlot[] layoutSlots, WidgetSlot widgetSlot)
    {
        sourceNodeId = sourceNode;
        layouts = layoutSlots ?? Array.Empty<LayoutSlot>();
        Array.Sort(layouts, (a, b) => a.componentOrder.CompareTo(b.componentOrder));
        widget = widgetSlot;
        sourceContractConfigured = true;
        enabled = HasEnabledConstraint();
    }

    bool HasEnabledConstraint()
    {
        foreach (var slot in layouts) if (slot != null && slot.sourceEnabled && IsSupported(slot)) return true;
        return widget != null && widget.sourceEnabled && IsSupported(widget);
    }

    static bool IsSupported(LayoutSlot s) => s.layoutType == 0 && s.resize == 0 ||
        (s.layoutType == 1 || s.layoutType == 2) && s.resize >= 0 && s.resize <= 2;
    static bool IsSupported(WidgetSlot s) => s.alignFlags >= 0 && s.alignFlags <= 63 && s.alignMode >= 0 && s.alignMode <= 2;

    public void ApplyNow()
    {
        ApplyRuntime(true);
    }

    void ApplyRuntime(bool force)
    {
        if (!sourceContractConfigured || applying) return;
        applying = true;
        try
        {
            foreach (var slot in layouts)
            {
                if (slot == null || !slot.sourceEnabled || !IsSupported(slot)) continue;
                ApplyLayout(slot);
            }
            if (widget != null && widget.sourceEnabled && IsSupported(widget))
            {
                var viewport = new Vector2(Screen.width, Screen.height);
                bool shouldAlign = force || !widgetInitialized || widget.alignMode == 2 ||
                    (widget.alignMode == 1 && viewport != widgetViewport);
                if (shouldAlign)
                {
                    ApplyWidget(widget);
                    widgetInitialized = true;
                    widgetViewport = viewport;
                }
            }
        }
        finally { applying = false; }
    }

    void ApplyLayout(LayoutSlot slot)
    {
        if (slot.layoutType == 0 && slot.resize == 0) return;
        var owner = Rect;
        int axis = slot.layoutType == 1 ? 0 : 1;
        bool horizontal = axis == 0;
        float before = horizontal ? slot.padding.x : slot.padding.y;
        float after = horizontal ? slot.padding.z : slot.padding.w;
        float gap = slot.spacingXY[axis];
        var children = new System.Collections.Generic.List<RectTransform>();
        foreach (Transform child in transform)
        {
            var rect = child as RectTransform;
            if (rect != null && child.gameObject.activeInHierarchy && !IsIgnoredLayoutChild(rect)) children.Add(rect);
        }
        if (children.Count == 0) return;
        float length = owner.rect.size[axis];
        if (slot.resize == 1)
        {
            length = before + after + gap * (children.Count - 1);
            foreach (var child in children)
                length += child.rect.size[axis] * (slot.affectedByScale ? Mathf.Abs(child.localScale[axis]) : 1f);
            owner.SetSizeWithCurrentAnchors((RectTransform.Axis)axis, length);
        }
        if (slot.resize == 2)
        {
            float available = length - before - after - gap * (children.Count - 1);
            foreach (var child in children)
            {
                float scale = slot.affectedByScale ? Mathf.Abs(child.localScale[axis]) : 1f;
                if (scale == 0) continue;
                child.SetSizeWithCurrentAnchors((RectTransform.Axis)axis, available / children.Count / scale);
            }
        }
        bool reverse = horizontal ? slot.horizontalDirection == 1 : slot.verticalDirection == 1;
        float sign = reverse ? -1f : 1f;
        float ownerAnchor = owner.pivot[axis];
        float cursor = (reverse ? (1f - ownerAnchor) * length : -ownerAnchor * length) + sign * (reverse ? after : before);
        foreach (var child in children)
        {
            float factor = slot.affectedByScale ? Mathf.Abs(child.localScale[axis]) : 1f;
            float extent = child.rect.size[axis] * factor;
            float anchor = child.pivot[axis];
            if (reverse) anchor = 1f - anchor;
            var p = child.anchoredPosition;
            cursor += sign * anchor * extent + sign * gap;
            p[axis] = cursor;
            child.anchoredPosition = p;
            cursor += sign * (1f - anchor) * extent;
        }
    }

    public static bool IsIgnoredLayoutChild(Component child)
    {
        if (child == null) return false;
        var ignorers=child.GetComponents(typeof(ILayoutIgnorer));
        if(ignorers.Length==0)return false;
        foreach(var component in ignorers)if(!((ILayoutIgnorer)component).ignoreLayout)return false;
        return true;
    }

    void ApplyWidget(WidgetSlot s)
    {
        RectTransform target = s.target != null ? s.target : s.targetUsesParentWhenNull ? transform.parent as RectTransform : null;
        if (target == null) return;
        var owner = Rect;
        var ownerParent = owner.parent as RectTransform;
        for (int axis = 0; axis < 2; axis++)
        {
            int lowBit = axis == 0 ? 8 : 4, highBit = axis == 0 ? 32 : 1, centerBit = axis == 0 ? 16 : 2;
            if ((s.alignFlags & (lowBit | highBit | centerBit)) == 0) continue;
            float sourceTargetLength = target.rect.size[axis];
            float targetLength = sourceTargetLength;
            float targetAnchor = target.pivot[axis];
            int lowIndex = axis == 0 ? 0 : 1, highIndex = axis == 0 ? 2 : 3;
            float lowMargin = s.margins[lowIndex] * (s.absoluteMargins[lowIndex] != 0 ? 1f : targetLength);
            float highMargin = s.margins[highIndex] * (s.absoluteMargins[highIndex] != 0 ? 1f : targetLength);
            float low = -targetAnchor * targetLength + lowMargin;
            float high = low + targetLength - highMargin;
            float targetMiddle = (0.5f - targetAnchor) * targetLength;
            if (ownerParent != null && target != ownerParent)
            {
                low = ConvertTargetAxis(target, ownerParent, axis, low);
                high = ConvertTargetAxis(target, ownerParent, axis, high);
                targetMiddle = ConvertTargetAxis(target, ownerParent, axis, targetMiddle);
                float targetEnd = ConvertTargetAxis(target, ownerParent, axis, targetLength);
                targetLength = Mathf.Abs(targetEnd - ConvertTargetAxis(target, ownerParent, axis, 0));
            }
            float scale = owner.localScale[axis];
            float anchor = owner.pivot[axis];
            if (scale < 0) { anchor = 1f - anchor; scale = -scale; }
            bool stretch = (s.alignFlags & lowBit) != 0 && (s.alignFlags & highBit) != 0;
            bool centered = (s.alignFlags & centerBit) != 0;
            var position = owner.anchoredPosition;
            if (stretch)
            {
                float extent = high - low;
                if (scale != 0) owner.SetSizeWithCurrentAnchors((RectTransform.Axis)axis, extent / scale);
                position[axis] = low + anchor * extent;
            }
            else
            {
                float extent = owner.rect.size[axis] * scale;
                if (centered)
                {
                    int offsetIndex = axis;
                    float offset = s.center[offsetIndex] * (s.centerAbsolute[offsetIndex] != 0 ? 1f : sourceTargetLength);
                    if (ownerParent != null && target != ownerParent)
                        offset = ConvertTargetAxis(target,ownerParent,axis,offset)-ConvertTargetAxis(target,ownerParent,axis,0);
                    position[axis] = targetMiddle + (anchor - 0.5f) * extent + offset;
                }
                else if ((s.alignFlags & lowBit) != 0) position[axis] = low + anchor * extent;
                else position[axis] = high + (anchor - 1f) * extent;
            }
            owner.anchoredPosition = position;
        }
    }

    static float ConvertTargetAxis(RectTransform target, RectTransform localParent, int axis, float value)
    {
        var local = axis == 0 ? new Vector3(value, 0, 0) : new Vector3(0, value, 0);
        var parentLocal = localParent.InverseTransformPoint(target.TransformPoint(local));
        return parentLocal[axis];
    }

    public SlotReadback[] Readback()
    {
        var result = new System.Collections.Generic.List<SlotReadback>();
        foreach (var s in layouts)
            result.Add(new SlotReadback { sourceComponentId=s.sourceComponentId, componentOrder=s.componentOrder,
                sourceEnabled=s.sourceEnabled, nativeComponentPresent=true, savedReferenceVerified=true,
                layoutValue=s });
        if (widget != null)
            result.Add(new SlotReadback { sourceComponentId=widget.sourceComponentId, componentOrder=widget.componentOrder,
                sourceEnabled=widget.sourceEnabled, nativeComponentPresent=true, savedReferenceVerified=true,
                widgetValue=widget });
        return result.ToArray();
    }
}
