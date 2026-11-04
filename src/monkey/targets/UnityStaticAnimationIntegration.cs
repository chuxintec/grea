// Candidate-time bridge between source cc.Animation records and real Unity assets.
// Source identities stay in Editor readback data; playback remains disabled.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static partial class MonkeyImporter
{
    [Serializable] public sealed class StaticAnimationEvidenceSpec {
        public string sourceClipId, path, sha256;
    }
    [Serializable] public sealed class StaticAnimationComponentOrigin {
        public string instanceSourceId, templateSourceId;
    }
    [Serializable] public sealed class StaticAnimationReadback {
        public string sourceComponentId, targetComponentId, targetNodeId, status, curveCompleteness;
        public bool playbackExecuted;
        public UnityStaticAnimationBindings.Readback binding;
    }
    [Serializable] public sealed class StaticAnimationFieldReference {
        public string sourceComponentId, fieldName, sourceClipId, path, guid, objectType, status;
        public bool persistent;
    }

    public static StaticAnimationReadback[] AttachStaticAnimationBindings(
        Plan plan, Dictionary<string,GameObject> nodes, MotionResult[] motionResults,
        StaticAnimationEvidenceSpec[] evidenceSpecs, StaticAnimationComponentOrigin[] componentOrigins)
    {
        var evidence = ResolveStaticAnimationEvidence(evidenceSpecs);
        var motions = motionResults ?? Array.Empty<MotionResult>();
        var origins = componentOrigins ?? Array.Empty<StaticAnimationComponentOrigin>();
        var results = new List<StaticAnimationReadback>();
        foreach (var source in (plan.components ?? Array.Empty<ComponentSpec>()).Where(row => row.type == "cc.Animation")) {
            if (!nodes.TryGetValue(source.node, out var node) || node == null)
                throw new InvalidOperationException("STATIC_ANIMATION_TARGET_NODE_MISSING: " + source.sourceId);
            var slots = new List<UnityStaticAnimationBindings.ClipSpec>();
            var clipOrder = source.clips ?? Array.Empty<string>();
            for (var index = 0; index < clipOrder.Length; index++) {
                var sourceClipId = clipOrder[index];
                var motion = ResolveBoundMotion(sourceClipId, source.sourceId, motions, origins);
                var evidenceAsset = evidence.TryGetValue(sourceClipId, out var sourceText) ? sourceText : null;
                if (motion == null && evidenceAsset == null)
                    throw new InvalidOperationException("STATIC_ANIMATION_SLOT_HAS_NO_REAL_ASSET_REFERENCE: " + sourceClipId);
                slots.Add(ToClipSpec(index, sourceClipId, motion, evidenceAsset));
            }
            var hasDefault = !string.IsNullOrEmpty(source.defaultClip);
            var defaultResolved = slots.Any(row => row.sourceClipId == source.defaultClip && row.status == "native_clip_reference_resolved");
            var spec = new UnityStaticAnimationBindings.Spec {
                schema = "monkey-static-animation-bindings/1",
                sourceComponentId = source.sourceId,
                targetComponentId = source.sourceId,
                sourceNodeId = source.node,
                targetNodeId = source.node,
                sourceEnabled = source.enabled,
                sourceEnabledKnown = true,
                sourcePlayOnLoad = source.playOnLoad,
                sourcePlayOnLoadKnown = true,
                sourceDefaultClipId = source.defaultClip??string.Empty,
                sourceDefaultClipKnown = source.defaultClipKnown,
                hasSourceDefaultClip = hasDefault,
                defaultClipReferenceStatus = !hasDefault ? "no_source_default" : defaultResolved ? "resolved" : "source_default_reference_retained",
                sourceClipOrder = clipOrder,
                clips = slots.ToArray(),
                nativePlaybackEnabled = false,
                nativeAnimatorEnabled = false,
                status = slots.All(row => row.status == "native_clip_reference_resolved" || !string.IsNullOrEmpty(row.sourceEvidencePath))
                    ? "resolved" : "partial",
            };
            var read = UnityStaticAnimationBindings.Attach(node, spec, false);
            results.Add(new StaticAnimationReadback {
                sourceComponentId = source.sourceId,
                targetComponentId = source.sourceId,
                targetNodeId = source.node,
                status = read.status,
                curveCompleteness = slots.All(row => row.convertible) ? "complete" : "partial",
                playbackExecuted = false,
                binding = read,
            });
        }
        return results.ToArray();
    }

    public static StaticAnimationReadback[] ReadSavedStaticAnimationBindings(
        Plan plan, Dictionary<string,GameObject> savedNodes, MotionResult[] motionResults,
        StaticAnimationEvidenceSpec[] evidenceSpecs, StaticAnimationComponentOrigin[] componentOrigins)
    {
        var evidence = ResolveStaticAnimationEvidence(evidenceSpecs);
        var motions = motionResults ?? Array.Empty<MotionResult>();
        var origins = componentOrigins ?? Array.Empty<StaticAnimationComponentOrigin>();
        var results = new List<StaticAnimationReadback>();
        foreach (var source in (plan.components ?? Array.Empty<ComponentSpec>()).Where(row => row.type == "cc.Animation" && savedNodes.ContainsKey(row.node))) {
            var node = savedNodes[source.node];
            var slots = (source.clips ?? Array.Empty<string>()).Select((clipId, index) => {
                var motion = ResolveBoundMotion(clipId, source.sourceId, motions, origins);
                var text = evidence.TryGetValue(clipId, out var found) ? found : null;
                if (motion == null && text == null)throw new InvalidOperationException("STATIC_ANIMATION_SLOT_HAS_NO_REAL_ASSET_REFERENCE: " + clipId);
                return ToClipSpec(index, clipId, motion, text);
            }).ToArray();
            var hasDefault = !string.IsNullOrEmpty(source.defaultClip);
            var spec = new UnityStaticAnimationBindings.Spec {
                schema = "monkey-static-animation-bindings/1", sourceComponentId = source.sourceId,
                targetComponentId = source.sourceId, sourceNodeId = source.node, targetNodeId = source.node,
                sourceEnabled = source.enabled, sourceEnabledKnown = true,
                sourcePlayOnLoad = source.playOnLoad, sourcePlayOnLoadKnown = true,
                sourceDefaultClipId = source.defaultClip??string.Empty, sourceDefaultClipKnown = source.defaultClipKnown,
                hasSourceDefaultClip = hasDefault,
                defaultClipReferenceStatus = !hasDefault ? "no_source_default" : slots.Any(row => row.sourceClipId == source.defaultClip && row.status == "native_clip_reference_resolved")
                    ? "resolved" : "source_default_reference_retained",
                sourceClipOrder = source.clips ?? Array.Empty<string>(), clips = slots,
                nativePlaybackEnabled = false, nativeAnimatorEnabled = false,
                status = "resolved",
            };
            var read = UnityStaticAnimationBindings.Read(node, spec);
            if (read.status == "mismatch")throw new InvalidOperationException("STATIC_ANIMATION_SAVED_READBACK_FAILED: " + source.sourceId);
            results.Add(new StaticAnimationReadback {
                sourceComponentId = source.sourceId, targetComponentId = source.sourceId, targetNodeId = source.node, status = read.status,
                curveCompleteness = slots.All(row => row.convertible) ? "complete" : "partial",
                playbackExecuted = read.playbackExecuted, binding = read,
            });
        }
        return results.ToArray();
    }

    public static StaticAnimationFieldReference[] ReadStaticAnimationFieldReferences(
        Plan plan, Dictionary<string,GameObject> nodes, IReadOnlyDictionary<string,AnimationClip> sourceClipAssets,
        StaticFieldResult[] savedStaticFields)
    {
        var savedByComponent = (savedStaticFields ?? Array.Empty<StaticFieldResult>())
            .Where(row => row != null && row.binding != null)
            .GroupBy(row => row.binding.sourceId).ToDictionary(group => group.Key, group => group.ToArray());
        var result = new List<StaticAnimationFieldReference>();
        foreach (var component in plan.components ?? Array.Empty<ComponentSpec>()) {
            var binding = component.staticFieldBinding;
            if (binding == null)continue;
            foreach (var field in binding.fields ?? Array.Empty<UnityStaticFields.FieldSpec>()) {
                if (field.sourceDeclaredType != "cc.AnimationClip" || field.nullExpected)continue;
                var ids = new List<string>();
                if (!string.IsNullOrEmpty(field.refValue))ids.Add(field.refValue);
                ids.AddRange(field.refValues ?? Array.Empty<string>());
                for (var index = 0; index < ids.Count; index++) {
                    var id = ids[index];
                    var clip = sourceClipAssets.TryGetValue(id, out var found) ? found : null;
                    string path = clip == null ? null : AssetDatabase.GetAssetPath(clip);
                    string guid = string.IsNullOrEmpty(path) ? null : AssetDatabase.AssetPathToGUID(path);
                    var persisted = savedByComponent.TryGetValue(component.sourceId, out var candidates) && candidates.Length == 1
                        ? candidates[0].references ?? Array.Empty<StaticReferenceIdentity>() : Array.Empty<StaticReferenceIdentity>();
                    var actual = persisted.Where(reference => reference.field == field.sourceFieldName
                        && reference.sourceId == id && reference.recordIndex == -1).ToArray();
                    bool exact = clip != null && EditorUtility.IsPersistent(clip) && !string.IsNullOrEmpty(guid)
                        && actual.Length == 1 && actual[0].persistent && actual[0].guid == guid;
                    result.Add(new StaticAnimationFieldReference {
                        sourceComponentId = component.sourceId, fieldName = field.sourceFieldName,
                        sourceClipId = id, path = path, guid = guid,
                        objectType = clip == null ? null : "AnimationClip",
                        persistent = exact,
                        status = exact ? "resolved_native_animation_clip" : "unresolved_native_animation_clip",
                    });
                }
            }
        }
        return result.ToArray();
    }

    static Dictionary<string,TextAsset> ResolveStaticAnimationEvidence(StaticAnimationEvidenceSpec[] evidenceSpecs)
    {
        var result = new Dictionary<string,TextAsset>(StringComparer.Ordinal);
        foreach (var spec in evidenceSpecs ?? Array.Empty<StaticAnimationEvidenceSpec>()) {
            if (spec == null || string.IsNullOrWhiteSpace(spec.sourceClipId) || string.IsNullOrWhiteSpace(spec.path)
                || !spec.path.StartsWith("Assets/Game/Content/SourceEvidence/Animations/", StringComparison.Ordinal)
                || spec.path.Contains("..") || string.IsNullOrWhiteSpace(spec.sha256))
                throw new InvalidOperationException("STATIC_ANIMATION_EVIDENCE_SPEC_INVALID");
            var asset = AssetDatabase.LoadAssetAtPath<TextAsset>(spec.path);
            var absolute = Path.GetFullPath(Path.Combine(Directory.GetParent(Application.dataPath).FullName, spec.path));
            if (asset == null || Hash(absolute) != spec.sha256 || result.ContainsKey(spec.sourceClipId))
                throw new InvalidOperationException("STATIC_ANIMATION_EVIDENCE_ASSET_INVALID: " + spec.sourceClipId);
            result.Add(spec.sourceClipId, asset);
        }
        return result;
    }

    static MotionResult ResolveBoundMotion(string sourceClipId, string sourceComponentId,
        MotionResult[] motions, StaticAnimationComponentOrigin[] origins)
    {
        var exactId = sourceClipId + "@" + sourceComponentId;
        var exact = motions.Where(row => row.id == exactId).ToArray();
        if (exact.Length == 1)return exact[0];
        var templateIds = origins.Where(row => row.instanceSourceId == sourceComponentId).Select(row => row.templateSourceId).Distinct().ToArray();
        if (templateIds.Length > 1)throw new InvalidOperationException("STATIC_ANIMATION_COMPONENT_ORIGIN_AMBIGUOUS: " + sourceComponentId);
        if (templateIds.Length == 1) {
            var templateId = sourceClipId + "@" + templateIds[0];
            var template = motions.Where(row => row.id == templateId).ToArray();
            if (template.Length == 1)return template[0];
            if (template.Length > 1)throw new InvalidOperationException("STATIC_ANIMATION_TEMPLATE_MOTION_AMBIGUOUS: " + templateId);
        }
        return null;
    }

    static UnityStaticAnimationBindings.ClipSpec ToClipSpec(int order, string sourceClipId,
        MotionResult motion, TextAsset sourceEvidence)
    {
        var row = new UnityStaticAnimationBindings.ClipSpec {
            order = order, sourceClipId = sourceClipId,
            planAnimationId = motion != null ? motion.id : sourceClipId+"@retained-source-evidence",
            status = motion != null ? "native_clip_reference_resolved" : "source_evidence_retained",
            convertible = motion != null,
            nativeClipReadbackStatus = "not_run", nativeClipContentStatus = "not_run",
            nativeName = motion != null ? AssetDatabase.LoadAssetAtPath<AnimationClip>(motion.path)?.name : null,
            sourceEvidencePath = sourceEvidence != null ? AssetDatabase.GetAssetPath(sourceEvidence) : null,
            sourceEvidenceGuid = sourceEvidence != null ? AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(sourceEvidence)) : null,
        };
        if (motion != null) {
            row.nativeClipPath = motion.path; row.nativeClipGuid = motion.guid;
            row.assetSha256 = Hash(Path.GetFullPath(Path.Combine(Directory.GetParent(Application.dataPath).FullName, motion.path)));
            row.metaSha256 = Hash(Path.GetFullPath(Path.Combine(Directory.GetParent(Application.dataPath).FullName, motion.path)) + ".meta");
        }
        if (sourceEvidence != null) {
            row.sourceEvidenceSha256 = Hash(Path.GetFullPath(Path.Combine(Directory.GetParent(Application.dataPath).FullName, row.sourceEvidencePath)));
        }
        return row;
    }
}
