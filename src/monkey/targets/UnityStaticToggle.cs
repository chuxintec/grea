using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

/// <summary>Applies source-evidenced Toggle state only. No source event is invoked; components stay disabled.</summary>
public static class UnityStaticToggle
{
    [Serializable] public sealed class Binding
    {
        public string kind, sourceId, nodeSourceId, checkMarkSourceId, targetSourceId, groupSourceId, groupNodeSourceId;
        public string[] targetRendererSourceIds;
        public bool checkedPresent, checkedValue, interactablePresent, interactableValue;
        public bool checkMarkPresent, targetPresent, allowSwitchOffPresent, allowSwitchOffValue;
        public bool targetHasSourceRenderer, sourceToggleEnabled;
        public bool zoomScalePresent, zoomScaleSourceDefaultVerified;
        public float zoomScaleValue;
        public bool transitionPresent, normalColorPresent, allowSwitchOffSourceDefaultVerified;
        public bool checkedSourceDefaultVerified, interactableSourceDefaultVerified, checkMarkSourceDefaultVerified;
        public bool targetSourceDefaultVerified, transitionSourceDefaultVerified, normalColorSourceDefaultVerified;
        public int transitionValue;
        public string unityTransition;
        public ColorValue normalColorValue;
        public string[] gaps;
    }
    [Serializable] public sealed class ColorValue { public float r, g, b, a; }
    [Serializable] public sealed class Spec { public Binding[] bindings; }
    [Serializable] public sealed class FieldRead
    {
        public string sourceId, kind, checkMarkSourceId, targetSourceId, groupSourceId, groupNodeSourceId;
        public bool verified, checkedValue, interactableValue, allowSwitchOffValue;
        public float zoomScaleValue;
        public int transitionValue;
        public string unityTransition;
        public ColorValue normalColorValue;
        public string[] gaps;
    }
    [Serializable] public sealed class Readback { public bool dynamicBehaviorComplete; public FieldRead[] fields; }

