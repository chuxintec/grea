using System.Collections.Generic;
using UnityEngine;

namespace Grea.Foundation.Runtime
{
    public sealed class BootstrapConfig : ScriptableObject
    {
        public string entryScene;
        public string playerSaveNamespace;
        public string qaSaveNamespace;
        public IEnumerable<string> Errors()
        {
            if (string.IsNullOrWhiteSpace(entryScene)) yield return nameof(entryScene);
            if (string.IsNullOrWhiteSpace(playerSaveNamespace)) yield return nameof(playerSaveNamespace);
            if (string.IsNullOrWhiteSpace(qaSaveNamespace) || qaSaveNamespace == playerSaveNamespace) yield return nameof(qaSaveNamespace);
        }
    }
}
