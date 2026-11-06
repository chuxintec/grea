using System;
using UnityEngine;
using UnityEngine.UI;

namespace Monkey.StaticSortQueueProxy
{
    /// <summary>
    /// Runtime-only transparent raycast surface for a typed Selectable whose
    /// source hit area has no Graphic of its own.
    /// </summary>
    [AddComponentMenu("")]
    [DisallowMultipleComponent]
    [RequireComponent(typeof(RectTransform), typeof(CanvasRenderer))]
    public sealed class NativeStaticSortInputSurface : MaskableGraphic
    {
        [NonSerialized] public Selectable owner;

        protected override void OnEnable()
        {
            base.OnEnable();
            if (canvasRenderer != null) canvasRenderer.cullTransparentMesh = false;
        }

        protected override void OnPopulateMesh(VertexHelper helper)
        {
            helper.Clear();
            var rect = rectTransform.rect;
            var transparent = new Color32(0, 0, 0, 0);
            helper.AddVert(new Vector3(rect.xMin, rect.yMin), transparent, Vector2.zero);
            helper.AddVert(new Vector3(rect.xMin, rect.yMax), transparent, Vector2.zero);
            helper.AddVert(new Vector3(rect.xMax, rect.yMax), transparent, Vector2.zero);
            helper.AddVert(new Vector3(rect.xMax, rect.yMin), transparent, Vector2.zero);
            helper.AddTriangle(0, 1, 2);
            helper.AddTriangle(2, 3, 0);
        }
    }
}
