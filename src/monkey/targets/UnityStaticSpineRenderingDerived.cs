// Saved SDK state and derived mesh ownership for static Spine rendering.
// Reuses the exact native-stage checks; emitted only with the rendering adapter.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;
using Spine.Unity;
using Monkey.Targets.Spine;

public static partial class MonkeyImporter
{
    static Plan spineRenderingUnitPlan;
    static Dictionary<string,GameObject> spineRenderingUnitNodes;
    static float spineRenderingObservedCanvasPpu;
    static partial void ObserveStaticSpineRenderingUnitMapping(Plan plan,Dictionary<string,GameObject> nodes) {
        spineRenderingUnitPlan=null;spineRenderingUnitNodes=null;spineRenderingObservedCanvasPpu=0;
        ResetStaticSpineOwnerLifecycleRegistries();
        if(String.IsNullOrEmpty(plan.staticSpineRenderingJson))return;
        var renderingPath=Path.Combine(Directory.GetParent(Application.dataPath).FullName,StaticSpineRenderingPlanPath);
        var embedded=JsonUtility.FromJson<StaticSpineRenderingEnvelope>(plan.staticSpineRenderingJson);
        if(embedded!=null&&File.Exists(renderingPath)) {
            var frozenBytes=File.ReadAllBytes(renderingPath);
            var frozen=JsonUtility.FromJson<StaticSpineRenderingEnvelope>(Encoding.UTF8.GetString(frozenBytes));
            if(frozen!=null&&JsonUtility.ToJson(frozen)==JsonUtility.ToJson(embedded)&&
                frozen.sourceManifestSha256==plan.sourceManifestSha256) {
                staticSpineRenderingPlan=frozen;
                staticSpineRenderingPlanSha=StaticSpineCanvasHashBytes(frozenBytes);
                InitializeStaticSpineOwnerLifecycleComponents(frozen);
            }
        }
        CaptureStaticSpineRenderingUnitMapping(plan,nodes,out var ppu);
        staticSpineSourceCanvasContext=BuildStaticSpineSourceCanvasContextEvidence(plan,nodes,ppu,true);
        spineRenderingUnitPlan=plan;spineRenderingUnitNodes=nodes;spineRenderingObservedCanvasPpu=ppu;
    }
    static bool VerifyStaticSpineRenderingUnitMapping(Plan plan,Dictionary<string,GameObject> nodes,out float actualCanvasPpu) {
        if(!System.Object.ReferenceEquals(plan,spineRenderingUnitPlan)||!System.Object.ReferenceEquals(nodes,spineRenderingUnitNodes)||
            spineRenderingObservedCanvasPpu<=0||staticSpineSourceCanvasContext==null||
            staticSpineSourceCanvasContext.sourceManifestSha256!=plan.sourceManifestSha256||
            !staticSpineSourceCanvasContext.sourceCanvasContextVerified||!staticSpineSourceCanvasContext.sourceNodeGeometryVerified||
            StaticSpineCanvasEvidenceHash(staticSpineSourceCanvasContext)!=staticSpineSourceCanvasContext.evidenceSha256)
            throw new InvalidOperationException("SPINE_UNIT_MAPPING_CONSTRUCTION_OBSERVATION_MISSING");
        actualCanvasPpu=spineRenderingObservedCanvasPpu;
        return true;
    }
    // Observe direct unit transfer immediately after hierarchy construction,
    // before legitimate Layout/Widget components can reposition their children.
    static bool CaptureStaticSpineRenderingUnitMapping(Plan plan,Dictionary<string,GameObject> nodes,out float actualCanvasPpu) {
        actualCanvasPpu=0;
        if(plan==null||plan.nodes==null||nodes==null)throw new InvalidOperationException("SPINE_UNIT_MAPPING_INPUT_MISSING");
        foreach(var source in plan.nodes) {
            if(!nodes.TryGetValue(source.sourceId,out var node)||node==null)throw new InvalidOperationException("SPINE_UNIT_MAPPING_NODE_MISSING: "+source.sourceId);
            var rect=node.transform as RectTransform;
            if(rect==null||source.position==null||source.position.Length!=3||source.size==null||source.size.Length!=2||source.scale==null||source.scale.Length!=3||
                !SpineUnitClose(rect.anchoredPosition3D.x,source.position[0])||!SpineUnitClose(rect.anchoredPosition3D.y,source.position[1])||!SpineUnitClose(rect.anchoredPosition3D.z,source.position[2])||
                !SpineUnitClose(rect.sizeDelta.x,source.size[0])||!SpineUnitClose(rect.sizeDelta.y,source.size[1])||
                !SpineUnitClose(rect.localScale.x,source.scale[0])||!SpineUnitClose(rect.localScale.y,source.scale[1])||!SpineUnitClose(rect.localScale.z,source.scale[2]))
                throw new InvalidOperationException("SPINE_UNIT_MAPPING_SOURCE_GEOMETRY_DIFFERS: "+source.sourceId);
            var canvas=node.GetComponentInParent<Canvas>(true);
            var scaler=canvas==null?null:canvas.GetComponent<CanvasScaler>();
            if(canvas==null||canvas.renderMode!=RenderMode.ScreenSpaceOverlay||scaler==null||
                !SpineUnitClose(canvas.referencePixelsPerUnit,scaler.referencePixelsPerUnit)||canvas.referencePixelsPerUnit<=0||
                Single.IsNaN(canvas.referencePixelsPerUnit)||Single.IsInfinity(canvas.referencePixelsPerUnit))
                throw new InvalidOperationException("SPINE_UNIT_MAPPING_CANVAS_CONTEXT_UNVERIFIED: "+source.sourceId);
            if(actualCanvasPpu!=0&&!SpineUnitClose(actualCanvasPpu,canvas.referencePixelsPerUnit))
                throw new InvalidOperationException("SPINE_UNIT_MAPPING_CANVAS_CONTEXT_CONFLICT: "+source.sourceId);
            actualCanvasPpu=canvas.referencePixelsPerUnit;
        }
        if(actualCanvasPpu<=0)throw new InvalidOperationException("SPINE_UNIT_MAPPING_NO_SOURCE_NODES");
        return true;
    }
    static bool SpineUnitClose(float actual,float expected) {
        return !Single.IsNaN(actual)&&!Single.IsInfinity(actual)&&!Single.IsNaN(expected)&&!Single.IsInfinity(expected)&&Math.Abs(actual-expected)<=0.001f;
    }

