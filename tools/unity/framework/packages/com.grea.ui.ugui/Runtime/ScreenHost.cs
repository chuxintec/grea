using System;
using Grea.Foundation.Contracts;
using UnityEngine;

namespace Grea.UI.UGUI
{
    // One visible panel per host. Navigation is explicit replacement, never a hidden queue.
    public sealed class ScreenHost : MonoBehaviour
    {
        ModalPanel active;
        public void Show(ModalPanel panel, LifetimeScope owner)
        {
            if (!panel) throw new ArgumentNullException(nameof(panel));
            if (active == panel && panel.IsOpen) return;
            Close(); panel.Open(owner); active = panel;
        }
        public void Close() { if (active) active.Close(); active = null; }
        void OnDisable() => Close();
        void OnDestroy() => Close();
    }
}
