using Puzzle.Domain;
namespace Puzzle.Gameplay
{
    public interface IBoardStore { Board Load(); void Save(Board board); }
    public sealed class PuzzleSession
    {
        readonly IBoardStore store;
        public Board Board { get; private set; }
        public int Selected { get; private set; }
        public PuzzleSession(IBoardStore store) { this.store = store; Board = store.Load(); }
        public bool Select(int tile) { if (tile < 1 || tile > 8 || Board.Solved) return false; Selected = tile; return true; }
        public bool MoveSelected()
        {
            var next = Board.Move(Selected); if (next == null) return false;
            store.Save(next); Board = next; Selected = 0; return true;
        }
        public void CancelSelection() { Selected = 0; }
        public void Reset() { var next = new Board(wins: Board.Wins); store.Save(next); Board = next; Selected = 0; }
    }
}
