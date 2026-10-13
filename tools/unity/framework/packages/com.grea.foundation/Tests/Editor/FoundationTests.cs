using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Grea.Foundation.Contracts;
using Grea.Foundation.Runtime;
using NUnit.Framework;
using UnityEngine;

namespace Grea.Tests
{
    public sealed class FoundationTests
    {
        sealed class Service : IAppService
        {
            readonly string id; readonly List<string> events;
            public Func<CancellationToken, Task> Init = _ => Task.CompletedTask;
            public bool FailDispose;
            public Service(string id, List<string> events) { this.id = id; this.events = events; }
            public Task InitializeAsync(CancellationToken token) { events.Add("start:" + id); return Init(token); }
            public void Dispose() { events.Add("stop:" + id); if (FailDispose) throw new InvalidOperationException(id); }
        }
        [Test] public void LifetimeReleasesReverseAndInvalidatesBeforeCleanup()
        {
            var scope = new LifetimeScope(); var stamp = scope.Capture("load"); var order = new List<int>();
            scope.Own(1, x => { Assert.IsFalse(stamp.IsCurrent); order.Add(x); }); scope.Own(2, order.Add);
            scope.Dispose(); scope.Dispose(); CollectionAssert.AreEqual(new[] { 2, 1 }, order);
            Assert.Throws<OperationCanceledException>(() => stamp.ThrowIfStale()); Assert.AreEqual(0, scope.OwnedCount);
        }
        [Test] public void LeaseDoubleReturnAndChildCleanupDoNotAccumulate()
        {
            using (var parent = new LifetimeScope())
            {
                for (int i = 0; i < 100; i++) { var child = parent.CreateChild(); child.Dispose(); }
                Assert.AreEqual(0, parent.OwnedCount);
                int released = 0; var lease = parent.Own(1, _ => released++); lease.Dispose(); lease.Dispose();
                Assert.AreEqual(1, released); Assert.Throws<ObjectDisposedException>(() => { var x = lease.Value; });
                var active = parent.CreateChild(); parent.Dispose(); Assert.IsFalse(active.IsAlive);
            }
        }
        [Test] public void CleanupContinuesAfterFailure()
        {
            var scope = new LifetimeScope(); int count = 0;
            scope.Own(0, _ => count++); scope.Own(1, _ => throw new Exception("failure"));
            Assert.Throws<AggregateException>(() => scope.Dispose()); Assert.AreEqual(1, count);
        }
        [Test] public async Task ServicesStartOnceAndStopReverse()
        {
            var events = new List<string>(); var scope = new ServiceScope(new Service("a", events), new Service("b", events));
            var first = scope.StartAsync(); Assert.AreSame(first, scope.StartAsync()); await first;
            Assert.AreEqual(ServiceState.Ready, scope.State); await scope.StopAsync(); await scope.StopAsync();
            CollectionAssert.AreEqual(new[] { "start:a", "start:b", "stop:b", "stop:a" }, events);
            Assert.Throws<InvalidOperationException>(() => scope.StartAsync());
        }
        [Test] public void FailedServiceCleansPartialAndSuccessfulServices()
        {
            var events = new List<string>(); var bad = new Service("b", events) { Init = _ => throw new Exception("init"), FailDispose = true };
            var scope = new ServiceScope(new Service("a", events), bad, new Service("c", events));
            Assert.ThrowsAsync<AggregateException>(async () => await scope.StartAsync());
            CollectionAssert.AreEqual(new[] { "start:a", "start:b", "stop:b", "stop:a" }, events);
            Assert.AreEqual(ServiceState.Faulted, scope.State);
            Assert.ThrowsAsync<AggregateException>(async () => await scope.StopAsync());
            Assert.AreEqual(ServiceState.Stopped, scope.State);
        }
        [Test] public async Task StopWaitsForInitializerAndRejectsLateSuccess()
        {
            var events = new List<string>(); var gate = new TaskCompletionSource<bool>(); CancellationToken token = default;
            var service = new Service("a", events) { Init = t => { token = t; return gate.Task; } };
            var scope = new ServiceScope(service); var start = scope.StartAsync(); var stop = scope.StopAsync();
            Assert.IsTrue(token.IsCancellationRequested); Assert.IsFalse(stop.IsCompleted); Assert.AreEqual(1, events.Count);
            gate.SetResult(true);
            try { await start; Assert.Fail(); } catch (OperationCanceledException) { }
            try { await stop; Assert.Fail(); } catch (AggregateException) { }
            CollectionAssert.AreEqual(new[] { "start:a", "stop:a" }, events);
        }
        [Test] public void DuplicateServiceRejected()
        { var s = new Service("a", new List<string>()); Assert.Throws<ArgumentException>(() => new ServiceScope(s, s)); }
        [Test] public void DiagnosticsAreBoundedAndCopied()
        {
            var sink = new DiagnosticBuffer(2);
            for (int i = 0; i < 3; i++) sink.Record(new DiagnosticEvent("ui", "op" + i, "CLOSED"));
            var snapshot = sink.Snapshot(); Assert.AreEqual(2, snapshot.Length); Assert.AreEqual("op1", snapshot[0].OperationId);
            snapshot[0] = null; Assert.IsNotNull(sink.Snapshot()[0]);
            Assert.Throws<ArgumentException>(() => new DiagnosticEvent("ui", "private/path", "error"));
        }
        [Test] public void CatalogTypeMissingAndDestroyedAssetsFailWithoutLeaking()
        {
            var go = new GameObject("owned-by-test");
            try
            {
                var catalog = new AssetCatalog(new Dictionary<string, UnityEngine.Object> { { "view", go } });
                using (var scope = new LifetimeScope())
                {
                    var a = catalog.Acquire<GameObject>("view", scope); catalog.Acquire<GameObject>("view", scope);
                    Assert.AreEqual(2, catalog.ReferenceCount("view")); a.Dispose(); Assert.AreEqual(1, catalog.ActiveHandles);
                    Assert.Throws<InvalidCastException>(() => catalog.Acquire<Texture>("view", scope));
                    Assert.Throws<KeyNotFoundException>(() => catalog.Acquire<GameObject>("missing", scope));
                }
                Assert.AreEqual(0, catalog.ActiveHandles); Assert.IsTrue(go);
                UnityEngine.Object.DestroyImmediate(go);
                using (var scope = new LifetimeScope()) Assert.Throws<MissingReferenceException>(() => catalog.Acquire<GameObject>("view", scope));
            }
            finally { if (go) UnityEngine.Object.DestroyImmediate(go); }
        }
        string root;
        [SetUp] public void Setup() { root = Path.Combine(Path.GetTempPath(), "grea-qa-" + Guid.NewGuid().ToString("N")); }
        [TearDown] public void Teardown() { if (Directory.Exists(root)) Directory.Delete(root, true); }
        [Test] public void SaveReopenBackupAndQaIsolation()
        {
            var store = new FileSaveStore(root, "player", "qa", true); Assert.IsNull(store.Read());
            store.Write("v1"); store.Write("v2");
            Assert.AreEqual("v2", new FileSaveStore(root, "player", "qa", true).Read()); Assert.AreEqual("v1", store.ReadBackup());
            Assert.IsNull(new FileSaveStore(root, "player", "qa", false).Read());
        }
        [Test] public void CorruptSaveAndInterruptedWritePreserveOriginal()
        {
            var store = new FileSaveStore(root, "player", "qa", true); store.Write("original");
            var path = Path.Combine(root, "qa", "save.v1"); var before = File.ReadAllBytes(path);
            File.WriteAllText(path + ".pending", "interrupted");
            Assert.Throws<IOException>(() => store.Write("next")); CollectionAssert.AreEqual(before, File.ReadAllBytes(path));
            File.WriteAllText(path, "bad"); Assert.Throws<InvalidDataException>(() => store.Read());
            Assert.Throws<InvalidDataException>(() => store.Write("default")); Assert.AreEqual("bad", File.ReadAllText(path));
        }
        [Test] public void SaveRejectsNamespaceAndPayloadErrors()
        {
            Assert.Throws<ArgumentException>(() => new FileSaveStore(root, "qa", "qa", true));
            Assert.Throws<ArgumentException>(() => new FileSaveStore(root, "player", "../qa", true));
            Assert.Throws<ArgumentException>(() => new FileSaveStore(root, "player", "con", true));
            var store = new FileSaveStore(root, "player", "qa", true);
            Assert.Throws<ArgumentException>(() => store.Write(new string('a', 1024 * 1024 + 1))); Assert.IsFalse(Directory.Exists(root));
        }
    }
}
