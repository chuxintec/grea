using System;
using System.Collections;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;

namespace Monkey.Recovered.Behaviors
{
    // Optional bridge for projects that have an exact native equivalent of
    // Cocos Widget.updateAlignment. Its presence must come from source binding.
    public interface IRecoveredWidgetAlignment
    {
        void UpdateAlignment();
    }

    public abstract class BaseEffect : MonoBehaviour
    {
        [SerializeField] public float delay = 0f;
        [SerializeField] public float tweenTime = 0.3f;

        protected float initScale;
        private readonly List<OwnedAction> ownedActions = new List<OwnedAction>();

        private sealed class OwnedAction
        {
            public Coroutine Coroutine;
        }

        protected virtual void Awake()
        {
            initScale = transform.localScale.x;
            ResetEffect();
            foreach (var behaviour in GetComponents<MonoBehaviour>())
                if (behaviour is IRecoveredWidgetAlignment alignment)
                    alignment.UpdateAlignment();
        }

        protected void StartOwnedTween(IEnumerator routine)
        {
            var owner = new OwnedAction();
            ownedActions.Add(owner);
            owner.Coroutine = StartCoroutine(TrackOwnedAction(routine, owner));
        }

        protected virtual void StopOwnedActions()
        {
            foreach (var owner in ownedActions)
                if (owner.Coroutine != null) StopCoroutine(owner.Coroutine);
            ownedActions.Clear();
        }

        private IEnumerator TrackOwnedAction(IEnumerator routine, OwnedAction owner)
        {
            yield return routine;
            ownedActions.Remove(owner);
        }

        protected virtual void ResetEffect() => StopOwnedActions();

        public virtual Task Show(object data = null)
        {
            ResetEffect();
            return Task.CompletedTask;
        }

        public virtual Task Hide(object data = null) => Task.CompletedTask;

        public async Task Excute(Func<Task> action)
        {
            if (gameObject.activeInHierarchy && action != null)
                await action();
        }
    }
}
