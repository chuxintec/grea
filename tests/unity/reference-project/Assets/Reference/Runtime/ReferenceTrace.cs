using System;
using System.IO;
using Grea.Reference.Domain;
using UnityEngine;

namespace Grea.Reference
{
    public sealed class ReferenceTrace : IDisposable
    {
        [Serializable] public sealed class Entry
        {
            public int sequence, score, wins;
            public string eventId, phase, buildId;
            public double seconds;
            public float audioRms;
            public float pointerX, pointerY;
            public bool focused;
            public string hit;
        }
        readonly StreamWriter writer;
        int sequence;
        public bool Enabled => writer != null;
        public ReferenceTrace(string path)
        {
            if (path != null) writer = new StreamWriter(new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read));
        }
        public void Record(string code, SignalSession state, float rms = 0, Vector2 pointer = default, string hit = null)
        {
            if (writer == null || sequence >= 512) return;
            writer.WriteLine(JsonUtility.ToJson(new Entry { sequence = ++sequence, eventId = code, phase = state?.Phase.ToString() ?? "Initializing",
                score = state?.Score ?? 0, wins = state?.Wins ?? 0, buildId = Application.buildGUID, seconds = Time.realtimeSinceStartupAsDouble, audioRms = rms, pointerX = pointer.x, pointerY = pointer.y, focused = Application.isFocused, hit = hit }));
            writer.Flush();
        }
        public void Dispose() => writer?.Dispose();
    }
}
