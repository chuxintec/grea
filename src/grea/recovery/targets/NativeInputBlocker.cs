using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

// A bounded native UI event sink. It never invokes recovered business events.
[DisallowMultipleComponent]
public sealed class NativeInputBlocker : MonoBehaviour,
    IPointerDownHandler, IPointerUpHandler, IPointerClickHandler,
    IPointerEnterHandler, IPointerExitHandler, IScrollHandler,
    IBeginDragHandler, IDragHandler, IEndDragHandler
{
    [SerializeField] private Graphic surface;
    [SerializeField] private bool previousRaycast;
    [SerializeField] private bool ownsSurface;
    [SerializeField] private bool sourceActivityOverrideConfigured;
    [SerializeField] private bool sourceEnabledAtCapture;
    [SerializeField] private bool sourceActiveAtCapture;
    public Graphic Surface => surface;
    public bool OwnsSurface => ownsSurface;
    public bool PreviousRaycast => previousRaycast;

    // Import can create a hierarchy while its eventual source parents are
    // still active, then restore authored parent activity before saving.
    // Reapply source-effective input state at that boundary instead of relying
    // on an OnEnable/OnDisable callback to follow the final hierarchy.
    public bool SynchronizeSourceActivity(bool sourceEnabled, bool sourceActive)
    {
        if (surface == null || enabled != sourceEnabled) return false;
        sourceActivityOverrideConfigured = true;
        sourceEnabledAtCapture = sourceEnabled;
        sourceActiveAtCapture = sourceActive;
        Apply(sourceEnabled && sourceActive);
        var sourceEffectiveActive = sourceEnabled && sourceActive;
        return surface.raycastTarget == (sourceEffectiveActive || (!ownsSurface && previousRaycast)) &&
            (!ownsSurface || surface.enabled == sourceEffectiveActive);
    }

    public void Configure(Graphic existing)
    {
        sourceActivityOverrideConfigured = false;
        surface = existing;
        if (surface == null) {
            surface = gameObject.AddComponent<NativeInputBlockerSurface>();
            ownsSurface = true;
        }
        previousRaycast = surface.raycastTarget;
        Apply(isActiveAndEnabled);
    }
    void OnEnable() { Apply(true); }
    void OnDisable() { Apply(false); }
    void Apply(bool active) {
        if (surface == null) return;
        if (sourceActivityOverrideConfigured && !Application.isPlaying)
            active = enabled && sourceEnabledAtCapture && sourceActiveAtCapture;
        surface.raycastTarget = active || (!ownsSurface && previousRaycast);
        if (ownsSurface) surface.enabled = active;
    }
    public void OnPointerDown(PointerEventData e) { e.Use(); }
    public void OnPointerUp(PointerEventData e) { e.Use(); }
    public void OnPointerClick(PointerEventData e) { e.Use(); }
    public void OnPointerEnter(PointerEventData e) { e.Use(); }
    public void OnPointerExit(PointerEventData e) { e.Use(); }
    public void OnScroll(PointerEventData e) { e.Use(); }
    public void OnBeginDrag(PointerEventData e) { e.Use(); }
    public void OnDrag(PointerEventData e) { e.Use(); }
    public void OnEndDrag(PointerEventData e) { e.Use(); }
}
