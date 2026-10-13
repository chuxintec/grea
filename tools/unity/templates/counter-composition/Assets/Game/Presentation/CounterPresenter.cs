using System;
using System.Threading.Tasks;
using Game.Gameplay;
using Grea.Foundation.Contracts;
using Grea.UI.UGUI;

namespace Game.Presentation
{
    public sealed class CounterPresenter : IDisposable
    {
        readonly LifetimeScope scope;
        public CounterPresenter(CounterSession session, CommandButton button, LifetimeScope parent)
        {
            if (session == null) throw new ArgumentNullException(nameof(session));
            if (!button) throw new ArgumentNullException(nameof(button));
            scope = parent.CreateChild();
            try { button.Bind(scope, stamp => { stamp.ThrowIfStale(); session.Increment(); return Task.CompletedTask; }); }
            catch { scope.Dispose(); throw; }
        }
        public void Dispose() => scope.Dispose();
    }
}
