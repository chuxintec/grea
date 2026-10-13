using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace Grea.Foundation.Contracts
{
    public sealed class DiagnosticEvent
    {
        public string Module { get; }
        public string OperationId { get; }
        public string Code { get; }
        public DiagnosticEvent(string module, string operationId, string code)
        { Module = Check(module); OperationId = Check(operationId); Code = Check(code); }
        static string Check(string value)
        {
            if (value == null || !Regex.IsMatch(value, @"\A[A-Za-z0-9_.:-]{1,80}\z"))
                throw new ArgumentException("Use a bounded technical identifier, not user data");
            return value;
        }
    }
    public sealed class DiagnosticBuffer
    {
        readonly Queue<DiagnosticEvent> events = new Queue<DiagnosticEvent>();
        readonly int capacity;
        public DiagnosticBuffer(int capacity = 128)
        { if (capacity < 1 || capacity > 4096) throw new ArgumentOutOfRangeException(nameof(capacity)); this.capacity = capacity; }
        public void Record(DiagnosticEvent entry)
        {
            if (entry == null) throw new ArgumentNullException(nameof(entry));
            if (events.Count == capacity) events.Dequeue();
            events.Enqueue(entry);
        }
        public DiagnosticEvent[] Snapshot() => events.ToArray();
    }
    public interface IGameClock { double Seconds { get; } }
    public interface ISaveStore { string Read(); void Write(string value); }
    public interface IPlatformInfo { string Platform { get; } bool HasFocus { get; } }
}
