using System;
using Game.Domain;

namespace Game.Gameplay
{
    public interface ICounterPersistence { CounterState Load(); void Save(CounterState value); }
    public enum SessionState { Created, Running, Paused, Stopped }
    public sealed class CounterSession : IDisposable
    {
        readonly ICounterPersistence store;
        public CounterState Value { get; private set; }
        public SessionState State { get; private set; }
        public CounterSession(ICounterPersistence store) { this.store = store ?? throw new ArgumentNullException(nameof(store)); }
        public void Start()
        {
            if (State == SessionState.Running) return;
            if (State != SessionState.Created) throw new InvalidOperationException("Session cannot restart");
            Value = store.Load(); State = SessionState.Running;
        }
        public void Increment()
        {
            if (State != SessionState.Running) throw new InvalidOperationException("Session is not running");
            var next = Value.Next(); store.Save(next); Value = next;
        }
        public void Pause() { if (State != SessionState.Running) throw new InvalidOperationException(); State = SessionState.Paused; }
        public void Resume() { if (State != SessionState.Paused) throw new InvalidOperationException(); State = SessionState.Running; }
        public void Dispose() { State = SessionState.Stopped; }
    }
}
