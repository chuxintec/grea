using UnityEngine;
using UnityEngine.UI;

// Unity GridLayoutGroup supplies all placement, wrapping and child sizing.
// Prefer content metrics over a background Image, and collapse an empty
// dynamic content grid to its padding instead of reserving one minimum row.
[AddComponentMenu("Layout/Content Grid Layout Group")]
public sealed class IntrinsicGridLayoutGroup : GridLayoutGroup
{
    public override int layoutPriority { get { return 1; } }
    public override void CalculateLayoutInputVertical()
    {
        base.CalculateLayoutInputVertical();
        if(rectChildren.Count==0)
            SetLayoutInputForAxis(padding.vertical,padding.vertical,padding.vertical,-1,1);
    }
}