    // Called by the shared source hierarchy walker. A child is generated by the
    // pinned Spine SDK only when its CanvasRenderer object is the exact direct
    // child stored in the owning SkeletonGraphic's renderer list and has the
    // SDK-created RawImage component. Names are intentionally irrelevant.
    static partial void IdentifyOptionalGeneratedSpineChild(Transform child, ref bool generated)
    {
        if (child == null || !(child is RectTransform) || child.parent == null || child.childCount != 0) return;
        var owner = child.parent.GetComponent<SkeletonGraphic>();
        if (owner == null || owner.canvasRenderers == null) return;
        var renderer = child.GetComponent<CanvasRenderer>();
        var rawImage = child.GetComponent<RawImage>();
        if (renderer == null || rawImage == null) return;
        if (owner.canvasRenderers.Count(row => row == renderer && row.gameObject == child.gameObject) == 1)
            generated = true;
    }

    // Unity serializes SkeletonGraphic.canvasRenderers because it is a public
    // List<CanvasRenderer>, but this list is derived by the pinned SDK from its
    // submesh pose. The serialized RawImage child objects and the helper's typed
    // material pairs remain the durable authoring data. Rebuild only SDK runtime
    // state from those saved fields; never consult the plan or reassign source refs.
    static partial void InitializeSavedStaticSpine(GameObject root)
    {
        if (root == null) throw new InvalidOperationException("SPINE_SAVED_INITIALIZE_ROOT_MISSING");
        var markers = root.GetComponentsInChildren<UnitySpineSourceIdentity>(true)
            .Where(marker => marker != null && marker.renderer != null &&
                marker.renderer.GetType() == typeof(SkeletonGraphic) &&
                marker.renderer.gameObject.transform.IsChildOf(root.transform))
            .ToArray();
        var seen = new HashSet<SkeletonGraphic>();
        foreach (var marker in markers)
        {
            var graphic = marker.renderer as SkeletonGraphic;
            if (graphic == null || graphic.gameObject == null || !seen.Add(graphic))
                throw new InvalidOperationException("SPINE_SAVED_GRAPHIC_IDENTITY_DUPLICATE_OR_MISSING:" +
                    (marker.instanceSourceComponentId ?? marker.sourceComponentId ?? "null"));
            var helper = graphic.GetComponent<UnitySpineGraphicMaterialPresentation>();
            if (graphic.skeletonDataAsset == null)
            {
                if (helper != null)
                    throw new InvalidOperationException("SPINE_SAVED_UNBOUND_GRAPHIC_HAS_MATERIAL_HELPER:" +
                        helper.SourceComponentId);
                continue;
            }
            if (helper == null || !helper.enabled ||
                (helper.SourceComponentId != marker.instanceSourceComponentId &&
                 helper.SourceComponentId != marker.sourceComponentId))
                throw new InvalidOperationException("SPINE_SAVED_GRAPHIC_HELPER_IDENTITY_MISMATCH:" +
                    (marker.instanceSourceComponentId ?? marker.sourceComponentId ?? "null"));
            if (!helper.AttachForSavedInitialization())
                throw new InvalidOperationException("SPINE_SAVED_GRAPHIC_HELPER_EVENT_ATTACH_FAILED:" + helper.SourceComponentId);

            var savedDataAsset = graphic.skeletonDataAsset;
            var savedSkin = graphic.initialSkinName;
            var savedAnimation = graphic.startingAnimation;
            var savedLoop = graphic.startingLoop;
            var savedTimeScale = graphic.timeScale;
            var savedBaseMaterial = graphic.material;
            var savedColor = graphic.color;
            var savedPma = graphic.MeshGenerator == null ? (bool?)null : graphic.MeshGenerator.settings.pmaVertexColors;
            if (!helper.RestoreSdkRendererLinksFromSavedChildren(out var restoreGaps) && restoreGaps.Length != 0)
                throw new InvalidOperationException("SPINE_SAVED_SDK_RENDERER_LINK_RESTORE_FAILED:" +
                    helper.SourceComponentId + ":" + String.Join(",", restoreGaps));

            // Read the already-saved data/skin/animation/material references. This
            // does not apply plan values or execute recovered scripts.
            graphic.Initialize(true);
            if (!graphic.IsValid)
                throw new InvalidOperationException("SPINE_SAVED_GRAPHIC_RUNTIME_SKELETON_NOT_INITIALIZED:" +
                    helper.SourceComponentId);
            graphic.Update(0f);
            graphic.UpdateMesh(keepRendererCount: false);
            graphic.TrimRenderers();
            graphic.UpdateMesh(keepRendererCount: false);
            bool savedFieldsUnchanged = graphic.skeletonDataAsset == savedDataAsset &&
                graphic.initialSkinName == savedSkin && graphic.startingAnimation == savedAnimation &&
                graphic.startingLoop == savedLoop && Math.Abs(graphic.timeScale - savedTimeScale) < 0.000001f &&
                graphic.material == savedBaseMaterial && graphic.color == savedColor &&
                (savedPma == null || graphic.MeshGenerator != null &&
                    graphic.MeshGenerator.settings.pmaVertexColors == savedPma.Value);
            if (!savedFieldsUnchanged)
                throw new InvalidOperationException("SPINE_SAVED_GRAPHIC_AUTHORED_FIELDS_CHANGED_DURING_INITIALIZE:" +
                    helper.SourceComponentId);
            var readback = helper.ReadSavedStoredState();
            if (!readback.nativeMaterialVerified)
                throw new InvalidOperationException("SPINE_SAVED_GRAPHIC_RUNTIME_STATE_UNVERIFIED:" +
                    helper.SourceComponentId + ":" + String.Join(",", readback.gaps ?? Array.Empty<string>()));
        }
    }

