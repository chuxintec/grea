// Exact per-submesh UI material presentation for the pinned Spine 3.8.99 runtime.
// This is a renderer adapter only: it does not inspect source JSON or advance Spine state.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Spine.Unity;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.UI;
using Monkey.StaticMaskSort;

namespace Monkey.Targets.Spine
{
    [DisallowMultipleComponent]
    [AddComponentMenu("")]
    public sealed class UnitySpineGraphicMaterialPresentation : MonoBehaviour
    {
        public const string ExpectedSdkInstructionsType = "Spine.Unity.SkeletonRendererInstruction";
        public const string ExpectedUiShaderName = "Monkey/SpineSourceGraphicProfile/Colored";

        [Serializable] public sealed class MaterialBinding
        {
            public string sourceMaterialId;
            public string textureSourceId;
            public string blendMode;
            public Material sourceMaterial;
            public Material graphicMaterial;
            public string graphicMaterialAssetPath;
            public string graphicMaterialAssetGuid;
            public string graphicTextureAssetPath;
            public string graphicTextureAssetGuid;
            public int expectedSrcBlend;
            public int expectedDstBlend;
        }

        [Serializable] public sealed class RendererRow
        {
            public int index;
            public string sourceMaterialId;
            public string textureSourceId;
            public string blendMode;
            public string actualMaterialShader;
            public string actualMaterialName;
            public string actualTextureName;
            public string baseMaterialAssetPath;
            public string baseMaterialAssetGuid;
            public string baseMaterialShader;
            public string baseMaterialTextureAssetPath;
            public string baseMaterialTextureGuid;
            public int stencilDepth;
            public string stencilRootSortCanvasPath;
            public string[] stencilMaskAncestorSourceIds;
            public int stencilReference;
            public int stencilComparison;
            public int stencilOperation;
            public int stencilReadMask;
            public int stencilWriteMask;
            public int stencilColorMask;
            public int stencilUseAlphaClip;
            public bool rawImageEnabled;
            public bool rawImageMaskable;
            public bool rawImageMaterialReferenceVerified;
            public bool materialReferenceVerified;
            public bool textureReferenceVerified;
            public bool blendVerified;
            public bool baseMaterialPersistentReferenceVerified;
            public bool modifiedMaterialShaderMatchesBase;
            public bool nonStencilMaterialPropertiesMatch;
            public bool stencilAncestryVerified;
            public bool stencilConfigurationVerified;
            public bool transientStencilVariantVerified;
        }

        [Serializable] public sealed class Readback
        {
            public string sourceComponentId;
            public string sdkInstructionsType;
            public int instructionCount;
            public int canvasRendererCount;
            public bool sdkEventAttached;
            public bool materialPairsVerified;
            public string nativeMaterialStatus;
            public bool nativeMaterialVerified;
            public string textureVerificationMethod;
            public PoseReadback pose;
            public string[] gaps;
            public RendererRow[] renderers;
        }

        [Serializable] public sealed class PoseReadback
        {
            public bool initialized;
            public bool animationStateInitialized;
            public bool sourceDataIdentityVerified;
            public string dataVersion;
            public int boneCount;
            public int slotCount;
            public int activeDrawableAttachmentCount;
            public int nonNullAttachmentCount;
            public string sourceSkin;
            public string actualSkin;
            public bool sourceSkinVerified;
            public string runtimeDefaultSkinName;
            public bool defaultSkinRuntimeNull;
            public string sourceAnimation;
            public string actualAnimation;
            public float trackTime;
            public bool sourceAnimationVerified;
            public bool allSlotsHaveNoDrawableAttachment;
            public bool emptyRendererStateVerified;
            public bool emptyPoseVerified;
            public string[] gaps;
            public string[] activeDrawableAttachments;
        }

        [SerializeField] string sourceComponentId;
        [SerializeField] SkeletonGraphic graphic;
        [SerializeField] MaterialBinding[] bindings = Array.Empty<MaterialBinding>();
        [NonSerialized] bool sdkEventAttached;
        [SerializeField] bool nativeMaterialVerified;
        [SerializeField] string[] lastGaps = Array.Empty<string>();

        static readonly BindingFlags InstanceFlags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

        public string SourceComponentId { get { return sourceComponentId; } }

        public bool HasBoundGraphicMaterial(Material material)
        {
            return material != null && (bindings ?? Array.Empty<MaterialBinding>())
                .Any(binding => binding != null && binding.graphicMaterial == material);
        }

        public bool AttachForSavedInitialization()
        {
            if (!enabled || graphic == null ||
                graphic.GetComponent<UnitySpineGraphicMaterialPresentation>() != this) return false;
            Attach();
            return sdkEventAttached;
        }

