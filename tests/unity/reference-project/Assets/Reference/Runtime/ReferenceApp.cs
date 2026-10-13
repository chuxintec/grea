using System;
using System.Collections;
using System.IO;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Grea.Foundation.Contracts;
using Grea.Foundation.Runtime;
using Grea.Reference.Domain;
using UnityEngine;

namespace Grea.Reference
{
    public sealed class ReferenceApp : MonoBehaviour
    {
        public ReferenceConfig config;
        public ReferenceView viewPrefab;
        public SignalSession Session { get; private set; }
        public ReferenceView View { get; private set; }
        public int ActiveOwnedResources => run?.OwnedCount ?? 0;
        LifetimeScope lifetime, run, interaction;
        ReferenceTrace trace;
        AudioClip tone;
        Lease<AudioSource> playing;
        bool initialized, stopped, focusPaused;
        float[] samples = new float[256];
        bool sampleAudio;
        public void Initialize(ReferenceView view, ReferenceConfig options, ISaveStore store, ReferenceTrace sink)
        {
            if (initialized) throw new InvalidOperationException("Already initialized");
            initialized = true; lifetime = new LifetimeScope(); View = view; config = options; trace = sink;
            try
            {
                if (!View || !config) throw new InvalidOperationException("Missing view or config");
                config.Validate(); View.Validate();
                Session = new SignalSession(config.goal, store);
                tone = AudioClip.Create("self-authored-signal", 13230, 1, 44100, false);
                var data = new float[13230];
                for (int i = 0; i < data.Length; i++) data[i] = .14f * Mathf.Sin(2 * Mathf.PI * 660 * i / 44100f) * (1 - (float)i / data.Length);
                tone.SetData(data, 0); lifetime.Own(tone, x => Destroy(x));
                View.Bind(this); Refresh("ready");
            }
            catch (Exception)
            {
                Session?.Fail(); trace?.Record("initialization_failed", Session);
                lifetime.Dispose(); View?.ShowError("Cannot start. Configuration or save needs review.");
                throw;
            }
        }
        void Start()
        {
            if (initialized) return;
            ReferenceTrace sink = null;
            try
            {
                if (!config || !viewPrefab) throw new InvalidOperationException("Missing startup binding");
                var args = Environment.GetCommandLineArgs(); string qaRoot = Arg(args, "--grea-qa-root");
                string id = Arg(args, "--grea-run-id");
                bool qa = qaRoot != null || Application.isEditor;
                string root = qaRoot ?? (Application.isEditor ? Path.GetFullPath(Path.Combine(Application.dataPath, "../Temp/ReferenceQA")) : Application.persistentDataPath);
                if (!Path.IsPathRooted(root)) throw new ArgumentException("QA root must be absolute");
                if (qaRoot != null)
                {
                    if (id == null || !Regex.IsMatch(id, @"\A[a-z0-9-]{1,64}\z")) throw new ArgumentException("Unique QA run id required");
                    Directory.CreateDirectory(Path.Combine(root, "runs")); sink = new ReferenceTrace(Path.Combine(root, "runs", id + ".jsonl"));
                }
                else sink = new ReferenceTrace(null);
                var view = Instantiate(viewPrefab); Initialize(view, config, new FileSaveStore(Path.Combine(root, "saves"), config.playerNamespace, config.qaNamespace, qa), sink);
            }
            catch (Exception e)
            {
                if (!View && viewPrefab) View = Instantiate(viewPrefab);
                if (View) View.ShowError("Cannot start. Configuration or save needs review.");
                sink?.Record("startup_failed", Session); sink?.Dispose(); trace = null;
                Debug.LogError("REFERENCE_START_FAILED: " + e.GetType().Name);
            }
        }
        static string Arg(string[] args, string key)
        {
            int index = Array.IndexOf(args, key);
            if (index < 0) return null;
            if (index + 1 >= args.Length) throw new ArgumentException("Missing argument value");
            return args[index + 1];
        }
        public void Begin()
        {
            if (!Session.Begin()) return;
            EndRun(); focusPaused = false; run = lifetime.CreateChild(); interaction = run.CreateChild(); Refresh("begin");
        }
        public async Task CollectAsync()
        {
            if (Session.Phase != Phase.Playing || interaction == null) return;
            var stamp = interaction.Capture("collect");
            try
            {
                await Task.Delay(TimeSpan.FromSeconds(config.collectDelaySeconds), stamp.Token); stamp.ThrowIfStale();
                if (!Session.Collect()) return;
                playing?.Dispose(); playing = new AudioPlayer(transform).Play(tone, run);
                sampleAudio = true; StartCoroutine(ReleaseTone(playing)); Refresh("collect");
                if (Session.Phase == Phase.Complete) { interaction.Dispose(); interaction = null; trace?.Record("complete", Session); }
            }
            catch (OperationCanceledException) { trace?.Record("collect_cancelled", Session); }
            catch (Exception)
            { Session.Fail(); EndRun(); View.ShowError("Save failed. Existing data is preserved."); trace?.Record("save_failed", Session); }
        }
        IEnumerator ReleaseTone(Lease<AudioSource> handle)
        { yield return new WaitForSecondsRealtime(.35f); handle.Dispose(); }
        void Update()
        {
            // QA records the actual engine input and raycast, never calls a command to simulate a click.
            if (trace?.Enabled == true && (Input.GetMouseButtonDown(0) || Input.GetMouseButtonUp(0)))
            {
                var hits = new System.Collections.Generic.List<UnityEngine.EventSystems.RaycastResult>();
                var events = UnityEngine.EventSystems.EventSystem.current;
                if (events) events.RaycastAll(new UnityEngine.EventSystems.PointerEventData(events) { position = Input.mousePosition }, hits);
                trace.Record(Input.GetMouseButtonDown(0) ? "pointer_down" : "pointer_up", Session, 0, Input.mousePosition, hits.Count > 0 ? hits[0].gameObject.name : "none");
            }
            if (sampleAudio && playing != null && !playing.IsDisposed && playing.Value)
            {
                AudioListener.GetOutputData(samples, 0); float sum = 0;
                foreach (float x in samples) sum += x * x;
                float rms = Mathf.Sqrt(sum / samples.Length);
                if (rms > .0001f) { trace?.Record("audio_signal", Session, rms); sampleAudio = false; }
            }
            if (Input.GetKeyDown(KeyCode.Escape))
            { if (Session?.Phase == Phase.Playing) Pause(); else if (Session?.Phase == Phase.Paused) Resume(); }
        }
        public void Pause()
        {
            if (!Session.Pause()) return;
            interaction?.Dispose(); interaction = null; playing?.Dispose(); Refresh("pause");
        }
        public void Resume()
        {
            if (!Session.Resume()) return;
            interaction = run.CreateChild(); focusPaused = false; Refresh("resume");
        }
        public void Menu()
        { if (!Session.Return()) return; EndRun(); Refresh("menu"); }
        void OnApplicationFocus(bool focused)
        { if (!focused && Session?.Phase == Phase.Playing) { focusPaused = true; Pause(); } }
        public void Quit() { trace?.Record("quit_requested", Session); Application.Quit(); }
        void Refresh(string code) { View.Render(Session, focusPaused); trace?.Record(code, Session); }
        void EndRun() { run?.Dispose(); run = null; interaction = null; playing = null; sampleAudio = false; }
        void Shutdown()
        {
            if (stopped) return; stopped = true;
            EndRun(); lifetime?.Dispose(); trace?.Record("shutdown", Session); trace?.Dispose(); trace = null;
            Session?.Stop(); if (View) Destroy(View.gameObject);
        }
        void OnApplicationQuit() => Shutdown();
        void OnDestroy() => Shutdown();
    }
}
