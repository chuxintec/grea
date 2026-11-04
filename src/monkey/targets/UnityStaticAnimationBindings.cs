using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;

// Editor-only resolver for static animation references. It reuses already saved
// AnimationClip assets, disables any Animator, and never creates a controller,
// calls Play/Sample, or advances time.
public static class UnityStaticAnimationBindings
{
    [Serializable]
    public sealed class Spec
    {
        public string schema;
        public string sourceComponentId;
        public string targetComponentId;
        public string sourceNodeId;
        public string targetNodeId;
        public bool sourceEnabled;
        public bool sourceEnabledKnown;
        public bool sourcePlayOnLoad;
        public bool sourcePlayOnLoadKnown;
        public string sourceDefaultClipId;
        public bool sourceDefaultClipKnown;
        public bool hasSourceDefaultClip;
        public string defaultClipReferenceStatus;
        public string[] sourceClipOrder;
        public ClipSpec[] clips;
        public bool nativePlaybackEnabled;
        public bool nativeAnimatorEnabled;
        public string status;
    }

    [Serializable]
    public sealed class ClipSpec
    {
        public int order;
        public string sourceClipId;
        public string planAnimationId;
        public string status;
        public string nativeClipPath;
        public string nativeClipGuid;
        public string assetSha256;
        public string metaSha256;
        public string nativeName;
        public bool nativeNameMatchesPlan;
        public bool convertible;
        public string nativeClipReadbackStatus;
        public string nativeClipContentStatus;
        public string sourceEvidencePath;
        public string sourceEvidenceGuid;
        public string sourceEvidenceSha256;
    }

    [Serializable]
    public sealed class ClipReadback
    {
        public int order;
        public string sourceClipId;
        public string planAnimationId;
        public string status;
        public string nativeClipPath;
        public string nativeClipGuid;
        public bool referenceMatches;
        public bool nativeNameMatchesPlan;
        public string contentReadbackStatus;
        public string assetHashStatus;
        public string metaHashStatus;
        public string sourceEvidencePath;
        public string sourceEvidenceGuid;
        public string sourceEvidenceHashStatus;
        public string bindingObjectType;
    }

    [Serializable]
    public sealed class Readback
    {
        public string status;
        public string sourceComponentId;
        public string targetComponentId;
        public string sourceNodeId;
        public string targetNodeId;
        public bool sourceEnabled;
        public bool sourceEnabledKnown;
        public bool sourcePlayOnLoad;
        public bool sourcePlayOnLoadKnown;
        public string sourceDefaultClipId;
        public bool sourceDefaultClipKnown;
        public string[] sourceClipOrder;
        public bool hasSourceDefaultClip;
        public bool animatorPresent;
        public bool animatorDisabled;
        public bool markerDisabled;
        public string defaultClipReferenceStatus;
        public ClipReadback[] clips;
        public bool playbackExecuted;
        public string[] diagnostics;
    }

