using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;

namespace Monkey.StaticSortQueue
{
    [Serializable] public sealed class QueueRendererSpec
    {
        public string node, sourceComponentId, sourceType, expectedGraphicType;
        public int nativeSortingOrder;
        public float sourceSortOrder;
        public string kind;
    }
    [Serializable] public sealed class QueueSortFieldSpec
    {
        public string sourceId, nativeId, node;
        public float sortOrder;
        public bool enabled;
    }
    [Serializable] public sealed class QueueDrawEventSpec
    {
        public string kind, node, sourceComponentId;
    }
    [Serializable] public sealed class QueueMaskScopeSpec
    {
        public string node;
        public int maskType;
        public bool inverted, convertible;
    }
    [Serializable] public sealed class QueuePrefabSpec
    {
        public string rootScope;
        public bool unityQueueMapped;
        public string unityMode, maskDiagnostic;
        public QueueRendererSpec[] renderers;
        public QueueSortFieldSpec[] sourceFields;
        public string[] maskNodeIds;
        public QueueDrawEventSpec[] sourceDrawEvents;
        public QueueMaskScopeSpec[] maskScopes;
        public Dictionary<string, bool> sourceNodeActive;
        public Dictionary<string, string[]> sourceChildOrder;
    }
    [Serializable] public sealed class QueueRendererReadback
    {
        public string node, sourceComponentId, sourceType, nativeGraphicType, rendererGuid, identityGuid, diagnostic;
        public int nativeSortingOrder, nativeSortingLayerId;
        public string canvasGuid;
        public long canvasFileId, rendererFileId, identityFileId;
        public bool overrideSorting, persistent, verified;
    }
    [Serializable] public sealed class QueueFieldReadback
    {
        public string sourceId, node, nativeId, carrierGuid;
        public long carrierFileId;
        public float sourceSortOrder;
        public bool enabled, persistent, verified;
    }
    [Serializable] public sealed class QueueMaskReadback
    {
        public string node, nativeType;
        public int sourceMaskType;
        public bool inverted, enabled, verified;
    }
    [Serializable] public sealed class QueueSourceSortIdentity : MonoBehaviour
    {
        public string sourceId, nativeId;
        public float sourceSortOrder;
        public bool enabledInSource;
    }
    [Serializable] public sealed class QueueReadback
    {
        public string rootScope;
        public bool sourceTreePreserved, nativeQueueMapped, verified;
        public string diagnostic;
        public QueueRendererReadback[] renderers;
        public QueueFieldReadback[] sourceFields;
        public QueueMaskReadback[] masks;
    }
    [Serializable] public sealed class QueueInactiveSpineReadback
    {
        public int schemaVersion = 1;
        public string contract = "monkey-static-spine-inactive-source-flow/1";
        public string sourcePrefabId, sourceManifestSha256, sourcePrefabRootNodeId,
            sourceComponentId, node, inactiveSourceAncestorId, rendererListDisposition,
            persistentOwnerType, loadedOwnerType, diagnostic;
        public string[] sourceActivityPath;
        public bool[] sourceActivityValues;
        public bool applicable, verified, sourceComponentEnabled, sourceEffectiveActive,
            sourceActivityVerified, controlledHostVerified, persistentIdentityVerified, loadedIdentityVerified,
            persistentEnabledVerified, loadedEnabledVerified, persistentOwnerActiveSelf, loadedOwnerActiveSelf,
            loadedOwnerActiveInHierarchy, runtimeRendererListRequired;
    }

    [AddComponentMenu("")]
    public sealed class NativeStaticSortQueueIdentity : MonoBehaviour
    {
        public string sourceId, sourceComponentId, sourceType;
        public float sourceSortOrder;
        public int nativeSortingOrder, sourceCanvasSortingLayerId;
    }

    /// <summary>
    /// Ensures generated TMP submesh renderers remain grouped under their
    /// source Label's Canvas and never acquire an independent sort identity.
    /// </summary>
    [AddComponentMenu("")]
    public sealed class NativeStaticSortQueueCanvasScope : MonoBehaviour
    {
        public string sourceNodeId;
        public int expectedSortingOrder;
        public bool lastGeneratedChildrenValid = true;

