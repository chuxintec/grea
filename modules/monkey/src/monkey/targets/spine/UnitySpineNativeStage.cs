// Thin Editor integration stage over the frozen Unity native Spine plan.
// The main importer supplies only sourceId->native-node/component resolvers.
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using Spine.Unity;

namespace Monkey.Targets.Spine
{
    public static class UnitySpineNativeStage
    {
        [Serializable] public sealed class Plan
        {
            public int schemaVersion;
            public string contract;
            public string sourceManifestSha256;
            public string normalizedIrSha256;
            public RuntimeInfo runtime;
            public string visualPolicy;
            public bool persistentVisiblePose;
            public VisiblePoseEvidence persistentVisiblePoseEvidence;
            public DataAssetRow[] dataAssets;
            public ComponentRow[] components;
        }

        [Serializable] public sealed class RuntimeInfo
        {
            public EditorVariant editorVariant;
        }

        [Serializable] public sealed class EditorVariant
        {
            public string status;
            public AssemblyLoadVerification assemblyLoadVerification;
        }

        [Serializable] public sealed class AssemblyLoadVerification
        {
            public string status;
            public string expectedAssemblyPath;
            public string expectedAssemblySha256;
            public string expectedCoreAssemblyPath;
            public string expectedCoreAssemblySha256;
            public bool expectedUnityEditorReference;
            public string[] requiredActualFields;
        }

        [Serializable] public sealed class VisiblePoseEvidence
        {
            public string status;
            public string upstreamCommit;
            public string runtimeVersion;
            public string targetPolicy;
        }

        [Serializable] public sealed class DataAssetRow
        {
            public string sourceAssetId;
            public string skeletonDataAssetPath;
            public string skeletonSha256;
            public string atlasTextAssetPath;
            public string atlasSha256;
            public string nativeDataAssetGuid;
            public float scale;
            public UnitySpineNativeFactory.DataAssetSpec factoryInput;
        }

        [Serializable] public sealed class ComponentRow
        {
            public string sourceComponentId;
            public string sourcePrefabId;
            public string sourceNodeId;
            public TemplateOrigin templateOrigin;
            public string sourceNodePath;
            public string sourceDataAssetId;
            public bool sourceHasStaticDataReference;
            public double sourceTimeScale;
            public bool sourceTimeScaleVerified;
            public bool persistentVisiblePose;
            public string rendererKind;
            public FieldBinding[] targetFieldBindings;
            public FieldGap[] fieldGaps;
        }

        [Serializable] public sealed class TemplateOrigin
        {
            public string sourceComponentId;
            public string sourcePrefabId;
            public string sourceNodeId;
            public string[] componentOriginChain;
            public string[] nodeOriginChain;
        }

        [Serializable] public sealed class FieldBinding
        {
            public string sourceProperty;
            public string member;
            public string status;
            public string valueType;
            public bool boolValue;
            public double numberValue;
            public string stringValue;
        }

        [Serializable] public sealed class FieldGap
        {
            public string sourceProperty;
            public string status;
        }

        [Serializable] public sealed class StageGap
        {
            public string sourceId;
            public string code;
            public string message;
            public string phase;
            public string exceptionType;
            public string stackTrace;
        }

        public sealed class CreateResult
        {
            public readonly Dictionary<string, SkeletonDataAsset> dataAssets = new Dictionary<string, SkeletonDataAsset>(StringComparer.Ordinal);
            public readonly Dictionary<string, UnitySpineNativeFactory.DataAssetReadback> dataAssetReadbacks =
                new Dictionary<string, UnitySpineNativeFactory.DataAssetReadback>(StringComparer.Ordinal);
            public readonly Dictionary<string, Component> components = new Dictionary<string, Component>(StringComparer.Ordinal);
            public readonly List<UnitySpineNativeFactory.ComponentReadback> componentReadbacks = new List<UnitySpineNativeFactory.ComponentReadback>();
            public readonly List<UnitySpineNativeFactory.DataAssetReadback> assetReadbacks = new List<UnitySpineNativeFactory.DataAssetReadback>();
            public readonly List<StageGap> gaps = new List<StageGap>();
        }

