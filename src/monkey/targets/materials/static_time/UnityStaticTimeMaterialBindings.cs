using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditorInternal;
using UnityEngine;
using UnityEngine.UI;

/// <summary>Native material adapter for a source-pinned, clock-independent Sprite at source t=0.</summary>
public static class UnityStaticTimeMaterialBindings
{
    [Serializable] public sealed class Spec
    {
        public string schema, profile, target, sourceManifestSha256, normalizedIrSha256;
        public float staticTimeSeconds;
        public string targetShaderSha256;
        public MaterialSpec[] materials;
        public TargetShader targetShader;
    }

    [Serializable] public sealed class TargetShader { public TargetShaderRef unity, creator; }
    [Serializable] public sealed class TargetShaderRef { public string path, guid, uuid, metaPath; }
    [Serializable] public sealed class UnityTarget
    {
        public string shaderPath, shaderGuid, materialPath, materialGuid;
    }
    [Serializable] public sealed class CreatorTarget
    {
        public string effectPath, effectUuid, effectMetaPath, materialPath, materialUuid, materialMetaPath;
    }
    [Serializable] public sealed class TargetProperties
    {
        public float sourceTimeSeconds, sourceScalar0, sourceScalar1, sourceScalar2, sourceScalar3;
        public float sourceScalar4, sourceScalar5, sourceScalar6;
        public float[] sourceColor;
    }
    [Serializable] public sealed class SpriteBinding
    {
        public string sourceId, sourceComponentId, sourcePrefabId, spriteFrameSourceId;
        public string spriteFrameTargetPath, ownerPrefabId;
    }
    [Serializable] public sealed class MaterialSpec
    {
        public string profile, sourceMaterialId, sourceMaterialUuid, sourceMaterialDocumentSha256;
        public string effectSourceId, effectDocumentSha256, targetShaderSha256, sourceEffectProgramFingerprint;
        public float staticTimeSeconds;
        public TargetProperties targetProperties;
        public UnityTarget unity;
        public CreatorTarget creator;
        public SpriteBinding[] spriteBindings;
    }

    [Serializable] public sealed class MaterialReadback
    {
        public string sourceMaterialId, profile, materialGuid, shaderGuid;
        public long materialLocalFileId, shaderLocalFileId;
        public string sourceMaterialDocumentSha256, sourceEffectDocumentSha256, shaderPayloadSha256;
        public float staticTimeSeconds;
        public bool sourcePropertiesVerified, targetPropertiesVerified;
        public TargetProperties targetProperties;
        public string[] boundSpriteComponentIds;
    }
    [Serializable] public sealed class PrefabReadback
    {
        public string sourcePrefabId;
        public MaterialReadback[] materials;
    }
    [Serializable] public sealed class ReadbackFile
    {
        public int schemaVersion = 1;
        public string schema, profile, sourceManifestSha256, normalizedIrSha256;
        public PrefabReadback[] prefabs;
    }

    public static Spec Parse(string json)
    {
        if (String.IsNullOrWhiteSpace(json)) return null;
        var spec = JsonUtility.FromJson<Spec>(json);
        if (spec == null || spec.schema != "monkey-prefab-static-time-materials/1" || spec.profile != "cocos24-static-t0-sprite-effects-v1" ||
            spec.target != "unity" || Mathf.Abs(spec.staticTimeSeconds) > 0.000001f || spec.materials == null)
            throw new InvalidOperationException("STATIC_TIME_MATERIAL_SPEC_INVALID");
        return spec;
    }

    static bool SafeTargetPath(string path)
    {
        return !String.IsNullOrWhiteSpace(path) && path.StartsWith("Assets/", StringComparison.Ordinal) &&
            !path.Contains("..") && !path.Contains("\\") && !path.Contains(":");
    }

    static string ProjectPath(string assetPath)
    {
        if (!SafeTargetPath(assetPath)) throw new InvalidOperationException("STATIC_TIME_MATERIAL_PATH_INVALID");
        var root = Directory.GetParent(Application.dataPath);
        if (root == null) throw new InvalidOperationException("STATIC_TIME_PROJECT_ROOT_UNAVAILABLE");
        return Path.GetFullPath(Path.Combine(root.FullName, assetPath.Replace('/', Path.DirectorySeparatorChar)));
    }

    static bool Near(float a, float b) { return Mathf.Abs(a - b) <= 0.00001f; }