        void OnTransformChildrenChanged() { ValidateChildren(); }
        public bool ValidateChildren()
        {
            var canvas = GetComponent<Canvas>();
            if (canvas == null || !canvas.overrideSorting || canvas.sortingOrder != expectedSortingOrder)
                return lastGeneratedChildrenValid = false;
            foreach (Transform child in transform)
            {
                var isTmpSubmesh = child.GetComponents<Component>().Any(c => c != null &&
                    c.GetType().FullName != null && c.GetType().FullName.Contains("TMP_SubMeshUI"));
                var nestedCanvas = child.GetComponent<Canvas>();
                if (isTmpSubmesh && nestedCanvas != null && nestedCanvas.overrideSorting)
                    return lastGeneratedChildrenValid = false;
            }
            return lastGeneratedChildrenValid = true;
        }
    }

    public static class UnityStaticSortQueue
    {
        const string SpineGraphicType = "Spine.Unity.SkeletonGraphic";
        const string SpineIdentityType = "UnitySpineSourceIdentity";
        const BindingFlags SpineIdentityFieldFlags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

        /// <summary>
        /// Proves that an exact SkeletonGraphic owner is outside the source
        /// render flow because its serialized node or an ancestor is inactive.
        /// This is an explicit inactive-source classification; it does not
        /// claim that the SDK CanvasRenderer list is empty or readable.
        /// </summary>
        public static QueueInactiveSpineReadback ReadInactiveSpineNoRender(string sourceComponentId,
            string nodeId, string sourcePrefabRootNodeId, bool sourceComponentEnabled,
            string[] sourceNodePath, IDictionary<string, bool> sourceNodeActive,
            IDictionary<string, GameObject> persistentNodes, IDictionary<string, GameObject> loadedNodes,
            GameObject controlledHost)
        {
            var result = new QueueInactiveSpineReadback
            {
                sourceComponentId = sourceComponentId,
                node = nodeId,
                sourceComponentEnabled = sourceComponentEnabled,
                runtimeRendererListRequired = false,
                rendererListDisposition = "not-required-source-inactive-subtree",
                sourceActivityPath = Array.Empty<string>(),
            };
            if (String.IsNullOrWhiteSpace(sourcePrefabRootNodeId) || String.IsNullOrWhiteSpace(sourceComponentId) ||
                String.IsNullOrWhiteSpace(nodeId) || sourceNodePath == null || sourceNodeActive == null ||
                persistentNodes == null || loadedNodes == null || controlledHost == null)
            {
                result.diagnostic = "inactive-spine-proof-input-missing";
                return result;
            }

            if (sourceNodePath.Length == 0 || sourceNodePath[0] != nodeId ||
                sourceNodePath[sourceNodePath.Length - 1] != sourcePrefabRootNodeId ||
                sourceNodePath.Any(String.IsNullOrWhiteSpace) || sourceNodePath.Distinct(StringComparer.Ordinal).Count() != sourceNodePath.Length)
            {
                result.diagnostic = "inactive-spine-source-activity-path-invalid";
                return result;
            }
            result.sourceActivityPath = sourceNodePath.ToArray();
            result.sourceActivityValues = sourceNodePath.Select(id => sourceNodeActive.TryGetValue(id, out var active) && active).ToArray();
            result.sourceEffectiveActive = true;
            foreach (var id in sourceNodePath)
            {
                if (!sourceNodeActive.TryGetValue(id, out var expectedSelf))
                {
                    result.diagnostic = "inactive-spine-source-path-activity-missing:" + id;
                    return result;
                }
                result.sourceEffectiveActive &= expectedSelf;
            }
            if (result.sourceEffectiveActive)
            {
                result.applicable = false;
                result.diagnostic = "inactive-spine-proof-not-applicable-to-active-source-owner";
                return result;
            }
            result.applicable = true;
            result.inactiveSourceAncestorId = sourceNodePath.First(id => !sourceNodeActive[id]);

            for (int i = 0; i < sourceNodePath.Length; i++)
            {
                var id = sourceNodePath[i];
                if (!persistentNodes.TryGetValue(id, out var persistentNode) || persistentNode == null ||
                    !loadedNodes.TryGetValue(id, out var loadedNode) || loadedNode == null)
                {
                    result.diagnostic = "inactive-spine-source-path-node-missing:" + id;
                    return result;
                }
                var expectedSelf = sourceNodeActive[id];
                if (persistentNode.activeSelf != expectedSelf || loadedNode.activeSelf != expectedSelf)
                {
                    result.diagnostic = "inactive-spine-source-node-activity-changed:" + id;
                    return result;
                }
            }
            for (int i = 0; i + 1 < sourceNodePath.Length; i++)
            {
                if (persistentNodes[sourceNodePath[i]].transform.parent != persistentNodes[sourceNodePath[i + 1]].transform ||
                    loadedNodes[sourceNodePath[i]].transform.parent != loadedNodes[sourceNodePath[i + 1]].transform)
                {
                    result.sourceActivityVerified = false;
                    result.diagnostic = "inactive-spine-source-path-parent-mismatch:" + sourceNodePath[i];
                    return result;
                }
            }
            var persistentOwner = ExactSpineGraphic(persistentNodes[nodeId]);
            var loadedOwner = ExactSpineGraphic(loadedNodes[nodeId]);
            if (persistentOwner == null || loadedOwner == null)
            {
                result.diagnostic = "inactive-spine-source-path-renderer-missing:" + nodeId;
                return result;
            }
            var persistentBehaviour = persistentOwner as Behaviour;
            var loadedBehaviour = loadedOwner as Behaviour;
            result.persistentOwnerActiveSelf = persistentOwner.gameObject.activeSelf;
            result.loadedOwnerActiveSelf = loadedOwner.gameObject.activeSelf;
            result.persistentOwnerType = persistentOwner.GetType().FullName;
            result.loadedOwnerType = loadedOwner.GetType().FullName;
            result.loadedOwnerActiveInHierarchy = loadedOwner.gameObject.activeInHierarchy;
            result.controlledHostVerified = controlledHost.activeInHierarchy &&
                loadedNodes[sourcePrefabRootNodeId].transform.IsChildOf(controlledHost.transform) &&
                loadedOwner.gameObject.activeInHierarchy == false;
            result.persistentEnabledVerified = persistentBehaviour != null && persistentBehaviour.enabled == sourceComponentEnabled;
            result.loadedEnabledVerified = loadedBehaviour != null && loadedBehaviour.enabled == sourceComponentEnabled;
            result.persistentIdentityVerified = HasExactSpineIdentity(persistentOwner, sourceComponentId);
            result.loadedIdentityVerified = HasExactSpineIdentity(loadedOwner, sourceComponentId);
            result.sourceActivityVerified = true;
            // The effective inactive path may be an ancestor, so owner.activeSelf
            // may remain true. Bind its serialized value to source evidence above;
            // only effective loaded activity is required to be false.
            result.verified = result.sourceActivityVerified && !result.sourceEffectiveActive &&
                result.controlledHostVerified && result.persistentEnabledVerified && result.loadedEnabledVerified &&
                result.persistentIdentityVerified && result.loadedIdentityVerified &&
                result.persistentOwnerActiveSelf == sourceNodeActive[nodeId] &&
                result.loadedOwnerActiveSelf == sourceNodeActive[nodeId];
            result.diagnostic = result.verified ? null : "inactive-spine-render-flow-boundary-unverified";
            return result;
        }