    public static Readback Attach(GameObject target, Spec spec, bool verifyPersistedIdentity = true)
    {
        ValidateTarget(target, spec);
        var animator = target.GetComponent<Animator>();
        if (animator == null) animator = target.AddComponent<Animator>();
        animator.enabled = false;

        var marker = target.GetComponent<NativeStaticAnimationBinding>();
        if (marker == null) marker = target.AddComponent<NativeStaticAnimationBinding>();
        var slots = (spec.clips ?? Array.Empty<ClipSpec>()).OrderBy(row => row.order).Select(row => {
            if (row == null) throw new InvalidOperationException("STATIC_ANIMATION_CLIP_ROW_NULL");
            AnimationClip clip = null;
            string resolvedPath = null;
            string resolvedGuid = null;
            TextAsset sourceEvidence = null;
            string evidencePath = null;
            string evidenceGuid = null;
            string status = row.status;
            if (row.status == "native_clip_reference_resolved") {
                clip = ResolveClip(row, verifyPersistedIdentity);
                resolvedPath = row.nativeClipPath;
                resolvedGuid = row.nativeClipGuid;
            }
            if (!string.IsNullOrWhiteSpace(row.sourceEvidencePath)) {
                sourceEvidence = ResolveSourceEvidence(row, verifyPersistedIdentity);
                evidencePath = row.sourceEvidencePath;
                evidenceGuid = row.sourceEvidenceGuid;
            }
            if (clip == null && sourceEvidence == null)
                throw new InvalidOperationException("STATIC_ANIMATION_SLOT_HAS_NO_REAL_ASSET_REFERENCE: " + row.sourceClipId);
            return new NativeStaticAnimationBinding.ClipSlot {
                order = row.order,
                sourceClipId = row.sourceClipId,
                planAnimationId = row.planAnimationId,
                nativeClipPath = resolvedPath,
                nativeClipGuid = resolvedGuid,
                nativeClipSha256 = row.assetSha256,
                status = status,
                nativeClip = clip,
                sourceEvidencePath = evidencePath,
                sourceEvidenceGuid = evidenceGuid,
                sourceEvidenceSha256 = row.sourceEvidenceSha256,
                sourceEvidenceAsset = sourceEvidence,
            };
        }).ToArray();
        AnimationClip defaultClip = null;
        if (spec.hasSourceDefaultClip) {
            var defaultSlot = slots.FirstOrDefault(row => row.sourceClipId == spec.sourceDefaultClipId);
            if (defaultSlot != null) defaultClip = defaultSlot.nativeClip;
        }
        marker.Configure(spec.sourceComponentId, spec.sourceNodeId, spec.sourceDefaultClipId,
            spec.hasSourceDefaultClip, spec.sourceEnabled, spec.sourceEnabledKnown,
            spec.sourcePlayOnLoad, spec.sourcePlayOnLoadKnown, spec.sourceDefaultClipKnown,
            spec.sourceClipOrder, defaultClip, slots);
        marker.enabled = false;
        EditorUtility.SetDirty(animator);
        EditorUtility.SetDirty(marker);
        PrefabUtility.RecordPrefabInstancePropertyModifications(animator);
        PrefabUtility.RecordPrefabInstancePropertyModifications(marker);
        return verifyPersistedIdentity ? Read(target, spec) : ReadAttached(target, spec);
    }

    static Readback ReadAttached(GameObject target, Spec spec)
    {
        var animator = target.GetComponent<Animator>();
        var marker = target.GetComponent<NativeStaticAnimationBinding>();
        if (animator == null || marker == null)return Failure(spec, "STATIC_ANIMATION_NATIVE_COMPONENT_MISSING");
        var expected = (spec.clips ?? Array.Empty<ClipSpec>()).OrderBy(row => row.order).ToArray();
        var actual = marker.SourceClips.OrderBy(row => row.order).ToArray();
        bool matches = !animator.enabled && !marker.enabled
            && marker.SourceComponentId == spec.sourceComponentId
            && marker.SourceNodeId == spec.sourceNodeId
            && marker.SourceEnabled == spec.sourceEnabled
            && marker.SourceEnabledKnown == spec.sourceEnabledKnown
            && marker.SourcePlayOnLoad == spec.sourcePlayOnLoad
            && marker.SourcePlayOnLoadKnown == spec.sourcePlayOnLoadKnown
            && marker.SourceDefaultClipKnown == spec.sourceDefaultClipKnown
            && marker.HasSourceDefaultClip == spec.hasSourceDefaultClip
            && marker.SourceDefaultClipId == spec.sourceDefaultClipId
            && marker.SourceClipOrder.SequenceEqual(spec.sourceClipOrder ?? Array.Empty<string>(), StringComparer.Ordinal)
            && expected.Length == actual.Length;
        for (int i = 0; i < expected.Length && i < actual.Length; i++) {
            var row = expected[i]; var saved = actual[i];
            var expectedClip = row.status == "native_clip_reference_resolved" ? ResolveClip(row, false) : null;
            var expectedEvidence = !string.IsNullOrWhiteSpace(row.sourceEvidencePath) ? ResolveSourceEvidence(row, false) : null;
            matches &= saved.order == row.order && saved.sourceClipId == row.sourceClipId
                && saved.planAnimationId == row.planAnimationId
                && saved.nativeClip == expectedClip && saved.sourceEvidenceAsset == expectedEvidence
                && (expectedClip != null || expectedEvidence != null);
        }
        var expectedDefault = spec.hasSourceDefaultClip && spec.defaultClipReferenceStatus == "resolved"
            ? actual.FirstOrDefault(row => row.sourceClipId == spec.sourceDefaultClipId)?.nativeClip : null;
        matches &= marker.SourceDefaultClip == expectedDefault;
        return new Readback {
            status = matches ? "attached_pending_save" : "mismatch",
            sourceComponentId = marker.SourceComponentId, targetComponentId = spec.targetComponentId,
            sourceNodeId = marker.SourceNodeId, targetNodeId = spec.targetNodeId,
            sourceEnabled = marker.SourceEnabled, sourceEnabledKnown = marker.SourceEnabledKnown,
            sourcePlayOnLoad = marker.SourcePlayOnLoad, sourcePlayOnLoadKnown = marker.SourcePlayOnLoadKnown,
            sourceDefaultClipId = marker.SourceDefaultClipId, sourceDefaultClipKnown = marker.SourceDefaultClipKnown,
            sourceClipOrder = marker.SourceClipOrder, hasSourceDefaultClip = marker.HasSourceDefaultClip,
            animatorPresent = true, animatorDisabled = !animator.enabled, markerDisabled = !marker.enabled,
            defaultClipReferenceStatus = spec.defaultClipReferenceStatus,
            playbackExecuted = false,
            diagnostics = matches ? Array.Empty<string>() : new[] { "In-memory animation references or disabled state differ before save." },
        };
    }