    static void EnsurePlannedMaterialMeta(string assetPath, string expectedGuid)
    {
        if (String.IsNullOrWhiteSpace(assetPath) || !assetPath.StartsWith("Assets/", StringComparison.Ordinal) ||
            assetPath.Contains("..") || assetPath.Contains("\\") || assetPath.Contains(":"))
            throw new InvalidOperationException("STATIC_TIME_MATERIAL_PATH_INVALID");
        var absolutePath = ProjectPath(assetPath);
        if (File.Exists(absolutePath))
            throw new InvalidOperationException("STATIC_TIME_MATERIAL_FILE_COLLISION: " + assetPath);
        var metaPath = absolutePath + ".meta";
        var guidOwner = AssetDatabase.GUIDToAssetPath(expectedGuid);
        if (!String.IsNullOrEmpty(guidOwner) && guidOwner != assetPath)
            throw new InvalidOperationException("STATIC_TIME_MATERIAL_GUID_ALREADY_OWNED: " + guidOwner);
        if (File.Exists(metaPath))
        {
            var contents = File.ReadAllText(metaPath);
            var existingGuid = contents.Split('\n').Select(line => line.Trim())
                .FirstOrDefault(line => line.StartsWith("guid:", StringComparison.Ordinal));
            if (existingGuid != "guid: " + expectedGuid || !contents.Contains("NativeFormatImporter:") ||
                !contents.Contains("mainObjectFileID: 2100000"))
                throw new InvalidOperationException("STATIC_TIME_MATERIAL_META_COLLISION: " + metaPath);
            return;
        }
        var directory = Path.GetDirectoryName(metaPath);
        if (String.IsNullOrEmpty(directory))
            throw new InvalidOperationException("STATIC_TIME_MATERIAL_DIRECTORY_MISSING: " + assetPath);
        Directory.CreateDirectory(directory);
        var temporary = metaPath + ".monkey-tmp";
        if (File.Exists(temporary)) throw new InvalidOperationException("STATIC_TIME_MATERIAL_META_TEMP_COLLISION");
        File.WriteAllText(temporary, "fileFormatVersion: 2\nguid: " + expectedGuid +
            "\nNativeFormatImporter:\n  externalObjects: {}\n  mainObjectFileID: 2100000\n  userData:\n  assetBundleName:\n  assetBundleVariant:\n");
        try { File.Move(temporary, metaPath); }
        catch { if (File.Exists(temporary)) File.Delete(temporary); throw; }
    }

    static bool VerifyProperties(Material material, MaterialSpec row)
    {
        if (material == null || row == null || row.targetProperties == null || !material.HasProperty("_StaticSourceTimeSeconds") ||
            !Near(material.GetFloat("_StaticSourceTimeSeconds"), 0f)) return false;
        var p = row.targetProperties;
        if (!Near(p.sourceTimeSeconds, 0f)) return false;
        for (var i = 0; i < 7; i++)
        {
            var name = "_SourceScalar" + i;
            if (!material.HasProperty(name)) return false;
            var values = new[] { p.sourceScalar0, p.sourceScalar1, p.sourceScalar2, p.sourceScalar3,
                p.sourceScalar4, p.sourceScalar5, p.sourceScalar6 };
            var expected = values[i];
            if (!Near(material.GetFloat(name), expected)) return false;
        }
        if (!material.HasProperty("_SourceColor0") || p.sourceColor == null || p.sourceColor.Length != 4) return false;
        var color = material.GetColor("_SourceColor0");
        return Near(color.r, p.sourceColor[0]) && Near(color.g, p.sourceColor[1]) &&
            Near(color.b, p.sourceColor[2]) && Near(color.a, p.sourceColor[3]);
    }

