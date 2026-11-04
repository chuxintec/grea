using UnityEngine;

namespace Monkey.StaticMaskSort
{
    /// <summary>Source identity and static values retained beside Unity's native Mask.</summary>
    [AddComponentMenu("")]
    public sealed class NativeStaticMaskIdentity : MonoBehaviour
    {
        public string sourceId, nativeId, sourceFieldsJson, spriteFrameUuid;
        public string sourceMaterialId, resolvedSourceMaterialId, sourceEffectId, sourceEffectName, sourceEffectDocumentSha256;
        public int sourceMaskType;
        public float sourceAlphaThreshold;
        public bool sourceInverted;
    }
}
