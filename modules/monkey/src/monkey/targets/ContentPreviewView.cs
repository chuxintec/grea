// Native UI references for normal Unity editing. No source IDs or conversion runtime.
using UnityEngine;

public sealed class ContentPreviewView : MonoBehaviour
{
    [SerializeField] public UnityEngine.UI.Image[] Images;
    [SerializeField] public TMPro.TextMeshProUGUI[] Labels;
    [SerializeField] public UnityEngine.UI.Button[] Buttons;
}
