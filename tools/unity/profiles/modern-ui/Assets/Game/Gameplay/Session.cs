using ModernSample.Domain;
namespace ModernSample.Gameplay
{
    public sealed class Session
    {
        readonly IProgressStore store;
        public Progress Progress { get; private set; }
        public GameKind Kind { get; }
        public int InitialHealth { get; }
        public int Damage { get; }
        public Session(IProgressStore store, GameKind kind, int health, int damage)
        { this.store=store;Kind=kind;InitialHealth=health;Damage=damage;Progress=store.Read(); }
        public void Act()
        { var next=new Progress(Progress.Actions+1);store.Write(next);Progress=next; }
        public int EnemyHealth => System.Math.Max(0, InitialHealth-Progress.Actions*Damage);
        // Two legal configurations of a two-cell puzzle; each move swaps tile and empty cell.
        public bool TileAtLeft => Progress.Actions%2==0;
    }
}