    // Read is intentionally non-mutating. The caller invokes it after save/reopen
    // to verify that serialized source fields and exact AnimationClip references survived.
    public static Readback Read(GameObject target, Spec spec)
    {
        ValidateTarget(target, spec);
        var animator = target.GetComponent<Animator>();
        var marker = target.GetComponent<NativeStaticAnimationBinding>();
        if (animator == null || marker == null)
            return Failure(spec, "STATIC_ANIMATION_NATIVE_COMPONENT_MISSING");
        var actualSlots = marker.SourceClips;
        var expected = (spec.clips ?? Array.Empty<ClipSpec>()).OrderBy(row => row.order).ToArray();
        var actual = actualSlots.OrderBy(row => row.order).ToArray();
        bool fieldsMatch = marker.SourceComponentId == spec.sourceComponentId
            && marker.SourceNodeId == spec.sourceNodeId
            && marker.SourceEnabled == spec.sourceEnabled
            && marker.SourceEnabledKnown == spec.sourceEnabledKnown
            && marker.SourcePlayOnLoad == spec.sourcePlayOnLoad
            && marker.SourcePlayOnLoadKnown == spec.sourcePlayOnLoadKnown
            && marker.SourceDefaultClipKnown == spec.sourceDefaultClipKnown
            && marker.HasSourceDefaultClip == spec.hasSourceDefaultClip
            && marker.SourceDefaultClipId == spec.sourceDefaultClipId
            && marker.SourceClipOrder.SequenceEqual(spec.sourceClipOrder ?? Array.Empty<string>(), StringComparer.Ordinal)
            && expected.Length == actual.Length
            && actual.Select(row => row.sourceClipId).SequenceEqual(expected.Select(row => row.sourceClipId), StringComparer.Ordinal)
            && actual.Select(row => row.order).SequenceEqual(expected.Select(row => row.order));
        var clipReadbacks = new ClipReadback[expected.Length];
        bool clipsMatch = expected.Length == actual.Length;
        for (int i = 0; i < expected.Length; i++) {
            var row = expected[i];
            var saved = i < actual.Length ? actual[i] : null;
            bool shouldHaveAsset = row.status == "native_clip_reference_resolved";
            bool shouldHaveEvidence = !string.IsNullOrWhiteSpace(row.sourceEvidencePath);
            string path = saved == null || saved.nativeClip == null ? null : AssetDatabase.GetAssetPath(saved.nativeClip);
            string guid = string.IsNullOrEmpty(path) ? null : AssetDatabase.AssetPathToGUID(path);
            string assetHashStatus = shouldHaveAsset && !string.IsNullOrEmpty(path)
                ? Hash(Path.GetFullPath(Path.Combine(Directory.GetParent(Application.dataPath).FullName, path))) == row.assetSha256
                    ? "verified" : "mismatch"
                : "not_applicable";
            string metaHashStatus = shouldHaveAsset && !string.IsNullOrEmpty(path) && !string.IsNullOrEmpty(row.metaSha256)
                ? Hash(Path.GetFullPath(Path.Combine(Directory.GetParent(Application.dataPath).FullName, path)) + ".meta") == row.metaSha256
                    ? "verified" : "mismatch"
                : "not_applicable";
            string evidencePath = saved == null || saved.sourceEvidenceAsset == null ? null : AssetDatabase.GetAssetPath(saved.sourceEvidenceAsset);
            string evidenceGuid = string.IsNullOrEmpty(evidencePath) ? null : AssetDatabase.AssetPathToGUID(evidencePath);
            string evidenceHashStatus = shouldHaveEvidence && !string.IsNullOrEmpty(evidencePath)
                ? Hash(Path.GetFullPath(Path.Combine(Directory.GetParent(Application.dataPath).FullName, evidencePath))) == row.sourceEvidenceSha256
                    ? "verified" : "mismatch"
                : "not_applicable";
            bool matches = saved != null && saved.order == row.order && saved.sourceClipId == row.sourceClipId
                && saved.planAnimationId == row.planAnimationId && saved.status == row.status
                && (shouldHaveAsset
                    ? saved.nativeClip != null && path == row.nativeClipPath && guid == row.nativeClipGuid
                        && saved.nativeClipPath == row.nativeClipPath && saved.nativeClipGuid == row.nativeClipGuid
                        && saved.nativeClipSha256 == row.assetSha256
                        && saved.nativeClip.name == row.nativeName && assetHashStatus == "verified"
                        && (string.IsNullOrEmpty(row.metaSha256) || metaHashStatus == "verified")
                    : saved.nativeClip == null)
                && (shouldHaveEvidence
                    ? saved.sourceEvidenceAsset != null && evidencePath == row.sourceEvidencePath
                        && evidenceGuid == row.sourceEvidenceGuid
                        && saved.sourceEvidencePath == row.sourceEvidencePath
                        && saved.sourceEvidenceGuid == row.sourceEvidenceGuid
                        && saved.sourceEvidenceSha256 == row.sourceEvidenceSha256
                        && evidenceHashStatus == "verified"
                    : saved.sourceEvidenceAsset == null);
            clipsMatch &= matches;
            clipReadbacks[i] = new ClipReadback {
                order = row.order,
                sourceClipId = row.sourceClipId,
                planAnimationId = row.planAnimationId,
                status = saved == null ? "missing_slot" : saved.status,
                nativeClipPath = path,
                nativeClipGuid = guid,
                referenceMatches = matches,
                nativeNameMatchesPlan = row.nativeNameMatchesPlan,
                contentReadbackStatus = row.nativeClipContentStatus ?? "not_run",
                assetHashStatus = assetHashStatus,
                metaHashStatus = metaHashStatus,
                sourceEvidencePath = evidencePath,
                sourceEvidenceGuid = evidenceGuid,
                sourceEvidenceHashStatus = evidenceHashStatus,
                bindingObjectType = saved != null && saved.nativeClip != null ? "AnimationClip" : "TextAsset",
            };
        }
        bool defaultMatches = !spec.hasSourceDefaultClip || spec.defaultClipReferenceStatus != "resolved"
            ? marker.SourceDefaultClip == null
            : marker.SourceDefaultClip != null
                && AssetDatabase.GetAssetPath(marker.SourceDefaultClip) == expected
                    .Where(row => row.sourceClipId == spec.sourceDefaultClipId)
                    .Select(row => row.nativeClipPath).FirstOrDefault();
        bool good = fieldsMatch && clipsMatch && defaultMatches && !animator.enabled && !marker.enabled
            && !spec.nativeAnimatorEnabled && !spec.nativePlaybackEnabled;
        return new Readback {
            status = good ? (spec.status == "resolved" ? "reference_fields_verified" : "partial") : "mismatch",
            sourceComponentId = marker.SourceComponentId,
            targetComponentId = spec.targetComponentId,
            sourceNodeId = marker.SourceNodeId,
            targetNodeId = spec.targetNodeId,
            sourceEnabled = marker.SourceEnabled,
            sourceEnabledKnown = marker.SourceEnabledKnown,
            sourcePlayOnLoad = marker.SourcePlayOnLoad,
            sourcePlayOnLoadKnown = marker.SourcePlayOnLoadKnown,
            sourceDefaultClipId = marker.SourceDefaultClipId,
            sourceDefaultClipKnown = marker.SourceDefaultClipKnown,
            sourceClipOrder = marker.SourceClipOrder,
            hasSourceDefaultClip = marker.HasSourceDefaultClip,
            animatorPresent = true,
            animatorDisabled = !animator.enabled,
            markerDisabled = !marker.enabled,
            defaultClipReferenceStatus = spec.defaultClipReferenceStatus,
            clips = clipReadbacks,
            playbackExecuted = false,
            diagnostics = good ? Array.Empty<string>() : new[] { "Serialized animation references or disabled state do not match the supplied source binding." },
        };
    }

