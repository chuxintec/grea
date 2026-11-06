using UnityEngine;
using UnityEngine.UI;

// Native uGUI layout. Arranges the main axis while retaining each child's
// authored position on the other axis, including when the container resizes.
[AddComponentMenu("Layout/Native Linear Layout Group")]
public sealed class NativeLinearLayoutGroup : NativeChildLayoutGroup
{
    public int Axis;
    public bool Reverse, IncludeScale, AlignCrossAxis, ResizeContainer, ResizeChildren;
    public float Spacing;
    public override int layoutPriority { get { return 1; } }
    float Extent(RectTransform child) { return child.rect.size[Axis] * (IncludeScale ? Mathf.Abs(child.localScale[Axis]) : 1); }
    float Preferred() {
        float result=Axis==0?padding.horizontal:padding.vertical;
        foreach(var child in rectChildren)result+=Extent(child);
        return result+Spacing*(rectChildren.Count-1);
    }
    public override void CalculateLayoutInputHorizontal() {
        base.CalculateLayoutInputHorizontal();
        float size=Axis==0?Preferred():rectTransform.rect.width;
        SetLayoutInputForAxis(size,float.PositiveInfinity,size,-1,0);
    }
    public override void CalculateLayoutInputVertical() {
        float size=Axis==1?Preferred():rectTransform.rect.height;
        SetLayoutInputForAxis(size,float.PositiveInfinity,size,-1,1);
    }
    public override void SetLayoutHorizontal() { if(Axis==0)Arrange(); }
    public override void SetLayoutVertical() { if(Axis==1)Arrange(); }
    void Arrange() {
        if(ResizeChildren&&rectChildren.Count>0){
            float available=rectTransform.rect.size[Axis]-(Axis==0?padding.horizontal:padding.vertical)-Spacing*(rectChildren.Count-1);
            foreach(var child in rectChildren){float scale=IncludeScale?Mathf.Abs(child.localScale[Axis]):1;
                if(scale>0)child.SetSizeWithCurrentAnchors((RectTransform.Axis)Axis,available/rectChildren.Count/scale);
            }
        }
        if(rectChildren.Count==0&&ResizeContainer){rectTransform.SetSizeWithCurrentAnchors((RectTransform.Axis)Axis,Preferred());return;}
        float length=rectTransform.rect.size[Axis],origin=rectTransform.pivot[Axis];
        float start=Axis==0?(Reverse?padding.right:padding.left):(Reverse?padding.top:padding.bottom);
        float cursor=(Reverse?1-origin:-origin)*length+(Reverse?-start:start);
        foreach(var child in rectChildren) {
            float extent=Extent(child),pos=cursor+(Reverse?-(1-child.pivot[Axis]):child.pivot[Axis])*extent;
            var min=child.anchorMin;var max=child.anchorMax;
            min[Axis]=max[Axis]=origin;child.anchorMin=min;child.anchorMax=max;
            var position=child.anchoredPosition;position[Axis]=pos;
            child.anchoredPosition=position;
            if(AlignCrossAxis){var local=child.localPosition;local[1-Axis]=0;child.localPosition=local;}
            cursor+=(Reverse?-1:1)*(extent+Spacing);
        }
    }
}

// RectTransform does not emit a dimensions event for a child's scale change.
// Observe only layout inputs, never the positions produced by the group.
public abstract class NativeChildLayoutGroup : LayoutGroup
{
    int geometryHash;
    protected virtual void LateUpdate(){
        int hash=transform.childCount;
        unchecked{for(int i=0;i<transform.childCount;i++){
            var child=transform.GetChild(i)as RectTransform;if(child==null)continue;
            hash=hash*31+child.GetEntityId().GetHashCode();hash=hash*31+child.gameObject.activeInHierarchy.GetHashCode();
            hash=hash*31+child.rect.size.GetHashCode();hash=hash*31+child.localScale.GetHashCode();hash=hash*31+child.pivot.GetHashCode();
        }}
        if(hash!=geometryHash){geometryHash=hash;SetDirty();}
    }
}
