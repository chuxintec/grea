using System;
using System.IO;
using Grea.Foundation.Contracts;
using Grea.Reference.Domain;
using NUnit.Framework;

namespace Grea.Reference.Tests
{
    public sealed class SignalSessionTests
    {
        sealed class Store : ISaveStore
        { public string Value; public bool Fail; public int Writes; public string Read()=>Value; public void Write(string value){if(Fail)throw new IOException();Value=value;Writes++;} }
        [Test] public void CompletePauseReturnReenterAndReload()
        {
            var store=new Store();var game=new SignalSession(5,store);
            Assert.IsFalse(game.Collect());Assert.IsTrue(game.Begin());Assert.IsFalse(game.Begin());game.Collect();game.Pause();
            Assert.IsFalse(game.Collect());Assert.AreEqual(1,game.Score);game.Resume();for(int i=0;i<4;i++)game.Collect();
            Assert.AreEqual(Phase.Complete,game.Phase);Assert.AreEqual(1,store.Writes);Assert.IsFalse(game.Collect());
            game.Return();game.Begin();Assert.AreEqual(0,game.Score);Assert.AreEqual(1,game.Wins);
            Assert.AreEqual(1,new SignalSession(5,store).Wins);game.Stop();Assert.IsFalse(game.Begin());Assert.IsFalse(game.Return());
        }
        [Test] public void FailedFinalSaveDoesNotAwardWinOrAdvanceScore()
        {
            var store=new Store{Fail=true};var game=new SignalSession(1,store);game.Begin();
            Assert.Throws<IOException>(()=>game.Collect());Assert.AreEqual(0,game.Score);Assert.AreEqual(0,game.Wins);Assert.AreEqual(0,store.Writes);
        }
        [TestCase("bad")] [TestCase("signal:2:8")] [TestCase("signal:1:-1")]
        public void InvalidSaveIsNeverReplaced(string data)
        {var store=new Store{Value=data};Assert.Throws<InvalidDataException>(()=>new SignalSession(5,store));Assert.AreEqual(data,store.Value);}
        [Test] public void InvalidConfigurationIsExplicit()
        {Assert.Throws<ArgumentOutOfRangeException>(()=>new SignalSession(0,new Store()));Assert.Throws<ArgumentNullException>(()=>new SignalSession(5,null));}
    }
}
