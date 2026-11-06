using UnityEngine;

namespace Monkey.NativeUiContracts
{
    /// <summary>A retained native transition target, independent of a consumer's helper namespace.</summary>
    public interface INativeStaticButtonTarget
    {
        GameObject TransitionTarget { get; }
    }
}
