using UnityEngine;
using UnityEngine.UI;

namespace Monkey.StaticMaskSort
{
    /// <summary>Ellipse stencil geometry used by the native uGUI Mask.</summary>
    [AddComponentMenu("")]
    [RequireComponent(typeof(CanvasRenderer))]
    public sealed class NativeStaticEllipseMaskGraphic : MaskableGraphic
    {
        // Cocos Creator 2.4.15 CCMask.js declares _segments: 64.
        [Min(3)] public int segments = 64;

        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            var rect = rectTransform.rect;
            var center = rect.center;
            vh.AddVert(center, color, Vector2.zero);
            for (var i = 0; i < segments; i++)
            {
                var angle = (float)(System.Math.PI * 2.0 * i / segments);
                var p = new Vector2(center.x + Mathf.Cos(angle) * rect.width * .5f,
                                    center.y + Mathf.Sin(angle) * rect.height * .5f);
                vh.AddVert(p, color, Vector2.zero);
            }
            for (var i = 0; i < segments; i++) vh.AddTriangle(0, i + 1, (i + 1) % segments + 1);
        }
    }
}
