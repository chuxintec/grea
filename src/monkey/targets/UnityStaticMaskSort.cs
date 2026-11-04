using System;
using System.Collections.Generic;
using System.Linq;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;
using UnityEngine.UI;
using UnityEditor;

namespace Monkey.StaticMaskSort
{
    [Serializable] public sealed class MaskSpec
    {
        public string sourceId, nativeId, node;
        public int maskType;
        public bool enabled, inverted;
        public float alphaThreshold;
        public string spriteFrameUuid;
        public string sourceFieldsJson;
        public string sourceMaterialId, resolvedSourceMaterialId, sourceEffectId, sourceEffectName, sourceEffectDocumentSha256;
        public string unityMaskShaderPath, unityMaskShaderSha256, unityMaskMaterialGuid, unityMaskMaterialPath;
    }
    [Serializable] public sealed class SortSpec
    {
        public string sourceId, nativeId, node;
        public bool enabled;
        public float sortOrder;
    }
    [Serializable] public sealed class SortRootSpec
    {
        public string sourceId, nativeId, node;
        public bool enabled;
    }
    [Serializable] public sealed class SortGroupSpec
    {
        public string parent, sortRootScope;
        public bool representableBySiblingOrder;
        public string[] expectedSiblingOrder;
    }
    [Serializable] public sealed class MaskReadback
    {
        public string sourceId, node, nativeType, spriteFrameUuid;
        public string sourceMaterialId, resolvedSourceMaterialId, sourceEffectId, sourceEffectName, sourceEffectDocumentSha256;
        public string unityMaskMaterialGuid;
        public string unityMaskShaderPath, unityMaskShaderSha256;
        public bool enabled, inverted, verified;
        public int maskType;
        public float alphaThreshold;
        public string sourceFieldsJson;
    }
    [Serializable] public sealed class SortReadback
    {
        public string sourceId, node, nativeType;
        public bool enabled, sourceGroupRepresentable, sourceQueueMapped, verified;
        public float sortOrder;
        public int siblingIndex;
        public string diagnostic;
    }
    [Serializable] public sealed class SortRootReadback
    {
        public string sourceId, node, nativeType;
        public bool enabled, sourceQueueMapped, verified;
        public string diagnostic;
    }

    /// <summary>
    /// Reusable partial-integration hooks. Call after nodes and source Sprite
    /// assets exist. Sort mapping deliberately changes sibling order only for
    /// direct siblings; callers must keep nested SortRoot scopes separate.
    /// </summary>
    public static class UnityStaticMaskSort
    {
        static string FileSha256(string path)
        {
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-", "").ToLowerInvariant();
        }

