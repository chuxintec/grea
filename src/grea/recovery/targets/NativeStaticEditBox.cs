using TMPro;
using UnityEngine;
using UnityEngine.UI;

/// <summary>Disabled Unity target carrier for frozen Creator EditBox state.</summary>
[DisallowMultipleComponent]
public sealed class NativeStaticEditBox : MonoBehaviour
{
    public string sourceId;
    public Image background;
    public TMP_Text placeholderLabel;
    public TMP_Text textLabel;
    public int maxLength;
}
