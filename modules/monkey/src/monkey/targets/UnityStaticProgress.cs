using UnityEngine;
using UnityEngine.UI;

// Disabled static data carrier for a source cc.ProgressBar. It does not drive
// geometry or execute progress behavior; BarSprite is the actual mapped Image.
public sealed class UnityStaticProgress : MonoBehaviour
{
    [SerializeField] string sourceComponentId;
    [SerializeField] string sourceNodeId;
    [SerializeField] Image barSprite;
    [SerializeField] float progress;
    [SerializeField] float totalLength;
    [SerializeField] int mode;
    [SerializeField] bool reverse;
    [SerializeField] bool sourceEnabled;

    public string SourceComponentId { get { return sourceComponentId; } }
    public string SourceNodeId { get { return sourceNodeId; } }
    public Image BarSprite { get { return barSprite; } }
    public float Progress { get { return progress; } }
    public float TotalLength { get { return totalLength; } }
    public int Mode { get { return mode; } }
    public bool Reverse { get { return reverse; } }
    public bool SourceEnabled { get { return sourceEnabled; } }

    public void Configure(string componentId, string nodeId, Image sprite,
        float progressValue, float lengthValue, int modeValue,
        bool reverseValue, bool enabledValue)
    {
        sourceComponentId = componentId;
        sourceNodeId = nodeId;
        barSprite = sprite;
        progress = progressValue;
        totalLength = lengthValue;
        mode = modeValue;
        reverse = reverseValue;
        sourceEnabled = enabledValue;
        enabled = false;
    }
}
