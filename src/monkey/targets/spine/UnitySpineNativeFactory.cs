// Unity Editor factory for source-exact, static Spine bindings.
// The factory invokes only Spine data parsing and component serialization; it
// never loads or executes recovered game scripts.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using Spine;
using Spine.Unity;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;

namespace Monkey.Targets.Spine
{
    public static class UnitySpineNativeFactory
    {
        public const string SourceProfile = "cocos24-builtin-spine-material-v1";
        public const string ShaderName = "Monkey/SpineSourceProfile/Colored";
        public const int DiagnosticStackMaxChars = 10000;

        public sealed class DataAssetCreateException : Exception
        {
            public readonly string sourceAssetId;
            public readonly string phase;
            public readonly string originalExceptionType;
            public readonly string originalStackTrace;

            public DataAssetCreateException(string sourceId, string failedPhase, Exception inner)
                : base("Spine data asset creation failed at " + failedPhase + ": " +
                       (inner == null ? "unknown exception" : inner.Message), inner)
            {
                sourceAssetId = sourceId;
                phase = failedPhase;
                originalExceptionType = inner == null ? "Exception" : inner.GetType().FullName;
                var full = inner == null ? String.Empty : inner.ToString();
                originalStackTrace = full.Length <= DiagnosticStackMaxChars
                    ? full : full.Substring(0, DiagnosticStackMaxChars) + "\n...[bounded]";
            }
        }

        public enum RendererKind { SkeletonAnimation, SkeletonGraphic }

        [Serializable] public sealed class MaterialVariantSpec
        {
            public string blendMode;
            public string materialAssetPath;
            public string graphicMaterialAssetPath;
            public int sourceSlotCountAcrossAsset;
            public string sourceSlotCountScope;
        }

        [Serializable] public sealed class AtlasPageSpec
        {
            public string sourceAtlasPage;
            public string nativeAtlasPage;
            public string sourceTextureSourceId;
            public string textureAssetPath;
            public string normalMaterialAssetPath;
            public string graphicNormalMaterialAssetPath;
            public MaterialVariantSpec[] variants;
        }

        [Serializable] public sealed class DataAssetSpec
        {
            public string sourceAssetId;
            public string skeletonTextAssetPath;
            public string skeletonSha256;
            public string atlasTextAssetPath;
            public string atlasSha256;
            public string atlasAssetPath;
            public string skeletonDataAssetPath;
            public string shaderAssetPath;
            public string shaderSha256;
            public string graphicShaderAssetPath;
            public string graphicShaderSha256;
            public string graphicShaderName;
            public string expectedSpineVersion;
            public float scale;
            public bool premultipliedAlpha;
            public AtlasPageSpec[] pages;
            public string[] requiredAnimations;
            public string[] requiredSkins;
        }

        [Serializable] public sealed class DataAssetReadback
        {
            public string sourceAssetId;
            public string skeletonDataAssetPath;
            public string skeletonDataAssetGuid;
            public string atlasAssetPath;
            public string atlasAssetGuid;
            public string skeletonSha256;
            public string atlasSha256;
            public string spineVersion;
            public string sourceMaterialProfile;
            public string profileShaderName;
            public string profileShaderSha256;
            public string uiGraphicShaderName;
            public string uiGraphicShaderSha256;
            public bool uiGraphicShaderVerified;
            public bool premultipliedAlpha;
            public float scale;
            public bool scaleVerified;
            public int boneCount;
            public int slotCount;
            public int skinCount;
            public int animationCount;
            public bool nativeAssetIdentityVerified;
            public bool savedSourceReferencesVerified;
            public bool sourceProfileMaterialsVerified;
            public bool staticDataVerified;
            public string[] animations;
            public string[] skins;
            public PageMaterialReadback[] pages;
            public string[] gaps;
        }

        [Serializable] public sealed class PageMaterialReadback
        {
            public string sourceAtlasPage;
            public string nativeAtlasPage;
            public string sourceTextureSourceId;
            public string textureGuid;
            public string normalMaterialGuid;
            public string graphicNormalMaterialPath;
            public string graphicNormalMaterialGuid;
            public string[] variantModes;
            public string[] variantMaterialGuids;
            public string[] graphicVariantMaterialPaths;
            public string[] graphicVariantMaterialGuids;
            public bool referencesVerified;
        }

        [Serializable] public sealed class ComponentReadback
        {
            public string sourceComponentId;
            public string rendererKind;
            public string nativeComponentType;
            public string sourceDataAssetId;
            public string nativeDataAssetPath;
            public string nativeDataAssetGuid;
            public bool staticDataBound;
            public bool sourceDataUnbound;
            public bool enabled;
            public bool componentTypeVerified;
            public bool dataReferenceVerified;
            public bool dataAssetContentVerified;
            // True when every statically mappable native field (including
            // SkeletonGraphic mesh-generator PMA) was applied and read back.
            // This can coexist with fieldsVerified=false when source-only
            // runtime fields remain explicit gaps.
            public bool mappedStaticFieldsVerified;
            public bool fieldsVerified;
            public bool pmaMaterialProfileRequired;
            public bool pmaMaterialProfileVerified;
            public bool pmaMaterialProfileNotApplicable;
            public bool rendererMaterialRequired;
            public bool rendererMaterialVerified;
            public bool allowMultipleCanvasRenderers;
            public int customMaterialOverrideCount;
            public string rendererBaseMaterialShader;
            public string rendererBaseMaterialAssetPath;
            public string rendererBaseMaterialGuid;
            public string rendererMaterialForRenderingShader;
            public string[] canvasRendererMaterialShaders;
            public string[] canvasRendererMaterialAssetPaths;
            public string rendererMainTextureAssetPath;
            public UnitySpineGraphicMaterialPresentation.Readback rendererPresentation;
            public bool nativeComplete;
            public bool dynamicAssignmentUnverified;
            public string[] sourceOnlyFieldGaps;
            public string[] gaps;
        }

        [Serializable] public sealed class StaticPoseReadback
        {
            public string sourceComponentId;
            public string sourceDataAssetId;
            public string nativeDataAssetGuid;
            public string rendererKind;
            public string requestedSkin;
            public string requestedAnimation;
            public string actualSkin;
            public string actualAnimation;
            public float trackTime;
            public bool loop;
            public bool componentEnabled;
            public bool poseVerified;
            public bool sourceCodeExecuted;
            public string timelineStatus;
            public string[] gaps;
        }

        /// <summary>Create the actual Unity Spine renderer selected from target-node evidence.</summary>
        public static Component CreateComponent(GameObject node, string sourceComponentId, RendererKind rendererKind)
        {
            if (node == null) throw new ArgumentNullException(nameof(node));
            if (String.IsNullOrWhiteSpace(sourceComponentId)) throw new ArgumentException("Source component identity is required.", nameof(sourceComponentId));
            Type type;
            if (rendererKind == RendererKind.SkeletonGraphic)
            {
                if (!(node.transform is RectTransform))
                    throw new InvalidOperationException("SkeletonGraphic requires a target RectTransform; importer must establish and verify UI node context first.");
                type = typeof(SkeletonGraphic);
            }
            else if (rendererKind == RendererKind.SkeletonAnimation)
                type = typeof(SkeletonAnimation);
            else throw new ArgumentOutOfRangeException(nameof(rendererKind));

            var component = node.AddComponent(type) as Component;
            if (component == null || component.GetType() != type)
                throw new InvalidOperationException("UNITY_SPINE_NATIVE_COMPONENT_CREATE_FAILED: " + sourceComponentId);
            var behaviour = component as Behaviour;
            if (behaviour != null) behaviour.enabled = false;
            return component;
        }

