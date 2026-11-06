// Static, time-zero SkeletonGraphic preparation for the frozen Cocos Spine source join.
// Source callbacks and recovered game scripts are never executed here.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Spine.Unity;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;
using Monkey.Targets.Spine;

public static partial class MonkeyImporter
{
    [Serializable] sealed class StaticSpineRenderingEnvelope
    {
        public int schemaVersion;
        public string contract,sourceManifestSha256;
        public StaticSpineRenderingData[] dataAssets;
        public StaticSpineRenderingComponent[] components;
        public StaticSpineRenderingPayload[] payloads;
    }

    [Serializable] sealed class StaticSpineCanvasComponentEvidence
    {
        public string sourceComponentId, sourcePrefabId, sourceNodeId, sourceDataAssetId;
        public int sourceCanvasContextIndex;
        public bool sourceCanvasContextVerified, sourceNodeActive, sourceNodeActivityVerified, sourceComponentEnabled;
    }

    [Serializable] sealed class StaticSpineCanvasContextEvidenceRow
    {
        public int contextIndex;
        public string sourceCanvasRenderMode, sourceCanvasScaleMode;
        public float sourceCanvasReferencePixelsPerUnit, sourceScalerReferencePixelsPerUnit,
            sourceScalerMatchWidthOrHeight;
        public float[] sourceScalerReferenceResolution;
        public bool sourceCanvasScalerPresent, sourceCanvasPpuMatchesScaler;
        public string[] sourceNodeIds;
    }

    [Serializable] sealed class StaticSpineCanvasContextEvidence
    {
        public int schemaVersion = 1;
        public string contract = "monkey-static-spine-source-canvas-context/1";
        public string sourceManifestSha256, renderingPlanSha256, evidenceSha256;
        public string capturePhase = "source-construction-before-prefab-save";
        public float sourceReferencePixelsPerUnit;
        public bool sourceNodeGeometryVerified, sourceCanvasContextVerified;
        public int sourceNodeCount;
        public StaticSpineCanvasContextEvidenceRow[] contexts;
        public StaticSpineCanvasComponentEvidence[] components;
    }

    [Serializable] sealed class StaticSpineControlledHostContextEvidence
    {
        public int schemaVersion = 1;
        public string contract = "monkey-static-spine-controlled-prefab-host/1";
        public string sourceManifestSha256, renderingPlanSha256, sourceCanvasEvidenceSha256, evidenceSha256, contextKind;
        public string sourceCanvasRenderMode, controlledHostCanvasRenderMode, controlledHostScaleMode;
        public float sourceCanvasReferencePixelsPerUnit, sourceScalerReferencePixelsPerUnit,
            controlledHostReferencePixelsPerUnit;
        public bool sourceCanvasScalerPresent, sourceContextVerified, controlledHostCanvasScalerAbsent,
            controlledHostGeometryMatchesPlan, verified;
    }

    sealed class StaticSpineSourceCanvasLiveRegistration
    {
        public Canvas canvas;
        public GameObject sourceNode;
        public StaticSpineCanvasContextEvidence evidence;
        public string sourceComponentId, sourcePrefabId, sourceNodeId, sourceDataAssetId;
    }

    [Serializable] sealed class StaticSpineOwnerContextLifecycleRow
    {
        public string phase, sourceComponentId, sourceDataAssetId, sourcePrefabId, sourceNodeId, templateComponentId;
        public string instanceOwnerPrefabId, instanceRootNodeId, instanceNodeId, templatePrefabId, templateNodeId;
        public string[] sourceActivityPath;
        public bool[] sourceActivityValues;
        public string priorOwnerType, priorOwnerPath, priorOwnerAssetPath, priorOwnerGuid;
        public long priorOwnerLocalFileId;
        public bool priorOwnerPersistent;
        public string actualOwnerType, actualOwnerPath, actualOwnerAssetPath, actualOwnerGuid;
        public long actualOwnerLocalFileId;
        public bool actualOwnerPersistent;
        public string dataAssetType, dataAssetPath, dataAssetGuid;
        public long dataAssetLocalFileId;
        public string sourceCanvasEvidenceSha256, renderingPlanSha256, sourceManifestSha256;
        public string controlledHostEvidenceSha256, controlledHostCanvasRenderMode;
        public string sourceCanvasRenderMode, actualCanvasRenderMode, actualCanvasScaleMode;
        public float sourceCanvasPpu, sourceScalerPpu, actualCanvasPpu, actualScalerPpu, actualScalerMatchWidthOrHeight,
            controlledHostCanvasPpu;
        public float[] actualScalerReferenceResolution;
        public bool sourceCanvasScalerPresent, actualCanvasScalerPresent, controlledHostContextVerified,
            ownerPairRegistered, sourceActivityPathVerified, verified;
        public bool priorOwnerRetired, priorOwnerRegistryRevoked;
        public string registrationStatus, diagnostic;
    }

    [Serializable] sealed class StaticSpineOwnerContextLifecycleComponent
    {
        public string sourceComponentId, sourceDataAssetId, sourcePrefabId, sourceNodeId, templateComponentId;
        public bool eligible, sourceConstructionOwnerRegistered;
        public string sourceConstructionOwnerType, sourceConstructionOwnerPath, sourceConstructionDataAssetPath,
            sourceConstructionDataAssetGuid, sourceCanvasEvidenceSha256, sourceCanvasRenderMode;
        public float sourceCanvasPpu, sourceScalerPpu;
        public StaticSpineOwnerContextLifecycleRow[] transitions;
    }

    [Serializable] sealed class StaticSpineOwnerContextLifecycleEnvelope
    {
        public int schemaVersion = 1;
        public string contract = "monkey-static-spine-owner-context-lifecycle/1";
        public string phase = "native-import";
        public string sourceCanvasEvidenceContract = "monkey-static-spine-source-canvas-context/1";
        public string sourceManifestSha256, renderingPlanSha256, sourceCanvasEvidenceSha256, evidenceSha256;
        public StaticSpineOwnerContextLifecycleComponent[] components;
        public StaticSpineOwnerContextLifecycleRow[] transitions;
    }

    sealed class StaticSpineNativeInstanceOwnerRegistration
    {
        public string sourceComponentId, sourceDataAssetId, sourcePrefabId, sourceNodeId, templateComponentId;
        public SkeletonGraphic priorOwner, owner;
        public SkeletonDataAsset dataAsset;
        public GameObject prefabRoot, instanceRoot;
        public StaticSpineCanvasContextEvidence sourceEvidence;
        public StaticSpineOwnerContextLifecycleRow lifecycle;
    }

    sealed class StaticSpineControlledCanvasRegistration
    {
        public GameObject host;
        public Canvas canvas;
        public StaticSpineControlledHostContextEvidence evidence;
    }

    sealed class StaticSpineReadbackOwnerRegistration
    {
        public string sourceComponentId, sourceDataAssetId, sourcePrefabId, sourceNodeId;
        public SkeletonGraphic persistentOwner, loadedOwner;
        public SkeletonDataAsset dataAsset;
        public bool sourceNodeActive;
        public GameObject controlledHost;
        public StaticSpineCanvasContextEvidence sourceEvidence;
        public StaticSpineControlledHostContextEvidence hostEvidence;
    }

    sealed class StaticSpineReadbackOwnerScope
    {
        public readonly List<StaticSpineReadbackOwnerRegistration> rows = new List<StaticSpineReadbackOwnerRegistration>();
    }

    [Serializable] sealed class StaticSpineRenderingPayload {public string target,sha256;}
    [Serializable] sealed class StaticSpineRenderingAssembly {
        public string target,expectedSha256,loadedPath,loadedSha256;public bool verified;
    }
    [Serializable] sealed class StaticSpineRenderingData
    {
        public string sourceDataAssetId;
        public bool eligible;
        public UnitySpineNativeFactory.DataAssetSpec factorySpec;
    }

    [Serializable] sealed class StaticSpineRenderingComponent
    {
        public string sourceComponentId;
        public string sourceNodeId;
        public string sourcePrefabId;
        public string templateComponentId;
        public string sourceDataAssetId;
        public bool eligible;
        public bool sourceVisible;
        public bool sourceComponentEnabled;
        public string gap;
        public string sourceSkin;
        public bool sourceSkinSerialized;
        public string sourceAnimation;
        public bool sourceAnimationSerialized;
        public bool sourceLoop;
        public bool sourceLoopSerialized;
        public int[] sourceNodeColorRgba8;
    }

    [Serializable] sealed class StaticSpineRenderingReadback
    {
        public string sourceComponentId;
        public string sourceDataAssetId;
        public string rendererGuid;
        public long rendererLocalId;
        public string dataAssetGuid;
        public long dataAssetLocalId;
        public bool verified;
        public bool rendererCreated;
        public bool sourceVisible;
        public bool sourceComponentEnabled;
        public bool sourceVisibleVerified;
        public bool rendererEnabled;
        public bool sourceNodeActive, sourceNodeActivityVerified;
        public bool sourceCodeExecuted;
        public bool persistent,dataPersistent,serializedFieldsVerified,actualSkinImplicitDefault;
        public bool sourceLoop,actualLoop,sourceLoopSerialized;
        public float timeScale;
        public string loopStatus;
        public bool unitMappingVerified;
        public float sourceDefaultScale;
        public float targetUnitsPerSourcePixel;
        public float canvasReferencePixelsPerUnit;
        public float sourceCanvasReferencePixelsPerUnit, sourceScalerReferencePixelsPerUnit,
            controlledHostCanvasReferencePixelsPerUnit;
        public string sourceCanvasContextEvidenceSha256, sourceCanvasContextKind, controlledHostContextKind,
            sourceCanvasRenderMode, controlledHostCanvasRenderMode;
        public string controlledHostContextEvidenceSha256;
        public bool sourceCanvasContextVerified, controlledHostContextVerified;
        public StaticSpineControlledHostContextEvidence controlledHostContextEvidence;
        public float dataScale;
        public bool poseVerified;
        public bool colorVerified;
        public bool materialReferencesVerified;
        public int meshVertexCount;
        public int meshTriangleCount;
        public string sourceSkin;
        public string actualSkin;
        public string sourceAnimation;
        public string actualAnimation;
        public float trackTime;
        public string[] gaps;
    }

    [Serializable] sealed class StaticSpineRenderingReadbackEnvelope
    {
        public int schemaVersion = 1;
        public string contract="monkey-static-spine-rendering-readback/1";
        public string status,phase,sourceManifestSha256,renderingPlanSha256,sourcePrefabId,unityVersion;
        public string sourceCanvasContextEvidencePath, sourceCanvasContextEvidenceFileSha256;
        public StaticSpineCanvasContextEvidence sourceCanvasContext;
        public StaticSpineRenderingReadback[] components;
        public StaticSpineRenderingAssembly[] runtimeAssemblies;
    }

    const string StaticSpineRenderingPlanPath = "Assets/Game/Editor/Conversion/spine-static-rendering.json";
    const string StaticSpineRenderingReadbackRoot = "Analysis/Readback/SpineRendering";
    const string StaticSpineCanvasContextEvidencePath = "Analysis/Readback/SpineRendering/source-canvas-context.json";
    const string StaticSpineOwnerContextLifecyclePath = "Analysis/Readback/SpineRendering/owner-context-lifecycle.json";
    static StaticSpineRenderingEnvelope staticSpineRenderingPlan;
    static string staticSpineRenderingPlanSha;
    static StaticSpineRenderingAssembly[] staticSpineRenderingAssemblies;
    static bool staticSpineRenderingUnitMappingVerified;
    static float staticSpineRenderingCanvasPpu;
    static StaticSpineCanvasContextEvidence staticSpineSourceCanvasContext;
    static readonly Dictionary<string, StaticSpineSourceCanvasLiveRegistration> staticSpineSourceCanvasOwners =
        new Dictionary<string, StaticSpineSourceCanvasLiveRegistration>(StringComparer.Ordinal);
    static readonly List<StaticSpineControlledCanvasRegistration> staticSpineControlledCanvasContexts =
        new List<StaticSpineControlledCanvasRegistration>();
    static readonly List<StaticSpineReadbackOwnerScope> staticSpineReadbackOwnerScopes =
        new List<StaticSpineReadbackOwnerScope>();
    static readonly List<StaticSpineNativeInstanceOwnerRegistration> staticSpineNativeInstanceOwners =
        new List<StaticSpineNativeInstanceOwnerRegistration>();
    static readonly List<StaticSpineOwnerContextLifecycleRow> staticSpineOwnerContextLifecycleRows =
        new List<StaticSpineOwnerContextLifecycleRow>();
    static readonly List<StaticSpineOwnerContextLifecycleComponent> staticSpineOwnerContextLifecycleComponents =
        new List<StaticSpineOwnerContextLifecycleComponent>();
    static readonly HashSet<Graphic> staticSpineRetiredNativeInstanceOwners = new HashSet<Graphic>();
    static readonly Dictionary<string, UnitySpineNativeFactory.DataAssetReadback> staticSpineRenderingAssets =
        new Dictionary<string, UnitySpineNativeFactory.DataAssetReadback>(StringComparer.Ordinal);

