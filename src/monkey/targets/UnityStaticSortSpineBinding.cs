// Cocos static Spine data identity bridge for the static sort queue.
// The source Cocos native Spine binding-plan path remains handled by the
// existing TryReadSpineDataIdentity implementation.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Monkey.Targets.Spine;
using Spine.Unity;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;
using DataAssetSpec = Monkey.Targets.Spine.UnitySpineNativeFactory.DataAssetSpec;

namespace Monkey.StaticSortQueueProxy
{
    public static partial class UnityStaticSortQueueProxy
    {
        const string CocosStaticSpineRenderingPath = "Assets/Game/Editor/Conversion/spine-static-rendering.json";
        const string CocosImportPlanPath = "Assets/Game/Editor/Conversion/import-plan.json";

        [Serializable] sealed class CocosImportPlanSpineEnvelope
        {
            public string sourceManifestSha256;
            public string staticSpineRenderingJson;
            public string staticSpineContinuationJson;
        }

        [Serializable] sealed class CocosStaticSpineRenderingEnvelope
        {
            public int schemaVersion;
            public string contract, sourceManifestSha256, sourceContinuationSha256;
            public CocosStaticSpineRenderingComponent[] components;
            public CocosStaticSpineRenderingData[] dataAssets;
            public CocosStaticSpineSourceComponentDefaults sourceComponentDefaults;
        }

        [Serializable] sealed class CocosStaticSpineRenderingComponent
        {
            public string sourceComponentId, sourceNodeId, sourcePrefabId, templateComponentId, sourceDataAssetId;
            public bool eligible;
        }

        [Serializable] sealed class CocosStaticSpineRenderingData
        {
            public string sourceDataAssetId;
            public bool eligible;
            public DataAssetSpec factorySpec;
            public CocosStaticSpineEffectivePma effectivePma;
            public CocosStaticSpineNativeAtlasMapping nativeAtlasMapping;
        }

        [Serializable] sealed class CocosStaticSpineNativeAtlasMapping
        {
            public string sourceDataAssetId, sourceAtlasSha256, nativeAtlasSha256;
            public bool textureBytesChanged, textureDecodeInvoked;
            public CocosStaticSpineNativeAtlasPage[] pages;
        }

        [Serializable] sealed class CocosStaticSpineNativeAtlasPage
        {
            public string sourceAtlasPage, previousNativeAtlasPage, nativeAtlasPage, textureAssetPath;
        }

        [Serializable] sealed class CocosStaticSpineSourceComponentDefaults
        {
            public string contract, sourceVersion;
            public CocosStaticSpineSourceEngine sourceEngine;
            public CocosStaticSpineSourceDefaultFields fields;
            public string[] componentSourceIds, dataAssetSourceIds;
        }

        [Serializable] sealed class CocosStaticSpineSourceEngine
        {
            public string logicalPath, sha256, originUrl;
        }

        [Serializable] sealed class CocosStaticSpineSourceDefaultFields
        {
            public bool premultipliedAlpha;
        }

        [Serializable] sealed class CocosStaticSpineEffectivePma
        {
            public string contract, sourceVersion, sourceEngineSha256, field, source;
            public bool valueKnown, value;
        }

        [Serializable] sealed class CocosStaticSpineContinuationEnvelope
        {
            public int schemaVersion;
            public string contract, sourceManifestSha256;
            public CocosStaticSpineContinuationComponent[] components;
            public CocosStaticSpineContinuationData[] dataAssets;
        }

        [Serializable] sealed class CocosStaticSpineContinuationComponent
        {
            public string sourceComponentId, sourceTemplateComponentId, sourcePrefabId, sourceNodeId;
            public CocosStaticSpineContinuationDataReference sourceDataReference;
        }

        [Serializable] sealed class CocosStaticSpineContinuationDataReference
        {
            public string status, sourceDataAssetId;
        }

        [Serializable] sealed class CocosStaticSpineContinuationData
        {
            public string sourceDataAssetId, sourceNativeSha256, sourceSkeletonTextAssetPath;
            public string sourceAtlasSha256, sourceAtlasTextAssetPath;
            public long sourceNativeBytes, sourceAtlasBytes;
            public CocosStaticSpineContinuationPage[] sourceAtlasPages;
            public CocosStaticSpinePma sourcePma;
            public CocosStaticSpineEffectivePma effectivePma;
        }

        [Serializable] sealed class CocosStaticSpineContinuationPage
        {
            public int atlasPageOrdinal;
            public string sourcePageName, sourceTextureSourceId, sourceTexturePath, sourceTextureSha256;
            public long sourceTextureBytes;
        }