        /// <summary>
        /// Rebuild the pinned SDK's non-source canvasRenderers list after native
        /// component-reference remapping. Existing child objects are accepted only
        /// when their exact RawImage.material is one of this helper's serialized UI
        /// profile materials; no object names or plan IDs are consulted.
        /// </summary>
        public bool RestoreSdkRendererLinksFromSavedChildren(out string[] gaps)
        {
            var found = new List<CanvasRenderer>();
            var issues = new List<string>();
            if (graphic == null || graphic.GetComponent<UnitySpineGraphicMaterialPresentation>() != this)
                issues.Add("saved_spine_graphic_helper_owner_mismatch");
            else if (graphic.enableSeparatorSlots)
                issues.Add("saved_spine_separator_renderer_hierarchy_not_supported");
            else
            {
                for (int i = 0; i < graphic.transform.childCount; i++)
                {
                    var child = graphic.transform.GetChild(i);
                    var renderer = child.GetComponent<CanvasRenderer>();
                    var rawImage = child.GetComponent<RawImage>();
                    // A normal source Image also has CanvasRenderer, but lacks the
                    // exact SDK RawImage component and is left in the hierarchy.
                    if (rawImage == null) continue;
                    bool ownsMaterial = HasBoundGraphicMaterial(rawImage.material);
                    if (renderer == null || !(child is RectTransform) || rawImage.canvasRenderer != renderer ||
                        child.childCount != 0)
                    {
                        if (ownsMaterial) issues.Add("saved_owned_spine_raw_image_shape_ambiguous:" + i);
                        continue;
                    }
                    if (!ownsMaterial)
                    {
                        if (!rawImage.raycastTarget && rawImage.maskable == graphic.maskable)
                            issues.Add("saved_spine_sdk_raw_image_profile_not_owned_by_helper:" + i);
                        continue;
                    }
                    if (rawImage.raycastTarget || rawImage.maskable != graphic.maskable)
                    { issues.Add("saved_sdk_raw_image_settings_mismatch:" + i); continue; }
                    found.Add(renderer);
                }

                // CanvasRenderer is a UnityEngine.Object list field and therefore
                // serialized by Unity. It is a derived Spine 3.8 field, unlike the
                // authored data/animation/material fields on SkeletonGraphic.
                graphic.canvasRenderers.Clear();
                graphic.canvasRenderers.AddRange(found);
                var sync = typeof(SkeletonGraphic).GetMethod("SyncRawImagesWithCanvasRenderers", InstanceFlags,
                    null, Type.EmptyTypes, null);
                if (sync == null || !sync.IsFamily && !sync.IsPublic && !sync.IsAssembly)
                    issues.Add("pinned_sdk_raw_image_sync_member_missing");
                else
                {
                    try { sync.Invoke(graphic, null); }
                    catch (Exception error)
                    { issues.Add("pinned_sdk_raw_image_sync_failed:" + error.GetType().Name + ":" + error.Message); }
                }
            }
            gaps = issues.Distinct(StringComparer.Ordinal).ToArray();
            return gaps.Length == 0;
        }

        public Readback ReadSavedStoredState()
        {
            return graphic == null
                ? ReadSaved(null, null, false, null, false)
                : ReadSaved(bindings, graphic.initialSkinName, true, graphic.startingAnimation, true);
        }

        /// <summary>Set durable exact Material-identity bindings before saving the prefab.</summary>
        public void Configure(string exactSourceComponentId, SkeletonGraphic exactGraphic,
            MaterialBinding[] exactBindings)
        {
            if (String.IsNullOrWhiteSpace(exactSourceComponentId) || exactGraphic == null)
                throw new ArgumentException("Spine graphic source identity and component are required.");
            ValidateBindings(exactBindings);
            Detach();
            sourceComponentId = exactSourceComponentId;
            graphic = exactGraphic;
            bindings = exactBindings.ToArray();
            Attach();
            ApplyExactBindings();
        }

        void OnEnable() { Attach(); }
        void OnDisable() { Detach(); }

        void Attach()
        {
            if (graphic == null || sdkEventAttached) return;
            graphic.OnMeshAndMaterialsUpdated += OnMeshAndMaterialsUpdated;
            sdkEventAttached = true;
        }

        void Detach()
        {
            if (graphic != null && sdkEventAttached)
                graphic.OnMeshAndMaterialsUpdated -= OnMeshAndMaterialsUpdated;
            sdkEventAttached = false;
        }

        void OnMeshAndMaterialsUpdated(SkeletonGraphic updated)
        {
            if (updated == graphic) ApplyExactBindings();
        }

