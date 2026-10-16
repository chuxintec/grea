using System;
namespace Numeric.Domain
{
    public sealed class Progress
    {
        public int Coins { get; }
        public int Level { get; }
        public int Wins { get; }
        public bool PendingReward { get; }
        public Progress(int coins = 10, int level = 1, int wins = 0, bool pendingReward = false)
        { if (coins < 0 || level < 1 || level > 100 || wins < 0) throw new ArgumentOutOfRangeException(); Coins = coins; Level = level; Wins = wins; PendingReward = pendingReward; }
    }
    public enum BattlePhase { Menu, Fighting, Paused, Victory, Defeat }
}
