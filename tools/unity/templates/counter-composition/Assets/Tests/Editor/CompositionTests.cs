using System;
using System.IO;
using Game.Bootstrap;
using Game.Gameplay;
using Grea.Foundation.Contracts;
using NUnit.Framework;

namespace Game.Tests
{
    public sealed class CompositionTests
    {
        sealed class Store : ISaveStore
        { public string Value; public bool Fail; public string Read() => Value; public void Write(string value) { if (Fail) throw new IOException(); Value = value; } }
        [Test] public void SessionPauseExitAndNewSessionReloadState()
        {
            var store = new Store();
            using (var app = new CounterComposition(store))
            {
                app.Session.Increment(); app.Session.Pause(); Assert.Throws<InvalidOperationException>(() => app.Session.Increment());
                app.Session.Resume(); app.Session.Increment(); Assert.AreEqual(2, app.Session.Value.Value);
                app.Dispose(); Assert.Throws<InvalidOperationException>(() => app.Session.Increment());
            }
            using (var second = new CounterComposition(store)) Assert.AreEqual(2, second.Session.Value.Value);
        }
        [Test] public void FailedPersistenceDoesNotCommitRuntimeState()
        {
            var store = new Store { Fail = true };
            using (var app = new CounterComposition(store))
            { Assert.Throws<IOException>(() => app.Session.Increment()); Assert.AreEqual(0, app.Session.Value.Value); }
        }
        [Test] public void UnknownDtoIsNotSilentlyReset()
        { var store = new Store { Value = "counter:2:10" }; Assert.Throws<InvalidDataException>(() => new CounterComposition(store)); Assert.AreEqual("counter:2:10", store.Value); }
    }
}
