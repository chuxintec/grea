using System;
using System.Collections;
using System.Threading.Tasks;
using Grea.Foundation.Contracts;
using Grea.Reference.Domain;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Grea.Reference.Tests
{
    public sealed class ReferenceLoopTests
    {
        sealed class Store : ISaveStore {public string Data;public string Read()=>Data;public void Write(string value)=>Data=value;}
        ReferenceApp app;ReferenceConfig config;
        [SetUp] public void Setup()
        {
#if UNITY_EDITOR
            var prefab=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Reference/Content/ReferenceView.prefab");
            var view=UnityEngine.Object.Instantiate(prefab).GetComponent<ReferenceView>();
            var root=new GameObject("IsolatedApp");root.SetActive(false);app=root.AddComponent<ReferenceApp>();
            config=ScriptableObject.CreateInstance<ReferenceConfig>();config.collectDelaySeconds=.01f;
            app.Initialize(view,config,new Store(),new ReferenceTrace(null));root.SetActive(true);
#else
            Assert.Ignore("Editor fixture test only");
#endif
        }
        [TearDown] public void Teardown(){if(app)UnityEngine.Object.DestroyImmediate(app.gameObject);if(config)UnityEngine.Object.DestroyImmediate(config);}
        IEnumerator Finish(Task task){double deadline=Time.realtimeSinceStartupAsDouble+5;while(!task.IsCompleted&&Time.realtimeSinceStartupAsDouble<deadline)yield return null;Assert.IsTrue(task.IsCompleted);if(task.IsFaulted)throw task.Exception;}
        [UnityTest] public IEnumerator VisibleStartButtonReceivesRaycastAndPointerClick()
        {
            yield return null; Canvas.ForceUpdateCanvases();
            var events = UnityEngine.EventSystems.EventSystem.current;
            Assert.IsNotNull(events);
            var target = app.View.startButton.gameObject;
            var pointer = new UnityEngine.EventSystems.PointerEventData(events) { position = RectTransformUtility.WorldToScreenPoint(null, target.transform.position) };
            var hits = new System.Collections.Generic.List<UnityEngine.EventSystems.RaycastResult>();
            events.RaycastAll(pointer, hits);
            Assert.IsNotEmpty(hits); Assert.AreEqual(target, hits[0].gameObject);
            UnityEngine.EventSystems.ExecuteEvents.Execute(target, pointer, UnityEngine.EventSystems.ExecuteEvents.pointerClickHandler);
            Assert.AreEqual(Phase.Playing, app.Session.Phase);
        }
        [UnityTest] public IEnumerator FullLoopIncludingRepeatedGameAndPause()
        {
            app.Begin();yield return Finish(app.CollectAsync());Assert.AreEqual(1,app.Session.Score);
            app.Pause();yield return Finish(app.CollectAsync());Assert.AreEqual(1,app.Session.Score);app.Resume();
            for(int i=0;i<4;i++)yield return Finish(app.CollectAsync());Assert.AreEqual(Phase.Complete,app.Session.Phase);
            app.Menu();Assert.AreEqual(0,app.ActiveOwnedResources);app.Begin();Assert.AreEqual(0,app.Session.Score);Assert.AreEqual(1,app.Session.Wins);
            app.Menu();yield return null;
        }
        [UnityTest] public IEnumerator ExitAndPauseCancelLateCollection()
        {
            config.collectDelaySeconds=.1f;app.Begin();var pending=app.CollectAsync();app.Menu();yield return Finish(pending);Assert.AreEqual(0,app.Session.Score);Assert.AreEqual(0,app.ActiveOwnedResources);
            app.Begin();pending=app.CollectAsync();app.Pause();app.Resume();yield return Finish(pending);Assert.AreEqual(0,app.Session.Score);
        }
        [UnityTest] public IEnumerator RepeatedUiEntryDoesNotDuplicateClickHandlers()
        {
            for(int i=0;i<3;i++){app.Begin();app.Menu();}
            app.View.startButton.GetComponent<UnityEngine.UI.Button>().onClick.Invoke();
            app.View.targetButton.GetComponent<UnityEngine.UI.Button>().onClick.Invoke();app.View.targetButton.GetComponent<UnityEngine.UI.Button>().onClick.Invoke();
            yield return Finish(app.View.targetButton.Pending);Assert.AreEqual(1,app.Session.Score);
        }
        [Test] public void InitializationFailureCleansAndDoesNotCreateImplicitDefaults()
        {
            var root=new GameObject("bad-init");root.SetActive(false);var bad=root.AddComponent<ReferenceApp>();
            try {Assert.Throws<InvalidOperationException>(()=>bad.Initialize(null,config,new Store(),new ReferenceTrace(null)));Assert.AreEqual(0,bad.ActiveOwnedResources);}
            finally {UnityEngine.Object.DestroyImmediate(root);}
        }
    }
}
