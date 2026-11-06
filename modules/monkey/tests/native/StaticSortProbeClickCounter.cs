#if UNITY_EDITOR
using UnityEngine;

namespace Monkey.Tests
{
    public sealed class StaticSortProbeClickCounter : MonoBehaviour
    {
        public int clicks;
        public void Increment() { clicks++; }
    }
}
#endif