    static AnimationClip ResolveClip(ClipSpec spec, bool verifyPersistedIdentity = true)
    {
        if (string.IsNullOrWhiteSpace(spec.nativeClipPath) || !spec.nativeClipPath.StartsWith("Assets/", StringComparison.Ordinal)
            || spec.nativeClipPath.Contains("..") || (verifyPersistedIdentity
                && (string.IsNullOrWhiteSpace(spec.nativeClipGuid) || string.IsNullOrWhiteSpace(spec.assetSha256))))
            throw new InvalidOperationException("STATIC_ANIMATION_CLIP_IDENTITY_INCOMPLETE: " + spec.sourceClipId);
        var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(spec.nativeClipPath);
        if (clip == null || (verifyPersistedIdentity && (AssetDatabase.AssetPathToGUID(spec.nativeClipPath) != spec.nativeClipGuid
            || clip.name != spec.nativeName)))
            throw new InvalidOperationException("STATIC_ANIMATION_CLIP_ASSET_IDENTITY_MISMATCH: " + spec.nativeClipPath);
        if (!verifyPersistedIdentity)return clip;
        var projectRoot = Directory.GetParent(Application.dataPath).FullName;
        var assetAbsolutePath = Path.GetFullPath(Path.Combine(projectRoot, spec.nativeClipPath));
        var actualHash = Hash(assetAbsolutePath);
        if (actualHash != spec.assetSha256)
            throw new InvalidOperationException("STATIC_ANIMATION_CLIP_ASSET_HASH_MISMATCH: " + spec.nativeClipPath);
        if (!string.IsNullOrWhiteSpace(spec.metaSha256)) {
            var actualMetaHash = Hash(assetAbsolutePath + ".meta");
            if (actualMetaHash != spec.metaSha256)
                throw new InvalidOperationException("STATIC_ANIMATION_CLIP_META_HASH_MISMATCH: " + spec.nativeClipPath);
        }
        return clip;
    }

