using System;
using Game.Gameplay;
using Game.Presentation;
using Game.Services;
using Grea.Foundation.Contracts;
using Grea.UI.UGUI;

namespace Game.Bootstrap
{
    // Seed sample only. A project supplies its scene bindings; no implicit singleton.
    public sealed class CounterComposition : IDisposable
    {
        readonly LifetimeScope lifetime = new LifetimeScope();
        public CounterSession Session { get; }
        public CounterComposition(ISaveStore store, CommandButton button = null)
        {
            try
            {
                Session = new CounterSession(new CounterPersistence(store));
                lifetime.Own(Session, x => x.Dispose()); Session.Start();
                if (button) lifetime.Own(new CounterPresenter(Session, button, lifetime), x => x.Dispose());
            }
            catch { lifetime.Dispose(); throw; }
        }
        public void Dispose() => lifetime.Dispose();
    }
}