        [Serializable] sealed class CocosStaticSpinePma
        {
            public string status;
            public bool valueKnown, boolValue;
            public bool[] knownValues;
            public int unknownComponentCount;
        }

        /// <summary>
        /// Strictly bind an actual SkeletonDataAsset to a Cocos static rendering
        /// row. Returns applicable=false when this source component has no
        /// Cocos rendering row, allowing the existing Unity-native Spine route
        /// to run unchanged. Once a row matches, any missing or inconsistent
        /// source evidence is an applicable failure and must not fall through.
        /// </summary>
        static bool TryReadCocosStaticSpineDataIdentity(ProxyQueueSpec spec,
            string sourceComponentId, UnityEngine.Object actualDataAsset,
            out SpineDataIdentityEvidence evidence, out string diagnostic, out bool applicable, Graphic sourceOwner)
        {
            evidence = null;
            diagnostic = null;
            applicable = false;
            if (spec == null || String.IsNullOrWhiteSpace(sourceComponentId))
            { diagnostic = "cocos-static-spine-proxy-or-component-id-missing"; return false; }

            try
            {
                var projectRoot = Directory.GetParent(Application.dataPath)?.FullName;
                if (String.IsNullOrWhiteSpace(projectRoot))
                { diagnostic = "cocos-static-spine-project-root-unavailable"; return false; }
                var importPlanPath = Path.Combine(projectRoot, CocosImportPlanPath);
                if (!File.Exists(importPlanPath))
                { diagnostic = "cocos-static-spine-import-plan-missing"; return false; }
                var importBytes = File.ReadAllBytes(importPlanPath);
                var importPlan = JsonUtility.FromJson<CocosImportPlanSpineEnvelope>(Encoding.UTF8.GetString(importBytes));
                if (importPlan == null || String.IsNullOrWhiteSpace(importPlan.sourceManifestSha256) ||
                    String.IsNullOrWhiteSpace(importPlan.staticSpineRenderingJson) ||
                    String.IsNullOrWhiteSpace(importPlan.staticSpineContinuationJson))
                { diagnostic = "cocos-static-spine-import-plan-envelope-incomplete"; return false; }

                var embeddedRendering = JsonUtility.FromJson<CocosStaticSpineRenderingEnvelope>(importPlan.staticSpineRenderingJson);
                var allRenderingComponents = embeddedRendering == null ? Array.Empty<CocosStaticSpineRenderingComponent>() :
                    embeddedRendering.components ?? Array.Empty<CocosStaticSpineRenderingComponent>();
                var exactRenderingRows = allRenderingComponents.Where(row => row != null &&
                    row.sourceComponentId == sourceComponentId).ToArray();
                var componentRows = exactRenderingRows.Length > 0 ? exactRenderingRows : allRenderingComponents
                    .Where(row => row != null && row.templateComponentId == sourceComponentId).ToArray();
                if (componentRows.Length == 0)
                { diagnostic = "cocos-static-spine-component-not-in-rendering-contract"; return false; }
                applicable = true;
                if (componentRows.Length != 1)
                { diagnostic = "cocos-static-spine-component-row-ambiguous"; return false; }
                var renderComponent = componentRows[0];

                if (String.IsNullOrWhiteSpace(spec.sourceManifestSha256) ||
                    spec.sourceManifestSha256 != importPlan.sourceManifestSha256 ||
                    embeddedRendering.schemaVersion != 1 || embeddedRendering.contract != "monkey-static-spine-rendering/1" ||
                    embeddedRendering.sourceManifestSha256 != importPlan.sourceManifestSha256 ||
                    String.IsNullOrWhiteSpace(embeddedRendering.sourceContinuationSha256))
                { diagnostic = "cocos-static-spine-rendering-manifest-or-contract-mismatch"; return false; }

                var proxyRows = (spec.renderers ?? Array.Empty<ProxyRendererSpec>())
                    .Concat(spec.nonDrawRenderers ?? Array.Empty<ProxyRendererSpec>())
                    .Where(row => row != null && row.sourceComponentId == sourceComponentId).ToArray();
                if (proxyRows.Length != 1 || proxyRows[0].sourceType != "sp.Skeleton" ||
                    proxyRows[0].node != renderComponent.sourceNodeId ||
                    proxyRows[0].expectedGraphicType != "Spine.Unity.SkeletonGraphic")
                { diagnostic = "cocos-static-spine-proxy-source-origin-mismatch"; return false; }

                if (!renderComponent.eligible || String.IsNullOrWhiteSpace(renderComponent.sourceDataAssetId) ||
                    String.IsNullOrWhiteSpace(renderComponent.sourceNodeId) ||
                    String.IsNullOrWhiteSpace(renderComponent.sourcePrefabId))
                { diagnostic = "cocos-static-spine-rendering-component-not-eligible-or-unbound"; return false; }

                var continuation = JsonUtility.FromJson<CocosStaticSpineContinuationEnvelope>(importPlan.staticSpineContinuationJson);
                if (continuation == null || continuation.schemaVersion != 1 ||
                    continuation.contract != "monkey-prefab-static-spine-continuation/1" ||
                    continuation.sourceManifestSha256 != importPlan.sourceManifestSha256)
                { diagnostic = "cocos-static-spine-continuation-contract-or-manifest-mismatch"; return false; }

                var allContinuationRows = continuation.components ?? Array.Empty<CocosStaticSpineContinuationComponent>();
                var exactContinuationRows = allContinuationRows.Where(row => row != null &&
                    row.sourceComponentId == sourceComponentId).ToArray();
                var continuationRows = exactContinuationRows.Length > 0 ? exactContinuationRows : allContinuationRows
                    .Where(row => row != null && row.sourceTemplateComponentId == renderComponent.templateComponentId &&
                        row.sourcePrefabId == renderComponent.sourcePrefabId && row.sourceNodeId == renderComponent.sourceNodeId)
                    .ToArray();
                if (continuationRows.Length != 1)
                { diagnostic = "cocos-static-spine-continuation-source-component-missing-or-ambiguous"; return false; }
                var continuationComponent = continuationRows[0];
                if (continuationComponent.sourcePrefabId != renderComponent.sourcePrefabId ||
                    continuationComponent.sourceNodeId != renderComponent.sourceNodeId ||
                    (!String.IsNullOrEmpty(renderComponent.templateComponentId) &&
                     continuationComponent.sourceTemplateComponentId != renderComponent.templateComponentId) ||
                    continuationComponent.sourceDataReference == null ||
                    continuationComponent.sourceDataReference.status != "source_reference_joined_exactly" ||
                    continuationComponent.sourceDataReference.sourceDataAssetId != renderComponent.sourceDataAssetId)
                { diagnostic = "cocos-static-spine-source-template-instance-or-data-reference-mismatch"; return false; }

                var renderingDataRows = (embeddedRendering.dataAssets ?? Array.Empty<CocosStaticSpineRenderingData>())
                    .Where(row => row != null && row.sourceDataAssetId == renderComponent.sourceDataAssetId).ToArray();
                var continuationDataRows = (continuation.dataAssets ?? Array.Empty<CocosStaticSpineContinuationData>())
                    .Where(row => row != null && row.sourceDataAssetId == renderComponent.sourceDataAssetId).ToArray();
                if (renderingDataRows.Length != 1 || continuationDataRows.Length != 1 ||
                    !renderingDataRows[0].eligible || renderingDataRows[0].factorySpec == null)
                { diagnostic = "cocos-static-spine-data-source-row-missing-or-ineligible"; return false; }
                var dataRow = continuationDataRows[0];
                var factorySpec = renderingDataRows[0].factorySpec;

                var renderingPath = Path.Combine(projectRoot, CocosStaticSpineRenderingPath);
                if (!File.Exists(renderingPath))
                { diagnostic = "cocos-static-spine-rendering-source-config-missing"; return false; }
                var renderingBytes = File.ReadAllBytes(renderingPath);
                var embeddedRenderingBytes = Encoding.UTF8.GetBytes(importPlan.staticSpineRenderingJson);
                var diskRendering = JsonUtility.FromJson<CocosStaticSpineRenderingEnvelope>(Encoding.UTF8.GetString(renderingBytes));
                if (!renderingBytes.SequenceEqual(embeddedRenderingBytes) ||
                    !RenderingDocumentMatches(embeddedRendering, diskRendering, renderComponent,
                    renderComponent.sourceDataAssetId, factorySpec))
                { diagnostic = "cocos-static-spine-rendering-config-differs-from-frozen-import-plan"; return false; }

                if (actualDataAsset == null)
                { diagnostic = "cocos-static-spine-component-data-asset-null"; return false; }
                var exactDataAsset = actualDataAsset as SkeletonDataAsset;
                if (exactDataAsset == null || actualDataAsset.GetType().FullName != "Spine.Unity.SkeletonDataAsset")
                { diagnostic = "cocos-static-spine-actual-data-asset-type-mismatch"; return false; }
                if (!EditorUtility.IsPersistent(actualDataAsset) ||
                    AssetDatabase.GetAssetPath(actualDataAsset) != factorySpec.skeletonDataAssetPath ||
                    AssetDatabase.LoadAssetAtPath<SkeletonDataAsset>(factorySpec.skeletonDataAssetPath) != exactDataAsset ||
                    !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(actualDataAsset, out var actualGuid, out long actualLocalId) ||
                    String.IsNullOrWhiteSpace(actualGuid) || actualLocalId == 0)
                { diagnostic = "cocos-static-spine-data-asset-path-or-persistent-identity-mismatch"; return false; }

                var atlas = exactDataAsset.atlasAssets != null && exactDataAsset.atlasAssets.Length == 1
                    ? exactDataAsset.atlasAssets[0] as SpineAtlasAsset : null;
                if (atlas == null || AssetDatabase.GetAssetPath(atlas) != factorySpec.atlasAssetPath ||
                    AssetDatabase.LoadAssetAtPath<SpineAtlasAsset>(factorySpec.atlasAssetPath) != atlas ||
                    !EditorUtility.IsPersistent(atlas) ||
                    !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(atlas, out var atlasGuid, out long atlasLocalId) ||
                    String.IsNullOrWhiteSpace(atlasGuid) || atlasLocalId == 0)
                { diagnostic = "cocos-static-spine-atlas-asset-reference-or-persistent-identity-mismatch"; return false; }

                // The saved persistent owner may have no Canvas. Its paired
                // controlled reopen owner must remain under the explicitly
                // registered host, whose PPU is compared with source-captured
                // Canvas/Scaler evidence. Never infer PPU from the data scale.
                var renderingHash = HashBytes(renderingBytes);
                var sourceCanvasPpu = 0f;
                var canvasProof = sourceOwner != null && MonkeyImporter.TryGetStaticSpineSourceCanvasProof(sourceOwner, sourceComponentId,
                    renderComponent.sourceDataAssetId, importPlan.sourceManifestSha256, renderingHash,
                    out sourceCanvasPpu, out _, out _, out diagnostic);
                if (sourceOwner == null) diagnostic = "cocos-static-spine-owner-null-before-canvas-proof";
                MonkeyImporter.RecordStaticSpineOwnerContextUse(sourceOwner, sourceComponentId,
                    renderComponent.sourceDataAssetId, "static-sort-create-capture", canvasProof, diagnostic);
                if (!canvasProof)
                { diagnostic = diagnostic ?? "cocos-static-spine-canvas-unit-context-unverified"; return false; }
                if (sourceOwner is SkeletonGraphic sourceGraphic && sourceGraphic.SkeletonDataAsset != exactDataAsset)
                { diagnostic = "cocos-static-spine-owner-data-reference-mismatch"; return false; }
                factorySpec = ReadCocosStaticSpineSpecForValidation(Encoding.UTF8.GetString(importBytes),
                    Encoding.UTF8.GetString(renderingBytes), sourceComponentId, sourceCanvasPpu, projectRoot);
                var readback = UnitySpineNativeFactory.ReadDataAssetAsset(factorySpec);
                if (readback == null || !readback.nativeAssetIdentityVerified ||
                    !readback.savedSourceReferencesVerified || !readback.sourceProfileMaterialsVerified ||
                    !readback.staticDataVerified || !readback.scaleVerified ||
                    readback.sourceAssetId != renderComponent.sourceDataAssetId ||
                    readback.skeletonDataAssetPath != factorySpec.skeletonDataAssetPath ||
                    readback.skeletonDataAssetGuid != actualGuid || readback.atlasAssetPath != factorySpec.atlasAssetPath ||
                    readback.atlasAssetGuid != atlasGuid || readback.skeletonSha256 != factorySpec.skeletonSha256 ||
                    readback.atlasSha256 != factorySpec.atlasSha256)
                { diagnostic = "cocos-static-spine-factory-saved-reference-proof-incomplete"; return false; }

                evidence = new SpineDataIdentityEvidence
                {
                    sourceDataAssetId = renderComponent.sourceDataAssetId,
                    dataAssetPath = factorySpec.skeletonDataAssetPath,
                    dataAssetGuid = actualGuid,
                    bindingPlanPath = CocosStaticSpineRenderingPath,
                    bindingPlanSha256 = renderingHash,
                    sourceManifestSha256 = importPlan.sourceManifestSha256,
                    dataAssetLocalFileId = actualLocalId,
                    dataAssetType = actualDataAsset.GetType().FullName,
                    atlasAssetPath = factorySpec.atlasAssetPath,
                    atlasAssetGuid = atlasGuid
                };
                return true;
            }
            catch (Exception exception)
            {
                diagnostic = "cocos-static-spine-identity-validation-failed:" + exception.GetType().FullName + ":" + exception.Message;
                evidence = null;
                return false;
            }
        }

