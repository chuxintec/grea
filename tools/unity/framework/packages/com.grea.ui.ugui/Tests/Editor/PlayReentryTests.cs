using System.Collections;
using System.Threading.Tasks;
using Grea.Foundation.Contracts;
using Grea.UI.UGUI;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using UnityEngine.TestTools;
using UnityEngine.UI;

namespace Grea.Tests
{
    public sealed class PlayReentryTests
    {
        bool priorEnabled;
        EnterPlayModeOptions priorOptions;
        LifetimeScope owner;
        GameObject root;
        [SetUp] public void Setup()
        {
            priorEnabled = EditorSettings.enterPlayModeOptionsEnabled;
            priorOptions = EditorSettings.enterPlayModeOptions;
            EditorSettings.enterPlayModeOptionsEnabled = true;
            EditorSettings.enterPlayModeOptions = EnterPlayModeOptions.DisableDomainReload | EnterPlayModeOptions.DisableSceneReload;
        }
        [TearDown] public void Teardown()
        {
            owner?.Dispose();
            if (root) Object.DestroyImmediate(root);
            EditorSettings.enterPlayModeOptions = priorOptions;
            EditorSettings.enterPlayModeOptionsEnabled = priorEnabled;
        }
        [UnityTest] public IEnumerator TwoRealPlayEntriesUnbindOnExitWithoutDomainOrSceneReload()
        {
            for (int i = 0; i < 2; i++)
            {
                yield return new EnterPlayMode(false);
                owner = new LifetimeScope();
                root = new GameObject("reentry-test", typeof(RectTransform), typeof(Button), typeof(CommandButton));
                var button = root.GetComponent<Button>(); var view = root.GetComponent<CommandButton>();
                view.Configure(button); int calls = 0;
                view.Bind(owner, _ => { calls++; return Task.CompletedTask; });
                button.onClick.Invoke(); Assert.AreEqual(1, calls); Assert.AreEqual(1, owner.OwnedCount);
                yield return new ExitPlayMode();
                Assert.AreEqual(0, owner.OwnedCount, "OnDisable/OnDestroy must detach the binding on real Play exit");
                owner.Dispose();
            }
        }
    }
}
