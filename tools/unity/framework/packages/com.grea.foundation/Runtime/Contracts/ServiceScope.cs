using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace Grea.Foundation.Contracts
{
    public interface IAppService : IDisposable
    {
        // Dispose must handle partial initialization. Work must honor cancellation.
        Task InitializeAsync(CancellationToken cancellation);
    }
    public enum ServiceState { Created, Initializing, Ready, Stopping, Stopped, Faulted }
    public sealed class ServiceScope
    {
        readonly IAppService[] services;
        readonly List<IAppService> entered = new List<IAppService>();
        readonly CancellationTokenSource cancellation = new CancellationTokenSource();
        Task start, stop;
        public ServiceState State { get; private set; } = ServiceState.Created;
        public ServiceScope(params IAppService[] services)
        {
            this.services = (IAppService[])(services ?? throw new ArgumentNullException(nameof(services))).Clone();
            var unique = new HashSet<IAppService>();
            foreach (var service in this.services)
                if (service == null || !unique.Add(service)) throw new ArgumentException("Null or duplicate service");
        }
        public Task StartAsync()
        {
            if (State == ServiceState.Stopping || State == ServiceState.Stopped)
                throw new InvalidOperationException("Scope is stopping or stopped");
            // State is set before callbacks; synchronous reentry is rejected.
            if (start == null && State != ServiceState.Created) throw new InvalidOperationException("Reentrant initialization");
            return start ?? (start = Initialize());
        }
        async Task Initialize()
        {
            State = ServiceState.Initializing;
            try
            {
                foreach (var service in services)
                {
                    cancellation.Token.ThrowIfCancellationRequested();
                    entered.Add(service);
                    await service.InitializeAsync(cancellation.Token);
                    cancellation.Token.ThrowIfCancellationRequested();
                }
                State = ServiceState.Ready;
            }
            catch (Exception original)
            {
                State = ServiceState.Faulted;
                var errors = Release();
                if (errors.Count != 0) { errors.Insert(0, original); throw new AggregateException(errors); }
                throw;
            }
        }
        public Task StopAsync()
        {
            if (stop != null) return stop;
            if (State == ServiceState.Stopping) throw new InvalidOperationException("Reentrant shutdown");
            if (State == ServiceState.Initializing && start == null)
                throw new InvalidOperationException("Stop from initializer before StartAsync returns");
            return stop = Stop();
        }
        async Task Stop()
        {
            State = ServiceState.Stopping;
            var errors = new List<Exception>();
            try { cancellation.Cancel(); } catch (Exception e) { errors.Add(e); }
            // Do not dispose services under an initializer that is still executing.
            if (start != null) try { await start; } catch (Exception e) { errors.Add(e); }
            errors.AddRange(Release());
            cancellation.Dispose();
            State = ServiceState.Stopped;
            if (errors.Count != 0) throw new AggregateException(errors);
        }
        List<Exception> Release()
        {
            var errors = new List<Exception>();
            for (int i = entered.Count - 1; i >= 0; i--)
                try { entered[i].Dispose(); } catch (Exception e) { errors.Add(e); }
            entered.Clear();
            return errors;
        }
    }
}
