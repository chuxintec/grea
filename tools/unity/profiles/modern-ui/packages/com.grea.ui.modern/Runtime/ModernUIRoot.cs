using System;
using Grea.Foundation.Contracts;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;

namespace Grea.UI.Modern
{
    // Native scene/prefab bindings. This host owns presentation lifetime, never game rules.
    public sealed class ModernUIRoot : MonoBehaviour
    {
        public Canvas canvas;
        public RectTransform pages, modals, toasts;
        public EventSystem events;
        public InputSystemUIInputModule input;
        public ModernDialog dialog;
        public void Validate()
        {
            if (!canvas || !pages || !modals || !toasts || !events || !input || !dialog)
                throw new InvalidOperationException("Modern UI bindings are incomplete");
            if (events.GetComponents<BaseInputModule>().Length!=1 || !input.actionsAsset || !input.point || !input.leftClick || !input.move || !input.submit || !input.cancel)
                throw new InvalidOperationException("Exactly one configured Input System module required");
        }
        void Awake() => Validate();
        void OnDisable() { if (dialog) dialog.Close(); }
    }
}
