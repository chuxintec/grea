using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Grea.Foundation.Contracts;
using Grea.Foundation.Runtime;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Grea.UI.UGUI
{
    public enum CommandOutcome { Idle, Running, Completed, Cancelled, Failed }
    // Feedback is delegated to Unity Button's transition; this component owns requests only.
    public sealed class CommandButton : MonoBehaviour, IBindingCheck
    {
        [SerializeField] Button button;
        LifetimeScope binding;
        LifetimeScope owner, resumeOwner;
        Func<OperationStamp, Task> resumeCommand;
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
            if (owner == null || !owner.IsAlive) throw new InvalidOperationException("Command owner must be alive");
            this.command = command ?? throw new ArgumentNullException(nameof(command));
            this.owner = owner;
            if (!isActiveAndEnabled) { resumeOwner = owner; resumeCommand = command; return; }
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
            var stamp = binding.Capture("button.execute");
            var action = command;
            var events = EventSystem.current;
            bool selected = events && events.currentSelectedGameObject == button.gameObject;
            busy = true;
            LastError = null; Outcome = CommandOutcome.Running;
            button.interactable = false;
            // Selectable clears selection when disabled. Keep the existing navigation owner,
            // so an opened modal can capture it and keyboard users can continue after completion.
            // A Deselect/Select listener may invalidate this binding or select another control.
            if (!stamp.IsCurrent) return;
            if (selected && events && !events.currentSelectedGameObject && button && button.gameObject.activeInHierarchy)
                events.SetSelectedGameObject(button.gameObject);
            if (!stamp.IsCurrent) return;
            Pending = Execute(stamp, action);
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
            resumeOwner = null; resumeCommand = null; owner = null;
            var previous = binding; binding = null;
            if (busy) Outcome = CommandOutcome.Cancelled;
            try { previous?.Dispose(); } finally { command = null; busy = false; }
        }
        void OnDisable()
        {
            var previousOwner = owner; var previousCommand = command;
            Unbind();
            resumeOwner = previousOwner; resumeCommand = previousCommand;
        }
        void OnEnable()
        {
            var previousOwner = resumeOwner; var previousCommand = resumeCommand;
            resumeOwner = null; resumeCommand = null;
            if (previousOwner != null && previousOwner.IsAlive && previousCommand != null) Bind(previousOwner, previousCommand);
        }
        void OnDestroy() => Unbind();
        public IEnumerable<string> MissingBindings() { if (!button) yield return nameof(button); }
    }
}