    // Run after all generic Canvas/Layout/Graphic refreshes and immediately
    // before static sort capture/readback. RawImage.texture dirties vertices;
    // the pinned SkeletonGraphic SDK must be the last mesh writer so its
    // actual clipped/polygon mesh is restored after any generic four-corner
    // RawImage population. Do not initialize/advance the animation here.
    static partial void FinalizePreviewSpineMeshes(Canvas canvas)
    {
        var owners = canvas.GetComponentsInChildren<UnitySpineSourceIdentity>()
            .Select(marker => marker.renderer as SkeletonGraphic)
            .Where(graphic => graphic != null && graphic.isActiveAndEnabled && graphic.skeletonDataAsset != null)
            .Cast<Graphic>().ToArray();
        if (owners.Length > 0) FinalizeSavedStaticSortSpineMeshes(owners);
    }

    static void FinalizeSavedStaticSortSpineMeshes(Graphic[] sourceOwners)
    {
        var owners = (sourceOwners ?? Array.Empty<Graphic>()).Distinct().ToArray();
        if (owners.Length == 0) throw new InvalidOperationException("SPINE_STATIC_SORT_FINALIZE_OWNER_SET_EMPTY");
        var seen = new HashSet<SkeletonGraphic>();
        foreach (var sourceOwner in owners)
        {
            var graphic = sourceOwner as SkeletonGraphic;
            var marker = graphic == null ? null : graphic.GetComponent<UnitySpineSourceIdentity>();
            var identity = marker == null ? "null" : marker.instanceSourceComponentId ?? marker.sourceComponentId ?? "null";
            if (graphic == null || !seen.Add(graphic))
                throw new InvalidOperationException("SPINE_STATIC_SORT_FINALIZE_OWNER_DUPLICATE_OR_MISSING:" + identity);
            if (marker == null || marker.renderer != graphic || graphic.skeletonDataAsset == null)
                throw new InvalidOperationException("SPINE_STATIC_SORT_FINALIZE_OWNER_TYPED_IDENTITY_OR_DATA_MISSING:" + identity);
            var helper = graphic.GetComponent<UnitySpineGraphicMaterialPresentation>();
            if (helper == null || !helper.enabled ||
                helper.SourceComponentId != marker.instanceSourceComponentId &&
                helper.SourceComponentId != marker.sourceComponentId)
                throw new InvalidOperationException("SPINE_STATIC_SORT_FINALIZE_HELPER_IDENTITY_MISMATCH:" + identity);
            if (!helper.AttachForSavedInitialization())
                throw new InvalidOperationException("SPINE_STATIC_SORT_FINALIZE_EVENT_ATTACH_FAILED:" + helper.SourceComponentId);
            if (!graphic.IsValid)
                throw new InvalidOperationException("SPINE_STATIC_SORT_FINALIZE_SKELETON_NOT_INITIALIZED:" + helper.SourceComponentId);

            var savedData = graphic.skeletonDataAsset;
            var savedSkin = graphic.initialSkinName;
            var savedAnimation = graphic.startingAnimation;
            var savedLoop = graphic.startingLoop;
            var savedTimeScale = graphic.timeScale;
            var savedMaterial = graphic.material;
            var savedColor = graphic.color;
            var savedPma = graphic.MeshGenerator == null ? (bool?)null : graphic.MeshGenerator.settings.pmaVertexColors;

            // Rebuild the already-initialized fixed pose; do not call
            // Initialize(true), advance time, wait for a frame, or play business logic.
            graphic.UpdateMesh(keepRendererCount: false);
            graphic.TrimRenderers();
            graphic.UpdateMesh(keepRendererCount: false);
            var bindingReadback = helper.ApplyExactBindings();
            if (!bindingReadback.nativeMaterialVerified)
                throw new InvalidOperationException("SPINE_STATIC_SORT_FINALIZE_MATERIAL_BINDING_FAILED:" +
                    helper.SourceComponentId + ":" + String.Join(",", bindingReadback.gaps ?? Array.Empty<string>()));
            if (graphic.skeletonDataAsset != savedData || graphic.initialSkinName != savedSkin ||
                graphic.startingAnimation != savedAnimation || graphic.startingLoop != savedLoop ||
                Math.Abs(graphic.timeScale - savedTimeScale) >= 0.000001f || graphic.material != savedMaterial ||
                graphic.color != savedColor || savedPma != null &&
                (graphic.MeshGenerator == null || graphic.MeshGenerator.settings.pmaVertexColors != savedPma.Value))
                throw new InvalidOperationException("SPINE_STATIC_SORT_FINALIZE_AUTHORED_FIELDS_CHANGED:" + helper.SourceComponentId);

            if (bindingReadback.instructionCount == 0)
            {
                var pose = bindingReadback.pose;
                var rootMesh = graphic.canvasRenderer == null ? null : graphic.canvasRenderer.GetMesh();
                var emptyPoseVerified = bindingReadback.nativeMaterialVerified &&
                    bindingReadback.nativeMaterialStatus == "verified_empty_pose_with_persistent_material_pairs" &&
                    bindingReadback.canvasRendererCount == 0 && pose != null && pose.emptyPoseVerified &&
                    pose.initialized && pose.animationStateInitialized && pose.sourceDataIdentityVerified &&
                    pose.sourceSkinVerified && pose.sourceAnimationVerified && pose.allSlotsHaveNoDrawableAttachment &&
                    pose.emptyRendererStateVerified && pose.activeDrawableAttachmentCount == 0 && pose.trackTime == 0f &&
                    pose.sourceSkinVerified && (pose.actualSkin == pose.sourceSkin ||
                        pose.defaultSkinRuntimeNull && String.IsNullOrEmpty(pose.actualSkin) &&
                        !String.IsNullOrEmpty(pose.runtimeDefaultSkinName) && pose.runtimeDefaultSkinName == pose.sourceSkin) &&
                    pose.actualAnimation == pose.sourceAnimation && graphic.canvasRenderers != null &&
                    graphic.canvasRenderers.Count == 0 && rootMesh == null;
                if (!emptyPoseVerified)
                    throw new InvalidOperationException("SPINE_STATIC_SORT_FINALIZE_ZERO_RENDERER_POSE_NOT_PROVEN_EMPTY:" +
                        helper.SourceComponentId + ";status=" + bindingReadback.nativeMaterialStatus +
                        ";instructions=" + bindingReadback.instructionCount + ";reportedRenderers=" +
                        bindingReadback.canvasRendererCount + ";actualRenderers=" +
                        (graphic.canvasRenderers == null ? -1 : graphic.canvasRenderers.Count) +
                        ";rootMeshVertices=" + (rootMesh == null ? -1 : rootMesh.vertexCount) +
                        ";skinRequested=" + (pose == null ? "<missing>" : pose.sourceSkin ?? "<null>") +
                        ";skinRuntime=" + (pose == null ? "<missing>" : pose.actualSkin ?? "<null>") +
                        ";defaultSkin=" + (pose == null ? "<missing>" : pose.runtimeDefaultSkinName ?? "<null>") +
                        ";defaultNullAlias=" + (pose != null && pose.defaultSkinRuntimeNull) +
                        ";animationRequested=" + (pose == null ? "<missing>" : pose.sourceAnimation ?? "<null>") +
                        ";animationRuntime=" + (pose == null ? "<missing>" : pose.actualAnimation ?? "<null>") +
                        ";trackTime=" + (pose == null ? "<missing>" : pose.trackTime.ToString("R", System.Globalization.CultureInfo.InvariantCulture)) +
                        ";gaps=" + String.Join(",", bindingReadback.gaps ?? Array.Empty<string>()));
                continue;
            }
            if (graphic.canvasRenderers == null || graphic.canvasRenderers.Count == 0)
                throw new InvalidOperationException("SPINE_STATIC_SORT_FINALIZE_RENDERER_LIST_EMPTY_WITH_DRAW_INSTRUCTIONS:" +
                    helper.SourceComponentId + ";instructions=" + bindingReadback.instructionCount);
            var seenRenderers = new HashSet<CanvasRenderer>();
            foreach (var renderer in graphic.canvasRenderers)
            {
                var child = renderer == null ? null : renderer.GetComponent<Graphic>();
                var mesh = renderer == null ? null : renderer.GetMesh();
                if (renderer == null || !seenRenderers.Add(renderer) || child == null ||
                    !IsSpineStaticSortGeneratedChild(child, graphic) || mesh == null || mesh.vertexCount == 0 ||
                    mesh.subMeshCount != 1 || renderer.materialCount != 1)
                    throw new InvalidOperationException("SPINE_STATIC_SORT_FINALIZE_CHILD_MESH_INVALID:" +
                        helper.SourceComponentId + ";child=" + (child == null ? "null" : child.name) +
                        ";vertices=" + (mesh == null ? -1 : mesh.vertexCount) + ";submeshes=" +
                        (mesh == null ? -1 : mesh.subMeshCount) + ";materials=" +
                        (renderer == null ? -1 : renderer.materialCount));
            }
        }
    }

