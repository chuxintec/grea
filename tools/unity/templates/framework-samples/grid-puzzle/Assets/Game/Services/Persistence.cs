using System;
using System.IO;
using System.Linq;
using Grea.Foundation.Contracts;
using Puzzle.Domain;
using Puzzle.Gameplay;
namespace Puzzle.Services
{
    // One authoring/persistence format per sample; the shared store owns the checksum envelope.
    public sealed class Persistence : IBoardStore
    {
        readonly ISaveStore store;
        public bool FailNextWrite { get; set; }
        public Persistence(ISaveStore store) { this.store = store; }
        public Board Load()
        {
            var raw = store.Read(); if (raw == null) return new Board();
            var parts = raw.Split('|');
            if (parts.Length != 4 || parts[0] != "puzzle:1") throw new InvalidDataException("Unknown sample save version; original preserved");
            try { return new Board(parts[1].Split(',').Select(int.Parse).ToArray(), int.Parse(parts[2]), int.Parse(parts[3])); }
            catch (Exception error) when (error is ArgumentException || error is FormatException || error is OverflowException)
            { throw new InvalidDataException("Invalid sample save; original preserved", error); }
        }
        public void Save(Board value)
        {
            if (FailNextWrite) { FailNextWrite = false; throw new IOException("Synthetic QA write failure; state unchanged"); }
            store.Write("puzzle:1|" + string.Join(",", value.Cells) + "|" + value.Moves + "|" + value.Wins);
        }
    }
}
