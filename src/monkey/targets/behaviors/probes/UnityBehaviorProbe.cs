using System;
using System.Collections;
using System.Collections.Generic;
using System.Threading.Tasks;
using Monkey.Recovered.Behaviors;
using UnityEngine;

namespace Monkey.Recovered.Behaviors.Probes
{
    /// <summary>
    /// Manual Play-mode probe. Attach to an isolated scene object and invoke
    /// RunProbe from the owning acceptance harness. It never starts itself.
    /// </summary>
    public sealed class UnityBehaviorProbe : MonoBehaviour
    {
        [Serializable]
        public sealed class Observation
        {
            public string id;
            public float elapsedSeconds;
            public float[] scale;
            public string scaleState;
            public bool nodeExists;
            public bool active;
            public bool componentEnabled;
        }

        [Serializable]
        public sealed class Checkpoint
        {
            public string id;
            public string relativeTo;
            public float seconds;
            public float[] expectedScale;
            public string expectedScaleState = "specified";
            public string sourceMeaning;
        }

        [Serializable]
        public sealed class TaskObservation
        {
            public string name;
            public bool completed;
            public bool faulted;
        }

        [Serializable]
        public sealed class StabilityCheck
        {
            public string name;
            public string beforeId;
            public string afterId;
            public float tolerance;
        }

        private static List<Checkpoint> BuildCheckpointPlan()
        {
            return new List<Checkpoint>
            {
                new Checkpoint { id="breath.start", relativeTo="breathCycleStart", seconds=0f, expectedScale=new[]{2f,3f,4f}, sourceMeaning="onLoad reads scale.x without writing the node" },
                new Checkpoint { id="breath.riseHalf", relativeTo="breathCycleStart", seconds=0.2f, expectedScale=new[]{2.1f,2.1f,2.1f}, sourceMeaning="quadInOut midpoint after scalar X capture and uniform setScale" },
                new Checkpoint { id="breath.riseEnd", relativeTo="breathCycleStart", seconds=0.4f, expectedScale=new[]{2.2f,2.2f,2.2f}, sourceMeaning="first tween reaches captured X plus offset" },
                new Checkpoint { id="breath.fallHalf", relativeTo="breathCycleStart", seconds=0.6f, expectedScale=new[]{2.1f,2.1f,2.1f}, sourceMeaning="return tween quadInOut midpoint" },
                new Checkpoint { id="breath.fallEnd", relativeTo="breathCycleStart", seconds=0.8f, expectedScale=new[]{2f,2f,2f}, sourceMeaning="return tween reaches captured scalar X" },
                new Checkpoint { id="scaleBack.showInstant", relativeTo="scaleBackStart", seconds=0f, expectedScale=new[]{0.6f,0.6f,0.6f}, sourceMeaning="show assigns scaleFrom before starting the tween" },
                new Checkpoint { id="scaleBack.showHalf", relativeTo="scaleBackStart", seconds=0.2f, expectedScale=new[]{1.035f,1.035f,1.035f}, sourceMeaning="backOut midpoint checkpoint" },
                new Checkpoint { id="scaleBack.showEnd", relativeTo="scaleBackStart", seconds=0.4f, expectedScale=new[]{1f,1f,1f}, sourceMeaning="show tween reaches uniform scale one" },
                new Checkpoint { id="scaleBack.overlapHideInitial", relativeTo="scaleBackOverlapStart", seconds=0f, expectedScale=null, expectedScaleState="unspecified", sourceMeaning="immediate show-to-hide overlap observation; timer and tween frame order is unspecified" },
                new Checkpoint { id="scaleBack.overlapHideHalf", relativeTo="scaleBackOverlapStart", seconds=0.2f, expectedScale=null, expectedScaleState="unspecified", sourceMeaning="immediate show-to-hide overlap observation; no deterministic midpoint oracle" },
                new Checkpoint { id="scaleBack.overlapHideEnd", relativeTo="scaleBackOverlapStart", seconds=0.4f, expectedScale=null, expectedScaleState="unspecified", sourceMeaning="immediate show-to-hide overlap observation; source hide assigns zero after its timer" },
                new Checkpoint { id="scaleBack.hideInitial", relativeTo="scaleBackHideOnlyStart", seconds=0f, expectedScale=new[]{2f,3f,4f}, sourceMeaning="fresh node preserves nonuniform initial scale before hide tween update" },
                new Checkpoint { id="scaleBack.hideHalf", relativeTo="scaleBackHideOnlyStart", seconds=0.2f, expectedScale=new[]{2.123f,2.123f,2.123f}, sourceMeaning="isolated backIn midpoint from scalar X=2 toward scaleFrom" },
                new Checkpoint { id="scaleBack.hideEnd", relativeTo="scaleBackHideOnlyStart", seconds=0.4f, expectedScale=new[]{0f,0f,0f}, sourceMeaning="isolated hide sets scale zero after kt timer resolves" },
                new Checkpoint { id="scaleBack.hideInstant", relativeTo="scaleBackHideOnlyStart", seconds=0.4f, expectedScale=new[]{0f,0f,0f}, sourceMeaning="tweenHide false sets scale zero without a tween" },
            };
        }