    public static string[] Apply(Spec spec, Func<string, GameObject> resolveNode, Func<string, UnityEngine.Object> resolveComponent)
    {
        var gaps = new List<string>();
        if (spec == null || spec.bindings == null) return new[] { "missing_toggle_spec" };
        var groupsById = new Dictionary<string, Binding>(StringComparer.Ordinal);
        var groupsByNode = new Dictionary<string, Binding>(StringComparer.Ordinal);
        var invalidGroupIds = new HashSet<string>(StringComparer.Ordinal);
        var invalidGroupNodes = new HashSet<string>(StringComparer.Ordinal);
        foreach (var row in spec.bindings)
        {
            if (row == null || row.kind != "cc.ToggleContainer") continue;
            if (String.IsNullOrEmpty(row.sourceId) || String.IsNullOrEmpty(row.nodeSourceId))
            { gaps.Add((row.sourceId ?? "toggle_group") + ":toggle_group_source_invalid"); continue; }
            if (groupsById.ContainsKey(row.sourceId))
            { invalidGroupIds.Add(row.sourceId); gaps.Add(row.sourceId + ":toggle_group_source_duplicate"); continue; }
            if (groupsByNode.TryGetValue(row.nodeSourceId, out var prior))
            {
                invalidGroupNodes.Add(row.nodeSourceId); invalidGroupIds.Add(row.sourceId); invalidGroupIds.Add(prior.sourceId);
                gaps.Add(row.sourceId + ":multiple_toggle_groups_on_node"); continue;
            }
            groupsById.Add(row.sourceId, row); groupsByNode.Add(row.nodeSourceId, row);
        }

        // Source ToggleContainers must exist before Toggle rows are bound. The
        // input spec order is derived from source components and is not a native
        // dependency order.
        foreach (var row in spec.bindings)
        {
            if (row == null || row.kind != "cc.ToggleContainer" || invalidGroupIds.Contains(row.sourceId) || invalidGroupNodes.Contains(row.nodeSourceId)) continue;
            try
            {
                var go = resolveNode?.Invoke(row.nodeSourceId);
                if (!go) { gaps.Add(row.sourceId + ":node_unresolved"); continue; }
                var group = go.GetComponent<ToggleGroup>();
                if (!group) group = go.AddComponent<ToggleGroup>();
                group.enabled = false;
                if (row.allowSwitchOffPresent || row.allowSwitchOffSourceDefaultVerified) group.allowSwitchOff = row.allowSwitchOffValue;
            }
            catch (Exception e) { gaps.Add(row.sourceId + ":apply_failed:" + e.GetType().Name); }
        }
        foreach (var row in spec.bindings)
        {
            if (row == null || row.kind == "cc.ToggleContainer") continue;
            try
            {
                var go = resolveNode?.Invoke(row.nodeSourceId);
                if (!go) { gaps.Add(row.sourceId + ":node_unresolved"); continue; }
                if (row.kind == "cc.Toggle")
                {
                    var toggle = go.GetComponent<Toggle>();
                    if (!toggle) toggle = go.AddComponent<Toggle>();
                    toggle.enabled = false;
                    if (row.interactablePresent || row.interactableSourceDefaultVerified) toggle.interactable = row.interactableValue;
                    if (row.checkMarkPresent || row.checkMarkSourceDefaultVerified)
                    {
                        if (String.IsNullOrEmpty(row.checkMarkSourceId)) toggle.graphic = null;
                        else { var image = resolveComponent?.Invoke(row.checkMarkSourceId) as Graphic;
                            if (image) toggle.graphic = image; else gaps.Add(row.sourceId + ":checkmark_unresolved"); }
                    }
                    if (row.targetPresent || row.targetSourceDefaultVerified)
                    {
                        if (String.IsNullOrEmpty(row.targetSourceId)) toggle.targetGraphic = null;
                        else { var targetNode = resolveNode?.Invoke(row.targetSourceId);
                            if (row.targetHasSourceRenderer)
                            {
                                Graphic graphic = null; int graphicCount = 0;
                                foreach (var rendererId in row.targetRendererSourceIds ?? Array.Empty<string>())
                                {
                                    var sourceGraphic = resolveComponent?.Invoke(rendererId) as Graphic;
                                    if (sourceGraphic) { graphic = sourceGraphic; graphicCount++; }
                                }
                                if (targetNode && graphicCount == 1 && targetNode.GetComponent<Graphic>() == graphic) toggle.targetGraphic = graphic;
                                else gaps.Add(row.sourceId + ":target_graphic_unresolved");
                            }
                            else if (targetNode)
                            {
                                toggle.targetGraphic = null;
                                var retained = go.GetComponent<NativeStaticButtonTarget>();
                                if (!retained) retained = go.AddComponent<NativeStaticButtonTarget>();
                                if (retained.HasSourceToggleTarget && (retained.SourceToggleTarget != targetNode || retained.SourceToggleEnabled != row.sourceToggleEnabled))
                                    gaps.Add(row.sourceId + ":source_toggle_target_marker_conflict");
                                else
                                {
                                    retained.SourceToggleTarget = targetNode;
                                    retained.HasSourceToggleTarget = true;
                                    retained.SourceToggleEnabled = row.sourceToggleEnabled;
                                    retained.enabled = false;
                                }
                            }
                            else gaps.Add(row.sourceId + ":target_node_unresolved"); }
                    }
                    if (row.normalColorValue != null && (row.normalColorPresent || row.normalColorSourceDefaultVerified))
                    {
                        var colors = toggle.colors;
                        colors.normalColor = new Color(row.normalColorValue.r / 255f, row.normalColorValue.g / 255f,
                            row.normalColorValue.b / 255f, row.normalColorValue.a / 255f);
                        toggle.colors = colors;
                    }
                    var nativeTransition = row.unityTransition;
                    if (!String.IsNullOrEmpty(nativeTransition))
                    {
                        if (nativeTransition == "ColorTint") toggle.transition = Selectable.Transition.ColorTint;
                        else if (nativeTransition == "SpriteSwap") toggle.transition = Selectable.Transition.SpriteSwap;
                        else toggle.transition = Selectable.Transition.None;
                    }
                    if (row.zoomScalePresent || row.zoomScaleSourceDefaultVerified)
                    {
                        var retained = go.GetComponent<NativeStaticButtonTarget>();
                        if (!retained) retained = go.AddComponent<NativeStaticButtonTarget>();
                        if (retained.HasSourceToggleZoomScale && Math.Abs(retained.SourceToggleZoomScale - row.zoomScaleValue) > 0.00001f)
                            gaps.Add(row.sourceId + ":source_toggle_zoom_scale_marker_conflict");
                        else
                        {
                            retained.SourceToggleZoomScale = row.zoomScaleValue;
                            retained.HasSourceToggleZoomScale = true;
                            retained.enabled = false;
                        }
                    }
                    if (!String.IsNullOrEmpty(row.groupSourceId))
                    {
                        if (invalidGroupIds.Contains(row.groupSourceId) || !groupsById.TryGetValue(row.groupSourceId, out var groupRow)
                            || !String.Equals(groupRow.nodeSourceId, row.groupNodeSourceId, StringComparison.Ordinal))
                        { gaps.Add(row.sourceId + ":toggle_group_source_mismatch"); continue; }
                        var groupNode = resolveNode?.Invoke(row.groupNodeSourceId);
                        var group = groupNode ? groupNode.GetComponent<ToggleGroup>() : null;
                        if (group && go.transform.parent == groupNode.transform && groupsById.ContainsKey(row.groupSourceId))
                        { group.enabled = false; toggle.group = group; }
                        else gaps.Add(row.sourceId + ":toggle_group_unresolved");
                    }
                    else if (go.transform.parent && go.transform.parent.GetComponent<ToggleGroup>())
                        gaps.Add(row.sourceId + ":unexpected_toggle_group");
                    if (row.checkedPresent || row.checkedSourceDefaultVerified)
                    {
                        if (toggle.graphic)
                        {
                            if (toggle.graphic.gameObject == go) toggle.graphic.enabled = row.checkedValue;
                            else toggle.graphic.gameObject.SetActive(row.checkedValue);
                        }
                        toggle.SetIsOnWithoutNotify(row.checkedValue);
                        // Toggle.PlayEffect also updates the live preview alpha. That alpha is transient,
                        // so Read verifies the persisted GameObject/component visibility above instead.
                        if (toggle.graphic) toggle.graphic.canvasRenderer.SetAlpha(row.checkedValue ? 1f : 0f);
                    }
                }
                else gaps.Add(row.sourceId + ":unsupported_toggle_kind");
            }
            catch (Exception e) { gaps.Add(row.sourceId + ":apply_failed:" + e.GetType().Name); }
        }
        return gaps.ToArray();
    }

