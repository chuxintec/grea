using UnityEngine;

namespace Monkey.StaticSortQueueProxy
{
    [AddComponentMenu("")]
    public sealed class NativeStaticSortRootIdentity : MonoBehaviour
    {
        public string sourceId, nativeId;
        public bool enabledInSource;
    }
}
