using System.Threading.Tasks;
using Numeric.Gameplay;
using Numeric.Domain;
using Grea.Foundation.Contracts;
using Grea.UI.UGUI;
using UnityEngine;
using UnityEngine.UI;
namespace Numeric.Presentation
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
    public sealed class BattleView : SampleView
    {
        public Button start, attack, pause, upgrade, claim;
        BattleSession session;
        public void Initialize(BattleSession session, bool qa, System.Action fail)
        {
            this.session = session; host.bindOpenButton = false;
            Bind(start, () => { notice = session.Start() ? "Battle started" : "REJECTED: already running"; });
            Bind(attack, () => { notice = session.Attack() ? "Attack committed" : "REJECTED: not fighting"; });
            Bind(claim, () => { notice = session.Claim() ? "Reward claimed once" : "REJECTED: no pending reward"; });
            Bind(upgrade, () => { notice = session.Upgrade() ? "Upgrade saved" : "REJECTED: need menu, coins and level below 100"; });
            Bind(pause, () => { if (!session.Pause()) { notice = "REJECTED: not fighting"; return; }
                host.modal.Title.text = "PAUSED"; modalAction.gameObject.SetActive(true); host.modal.Open(lifetime); });
            Bind(modalAction, () => { session.ReturnToMenu(); host.modal.Close(); notice = "Cancelled battle: no reward"; });
            host.modal.CloseButton.onClick.AddListener(() => { session.Resume(); Render(); });
            failSave.gameObject.SetActive(qa); if (qa) Bind(failSave, () => { fail(); notice = "QA: next save will fail"; });
            Bind(quit, () => Application.Quit());
            host.events.firstSelectedGameObject = start.gameObject;
            host.events.SetSelectedGameObject(start.gameObject); Render();
        }
        protected override void Render()
        {
            if (session == null) return;
            status.text = session.Phase + " | COINS " + session.Progress.Coins + " | LV " + session.Progress.Level +
                " | WINS " + session.Progress.Wins + " | PENDING " + session.Progress.PendingReward + "\nENEMY " + session.EnemyHealth + " / HP " + session.Health + "\n" + notice;
        }
    }
}
