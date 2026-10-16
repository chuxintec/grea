using System;
using System.IO;
using Puzzle.Gameplay;
using Puzzle.Services;
using Puzzle.Presentation;
using Grea.Foundation.Runtime;
using UnityEngine;
using UnityEngine.UI;
namespace Puzzle.Bootstrap
{
    public sealed class SampleBootstrap : MonoBehaviour
    {
        public BootstrapConfig config;
        public PuzzleView view;
        void Start()
        {
            try
            {
                if (!config || !view) throw new InvalidOperationException("Explicit config and view bindings required");
                var args = Environment.GetCommandLineArgs(); int flag = Array.IndexOf(args, "--grea-qa-root");
                bool qa = Array.IndexOf(args, "--grea-qa") >= 0;
                if (qa != (flag >= 0) || (qa && (flag + 1 >= args.Length || !Path.IsPathRooted(args[flag + 1]))))
                    throw new InvalidOperationException("QA requires --grea-qa and an explicit absolute --grea-qa-root");
                string root = qa ? args[flag + 1] : Application.persistentDataPath;
                var persistence = new Persistence(new FileSaveStore(root, "grid-puzzle-player", "grid-puzzle-qa", qa));
                view.Initialize(new PuzzleSession(persistence), qa, () => persistence.FailNextWrite = true);
                Debug.Log("SAMPLE_READY grid-puzzle " + (qa ? "qa" : "player"));
            }
            catch (Exception error)
            {
                if (view && view.status) view.status.text = "LOAD ERROR: " + error.Message + "\nOriginal save preserved. Exit and inspect; no automatic reset.";
                if (view && view.quit) view.quit.onClick.AddListener(() => Application.Quit());
                Debug.LogError("SAMPLE_LOAD_FAILED " + error.GetType().Name);
            }
        }
    }
}
