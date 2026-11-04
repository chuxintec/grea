using UnityEngine;

namespace Monkey.Recovered.Behaviors
{
    /// <summary>
    /// Supplies viewport dimensions and a configured notch/status inset in
    /// the same local UI units used by the bound AutoScaleComp RectTransform.
    /// </summary>
    public sealed class ViewportNotchProvider : MonoBehaviour
    {
        [SerializeField] private RectTransform visibleRoot;
        [SerializeField] private float statusNotchHeight = -1f;

        public bool TryGetSnapshot(out Vector2 visibleSize, out float notchHeight)
        {
            visibleSize = default;
            notchHeight = statusNotchHeight;
            if (visibleRoot == null || float.IsNaN(statusNotchHeight) || float.IsInfinity(statusNotchHeight) || statusNotchHeight < 0f)
                return false;
            visibleSize = visibleRoot.rect.size;
            return !float.IsNaN(visibleSize.x) && !float.IsInfinity(visibleSize.x) &&
                   !float.IsNaN(visibleSize.y) && !float.IsInfinity(visibleSize.y) &&
                   visibleSize.x > 0f && visibleSize.y > 0f;
        }
    }
}
