using System;
using UnityEngine;

// Serialized source-animation identity and native clip references for static
// previews. This marker intentionally has no playback/update behavior.
[DisallowMultipleComponent]
public sealed class NativeStaticAnimationBinding : MonoBehaviour
{
    [Serializable]
    public sealed class ClipSlot
    {
        public int order;
        public string sourceClipId;
        public string planAnimationId;
        public string nativeClipPath;
        public string nativeClipGuid;
        public string nativeClipSha256;
        public string status;
        public AnimationClip nativeClip;
        public string sourceEvidencePath;
        public string sourceEvidenceGuid;
        public string sourceEvidenceSha256;
        public TextAsset sourceEvidenceAsset;
    }

    [SerializeField] string sourceComponentId;
    [SerializeField] string sourceNodeId;
    [SerializeField] string sourceDefaultClipId;
    [SerializeField] bool sourceDefaultClipKnown;
    [SerializeField] bool hasSourceDefaultClip;
    [SerializeField] bool sourceEnabled;
    [SerializeField] bool sourceEnabledKnown;
    [SerializeField] bool sourcePlayOnLoad;
    [SerializeField] bool sourcePlayOnLoadKnown;
    [SerializeField] AnimationClip sourceDefaultClip;
    [SerializeField] string[] sourceClipOrder = Array.Empty<string>();
    [SerializeField] ClipSlot[] sourceClips = Array.Empty<ClipSlot>();

    public string SourceComponentId { get { return sourceComponentId; } }
    public string SourceNodeId { get { return sourceNodeId; } }
    public string SourceDefaultClipId { get { return sourceDefaultClipId; } }
    public bool SourceDefaultClipKnown { get { return sourceDefaultClipKnown; } }
    public bool HasSourceDefaultClip { get { return hasSourceDefaultClip; } }
    public bool SourceEnabled { get { return sourceEnabled; } }
    public bool SourceEnabledKnown { get { return sourceEnabledKnown; } }
    public bool SourcePlayOnLoad { get { return sourcePlayOnLoad; } }
    public bool SourcePlayOnLoadKnown { get { return sourcePlayOnLoadKnown; } }
    public AnimationClip SourceDefaultClip { get { return sourceDefaultClip; } }
    public string[] SourceClipOrder { get { return sourceClipOrder ?? Array.Empty<string>(); } }
    public ClipSlot[] SourceClips { get { return sourceClips ?? Array.Empty<ClipSlot>(); } }

    public void Configure(string componentId, string nodeId, string defaultClipId, bool hasDefaultClip,
        bool enabledValue, bool enabledKnown, bool playOnLoadValue, bool playOnLoadKnown,
        bool defaultClipKnown, string[] clipOrder, AnimationClip defaultClip, ClipSlot[] clips)
    {
        sourceComponentId = componentId;
        sourceNodeId = nodeId;
        sourceDefaultClipId = defaultClipId;
        sourceDefaultClipKnown = defaultClipKnown;
        hasSourceDefaultClip = hasDefaultClip;
        sourceEnabled = enabledValue;
        sourceEnabledKnown = enabledKnown;
        sourcePlayOnLoad = playOnLoadValue;
        sourcePlayOnLoadKnown = playOnLoadKnown;
        sourceDefaultClip = defaultClip;
        sourceClipOrder = clipOrder ?? Array.Empty<string>();
        sourceClips = clips ?? Array.Empty<ClipSlot>();
    }
}