        static Component ExactSpineGraphic(GameObject node)
        {
            var matches = node == null ? Array.Empty<Component>() : node.GetComponents<Component>()
                .Where(component => component != null && component.GetType().FullName == SpineGraphicType).ToArray();
            return matches.Length == 1 ? matches[0] : null;
        }

        static bool HasExactSpineIdentity(Component owner, string sourceComponentId)
        {
            if (owner == null || owner.GetType().FullName != SpineGraphicType) return false;
            var matches = owner.GetComponents<Component>().Where(component => component != null &&
                component.GetType().FullName == SpineIdentityType).ToArray();
            if (matches.Length != 1) return false;
            var type = matches[0].GetType();
            var sourceIdField = type.GetField("instanceSourceComponentId", SpineIdentityFieldFlags);
            var rendererField = type.GetField("renderer", SpineIdentityFieldFlags);
            return sourceIdField != null && rendererField != null &&
                sourceIdField.GetValue(matches[0]) as string == sourceComponentId &&
                rendererField.GetValue(matches[0]) as Component == owner;
        }

        static string PrefabGuid(UnityEngine.Object value, out long localFileId)
        {
            string guid;
            return AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value, out guid, out localFileId) ? guid : null;
        }

        static bool IsTmpSubmesh(GameObject value) => value.GetComponents<Component>().Any(c => c != null &&
            c.GetType().FullName != null && c.GetType().FullName.Contains("TMP_SubMeshUI"));