        // Shared production binding/spec boundary. The optional parser permits
        // offline SDK diagnostics with the actual serialized input; Unity callers
        // always use JsonUtility. It does not assert Unity GUID persistence.
        public static DataAssetSpec ReadCocosStaticSpineSpecForValidation(string importJson,
            string renderingJson, string sourceComponentId, float canvasPpu, string projectRoot,
            Func<string, Type, object> deserialize = null)
        {
            if (deserialize == null) deserialize = (raw, type) => JsonUtility.FromJson(raw, type);
            T Parse<T>(string raw) => (T)deserialize(raw, typeof(T));
            var plan = Parse<CocosImportPlanSpineEnvelope>(importJson);
            if (plan == null || String.IsNullOrWhiteSpace(plan.sourceManifestSha256) ||
                plan.staticSpineRenderingJson != renderingJson)
                throw new InvalidOperationException("COCOS_STATIC_SPEC_IMPORT_RENDERING_MISMATCH");
            var rendering = Parse<CocosStaticSpineRenderingEnvelope>(renderingJson);
            var continuation = Parse<CocosStaticSpineContinuationEnvelope>(plan.staticSpineContinuationJson);
            if (rendering == null || continuation == null || rendering.schemaVersion != 1 || continuation.schemaVersion != 1 ||
                rendering.contract != "monkey-static-spine-rendering/1" ||
                continuation.contract != "monkey-prefab-static-spine-continuation/1" ||
                rendering.sourceManifestSha256 != plan.sourceManifestSha256 || continuation.sourceManifestSha256 != plan.sourceManifestSha256 ||
                String.IsNullOrWhiteSpace(rendering.sourceContinuationSha256))
                throw new InvalidOperationException("COCOS_STATIC_SPEC_SOURCE_CONTRACT_MISMATCH");
            var all = rendering.components ?? Array.Empty<CocosStaticSpineRenderingComponent>();
            var exact = all.Where(x => x != null && x.sourceComponentId == sourceComponentId).ToArray();
            var rows = exact.Length > 0 ? exact : all.Where(x => x != null && x.templateComponentId == sourceComponentId).ToArray();
            if (rows.Length != 1 || !rows[0].eligible) throw new InvalidOperationException("COCOS_STATIC_SPEC_COMPONENT_MISSING_OR_AMBIGUOUS");
            var component = rows[0];
            var sourceRows = (continuation.components ?? Array.Empty<CocosStaticSpineContinuationComponent>())
                .Where(x => x != null && x.sourceComponentId == component.sourceComponentId).ToArray();
            if (sourceRows.Length != 1 || sourceRows[0].sourceNodeId != component.sourceNodeId ||
                sourceRows[0].sourcePrefabId != component.sourcePrefabId || sourceRows[0].sourceTemplateComponentId != component.templateComponentId ||
                sourceRows[0].sourceDataReference == null || sourceRows[0].sourceDataReference.status != "source_reference_joined_exactly" ||
                sourceRows[0].sourceDataReference.sourceDataAssetId != component.sourceDataAssetId)
                throw new InvalidOperationException("COCOS_STATIC_SPEC_COMPONENT_SOURCE_IDENTITY_MISMATCH");
            var renderData = (rendering.dataAssets ?? Array.Empty<CocosStaticSpineRenderingData>())
                .Single(x => x != null && x.sourceDataAssetId == component.sourceDataAssetId && x.eligible);
            var sourceData = (continuation.dataAssets ?? Array.Empty<CocosStaticSpineContinuationData>())
                .Single(x => x != null && x.sourceDataAssetId == component.sourceDataAssetId);
            byte[] Read(string relative)
            {
                if (String.IsNullOrWhiteSpace(relative) || !relative.StartsWith("Assets/", StringComparison.Ordinal) ||
                    relative.Contains("\\") || relative.Split('/').Any(part => part == ".." || part == "." || part.Length == 0))
                    throw new InvalidOperationException("COCOS_STATIC_SPEC_UNSAFE_SOURCE_PATH:" + relative);
                var path = Path.Combine(projectRoot, relative);
                return File.Exists(path) ? File.ReadAllBytes(path) : null;
            }
            if (!ValidateCocosSpineSourceDataClosure(sourceData, renderData, component.sourceComponentId, rendering, out var diagnostic, Read))
                throw new InvalidOperationException(diagnostic);
            var resolved = UnitySpineNativeFactory.ResolveStaticCanvasSpec(renderData.factorySpec, canvasPpu);
            UnitySpineNativeFactory.ValidateStaticSpecAssetFiles(resolved, Read);
            return resolved;
        }

