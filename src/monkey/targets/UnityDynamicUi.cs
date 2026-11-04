using System;
using System.Linq;
using UnityEngine;

public static partial class MonkeyImporter
{
    static GameObject CreatePrefabUiContext(GameObject contents,Plan plan) {
        var context=new GameObject("OwnedPrefabUiContext",typeof(RectTransform),typeof(Canvas));
        UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(context,contents.scene);
        context.GetComponent<Canvas>().renderMode=RenderMode.WorldSpace;
        var rect=(RectTransform)context.transform;rect.pivot=Vector2.zero;rect.sizeDelta=new Vector2(plan.designSize[0],plan.designSize[1]);
        contents.transform.SetParent(rect,false);
        BindOptionalStaticSpineControlledCanvasContext(context,plan);
        return context;
    }
    static void ReleasePrefabUiContext(GameObject context) {
        if(context==null)return;
        ForgetOptionalStaticSpineReadbackOwnerContext(context);
        ForgetOptionalStaticSpineControlledCanvasContext(context);
    }
    [Serializable] public class DynamicUiChild {public int index;public bool active;public float[] size,position,scale;}
    [Serializable] public class DynamicUiState { public string action;public float[] size,position;public float fontSize;public DynamicUiChild[] children; }
    [Serializable] public class DynamicUiResult { public string sourceId,type,status;public DynamicUiState[] states; }
    static DynamicUiState UiState(string action,RectTransform rect) {
        var label=rect.GetComponent<TMPro.TextMeshProUGUI>();
        return new DynamicUiState {action=action,size=new[]{rect.rect.width,rect.rect.height},position=new[]{rect.localPosition.x,rect.localPosition.y},fontSize=label!=null?label.fontSize:0,
            children=Enumerable.Range(0,rect.childCount).Select(i=>{var c=(RectTransform)rect.GetChild(i);return new DynamicUiChild{index=i,active=c.gameObject.activeSelf,size=new[]{c.rect.width,c.rect.height},position=new[]{c.localPosition.x,c.localPosition.y},scale=new[]{c.localScale.x,c.localScale.y}};}).ToArray()};
    }
    static DynamicUiResult[] ProbeDynamicUi(Plan plan,GameObject instance) {
        var results=new System.Collections.Generic.List<DynamicUiResult>();
        var selected=plan.components.Where(c=>c.convertible&&c.enabled&&
            ((c.type=="cc.Label"&&!string.IsNullOrEmpty(c.text))||c.type=="cc.Widget"||c.type=="cc.Layout"&&(c.layoutType==1||c.layoutType==2)&&c.resize==1))
            .GroupBy(c=>c.type=="cc.Label"?c.type+"/"+c.overflow:c.type).Select(g=>g.First()).Take(6);
        if(plan.uiStateProbeVersion>=2)selected=(plan.uiProbeSources??new string[0]).Select(sid=>plan.components.Single(c=>c.sourceId==sid));
        foreach(var spec in selected) {
            var clone=UnityEngine.Object.Instantiate(instance);clone.name="OwnedDynamicUiProbe";
            try {
                var mapped=SavedNodeMap(plan.nodes,clone);var rect=mapped[spec.node];
                for(var p=rect.transform;p!=null;p=p.parent)p.gameObject.SetActive(true);
                SettleNativeLayout(clone);var states=new System.Collections.Generic.List<DynamicUiState>{UiState("baseline",rect)};
                if(spec.type=="cc.Label") {
                    var label=rect.GetComponent<TMPro.TextMeshProUGUI>();var original=label.text;
                    label.text=spec.overflow==3?original+"\n"+original:original+original;
                    SettleNativeLayout(clone);states.Add(UiState("text-change",rect));
                    if(spec.overflow==0&&rect.rect.width+0.01f<states[0].size[0]||spec.overflow==3&&rect.rect.height+0.01f<states[0].size[1])throw new InvalidOperationException("Native text sizing did not grow");
                    var grown=rect.rect.size;rect.gameObject.SetActive(false);label.text=original;
                    rect.gameObject.SetActive(true);SettleNativeLayout(clone);states.Add(UiState("show-original-text",rect));
                    if((rect.rect.size-new Vector2(states[0].size[0],states[0].size[1])).sqrMagnitude>.01f)throw new InvalidOperationException("Text hidden/restore geometry differs");
                } else if(spec.type=="cc.Widget") {
                    var constraint=rect.GetComponent<NativeRectConstraints>();var parent=rect.parent as RectTransform;
                    if(constraint==null||parent==null)continue;
                    var size=parent.rect.size;parent.SetSizeWithCurrentAnchors(RectTransform.Axis.Horizontal,size.x+40);parent.SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical,size.y+20);
                    SettleNativeLayout(clone);states.Add(UiState("parent-resize",rect));
                    rect.gameObject.SetActive(false);parent.SetSizeWithCurrentAnchors(RectTransform.Axis.Horizontal,size.x+80);
                    rect.gameObject.SetActive(true);SettleNativeLayout(clone);states.Add(UiState("show-after-resize",rect));
                } else if(plan.uiStateProbeVersion>=2) {
                    var first=rect.Cast<Transform>().Select(t=>t as RectTransform).FirstOrDefault(t=>t!=null&&t.gameObject.activeSelf);
                    var child=new GameObject("OwnedDynamicChild",typeof(RectTransform));var added=(RectTransform)child.transform;added.SetParent(rect,false);
                    added.sizeDelta=first!=null?first.rect.size:new Vector2(40,20);added.localScale=first!=null?first.localScale:Vector3.one;
                    SettleNativeLayout(clone);states.Add(UiState("add-child",rect));
                    child.SetActive(false);SettleNativeLayout(clone);states.Add(UiState("hide-child",rect));
                    child.SetActive(true);SettleNativeLayout(clone);states.Add(UiState("show-child",rect));
                    UnityEngine.Object.DestroyImmediate(child);SettleNativeLayout(clone);states.Add(UiState("remove-child",rect));
                    rect.SetSizeWithCurrentAnchors(RectTransform.Axis.Horizontal,rect.rect.width+60);rect.SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical,rect.rect.height+30);
                    SettleNativeLayout(clone);states.Add(UiState("container-resize",rect));
                    if(first!=null)first.localScale=Vector3.Scale(first.localScale,new Vector3(1.25f,.75f,1));
                    SettleNativeLayout(clone);states.Add(UiState("scale-child",rect));
                    if(first!=null){first.SetSizeWithCurrentAnchors(RectTransform.Axis.Horizontal,first.rect.width+12);first.SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical,first.rect.height+8);}
                    SettleNativeLayout(clone);states.Add(UiState("resize-child",rect));
                    rect.gameObject.SetActive(false);rect.gameObject.SetActive(true);SettleNativeLayout(clone);states.Add(UiState("hide-show-container",rect));
                } else {
                    var group=rect.GetComponent<NativeLinearLayoutGroup>();if(group==null)continue;
                    var child=new GameObject("OwnedDynamicChild",typeof(RectTransform));var added=(RectTransform)child.transform;
                    added.SetParent(rect,false);added.sizeDelta=new Vector2(40,20);
                    SettleNativeLayout(clone);states.Add(UiState("add-child",rect));
                    float expected=states[0].size[group.Axis]+(group.Axis==0?40:20)+group.Spacing;
                    if(Math.Abs(rect.rect.size[group.Axis]-expected)>.01f)throw new InvalidOperationException("Dynamic child layout extent differs");
                    child.SetActive(false);SettleNativeLayout(clone);states.Add(UiState("hide-child",rect));
                    child.SetActive(true);SettleNativeLayout(clone);states.Add(UiState("show-child",rect));
                    UnityEngine.Object.DestroyImmediate(child);SettleNativeLayout(clone);states.Add(UiState("remove-child",rect));
                    if(Math.Abs(rect.rect.size[group.Axis]-states[0].size[group.Axis])>.01f)throw new InvalidOperationException("Dynamic child removal did not restore extent");
                }
                results.Add(new DynamicUiResult{sourceId=spec.sourceId,type=spec.type,status="native-state-changes-passed",states=states.ToArray()});
            } finally {UnityEngine.Object.DestroyImmediate(clone);}
        }
        return results.ToArray();
    }
    static void ConfigureWidget(GameObject go,ComponentSpec spec) {
        var controller=go.AddComponent<NativeRectConstraints>();controller.enabled=false;
        Func<int,int,int,NativeRectConstraints.Edge> edge=(min,center,max)=>
            (spec.flags&min)!=0&&(spec.flags&max)!=0?NativeRectConstraints.Edge.Stretch:
            (spec.flags&min)!=0?NativeRectConstraints.Edge.Minimum:
            (spec.flags&max)!=0?NativeRectConstraints.Edge.Maximum:
            (spec.flags&center)!=0?NativeRectConstraints.Edge.Center:NativeRectConstraints.Edge.Unconstrained;
        controller.Horizontal=edge(8,16,32);controller.Vertical=edge(4,2,1);
        controller.Policy=(NativeRectConstraints.UpdatePolicy)spec.alignMode;
        var minimum=Vector2.zero;var maximum=Vector2.zero;var minimumFraction=Vector2.zero;var maximumFraction=Vector2.zero;
        for(int axis=0;axis<2;axis++) {
            if(spec.absolute[axis])minimum[axis]=spec.margins[axis];else minimumFraction[axis]=spec.margins[axis];
            if(spec.absolute[axis+2])maximum[axis]=spec.margins[axis+2];else maximumFraction[axis]=spec.margins[axis+2];
        }
        controller.Minimum=minimum;controller.Maximum=maximum;controller.MinimumFraction=minimumFraction;controller.MaximumFraction=maximumFraction;
        for(int axis=0;axis<2;axis++){if(spec.centerAbsolute[axis])controller.Center[axis]=spec.center[axis];else controller.CenterFraction[axis]=spec.center[axis];}
        controller.Configured=true;controller.enabled=spec.enabled;controller.Refresh();
    }
    static void ConfigureLabel(GameObject go,TMPro.TextMeshProUGUI label,ComponentSpec spec,bool bitmap) {
        float lineHeight=spec.lineHeight==0?spec.fontSize:spec.lineHeight;
        label.lineSpacing=spec.fontSize>0?(lineHeight-label.font.faceInfo.lineHeight*spec.fontSize/label.font.faceInfo.pointSize)*100f/spec.fontSize:0;
        label.enableAutoSizing=spec.overflow==2;label.fontSizeMax=spec.fontSize;label.fontSizeMin=.1f;
        label.overflowMode=spec.overflow==1?TMPro.TextOverflowModes.Masking:TMPro.TextOverflowModes.Overflow;
        if(spec.overflow==0||spec.overflow==3) {
            if(!bitmap){var box=go.AddComponent<NativeTextLineBox>();box.LineHeight=lineHeight;box.ExtraLineFraction=.26f;box.enabled=spec.enabled;}
            var fitter=go.AddComponent<UnityEngine.UI.ContentSizeFitter>();
            fitter.horizontalFit=spec.overflow==0?UnityEngine.UI.ContentSizeFitter.FitMode.PreferredSize:UnityEngine.UI.ContentSizeFitter.FitMode.Unconstrained;
            fitter.verticalFit=UnityEngine.UI.ContentSizeFitter.FitMode.PreferredSize;fitter.enabled=spec.enabled;
        }
    }
    static UnityEngine.UI.LayoutGroup ConfigureNativeGrid(GameObject go,ComponentSpec spec) {
        UnityEngine.UI.LayoutGroup result;
        int align=(spec.verticalDirection==0?6:0)+(spec.horizontalDirection==1?2:0);
        if(spec.nativeLayoutMode=="unity-horizontal-row") {
            var row=go.AddComponent<UnityEngine.UI.HorizontalLayoutGroup>();row.enabled=false;
            row.childControlWidth=false;row.childControlHeight=false;row.childForceExpandWidth=false;row.childForceExpandHeight=false;
            row.childScaleWidth=false;row.childScaleHeight=false;row.reverseArrangement=spec.horizontalDirection==1;
            row.spacing=spec.spacingXY[0];result=row;
        } else {
            if(spec.nativeLayoutMode!="unity-grid"&&spec.nativeLayoutMode!="unity-content-grid")throw new InvalidOperationException("Native grid mapping absent; regenerate or review the source candidate");
            var grid=spec.nativeLayoutMode=="unity-content-grid"&&spec.enabled?go.AddComponent<IntrinsicGridLayoutGroup>():go.AddComponent<UnityEngine.UI.GridLayoutGroup>();grid.enabled=false;
            if(spec.nativeCellSize==null||spec.nativeCellSize.Length!=2)throw new InvalidOperationException("Explicit native cell size required");
            grid.cellSize=new Vector2(spec.nativeCellSize[0],spec.nativeCellSize[1]);grid.spacing=new Vector2(spec.spacingXY[0],spec.spacingXY[1]);
            grid.startCorner=(UnityEngine.UI.GridLayoutGroup.Corner)((spec.verticalDirection==0?2:0)+(spec.horizontalDirection==1?1:0));
            grid.startAxis=UnityEngine.UI.GridLayoutGroup.Axis.Horizontal;grid.constraint=UnityEngine.UI.GridLayoutGroup.Constraint.Flexible;
            result=grid;
        }
        result.childAlignment=(TextAnchor)align;result.padding=new RectOffset((int)spec.padding[0],(int)spec.padding[2],(int)spec.padding[3],(int)spec.padding[1]);result.enabled=spec.enabled;
        if(spec.resize==1){
            var fitter=go.GetComponent<UnityEngine.UI.ContentSizeFitter>()??go.AddComponent<UnityEngine.UI.ContentSizeFitter>();
            if(fitter.horizontalFit!=UnityEngine.UI.ContentSizeFitter.FitMode.Unconstrained)throw new InvalidOperationException("Grid has an unrelated horizontal fitter");
            fitter.verticalFit=UnityEngine.UI.ContentSizeFitter.FitMode.PreferredSize;fitter.enabled=spec.enabled;
        }
        return result;
    }
    static void ConfigureLinearLayout(GameObject go,ComponentSpec spec) {
        var group=go.AddComponent<NativeLinearLayoutGroup>();group.enabled=false;
        group.Axis=spec.layoutType-1;group.Reverse=spec.layoutType==1?spec.horizontalDirection==1:spec.verticalDirection==1;
        group.ResizeChildren=spec.resize==2;group.ResizeContainer=spec.resize==1;group.IncludeScale=spec.affectedByScale;group.AlignCrossAxis=spec.alignCross;
        group.Spacing=spec.spacingXY[group.Axis];group.padding=new RectOffset((int)spec.padding[0],(int)spec.padding[2],(int)spec.padding[3],(int)spec.padding[1]);
        group.enabled=spec.enabled;
        if(spec.resize==1){var fitter=go.AddComponent<UnityEngine.UI.ContentSizeFitter>();
            if(group.Axis==0)fitter.horizontalFit=UnityEngine.UI.ContentSizeFitter.FitMode.PreferredSize;
            else fitter.verticalFit=UnityEngine.UI.ContentSizeFitter.FitMode.PreferredSize;
            fitter.enabled=spec.enabled;
        }
    }
}
