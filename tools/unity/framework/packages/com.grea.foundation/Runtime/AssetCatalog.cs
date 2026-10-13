using System;
using System.Collections.Generic;
using Grea.Foundation.Contracts;
using UnityEngine;

namespace Grea.Foundation.Runtime
{
    // Borrowed Unity objects remain owned by their scene/package. Handles own only claims.
    public sealed class AssetCatalog
    {
        readonly Dictionary<string, UnityEngine.Object> assets;
        readonly Dictionary<string, int> references = new Dictionary<string, int>();
        public int ActiveHandles { get; private set; }
        public AssetCatalog(IDictionary<string, UnityEngine.Object> assets)
        {
            this.assets = new Dictionary<string, UnityEngine.Object>(assets ?? throw new ArgumentNullException(nameof(assets)));
            foreach (var pair in this.assets)
                if (string.IsNullOrWhiteSpace(pair.Key) || !pair.Value) throw new ArgumentException("Invalid catalog entry: " + pair.Key);
        }
        public Lease<T> Acquire<T>(string key, LifetimeScope scope) where T : UnityEngine.Object
        {
            if (!assets.TryGetValue(key, out var asset)) throw new KeyNotFoundException(key);
            if (!asset) throw new MissingReferenceException(key);
            if (!(asset is T typed)) throw new InvalidCastException(key);
            var handle = scope.Own(typed, _ => { references[key]--; ActiveHandles--; });
            references.TryGetValue(key, out int count); references[key] = count + 1; ActiveHandles++;
            return handle;
        }
        public int ReferenceCount(string key) => references.TryGetValue(key, out var count) ? count : 0;
    }
}
