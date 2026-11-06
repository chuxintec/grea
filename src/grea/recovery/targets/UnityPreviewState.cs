// Import-time static preview operations. Does not load or execute source scripts.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

public static class UnityPreviewState
{
    public static bool IsFrozenNativeRenderer(MonoBehaviour behavior) {
        if(behavior==null)return false;
        var type=behavior.GetType();var name=type.FullName;
        if(name!="Spine.Unity.SkeletonGraphic"&&name!="Spine.Unity.SkeletonAnimation")return false;
        var timeScale=type.GetField("timeScale");
        if(timeScale==null||!(timeScale.GetValue(behavior) is float)||((float)timeScale.GetValue(behavior))!=0f)return false;
        foreach(var marker in behavior.GetComponents<MonoBehaviour>()) {
            if(marker==null||marker.enabled||marker.GetType().FullName!="UnitySpineSourceIdentity")continue;
            var mt=marker.GetType();
            if((mt.GetField("renderer")?.GetValue(marker) as UnityEngine.Object)!=behavior)continue;
            if(!(mt.GetField("persistentVisiblePose")?.GetValue(marker) is bool visible)||!visible)continue;
            if(!(mt.GetField("sourceTimeScaleVerified")?.GetValue(marker) is bool verified)||!verified)continue;
            if(mt.GetField("nativeTimeScale")?.GetValue(marker) is float speed&&speed==0f)return true;
        }
        return false;
    }
    static readonly HashSet<string> StaticLayoutHelpers = new HashSet<string>(StringComparer.Ordinal)
    {
        "NativeRectConstraints", "NativeTextLineBox", "IntrinsicGridLayoutGroup", "NativeLinearLayoutGroup", "NativeHorizontalProgressFill", "NativeInputBlocker", "NativeInputBlockerSurface", "NativeStaticTextOutline", "Monkey.Targets.Spine.UnitySpineGraphicMaterialPresentation"
    };
    [Serializable] public sealed class EvidenceSpec { public string id, path, sha256; }
    [Serializable] public sealed class OperationSpec
    {
        public string kind, sourceId, stringValue, assetId, expectedStringValue, expectedAssetId, evidenceId,nativeAssetId,nativeExpectedAssetId;
        public bool boolValue, expectedBoolValue, sourceEnabled; public float numberValue,expectedNumberValue;
        public float[] vectorValue, expectedVectorValue;
    }
    [Serializable] public class OperationState
    {
        public int schemaVersion;
        public string stateId, sourcePrefabId, sourceManifestSha256, sourceVersion, referenceVersion, stateSha256;
        public EvidenceSpec[] evidence;
        public OperationSpec[] operations;
    }
    // Clone rows carry only operations; never recursively serialize clone batches.
    [Serializable] public sealed class Spec : OperationState
    {
        public UnityPreviewClones.CloneBatch[] cloneBatches;
        public UnityStaticSpriteFrames.ProjectionPlan spriteProjection;
    }
    [Serializable] public sealed class OperationReadback
    {
        public string kind, sourceId, evidenceId, actualAssetId;
        public bool verified, actualBoolValue, actualAssetPresent, actualAssetIdentityKnown;
        public float[] actualVectorValue; public float actualNumberValue;
        public string actualStringValue; public int[] missingGlyphs;
    }
    [Serializable] public sealed class Readback
    {
        public string stateId, sourcePrefabId, sourceManifestSha256, sourceVersion, referenceVersion, stateSha256;
        public bool applied, verified, businessBehaviorComplete;
        public OperationReadback[] operations;
        public string[] gaps;
    }