    static StaticSpineCanvasContextEvidence BuildStaticSpineSourceCanvasContextEvidence(
        Plan plan, Dictionary<string, GameObject> nodes, float expectedPpu, bool sourceGeometryVerified)
    {
        if (plan == null || nodes == null || plan.nodes == null || expectedPpu <= 0f ||
            Single.IsNaN(expectedPpu) || Single.IsInfinity(expectedPpu))
            throw new InvalidOperationException("SPINE_SOURCE_CANVAS_EVIDENCE_INPUT_INVALID");
        var rendering = JsonUtility.FromJson<StaticSpineRenderingEnvelope>(plan.staticSpineRenderingJson);
        if (rendering == null || rendering.components == null || rendering.sourceManifestSha256 != plan.sourceManifestSha256)
            throw new InvalidOperationException("SPINE_SOURCE_CANVAS_EVIDENCE_RENDERING_PLAN_INVALID");

        var canvases = new List<Canvas>();
        var canvasNodeIds = new List<List<string>>();
        var nodeCanvasIndices = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (var sourceNode in plan.nodes)
        {
            if (sourceNode == null || String.IsNullOrWhiteSpace(sourceNode.sourceId) ||
                !nodes.TryGetValue(sourceNode.sourceId, out var node) || node == null)
                throw new InvalidOperationException("SPINE_SOURCE_CANVAS_EVIDENCE_NODE_MISSING:" +
                    (sourceNode == null ? "null" : sourceNode.sourceId));
            var canvas = node.GetComponentInParent<Canvas>(true);
            var scaler = canvas == null ? null : canvas.GetComponent<CanvasScaler>();
            if (canvas == null || scaler == null || canvas.renderMode != RenderMode.ScreenSpaceOverlay ||
                !SpineUnitClose(canvas.referencePixelsPerUnit, scaler.referencePixelsPerUnit) ||
                !SpineUnitClose(canvas.referencePixelsPerUnit, expectedPpu) || canvas.referencePixelsPerUnit <= 0f ||
                Single.IsNaN(canvas.referencePixelsPerUnit) || Single.IsInfinity(canvas.referencePixelsPerUnit))
                throw new InvalidOperationException("SPINE_SOURCE_CANVAS_EVIDENCE_CONTEXT_DIFFERS:" + sourceNode.sourceId);
            var index = canvases.FindIndex(value => value == canvas);
            if (index < 0)
            {
                index = canvases.Count;
                canvases.Add(canvas);
                canvasNodeIds.Add(new List<string>());
            }
            canvasNodeIds[index].Add(sourceNode.sourceId);
            nodeCanvasIndices.Add(sourceNode.sourceId, index);
        }
        if (canvases.Count == 0) throw new InvalidOperationException("SPINE_SOURCE_CANVAS_EVIDENCE_CANVAS_SET_EMPTY");

        var contexts = new StaticSpineCanvasContextEvidenceRow[canvases.Count];
        for (int i = 0; i < canvases.Count; i++)
        {
            var canvas = canvases[i];
            var scaler = canvas.GetComponent<CanvasScaler>();
            contexts[i] = new StaticSpineCanvasContextEvidenceRow
            {
                contextIndex = i,
                sourceCanvasRenderMode = canvas.renderMode.ToString(),
                sourceCanvasScaleMode = scaler.uiScaleMode.ToString(),
                sourceCanvasReferencePixelsPerUnit = canvas.referencePixelsPerUnit,
                sourceScalerReferencePixelsPerUnit = scaler.referencePixelsPerUnit,
                sourceScalerMatchWidthOrHeight = scaler.matchWidthOrHeight,
                sourceScalerReferenceResolution = new[] { scaler.referenceResolution.x, scaler.referenceResolution.y },
                sourceCanvasScalerPresent = true,
                sourceCanvasPpuMatchesScaler = SpineUnitClose(canvas.referencePixelsPerUnit, scaler.referencePixelsPerUnit),
                sourceNodeIds = canvasNodeIds[i].OrderBy(value => value, StringComparer.Ordinal).ToArray(),
            };
        }

        staticSpineSourceCanvasOwners.Clear();
        var nodeSpecs = plan.nodes.Where(row => row != null && !String.IsNullOrWhiteSpace(row.sourceId))
            .ToDictionary(row => row.sourceId, StringComparer.Ordinal);
        var componentEvidence = new List<StaticSpineCanvasComponentEvidence>();
        foreach (var component in rendering.components.Where(row => row != null))
        {
            if (String.IsNullOrWhiteSpace(component.sourceComponentId) || String.IsNullOrWhiteSpace(component.sourceNodeId) ||
                String.IsNullOrWhiteSpace(component.sourceDataAssetId) || !nodeCanvasIndices.TryGetValue(component.sourceNodeId, out var contextIndex))
                throw new InvalidOperationException("SPINE_SOURCE_CANVAS_EVIDENCE_COMPONENT_SOURCE_JOIN_MISSING:" +
                    (component.sourceComponentId ?? "null"));
            if (!nodeSpecs.TryGetValue(component.sourceNodeId, out var sourceNodeSpec))
                throw new InvalidOperationException("SPINE_SOURCE_CANVAS_EVIDENCE_NODE_PLAN_MISSING:" + component.sourceNodeId);
            var componentRow = new StaticSpineCanvasComponentEvidence
            {
                sourceComponentId = component.sourceComponentId,
                sourcePrefabId = component.sourcePrefabId,
                sourceNodeId = component.sourceNodeId,
                sourceDataAssetId = component.sourceDataAssetId,
                sourceCanvasContextIndex = contextIndex,
                sourceNodeActive = sourceNodeSpec.active,
                sourceNodeActivityVerified = nodes[component.sourceNodeId].activeSelf == sourceNodeSpec.active,
                sourceComponentEnabled = component.sourceComponentEnabled,
                sourceCanvasContextVerified = contexts[contextIndex].sourceCanvasPpuMatchesScaler &&
                    contexts[contextIndex].sourceCanvasRenderMode == RenderMode.ScreenSpaceOverlay.ToString(),
            };
            componentEvidence.Add(componentRow);
            if (componentRow.sourceCanvasContextVerified)
                staticSpineSourceCanvasOwners.Add(component.sourceComponentId, new StaticSpineSourceCanvasLiveRegistration
                {
                    canvas = canvases[contextIndex], sourceNode = nodes[component.sourceNodeId],
                    sourceComponentId = component.sourceComponentId, sourcePrefabId = component.sourcePrefabId,
                    sourceNodeId = component.sourceNodeId, sourceDataAssetId = component.sourceDataAssetId,
                });
        }

        var contextEvidence = new StaticSpineCanvasContextEvidence
        {
            sourceManifestSha256 = plan.sourceManifestSha256,
            sourceNodeGeometryVerified = sourceGeometryVerified,
            sourceCanvasContextVerified = contexts.Length > 0 && contexts.All(row => row.sourceCanvasScalerPresent &&
                row.sourceCanvasPpuMatchesScaler && row.sourceCanvasRenderMode == RenderMode.ScreenSpaceOverlay.ToString() &&
                SpineUnitClose(row.sourceCanvasReferencePixelsPerUnit, expectedPpu)),
            sourceReferencePixelsPerUnit = expectedPpu,
            sourceNodeCount = plan.nodes.Length,
            contexts = contexts,
            components = componentEvidence.OrderBy(row => row.sourceComponentId, StringComparer.Ordinal).ToArray(),
        };
        var renderingPath = Path.Combine(Directory.GetParent(Application.dataPath).FullName, StaticSpineRenderingPlanPath);
        if (!File.Exists(renderingPath)) throw new InvalidOperationException("SPINE_SOURCE_CANVAS_EVIDENCE_RENDERING_FILE_MISSING");
        contextEvidence.renderingPlanSha256 = StaticSpineCanvasHashBytes(File.ReadAllBytes(renderingPath));
        contextEvidence.evidenceSha256 = StaticSpineCanvasEvidenceHash(contextEvidence);
            if (!contextEvidence.sourceNodeGeometryVerified || !contextEvidence.sourceCanvasContextVerified ||
            contextEvidence.components.Length != rendering.components.Length ||
            contextEvidence.components.Any(row => !row.sourceCanvasContextVerified || !row.sourceNodeActivityVerified))
            throw new InvalidOperationException("SPINE_SOURCE_CANVAS_EVIDENCE_INCOMPLETE");
        foreach (var registration in staticSpineSourceCanvasOwners.Values)
            registration.evidence = contextEvidence;
        return contextEvidence;
    }

    static string StaticSpineCanvasEvidenceHash(StaticSpineCanvasContextEvidence evidence)
    {
        if (evidence == null) return null;
        var copy = JsonUtility.FromJson<StaticSpineCanvasContextEvidence>(JsonUtility.ToJson(evidence));
        if (copy == null) return null;
        copy.evidenceSha256 = null;
        using (var digest = SHA256.Create())
            return BitConverter.ToString(digest.ComputeHash(Encoding.UTF8.GetBytes(JsonUtility.ToJson(copy))))
                .Replace("-", String.Empty).ToLowerInvariant();
    }

    static string StaticSpineCanvasHashBytes(byte[] bytes)
    {
        using (var digest = SHA256.Create())
            return BitConverter.ToString(digest.ComputeHash(bytes ?? Array.Empty<byte>())).Replace("-", String.Empty).ToLowerInvariant();
    }

    static string StaticSpineControlledHostEvidenceHash(StaticSpineControlledHostContextEvidence evidence)
    {
        if (evidence == null) return null;
        var copy = JsonUtility.FromJson<StaticSpineControlledHostContextEvidence>(JsonUtility.ToJson(evidence));
        if (copy == null) return null;
        copy.evidenceSha256 = null;
        using (var digest = SHA256.Create())
            return BitConverter.ToString(digest.ComputeHash(Encoding.UTF8.GetBytes(JsonUtility.ToJson(copy))))
                .Replace("-", String.Empty).ToLowerInvariant();
    }

    static bool StaticSpineCanvasContextEvidenceMatches(StaticSpineCanvasContextEvidence evidence,
        string sourceComponentId, string sourceDataAssetId, string sourceManifestSha256,
        string renderingPlanSha256, float controlledHostPpu, string controlledHostRenderMode,
        bool controlledHostCanvasScalerAbsent)
    {
        if (evidence == null || evidence.schemaVersion != 1 ||
            evidence.contract != "monkey-static-spine-source-canvas-context/1" ||
            evidence.sourceManifestSha256 != sourceManifestSha256 || evidence.renderingPlanSha256 != renderingPlanSha256 ||
            !evidence.sourceNodeGeometryVerified || !evidence.sourceCanvasContextVerified ||
            evidence.sourceNodeCount <= 0 || evidence.contexts == null || evidence.contexts.Length == 0 ||
            evidence.components == null || String.IsNullOrWhiteSpace(sourceComponentId) ||
            String.IsNullOrWhiteSpace(sourceDataAssetId) || evidence.evidenceSha256 != StaticSpineCanvasEvidenceHash(evidence) ||
            controlledHostRenderMode != RenderMode.WorldSpace.ToString() || !controlledHostCanvasScalerAbsent ||
            controlledHostPpu <= 0f || Single.IsNaN(controlledHostPpu) || Single.IsInfinity(controlledHostPpu) ||
            !SpineUnitClose(controlledHostPpu, evidence.sourceReferencePixelsPerUnit)) return false;
        var rows = evidence.components.Where(row => row != null && row.sourceComponentId == sourceComponentId &&
            row.sourceDataAssetId == sourceDataAssetId && row.sourceCanvasContextVerified && row.sourceNodeActivityVerified).ToArray();
        if (rows.Length != 1 || rows[0].sourceCanvasContextIndex < 0 || rows[0].sourceCanvasContextIndex >= evidence.contexts.Length)
            return false;
        var context = evidence.contexts[rows[0].sourceCanvasContextIndex];
        return context != null && context.contextIndex == rows[0].sourceCanvasContextIndex &&
            context.sourceCanvasScalerPresent && context.sourceCanvasPpuMatchesScaler &&
            context.sourceCanvasRenderMode == RenderMode.ScreenSpaceOverlay.ToString() &&
            SpineUnitClose(context.sourceCanvasReferencePixelsPerUnit, evidence.sourceReferencePixelsPerUnit) &&
            SpineUnitClose(context.sourceScalerReferencePixelsPerUnit, evidence.sourceReferencePixelsPerUnit);
    }

    static StaticSpineCanvasComponentEvidence StaticSpineSourceCanvasComponent(string sourceComponentId,
        string sourceDataAssetId, string sourceManifestSha256, string renderingPlanSha256)
    {
        var evidence = staticSpineSourceCanvasContext;
        if (evidence == null || evidence.sourceManifestSha256 != sourceManifestSha256 ||
            evidence.renderingPlanSha256 != renderingPlanSha256 ||
            evidence.evidenceSha256 != StaticSpineCanvasEvidenceHash(evidence)) return null;
        var rows = (evidence.components ?? Array.Empty<StaticSpineCanvasComponentEvidence>())
            .Where(row => row != null && row.sourceComponentId == sourceComponentId && row.sourceDataAssetId == sourceDataAssetId)
            .ToArray();
        return rows.Length == 1 && rows[0].sourceCanvasContextVerified && rows[0].sourceNodeActivityVerified ? rows[0] : null;
    }

    static StaticSpineControlledHostContextEvidence MakeStaticSpineControlledHostEvidence(
        GameObject context, Plan plan, Canvas canvas)
    {
        if (context == null || plan == null || canvas == null || staticSpineSourceCanvasContext == null ||
            staticSpineRenderingPlan == null || plan.sourceManifestSha256 != staticSpineRenderingPlan.sourceManifestSha256 ||
            String.IsNullOrEmpty(plan.staticSpineRenderingJson) ||
            staticSpineSourceCanvasContext.evidenceSha256 != StaticSpineCanvasEvidenceHash(staticSpineSourceCanvasContext))
            throw new InvalidOperationException("SPINE_CONTROLLED_HOST_SOURCE_CONTEXT_UNAVAILABLE");
        var scaler = context.GetComponent<CanvasScaler>();
        var rect = context.transform as RectTransform;
        bool geometryMatches = rect != null && plan.designSize != null && plan.designSize.Length == 2 &&
            SpineUnitClose(rect.pivot.x, 0f) && SpineUnitClose(rect.pivot.y, 0f) &&
            SpineUnitClose(rect.sizeDelta.x, plan.designSize[0]) && SpineUnitClose(rect.sizeDelta.y, plan.designSize[1]);
        var result = new StaticSpineControlledHostContextEvidence
        {
            sourceManifestSha256 = staticSpineSourceCanvasContext.sourceManifestSha256,
            renderingPlanSha256 = staticSpineSourceCanvasContext.renderingPlanSha256,
            sourceCanvasEvidenceSha256 = staticSpineSourceCanvasContext.evidenceSha256,
            contextKind = "created-by-monkey-owned-prefab-ui-context",
            sourceCanvasRenderMode = staticSpineSourceCanvasContext.contexts.First().sourceCanvasRenderMode,
            controlledHostCanvasRenderMode = canvas.renderMode.ToString(),
            controlledHostScaleMode = scaler == null ? "none" : scaler.uiScaleMode.ToString(),
            sourceCanvasReferencePixelsPerUnit = staticSpineSourceCanvasContext.sourceReferencePixelsPerUnit,
            sourceScalerReferencePixelsPerUnit = staticSpineSourceCanvasContext.contexts.First().sourceScalerReferencePixelsPerUnit,
            controlledHostReferencePixelsPerUnit = canvas.referencePixelsPerUnit,
            sourceCanvasScalerPresent = staticSpineSourceCanvasContext.contexts.All(row => row.sourceCanvasScalerPresent),
            sourceContextVerified = staticSpineSourceCanvasContext.sourceCanvasContextVerified &&
                staticSpineSourceCanvasContext.sourceNodeGeometryVerified,
            controlledHostCanvasScalerAbsent = scaler == null,
            controlledHostGeometryMatchesPlan = geometryMatches,
        };
        result.verified = result.sourceContextVerified && result.controlledHostCanvasScalerAbsent &&
            result.controlledHostCanvasRenderMode == RenderMode.WorldSpace.ToString() && result.controlledHostGeometryMatchesPlan &&
            staticSpineSourceCanvasContext.components.All(row => row != null && StaticSpineCanvasContextEvidenceMatches(
                staticSpineSourceCanvasContext, row.sourceComponentId, row.sourceDataAssetId,
                result.sourceManifestSha256, result.renderingPlanSha256, result.controlledHostReferencePixelsPerUnit,
                result.controlledHostCanvasRenderMode, result.controlledHostCanvasScalerAbsent));
        result.evidenceSha256 = StaticSpineControlledHostEvidenceHash(result);
        if (!result.verified) throw new InvalidOperationException("SPINE_CONTROLLED_HOST_CANVAS_CONTEXT_DIFFERS_FROM_SOURCE_EVIDENCE");
        return result;
    }

    static StaticSpineControlledCanvasRegistration FindStaticSpineControlledCanvas(Canvas canvas)
    {
        if (canvas == null) return null;
        return staticSpineControlledCanvasContexts.FirstOrDefault(row => row != null && row.canvas == canvas &&
            row.host == canvas.gameObject && row.evidence != null && row.evidence.verified &&
            row.evidence.evidenceSha256 == StaticSpineControlledHostEvidenceHash(row.evidence));
    }