    public static Material Prepare(Spec spec, MaterialSpec row)
    {
        if (spec == null || row == null || row.unity == null || !SafeTargetPath(row.unity.shaderPath) ||
            !SafeTargetPath(row.unity.materialPath) || !System.Text.RegularExpressions.Regex.IsMatch(row.unity.shaderGuid ?? "", "^[0-9a-f]{32}$") ||
            !System.Text.RegularExpressions.Regex.IsMatch(row.unity.materialGuid ?? "", "^[0-9a-f]{32}$"))
            throw new InvalidOperationException("STATIC_TIME_MATERIAL_IDENTITY_INVALID");
        var shader = AssetDatabase.LoadAssetAtPath<Shader>(row.unity.shaderPath);
        if (shader == null || AssetDatabase.AssetPathToGUID(row.unity.shaderPath) != row.unity.shaderGuid)
            throw new InvalidOperationException("STATIC_TIME_SHADER_ASSET_MISSING_OR_WRONG_GUID: " + row.unity.shaderPath);
        var material = AssetDatabase.LoadAssetAtPath<Material>(row.unity.materialPath);
        if (material == null)
        {
            EnsurePlannedMaterialMeta(row.unity.materialPath, row.unity.materialGuid);
            var temporaryMaterial = new Material(shader) { name = "StaticT0Sprite" };
            try
            {
                SetProperties(temporaryMaterial, row.targetProperties);
                if (!VerifyProperties(temporaryMaterial, row))
                    throw new InvalidOperationException("STATIC_TIME_MATERIAL_PRE_SAVE_PROPERTIES_MISMATCH: " + row.sourceMaterialId);
                InternalEditorUtility.SaveToSerializedFileAndForget(
                    new UnityEngine.Object[] { temporaryMaterial }, ProjectPath(row.unity.materialPath), true);
            }
            finally
            {
                if (temporaryMaterial != null) UnityEngine.Object.DestroyImmediate(temporaryMaterial);
            }
            AssetDatabase.ImportAsset(row.unity.materialPath,
                ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
            AssetDatabase.SaveAssets();
            material = AssetDatabase.LoadAssetAtPath<Material>(row.unity.materialPath);
            if (material == null || AssetDatabase.AssetPathToGUID(row.unity.materialPath) != row.unity.materialGuid)
                throw new InvalidOperationException("STATIC_TIME_MATERIAL_CREATE_GUID_MISMATCH: " + row.sourceMaterialId);
        }
        if (material == null || AssetDatabase.AssetPathToGUID(row.unity.materialPath) != row.unity.materialGuid ||
            material.shader != shader || !VerifyProperties(material, row))
            throw new InvalidOperationException("STATIC_TIME_MATERIAL_NATIVE_ASSET_MISMATCH: " + row.sourceMaterialId);
        VerifyMaterialAsset(spec, row, material);
        return material;
    }

    public static void VerifyMaterialAsset(Spec spec, MaterialSpec row, Material material)
    {
        if (spec == null || row == null || row.unity == null || material == null || !EditorUtility.IsPersistent(material) ||
            AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(material)) != row.unity.materialGuid ||
            material.shader == null || !EditorUtility.IsPersistent(material.shader) ||
            AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(material.shader)) != row.unity.shaderGuid ||
            !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material.shader, out string shaderIdentityGuid, out long shaderIdentityLocalId) ||
            shaderIdentityGuid != row.unity.shaderGuid || shaderIdentityLocalId == 0 ||
            !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material, out string materialGuid, out long materialLocalId) ||
            materialGuid != row.unity.materialGuid || materialLocalId == 0 ||
            !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material.shader, out string shaderGuid, out long shaderLocalId) ||
            shaderGuid != row.unity.shaderGuid || shaderLocalId == 0 ||
            !VerifyProperties(material, row))
            throw new InvalidOperationException("STATIC_TIME_MATERIAL_NATIVE_ASSET_MISMATCH: " + (row == null ? "material" : row.sourceMaterialId));
    }

    static void SetProperties(Material material, TargetProperties p)
    {
        if (p == null || p.sourceColor == null || p.sourceColor.Length != 4 || !Near(p.sourceTimeSeconds, 0f))
            throw new InvalidOperationException("STATIC_TIME_MATERIAL_PROPERTIES_INVALID");
        material.SetFloat("_StaticSourceTimeSeconds", 0f);
        material.SetFloat("_SourceScalar0", p.sourceScalar0); material.SetFloat("_SourceScalar1", p.sourceScalar1);
        material.SetFloat("_SourceScalar2", p.sourceScalar2); material.SetFloat("_SourceScalar3", p.sourceScalar3);
        material.SetFloat("_SourceScalar4", p.sourceScalar4); material.SetFloat("_SourceScalar5", p.sourceScalar5);
        material.SetFloat("_SourceScalar6", p.sourceScalar6);
        material.SetColor("_SourceColor0", new Color(p.sourceColor[0], p.sourceColor[1], p.sourceColor[2], p.sourceColor[3]));
    }

    public static void Apply(Spec spec, MaterialSpec row, IDictionary<string, Image> images,
        IDictionary<string, Sprite> sourceFrames)
    {
        var material = Prepare(spec, row);
        var bindings = row.spriteBindings ?? Array.Empty<SpriteBinding>();
        if (images == null || images.Count != bindings.Length || sourceFrames == null)
            throw new InvalidOperationException("STATIC_TIME_SPRITE_BINDING_MAP_MISMATCH");
        foreach (var binding in bindings)
        {
            if (!images.TryGetValue(binding.sourceId, out var image) || image == null ||
                !sourceFrames.TryGetValue(binding.spriteFrameSourceId, out var frame) || frame == null || image.sprite != frame)
                throw new InvalidOperationException("STATIC_TIME_SOURCE_SPRITE_FRAME_MISMATCH: " + binding.sourceId);
            image.material = material;
            if (image.material != material || image.sprite != frame)
                throw new InvalidOperationException("STATIC_TIME_SPRITE_MATERIAL_BINDING_MISMATCH: " + binding.sourceId);
        }
    }

    public static MaterialReadback Read(Spec spec, MaterialSpec row, Material material,
        IDictionary<string, Image> images, IDictionary<string, Sprite> sourceFrames)
    {
        if (spec == null || row == null || row.unity == null || material == null || images == null || sourceFrames == null ||
            images.Count != (row.spriteBindings ?? Array.Empty<SpriteBinding>()).Length ||
            !EditorUtility.IsPersistent(material) ||
            AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(material)) != row.unity.materialGuid ||
            !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material, out string materialGuid, out long materialLocalId) ||
            materialGuid != row.unity.materialGuid || materialLocalId == 0 ||
            material.shader == null || !EditorUtility.IsPersistent(material.shader) ||
            AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(material.shader)) != row.unity.shaderGuid ||
            !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material.shader, out string shaderGuid, out long shaderLocalId) ||
            shaderGuid != row.unity.shaderGuid || shaderLocalId == 0 ||
            !VerifyProperties(material, row))
            throw new InvalidOperationException("STATIC_TIME_MATERIAL_PERSISTENT_READBACK_MISMATCH: " + (row == null ? "material" : row.sourceMaterialId));
        foreach (var binding in row.spriteBindings ?? Array.Empty<SpriteBinding>())
        {
            if (!images.TryGetValue(binding.sourceId, out var image) || image == null || image.material != material ||
                !sourceFrames.TryGetValue(binding.spriteFrameSourceId, out var frame) || frame == null || image.sprite != frame)
                throw new InvalidOperationException("STATIC_TIME_SPRITE_PERSISTENT_READBACK_MISMATCH: " + binding.sourceId);
        }
        var actualProperties = ReadProperties(material);
        return new MaterialReadback { sourceMaterialId = row.sourceMaterialId, profile = row.profile,
            materialGuid = materialGuid, shaderGuid = shaderGuid,
            materialLocalFileId = materialLocalId, shaderLocalFileId = shaderLocalId,
            sourceMaterialDocumentSha256 = row.sourceMaterialDocumentSha256,
            sourceEffectDocumentSha256 = row.effectDocumentSha256,
            shaderPayloadSha256 = spec.targetShaderSha256, staticTimeSeconds = 0f,
            sourcePropertiesVerified = true, targetPropertiesVerified = true,
            targetProperties = actualProperties,
            boundSpriteComponentIds = (row.spriteBindings ?? Array.Empty<SpriteBinding>()).Select(x => x.sourceId).OrderBy(x => x,StringComparer.Ordinal).ToArray() };
    }

    static TargetProperties ReadProperties(Material material)
    {
        var color = material.GetColor("_SourceColor0");
        return new TargetProperties
        {
            sourceTimeSeconds = material.GetFloat("_StaticSourceTimeSeconds"),
            sourceScalar0 = material.GetFloat("_SourceScalar0"), sourceScalar1 = material.GetFloat("_SourceScalar1"),
            sourceScalar2 = material.GetFloat("_SourceScalar2"), sourceScalar3 = material.GetFloat("_SourceScalar3"),
            sourceScalar4 = material.GetFloat("_SourceScalar4"), sourceScalar5 = material.GetFloat("_SourceScalar5"),
            sourceScalar6 = material.GetFloat("_SourceScalar6"),
            sourceColor = new[] { color.r, color.g, color.b, color.a }
        };
    }

    public static void WriteReadback(string path, Spec spec, string prefabId, MaterialReadback[] rows)
    {
        if (spec == null || spec.schema != "monkey-prefab-static-time-materials/1" ||
            spec.profile != "cocos24-static-t0-sprite-effects-v1" || String.IsNullOrWhiteSpace(spec.sourceManifestSha256) ||
            String.IsNullOrWhiteSpace(spec.normalizedIrSha256) || String.IsNullOrWhiteSpace(prefabId))
            throw new InvalidOperationException("STATIC_TIME_READBACK_SOURCE_PINS_MISSING");
        var previous = File.Exists(path) ? JsonUtility.FromJson<ReadbackFile>(File.ReadAllText(path)) : null;
        if (File.Exists(path) && (previous == null || previous.schemaVersion != 1 || previous.schema != spec.schema ||
            previous.profile != spec.profile || previous.sourceManifestSha256 != spec.sourceManifestSha256 ||
            previous.normalizedIrSha256 != spec.normalizedIrSha256))
            throw new InvalidOperationException("STATIC_TIME_READBACK_EXISTING_SOURCE_PINS_MISMATCH");
        var prefabs = (previous != null && previous.prefabs != null ? previous.prefabs : Array.Empty<PrefabReadback>())
            .Where(x => x != null && x.sourcePrefabId != prefabId).ToList();
        prefabs.Add(new PrefabReadback { sourcePrefabId = prefabId, materials = rows ?? Array.Empty<MaterialReadback>() });
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, JsonUtility.ToJson(new ReadbackFile { schema = spec.schema, profile = spec.profile,
            sourceManifestSha256 = spec.sourceManifestSha256, normalizedIrSha256 = spec.normalizedIrSha256,
            prefabs = prefabs.ToArray() }, true));
    }
}
