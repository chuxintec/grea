using UnityEngine;

namespace Monkey.StaticSortQueueProxy
{
    [AddComponentMenu("")]
    public sealed class NativeStaticSortOrderIdentity : MonoBehaviour
    {
        public string sourceId, nativeId;
        public float sourceSortOrder;
        public bool enabledInSource;
    }
}
