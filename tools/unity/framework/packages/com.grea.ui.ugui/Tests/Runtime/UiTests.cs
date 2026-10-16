using System;
using System.Collections;
using System.Threading.Tasks;
using Grea.Foundation.Contracts;
using Grea.Foundation.Runtime;
using Grea.UI.UGUI;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.TestTools;
using UnityEngine.UI;

namespace Grea.Tests
{
    public sealed class UiTests
    {
        GameObject root; LifetimeScope scope;
        [SetUp] public void Setup() { root = new GameObject("test-root"); scope = new LifetimeScope(); }
        [TearDown] public void Teardown() { scope.Dispose(); UnityEngine.Object.DestroyImmediate(root); }
        GameObject Child(string name, params Type[] types)
        { var go = new GameObject(name, types); go.transform.SetParent(root.transform); return go; }
        CommandButton MakeButton(out Button button)
        {
            var go = Child("button", typeof(RectTransform), typeof(Button), typeof(CommandButton));
            button = go.GetComponent<Button>(); var view = go.GetComponent<CommandButton>(); view.Configure(button); return view;
        }
        [UnityTest] public IEnumerator RebindAndRapidClickRunOnceAndLateCompletionCannotTouchNewBinding()
        {
            var view = MakeButton(out var button); int calls = 0;
            var pending = new TaskCompletionSource<bool>(); OperationStamp old = default;
            Func<OperationStamp, Task> command = stamp => { calls++; old = stamp; return pending.Task; };
            view.Bind(scope, command); view.Bind(scope, command);
            button.onClick.Invoke(); button.onClick.Invoke(); Assert.AreEqual(1, calls);
            var priorTask = view.Pending; view.Unbind(); Assert.IsFalse(old.IsCurrent);
            view.Bind(scope, _ => { calls++; return Task.CompletedTask; });
            pending.SetResult(true); yield return null;
            Assert.IsTrue(priorTask.IsCompleted); Assert.IsTrue(button.interactable);
            button.onClick.Invoke(); Assert.AreEqual(2, calls);
            view.Unbind(); button.onClick.Invoke(); Assert.AreEqual(2, calls);
        }
        [UnityTest] public IEnumerator HideShowRestoresBindingButRejectsLateCommandsAndDisposedOwner()
        {
            var view = MakeButton(out var button); int calls = 0;
            var gate = new TaskCompletionSource<bool>(); OperationStamp old = default;
            view.Bind(scope, stamp => { calls++; old = stamp; return calls == 1 ? gate.Task : Task.CompletedTask; });
            button.onClick.Invoke(); view.gameObject.SetActive(false); Assert.IsFalse(old.IsCurrent);
            button.onClick.Invoke(); Assert.AreEqual(1, calls);
            view.gameObject.SetActive(true); button.onClick.Invoke(); Assert.AreEqual(2, calls);
            gate.SetResult(true); yield return null; Assert.IsTrue(button.interactable);
            view.gameObject.SetActive(false); scope.Dispose(); view.gameObject.SetActive(true);
            button.onClick.Invoke(); Assert.AreEqual(2, calls);
        }
        [UnityTest] public IEnumerator CommandFailureIsObservedAndButtonRecovers()
        {
            var view = MakeButton(out var button);
            view.Bind(scope, _ => throw new InvalidOperationException("synthetic failure")); button.onClick.Invoke(); yield return null;
            Assert.IsInstanceOf<InvalidOperationException>(view.LastError); Assert.IsTrue(button.interactable);
            Assert.AreEqual(CommandOutcome.Failed, view.Outcome);
        }
        [UnityTest] public IEnumerator ParentExitCancelsPendingCommandAndRejectsLateUpdate()
        {
            var view = MakeButton(out var button); var gate = new TaskCompletionSource<bool>(); int updates = 0;
            view.Bind(scope, async stamp => { await gate.Task; stamp.ThrowIfStale(); updates++; });
            button.onClick.Invoke(); scope.Dispose();
            Assert.AreEqual(CommandOutcome.Cancelled, view.Outcome); gate.SetResult(true); yield return null;
            Assert.AreEqual(0, updates); Assert.AreEqual(CommandOutcome.Cancelled, view.Outcome);
        }
        [Test] public void ScreenHostReplacesAndClosesActivePanel()
        {
            var events = Child("events", typeof(EventSystem)).GetComponent<EventSystem>();
            var a = Child("a", typeof(ModalPanel)).GetComponent<ModalPanel>();
            var b = Child("b", typeof(ModalPanel)).GetComponent<ModalPanel>();
            foreach (var panel in new[] { a, b })
            {
                var close = Child("close", typeof(RectTransform), typeof(Button)).GetComponent<Button>();
                panel.Configure(Child("content"), Child("blocker"), close, close, events);
            }
            var host = Child("host", typeof(ScreenHost)).GetComponent<ScreenHost>();
            host.Show(a, scope); host.Show(a, scope); Assert.AreEqual(1, scope.OwnedCount);
            host.Show(b, scope); Assert.IsFalse(a.IsOpen); Assert.IsTrue(b.IsOpen);
            host.Close(); host.Close(); Assert.IsFalse(b.IsOpen); Assert.AreEqual(0, scope.OwnedCount);
        }
        [Test] public void MissingBindingFailsBeforeListening()
        {
            var view = Child("unbound", typeof(CommandButton)).GetComponent<CommandButton>();
            Assert.Throws<InvalidOperationException>(() => view.Bind(scope, _ => Task.CompletedTask));
        }
        [UnityTest] public IEnumerator ModalReopensAndRestoresFocusWithoutOldTasksOrListeners()
        {
            var events = Child("events", typeof(EventSystem)).GetComponent<EventSystem>();
            var prior = Child("prior", typeof(RectTransform), typeof(Button)); events.SetSelectedGameObject(prior);
            var content = Child("content"); var blocker = Child("blocker");
            var close = Child("close", typeof(RectTransform), typeof(Button)).GetComponent<Button>();
            var panel = Child("panel", typeof(ModalPanel)).GetComponent<ModalPanel>();
            panel.Configure(content, blocker, close, close, events);
            for (int i = 0; i < 3; i++)
            {
                panel.Open(scope); var stamp = panel.VisibleScope.Capture("load"); panel.Open(scope);
                Assert.AreSame(close.gameObject, events.currentSelectedGameObject); Assert.IsTrue(blocker.activeSelf);
                close.onClick.Invoke(); Assert.IsFalse(panel.IsOpen); Assert.IsFalse(stamp.IsCurrent);
                Assert.IsFalse(blocker.activeSelf); Assert.AreSame(prior, events.currentSelectedGameObject);
                Assert.AreEqual(0, scope.OwnedCount);
            }
            panel.Open(scope); scope.Dispose(); Assert.IsFalse(panel.IsOpen); Assert.IsFalse(content.activeSelf);
            yield return null;
        }
        [Test] public void PanelInvalidBindingAndHostInvalidTargetAreExplicit()
        {
            var panel = Child("panel", typeof(ModalPanel)).GetComponent<ModalPanel>();
            Assert.Throws<InvalidOperationException>(() => panel.Open(scope));
            var host = Child("host", typeof(ScreenHost)).GetComponent<ScreenHost>();
            Assert.Throws<ArgumentNullException>(() => host.Show(null, scope));
        }
        [UnityTest] public IEnumerator DisabledViewStopsRequestsAndAudioIsReleasedOnScopeExit()
        {
            var view = MakeButton(out var button); int calls = 0;
            view.Bind(scope, _ => { calls++; return Task.CompletedTask; });
            view.gameObject.SetActive(false); button.onClick.Invoke(); Assert.AreEqual(0, calls);
            var clip = AudioClip.Create("synthetic", 4410, 1, 44100, false);
            try
            {
                var audio = new AudioPlayer(root.transform); var handle = audio.Play(clip, scope, true); var source = handle.Value;
                Assert.AreSame(clip, source.clip); scope.Dispose(); Assert.IsTrue(handle.IsDisposed);
                Assert.IsNull(source.clip); Assert.IsFalse(source.isPlaying); yield return null; Assert.IsFalse(source);
                Assert.Throws<MissingReferenceException>(() => audio.Play(null, new LifetimeScope()));
            }
            finally { UnityEngine.Object.DestroyImmediate(clip); }
        }
        [UnityTest] public IEnumerator HostCanLeaveCommandOwnershipWithTheConsumer()
        {
            var go=Child("host",typeof(RectTransform)); go.SetActive(false);
            var host=go.AddComponent<UIHost>(); host.bindOpenButton=false;
            host.canvas=go.AddComponent<Canvas>();
            host.pageLayer=Child("pages",typeof(RectTransform)).GetComponent<RectTransform>();
            host.modalLayer=Child("modals",typeof(RectTransform)).GetComponent<RectTransform>();
            host.toastLayer=Child("toasts",typeof(RectTransform)).GetComponent<RectTransform>();
            host.events=Child("events",typeof(EventSystem)).GetComponent<EventSystem>();
            var command=MakeButton(out var button); int count=0;
            command.Bind(scope,stamp=>{count++;return Task.CompletedTask;});
            host.openButton=command; host.Initialize(); go.SetActive(true); yield return null;
            button.onClick.Invoke(); Assert.AreEqual(1,count);
            go.SetActive(false); go.SetActive(true); yield return null;
            button.onClick.Invoke(); Assert.AreEqual(2,count);
        }
        [UnityTest] public IEnumerator CommandPreservesNavigationFocusWithoutStealingAnotherSelection()
        {
            var events=Child("events",typeof(EventSystem)).GetComponent<EventSystem>();
            var previous=EventSystem.current; EventSystem.current=events;
            try
            {
                var command=MakeButton(out var button); var other=Child("other",typeof(RectTransform),typeof(Button));
                command.Bind(scope,stamp=>Task.CompletedTask);
                events.SetSelectedGameObject(button.gameObject); button.onClick.Invoke();
                Assert.AreEqual(button.gameObject,events.currentSelectedGameObject,"Busy tint must not lose keyboard navigation");
                var wait=new TaskCompletionSource<bool>();
                command.Bind(scope,stamp=>{ events.SetSelectedGameObject(other); return wait.Task; });
                events.SetSelectedGameObject(button.gameObject); button.onClick.Invoke();
                Assert.AreEqual(other,events.currentSelectedGameObject);
                wait.SetResult(true); yield return null;
                Assert.AreEqual(other,events.currentSelectedGameObject,"Completion must not steal a modal/new focus");
            }
            finally { EventSystem.current=previous; }
        }
    }
}
