using System;
using System.Collections;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Grea.Foundation.Contracts;
using Grea.Foundation.Runtime;
using Grea.UI.UGUI;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.TestTools;
using UnityEngine.UI;
using Object = UnityEngine.Object;

namespace Grea.Tests
{
    // Interface/reflection boundary allows a genuine failing test before the new component exists.
    public sealed class ButtonPressFeedbackTests
    {
        GameObject root;
        Button button;
        Transform visual;
        MonoBehaviour feedback;
        float previousTimeScale;
        readonly Vector3 basis = new Vector3(2, 3, 4);

        [SetUp] public void Setup()
        {
            previousTimeScale = Time.timeScale;
            root = new GameObject("press-test", typeof(RectTransform), typeof(Button));
            button = root.GetComponent<Button>();
            visual = new GameObject("visual").transform;
            visual.SetParent(root.transform, false); visual.localScale = basis;
            var type = typeof(CommandButton).Assembly.GetType("Grea.UI.UGUI.ButtonPressFeedback");
            Assert.That(type, Is.Not.Null, "A finite, explicitly bound press feedback component is missing.");
            feedback = (MonoBehaviour)root.AddComponent(type);
            Configure(button, visual, .8f, 0);
        }
        [TearDown] public void Teardown()
        {
            Time.timeScale = previousTimeScale;
            if (root) Object.DestroyImmediate(root);
        }
        void Configure(Button control, Transform target, float scale, float seconds)
        { feedback.GetType().GetMethod("Configure").Invoke(feedback, new object[] { control, target, scale, seconds }); }
        void Cancel() => feedback.GetType().GetMethod("Cancel").Invoke(feedback, null);
        PointerEventData Pointer(int id = -1, PointerEventData.InputButton which = PointerEventData.InputButton.Left)
            => new PointerEventData(null) { pointerId = id, button = which };
        void Down(int id = -1) => ((IPointerDownHandler)feedback).OnPointerDown(Pointer(id));
        void Up(int id = -1) => ((IPointerUpHandler)feedback).OnPointerUp(Pointer(id));
        void AssertScale(Vector3 wanted) => Assert.That(Vector3.Distance(visual.localScale, wanted), Is.LessThan(.0001f));
        Vector3 Pressed(Vector3 value) => new Vector3(value.x * .8f, value.y * .8f, value.z);

