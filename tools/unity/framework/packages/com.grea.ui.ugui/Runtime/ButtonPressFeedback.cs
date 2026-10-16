using System;
using System.Collections.Generic;
using Grea.Foundation.Runtime;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Grea.UI.UGUI
{
    /// <summary>Finite visual scaling only. Unity Button continues to own click semantics.</summary>
    [DisallowMultipleComponent]
    [RequireComponent(typeof(Button))]
    public sealed class ButtonPressFeedback : MonoBehaviour, IPointerDownHandler, IPointerUpHandler,
        IPointerExitHandler, IBeginDragHandler, IBindingCheck
    {
        [SerializeField] Button button;
        [SerializeField] Transform visual;
        [SerializeField, Range(.01f, 1)] float pressedScale = .9f;
        [SerializeField, Min(0)] float duration = .08f;
        Vector3 resting, lastWritten;
        float multiplier = 1, from = 1, to = 1, elapsed;
        bool ownsVisual, hasWritten, held;
        int pointerId;

        public void Configure(Button control, Transform target, float scale, float seconds)
        {
            if (!control) throw new ArgumentNullException(nameof(control));
            if (!target) throw new ArgumentNullException(nameof(target));
            if (!Finite(scale) || scale <= 0 || scale > 1) throw new ArgumentOutOfRangeException(nameof(scale));
            if (!Finite(seconds) || seconds < 0) throw new ArgumentOutOfRangeException(nameof(seconds));
            Cancel(); button = control; visual = target; pressedScale = scale; duration = seconds;
        }
        static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);
        bool CanPress => isActiveAndEnabled && button && button.isActiveAndEnabled && button.IsInteractable();

        public void OnPointerDown(PointerEventData data)
        {
            if (data.button != PointerEventData.InputButton.Left || held || !CanPress) return;
            foreach (var field in MissingBindings())
                throw new InvalidOperationException("ButtonPressFeedback." + field + " is missing or invalid");
            if (!ownsVisual) { resting = visual.localScale; ownsVisual = true; }
            ObserveExternalScale();
            held = true; pointerId = data.pointerId; Transition(pressedScale);
        }
        public void OnPointerUp(PointerEventData data)
        {
            if (!held || data.pointerId != pointerId || data.button != PointerEventData.InputButton.Left) return;
            held = false; Transition(1);
        }
        public void OnPointerExit(PointerEventData data)
        { if (held && data.pointerId == pointerId) Cancel(); }
        public void OnBeginDrag(PointerEventData data)
        { if (held && data.pointerId == pointerId) Cancel(); }
        void Transition(float target) { from = multiplier; to = target; elapsed = 0; }
        void ObserveExternalScale()
        {
            // A new authored scale becomes the base; cancellation must not erase that edit.
            if (ownsVisual && visual && hasWritten && visual.localScale != lastWritten)
                resting = visual.localScale;
        }
        void Update()
        {
            if (!ownsVisual) return;
            if (!visual || !CanPress) { Cancel(); return; }
            ObserveExternalScale();
            elapsed += Time.unscaledDeltaTime;
            float progress = duration <= 0 ? 1 : Mathf.Clamp01(elapsed / duration);
            multiplier = Mathf.Lerp(from, to, progress);
            lastWritten = new Vector3(resting.x * multiplier, resting.y * multiplier, resting.z);
            visual.localScale = lastWritten; hasWritten = true;
            if (!held && progress >= 1) Cancel();
        }
        public void Cancel()
        {
            ObserveExternalScale();
            if (ownsVisual && visual) visual.localScale = resting;
            held = ownsVisual = hasWritten = false;
            multiplier = from = to = 1; elapsed = 0;
        }
        void OnApplicationFocus(bool focused) { if (!focused) Cancel(); }
        void OnApplicationPause(bool paused) { if (paused) Cancel(); }
        void OnDisable() => Cancel();
        void OnDestroy() => Cancel();
        public IEnumerable<string> MissingBindings()
        {
            if (!button) yield return nameof(button);
            if (!visual) yield return nameof(visual);
            if (!Finite(pressedScale) || pressedScale <= 0 || pressedScale > 1) yield return nameof(pressedScale);
            if (!Finite(duration) || duration < 0) yield return nameof(duration);
        }
    }
}