        static bool ValidateCocosSpineSourceDataClosure(CocosStaticSpineContinuationData data,
            CocosStaticSpineRenderingData renderingData, string sourceComponentId,
            CocosStaticSpineRenderingEnvelope rendering, out string diagnostic, Func<string, byte[]> readBytes)
        {
            diagnostic = null;
            var spec = renderingData == null ? null : renderingData.factorySpec;
            if (data == null || spec == null || data.sourceDataAssetId != spec.sourceAssetId ||
                String.IsNullOrWhiteSpace(data.sourceNativeSha256) || String.IsNullOrWhiteSpace(spec.skeletonSha256) ||
                data.sourceNativeSha256 != spec.skeletonSha256 ||
                String.IsNullOrWhiteSpace(data.sourceSkeletonTextAssetPath) || String.IsNullOrWhiteSpace(spec.skeletonTextAssetPath) ||
                String.IsNullOrWhiteSpace(data.sourceAtlasTextAssetPath) || String.IsNullOrWhiteSpace(spec.atlasTextAssetPath) ||
                String.IsNullOrWhiteSpace(data.sourceAtlasSha256) || String.IsNullOrWhiteSpace(spec.atlasSha256) ||
                data.sourceAtlasPages == null || spec.pages == null || data.sourceAtlasPages.Length != spec.pages.Length)
            { diagnostic = "cocos-static-spine-continuation-and-factory-source-denominator-differs"; return false; }

            // The continuation and renderer intentionally place copied TextAssets
            // in different source-data/rendering directories. Path equality is
            // not an identity requirement; each independently pinned copy must
            // match its own source or derived hash.
            var sourceSkeleton = readBytes(data.sourceSkeletonTextAssetPath);
            var nativeSkeleton = readBytes(spec.skeletonTextAssetPath);
            if (sourceSkeleton == null || nativeSkeleton == null ||
                data.sourceNativeBytes <= 0 || sourceSkeleton.LongLength != data.sourceNativeBytes ||
                HashBytes(sourceSkeleton) != data.sourceNativeSha256 ||
                HashBytes(nativeSkeleton) != spec.skeletonSha256 ||
                !sourceSkeleton.SequenceEqual(nativeSkeleton))
            { diagnostic = "cocos-static-spine-source-and-render-skeleton-bytes-differ"; return false; }

            var sourceAtlas = readBytes(data.sourceAtlasTextAssetPath);
            var nativeAtlas = readBytes(spec.atlasTextAssetPath);
            var mapping = renderingData.nativeAtlasMapping;
            if (sourceAtlas == null || nativeAtlas == null || mapping == null ||
                data.sourceAtlasBytes <= 0 || sourceAtlas.LongLength != data.sourceAtlasBytes ||
                HashBytes(sourceAtlas) != data.sourceAtlasSha256 ||
                HashBytes(nativeAtlas) != spec.atlasSha256 ||
                mapping.sourceDataAssetId != data.sourceDataAssetId ||
                mapping.sourceAtlasSha256 != data.sourceAtlasSha256 || mapping.nativeAtlasSha256 != spec.atlasSha256 ||
                mapping.pages == null || mapping.pages.Length != spec.pages.Length ||
                mapping.textureBytesChanged || mapping.textureDecodeInvoked)
            { diagnostic = "cocos-static-spine-source-or-render-atlas-bytes-differs-from-pins"; return false; }

            if (data.sourcePma != null && data.sourcePma.valueKnown)
            {
                if (data.sourcePma.boolValue != spec.premultipliedAlpha)
                { diagnostic = "cocos-static-spine-source-pma-value-differs-from-factory-profile"; return false; }
            }
            else if (!ValidateCocosSpineDefaultPma(data, spec, sourceComponentId, rendering))
            { diagnostic = "cocos-static-spine-source-pma-unknown-without-exact-version-default-proof"; return false; }

            for (int i = 0; i < spec.pages.Length; i++)
            {
                var sourcePage = data.sourceAtlasPages[i];
                var factoryPage = spec.pages[i];
                var mappedPage = mapping.pages[i];
                if (sourcePage == null || factoryPage == null || mappedPage == null ||
                    sourcePage.atlasPageOrdinal != i || sourcePage.sourcePageName != factoryPage.sourceAtlasPage ||
                    mappedPage.sourceAtlasPage != sourcePage.sourcePageName ||
                    mappedPage.nativeAtlasPage != factoryPage.nativeAtlasPage ||
                    mappedPage.textureAssetPath != factoryPage.textureAssetPath ||
                    sourcePage.sourceTextureSourceId != factoryPage.sourceTextureSourceId ||
                    String.IsNullOrWhiteSpace(sourcePage.sourceTexturePath) || String.IsNullOrWhiteSpace(sourcePage.sourceTextureSha256))
                { diagnostic = "cocos-static-spine-source-page-identity-differs-from-factory-profile:" + i; return false; }
                var opaquePage = readBytes(sourcePage.sourceTexturePath);
                if (opaquePage == null || sourcePage.sourceTextureBytes <= 0 ||
                    opaquePage.LongLength != sourcePage.sourceTextureBytes ||
                    HashBytes(opaquePage) != sourcePage.sourceTextureSha256)
                { diagnostic = "cocos-static-spine-opaque-source-page-bytes-differs-from-pin:" + i; return false; }
            }
            if (!TryRewriteAtlasPageHeaders(sourceAtlas, mapping.pages, out var expectedNativeAtlas) ||
                !expectedNativeAtlas.SequenceEqual(nativeAtlas))
            { diagnostic = "cocos-static-spine-native-atlas-is-not-lossless-page-header-remap"; return false; }
            return true;
        }