        [UnityTest] public IEnumerator SameFrameEdgesRestoreAndOnlyUnityButtonDispatches()
        {
            int clicks = 0; button.onClick.AddListener(() => clicks++);
            Down(); Up(); ((IPointerClickHandler)button).OnPointerClick(Pointer());
            yield return null; yield return null;
            AssertScale(basis); Assert.AreEqual(1,clicks);
            Down(); root.SetActive(false); root.SetActive(true);
            if (feedback is IPointerEnterHandler enter) enter.OnPointerEnter(Pointer());
            Up(); yield return null; AssertScale(basis); Assert.AreEqual(1,clicks);
        }
        [UnityTest] public IEnumerator DownAndReleaseRestoreAuthoredScale()
        {
            Down(); yield return null; yield return null;
            AssertScale(Pressed(basis));
            Up(); yield return null; yield return null;
            AssertScale(basis);
            Down(); yield return null; yield return null;
            Cancel(); Cancel(); AssertScale(basis);
        }
        [UnityTest] public IEnumerator ExitAndDragCancelUntilANewPress()
        {
            Down(); yield return null; yield return null;
            ((IPointerExitHandler)feedback).OnPointerExit(Pointer());
            AssertScale(basis);
            if (feedback is IPointerEnterHandler enter) enter.OnPointerEnter(Pointer());
            yield return null; AssertScale(basis);
            Down(); yield return null; yield return null;
            ((IBeginDragHandler)feedback).OnBeginDrag(Pointer());
            yield return null; AssertScale(basis);
        }
        [UnityTest] public IEnumerator AnotherPointerCannotStealOrReleaseThePress()
        {
            Down(7); yield return null; yield return null;
            Down(8); Up(8); yield return null; AssertScale(Pressed(basis));
            ((IPointerExitHandler)feedback).OnPointerExit(Pointer(8));
            ((IBeginDragHandler)feedback).OnBeginDrag(Pointer(8));
            AssertScale(Pressed(basis));
            Up(7); yield return null; yield return null; AssertScale(basis);
        }
        [UnityTest] public IEnumerator RightClickAndDisabledButtonNeverPress()
        {
            ((IPointerDownHandler)feedback).OnPointerDown(Pointer(-1, PointerEventData.InputButton.Right));
            yield return null; AssertScale(basis);
            button.interactable = false; Down(); yield return null; AssertScale(basis);
            button.interactable = true; Down(); yield return null; yield return null;
            button.enabled = false; yield return null; yield return null; AssertScale(basis);
        }
        [UnityTest] public IEnumerator FocusLossDisableAndDestroyRestoreWithoutDispatchingClicks()
        {
            int calls = 0; button.onClick.AddListener(() => calls++);
            Down(); yield return null; yield return null;
            feedback.SendMessage("OnApplicationFocus", false, SendMessageOptions.DontRequireReceiver);
            AssertScale(basis);
            Down(); yield return null; yield return null;
            feedback.enabled = false; AssertScale(basis);
            feedback.enabled = true; Down(); yield return null; yield return null;
            Object.Destroy(feedback); yield return null; yield return null;
            AssertScale(basis); Assert.AreEqual(0, calls);
        }
        [UnityTest] public IEnumerator ExternalAuthoredScaleChangeSurvivesCancellation()
        {
            Down(); yield return null; yield return null;
            var changed = new Vector3(4, 5, 2); visual.localScale = changed;
            Cancel(); AssertScale(changed);
            Down(); yield return null; yield return null; AssertScale(Pressed(changed));
            visual.localScale = basis; yield return null; yield return null;
            AssertScale(Pressed(basis)); Cancel(); AssertScale(basis);
        }
        [UnityTest] public IEnumerator FeedbackUsesUnscaledTimeWhileGameplayIsPaused()
        {
            Configure(button, visual, .8f, .03f); Time.timeScale = 0;
            Down(); yield return new WaitForSecondsRealtime(.08f); AssertScale(Pressed(basis));
            Up(); yield return new WaitForSecondsRealtime(.08f); AssertScale(basis);
        }
        [UnityTest] public IEnumerator ReconfigureRestoresOldVisualAndOwnsOnlyTheNewTarget()
        {
            Down(); yield return null; yield return null;
            var target = new GameObject("replacement").transform;
            target.SetParent(root.transform, false); target.localScale = Vector3.one;
            Configure(button, target, .8f, 0); AssertScale(basis);
            Down(); yield return null; yield return null;
            Assert.That(Vector3.Distance(target.localScale, new Vector3(.8f, .8f, 1)), Is.LessThan(.0001f));
            Cancel(); Assert.AreEqual(Vector3.one, target.localScale); AssertScale(basis);
        }
        [UnityTest] public IEnumerator CommandBusyCancellationDoesNotDuplicateTheBusinessRequest()
        {
            var command = root.AddComponent<CommandButton>(); command.Configure(button);
            using (var scope = new LifetimeScope())
            {
                var gate = new TaskCompletionSource<bool>(); int calls = 0;
                command.Bind(scope, _ => { calls++; return gate.Task; });
                Down(); yield return null; yield return null;
                button.onClick.Invoke(); button.onClick.Invoke();
                yield return null; yield return null;
                AssertScale(basis); Assert.AreEqual(1, calls);
                gate.SetResult(true); yield return null;
                Assert.IsTrue(button.interactable);
                Assert.AreEqual(CommandOutcome.Completed, command.Outcome);
            }
        }
        [Test] public void MissingReferencesAndInvalidNumbersAreObservable()
        {
            Assert.That(ConfigureError(null, visual, .8f, 0), Is.InstanceOf<ArgumentNullException>());
            Assert.That(ConfigureError(button, null, .8f, 0), Is.InstanceOf<ArgumentNullException>());
            foreach (float scale in new[] { 0f, -1f, 2f, float.NaN, float.PositiveInfinity })
                Assert.That(ConfigureError(button, visual, scale, 0), Is.InstanceOf<ArgumentOutOfRangeException>());
            foreach (float seconds in new[] { -1f, float.NaN, float.PositiveInfinity })
                Assert.That(ConfigureError(button, visual, .8f, seconds), Is.InstanceOf<ArgumentOutOfRangeException>());
            Assert.IsEmpty(((IBindingCheck)feedback).MissingBindings().ToArray());
        }
        Exception ConfigureError(Button control, Transform target, float scale, float seconds)
        {
            try { Configure(control, target, scale, seconds); return null; }
            catch (TargetInvocationException error) { return error.InnerException; }
        }
    }
}