        public sealed class SavedReadResult
        {
            public readonly List<UnitySpineNativeFactory.DataAssetReadback> dataAssets = new List<UnitySpineNativeFactory.DataAssetReadback>();
            public readonly List<UnitySpineNativeFactory.ComponentReadback> components = new List<UnitySpineNativeFactory.ComponentReadback>();
            public readonly List<StageGap> gaps = new List<StageGap>();
        }

        public static Plan Parse(string json)
        {
            if (String.IsNullOrWhiteSpace(json)) throw new ArgumentException("Spine native stage plan JSON is required.", nameof(json));
            var plan = JsonUtility.FromJson<Plan>(json);
            if (plan == null || plan.schemaVersion != 1 || plan.contract != "monkey-spine-native-binding/1" ||
                String.IsNullOrWhiteSpace(plan.sourceManifestSha256) || String.IsNullOrWhiteSpace(plan.normalizedIrSha256) ||
                plan.components == null || plan.dataAssets == null)
                throw new InvalidOperationException("SPINE_NATIVE_STAGE_PLAN_INVALID");
            if (!plan.persistentVisiblePose || plan.visualPolicy != "native_renderer_enabled_timeScale_zero_source_timeScale_retained" ||
                plan.persistentVisiblePoseEvidence == null ||
                plan.persistentVisiblePoseEvidence.status != "verified_pinned_spine_unity_3_8_runtime_source" ||
                plan.persistentVisiblePoseEvidence.upstreamCommit != "8b4844bd4b193ba9e54487ed397a777993cbad56" ||
                plan.persistentVisiblePoseEvidence.runtimeVersion != "3.8.99" ||
                plan.persistentVisiblePoseEvidence.targetPolicy != "keep_native_renderer_enabled_and_set_timeScale_zero; preserve verified sourceTimeScale in identity/readback; no recovered game behavior" ||
                plan.components.Any(row => row == null || !row.persistentVisiblePose || !row.sourceTimeScaleVerified ||
                                           String.IsNullOrWhiteSpace(row.sourceComponentId) || String.IsNullOrWhiteSpace(row.sourcePrefabId) ||
                                           String.IsNullOrWhiteSpace(row.sourceNodeId) || row.templateOrigin == null ||
                                           String.IsNullOrWhiteSpace(row.templateOrigin.sourceComponentId) ||
                                           String.IsNullOrWhiteSpace(row.templateOrigin.sourcePrefabId) ||
                                           String.IsNullOrWhiteSpace(row.templateOrigin.sourceNodeId) ||
                                           row.templateOrigin.componentOriginChain == null || row.templateOrigin.componentOriginChain.Length < 1 ||
                                           row.templateOrigin.nodeOriginChain == null || row.templateOrigin.nodeOriginChain.Length < 1 ||
                                           row.templateOrigin.componentOriginChain[0] != row.sourceComponentId ||
                                           row.templateOrigin.componentOriginChain[row.templateOrigin.componentOriginChain.Length - 1] != row.templateOrigin.sourceComponentId ||
                                           row.templateOrigin.nodeOriginChain[0] != row.sourceNodeId ||
                                           row.templateOrigin.nodeOriginChain[row.templateOrigin.nodeOriginChain.Length - 1] != row.templateOrigin.sourceNodeId ||
                                           Double.IsNaN(row.sourceTimeScale) || Double.IsInfinity(row.sourceTimeScale)))
                throw new InvalidOperationException("SPINE_NATIVE_STAGE_VISUAL_POLICY_OR_SOURCE_TIME_SCALE_INVALID");
            if (plan.components.Select(row => row.sourceComponentId).Distinct(StringComparer.Ordinal).Count() != plan.components.Length ||
                plan.dataAssets.Select(row => row.sourceAssetId).Distinct(StringComparer.Ordinal).Count() != plan.dataAssets.Length)
                throw new InvalidOperationException("SPINE_NATIVE_STAGE_PLAN_DUPLICATE_SOURCE_ID");
            return plan;
        }

