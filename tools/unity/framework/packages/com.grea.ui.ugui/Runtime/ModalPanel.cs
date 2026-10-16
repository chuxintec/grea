using System;
using System.Collections.Generic;
using Grea.Foundation.Contracts;
using Grea.Foundation.Runtime;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Grea.UI.UGUI
{
    public sealed class ModalPanel : MonoBehaviour, IBindingCheck
    {
        [SerializeField] GameObject content;
        [SerializeField] GameObject blocker;
        [SerializeField] Button closeButton;
        [SerializeField] Selectable firstSelected;
        [SerializeField] EventSystem events;
        [SerializeField] RectTransform contentSlot;
        [SerializeField] Text title;
        public RectTransform ContentSlot => contentSlot;
        public Text Title => title;
        public Button CloseButton => closeButton;
        public void ConfigureContentSlots(RectTransform body, Text heading)
        { if (!body) throw new ArgumentNullException(nameof(body)); contentSlot = body; title = heading; }
        LifetimeScope visible;
        public bool IsOpen => visible != null && visible.IsAlive;
        public LifetimeScope VisibleScope => IsOpen ? visible : throw new InvalidOperationException("Panel is closed");
        public void Configure(GameObject content, GameObject blocker, Button closeButton, Selectable firstSelected, EventSystem events)
        { Close(); this.content = content; this.blocker = blocker; this.closeButton = closeButton; this.firstSelected = firstSelected; this.events = events; }
        public void Open(LifetimeScope parent)
        {
            if (IsOpen) return;
            foreach (var missing in MissingBindings()) throw new InvalidOperationException("ModalPanel." + missing + " is required");
            visible = parent.CreateChild();
            var prior = events.currentSelectedGameObject;
            visible.Own(prior, p => {
                if (closeButton) closeButton.onClick.RemoveListener(Close);
                if (blocker) blocker.SetActive(false);
                if (content) content.SetActive(false);
                if (events) events.SetSelectedGameObject(p && p.activeInHierarchy ? p : null);
            });
            content.SetActive(true); blocker.SetActive(true);
            closeButton.onClick.AddListener(Close);
            events.SetSelectedGameObject(firstSelected.gameObject);
        }
        public void Close() { var old = visible; visible = null; old?.Dispose(); }
        void OnDisable() => Close();
        void OnDestroy() => Close();
        public IEnumerable<string> MissingBindings()
        {
            if (!content) yield return nameof(content);
            if (!blocker) yield return nameof(blocker);
            if (!closeButton) yield return nameof(closeButton);
            if (!firstSelected) yield return nameof(firstSelected);
            if (!events) yield return nameof(events);
        }
    }
}
