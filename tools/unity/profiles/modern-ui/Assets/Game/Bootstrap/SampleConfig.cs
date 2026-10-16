using ModernSample.Domain;
using UnityEngine;
namespace ModernSample.Bootstrap
{
    [CreateAssetMenu(menuName="Grea Samples/Modern Config")]
    public sealed class SampleConfig : ScriptableObject
    {
        public GameKind kind;
        [Min(1)] public int enemyHealth=100;
        [Min(1)] public int damage=17;
    }
}
