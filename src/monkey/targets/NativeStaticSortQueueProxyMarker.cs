using UnityEngine;
using UnityEngine.UI;

namespace Monkey.StaticSortQueueProxy
{
    [AddComponentMenu("")]
    public sealed class NativeStaticSortQueueProxyMarker : MonoBehaviour
    {
        public string kind, sourceNode, sourceComponentId, sourceType;
        public GameObject sourceRootOwner;
        public int queueIndex, maskType;
        public bool sourceInverted, generatedRootActiveBefore = true;
        public Component sourceComponent;
        public Graphic sourceGraphic;
        public bool sourceEnabled, sourceActive, sourceTextureBound, sourceTextEmpty, sourceFontMissing;
        public string sourceText, nativeTextExpectation, noDrawReason, sourceFieldsJson, sourceFieldsSha256, sourceDrawingCommands;
        public string[] sourceMaterialGuids;
        public bool sourceCommandsEmpty;
        public ProxySpineEmptyPoseOwner spineEmptyPoseOwnerProof;
    }
}
