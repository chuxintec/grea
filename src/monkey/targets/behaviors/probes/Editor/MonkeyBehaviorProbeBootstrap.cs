using System;
using System.Globalization;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using Monkey.Recovered.Behaviors.Probes;

[InitializeOnLoad]
public static class MonkeyBehaviorProbeBootstrap
{
    private const string StageKey = "MonkeyBehaviorProbe.Stage";
    private const string ReceiptKey = "MonkeyBehaviorProbe.Receipt";
    private const string DeadlineKey = "MonkeyBehaviorProbe.DeadlineUtc";
    private const string ExitCodeKey = "MonkeyBehaviorProbe.ExitCode";
    private static bool startQueued;

    static MonkeyBehaviorProbeBootstrap()
    {
        EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
        EditorApplication.playModeStateChanged += OnPlayModeStateChanged;
        EditorApplication.update -= WatchDeadline;
        EditorApplication.update += WatchDeadline;

        string stage = SessionState.GetString(StageKey, "");
        if ((stage == "enter-play" || stage == "running") && EditorApplication.isPlaying)
            QueueProbeStart();
        else if (stage == "exit-play" && !EditorApplication.isPlaying)
            EditorApplication.delayCall += ExitBatchProcess;
    }

    /// <summary>Batch entry point; creates a new empty scene before entering Play.</summary>
    public static void Begin()
    {
        try
        {
            if (!Application.isBatchMode)
                throw new InvalidOperationException("This probe entry requires Unity batchMode.");
            if (EditorApplication.isPlayingOrWillChangePlaymode)
                throw new InvalidOperationException("Unity is already entering or running Play mode.");

            string receiptPath = ArgumentValue("-monkeyProbeReceipt");
            string deadline = ArgumentValue("-monkeyProbeDeadlineUtc");
            if (string.IsNullOrWhiteSpace(receiptPath) || string.IsNullOrWhiteSpace(deadline))
                throw new ArgumentException("Pass -monkeyProbeReceipt and -monkeyProbeDeadlineUtc.");

            DateTime deadlineUtc = DateTime.Parse(deadline, CultureInfo.InvariantCulture,
                DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal);
            if (DateTime.UtcNow >= deadlineUtc)
                throw new TimeoutException("The requested probe deadline has already elapsed.");

            SessionState.SetString(ReceiptKey, Path.GetFullPath(receiptPath));
            SessionState.SetString(DeadlineKey, deadlineUtc.ToString("O", CultureInfo.InvariantCulture));
            SessionState.SetInt(ExitCodeKey, 1);

            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var host = new GameObject("NativeBehaviorProbeOnly");
            host.AddComponent<UnityBehaviorProbe>();
            Scene active = SceneManager.GetActiveScene();
            if (active.rootCount != 1 || active.GetRootGameObjects()[0] != host)
                throw new InvalidOperationException("Isolated probe scene contains unexpected roots.");

            SessionState.SetString(StageKey, "enter-play");
            EditorApplication.isPlaying = true;
        }
        catch (Exception error)
        {
            WriteFailure(error.ToString(), 2);
            if (Application.isBatchMode) EditorApplication.Exit(2);
            else throw;
        }
    }

    private static void OnPlayModeStateChanged(PlayModeStateChange state)
    {
        string stage = SessionState.GetString(StageKey, "");
        if (state == PlayModeStateChange.EnteredPlayMode && stage == "enter-play")
            QueueProbeStart();
        else if (state == PlayModeStateChange.EnteredEditMode && stage == "exit-play")
            EditorApplication.delayCall += ExitBatchProcess;
    }

    private static void QueueProbeStart()
    {
        if (startQueued) return;
        startQueued = true;
        SessionState.SetString(StageKey, "running");
        EditorApplication.delayCall += StartProbeInPlayMode;
    }

    private static void StartProbeInPlayMode()
    {
        startQueued = false;
        if (!EditorApplication.isPlaying || SessionState.GetString(StageKey, "") != "running") return;
        try
        {
            var probe = UnityEngine.Object.FindFirstObjectByType<UnityBehaviorProbe>();
            if (probe == null)
            {
                Finish("{\"status\":\"error\",\"reason\":\"probe component missing after domain reload\"}", 3);
                return;
            }
            probe.StartCoroutine(probe.RunProbe(json => Finish(json, 0)));
        }
        catch (Exception error)
        {
            Finish("{\"status\":\"error\",\"message\":" + EscapeJson(error.ToString()) + "}", 3);
        }
    }

    private static void WatchDeadline()
    {
        string stage = SessionState.GetString(StageKey, "");
        if (stage != "enter-play" && stage != "running") return;
        string value = SessionState.GetString(DeadlineKey, "");
        if (DateTime.TryParse(value, CultureInfo.InvariantCulture,
                DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out var deadline) &&
            DateTime.UtcNow >= deadline)
            Finish("{\"status\":\"timeout\",\"reason\":\"Unity behavior probe deadline elapsed\"}", 124);
    }

    private static void Finish(string json, int code)
    {
        WriteReceipt(json);
        SessionState.SetInt(ExitCodeKey, code);
        SessionState.SetString(StageKey, "exit-play");
        EditorApplication.isPlaying = false;
        if (!EditorApplication.isPlayingOrWillChangePlaymode)
            EditorApplication.delayCall += ExitBatchProcess;
    }

    private static void WriteFailure(string message, int code)
    {
        WriteReceipt("{\"status\":\"error\",\"message\":" + EscapeJson(message) + "}");
        SessionState.SetInt(ExitCodeKey, code);
        SessionState.SetString(StageKey, "exit-play");
    }

    private static string EscapeJson(string value)
    {
        return "\"" + (value ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"")
            .Replace("\r", "\\r").Replace("\n", "\\n") + "\"";
    }

    private static void WriteReceipt(string json)
    {
        string path = SessionState.GetString(ReceiptKey, "");
        if (string.IsNullOrWhiteSpace(path)) return;
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, json + Environment.NewLine);
    }

    private static void ExitBatchProcess()
    {
        if (!Application.isBatchMode || EditorApplication.isPlayingOrWillChangePlaymode) return;
        int code = SessionState.GetInt(ExitCodeKey, 1);
        SessionState.SetString(StageKey, "finished");
        EditorApplication.Exit(code);
    }

    private static string ArgumentValue(string key)
    {
        string[] args = Environment.GetCommandLineArgs();
        for (int i = 0; i + 1 < args.Length; i++)
            if (string.Equals(args[i], key, StringComparison.Ordinal)) return args[i + 1];
        return null;
    }
}