    static TextAsset ResolveSourceEvidence(ClipSpec spec, bool verifyPersistedIdentity = true)
    {
        if (string.IsNullOrWhiteSpace(spec.sourceEvidencePath)
            || !spec.sourceEvidencePath.StartsWith("Assets/", StringComparison.Ordinal)
            || spec.sourceEvidencePath.Contains("..")
            || (verifyPersistedIdentity && (string.IsNullOrWhiteSpace(spec.sourceEvidenceGuid)
                || string.IsNullOrWhiteSpace(spec.sourceEvidenceSha256))))
            throw new InvalidOperationException("STATIC_ANIMATION_SOURCE_EVIDENCE_IDENTITY_INCOMPLETE: " + spec.sourceClipId);
        var asset = AssetDatabase.LoadAssetAtPath<TextAsset>(spec.sourceEvidencePath);
        if (asset == null || (verifyPersistedIdentity && AssetDatabase.AssetPathToGUID(spec.sourceEvidencePath) != spec.sourceEvidenceGuid))
            throw new InvalidOperationException("STATIC_ANIMATION_SOURCE_EVIDENCE_IDENTITY_MISMATCH: " + spec.sourceEvidencePath);
        if (!verifyPersistedIdentity)return asset;
        var root = Directory.GetParent(Application.dataPath).FullName;
        var absolute = Path.GetFullPath(Path.Combine(root, spec.sourceEvidencePath));
        if (Hash(absolute) != spec.sourceEvidenceSha256)
            throw new InvalidOperationException("STATIC_ANIMATION_SOURCE_EVIDENCE_HASH_MISMATCH: " + spec.sourceEvidencePath);
        return asset;
    }

    static void ValidateTarget(GameObject target, Spec spec)
    {
        if (target == null || spec == null || spec.schema != "monkey-static-animation-bindings/1"
            || string.IsNullOrWhiteSpace(spec.sourceComponentId) || string.IsNullOrWhiteSpace(spec.targetNodeId))
            throw new InvalidOperationException("STATIC_ANIMATION_BINDING_INPUT_INVALID");
    }

    static Readback Failure(Spec spec, string message)
    {
        return new Readback {
            status = "partial",
            sourceComponentId = spec.sourceComponentId,
            targetComponentId = spec.targetComponentId,
            sourceNodeId = spec.sourceNodeId,
            targetNodeId = spec.targetNodeId,
            playbackExecuted = false,
            diagnostics = new[] { message },
        };
    }

    static string Hash(string assetPath)
    {
        using (var algorithm = SHA256.Create())
        using (var stream = File.OpenRead(assetPath))
            return BitConverter.ToString(algorithm.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }
}