        [Serializable]
        public sealed class Receipt
        {
            public string schema = "monkey-prefab-behavior-runtime-probe/1";
            public string targetEngine = "Unity " + Application.unityVersion;
            public string sourceEngine = "Cocos Creator 2.4.15";
            public string ruleVersion = "monkey-prefab-local-behaviors/1";
            public string sourceBundleSha256 = "21af08e48846f6ad1a2e0673b0c945358136723b1664f0cd1f6ec9b3df6c5cb5";
            public string breathEffectSha256 = "a44e4524015e193da241958bfe2b47901a6232ac89e0e063b59a9a362da94617";
            public string scaleBackEffectSha256 = "ab661a87764aba785f3039b2767301d8b854031b1b57f813a559bf5a09e6c924";
            public float timeScale;
            public float tweenSeconds = 0.4f;
            public float breathDelaySeconds = 0.3f;
            public float breathOffset = 0.2f;
            public float scaleBackFrom = 0.6f;
            public string sampleClock = "Time.realtimeSinceStartup; coroutine easing advances with Time.deltaTime";
            public string[] unknownSemantics = {
                "BaseEffect.reset stopAllActions node-wide cancellation remains unclosed because native tween/coroutine ownership is component-local and untracked node actions have no shared typed registry",
                "ScaleBackEffect disable/destroy tween cancellation is not specified by its source hooks",
                "Immediate ScaleBackEffect show-to-hide overlap is recorded without a deterministic midpoint oracle because wall-clock kt and engine-frame tween completion can race"
            };
            public string probeRevision = "scaleBack-hide-isolated-02";
            public string[] taskExpectations = {
                "scaleBack.show", "scaleBack.overlapHide", "scaleBack.hideOnly", "scaleBack.hideInstant",
                "scaleBack.disabledShow", "scaleBack.destroyDuringTweenShow"
            };
            public string[] destructionChecks = {
                "breath.destroyed", "breath.lifecycleDestroyed",
                "scaleBack.overlapDestroyed", "scaleBack.destroyed", "scaleBack.lifecycleDestroyed", "scaleBack.destroyDuringTween"
            };
            public List<StabilityCheck> stabilityChecks = new List<StabilityCheck>
            {
                new StabilityCheck { name="running_false_holds_scale", beforeId="breath.runningFalseBefore", afterId="breath.runningFalseAfter", tolerance=0.015f },
                new StabilityCheck { name="disabled_breath_cancels_owned_tween", beforeId="breath.disabledBefore", afterId="breath.disabledAfter", tolerance=0.015f },
            };
            public List<Observation> observations = new List<Observation>();
            public List<Checkpoint> checkpointPlan = UnityBehaviorProbe.BuildCheckpointPlan();
            public List<TaskObservation> taskResults = new List<TaskObservation>();
        }

        public float tweenSeconds = 0.4f;
        public float breathDelaySeconds = 0.3f;
        public float breathOffset = 0.2f;
        public float scaleBackFrom = 0.6f;

        private Receipt receipt;
        private float clockOrigin;

        public IEnumerator RunProbe(Action<string> completed = null)
        {
            receipt = new Receipt
            {
                timeScale = Time.timeScale,
                tweenSeconds = tweenSeconds,
                breathDelaySeconds = breathDelaySeconds,
                breathOffset = breathOffset,
                scaleBackFrom = scaleBackFrom,
            };
            yield return StartCoroutine(ProbeBreathCycle());
            yield return StartCoroutine(ProbeBreathLifecycle());
            yield return StartCoroutine(ProbeScaleBack());
            yield return StartCoroutine(ProbeScaleBackLifecycle());
            yield return StartCoroutine(ProbeScaleBackDestroy());
            string json = JsonUtility.ToJson(receipt);
            Debug.Log("MONKEY_BEHAVIOR_PROBE:" + json);
            completed?.Invoke(json);
        }

