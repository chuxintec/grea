using UnityEngine;
using UnityEngine.UI;

// A transparent rectangular native raycast surface when the source has no image.
[RequireComponent(typeof(RectTransform), typeof(CanvasRenderer))]
public sealed class NativeInputBlockerSurface : MaskableGraphic
{
    protected override void OnPopulateMesh(VertexHelper helper)
    {
        helper.Clear();
        var r = rectTransform.rect;
        var clear = new Color32(0, 0, 0, 0);
        helper.AddVert(new Vector3(r.xMin, r.yMin), clear, Vector2.zero);
        helper.AddVert(new Vector3(r.xMin, r.yMax), clear, Vector2.zero);
        helper.AddVert(new Vector3(r.xMax, r.yMax), clear, Vector2.zero);
        helper.AddVert(new Vector3(r.xMax, r.yMin), clear, Vector2.zero);
        helper.AddTriangle(0, 1, 2); helper.AddTriangle(2, 3, 0);
    }
}
