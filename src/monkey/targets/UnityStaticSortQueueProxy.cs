using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.UI;
using Monkey.StaticMaskSort;
using Monkey.StaticSortQueue;

namespace Monkey.StaticSortQueueProxy
{
    [Serializable] public sealed class ProxyRendererSpec
    {
        public string node, sourceComponentId, sourceType, expectedGraphicType;
        public float sourceSortOrder;
        public int sourceQueueIndex;
        public bool sourceEnabled, sourceActive, sourceTextureBound, sourceTextEmpty, sourceFontMissing;
        public string sourceText, nativeTextExpectation, sourceFieldsJson, sourceFieldsSha256, sourceDrawingCommands;
        public string[] sourceMaterialGuids;
        public bool sourceCommandsEmpty;
    }
    [Serializable] public sealed class ProxyBlockInputSpec
    {
        public string sourceComponentId, node, sourceType, expectedSourceGraphicComponentId, expectedSourceGraphicType;
        public bool sourceEnabled, sourceActive;
    }
    [Serializable] public sealed class ProxyMaskSpec
    {
        public string node, sourceId, nativeId, spriteFrameUuid, sourceFieldsJson;
        public int maskType;
        public bool inverted, enabled, convertible;
        public float alphaThreshold;
        public string sourceMaterialId, resolvedSourceMaterialId, sourceEffectId, sourceEffectName,
            sourceEffectDocumentSha256, unityMaskShaderPath, unityMaskShaderSha256,
            unityMaskMaterialGuid, unityMaskMaterialPath;
    }
    [Serializable] public sealed class ProxySourceMaskIdentitySpec
    {
        public string sourceId, nativeId, node, sourceFieldsJson, spriteFrameUuid, sourceMaterialId,
            resolvedSourceMaterialId, sourceEffectId, sourceEffectName, sourceEffectDocumentSha256,
            unityMaskShaderPath, unityMaskShaderSha256, unityMaskMaterialGuid, unityMaskMaterialPath;
        public int maskType;
        public bool enabled, inverted, sourceActiveSelf, sourceActive;
        public float alphaThreshold;
    }
    [Serializable] public sealed class ProxyDrawEventSpec
    {
        public string kind, node, sourceComponentId;
    }
    [Serializable] public sealed class ProxySortRootFieldSpec
    {
        public string sourceId, nativeId, node;
        public bool enabled;
    }
    [Serializable] public sealed class ProxySourceChildrenSpec
    {
        public string node;
        public string[] children;
    }
    [Serializable] public sealed class ProxySourceActiveSpec
    {
        public string node;
        public bool active;
    }
    [Serializable] public sealed class ProxyQueueSpec
    {
        public string rootScope, sourcePrefabId, prefabPath, meshAssetFolder, sourceManifestSha256;
        public ProxyRendererSpec[] renderers;
        public ProxyMaskSpec[] masks;
        public ProxySourceMaskIdentitySpec[] sourceMaskIdentities;
        public ProxyDrawEventSpec[] drawEvents;
        public QueueSortFieldSpec[] sourceFields;
        public ProxySortRootFieldSpec[] sourceSortRoots;
        public ProxySourceChildrenSpec[] sourceChildOrder;
        public ProxySourceActiveSpec[] sourceNodeActive;
        public ProxyRendererSpec[] nonDrawRenderers;
        public ProxyBlockInputSpec[] sourceBlockInputEvents;
    }
    public sealed class ProxyPrefabScopeProvenance
    {
        public string sourcePrefabId, prefabPath, rootScope;
        public GameObject persistentAssetRoot, loadedScopeRoot;
    }
    [Serializable] public sealed class ProxyPresenterReadback
    {
        public string sourceComponentId, sourceNode, nativeGraphicType, sourceMeshSha256, currentTextSourceMeshSha256,
            proxyMeshSha256, renderedMeshSha256,
            capturedSourceMeshSha256, meshContentSha256, meshAssetGuid, materialGuid, textureGuid,
            expectedTransformedMeshSha256, actualTransformedMeshSha256, transformCaptureDiagnosticJson,
            transformedUvDiagnostic, transformedVertexDiagnostic, worldMeasurementMethod, transformedSourceMatrixExact,
            transformedProxyMatrixExact, transformedMatrixDifference;
        public int submeshIndex, vertexCount, sourceQueueIndex, textMaterialSlot;
        public int sourceVertexCount, persistedProxyVertexCount;
        public int[] sourceUvChannelVertexCounts, proxyUvChannelVertexCounts, renderedUvChannelVertexCounts;
        public int[] sourceUvChannelDimensions, proxyUvChannelDimensions, renderedUvChannelDimensions;
        public float sourceRendererAlpha, proxyRendererAlpha, sourceInheritedAlpha, proxyInheritedAlpha,
            sourceEffectiveAlpha, proxyEffectiveAlpha, maxWorldVertexError, maxWorldNormalError, maxWorldTangentError;
        public bool sourceGraphicEnabled, sourceCulled, proxyVisible, generatedSourceChild,
            staticSnapshotVerified, transformedGeometryVerified, runtimeMeshVerified, opacityVerified, verified,
            worldRectVerified, transformedMeshFingerprintVerified, transformedMeshMetricsVerified,
            transformedTopologyMatches, transformedUvMatches, transformedColorsMatch, transformedNormalsMatch,
            transformedTangentsMatch;
    }
    [Serializable] sealed class ProxyRectCopyCaptureDiagnostic
    {
        public string sourceComponentId, selectedPath, sourceParentPath, targetParentPath;
        public float[] sourceParentMatrix, targetParentMatrix, sourceLocalToWorldMatrix, finalProxyLocalToWorldMatrix;
        public Vector3 sourceLocalPosition, sourceLocalScale, finalProxyLocalPosition, finalProxyLocalScale;
        public Vector3 sourcePivotWorld, finalProxyPivotWorld;
        public float pivotWorldError;
        public Quaternion sourceLocalRotation, finalProxyLocalRotation;
        public bool linearBasisExactlyEqual, originCorrectionAttempted, originCorrectionSucceeded, finalWorldRectMatches;
        public Vector3 originCorrectionLocal;
        public float originCorrectionResidual;
    }
    [Serializable] public sealed class ProxySpineOwnerDelegationReadback
    {
        public string sourceComponentId, sourceNode, sourceGraphicType, sourceIdentityComponentId, sourceDataAssetId,
            sourceDataAssetPath, sourceDataAssetGuid, sourceBindingPlanPath,
            sourceBindingPlanSha256, sourceManifestSha256;
        public int rootMeshVertexCount, rootMeshSubmeshCount, rootCanvasMaterialCount;
        public string[] delegatedChildPaths, delegatedChildGraphicTypes, delegatedChildTextureGuids,
            delegatedChildMaterialGuids;
        public int[] childMeshVertexCounts, childMeshSubmeshCounts, childCanvasMaterialCounts;
        public bool rootMeshWasMissing, sourceIdentityVerified, sourceDataReferenceVerified, rootMeshDelegated,
            childRendererListVerified, childReferencesPersistent, verified;
    }
    [Serializable] public sealed class ProxySpineNonDrawChildReadback
    {
        public string sourceComponentId, sourceNode, noDrawReason, sourceIdentityComponentId, sourceDataAssetId,
            sourceDataAssetPath, sourceDataAssetGuid, childPath, childGraphicType, childMaterialGuid, childTextureGuid;
        public bool sourceOwnerEnabled, sourceNodeActive, sourceChildEnabled, sourceChildActiveSelf,
            sourceChildActiveInHierarchy, targetChildEnabled, targetChildActiveInHierarchy,
            sourceIdentityVerified, sourceDataReferenceVerified, registeredChildVerified,
            childReferencePersistent, childNoDrawVerified, ownerOnlyNoRegisteredChildren,
            ownerRendererListReadable, ownerRendererListEmpty, ownerRootMeshEmpty, verified;
        public int sourceChildMeshVertexCount, sourceChildMeshSubmeshCount, sourceChildMaterialCount;
        public int ownerRootMeshVertexCount, ownerRootMeshSubmeshCount, ownerRootMeshIndexCount, ownerRootCanvasMaterialCount;
        public string ownerRootMeshSha256;
        public int currentOwnerRootMeshVertexCount, currentOwnerRootMeshSubmeshCount, currentOwnerRootMeshIndexCount,
            currentOwnerRootCanvasMaterialCount;
        public string currentOwnerRootMeshSha256;
        public bool currentOwnerRendererListReadable, currentOwnerRendererListEmpty, currentOwnerRootMeshEmpty,
            ownerRootMeshCaptureAndCurrentFingerprintAbsent;
    }
    [Serializable] public sealed class ProxySpineNullDataOwnerReadback
    {
        public string sourceComponentId, sourceNode, sourceStaticDataState, sourceBindingPlanPath,
            sourceBindingPlanSha256, sourceManifestSha256, sourceMaterialClosureStatus,
            sourceIdentityComponentId, sourceTargetFieldsJson, expectedFieldsJson,
            actualFieldsJson, sourceActivityStage, rootMaterialEvidence, rootMeshSha256, rootMeshGeometryEvidence,
            savedOwnerReferenceEvidence, currentOwnerReferenceEvidence;
        public string[] savedProofDifferences;
        public bool sourceHasStaticDataReference, sourceDataAssetIdNull, sourcePlanVerified, sourceIdentityVerified,
            sourceNodeInactive, sourceNodeActive, sourceOwnerEnabled, nativeDataReferenceNull,
            sourceSerializedActive, sourceSerializedActiveVerified,
            nativeRootMeshEmpty, nativeRootMeshDefaultGraphicQuad, rootCanvasDefaultMaterialOnly, rootSourceBaseDefaultMaterial,
            rootMaterialSlotMatchesGraphicRendering, registeredRendererListEmpty,
            mappedStaticFieldsVerified, sourceBehaviorBoundaryVerified, dynamicAssignmentUnverified,
            sourceTimeScaleVerified, sourceIdentityTimeScaleVerified, persistentVisiblePose, verified;
        public int rootMeshVertexCount, rootMeshSubmeshCount, rootMeshIndexCount, rootCanvasMaterialCount,
            rootExtraMaterialModifierCount, registeredRendererCount;
        public float sourceTimeScale, nativeTimeScale;
    }
    [Serializable] public sealed class ProxySpineEmptyPoseOwnerReadback
    {
        public string sourceComponentId, sourceNode, sourceDataAssetId, sourceDataAssetPath, sourceDataAssetGuid,
            sourceBindingPlanPath, sourceBindingPlanSha256, sourceManifestSha256, sourceSkin, sourceAnimation,
            actualSkin, runtimeDefaultSkinName, actualAnimation, sourceTargetFieldsJson, expectedFieldsJson, actualFieldsJson;
        public bool sourceHasStaticDataReference, sourcePlanVerified, sourceIdentityVerified,
            sourceDataReferenceVerified, sourceTimeScaleVerified, sourceIdentityTimeScaleVerified,
            persistentVisiblePose, sourceBusinessBehaviorDisabled, sourceCallbacksExecuted,
            mappedStaticFieldsVerified, sdkPoseInitialized, sdkDataIdentityVerified,
            sourceSkinRuntimeVerified, defaultSkinRuntimeNull, fixedPoseVerified, noDrawableAttachmentPoseVerified, rootMeshEmpty,
            registeredRendererListEmpty, helperReadbackVerified, verified;
        public bool presenterFound, presenterProofCardinalityVerified, presenterOwnerReferenceVerified, presenterDataAssetReferenceVerified,
            presenterSourceIdentityVerified, presenterSkinEvidenceVerified, presenterFieldEvidenceVerified,
            storedCaptureProofVerified, storedSkinRepresentationVerified, loadedPoseVerified;
        public bool currentOwnerPresent, currentOwnerTypeMatches, currentOwnerEnabledMatches,
            currentOwnerReferenceMatchesStored, currentOwnerNodeMappingMatches, currentSourceIdentityMatches,
            currentSourceSerializedActivityVerified, currentSourceSerializedActivityMatchesExpected,
            currentSourceHierarchyActivityMatchesExpected, currentDataAssetPresent,
            currentDataAssetReferenceMatchesStored, currentDataAssetIdentityVerified,
            currentDataAssetIdMatchesStored, currentDataAssetPathMatchesStored, currentDataAssetGuidMatchesStored,
            currentBindingPlanPathMatchesStored, currentBindingPlanHashMatchesStored,
            currentManifestMatchesStored;
        public string diagnostic, currentOwnerType, currentOwnerIdentityComponentId, currentSourceIdentityComponentType,
            currentDataAssetType, currentDataAssetPath, currentDataAssetGuid, currentDataAssetId,
            currentBindingPlanPath, currentBindingPlanSha256, currentSourceManifestSha256;
        public bool currentOwnerEnabled, expectedOwnerEnabled, sourceSerializedEffectiveActive,
            expectedSerializedEffectiveActive, sourceHierarchyActive, expectedHierarchyActive;
        public int presenterProofArrayLength, presenterMatchingProofCount;
        public int fixedPoseSlotCount, fixedPoseAttachmentCount, fixedPoseDrawableAttachmentCount,
            presentationInstructionCount, presentationCanvasRendererCount, rootMeshVertexCount,
            rootMeshSubmeshCount, rootCanvasMaterialCount, registeredRendererCount;
        public float sourceTimeScale, nativeTimeScale, actualTrackTime;
    }
    [Serializable] public sealed class ProxyQueueReadback
    {
        public string rootScope, proxyRootName;
        public bool sourceTreePreserved, sourceActivePreserved, sourceFieldsPreserved, sourceSortRootsPreserved,
            nestedProxyRootsDisabled, drawSequenceVerified, rendererDenominatorVerified, prefabPathVerified,
            rootMarkerVerified, presenterReferencesVerified, presenterEnabled, maskRowsVerified,
            nativeStructureVerified, graphicsStaticSnapshotVerified, graphicsRuntimeGeometryVerified,
            persistentAssetScopeVerified, loadedAssetScopeVerified, loadedSourceRootIsPersistent, verified;
        public bool sourceBlockInputEventsVerified;
        public bool spineNullDataOwnersVerified;
        public bool spineEmptyPoseOwnersVerified;
        public string diagnostic, readbackMode;
        public string prefabScopeProvenanceDiagnostic;
        public string[] aggregateDiagnostics;
        public string[] spineDelegationDiagnostics, spineNonDrawChildDiagnostics;
        public string[] spineNullDataOwnerDiagnostics;
        public string[] spineEmptyPoseOwnerDiagnostics;
        public bool provisional, persistentSnapshotVerified, initializedPresentationVerified, runtimeGeometryDeferred;
        public bool sourceGraphicsCovered, layoutIgnored, spineDelegationsVerified, spineNonDrawChildrenVerified;
        public bool textSourcesVerified;
        public bool sourceMaskReferencesVerified;
        public bool sourceMaskIdentitiesVerified;
        public string[] structuralDiagnostics;
        public ProxyPresenterReadback[] graphics;
        public ProxyTextSourceReadback[] textSources;
        public ProxySpineOwnerDelegationReadback[] spineOwnerDelegations;
        public ProxySpineNonDrawChildReadback[] spineNonDrawChildren;
        public ProxySpineNullDataOwnerReadback[] spineNullDataOwners;
        public ProxySpineEmptyPoseOwnerReadback[] spineEmptyPoseOwners;
        public ProxyEmptyRendererReadback[] emptyRenderers;
        public ProxyBlockInputReadback[] blockInputEvents;
        public ProxyMaskReadback[] masks;
        public ProxySourceMaskIdentityReadback[] sourceMaskIdentities;
        public ProxySortFieldReadback[] sourceFields;
        public ProxySortRootValueReadback[] sourceSortRoots;
        public string[] maskSourceIds;
    }
    [Serializable] public sealed class ProxyTextSourceReadback
    {
        public string sourceNode, readbackMode, sourceComponentId;
        public int materialSlot;
        public TextSourceReadback evidence;
    }
    [Serializable] public sealed class ProxyEmptyRendererReadback
    {
        public string sourceComponentId, sourceNode, sourceType, noDrawReason, carrierGuid;
        public string sourceComponentType, sourceFieldsSha256, sourceDrawingCommands, sourceText, nativeTextExpectation, nativeText,
            sourceActivityStage;
        public string[] sourceMaterialGuids, actualSourceMaterialGuids;
        public long carrierLocalFileId;
        public bool sourceEnabled, sourceActive, sourceActiveSelf, sourceSerializedActive,
            sourceSerializedActiveVerified, sourceHierarchyActiveMatchesExpected, sourceActivityMatchesExpected,
            nativeGraphicEnabled, nativeComponentEnabled, sourceActiveInHierarchy,
            sourceTextureBound, nativeTextureBound, sourceTextEmpty, nativeTextEmpty,
            sourceFontMissing, nativeFontMissing, sourceMeshPresent, carrierPresent,
            carrierAssetIdentityVerified, carrierOwnerScopeVerified,
            sourceSpineNullDataProofVerified, sourceSpineNullDataRootFallbackQuad,
            sourceSpineNullDataRootMeshCacheAbsent,
            sourceSpineNullDataCurrentDefaultMaterialOnly,
            sourceNoDrawEvidenceVerified,
            sourceGraphicSuppressedByPresenter,
            sourceReferenceVerified, typedFieldsVerified, sourceCommandsEmpty, nativeCommandsEmpty, verified;
        public int sourceMeshVertexCount, sourceCanvasMaterialCount, actualQueueIndex;
        public ProxySpineEmptyPoseOwnerReadback spineEmptyPoseProof;
        public string spineNullDataRootMeshSha256;
        public TextSlotEnumerationReadback emptyTextSlotEnumerationProof;
        public bool emptyTextSlotEnumerationVerified;
    }
    [Serializable] public sealed class ProxyBlockInputReadback
    {
        public string sourceComponentId, sourceNode, surfaceType, expectedSourceGraphicComponentId,
            expectedSourceGraphicType, nativeSourceGraphicType;
        public bool sourceEnabled, sourceActive, sourceReferenceVerified, blockerPresent, blockerUnique,
            blockerEnabledMatches, surfaceReferenceVerified, surfaceOwnerMatches, surfaceOwnedMatches,
            surfaceEnabledMatches, surfaceRaycastMatches, surfaceImplementationVerified, clearAlphaMeshVerified,
            sourceNoDrawStateVerified, surfaceEnabledActual, surfaceRaycastActual,
            sourceSerializedActive, sourceSerializedActiveVerified, sourceHierarchyActiveMatchesExpected,
            surfaceMeshDeferred, verified;
        public bool sourceActiveSelf, sourceActiveInHierarchy;
        public Color surfaceColor;
        public int surfaceMeshAlphaMin, surfaceMeshAlphaMax;
        public int surfaceMeshVertexCount, surfaceMeshIndexCount, surfaceMaterialCount;
    }
    [Serializable] public sealed class ProxySortFieldReadback
    {
        public string sourceId, node, nativeId, actualSourceId, actualNativeId;
        public float sourceSortOrder, actualSortOrder;
        public bool enabledInSource, actualEnabledInSource, identityPresent, identityComponentEnabled, verified;
    }
    [Serializable] public sealed class ProxySortRootValueReadback
    {
        public string sourceId, node, nativeId, actualSourceId, actualNativeId;
        public bool enabledInSource, actualEnabledInSource, identityPresent, identityComponentEnabled, verified;
    }
    [Serializable] public sealed class ProxyMaskReadback
    {
        public string sourceId, sourceNode, nativeMaskType;
        public int sourceMaskType;
        public bool inverted, enabled, sourceTransformVerified, verified;
        public bool maskPresent, identityPresent, graphicPresent, graphicTypeMatches, sourceIdentityMatches,
            sourceFieldsMatches, maskEnabledMatches, maskGraphicHidden, graphicEnabledMatches, graphicRaycastDisabled,
            sourceMaterialMatches, resolvedSourceMaterialMatches, sourceEffectMatches, alphaThresholdMatches,
            invertedCanvasMatches;
        public string[] failedChecks;
        public float alphaThreshold;
    }
    [Serializable] public sealed class ProxySourceMaskIdentityReadback
    {
        public string sourceId, nativeId, node, nativeMaskType, graphicType, sourceFieldsJson,
            spriteFrameUuid, sourceMaterialId, resolvedSourceMaterialId, sourceEffectId, sourceEffectName,
            sourceEffectDocumentSha256, unityMaskMaterialGuid, unityMaskShaderPath, unityMaskShaderSha256,
            sourceActivityStage;
        public int sourceMaskType;
        public bool sourceEnabled, sourceInverted, sourceActiveSelfExpected, sourceActiveExpected,
            actualMaskEnabled, actualGraphicEnabled, actualRaycastTarget, sourceActiveSelf, sourceActiveInHierarchy,
            sourceSerializedActive, sourceSerializedActiveVerified, sourceHierarchyActiveMatchesExpected,
            sourceReferenceVerified, sourceIdentityVerified, sourceGraphicTypeVerified,
            sourceMaskFieldsVerified, sourceRenderContextDeferred, helperMaskReadbackVerified, verified;
        public float sourceAlphaThreshold, actualAlphaThreshold;
    }

    public static class UnityStaticSortQueueProxy
    {
        static string HashBytes(byte[] bytes)
        {
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        }
        static string HashText(string value) => HashBytes(Encoding.UTF8.GetBytes(value ?? ""));

        static string MaterialFingerprint(Material material)
        {
            if (material == null) return null;
            var shader = material.shader;
            if (shader == null || !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(shader, out var shaderGuid, out long shaderFileId) ||
                string.IsNullOrEmpty(shaderGuid))
                throw new InvalidOperationException("STATIC_SORT_PROXY_SHADER_GUID_MISSING: " + material.name);
            var sb = new StringBuilder();
            sb.Append("shader=").Append(shaderGuid).Append(':').Append(shaderFileId)
              .Append("|queue=").Append(material.renderQueue)
              .Append("|instancing=").Append(material.enableInstancing)
              .Append("|doubleSidedGI=").Append(material.doubleSidedGI)
              .Append("|giFlags=").Append((int)material.globalIlluminationFlags)
              .Append("|keywords=").Append(string.Join(",", material.shaderKeywords.OrderBy(x => x, StringComparer.Ordinal)));
            for (var index = 0; index < shader.GetPropertyCount(); index++)
            {
                var name = shader.GetPropertyName(index);
                var type = shader.GetPropertyType(index);
                sb.Append("|p=").Append(name).Append(':').Append(type).Append('=');
                if (type == UnityEngine.Rendering.ShaderPropertyType.Color)
                {
                    var value = material.GetColor(name);
                    sb.Append(value.r.ToString("R", CultureInfo.InvariantCulture)).Append(',')
                      .Append(value.g.ToString("R", CultureInfo.InvariantCulture)).Append(',')
                      .Append(value.b.ToString("R", CultureInfo.InvariantCulture)).Append(',')
                      .Append(value.a.ToString("R", CultureInfo.InvariantCulture));
                }
                else if (type == UnityEngine.Rendering.ShaderPropertyType.Vector)
                    AppendVector(sb, material.GetVector(name));
                else if (type == UnityEngine.Rendering.ShaderPropertyType.Texture)
                {
                    var texture = material.GetTexture(name);
                    if (texture == null) sb.Append("null");
                    else if (texture == Texture2D.whiteTexture) sb.Append("builtin:white");
                    else
                    {
                        if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(texture, out var textureGuid, out long textureFileId) ||
                            string.IsNullOrEmpty(textureGuid))
                            throw new InvalidOperationException("STATIC_SORT_PROXY_MATERIAL_TEXTURE_GUID_MISSING: " + name);
                        sb.Append(textureGuid).Append(':').Append(textureFileId);
                    }
                    var scale = material.GetTextureScale(name); var offset = material.GetTextureOffset(name);
                    sb.Append(";scale=").Append(scale.x.ToString("R", CultureInfo.InvariantCulture)).Append(',')
                      .Append(scale.y.ToString("R", CultureInfo.InvariantCulture))
                      .Append(";offset=").Append(offset.x.ToString("R", CultureInfo.InvariantCulture)).Append(',')
                      .Append(offset.y.ToString("R", CultureInfo.InvariantCulture));
                }
                else if (type == UnityEngine.Rendering.ShaderPropertyType.Int)
                    sb.Append(material.GetInt(name));
                else
                    sb.Append(material.GetFloat(name).ToString("R", CultureInfo.InvariantCulture));
            }
            return HashText(sb.ToString());
        }

        static void AppendVector(StringBuilder sb, Vector4 value)
        {
            sb.Append(value.x.ToString("R", CultureInfo.InvariantCulture)).Append(',')
              .Append(value.y.ToString("R", CultureInfo.InvariantCulture)).Append(',')
              .Append(value.z.ToString("R", CultureInfo.InvariantCulture)).Append(',')
              .Append(value.w.ToString("R", CultureInfo.InvariantCulture)).Append(';');
        }

        static int UvDimension(Mesh mesh, int channel)
        {
            if (mesh == null || channel < 0 || channel > 7) return 0;
            var attribute = (VertexAttribute)((int)VertexAttribute.TexCoord0 + channel);
            return mesh.HasVertexAttribute(attribute) ? mesh.GetVertexAttributeDimension(attribute) : 0;
        }

        static int[] UvChannelVertexCounts(Mesh mesh)
        {
            var result = new int[8];
            if (mesh == null) return result;
            for (var channel = 0; channel < result.Length; channel++)
            {
                var values = new List<Vector4>(); mesh.GetUVs(channel, values);
                result[channel] = values.Count;
            }
            return result;
        }

        static int[] UvChannelDimensions(Mesh mesh)
        {
            var result = new int[8];
            if (mesh == null) return result;
            for (var channel = 0; channel < result.Length; channel++) result[channel] = UvDimension(mesh, channel);
            return result;
        }

        static bool HasMalformedUvChannels(Mesh mesh)
        {
            if (mesh == null) return true;
            var counts = UvChannelVertexCounts(mesh);
            var dimensions = UvChannelDimensions(mesh);
            for (var channel = 0; channel < counts.Length; channel++)
            {
                if (counts[channel] != 0 && counts[channel] != mesh.vertexCount) return true;
                if (counts[channel] != 0 && (dimensions[channel] < 2 || dimensions[channel] > 4)) return true;
            }
            return false;
        }

        static void CopyUvChannels(Mesh source, Mesh target)
        {
            for (var channel = 0; channel < 8; channel++)
            {
                switch (UvDimension(source, channel))
                {
                    case 0: break;
                    case 2:
                    {
                        var values = new List<Vector2>(); source.GetUVs(channel, values);
                        if (values.Count != source.vertexCount) throw new InvalidOperationException("STATIC_SORT_PROXY_UV_CHANNEL_VERTEX_COUNT_MISMATCH:" + channel);
                        target.SetUVs(channel, values); break;
                    }
                    case 3:
                    {
                        var values = new List<Vector3>(); source.GetUVs(channel, values);
                        if (values.Count != source.vertexCount) throw new InvalidOperationException("STATIC_SORT_PROXY_UV_CHANNEL_VERTEX_COUNT_MISMATCH:" + channel);
                        target.SetUVs(channel, values); break;
                    }
                    case 4:
                    {
                        var values = new List<Vector4>(); source.GetUVs(channel, values);
                        if (values.Count != source.vertexCount) throw new InvalidOperationException("STATIC_SORT_PROXY_UV_CHANNEL_VERTEX_COUNT_MISMATCH:" + channel);
                        target.SetUVs(channel, values); break;
                    }
                    default: throw new InvalidOperationException("STATIC_SORT_PROXY_UV_DIMENSION_UNSUPPORTED:" + channel);
                }
            }
        }

        static string MeshFingerprint(Mesh mesh, int submesh)
        {
            var sb = new StringBuilder();
            sb.Append(mesh.vertexCount).Append('|').Append(mesh.subMeshCount).Append('|').Append(submesh).Append('|');
            foreach (var p in mesh.vertices) AppendVector(sb, p);
            foreach (var c in mesh.colors32) sb.Append(c.r).Append(',').Append(c.g).Append(',').Append(c.b).Append(',').Append(c.a).Append(';');
            for (var channel = 0; channel < 8; channel++)
            {
                var values = new List<Vector4>(); mesh.GetUVs(channel, values);
                sb.Append('#').Append(channel).Append('/').Append(UvDimension(mesh, channel)).Append(':');
                foreach (var uv in values) AppendVector(sb, uv);
            }
            foreach (var n in mesh.normals) AppendVector(sb, n);
            foreach (var t in mesh.tangents) AppendVector(sb, t);
            foreach (var index in mesh.GetTriangles(submesh)) sb.Append(index).Append(',');
            return HashText(sb.ToString());
        }

        static bool TransformedMeshMatches(Mesh source, int submesh, Transform sourceTransform,
            Transform proxyTransform, Mesh persistedProxy, string sourceComponentId,
            out string expectedFingerprint, out string actualFingerprint)
        {
            expectedFingerprint = null;
            actualFingerprint = persistedProxy == null ? null : MeshFingerprint(persistedProxy, 0);
            if (source == null || sourceTransform == null || proxyTransform == null || persistedProxy == null ||
                submesh < 0 || submesh >= source.subMeshCount) return false;
            var expected = SnapshotSubmesh(source, submesh, sourceTransform, proxyTransform, sourceComponentId);
            expectedFingerprint = MeshFingerprint(expected, 0);
            var matches = expectedFingerprint == actualFingerprint;
            UnityEngine.Object.DestroyImmediate(expected);
            return matches;
        }

        sealed class TransformedMeshDiagnostics
        {
            public float maxWorldVertexError, maxWorldNormalError, maxWorldTangentError;
            public string uvDiagnostic;
            public int maxWorldVertexIndex = -1;
            public Vector3 maxSourceLocalVertex, maxSourceWorldVertex, maxProxyLocalVertex, maxProxyWorldVertex;
            public bool topologyMatches, uvMatches, colorsMatch, normalsMatch, tangentsMatch;
        }

        sealed class PendingSpineGraphicProxy
        {
            public ProxyRendererSpec row;
            public GameObject sourceNode;
            public Graphic sourceGraphic, sourceOwnerGraphic;
            public Transform parent;
            public int queueIndex;
        }

        static TransformedMeshDiagnostics MeasureTransformedMesh(Mesh source, int submesh, Transform sourceTransform,
            Transform proxyTransform, Mesh persistedProxy)
        {
            var result = new TransformedMeshDiagnostics();
            if (source == null || persistedProxy == null || sourceTransform == null || proxyTransform == null ||
                submesh < 0 || submesh >= source.subMeshCount) return result;
            var sourceVertices = source.vertices; var proxyVertices = persistedProxy.vertices;
            var sourceMatrix = sourceTransform.localToWorldMatrix;
            var proxyMatrix = proxyTransform.localToWorldMatrix;
            if (sourceVertices.Length == proxyVertices.Length)
            {
                result.maxWorldVertexError = 0f;
                for (var index = 0; index < sourceVertices.Length; index++)
                {
                    var sourceWorld = sourceMatrix.MultiplyPoint3x4(sourceVertices[index]);
                    var proxyWorld = proxyMatrix.MultiplyPoint3x4(proxyVertices[index]);
                    var error = Vector3.Distance(sourceWorld, proxyWorld);
                    if (error > result.maxWorldVertexError)
                    {
                        result.maxWorldVertexError = error;
                        result.maxWorldVertexIndex = index;
                        result.maxSourceLocalVertex = sourceVertices[index];
                        result.maxSourceWorldVertex = sourceWorld;
                        result.maxProxyLocalVertex = proxyVertices[index];
                        result.maxProxyWorldVertex = proxyWorld;
                    }
                }
            }
            result.topologyMatches = sourceVertices.Length == proxyVertices.Length && persistedProxy.subMeshCount == 1 &&
                source.GetTriangles(submesh).SequenceEqual(persistedProxy.GetTriangles(0));
            result.uvMatches = true;
            for (var channel = 0; channel < 8; channel++)
            {
                if (UvDimension(source, channel) != UvDimension(persistedProxy, channel))
                {
                    result.uvMatches = false;
                    result.uvDiagnostic = "channel=" + channel + ";dimension=" + UvDimension(source, channel) +
                        "/" + UvDimension(persistedProxy, channel);
                    break;
                }
                var sourceUvs = new List<Vector4>(); var proxyUvs = new List<Vector4>();
                source.GetUVs(channel, sourceUvs); persistedProxy.GetUVs(channel, proxyUvs);
                if (sourceUvs.Count != proxyUvs.Count)
                {
                    result.uvMatches = false;
                    result.uvDiagnostic = "channel=" + channel + ";vertexCount=" + sourceUvs.Count + "/" + proxyUvs.Count;
                    break;
                }
                var mismatch = -1;
                for (var index = 0; index < sourceUvs.Count; index++)
                    if (sourceUvs[index] != proxyUvs[index]) { mismatch = index; break; }
                if (mismatch >= 0)
                {
                    var expectedUv = sourceUvs[mismatch]; var actualUv = proxyUvs[mismatch];
                    result.uvMatches = false;
                    result.uvDiagnostic = "channel=" + channel + ";vertex=" + mismatch + ";source=" +
                        UvValueDiagnostic(expectedUv) + ";proxy=" + UvValueDiagnostic(actualUv);
                    break;
                }
            }
            var sourceColors = source.colors32; var proxyColors = persistedProxy.colors32;
            result.colorsMatch = sourceColors.SequenceEqual(proxyColors);
            var sourceNormals = source.normals; var proxyNormals = persistedProxy.normals;
            result.normalsMatch = sourceNormals.Length == proxyNormals.Length;
            if (result.normalsMatch && sourceNormals.Length == sourceVertices.Length)
            {
                result.maxWorldNormalError = 0f;
                var sourceNormalMatrix = Mathf.Abs(sourceMatrix.determinant) > 1e-8f ? sourceMatrix.inverse.transpose : Matrix4x4.identity;
                var proxyNormalMatrix = Mathf.Abs(proxyMatrix.determinant) > 1e-8f ? proxyMatrix.inverse.transpose : Matrix4x4.identity;
                for (var index = 0; index < sourceNormals.Length; index++)
                {
                    var sourceWorld = sourceNormalMatrix.MultiplyVector(sourceNormals[index]).normalized;
                    var proxyWorld = proxyNormalMatrix.MultiplyVector(proxyNormals[index]).normalized;
                    result.maxWorldNormalError = Mathf.Max(result.maxWorldNormalError, Vector3.Distance(sourceWorld, proxyWorld));
                }
                result.normalsMatch &= result.maxWorldNormalError <= 1e-5f;
            }
            var sourceTangents = source.tangents; var proxyTangents = persistedProxy.tangents;
            result.tangentsMatch = sourceTangents.Length == proxyTangents.Length;
            if (result.tangentsMatch && sourceTangents.Length == sourceVertices.Length)
            {
                result.maxWorldTangentError = 0f;
                for (var index = 0; index < sourceTangents.Length; index++)
                {
                    var sourceTangent = sourceTangents[index]; var proxyTangent = proxyTangents[index];
                    var sourceWorld = sourceMatrix.MultiplyVector(new Vector3(sourceTangent.x, sourceTangent.y, sourceTangent.z)).normalized;
                    var proxyWorld = proxyMatrix.MultiplyVector(new Vector3(proxyTangent.x, proxyTangent.y, proxyTangent.z)).normalized;
                    result.maxWorldTangentError = Mathf.Max(result.maxWorldTangentError, Vector3.Distance(sourceWorld, proxyWorld));
                    var sourceHand = sourceTangent.w * Math.Sign(sourceMatrix.determinant);
                    var proxyHand = proxyTangent.w * Math.Sign(proxyMatrix.determinant);
                    if (sourceHand != proxyHand) result.tangentsMatch = false;
                }
                result.tangentsMatch &= result.maxWorldTangentError <= 1e-5f;
            }
            return result;
        }

        static string UvValueDiagnostic(Vector4 value)
        {
            return value.x.ToString("R", CultureInfo.InvariantCulture) + "," +
                value.y.ToString("R", CultureInfo.InvariantCulture) + "," +
                value.z.ToString("R", CultureInfo.InvariantCulture) + "," +
                value.w.ToString("R", CultureInfo.InvariantCulture);
        }

        static string VertexErrorDiagnostic(TransformedMeshDiagnostics diagnostics)
        {
            if (diagnostics == null || diagnostics.maxWorldVertexIndex < 0) return String.Empty;
            string V(Vector3 value) => value.x.ToString("R", CultureInfo.InvariantCulture) + "," +
                value.y.ToString("R", CultureInfo.InvariantCulture) + "," + value.z.ToString("R", CultureInfo.InvariantCulture);
            return "index=" + diagnostics.maxWorldVertexIndex + ";sourceLocal=" + V(diagnostics.maxSourceLocalVertex) +
                ";sourceWorld=" + V(diagnostics.maxSourceWorldVertex) + ";proxyLocal=" + V(diagnostics.maxProxyLocalVertex) +
                ";proxyWorld=" + V(diagnostics.maxProxyWorldVertex) + ";distance=" +
                diagnostics.maxWorldVertexError.ToString("R", CultureInfo.InvariantCulture);
        }

        static string AssetGuid(UnityEngine.Object value, out long fileId)
        {
            string guid;
            return AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value, out guid, out fileId) ? guid : null;
        }
        static string TextureAssetGuid(Texture value)
        {
            if (value == null) return null;
            if (value == Texture2D.whiteTexture) return "builtin:white";
            long fileId; return AssetGuid(value, out fileId);
        }

        /// <summary>True only for the generated proxy root owned by this exact source root.</summary>
        public static bool IsGeneratedSortProxyRoot(Transform child)
        {
            if (child == null || child.parent == null) return false;
            var marker = child.GetComponent<NativeStaticSortQueueProxyMarker>();
            if (marker == null || marker.kind != "root" || marker.sourceRootOwner == null ||
                marker.sourceRootOwner.transform != child.parent) return false;
            var presenter = child.GetComponent<NativeStaticSortQueueProxyPresenter>();
            return presenter != null && presenter.sourceRoot == marker.sourceRootOwner &&
                presenter.proxyRoot == child.gameObject && presenter.sourceRootId == marker.sourceNode;
        }

        static List<GameObject> NestedProxyRoots(GameObject sourceRoot)
        {
            var roots = new List<GameObject>();
            foreach (var marker in sourceRoot.GetComponentsInChildren<NativeStaticSortQueueProxyMarker>(true))
            {
                if (marker == null || marker.kind != "root" || marker.sourceRootOwner == sourceRoot) continue;
                if (!IsGeneratedSortProxyRoot(marker.transform)) continue;
                if (marker.sourceRootOwner == null || !marker.sourceRootOwner.transform.IsChildOf(sourceRoot.transform))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_NESTED_ROOT_OWNER_OUTSIDE_SOURCE_SCOPE: " + marker.sourceNode);
                roots.Add(marker.gameObject);
            }
            return roots.Distinct().ToList();
        }

        /// <summary>
        /// Temporarily removes nested presenters from the mesh capture path.
        /// Their OnDisable restores the source CanvasRenderer cull values; the
        /// generated proxy roots are then hidden while source geometry is
        /// rebuilt and copied by the outer queue.
        /// </summary>
        sealed class NestedProxyCaptureScope : IDisposable
        {
            readonly GameObject[] roots;
            readonly NativeStaticSortQueueProxyPresenter[] presenters;
            readonly bool[] rootActiveBefore, presenterEnabledBefore;
            bool committed, disposed;

            public NestedProxyCaptureScope(IReadOnlyList<GameObject> nestedRoots)
            {
                roots = (nestedRoots ?? Array.Empty<GameObject>()).ToArray();
                presenters = roots.Select(root => root == null ? null : root.GetComponent<NativeStaticSortQueueProxyPresenter>()).ToArray();
                rootActiveBefore = roots.Select(root => root != null && root.activeSelf).ToArray();
                presenterEnabledBefore = presenters.Select(presenter => presenter != null && presenter.enabled).ToArray();
                for (var i = 0; i < roots.Length; i++)
                    if (roots[i] == null || presenters[i] == null || !IsGeneratedSortProxyRoot(roots[i].transform))
                        throw new InvalidOperationException("STATIC_SORT_PROXY_NESTED_CAPTURE_IDENTITY_INVALID: " + i);

                // Disable presenters first so their source cull state is restored
                // before any source Graphic mesh is rebuilt.
                for (var i = 0; i < presenters.Length; i++)
                    if (presenters[i].enabled) presenters[i].enabled = false;
                for (var i = 0; i < roots.Length; i++)
                    if (roots[i].activeSelf) roots[i].SetActive(false);
            }

            public void Commit()
            {
                if (disposed) throw new ObjectDisposedException(nameof(NestedProxyCaptureScope));
                committed = true;
                // Preserve the authored component enabled state while leaving
                // each generated nested branch inactive under the outer queue.
                for (var i = 0; i < presenters.Length; i++)
                    if (presenters[i] != null) presenters[i].enabled = presenterEnabledBefore[i];
            }

            public void Dispose()
            {
                if (disposed) return;
                disposed = true;
                if (committed) return;
                // On failure, restore the exact pre-capture active/enabled
                // state. Enabling a presenter after its root is active restores
                // its normal source suppression behavior.
                for (var i = 0; i < roots.Length; i++)
                    if (roots[i] != null) roots[i].SetActive(rootActiveBefore[i]);
                for (var i = 0; i < presenters.Length; i++)
                    if (presenters[i] != null) presenters[i].enabled = presenterEnabledBefore[i];
            }
        }

        static void EnsureSourceGraphicMeshReady(Graphic graphic)
        {
            if (graphic == null || graphic.canvasRenderer == null) return;
            // Spine's registered RawImage children carry a custom mesh emitted
            // by SkeletonGraphic. Rebuilding them as ordinary RawImages would
            // replace that mesh with a quad, so only the SDK static-pose path
            // may prepare those renderers.
            var parentGraphic = graphic.transform.parent == null ? null : graphic.transform.parent.GetComponent<Graphic>();
            if (parentGraphic != null && IsSpineCanvasSubmesh(graphic.gameObject, parentGraphic)) return;
            // TMP generated submesh objects are emitted by the owning text
            // component's ForceMeshUpdate and likewise must keep that mesh.
            if (parentGraphic != null && parentGraphic.GetType().FullName == "TMPro.TextMeshProUGUI" &&
                IsGeneratedTextSubmesh(graphic.gameObject)) return;
            if (graphic.GetType().FullName == "Spine.Unity.SkeletonGraphic") return;
            if (graphic is TMPro.TMP_Text tmp)
            {
                tmp.ForceMeshUpdate(true, false);
                return;
            }
            var renderer = graphic.canvasRenderer;
            var cullBefore = renderer.cull;
            try
            {
                // A ScrollRect/Mask can cull an otherwise enabled Image before
                // its first Canvas mesh is built. Rebuild its real Sprite mesh
                // uncullled for capture, then restore the exact authored cull
                // state so viewport clipping remains intact.
                if (graphic is Image && cullBefore) renderer.cull = false;
                graphic.SetAllDirty();
                graphic.Rebuild(CanvasUpdate.PreRender);
            }
            finally
            {
                if (graphic is Image) renderer.cull = cullBefore;
            }
            if (graphic is Image && renderer.cull != cullBefore)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_IMAGE_CULL_RESTORE_FAILED: " + graphic.name);
        }

        static void EnsureLoadedRegularImageMeshReady(Image image)
        {
            if (image == null || image.sprite == null || !image.enabled || !image.gameObject.activeInHierarchy ||
                image.canvasRenderer == null) return;
            var renderer = image.canvasRenderer;
            var cullBefore = renderer.cull;
            try
            {
                // An initialized Presenter culls the authored source. Temporarily
                // remove that renderer cull only while Unity rebuilds the native
                // Image mesh, then restore the exact cull state in all cases.
                if (cullBefore) renderer.cull = false;
                EnsureSourceGraphicMeshReady(image);
            }
            finally
            {
                renderer.cull = cullBefore;
            }
            if (renderer.cull != cullBefore)
                throw new InvalidOperationException("STATIC_SORT_PROXY_IMAGE_SOURCE_CULL_RESTORE_FAILED: " + image.name);
        }

        static Dictionary<string, OwnerFontStyleDescriptor> PrepareSourceGeometryForCapture(ProxyQueueSpec spec,
            IDictionary<string, GameObject> sourceNodes,
            GameObject sourceRoot)
        {
            var ownerStyles = new Dictionary<string, OwnerFontStyleDescriptor>(StringComparer.Ordinal);
            if ((spec.renderers ?? Array.Empty<ProxyRendererSpec>()).Any(row => row != null && row.sourceType == "sp.Skeleton"))
                InitializeSourceSpineStaticPose(sourceRoot);
            Canvas.ForceUpdateCanvases();
            foreach (var row in spec.renderers ?? Array.Empty<ProxyRendererSpec>())
            {
                if (row == null || !String.Equals(row.sourceType, "cc.Sprite", StringComparison.Ordinal) &&
                    !String.Equals(row.sourceType, "cc.Label", StringComparison.Ordinal) &&
                    !String.Equals(row.sourceType, "cc.RichText", StringComparison.Ordinal)) continue;
                if (!sourceNodes.TryGetValue(row.node, out var sourceNode) || sourceNode == null) continue;
                var graphic = sourceNode.GetComponent<Graphic>();
                if (graphic == null || graphic.GetType().FullName != row.expectedGraphicType)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_GRAPHIC_MISMATCH_DURING_CAPTURE_PREPARE: " +
                        row.sourceComponentId + ";node=" + row.node);
                if (row.sourceType == "cc.Label" || row.sourceType == "cc.RichText")
                {
                    if (!row.sourceEnabled || !row.sourceActive || row.sourceTextEmpty) continue;
                    var textOwner = sourceNode.GetComponent<TMPro.TMP_Text>();
                    if (textOwner == null)
                        throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SOURCE_OWNER_MISSING: " + row.sourceComponentId);
                    if (!UnityStaticSortTextSource.PrepareSource(textOwner, row.sourceComponentId, out var textDiagnostic))
                        throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SOURCE_PREPARE_FAILED: " + row.sourceComponentId +
                            ";diagnostic=" + textDiagnostic);
                    var outline = sourceNode.GetComponent<NativeStaticTextOutline>();
                    if (outline != null)
                    {
                        var ownerStylePath = OwnerFontMaterialPath(spec.meshAssetFolder, row.sourceComponentId,
                            textOwner, outline);
                        if (!UnityStaticSortTextSource.CaptureOwnerFontMaterial(textOwner, row.sourceComponentId,
                                ownerStylePath, out var persistentOwnerMaterial, out var ownerStyle, out var ownerStyleDiagnostic) ||
                            persistentOwnerMaterial == null || ownerStyle == null)
                            throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_OWNER_STYLE_CAPTURE_FAILED: " +
                                row.sourceComponentId + ";diagnostic=" + ownerStyleDiagnostic);
                        ownerStyles.Add(row.sourceComponentId, ownerStyle);
                        if (!UnityStaticSortTextSource.PrepareSource(textOwner, row.sourceComponentId, out textDiagnostic))
                            throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_OWNER_STYLE_REPREPARE_FAILED: " +
                                row.sourceComponentId + ";diagnostic=" + textDiagnostic);
                    }
                }
                else EnsureSourceGraphicMeshReady(graphic);
            }
            Canvas.ForceUpdateCanvases();
            return ownerStyles;
        }

        static List<TextSlotBinding> CaptureAndRebindTextSlots(ProxyQueueSpec spec, ProxyRendererSpec row,
            TMPro.TMP_Text owner, OwnerFontStyleDescriptor ownerStyle,
            out NativeStaticSortTextSlotEnumeration slotEnumeration)
        {
            slotEnumeration = null;
            if (owner == null) throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_OWNER_MISSING: " + row.sourceComponentId);
            if (!UnityStaticSortTextSource.GetCurrentSlots(owner, row.sourceComponentId, out var initialSlots,
                    out slotEnumeration, out var initialDiagnostic))
                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_CAPTURE_FAILED: " + row.sourceComponentId +
                    ";diagnostic=" + initialDiagnostic);
            ValidateTextSlotEnumeration(slotEnumeration, row.sourceComponentId);
            if (initialSlots.Count == 0)
            {
                if (!IsExactEmptyTextSource(row, owner) ||
                    slotEnumeration.rows.Any(evidence => evidence.disposition != "empty-placeholder"))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_DENOMINATOR_EMPTY: " + row.sourceComponentId +
                        ";sourceTextEmpty=" + row.sourceTextEmpty + ";sourceText=" + (row.sourceText ?? "<null>") +
                        ";targetText=" + (owner.text ?? "<null>") + ";enumeration=" + slotEnumeration.evidenceSha256);
                return initialSlots;
            }
            var slotIds = initialSlots.Select(binding => binding.materialSlot).OrderBy(slot => slot).ToArray();
            if (slotIds.Distinct().Count() != slotIds.Length)
                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_DENOMINATOR_DUPLICATED: " + row.sourceComponentId);
            var captureProofs = new Dictionary<int, TextSlotBinding>();
            foreach (var slot in slotIds)
            {
                if (!UnityStaticSortTextSource.GetCurrentSlots(owner, row.sourceComponentId, out var liveSlots,
                        out var liveEnumeration, out var liveDiagnostic))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_REFRESH_FAILED: " + row.sourceComponentId +
                        ";slot=" + slot + ";diagnostic=" + liveDiagnostic);
                if (!SameTextSlotEnumeration(slotEnumeration, liveEnumeration))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_EVIDENCE_CHANGED_DURING_CAPTURE: " +
                        row.sourceComponentId + ";slot=" + slot);
                var live = liveSlots.SingleOrDefault(binding => binding.materialSlot == slot);
                if (live == null)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_DISAPPEARED_DURING_CAPTURE: " + row.sourceComponentId +
                        ";slot=" + slot);
                live.ownerStyle = ownerStyle;
                var materialPath = spec.meshAssetFolder.TrimEnd('/') + "/TMPTextMaterial_" +
                    HashText(row.sourceComponentId + "|" + slot + "|" +
                        (live.transientFallbackFingerprint ?? live.sourceMaterialFingerprint ?? String.Empty)).Substring(0, 24) + ".mat";
                if (!UnityStaticSortTextSource.CaptureFallbackMaterial(live, materialPath, out var captureDiagnostic))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_FALLBACK_MATERIAL_CAPTURE_FAILED: " + row.sourceComponentId +
                        ";slot=" + slot + ";diagnostic=" + captureDiagnostic);
                captureProofs.Add(slot, live);
                // The registered primary/fallback material must take effect in
                // TMP's current mesh before another slot is resolved.
                if (!UnityStaticSortTextSource.PrepareSource(owner, row.sourceComponentId, out var prepareDiagnostic))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_REPREPARE_FAILED: " + row.sourceComponentId +
                        ";slot=" + slot + ";diagnostic=" + prepareDiagnostic);
                Canvas.ForceUpdateCanvases();
            }

            if (!UnityStaticSortTextSource.PrepareSource(owner, row.sourceComponentId, out var finalPrepareDiagnostic))
                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_FINAL_REPREPARE_FAILED: " + row.sourceComponentId +
                    ";diagnostic=" + finalPrepareDiagnostic);
            Canvas.ForceUpdateCanvases();
            if (!UnityStaticSortTextSource.GetCurrentSlots(owner, row.sourceComponentId, out var finalSlots,
                    out var finalEnumeration, out var finalDiagnostic))
                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_FINAL_SLOTS_FAILED: " + row.sourceComponentId +
                    ";diagnostic=" + finalDiagnostic);
            if (!SameTextSlotEnumeration(slotEnumeration, finalEnumeration))
                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_EVIDENCE_CHANGED_AFTER_REGISTRATION: " + row.sourceComponentId);
            if (!slotIds.SequenceEqual(finalSlots.Select(binding => binding.materialSlot).OrderBy(slot => slot)))
                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_DENOMINATOR_CHANGED_AFTER_REGISTRATION: " + row.sourceComponentId);
            var result = new List<TextSlotBinding>();
            foreach (var slot in slotIds)
            {
                var current = finalSlots.Single(binding => binding.materialSlot == slot);
                if (!UnityStaticSortTextSource.RebindCapturedSlot(captureProofs[slot], owner, current.sourceGraphic,
                        out var rebound, out var rebindDiagnostic))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_REBIND_FAILED: " + row.sourceComponentId +
                        ";slot=" + slot + ";diagnostic=" + rebindDiagnostic);
                if (!SameTextSlotEnumeration(finalEnumeration, current.textSlotEnumeration) ||
                    rebound.sourceTextSha256 != finalEnumeration.sourceTextSha256)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_REBIND_ENUMERATION_MISMATCH: " +
                        row.sourceComponentId + ";slot=" + slot);
                // Rebind resolves a fresh slot object; carry the enumeration
                // captured by that final pass onto the exact rebound binding
                // that Attach persists.
                rebound.textSlotEnumeration = finalEnumeration;
                rebound.ownerStyle = ownerStyle;
                result.Add(rebound);
            }
            return result;
        }

        static void ValidateTextSlotEnumeration(NativeStaticSortTextSlotEnumeration enumeration, string sourceComponentId)
        {
            if (enumeration == null || enumeration.verified != true || enumeration.sourceComponentId != sourceComponentId ||
                String.IsNullOrEmpty(enumeration.sourceTextSha256) || String.IsNullOrEmpty(enumeration.evidenceSha256) ||
                enumeration.slotCount < 1 || enumeration.rows == null || enumeration.rows.Length != enumeration.slotCount ||
                enumeration.rows.Select(row => row == null ? -1 : row.slot).Distinct().Count() != enumeration.slotCount ||
                !enumeration.rows.Select(row => row.slot).OrderBy(slot => slot).SequenceEqual(Enumerable.Range(0, enumeration.slotCount)))
                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_ENUMERATION_INVALID: " + sourceComponentId);
            foreach (var row in enumeration.rows)
            {
                if (row == null || String.IsNullOrEmpty(row.evidenceSha256) ||
                    (row.disposition != "drawable" && row.disposition != "empty-placeholder"))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_EVIDENCE_ROW_INVALID: " + sourceComponentId);
                if (row.disposition == "empty-placeholder" &&
                    // TextInfo may retain newline/control-character references in a nondrawing slot.
                    // Keep that count in the hashed row; only visible refs or actual triangles invalidate no-draw.
                    (row.characterReferences < 0 || row.visibleCharacterReferences != 0 ||
                     row.textInfoNondegenerateTriangleCount != 0 || row.canvasNondegenerateTriangleCount != 0))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_PLACEHOLDER_HAS_DRAWABLE_EVIDENCE: " +
                        sourceComponentId + ";slot=" + row.slot);
            }
            if (enumeration.rows.Any(row => row.disposition == "empty-placeholder" && row.slot != 0) ||
                enumeration.rows.Count(row => row.disposition == "empty-placeholder") > 1)
                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_PLACEHOLDER_SLOT_NOT_OWNER_SLOT0: " + sourceComponentId);
        }

        static bool SameTextSlotEnumeration(NativeStaticSortTextSlotEnumeration left,
            NativeStaticSortTextSlotEnumeration right)
        {
            return left != null && right != null && left.sourceComponentId == right.sourceComponentId &&
                left.sourceTextSha256 == right.sourceTextSha256 && left.slotCount == right.slotCount &&
                left.evidenceSha256 == right.evidenceSha256;
        }

        static bool IsExactEmptyTextSource(ProxyRendererSpec row, TMPro.TMP_Text owner)
        {
            return row != null && owner != null && row.sourceTextEmpty &&
                String.IsNullOrEmpty(row.sourceText) && String.IsNullOrEmpty(row.nativeTextExpectation) &&
                String.IsNullOrEmpty(owner.text) && String.IsNullOrEmpty(owner.GetParsedText());
        }

        static bool AttachEmptyTextSlotProof(ProxyRendererSpec row, TMPro.TMP_Text owner, GameObject carrier,
            out string diagnostic)
        {
            diagnostic = null;
            if (!IsExactEmptyTextSource(row, owner) || carrier == null)
            {
                diagnostic = "exact-empty-source-text-contract-failed";
                return false;
            }
            if (!UnityStaticSortTextSource.PrepareSource(owner, row.sourceComponentId, out diagnostic)) return false;
            Canvas.ForceUpdateCanvases();
            if (!UnityStaticSortTextSource.GetCurrentSlots(owner, row.sourceComponentId, out var slots,
                    out var enumeration, out diagnostic)) return false;
            if (slots.Count != 0 || enumeration == null || enumeration.rows == null || enumeration.rows.Length == 0 ||
                enumeration.rows.Any(evidence => evidence == null || evidence.disposition != "empty-placeholder"))
            {
                diagnostic = "source-empty-text-has-drawable-or-unclassified-slot:" +
                    (enumeration == null ? "null" : enumeration.evidenceSha256 ?? "<no-hash>");
                return false;
            }
            return UnityStaticSortTextSource.AttachEmptyTextSlotEnumeration(carrier, owner, row.sourceComponentId,
                enumeration, out diagnostic);
        }

        static string OwnerFontMaterialPath(string folder, string sourceComponentId, TMPro.TMP_Text owner,
            NativeStaticTextOutline outline)
        {
            if (String.IsNullOrWhiteSpace(folder) || owner == null || owner.font == null || outline == null ||
                !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(owner.font, out var fontGuid, out long fontLocalId) ||
                String.IsNullOrWhiteSpace(fontGuid) || fontLocalId == 0)
                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_OWNER_STYLE_PATH_INPUT_INVALID: " + sourceComponentId);
            var color = outline.SourceOutlineColor;
            var profile = sourceComponentId + "|" + fontGuid + ":" + fontLocalId + "|" +
                owner.fontSize.ToString("R", CultureInfo.InvariantCulture) + "|" +
                outline.SourceOutlineWidth.ToString("R", CultureInfo.InvariantCulture) + "|" +
                color.r.ToString("R", CultureInfo.InvariantCulture) + "," + color.g.ToString("R", CultureInfo.InvariantCulture) + "," +
                color.b.ToString("R", CultureInfo.InvariantCulture) + "," + color.a.ToString("R", CultureInfo.InvariantCulture);
            return folder.TrimEnd('/') + "/TMPOwnerMaterial_" + HashText(profile).Substring(0, 24) + ".mat";
        }

        static void InitializeSourceSpineStaticPose(GameObject sourceRoot)
        {
            // The hook is emitted only when the pinned Spine integration is
            // part of this target. Reflection keeps the optional non-Spine
            // Editor assembly compilable without adding a hard SDK dependency.
            var initialize = typeof(MonkeyImporter).GetMethod("InitializeSavedStaticSpine",
                BindingFlags.Static | BindingFlags.NonPublic);
            if (initialize == null)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_STATIC_POSE_INITIALIZER_MISSING");
            try { initialize.Invoke(null, new object[] { sourceRoot }); }
            catch (TargetInvocationException error)
            {
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_STATIC_POSE_INITIALIZATION_FAILED",
                    error.InnerException ?? error);
            }
        }

        static void FinalizeSourceSpineStaticMesh(IEnumerable<Graphic> sourceOwners, string phase)
        {
            var owners = (sourceOwners ?? Array.Empty<Graphic>()).Where(owner => owner != null).Distinct().ToArray();
            if (owners.Length == 0) throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_FINALIZE_OWNERS_MISSING:" + phase);
            var method = typeof(MonkeyImporter).GetMethod("FinalizeSavedStaticSortSpineMeshes",
                BindingFlags.Static | BindingFlags.NonPublic);
            if (method == null)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_FINALIZE_SDK_HELPER_MISSING:" + phase);
            try { method.Invoke(null, new object[] { owners }); }
            catch (TargetInvocationException error)
            {
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_FINALIZE_FAILED:" + phase,
                    error.InnerException ?? error);
            }
        }

        static bool SourceTreeMatchesProxy(ProxyQueueSpec spec, IDictionary<string, GameObject> nodes,
            bool loadedReadback, out string diagnostic)
        {
            diagnostic = null;
            var rows = spec.sourceChildOrder ?? Array.Empty<ProxySourceChildrenSpec>();
            var active = spec.sourceNodeActive ?? Array.Empty<ProxySourceActiveSpec>();
            if (rows.Length == 0 || rows.Any(row => row == null || string.IsNullOrEmpty(row.node)) ||
                rows.Select(row => row.node).Distinct().Count() != rows.Length ||
                active.Any(row => row == null || string.IsNullOrEmpty(row.node)) ||
                active.Select(row => row.node).Distinct().Count() != active.Length ||
                active.Length != rows.Length || !active.Select(row => row.node).ToHashSet().SetEquals(rows.Select(row => row.node)) ||
                !rows.Any(row => row.node == spec.rootScope))
            {
                diagnostic = "sourceTreeContractInvalid;root=" + spec.rootScope + ";rows=" + rows.Length + ";active=" + active.Length;
                return false;
            }
            var sourceIds = new HashSet<string>(rows.Select(row => row.node));
            foreach (var row in rows)
            {
                if (!nodes.TryGetValue(row.node, out var parent) || parent == null)
                {
                    diagnostic = "sourceNodeMissing;node=" + row.node;
                    return false;
                }
                var expected = row.children ?? Array.Empty<string>();
                if (expected.Any(string.IsNullOrEmpty) || expected.Distinct().Count() != expected.Length ||
                    expected.Any(id => !sourceIds.Contains(id)))
                {
                    diagnostic = "sourceChildOrderContractInvalid;parent=" + row.node + ";expected=" +
                        String.Join(",", expected);
                    return false;
                }
                var observed = new List<string>();
                var observedPaths = new List<string>();
                foreach (Transform child in parent.transform)
                {
                    if (IsGeneratedSortProxyRoot(child)) continue;
                    var sourceChild = nodes.FirstOrDefault(entry => entry.Value != null && entry.Value.transform == child).Key;
                    if (sourceChild != null)
                    {
                        observed.Add(sourceChild);
                        observedPaths.Add(sourceChild + "(" + child.name + ")");
                    }
                    else if (IsGeneratedTextSubmesh(child.gameObject))
                        observedPaths.Add("<typed-generated-TMP:" + child.name + ">");
                    else if (TryGetGeneratedSpineSourceIdentity(spec, nodes, child, out var spineOwnerNodeId,
                        out var spineOwnerSpec, loadedReadback, out _))
                        observedPaths.Add("<typed-generated-Spine:" + spineOwnerNodeId + ":" +
                            spineOwnerSpec.sourceComponentId + ":" + child.name + ">");
                    else
                    {
                        var componentNames = child.GetComponents<Component>().Where(component => component != null)
                            .Select(component => component.GetType().FullName).ToArray();
                        diagnostic = "unmappedSourceChild;parent=" + row.node + "(" + parent.name + ");child=" + child.name +
                            ";path=" + TransformPath(child) + ";type=" + child.GetType().FullName + ";components=" +
                            String.Join(",", componentNames) + ";activeSelf=" + child.gameObject.activeSelf +
                            ";activeHierarchy=" + child.gameObject.activeInHierarchy;
                        return false;
                    }
                }
                if (!observed.SequenceEqual(expected))
                {
                    diagnostic = "childOrderMismatch;parent=" + row.node + "(" + parent.name + ");expected=" +
                        String.Join(",", expected) + ";observed=" + String.Join(",", observed) +
                        ";observedPaths=" + String.Join("|", observedPaths);
                    return false;
                }
            }
            return true;
        }

        static void SortGeneratedProxyChildrenBySourceEvent(ProxyQueueSpec spec, Transform proxyRoot)
        {
            if (spec == null || proxyRoot == null)
                throw new InvalidOperationException("STATIC_SORT_PROXY_EVENT_SORT_INPUT_MISSING");
            var rendererOrder = new Dictionary<string, int>(StringComparer.Ordinal);
            var maskOrder = new Dictionary<string, int>(StringComparer.Ordinal);
            var events = spec.drawEvents ?? Array.Empty<ProxyDrawEventSpec>();
            for (var index = 0; index < events.Length; index++)
            {
                var row = events[index];
                if (row == null) continue;
                if (row.kind == "renderer" && !rendererOrder.ContainsKey(row.sourceComponentId))
                    rendererOrder.Add(row.sourceComponentId, index);
                else if (row.kind == "maskEnter" && !maskOrder.ContainsKey(row.node))
                    maskOrder.Add(row.node, index);
            }
            void Visit(Transform parent)
            {
                var children = new List<(Transform transform, int eventIndex, int queueIndex, int originalIndex)>();
                for (var index = 0; index < parent.childCount; index++)
                {
                    var child = parent.GetChild(index);
                    var marker = child.GetComponent<NativeStaticSortQueueProxyMarker>();
                    if (marker == null || marker.kind == "root")
                        throw new InvalidOperationException("STATIC_SORT_PROXY_EVENT_SORT_UNCLASSIFIED_CHILD: parent=" +
                            TransformPath(parent) + ";child=" + child.name + ";type=" + child.GetType().FullName);
                    int eventIndex;
                    if (marker.kind == "retainedNonDraw")
                    {
                        var nonDrawMatches = (spec.nonDrawRenderers ?? Array.Empty<ProxyRendererSpec>())
                            .Where(row => row != null && row.sourceComponentId == marker.sourceComponentId).ToArray();
                        if (nonDrawMatches.Length != 1 || rendererOrder.ContainsKey(marker.sourceComponentId) ||
                            marker.queueIndex != -1 || marker.sourceNode != nonDrawMatches[0].node ||
                            marker.sourceType != nonDrawMatches[0].sourceType || marker.sourceEnabled != nonDrawMatches[0].sourceEnabled ||
                            marker.sourceActive != nonDrawMatches[0].sourceActive || marker.enabled ||
                            String.IsNullOrEmpty(marker.noDrawReason))
                            throw new InvalidOperationException("STATIC_SORT_PROXY_EVENT_SORT_RETAINED_NONDRAW_IDENTITY_INVALID: source=" +
                                marker.sourceComponentId + ";matchingSpecs=" + nonDrawMatches.Length +
                                ";drawEventPresent=" + rendererOrder.ContainsKey(marker.sourceComponentId) +
                                ";path=" + TransformPath(child));
                        // Retained typed source evidence is not a drawable queue
                        // event. Keep the marker in the generated hierarchy,
                        // after draw events, and preserve its source identity.
                        eventIndex = Int32.MaxValue;
                    }
                    else if (marker.kind == "renderer" || marker.kind == "emptyRenderer")
                    {
                        if (!rendererOrder.TryGetValue(marker.sourceComponentId, out eventIndex))
                            throw new InvalidOperationException("STATIC_SORT_PROXY_EVENT_SORT_RENDERER_EVENT_MISSING: source=" +
                                marker.sourceComponentId + ";path=" + TransformPath(child));
                    }
                    else if (marker.kind == "mask")
                    {
                        if (!maskOrder.TryGetValue(marker.sourceNode, out eventIndex))
                            throw new InvalidOperationException("STATIC_SORT_PROXY_EVENT_SORT_MASK_EVENT_MISSING: node=" +
                                marker.sourceNode + ";path=" + TransformPath(child));
                    }
                    else throw new InvalidOperationException("STATIC_SORT_PROXY_EVENT_SORT_MARKER_KIND_UNSUPPORTED: " + marker.kind);
                    var proxyGraphic = child.GetComponent<NativeStaticSortQueueProxyGraphic>();
                    var queueIndex = proxyGraphic != null ? proxyGraphic.queueIndex : marker.queueIndex;
                    children.Add((child, eventIndex, queueIndex, index));
                }
                var sorted = children.OrderBy(row => row.eventIndex).ThenBy(row => row.queueIndex)
                    .ThenBy(row => row.originalIndex).ToArray();
                for (var index = 0; index < sorted.Length; index++)
                    sorted[index].transform.SetSiblingIndex(index);
                foreach (var child in sorted) Visit(child.transform);
            }
            Visit(proxyRoot);
        }

        static Mesh SnapshotSubmesh(Mesh source, int submesh, Transform sourceTransform, Transform proxyTransform,
            string sourceComponentId)
        {
            var copy = new Mesh { name = source.name + "_StaticQueue" };
            if (source.vertexCount > 65535) copy.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            var transformsIdentical = MatrixExactlyEquals(sourceTransform.localToWorldMatrix, proxyTransform.localToWorldMatrix);
            var sameLinearBasis = LinearBasisExactlyEquals(sourceTransform.localToWorldMatrix, proxyTransform.localToWorldMatrix);
            var singularPlane = Mathf.Abs(sourceTransform.localToWorldMatrix.determinant) <= 1e-8f ||
                Mathf.Abs(proxyTransform.localToWorldMatrix.determinant) <= 1e-8f;
            var sourceVertices = source.vertices;
            var sourceAndProxyShareObservedUiPlane = sourceVertices.All(vertex => vertex.z == 0f) &&
                ObservableUiPlaneExactlyEquals(sourceTransform.localToWorldMatrix, proxyTransform.localToWorldMatrix);
            // Canvas renders local mesh vertices through the persisted world
            // matrices. Use that same matrix path for both the source and the
            // proxy; recursive TransformPoint calls can round differently for
            // equivalent hierarchies and spuriously move large UI vertices.
            var sourceMatrix = sourceTransform.localToWorldMatrix;
            var proxyMatrix = proxyTransform.localToWorldMatrix;
            // If only the origin differs, keep source-local vertices. Re-solving
            // enormous Spine vertices through an equal basis can move them by a
            // whole float ULP even when the origin delta itself is subpixel; the
            // final loaded-matrix world-vertex gate remains authoritative.
            var positions = MatrixExactlyEquals(sourceMatrix, proxyMatrix) || sameLinearBasis || sourceAndProxyShareObservedUiPlane
                ? sourceVertices : sourceVertices.Select(vertex =>
            {
                var desiredWorld = sourceMatrix.MultiplyPoint3x4(vertex);
                if (Vector3.Distance(proxyMatrix.MultiplyPoint3x4(vertex), desiredWorld) <= .001f)
                    return vertex;
                var initialLocal = InverseTransformPointForUiPlane(proxyTransform, desiredWorld, sourceComponentId);
                return UnityStaticSortVertexPrecision.ImproveInitialLocalPoint(proxyMatrix.MultiplyPoint3x4,
                    proxyMatrix, desiredWorld, initialLocal, out _);
            }).ToArray();
            copy.vertices = positions;
            if (source.colors32.Length == source.vertexCount) copy.colors32 = source.colors32;
            CopyUvChannels(source, copy);
            var normals = source.normals;
            if (normals.Length == source.vertexCount)
            {
                if (transformsIdentical || sameLinearBasis || singularPlane) copy.normals = normals;
                else
                {
                    var sourceNormalMatrix = sourceTransform.localToWorldMatrix.inverse.transpose;
                    var proxyNormalMatrix = proxyTransform.localToWorldMatrix.transpose;
                    copy.normals = normals.Select(n => proxyNormalMatrix.MultiplyVector(sourceNormalMatrix.MultiplyVector(n)).normalized).ToArray();
                }
            }
            var tangents = source.tangents;
            if (tangents.Length == source.vertexCount)
            {
                if (transformsIdentical || sameLinearBasis || singularPlane) copy.tangents = tangents;
                else
                {
                    var proxyInverse = proxyMatrix.inverse;
                    copy.tangents = tangents.Select(t => {
                        var direction = proxyInverse.MultiplyVector(sourceMatrix.MultiplyVector(new Vector3(t.x, t.y, t.z))).normalized;
                        var handedness = Mathf.Sign((proxyInverse * sourceMatrix).determinant);
                        return new Vector4(direction.x, direction.y, direction.z, t.w * handedness);
                    }).ToArray();
                }
            }
            copy.subMeshCount = 1;
            copy.SetTriangles(source.GetTriangles(submesh), 0, false);
            copy.RecalculateBounds();
            return copy;
        }

        static Mesh PersistMesh(Mesh source, int submesh, Transform sourceTransform, Transform proxyTransform,
            string sourceComponentId, int submeshIndex, string folder, out string sourceSha,
            out string contentSha, out string guid)
        {
            sourceSha = MeshFingerprint(source, submesh);
            var snapshot = SnapshotSubmesh(source, submesh, sourceTransform, proxyTransform, sourceComponentId);
            contentSha = MeshFingerprint(snapshot, 0);
            var key = HashText(sourceComponentId + "|" + submeshIndex + "|" + sourceSha + "|" + contentSha).Substring(0, 24);
            var path = folder.TrimEnd('/') + "/QueueMesh_" + key + ".asset";
            var existing = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (existing != null)
            {
                // Existing generated assets are immutable unless byte-level
                // vertex/channel/index data matches this source snapshot.
                var existingHash = MeshFingerprint(existing, 0);
                if (existingHash != contentSha)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_MESH_ASSET_COLLISION: " + path);
                long existingId; guid = AssetGuid(existing, out existingId);
                return existing;
            }
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            AssetDatabase.CreateAsset(snapshot, path);
            long local; guid = AssetGuid(snapshot, out local);
            if (guid == null) throw new InvalidOperationException("STATIC_SORT_PROXY_MESH_NOT_PERSISTENT: " + sourceComponentId);
            return snapshot;
        }

        static bool WorldRectMatches(RectTransform source, RectTransform proxy, float tolerance = .001f)
        {
            var a = new Vector3[4]; var b = new Vector3[4];
            source.GetWorldCorners(a); proxy.GetWorldCorners(b);
            for (var i = 0; i < 4; i++) if ((a[i] - b[i]).sqrMagnitude > tolerance * tolerance) return false;
            return true;
        }

        static string WorldCornerEvidence(RectTransform source, RectTransform proxy)
        {
            var sourceCorners = new Vector3[4]; var proxyCorners = new Vector3[4];
            source.GetWorldCorners(sourceCorners); proxy.GetWorldCorners(proxyCorners);
            return "sourceCorners=[" + string.Join(";", sourceCorners.Select(value => value.ToString("R"))) +"];proxyCorners=[" +
                string.Join(";", proxyCorners.Select(value => value.ToString("R"))) + "]";
        }

        static float[] MatrixEvidence(Matrix4x4 matrix)
        {
            var values = new float[16];
            for (var row = 0; row < 4; row++)
                for (var column = 0; column < 4; column++) values[row * 4 + column] = matrix[row, column];
            return values;
        }

        static string MatrixRoundTripEvidence(Matrix4x4 matrix)
        {
            var values = new List<string>();
            for (var row = 0; row < 4; row++)
                for (var column = 0; column < 4; column++)
                    values.Add(matrix[row, column].ToString("R", CultureInfo.InvariantCulture));
            return String.Join(",", values);
        }

        static string MatrixDifferenceEvidence(Matrix4x4 source, Matrix4x4 proxy)
        {
            var maxDifference = 0f; var maxRow = -1; var maxColumn = -1; var firstMismatch = -1;
            for (var row = 0; row < 4; row++)
                for (var column = 0; column < 4; column++)
                {
                    var difference = Mathf.Abs(source[row, column] - proxy[row, column]);
                    if (difference != 0f && firstMismatch < 0) firstMismatch = row * 4 + column;
                    if (difference > maxDifference)
                    { maxDifference = difference; maxRow = row; maxColumn = column; }
                }
            return "firstIndex=" + firstMismatch + ";maxRow=" + maxRow + ";maxColumn=" + maxColumn +
                ";source=" + (maxRow < 0 ? "0" : source[maxRow, maxColumn].ToString("R", CultureInfo.InvariantCulture)) +
                ";proxy=" + (maxRow < 0 ? "0" : proxy[maxRow, maxColumn].ToString("R", CultureInfo.InvariantCulture)) +
                ";maxAbsDifference=" + maxDifference.ToString("R", CultureInfo.InvariantCulture);
        }

        static string RectCopyDiagnostic(RectTransform source, RectTransform proxy, Transform parent, string sourceId,
            string selectedPath, bool basisEqual, bool correctionAttempted, bool correctionSucceeded,
            Vector3 localCorrection, float correctionResidual)
        {
            var sourceParent = source == null ? null : source.parent;
            var diagnostic = new ProxyRectCopyCaptureDiagnostic { sourceComponentId = sourceId, selectedPath = selectedPath,
                sourceParentPath = sourceParent == null ? null : TransformPath(sourceParent),
                targetParentPath = parent == null ? null : TransformPath(parent),
                sourceParentMatrix = sourceParent == null ? Array.Empty<float>() : MatrixEvidence(sourceParent.localToWorldMatrix),
                targetParentMatrix = parent == null ? Array.Empty<float>() : MatrixEvidence(parent.localToWorldMatrix),
                sourceLocalToWorldMatrix = source == null ? Array.Empty<float>() : MatrixEvidence(source.localToWorldMatrix),
                finalProxyLocalToWorldMatrix = proxy == null ? Array.Empty<float>() : MatrixEvidence(proxy.localToWorldMatrix),
                sourceLocalPosition = source == null ? Vector3.zero : source.localPosition,
                sourceLocalRotation = source == null ? Quaternion.identity : source.localRotation,
                sourceLocalScale = source == null ? Vector3.one : source.localScale,
                linearBasisExactlyEqual = basisEqual, originCorrectionAttempted = correctionAttempted,
                originCorrectionSucceeded = correctionSucceeded, originCorrectionLocal = localCorrection,
                originCorrectionResidual = correctionResidual,
                finalProxyLocalPosition = proxy == null ? Vector3.zero : proxy.localPosition,
                finalProxyLocalRotation = proxy == null ? Quaternion.identity : proxy.localRotation,
                finalProxyLocalScale = proxy == null ? Vector3.one : proxy.localScale,
                sourcePivotWorld = source == null ? Vector3.zero : source.position,
                finalProxyPivotWorld = proxy == null ? Vector3.zero : proxy.position,
                pivotWorldError = source == null || proxy == null ? Single.PositiveInfinity : Vector3.Distance(source.position, proxy.position),
                finalWorldRectMatches = source != null && proxy != null && WorldRectMatches(source, proxy) };
            return JsonUtility.ToJson(diagnostic);
        }

        static bool MatrixNear(Matrix4x4 a, Matrix4x4 b, float tolerance)
        {
            for (var row = 0; row < 4; row++)
                for (var column = 0; column < 4; column++)
                    if (Mathf.Abs(a[row, column] - b[row, column]) > tolerance) return false;
            return true;
        }

        static bool MatrixExactlyEquals(Matrix4x4 a, Matrix4x4 b)
        {
            for (var row = 0; row < 4; row++)
                for (var column = 0; column < 4; column++)
                    if (a[row, column] != b[row, column]) return false;
            return true;
        }

        static bool ObservableUiPlaneExactlyEquals(Matrix4x4 a, Matrix4x4 b)
        {
            // RectTransform UI meshes are authored on local z=0. If the full
            // X/Y basis and world translation match exactly, differences on
            // the unobserved local-Z column cannot move these vertices.
            foreach (var column in new[] { 0, 1, 3 })
                for (var row = 0; row < 3; row++)
                    if (a[row, column] != b[row, column]) return false;
            return true;
        }

        static bool IsFinite(Vector3 value)
        {
            return !float.IsNaN(value.x) && !float.IsInfinity(value.x) &&
                !float.IsNaN(value.y) && !float.IsInfinity(value.y) &&
                !float.IsNaN(value.z) && !float.IsInfinity(value.z);
        }

        static bool IsFinite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);

        static bool LinearBasisExactlyEquals(Matrix4x4 a, Matrix4x4 b)
        {
            for (var row = 0; row < 3; row++)
                for (var column = 0; column < 3; column++)
                    if (a[row, column] != b[row, column]) return false;
            return true;
        }

        static bool TrySolveBasisTranslation(Transform target, Vector3 worldDelta, out Vector3 localDelta)
        {
            localDelta = Vector3.zero;
            if (target == null) return false;
            var matrix = target.localToWorldMatrix;
            var matrixDeterminant = matrix.determinant;
            if (IsFinite(matrixDeterminant) && matrixDeterminant != 0f)
            {
                localDelta = matrix.inverse.MultiplyVector(worldDelta);
                // A full-rank basis represents every finite world delta.
                // The resulting RectTransform corners are checked by the
                // caller's existing strict WorldRectMatches gate.
                return IsFinite(localDelta);
            }
            var axes = new[] { (Vector3)matrix.GetColumn(0), (Vector3)matrix.GetColumn(1), (Vector3)matrix.GetColumn(2) };
            var lengths = axes.Select(axis => Vector3.Dot(axis, axis)).ToArray();
            var maxLength = Mathf.Max(lengths);
            if (maxLength == 0f) return worldDelta == Vector3.zero;
            var bestDeterminant = 0f; var bestI = -1; var bestJ = -1;
            for (var i = 0; i < 3; i++)
                for (var j = i + 1; j < 3; j++)
                {
                    var determinant = Vector3.Cross(axes[i], axes[j]).sqrMagnitude;
                    if (determinant > bestDeterminant) { bestDeterminant = determinant; bestI = i; bestJ = j; }
                }
            if (bestDeterminant > maxLength * maxLength * 1e-12f)
            {
                var axisI = axes[bestI]; var axisJ = axes[bestJ];
                var ii = lengths[bestI]; var ij = Vector3.Dot(axisI, axisJ); var jj = lengths[bestJ];
                var determinant = ii * jj - ij * ij;
                var di = Vector3.Dot(axisI, worldDelta); var dj = Vector3.Dot(axisJ, worldDelta);
                localDelta[bestI] = (di * jj - dj * ij) / determinant;
                localDelta[bestJ] = (dj * ii - di * ij) / determinant;
            }
            else
            {
                var axisIndex = Array.IndexOf(lengths, maxLength);
                localDelta[axisIndex] = Vector3.Dot(axes[axisIndex], worldDelta) / maxLength;
            }
            return (matrix.MultiplyVector(localDelta) - worldDelta).sqrMagnitude <= 1e-12f;
        }

        static bool TrySolvePlaneCoordinates(Transform plane, Vector3 worldPoint, out Vector2 coordinates,
            out Vector3 reconstructed)
        {
            coordinates = Vector2.zero; reconstructed = Vector3.zero;
            if (plane == null) return false;
            var matrix = plane.localToWorldMatrix;
            var origin = matrix.GetColumn(3);
            var axisX = (Vector3)matrix.GetColumn(0); var axisY = (Vector3)matrix.GetColumn(1);
            var delta = worldPoint - (Vector3)origin;
            var xx = Vector3.Dot(axisX, axisX); var xy = Vector3.Dot(axisX, axisY); var yy = Vector3.Dot(axisY, axisY);
            var determinant = xx * yy - xy * xy;
            var scale = Mathf.Max(xx, yy);
            if (scale == 0f)
            {
                reconstructed = (Vector3)origin;
                return true;
            }
            if (determinant > scale * scale * 1e-12f)
            {
                var dx = Vector3.Dot(axisX, delta); var dy = Vector3.Dot(axisY, delta);
                coordinates.x = (dx * yy - dy * xy) / determinant;
                coordinates.y = (dy * xx - dx * xy) / determinant;
            }
            else if (xx >= yy)
                coordinates.x = Vector3.Dot(axisX, delta) / xx;
            else
                coordinates.y = Vector3.Dot(axisY, delta) / yy;
            reconstructed = (Vector3)origin + axisX * coordinates.x + axisY * coordinates.y;
            return true;
        }

        static bool TrySolvePlaneVector(Transform plane, Vector3 worldVector, out Vector2 coordinates,
            out Vector3 reconstructed)
        {
            coordinates = Vector2.zero; reconstructed = Vector3.zero;
            if (plane == null) return false;
            var matrix = plane.localToWorldMatrix;
            var axisX = (Vector3)matrix.GetColumn(0); var axisY = (Vector3)matrix.GetColumn(1);
            var xx = Vector3.Dot(axisX, axisX); var xy = Vector3.Dot(axisX, axisY); var yy = Vector3.Dot(axisY, axisY);
            var determinant = xx * yy - xy * xy;
            var scale = Mathf.Max(xx, yy);
            if (scale == 0f) return worldVector == Vector3.zero;
            if (determinant > scale * scale * 1e-12f)
            {
                var dx = Vector3.Dot(axisX, worldVector); var dy = Vector3.Dot(axisY, worldVector);
                coordinates.x = (dx * yy - dy * xy) / determinant;
                coordinates.y = (dy * xx - dx * xy) / determinant;
            }
            else if (xx >= yy)
                coordinates.x = Vector3.Dot(axisX, worldVector) / xx;
            else
                coordinates.y = Vector3.Dot(axisY, worldVector) / yy;
            reconstructed = axisX * coordinates.x + axisY * coordinates.y;
            return true;
        }

        static Vector3 InverseTransformPointForUiPlane(Transform target, Vector3 worldPoint, string sourceId)
        {
            var targetMatrix = target.localToWorldMatrix;
            if (Mathf.Abs(targetMatrix.determinant) > 1e-8f) return targetMatrix.inverse.MultiplyPoint3x4(worldPoint);
            var solved = TrySolvePlaneCoordinates(target, worldPoint, out var coordinates, out var reconstructed);
            var planeDistance = solved ? Vector3.Distance(reconstructed, worldPoint) : Single.PositiveInfinity;
            if (!solved || planeDistance > .001f)
                throw new InvalidOperationException("STATIC_SORT_PROXY_VERTEX_OUTSIDE_SINGULAR_UI_PLANE:source=" +
                    (sourceId ?? "<unknown>") + ";planeDistance=" + planeDistance.ToString("R", CultureInfo.InvariantCulture) +
                    ";world=" + worldPoint.ToString("R") + ";reconstructed=" + reconstructed.ToString("R") +
                    ";matrix=" + MatrixRoundTripEvidence(target.localToWorldMatrix));
            // Local Z is unobservable when the native parent has a zero depth
            // scale. Preserve exact world positions in its invertible UI plane.
            return new Vector3(coordinates.x, coordinates.y, 0f);
        }

        static Vector3 PerpendicularUnit(Vector3 direction)
        {
            if (direction.sqrMagnitude == 0f) return Vector3.up;
            var unit = direction.normalized;
            var seed = Mathf.Abs(Vector3.Dot(unit, Vector3.up)) < .9f ? Vector3.up : Vector3.right;
            return Vector3.Cross(unit, seed).normalized;
        }

        static void CopyWorldRectOnSingularPlane(RectTransform source, RectTransform proxy, Transform parent, string sourceId)
        {
            if (!TrySolvePlaneCoordinates(parent, source.position, out var position, out var reconstructedPosition) ||
                (reconstructedPosition - source.position).sqrMagnitude > 1e-6f)
                throw new InvalidOperationException("STATIC_SORT_PROXY_PIVOT_OUTSIDE_SINGULAR_UI_PLANE: " + sourceId);
            var sourceRight = source.TransformVector(Vector3.right);
            var sourceUp = source.TransformVector(Vector3.up);
            if (!TrySolvePlaneVector(parent, sourceRight, out var right, out var reconstructedRight) ||
                !TrySolvePlaneVector(parent, sourceUp, out var up, out var reconstructedUp) ||
                (reconstructedRight - sourceRight).sqrMagnitude > 1e-8f ||
                (reconstructedUp - sourceUp).sqrMagnitude > 1e-8f)
                throw new InvalidOperationException("STATIC_SORT_PROXY_BASIS_OUTSIDE_SINGULAR_UI_PLANE: " + sourceId);
            var sx = right.magnitude; var upLength = up.magnitude;
            float angle; float signedX; float signedY;
            if (sx == 0f && upLength == 0f)
            {
                angle = 0f; signedX = 0f; signedY = 0f;
            }
            else if (sx == 0f)
            {
                angle = Mathf.Atan2(up.y, up.x) - Mathf.PI * .5f;
                signedX = 0f; signedY = upLength;
                var rotatedUp = new Vector2(-Mathf.Sin(angle), Mathf.Cos(angle));
                if ((up - rotatedUp * signedY).sqrMagnitude > 1e-8f)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_2D_SHEAR_UNREPRESENTABLE: " + sourceId);
            }
            else if (upLength == 0f)
            {
                angle = Mathf.Atan2(right.y, right.x);
                signedX = sx; signedY = 0f;
                var rotatedRight = new Vector2(Mathf.Cos(angle), Mathf.Sin(angle));
                if ((right - rotatedRight * signedX).sqrMagnitude > 1e-8f)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_2D_SHEAR_UNREPRESENTABLE: " + sourceId);
            }
            else
            {
                angle = Mathf.Atan2(right.y, right.x);
                signedX = sx;
                var rotatedUp = new Vector2(-Mathf.Sin(angle), Mathf.Cos(angle));
                signedY = Vector2.Dot(up, rotatedUp);
                if (Mathf.Abs(signedY) <= 1e-8f || (up - rotatedUp * signedY).sqrMagnitude > 1e-8f)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_2D_SHEAR_UNREPRESENTABLE: " + sourceId);
            }
            var rotation = Quaternion.Euler(0f, 0f, angle * Mathf.Rad2Deg);
            proxy.localPosition = new Vector3(position.x, position.y, 0f);
            proxy.localRotation = rotation;
            proxy.localScale = new Vector3(signedX, signedY, 1f);
            var matrix = parent.localToWorldMatrix * Matrix4x4.TRS(proxy.localPosition, proxy.localRotation, proxy.localScale);
            var reconstructedProxyRight = matrix.MultiplyVector(Vector3.right);
            var reconstructedProxyUp = matrix.MultiplyVector(Vector3.up);
            if ((reconstructedProxyRight - sourceRight).sqrMagnitude > 1e-8f ||
                (reconstructedProxyUp - sourceUp).sqrMagnitude > 1e-8f ||
                ((Vector3)matrix.GetColumn(3) - source.position).sqrMagnitude > 1e-6f)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SINGULAR_2D_TRS_NOT_EXACT: " + sourceId);
            if (!WorldRectMatches(source, proxy))
                throw new InvalidOperationException("STATIC_SORT_PROXY_TRANSFORM_NOT_EXACT: " + sourceId + " (" + WorldCornerEvidence(source, proxy) + ")");
        }

        static void CopyWorldRect(RectTransform source, RectTransform proxy, Transform parent, string sourceId)
        {
            CopyWorldRect(source, proxy, parent, sourceId, out _);
        }

        static void CopyWorldRect(RectTransform source, RectTransform proxy, Transform parent, string sourceId,
            out string captureDiagnostic)
        {
            captureDiagnostic = null;
            proxy.SetParent(parent, false);
            if (source.transform == parent)
            {
                // A proxy root copied directly under its source root already
                // shares the exact world matrix. Keep the local identity so
                // matrix inversion/recomposition cannot introduce a 1-ULP
                // scale error into every captured source vertex.
                proxy.anchorMin = source.pivot; proxy.anchorMax = source.pivot;
                proxy.pivot = source.pivot; proxy.sizeDelta = source.rect.size;
                proxy.localPosition = Vector3.zero; proxy.localRotation = Quaternion.identity;
                proxy.localScale = Vector3.one;
                if (!WorldRectMatches(source, proxy))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_IDENTITY_CHILD_RECT_NOT_EXACT: " +
                        sourceId + " (" + WorldCornerEvidence(source, proxy) + ")");
                captureDiagnostic = RectCopyDiagnostic(source, proxy, parent, sourceId, "same-transform-identity-child",
                    source.parent != null && LinearBasisExactlyEquals(source.parent.localToWorldMatrix, parent.localToWorldMatrix),
                    false, false, Vector3.zero, 0f);
                return;
            }
            var basisEqual = source.parent != null && LinearBasisExactlyEquals(source.parent.localToWorldMatrix, parent.localToWorldMatrix);
            var correctionAttempted = false; var correctionSucceeded = false;
            var localCorrection = Vector3.zero; var correctionResidual = 0f;
            if (basisEqual)
            {
                var parentOriginDelta = source.parent.position - parent.position;
                correctionAttempted = true;
                correctionSucceeded = TrySolveBasisTranslation(parent, parentOriginDelta, out localCorrection);
                correctionResidual = (parent.localToWorldMatrix.MultiplyVector(localCorrection) - parentOriginDelta).magnitude;
                if (correctionSucceeded)
                {
                    // Parent RectTransform dimensions can differ even when
                    // their world 3x3 bases match. Fixed anchors preserve the
                    // captured source rect size instead of reapplying source
                    // stretch anchors to the destination parent's size.
                    var fixedAnchor = parent is RectTransform parentRect ? parentRect.pivot : new Vector2(.5f, .5f);
                    proxy.anchorMin = fixedAnchor; proxy.anchorMax = fixedAnchor;
                    proxy.pivot = source.pivot; proxy.sizeDelta = source.rect.size;
                    proxy.localRotation = source.localRotation; proxy.localScale = source.localScale;
                    proxy.localPosition = source.localPosition + localCorrection;
                    // RectTransform anchor bookkeeping can make the position
                    // reconstructed from localPosition differ by one parent
                    // matrix ULP. For a full-rank destination, set the actual
                    // world pivot from the source after establishing the exact
                    // rect shape; the strict world-corner gate below remains
                    // authoritative. Singular UI planes keep the rank-aware
                    // solved local position above.
                    var parentMatrix = parent.localToWorldMatrix;
                    if (IsFinite(parentMatrix.determinant) && parentMatrix.determinant != 0f)
                        proxy.position = source.position;
                    if (!WorldRectMatches(source, proxy))
                        throw new InvalidOperationException("STATIC_SORT_PROXY_EQUAL_BASIS_RECT_NOT_EXACT: " +
                            sourceId + " (" + WorldCornerEvidence(source, proxy) + ")");
                    captureDiagnostic = RectCopyDiagnostic(source, proxy, parent, sourceId, "equal-linear-basis-origin-correction",
                        basisEqual, correctionAttempted, correctionSucceeded, localCorrection, correctionResidual);
                    return;
                }
                // A matching basis is useful only when its observable span
                // can represent the parent-origin delta. In a rank-deficient
                // case, keep the established strict inverse/plane path below
                // rather than rejecting a rect that path can still represent.
            }
            proxy.anchorMin = new Vector2(.5f, .5f); proxy.anchorMax = new Vector2(.5f, .5f);
            proxy.pivot = source.pivot; proxy.sizeDelta = source.rect.size;
            if (Mathf.Abs(parent.localToWorldMatrix.determinant) <= 1e-8f)
            {
                CopyWorldRectOnSingularPlane(source, proxy, parent, sourceId);
                captureDiagnostic = RectCopyDiagnostic(source, proxy, parent, sourceId, "rank-aware-singular-parent-plane",
                    basisEqual, correctionAttempted, correctionSucceeded, localCorrection, correctionResidual);
                return;
            }
            var commonAncestorRelativeAvailable = UnityStaticSortVertexPrecision.TryGetRelativeMatrixFromCommonAncestor(
                source, parent, out var local);
            var transformPath = commonAncestorRelativeAvailable ? "common-ancestor-trs" : "matrix-trs-decomposition";
            if (!commonAncestorRelativeAvailable)
                local = parent.worldToLocalMatrix * source.localToWorldMatrix;
            var x = (Vector3)local.GetColumn(0); var y = (Vector3)local.GetColumn(1); var z = (Vector3)local.GetColumn(2);
            var sx = x.magnitude; var sy = y.magnitude;
            var preferredRotation = Quaternion.Inverse(parent.rotation) * source.rotation;
            Quaternion rotation;
            Vector3 right, up, forward;
            if (sx == 0f && sy == 0f)
            {
                var preferredForward = preferredRotation * Vector3.forward;
                forward = z.sqrMagnitude == 0f ? preferredForward : z.normalized;
                up = preferredRotation * Vector3.up;
                right = preferredRotation * Vector3.right;
                rotation = z.sqrMagnitude == 0f || Vector3.Dot(preferredForward, forward) > .99999f
                    ? preferredRotation : Quaternion.LookRotation(forward, PerpendicularUnit(forward));
            }
            else if (sx == 0f)
            {
                up = y / sy;
                var preferredUp = preferredRotation * Vector3.up;
                var preferredForward = preferredRotation * Vector3.forward;
                forward = z.sqrMagnitude == 0f ? preferredForward : z.normalized;
                var preferredBasisMatches = Vector3.Dot(preferredUp, up) > .99999f &&
                    (z.sqrMagnitude == 0f || Vector3.Dot(preferredForward, forward) > .99999f);
                if (preferredBasisMatches)
                {
                    rotation = preferredRotation;
                    right = preferredRotation * Vector3.right;
                }
                else
                {
                    if (z.sqrMagnitude == 0f) forward = PerpendicularUnit(up);
                    if (Mathf.Abs(Vector3.Dot(up, forward)) > 1e-5f)
                        throw new InvalidOperationException("STATIC_SORT_PROXY_TRANSFORM_SHEAR_UNREPRESENTABLE: " + sourceId);
                    right = Vector3.Cross(up, forward).normalized;
                    rotation = Quaternion.LookRotation(forward, up);
                }
            }
            else if (sy == 0f)
            {
                right = x / sx;
                var preferredRight = preferredRotation * Vector3.right;
                var preferredForward = preferredRotation * Vector3.forward;
                forward = z.sqrMagnitude == 0f ? preferredForward : z.normalized;
                var preferredBasisMatches = Vector3.Dot(preferredRight, right) > .99999f &&
                    (z.sqrMagnitude == 0f || Vector3.Dot(preferredForward, forward) > .99999f);
                if (preferredBasisMatches)
                {
                    rotation = preferredRotation;
                    up = preferredRotation * Vector3.up;
                }
                else
                {
                    if (z.sqrMagnitude == 0f) forward = PerpendicularUnit(right);
                    if (Mathf.Abs(Vector3.Dot(right, forward)) > 1e-5f)
                        throw new InvalidOperationException("STATIC_SORT_PROXY_TRANSFORM_SHEAR_UNREPRESENTABLE: " + sourceId);
                    up = Vector3.Cross(forward, right).normalized;
                    rotation = Quaternion.LookRotation(forward, up);
                }
            }
            else
            {
                right = x / sx; up = y / sy;
                if (Mathf.Abs(Vector3.Dot(right, up)) > 1e-5f ||
                    z.sqrMagnitude != 0f && (Mathf.Abs(Vector3.Dot(right, z.normalized)) > 1e-5f ||
                    Mathf.Abs(Vector3.Dot(up, z.normalized)) > 1e-5f))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_TRANSFORM_SHEAR_UNREPRESENTABLE: " + sourceId);
                forward = Vector3.Cross(right, up).normalized;
                rotation = Quaternion.LookRotation(forward, up);
            }
            var signedZ = z.sqrMagnitude == 0f ? 0f : Vector3.Dot(z, forward);
            proxy.localPosition = local.GetColumn(3);
            proxy.localRotation = rotation;
            // Derive orientation from the actual X/Y basis, then preserve a
            // reflection on the depth axis explicitly. Matrix4x4.rotation and
            // lossyScale can redistribute a reflection (notably local Z=-1)
            // across X/Y, changing RectTransform corners.
            proxy.localScale = new Vector3(sx, sy, signedZ);
            var reconstructed = Matrix4x4.TRS(proxy.localPosition, proxy.localRotation, proxy.localScale);
            if (!MatrixNear(local, reconstructed, 1e-4f))
                throw new InvalidOperationException("STATIC_SORT_PROXY_TRANSFORM_TRS_NOT_EXACT: " + sourceId + " (" + WorldCornerEvidence(source, proxy) + ")");
            if (!WorldRectMatches(source, proxy))
                throw new InvalidOperationException("STATIC_SORT_PROXY_TRANSFORM_NOT_EXACT: " + sourceId + " (" + WorldCornerEvidence(source, proxy) + ")");
            captureDiagnostic = RectCopyDiagnostic(source, proxy, parent, sourceId, transformPath,
                basisEqual, correctionAttempted, correctionSucceeded, localCorrection, correctionResidual);
        }

        static bool IsGeneratedTextSubmesh(GameObject gameObject)
        {
            if (gameObject == null || gameObject.transform.parent == null || gameObject.transform.childCount != 0 ||
                !(gameObject.transform is RectTransform) || (gameObject.hideFlags & HideFlags.DontSave) != HideFlags.DontSave) return false;
            var components = gameObject.GetComponents<Component>();
            var sub = components.FirstOrDefault(component => component != null && component.GetType().FullName == "TMPro.TMP_SubMeshUI");
            var owner = gameObject.transform.parent.GetComponents<Component>().FirstOrDefault(component => component != null &&
                component.GetType().FullName == "TMPro.TextMeshProUGUI");
            var layout = gameObject.GetComponent<LayoutElement>();
            if (sub == null || owner == null || layout == null || !layout.ignoreLayout) return false;
            var textComponent = sub.GetType().GetProperty("textComponent", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.GetValue(sub, null);
            var fontAsset = sub.GetType().GetProperty("fontAsset", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.GetValue(sub, null);
            return textComponent == (object)owner && fontAsset != null && components.All(component => component == null ||
                component is RectTransform || component is CanvasRenderer || component == sub || component is LayoutElement);
        }

        static bool IsSpineCanvasSubmesh(GameObject gameObject, Graphic sourceGraphic)
        {
            if (gameObject == null || sourceGraphic == null || sourceGraphic.GetType().FullName != "Spine.Unity.SkeletonGraphic" ||
                gameObject.transform.parent != sourceGraphic.transform || gameObject.transform.childCount != 0 ||
                !(gameObject.transform is RectTransform) || gameObject.GetComponent<RawImage>() == null ||
                gameObject.GetComponent<CanvasRenderer>() == null) return false;
            if (gameObject.GetComponents<Component>().Any(component => component != null &&
                !(component is RectTransform) && !(component is CanvasRenderer) && !(component is RawImage))) return false;
            var rendererListMember = (MemberInfo)sourceGraphic.GetType().GetProperty("canvasRenderers", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic) ??
                                     sourceGraphic.GetType().GetField("canvasRenderers", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            var rendererList = rendererListMember is PropertyInfo property ? property.GetValue(sourceGraphic, null) :
                rendererListMember is FieldInfo field ? field.GetValue(sourceGraphic) : null;
            if (!(rendererList is IEnumerable enumerable)) return false;
            var target = gameObject.GetComponent<CanvasRenderer>(); var exactCount = 0;
            foreach (var item in enumerable) if (item is CanvasRenderer renderer && renderer == target && renderer.gameObject == gameObject) exactCount++;
            return exactCount == 1;
        }

        static bool TryGetGeneratedSpineSourceIdentity(ProxyQueueSpec spec,
            IDictionary<string, GameObject> sourceNodes, Transform child, out string ownerNodeId,
            out ProxyRendererSpec ownerSpec, bool loadedReadback, out Graphic ownerGraphic)
        {
            ownerNodeId = null; ownerSpec = null; ownerGraphic = null;
            if (spec == null || sourceNodes == null || child == null || child.parent == null) return false;
            ownerGraphic = child.parent.GetComponent<Graphic>();
            if (ownerGraphic == null || ownerGraphic.GetType().FullName != "Spine.Unity.SkeletonGraphic" ||
                !IsSpineCanvasSubmesh(child.gameObject, ownerGraphic)) return false;
            var resolvedOwnerGraphic = ownerGraphic;
            var ownerIds = sourceNodes.Where(pair => pair.Value != null && pair.Value.transform == resolvedOwnerGraphic.transform)
                .Select(pair => pair.Key).ToArray();
            if (ownerIds.Length != 1) return false;
            ownerNodeId = ownerIds[0];
            var resolvedOwnerNodeId = ownerNodeId;
            var candidates = (spec.renderers ?? Array.Empty<ProxyRendererSpec>())
                .Concat(spec.nonDrawRenderers ?? Array.Empty<ProxyRendererSpec>())
                .Where(row => row != null && row.sourceType == "sp.Skeleton" && row.node == resolvedOwnerNodeId)
                .ToArray();
            if (candidates.Length != 1) return false;
            ownerSpec = candidates[0];
            if (!sourceNodes.TryGetValue(ownerNodeId, out var mappedOwner) || mappedOwner == null ||
                mappedOwner.GetComponent<Graphic>() != ownerGraphic || ownerGraphic.enabled != ownerSpec.sourceEnabled ||
                !TryGetSerializedEffectiveActive(spec, sourceNodes, mappedOwner, out var serializedActive) ||
                serializedActive != ownerSpec.sourceActive ||
                loadedReadback && mappedOwner.activeInHierarchy != ownerSpec.sourceActive) return false;
            return true;
        }

        static string TransformPath(Transform node)
        {
            var names = new Stack<string>();
            for (var cursor = node; cursor != null; cursor = cursor.parent) names.Push(cursor.name);
            return String.Join("/", names.ToArray());
        }

        static string SpineChildPath(Transform root, Transform child)
        {
            if (root == null || child == null || child == root || !child.IsChildOf(root)) return null;
            var segments = new Stack<string>();
            for (var cursor = child; cursor != null && cursor != root; cursor = cursor.parent)
                segments.Push(cursor.name + "[" + cursor.GetSiblingIndex() + "]");
            return String.Join("/", segments.ToArray());
        }

        static bool TryReadSpineMember(object target, string name, out object value)
        {
            for (var type = target == null ? null : target.GetType(); type != null; type = type.BaseType)
            {
                var flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly;
                var property = type.GetProperty(name, flags);
                if (property != null && property.CanRead) { value = property.GetValue(target, null); return true; }
                var field = type.GetField(name, flags);
                if (field != null) { value = field.GetValue(target); return true; }
            }
            value = null; return false;
        }

        static bool TryReadSpineTargetField(Graphic owner, string name, out object value)
        {
            if (name != "pmaVertexColors") return TryReadSpineMember(owner, name, out value);
            value = null;
            if (owner == null || owner.GetType().FullName != "Spine.Unity.SkeletonGraphic") return false;
            object generator;
            if (!TryReadSpineMember(owner, "MeshGenerator", out generator) || generator == null)
            {
                if (!TryReadSpineMember(owner, "meshGenerator", out generator) || generator == null) return false;
            }
            if (!TryReadSpineMember(generator, "settings", out var settings) || settings == null) return false;
            return TryReadSpineMember(settings, "pmaVertexColors", out value);
        }

        static bool TryReadSpineRendererList(Graphic owner, out List<CanvasRenderer> renderers)
        {
            renderers = new List<CanvasRenderer>();
            if (owner == null || owner.GetType().FullName != "Spine.Unity.SkeletonGraphic") return false;
            if (!TryReadSpineMember(owner, "canvasRenderers", out var value) || !(value is IEnumerable enumerable)) return false;
            foreach (var item in enumerable)
            {
                if (!(item is CanvasRenderer renderer) || renderer == null) return false;
                renderers.Add(renderer);
            }
            return true;
        }

        static bool TryReadSpineDataAsset(Graphic owner, out UnityEngine.Object dataAsset)
        {
            dataAsset = null;
            if (owner == null || owner.GetType().FullName != "Spine.Unity.SkeletonGraphic") return false;
            if (!TryReadSpineMember(owner, "SkeletonDataAsset", out var value) &&
                !TryReadSpineMember(owner, "skeletonDataAsset", out value)) return false;
            dataAsset = value as UnityEngine.Object;
            return dataAsset != null;
        }

        [Serializable] sealed class SpineSourceBindingPlan
        {
            public string sourceManifestSha256;
            public SpineSourceBindingComponent[] components;
            public SpineSourceBindingAsset[] dataAssets;
        }
        [Serializable] sealed class SpineSourceBindingComponent
        {
            public string sourceComponentId, sourceDataAssetId;
            public bool sourceHasStaticDataReference;
        }
        [Serializable] sealed class SpineSourceBindingAsset
        {
            public string sourceAssetId, skeletonDataAssetPath, skeletonSha256;
        }
        [Serializable] sealed class SpineDataCreateAttempt
        {
            public string sourceManifestSha256;
            public SpineDataAssetReadback[] readback;
        }
        [Serializable] sealed class SpineDataAssetReadback
        {
            public string sourceAssetId, skeletonDataAssetPath, skeletonDataAssetGuid, skeletonSha256;
            public bool nativeAssetIdentityVerified, savedSourceReferencesVerified, sourceProfileMaterialsVerified, staticDataVerified;
        }
        sealed class SpineDataIdentityEvidence
        {
            public string sourceDataAssetId, dataAssetPath, dataAssetGuid, bindingPlanPath, bindingPlanSha256,
                sourceManifestSha256;
        }
        [Serializable] sealed class SpineImportPlanEnvelope { public SpineImportPlanStage spineNativeStage; }
        [Serializable] sealed class SpineImportPlanStage
        {
            public string nativeBindingPlanPath, sourceNativeBindingPlanSha256, sourceManifestSha256;
        }
        [Serializable] sealed class SpineNullDataSourcePlan
        {
            public string sourceManifestSha256;
            public SpineNullDataSourceComponent[] components;
        }
        [Serializable] sealed class SpineNullDataSourceComponent
        {
            public string sourceComponentId, sourcePrefabId, sourceDataAssetId, staticDataState;
            public bool sourceHasStaticDataReference, sourceBusinessBehaviorDisabled, sourceCallbacksExecuted,
                persistentVisiblePose, sourceTimeScaleVerified, nativeRendererEnabled;
            public float sourceTimeScale, nativeTimeScale;
            public SpineNullDataFields fields;
            public SpineNullDataMaterialProfile unityMaterialProfile;
            public SpineNullTargetField[] targetFieldBindings;
        }
        [Serializable] sealed class SpineNullDataMaterialProfile { public string status; }
        [Serializable] sealed class SpineNullDataFields { public SpineNullDataSourceField skeletonData; }
        [Serializable] sealed class SpineNullDataSourceField
        {
            public string status, candidateInputMetaGuid, candidateInputPath, nativeSkeletonDataAssetGuid;
        }
        [Serializable] sealed class SpineNullTargetField
        {
            public string member, sourceProperty, status, valueType, stringValue;
            public bool boolValue;
            public float numberValue;
        }
        sealed class SpineNullDataPlanCache
        {
            public string sourcePlanPath, sourcePlanSha256, sourceManifestSha256;
            public Dictionary<string, SpineNullDataSourceComponent> components;
        }
        static readonly Dictionary<string, SpineNullDataPlanCache> SpineNullDataPlanCacheByPin =
            new Dictionary<string, SpineNullDataPlanCache>(StringComparer.Ordinal);
        static string SpineStageCachePath;
        static long SpineStageCacheLastWriteTicks;
        static SpineImportPlanStage SpineStageCache;

        static bool TryLoadPinnedSpineNullDataPlan(ProxyQueueSpec spec, out SpineNullDataPlanCache cache,
            out string diagnostic)
        {
            cache = null; diagnostic = null;
            var importPlanPath = Path.Combine(Application.dataPath, "Game/Editor/Conversion/import-plan.json");
            if (spec == null || !File.Exists(importPlanPath))
            { diagnostic = "import-plan-or-spine-stage-missing"; return false; }
            SpineImportPlanStage stage = SpineStageCache;
            var lastWriteTicks = File.GetLastWriteTimeUtc(importPlanPath).Ticks;
            if (stage == null || SpineStageCachePath != importPlanPath || SpineStageCacheLastWriteTicks != lastWriteTicks)
            {
                SpineImportPlanEnvelope envelope;
                try { envelope = JsonUtility.FromJson<SpineImportPlanEnvelope>(File.ReadAllText(importPlanPath, Encoding.UTF8)); }
                catch (Exception error) { diagnostic = "import-plan-json-invalid:" + error.GetType().Name; return false; }
                stage = envelope == null ? null : envelope.spineNativeStage;
                SpineStageCachePath = importPlanPath; SpineStageCacheLastWriteTicks = lastWriteTicks; SpineStageCache = stage;
            }
            const string expectedSourcePath = "Assets/Game/Editor/Conversion/spine-native-source-binding-plan.json";
            if (stage == null || stage.nativeBindingPlanPath != "Assets/Game/Editor/Conversion/spine-native-binding-plan.json" ||
                String.IsNullOrWhiteSpace(stage.sourceNativeBindingPlanSha256) ||
                stage.sourceManifestSha256 != spec.sourceManifestSha256)
            { diagnostic = "spine-source-plan-stage-pin-invalid"; return false; }
            var cacheKey = expectedSourcePath + "\n" + stage.sourceNativeBindingPlanSha256 + "\n" + stage.sourceManifestSha256;
            if (SpineNullDataPlanCacheByPin.TryGetValue(cacheKey, out cache)) return true;
            var projectRoot = Directory.GetParent(Application.dataPath).FullName;
            var sourcePlanPath = Path.Combine(projectRoot, expectedSourcePath.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(sourcePlanPath)) { diagnostic = "source-binding-plan-file-missing"; return false; }
            var bytes = File.ReadAllBytes(sourcePlanPath);
            var sourcePlanHash = HashBytes(bytes);
            if (sourcePlanHash != stage.sourceNativeBindingPlanSha256)
            { diagnostic = "source-binding-plan-byte-hash-differs"; return false; }
            SpineNullDataSourcePlan sourcePlan;
            try { sourcePlan = JsonUtility.FromJson<SpineNullDataSourcePlan>(Encoding.UTF8.GetString(bytes)); }
            catch (Exception error) { diagnostic = "source-binding-plan-json-invalid:" + error.GetType().Name; return false; }
            if (sourcePlan == null || sourcePlan.sourceManifestSha256 != spec.sourceManifestSha256)
            { diagnostic = "source-binding-plan-manifest-differs"; return false; }
            var componentMap = new Dictionary<string, SpineNullDataSourceComponent>(StringComparer.Ordinal);
            foreach (var component in sourcePlan.components ?? Array.Empty<SpineNullDataSourceComponent>())
            {
                if (component == null || String.IsNullOrWhiteSpace(component.sourceComponentId) ||
                    componentMap.ContainsKey(component.sourceComponentId))
                { diagnostic = "source-binding-plan-component-id-missing-or-duplicate"; return false; }
                componentMap.Add(component.sourceComponentId, component);
            }
            cache = new SpineNullDataPlanCache { sourcePlanPath = expectedSourcePath, sourcePlanSha256 = sourcePlanHash,
                sourceManifestSha256 = sourcePlan.sourceManifestSha256, components = componentMap };
            SpineNullDataPlanCacheByPin[cacheKey] = cache;
            return true;
        }

        static bool SameSpineFieldValue(object actual, SpineNullTargetField expected)
        {
            if (expected == null) return false;
            if (expected.valueType == "bool") return actual is bool actualBool && actualBool == expected.boolValue;
            if (expected.valueType == "string") return String.Equals(actual as string ?? String.Empty,
                expected.stringValue ?? String.Empty, StringComparison.Ordinal);
            if (expected.valueType == "number")
            {
                if (!(actual is IConvertible)) return false;
                try { return Convert.ToSingle(actual, CultureInfo.InvariantCulture) == expected.numberValue; }
                catch { return false; }
            }
            return false;
        }

        static bool IsIndependentlyMappedSourceNode(Transform child, Transform sourceOwner,
            IDictionary<string, GameObject> sourceNodes)
        {
            if (child == null || sourceOwner == null || sourceNodes == null) return false;
            if (sourceNodes.Values.Any(node => node != null && node.transform == child)) return true;
            for (var cursor = child.parent; cursor != null && cursor != sourceOwner; cursor = cursor.parent)
                if (sourceNodes.Values.Any(node => node != null && node.transform == cursor)) return true;
            return false;
        }

        static bool SameSpineNumber(object actual, float expected)
        {
            if (!(actual is IConvertible)) return false;
            try { return Convert.ToSingle(actual, CultureInfo.InvariantCulture) == expected; }
            catch { return false; }
        }

        static bool TryProveNullSpineDefaultGraphicQuad(Graphic owner, Mesh mesh,
            out string meshSha256, out string diagnostic)
        {
            meshSha256 = null; diagnostic = null;
            if (owner == null || owner.GetType().FullName != "Spine.Unity.SkeletonGraphic" || mesh == null)
            { diagnostic = "typed-owner-or-mesh-missing"; return false; }
            var vertices = mesh.vertices;
            var triangles = mesh.subMeshCount == 1 ? mesh.GetTriangles(0) : Array.Empty<int>();
            var rect = owner.rectTransform.rect;
            var expected = new[] { new Vector3(rect.xMin, rect.yMin, 0f), new Vector3(rect.xMin, rect.yMax, 0f),
                new Vector3(rect.xMax, rect.yMax, 0f), new Vector3(rect.xMax, rect.yMin, 0f) };
            var cornersExact = vertices.Length == 4 && vertices.SequenceEqual(expected);
            var trianglesExact = triangles.SequenceEqual(new[] { 0, 1, 2, 2, 3, 0 });
            var geometryExact = vertices.Length == 4 && mesh.subMeshCount == 1 && trianglesExact && cornersExact;
            string V(Vector3 value) => value.x.ToString("R", CultureInfo.InvariantCulture) + "," +
                value.y.ToString("R", CultureInfo.InvariantCulture) + "," + value.z.ToString("R", CultureInfo.InvariantCulture);
            diagnostic = "vertexCount=" + vertices.Length + ";submeshes=" + mesh.subMeshCount +
                ";indices=" + triangles.Length + ";triangleOrderExact=" + trianglesExact +
                ";rectCornersExact=" + cornersExact + ";rectMin=" + V(new Vector3(rect.xMin, rect.yMin, 0f)) +
                ";rectMax=" + V(new Vector3(rect.xMax, rect.yMax, 0f)) + ";vertices=[" +
                String.Join(";", vertices.Select(V)) + "]";
            if (!geometryExact) return false;
            meshSha256 = MeshFingerprint(mesh, 0);
            return !String.IsNullOrWhiteSpace(meshSha256);
        }

        static bool SpineSkinRuntimeRepresentationMatches(string sourceSkin, string actualSkin,
            string runtimeDefaultSkinName, bool sourceSkinVerified, bool defaultSkinRuntimeNull)
        {
            if (!sourceSkinVerified) return false;
            if (String.IsNullOrEmpty(sourceSkin)) return !defaultSkinRuntimeNull && String.IsNullOrEmpty(actualSkin);
            if (actualSkin == sourceSkin) return !defaultSkinRuntimeNull;
            // Unity serializes a null string in an inline proof as "". Accept
            // that exact representation only with the pinned data default-skin name.
            return defaultSkinRuntimeNull && String.IsNullOrEmpty(actualSkin) &&
                runtimeDefaultSkinName == sourceSkin;
        }

        static bool TryBuildSpineNullDataOwnerProof(ProxyQueueSpec spec, ProxyRendererSpec row, GameObject sourceNode,
            IDictionary<string, GameObject> sourceNodes, bool requireHierarchyActivity,
            out ProxySpineNullDataOwner proof, out string diagnostic)
        {
            proof = null; diagnostic = null;
            if (spec == null || row == null || sourceNode == null || sourceNodes == null || row.sourceType != "sp.Skeleton" ||
                !TryGetSerializedEffectiveActive(spec, sourceNodes, sourceNode, out var serializedActive) ||
                serializedActive != row.sourceActive || requireHierarchyActivity && sourceNode.activeInHierarchy != row.sourceActive)
            { diagnostic = "source-owner-is-not-an-exact-static-nondraw-spine-case"; return false; }
            var owner = sourceNode.GetComponent<Graphic>();
            if (owner == null || owner.GetType().FullName != "Spine.Unity.SkeletonGraphic" || owner.enabled != row.sourceEnabled ||
                !TryReadSpineIdentity(owner, row.sourceComponentId, out var actualSourceIdentity))
            { diagnostic = "typed-source-graphic-or-source-identity-differs"; return false; }
            var identityRows = sourceNode.GetComponents<Component>().Where(component => component != null &&
                component.GetType().FullName == "UnitySpineSourceIdentity").ToArray();
            if (!TryReadSpineMember(owner, "SkeletonDataAsset", out var nativeDataValue) &&
                !TryReadSpineMember(owner, "skeletonDataAsset", out nativeDataValue))
            { diagnostic = "skeleton-data-reference-member-missing"; return false; }
            var nativeDataReferenceNull = nativeDataValue == null;
            if (!TryLoadPinnedSpineNullDataPlan(spec, out var planCache, out var planDiagnostic))
            { diagnostic = planDiagnostic; return false; }
            if (!planCache.components.TryGetValue(row.sourceComponentId, out var sourceRow) ||
                sourceRow.sourceComponentId != row.sourceComponentId || sourceRow.sourcePrefabId != spec.sourcePrefabId ||
                sourceRow.sourceHasStaticDataReference || !String.IsNullOrEmpty(sourceRow.sourceDataAssetId) ||
                sourceRow.staticDataState != "source_uuid_absent_component_preserved_unbound" ||
                sourceRow.fields == null || sourceRow.fields.skeletonData == null ||
                sourceRow.fields.skeletonData.status != "no_static_source_data_reference" ||
                !String.IsNullOrEmpty(sourceRow.fields.skeletonData.candidateInputMetaGuid) ||
                !String.IsNullOrEmpty(sourceRow.fields.skeletonData.candidateInputPath) ||
                !String.IsNullOrEmpty(sourceRow.fields.skeletonData.nativeSkeletonDataAssetGuid) ||
                sourceRow.unityMaterialProfile == null ||
                sourceRow.unityMaterialProfile.status != "no-serialized-skeleton-data-no-render-material-closure")
            { diagnostic = "source-plan-does-not-prove-absent-skeleton-data-reference"; return false; }
            var sourceIdentityTimeScaleVerified = identityRows.Length == 1 &&
                TryReadSpineMember(identityRows[0], "renderer", out var identityRenderer) && identityRenderer as Component == owner &&
                TryReadSpineMember(identityRows[0], "sourceTimeScale", out var identitySourceTimeScale) &&
                SameSpineNumber(identitySourceTimeScale, sourceRow.sourceTimeScale) &&
                TryReadSpineMember(identityRows[0], "nativeTimeScale", out var identityNativeTimeScale) &&
                SameSpineNumber(identityNativeTimeScale, sourceRow.nativeTimeScale) &&
                TryReadSpineMember(identityRows[0], "sourceTimeScaleVerified", out var identityScaleVerified) &&
                identityScaleVerified is bool identityScaleBool && identityScaleBool == sourceRow.sourceTimeScaleVerified &&
                TryReadSpineMember(identityRows[0], "persistentVisiblePose", out var identityPersistentPose) &&
                identityPersistentPose is bool identityPoseBool && identityPoseBool == sourceRow.persistentVisiblePose;
            if (!sourceIdentityTimeScaleVerified)
            { diagnostic = "source-identity-time-scale-contract-differs"; return false; }
            if (!sourceRow.persistentVisiblePose || !sourceRow.sourceBusinessBehaviorDisabled || sourceRow.sourceCallbacksExecuted ||
                !sourceRow.sourceTimeScaleVerified || sourceRow.nativeRendererEnabled != row.sourceEnabled ||
                sourceRow.nativeTimeScale != 0f || !TryReadSpineRendererList(owner, out var registered) || registered.Count != 0)
            { diagnostic = "source-static-boundary-or-empty-registered-list-invalid"; return false; }
            var rootMesh = owner.canvasRenderer == null ? null : owner.canvasRenderer.GetMesh();
            var rootVertices = rootMesh == null ? 0 : rootMesh.vertexCount;
            var rootSubmeshes = rootMesh == null ? 0 : rootMesh.subMeshCount;
            var rootMaterials = owner.canvasRenderer == null ? -1 : owner.canvasRenderer.materialCount;
            var rootMeshIndexCount = rootMesh == null ? 0 : Enumerable.Range(0, rootMesh.subMeshCount)
                .Sum(index => rootMesh.GetIndexCount(index) > Int32.MaxValue ? Int32.MaxValue : (int)rootMesh.GetIndexCount(index));
            var defaultGraphicMaterial = Graphic.defaultGraphicMaterial;
            var sourceUsesDefaultGraphicMaterial = owner.material == defaultGraphicMaterial;
            var rendererMaterial = rootMaterials == 1 && owner.canvasRenderer != null ? owner.canvasRenderer.GetMaterial(0) : null;
            var rendererMaterialMatchesGraphic = rendererMaterial != null && rendererMaterial == owner.materialForRendering;
            var materialSlots = rootMaterials > 0 && owner.canvasRenderer != null
                ? Enumerable.Range(0, rootMaterials).Select(index => owner.canvasRenderer.GetMaterial(index)).ToArray()
                : Array.Empty<Material>();
            var extraMaterialModifierCount = owner.GetComponents<Component>().Count(component => component != null &&
                component != owner && component is IMaterialModifier);
            var defaultGraphicMaterialOnly = rootMaterials == 0 || (rootMaterials == 1 &&
                sourceUsesDefaultGraphicMaterial && rendererMaterialMatchesGraphic && extraMaterialModifierCount == 0);
            var rootMaterialEvidence = "count=" + rootMaterials + ";sourceBaseIsGraphicDefault=" + sourceUsesDefaultGraphicMaterial +
                ";slotMatchesMaterialForRendering=" + rendererMaterialMatchesGraphic + ";extraMaterialModifiers=" +
                extraMaterialModifierCount + ";slots=[" + String.Join("|", materialSlots.Select((material, index) =>
                    index + ":" + (material == null ? "<null>" : material.name) + "/" +
                    (material == null || material.shader == null ? "<null>" : material.shader.name))) + "]";
            if (!defaultGraphicMaterialOnly)
            { diagnostic = "source-null-spine-owner-has-nondefault-material-presentation:vertices=" + rootVertices +
                ";indices=" + rootMeshIndexCount + ";" + rootMaterialEvidence; return false; }
            var nativeRootMeshEmpty = rootVertices == 0 && rootMeshIndexCount == 0;
            var nativeRootMeshDefaultGraphicQuad = false;
            string rootMeshSha256 = null; string rootMeshGeometryEvidence = "empty-render-mesh";
            if (!nativeRootMeshEmpty && !TryProveNullSpineDefaultGraphicQuad(owner, rootMesh,
                out rootMeshSha256, out rootMeshGeometryEvidence))
            { diagnostic = "source-null-spine-mesh-is-not-exact-default-graphic-quad:vertices=" + rootVertices +
                ";submeshes=" + rootSubmeshes + ";indices=" + rootMeshIndexCount +
                ";materialDefaultOnly=" + defaultGraphicMaterialOnly + ";" + rootMeshGeometryEvidence +
                ";" + rootMaterialEvidence; return false; }
            if (!nativeRootMeshEmpty) nativeRootMeshDefaultGraphicQuad = true;
            if (owner.GetComponents<Graphic>().Length != 1 || sourceNode.GetComponentsInChildren<Graphic>(true)
                .Any(child => child != null && child != owner &&
                    !IsIndependentlyMappedSourceNode(child.transform, sourceNode.transform, sourceNodes)))
            { diagnostic = "source-null-spine-owner-has-unregistered-child-graphic"; return false; }
            var components = sourceNode.GetComponents<Component>();
            if (components.Any(component => component != null && component.GetType().FullName ==
                "Monkey.Targets.Spine.UnitySpineGraphicMaterialPresentation"))
            { diagnostic = "source-null-spine-owner-has-material-presentation"; return false; }

            var sourceTargetFields = new List<string>();
            var expectedFields = new List<string>(); var actualFields = new List<string>();
            var sourceTimeScaleFieldFound = false;
            foreach (var field in sourceRow.targetFieldBindings ?? Array.Empty<SpineNullTargetField>())
            {
                if (field == null || String.IsNullOrWhiteSpace(field.member) ||
                    field.status != "explicit" && field.status != "resolved_source_engine_default") continue;
                object sourceTargetValue = field.valueType == "bool" ? (object)field.boolValue :
                    field.valueType == "number" ? (object)field.numberValue :
                    field.valueType == "string" ? (object)field.stringValue : null;
                if (sourceTargetValue == null)
                { diagnostic = "source-target-field-type-unresolved:" + field.member; return false; }
                sourceTargetFields.Add(field.member + "=" + Convert.ToString(sourceTargetValue, CultureInfo.InvariantCulture));
                var fixedPoseTimeScale = sourceRow.persistentVisiblePose && field.member == "timeScale";
                if (field.member == "timeScale")
                {
                    sourceTimeScaleFieldFound = field.valueType == "number" &&
                        field.numberValue == sourceRow.sourceTimeScale && sourceRow.sourceTimeScaleVerified;
                    if (!sourceTimeScaleFieldFound)
                    { diagnostic = "source-timescale-field-does-not-match-pinned-source-value"; return false; }
                }
                object nativeExpectedValue = fixedPoseTimeScale ? (object)sourceRow.nativeTimeScale : sourceTargetValue;
                if (!TryReadSpineTargetField(owner, field.member, out var actualValue) ||
                    (fixedPoseTimeScale ? !SameSpineNumber(actualValue, sourceRow.nativeTimeScale) :
                        !SameSpineFieldValue(actualValue, field)))
                { diagnostic = "mapped-static-field-differs:" + field.member; return false; }
                expectedFields.Add(field.member + "=" + Convert.ToString(nativeExpectedValue, CultureInfo.InvariantCulture));
                actualFields.Add(field.member + "=" + Convert.ToString(actualValue, CultureInfo.InvariantCulture));
            }
            if (sourceRow.persistentVisiblePose && !sourceTimeScaleFieldFound)
            { diagnostic = "persistent-visible-spine-source-timescale-not-pinned"; return false; }
            if (sourceRow.persistentVisiblePose)
            {
                if (!TryReadSpineMember(owner, "timeScale", out var nativeTimeScale) ||
                    !SameSpineNumber(nativeTimeScale, sourceRow.nativeTimeScale))
                { diagnostic = "persistent-visible-spine-timescale-differs"; return false; }
            }
            var sourceTargetFieldsJson = "[" + String.Join(",", sourceTargetFields.OrderBy(value => value, StringComparer.Ordinal)
                .Select(value => "\"" + value.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"")) + "]";
            var expectedJson = "[" + String.Join(",", expectedFields.OrderBy(value => value, StringComparer.Ordinal)
                .Select(value => "\"" + value.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"")) + "]";
            var actualJson = "[" + String.Join(",", actualFields.OrderBy(value => value, StringComparer.Ordinal)
                .Select(value => "\"" + value.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"")) + "]";
            proof = new ProxySpineNullDataOwner { sourceComponentId = row.sourceComponentId, sourceNode = row.node,
                sourceStaticDataState = sourceRow.staticDataState, sourceBindingPlanPath = planCache.sourcePlanPath,
                sourceBindingPlanSha256 = planCache.sourcePlanSha256, sourceManifestSha256 = planCache.sourceManifestSha256,
                sourceMaterialClosureStatus = sourceRow.unityMaterialProfile.status, rootMaterialEvidence = rootMaterialEvidence,
                rootMeshSha256 = rootMeshSha256, rootMeshGeometryEvidence = rootMeshGeometryEvidence,
                sourceOwnerGraphic = owner, sourceHasStaticDataReference = sourceRow.sourceHasStaticDataReference,
                sourceDataAssetIdNull = sourceRow.sourceDataAssetId == null, sourcePlanVerified = true,
                sourceIdentityVerified = actualSourceIdentity == row.sourceComponentId, sourceNodeInactive = !sourceNode.activeInHierarchy,
                sourceNodeActive = sourceNode.activeInHierarchy, sourceOwnerEnabled = owner.enabled,
                sourceSerializedActive = serializedActive, sourceSerializedActiveVerified = true,
                nativeDataReferenceNull = nativeDataReferenceNull, nativeRootMeshEmpty = nativeRootMeshEmpty,
                nativeRootMeshDefaultGraphicQuad = nativeRootMeshDefaultGraphicQuad,
                rootCanvasDefaultMaterialOnly = defaultGraphicMaterialOnly,
                rootSourceBaseDefaultMaterial = sourceUsesDefaultGraphicMaterial,
                rootMaterialSlotMatchesGraphicRendering = rendererMaterialMatchesGraphic,
                registeredRendererListEmpty = registered.Count == 0, mappedStaticFieldsVerified = true,
                sourceBehaviorBoundaryVerified = sourceRow.sourceBusinessBehaviorDisabled && !sourceRow.sourceCallbacksExecuted,
                dynamicAssignmentUnverified = true, rootMeshVertexCount = rootVertices, rootMeshSubmeshCount = rootSubmeshes,
                rootMeshIndexCount = rootMeshIndexCount,
                rootCanvasMaterialCount = rootMaterials, rootExtraMaterialModifierCount = extraMaterialModifierCount,
                registeredRendererCount = registered.Count,
                sourceTargetFieldsJson = sourceTargetFieldsJson, expectedFieldsJson = expectedJson, actualFieldsJson = actualJson,
                sourceTimeScale = sourceRow.sourceTimeScale, nativeTimeScale = sourceRow.nativeTimeScale,
                sourceTimeScaleVerified = sourceRow.sourceTimeScaleVerified,
                sourceIdentityTimeScaleVerified = sourceIdentityTimeScaleVerified,
                persistentVisiblePose = sourceRow.persistentVisiblePose };
            proof.verified = nativeDataReferenceNull && (proof.nativeRootMeshEmpty || proof.nativeRootMeshDefaultGraphicQuad) &&
                proof.registeredRendererListEmpty &&
                proof.sourceIdentityVerified && proof.sourcePlanVerified && proof.mappedStaticFieldsVerified &&
                proof.sourceBehaviorBoundaryVerified && proof.dynamicAssignmentUnverified && proof.sourceSerializedActiveVerified &&
                proof.sourceIdentityTimeScaleVerified;
            if (!proof.verified) { diagnostic = "source-null-spine-native-proof-incomplete"; proof = null; return false; }
            return true;
        }

        static bool TryReadSpineDataIdentity(ProxyQueueSpec spec, string sourceComponentId,
            UnityEngine.Object actualDataAsset, out SpineDataIdentityEvidence evidence, out string diagnostic)
        {
            evidence = null; diagnostic = null;
            const string bindingPlanPath = "Assets/Game/Editor/Conversion/spine-native-binding-plan.json";
            if (spec == null || actualDataAsset == null || !File.Exists(bindingPlanPath))
            { diagnostic = "source-binding-plan-or-data-asset-missing"; return false; }
            var planBytes = File.ReadAllBytes(bindingPlanPath);
            var planHash = HashBytes(planBytes);
            var bindingPlan = JsonUtility.FromJson<SpineSourceBindingPlan>(Encoding.UTF8.GetString(planBytes));
            if (bindingPlan == null || String.IsNullOrWhiteSpace(bindingPlan.sourceManifestSha256) ||
                bindingPlan.sourceManifestSha256 != spec.sourceManifestSha256)
            { diagnostic = "source-binding-plan-manifest-hash-differs"; return false; }
            var componentRows = (bindingPlan.components ?? Array.Empty<SpineSourceBindingComponent>())
                .Where(row => row != null && row.sourceComponentId == sourceComponentId).ToArray();
            if (componentRows.Length != 1 || !componentRows[0].sourceHasStaticDataReference ||
                String.IsNullOrWhiteSpace(componentRows[0].sourceDataAssetId))
            { diagnostic = "source-component-data-asset-mapping-missing-or-ambiguous"; return false; }
            var sourceDataAssetId = componentRows[0].sourceDataAssetId;
            var dataRows = (bindingPlan.dataAssets ?? Array.Empty<SpineSourceBindingAsset>())
                .Where(row => row != null && row.sourceAssetId == sourceDataAssetId).ToArray();
            if (dataRows.Length != 1 || String.IsNullOrWhiteSpace(dataRows[0].skeletonDataAssetPath) ||
                String.IsNullOrWhiteSpace(dataRows[0].skeletonSha256))
            { diagnostic = "source-data-asset-plan-row-missing-or-ambiguous"; return false; }
            var attemptPath = Path.Combine(Directory.GetParent(Application.dataPath).FullName,
                "Analysis/Readback/Spine/create-attempt.json");
            if (!File.Exists(attemptPath))
            { diagnostic = "spine-data-asset-native-readback-missing"; return false; }
            var attempt = JsonUtility.FromJson<SpineDataCreateAttempt>(File.ReadAllText(attemptPath, Encoding.UTF8));
            if (attempt == null || attempt.sourceManifestSha256 != bindingPlan.sourceManifestSha256)
            { diagnostic = "spine-data-asset-readback-manifest-hash-differs"; return false; }
            var readbackRows = (attempt.readback ?? Array.Empty<SpineDataAssetReadback>())
                .Where(row => row != null && row.sourceAssetId == sourceDataAssetId).ToArray();
            if (readbackRows.Length != 1)
            { diagnostic = "spine-data-asset-native-readback-row-missing-or-ambiguous"; return false; }
            var readback = readbackRows[0];
            if (!readback.nativeAssetIdentityVerified || !readback.savedSourceReferencesVerified ||
                !readback.sourceProfileMaterialsVerified || !readback.staticDataVerified ||
                readback.skeletonDataAssetPath != dataRows[0].skeletonDataAssetPath ||
                readback.skeletonSha256 != dataRows[0].skeletonSha256)
            { diagnostic = "spine-data-asset-native-readback-content-or-path-differs"; return false; }
            var actualPath = AssetDatabase.GetAssetPath(actualDataAsset);
            var actualGuid = String.IsNullOrWhiteSpace(actualPath) ? null : AssetDatabase.AssetPathToGUID(actualPath);
            if (actualPath != readback.skeletonDataAssetPath || String.IsNullOrWhiteSpace(actualGuid) ||
                actualGuid != readback.skeletonDataAssetGuid || AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(actualPath) != actualDataAsset)
            { diagnostic = "component-data-asset-reference-does-not-match-exact-readback-guid"; return false; }
            evidence = new SpineDataIdentityEvidence { sourceDataAssetId = sourceDataAssetId, dataAssetPath = actualPath,
                dataAssetGuid = actualGuid, bindingPlanPath = bindingPlanPath, bindingPlanSha256 = planHash,
                sourceManifestSha256 = bindingPlan.sourceManifestSha256 };
            return true;
        }

        static bool TryBuildSpineEmptyPoseOwnerProof(ProxyQueueSpec spec, ProxyRendererSpec row, GameObject sourceNode,
            IDictionary<string, GameObject> sourceNodes, bool requireHierarchyActivity,
            out ProxySpineEmptyPoseOwner proof, out string diagnostic)
        {
            proof = null; diagnostic = null;
            if (spec == null || row == null || sourceNode == null || sourceNodes == null || row.sourceType != "sp.Skeleton" ||
                sourceNode.activeInHierarchy != row.sourceActive || !row.sourceActive || !row.sourceEnabled)
            { diagnostic = "source-owner-is-not-an-active-spine-render-event"; return false; }
            var owner = sourceNode.GetComponent<Graphic>();
            if (owner == null || owner.GetType().FullName != "Spine.Unity.SkeletonGraphic" || owner.enabled != row.sourceEnabled ||
                !TryReadSpineIdentity(owner, row.sourceComponentId, out _))
            { diagnostic = "typed-source-graphic-or-source-identity-differs"; return false; }
            UnityEngine.Object dataAsset = null;
            SpineDataIdentityEvidence dataEvidence = null;
            string dataDiagnostic = null;
            if (!TryReadSpineDataAsset(owner, out dataAsset) || dataAsset == null ||
                !TryReadSpineDataIdentity(spec, row.sourceComponentId, dataAsset, out dataEvidence, out dataDiagnostic))
            { diagnostic = dataDiagnostic ?? "exact-source-skeleton-data-reference-missing"; return false; }
            if (!TryLoadPinnedSpineNullDataPlan(spec, out var planCache, out var planDiagnostic))
            { diagnostic = planDiagnostic; return false; }
            if (!planCache.components.TryGetValue(row.sourceComponentId, out var sourceRow) ||
                sourceRow.sourceComponentId != row.sourceComponentId || sourceRow.sourcePrefabId != spec.sourcePrefabId ||
                !sourceRow.sourceHasStaticDataReference || sourceRow.sourceDataAssetId != dataEvidence.sourceDataAssetId ||
                sourceRow.staticDataState != "exact_data_asset_required" || sourceRow.fields == null ||
                sourceRow.fields.skeletonData == null ||
                sourceRow.fields.skeletonData.status != "candidate_guid_declared_source_hash_verified" ||
                String.IsNullOrWhiteSpace(sourceRow.fields.skeletonData.candidateInputMetaGuid) ||
                String.IsNullOrWhiteSpace(sourceRow.fields.skeletonData.candidateInputPath))
            { diagnostic = "source-plan-does-not-pin-exact-skeleton-data-and-fields"; return false; }
            if (!sourceRow.persistentVisiblePose || !sourceRow.sourceBusinessBehaviorDisabled || sourceRow.sourceCallbacksExecuted ||
                !sourceRow.sourceTimeScaleVerified || sourceRow.nativeRendererEnabled != row.sourceEnabled ||
                sourceRow.nativeTimeScale != 0f)
            { diagnostic = "source-static-pose-policy-or-native-time-scale-invalid"; return false; }
            if (!TryGetSpineTargetField(sourceRow, "initialSkinName", out var skinValue) || !(skinValue is string sourceSkin) ||
                !TryGetSpineTargetField(sourceRow, "startingAnimation", out var animationValue) || !(animationValue is string sourceAnimation))
            { diagnostic = "source-skin-or-animation-target-field-unresolved"; return false; }

            var sourceTargetFields = new List<string>(); var expectedNativeFields = new List<string>(); var actualNativeFields = new List<string>();
            var sourceTimeScaleFieldFound = false;
            foreach (var field in sourceRow.targetFieldBindings ?? Array.Empty<SpineNullTargetField>())
            {
                if (field == null || String.IsNullOrWhiteSpace(field.member) ||
                    field.status != "explicit" && field.status != "resolved_source_engine_default") continue;
                object sourceValue = field.valueType == "bool" ? (object)field.boolValue :
                    field.valueType == "number" ? (object)field.numberValue :
                    field.valueType == "string" ? (object)field.stringValue : null;
                if (sourceValue == null) { diagnostic = "source-target-field-type-unresolved:" + field.member; return false; }
                sourceTargetFields.Add(field.member + "=" + Convert.ToString(sourceValue, CultureInfo.InvariantCulture));
                var timeScaleOverride = sourceRow.persistentVisiblePose && field.member == "timeScale";
                if (field.member == "timeScale")
                {
                    sourceTimeScaleFieldFound = field.valueType == "number" && field.numberValue == sourceRow.sourceTimeScale;
                    if (!sourceTimeScaleFieldFound)
                    { diagnostic = "source-timescale-field-does-not-match-pinned-source-value"; return false; }
                }
                object expectedNative = timeScaleOverride ? (object)sourceRow.nativeTimeScale : sourceValue;
                if (!TryReadSpineTargetField(owner, field.member, out var actualValue) ||
                    (timeScaleOverride ? !SameSpineNumber(actualValue, sourceRow.nativeTimeScale) : !SameSpineFieldValue(actualValue, field)))
                { diagnostic = "mapped-static-field-differs:" + field.member; return false; }
                expectedNativeFields.Add(field.member + "=" + Convert.ToString(expectedNative, CultureInfo.InvariantCulture));
                actualNativeFields.Add(field.member + "=" + Convert.ToString(actualValue, CultureInfo.InvariantCulture));
            }
            if (!sourceTimeScaleFieldFound)
            { diagnostic = "source-timescale-field-not-pinned"; return false; }
            var sourceTargetFieldsJson = SpineFieldListJson(sourceTargetFields);
            var expectedNativeFieldsJson = SpineFieldListJson(expectedNativeFields);
            var actualNativeFieldsJson = SpineFieldListJson(actualNativeFields);

            var identityRows = sourceNode.GetComponents<Component>().Where(component => component != null &&
                component.GetType().FullName == "UnitySpineSourceIdentity").ToArray();
            var identityTimeScaleVerified = identityRows.Length == 1 &&
                TryReadSpineMember(identityRows[0], "renderer", out var identityRenderer) && identityRenderer as Component == owner &&
                TryReadSpineMember(identityRows[0], "sourceTimeScale", out var identitySourceTimeScale) &&
                SameSpineNumber(identitySourceTimeScale, sourceRow.sourceTimeScale) &&
                TryReadSpineMember(identityRows[0], "nativeTimeScale", out var identityNativeTimeScale) &&
                SameSpineNumber(identityNativeTimeScale, sourceRow.nativeTimeScale) &&
                TryReadSpineMember(identityRows[0], "sourceTimeScaleVerified", out var identityScaleVerified) &&
                identityScaleVerified is bool identityScaleBool && identityScaleBool == sourceRow.sourceTimeScaleVerified &&
                TryReadSpineMember(identityRows[0], "persistentVisiblePose", out var identityPoseValue) &&
                identityPoseValue is bool identityPoseBool && identityPoseBool == sourceRow.persistentVisiblePose;
            if (!identityTimeScaleVerified)
            { diagnostic = "source-identity-time-scale-contract-differs"; return false; }

            var helper = sourceNode.GetComponents<Component>().SingleOrDefault(component => component != null &&
                component.GetType().FullName == "Monkey.Targets.Spine.UnitySpineGraphicMaterialPresentation");
            if (helper == null || !(helper is Behaviour helperBehaviour) || !helperBehaviour.enabled ||
                !TryReadSpineMember(helper, "graphic", out var helperGraphic) || helperGraphic as Graphic != owner)
            { diagnostic = "exact-spine-material-presentation-helper-missing-or-mismatched"; return false; }
            var readSaved = helper.GetType().GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                .SingleOrDefault(method => method.Name == "ReadSaved" && method.GetParameters().Length == 5);
            if (readSaved == null)
            { diagnostic = "exact-spine-material-presentation-readback-api-missing"; return false; }
            object presentation;
            try { presentation = readSaved.Invoke(helper, new object[] { null, sourceSkin, true, sourceAnimation, true }); }
            catch (Exception error)
            { diagnostic = "spine-presentation-readback-threw:" + error.GetType().Name; return false; }
            if (presentation == null || !TryReadSpineMember(presentation, "pose", out var pose) || pose == null)
            { diagnostic = "spine-fixed-pose-presentation-readback-missing"; return false; }
            if (!TryReadSpineMember(presentation, "nativeMaterialVerified", out var materialReadback) ||
                !(materialReadback is bool materialVerified) || !materialVerified ||
                !TryReadSpineMember(presentation, "instructionCount", out var instructionValue) || !(instructionValue is int instructionCount) ||
                !TryReadSpineMember(presentation, "canvasRendererCount", out var rendererValue) || !(rendererValue is int presentationRendererCount) ||
                !TryReadSpineMember(pose, "emptyPoseVerified", out var emptyPoseValue) || !(emptyPoseValue is bool emptyPoseVerified) || !emptyPoseVerified ||
                !TryReadSpineMember(pose, "sourceDataIdentityVerified", out var dataIdentityValue) || !(dataIdentityValue is bool dataIdentityVerified) || !dataIdentityVerified ||
                !TryReadSpineMember(pose, "initialized", out var initializedValue) || !(initializedValue is bool initialized) || !initialized ||
                !TryReadSpineMember(pose, "animationStateInitialized", out var stateValue) || !(stateValue is bool stateInitialized) || !stateInitialized ||
                !TryReadSpineMember(pose, "actualSkin", out var actualSkinValue) ||
                !TryReadSpineMember(pose, "sourceSkinVerified", out var skinVerifiedValue) ||
                    !(skinVerifiedValue is bool sourceSkinRuntimeVerified) || !sourceSkinRuntimeVerified ||
                !TryReadSpineMember(pose, "runtimeDefaultSkinName", out var runtimeDefaultSkinNameValue) ||
                !TryReadSpineMember(pose, "defaultSkinRuntimeNull", out var defaultSkinRuntimeNullValue) ||
                    !(defaultSkinRuntimeNullValue is bool defaultSkinRuntimeNull) ||
                !SpineSkinRuntimeRepresentationMatches(sourceSkin, actualSkinValue as string,
                    runtimeDefaultSkinNameValue as string, sourceSkinRuntimeVerified, defaultSkinRuntimeNull) ||
                !TryReadSpineMember(pose, "actualAnimation", out var actualAnimationValue) || (actualAnimationValue as string) != sourceAnimation ||
                !TryReadSpineMember(pose, "trackTime", out var trackTimeValue) || !SameSpineNumber(trackTimeValue, 0f) ||
                !TryReadSpineMember(pose, "slotCount", out var slotValue) || !(slotValue is int slotCount) ||
                !TryReadSpineMember(pose, "nonNullAttachmentCount", out var attachmentValue) || !(attachmentValue is int attachmentCount) ||
                !TryReadSpineMember(pose, "activeDrawableAttachmentCount", out var drawableValue) || !(drawableValue is int drawableCount) || drawableCount != 0)
            { diagnostic = "pinned-spine-fixed-pose-does-not-prove-no-drawable-attachments"; return false; }
            var rootMesh = owner.canvasRenderer == null ? null : owner.canvasRenderer.GetMesh();
            var rootVertices = rootMesh == null ? 0 : rootMesh.vertexCount;
            var rootSubmeshes = rootMesh == null ? 0 : rootMesh.subMeshCount;
            var rootMaterials = owner.canvasRenderer == null ? -1 : owner.canvasRenderer.materialCount;
            if (instructionCount != 0 || presentationRendererCount != 0 || rootVertices != 0 || rootMaterials < 0 ||
                rootSubmeshes > 0 || !TryReadSpineRendererList(owner, out var registered) || registered.Count != 0)
            { diagnostic = "spine-empty-fixed-pose-has-native-renderer-or-submesh"; return false; }
            if (sourceNode.GetComponentsInChildren<Graphic>(true).Any(child => child != null && child != owner &&
                !IsIndependentlyMappedSourceNode(child.transform, sourceNode.transform, sourceNodes)))
            { diagnostic = "spine-empty-fixed-pose-has-unmapped-child-graphic"; return false; }

            proof = new ProxySpineEmptyPoseOwner { sourceComponentId = row.sourceComponentId, sourceNode = row.node,
                sourceDataAssetId = dataEvidence.sourceDataAssetId, sourceDataAssetPath = dataEvidence.dataAssetPath,
                sourceDataAssetGuid = dataEvidence.dataAssetGuid, sourceBindingPlanPath = dataEvidence.bindingPlanPath,
                sourceBindingPlanSha256 = dataEvidence.bindingPlanSha256, sourceManifestSha256 = dataEvidence.sourceManifestSha256,
                sourceOwnerGraphic = owner, sourceDataAssetReference = dataAsset, sourceSkin = sourceSkin,
                sourceAnimation = sourceAnimation, actualSkin = actualSkinValue as string,
                runtimeDefaultSkinName = runtimeDefaultSkinNameValue as string,
                actualAnimation = actualAnimationValue as string, sourceTargetFieldsJson = sourceTargetFieldsJson,
                expectedFieldsJson = expectedNativeFieldsJson, actualFieldsJson = actualNativeFieldsJson,
                fixedPoseSlotCount = slotCount, fixedPoseAttachmentCount = attachmentCount,
                fixedPoseDrawableAttachmentCount = drawableCount, presentationInstructionCount = instructionCount,
                presentationCanvasRendererCount = presentationRendererCount, rootMeshVertexCount = rootVertices,
                rootMeshSubmeshCount = rootSubmeshes, rootCanvasMaterialCount = rootMaterials,
                registeredRendererCount = registered.Count, sourceTimeScale = sourceRow.sourceTimeScale,
                nativeTimeScale = sourceRow.nativeTimeScale, actualTrackTime = Convert.ToSingle(trackTimeValue, CultureInfo.InvariantCulture),
                sourceHasStaticDataReference = sourceRow.sourceHasStaticDataReference, sourcePlanVerified = true,
                sourceIdentityVerified = TryReadSpineIdentity(owner, row.sourceComponentId, out _),
                sourceDataReferenceVerified = owner != null && dataAsset != null &&
                    (TryReadSpineMember(owner, "SkeletonDataAsset", out var actualData) ||
                     TryReadSpineMember(owner, "skeletonDataAsset", out actualData)) && actualData as UnityEngine.Object == dataAsset,
                sourceTimeScaleVerified = sourceRow.sourceTimeScaleVerified,
                sourceIdentityTimeScaleVerified = identityTimeScaleVerified,
                persistentVisiblePose = sourceRow.persistentVisiblePose,
                sourceBusinessBehaviorDisabled = sourceRow.sourceBusinessBehaviorDisabled,
                sourceCallbacksExecuted = sourceRow.sourceCallbacksExecuted,
                mappedStaticFieldsVerified = expectedNativeFieldsJson == actualNativeFieldsJson,
                sdkPoseInitialized = initialized && stateInitialized, sdkDataIdentityVerified = dataIdentityVerified,
                sourceSkinRuntimeVerified = sourceSkinRuntimeVerified,
                defaultSkinRuntimeNull = defaultSkinRuntimeNull,
                fixedPoseVerified = emptyPoseVerified && sourceSkinRuntimeVerified &&
                    sourceAnimation == (actualAnimationValue as string) && SameSpineNumber(trackTimeValue, 0f),
                noDrawableAttachmentPoseVerified = drawableCount == 0,
                rootMeshEmpty = rootVertices == 0 && rootMaterials >= 0 && rootSubmeshes <= 0,
                registeredRendererListEmpty = registered.Count == 0,
                helperReadbackVerified = materialVerified && instructionCount == 0 && presentationRendererCount == 0 };
            proof.verified = proof.sourceHasStaticDataReference && proof.sourcePlanVerified && proof.sourceIdentityVerified &&
                proof.sourceDataReferenceVerified && proof.sourceTimeScaleVerified && proof.sourceIdentityTimeScaleVerified &&
                proof.persistentVisiblePose && proof.sourceBusinessBehaviorDisabled && !proof.sourceCallbacksExecuted &&
                proof.mappedStaticFieldsVerified && proof.sdkPoseInitialized && proof.sdkDataIdentityVerified &&
                proof.fixedPoseVerified && proof.noDrawableAttachmentPoseVerified && proof.rootMeshEmpty &&
                proof.registeredRendererListEmpty && proof.helperReadbackVerified;
            if (!proof.verified) { diagnostic = "spine-empty-fixed-pose-proof-incomplete"; proof = null; return false; }
            return true;
        }

        static bool TryGetSpineTargetField(SpineNullDataSourceComponent sourceRow, string member, out object value)
        {
            value = null;
            var rows = (sourceRow == null ? Array.Empty<SpineNullTargetField>() :
                sourceRow.targetFieldBindings ?? Array.Empty<SpineNullTargetField>())
                .Where(field => field != null && field.member == member &&
                    (field.status == "explicit" || field.status == "resolved_source_engine_default")).ToArray();
            if (rows.Length != 1) return false;
            var field = rows[0];
            if (field.valueType == "bool") value = field.boolValue;
            else if (field.valueType == "number") value = field.numberValue;
            else if (field.valueType == "string") value = field.stringValue;
            return value != null;
        }

        static string SpineFieldListJson(List<string> fields)
        {
            return "[" + String.Join(",", (fields ?? new List<string>()).OrderBy(value => value, StringComparer.Ordinal)
                .Select(value => "\"" + value.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"")) + "]";
        }

        static ProxySpineNonDrawChild[] CaptureSpineNonDrawChildren(ProxyQueueSpec spec, ProxyRendererSpec row,
            GameObject sourceNode, IDictionary<string, GameObject> sourceNodes,
            out ProxySpineNullDataOwner nullDataOwner)
        {
            nullDataOwner = null;
            if (spec == null || row == null || sourceNode == null || sourceNodes == null ||
                row.sourceType != "sp.Skeleton" || row.sourceActive && row.sourceEnabled ||
                sourceNode.activeInHierarchy != row.sourceActive)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NONDRAW_OWNER_SPEC_INVALID: " +
                    (row == null ? "null" : row.sourceComponentId));
            var owner = sourceNode.GetComponent<Graphic>();
            if (owner == null || owner.GetType().FullName != "Spine.Unity.SkeletonGraphic" || owner.enabled != row.sourceEnabled)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NONDRAW_OWNER_COMPONENT_MISMATCH: " + row.sourceComponentId);
            if (!TryReadSpineIdentity(owner, row.sourceComponentId, out _))
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NONDRAW_OWNER_IDENTITY_MISMATCH: " + row.sourceComponentId);
            UnityEngine.Object dataAsset = null;
            if (!TryReadSpineDataAsset(owner, out dataAsset))
            {
                if (!TryBuildSpineNullDataOwnerProof(spec, row, sourceNode, sourceNodes, true,
                    out nullDataOwner, out var nullDataDiagnostic))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NONDRAW_DATA_ASSET_NOT_BOUND: " + row.sourceComponentId +
                        ";dataGuid=<null>;binding=" + nullDataDiagnostic);
                return Array.Empty<ProxySpineNonDrawChild>();
            }
            if (!TryReadSpineDataIdentity(spec, row.sourceComponentId, dataAsset, out var dataEvidence, out var dataGap))
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NONDRAW_DATA_ASSET_NOT_BOUND: " + row.sourceComponentId +
                    ";dataGuid=" + AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(dataAsset)) + ";binding=" + dataGap);
            var registered = new List<CanvasRenderer>();
            if (!TryReadSpineRendererList(owner, out registered) || registered.Distinct().Count() != registered.Count)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NONDRAW_REGISTERED_CHILD_LIST_INVALID: source=" +
                    row.sourceComponentId + ";owner=" + SpineMeshDiagnostic(row.sourceComponentId, owner,
                    owner.canvasRenderer == null ? null : owner.canvasRenderer.GetMesh()) + ";registered=" + registered.Count +
                    ";dataGuid=" + dataEvidence.dataAssetGuid);
            var childGraphics = new List<Graphic>();
            foreach (var renderer in registered)
            {
                var child = renderer == null ? null : renderer.GetComponent<Graphic>();
                if (child == null || renderer.gameObject != child.gameObject ||
                    !IsSpineCanvasSubmesh(child.gameObject, owner) || childGraphics.Contains(child))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NONDRAW_REGISTERED_CHILD_NOT_EXACT: source=" +
                        row.sourceComponentId + ";child=" + (renderer == null ? "<null>" : TransformPath(renderer.transform)) +
                        ";type=" + (child == null ? "<null>" : child.GetType().FullName) + ";dataGuid=" + dataEvidence.dataAssetGuid);
                if (row.sourceActive && row.sourceEnabled == false && child.gameObject.activeInHierarchy && child.enabled)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NONDRAW_ACTIVE_CHILD_GRAPHIC_STILL_ENABLED: source=" +
                        row.sourceComponentId + ";child=" + TransformPath(child.transform) + ";type=" + child.GetType().FullName +
                        ";enabled=" + child.enabled + ";activeSelf=" + child.gameObject.activeSelf +
                        ";activeInHierarchy=" + child.gameObject.activeInHierarchy + ";dataGuid=" + dataEvidence.dataAssetGuid);
                if (!row.sourceActive && child.gameObject.activeInHierarchy)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NONDRAW_INACTIVE_OWNER_CHILD_IS_EFFECTIVE_ACTIVE: source=" +
                        row.sourceComponentId + ";child=" + TransformPath(child.transform) + ";type=" + child.GetType().FullName +
                        ";enabled=" + child.enabled + ";activeSelf=" + child.gameObject.activeSelf +
                        ";dataGuid=" + dataEvidence.dataAssetGuid);
                childGraphics.Add(child);
            }

            var sourceNodeTransforms = new HashSet<Transform>(sourceNodes.Values.Where(node => node != null)
                .Select(node => node.transform));
            foreach (var childGraphic in sourceNode.GetComponentsInChildren<Graphic>(true))
            {
                if (childGraphic == null || childGraphic == owner) continue;
                var cursor = childGraphic.transform.parent;
                var independentlyMapped = false;
                while (cursor != null && cursor != sourceNode.transform)
                {
                    if (sourceNodeTransforms.Contains(cursor)) { independentlyMapped = true; break; }
                    cursor = cursor.parent;
                }
                if (independentlyMapped) continue;
                if (!childGraphics.Contains(childGraphic) || !IsSpineCanvasSubmesh(childGraphic.gameObject, owner))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NONDRAW_UNCLASSIFIED_DESCENDANT_GRAPHIC: source=" +
                        row.sourceComponentId + ";child=" + TransformPath(childGraphic.transform) +
                        ";type=" + childGraphic.GetType().FullName + ";dataGuid=" + dataEvidence.dataAssetGuid);
            }

            if (registered.Count == 0)
            {
                var rootRenderer = owner.canvasRenderer;
                var rootMesh = rootRenderer == null ? null : rootRenderer.GetMesh();
                var rootIndices = rootMesh != null && rootMesh.subMeshCount == 1
                    ? rootMesh.GetIndices(0) : Array.Empty<int>();
                var rootMeshEmpty = rootMesh == null || rootMesh.vertexCount == 0 && rootMesh.subMeshCount == 0;
                var ownerInactiveOrDisabled = !row.sourceActive || !row.sourceEnabled;
                var rootMaterialCount = rootRenderer == null ? -1 : rootRenderer.materialCount;
                if (!ownerInactiveOrDisabled || !rootMeshEmpty || rootMaterialCount != 0)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NONDRAW_EMPTY_REGISTERED_OWNER_NOT_PROVEN: source=" +
                        row.sourceComponentId + ";sourceEnabled=" + row.sourceEnabled + ";sourceActive=" + row.sourceActive +
                        ";root=" + SpineMeshDiagnostic(row.sourceComponentId, owner, rootMesh) +
                        ";rootIndexCount=" + rootIndices.Length + ";dataGuid=" + dataEvidence.dataAssetGuid);
                var rootSha = rootMesh == null || rootMesh.subMeshCount == 0 ? null : MeshFingerprint(rootMesh, 0);
                return new[] { new ProxySpineNonDrawChild { sourceComponentId = row.sourceComponentId, sourceNode = row.node,
                    noDrawReason = !row.sourceActive ? "inactive-owner-no-registered-renderers" : "disabled-owner-no-registered-renderers",
                    sourceDataAssetId = dataEvidence.sourceDataAssetId, sourceDataAssetPath = dataEvidence.dataAssetPath,
                    sourceDataAssetGuid = dataEvidence.dataAssetGuid, sourceOwnerGraphic = owner,
                    sourceDataAssetReference = dataAsset, sourceOwnerEnabled = owner.enabled, sourceNodeActive = row.sourceActive,
                    ownerOnlyNoRegisteredChildren = true, ownerRendererListReadable = true, ownerRendererListEmpty = true,
                    ownerRootMeshEmpty = rootMeshEmpty, ownerRootMeshVertexCount = rootMesh == null ? -1 : rootMesh.vertexCount,
                    ownerRootMeshSubmeshCount = rootMesh == null ? -1 : rootMesh.subMeshCount,
                    ownerRootMeshIndexCount = rootIndices.Length, ownerRootCanvasMaterialCount = rootMaterialCount,
                    ownerRootMeshSha256 = rootSha } };
            }

            var readbacks = new List<ProxySpineNonDrawChild>();
            foreach (var child in childGraphics)
            {
                var renderer = child.canvasRenderer;
                var mesh = renderer == null ? null : renderer.GetMesh();
                var material = child.material;
                var texture = material == null || material.mainTexture == null ? child.mainTexture : material.mainTexture;
                long materialLocal;
                var materialGuid = material == null ? null : AssetGuid(material, out materialLocal);
                var textureGuid = TextureAssetGuid(texture);
                if (String.IsNullOrWhiteSpace(materialGuid) || String.IsNullOrWhiteSpace(textureGuid) ||
                    String.IsNullOrWhiteSpace(AssetDatabase.GetAssetPath(material)))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NONDRAW_CHILD_RESOURCE_NOT_PERSISTENT: source=" +
                        row.sourceComponentId + ";child=" + TransformPath(child.transform) + ";vertices=" +
                        (mesh == null ? -1 : mesh.vertexCount) + ";submeshes=" + (mesh == null ? -1 : mesh.subMeshCount) +
                        ";materials=" + (renderer == null ? -1 : renderer.materialCount) + ";dataGuid=" + dataEvidence.dataAssetGuid);
                readbacks.Add(new ProxySpineNonDrawChild { sourceComponentId = row.sourceComponentId, sourceNode = row.node,
                    noDrawReason = !row.sourceActive ? "inactive-source" : "disabled-source",
                    sourceDataAssetId = dataEvidence.sourceDataAssetId, sourceDataAssetPath = dataEvidence.dataAssetPath,
                    sourceDataAssetGuid = dataEvidence.dataAssetGuid, childPath = SpineChildPath(sourceNode.transform, child.transform),
                    childMaterialGuid = materialGuid, childTextureGuid = textureGuid,
                    sourceOwnerGraphic = owner, sourceChildGraphic = child, sourceChildCanvasRenderer = renderer,
                    sourceDataAssetReference = dataAsset, sourceOwnerEnabled = owner.enabled, sourceNodeActive = row.sourceActive,
                    sourceChildEnabled = child.enabled, sourceChildActiveSelf = child.gameObject.activeSelf,
                    sourceChildActiveInHierarchy = child.gameObject.activeInHierarchy,
                    targetChildEnabled = child.enabled, targetChildActiveInHierarchy = child.gameObject.activeInHierarchy,
                    sourceChildMeshVertexCount = mesh == null ? -1 : mesh.vertexCount,
                    sourceChildMeshSubmeshCount = mesh == null ? -1 : mesh.subMeshCount,
                    sourceChildMaterialCount = renderer == null ? -1 : renderer.materialCount });
            }
            return readbacks.ToArray();
        }

        static bool TryReadSpineIdentity(Graphic owner, string sourceComponentId, out string actualSourceId)
        {
            actualSourceId = null;
            if (owner == null || owner.GetType().FullName != "Spine.Unity.SkeletonGraphic") return false;
            var candidates = owner.GetComponents<Component>().Where(component => component != null &&
                component.GetType().FullName == "UnitySpineSourceIdentity").ToArray();
            if (candidates.Length != 1) return false;
            var marker = candidates[0];
            if (!TryReadSpineMember(marker, "instanceSourceComponentId", out var sourceIdValue) ||
                !TryReadSpineMember(marker, "renderer", out var rendererValue)) return false;
            actualSourceId = sourceIdValue as string;
            return actualSourceId == sourceComponentId && rendererValue as Component == owner;
        }

        static string SpineMeshDiagnostic(string sourceComponentId, Graphic graphic, Mesh mesh)
        {
            var canvas = graphic == null ? null : graphic.canvasRenderer;
            return "source=" + sourceComponentId + ";child=" + (graphic == null ? "<null>" : TransformPath(graphic.transform)) +
                ";vertices=" + (mesh == null ? -1 : mesh.vertexCount) + ";submeshes=" + (mesh == null ? -1 : mesh.subMeshCount) +
                ";materials=" + (canvas == null ? -1 : canvas.materialCount);
        }

        static string SpineObjectReferenceEvidence(UnityEngine.Object value)
        {
            if (value == null) return "<null>";
            long localId;
            var guid = AssetGuid(value, out localId) ?? String.Empty;
            var path = AssetDatabase.GetAssetPath(value) ?? String.Empty;
            var component = value as Component;
            return value.GetType().FullName + ";name=" + value.name + ";assetPath=" + path +
                ";assetGuid=" + guid + ";localId=" + localId +
                ";persistent=" + EditorUtility.IsPersistent(value) +
                ";transformPath=" + (component == null ? String.Empty : TransformPath(component.transform));
        }

        static string SourceGraphicMeshDiagnostic(string sourceComponentId, Graphic graphic, Mesh mesh)
        {
            var canvas = graphic == null ? null : graphic.canvasRenderer;
            var image = graphic as Image;
            var masks = new List<string>();
            for (var parent = graphic == null ? null : graphic.transform.parent; parent != null; parent = parent.parent)
            {
                var mask = parent.GetComponent<Mask>(); var rectMask = parent.GetComponent<RectMask2D>();
                if (mask != null || rectMask != null)
                    masks.Add(parent.name + ":Mask=" + (mask != null && mask.enabled) + ":RectMask2D=" +
                        (rectMask != null && rectMask.enabled));
            }
            return SpineMeshDiagnostic(sourceComponentId, graphic, mesh) +
                ";enabled=" + (graphic != null && graphic.enabled) +
                ";activeSelf=" + (graphic != null && graphic.gameObject.activeSelf) +
                ";activeInHierarchy=" + (graphic != null && graphic.gameObject.activeInHierarchy) +
                ";rendererCull=" + (canvas != null && canvas.cull) +
                ";sprite=" + (image == null || image.sprite == null ? "<null>" : image.sprite.name) +
                ";maskAncestors=" + String.Join("|", masks);
        }

        static ProxySpineOwnerDelegation CreateSpineOwnerDelegation(ProxyRendererSpec row,
            Graphic rootGraphic, Mesh rootMesh, List<Graphic> delegatedGraphics,
            SpineDataIdentityEvidence dataEvidence, UnityEngine.Object dataAsset)
        {
            var sourceDataAssetPath = dataEvidence == null ? null : dataEvidence.dataAssetPath;
            var sourceDataAssetGuid = dataEvidence == null ? null : dataEvidence.dataAssetGuid;
            var rootMaterialCount = rootGraphic.canvasRenderer == null ? -1 : rootGraphic.canvasRenderer.materialCount;
            if (!row.sourceEnabled || !row.sourceActive || !rootGraphic.enabled ||
                !rootGraphic.gameObject.activeInHierarchy)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_OWNER_DELEGATION_SOURCE_INACTIVE: " +
                    SpineMeshDiagnostic(row.sourceComponentId, rootGraphic, rootMesh) + ";dataGuid=" + sourceDataAssetGuid);
            if (dataAsset == null || String.IsNullOrWhiteSpace(sourceDataAssetPath) ||
                !sourceDataAssetPath.StartsWith("Assets/", StringComparison.Ordinal) ||
                String.IsNullOrWhiteSpace(sourceDataAssetGuid) ||
                AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(sourceDataAssetPath) != dataAsset)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_OWNER_DELEGATION_DATA_REFERENCE_NOT_PERSISTENT: " +
                    SpineMeshDiagnostic(row.sourceComponentId, rootGraphic, rootMesh) + ";dataPath=" + sourceDataAssetPath +
                    ";dataGuid=" + sourceDataAssetGuid);
            if (!TryReadSpineIdentity(rootGraphic, row.sourceComponentId, out _))
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_OWNER_DELEGATION_SOURCE_IDENTITY_MISMATCH: " +
                    SpineMeshDiagnostic(row.sourceComponentId, rootGraphic, rootMesh) + ";dataGuid=" + sourceDataAssetGuid);
            var registered = new List<CanvasRenderer>();
            if (!TryReadSpineRendererList(rootGraphic, out registered) || registered.Count == 0 ||
                registered.Distinct().Count() != registered.Count)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_OWNER_DELEGATION_REGISTERED_RENDERERS_MISSING: " +
                    SpineMeshDiagnostic(row.sourceComponentId, rootGraphic, rootMesh) + ";registered=" + registered.Count +
                    ";dataGuid=" + sourceDataAssetGuid);
            if (delegatedGraphics == null || delegatedGraphics.Count != registered.Count ||
                delegatedGraphics.Distinct().Count() != delegatedGraphics.Count)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_OWNER_DELEGATION_CHILD_DENOMINATOR_DIFFERS: " +
                    SpineMeshDiagnostic(row.sourceComponentId, rootGraphic, rootMesh) + ";registered=" + registered.Count +
                    ";collected=" + (delegatedGraphics == null ? -1 : delegatedGraphics.Count) + ";dataGuid=" + sourceDataAssetGuid);

            var vertices = new List<int>(); var submeshes = new List<int>(); var materials = new List<int>();
            var renderers = new List<CanvasRenderer>(); var paths = new List<string>();
            var materialGuids = new List<string>(); var textureGuids = new List<string>();
            foreach (var childGraphic in delegatedGraphics)
            {
                var childRenderer = childGraphic == null ? null : childGraphic.canvasRenderer;
                var childMesh = childRenderer == null ? null : childRenderer.GetMesh();
                var materialCount = childRenderer == null ? -1 : childRenderer.materialCount;
                if (childGraphic == null || !IsSpineCanvasSubmesh(childGraphic.gameObject, rootGraphic) ||
                    childRenderer == null || !registered.Contains(childRenderer) || childMesh == null ||
                    childMesh.vertexCount <= 0 || childMesh.subMeshCount <= 0 || materialCount != childMesh.subMeshCount ||
                    materialCount != 1)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_OWNER_DELEGATION_CHILD_MESH_INVALID: " +
                        SpineMeshDiagnostic(row.sourceComponentId, childGraphic, childMesh) + ";root=" +
                        SpineMeshDiagnostic(row.sourceComponentId, rootGraphic, rootMesh) + ";dataGuid=" + sourceDataAssetGuid);
                var sourceMaterial = childGraphic.material;
                var sourceTexture = sourceMaterial == null || sourceMaterial.mainTexture == null ? childGraphic.mainTexture : sourceMaterial.mainTexture;
                long materialLocal;
                var materialGuid = sourceMaterial == null ? null : AssetGuid(sourceMaterial, out materialLocal);
                var textureGuid = TextureAssetGuid(sourceTexture);
                if (String.IsNullOrWhiteSpace(materialGuid) ||
                    String.IsNullOrWhiteSpace(AssetDatabase.GetAssetPath(sourceMaterial)) ||
                    String.IsNullOrWhiteSpace(textureGuid))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_OWNER_DELEGATION_CHILD_RESOURCE_NOT_PERSISTENT: " +
                        SpineMeshDiagnostic(row.sourceComponentId, childGraphic, childMesh) + ";materialGuid=" + materialGuid +
                        ";textureGuid=" + textureGuid + ";dataGuid=" + sourceDataAssetGuid);
                vertices.Add(childMesh.vertexCount); submeshes.Add(childMesh.subMeshCount); materials.Add(materialCount);
                renderers.Add(childRenderer); paths.Add(SpineChildPath(rootGraphic.transform, childGraphic.transform));
                materialGuids.Add(materialGuid); textureGuids.Add(textureGuid);
            }
            return new ProxySpineOwnerDelegation { sourceComponentId = row.sourceComponentId, sourceNode = row.node,
                sourceDataAssetId = dataEvidence.sourceDataAssetId,
                sourceOwnerGraphic = rootGraphic, sourceDataAssetReference = dataAsset,
                sourceDataAssetPath = sourceDataAssetPath, sourceDataAssetGuid = sourceDataAssetGuid,
                sourceBindingPlanPath = dataEvidence.bindingPlanPath,
                sourceBindingPlanSha256 = dataEvidence.bindingPlanSha256,
                sourceManifestSha256 = dataEvidence.sourceManifestSha256,
                delegatedSourceGraphics = delegatedGraphics.ToArray(), delegatedCanvasRenderers = renderers.ToArray(),
                delegatedChildPaths = paths.ToArray(), delegatedChildMaterialGuids = materialGuids.ToArray(),
                delegatedChildTextureGuids = textureGuids.ToArray(), rootMeshVertexCount = rootMesh == null ? 0 : rootMesh.vertexCount,
                rootMeshSubmeshCount = rootMesh == null ? -1 : rootMesh.subMeshCount, rootCanvasMaterialCount = rootMaterialCount,
                rootMeshWasMissing = rootMesh == null,
                childMeshVertexCounts = vertices.ToArray(), childMeshSubmeshCounts = submeshes.ToArray(),
                childCanvasMaterialCounts = materials.ToArray() };
        }

        static List<Graphic> CollectEventGraphics(ProxyQueueSpec queue, ProxyRendererSpec row, IDictionary<string, GameObject> nodes,
            out ProxySpineOwnerDelegation spineDelegation, bool captureFinalSpineProof = false)
        {
            spineDelegation = null;
            var root = nodes[row.node];
            var result = new List<Graphic>();
            var rootGraphic = root.GetComponent<Graphic>();
            if (rootGraphic == null || rootGraphic.GetType().FullName != row.expectedGraphicType)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_GRAPHIC_MISMATCH: " + row.node + ";source=" + row.sourceComponentId);
            var rootMesh = rootGraphic.canvasRenderer == null ? null : rootGraphic.canvasRenderer.GetMesh();
            var delegateEmptySpineOwner = row.sourceType == "sp.Skeleton" &&
                rootGraphic.GetType().FullName == "Spine.Unity.SkeletonGraphic" && (rootMesh == null || rootMesh.vertexCount == 0);
            if (!delegateEmptySpineOwner) result.Add(rootGraphic);
            void Visit(Transform parent)
            {
                foreach (Transform child in parent)
                {
                    if (IsGeneratedSortProxyRoot(child)) continue;
                    var sourceNode = nodes.FirstOrDefault(pair => pair.Value != null && pair.Value.transform == child).Key;
                    // Every mapped source child is an independent render
                    // boundary, even when that child is inactive, disabled,
                    // or has no current draw event. Its typed renderer row is
                    // handled by its own draw/non-draw contract.
                    if (sourceNode != null && sourceNode != row.node) continue;
                    var graphics = child.GetComponents<Graphic>();
                    if (graphics.Length > 0)
                    {
                        var allowed = row.sourceType == "cc.Label" || row.sourceType == "cc.RichText" ? IsGeneratedTextSubmesh(child.gameObject) :
                            row.sourceType == "sp.Skeleton" && IsSpineCanvasSubmesh(child.gameObject, root.GetComponent<Graphic>());
                        if (!allowed)
                        {
                            var graphicTypes = String.Join(",", graphics.Select(graphic => graphic == null ? "<missing>" : graphic.GetType().FullName).ToArray());
                            throw new InvalidOperationException("STATIC_SORT_PROXY_UNCLASSIFIED_DESCENDANT_GRAPHIC: sourceNode=" + row.node +
                                ";sourceComponent=" + row.sourceComponentId + ";childPath=" + TransformPath(child) +
                                ";graphicTypes=" + graphicTypes);
                        }
                        foreach (var graphic in graphics) result.Add(graphic);
                    }
                    Visit(child);
                }
            }
            Visit(root.transform);
            if (delegateEmptySpineOwner && captureFinalSpineProof)
            {
                if (!TryReadSpineDataAsset(rootGraphic, out var dataAsset))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_OWNER_DELEGATION_DATA_REFERENCE_MISSING: " +
                        SpineMeshDiagnostic(row.sourceComponentId, rootGraphic, rootMesh));
                if (!TryReadSpineDataIdentity(queue, row.sourceComponentId, dataAsset, out var dataEvidence, out var dataDiagnostic))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_OWNER_DELEGATION_DATA_REFERENCE_NOT_PERSISTENT: " +
                        SpineMeshDiagnostic(row.sourceComponentId, rootGraphic, rootMesh) + ";sourceDataGuid=" +
                        (dataEvidence == null ? "<unresolved>" : dataEvidence.dataAssetGuid) + ";sourceDataBinding=" + dataDiagnostic);
                spineDelegation = CreateSpineOwnerDelegation(row, rootGraphic, rootMesh, result, dataEvidence, dataAsset);
            }
            return result;
        }

        static bool MeshHasNoVertices(Mesh mesh) => mesh == null || mesh.vertexCount == 0;

        static bool TryGetSerializedEffectiveActive(ProxyQueueSpec spec, IDictionary<string, GameObject> sourceNodes,
            GameObject sourceNode, out bool serializedEffectiveActive)
        {
            serializedEffectiveActive = false;
            if (spec == null || sourceNode == null || sourceNodes == null ||
                !sourceNodes.TryGetValue(spec.rootScope, out var sourceRoot) || sourceRoot == null) return false;
            var activeRows = spec.sourceNodeActive ?? Array.Empty<ProxySourceActiveSpec>();
            if (activeRows.Any(row => row == null || String.IsNullOrEmpty(row.node)) ||
                activeRows.Select(row => row.node).Distinct(StringComparer.Ordinal).Count() != activeRows.Length) return false;
            var activeById = activeRows.ToDictionary(row => row.node, row => row.active, StringComparer.Ordinal);
            var root = sourceRoot.transform;
            var cursor = sourceNode.transform;
            var seen = new HashSet<string>(StringComparer.Ordinal);
            bool effective = true;
            while (cursor != null)
            {
                var ids = sourceNodes.Where(pair => pair.Value != null && pair.Value.transform == cursor)
                    .Select(pair => pair.Key).ToArray();
                if (ids.Length != 1 || !activeById.TryGetValue(ids[0], out var expectedSelf) ||
                    !seen.Add(ids[0]) || cursor.gameObject.activeSelf != expectedSelf) return false;
                var id = ids[0];
                effective &= cursor.gameObject.activeSelf;
                if (cursor == root)
                {
                    serializedEffectiveActive = effective;
                    return id == spec.rootScope;
                }
                var parent = cursor.parent;
                if (parent == null) return false;
                var parentIds = sourceNodes.Where(pair => pair.Value != null && pair.Value.transform == parent)
                    .Select(pair => pair.Key).ToArray();
                if (parentIds.Length != 1) return false;
                var parentRow = (spec.sourceChildOrder ?? Array.Empty<ProxySourceChildrenSpec>())
                    .SingleOrDefault(row => row != null && row.node == parentIds[0]);
                if (parentRow == null || !(parentRow.children ?? Array.Empty<string>()).Contains(id)) return false;
                cursor = parent;
            }
            return false;
        }

        static bool TryCreateEmptyRendererCarrier(ProxyQueueSpec queueSpec, ProxyRendererSpec spec,
            IDictionary<string, GameObject> sourceNodes, GameObject sourceNode,
            Transform parent, int queueIndex, out NativeStaticSortQueueProxyMarker marker,
            ProxySpineEmptyPoseOwner spineEmptyPoseOwnerProof = null)
        {
            marker = null;
            if (spec == null || sourceNode == null ||
                !TryGetSerializedEffectiveActive(queueSpec, sourceNodes, sourceNode, out var sourceSerializedActive) ||
                sourceSerializedActive != spec.sourceActive) return false;
            var source = sourceNode.GetComponent<Graphic>();
            Component sourceComponent = source;
            string reason = null;
            var sprite = source as Image;
            var text = source as TMPro.TMP_Text;
            var spriteFrameBound = sprite != null && sprite.sprite != null;
            var textIsEmpty = text != null && String.IsNullOrEmpty(text.GetParsedText());
            var fontMissing = text != null && text.font == null;
            var sourceMesh = source == null || source.canvasRenderer == null ? null : source.canvasRenderer.GetMesh();
            if (!spec.sourceActive)
            {
                if (spec.sourceType == "cc.Graphics")
                {
                    var graphics = sourceNode.GetComponent<NativeStaticGraphics>();
                    sourceComponent = graphics;
                    if (source != null || graphics == null || graphics.enabled || graphics.sourceId != spec.sourceComponentId ||
                        graphics.sourceDrawingCommands != spec.sourceDrawingCommands || !spec.sourceCommandsEmpty ||
                        !GraphicsMaterialGuidsMatch(spec.sourceMaterialGuids, graphics.sourceMaterials)) return false;
                }
                else if (source == null || source.GetType().FullName != spec.expectedGraphicType)
                    return false;
                else if (spec.sourceType == "cc.Sprite" && (sprite == null || spriteFrameBound != spec.sourceTextureBound ||
                    source.enabled != (spec.sourceEnabled && spec.sourceTextureBound))) return false;
                else if ((spec.sourceType == "cc.Label" || spec.sourceType == "cc.RichText") &&
                    (text == null || text.enabled != spec.sourceEnabled ||
                     !String.Equals(text.text ?? String.Empty, spec.nativeTextExpectation ?? String.Empty, StringComparison.Ordinal) ||
                     fontMissing != spec.sourceFontMissing)) return false;
                else if (spec.sourceType != "cc.Sprite" && spec.sourceType != "cc.Label" && spec.sourceType != "cc.RichText" &&
                    source.enabled != spec.sourceEnabled) return false;
                reason = "source-node-inactive";
            }
            else if (!spec.sourceEnabled && source != null && !source.enabled)
                reason = "source-renderer-disabled";
            else if (spec.sourceType == "cc.Sprite")
            {
                // UnityImporter deliberately disables Image when the source
                // Sprite has no frame. Keep that distinction from the source
                // component's authored enabled bit.
                var sourceCanvas = source == null ? null : source.canvasRenderer;
                var zeroMesh = MeshHasNoVertices(sourceMesh);
                var zeroMaterials = sourceCanvas != null && sourceCanvas.materialCount == 0;
                if (!spec.sourceEnabled || spec.sourceTextureBound || sprite == null || spriteFrameBound || source.enabled ||
                    sourceNode.GetComponent<Mask>() != null || sourceNode.GetComponent<RectMask2D>() != null ||
                    !zeroMesh && !zeroMaterials)
                    return false;
                reason = zeroMesh ? "source-sprite-frame-null-native-image-disabled-zero-mesh" :
                    "source-sprite-frame-null-native-image-disabled-no-material";
            }
            else if (spec.sourceType == "cc.Label" || spec.sourceType == "cc.RichText")
            {
                if (!spec.sourceEnabled || !spec.sourceTextEmpty || !textIsEmpty || source.enabled != spec.sourceEnabled ||
                    !String.Equals(text.text ?? String.Empty, spec.nativeTextExpectation ?? String.Empty, StringComparison.Ordinal) ||
                    fontMissing != spec.sourceFontMissing || !MeshHasNoVertices(sourceMesh)) return false;
                reason = "source-text-empty-zero-mesh";
            }
            else if (spec.sourceType == "cc.Graphics")
            {
                var graphics = sourceNode.GetComponent<NativeStaticGraphics>();
                sourceComponent = graphics;
                if (source != null || graphics == null || graphics.enabled || !spec.sourceCommandsEmpty ||
                    spec.sourceDrawingCommands != "not-serialized-empty-in-fixed-state" ||
                    graphics.sourceId != spec.sourceComponentId || graphics.sourceDrawingCommands != spec.sourceDrawingCommands ||
                    !GraphicsMaterialGuidsMatch(spec.sourceMaterialGuids, graphics.sourceMaterials)) return false;
                reason = spec.sourceEnabled ? "source-graphics-command-stream-proven-empty" : "source-renderer-disabled";
            }
            else if (spec.sourceType == "sp.Skeleton")
            {
                if (source == null || source.GetType().FullName != "Spine.Unity.SkeletonGraphic" ||
                    source.enabled != spec.sourceEnabled) return false;
                if (spineEmptyPoseOwnerProof != null)
                {
                    if (!spineEmptyPoseOwnerProof.verified || spineEmptyPoseOwnerProof.sourceComponentId != spec.sourceComponentId ||
                        spineEmptyPoseOwnerProof.sourceNode != spec.node || spineEmptyPoseOwnerProof.sourceOwnerGraphic != source ||
                        spineEmptyPoseOwnerProof.sourceDataAssetReference == null ||
                        !TryReadSpineDataAsset(source, out var actualSpineData) ||
                        actualSpineData != spineEmptyPoseOwnerProof.sourceDataAssetReference) return false;
                    reason = "source-spine-fixed-pose-no-renderable-attachments";
                }
                else
                {
                    if (!TryBuildSpineNullDataOwnerProof(queueSpec, spec, sourceNode, sourceNodes, true, out _, out _)) return false;
                    reason = "source-spine-data-reference-absent-no-source-renderable-output";
                }
            }
            else return false;

            var go = new GameObject("__sort_empty_source_" + queueIndex, typeof(RectTransform),
                typeof(NativeStaticSortQueueProxyMarker));
            go.transform.SetParent(parent, false);
            marker = go.GetComponent<NativeStaticSortQueueProxyMarker>();
            marker.kind = queueIndex >= 0 ? "emptyRenderer" : "retainedNonDraw"; marker.sourceNode = spec.node;
            marker.sourceComponentId = spec.sourceComponentId; marker.sourceType = spec.sourceType;
            marker.queueIndex = queueIndex; marker.sourceGraphic = source; marker.sourceComponent = sourceComponent;
            marker.sourceEnabled = spec.sourceEnabled; marker.sourceActive = spec.sourceActive;
            marker.sourceTextureBound = spec.sourceTextureBound; marker.sourceTextEmpty = spec.sourceTextEmpty;
            marker.sourceFontMissing = spec.sourceFontMissing; marker.sourceText = spec.sourceText ?? String.Empty;
            marker.nativeTextExpectation = spec.nativeTextExpectation ?? String.Empty;
            marker.sourceFieldsJson = spec.sourceFieldsJson ?? String.Empty;
            marker.sourceFieldsSha256 = spec.sourceFieldsSha256 ?? String.Empty;
            marker.sourceDrawingCommands = spec.sourceDrawingCommands ?? String.Empty;
            marker.sourceMaterialGuids = spec.sourceMaterialGuids ?? Array.Empty<string>();
            marker.sourceCommandsEmpty = spec.sourceCommandsEmpty;
            marker.spineEmptyPoseOwnerProof = spineEmptyPoseOwnerProof;
            marker.noDrawReason = reason; marker.enabled = false;
            return true;
        }

        static bool IsEmptySpineEmptyPosePlaceholder(ProxySpineEmptyPoseOwner proof)
        {
            // Unity serializes a null inline serializable class as an empty object
            // in JsonUtility readback. Accept only that all-default placeholder
            // when this renderer is not the typed fixed-pose empty event.
            return proof == null || !proof.verified && proof.sourceOwnerGraphic == null && proof.sourceDataAssetReference == null &&
                String.IsNullOrEmpty(proof.sourceComponentId) && String.IsNullOrEmpty(proof.sourceNode) &&
                String.IsNullOrEmpty(proof.sourceDataAssetId) && String.IsNullOrEmpty(proof.sourceDataAssetPath) &&
                String.IsNullOrEmpty(proof.sourceDataAssetGuid) && String.IsNullOrEmpty(proof.sourceBindingPlanPath) &&
                String.IsNullOrEmpty(proof.sourceBindingPlanSha256) && String.IsNullOrEmpty(proof.sourceManifestSha256) &&
                String.IsNullOrEmpty(proof.sourceSkin) && String.IsNullOrEmpty(proof.sourceAnimation) &&
                String.IsNullOrEmpty(proof.actualSkin) && String.IsNullOrEmpty(proof.runtimeDefaultSkinName) &&
                String.IsNullOrEmpty(proof.actualAnimation) && String.IsNullOrEmpty(proof.sourceTargetFieldsJson) &&
                String.IsNullOrEmpty(proof.expectedFieldsJson) && String.IsNullOrEmpty(proof.actualFieldsJson) &&
                proof.fixedPoseSlotCount == 0 && proof.fixedPoseAttachmentCount == 0 && proof.fixedPoseDrawableAttachmentCount == 0 &&
                proof.presentationInstructionCount == 0 && proof.presentationCanvasRendererCount == 0 &&
                proof.rootMeshVertexCount == 0 && proof.rootMeshSubmeshCount == 0 && proof.rootCanvasMaterialCount == 0 &&
                proof.registeredRendererCount == 0 && proof.sourceTimeScale == 0f && proof.nativeTimeScale == 0f &&
                proof.actualTrackTime == 0f && !proof.sourceHasStaticDataReference && !proof.sourcePlanVerified &&
                !proof.sourceIdentityVerified && !proof.sourceDataReferenceVerified && !proof.sourceTimeScaleVerified &&
                !proof.sourceIdentityTimeScaleVerified && !proof.persistentVisiblePose &&
                !proof.sourceBusinessBehaviorDisabled && !proof.sourceCallbacksExecuted && !proof.mappedStaticFieldsVerified &&
                !proof.sdkPoseInitialized && !proof.sdkDataIdentityVerified && !proof.sourceSkinRuntimeVerified &&
                !proof.defaultSkinRuntimeNull && !proof.fixedPoseVerified && !proof.noDrawableAttachmentPoseVerified &&
                !proof.rootMeshEmpty && !proof.registeredRendererListEmpty && !proof.helperReadbackVerified;
        }

        static bool GraphicsMaterialGuidsMatch(string[] expected, Material[] actual)
        {
            expected = expected ?? Array.Empty<string>(); actual = actual ?? Array.Empty<Material>();
            return expected.Length == actual.Length && expected.Select((guid, index) =>
            {
                long localId; return !String.IsNullOrWhiteSpace(guid) && actual[index] != null && AssetGuid(actual[index], out localId) == guid;
            }).All(value => value);
        }

        static ProxyBlockInputReadback[] ReadBlockInputEvents(ProxyQueueSpec spec,
            IDictionary<string, GameObject> sourceNodes, bool loadedPhase, out bool allVerified, out string[] diagnostics)
        {
            var rows = new List<ProxyBlockInputReadback>();
            var gaps = new List<string>();
            var expectedRows = spec.sourceBlockInputEvents ?? Array.Empty<ProxyBlockInputSpec>();
            var ids = expectedRows.Where(row => row != null).Select(row => row.sourceComponentId).ToArray();
            if (ids.Any(String.IsNullOrWhiteSpace) || ids.Distinct(StringComparer.Ordinal).Count() != ids.Length)
                gaps.Add("block-input-source-ids-missing-or-duplicate");
            foreach (var row in expectedRows)
            {
                if (row == null) { gaps.Add("null-block-input-spec"); continue; }
                var node = sourceNodes != null && sourceNodes.TryGetValue(row.node, out var found) ? found : null;
                var blockers = node == null ? Array.Empty<NativeInputBlocker>() : node.GetComponents<NativeInputBlocker>();
                var blocker = blockers.Length == 1 ? blockers[0] : null;
                var surface = blocker == null ? null : blocker.Surface;
                var serializedEffectiveActive = false;
                var activityProof = node != null && TryGetSerializedEffectiveActive(spec, sourceNodes, node,
                    out serializedEffectiveActive);
                var sourceSerializedActive = activityProof && serializedEffectiveActive;
                var sourceHierarchyActiveMatches = !loadedPhase || (node != null && node.activeInHierarchy == row.sourceActive);
                var sourceActivityMatches = activityProof && sourceSerializedActive == row.sourceActive && sourceHierarchyActiveMatches;
                var expectedReused = !String.IsNullOrWhiteSpace(row.expectedSourceGraphicComponentId);
                var actualNativeType = surface == null ? null : surface.GetType().FullName;
                var ownedSurface = blocker != null && blocker.OwnsSurface;
                var surfaceOnNode = surface != null && surface.gameObject == node;
                var expectedTypeMatches = expectedReused
                    ? surface != null && actualNativeType == row.expectedSourceGraphicType && !ownedSurface
                    : surface is NativeInputBlockerSurface && ownedSurface;
                var blockerEnabledMatches = blocker != null && blocker.enabled == row.sourceEnabled;
                var sourceReferenceVerified = node != null && row.sourceType == "cc.BlockInputEvents" &&
                    !String.IsNullOrWhiteSpace(row.sourceComponentId);
                if (expectedReused)
                {
                    var expectedGraphic = surface as Graphic;
                    var planned = (spec.renderers ?? Array.Empty<ProxyRendererSpec>())
                        .Concat(spec.nonDrawRenderers ?? Array.Empty<ProxyRendererSpec>())
                        .SingleOrDefault(candidate => candidate != null &&
                            candidate.sourceComponentId == row.expectedSourceGraphicComponentId);
                    expectedTypeMatches = expectedTypeMatches && planned != null && planned.node == row.node &&
                        expectedGraphic != null && expectedGraphic.gameObject == node;
                }
                var surfaceEnabledExpected = row.sourceEnabled && row.sourceActive;
                var surfaceEnabledMatches = surface != null && (!ownedSurface || surface.enabled == surfaceEnabledExpected);
                var surfaceRaycastMatches = surface != null && surface.raycastTarget ==
                    (ownedSurface ? surfaceEnabledExpected : surfaceEnabledExpected || blocker.PreviousRaycast);
                var mesh = surface == null || surface.canvasRenderer == null ? null : surface.canvasRenderer.GetMesh();
                var meshDeferred = !loadedPhase && mesh == null && ownedSurface;
                var meshVertexCount = mesh == null ? -1 : mesh.vertexCount;
                var meshIndices = mesh == null || mesh.subMeshCount != 1 ? Array.Empty<int>() : mesh.GetIndices(0);
                var colors = mesh == null ? Array.Empty<Color32>() : mesh.colors32;
                var clearMesh = ownedSurface && mesh != null && mesh.vertexCount == 4 && mesh.subMeshCount == 1 &&
                    meshIndices.SequenceEqual(new[] { 0, 1, 2, 2, 3, 0 }) && colors.Length == 4 && colors.All(color => color.a == 0);
                var sourceNoDrawSurfaceState = ownedSurface && (!row.sourceEnabled || !row.sourceActive) &&
                    sourceActivityMatches && surface != null && !surface.enabled && !surface.raycastTarget;
                var meshStateVerified = expectedReused ? true : sourceNoDrawSurfaceState ||
                    (loadedPhase ? clearMesh : clearMesh || meshDeferred);
                var implementationVerified = !expectedReused ? surface is NativeInputBlockerSurface :
                    surface != null && surface.GetType().FullName == row.expectedSourceGraphicType;
                var verified = sourceReferenceVerified && sourceActivityMatches && blockers.Length == 1 && blocker != null && blockerEnabledMatches &&
                    surfaceOnNode && expectedTypeMatches && ownedSurface == !expectedReused && surfaceEnabledMatches &&
                    surfaceRaycastMatches && implementationVerified && meshStateVerified;
                var result = new ProxyBlockInputReadback { sourceComponentId = row.sourceComponentId, sourceNode = row.node,
                    surfaceType = actualNativeType, expectedSourceGraphicComponentId = row.expectedSourceGraphicComponentId,
                    expectedSourceGraphicType = row.expectedSourceGraphicType, nativeSourceGraphicType = actualNativeType,
                    sourceEnabled = row.sourceEnabled, sourceActive = row.sourceActive,
                    sourceActiveSelf = node != null && node.activeSelf,
                    sourceActiveInHierarchy = node != null && node.activeInHierarchy,
                    sourceSerializedActive = sourceSerializedActive,
                    sourceSerializedActiveVerified = activityProof && sourceSerializedActive == row.sourceActive,
                    sourceHierarchyActiveMatchesExpected = sourceHierarchyActiveMatches,
                    sourceReferenceVerified = sourceReferenceVerified, blockerPresent = blocker != null,
                    blockerUnique = blockers.Length == 1, blockerEnabledMatches = blockerEnabledMatches,
                    surfaceReferenceVerified = surface != null, surfaceOwnerMatches = surfaceOnNode,
                    surfaceOwnedMatches = ownedSurface == !expectedReused, surfaceEnabledMatches = surfaceEnabledMatches,
                    surfaceEnabledActual = surface != null && surface.enabled,
                    surfaceRaycastActual = surface != null && surface.raycastTarget,
                    surfaceRaycastMatches = surfaceRaycastMatches, surfaceImplementationVerified = implementationVerified,
                    clearAlphaMeshVerified = expectedReused || clearMesh, surfaceMeshDeferred = meshDeferred,
                    sourceNoDrawStateVerified = sourceNoDrawSurfaceState,
                    surfaceColor = surface == null ? Color.clear : surface.color,
                    surfaceMeshAlphaMin = colors.Length == 0 ? -1 : colors.Min(color => (int)color.a),
                    surfaceMeshAlphaMax = colors.Length == 0 ? -1 : colors.Max(color => (int)color.a),
                    surfaceMeshVertexCount = meshVertexCount, surfaceMeshIndexCount = meshIndices.Length,
                    surfaceMaterialCount = surface == null || surface.canvasRenderer == null ? -1 : surface.canvasRenderer.materialCount,
                    verified = verified };
                rows.Add(result);
                if (!verified) gaps.Add(row.sourceComponentId + ":node=" + row.node + ";blockers=" + blockers.Length +
                    ";surface=" + (actualNativeType ?? "<null>") + ";owned=" + ownedSurface +
                    ";reused=" + expectedReused + ";enabled=" + blockerEnabledMatches +
                    ";sourceActivity=" + sourceActivityMatches + ";serializedActivity=" + sourceSerializedActive +
                    ";hierarchyActivity=" + sourceHierarchyActiveMatches +
                    ";surfaceEnabled=" + surfaceEnabledMatches + ";raycast=" + surfaceRaycastMatches +
                    ";actualSurfaceEnabled=" + (surface != null && surface.enabled) +
                    ";actualSurfaceRaycast=" + (surface != null && surface.raycastTarget) +
                    ";surfaceColor=" + (surface == null ? "<null>" : surface.color.ToString("R")) +
                    ";mesh=" + meshVertexCount + "/" + meshIndices.Length + ";meshAlpha=" +
                    (colors.Length == 0 ? "<none>" : colors.Min(color => (int)color.a) + ".." + colors.Max(color => (int)color.a)) +
                    ";clearAlpha=" + clearMesh + ";sourceNoDraw=" + sourceNoDrawSurfaceState + ";meshDeferred=" + meshDeferred);
            }
            allVerified = gaps.Count == 0 && rows.Count == expectedRows.Length;
            diagnostics = gaps.ToArray();
            return rows.ToArray();
        }

        static ProxySourceMaskIdentityReadback[] ReadSourceMaskIdentities(ProxyQueueSpec spec,
            IDictionary<string, GameObject> sourceNodes, Func<string, Sprite> resolveSprite,
            bool loadedPhase, out bool allVerified, out string[] diagnostics)
        {
            var rows = new List<ProxySourceMaskIdentityReadback>();
            var gaps = new List<string>();
            var expectedRows = spec.sourceMaskIdentities ?? Array.Empty<ProxySourceMaskIdentitySpec>();
            if (expectedRows.Any(row => row == null || String.IsNullOrWhiteSpace(row.sourceId) ||
                String.IsNullOrWhiteSpace(row.node)) ||
                expectedRows.Where(row => row != null).Select(row => row.sourceId).Distinct(StringComparer.Ordinal).Count() != expectedRows.Length)
                gaps.Add("source-mask-identity-spec-missing-or-duplicate");
            foreach (var row in expectedRows)
            {
                if (row == null) continue;
                var node = sourceNodes != null && sourceNodes.TryGetValue(row.node, out var found) ? found : null;
                var serializedEffectiveActive = false;
                var activityProof = node != null && TryGetSerializedEffectiveActive(spec, sourceNodes, node,
                    out serializedEffectiveActive);
                var sourceHierarchyMatches = !loadedPhase || (node != null && node.activeInHierarchy == row.sourceActive);
                var sourceActivityMatches = activityProof && serializedEffectiveActive == row.sourceActive &&
                    node.activeSelf == row.sourceActiveSelf && sourceHierarchyMatches;
                var maskSpec = new MaskSpec { sourceId = row.sourceId, nativeId = row.nativeId, node = row.node,
                    maskType = row.maskType, enabled = row.enabled, inverted = row.inverted,
                    alphaThreshold = row.alphaThreshold, spriteFrameUuid = row.spriteFrameUuid,
                    sourceFieldsJson = row.sourceFieldsJson, sourceMaterialId = row.sourceMaterialId,
                    resolvedSourceMaterialId = row.resolvedSourceMaterialId, sourceEffectId = row.sourceEffectId,
                    sourceEffectName = row.sourceEffectName, sourceEffectDocumentSha256 = row.sourceEffectDocumentSha256,
                    unityMaskShaderPath = row.unityMaskShaderPath, unityMaskShaderSha256 = row.unityMaskShaderSha256,
                    unityMaskMaterialGuid = row.unityMaskMaterialGuid, unityMaskMaterialPath = row.unityMaskMaterialPath };
                var mask = node == null ? null : node.GetComponent<Mask>();
                var identity = node == null ? null : node.GetComponent<NativeStaticMaskIdentity>();
                var graphic = node == null ? null : node.GetComponent<Graphic>();
                var sourceReadback = node == null ? null : UnityStaticMaskSort.ReadStaticMask(maskSpec, node, resolveSprite);
                var typeVerified = row.maskType == 0 ? row.inverted ? graphic is NativeStaticInvertedMaskGraphic : graphic is Image :
                    row.maskType == 1 ? graphic is NativeStaticEllipseMaskGraphic : graphic is Image;
                var sourceMaskFieldsVerified = sourceReadback != null && mask != null && identity != null && graphic != null &&
                    typeVerified && mask.enabled == row.enabled && !mask.showMaskGraphic &&
                    graphic.enabled == row.enabled && !graphic.raycastTarget &&
                    identity.sourceId == row.sourceId && identity.nativeId == row.nativeId &&
                    identity.sourceMaskType == row.maskType && identity.sourceInverted == row.inverted &&
                    identity.sourceAlphaThreshold == row.alphaThreshold && identity.sourceFieldsJson == row.sourceFieldsJson &&
                    identity.spriteFrameUuid == row.spriteFrameUuid && identity.sourceMaterialId == row.sourceMaterialId &&
                    identity.resolvedSourceMaterialId == row.resolvedSourceMaterialId &&
                    identity.sourceEffectId == row.sourceEffectId && identity.sourceEffectName == row.sourceEffectName &&
                    identity.sourceEffectDocumentSha256 == row.sourceEffectDocumentSha256 &&
                    sourceReadback.sourceId == row.sourceId && sourceReadback.node == row.node &&
                    sourceReadback.nativeType == typeof(Mask).FullName && sourceReadback.maskType == row.maskType &&
                    sourceReadback.enabled == row.enabled && sourceReadback.inverted == row.inverted &&
                    sourceReadback.alphaThreshold == row.alphaThreshold && sourceReadback.sourceFieldsJson == row.sourceFieldsJson &&
                    sourceReadback.spriteFrameUuid == row.spriteFrameUuid &&
                    sourceReadback.sourceMaterialId == row.sourceMaterialId &&
                    sourceReadback.resolvedSourceMaterialId == row.resolvedSourceMaterialId &&
                    sourceReadback.sourceEffectId == row.sourceEffectId && sourceReadback.sourceEffectName == row.sourceEffectName &&
                    sourceReadback.sourceEffectDocumentSha256 == row.sourceEffectDocumentSha256;
                var sourceRenderContextDeferred = !loadedPhase && row.maskType == 0 && row.inverted &&
                    node != null && node.GetComponentInParent<Canvas>() == null && sourceMaskFieldsVerified;
                var fieldsVerified = sourceMaskFieldsVerified && (sourceReadback.verified || sourceRenderContextDeferred);
                var verified = sourceActivityMatches && mask != null && identity != null && graphic != null &&
                    typeVerified && fieldsVerified && mask.enabled == row.enabled && graphic.enabled == row.enabled &&
                    !graphic.raycastTarget;
                var result = new ProxySourceMaskIdentityReadback { sourceId = row.sourceId, nativeId = row.nativeId,
                    node = row.node, nativeMaskType = mask == null ? null : mask.GetType().FullName,
                    graphicType = graphic == null ? null : graphic.GetType().FullName,
                    sourceFieldsJson = identity == null ? null : identity.sourceFieldsJson,
                    spriteFrameUuid = identity == null ? null : identity.spriteFrameUuid,
                    sourceMaterialId = identity == null ? null : identity.sourceMaterialId,
                    resolvedSourceMaterialId = identity == null ? null : identity.resolvedSourceMaterialId,
                    sourceEffectId = identity == null ? null : identity.sourceEffectId,
                    sourceEffectName = identity == null ? null : identity.sourceEffectName,
                    sourceEffectDocumentSha256 = identity == null ? null : identity.sourceEffectDocumentSha256,
                    unityMaskMaterialGuid = row.unityMaskMaterialGuid, unityMaskShaderPath = row.unityMaskShaderPath,
                    unityMaskShaderSha256 = row.unityMaskShaderSha256, sourceMaskType = identity == null ? -1 : identity.sourceMaskType,
                    sourceEnabled = row.enabled, sourceInverted = row.inverted, sourceActiveSelfExpected = row.sourceActiveSelf,
                    sourceActiveExpected = row.sourceActive, actualMaskEnabled = mask != null && mask.enabled,
                    actualGraphicEnabled = graphic != null && graphic.enabled, actualRaycastTarget = graphic != null && graphic.raycastTarget,
                    sourceActiveSelf = node != null && node.activeSelf, sourceActiveInHierarchy = node != null && node.activeInHierarchy,
                    sourceSerializedActive = activityProof && serializedEffectiveActive,
                    sourceSerializedActiveVerified = activityProof && serializedEffectiveActive == row.sourceActive &&
                        node != null && node.activeSelf == row.sourceActiveSelf,
                    sourceHierarchyActiveMatchesExpected = sourceHierarchyMatches,
                    sourceReferenceVerified = node != null && sourceNodes.TryGetValue(row.node, out var mappedNode) && mappedNode == node,
                    sourceIdentityVerified = identity != null && fieldsVerified, sourceGraphicTypeVerified = typeVerified,
                    sourceMaskFieldsVerified = sourceMaskFieldsVerified, sourceRenderContextDeferred = sourceRenderContextDeferred,
                    helperMaskReadbackVerified = sourceReadback != null && sourceReadback.verified,
                    sourceActivityStage = loadedPhase ? "loaded-hierarchy" : "persistent-serialized-scope",
                    sourceAlphaThreshold = row.alphaThreshold, actualAlphaThreshold = identity == null ? -1 : identity.sourceAlphaThreshold,
                    verified = verified };
                rows.Add(result);
                if (!verified) gaps.Add(row.sourceId + ":node=" + row.node + ";mask=" + (mask != null) +
                    ";identity=" + (identity != null) + ";graphic=" + (graphic == null ? "<null>" : graphic.GetType().FullName) +
                    ";type=" + typeVerified + ";fields=" + fieldsVerified + ";fieldValues=" + sourceMaskFieldsVerified +
                    ";helperReadback=" + (sourceReadback != null && sourceReadback.verified) +
                    ";persistentCanvasContextDeferred=" + sourceRenderContextDeferred + ";serializedActive=" +
                    (activityProof && serializedEffectiveActive) + ";expectedActive=" + row.sourceActive +
                    ";hierarchy=" + sourceHierarchyMatches + ";graphicEnabled=" + (graphic != null && graphic.enabled) +
                    ";raycast=" + (graphic != null && graphic.raycastTarget));
            }
            allVerified = gaps.Count == 0 && rows.Count == expectedRows.Length;
            diagnostics = gaps.ToArray();
            return rows.ToArray();
        }

        static bool ValidateSourceGraphicCoverage(ProxyQueueSpec spec, IDictionary<string, GameObject> sourceNodes,
            Transform proxyRoot, IList<ProxyGraphicBinding> bindings,
            IEnumerable<ProxySpineOwnerDelegation> spineDelegations,
            IEnumerable<ProxySpineNonDrawChild> spineNonDrawChildren,
            IEnumerable<ProxySpineNullDataOwner> spineNullDataOwners,
            IEnumerable<ProxySpineEmptyPoseOwner> spineEmptyPoseOwners, bool requireGeneratedTextSlots, string verificationPhase,
            IDictionary<NativeStaticSortTextSource, bool> textSourceVerified,
            IEnumerable<ProxyBlockInputReadback> blockInputRows,
            IEnumerable<ProxySourceMaskIdentityReadback> sourceMaskIdentityRows,
            out string missingSourceNode)
        {
            missingSourceNode = null;
            var root = sourceNodes.TryGetValue(spec.rootScope, out var rootObject) ? rootObject : null;
            if (root == null || proxyRoot == null) return false;
            var boundGraphics = new HashSet<Graphic>((bindings ?? Array.Empty<ProxyGraphicBinding>())
                .Where(binding => binding != null && binding.sourceGraphic != null).Select(binding => binding.sourceGraphic));
            foreach (var delegation in spineDelegations ?? Array.Empty<ProxySpineOwnerDelegation>())
                if (delegation != null && delegation.sourceOwnerGraphic != null &&
                    delegation.rootMeshVertexCount == 0 && delegation.delegatedSourceGraphics != null &&
                    delegation.delegatedSourceGraphics.Length > 0)
                    boundGraphics.Add(delegation.sourceOwnerGraphic);
            foreach (var child in spineNonDrawChildren ?? Array.Empty<ProxySpineNonDrawChild>())
                if (child != null && child.sourceChildGraphic != null && child.sourceOwnerGraphic != null &&
                    child.sourceChildCanvasRenderer == child.sourceChildGraphic.canvasRenderer)
                    boundGraphics.Add(child.sourceChildGraphic);
            foreach (var nullDataOwner in spineNullDataOwners ?? Array.Empty<ProxySpineNullDataOwner>())
                if (nullDataOwner != null && nullDataOwner.sourceOwnerGraphic != null && nullDataOwner.verified &&
                    nullDataOwner.nativeDataReferenceNull &&
                    (nullDataOwner.nativeRootMeshEmpty || nullDataOwner.nativeRootMeshDefaultGraphicQuad) &&
                    nullDataOwner.registeredRendererListEmpty)
                    boundGraphics.Add(nullDataOwner.sourceOwnerGraphic);
            foreach (var emptyPoseOwner in spineEmptyPoseOwners ?? Array.Empty<ProxySpineEmptyPoseOwner>())
                if (emptyPoseOwner != null && emptyPoseOwner.sourceOwnerGraphic != null && emptyPoseOwner.verified &&
                    emptyPoseOwner.sourceHasStaticDataReference && emptyPoseOwner.sourceDataAssetReference != null &&
                    emptyPoseOwner.fixedPoseDrawableAttachmentCount == 0 && emptyPoseOwner.rootMeshEmpty &&
                    emptyPoseOwner.registeredRendererListEmpty)
                    boundGraphics.Add(emptyPoseOwner.sourceOwnerGraphic);
            foreach (var inputRow in blockInputRows ?? Array.Empty<ProxyBlockInputReadback>())
                if (inputRow != null && inputRow.verified && String.IsNullOrEmpty(inputRow.expectedSourceGraphicComponentId) &&
                    sourceNodes.TryGetValue(inputRow.sourceNode, out var inputNode) && inputNode != null)
                {
                    var blocker = inputNode.GetComponent<NativeInputBlocker>();
                    if (blocker != null && blocker.OwnsSurface && blocker.Surface is NativeInputBlockerSurface &&
                        blocker.Surface.gameObject == inputNode)
                        boundGraphics.Add(blocker.Surface);
                }
            foreach (var sourceMaskRow in sourceMaskIdentityRows ?? Array.Empty<ProxySourceMaskIdentityReadback>())
                if (sourceMaskRow != null && sourceMaskRow.verified && !sourceMaskRow.sourceActiveExpected &&
                    sourceNodes.TryGetValue(sourceMaskRow.node, out var inactiveMaskNode) && inactiveMaskNode != null)
                {
                    var sourceMask = inactiveMaskNode.GetComponent<Mask>();
                    var sourceIdentity = inactiveMaskNode.GetComponent<NativeStaticMaskIdentity>();
                    var sourceGraphic = inactiveMaskNode.GetComponent<Graphic>();
                    if (sourceMask != null && sourceIdentity != null && sourceGraphic != null &&
                        sourceIdentity.sourceId == sourceMaskRow.sourceId && sourceIdentity.nativeId == sourceMaskRow.nativeId &&
                        sourceIdentity.sourceFieldsJson == sourceMaskRow.sourceFieldsJson && !inactiveMaskNode.activeInHierarchy)
                        boundGraphics.Add(sourceGraphic);
                }
            var textOwners = new HashSet<TMPro.TMP_Text>();
            var textIdentities = proxyRoot.GetComponentsInChildren<NativeStaticSortTextSource>(true)
                .Where(identity => identity != null).ToArray();
            foreach (var identityGroup in textIdentities.GroupBy(identity => identity.sourceComponentId, StringComparer.Ordinal))
            {
                var sourceComponentId = identityGroup.Key;
                if (String.IsNullOrEmpty(sourceComponentId))
                {
                    missingSourceNode = "TMP identity has an empty source component ID";
                    return false;
                }
                var textSpec = (spec.renderers ?? Array.Empty<ProxyRendererSpec>())
                    .SingleOrDefault(row => row != null && row.sourceComponentId == sourceComponentId);
                var expectedTextOwner = textSpec != null && sourceNodes.TryGetValue(textSpec.node, out var textNode) && textNode != null ?
                    textNode.GetComponent<TMPro.TMP_Text>() : null;
                if (expectedTextOwner == null || identityGroup.Any(identity => identity.sourceOwner != expectedTextOwner))
                {
                    missingSourceNode = sourceComponentId + ";expectedOwner=" + (expectedTextOwner != null) +
                        ";identityOwnerMismatch=" + identityGroup.Any(identity => identity.sourceOwner != expectedTextOwner);
                    return false;
                }
                textOwners.Add(expectedTextOwner);
                var identities = identityGroup.ToArray();
                var enumeration = identities[0].textSlotEnumeration;
                try { ValidateTextSlotEnumeration(enumeration, sourceComponentId); }
                catch (Exception error)
                {
                    missingSourceNode = sourceComponentId + ";slotEnumeration=" + error.Message;
                    return false;
                }
                if (identities.Any(identity => !SameTextSlotEnumeration(enumeration, identity.textSlotEnumeration)))
                {
                    missingSourceNode = sourceComponentId + ";slotEnumerationDiffersAcrossIdentities";
                    return false;
                }
                var expectedDrawableSlots = enumeration.rows.Where(row => row.disposition == "drawable")
                    .Select(row => row.slot).OrderBy(slot => slot).ToArray();
                var actualSlots = identities.Select(identity => identity.materialSlot).OrderBy(slot => slot).ToArray();
                if (!expectedDrawableSlots.SequenceEqual(actualSlots) ||
                    actualSlots.Distinct().Count() != actualSlots.Length)
                {
                    missingSourceNode = sourceComponentId + ";drawableSlots=" + String.Join(",", expectedDrawableSlots) +
                        ";identitySlots=" + String.Join(",", actualSlots);
                    return false;
                }
                foreach (var textIdentity in identities)
                {
                    if (!requireGeneratedTextSlots)
                    {
                        var savedSlot = enumeration.rows.SingleOrDefault(row => row.slot == textIdentity.materialSlot);
                        if (textSourceVerified == null || !textSourceVerified.TryGetValue(textIdentity, out var savedTextVerified) ||
                            !savedTextVerified || textIdentity.sourceOwner != expectedTextOwner || savedSlot == null ||
                            savedSlot.disposition != "drawable" || String.IsNullOrEmpty(textIdentity.sourceMeshSha256) ||
                            textIdentity.sourceMeshSha256 != savedSlot.sourceMeshSha256 ||
                            (textIdentity.materialSlot == 0 && (textIdentity.generatedSubmesh ||
                                textIdentity.sourceOwner as Graphic != expectedTextOwner as Graphic)) ||
                            (textIdentity.materialSlot != 0 && !textIdentity.generatedSubmesh))
                        {
                            missingSourceNode = sourceComponentId + ";textSlot=" + textIdentity.materialSlot +
                                ";persistentTextEvidence=" + (textSourceVerified != null &&
                                    textSourceVerified.TryGetValue(textIdentity, out var evidenceOK) && evidenceOK) +
                                ";generatedSubmesh=" + textIdentity.generatedSubmesh + ";sourceOwnerMatches=" +
                                (textIdentity.sourceOwner == expectedTextOwner) + ";savedSlot=" +
                                (savedSlot == null ? "missing" : savedSlot.disposition) + ";phase=" +
                                (verificationPhase ?? "unknown");
                            return false;
                        }
                        if (textIdentity.materialSlot == 0) boundGraphics.Add(expectedTextOwner as Graphic);
                        continue;
                    }
                    if (!UnityStaticSortTextSource.ResolveGeneratedSlot(textIdentity, expectedTextOwner,
                            textIdentity.sourceComponentId, out var slotBinding, out var slotDiagnostic) ||
                        slotBinding == null || slotBinding.sourceGraphic == null)
                    {
                        missingSourceNode = sourceComponentId + ";textSlot=" + textIdentity.materialSlot +
                            ";generatedSubmesh=" + textIdentity.generatedSubmesh + ";sourceOwnerMatches=" +
                            (textIdentity.sourceOwner == expectedTextOwner) + ";phase=" +
                            (verificationPhase ?? "unknown") + ";diagnostic=" +
                            (slotDiagnostic ?? "resolved-binding-null");
                        return false;
                    }
                    var slotBindingIsOwnerGraphic = slotBinding.sourceGraphic == (expectedTextOwner as Graphic) &&
                        slotBinding.generatedSubmesh == false;
                    if (textIdentity.materialSlot == 0 && !textIdentity.generatedSubmesh)
                    {
                        if (!slotBindingIsOwnerGraphic)
                        {
                            missingSourceNode = sourceComponentId + ";ownerSlotIdentityInvalid=" + textIdentity.materialSlot +
                                ";resolvedGraphic=" + (slotBinding.sourceGraphic == null ? "null" : slotBinding.sourceGraphic.GetType().FullName) +
                                ";expectedOwnerGraphic=" + (expectedTextOwner as Graphic != null ?
                                    (expectedTextOwner as Graphic).GetType().FullName : "null") +
                                ";resolvedGenerated=" + slotBinding.generatedSubmesh + ";identityGenerated=" +
                                textIdentity.generatedSubmesh + ";phase=" + (verificationPhase ?? "unknown");
                            return false;
                        }
                    }
                    else if (!textIdentity.generatedSubmesh || !slotBinding.generatedSubmesh ||
                        slotBinding.materialSlot != textIdentity.materialSlot)
                    {
                        missingSourceNode = sourceComponentId + ";generatedSlotIdentityInvalid=" + textIdentity.materialSlot +
                            ";resolvedSlot=" + slotBinding.materialSlot + ";resolvedGenerated=" + slotBinding.generatedSubmesh +
                            ";mode=" + (requireGeneratedTextSlots ? "loaded" : "persistent");
                        return false;
                    }
                    boundGraphics.Add(slotBinding.sourceGraphic);
                }
                var placeholder = enumeration.rows.SingleOrDefault(row => row.disposition == "empty-placeholder");
                if (placeholder != null)
                {
                    var ownerGraphic = expectedTextOwner as Graphic;
                    // Preserve refs for invisible newline/control characters in slot 0. The owner Graphic
                    // is a zero-draw placeholder only when visible refs and actual triangles are absent.
                    if (placeholder.slot != 0 || ownerGraphic == null || placeholder.characterReferences < 0 ||
                        placeholder.visibleCharacterReferences != 0 || placeholder.textInfoNondegenerateTriangleCount != 0 ||
                        placeholder.canvasNondegenerateTriangleCount != 0)
                    {
                        missingSourceNode = sourceComponentId + ";placeholderEvidenceInvalid";
                        return false;
                    }
                    // This is the only non-proxied TMP source Graphic accepted:
                    // typed enumeration proves owner slot 0 is zero-area while
                    // every drawable material slot has a proxy identity above.
                    boundGraphics.Add(ownerGraphic);
                }
            }
            foreach (var marker in proxyRoot.GetComponentsInChildren<NativeStaticSortQueueProxyMarker>(true)
                .Where(marker => marker != null && (marker.kind == "emptyRenderer" || marker.kind == "retainedNonDraw") && marker.sourceGraphic != null))
                boundGraphics.Add(marker.sourceGraphic);
            var allowedMaskGraphics = new HashSet<Graphic>();
            foreach (var nodeId in (spec.masks ?? Array.Empty<ProxyMaskSpec>()).Select(mask => mask.node).Distinct(StringComparer.Ordinal))
                if (sourceNodes.TryGetValue(nodeId, out var maskNode) && maskNode != null)
                {
                    var graphic = maskNode.GetComponent<Graphic>();
                    if (graphic != null) allowedMaskGraphics.Add(graphic);
                }
            var nodeIds = sourceNodes.ToDictionary(pair => pair.Value.transform, pair => pair.Key);
            foreach (var graphic in root.GetComponentsInChildren<Graphic>(true))
            {
                if (graphic == null) continue;
                if (!requireGeneratedTextSlots && graphic is TMPro.TMP_SubMeshUI generatedText &&
                    generatedText.textComponent != null && textOwners.Contains(generatedText.textComponent) &&
                    IsGeneratedTextSubmesh(generatedText.gameObject)) continue;
                var cursor = graphic.transform;
                var generatedProxy = false;
                while (cursor != null && cursor != root.transform)
                {
                    if (IsGeneratedSortProxyRoot(cursor)) { generatedProxy = true; break; }
                    cursor = cursor.parent;
                }
                if (generatedProxy || boundGraphics.Contains(graphic) || allowedMaskGraphics.Contains(graphic)) continue;
                var owner = graphic.transform;
                string sourceId = null;
                while (owner != null && owner != root.transform)
                {
                    if (nodeIds.TryGetValue(owner, out sourceId)) break;
                    owner = owner.parent;
                }
                missingSourceNode = sourceId ?? spec.rootScope;
                var ancestors = new List<string>();
                for (var ancestorCursor = graphic.transform; ancestorCursor != null; ancestorCursor = ancestorCursor.parent)
                {
                    var ids = sourceNodes.Where(pair => pair.Value != null && pair.Value.transform == ancestorCursor)
                        .Select(pair => pair.Key).ToArray();
                    ancestors.Add((ids.Length == 1 ? ids[0] : ids.Length == 0 ? "<unmapped>" :
                        "<ambiguous:" + String.Join(",", ids) + ">") + "(" + ancestorCursor.name + ")");
                    if (ancestorCursor == root.transform) break;
                }
                var sourceIdForNode = sourceId ?? spec.rootScope;
                var plannedDrawRows = (spec.renderers ?? Array.Empty<ProxyRendererSpec>())
                    .Where(row => row != null && row.node == sourceIdForNode).ToArray();
                var plannedNonDrawRows = (spec.nonDrawRenderers ?? Array.Empty<ProxyRendererSpec>())
                    .Where(row => row != null && row.node == sourceIdForNode).ToArray();
                var graphicComponents = graphic.GetComponents<Component>().Where(component => component != null)
                    .Select(component => component.GetType().FullName).ToArray();
                var tmpGenerated = graphic is TMPro.TMP_SubMeshUI tmpSubmesh && tmpSubmesh.textComponent != null &&
                    IsGeneratedTextSubmesh(graphic.gameObject);
                var spineOwners = sourceNodes.Values.Where(candidate => candidate != null)
                    .Select(candidate => candidate.GetComponent<Graphic>())
                    .Where(ownerGraphic => ownerGraphic != null && ownerGraphic.GetType().FullName == "Spine.Unity.SkeletonGraphic" &&
                        IsSpineCanvasSubmesh(graphic.gameObject, ownerGraphic))
                    .Select(ownerGraphic => TransformPath(ownerGraphic.transform)).ToArray();
                missingSourceNode += ";uncoveredGraphicPath=" + TransformPath(graphic.transform) +
                    ";graphicType=" + graphic.GetType().FullName + ";components=" + String.Join(",", graphicComponents) +
                    ";activeSelf=" + graphic.gameObject.activeSelf + ";activeHierarchy=" + graphic.gameObject.activeInHierarchy +
                    ";enabled=" + graphic.enabled + ";canvasMeshVertices=" +
                    (graphic.canvasRenderer == null || graphic.canvasRenderer.GetMesh() == null ? -1 : graphic.canvasRenderer.GetMesh().vertexCount) +
                    ";canvasMaterialCount=" + (graphic.canvasRenderer == null ? -1 : graphic.canvasRenderer.materialCount) +
                    ";ancestors=" + String.Join("|", ancestors) + ";plannedDrawAtNearestNode=" +
                    String.Join(",", plannedDrawRows.Select(row => row.sourceComponentId + ":" + row.sourceType)) +
                    ";plannedNonDrawAtNearestNode=" +
                    String.Join(",", plannedNonDrawRows.Select(row => row.sourceComponentId + ":" + row.sourceType)) +
                    ";typedGeneratedTmp=" + tmpGenerated + ";registeredSpineOwners=" + String.Join(",", spineOwners);
                return false;
            }
            return true;
        }

        static bool ReadSpineEmptyPoseOwnerProof(ProxyQueueSpec queueSpec, ProxyRendererSpec spec,
            IDictionary<string, GameObject> sourceNodes, NativeStaticSortQueueProxyPresenter presenter,
            NativeStaticSortQueueProxyMarker marker, bool loadedReadback,
            out ProxySpineEmptyPoseOwnerReadback readback, out string diagnostic)
        {
            readback = null; diagnostic = null;
            var stored = marker == null ? null : marker.spineEmptyPoseOwnerProof;
            if (queueSpec == null || spec == null || spec.sourceType != "sp.Skeleton" || stored == null ||
                !sourceNodes.TryGetValue(spec.node, out var node) || node == null)
            { diagnostic = "stored-empty-pose-proof-or-source-node-missing"; return false; }
            var presenterProofs = presenter == null ? Array.Empty<ProxySpineEmptyPoseOwner>() :
                presenter.spineEmptyPoseOwners ?? Array.Empty<ProxySpineEmptyPoseOwner>();
            var exactPresenterRows = presenterProofs.Where(proof => proof != null &&
                proof.sourceComponentId == spec.sourceComponentId).ToArray();
            var owner = node.GetComponent<Graphic>();
            var dataAsset = (UnityEngine.Object)null;
            SpineDataIdentityEvidence dataEvidence = null;
            string dataDiagnostic = null;
            var serializedActivityOK = TryGetSerializedEffectiveActive(queueSpec, sourceNodes, node,
                out var serializedEffectiveActive) && serializedEffectiveActive == spec.sourceActive;
            var ownerType = owner == null ? String.Empty : owner.GetType().FullName;
            var ownerTypeMatches = ownerType == "Spine.Unity.SkeletonGraphic";
            var ownerNodeMappingMatches = sourceNodes.TryGetValue(spec.node, out var mappedNode) && mappedNode == node &&
                node != null && node.GetComponent<Graphic>() == owner;
            var ownerReferenceMatchesStored = owner != null && owner == stored.sourceOwnerGraphic;
            var ownerEnabledMatches = owner != null && owner.enabled == spec.sourceEnabled;
            string actualOwnerIdentity = String.Empty;
            var ownerIdentityMatches = owner != null && TryReadSpineIdentity(owner, spec.sourceComponentId, out actualOwnerIdentity) &&
                actualOwnerIdentity == spec.sourceComponentId;
            var sourceIdentityComponents = node == null ? Array.Empty<Component>() : node.GetComponents<Component>()
                .Where(component => component != null && component.GetType().FullName == "UnitySpineSourceIdentity").ToArray();
            var sourceHierarchyActivityMatches = node != null && node.activeInHierarchy == spec.sourceActive;
            var sourceIdentityOK = owner != null && ownerTypeMatches && ownerReferenceMatchesStored && ownerEnabledMatches &&
                ownerNodeMappingMatches && ownerIdentityMatches && serializedActivityOK &&
                (!loadedReadback || sourceHierarchyActivityMatches);
            var dataAssetMemberReadable = owner != null && TryReadSpineDataAsset(owner, out dataAsset) && dataAsset != null;
            var dataAssetReferenceMatchesStored = dataAssetMemberReadable && dataAsset == stored.sourceDataAssetReference;
            var dataAssetIdentityVerified = dataAssetMemberReadable && dataAssetReferenceMatchesStored &&
                TryReadSpineDataIdentity(queueSpec, spec.sourceComponentId, dataAsset, out dataEvidence, out dataDiagnostic);
            var dataAssetIdMatchesStored = dataAssetIdentityVerified && dataEvidence.sourceDataAssetId == stored.sourceDataAssetId;
            var dataAssetPathMatchesStored = dataAssetIdentityVerified && dataEvidence.dataAssetPath == stored.sourceDataAssetPath;
            var dataAssetGuidMatchesStored = dataAssetIdentityVerified && dataEvidence.dataAssetGuid == stored.sourceDataAssetGuid;
            var bindingPlanPathMatchesStored = dataAssetIdentityVerified && dataEvidence.bindingPlanPath == stored.sourceBindingPlanPath;
            var bindingPlanHashMatchesStored = dataAssetIdentityVerified && dataEvidence.bindingPlanSha256 == stored.sourceBindingPlanSha256;
            var manifestMatchesStored = dataAssetIdentityVerified && dataEvidence.sourceManifestSha256 == stored.sourceManifestSha256;
            var dataRefOK = sourceIdentityOK && dataAssetMemberReadable && dataAssetReferenceMatchesStored &&
                dataAssetIdentityVerified && dataAssetIdMatchesStored && dataAssetPathMatchesStored && dataAssetGuidMatchesStored &&
                bindingPlanPathMatchesStored && bindingPlanHashMatchesStored && manifestMatchesStored;
            var presenterProofCardinalityVerified = exactPresenterRows.Length == 1;
            var presenterProof = presenterProofCardinalityVerified ? exactPresenterRows[0] : null;
            var presenterOwnerReferenceVerified = presenterProof != null &&
                presenterProof.sourceOwnerGraphic == stored.sourceOwnerGraphic;
            var presenterDataAssetReferenceVerified = presenterProof != null &&
                presenterProof.sourceDataAssetReference == stored.sourceDataAssetReference;
            var presenterSourceIdentityVerified = presenterProof != null &&
                presenterProof.sourceComponentId == stored.sourceComponentId && presenterProof.sourceNode == stored.sourceNode &&
                presenterProof.sourceDataAssetId == stored.sourceDataAssetId;
            var presenterSkinEvidenceVerified = presenterProof != null &&
                presenterProof.sourceSkin == stored.sourceSkin && presenterProof.sourceAnimation == stored.sourceAnimation &&
                presenterProof.actualSkin == stored.actualSkin &&
                presenterProof.runtimeDefaultSkinName == stored.runtimeDefaultSkinName &&
                presenterProof.defaultSkinRuntimeNull == stored.defaultSkinRuntimeNull;
            var presenterFieldEvidenceVerified = presenterProof != null &&
                presenterProof.expectedFieldsJson == stored.expectedFieldsJson &&
                presenterProof.actualFieldsJson == stored.actualFieldsJson;
            var exactPresenterProof = presenterProofCardinalityVerified && presenterOwnerReferenceVerified &&
                presenterDataAssetReferenceVerified && presenterSourceIdentityVerified && presenterSkinEvidenceVerified &&
                presenterFieldEvidenceVerified;
            var storedSkinRepresentationVerified = SpineSkinRuntimeRepresentationMatches(stored.sourceSkin, stored.actualSkin,
                stored.runtimeDefaultSkinName, stored.sourceSkinRuntimeVerified, stored.defaultSkinRuntimeNull);
            var storedCaptureProofVerified = stored.verified && stored.sourceComponentId == spec.sourceComponentId &&
                stored.sourceNode == spec.node && stored.sourceHasStaticDataReference && stored.sourcePlanVerified &&
                stored.sourceIdentityVerified && stored.sourceDataReferenceVerified && stored.sourceTimeScaleVerified &&
                stored.sourceIdentityTimeScaleVerified && stored.persistentVisiblePose &&
                stored.sourceBusinessBehaviorDisabled && !stored.sourceCallbacksExecuted && stored.mappedStaticFieldsVerified &&
                stored.sdkPoseInitialized && stored.sdkDataIdentityVerified && stored.fixedPoseVerified &&
                stored.noDrawableAttachmentPoseVerified && stored.fixedPoseDrawableAttachmentCount == 0 &&
                stored.rootMeshEmpty && stored.registeredRendererListEmpty && stored.helperReadbackVerified &&
                stored.expectedFieldsJson == stored.actualFieldsJson &&
                storedSkinRepresentationVerified &&
                stored.actualAnimation == stored.sourceAnimation && stored.actualTrackTime == 0f &&
                stored.sourceManifestSha256 == queueSpec.sourceManifestSha256;
            var currentPoseOK = true;
            ProxySpineEmptyPoseOwner currentPose = null;
            string currentPoseDiagnostic = null;
            if (loadedReadback)
            {
                currentPoseOK = TryBuildSpineEmptyPoseOwnerProof(queueSpec, spec, node, sourceNodes, true,
                    out currentPose, out currentPoseDiagnostic) && currentPose != null &&
                    currentPose.sourceDataAssetId == stored.sourceDataAssetId &&
                    currentPose.sourceDataAssetGuid == stored.sourceDataAssetGuid &&
                    currentPose.sourceBindingPlanSha256 == stored.sourceBindingPlanSha256 &&
                    currentPose.sourceSkin == stored.sourceSkin && currentPose.sourceAnimation == stored.sourceAnimation &&
                    SpineSkinRuntimeRepresentationMatches(currentPose.sourceSkin, currentPose.actualSkin,
                        currentPose.runtimeDefaultSkinName, currentPose.sourceSkinRuntimeVerified,
                        currentPose.defaultSkinRuntimeNull) &&
                    currentPose.runtimeDefaultSkinName == stored.runtimeDefaultSkinName &&
                    currentPose.expectedFieldsJson == stored.expectedFieldsJson && currentPose.actualFieldsJson == stored.actualFieldsJson &&
                    currentPose.fixedPoseSlotCount == stored.fixedPoseSlotCount &&
                    currentPose.fixedPoseAttachmentCount == stored.fixedPoseAttachmentCount &&
                    currentPose.fixedPoseDrawableAttachmentCount == 0 && currentPose.actualTrackTime == 0f;
            }
            var loadedPoseVerified = !loadedReadback || currentPoseOK;
            var storedProofOK = storedCaptureProofVerified;
            var verified = sourceIdentityOK && dataRefOK && exactPresenterProof && storedProofOK && currentPoseOK;
            diagnostic = !sourceIdentityOK ? "source-owner-or-source-id-differs" : !dataRefOK ?
                "source-data-reference-or-asset-identity-differs:" + (dataDiagnostic ?? "unknown") : !exactPresenterProof ?
                "presenter-empty-pose-proof-cardinality-or-identity-differs" : !storedProofOK ?
                "stored-empty-pose-capture-evidence-incomplete" : !currentPoseOK ?
                "loaded-sdk-fixed-pose-mismatch:" + (currentPoseDiagnostic ?? "pose-fields-differ") : null;
            var readbackSerializedActivityVerified = TryGetSerializedEffectiveActive(queueSpec, sourceNodes, node,
                out var readbackSerializedActive);
            readback = new ProxySpineEmptyPoseOwnerReadback {
                sourceComponentId = spec.sourceComponentId, sourceNode = spec.node,
                sourceDataAssetId = stored.sourceDataAssetId, sourceDataAssetPath = stored.sourceDataAssetPath,
                sourceDataAssetGuid = stored.sourceDataAssetGuid, sourceBindingPlanPath = stored.sourceBindingPlanPath,
                sourceBindingPlanSha256 = stored.sourceBindingPlanSha256, sourceManifestSha256 = stored.sourceManifestSha256,
                sourceSkin = stored.sourceSkin, sourceAnimation = stored.sourceAnimation,
                actualSkin = loadedReadback && currentPose != null ? currentPose.actualSkin : stored.actualSkin,
                runtimeDefaultSkinName = loadedReadback && currentPose != null ? currentPose.runtimeDefaultSkinName : stored.runtimeDefaultSkinName,
                actualAnimation = loadedReadback && currentPose != null ? currentPose.actualAnimation : stored.actualAnimation,
                sourceTargetFieldsJson = stored.sourceTargetFieldsJson, expectedFieldsJson = stored.expectedFieldsJson,
                actualFieldsJson = loadedReadback && currentPose != null ? currentPose.actualFieldsJson : stored.actualFieldsJson,
                sourceHasStaticDataReference = stored.sourceHasStaticDataReference,
                sourcePlanVerified = stored.sourcePlanVerified, sourceIdentityVerified = sourceIdentityOK,
                sourceDataReferenceVerified = dataRefOK, sourceTimeScaleVerified = stored.sourceTimeScaleVerified,
                sourceIdentityTimeScaleVerified = stored.sourceIdentityTimeScaleVerified,
                persistentVisiblePose = stored.persistentVisiblePose,
                sourceBusinessBehaviorDisabled = stored.sourceBusinessBehaviorDisabled,
                sourceCallbacksExecuted = stored.sourceCallbacksExecuted,
                mappedStaticFieldsVerified = stored.mappedStaticFieldsVerified && stored.expectedFieldsJson == stored.actualFieldsJson,
                sdkPoseInitialized = stored.sdkPoseInitialized && (!loadedReadback || currentPoseOK),
                sdkDataIdentityVerified = stored.sdkDataIdentityVerified && dataRefOK,
                sourceSkinRuntimeVerified = loadedReadback && currentPose != null ? currentPose.sourceSkinRuntimeVerified :
                    stored.sourceSkinRuntimeVerified,
                defaultSkinRuntimeNull = loadedReadback && currentPose != null ? currentPose.defaultSkinRuntimeNull :
                    stored.defaultSkinRuntimeNull,
                fixedPoseVerified = stored.fixedPoseVerified && (!loadedReadback || currentPoseOK),
                noDrawableAttachmentPoseVerified = stored.noDrawableAttachmentPoseVerified &&
                    stored.fixedPoseDrawableAttachmentCount == 0 && (!loadedReadback || currentPoseOK),
                rootMeshEmpty = stored.rootMeshEmpty && (!loadedReadback || currentPoseOK),
                registeredRendererListEmpty = stored.registeredRendererListEmpty && (!loadedReadback || currentPoseOK),
                helperReadbackVerified = stored.helperReadbackVerified && (!loadedReadback || currentPoseOK),
                fixedPoseSlotCount = stored.fixedPoseSlotCount, fixedPoseAttachmentCount = stored.fixedPoseAttachmentCount,
                fixedPoseDrawableAttachmentCount = loadedReadback && currentPose != null ? currentPose.fixedPoseDrawableAttachmentCount :
                    stored.fixedPoseDrawableAttachmentCount,
                presentationInstructionCount = stored.presentationInstructionCount,
                presentationCanvasRendererCount = stored.presentationCanvasRendererCount,
                rootMeshVertexCount = loadedReadback && currentPose != null ? currentPose.rootMeshVertexCount : stored.rootMeshVertexCount,
                rootMeshSubmeshCount = stored.rootMeshSubmeshCount, rootCanvasMaterialCount = stored.rootCanvasMaterialCount,
                registeredRendererCount = stored.registeredRendererCount,
                presenterProofArrayLength = presenterProofs.Length,
                presenterMatchingProofCount = exactPresenterRows.Length,
                sourceTimeScale = stored.sourceTimeScale, nativeTimeScale = stored.nativeTimeScale,
                actualTrackTime = loadedReadback && currentPose != null ? currentPose.actualTrackTime : stored.actualTrackTime,
                presenterFound = presenter != null,
                presenterProofCardinalityVerified = presenterProofCardinalityVerified,
                presenterOwnerReferenceVerified = presenterOwnerReferenceVerified,
                presenterDataAssetReferenceVerified = presenterDataAssetReferenceVerified,
                presenterSourceIdentityVerified = presenterSourceIdentityVerified,
                presenterSkinEvidenceVerified = presenterSkinEvidenceVerified,
                presenterFieldEvidenceVerified = presenterFieldEvidenceVerified,
                storedCaptureProofVerified = storedCaptureProofVerified,
                storedSkinRepresentationVerified = storedSkinRepresentationVerified,
                loadedPoseVerified = loadedPoseVerified,
                currentOwnerPresent = owner != null, currentOwnerTypeMatches = ownerTypeMatches,
                currentOwnerEnabledMatches = ownerEnabledMatches,
                currentOwnerReferenceMatchesStored = ownerReferenceMatchesStored,
                currentOwnerNodeMappingMatches = ownerNodeMappingMatches,
                currentSourceIdentityMatches = ownerIdentityMatches,
                currentSourceSerializedActivityVerified = readbackSerializedActivityVerified,
                currentSourceSerializedActivityMatchesExpected = serializedActivityOK,
                currentSourceHierarchyActivityMatchesExpected = sourceHierarchyActivityMatches,
                currentDataAssetPresent = dataAssetMemberReadable,
                currentDataAssetReferenceMatchesStored = dataAssetReferenceMatchesStored,
                currentDataAssetIdentityVerified = dataAssetIdentityVerified,
                currentDataAssetIdMatchesStored = dataAssetIdMatchesStored,
                currentDataAssetPathMatchesStored = dataAssetPathMatchesStored,
                currentDataAssetGuidMatchesStored = dataAssetGuidMatchesStored,
                currentBindingPlanPathMatchesStored = bindingPlanPathMatchesStored,
                currentBindingPlanHashMatchesStored = bindingPlanHashMatchesStored,
                currentManifestMatchesStored = manifestMatchesStored,
                currentOwnerType = ownerType,
                currentOwnerIdentityComponentId = actualOwnerIdentity,
                currentSourceIdentityComponentType = sourceIdentityComponents.Length == 1 ?
                    sourceIdentityComponents[0].GetType().FullName : String.Empty,
                currentDataAssetType = dataAsset == null ? String.Empty : dataAsset.GetType().FullName,
                currentDataAssetPath = dataEvidence == null ? String.Empty : dataEvidence.dataAssetPath,
                currentDataAssetGuid = dataEvidence == null ? String.Empty : dataEvidence.dataAssetGuid,
                currentDataAssetId = dataEvidence == null ? String.Empty : dataEvidence.sourceDataAssetId,
                currentBindingPlanPath = dataEvidence == null ? String.Empty : dataEvidence.bindingPlanPath,
                currentBindingPlanSha256 = dataEvidence == null ? String.Empty : dataEvidence.bindingPlanSha256,
                currentSourceManifestSha256 = dataEvidence == null ? String.Empty : dataEvidence.sourceManifestSha256,
                currentOwnerEnabled = owner != null && owner.enabled, expectedOwnerEnabled = spec.sourceEnabled,
                sourceSerializedEffectiveActive = readbackSerializedActive, expectedSerializedEffectiveActive = spec.sourceActive,
                sourceHierarchyActive = node != null && node.activeInHierarchy, expectedHierarchyActive = spec.sourceActive,
                diagnostic = verified ? String.Empty : "sourceIdentity=" + sourceIdentityOK +
                    ";ownerPresent=" + (owner != null) + ";ownerType=" + (ownerType ?? String.Empty) +
                    ";ownerTypeExpected=Spine.Unity.SkeletonGraphic;ownerEnabled=" + (owner != null && owner.enabled) +
                    ";ownerEnabledExpected=" + spec.sourceEnabled + ";ownerStoredRef=" + ownerReferenceMatchesStored +
                    ";ownerNodeMap=" + ownerNodeMappingMatches + ";sourceIdentity=" + ownerIdentityMatches +
                ";serializedActivityVerified=" + readbackSerializedActivityVerified +
                    ";serializedActivity=" + serializedEffectiveActive + ";serializedExpected=" + spec.sourceActive +
                    ";hierarchyActive=" + (node != null && node.activeInHierarchy) + ";hierarchyExpected=" + spec.sourceActive +
                    ";dataMember=" + dataAssetMemberReadable + ";dataRefStored=" + dataAssetReferenceMatchesStored +
                    ";dataIdentity=" + dataAssetIdentityVerified + ";dataId=" + dataAssetIdMatchesStored +
                    ";dataPath=" + dataAssetPathMatchesStored + ";dataGuid=" + dataAssetGuidMatchesStored +
                    ";bindingPlanPath=" + bindingPlanPathMatchesStored + ";bindingPlanHash=" + bindingPlanHashMatchesStored +
                    ";manifest=" + manifestMatchesStored + ";dataDiagnostic=" + (dataDiagnostic ?? String.Empty) +
                    ";presenterFound=" + (presenter != null) + ";presenterProofArrayLength=" + presenterProofs.Length +
                    ";presenterMatchingProofCount=" + exactPresenterRows.Length + ";presenterCount=" + presenterProofCardinalityVerified +
                    ";presenterOwnerRef=" + presenterOwnerReferenceVerified + ";presenterDataRef=" +
                    presenterDataAssetReferenceVerified + ";presenterIdentity=" + presenterSourceIdentityVerified +
                    ";presenterSkin=" + presenterSkinEvidenceVerified + ";presenterFields=" +
                    presenterFieldEvidenceVerified + ";storedCapture=" + storedCaptureProofVerified +
                    ";storedSkin=" + storedSkinRepresentationVerified + ";loadedPose=" + loadedPoseVerified +
                    ";currentPoseDiagnostic=" + (currentPoseDiagnostic ?? String.Empty),
                verified = verified
            };
            return verified;
        }

        static ProxyEmptyRendererReadback ReadEmptyRenderer(ProxyQueueSpec queueSpec, ProxyRendererSpec spec,
            IDictionary<string, GameObject> sourceNodes, NativeStaticSortQueueProxyMarker marker,
            Transform proxyRoot, NativeStaticSortQueueProxyPresenter presenter, bool loadedReadback)
        {
            var node = sourceNodes.TryGetValue(spec.node, out var sourceNode) ? sourceNode : null;
            var graphic = node == null ? null : node.GetComponent<Graphic>();
            Component sourceComponent = graphic;
            var staticGraphics = node == null ? null : node.GetComponent<NativeStaticGraphics>();
            if (spec.sourceType == "cc.Graphics") sourceComponent = staticGraphics;
            var image = graphic as Image; var text = graphic as TMPro.TMP_Text;
            var mesh = graphic == null || graphic.canvasRenderer == null ? null : graphic.canvasRenderer.GetMesh();
            var sourceTextureBound = image != null && image.sprite != null;
            var sourceTextEmpty = spec.sourceTextEmpty;
            var sourceFontMissing = text != null && text.font == null;
            var sourceText = text == null ? String.Empty : text.text ?? String.Empty;
            var nativeTextEmpty = text != null && String.IsNullOrEmpty(text.GetParsedText());
            var emptyTextEnumerationRequired = (spec.sourceType == "cc.Label" || spec.sourceType == "cc.RichText") &&
                spec.sourceActive && spec.sourceEnabled && spec.sourceTextEmpty && marker != null &&
                marker.noDrawReason == "source-text-empty-zero-mesh";
            var emptyTextSlotIdentity = marker == null ? null : marker.GetComponent<NativeStaticSortTextSlotEnumerationIdentity>();
            TextSlotEnumerationReadback emptyTextSlotReadback = null;
            var emptyTextSlotEnumerationVerified = !emptyTextEnumerationRequired;
            if (emptyTextEnumerationRequired)
            {
                if (text != null && String.IsNullOrEmpty(spec.sourceText) &&
                    String.IsNullOrEmpty(spec.nativeTextExpectation) && String.IsNullOrEmpty(sourceText) && nativeTextEmpty)
                {
                    if (loadedReadback)
                        emptyTextSlotEnumerationVerified = UnityStaticSortTextSource.ReadEmptyTextSlotEnumerationIdentity(
                            emptyTextSlotIdentity, text, spec.sourceComponentId, out emptyTextSlotReadback);
                    else
                        emptyTextSlotEnumerationVerified = UnityStaticSortTextSource.ReadPersistentEmptyTextSlotEnumerationIdentity(
                            emptyTextSlotIdentity, text, spec.sourceComponentId, out emptyTextSlotReadback);
                }
                else emptyTextSlotReadback = new TextSlotEnumerationReadback {
                    sourceComponentId = spec.sourceComponentId,
                    diagnostic = "TMP_SORT_EMPTY_TEXT_ENUMERATION_SOURCE_TEXT_IS_NOT_EXACTLY_EMPTY" };
            }
            ProxySpineEmptyPoseOwnerReadback spineEmptyPoseReadback = null;
            string spineEmptyPoseDiagnostic = null;
            // Persistent prefab hierarchies can be inactive. Include inactive ancestors so the
            // presenter proof is resolved from the serialized object graph in both read modes.
            var sortPresenter = marker == null ? null : marker.GetComponentInParent<NativeStaticSortQueueProxyPresenter>(true);
            var fixedEmptyPoseMarker = marker != null && marker.noDrawReason ==
                "source-spine-fixed-pose-no-renderable-attachments";
            var spineEmptyPoseVerified = fixedEmptyPoseMarker && ReadSpineEmptyPoseOwnerProof(queueSpec, spec,
                sourceNodes, sortPresenter, marker, loadedReadback,
                out spineEmptyPoseReadback, out spineEmptyPoseDiagnostic);
            ProxySpineNullDataOwner currentNullDataProof = null;
            var spineNullDataVerified = spec.sourceType == "sp.Skeleton" && !fixedEmptyPoseMarker &&
                TryBuildSpineNullDataOwnerProof(queueSpec, spec, node, sourceNodes, loadedReadback,
                    out currentNullDataProof, out _);
            var savedNullDataProofs = presenter == null ? Array.Empty<ProxySpineNullDataOwner>() :
                (presenter.spineNullDataOwners ?? Array.Empty<ProxySpineNullDataOwner>())
                    .Where(row => row != null && row.sourceComponentId == spec.sourceComponentId).ToArray();
            var savedNullDataProof = savedNullDataProofs.Length == 1 ? savedNullDataProofs[0] : null;
            var nullDataCarrierReason = marker != null &&
                marker.noDrawReason == "source-spine-data-reference-absent-no-source-renderable-output";
            var capturedFallbackQuad = savedNullDataProof != null && savedNullDataProof.nativeRootMeshDefaultGraphicQuad;
            var savedTargetFallbackQuadNotCurrentlyPresent = capturedFallbackQuad &&
                currentNullDataProof != null && currentNullDataProof.nativeRootMeshEmpty &&
                savedNullDataProof.rootMeshVertexCount == 4 && savedNullDataProof.rootMeshSubmeshCount == 1 &&
                savedNullDataProof.rootMeshIndexCount == 6 && !String.IsNullOrWhiteSpace(savedNullDataProof.rootMeshSha256) &&
                String.IsNullOrEmpty(currentNullDataProof.rootMeshSha256) &&
                savedNullDataProof.rootMeshGeometryEvidence != null &&
                savedNullDataProof.rootMeshGeometryEvidence.Contains("triangleOrderExact=True") &&
                savedNullDataProof.rootMeshGeometryEvidence.Contains("rectCornersExact=True") &&
                currentNullDataProof.rootCanvasMaterialCount >= 0 && currentNullDataProof.rootCanvasMaterialCount <= 1 &&
                currentNullDataProof.rootCanvasDefaultMaterialOnly && currentNullDataProof.rootSourceBaseDefaultMaterial &&
                currentNullDataProof.rootExtraMaterialModifierCount == 0;
            var sameLiveRootMeshProof = savedNullDataProof != null && currentNullDataProof != null &&
                savedNullDataProof.nativeRootMeshEmpty == currentNullDataProof.nativeRootMeshEmpty &&
                savedNullDataProof.nativeRootMeshDefaultGraphicQuad == currentNullDataProof.nativeRootMeshDefaultGraphicQuad &&
                (currentNullDataProof.nativeRootMeshEmpty
                    ? String.IsNullOrEmpty(savedNullDataProof.rootMeshSha256) && String.IsNullOrEmpty(currentNullDataProof.rootMeshSha256)
                    : savedNullDataProof.rootMeshSha256 == currentNullDataProof.rootMeshSha256);
            var spineNullDataProofVerified = nullDataCarrierReason && spineNullDataVerified &&
                savedNullDataProof != null && currentNullDataProof != null && savedNullDataProof.verified &&
                savedNullDataProof.sourceOwnerGraphic == graphic && currentNullDataProof.sourceOwnerGraphic == graphic &&
                savedNullDataProof.sourceNode == spec.node && currentNullDataProof.sourceNode == spec.node &&
                (sameLiveRootMeshProof || savedTargetFallbackQuadNotCurrentlyPresent);
            var sourceGraphicIndex = presenter == null ? -1 : Array.IndexOf(presenter.sourceGraphics ?? Array.Empty<Graphic>(), graphic);
            var sourceGraphicSuppressedByPresenter = nullDataCarrierReason && loadedReadback &&
                graphic != null && graphic.canvasRenderer != null && graphic.canvasRenderer.cull &&
                sourceGraphicIndex >= 0 && sourceGraphicIndex < (presenter.sourceCullBefore ?? Array.Empty<bool>()).Length;
            var sourceGraphicTypeMatches = spec.sourceType == "cc.Graphics" ? staticGraphics != null &&
                staticGraphics.GetType().FullName == spec.expectedGraphicType : graphic != null && graphic.GetType().FullName == spec.expectedGraphicType;
            var sourceActive = node != null && node.activeInHierarchy;
            var sourceActiveSelf = node != null && node.activeSelf;
            var sourceHierarchyActiveMatchesExpected = sourceActive == spec.sourceActive;
            var sourceSerializedActiveVerified = TryGetSerializedEffectiveActive(queueSpec, sourceNodes, node,
                out var sourceSerializedActive);
            var sourceActivityMatchesExpected = sourceSerializedActiveVerified && sourceSerializedActive == spec.sourceActive &&
                (!loadedReadback || sourceHierarchyActiveMatchesExpected);
            var sourceGraphicStateMatches = sourceGraphicTypeMatches && sourceActivityMatchesExpected &&
                (!spec.sourceActive ? spec.sourceType == "cc.Graphics" ? staticGraphics != null && !staticGraphics.enabled &&
                    staticGraphics.sourceId == spec.sourceComponentId && staticGraphics.sourceDrawingCommands == spec.sourceDrawingCommands &&
                    spec.sourceCommandsEmpty && GraphicsMaterialGuidsMatch(spec.sourceMaterialGuids, staticGraphics.sourceMaterials) :
                    graphic != null &&
                    (spec.sourceType == "cc.Sprite" ? image != null && (image.sprite != null) == spec.sourceTextureBound &&
                        image.enabled == (spec.sourceEnabled && spec.sourceTextureBound) : graphic.enabled == spec.sourceEnabled) &&
                    (spec.sourceType == "cc.Sprite" ? true :
                     spec.sourceType == "cc.Label" || spec.sourceType == "cc.RichText" ? text != null &&
                        String.Equals(sourceText, spec.nativeTextExpectation ?? String.Empty, StringComparison.Ordinal) &&
                        sourceFontMissing == spec.sourceFontMissing : true) :
                 !spec.sourceEnabled ? spec.sourceType == "cc.Graphics" ? staticGraphics != null && !staticGraphics.enabled &&
                    staticGraphics.sourceId == spec.sourceComponentId && staticGraphics.sourceDrawingCommands == spec.sourceDrawingCommands &&
                    spec.sourceCommandsEmpty && GraphicsMaterialGuidsMatch(spec.sourceMaterialGuids, staticGraphics.sourceMaterials) :
                    sourceComponent is Behaviour disabledBehaviour && !disabledBehaviour.enabled :
                 spec.sourceType == "cc.Graphics" ? staticGraphics != null && !staticGraphics.enabled &&
                    staticGraphics.sourceId == spec.sourceComponentId && staticGraphics.sourceDrawingCommands == spec.sourceDrawingCommands &&
                    spec.sourceCommandsEmpty && GraphicsMaterialGuidsMatch(spec.sourceMaterialGuids, staticGraphics.sourceMaterials) :
                 spec.sourceType == "cc.Sprite" ? image != null && !image.enabled && image.sprite == null &&
                    spec.sourceEnabled && !spec.sourceTextureBound :
                 spec.sourceType == "cc.Label" || spec.sourceType == "cc.RichText" ? text != null &&
                    text.enabled == spec.sourceEnabled && nativeTextEmpty == spec.sourceTextEmpty &&
                    String.Equals(sourceText, spec.nativeTextExpectation ?? String.Empty, StringComparison.Ordinal) &&
                    sourceFontMissing == spec.sourceFontMissing :
                 spec.sourceType == "sp.Skeleton" ? graphic != null && graphic.enabled == spec.sourceEnabled &&
                    graphic.GetType().FullName == "Spine.Unity.SkeletonGraphic" && graphic.canvasRenderer != null &&
                    (fixedEmptyPoseMarker ? MeshHasNoVertices(mesh) && graphic.canvasRenderer.materialCount == 0 && spineEmptyPoseVerified :
                        spineNullDataVerified && currentNullDataProof != null &&
                        (currentNullDataProof.nativeRootMeshEmpty
                            ? MeshHasNoVertices(mesh) && graphic.canvasRenderer.materialCount <= 1 &&
                              (graphic.canvasRenderer.materialCount == 0 || currentNullDataProof.rootCanvasDefaultMaterialOnly)
                            : currentNullDataProof.nativeRootMeshDefaultGraphicQuad && mesh != null &&
                              MeshFingerprint(mesh, 0) == currentNullDataProof.rootMeshSha256 &&
                              graphic.canvasRenderer.materialCount == 1)) :
                 !spec.sourceEnabled && graphic != null && !graphic.enabled);
            var noMesh = spec.sourceType == "cc.Graphics" ? spec.sourceCommandsEmpty : MeshHasNoVertices(mesh);
            var markerExpected = marker != null && (marker.kind == "emptyRenderer" || marker.kind == "retainedNonDraw") && marker.sourceNode == spec.node &&
                marker.sourceComponentId == spec.sourceComponentId && marker.sourceType == spec.sourceType &&
                (marker.kind == "emptyRenderer" ? marker.queueIndex >= 0 : marker.queueIndex == -1) && marker.noDrawReason != null && !marker.enabled;
            var expectedSourceFieldsJson = spec.sourceFieldsJson ?? String.Empty;
            var expectedSourceFieldsSha256 = spec.sourceFieldsSha256 ?? String.Empty;
            var expectedSourceDrawingCommands = spec.sourceDrawingCommands ?? String.Empty;
            var fieldsJsonVerified = String.IsNullOrEmpty(expectedSourceFieldsJson) ? String.IsNullOrEmpty(expectedSourceFieldsSha256) :
                HashText(expectedSourceFieldsJson) == expectedSourceFieldsSha256;
            var typedFieldsVerified = markerExpected && marker.sourceGraphic == graphic && marker.sourceComponent == sourceComponent &&
                marker.sourceEnabled == spec.sourceEnabled && marker.sourceActive == spec.sourceActive &&
                marker.sourceTextureBound == spec.sourceTextureBound && marker.sourceTextEmpty == spec.sourceTextEmpty &&
                marker.sourceFontMissing == spec.sourceFontMissing &&
                String.Equals(marker.sourceText ?? String.Empty, spec.sourceText ?? String.Empty, StringComparison.Ordinal) &&
                String.Equals(marker.nativeTextExpectation ?? String.Empty, spec.nativeTextExpectation ?? String.Empty, StringComparison.Ordinal) &&
                String.Equals(marker.sourceFieldsJson ?? String.Empty, expectedSourceFieldsJson, StringComparison.Ordinal) &&
                String.Equals(marker.sourceFieldsSha256 ?? String.Empty, expectedSourceFieldsSha256, StringComparison.Ordinal) &&
                marker.sourceCommandsEmpty == spec.sourceCommandsEmpty &&
                String.Equals(marker.sourceDrawingCommands ?? String.Empty, expectedSourceDrawingCommands, StringComparison.Ordinal) &&
                (marker.sourceMaterialGuids ?? Array.Empty<string>()).SequenceEqual(spec.sourceMaterialGuids ?? Array.Empty<string>()) &&
                (fixedEmptyPoseMarker ? marker.spineEmptyPoseOwnerProof != null &&
                    marker.spineEmptyPoseOwnerProof.sourceComponentId == spec.sourceComponentId &&
                    marker.spineEmptyPoseOwnerProof.sourceNode == spec.node && marker.spineEmptyPoseOwnerProof.verified :
                    IsEmptySpineEmptyPosePlaceholder(marker.spineEmptyPoseOwnerProof)) &&
                fieldsJsonVerified;
            string carrierGuid = null; long carrierLocalId = 0;
            var carrierPersistent = marker != null && AssetDatabase.TryGetGUIDAndLocalFileIdentifier(marker, out carrierGuid, out carrierLocalId) &&
                !String.IsNullOrWhiteSpace(carrierGuid) && carrierLocalId != 0;
            var carrierOwnerScopeVerified = marker != null && proxyRoot != null && IsGeneratedSortProxyRoot(proxyRoot) &&
                (marker.transform == proxyRoot || marker.transform.IsChildOf(proxyRoot)) &&
                marker.sourceGraphic == graphic && marker.sourceComponent == sourceComponent;
            var materialCount = graphic == null || graphic.canvasRenderer == null ? -1 : graphic.canvasRenderer.materialCount;
            var actualMaterialGuids = staticGraphics == null ? Array.Empty<string>() :
                (staticGraphics.sourceMaterials ?? Array.Empty<Material>()).Select(material =>
                { long id; return material == null ? null : AssetGuid(material, out id); }).ToArray();
            var expectedReason = spec.sourceType == "sp.Skeleton" && spec.sourceActive && spec.sourceEnabled ?
                fixedEmptyPoseMarker ? "source-spine-fixed-pose-no-renderable-attachments" :
                    "source-spine-data-reference-absent-no-source-renderable-output" :
                !spec.sourceActive ? "source-node-inactive" : !spec.sourceEnabled ? "source-renderer-disabled" :
                spec.sourceType == "cc.Sprite" ? MeshHasNoVertices(mesh)
                    ? "source-sprite-frame-null-native-image-disabled-zero-mesh"
                    : "source-sprite-frame-null-native-image-disabled-no-material" :
                spec.sourceType == "cc.Label" || spec.sourceType == "cc.RichText" ? "source-text-empty-zero-mesh" :
                spec.sourceType == "cc.Graphics" ? "source-graphics-command-stream-proven-empty" : "source-renderer-disabled";
            var nullSpriteNoMaterialReason = spec.sourceType == "cc.Sprite" && !spec.sourceTextureBound &&
                image != null && image.sprite == null && !image.enabled && materialCount == 0 &&
                node != null && node.GetComponent<Mask>() == null && node.GetComponent<RectMask2D>() == null &&
                marker != null && marker.noDrawReason == "source-sprite-frame-null-native-image-disabled-no-material";
            var nullSpriteZeroMeshReason = spec.sourceType == "cc.Sprite" && !spec.sourceTextureBound &&
                image != null && image.sprite == null && !image.enabled && noMesh &&
                node != null && node.GetComponent<Mask>() == null && node.GetComponent<RectMask2D>() == null &&
                marker != null && marker.noDrawReason == "source-sprite-frame-null-native-image-disabled-zero-mesh";
            var markerReasonVerified = marker != null && (marker.noDrawReason == expectedReason ||
                nullSpriteNoMaterialReason || nullSpriteZeroMeshReason);
            var noMaterialSpriteProven = spec.sourceType == "cc.Sprite" && spec.sourceTextureBound == false &&
                image != null && image.sprite == null && !image.enabled && materialCount == 0 &&
                node != null && node.GetComponent<Mask>() == null && node.GetComponent<RectMask2D>() == null;
            var carrierPresent = loadedReadback ? carrierOwnerScopeVerified : carrierPersistent;
            var verified = sourceGraphicStateMatches && (noMesh || nullDataCarrierReason && spineNullDataProofVerified || !spec.sourceActive ||
                    (!spec.sourceEnabled && graphic != null && !graphic.enabled) || noMaterialSpriteProven) &&
                typedFieldsVerified && carrierPresent && markerReasonVerified &&
                emptyTextSlotEnumerationVerified &&
                (!nullDataCarrierReason || !loadedReadback || sourceGraphicSuppressedByPresenter) &&
                (!nullDataCarrierReason || spineNullDataProofVerified) &&
                (!fixedEmptyPoseMarker || spineEmptyPoseVerified) &&
                (spec.sourceType != "cc.Graphics" || actualMaterialGuids.SequenceEqual(spec.sourceMaterialGuids ?? Array.Empty<string>()));
            return new ProxyEmptyRendererReadback { sourceComponentId = spec.sourceComponentId, sourceNode = spec.node,
                sourceType = spec.sourceType, noDrawReason = marker == null ? null : marker.noDrawReason,
                sourceComponentType = sourceComponent == null ? null : sourceComponent.GetType().FullName,
                sourceFieldsSha256 = marker == null ? null : marker.sourceFieldsSha256,
                sourceDrawingCommands = marker == null ? null : marker.sourceDrawingCommands,
                sourceText = marker == null ? null : marker.sourceText,
                sourceActivityStage = loadedReadback ? "loaded-hierarchy-plus-serialized-scope" : "persistent-serialized-scope",
                nativeTextExpectation = spec.nativeTextExpectation,
                nativeText = text == null ? String.Empty : text.text ?? String.Empty,
                sourceMaterialGuids = marker == null ? null : marker.sourceMaterialGuids,
                actualSourceMaterialGuids = actualMaterialGuids,
                carrierGuid = carrierPersistent ? carrierGuid : String.Empty,
                carrierLocalFileId = carrierPersistent ? carrierLocalId : 0,
                sourceEnabled = spec.sourceEnabled, sourceActive = spec.sourceActive,
                sourceActiveSelf = sourceActiveSelf, sourceSerializedActive = sourceSerializedActive,
                sourceSerializedActiveVerified = sourceSerializedActiveVerified,
                sourceHierarchyActiveMatchesExpected = sourceHierarchyActiveMatchesExpected,
                sourceActivityMatchesExpected = sourceActivityMatchesExpected,
                nativeGraphicEnabled = graphic != null && graphic.enabled,
                nativeComponentEnabled = sourceComponent is Behaviour behaviour && behaviour.enabled,
                sourceActiveInHierarchy = sourceActive,
                sourceTextureBound = spec.sourceTextureBound, nativeTextureBound = sourceTextureBound,
                sourceTextEmpty = spec.sourceTextEmpty, nativeTextEmpty = nativeTextEmpty,
                sourceFontMissing = spec.sourceFontMissing, nativeFontMissing = sourceFontMissing,
                sourceMeshPresent = mesh != null && mesh.vertexCount > 0, sourceMeshVertexCount = mesh == null ? 0 : mesh.vertexCount,
                sourceCanvasMaterialCount = materialCount, actualQueueIndex = marker == null ? -1 : marker.queueIndex,
                spineEmptyPoseProof = spineEmptyPoseReadback,
                emptyTextSlotEnumerationProof = emptyTextSlotReadback,
                emptyTextSlotEnumerationVerified = emptyTextSlotEnumerationVerified,
                carrierPresent = carrierPresent, carrierAssetIdentityVerified = carrierPersistent,
                carrierOwnerScopeVerified = carrierOwnerScopeVerified,
                sourceSpineNullDataProofVerified = spineNullDataProofVerified,
                sourceSpineNullDataRootFallbackQuad = capturedFallbackQuad,
                sourceSpineNullDataRootMeshCacheAbsent = savedTargetFallbackQuadNotCurrentlyPresent,
                sourceSpineNullDataCurrentDefaultMaterialOnly = currentNullDataProof != null && currentNullDataProof.rootCanvasDefaultMaterialOnly,
                sourceNoDrawEvidenceVerified = spineNullDataProofVerified,
                sourceGraphicSuppressedByPresenter = sourceGraphicSuppressedByPresenter,
                spineNullDataRootMeshSha256 = savedNullDataProof == null ? String.Empty : savedNullDataProof.rootMeshSha256 ?? String.Empty,
                sourceReferenceVerified = marker != null && marker.sourceComponent == sourceComponent,
                typedFieldsVerified = typedFieldsVerified, sourceCommandsEmpty = spec.sourceCommandsEmpty,
                nativeCommandsEmpty = spec.sourceType == "cc.Graphics" && staticGraphics != null &&
                    staticGraphics.sourceDrawingCommands == "not-serialized-empty-in-fixed-state", verified = verified };
        }

        static string SourceNullSpriteProofDiagnostic(ProxyRendererSpec spec, GameObject sourceNode)
        {
            var image = sourceNode == null ? null : sourceNode.GetComponent<Image>();
            var canvas = image == null ? null : image.canvasRenderer;
            var mesh = canvas == null ? null : canvas.GetMesh();
            var sameNodeMask = sourceNode != null && (sourceNode.GetComponent<Mask>() != null ||
                sourceNode.GetComponent<RectMask2D>() != null);
            return "node=" + (sourceNode == null ? "null" : sourceNode.name) +
                ";plannedActive=" + (spec != null && spec.sourceActive) +
                ";actualActiveSelf=" + (sourceNode != null && sourceNode.activeSelf) +
                ";actualActiveHierarchy=" + (sourceNode != null && sourceNode.activeInHierarchy) +
                ";plannedEnabled=" + (spec != null && spec.sourceEnabled) +
                ";actualImageEnabled=" + (image != null && image.enabled) +
                ";plannedTextureBound=" + (spec != null && spec.sourceTextureBound) +
                ";actualSpriteBound=" + (image != null && image.sprite != null) +
                ";canvasRenderer=" + (canvas != null) + ";canvasCull=" + (canvas != null && canvas.cull) +
                ";meshVertices=" + (mesh == null ? -1 : mesh.vertexCount) +
                ";meshSubmeshes=" + (mesh == null ? -1 : mesh.subMeshCount) +
                ";materialCount=" + (canvas == null ? -1 : canvas.materialCount) +
                ";sameNodeMask=" + sameNodeMask;
        }

        static NativeStaticSortQueueProxyGraphic CreateProxyGraphic(Graphic source, Graphic sourceOwnerGraphic, string sourceNodeId,
            string sourceComponentId, string sourceType, int queueIndex, int submeshIndex,
            string expectedGraphicType, bool generatedSourceChild, Transform parent, string meshFolder,
            TextSlotBinding textBinding, out ProxyGraphicBinding binding)
        {
            // Callers prepare the exact source renderer mesh before reaching
            // this method. A generic Canvas rebuild here would overwrite the
            // pinned Spine SDK's final SkeletonGraphic submesh with a RawImage quad.
            var stableSourceGraphic = textBinding == null ? source : (Graphic)textBinding.owner;
            var sourceCanvasRenderer = source.canvasRenderer;
            var sourceMesh = textBinding != null ? textBinding.sourceMesh : sourceCanvasRenderer == null ? null : sourceCanvasRenderer.GetMesh();
            if (sourceMesh == null || sourceMesh.vertexCount == 0)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_MESH_EMPTY: " + sourceComponentId);
            if (HasMalformedUvChannels(sourceMesh))
                throw new InvalidOperationException("STATIC_SORT_PROXY_MALFORMED_UV_CHANNELS: " + sourceComponentId);
            var materialCount = Math.Max(1, sourceCanvasRenderer.materialCount);
            if (sourceMesh.subMeshCount != materialCount)
                throw new InvalidOperationException("STATIC_SORT_PROXY_MATERIAL_MESH_SUBMESH_MISMATCH: " + sourceComponentId);
            var rt = source.transform as RectTransform;
            if (rt == null) throw new InvalidOperationException("STATIC_SORT_PROXY_RECTTRANSFORM_MISSING: " + sourceComponentId);
            var proxyObject = new GameObject("__sort_proxy_" + queueIndex + "_" + submeshIndex,
                typeof(RectTransform), typeof(CanvasRenderer), typeof(NativeStaticSortQueueProxyGraphic),
                typeof(NativeStaticSortQueueProxyMarker), typeof(CanvasGroup));
            var proxyRect = proxyObject.GetComponent<RectTransform>();
            CopyWorldRect(rt, proxyRect, parent, sourceComponentId, out var transformCaptureDiagnostic);
            // Graphic.material is the authored base material. CanvasRenderer's
            // installed material may already include an ancestor Mask stencil
            // modifier, so it must never seed the proxy material.
            var sourceMaterial = textBinding != null ? textBinding.sourceMaterial : source.material;
            if (textBinding != null && sourceMaterial == null)
                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SOURCE_MATERIAL_MISSING: " + sourceComponentId);
            if (sourceMaterial == null) sourceMaterial = Canvas.GetDefaultCanvasMaterial();
            if (sourceMaterial == null) throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_MATERIAL_MISSING: " + sourceComponentId);
            var sourceMaterialFingerprint = MaterialFingerprint(sourceMaterial);
            var texture = textBinding != null ? textBinding.sourceTexture : sourceMaterial.mainTexture ?? source.mainTexture;
            if (textBinding != null && texture == null)
                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SOURCE_TEXTURE_MISSING: " + sourceComponentId);
            var mesh = PersistMesh(sourceMesh, submeshIndex, source.transform, proxyRect,
                sourceComponentId, submeshIndex, meshFolder, out var sourceMeshSha, out var meshSha, out var meshGuid);
            var material = textBinding != null ? textBinding.proxyMaterial : sourceMaterial;
            if (textBinding != null && material == null)
                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_PROXY_MATERIAL_MISSING: " + sourceComponentId);
            if (string.IsNullOrEmpty(AssetDatabase.GetAssetPath(material)) ||
                !AssetDatabase.GetAssetPath(material).StartsWith("Assets/", StringComparison.Ordinal))
            {
                if (textBinding != null)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_PROXY_MATERIAL_NOT_PERSISTENT: " + sourceComponentId);
                var materialPath = meshFolder.TrimEnd('/') + "/QueueMaterial_" + HashText(sourceComponentId + sourceMaterialFingerprint).Substring(0, 20) + ".mat";
                var persisted = AssetDatabase.LoadAssetAtPath<Material>(materialPath);
                if (persisted == null)
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(materialPath));
                    persisted = new Material(material) { name = material.name };
                    AssetDatabase.CreateAsset(persisted, materialPath);
                }
                material = persisted;
            }
            var materialGuid = AssetGuid(material, out var materialLocal);
            var textureGuid = TextureAssetGuid(texture);
            if (materialGuid == null || textureGuid == null)
                throw new InvalidOperationException("STATIC_SORT_PROXY_RESOURCE_NOT_PERSISTENT: " + sourceComponentId);
            var proxy = proxyObject.GetComponent<NativeStaticSortQueueProxyGraphic>();
            proxy.sourceGraphic = stableSourceGraphic; proxy.sourceOwnerGraphic = sourceOwnerGraphic;
            proxy.sourceNodeId = sourceNodeId; proxy.sourceComponentId = sourceComponentId;
            proxy.sourceType = sourceType; proxy.queueIndex = queueIndex; proxy.submeshIndex = submeshIndex;
            proxy.expectedSourceGraphicType = expectedGraphicType; proxy.generatedSourceChild = generatedSourceChild;
            proxy.sourceRendererAlpha = sourceCanvasRenderer.GetAlpha();
            proxy.sourceInheritedAlpha = sourceCanvasRenderer.GetInheritedAlpha();
            proxy.sourceOpacityCaptured = true;
            proxy.proxyMesh = mesh; proxy.proxyTexture = texture; proxy.proxyBaseMaterial = material;
            proxy.sourceMeshSha256 = sourceMeshSha; proxy.meshContentSha256 = meshSha; proxy.meshAssetGuid = meshGuid;
            proxy.sourceUvChannelVertexCounts = UvChannelVertexCounts(sourceMesh);
            proxy.sourceUvChannelDimensions = UvChannelDimensions(sourceMesh);
            proxy.sourceMaterialGuid = materialGuid; proxy.sourceTextureGuid = textureGuid;
            proxy.sourceBaseTexture = texture; proxy.sourceMaterialFingerprint = sourceMaterialFingerprint;
            proxy.transformCaptureDiagnosticJson = transformCaptureDiagnostic;
            proxy.raycastTarget = false; proxy.color = Color.white;
            var opacity = proxyObject.GetComponent<CanvasGroup>();
            opacity.ignoreParentGroups = true;
            opacity.alpha = proxy.sourceInheritedAlpha;
            proxyObject.GetComponent<CanvasRenderer>().SetAlpha(proxy.sourceRendererAlpha);
            var marker = proxyObject.GetComponent<NativeStaticSortQueueProxyMarker>();
            marker.kind = "renderer"; marker.sourceNode = sourceNodeId; marker.sourceComponentId = sourceComponentId;
            marker.sourceType = sourceType; marker.queueIndex = queueIndex;
            if (textBinding != null) UnityStaticSortTextSource.Attach(proxyObject, textBinding, mesh, meshSha);
            binding = new ProxyGraphicBinding { sourceGraphic = stableSourceGraphic,
                sourceCanvasRenderer = stableSourceGraphic == null ? null : stableSourceGraphic.canvasRenderer,
                proxyGraphics = new[] { proxy }, sourceGraphicEnabled = stableSourceGraphic != null && stableSourceGraphic.enabled,
                sourceCanvasCullBefore = stableSourceGraphic != null && stableSourceGraphic.canvasRenderer != null &&
                    stableSourceGraphic.canvasRenderer.cull };
            return proxy;
        }

        static void SynchronizeBlockInputSourceActivity(ProxyQueueSpec spec,
            IDictionary<string, GameObject> sourceNodes)
        {
            foreach (var row in spec.sourceBlockInputEvents ?? Array.Empty<ProxyBlockInputSpec>())
            {
                if (row == null || String.IsNullOrWhiteSpace(row.sourceComponentId) ||
                    !sourceNodes.TryGetValue(row.node, out var node) || node == null)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_BLOCK_INPUT_SOURCE_NODE_MISSING:" +
                        (row == null ? "<null>" : row.sourceComponentId));
                var blockers = node.GetComponents<NativeInputBlocker>();
                if (blockers.Length != 1 || blockers[0] == null ||
                    !blockers[0].SynchronizeSourceActivity(row.sourceEnabled, row.sourceActive))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_BLOCK_INPUT_SOURCE_ACTIVITY_SYNC_FAILED:" +
                        row.sourceComponentId + ";blockers=" + blockers.Length +
                        ";plannedEnabled=" + row.sourceEnabled + ";plannedEffectiveActive=" + row.sourceActive +
                        ";actualComponentEnabled=" + (blockers.Length == 1 && blockers[0] != null && blockers[0].enabled) +
                        ";surface=" + (blockers.Length == 1 && blockers[0] != null && blockers[0].Surface != null
                            ? blockers[0].Surface.GetType().FullName : "<missing>"));
            }
        }

        public static ProxyQueueReadback CreateStaticSortQueueProxy(ProxyQueueSpec spec,
            IDictionary<string, GameObject> sourceNodes, Func<string, Sprite> resolveSprite,
            Func<MaskSpec, Material> resolveMaskMaterial)
        {
            if (spec == null || sourceNodes == null || !sourceNodes.TryGetValue(spec.rootScope, out var sourceRoot) || sourceRoot == null)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_ROOT_MISSING");
            using (var capture = new NestedProxyCaptureScope(NestedProxyRoots(sourceRoot)))
                return CreateStaticSortQueueProxyCore(spec, sourceNodes, resolveSprite, resolveMaskMaterial, capture);
        }

        static ProxyQueueReadback CreateStaticSortQueueProxyCore(ProxyQueueSpec spec,
            IDictionary<string, GameObject> sourceNodes, Func<string, Sprite> resolveSprite,
            Func<MaskSpec, Material> resolveMaskMaterial, NestedProxyCaptureScope nestedCapture)
        {
            if (spec == null || sourceNodes == null || string.IsNullOrEmpty(spec.rootScope))
                throw new InvalidOperationException("STATIC_SORT_PROXY_PLAN_INVALID");
            if (string.IsNullOrEmpty(spec.meshAssetFolder) || !spec.meshAssetFolder.StartsWith("Assets/", StringComparison.Ordinal))
                throw new InvalidOperationException("STATIC_SORT_PROXY_ASSET_FOLDER_INVALID");
            if (!sourceNodes.TryGetValue(spec.rootScope, out var sourceRoot) || sourceRoot == null)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_ROOT_MISSING");
            if (sourceRoot.GetComponentsInChildren<NativeStaticSortQueueProxyMarker>(true).Any(marker => marker != null &&
                marker.kind == "root" && marker.sourceRootOwner == sourceRoot && IsGeneratedSortProxyRoot(marker.transform)))
                throw new InvalidOperationException("STATIC_SORT_PROXY_ROOT_ALREADY_EXISTS: " + spec.rootScope);
            SynchronizeBlockInputSourceActivity(spec, sourceNodes);
            Canvas.ForceUpdateCanvases();
            if (!AssetDatabase.IsValidFolder(spec.meshAssetFolder))
            {
                var parent = Path.GetDirectoryName(spec.meshAssetFolder).Replace("\\", "/");
                var leaf = Path.GetFileName(spec.meshAssetFolder);
                if (!AssetDatabase.IsValidFolder(parent)) throw new InvalidOperationException("STATIC_SORT_PROXY_PARENT_ASSET_FOLDER_MISSING: " + parent);
                AssetDatabase.CreateFolder(parent, leaf);
            }
            var ownerTextStyles = PrepareSourceGeometryForCapture(spec, sourceNodes, sourceRoot);

            var sourceRendererByComponent = (spec.renderers ?? Array.Empty<ProxyRendererSpec>()).ToDictionary(row => row.sourceComponentId);
            var maskByNode = (spec.masks ?? Array.Empty<ProxyMaskSpec>()).ToDictionary(row => row.node);
            var sourceParent = sourceRoot.transform;
            var proxyRootObject = new GameObject("__NativeStaticSortQueueProxy_" + HashText(spec.rootScope).Substring(0, 12),
                typeof(RectTransform), typeof(LayoutElement));
            proxyRootObject.GetComponent<LayoutElement>().ignoreLayout = true;
            var proxyRoot = proxyRootObject.GetComponent<RectTransform>();
            var sourceRootRect = sourceRoot.transform as RectTransform;
            if (sourceRootRect == null) throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_ROOT_RECTTRANSFORM_REQUIRED");
            CopyWorldRect(sourceRootRect, proxyRoot, sourceParent, spec.rootScope);
            var rootMarker = proxyRootObject.AddComponent<NativeStaticSortQueueProxyMarker>();
            rootMarker.kind = "root"; rootMarker.sourceNode = spec.rootScope; rootMarker.sourceRootOwner = sourceRoot;
            var bindings = new List<ProxyGraphicBinding>();
            var pendingSpineGraphics = new List<PendingSpineGraphicProxy>();
            var spineOwnerDelegations = new List<ProxySpineOwnerDelegation>();
            var spineNonDrawChildren = new List<ProxySpineNonDrawChild>();
            var spineNullDataOwners = new List<ProxySpineNullDataOwner>();
            var spineEmptyPoseOwners = new List<ProxySpineEmptyPoseOwner>();
            var maskBindings = new List<ProxyMaskBinding>();
            var nestedProxyRoots = NestedProxyRoots(sourceRoot);
            var nestedProxyActiveBefore = nestedProxyRoots.Select(root =>
            {
                var marker = root.GetComponent<NativeStaticSortQueueProxyMarker>();
                return marker != null && marker.generatedRootActiveBefore;
            }).ToArray();
            var maskProxyIds = new List<string>();
            var containerStack = new Stack<Transform>(); containerStack.Push(proxyRoot);
            var maskNodeStack = new Stack<string>();
            var queueIndex = 0;
            foreach (var item in spec.drawEvents ?? Array.Empty<ProxyDrawEventSpec>())
            {
                if (item.kind == "maskEnter")
                {
                    if (!maskByNode.TryGetValue(item.node, out var maskSpec) || !sourceNodes.TryGetValue(item.node, out var sourceMaskNode))
                        throw new InvalidOperationException("STATIC_SORT_PROXY_MASK_SOURCE_MISSING: " + item.node);
                    var maskObject = new GameObject("__sort_mask_" + queueIndex++, typeof(RectTransform), typeof(CanvasRenderer),
                        typeof(NativeStaticSortQueueProxyMarker));
                    var maskRect = maskObject.GetComponent<RectTransform>();
                    var sourceMaskRect = sourceMaskNode.transform as RectTransform;
                    if (sourceMaskRect == null) throw new InvalidOperationException("STATIC_SORT_PROXY_MASK_RECTTRANSFORM_MISSING: " + item.node);
                    CopyWorldRect(sourceMaskRect, maskRect, containerStack.Peek(), item.node);
                    var marker = maskObject.GetComponent<NativeStaticSortQueueProxyMarker>();
                    marker.kind = "mask"; marker.sourceNode = item.node; marker.sourceType = "cc.Mask";
                    marker.maskType = maskSpec.maskType; marker.sourceInverted = maskSpec.inverted;
                    var nativeMask = new MaskSpec { sourceId = maskSpec.sourceId, nativeId = maskSpec.nativeId,
                        node = "proxy:" + item.node, enabled = maskSpec.enabled, maskType = maskSpec.maskType,
                        inverted = maskSpec.inverted, alphaThreshold = maskSpec.alphaThreshold,
                        spriteFrameUuid = maskSpec.spriteFrameUuid, sourceFieldsJson = maskSpec.sourceFieldsJson,
                        sourceMaterialId = maskSpec.sourceMaterialId ?? String.Empty,
                        resolvedSourceMaterialId = maskSpec.resolvedSourceMaterialId ?? String.Empty,
                        sourceEffectId = maskSpec.sourceEffectId ?? String.Empty,
                        sourceEffectName = maskSpec.sourceEffectName ?? String.Empty,
                        sourceEffectDocumentSha256 = maskSpec.sourceEffectDocumentSha256 ?? String.Empty,
                        unityMaskShaderPath = maskSpec.unityMaskShaderPath, unityMaskShaderSha256 = maskSpec.unityMaskShaderSha256,
                        unityMaskMaterialGuid = maskSpec.unityMaskMaterialGuid, unityMaskMaterialPath = maskSpec.unityMaskMaterialPath };
                    // Always use stencil Mask on the render proxy. RectMask2D
                    // uses an axis-aligned clip rect and cannot represent a
                    // rotated source mask shape exactly.
                    UnityStaticMaskSort.CreateStaticMasks(new[] { nativeMask },
                        new Dictionary<string, GameObject> { [nativeMask.node] = maskObject }, resolveSprite, resolveMaskMaterial);
                    var sourceMaskComponent = (Component)sourceMaskNode.GetComponent<Mask>() ?? sourceMaskNode.GetComponent<RectMask2D>();
                    var proxyMaskComponent = maskObject.GetComponent<Mask>();
                    if (sourceMaskComponent == null || proxyMaskComponent == null)
                        throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_OR_PROXY_MASK_REFERENCE_MISSING: " + maskSpec.sourceId);
                    maskBindings.Add(new ProxyMaskBinding { sourceId = maskSpec.sourceId, sourceNode = item.node,
                        sourceMask = sourceMaskComponent, proxyMask = proxyMaskComponent });
                    containerStack.Peek().gameObject.GetComponent<NativeStaticSortQueueProxyMarker>();
                    containerStack.Push(maskRect); maskNodeStack.Push(item.node); maskProxyIds.Add(item.node);
                }
                else if (item.kind == "maskExit")
                {
                    if (containerStack.Count <= 1 || maskNodeStack.Count == 0 || maskNodeStack.Pop() != item.node)
                        throw new InvalidOperationException("STATIC_SORT_PROXY_MASK_EVENT_STACK_MISMATCH: " + item.node);
                    containerStack.Pop();
                }
                else if (item.kind == "renderer")
                {
                    if (!sourceRendererByComponent.TryGetValue(item.sourceComponentId, out var row) ||
                        !sourceNodes.TryGetValue(row.node, out var sourceNode))
                        throw new InvalidOperationException("STATIC_SORT_PROXY_RENDERER_SOURCE_MISSING: " + item.sourceComponentId);
                    if (row.sourceType == "cc.Graphics")
                    {
                        if (!TryCreateEmptyRendererCarrier(spec, row, sourceNodes, sourceNode, containerStack.Peek(), queueIndex++, out var graphicsCarrier))
                            throw new InvalidOperationException("STATIC_SORT_PROXY_GRAPHICS_EMPTY_SOURCE_PROOF_FAILED: " + item.sourceComponentId);
                        continue;
                    }
                    if (row.sourceType == "cc.Sprite")
                    {
                        var sourceImage = sourceNode.GetComponent<Image>();
                        if (sourceImage == null || (sourceImage.sprite != null) != row.sourceTextureBound)
                            throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_SPRITE_FRAME_BOUNDNESS_DIFFERS: " +
                                item.sourceComponentId + ";planned=" + row.sourceTextureBound + ";actual=" +
                                (sourceImage != null && sourceImage.sprite != null));
                        if (!row.sourceTextureBound)
                        {
                            if ((spec.masks ?? Array.Empty<ProxyMaskSpec>()).Any(mask => mask != null && mask.node == row.node))
                                throw new InvalidOperationException("STATIC_SORT_PROXY_NULL_SPRITE_IS_SOURCE_MASK_GRAPHIC: " +
                                    item.sourceComponentId + ";node=" + row.node);
                            if (!TryCreateEmptyRendererCarrier(spec, row, sourceNodes, sourceNode, containerStack.Peek(), queueIndex++, out var nullSpriteCarrier))
                                throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_NULL_SPRITE_NONDRAW_PROOF_FAILED: " +
                                    item.sourceComponentId + ";" + SourceNullSpriteProofDiagnostic(row, sourceNode));
                            continue;
                        }
                    }
                    if (row.sourceType == "sp.Skeleton")
                    {
                        var spineOwner = sourceNode.GetComponent<Graphic>();
                        if (spineOwner != null && spineOwner.GetType().FullName == "Spine.Unity.SkeletonGraphic" &&
                            !TryReadSpineDataAsset(spineOwner, out _))
                        {
                            if (!TryBuildSpineNullDataOwnerProof(spec, row, sourceNode, sourceNodes, true,
                                out var nullDataOwner, out var nullDataDiagnostic))
                                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NULL_DATA_DRAW_EVENT_PROOF_FAILED: " +
                                    item.sourceComponentId + ";" + nullDataDiagnostic);
                            if ((!nullDataOwner.nativeRootMeshEmpty && !nullDataOwner.nativeRootMeshDefaultGraphicQuad) ||
                                !TryCreateEmptyRendererCarrier(spec, row, sourceNodes, sourceNode, containerStack.Peek(),
                                    queueIndex++, out var emptySpineCarrier))
                                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_NULL_DATA_NO_DRAW_CARRIER_FAILED: " +
                                    item.sourceComponentId + ";empty=" + nullDataOwner.nativeRootMeshEmpty +
                                    ";targetFallbackQuad=" + nullDataOwner.nativeRootMeshDefaultGraphicQuad);
                            spineNullDataOwners.Add(nullDataOwner);
                            continue;
                        }
                    }
                    var graphics = CollectEventGraphics(spec, row, sourceNodes, out var spineDelegation);
                    if (spineDelegation != null) spineOwnerDelegations.Add(spineDelegation);
                    if (row.sourceType == "sp.Skeleton")
                    {
                        if (graphics.Count == 0)
                        {
                            var emptyPoseOwnerGraphic = sourceNode.GetComponent<Graphic>();
                            if (emptyPoseOwnerGraphic == null || emptyPoseOwnerGraphic.GetType().FullName != "Spine.Unity.SkeletonGraphic")
                                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_EMPTY_POSE_OWNER_GRAPHIC_MISSING: " +
                                    item.sourceComponentId);
                            FinalizeSourceSpineStaticMesh(new[] { emptyPoseOwnerGraphic }, "capture-empty-fixed-pose-probe");
                            graphics = CollectEventGraphics(spec, row, sourceNodes, out spineDelegation);
                            if (spineDelegation != null) spineOwnerDelegations.Add(spineDelegation);
                            if (graphics.Count == 0)
                            {
                                if (!TryBuildSpineEmptyPoseOwnerProof(spec, row, sourceNode, sourceNodes, true,
                                    out var emptyPoseProof, out var emptyPoseDiagnostic))
                                    throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_EMPTY_FIXED_POSE_PROOF_FAILED: " +
                                        item.sourceComponentId + ";" + emptyPoseDiagnostic + ";" +
                                        SpineMeshDiagnostic(item.sourceComponentId, emptyPoseOwnerGraphic,
                                            emptyPoseOwnerGraphic.canvasRenderer == null ? null : emptyPoseOwnerGraphic.canvasRenderer.GetMesh()));
                                if (!TryCreateEmptyRendererCarrier(spec, row, sourceNodes, sourceNode, containerStack.Peek(),
                                    queueIndex++, out var emptyPoseCarrier, emptyPoseProof))
                                    throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_EMPTY_FIXED_POSE_CARRIER_FAILED: " +
                                        item.sourceComponentId);
                                spineEmptyPoseOwners.Add(emptyPoseProof);
                                continue;
                            }
                        }
                        var ownerGraphic = sourceNode.GetComponent<Graphic>();
                        foreach (var sourceGraphic in graphics)
                        {
                            if (sourceGraphic == null || sourceGraphic.canvasRenderer == null ||
                                sourceGraphic != ownerGraphic && !IsSpineCanvasSubmesh(sourceGraphic.gameObject, ownerGraphic))
                                throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_PENDING_GRAPHIC_IDENTITY_INVALID: source=" +
                                    item.sourceComponentId + ";graphic=" + (sourceGraphic == null ? "null" : TransformPath(sourceGraphic.transform)));
                            // Reserve the queue index now, but wait to build the
                            // proxy until every generic Canvas/TMP/Image refresh
                            // is complete and the SDK has emitted its final mesh.
                            pendingSpineGraphics.Add(new PendingSpineGraphicProxy { row = row, sourceNode = sourceNode,
                                sourceGraphic = sourceGraphic, sourceOwnerGraphic = ownerGraphic,
                                parent = containerStack.Peek(), queueIndex = queueIndex++ });
                        }
                        continue;
                    }
                    if (row.sourceType == "cc.Label" || row.sourceType == "cc.RichText")
                    {
                        var textOwner = sourceNode.GetComponent<TMPro.TMP_Text>();
                        if (textOwner == null)
                            throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_OWNER_MISSING: " + item.sourceComponentId);
                        var textInfo = textOwner.textInfo;
                        var hasTextGeometry = textInfo != null && textInfo.meshInfo != null &&
                            Enumerable.Range(0, Mathf.Min(textInfo.materialCount, textInfo.meshInfo.Length))
                                .Any(index => textInfo.meshInfo[index].mesh != null && textInfo.meshInfo[index].mesh.vertexCount > 0);
                        if (!hasTextGeometry)
                        {
                            if (!TryCreateEmptyRendererCarrier(spec, row, sourceNodes, sourceNode, containerStack.Peek(), queueIndex++, out var emptyTextCarrier))
                                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_EMPTY_SOURCE_PROOF_FAILED: " + item.sourceComponentId);
                            if (!AttachEmptyTextSlotProof(row, textOwner, emptyTextCarrier.gameObject, out var emptyTextSlotDiagnostic))
                                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_EMPTY_SLOT_ENUMERATION_ATTACH_FAILED: " +
                                    item.sourceComponentId + ";diagnostic=" + emptyTextSlotDiagnostic);
                            continue;
                        }
                        ownerTextStyles.TryGetValue(row.sourceComponentId, out var ownerStyle);
                        var textSlots = CaptureAndRebindTextSlots(spec, row, textOwner, ownerStyle, out var textSlotEnumeration);
                        if (textSlots.Count == 0)
                        {
                            if (!TryCreateEmptyRendererCarrier(spec, row, sourceNodes, sourceNode, containerStack.Peek(),
                                    queueIndex++, out var noSlotTextCarrier))
                                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_EMPTY_SLOT_ENUMERATION_ATTACH_FAILED: " +
                                    item.sourceComponentId + ";diagnostic=empty-carrier-create-failed");
                            if (!AttachEmptyTextSlotProof(row, textOwner, noSlotTextCarrier.gameObject, out var noSlotDiagnostic))
                                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_EMPTY_SLOT_ENUMERATION_ATTACH_FAILED: " +
                                    item.sourceComponentId + ";diagnostic=" + noSlotDiagnostic);
                            if (!SameTextSlotEnumeration(textSlotEnumeration, noSlotTextCarrier.GetComponent<NativeStaticSortTextSlotEnumerationIdentity>()
                                    .slotEnumeration))
                                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_EMPTY_SLOT_ENUMERATION_CHANGED_DURING_ATTACH: " +
                                    item.sourceComponentId);
                            continue;
                        }
                        var expectedGraphics = textSlots.Select(binding => binding.sourceGraphic).ToHashSet();
                        var placeholder = textSlotEnumeration.rows.SingleOrDefault(slot => slot.disposition == "empty-placeholder");
                        if (placeholder != null)
                        {
                            if (placeholder.slot != 0 || !expectedGraphics.Add(textOwner as Graphic))
                                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_PLACEHOLDER_OWNER_GRAPHIC_INVALID: " +
                                    item.sourceComponentId + ";slot=" + placeholder.slot);
                        }
                        var collectedGraphics = graphics.ToHashSet();
                        if (expectedGraphics.Contains(null) || expectedGraphics.Count != graphics.Count ||
                            !expectedGraphics.SetEquals(collectedGraphics))
                            throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_GRAPHIC_DENOMINATOR_DIFFERS: " +
                                item.sourceComponentId + ";drawableSlots=" + textSlots.Count + ";placeholder=" +
                                (placeholder == null ? "none" : placeholder.slot.ToString()) + ";graphics=" +
                                String.Join(",", graphics.Select(graphic => graphic == null ? "null" : graphic.GetType().Name + ":" + graphic.name)));
                        foreach (var textBinding in textSlots)
                        {
                            var sourceGraphic = textBinding.sourceGraphic;
                            var canvasRenderer = sourceGraphic == null ? null : sourceGraphic.canvasRenderer;
                            var sourceMesh = textBinding.sourceMesh;
                            var materialCount = canvasRenderer == null ? -1 : Math.Max(1, canvasRenderer.materialCount);
                            if (sourceGraphic == null || canvasRenderer == null || sourceMesh == null || sourceMesh.vertexCount == 0)
                                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_FINAL_MESH_EMPTY: " +
                                    item.sourceComponentId + ";slot=" + textBinding.materialSlot);
                            if (materialCount != sourceMesh.subMeshCount || materialCount != 1)
                                throw new InvalidOperationException("STATIC_SORT_PROXY_TEXT_SLOT_SUBMESH_DENOMINATOR_UNPROVEN: " +
                                    item.sourceComponentId + ";slot=" + textBinding.materialSlot +
                                    ";materials=" + materialCount + ";submeshes=" + sourceMesh.subMeshCount);
                            CreateProxyGraphic(sourceGraphic, sourceNode.GetComponent<Graphic>(), row.node, item.sourceComponentId,
                                row.sourceType, queueIndex++, 0, row.expectedGraphicType, sourceGraphic.gameObject != sourceNode,
                                containerStack.Peek(), spec.meshAssetFolder, textBinding, out var textProxyBinding);
                            bindings.Add(textProxyBinding);
                        }
                        continue;
                    }
                    foreach (var sourceGraphic in graphics)
                    {
                        var canvasRenderer = sourceGraphic.canvasRenderer;
                        EnsureSourceGraphicMeshReady(sourceGraphic);
                        var sourceMesh = canvasRenderer.GetMesh();
                        var materialCount = Math.Max(1, canvasRenderer.materialCount);
                        if (sourceMesh == null || sourceMesh.vertexCount == 0)
                        {
                            if (!TryCreateEmptyRendererCarrier(spec, row, sourceNodes, sourceNode, containerStack.Peek(), queueIndex++, out var emptyCarrier))
                                throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_MESH_MATERIAL_COUNT_MISMATCH: " +
                                    SourceGraphicMeshDiagnostic(item.sourceComponentId, sourceGraphic, sourceMesh));
                            continue;
                        }
                        if (materialCount != sourceMesh.subMeshCount)
                            throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_MESH_MATERIAL_COUNT_MISMATCH: " +
                                SpineMeshDiagnostic(item.sourceComponentId, sourceGraphic, sourceMesh));
                        if (materialCount != 1)
                            throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_BASE_MATERIAL_PER_SUBMESH_UNPROVEN: " + item.sourceComponentId);
                        for (var submesh = 0; submesh < materialCount; submesh++)
                        {
                            CreateProxyGraphic(sourceGraphic, sourceNode.GetComponent<Graphic>(), row.node, item.sourceComponentId, row.sourceType,
                                queueIndex++, submesh, row.expectedGraphicType, sourceGraphic.gameObject != sourceNode,
                                containerStack.Peek(), spec.meshAssetFolder, null, out var binding);
                            bindings.Add(binding);
                        }
                    }
                }
                else throw new InvalidOperationException("STATIC_SORT_PROXY_DRAW_EVENT_UNKNOWN: " + item.kind);
            }
            foreach (var row in spec.nonDrawRenderers ?? Array.Empty<ProxyRendererSpec>())
            {
                if (row == null || !sourceNodes.TryGetValue(row.node, out var disabledNode) ||
                    row.sourceEnabled && row.sourceActive)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_NON_DRAW_SPEC_INVALID: " + (row == null ? "null" : row.sourceComponentId));
                if (!TryCreateEmptyRendererCarrier(spec, row, sourceNodes, disabledNode, proxyRoot, -1, out var carrier))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_NON_DRAW_SOURCE_PROOF_FAILED: " + row.sourceComponentId);
                if (row.sourceType == "sp.Skeleton")
                {
                    spineNonDrawChildren.AddRange(CaptureSpineNonDrawChildren(spec, row, disabledNode, sourceNodes,
                        out var nullDataOwner));
                    if (nullDataOwner != null) spineNullDataOwners.Add(nullDataOwner);
                }
            }
            if (pendingSpineGraphics.Count > 0)
            {
                // This is intentionally the last generic rebuild in capture.
                // The pinned Spine SDK now owns the final child mesh/material
                // write, and no Canvas force/rebuild follows before capture.
                FinalizeSourceSpineStaticMesh(pendingSpineGraphics.Select(item => item.sourceOwnerGraphic), "capture");
                foreach (var sourceComponentId in pendingSpineGraphics.Select(item => item.row.sourceComponentId)
                    .Distinct(StringComparer.Ordinal))
                {
                    var pending = pendingSpineGraphics.Where(item => item.row.sourceComponentId == sourceComponentId).ToArray();
                    var proofIndex = spineOwnerDelegations.FindIndex(proof => proof != null && proof.sourceComponentId == sourceComponentId);
                    var finalGraphics = CollectEventGraphics(spec, pending[0].row, sourceNodes,
                        out var finalProof, captureFinalSpineProof: true);
                    var expectedGraphics = pending.Select(item => item.sourceGraphic).ToArray();
                    var expectedOwner = pending[0].sourceOwnerGraphic;
                    var delegatedChildren = expectedGraphics.Any(graphic => graphic != expectedOwner);
                    if (!expectedGraphics.SequenceEqual(finalGraphics) || delegatedChildren != (finalProof != null) ||
                        finalProof != null && (finalProof.sourceOwnerGraphic != expectedOwner ||
                            !finalProof.delegatedCanvasRenderers.SequenceEqual(expectedGraphics.Select(graphic => graphic.canvasRenderer))))
                        throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_FINAL_CHILD_IDENTITY_CHANGED: " +
                            sourceComponentId + ";expected=" + String.Join(",", expectedGraphics.Select(item =>
                                item == expectedOwner ? "<owner>" : SpineChildPath(expectedOwner.transform, item.transform))) +
                            ";actual=" + String.Join(",", finalGraphics.Select(item => item == null ? "null" :
                                item == expectedOwner ? "<owner>" : SpineChildPath(expectedOwner.transform, item.transform))) +
                            ";delegation=" + (finalProof != null));
                    if (finalProof != null)
                    {
                        if (proofIndex >= 0) spineOwnerDelegations[proofIndex] = finalProof;
                        else spineOwnerDelegations.Add(finalProof);
                    }
                }
                foreach (var pending in pendingSpineGraphics.OrderBy(item => item.queueIndex))
                {
                    var sourceGraphic = pending.sourceGraphic;
                    var canvasRenderer = sourceGraphic == null ? null : sourceGraphic.canvasRenderer;
                    var sourceMesh = canvasRenderer == null ? null : canvasRenderer.GetMesh();
                    var materialCount = canvasRenderer == null ? -1 : Math.Max(1, canvasRenderer.materialCount);
                    if (sourceMesh == null || sourceMesh.vertexCount == 0 || materialCount != sourceMesh.subMeshCount || materialCount != 1)
                        throw new InvalidOperationException("STATIC_SORT_PROXY_SPINE_FINAL_MESH_MATERIAL_DENOMINATOR_INVALID: " +
                            SpineMeshDiagnostic(pending.row.sourceComponentId, sourceGraphic, sourceMesh) +
                            ";queueIndex=" + pending.queueIndex);
                    CreateProxyGraphic(sourceGraphic, pending.sourceOwnerGraphic, pending.row.node,
                        pending.row.sourceComponentId, pending.row.sourceType, pending.queueIndex, 0,
                        pending.row.expectedGraphicType, sourceGraphic.gameObject != pending.sourceNode,
                        pending.parent, spec.meshAssetFolder, null, out var spineProxyBinding);
                    bindings.Add(spineProxyBinding);
                }
                SortGeneratedProxyChildrenBySourceEvent(spec, proxyRootObject.transform);
            }
            if (containerStack.Count != 1 || maskNodeStack.Count != 0)
                throw new InvalidOperationException("STATIC_SORT_PROXY_UNCLOSED_MASK_SCOPE");
            var presenter = proxyRootObject.AddComponent<NativeStaticSortQueueProxyPresenter>();
            presenter.sourceRootId = spec.rootScope; presenter.sourcePrefabId = spec.sourcePrefabId;
            presenter.prefabPath = spec.prefabPath; presenter.sourceRoot = sourceRoot; presenter.proxyRoot = proxyRootObject;
            presenter.queueSha256 = HashText(string.Join("|", (spec.drawEvents ?? Array.Empty<ProxyDrawEventSpec>())
                .Select(row => row.kind + ":" + row.node + ":" + row.sourceComponentId)));
            presenter.bindings = bindings.ToArray();
            presenter.maskBindings = maskBindings.ToArray();
            presenter.spineOwnerDelegations = spineOwnerDelegations.ToArray();
            presenter.spineNonDrawChildren = spineNonDrawChildren.ToArray();
            presenter.spineNullDataOwners = spineNullDataOwners.ToArray();
            presenter.spineEmptyPoseOwners = spineEmptyPoseOwners.ToArray();
            presenter.nestedProxyRoots = nestedProxyRoots.ToArray();
            presenter.nestedProxyRootActiveBefore = nestedProxyActiveBefore;
            presenter.nestedProxyPresenters = nestedProxyRoots.Select(root =>
                root.GetComponent<NativeStaticSortQueueProxyPresenter>()).ToArray();
            var blockInputRows = ReadBlockInputEvents(spec, sourceNodes, true,
                out var blockInputsVerified, out var blockInputDiagnostics);
            if (!blockInputsVerified)
                throw new InvalidOperationException("STATIC_SORT_PROXY_BLOCK_INPUT_READBACK_INVALID: " +
                    String.Join("|", blockInputDiagnostics ?? Array.Empty<string>()));
            var sourceMaskIdentityRows = ReadSourceMaskIdentities(spec, sourceNodes, resolveSprite, true,
                out var sourceMaskIdentitiesVerified, out var sourceMaskIdentityDiagnostics);
            if (!sourceMaskIdentitiesVerified)
                throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_MASK_IDENTITY_READBACK_INVALID: " +
                    String.Join("|", sourceMaskIdentityDiagnostics ?? Array.Empty<string>()));
            if (!ValidateSourceGraphicCoverage(spec, sourceNodes, proxyRootObject.transform, bindings,
                    spineOwnerDelegations, spineNonDrawChildren, spineNullDataOwners, spineEmptyPoseOwners,
                    true, "capture-in-memory", null, blockInputRows,
                    sourceMaskIdentityRows,
                    out var uncoveredSourceNode))
                throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_GRAPHIC_UNCOVERED: " + uncoveredSourceNode);
            presenter.InitializePresentation();
            nestedCapture.Commit();
            var sourceFields = spec.sourceFields ?? Array.Empty<QueueSortFieldSpec>();
            foreach (var field in sourceFields)
            {
                if (!sourceNodes.TryGetValue(field.node, out var fieldNode))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_FIELD_NODE_MISSING: " + field.sourceId);
                var identity = fieldNode.GetComponent<NativeStaticSortOrderIdentity>();
                if (identity == null || identity.sourceId != field.sourceId || identity.nativeId != field.nativeId ||
                    identity.sourceSortOrder != field.sortOrder || identity.enabledInSource != field.enabled)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_SORTORDER_IDENTITY_MISSING_OR_DIFFERS: " + field.sourceId);
            }
            foreach (var field in spec.sourceSortRoots ?? Array.Empty<ProxySortRootFieldSpec>())
            {
                if (!sourceNodes.TryGetValue(field.node, out var fieldNode))
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_SORTROOT_NODE_MISSING: " + field.sourceId);
                var identity = fieldNode.GetComponent<NativeStaticSortRootIdentity>();
                if (identity == null || identity.sourceId != field.sourceId || identity.nativeId != field.nativeId ||
                    identity.enabledInSource != field.enabled)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_SOURCE_SORTROOT_IDENTITY_MISSING_OR_DIFFERS: " + field.sourceId);
            }
            AssetDatabase.SaveAssets();
            return ReadProxy(spec, sourceNodes, proxyRootObject, presenter, resolveSprite, resolveMaskMaterial,
                verifyRuntimeGeometry: true, requireSavedPrefabAsset: false, provisional: true, scopeProvenance: null);
        }

        public static ProxyQueueReadback ReadStaticSortQueueProxy(ProxyQueueSpec spec,
            IDictionary<string, GameObject> sourceNodes, GameObject proxyRoot, NativeStaticSortQueueProxyPresenter presenter,
            Func<string, Sprite> resolveSprite = null, Func<MaskSpec, Material> resolveMaskMaterial = null,
            ProxyPrefabScopeProvenance scopeProvenance = null)
        {
            return ReadProxy(spec, sourceNodes, proxyRoot, presenter, resolveSprite, resolveMaskMaterial,
                verifyRuntimeGeometry: true, requireSavedPrefabAsset: true, provisional: false,
                scopeProvenance: scopeProvenance);
        }

        public static ProxyQueueReadback ReadPersistentSortQueueProxy(ProxyQueueSpec spec,
            IDictionary<string, GameObject> sourceNodes, GameObject proxyRoot, NativeStaticSortQueueProxyPresenter presenter,
            Func<string, Sprite> resolveSprite = null, Func<MaskSpec, Material> resolveMaskMaterial = null,
            ProxyPrefabScopeProvenance scopeProvenance = null)
        {
            return ReadProxy(spec, sourceNodes, proxyRoot, presenter, resolveSprite, resolveMaskMaterial,
                verifyRuntimeGeometry: false, requireSavedPrefabAsset: true, provisional: false,
                scopeProvenance: scopeProvenance);
        }

        static ProxySpineOwnerDelegationReadback[] ReadSpineOwnerDelegations(ProxyQueueSpec spec,
            IDictionary<string, GameObject> sourceNodes, NativeStaticSortQueueProxyPresenter presenter,
            bool requireRuntimeMeshes, out bool allVerified, out string[] diagnostics)
        {
            var rows = new List<ProxySpineOwnerDelegationReadback>();
            var gaps = new List<string>();
            var specs = (spec.renderers ?? Array.Empty<ProxyRendererSpec>())
                .Where(row => row != null && row.sourceType == "sp.Skeleton")
                .ToDictionary(row => row.sourceComponentId, StringComparer.Ordinal);
            var proofs = presenter == null ? Array.Empty<ProxySpineOwnerDelegation>() :
                presenter.spineOwnerDelegations ?? Array.Empty<ProxySpineOwnerDelegation>();
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var proof in proofs)
            {
                if (proof == null || String.IsNullOrWhiteSpace(proof.sourceComponentId) || !seen.Add(proof.sourceComponentId))
                {
                    gaps.Add("STATIC_SORT_PROXY_SPINE_DELEGATION_PROOF_MISSING_OR_DUPLICATE");
                    continue;
                }
                specs.TryGetValue(proof.sourceComponentId, out var rendererSpec);
                sourceNodes.TryGetValue(proof.sourceNode, out var node);
                var owner = node == null ? null : node.GetComponent<Graphic>();
                var rootMesh = owner == null || owner.canvasRenderer == null ? null : owner.canvasRenderer.GetMesh();
                var rootVertices = rootMesh == null ? 0 : rootMesh.vertexCount;
                var rootSubmeshes = rootMesh == null ? -1 : rootMesh.subMeshCount;
                var rootMaterials = owner == null || owner.canvasRenderer == null ? -1 : owner.canvasRenderer.materialCount;
                var sourceIdentityVerified = rendererSpec != null && rendererSpec.node == proof.sourceNode &&
                    proof.sourceOwnerGraphic == owner && owner != null &&
                    TryReadSpineIdentity(owner, proof.sourceComponentId, out var actualSourceId);
                UnityEngine.Object actualData = null;
                var hasActualData = owner != null && TryReadSpineDataAsset(owner, out actualData);
                SpineDataIdentityEvidence dataEvidence = null; string dataDiagnostic = null;
                var sourceDataReferenceVerified = hasActualData && actualData != null &&
                    actualData == proof.sourceDataAssetReference &&
                    TryReadSpineDataIdentity(spec, proof.sourceComponentId, actualData, out dataEvidence, out dataDiagnostic) &&
                    dataEvidence.sourceDataAssetId == proof.sourceDataAssetId &&
                    dataEvidence.dataAssetPath == proof.sourceDataAssetPath &&
                    dataEvidence.dataAssetGuid == proof.sourceDataAssetGuid &&
                    dataEvidence.bindingPlanPath == proof.sourceBindingPlanPath &&
                    dataEvidence.bindingPlanSha256 == proof.sourceBindingPlanSha256 &&
                    dataEvidence.sourceManifestSha256 == proof.sourceManifestSha256;
                var registered = new List<CanvasRenderer>();
                var listReadable = owner != null && TryReadSpineRendererList(owner, out registered);
                var sourceGraphics = proof.delegatedSourceGraphics ?? Array.Empty<Graphic>();
                var renderers = proof.delegatedCanvasRenderers ?? Array.Empty<CanvasRenderer>();
                var paths = proof.delegatedChildPaths ?? Array.Empty<string>();
                var materialGuids = proof.delegatedChildMaterialGuids ?? Array.Empty<string>();
                var textureGuids = proof.delegatedChildTextureGuids ?? Array.Empty<string>();
                var vertexCounts = proof.childMeshVertexCounts ?? Array.Empty<int>();
                var submeshCounts = proof.childMeshSubmeshCounts ?? Array.Empty<int>();
                var materialCounts = proof.childCanvasMaterialCounts ?? Array.Empty<int>();
                var count = sourceGraphics.Length;
                var childPaths = new List<string>(); var childTypes = new List<string>();
                var childMaterialGuids = new List<string>(); var childTextureGuids = new List<string>();
                var childRendererListVerified = listReadable && count > 0 &&
                    count == renderers.Length && count == paths.Length && count == materialGuids.Length &&
                    count == textureGuids.Length && count == vertexCounts.Length && count == submeshCounts.Length &&
                    count == materialCounts.Length && registered.Count == count &&
                    registered.SequenceEqual(renderers) && sourceGraphics.Distinct().Count() == count &&
                    renderers.Distinct().Count() == count;
                var childReferencesPersistent = childRendererListVerified;
                for (var index = 0; index < count; index++)
                {
                    var child = sourceGraphics[index];
                    var renderer = child == null ? null : child.canvasRenderer;
                    var mesh = requireRuntimeMeshes && renderer != null ? renderer.GetMesh() : null;
                    var sourceMaterial = child == null ? null : child.material;
                    var sourceTexture = sourceMaterial == null || sourceMaterial.mainTexture == null ?
                        child == null ? null : child.mainTexture : sourceMaterial.mainTexture;
                    long materialLocal; var actualMaterialGuid = sourceMaterial == null ? null : AssetGuid(sourceMaterial, out materialLocal);
                    var actualTextureGuid = TextureAssetGuid(sourceTexture);
                    var childOK = child != null && renderer != null && renderer == renderers.ElementAtOrDefault(index) &&
                        IsSpineCanvasSubmesh(child.gameObject, owner) && paths.ElementAtOrDefault(index) == SpineChildPath(owner.transform, child.transform) &&
                        !String.IsNullOrWhiteSpace(actualMaterialGuid) && actualMaterialGuid == materialGuids.ElementAtOrDefault(index) &&
                        !String.IsNullOrWhiteSpace(AssetDatabase.GetAssetPath(sourceMaterial)) &&
                        !String.IsNullOrWhiteSpace(actualTextureGuid) && actualTextureGuid == textureGuids.ElementAtOrDefault(index);
                    if (requireRuntimeMeshes)
                        childOK = childOK && mesh != null && mesh.vertexCount == vertexCounts.ElementAtOrDefault(index) &&
                            mesh.subMeshCount == submeshCounts.ElementAtOrDefault(index) &&
                            renderer.materialCount == materialCounts.ElementAtOrDefault(index) && mesh.vertexCount > 0 &&
                            mesh.subMeshCount > 0 && renderer.materialCount == mesh.subMeshCount;
                    childRendererListVerified &= childOK;
                    childReferencesPersistent &= childOK;
                    childPaths.Add(child == null ? null : SpineChildPath(owner.transform, child.transform));
                    childTypes.Add(child == null ? null : child.GetType().FullName);
                    childMaterialGuids.Add(actualMaterialGuid); childTextureGuids.Add(actualTextureGuid);
                }
                var childProxyBindings = (presenter == null ? Array.Empty<ProxyGraphicBinding>() : presenter.bindings ?? Array.Empty<ProxyGraphicBinding>())
                    .Where(binding => binding != null && binding.sourceGraphic != null && sourceGraphics.Contains(binding.sourceGraphic)).ToArray();
                var boundChildren = childProxyBindings.Select(binding => binding.sourceGraphic).ToArray();
                var childProxyRefsVerified = boundChildren.Length == count && boundChildren.Distinct().Count() == count &&
                    sourceGraphics.All(child => childProxyBindings.Count(binding => binding.sourceGraphic == child &&
                        (binding.proxyGraphics ?? Array.Empty<NativeStaticSortQueueProxyGraphic>()).Length == 1 &&
                        binding.proxyGraphics[0] != null && binding.proxyGraphics[0].sourceComponentId == proof.sourceComponentId &&
                        binding.proxyGraphics[0].sourceNodeId == proof.sourceNode && binding.proxyGraphics[0].generatedSourceChild &&
                        binding.proxyGraphics[0].sourceOwnerGraphic == owner) == 1);
                var rootMeshDelegated = proof.rootMeshVertexCount == 0 && rootVertices == 0 &&
                    proof.rootMeshWasMissing == (proof.rootMeshSubmeshCount == -1) && proof.rootCanvasMaterialCount >= 0 &&
                    (!requireRuntimeMeshes && rootMesh == null || rootSubmeshes == proof.rootMeshSubmeshCount) &&
                    (!requireRuntimeMeshes || rootMaterials == proof.rootCanvasMaterialCount);
                var verified = sourceIdentityVerified && sourceDataReferenceVerified && rootMeshDelegated &&
                    childRendererListVerified && childReferencesPersistent && childProxyRefsVerified;
                if (!verified)
                    gaps.Add("STATIC_SORT_PROXY_SPINE_OWNER_DELEGATION_READBACK_INVALID: source=" + proof.sourceComponentId +
                        ";rootVertices=" + rootVertices + ";rootSubmeshes=" + rootSubmeshes + ";rootMaterials=" + rootMaterials +
                        ";proofRootVertices=" + proof.rootMeshVertexCount + ";proofRootSubmeshes=" + proof.rootMeshSubmeshCount +
                        ";proofRootMaterials=" + proof.rootCanvasMaterialCount + ";dataGuid=" + proof.sourceDataAssetGuid +
                        ";registeredChildren=" + registered.Count + ";proofChildren=" + count +
                        ";boundChildren=" + boundChildren.Length);
                TryReadSpineIdentity(owner, proof.sourceComponentId, out var actualIdentityId);
                rows.Add(new ProxySpineOwnerDelegationReadback { sourceComponentId = proof.sourceComponentId,
                    sourceNode = proof.sourceNode, sourceGraphicType = owner == null ? null : owner.GetType().FullName,
                    sourceIdentityComponentId = actualIdentityId, sourceDataAssetPath = proof.sourceDataAssetPath,
                    sourceDataAssetId = proof.sourceDataAssetId, sourceBindingPlanPath = proof.sourceBindingPlanPath,
                    sourceBindingPlanSha256 = proof.sourceBindingPlanSha256, sourceManifestSha256 = proof.sourceManifestSha256,
                    sourceDataAssetGuid = proof.sourceDataAssetGuid, rootMeshVertexCount = rootVertices,
                    rootMeshSubmeshCount = rootSubmeshes, rootCanvasMaterialCount = rootMaterials,
                    delegatedChildPaths = childPaths.ToArray(), delegatedChildGraphicTypes = childTypes.ToArray(),
                    delegatedChildTextureGuids = childTextureGuids.ToArray(), delegatedChildMaterialGuids = childMaterialGuids.ToArray(),
                    childMeshVertexCounts = vertexCounts, childMeshSubmeshCounts = submeshCounts,
                    childCanvasMaterialCounts = materialCounts, rootMeshWasMissing = proof.rootMeshWasMissing,
                    sourceIdentityVerified = sourceIdentityVerified, sourceDataReferenceVerified = sourceDataReferenceVerified,
                    rootMeshDelegated = rootMeshDelegated, childRendererListVerified = childRendererListVerified,
                    childReferencesPersistent = childReferencesPersistent, verified = verified });
            }
            allVerified = gaps.Count == 0;
            diagnostics = gaps.ToArray();
            return rows.ToArray();
        }

        static ProxySpineNullDataOwnerReadback[] ReadSpineNullDataOwners(ProxyQueueSpec spec,
            IDictionary<string, GameObject> sourceNodes, NativeStaticSortQueueProxyPresenter presenter,
            bool requireHierarchyActivity, out bool allVerified, out string[] diagnostics)
        {
            var rows = new List<ProxySpineNullDataOwnerReadback>();
            var gaps = new List<string>();
            var expected = new Dictionary<string, ProxyRendererSpec>(StringComparer.Ordinal);
            foreach (var source in (spec.renderers ?? Array.Empty<ProxyRendererSpec>())
                .Concat(spec.nonDrawRenderers ?? Array.Empty<ProxyRendererSpec>()))
            {
                if (source == null || source.sourceType != "sp.Skeleton") continue;
                if (!sourceNodes.TryGetValue(source.node, out var node) || node == null)
                { gaps.Add("STATIC_SORT_PROXY_SPINE_NULL_DATA_SOURCE_NODE_MISSING:" + source.sourceComponentId); continue; }
                var owner = node.GetComponent<Graphic>();
                if (owner == null || owner.GetType().FullName != "Spine.Unity.SkeletonGraphic") continue;
                if (TryReadSpineDataAsset(owner, out _)) continue;
                if (expected.ContainsKey(source.sourceComponentId))
                    gaps.Add("STATIC_SORT_PROXY_SPINE_NULL_DATA_SOURCE_ID_DUPLICATE:" + source.sourceComponentId);
                else expected.Add(source.sourceComponentId, source);
            }
            var proofs = presenter == null ? Array.Empty<ProxySpineNullDataOwner>() :
                presenter.spineNullDataOwners ?? Array.Empty<ProxySpineNullDataOwner>();
            var proofIds = proofs.Where(proof => proof != null).Select(proof => proof.sourceComponentId).ToArray();
            if (proofIds.Any(String.IsNullOrWhiteSpace) || proofIds.Distinct(StringComparer.Ordinal).Count() != proofIds.Length ||
                !new HashSet<string>(proofIds, StringComparer.Ordinal).SetEquals(expected.Keys))
                gaps.Add("STATIC_SORT_PROXY_SPINE_NULL_DATA_OWNER_DENOMINATOR_DIFFERS:expected=" + expected.Count +
                    ";actual=" + proofIds.Length);
            foreach (var pair in expected)
            {
                var source = pair.Value;
                sourceNodes.TryGetValue(source.node, out var node);
                var currentOK = TryBuildSpineNullDataOwnerProof(spec, source, node, sourceNodes, requireHierarchyActivity,
                    out var actualProof, out var actualDiagnostic);
                var saved = proofs.SingleOrDefault(proof => proof != null && proof.sourceComponentId == pair.Key);
                var savedTargetFallbackQuadNotCurrentlyPresent = saved != null && actualProof != null &&
                    saved.nativeRootMeshDefaultGraphicQuad && actualProof.nativeRootMeshEmpty &&
                    saved.rootMeshVertexCount == 4 && saved.rootMeshSubmeshCount == 1 && saved.rootMeshIndexCount == 6 &&
                    saved.rootCanvasMaterialCount == 1 && saved.rootSourceBaseDefaultMaterial &&
                    saved.rootCanvasDefaultMaterialOnly && saved.rootMaterialSlotMatchesGraphicRendering &&
                    saved.rootExtraMaterialModifierCount == 0 && (saved.rootMeshSha256 ?? String.Empty).Length == 64 &&
                    (saved.rootMeshGeometryEvidence ?? String.Empty).Contains("triangleOrderExact=True") &&
                    (saved.rootMeshGeometryEvidence ?? String.Empty).Contains("rectCornersExact=True") &&
                    actualProof.nativeRootMeshEmpty && actualProof.rootCanvasMaterialCount == 0 &&
                    actualProof.rootCanvasDefaultMaterialOnly && actualProof.rootSourceBaseDefaultMaterial;
                var currentRootMeshMatchesCapture = saved != null && actualProof != null &&
                    (savedTargetFallbackQuadNotCurrentlyPresent ||
                     (saved.nativeRootMeshEmpty == actualProof.nativeRootMeshEmpty &&
                      saved.nativeRootMeshDefaultGraphicQuad == actualProof.nativeRootMeshDefaultGraphicQuad &&
                      (actualProof.nativeRootMeshEmpty
                          ? String.IsNullOrEmpty(saved.rootMeshSha256) && String.IsNullOrEmpty(actualProof.rootMeshSha256)
                          : saved.rootMeshSha256 == actualProof.rootMeshSha256) &&
                      saved.rootMeshGeometryEvidence == actualProof.rootMeshGeometryEvidence &&
                      saved.rootMaterialEvidence == actualProof.rootMaterialEvidence &&
                      saved.rootCanvasDefaultMaterialOnly == actualProof.rootCanvasDefaultMaterialOnly &&
                      saved.rootSourceBaseDefaultMaterial == actualProof.rootSourceBaseDefaultMaterial &&
                      saved.rootMaterialSlotMatchesGraphicRendering == actualProof.rootMaterialSlotMatchesGraphicRendering &&
                      saved.rootMeshVertexCount == actualProof.rootMeshVertexCount &&
                      saved.rootMeshSubmeshCount == actualProof.rootMeshSubmeshCount &&
                      saved.rootMeshIndexCount == actualProof.rootMeshIndexCount &&
                      saved.rootCanvasMaterialCount == actualProof.rootCanvasMaterialCount &&
                      saved.rootExtraMaterialModifierCount == actualProof.rootExtraMaterialModifierCount));
                var savedProofDifferences = new List<string>();
                if (saved == null) savedProofDifferences.Add("saved-proof-missing");
                else if (actualProof == null) savedProofDifferences.Add("current-proof-missing");
                else
                {
                    void Check(string name, bool matches) { if (!matches) savedProofDifferences.Add(name); }
                    Check("sourceOwnerGraphicReference", saved.sourceOwnerGraphic == actualProof.sourceOwnerGraphic);
                    Check("sourceNode", saved.sourceNode == actualProof.sourceNode);
                    Check("sourceStaticDataState", saved.sourceStaticDataState == actualProof.sourceStaticDataState);
                    Check("sourceBindingPlanPath", saved.sourceBindingPlanPath == actualProof.sourceBindingPlanPath);
                    Check("sourceBindingPlanSha256", saved.sourceBindingPlanSha256 == actualProof.sourceBindingPlanSha256);
                    Check("sourceManifestSha256", saved.sourceManifestSha256 == actualProof.sourceManifestSha256);
                    Check("sourceMaterialClosureStatus", saved.sourceMaterialClosureStatus == actualProof.sourceMaterialClosureStatus);
                    Check("sourceTargetFieldsJson", saved.sourceTargetFieldsJson == actualProof.sourceTargetFieldsJson);
                    Check("expectedFieldsJson", saved.expectedFieldsJson == actualProof.expectedFieldsJson);
                    Check("actualFieldsJson", saved.actualFieldsJson == actualProof.actualFieldsJson);
                    Check("sourceHasStaticDataReference", saved.sourceHasStaticDataReference == actualProof.sourceHasStaticDataReference);
                    Check("sourceDataAssetIdNull", saved.sourceDataAssetIdNull == actualProof.sourceDataAssetIdNull);
                    Check("sourcePlanVerified", saved.sourcePlanVerified && actualProof.sourcePlanVerified);
                    Check("sourceIdentityVerified", saved.sourceIdentityVerified && actualProof.sourceIdentityVerified);
                    Check("sourceOwnerEnabled", saved.sourceOwnerEnabled == actualProof.sourceOwnerEnabled);
                    Check("rootMeshEmptyFlag", saved.nativeRootMeshEmpty == actualProof.nativeRootMeshEmpty || savedTargetFallbackQuadNotCurrentlyPresent);
                    Check("rootMeshFallbackQuadFlag", saved.nativeRootMeshDefaultGraphicQuad == actualProof.nativeRootMeshDefaultGraphicQuad ||
                        savedTargetFallbackQuadNotCurrentlyPresent);
                    Check("rootMeshSha256", savedTargetFallbackQuadNotCurrentlyPresent ||
                        (actualProof.nativeRootMeshEmpty
                            ? String.IsNullOrEmpty(saved.rootMeshSha256) && String.IsNullOrEmpty(actualProof.rootMeshSha256)
                            : saved.rootMeshSha256 == actualProof.rootMeshSha256));
                    Check("rootMeshGeometryEvidence", savedTargetFallbackQuadNotCurrentlyPresent ||
                        saved.rootMeshGeometryEvidence == actualProof.rootMeshGeometryEvidence);
                    Check("rootMaterialEvidence", savedTargetFallbackQuadNotCurrentlyPresent ||
                        saved.rootMaterialEvidence == actualProof.rootMaterialEvidence);
                    Check("rootCanvasDefaultMaterialOnly", saved.rootCanvasDefaultMaterialOnly && actualProof.rootCanvasDefaultMaterialOnly);
                    Check("rootSourceBaseDefaultMaterial", saved.rootSourceBaseDefaultMaterial == actualProof.rootSourceBaseDefaultMaterial);
                    Check("rootMaterialSlotMatchesGraphicRendering", saved.rootMaterialSlotMatchesGraphicRendering ==
                        actualProof.rootMaterialSlotMatchesGraphicRendering || savedTargetFallbackQuadNotCurrentlyPresent);
                    Check("rootMeshVertexCount", saved.rootMeshVertexCount == actualProof.rootMeshVertexCount ||
                        savedTargetFallbackQuadNotCurrentlyPresent);
                    Check("rootMeshSubmeshCount", saved.rootMeshSubmeshCount == actualProof.rootMeshSubmeshCount ||
                        savedTargetFallbackQuadNotCurrentlyPresent);
                    Check("rootMeshIndexCount", saved.rootMeshIndexCount == actualProof.rootMeshIndexCount ||
                        savedTargetFallbackQuadNotCurrentlyPresent);
                    Check("rootCanvasMaterialCount", saved.rootCanvasMaterialCount == actualProof.rootCanvasMaterialCount ||
                        savedTargetFallbackQuadNotCurrentlyPresent);
                    Check("rootExtraMaterialModifierCount", saved.rootExtraMaterialModifierCount ==
                        actualProof.rootExtraMaterialModifierCount || savedTargetFallbackQuadNotCurrentlyPresent);
                    Check("sourceSerializedActive", saved.sourceSerializedActive == actualProof.sourceSerializedActive);
                    Check("sourceTimeScale", saved.sourceTimeScale == actualProof.sourceTimeScale);
                    Check("nativeTimeScale", saved.nativeTimeScale == actualProof.nativeTimeScale);
                    Check("sourceTimeScaleVerified", saved.sourceTimeScaleVerified && actualProof.sourceTimeScaleVerified);
                    Check("sourceIdentityTimeScaleVerified", saved.sourceIdentityTimeScaleVerified && actualProof.sourceIdentityTimeScaleVerified);
                    Check("persistentVisiblePose", saved.persistentVisiblePose && actualProof.persistentVisiblePose);
                    Check("sourceSerializedActiveVerified", saved.sourceSerializedActiveVerified && actualProof.sourceSerializedActiveVerified);
                    Check("nativeDataReferenceNull", saved.nativeDataReferenceNull && actualProof.nativeDataReferenceNull);
                    Check("registeredRendererListEmpty", saved.registeredRendererListEmpty && actualProof.registeredRendererListEmpty);
                    Check("mappedStaticFieldsVerified", saved.mappedStaticFieldsVerified && actualProof.mappedStaticFieldsVerified);
                    Check("sourceBehaviorBoundaryVerified", saved.sourceBehaviorBoundaryVerified && actualProof.sourceBehaviorBoundaryVerified);
                    Check("dynamicAssignmentUnverified", saved.dynamicAssignmentUnverified && actualProof.dynamicAssignmentUnverified);
                    Check("registeredRendererCount", saved.registeredRendererCount == 0 && actualProof.registeredRendererCount == 0);
                    Check("savedVerified", saved.verified);
                }
                var savedOK = savedProofDifferences.Count == 0;
                var verified = currentOK && savedOK;
                if (!verified) gaps.Add("STATIC_SORT_PROXY_SPINE_NULL_DATA_OWNER_INVALID:" + pair.Key +
                    ";current=" + currentOK + ";saved=" + savedOK + ";savedDiffs=" +
                    String.Join(",", savedProofDifferences) + ";proof=" + (actualDiagnostic ?? "typed-proof-differs"));
                if (saved != null)
                {
                    string actualIdentity = null;
                    if (actualProof != null) TryReadSpineIdentity(actualProof.sourceOwnerGraphic, pair.Key, out actualIdentity);
                    rows.Add(new ProxySpineNullDataOwnerReadback { sourceComponentId = pair.Key,
                        sourceNode = source.node, sourceStaticDataState = saved.sourceStaticDataState,
                        sourceBindingPlanPath = saved.sourceBindingPlanPath, sourceBindingPlanSha256 = saved.sourceBindingPlanSha256,
                        sourceManifestSha256 = saved.sourceManifestSha256,
                        sourceMaterialClosureStatus = saved.sourceMaterialClosureStatus,
                        rootMaterialEvidence = saved.rootMaterialEvidence, rootMeshSha256 = saved.rootMeshSha256,
                        rootMeshGeometryEvidence = saved.rootMeshGeometryEvidence, sourceIdentityComponentId = actualIdentity,
                        sourceTargetFieldsJson = saved.sourceTargetFieldsJson,
                        expectedFieldsJson = saved.expectedFieldsJson, actualFieldsJson = saved.actualFieldsJson,
                        sourceHasStaticDataReference = saved.sourceHasStaticDataReference,
                        sourceDataAssetIdNull = saved.sourceDataAssetIdNull, sourcePlanVerified = saved.sourcePlanVerified,
                        sourceIdentityVerified = saved.sourceIdentityVerified,
                        sourceNodeInactive = actualProof == null ? saved.sourceNodeInactive : actualProof.sourceNodeInactive,
                        sourceNodeActive = actualProof == null ? saved.sourceNodeActive : actualProof.sourceNodeActive,
                        sourceOwnerEnabled = saved.sourceOwnerEnabled,
                        sourceSerializedActive = actualProof == null ? saved.sourceSerializedActive : actualProof.sourceSerializedActive,
                        sourceSerializedActiveVerified = saved.sourceSerializedActiveVerified &&
                            actualProof != null && actualProof.sourceSerializedActiveVerified,
                        sourceActivityStage = requireHierarchyActivity ? "loaded-hierarchy-plus-serialized-scope" : "persistent-serialized-scope",
                        savedProofDifferences = savedProofDifferences.ToArray(),
                        savedOwnerReferenceEvidence = SpineObjectReferenceEvidence(saved.sourceOwnerGraphic),
                        currentOwnerReferenceEvidence = SpineObjectReferenceEvidence(actualProof == null ? null : actualProof.sourceOwnerGraphic),
                        sourceTimeScale = saved.sourceTimeScale, nativeTimeScale = saved.nativeTimeScale,
                        sourceTimeScaleVerified = saved.sourceTimeScaleVerified,
                        sourceIdentityTimeScaleVerified = saved.sourceIdentityTimeScaleVerified,
                        persistentVisiblePose = saved.persistentVisiblePose,
                        nativeDataReferenceNull = saved.nativeDataReferenceNull, nativeRootMeshEmpty = saved.nativeRootMeshEmpty,
                        nativeRootMeshDefaultGraphicQuad = saved.nativeRootMeshDefaultGraphicQuad,
                        rootCanvasDefaultMaterialOnly = saved.rootCanvasDefaultMaterialOnly,
                        rootSourceBaseDefaultMaterial = saved.rootSourceBaseDefaultMaterial,
                        rootMaterialSlotMatchesGraphicRendering = saved.rootMaterialSlotMatchesGraphicRendering,
                        registeredRendererListEmpty = saved.registeredRendererListEmpty,
                        mappedStaticFieldsVerified = saved.mappedStaticFieldsVerified,
                        sourceBehaviorBoundaryVerified = saved.sourceBehaviorBoundaryVerified,
                        dynamicAssignmentUnverified = saved.dynamicAssignmentUnverified,
                        rootMeshVertexCount = saved.rootMeshVertexCount, rootMeshSubmeshCount = saved.rootMeshSubmeshCount,
                        rootMeshIndexCount = saved.rootMeshIndexCount,
                        rootCanvasMaterialCount = saved.rootCanvasMaterialCount,
                        rootExtraMaterialModifierCount = saved.rootExtraMaterialModifierCount,
                        registeredRendererCount = saved.registeredRendererCount, verified = verified });
                }
            }
            allVerified = gaps.Count == 0 && rows.Count == expected.Count;
            diagnostics = gaps.ToArray();
            return rows.ToArray();
        }

        static ProxySpineNonDrawChildReadback[] ReadSpineNonDrawChildren(ProxyQueueSpec spec,
            IDictionary<string, GameObject> sourceNodes, NativeStaticSortQueueProxyPresenter presenter,
            out bool allVerified, out string[] diagnostics)
        {
            var rows = new List<ProxySpineNonDrawChildReadback>();
            var gaps = new List<string>();
            var expectedOwners = (spec.nonDrawRenderers ?? Array.Empty<ProxyRendererSpec>())
                .Where(row => row != null && row.sourceType == "sp.Skeleton").ToDictionary(row => row.sourceComponentId, StringComparer.Ordinal);
            var proofs = presenter == null ? Array.Empty<ProxySpineNonDrawChild>() :
                presenter.spineNonDrawChildren ?? Array.Empty<ProxySpineNonDrawChild>();
            var nullOwnerIds = new HashSet<string>((presenter == null ? Array.Empty<ProxySpineNullDataOwner>() :
                presenter.spineNullDataOwners ?? Array.Empty<ProxySpineNullDataOwner>())
                .Where(proof => proof != null).Select(proof => proof.sourceComponentId), StringComparer.Ordinal);
            foreach (var id in nullOwnerIds) expectedOwners.Remove(id);
            var proofOwners = proofs.Where(proof => proof != null).Select(proof => proof.sourceComponentId)
                .Distinct(StringComparer.Ordinal).ToArray();
            if (!new HashSet<string>(proofOwners, StringComparer.Ordinal).SetEquals(expectedOwners.Keys))
                gaps.Add("STATIC_SORT_PROXY_SPINE_NONDRAW_OWNER_DENOMINATOR_DIFFERS: expected=" + expectedOwners.Count +
                    ";observed=" + proofOwners.Length);

            var globalChildRefs = new HashSet<Graphic>();
            foreach (var pair in expectedOwners)
            {
                var sourceId = pair.Key; var expected = pair.Value;
                sourceNodes.TryGetValue(expected.node, out var node);
                var owner = node == null ? null : node.GetComponent<Graphic>();
                if (owner == null || owner.GetType().FullName != "Spine.Unity.SkeletonGraphic")
                {
                    gaps.Add("STATIC_SORT_PROXY_SPINE_NONDRAW_OWNER_MISSING: " + sourceId + ";node=" + expected.node);
                    continue;
                }
                UnityEngine.Object dataAsset = null;
                var hasDataAsset = TryReadSpineDataAsset(owner, out dataAsset);
                SpineDataIdentityEvidence dataEvidence = null; string dataDiagnostic = null;
                var dataOK = hasDataAsset && TryReadSpineDataIdentity(spec, sourceId, dataAsset, out dataEvidence, out dataDiagnostic);
                var sourceIdentityOK = TryReadSpineIdentity(owner, sourceId, out var actualSourceIdentity);
                var registered = new List<CanvasRenderer>();
                var listReadable = TryReadSpineRendererList(owner, out registered);
                var ownerProofs = proofs.Where(proof => proof != null && proof.sourceComponentId == sourceId).ToArray();
                var ownerGraphicOK = owner.enabled == expected.sourceEnabled && node.activeInHierarchy == expected.sourceActive &&
                    ownerProofs.Length > 0;
                var ownerOnlyProof = ownerProofs.Length == 1 && ownerProofs[0].ownerOnlyNoRegisteredChildren
                    ? ownerProofs[0] : null;
                if (ownerOnlyProof != null)
                {
                    var rootRenderer = owner.canvasRenderer;
                    var rootMesh = rootRenderer == null ? null : rootRenderer.GetMesh();
                    var rootIndices = rootMesh != null && rootMesh.subMeshCount == 1
                        ? rootMesh.GetIndices(0) : Array.Empty<int>();
                    var rootMeshEmpty = rootMesh == null || rootMesh.vertexCount == 0 && rootMesh.subMeshCount == 0;
                    var rootHash = rootMesh == null || rootMesh.subMeshCount == 0 ? null : MeshFingerprint(rootMesh, 0);
                    var capturedRootMeshCountsEmpty =
                        ownerOnlyProof.ownerRootMeshVertexCount == -1 && ownerOnlyProof.ownerRootMeshSubmeshCount == -1 &&
                            ownerOnlyProof.ownerRootMeshIndexCount == 0 ||
                        ownerOnlyProof.ownerRootMeshVertexCount == 0 && ownerOnlyProof.ownerRootMeshSubmeshCount == 0 &&
                            ownerOnlyProof.ownerRootMeshIndexCount == 0;
                    var currentRootMeshCountsEmpty = rootMesh == null
                        ? rootIndices.Length == 0
                        : rootMesh.vertexCount == 0 && rootMesh.subMeshCount == 0 && rootIndices.Length == 0;
                    var rootMeshFingerprintsAbsent = String.IsNullOrEmpty(ownerOnlyProof.ownerRootMeshSha256) &&
                        String.IsNullOrEmpty(rootHash);
                    var noUnmappedChildGraphics = !node.GetComponentsInChildren<Graphic>(true).Any(child => child != null && child != owner &&
                        !IsIndependentlyMappedSourceNode(child.transform, node.transform, sourceNodes));
                    var ownerActivityAllowsNoDraw = !expected.sourceActive || !expected.sourceEnabled;
                    var ownerOnlyVerified = ownerGraphicOK && ownerActivityAllowsNoDraw && dataOK && sourceIdentityOK && listReadable &&
                        registered.Count == 0 && node.activeInHierarchy == expected.sourceActive &&
                        ownerOnlyProof.sourceOwnerGraphic == owner && ownerOnlyProof.sourceDataAssetReference == dataAsset &&
                        ownerOnlyProof.sourceOwnerEnabled == expected.sourceEnabled && ownerOnlyProof.sourceNodeActive == expected.sourceActive &&
                        ownerOnlyProof.sourceDataAssetId == (dataEvidence == null ? null : dataEvidence.sourceDataAssetId) &&
                        ownerOnlyProof.sourceDataAssetPath == (dataEvidence == null ? null : dataEvidence.dataAssetPath) &&
                        ownerOnlyProof.sourceDataAssetGuid == (dataEvidence == null ? null : dataEvidence.dataAssetGuid) &&
                        ownerOnlyProof.ownerRendererListReadable && ownerOnlyProof.ownerRendererListEmpty && rootMeshEmpty &&
                        ownerOnlyProof.ownerRootMeshEmpty && capturedRootMeshCountsEmpty && currentRootMeshCountsEmpty &&
                        ownerOnlyProof.ownerRootCanvasMaterialCount == 0 && rootRenderer != null && rootRenderer.materialCount == 0 &&
                        rootMeshFingerprintsAbsent &&
                        noUnmappedChildGraphics;
                    if (!ownerOnlyVerified)
                        gaps.Add("STATIC_SORT_PROXY_SPINE_NONDRAW_EMPTY_OWNER_READBACK_INVALID: source=" + sourceId +
                            ";ownerType=" + owner.GetType().FullName + ";sourceActive=" + expected.sourceActive +
                            ";sourceEnabled=" + expected.sourceEnabled + ";listReadable=" + listReadable +
                            ";registered=" + registered.Count + ";proofCount=" + ownerProofs.Length +
                            ";captureRootEmpty=" + ownerOnlyProof.ownerRootMeshEmpty + ";captureRootMesh=" +
                            ownerOnlyProof.ownerRootMeshVertexCount + "/" + ownerOnlyProof.ownerRootMeshSubmeshCount +
                            "/" + ownerOnlyProof.ownerRootMeshIndexCount + ";currentRootEmpty=" + rootMeshEmpty +
                            ";currentRootMesh=" + (rootMesh == null ? -1 : rootMesh.vertexCount) + "/" +
                            (rootMesh == null ? -1 : rootMesh.subMeshCount) + "/" + rootIndices.Length +
                            ";rootMaterials=" + (rootRenderer == null ? -1 : rootRenderer.materialCount) +
                            ";dataGuid=" +
                            (dataEvidence == null ? "<unresolved>" : dataEvidence.dataAssetGuid) +
                            ";unmappedChildGraphics=" + !noUnmappedChildGraphics);
                    rows.Add(new ProxySpineNonDrawChildReadback {
                        sourceComponentId = sourceId, sourceNode = expected.node,
                        noDrawReason = !expected.sourceActive ? "inactive-owner-no-registered-renderers" : "disabled-owner-no-registered-renderers",
                        sourceIdentityComponentId = actualSourceIdentity, sourceDataAssetId = ownerOnlyProof.sourceDataAssetId,
                        sourceDataAssetPath = ownerOnlyProof.sourceDataAssetPath, sourceDataAssetGuid = ownerOnlyProof.sourceDataAssetGuid,
                        sourceOwnerEnabled = ownerOnlyProof.sourceOwnerEnabled, sourceNodeActive = ownerOnlyProof.sourceNodeActive,
                        sourceIdentityVerified = sourceIdentityOK, sourceDataReferenceVerified = dataOK,
                        registeredChildVerified = registered.Count == 0 && listReadable,
                        childReferencePersistent = ownerOnlyProof.sourceDataAssetReference == dataAsset && dataOK,
                        childNoDrawVerified = ownerActivityAllowsNoDraw && node.activeInHierarchy == expected.sourceActive &&
                            noUnmappedChildGraphics && rootMeshEmpty && rootRenderer != null && rootRenderer.materialCount == 0,
                        ownerOnlyNoRegisteredChildren = true, ownerRendererListReadable = listReadable,
                        ownerRendererListEmpty = ownerOnlyProof.ownerRendererListEmpty,
                        ownerRootMeshEmpty = ownerOnlyProof.ownerRootMeshEmpty,
                        ownerRootMeshVertexCount = ownerOnlyProof.ownerRootMeshVertexCount,
                        ownerRootMeshSubmeshCount = ownerOnlyProof.ownerRootMeshSubmeshCount,
                        ownerRootMeshIndexCount = ownerOnlyProof.ownerRootMeshIndexCount,
                        ownerRootCanvasMaterialCount = ownerOnlyProof.ownerRootCanvasMaterialCount,
                        ownerRootMeshSha256 = ownerOnlyProof.ownerRootMeshSha256,
                        currentOwnerRendererListReadable = listReadable,
                        currentOwnerRendererListEmpty = registered.Count == 0,
                        currentOwnerRootMeshEmpty = rootMeshEmpty,
                        currentOwnerRootMeshVertexCount = rootMesh == null ? -1 : rootMesh.vertexCount,
                        currentOwnerRootMeshSubmeshCount = rootMesh == null ? -1 : rootMesh.subMeshCount,
                        currentOwnerRootMeshIndexCount = rootIndices.Length,
                        currentOwnerRootCanvasMaterialCount = rootRenderer == null ? -1 : rootRenderer.materialCount,
                        currentOwnerRootMeshSha256 = rootHash,
                        ownerRootMeshCaptureAndCurrentFingerprintAbsent = rootMeshFingerprintsAbsent,
                        sourceChildMeshVertexCount = -1,
                        sourceChildMeshSubmeshCount = -1, sourceChildMaterialCount = -1,
                        verified = ownerOnlyVerified
                    });
                    continue;
                }
                if (!dataOK || !sourceIdentityOK || !listReadable || registered.Count != ownerProofs.Length ||
                    registered.Count == 0 || !registered.SequenceEqual(ownerProofs.Select(proof => proof.sourceChildCanvasRenderer)))
                    gaps.Add("STATIC_SORT_PROXY_SPINE_NONDRAW_OWNER_TYPED_IDENTITY_OR_RENDERER_LIST_DIFFERS: source=" + sourceId +
                        ";node=" + expected.node + ";children=" + registered.Count + ";proofs=" + ownerProofs.Length +
                        ";dataGuid=" + (dataEvidence == null ? "<unresolved>" : dataEvidence.dataAssetGuid) +
                        ";dataBinding=" + (dataDiagnostic ?? "none"));

                for (var index = 0; index < ownerProofs.Length; index++)
                {
                    var proof = ownerProofs[index];
                    var child = proof.sourceChildGraphic;
                    var renderer = child == null ? null : child.canvasRenderer;
                    var mesh = renderer == null ? null : renderer.GetMesh();
                    var material = child == null ? null : child.material;
                    var texture = material == null || material.mainTexture == null ?
                        child == null ? null : child.mainTexture : material.mainTexture;
                    long materialLocal; var materialGuid = material == null ? null : AssetGuid(material, out materialLocal);
                    var textureGuid = TextureAssetGuid(texture);
                    var registeredOK = index < registered.Count && renderer != null && renderer == registered[index] &&
                        proof.sourceChildCanvasRenderer == renderer && IsSpineCanvasSubmesh(child.gameObject, owner) &&
                        proof.childPath == SpineChildPath(node.transform, child.transform) && globalChildRefs.Add(child);
                    var childRefOK = registeredOK && materialGuid == proof.childMaterialGuid &&
                        textureGuid == proof.childTextureGuid && !String.IsNullOrWhiteSpace(AssetDatabase.GetAssetPath(material)) &&
                        proof.sourceOwnerGraphic == owner && proof.sourceDataAssetReference == dataAsset &&
                        proof.sourceDataAssetId == (dataEvidence == null ? null : dataEvidence.sourceDataAssetId) &&
                        proof.sourceDataAssetPath == (dataEvidence == null ? null : dataEvidence.dataAssetPath) &&
                        proof.sourceDataAssetGuid == (dataEvidence == null ? null : dataEvidence.dataAssetGuid);
                    var sourceChildStateOK = proof.sourceOwnerEnabled == expected.sourceEnabled &&
                        proof.sourceNodeActive == expected.sourceActive && proof.sourceChildEnabled == child.enabled &&
                        proof.sourceChildActiveSelf == child.gameObject.activeSelf &&
                        proof.sourceChildActiveInHierarchy == child.gameObject.activeInHierarchy &&
                        proof.targetChildEnabled == child.enabled && proof.targetChildActiveInHierarchy == child.gameObject.activeInHierarchy;
                    var childNoDraw = expected.sourceActive
                        ? (!child.gameObject.activeInHierarchy || !child.enabled)
                        : !child.gameObject.activeInHierarchy;
                    var verified = ownerGraphicOK && dataOK && sourceIdentityOK && registeredOK && childRefOK &&
                        sourceChildStateOK && childNoDraw;
                    if (!verified)
                        gaps.Add("STATIC_SORT_PROXY_SPINE_NONDRAW_CHILD_READBACK_INVALID: source=" + sourceId +
                            ";child=" + (child == null ? "<null>" : SpineChildPath(node.transform, child.transform)) +
                            ";type=" + (child == null ? "<null>" : child.GetType().FullName) +
                            ";sourceEnabled=" + expected.sourceEnabled + ";sourceActive=" + expected.sourceActive +
                            ";childEnabled=" + (child != null && child.enabled) +
                            ";childActiveSelf=" + (child != null && child.gameObject.activeSelf) +
                            ";childActiveInHierarchy=" + (child != null && child.gameObject.activeInHierarchy) +
                            ";meshVertices=" + (mesh == null ? -1 : mesh.vertexCount) +
                            ";meshSubmeshes=" + (mesh == null ? -1 : mesh.subMeshCount) +
                            ";materialCount=" + (renderer == null ? -1 : renderer.materialCount) +
                            ";dataGuid=" + (dataEvidence == null ? proof.sourceDataAssetGuid : dataEvidence.dataAssetGuid));
                    rows.Add(new ProxySpineNonDrawChildReadback { sourceComponentId = sourceId,
                        sourceNode = expected.node, noDrawReason = expected.sourceActive ? "disabled-source" : "inactive-source",
                        sourceIdentityComponentId = actualSourceIdentity, sourceDataAssetId = proof.sourceDataAssetId,
                        sourceDataAssetPath = proof.sourceDataAssetPath, sourceDataAssetGuid = proof.sourceDataAssetGuid,
                        childPath = child == null ? null : SpineChildPath(node.transform, child.transform),
                        childGraphicType = child == null ? null : child.GetType().FullName,
                        childMaterialGuid = materialGuid, childTextureGuid = textureGuid,
                        sourceOwnerEnabled = proof.sourceOwnerEnabled, sourceNodeActive = proof.sourceNodeActive,
                        sourceChildEnabled = proof.sourceChildEnabled, sourceChildActiveSelf = proof.sourceChildActiveSelf,
                        sourceChildActiveInHierarchy = proof.sourceChildActiveInHierarchy,
                        targetChildEnabled = child != null && child.enabled,
                        targetChildActiveInHierarchy = child != null && child.gameObject.activeInHierarchy,
                        sourceIdentityVerified = sourceIdentityOK, sourceDataReferenceVerified = dataOK,
                        registeredChildVerified = registeredOK, childReferencePersistent = childRefOK,
                        childNoDrawVerified = childNoDraw, sourceChildMeshVertexCount = mesh == null ? -1 : mesh.vertexCount,
                        sourceChildMeshSubmeshCount = mesh == null ? -1 : mesh.subMeshCount,
                        sourceChildMaterialCount = renderer == null ? -1 : renderer.materialCount,
                        verified = verified });
                }
            }
            allVerified = gaps.Count == 0;
            diagnostics = gaps.ToArray();
            return rows.ToArray();
        }

        static ProxyQueueReadback ReadProxy(ProxyQueueSpec spec,
            IDictionary<string, GameObject> sourceNodes, GameObject proxyRoot, NativeStaticSortQueueProxyPresenter presenter,
            Func<string, Sprite> resolveSprite, Func<MaskSpec, Material> resolveMaskMaterial,
            bool verifyRuntimeGeometry, bool requireSavedPrefabAsset, bool provisional,
            ProxyPrefabScopeProvenance scopeProvenance)
        {
            var expected = (spec.drawEvents ?? Array.Empty<ProxyDrawEventSpec>()).Select(row => row.kind + ":" + row.node + ":" + row.sourceComponentId).ToArray();
            var observed = new List<string>(); var graphics = new List<ProxyPresenterReadback>();
            var emptyGraphics = new List<ProxyEmptyRendererReadback>();
            var proxyMasks = new Dictionary<string, GameObject>();
            var structuralDiagnostics = new List<string>();
            var textSourceReadbacks = new List<ProxyTextSourceReadback>();
            var textSourceBindings = new Dictionary<NativeStaticSortTextSource, TextSlotBinding>();
            var textSourceVerified = new Dictionary<NativeStaticSortTextSource, bool>();
            var textSourceEvidence = new Dictionary<NativeStaticSortTextSource, TextSourceReadback>();
            var root = proxyRoot == null ? null : proxyRoot.transform;
            if (verifyRuntimeGeometry && presenter != null)
            {
                // Settle generic Canvas/layout/clip state before TMP slot
                // reads. Spine's SDK mesh finalization remains after those
                // reads, with no global Canvas rebuild following it.
                Canvas.ForceUpdateCanvases();
                presenter.RefreshSourceSuppression();
            }
            foreach (var identity in proxyRoot == null ? Array.Empty<NativeStaticSortTextSource>() :
                proxyRoot.GetComponentsInChildren<NativeStaticSortTextSource>(true))
            {
                if (identity == null) continue;
                var proxyGraphic = identity.GetComponent<NativeStaticSortQueueProxyGraphic>();
                var textMesh = proxyGraphic == null ? null : proxyGraphic.proxyMesh;
                var sourceTextSpec = (spec.renderers ?? Array.Empty<ProxyRendererSpec>())
                    .SingleOrDefault(row => row != null && row.sourceComponentId == identity.sourceComponentId);
                var expectedTextOwner = sourceTextSpec != null && sourceNodes.TryGetValue(sourceTextSpec.node, out var sourceTextNode) &&
                    sourceTextNode != null ? sourceTextNode.GetComponent<TMPro.TMP_Text>() : null;
                TextSourceReadback textReadback;
                bool textVerified;
                if (expectedTextOwner == null || identity.sourceOwner != expectedTextOwner)
                {
                    textReadback = new TextSourceReadback { sourceComponentId = identity.sourceComponentId,
                        materialSlot = identity.materialSlot, diagnostic = "TMP_SORT_EXPECTED_SOURCE_NODE_OWNER_MISSING_OR_DIFFERS" };
                    textVerified = false;
                }
                else if (verifyRuntimeGeometry)
                {
                    textVerified = UnityStaticSortTextSource.ReadInitialized(identity, textMesh, expectedTextOwner,
                        identity.sourceComponentId, presenter, out textReadback);
                }
                else if (AssetDatabase.TryGetGUIDAndLocalFileIdentifier(expectedTextOwner, out var expectedOwnerGuid, out long expectedOwnerLocalId) &&
                    !String.IsNullOrWhiteSpace(expectedOwnerGuid) && expectedOwnerLocalId != 0)
                {
                    textVerified = UnityStaticSortTextSource.ReadPersistent(identity, textMesh, expectedTextOwner,
                        identity.sourceComponentId, expectedOwnerGuid, expectedOwnerLocalId, out textReadback);
                }
                else
                {
                    textReadback = new TextSourceReadback { sourceComponentId = identity.sourceComponentId,
                        materialSlot = identity.materialSlot, diagnostic = "TMP_SORT_PERSISTENT_MAP_OWNER_ASSET_GUID_OR_LOCAL_ID_MISSING" };
                    textVerified = false;
                }
                textSourceReadbacks.Add(new ProxyTextSourceReadback { sourceNode = sourceTextSpec == null ? null : sourceTextSpec.node,
                    readbackMode = verifyRuntimeGeometry ? "loaded" : "persistent",
                    sourceComponentId = textReadback.sourceComponentId, materialSlot = textReadback.materialSlot,
                    evidence = textReadback });
                textSourceEvidence[identity] = textReadback;
                textSourceVerified[identity] = textVerified;
                if (textVerified && verifyRuntimeGeometry)
                {
                    if (UnityStaticSortTextSource.ResolveGeneratedSlot(identity, expectedTextOwner,
                            identity.sourceComponentId, presenter, out var textBinding, out var resolveDiagnostic))
                        textSourceBindings[identity] = textBinding;
                    else
                    {
                        textReadback.verified = false;
                        textReadback.diagnostic = resolveDiagnostic;
                        textVerified = false;
                        textSourceVerified[identity] = false;
                    }
                }
                if (!textVerified)
                    structuralDiagnostics.Add("STATIC_SORT_PROXY_TEXT_SOURCE_READBACK_INVALID: source=" + identity.sourceComponentId +
                        ";slot=" + identity.materialSlot + ";mode=" + (verifyRuntimeGeometry ? "initialized" : "persistent") +
                        ";diagnostic=" + textReadback.diagnostic);
            }
            if (verifyRuntimeGeometry && presenter != null)
            {
                var activeSpineOwners = new List<Graphic>();
                foreach (var row in (spec.renderers ?? Array.Empty<ProxyRendererSpec>())
                    .Where(row => row != null && row.sourceType == "sp.Skeleton" && row.sourceEnabled && row.sourceActive))
                {
                    if (!sourceNodes.TryGetValue(row.node, out var sourceNode) || sourceNode == null)
                    {
                        structuralDiagnostics.Add("STATIC_SORT_PROXY_SPINE_FINALIZE_SOURCE_NODE_MISSING:" + row.sourceComponentId);
                        continue;
                    }
                    var owner = sourceNode.GetComponent<Graphic>();
                    if (owner == null || owner.GetType().FullName != "Spine.Unity.SkeletonGraphic")
                    {
                        structuralDiagnostics.Add("STATIC_SORT_PROXY_SPINE_FINALIZE_SOURCE_OWNER_TYPE_MISMATCH:" + row.sourceComponentId);
                        continue;
                    }
                    if (TryReadSpineDataAsset(owner, out var sourceDataAsset) && sourceDataAsset != null)
                    {
                        activeSpineOwners.Add(owner);
                        continue;
                    }
                    var noDrawCurrentVerified = TryBuildSpineNullDataOwnerProof(spec, row, sourceNode, sourceNodes,
                        requireHierarchyActivity: true, out var currentNoDrawProof, out var noDrawDiagnostic);
                    var noDrawStoredRows = (presenter.spineNullDataOwners ?? Array.Empty<ProxySpineNullDataOwner>())
                        .Where(proof => proof != null && proof.sourceComponentId == row.sourceComponentId).ToArray();
                    var noDrawStoredVerified = noDrawStoredRows.Length == 1 && currentNoDrawProof != null &&
                        noDrawStoredRows[0].verified && noDrawStoredRows[0].sourceOwnerGraphic == owner &&
                        noDrawStoredRows[0].sourceNode == row.node && noDrawStoredRows[0].nativeDataReferenceNull &&
                        !noDrawStoredRows[0].sourceHasStaticDataReference && noDrawStoredRows[0].sourcePlanVerified &&
                        noDrawStoredRows[0].sourceIdentityVerified && noDrawStoredRows[0].sourceBehaviorBoundaryVerified &&
                        noDrawStoredRows[0].registeredRendererListEmpty && currentNoDrawProof.nativeDataReferenceNull &&
                        currentNoDrawProof.sourceIdentityVerified && currentNoDrawProof.sourceBehaviorBoundaryVerified &&
                        currentNoDrawProof.registeredRendererListEmpty;
                    if (!noDrawCurrentVerified || !noDrawStoredVerified)
                        structuralDiagnostics.Add("STATIC_SORT_PROXY_SPINE_NULL_DATA_NO_DRAW_NOT_PROVEN_BEFORE_FINALIZE:" +
                            row.sourceComponentId + ";current=" + noDrawCurrentVerified + ";stored=" + noDrawStoredVerified +
                            ";savedProofCount=" + noDrawStoredRows.Length + ";diagnostic=" + (noDrawDiagnostic ?? String.Empty));
                    // Creator's null SkeletonData has no source render output.
                    // Keep the exact typed evidence, but do not pass Unity's
                    // target fallback quad through the Spine mesh finalizer.
                }
                if (activeSpineOwners.Count > 0)
                    FinalizeSourceSpineStaticMesh(activeSpineOwners, provisional ? "pre-save-provisional-readback" : "loaded-readback");
            }
            var textSourcesVerified = textSourceReadbacks.All(readback => readback != null && readback.evidence != null &&
                readback.evidence.verified);
            bool Visit(Transform node)
            {
                var marker = node.GetComponent<NativeStaticSortQueueProxyMarker>();
                if (marker != null && (marker.kind == "emptyRenderer" || marker.kind == "retainedNonDraw"))
                {
                    var rendererSpec = (spec.renderers ?? Array.Empty<ProxyRendererSpec>())
                        .Concat(spec.nonDrawRenderers ?? Array.Empty<ProxyRendererSpec>())
                        .SingleOrDefault(row => row != null && row.sourceComponentId == marker.sourceComponentId);
                    var nodeOK = rendererSpec != null;
                    if (rendererSpec == null)
                        structuralDiagnostics.Add("STATIC_SORT_PROXY_EMPTY_RENDERER_SPEC_MISSING: source=" +
                            marker.sourceComponentId + ";node=" + marker.sourceNode + ";kind=" + marker.kind);
                    else
                    {
                        var empty = ReadEmptyRenderer(spec, rendererSpec, sourceNodes, marker, root, presenter, verifyRuntimeGeometry);
                        if (empty != null) emptyGraphics.Add(empty);
                        nodeOK = empty != null && empty.verified;
                        if (!nodeOK)
                            structuralDiagnostics.Add("STATIC_SORT_PROXY_EMPTY_RENDERER_READBACK_INVALID: source=" +
                                marker.sourceComponentId + ";node=" + marker.sourceNode + ";kind=" + marker.kind +
                                ";reason=" + (empty == null ? "readback-null" : empty.noDrawReason) +
                                ";sourceMeshVertices=" + (empty == null ? -1 : empty.sourceMeshVertexCount) +
                                ";sourceMaterials=" + (empty == null ? -1 : empty.sourceCanvasMaterialCount) +
                                ";sourceEnabled=" + (empty != null && empty.sourceEnabled) +
                                ";sourceActive=" + (empty != null && empty.sourceActive) +
                                ";sourceActiveSelf=" + (empty != null && empty.sourceActiveSelf) +
                                ";sourceActiveInHierarchy=" + (empty != null && empty.sourceActiveInHierarchy) +
                                ";sourceSerializedActive=" + (empty != null && empty.sourceSerializedActive) +
                                ";sourceSerializedActiveVerified=" + (empty != null && empty.sourceSerializedActiveVerified) +
                                ";sourceHierarchyActiveMatchesExpected=" + (empty != null && empty.sourceHierarchyActiveMatchesExpected) +
                                ";sourceActivityStage=" + (empty == null ? "<missing>" : empty.sourceActivityStage) +
                                ";sourceActivityMatchesExpected=" + (empty != null && empty.sourceActivityMatchesExpected) +
                                ";carrierAssetIdentity=" + (empty != null && empty.carrierAssetIdentityVerified) +
                                ";carrierOwnerScope=" + (empty != null && empty.carrierOwnerScopeVerified) +
                                ";fields=" + (empty != null && empty.typedFieldsVerified) +
                                ";sourceRef=" + (empty != null && empty.sourceReferenceVerified) +
                                ";spineEmptyPose=" + (empty == null || empty.spineEmptyPoseProof == null ? "<none>" :
                                    empty.spineEmptyPoseProof.diagnostic ?? String.Empty));
                        if (marker.kind == "emptyRenderer")
                        {
                            var eventKey = "renderer:" + marker.sourceNode + ":" + marker.sourceComponentId;
                            if (observed.Count == 0 || observed[observed.Count - 1] != eventKey) observed.Add(eventKey);
                        }
                    }
                    var childrenOK = true;
                    foreach (Transform child in node) if (!Visit(child)) childrenOK = false;
                    return nodeOK && childrenOK;
                }
                if (marker != null && marker.kind == "mask")
                {
                    var nodeOK = proxyMasks.TryAdd(marker.sourceNode, node.gameObject);
                    if (!nodeOK) structuralDiagnostics.Add("STATIC_SORT_PROXY_DUPLICATE_MASK_PROXY: node=" + marker.sourceNode +
                        ";path=" + TransformPath(node));
                    observed.Add("maskEnter:" + marker.sourceNode + ":");
                    var childrenOK = true;
                    foreach (Transform child in node) if (!Visit(child)) childrenOK = false;
                    observed.Add("maskExit:" + marker.sourceNode + ":");
                    return nodeOK && childrenOK;
                }
                var proxy = node.GetComponent<NativeStaticSortQueueProxyGraphic>();
                if (proxy != null)
                {
                    var eventKey = "renderer:" + proxy.sourceNodeId + ":" + proxy.sourceComponentId;
                    // One source renderer can produce several real native
                    // CanvasRenderer materials/submeshes. Keep each proxy
                    // leaf inspectable while comparing the source event once.
                    if (observed.Count == 0 || observed[observed.Count - 1] != eventKey) observed.Add(eventKey);
                    var textIdentity = proxy.GetComponent<NativeStaticSortTextSource>();
                    var textBinding = textIdentity != null && textSourceBindings.TryGetValue(textIdentity, out var resolvedTextBinding) ?
                        resolvedTextBinding : null;
                    var source = textIdentity == null ? proxy.sourceGraphic :
                        textBinding != null ? textBinding.sourceGraphic : textIdentity.sourceOwner as Graphic;
                    if (verifyRuntimeGeometry && textIdentity == null && source is Image image && image.sprite != null &&
                        image.enabled && image.gameObject.activeInHierarchy)
                        EnsureLoadedRegularImageMeshReady(image);
                    var sourceMesh = textIdentity != null ? textBinding == null ? null : textBinding.sourceMesh :
                        !verifyRuntimeGeometry || source == null || source.canvasRenderer == null ? null : source.canvasRenderer.GetMesh();
                    var currentHash = textIdentity != null ? textBinding == null ? textIdentity.sourceMeshSha256 : textBinding.sourceMeshSha256 :
                        sourceMesh == null ? null : MeshFingerprint(sourceMesh, proxy.submeshIndex);
                    var proxyHash = proxy.proxyMesh == null ? null : MeshFingerprint(proxy.proxyMesh, 0);
                    var renderedMesh = !verifyRuntimeGeometry ? null : proxy.GetComponent<CanvasRenderer>()?.GetMesh();
                    var renderedHash = renderedMesh == null ? null : MeshFingerprint(renderedMesh, 0);
                    var sourceUvCounts = sourceMesh == null ? proxy.sourceUvChannelVertexCounts : UvChannelVertexCounts(sourceMesh);
                    var sourceUvDimensions = sourceMesh == null ? proxy.sourceUvChannelDimensions : UvChannelDimensions(sourceMesh);
                    var proxyUvCounts = UvChannelVertexCounts(proxy.proxyMesh);
                    var proxyUvDimensions = UvChannelDimensions(proxy.proxyMesh);
                    var renderedUvCounts = renderedMesh == null ? Array.Empty<int>() : UvChannelVertexCounts(renderedMesh);
                    var renderedUvDimensions = renderedMesh == null ? Array.Empty<int>() : UvChannelDimensions(renderedMesh);
                    var sourceProxyUvVerified = sourceUvCounts != null && sourceUvDimensions != null &&
                        sourceUvCounts.SequenceEqual(proxyUvCounts) && sourceUvDimensions.SequenceEqual(proxyUvDimensions);
                    var renderedProxyUvVerified = !verifyRuntimeGeometry || renderedMesh != null &&
                        renderedUvCounts.SequenceEqual(proxyUvCounts) && renderedUvDimensions.SequenceEqual(proxyUvDimensions);
                    var currentSourceMaterial = textIdentity != null ?
                        (textBinding == null ? textIdentity.sourceMaterial : textBinding.sourceMaterial) :
                        source == null ? null : (source.material ?? Canvas.GetDefaultCanvasMaterial());
                    var currentSourceTexture = textIdentity != null ?
                        (textBinding == null ? textIdentity.sourceTexture : textBinding.sourceTexture) :
                        currentSourceMaterial != null && currentSourceMaterial.mainTexture != null ?
                            currentSourceMaterial.mainTexture : source == null ? null : source.mainTexture;
                    var sourceGraphicNode = source == null ? null : source.transform as RectTransform;
                    var proxyRt = node as RectTransform;
                    var worldRectVerified = verifyRuntimeGeometry && sourceGraphicNode != null && proxyRt != null &&
                        WorldRectMatches(sourceGraphicNode, proxyRt);
                    string expectedTransformedMeshSha256 = null;
                    string actualTransformedMeshSha256 = null;
                    var transformedMeshFingerprintVerified = verifyRuntimeGeometry && sourceGraphicNode != null && proxyRt != null &&
                        TransformedMeshMatches(sourceMesh, proxy.submeshIndex, source.transform, proxyRt, proxy.proxyMesh,
                            proxy.sourceComponentId,
                            out expectedTransformedMeshSha256, out actualTransformedMeshSha256);
                    var transformDiagnostics = verifyRuntimeGeometry ? MeasureTransformedMesh(sourceMesh, proxy.submeshIndex,
                        source == null ? null : source.transform, proxyRt, proxy.proxyMesh) : new TransformedMeshDiagnostics();
                    var transformedVertexPositionsWithinTolerance = verifyRuntimeGeometry && sourceMesh != null && proxy.proxyMesh != null &&
                        sourceMesh.vertexCount == proxy.proxyMesh.vertexCount &&
                        transformDiagnostics.maxWorldVertexError <= .001f;
                    var transformedMeshMetricsVerified = transformedVertexPositionsWithinTolerance &&
                        transformDiagnostics.topologyMatches && transformDiagnostics.uvMatches &&
                        transformDiagnostics.colorsMatch && transformDiagnostics.normalsMatch &&
                        transformDiagnostics.tangentsMatch;
                    // The exact fingerprint remains separately reported. Unity
                    // transform/inverse-transform can change vertex float bits
                    // while preserving indexed world geometry; in that case the
                    // measured position tolerance is the only approximate check.
                    var transformed = worldRectVerified && transformedMeshMetricsVerified;
                    var textOwnerGraphicReferenceValid = textIdentity != null &&
                        proxy.sourceGraphic == (Graphic)textIdentity.sourceOwner &&
                        proxy.sourceOwnerGraphic == (Graphic)textIdentity.sourceOwner;
                    var sourceReferenceValid = source != null && sourceNodes.TryGetValue(proxy.sourceNodeId, out var sourceNode) &&
                        (textIdentity != null ?
                            textIdentity.sourceComponentId == proxy.sourceComponentId &&
                            textIdentity.sourceOwner != null &&
                            textIdentity.sourceOwner == sourceNode.GetComponent<TMPro.TMP_Text>() &&
                            proxy.sourceOwnerGraphic == (Graphic)textIdentity.sourceOwner &&
                            textIdentity.sourceOwner.GetType().FullName == proxy.expectedSourceGraphicType &&
                            textOwnerGraphicReferenceValid &&
                            textIdentity.generatedSubmesh == proxy.generatedSourceChild &&
                            textSourceVerified.TryGetValue(textIdentity, out var textProofVerified) && textProofVerified &&
                            (!verifyRuntimeGeometry || textBinding != null && textBinding.sourceGraphic == source &&
                                (source.GetType().FullName == "TMPro.TMP_SubMeshUI") == proxy.generatedSourceChild) :
                            (source.transform == sourceNode.transform || source.transform.IsChildOf(sourceNode.transform)) &&
                            (proxy.generatedSourceChild ? (proxy.sourceType == "cc.Label" || proxy.sourceType == "cc.RichText" ? IsGeneratedTextSubmesh(source.gameObject) :
                                proxy.sourceType == "sp.Skeleton" && source != null && IsSpineCanvasSubmesh(source.gameObject, proxy.sourceOwnerGraphic)) :
                                source.GetType().FullName == proxy.expectedSourceGraphicType));
                    var canvasCull = source != null && source.canvasRenderer.cull;
                    long meshLocal; var meshGuid = proxy.proxyMesh == null ? null : AssetGuid(proxy.proxyMesh, out meshLocal);
                    long materialLocal; var actualMaterialGuid = proxy.proxyBaseMaterial == null ? null : AssetGuid(proxy.proxyBaseMaterial, out materialLocal);
                    var actualTextureGuid = TextureAssetGuid(proxy.proxyTexture);
                    var proxyMeshPersistent = proxy.proxyMesh != null && !string.IsNullOrEmpty(AssetDatabase.GetAssetPath(proxy.proxyMesh)) &&
                        AssetDatabase.GetAssetPath(proxy.proxyMesh).StartsWith("Assets/", StringComparison.Ordinal) &&
                        AssetGuid(proxy.proxyMesh, out meshLocal) == proxy.meshAssetGuid;
                    var proxyResourcesPersistent = proxy.proxyBaseMaterial != null &&
                        AssetDatabase.GetAssetPath(proxy.proxyBaseMaterial).StartsWith("Assets/", StringComparison.Ordinal) &&
                        actualMaterialGuid == proxy.sourceMaterialGuid && actualTextureGuid == proxy.sourceTextureGuid;
                    var renderer = proxy.GetComponent<CanvasRenderer>();
                    var sourceGraphicEnabled = textIdentity != null ?
                        (textBinding == null ? textIdentity.sourceGraphicEnabled : textBinding.sourceGraphicEnabled) :
                        source != null && source.enabled;
                    var sourceRendererAlpha = textIdentity != null && !verifyRuntimeGeometry ? proxy.sourceRendererAlpha :
                        source == null || source.canvasRenderer == null ? 0f : source.canvasRenderer.GetAlpha();
                    var sourceInheritedAlpha = textIdentity != null && !verifyRuntimeGeometry ? proxy.sourceInheritedAlpha :
                        source == null || source.canvasRenderer == null ? 0f : source.canvasRenderer.GetInheritedAlpha();
                    var proxyRendererAlpha = renderer == null ? 0f : renderer.GetAlpha();
                    var proxyInheritedAlpha = renderer == null ? 0f : renderer.GetInheritedAlpha();
                    var opacityCarrier = proxy.GetComponent<CanvasGroup>();
                    var sourceEffectiveAlpha = sourceRendererAlpha * sourceInheritedAlpha;
                    var proxyEffectiveAlpha = proxyRendererAlpha * proxyInheritedAlpha;
                    var opacityVerified = source != null && proxy.sourceOpacityCaptured && opacityCarrier != null &&
                        opacityCarrier.ignoreParentGroups && Mathf.Abs(opacityCarrier.alpha - sourceInheritedAlpha) <= 1e-4f &&
                        Mathf.Abs(proxy.sourceRendererAlpha - sourceRendererAlpha) <= 1e-4f &&
                        Mathf.Abs(proxy.sourceInheritedAlpha - sourceInheritedAlpha) <= 1e-4f &&
                        Mathf.Abs(proxyRendererAlpha - sourceRendererAlpha) <= 1e-4f &&
                        Mathf.Abs(proxyInheritedAlpha - sourceInheritedAlpha) <= 1e-4f &&
                        Mathf.Abs(proxyEffectiveAlpha - sourceEffectiveAlpha) <= 1e-4f;
                    var currentMaterialFingerprint = source == null ? null : MaterialFingerprint(currentSourceMaterial);
                    var proxyMaterialFingerprint = MaterialFingerprint(proxy.proxyBaseMaterial);
                    var persistentTextEvidenceValid = textIdentity != null && !verifyRuntimeGeometry &&
                        textSourceEvidence.TryGetValue(textIdentity, out var persistentTextEvidence) &&
                        persistentTextEvidence != null && persistentTextEvidence.verified &&
                        textSourceVerified.TryGetValue(textIdentity, out var verifiedPersistentText) && verifiedPersistentText &&
                        persistentTextEvidence.proxyMaterialGuid == actualMaterialGuid &&
                        persistentTextEvidence.bakedProxyMaterialFingerprint == proxyMaterialFingerprint &&
                        persistentTextEvidence.textureGuid == actualTextureGuid;
                    var sourceMaterialMatches = textIdentity != null && !verifyRuntimeGeometry ?
                        persistentTextEvidenceValid : source != null && currentMaterialFingerprint == proxy.sourceMaterialFingerprint &&
                        proxyMaterialFingerprint == proxy.sourceMaterialFingerprint && proxy.proxyTexture == currentSourceTexture &&
                        (textIdentity == null || textSourceVerified.TryGetValue(textIdentity, out var verifiedTextMaterial) && verifiedTextMaterial);
                    var staticSnapshotVerified = sourceReferenceValid && source != null && sourceGraphicEnabled && sourceProxyUvVerified && opacityVerified &&
                        proxyMeshPersistent && proxy.meshContentSha256 == proxyHash && meshGuid == proxy.meshAssetGuid &&
                        proxyResourcesPersistent && sourceMaterialMatches;
                    var runtimeMeshVerified = staticSnapshotVerified && renderedProxyUvVerified && canvasCull && renderer != null && !renderer.cull &&
                        proxy.sourceMeshSha256 == currentHash && renderedHash == proxyHash && transformed;
                    graphics.Add(new ProxyPresenterReadback { sourceComponentId = proxy.sourceComponentId,
                        sourceNode = proxy.sourceNodeId, nativeGraphicType = source == null ? null : source.GetType().FullName,
                        sourceMeshSha256 = currentHash,
                        currentTextSourceMeshSha256 = textBinding == null ? null : textBinding.currentSourceMeshSha256,
                        capturedSourceMeshSha256 = proxy.sourceMeshSha256,
                        meshContentSha256 = proxy.meshContentSha256, proxyMeshSha256 = proxyHash, renderedMeshSha256 = renderedHash,
                        meshAssetGuid = meshGuid, materialGuid = actualMaterialGuid,
                        textureGuid = actualTextureGuid, transformCaptureDiagnosticJson = proxy.transformCaptureDiagnosticJson,
                        worldMeasurementMethod = verifyRuntimeGeometry
                            ? "CanvasRenderer.SetMesh-local+Transform.localToWorldMatrix.MultiplyPoint3x4"
                            : "deferred-persistent-snapshot-only",
                        transformedSourceMatrixExact = source == null ? String.Empty : MatrixRoundTripEvidence(source.transform.localToWorldMatrix),
                        transformedProxyMatrixExact = proxyRt == null ? String.Empty : MatrixRoundTripEvidence(proxyRt.localToWorldMatrix),
                        transformedMatrixDifference = source == null || proxyRt == null ? "source-or-proxy-transform-missing" :
                            MatrixDifferenceEvidence(source.transform.localToWorldMatrix, proxyRt.localToWorldMatrix),
                        submeshIndex = proxy.submeshIndex,
                        sourceVertexCount = sourceMesh == null ? -1 : sourceMesh.vertexCount,
                        persistedProxyVertexCount = proxy.proxyMesh == null ? -1 : proxy.proxyMesh.vertexCount,
                        sourceUvChannelVertexCounts = sourceUvCounts,
                        proxyUvChannelVertexCounts = proxyUvCounts,
                        renderedUvChannelVertexCounts = renderedUvCounts,
                        sourceUvChannelDimensions = sourceUvDimensions,
                        proxyUvChannelDimensions = proxyUvDimensions,
                        renderedUvChannelDimensions = renderedUvDimensions,
                        sourceRendererAlpha = sourceRendererAlpha, proxyRendererAlpha = proxyRendererAlpha,
                        sourceInheritedAlpha = sourceInheritedAlpha, proxyInheritedAlpha = proxyInheritedAlpha,
                        sourceEffectiveAlpha = sourceEffectiveAlpha, proxyEffectiveAlpha = proxyEffectiveAlpha,
                        vertexCount = proxy.proxyMesh == null ? 0 : proxy.proxyMesh.vertexCount,
                        sourceQueueIndex = proxy.queueIndex, textMaterialSlot = textIdentity == null ? -1 : textIdentity.materialSlot,
                        sourceGraphicEnabled = sourceGraphicEnabled,
                        sourceCulled = canvasCull, proxyVisible = renderer != null && !renderer.cull,
                        generatedSourceChild = proxy.generatedSourceChild,
                        staticSnapshotVerified = staticSnapshotVerified, runtimeMeshVerified = runtimeMeshVerified,
                        transformedGeometryVerified = transformed, opacityVerified = opacityVerified,
                        worldRectVerified = worldRectVerified,
                        transformedMeshFingerprintVerified = transformedMeshFingerprintVerified,
                        transformedMeshMetricsVerified = transformedMeshMetricsVerified,
                        expectedTransformedMeshSha256 = expectedTransformedMeshSha256,
                        actualTransformedMeshSha256 = actualTransformedMeshSha256,
                        transformedVertexDiagnostic = VertexErrorDiagnostic(transformDiagnostics),
                        maxWorldVertexError = transformDiagnostics.maxWorldVertexError,
                        maxWorldNormalError = transformDiagnostics.maxWorldNormalError,
                        maxWorldTangentError = transformDiagnostics.maxWorldTangentError,
                        transformedTopologyMatches = transformDiagnostics.topologyMatches,
                        transformedUvMatches = transformDiagnostics.uvMatches,
                        transformedUvDiagnostic = transformDiagnostics.uvDiagnostic,
                        transformedColorsMatch = transformDiagnostics.colorsMatch,
                        transformedNormalsMatch = transformDiagnostics.normalsMatch,
                        transformedTangentsMatch = transformDiagnostics.tangentsMatch,
                        verified = verifyRuntimeGeometry ? runtimeMeshVerified : staticSnapshotVerified });
                    var graphicReadback = graphics[graphics.Count - 1];
                    if (!graphicReadback.verified)
                        structuralDiagnostics.Add("STATIC_SORT_PROXY_GRAPHIC_READBACK_INVALID: source=" + proxy.sourceComponentId +
                            ";node=" + proxy.sourceNodeId + ";type=" + graphicReadback.nativeGraphicType +
                            ";sourceMesh=" + graphicReadback.sourceMeshSha256 + ";proxyMesh=" + graphicReadback.proxyMeshSha256 +
                            ";renderedMesh=" + graphicReadback.renderedMeshSha256 +
                            ";worldVertexError=" + graphicReadback.maxWorldVertexError.ToString("R", CultureInfo.InvariantCulture) +
                            ";worldRect=" + graphicReadback.worldRectVerified +
                            ";transformedFingerprint=" + graphicReadback.transformedMeshFingerprintVerified +
                            ";transformedMetrics=" + graphicReadback.transformedMeshMetricsVerified +
                            ";expectedTransformedMesh=" + (graphicReadback.expectedTransformedMeshSha256 ?? "<null>") +
                            ";actualProxyMesh=" + (graphicReadback.actualTransformedMeshSha256 ?? "<null>") +
                            ";topology=" + graphicReadback.transformedTopologyMatches + ";uv=" + graphicReadback.transformedUvMatches +
                            ";colors=" + graphicReadback.transformedColorsMatch + ";normals=" + graphicReadback.transformedNormalsMatch +
                            ";tangents=" + graphicReadback.transformedTangentsMatch +
                            ";uvDiagnostic=" + (graphicReadback.transformedUvDiagnostic ?? String.Empty) +
                            ";worstVertex=" + (graphicReadback.transformedVertexDiagnostic ?? String.Empty) +
                            ";transformed=" + graphicReadback.transformedGeometryVerified +
                            ";static=" + graphicReadback.staticSnapshotVerified + ";runtime=" + graphicReadback.runtimeMeshVerified);
                }
                var descendantsOK = true;
                foreach (Transform child in node) if (!Visit(child)) descendantsOK = false;
                return descendantsOK;
            }
            var rootMarker = proxyRoot == null ? null : proxyRoot.GetComponent<NativeStaticSortQueueProxyMarker>();
            var traversalOk = root != null;
            if (traversalOk) foreach (Transform child in root) if (!Visit(child)) traversalOk = false;
            var observedArray = observed.ToArray();
            var textSourceSlots = textSourceReadbacks.Where(readback => readback != null)
                .Select(readback => readback.sourceComponentId + "\n" + readback.materialSlot).ToArray();
            var actualEmptyDrawIds = new HashSet<string>(emptyGraphics.Where(row => row != null && row.actualQueueIndex >= 0)
                .Select(row => row.sourceComponentId), StringComparer.Ordinal);
            var expectedTextIds = new HashSet<string>((spec.renderers ?? Array.Empty<ProxyRendererSpec>())
                .Where(row => row != null && (row.sourceType == "cc.Label" || row.sourceType == "cc.RichText") &&
                    !actualEmptyDrawIds.Contains(row.sourceComponentId) &&
                    (spec.drawEvents ?? Array.Empty<ProxyDrawEventSpec>()).Any(draw => draw != null && draw.kind == "renderer" &&
                        draw.sourceComponentId == row.sourceComponentId))
                .Select(row => row.sourceComponentId), StringComparer.Ordinal);
            var actualTextIds = new HashSet<string>(textSourceReadbacks.Where(row => row != null)
                .Select(row => row.sourceComponentId), StringComparer.Ordinal);
            textSourcesVerified &= textSourceSlots.Length == textSourceSlots.Distinct(StringComparer.Ordinal).Count() &&
                expectedTextIds.SetEquals(actualTextIds);
            if (!textSourcesVerified)
                structuralDiagnostics.Add("STATIC_SORT_PROXY_TEXT_SOURCE_DENOMINATOR_OR_IDENTITY_INVALID: expected=" +
                    String.Join(",", expectedTextIds.OrderBy(value => value, StringComparer.Ordinal)) + ";actual=" +
                    String.Join(",", actualTextIds.OrderBy(value => value, StringComparer.Ordinal)));
            var sourceTreePreserved = SourceTreeMatchesProxy(spec, sourceNodes, verifyRuntimeGeometry, out var sourceTreeDiagnostic);
            if (!sourceTreePreserved)
                structuralDiagnostics.Add("STATIC_SORT_PROXY_SOURCE_TREE_MISMATCH: " + sourceTreeDiagnostic);
            var sourceActivePreserved = (spec.sourceNodeActive ?? Array.Empty<ProxySourceActiveSpec>()).Length > 0 &&
                (spec.sourceNodeActive ?? Array.Empty<ProxySourceActiveSpec>()).All(row =>
                    row != null && sourceNodes.TryGetValue(row.node, out var go) && go != null && go.activeSelf == row.active);
            var sourceRoot = sourceNodes.TryGetValue(spec.rootScope, out var sourceRootGo) ? sourceRootGo : null;
            var expectedQueueSha = HashText(string.Join("|", (spec.drawEvents ?? Array.Empty<ProxyDrawEventSpec>())
                .Select(row => row.kind + ":" + row.node + ":" + row.sourceComponentId)));
            var presenterRefsOK = presenter != null && presenter.sourceRootId == spec.rootScope &&
                presenter.sourcePrefabId == spec.sourcePrefabId && presenter.prefabPath == spec.prefabPath &&
                presenter.sourceRoot == sourceRoot && presenter.proxyRoot == proxyRoot &&
                presenter.queueSha256 == expectedQueueSha && presenter.sourceTreeStayedUnmodified &&
                (presenter.sourceGraphics ?? Array.Empty<Graphic>()).All(graphic => graphic != null && graphic.canvasRenderer != null && graphic.canvasRenderer.cull);
            var nestedProxyRootsDisabled = presenter != null &&
                presenter.nestedProxyRoots.Length == presenter.nestedProxyRootActiveBefore.Length &&
                presenter.nestedProxyRoots.Length == presenter.nestedProxyPresenters.Length &&
                presenter.nestedProxyRoots.Select((nestedRoot, index) => nestedRoot != null &&
                    IsGeneratedSortProxyRoot(nestedRoot.transform) && !nestedRoot.activeSelf &&
                    nestedRoot.GetComponent<NativeStaticSortQueueProxyPresenter>() == presenter.nestedProxyPresenters[index]).All(value => value);
            var sourceMaskRefsOK = true;
            foreach (var mask in spec.masks ?? Array.Empty<ProxyMaskSpec>())
            {
                var matches = (presenter == null ? Array.Empty<ProxyMaskBinding>() : presenter.maskBindings ?? Array.Empty<ProxyMaskBinding>())
                    .Where(item => item != null && item.sourceId == mask.sourceId).ToArray();
                var binding = matches.Length == 1 ? matches[0] : null;
                var sourceNode = sourceNodes.TryGetValue(mask.node, out var sourceMaskNode) ? sourceMaskNode : null;
                var proxyNode = proxyMasks.TryGetValue(mask.node, out var proxyMaskNode) ? proxyMaskNode : null;
                var expectedSourceMask = sourceNode == null ? null : (Component)sourceNode.GetComponent<Mask>() ?? sourceNode.GetComponent<RectMask2D>();
                var sourceReferenceOK = binding != null && sourceNode != null && proxyNode != null &&
                    binding.sourceNode == mask.node && binding.sourceMask == expectedSourceMask &&
                    binding.proxyMask == proxyNode.GetComponent<Mask>();
                if (!sourceReferenceOK)
                {
                    sourceMaskRefsOK = false;
                    structuralDiagnostics.Add("STATIC_SORT_PROXY_MASK_SOURCE_REFERENCE_INVALID: source=" + mask.sourceId +
                        ";node=" + mask.node + ";bindings=" + matches.Length + ";sourceNode=" + (sourceNode != null) +
                        ";sourceComponent=" + (expectedSourceMask == null ? "missing" : expectedSourceMask.GetType().FullName) +
                        ";proxyNode=" + (proxyNode != null) + ";proxyMask=" + (proxyNode == null ? "missing" :
                            (proxyNode.GetComponent<Mask>() == null ? "missing" : proxyNode.GetComponent<Mask>().GetType().FullName)));
                }
            }
            var prefabAsset = requireSavedPrefabAsset && !String.IsNullOrEmpty(spec.prefabPath) ?
                AssetDatabase.LoadAssetAtPath<GameObject>(spec.prefabPath) : null;
            var provenanceIdentityMatches = scopeProvenance != null &&
                scopeProvenance.sourcePrefabId == spec.sourcePrefabId && scopeProvenance.prefabPath == spec.prefabPath &&
                scopeProvenance.rootScope == spec.rootScope &&
                scopeProvenance.persistentAssetRoot != null && scopeProvenance.loadedScopeRoot != null;
            var pinnedPersistentRoot = scopeProvenance == null ? null : scopeProvenance.persistentAssetRoot;
            var pinnedPersistentRootPath = pinnedPersistentRoot == null ? null : AssetDatabase.GetAssetPath(pinnedPersistentRoot);
            var pinnedPersistentRootPrefabPath = pinnedPersistentRoot == null ? null :
                PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(pinnedPersistentRoot);
            var persistentAssetScopeVerified = provenanceIdentityMatches && !verifyRuntimeGeometry &&
                sourceRoot != null && pinnedPersistentRoot == sourceRoot &&
                AssetDatabase.AssetPathToGUID(spec.prefabPath) != String.Empty &&
                pinnedPersistentRootPath == spec.prefabPath && pinnedPersistentRootPrefabPath == spec.prefabPath &&
                EditorUtility.IsPersistent(pinnedPersistentRoot);
            var loadedPrefabScopeOK = provenanceIdentityMatches && verifyRuntimeGeometry && sourceRoot != null &&
                sourceNodes.TryGetValue(spec.rootScope, out var mappedLoadedRoot) && mappedLoadedRoot == sourceRoot &&
                scopeProvenance.loadedScopeRoot == sourceRoot &&
                EditorUtility.IsPersistent(pinnedPersistentRoot) &&
                pinnedPersistentRootPath == spec.prefabPath && pinnedPersistentRootPrefabPath == spec.prefabPath &&
                presenter != null && presenter.sourceRoot == sourceRoot && presenter.proxyRoot == proxyRoot &&
                presenter.sourceRootId == spec.rootScope && presenter.sourcePrefabId == spec.sourcePrefabId &&
                presenter.prefabPath == spec.prefabPath;
            var loadedSourceRootIsPersistent = sourceRoot != null && EditorUtility.IsPersistent(sourceRoot);
            var prefabPathOK = !requireSavedPrefabAsset || (prefabAsset != null &&
                AssetDatabase.GetAssetPath(prefabAsset) == spec.prefabPath &&
                (verifyRuntimeGeometry ? loadedPrefabScopeOK : persistentAssetScopeVerified));
            var prefabScopeProvenanceDiagnostic = "provenance=" + provenanceIdentityMatches +
                ";persistentRootRef=" + (pinnedPersistentRoot != null) +
                ";persistentRootPath=" + (pinnedPersistentRootPath ?? "<null>") +
                ";persistentRootPrefabPath=" + (pinnedPersistentRootPrefabPath ?? "<null>") +
                ";persistentRootPersistent=" + (pinnedPersistentRoot != null && EditorUtility.IsPersistent(pinnedPersistentRoot)) +
                ";loadedRootMatches=" + (scopeProvenance != null && scopeProvenance.loadedScopeRoot == sourceRoot) +
                ";loadedRootPersistent=" + loadedSourceRootIsPersistent +
                ";loadedPresenterMatches=" + (presenter != null && presenter.sourceRoot == sourceRoot &&
                    presenter.proxyRoot == proxyRoot && presenter.sourceRootId == spec.rootScope &&
                    presenter.sourcePrefabId == spec.sourcePrefabId && presenter.prefabPath == spec.prefabPath);
            var spineDelegationRows = ReadSpineOwnerDelegations(spec, sourceNodes, presenter, verifyRuntimeGeometry,
                out var spineDelegationsVerified, out var spineDelegationDiagnostics);
            var spineNullDataOwnerRows = ReadSpineNullDataOwners(spec, sourceNodes, presenter, verifyRuntimeGeometry,
                out var spineNullDataOwnersVerified, out var spineNullDataOwnerDiagnostics);
            var spineEmptyPoseOwnerRows = emptyGraphics.Select(row => row == null ? null : row.spineEmptyPoseProof)
                .Where(row => row != null).ToArray();
            var expectedEmptyPoseOwnerIds = emptyGraphics.Where(row => row != null && row.sourceType == "sp.Skeleton" &&
                    row.noDrawReason == "source-spine-fixed-pose-no-renderable-attachments")
                .Select(row => row.sourceComponentId).OrderBy(id => id, StringComparer.Ordinal).ToArray();
            var presenterEmptyPoseOwnerIds = (presenter == null ? Array.Empty<ProxySpineEmptyPoseOwner>() :
                    presenter.spineEmptyPoseOwners ?? Array.Empty<ProxySpineEmptyPoseOwner>())
                .Where(row => row != null).Select(row => row.sourceComponentId)
                .OrderBy(id => id, StringComparer.Ordinal).ToArray();
            var spineEmptyPoseOwnersVerified = expectedEmptyPoseOwnerIds.Distinct(StringComparer.Ordinal).Count() ==
                    expectedEmptyPoseOwnerIds.Length && expectedEmptyPoseOwnerIds.SequenceEqual(presenterEmptyPoseOwnerIds) &&
                spineEmptyPoseOwnerRows.Length == expectedEmptyPoseOwnerIds.Length &&
                spineEmptyPoseOwnerRows.All(row => row.verified);
            var spineEmptyPoseOwnerDiagnostics = spineEmptyPoseOwnersVerified ? Array.Empty<string>() :
                new[] { "STATIC_SORT_PROXY_SPINE_EMPTY_POSE_OWNER_DENOMINATOR_OR_PROOF_DIFFERS: expected=" +
                    String.Join(",", expectedEmptyPoseOwnerIds) + ";presenter=" + String.Join(",", presenterEmptyPoseOwnerIds) +
                    ";readback=" + spineEmptyPoseOwnerRows.Length + ";unverified=" +
                    String.Join(",", spineEmptyPoseOwnerRows.Where(row => row == null || !row.verified)
                        .Select(row => row == null ? "<null>" : row.sourceComponentId)) };
            var spineNonDrawChildRows = ReadSpineNonDrawChildren(spec, sourceNodes, presenter,
                out var spineNonDrawChildrenVerified, out var spineNonDrawChildDiagnostics);
            var verifiedSpineIds = new HashSet<string>(spineDelegationRows.Where(row => row.verified)
                .Select(row => row.sourceComponentId), StringComparer.Ordinal);
            var validSpineDelegations = (presenter == null ? Array.Empty<ProxySpineOwnerDelegation>() :
                presenter.spineOwnerDelegations ?? Array.Empty<ProxySpineOwnerDelegation>())
                .Where(row => row != null && verifiedSpineIds.Contains(row.sourceComponentId)).ToArray();
            var validSpineNonDrawChildKeys = new HashSet<string>(spineNonDrawChildRows.Where(row => row.verified)
                .Select(row => row.sourceComponentId + "\n" + row.childPath), StringComparer.Ordinal);
            var validSpineNonDrawChildren = (presenter == null ? Array.Empty<ProxySpineNonDrawChild>() :
                presenter.spineNonDrawChildren ?? Array.Empty<ProxySpineNonDrawChild>())
                .Where(row => row != null && validSpineNonDrawChildKeys.Contains(row.sourceComponentId + "\n" + row.childPath))
                .ToArray();
            var validSpineNullDataOwners = (presenter == null ? Array.Empty<ProxySpineNullDataOwner>() :
                presenter.spineNullDataOwners ?? Array.Empty<ProxySpineNullDataOwner>())
                .Where(proof => proof != null && spineNullDataOwnerRows.Any(row => row.verified && row.sourceComponentId == proof.sourceComponentId))
                .ToArray();
            var blockInputRows = ReadBlockInputEvents(spec, sourceNodes, verifyRuntimeGeometry,
                out var blockInputEventsVerified, out var blockInputDiagnostics);
            var sourceMaskIdentityRows = ReadSourceMaskIdentities(spec, sourceNodes, resolveSprite, verifyRuntimeGeometry,
                out var sourceMaskIdentitiesVerified, out var sourceMaskIdentityDiagnostics);
            var sourceGraphicsCovered = ValidateSourceGraphicCoverage(spec, sourceNodes, root, presenter == null ?
                Array.Empty<ProxyGraphicBinding>() : presenter.bindings ?? Array.Empty<ProxyGraphicBinding>(),
                validSpineDelegations, validSpineNonDrawChildren, validSpineNullDataOwners,
                (presenter == null ? Array.Empty<ProxySpineEmptyPoseOwner>() : presenter.spineEmptyPoseOwners ??
                    Array.Empty<ProxySpineEmptyPoseOwner>()).Where(proof => proof != null &&
                    spineEmptyPoseOwnerRows.Any(row => row.verified && row.sourceComponentId == proof.sourceComponentId)),
                verifyRuntimeGeometry,
                provisional ? "pre-save-provisional" : verifyRuntimeGeometry ? "loaded" : "persistent",
                textSourceVerified, blockInputRows, sourceMaskIdentityRows,
                out var uncoveredGraphicNode);
            var layoutElement = proxyRoot == null ? null : proxyRoot.GetComponent<LayoutElement>();
            var layoutIgnored = layoutElement != null && layoutElement.ignoreLayout;
            var expectedRendererIds = (spec.drawEvents ?? Array.Empty<ProxyDrawEventSpec>())
                .Where(row => row.kind == "renderer").Select(row => row.sourceComponentId).ToArray();
            var actualRendererIds = graphics.Select(row => row.sourceComponentId)
                .Concat(emptyGraphics.Where(row => row.actualQueueIndex >= 0).Select(row => row.sourceComponentId))
                .Distinct(StringComparer.Ordinal).ToArray();
            var nonDrawIds = (spec.nonDrawRenderers ?? Array.Empty<ProxyRendererSpec>()).Select(row => row.sourceComponentId).ToArray();
            var actualNonDrawIds = emptyGraphics.Where(row => row.actualQueueIndex < 0).Select(row => row.sourceComponentId).ToArray();
            var rendererDenominatorOK = expectedRendererIds.Distinct(StringComparer.Ordinal).Count() == expectedRendererIds.Length &&
                expectedRendererIds.OrderBy(id => id, StringComparer.Ordinal).SequenceEqual(actualRendererIds.OrderBy(id => id, StringComparer.Ordinal)) &&
                nonDrawIds.Distinct(StringComparer.Ordinal).Count() == nonDrawIds.Length &&
                nonDrawIds.OrderBy(id => id, StringComparer.Ordinal).SequenceEqual(actualNonDrawIds.OrderBy(id => id, StringComparer.Ordinal));
            var sourceFieldRows = (spec.sourceFields ?? Array.Empty<QueueSortFieldSpec>()).Select(field =>
            {
                var node = field != null && sourceNodes.TryGetValue(field.node, out var value) ? value : null;
                var identity = node == null ? null : node.GetComponent<NativeStaticSortOrderIdentity>();
                return new ProxySortFieldReadback { sourceId = field == null ? null : field.sourceId,
                    node = field == null ? null : field.node, nativeId = field == null ? null : field.nativeId,
                    sourceSortOrder = field == null ? 0f : field.sortOrder,
                    enabledInSource = field != null && field.enabled, identityPresent = identity != null,
                    actualSourceId = identity == null ? null : identity.sourceId,
                    actualNativeId = identity == null ? null : identity.nativeId,
                    actualSortOrder = identity == null ? 0f : identity.sourceSortOrder,
                    actualEnabledInSource = identity != null && identity.enabledInSource,
                    identityComponentEnabled = identity != null && identity.enabled,
                    verified = identity != null && identity.sourceId == field.sourceId && identity.nativeId == field.nativeId &&
                        identity.sourceSortOrder == field.sortOrder && identity.enabledInSource == field.enabled && !identity.enabled };
            }).ToArray();
            var sourceSortRootRows = (spec.sourceSortRoots ?? Array.Empty<ProxySortRootFieldSpec>()).Select(field =>
            {
                var node = field != null && sourceNodes.TryGetValue(field.node, out var value) ? value : null;
                var identity = node == null ? null : node.GetComponent<NativeStaticSortRootIdentity>();
                return new ProxySortRootValueReadback { sourceId = field == null ? null : field.sourceId,
                    node = field == null ? null : field.node, nativeId = field == null ? null : field.nativeId,
                    enabledInSource = field != null && field.enabled, identityPresent = identity != null,
                    actualSourceId = identity == null ? null : identity.sourceId,
                    actualNativeId = identity == null ? null : identity.nativeId,
                    actualEnabledInSource = identity != null && identity.enabledInSource,
                    identityComponentEnabled = identity != null && identity.enabled,
                    verified = identity != null && identity.sourceId == field.sourceId && identity.nativeId == field.nativeId &&
                        identity.enabledInSource == field.enabled && !identity.enabled };
            }).ToArray();
            var fieldsOK = sourceFieldRows.All(row => row != null && row.verified);
            var sortRootsOK = sourceSortRootRows.All(row => row != null && row.verified);
            var expectedSequence = expected;
            var sequenceOK = traversalOk && observedArray.SequenceEqual(expectedSequence);
            var maskReadbacks = new List<ProxyMaskReadback>();
            foreach (var sourceMask in spec.masks ?? Array.Empty<ProxyMaskSpec>())
            {
                if (!proxyMasks.TryGetValue(sourceMask.node, out var maskObject))
                {
                    maskReadbacks.Add(new ProxyMaskReadback { sourceId = sourceMask.sourceId,
                        sourceNode = sourceMask.node, sourceMaskType = sourceMask.maskType, verified = false });
                    continue;
                }
                {
                    var nativeSpec = new MaskSpec { sourceId = sourceMask.sourceId, nativeId = sourceMask.nativeId,
                        node = "proxy:" + sourceMask.node, enabled = sourceMask.enabled, maskType = sourceMask.maskType,
                        inverted = sourceMask.inverted, alphaThreshold = sourceMask.alphaThreshold,
                        spriteFrameUuid = sourceMask.spriteFrameUuid, sourceFieldsJson = sourceMask.sourceFieldsJson,
                        sourceMaterialId = sourceMask.sourceMaterialId ?? String.Empty,
                        resolvedSourceMaterialId = sourceMask.resolvedSourceMaterialId ?? String.Empty,
                        sourceEffectId = sourceMask.sourceEffectId ?? String.Empty,
                        sourceEffectName = sourceMask.sourceEffectName ?? String.Empty,
                        sourceEffectDocumentSha256 = sourceMask.sourceEffectDocumentSha256 ?? String.Empty,
                        unityMaskShaderPath = sourceMask.unityMaskShaderPath, unityMaskShaderSha256 = sourceMask.unityMaskShaderSha256,
                        unityMaskMaterialGuid = sourceMask.unityMaskMaterialGuid, unityMaskMaterialPath = sourceMask.unityMaskMaterialPath };
                    var native = UnityStaticMaskSort.ReadStaticMask(nativeSpec, maskObject, resolveSprite);
                    // For readback, verify the exact generated material asset too.
                    if (sourceMask.maskType == 2)
                    {
                        var image = maskObject.GetComponent<Image>();
                        var material = resolveMaskMaterial == null ? null : resolveMaskMaterial(nativeSpec);
                        native.verified = native.verified && image != null && material != null && image.material == material;
                    }
                    var sourceTransformVerified = sourceNodes.TryGetValue(sourceMask.node, out var sourceMaskNode) &&
                        sourceMaskNode.transform is RectTransform sourceMaskRect &&
                        maskObject.transform is RectTransform proxyMaskRect && WorldRectMatches(sourceMaskRect, proxyMaskRect);
                    var maskComponent = maskObject.GetComponent<Mask>();
                    var maskIdentity = maskObject.GetComponent<NativeStaticMaskIdentity>();
                    var maskGraphic = maskObject.GetComponent<Graphic>();
                    var expectedGraphicType = sourceMask.maskType == 0 ? sourceMask.inverted ?
                        maskGraphic is NativeStaticInvertedMaskGraphic : maskGraphic is Image :
                        sourceMask.maskType == 1 ? maskGraphic is NativeStaticEllipseMaskGraphic : maskGraphic is Image;
                    var checks = new List<string>();
                    if (maskComponent == null) checks.Add("mask-present");
                    if (maskIdentity == null) checks.Add("typed-identity-present");
                    if (maskGraphic == null) checks.Add("graphic-present");
                    if (!expectedGraphicType) checks.Add("mask-graphic-type");
                    var sourceIdentityMatches = maskIdentity != null && maskIdentity.sourceId == sourceMask.sourceId &&
                        maskIdentity.nativeId == sourceMask.nativeId && maskIdentity.sourceMaskType == sourceMask.maskType &&
                        maskIdentity.sourceInverted == sourceMask.inverted;
                    if (!sourceIdentityMatches) checks.Add("source-identity");
                    var sourceFieldsMatches = maskIdentity != null && maskIdentity.sourceFieldsJson == sourceMask.sourceFieldsJson;
                    if (!sourceFieldsMatches) checks.Add("source-fields");
                    var maskEnabledMatches = maskComponent != null && maskComponent.enabled == sourceMask.enabled;
                    if (!maskEnabledMatches) checks.Add("mask-enabled");
                    var maskGraphicHidden = maskComponent != null && !maskComponent.showMaskGraphic;
                    if (!maskGraphicHidden) checks.Add("show-mask-graphic");
                    var graphicEnabledMatches = maskGraphic != null && maskGraphic.enabled == sourceMask.enabled;
                    if (!graphicEnabledMatches) checks.Add("graphic-enabled");
                    var graphicRaycastDisabled = maskGraphic != null && !maskGraphic.raycastTarget;
                    if (!graphicRaycastDisabled) checks.Add("graphic-raycast-target");
                    var sourceMaterialMatches = maskIdentity != null && maskIdentity.sourceMaterialId == sourceMask.sourceMaterialId;
                    if (!sourceMaterialMatches) checks.Add("source-material-id");
                    var resolvedSourceMaterialMatches = maskIdentity != null && maskIdentity.resolvedSourceMaterialId == sourceMask.resolvedSourceMaterialId;
                    if (!resolvedSourceMaterialMatches) checks.Add("resolved-source-material-id");
                    var sourceEffectMatches = maskIdentity != null && maskIdentity.sourceEffectId == sourceMask.sourceEffectId &&
                        maskIdentity.sourceEffectName == sourceMask.sourceEffectName &&
                        maskIdentity.sourceEffectDocumentSha256 == sourceMask.sourceEffectDocumentSha256;
                    if (!sourceEffectMatches) checks.Add("source-effect-proof");
                    var alphaThresholdMatches = maskIdentity != null && maskIdentity.sourceAlphaThreshold == sourceMask.alphaThreshold;
                    if (!alphaThresholdMatches) checks.Add("alpha-threshold");
                    var invertedCanvasMatches = !sourceMask.inverted || maskGraphic is NativeStaticInvertedMaskGraphic &&
                        maskGraphic.GetComponentInParent<Canvas>() != null;
                    if (!invertedCanvasMatches) checks.Add("inverted-canvas");
                    maskReadbacks.Add(new ProxyMaskReadback { sourceId = sourceMask.sourceId,
                        sourceNode = sourceMask.node, nativeMaskType = native.nativeType,
                        sourceMaskType = native.maskType, inverted = native.inverted, enabled = native.enabled,
                        alphaThreshold = native.alphaThreshold, sourceTransformVerified = sourceTransformVerified,
                        maskPresent = maskComponent != null, identityPresent = maskIdentity != null, graphicPresent = maskGraphic != null,
                        graphicTypeMatches = expectedGraphicType, sourceIdentityMatches = sourceIdentityMatches,
                        sourceFieldsMatches = sourceFieldsMatches, maskEnabledMatches = maskEnabledMatches,
                        maskGraphicHidden = maskGraphicHidden, graphicEnabledMatches = graphicEnabledMatches,
                        graphicRaycastDisabled = graphicRaycastDisabled, sourceMaterialMatches = sourceMaterialMatches,
                        resolvedSourceMaterialMatches = resolvedSourceMaterialMatches, sourceEffectMatches = sourceEffectMatches,
                        alphaThresholdMatches = alphaThresholdMatches, invertedCanvasMatches = invertedCanvasMatches,
                        failedChecks = checks.ToArray(),
                        verified = native.verified && sourceTransformVerified });
                    var maskReadback = maskReadbacks[maskReadbacks.Count - 1];
                    if (!maskReadback.verified)
                        structuralDiagnostics.Add("STATIC_SORT_PROXY_MASK_READBACK_INVALID: source=" + maskReadback.sourceId +
                            ";node=" + maskReadback.sourceNode + ";nativeType=" + maskReadback.nativeMaskType +
                            ";maskType=" + maskReadback.sourceMaskType + ";inverted=" + maskReadback.inverted +
                            ";enabled=" + maskReadback.enabled + ";alphaThreshold=" +
                            maskReadback.alphaThreshold.ToString("R", CultureInfo.InvariantCulture) +
                            ";sourceTransform=" + maskReadback.sourceTransformVerified +
                            ";failedChecks=" + String.Join(",", maskReadback.failedChecks ?? Array.Empty<string>()));
                }
            }
            var rootMarkerVerified = rootMarker != null && rootMarker.kind == "root" && rootMarker.sourceNode == spec.rootScope;
            var maskRowsVerified = maskReadbacks.Count == (spec.masks ?? Array.Empty<ProxyMaskSpec>()).Length &&
                maskReadbacks.All(mask => mask.verified);
            var graphicsStaticSnapshotVerified = graphics.All(graphic => graphic.staticSnapshotVerified);
            var graphicsRuntimeGeometryVerified = graphics.All(graphic => graphic.runtimeMeshVerified);
            var aggregateDiagnostics = new List<string>();
            if (!rootMarkerVerified) aggregateDiagnostics.Add("rootMarkerVerified=false;present=" + (rootMarker != null) +
                ";kind=" + (rootMarker == null ? "<null>" : rootMarker.kind) +
                ";sourceNode=" + (rootMarker == null ? "<null>" : rootMarker.sourceNode));
            if (!prefabPathOK) aggregateDiagnostics.Add("prefabPathVerified=false;path=" + (spec.prefabPath ?? "<null>") +
                ";assetFound=" + (prefabAsset != null) + ";assetPath=" +
                (prefabAsset == null ? "<null>" : AssetDatabase.GetAssetPath(prefabAsset)) +
                ";persistentSourcePath=" + (sourceRoot == null ? "<null>" :
                    PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(sourceRoot)) +
                ";persistentAssetScope=" + persistentAssetScopeVerified + ";loadedScope=" + loadedPrefabScopeOK +
                ";mappedRoot=" + (sourceRoot != null) + ";" + prefabScopeProvenanceDiagnostic);
            if (!sourceTreePreserved) aggregateDiagnostics.Add("sourceTreePreserved=false");
            if (!sourceActivePreserved) aggregateDiagnostics.Add("sourceActivePreserved=false");
            if (!fieldsOK) aggregateDiagnostics.Add("sourceFieldsPreserved=false;failed=" +
                String.Join(",", sourceFieldRows.Where(row => row == null || !row.verified).Select(row => row == null ? "<null>" : row.sourceId)));
            if (!sortRootsOK) aggregateDiagnostics.Add("sourceSortRootsPreserved=false;failed=" +
                String.Join(",", sourceSortRootRows.Where(row => row == null || !row.verified).Select(row => row == null ? "<null>" : row.sourceId)));
            if (!sequenceOK) aggregateDiagnostics.Add("drawSequenceVerified=false;expected=" +
                String.Join("|", expectedSequence) + ";observed=" + String.Join("|", observedArray) +
                ";traversal=" + traversalOk);
            if (!rendererDenominatorOK) aggregateDiagnostics.Add("rendererDenominatorVerified=false;expectedDraw=" +
                String.Join(",", expectedRendererIds) + ";actualDraw=" + String.Join(",", actualRendererIds) +
                ";expectedNonDraw=" + String.Join(",", nonDrawIds) + ";actualNonDraw=" + String.Join(",", actualNonDrawIds));
            if (!sourceGraphicsCovered) aggregateDiagnostics.Add("sourceGraphicsCovered=false;uncovered=" +
                (uncoveredGraphicNode ?? "<unknown>"));
            if (!layoutIgnored) aggregateDiagnostics.Add("layoutIgnored=false;present=" + (layoutElement != null) +
                ";ignoreLayout=" + (layoutElement != null && layoutElement.ignoreLayout));
            if (!spineDelegationsVerified) aggregateDiagnostics.Add("spineDelegationsVerified=false;" +
                String.Join(",", spineDelegationDiagnostics ?? Array.Empty<string>()));
            if (!spineNonDrawChildrenVerified) aggregateDiagnostics.Add("spineNonDrawChildrenVerified=false;" +
                String.Join(",", spineNonDrawChildDiagnostics ?? Array.Empty<string>()));
            if (!spineNullDataOwnersVerified) aggregateDiagnostics.Add("spineNullDataOwnersVerified=false;" +
                String.Join(",", spineNullDataOwnerDiagnostics ?? Array.Empty<string>()));
            if (!spineEmptyPoseOwnersVerified) aggregateDiagnostics.Add("spineEmptyPoseOwnersVerified=false;" +
                String.Join(",", spineEmptyPoseOwnerDiagnostics ?? Array.Empty<string>()));
            if (!blockInputEventsVerified) aggregateDiagnostics.Add("blockInputEventsVerified=false;" +
                String.Join(",", blockInputDiagnostics ?? Array.Empty<string>()));
            if (!sourceMaskIdentitiesVerified) aggregateDiagnostics.Add("sourceMaskIdentitiesVerified=false;" +
                String.Join(",", sourceMaskIdentityDiagnostics ?? Array.Empty<string>()));
            if (!textSourcesVerified) aggregateDiagnostics.Add("textSourcesVerified=false;failed=" +
                String.Join(",", textSourceReadbacks.Where(row => row == null || row.evidence == null || !row.evidence.verified)
                    .Select(row => row == null ? "<null>" : row.sourceComponentId + ":" + row.materialSlot)));
            if (!maskRowsVerified) aggregateDiagnostics.Add("maskRowsVerified=false;expected=" +
                (spec.masks ?? Array.Empty<ProxyMaskSpec>()).Length + ";actual=" + maskReadbacks.Count +
                ";failed=" + String.Join(",", maskReadbacks.Where(mask => mask == null || !mask.verified)
                    .Select(mask => mask == null ? "<null>" : mask.sourceId)));
            if (!sourceMaskRefsOK) aggregateDiagnostics.Add("sourceMaskReferencesVerified=false");
            if (!nestedProxyRootsDisabled) aggregateDiagnostics.Add("nestedProxyRootsDisabled=false");
            if (!presenterRefsOK) aggregateDiagnostics.Add("presenterReferencesVerified=false;present=" + (presenter != null));
            if (presenter == null || !presenter.enabled) aggregateDiagnostics.Add("presenterEnabled=false;present=" + (presenter != null));
            if (!graphicsStaticSnapshotVerified) aggregateDiagnostics.Add("graphicsStaticSnapshotVerified=false;failed=" +
                String.Join(",", graphics.Where(graphic => graphic == null || !graphic.staticSnapshotVerified)
                    .Select(graphic => graphic == null ? "<null>" : graphic.sourceComponentId + ":slot=" + graphic.textMaterialSlot)));
            if (verifyRuntimeGeometry && !graphicsRuntimeGeometryVerified)
                aggregateDiagnostics.Add("graphicsRuntimeGeometryVerified=false;failed=" +
                    String.Join(",", graphics.Where(graphic => graphic == null || !graphic.runtimeMeshVerified)
                        .Select(graphic => graphic == null ? "<null>" : graphic.sourceComponentId + ":slot=" + graphic.textMaterialSlot)));
            var nativeStructureOK = rootMarkerVerified && prefabPathOK && sourceTreePreserved && sourceActivePreserved &&
                fieldsOK && sortRootsOK && sequenceOK && rendererDenominatorOK && sourceGraphicsCovered && layoutIgnored &&
                spineDelegationsVerified && spineNonDrawChildrenVerified && spineNullDataOwnersVerified &&
                spineEmptyPoseOwnersVerified && textSourcesVerified && maskRowsVerified &&
                blockInputEventsVerified && sourceMaskIdentitiesVerified && sourceMaskRefsOK && nestedProxyRootsDisabled &&
                presenterRefsOK && presenter != null && presenter.enabled;
            var persistentSnapshotVerified = !provisional && requireSavedPrefabAsset && prefabPathOK && nativeStructureOK &&
                graphicsStaticSnapshotVerified;
            if (provisional || !requireSavedPrefabAsset) aggregateDiagnostics.Add("persistentSnapshotVerified=false;provisional=" +
                provisional + ";requireSavedPrefabAsset=" + requireSavedPrefabAsset);
            if (!persistentSnapshotVerified)
                aggregateDiagnostics.Add("persistentSnapshotVerified=false;nativeStructure=" + nativeStructureOK +
                    ";prefabPath=" + prefabPathOK + ";graphicsStaticSnapshot=" + graphicsStaticSnapshotVerified);
            var initializedPresentationVerified = persistentSnapshotVerified && verifyRuntimeGeometry &&
                graphicsRuntimeGeometryVerified;
            if (verifyRuntimeGeometry && !initializedPresentationVerified)
                aggregateDiagnostics.Add("initializedPresentationVerified=false;persistentSnapshot=" +
                    persistentSnapshotVerified + ";graphicsRuntimeGeometry=" + graphicsRuntimeGeometryVerified);
            var passed = !provisional && (verifyRuntimeGeometry ? initializedPresentationVerified : persistentSnapshotVerified);
            if (aggregateDiagnostics.Count > 0)
                structuralDiagnostics.AddRange(aggregateDiagnostics.Select(item => "STATIC_SORT_PROXY_AGGREGATE: " + item));
            return new ProxyQueueReadback { rootScope = spec.rootScope,
                proxyRootName = proxyRoot == null ? null : proxyRoot.name,
                sourceTreePreserved = sourceTreePreserved, sourceActivePreserved = sourceActivePreserved,
                sourceFieldsPreserved = fieldsOK,
                sourceSortRootsPreserved = sortRootsOK,
                sourceGraphicsCovered = sourceGraphicsCovered, layoutIgnored = layoutIgnored,
                nestedProxyRootsDisabled = nestedProxyRootsDisabled,
                drawSequenceVerified = sequenceOK, rendererDenominatorVerified = rendererDenominatorOK,
                prefabPathVerified = prefabPathOK, rootMarkerVerified = rootMarkerVerified,
                presenterReferencesVerified = presenterRefsOK, presenterEnabled = presenter != null && presenter.enabled,
                maskRowsVerified = maskRowsVerified, nativeStructureVerified = nativeStructureOK,
                graphicsStaticSnapshotVerified = graphicsStaticSnapshotVerified,
                graphicsRuntimeGeometryVerified = graphicsRuntimeGeometryVerified,
                persistentAssetScopeVerified = persistentAssetScopeVerified,
                loadedAssetScopeVerified = loadedPrefabScopeOK,
                loadedSourceRootIsPersistent = loadedSourceRootIsPersistent,
                prefabScopeProvenanceDiagnostic = prefabScopeProvenanceDiagnostic,
                aggregateDiagnostics = aggregateDiagnostics.ToArray(),
                persistentSnapshotVerified = persistentSnapshotVerified,
                initializedPresentationVerified = initializedPresentationVerified,
                runtimeGeometryDeferred = !verifyRuntimeGeometry && !provisional, provisional = provisional,
                readbackMode = provisional ? "pre-save-provisional" : verifyRuntimeGeometry ? "initialized" : "persistent",
                spineDelegationsVerified = spineDelegationsVerified,
                spineDelegationDiagnostics = spineDelegationDiagnostics,
                textSourcesVerified = textSourcesVerified,
                sourceMaskReferencesVerified = sourceMaskRefsOK,
                sourceBlockInputEventsVerified = blockInputEventsVerified,
                sourceMaskIdentitiesVerified = sourceMaskIdentitiesVerified,
                blockInputEvents = blockInputRows,
                sourceMaskIdentities = sourceMaskIdentityRows,
                spineNonDrawChildrenVerified = spineNonDrawChildrenVerified,
                spineNonDrawChildDiagnostics = spineNonDrawChildDiagnostics,
                spineNullDataOwnersVerified = spineNullDataOwnersVerified,
                spineNullDataOwnerDiagnostics = spineNullDataOwnerDiagnostics,
                spineEmptyPoseOwnersVerified = spineEmptyPoseOwnersVerified,
                spineEmptyPoseOwnerDiagnostics = spineEmptyPoseOwnerDiagnostics,
                verified = passed,
                diagnostic = provisional ? "STATIC_SORT_PROXY_PRE_SAVE_PROVISIONAL" : !passed ?
                    "STATIC_SORT_PROXY_NATIVE_MESH_MASK_OR_TREE_READBACK_FAILED" : !verifyRuntimeGeometry ?
                    "STATIC_SORT_PROXY_RUNTIME_GEOMETRY_DEFERRED" : null,
                structuralDiagnostics = structuralDiagnostics.ToArray(),
                graphics = graphics.ToArray(), spineOwnerDelegations = spineDelegationRows,
                spineNonDrawChildren = spineNonDrawChildRows,
                spineNullDataOwners = spineNullDataOwnerRows,
                spineEmptyPoseOwners = spineEmptyPoseOwnerRows,
                textSources = textSourceReadbacks.ToArray(),
                emptyRenderers = emptyGraphics.ToArray(), masks = maskReadbacks.ToArray(),
                sourceFields = sourceFieldRows, sourceSortRoots = sourceSortRootRows,
                maskSourceIds = (spec.masks ?? Array.Empty<ProxyMaskSpec>()).Select(mask => mask.sourceId).ToArray() };
        }
    }

}
