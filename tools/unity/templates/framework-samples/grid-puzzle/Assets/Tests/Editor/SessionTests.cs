using System;
using System.IO;
using NUnit.Framework;
using Grea.Foundation.Contracts;
using Grea.Foundation.Runtime;
using Puzzle.Domain;
using Puzzle.Gameplay;
using Puzzle.Services;
namespace Puzzle.Tests
{
    public sealed class SessionTests
    {
        sealed class Memory : ISaveStore { public string Raw; public string Read() => Raw; public void Write(string value) { Raw=value; } }

        [Test] public void LegalMovesSolveOnceAndReopenRetainsBoard()
        {
            var memory=new Memory(); var persistence=new Persistence(memory); var session=new PuzzleSession(persistence);
            session.Select(5); Assert.IsTrue(session.MoveSelected()); Assert.IsFalse(session.Board.Solved);
            var reopened=new PuzzleSession(persistence); Assert.AreEqual(1,reopened.Board.Moves);
            reopened.Select(6); Assert.IsTrue(reopened.MoveSelected()); Assert.IsTrue(reopened.Board.Solved); Assert.AreEqual(1,reopened.Board.Wins);
            Assert.IsFalse(reopened.Select(5)); Assert.IsFalse(reopened.MoveSelected());
        }
        [Test] public void IllegalMoveAndCancelledSelectionNeverWrite()
        {
            var memory=new Memory(); var session=new PuzzleSession(new Persistence(memory));
            Assert.IsTrue(session.Select(1)); Assert.IsFalse(session.MoveSelected()); Assert.IsNull(memory.Raw);
            session.Select(5); session.CancelSelection(); Assert.IsFalse(session.MoveSelected()); Assert.AreEqual(0,session.Board.Moves);
        }
        [Test] public void FailedMoveOrResetPreservesBoardAndCanRetry()
        {
            var persistence=new Persistence(new Memory()); var session=new PuzzleSession(persistence); session.Select(5);
            persistence.FailNextWrite=true; Assert.Throws<IOException>(()=>session.MoveSelected()); Assert.AreEqual(0,session.Board.Moves);
            Assert.IsTrue(session.MoveSelected()); persistence.FailNextWrite=true;
            Assert.Throws<IOException>(()=>session.Reset()); Assert.AreEqual(1,session.Board.Moves);
            session.Reset(); Assert.AreEqual(0,session.Board.Moves); Assert.AreEqual(0,session.Selected);
        }
        [Test] public void DomainRejectsInvalidPermutationAndDoesNotExposeMutableCells()
        {
            Assert.Throws<ArgumentException>(()=>new Board(new[]{1,1,2}));
            var board=new Board(); var cells=board.Cells; cells[0]=8; Assert.AreEqual(1,board.Cells[0]);
            Assert.IsNull(board.Move(1)); Assert.IsNull(board.Move(0)); Assert.IsNotNull(board.Move(5));
        }

        [TestCase("future:2|0|1|0")] [TestCase("malformed")] [TestCase("puzzle:1|bad|1|0")]
        public void InvalidPayloadIsObservableAndPreserved(string raw)
        {
            var memory=new Memory {Raw=raw}; var persistence=new Persistence(memory);
            Assert.Throws<InvalidDataException>(()=>persistence.Load()); Assert.AreEqual(raw,memory.Raw);
        }
        [Test] public void IndependentFileStoreReopenUsesOnlyQaNamespace()
        {
            string root=Path.Combine(Path.GetTempPath(),"grea-sample-"+Guid.NewGuid().ToString("N"));
            try
            {
                var persistence=new Persistence(new FileSaveStore(root,"player","qa",true));
                var state=persistence.Load(); persistence.Save(state);
                Assert.IsNotNull(new Persistence(new FileSaveStore(root,"player","qa",true)).Load());
                Assert.IsFalse(Directory.Exists(Path.Combine(root,"player")));
                var path=Path.Combine(root,"qa","save.v1"); File.WriteAllText(path,"corrupt");
                Assert.Throws<InvalidDataException>(()=>persistence.Load()); Assert.AreEqual("corrupt",File.ReadAllText(path));
            }
            finally { if(Directory.Exists(root)) Directory.Delete(root,true); }
        }
    }
}
