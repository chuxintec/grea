using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Grea.Foundation.Contracts;
using Grea.Foundation.Runtime;
using UnityEngine;
using UnityEngine.UI;

namespace Grea.UI.UGUI
{
    public enum CommandOutcome { Idle, Running, Completed, Cancelled, Failed }
    // Feedback is delegated to Unity Button's transition; this component owns requests only.
    public sealed class CommandButton : MonoBehaviour, IBindingCheck
    {
        [SerializeField] Button button;
        LifetimeScope binding;
        Func<OperationStamp, Task> command;
        bool busy;
        bool originalInteractable;
        public Task Pending { get; private set; } = Task.CompletedTask;
        public Exception LastError { get; private set; }
        public CommandOutcome Outcome { get; private set; }
        public void Configure(Button target) { Unbind(); button = target; }
        public void Bind(LifetimeScope owner, Func<OperationStamp, Task> command)
        {
            Unbind();
            if (!button) throw new InvalidOperationException("CommandButton.button is required");
            this.command = command ?? throw new ArgumentNullException(nameof(command));
            binding = owner.CreateChild();
            originalInteractable = button.interactable;
            button.onClick.AddListener(Click);
            var boundButton = button;
            var session = binding;
            binding.Own(boundButton, b => {
                if (b) { b.onClick.RemoveListener(Click); b.interactable = originalInteractable; }
                if (binding == session)
                {
                    binding = null; command = null;
                    if (busy) Outcome = CommandOutcome.Cancelled;
                    busy = false;
                }
            });
            LastError = null;
            Outcome = CommandOutcome.Idle;
        }
        void Click()
        {
            if (binding == null || !binding.IsAlive || busy || !button || !button.IsInteractable()) return;
            busy = true; button.interactable = false;
            LastError = null; Outcome = CommandOutcome.Running;
            var stamp = binding.Capture("button.execute");
            Pending = Execute(stamp, command);
        }
        async Task Execute(OperationStamp stamp, Func<OperationStamp, Task> action)
        {
            try { await action(stamp); stamp.ThrowIfStale(); Outcome = CommandOutcome.Completed; }
            catch (OperationCanceledException) { if (stamp.IsCurrent) Outcome = CommandOutcome.Cancelled; }
            catch (Exception e) { if (stamp.IsCurrent) { LastError = e; Outcome = CommandOutcome.Failed; } }
            finally
            {
                if (stamp.IsCurrent && this && button) { busy = false; button.interactable = originalInteractable; }
            }
        }
        public void Unbind()
        {
            var previous = binding; binding = null;
            if (busy) Outcome = CommandOutcome.Cancelled;
            try { previous?.Dispose(); } finally { command = null; busy = false; }
        }
        void OnDisable() => Unbind();
        void OnDestroy() => Unbind();
        public IEnumerable<string> MissingBindings() { if (!button) yield return nameof(button); }
    }
}