    sealed class Pending
    {
        public OperationSpec spec;
        public Action apply;
    }
    static bool Digest(string value) { return Regex.IsMatch(value ?? "", "^[0-9a-f]{64}$"); }
    static void Validate(OperationState spec)
    {
        if (spec == null || spec.schemaVersion != 1 || String.IsNullOrEmpty(spec.stateId) ||
            String.IsNullOrEmpty(spec.sourcePrefabId) || String.IsNullOrEmpty(spec.sourceVersion) ||
            String.IsNullOrEmpty(spec.referenceVersion) || !Digest(spec.sourceManifestSha256) || !Digest(spec.stateSha256))
            throw new InvalidOperationException("PREVIEW_STATE_SPEC_INVALID");
        if (spec.evidence == null || spec.evidence.Length == 0 || spec.evidence.Any(e => e == null || String.IsNullOrEmpty(e.id) || String.IsNullOrEmpty(e.path) || !Digest(e.sha256)))
            throw new InvalidOperationException("PREVIEW_STATE_EVIDENCE_INVALID");
        if (spec.evidence.Select(e => e.id).Distinct().Count() != spec.evidence.Length)
            throw new InvalidOperationException("PREVIEW_STATE_EVIDENCE_DUPLICATE");
        if (spec.operations == null || spec.operations.Length == 0 || spec.operations.Any(op => op == null || String.IsNullOrEmpty(op.sourceId) ||
            String.IsNullOrEmpty(op.evidenceId) || !spec.evidence.Any(e => e.id == op.evidenceId) ||
            !op.sourceId.StartsWith(spec.sourcePrefabId + "#", StringComparison.Ordinal)))
            throw new InvalidOperationException("PREVIEW_STATE_OPERATIONS_INVALID");
        if (spec.operations.Select(op => op.kind + "\n" + op.sourceId).Distinct().Count() != spec.operations.Length)
            throw new InvalidOperationException("PREVIEW_STATE_OPERATION_DUPLICATE");
    }
    static UnityEngine.Object Resolve(string sourceId, Func<string, UnityEngine.Object> resolver)
    {
        if (resolver == null) throw new InvalidOperationException("PREVIEW_STATE_RESOLVER_MISSING: " + sourceId);
        UnityEngine.Object value;
        try { value = resolver(sourceId); }
        catch (Exception error) { throw new InvalidOperationException("PREVIEW_STATE_RESOLVE_FAILED: " + sourceId, error); }
        if (value == null) throw new InvalidOperationException("PREVIEW_STATE_SOURCE_MISSING: " + sourceId);
        return value;
    }
    static GameObject GameObjectFor(UnityEngine.Object value, string sourceId)
    {
        var go = value as GameObject;
        var component = value as Component;
        if (go == null && component != null) go = component.gameObject;
        if (go == null) throw new InvalidOperationException("PREVIEW_STATE_NODE_TYPE: " + sourceId);
        if (EditorUtility.IsPersistent(go) || !go.scene.IsValid() || !go.scene.isLoaded)
            throw new InvalidOperationException("PREVIEW_STATE_REQUIRES_SCENE_CLONE: " + sourceId);
        return go;
    }
    static void EnsureUserBehaviorsDisabled(GameObject root)
    {
        foreach (var behavior in root.GetComponentsInChildren<MonoBehaviour>(true))
        {
            var assembly = behavior.GetType().Assembly.GetName().Name ?? "";
            bool engineOwned = assembly.StartsWith("UnityEngine", StringComparison.Ordinal) ||
                               assembly.StartsWith("Unity.", StringComparison.Ordinal) ||
                               assembly.StartsWith("UnityEditor", StringComparison.Ordinal) ||
                               assembly.StartsWith("Unity.TextMeshPro", StringComparison.Ordinal) ||
                               assembly.StartsWith("TMPro", StringComparison.Ordinal);
            bool staticLayout = StaticLayoutHelpers.Contains(behavior.GetType().FullName ?? "");
            if (!engineOwned && !staticLayout && !IsFrozenNativeRenderer(behavior) && behavior.enabled)
                throw new InvalidOperationException("PREVIEW_STATE_ENABLED_USER_BEHAVIOR: " + behavior.GetType().FullName);
        }
    }
    static bool Near(float a, float b) { return Mathf.Abs(a - b) <= 1e-5f; }
    static bool Near(Vector3 a, Vector3 b) { return Near(a.x, b.x) && Near(a.y, b.y) && Near(a.z, b.z); }
    static Vector3 Vector(float[] value, string sourceId)
    {
        if (value == null || value.Length != 3 || value.Any(v => Single.IsNaN(v) || Single.IsInfinity(v)))
            throw new InvalidOperationException("PREVIEW_STATE_VECTOR_INVALID: " + sourceId);
        return new Vector3(value[0], value[1], value[2]);
    }
    static TMP_Text Label(UnityEngine.Object value, string sourceId)
    {
        var label = value as TMP_Text;
        if (label == null)
        {
            var go = value as GameObject;
            var component = value as Component;
            if (go == null && component != null) go = component.gameObject;
            if (go != null) label = go.GetComponent<TMP_Text>();
        }
        if (label == null) throw new InvalidOperationException("PREVIEW_STATE_LABEL_MISSING: " + sourceId);
        GameObjectFor(label, sourceId);
        return label;
    }
    static Image SpriteImage(UnityEngine.Object value, string sourceId)
    {
        var image = value as Image;
        if (image == null)
        {
            var go = value as GameObject;
            var component = value as Component;
            if (go == null && component != null) go = component.gameObject;
            if (go != null) image = go.GetComponent<Image>();
        }
        if (image == null) throw new InvalidOperationException("PREVIEW_STATE_SPRITE_COMPONENT_MISSING: " + sourceId);
        GameObjectFor(image, sourceId);
        return image;
    }
    static Sprite ResolveSprite(string assetId, Func<string, UnityEngine.Object> resolver, bool optional)
    {
        if (String.IsNullOrEmpty(assetId))
        {
            if (optional) return null;
            throw new InvalidOperationException("PREVIEW_STATE_SPRITE_ASSET_ID_MISSING");
        }
        var sprite = Resolve(assetId, resolver) as Sprite;
        if (sprite == null) throw new InvalidOperationException("PREVIEW_STATE_SPRITE_ASSET_TYPE: " + assetId);
        return sprite;
    }

