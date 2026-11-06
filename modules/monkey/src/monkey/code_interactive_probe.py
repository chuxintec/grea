"""A fresh Editor-only pointer flow over already source-bound recovered modules."""
from pathlib import Path

from .code_native_probe import prepare as prepare_native
from .io import safe, read, sha, write_json


def prepare(candidate, expected_manifest_sha256, output):
    result = prepare_native(candidate, expected_manifest_sha256, output, recipe_module=True)
    out = safe(output)
    path = out / 'Assets/Editor/InteractiveModuleProbeWindow.cs'
    raw = _source(expected_manifest_sha256).encode('utf-8')
    path.write_bytes(raw)
    # Unity 6000.6.2f1's normal default index, project-local only. Its startup
    # initializer skips creating this file while PlayMode is pending; a fresh
    # scripted window can expose its Start control before that initialization.
    index=out/'UserSettings/Search.index'
    write_json(index,dict(name='Assets',roots=['Assets','Packages'],includes=[],excludes=['Assets/Temp/','Assets/External/'],
                          options=dict(types=True,properties=True,extended=False,dependencies=True),baseScore=999))
    plan = dict(schemaVersion=1,status='prepared_not_run',candidateManifestSha256=expected_manifest_sha256,
                mode='Editor-only IMGUI pointer flow; new test UI, not recovered original UI',
                sourceBinding='Exact HealthState delegate fields and RecipeCatalog source methods from native plan',
                sourceExecuted=False,executeMethod='MonkeyInteractiveProbeWindow.Open',
                script=dict(path=path.relative_to(out).as_posix(),sha256=sha(raw)),
                projectSearchIndex=dict(path='UserSettings/Search.index',sha256=sha(read(index)),scope='Normal project-local default; no global preferences or index disabling'),
                receipt='interactive-code-probe.json',physicalHumanInput='not_claimed',
                steps=['start-play','damage','heal','combo','query-recipe','stop-and-reopen'],
                originalComponents='Source HealthState is an ECS model; its original entity lifecycle and UI consumers are not recovered by this adapter')
    write_json(out/'interactive-code-probe-plan.json',plan)
    return dict(status='prepared_not_run',project=str(out),plan=str(out/'interactive-code-probe-plan.json'),executeMethod=plan['executeMethod'])