        static bool TryRewriteAtlasPageHeaders(byte[] sourceBytes, CocosStaticSpineNativeAtlasPage[] pages,
            out byte[] rewritten)
        {
            rewritten = null;
            if (sourceBytes == null || pages == null || pages.Length == 0 ||
                pages.Any(page => page == null || String.IsNullOrWhiteSpace(page.sourceAtlasPage) ||
                    String.IsNullOrWhiteSpace(page.nativeAtlasPage)) ||
                pages.Select(page => page.sourceAtlasPage).Distinct(StringComparer.Ordinal).Count() != pages.Length)
                return false;

            var replacements = pages.ToDictionary(page => Encoding.UTF8.GetBytes(page.sourceAtlasPage),
                page => Encoding.UTF8.GetBytes(page.nativeAtlasPage), ByteArrayComparer.Instance);
            var found = new HashSet<string>(StringComparer.Ordinal);
            var output = new MemoryStream(sourceBytes.Length + 256);
            var cursor = 0;
            var lineStart = 0;
            var priorLineBlank = false;
            var nextPageIndex = 0;
            while (lineStart < sourceBytes.Length)
            {
                var newline = Array.IndexOf(sourceBytes, (byte)'\n', lineStart);
                var lineEnd = newline < 0 ? sourceBytes.Length : newline;
                var contentEnd = lineEnd > lineStart && sourceBytes[lineEnd - 1] == (byte)'\r' ? lineEnd - 1 : lineEnd;
                var contentStart = lineStart;
                if (lineStart == 0 && sourceBytes.Length >= 3 && sourceBytes[0] == 0xef &&
                    sourceBytes[1] == 0xbb && sourceBytes[2] == 0xbf)
                    contentStart += 3;
                var lineIsBlank = contentStart == contentEnd;
                var isPageHeaderPosition = lineStart == 0 || priorLineBlank;
                if (isPageHeaderPosition && !lineIsBlank)
                {
                    var oldName = new byte[contentEnd - contentStart];
                    Buffer.BlockCopy(sourceBytes, contentStart, oldName, 0, oldName.Length);
                    if (replacements.TryGetValue(oldName, out var newName))
                    {
                        var oldNameText = Encoding.UTF8.GetString(oldName);
                        if (nextPageIndex >= pages.Length || pages[nextPageIndex].sourceAtlasPage != oldNameText ||
                            !found.Add(oldNameText)) return false;
                        output.Write(sourceBytes, cursor, contentStart - cursor);
                        output.Write(newName, 0, newName.Length);
                        cursor = contentEnd;
                        nextPageIndex++;
                    }
                }
                priorLineBlank = lineIsBlank;
                if (newline < 0) break;
                lineStart = newline + 1;
            }
            if (nextPageIndex != pages.Length || found.Count != pages.Length) return false;
            output.Write(sourceBytes, cursor, sourceBytes.Length - cursor);
            rewritten = output.ToArray();
            return true;
        }

