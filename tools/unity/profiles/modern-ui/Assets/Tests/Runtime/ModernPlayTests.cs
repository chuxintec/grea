#if UNITY_EDITOR
using System;
using System.Collections;
using System.IO;
using System.Linq;
using Grea.Foundation.Runtime;
using Grea.Editor;
using ModernSample.Bootstrap;
using ModernSample.Domain;
using ModernSample.Gameplay;
using ModernSample.Presentation;
using ModernSample.Services;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace ModernSample.Tests
{
    public sealed class ModernPlayTests : InputTestFixture
    {
        [UnityTest] public IEnumerator NativeInputTmpReentryAndEditableConfig()
        {
            // The test owns a new scene and explicit QA storage.
            var scene=SceneManager.CreateScene("isolated-modern-test");SceneManager.SetActiveScene(scene);
            Assert.IsTrue(Application.isPlaying);
            var prefab=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Game/Content/sample_ui.prefab");
            Assert.IsNotNull(prefab);var root=UnityEngine.Object.Instantiate(prefab);var view=root.GetComponent<SampleView>();Assert.IsNotNull(view);Debug.Log("MODERN_TEST instantiated");
            var folder=Path.Combine(Path.GetTempPath(),"grea-modern-"+Guid.NewGuid().ToString("N"));
            Debug.Log("MODERN_TEST input settings="+(InputSystem.settings!=null));
            InputSystem.settings.backgroundBehavior=InputSettings.BackgroundBehavior.IgnoreFocus; // Virtual-device test only; not OS focus acceptance.
            var mouse=InputSystem.AddDevice<Mouse>();
            Debug.Log("MODERN_TEST mouse added");
            try
            {
                var config=AssetDatabase.LoadAssetAtPath<SampleConfig>("Assets/Game/Content/sample_config.asset");
                // Values are read from an editable native SO. A changed value reaches the actual consumer.
                Assert.IsNotNull(config);Debug.Log("MODERN_TEST config loaded");
                var copy=UnityEngine.Object.Instantiate(config);copy.enemyHealth=231;copy.damage=19;
                var session=new Session(new ProgressStore(new FileSaveStore(folder,"player","qa",true)),copy.kind,copy.enemyHealth,copy.damage);
                Debug.Log("MODERN_TEST session ready");view.Initialize(session);yield return null;yield return null;
                Assert.AreEqual(231,session.EnemyHealth);Assert.Greater(view.status.textInfo.characterCount,0);
                Assert.Greater(view.status.mesh.vertexCount,0);Assert.IsTrue(view.status.font.HasCharacter(copy.kind==GameKind.Combat?'数':'益'),"Rendered Chinese glyph must be present");
                var before=PresentationSampler.Sample(root,"cold_open");
                IEnumerator Click(UnityEngine.UI.Button button)
                {
                    var point=RectTransformUtility.WorldToScreenPoint(null,button.transform.position);
                    Set(mouse.position,point);yield return null;
                    var hits=new System.Collections.Generic.List<UnityEngine.EventSystems.RaycastResult>();
                    view.root.events.RaycastAll(new UnityEngine.EventSystems.PointerEventData(view.root.events){position=point},hits);
                    Assert.IsTrue(hits.Count>0 && hits[0].gameObject==button.gameObject,"Actual graphic raycast must hit the button");
                    Press(mouse.leftButton);yield return null;
                    Release(mouse.leftButton);yield return null;yield return null;
                }
                int clicked=0,performed=0;view.action.onClick.AddListener(()=>clicked++);
                view.root.input.leftClick.action.performed+=_=>performed++;
                yield return Click(view.action);
                Assert.AreEqual(1,session.Progress.Actions,$"clicks={clicked}, inputPerformed={performed}, enabled={view.root.input.leftClick.action.enabled}, module={view.root.events.currentInputModule}, outcome={view.action.GetComponent<Grea.UI.UGUI.CommandButton>().Outcome}, error={view.action.GetComponent<Grea.UI.UGUI.CommandButton>().LastError}");
                yield return Click(view.menu);Assert.IsTrue(view.root.dialog.IsOpen);
                yield return Click(view.root.dialog.close);Assert.IsFalse(view.root.dialog.IsOpen);
                var closed=PresentationSampler.Sample(root,"closed");
                yield return Click(view.menu);Assert.IsTrue(view.root.dialog.IsOpen);
                var reopened=PresentationSampler.Sample(root,"reopen");
                File.WriteAllText("modern-observation.json",JsonUtility.ToJson(new PresentationSampler.Capture {candidate_sha256=ProjectGenerator.Hash("prepared-inputs.json"),run_instance="unity-playmode-fixture",frames=new[]{before,closed,reopened}},true));
                yield return Click(view.root.dialog.close);yield return Click(view.action);Assert.AreEqual(2,session.Progress.Actions);
                var reopenedStore=new ProgressStore(new FileSaveStore(folder,"player","qa",true));Assert.AreEqual(2,reopenedStore.Read().Actions);
                UnityEngine.Object.Destroy(copy);
            }
            finally
            {
                UnityEngine.Object.Destroy(root);if(Directory.Exists(folder))Directory.Delete(folder,true);
            }
            yield return null;
        }
    }
}

#endif