        /// <summary>Read current SDK submesh instructions, then apply the corresponding UGUI material.</summary>
        public Readback ApplyExactBindings()
        {
            var rows = new List<RendererRow>();
            var gaps = new List<string>();
            if (!enabled || (gameObject.activeInHierarchy && !sdkEventAttached))
                gaps.Add("sdk_material_update_event_not_attached");
            object[] instructions;
            string instructionType;
            if (!TryReadInstructions(graphic, out instructions, out instructionType, out var readGap))
                gaps.Add(readGap);
            else if (instructions.Length > 0 && (graphic.canvasRenderers == null || graphic.canvasRenderers.Count != instructions.Length))
                gaps.Add("sdk_submesh_canvas_renderer_count_mismatch");
            else if (bindings == null || bindings.Length == 0)
                gaps.Add("exact_material_bindings_missing");
            else
            {
                for (int i = 0; i < instructions.Length; i++)
                {
                    var sourceMaterial = ReadMember<Material>(instructions[i], "material");
                    var matches = bindings.Where(binding => binding != null && binding.sourceMaterial == sourceMaterial).ToArray();
                    if (matches.Length != 1)
                    {
                        gaps.Add(matches.Length == 0 ? "submesh_source_material_unmapped:" + i : "submesh_source_material_ambiguous:" + i);
                        continue;
                    }
                    var binding = matches[0];
                    var canvasRenderer = graphic.canvasRenderers[i];
                    if (canvasRenderer == null) { gaps.Add("submesh_canvas_renderer_missing:" + i); continue; }
                    var rawImage = canvasRenderer.GetComponent<RawImage>();
                    if (rawImage == null) { gaps.Add("submesh_sdk_raw_image_missing:" + i); continue; }
                    if (binding.graphicMaterial == null || binding.graphicMaterial.shader == null ||
                        binding.graphicMaterial.shader.name != ExpectedUiShaderName)
                    { gaps.Add("submesh_ui_material_invalid:" + i); continue; }
                    if (sourceMaterial == null || sourceMaterial.mainTexture == null)
                    { gaps.Add("submesh_source_material_texture_missing:" + i); continue; }

                    // RawImage is the SDK-owned MaskableGraphic for this renderer. Its materialForRendering
                    // applies UGUI stencil state; CanvasRenderer then gets that exact modified material.
                    rawImage.material = binding.graphicMaterial;
                    rawImage.texture = sourceMaterial.mainTexture;
                    rawImage.maskable = graphic.maskable;
                    if (!rawImage.enabled) { gaps.Add("submesh_sdk_raw_image_disabled:" + i); continue; }
                    var modified = rawImage.materialForRendering;
                    if (modified == null) { gaps.Add("submesh_mask_modified_material_missing:" + i); continue; }
                    canvasRenderer.SetMaterial(modified, sourceMaterial.mainTexture);
                    canvasRenderer.materialCount = 1;
                    var row = ReadRenderer(i, binding, rawImage, canvasRenderer, modified, gaps);
                    rows.Add(row);
                }
            }
            var pose = ReadPose(graphic == null ? null : graphic.initialSkinName, true,
                graphic == null ? null : graphic.startingAnimation, true);
            bool pairsVerified = VerifyMaterialPairs(bindings, gaps);
            bool emptyVerified = instructions != null && instructions.Length == 0 && pose.emptyPoseVerified && pairsVerified;
            if (instructions != null && instructions.Length == 0 && !emptyVerified)
            {
                gaps.Add("sdk_zero_submesh_pose_not_proven_initialized_and_empty");
                foreach (var gap in pose.gaps ?? Array.Empty<string>()) gaps.Add("pose:" + gap);
            }
            lastGaps = gaps.Distinct(StringComparer.Ordinal).ToArray();
            bool rowsVerified = instructions != null && instructions.Length > 0 && rows.Count == instructions.Length;
            bool verified = (rowsVerified || emptyVerified) && pairsVerified && lastGaps.Length == 0;
            nativeMaterialVerified = verified;
            string status = emptyVerified ? "verified_empty_pose_with_persistent_material_pairs" :
                rowsVerified && lastGaps.Length == 0 ? "verified_active_submesh_materials" : "unverified";
            return BuildReadback(instructionType, instructions == null ? 0 : instructions.Length, rows,
                lastGaps, pose, pairsVerified, status, verified);
        }

        /// <summary>Strict, read-only saved-prefab material verification. It never repairs component state.</summary>
        public Readback ReadSaved()
        {
            return ReadSaved(null, null, false, null, false);
        }

        public Readback ReadSaved(MaterialBinding[] expectedBindings, string expectedSkin, bool expectedSkinKnown,
            string expectedAnimation, bool expectedAnimationKnown)
        {
            var rows = new List<RendererRow>();
            var gaps = new List<string>();
            if (!enabled || (gameObject.activeInHierarchy && !sdkEventAttached))
                gaps.Add("sdk_material_update_event_not_attached");
            object[] instructions;
            string instructionType;
            if (!TryReadInstructions(graphic, out instructions, out instructionType, out var readGap))
                gaps.Add(readGap);
            else if (instructions.Length > 0 && graphic.canvasRenderers != null &&
                     graphic.canvasRenderers.Count != instructions.Length)
                gaps.Add("saved_submesh_canvas_renderer_count_mismatch");
            else if (instructions.Length > 0)
            {
                for (int i = 0; i < instructions.Length; i++)
                {
                    var sourceMaterial = ReadMember<Material>(instructions[i], "material");
                    var matches = (bindings ?? Array.Empty<MaterialBinding>()).Where(binding => binding != null && binding.sourceMaterial == sourceMaterial).ToArray();
                    if (matches.Length != 1) { gaps.Add("saved_submesh_source_material_unmapped_or_ambiguous:" + i); continue; }
                    var renderer = graphic.canvasRenderers[i];
                    var rawImage = renderer == null ? null : renderer.GetComponent<RawImage>();
                    var actual = renderer == null ? null : renderer.GetMaterial();
                    var expectedModified = rawImage == null ? null : rawImage.materialForRendering;
                    rows.Add(ReadRenderer(i, matches[0], rawImage, renderer, expectedModified, gaps));
                    if (actual != expectedModified) gaps.Add("saved_canvas_renderer_material_differs_from_maskable_raw_image:" + i);
                    if (rawImage == null || rawImage.texture != sourceMaterial.mainTexture)
                        gaps.Add("saved_raw_image_texture_reference_mismatch:" + i);
                    if (rawImage != null && !rawImage.enabled)
                        gaps.Add("saved_sdk_raw_image_disabled:" + i);
                }
            }
            var pose = ReadPose(expectedSkin, expectedSkinKnown, expectedAnimation, expectedAnimationKnown);
            var expectedPairBindings = expectedBindings ?? bindings;
            bool pairsVerified = VerifyMaterialPairs(expectedPairBindings, gaps) && VerifyPersistedPairsMatch(expectedPairBindings, bindings, gaps);
            bool emptyVerified = instructions != null && instructions.Length == 0 && pose.emptyPoseVerified && pairsVerified;
            if (instructions != null && instructions.Length == 0 && !emptyVerified)
            {
                gaps.Add("saved_zero_submesh_pose_not_proven_initialized_and_empty");
                foreach (var gap in pose.gaps ?? Array.Empty<string>()) gaps.Add("pose:" + gap);
            }
            var distinctGaps = gaps.Distinct(StringComparer.Ordinal).ToArray();
            bool rowsVerified = instructions != null && instructions.Length > 0 && rows.Count == instructions.Length;
            string status = emptyVerified ? "verified_empty_pose_with_persistent_material_pairs" :
                rowsVerified && distinctGaps.Length == 0 ? "verified_active_submesh_materials" : "unverified";
            bool verified = (rowsVerified || emptyVerified) && pairsVerified && distinctGaps.Length == 0;
            return BuildReadback(instructionType, instructions == null ? 0 : instructions.Length, rows,
                distinctGaps, pose, pairsVerified, status, verified);
        }

