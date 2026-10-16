using System.Threading.Tasks;
using Puzzle.Gameplay;
using Grea.Foundation.Contracts;
using Grea.UI.UGUI;
using UnityEngine;
using UnityEngine.UI;
namespace Puzzle.Presentation
{
    public abstract class SampleView : MonoBehaviour
    {

        public UIHost host;
        public Text status;
        public Button quit;
        public Button failSave;
        public Button modalAction;
        protected readonly LifetimeScope lifetime = new LifetimeScope();
        protected string notice = "";
        protected void Bind(Button button, System.Action action)
        {
            button.GetComponent<CommandButton>().Bind(lifetime, stamp => {
                stamp.ThrowIfStale();
                try { action(); }
                catch (System.Exception error) { notice = "SAVE ERROR: " + error.Message; OpenError(); }
                Render(); Debug.Log("SAMPLE_STATE " + status.text.Replace("\n", " | ")); return Task.CompletedTask;
            });
        }
        protected void OpenError() { host.modal.Close(); host.modal.Title.text = "SAVE ERROR"; modalAction.gameObject.SetActive(false); host.modal.Open(lifetime); }
        protected abstract void Render();
        void OnDestroy() { lifetime.Dispose(); }

    }
    public sealed class PuzzleView : SampleView
    {
        public Button[] tiles;
        public Button move, reset, cancel;
        PuzzleSession session;
        public void Initialize(PuzzleSession session, bool qa, System.Action fail)
        {
            this.session = session; host.bindOpenButton = false;
            for (int index = 0; index < tiles.Length; index++)
            {
                int slot = index; Bind(tiles[index], () => { var tile = session.Board.Cells[slot]; notice = session.Select(tile) ? "Selected " + tile : "REJECTED: empty or solved"; });
            }
            Bind(move, () => { notice = session.MoveSelected() ? "Move saved" : "REJECTED: select adjacent tile"; });
            Bind(cancel, () => { session.CancelSelection(); notice = "Selection cancelled"; });
            Bind(reset, () => { host.modal.Title.text = "RESET BOARD?"; modalAction.gameObject.SetActive(true); host.modal.Open(lifetime); });
            Bind(modalAction, () => { session.Reset(); host.modal.Close(); notice = "Reset saved"; });
            failSave.gameObject.SetActive(qa); if (qa) Bind(failSave, () => { fail(); notice = "QA: next save will fail"; });
            Bind(quit, () => Application.Quit());
            host.events.firstSelectedGameObject = tiles[0].gameObject;
            host.events.SetSelectedGameObject(tiles[0].gameObject); Render();
        }
        protected override void Render()
        {
            if (session == null) return;
            var cells = session.Board.Cells;
            for (int i = 0; i < cells.Length; i++) tiles[i].GetComponentInChildren<Text>(true).text = cells[i] == 0 ? "-" : cells[i].ToString();
            status.text = (session.Board.Solved ? "SOLVED" : "SLIDE PUZZLE") + " | MOVES " + session.Board.Moves + " | WINS " + session.Board.Wins +
                "\nSELECTED " + session.Selected + "\n" + notice;
        }
    }
}
