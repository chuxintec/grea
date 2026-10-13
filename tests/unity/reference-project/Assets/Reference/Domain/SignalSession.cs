using System;
using System.Globalization;
using System.IO;
using Grea.Foundation.Contracts;

namespace Grea.Reference.Domain
{
    public enum Phase { Menu, Playing, Paused, Complete, Faulted, Stopped }
    // The session owns rules and commits persistence; views only send commands.
    public sealed class SignalSession
    {
        readonly ISaveStore store;
        public int Goal { get; }
        public int Score { get; private set; }
        public int Wins { get; private set; }
        public Phase Phase { get; private set; } = Phase.Menu;
        public SignalSession(int goal, ISaveStore store)
        {
            if (goal < 1 || goal > 20) throw new ArgumentOutOfRangeException(nameof(goal));
            this.store = store ?? throw new ArgumentNullException(nameof(store)); Goal = goal;
            string dto = store.Read();
            if (dto != null)
            {
                if (!dto.StartsWith("signal:1:", StringComparison.Ordinal) ||
                    !int.TryParse(dto.Substring(9), NumberStyles.None, CultureInfo.InvariantCulture, out int wins))
                    throw new InvalidDataException("Unknown or damaged save; retained for recovery");
                Wins = wins;
            }
        }
        public bool Begin()
        { if (Phase != Phase.Menu && Phase != Phase.Complete) return false; Score = 0; Phase = Phase.Playing; return true; }
        public bool Collect()
        {
            if (Phase != Phase.Playing) return false;
            int next = Score + 1;
            if (next == Goal)
            {
                int wins = checked(Wins + 1);
                store.Write("signal:1:" + wins.ToString(CultureInfo.InvariantCulture));
                Wins = wins; Phase = Phase.Complete;
            }
            Score = next; return true;
        }
        public bool Pause() { if (Phase != Phase.Playing) return false; Phase = Phase.Paused; return true; }
        public bool Resume() { if (Phase != Phase.Paused) return false; Phase = Phase.Playing; return true; }
        public bool Return() { if (Phase == Phase.Stopped || Phase == Phase.Faulted) return false; Phase = Phase.Menu; Score = 0; return true; }
        public void Fail() => Phase = Phase.Faulted;
        public void Stop() => Phase = Phase.Stopped;
    }
}