        Readback BuildReadback(string instructionType, int instructionCount, List<RendererRow> rows, string[] gaps,
            PoseReadback pose, bool pairsVerified, string status = "unverified", bool verified = false)
        {
            int rendererCount = graphic == null || graphic.canvasRenderers == null ? 0 : graphic.canvasRenderers.Count;
            return new Readback { sourceComponentId = sourceComponentId, sdkInstructionsType = instructionType,
                instructionCount = instructionCount, canvasRendererCount = rendererCount,
                sdkEventAttached = sdkEventAttached, materialPairsVerified = pairsVerified,
                nativeMaterialStatus = status, nativeMaterialVerified = verified, pose = pose,
                textureVerificationMethod = "serialized RawImage.texture identity plus exact Spine callback SetMaterial(material, texture); Unity CanvasRenderer exposes no public texture getter",
                gaps = gaps, renderers = rows.ToArray() };
        }

        PoseReadback ReadPose(string expectedSkin, bool expectedSkinKnown,
            string expectedAnimation, bool expectedAnimationKnown)
        {
            var gaps = new List<string>();
            var activeDrawable = new List<string>();
            var runtimeFieldFlags = InstanceFlags;
            var skeletonField = typeof(SkeletonGraphic).GetField("skeleton", runtimeFieldFlags);
            var stateField = typeof(SkeletonGraphic).GetField("state", runtimeFieldFlags);
            var skeleton = skeletonField == null || graphic == null ? null : skeletonField.GetValue(graphic) as global::Spine.Skeleton;
            var state = stateField == null || graphic == null ? null : stateField.GetValue(graphic) as global::Spine.AnimationState;
            bool initialized = skeleton != null;
            bool stateInitialized = state != null;
            if (!initialized) gaps.Add("spine_skeleton_runtime_not_initialized");
            if (!stateInitialized) gaps.Add("spine_animation_state_runtime_not_initialized");
            var data = skeleton == null ? null : skeleton.Data;
            var assetData = graphic == null || graphic.skeletonDataAsset == null
                ? null : graphic.skeletonDataAsset.GetSkeletonData(false);
            bool dataIdentity = data != null && assetData != null && ReferenceEquals(data, assetData);
            if (!dataIdentity) gaps.Add("spine_runtime_skeleton_data_identity_unverified");
            int bones = data == null || data.Bones == null ? 0 : data.Bones.Count;
            int slots = skeleton == null || skeleton.Slots == null ? 0 : skeleton.Slots.Count;
            int nonNull = 0;
            for (int i = 0; i < slots; i++)
            {
                var slot = skeleton.Slots.Items[i];
                if (slot == null) { gaps.Add("spine_runtime_slot_null:" + i); continue; }
                var attachment = slot.Attachment;
                if (attachment == null) continue;
                nonNull++;
                if (attachment is global::Spine.RegionAttachment || attachment is global::Spine.MeshAttachment)
                    activeDrawable.Add(slot.Data.Name + "/" + attachment.Name + "/" + attachment.GetType().Name);
            }
            var current = state == null ? null : state.GetCurrent(0);
            string actualSkin = skeleton == null || skeleton.Skin == null ? null : skeleton.Skin.Name;
            string actualAnimation = current == null || current.Animation == null ? null : current.Animation.Name;
            float trackTime = current == null ? 0f : current.TrackTime;
            // Spine 3.8 represents the authored default skin as Skeleton.Skin == null
            // in the Editor validation path while still resolving attachments through
            // SkeletonData.DefaultSkin. Preserve the serialized request and prove this
            // exact runtime alias; do not accept a missing or different named skin.
            string runtimeDefaultSkinName = data == null || data.DefaultSkin == null ? null : data.DefaultSkin.Name;
            bool defaultSkinRuntimeNull = expectedSkinKnown && !String.IsNullOrEmpty(expectedSkin) &&
                expectedSkin == runtimeDefaultSkinName && String.IsNullOrEmpty(actualSkin);
            bool skinVerified = !expectedSkinKnown ||
                ((graphic != null && graphic.initialSkinName == expectedSkin) &&
                 (String.IsNullOrEmpty(expectedSkin) ? String.IsNullOrEmpty(actualSkin) :
                    actualSkin == expectedSkin || defaultSkinRuntimeNull));
            bool animationVerified = !expectedAnimationKnown ||
                ((graphic != null && graphic.startingAnimation == expectedAnimation) &&
                 (String.IsNullOrEmpty(expectedAnimation) ? String.IsNullOrEmpty(actualAnimation) : actualAnimation == expectedAnimation) &&
                 Math.Abs(trackTime) <= 0.000001f);
            if (!skinVerified) gaps.Add("spine_requested_skin_runtime_mismatch:requested=" + (expectedSkin ?? "<null>") +
                ";component=" + (graphic == null ? "<null>" : graphic.initialSkinName ?? "<null>") +
                ";runtime=" + (actualSkin ?? "<null>") + ";dataDefault=" + (runtimeDefaultSkinName ?? "<null>") +
                ";defaultNullAlias=" + defaultSkinRuntimeNull);
            if (!animationVerified) gaps.Add("spine_requested_animation_runtime_mismatch");
            bool noDrawable = activeDrawable.Count == 0;
            bool emptyRendererState = graphic != null && graphic.canvasRenderer != null &&
                graphic.canvasRenderer.GetMesh() == null &&
                (graphic.canvasRenderers ?? new List<CanvasRenderer>()).All(renderer => renderer != null &&
                    !renderer.gameObject.activeSelf && renderer.GetMesh() == null);
            bool empty = initialized && stateInitialized && dataIdentity && expectedSkinKnown && expectedAnimationKnown &&
                skinVerified && animationVerified && noDrawable && emptyRendererState;
            return new PoseReadback { initialized = initialized, animationStateInitialized = stateInitialized,
                sourceDataIdentityVerified = dataIdentity, dataVersion = data == null ? null : data.Version,
                boneCount = bones, slotCount = slots, activeDrawableAttachmentCount = activeDrawable.Count,
                nonNullAttachmentCount = nonNull, sourceSkin = expectedSkin, actualSkin = actualSkin,
                sourceSkinVerified = skinVerified, runtimeDefaultSkinName = runtimeDefaultSkinName,
                defaultSkinRuntimeNull = defaultSkinRuntimeNull, sourceAnimation = expectedAnimation,
                actualAnimation = actualAnimation, trackTime = trackTime,
                sourceAnimationVerified = animationVerified, allSlotsHaveNoDrawableAttachment = noDrawable,
                emptyRendererStateVerified = emptyRendererState, emptyPoseVerified = empty,
                gaps = gaps.ToArray(), activeDrawableAttachments = activeDrawable.ToArray() };
        }

