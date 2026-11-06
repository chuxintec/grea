using UnityEngine;

// A persistent carrier for the serialized source component. This component is
// deliberately disabled and has no renderer or source behavior implementation.
public sealed class NativeStaticSpineReference : MonoBehaviour
{
    public string sourceComponentId;
    public string sourceTemplateComponentId;
    public string sourcePrefabId;
    public string sourceNodeId;
    public string sourceTemplateNodeId;
    public bool sourceComponentEnabled;
    public bool sourceComponentEnabledKnown;
    public NativeStaticSpineData sourceData;
    public bool hasDefaultSkin; public string defaultSkin;
    public bool hasSkinName; public string skinName;
    public bool hasAnimationName; public string animationName;
    public bool hasDefaultAnimation; public string defaultAnimation;
    public bool hasLoop; public bool loop;
    public bool hasPlayTimes; public float playTimes;
    public bool hasTimeScale; public float timeScale;
    public bool hasPremultipliedAlpha; public bool premultipliedAlpha;
    public bool hasUseTint; public bool useTint;
    public bool hasDebugSlots; public bool debugSlots;
    public bool hasDebugBones; public bool debugBones;
    public bool hasDebugMesh; public bool debugMesh;
    public bool hasPreCacheMode; public int preCacheMode;
    public bool hasEnableBatch; public bool enableBatch;
    public string sourceFieldsJson;
    public string sourceFieldsSha256;
    public string sourceComponentEnvelopeJson;
    public string sourceComponentEnvelopeSha256;
    public string sourceNodeEnvelopeJson;
    public string sourceNodeEnvelopeSha256;
    public string sourceObjectReferencesJson;
    public string sourceObjectReferencesSha256;
    public string[] sourceObjectReferencePaths;
    public string[] sourceObjectReferenceIds;
    public string[] sourceObjectReferenceUuids;
    public UnityEngine.Object[] sourceObjectReferences;
    public NativeRetainedMaterial[] sourceMaterials;
    public bool nonRendering = true;
    public bool dynamicBehaviorRestored;
}
