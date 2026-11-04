using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;

public static partial class MonkeyImporter
{
    [Serializable] public class StaticProgressSpec
    {
        public string policy, sourceComponentId, sourceNodeId, barSpriteSourceId;
        public string barNodeSourceId, sourceTemplateId;
        public string displayGeometryEvidence;
        public float progress, totalLength;
        public int mode;
        public bool reverse, sourceEnabled, carrierEnabled;
        public float[] sourceBarSize, sourceBarAnchor;
    }

    [Serializable] public class StaticProgressResult
    {
        public string sourceComponentId, sourceNodeId, barSpriteSourceId;
        public string carrierGuid, barSpriteGuid, barSpriteIdentity;
        public long carrierLocalFileId, barSpriteLocalFileId;
        public float progress, totalLength;
        public int mode;
        public bool reverse, sourceEnabled, carrierDisabled, barSpritePersistent, verified;
    }

    static ComponentSpec StaticProgressSource(Plan plan, string sourceId)
    {
        var rows = (plan.components ?? Array.Empty<ComponentSpec>()).Where(x => x.sourceId == sourceId).ToArray();
        if (rows.Length != 1) throw new InvalidOperationException("STATIC_PROGRESS_SOURCE_ID_NOT_UNIQUE: " + sourceId);
        return rows[0];
    }

    static UnityStaticProgress StaticProgressComponent(ComponentSpec component, GameObject node)
    {
        var binding = component.staticProgressBinding;
        if (binding == null) return null;
        var acceptedIds = new HashSet<string>(StringComparer.Ordinal) { binding.sourceComponentId };
        if (!String.IsNullOrEmpty(binding.sourceTemplateId)) acceptedIds.Add(binding.sourceTemplateId);
        var matches = node.GetComponents<UnityStaticProgress>()
            .Where(x => x != null && acceptedIds.Contains(x.SourceComponentId)).ToArray();
        if (matches.Length > 1) throw new InvalidOperationException("STATIC_PROGRESS_CARRIER_AMBIGUOUS: " + component.sourceId);
        return matches.SingleOrDefault();
    }

    // Resolves only exact plan source IDs. Sprite IDs return their mapped Image;
    // ProgressBar IDs return the corresponding typed static carrier.
    static UnityEngine.Object ResolveStaticProgress(Plan plan, Dictionary<string, GameObject> nodes, string sourceId)
    {
        if (String.IsNullOrEmpty(sourceId)) throw new InvalidOperationException("STATIC_PROGRESS_REFERENCE_ID_MISSING");
        var source = StaticProgressSource(plan, sourceId);
        if (!nodes.TryGetValue(source.node, out var node) || node == null)
            throw new InvalidOperationException("STATIC_PROGRESS_NODE_MAPPING_MISSING: " + sourceId);
        if (source.type == "cc.Sprite")
        {
            var images = node.GetComponents<Image>();
            if (images.Length != 1) throw new InvalidOperationException("STATIC_PROGRESS_SPRITE_MAPPING_NOT_UNIQUE: " + sourceId);
            if (!source.convertible) throw new InvalidOperationException("STATIC_PROGRESS_SPRITE_NOT_CONVERTIBLE: " + sourceId);
            return images[0];
        }
        if (source.type == "cc.ProgressBar")
        {
            if (source.staticProgressBinding != null && !source.convertible)
            {
                var carrier = StaticProgressComponent(source, node);
                if (carrier == null) throw new InvalidOperationException("STATIC_PROGRESS_CARRIER_MISSING: " + sourceId);
                return carrier;
            }
            if (source.convertible)
            {
                var drivers = node.GetComponents<NativeHorizontalProgressFill>();
                var matches = drivers.Where(x => x != null && x.Progress != null).ToArray();
                if (matches.Length != 1) throw new InvalidOperationException("STATIC_PROGRESS_LEGACY_MAPPING_NOT_UNIQUE: " + sourceId);
                var barSource = StaticProgressSource(plan, source.barNode);
                if (barSource.type != "cc.Sprite" || !nodes.TryGetValue(barSource.node, out var barNode) || barNode == null)
                    throw new InvalidOperationException("STATIC_PROGRESS_LEGACY_BAR_NODE_MAPPING_MISSING: " + sourceId);
                var images = barNode.GetComponents<Image>();
                if (images.Length != 1 || matches[0].Fill != images[0].rectTransform)
                    throw new InvalidOperationException("STATIC_PROGRESS_LEGACY_BAR_REFERENCE_DIFFERS: " + sourceId);
                return matches[0].Progress;
            }
            throw new InvalidOperationException("STATIC_PROGRESS_BINDING_MISSING: " + sourceId);
        }
        throw new InvalidOperationException("STATIC_PROGRESS_REFERENCE_TYPE_UNSUPPORTED: " + sourceId + ":" + source.type);
    }