        static bool VerifyMaterialPairs(MaterialBinding[] values, List<string> gaps)
        {
            if (values == null || values.Length == 0) { gaps.Add("persistent_material_pairs_missing"); return false; }
            bool verified = true;
            foreach (var binding in values)
            {
                if (binding == null || binding.sourceMaterial == null || binding.graphicMaterial == null ||
                    binding.sourceMaterial.mainTexture == null || binding.graphicMaterial.mainTexture != binding.sourceMaterial.mainTexture ||
                    String.IsNullOrWhiteSpace(binding.graphicMaterialAssetPath) || String.IsNullOrWhiteSpace(binding.graphicMaterialAssetGuid) ||
                    String.IsNullOrWhiteSpace(binding.graphicTextureAssetPath) || String.IsNullOrWhiteSpace(binding.graphicTextureAssetGuid) ||
                    binding.graphicMaterial.shader == null || binding.graphicMaterial.shader.name != ExpectedUiShaderName ||
                    !binding.graphicMaterial.HasProperty("_SrcBlend") || !binding.graphicMaterial.HasProperty("_DstBlend") ||
                    binding.graphicMaterial.GetInt("_SrcBlend") != binding.expectedSrcBlend ||
                    binding.graphicMaterial.GetInt("_DstBlend") != binding.expectedDstBlend)
                {
                    gaps.Add("persistent_material_pair_unverified:" + (binding == null ? "null" : binding.sourceMaterialId));
                    verified = false;
                }
            }
            if (values.Where(binding => binding != null).Select(binding => binding.sourceMaterialId)
                    .Distinct(StringComparer.Ordinal).Count() != values.Length)
            { gaps.Add("persistent_material_pair_identity_duplicate"); verified = false; }
            return verified;
        }

