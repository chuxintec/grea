using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;
using Monkey.StaticMaskSort;
using Monkey.StaticSortQueue;
using Monkey.StaticSortQueueProxy;

public static partial class MonkeyImporter
{
    static string StaticSortFileSha256(string path)
    {
        using (var sha = SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-", "").ToLowerInvariant();
    }

    // Readback is deliberately load-only. Missing generated assets must fail
    // verification instead of being silently recreated during inspection.
    static Material ResolveStaticSortMaskMaterialReadOnly(MaskSpec spec)
    {
        if (spec == null || String.IsNullOrWhiteSpace(spec.unityMaskMaterialPath) ||
            !spec.unityMaskMaterialPath.StartsWith("Assets/Game/Content/Materials/StaticMasks/", StringComparison.Ordinal) ||
            spec.unityMaskMaterialPath.Contains("..")) return null;
        var material = AssetDatabase.LoadAssetAtPath<Material>(spec.unityMaskMaterialPath);
        if (material == null || AssetDatabase.GetAssetPath(material) != spec.unityMaskMaterialPath || material.shader == null)
            return null;
        if (AssetDatabase.AssetPathToGUID(spec.unityMaskMaterialPath) != spec.unityMaskMaterialGuid ||
            AssetDatabase.GetAssetPath(material.shader) != spec.unityMaskShaderPath ||
            !material.HasProperty("_AlphaThreshold") ||
            Math.Abs(material.GetFloat("_AlphaThreshold") - spec.alphaThreshold) > 0.000001f)
            return null;
        var shader = AssetDatabase.LoadAssetAtPath<Shader>(spec.unityMaskShaderPath);
        if (shader == null || shader != material.shader) return null;
        var absoluteShaderPath = Path.GetFullPath(Path.Combine(Application.dataPath, "..", spec.unityMaskShaderPath));
        if (!File.Exists(absoluteShaderPath) || StaticSortFileSha256(absoluteShaderPath) != spec.unityMaskShaderSha256)
            return null;
        return material;
    }

    [Serializable] public sealed class StaticSortPrefabReadback
    {
        public string sourcePrefabId, prefabPath;
        public ProxyQueueReadback[] persistentAsset;
        public ProxyQueueReadback[] loadedInstance;
        public string[] diagnostics;
        public bool verified;
    }

    static ProxyQueueSpec[] StaticSortQueuesForPrefab(Plan plan, SourcePrefabSpec prefab)
    {
        if (plan == null || prefab == null || String.IsNullOrWhiteSpace(prefab.sourceId) ||
            String.IsNullOrWhiteSpace(prefab.path) || prefab.nodes == null)
            throw new InvalidOperationException("STATIC_SORT_PREFAB_SCOPE_INVALID");
        var queues = (plan.staticSortQueue ?? Array.Empty<ProxyQueueSpec>())
            .Where(queue => queue != null && queue.sourcePrefabId == prefab.sourceId).ToArray();
        if (queues.Length == 0)
            throw new InvalidOperationException("STATIC_SORT_QUEUE_SCOPE_MISSING: " + prefab.sourceId);
        if (queues.Select(queue => queue.rootScope).Distinct(StringComparer.Ordinal).Count() != queues.Length)
            throw new InvalidOperationException("STATIC_SORT_QUEUE_SCOPE_DUPLICATE: " + prefab.sourceId);
        var scopeNodes = new HashSet<string>(prefab.nodes, StringComparer.Ordinal);
        foreach (var queue in queues)
        {
            if (String.IsNullOrWhiteSpace(queue.rootScope) || !scopeNodes.Contains(queue.rootScope))
                throw new InvalidOperationException("STATIC_SORT_QUEUE_ROOT_OUTSIDE_PREFAB_SCOPE: " + queue.rootScope);
            if (!String.Equals(queue.prefabPath, prefab.path, StringComparison.Ordinal))
                throw new InvalidOperationException("STATIC_SORT_QUEUE_PREFAB_PATH_DIFFERS: " + queue.rootScope);
            if (String.IsNullOrWhiteSpace(queue.meshAssetFolder) || !queue.meshAssetFolder.StartsWith("Assets/", StringComparison.Ordinal) ||
                queue.meshAssetFolder.Contains(".."))
                throw new InvalidOperationException("STATIC_SORT_QUEUE_MESH_FOLDER_INVALID: " + queue.rootScope);

            var referencedNodes = new HashSet<string>(StringComparer.Ordinal) { queue.rootScope };
            foreach (var row in queue.sourceChildOrder ?? Array.Empty<ProxySourceChildrenSpec>())
            {
                if (row == null || String.IsNullOrWhiteSpace(row.node))
                    throw new InvalidOperationException("STATIC_SORT_QUEUE_CHILD_ORDER_INVALID: " + queue.rootScope);
                referencedNodes.Add(row.node);
                foreach (var child in row.children ?? Array.Empty<string>()) referencedNodes.Add(child);
            }
            foreach (var row in queue.sourceNodeActive ?? Array.Empty<ProxySourceActiveSpec>())
            {
                if (row == null || String.IsNullOrWhiteSpace(row.node))
                    throw new InvalidOperationException("STATIC_SORT_QUEUE_ACTIVE_STATE_INVALID: " + queue.rootScope);
                referencedNodes.Add(row.node);
            }
            foreach (var row in queue.renderers ?? Array.Empty<ProxyRendererSpec>())
            { if (row == null || String.IsNullOrWhiteSpace(row.node)) throw new InvalidOperationException("STATIC_SORT_QUEUE_RENDERER_INVALID: " + queue.rootScope); referencedNodes.Add(row.node); }
            foreach (var row in queue.nonDrawRenderers ?? Array.Empty<ProxyRendererSpec>())
            { if (row == null || String.IsNullOrWhiteSpace(row.node)) throw new InvalidOperationException("STATIC_SORT_QUEUE_NON_DRAW_RENDERER_INVALID: " + queue.rootScope); referencedNodes.Add(row.node); }
            foreach (var row in queue.masks ?? Array.Empty<ProxyMaskSpec>())
            { if (row == null || String.IsNullOrWhiteSpace(row.node)) throw new InvalidOperationException("STATIC_SORT_QUEUE_MASK_INVALID: " + queue.rootScope); referencedNodes.Add(row.node); }
            foreach (var row in queue.drawEvents ?? Array.Empty<ProxyDrawEventSpec>())
            { if (row == null || String.IsNullOrWhiteSpace(row.node)) throw new InvalidOperationException("STATIC_SORT_QUEUE_DRAW_EVENT_INVALID: " + queue.rootScope); referencedNodes.Add(row.node); }
            foreach (var row in queue.sourceFields ?? Array.Empty<QueueSortFieldSpec>())
            { if (row == null || String.IsNullOrWhiteSpace(row.node)) throw new InvalidOperationException("STATIC_SORT_QUEUE_SORT_FIELD_INVALID: " + queue.rootScope); referencedNodes.Add(row.node); }
            foreach (var row in queue.sourceSortRoots ?? Array.Empty<ProxySortRootFieldSpec>())
            { if (row == null || String.IsNullOrWhiteSpace(row.node)) throw new InvalidOperationException("STATIC_SORT_QUEUE_SORTROOT_INVALID: " + queue.rootScope); referencedNodes.Add(row.node); }
            foreach (var row in queue.sourceBlockInputEvents ?? Array.Empty<ProxyBlockInputSpec>())
            { if (row == null || String.IsNullOrWhiteSpace(row.node)) throw new InvalidOperationException("STATIC_SORT_QUEUE_BLOCK_INPUT_INVALID: " + queue.rootScope); referencedNodes.Add(row.node); }
            var outside = referencedNodes.Where(node => !scopeNodes.Contains(node)).ToArray();
            if (outside.Length != 0)
                throw new InvalidOperationException("STATIC_SORT_QUEUE_NODE_OUTSIDE_PREFAB_SCOPE: " + outside[0]);

            var queueNodeIds = new HashSet<string>((queue.sourceChildOrder ?? Array.Empty<ProxySourceChildrenSpec>())
                .Where(row => row != null && !String.IsNullOrWhiteSpace(row.node)).Select(row => row.node), StringComparer.Ordinal);
            queueNodeIds.Add(queue.rootScope);
            var activeSelf = (queue.sourceNodeActive ?? Array.Empty<ProxySourceActiveSpec>())
                .Where(row => row != null && !String.IsNullOrWhiteSpace(row.node))
                .GroupBy(row => row.node, StringComparer.Ordinal).ToDictionary(group => group.Key, group => group.Single().active, StringComparer.Ordinal);
            var parentByNode = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (var parent in queue.sourceChildOrder ?? Array.Empty<ProxySourceChildrenSpec>())
                if (parent != null)
                    foreach (var child in parent.children ?? Array.Empty<string>())
                        if (parentByNode.ContainsKey(child))
                            throw new InvalidOperationException("STATIC_SORT_QUEUE_PARENT_DUPLICATE: " + child);
                        else parentByNode.Add(child, parent.node);
            bool EffectiveActive(string node)
            {
                var cursor = node; var seen = new HashSet<string>(StringComparer.Ordinal);
                while (!String.IsNullOrWhiteSpace(cursor))
                {
                    if (!seen.Add(cursor) || !activeSelf.TryGetValue(cursor, out var active) || !active) return false;
                    if (cursor == queue.rootScope) return true;
                    if (!parentByNode.TryGetValue(cursor, out var parent)) return false;
                    cursor = parent;
                }
                return false;
            }
            var blockInputRows = (plan.components ?? Array.Empty<ComponentSpec>())
                .Where(component => component != null && component.type == "cc.BlockInputEvents" &&
                    queueNodeIds.Contains(component.node))
                .Select(component =>
                {
                    var graphicCandidates = (plan.components ?? Array.Empty<ComponentSpec>())
                        .Where(candidate => candidate != null && candidate.convertible && candidate.node == component.node &&
                            (candidate.type == "cc.Sprite" || candidate.type == "cc.Label" ||
                             candidate.type == "cc.RichText" || candidate.type == "sp.Skeleton"))
                        .ToArray();
                    if (graphicCandidates.Length > 1)
                        throw new InvalidOperationException("STATIC_SORT_BLOCK_INPUT_SOURCE_GRAPHIC_AMBIGUOUS: " + component.sourceId);
                    var graphic = graphicCandidates.SingleOrDefault();
                    var nativeGraphicType = graphic == null ? null : graphic.type == "cc.Sprite" ? "UnityEngine.UI.Image" :
                        graphic.type == "sp.Skeleton" ? "Spine.Unity.SkeletonGraphic" : "TMPro.TextMeshProUGUI";
                    return new ProxyBlockInputSpec { sourceComponentId = component.sourceId, node = component.node,
                        sourceType = component.type, sourceEnabled = component.enabled,
                        sourceActive = EffectiveActive(component.node),
                        expectedSourceGraphicComponentId = graphic == null ? null : graphic.sourceId,
                        expectedSourceGraphicType = nativeGraphicType };
                }).ToArray();
            if (blockInputRows.Any(row => row == null || String.IsNullOrWhiteSpace(row.sourceComponentId) ||
                String.IsNullOrWhiteSpace(row.node) || row.sourceType != "cc.BlockInputEvents"))
                throw new InvalidOperationException("STATIC_SORT_BLOCK_INPUT_SOURCE_CONTRACT_INVALID: " + queue.rootScope);
            queue.sourceBlockInputEvents = blockInputRows;
            var sourceMaskRows = (plan.staticMasks == null ? Array.Empty<MaskSpec>() :
                    plan.staticMasks.masks ?? Array.Empty<MaskSpec>())
                .Where(mask => mask != null && queueNodeIds.Contains(mask.node))
                .Select(mask =>
                {
                    if (!activeSelf.TryGetValue(mask.node, out var activeSelfValue))
                        throw new InvalidOperationException("STATIC_SORT_SOURCE_MASK_ACTIVE_STATE_MISSING: " + mask.sourceId);
                    return new ProxySourceMaskIdentitySpec { sourceId = mask.sourceId, nativeId = mask.nativeId,
                        node = mask.node, maskType = mask.maskType, enabled = mask.enabled, inverted = mask.inverted,
                        alphaThreshold = mask.alphaThreshold, spriteFrameUuid = mask.spriteFrameUuid,
                        sourceFieldsJson = mask.sourceFieldsJson, sourceMaterialId = mask.sourceMaterialId,
                        resolvedSourceMaterialId = mask.resolvedSourceMaterialId, sourceEffectId = mask.sourceEffectId,
                        sourceEffectName = mask.sourceEffectName, sourceEffectDocumentSha256 = mask.sourceEffectDocumentSha256,
                        unityMaskShaderPath = mask.unityMaskShaderPath, unityMaskShaderSha256 = mask.unityMaskShaderSha256,
                        unityMaskMaterialGuid = mask.unityMaskMaterialGuid, unityMaskMaterialPath = mask.unityMaskMaterialPath,
                        sourceActiveSelf = activeSelfValue, sourceActive = EffectiveActive(mask.node) };
                }).ToArray();
            if (sourceMaskRows.Select(row => row.sourceId).Distinct(StringComparer.Ordinal).Count() != sourceMaskRows.Length)
                throw new InvalidOperationException("STATIC_SORT_SOURCE_MASK_IDENTITY_DUPLICATE: " + queue.rootScope);
            queue.sourceMaskIdentities = sourceMaskRows;
        }
        return queues.OrderBy(queue => queue.rootScope, StringComparer.Ordinal).ToArray();
    }

    static void CreateStaticSortIdentities(Plan plan, IDictionary<string, GameObject> nodes)
    {
        if (plan == null || nodes == null) throw new InvalidOperationException("STATIC_SORT_IDENTITY_PLAN_INVALID");
        var queueSpecs = plan.staticSortQueue ?? Array.Empty<ProxyQueueSpec>();
        var sortOrders = new Dictionary<string, QueueSortFieldSpec>(StringComparer.Ordinal);
        var sortRoots = new Dictionary<string, ProxySortRootFieldSpec>(StringComparer.Ordinal);
        foreach (var queue in queueSpecs)
        {
            if (queue == null) throw new InvalidOperationException("STATIC_SORT_IDENTITY_QUEUE_SPEC_NULL");
            foreach (var field in queue.sourceFields ?? Array.Empty<QueueSortFieldSpec>())
            {
                if (field == null || String.IsNullOrWhiteSpace(field.sourceId) || String.IsNullOrWhiteSpace(field.nativeId) ||
                    String.IsNullOrWhiteSpace(field.node) || !nodes.ContainsKey(field.node))
                    throw new InvalidOperationException("STATIC_SORT_IDENTITY_SORTORDER_SPEC_INVALID: " + (field == null ? "null" : field.sourceId));
                var key = field.node + "\n" + field.sourceId;
                if (sortOrders.TryGetValue(key, out var prior) &&
                    (prior.nativeId != field.nativeId || prior.sortOrder != field.sortOrder || prior.enabled != field.enabled))
                    throw new InvalidOperationException("STATIC_SORT_IDENTITY_SORTORDER_CLONES_DISAGREE: " + field.sourceId);
                sortOrders[key] = field;
            }
            foreach (var field in queue.sourceSortRoots ?? Array.Empty<ProxySortRootFieldSpec>())
            {
                if (field == null || String.IsNullOrWhiteSpace(field.sourceId) || String.IsNullOrWhiteSpace(field.nativeId) ||
                    String.IsNullOrWhiteSpace(field.node) || !nodes.ContainsKey(field.node))
                    throw new InvalidOperationException("STATIC_SORT_IDENTITY_SORTROOT_SPEC_INVALID: " + (field == null ? "null" : field.sourceId));
                var key = field.node + "\n" + field.sourceId;
                if (sortRoots.TryGetValue(key, out var prior) && (prior.nativeId != field.nativeId || prior.enabled != field.enabled))
                    throw new InvalidOperationException("STATIC_SORT_IDENTITY_SORTROOT_CLONES_DISAGREE: " + field.sourceId);
                sortRoots[key] = field;
            }
        }

        foreach (var field in sortOrders.Values)
        {
            var node = nodes[field.node];
            var identity = node.GetComponent<NativeStaticSortOrderIdentity>();
            if (identity == null) identity = node.AddComponent<NativeStaticSortOrderIdentity>();
            else if (identity.sourceId != field.sourceId || identity.nativeId != field.nativeId ||
                     identity.sourceSortOrder != field.sortOrder || identity.enabledInSource != field.enabled || identity.enabled)
                throw new InvalidOperationException("STATIC_SORT_IDENTITY_EXISTING_SORTORDER_DIFFERS: " + field.sourceId);
            identity.sourceId = field.sourceId; identity.nativeId = field.nativeId;
            identity.sourceSortOrder = field.sortOrder; identity.enabledInSource = field.enabled;
            identity.enabled = false;
        }
        foreach (var field in sortRoots.Values)
        {
            var node = nodes[field.node];
            var identity = node.GetComponent<NativeStaticSortRootIdentity>();
            if (identity == null) identity = node.AddComponent<NativeStaticSortRootIdentity>();
            else if (identity.sourceId != field.sourceId || identity.nativeId != field.nativeId ||
                     identity.enabledInSource != field.enabled || identity.enabled)
                throw new InvalidOperationException("STATIC_SORT_IDENTITY_EXISTING_SORTROOT_DIFFERS: " + field.sourceId);
            identity.sourceId = field.sourceId; identity.nativeId = field.nativeId;
            identity.enabledInSource = field.enabled; identity.enabled = false;
        }
    }

    static Dictionary<string, GameObject> StaticSortSourceNodes(SourcePrefabSpec prefab,
        IDictionary<string, GameObject> available)
    {
        var nodes = new Dictionary<string, GameObject>(StringComparer.Ordinal);
        foreach (var id in prefab.nodes ?? Array.Empty<string>())
        {
            if (String.IsNullOrWhiteSpace(id) || !available.TryGetValue(id, out var node) || node == null)
                throw new InvalidOperationException("STATIC_SORT_SOURCE_NODE_MISSING: " + id);
            if (!nodes.TryAdd(id, node)) throw new InvalidOperationException("STATIC_SORT_SOURCE_NODE_DUPLICATE: " + id);
        }
        return nodes;
    }

    static Dictionary<string, Sprite> StaticSortSpriteReferences(Plan plan, ProxyQueueSpec[] queues)
    {
        var frameIds = (queues ?? Array.Empty<ProxyQueueSpec>())
            .SelectMany(queue => queue.masks ?? Array.Empty<ProxyMaskSpec>())
            .Where(mask => mask.maskType == 2)
            .Select(mask => mask.spriteFrameUuid)
            .Concat((queues ?? Array.Empty<ProxyQueueSpec>()).SelectMany(queue =>
                queue.sourceMaskIdentities ?? Array.Empty<ProxySourceMaskIdentitySpec>())
                .Where(mask => mask.maskType == 2).Select(mask => mask.spriteFrameUuid))
            .Distinct(StringComparer.Ordinal).ToArray();
        var result = new Dictionary<string, Sprite>(StringComparer.Ordinal);
        foreach (var frameId in frameIds)
        {
            if (String.IsNullOrWhiteSpace(frameId))
                throw new InvalidOperationException("STATIC_SORT_MASK_SPRITE_FRAME_ID_MISSING");
            var matches = (plan.textures ?? Array.Empty<TextureSpec>())
                .Where(texture => texture != null && !String.IsNullOrWhiteSpace(texture.id) &&
                    texture.id.EndsWith(":" + frameId, StringComparison.Ordinal)).ToArray();
            if (matches.Length != 1)
                throw new InvalidOperationException("STATIC_SORT_MASK_SPRITE_FRAME_IDENTITY_AMBIGUOUS: " + frameId);
            var texture = matches[0];
            var sprite = AssetDatabase.LoadAssetAtPath<Sprite>(texture.path);
            if (sprite == null || AssetDatabase.GetAssetPath(sprite) != texture.path)
                throw new InvalidOperationException("STATIC_SORT_MASK_SPRITE_FRAME_NATIVE_REFERENCE_MISSING: " + frameId);
            long localId;
            var guid = AssetDatabase.TryGetGUIDAndLocalFileIdentifier(sprite, out var spriteGuid, out localId) ? spriteGuid : null;
            if (String.IsNullOrWhiteSpace(guid) || AssetDatabase.AssetPathToGUID(texture.path) != guid)
                throw new InvalidOperationException("STATIC_SORT_MASK_SPRITE_FRAME_PERSISTENT_IDENTITY_INVALID: " + frameId);
            result.Add(texture.id, sprite);
        }
        return result;
    }

    static ProxyQueueReadback[] CreateStaticSortForPrefab(Plan plan, SourcePrefabSpec prefab,
        IDictionary<string, GameObject> sourceNodes)
    {
        var queues = StaticSortQueuesForPrefab(plan, prefab);
        var scopedNodes = StaticSortSourceNodes(prefab, sourceNodes);
        var sprites = StaticSortSpriteReferences(plan, queues);
        var results = new List<ProxyQueueReadback>();
        foreach (var queue in queues)
        {
            var sourceRoot = scopedNodes[queue.rootScope];
            var existing = sourceRoot.GetComponentsInChildren<NativeStaticSortQueueProxyMarker>(true)
                .Where(marker => marker != null && marker.kind == "root" && marker.sourceNode == queue.rootScope &&
                    marker.sourceRootOwner == sourceRoot && UnityStaticSortQueueProxy.IsGeneratedSortProxyRoot(marker.transform))
                .ToArray();
            if (existing.Length > 1)
                throw new InvalidOperationException("STATIC_SORT_PROXY_ROOT_DUPLICATE: " + queue.rootScope);
            if (existing.Length == 1)
            {
                var presenter = existing[0].GetComponent<NativeStaticSortQueueProxyPresenter>();
                if (presenter == null || presenter.sourceRoot != sourceRoot || presenter.proxyRoot != existing[0].gameObject ||
                    presenter.sourceRootId != queue.rootScope || presenter.sourcePrefabId != prefab.sourceId ||
                    presenter.prefabPath != prefab.path)
                    throw new InvalidOperationException("STATIC_SORT_PROXY_EXISTING_TEMPLATE_ROOT_IDENTITY_MISMATCH: " + queue.rootScope);
                // A nested source Prefab may already carry its own proxy. Reuse
                // that serialized tree; CreateStaticSortQueueProxy forbids a
                // second root on the same owner.
                continue;
            }
            var result = UnityStaticSortQueueProxy.CreateStaticSortQueueProxy(queue, scopedNodes,
                id => ResolveStaticMaskSprite(id, plan, sprites), CreateStaticMaskMaterial);
            if (result == null || !result.provisional || result.verified || result.readbackMode != "pre-save-provisional")
                throw new InvalidOperationException("STATIC_SORT_PROXY_CREATE_RETURNED_NONPROVISIONAL_RESULT: " + queue.rootScope);
            results.Add(result);
        }
        return results.ToArray();
    }

    static NativeStaticSortQueueProxyMarker[] StaticSortProxyRoots(ProxyQueueSpec queue,
        IDictionary<string, GameObject> sourceNodes)
    {
        if (!sourceNodes.TryGetValue(queue.rootScope, out var sourceRoot) || sourceRoot == null)
            return Array.Empty<NativeStaticSortQueueProxyMarker>();
        return sourceRoot.GetComponentsInChildren<NativeStaticSortQueueProxyMarker>(true)
            .Where(marker => marker != null && marker.kind == "root" && marker.sourceNode == queue.rootScope &&
                marker.sourceRootOwner == sourceRoot && UnityStaticSortQueueProxy.IsGeneratedSortProxyRoot(marker.transform))
            .ToArray();
    }

    static StaticSortPrefabReadback ReadStaticSortForPrefab(Plan plan, SourcePrefabSpec prefab,
        IDictionary<string, GameObject> persistentMap, IDictionary<string, GameObject> loadedMap)
    {
        var queues = StaticSortQueuesForPrefab(plan, prefab);
        var persistentNodes = StaticSortSourceNodes(prefab, persistentMap);
        var loadedNodes = StaticSortSourceNodes(prefab, loadedMap);
        var sprites = StaticSortSpriteReferences(plan, queues);
        var persistentRows = new List<ProxyQueueReadback>();
        var loadedRows = new List<ProxyQueueReadback>();
        var diagnostics = new List<string>();
        foreach (var queue in queues)
        {
            var persistentRoots = StaticSortProxyRoots(queue, persistentNodes);
            var loadedRoots = StaticSortProxyRoots(queue, loadedNodes);
            if (persistentRoots.Length != 1 || loadedRoots.Length != 1)
            {
                diagnostics.Add("STATIC_SORT_PROXY_PERSISTED_ROOT_COUNT_MISMATCH:" + queue.rootScope);
                continue;
            }
            var persistentPresenter = persistentRoots[0].GetComponent<NativeStaticSortQueueProxyPresenter>();
            var loadedPresenter = loadedRoots[0].GetComponent<NativeStaticSortQueueProxyPresenter>();
            if (persistentPresenter == null || loadedPresenter == null)
            {
                diagnostics.Add("STATIC_SORT_PROXY_PRESENTER_MISSING:" + queue.rootScope);
                continue;
            }
            var resolver = new Func<string, Sprite>(id => ResolveStaticMaskSprite(id, plan, sprites));
            var materialResolver = new Func<MaskSpec, Material>(ResolveStaticSortMaskMaterialReadOnly);
            var scopeProvenance = new ProxyPrefabScopeProvenance { sourcePrefabId = prefab.sourceId,
                prefabPath = prefab.path, rootScope = queue.rootScope,
                persistentAssetRoot = persistentNodes[queue.rootScope],
                loadedScopeRoot = loadedNodes[queue.rootScope] };
            var persistent = UnityStaticSortQueueProxy.ReadPersistentSortQueueProxy(queue, persistentNodes,
                persistentRoots[0].gameObject, persistentPresenter, resolver, materialResolver, scopeProvenance);
            var loaded = UnityStaticSortQueueProxy.ReadStaticSortQueueProxy(queue, loadedNodes,
                loadedRoots[0].gameObject, loadedPresenter, resolver, materialResolver, scopeProvenance);
            persistentRows.Add(persistent);
            loadedRows.Add(loaded);
            if (persistent == null || !persistent.verified)
                diagnostics.Add("STATIC_SORT_PROXY_PERSISTENT_READBACK_FAILED:" + queue.rootScope + ":" +
                    (persistent == null ? "null" : persistent.diagnostic ?? "unverified"));
            if (loaded == null || !loaded.verified)
                diagnostics.Add("STATIC_SORT_PROXY_INITIALIZED_READBACK_FAILED:" + queue.rootScope + ":" +
                    (loaded == null ? "null" : loaded.diagnostic ?? "unverified"));
        }
        bool passed = diagnostics.Count == 0 && persistentRows.Count == queues.Length && loadedRows.Count == queues.Length &&
            persistentRows.All(row => row != null && row.verified && row.persistentSnapshotVerified) &&
            loadedRows.All(row => row != null && row.verified && row.initializedPresentationVerified);
        return new StaticSortPrefabReadback { sourcePrefabId = prefab.sourceId, prefabPath = prefab.path,
            persistentAsset = persistentRows.ToArray(), loadedInstance = loadedRows.ToArray(),
            diagnostics = diagnostics.ToArray(), verified = passed };
    }
}
