using System.Collections;
using Grea.UI.UGUI;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using UnityEngine.UI;
using UnityEngine.SceneManagement;
using UnityEngine.EventSystems;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Grea.Generation.Tests
{
    public sealed class GeneratedPrefabTests
    {
        [UnityTearDown] public IEnumerator CleanupScenes()
        {
            var bootstrap = SceneManager.GetSceneByPath("Assets/Game/Scenes/Bootstrap.unity");
            var entry = SceneManager.GetSceneByPath("Assets/Game/Scenes/Entry.unity");
            if (bootstrap.isLoaded || entry.isLoaded)
            {
                var empty = SceneManager.CreateScene("M3TestCleanup"); SceneManager.SetActiveScene(empty);
                if (entry.isLoaded) yield return SceneManager.UnloadSceneAsync(entry);
                if (bootstrap.isLoaded) yield return SceneManager.UnloadSceneAsync(bootstrap);
            }
        }
        [UnityTest] public IEnumerator BootstrapLoadsEntryAndOwnsExactlyOneEventSystemOnReentry()
        {
            for (int pass = 0; pass < 2; pass++)
            {
                yield return SceneManager.LoadSceneAsync("Assets/Game/Scenes/Bootstrap.unity", LoadSceneMode.Single);
                for (int frame = 0; frame < 120 && !SceneManager.GetSceneByPath("Assets/Game/Scenes/Entry.unity").isLoaded; frame++) yield return null;
                Assert.IsTrue(SceneManager.GetSceneByPath("Assets/Game/Scenes/Entry.unity").isLoaded);
                Assert.AreEqual(1, Object.FindObjectsByType<EventSystem>(FindObjectsSortMode.None).Length);
                Assert.AreEqual(1, Object.FindObjectsByType<UIHost>(FindObjectsSortMode.None).Length);
            }
        }
        [UnityTest] public IEnumerator GeneratedHostOpensClosesReopensAndCleansUp()
        {
#if UNITY_EDITOR
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/GreaGenerated/UIHost.prefab");
            Assert.IsNotNull(prefab);
            var instance = Object.Instantiate(prefab);
            try
            {
                yield return null;
                var host = instance.GetComponent<UIHost>();
                for (int i = 0; i < 3; i++)
                {
                    host.openButton.GetComponent<Button>().onClick.Invoke(); Assert.IsTrue(host.modal.IsOpen);
                    host.modal.Close(); Assert.IsFalse(host.modal.IsOpen);
                }
                host.openButton.GetComponent<Button>().onClick.Invoke(); instance.SetActive(false); Assert.IsFalse(host.modal.IsOpen);
                instance.SetActive(true); host.openButton.GetComponent<Button>().onClick.Invoke(); Assert.IsTrue(host.modal.IsOpen);
            }
            finally { Object.Destroy(instance); }
            yield return null;
#else
            Assert.Ignore("Editor prefab asset test only"); yield break;
#endif
        }
    }
}
