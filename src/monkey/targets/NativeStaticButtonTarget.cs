using UnityEngine;

// Explicit native reference retained when a source Button targets a grouping
// node without a Graphic. This component has no callbacks or runtime behavior.
public sealed class NativeStaticButtonTarget : MonoBehaviour, Monkey.NativeUiContracts.INativeStaticButtonTarget
{
    public GameObject Target;
    public GameObject TransitionTarget => Target;
    public bool SourceEnabled;
    public int SourceTransition;
    public float SourceZoomScale;
    public float SourceDuration;

    // Toggle.target can name a source node without any render component. Keep
    // that exact source identity separately so a Button on this same GameObject
    // can retain its own Target and SourceEnabled state unchanged.
    public GameObject SourceToggleTarget;
    public bool HasSourceToggleTarget;
    public bool SourceToggleEnabled;
    public float SourceToggleZoomScale;
    public bool HasSourceToggleZoomScale;
}