    public static string[] Create(Spec spec, Func<string, GameObject> resolveNode, Func<string, UnityEngine.Object> resolveComponent)
        => Apply(spec, resolveNode, resolveComponent);

    public static Readback Read(Spec spec, Func<string, GameObject> resolveNode, Func<string, UnityEngine.Object> resolveComponent)
    {
        var rows = new List<FieldRead>();
        if (spec?.bindings == null) return new Readback { dynamicBehaviorComplete = false, fields = rows.ToArray() };
        var groupsById = new Dictionary<string, Binding>(StringComparer.Ordinal);
        var groupsByNode = new Dictionary<string, Binding>(StringComparer.Ordinal);
        var invalidGroupIds = new HashSet<string>(StringComparer.Ordinal);
        var invalidGroupNodes = new HashSet<string>(StringComparer.Ordinal);
        foreach (var row in spec.bindings)
        {
            if (row == null || row.kind != "cc.ToggleContainer" || String.IsNullOrEmpty(row.sourceId) || String.IsNullOrEmpty(row.nodeSourceId)) continue;
            if (groupsById.ContainsKey(row.sourceId)) { invalidGroupIds.Add(row.sourceId); continue; }
            if (groupsByNode.TryGetValue(row.nodeSourceId, out var prior))
            { invalidGroupIds.Add(row.sourceId); invalidGroupIds.Add(prior.sourceId); invalidGroupNodes.Add(row.nodeSourceId); continue; }
            groupsById.Add(row.sourceId, row); groupsByNode.Add(row.nodeSourceId, row);
        }
        foreach (var row in spec.bindings)
        {
            var result = new FieldRead { sourceId = row.sourceId, kind = row.kind, gaps = row.gaps ?? Array.Empty<string>() };
            try
            {
                var go = resolveNode?.Invoke(row.nodeSourceId);
                if (!go) { result.gaps = Append(result.gaps, "node_unresolved"); rows.Add(result); continue; }
                if (row.kind == "cc.Toggle")
                {
                    var toggle = go.GetComponent<Toggle>();
                    if (!toggle || toggle.enabled) { result.gaps = Append(result.gaps, "toggle_missing_or_enabled"); }
                    else
                    {
                        result.checkedValue = toggle.isOn; result.interactableValue = toggle.interactable;
                        result.checkMarkSourceId = row.checkMarkPresent ? row.checkMarkSourceId : null;
                        result.targetSourceId = row.targetPresent ? row.targetSourceId : null;
                        result.groupSourceId = row.groupSourceId;
                        result.groupNodeSourceId = row.groupNodeSourceId;
                        bool ok = (!(row.checkedPresent || row.checkedSourceDefaultVerified) || toggle.isOn == row.checkedValue)
                            && (!(row.interactablePresent || row.interactableSourceDefaultVerified) || toggle.interactable == row.interactableValue);
                        if (row.zoomScalePresent || row.zoomScaleSourceDefaultVerified)
                        {
                            var retained = go.GetComponent<NativeStaticButtonTarget>();
                            result.zoomScaleValue = retained ? retained.SourceToggleZoomScale : 0f;
                            ok &= retained && !retained.enabled && retained.HasSourceToggleZoomScale
                                && Math.Abs(retained.SourceToggleZoomScale - row.zoomScaleValue) < 0.00001f;
                        }
                        if (row.checkMarkPresent || row.checkMarkSourceDefaultVerified)
                            ok &= String.IsNullOrEmpty(row.checkMarkSourceId) ? toggle.graphic == null : ReferenceEquals(toggle.graphic, resolveComponent?.Invoke(row.checkMarkSourceId));
                        if (toggle.graphic && (row.checkedPresent || row.checkedSourceDefaultVerified))
                        {
                            bool persistedVisible = toggle.graphic.gameObject == go
                                ? toggle.graphic.enabled : toggle.graphic.gameObject.activeSelf;
                            ok &= persistedVisible == row.checkedValue;
                        }
                        if ((row.targetPresent || row.targetSourceDefaultVerified) && String.IsNullOrEmpty(row.targetSourceId)) ok &= toggle.targetGraphic == null;
                        else if (row.targetPresent || row.targetSourceDefaultVerified)
                        {
                            var targetNode = resolveNode?.Invoke(row.targetSourceId);
                            if (row.targetHasSourceRenderer)
                            {
                                Graphic targetGraphic = null; int graphicCount = 0;
                                foreach (var rendererId in row.targetRendererSourceIds ?? Array.Empty<string>())
                                {
                                    var sourceGraphic = resolveComponent?.Invoke(rendererId) as Graphic;
                                    if (sourceGraphic) { targetGraphic = sourceGraphic; graphicCount++; }
                                }
                                ok &= targetNode && graphicCount == 1 && targetNode.GetComponent<Graphic>() == targetGraphic && toggle.targetGraphic == targetGraphic;
                            }
                            else
                            {
                                var retained = go.GetComponent<NativeStaticButtonTarget>();
                                ok &= targetNode && toggle.targetGraphic == null && retained && !retained.enabled
                                    && retained.HasSourceToggleTarget && retained.SourceToggleTarget == targetNode
                                    && retained.SourceToggleEnabled == row.sourceToggleEnabled;
                            }
                        }
                        result.transitionValue = row.transitionValue;
                        result.unityTransition = toggle.transition.ToString();
                        var normalColor = toggle.colors.normalColor;
                        result.normalColorValue = new ColorValue { r = normalColor.r * 255f, g = normalColor.g * 255f,
                            b = normalColor.b * 255f, a = normalColor.a * 255f };
                        if (row.normalColorValue != null && (row.normalColorPresent || row.normalColorSourceDefaultVerified))
                        {
                            var expected = row.normalColorValue;
                            ok &= Math.Abs(result.normalColorValue.r - expected.r) < 0.01f
                                && Math.Abs(result.normalColorValue.g - expected.g) < 0.01f
                                && Math.Abs(result.normalColorValue.b - expected.b) < 0.01f
                                && Math.Abs(result.normalColorValue.a - expected.a) < 0.01f;
                        }
                        string expectedTransition = row.unityTransition;
                        if (row.transitionPresent || row.transitionSourceDefaultVerified)
                            ok &= String.IsNullOrEmpty(expectedTransition) || result.unityTransition == expectedTransition;
                        if (!String.IsNullOrEmpty(row.groupSourceId))
                        {
                            var groupNode = resolveNode?.Invoke(row.groupNodeSourceId);
                            var group = groupNode ? groupNode.GetComponent<ToggleGroup>() : null;
                            var expectedGroup = groupsById.TryGetValue(row.groupSourceId, out var groupRow) ? groupRow : null;
                            bool groupMatches = !invalidGroupIds.Contains(row.groupSourceId) && expectedGroup != null
                                && String.Equals(expectedGroup.nodeSourceId, row.groupNodeSourceId, StringComparison.Ordinal)
                                && groupNode && go.transform.parent == groupNode.transform && group && toggle.group == group;
                            ok &= groupMatches;
                            if (!groupMatches) result.gaps = Append(result.gaps, "toggle_group_mismatch");
                        }
                        else
                        {
                            ok &= toggle.group == null;
                            if (go.transform.parent && go.transform.parent.GetComponent<ToggleGroup>())
                                result.gaps = Append(result.gaps, "unexpected_toggle_group");
                        }
                        result.verified = ok;
                        if (!ok) result.gaps = Append(result.gaps, "toggle_fields_mismatch");
                    }
                }
                else
                {
                    var group = go.GetComponent<ToggleGroup>();
                    result.allowSwitchOffValue = group && group.allowSwitchOff;
                    result.verified = !invalidGroupIds.Contains(row.sourceId) && !invalidGroupNodes.Contains(row.nodeSourceId)
                        && groupsById.TryGetValue(row.sourceId, out var groupRow) && ReferenceEquals(groupRow, row)
                        && group && !group.enabled && (!(row.allowSwitchOffPresent || row.allowSwitchOffSourceDefaultVerified) || group.allowSwitchOff == row.allowSwitchOffValue);
                    if (!result.verified) result.gaps = Append(result.gaps, "toggle_group_mismatch");
                }
            }
            catch (Exception e) { result.gaps = Append(result.gaps, "read_failed:" + e.GetType().Name); }
            rows.Add(result);
        }
        return new Readback { dynamicBehaviorComplete = false, fields = rows.ToArray() };
    }
    static string[] Append(string[] source, string item) { var list = new List<string>(source ?? Array.Empty<string>()); list.Add(item); return list.ToArray(); }
}
