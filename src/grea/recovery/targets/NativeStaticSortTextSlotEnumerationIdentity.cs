using TMPro;
using UnityEngine;

namespace Monkey.StaticSortQueueProxy
{
    /// <summary>Persist typed TMP slot evidence when an exact empty source label draws no proxy mesh.</summary>
    [AddComponentMenu("")]
    [DisallowMultipleComponent]
    public sealed class NativeStaticSortTextSlotEnumerationIdentity : MonoBehaviour
    {
        public TMP_Text sourceOwner;
        public string sourceComponentId;
        public NativeStaticSortTextSlotEnumeration slotEnumeration;
    }
}
