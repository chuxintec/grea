using System;
using System.IO;
using NUnit.Framework;
using Grea.Foundation.Contracts;
using Grea.Foundation.Runtime;
using Numeric.Domain;
using Numeric.Gameplay;
using Numeric.Services;
namespace Numeric.Tests
{
    public sealed class SessionTests
    {
        sealed class Memory : ISaveStore { public string Raw; public string Read() => Raw; public void Write(string value) { Raw=value; } }

        [Test] public void VictoryAwardsOnceAndReopenRetainsProgress()
        {
            var memory=new Memory(); var persistence=new Persistence(memory); var session=new BattleSession(persistence);
            Assert.IsTrue(session.Start()); Assert.IsFalse(session.Start());
            Assert.IsTrue(session.Attack()); Assert.IsTrue(session.Attack()); Assert.IsTrue(session.Attack());
            Assert.AreEqual(BattlePhase.Victory,session.Phase); Assert.AreEqual(10,session.Progress.Coins); Assert.IsTrue(session.Progress.PendingReward);
            var reopened=new BattleSession(persistence); Assert.IsFalse(reopened.Start()); Assert.IsTrue(reopened.Claim());
            Assert.IsFalse(reopened.Claim()); Assert.AreEqual(15,reopened.Progress.Coins);
            Assert.IsFalse(session.Attack()); Assert.AreEqual(1,new BattleSession(persistence).Progress.Wins);
        }
        [Test] public void PauseCancelAndReentryDoNotSettleIncompleteBattle()
        {
            var session=new BattleSession(new Persistence(new Memory())); session.Start(); session.Attack();
            Assert.IsTrue(session.Pause()); Assert.IsFalse(session.Attack()); Assert.IsTrue(session.Resume());
            session.Pause(); session.ReturnToMenu(); Assert.IsFalse(session.Resume());
            Assert.AreEqual(10,session.Progress.Coins); Assert.IsTrue(session.Start()); Assert.AreEqual(12,session.EnemyHealth);
        }
        [Test] public void UpgradeSaveFailureDoesNotCommitAndCanRetry()
        {
            var persistence=new Persistence(new Memory()); var session=new BattleSession(persistence);
            persistence.FailNextWrite=true; Assert.Throws<IOException>(()=>session.Upgrade());
            Assert.AreEqual(10,session.Progress.Coins); Assert.AreEqual(1,session.Progress.Level);
            Assert.IsTrue(session.Upgrade()); Assert.AreEqual(5,session.Progress.Coins); Assert.AreEqual(2,new BattleSession(persistence).Progress.Level);
            session.Start(); Assert.IsFalse(session.Upgrade());
        }
        [Test] public void SettlementFailurePreservesLastDamageAndDoesNotDuplicateReward()
        {
            var persistence=new Persistence(new Memory()); var session=new BattleSession(persistence); session.Start(); session.Attack(); session.Attack();
            persistence.FailNextWrite=true; Assert.Throws<IOException>(()=>session.Attack());
            Assert.AreEqual(2,session.EnemyHealth); Assert.AreEqual(BattlePhase.Fighting,session.Phase); Assert.AreEqual(0,session.Progress.Wins);
            session.Attack(); Assert.IsTrue(session.Progress.PendingReward);
            persistence.FailNextWrite=true; Assert.Throws<IOException>(()=>session.Claim()); Assert.AreEqual(0,session.Progress.Wins);
            Assert.IsTrue(new BattleSession(persistence).Progress.PendingReward); session.Claim(); Assert.AreEqual(1,session.Progress.Wins); Assert.IsFalse(session.Attack());
        }

        [TestCase("future:2|0|1|0")] [TestCase("malformed")] [TestCase("numeric:1|bad|1|0")]
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
