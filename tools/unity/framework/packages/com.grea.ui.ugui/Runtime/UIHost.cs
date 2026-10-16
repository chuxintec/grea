using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Grea.Foundation.Contracts;
using Grea.Foundation.Runtime;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Grea.UI.UGUI
{
    public sealed class UIHost : MonoBehaviour, IBindingCheck
    {
        public Canvas canvas;
        public RectTransform safeAreaRoot;
        public bool bindOpenButton = true;
        Rect lastSafeArea;
        Vector2 lastViewport;
        public RectTransform pageLayer;
        public RectTransform modalLayer;
        public RectTransform toastLayer;
        public EventSystem events;
        public CommandButton openButton;
        public ModalPanel modal;
        LifetimeScope scope;
        bool started;
        public void Initialize()
        {
            if (scope != null && scope.IsAlive) return;
            foreach (var missing in MissingBindings()) throw new InvalidOperationException("UIHost." + missing);
            scope = new LifetimeScope();
            try { if (bindOpenButton) openButton.Bind(scope, stamp => { stamp.ThrowIfStale(); modal.Open(scope); return Task.CompletedTask; }); }
            catch { scope.Dispose(); scope = null; throw; }
        }
        // Both rectangles use the same physical-pixel coordinate system and origin.
        // Platform logical-pixel/top-left conversion belongs to the platform adapter.
        public void ApplySafeArea(Rect pixels, Vector2 viewport) => ApplySafeArea(pixels, new Rect(Vector2.zero, viewport));
        public void ApplySafeArea(Rect pixels, Rect viewport)
        {
            bool Finite(float v) => !float.IsNaN(v) && !float.IsInfinity(v);
            bool Valid(Rect r) => Finite(r.x) && Finite(r.y) && Finite(r.width) && Finite(r.height) &&
                Finite(r.xMax) && Finite(r.yMax) && r.width > 0 && r.height > 0;
            if (!Valid(pixels) || !Valid(viewport)) throw new ArgumentOutOfRangeException(nameof(pixels), "Finite positive pixel rectangles required");
            float left = Mathf.Max(pixels.xMin, viewport.xMin), bottom = Mathf.Max(pixels.yMin, viewport.yMin);
            float right = Mathf.Min(pixels.xMax, viewport.xMax), top = Mathf.Min(pixels.yMax, viewport.yMax);
            if (right <= left || top <= bottom) throw new ArgumentOutOfRangeException(nameof(pixels), "Safe area must intersect the viewport");
            if (!safeAreaRoot) throw new InvalidOperationException("UIHost.safeAreaRoot is required");
            safeAreaRoot.anchorMin = new Vector2((left - viewport.xMin) / viewport.width, (bottom - viewport.yMin) / viewport.height);
            safeAreaRoot.anchorMax = new Vector2((right - viewport.xMin) / viewport.width, (top - viewport.yMin) / viewport.height);
            safeAreaRoot.offsetMin = safeAreaRoot.offsetMax = Vector2.zero;
        }
        void LateUpdate()
        {
            if (!safeAreaRoot || Screen.width <= 0 || Screen.height <= 0 || Screen.safeArea.width <= 0 || Screen.safeArea.height <= 0) return;
            var viewport = new Vector2(Screen.width, Screen.height);
            if (lastViewport == viewport && lastSafeArea == Screen.safeArea) return;
            ApplySafeArea(Screen.safeArea, viewport); lastViewport = viewport; lastSafeArea = Screen.safeArea;
        }
        void Start() { started = true; Initialize(); }
        void OnEnable() { if (started) Initialize(); }
        void OnDisable() { var old = scope; scope = null; old?.Dispose(); }
        void OnDestroy() { var old = scope; scope = null; old?.Dispose(); }
        public IEnumerable<string> MissingBindings()
        {
            if (!canvas) yield return nameof(canvas);
            if (!pageLayer) yield return nameof(pageLayer);
            if (!modalLayer) yield return nameof(modalLayer);
            if (!toastLayer) yield return nameof(toastLayer);
            if (!events) yield return nameof(events);
            if (bindOpenButton && !openButton) yield return nameof(openButton);
            if (bindOpenButton && !modal) yield return nameof(modal);
        }
    }
}
