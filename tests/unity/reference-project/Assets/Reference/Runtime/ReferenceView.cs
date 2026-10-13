using System;
using System.Threading.Tasks;
using Grea.Foundation.Contracts;
using Grea.Reference.Domain;
using Grea.UI.UGUI;
using UnityEngine;
using UnityEngine.UI;

namespace Grea.Reference
{
    public sealed class ReferenceView : MonoBehaviour
    {
        public GameObject menu, game, pause, result, error;
        public CommandButton startButton, targetButton, pauseButton, resumeButton, leaveButton, againButton, menuButton, quitButton;
        public Text scoreText, winsText, resultText, pauseText, errorText;
        public Image[] progress;
        LifetimeScope bindings;
        ReferenceApp app;
        Phase? lastPhase;
        static readonly Vector2[] Positions = { new Vector2(-250, 5), new Vector2(210, 60), new Vector2(-110, -130), new Vector2(260, -100), new Vector2(0, 70) };
        public void Validate()
        {
            if (!menu || !game || !pause || !result || !error || !startButton || !targetButton || !pauseButton || !resumeButton || !leaveButton ||
                !againButton || !menuButton || !quitButton || !scoreText || !winsText || !resultText || !pauseText || !errorText || progress == null || progress.Length != 5)
                throw new InvalidOperationException("ReferenceView binding is missing");
            foreach (var dot in progress) if (!dot) throw new InvalidOperationException("Progress binding is missing");
        }
        public void Bind(ReferenceApp owner) { app = owner; lastPhase = null; }
        void Action(CommandButton button, System.Action action) => button.Bind(bindings, _ => { action(); return Task.CompletedTask; });
        public void Render(SignalSession state, bool focusPaused)
        {
            if (lastPhase != state.Phase)
            {
                bindings?.Dispose(); bindings = new LifetimeScope(); lastPhase = state.Phase;
                menu.SetActive(state.Phase == Phase.Menu); game.SetActive(state.Phase == Phase.Playing || state.Phase == Phase.Paused);
                pause.SetActive(state.Phase == Phase.Paused); result.SetActive(state.Phase == Phase.Complete); error.SetActive(false);
                if (state.Phase == Phase.Menu) { Action(startButton, app.Begin); Action(quitButton, app.Quit); }
                if (state.Phase == Phase.Playing) { targetButton.Bind(bindings, _ => app.CollectAsync()); Action(pauseButton, app.Pause); }
                if (state.Phase == Phase.Paused) { Action(resumeButton, app.Resume); Action(leaveButton, app.Menu); }
                if (state.Phase == Phase.Complete) { Action(againButton, app.Begin); Action(menuButton, app.Menu); }
            }
            scoreText.text = "SIGNALS  " + state.Score + " / " + state.Goal;
            winsText.text = "RUNS COMPLETED  " + state.Wins;
            resultText.text = state.Score + " signals collected.  Total completed runs: " + state.Wins;
            pauseText.text = focusPaused ? "PAUSED / WINDOW LOST FOCUS" : "PAUSED";
            ((RectTransform)targetButton.transform).anchoredPosition = Positions[state.Score % Positions.Length];
            for (int i = 0; i < progress.Length; i++) progress[i].color = i < state.Score ? new Color(.25f, .95f, .75f) : new Color(.18f, .27f, .34f);
        }
        public void ShowError(string message)
        {
            bindings?.Dispose(); lastPhase = Phase.Faulted;
            if (menu) menu.SetActive(false); if (game) game.SetActive(false); if (pause) pause.SetActive(false); if (result) result.SetActive(false);
            if (error) error.SetActive(true); if (errorText) errorText.text = message;
        }
        void OnDestroy() => bindings?.Dispose();
    }
}
