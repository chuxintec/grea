using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.UI;

namespace Monkey.StaticSortQueueProxy
{
    [Serializable] public sealed class ProxyMaskBinding
    {
        public string sourceId, sourceNode;
        public Component sourceMask;
        public Mask proxyMask;
    }

    [Serializable] public sealed class ProxyGraphicBinding
    {
        public Graphic sourceGraphic;
        public CanvasRenderer sourceCanvasRenderer;
        public NativeStaticSortQueueProxyGraphic[] proxyGraphics;
        public bool sourceGraphicEnabled;
        public bool sourceCanvasCullBefore;
    }

    /// <summary>
    /// Persistent proof that a zero-geometry SkeletonGraphic owner delegates
    /// its fixed-state draw to the exact CanvasRenderers registered by Spine.
    /// The object references are serialized with the proxy presenter so the
    /// Editor can validate the source/child relation after save and reload.
    /// </summary>
    [Serializable] public sealed class ProxySpineOwnerDelegation
    {
        public string sourceComponentId, sourceNode, sourceDataAssetId, sourceDataAssetPath, sourceDataAssetGuid,
            sourceBindingPlanPath, sourceBindingPlanSha256, sourceManifestSha256;
        public Graphic sourceOwnerGraphic;
        public UnityEngine.Object sourceDataAssetReference;
        public Graphic[] delegatedSourceGraphics = Array.Empty<Graphic>();
        public CanvasRenderer[] delegatedCanvasRenderers = Array.Empty<CanvasRenderer>();
        public string[] delegatedChildPaths = Array.Empty<string>();
        public string[] delegatedChildMaterialGuids = Array.Empty<string>();
        public string[] delegatedChildTextureGuids = Array.Empty<string>();
        public int rootMeshVertexCount, rootMeshSubmeshCount, rootCanvasMaterialCount;
        public bool rootMeshWasMissing;
        public int[] childMeshVertexCounts = Array.Empty<int>();
        public int[] childMeshSubmeshCounts = Array.Empty<int>();
        public int[] childCanvasMaterialCounts = Array.Empty<int>();
    }

    /// <summary>Typed evidence for registered Spine child Graphics under a no-draw source owner.</summary>
    [Serializable] public sealed class ProxySpineNonDrawChild
    {
        public string sourceComponentId, sourceNode, noDrawReason, sourceDataAssetId, sourceDataAssetPath,
            sourceDataAssetGuid, childPath, childMaterialGuid, childTextureGuid;
        public Graphic sourceOwnerGraphic, sourceChildGraphic;
        public CanvasRenderer sourceChildCanvasRenderer;
        public UnityEngine.Object sourceDataAssetReference;
        public bool sourceOwnerEnabled, sourceNodeActive, sourceChildEnabled, sourceChildActiveSelf,
            sourceChildActiveInHierarchy, targetChildEnabled, targetChildActiveInHierarchy;
        public bool ownerOnlyNoRegisteredChildren, ownerRendererListReadable, ownerRendererListEmpty, ownerRootMeshEmpty;
        public int sourceChildMeshVertexCount, sourceChildMeshSubmeshCount, sourceChildMaterialCount;
        public int ownerRootMeshVertexCount, ownerRootMeshSubmeshCount, ownerRootMeshIndexCount, ownerRootCanvasMaterialCount;
        public string ownerRootMeshSha256;
    }

    /// <summary>Typed evidence for a Spine owner whose pinned source has no SkeletonData reference.</summary>
    [Serializable] public sealed class ProxySpineNullDataOwner
    {
        public string sourceComponentId, sourceNode, sourceStaticDataState, sourceBindingPlanPath,
            sourceBindingPlanSha256, sourceManifestSha256, sourceMaterialClosureStatus,
            sourceTargetFieldsJson, expectedFieldsJson, actualFieldsJson, rootMaterialEvidence, rootMeshSha256,
            rootMeshGeometryEvidence;
        public Graphic sourceOwnerGraphic;
        public bool sourceHasStaticDataReference, sourceDataAssetIdNull, sourcePlanVerified,
            sourceIdentityVerified, sourceNodeInactive, sourceNodeActive, sourceOwnerEnabled,
            sourceSerializedActive, sourceSerializedActiveVerified,
            nativeDataReferenceNull, nativeRootMeshEmpty, nativeRootMeshDefaultGraphicQuad, rootCanvasDefaultMaterialOnly,
            rootSourceBaseDefaultMaterial, rootMaterialSlotMatchesGraphicRendering,
            registeredRendererListEmpty, mappedStaticFieldsVerified, sourceBehaviorBoundaryVerified,
            dynamicAssignmentUnverified, sourceTimeScaleVerified, sourceIdentityTimeScaleVerified,
            persistentVisiblePose, verified;
        public float sourceTimeScale, nativeTimeScale;
        public int rootMeshVertexCount, rootMeshSubmeshCount, rootMeshIndexCount, rootCanvasMaterialCount,
            rootExtraMaterialModifierCount, registeredRendererCount;
    }