        sealed class ByteArrayComparer : System.Collections.Generic.IEqualityComparer<byte[]>
        {
            public static readonly ByteArrayComparer Instance = new ByteArrayComparer();
            public bool Equals(byte[] left, byte[] right) => ReferenceEquals(left, right) ||
                left != null && right != null && left.SequenceEqual(right);
            public int GetHashCode(byte[] value)
            {
                unchecked
                {
                    var hash = 17;
                    if (value != null) foreach (var item in value) hash = hash * 31 + item;
                    return hash;
                }
            }
        }

        static bool ValidateCocosSpineDefaultPma(CocosStaticSpineContinuationData data,
            DataAssetSpec spec, string sourceComponentId, CocosStaticSpineRenderingEnvelope rendering)
        {
            var raw = data == null ? null : data.sourcePma;
            var effective = data == null ? null : data.effectivePma;
            var renderData = rendering == null ? Array.Empty<CocosStaticSpineRenderingData>() :
                (rendering.dataAssets ?? Array.Empty<CocosStaticSpineRenderingData>())
                    .Where(row => row != null && row.sourceDataAssetId == data.sourceDataAssetId).ToArray();
            var renderEffective = renderData.Length == 1 ? renderData[0].effectivePma : null;
            var defaults = rendering == null ? null : rendering.sourceComponentDefaults;
            var engine = defaults == null ? null : defaults.sourceEngine;
            var fields = defaults == null ? null : defaults.fields;
            var exactDefaults = defaults != null &&
                defaults.contract == "monkey-cocos-spine-version-defaults/1" && defaults.sourceVersion == "2.4.15" &&
                engine != null && engine.logicalPath == "extensions/spine/Skeleton.js" &&
                engine.sha256 == "7cdc119e26aa6dceec4bd78ae30dd08f39daa2f0da5d914d2197a730b558a5e8" &&
                engine.originUrl == "https://raw.githubusercontent.com/cocos/cocos-engine/v2.4.15/extensions/spine/Skeleton.js" &&
                fields != null && fields.premultipliedAlpha &&
                (defaults.componentSourceIds ?? Array.Empty<string>()).Contains(sourceComponentId, StringComparer.Ordinal) &&
                (defaults.dataAssetSourceIds ?? Array.Empty<string>()).Contains(data.sourceDataAssetId, StringComparer.Ordinal);
            return raw != null && raw.unknownComponentCount > 0 && raw.knownValues != null &&
                raw.knownValues.All(value => value) && exactDefaults &&
                EffectivePmaMatches(effective, spec) && EffectivePmaMatches(renderEffective, spec);
        }

