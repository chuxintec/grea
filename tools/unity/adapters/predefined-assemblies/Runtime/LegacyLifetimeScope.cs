using System;
using System.Threading;
using Grea.Foundation.Contracts;

namespace Grea.Adapters.Predefined
{
    // Only this opt-in facade is auto-referenced. The core keeps explicit dependencies.
    // Expose BCL types so Assembly-CSharp does not need a direct Contracts reference.
    public sealed class LegacyLifetimeScope : IDisposable
    {
        readonly LifetimeScope scope;
        public LegacyLifetimeScope() : this(new LifetimeScope()) { }
        LegacyLifetimeScope(LifetimeScope scope) { this.scope = scope; }
        public bool IsAlive => scope.IsAlive;
        public int OwnedCount => scope.OwnedCount;
        public CancellationToken Token => scope.Token;
        public LegacyLifetimeScope CreateChild() => new LegacyLifetimeScope(scope.CreateChild());
        public IDisposable Own<T>(T value, Action<T> release) => scope.Own(value, release);
        public void Dispose() => scope.Dispose();
    }
}