        public static bool SourceTreeMatches(QueuePrefabSpec spec, IDictionary<string, GameObject> nodes)
        {
            foreach (var pair in spec.sourceChildOrder ?? new Dictionary<string, string[]>())
            {
                if (!nodes.TryGetValue(pair.Key, out var parent) || parent == null) return false;
                var observed = new List<string>();
                foreach (Transform child in parent.transform)
                {
                    var sourceChild = nodes.FirstOrDefault(entry => entry.Value != null && entry.Value.transform == child).Key;
                    if (sourceChild != null) observed.Add(sourceChild);
                    else if (!IsTmpSubmesh(child.gameObject)) return false;
                }
                if (!observed.SequenceEqual(pair.Value ?? Array.Empty<string>())) return false;
            }
            return true;
        }

        static bool NativeDfsMatchesSource(QueuePrefabSpec spec, IDictionary<string, GameObject> nodes)
        {
            var masks = (spec.maskScopes ?? Array.Empty<QueueMaskScopeSpec>()).ToDictionary(row => row.node);
            var renderers = (spec.renderers ?? Array.Empty<QueueRendererSpec>()).ToDictionary(row => row.node);
            var observed = new List<QueueDrawEventSpec>();
            bool Visit(string nodeId, bool parentActive)
            {
                if (!nodes.TryGetValue(nodeId, out var go) || go == null || !spec.sourceNodeActive.TryGetValue(nodeId, out var sourceActive)) return false;
                if (go.activeSelf != sourceActive) return false;
                var active = parentActive && go.activeSelf;
                if (!active) return true;
                if (masks.TryGetValue(nodeId, out var maskSpec))
                {
                    var mask = go.GetComponent<Mask>(); var rect = go.GetComponent<RectMask2D>();
                    var rectExpected = maskSpec.convertible && maskSpec.maskType == 0 && !maskSpec.inverted;
                    if (rectExpected ? rect == null || !rect.enabled || mask != null : mask == null || !mask.enabled || rect != null)
                        return false;
                    foreach (var child in spec.sourceChildOrder[nodeId]) if (!Visit(child, active)) return false;
                    return true;
                }
                if (renderers.TryGetValue(nodeId, out var row))
                {
                    var graphic = go.GetComponent<Graphic>();
                    if (graphic == null || !graphic.enabled || graphic.GetType().FullName != row.expectedGraphicType) return false;
                    observed.Add(new QueueDrawEventSpec { kind = "renderer", node = nodeId, sourceComponentId = row.sourceComponentId });
                }
                foreach (var child in spec.sourceChildOrder[nodeId]) if (!Visit(child, active)) return false;
                return true;
            }
            if (!Visit(spec.rootScope, true)) return false;
            var expected = spec.sourceDrawEvents ?? Array.Empty<QueueDrawEventSpec>();
            return observed.Count == expected.Length && observed.Zip(expected, (a, b) =>
                a.kind == b.kind && a.node == b.node && a.sourceComponentId == b.sourceComponentId).All(equal => equal);
        }