    static IEnumerable<ComponentSpec> StaticProgressSources(Plan plan)
    {
        return (plan.components ?? Array.Empty<ComponentSpec>()).Where(c =>
            c.type == "cc.ProgressBar" && c.staticProgressBinding != null && !c.convertible);
    }

    static void CreateStaticProgress(Plan plan, Dictionary<string, GameObject> nodes)
    {
        foreach (var component in StaticProgressSources(plan))
        {
            var spec = component.staticProgressBinding;
            if (spec.policy != "native-static-progress-v1" || spec.sourceComponentId != component.sourceId ||
                spec.sourceNodeId != component.node || spec.carrierEnabled || Single.IsNaN(spec.progress) ||
                Single.IsInfinity(spec.progress) || Single.IsNaN(spec.totalLength) ||
                Single.IsInfinity(spec.totalLength) || spec.mode < 0 || spec.mode > 2)
                throw new InvalidOperationException("STATIC_PROGRESS_SPEC_INVALID: " + component.sourceId);
            if (!nodes.TryGetValue(component.node, out var node) || node == null)
                throw new InvalidOperationException("STATIC_PROGRESS_OWNER_NODE_MISSING: " + component.sourceId);
            var sprite = ResolveStaticProgress(plan, nodes, spec.barSpriteSourceId) as Image;
            if (sprite == null) throw new InvalidOperationException("STATIC_PROGRESS_SPRITE_TYPE_MISMATCH: " + component.sourceId);
            var carrier = StaticProgressComponent(component, node);
            if (carrier == null) carrier = node.AddComponent<UnityStaticProgress>();
            carrier.Configure(component.sourceId, component.node, sprite, spec.progress, spec.totalLength,
                spec.mode, spec.reverse, spec.sourceEnabled);
        }

    }

    static StaticProgressResult[] ReadStaticProgress(Plan plan, Dictionary<string, GameObject> nodes)
    {
        return StaticProgressSources(plan).Where(component=>nodes.ContainsKey(component.node)).Select(component =>
        {
            var spec = component.staticProgressBinding;
            if (!nodes.TryGetValue(component.node, out var node) || node == null)
                throw new InvalidOperationException("STATIC_PROGRESS_OWNER_NODE_MISSING: " + component.sourceId);
            var carrier = StaticProgressComponent(component, node);
            var expectedSprite = ResolveStaticProgress(plan, nodes, spec.barSpriteSourceId) as Image;
            if (carrier == null || expectedSprite == null || carrier.enabled || carrier.BarSprite != expectedSprite ||
                carrier.Progress != spec.progress || carrier.TotalLength != spec.totalLength || carrier.Mode != spec.mode ||
                carrier.Reverse != spec.reverse || carrier.SourceEnabled != spec.sourceEnabled)
                throw new InvalidOperationException("STATIC_PROGRESS_SAVED_FIELDS_OR_REFERENCE_DIFFER: " + component.sourceId);
            string carrierGuid, spriteGuid;
            long carrierId, spriteId;
            if (!EditorUtility.IsPersistent(carrier) || !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(carrier, out carrierGuid, out carrierId) || carrierId == 0)
                throw new InvalidOperationException("STATIC_PROGRESS_CARRIER_PERSISTENCE_IDENTITY_MISSING: " + component.sourceId);
            var persistentSprite = EditorUtility.IsPersistent(carrier.BarSprite);
            if (!persistentSprite || !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(carrier.BarSprite, out spriteGuid, out spriteId) || spriteId == 0)
                throw new InvalidOperationException("STATIC_PROGRESS_SPRITE_PERSISTENCE_IDENTITY_MISSING: " + component.sourceId);
            string expectedGuid; long expectedId;
            if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(expectedSprite, out expectedGuid, out expectedId) ||
                expectedGuid != spriteGuid || expectedId != spriteId)
                throw new InvalidOperationException("STATIC_PROGRESS_SPRITE_SOURCE_IDENTITY_DIFFERS: " + component.sourceId);
            return new StaticProgressResult
            {
                sourceComponentId = component.sourceId,
                sourceNodeId = component.node,
                barSpriteSourceId = spec.barSpriteSourceId,
                carrierGuid = carrierGuid,
                carrierLocalFileId = carrierId,
                barSpriteGuid = spriteGuid,
                barSpriteLocalFileId = spriteId,
                barSpriteIdentity = spriteGuid + "/" + spriteId.ToString(CultureInfo.InvariantCulture),
                progress = carrier.Progress,
                totalLength = carrier.TotalLength,
                mode = carrier.Mode,
                reverse = carrier.Reverse,
                sourceEnabled = carrier.SourceEnabled,
                carrierDisabled = !carrier.enabled,
                barSpritePersistent = persistentSprite,
                verified = true,
            };
        }).ToArray();
    }
}