    static bool IsSpineStaticSortGeneratedChild(Graphic child, SkeletonGraphic owner)
    {
        if (child == null || owner == null || child.transform.parent != owner.transform ||
            child.transform.childCount != 0 || !(child.transform is RectTransform) ||
            child.GetType() != typeof(RawImage) || child.canvasRenderer == null ||
            owner.canvasRenderers == null) return false;
        return owner.canvasRenderers.Count(renderer => renderer == child.canvasRenderer &&
            renderer.gameObject == child.gameObject) == 1;
    }

    // canvasRenderers is the sole serialized derived list in the pinned SDK
    // SkeletonGraphic layout. rawImages/currentInstructions/meshes are protected
    // or private and lack [SerializeField], so Unity does not copy them.
    static partial void SkipOptionalSpineDerivedProperty(Component component, string propertyPath, ref bool skip)
    {
        if (component == null || component.GetType() != typeof(SkeletonGraphic) ||
            String.IsNullOrWhiteSpace(propertyPath)) return;
        if (propertyPath == "canvasRenderers" || propertyPath.StartsWith("canvasRenderers.", StringComparison.Ordinal))
            skip = true;
    }

    // In the pinned SDK, multiple-renderer Submesh GameObjects are direct
    // SkeletonGraphic children with the exact CanvasRenderer instance listed in
    // canvasRenderers; SyncRawImagesWithCanvasRenderers added this RawImage.
    // The root renderer is not in that list, so a RawImage on the root is never
    // classified as SDK-generated by this proof.
    static partial void IdentifyOptionalSpineDerivedComponent(Component component, ref bool generated)
    {
        if (component == null || component.GetType() != typeof(RawImage)) return;
        var rawImage = (RawImage)component;
        var renderer = rawImage.canvasRenderer;
        if (renderer == null || renderer.gameObject != component.gameObject ||
            !(component.transform is RectTransform) || component.transform.childCount != 0) return;
        var owner = component.transform.parent == null
            ? null : component.transform.parent.GetComponent<SkeletonGraphic>();
        if (owner == null || owner.canvasRenderers == null || owner.enableSeparatorSlots)
            return;
        var helper = owner.GetComponent<UnitySpineGraphicMaterialPresentation>();
        if (helper == null || !helper.HasBoundGraphicMaterial(rawImage.material) ||
            rawImage.raycastTarget || rawImage.maskable != owner.maskable) return;
        bool exactSdkListLink = owner.canvasRenderers.Any(candidate =>
            candidate == renderer && candidate.gameObject == component.gameObject);
        // A copy counterpart may be checked after the canvasRenderers serialized
        // field was intentionally skipped. In that state an empty list is expected;
        // the serialized helper Material reference is the durable owner proof.
        if (!exactSdkListLink && owner.canvasRenderers.Count != 0) return;
        generated = true;
    }



    static Color SourceSpineNodeColor(NodeSpec source, string sourceComponentId)
    {
        var channels = source == null ? null : source.color;
        if (channels == null || channels.Length != 4 || channels.Any(value => Single.IsNaN(value) || Single.IsInfinity(value) || value < 0f || value > 255f))
            throw new InvalidOperationException("SPINE_SOURCE_NODE_RGBA_INVALID:" + sourceComponentId);
        // NodeSpec.color stores source RGBA channels as bytes. CanvasGroup
        // opacity is emitted separately by the primary importer.
        return new Color(channels[0] / 255f, channels[1] / 255f, channels[2] / 255f, channels[3] / 255f);
    }

    static float[] SpineGraphicColorChannels(SkeletonGraphic graphic)
    {
        var color = graphic.color;
        return new[] { color.r * 255f, color.g * 255f, color.b * 255f, color.a * 255f };
    }

    static bool SpineGraphicColorMatches(SkeletonGraphic graphic, NodeSpec source, string sourceComponentId)
    {
        SourceSpineNodeColor(source, sourceComponentId);
        var actual = SpineGraphicColorChannels(graphic);
        return Enumerable.Range(0, 4).All(index => Math.Abs(actual[index] - source.color[index]) <= 0.001f);
    }
}
