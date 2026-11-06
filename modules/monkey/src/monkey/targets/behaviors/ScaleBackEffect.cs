using System;
using System.Collections;
using System.Threading.Tasks;
using UnityEngine;

namespace Monkey.Recovered.Behaviors
{
    /// <summary>Native adapter for the frozen ScaleBackEffect/BaseEffect chain.</summary>
    [DisallowMultipleComponent]
    public sealed class ScaleBackEffect : BaseEffect
    {
        private enum Ease { BackOut, BackIn }
        [SerializeField] public bool tweenHide = false;
        [SerializeField] public float scaleFrom = 0.7f;

        protected override void Awake() => base.Awake();

        public override async Task Show(object data = null)
        {
            await base.Show(data);
            transform.localScale = Vector3.one * scaleFrom;
            StartOwnedTween(ScaleTo(1f, Ease.BackOut));
            await Task.Delay(TimeSpan.FromMilliseconds(Math.Max(0f, 1000f * tweenTime)));
        }

        public override async Task Hide(object data = null)
        {
            if (!tweenHide)
            {
                transform.localScale = Vector3.zero;
                return;
            }
            StartOwnedTween(ScaleTo(scaleFrom, Ease.BackIn));
            await Task.Delay(TimeSpan.FromMilliseconds(Math.Max(0f, 1000f * tweenTime)));
            transform.localScale = Vector3.zero;
        }

        private IEnumerator ScaleTo(float target, Ease easing)
        {
            float initial = transform.localScale.x;
            if (tweenTime <= 0f)
            {
                transform.localScale = Vector3.one * target;
                yield break;
            }
            float elapsed = 0f;
            yield return null;
            while (elapsed < tweenTime)
            {
                elapsed += Time.deltaTime;
                float t = Mathf.Clamp01(elapsed / tweenTime);
                float c1 = 1.70158f;
                float eased = easing == Ease.BackOut
                    ? 1f + (c1 + 1f) * Mathf.Pow(t - 1f, 3f) + c1 * Mathf.Pow(t - 1f, 2f)
                    : (c1 + 1f) * t * t * t - c1 * t * t;
                float scale = Mathf.LerpUnclamped(initial, target, eased);
                transform.localScale = Vector3.one * scale;
                yield return null;
            }
            transform.localScale = Vector3.one * target;
        }
    }
}