        /// <summary>Create all 16 (or plan-count) actual ScriptableObject assets, continuing across per-asset failures.</summary>
        public static CreateResult CreateDataAssets(Plan plan)
        {
            if (plan == null) throw new ArgumentNullException(nameof(plan));
            var result = new CreateResult();
            foreach (var row in plan.dataAssets ?? Array.Empty<DataAssetRow>())
            {
                try
                {
                    if (row.factoryInput == null || row.factoryInput.sourceAssetId != row.sourceAssetId)
                        throw new InvalidOperationException("factory_input_source_identity_mismatch");
                    var readback = UnitySpineNativeFactory.CreateDataAsset(row.factoryInput);
                    if (readback.sourceAssetId != row.sourceAssetId || !readback.nativeAssetIdentityVerified)
                        throw new InvalidOperationException("native_data_asset_identity_readback_failed");
                    var asset = UnityEditor.AssetDatabase.LoadAssetAtPath<SkeletonDataAsset>(row.skeletonDataAssetPath);
                    if (asset == null) throw new InvalidOperationException("saved_skeleton_data_asset_missing");
                    row.nativeDataAssetGuid = readback.skeletonDataAssetGuid;
                    result.dataAssets.Add(row.sourceAssetId, asset);
                    result.dataAssetReadbacks.Add(row.sourceAssetId, readback);
                    result.assetReadbacks.Add(readback);
                    foreach (var gap in readback.gaps) result.gaps.Add(new StageGap { sourceId = row.sourceAssetId, code = "SPINE_DATA_ASSET_GAP", message = gap });
                }
                catch (Exception error)
                {
                    var factoryError = error as UnitySpineNativeFactory.DataAssetCreateException;
                    var originalType = factoryError == null ? error.GetType().FullName : factoryError.originalExceptionType;
                    var originalStack = factoryError == null ? error.ToString() : factoryError.originalStackTrace;
                    var phase = factoryError == null ? "factory_input_or_existing_asset_validation" : factoryError.phase;
                    result.gaps.Add(new StageGap {
                        sourceId = row.sourceAssetId,
                        code = "SPINE_DATA_ASSET_CREATE_FAILED",
                        message = "phase=" + phase + "; " + error.GetType().Name + ": " + error.Message,
                        phase = phase,
                        exceptionType = originalType,
                        stackTrace = BoundDiagnosticText(originalStack),
                    });
                }
            }
            return result;
        }

        static string BoundDiagnosticText(string text)
        {
            if (String.IsNullOrEmpty(text)) return String.Empty;
            const int maxChars = UnitySpineNativeFactory.DiagnosticStackMaxChars;
            return text.Length <= maxChars ? text : text.Substring(0, maxChars) + "\n...[bounded]";
        }

        /// <summary>
        /// Attach native renderers to nodes the parent importer resolved from
        /// exact sourcePrefabId/sourceNodeId. RectTransform selects Graphic;
        /// no game/source name is used to decide the renderer.
        /// </summary>
        public static CreateResult CreateComponents(Plan plan, CreateResult assets,
            Func<string, string, GameObject> resolveNode, string onlySourcePrefabId = null)
        {
            if (plan == null || assets == null || resolveNode == null) throw new ArgumentNullException("Spine stage inputs and node resolver are required.");
            var result = new CreateResult();
            foreach (var asset in assets.dataAssets) result.dataAssets[asset.Key] = asset.Value;
            foreach (var asset in assets.dataAssetReadbacks) result.dataAssetReadbacks[asset.Key] = asset.Value;
            result.assetReadbacks.AddRange(assets.assetReadbacks);
            result.gaps.AddRange(assets.gaps);

            foreach (var row in plan.components ?? Array.Empty<ComponentRow>())
            {
                if (!String.IsNullOrEmpty(onlySourcePrefabId) && row.sourcePrefabId != onlySourcePrefabId) continue;
                try
                {
                    var node = resolveNode(row.sourcePrefabId, row.sourceNodeId);
                    if (node == null) throw new InvalidOperationException("exact_source_node_unresolved:" + row.sourceNodeId);
                    var rendererKind = node.transform is RectTransform
                        ? UnitySpineNativeFactory.RendererKind.SkeletonGraphic
                        : UnitySpineNativeFactory.RendererKind.SkeletonAnimation;
                    var component = UnitySpineNativeFactory.CreateComponent(node, row.sourceComponentId, rendererKind);
                    assets.dataAssets.TryGetValue(row.sourceDataAssetId ?? String.Empty, out var dataAsset);
                    assets.dataAssetReadbacks.TryGetValue(row.sourceDataAssetId ?? String.Empty, out var dataReadback);
                    var fields = ToTargetFields(row.targetFieldBindings, row.persistentVisiblePose);
                    var readback = UnitySpineNativeFactory.ApplyComponent(component, row.sourceComponentId,
                        row.sourceDataAssetId, dataAsset, fields, row.sourceHasStaticDataReference, dataReadback,
                        row.persistentVisiblePose);
                    AddFieldGaps(readback, row.fieldGaps);
                    result.components.Add(row.sourceComponentId, component);
                    result.componentReadbacks.Add(readback);
                    foreach (var gap in readback.gaps) result.gaps.Add(new StageGap { sourceId = row.sourceComponentId, code = "SPINE_COMPONENT_GAP", message = gap });
                }
                catch (Exception error)
                {
                    result.gaps.Add(new StageGap { sourceId = row.sourceComponentId, code = "SPINE_COMPONENT_CREATE_FAILED", message = error.GetType().Name + ": " + error.Message });
                }
            }
            return result;
        }