        static bool HasMaskInterference(GameObject node, ISet<string> sourceMaskNodes,
            IDictionary<string, GameObject> nodes)
        {
            for (var t = node.transform; t != null; t = t.parent)
            {
                if (t.GetComponent<Mask>() != null || t.GetComponent<RectMask2D>() != null) return true;
                if (sourceMaskNodes.Any(id => nodes.TryGetValue(id, out var maskNode) && maskNode != null && maskNode.transform == t)) return true;
            }
            return false;
        }

        public static QueueReadback CreateStaticSortQueue(QueuePrefabSpec spec,
            IDictionary<string, GameObject> nodes)
        {
            if (spec == null || nodes == null) throw new InvalidOperationException("STATIC_SORT_QUEUE_PLAN_INVALID");
            if (!spec.unityQueueMapped)
                return FailureReadback(spec, nodes, spec.maskDiagnostic ?? "UNITY_NESTED_CANVAS_BREAKS_MASK_STENCIL_BLOCK");
            if (!SourceTreeMatches(spec, nodes))
                return FailureReadback(spec, nodes, "STATIC_SORT_SOURCE_TREE_IDENTITY_MISMATCH");
            if (spec.unityMode == "source-fixed-tree" && !NativeDfsMatchesSource(spec, nodes))
                return FailureReadback(spec, nodes, "STATIC_SORT_SOURCE_FIXED_DRAW_SEQUENCE_MISMATCH");
            var maskNodes = new HashSet<string>(spec.maskNodeIds ?? Array.Empty<string>());
            var prepared = new List<(QueueRendererSpec spec, GameObject node, Graphic graphic, Canvas parentCanvas)>();
            foreach (var row in spec.unityMode == "canvas-rank" ? spec.renderers ?? Array.Empty<QueueRendererSpec>() : Array.Empty<QueueRendererSpec>())
            {
                if (row.nativeSortingOrder < short.MinValue || row.nativeSortingOrder > short.MaxValue)
                    return FailureReadback(spec, nodes, "STATIC_SORT_CANVAS_INT16_ORDER_OVERFLOW");
                if (!nodes.TryGetValue(row.node, out var node) || node == null)
                    return FailureReadback(spec, nodes, "STATIC_SORT_RENDER_NODE_MISSING: " + row.node);
                if (HasMaskInterference(node, maskNodes, nodes))
                    return FailureReadback(spec, nodes, "UNITY_NESTED_CANVAS_BREAKS_MASK_STENCIL_BLOCK: " + row.node);
                var graphics = node.GetComponents<Graphic>();
                if (graphics.Length != 1 || graphics[0] == null)
                    return FailureReadback(spec, nodes, "STATIC_SORT_GRAPHIC_COUNT_UNSUPPORTED: " + row.node);
                if (string.IsNullOrEmpty(row.expectedGraphicType) || graphics[0].GetType().FullName != row.expectedGraphicType)
                    return FailureReadback(spec, nodes, "STATIC_SORT_GRAPHIC_NATIVE_TYPE_MISMATCH: " + row.node);
                var parentCanvas = node.GetComponentInParent<Canvas>();
                if (parentCanvas == null)
                    return FailureReadback(spec, nodes, "STATIC_SORT_PARENT_CANVAS_MISSING: " + row.node);
                if (node.GetComponent<Canvas>() != null || node.GetComponent<NativeStaticSortQueueIdentity>() != null)
                    return FailureReadback(spec, nodes, "STATIC_SORT_CANVAS_OR_IDENTITY_ALREADY_EXISTS: " + row.node);
                prepared.Add((row, node, graphics[0], parentCanvas));
            }
            foreach (var field in spec.sourceFields ?? Array.Empty<QueueSortFieldSpec>())
                if (!nodes.TryGetValue(field.node, out var node) || node == null || node.GetComponent<QueueSourceSortIdentity>() != null)
                    return FailureReadback(spec, nodes, "STATIC_SORT_SOURCE_FIELD_IDENTITY_INVALID: " + field.sourceId);

            foreach (var item in prepared)
            {
                var canvas = item.node.AddComponent<Canvas>();
                canvas.overrideSorting = true;
                canvas.sortingLayerID = item.parentCanvas.sortingLayerID;
                canvas.sortingOrder = item.spec.nativeSortingOrder;
                var identity = item.node.AddComponent<NativeStaticSortQueueIdentity>();
                identity.sourceId = item.spec.node;
                identity.sourceComponentId = item.spec.sourceComponentId;
                identity.sourceType = item.spec.sourceType;
                identity.sourceSortOrder = item.spec.sourceSortOrder;
                identity.nativeSortingOrder = item.spec.nativeSortingOrder;
                identity.sourceCanvasSortingLayerId = item.parentCanvas.sortingLayerID;
                var scope = item.node.AddComponent<NativeStaticSortQueueCanvasScope>();
                scope.sourceNodeId = item.spec.node; scope.expectedSortingOrder = item.spec.nativeSortingOrder;
            }
            foreach (var field in spec.sourceFields ?? Array.Empty<QueueSortFieldSpec>())
            {
                var identity = nodes[field.node].AddComponent<QueueSourceSortIdentity>();
                identity.sourceId = field.sourceId; identity.nativeId = field.nativeId;
                identity.sourceSortOrder = field.sortOrder; identity.enabledInSource = field.enabled;
            }
            return ReadStaticSortQueue(spec, nodes);
        }