        static bool VerifyPersistedPairsMatch(MaterialBinding[] expected, MaterialBinding[] actual, List<string> gaps)
        {
            if (expected == null || actual == null || expected.Length != actual.Length)
            { gaps.Add("persisted_material_pair_denominator_mismatch"); return false; }
            var validActual = actual.Where(row => row != null).ToArray();
            if (validActual.Select(row => row.sourceMaterialId).Distinct(StringComparer.Ordinal).Count() != validActual.Length)
            { gaps.Add("persisted_material_pair_identity_duplicate"); return false; }
            var byId = validActual.ToDictionary(row => row.sourceMaterialId, StringComparer.Ordinal);
            foreach (var row in expected)
            {
                if (row == null || !byId.TryGetValue(row.sourceMaterialId, out var saved) ||
                    saved.sourceMaterial != row.sourceMaterial || saved.graphicMaterial != row.graphicMaterial ||
                    saved.graphicMaterialAssetPath != row.graphicMaterialAssetPath ||
                    saved.graphicMaterialAssetGuid != row.graphicMaterialAssetGuid ||
                    saved.graphicTextureAssetPath != row.graphicTextureAssetPath ||
                    saved.graphicTextureAssetGuid != row.graphicTextureAssetGuid ||
                    saved.textureSourceId != row.textureSourceId || saved.blendMode != row.blendMode ||
                    saved.expectedSrcBlend != row.expectedSrcBlend || saved.expectedDstBlend != row.expectedDstBlend)
                { gaps.Add("persisted_material_pair_identity_mismatch:" + (row == null ? "null" : row.sourceMaterialId)); return false; }
            }
            return true;
        }

        static RendererRow ReadRenderer(int index, MaterialBinding binding, RawImage rawImage, CanvasRenderer renderer,
            Material expectedModified, List<string> gaps)
        {
            var actual = renderer == null ? null : renderer.GetMaterial();
            var baseMaterial = rawImage == null ? null : rawImage.material;
            bool materialRef = actual == expectedModified;
            var texture = rawImage == null ? null : rawImage.texture;
            bool textureRef = texture != null && binding.sourceMaterial != null &&
                texture == binding.sourceMaterial.mainTexture && actual != null && actual.mainTexture == texture;
            bool rawMaterialRef = rawImage != null && rawImage.material == binding.graphicMaterial;
            bool blend = binding.graphicMaterial != null && binding.graphicMaterial.shader != null &&
                binding.graphicMaterial.shader.name == ExpectedUiShaderName &&
                binding.graphicMaterial.HasProperty("_SrcBlend") && binding.graphicMaterial.HasProperty("_DstBlend") &&
                binding.graphicMaterial.GetInt("_SrcBlend") == binding.expectedSrcBlend &&
                binding.graphicMaterial.GetInt("_DstBlend") == binding.expectedDstBlend;
            if (!materialRef) gaps.Add("canvas_renderer_material_readback_mismatch:" + index);
            if (!textureRef) gaps.Add("canvas_renderer_texture_readback_mismatch:" + index);
            if (!rawMaterialRef) gaps.Add("raw_image_profile_material_reference_mismatch:" + index);
            if (!blend) gaps.Add("ui_material_blend_readback_mismatch:" + index);
            var stencil = ReadStencilState(rawImage, baseMaterial, actual);
            if (!stencil.ancestryVerified) gaps.Add("stencil_mask_ancestry_readback_mismatch:" + index);
            if (!stencil.shaderMatches) gaps.Add("stencil_material_shader_differs_from_base:" + index);
            if (!stencil.propertiesMatch) gaps.Add("stencil_material_non_stencil_properties_differ:" + index);
            if (!stencil.configurationVerified) gaps.Add("stencil_material_configuration_differs_from_mask_ancestry:" + index);
            if (stencil.depth > 0 && !stencil.transientVariantVerified)
                gaps.Add("stencil_material_transient_variant_unverified:" + index);
            bool baseReference = baseMaterial != null && rawMaterialRef && binding.graphicMaterial == baseMaterial &&
                !String.IsNullOrWhiteSpace(binding.graphicMaterialAssetPath) &&
                !String.IsNullOrWhiteSpace(binding.graphicMaterialAssetGuid) &&
                !String.IsNullOrWhiteSpace(binding.graphicTextureAssetPath) &&
                !String.IsNullOrWhiteSpace(binding.graphicTextureAssetGuid) &&
                baseMaterial.shader != null && baseMaterial.shader.name == ExpectedUiShaderName &&
                baseMaterial.mainTexture == binding.sourceMaterial.mainTexture;
            if (!baseReference) gaps.Add("persistent_graphic_base_material_reference_unverified:" + index);
            return new RendererRow { index = index, sourceMaterialId = binding.sourceMaterialId,
                textureSourceId = binding.textureSourceId, blendMode = binding.blendMode,
                actualMaterialShader = actual == null || actual.shader == null ? null : actual.shader.name,
                actualMaterialName = actual == null ? null : actual.name,
                actualTextureName = texture == null ? null : texture.name,
                baseMaterialAssetPath = binding.graphicMaterialAssetPath,
                baseMaterialAssetGuid = binding.graphicMaterialAssetGuid,
                baseMaterialShader = baseMaterial == null || baseMaterial.shader == null ? null : baseMaterial.shader.name,
                baseMaterialTextureAssetPath = binding.graphicTextureAssetPath,
                baseMaterialTextureGuid = binding.graphicTextureAssetGuid,
                stencilDepth = stencil.depth, stencilRootSortCanvasPath = stencil.rootCanvasPath,
                stencilMaskAncestorSourceIds = stencil.ancestorSourceIds,
                stencilReference = stencil.reference, stencilComparison = stencil.comparison,
                stencilOperation = stencil.operation, stencilReadMask = stencil.readMask,
                stencilWriteMask = stencil.writeMask, stencilColorMask = stencil.colorMask,
                stencilUseAlphaClip = stencil.useAlphaClip,
                rawImageEnabled = rawImage != null && rawImage.enabled,
                rawImageMaskable = rawImage != null && rawImage.maskable,
                rawImageMaterialReferenceVerified = rawMaterialRef,
                materialReferenceVerified = materialRef, textureReferenceVerified = textureRef, blendVerified = blend,
                baseMaterialPersistentReferenceVerified = baseReference,
                modifiedMaterialShaderMatchesBase = stencil.shaderMatches,
                nonStencilMaterialPropertiesMatch = stencil.propertiesMatch,
                stencilAncestryVerified = stencil.ancestryVerified,
                stencilConfigurationVerified = stencil.configurationVerified,
                transientStencilVariantVerified = stencil.transientVariantVerified };
        }

