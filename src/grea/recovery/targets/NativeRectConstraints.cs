using UnityEngine;
using UnityEngine.EventSystems;

// A native RectTransform controller, independent of source IDs or engine IR.
[ExecuteAlways, RequireComponent(typeof(RectTransform))]
public sealed class NativeRectConstraints : UIBehaviour
{
    public enum Edge { Unconstrained, Minimum, Center, Maximum, Stretch }
    public enum UpdatePolicy { Once, ViewportResize, Continuous }
    public Edge Horizontal, Vertical;
    public UpdatePolicy Policy;
    public Vector2 Minimum, Maximum, Center;
    public Vector2 MinimumFraction, MaximumFraction, CenterFraction;
    public bool Configured;
    bool initialized,applying;
    Vector2 viewport;
    Rect previousParentRect;
    protected override void OnEnable(){base.OnEnable();initialized=false;Refresh();}
    void LateUpdate(){Refresh();}
    public void Refresh() {
        if(!Configured||!isActiveAndEnabled||applying)return;
        var rect=(RectTransform)transform;var parent=rect.parent as RectTransform;if(parent==null)return;
        var canvas=GetComponentInParent<Canvas>();
        var screen=canvas!=null?(canvas.rootCanvas.transform as RectTransform).rect.size:new Vector2(Screen.width,Screen.height);
        bool needed=!initialized||Policy==UpdatePolicy.Continuous||(Policy==UpdatePolicy.ViewportResize&&(screen!=viewport || parent.rect!=previousParentRect));
        if(!Application.isPlaying)needed=true;
        if(!needed)return;
        applying=true;
        try {
            var position=rect.localPosition;
            for(int axis=0;axis<2;axis++) {
                var edge=axis==0?Horizontal:Vertical;if(edge==Edge.Unconstrained)continue;
                float parentSize=parent.rect.size[axis],size=rect.rect.size[axis],pivot=rect.pivot[axis];
                float low=Minimum[axis]+MinimumFraction[axis]*parentSize,high=Maximum[axis]+MaximumFraction[axis]*parentSize;
                float scale=rect.localScale[axis];
                if(scale<0) pivot=1-pivot;
                scale=Mathf.Abs(scale);
                size*=scale;
                float start=-parent.pivot[axis]*parentSize;
                if(edge==Edge.Stretch){size=parentSize-low-high;if(scale>0)rect.SetSizeWithCurrentAnchors((RectTransform.Axis)axis,size/scale);position[axis]=start+low+pivot*size;}
                else if(edge==Edge.Minimum)position[axis]=start+low+pivot*size;
                else if(edge==Edge.Maximum)position[axis]=start+parentSize-high-(1-pivot)*size;
                else position[axis]=start+parentSize*.5f+Center[axis]+CenterFraction[axis]*parentSize+(pivot-.5f)*size;
            }
            rect.localPosition=position;initialized=true;viewport=screen;previousParentRect=parent.rect;
        }finally{applying=false;}
    }
}
