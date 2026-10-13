using System;
using Grea.Foundation.Contracts;
using UnityEngine;
using UnityEngine.Audio;

namespace Grea.Foundation.Runtime
{
    public sealed class AudioPlayer
    {
        readonly Transform owner;
        readonly AudioMixerGroup group;
        public AudioPlayer(Transform owner, AudioMixerGroup group = null)
        { if (!owner) throw new ArgumentNullException(nameof(owner)); this.owner = owner; this.group = group; }
        public Lease<AudioSource> Play(AudioClip clip, LifetimeScope scope, bool loop = false)
        {
            if (!owner || !clip) throw new MissingReferenceException("Audio owner or clip missing");
            if (!scope.IsAlive) throw new ObjectDisposedException(nameof(scope));
            var go = new GameObject("GreaAudio"); go.transform.SetParent(owner, false);
            var source = go.AddComponent<AudioSource>();
            source.playOnAwake = false; source.clip = clip; source.loop = loop; source.outputAudioMixerGroup = group;
            var handle = scope.Own(source, x => {
                if (!x) return;
                x.Stop(); x.clip = null;
                if (Application.isPlaying) UnityEngine.Object.Destroy(x.gameObject);
                else UnityEngine.Object.DestroyImmediate(x.gameObject);
            });
            source.Play(); return handle;
        }
    }
    public sealed class UnityPlatformInfo : IPlatformInfo
    {
        public string Platform => Application.platform.ToString();
        public bool HasFocus => Application.isFocused;
    }
    public sealed class UnityGameClock : IGameClock { public double Seconds => Time.timeAsDouble; }
}
