using UnityEngine;
using UnityEngine.UI;

// Native typographic line box, evaluated again when TMP text or width changes.
// The converter supplies leading; no source graph or engine component is read.
[ExecuteAlways,RequireComponent(typeof(TMPro.TextMeshProUGUI))]
public sealed class NativeTextLineBox : MonoBehaviour, ILayoutElement
{
    public float LineHeight,ExtraLineFraction;
    TMPro.TextMeshProUGUI label;
    public void CalculateLayoutInputHorizontal() {}
    public void CalculateLayoutInputVertical(){label=GetComponent<TMPro.TextMeshProUGUI>();label.ForceMeshUpdate(true);}
    public float preferredHeight {get {
        if(label==null)label=GetComponent<TMPro.TextMeshProUGUI>();
        return (Mathf.Max(1,label.textInfo.lineCount)+ExtraLineFraction)*LineHeight+label.margin.y+label.margin.w;
    }}
    public float minWidth {get{return -1;}} public float preferredWidth {get{return -1;}} public float flexibleWidth {get{return -1;}}
    public float minHeight {get{return -1;}} public float flexibleHeight {get{return -1;}}
    public float maxWidth {get{return -1;}} public float maxHeight {get{return -1;}}
    public int layoutPriority {get{return 1;}}
}
