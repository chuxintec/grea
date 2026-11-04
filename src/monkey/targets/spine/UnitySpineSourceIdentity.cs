using UnityEngine;

// Serialized, callback-free identity metadata for source Spine components.
// It lets Editor readback distinguish multiple native renderers on one node.
[AddComponentMenu("")]
public sealed class UnitySpineSourceIdentity : MonoBehaviour
{
    // Marker identity belongs to the saved source template. Expanded sync
    // instances resolve their logical stage sourceComponentId only through
    // the explicit TemplateOrigin chain in the frozen stage plan.
    [HideInInspector] public string sourceComponentId;
    [HideInInspector] public string templateSourceId;
    [HideInInspector] public string templateSourcePrefabId;
    [HideInInspector] public string instanceSourceComponentId;
    [HideInInspector] public string rendererKind;
    [HideInInspector] public Behaviour renderer;
    [HideInInspector] public float sourceTimeScale;
    [HideInInspector] public float nativeTimeScale;
    [HideInInspector] public bool sourceTimeScaleVerified;
    [HideInInspector] public bool persistentVisiblePose;
}
