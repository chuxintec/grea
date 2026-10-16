using System;
using System.Linq;
namespace Puzzle.Domain
{
    public sealed class Board
    {
        readonly int[] cells;
        public int Moves { get; }
        public int Wins { get; }
        public bool Solved => cells.SequenceEqual(new[] { 1,2,3,4,5,6,7,8,0 });
        public int[] Cells => (int[])cells.Clone();
        public Board(int[] cells = null, int moves = 0, int wins = 0)
        {
            this.cells = cells == null ? new[] { 1,2,3,4,0,5,7,8,6 } : (int[])cells.Clone();
            if (this.cells.Length != 9 || !this.cells.OrderBy(x => x).SequenceEqual(Enumerable.Range(0,9)) || moves < 0 || wins < 0)
                throw new ArgumentException("Invalid board payload");
            Moves = moves; Wins = wins;
        }
        public Board Move(int tile)
        {
            if (Solved || tile <= 0 || tile > 8) return null;
            int from = Array.IndexOf(cells, tile), empty = Array.IndexOf(cells, 0);
            if (Math.Abs(from / 3 - empty / 3) + Math.Abs(from % 3 - empty % 3) != 1) return null;
            var next = Cells; next[empty] = tile; next[from] = 0;
            bool solved = next.SequenceEqual(new[] { 1,2,3,4,5,6,7,8,0 });
            return new Board(next, checked(Moves + 1), checked(Wins + (solved ? 1 : 0)));
        }
    }
}