        sealed class StencilReadback
        {
            public int depth, reference, comparison, operation, readMask, writeMask, colorMask, useAlphaClip;
            public string rootCanvasPath;
            public string[] ancestorSourceIds = Array.Empty<string>();
            public bool ancestryVerified, shaderMatches, propertiesMatch, configurationVerified, transientVariantVerified;
        }

        static StencilReadback ReadStencilState(RawImage image, Material baseMaterial, Material actual)
        {
            var result = new StencilReadback();
            if (image == null || baseMaterial == null || actual == null) return result;
            var rootCanvas = MaskUtilities.FindRootSortOverrideCanvas(image.transform);
            result.rootCanvasPath = TransformPath(rootCanvas);
            var ancestorIds = new List<string>();
            bool allMapped = true;
            for (var current = image.transform.parent; current != null; current = current.parent)
            {
                foreach (var mask in current.GetComponents<Mask>())
                {
                    if (mask == null || !mask.MaskEnabled() || mask.graphic == null || !mask.graphic.IsActive()) continue;
                    var identity = mask.GetComponent<NativeStaticMaskIdentity>();
                    if (identity == null || String.IsNullOrWhiteSpace(identity.sourceId))
                    { ancestorIds.Add(""); allMapped = false; }
                    else ancestorIds.Add(identity.sourceId);
                    break; // Match MaskUtilities.GetStencilDepth: at most one stencil per ancestor Transform.
                }
                if (current == rootCanvas) break;
            }
            result.ancestorSourceIds = ancestorIds.ToArray();
            int sdkDepth = MaskUtilities.GetStencilDepth(image.transform, rootCanvas);
            result.depth = image.maskable ? sdkDepth : 0;
            result.ancestryVerified = allMapped && ancestorIds.Count == sdkDepth &&
                ancestorIds.Distinct(StringComparer.Ordinal).Count() == ancestorIds.Count;
            result.shaderMatches = baseMaterial.shader != null && actual.shader == baseMaterial.shader;
            result.propertiesMatch = AreNonStencilPropertiesEqual(baseMaterial, actual);
            result.reference = ReadInt(actual, "_Stencil"); result.comparison = ReadInt(actual, "_StencilComp");
            result.operation = ReadInt(actual, "_StencilOp"); result.readMask = ReadInt(actual, "_StencilReadMask");
            result.writeMask = ReadInt(actual, "_StencilWriteMask"); result.colorMask = ReadInt(actual, "_ColorMask");
            result.useAlphaClip = ReadInt(actual, "_UseUIAlphaClip");
            if (result.depth == 0)
            {
                result.configurationVerified = actual == baseMaterial && result.shaderMatches && result.propertiesMatch;
                return result;
            }

            int stencilId = result.depth < 31 ? (1 << result.depth) - 1 : -1;
            result.configurationVerified = stencilId >= 0 && HasStencilProperties(baseMaterial) &&
                result.reference == stencilId && result.comparison == (int)CompareFunction.Equal &&
                result.operation == (int)StencilOp.Keep && result.readMask == stencilId &&
                result.writeMask == 0 && result.colorMask == (int)ColorWriteMask.All &&
                result.useAlphaClip == 0 && !actual.IsKeywordEnabled("UNITY_UI_ALPHACLIP");
            result.transientVariantVerified = actual != baseMaterial &&
                (actual.hideFlags & HideFlags.HideAndDontSave) == HideFlags.HideAndDontSave &&
                result.shaderMatches && result.propertiesMatch && result.configurationVerified && result.ancestryVerified;
            return result;
        }

        static readonly HashSet<string> StencilPropertyNames = new HashSet<string>(StringComparer.Ordinal)
        { "_Stencil", "_StencilComp", "_StencilOp", "_StencilReadMask", "_StencilWriteMask", "_ColorMask", "_UseUIAlphaClip" };

