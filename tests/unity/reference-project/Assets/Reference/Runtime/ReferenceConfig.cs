using System;
using UnityEngine;

namespace Grea.Reference
{
    public sealed class ReferenceConfig : ScriptableObject
    {
        public int goal = 5;
        public float collectDelaySeconds = .12f;
        public string playerNamespace = "signal-player";
        public string qaNamespace = "signal-qa";
        public void Validate()
        {
            if (goal != 5 || collectDelaySeconds < 0 || collectDelaySeconds > 2 ||
                string.IsNullOrWhiteSpace(playerNamespace) || string.IsNullOrWhiteSpace(qaNamespace) || playerNamespace == qaNamespace)
                throw new InvalidOperationException("Invalid reference configuration");
        }
    }
}