        /// <summary>
        /// Create and save a real SpineAtlasAsset/SkeletonDataAsset from exact
        /// imported Unity TextAssets, Texture2Ds and a source-pinned shader.
        /// Caller owns exact sourceId-to-path resolution and target scale.
        /// </summary>
        public static DataAssetReadback CreateDataAsset(DataAssetSpec spec)
        {
            ValidateSpec(spec);
            var phase = "check_existing_native_asset";
            var existing = AssetDatabase.LoadAssetAtPath<SkeletonDataAsset>(spec.skeletonDataAssetPath);
            if (existing != null)
            {
                var existingReadback = ReadDataAssetAsset(spec);
                if (!existingReadback.nativeAssetIdentityVerified || !existingReadback.savedSourceReferencesVerified ||
                    !existingReadback.scaleVerified || !existingReadback.sourceProfileMaterialsVerified)
                    throw new InvalidOperationException("SPINE_EXISTING_NATIVE_ASSET_CONFLICT:" + String.Join(",", existingReadback.gaps));
                return existingReadback;
            }
            var createdPaths = new List<string>();
            var createdFolders = new List<string>();
            try
            {
                phase = "load_source_text_and_shader";
                var skeletonText = AssetDatabase.LoadAssetAtPath<TextAsset>(spec.skeletonTextAssetPath);
                var atlasText = AssetDatabase.LoadAssetAtPath<TextAsset>(spec.atlasTextAssetPath);
                var shader = AssetDatabase.LoadAssetAtPath<Shader>(spec.shaderAssetPath);
                var graphicShader = AssetDatabase.LoadAssetAtPath<Shader>(spec.graphicShaderAssetPath);
                if (skeletonText == null || atlasText == null)
                    throw new InvalidOperationException("SPINE_SOURCE_TEXT_ASSET_MISSING");
                if (shader == null || shader.name != ShaderName || HashAsset(spec.shaderAssetPath) != spec.shaderSha256)
                    throw new InvalidOperationException("SPINE_PROFILE_SHADER_IDENTITY_MISMATCH");
                if (graphicShader == null || graphicShader.name != spec.graphicShaderName ||
                    graphicShader.name != UnitySpineGraphicMaterialPresentation.ExpectedUiShaderName ||
                    HashAsset(spec.graphicShaderAssetPath) != spec.graphicShaderSha256)
                    throw new InvalidOperationException("SPINE_UI_GRAPHIC_SHADER_IDENTITY_MISMATCH");
                if (!String.Equals(HashBytes(skeletonText.bytes), spec.skeletonSha256, StringComparison.OrdinalIgnoreCase) ||
                    !String.Equals(HashBytes(atlasText.bytes), spec.atlasSha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("SPINE_SOURCE_TEXT_ASSET_HASH_MISMATCH");
                if (String.IsNullOrEmpty(skeletonText.name) || !skeletonText.name.Contains(".skel"))
                    throw new InvalidOperationException("SPINE_BINARY_TEXT_ASSET_NAME_MUST_RETAIN_SKEL_EXTENSION");

                phase = "parse_atlas_page_identity";
                var pageNames = ReadAtlasPageNames(atlasText.text);
                if (!pageNames.SequenceEqual(spec.pages.Select(p => p.nativeAtlasPage), StringComparer.Ordinal))
                    throw new InvalidOperationException("SPINE_ATLAS_PAGE_ORDER_OR_IDENTITY_MISMATCH");

                // AssetDatabase.CreateAsset requires every parent folder to be
                // an imported Unity folder. A plain System.IO directory is not
                // enough (and leaves no stable folder GUID/meta). Create every
                // exact material/atlas/data parent with AssetDatabase before
                // any native asset write.
                phase = "register_output_folders";
                createdFolders.AddRange(EnsureAssetDirectoriesForPaths(
                    spec.pages.SelectMany(page => new[] { page.normalMaterialAssetPath, page.graphicNormalMaterialAssetPath }
                        .Concat((page.variants ?? Array.Empty<MaterialVariantSpec>()).SelectMany(variant =>
                            new[] { variant.materialAssetPath, variant.graphicMaterialAssetPath })))
                        .Concat(new[] { spec.atlasAssetPath, spec.skeletonDataAssetPath }).ToArray()));

                var normalMaterials = new Material[spec.pages.Length];
                var graphicNormalMaterials = new Material[spec.pages.Length];
                var variantMaterials = new Dictionary<string, Material>(StringComparer.Ordinal);
                var graphicVariantMaterials = new Dictionary<string, Material>(StringComparer.Ordinal);
                for (int index = 0; index < spec.pages.Length; index++)
                {
                    var page = spec.pages[index];
                    phase = "load_texture:" + page.sourceAtlasPage;
                    var texture = LoadSpinePageTexture(page);
                    phase = "create_material:" + page.sourceAtlasPage + ":normal";
                    normalMaterials[index] = CreateProfileMaterial(spec, shader, texture, page,
                        "normal", page.normalMaterialAssetPath, createdPaths);
                    graphicNormalMaterials[index] = CreateGraphicProfileMaterial(spec, graphicShader, texture,
                        page, "normal", page.graphicNormalMaterialAssetPath, createdPaths);
                    foreach (var variant in page.variants ?? Array.Empty<MaterialVariantSpec>())
                    {
                        if (variant.sourceSlotCountAcrossAsset <= 0) throw new InvalidOperationException("SPINE_EMPTY_BLEND_VARIANT: " + page.sourceAtlasPage);
                        var variantKey = page.sourceAtlasPage + "\n" + variant.blendMode;
                        if (variantMaterials.ContainsKey(variantKey))
                            throw new InvalidOperationException("SPINE_DUPLICATE_PAGE_BLEND_VARIANT: " + page.sourceAtlasPage + "/" + variant.blendMode);
                        phase = "create_material:" + page.sourceAtlasPage + ":" + variant.blendMode;
                        var material = CreateProfileMaterial(spec, shader, texture, page,
                            variant.blendMode, variant.materialAssetPath, createdPaths);
                        variantMaterials.Add(variantKey, material);
                        var graphicMaterial = CreateGraphicProfileMaterial(spec, graphicShader, texture,
                            page, variant.blendMode, variant.graphicMaterialAssetPath, createdPaths);
                        graphicVariantMaterials.Add(variantKey, graphicMaterial);
                    }
                }

                phase = "create_atlas_asset_instance";
                var atlasAsset = ScriptableObject.CreateInstance<SpineAtlasAsset>();
                if (atlasAsset == null) throw new InvalidOperationException("SPINE_ATLAS_ASSET_INSTANCE_CREATE_FAILED");
                atlasAsset.name = Path.GetFileNameWithoutExtension(spec.atlasAssetPath);
                atlasAsset.atlasFile = atlasText;
                atlasAsset.materials = normalMaterials;
                phase = "save_atlas_asset";
                CreateOwnedAsset(atlasAsset, spec.atlasAssetPath, createdPaths);
                AssetDatabase.SaveAssets();

                phase = "load_saved_atlas_asset";
                var savedAtlasAsset = AssetDatabase.LoadAssetAtPath<SpineAtlasAsset>(spec.atlasAssetPath);
                if (savedAtlasAsset == null || savedAtlasAsset.atlasFile != atlasText ||
                    savedAtlasAsset.materials == null || savedAtlasAsset.materials.Length != normalMaterials.Length)
                    throw new InvalidOperationException("SPINE_ATLAS_ASSET_SAVED_REFERENCE_MISMATCH");
                phase = "parse_saved_atlas";
                var parsedAtlas = savedAtlasAsset.GetAtlas();
                if (parsedAtlas == null || parsedAtlas.Pages == null || parsedAtlas.Pages.Count != spec.pages.Length)
                    throw new InvalidOperationException("SPINE_ATLAS_NATIVE_PARSE_FAILED");
                for (int index = 0; index < spec.pages.Length; index++)
                {
                    var page = parsedAtlas.Pages[index];
                    if (page.name != spec.pages[index].nativeAtlasPage || !ReferenceEquals(page.rendererObject, normalMaterials[index]))
                        throw new InvalidOperationException("SPINE_ATLAS_NATIVE_PAGE_READBACK_MISMATCH: " + spec.pages[index].sourceAtlasPage);
                }

                phase = "create_skeleton_data_asset_instance";
                var dataAsset = SkeletonDataAsset.CreateRuntimeInstance(skeletonText,
                    new AtlasAssetBase[] { savedAtlasAsset }, false, spec.scale);
                if (dataAsset == null) throw new InvalidOperationException("SPINE_SKELETON_DATA_ASSET_INSTANCE_CREATE_FAILED");
                dataAsset.name = Path.GetFileNameWithoutExtension(spec.skeletonDataAssetPath);
                phase = "configure_skeleton_blend_materials";
                ConfigureBlendMaterials(dataAsset, spec, variantMaterials);
                phase = "save_skeleton_data_asset";
                CreateOwnedAsset(dataAsset, spec.skeletonDataAssetPath, createdPaths);
                AssetDatabase.SaveAssets();
                phase = "import_saved_skeleton_data_asset";
                AssetDatabase.ImportAsset(spec.skeletonDataAssetPath, ImportAssetOptions.ForceSynchronousImport);
                AssetDatabase.SaveAssets();

                phase = "read_saved_skeleton_data_asset";
                var saved = AssetDatabase.LoadAssetAtPath<SkeletonDataAsset>(spec.skeletonDataAssetPath);
                var parsed = saved == null ? null : saved.GetSkeletonData(true);
                if (saved == null || parsed == null)
                    throw new InvalidOperationException("SPINE_SKELETON_DATA_NATIVE_PARSE_FAILED");
                return ReadDataAsset(spec, saved, parsed, variantMaterials, graphicNormalMaterials, graphicVariantMaterials);
            }
            catch (Exception error)
            {
                foreach (var path in createdPaths.AsEnumerable().Reverse()) AssetDatabase.DeleteAsset(path);
                DeleteCreatedEmptyFolders(createdFolders);
                AssetDatabase.SaveAssets();
                throw new DataAssetCreateException(spec.sourceAssetId, phase, error);
            }
        }

        /// <summary>Reopen and strictly re-read a previously created native asset from its exact plan paths.</summary>
        public static DataAssetReadback ReadDataAssetAsset(DataAssetSpec spec)
        {
            ValidateSpec(spec);
            var saved = AssetDatabase.LoadAssetAtPath<SkeletonDataAsset>(spec.skeletonDataAssetPath);
            if (saved == null) throw new InvalidOperationException("SPINE_SAVED_SKELETON_DATA_ASSET_MISSING");
            var parsed = saved.GetSkeletonData(true);
            if (parsed == null) throw new InvalidOperationException("SPINE_SAVED_SKELETON_DATA_PARSE_FAILED");
            var variants = new Dictionary<string, Material>(StringComparer.Ordinal);
            var graphicVariants = new Dictionary<string, Material>(StringComparer.Ordinal);
            foreach (var page in spec.pages)
            foreach (var variant in page.variants ?? Array.Empty<MaterialVariantSpec>())
            {
                var material = AssetDatabase.LoadAssetAtPath<Material>(variant.materialAssetPath);
                if (material != null) variants[page.sourceAtlasPage + "\n" + variant.blendMode] = material;
                var graphicMaterial = AssetDatabase.LoadAssetAtPath<Material>(variant.graphicMaterialAssetPath);
                if (graphicMaterial != null) graphicVariants[page.sourceAtlasPage + "\n" + variant.blendMode] = graphicMaterial;
            }
            var graphicNormals = spec.pages.Select(page => AssetDatabase.LoadAssetAtPath<Material>(page.graphicNormalMaterialAssetPath)).ToArray();
            return ReadDataAsset(spec, saved, parsed, variants, graphicNormals, graphicVariants);
        }

        /// <summary>Bind source settings without enabling the recovered component.</summary>
        public static ComponentReadback ApplyComponent(Component component, string sourceComponentId,
            string sourceDataAssetId, SkeletonDataAsset exactDataAsset,
            IDictionary<string, object> explicitTargetFields, bool sourceHasStaticDataReference,
            DataAssetReadback exactDataAssetReadback = null, bool persistentVisiblePose = false)
        {
            var gaps = new List<string>();
            if (component == null || String.IsNullOrWhiteSpace(sourceComponentId))
                return ComponentFailure(sourceComponentId, "carrier_missing");
            bool isGraphic = component.GetType() == typeof(SkeletonGraphic);
            bool isAnimation = component.GetType() == typeof(SkeletonAnimation);
            if (!isGraphic && !isAnimation) return ComponentFailure(sourceComponentId, "unsupported_native_spine_component_type");
            if (isGraphic && sourceHasStaticDataReference)
                ((SkeletonGraphic)component).allowMultipleCanvasRenderers = true;
            if (sourceHasStaticDataReference && exactDataAsset == null)
                gaps.Add("exact_skeleton_data_asset_unresolved:" + sourceDataAssetId);
            if (!sourceHasStaticDataReference && exactDataAsset != null)
                gaps.Add("unexpected_skeleton_data_asset_for_unbound_source");

            var fields = NormalizeTargetFields(component, explicitTargetFields);
            if (persistentVisiblePose) fields["timeScale"] = 0.0;
            var expectedFields = new Dictionary<string, object>(fields, StringComparer.Ordinal);
            bool pma = fields.ContainsKey("pmaVertexColors");
            bool pmaValue = pma && Convert.ToBoolean(fields["pmaVertexColors"]);
            if (isGraphic && pma) fields.Remove("pmaVertexColors");
            UnitySpineBinding.Apply(component, sourceComponentId, exactDataAsset,
                sourceHasStaticDataReference && exactDataAsset != null, fields);
            var behaviour = component as Behaviour;
            if (behaviour != null) behaviour.enabled = persistentVisiblePose;
            if (persistentVisiblePose && sourceHasStaticDataReference && exactDataAsset != null)
                BuildPersistentStaticPose(component, isGraphic && pma ? (bool?)pmaValue : null);
            else if (isGraphic && pma)
            {
                try { SetSkeletonGraphicPmaVertexColors((SkeletonGraphic)component, pmaValue); }
                catch (Exception error) { gaps.Add("skeleton_graphic_pma_vertex_setting_apply_failed:" + error.GetType().Name + ":" + error.Message); }
            }
            if (isGraphic && sourceHasStaticDataReference && exactDataAsset != null && exactDataAssetReadback != null)
            {
                try { ConfigureGraphicMaterialPresentation((SkeletonGraphic)component, sourceComponentId, sourceDataAssetId,
                    exactDataAsset, exactDataAssetReadback); }
                catch (Exception error) { gaps.Add("skeleton_graphic_material_presentation_apply_failed:" + error.GetType().Name + ":" + error.Message); }
            }
            return ReadComponent(sourceComponentId, sourceDataAssetId, component, exactDataAsset,
                sourceHasStaticDataReference, expectedFields, gaps, exactDataAssetReadback, persistentVisiblePose);
        }

        /// <summary>Read a saved/reopened component using the exact sourceId-to-data resolver result.</summary>
        public static ComponentReadback ReadComponent(string sourceComponentId, string sourceDataAssetId,
            Component component, SkeletonDataAsset exactDataAsset, bool sourceHasStaticDataReference,
            IDictionary<string, object> expectedTargetFields, IList<string> inheritedGaps = null,
            DataAssetReadback exactDataAssetReadback = null, bool persistentVisiblePose = false)
        {
            var gaps = new List<string>();
            if (inheritedGaps != null) foreach (var gap in inheritedGaps) AddGap(gaps, gap);
            if (component == null) return ComponentFailure(sourceComponentId, "saved_component_missing");
            var type = component.GetType();
            bool isGraphic = type == typeof(SkeletonGraphic);
            bool isAnimation = type == typeof(SkeletonAnimation);
            if (!isGraphic && !isAnimation) AddGap(gaps, "unsupported_native_spine_component_type");
            var behaviour = component as Behaviour;
            bool enabled = behaviour != null && behaviour.enabled;
            if (enabled != persistentVisiblePose)
                AddGap(gaps, persistentVisiblePose ? "persistent_spine_renderer_not_enabled" : "spine_component_enabled");

            var savedData = ReadDataReference(component);
            bool dataVerified = false;
            string dataPath = null, dataGuid = null;
            if (sourceHasStaticDataReference)
            {
                if (exactDataAsset == null) AddGap(gaps, "exact_skeleton_data_asset_unresolved:" + sourceDataAssetId);
                else
                {
                    dataPath = AssetDatabase.GetAssetPath(exactDataAsset);
                    dataGuid = String.IsNullOrEmpty(dataPath) ? null : AssetDatabase.AssetPathToGUID(dataPath);
                    dataVerified = savedData == exactDataAsset && !String.IsNullOrEmpty(dataGuid);
                    if (!dataVerified) AddGap(gaps, "skeleton_data_native_reference_mismatch:" + sourceDataAssetId);
                }
            }
            else
            {
                dataVerified = savedData == null;
                if (!dataVerified) AddGap(gaps, "source_unbound_component_has_native_data_asset");
                AddGap(gaps, "dynamic_skeleton_data_assignment_unverified");
            }

            var expectedFields = NormalizeTargetFields(component, expectedTargetFields);
            bool fieldsVerified = VerifyFields(component, expectedFields, isGraphic, gaps);
            if (isGraphic && expectedFields != null && expectedFields.ContainsKey("pmaVertexColors"))
                fieldsVerified &= VerifySkeletonGraphicPmaVertexColors((SkeletonGraphic)component,
                    Convert.ToBoolean(expectedFields["pmaVertexColors"]), gaps);
            bool dataContentVerified = sourceHasStaticDataReference && exactDataAsset != null && exactDataAssetReadback != null &&
                exactDataAssetReadback.sourceAssetId == sourceDataAssetId &&
                exactDataAssetReadback.skeletonDataAssetGuid == dataGuid && exactDataAssetReadback.staticDataVerified;
            if (sourceHasStaticDataReference && !dataContentVerified)
                AddGap(gaps, "skeleton_data_asset_content_readback_missing_or_incomplete");
            bool sourceUnbound = !sourceHasStaticDataReference && dataVerified;
            bool pmaMaterialProfileRequired = isGraphic && expectedFields != null &&
                expectedFields.ContainsKey("pmaVertexColors") && sourceHasStaticDataReference;
            bool pmaMaterialVerified = false;
            bool pmaMaterialProfileNotApplicable = isGraphic && expectedFields != null &&
                expectedFields.ContainsKey("pmaVertexColors") && !sourceHasStaticDataReference && sourceUnbound;
            if (pmaMaterialProfileRequired)
            {
                pmaMaterialVerified = sourceHasStaticDataReference && exactDataAsset != null && exactDataAssetReadback != null &&
                    exactDataAssetReadback.sourceAssetId == sourceDataAssetId &&
                    exactDataAssetReadback.skeletonDataAssetGuid == dataGuid &&
                    exactDataAssetReadback.sourceMaterialProfile == SourceProfile &&
                    exactDataAssetReadback.profileShaderName == ShaderName &&
                    exactDataAssetReadback.sourceProfileMaterialsVerified &&
                    exactDataAssetReadback.premultipliedAlpha == Convert.ToBoolean(expectedTargetFields["pmaVertexColors"]);
                if (!pmaMaterialVerified) AddGap(gaps, "skeleton_graphic_pma_material_profile_readback_missing_or_mismatched");
            }
            bool pmaMaterialEvidenceSatisfied = !isGraphic || expectedFields == null ||
                !expectedFields.ContainsKey("pmaVertexColors") || pmaMaterialVerified || pmaMaterialProfileNotApplicable;
            bool rendererMaterialRequired = isGraphic && sourceHasStaticDataReference;
            bool rendererMaterialVerified = !rendererMaterialRequired;
            bool allowMultipleCanvasRenderers = false;
            int customMaterialOverrideCount = 0;
            string rendererBaseMaterialShader = null, rendererBaseMaterialAssetPath = null,
                rendererBaseMaterialGuid = null, rendererMaterialForRenderingShader = null,
                rendererMainTextureAssetPath = null;
            string[] canvasRendererMaterialShaders = Array.Empty<string>();
            string[] canvasRendererMaterialAssetPaths = Array.Empty<string>();
            UnitySpineGraphicMaterialPresentation.Readback rendererPresentation = null;
            if (isGraphic)
            {
                var graphic = (SkeletonGraphic)component;
                allowMultipleCanvasRenderers = graphic.allowMultipleCanvasRenderers;
                customMaterialOverrideCount = graphic.CustomMaterialOverride == null ? 0 : graphic.CustomMaterialOverride.Count;
                var baseMaterial = graphic.material;
                rendererBaseMaterialShader = baseMaterial == null || baseMaterial.shader == null ? null : baseMaterial.shader.name;
                rendererBaseMaterialAssetPath = baseMaterial == null ? null : AssetDatabase.GetAssetPath(baseMaterial);
                rendererBaseMaterialGuid = String.IsNullOrEmpty(rendererBaseMaterialAssetPath)
                    ? null : AssetDatabase.AssetPathToGUID(rendererBaseMaterialAssetPath);
                var renderingMaterial = graphic.materialForRendering;
                rendererMaterialForRenderingShader = renderingMaterial == null || renderingMaterial.shader == null
                    ? null : renderingMaterial.shader.name;
                rendererMainTextureAssetPath = graphic.mainTexture == null ? null : AssetDatabase.GetAssetPath(graphic.mainTexture);
                var rendererMaterials = new List<string>();
                var rendererMaterialPaths = new List<string>();
                var primaryCanvasRendererMaterial = graphic.canvasRenderer == null ? null : graphic.canvasRenderer.GetMaterial();
                AddGraphicRendererMaterialReadback(primaryCanvasRendererMaterial, rendererMaterials, rendererMaterialPaths);
                foreach (var renderer in graphic.canvasRenderers ?? new List<CanvasRenderer>())
                    AddGraphicRendererMaterialReadback(renderer == null ? null : renderer.GetMaterial(),
                        rendererMaterials, rendererMaterialPaths);
                canvasRendererMaterialShaders = rendererMaterials.ToArray();
                canvasRendererMaterialAssetPaths = rendererMaterialPaths.ToArray();

                if (rendererMaterialRequired)
                {
                    var presentation = graphic.GetComponent<UnitySpineGraphicMaterialPresentation>();
                    UnitySpineGraphicMaterialPresentation.MaterialBinding[] expectedPresentationBindings = null;
                    try
                    {
                        expectedPresentationBindings = BuildGraphicMaterialBindings(sourceDataAssetId, exactDataAsset,
                            exactDataAssetReadback, graphic.allowMultipleCanvasRenderers);
                    }
                    catch (Exception error)
                    { AddGap(gaps, "skeleton_graphic_expected_material_pairs_unresolved:" + error.GetType().Name + ":" + error.Message); }
                    bool hasExpectedSkin = expectedFields != null && expectedFields.ContainsKey("initialSkinName");
                    bool hasExpectedAnimation = expectedFields != null && expectedFields.ContainsKey("startingAnimation");
                    var presentationReadback = presentation == null ? null : presentation.ReadSaved(
                        expectedPresentationBindings,
                        hasExpectedSkin ? Convert.ToString(expectedFields["initialSkinName"]) : null, hasExpectedSkin,
                        hasExpectedAnimation ? Convert.ToString(expectedFields["startingAnimation"]) : null, hasExpectedAnimation);
                    rendererPresentation = presentationReadback;
                    rendererMaterialVerified = presentationReadback != null &&
                        presentationReadback.sourceComponentId == sourceComponentId &&
                        presentationReadback.nativeMaterialVerified;
                    if (!rendererMaterialVerified)
                    {
                        AddGap(gaps, "skeleton_graphic_renderer_material_profile_not_bound_or_readback_unverified");
                        if (presentationReadback != null && presentationReadback.sourceComponentId != sourceComponentId)
                            AddGap(gaps, "skeleton_graphic_material_source_component_identity_mismatch");
                        if (presentationReadback != null)
                            foreach (var gap in presentationReadback.gaps ?? Array.Empty<string>())
                                AddGap(gaps, "skeleton_graphic_material:" + gap);
                    }
                    if (!graphic.allowMultipleCanvasRenderers)
                    { AddGap(gaps, "skeleton_graphic_multiple_canvas_renderers_disabled"); rendererMaterialVerified = false; }
                }
            }
            bool typeVerified = isGraphic || isAnimation;
            bool complete = typeVerified && dataVerified && dataContentVerified && fieldsVerified &&
                            enabled == persistentVisiblePose && gaps.Count == 0;
            return new ComponentReadback
            {
                sourceComponentId = sourceComponentId, rendererKind = isGraphic ? "SkeletonGraphic" : isAnimation ? "SkeletonAnimation" : "unknown",
                nativeComponentType = type.FullName, sourceDataAssetId = sourceDataAssetId,
                nativeDataAssetPath = dataPath, nativeDataAssetGuid = dataGuid,
                staticDataBound = sourceHasStaticDataReference && dataVerified, sourceDataUnbound = sourceUnbound,
                enabled = enabled, componentTypeVerified = typeVerified, dataReferenceVerified = dataVerified,
                dataAssetContentVerified = dataContentVerified,
                mappedStaticFieldsVerified = fieldsVerified && pmaMaterialEvidenceSatisfied &&
                    (!rendererMaterialRequired || rendererMaterialVerified), fieldsVerified = fieldsVerified,
                pmaMaterialProfileRequired = pmaMaterialProfileRequired,
                pmaMaterialProfileVerified = pmaMaterialVerified,
                pmaMaterialProfileNotApplicable = pmaMaterialProfileNotApplicable,
                rendererMaterialRequired = rendererMaterialRequired,
                rendererMaterialVerified = rendererMaterialVerified,
                allowMultipleCanvasRenderers = allowMultipleCanvasRenderers,
                customMaterialOverrideCount = customMaterialOverrideCount,
                rendererBaseMaterialShader = rendererBaseMaterialShader,
                rendererBaseMaterialAssetPath = rendererBaseMaterialAssetPath,
                rendererBaseMaterialGuid = rendererBaseMaterialGuid,
                rendererMaterialForRenderingShader = rendererMaterialForRenderingShader,
                canvasRendererMaterialShaders = canvasRendererMaterialShaders,
                canvasRendererMaterialAssetPaths = canvasRendererMaterialAssetPaths,
                rendererMainTextureAssetPath = rendererMainTextureAssetPath,
                rendererPresentation = rendererPresentation,
                nativeComplete = complete,
                dynamicAssignmentUnverified = sourceUnbound, sourceOnlyFieldGaps = Array.Empty<string>(), gaps = gaps.ToArray(),
            };
        }

        /// <summary>
        /// Sample only the authored initial pose at t=0. This invokes the
        /// pinned native Spine data/runtime APIs, never source game callbacks,
        /// and leaves the component disabled. The resulting runtime skeleton
        /// is a preview readback; saved component fields remain the durable state.
        /// </summary>
        public static StaticPoseReadback SampleInitialPoseAtZero(Component component, string sourceComponentId,
            string sourceDataAssetId, SkeletonDataAsset exactDataAsset, DataAssetReadback dataAssetReadback,
            string requestedSkin, string requestedAnimation, bool loop)
        {
            var gaps = new List<string>();
            var result = new StaticPoseReadback
            {
                sourceComponentId = sourceComponentId, sourceDataAssetId = sourceDataAssetId,
                requestedSkin = requestedSkin, requestedAnimation = requestedAnimation, loop = loop,
                componentEnabled = false, sourceCodeExecuted = false,
                timelineStatus = "only_time_zero_pose_sampled",
            };
            if (component == null || String.IsNullOrWhiteSpace(sourceComponentId))
                return PoseFailure(result, "native_spine_component_missing");
            if (exactDataAsset == null || dataAssetReadback == null || !dataAssetReadback.staticDataVerified ||
                dataAssetReadback.sourceAssetId != sourceDataAssetId)
                return PoseFailure(result, "exact_verified_skeleton_data_asset_missing");
            var path = AssetDatabase.GetAssetPath(exactDataAsset);
            var guid = String.IsNullOrEmpty(path) ? null : AssetDatabase.AssetPathToGUID(path);
            if (String.IsNullOrEmpty(guid) || guid != dataAssetReadback.skeletonDataAssetGuid)
                return PoseFailure(result, "skeleton_data_asset_guid_mismatch");

            Skeleton skeleton;
            global::Spine.AnimationState state;
            try
            {
                if (component.GetType() == typeof(SkeletonAnimation))
                {
                    var renderer = (SkeletonAnimation)component;
                    renderer.Initialize(true, true);
                    skeleton = renderer.Skeleton; state = renderer.AnimationState;
                    result.rendererKind = "SkeletonAnimation";
                }
                else if (component.GetType() == typeof(SkeletonGraphic))
                {
                    var renderer = (SkeletonGraphic)component;
                    renderer.Initialize(true);
                    skeleton = renderer.Skeleton; state = renderer.AnimationState;
                    result.rendererKind = "SkeletonGraphic";
                }
                else return PoseFailure(result, "unsupported_native_spine_component_type");
            }
            catch (Exception error) { return PoseFailure(result, "native_pose_initialize_failed:" + error.GetType().Name); }

            if (skeleton == null || state == null) return PoseFailure(result, "native_skeleton_or_animation_state_missing");
            if (!String.IsNullOrEmpty(requestedSkin))
            {
                if (skeleton.Data.FindSkin(requestedSkin) == null) AddGap(gaps, "requested_skin_missing:" + requestedSkin);
                else { skeleton.SetSkin(requestedSkin); skeleton.SetSlotsToSetupPose(); }
            }
            else skeleton.SetToSetupPose();

            TrackEntry entry = null;
            if (!String.IsNullOrEmpty(requestedAnimation))
            {
                var animation = skeleton.Data.FindAnimation(requestedAnimation);
                if (animation == null) AddGap(gaps, "requested_animation_missing:" + requestedAnimation);
                else entry = state.SetAnimation(0, animation, loop);
            }
            if (entry != null) entry.TrackTime = 0f;
            // Applying an AnimationState does not advance track time; deliberately
            // do not call Update/Complete/event queue processing or any source code.
            state.Apply(skeleton);
            skeleton.UpdateWorldTransform();
            var current = state.GetCurrent(0);
            result.nativeDataAssetGuid = guid;
            result.actualSkin = skeleton.Skin == null ? null : skeleton.Skin.Name;
            result.actualAnimation = current == null || current.Animation == null ? null : current.Animation.Name;
            result.trackTime = current == null ? 0f : current.TrackTime;
            result.componentEnabled = ((Behaviour)component).enabled;
            if (!String.IsNullOrEmpty(requestedSkin) && result.actualSkin != requestedSkin)
                AddGap(gaps, "sampled_skin_mismatch:" + requestedSkin);
            if (!String.IsNullOrEmpty(requestedAnimation) && result.actualAnimation != requestedAnimation)
                AddGap(gaps, "sampled_animation_mismatch:" + requestedAnimation);
            if (Math.Abs(result.trackTime) > 0.000001f) AddGap(gaps, "sampled_track_time_not_zero");
            result.poseVerified = gaps.Count == 0;
            result.gaps = gaps.ToArray();
            return result;
        }

        static DataAssetReadback ReadDataAsset(DataAssetSpec spec, SkeletonDataAsset saved, SkeletonData parsed,
            IDictionary<string, Material> variantMaterials, Material[] graphicNormalMaterials,
            IDictionary<string, Material> graphicVariantMaterials)
        {
            var gaps = new List<string>();
            var dataPath = AssetDatabase.GetAssetPath(saved);
            var atlas = saved.atlasAssets != null && saved.atlasAssets.Length == 1 ? saved.atlasAssets[0] as SpineAtlasAsset : null;
            var atlasPath = atlas == null ? null : AssetDatabase.GetAssetPath(atlas);
            bool identity = dataPath == spec.skeletonDataAssetPath && !String.IsNullOrEmpty(AssetDatabase.AssetPathToGUID(dataPath)) &&
                atlasPath == spec.atlasAssetPath && !String.IsNullOrEmpty(AssetDatabase.AssetPathToGUID(atlasPath));
            bool refs = saved.skeletonJSON != null && HashBytes(saved.skeletonJSON.bytes) == spec.skeletonSha256 &&
                atlas != null && atlas.atlasFile != null && HashBytes(atlas.atlasFile.bytes) == spec.atlasSha256;
            bool scaleVerified = Math.Abs(saved.scale - spec.scale) <= 0.000001f;
            if (!identity) AddGap(gaps, "native_data_asset_identity_unverified");
            if (!refs) AddGap(gaps, "saved_data_asset_source_reference_mismatch");
            if (!scaleVerified) AddGap(gaps, "saved_skeleton_data_scale_mismatch");

            bool materialReadback = true;
            var pinnedShader = AssetDatabase.LoadAssetAtPath<Shader>(spec.shaderAssetPath);
            if (pinnedShader == null || pinnedShader.name != ShaderName || HashAsset(spec.shaderAssetPath) != spec.shaderSha256)
                materialReadback = false;
            var graphicShader = AssetDatabase.LoadAssetAtPath<Shader>(spec.graphicShaderAssetPath);
            if (graphicShader == null || graphicShader.name != spec.graphicShaderName ||
                graphicShader.name != UnitySpineGraphicMaterialPresentation.ExpectedUiShaderName ||
                HashAsset(spec.graphicShaderAssetPath) != spec.graphicShaderSha256)
                materialReadback = false;
            var parsedAtlas = atlas == null ? null : atlas.GetAtlas();
            if (parsedAtlas == null || parsedAtlas.Pages == null || parsedAtlas.Pages.Count != spec.pages.Length) materialReadback = false;
            else for (int index = 0; index < spec.pages.Length; index++)
            {
                var page = parsedAtlas.Pages[index];
                var expected = atlas.materials[index];
                if (page.name != spec.pages[index].nativeAtlasPage || !ReferenceEquals(page.rendererObject, expected) ||
                    expected == null || expected.mainTexture != AssetDatabase.LoadAssetAtPath<Texture2D>(spec.pages[index].textureAssetPath) ||
                    expected.shader != pinnedShader || !BlendMatches(expected, spec.premultipliedAlpha, "normal"))
                    materialReadback = false;
            }
            if (!VerifyBlendMaterials(saved, spec, variantMaterials)) materialReadback = false;
            if (!materialReadback) AddGap(gaps, "source_profile_native_material_readback_mismatch");

            var animationNames = new List<string>();
            bool animationCatalogVerified = ReadCatalogNames(parsed.Animations, "animation", animationNames, gaps);
            var skinNames = new List<string>();
            bool skinCatalogVerified = ReadCatalogNames(parsed.Skins, "skin", skinNames, gaps);
            bool boneCatalogVerified = ValidateCatalogStructure(parsed.Bones, "bone", gaps);
            bool slotCatalogVerified = ValidateCatalogStructure(parsed.Slots, "slot", gaps);
            bool versionVerified = String.IsNullOrEmpty(spec.expectedSpineVersion) || parsed.Version == spec.expectedSpineVersion;
            bool catalogVerified = versionVerified && animationCatalogVerified && skinCatalogVerified &&
                boneCatalogVerified && slotCatalogVerified;
            if (!versionVerified) AddGap(gaps, "native_spine_version_mismatch:" + parsed.Version);
            foreach (var name in spec.requiredAnimations ?? Array.Empty<string>())
                if (!animationNames.Contains(name, StringComparer.Ordinal)) AddGap(gaps, "requested_animation_missing:" + name);
            foreach (var name in spec.requiredSkins ?? Array.Empty<string>())
                if (!skinNames.Contains(name, StringComparer.Ordinal)) AddGap(gaps, "requested_skin_missing:" + name);

            var pageReadbacks = new List<PageMaterialReadback>();
            for (int index = 0; index < spec.pages.Length; index++)
            {
                var pageSpec = spec.pages[index];
                var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(pageSpec.textureAssetPath);
                var normal = atlas != null && atlas.materials != null && index < atlas.materials.Length ? atlas.materials[index] : null;
                var variantGuids = new List<string>(); var variantModes = new List<string>();
                var graphicVariantPaths = new List<string>(); var graphicVariantGuids = new List<string>();
                bool pageRefs = texture != null && normal != null && normal.mainTexture == texture && normal.shader == pinnedShader;
                foreach (var variant in pageSpec.variants ?? Array.Empty<MaterialVariantSpec>())
                {
                    var material = variantsOrNull(variantMaterials, pageSpec.sourceAtlasPage, variant.blendMode);
                    var materialPath = material == null ? null : AssetDatabase.GetAssetPath(material);
                    var materialGuid = String.IsNullOrEmpty(materialPath) ? null : AssetDatabase.AssetPathToGUID(materialPath);
                    variantModes.Add(variant.blendMode); variantGuids.Add(materialGuid);
                    pageRefs &= material != null && material.mainTexture == texture && material.shader == pinnedShader &&
                        BlendMatches(material, spec.premultipliedAlpha, variant.blendMode) && !String.IsNullOrEmpty(materialGuid);
                    var graphicMaterial = variantsOrNull(graphicVariantMaterials, pageSpec.sourceAtlasPage, variant.blendMode);
                    var graphicPath = graphicMaterial == null ? null : AssetDatabase.GetAssetPath(graphicMaterial);
                    var graphicGuid = String.IsNullOrEmpty(graphicPath) ? null : AssetDatabase.AssetPathToGUID(graphicPath);
                    graphicVariantPaths.Add(graphicPath); graphicVariantGuids.Add(graphicGuid);
                    pageRefs &= GraphicProfileMaterialMatches(graphicMaterial, graphicShader, texture,
                        variant.blendMode, spec.premultipliedAlpha) && !String.IsNullOrEmpty(graphicGuid);
                }
                var texturePath = texture == null ? null : AssetDatabase.GetAssetPath(texture);
                var normalPath = normal == null ? null : AssetDatabase.GetAssetPath(normal);
                var textureGuid = String.IsNullOrEmpty(texturePath) ? null : AssetDatabase.AssetPathToGUID(texturePath);
                var normalGuid = String.IsNullOrEmpty(normalPath) ? null : AssetDatabase.AssetPathToGUID(normalPath);
                var graphicNormal = graphicNormalMaterials != null && index < graphicNormalMaterials.Length ? graphicNormalMaterials[index] : null;
                var graphicNormalPath = graphicNormal == null ? null : AssetDatabase.GetAssetPath(graphicNormal);
                var graphicNormalGuid = String.IsNullOrEmpty(graphicNormalPath) ? null : AssetDatabase.AssetPathToGUID(graphicNormalPath);
                pageRefs &= !String.IsNullOrEmpty(textureGuid) && !String.IsNullOrEmpty(normalGuid);
                pageRefs &= GraphicProfileMaterialMatches(graphicNormal, graphicShader, texture, "normal", spec.premultipliedAlpha) &&
                    !String.IsNullOrEmpty(graphicNormalGuid);
                if (!pageRefs) AddGap(gaps, "atlas_page_material_native_identity_unverified:" + pageSpec.sourceAtlasPage);
                pageReadbacks.Add(new PageMaterialReadback
                {
                    sourceAtlasPage = pageSpec.sourceAtlasPage, nativeAtlasPage = pageSpec.nativeAtlasPage,
                    sourceTextureSourceId = pageSpec.sourceTextureSourceId, textureGuid = textureGuid,
                    normalMaterialGuid = normalGuid, graphicNormalMaterialPath = graphicNormalPath,
                    graphicNormalMaterialGuid = graphicNormalGuid, variantModes = variantModes.ToArray(),
                    variantMaterialGuids = variantGuids.ToArray(), graphicVariantMaterialPaths = graphicVariantPaths.ToArray(),
                    graphicVariantMaterialGuids = graphicVariantGuids.ToArray(), referencesVerified = pageRefs,
                });
            }
            bool allPageReferencesVerified = pageReadbacks.Count == spec.pages.Length && pageReadbacks.All(page => page.referencesVerified);
            bool profileMaterialsVerified = materialReadback && allPageReferencesVerified;
            if (!allPageReferencesVerified) AddGap(gaps, "source_profile_material_native_guids_unverified");

            return new DataAssetReadback
            {
                sourceAssetId = spec.sourceAssetId, skeletonDataAssetPath = dataPath,
                skeletonDataAssetGuid = AssetDatabase.AssetPathToGUID(dataPath), atlasAssetPath = atlasPath,
                atlasAssetGuid = AssetDatabase.AssetPathToGUID(atlasPath), skeletonSha256 = HashBytes(saved.skeletonJSON.bytes),
                atlasSha256 = HashBytes(atlas.atlasFile.bytes), spineVersion = parsed.Version,
                sourceMaterialProfile = SourceProfile, profileShaderName = pinnedShader == null ? null : pinnedShader.name,
                profileShaderSha256 = pinnedShader == null ? null : HashAsset(spec.shaderAssetPath),
                uiGraphicShaderName = graphicShader == null ? null : graphicShader.name,
                uiGraphicShaderSha256 = graphicShader == null ? null : HashAsset(spec.graphicShaderAssetPath),
                uiGraphicShaderVerified = graphicShader != null && graphicShader.name == spec.graphicShaderName &&
                    graphicShader.name == UnitySpineGraphicMaterialPresentation.ExpectedUiShaderName &&
                    HashAsset(spec.graphicShaderAssetPath) == spec.graphicShaderSha256,
                premultipliedAlpha = spec.premultipliedAlpha, scale = saved.scale, scaleVerified = scaleVerified,
                boneCount = parsed.Bones.Count, slotCount = parsed.Slots.Count, skinCount = parsed.Skins.Count,
                animationCount = parsed.Animations.Count, nativeAssetIdentityVerified = identity,
                savedSourceReferencesVerified = refs, sourceProfileMaterialsVerified = profileMaterialsVerified,
                staticDataVerified = identity && refs && scaleVerified && profileMaterialsVerified && catalogVerified && parsed.Bones.Count > 0 &&
                    !gaps.Any(gap => gap.StartsWith("requested_animation_missing:", StringComparison.Ordinal) ||
                                     gap.StartsWith("requested_skin_missing:", StringComparison.Ordinal)),
                animations = animationNames.ToArray(), skins = skinNames.ToArray(), pages = pageReadbacks.ToArray(), gaps = gaps.ToArray(),
            };
        }

        static bool ReadCatalogNames<T>(global::Spine.ExposedList<T> catalog, string kind, List<string> names, List<string> gaps)
            where T : class
        {
            if (!ValidateCatalogStructure(catalog, kind, gaps)) return false;
            bool valid = true;
            // ExposedList.Items is a capacity-sized backing array. Only the
            // Count prefix contains entries; the remaining slots are null.
            for (int index = 0; index < catalog.Count; index++)
            {
                var item = catalog.Items[index];
                if (item == null)
                {
                    valid = false;
                    continue;
                }
                var name = item is global::Spine.Animation animation ? animation.Name
                    : item is global::Spine.Skin skin ? skin.Name : null;
                if (name == null)
                {
                    AddGap(gaps, "native_" + kind + "_catalog_unsupported_item:" + index);
                    valid = false;
                    continue;
                }
                names.Add(name);
            }
            return valid;
        }

        static bool ValidateCatalogStructure<T>(global::Spine.ExposedList<T> catalog, string kind, List<string> gaps)
            where T : class
        {
            if (catalog == null || catalog.Count < 0 || (catalog.Count > 0 && catalog.Items == null))
            {
                AddGap(gaps, "native_" + kind + "_catalog_unavailable");
                return false;
            }
            bool valid = true;
            // Validate only the logical Count range; ExposedList's backing
            // array may be larger and intentionally has null capacity slots.
            for (int index = 0; index < catalog.Count; index++)
            {
                if (catalog.Items[index] != null) continue;
                AddGap(gaps, "native_" + kind + "_catalog_null_item:" + index);
                valid = false;
            }
            return valid;
        }

        static Material variantsOrNull(IDictionary<string, Material> variants, string sourcePage, string mode)
        {
            return variants.TryGetValue(sourcePage + "\n" + mode, out var material) ? material : null;
        }

        static bool VerifyBlendMaterials(SkeletonDataAsset asset, DataAssetSpec spec, IDictionary<string, Material> variants)
        {
            if (asset.blendModeMaterials == null) return variants.Count == 0;
            var blend = asset.blendModeMaterials;
            var fields = new Dictionary<string, List<BlendModeMaterials.ReplacementMaterial>>(StringComparer.Ordinal)
            {
                ["additive"] = blend.additiveMaterials,
                ["multiply"] = blend.multiplyMaterials,
                ["screen"] = blend.screenMaterials,
            };
            foreach (var page in spec.pages)
            foreach (var variant in page.variants ?? Array.Empty<MaterialVariantSpec>())
            {
                if (!fields.TryGetValue(variant.blendMode, out var rows)) return false;
                var item = rows.FirstOrDefault(row => row.pageName == page.nativeAtlasPage);
                if (item == null || !variants.TryGetValue(page.sourceAtlasPage + "\n" + variant.blendMode, out var expected) ||
                    item.material != expected || !BlendMatches(item.material, spec.premultipliedAlpha, variant.blendMode))
                    return false;
            }
            return true;
        }

        static void ConfigureBlendMaterials(SkeletonDataAsset asset, DataAssetSpec spec, IDictionary<string, Material> variants)
        {
            var blend = asset.blendModeMaterials ?? new BlendModeMaterials();
            blend.applyAdditiveMaterial = false;
            blend.additiveMaterials.Clear(); blend.multiplyMaterials.Clear(); blend.screenMaterials.Clear();
            foreach (var page in spec.pages)
            foreach (var variant in page.variants ?? Array.Empty<MaterialVariantSpec>())
            {
                var row = new BlendModeMaterials.ReplacementMaterial
                {
                    pageName = page.nativeAtlasPage,
                    material = variants[page.sourceAtlasPage + "\n" + variant.blendMode],
                };
                if (variant.blendMode == "additive") { blend.additiveMaterials.Add(row); blend.applyAdditiveMaterial = true; }
                else if (variant.blendMode == "multiply") blend.multiplyMaterials.Add(row);
                else if (variant.blendMode == "screen") blend.screenMaterials.Add(row);
            }
            asset.blendModeMaterials = blend;
        }

        static void ConfigureGraphicMaterialPresentation(SkeletonGraphic graphic, string sourceComponentId,
            string sourceDataAssetId, SkeletonDataAsset dataAsset, DataAssetReadback dataReadback)
        {
            if (graphic == null) throw new InvalidOperationException("SPINE_UI_GRAPHIC_RENDERER_MISSING");
            var bindings = BuildGraphicMaterialBindings(sourceDataAssetId, dataAsset, dataReadback,
                graphic != null && graphic.allowMultipleCanvasRenderers);
            graphic.material = bindings[0].graphicMaterial;
            var helper = graphic.GetComponent<UnitySpineGraphicMaterialPresentation>();
            if (helper == null) helper = graphic.gameObject.AddComponent<UnitySpineGraphicMaterialPresentation>();
            helper.Configure(sourceComponentId, graphic, bindings);
            // Force the pinned SDK's per-submesh assignment, then reapply exact UI profiles
            // after its OnMeshAndMaterialsUpdated event has finished the normal material write.
            graphic.UpdateMesh(keepRendererCount: false);
            var readback = helper.ReadSaved(bindings, graphic.initialSkinName, true,
                graphic.startingAnimation, true);
            if (!readback.nativeMaterialVerified)
                throw new InvalidOperationException("SPINE_UI_GRAPHIC_MATERIAL_READBACK_FAILED:" +
                    String.Join(",", readback.gaps ?? Array.Empty<string>()));
        }

        static UnitySpineGraphicMaterialPresentation.MaterialBinding[] BuildGraphicMaterialBindings(
            string sourceDataAssetId, SkeletonDataAsset dataAsset, DataAssetReadback dataReadback,
            bool multipleCanvasRenderersEnabled)
        {
            if (dataAsset == null || dataReadback == null || !dataReadback.staticDataVerified ||
                dataReadback.sourceAssetId != sourceDataAssetId || dataReadback.pages == null ||
                dataReadback.pages.Length == 0 || !multipleCanvasRenderersEnabled)
                throw new InvalidOperationException("SPINE_UI_GRAPHIC_MATERIAL_EVIDENCE_MISSING");
            var atlas = dataAsset.atlasAssets != null && dataAsset.atlasAssets.Length == 1
                ? dataAsset.atlasAssets[0] as SpineAtlasAsset : null;
            if (atlas == null || atlas.materials == null || atlas.materials.Length != dataReadback.pages.Length)
                throw new InvalidOperationException("SPINE_UI_GRAPHIC_ATLAS_MATERIAL_DENOMINATOR_MISMATCH");
            var bindings = new List<UnitySpineGraphicMaterialPresentation.MaterialBinding>();
            for (int i = 0; i < dataReadback.pages.Length; i++)
            {
                var page = dataReadback.pages[i];
                if (!page.referencesVerified || atlas.materials[i] == null ||
                    String.IsNullOrWhiteSpace(page.graphicNormalMaterialPath))
                    throw new InvalidOperationException("SPINE_UI_GRAPHIC_PAGE_PROFILE_UNVERIFIED:" + page.sourceAtlasPage);
                var normalUi = AssetDatabase.LoadAssetAtPath<Material>(page.graphicNormalMaterialPath);
                AddGraphicMaterialBinding(bindings, sourceDataAssetId + "/" + page.sourceAtlasPage + "/normal",
                    page.sourceTextureSourceId, "normal", atlas.materials[i], normalUi,
                    dataReadback.premultipliedAlpha);
                AddBlendVariantBindings(bindings, sourceDataAssetId, page, dataAsset.blendModeMaterials,
                    dataReadback.premultipliedAlpha);
            }
            if (bindings.Count == 0) throw new InvalidOperationException("SPINE_UI_GRAPHIC_MATERIAL_BINDINGS_EMPTY");
            return bindings.ToArray();
        }

        static void AddBlendVariantBindings(List<UnitySpineGraphicMaterialPresentation.MaterialBinding> bindings,
            string sourceDataAssetId, PageMaterialReadback page, BlendModeMaterials blend, bool pma)
        {
            if (page.variantModes == null) return;
            for (int i = 0; i < page.variantModes.Length; i++)
            {
                var mode = page.variantModes[i];
                var replacement = FindBlendReplacement(blend, mode, page.nativeAtlasPage);
                var graphicPath = page.graphicVariantMaterialPaths != null && i < page.graphicVariantMaterialPaths.Length
                    ? page.graphicVariantMaterialPaths[i] : null;
                var graphicMaterial = String.IsNullOrWhiteSpace(graphicPath)
                    ? null : AssetDatabase.LoadAssetAtPath<Material>(graphicPath);
                if (replacement == null || replacement.material == null || graphicMaterial == null)
                    throw new InvalidOperationException("SPINE_UI_GRAPHIC_VARIANT_REFERENCE_MISSING:" + page.sourceAtlasPage + "/" + mode);
                AddGraphicMaterialBinding(bindings, sourceDataAssetId + "/" + page.sourceAtlasPage + "/" + mode,
                    page.sourceTextureSourceId, mode, replacement.material, graphicMaterial, pma);
            }
        }

        static BlendModeMaterials.ReplacementMaterial FindBlendReplacement(BlendModeMaterials blend, string mode, string pageName)
        {
            if (blend == null) return null;
            IEnumerable<BlendModeMaterials.ReplacementMaterial> rows = mode == "additive" ? blend.additiveMaterials :
                mode == "multiply" ? blend.multiplyMaterials : mode == "screen" ? blend.screenMaterials : null;
            return rows == null ? null : rows.FirstOrDefault(row => row != null && row.pageName == pageName);
        }

        static void AddGraphicMaterialBinding(List<UnitySpineGraphicMaterialPresentation.MaterialBinding> bindings,
            string sourceMaterialId, string textureSourceId, string mode, Material sourceMaterial,
            Material graphicMaterial, bool pma)
        {
            if (sourceMaterial == null || graphicMaterial == null || sourceMaterial.mainTexture == null ||
                graphicMaterial.mainTexture != sourceMaterial.mainTexture)
                throw new InvalidOperationException("SPINE_UI_GRAPHIC_MATERIAL_REFERENCE_MISMATCH:" + sourceMaterialId);
            var factors = Monkey.Targets.SpineMaterials.UnitySpineMaterialBindings.BlendFactors(mode, pma);
            if (!GraphicProfileMaterialMatches(graphicMaterial, graphicMaterial.shader, sourceMaterial.mainTexture, mode, pma))
                throw new InvalidOperationException("SPINE_UI_GRAPHIC_MATERIAL_PROFILE_MISMATCH:" + sourceMaterialId);
            var graphicPath = AssetDatabase.GetAssetPath(graphicMaterial);
            var graphicGuid = String.IsNullOrWhiteSpace(graphicPath) ? null : AssetDatabase.AssetPathToGUID(graphicPath);
            var texturePath = AssetDatabase.GetAssetPath(graphicMaterial.mainTexture);
            var textureGuid = String.IsNullOrWhiteSpace(texturePath) ? null : AssetDatabase.AssetPathToGUID(texturePath);
            if (String.IsNullOrWhiteSpace(graphicGuid) || String.IsNullOrWhiteSpace(textureGuid))
                throw new InvalidOperationException("SPINE_UI_GRAPHIC_MATERIAL_PERSISTENT_IDENTITY_MISSING:" + sourceMaterialId);
            bindings.Add(new UnitySpineGraphicMaterialPresentation.MaterialBinding
            {
                sourceMaterialId = sourceMaterialId, textureSourceId = textureSourceId, blendMode = mode,
                sourceMaterial = sourceMaterial, graphicMaterial = graphicMaterial,
                graphicMaterialAssetPath = graphicPath, graphicMaterialAssetGuid = graphicGuid,
                graphicTextureAssetPath = texturePath, graphicTextureAssetGuid = textureGuid,
                expectedSrcBlend = factors[0], expectedDstBlend = factors[1],
            });
        }

        static Material CreateProfileMaterial(DataAssetSpec spec, Shader shader, Texture2D texture,
            AtlasPageSpec page, string mode, string path, List<string> createdPaths)
        {
            if (String.IsNullOrWhiteSpace(path) || !path.StartsWith("Assets/", StringComparison.Ordinal))
                throw new InvalidOperationException("SPINE_MATERIAL_PATH_INVALID: " + mode);
            EnsureRegisteredAssetParent(path);
            if (AssetDatabase.LoadAssetAtPath<Material>(path) != null || File.Exists(AbsoluteAssetPath(path)))
                throw new InvalidOperationException("SPINE_MATERIAL_ASSET_COLLISION: " + path);
            var material = new Material(shader) { name = Path.GetFileNameWithoutExtension(path), mainTexture = texture };
            if (!material.HasProperty("_SrcBlend") || !material.HasProperty("_DstBlend"))
            { UnityEngine.Object.DestroyImmediate(material); throw new InvalidOperationException("SPINE_PROFILE_SHADER_BLEND_PROPERTIES_MISSING"); }
            try { Monkey.Targets.SpineMaterials.UnitySpineMaterialBindings.ConfigureProfileMaterial(material, mode, spec.premultipliedAlpha); }
            catch { UnityEngine.Object.DestroyImmediate(material); throw; }
            AssetDatabase.CreateAsset(material, path); createdPaths.Add(path);
            var saved = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (saved == null || saved.shader != shader || saved.mainTexture != texture ||
                !Monkey.Targets.SpineMaterials.UnitySpineMaterialBindings.ProfileMaterialMatches(saved, mode, spec.premultipliedAlpha))
                throw new InvalidOperationException("SPINE_PROFILE_MATERIAL_SAVED_READBACK_MISMATCH: " + page.sourceAtlasPage + "/" + mode);
            return saved;
        }

        static Material CreateGraphicProfileMaterial(DataAssetSpec spec, Shader shader, Texture2D texture,
            AtlasPageSpec page, string mode, string path, List<string> createdPaths)
        {
            if (String.IsNullOrWhiteSpace(path) || !path.StartsWith("Assets/", StringComparison.Ordinal))
                throw new InvalidOperationException("SPINE_UI_GRAPHIC_MATERIAL_PATH_INVALID: " + mode);
            EnsureRegisteredAssetParent(path);
            if (AssetDatabase.LoadAssetAtPath<Material>(path) != null || File.Exists(AbsoluteAssetPath(path)))
                throw new InvalidOperationException("SPINE_UI_GRAPHIC_MATERIAL_ASSET_COLLISION: " + path);
            var material = new Material(shader) { name = Path.GetFileNameWithoutExtension(path), mainTexture = texture };
            try { ConfigureGraphicProfileMaterial(material, mode, spec.premultipliedAlpha); }
            catch { UnityEngine.Object.DestroyImmediate(material); throw; }
            AssetDatabase.CreateAsset(material, path); createdPaths.Add(path);
            var saved = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (!GraphicProfileMaterialMatches(saved, shader, texture, mode, spec.premultipliedAlpha))
                throw new InvalidOperationException("SPINE_UI_GRAPHIC_MATERIAL_SAVED_READBACK_MISMATCH: " + page.sourceAtlasPage + "/" + mode);
            return saved;
        }

        static void ConfigureGraphicProfileMaterial(Material material, string mode, bool pma)
        {
            if (material == null || material.shader == null ||
                material.shader.name != UnitySpineGraphicMaterialPresentation.ExpectedUiShaderName ||
                !material.HasProperty("_SrcBlend") || !material.HasProperty("_DstBlend"))
                throw new InvalidOperationException("SPINE_UI_GRAPHIC_SHADER_BLEND_PROPERTIES_MISSING");
            var factors = Monkey.Targets.SpineMaterials.UnitySpineMaterialBindings.BlendFactors(mode, pma);
            material.SetInt("_SrcBlend", factors[0]); material.SetInt("_DstBlend", factors[1]);
            // The frozen source profile shader samples source atlas pixels
            // directly; alpha-mode conversion has no evidence input here.
            material.SetInt("_StraightAlphaInput", 0);
            material.SetInt("_CanvasGroupCompatible", pma ? 1 : 0);
            material.SetInt("_PremultipliedAlpha", pma ? 1 : 0);
            SetKeyword(material, "_STRAIGHT_ALPHA_INPUT", false);
            SetKeyword(material, "_CANVAS_GROUP_COMPATIBLE", pma);
            SetKeyword(material, "_PREMULTIPLIED_ALPHA", pma);
            material.SetOverrideTag("RenderType", "Transparent");
            material.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
        }

        static bool GraphicProfileMaterialMatches(Material material, Shader shader, Texture texture,
            string mode, bool pma)
        {
            if (material == null || shader == null || material.shader != shader || material.mainTexture != texture ||
                material.shader.name != UnitySpineGraphicMaterialPresentation.ExpectedUiShaderName ||
                !material.HasProperty("_SrcBlend") || !material.HasProperty("_DstBlend") ||
                !material.HasProperty("_StraightAlphaInput") || !material.HasProperty("_CanvasGroupCompatible") ||
                !material.HasProperty("_PremultipliedAlpha")) return false;
            var factors = Monkey.Targets.SpineMaterials.UnitySpineMaterialBindings.BlendFactors(mode, pma);
            return material.GetInt("_SrcBlend") == factors[0] && material.GetInt("_DstBlend") == factors[1] &&
                material.GetInt("_StraightAlphaInput") == 0 && material.GetInt("_CanvasGroupCompatible") == (pma ? 1 : 0) &&
                material.GetInt("_PremultipliedAlpha") == (pma ? 1 : 0) &&
                !material.IsKeywordEnabled("_STRAIGHT_ALPHA_INPUT") &&
                material.IsKeywordEnabled("_CANVAS_GROUP_COMPATIBLE") == pma &&
                material.IsKeywordEnabled("_PREMULTIPLIED_ALPHA") == pma;
        }

        static void SetKeyword(Material material, string keyword, bool enabled)
        { if (enabled) material.EnableKeyword(keyword); else material.DisableKeyword(keyword); }

        static bool BlendMatches(Material material, bool pma, string mode)
        {
            return Monkey.Targets.SpineMaterials.UnitySpineMaterialBindings.ProfileMaterialMatches(material, mode, pma);
        }

        static void CreateOwnedAsset(UnityEngine.Object asset, string path, List<string> createdPaths)
        {
            if (asset == null || String.IsNullOrWhiteSpace(path) || !path.StartsWith("Assets/", StringComparison.Ordinal))
                throw new InvalidOperationException("SPINE_NATIVE_ASSET_PATH_INVALID");
            EnsureRegisteredAssetParent(path);
            if (AssetDatabase.LoadMainAssetAtPath(path) != null || File.Exists(AbsoluteAssetPath(path)))
                throw new InvalidOperationException("SPINE_NATIVE_ASSET_COLLISION: " + path);
            AssetDatabase.CreateAsset(asset, path); createdPaths.Add(path); EditorUtility.SetDirty(asset);
        }

        static List<string> EnsureAssetDirectoriesForPaths(IEnumerable<string> assetPaths)
        {
            var created = new List<string>();
            foreach (var path in assetPaths.Distinct(StringComparer.Ordinal))
            {
                if (String.IsNullOrWhiteSpace(path) || !path.StartsWith("Assets/", StringComparison.Ordinal) || path.Contains("\\"))
                    throw new InvalidOperationException("SPINE_NATIVE_ASSET_PATH_INVALID: " + path);
                var segments = path.Split('/');
                if (segments.Length < 2 || segments.Any(segment => String.IsNullOrWhiteSpace(segment) || segment == "." || segment == ".."))
                    throw new InvalidOperationException("SPINE_NATIVE_ASSET_PATH_INVALID: " + path);

                var parent = "Assets";
                for (int index = 1; index < segments.Length - 1; index++)
                {
                    var child = parent + "/" + segments[index];
                    if (AssetDatabase.IsValidFolder(child)) { parent = child; continue; }

                    var absolute = AbsoluteAssetPath(child);
                    if (File.Exists(absolute))
                        throw new InvalidOperationException("SPINE_ASSET_DIRECTORY_FILE_COLLISION: " + child);
                    if (Directory.Exists(absolute))
                    {
                        // Import an externally-created directory only if Unity
                        // can register it as a folder. Never create filesystem
                        // directories as an AssetDatabase fallback.
                        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
                        if (AssetDatabase.IsValidFolder(child)) { parent = child; continue; }
                        throw new InvalidOperationException("SPINE_ASSET_DIRECTORY_UNREGISTERED: " + child);
                    }
                    if (!AssetDatabase.IsValidFolder(parent))
                        throw new InvalidOperationException("SPINE_ASSET_PARENT_FOLDER_UNREGISTERED: " + parent);

                    var guid = AssetDatabase.CreateFolder(parent, segments[index]);
                    if (String.IsNullOrWhiteSpace(guid) || !AssetDatabase.IsValidFolder(child))
                        throw new InvalidOperationException("SPINE_ASSET_DIRECTORY_CREATE_FAILED: " + child);
                    created.Add(child);
                    parent = child;
                }
            }
            return created;
        }

        static void EnsureRegisteredAssetParent(string assetPath)
        {
            var parent = Path.GetDirectoryName(assetPath)?.Replace('\\', '/');
            if (String.IsNullOrWhiteSpace(parent) || !AssetDatabase.IsValidFolder(parent))
                throw new InvalidOperationException("SPINE_ASSET_PARENT_FOLDER_UNREGISTERED: " + parent);
        }

        static void DeleteCreatedEmptyFolders(IEnumerable<string> folders)
        {
            foreach (var folder in folders.Reverse())
            {
                if (!AssetDatabase.IsValidFolder(folder)) continue;
                var absolute = AbsoluteAssetPath(folder);
                if (Directory.Exists(absolute) && !Directory.EnumerateFileSystemEntries(absolute).Any())
                    AssetDatabase.DeleteAsset(folder);
            }
        }

        static Texture2D LoadSpinePageTexture(AtlasPageSpec page)
        {
            if (page == null || String.IsNullOrWhiteSpace(page.textureAssetPath))
                throw new InvalidOperationException("SPINE_PAGE_TEXTURE_PATH_INVALID: " + (page == null ? "null" : page.sourceTextureSourceId));
            var path = page.textureAssetPath;
            var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            var absolutePath = AbsoluteAssetPath(path);
            var diskFileExists = File.Exists(absolutePath);
            if (texture != null)
            {
                var objectPath = AssetDatabase.GetAssetPath(texture);
                if (String.Equals(objectPath, path, StringComparison.Ordinal)) return texture;
                throw new InvalidOperationException("SPINE_PAGE_TEXTURE_ASSET_PATH_MISMATCH: source=" +
                    page.sourceTextureSourceId + " expected=" + path + " actual=" + objectPath);
            }

            var importer = AssetImporter.GetAtPath(path);
            var importerName = importer == null ? "null" : importer.GetType().FullName;
            var mainType = AssetDatabase.GetMainAssetTypeAtPath(path);
            var mainTypeName = mainType == null ? "null" : mainType.FullName;
            var mainAsset = AssetDatabase.LoadMainAssetAtPath(path);
            var mainObjectPath = mainAsset == null ? "null" : AssetDatabase.GetAssetPath(mainAsset);
            var requestedObject = AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(path);
            var requestedObjectType = requestedObject == null ? "null" : requestedObject.GetType().FullName;
            var requestedObjectPath = requestedObject == null ? "null" : AssetDatabase.GetAssetPath(requestedObject);
            var importedObjects = AssetDatabase.LoadAllAssetsAtPath(path) ?? Array.Empty<UnityEngine.Object>();
            var importedObjectDetails = String.Join(";", importedObjects.Where(value => value != null).Select(value =>
                value.GetType().FullName + "[" + value.name + "]@" + AssetDatabase.GetAssetPath(value)));
            throw new InvalidOperationException("SPINE_PAGE_TEXTURE_MISSING: source=" + page.sourceTextureSourceId +
                " path=" + path + " diskFileExists=" + diskFileExists + " importer=" + importerName +
                " mainAssetType=" + mainTypeName + " mainObjectPath=" + mainObjectPath +
                " requestedObjectType=" + requestedObjectType + " requestedObjectPath=" + requestedObjectPath +
                " subassets=" + importedObjectDetails);
        }

        static bool VerifyFields(Component component, IDictionary<string, object> expected, bool isGraphic, List<string> gaps)
        {
            if (expected == null) return true;
            bool verified = true;
            foreach (var pair in expected)
            {
                if (isGraphic && pair.Key == "pmaVertexColors") continue;
                object actual;
                if (!TryReadMember(component, pair.Key, out actual) || !System.Object.Equals(actual, CoerceExpected(pair.Value, actual == null ? null : actual.GetType())))
                { AddGap(gaps, "native_field_readback_mismatch:" + pair.Key); verified = false; }
            }
            return verified;
        }

        static void BuildPersistentStaticPose(Component component, bool? graphicPmaVertexColors)
        {
            if (component.GetType() == typeof(SkeletonGraphic))
            {
                var graphic = (SkeletonGraphic)component;
                graphic.freeze = false;
                graphic.Initialize(true);
                if (graphicPmaVertexColors.HasValue)
                    SetSkeletonGraphicPmaVertexColors(graphic, graphicPmaVertexColors.Value);
                graphic.Update(0f);
                graphic.UpdateMesh(keepRendererCount: false);
                graphic.SetVerticesDirty();
                graphic.SetMaterialDirty();
                return;
            }
            if (component.GetType() == typeof(SkeletonAnimation))
            {
                var animation = (SkeletonAnimation)component;
                animation.Initialize(true, true);
                animation.Update(0f);
                animation.LateUpdate();
                return;
            }
            throw new InvalidOperationException("SPINE_PERSISTENT_POSE_UNSUPPORTED_RENDERER");
        }

        static void SetSkeletonGraphicPmaVertexColors(SkeletonGraphic graphic, bool value)
        {
            if (graphic == null || graphic.MeshGenerator == null)
                throw new InvalidOperationException("SPINE_GRAPHIC_MESH_GENERATOR_UNAVAILABLE");
            var generator = graphic.MeshGenerator;
            var settings = generator.settings;
            settings.pmaVertexColors = value;
            generator.settings = settings;
            if (generator.settings.pmaVertexColors != value)
                throw new InvalidOperationException("SPINE_GRAPHIC_PMA_VERTEX_SETTING_WRITE_MISMATCH");
        }

        static bool VerifySkeletonGraphicPmaVertexColors(SkeletonGraphic graphic, bool expected, List<string> gaps)
        {
            if (graphic == null || graphic.MeshGenerator == null)
            {
                AddGap(gaps, "skeleton_graphic_pma_vertex_setting_unavailable");
                return false;
            }
            var actual = graphic.MeshGenerator.settings.pmaVertexColors;
            if (actual == expected) return true;
            AddGap(gaps, "skeleton_graphic_pma_vertex_setting_mismatch");
            return false;
        }

        static void AddGraphicRendererMaterialReadback(Material material, List<string> shaders, List<string> paths)
        {
            shaders.Add(material == null || material.shader == null ? null : material.shader.name);
            var path = material == null ? null : AssetDatabase.GetAssetPath(material);
            paths.Add(String.IsNullOrEmpty(path) ? null : path);
        }

        static Dictionary<string, object> NormalizeTargetFields(Component component, IDictionary<string, object> source)
        {
            var result = source == null
                ? new Dictionary<string, object>()
                : new Dictionary<string, object>(source);
            if (component != null && component.GetType() == typeof(SkeletonAnimation))
            {
                if (result.TryGetValue("startingAnimation", out var animation))
                { result.Remove("startingAnimation"); result["AnimationName"] = animation; }
                if (result.TryGetValue("startingLoop", out var loop))
                { result.Remove("startingLoop"); result["loop"] = loop; }
            }
            return result;
        }

        static UnityEngine.Object ReadDataReference(Component component)
        {
            for (var type = component.GetType(); type != null; type = type.BaseType)
            {
                var property = type.GetProperty("SkeletonDataAsset", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.DeclaredOnly);
                if (property != null && typeof(UnityEngine.Object).IsAssignableFrom(property.PropertyType)) return property.GetValue(component, null) as UnityEngine.Object;
                var field = type.GetField("skeletonDataAsset", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.DeclaredOnly);
                if (field != null && typeof(UnityEngine.Object).IsAssignableFrom(field.FieldType)) return field.GetValue(component) as UnityEngine.Object;
            }
            return null;
        }

        static bool TryReadMember(object target, string name, out object value)
        {
            for (var type = target.GetType(); type != null; type = type.BaseType)
            {
                var property = type.GetProperty(name, System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.DeclaredOnly);
                if (property != null && property.CanRead) { value = property.GetValue(target, null); return true; }
                var field = type.GetField(name, System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.DeclaredOnly);
                if (field != null) { value = field.GetValue(target); return true; }
            }
            value = null; return false;
        }

        static object CoerceExpected(object value, Type type)
        {
            if (value == null || type == null || type.IsInstanceOfType(value)) return value;
            if (type.IsEnum) return value is string text ? Enum.Parse(type, text, false) : Enum.ToObject(type, value);
            return Convert.ChangeType(value, type);
        }

        static void ValidateSpec(DataAssetSpec spec)
        {
            if (spec == null || String.IsNullOrWhiteSpace(spec.sourceAssetId) ||
                !IsSha(spec.skeletonSha256) || !IsSha(spec.atlasSha256) || !IsSha(spec.shaderSha256) ||
                !IsSha(spec.graphicShaderSha256) || String.IsNullOrWhiteSpace(spec.graphicShaderAssetPath) ||
                spec.graphicShaderName != UnitySpineGraphicMaterialPresentation.ExpectedUiShaderName ||
                String.IsNullOrWhiteSpace(spec.skeletonDataAssetPath) || String.IsNullOrWhiteSpace(spec.atlasAssetPath) ||
                !IsFinite(spec.scale) || spec.scale <= 0f || spec.pages == null || spec.pages.Length == 0)
                throw new InvalidOperationException("SPINE_NATIVE_DATA_ASSET_SPEC_INVALID");
            if (spec.pages.Any(page => page == null || String.IsNullOrWhiteSpace(page.sourceAtlasPage) ||
                String.IsNullOrWhiteSpace(page.sourceTextureSourceId) || String.IsNullOrWhiteSpace(page.textureAssetPath) ||
                String.IsNullOrWhiteSpace(page.normalMaterialAssetPath) ||
                String.IsNullOrWhiteSpace(page.graphicNormalMaterialAssetPath) ||
                (page.variants ?? Array.Empty<MaterialVariantSpec>()).Any(variant => variant == null ||
                    String.IsNullOrWhiteSpace(variant.materialAssetPath) || String.IsNullOrWhiteSpace(variant.graphicMaterialAssetPath))))
                throw new InvalidOperationException("SPINE_NATIVE_ATLAS_PAGE_SPEC_INVALID");
        }

        static string[] ReadAtlasPageNames(string atlas)
        {
            var lines = (atlas ?? String.Empty).Replace("\r\n", "\n").Replace('\r', '\n').Split('\n');
            var result = new List<string>();
            for (int i = 0; i + 1 < lines.Length; i++)
            {
                var line = lines[i];
                if (line.Length > 0 && !Char.IsWhiteSpace(line[0]) && !line.Contains(":") &&
                    (lines[i + 1].StartsWith("size:", StringComparison.Ordinal) || lines[i + 1].StartsWith("format:", StringComparison.Ordinal)))
                    result.Add(line);
            }
            if (result.Count == 0 || result.Distinct(StringComparer.Ordinal).Count() != result.Count)
                throw new InvalidOperationException("SPINE_ATLAS_PAGE_DECLARATIONS_INVALID");
            return result.ToArray();
        }

        static bool IsSha(string value) => value != null && value.Length == 64 && value.All(Uri.IsHexDigit);
        static bool IsFinite(float value) => !Single.IsNaN(value) && !Single.IsInfinity(value);
        static void AddGap(List<string> gaps, string value) { if (!gaps.Contains(value)) gaps.Add(value); }
        static ComponentReadback ComponentFailure(string sourceId, string gap) => new ComponentReadback
        {
            sourceComponentId = sourceId, componentTypeVerified = false, dataReferenceVerified = false,
            fieldsVerified = false, nativeComplete = false, enabled = false, gaps = new[] { gap },
        };
        static StaticPoseReadback PoseFailure(StaticPoseReadback result, string gap)
        {
            result.gaps = new[] { gap };
            result.poseVerified = false;
            return result;
        }
        static string HashBytes(byte[] bytes) { using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant(); }
        static string HashAsset(string assetPath) => HashBytes(File.ReadAllBytes(AbsoluteAssetPath(assetPath)));
        static string AbsoluteAssetPath(string assetPath) => Path.GetFullPath(Path.Combine(Directory.GetParent(Application.dataPath).FullName, assetPath));
    }
}
