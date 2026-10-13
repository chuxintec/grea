using System;
using System.Collections.Generic;
using System.Threading;

namespace Grea.Foundation.Contracts
{
    // Main-thread owned. Invalidate first, then release in reverse acquisition order.
    public sealed class LifetimeScope : IDisposable
    {
        readonly CancellationTokenSource cancellation = new CancellationTokenSource();
        readonly List<IDisposable> owned = new List<IDisposable>();
        readonly LifetimeScope parent;
        bool disposed;
        public CancellationToken Token { get; }
        public bool IsAlive => !disposed && (parent == null || parent.IsAlive);
        public int OwnedCount => owned.Count;
        public LifetimeScope() { Token = cancellation.Token; }
        LifetimeScope(LifetimeScope parent) : this() { this.parent = parent; }
        public OperationStamp Capture(string operationId)
        {
            if (!IsAlive) throw new ObjectDisposedException(nameof(LifetimeScope));
            if (string.IsNullOrWhiteSpace(operationId)) throw new ArgumentException(nameof(operationId));
            return new OperationStamp(this, operationId);
        }
        public Lease<T> Own<T>(T value, Action<T> release)
        {
            if (!IsAlive) throw new ObjectDisposedException(nameof(LifetimeScope));
            if (release == null) throw new ArgumentNullException(nameof(release));
            Lease<T> lease = null;
            lease = new Lease<T>(value, v => { owned.Remove(lease); release(v); });
            owned.Add(lease);
            return lease;
        }
        public LifetimeScope CreateChild()
        {
            if (!IsAlive) throw new ObjectDisposedException(nameof(LifetimeScope));
            var child = new LifetimeScope(this);
            var link = Own(child, x => x.Dispose());
            child.Own(link, x => x.Dispose());
            return child;
        }
        public void Dispose()
        {
            if (disposed) return;
            disposed = true;
            var failures = new List<Exception>();
            try { cancellation.Cancel(); } catch (Exception e) { failures.Add(e); }
            var items = owned.ToArray();
            for (int i = items.Length - 1; i >= 0; i--)
                try { items[i].Dispose(); } catch (Exception e) { failures.Add(e); }
            owned.Clear();
            cancellation.Dispose();
            if (failures.Count != 0) throw new AggregateException(failures);
        }
    }

    public readonly struct OperationStamp
    {
        readonly LifetimeScope owner;
        public string OperationId { get; }
        public CancellationToken Token => owner == null ? new CancellationToken(true) : owner.Token;
        public bool IsCurrent => owner != null && owner.IsAlive;
        internal OperationStamp(LifetimeScope scope, string id) { owner = scope; OperationId = id; }
        public void ThrowIfStale() { if (!IsCurrent) throw new OperationCanceledException(Token); }
    }

    public sealed class Lease<T> : IDisposable
    {
        readonly T value;
        Action<T> release;
        public bool IsDisposed => release == null;
        public T Value => !IsDisposed ? value : throw new ObjectDisposedException(nameof(Lease<T>));
        internal Lease(T value, Action<T> release) { this.value = value; this.release = release; }
        public void Dispose()
        {
            var action = release;
            release = null;
            action?.Invoke(value);
        }
    }
}