    static float Number(OperationSpec op,UnityEngine.Object value) {
        if(op.kind=="node.opacity"){var group=GameObjectFor(value,op.sourceId).GetComponent<CanvasGroup>();return(group==null?1:group.alpha)*255;}
        if(op.kind=="progress.value"){var slider=value as Slider;if(slider==null)throw new InvalidOperationException("PREVIEW_PROGRESS_MISSING");return slider.normalizedValue;}
        var label=Label(value,op.sourceId);
        return op.kind=="label.fontSize"?label.fontSize:label.font.faceInfo.lineHeight*label.fontSize/label.font.faceInfo.pointSize+label.lineSpacing*label.fontSize/100f;
    }
    static void SetNumber(OperationSpec op,UnityEngine.Object value) {
        if(op.kind=="node.opacity"){var go=GameObjectFor(value,op.sourceId);var group=go.GetComponent<CanvasGroup>()??go.AddComponent<CanvasGroup>();group.alpha=op.numberValue/255f;return;}
        if(op.kind=="progress.value"){((Slider)value).normalizedValue=op.numberValue;return;}
        var label=Label(value,op.sourceId);
        if(op.kind=="label.fontSize")label.fontSize=op.numberValue;
        else label.lineSpacing=(op.numberValue-label.font.faceInfo.lineHeight*label.fontSize/label.font.faceInfo.pointSize)*100f/label.fontSize;
    }
    public static Readback Apply(OperationState spec, Func<string, UnityEngine.Object> resolve)
    {
        Validate(spec);
        var pending = new List<Pending>();
        foreach (var op in spec.operations)
        {
            switch (op.kind)
            {
                case "node.active":
                {
                    var go = GameObjectFor(Resolve(op.sourceId, resolve), op.sourceId);
                    bool before = op.expectedBoolValue, after = op.boolValue, current = go.activeSelf;
                    if (current != before && current != after) throw new InvalidOperationException("PREVIEW_STATE_REENTRY_MISMATCH: " + op.sourceId);
                    if (current != after) EnsureUserBehaviorsDisabled(go);
                    pending.Add(new Pending { spec = op, apply = () => { if (go.activeSelf == before) go.SetActive(after); } });
                    break;
                }
                case "node.scale":
                {
                    var go = GameObjectFor(Resolve(op.sourceId, resolve), op.sourceId);
                    var before = Vector(op.expectedVectorValue, op.sourceId); var after = Vector(op.vectorValue, op.sourceId);
                    var current = go.transform.localScale;
                    if (!Near(current, before) && !Near(current, after)) throw new InvalidOperationException("PREVIEW_STATE_REENTRY_MISMATCH: " + op.sourceId);
                    pending.Add(new Pending { spec = op, apply = () => { if (Near(go.transform.localScale, before)) go.transform.localScale = after; } });
                    break;
                }
                case "node.opacity":case "label.fontSize":case "label.lineHeight":case "progress.value": {
                    var value=Resolve(op.sourceId,resolve);var current=Number(op,value);
                    if(!Near(current,op.expectedNumberValue)&&!Near(current,op.numberValue))throw new InvalidOperationException("PREVIEW_STATE_REENTRY_MISMATCH: "+op.sourceId);
                    pending.Add(new Pending{spec=op,apply=()=>SetNumber(op,value)});break;
                }
                case "label.text":
                {
                    var label = Label(Resolve(op.sourceId, resolve), op.sourceId);
                    string before = op.expectedStringValue, after = op.stringValue, current = label.text;
                    if (before == null || after == null || (current != before && current != after)) throw new InvalidOperationException("PREVIEW_STATE_REENTRY_MISMATCH: " + op.sourceId);
                    pending.Add(new Pending { spec = op, apply = () => { if (label.text == before) label.text = after; } });
                    break;
                }
                case "sprite.asset":
                {
                    var image = SpriteImage(Resolve(op.sourceId, resolve), op.sourceId);
                    var before = ResolveSprite(op.nativeExpectedAssetId??op.expectedAssetId, resolve, true);
                    var after = ResolveSprite(op.nativeAssetId??op.assetId, resolve, true);
                    if (image.sprite != before && image.sprite != after) throw new InvalidOperationException("PREVIEW_STATE_REENTRY_MISMATCH: " + op.sourceId);
                    pending.Add(new Pending { spec = op, apply = () => { if (image.sprite == before) image.sprite = after; image.enabled = op.sourceEnabled; } });
                    break;
                }
                default: throw new InvalidOperationException("PREVIEW_STATE_KIND_UNSUPPORTED: " + op.kind);
            }
        }
        foreach (var item in pending) item.apply();
        var result = Read(spec, resolve);
        result.applied = true;
        return result;
    }