        private IEnumerator ProbeBreathCycle()
        {
            GameObject go = NewInactive("BreathCycle", new Vector3(2f, 3f, 4f));
            var behaviour = go.AddComponent<BreathEffect>();
            behaviour.tweenTime = tweenSeconds;
            behaviour.delay = breathDelaySeconds;
            behaviour.offset = breathOffset;
            clockOrigin = Time.realtimeSinceStartup;
            go.SetActive(true);
            Record("breath.start", go);
            yield return new WaitForSecondsRealtime(tweenSeconds * 0.5f);
            Record("breath.riseHalf", go);
            yield return new WaitForSecondsRealtime(tweenSeconds * 0.5f);
            Record("breath.riseEnd", go);
            yield return new WaitForSecondsRealtime(tweenSeconds * 0.5f);
            Record("breath.fallHalf", go);
            yield return new WaitForSecondsRealtime(tweenSeconds * 0.5f);
            Record("breath.fallEnd", go);
            Destroy(go);
            yield return null;
            receipt.observations.Add(new Observation { id = "breath.destroyed", elapsedSeconds = Time.realtimeSinceStartup - clockOrigin, scaleState = "unavailable", nodeExists = false, active = false, componentEnabled = false });
        }

        private IEnumerator ProbeBreathLifecycle()
        {
            GameObject go = NewInactive("BreathLifecycle", new Vector3(2f, 3f, 4f));
            var behaviour = go.AddComponent<BreathEffect>();
            behaviour.tweenTime = tweenSeconds;
            behaviour.delay = breathDelaySeconds;
            behaviour.offset = breathOffset;
            clockOrigin = Time.realtimeSinceStartup;
            go.SetActive(true);
            yield return new WaitForSecondsRealtime(tweenSeconds * 0.5f);
            behaviour.Running = false;
            Record("breath.runningFalseBefore", go);
            yield return new WaitForSecondsRealtime(0.12f);
            Record("breath.runningFalseAfter", go);
            behaviour.Running = true;
            yield return new WaitForSecondsRealtime(tweenSeconds * 0.5f);
            Record("breath.resumedHalf", go);
            behaviour.enabled = false;
            Record("breath.disabledBefore", go);
            yield return new WaitForSecondsRealtime(0.12f);
            Record("breath.disabledAfter", go);
            behaviour.enabled = true;
            yield return new WaitForSecondsRealtime(0.08f);
            Destroy(go);
            yield return null;
            receipt.observations.Add(new Observation { id = "breath.lifecycleDestroyed", elapsedSeconds = Time.realtimeSinceStartup - clockOrigin, scaleState = "unavailable", nodeExists = false, active = false, componentEnabled = false });
        }

        private IEnumerator ProbeScaleBack()
        {
            GameObject go = NewInactive("ScaleBack", new Vector3(2f, 3f, 4f));
            var behaviour = go.AddComponent<ScaleBackEffect>();
            behaviour.tweenTime = tweenSeconds;
            behaviour.scaleFrom = scaleBackFrom;
            behaviour.tweenHide = true;
            clockOrigin = Time.realtimeSinceStartup;
            go.SetActive(true);
            Task show = behaviour.Show();
            Record("scaleBack.showInstant", go);
            yield return new WaitForSecondsRealtime(tweenSeconds * 0.5f);
            Record("scaleBack.showHalf", go);
            yield return WaitForTask(show, tweenSeconds);
            RecordTask("scaleBack.show", show);
            Record("scaleBack.showEnd", go);

            clockOrigin = Time.realtimeSinceStartup;
            go.transform.localScale = new Vector3(2f, 3f, 4f);
            Task overlapHide = behaviour.Hide();
            Record("scaleBack.overlapHideInitial", go);
            yield return new WaitForSecondsRealtime(tweenSeconds * 0.5f);
            Record("scaleBack.overlapHideHalf", go);
            yield return WaitForTask(overlapHide, tweenSeconds);
            RecordTask("scaleBack.overlapHide", overlapHide);
            Record("scaleBack.overlapHideEnd", go);
            Destroy(go);
            yield return null;
            receipt.observations.Add(new Observation { id = "scaleBack.overlapDestroyed", elapsedSeconds = Time.realtimeSinceStartup - clockOrigin, scaleState = "unavailable", nodeExists = false, active = false, componentEnabled = false });

            GameObject hideOnlyGo = NewInactive("ScaleBackHideOnly", new Vector3(2f, 3f, 4f));
            var hideOnlyBehaviour = hideOnlyGo.AddComponent<ScaleBackEffect>();
            hideOnlyBehaviour.tweenTime = tweenSeconds;
            hideOnlyBehaviour.scaleFrom = scaleBackFrom;
            hideOnlyBehaviour.tweenHide = true;
            clockOrigin = Time.realtimeSinceStartup;
            hideOnlyGo.SetActive(true);
            Task hide = hideOnlyBehaviour.Hide();
            Record("scaleBack.hideInitial", hideOnlyGo);
            yield return new WaitForSecondsRealtime(tweenSeconds * 0.5f);
            Record("scaleBack.hideHalf", hideOnlyGo);
            yield return WaitForTask(hide, tweenSeconds);
            RecordTask("scaleBack.hideOnly", hide);
            Record("scaleBack.hideEnd", hideOnlyGo);

            hideOnlyBehaviour.tweenHide = false;
            Task instantHide = hideOnlyBehaviour.Hide();
            yield return WaitForTask(instantHide, 0.1f);
            RecordTask("scaleBack.hideInstant", instantHide);
            Record("scaleBack.hideInstant", hideOnlyGo);
            Destroy(hideOnlyGo);
            yield return null;
            receipt.observations.Add(new Observation { id = "scaleBack.destroyed", elapsedSeconds = Time.realtimeSinceStartup - clockOrigin, scaleState = "unavailable", nodeExists = false, active = false, componentEnabled = false });
        }