    /// <summary>Typed proof for a pinned Spine asset whose fixed pose has no drawable attachments.</summary>
    [Serializable] public sealed class ProxySpineEmptyPoseOwner
    {
        public string sourceComponentId, sourceNode, sourceDataAssetId, sourceDataAssetPath, sourceDataAssetGuid,
            sourceBindingPlanPath, sourceBindingPlanSha256, sourceManifestSha256, sourceSkin, sourceAnimation,
            actualSkin, runtimeDefaultSkinName, actualAnimation, sourceTargetFieldsJson, expectedFieldsJson, actualFieldsJson;
        public Graphic sourceOwnerGraphic;
        public UnityEngine.Object sourceDataAssetReference;
        public int fixedPoseSlotCount, fixedPoseAttachmentCount, fixedPoseDrawableAttachmentCount,
            presentationInstructionCount, presentationCanvasRendererCount, rootMeshVertexCount,
            rootMeshSubmeshCount, rootCanvasMaterialCount, registeredRendererCount;
        public float sourceTimeScale, nativeTimeScale, actualTrackTime;
        public bool sourceHasStaticDataReference, sourcePlanVerified, sourceIdentityVerified,
            sourceDataReferenceVerified, sourceTimeScaleVerified, sourceIdentityTimeScaleVerified,
            persistentVisiblePose, sourceBusinessBehaviorDisabled, sourceCallbacksExecuted,
            mappedStaticFieldsVerified, sdkPoseInitialized, sdkDataIdentityVerified,
            sourceSkinRuntimeVerified, defaultSkinRuntimeNull, fixedPoseVerified, noDrawableAttachmentPoseVerified, rootMeshEmpty,
            registeredRendererListEmpty, helperReadbackVerified, verified;
    }

    /// <summary>Maintains source render suppression without changing Graphic.enabled or authored fields.</summary>
    [AddComponentMenu("")]
    [ExecuteAlways]
    public sealed class NativeStaticSortQueueProxyPresenter : MonoBehaviour
    {
        public string sourceRootId, sourcePrefabId, prefabPath, queueSha256;
        public GameObject sourceRoot;
        public GameObject proxyRoot;
        public ProxyGraphicBinding[] bindings = Array.Empty<ProxyGraphicBinding>();
        public ProxyMaskBinding[] maskBindings = Array.Empty<ProxyMaskBinding>();
        public ProxySpineOwnerDelegation[] spineOwnerDelegations = Array.Empty<ProxySpineOwnerDelegation>();
        public ProxySpineNonDrawChild[] spineNonDrawChildren = Array.Empty<ProxySpineNonDrawChild>();
        public ProxySpineNullDataOwner[] spineNullDataOwners = Array.Empty<ProxySpineNullDataOwner>();
        public ProxySpineEmptyPoseOwner[] spineEmptyPoseOwners = Array.Empty<ProxySpineEmptyPoseOwner>();
        public GameObject[] nestedProxyRoots = Array.Empty<GameObject>();
        public NativeStaticSortQueueProxyPresenter[] nestedProxyPresenters = Array.Empty<NativeStaticSortQueueProxyPresenter>();
        public bool[] nestedProxyRootActiveBefore = Array.Empty<bool>();
        [NonSerialized] public Graphic[] sourceGraphics = Array.Empty<Graphic>();
        [NonSerialized] public bool[] sourceCullBefore = Array.Empty<bool>();
        public bool sourceTreeStayedUnmodified = true;
        bool subscribed;
        NativeStaticSortQueueRuntime runtime;