        static bool ImageMaskAssetMatches(MaskSpec spec, Material material)
        {
            if (material == null || material.shader == null || material.shader.name != "Monkey/NativeStaticImageMask") return false;
            if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material, out var materialGuid, out long _)) return false;
            if (materialGuid != spec.unityMaskMaterialGuid) return false;
            var shaderAssetPath = AssetDatabase.GetAssetPath(material.shader);
            if (shaderAssetPath != spec.unityMaskShaderPath) return false;
            var absolute = Path.GetFullPath(Path.Combine(Application.dataPath, "..", shaderAssetPath));
            return File.Exists(absolute) && FileSha256(absolute) == spec.unityMaskShaderSha256;
        }

        public static MaskReadback[] CreateStaticMasks(MaskSpec[] specs,
            IDictionary<string, GameObject> nodes, Func<string, Sprite> resolveSprite,
            Func<MaskSpec, Material> resolveMaskMaterial)
        {
            var result = new List<MaskReadback>();
            foreach (var spec in specs ?? Array.Empty<MaskSpec>())
            {
                if (spec == null || !nodes.TryGetValue(spec.node, out var go) || go == null)
                    throw new InvalidOperationException("STATIC_MASK_NODE_MISSING: " + (spec == null ? "<null>" : spec.sourceId));
                if (go.GetComponent<Mask>() || go.GetComponent<RectMask2D>())
                    throw new InvalidOperationException("STATIC_MASK_ALREADY_EXISTS: " + spec.sourceId);
                Graphic shape;
                if (spec.maskType == 0)
                {
                    if (spec.inverted)
                        shape = go.AddComponent<NativeStaticInvertedMaskGraphic>();
                    else shape = go.GetComponent<Image>() ?? go.AddComponent<Image>();
                }
                else if (spec.maskType == 1)
                    shape = go.AddComponent<NativeStaticEllipseMaskGraphic>();
                else if (spec.maskType == 2)
                {
                    var sprite = resolveSprite == null ? null : resolveSprite(spec.spriteFrameUuid);
                    if (sprite == null) throw new InvalidOperationException("STATIC_MASK_SPRITE_MISSING: " + spec.sourceId);
                    var image = go.GetComponent<Image>() ?? go.AddComponent<Image>();
                    image.sprite = sprite;
                    var material = resolveMaskMaterial == null ? null : resolveMaskMaterial(spec);
                    string materialGuid; long materialFileId;
                    if (material == null || !material.HasProperty("_AlphaThreshold") ||
                        Mathf.Abs(material.GetFloat("_AlphaThreshold") - spec.alphaThreshold) > 0.000001f ||
                        !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material, out materialGuid, out materialFileId) ||
                        materialGuid != spec.unityMaskMaterialGuid || !ImageMaskAssetMatches(spec, material))
                        throw new InvalidOperationException("STATIC_MASK_THRESHOLD_MATERIAL_MISMATCH: " + spec.sourceId);
                    if (image == null) throw new InvalidOperationException("STATIC_MASK_IMAGE_MISSING: " + spec.sourceId);
                    image.material = material;
                    shape = image;
                }
                else throw new InvalidOperationException("STATIC_MASK_TYPE_UNSUPPORTED: " + spec.sourceId);
                shape.raycastTarget = false;
                shape.enabled = spec.enabled;
                var mask = go.AddComponent<Mask>();
                mask.showMaskGraphic = false;
                mask.enabled = spec.enabled;
                var identity = go.AddComponent<NativeStaticMaskIdentity>();
                identity.sourceId = spec.sourceId; identity.nativeId = spec.nativeId;
                identity.sourceMaskType = spec.maskType; identity.sourceInverted = spec.inverted;
                identity.sourceAlphaThreshold = spec.alphaThreshold;
                identity.spriteFrameUuid = spec.spriteFrameUuid; identity.sourceFieldsJson = spec.sourceFieldsJson;
                identity.sourceMaterialId = spec.sourceMaterialId; identity.resolvedSourceMaterialId = spec.resolvedSourceMaterialId;
                identity.sourceEffectId = spec.sourceEffectId; identity.sourceEffectName = spec.sourceEffectName;
                identity.sourceEffectDocumentSha256 = spec.sourceEffectDocumentSha256;
                result.Add(ReadStaticMask(spec, go, resolveSprite));
            }
            return result.ToArray();
        }

        public static MaskReadback ReadStaticMask(MaskSpec spec, GameObject go, Func<string, Sprite> resolveSprite)
        {
            var mask = go == null ? null : go.GetComponent<Mask>();
            var identity = go == null ? null : go.GetComponent<NativeStaticMaskIdentity>();
            var graphic = go == null ? null : go.GetComponent<Graphic>();
            var typeOk = spec.maskType == 0 ? (spec.inverted ? graphic is NativeStaticInvertedMaskGraphic : graphic is Image) :
                spec.maskType == 1 ? graphic is NativeStaticEllipseMaskGraphic : graphic is Image;
            var image = graphic as Image;
            var invertedCanvasOk = !spec.inverted || (graphic is NativeStaticInvertedMaskGraphic &&
                graphic.GetComponentInParent<Canvas>() != null);
            var imageMaterialOk = spec.maskType != 2 || (image != null && image.sprite != null && image.material != null &&
                image.material.HasProperty("_AlphaThreshold") && image.sprite == (resolveSprite == null ? null : resolveSprite(spec.spriteFrameUuid)) &&
                Math.Abs(image.material.GetFloat("_AlphaThreshold") - spec.alphaThreshold) < .000001f &&
                ImageMaskAssetMatches(spec, image.material));
            var verified = mask != null && identity != null && typeOk && identity.sourceId == spec.sourceId &&
                identity.nativeId == spec.nativeId && identity.sourceMaskType == spec.maskType &&
                identity.sourceInverted == spec.inverted && identity.sourceAlphaThreshold == spec.alphaThreshold &&
                identity.sourceFieldsJson == spec.sourceFieldsJson && mask.enabled == spec.enabled && !mask.showMaskGraphic &&
                identity.sourceMaterialId == spec.sourceMaterialId && identity.resolvedSourceMaterialId == spec.resolvedSourceMaterialId &&
                identity.sourceEffectId == spec.sourceEffectId && identity.sourceEffectName == spec.sourceEffectName &&
                identity.sourceEffectDocumentSha256 == spec.sourceEffectDocumentSha256 && imageMaterialOk &&
                invertedCanvasOk && graphic.enabled == spec.enabled && !graphic.raycastTarget;
            return new MaskReadback { sourceId = spec.sourceId, node = spec.node,
                nativeType = mask == null ? null : mask.GetType().FullName, enabled = mask != null && mask.enabled,
                maskType = identity == null ? -1 : identity.sourceMaskType,
                inverted = identity != null && identity.sourceInverted,
                alphaThreshold = identity == null ? -1 : identity.sourceAlphaThreshold,
                spriteFrameUuid = identity == null ? null : identity.spriteFrameUuid,
                sourceFieldsJson = identity == null ? null : identity.sourceFieldsJson,
                sourceMaterialId = identity == null ? null : identity.sourceMaterialId,
                resolvedSourceMaterialId = identity == null ? null : identity.resolvedSourceMaterialId,
                sourceEffectId = identity == null ? null : identity.sourceEffectId,
                sourceEffectName = identity == null ? null : identity.sourceEffectName,
                sourceEffectDocumentSha256 = identity == null ? null : identity.sourceEffectDocumentSha256,
                unityMaskMaterialGuid = spec.unityMaskMaterialGuid, unityMaskShaderPath = spec.unityMaskShaderPath,
                unityMaskShaderSha256 = spec.unityMaskShaderSha256, verified = verified };
        }

        public static SortReadback[] CreateStaticSort(SortSpec[] orderSpecs, SortRootSpec[] rootSpecs,
            SortGroupSpec[] groupSpecs, IDictionary<string, GameObject> nodes)
        {
            if (groupSpecs == null) throw new InvalidOperationException("STATIC_SORT_SCOPE_PROOF_REQUIRED");
            var specs = orderSpecs ?? Array.Empty<SortSpec>();
            foreach (var spec in specs)
                if (spec == null || !nodes.ContainsKey(spec.node))
                    throw new InvalidOperationException("STATIC_SORT_NODE_MISSING: " + (spec == null ? "<null>" : spec.sourceId));
            return specs.Select(s => {
                var parent = nodes[s.node].transform.parent;
                var provedSiblingGroup = groupSpecs.Any(g => g != null && g.representableBySiblingOrder &&
                    nodes.TryGetValue(g.parent, out var parentGo) && parentGo != null && parentGo.transform == parent);
                return ReadStaticSort(s, nodes[s.node], provedSiblingGroup);
            }).ToArray();
        }

        public static SortRootReadback[] ReadStaticSortRoots(SortRootSpec[] specs,
            IDictionary<string, GameObject> nodes)
        {
            return (specs ?? Array.Empty<SortRootSpec>()).Select(spec => {
                var go = nodes.TryGetValue(spec.node, out var value) ? value : null;
                return new SortRootReadback { sourceId = spec.sourceId, node = spec.node,
                    nativeType = null, enabled = spec.enabled, sourceQueueMapped = false,
                    diagnostic = "STATIC_SORT_GLOBAL_QUEUE_ADAPTER_REQUIRED", verified = false };
            }).ToArray();
        }

        public static SortReadback ReadStaticSort(SortSpec spec, GameObject go, bool sourceGroupRepresentable)
        {
            return new SortReadback { sourceId = spec.sourceId, node = spec.node,
                nativeType = null, enabled = spec.enabled, sortOrder = spec.sortOrder,
                sourceGroupRepresentable = sourceGroupRepresentable,
                siblingIndex = go == null ? -1 : go.transform.GetSiblingIndex(),
                sourceQueueMapped = false, diagnostic = "STATIC_SORT_GLOBAL_QUEUE_ADAPTER_REQUIRED", verified = false };
        }
    }
}