    static bool StaticSpineRendererIdentityMatches(Graphic graphic, StaticSpineRenderingComponent component)
    {
        var owner = graphic as SkeletonGraphic;
        if (owner == null || owner.GetType() != typeof(SkeletonGraphic) || component == null) return false;
        var markers = owner.GetComponents<UnitySpineSourceIdentity>().Where(row => row != null && row.renderer == owner &&
            row.instanceSourceComponentId == component.sourceComponentId &&
            row.templateSourcePrefabId == component.sourcePrefabId &&
            row.templateSourceId == (String.IsNullOrEmpty(component.templateComponentId) ? component.sourceComponentId : component.templateComponentId) &&
            row.rendererKind == typeof(SkeletonGraphic).FullName).ToArray();
        return markers.Length == 1;
    }

    static string StaticSpineOwnerRelativePath(GameObject root, GameObject owner)
    {
        if (root == null || owner == null) return null;
        var parts = new List<string>();
        var cursor = owner.transform;
        while (cursor != null && cursor != root.transform)
        {
            parts.Add(cursor.GetSiblingIndex().ToString() + ":" + cursor.name);
            cursor = cursor.parent;
        }
        if (cursor != root.transform) return null;
        parts.Add("root:" + root.name);
        parts.Reverse();
        return String.Join("/", parts);
    }