        /// <summary>Read saved/reopened native assets and components without repairing identity or fields.</summary>
        public static SavedReadResult ReadSaved(Plan plan, Func<string, Component> resolveSavedComponent,
            string onlySourcePrefabId = null)
        {
            if (plan == null || resolveSavedComponent == null) throw new ArgumentNullException("Spine plan and saved component resolver are required.");
            var result = new SavedReadResult();
            var assets = new Dictionary<string, SkeletonDataAsset>(StringComparer.Ordinal);
            var assetReadbacks = new Dictionary<string, UnitySpineNativeFactory.DataAssetReadback>(StringComparer.Ordinal);
            var neededAssetIds = new HashSet<string>((plan.components ?? Array.Empty<ComponentRow>())
                .Where(row => String.IsNullOrEmpty(onlySourcePrefabId) || row.sourcePrefabId == onlySourcePrefabId)
                .Where(row => row.sourceHasStaticDataReference && !String.IsNullOrEmpty(row.sourceDataAssetId))
                .Select(row => row.sourceDataAssetId), StringComparer.Ordinal);
            foreach (var row in plan.dataAssets ?? Array.Empty<DataAssetRow>())
            {
                if (!neededAssetIds.Contains(row.sourceAssetId)) continue;
                try
                {
                    var asset = UnityEditor.AssetDatabase.LoadAssetAtPath<SkeletonDataAsset>(row.skeletonDataAssetPath);
                    var readback = asset == null ? null : UnitySpineNativeFactory.ReadDataAssetAsset(row.factoryInput);
                    if (asset == null || readback == null || readback.sourceAssetId != row.sourceAssetId)
                        throw new InvalidOperationException("saved_native_data_asset_identity_mismatch");
                    assets.Add(row.sourceAssetId, asset); assetReadbacks.Add(row.sourceAssetId, readback); result.dataAssets.Add(readback);
                    foreach (var gap in readback.gaps) result.gaps.Add(new StageGap { sourceId = row.sourceAssetId, code = "SPINE_DATA_ASSET_READBACK_GAP", message = gap });
                }
                catch (Exception error)
                { result.gaps.Add(new StageGap { sourceId = row.sourceAssetId, code = "SPINE_DATA_ASSET_READBACK_FAILED", message = error.GetType().Name + ": " + error.Message }); }
            }

            foreach (var row in plan.components ?? Array.Empty<ComponentRow>())
            {
                if (!String.IsNullOrEmpty(onlySourcePrefabId) && row.sourcePrefabId != onlySourcePrefabId) continue;
                var component = resolveSavedComponent(row.sourceComponentId);
                assets.TryGetValue(row.sourceDataAssetId ?? String.Empty, out var asset);
                assetReadbacks.TryGetValue(row.sourceDataAssetId ?? String.Empty, out var dataReadback);
                var readback = UnitySpineNativeFactory.ReadComponent(row.sourceComponentId, row.sourceDataAssetId,
                    component, asset, row.sourceHasStaticDataReference,
                    ToTargetFields(row.targetFieldBindings, row.persistentVisiblePose),
                    null, dataReadback, row.persistentVisiblePose);
                AddFieldGaps(readback, row.fieldGaps);
                result.components.Add(readback);
                foreach (var gap in readback.gaps) result.gaps.Add(new StageGap { sourceId = row.sourceComponentId, code = "SPINE_COMPONENT_READBACK_GAP", message = gap });
            }
            return result;
        }

