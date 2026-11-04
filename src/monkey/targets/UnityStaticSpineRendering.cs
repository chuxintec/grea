// Static, time-zero SkeletonGraphic preparation for the frozen Cocos Spine source join.
// Source callbacks and recovered game scripts are never executed here.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
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
        public bool sourceCodeExecuted;
        public bool persistent,dataPersistent,serializedFieldsVerified,actualSkinImplicitDefault;
        public bool sourceLoop,actualLoop,sourceLoopSerialized;
        public float timeScale;
        public string loopStatus;
        public bool unitMappingVerified;
        public float sourceDefaultScale;
        public float targetUnitsPerSourcePixel;
        public float canvasReferencePixelsPerUnit;
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
        public StaticSpineRenderingReadback[] components;
        public StaticSpineRenderingAssembly[] runtimeAssemblies;
    }

    const string StaticSpineRenderingPlanPath = "Assets/Game/Editor/Conversion/spine-static-rendering.json";
    const string StaticSpineRenderingReadbackRoot = "Analysis/Readback/SpineRendering";
    static StaticSpineRenderingEnvelope staticSpineRenderingPlan;
    static string staticSpineRenderingPlanSha;
    static StaticSpineRenderingAssembly[] staticSpineRenderingAssemblies;
    static bool staticSpineRenderingUnitMappingVerified;
    static float staticSpineRenderingCanvasPpu;
    static readonly Dictionary<string, UnitySpineNativeFactory.DataAssetReadback> staticSpineRenderingAssets =
        new Dictionary<string, UnitySpineNativeFactory.DataAssetReadback>(StringComparer.Ordinal);

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
            spec.scale = spec.sourceDefaultScale * targetUnits / actualCanvasPpu;
            var readback = UnitySpineNativeFactory.CreateDataAsset(spec);
            if (readback == null || !readback.staticDataVerified || !readback.nativeAssetIdentityVerified ||
                !readback.savedSourceReferencesVerified || !readback.sourceProfileMaterialsVerified)
                throw new InvalidOperationException("SPINE_RENDERING_DATA_ASSET_READBACK_INCOMPLETE:" + data.sourceDataAssetId);
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
                unitMappingVerified = staticSpineRenderingUnitMappingVerified && dataReadback.scaleVerified,
                sourceDefaultScale = staticSpineRenderingPlan.dataAssets.Single(x => x.sourceDataAssetId == row.sourceDataAssetId).factorySpec.sourceDefaultScale,
                targetUnitsPerSourcePixel = staticSpineRenderingPlan.dataAssets.Single(x => x.sourceDataAssetId == row.sourceDataAssetId).factorySpec.targetUnitsPerSourcePixel,
                canvasReferencePixelsPerUnit = actualCanvasPpu,
                dataScale = staticSpineRenderingAssets[row.sourceDataAssetId].scale,
                sourceVisibleVerified = (node.activeInHierarchy && graphic.enabled) == row.sourceVisible,
                rendererEnabled = graphic.enabled,
                verified = componentReadback != null && componentReadback.staticDataBound && componentReadback.componentTypeVerified &&
                    componentReadback.dataReferenceVerified && componentReadback.dataAssetContentVerified && componentReadback.rendererMaterialVerified &&
                    !String.IsNullOrEmpty(guid) && localId != 0 && !String.IsNullOrEmpty(dataGuid) && dataLocal != 0 && poseVerified,
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
            var canvas=graphic.canvas;
            bool unitVerified=staticSpineRenderingUnitMappingVerified&&canvas!=null&&SpineUnitClose(canvas.referencePixelsPerUnit,staticSpineRenderingCanvasPpu)&&
                dataReadback.staticDataVerified&&dataReadback.scaleVerified&&Math.Abs(dataReadback.scale-spec.sourceDefaultScale*spec.targetUnitsPerSourcePixel/staticSpineRenderingCanvasPpu)<=0.000001f;
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
                verified=persistent&&dataPersistent&&fieldsMatch&&unitVerified&&poseVerified&&visibleVerified&&colorVerified&&meshVerified&&materialsVerified,
                unitMappingVerified=unitVerified,sourceDefaultScale=spec.sourceDefaultScale,targetUnitsPerSourcePixel=spec.targetUnitsPerSourcePixel,
                canvasReferencePixelsPerUnit=staticSpineRenderingCanvasPpu,dataScale=dataReadback.scale,
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
        File.WriteAllText(path, JsonUtility.ToJson(new StaticSpineRenderingReadbackEnvelope {
            status = rows.All(row => row != null && row.verified) ? "verified" : "partial", components = rows.ToArray(),
            phase=name=="prepare"?"prepare-only":"saved-prefab-reopen",sourcePrefabId=name=="prepare"?null:name,
            sourceManifestSha256=staticSpineRenderingPlan.sourceManifestSha256,renderingPlanSha256=staticSpineRenderingPlanSha,
            unityVersion=Application.unityVersion,runtimeAssemblies=staticSpineRenderingAssemblies
        }, true));
    }
}
