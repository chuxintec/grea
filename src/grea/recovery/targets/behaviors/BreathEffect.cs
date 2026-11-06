using System.Collections;
using UnityEngine;

namespace Monkey.Recovered.Behaviors
{
    /// <summary>Native lowering of the frozen Cocos BreathEffect source module.</summary>
    [DisallowMultipleComponent]
    public sealed class BreathEffect : MonoBehaviour
    {
        [SerializeField] public float delay = 0.3f;
        [SerializeField] public float tweenTime = 0.7f;
        [SerializeField] public float offset = 0.1f;

        private float startValue;
        private float endValue;
        private bool running = true;
        private Coroutine cycle;

        public bool Running
        {
            get => running;
            set
            {
                if (running == value) return;
                running = value;
                PlayEffect();
            }
        }

        private void Awake()
        {
            startValue = transform.localScale.x;
            endValue = startValue + offset;
        }

        private void OnEnable() => PlayEffect();

        private void OnDisable()
        {
            // Keep cancellation scoped to the tween owned by this adapter.
            // Other components may run unrelated gameplay/save/network work.
            if (cycle != null) StopCoroutine(cycle);
            cycle = null;
        }

        private void PlayEffect()
        {
            if (!isActiveAndEnabled) return;
            if (cycle != null) StopCoroutine(cycle);
            cycle = null;
            if (running) cycle = StartCoroutine(RunCycle());
        }

        private IEnumerator RunCycle()
        {
            while (running)
            {
                yield return TweenScale(transform.localScale.x, endValue, tweenTime);
                yield return TweenScale(endValue, startValue, tweenTime);
                if (delay > 0f) yield return new WaitForSeconds(delay);
                else yield return null;
            }
            cycle = null;
        }

        private IEnumerator TweenScale(float from, float to, float duration)
        {
            if (duration <= 0f)
            {
                transform.localScale = Vector3.one * to;
                yield break;
            }
            float elapsed = 0f;
            yield return null;
            while (elapsed < duration)
            {
                elapsed += Time.deltaTime;
                float t = Mathf.Clamp01(elapsed / duration);
                float eased = t < 0.5f ? 2f * t * t : 1f - Mathf.Pow(-2f * t + 2f, 2f) * 0.5f;
                float scale = Mathf.LerpUnclamped(from, to, eased);
                transform.localScale = Vector3.one * scale;
                yield return null;
            }
            transform.localScale = Vector3.one * to;
        }
    }
}
