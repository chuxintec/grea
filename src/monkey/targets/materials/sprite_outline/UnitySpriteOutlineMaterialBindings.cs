// Editor-only native Sprite outline material creation and exact Sprite binding.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;

public static class UnitySpriteOutlineMaterialBindings
{
    const string Profile = "cocos24-sprite-alpha-outline-v1";
    const string ProgramHash = "53fbec41d8b524d31908b3b27f1b6cccbd2fcd1eb0be9ace5917be386dad4784";
    const float Epsilon = 0.0001f;

    [Serializable] public sealed class Properties
    {
        public float[] outlineColor, outlineTextureSize;
        public float outlineWidth, fillAlpha, alphaThreshold;
    }
    [Serializable] public sealed class Target
    {
        public string shaderPath, shaderGuid, materialPath, materialGuid;
    }
    [Serializable] public sealed class SpriteBinding
    {
        public string sourceId, spriteFrameSourceId;
    }
    [Serializable] public sealed class Spec
    {
        public string schema, profile, programCanonicalSha256, materialSourceId, module;
        public Properties properties;
        public Target unity;
        public string[] sourceComponentIds;
        public SpriteBinding[] spriteBindings;
    }
    [Serializable] public sealed class Readback
    {
        public string materialSourceId, materialGuid, shaderGuid;
        public long localFileId;
        public bool persistent, shaderCompiled, propertiesVerified;
        public float[] outlineColor, outlineTextureSize;
        public float outlineWidth, fillAlpha, alphaThreshold;
    }

    static void Validate(Spec spec)
    {
        if (spec == null || spec.schema != "monkey-prefab-sprite-outline-binding/1" ||
            spec.profile != Profile || spec.programCanonicalSha256 != ProgramHash)
            throw new InvalidOperationException("SPRITE_OUTLINE_PROFILE_UNSUPPORTED");
        if (spec.properties == null || spec.properties.outlineColor == null || spec.properties.outlineColor.Length != 4 ||
            spec.properties.outlineTextureSize == null || spec.properties.outlineTextureSize.Length != 2 ||
            spec.properties.outlineWidth < 0 || spec.properties.outlineWidth > 8 ||
            spec.properties.fillAlpha < 0 || spec.properties.fillAlpha > 1 ||
            spec.properties.alphaThreshold < 0 || spec.properties.alphaThreshold >= 1)
            throw new InvalidOperationException("SPRITE_OUTLINE_PROPERTIES_INVALID");
        if (spec.unity == null || String.IsNullOrEmpty(spec.unity.shaderPath) || String.IsNullOrEmpty(spec.unity.materialPath) ||
            !Regex.IsMatch(spec.unity.shaderGuid ?? "", "^[0-9a-f]{32}$") ||
            !Regex.IsMatch(spec.unity.materialGuid ?? "", "^[0-9a-f]{32}$"))
            throw new InvalidOperationException("SPRITE_OUTLINE_UNITY_IDENTITY_INVALID");
        if (!spec.unity.materialPath.StartsWith("Assets/", StringComparison.Ordinal) ||
            !spec.unity.materialPath.EndsWith(".mat", StringComparison.Ordinal) ||
            spec.unity.materialPath.Contains("..") || spec.unity.materialPath.Contains("\\") ||
            !spec.unity.shaderPath.StartsWith("Assets/", StringComparison.Ordinal) || spec.unity.shaderPath.Contains(".."))
            throw new InvalidOperationException("SPRITE_OUTLINE_ASSET_PATH_INVALID");
        if (spec.sourceComponentIds == null || spec.sourceComponentIds.Length == 0 ||
            spec.sourceComponentIds.Distinct().Count() != spec.sourceComponentIds.Length ||
            spec.spriteBindings == null || spec.spriteBindings.Length != spec.sourceComponentIds.Length ||
            !spec.sourceComponentIds.SequenceEqual(spec.spriteBindings.Select(row => row == null ? null : row.sourceId)) ||
            spec.spriteBindings.Any(row => row == null || String.IsNullOrEmpty(row.spriteFrameSourceId)))
            throw new InvalidOperationException("SPRITE_OUTLINE_SOURCE_BINDINGS_INVALID");
        if (spec.properties.outlineColor.Any(value => Single.IsNaN(value) || Single.IsInfinity(value) || value < 0 || value > 1) ||
            spec.properties.outlineTextureSize.Any(value => Single.IsNaN(value) || Single.IsInfinity(value) || value <= 0))
            throw new InvalidOperationException("SPRITE_OUTLINE_PROPERTY_NONFINITE");
    }