    public static Readback Read(OperationState spec, Func<string, UnityEngine.Object> resolve)
    {
        Validate(spec);
        var rows = new List<OperationReadback>();
        foreach (var op in spec.operations)
        {
            var row = new OperationReadback { kind = op.kind, sourceId = op.sourceId, evidenceId = op.evidenceId };
            switch (op.kind)
            {
                case "node.active":
                    row.actualBoolValue = GameObjectFor(Resolve(op.sourceId, resolve), op.sourceId).activeSelf;
                    row.verified = row.actualBoolValue == op.boolValue;
                    break;
                case "node.scale":
                    var scale = GameObjectFor(Resolve(op.sourceId, resolve), op.sourceId).transform.localScale;
                    row.actualVectorValue = new[] { scale.x, scale.y, scale.z };
                    row.verified = Near(scale, Vector(op.vectorValue, op.sourceId));
                    break;
                case "node.opacity":case "label.fontSize":case "label.lineHeight":case "progress.value":
                    row.actualNumberValue=Number(op,Resolve(op.sourceId,resolve));row.verified=Near(row.actualNumberValue,op.numberValue);break;
                case "label.text":
                    var label = Label(Resolve(op.sourceId, resolve), op.sourceId);
                    row.actualStringValue = label.text;
                    uint[] missing=Array.Empty<uint>();
                    bool glyphs=label.font!=null&&label.font.HasCharacters(op.stringValue,out missing,true,true);
                    if(label.font==null)missing=new uint[0];
                    row.missingGlyphs=(missing??Array.Empty<uint>()).Select(x=>(int)x).Distinct().ToArray();
                    row.verified = row.actualStringValue == op.stringValue && glyphs;
                    break;
                case "sprite.asset":
                    var image = SpriteImage(Resolve(op.sourceId, resolve), op.sourceId);
                    var expectedSprite = ResolveSprite(op.nativeAssetId??op.assetId, resolve, true);
                    var beforeSprite = ResolveSprite(op.nativeExpectedAssetId??op.expectedAssetId, resolve, true);
                    row.actualAssetPresent = image.sprite != null;
                    if (image.sprite == expectedSprite) { row.actualAssetId = op.assetId; row.actualAssetIdentityKnown = true; }
                    else if (image.sprite == beforeSprite) { row.actualAssetId = op.expectedAssetId; row.actualAssetIdentityKnown = true; }
                    else if (image.sprite == null) row.actualAssetIdentityKnown = true;
                    row.verified = image.sprite == expectedSprite && image.enabled == op.sourceEnabled;
                    break;
                default: throw new InvalidOperationException("PREVIEW_STATE_KIND_UNSUPPORTED: " + op.kind);
            }
            rows.Add(row);
        }
        bool verified = rows.All(row => row.verified);
        return new Readback { stateId = spec.stateId, sourcePrefabId = spec.sourcePrefabId,
            sourceManifestSha256 = spec.sourceManifestSha256, sourceVersion = spec.sourceVersion,
            referenceVersion = spec.referenceVersion, stateSha256 = spec.stateSha256,
            applied = false, verified = verified, businessBehaviorComplete = false,
            operations = rows.ToArray(), gaps = verified ? Array.Empty<string>() : new[] { "preview_state_readback_mismatch" } };
    }
}
