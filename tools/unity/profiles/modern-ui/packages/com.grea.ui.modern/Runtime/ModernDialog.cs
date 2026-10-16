using System;
using Grea.Foundation.Contracts;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;

namespace Grea.UI.Modern
{
    public sealed class ModernDialog : MonoBehaviour
    {
        public GameObject content;
        public TMP_Text title;
        public Button close;
        public EventSystem events;
        LifetimeScope visible;
        public bool IsOpen => visible!=null && visible.IsAlive;
        public void Open(LifetimeScope owner, string heading)
        {
            Close();
            if (!content || !title || !close || !events) throw new InvalidOperationException("Dialog bindings incomplete");
            var prior=events.currentSelectedGameObject;
            visible=owner.CreateChild();
            visible.Own(prior, selected=>{
                if (close) close.onClick.RemoveListener(Close);
                if (content) content.SetActive(false);
                if (events) events.SetSelectedGameObject(selected && selected.activeInHierarchy ? selected : null);
            });
            title.text=heading;content.SetActive(true);close.onClick.AddListener(Close);events.SetSelectedGameObject(close.gameObject);
        }
        public void Close() { var old=visible;visible=null;old?.Dispose(); }
        void OnDisable()=>Close();
        void OnDestroy()=>Close();
    }
}