    static bool Near(float left, float right) => Mathf.Abs(left - right) <= Epsilon;
    static bool VerifyProperties(Material material, Spec spec)
    {
        if (material == null) return false;
        foreach (var name in new[] { "_OutlineColor", "_OutlineTextureSize", "_OutlineWidth", "_FillAlpha", "_AlphaThreshold" })
            if (!material.HasProperty(name)) return false;
        var color = material.GetColor("_OutlineColor");
        var size = material.GetVector("_OutlineTextureSize");
        return Near(color.r, spec.properties.outlineColor[0]) && Near(color.g, spec.properties.outlineColor[1]) &&
            Near(color.b, spec.properties.outlineColor[2]) && Near(color.a, spec.properties.outlineColor[3]) &&
            Near(size.x, spec.properties.outlineTextureSize[0]) && Near(size.y, spec.properties.outlineTextureSize[1]) &&
            Near(material.GetFloat("_OutlineWidth"), spec.properties.outlineWidth) &&
            Near(material.GetFloat("_FillAlpha"), spec.properties.fillAlpha) &&
            Near(material.GetFloat("_AlphaThreshold"), spec.properties.alphaThreshold);
    }

    public static Readback CreateNative(Spec spec)
    {
        Validate(spec);
        if (FileExists(spec.unity.materialPath))
            throw new InvalidOperationException("SPRITE_OUTLINE_MATERIAL_PATH_COLLISION: " + spec.unity.materialPath);
        var pathGuid = AssetDatabase.AssetPathToGUID(spec.unity.materialPath);
        if (!String.IsNullOrEmpty(pathGuid) && pathGuid != spec.unity.materialGuid)
            throw new InvalidOperationException("SPRITE_OUTLINE_MATERIAL_GUID_CONFLICT: " + pathGuid);
        var guidOwner = AssetDatabase.GUIDToAssetPath(spec.unity.materialGuid);
        if (!String.IsNullOrEmpty(guidOwner) && guidOwner != spec.unity.materialPath)
            throw new InvalidOperationException("SPRITE_OUTLINE_MATERIAL_GUID_ALREADY_OWNED: " + guidOwner);
        var shader = AssetDatabase.LoadAssetAtPath<Shader>(spec.unity.shaderPath);
        if (shader == null || AssetDatabase.AssetPathToGUID(spec.unity.shaderPath) != spec.unity.shaderGuid || ShaderUtil.ShaderHasError(shader))
            throw new InvalidOperationException("SPRITE_OUTLINE_SHADER_NOT_IMPORTED_OR_COMPILED");
        var material = new Material(shader) { name = "Shader2DOutline" };
        material.SetColor("_OutlineColor", new Color(spec.properties.outlineColor[0], spec.properties.outlineColor[1],
            spec.properties.outlineColor[2], spec.properties.outlineColor[3]));
        material.SetVector("_OutlineTextureSize", new Vector4(spec.properties.outlineTextureSize[0], spec.properties.outlineTextureSize[1], 0, 0));
        material.SetFloat("_OutlineWidth", spec.properties.outlineWidth);
        material.SetFloat("_FillAlpha", spec.properties.fillAlpha);
        material.SetFloat("_AlphaThreshold", spec.properties.alphaThreshold);
        if (!VerifyProperties(material, spec)) throw new InvalidOperationException("SPRITE_OUTLINE_PRE_SAVE_PROPERTIES_MISMATCH");
        // CreateAsset assigns a fresh GUID even if an unregistered orphan
        // meta exists. Serialize through Unity's native serializer, then import
        // the complete asset/meta pair so the planned identity is retained.
        try {
            var metaPath = spec.unity.materialPath + ".meta";
            if (System.IO.File.Exists(metaPath)) {
                var meta = System.IO.File.ReadAllText(metaPath);
                var match = Regex.Match(meta, @"(?m)^guid: ([0-9a-f]{32})\s*$");
                if (!match.Success || match.Groups[1].Value != spec.unity.materialGuid)
                    throw new InvalidOperationException("SPRITE_OUTLINE_MATERIAL_META_CONFLICT");
            } else {
                var raw = System.Text.Encoding.UTF8.GetBytes("fileFormatVersion: 2\nguid: " + spec.unity.materialGuid +
                    "\nNativeFormatImporter:\n  externalObjects: {}\n  mainObjectFileID: 2100000\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n");
                using (var stream = new System.IO.FileStream(metaPath, System.IO.FileMode.CreateNew, System.IO.FileAccess.Write))
                    stream.Write(raw, 0, raw.Length);
            }
            UnityEditorInternal.InternalEditorUtility.SaveToSerializedFileAndForget(
                new UnityEngine.Object[] { material }, spec.unity.materialPath, true);
        } finally { UnityEngine.Object.DestroyImmediate(material); }
        AssetDatabase.ImportAsset(spec.unity.materialPath, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
        AssetDatabase.SaveAssets();
        return ReadbackNative(spec);
    }

    static bool FileExists(string path) => System.IO.File.Exists(path) || AssetDatabase.LoadAssetAtPath<Material>(path) != null;

    public static Readback ReadbackNative(Spec spec)
    {
        Validate(spec);
        var saved = AssetDatabase.LoadAssetAtPath<Material>(spec.unity.materialPath);
        if (saved == null || !EditorUtility.IsPersistent(saved) ||
            AssetDatabase.AssetPathToGUID(spec.unity.materialPath) != spec.unity.materialGuid ||
            AssetDatabase.AssetPathToGUID(spec.unity.shaderPath) != spec.unity.shaderGuid ||
            saved.shader == null || ShaderUtil.ShaderHasError(saved.shader) || !VerifyProperties(saved, spec) ||
            !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(saved, out string materialGuid, out long localId) ||
            materialGuid != spec.unity.materialGuid || localId == 0)
            throw new InvalidOperationException("SPRITE_OUTLINE_NATIVE_MATERIAL_READBACK_MISMATCH");
        return new Readback { materialSourceId = spec.materialSourceId, materialGuid = materialGuid,
            shaderGuid = spec.unity.shaderGuid, localFileId = localId, persistent = true,
            shaderCompiled = !ShaderUtil.ShaderHasError(saved.shader), propertiesVerified = true,
            outlineColor = spec.properties.outlineColor, outlineTextureSize = spec.properties.outlineTextureSize,
            outlineWidth = saved.GetFloat("_OutlineWidth"), fillAlpha = saved.GetFloat("_FillAlpha"),
            alphaThreshold = saved.GetFloat("_AlphaThreshold") };
    }

    static HashSet<string> ExpectedIds(Spec spec) => new HashSet<string>(spec.sourceComponentIds, StringComparer.Ordinal);
    static Sprite ExpectedFrame(Spec spec, string sourceId, Func<string, Sprite> resolve)
    {
        var row = spec.spriteBindings.Single(item => item.sourceId == sourceId);
        var sprite = resolve(row.spriteFrameSourceId);
        if (sprite == null) throw new InvalidOperationException("SPRITE_OUTLINE_SOURCE_FRAME_MISSING: " + row.spriteFrameSourceId);
        return sprite;
    }
    static Sprite ReadSprite(Component component)
    {
        var image = component as Image;
        if (image != null) return image.sprite;
        var renderer = component as SpriteRenderer;
        if (renderer != null) return renderer.sprite;
        throw new InvalidOperationException("SPRITE_OUTLINE_COMPONENT_TYPE_UNSUPPORTED");
    }
    static void SetMaterial(Component component, Material material)
    {
        var image = component as Image;
        if (image != null) { image.material = material; return; }
        var renderer = component as SpriteRenderer;
        if (renderer != null) { renderer.sharedMaterial = material; return; }
        throw new InvalidOperationException("SPRITE_OUTLINE_COMPONENT_TYPE_UNSUPPORTED");
    }
    static bool HasMaterial(Component component, Material material)
    {
        var image = component as Image;
        if (image != null) return image.material == material;
        var renderer = component as SpriteRenderer;
        return renderer != null && renderer.sharedMaterial == material;
    }

    public static void Bind(Spec spec, Material savedMaterial, IDictionary<string, Component> components,
        Func<string, Sprite> resolveSpriteFrame)
    {
        Validate(spec);
        if (AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(savedMaterial)) != spec.unity.materialGuid ||
            !VerifyProperties(savedMaterial, spec) || components == null || resolveSpriteFrame == null)
            throw new InvalidOperationException("SPRITE_OUTLINE_MATERIAL_NOT_VERIFIED");
        var expected = ExpectedIds(spec);
        if (components.Count != expected.Count || !expected.SetEquals(components.Keys))
            throw new InvalidOperationException("SPRITE_OUTLINE_SOURCE_COMPONENT_MAP_MISMATCH");
        foreach (var id in expected)
        {
            var component = components[id];
            if (component == null || ReadSprite(component) != ExpectedFrame(spec, id, resolveSpriteFrame))
                throw new InvalidOperationException("SPRITE_OUTLINE_SOURCE_SPRITEFRAME_MISMATCH: " + id);
            SetMaterial(component, savedMaterial);
            if (!HasMaterial(component, savedMaterial) || ReadSprite(component) != ExpectedFrame(spec, id, resolveSpriteFrame))
                throw new InvalidOperationException("SPRITE_OUTLINE_SPRITE_BINDING_READBACK_MISMATCH: " + id);
        }
    }

    public static bool ReadBound(Spec spec, Material savedMaterial, string sourceId, Component component,
        Func<string, Sprite> resolveSpriteFrame)
    {
        Validate(spec);
        if (!ExpectedIds(spec).Contains(sourceId) || !VerifyProperties(savedMaterial, spec) || component == null || resolveSpriteFrame == null)
            return false;
        return HasMaterial(component, savedMaterial) && ReadSprite(component) == ExpectedFrame(spec, sourceId, resolveSpriteFrame);
    }
}
