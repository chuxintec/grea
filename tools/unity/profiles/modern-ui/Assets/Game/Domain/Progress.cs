using System;
namespace ModernSample.Domain
{
    public enum GameKind { Combat, Puzzle }
    public sealed class Progress
    {
        public int Actions { get; }
        public Progress(int actions=0) { if(actions<0 || actions>100000) throw new ArgumentOutOfRangeException(nameof(actions));Actions=actions; }
    }
    public interface IProgressStore { Progress Read(); void Write(Progress value); }
}