        static bool EffectivePmaMatches(CocosStaticSpineEffectivePma evidence, DataAssetSpec spec)
        {
            return evidence != null && evidence.contract == "monkey-cocos-spine-version-defaults/1" &&
                evidence.sourceVersion == "2.4.15" &&
                evidence.sourceEngineSha256 == "7cdc119e26aa6dceec4bd78ae30dd08f39daa2f0da5d914d2197a730b558a5e8" &&
                evidence.field == "premultipliedAlpha" && evidence.valueKnown && evidence.value &&
                evidence.source == "pinned-source-version-default" && spec != null && spec.premultipliedAlpha;
        }

        static bool RenderingDocumentMatches(CocosStaticSpineRenderingEnvelope embedded,
            CocosStaticSpineRenderingEnvelope onDisk, CocosStaticSpineRenderingComponent component,
            string dataId, DataAssetSpec spec)
        {
            if (embedded == null || onDisk == null || embedded.schemaVersion != onDisk.schemaVersion ||
                embedded.contract != onDisk.contract || embedded.sourceManifestSha256 != onDisk.sourceManifestSha256 ||
                embedded.sourceContinuationSha256 != onDisk.sourceContinuationSha256 ||
                embedded.sourceManifestSha256 == null || embedded.components == null || onDisk.components == null ||
                embedded.dataAssets == null || onDisk.dataAssets == null ||
                embedded.components.Length != onDisk.components.Length || embedded.dataAssets.Length != onDisk.dataAssets.Length)
                return false;
            if (component == null) return false;
            var embeddedComponent = embedded.components.Where(row => row != null &&
                row.sourceComponentId == component.sourceComponentId).ToArray();
            var diskComponent = onDisk.components.Where(row => row != null &&
                row.sourceComponentId == component.sourceComponentId).ToArray();
            var embeddedData = embedded.dataAssets.Where(row => row != null && row.sourceDataAssetId == dataId).ToArray();
            var diskData = onDisk.dataAssets.Where(row => row != null && row.sourceDataAssetId == dataId).ToArray();
            if (embeddedComponent.Length != 1 || diskComponent.Length != 1 || embeddedData.Length != 1 || diskData.Length != 1)
                return false;
            var a = embeddedComponent[0]; var b = diskComponent[0];
            var x = embeddedData[0]; var y = diskData[0];
            return a.eligible == b.eligible && a.sourceNodeId == b.sourceNodeId && a.sourcePrefabId == b.sourcePrefabId &&
                a.templateComponentId == b.templateComponentId && a.sourceDataAssetId == b.sourceDataAssetId &&
                x.eligible == y.eligible && x.factorySpec != null && y.factorySpec != null &&
                JsonUtility.ToJson(x.factorySpec) == JsonUtility.ToJson(y.factorySpec) &&
                JsonUtility.ToJson(x.factorySpec) == JsonUtility.ToJson(spec);
        }
    }
}
