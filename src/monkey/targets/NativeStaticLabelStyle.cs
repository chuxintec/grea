using UnityEngine;
// Cocos 2.4.15 bitmap assembly consumes glyph metrics but not the Label style
// flags (cocos2d/core/renderer/utils/label/bmfont.js). Retain those authored
// values without adding synthetic TMP styles absent from the source output.
public sealed class NativeStaticLabelStyle : MonoBehaviour
{
    public TMPro.TMP_Text Target;
    public bool SourceBold, SourceItalic, SourceUnderline;
    public bool SourceOutlinePresent,SourceOutlineEnabled;
    public float SourceOutlineWidth;
    public Color SourceOutlineColor;
    public string SourceOutlineComponentId;
    public string Policy="cocos24-bitmap-styles-not-rendered-v1";
}
