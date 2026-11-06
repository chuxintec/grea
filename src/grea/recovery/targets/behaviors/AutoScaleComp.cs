using System;
using UnityEngine;
using UnityEngine.UI;

namespace Monkey.Recovered.Behaviors
{
    /// <summary>Native adapter for the source viewport resize behavior.</summary>
    [RequireComponent(typeof(RectTransform))]
    public sealed class AutoScaleComp : MonoBehaviour
    {
        [SerializeField] private ViewportNotchProvider viewportProvider;

        private RectTransform rectTransform;
        private float initialY;

        private void Awake()
        {
            rectTransform = GetComponent<RectTransform>();
            initialY = rectTransform.anchoredPosition.y;
        }

        private void OnEnable()
        {
            foreach (var behaviour in GetComponents<MonoBehaviour>())
                if (behaviour is IRecoveredWidgetAlignment)
                {
                    Debug.LogError("AutoScaleComp blocked: a Widget layout writer is attached to the same node.", this);
                    return;
                }
            if (GetComponent<LayoutGroup>() != null || GetComponent<ContentSizeFitter>() != null)
            {
                Debug.LogError("AutoScaleComp blocked: a native layout writer is attached to the same node.", this);
                return;
            }
            if (viewportProvider == null || !viewportProvider.TryGetSnapshot(out var visibleSize, out var notchHeight))
            {
                Debug.LogError("AutoScaleComp blocked: explicit viewport/notch metrics are missing or invalid.", this);
                return;
            }

            float inset = notchHeight > 0f ? notchHeight : 0f;
            float availableHeight = visibleSize.y - inset;
            float width = rectTransform.rect.width;
            float height = rectTransform.rect.height;
            rectTransform.anchoredPosition = new Vector2(rectTransform.anchoredPosition.x, initialY - 0.5f * inset);

            bool contained = -0.5f * inset <= 0f && visibleSize.x >= width &&
                             -0.5f * inset + availableHeight >= height;
            if (!(contained || height <= availableHeight))
            {
                if (height <= 0f)
                {
                    Debug.LogError("AutoScaleComp blocked: node height must be positive before scale division.", this);
                    return;
                }
                float scale = availableHeight / height;
                rectTransform.localScale = new Vector3(scale, scale, scale);
            }
        }
    }
}
