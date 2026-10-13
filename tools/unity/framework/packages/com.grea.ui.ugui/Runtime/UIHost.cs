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
            try { openButton.Bind(scope, stamp => { stamp.ThrowIfStale(); modal.Open(scope); return Task.CompletedTask; }); }
            catch { scope.Dispose(); scope = null; throw; }
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
            if (!openButton) yield return nameof(openButton);
            if (!modal) yield return nameof(modal);
        }
    }
}
