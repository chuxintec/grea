using System;
using System.IO;
using System.Linq;
using Grea.Foundation.Contracts;
using Numeric.Domain;
using Numeric.Gameplay;
namespace Numeric.Services
{
    // One authoring/persistence format per sample; the shared store owns the checksum envelope.
    public sealed class Persistence : IProgressStore
    {
        readonly ISaveStore store;
        public bool FailNextWrite { get; set; }
        public Persistence(ISaveStore store) { this.store = store; }
        public Progress Load()
        {
            var raw = store.Read(); if (raw == null) return new Progress();
            var parts = raw.Split('|');
            if (parts.Length != 5 || parts[0] != "numeric:1") throw new InvalidDataException("Unknown sample save version; original preserved");
            try { return new Progress(int.Parse(parts[1]), int.Parse(parts[2]), int.Parse(parts[3]), bool.Parse(parts[4])); }
            catch (Exception error) when (error is ArgumentException || error is FormatException || error is OverflowException)
            { throw new InvalidDataException("Invalid sample save; original preserved", error); }
        }
        public void Save(Progress value)
        {
            if (FailNextWrite) { FailNextWrite = false; throw new IOException("Synthetic QA write failure; state unchanged"); }
            store.Write("numeric:1|" + value.Coins + "|" + value.Level + "|" + value.Wins + "|" + value.PendingReward);
        }
    }
}
