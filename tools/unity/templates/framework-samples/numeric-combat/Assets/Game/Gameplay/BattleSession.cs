using Numeric.Domain;
namespace Numeric.Gameplay
{
    public interface IProgressStore { Progress Load(); void Save(Progress progress); }
    public sealed class BattleSession
    {
        readonly IProgressStore store;
        public Progress Progress { get; private set; }
        public BattlePhase Phase { get; private set; }
        public int EnemyHealth { get; private set; }
        public int Health { get; private set; }
        public BattleSession(IProgressStore store) { this.store = store; Progress = store.Load(); if (Progress.PendingReward) Phase = BattlePhase.Victory; }
        public bool Start()
        { if (Progress.PendingReward || (Phase != BattlePhase.Menu && Phase != BattlePhase.Victory && Phase != BattlePhase.Defeat)) return false;
          EnemyHealth = 12; Health = 3; Phase = BattlePhase.Fighting; return true; }
        public bool Attack()
        {
            if (Phase != BattlePhase.Fighting) return false;
            int next = System.Math.Max(0, EnemyHealth - (4 + Progress.Level));
            if (next == 0)
            {
                var progress = new Progress(Progress.Coins, Progress.Level, Progress.Wins, true);
                store.Save(progress); Progress = progress; Phase = BattlePhase.Victory;
            }
            else if (--Health == 0) Phase = BattlePhase.Defeat;
            EnemyHealth = next; return true;
        }
        public bool Pause() { if (Phase != BattlePhase.Fighting) return false; Phase = BattlePhase.Paused; return true; }
        public bool Resume() { if (Phase != BattlePhase.Paused) return false; Phase = BattlePhase.Fighting; return true; }
        public void ReturnToMenu() { Phase = BattlePhase.Menu; }
        public bool Claim()
        {
            if (!Progress.PendingReward) return false;
            var next = new Progress(checked(Progress.Coins + 5), Progress.Level, checked(Progress.Wins + 1));
            store.Save(next); Progress = next; return true;
        }
        public bool Upgrade()
        {
            if (Progress.PendingReward || Phase != BattlePhase.Menu || Progress.Coins < 5 || Progress.Level >= 100) return false;
            var next = new Progress(Progress.Coins - 5, Progress.Level + 1, Progress.Wins);
            store.Save(next); Progress = next; return true;
        }
    }
}