        static bool HasStencilProperties(Material material)
        {
            return material != null && StencilPropertyNames.All(material.HasProperty);
        }

        static int ReadInt(Material material, string property)
        {
            if (material == null || !material.HasProperty(property)) return Int32.MinValue;
            return Mathf.RoundToInt(material.GetFloat(property));
        }

        static bool AreNonStencilPropertiesEqual(Material left, Material right)
        {
            if (left == null || right == null || left.shader == null || left.shader != right.shader ||
                left.mainTexture != right.mainTexture || left.renderQueue != right.renderQueue ||
                left.enableInstancing != right.enableInstancing || left.doubleSidedGI != right.doubleSidedGI ||
                left.globalIlluminationFlags != right.globalIlluminationFlags) return false;
            var leftKeywords = (left.shaderKeywords ?? Array.Empty<string>()).Where(k => k != "UNITY_UI_ALPHACLIP").OrderBy(k => k, StringComparer.Ordinal);
            var rightKeywords = (right.shaderKeywords ?? Array.Empty<string>()).Where(k => k != "UNITY_UI_ALPHACLIP").OrderBy(k => k, StringComparer.Ordinal);
            if (!leftKeywords.SequenceEqual(rightKeywords)) return false;
            var shader = left.shader;
            for (int i = 0; i < shader.GetPropertyCount(); i++)
            {
                var name = shader.GetPropertyName(i);
                if (StencilPropertyNames.Contains(name)) continue;
                switch (shader.GetPropertyType(i))
                {
                    case ShaderPropertyType.Color: if (left.GetColor(name) != right.GetColor(name)) return false; break;
                    case ShaderPropertyType.Vector: if (left.GetVector(name) != right.GetVector(name)) return false; break;
                    case ShaderPropertyType.Float:
                    case ShaderPropertyType.Range: if (!left.GetFloat(name).Equals(right.GetFloat(name))) return false; break;
                    case ShaderPropertyType.Int: if (left.GetInt(name) != right.GetInt(name)) return false; break;
                    case ShaderPropertyType.Texture:
                        if (left.GetTexture(name) != right.GetTexture(name) ||
                            left.GetTextureScale(name) != right.GetTextureScale(name) ||
                            left.GetTextureOffset(name) != right.GetTextureOffset(name)) return false;
                        break;
                    default: return false;
                }
            }
            return true;
        }

        static string TransformPath(Transform value)
        {
            if (value == null) return "";
            var names = new Stack<string>();
            for (var current = value; current != null; current = current.parent) names.Push(current.name);
            return String.Join("/", names.ToArray());
        }

        static void ValidateBindings(MaterialBinding[] values)
        {
            if (values == null || values.Length == 0 || values.Any(binding => binding == null ||
                String.IsNullOrWhiteSpace(binding.sourceMaterialId) || String.IsNullOrWhiteSpace(binding.textureSourceId) ||
                String.IsNullOrWhiteSpace(binding.blendMode) || binding.sourceMaterial == null || binding.graphicMaterial == null))
                throw new ArgumentException("Complete exact Spine material bindings are required.");
            if (values.Select(binding => binding.sourceMaterial).Distinct().Count() != values.Length ||
                values.Select(binding => binding.sourceMaterialId).Distinct(StringComparer.Ordinal).Count() != values.Length)
                throw new ArgumentException("Spine source Material bindings must be unique by object and source identity.");
        }

        static bool TryReadInstructions(SkeletonGraphic value, out object[] items, out string instructionType, out string gap)
        {
            items = null; instructionType = null; gap = null;
            if (value == null) { gap = "skeleton_graphic_missing"; return false; }
            var field = typeof(SkeletonGraphic).GetField("currentInstructions", InstanceFlags);
            if (field == null || field.FieldType.FullName != ExpectedSdkInstructionsType)
            { gap = "pinned_sdk_current_instructions_field_mismatch"; return false; }
            var instruction = field.GetValue(value);
            if (instruction == null) { gap = "sdk_current_instructions_null"; return false; }
            instructionType = instruction.GetType().FullName;
            var list = GetMember(instruction, "submeshInstructions");
            if (list == null) { gap = "sdk_submesh_instructions_missing"; return false; }
            var listType = list.GetType();
            var count = GetMember(list, "Count");
            var array = GetMember(list, "Items") as Array;
            if (!(count is int length) || array == null || length < 0 || length > array.Length)
            { gap = "sdk_submesh_instruction_layout_mismatch"; return false; }
            items = new object[length];
            for (int i = 0; i < length; i++)
            {
                items[i] = array.GetValue(i);
                if (items[i] == null || ReadMember<Material>(items[i], "material") == null)
                { gap = "sdk_submesh_instruction_material_missing:" + i; items = null; return false; }
            }
            return true;
        }

        static T ReadMember<T>(object value, string name) where T : class
        { return GetMember(value, name) as T; }

        static object GetMember(object value, string name)
        {
            if (value == null) return null;
            var type = value.GetType();
            var field = type.GetField(name, InstanceFlags);
            if (field != null) return field.GetValue(value);
            var property = type.GetProperty(name, InstanceFlags);
            return property != null && property.CanRead ? property.GetValue(value, null) : null;
        }

    }
}
