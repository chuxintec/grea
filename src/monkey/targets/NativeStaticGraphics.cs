using UnityEngine;

/// <summary>Disabled Unity target carrier for frozen Creator Graphics references.</summary>
[DisallowMultipleComponent]
public sealed class NativeStaticGraphics : MonoBehaviour
{
    public string sourceId;
    public string[] sourceMaterialIds;
    public string[] sourceEffectIds;
    public string[] sourceEffectNames;
    public Material[] sourceMaterials;
    public string sourceDrawingCommands;
}
