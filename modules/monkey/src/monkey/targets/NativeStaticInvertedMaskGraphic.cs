using System;
using System.Linq;
using UnityEngine;
using UnityEngine.UI;

namespace Monkey.StaticMaskSort
{
    /// <summary>Stencil geometry for an inverted RECT: canvas extent with the mask rect removed.</summary>
    [AddComponentMenu("")]
    [RequireComponent(typeof(CanvasRenderer))]
    public sealed class NativeStaticInvertedMaskGraphic : MaskableGraphic
    {
        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            var canvas = GetComponentInParent<Canvas>();
            var canvasRect = canvas == null ? null : canvas.transform as RectTransform;
            if (canvasRect == null) throw new InvalidOperationException("STATIC_INVERTED_MASK_CANVAS_MISSING: " + name);
            var axisAligned = Mathf.Abs(Vector3.Dot(canvasRect.right.normalized, rectTransform.right.normalized)) > .9999f &&
                              Mathf.Abs(Vector3.Dot(canvasRect.up.normalized, rectTransform.up.normalized)) > .9999f;
            if (!axisAligned) throw new InvalidOperationException("STATIC_INVERTED_MASK_CANVAS_TRANSFORM_UNSUPPORTED: " + name);
            var corners = new Vector3[4];
            canvasRect.GetWorldCorners(corners);
            var local = corners.Select(rectTransform.InverseTransformPoint).ToArray();
            var canvasMin = new Vector2(local.Min(p => p.x), local.Min(p => p.y));
            var canvasMax = new Vector2(local.Max(p => p.x), local.Max(p => p.y));
            var mask = rectTransform.rect;
            AddQuad(vh, new Vector2(canvasMin.x, mask.yMax), new Vector2(canvasMax.x, canvasMax.y));
            AddQuad(vh, new Vector2(canvasMin.x, canvasMin.y), new Vector2(canvasMax.x, mask.yMin));
            AddQuad(vh, new Vector2(canvasMin.x, mask.yMin), new Vector2(mask.xMin, mask.yMax));
            AddQuad(vh, new Vector2(mask.xMax, mask.yMin), new Vector2(canvasMax.x, mask.yMax));
        }

        void AddQuad(VertexHelper vh, Vector2 min, Vector2 max)
        {
            if (max.x <= min.x || max.y <= min.y) return;
            var start = vh.currentVertCount;
            vh.AddVert(new Vector3(min.x, min.y), color, Vector2.zero);
            vh.AddVert(new Vector3(min.x, max.y), color, Vector2.zero);
            vh.AddVert(new Vector3(max.x, max.y), color, Vector2.zero);
            vh.AddVert(new Vector3(max.x, min.y), color, Vector2.zero);
            vh.AddTriangle(start, start + 1, start + 2);
            vh.AddTriangle(start, start + 2, start + 3);
        }

        protected override void OnTransformParentChanged() { base.OnTransformParentChanged(); SetVerticesDirty(); }
        protected override void OnRectTransformDimensionsChange() { base.OnRectTransformDimensionsChange(); SetVerticesDirty(); }
    }
}