def _source(manifest):
    return r'''using System;
using System.IO;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using Game.Domain.Recovered;
using Monkey.CodeModuleProbe;

[Serializable] public sealed class InteractiveModuleAction {
    public string action, inputEvent;
    public double hp, combo;
    public int hpCallbacks, comboCallbacks;
}
[Serializable] public sealed class InteractiveModuleReceipt {
    public int schemaVersion = 1;
    public string status = "awaiting_pointer_actions", candidateManifestSha256 = "__MANIFEST__";
    public string originalUi = "not_recovered; new Editor test UI";
    public string inputScope = "CUA/OS pointer to IMGUI; not original-game input or human-input claim";
    public bool sourceExecuted = false, originalLifecycleRecovered = false;
    public int nextStep;
    public string bindingsBefore, bindingsAfter, error;
    public bool onDestroyUnsubscribed;
    public double[] recipeLeaves;
    public List<InteractiveModuleAction> actions = new List<InteractiveModuleAction>();
}

public sealed class MonkeyInteractiveProbeWindow : EditorWindow {
    private InteractiveModuleReceipt receipt;
    private static string ReceiptPath { get { return Path.Combine(Directory.GetParent(Application.dataPath).FullName, "interactive-code-probe.json"); } }
    public static void Open() {
        if (File.Exists(ReceiptPath)) throw new InvalidOperationException("Prepare a fresh interactive project.");
        var bindings = MonkeyCodeModuleProbe.PrepareInteractiveScene();
        var window = GetWindow<MonkeyInteractiveProbeWindow>("Monkey Module Flow");
        window.minSize = new Vector2(620, 550);
        window.position = new Rect(140, 90, 760, 620);
        window.receipt = new InteractiveModuleReceipt { bindingsBefore = bindings };
        window.Save(); window.Show(); window.Focus();
    }
    private void OnEnable() { receipt = null; Load(); EditorApplication.update += Poll; EditorApplication.playModeStateChanged += PlayState; }
    private void OnDisable() { EditorApplication.update -= Poll; EditorApplication.playModeStateChanged -= PlayState; }
    private void PlayState(PlayModeStateChange state) {
        Load();
        if (state == PlayModeStateChange.EnteredEditMode && receipt != null && receipt.status == "reopening") {
            receipt.status = "ready_to_reopen"; Save();
        }
    }
    private void Load() {
        if (receipt == null && File.Exists(ReceiptPath)) receipt = JsonUtility.FromJson<InteractiveModuleReceipt>(File.ReadAllText(ReceiptPath));
    }
    private void Save() { File.WriteAllText(ReceiptPath, JsonUtility.ToJson(receipt, true)); Repaint(); }
    private void Poll() {
        Load(); if (receipt == null) return;
        if (receipt.status == "ready_to_reopen" && !Application.isPlaying && !EditorApplication.isPlaying && !EditorApplication.isPlayingOrWillChangePlaymode && !EditorApplication.isCompiling && !EditorApplication.isUpdating) {
            try {
                receipt.bindingsAfter = MonkeyCodeModuleProbe.ReopenInteractiveScene();
                if (receipt.bindingsBefore != receipt.bindingsAfter) throw new InvalidOperationException("Saved bindings changed after pointer flow.");
                receipt.status = "passed"; Save();
            } catch (Exception e) { Fail(e); }
        }
        Repaint();
    }
    private void Fail(Exception error) { receipt.status = "failed"; receipt.error = error.Message; Save(); }
    private void Record(string action, EventType input, CodeModuleProbeRuntime runtime) {
        if (input != EventType.MouseUp) throw new InvalidOperationException("Proof requires an OS pointer MouseUp on this control.");
        var row = new InteractiveModuleAction { action = action, inputEvent = input.ToString() };
        if (runtime != null) { row.hp = runtime.State.currHp; row.combo = runtime.State.combo; row.hpCallbacks = runtime.Readout.hpCallbacks; row.comboCallbacks = runtime.Readout.comboCallbacks; }
        receipt.actions.Add(row); receipt.nextStep++; Save();
    }
    private void OnGUI() {
        Load(); if (receipt == null) { GUILayout.Label("Use MonkeyInteractiveProbeWindow.Open on a fresh project."); return; }
        var input = Event.current.rawType;
        GUILayout.Space(14);
        GUILayout.Label("Source-bound module flow", EditorStyles.boldLabel);
        GUILayout.Label("New Editor test controls; original game UI/lifecycle are not restored.");
        GUILayout.Label("Status: " + receipt.status + "    Step: " + receipt.nextStep + " / 6");
        var runtime = UnityEngine.Object.FindAnyObjectByType<CodeModuleProbeRuntime>();
        bool ready = EditorApplication.isPlaying && runtime != null && runtime.State != null;
        if (ready) {
            GUILayout.Label("HP " + runtime.State.currHp + " / " + runtime.State.maxHp + "    Combo " + runtime.State.combo);
            GUILayout.Label("Persistent callbacks: HP " + runtime.Readout.hpCallbacks + "    Combo " + runtime.Readout.comboCallbacks);
        }
        try {
            GUI.enabled = receipt.nextStep == 0 && !EditorApplication.isPlayingOrWillChangePlaymode;
            if (GUILayout.Button("1. Start source module flow", GUILayout.Height(40))) {
                Record("start-play", input, null); receipt.status = "playing"; Save(); EditorApplication.isPlaying = true;
            }
            GUI.enabled = ready && receipt.nextStep == 1;
            if (GUILayout.Button("2. Apply source damage -10", GUILayout.Height(40))) {
                runtime.State.DoDelta(-10d);
                if (runtime.State.currHp != 79d || runtime.Readout.hpCallbacks != 1 || runtime.Readout.lastHp != 79d) throw new InvalidOperationException("Damage/callback mismatch.");
                Record("damage", input, runtime);
            }
            GUI.enabled = ready && receipt.nextStep == 2;
            if (GUILayout.Button("3. Apply source healing +10", GUILayout.Height(40))) {
                runtime.State.DoDelta(10d);
                if (runtime.State.currHp != 89d || runtime.Readout.hpCallbacks != 2 || runtime.Readout.lastHp != 89d) throw new InvalidOperationException("Healing/callback mismatch.");
                Record("heal", input, runtime);
            }
            GUI.enabled = ready && receipt.nextStep == 3;
            if (GUILayout.Button("4. Apply source combo +1", GUILayout.Height(40))) {
                runtime.State.ComboDoDelta(1d);
                if (runtime.State.combo != 1d || runtime.Readout.comboCallbacks != 1 || runtime.Readout.lastCombo != 1d) throw new InvalidOperationException("Combo/callback mismatch.");
                Record("combo", input, runtime);
            }
            GUI.enabled = ready && receipt.nextStep == 4;
            if (GUILayout.Button("5. Query original JSON recipe 2015015", GUILayout.Height(40))) {
                var leaves = RecipeCatalog.FlattenIngredientsOf(2015015d);
                double[] expected = { 1010204d,1005303d,1007206d,1002401d,1007204d,1010201d,1004302d,1005203d,1010303d };
                if (leaves.Count != expected.Length) throw new InvalidOperationException("Recipe count mismatch.");
                for (int i = 0; i < expected.Length; i++) if (leaves[i] != expected[i]) throw new InvalidOperationException("Recipe order/value mismatch.");
                receipt.recipeLeaves = leaves.ToArray(); Record("query-recipe", input, runtime);
            }
            GUI.enabled = ready && receipt.nextStep == 5;
            if (GUILayout.Button("6. Stop and verify saved bindings", GUILayout.Height(40))) {
                Record("stop-and-reopen", input, runtime);
                var state = runtime.State; UnityEngine.Object.DestroyImmediate(runtime);
                if (state.onHpChange != null || state.onComboChange != null) throw new InvalidOperationException("Destroy retained subscriptions.");
                receipt.onDestroyUnsubscribed = true; receipt.status = "reopening"; Save(); EditorApplication.isPlaying = false;
            }
            GUI.enabled = true;
            if (receipt.recipeLeaves != null) GUILayout.Label("Recipe: " + String.Join(", ", receipt.recipeLeaves));
            if (receipt.actions.Count > 0) {
                var last = receipt.actions[receipt.actions.Count - 1];
                GUILayout.Label("Last pointer action: " + last.action + "    HP " + last.hp + "    Combo " + last.combo);
            }
            if (receipt.error != null) GUILayout.Label("Error: " + receipt.error);
            GUI.enabled = receipt.status == "passed" || receipt.status == "failed";
            if (GUILayout.Button("Close probe Editor", GUILayout.Height(30))) EditorApplication.Exit(receipt.status == "passed" ? 0 : 1);
        } catch (Exception e) { Fail(e); }
        finally { GUI.enabled = true; }
    }
}
'''.replace('__MANIFEST__', manifest)