        void OnEnable()
        {
            DisableNestedProxyRoots();
            SuppressSources();
            Canvas.willRenderCanvases += SuppressSources;
            subscribed = true;
        }
        void OnDisable()
        {
            if (subscribed) Canvas.willRenderCanvases -= SuppressSources;
            subscribed = false;
            runtime?.Dispose(); runtime = null;
            for (var i = 0; i < (sourceGraphics ?? Array.Empty<Graphic>()).Length; i++)
                if (sourceGraphics[i] != null && sourceGraphics[i].canvasRenderer != null && i < sourceCullBefore.Length)
                    sourceGraphics[i].canvasRenderer.cull = sourceCullBefore[i];
            foreach (var binding in bindings ?? Array.Empty<ProxyGraphicBinding>())
                if (binding != null && binding.sourceCanvasRenderer != null)
                    binding.sourceCanvasRenderer.cull = binding.sourceCanvasCullBefore;
            RestoreNestedProxyRoots();
        }
        public void CaptureSourceCullStates()
        {
            if (sourceRoot == null) return;
            var current = SourceGraphics().ToArray();
            var prior = new Dictionary<Graphic, bool>();
            for (var i = 0; i < (sourceGraphics ?? Array.Empty<Graphic>()).Length; i++)
                if (sourceGraphics[i] != null && i < sourceCullBefore.Length) prior[sourceGraphics[i]] = sourceCullBefore[i];
            sourceCullBefore = current.Select(g => prior.TryGetValue(g, out var value) ? value : g.canvasRenderer.cull).ToArray();
            sourceGraphics = current;
        }
        void SuppressSources()
        {
            DisableNestedProxyRoots();
            if (Application.isPlaying)
            {
                if (runtime == null && sourceRoot != null) runtime = new NativeStaticSortQueueRuntime(this);
                runtime?.Refresh();
            }
            // CanvasRenderer.cull is runtime-only. Reapply after each Canvas
            // rebuild so generated TMP/Spine child Graphics cannot leak a draw.
            if (sourceRoot != null)
            {
                CaptureSourceCullStates();
                foreach (var graphic in sourceGraphics)
                    if (graphic != null && graphic.canvasRenderer != null) graphic.canvasRenderer.cull = true;
            }
            foreach (var binding in bindings ?? Array.Empty<ProxyGraphicBinding>())
                if (binding != null && binding.sourceCanvasRenderer != null)
                    binding.sourceCanvasRenderer.cull = true;
        }

        IEnumerable<Graphic> SourceGraphics()
        {
            if (sourceRoot == null) yield break;
            foreach (var graphic in sourceRoot.GetComponentsInChildren<Graphic>(true))
            {
                if (graphic == null) continue;
                // An owned input-only surface must keep its CanvasRenderer uncullled:
                // GraphicRaycaster uses cull as part of its hit test. The exact
                // typed blocker contract is independently validated by the proxy readback.
                var inputBlocker = graphic.GetComponent<NativeInputBlocker>();
                if (graphic is NativeInputBlockerSurface && inputBlocker != null &&
                    inputBlocker.OwnsSurface && inputBlocker.Surface == graphic)
                    continue;
                var cursor = graphic.transform;
                while (cursor != null && cursor != sourceRoot.transform)
                {
                    if (IsGeneratedProxyRoot(cursor)) break;
                    cursor = cursor.parent;
                }
                if (cursor != null && cursor != sourceRoot.transform) continue;
                yield return graphic;
            }
        }

        bool IsGeneratedProxyRoot(Transform candidate)
        {
            if (candidate == null || candidate.parent == null) return false;
            var marker = candidate.GetComponent<NativeStaticSortQueueProxyMarker>();
            if (marker == null || marker.kind != "root" || marker.sourceRootOwner == null || marker.sourceRootOwner.transform != candidate.parent)
                return false;
            var ownerPresenter = candidate.GetComponent<NativeStaticSortQueueProxyPresenter>();
            return ownerPresenter != null && ownerPresenter.sourceRoot == marker.sourceRootOwner &&
                ownerPresenter.proxyRoot == candidate.gameObject && ownerPresenter.sourceRootId == marker.sourceNode;
        }

        public void InitializePresentation()
        {
            DisableNestedProxyRoots();
            SuppressSources();
        }

        public void RefreshSourceSuppression() => SuppressSources();

        void DisableNestedProxyRoots()
        {
            foreach (var root in (nestedProxyRoots ?? Array.Empty<GameObject>()).Where(item => item != null)
                .OrderBy(item => HierarchyDepth(item.transform)))
                if (root != null && root.activeSelf) root.SetActive(false);
        }

        void RestoreNestedProxyRoots()
        {
            var indexes = Enumerable.Range(0, (nestedProxyRoots ?? Array.Empty<GameObject>()).Length)
                .Where(i => nestedProxyRoots[i] != null && i < nestedProxyRootActiveBefore.Length)
                .OrderByDescending(i => HierarchyDepth(nestedProxyRoots[i].transform));
            foreach (var index in indexes) nestedProxyRoots[index].SetActive(nestedProxyRootActiveBefore[index]);
        }

        static int HierarchyDepth(Transform value)
        {
            var result = 0;
            while (value != null) { result++; value = value.parent; }
            return result;
        }
    }
}