        public static UnitySpineNativeFactory.StaticPoseReadback SampleInitialPoseAtZero(Plan plan,
            string sourceComponentId, Component component, CreateResult createdAssets)
        {
            var row = (plan == null ? Array.Empty<ComponentRow>() : plan.components ?? Array.Empty<ComponentRow>())
                .SingleOrDefault(candidate => candidate.sourceComponentId == sourceComponentId);
            if (row == null) throw new InvalidOperationException("SPINE_COMPONENT_NOT_IN_FROZEN_PLAN");
            createdAssets.dataAssets.TryGetValue(row.sourceDataAssetId ?? String.Empty, out var asset);
            createdAssets.dataAssetReadbacks.TryGetValue(row.sourceDataAssetId ?? String.Empty, out var readback);
            var fields = ToTargetFields(row.targetFieldBindings, row.persistentVisiblePose);
            string skin = fields.TryGetValue("initialSkinName", out var skinValue) ? skinValue as string : null;
            string animation = fields.TryGetValue("startingAnimation", out var animationValue) ? animationValue as string : null;
            bool loop = fields.TryGetValue("startingLoop", out var loopValue) && loopValue is bool value && value;
            return UnitySpineNativeFactory.SampleInitialPoseAtZero(component, sourceComponentId,
                row.sourceDataAssetId, asset, readback, skin, animation, loop);
        }

        static Dictionary<string, object> ToTargetFields(FieldBinding[] bindings, bool persistentVisiblePose)
        {
            var result = new Dictionary<string, object>(StringComparer.Ordinal);
            foreach (var row in bindings ?? Array.Empty<FieldBinding>())
            {
                if (row == null || String.IsNullOrWhiteSpace(row.member) || row.status != "explicit" && row.status != "resolved_source_engine_default") continue;
                if (row.valueType == "bool") result[row.member] = row.boolValue;
                else if (row.valueType == "number") result[row.member] = row.numberValue;
                else if (row.valueType == "string") result[row.member] = row.stringValue;
            }
            if (persistentVisiblePose) result["timeScale"] = 0.0;
            return result;
        }

        static void AddFieldGaps(UnitySpineNativeFactory.ComponentReadback readback, FieldGap[] rows)
        {
            if (readback == null || rows == null || rows.Length == 0) return;
            var gaps = new List<string>(readback.gaps ?? Array.Empty<string>());
            var sourceOnly = new List<string>(readback.sourceOnlyFieldGaps ?? Array.Empty<string>());
            bool everyGapExplicitlyAllowlisted = true;
            for (int index = 0; index < rows.Length; index++)
            {
                var row = rows[index];
                if (row == null) { everyGapExplicitlyAllowlisted = false; continue; }
                var gap = "source_field_unmapped:" + row.sourceProperty + ":" + row.status;
                if (!gaps.Contains(gap)) gaps.Add(gap);
                if (IsExplicitlyAllowedSourceOnlyFieldGap(row))
                {
                    if (!sourceOnly.Contains(gap)) sourceOnly.Add(gap);
                }
                else everyGapExplicitlyAllowlisted = false;
            }
            readback.gaps = gaps.ToArray();
            readback.sourceOnlyFieldGaps = sourceOnly.ToArray();
            readback.mappedStaticFieldsVerified &= everyGapExplicitlyAllowlisted;
            readback.fieldsVerified = false;
            readback.nativeComplete = false;
        }

        static bool IsExplicitlyAllowedSourceOnlyFieldGap(FieldGap row)
        {
            if (row == null) return false;
            return row.sourceProperty == "playTimes" && row.status == "source_only_no_same_component_field" ||
                row.sourceProperty == "caching" && row.status == "source_only_runtime_cache_mapping_unresolved";
        }
    }
}