    static string StaticSpineAssetGuid(UnityEngine.Object asset, out long localId)
    {
        localId = 0;
        if (asset == null || !EditorUtility.IsPersistent(asset)) return null;
        return AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset, out var guid, out localId) ? guid : null;
    }

    static StaticSpineCanvasContextEvidenceRow StaticSpineSourceCanvasContextRow(StaticSpineCanvasComponentEvidence component)
    {
        return component == null || staticSpineSourceCanvasContext == null ? null :
            (staticSpineSourceCanvasContext.contexts ?? Array.Empty<StaticSpineCanvasContextEvidenceRow>())
                .SingleOrDefault(row => row != null && row.contextIndex == component.sourceCanvasContextIndex);
    }

    static bool StaticSpineCloneCanvasMatchesSource(Graphic owner, StaticSpineCanvasComponentEvidence component,
        out Canvas canvas, out string diagnostic)
    {
        canvas = owner == null ? null : owner.GetComponentInParent<Canvas>(true);
        diagnostic = null;
        var source = StaticSpineSourceCanvasContextRow(component);
        var scaler = canvas == null ? null : canvas.GetComponent<CanvasScaler>();
        if (source == null || canvas == null)
        { diagnostic = "clone-canvas-or-source-context-missing"; return false; }
        if (source.sourceCanvasScalerPresent != (scaler != null) ||
            canvas.renderMode.ToString() != source.sourceCanvasRenderMode ||
            !SpineUnitClose(canvas.referencePixelsPerUnit, source.sourceCanvasReferencePixelsPerUnit))
        { diagnostic = "clone-canvas-render-mode-or-ppu-differs-from-source"; return false; }
        if (scaler != null && (scaler.uiScaleMode.ToString() != source.sourceCanvasScaleMode ||
            !SpineUnitClose(scaler.referencePixelsPerUnit, source.sourceScalerReferencePixelsPerUnit) ||
            !SpineUnitClose(scaler.matchWidthOrHeight, source.sourceScalerMatchWidthOrHeight) ||
            source.sourceScalerReferenceResolution == null || source.sourceScalerReferenceResolution.Length != 2 ||
            !SpineUnitClose(scaler.referenceResolution.x, source.sourceScalerReferenceResolution[0]) ||
            !SpineUnitClose(scaler.referenceResolution.y, source.sourceScalerReferenceResolution[1])))
        { diagnostic = "clone-canvas-scaler-fields-differ-from-source"; return false; }
        return true;
    }

    static bool StaticSpineInstanceActivityPathMatches(Plan plan, string sourceNodeId, string sourceRootId,
        IDictionary<string, GameObject> actualNodes, Dictionary<UnityEngine.Object, UnityEngine.Object> replacements,
        out string[] path, out bool[] activeValues, out GameObject oldRoot, out GameObject actualRoot, out string diagnostic)
    {
        path = Array.Empty<string>(); activeValues = Array.Empty<bool>(); oldRoot = null; actualRoot = null; diagnostic = null;
        var specs = (plan == null ? Array.Empty<NodeSpec>() : plan.nodes ?? Array.Empty<NodeSpec>())
            .Where(row => row != null && !String.IsNullOrWhiteSpace(row.sourceId)).ToArray();
        var matches = specs.GroupBy(row => row.sourceId, StringComparer.Ordinal)
            .Where(group => group.Count() != 1).Select(group => group.Key).ToArray();
        if (matches.Length != 0)
        { diagnostic = "source-node-plan-identity-ambiguous:" + matches[0]; return false; }
        var byId = specs.ToDictionary(row => row.sourceId, StringComparer.Ordinal);
        var pathRows = new List<string>();
        var values = new List<bool>();
        var actualPathNodes = new List<GameObject>();
        var previousPathNodes = new List<GameObject>();
        var seen = new HashSet<string>(StringComparer.Ordinal);
        var cursorId = sourceNodeId;
        while (true)
        {
            if (String.IsNullOrWhiteSpace(cursorId) || !seen.Add(cursorId) || !byId.TryGetValue(cursorId, out var nodeSpec) ||
                actualNodes == null || !actualNodes.TryGetValue(cursorId, out var actualNode) || actualNode == null)
            { diagnostic = "source-activity-path-source-or-actual-node-missing:" + (cursorId ?? "<null>"); return false; }
            var previousRows = replacements == null ? Array.Empty<GameObject>() : replacements
                .Where(pair => pair.Key is GameObject && pair.Value == actualNode)
                .Select(pair => pair.Key as GameObject).Where(value => value != null).ToArray();
            if (previousRows.Length != 1 || previousRows[0].activeSelf != nodeSpec.active || actualNode.activeSelf != nodeSpec.active)
            { diagnostic = "source-activity-path-object-or-state-differs:" + cursorId; return false; }
            pathRows.Add(cursorId); values.Add(nodeSpec.active);
            actualPathNodes.Add(actualNode); previousPathNodes.Add(previousRows[0]);
            if (cursorId == sourceRootId)
            {
                actualRoot = actualNode; oldRoot = previousRows[0];
                break;
            }
            cursorId = nodeSpec.parent;
        }
        for (int i = 0; i + 1 < pathRows.Count; i++)
        {
            if (previousPathNodes[i].transform.parent != previousPathNodes[i + 1].transform ||
                actualPathNodes[i].transform.parent != actualPathNodes[i + 1].transform)
            { diagnostic = "source-activity-path-parent-mismatch:" + pathRows[i]; return false; }
        }
        path = pathRows.ToArray(); activeValues = values.ToArray();
        return true;
    }

    static StaticSpineOwnerContextLifecycleRow StaticSpineLifecycleRow(string phase,
        StaticSpineRenderingComponent expected, Graphic priorOwner, Graphic actualOwner,
        GameObject priorRoot, GameObject actualRoot, SkeletonDataAsset dataAsset,
        string instanceOwnerPrefabId, string instanceRootNodeId, string instanceNodeId,
        string templatePrefabId, string templateNodeId, bool registered, bool verified, string diagnostic)
    {
        var sourceEvidence = staticSpineSourceCanvasContext;
        var componentEvidence = StaticSpineSourceCanvasComponent(expected == null ? null : expected.sourceComponentId,
            expected == null ? null : expected.sourceDataAssetId,
            sourceEvidence == null ? null : sourceEvidence.sourceManifestSha256,
            sourceEvidence == null ? null : sourceEvidence.renderingPlanSha256);
        var sourceContext = StaticSpineSourceCanvasContextRow(componentEvidence);
        var priorGuid = StaticSpineAssetGuid(priorOwner, out var priorLocal);
        var actualGuid = StaticSpineAssetGuid(actualOwner, out var actualLocal);
        var dataGuid = StaticSpineAssetGuid(dataAsset, out var dataLocal);
        var actualCanvas = actualOwner == null ? null : actualOwner.GetComponentInParent<Canvas>(true);
        var actualScaler = actualCanvas == null ? null : actualCanvas.GetComponent<CanvasScaler>();
        return new StaticSpineOwnerContextLifecycleRow
        {
            phase = phase,
            sourceComponentId = expected == null ? null : expected.sourceComponentId,
            sourceDataAssetId = expected == null ? null : expected.sourceDataAssetId,
            sourcePrefabId = expected == null ? null : expected.sourcePrefabId,
            sourceNodeId = expected == null ? null : expected.sourceNodeId,
            templateComponentId = expected == null ? null : expected.templateComponentId,
            instanceOwnerPrefabId = instanceOwnerPrefabId,
            instanceRootNodeId = instanceRootNodeId,
            instanceNodeId = instanceNodeId,
            templatePrefabId = templatePrefabId,
            templateNodeId = templateNodeId,
            priorOwnerType = priorOwner == null ? null : priorOwner.GetType().FullName,
            priorOwnerPath = StaticSpineOwnerRelativePath(priorRoot, priorOwner == null ? null : priorOwner.gameObject),
            priorOwnerAssetPath = priorOwner == null ? null : AssetDatabase.GetAssetPath(priorOwner),
            priorOwnerGuid = priorGuid,
            priorOwnerLocalFileId = priorLocal,
            priorOwnerPersistent = priorOwner != null && EditorUtility.IsPersistent(priorOwner),
            actualOwnerType = actualOwner == null ? null : actualOwner.GetType().FullName,
            actualOwnerPath = StaticSpineOwnerRelativePath(actualRoot, actualOwner == null ? null : actualOwner.gameObject),
            actualOwnerAssetPath = actualOwner == null ? null : AssetDatabase.GetAssetPath(actualOwner),
            actualOwnerGuid = actualGuid,
            actualOwnerLocalFileId = actualLocal,
            actualOwnerPersistent = actualOwner != null && EditorUtility.IsPersistent(actualOwner),
            dataAssetType = dataAsset == null ? null : dataAsset.GetType().FullName,
            dataAssetPath = dataAsset == null ? null : AssetDatabase.GetAssetPath(dataAsset),
            dataAssetGuid = dataGuid,
            dataAssetLocalFileId = dataLocal,
            sourceCanvasEvidenceSha256 = sourceEvidence == null ? null : sourceEvidence.evidenceSha256,
            renderingPlanSha256 = staticSpineRenderingPlanSha,
            sourceManifestSha256 = sourceEvidence == null ? null : sourceEvidence.sourceManifestSha256,
            sourceCanvasRenderMode = sourceContext == null ? null : sourceContext.sourceCanvasRenderMode,
            sourceCanvasPpu = sourceContext == null ? 0f : sourceContext.sourceCanvasReferencePixelsPerUnit,
            sourceScalerPpu = sourceContext == null ? 0f : sourceContext.sourceScalerReferencePixelsPerUnit,
            sourceCanvasScalerPresent = sourceContext != null && sourceContext.sourceCanvasScalerPresent,
            actualCanvasRenderMode = actualCanvas == null ? null : actualCanvas.renderMode.ToString(),
            actualCanvasScaleMode = actualScaler == null ? "none" : actualScaler.uiScaleMode.ToString(),
            actualCanvasPpu = actualCanvas == null ? 0f : actualCanvas.referencePixelsPerUnit,
            actualScalerPpu = actualScaler == null ? 0f : actualScaler.referencePixelsPerUnit,
            actualScalerMatchWidthOrHeight = actualScaler == null ? 0f : actualScaler.matchWidthOrHeight,
            actualScalerReferenceResolution = actualScaler == null ? Array.Empty<float>() :
                new[] { actualScaler.referenceResolution.x, actualScaler.referenceResolution.y },
            actualCanvasScalerPresent = actualScaler != null,
            ownerPairRegistered = registered,
            verified = verified,
            registrationStatus = registered ? verified ? "registered-verified" : "registered-unverified" : "not-registered",
            diagnostic = diagnostic,
        };
    }

    static void RecordStaticSpineOwnerLifecycle(StaticSpineOwnerContextLifecycleRow row)
    {
        if (row == null) throw new ArgumentNullException(nameof(row));
        staticSpineOwnerContextLifecycleRows.Add(row);
    }

    static StaticSpineOwnerContextLifecycleComponent StaticSpineLifecycleComponent(string sourceComponentId)
    {
        return staticSpineOwnerContextLifecycleComponents.SingleOrDefault(row => row != null &&
            row.sourceComponentId == sourceComponentId);
    }

    static void ResetStaticSpineOwnerLifecycleRegistries()
    {
        staticSpineRenderingPlan = null;
        staticSpineRenderingPlanSha = null;
        staticSpineRenderingAssets.Clear();
        staticSpineSourceCanvasContext = null;
        staticSpineSourceCanvasOwners.Clear();
        staticSpineNativeInstanceOwners.Clear();
        staticSpineRetiredNativeInstanceOwners.Clear();
        staticSpineReadbackOwnerScopes.Clear();
        staticSpineControlledCanvasContexts.Clear();
        staticSpineOwnerContextLifecycleRows.Clear();
        staticSpineOwnerContextLifecycleComponents.Clear();
    }

    static void InitializeStaticSpineOwnerLifecycleComponents(StaticSpineRenderingEnvelope rendering)
    {
        staticSpineOwnerContextLifecycleComponents.Clear();
        foreach (var component in rendering == null ? Array.Empty<StaticSpineRenderingComponent>() :
            rendering.components ?? Array.Empty<StaticSpineRenderingComponent>())
            if (component != null)
                staticSpineOwnerContextLifecycleComponents.Add(new StaticSpineOwnerContextLifecycleComponent
                {
                    sourceComponentId = component.sourceComponentId, sourceDataAssetId = component.sourceDataAssetId,
                    sourcePrefabId = component.sourcePrefabId, sourceNodeId = component.sourceNodeId,
                    templateComponentId = component.templateComponentId, eligible = component.eligible,
                    sourceConstructionOwnerRegistered = false,
                    transitions = Array.Empty<StaticSpineOwnerContextLifecycleRow>(),
                });
    }

    static void RegisterStaticSpineSourceConstructionOwner(StaticSpineRenderingComponent expected,
        GameObject node, SkeletonGraphic graphic, SkeletonDataAsset dataAsset)
    {
        if (expected == null || node == null || graphic == null || dataAsset == null ||
            !staticSpineSourceCanvasOwners.TryGetValue(expected.sourceComponentId, out var source) || source == null ||
            source.sourceNode != node || source.sourcePrefabId != expected.sourcePrefabId ||
            source.sourceNodeId != expected.sourceNodeId || source.sourceDataAssetId != expected.sourceDataAssetId ||
            source.evidence == null || source.evidence != staticSpineSourceCanvasContext ||
            !StaticSpineRendererIdentityMatches(graphic, expected) || graphic.SkeletonDataAsset != dataAsset)
            throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_SOURCE_CONSTRUCTION_REGISTRATION_INVALID:" +
                (expected == null ? "null" : expected.sourceComponentId));
        var dataRows = (staticSpineRenderingPlan.dataAssets ?? Array.Empty<StaticSpineRenderingData>())
            .Where(row => row != null && row.eligible && row.sourceDataAssetId == expected.sourceDataAssetId).ToArray();
        if (dataRows.Length != 1 || dataRows[0].factorySpec == null ||
            AssetDatabase.GetAssetPath(dataAsset) != dataRows[0].factorySpec.skeletonDataAssetPath ||
            AssetDatabase.LoadAssetAtPath<SkeletonDataAsset>(dataRows[0].factorySpec.skeletonDataAssetPath) != dataAsset ||
            !EditorUtility.IsPersistent(dataAsset) || String.IsNullOrWhiteSpace(StaticSpineAssetGuid(dataAsset, out var dataLocal)) || dataLocal == 0)
            throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_SOURCE_DATA_ASSET_NOT_EXACT_PERSISTENT:" + expected.sourceComponentId);
        var component = StaticSpineLifecycleComponent(expected.sourceComponentId);
        if (component == null || component.sourceDataAssetId != expected.sourceDataAssetId ||
            component.sourcePrefabId != expected.sourcePrefabId || component.sourceNodeId != expected.sourceNodeId ||
            component.templateComponentId != expected.templateComponentId)
            throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_SOURCE_COMPONENT_ROW_MISSING:" + expected.sourceComponentId);
        var row = StaticSpineLifecycleRow("source-construction", expected, null, graphic, null, node,
            dataAsset, null, null, expected.sourceNodeId, null, null, true, true, null);
        component.sourceConstructionOwnerRegistered = true;
        component.sourceConstructionOwnerType = graphic.GetType().FullName;
        component.sourceConstructionOwnerPath = row.actualOwnerPath;
        component.sourceConstructionDataAssetPath = row.dataAssetPath;
        component.sourceConstructionDataAssetGuid = row.dataAssetGuid;
        component.sourceCanvasEvidenceSha256 = row.sourceCanvasEvidenceSha256;
        component.sourceCanvasRenderMode = row.sourceCanvasRenderMode;
        component.sourceCanvasPpu = row.sourceCanvasPpu;
        component.sourceScalerPpu = row.sourceScalerPpu;
        RecordStaticSpineOwnerLifecycle(row);
        staticSpineNativeInstanceOwners.Add(new StaticSpineNativeInstanceOwnerRegistration
        {
            sourceComponentId = expected.sourceComponentId, sourceDataAssetId = expected.sourceDataAssetId,
            sourcePrefabId = expected.sourcePrefabId, sourceNodeId = expected.sourceNodeId,
            templateComponentId = expected.templateComponentId, owner = graphic, dataAsset = dataAsset,
            prefabRoot = node, instanceRoot = node, sourceEvidence = staticSpineSourceCanvasContext,
            lifecycle = row,
        });
    }

    public static void RecordStaticSpineOwnerContextUse(Graphic owner, string sourceComponentId,
        string sourceDataAssetId, string phase, bool verified, string diagnostic)
    {
        if (staticSpineRenderingPlan == null) return;
        var expectedRows = (staticSpineRenderingPlan.components ?? Array.Empty<StaticSpineRenderingComponent>())
            .Where(row => row != null && row.eligible && row.sourceComponentId == sourceComponentId &&
                row.sourceDataAssetId == sourceDataAssetId).ToArray();
        if (expectedRows.Length != 1)
            throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_USE_SOURCE_ROW_MISSING_OR_AMBIGUOUS:" + sourceComponentId);
        var expected = expectedRows[0];
        var registration = staticSpineNativeInstanceOwners.Where(row => row != null && row.owner == owner &&
            row.sourceComponentId == sourceComponentId && row.sourceDataAssetId == sourceDataAssetId).ToArray();
        var savedPairs = staticSpineReadbackOwnerScopes.SelectMany(scope => scope == null ?
            Enumerable.Empty<StaticSpineReadbackOwnerRegistration>() : scope.rows).Where(row => row != null &&
                row.sourceComponentId == sourceComponentId && row.sourceDataAssetId == sourceDataAssetId &&
                (row.persistentOwner == owner || row.loadedOwner == owner)).ToArray();
        if (registration.Length > 1 || savedPairs.Length > 1)
            throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_USE_OWNER_PAIR_AMBIGUOUS:" + sourceComponentId);
        var dataAsset = owner as SkeletonGraphic == null ? null : ((SkeletonGraphic)owner).SkeletonDataAsset;
        var savedPair = savedPairs.Length == 1 ? savedPairs[0] : null;
        var effectivePhase = savedPair != null && phase == "static-sort-create-capture"
            ? "saved-prefab-owner-pair-capture" : phase;
        var row = savedPair == null
            ? StaticSpineLifecycleRow(effectivePhase, expected, null, owner, null,
                registration.Length == 1 ? registration[0].instanceRoot : owner == null ? null : owner.gameObject,
                dataAsset, expected.sourcePrefabId, null, expected.sourceNodeId, null, null,
                registration.Length == 1, verified && registration.Length == 1, diagnostic)
            : StaticSpineLifecycleRow(effectivePhase, expected, savedPair.persistentOwner, owner,
                savedPair.persistentOwner == null ? null : savedPair.persistentOwner.gameObject,
                owner == null ? null : owner.gameObject,
                savedPair.dataAsset, savedPair.sourcePrefabId, null, savedPair.sourceNodeId, null, null,
                true, verified && savedPair.hostEvidence != null && savedPair.hostEvidence.verified, diagnostic);
        row.diagnostic = String.IsNullOrEmpty(row.diagnostic) ? diagnostic : row.diagnostic + ";" + diagnostic;
        if (savedPair != null)
        {
            row.controlledHostEvidenceSha256 = savedPair.hostEvidence == null ? null : savedPair.hostEvidence.evidenceSha256;
            row.controlledHostContextVerified = savedPair.hostEvidence != null && savedPair.hostEvidence.verified;
            row.controlledHostCanvasRenderMode = savedPair.controlledHost == null ? null :
                savedPair.controlledHost.GetComponent<Canvas>()?.renderMode.ToString();
            var controlledCanvas = savedPair.controlledHost == null ? null : savedPair.controlledHost.GetComponent<Canvas>();
            row.controlledHostCanvasPpu = controlledCanvas == null ? 0f : controlledCanvas.referencePixelsPerUnit;
        }
        if (registration.Length == 1)
        {
            if (phase == "native-instance-clone")
            {
                row.priorOwnerRegistryRevoked = registration[0].lifecycle.priorOwnerRegistryRevoked;
                row.priorOwnerRetired = registration[0].priorOwner == null ||
                    staticSpineRetiredNativeInstanceOwners.Contains(registration[0].priorOwner);
            }
            if (!registration[0].lifecycle.verified || !row.verified)
                row.registrationStatus = "registered-unverified";
        }
        if (savedPair != null && (!row.verified || !row.controlledHostContextVerified))
            row.registrationStatus = "registered-unverified";
        RecordStaticSpineOwnerLifecycle(row);
    }

    static partial void RebindOptionalStaticSpineNativeInstanceContext(Plan plan, PrefabInstanceSpec instance,
        Dictionary<string, GameObject> nodes, Dictionary<UnityEngine.Object, UnityEngine.Object> replacements)
    {
        if (plan == null || String.IsNullOrEmpty(plan.staticSpineRenderingJson)) return;
        if (instance == null || nodes == null || replacements == null || staticSpineRenderingPlan == null ||
            staticSpineSourceCanvasContext == null || plan.sourceManifestSha256 != staticSpineRenderingPlan.sourceManifestSha256 ||
            staticSpineSourceCanvasContext.sourceManifestSha256 != plan.sourceManifestSha256 ||
            staticSpineSourceCanvasContext.renderingPlanSha256 != staticSpineRenderingPlanSha ||
            StaticSpineCanvasEvidenceHash(staticSpineSourceCanvasContext) != staticSpineSourceCanvasContext.evidenceSha256)
            throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_REBIND_INPUT_OR_PIN_INVALID:" +
                (instance == null ? "null-instance" : instance.owner + ":" + instance.root));

        var nodePairs = instance.nodes ?? Array.Empty<PrefabObjectPair>();
        var candidates = (staticSpineRenderingPlan.components ?? Array.Empty<StaticSpineRenderingComponent>())
            .Where(expected => expected != null && expected.eligible && expected.sourcePrefabId == instance.owner &&
                !String.IsNullOrWhiteSpace(expected.templateComponentId) &&
                expected.templateComponentId.StartsWith(instance.template + "#", StringComparison.Ordinal))
            .Select(expected => new { expected, pairs = nodePairs.Where(pair => pair != null &&
                pair.instanceObject == expected.sourceNodeId).ToArray() })
            .Where(item => item.pairs.Length > 0).ToArray();
        if (candidates.Length == 0) return;

        var pending = new List<StaticSpineNativeInstanceOwnerRegistration>();
        var rootTarget = nodes.TryGetValue(instance.root, out var mappedRoot) ? mappedRoot : null;
        var rootPairs = rootTarget == null ? Array.Empty<KeyValuePair<UnityEngine.Object, UnityEngine.Object>>() :
            replacements.Where(pair => pair.Key is GameObject && pair.Value == rootTarget).ToArray();
        if (rootTarget == null || rootPairs.Length != 1)
            throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_INSTANCE_ROOT_REPLACEMENT_MISSING:" +
                instance.owner + ":" + instance.root);
        var rootSource = rootPairs[0].Key as GameObject;

        foreach (var item in candidates)
        {
            var expected = item.expected;
            if (item.pairs.Length != 1)
                throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_INSTANCE_NODE_MAPPING_AMBIGUOUS:" + expected.sourceComponentId);
            var pair = item.pairs[0];
            var templateComponentRows = (plan.components ?? Array.Empty<ComponentSpec>())
                .Where(component => component != null && component.sourceId == expected.templateComponentId &&
                    component.type == "sp.Skeleton").ToArray();
            if (templateComponentRows.Length != 1 || templateComponentRows[0].node != pair.templateObject)
            {
                var failure = StaticSpineLifecycleRow("native-instance-clone", expected, null, null,
                    null, null, null, instance.owner, instance.root, pair.instanceObject,
                    instance.template, pair.templateObject, false, false,
                    "template-component-node-join-count=" + templateComponentRows.Length);
                RecordStaticSpineOwnerLifecycle(failure);
                throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_TEMPLATE_COMPONENT_NODE_JOIN_INVALID:" +
                    expected.sourceComponentId + ";templateComponent=" + expected.templateComponentId +
                    ";mappedNode=" + pair.templateObject + ";componentRows=" + templateComponentRows.Length);
            }
            var newNode = nodes.TryGetValue(expected.sourceNodeId, out var mappedNode) ? mappedNode : null;
            var activityPathOK = StaticSpineInstanceActivityPathMatches(plan, expected.sourceNodeId, instance.root,
                nodes, replacements, out var activityPath, out var activityValues,
                out var activityPathOldRoot, out var activityPathActualRoot, out var activityPathDiagnostic);
            var oldNodePairs = replacements.Where(mapping => mapping.Key is GameObject && mapping.Value == newNode)
                .Select(mapping => mapping.Key as GameObject).Where(node => node != null).ToArray();
            GameObject oldNode = oldNodePairs.Length == 1 ? oldNodePairs[0] : null;
            if (newNode == null || oldNodePairs.Length != 1 || oldNode == null ||
                !oldNode.transform.IsChildOf(rootSource.transform) ||
                !newNode.transform.IsChildOf(rootTarget.transform) || !activityPathOK ||
                activityPathOldRoot != rootSource || activityPathActualRoot != rootTarget)
            {
                var failure = StaticSpineLifecycleRow("native-instance-clone", expected, null, null,
                    rootSource, rootTarget, null, instance.owner, instance.root, pair.instanceObject,
                    instance.template, pair.templateObject, false, false, activityPathDiagnostic ??
                        "instance-node-ancestry-or-replacement-mismatch");
                failure.sourceActivityPath = activityPath;
                failure.sourceActivityValues = activityValues;
                failure.sourceActivityPathVerified = activityPathOK;
                RecordStaticSpineOwnerLifecycle(failure);
                throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_INSTANCE_NODE_ANCESTRY_MISMATCH:" +
                    expected.sourceComponentId + ";templateNode=" + pair.templateObject + ";root=" + instance.root +
                    ";activity=" + (activityPathDiagnostic ?? "invalid"));
            }
            var oldOwners = replacements.Where(mapping => mapping.Key is SkeletonGraphic && mapping.Value is SkeletonGraphic)
                .Select(mapping => new { oldOwner = (SkeletonGraphic)mapping.Key, newOwner = (SkeletonGraphic)mapping.Value })
                .Where(mapping => mapping.oldOwner.gameObject == oldNode && StaticSpineRendererIdentityMatches(mapping.oldOwner, expected))
                .ToArray();
            if (oldOwners.Length != 1)
                throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_INSTANCE_OWNER_REPLACEMENT_AMBIGUOUS:" +
                    expected.sourceComponentId + ";oldCount=" + oldOwners.Length);
            var oldOwner = oldOwners[0].oldOwner;
            var newOwner = oldOwners[0].newOwner;
            var parents = staticSpineNativeInstanceOwners.Where(row => row != null && row.owner == oldOwner &&
                row.sourceComponentId == expected.sourceComponentId && row.sourceDataAssetId == expected.sourceDataAssetId &&
                row.sourceEvidence == staticSpineSourceCanvasContext && row.lifecycle != null && row.lifecycle.verified).ToArray();
            if (parents.Length != 1)
            {
                var failure = StaticSpineLifecycleRow("native-instance-clone", expected, oldOwner, newOwner,
                    rootSource, rootTarget, newOwner == null ? null : newOwner.SkeletonDataAsset,
                    instance.owner, instance.root, pair.instanceObject, instance.template, pair.templateObject,
                    false, false, "prior-owner-registration-count=" + parents.Length);
                RecordStaticSpineOwnerLifecycle(failure);
                throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_PRIOR_OWNER_NOT_EXACTLY_REGISTERED:" +
                    expected.sourceComponentId + ";count=" + parents.Length);
            }
            var parent = parents[0];
            var componentEvidence = StaticSpineSourceCanvasComponent(expected.sourceComponentId, expected.sourceDataAssetId,
                plan.sourceManifestSha256, staticSpineRenderingPlanSha);
            var source = staticSpineSourceCanvasOwners.TryGetValue(expected.sourceComponentId, out var sourceOwner) ? sourceOwner : null;
            var nodePlan = (plan.nodes ?? Array.Empty<NodeSpec>()).Where(row => row != null &&
                row.sourceId == expected.sourceNodeId).ToArray();
            var dataRows = (staticSpineRenderingPlan.dataAssets ?? Array.Empty<StaticSpineRenderingData>())
                .Where(row => row != null && row.eligible && row.sourceDataAssetId == expected.sourceDataAssetId).ToArray();
            var spec = dataRows.Length == 1 ? dataRows[0].factorySpec : null;
            var expectedAsset = spec == null ? null : AssetDatabase.LoadAssetAtPath<SkeletonDataAsset>(spec.skeletonDataAssetPath);
            var actualAsset = newOwner == null ? null : newOwner.SkeletonDataAsset;
            var oldAsset = oldOwner == null ? null : oldOwner.SkeletonDataAsset;
            var assetGuid = StaticSpineAssetGuid(actualAsset, out var assetLocalId);
            bool oldCanvasOK = StaticSpineCloneCanvasMatchesSource(oldOwner, componentEvidence, out var oldCanvas, out var oldCanvasDiagnostic);
            bool newCanvasOK = StaticSpineCloneCanvasMatchesSource(newOwner, componentEvidence, out var newCanvas, out var newCanvasDiagnostic);
            var targetDataOK = dataRows.Length == 1 && spec != null && expectedAsset != null &&
                EditorUtility.IsPersistent(expectedAsset) && actualAsset == expectedAsset && oldAsset == expectedAsset &&
                parent.dataAsset == expectedAsset && AssetDatabase.GetAssetPath(actualAsset) == spec.skeletonDataAssetPath &&
                !String.IsNullOrWhiteSpace(assetGuid) && assetLocalId != 0;
            var sourceNodeActivity = activityPathOK && nodePlan.Length == 1 && oldNode.activeSelf == nodePlan[0].active &&
                newNode.activeSelf == nodePlan[0].active && oldOwner.enabled == expected.sourceComponentEnabled &&
                newOwner.enabled == expected.sourceComponentEnabled;
            var exactInstanceRelation = instance.owner == expected.sourcePrefabId &&
                instance.template == expected.templateComponentId.Split('#')[0] &&
                templateComponentRows[0].sourceId == expected.templateComponentId &&
                templateComponentRows[0].node == pair.templateObject &&
                parent.sourcePrefabId == expected.sourcePrefabId && parent.sourceNodeId == expected.sourceNodeId &&
                parent.templateComponentId == expected.templateComponentId &&
                oldNode.transform.IsChildOf(rootSource.transform) && newNode.transform.IsChildOf(rootTarget.transform) &&
                StaticSpineRendererIdentityMatches(oldOwner, expected) && StaticSpineRendererIdentityMatches(newOwner, expected);
            var diagnostic = !exactInstanceRelation ? "source-template-instance-identity-mismatch" :
                !targetDataOK ? "persistent-source-data-asset-reference-mismatch" :
                !sourceNodeActivity ? "source-node-or-component-activity-mismatch" :
                !oldCanvasOK ? "prior-owner-canvas:" + oldCanvasDiagnostic :
                !newCanvasOK ? "clone-owner-canvas:" + newCanvasDiagnostic : null;
            bool verified = exactInstanceRelation && targetDataOK && sourceNodeActivity && oldCanvasOK && newCanvasOK &&
                source != null && source.sourceNode == oldNode && source.sourceDataAssetId == expected.sourceDataAssetId &&
                parent.owner == oldOwner && staticSpineSourceCanvasContext.sourceNodeGeometryVerified &&
                staticSpineSourceCanvasContext.sourceCanvasContextVerified;
            var lifecycle = StaticSpineLifecycleRow("native-instance-clone", expected, oldOwner, newOwner,
                rootSource, rootTarget, actualAsset, instance.owner, instance.root, pair.instanceObject,
                instance.template, pair.templateObject, verified, verified, diagnostic);
            lifecycle.sourceActivityPath = activityPath;
            lifecycle.sourceActivityValues = activityValues;
            lifecycle.sourceActivityPathVerified = activityPathOK;
            lifecycle.priorOwnerRegistryRevoked = verified;
            if (!verified)
            {
                lifecycle.registrationStatus = "registered-unverified";
                RecordStaticSpineOwnerLifecycle(lifecycle);
                throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_NATIVE_INSTANCE_CLONE_UNVERIFIED:" +
                    expected.sourceComponentId + ";phase=native-instance-clone;old=" + lifecycle.priorOwnerPath +
                    ";new=" + lifecycle.actualOwnerPath + ";data=" + lifecycle.dataAssetGuid + ";canvas=" + diagnostic);
            }
            pending.Add(new StaticSpineNativeInstanceOwnerRegistration
            {
                sourceComponentId = expected.sourceComponentId, sourceDataAssetId = expected.sourceDataAssetId,
                sourcePrefabId = expected.sourcePrefabId, sourceNodeId = expected.sourceNodeId,
                templateComponentId = expected.templateComponentId, priorOwner = oldOwner, owner = newOwner,
                dataAsset = expectedAsset, prefabRoot = rootSource, instanceRoot = rootTarget,
                sourceEvidence = staticSpineSourceCanvasContext, lifecycle = lifecycle,
            });
        }

        // Commit only after every mapped owner in this native replacement passed.
        var priorRegistrations = pending.Select(transfer => staticSpineNativeInstanceOwners.Where(row => row != null &&
            row.owner == transfer.priorOwner && row.sourceComponentId == transfer.sourceComponentId &&
            row.sourceDataAssetId == transfer.sourceDataAssetId).ToArray()).ToArray();
        if (priorRegistrations.Any(rows => rows.Length != 1) || priorRegistrations.Select(rows => rows[0])
            .Distinct().Count() != priorRegistrations.Length)
        {
            foreach (var transfer in pending)
            {
                transfer.lifecycle.verified = false;
                transfer.lifecycle.ownerPairRegistered = false;
                transfer.lifecycle.priorOwnerRegistryRevoked = false;
                transfer.lifecycle.registrationStatus = "not-registered";
                transfer.lifecycle.diagnostic = "native-instance-rebind-prior-registration-changed-before-commit";
                RecordStaticSpineOwnerLifecycle(transfer.lifecycle);
            }
            throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_REBIND_TRANSACTION_PRIOR_REGISTRATION_CHANGED:" +
                instance.owner + ":" + instance.root);
        }
        for (int i = 0; i < pending.Count; i++)
        {
            var transfer = pending[i];
            var previous = priorRegistrations[i][0];
            staticSpineNativeInstanceOwners.Remove(previous);
            staticSpineRetiredNativeInstanceOwners.Add(transfer.priorOwner);
            transfer.lifecycle.priorOwnerRegistryRevoked = true;
            staticSpineNativeInstanceOwners.Add(transfer);
            RecordStaticSpineOwnerLifecycle(transfer.lifecycle);
        }
    }

    public static bool TryGetStaticSpineSourceCanvasProof(Graphic graphic, string sourceComponentId, string sourceDataAssetId,
        string sourceManifestSha256, string renderingPlanSha256, out float sourcePpu,
        out string evidenceSha256, out string contextKind, out string diagnostic)
    {
        sourcePpu = 0f; evidenceSha256 = null; contextKind = null; diagnostic = null;
        var componentEvidence = StaticSpineSourceCanvasComponent(sourceComponentId, sourceDataAssetId,
            sourceManifestSha256, renderingPlanSha256);
        var renderingRows = (staticSpineRenderingPlan == null ? Array.Empty<StaticSpineRenderingComponent>() :
            staticSpineRenderingPlan.components ?? Array.Empty<StaticSpineRenderingComponent>())
            .Where(row => row != null && row.sourceComponentId == sourceComponentId &&
                row.sourceDataAssetId == sourceDataAssetId).ToArray();
        if (componentEvidence == null || renderingRows.Length != 1 || !StaticSpineRendererIdentityMatches(graphic, renderingRows[0]))
        { diagnostic = "source-canvas-context-or-renderer-identity-unverified"; return false; }
        var expected = renderingRows[0];
        var canvas = graphic.GetComponentInParent<Canvas>(true);
        if (staticSpineSourceCanvasOwners.TryGetValue(sourceComponentId, out var sourceRegistration) &&
            sourceRegistration != null && sourceRegistration.sourceNode == graphic.gameObject && sourceRegistration.canvas == canvas &&
            !staticSpineRetiredNativeInstanceOwners.Contains(graphic))
        {
            var scaler = canvas.GetComponent<CanvasScaler>();
            if (scaler == null || canvas.renderMode != RenderMode.ScreenSpaceOverlay ||
                !SpineUnitClose(canvas.referencePixelsPerUnit, staticSpineSourceCanvasContext.sourceReferencePixelsPerUnit) ||
                !SpineUnitClose(scaler.referencePixelsPerUnit, staticSpineSourceCanvasContext.sourceReferencePixelsPerUnit) ||
                !System.Object.ReferenceEquals(graphic.gameObject, sourceRegistration.sourceNode) ||
                !String.IsNullOrEmpty(expected.sourceNodeId) && expected.sourceNodeId != componentEvidence.sourceNodeId)
            { diagnostic = "source-canvas-context-unverified"; return false; }
            sourcePpu = staticSpineSourceCanvasContext.sourceReferencePixelsPerUnit;
            evidenceSha256 = staticSpineSourceCanvasContext.evidenceSha256;
            contextKind = "source-construction-canvas";
            return true;
        }

        var nativeInstanceOwners = staticSpineNativeInstanceOwners.Where(row => row != null &&
            row.sourceComponentId == sourceComponentId && row.sourceDataAssetId == sourceDataAssetId && row.owner == graphic).ToArray();
        if (nativeInstanceOwners.Length != 0)
        {
            if (nativeInstanceOwners.Length != 1)
            { diagnostic = "native-instance-owner-registration-ambiguous:phase=native-instance-clone;count=" + nativeInstanceOwners.Length; return false; }
            var lifecycleOwner = nativeInstanceOwners[0];
            var canvasMatches = StaticSpineCloneCanvasMatchesSource(graphic, componentEvidence, out var lifecycleCanvas,
                out var canvasDiagnostic);
            var exactDataAsset = lifecycleOwner.dataAsset;
            long localId;
            var dataGuid = StaticSpineAssetGuid(exactDataAsset, out localId);
            var actualGraphic = graphic as SkeletonGraphic;
            if (lifecycleOwner.lifecycle == null || !lifecycleOwner.lifecycle.verified ||
                lifecycleOwner.sourceEvidence != staticSpineSourceCanvasContext ||
                lifecycleOwner.lifecycle.sourceCanvasEvidenceSha256 != staticSpineSourceCanvasContext.evidenceSha256 ||
                lifecycleOwner.lifecycle.renderingPlanSha256 != renderingPlanSha256 ||
                lifecycleOwner.lifecycle.sourceManifestSha256 != sourceManifestSha256 ||
                lifecycleOwner.lifecycle.sourceComponentId != sourceComponentId ||
                lifecycleOwner.lifecycle.sourceDataAssetId != sourceDataAssetId ||
                !StaticSpineRendererIdentityMatches(graphic, expected) || exactDataAsset == null || actualGraphic == null ||
                actualGraphic.SkeletonDataAsset != exactDataAsset || !EditorUtility.IsPersistent(exactDataAsset) ||
                String.IsNullOrWhiteSpace(dataGuid) || localId == 0 || !canvasMatches || lifecycleCanvas == null ||
                lifecycleOwner.instanceRoot == null || !graphic.transform.IsChildOf(lifecycleOwner.instanceRoot.transform))
            {
                diagnostic = "native-instance-owner-lifecycle-unverified:phase=native-instance-clone;source=" + sourceComponentId +
                    ";prior=" + (lifecycleOwner.lifecycle == null ? "<none>" : lifecycleOwner.lifecycle.priorOwnerPath ?? "<none>") +
                    ";actual=" + (lifecycleOwner.lifecycle == null ? "<none>" : lifecycleOwner.lifecycle.actualOwnerPath ?? "<none>") +
                    ";dataGuid=" + (dataGuid ?? "<missing>") + ";canvas=" + (canvasDiagnostic ?? "unverified");
                return false;
            }
            sourcePpu = staticSpineSourceCanvasContext.sourceReferencePixelsPerUnit;
            evidenceSha256 = staticSpineSourceCanvasContext.evidenceSha256;
            contextKind = "native-instance-clone-lifecycle";
            return true;
        }

        var ownerScopes = staticSpineReadbackOwnerScopes.SelectMany(scope => scope.rows).Where(row => row != null &&
            row.sourceComponentId == sourceComponentId && row.sourceDataAssetId == sourceDataAssetId &&
            (row.loadedOwner == graphic || row.persistentOwner == graphic)).ToArray();
        if (ownerScopes.Length != 1)
        { diagnostic = "controlled-prefab-owner-pair-not-registered"; return false; }
        var ownerScope = ownerScopes[0];
        var controlled = staticSpineControlledCanvasContexts.SingleOrDefault(row => row != null && row.host == ownerScope.controlledHost);
        var actualOwner = graphic as SkeletonGraphic;
        var loadedCanvas = ownerScope.loadedOwner == null ? null : ownerScope.loadedOwner.GetComponentInParent<Canvas>(true);
        if (controlled == null || actualOwner == null || actualOwner.enabled != expected.sourceComponentEnabled ||
            actualOwner.gameObject.activeSelf != ownerScope.sourceNodeActive || loadedCanvas == null ||
            loadedCanvas != controlled.canvas || loadedCanvas.gameObject != controlled.host ||
            (canvas != null && canvas != controlled.canvas))
        { diagnostic = "controlled-prefab-owner-or-host-identity-mismatch"; return false; }
        if (ownerScopes.Length != 1 || controlled.evidence == null || controlled.evidence.sourceManifestSha256 != sourceManifestSha256 ||
            controlled.evidence.evidenceSha256 != StaticSpineControlledHostEvidenceHash(controlled.evidence) ||
            controlled.evidence.renderingPlanSha256 != renderingPlanSha256 ||
            controlled.evidence.sourceCanvasEvidenceSha256 != staticSpineSourceCanvasContext.evidenceSha256 ||
            controlled.canvas == null || !SpineUnitClose(controlled.canvas.referencePixelsPerUnit, controlled.evidence.sourceCanvasReferencePixelsPerUnit) ||
            !StaticSpineCanvasContextEvidenceMatches(staticSpineSourceCanvasContext, sourceComponentId, sourceDataAssetId,
                sourceManifestSha256, renderingPlanSha256, controlled.canvas.referencePixelsPerUnit,
                controlled.canvas.renderMode.ToString(), controlled.canvas.GetComponent<CanvasScaler>() == null))
        { diagnostic = "cocos-static-spine-canvas-unit-context-unverified"; return false; }
        var actualData = actualOwner.SkeletonDataAsset;
        if (actualData == null || actualData != ownerScope.dataAsset || actualData != AssetDatabase.LoadAssetAtPath<SkeletonDataAsset>(
            (staticSpineRenderingPlan.dataAssets ?? Array.Empty<StaticSpineRenderingData>())
                .Single(row => row != null && row.sourceDataAssetId == sourceDataAssetId).factorySpec.skeletonDataAssetPath))
        { diagnostic = "source-owner-skeleton-data-reference-differs-from-pinned-asset"; return false; }
        sourcePpu = staticSpineSourceCanvasContext.sourceReferencePixelsPerUnit;
        evidenceSha256 = staticSpineSourceCanvasContext.evidenceSha256;
        contextKind = ownerScope.persistentOwner == graphic ? "saved-persistent-owner-with-controlled-reopen-peer" : "controlled-prefab-reopened-owner";
        return true;
    }

    public static void RegisterStaticSpineControlledCanvasContext(GameObject context, Plan plan)
    {
        if (plan == null || String.IsNullOrEmpty(plan.staticSpineRenderingJson)) return;
        if (context == null || staticSpineRenderingPlan == null || staticSpineSourceCanvasContext == null ||
            plan.sourceManifestSha256 != staticSpineRenderingPlan.sourceManifestSha256)
            throw new InvalidOperationException("SPINE_CONTROLLED_HOST_SOURCE_CONTEXT_UNAVAILABLE");
        var canvas = context.GetComponent<Canvas>();
        var evidence = MakeStaticSpineControlledHostEvidence(context, plan, canvas);
        staticSpineControlledCanvasContexts.RemoveAll(row => row == null || row.host == null || row.canvas == null || row.host == context);
        staticSpineControlledCanvasContexts.Add(new StaticSpineControlledCanvasRegistration { host = context, canvas = canvas, evidence = evidence });
    }

    public static void UnregisterStaticSpineControlledCanvasContext(GameObject context)
    {
        if (context == null) return;
        staticSpineControlledCanvasContexts.RemoveAll(row => row == null || row.host == null || row.host == context);
    }

    public static void RegisterStaticSpineReadbackOwnerContext(Plan plan, string prefabId,
        Dictionary<string, GameObject> persistentNodes, Dictionary<string, GameObject> loadedNodes, GameObject controlledHost)
    {
        if (plan == null || String.IsNullOrEmpty(plan.staticSpineRenderingJson)) return;
        var host = controlledHost == null ? null : staticSpineControlledCanvasContexts.SingleOrDefault(row => row != null && row.host == controlledHost);
        if (host == null || !host.evidence.verified || staticSpineRenderingPlan == null ||
            staticSpineSourceCanvasContext == null || plan.sourceManifestSha256 != staticSpineRenderingPlan.sourceManifestSha256 ||
            persistentNodes == null || loadedNodes == null)
            throw new InvalidOperationException("SPINE_READBACK_OWNER_CONTEXT_INPUT_INVALID");
        var owningPrefabs = (plan.sourcePrefabs ?? Array.Empty<SourcePrefabSpec>())
            .Where(row => row != null && row.sourceId == prefabId).ToArray();
        if (owningPrefabs.Length != 1 || String.IsNullOrWhiteSpace(owningPrefabs[0].root) ||
            String.IsNullOrWhiteSpace(owningPrefabs[0].path) ||
            !persistentNodes.TryGetValue(owningPrefabs[0].root, out var persistentRoot) || persistentRoot == null ||
            !loadedNodes.TryGetValue(owningPrefabs[0].root, out var loadedRoot) || loadedRoot == null)
            throw new InvalidOperationException("SPINE_READBACK_OWNER_PREFAB_ROOT_PAIR_INVALID:" + prefabId);
        var expectedPrefabPath = owningPrefabs[0].path.Replace('\\', '/');
        if (!EditorUtility.IsPersistent(persistentRoot) ||
            AssetDatabase.GetAssetPath(persistentRoot).Replace('\\', '/') != expectedPrefabPath ||
            AssetDatabase.LoadAssetAtPath<GameObject>(expectedPrefabPath) != persistentRoot)
            throw new InvalidOperationException("SPINE_READBACK_OWNER_PERSISTENT_ROOT_PATH_OR_IDENTITY_MISMATCH:" + prefabId +
                ";expected=" + expectedPrefabPath + ";actual=" + AssetDatabase.GetAssetPath(persistentRoot));
        var nodePlan = (plan.nodes ?? Array.Empty<NodeSpec>()).Where(row => row != null).ToDictionary(row => row.sourceId, StringComparer.Ordinal);
        var sourceRows = (staticSpineRenderingPlan.components ?? Array.Empty<StaticSpineRenderingComponent>())
            .Where(row => row != null && row.eligible && (row.sourcePrefabId == prefabId ||
                row.sourceComponentId.StartsWith(prefabId + "#", StringComparison.Ordinal))).ToArray();
        var scope = new StaticSpineReadbackOwnerScope();
        foreach (var expected in sourceRows)
        {
            if (!persistentNodes.TryGetValue(expected.sourceNodeId, out var persistentNode) || persistentNode == null ||
                !loadedNodes.TryGetValue(expected.sourceNodeId, out var loadedNode) || loadedNode == null ||
                !nodePlan.TryGetValue(expected.sourceNodeId, out var nodeExpected) ||
                persistentNode.activeSelf != nodeExpected.active || loadedNode.activeSelf != nodeExpected.active)
                throw new InvalidOperationException("SPINE_READBACK_OWNER_NODE_OR_ACTIVITY_MISMATCH:" + expected.sourceComponentId);
            var persistentComponents = persistentNode.GetComponents<SkeletonGraphic>();
            var loadedComponents = loadedNode.GetComponents<SkeletonGraphic>();
            if (persistentComponents.Length != 1 || loadedComponents.Length != 1)
                throw new InvalidOperationException("SPINE_READBACK_OWNER_COMPONENT_COUNT_MISMATCH:" + expected.sourceComponentId);
            var persistentComponentPath = AssetDatabase.GetAssetPath(persistentComponents[0]).Replace('\\', '/');
            if (!EditorUtility.IsPersistent(persistentComponents[0]) || persistentComponentPath != expectedPrefabPath)
                throw new InvalidOperationException("SPINE_READBACK_OWNER_PERSISTENT_COMPONENT_PATH_OR_IDENTITY_MISMATCH:" +
                    expected.sourceComponentId + ";expected=" + expectedPrefabPath + ";actual=" + persistentComponentPath);
            if (
                !StaticSpineRendererIdentityMatches(persistentComponents[0], expected) ||
                !StaticSpineRendererIdentityMatches(loadedComponents[0], expected) ||
                persistentComponents[0].enabled != expected.sourceComponentEnabled ||
                loadedComponents[0].enabled != expected.sourceComponentEnabled)
                throw new InvalidOperationException("SPINE_READBACK_OWNER_COMPONENT_IDENTITY_OR_ENABLED_MISMATCH:" + expected.sourceComponentId);
            var dataRows = (staticSpineRenderingPlan.dataAssets ?? Array.Empty<StaticSpineRenderingData>())
                .Where(row => row != null && row.sourceDataAssetId == expected.sourceDataAssetId && row.eligible).ToArray();
            if (dataRows.Length != 1 || dataRows[0].factorySpec == null)
                throw new InvalidOperationException("SPINE_READBACK_OWNER_DATA_SPEC_MISSING:" + expected.sourceDataAssetId);
            var dataAsset = AssetDatabase.LoadAssetAtPath<SkeletonDataAsset>(dataRows[0].factorySpec.skeletonDataAssetPath);
            if (dataAsset == null || !EditorUtility.IsPersistent(dataAsset) ||
                persistentComponents[0].SkeletonDataAsset != dataAsset || loadedComponents[0].SkeletonDataAsset != dataAsset)
                throw new InvalidOperationException("SPINE_READBACK_OWNER_DATA_REFERENCE_MISMATCH:" + expected.sourceComponentId);
            var loadedCanvas = loadedComponents[0].GetComponentInParent<Canvas>(true);
            if (loadedCanvas == null || loadedCanvas != host.canvas || loadedCanvas.gameObject != controlledHost)
                throw new InvalidOperationException("SPINE_READBACK_OWNER_NOT_UNDER_REGISTERED_CONTROLLED_CANVAS:" + expected.sourceComponentId);
            scope.rows.Add(new StaticSpineReadbackOwnerRegistration
            {
                sourceComponentId = expected.sourceComponentId, sourceDataAssetId = expected.sourceDataAssetId,
                sourcePrefabId = expected.sourcePrefabId, sourceNodeId = expected.sourceNodeId,
                persistentOwner = persistentComponents[0], loadedOwner = loadedComponents[0], dataAsset = dataAsset,
                sourceNodeActive = nodeExpected.active,
                controlledHost = controlledHost, sourceEvidence = staticSpineSourceCanvasContext,
                hostEvidence = host.evidence,
            });
            var lifecycle = StaticSpineLifecycleRow("saved-prefab-owner-pair", expected, persistentComponents[0],
                loadedComponents[0], persistentRoot, loadedRoot, dataAsset, prefabId, owningPrefabs[0].root,
                expected.sourceNodeId, null, null, true, true, null);
            lifecycle.controlledHostEvidenceSha256 = host.evidence.evidenceSha256;
            lifecycle.controlledHostCanvasRenderMode = host.canvas.renderMode.ToString();
            lifecycle.controlledHostCanvasPpu = host.canvas.referencePixelsPerUnit;
            lifecycle.controlledHostContextVerified = host.evidence.verified &&
                host.evidence.sourceCanvasEvidenceSha256 == staticSpineSourceCanvasContext.evidenceSha256 &&
                host.evidence.sourceManifestSha256 == plan.sourceManifestSha256 &&
                host.evidence.renderingPlanSha256 == staticSpineRenderingPlanSha;
            if (!lifecycle.controlledHostContextVerified)
                throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_SAVED_PAIR_HOST_EVIDENCE_INVALID:" + expected.sourceComponentId);
            RecordStaticSpineOwnerLifecycle(lifecycle);
        }
        staticSpineReadbackOwnerScopes.Add(scope);
    }

    public static void UnregisterStaticSpineReadbackOwnerContext(GameObject controlledHost)
    {
        if (controlledHost == null) return;
        var releasedScopes = staticSpineReadbackOwnerScopes.Where(scope => scope != null &&
            scope.rows.Any(row => row != null && row.controlledHost == controlledHost)).ToArray();
        var host = staticSpineControlledCanvasContexts.SingleOrDefault(row => row != null && row.host == controlledHost);
        foreach (var scope in releasedScopes)
        foreach (var owner in scope.rows.Where(row => row != null && row.controlledHost == controlledHost))
        {
            var expectedRows = (staticSpineRenderingPlan == null ? Array.Empty<StaticSpineRenderingComponent>() :
                staticSpineRenderingPlan.components ?? Array.Empty<StaticSpineRenderingComponent>())
                .Where(row => row != null && row.sourceComponentId == owner.sourceComponentId &&
                    row.sourceDataAssetId == owner.sourceDataAssetId).ToArray();
            var expected = expectedRows.Length == 1 ? expectedRows[0] : null;
            var release = StaticSpineLifecycleRow("controlled-host-release", expected, owner.persistentOwner,
                owner.loadedOwner, owner.persistentOwner == null ? null : owner.persistentOwner.gameObject,
                owner.loadedOwner == null ? null : owner.loadedOwner.gameObject, owner.dataAsset,
                owner.sourcePrefabId, null, owner.sourceNodeId, null, null, false,
                expected != null && owner.sourceEvidence == staticSpineSourceCanvasContext &&
                    owner.hostEvidence != null && owner.hostEvidence.verified && host != null && host.evidence == owner.hostEvidence,
                expected == null ? "release-source-component-row-missing" : null);
            release.ownerPairRegistered = false;
            release.priorOwnerRegistryRevoked = true;
            release.registrationStatus = release.verified ? "released" : "released-unverified";
            release.controlledHostContextVerified = release.verified;
            release.controlledHostEvidenceSha256 = owner.hostEvidence == null ? null : owner.hostEvidence.evidenceSha256;
            release.controlledHostCanvasRenderMode = host == null || host.canvas == null ? null : host.canvas.renderMode.ToString();
            release.controlledHostCanvasPpu = host == null || host.canvas == null ? 0f : host.canvas.referencePixelsPerUnit;
            RecordStaticSpineOwnerLifecycle(release);
        }
        staticSpineReadbackOwnerScopes.RemoveAll(scope => scope == null || scope.rows.Any(row => row == null || row.controlledHost == controlledHost));
    }

    public static string WriteStaticSpineOwnerContextLifecycleEvidence()
    {
        if (staticSpineRenderingPlan == null || staticSpineSourceCanvasContext == null) return null;
        if (staticSpineSourceCanvasContext.evidenceSha256 != StaticSpineCanvasEvidenceHash(staticSpineSourceCanvasContext) ||
            staticSpineSourceCanvasContext.sourceManifestSha256 != staticSpineRenderingPlan.sourceManifestSha256 ||
            staticSpineSourceCanvasContext.renderingPlanSha256 != staticSpineRenderingPlanSha)
            throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_SOURCE_CANVAS_EVIDENCE_PIN_MISMATCH");
        foreach (var owner in staticSpineNativeInstanceOwners.Where(row => row != null && row.lifecycle != null &&
            row.lifecycle.phase == "native-instance-clone"))
        {
            owner.lifecycle.priorOwnerRetired = owner.priorOwner == null;
            owner.lifecycle.priorOwnerRegistryRevoked = !staticSpineNativeInstanceOwners.Any(row => row != null &&
                row.owner == owner.priorOwner && row.sourceComponentId == owner.sourceComponentId);
            if (!owner.lifecycle.priorOwnerRetired || !owner.lifecycle.priorOwnerRegistryRevoked)
            {
                owner.lifecycle.verified = false;
                owner.lifecycle.registrationStatus = "registered-unverified";
                owner.lifecycle.diagnostic = "prior-owner-not-retired-or-registration-not-revoked";
            }
        }
        var known = new HashSet<string>(staticSpineOwnerContextLifecycleComponents.Select(row => row.sourceComponentId), StringComparer.Ordinal);
        if (known.Count != staticSpineOwnerContextLifecycleComponents.Count ||
            staticSpineOwnerContextLifecycleRows.Any(row => row == null || !known.Contains(row.sourceComponentId)))
            throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_TRACE_SOURCE_DENOMINATOR_INVALID");
        foreach (var component in staticSpineOwnerContextLifecycleComponents)
            component.transitions = staticSpineOwnerContextLifecycleRows.Where(row => row.sourceComponentId == component.sourceComponentId).ToArray();
        var envelope = new StaticSpineOwnerContextLifecycleEnvelope
        {
            sourceManifestSha256 = staticSpineRenderingPlan.sourceManifestSha256,
            renderingPlanSha256 = staticSpineRenderingPlanSha,
            sourceCanvasEvidenceSha256 = staticSpineSourceCanvasContext.evidenceSha256,
            components = staticSpineOwnerContextLifecycleComponents.OrderBy(row => row.sourceComponentId, StringComparer.Ordinal).ToArray(),
            transitions = staticSpineOwnerContextLifecycleRows.ToArray(),
        };
        envelope.evidenceSha256 = null;
        envelope.evidenceSha256 = StaticSpineCanvasHashBytes(Encoding.UTF8.GetBytes(JsonUtility.ToJson(envelope)));
        var bytes = Encoding.UTF8.GetBytes(JsonUtility.ToJson(envelope, true));
        var projectRoot = Directory.GetParent(Application.dataPath)?.FullName;
        if (String.IsNullOrWhiteSpace(projectRoot)) throw new InvalidOperationException("SPINE_OWNER_LIFECYCLE_PROJECT_ROOT_UNAVAILABLE");
        var path = Path.Combine(projectRoot, StaticSpineOwnerContextLifecyclePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllBytes(path, bytes);
        return path;
    }

    static partial void WriteOptionalStaticSpineOwnerContextLifecycleEvidence()
    { WriteStaticSpineOwnerContextLifecycleEvidence(); }

    static partial void BindOptionalStaticSpineControlledCanvasContext(GameObject context, Plan plan)
    { RegisterStaticSpineControlledCanvasContext(context, plan); }

    static partial void ForgetOptionalStaticSpineControlledCanvasContext(GameObject context)
    { UnregisterStaticSpineControlledCanvasContext(context); }

    static partial void BindOptionalStaticSpineReadbackOwnerContext(Plan plan, string prefabId,
        Dictionary<string, GameObject> persistentNodes, Dictionary<string, GameObject> loadedNodes, GameObject controlledHost)
    { RegisterStaticSpineReadbackOwnerContext(plan, prefabId, persistentNodes, loadedNodes, controlledHost); }

    static partial void ForgetOptionalStaticSpineReadbackOwnerContext(GameObject controlledHost)
    { UnregisterStaticSpineReadbackOwnerContext(controlledHost); }

    static partial void PrepareStaticSpineRendering(Plan plan, Dictionary<string, GameObject> nodes)
    {
        if (plan == null || String.IsNullOrEmpty(plan.staticSpineRenderingJson)) return;
        if (nodes == null) throw new InvalidOperationException("SPINE_RENDERING_NODE_MAP_MISSING");
        var frozenPath = Path.Combine(Directory.GetParent(Application.dataPath).FullName, StaticSpineRenderingPlanPath);
        if (!File.Exists(frozenPath)) throw new InvalidOperationException("SPINE_RENDERING_PLAN_FILE_MISSING");
        var raw = File.ReadAllText(frozenPath);
        using(var digest=SHA256.Create())staticSpineRenderingPlanSha=BitConverter.ToString(digest.ComputeHash(File.ReadAllBytes(frozenPath))).Replace("-",String.Empty).ToLowerInvariant();
        staticSpineRenderingPlan = JsonUtility.FromJson<StaticSpineRenderingEnvelope>(raw);
        var planRendering = JsonUtility.FromJson<StaticSpineRenderingEnvelope>(plan.staticSpineRenderingJson);
        if (staticSpineRenderingPlan == null || staticSpineRenderingPlan.schemaVersion != 1 ||
            staticSpineRenderingPlan.contract != "monkey-static-spine-rendering/1" ||
            staticSpineRenderingPlan.dataAssets == null || staticSpineRenderingPlan.components == null ||
            planRendering == null || JsonUtility.ToJson(planRendering) != JsonUtility.ToJson(staticSpineRenderingPlan))
            throw new InvalidOperationException("SPINE_RENDERING_PLAN_SCHEMA_INVALID");
        if (staticSpineSourceCanvasContext == null ||
            staticSpineSourceCanvasContext.sourceManifestSha256 != staticSpineRenderingPlan.sourceManifestSha256 ||
            staticSpineSourceCanvasContext.renderingPlanSha256 != staticSpineRenderingPlanSha ||
            !staticSpineSourceCanvasContext.sourceNodeGeometryVerified ||
            !staticSpineSourceCanvasContext.sourceCanvasContextVerified ||
            StaticSpineCanvasEvidenceHash(staticSpineSourceCanvasContext) != staticSpineSourceCanvasContext.evidenceSha256)
            throw new InvalidOperationException("SPINE_RENDERING_SOURCE_CANVAS_CONTEXT_EVIDENCE_MISSING_OR_CHANGED");

        staticSpineNativeInstanceOwners.Clear();
        staticSpineRetiredNativeInstanceOwners.Clear();
        staticSpineOwnerContextLifecycleRows.Clear();
        InitializeStaticSpineOwnerLifecycleComponents(staticSpineRenderingPlan);

        staticSpineRenderingAssemblies=new[]{
            ReadStaticSpineAssembly(typeof(global::Spine.Skeleton).Assembly,"Assets/Plugins/Spine38/EditorRuntime/spine-csharp.dll"),
            ReadStaticSpineAssembly(typeof(SkeletonGraphic).Assembly,"Assets/Plugins/Spine38/EditorRuntime/spine-unity.dll")};

        if (!VerifyStaticSpineRenderingUnitMapping(plan, nodes, out var actualCanvasPpu) || actualCanvasPpu <= 0f)
            throw new InvalidOperationException("SPINE_RENDERING_UNIT_MAPPING_NOT_VERIFIED");
        staticSpineRenderingUnitMappingVerified = true;
        staticSpineRenderingCanvasPpu = actualCanvasPpu;

        staticSpineRenderingAssets.Clear();
        foreach (var data in staticSpineRenderingPlan.dataAssets.Where(row => row != null && row.eligible))
        {
            var spec = data.factorySpec;
            if (spec == null || spec.sourceAssetId != data.sourceDataAssetId || String.IsNullOrEmpty(spec.skeletonDataAssetPath))
                throw new InvalidOperationException("SPINE_RENDERING_DATA_SPEC_IDENTITY_INVALID:" + data.sourceDataAssetId);
            var targetUnits = spec.targetUnitsPerSourcePixel;
            if (targetUnits <= 0f || Single.IsNaN(targetUnits) || Single.IsInfinity(targetUnits))
                throw new InvalidOperationException("SPINE_RENDERING_TARGET_UNIT_MAPPING_UNVERIFIED:" + data.sourceDataAssetId);
            spec = UnitySpineNativeFactory.ResolveStaticCanvasSpec(spec, actualCanvasPpu);
            data.factorySpec = spec;
            var readback = UnitySpineNativeFactory.CreateDataAsset(spec);
            if (readback == null || !readback.staticDataVerified || !readback.nativeAssetIdentityVerified ||
                !readback.savedSourceReferencesVerified || !readback.sourceProfileMaterialsVerified)
                throw new InvalidOperationException("SPINE_RENDERING_DATA_ASSET_READBACK_INCOMPLETE:" + data.sourceDataAssetId + ":" + String.Join(",", readback?.gaps ?? Array.Empty<string>()));
            staticSpineRenderingAssets.Add(data.sourceDataAssetId, readback);
        }

        var results = new List<StaticSpineRenderingReadback>();
        foreach (var row in staticSpineRenderingPlan.components)
        {
            if (row == null || String.IsNullOrEmpty(row.sourceComponentId))
                throw new InvalidOperationException("SPINE_RENDERING_COMPONENT_ROW_INVALID");
            if (!row.eligible)
            {
                results.Add(new StaticSpineRenderingReadback { sourceComponentId = row.sourceComponentId,
                    sourceDataAssetId = row.sourceDataAssetId, rendererCreated = false, sourceVisible = row.sourceVisible,
                    sourceComponentEnabled = row.sourceComponentEnabled,
                    sourceCodeExecuted = false, gaps = new[] { row.gap ?? "source-data-not-eligible" } });
                continue;
            }
            var node = ResolveRendererNode(nodes, row);
            if (node == null) throw new InvalidOperationException("SPINE_RENDERING_SOURCE_NODE_MISSING:" + row.sourceComponentId);
            if (!staticSpineRenderingAssets.TryGetValue(row.sourceDataAssetId, out var dataReadback))
                throw new InvalidOperationException("SPINE_RENDERING_DATA_ASSET_MISSING:" + row.sourceDataAssetId);
            var dataAsset = AssetDatabase.LoadAssetAtPath<SkeletonDataAsset>(dataReadback.skeletonDataAssetPath);
            if (dataAsset == null) throw new InvalidOperationException("SPINE_RENDERING_DATA_ASSET_REOPEN_MISSING:" + row.sourceDataAssetId);
            var graphic = node.GetComponent<SkeletonGraphic>();
            if (graphic != null && node.GetComponents<SkeletonGraphic>().Length != 1)
                throw new InvalidOperationException("SPINE_RENDERING_DUPLICATE_GRAPHIC:" + row.sourceComponentId);
            if (graphic == null) graphic = node.AddComponent<SkeletonGraphic>();
            graphic.allowMultipleCanvasRenderers = true;
            var expectedColor = ReadSourceNodeColor(plan, row.sourceNodeId, row.sourceComponentId);
            graphic.color = expectedColor;

            var fields = new Dictionary<string, object>(StringComparer.Ordinal);
            if (row.sourceSkinSerialized) fields["initialSkinName"] = row.sourceSkin ?? String.Empty;
            if (row.sourceAnimationSerialized) fields["startingAnimation"] = row.sourceAnimation ?? String.Empty;
            fields["startingLoop"] = row.sourceLoopSerialized && row.sourceLoop;
            fields["timeScale"] = 0.0;
            fields["pmaVertexColors"] = dataReadback.premultipliedAlpha;
            var componentReadback = UnitySpineNativeFactory.ApplyComponent(graphic, row.sourceComponentId,
                row.sourceDataAssetId, dataAsset, fields, true, dataReadback, true);
            graphic.enabled=row.sourceComponentEnabled;
            UnitySpineNativeFactory.StaticPoseReadback pose = null;
            if (row.sourceComponentEnabled)
            {
                pose = UnitySpineNativeFactory.SampleInitialPoseAtZero(graphic, row.sourceComponentId,
                    row.sourceDataAssetId, dataAsset, dataReadback, row.sourceSkinSerialized ? row.sourceSkin : null,
                    row.sourceAnimationSerialized ? row.sourceAnimation : null,
                    row.sourceLoopSerialized && row.sourceLoop);
                if (pose == null || !pose.poseVerified || Math.Abs(pose.trackTime) > 0.000001f)
                    throw new InvalidOperationException("SPINE_RENDERING_TIME_ZERO_POSE_FAILED:" + row.sourceComponentId + ":" +
                        (pose == null ? "missing" : String.Join(",", pose.gaps ?? Array.Empty<string>())));
            }
            var identity = node.GetComponents<UnitySpineSourceIdentity>().FirstOrDefault(marker => marker != null &&
                marker.instanceSourceComponentId == row.sourceComponentId);
            if (identity == null) identity = node.AddComponent<UnitySpineSourceIdentity>();
            identity.sourceComponentId = row.sourceComponentId;
            identity.templateSourceId = String.IsNullOrEmpty(row.templateComponentId) ? row.sourceComponentId : row.templateComponentId;
            identity.templateSourcePrefabId = row.sourcePrefabId;
            identity.instanceSourceComponentId = row.sourceComponentId;
            identity.rendererKind = typeof(SkeletonGraphic).FullName;
            identity.renderer = graphic;
            identity.sourceTimeScale = 0f;
            identity.nativeTimeScale = 0f;
            identity.sourceTimeScaleVerified = false;
            identity.persistentVisiblePose = row.sourceComponentEnabled;
            RegisterStaticSpineSourceConstructionOwner(row, node, graphic, dataAsset);
            bool sourceCanvasVerified = TryGetStaticSpineSourceCanvasProof(graphic, row.sourceComponentId,
                row.sourceDataAssetId, staticSpineRenderingPlan.sourceManifestSha256, staticSpineRenderingPlanSha,
                out var sourcePpu, out var sourceCanvasEvidenceSha, out var sourceCanvasContextKind, out _);
            var rendererGuid = AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(graphic));
            long localId = 0;
            AssetDatabase.TryGetGUIDAndLocalFileIdentifier(graphic, out var guid, out localId);
            var dataLocal = 0L;
            AssetDatabase.TryGetGUIDAndLocalFileIdentifier(dataAsset, out var dataGuid, out dataLocal);
            var meshCounts = ReadCanvasRendererMeshCounts(graphic);
            var poseVerified = !row.sourceComponentEnabled || (pose != null && pose.poseVerified && Math.Abs(pose.trackTime) <= 0.000001f);
            var actualEntry = graphic.AnimationState == null ? null : graphic.AnimationState.GetCurrent(0);
            results.Add(new StaticSpineRenderingReadback { sourceComponentId = row.sourceComponentId,
                sourceDataAssetId = row.sourceDataAssetId, rendererGuid = guid, rendererLocalId = localId,
                dataAssetGuid = dataGuid, dataAssetLocalId = dataLocal,
                rendererCreated = true, sourceVisible = row.sourceVisible, sourceCodeExecuted = false,
                sourceComponentEnabled = row.sourceComponentEnabled,
                unitMappingVerified = staticSpineRenderingUnitMappingVerified && dataReadback.scaleVerified && sourceCanvasVerified,
                sourceDefaultScale = staticSpineRenderingPlan.dataAssets.Single(x => x.sourceDataAssetId == row.sourceDataAssetId).factorySpec.sourceDefaultScale,
                targetUnitsPerSourcePixel = staticSpineRenderingPlan.dataAssets.Single(x => x.sourceDataAssetId == row.sourceDataAssetId).factorySpec.targetUnitsPerSourcePixel,
                canvasReferencePixelsPerUnit = sourcePpu,
                sourceCanvasReferencePixelsPerUnit = sourcePpu,
                sourceScalerReferencePixelsPerUnit = sourcePpu,
                sourceCanvasContextEvidenceSha256 = sourceCanvasEvidenceSha,
                sourceCanvasContextKind = sourceCanvasContextKind,
                sourceCanvasContextVerified = sourceCanvasVerified,
                sourceNodeActive = node.activeSelf,
                sourceNodeActivityVerified = sourceCanvasVerified && node.activeSelf == staticSpineSourceCanvasContext.components
                    .Single(item => item.sourceComponentId == row.sourceComponentId).sourceNodeActive,
                sourceCanvasRenderMode = staticSpineSourceCanvasContext.contexts
                    .Single(context => context.contextIndex == staticSpineSourceCanvasContext.components
                        .Single(item => item.sourceComponentId == row.sourceComponentId).sourceCanvasContextIndex)
                    .sourceCanvasRenderMode,
                controlledHostContextKind = sourceCanvasContextKind,
                dataScale = staticSpineRenderingAssets[row.sourceDataAssetId].scale,
                sourceVisibleVerified = (node.activeInHierarchy && graphic.enabled) == row.sourceVisible,
                rendererEnabled = graphic.enabled,
                verified = componentReadback != null && componentReadback.staticDataBound && componentReadback.componentTypeVerified &&
                    componentReadback.dataReferenceVerified && componentReadback.dataAssetContentVerified && componentReadback.rendererMaterialVerified &&
                    !String.IsNullOrEmpty(guid) && localId != 0 && !String.IsNullOrEmpty(dataGuid) && dataLocal != 0 && poseVerified && sourceCanvasVerified,
                colorVerified = graphic.color == expectedColor, materialReferencesVerified = componentReadback != null && componentReadback.rendererMaterialVerified,
                meshVertexCount = meshCounts.Item1, meshTriangleCount = meshCounts.Item2,
                poseVerified = poseVerified, sourceSkin = row.sourceSkin, actualSkin = graphic.Skeleton == null || graphic.Skeleton.Skin == null ? null : graphic.Skeleton.Skin.Name,
                sourceAnimation = row.sourceAnimation, actualAnimation = actualEntry == null || actualEntry.Animation == null ? null : actualEntry.Animation.Name,
                trackTime = actualEntry == null ? 0f : actualEntry.TrackTime,
                gaps = componentReadback == null ? new[] { "component_readback_missing" } : componentReadback.gaps });
        }
        WriteStaticSpineRenderingReadback("prepare", results);
    }

    static partial void ReadSavedStaticSpineRendering(Plan plan, Dictionary<string, GameObject> persistentNodes,
        Dictionary<string, GameObject> loadedNodes, string prefabId)
    {
        if(staticSpineRenderingPlan==null||staticSpineRenderingPlan.components==null)return;
        var rows=new List<StaticSpineRenderingReadback>();
        foreach(var expected in staticSpineRenderingPlan.components.Where(row=>row!=null&&BelongsToPrefab(row,prefabId))) {
            if(!expected.eligible) {
                rows.Add(new StaticSpineRenderingReadback{sourceComponentId=expected.sourceComponentId,
                    sourceDataAssetId=expected.sourceDataAssetId,rendererCreated=false,sourceVisible=expected.sourceVisible,
                    sourceComponentEnabled=expected.sourceComponentEnabled,sourceCodeExecuted=false,
                    gaps=new[]{expected.gap??"source-data-not-eligible"}});
                continue;
            }
            var savedNode=ResolveRendererNode(persistentNodes,expected);
            var liveNode=ResolveRendererNode(loadedNodes,expected);
            var saved=savedNode==null?null:savedNode.GetComponent<SkeletonGraphic>();
            var graphic=liveNode==null?null:liveNode.GetComponent<SkeletonGraphic>();
            if(saved==null||graphic==null)throw new InvalidOperationException("SPINE_RENDERING_SAVED_OR_LOADED_GRAPHIC_MISSING: "+expected.sourceComponentId);
            var savedMarkers=savedNode.GetComponents<UnitySpineSourceIdentity>().Where(x=>x.renderer==saved&&x.instanceSourceComponentId==expected.sourceComponentId).ToArray();
            var liveMarkers=liveNode.GetComponents<UnitySpineSourceIdentity>().Where(x=>x.renderer==graphic&&x.instanceSourceComponentId==expected.sourceComponentId).ToArray();
            if(savedMarkers.Length!=1||liveMarkers.Length!=1)throw new InvalidOperationException("SPINE_RENDERING_SAVED_INSTANCE_IDENTITY_MISMATCH: "+expected.sourceComponentId);
            string guid=null;long local=0;
            bool persistent=EditorUtility.IsPersistent(saved)&&AssetDatabase.TryGetGUIDAndLocalFileIdentifier(saved,out guid,out local)&&!String.IsNullOrEmpty(guid)&&local!=0;
            // Persistent assets supply identity/serialized state. The existing
            // owned UI context supplies a separately reopened, initialized pose.
            var data=saved.SkeletonDataAsset;
            string dataGuid=null;long dataLocal=0;
            bool dataPersistent=data!=null&&EditorUtility.IsPersistent(data)&&AssetDatabase.TryGetGUIDAndLocalFileIdentifier(data,out dataGuid,out dataLocal)&&!String.IsNullOrEmpty(dataGuid)&&dataLocal!=0;
            var spec=staticSpineRenderingPlan.dataAssets.Single(x=>x.sourceDataAssetId==expected.sourceDataAssetId).factorySpec;
            var dataReadback=UnitySpineNativeFactory.ReadDataAssetAsset(spec);
            var expectedAsset=AssetDatabase.LoadAssetAtPath<SkeletonDataAsset>(spec.skeletonDataAssetPath);
            bool fieldsMatch=data==expectedAsset&&graphic.SkeletonDataAsset==data&&saved.enabled==expected.sourceComponentEnabled&&graphic.enabled==saved.enabled&&
                saved.initialSkinName==graphic.initialSkinName&&saved.startingAnimation==graphic.startingAnimation&&saved.startingLoop==graphic.startingLoop&&
                saved.color==graphic.color&&saved.material==graphic.material&&saved.allowMultipleCanvasRenderers&&graphic.allowMultipleCanvasRenderers&&
                Math.Abs(saved.timeScale)<=0.000001f&&Math.Abs(graphic.timeScale-saved.timeScale)<=0.000001f&&
                (!expected.sourceSkinSerialized||saved.initialSkinName==(expected.sourceSkin??String.Empty))&&
                (!expected.sourceAnimationSerialized||saved.startingAnimation==(expected.sourceAnimation??String.Empty))&&
                saved.startingLoop==(expected.sourceLoopSerialized&&expected.sourceLoop);
            bool sourceCanvasVerified=TryGetStaticSpineSourceCanvasProof(graphic,expected.sourceComponentId,
                expected.sourceDataAssetId,staticSpineRenderingPlan.sourceManifestSha256,staticSpineRenderingPlanSha,
                out var sourcePpu,out var sourceCanvasEvidenceSha,out var sourceCanvasContextKind,out var sourceCanvasDiagnostic);
            var ownerContext=staticSpineReadbackOwnerScopes.SelectMany(scope=>scope.rows).SingleOrDefault(row=>row!=null&&
                row.sourceComponentId==expected.sourceComponentId&&row.sourceDataAssetId==expected.sourceDataAssetId&&
                row.loadedOwner==graphic&&row.persistentOwner==saved);
            bool hostContextVerified=ownerContext!=null&&ownerContext.hostEvidence!=null&&ownerContext.hostEvidence.verified;
            var hostEvidence=ownerContext==null?null:ownerContext.hostEvidence;
            bool unitVerified=staticSpineRenderingUnitMappingVerified&&sourceCanvasVerified&&hostContextVerified&&
                dataReadback.staticDataVerified&&dataReadback.scaleVerified&&
                Math.Abs(dataReadback.scale-spec.sourceDefaultScale*spec.targetUnitsPerSourcePixel/sourcePpu)<=0.000001f;
            // Generic Graphic/Layout refreshes can overwrite a derived RawImage
            // mesh. The SDK must write its actual source-pose geometry last.
            FinalizeSavedStaticSortSpineMeshes(new Graphic[]{graphic});
            var presentation=graphic.GetComponent<UnitySpineGraphicMaterialPresentation>();
            var materialReadback=presentation==null?null:presentation.ReadSavedStoredState();
            var entry=graphic.AnimationState==null?null:graphic.AnimationState.GetCurrent(0);
            var skeleton=graphic.Skeleton;
            var effectiveSkin=skeleton==null?null:skeleton.Skin!=null?skeleton.Skin.Name:skeleton.Data.DefaultSkin==null?null:skeleton.Data.DefaultSkin.Name;
            var actualAnimation=entry==null||entry.Animation==null?null:entry.Animation.Name;
            bool actualLoop=entry==null?saved.startingLoop:entry.Loop;
            bool poseVerified=skeleton!=null&&graphic.AnimationState!=null&&
                (!expected.sourceSkinSerialized||String.IsNullOrEmpty(expected.sourceSkin)||effectiveSkin==expected.sourceSkin)&&
                (!expected.sourceAnimationSerialized||String.IsNullOrEmpty(expected.sourceAnimation)?entry==null:actualAnimation==expected.sourceAnimation)&&
                (entry==null||Math.Abs(entry.TrackTime)<=0.000001f)&&actualLoop==saved.startingLoop;
            bool visibleVerified=(liveNode.activeInHierarchy&&graphic.enabled)==expected.sourceVisible;
            bool colorVerified=saved.color==ReadSourceNodeColor(plan,expected.sourceNodeId,expected.sourceComponentId)&&graphic.color==saved.color;
            var mesh=ReadCanvasRendererMeshCounts(graphic);
            bool meshVerified=!expected.sourceVisible||mesh.Item1>0&&mesh.Item2>0;
            bool materialsVerified=materialReadback!=null&&materialReadback.nativeMaterialVerified&&dataReadback.sourceProfileMaterialsVerified;
            var issues=new List<string>();
            if(!persistent||!dataPersistent)issues.Add("saved_persistent_identity_unverified");
            if(!fieldsMatch)issues.Add("saved_or_reopened_serialized_fields_differ");
            if(!sourceCanvasVerified)issues.Add(sourceCanvasDiagnostic??"source_canvas_context_unverified");
            if(!hostContextVerified)issues.Add("controlled_host_context_unverified");
            if(!unitVerified)issues.Add("source_to_native_unit_mapping_unverified");
            if(!poseVerified)issues.Add("source_time_zero_pose_unverified");
            if(!visibleVerified)issues.Add("source_visibility_differs");
            if(!colorVerified)issues.Add("source_node_color_differs");
            if(!meshVerified)issues.Add("visible_source_mesh_missing");
            if(!materialsVerified)issues.AddRange(materialReadback==null?new[]{"source_material_readback_missing"}:materialReadback.gaps??new[]{"source_material_readback_unverified"});
            rows.Add(new StaticSpineRenderingReadback{sourceComponentId=expected.sourceComponentId,sourceDataAssetId=expected.sourceDataAssetId,
                rendererGuid=guid,rendererLocalId=local,dataAssetGuid=dataGuid,dataAssetLocalId=dataLocal,
                persistent=persistent,dataPersistent=dataPersistent,serializedFieldsVerified=fieldsMatch,
                rendererCreated=true,sourceVisible=expected.sourceVisible,sourceComponentEnabled=expected.sourceComponentEnabled,
                sourceVisibleVerified=visibleVerified,rendererEnabled=saved.enabled,sourceCodeExecuted=false,
                verified=persistent&&dataPersistent&&fieldsMatch&&unitVerified&&poseVerified&&visibleVerified&&colorVerified&&meshVerified&&materialsVerified&&
                    ownerContext!=null&&ownerContext.sourceNodeActive==savedNode.activeSelf,
                unitMappingVerified=unitVerified,sourceDefaultScale=spec.sourceDefaultScale,targetUnitsPerSourcePixel=spec.targetUnitsPerSourcePixel,
                canvasReferencePixelsPerUnit=sourcePpu,sourceCanvasReferencePixelsPerUnit=sourcePpu,
                sourceNodeActive=ownerContext!=null&&ownerContext.sourceNodeActive,
                sourceNodeActivityVerified=ownerContext!=null&&ownerContext.sourceNodeActive==savedNode.activeSelf&&liveNode.activeSelf==savedNode.activeSelf,
                sourceScalerReferencePixelsPerUnit=sourcePpu,sourceCanvasContextEvidenceSha256=sourceCanvasEvidenceSha,
                sourceCanvasContextKind=sourceCanvasContextKind,sourceCanvasContextVerified=sourceCanvasVerified,
                controlledHostCanvasReferencePixelsPerUnit=hostEvidence==null?0f:hostEvidence.controlledHostReferencePixelsPerUnit,
                controlledHostCanvasRenderMode=hostEvidence==null?null:hostEvidence.controlledHostCanvasRenderMode,
                controlledHostContextEvidenceSha256=hostEvidence==null?null:hostEvidence.evidenceSha256,
                controlledHostContextKind=hostEvidence==null?null:hostEvidence.contextKind,
                controlledHostContextEvidence=hostEvidence,
                sourceCanvasRenderMode=staticSpineSourceCanvasContext.contexts.Single(context=>context.contextIndex==
                    staticSpineSourceCanvasContext.components.Single(item=>item.sourceComponentId==expected.sourceComponentId).sourceCanvasContextIndex)
                    .sourceCanvasRenderMode,
                controlledHostContextVerified=hostContextVerified,dataScale=dataReadback.scale,
                poseVerified=poseVerified,colorVerified=colorVerified,materialReferencesVerified=materialsVerified,
                meshVertexCount=mesh.Item1,meshTriangleCount=mesh.Item2,sourceSkin=expected.sourceSkin,actualSkin=effectiveSkin,
                actualSkinImplicitDefault=skeleton!=null&&skeleton.Skin==null,sourceAnimation=expected.sourceAnimation,actualAnimation=actualAnimation,
                sourceLoop=expected.sourceLoop,sourceLoopSerialized=expected.sourceLoopSerialized,actualLoop=actualLoop,
                loopStatus=entry==null?"saved_starting_loop_no_runtime_track":expected.sourceLoopSerialized?"source_serialized":"frozen_time_zero_only",
                timeScale=saved.timeScale,trackTime=entry==null?0f:entry.TrackTime,gaps=issues.ToArray()});
        }
        WriteStaticSpineRenderingReadback(prefabId,rows);
    }

    static StaticSpineRenderingAssembly ReadStaticSpineAssembly(System.Reflection.Assembly assembly,string target) {
        var pins=(staticSpineRenderingPlan.payloads??Array.Empty<StaticSpineRenderingPayload>()).Where(row=>row.target==target).ToArray();
        if(pins.Length!=1||String.IsNullOrEmpty(pins[0].sha256)||String.IsNullOrEmpty(assembly.Location)||!File.Exists(assembly.Location))
            throw new InvalidOperationException("SPINE_RENDERING_LOADED_ASSEMBLY_IDENTITY_MISSING: "+target);
        var actual=Hash(assembly.Location);
        bool verified=actual==pins[0].sha256&&Hash(target)==pins[0].sha256;
        if(!verified)throw new InvalidOperationException("SPINE_RENDERING_LOADED_ASSEMBLY_BYTES_MISMATCH: "+target);
        return new StaticSpineRenderingAssembly{target=target,expectedSha256=pins[0].sha256,loadedPath=assembly.Location,loadedSha256=actual,verified=true};
    }

    static GameObject ResolveRendererNode(Dictionary<string, GameObject> nodes, StaticSpineRenderingComponent row)
    {
        if (nodes == null || row == null) return null;
        return nodes.TryGetValue(row.sourceNodeId, out var exact) ? exact : null;
    }

    static bool BelongsToPrefab(StaticSpineRenderingComponent row, string prefabId)
    {
        if (row == null || String.IsNullOrEmpty(prefabId)) return false;
        return row.sourcePrefabId == prefabId || row.sourceComponentId.StartsWith(prefabId + "#", StringComparison.Ordinal);
    }

    static Tuple<int, int> ReadCanvasRendererMeshCounts(SkeletonGraphic graphic)
    {
        int vertices = 0, triangles = 0;
        if (graphic == null || graphic.canvasRenderers == null) return Tuple.Create(vertices, triangles);
        foreach (var renderer in graphic.canvasRenderers.Where(row => row != null))
        {
            var mesh = renderer.GetMesh();
            if(mesh==null)continue;
            vertices += mesh.vertexCount;
            for(int submesh=0;submesh<mesh.subMeshCount;submesh++)
                triangles += (int)(mesh.GetIndexCount(submesh)/3);
        }
        return Tuple.Create(vertices, triangles);
    }

    static Color ReadSourceNodeColor(Plan plan, string sourceNodeId, string sourceComponentId)
    {
        var source = plan.nodes == null ? null : plan.nodes.SingleOrDefault(row => row != null && row.sourceId == sourceNodeId);
        if (source == null) throw new InvalidOperationException("SPINE_RENDERING_SOURCE_NODE_COLOR_MISSING:" + sourceComponentId);
        var channels = source.color;
        if (channels == null || channels.Length != 4 || channels.Any(value => Single.IsNaN(value) || Single.IsInfinity(value) || value < 0f || value > 255f))
            throw new InvalidOperationException("SPINE_RENDERING_SOURCE_NODE_RGBA_INVALID:" + sourceComponentId);
        return new Color(channels[0] / 255f, channels[1] / 255f, channels[2] / 255f, channels[3] / 255f);
    }

    static void WriteStaticSpineRenderingReadback(string name, List<StaticSpineRenderingReadback> rows)
    {
        var path = Path.Combine(Directory.GetParent(Application.dataPath).FullName, StaticSpineRenderingReadbackRoot,
            name=="prepare"?"prepare.json":SpineSha(name??String.Empty)+".json");
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        var contextPath = Path.Combine(Directory.GetParent(Application.dataPath).FullName,
            StaticSpineCanvasContextEvidencePath.Replace('/', Path.DirectorySeparatorChar));
        var contextBytes = Encoding.UTF8.GetBytes(JsonUtility.ToJson(staticSpineSourceCanvasContext, true));
        File.WriteAllBytes(contextPath, contextBytes);
        var contextFileSha = StaticSpineCanvasHashBytes(contextBytes);
        File.WriteAllText(path, JsonUtility.ToJson(new StaticSpineRenderingReadbackEnvelope {
            status = rows.All(row => row != null && row.verified) ? "verified" : "partial", components = rows.ToArray(),
            phase=name=="prepare"?"prepare-only":"saved-prefab-reopen",sourcePrefabId=name=="prepare"?null:name,
            sourceManifestSha256=staticSpineRenderingPlan.sourceManifestSha256,renderingPlanSha256=staticSpineRenderingPlanSha,
            sourceCanvasContext=staticSpineSourceCanvasContext,
            sourceCanvasContextEvidencePath=StaticSpineCanvasContextEvidencePath,
            sourceCanvasContextEvidenceFileSha256=contextFileSha,
            unityVersion=Application.unityVersion,runtimeAssemblies=staticSpineRenderingAssemblies
        }, true));
    }
}