        public static QueueReadback ReadStaticSortQueue(QueuePrefabSpec spec,
            IDictionary<string, GameObject> nodes)
        {
            if (spec == null || !nodes.TryGetValue(spec.rootScope, out var root) || root == null)
                return FailureReadback(spec, nodes, "STATIC_SORT_ROOT_MISSING");
            var treeOK = SourceTreeMatches(spec, nodes);
            var rows = (spec.renderers ?? Array.Empty<QueueRendererSpec>()).Select(row => {
                var node = nodes.TryGetValue(row.node, out var value) ? value : null;
                var canvas = node == null ? null : node.GetComponent<Canvas>();
                var identity = node == null ? null : node.GetComponent<NativeStaticSortQueueIdentity>();
                var scope = node == null ? null : node.GetComponent<NativeStaticSortQueueCanvasScope>();
                var graphic = node == null ? null : node.GetComponent<Graphic>();
                long local = 0; var guid = canvas == null ? null : PrefabGuid(canvas, out local);
                long rendererLocal = 0; var rendererGuid = graphic == null ? null : PrefabGuid(graphic, out rendererLocal);
                long identityLocal = 0; var identityGuid = identity == null ? null : PrefabGuid(identity, out identityLocal);
                var fixedMode = spec.unityMode == "source-fixed-tree";
                var persistent = graphic != null && rendererGuid != null &&
                    (fixedMode || canvas != null && guid != null && identity != null && identityGuid != null);
                var canvasOK = fixedMode || (canvas != null && canvas.overrideSorting && canvas.sortingOrder == row.nativeSortingOrder &&
                    identity != null && canvas.sortingLayerID == identity.sourceCanvasSortingLayerId &&
                    identity.sourceId == row.node && identity.sourceComponentId == row.sourceComponentId &&
                    identity.sourceType == row.sourceType && identity.sourceSortOrder == row.sourceSortOrder &&
                    identity.nativeSortingOrder == row.nativeSortingOrder && scope != null && scope.ValidateChildren() &&
                    graphic != null && graphic.GetType().FullName == row.expectedGraphicType);
                var valid = treeOK && canvasOK && graphic != null && graphic.GetType().FullName == row.expectedGraphicType &&
                    (!fixedMode || NativeDfsMatchesSource(spec, nodes)) && persistent;
                return new QueueRendererReadback { node = row.node, sourceComponentId = row.sourceComponentId,
                    sourceType = row.sourceType, nativeGraphicType = graphic == null ? null : graphic.GetType().FullName,
                    rendererGuid = rendererGuid, rendererFileId = rendererLocal,
                    identityGuid = identityGuid, identityFileId = identityLocal,
                    nativeSortingOrder = canvas == null ? int.MinValue : canvas.sortingOrder,
                    nativeSortingLayerId = canvas == null ? 0 : canvas.sortingLayerID, overrideSorting = canvas != null && canvas.overrideSorting,
                    canvasGuid = guid, canvasFileId = local, persistent = persistent, verified = valid,
                    diagnostic = valid ? null : "UNITY_SORT_CANVAS_NATIVE_OR_PERSISTENT_IDENTITY_MISMATCH" };
            }).ToArray();
            var fields = (spec.sourceFields ?? Array.Empty<QueueSortFieldSpec>()).Select(field => {
                var identity = nodes.TryGetValue(field.node, out var node) && node != null ? node.GetComponent<QueueSourceSortIdentity>() : null;
                long carrierLocal = 0; var carrierGuid = identity == null ? null : PrefabGuid(identity, out carrierLocal);
                return new QueueFieldReadback { sourceId = field.sourceId, node = field.node,
                    nativeId = identity == null ? null : identity.nativeId,
                    carrierGuid = carrierGuid, carrierFileId = carrierLocal,
                    persistent = identity != null && carrierGuid != null,
                    sourceSortOrder = identity == null ? float.NaN : identity.sourceSortOrder,
                    enabled = identity != null && identity.enabledInSource,
                    verified = identity != null && carrierGuid != null && identity.sourceId == field.sourceId && identity.nativeId == field.nativeId &&
                        identity.sourceSortOrder == field.sortOrder && identity.enabledInSource == field.enabled };
            }).ToArray();
            var masks = (spec.maskScopes ?? Array.Empty<QueueMaskScopeSpec>()).Select(maskSpec => {
                var node = nodes.TryGetValue(maskSpec.node, out var value) ? value : null;
                var mask = node == null ? null : node.GetComponent<Mask>();
                var rect = node == null ? null : node.GetComponent<RectMask2D>();
                var rectExpected = maskSpec.convertible && maskSpec.maskType == 0 && !maskSpec.inverted;
                var verified = rectExpected ? rect != null && rect.enabled && mask == null : mask != null && mask.enabled && rect == null;
                return new QueueMaskReadback { node = maskSpec.node,
                    nativeType = rectExpected ? rect == null ? null : rect.GetType().FullName : mask == null ? null : mask.GetType().FullName,
                    sourceMaskType = maskSpec.maskType, inverted = maskSpec.inverted,
                    enabled = rectExpected ? rect != null && rect.enabled : mask != null && mask.enabled, verified = verified };
            }).ToArray();
            var passed = spec.unityQueueMapped && treeOK && rows.All(row => row.verified) &&
                fields.All(row => row.verified) && masks.All(row => row.verified);
            return new QueueReadback { rootScope = spec.rootScope, sourceTreePreserved = treeOK,
                nativeQueueMapped = spec.unityQueueMapped, verified = passed,
                diagnostic = passed ? null : spec.unityQueueMapped ? "STATIC_SORT_NATIVE_READBACK_FAILED" : "UNITY_NESTED_CANVAS_BREAKS_MASK_STENCIL_BLOCK",
                renderers = rows, sourceFields = fields, masks = masks };
        }

        static QueueReadback FailureReadback(QueuePrefabSpec spec, IDictionary<string, GameObject> nodes, string diagnostic)
        {
            return new QueueReadback { rootScope = spec == null ? null : spec.rootScope,
                sourceTreePreserved = spec != null && nodes != null && SourceTreeMatches(spec, nodes),
                nativeQueueMapped = false, verified = false, diagnostic = diagnostic,
                renderers = (spec == null ? Array.Empty<QueueRendererSpec>() : spec.renderers ?? Array.Empty<QueueRendererSpec>())
                    .Select(row => new QueueRendererReadback { node = row.node, sourceComponentId = row.sourceComponentId,
                        sourceType = row.sourceType, nativeSortingOrder = row.nativeSortingOrder,
                        diagnostic = diagnostic, verified = false }).ToArray(),
                sourceFields = Array.Empty<QueueFieldReadback>(), masks = Array.Empty<QueueMaskReadback>() };
        }
    }
}