        private IEnumerator ProbeScaleBackLifecycle()
        {
            GameObject go = NewInactive("ScaleBackLifecycle", new Vector3(2f, 3f, 4f));
            var behaviour = go.AddComponent<ScaleBackEffect>();
            behaviour.tweenTime = tweenSeconds;
            behaviour.scaleFrom = scaleBackFrom;
            clockOrigin = Time.realtimeSinceStartup;
            go.SetActive(true);
            Task show = behaviour.Show();
            yield return new WaitForSecondsRealtime(0.1f);
            go.SetActive(false);
            Record("scaleBack.disabled", go);
            yield return WaitForTask(show, tweenSeconds * 2f);
            RecordTask("scaleBack.disabledShow", show);
            Destroy(go);
            yield return null;
            receipt.observations.Add(new Observation { id = "scaleBack.lifecycleDestroyed", elapsedSeconds = Time.realtimeSinceStartup - clockOrigin, scaleState = "unavailable", nodeExists = false, active = false, componentEnabled = false });
        }

        private IEnumerator ProbeScaleBackDestroy()
        {
            GameObject go = NewInactive("ScaleBackDestroyDuringTween", new Vector3(2f, 3f, 4f));
            var behaviour = go.AddComponent<ScaleBackEffect>();
            behaviour.tweenTime = tweenSeconds;
            behaviour.scaleFrom = scaleBackFrom;
            clockOrigin = Time.realtimeSinceStartup;
            go.SetActive(true);
            Task show = behaviour.Show();
            yield return new WaitForSecondsRealtime(0.1f);
            Destroy(go);
            yield return null;
            receipt.observations.Add(new Observation { id = "scaleBack.destroyDuringTween", elapsedSeconds = Time.realtimeSinceStartup - clockOrigin, scaleState = "unavailable", nodeExists = false, active = false, componentEnabled = false });
            yield return WaitForTask(show, tweenSeconds * 2f);
            RecordTask("scaleBack.destroyDuringTweenShow", show);
        }

        private GameObject NewInactive(string name, Vector3 scale)
        {
            var go = new GameObject(name);
            go.SetActive(false);
            go.transform.localScale = scale;
            go.transform.SetParent(transform, false);
            return go;
        }

        private void Record(string id, GameObject go)
        {
            Vector3 scale = go.transform.localScale;
            receipt.observations.Add(new Observation
            {
                id = id,
                elapsedSeconds = Time.realtimeSinceStartup - clockOrigin,
                scale = new[] { scale.x, scale.y, scale.z },
                scaleState = "measured",
                nodeExists = go != null,
                active = go.activeInHierarchy,
                componentEnabled = go.GetComponent<Behaviour>() != null && go.GetComponent<Behaviour>().enabled,
            });
        }

        private void RecordTask(string name, Task task)
        {
            receipt.taskResults.Add(new TaskObservation
            {
                name = name,
                completed = task != null && task.IsCompleted,
                faulted = task != null && task.IsFaulted,
            });
        }

        private static IEnumerator WaitForTask(Task task, float timeout)
        {
            float start = Time.realtimeSinceStartup;
            while (task != null && !task.IsCompleted && Time.realtimeSinceStartup - start < timeout)
                yield return null;
        }
    }
}
